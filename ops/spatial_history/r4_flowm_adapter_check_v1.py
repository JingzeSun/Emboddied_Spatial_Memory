"""D-095 FloWM continuous-camera/task checks; synthetic only, no optimizer."""
import argparse
import datetime
import hashlib
import importlib
import json
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
import types
from r4_model_assets_v1 import ASSETS,DEADLINE,ROOT,record,write
from r4_native_models_v1 import no_dataset,validate_sources

RUN=ASSETS/'flowm-adapter-check-v1'
FILES=['src/spatial_world_model/r4_model_inputs.py','src/spatial_world_model/r4_torch_task.py',
       'src/spatial_world_model/r4_flowm_adapter.py','src/spatial_world_model/__init__.py',
       'src/spatial_world_model/r4_query_v2.py','src/spatial_world_model/pair_contract.py',
       'src/spatial_world_model/two_gate_contract.py','tests/spatial_world_model/r4_examples_v2.py',
       'ops/spatial_history/r4_flowm_adapter_check_v1.py',
       'ops/spatial_history/r4_model_assets_v1.py','ops/spatial_history/r4_native_models_v1.py',
       'docs/METHOD.md','docs/DATA.md','docs/DECISIONS.md']


def bind_author():
    root=ASSETS/'flowm'
    for name in ['algorithms','algorithms.mem_wm','algorithms.mem_wm.backbones',
                 'algorithms.mem_wm.backbones.embeddings','algorithms.mem_wm.backbones.flowm']:
        module=types.ModuleType(name);module.__path__=[str(root.joinpath(*name.split('.')))];sys.modules[name]=module


def check():
    bind_author();sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests/spatial_world_model')]
    import torch
    from r4_examples_v2 import public
    from spatial_world_model.r4_query_v2 import from_public_query
    from spatial_world_model.r4_torch_task import tensorize
    from spatial_world_model.r4_flowm_adapter import FloWMTask,align_map,shift_velocity,surface_mask
    torch.set_num_threads(4);torch.manual_seed(7915);torch.cuda.manual_seed_all(7915)
    model=FloWMTask().cuda().eval()
    history,controls,goal=tensorize(from_public_query(public(range(121))))
    assert history['rgb'].shape==(1,121,3,80,80)
    with torch.no_grad():
        base=torch.randn((1,5,49,49,256),device='cuda')
        zero=torch.zeros((1,2),device='cuda')
        assert torch.equal(align_map(base,zero),base)
        translated=align_map(base,torch.tensor([[.15,0]],device='cuda'))
        native=model.memory.roll_map(base,torch.tensor([2],device='cuda'))
        torch.testing.assert_close(translated[:,:,:,:-1],native[:,:,:,:-1],atol=2e-5,rtol=2e-5)
        assert translated[:,:,:,-1].abs().max()<2e-5
        impulse=torch.zeros((1,1,49,49,1),device='cuda');impulse[:,:,24,24]=1
        half=align_map(impulse,torch.tensor([[.075,0]],device='cuda'))
        torch.testing.assert_close(half[0,0,24,23:25,0],torch.tensor([.5,.5],device='cuda'),atol=2e-5,rtol=0)
        velocities=shift_velocity(base);native_v=model.memory.shift_v_channels(base)
        torch.testing.assert_close(velocities[:,:,1:-1,1:-1],native_v[:,:,1:-1,1:-1],atol=0,rtol=0)
        assert torch.count_nonzero(velocities[:,1,:,0])==0 and torch.count_nonzero(velocities[:,3,:,-1])==0
        depth=history['depth_m'][:,0];valid=history['depth_valid'][:,0];meta=history['metadata'][:,0]
        mask=surface_mask(depth,valid,meta);assert mask.any()
        empty=surface_mask(depth,torch.zeros_like(valid),meta);assert not empty.any()
        frame=model.frame(history['rgb'][:,0],depth,valid)
        updated=model.memory(base,frame,mask,model.control(torch.cat((meta,controls[:,0]),-1))[:,None])
        assert torch.equal(updated[:,:,~mask],base[:,:,~mask])
        assert not torch.equal(updated[:,:,mask],base[:,:,mask])
        blank=frame.clone();blank[:,3:]=0
        empty_result=model.future_step(base,blank,meta,controls[:,0])
        assert all(torch.isfinite(x).all() for x in empty_result)
        del base,translated,native,velocities,native_v,updated,empty_result
        state=model.observe(history)
        assert state['map'].shape==(1,5,49,49,256) and state['history_frames']==121
        first={k:v[:,:57] for k,v in history.items()};second={k:v[:,57:] for k,v in history.items()}
        split=model.observe(second,model.observe(first))
        assert torch.equal(state['map'],split['map']) and torch.equal(state['observed_support'],split['observed_support'])
        before=state['map'].clone();support=state['observed_support'].clone()
        left=model.imagine(state,controls,goal)
        changed=controls.clone();changed[:,100,0]=.5
        right=model.imagine(state,changed,goal)
        assert torch.equal(state['map'],before) and torch.equal(state['observed_support'],support)
        assert torch.equal(left['future_features'][:,:100],right['future_features'][:,:100])
        assert not torch.equal(left['future_features'][:,100],right['future_features'][:,100])
        assert torch.equal(left['observed_support'],support)
        assert left['task']['object_position_m'].shape==(1,200,3)
        assert left['task']['contact_logit'].shape==(1,200) and left['task']['success_logit'].shape==(1,)
        assert set(left['snapshots'])=={0,50,100,150,200}
        assert torch.isfinite(left['predicted_rgbd']).all() and all(torch.isfinite(x).all() for x in left['task'].values())
        task_hash=hashlib.sha256(left['task']['object_position_m'].cpu().numpy().tobytes()).hexdigest()
    del state,split,before,support,left,right,first,second
    print('F ADAPTER alignment, support, full121/200 and causal task forward passed',flush=True)
    labels={'position_m':torch.zeros((1,200,3),device='cuda'),
            'contact':torch.zeros((1,200),device='cuda',dtype=torch.bool),
            'success':torch.ones((1,),device='cuda',dtype=torch.bool)}
    images={key:history[key][:,-1:].expand(-1,200,-1,-1,-1) for key in ('rgb','depth_m','depth_valid')}
    model.train();torch.manual_seed(7917);torch.cuda.manual_seed_all(7917)
    total,terms=model.loss(history,controls,goal,labels,images)
    total.backward();torch.cuda.synchronize()
    assert torch.isfinite(total)
    assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
    norms={}
    for group in ('memory.patch.rgb','memory.patch.depth','memory.blocks','memory.update_gate','control','decoder','pool','task'):
        grads=[p.grad for n,p in model.named_parameters() if n.startswith(group+'.')]
        assert grads,group
        norm=sum(float(g.square().sum()) for g in grads)**.5;assert norm>0,group;norms[group]=norm
    return {'checks':['all_121_native_80px_frames','zero_camera_identity','native_integer_translation_overlap',
       'translation_no_wrap','fractional_translation','native_velocity_overlap','velocity_no_wrap',
       'public_depth_surface_mask','invalid_depth_no_observed_cells','unseen_memory_retained',
       'empty_view_finite_prior','121_frame_map_and_chunk_equivalence','branch_immutable',
       'later_control_no_earlier_effect','zero_camera_independent_action_effect','imagined_pixels_not_observed_support',
       '200_task_outputs_and_five_snapshots','finite_full_200_step_backward','eight_gradient_paths'],
       'history_frames':121,'future_steps':200,'map_shape':[1,5,49,49,256],
       'parameter_count':sum(p.numel() for p in model.parameters()),
       'parameter_shapes':{n:list(p.shape) for n,p in model.named_parameters()},'gradient_l2':norms,
       'synthetic_total_loss':float(total.detach()),'synthetic_loss_terms':{k:float(v.detach()) for k,v in terms.items()},
       'max_cuda_allocated_bytes':torch.cuda.max_memory_allocated(),'initial_task_sha256':task_hash,
       'new_training_steps':0,'optimizer_constructed':False,'real_data_predictions':0,'trained_model_ready':False}


def main():
    assert sys.platform.startswith('linux')
    parser=argparse.ArgumentParser();parser.add_argument('step',choices=['run','export']);step=parser.parse_args().step
    if step=='export':
        artifacts={p.name:{**record(p),'text':p.read_text()} for p in RUN.glob('*.json')}
        write(ROOT/'results/spatial_history_r4_flowm_adapter_v1.json',
            {'stage':'SH-04-R4-flowm-adapter-v1','artifacts':artifacts,'exporter':record(Path(__file__))})
        print('F ADAPTER EXPORTED exit=0');return
    assert datetime.datetime.now(datetime.timezone.utc)<DEADLINE
    source=validate_sources()
    assert json.loads((ASSETS/'native-audit-v1/flowm/receipt.json').read_text())['exit_code']==0
    RUN.mkdir(exist_ok=False);binding={f:record(ROOT/f) for f in FILES}
    write(RUN/'started.json',{'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
       'binding':binding,'author_source_receipt':source,
       'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()})
    began=time.monotonic()
    def timeout(*_):raise TimeoutError('FloWM adapter 1800-second limit')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(1800);sys.addaudithook(no_dataset)
    try:
        result=check();assert binding=={f:record(ROOT/f) for f in FILES}
        assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024<=12*2**30,'RSS budget exceeded'
        assert result['max_cuda_allocated_bytes']<=28*2**30,'CUDA allocation budget exceeded'
        write(RUN/'receipt.json',{'exit_code':0,'result':result,'elapsed_s':time.monotonic()-began,
            'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'started':record(RUN/'started.json')})
        print('F ADAPTER COMPLETE checks='+str(len(result['checks']))+' exit=0',flush=True)
    except BaseException as error:
        write(RUN/'failure.json',{'exit_code':1,'error':repr(error),'elapsed_s':time.monotonic()-began});raise


if __name__=='__main__':main()
