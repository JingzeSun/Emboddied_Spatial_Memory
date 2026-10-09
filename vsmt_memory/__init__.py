"""VSMT-lean entity memory as a plug-in for an RGB-D stream (guide: docs/PLUGIN.md).

Per frame the memory takes RGB, metric depth, intrinsics, a camera pose and instance masks, and returns the committed
frame program (NOOP / BIND / BIRTH / RETRACT / REACTIVATE) and the entity table (identity, state, version).  The
memory, recall, joint assignment, existence decisions and executor are the frozen functions of ``src/vsmt/lean_*.py``;
the default weights are the released ones (Hugging Face ``Jsun0632/vsmt-lean``).  They were trained and evaluated on
ProcTHOR houses only; transfer to other scenes or sensors has not been tested.

    from vsmt_memory import VSMTMemory, CameraIntrinsics, CameraPose

    memory = VSMTMemory.from_pretrained()                 # SAM 2.1 front-end weights, seed 7
    result = memory.step(rgb, depth_m, intrinsics, pose, masks)
    for op in result.program: ...
    for entity in result.entities: ...
"""

from . import _repo  # noqa: F401  (puts the repository's src/ on sys.path)
from .conventions import CameraIntrinsics, CameraPose, to_user_world
from .memory import EntityRecord, FrameResult, Operation, VSMTMemory
from .weights import PretrainedWeights, load_pretrained

__all__ = ["CameraIntrinsics", "CameraPose", "EntityRecord", "FrameResult", "Operation", "PretrainedWeights",
           "VSMTMemory", "load_pretrained", "to_user_world"]
