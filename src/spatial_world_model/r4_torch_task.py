"""D-094 shared Torch public tensors and equally sized task heads for F/W."""
import torch
from torch import nn
from .r4_model_inputs import prepare


def tensorize(query, device='cuda', **mode):
    value=prepare(query,**mode); raw=value['history']; length=len(raw['rgb'])
    history={key:torch.tensor(val,device=device,dtype=(torch.bool if key in ('depth_valid','reset')
             else torch.uint8 if key=='rgb' else torch.float32))[None] for key,val in raw.items()}
    history['rgb']=history['rgb'].reshape(1,length,80,80,3).permute(0,1,4,2,3)
    for key in ('depth_m','depth_valid'):history[key]=history[key].reshape(1,length,1,80,80)
    return history,torch.tensor(value['controls'],device=device)[None],torch.tensor(value['goal'],device=device)[None]


class SpatialPool(nn.Module):
    """Position-aware learned pooling, without labels or private coordinates."""
    def __init__(self, input_dim, rows, columns):
        super().__init__()
        self.project=nn.Linear(input_dim+2,256)
        self.score=nn.Linear(256,1)
        yy,xx=torch.meshgrid(torch.linspace(-1,1,rows),torch.linspace(-1,1,columns),indexing='ij')
        self.register_buffer('positions',torch.stack((xx,yy),-1).reshape(1,rows*columns,2))

    def forward(self,tokens):
        positions=self.positions.expand(*tokens.shape[:-2],-1,-1)
        values=torch.nn.functional.gelu(self.project(torch.cat((tokens,positions),-1)))
        weights=self.score(values).softmax(-2)
        return (values*weights).sum(-2)


class TaskHeads(nn.Module):
    def __init__(self,input_dim=256):
        super().__init__()
        self.local=nn.Sequential(nn.Linear(input_dim,256),nn.GELU(),nn.Linear(256,256),nn.GELU(),nn.Linear(256,4))
        self.gru=nn.GRU(input_dim,256,batch_first=True)
        self.success=nn.Sequential(nn.Linear(268,256),nn.GELU(),nn.Linear(256,1))

    def forward(self,features,goal):
        local=self.local(features);_,hidden=self.gru(features)
        return {'object_position_m':local[...,:3],'contact_logit':local[...,3],
                'success_logit':self.success(torch.cat((hidden[-1],goal),-1))[...,0],
                'success_state':hidden[-1]}


def task_loss(task,labels):
    assert set(labels)=={'position_m','contact','success'}
    return {'position':((task['object_position_m']-labels['position_m'].detach())/0.1).square().mean(),
            'contact':nn.functional.binary_cross_entropy_with_logits(task['contact_logit'],labels['contact'].float().detach()),
            'success':nn.functional.binary_cross_entropy_with_logits(task['success_logit'],labels['success'].float().detach())}
