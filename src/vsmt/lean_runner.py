"""D-224 / S2-01: the common runner -- cache frame + M_{t-1} -> frame program -> M_t, shared by every arm.

This module is the one place where a sealed cache frame and the previous memory become the next
memory.  Every arm goes through the same steps in the same order; an arm may only change what the
S0-05 contract says it may change (how the association, birth and existence logits are produced and
which atoms its vocabulary allows).  Nothing here reads a private file: the public phase is a pure
function of (cache frames, policy values, arm configuration, arm weights).

Per frame, in this order:
  1. entity geometry: the two S0-03 ratios per entity of M_{t-1}, derived online by the per-point
     depth test of ruling 74 (METHOD section 5) -- a pure function of (this frame's public depth,
     intrinsics and causal pose, M_{t-1}) with a registered sampling resolution and a frozen margin;
     the public depth view is attached to the frame by the reader after the seal check
     (``PUBLIC_DEPTH_VIEW_KEY``), never written into the cache;
  2. the S0-03 view of the frame under the descriptor S1-05 froze (the shared ReID projection of
     ``descriptor_vitb14``), or under the frozen-descriptor baseline the paper reports alongside;
  3. stage A: recall at the ruling-57/58 values, association and birth features, sealed;
  4. logits: rule arms from ``lean_arms`` on the sealed rows, learned arms from a caller-supplied
     scorer; solve; a rule arm's assignment must contain no sentinel pair;
  5. stage B: assignment receipt and existence features, sealed; the private gate receipt;
  6. existence decisions on the eligible rows (active or dormant, should-be-visible ratio at or
     above the shared minimum), per arm, with the arm's temporal state (ELU-P log-odds, RAC counters);
  7. compile the atoms within the arm's vocabulary and commit them atomically through the S0-01
     executor with the shared dormancy and dedup values; an illegal program rolls back the whole
     frame -- the memory AND the arm's temporal state -- the frame then commits an EMPTY program
     (tick advances, maintenance runs) and the failure is counted (D-224-X, METHOD section 6
     step 6); NoVersion deletes retracted entities after the commit;
  8. the frame receipt: seals, recall, assignment, decisions, atoms, the memory digests before and
     after, the sparse frame delta, and the cache frame seal it consumed.

After both seals exist, the private side may build the evaluator's truth table for the frame
(``TruthTableBuilder``): every private key seen so far, ``present`` from the S1-04 truth tracker,
``in_scope`` from the S0-04 rule (observable at least once since the episode start, not a
structural type), boxes for present in-scope objects.

白话：这是五个臂共用的"每帧走一遍"的流程。输入是 cache 的一帧（色块、公开体积）和上一帧的记忆，
输出是这一帧的原子程序、提交后的新记忆和一份回执。例如一帧里三个色块：先算旧记忆里每个实体"本帧
应该能看到多少、被可靠深度射线穿过多少"，把 ViT-B/14 描述子投影成 128 维，按冻结规则召回候选并封
存，臂给出每格的 logit，解一次矩形分配，再封存分配与存在特征，臂再对"应可见却没匹配"的实体判
RETRACT/NOOP，最后编译成原子一次提交。程序非法就整帧回滚，这一帧改提交空程序并计一次，避免整条
episode 卡死。它不训练、不读私有文件、不算任何论文指标；臂之间只有 logit 与词表不同。
"""

from __future__ import annotations

import hashlib
import math
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from cpmt.hashing import canonical_json, clone_json

from vsmt import lean_arms as arms
from vsmt import lean_assignment as la
from vsmt import lean_frontend_cache as fc
from vsmt import lean_memory as lm
from vsmt import lean_teacher as lt

CONTRACT_SCHEMA_VERSION = "vsmt-lean-s2-01-runner-v1"
STAGE_ID = "S2-01"

#: The two descriptor choices a run may use: the S1-05 selection and the frozen baseline the paper
#: must report alongside.  Anything else is refused.
DESCRIPTOR_CHOICES = (la.SELECTED_DESCRIPTOR, la.FROZEN_DESCRIPTOR_BASELINE)
PROJECTION_PREFIX = "reid_projection:"

#: Entity geometry rule (METHOD section 5, S2-01), ruling 74 (2026-09-26): the per-point depth test.
#: Every cell centre of a uniform grid over the entity AABB is projected into this frame's public depth
#: image (public intrinsics, causal public pose, the frozen back-projection's convention inverted); with
#: its axial depth z and the depth d measured at its pixel it is seen through when d > z + margin, on the
#: surface when |d - z| <= margin, occluded when d < z - margin, unobserved outside the image or on an
#: invalid depth.  should_be_visible_ratio = (seen through + on surface) / points;
#: free_space_coverage_ratio = seen through / (seen through + on surface), 0 when nothing is observed.
#: The block-frustum rule it replaces (LOG-260, LOG-261: it saw the entity box in about 3 percent of
#: entity-frames, gone-above-present AUC 0.57) is kept as ``entity_geometry_blocks`` for diagnostics only.
ENTITY_GEOMETRY_RULE = (
    "the entity's surface points (the fragments of its latest observed frame, up to max_points each) projected into "
    "the public depth image; seen_through d > z + margin, on_surface |d - z| <= margin, occluded d < z - margin, "
    "unobserved outside the image or invalid depth; should_be_visible_ratio = (seen_through + on_surface) / points; "
    "free_space_coverage_ratio = seen_through / (seen_through + on_surface), 0 when none is observed"
)
#: Ruling 75 (2)(a) (2026-09-26): the points tested are the entity's own last-observed surface, as Khronos tests the
#: object's surface points against the rays of a later view, not the AABB interior -- a single-frame box is mostly
#: empty space, so a present object's box read as seen through (LOG-261, calibration 253d6bd).  A fragment's surface
#: points are its mask pixels with valid public depth, back-projected with the causal pose, and subsampled to
#: FRAGMENT_SURFACE_MAX_POINTS evenly in row-major pixel order; an entity's points are those of the fragments of its
#: evidence at its last_seen_tick -- the same set its box is the union of (ENTITY_BOX_RULE), so a same-frame merge
#: unions them and a later frame replaces them.  The AABB grid stays the yardstick for a truth place (the teacher's
#: place_observable), which has no surface of its own.
FRAGMENT_SURFACE_MAX_POINTS = 64
FRAGMENT_SURFACE_RULE = ("mask_pixels_with_valid_public_depth_back_projected_with_the_causal_pose; "
                         "subsampled_to_max_points_at_evenly_spaced_row_major_pixel_indices")
#: Ruling 74: the margin, frozen at the best of the three probed values (0.05 / 0.10 / 0.20 m).
DEPTH_MARGIN_M = 0.05
#: The valid depth range is the frozen D-223 free-space configuration's (minimum_depth_m, maximum_valid_depth_m).
DEPTH_VALID_RANGE_M = (0.05, 20.0)
#: The key under which a reader attaches the frame's public depth view after the seal check.
PUBLIC_DEPTH_VIEW_KEY = "public_depth_view"
PUBLIC_DEPTH_VIEW_FIELDS = ("frame_digest", "depth_m", "calibration", "pose", "fragment_surface_points")
HALFSPACE_TOLERANCE_M = 1e-9
#: The registered sampling resolution (points per axis): D-224-S1 ruling 60 (2026-09-24) froze
#: it at 4, i.e. 64 cell centres per entity and a ratio granularity of 1/64.  The contract's value
#: slot carries the same number and the validator refuses any other; the ops entry still reads the
#: contract, so the constant here only binds the two together.
ENTITY_GEOMETRY_SAMPLES_PER_AXIS: int | None = 4

#: Illegal-program rule (D-224-X, METHOD section 6 step 6).
ILLEGAL_PROGRAM_RULE = (
    "an_illegal_program_rolls_back_the_whole_frame_then_the_frame_commits_an_empty_program_"
    "tick_advances_dormancy_and_dedup_run_and_the_failure_is_counted_per_episode"
)

#: Truth-table rules (S0-04 node scope, D-224-S1 ruling 56 continued; S2-01 makes them machine form).
OBSERVABLE_MIN_PIXELS = fc.MINIMUM_VISIBLE_PIXELS
TRUTH_TABLE_OBSERVABLE_RULE = (
    "an_object_has_been_observable_once_its_private_instance_mask_reached_at_least_196_pixels_"
    "in_some_frame_up_to_t"
)
TRUTH_TABLE_KEY_RULE = (
    "every_private_key_seen_in_any_frame_up_to_t_is_a_row; a key in the geometry table takes present "
    "and box from the truth tracker; a structural key (Ceiling_room, door, room, wall, window) is present "
    "and out of scope without a box; a spawned-after-reload key (last field a spawn tag) is present and "
    "out of scope without a box and counted; any other key outside the geometry table fails the episode"
)

#: Where the runner's policy values come from.  None is defined here.
POLICY_INPUT_SOURCES = {
    "dormancy_missed_opportunity_limit": "S0-01 shared_dormancy.dormancy_missed_opportunity_limit",
    "dedup": "S0-01 shared_dedup.{period_ticks,descriptor_cosine_min,centroid_distance_max_m,aabb_iou_min}",
    "should_be_visible_min_ratio": "S0-05 shared.should_be_visible_min_ratio",
    "entity_geometry_samples_per_axis": "S2-01 entity_geometry.samples_per_axis",
    "recall": "S0-03 recall_rule (frozen: rulings 57/58)",
    "descriptor": "S0-03 reid_adapter_head.selection_result (frozen: S1-05)",
}
POLICY_FIELDS = (
    "dormancy_missed_opportunity_limit", "dedup", "should_be_visible_min_ratio",
    "entity_geometry_samples_per_axis",
)

#: Arms this runner drives.  LLM-op is validation-only and has its own entry (S2-02 interface,
#: not called in S2); it is refused here.
LEARNED_ARMS = tuple(arm for arm in arms.LEARNED_ARMS)
RULE_ARMS = tuple(arms.RULE_ARMS)
RUNNABLE_ARMS = tuple(arm for arm in arms.ALL_ARMS if arm != arms.APPENDIX_ARM)
#: Configuration fields each arm needs, all without defaults.  ELU-P adds its three fitted scalars.
ARM_CONFIG_FIELDS: dict[str, tuple[str, ...]] = {
    **{arm: arms.GRID_PARAMETERS[arm] for arm in RUNNABLE_ARMS},
    "ELU-P": (*arms.GRID_PARAMETERS["ELU-P"], *arms.ELU_P_FITTED),
}
#: A distance-gate parameter may legitimately be None (no gate); every other field must be a value.
NULLABLE_CONFIG_FIELDS = {arm: (name,) for arm, name in arms.NO_GATE_PARAMETER.items()}

FAILURE_REASONS = (
    "descriptor_choice_not_frozen",
    "reid_weights_digest_not_the_frozen_one",
    "policy_value_missing",
    "arm_not_runnable_here",
    "arm_config_missing",
    "scorer_missing_for_learned_arm",
    "cache_frame_malformed",
    "truth_key_outside_geometry_table",
    "truth_object_without_box",
)


class LeanRunnerError(ValueError):
    """Raised with a short machine-readable code."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LeanRunnerError(code)


def _finite(value: Any, code: str) -> float:
    _require(type(value) in {int, float} and type(value) is not bool, code)
    result = float(value)
    _require(math.isfinite(result), code)
    return result


def _int(value: Any, code: str, *, minimum: int | None = None) -> int:
    _require(type(value) is int and type(value) is not bool, code)
    if minimum is not None:
        _require(value >= minimum, code)
    return value


def sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# 1. entity geometry: a pure function of (public volumes, M_{t-1})
# --------------------------------------------------------------------------

def _blocks(records: Sequence[Mapping[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    """Normals (B, 6, 3) and offsets (B, 6) of the frame's volume blocks."""

    normals = np.zeros((len(records), 6, 3), dtype=np.float64)
    offsets = np.zeros((len(records), 6), dtype=np.float64)
    for b, record in enumerate(records):
        planes = record["halfspaces_world"]
        _require(len(planes) == 6, "cache_frame_malformed")
        for h, plane in enumerate(planes):
            normal = [float(v) for v in plane["normal"]]
            _require(len(normal) == 3, "cache_frame_malformed")
            normals[b, h, :] = normal
            offsets[b, h] = float(plane["offset_m"])
    return normals, offsets


def sample_points(lower: Sequence[float], upper: Sequence[float], *, samples_per_axis: int) -> np.ndarray:
    """Cell centres of a uniform ``s x s x s`` grid over the box; a flat axis yields its single coordinate."""

    s = _int(samples_per_axis, "samples_per_axis_invalid", minimum=1)
    lo = np.asarray([float(v) for v in lower], dtype=np.float64)
    hi = np.asarray([float(v) for v in upper], dtype=np.float64)
    _require(lo.shape == (3,) and hi.shape == (3,) and bool(np.all(lo <= hi)), "entity_box_invalid")
    steps = (np.arange(s, dtype=np.float64) + 0.5) / float(s)
    axes = [lo[k] + steps * (hi[k] - lo[k]) for k in range(3)]
    grid = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 3)
    return grid


_PLANE_TRIPLES = np.asarray([(a, b, c) for a in range(6) for b in range(a + 1, 6) for c in range(b + 1, 6)])
BLOCK_AABB_MARGIN_M = 1e-6


def block_aabbs(normals: np.ndarray, offsets: np.ndarray, *, margin: float = BLOCK_AABB_MARGIN_M) -> tuple[np.ndarray, np.ndarray]:
    """Axis-aligned bounds of every convex six-plane block, from its feasible plane-triple vertices, padded by ``margin``.

    Engineering (S2-05 profiling, LOG-254): testing every sample point of every entity against every
    block of the frame took a fifth of the per-frame time.  A block is the convex hull of its
    vertices, so a point inside it (within the 1e-9 m tolerance) lies inside the block's exact
    bounding box padded by far less than the margin; ``entity_geometry`` therefore tests only the
    blocks whose padded box meets the entity box and gets the same ratio to the last bit.  A block
    without four feasible vertices is left unbounded (no filtering) so the fallback is always safe.
    """

    count = int(normals.shape[0])
    if count == 0:
        return np.zeros((0, 3)), np.zeros((0, 3))
    matrices = normals[:, _PLANE_TRIPLES, :]  # (B, 20, 3, 3)
    rhs = offsets[:, _PLANE_TRIPLES]  # (B, 20, 3)
    determinant = np.linalg.det(matrices)
    solvable = np.abs(determinant) > 1e-12
    vertices = np.full((count, _PLANE_TRIPLES.shape[0], 3), np.nan)
    if solvable.any():
        vertices[solvable] = np.linalg.solve(matrices[solvable], rhs[solvable][:, :, None])[:, :, 0]
    with np.errstate(invalid="ignore"):
        lhs = np.einsum("bkj,bvj->bvk", normals, vertices)  # (B, 20, 6)
        feasible = solvable & np.all(lhs <= offsets[:, None, :] + 1e-6, axis=2)
    lower = np.where(feasible[:, :, None], vertices, np.inf).min(axis=1) - margin
    upper = np.where(feasible[:, :, None], vertices, -np.inf).max(axis=1) + margin
    unbounded = feasible.sum(axis=1) < 4
    lower[unbounded] = -np.inf
    upper[unbounded] = np.inf
    return lower, upper


def inside_union_fraction(points: np.ndarray, normals: np.ndarray, offsets: np.ndarray) -> float:
    """Share of ``points`` inside the union of the blocks; 0.0 when there is no block.

    The dot products are explicit per-coordinate multiply-adds in a fixed order, not a BLAS matmul,
    so the same frame and memory give the same ratio on every machine (the S1-03 digests once moved
    by one ULP between BLAS builds; a boundary point must not flip between platforms).
    """

    if normals.shape[0] == 0 or points.shape[0] == 0:
        return 0.0
    # (B, P, 6): n . p for every block, point and halfspace
    lhs = (normals[:, None, :, 0] * points[None, :, None, 0]
           + normals[:, None, :, 1] * points[None, :, None, 1]
           + normals[:, None, :, 2] * points[None, :, None, 2])
    inside_block = np.all(lhs <= offsets[:, None, :] + HALFSPACE_TOLERANCE_M, axis=2)  # (B, P)
    inside_any = np.any(inside_block, axis=0)  # (P,)
    return float(int(inside_any.sum())) / float(points.shape[0])


def entity_geometry_blocks(
    memory: Mapping[str, Any], cache_frame: Mapping[str, Any], *, samples_per_axis: int | None,
) -> dict[str, dict[str, float]]:
    """The superseded block-frustum ratios (diagnostics only since ruling 74; the runner never calls it).

    白话：裁决 74 之前的算法：包围盒采样点落进本帧可见体积块、自由空间块并集的比例。块视锥为了保守，
    在每个 14×14 像素块里取最近深度再退 10 cm，放在桌上的小物体原位置几乎永远算不进去（LOG-260）。
    只留给探针与审计做新旧对照。
    """

    _require(samples_per_axis is not None, "policy_value_missing:entity_geometry_samples_per_axis")
    s = _int(samples_per_axis, "samples_per_axis_invalid", minimum=1)
    volumes = []
    for records in (cache_frame["visibility"], cache_frame["free_space"]):
        normals, offsets = _blocks(records)
        volumes.append((normals, offsets, *block_aabbs(normals, offsets)))
    out: dict[str, dict[str, float]] = {}
    for entity in sorted(memory["entities"], key=lambda item: str(item["entity_id"])):
        lower = np.asarray([float(v) for v in entity["aabb_min_m"]], dtype=np.float64)
        upper = np.asarray([float(v) for v in entity["aabb_max_m"]], dtype=np.float64)
        points = sample_points(lower, upper, samples_per_axis=s)
        ratios = []
        for normals, offsets, block_lower, block_upper in volumes:
            # only blocks whose padded box meets the entity box can contain a sample point (see block_aabbs)
            candidates = np.all(block_lower <= upper[None, :], axis=1) & np.all(block_upper >= lower[None, :], axis=1)
            ratios.append(inside_union_fraction(points, normals[candidates], offsets[candidates]))
        out[str(entity["entity_id"])] = {"should_be_visible_ratio": ratios[0], "free_space_coverage_ratio": ratios[1]}
    return out


def point_depth_counts(points_world: np.ndarray, depth_view: Mapping[str, Any], *,
                       margin_m: float = DEPTH_MARGIN_M) -> dict[str, np.ndarray]:
    """Per-entity counts of seen-through / on-surface / occluded / unobserved points (points_world is (E, P, 3)).

    The camera convention is the frozen back-projection's (``l1_entities.backproject_public_entity_geometry``)
    inverted: world = R @ camera + position, camera +x right, +y up, +z forward, u = cx + fx x / z,
    v = cy - fy y / z, pixel = (round(v), round(u)).  The rotation is applied as explicit per-coordinate
    multiply-adds in a fixed order, not a BLAS matmul, so a point on the margin cannot flip between machines.
    """

    from vsmt.l1_entities import _camera_values

    depth = np.asarray(depth_view["depth_m"])
    _require(depth.ndim == 2 and np.issubdtype(depth.dtype, np.floating), "public_depth_view_malformed")
    fx, fy, cx, cy, position, rotation = _camera_values(depth_view["calibration"], depth_view["pose"])
    points = np.asarray(points_world, dtype=np.float64)
    _require(points.ndim == 3 and points.shape[-1] == 3, "entity_points_malformed")
    d = [points[..., k] - position[k] for k in range(3)]
    # camera_j = sum_k R[k, j] * d_k (R^T d), in a fixed order
    x = d[0] * rotation[0, 0] + d[1] * rotation[1, 0] + d[2] * rotation[2, 0]
    y = d[0] * rotation[0, 1] + d[1] * rotation[1, 1] + d[2] * rotation[2, 1]
    z = d[0] * rotation[0, 2] + d[1] * rotation[1, 2] + d[2] * rotation[2, 2]
    height, width = depth.shape
    minimum, maximum = DEPTH_VALID_RANGE_M
    ahead = z >= minimum  # ruling 76 (4)(a): the same closed range as the measured depth
    safe_z = np.where(ahead, z, 1.0)
    column = np.rint(np.where(ahead, cx + fx * x / safe_z, -1.0)).astype(np.int64)
    row = np.rint(np.where(ahead, cy - fy * y / safe_z, -1.0)).astype(np.int64)
    in_image = ahead & (column >= 0) & (column < width) & (row >= 0) & (row < height)
    measured = np.full(z.shape, np.nan)
    measured[in_image] = depth[row[in_image], column[in_image]]
    valid = in_image & np.isfinite(measured) & (measured >= minimum) & (measured <= maximum)
    through = valid & (measured > z + margin_m)
    surface = valid & (np.abs(measured - z) <= margin_m)
    occluded = valid & (measured < z - margin_m)
    return {"through": through.sum(axis=1), "surface": surface.sum(axis=1), "occluded": occluded.sum(axis=1),
            "unobserved": (~valid).sum(axis=1), "points": np.full(points.shape[0], points.shape[1])}


def public_depth_view_of(cache_frame: Mapping[str, Any]) -> Mapping[str, Any]:
    """The frame's public depth view, refused when missing, malformed or of another frame."""

    view = cache_frame.get(PUBLIC_DEPTH_VIEW_KEY)
    _require(isinstance(view, Mapping), "public_depth_view_missing")
    _require(tuple(view) == PUBLIC_DEPTH_VIEW_FIELDS, "public_depth_view_malformed")
    _require(str(view["frame_digest"]) == str(cache_frame["frame_digest"]), "public_depth_view_of_another_frame")
    return view


def fragment_surface_points(mask: Any, depth_view: Mapping[str, Any], *,
                            max_points: int = FRAGMENT_SURFACE_MAX_POINTS) -> list[list[float]]:
    """Ruling 75 (2)(a): a fragment's surface points -- its mask pixels with valid public depth, back-projected.

    白话：色块的"表面点"就是它 mask 里深度有效的像素反投影到世界坐标，按行优先像素顺序等间隔取至多 64 个。
    它只用公开深度、内参、因果位姿和匿名 mask，与冻结反投影同一约定；一个像素都没有有效深度时返回空。
    """

    from vsmt.l1_entities import _camera_values

    binary = np.asarray(mask, dtype=bool)
    depth = np.asarray(depth_view["depth_m"], dtype=np.float64)
    _require(binary.shape == depth.shape, "fragment_mask_shape_differs_from_depth")
    minimum, maximum = DEPTH_VALID_RANGE_M
    valid = binary & np.isfinite(depth) & (depth >= minimum) & (depth <= maximum)
    rows, columns = np.nonzero(valid)
    if rows.size == 0:
        return []
    count = min(int(max_points), int(rows.size))
    keep = np.unique(np.floor(np.linspace(0, rows.size - 1, count)).astype(np.int64))
    rows, columns = rows[keep], columns[keep]
    fx, fy, cx, cy, position, rotation = _camera_values(depth_view["calibration"], depth_view["pose"])
    z = depth[rows, columns]
    x = (columns.astype(np.float64) - cx) * z / fx
    y = (cy - rows.astype(np.float64)) * z / fy
    world = [rotation[k, 0] * x + rotation[k, 1] * y + rotation[k, 2] * z + position[k] for k in range(3)]
    return [[float(world[0][i]), float(world[1][i]), float(world[2][i])] for i in range(len(z))]


def entity_surface_points(memory: Mapping[str, Any], store: Mapping[str, Sequence[Sequence[float]]]) -> dict[str, list[list[float]]]:
    """Each entity's surface points: those of the fragments of its evidence at its last_seen_tick (ruling 75)."""

    out: dict[str, list[list[float]]] = {}
    for entity in memory["entities"]:
        latest = int(entity["last_seen_tick"])
        points: list[list[float]] = []
        for item in entity["evidence"]:
            if int(item["tick"]) == latest:
                points.extend(store.get(f"{item['frame_digest']}|{item['fragment_id']}", []))
        out[str(entity["entity_id"])] = points
    return out


def updated_surface_store(store: Mapping[str, Any], memory_after: Mapping[str, Any], depth_view: Mapping[str, Any]) -> dict[str, Any]:
    """This frame's fragment points added, then only the fragments some entity's latest evidence still names kept."""

    merged = dict(store)
    digest = str(depth_view["frame_digest"])
    for fragment_id, points in depth_view["fragment_surface_points"].items():
        merged[f"{digest}|{fragment_id}"] = points
    wanted = {f"{item['frame_digest']}|{item['fragment_id']}" for entity in memory_after["entities"]
              for item in entity["evidence"] if int(item["tick"]) == int(entity["last_seen_tick"])}
    return {key: merged[key] for key in sorted(wanted) if key in merged}


def entity_geometry(
    memory: Mapping[str, Any], depth_view: Mapping[str, Any], *, samples_per_axis: int | None,
    margin_m: float = DEPTH_MARGIN_M, surface_points: Mapping[str, Sequence[Sequence[float]]] | None = None,
) -> dict[str, dict[str, float]]:
    """The two S0-03 ratios for every entity of M_{t-1}, by the per-point depth test (ruling 74).

    白话：输入上一帧的记忆和本帧的公开深度视图（深度图、内参、因果位姿），输出每个实体两个比例。把实体
    包围盒上 64 个采样点逐个投到深度图上：测到的深度比点远出 5 cm 叫"看穿"（那里是空的），差不多远叫"在
    表面"，更近叫"被挡"，出画或深度无效叫"看不到"。应可见比例＝（看穿＋在表面）／64；自由空间覆盖＝看穿／
    （看穿＋在表面），一个点都没看到时记 0。例如杯子被拿走后相机再看桌面，原位置的点测到的是后面的墙，
    全部看穿，覆盖为 1；杯子还在时只看到它朝相机的表面，其余点被自己挡住，覆盖为 0。它只读公开深度、内参
    与位姿和记忆，五个臂拿到逐字节相同的函数；它不等于读私有真值，也不改 cache。
    """

    _require(samples_per_axis is not None, "policy_value_missing:entity_geometry_samples_per_axis")
    s = _int(samples_per_axis, "samples_per_axis_invalid", minimum=1)
    entities = sorted(memory["entities"], key=lambda item: str(item["entity_id"]))
    out: dict[str, dict[str, float]] = {}
    if not entities:
        return out
    if surface_points is None:  # a truth place (teacher): the AABB grid
        groups = [sample_points(e["aabb_min_m"], e["aabb_max_m"], samples_per_axis=s) for e in entities]
    else:  # an entity (ruling 75 (2)(a)): its own last-observed surface points
        groups = [np.asarray(surface_points.get(str(e["entity_id"])) or np.zeros((0, 3)), dtype=np.float64).reshape(-1, 3)
                  for e in entities]
    for entity, points in zip(entities, groups):
        if points.shape[0] == 0:  # no surface with valid depth: nothing can be observed
            out[str(entity["entity_id"])] = {"should_be_visible_ratio": 0.0, "free_space_coverage_ratio": 0.0}
            continue
        counts = point_depth_counts(points[None], depth_view, margin_m=margin_m)
        observed = int(counts["through"][0] + counts["surface"][0])
        total = int(counts["points"][0])
        out[str(entity["entity_id"])] = {
            "should_be_visible_ratio": observed / total,
            "free_space_coverage_ratio": (int(counts["through"][0]) / observed) if observed else 0.0,
        }
    return out


# --------------------------------------------------------------------------
# 2. the descriptor S1-05 froze
# --------------------------------------------------------------------------

def descriptor_projector(weights_payload: Mapping[str, Any], *, expected_sha256: str, device: str = "cpu") -> Callable[[Sequence[Sequence[float]]], list[list[float]]]:
    """A callable projecting frozen descriptors through the shared ReID head, digest-checked first.

    白话：输入 S1-04 写出的权重文件内容和冻结的摘要，输出一个"把 768 维描述子投成 128 维单位向量"的
    函数；摘要对不上直接拒绝，因为五个臂必须用同一份权重。它不训练。
    """

    from vsmt import lean_reid_head as rh

    _require(type(expected_sha256) is str and len(expected_sha256) == 64, "reid_weights_digest_not_the_frozen_one")
    _require(weights_payload.get("sha256") == expected_sha256, "reid_weights_digest_not_the_frozen_one")
    head = rh.load_head(weights_payload, device=device)

    def project(descriptors: Sequence[Sequence[float]]) -> list[list[float]]:
        if not descriptors:
            return []
        projected = rh.project_with(head, np.asarray(descriptors, dtype=np.float32))
        return [[float(v) for v in row] for row in np.asarray(projected)]

    return project


def source_set_of(descriptor: str) -> str:
    """Which cache descriptor set a descriptor choice reads."""

    _require(descriptor in DESCRIPTOR_CHOICES, "descriptor_choice_not_frozen")
    if descriptor.startswith(PROJECTION_PREFIX):
        source = descriptor[len(PROJECTION_PREFIX):]
        _require(source == la.SELECTED_DESCRIPTOR_SOURCE_SET, "descriptor_choice_not_frozen")
        return source
    return descriptor


def assignment_frame(
    cache_frame: Mapping[str, Any], *, descriptor: str,
    projector: Callable[[Sequence[Sequence[float]]], list[list[float]]] | None,
    entity_geometry_by_id: Mapping[str, Mapping[str, float]],
) -> dict[str, Any]:
    """The S0-03 view of one cache frame under the frozen descriptor choice, with entity geometry injected."""

    source = source_set_of(descriptor)
    view = fc.assignment_view(cache_frame, descriptor_set=source, entity_geometry=entity_geometry_by_id)
    if descriptor.startswith(PROJECTION_PREFIX):
        _require(projector is not None, "projector_required_for_the_selected_descriptor")
        projected = projector([fragment["descriptor"] for fragment in view["fragments"]])
        _require(len(projected) == len(view["fragments"]), "projector_returned_wrong_count")
        for fragment, row in zip(view["fragments"], projected):
            _require(len(row) == la.REID_OUTPUT_DIMENSION, "projector_returned_wrong_dimension")
            fragment["descriptor"] = [float(v) for v in row]
    else:
        _require(projector is None, "projector_given_for_a_frozen_descriptor")
    return la.validate_cache_frame(view)


# --------------------------------------------------------------------------
# 3. policy values and arm configurations: explicit, no defaults
# --------------------------------------------------------------------------

def validate_policy(policy: Mapping[str, Any]) -> dict[str, Any]:
    """Every shared value the runner needs, present and in range; None anywhere is refused."""

    _require(type(policy) is dict and set(policy) == set(POLICY_FIELDS), "policy_fields_invalid")
    for name in POLICY_FIELDS:
        _require(policy[name] is not None, f"policy_value_missing:{name}")
    limit = _int(policy["dormancy_missed_opportunity_limit"], "policy_value_missing:dormancy_missed_opportunity_limit", minimum=1)
    dedup = lm.validate_dedup_policy(policy["dedup"])
    ratio = _finite(policy["should_be_visible_min_ratio"], "policy_value_missing:should_be_visible_min_ratio")
    _require(0.0 < ratio <= 1.0, "policy_value_missing:should_be_visible_min_ratio")
    samples = _int(policy["entity_geometry_samples_per_axis"], "policy_value_missing:entity_geometry_samples_per_axis", minimum=1)
    return {"dormancy_missed_opportunity_limit": limit, "dedup": dedup, "should_be_visible_min_ratio": ratio,
            "entity_geometry_samples_per_axis": samples}


def validate_arm_config(arm: str, config: Mapping[str, Any]) -> dict[str, Any]:
    """The arm's registered parameters, all given (a distance gate may be None: no gate)."""

    _require(arm in RUNNABLE_ARMS, f"arm_not_runnable_here:{arm}")
    fields = ARM_CONFIG_FIELDS[arm]
    _require(type(config) is dict and set(config) == set(fields), f"arm_config_missing:{arm}")
    nullable = set(NULLABLE_CONFIG_FIELDS.get(arm, ()))
    for name in fields:
        if config[name] is None:
            _require(name in nullable, f"arm_config_missing:{arm}:{name}")
    return dict(config)


# --------------------------------------------------------------------------
# 4. one frame
# --------------------------------------------------------------------------

def initial_state(*, episode_id: str, arm: str) -> dict[str, Any]:
    """M_0 plus the arm's empty temporal state and zeroed counters."""

    _require(arm in RUNNABLE_ARMS, f"arm_not_runnable_here:{arm}")
    return {
        "arm": arm,
        "memory": lm.empty_memory(episode_id=episode_id),
        "arm_state": {},
        "counters": {"frames": 0, "illegal_programs": 0, "atoms": {atom: 0 for atom in lm.ATOMS},
                     "existence_candidates": 0, "excluded_not_visible": 0, "excluded_retracted": 0,
                     "no_version_deleted": 0},
        "cache_frame_seals": [],
        "surface_points": {},
    }


def _association_logits(arm: str, config: Mapping[str, Any], stage_a: Mapping[str, Any], scorer: Any) -> dict[str, Any]:
    if arm in ("TAF", "ELU-P", "RAC"):
        return arms.gate_association_logits(stage_a, theta_a=config["theta_a"], d_a=config["d_a"],
                                            reactivates_retracted=arms.REACTIVATES_RETRACTED[arm])
    if arm == "LOW":
        return arms.low_association_logits(stage_a, d_low=config["d_low"])
    if arm == "HandCost":
        return arms.hand_cost_association_logits(stage_a, theta_b=config["theta_b"])
    _require(scorer is not None, f"scorer_missing_for_learned_arm:{arm}")
    logits = scorer.association_and_birth_logits(stage_a)
    _require(set(logits) == {"association_logits", "birth_logits"}, "scorer_logits_malformed")
    expected_pairs = {f"{row['fragment_id']}|{row['entity_id']}" for row in stage_a["association_rows"]}
    _require(set(logits["association_logits"]) == expected_pairs, "scorer_association_logits_do_not_match_the_sealed_rows")
    _require(set(logits["birth_logits"]) == set(stage_a["rows"]), "scorer_birth_logits_do_not_match_the_sealed_rows")
    return {"association_logits": {k: _finite(v, "association_logit_invalid") for k, v in logits["association_logits"].items()},
            "birth_logits": {k: _finite(v, "birth_logit_invalid") for k, v in logits["birth_logits"].items()}}


def _existence(arm: str, config: Mapping[str, Any], eligible: Sequence[Mapping[str, Any]], order: Sequence[str],
               arm_state: Mapping[str, Any], scorer: Any) -> tuple[dict[str, str], dict[str, Any]]:
    state = clone_json(dict(arm_state))
    if arm in ("TAF", "LOW"):
        return arms.never_retract(eligible), state
    if arm == "AssocOnly":
        return arms.skip_existence(eligible), state
    if arm == "ELU-P":
        result = arms.elu_p_existence(
            eligible, order, state=state.get("log_odds", {}),
            initial_log_odds=config["initial_log_odds"],
            persistence_log_decay_per_tick=config["persistence_log_decay_per_tick"],
            free_space_weight=config["free_space_weight"], retract_threshold=config["retract_threshold"])
        state["log_odds"] = result["state"]
        return result["decisions"], state
    if arm == "RAC":
        result = arms.rac_existence(eligible, order, state=state.get("negative_renders", {}),
                                    rho_rac=config["rho_rac"], n_rac=config["n_rac"])
        state["negative_renders"] = result["state"]
        return result["decisions"], state
    if arm == "HandCost":
        return arms.hand_cost_existence(eligible, order, rho_h=config["rho_h"]), state
    _require(scorer is not None, f"scorer_missing_for_learned_arm:{arm}")
    logits = scorer.existence_logits(eligible, order)
    _require(set(logits) == {str(row["entity_id"]) for row in eligible}, "scorer_existence_logits_do_not_match_the_eligible_rows")
    return arms.learned_existence(logits, tau_r=config["tau_r"]), state


def _observe_matches(arm: str, config: Mapping[str, Any], arm_state: dict[str, Any], matched: Sequence[str]) -> dict[str, Any]:
    if arm == "ELU-P":
        arm_state["log_odds"] = arms.elu_p_observe_matches(
            arm_state.get("log_odds", {}), matched, initial_log_odds=config["initial_log_odds"], match_gain=config["match_gain"])
    elif arm == "RAC":
        arm_state["negative_renders"] = arms.rac_observe_matches(arm_state.get("negative_renders", {}), matched)
    return arm_state


def _prune_arm_state(arm_state: dict[str, Any], entity_ids: set[str]) -> dict[str, Any]:
    return {name: {key: value for key, value in table.items() if key in entity_ids} for name, table in arm_state.items()}


def _fragment_for_executor(fragment: Mapping[str, Any]) -> dict[str, Any]:
    return {name: clone_json(fragment[name]) for name in sorted(lm.FRAGMENT_FIELDS)}


def compile_frame_program(
    operations: Sequence[Mapping[str, Any]], view: Mapping[str, Any], *, association_logits: Mapping[str, float],
    birth_logits: Mapping[str, float], geometry: Mapping[str, Mapping[str, float]], arm: str,
) -> dict[str, Any]:
    """Attach the fragment records and a small decision basis to the compiled atoms."""

    fragments = {str(f["fragment_id"]): f for f in view["fragments"]}
    program_ops: list[dict[str, Any]] = []
    for op in operations:
        atom = op["atom"]
        record: dict[str, Any] = {"atom": atom}
        if atom in ("BIND", "REACTIVATE", "BIRTH"):
            fragment_id = str(op["fragment_id"])
            record["fragment"] = _fragment_for_executor(fragments[fragment_id])
            if atom == "BIRTH":
                record["decision_basis"] = {"arm": arm, "birth_logit": float(birth_logits[fragment_id])}
            else:
                record["entity_id"] = str(op["entity_id"])
                record["decision_basis"] = {"arm": arm, "association_logit": float(association_logits[f"{fragment_id}|{op['entity_id']}"])}
        else:
            entity_id = str(op["entity_id"])
            record["entity_id"] = entity_id
            g = geometry[entity_id]
            record["decision_basis"] = {"arm": arm, "should_be_visible_ratio": float(g["should_be_visible_ratio"]),
                                        "free_space_coverage_ratio": float(g["free_space_coverage_ratio"])}
        program_ops.append(record)
    return {"frame_digest": str(view["frame_digest"]), "operations": program_ops}


def run_frame(
    state: Mapping[str, Any], cache_frame: Mapping[str, Any], *, arm: str, config: Mapping[str, Any],
    policy: Mapping[str, Any], descriptor: str,
    projector: Callable[[Sequence[Sequence[float]]], list[list[float]]] | None = None, scorer: Any = None,
) -> dict[str, Any]:
    """One frame for one arm: the eight steps of the module docstring, returning the new state and a receipt.

    白话：输入上一帧的状态（记忆、臂的时间状态、计数）和 cache 的一帧，输出新状态、这一帧的回执，以及
    S0-03 的两份封存（teacher 之后要用）。例如 TAF 在这一帧把两个色块绑到旧实体、一个新建，对一个应可见
    却没匹配的实体记 NOOP。任何一步用到的登记值都必须由调用方给出，None 直接拒绝。
    """

    checked_policy = validate_policy(policy)
    checked_config = validate_arm_config(arm, config)
    _require(state["arm"] == arm, "state_belongs_to_another_arm")
    memory = state["memory"]
    tick = int(cache_frame["tick"])
    _require(tick == int(memory["tick"]) + 1, "frame_tick_not_next")

    # 1-2. entity geometry by the per-point depth test (ruling 74) on this frame's public depth view and
    # M_{t-1}; the view under the frozen descriptor
    depth_view = public_depth_view_of(cache_frame)
    _require(sorted(depth_view["fragment_surface_points"]) == sorted(str(f["fragment_id"]) for f in cache_frame["fragments"]),
             "public_depth_view_surface_points_do_not_match_the_fragments")
    geometry = entity_geometry(memory, depth_view, samples_per_axis=checked_policy["entity_geometry_samples_per_axis"],
                               surface_points=entity_surface_points(memory, state.get("surface_points", {})))
    view = assignment_frame(cache_frame, descriptor=descriptor, projector=projector, entity_geometry_by_id=geometry)

    # 3. stage A
    stage_a = la.build_assignment_inputs(
        view, memory, local_count=la.RECALL_LOCAL_COUNT, global_count=la.RECALL_GLOBAL_COUNT,
        local_radius_m=la.RECALL_LOCAL_RADIUS_M, birth_neighbourhood_radius_m=la.RECALL_BIRTH_NEIGHBOURHOOD_RADIUS_M)

    # 4. logits and the solve
    logits = _association_logits(arm, checked_config, stage_a, scorer)
    solution = la.solve_frame(stage_a, association_logits=logits["association_logits"], birth_logits=logits["birth_logits"])
    if arm in RULE_ARMS:
        arms.assert_no_sentinel_chosen(solution["assignment"], logits["association_logits"])

    # 5. stage B and the private gate
    stage_b = la.seal_solution_and_existence(solution, view, memory, inputs=stage_a)
    gate = lt.build_private_gate(stage_a, stage_b)

    # 6. existence decisions on the eligible rows, with the arm's temporal state
    order = stage_b["existence_feature_order"]
    if arm == "AssocOnly":
        # the existence step is skipped entirely (S0-05): no candidates, no NOOP, hence no dormancy
        filtered: dict[str, Any] = {"eligible": [], "excluded_not_visible": [], "excluded_retracted": []}
    else:
        filtered = arms.eligible_existence_rows(stage_b["existence_rows"], order,
                                               visible_min_ratio=checked_policy["should_be_visible_min_ratio"])
    decisions, arm_state = _existence(arm, checked_config, filtered["eligible"], order, state["arm_state"], scorer)
    matched = sorted(str(column) for column in solution["assignment"].values() if not str(column).startswith(la.BIRTH_COLUMN_PREFIX))
    arm_state = _observe_matches(arm, checked_config, arm_state, matched)

    # 7. compile and commit atomically; an illegal program falls back to the empty program
    entity_states = {str(e["entity_id"]): str(e["state"]) for e in memory["entities"]}
    operations = arms.compile_program(solution["assignment"], entity_states, arm=arm, existence_decisions=decisions)
    program = compile_frame_program(operations, view, association_logits=logits["association_logits"],
                                    birth_logits=logits["birth_logits"], geometry=geometry, arm=arm)
    illegal: dict[str, Any] | None = None
    try:
        new_memory = lm.apply_program(memory, program, method_id=arm,
                                      dormancy_missed_opportunity_limit=checked_policy["dormancy_missed_opportunity_limit"],
                                      dedup=checked_policy["dedup"])
    except lm.LeanMemoryError as exc:
        illegal = {"code": str(exc), "operations_attempted": len(program["operations"]),
                   "atoms_attempted": {atom: sum(1 for op in operations if op["atom"] == atom) for atom in lm.ATOMS},
                   "arm_state_rolled_back": True}
        new_memory = lm.apply_program(memory, {"frame_digest": program["frame_digest"], "operations": []}, method_id=arm,
                                      dormancy_missed_opportunity_limit=checked_policy["dormancy_missed_opportunity_limit"],
                                      dedup=checked_policy["dedup"])
        # The whole frame rolls back, the arm's temporal state included: the ELU-P log-odds and
        # RAC counters were advanced for decisions that never took effect (S2 review, 2026-09-24).
        arm_state = clone_json(dict(state["arm_state"]))
    no_version_deleted: list[str] = []
    if arm == "NoVersion":
        new_memory = arms.apply_no_version(new_memory)
        no_version_deleted = list(new_memory.pop("no_version_deleted"))
    committed_ops = [] if illegal else operations
    live_ids = {str(e["entity_id"]) for e in new_memory["entities"]}
    arm_state = _prune_arm_state(arm_state, live_ids)

    # 8. receipt and counters
    counters = clone_json(dict(state["counters"]))
    counters["frames"] += 1
    counters["illegal_programs"] += int(illegal is not None)
    for op in committed_ops:
        counters["atoms"][op["atom"]] += 1
    counters["existence_candidates"] += len(filtered["eligible"])
    counters["excluded_not_visible"] += len(filtered["excluded_not_visible"])
    counters["excluded_retracted"] += len(filtered["excluded_retracted"])
    counters["no_version_deleted"] += len(no_version_deleted)
    delta = lm.frame_delta(new_memory)
    receipt = {
        "tick": tick,
        "frame_digest": str(view["frame_digest"]),
        "cache_frame_seal_sha256": str(cache_frame["frame_seal"]["payload_sha256"]),
        "descriptor": descriptor,
        "stage_a_seal_sha256": stage_a["seal_sha256"],
        "stage_b_seal_sha256": stage_b["seal_sha256"],
        "private_gate": gate,
        "recall": stage_a["recall"],
        "assignment": dict(stage_b["assignment"]),
        "total_cost": float(solution["total_cost"]),
        "existence": {
            "candidates": sorted(str(row["entity_id"]) for row in filtered["eligible"]),
            "excluded_not_visible": list(filtered["excluded_not_visible"]),
            "excluded_retracted": list(filtered["excluded_retracted"]),
            "decisions": dict(decisions),
        },
        "program": {"operations": [{k: v for k, v in op.items()} for op in committed_ops],
                    "atom_counts": {atom: sum(1 for op in committed_ops if op["atom"] == atom) for atom in lm.ATOMS}},
        "illegal_program": illegal,
        "no_version_deleted": no_version_deleted,
        "memory_digest_before": str(memory["memory_digest"]),
        "memory_digest_after": str(new_memory["memory_digest"]),
        "entities_by_state": {s: sum(1 for e in new_memory["entities"] if e["state"] == s) for s in lm.ENTITY_STATES},
        "frame_delta": delta,
        "arm_state_sha256": sha(arm_state),
    }
    new_state = {
        "arm": arm, "memory": new_memory, "arm_state": arm_state, "counters": counters,
        "surface_points": updated_surface_store(state.get("surface_points", {}), new_memory, depth_view),
        "cache_frame_seals": [*state["cache_frame_seals"], receipt["cache_frame_seal_sha256"]],
    }
    return {"state": new_state, "receipt": receipt, "stage_a": stage_a, "stage_b": stage_b, "view": view,
            "memory_before": memory, "entity_geometry": geometry}


def run_episode(
    frames: Sequence[Mapping[str, Any]], *, episode_id: str, arm: str, config: Mapping[str, Any],
    policy: Mapping[str, Any], descriptor: str,
    projector: Callable[[Sequence[Sequence[float]]], list[list[float]]] | None = None, scorer: Any = None,
):
    """Generator over the frames of one episode, yielding ``run_frame``'s result per frame."""

    state = initial_state(episode_id=episode_id, arm=arm)
    for frame in frames:
        step = run_frame(state, frame, arm=arm, config=config, policy=policy, descriptor=descriptor,
                         projector=projector, scorer=scorer)
        state = step["state"]
        yield step


def episode_summary(state: Mapping[str, Any], receipts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Per-episode counts and the list of cache frame seals the run consumed."""

    counters = state["counters"]
    _require(counters["frames"] == len(receipts) == len(state["cache_frame_seals"]), "summary_frame_counts_differ")
    return {
        "arm": state["arm"],
        "episode_id": state["memory"]["episode_id"],
        "frames": counters["frames"],
        "illegal_programs": counters["illegal_programs"],
        "atoms": dict(counters["atoms"]),
        "existence_candidates": counters["existence_candidates"],
        "excluded_not_visible": counters["excluded_not_visible"],
        "excluded_retracted": counters["excluded_retracted"],
        "no_version_deleted": counters["no_version_deleted"],
        "final_entities_by_state": {s: sum(1 for e in state["memory"]["entities"] if e["state"] == s) for s in lm.ENTITY_STATES},
        "final_memory_digest": state["memory"]["memory_digest"],
        "cache_frame_seals_sha256": sha(list(state["cache_frame_seals"])),
        "cache_frame_seals": list(state["cache_frame_seals"]),
        "stage_a_seals_sha256": sha([r["stage_a_seal_sha256"] for r in receipts]),
        "stage_b_seals_sha256": sha([r["stage_b_seal_sha256"] for r in receipts]),
    }


def assert_identical_cache_across_arms(summaries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """S2-01 continue gate: every arm read byte-identical cache frames (the same seals in the same order)."""

    _require(len(summaries) >= 2, "cache_gate_needs_two_arms")
    baseline = summaries[0]
    for summary in summaries[1:]:
        _require(summary["episode_id"] == baseline["episode_id"], "cache_gate_episodes_differ")
        _require(summary["cache_frame_seals"] == baseline["cache_frame_seals"], f"cache_gate_arm_read_different_cache:{summary['arm']}")
    return {"episode_id": baseline["episode_id"], "arms": [s["arm"] for s in summaries],
            "cache_frame_seals_sha256": baseline["cache_frame_seals_sha256"], "frames": baseline["frames"]}


# --------------------------------------------------------------------------
# 5. the private side: the evaluator's truth table, built after both seals
# --------------------------------------------------------------------------

class TruthTableBuilder:
    """Frame-by-frame truth table for the S0-04 evaluator, with the ruling-56 (continued) scope flag.

    白话：输入每帧的私有记录（哪些物体有多少像素）和 S1-04 真值追踪器给出的"在不在、盒子在哪"，输出
    评价器要的真值表：到这一帧为止见过的每个私有键一行，present 来自追踪器，in_scope 按 S0-04 规则算
    （此前至少一帧私有 mask ≥196 像素，且不是墙/房间/门/窗）。结构件不在几何表里，登记为在场、范围
    外、无盒；其他不在几何表里的键说明数据有问题，整条 episode 失败而不是悄悄缩小范围。
    """

    def __init__(self) -> None:
        self.seen_keys: set[str] = set()
        self.observable_keys: set[str] = set()
        self.spawned_keys: set[str] = set()  # ruling 69: keys outside the table with a spawn tag, counted
        self.frames_seen = 0

    def update(self, private_record: Mapping[str, Any], tracker_truth: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
        visibility = private_record.get("object_visibility")
        _require(type(visibility) is dict, "private_record_without_object_visibility")
        for key, pixels in visibility.items():
            self.seen_keys.add(str(key))
            if int(pixels) >= OBSERVABLE_MIN_PIXELS:
                self.observable_keys.add(str(key))
        for key in private_record.get("object_id_to_entity_id", {}):
            self.seen_keys.add(str(key))
        self.frames_seen += 1
        table: dict[str, dict[str, Any]] = {}
        for key in sorted(self.seen_keys):
            in_scope = lt.in_truth_node_scope(key, observable_before=key in self.observable_keys)
            if key in tracker_truth:
                entry = tracker_truth[key]
                present = bool(entry["present"])
                row: dict[str, Any] = {"present": present, "in_scope": in_scope}
                if present:
                    if in_scope:
                        _require(entry.get("aabb_min_m") is not None and entry.get("aabb_max_m") is not None,
                                 f"truth_object_without_box:{key}")
                    if entry.get("aabb_min_m") is not None:
                        row["aabb_min_m"] = [float(v) for v in entry["aabb_min_m"]]
                        row["aabb_max_m"] = [float(v) for v in entry["aabb_max_m"]]
                    if entry.get("centroid_m") is not None:
                        row["centroid_m"] = [float(v) for v in entry["centroid_m"]]
            elif lt.structural_type_of(key) in lt.STRUCTURAL_TYPES_EXCLUDED:
                row = {"present": True, "in_scope": False}
            elif lt.is_spawned_after_reload(key):  # ruling 69: a physics-spawned object, never in the reload table
                self.spawned_keys.add(key)
                row = {"present": True, "in_scope": False}
            else:
                raise LeanRunnerError(f"truth_key_outside_geometry_table:{key}")
            table[key] = row
        return table


# --------------------------------------------------------------------------
# 6. machine contract
# --------------------------------------------------------------------------

def validate_runner_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Check that the S2-01 machine contract agrees with this implementation."""

    _require(type(contract) is dict, "contract_not_object")
    _require(contract.get("schema_version") == CONTRACT_SCHEMA_VERSION, "contract_schema_version_invalid")
    _require(contract.get("decision_id") == "D-224", "contract_decision_id_invalid")
    _require(contract.get("stage_id") == STAGE_ID, "contract_stage_id_invalid")
    descriptor = contract["descriptor"]
    _require(descriptor["selected"] == la.SELECTED_DESCRIPTOR, "contract_descriptor_selected_mismatch")
    _require(descriptor["source_set"] == la.SELECTED_DESCRIPTOR_SOURCE_SET, "contract_descriptor_source_mismatch")
    _require(descriptor["frozen_baseline"] == la.FROZEN_DESCRIPTOR_BASELINE, "contract_descriptor_baseline_mismatch")
    _require(descriptor["weights_sha256"] == la.SELECTED_REID_WEIGHTS_SHA256, "contract_descriptor_weights_mismatch")
    _require(tuple(descriptor["choices"]) == DESCRIPTOR_CHOICES, "contract_descriptor_choices_mismatch")
    _require(descriptor["weights_digest_checked_before_any_projection"] is True, "contract_descriptor_claim_weakened")
    geometry = contract["entity_geometry"]
    _require(geometry["rule"] == ENTITY_GEOMETRY_RULE, "contract_entity_geometry_rule_mismatch")
    _require(geometry["depth_margin_m"] == DEPTH_MARGIN_M, "contract_entity_geometry_margin_mismatch")
    _require(geometry["fragment_surface_max_points"] == FRAGMENT_SURFACE_MAX_POINTS
             and geometry["fragment_surface_rule"] == FRAGMENT_SURFACE_RULE, "contract_entity_geometry_surface_rule_mismatch")
    _require(list(geometry["valid_depth_range_m"]) == list(DEPTH_VALID_RANGE_M), "contract_entity_geometry_depth_range_mismatch")
    _require(tuple(geometry["public_depth_view_fields"]) == PUBLIC_DEPTH_VIEW_FIELDS, "contract_entity_geometry_view_fields_mismatch")
    _require(tuple(geometry["fields"]) == la.ENTITY_GEOMETRY_FIELDS, "contract_entity_geometry_fields_mismatch")
    for name in ("pure_function_of_public_depth_intrinsics_causal_pose_and_previous_memory", "identical_bytes_for_all_arms",
                 "depth_view_must_be_of_the_same_frame", "depth_view_is_never_written_into_the_cache",
                 "computed_for_every_entity_of_the_previous_memory", "projection_is_fixed_order_elementwise_not_blas"):
        _require(geometry[name] is True, f"contract_entity_geometry_claim_weakened:{name}")
    open_slots = contract["policy_values_without_defaults"]
    slot = "entity_geometry.samples_per_axis"
    if geometry["samples_per_axis"] is None:
        _require(slot in open_slots, "contract_samples_per_axis_null_but_not_registered_as_open")
    else:
        _require(slot not in open_slots, "contract_samples_per_axis_frozen_but_still_listed_as_open")
        _require(ENTITY_GEOMETRY_SAMPLES_PER_AXIS is not None and geometry["samples_per_axis"] == ENTITY_GEOMETRY_SAMPLES_PER_AXIS,
                 "contract_samples_per_axis_differs_from_the_frozen_constant")
    step = contract["frame_step"]
    _require(tuple(step["order"]) == FRAME_STEP_ORDER, "contract_frame_step_order_mismatch")
    _require(step["illegal_program_rule"] == ILLEGAL_PROGRAM_RULE, "contract_illegal_program_rule_mismatch")
    for name in ("recall_values_are_the_frozen_s0_03_values", "rule_arm_assignment_must_contain_no_sentinel_pair",
                 "existence_candidates_are_eligible_rows_only", "private_gate_receipt_built_from_both_seals",
                 "no_private_file_is_read_in_the_public_phase", "no_version_deletes_retracted_after_the_commit"):
        _require(step[name] is True, f"contract_frame_step_claim_weakened:{name}")
    _require(dict(step["policy_input_sources"]) == POLICY_INPUT_SOURCES, "contract_policy_sources_mismatch")
    _require(tuple(step["runnable_arms"]) == RUNNABLE_ARMS, "contract_runnable_arms_mismatch")
    _require(step["appendix_arm_refused_here"] == arms.APPENDIX_ARM, "contract_appendix_arm_mismatch")
    _require(step["arm_state"]["arm_state_rolled_back_with_the_frame_on_an_illegal_program"] is True,
             "contract_frame_step_claim_weakened:arm_state_rolled_back_with_the_frame_on_an_illegal_program")
    truth = contract["truth_table"]
    _require(truth["observable_rule"] == TRUTH_TABLE_OBSERVABLE_RULE, "contract_truth_observable_rule_mismatch")
    _require(truth["observable_min_pixels"] == OBSERVABLE_MIN_PIXELS, "contract_truth_pixels_mismatch")
    _require(truth["key_rule"] == TRUTH_TABLE_KEY_RULE, "contract_truth_key_rule_mismatch")
    _require(tuple(truth["structural_types_out_of_scope"]) == lt.STRUCTURAL_TYPES_EXCLUDED, "contract_truth_structural_mismatch")
    _require(truth["spawned_after_reload_rule"] == lt.SPAWNED_AFTER_RELOAD_RULE, "contract_truth_spawned_rule_mismatch")
    _require(truth["built_only_after_both_seals"] is True and truth["in_scope_by_s0_04_in_truth_node_scope"] is True,
             "contract_truth_claim_weakened")
    _require(tuple(contract["failure_reasons"]) == FAILURE_REASONS, "contract_failure_reasons_mismatch")
    gate = contract["continue_gate"]
    _require(gate["five_arms_read_byte_identical_cache_clones"] is True, "contract_continue_gate_weakened")
    # Authorization bits are not switches the implementer may flip: a bit may be true only when
    # an activation_policy names it and the ruling that opened it (the S1-03 / S1-04 pattern;
    # D-224-S1 ruling 61, 2026-09-24).  The ops entry separately refuses while a bit is closed.
    policy = contract.get("activation_policy")
    opened = set(policy["active_true_authorizations"]) if policy else set()
    if policy:
        _require(type(policy.get("opened_by")) is str and bool(policy["opened_by"]), "contract_activation_policy_names_no_ruling")
    for name, value in contract["authorization"].items():
        _require(type(value) is bool, f"contract_authorization_not_boolean:{name}")
        _require(value is False or name in opened, f"contract_bit_opened_without_a_ruling:{name}")
    return clone_json(dict(contract))


FRAME_STEP_ORDER = (
    "entity_geometry_from_public_volumes_and_previous_memory",
    "assignment_view_under_the_frozen_descriptor",
    "stage_a_recall_and_features_sealed",
    "arm_logits_then_one_rectangular_solve",
    "stage_b_assignment_and_existence_features_sealed_and_private_gate",
    "existence_decisions_on_eligible_rows_with_arm_state",
    "compile_within_vocabulary_and_commit_atomically_or_empty_program",
    "receipt_with_seals_digests_and_frame_delta",
)


__all__ = [
    "ARM_CONFIG_FIELDS",
    "CONTRACT_SCHEMA_VERSION",
    "DESCRIPTOR_CHOICES",
    "DEPTH_MARGIN_M",
    "DEPTH_VALID_RANGE_M",
    "FRAGMENT_SURFACE_MAX_POINTS",
    "FRAGMENT_SURFACE_RULE",
    "ENTITY_GEOMETRY_RULE",
    "PUBLIC_DEPTH_VIEW_FIELDS",
    "PUBLIC_DEPTH_VIEW_KEY",
    "ENTITY_GEOMETRY_SAMPLES_PER_AXIS",
    "FAILURE_REASONS",
    "FRAME_STEP_ORDER",
    "HALFSPACE_TOLERANCE_M",
    "ILLEGAL_PROGRAM_RULE",
    "LeanRunnerError",
    "OBSERVABLE_MIN_PIXELS",
    "POLICY_FIELDS",
    "POLICY_INPUT_SOURCES",
    "RUNNABLE_ARMS",
    "STAGE_ID",
    "TRUTH_TABLE_KEY_RULE",
    "TRUTH_TABLE_OBSERVABLE_RULE",
    "TruthTableBuilder",
    "assert_identical_cache_across_arms",
    "assignment_frame",
    "compile_frame_program",
    "descriptor_projector",
    "entity_geometry",
    "entity_geometry_blocks",
    "entity_surface_points",
    "fragment_surface_points",
    "updated_surface_store",
    "point_depth_counts",
    "public_depth_view_of",
    "episode_summary",
    "initial_state",
    "block_aabbs",
    "inside_union_fraction",
    "run_episode",
    "run_frame",
    "sample_points",
    "source_set_of",
    "validate_arm_config",
    "validate_policy",
    "validate_runner_contract",
]
