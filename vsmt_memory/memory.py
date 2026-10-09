"""``VSMTMemory``: the VSMT-lean entity memory driven frame by frame from an RGB-D stream.

Each call to ``step`` runs the frozen per-frame loop ``vsmt.lean_runner.run_frame`` for the arm ``VSMT-lean``: entity
geometry by the per-point depth test, recall, the sealed association/birth features, the three learned cost heads, one
rectangular assignment, existence decisions at the selected ``tau_r``, and the atomic commit through the versioned
executor with the shared dormancy and deduplication rules.  The policy values are read from the frozen contracts; the
weights are those of ``weights.load_pretrained``.  This module adds no decision rule of its own.

The cost heads were trained and evaluated on ProcTHOR houses only.  Whether they transfer to other scenes or sensors
has not been tested.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from . import _repo
from .conventions import CameraIntrinsics, CameraPose
from .frontend import BuiltFrame, DinoV2Extractor, Sam2MaskGenerator, build_frame
from .weights import PretrainedWeights, load_pretrained
from cpmt.hashing import clone_json
from vsmt import lean_assignment as la
from vsmt import lean_memory as lm
from vsmt import lean_model
from vsmt import lean_runner as lr

ARM = "VSMT-lean"
S0_01_CONTRACT = _repo.CONFIG_DIR / "lean_s0_entity_memory_v2.json"
S0_05_CONTRACT = _repo.CONFIG_DIR / "lean_s0_arms_v2.json"
S2_01_CONTRACT = _repo.CONFIG_DIR / "lean_s2_01_runner_v1.json"


def frozen_policy() -> dict[str, Any]:
    """The shared runner values (dormancy limit, deduplication, visibility minimum, sampling) from their contracts."""

    s0_01, s0_05, s2_01 = (_repo.load_json(p) for p in (S0_01_CONTRACT, S0_05_CONTRACT, S2_01_CONTRACT))
    policy = {
        "dormancy_missed_opportunity_limit": s0_01["shared_dormancy"]["dormancy_missed_opportunity_limit"],
        "dedup": {name: s0_01["shared_dedup"][name]
                  for name in ("period_ticks", "descriptor_cosine_min", "centroid_distance_max_m", "aabb_iou_min")},
        "should_be_visible_min_ratio": s0_05["shared"]["should_be_visible_min_ratio"],
        "entity_geometry_samples_per_axis": s2_01["entity_geometry"]["samples_per_axis"],
    }
    return lr.validate_policy(policy)


@dataclass(frozen=True)
class Operation:
    """One atom of a committed frame program.

    ``atom`` is NOOP, BIND, BIRTH, RETRACT or REACTIVATE; ``mask_index`` is the index of the input mask the fragment
    came from (BIND, BIRTH and REACTIVATE only); ``decision_basis`` is the logit or the two visibility ratios the atom
    was decided on.
    """

    atom: str
    entity_id: str
    fragment_id: str | None
    mask_index: int | None
    decision_basis: dict[str, Any]


@dataclass(frozen=True)
class EntityRecord:
    """One entity after the frame.

    ``state`` is active, dormant or retracted; a retracted entity keeps its identity and history and can be
    reactivated.  A new version is opened by every change of the entity -- BIRTH, BIND, REACTIVATE, RETRACT, turning
    dormant and absorbing a duplicate -- so ``version_count`` counts changes, not lifecycles; ``version_id`` names the
    current one.  ``canonical_of`` lists the entities folded into this one by the shared deduplication.  Coordinates
    are in the frozen world frame (+y up; ``conventions.to_user_world`` converts back)."""

    entity_id: str
    state: str
    version_id: str
    version_count: int
    centroid_m: tuple[float, float, float]
    aabb_min_m: tuple[float, float, float]
    aabb_max_m: tuple[float, float, float]
    observation_count: int
    last_seen_tick: int
    missed_opportunity_count: int
    canonical_of: tuple[str, ...] = ()


@dataclass
class FrameResult:
    """What one ``step`` produced.

    ``program`` lists the committed atoms; ``maintenance`` the shared rules applied after them, as
    ``{"dormancy": [{"entity_id", "missed_opportunity_count"}], "dedup": [{"canonical_entity_id", "folded_entity_id",
    "descriptor_cosine"}]}`` (a folded entity is removed and its ID kept in the canonical entity's ``canonical_of``);
    ``entities`` the memory after the frame.  A skipped frame (``skipped_reason`` set) left the memory unchanged.
    """

    tick: int
    program: list[Operation]
    maintenance: dict[str, Any]
    entities: list[EntityRecord]
    fragment_to_mask: dict[str, int] = field(default_factory=dict)
    dropped_masks: list[tuple[int, str]] = field(default_factory=list)
    illegal_program: dict[str, Any] | None = None
    skipped_reason: str | None = None


def entity_records(memory: Mapping[str, Any]) -> list[EntityRecord]:
    """The entities of a memory record as ``EntityRecord`` rows, ordered by ``entity_id``."""

    rows = []
    for entity in sorted(memory["entities"], key=lambda e: str(e["entity_id"])):
        rows.append(EntityRecord(
            entity_id=str(entity["entity_id"]), state=str(entity["state"]),
            version_id=str(entity["versions"][-1]["version_id"]), version_count=len(entity["versions"]),
            centroid_m=tuple(float(v) for v in entity["centroid_m"]),
            aabb_min_m=tuple(float(v) for v in entity["aabb_min_m"]),
            aabb_max_m=tuple(float(v) for v in entity["aabb_max_m"]),
            observation_count=int(entity["observation_count"]), last_seen_tick=int(entity["last_seen_tick"]),
            missed_opportunity_count=int(entity["missed_opportunity_count"]),
            canonical_of=tuple(str(v) for v in entity.get("canonical_of", ()))))
    return rows


class VSMTMemory:
    """The VSMT-lean memory of one stream (one episode).

    Construct it with ``from_pretrained`` for the released weights, then call ``step`` once per RGB-D frame in time
    order.  Poses must be causal (from odometry or SLAM up to the current frame) and expressed in one fixed world frame
    with +y up (see ``conventions.CameraPose``).
    """

    def __init__(self, weights: PretrainedWeights, *, descriptor_extractor: Any = None, mask_generator: Any = None,
                 episode_id: str = "stream", device: str = "cpu", strict: bool = False) -> None:
        self.weights = weights
        self.config = {"tau_r": float(weights.tau_r)}
        self.policy = frozen_policy()
        self.scorer = lean_model.LeanScorer(lean_model.load_heads(weights.heads, device=device), device=device)
        self.projector = lr.descriptor_projector(weights.reid_head,
                                                 expected_sha256=la.reid_weights_sha256_for(weights.mask_source),
                                                 device=device)
        self.descriptor_extractor = descriptor_extractor
        self.mask_generator = mask_generator
        self.strict = strict
        self.reset(episode_id)

    @classmethod
    def from_pretrained(cls, front_end: str = "sam2", seed: int = 7, *, cache_dir: Path | None = None,
                        restored_root: Path | None = None, reid_head_path: Path | None = None,
                        dinov2_repository: Path | None = None, dinov2_checkpoint: Path | None = None,
                        load_descriptor: bool = True, load_sam2: bool = False, sam2_checkpoint: Path | None = None,
                        device: str = "cpu", strict: bool = False, episode_id: str = "stream") -> "VSMTMemory":
        """The memory with the released weights of ``front_end`` (``"sam2"`` or ``"instance"``) and ``seed``.

        ``load_descriptor`` loads DINOv2 ViT-B/14 (needed by ``step``; not by ``step_cache_frame``); ``load_sam2``
        loads the SAM 2.1 mask generator used when ``step`` is called without masks.
        """

        from .weights import default_cache_dir

        weights = load_pretrained(front_end, seed, cache_dir=cache_dir, restored_root=restored_root,
                                  reid_head_path=reid_head_path)
        cache = Path(cache_dir) if cache_dir is not None else default_cache_dir()
        extractor = DinoV2Extractor(cache_dir=cache, repository=dinov2_repository, checkpoint=dinov2_checkpoint,
                                    device=device) if load_descriptor else None
        generator = Sam2MaskGenerator(cache_dir=cache, checkpoint=sam2_checkpoint, device=device) if load_sam2 else None
        return cls(weights, descriptor_extractor=extractor, mask_generator=generator, episode_id=episode_id,
                   device=device, strict=strict)

    def reset(self, episode_id: str = "stream") -> None:
        """Start a new, empty memory (a new stream)."""

        self._state = lr.initial_state(episode_id=episode_id, arm=ARM)
        self._chain: list[list[Any]] = []

    @property
    def tick(self) -> int:
        """The number of frames committed so far."""

        return int(self._state["memory"]["tick"])

    @property
    def memory(self) -> dict[str, Any]:
        """A copy of the full memory record: entities with their version chains and evidence, and the transaction log."""

        return clone_json(self._state["memory"])

    def entities(self, *, include_retracted: bool = True) -> list[EntityRecord]:
        """The current entities; retracted ones are included unless ``include_retracted`` is false."""

        rows = entity_records(self._state["memory"])
        return rows if include_retracted else [row for row in rows if row.state != "retracted"]

    def resolve(self, entity_id: str) -> str | None:
        """The ID of the live entity that now carries ``entity_id`` (the same ID, or the ID of the entity it was folded
        into by deduplication), or None for an ID this memory never had.  A folded ID disappears from ``entities()``;
        map stored IDs through this."""

        for entity in self._state["memory"]["entities"]:
            if str(entity["entity_id"]) == entity_id or entity_id in entity.get("canonical_of", ()):
                return str(entity["entity_id"])
        return None

    def entity_tokens(self) -> list[dict[str, Any]]:
        """The fixed-field per-entity export for a downstream planner or world model (``lean_memory.entity_tokens``)."""

        return lm.entity_tokens(self._state["memory"])

    def trajectory_sha256(self) -> str:
        """Digest of the per-frame seal chain (tick, both stage seals, committed memory digest); the same definition as
        ``trajectory_sha256`` in the audit runner, so a replay of a released episode can be compared with its audit."""

        return hashlib.sha256(json.dumps(self._chain, separators=(",", ":")).encode("utf-8")).hexdigest()

    def step(self, rgb: np.ndarray, depth_m: np.ndarray, intrinsics: CameraIntrinsics, pose: CameraPose,
             masks: Sequence[np.ndarray] | None = None) -> FrameResult:
        """Process one frame.

        ``rgb`` is uint8 (H, W, 3); ``depth_m`` is metric z-depth (H, W), invalid pixels as 0, NaN or inf; ``masks``
        are boolean (H, W) instance masks (one object each, any order).  Without masks the SAM 2.1 generator runs
        (``from_pretrained(load_sam2=True)``).
        """

        if self.descriptor_extractor is None:
            raise RuntimeError("step needs DINOv2: construct with load_descriptor=True")
        if masks is None:
            if self.mask_generator is None:
                raise RuntimeError("no masks given and no SAM 2.1 generator loaded (from_pretrained(load_sam2=True))")
            from .conventions import resize_to_frame_size

            rgb, depth_m, _, intrinsics = resize_to_frame_size(np.asarray(rgb), np.asarray(depth_m), [], intrinsics)
            masks = self.mask_generator(rgb)
        built = build_frame(tick=self.tick + 1, rgb=rgb, depth_m=depth_m, intrinsics=intrinsics, pose=pose,
                            masks=masks, patch_tokens=self.descriptor_extractor, strict=self.strict)
        return self._commit(built)

    def step_cache_frame(self, cache_frame: Mapping[str, Any], *, fragment_to_mask: Mapping[str, int] | None = None) -> FrameResult:
        """Process one frame that is already in the frozen cache format, with its public depth view attached.

        This is the path of the released caches (Hugging Face T1/T3); ``episodes.HfEpisode`` builds such frames.
        """

        return self._commit(BuiltFrame(cache_frame=dict(cache_frame), fragment_to_mask=dict(fragment_to_mask or {})))

    def _commit(self, built: BuiltFrame) -> FrameResult:
        if built.cache_frame is None:
            return FrameResult(tick=self.tick, program=[], maintenance={}, entities=self.entities(),
                               dropped_masks=built.dropped_masks, skipped_reason=built.skipped_reason)
        step = lr.run_frame(self._state, built.cache_frame, arm=ARM, config=self.config, policy=self.policy,
                            descriptor=la.SELECTED_DESCRIPTOR, projector=self.projector, scorer=self.scorer)
        self._state = step["state"]
        receipt = step["receipt"]
        self._chain.append([int(receipt["tick"]), str(receipt["stage_a_seal_sha256"]),
                            str(receipt["stage_b_seal_sha256"]), str(receipt["memory_digest_after"])])
        record = self._state["memory"]["transaction_log"][-1]
        program = [Operation(atom=str(op["atom"]), entity_id=str(op["entity_id"]), fragment_id=op.get("fragment_id"),
                             mask_index=built.fragment_to_mask.get(op["fragment_id"]) if op.get("fragment_id") else None,
                             decision_basis=dict(op.get("decision_basis") or {}))
                   for op in record["operations"]]
        return FrameResult(tick=int(receipt["tick"]), program=program, maintenance=clone_json(record["post_maintenance"]),
                           entities=self.entities(), fragment_to_mask=dict(built.fragment_to_mask),
                           dropped_masks=built.dropped_masks, illegal_program=receipt["illegal_program"])


__all__ = ["EntityRecord", "FrameResult", "Operation", "VSMTMemory", "entity_records", "frozen_policy"]
