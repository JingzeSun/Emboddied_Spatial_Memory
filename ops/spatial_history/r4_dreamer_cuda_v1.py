"""D-098 isolated CUDA plugins and full synthetic Dreamer gradient timing.

No optimizer, dataset, checkpoint training, or modification of the CPU env.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import resource
import selectors
import subprocess
import sys
import time

from r4_model_assets_v1 import ASSETS, ROOT, record, write

RUN = ASSETS / 'dreamer-cuda-v1'
OVERLAY = RUN / 'packages'
PYTHON = ASSETS / 'dreamer-env-v1/bin/python'
SOURCES = ['ops/spatial_history/r4_dreamer_cuda_v1.py',
           'ops/spatial_history/r4_model_assets_v1.py',
           'ops/spatial_history/r4_native_models_v1.py',
           'src/spatial_world_model/r4_dreamer_adapter.py',
           'src/spatial_world_model/r4_model_inputs.py',
           'src/spatial_world_model/r4_query_v2.py',
           'src/spatial_world_model/pair_contract.py',
           'src/spatial_world_model/two_gate_contract.py',
           'src/spatial_world_model/__init__.py',
           'tests/spatial_world_model/r4_examples_v2.py',
           'docs/METHOD.md', 'docs/DATA.md', 'docs/DECISIONS.md']


def environment():
    nvidia = Path('/root/miniconda3/lib/python3.12/site-packages/nvidia')
    libraries = sorted(str(p) for p in nvidia.glob('*/lib') if p.is_dir())
    return dict(os.environ, PYTHONPATH=str(OVERLAY), JAX_PLATFORMS='cuda',
                XLA_FLAGS='--xla_gpu_cuda_data_dir=/usr/local/cuda',
                XLA_PYTHON_CLIENT_PREALLOCATE='false',
                PATH='/usr/local/cuda/bin:' + os.environ['PATH'],
                LD_LIBRARY_PATH=':'.join(libraries),
                PYTHONDONTWRITEBYTECODE='1', PIP_NO_CACHE_DIR='1')


def child_check():
    from r4_native_models_v1 import no_dataset, validate_sources
    validate_sources()
    sys.addaudithook(no_dataset)
    sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests/spatial_world_model'), str(ASSETS / 'dreamerv3')]
    import jax
    import jax.numpy as jnp
    import ninjax as nj
    from r4_examples_v2 import public
    from spatial_world_model.r4_query_v2 import from_public_query
    from spatial_world_model.r4_dreamer_adapter import DreamerTask, tensorize
    if jax.__version__ != '0.4.33' or jax.default_backend() != 'gpu':
        raise RuntimeError('pinned JAX GPU required, no CPU fallback')
    history, controls, goal = tensorize(from_public_query(public(range(121))))
    labels = {'position_m': jnp.zeros((1, 200, 3), jnp.float32),
              'contact': jnp.zeros((1, 200), bool), 'success': jnp.ones((1,), bool)}
    images = {key: jnp.repeat(history[key][:, -1:], 200, axis=1)
              for key in ('rgb', 'depth_m', 'depth_valid')}
    model = DreamerTask(name='dreamer_task')
    loss = nj.pure(model.loss)
    initialize = jax.jit(lambda: loss({}, history, controls, goal, labels, images, seed=7923, create=True))
    params, initial = initialize()
    jax.block_until_ready(initial)

    def objective(p):
        _, (total, terms) = loss(p, history, controls, goal, labels, images, seed=7925)
        return total, terms

    backward = jax.jit(jax.value_and_grad(objective, has_aux=True))
    seconds = []
    for index in range(4):
        began = time.monotonic()
        (total, terms), grads = backward(params)
        jax.block_until_ready(grads)
        seconds.append(time.monotonic() - began)
        if not bool(jnp.isfinite(total)) or not all(bool(jnp.isfinite(g).all()) for g in grads.values()):
            raise ValueError('nonfinite full sequence gradient')
        print('D CUDA FULL BACKWARD', index, seconds[-1], flush=True)
    norms = {}
    for part in ('rgb', 'depth', 'metadata', 'rssm', 'task', 'rgb_decoder', 'depth_decoder'):
        values = [g for name, g in grads.items() if '/' + part + '/' in name]
        if not values:
            raise ValueError('missing gradient path ' + part)
        norms[part] = sum(float(jnp.square(g).sum()) for g in values) ** 0.5
        if not norms[part] > 0:
            raise ValueError('zero gradient path ' + part)
    memory = jax.devices()[0].memory_stats() or {}
    peak = memory.get('peak_bytes_in_use')
    if peak is None or peak > 28 * 2**30:
        raise RuntimeError('missing or excessive JAX peak GPU allocation')
    if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 > 12 * 2**30:
        raise RuntimeError('RSS budget exceeded')
    result = {'jax': jax.__version__, 'backend': jax.default_backend(), 'devices': [str(d) for d in jax.devices()],
              'history_frames': 121, 'future_steps': 200, 'parameter_count': sum(v.size for v in params.values()),
              'gradient_l2': norms, 'compile_and_first_backward_s': seconds[0],
              'three_warm_backward_s': seconds[1:], 'memory_stats': memory,
              'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
              'synthetic_loss': float(total), 'loss_terms': {k: float(v) for k, v in terms.items()},
              'optimizer_constructed': False, 'new_training_steps': 0, 'dataset_files_read': 0,
              'optimizer_throughput_measured': False, 'trained_model_ready': False}
    write(RUN / 'check/result.json', result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('step', choices=['install', 'check', 'export', '_child'])
    step = parser.parse_args().step
    if step == '_child':
        child_check()
        return
    if step == 'export':
        artifacts = {p.relative_to(RUN).as_posix(): {**record(p), 'text': p.read_text()}
                     for folder in ('install', 'check') for p in (RUN / folder).glob('*.json')}
        write(ROOT / 'results/spatial_history_r4_dreamer_cuda_v1.json',
              {'stage': 'R4-5-dreamer-cuda-v1', 'artifacts': artifacts, 'exporter': record(Path(__file__)),
               'trained_model_ready': False})
        print('D CUDA EXPORTED exit=0', flush=True)
        return
    if step == 'check':
        previous = json.loads((RUN / 'install/receipt.json').read_text())
        if previous['exit_code'] != 0:
            raise RuntimeError('install success required')
        for name, item in previous['package_files'].items():
            if record(OVERLAY / name) != item:
                raise ValueError('installed plugin changed')
    stage = RUN / step
    stage.mkdir(parents=True, exist_ok=False)
    binding = {name: record(ROOT / name) for name in SOURCES}
    write(stage / 'started.json', {'time_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
          'binding': binding})
    began = time.monotonic()
    try:
        if step == 'install':
            args = [str(PYTHON), '-m', 'pip', 'install', '--no-deps', '--no-cache-dir',
                    '--target', str(OVERLAY), '--report', str(stage / 'pip_report.json'),
                    'jax-cuda12-plugin==0.4.33', 'jax-cuda12-pjrt==0.4.33']
        else:
            args = [str(PYTHON), '-B', str(Path(__file__)), '_child']
        with (stage / 'run.log').open('x') as log:
            proc = subprocess.Popen(args, env=environment(), cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            reader = selectors.DefaultSelector()
            reader.register(proc.stdout, selectors.EVENT_READ)
            try:
                while reader.get_map():
                    if time.monotonic() - began > 1800:
                        raise TimeoutError('stage 1800-second budget exceeded')
                    for key, _ in reader.select(1):
                        chunk = os.read(key.fd, 65536)
                        if not chunk:
                            reader.unregister(key.fileobj)
                            continue
                        output = chunk.decode('utf-8', errors='replace')
                        log.write(output); log.flush()
                        print(output, end='', flush=True)
                code = proc.wait(timeout=5)
            except BaseException:
                proc.kill(); proc.wait()
                raise
            finally:
                reader.close()
        if code:
            raise RuntimeError('child exit=' + str(code))
        if step == 'install':
            (OVERLAY / 'nvidia').symlink_to('/root/miniconda3/lib/python3.12/site-packages/nvidia', target_is_directory=True)
        package_files = {p.relative_to(OVERLAY).as_posix(): record(p) for p in OVERLAY.rglob('*')
                         if p.is_file() and not p.is_symlink()}
        if sum(v['bytes'] for v in package_files.values()) > 2**30:
            raise RuntimeError('overlay 1 GiB budget exceeded')
        if binding != {name: record(ROOT / name) for name in SOURCES}:
            raise ValueError('source changed')
        write(stage / 'receipt.json', {'exit_code': 0, 'elapsed_s': time.monotonic() - began,
              'started': record(stage / 'started.json'), 'log': record(stage / 'run.log'),
              'package_files': package_files,
              'result': record(stage / 'result.json') if step == 'check' else record(stage / 'pip_report.json')})
        print('D CUDA', step, 'COMPLETE exit=0', flush=True)
    except BaseException as error:
        write(stage / 'failure.json', {'error': repr(error), 'elapsed_s': time.monotonic() - began, 'exit_code': 1})
        raise


if __name__ == '__main__':
    main()
