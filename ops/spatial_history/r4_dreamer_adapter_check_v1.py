"""D-093 full RGBD Dreamer adapter synthetic forward/backward check; no optimizer."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

from r4_model_assets_v1 import ASSETS, DEADLINE, ROOT, record, write
from r4_native_models_v1 import no_dataset, validate_sources

RUN=ASSETS/'dreamer-adapter-check-v1'
FILES=['src/spatial_world_model/r4_model_inputs.py','src/spatial_world_model/r4_dreamer_adapter.py',
       'src/spatial_world_model/__init__.py',
       'src/spatial_world_model/r4_query_v2.py','src/spatial_world_model/pair_contract.py',
       'src/spatial_world_model/two_gate_contract.py','tests/spatial_world_model/r4_examples_v2.py',
       'ops/spatial_history/r4_dreamer_adapter_check_v1.py',
       'ops/spatial_history/r4_model_assets_v1.py','ops/spatial_history/r4_native_models_v1.py',
       'docs/METHOD.md','docs/DATA.md','docs/DECISIONS.md']


def check():
    os.environ['JAX_PLATFORMS']='cpu'
    os.environ['XLA_FLAGS']='--xla_cpu_multi_thread_eigen=false intra_op_parallelism_threads=4'
    sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests/spatial_world_model'),str(ASSETS/'dreamerv3')]
    import jax
    import jax.numpy as jnp
    import ninjax as nj
    import numpy as np
    from r4_examples_v2 import public
    from spatial_world_model.r4_query_v2 import from_public_query
    from spatial_world_model.r4_model_inputs import prepare
    from spatial_world_model.r4_dreamer_adapter import DreamerTask,tensorize
    source=public(range(121))
    source['history'][0]['rgb'][0:3]=[120,40,10]
    query=from_public_query(source)
    prepared=prepare(query)
    assert len(prepared['history']['rgb'])==121
    assert prepared['history']['rgb'][0][:3]==[120,40,10]
    assert prepared['history']['depth_m'][0][-1]==0
    assert prepared['history']['depth_valid'][0][-1] is False
    assert len(prepared['history']['metadata'][0])==37
    assert prepared['controls'][0]==[0,0.4,0,1]
    illegal=dict(query,actual_future_robot_motion=[0])
    try:prepare(illegal)
    except ValueError:pass
    else:raise AssertionError('private input accepted')
    history,controls,goal=tensorize(query)
    assert history['depth_m'].dtype==jnp.float32
    model=DreamerTask(name='dreamer_task')
    predict=nj.pure(model.predict)
    initial=jax.jit(lambda h,a,g:predict({},h,a,g,seed=7903,create=True))
    params,out=initial(history,controls,goal);jax.block_until_ready(out)
    assert out['observed']['tokens'].shape==(1,121,9856)
    assert out['task']['object_position_m'].shape==(1,200,3)
    assert out['task']['contact_logit'].shape==(1,200)
    assert out['task']['success_logit'].shape==(1,)
    assert all(bool(jnp.isfinite(x).all()) for x in jax.tree.leaves(out))
    apply=jax.jit(lambda p,h,a,g:predict(p,h,a,g,seed=7905))
    _,left=apply(params,history,controls,goal)
    changed=controls.at[:,100,0].set(0.5)
    _,right=apply(params,history,changed,goal);jax.block_until_ready(right)
    assert all(np.array_equal(a,b) for a,b in zip(jax.tree.leaves(left['decision']),jax.tree.leaves(right['decision'])))
    assert np.array_equal(left['task']['object_position_m'][:,:100],right['task']['object_position_m'][:,:100])
    assert not np.array_equal(left['future']['deter'][:,100],right['future']['deter'][:,100])
    print('D ADAPTER forward, full history, causal control and task heads passed',flush=True)
    labels={'position_m':jnp.zeros((1,200,3),jnp.float32),'contact':jnp.zeros((1,200),bool),'success':jnp.ones((1,),bool)}
    images={'rgb':jnp.repeat(history['rgb'][:,-1:],200,axis=1),
            'depth_m':jnp.repeat(history['depth_m'][:,-1:],200,axis=1),
            'depth_valid':jnp.repeat(history['depth_valid'][:,-1:],200,axis=1)}
    loss=nj.pure(model.loss)
    initialise_loss=jax.jit(lambda p,h,a,g,l,i:loss(p,h,a,g,l,i,seed=7907,create=True))
    all_params,loss_output=initialise_loss(params,history,controls,goal,labels,images)
    jax.block_until_ready(loss_output)
    def objective(p,h,a,g,l,i):
        _,(total,terms)=loss(p,h,a,g,l,i,seed=7909)
        return total,terms
    backward=jax.jit(jax.value_and_grad(objective,has_aux=True))
    (total,terms),grads=backward(all_params,history,controls,goal,labels,images)
    jax.block_until_ready(grads)
    assert bool(jnp.isfinite(total)) and all(bool(jnp.isfinite(x).all()) for x in grads.values())
    norms={}
    for part in ('rgb','depth','metadata','rssm','task','rgb_decoder','depth_decoder'):
        values=[g for name,g in grads.items() if '/'+part+'/' in name]
        assert values,part
        norm=sum(float(jnp.square(g).sum()) for g in values)
        assert norm>0 and np.isfinite(norm),(part,norm)
        norms[part]=norm**0.5
    assert not any('/actor/' in name or '/critic/' in name for name in all_params)
    task_hash=hashlib.sha256()
    for key in sorted(out['task']):task_hash.update(np.asarray(out['task'][key]).tobytes())
    return {'checks':['all_121_public_frames','native_rgb_preserved','invalid_depth_mask',
        '37_public_metadata_values','control_scale_and_dt','private_field_rejection','float32_depth',
        '9856_rgbd_metadata_tokens','200_position_contact_success_heads','finite_forward',
        'branch_decision_equal','later_control_no_earlier_effect','action_alignment',
        'finite_full_200_step_backward','seven_gradient_paths','no_actor_critic'],
        'history_frames':121,'future_steps':200,'compute_dtype':'float32','backend':jax.default_backend(),
        'parameter_count':sum(p.size for p in all_params.values()),
        'parameter_shapes':{n:list(p.shape) for n,p in all_params.items()},
        'gradient_l2':norms,'synthetic_loss_terms':{k:float(x) for k,x in terms.items()},
        'synthetic_total_loss':float(total),'initial_task_sha256':task_hash.hexdigest(),
        'new_training_steps':0,'optimizer_constructed':False,'real_data_predictions':0,
        'trained_model_ready':False}


def main():
    assert sys.platform.startswith('linux')
    parser=argparse.ArgumentParser();parser.add_argument('step',choices=['run','export'])
    step=parser.parse_args().step
    if step=='export':
        artifacts={p.name:{**record(p),'text':p.read_text()} for p in RUN.glob('*.json')}
        write(ROOT/'results/spatial_history_r4_dreamer_adapter_v1.json',
            {'stage':'SH-04-R4-dreamer-adapter-v1','artifacts':artifacts,'exporter':record(Path(__file__))})
        print('D ADAPTER EXPORTED exit=0');return
    assert datetime.datetime.now(datetime.timezone.utc)<DEADLINE
    validate_sources()
    assert (ASSETS/'native-audit-v1/dreamer/receipt.json').exists()
    RUN.mkdir(exist_ok=False)
    binding={f:record(ROOT/f) for f in FILES}
    write(RUN/'started.json',{'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'binding':binding,'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()})
    began=time.monotonic()
    def timeout(*_):raise TimeoutError('Dreamer adapter 1800-second check limit')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(1800)
    sys.addaudithook(no_dataset)
    try:
        result=check()
        assert binding=={f:record(ROOT/f) for f in FILES}
        assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024 <= 12*2**30, 'RSS budget exceeded'
        write(RUN/'receipt.json',{'exit_code':0,'result':result,'elapsed_s':time.monotonic()-began,
            'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'started':record(RUN/'started.json')})
        print('D ADAPTER COMPLETE checks='+str(len(result['checks']))+' exit=0',flush=True)
    except BaseException as error:
        write(RUN/'failure.json',{'exit_code':1,'error':repr(error),'elapsed_s':time.monotonic()-began})
        raise


if __name__=='__main__':main()
