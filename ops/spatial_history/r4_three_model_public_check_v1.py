"""D-096 one fixed existing public history/nine controls; no truth or training."""
import argparse
import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
from r4_model_assets_v1 import ASSETS,DEADLINE,ROOT,record,write

RUN=ASSETS/'three-model-public-check-v1'
CONFIG='configs/spatial_history/r4_frontend_stage_v2r1.json'
FILES=['src/spatial_world_model/'+f for f in ('__init__.py','r4_query_v2.py','pair_contract.py',
       'two_gate_contract.py','r4_model_inputs.py','r4_model_prediction.py','r4_torch_task.py',
       'r4_dreamer_adapter.py','r4_dinowm_adapter.py','r4_flowm_adapter.py')]+[
       'ops/spatial_history/r4_three_model_public_check_v1.py','ops/spatial_history/r4_model_assets_v1.py',
       'ops/spatial_history/r4_native_models_v1.py','ops/spatial_history/r4_dinowm_assets_v1.py',
       'ops/spatial_history/r4_flowm_adapter_check_v1.py',CONFIG,'docs/METHOD.md','docs/DATA.md','docs/DECISIONS.md']
NAMES={'D':'dreamer','F':'flowm','W':'dinowm'}


def prior(model):
    directory=ASSETS/(NAMES[model]+'-adapter-check-v1')
    receipt=json.loads((directory/'receipt.json').read_text())
    assert receipt['exit_code']==0 and receipt['started']==record(directory/'started.json')
    started=json.loads((directory/'started.json').read_text())
    for name,expected in started['binding'].items():
        blob=subprocess.check_output(['git','show',started['commit']+':'+name],cwd=ROOT)
        assert {'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest()}==expected
        if name.startswith('src/'):assert record(ROOT/name)==expected,('adapter changed since check',name)
    if model=='W':
        from r4_dinowm_assets_v1 import sources,WEIGHT
        sources();assert record(WEIGHT)==started['weight']
    else:
        from r4_native_models_v1 import validate_sources
        validate_sources()
    return record(directory/'receipt.json')


def inputs():
    cfg=json.loads((ROOT/CONFIG).read_text())
    # Deterministic first registered history, selected without accuracy/labels.
    relative=f"execution/{cfg['families'][0]}/data/public/{cfg['worlds'][0]}.json.gz"
    path=(Path(cfg['source_directory'])/relative).resolve()
    expected=cfg['public_registration'][relative]
    def guard(event,args):
        if event=='open' and args and isinstance(args[0],(str,bytes)):
            candidate=Path(os.fsdecode(args[0])).resolve()
            if candidate.is_relative_to('/root/autodl-tmp/spatial-history') and candidate!=path:
                raise PermissionError('public model check forbids all other project data')
    sys.addaudithook(guard)
    assert record(path)==expected
    with gzip.open(path,'rt') as stream:value=json.load(stream)
    assert len(value['history'])==121 and len(value['actions'])==9
    from spatial_world_model.r4_query_v2 import from_public_query,SOURCE_VERSION,validate_controls
    query=from_public_query({'schema_version':SOURCE_VERSION,'history':value['history'],
                            'controls':value['actions'][0],'goal':value['goal']})
    actions=[]
    for action in value['actions']:
        control={k:[step[k] for step in action] for k in ('ee_velocity_mps','duration_s')}
        validate_controls(control)
        actions.append([[*[v/.5 for v in step['ee_velocity_mps']],step['duration_s']/.1] for step in action])
    # Explicit forbidden-open check; no bytes are consumed.
    private=Path(cfg['source_directory'])/next(iter(cfg['truth_registration']))
    try:private.open('rb')
    except PermissionError:pass
    else:raise AssertionError('private guard failed')
    return query,actions,{'path':str(path),'relative':relative,**expected},cfg['actions']


def check_packing():
    from spatial_world_model.r4_model_prediction import pack,aggregate,sigmoid
    assert sigmoid(0)==.5 and sigmoid(1000)==1 and sigmoid(-1000)==0
    for value in (float('nan'),float('inf')):
        try:sigmoid(value)
        except ValueError:pass
        else:raise AssertionError('nonfinite logit accepted')
    samples=[pack([[0.,0.,0.]]*200,[float(i%2)]*200,float(i%2)) for i in range(16)]
    assert abs(aggregate(samples)['task_success_probability']-(.5+sigmoid(1))/2)<1e-12


def dreamer(query,actions,dest,names):
    os.environ['JAX_PLATFORMS']='cpu'
    os.environ['XLA_FLAGS']='--xla_cpu_multi_thread_eigen=false intra_op_parallelism_threads=4'
    sys.path.insert(0,str(ASSETS/'dreamerv3'))
    import jax
    import jax.numpy as jnp
    import ninjax as nj
    import numpy as np
    from spatial_world_model.r4_dreamer_adapter import DreamerTask,tensorize
    from spatial_world_model.r4_model_prediction import pack,aggregate
    history,controls,goal=tensorize(query);model=DreamerTask(name='dreamer_task')
    initial=nj.pure(model.predict)
    params,_=jax.jit(lambda h,a,g:initial({},h,a,g,seed=7921,create=True))(history,controls,goal)
    observe=nj.pure(model.observe);imagine=nj.pure(model.imagine)
    condition=jax.jit(lambda p,h,r:observe(p,h,seed=r))
    rollout=jax.jit(lambda p,s,a,g,r:imagine(p,s,a,g,seed=r))
    def digest(tree):
        sha=hashlib.sha256()
        for leaf in jax.tree.leaves(tree):sha.update(np.asarray(leaf).tobytes())
        return sha.hexdigest()
    original_params=digest(params);samples=[[] for _ in actions];states=[]
    # Each stochastic draw conditions once. All nine controls share that draw's
    # posterior and future RNG key; neither seed depends on world/action IDs.
    for sample in range(16):
        _,(state,observed)=condition(params,history,jax.random.PRNGKey(8000+sample))
        state_hash=digest(state);states.append(state_hash)
        for index,action in enumerate(actions):
            _,(_,native,task)=rollout(params,state,jnp.asarray(action,dtype=jnp.float32)[None],goal,jax.random.PRNGKey(8100+sample))
            samples[index].append(pack(np.asarray(task['object_position_m'][0]).tolist(),
                 np.asarray(task['contact_logit'][0]).tolist(),float(task['success_logit'][0])))
        assert digest(state)==state_hash
        print('D PUBLIC stochastic draw',sample+1,'/16 COMPLETE',flush=True)
    assert digest(params)==original_params
    for name,draws in zip(names,samples):write(dest/(name+'.json'),{'samples':draws,'prediction':aggregate(draws)})
    return {'stochastic_draws':16,'decision_state_sha256':states,'parameter_sha256':original_params,
            'parameter_count':sum(p.size for p in params.values()),'backend':'jax_cpu','max_cuda_allocated_bytes':0}


def torch_model(kind,query,actions,dest,names):
    import torch
    from spatial_world_model.r4_torch_task import tensorize
    from spatial_world_model.r4_model_prediction import pack,aggregate
    torch.set_num_threads(4);torch.manual_seed(7921);torch.cuda.manual_seed_all(7921)
    if kind=='F':
        from r4_flowm_adapter_check_v1 import bind_author
        bind_author()
        from spatial_world_model.r4_flowm_adapter import FloWMTask
        model=FloWMTask().cuda().eval()
    else:
        sys.path[:0]=[str(ASSETS/'dino_wm'),str(ASSETS/'dinov2')]
        from r4_dinowm_assets_v1 import WEIGHT
        from spatial_world_model.r4_dinowm_adapter import DinoWMTask
        model=DinoWMTask(WEIGHT).cuda().eval()
    history,_,goal=tensorize(query)
    def digest(value):
        sha=hashlib.sha256()
        def visit(item):
            if isinstance(item,torch.Tensor):sha.update(item.detach().cpu().numpy().tobytes())
            elif isinstance(item,dict):
                for key in sorted(item):visit(item[key])
            elif isinstance(item,(list,tuple)):
                for part in item:visit(part)
        visit(value);return sha.hexdigest()
    original=digest(model.state_dict())
    with torch.no_grad():
        state=model.observe(history);state_hash=digest(state)
        for name,action in zip(names,actions):
            output=model.imagine(state,torch.tensor(action,device='cuda',dtype=torch.float32)[None],goal)
            task=output['task']
            prediction=pack(task['object_position_m'][0].cpu().tolist(),task['contact_logit'][0].cpu().tolist(),float(task['success_logit'][0]))
            write(dest/(name+'.json'),{'samples':[prediction],'prediction':aggregate([prediction])})
            assert digest(state)==state_hash
            print(kind,'PUBLIC',name,'COMPLETE',flush=True)
    assert digest(model.state_dict())==original
    torch.cuda.synchronize()
    return {'stochastic_draws':1,'decision_state_sha256':[state_hash],'parameter_sha256':original,
            'parameter_count':sum(p.numel() for p in model.parameters()),'backend':'torch_cuda',
            'max_cuda_allocated_bytes':torch.cuda.max_memory_allocated()}


def main():
    assert sys.platform.startswith('linux')
    parser=argparse.ArgumentParser();parser.add_argument('step',choices=['D','F','W','export']);kind=parser.parse_args().step
    if kind=='export':
        artifacts={p.relative_to(RUN).as_posix():{**record(p),'text':p.read_text()} for p in RUN.glob('*/*.json')}
        completed=[k for k in NAMES if (RUN/k/'receipt.json').exists()]
        write(ROOT/'results/spatial_history_r4_three_model_public_v1.json',
           {'stage':'SH-04-R4-three-model-public-v1','completed_models':completed,'artifacts':artifacts,
            'engineering_ready':completed==list(NAMES),'trained_model_ready':False,'exporter':record(Path(__file__))})
        print('THREE MODEL PUBLIC EXPORTED exit=0');return
    assert datetime.datetime.now(datetime.timezone.utc)<DEADLINE
    sys.path.insert(0,str(ROOT/'src'));previous=prior(kind)
    dest=RUN/kind;dest.mkdir(parents=True,exist_ok=False)
    binding={f:record(ROOT/f) for f in FILES}
    write(dest/'started.json',{'binding':binding,'adapter_receipt':previous,'model':kind,
       'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
       'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()})
    began=time.monotonic()
    def timeout(*_):raise TimeoutError('public model check 1800-second limit')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(1800)
    try:
        check_packing();query,actions,source,names=inputs()
        result=dreamer(query,actions,dest,names) if kind=='D' else torch_model(kind,query,actions,dest,names)
        assert record(Path(source['path']))=={'bytes':source['bytes'],'sha256':source['sha256']}
        assert binding=={f:record(ROOT/f) for f in FILES}
        assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024<=12*2**30
        assert result['max_cuda_allocated_bytes']<=28*2**30
        write(dest/'receipt.json',{'exit_code':0,'result':result,'source':source,'history_frames':121,
            'candidate_count':9,'future_steps':200,'new_training_steps':0,'truth_files_read':0,
            'trained_model_ready':False,'elapsed_s':time.monotonic()-began,
            'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            'files':{p.name:record(p) for p in dest.glob('*.json')}})
        print(kind,'PUBLIC COMPLETE nine_candidates=9 exit=0',flush=True)
    except BaseException as error:
        write(dest/'failure.json',{'exit_code':1,'error':repr(error),'elapsed_s':time.monotonic()-began});raise


if __name__=='__main__':main()
