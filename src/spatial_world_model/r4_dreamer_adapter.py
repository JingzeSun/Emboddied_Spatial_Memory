"""D-093 offline RGBD/task adapter around the pinned original Dreamer RSSM.

The caller binds the author repository before import. No author policy, value,
reward model, data loader, or train loop is constructed. Public inference and
training-only image/label loss are separate methods.
"""
import elements
import jax
import jax.numpy as jnp
import ninjax as nj
import numpy as np
import embodied.jax.nets as nn
from dreamerv3.rssm import RSSM, Encoder, Decoder

from .r4_model_inputs import prepare

# This task adaptation explicitly uses float32 compute, including metric depth.
nn.COMPUTE_DTYPE = jnp.float32


def tensorize(query, **mode):
    raw=prepare(query,**mode); h=raw['history']; length=len(h['rgb'])
    history={
        'rgb':jnp.asarray(h['rgb'],jnp.uint8).reshape(1,length,80,80,3),
        'depth_m':jnp.asarray(h['depth_m'],jnp.float32).reshape(1,length,80,80,1),
        'depth_valid':jnp.asarray(h['depth_valid'],bool).reshape(1,length,80,80,1),
        'metadata':jnp.asarray(h['metadata'],jnp.float32)[None],
        'previous_action':jnp.asarray(h['previous_action'],jnp.float32)[None],
        'reset':jnp.asarray(h['reset'],bool)[None]}
    return history,jnp.asarray(raw['controls'],jnp.float32)[None],jnp.asarray(raw['goal'],jnp.float32)[None]


class DepthEncoder(nj.Module):
    def __call__(self, depth, valid):
        leading=depth.shape[:-3]
        x=jnp.concatenate([jnp.where(valid,depth,0),valid.astype(jnp.float32)],-1)
        x=x.reshape((-1,80,80,2))
        for i,width in enumerate((32,64,128,128)):
            x=jax.nn.gelu(self.sub(f'conv{i}',nn.Conv2D,width,3,2)(x))
        return x.reshape((*leading,-1))


class MetadataEncoder(nj.Module):
    def __call__(self,x):
        for i in range(2):x=jax.nn.gelu(self.sub(f'linear{i}',nn.Linear,256)(x))
        return x


class TaskHeads(nj.Module):
    def __call__(self,features,goal):
        x=features
        for i in range(2):x=jax.nn.gelu(self.sub(f'local{i}',nn.Linear,256)(x))
        local=self.sub('local_output',nn.Linear,4)(x)
        def step(hidden,item):
            projected=self.sub('gru_input',nn.Linear,768)(item)
            recurrent=self.sub('gru_hidden',nn.Linear,768)(hidden)
            ir,iz,inn=jnp.split(projected,3,-1);hr,hz,hn=jnp.split(recurrent,3,-1)
            reset=jax.nn.sigmoid(ir+hr);update=jax.nn.sigmoid(iz+hz)
            candidate=jnp.tanh(inn+reset*hn)
            hidden=(1-update)*candidate+update*hidden
            return hidden,hidden
        hidden,_=nj.scan(step,jnp.zeros((features.shape[0],256),jnp.float32),features,axis=1)
        pooled=jnp.concatenate([hidden,goal],-1)
        pooled=jax.nn.gelu(self.sub('success_hidden',nn.Linear,256)(pooled))
        success=self.sub('success_output',nn.Linear,1)(pooled)[...,0]
        return {'object_position_m':local[...,:3],'contact_logit':local[...,3],
                'success_logit':success,'success_state':hidden}


class DepthDecoder(nj.Module):
    def __call__(self,features):
        leading=features.shape[:-1]
        x=self.sub('initial',nn.Linear,3200)(features).reshape(-1,5,5,128)
        for i,width in enumerate((128,128,64,1)):
            x=x.repeat(2,1).repeat(2,2)
            x=self.sub(f'conv{i}',nn.Conv2D,width,3)(x)
            if i<3:x=jax.nn.gelu(x)
        return x.reshape((*leading,80,80,1))


class DreamerTask(nj.Module):
    def __init__(self):
        image_space={'rgb':elements.Space(np.uint8,(80,80,3))}
        action_space={'velocity_dt':elements.Space(np.float32,(4,))}
        self.rgb=Encoder(image_space,name='rgb')
        self.depth=DepthEncoder(name='depth')
        self.metadata=MetadataEncoder(name='metadata')
        self.rssm=RSSM(action_space,deter=1024,hidden=512,stoch=32,classes=32,blocks=8,name='rssm')
        self.heads=TaskHeads(name='task')
        self.rgb_decoder=Decoder(image_space,name='rgb_decoder')
        self.depth_decoder=DepthDecoder(name='depth_decoder')

    def encode(self,history):
        reset=history['reset']
        _,_,rgb=self.rgb({}, {'rgb':history['rgb']},reset,False)
        return jnp.concatenate([rgb,self.depth(history['depth_m'],history['depth_valid']),
                                self.metadata(history['metadata'])],-1)

    def observe(self,history):
        tokens=self.encode(history)
        state,entries,observed=self.rssm.observe(self.rssm.initial(tokens.shape[0]),tokens,
            {'velocity_dt':history['previous_action']},history['reset'],False)
        return state,{'tokens':tokens,**observed}

    @staticmethod
    def features(native):
        return jnp.concatenate([native['deter'],native['stoch'].reshape(*native['deter'].shape[:-1],-1)],-1)

    def imagine(self,state,controls,goal):
        assert controls.shape[1:]==(200,4)
        last,native,used=self.rssm.imagine(state,{'velocity_dt':controls},200,False)
        task=self.heads(self.features(native),goal)
        return last,native,task

    def predict(self,history,controls,goal):
        decision,observed=self.observe(history)
        last,native,task=self.imagine(decision,controls,goal)
        return {'decision':decision,'observed':observed,'future':native,'task':task}

    def reconstruct(self,native):
        leading=native['deter'].shape[:-1]
        reset=jnp.zeros(leading,bool)
        _,_,rgb=self.rgb_decoder({},native,reset,False)
        return rgb['rgb'].pred(),self.depth_decoder(self.features(native))

    def loss(self,history,controls,goal,labels,future_images):
        """Labels/images are targets only; main open-loop prediction precedes them.

        Future metadata is the declared decision anchor with an updated clock;
        no actual future robot proprioception is accepted by this interface.
        """
        assert set(labels)=={'position_m','contact','success'}
        assert set(future_images)=={'rgb','depth_m','depth_valid'}
        output=self.predict(history,controls,goal)
        task=output['task']
        bce=lambda logit,target: jax.nn.softplus(logit)-logit*jax.lax.stop_gradient(target)
        position=jnp.square((task['object_position_m']-jax.lax.stop_gradient(labels['position_m']))/0.1).mean()
        contact=bce(task['contact_logit'],labels['contact'].astype(jnp.float32)).mean()
        success=bce(task['success_logit'],labels['success'].astype(jnp.float32)).mean()
        # Separate posterior targets: none of these states enter task prediction.
        meta=jnp.repeat(history['metadata'][:,-1:],200,axis=1)
        meta=meta.at[:,:,17].set(jnp.arange(1,201,dtype=jnp.float32)[None]/200)
        teacher={'rgb':future_images['rgb'],'depth_m':future_images['depth_m'],
                 'depth_valid':future_images['depth_valid'],'metadata':meta,
                 'previous_action':controls,'reset':jnp.zeros(controls.shape[:2],bool)}
        tokens=self.encode(teacher)
        _,_,kl,posterior,_=self.rssm.loss(output['decision'],tokens,
            {'velocity_dt':controls},teacher['reset'],True)
        rgb,depth=self.reconstruct(posterior)
        target_rgb=jax.lax.stop_gradient(teacher['rgb'].astype(jnp.float32)/255)
        rgb_mse=jnp.square(rgb-target_rgb).mean()
        valid=teacher['depth_valid']
        depth_mse=jnp.where(valid,jnp.square(depth-jax.lax.stop_gradient(teacher['depth_m'])),0).sum()/jnp.maximum(valid.sum(),1)
        losses={'position':position,'contact':contact,'success':success,
                'rgb_mse':rgb_mse,'valid_depth_mse':depth_mse,'dyn_kl':kl['dyn'].mean(),'rep_kl':kl['rep'].mean()}
        total=position+contact+success+rgb_mse+depth_mse+0.5*losses['dyn_kl']+0.1*losses['rep_kl']
        return total,losses
