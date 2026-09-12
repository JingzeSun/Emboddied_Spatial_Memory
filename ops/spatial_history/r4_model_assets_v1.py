"""Server-only author-source/environment audit; no dataset or training access.

Stages are immutable. A failed attempt is preserved; repair requires a new stage
name/version. See D-091, METHOD and DATA for the engineering-only boundary.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
ASSETS = Path('/root/sh05-assets-v1')
RUN = ASSETS / 'audit-v1'
SOURCES = {
    'dreamerv3': 'e3f02248693a79dc8b0ebd62c93683888ddaccfe',
    'flowm': 'c909c54a3d58ae240de03f5ebbec222d3e6b1264',
    'pointworld': '05484826dfef74cbe278a3974179a5a16705d35d',
}
DEADLINE = datetime.datetime.fromisoformat('2026-09-13T18:14:12+00:00')


def record(path):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'bytes': path.stat().st_size, 'sha256': digest}


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def call(args, log, timeout=600):
    print('RUN', ' '.join(map(str, args)), flush=True)
    env = dict(os.environ, PIP_NO_CACHE_DIR='1', PYTHONDONTWRITEBYTECODE='1')
    process = subprocess.Popen(list(map(str, args)), env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True)
    # communicate enforces timeout even if the child is silent.
    try:
        output, _ = process.communicate(timeout=timeout)
    except BaseException:
        process.kill()
        output, _ = process.communicate()
        log.write(output); log.flush()
        raise
    log.write(output); log.flush()
    print(output[-5000:], flush=True)
    if process.returncode:
        raise RuntimeError(f'command exit={process.returncode}: {args[0]}')


def sources(log):
    result = {}
    for name, commit in SOURCES.items():
        path = ASSETS / name
        actual = subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != commit:
            raise ValueError('author commit mismatch: ' + name)
        dirty = subprocess.check_output(['git', '-C', str(path), 'diff', '--name-only', 'HEAD'], text=True)
        if dirty:
            raise ValueError('modified author source: ' + name)
        files = subprocess.check_output(['git', '-C', str(path), 'ls-files', '-z']).decode().split('\0')
        result[name] = {'commit': commit, 'files': {f: record(path / f) for f in files if f and (path / f).is_file()}}
    return {'sources': result, 'disk_free_bytes': {str(p): shutil.disk_usage(p).free for p in (ASSETS, Path('/root/autodl-tmp'))}}


def env_flowm(log):
    env = ASSETS / 'flowm-env-v1'
    if env.exists():
        raise ValueError('environment already exists without successful receipt')
    call(['/root/miniconda3/bin/python', '-m', 'venv', '--system-site-packages', env], log)
    py = env / 'bin/python'
    call([py, '-m', 'pip', 'install', 'einops==0.8.1'], log)
    call([py, '-c', 'import torch,einops; assert torch.__version__=="2.8.0+cu128"; assert torch.cuda.is_available(); print(torch.__version__,einops.__version__)'], log)
    call([py, '-m', 'pip', 'freeze'], log)
    return {'python': str(py), 'base_site_packages_read_only': True, 'torch': '2.8.0+cu128'}


def env_dreamer(log):
    env = ASSETS / 'dreamer-env-v1'
    if env.exists():
        raise ValueError('environment already exists without successful receipt')
    call(['/root/miniconda3/bin/python', '-m', 'venv', env], log)
    py = env / 'bin/python'
    call([py, '-m', 'pip', 'install', 'jax==0.4.33', 'jaxlib==0.4.33', 'numpy==1.26.4',
          'elements==3.19.1', 'ninjax==3.5.1', 'optax==0.2.3', 'chex==0.1.87',
          'granular==0.20.3', 'portal==3.5.0', 'scope==0.4.4', 'einops==0.8.1'], log, 1200)
    call([py, '-m', 'pip', 'check'], log)
    call([py, '-m', 'pip', 'freeze'], log)
    return {'python': str(py), 'jax_backend': 'cpu', 'gpu_training_ready': False}


def export():
    artifacts = {}
    for path in sorted(RUN.glob('*/*')):
        if path.is_file():
            artifacts[path.relative_to(RUN).as_posix()] = {**record(path), 'text': path.read_text()}
    receipts = {k.split('/')[0]: json.loads(v['text']) for k,v in artifacts.items() if k.endswith('/receipt.json')}
    value = {'stage': 'SH-04-R4-model-assets-v1', 'artifacts': artifacts, 'receipts': receipts,
             'author_forward_passed': [], 'adapted_models_ready': [], 'new_training_steps': 0,
             'exporter': record(Path(__file__))}
    target = ROOT / 'results/spatial_history_r4_model_assets_v1.json'
    write(target, value)
    print('EXPORTED', target, 'exit=0')


def main():
    if platform.system() != 'Linux':
        raise RuntimeError('server only')
    parser = argparse.ArgumentParser()
    parser.add_argument('step', choices=['sources', 'env_flowm', 'env_dreamer', 'export'])
    step = parser.parse_args().step
    if step == 'export':
        export(); return
    if datetime.datetime.now(datetime.timezone.utc) >= DEADLINE:
        raise RuntimeError('authorized window expired')
    if shutil.disk_usage(ASSETS).free < 5 * 2**30:
        raise RuntimeError('need 5 GiB free system disk')
    dest = RUN / step
    receipt = dest / 'receipt.json'
    if receipt.exists():
        value = json.loads(receipt.read_text())
        if value['exit_code'] != 0 or record(dest/'run.log') != value['log']:
            raise RuntimeError('saved receipt/log mismatch')
        print('REUSED', step, 'exit=0'); return
    dest.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    write(dest/'started.json', {'time_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'step': step, 'script': record(Path(__file__)), 'new_training_steps': 0})
    try:
        with (dest/'run.log').open('x') as log:
            extra = globals()[step](log)
        write(receipt, {'step': step, 'exit_code': 0, 'elapsed_s': time.monotonic()-started,
                        'log': record(dest/'run.log'), **extra})
        print('COMPLETE', step, 'exit=0', flush=True)
    except BaseException as error:
        write(dest/'failure.json', {'step': step, 'error': repr(error), 'exit_code': 1,
                                  'elapsed_s': time.monotonic()-started})
        raise


if __name__ == '__main__':
    main()
