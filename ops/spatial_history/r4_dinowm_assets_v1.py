"""D-092: pinned DINOv2 download and original DINO-WM native interface audit."""
import argparse
import datetime
import hashlib
import importlib
import json
from pathlib import Path
import resource
import signal
import sys
import time
import urllib.request

from r4_model_assets_v1 import ASSETS, DEADLINE, ROOT, record, write
from r4_native_models_v1 import no_dataset

RUN = ASSETS/'dinowm-native-v1'
VERSIONS = {'dino_wm':'0a9492fa12044b852ae9e001cc74604b79c8bb0c',
            'dinov2':'7764ea0f912e53c92e82eb78a2a1631e92725fc8'}
URL = 'https://dl.fbaipublicfiles.com/dinov2/dinov2_vits14/dinov2_vits14_pretrain.pth'
WEIGHT = RUN/'download/dinov2_vits14_pretrain.pth'


def sources():
    import subprocess
    result = {}
    for name, commit in VERSIONS.items():
        root = ASSETS/name
        assert subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip() == commit
        subprocess.run(['git','-C',str(root),'diff','--quiet','HEAD'],check=True)
        files = subprocess.check_output(['git','-C',str(root),'ls-files','-z']).decode().split('\0')
        result[name] = {'commit':commit,'files':{f:record(root/f) for f in files if f and (root/f).is_file()}}
    return result


def download():
    total = 0
    with urllib.request.urlopen(URL,timeout=60) as response, WEIGHT.open('xb') as output:
        size = int(response.headers.get('Content-Length','0'))
        if not 0 < size <= 128*2**20: raise ValueError('unexpected asset size')
        while chunk := response.read(2**20):
            total += len(chunk)
            if total > 128*2**20: raise ValueError('asset limit exceeded')
            output.write(chunk)
        assert total == size
    return {'url':URL,'weight':record(WEIGHT),'downloaded_bytes':total}


def native():
    download_receipt = json.loads((RUN/'download/receipt.json').read_text())
    assert download_receipt['result']['weight'] == record(WEIGHT)
    import torch
    import torch.nn as nn
    torch.set_num_threads(4); torch.manual_seed(7901); torch.cuda.manual_seed_all(7901)
    sys.path[:0] = [str(ASSETS/'dino_wm'),str(ASSETS/'dinov2')]
    from dinov2.hub.backbones import dinov2_vits14
    from models.proprio import ProprioceptiveEmbedding
    from models.vit import ViTPredictor
    from models.visual_world_model import VWorldModel
    # Constructor resolves the already audited local official asset. Forward is
    # the same frozen DINOv2 patch-feature operation as models/dino.py.
    class LocalDino(nn.Module):
        def __init__(self):
            super().__init__()
            self.name='dinov2_vits14'; self.base_model=dinov2_vits14(pretrained=False)
            state=torch.load(WEIGHT,map_location='cpu',weights_only=True)
            status=self.base_model.load_state_dict(state,strict=True)
            assert not status.missing_keys and not status.unexpected_keys
            self.base_model.requires_grad_(False).eval()
            self.emb_dim=384; self.patch_size=14; self.latent_ndim=2
        def forward(self,x):
            return self.base_model.forward_features(x)['x_norm_patchtokens']
    encoder = LocalDino()
    model = VWorldModel(image_size=224,num_hist=3,num_pred=1,encoder=encoder,
        proprio_encoder=ProprioceptiveEmbedding(in_chans=4,emb_dim=10),
        action_encoder=ProprioceptiveEmbedding(in_chans=4,emb_dim=10),decoder=None,
        predictor=ViTPredictor(num_patches=196,num_frames=3,dim=404,depth=6,heads=16,
                               mlp_dim=2048,dropout=0.1),
        proprio_dim=10,action_dim=10,concat_dim=1,num_action_repeat=1,num_proprio_repeat=1,
        train_encoder=False,train_predictor=True,train_decoder=False).cuda()
    model.eval()
    obs={'visual':torch.linspace(0,1,3*3*224*224,device='cuda').reshape(1,3,3,224,224),
         'proprio':torch.zeros((1,3,4),device='cuda')}
    actions=torch.zeros((1,3,4),device='cuda')
    with torch.no_grad():
        z=model.encode(obs,actions)
        pred=model.predict(z)
        assert z.shape==(1,3,196,404) and pred.shape==z.shape
        assert torch.isfinite(pred).all()
        modified=actions.clone(); modified[:,-1,0]=0.5
        changed=model.predict(model.encode(obs,modified))
        assert torch.allclose(pred[:,:2],changed[:,:2],atol=1e-6,rtol=1e-6)
        assert not torch.equal(pred[:,-1],changed[:,-1])
        frozen=z.clone();model.replace_actions_from_z(frozen,modified)
        assert torch.equal(frozen[...,:-10],z[...,:-10])
        assert not torch.equal(frozen[...,-10:],z[...,-10:])
    torch.cuda.synchronize()
    return {'checks':['strict_official_dinov2_load','native_patch_encoding','native_causal_prediction',
        'finite_output','future_action_does_not_change_earlier_prediction','action_changes_next_prediction',
        'action_replacement_preserves_observation_channels'],
        'native_feature_shape':list(z.shape),'encoder_input_hw':[196,196],
        'parameter_count':sum(p.numel() for p in model.parameters()),
        'frozen_encoder_parameters':sum(p.numel() for p in encoder.parameters()),
        'weight':record(WEIGHT),'max_cuda_allocated_bytes':torch.cuda.max_memory_allocated(),
        'loader_adaptation':'local strict asset constructor; original frozen DINOv2 patch forward',
        'world_model_checkpoint':'random_initialization_no_author_task_checkpoint',
        'task_adapter_ready':False,'training_steps':0}


def main():
    assert sys.platform.startswith('linux'), 'server only'
    parser=argparse.ArgumentParser();parser.add_argument('step',choices=['download','native','export'])
    step=parser.parse_args().step
    if step=='export':
        files={p.relative_to(RUN).as_posix():{**record(p),'text':p.read_text()}
               for p in RUN.glob('*/*.json')}
        write(ROOT/'results/spatial_history_r4_dinowm_native_v1.json',
            {'stage':'SH-04-R4-dinowm-native-v1','artifacts':files,'adapted_models_ready':[],
             'exporter':record(Path(__file__))})
        print('DINO-WM EXPORTED exit=0');return
    assert datetime.datetime.now(datetime.timezone.utc)<DEADLINE
    source=sources();dest=RUN/step;dest.mkdir(parents=True,exist_ok=False)
    write(dest/'started.json',{'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'sources':source,'script':record(Path(__file__)),'step':step})
    began=time.monotonic()
    def timeout(*_):raise TimeoutError('DINO-WM native stage limit')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(1200)
    sys.addaudithook(no_dataset)
    try:
        result=globals()[step]()
        write(dest/'receipt.json',{'step':step,'result':result,'exit_code':0,'elapsed_s':time.monotonic()-began,
              'started':record(dest/'started.json'),'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024})
        print(json.dumps(result,sort_keys=True));print('DINO-WM',step,'COMPLETE exit=0',flush=True)
    except BaseException as e:
        write(dest/'failure.json',{'step':step,'error':repr(e),'exit_code':1,'elapsed_s':time.monotonic()-began})
        raise


if __name__=='__main__':main()
