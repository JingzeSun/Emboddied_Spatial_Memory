"""Bounded original-module checks, with synthetic inputs and zero training.

This does not implement task adapters or evaluate learned task performance.
FloWM package initializers that eagerly import unrelated trainers are excluded;
the three original model/patch/FOV source files execute unchanged.
"""
import argparse
import datetime
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import sys
import time
import types

from r4_model_assets_v1 import ASSETS, DEADLINE, ROOT, SOURCES, record, write, call

RUN = ASSETS / 'native-audit-v1'
SEED = 7901


def validate_sources():
    receipt = json.loads((ASSETS/'audit-v1/sources/receipt.json').read_text())
    for name, version in SOURCES.items():
        source = receipt['sources'][name]
        assert source['commit'] == version
        for relative, expected in source['files'].items():
            assert record(ASSETS/name/relative) == expected, (name, relative)
    return record(ASSETS/'audit-v1/sources/receipt.json')


def no_dataset(event, args):
    if event == 'open' and args and isinstance(args[0], (str, bytes)):
        path = Path(os.fsdecode(args[0])).resolve()
        if path.is_relative_to('/root/autodl-tmp/spatial-history'):
            raise PermissionError('native check has no project dataset permission')


def support_flowm(log):
    py = ASSETS/'flowm-env-v1/bin/python'
    call([py, '-m', 'pip', 'install', 'timm==1.0.19', 'huggingface-hub==0.26.2',
          'safetensors==0.4.5'], log, 900)
    call([py, '-c', 'import torch,timm; assert torch.__version__=="2.8.0+cu128"; print(timm.__version__)'], log)
    call([py, '-m', 'pip', 'freeze'], log)
    return {'torch': '2.8.0+cu128', 'timm': '1.0.19'}


def flowm(log):
    # Only bypass eager package initializers. No stub model/function is supplied.
    root = ASSETS/'flowm'
    namespaces = ['algorithms', 'algorithms.mem_wm', 'algorithms.mem_wm.backbones',
                  'algorithms.mem_wm.backbones.embeddings', 'algorithms.mem_wm.backbones.flowm']
    for name in namespaces:
        module = types.ModuleType(name)
        module.__path__ = [str(root.joinpath(*name.split('.')))]
        sys.modules[name] = module
    original = importlib.import_module('algorithms.mem_wm.backbones.flowm.flowm_models_3d')
    import torch
    torch.manual_seed(SEED); torch.cuda.manual_seed_all(SEED)
    torch.set_num_threads(4)
    model = original.MapLatentProcessor(world_size=24, embed_dim=256, num_heads=8,
        depth=6, img_size=(64,64), patch_size=8, v_range=1).cuda().eval()
    device = torch.device('cuda')
    mask = torch.zeros((49,49), dtype=torch.bool, device=device)
    mask[23:26,23:26] = True
    initial = model.init_map(1, device)
    frame = torch.linspace(0,1,3*64*64,device=device).reshape(1,3,64,64)
    with torch.no_grad():
        state = model(initial, frame, mask)
        assert state.shape == (1,5,49,49,256)
        assert torch.isfinite(state).all()
        assert torch.count_nonzero(initial) == 0
        assert torch.equal(state[:,:,~mask], initial[:,:,~mask])
        assert not torch.equal(state[:,:,mask], initial[:,:,mask])
        # Source accepts explicitly carried state; split calls must retain it.
        whole = initial
        for _ in range(6): whole = model(whole, frame, mask)
        chunk = initial
        for length in (2,4):
            for _ in range(length): chunk = model(chunk, frame, mask)
        assert torch.equal(whole, chunk)
        with_action = model(state, frame, mask, torch.ones((1,1,256),device=device))
        no_action = model(state, frame, mask, torch.zeros((1,1,256),device=device))
        assert not torch.equal(with_action, no_action)
        shifted = model.shift_v_channels(state)
        assert shifted.shape == state.shape and torch.isfinite(shifted).all()
    torch.cuda.synchronize()
    return {'checks': ['finite_native_forward', 'full_map_shape', 'input_immutable',
        'unseen_unchanged', 'seen_updated', 'explicit_state_chunk_equivalence',
        'action_token_effect', 'five_velocity_channel_shift'],
        'source_module': record(Path(original.__file__)), 'excluded_initializers': namespaces,
        'native_map_shape': list(state.shape), 'native_image_shape': list(frame.shape),
        'parameter_count': sum(p.numel() for p in model.parameters()),
        'max_cuda_allocated_bytes': torch.cuda.max_memory_allocated(),
        'dependencies': {n:importlib.metadata.version(n) for n in ('torch','torchvision','timm','einops')},
        'native_roll_wraps': True, 'task_adapter_ready': False, 'training_steps': 0}


def dreamer(log):
    os.environ['JAX_PLATFORMS'] = 'cpu'
    os.environ['XLA_FLAGS'] = '--xla_cpu_multi_thread_eigen=false intra_op_parallelism_threads=4'
    sys.path.insert(0, str(ASSETS/'dreamerv3'))
    import elements
    import jax
    import jax.numpy as jnp
    import ninjax as nj
    import numpy as np
    from dreamerv3.rssm import RSSM, Encoder
    import dreamerv3.rssm as original
    rssm = RSSM({'velocity_dt': elements.Space(np.float32, (4,))},
        deter=1024, hidden=512, stoch=32, classes=32, blocks=8, name='rssm')
    encoder = Encoder({'rgb': elements.Space(np.uint8, (80,80,3))}, name='encoder')
    image = jnp.broadcast_to(jnp.arange(80*80*3,dtype=jnp.uint8).reshape(1,1,80,80,3), (1,121,80,80,3))
    reset = jnp.zeros((1,121),bool).at[:,0].set(True)
    past = {'velocity_dt': jnp.zeros((1,121,4),jnp.float32)}
    future = {'velocity_dt': jnp.zeros((1,200,4),jnp.float32)}
    def forward(controls):
        _, _, tokens = encoder({}, {'rgb':image}, reset, False)
        state, entries, observed = rssm.observe(rssm.initial(1), tokens, past, reset, False)
        last, predicted, used = rssm.imagine(state, controls, 200, False)
        return tokens, state, observed, last, predicted, used
    pure = nj.pure(forward)
    init = jax.jit(lambda: pure({}, future, seed=SEED, create=True))
    params, result = init()
    jax.block_until_ready(result)
    apply = jax.jit(lambda p,a: pure(p,a,seed=SEED+1))
    _, left = apply(params, future)
    _, repeat = apply(params, future)
    changed = {'velocity_dt': future['velocity_dt'].at[:,0,0].set(0.5)}
    _, right = apply(params, changed)
    jax.block_until_ready(right)
    assert result[0].shape[:2] == (1,121)
    assert result[2]['deter'].shape == (1,121,1024)
    assert result[4]['deter'].shape == (1,200,1024)
    assert result[4]['stoch'].shape == (1,200,32,32)
    assert all(bool(jnp.isfinite(x).all()) for x in jax.tree.leaves(result))
    assert all(np.array_equal(a,b) for a,b in zip(jax.tree.leaves(left),jax.tree.leaves(repeat)))
    assert all(np.array_equal(a,b) for a,b in zip(jax.tree.leaves(left[1]),jax.tree.leaves(right[1])))
    assert not np.array_equal(left[4]['deter'][:,0],right[4]['deter'][:,0])
    assert all(not any(x in name for x in ('actor','critic','value','reward')) for name in params)
    return {'checks': ['native_80px_encoder', 'complete_121_observations', '200_control_only_steps',
        'finite_native_states', 'same_seed_replay', 'branch_initial_state_equal', 'first_action_alignment',
        'no_actor_critic_parameters'], 'source_module': record(Path(original.__file__)),
        'token_shape': list(result[0].shape), 'observed_deter_shape': list(result[2]['deter'].shape),
        'future_deter_shape': list(result[4]['deter'].shape),
        'parameter_count': sum(x.size for x in jax.tree.leaves(params)),
        'parameter_names': sorted(params), 'jax_backend': jax.default_backend(),
        'dependencies': {n:importlib.metadata.version(n) for n in ('jax','jaxlib','ninjax','elements','numpy')},
        'task_adapter_ready': False, 'training_steps': 0}


def main():
    assert platform.system() == 'Linux', 'server only'
    parser = argparse.ArgumentParser()
    parser.add_argument('step',choices=['support_flowm','flowm','dreamer','export'])
    step = parser.parse_args().step
    if step == 'export':
        files = {p.relative_to(RUN).as_posix(): {**record(p),'text':p.read_text()}
                 for p in sorted(RUN.glob('*/*')) if p.is_file()}
        complete = []
        for name in ('support_flowm','flowm','dreamer'):
            receipt = RUN/name/'receipt.json'
            if not receipt.exists(): continue
            value = json.loads(receipt.read_text())
            assert value['exit_code'] == 0
            assert value['log'] == record(RUN/name/'run.log')
            assert value['started'] == record(RUN/name/'started.json')
            complete.append(name)
        write(ROOT/'results/spatial_history_r4_native_models_v1.json',
              {'stage':'SH-04-R4-native-models-v1','artifacts':files,
               'complete_stages':complete, 'status':'passed' if len(complete)==3 else 'incomplete_or_failed',
               'adapted_models_ready':[], 'new_training_steps':0,'exporter':record(Path(__file__))})
        print('EXPORTED native-models-v1 exit=0'); return
    assert datetime.datetime.now(datetime.timezone.utc) < DEADLINE
    binding = validate_sources()
    assert (ASSETS/'audit-v1/env_flowm/receipt.json').exists() if step != 'dreamer' else (ASSETS/'audit-v1/env_dreamer/receipt.json').exists()
    if step == 'flowm': assert (RUN/'support_flowm/receipt.json').exists()
    dest = RUN/step
    dest.mkdir(parents=True,exist_ok=False)
    began = time.monotonic()
    write(dest/'started.json', {'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'script':record(Path(__file__)),'source_receipt':binding,'step':step,'seed':SEED})
    def timeout(*_): raise TimeoutError('native stage limit')
    signal.signal(signal.SIGALRM,timeout); signal.alarm(1200)
    sys.addaudithook(no_dataset)
    try:
        with (dest/'run.log').open('x') as log: result = globals()[step](log)
        result.update(step=step,exit_code=0,elapsed_s=time.monotonic()-began,
                      peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                      log=record(dest/'run.log'),started=record(dest/'started.json'))
        write(dest/'receipt.json',result)
        print(json.dumps(result,sort_keys=True),flush=True)
        print('NATIVE COMPLETE',step,'exit=0',flush=True)
    except BaseException as error:
        write(dest/'failure.json',{'error':repr(error),'step':step,'exit_code':1,'elapsed_s':time.monotonic()-began})
        raise


if __name__ == '__main__': main()
