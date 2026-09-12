"""D-094 full-history DINO-WM adapter; author weights/modules, causal KV execution.

The caller binds pinned dino_wm and dinov2 repositories. Model inference accepts
only public tensors; targets enter the separate loss method after the rollout.
"""
import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.checkpoint import checkpoint
from models.vit import ViTPredictor
from models.proprio import ProprioceptiveEmbedding
from dinov2.hub.backbones import dinov2_vits14
from .r4_torch_task import SpatialPool,TaskHeads,task_loss


class CausalCache(nn.Module):
    """Original frame-causal attention with full, differentiable past K/V."""
    def __init__(self):
        super().__init__()
        self.native=ViTPredictor(num_patches=36,num_frames=3,dim=404,depth=6,heads=16,
                                 dim_head=64,mlp_dim=2048,dropout=0.1)
        original=self.native.pos_embedding
        full=original.new_empty((1,321*36,404)).normal_()
        full[:,:108]=original.detach()
        self.native.pos_embedding=nn.Parameter(full)

    def empty(self):return tuple(((),()) for _ in self.native.transformer.layers)

    @staticmethod
    def layer(x, past_k, past_v, attention, feedforward):
        q,k,v=[part.reshape(x.shape[0],36,attention.heads,-1).transpose(1,2)
               for part in attention.to_qkv(attention.norm(x)).chunk(3,-1)]
        keys=torch.cat((*past_k,k),-2);values=torch.cat((*past_v,v),-2)
        # All earlier frames and every patch of this frame are visible. This is
        # the author's block-causal mask, not token-autoregressive attention.
        attended=F.scaled_dot_product_attention(q,keys,values,
            dropout_p=attention.dropout.p if attention.training else 0.0,scale=attention.scale)
        x=x+attention.to_out(attended.transpose(1,2).reshape(x.shape[0],36,-1))
        return x+feedforward(x),k,v

    def step(self,x,cache,index):
        assert 0<=index<321 and len(cache[0][0])==index
        x=self.native.dropout(x+self.native.pos_embedding[:,index*36:(index+1)*36])
        updated=[]
        for (attention,feedforward),(past_k,past_v) in zip(self.native.transformer.layers,cache):
            if torch.is_grad_enabled():
                x,k,v=checkpoint(self.layer,x,past_k,past_v,attention,feedforward,
                                  use_reentrant=False,preserve_rng_state=True)
            else:x,k,v=self.layer(x,past_k,past_v,attention,feedforward)
            updated.append(((*past_k,k),(*past_v,v)))
        return self.native.transformer.norm(x),tuple(updated)


class DinoWMTask(nn.Module):
    def __init__(self,weight_path):
        super().__init__()
        self.rgb=dinov2_vits14(pretrained=False)
        self.rgb.load_state_dict(torch.load(weight_path,map_location='cpu',weights_only=True),strict=True)
        self.rgb.requires_grad_(False).eval()
        self.register_buffer('rgb_mean',torch.tensor([.485,.456,.406])[None,:,None,None])
        self.register_buffer('rgb_std',torch.tensor([.229,.224,.225])[None,:,None,None])
        self.depth=nn.Conv2d(2,384,14,stride=14)
        self.metadata=ProprioceptiveEmbedding(in_chans=37,emb_dim=10)
        self.action=ProprioceptiveEmbedding(in_chans=4,emb_dim=10)
        self.predictor=CausalCache()
        self.pool=SpatialPool(394,6,6)
        self.task=TaskHeads()
        self.depth_decoder=nn.Sequential(nn.Linear(384,256),nn.GELU(),nn.Linear(256,196))

    def train(self,mode=True):
        super().train(mode);self.rgb.eval();return self

    def image_features(self,rgb,depth,valid):
        batch,frames=rgb.shape[:2]
        flat=rgb.reshape(-1,3,80,80).float()/255
        # Replicated RGB border preserves every original pixel; depth/mask
        # padding is zero and never becomes a valid target observation.
        flat=(F.pad(flat,(0,4,0,4),mode='replicate')-self.rgb_mean)/self.rgb_std
        with torch.no_grad():
            visual=torch.cat([self.rgb.forward_features(piece)['x_norm_patchtokens']
                              for piece in flat.split(8)],0)
        depth_input=torch.cat((torch.where(valid,depth,0),valid.float()),2).reshape(-1,2,80,80)
        encoded=self.depth(F.pad(depth_input,(0,4,0,4))).flatten(2).transpose(1,2)
        return (visual+encoded).reshape(batch,frames,36,384)

    def encode(self,history):
        visual=self.image_features(history['rgb'],history['depth_m'],history['depth_valid'])
        meta=self.metadata(history['metadata'])[:,:,None].expand(-1,-1,36,-1)
        return torch.cat((visual,meta),-1)

    def join_action(self,observation,action):
        embedded=self.action(action[:,None])[:,0,None].expand(-1,36,-1)
        return torch.cat((observation,embedded),-1)

    def observe(self,history):
        encoded=self.encode(history);count=encoded.shape[1]
        cache=self.predictor.empty()
        for i in range(count-1):
            # Command attached to obs_i drives i -> i+1; public previous_action
            # of the NEXT observation is precisely that historical command.
            _,cache=self.predictor.step(self.join_action(encoded[:,i],history['previous_action'][:,i+1]),cache,i)
        last=encoded[:,-1]
        neutral=torch.zeros_like(history['previous_action'][:,-1])
        decision,_=self.predictor.step(self.join_action(last,neutral),cache,count-1)
        return {'prefix_cache':cache,'last_observation':last,'index':count-1,
                'decision':decision,'encoded_history':encoded}

    def imagine(self,state,controls,goal):
        assert controls.shape[1:]==(200,4)
        cache=state['prefix_cache']; observation=state['last_observation']
        predictions=[]; pooled=[]
        for step in range(200):
            predicted,cache=self.predictor.step(self.join_action(observation,controls[:,step]),cache,state['index']+step)
            observation=predicted[...,:394]
            predictions.append(observation);pooled.append(self.pool(observation))
        future=torch.stack(predictions,1)
        return {'future':future,'task':self.task(torch.stack(pooled,1),goal),
                'last_cache_frames':len(cache[0][0])}

    def predict(self,history,controls,goal):
        state=self.observe(history)
        return {'decision':state['decision'],**self.imagine(state,controls,goal)}

    def decode_depth(self,visual):
        b,t=visual.shape[:2]
        pixels=self.depth_decoder(visual).reshape(b,t,6,6,14,14)
        return pixels.permute(0,1,2,4,3,5).reshape(b,t,1,84,84)[...,:80,:80]

    def loss(self,history,controls,goal,labels,future_images):
        assert set(future_images)=={'rgb','depth_m','depth_valid'}
        output=self.predict(history,controls,goal)
        losses=task_loss(output['task'],labels)
        with torch.no_grad():
            target=self.image_features(future_images['rgb'],future_images['depth_m'],future_images['depth_valid'])
        visual=output['future'][...,:384]
        losses['visual_feature_mse']=(visual-target).square().mean()
        depth=self.decode_depth(visual); valid=future_images['depth_valid']
        losses['valid_depth_mse']=torch.where(valid,(depth-future_images['depth_m'].detach()).square(),0).sum()/valid.sum().clamp_min(1)
        return sum(losses.values()),losses
