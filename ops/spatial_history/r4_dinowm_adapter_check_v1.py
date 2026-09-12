"""D-094 full-history DINO-WM engineering checks, with zero optimizer updates."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
from r4_model_assets_v1 import ASSETS,DEADLINE,ROOT,record,write
from r4_native_models_v1 import no_dataset
from r4_dinowm_assets_v1 import sources,WEIGHT

RUN=ASSETS/'dinowm-adapter-check-v1'
FILES=['src/spatial_world_model/r4_model_inputs.py','src/spatial_world_model/r4_torch_task.py',
       'src/spatial_world_model/r4_dinowm_adapter.py','src/spatial_world_model/__init__.py',
       'src/spatial_world_model/r4_query_v2.py','src/spatial_world_model/pair_contract.py',
       'src/spatial_world_model/two_gate_contract.py','tests/spatial_world_model/r4_examples_v2.py',
       'ops/spatial_history/r4_dinowm_adapter_check_v1.py','ops/spatial_history/r4_dinowm_assets_v1.py',
       'ops/spatial_history/r4_model_assets_v1.py','ops/spatial_history/r4_native_models_v1.py',
       'docs/METHOD.md','docs/DATA.md','docs/DECISIONS.md']


def check():
    sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests/spatial_world_model'),str(ASSETS/'dino_wm'),str(ASSETS/'dinov2')]
    import torch
    from r4_examples_v2 import public
    from spatial_world_model.r4_query_v2 import from_public_query
    from spatial_world_model.r4_torch_task import tensorize
    from spatial_world_model.r4_dinowm_adapter import DinoWMTask
    torch.set_num_threads(4);torch.manual_seed(7911);torch.cuda.manual_seed_all(7911)
    model=DinoWMTask(WEIGHT).cuda().eval()
    # Exact same parameters and first three positional embeddings, original
    # dense frame-causal attention versus the differentiable cache execution.
    tokens=torch.randn((1,3,36,404),device='cuda',requires_grad=True)
    dense=model.predictor.native(tokens.reshape(1,108,404))
    cache=model.predictor.empty();pieces=[]
    for i in range(3):
        result,cache=model.predictor.step(tokens[:,i],cache,i);pieces.append(result)
    cached=torch.stack(pieces,1).reshape(1,108,404)
    torch.testing.assert_close(cached,dense,atol=5e-5,rtol=5e-5)
    probe=torch.randn_like(dense)
    grad_dense=torch.autograd.grad((dense*probe).sum(),tokens)[0]
    grad_cache=torch.autograd.grad((cached*probe).sum(),tokens)[0]
    torch.testing.assert_close(grad_cache,grad_dense,atol=1e-4,rtol=1e-4)
    parity={'output_max_abs':float((cached-dense).abs().max().detach()),
            'input_gradient_max_abs':float((grad_cache-grad_dense).abs().max())}
    del tokens,dense,cached,cache,pieces,grad_dense,grad_cache,result,probe
    query=from_public_query(public(range(121)))
    history,controls,goal=tensorize(query)
    assert history['rgb'].shape==(1,121,3,80,80) and history['depth_m'].dtype==torch.float32
    assert not history['depth_valid'][0,0,0,-1,-1]
    with torch.no_grad():
        state=model.observe(history)
        assert state['encoded_history'].shape==(1,121,36,394)
        assert len(state['prefix_cache'][0][0])==120
        original_last=state['last_observation'].clone()
        original_first_key=state['prefix_cache'][0][0][0].clone()
        left=model.imagine(state,controls,goal)
        changed=controls.clone();changed[:,100,0]=0.5
        right=model.imagine(state,changed,goal)
        assert torch.equal(state['last_observation'],original_last)
        assert torch.equal(state['prefix_cache'][0][0][0],original_first_key)
        torch.testing.assert_close(left['future'][:,:100],right['future'][:,:100],atol=0,rtol=0)
        assert not torch.equal(left['future'][:,100],right['future'][:,100])
        assert left['future'].shape==(1,200,36,394) and left['last_cache_frames']==320
        assert left['task']['object_position_m'].shape==(1,200,3)
        assert left['task']['contact_logit'].shape==(1,200) and left['task']['success_logit'].shape==(1,)
        assert torch.isfinite(left['future']).all() and all(torch.isfinite(x).all() for x in left['task'].values())
        # An early observation affects a late prediction despite identical
        # recent frames; this is a dependency check, never task accuracy.
        earlier={k:v.clone() for k,v in history.items()};earlier['rgb'][:,0]=255
        early_state=model.observe(earlier)
        assert not torch.equal(state['decision'],early_state['decision'])
        task_hash=hashlib.sha256(left['task']['object_position_m'].cpu().numpy().tobytes()).hexdigest()
    del state,left,right,early_state,earlier,original_last,original_first_key
    print('W ADAPTER native value/gradient parity and full121/200 causal forward passed',flush=True)
    labels={'position_m':torch.zeros((1,200,3),device='cuda'),
            'contact':torch.zeros((1,200),device='cuda',dtype=torch.bool),
            'success':torch.ones((1,),device='cuda',dtype=torch.bool)}
    images={key:history[key][:,-1:].expand(-1,200,-1,-1,-1) for key in ('rgb','depth_m','depth_valid')}
    model.train();torch.manual_seed(7913);torch.cuda.manual_seed_all(7913)
    total,terms=model.loss(history,controls,goal,labels,images)
    total.backward();torch.cuda.synchronize()
    assert torch.isfinite(total)
    norms={}
    for group in ('depth','metadata','action','predictor','pool','task','depth_decoder'):
        grads=[p.grad for n,p in model.named_parameters() if n.startswith(group+'.') and p.requires_grad]
        assert grads and all(g is not None and torch.isfinite(g).all() for g in grads),group
        norm=sum(float(g.square().sum()) for g in grads)**0.5
        assert norm>0,group
        norms[group]=norm
    assert all(not p.requires_grad and p.grad is None for p in model.rgb.parameters())
    checks=['strict_official_weight','native_causal_value_parity','native_causal_gradient_parity',
        'all_121_native_80px_frames','metric_depth_and_mask','36_padded_patches',
        '120_frame_prefix_cache','branch_state_immutable','later_control_no_earlier_effect',
        'action_alignment','200_step_future_and_task_heads','320_frame_cache_no_truncation',
        'finite_forward','early_history_dependency','finite_full_200_step_backward',
        'seven_gradient_paths','dinov2_frozen']
    return {'checks':checks,'native_parity':parity,'gradient_l2':norms,
        'synthetic_total_loss':float(total.detach()),'synthetic_loss_terms':{k:float(v.detach()) for k,v in terms.items()},
        'history_frames':121,'future_steps':200,'patches_per_frame':36,'maximum_cache_frames':320,
        'parameter_count':sum(p.numel() for p in model.parameters()),
        'frozen_parameters':sum(p.numel() for p in model.parameters() if not p.requires_grad),
        'parameter_shapes':{n:list(p.shape) for n,p in model.named_parameters()},
        'max_cuda_allocated_bytes':torch.cuda.max_memory_allocated(),
        'initial_task_sha256':task_hash,'new_training_steps':0,'optimizer_constructed':False,
        'real_data_predictions':0,'trained_model_ready':False}


def main():
    assert sys.platform.startswith('linux')
    parser=argparse.ArgumentParser();parser.add_argument('step',choices=['run','export']);step=parser.parse_args().step
    if step=='export':
        artifacts={p.name:{**record(p),'text':p.read_text()} for p in RUN.glob('*.json')}
        write(ROOT/'results/spatial_history_r4_dinowm_adapter_v1.json',
            {'stage':'SH-04-R4-dinowm-adapter-v1','artifacts':artifacts,'exporter':record(Path(__file__))})
        print('W ADAPTER EXPORTED exit=0');return
    assert datetime.datetime.now(datetime.timezone.utc)<DEADLINE
    source=sources()
    native=json.loads((ASSETS/'dinowm-native-v1/native/receipt.json').read_text())
    assert native['exit_code']==0 and native['result']['weight']==record(WEIGHT)
    RUN.mkdir(exist_ok=False);binding={f:record(ROOT/f) for f in FILES}
    write(RUN/'started.json',{'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'binding':binding,'sources':source,'weight':record(WEIGHT),
        'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()})
    began=time.monotonic()
    def timeout(*_):raise TimeoutError('DINO-WM adapter 1800-second limit')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(1800);sys.addaudithook(no_dataset)
    try:
        result=check()
        assert binding=={f:record(ROOT/f) for f in FILES}
        assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024<=12*2**30,'RSS budget exceeded'
        assert result['max_cuda_allocated_bytes']<=28*2**30,'CUDA allocation budget exceeded'
        write(RUN/'receipt.json',{'exit_code':0,'result':result,'elapsed_s':time.monotonic()-began,
            'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'started':record(RUN/'started.json')})
        print('W ADAPTER COMPLETE checks='+str(len(result['checks']))+' exit=0',flush=True)
    except BaseException as error:
        write(RUN/'failure.json',{'exit_code':1,'error':repr(error),'elapsed_s':time.monotonic()-began});raise


if __name__=='__main__':main()
