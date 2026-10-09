# Using the VSMT-lean memory on your own RGB-D stream

The package [`vsmt_memory/`](../vsmt_memory/) wraps the object-level memory of the paper (entity records, recall,
frame-level joint assignment, existence decisions and the versioned executor) for any RGB-D stream with camera poses
and instance masks. Every decision is made by the frozen functions in `src/vsmt/lean_*.py` that produced the paper's
results; the package only builds their inputs and returns their outputs as typed records. Status: implemented;
verified against the frozen pipeline on a released episode (see [Verification](#8-verification)).

**Scope.** The cost heads were trained, selected and evaluated on procedurally generated ProcTHOR houses only. Whether
they transfer to other scenes, sensors or segmenters has not been tested. The external 3RScan check in the paper is
descriptive (instance masks rendered from annotated meshes, no gate) and is not evidence of transfer. On the synthetic,
out-of-distribution scenes tried while checking this guide (ray-cast rooms with textured boxes), the memory confused
boxes that look alike to DINOv2 (projected-descriptor cosine 0.56–0.71) and bound them to one entity across several
metres, and a removed box was not retracted: the distinction between hidden, removed and moved objects that the paper
measures on ProcTHOR did not appear there. Validate on your own data before relying on it. The package does not
estimate poses, segment images (except through the optional SAM 2.1 generator), name objects, or learn online.

## Contents

1. [Install](#1-install)
2. [Quick start](#2-quick-start)
3. [Inputs](#3-inputs)
4. [Outputs](#4-outputs)
5. [Weights](#5-weights)
6. [Behaviour and cost](#6-behaviour-and-cost)
7. [Examples and tests](#7-examples-and-tests)
8. [Verification](#8-verification)
9. [Citation and licence](#9-citation-and-licence)

## 1. Install

Python 3.11 or 3.12. From a clone of this repository:

```bash
git clone https://github.com/JingzeSun/VSMT.git
cd VSMT
uv sync
uv pip install huggingface_hub pillow
```

`uv sync` installs `numpy` and `torch`; a CPU build of `torch` is enough. Run your code from the repository root, or put
the repository root on `PYTHONPATH`; the package then imports the frozen modules from `src/`. Nothing is installed
system-wide.

Downloaded on first use, each checked against a pinned SHA-256; the weights and checkpoints go into
`$VSMT_MEMORY_CACHE` (default `~/.cache/vsmt_memory`), the DINOv2 code into the `torch.hub` cache (`~/.cache/torch/hub`);
files already in a cache are used without network access:

| What | Size | From |
|---|---|---|
| cost heads and ReID head | 100 MB | Hugging Face [`Jsun0632/vsmt-lean`](https://huggingface.co/Jsun0632/vsmt-lean), revision `0b2ce7f8bb5d` |
| DINOv2 ViT-B/14 checkpoint | 346 MB | `dl.fbaipublicfiles.com`, the file the paper's front end used |
| DINOv2 model code | 1 MB | `torch.hub` at commit `7764ea0f` of `facebookresearch/dinov2` (or pass a local clone) |
| SAM 2.1 Hiera Small (optional) | 184 MB | `dl.fbaipublicfiles.com`; needs the `sam2` package (the paper used commit `2b90b9f5`) |

## 2. Quick start

```python
import numpy as np
from vsmt_memory import VSMTMemory, CameraIntrinsics, CameraPose

memory = VSMTMemory.from_pretrained()          # heads trained on SAM 2.1 masks (no sam2 package needed), seed 7
intrinsics = CameraIntrinsics(fx=525.0, fy=525.0, cx=319.5, cy=239.5, width=640, height=480)

for rgb, depth_m, world_from_camera, masks in my_stream():          # your sensor, odometry and segmenter
    pose = CameraPose.from_opencv(world_from_camera, world_up="z")  # ROS-style map frame, OpenCV camera
    result = memory.step(rgb, depth_m, intrinsics, pose, masks)
    for op in result.program:                    # NOOP / BIND / BIRTH / RETRACT / REACTIVATE
        print(result.tick, op.atom, op.entity_id, op.mask_index)

for entity in memory.entities():                 # identity, state, version
    print(entity.entity_id, entity.state, entity.version_count, entity.centroid_m)
```

## 3. Inputs

One call of `memory.step(rgb, depth_m, intrinsics, pose, masks)` per frame, in time order:

| Argument | Type | Meaning |
|---|---|---|
| `rgb` | `uint8` array (H, W, 3) | colour image |
| `depth_m` | float array (H, W) | metric depth along the camera axis (z-depth, not ray length), registered to `rgb`; values outside 0.05–20 m, NaN or inf are invalid |
| `intrinsics` | `CameraIntrinsics(fx, fy, cx, cy, width, height)` | pinhole intrinsics of `rgb`/`depth_m` in pixels (OpenCV convention) |
| `pose` | `CameraPose` | causal camera-to-world pose (odometry or SLAM up to this frame) in one fixed world frame |
| `masks` | list of bool arrays (H, W), or `None` | every segment your segmenter returns, in any order, including floors, walls and other surfaces; `None` runs SAM 2.1 (`from_pretrained(load_sam2=True)`) |

Conventions (the frozen ones; see [`conventions.py`](../vsmt_memory/conventions.py)):

- **Pose.** The frozen code uses a gravity-aligned world with +y up and a camera with +x right, +y up, +z forward.
  `CameraPose.from_opencv(T, world_up=...)` converts a 4 x 4 camera-to-world matrix with an OpenCV camera (+y down) and
  a right-handed world whose up axis you name (`"z"` for ROS maps); the conversion is orthogonal, so distances, box
  volumes and heights are unchanged. Entity coordinates in the outputs are in the converted frame: your
  `(x, y, z)` with `world_up="z"` comes back as `(x, z, y)`.
- **ROS.** Take `world_from_camera` from tf as the transform from the camera's *optical* frame (`*_optical_frame`, z
  forward, y down) to the map frame, and convert depth images in millimetres (`16UC1`) to metres. Convert outputs back
  with `to_user_world(points, world_up="z")` (`from vsmt_memory import to_user_world`); for a box, convert both corners and take the element-wise minimum and
  maximum.
- **Segments.** Pass every segment, not only objects of interest: both training front ends produced fragments for
  walls, floors, doors and windows as well (the simulator's instance masks include them; SAM 2.1 segments whatever it
  finds), and the memory keeps entities for them; the paper's evaluation excluded structural objects from scoring only.
- **Resolution.** Frames are resized to 224 x 224 (the DINOv2 input size of the frozen front end and the size of every
  training frame): RGB bilinear, depth and masks by the nearest pixel centre, intrinsics accordingly. Pixel counts
  therefore keep the scale the cost heads were trained on; non-square images are stretched for DINOv2.
- **Masks.** After resizing, masks below 196 pixels are dropped (about 196 x H x W / 224² pixels of the input image,
  for example about 1,200 at 640 x 480); identical masks count once; a frame with more than 64
  masks is skipped (`result.skipped_reason`), and a mask with too little valid depth (fewer than 32 points or 25% of its
  pixels) is dropped (`result.dropped_masks`). With `strict=True` these raise instead, as in the paper's cache builder.

## 4. Outputs

`step` returns a `FrameResult`:

| Field | Content |
|---|---|
| `tick` | frame number (1, 2, …); a skipped frame does not advance it |
| `program` | the committed atoms, each an `Operation(atom, entity_id, fragment_id, mask_index, decision_basis)`; `mask_index` refers to your `masks` list (BIND, BIRTH, REACTIVATE); `decision_basis` holds the logit or the two visibility ratios behind the atom |
| `maintenance` | the shared rules applied after the program: `{"dormancy": [{"entity_id", "missed_opportunity_count"}], "dedup": [{"canonical_entity_id", "folded_entity_id", "descriptor_cosine"}]}`; entities turn dormant after 3 consecutive missed opportunities, and duplicates are merged every 10 frames |
| `entities` | every entity after the frame as `EntityRecord(entity_id, state, version_id, version_count, centroid_m, aabb_min_m, aabb_max_m, observation_count, last_seen_tick, missed_opportunity_count, canonical_of)` |
| `fragment_to_mask`, `dropped_masks`, `skipped_reason`, `illegal_program` | bookkeeping for the frame |

Atoms: `BIND` attaches a mask to an active entity; `BIRTH` creates an entity; `REACTIVATE` reopens a dormant or
retracted entity with the same identity; `RETRACT` closes the version of an entity that should be visible but is judged
no longer at its place (history is kept); `NOOP` records a missed opportunity. States: `active`, `dormant` (missed
repeatedly, no evidence it is gone), `retracted` (evidence it is gone; can be reactivated).

Versions: every change of an entity opens a new version — BIRTH, BIND (new evidence and geometry), REACTIVATE, RETRACT,
turning dormant, and absorbing a duplicate — so `version_count` counts changes, not lifecycles; `version_id` names the
current version, and `memory.memory` holds the whole chain with what opened each version.

Merged identities: the shared deduplication folds one of two duplicate entities into the other; the folded ID then
disappears from `entities()` and is listed in the survivor's `canonical_of`. If you store entity IDs (for example in a
planner), map them with `memory.resolve(entity_id)`: it returns the ID of the live entity that now carries the ID (the
same ID if the entity was never folded), or `None` for an ID the memory never had; look the record up in
`memory.entities()`.

Also available: `memory.entities(include_retracted=False)`, `memory.entity_tokens()` (one fixed-field row per entity
for a planner or world model), `memory.memory` (the full record: version chains, evidence, transaction log),
`memory.reset()` (optionally `reset(episode_id=...)`) for a new stream, and `memory.trajectory_sha256()`.

## 5. Weights

`VSMTMemory.from_pretrained(front_end="sam2", seed=7)` loads the round-1 VSMT-lean cost heads of one training seed, the
ReID projection head shared by all compared methods, and the existence threshold `tau_r` that was selected on
validation for that front end (0.25 for SAM 2.1). Each file is checked against the release manifest and against the
digest recorded by the freeze that preceded the test run.

| `front_end` | Trained on | When to use | Released |
|---|---|---|---|
| `"sam2"` (default) | SAM 2.1 automatic masks (part-level, over-segmented) | masks from SAM or another segmenter whose masks are not exact whole objects | yes |
| `"instance"` | the simulator's instance masks (near-perfect, whole objects) | near-perfect whole-object masks | heads yes; its ReID head (`5cea91cf…`) is not released, and `reid_head_path=` accepts only that exact file (a head retrained in S1-04 has another digest; docs/REPRODUCE.md, section 11) |

Only `"sam2"` can be used from the release alone; the instance-mask ReID head is not published anywhere at present.

`seed` is one of 7, 19, 31, 43, 59. The paper reports the mean over all five, and no seed is recommended: seed 7 is the
default because it is the first registered seed, not because it scored best, and single seeds differ (validation
identity continuity with SAM 2.1 ranged from 0.02 to 0.11 across seeds). Choosing a seed on your own validation data is
the safe course. Other options: `episode_id` (a label stored in the memory record), `strict`, `cache_dir`,
`restored_root` (reuse files restored by `ops/vsmt/hf_fetch.py`), `dinov2_repository`/`dinov2_checkpoint` (offline
use), `load_sam2`, `sam2_checkpoint`, `device`.

## 6. Behaviour and cost

- The memory assumes a revisit setting: decisions about unseen objects are made when their remembered surface should be
  visible again. An entity outside the view is never retracted.
- Poses must be causal and in one world frame for the whole stream; a pose jump moves every new observation away from
  its entity.
- Speed on a laptop CPU (Intel 13th generation, torch 2.14): about 0.37 s per frame including DINOv2, about 0.15–0.25 s
  without it (cache replay). The memory record grows by about 10 KB per frame (3.5 MB after 341 frames); the
  transaction log and the version chains are never pruned, so for long missions start a new memory per session
  (`memory.reset`) or keep the last `memory.memory` as a snapshot.
- Results are deterministic for the same inputs, code and environment. Across CPUs and library versions a few
  near-tie decisions can differ (see [Verification](#8-verification)).

## 7. Examples and tests

Run from the repository root:

```bash
python -m vsmt_memory.examples.hf_episode --data-root <data root> --check
python -m vsmt_memory.examples.synthetic_scene
python -m unittest discover -s vsmt_memory/tests -t .
```

- [`examples/hf_episode.py`](../vsmt_memory/examples/hf_episode.py): one released ProcTHOR episode (341 frames)
  streamed as RGB, depth, intrinsics, pose and masks; prints the atoms, a summary every 50 frames and the entity table,
  and with `--check` compares the atoms with a replay of the released cache. It needs the episode from Hugging Face
  layer T1 (160 MB); `<data root>` is any directory, given both to the download and to the example:

  ```bash
  python ops/vsmt/hf_fetch.py --repo Jsun0632/vsmt-lean-s3-eval --repo-type dataset --revision 1bb81d27554d3795439172c418dc1416bff0c56e --dest <data root> --select validation/raw/procthor10k-0.1.2-train-02318.tar validation/sam2_cache/procthor10k-0.1.2-train-02318.tar
  ```
- [`examples/synthetic_scene.py`](../vsmt_memory/examples/synthetic_scene.py): a ray-cast room in the ROS convention at
  320 x 240; one box is removed and one moved between two turns of the camera. It prints what became of both boxes.
  It shows the conventions, not the method's accuracy (see Scope).
- Tests: conversions and the front end run without downloads; `test_parity.py` runs when `VSMT_DATA` is the data root
  of the episode above, into which `weights/sam2/` and `reid/` of T0 have also been restored with `hf_fetch.py` (they
  land under `vsmt_private/`; the replay test reads the weights there).

## 8. Verification

On validation episode `procthor10k-0.1.2-train-02318` (SAM 2.1 front end, seed 7, `tau_r` 0.25; Windows 11, Intel
13th-generation laptop CPU, Python 3.12.14, torch 2.14.0, numpy 2.5.2; 2026-10-09):

| Check | Result |
|---|---|
| Sealed-cache replay through the package against the frozen audit entry (`ops/vsmt/lean_s2_05_node_audit.py` at `paper-v1`), same environment | per-frame seal chain and final memory digest bit-identical (all 341 frames) |
| The same replay against the S3-04 probe audit computed on the server (Linux, Xeon, torch 2.8.0, numpy 2.3.2) | final entity states identical (50 active, 25 dormant, 1 retracted) and every metric of the audit report identical; the error decomposition differs in 19 of about 5,500 decisions and the seal chain differs |
| Fragments rebuilt from the public RGB-D and the cache's SAM 2.1 masks against the released cache | geometry bit-identical; DINOv2 descriptors within 6.7e-7 (the cache was computed on a GPU) |
| Full stream through `step` (RGB-D path) against the sealed-cache replay | 337 of 341 frames committed the same atoms on the same fragments |

## 9. Citation and licence

If you use the memory, please cite the paper (BibTeX in the [README](../README.md#citation)) and DINOv2; if you use
SAM 2.1 masks, also SAM 2:

```bibtex
@article{oquab2024dinov2,
  title   = {{DINOv2}: Learning Robust Visual Features without Supervision},
  author  = {Oquab, Maxime and Darcet, Timoth{\'e}e and Moutakanni, Th{\'e}o and others},
  journal = {Transactions on Machine Learning Research},
  year    = {2024}
}
@inproceedings{ravi2025sam2,
  title     = {{SAM 2}: Segment Anything in Images and Videos},
  author    = {Ravi, Nikhila and Gabeur, Valentin and Hu, Yuan-Ting and others},
  booktitle = {International Conference on Learning Representations (ICLR)},
  year      = {2025}
}
```

The code is released under Apache-2.0 ([LICENSE](../LICENSE)), the weights under Apache-2.0 (Hugging Face card); the
DINOv2 and SAM 2.1 checkpoints keep their own Apache-2.0 licences.
