"""Deterministic branch sampling and framework-neutral accumulation boundaries."""

from __future__ import annotations

import math
import os
from pathlib import Path
import random

from .pair_contract import require
from .r4_learning_data import WORLDS
from .r4_generation_v2 import ACTIONS

VERSION = "spatial-history-r4-learning-runtime-v1"


def _tuples(value):
    if isinstance(value, list):
        return tuple(_tuples(item) for item in value)
    return value


class UniformBranchSampler:
    """Uniform family/world/candidate draws with an exactly restorable RNG state."""

    def __init__(self, family_ids, seed):
        require(isinstance(family_ids, (list, tuple)) and family_ids, "training families required")
        require(len(set(family_ids)) == len(family_ids)
                and all(type(item) is str and item.startswith("r4-") for item in family_ids),
                "unique R4 training families required")
        require(type(seed) is int and seed >= 0, "nonnegative sampler seed required")
        self.family_ids = tuple(family_ids)
        self.seed = seed
        self.draws = 0
        self._random = random.Random(seed)

    def draw(self):
        row = {
            "family_id": self._random.choice(self.family_ids),
            "world": self._random.choice(WORLDS),
            "action_slot": self._random.randrange(len(ACTIONS)),
        }
        row["action"] = ACTIONS[row["action_slot"]]
        self.draws += 1
        return row

    def state_dict(self):
        return {
            "schema_version": VERSION,
            "family_ids": list(self.family_ids),
            "seed": self.seed,
            "draws": self.draws,
            "python_random_state": self._random.getstate(),
        }

    @classmethod
    def from_state_dict(cls, state):
        require(set(state) == {"schema_version", "family_ids", "seed", "draws", "python_random_state"}
                and state["schema_version"] == VERSION, "sampler checkpoint schema")
        sampler = cls(state["family_ids"], state["seed"])
        require(type(state["draws"]) is int and state["draws"] >= 0, "sampler draw count")
        sampler._random.setstate(_tuples(state["python_random_state"]))
        sampler.draws = state["draws"]
        return sampler


def torch_targets(branch, device="cuda", *, auxiliary=False):
    """Tensorize separated targets without adding audit identities to model inputs."""
    import torch

    require(branch["schema_version"] == "spatial-history-r4-learning-branch-v1", "branch schema")
    target = branch["targets"]
    labels = {
        "position_m": torch.as_tensor(target["object_position_m"], dtype=torch.float32,
                                      device=device)[None],
        "contact": torch.as_tensor(target["interval_contact"], dtype=torch.bool,
                                   device=device)[None],
        "success": torch.as_tensor([target["task_success"]], dtype=torch.bool, device=device),
    }
    images = None
    if auxiliary:
        raw = branch["auxiliary_targets"]
        require(raw is not None, "auxiliary targets were not loaded")
        images = {
            "rgb": torch.as_tensor(raw["future_rgb"], dtype=torch.uint8, device=device)
                        .permute(0, 3, 1, 2)[None],
            "depth_m": torch.as_tensor(raw["future_depth_m"], dtype=torch.float32,
                                       device=device)[:, None][None],
            "depth_valid": torch.as_tensor(raw["future_depth_valid"], dtype=torch.bool,
                                           device=device)[:, None][None],
        }
    return labels, images


def accumulated_torch_step(model, optimizer, branches, loss_for_branch, *, accumulation=8,
                           clip_norm=1.0):
    """Average complete-branch losses, clip once, then perform exactly one update."""
    import torch

    require(len(branches) == accumulation == 8, "exactly eight complete branches per update")
    require(math.isclose(clip_norm, 1.0, rel_tol=0, abs_tol=0), "registered clip norm")
    optimizer.zero_grad(set_to_none=True)
    term_sums = {}
    losses = []
    for branch in branches:
        loss, terms = loss_for_branch(model, branch)
        require(loss.ndim == 0 and bool(torch.isfinite(loss)), "nonfinite branch loss")
        require(terms and all(value.ndim == 0 and bool(torch.isfinite(value)) for value in terms.values()),
                "nonfinite or empty loss terms")
        (loss / accumulation).backward()
        losses.append(float(loss.detach()))
        for name, value in terms.items():
            term_sums[name] = term_sums.get(name, 0.0) + float(value.detach())
    parameters = [value for value in model.parameters() if value.requires_grad]
    require(parameters and any(value.grad is not None for value in parameters), "no trainable gradient")
    norm = torch.nn.utils.clip_grad_norm_(parameters, clip_norm, error_if_nonfinite=True)
    optimizer.step()
    return {
        "branch_loss_mean": math.fsum(losses) / accumulation,
        "term_means": {name: value / accumulation for name, value in sorted(term_sums.items())},
        "gradient_norm_before_clip": float(norm.detach()),
        "branches": accumulation,
    }


def save_torch_checkpoint(path, payload):
    """Create one immutable checkpoint with no partially named success artifact."""
    import hashlib
    import torch

    path = Path(path)
    require(not path.exists(), "refuse checkpoint overwrite")
    require(set(payload) == {"schema_version", "update", "model", "optimizer", "sampler",
                             "torch_rng_state", "cuda_rng_state", "binding"},
            "checkpoint fields")
    require(payload["schema_version"] == VERSION and type(payload["update"]) is int
            and payload["update"] >= 0, "checkpoint version/update")
    partial = path.with_name(path.name + ".partial")
    require(not partial.exists(), "partial checkpoint already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        torch.save(payload, partial)
        with partial.open("rb+") as handle:
            os.fsync(handle.fileno())
        os.replace(partial, path)
    except BaseException:
        # Preserve a partial write for diagnosis; it is never accepted as a checkpoint.
        raise
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"bytes": path.stat().st_size, "sha256": digest}


def load_torch_checkpoint(path, expected_binding):
    """Load tensors/primitives only and reject a different code/data/config binding."""
    import torch

    value = torch.load(Path(path), map_location="cpu", weights_only=True)
    require(value["schema_version"] == VERSION and value["binding"] == expected_binding,
            "checkpoint binding changed")
    UniformBranchSampler.from_state_dict(value["sampler"])
    return value
