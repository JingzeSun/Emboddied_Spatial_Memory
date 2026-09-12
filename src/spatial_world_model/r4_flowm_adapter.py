"""D-095 continuous-camera FloWM RGBD adapter around unchanged author modules.

The caller loads the pinned author namespaces. Only public tensor values enter
observe/imagine; future images and labels belong exclusively to loss targets.
"""
import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.checkpoint import checkpoint
from algorithms.mem_wm.backbones.flowm.flowm_models_3d import MapLatentProcessor,ViTImageDecoder
from .r4_torch_task import SpatialPool,TaskHeads,task_loss

CELL_M=0.15
SIZE=49


def align_map(memory,delta_xy):
    """New camera-relative cell queries old cell + actual camera displacement."""
    if bool((delta_xy==0).all()):return memory
    b,v,h,w,d=memory.shape
    yy,xx=torch.meshgrid(torch.arange(h,device=memory.device),torch.arange(w,device=memory.device),indexing='ij')
    grid=torch.stack((xx,yy),-1).float()[None]+delta_xy[:,None,None]/CELL_M
    grid=grid*2/(SIZE-1)-1
    flat=memory.permute(0,1,4,2,3).reshape(b,v*d,h,w)
    shifted=F.grid_sample(flat,grid,mode='bilinear',padding_mode='zeros',align_corners=True)
    return shifted.reshape(b,v,d,h,w).permute(0,1,3,4,2).contiguous()


def shift_velocity(memory):
    """Author five directions and one cell per step, explicitly zero outside."""
    out=torch.zeros_like(memory)
    for i,(vx,vy) in enumerate(((0,0),(1,0),(0,1),(-1,0),(0,-1))):
        y=slice(max(0,vy),min(SIZE,SIZE+vy)); x=slice(max(0,vx),min(SIZE,SIZE+vx))
        old_y=slice(max(0,-vy),min(SIZE,SIZE-vy));old_x=slice(max(0,-vx),min(SIZE,SIZE-vx))
        out[:,i,y,x]=memory[:,i,old_y,old_x]
    return out


def surface_mask(depth,valid,metadata):
    """Public top-down depth samples select xy columns; not free-space proof."""
    assert depth.shape==(1,1,80,80) and metadata.shape==(1,37)
    fx,fy,cx,cy=metadata[0,13:17]*80
    yy,xx=torch.meshgrid(torch.arange(80,device=depth.device),torch.arange(80,device=depth.device),indexing='ij')
    z=depth[0,0]
    gx=torch.round((xx-cx)*z/fx/CELL_M+24).long()
    gy=torch.round(-(yy-cy)*z/fy/CELL_M+24).long()
    accepted=valid[0,0] & torch.isfinite(z) & (z>0) & (z<20) & (gx>=0)&(gx<SIZE)&(gy>=0)&(gy<SIZE)
    mask=torch.zeros((SIZE,SIZE),device=depth.device,dtype=torch.bool)
    mask[gy[accepted],gx[accepted]]=True
    return mask


class RGBDPatch(nn.Module):
    def __init__(self,rgb):
        super().__init__();self.rgb=rgb;self.grid_size=rgb.grid_size
        self.depth=nn.Conv2d(2,256,8,stride=8)
    def forward(self,image):
        return self.rgb(image[:,:3])+self.depth(image[:,3:]).flatten(2).transpose(1,2)


class FloWMTask(nn.Module):
    def __init__(self):
        super().__init__()
        self.memory=MapLatentProcessor(world_size=24,embed_dim=256,num_heads=8,depth=6,
             img_size=(80,80),patch_size=8,v_range=1)
        self.memory.patch=RGBDPatch(self.memory.patch)
        self.control=nn.Sequential(nn.Linear(41,256),nn.GELU(),nn.Linear(256,256),nn.GELU())
        self.decoder=ViTImageDecoder(out_chans=4,img_size=(80,80),patch_size=8,embed_dim=256,depth=6,num_heads=8)
        self.pool=SpatialPool(5*256,SIZE,SIZE)
        self.task=TaskHeads()

    @staticmethod
    def frame(rgb,depth,valid):
        return torch.cat((rgb.float()/255-.5,torch.where(valid,depth,0),valid.float()),1)

    def initial(self,metadata):
        return {'map':self.memory.init_map(1,metadata.device),
                'observed_support':torch.zeros((1,1,SIZE,SIZE,1),device=metadata.device),
                'camera_xy':metadata[:,6:8], 'metadata':metadata,'history_frames':0}

    def history_step(self,memory,image,mask,metadata,previous_action,delta,first):
        memory=align_map(memory,delta)
        if not first:memory=shift_velocity(memory)
        token=self.control(torch.cat((metadata,previous_action),-1))[:,None]
        return self.memory(memory,image,mask,token)

    def observe(self,history,state=None):
        assert history['rgb'].shape[0]==1
        if state is None:state=self.initial(history['metadata'][:,0])
        else:state=dict(state)
        for i in range(history['rgb'].shape[1]):
            metadata=history['metadata'][:,i];depth=history['depth_m'][:,i];valid=history['depth_valid'][:,i]
            image=self.frame(history['rgb'][:,i],depth,valid)
            mask=surface_mask(depth,valid,metadata)
            delta=metadata[:,6:8]-state['camera_xy']
            args=(state['map'],image,mask,metadata,history['previous_action'][:,i],delta,state['history_frames']==0)
            memory=checkpoint(self.history_step,*args,use_reentrant=False) if torch.is_grad_enabled() else self.history_step(*args)
            # This mask tracks observed history support, not static geometry or
            # future predicted pixels. It is aligned but never velocity-shifted.
            support=align_map(state['observed_support'],delta).clamp(0,1)
            support=torch.maximum(support,mask[None,None,:,:,None].float())
            state={'map':memory,'observed_support':support,'camera_xy':metadata[:,6:8],
                   'metadata':metadata,'image':image,'history_frames':state['history_frames']+1}
        return state

    def future_step(self,memory,image,metadata,control):
        depth=image[:,3:4];valid=image[:,4:5]>0.5
        mask=surface_mask(depth,valid,metadata)
        shifted=shift_velocity(memory)
        token=self.control(torch.cat((metadata,control),-1))[:,None]
        memory=self.memory(shifted,image,mask,token)
        visible,indices=self.memory.extract_view_tokens(memory,mask)
        pos=self.memory.map_pos_enc(SIZE,SIZE,device=memory.device)[indices]
        context=(visible+pos[None,None]).reshape(1,-1,256)
        if context.shape[1]==0:context=memory.new_zeros((1,1,256))
        decoded=self.decoder(context)
        rgb=decoded[:,:3].sigmoid();depth=F.softplus(decoded[:,3:4])
        own_valid=torch.isfinite(depth)&(depth>0)&(depth<20)
        feedback=torch.cat((rgb-.5,torch.where(own_valid,depth,0),own_valid.float()),1)
        tokens=memory.permute(0,2,3,1,4).reshape(1,SIZE*SIZE,5*256)
        pooled=self.pool(tokens)
        return memory,feedback,pooled,torch.cat((rgb,depth),1)

    def imagine(self,state,controls,goal):
        assert controls.shape==(1,200,4)
        memory=state['map'];image=state['image'];features=[];images=[];snapshots={0:memory}
        for step in range(200):
            # Future camera and proprioception stay at public decision anchor;
            # only known clock and the independent control token advance.
            metadata=state['metadata'].clone();metadata[:,17]=(step+1)/200
            args=(memory,image,metadata,controls[:,step])
            memory,image,pooled,decoded=(checkpoint(self.future_step,*args,use_reentrant=False)
                if torch.is_grad_enabled() else self.future_step(*args))
            features.append(pooled);images.append(decoded)
            if (step+1)%50==0:snapshots[step+1]=memory
        features=torch.stack(features,1)
        return {'task':self.task(features,goal),'future_features':features,'predicted_rgbd':torch.stack(images,1),
                'snapshots':snapshots,'observed_support':state['observed_support'],
                'camera_xy':state['camera_xy']}

    def predict(self,history,controls,goal):
        state=self.observe(history)
        return {'decision':state,**self.imagine(state,controls,goal)}

    def loss(self,history,controls,goal,labels,future_images):
        assert set(future_images)=={'rgb','depth_m','depth_valid'}
        output=self.predict(history,controls,goal)
        losses=task_loss(output['task'],labels)
        rgbd=output['predicted_rgbd']
        losses['rgb_mse']=(rgbd[:,:,:3]-future_images['rgb'].float().detach()/255).square().mean()
        valid=future_images['depth_valid']
        losses['valid_depth_mse']=torch.where(valid,(rgbd[:,:,3:4]-future_images['depth_m'].detach()).square(),0).sum()/valid.sum().clamp_min(1)
        return sum(losses.values()),losses
