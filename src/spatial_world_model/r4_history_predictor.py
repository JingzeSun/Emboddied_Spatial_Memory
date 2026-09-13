"""D-099 proposed L/R baselines: full image history or public coverage retrieval.

Pure values/tensors. No file access, private geometry, future teacher inputs,
pretrained encoder, learned retrieval, or policy. See METHOD/DATA.
"""
import math

import torch
from torch import nn
from torch.utils.checkpoint import checkpoint

from .r4_coverage import HISTORY_VERSION, parameters, select_history, sensor_spec
from .r4_query_v2 import validate_query
from .r4_torch_task import TaskHeads, task_loss, tensorize


def prepare_query(query, *, retrieval=False, device='cuda', history_mode='full', history_cut_index=None):
    """Keep selection provenance outside the model state and numeric features."""
    mode = {'history_mode': history_mode, 'history_cut_index': history_cut_index}
    validate_query(query, **mode)
    history, controls, goal = tensorize(query, device=device, **mode)
    evidence = None
    if retrieval:
        source = query['history']
        fields = ('time_s', 'depth_m', 'camera_position_m', 'camera_xyzw', 'intrinsics')
        depth_history = {'schema_version': HISTORY_VERSION, 'frames': [
            {'width': 80, 'height': 80, **{key: source[key][i] for key in fields}}
            for i in range(len(source['time_s']))]}
        evidence = select_history(depth_history, sensor_spec(), parameters(), **mode)
        indices = evidence['selected_local_indices']
        history = {key: value[:, indices] for key, value in history.items()}
    return history, controls, goal, evidence


def sinusoidal(values, width):
    frequency = torch.exp(torch.arange(0, width, 2, device=values.device, dtype=values.dtype)
                          * (-math.log(10000) / width))
    phase = values[..., None] * frequency
    return torch.stack((phase.sin(), phase.cos()), -1).flatten(-2)


def mlp(input_width):
    return nn.Sequential(nn.Linear(input_width, 256), nn.GELU(), nn.Linear(256, 256))


class ImageBranch(nn.Module):
    def __init__(self, channels):
        super().__init__()
        layers = []
        for width in (32, 64, 128, 256):
            layers.extend((nn.Conv2d(channels, width, 3, stride=2, padding=1), nn.GELU()))
            channels = width
        self.layers = nn.Sequential(*layers)

    def forward(self, values):
        return self.layers(values)


class HistoryPredictor(nn.Module):
    """L and R have identical parameterization; only legal history selection differs."""
    def __init__(self):
        super().__init__()
        self.rgb = ImageBranch(3)
        self.depth = ImageBranch(2)
        self.metadata = mlp(37)
        self.previous_action = mlp(4)
        self.encoder = nn.ModuleList([nn.TransformerEncoderLayer(
            256, 8, 1024, 0.1, activation='gelu', batch_first=True, norm_first=True)
            for _ in range(6)])
        self.history_norm = nn.LayerNorm(256)
        self.control = mlp(41)
        self.decoder = nn.ModuleList([nn.TransformerDecoderLayer(
            256, 8, 1024, 0.1, activation='gelu', batch_first=True, norm_first=True)
            for _ in range(2)])
        self.future_norm = nn.LayerNorm(256)
        self.task = TaskHeads()
        y, x = torch.meshgrid(torch.linspace(-1, 1, 5), torch.linspace(-1, 1, 5), indexing='ij')
        position = torch.cat((sinusoidal(x, 128), sinusoidal(y, 128)), -1).reshape(1, 1, 25, 256)
        self.register_buffer('spatial_position', position)
        self.register_buffer('future_position', sinusoidal(torch.arange(1, 201).float() / 10, 256)[None])
        self.register_buffer('causal_mask', torch.ones(200, 200, dtype=torch.bool).triu(1))

    def encode_frames(self, history):
        rgb, depth, valid = history['rgb'], history['depth_m'], history['depth_valid']
        batch, frames = rgb.shape[:2]
        if rgb.shape[2:] != (3, 80, 80) or depth.shape != (batch, frames, 1, 80, 80):
            raise ValueError('native 80-pixel RGBD required')
        if valid.shape != depth.shape or valid.dtype != torch.bool:
            raise ValueError('separate depth validity required')
        if not 1 <= frames <= 121:
            raise ValueError('history length outside registered range')
        rgb_features = self.rgb(rgb.reshape(-1, 3, 80, 80).float() / 255)
        depth_input = torch.cat((torch.where(valid, depth, 0), valid.to(depth.dtype)), 2)
        depth_features = self.depth(depth_input.reshape(-1, 2, 80, 80))
        pixels = (rgb_features + depth_features).flatten(2).transpose(1, 2).reshape(batch, frames, 25, 256)
        metadata = self.metadata(history['metadata']) + self.previous_action(history['previous_action'])
        return pixels + metadata[:, :, None] + self.spatial_position

    def observe(self, history):
        frames = self.encode_frames(history)
        tokens = frames.flatten(1, 2)
        for layer in self.encoder:
            if torch.is_grad_enabled():
                tokens = checkpoint(layer, tokens, use_reentrant=False, preserve_rng_state=True)
            else:
                tokens = layer(tokens)
        return {'tokens': self.history_norm(tokens),
                'decision_metadata': history['metadata'][:, -1].clone()}

    def imagine(self, state, controls, goal):
        if controls.shape[1:] != (200, 4) or goal.shape != (controls.shape[0], 12):
            raise ValueError('200 controls and public goal required')
        if set(state) != {'tokens', 'decision_metadata'}:
            raise ValueError('only registered decision state accepted')
        anchor = state['decision_metadata'][:, None].expand(-1, 200, -1)
        future = self.control(torch.cat((controls, anchor), -1)) + self.future_position
        for layer in self.decoder:
            if torch.is_grad_enabled():
                future = checkpoint(layer, future, state['tokens'], tgt_mask=self.causal_mask,
                                    use_reentrant=False, preserve_rng_state=True)
            else:
                future = layer(future, state['tokens'], tgt_mask=self.causal_mask)
        future = self.future_norm(future)
        return {'future_features': future, 'task': self.task(future, goal)}

    def loss(self, history, controls, goal, labels):
        output = self.imagine(self.observe(history), controls, goal)
        terms = task_loss(output['task'], labels)
        return sum(terms.values()), terms
