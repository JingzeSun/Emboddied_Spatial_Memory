"""D-224 / S0-03: recall, features, cost matrix and the rectangular solve.

This module turns one frozen frontend frame plus the prior predicted memory
into the exact inputs of the frame-level joint assignment, and solves it.
Everything here is public: it never takes a private, teacher, future or
reference argument, and it never reads a path, slot index or sample name.

白话：这个模块解决"本帧的每个色块该和旧记忆里的哪个实体配对，还是自己新建"。
输入是冻结前端的一帧、此前预测的记忆和一组无默认值的规则数值，输出是召回集合、
特征矩阵、代价矩阵和一次分配结果。例如两个相似色块同时匹配一个旧实体时，分配
会把其中一个推向新建。它不训练模型、不读取私有数据、不决定该记什么指标。

Three ordering facts matter and are enforced rather than assumed:

* Recall and the association/birth feature matrix are computed **before** any
  model runs, and their digest is sealed.  Nothing private has been opened.
* The solve consumes only those sealed features plus the cost heads' output.
* Existence features are computed **after** the solve, because one of them is
  "the best-matching fragment is still unassigned".  They are still public:
  they derive from the same cache, the same prior memory and the assignment.

The solver is written here rather than taken from scipy.  scipy is not a
dependency of this project, and the tie-breaking has to be ours anyway: a
rectangular assignment usually has several optima, and which one is returned
must not depend on dict order, float noise or library version.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any, Mapping, Sequence

import numpy as np

from cpmt.hashing import canonical_json, clone_json

from vsmt.lean_geometry import cosine_similarity
from vsmt.lean_memory import ENTITY_STATES, validate_memory


class _NeumaierSum:
    """Element-wise replica of CPython 3.12's ``sum()`` over floats (Neumaier compensated summation).

    ``sum(generator)`` no longer adds left to right: since Python 3.12 it keeps a compensation term
    ``c`` and adds it once at the end.  To equal the scalar function bit for bit, the matrix form
    runs the same three operations per term, on arrays of partial sums.
    """

    def __init__(self, shape: tuple[int, ...]) -> None:
        self.total = np.zeros(shape, dtype=np.float64)
        self.compensation = np.zeros(shape, dtype=np.float64)

    def add(self, term: np.ndarray) -> None:
        running = self.total + term
        dominant = np.abs(self.total) >= np.abs(term)
        self.compensation += np.where(dominant, (self.total - running) + term, (term - running) + self.total)
        self.total = running

    def result(self) -> np.ndarray:
        # CPython adds the compensation only when it is non-zero (and finite), which also keeps -0.0
        return np.where(self.compensation != 0.0, self.total + self.compensation, self.total)


def cosine_matrix(left_rows: Sequence[Sequence[float]], right_rows: Sequence[Sequence[float]]) -> list[list[float]]:
    """Cosine of every left row against every right row, bit-identical to ``cosine_similarity``.

    Engineering (S2-05 profiling, LOG-254): the scalar function was called once per (fragment,
    entity) pair in pure Python and took an eighth of the per-frame time.  This does the same
    arithmetic in the same order on whole rows -- the products summed left to right from zero,
    the norms as the square root of the same sums of squares, one division, one clip -- so every
    cell equals the scalar result to the last bit (pinned by test).  Rows of unequal width fall
    back to the scalar function so the -1.0 convention is kept.
    """

    left = [[float(v) for v in row] for row in left_rows]
    right = [[float(v) for v in row] for row in right_rows]
    if not left or not right:
        return [[-1.0] * len(right) for _ in left]
    widths = {len(row) for row in left} | {len(row) for row in right}
    if len(widths) != 1 or 0 in widths:
        return [[cosine_similarity(a, b) for b in right] for a in left]
    a = np.asarray(left, dtype=np.float64)
    b = np.asarray(right, dtype=np.float64)
    dot = _NeumaierSum((a.shape[0], b.shape[0]))
    for k in range(a.shape[1]):
        dot.add(a[:, k][:, None] * b[:, k][None, :])
    dot = dot.result()
    # The norms stay on the scalar path: ``value ** 2`` is the C library's pow(x, 2.0), which glibc
    # rounds within 0.52 ULP but not always to x*x, so a vectorised square differed from the scalar
    # function by one ULP on a few real descriptors (server check, LOG-254).  One norm per vector
    # is cheap; the fragment-by-entity products are what the matrix form is for.
    left_norm = np.asarray([math.sqrt(sum(float(value) ** 2 for value in row)) for row in left], dtype=np.float64)
    right_norm = np.asarray([math.sqrt(sum(float(value) ** 2 for value in row)) for row in right], dtype=np.float64)
    denominator = left_norm[:, None] * right_norm[None, :]
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.clip(dot / denominator, -1.0, 1.0)
    zero = (left_norm[:, None] == 0.0) | (right_norm[None, :] == 0.0)
    return np.where(zero, -1.0, ratio).tolist()


CONTRACT_SCHEMA_VERSION = "vsmt-lean-s0-assignment-v2"

#: Frozen feature order for the association head a(f, e).  Downstream code
#: indexes by position, so changing this order is a contract change.
ASSOCIATION_FEATURES = (
    "cosine_to_descriptor_mean",
    "cosine_to_best_view_descriptor",
    "centroid_distance_m",
    "aabb_iou",
    "log_size_ratio",
    "ticks_since_last_seen",
    "missed_opportunity_count",
    "state_is_active",
    "state_is_dormant",
    "state_is_retracted",
    "cosine_rank_within_recall",
    "cosine_margin_to_runner_up",
    "mutual_best",
    "support_height_difference_m",
)

#: Frozen feature order for the existence head r(e), computed after the solve.
EXISTENCE_FEATURES = (
    "should_be_visible_ratio",
    "free_space_coverage_ratio",
    "camera_distance_m",
    "camera_view_cosine",
    "missed_opportunity_count",
    "observation_count",
    "ticks_since_last_seen",
    "best_fragment_cosine",
    "best_fragment_still_unassigned",
    "state_is_active",
    "state_is_dormant",
    "state_is_retracted",
)

#: Frozen feature order for the birth head b(f).
BIRTH_FEATURES = (
    "best_cosine_to_any_entity",
    "active_entities_within_radius",
    "pixel_count",
    "depth_valid_ratio",
)

#: Fields one frontend cache frame must expose, and nothing more.
CACHE_FRAME_FIELDS = (
    "frame_digest", "tick", "camera_position_m", "camera_forward",
    "fragments", "entity_geometry",
)

#: Per-entity public geometry the frame supplies for the existence head.
ENTITY_GEOMETRY_FIELDS = (
    "should_be_visible_ratio", "free_space_coverage_ratio",
)

#: A virtual BIRTH column is named after its fragment, never after a slot.
BIRTH_COLUMN_PREFIX = "birth:"

#: Index of the vertical axis in every 3-vector (AI2-THOR / ProcTHOR are
#: y-up).  The support-height feature reads this axis; registering it here
#: keeps the convention out of a bare literal.
UP_AXIS_INDEX = 1

#: Shared ReID adapter head (D-224-E), values ledgered by D-224-S1 ruling 47 (2026-09-22):
#: the projection is 128-dimensional (D-224-E's own words) and it is selected in S1-05 only
#: if its median cross-view separation on the selection houses beats the best frozen
#: descriptor by at least this cosine margin.  The projection is trained on the first 30
#: cached development houses and judged on the last 12, so it is never scored on a house
#: it was fitted to.
REID_OUTPUT_DIMENSION = 128
REID_SELECTION_RULE_THRESHOLD = 0.05
#: D-224-S1 ruling 57 (2026-09-24): the three recall values frozen from the S1-04 curve (LOG-244).
RECALL_LOCAL_COUNT = 5
RECALL_GLOBAL_COUNT = 3
RECALL_LOCAL_RADIUS_M = 3.0
#: D-224-S1 ruling 58 (2026-09-24): the fourth recall value, from the S1-04 birth neighbourhood counts.
RECALL_BIRTH_NEIGHBOURHOOD_RADIUS_M = 1.0
REID_TRAINING_HOUSES = 30
REID_SELECTION_HOUSES = 12
#: S1-05 (2026-09-24, LOG-245): the frozen ruling-47 rule applied to the S1-04 report
#: (results/vsmt_lean_s1_04_diagnostics_154776d.json).  On the 9 selection houses the ViT-B/14
#: projection's median cross-view separation is 0.2358 against 0.1430 for the best frozen set
#: (ViT-B/14 itself): a gain of 0.093 over the 0.05 margin, so every arm reads the projection of
#: ``descriptor_vitb14`` and frozen ViT-B/14 is the baseline the paper reports alongside.  The
#: selection group is 9 houses, not 12: the cached development block has 39 episodes and the
#: contract skips and counts, never refills.  No later stage may change this choice.
SELECTED_DESCRIPTOR = "reid_projection:vitb14"
SELECTED_DESCRIPTOR_SOURCE_SET = "vitb14"
FROZEN_DESCRIPTOR_BASELINE = "vitb14"
SELECTED_REID_WEIGHTS_SHA256 = "f6fc67e5f365a4f6d375d6aa16afe15cb0d9769879aa0cc1ab84ff6de9b65073"


class LeanAssignmentError(ValueError):
    """Raised for any malformed frame, memory view, rule value or matrix."""


# --------------------------------------------------------------------------
# small validators
# --------------------------------------------------------------------------

def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LeanAssignmentError(code)


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


def _ratio(value: Any, code: str) -> float:
    result = _finite(value, code)
    _require(0.0 <= result <= 1.0, code)
    return result


def _vector(value: Any, code: str, *, length: int | None = None) -> list[float]:
    _require(type(value) is list and value, code)
    if length is not None:
        _require(len(value) == length, code)
    return [_finite(item, code) for item in value]


def _hex64(value: Any, code: str) -> str:
    _require(type(value) is str and len(value) == 64, code)
    _require(all(char in "0123456789abcdef" for char in value), code)
    return value


def _distance(left: Sequence[float], right: Sequence[float]) -> float:
    return math.sqrt(sum(
        (float(a) - float(b)) ** 2 for a, b in zip(left, right, strict=True)
    ))


def _aabb_iou(
    lower_a: Sequence[float], upper_a: Sequence[float],
    lower_b: Sequence[float], upper_b: Sequence[float],
) -> float:
    overlap = 1.0
    volume_a = 1.0
    volume_b = 1.0
    for axis in range(3):
        low = max(float(lower_a[axis]), float(lower_b[axis]))
        high = min(float(upper_a[axis]), float(upper_b[axis]))
        overlap *= max(0.0, high - low)
        volume_a *= max(0.0, float(upper_a[axis]) - float(lower_a[axis]))
        volume_b *= max(0.0, float(upper_b[axis]) - float(lower_b[axis]))
    union = volume_a + volume_b - overlap
    if union <= 0.0:
        return 0.0
    return overlap / union


def _volume(lower: Sequence[float], upper: Sequence[float]) -> float:
    result = 1.0
    for axis in range(3):
        result *= max(0.0, float(upper[axis]) - float(lower[axis]))
    return result


# --------------------------------------------------------------------------
# frame validation
# --------------------------------------------------------------------------

def validate_cache_frame(frame: Mapping[str, Any]) -> dict[str, Any]:
    """Check one frozen frontend frame.  It must carry no private identifier.

    白话：输入共享前端 cache 的一帧，输出同样内容的副本，并在字段不符、几何非法
    或出现场景标识时拒绝。例如把 house ID 写进 fragment 会被拒。它不打开图像，也
    不判断 fragment 是否真的对应一个物体。
    """

    _require(type(frame) is dict, "frame_not_object")
    _require(
        tuple(sorted(frame.keys())) == tuple(sorted(CACHE_FRAME_FIELDS)),
        "frame_fields_invalid",
    )
    _hex64(frame["frame_digest"], "frame_digest_invalid")
    _int(frame["tick"], "frame_tick_invalid", minimum=1)
    _vector(frame["camera_position_m"], "camera_position_invalid", length=3)
    forward = _vector(frame["camera_forward"], "camera_forward_invalid", length=3)
    _require(
        abs(math.sqrt(sum(value * value for value in forward)) - 1.0) < 1e-6,
        "camera_forward_not_unit",
    )

    fragments = frame["fragments"]
    _require(type(fragments) is list, "fragments_invalid")
    seen: set[str] = set()
    dimensions: set[int] = set()
    for fragment in fragments:
        _require(type(fragment) is dict, "fragment_not_object")
        _require(
            tuple(sorted(fragment.keys())) == tuple(sorted((
                "fragment_id", "descriptor", "centroid_m", "aabb_min_m",
                "aabb_max_m", "pixel_count", "depth_valid_ratio", "supported_by",
            ))),
            "fragment_fields_invalid",
        )
        fragment_id = fragment["fragment_id"]
        _require(type(fragment_id) is str and fragment_id, "fragment_id_invalid")
        _require(
            not fragment_id.startswith(BIRTH_COLUMN_PREFIX),
            "fragment_id_collides_with_birth_column",
        )
        _require(fragment_id not in seen, "fragment_id_duplicate")
        seen.add(fragment_id)
        dimensions.add(len(_vector(fragment["descriptor"], "fragment_descriptor_invalid")))
        _vector(fragment["centroid_m"], "fragment_centroid_invalid", length=3)
        lower = _vector(fragment["aabb_min_m"], "fragment_aabb_min_invalid", length=3)
        upper = _vector(fragment["aabb_max_m"], "fragment_aabb_max_invalid", length=3)
        _require(
            all(a <= b for a, b in zip(lower, upper, strict=True)),
            "fragment_aabb_inverted",
        )
        _int(fragment["pixel_count"], "fragment_pixel_count_invalid", minimum=1)
        _ratio(fragment["depth_valid_ratio"], "fragment_depth_valid_ratio_invalid")
        if fragment["supported_by"] is not None:
            _require(
                type(fragment["supported_by"]) is str and fragment["supported_by"],
                "fragment_supported_by_invalid",
            )
    _require(len(dimensions) <= 1, "frame_descriptor_dimension_mixed")

    geometry = frame["entity_geometry"]
    _require(type(geometry) is dict, "entity_geometry_invalid")
    for entity_id, record in geometry.items():
        _require(type(entity_id) is str and entity_id, "entity_geometry_key_invalid")
        _require(type(record) is dict, "entity_geometry_record_invalid")
        _require(
            tuple(sorted(record.keys())) == tuple(sorted(ENTITY_GEOMETRY_FIELDS)),
            "entity_geometry_fields_invalid",
        )
        for name in ENTITY_GEOMETRY_FIELDS:
            _ratio(record[name], f"entity_geometry_{name}_invalid")
    return clone_json(dict(frame))


# --------------------------------------------------------------------------
# recall
# --------------------------------------------------------------------------

def recall_for_fragment(
    fragment: Mapping[str, Any], memory: Mapping[str, Any], *,
    local_count: int, global_count: int, local_radius_m: float,
    cosines: Mapping[str, float] | None = None,
) -> list[str]:
    """Return the recalled entity ids for one fragment, in a fixed order.

    白话：输入一个色块和旧记忆，输出这次要为它考虑的实体列表。两条通道取并集：本
    地通道在登记半径内按余弦取前 k 个，全局通道**对全部状态一视同仁**、不设距离
    上限、按余弦取前 k′ 个。例如杯子从厨房搬到卧室后，全局通道仍能把旧杯子召回来。
    它不判断谁是正确答案，也不读取私有身份。

    Why the global channel ignores state.  An earlier version gave the
    distance-free channel only to dormant and retracted entities.  That
    silently confounded the ``AssocOnly`` ablation: ``AssocOnly`` has no
    dormant or retracted state at all, so a carried-away object would stay
    active at its old place, fall outside the local radius, and be forced to
    BIRTH.  The comparison would then measure "does it have the lifecycle
    vocabulary" *and* "is it allowed distant candidates" together, which is
    not the causal counterfactual D-224-HIJ made mandatory.  Candidate
    eligibility is now state-independent and identical for all five arms;
    state only decides which atom an assignment compiles to.

    Ties in cosine are broken by ``entity_id`` so the order never depends on
    dict iteration or on the order entities happen to sit in the memory list.
    """

    k_local = _int(local_count, "recall_local_count_invalid", minimum=0)
    k_global = _int(global_count, "recall_global_count_invalid", minimum=0)
    radius = _finite(local_radius_m, "recall_local_radius_invalid")
    _require(radius > 0.0, "recall_local_radius_invalid")

    descriptor = fragment["descriptor"]
    centroid = fragment["centroid_m"]
    local: list[tuple[float, str]] = []
    everywhere: list[tuple[float, str]] = []
    for entity in memory["entities"]:
        entity_id = str(entity["entity_id"])
        # ``cosines`` is the precomputed row of cosine_matrix (bit-identical); absent, compute as before
        cosine = cosines[entity_id] if cosines is not None else cosine_similarity(descriptor, entity["descriptor_mean"])
        everywhere.append((cosine, entity_id))
        if _distance(centroid, entity["centroid_m"]) <= radius:
            local.append((cosine, entity_id))

    local.sort(key=lambda item: (-item[0], item[1]))
    everywhere.sort(key=lambda item: (-item[0], item[1]))
    ordered: list[str] = []
    seen: set[str] = set()
    for _, entity_id in local[:k_local] + everywhere[:k_global]:
        if entity_id not in seen:
            seen.add(entity_id)
            ordered.append(entity_id)
    return ordered


def build_recall(
    frame: Mapping[str, Any], memory: Mapping[str, Any], *,
    local_count: int, global_count: int, local_radius_m: float,
    cosine_rows: Mapping[str, Mapping[str, float]] | None = None,
) -> dict[str, list[str]]:
    """Recall for every fragment of the frame, keyed by fragment id."""

    return {
        str(fragment["fragment_id"]): recall_for_fragment(
            fragment, memory, local_count=local_count,
            global_count=global_count, local_radius_m=local_radius_m,
            cosines=None if cosine_rows is None else cosine_rows[str(fragment["fragment_id"])],
        )
        for fragment in frame["fragments"]
    }


# --------------------------------------------------------------------------
# features
# --------------------------------------------------------------------------

def _state_one_hot(state: str) -> list[float]:
    return [1.0 if state == candidate else 0.0 for candidate in ENTITY_STATES]


def association_feature_vector(
    fragment: Mapping[str, Any], entity: Mapping[str, Any], *,
    recall_order: Sequence[str], cosines: Mapping[str, float],
    mutual_best: bool, tick: int, best_view_cosine: float | None = None,
) -> list[float]:
    """One association feature row, in the frozen ASSOCIATION_FEATURES order.

    ``best_view_cosine`` is the precomputed (bit-identical) cosine to the entity's best-view
    descriptor from ``cosine_matrix``; absent, it is computed here as before.
    """

    entity_id = str(entity["entity_id"])
    cosine = cosines[entity_id]
    ranked = sorted(
        ((cosines[item], item) for item in recall_order),
        key=lambda item: (-item[0], item[1]),
    )
    rank = [item[1] for item in ranked].index(entity_id)
    runner_up = ranked[1][0] if len(ranked) > 1 else -1.0
    margin = cosine - runner_up if rank == 0 else cosine - ranked[0][0]

    fragment_volume = _volume(fragment["aabb_min_m"], fragment["aabb_max_m"])
    entity_volume = _volume(entity["aabb_min_m"], entity["aabb_max_m"])
    log_ratio = math.log(
        max(fragment_volume, 1e-9) / max(entity_volume, 1e-9)
    )

    row = [
        cosine,
        (cosine_similarity(fragment["descriptor"], entity["best_view_descriptor"])
         if best_view_cosine is None else float(best_view_cosine)),
        _distance(fragment["centroid_m"], entity["centroid_m"]),
        _aabb_iou(
            fragment["aabb_min_m"], fragment["aabb_max_m"],
            entity["aabb_min_m"], entity["aabb_max_m"],
        ),
        log_ratio,
        float(tick - int(entity["last_seen_tick"])),
        float(entity["missed_opportunity_count"]),
        *_state_one_hot(str(entity["state"])),
        float(rank),
        margin,
        1.0 if mutual_best else 0.0,
        # Height of the supporting plane, as a pure geometric difference.
        # Comparing ``supported_by`` ids instead would only be informative if
        # surface ids were stable across frames, which would mean maintaining
        # a persistent surface identity -- exactly the capability D-224 took
        # out of the first paper.  The bottom-face height carries the same
        # public cue with no identity and no threshold.
        abs(
            float(fragment["aabb_min_m"][UP_AXIS_INDEX])
            - float(entity["aabb_min_m"][UP_AXIS_INDEX])
        ),
    ]
    _require(len(row) == len(ASSOCIATION_FEATURES), "association_feature_arity")
    return row


def birth_feature_vector(
    fragment: Mapping[str, Any], memory: Mapping[str, Any], *,
    cosines: Mapping[str, float], neighbourhood_radius_m: float,
) -> list[float]:
    """One birth feature row, in the frozen BIRTH_FEATURES order."""

    radius = _finite(neighbourhood_radius_m, "birth_radius_invalid")
    _require(radius > 0.0, "birth_radius_invalid")
    best = max(cosines.values()) if cosines else -1.0
    nearby = sum(
        1 for entity in memory["entities"]
        if entity["state"] == "active"
        and _distance(fragment["centroid_m"], entity["centroid_m"]) <= radius
    )
    row = [
        best,
        float(nearby),
        float(fragment["pixel_count"]),
        float(fragment["depth_valid_ratio"]),
    ]
    _require(len(row) == len(BIRTH_FEATURES), "birth_feature_arity")
    return row


def existence_feature_vector(
    entity: Mapping[str, Any], frame: Mapping[str, Any], *,
    assignment: Mapping[str, str], tick: int,
    fragment_cosines: Mapping[str, float] | None = None,
) -> list[float]:
    """One existence feature row, computed after the solve.

    白话：输入一个本帧未被分配的实体、当前帧和已经解出的分配，输出存在头的特征
    行。其中"最相似色块是否仍未被分配"必须在分配之后才有定义，因此存在特征在求
    解之后计算。例如一个实体的最佳色块已经绑给别的实体，说明它更可能真的不在了。
    它仍然只用公开量，不读取私有身份。
    """

    entity_id = str(entity["entity_id"])
    geometry = frame["entity_geometry"].get(entity_id)
    _require(geometry is not None, f"entity_geometry_missing:{entity_id}")

    camera = frame["camera_position_m"]
    forward = frame["camera_forward"]
    offset = [
        float(entity["centroid_m"][axis]) - float(camera[axis]) for axis in range(3)
    ]
    distance = math.sqrt(sum(value * value for value in offset))
    if distance > 0.0:
        view_cosine = sum(
            offset[axis] * float(forward[axis]) for axis in range(3)
        ) / distance
    else:
        view_cosine = 1.0

    # Highest cosine wins; a tie goes to the smaller fragment id so the value
    # never depends on the order fragments happen to sit in the frame.
    best_cosine = -1.0
    best_fragment_id = ""
    for fragment in frame["fragments"]:
        candidate = str(fragment["fragment_id"])
        # ``fragment_cosines`` is the precomputed column of cosine_matrix (bit-identical); absent, compute as before
        cosine = (fragment_cosines[candidate] if fragment_cosines is not None
                  else cosine_similarity(fragment["descriptor"], entity["descriptor_mean"]))
        if best_fragment_id == "" or (-cosine, candidate) < (
            -best_cosine, best_fragment_id
        ):
            best_cosine, best_fragment_id = cosine, candidate

    unassigned = (
        best_fragment_id != ""
        and assignment.get(best_fragment_id, "").startswith(BIRTH_COLUMN_PREFIX)
    )
    row = [
        float(geometry["should_be_visible_ratio"]),
        float(geometry["free_space_coverage_ratio"]),
        distance,
        view_cosine,
        float(entity["missed_opportunity_count"]),
        float(entity["observation_count"]),
        float(tick - int(entity["last_seen_tick"])),
        best_cosine,
        1.0 if unassigned else 0.0,
        *_state_one_hot(str(entity["state"])),
    ]
    _require(len(row) == len(EXISTENCE_FEATURES), "existence_feature_arity")
    return row


def build_assignment_inputs(
    frame: Mapping[str, Any], memory: Mapping[str, Any], *,
    local_count: int, global_count: int, local_radius_m: float,
    birth_neighbourhood_radius_m: float,
) -> dict[str, Any]:
    """Stage A: build recall, the association rows and the birth rows, and seal.

    白话：输入一帧和旧记忆，输出召回集合、两张特征矩阵、列顺序和一个封存摘要。
    它在任何模型运行前、任何私有文件打开前完成；此后私有数据怎么变，这份摘要都
    必须逐字节不变。例如只换模拟器实例映射，摘要必须一模一样。存在特征不在这一
    阶段，它要等求解之后由 `seal_solution_and_existence` 封存。
    """

    checked_frame = validate_cache_frame(frame)
    checked_memory = validate_memory(memory)
    tick = int(checked_frame["tick"])
    _require(tick == int(checked_memory["tick"]) + 1, "frame_tick_not_next")

    by_id = {
        str(entity["entity_id"]): entity for entity in checked_memory["entities"]
    }
    # A descriptor of the wrong width silently scores -1 against every entity,
    # which would look like "nothing matches" instead of a broken frontend.
    if checked_memory["entities"] and checked_frame["fragments"]:
        width = len(checked_memory["entities"][0]["descriptor_mean"])
        for fragment in checked_frame["fragments"]:
            _require(
                len(fragment["descriptor"]) == width,
                "frame_descriptor_width_differs_from_memory",
            )

    # The two cosine tables of the frame, computed once as matrices (bit-identical to the
    # per-pair scalar function; see cosine_matrix) and threaded through recall and the rows.
    entity_ids = [str(entity["entity_id"]) for entity in checked_memory["entities"]]
    fragment_descriptors = [fragment["descriptor"] for fragment in checked_frame["fragments"]]
    mean_matrix = cosine_matrix(fragment_descriptors, [entity["descriptor_mean"] for entity in checked_memory["entities"]])
    best_view_matrix = cosine_matrix(fragment_descriptors, [entity["best_view_descriptor"] for entity in checked_memory["entities"]])
    all_cosines: dict[str, dict[str, float]] = {}
    best_view_cosines: dict[str, dict[str, float]] = {}
    for index, fragment in enumerate(checked_frame["fragments"]):
        fragment_id = str(fragment["fragment_id"])
        all_cosines[fragment_id] = dict(zip(entity_ids, mean_matrix[index]))
        best_view_cosines[fragment_id] = dict(zip(entity_ids, best_view_matrix[index]))

    recall = build_recall(
        checked_frame, checked_memory, local_count=local_count,
        global_count=global_count, local_radius_m=local_radius_m,
        cosine_rows=all_cosines,
    )

    cosines: dict[str, dict[str, float]] = {}
    for fragment in checked_frame["fragments"]:
        fragment_id = str(fragment["fragment_id"])
        cosines[fragment_id] = {
            entity_id: all_cosines[fragment_id][entity_id]
            for entity_id in recall[fragment_id]
        }

    # "Mutual best" needs both directions, so it is resolved once here.
    best_for_entity: dict[str, tuple[float, str]] = {}
    for fragment_id, table in cosines.items():
        for entity_id, value in table.items():
            current = best_for_entity.get(entity_id)
            if current is None or (-value, fragment_id) < (-current[0], current[1]):
                best_for_entity[entity_id] = (value, fragment_id)

    # Canonical row order: the fragment id, not the order SAM happened to
    # return masks in.  Without this, swapping two fragments in the frame can
    # swap which of two equal-cost optima the solver returns.
    ordered_fragments = sorted(
        checked_frame["fragments"], key=lambda item: str(item["fragment_id"]),
    )

    association_rows: list[dict[str, Any]] = []
    birth_rows: list[dict[str, Any]] = []
    for fragment in ordered_fragments:
        fragment_id = str(fragment["fragment_id"])
        table = cosines[fragment_id]
        order = recall[fragment_id]
        best_entity = ""
        if table:
            best_entity = sorted(
                table.items(), key=lambda item: (-item[1], item[0]),
            )[0][0]
        for entity_id in order:
            association_rows.append({
                "fragment_id": fragment_id,
                "entity_id": entity_id,
                "features": association_feature_vector(
                    fragment, by_id[entity_id], recall_order=order,
                    cosines=table,
                    mutual_best=(
                        entity_id == best_entity
                        and best_for_entity.get(entity_id, (0.0, ""))[1] == fragment_id
                    ),
                    tick=tick,
                    best_view_cosine=best_view_cosines[fragment_id][entity_id],
                ),
            })
        birth_rows.append({
            "fragment_id": fragment_id,
            "features": birth_feature_vector(
                fragment, checked_memory, cosines=all_cosines[fragment_id],
                neighbourhood_radius_m=birth_neighbourhood_radius_m,
            ),
        })

    columns = sorted({row["entity_id"] for row in association_rows})
    columns += [
        f"{BIRTH_COLUMN_PREFIX}{str(fragment['fragment_id'])}"
        for fragment in ordered_fragments
    ]
    payload = {
        "frame_digest": checked_frame["frame_digest"],
        "tick": tick,
        "rows": [str(item["fragment_id"]) for item in birth_rows],
        "columns": columns,
        "recall": recall,
        "association_rows": association_rows,
        "birth_rows": birth_rows,
        "association_feature_order": list(ASSOCIATION_FEATURES),
        "birth_feature_order": list(BIRTH_FEATURES),
    }
    payload["seal_sha256"] = hashlib.sha256(
        canonical_json(payload).encode("utf-8")
    ).hexdigest()
    return payload


# --------------------------------------------------------------------------
# cost matrix and the rectangular solve
# --------------------------------------------------------------------------

def build_cost_matrix(
    inputs: Mapping[str, Any], *,
    association_logits: Mapping[str, float], birth_logits: Mapping[str, float],
) -> dict[str, Any]:
    """Turn head outputs into the rectangular cost matrix, cost = ``-logit``.

    白话：输入封存好的特征矩阵和三个头给出的 logit，输出代价矩阵：行是色块，列是
    被召回的实体加上每个色块自己的新建列。代价取 logit 的相反数，而不是
    `-log sigmoid(logit)`。例如两个色块竞争同一个实体时，用哪种变换会改出不同的
    最优配对。它不决定 logit 怎么来，也不做任何学习。

    Why ``-logit`` and not ``-log sigmoid(logit)``.  METHOD trains the
    association and birth heads with a per-fragment softmax cross-entropy, so
    the model learns ``p(column | row) ∝ exp(logit)``.  Maximising the joint
    log-likelihood of an assignment means minimising ``sum(-logit)``: the
    softmax normaliser is a per-row constant and every row picks exactly one
    column, so it cannot change which assignment wins.  ``-log sigmoid`` is a
    *nonlinear* monotone map of ``-logit``, so it reorders joint assignments
    across rows.  On 200,000 random two-by-two cases the two transforms chose
    a different optimum about one time in ten, and the gap in joint logit was
    not small, so this is a correctness bug rather than a scaling choice.
    """

    rows = list(inputs["rows"])
    columns = list(inputs["columns"])
    _require(len(columns) >= len(rows), "cost_matrix_more_rows_than_columns")
    if not rows:
        # A frame with no fragment is legal: the robot may be facing a blank
        # wall.  It yields an empty assignment and the existence pass still
        # runs, so this is not a construction failure.
        return {"rows": [], "columns": columns, "matrix": [], "forbidden_cost": 0.0}

    index_of_column = {name: index for index, name in enumerate(columns)}
    index_of_row = {name: index for index, name in enumerate(rows)}
    legal: list[tuple[int, int, float]] = []
    for row_index, fragment_id in enumerate(rows):
        birth_column = index_of_column[f"{BIRTH_COLUMN_PREFIX}{fragment_id}"]
        legal.append((row_index, birth_column, -_finite(
            birth_logits[fragment_id], "birth_logit_invalid",
        )))
    for item in inputs["association_rows"]:
        row_index = index_of_row[str(item["fragment_id"])]
        column_index = index_of_column[str(item["entity_id"])]
        key = f"{item['fragment_id']}|{item['entity_id']}"
        legal.append((row_index, column_index, -_finite(
            association_logits[key], "association_logit_invalid",
        )))

    forbidden = _forbidden_cost([value for _, _, value in legal], rows=len(rows))
    matrix = [[forbidden] * len(columns) for _ in rows]
    for row_index, column_index, value in legal:
        matrix[row_index][column_index] = value
    return {
        "rows": rows, "columns": columns, "matrix": matrix,
        "forbidden_cost": forbidden,
    }


def _forbidden_cost(legal_values: Sequence[float], *, rows: int) -> float:
    """A cost no optimal assignment can ever prefer, derived from the matrix.

    白话：召回之外的组合需要一个"永远不会被选"的代价。固定写 1e9 不安全，因为一
    个足够极端的 logit 会产生同样大甚至更大的合法代价。这里改为由当前矩阵的最大/
    最小合法代价和行数算出来，保证任何含禁止格的分配都严格贵于任意全合法分配。
    例如全部合法代价都在 [-5, 5] 且有 3 行时，禁止代价取 21。它不是一个可调参数。

    Any all-legal assignment costs at most ``rows * hi``.  An assignment that
    uses one forbidden cell costs at least ``B + (rows - 1) * lo``.  Requiring
    the second to exceed the first gives ``B > rows * hi - (rows - 1) * lo``.
    A fully legal assignment always exists because every fragment owns a birth
    column, so the bound is never vacuous.
    """

    _require(rows >= 1, "forbidden_cost_needs_a_row")
    _require(bool(legal_values), "forbidden_cost_needs_a_legal_value")
    hi = max(legal_values)
    lo = min(legal_values)
    return rows * hi - (rows - 1) * lo + 1.0


def solve_rectangular_assignment(matrix: Sequence[Sequence[float]]) -> list[int]:
    """Minimum-cost assignment, canonicalised to the lexicographic optimum.

    白话：输入行数不超过列数的代价矩阵，输出每一行选中的列号，使总代价最小；若存
    在多个代价相同的最优解，固定返回"按行依次取可行的最小列号"的那一个。例如两个
    色块都最像同一个实体时，只有一个能拿到它，另一个会被推向次优列或新建列。它是
    确定性的，且不依赖行列的偶然输入顺序。

    Written here rather than taken from scipy: scipy is not a dependency, and
    the tie-breaking has to be ours because a rectangular assignment usually
    has several optima.  The raw solve is a shortest-augmenting-path method
    with potentials; the canonicalisation afterwards is what makes the
    declared "smaller column first" semantics actually true, which the raw
    solve alone does not deliver.  The canonicalisation works on the equality
    subgraph of the raw solve's optimal potentials (D-224-X, ruling X5), so it
    never re-solves the whole matrix; the returned columns are identical to
    the earlier re-solving version, which the tests pin.
    """

    seed, u, v = _solve_rectangular_core_with_potentials(matrix)
    return _lexicographically_smallest_optimum(matrix, seed, u, v)


def _solve_rectangular_core(matrix: Sequence[Sequence[float]]) -> list[int]:
    """One optimal assignment, with no guarantee about which optimum."""

    return _solve_rectangular_core_with_potentials(matrix)[0]


def _solve_rectangular_core_with_potentials(
    matrix: Sequence[Sequence[float]],
) -> tuple[list[int], list[float], list[float]]:
    """One optimal assignment plus the optimal dual potentials ``(u, v)``.

    ``u`` has one entry per row and ``v`` one per column, zero-indexed.  At
    termination every cell satisfies ``matrix[r][c] - u[r] - v[c] >= 0``,
    every matched cell has reduced cost zero, ``v[c] <= 0`` everywhere and
    ``v[c] == 0`` for every unmatched column; that is exactly a dual optimum
    of the rectangular assignment LP, which the canonicalisation relies on.
    """

    rows = len(matrix)
    _require(rows > 0, "assignment_matrix_empty")
    columns = len(matrix[0])
    _require(
        all(len(row) == columns for row in matrix), "assignment_matrix_ragged",
    )
    _require(columns >= rows, "assignment_matrix_more_rows_than_columns")
    for row in matrix:
        for value in row:
            _finite(value, "assignment_matrix_value_invalid")

    infinity = float("inf")
    # 1-indexed potentials; column 0 is the sentinel free column.
    u = [0.0] * (rows + 1)
    v = [0.0] * (columns + 1)
    column_match = [0] * (columns + 1)
    path = [0] * (columns + 1)

    for row in range(1, rows + 1):
        column_match[0] = row
        free_column = 0
        minimum = [infinity] * (columns + 1)
        used = [False] * (columns + 1)
        while True:
            used[free_column] = True
            current_row = column_match[free_column]
            delta = infinity
            next_column = 0
            for column in range(1, columns + 1):
                if used[column]:
                    continue
                candidate = (
                    matrix[current_row - 1][column - 1]
                    - u[current_row] - v[column]
                )
                if candidate < minimum[column]:
                    minimum[column] = candidate
                    path[column] = free_column
                if minimum[column] < delta:
                    delta = minimum[column]
                    next_column = column
            _require(next_column != 0, "assignment_no_augmenting_column")
            for column in range(columns + 1):
                if used[column]:
                    u[column_match[column]] += delta
                    v[column] -= delta
                else:
                    minimum[column] -= delta
            free_column = next_column
            if column_match[free_column] == 0:
                break
        while free_column:
            previous = path[free_column]
            column_match[free_column] = column_match[previous]
            free_column = previous

    result = [0] * rows
    for column in range(1, columns + 1):
        if column_match[column] != 0:
            result[column_match[column] - 1] = column - 1
    return result, u[1:], v[1:]


def _lexicographically_smallest_optimum(
    matrix: Sequence[Sequence[float]], seed: Sequence[int],
    u: Sequence[float], v: Sequence[float],
) -> list[int]:
    """Canonicalise an optimum to the lexicographically smallest one.

    白话：一个矩形分配通常有多个代价相同的最优解。这一步把结果收敛到"按行依次取
    可行的最小列号"的那一个，使返回值只由矩阵和规范行列顺序决定。例如
    `[[1,0],[1,0]]` 的两个最优解 `[1,0]` 与 `[0,1]` 代价都是 1，这里固定返回
    `[0,1]`。它不改变最优代价，只消除并列时的任意性。

    Why the equality subgraph and not a re-solve per candidate.  The earlier
    version re-solved the whole matrix once per *tried* column, which is
    O(rows × columns) full solves: measured 1,337 sub-solves and 1.2 s at
    30×100 with float costs, 13,055 sub-solves and about two minutes at
    64×500 (D-224-X).  By complementary slackness, an assignment is optimal
    if and only if it uses only cells whose reduced cost ``matrix - u - v``
    is zero and matches every column whose potential ``v`` is negative.  So
    the search only has to try zero-reduced-cost cells, and "can the rest
    still be completed" is two bipartite matchings on that sparse graph
    (one saturating the remaining rows, one saturating the still-unmatched
    forced columns; Mendelsohn–Dulmage guarantees a common matching exists).
    The columns returned are the same as before; only the work changes.
    """

    rows = len(matrix)
    columns = len(matrix[0])
    scale = max(
        [1.0]
        + [abs(float(value)) for value in u]
        + [abs(float(value)) for value in v]
        + [abs(float(matrix[row][column])) for row, column in enumerate(seed)]
    )
    tolerance = 1e-9 * scale

    zero_columns: list[list[int]] = []
    for row in range(rows):
        cells: list[int] = []
        for column in range(columns):
            reduced = float(matrix[row][column]) - float(u[row]) - float(v[column])
            _require(reduced >= -tolerance, "assignment_dual_infeasible")
            if reduced <= tolerance:
                cells.append(column)
        zero_columns.append(cells)
    forced = frozenset(
        column for column in range(columns) if float(v[column]) < -tolerance
    )

    chosen: list[int] = []
    used: set[int] = set()
    for row in range(rows):
        for candidate in zero_columns[row]:
            if candidate in used:
                continue
            if _rest_is_feasible(
                zero_columns, first_row=row + 1, used=used | {candidate},
                forced=forced,
            ):
                chosen.append(candidate)
                used.add(candidate)
                break
        else:
            raise LeanAssignmentError("assignment_canonicalisation_failed")

    target = sum(float(matrix[row][column]) for row, column in enumerate(seed))
    total = sum(float(matrix[row][column]) for row, column in enumerate(chosen))
    _require(
        abs(total - target) <= rows * tolerance + 1e-9 * max(1.0, abs(target)),
        "assignment_canonicalisation_failed",
    )
    return chosen


def _rest_is_feasible(
    zero_columns: Sequence[Sequence[int]], *, first_row: int,
    used: set[int], forced: frozenset[int],
) -> bool:
    """Can rows ``first_row..`` still be completed into an optimum?

    Optimal completions use zero-reduced-cost cells only, must cover every
    remaining row and must cover every forced column not already used.  Both
    coverings are plain maximum bipartite matchings; if each exists on its
    own, a matching achieving both exists (Mendelsohn–Dulmage).
    """

    remaining = list(range(first_row, len(zero_columns)))
    adjacency = {
        row: [column for column in zero_columns[row] if column not in used]
        for row in remaining
    }
    if _matching_size(remaining, adjacency) != len(remaining):
        return False
    pending = sorted(forced - used)
    if not pending:
        return True
    reverse = {
        column: [row for row in remaining if column in adjacency[row]]
        for column in pending
    }
    return _matching_size(pending, reverse) == len(pending)


def _matching_size(
    left: Sequence[int], adjacency: Mapping[int, Sequence[int]],
) -> int:
    """Size of a maximum bipartite matching (Kuhn's augmenting paths)."""

    match_right: dict[int, int] = {}

    def augment(node: int, seen: set[int]) -> bool:
        for other in adjacency[node]:
            if other in seen:
                continue
            seen.add(other)
            if other not in match_right or augment(match_right[other], seen):
                match_right[other] = node
                return True
        return False

    return sum(1 for node in left if augment(node, set()))


def assignment_cost(
    matrix: Sequence[Sequence[float]], columns: Sequence[int],
) -> float:
    return sum(
        float(matrix[row][column]) for row, column in enumerate(columns)
    )


def solve_frame(
    inputs: Mapping[str, Any], *,
    association_logits: Mapping[str, float], birth_logits: Mapping[str, float],
) -> dict[str, Any]:
    """Solve one frame and return fragment -> column, plus the realised cost.

    白话：输入封存的特征与三个头的 logit，输出每个色块被分配到哪个实体或新建列。
    例如 f1 分到 e1、f2 分到自己的新建列。它不提交事务，也不做存在判定；那两步由
    调用方按 S0-01 的执行器完成。
    """

    built = build_cost_matrix(
        inputs, association_logits=association_logits, birth_logits=birth_logits,
    )
    matrix = built["matrix"]
    rows = list(inputs["rows"])
    columns = list(inputs["columns"])
    if not rows:
        return {
            "frame_digest": inputs["frame_digest"],
            "assignment": {},
            "total_cost": 0.0,
            "forbidden_cost": built["forbidden_cost"],
            "stage_a_seal_sha256": inputs["seal_sha256"],
        }
    chosen = solve_rectangular_assignment(matrix)
    assignment = {
        rows[index]: columns[column] for index, column in enumerate(chosen)
    }
    for fragment_id, column in assignment.items():
        _require(
            not column.startswith(BIRTH_COLUMN_PREFIX)
            or column == f"{BIRTH_COLUMN_PREFIX}{fragment_id}",
            "fragment_took_another_fragments_birth_column",
        )
    return {
        "frame_digest": inputs["frame_digest"],
        "assignment": assignment,
        "total_cost": assignment_cost(matrix, chosen),
        "forbidden_cost": built["forbidden_cost"],
        "stage_a_seal_sha256": inputs["seal_sha256"],
    }


def seal_solution_and_existence(
    solution: Mapping[str, Any], frame: Mapping[str, Any],
    memory: Mapping[str, Any], *, inputs: Mapping[str, Any],
) -> dict[str, Any]:
    """Stage B: seal the solve receipt together with the existence rows.

    白话：输入 stage A 的封存、当前帧、旧记忆和求解结果，输出第二份封存：分配回执
    加上每个"本帧应可见却未被分配"的实体的存在特征。两份封存都完成后，teacher 才
    可以打开 private。例如一个实体的最佳色块已经绑给别人，这条线索就落在这一份里。
    它不做存在判定（那要 τ_r），也不读取私有数据。

    The split exists because one existence feature is "the best-matching
    fragment is still unassigned", which has no meaning before the solve.
    Sealing only stage A would leave a third of the model's inputs outside the
    invariance guarantee, so the contract's claim about the feature tables
    would not actually hold.  During training the assignment fed in here must
    be the current policy's or a registered rule arm's, never the teacher's.
    """

    checked_frame = validate_cache_frame(frame)
    checked_memory = validate_memory(memory)
    _require(
        str(solution["stage_a_seal_sha256"]) == str(inputs["seal_sha256"]),
        "stage_b_does_not_follow_stage_a",
    )
    _require(
        str(solution["frame_digest"]) == str(checked_frame["frame_digest"]),
        "stage_b_frame_mismatch",
    )
    tick = int(checked_frame["tick"])
    assignment = dict(solution["assignment"])
    taken = {
        value for value in assignment.values()
        if not str(value).startswith(BIRTH_COLUMN_PREFIX)
    }

    # one cosine matrix for the frame (entities x fragments), bit-identical to the scalar calls
    fragment_ids = [str(fragment["fragment_id"]) for fragment in checked_frame["fragments"]]
    entity_rows = cosine_matrix([entity["descriptor_mean"] for entity in checked_memory["entities"]],
                                [fragment["descriptor"] for fragment in checked_frame["fragments"]])
    cosine_by_entity = {str(entity["entity_id"]): dict(zip(fragment_ids, row))
                        for entity, row in zip(checked_memory["entities"], entity_rows)}
    existence_rows: list[dict[str, Any]] = []
    for entity in sorted(
        checked_memory["entities"], key=lambda item: str(item["entity_id"]),
    ):
        entity_id = str(entity["entity_id"])
        if entity_id in taken or entity_id not in checked_frame["entity_geometry"]:
            continue
        existence_rows.append({
            "entity_id": entity_id,
            "features": existence_feature_vector(
                entity, checked_frame, assignment=assignment, tick=tick,
                fragment_cosines=cosine_by_entity[entity_id],
            ),
        })

    payload = {
        "frame_digest": str(checked_frame["frame_digest"]),
        "tick": tick,
        "stage_a_seal_sha256": str(inputs["seal_sha256"]),
        "assignment": {key: str(value) for key, value in sorted(assignment.items())},
        "total_cost": float(solution["total_cost"]),
        "existence_rows": existence_rows,
        "existence_feature_order": list(EXISTENCE_FEATURES),
    }
    payload["seal_sha256"] = hashlib.sha256(
        canonical_json(payload).encode("utf-8")
    ).hexdigest()
    return payload


# --------------------------------------------------------------------------
# private-mutation invariance
# --------------------------------------------------------------------------

def reference_untrained_scores(inputs: Mapping[str, Any], *, seed: int) -> list[float]:
    """A fixed deterministic stand-in for the untrained network's logits.

    白话：输入封存的特征矩阵和一个登记的 seed，输出一组确定性分数。它**不是**真
    的模型，只是让"未训练 logits 逐字节不变"这句话可被测试：同样的特征给同样的
    分数。例如只换私有标注而公开输入不变时，这组分数必须一模一样。
    """

    _int(seed, "reference_seed_invalid", minimum=0)
    rows = list(inputs.get("association_rows", [])) + list(inputs.get("birth_rows", []))
    rows += list(inputs.get("existence_rows", []))
    scores: list[float] = []
    for item in rows:
        payload = canonical_json([seed, item["features"]]).encode("utf-8")
        raw = int(hashlib.sha256(payload).hexdigest()[:8], 16)
        scores.append(raw / 0xFFFFFFFF)
    return scores


def assert_private_mutation_invariance(
    runs: Sequence[Mapping[str, Any]], *, seed: int,
) -> dict[str, Any]:
    """Require identical public bytes across runs that differ only privately.

    白话：输入同一公开前缀、不同私有标注下的若干次构建结果，输出一份不变性回执，
    并在召回顺序、特征矩阵、封存摘要或参考分数有任何差异时拒绝。例如只交换两个
    物体的模拟器实例 ID，这些都必须逐字节相同。它不证明整条流水线无泄漏，只证明
    这一层的公开产物不随私有数据变化。
    """

    _require(len(runs) >= 2, "invariance_needs_two_runs")
    baseline = runs[0]
    baseline_scores = reference_untrained_scores(baseline, seed=seed)
    guarded = ("recall", "association_rows", "birth_rows", "existence_rows",
               "assignment", "columns", "rows")
    for index, candidate in enumerate(runs[1:], start=1):
        _require(
            candidate["seal_sha256"] == baseline["seal_sha256"],
            f"seal_changed_under_private_mutation:{index}",
        )
        _require(
            set(candidate.keys()) == set(baseline.keys()),
            f"payload_shape_changed_under_private_mutation:{index}",
        )
        for name in guarded:
            if name not in baseline:
                continue
            _require(
                canonical_json(candidate[name]) == canonical_json(baseline[name]),
                f"{name}_changed_under_private_mutation:{index}",
            )
        _require(
            reference_untrained_scores(candidate, seed=seed) == baseline_scores,
            f"logits_changed_under_private_mutation:{index}",
        )
    return {
        "runs": len(runs),
        "seal_sha256": baseline["seal_sha256"],
        "score_count": len(baseline_scores),
        "guarded_fields": [name for name in guarded if name in baseline],
    }


# --------------------------------------------------------------------------
# machine contract
# --------------------------------------------------------------------------

def validate_assignment_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Check that the S0-03 machine contract agrees with this implementation."""

    _require(type(contract) is dict, "contract_not_object")
    _require(
        contract.get("schema_version") == CONTRACT_SCHEMA_VERSION,
        "contract_schema_version_invalid",
    )
    _require(contract.get("decision_id") == "D-224", "contract_decision_id_invalid")
    _require(contract.get("stage_id") == "S0-03", "contract_stage_id_invalid")

    required = {
        "cache_frame_fields", "association_feature_order",
        "existence_feature_order", "birth_feature_order", "recall_rule",
        "cost_matrix", "solver", "seal", "reid_adapter_head", "authorization",
    }
    missing = sorted(required - set(contract.keys()))
    _require(not missing, f"contract_missing_sections:{','.join(missing)}")

    _require(
        tuple(contract["cache_frame_fields"]) == CACHE_FRAME_FIELDS,
        "contract_cache_frame_fields_mismatch",
    )
    _require(
        tuple(contract["association_feature_order"]) == ASSOCIATION_FEATURES,
        "contract_association_feature_order_mismatch",
    )
    _require(
        tuple(contract["existence_feature_order"]) == EXISTENCE_FEATURES,
        "contract_existence_feature_order_mismatch",
    )
    _require(
        tuple(contract["birth_feature_order"]) == BIRTH_FEATURES,
        "contract_birth_feature_order_mismatch",
    )
    # Every boolean below is a claim the implementation actually enforces, so
    # flipping one in the contract must fail rather than quietly widen what the
    # paper is allowed to say.  An earlier version only checked three of them
    # and accepted "no local distance limit", "forbidden cost 42" and "not
    # sealed before private opens".
    for section, name, expected, code in (
        ("recall_rule", "global_channel_covers_every_state", True,
         "contract_recall_state_independence_weakened"),
        ("recall_rule", "global_channel_has_no_distance_limit", True,
         "contract_recall_distance_rule_weakened"),
        ("recall_rule", "local_channel_has_distance_limit", True,
         "contract_recall_local_channel_weakened"),
        ("recall_rule", "identical_for_all_five_arms", True,
         "contract_recall_sharing_weakened"),
        ("seal", "existence_features_computed_after_the_solve", True,
         "contract_existence_ordering_weakened"),
        ("seal", "private_mutation_must_not_change_public_bytes", True,
         "contract_invariance_weakened"),
        ("seal", "sealed_before_any_model_runs", True,
         "contract_stage_a_timing_weakened"),
        ("seal", "sealed_before_any_private_file_is_opened", True,
         "contract_private_timing_weakened"),
        ("seal", "teacher_assignment_must_not_feed_existence_features", True,
         "contract_teacher_assignment_leak_allowed"),
        ("cost_matrix", "forbidden_cost_is_derived_from_the_matrix", True,
         "contract_forbidden_cost_must_stay_derived"),
        ("solver", "canonicalisation_never_re_solves_the_matrix", True,
         "contract_solver_canonicalisation_claim_weakened"),
        ("solver", "columns_identical_to_v1_canonicalisation", True,
         "contract_solver_equivalence_claim_weakened"),
    ):
        _require(contract[section][name] is expected, code)

    _require(
        contract["cost_matrix"]["cost"] == "negative_logit",
        "contract_cost_transform_mismatch",
    )
    _require(
        contract["feature_rules"]["up_axis_index"] == UP_AXIS_INDEX,
        "contract_up_axis_mismatch",
    )
    _require(
        contract["solver"]["implementation"] == "self_written_no_new_dependency",
        "contract_solver_source_mismatch",
    )
    _require(
        contract["solver"]["tie_break"] == "lexicographically_smallest_optimum",
        "contract_solver_tie_break_mismatch",
    )
    _require(
        contract["reid_adapter_head"]["shared_bytes_across_all_arms"] is True,
        "contract_reid_sharing_weakened",
    )
    _require(
        contract["reid_adapter_head"]["counts_against_config_budget"] is False,
        "contract_reid_budget_mismatch",
    )

    # A registered value is either still open, and then it must say so in
    # policy_values_without_defaults, or frozen, and then it must have left
    # that list and equal the constant this implementation binds (D-224-S1
    # ruling 24: values change only by ledger).  Requiring null outright made
    # it impossible to ever record the value the contract was written to carry.
    open_values = contract["policy_values_without_defaults"]
    frozen_constants = {
        "reid_adapter_head.output_dimension": REID_OUTPUT_DIMENSION,
        "reid_adapter_head.selection_rule_threshold": REID_SELECTION_RULE_THRESHOLD,
        "recall_rule.local_count": RECALL_LOCAL_COUNT,
        "recall_rule.global_count": RECALL_GLOBAL_COUNT,
        "recall_rule.local_radius_m": RECALL_LOCAL_RADIUS_M,
        "recall_rule.birth_neighbourhood_radius_m": RECALL_BIRTH_NEIGHBOURHOOD_RADIUS_M,
    }
    for section, names in (
        ("recall_rule", ("local_count", "global_count", "local_radius_m",
                         "birth_neighbourhood_radius_m")),
        ("cost_matrix", ("existence_threshold_tau_r",)),
        ("seal", ("reference_score_seed",)),
        ("reid_adapter_head", ("output_dimension", "selection_rule_threshold")),
    ):
        for name in names:
            registered = f"{section}.{name}"
            value = contract[section][name]
            if value is None:
                _require(registered in open_values,
                         f"contract_{section}_{name}_null_but_not_registered_as_open")
            else:
                _require(registered not in open_values,
                         f"contract_{section}_{name}_frozen_but_still_listed_as_open")
                _require(registered in frozen_constants,
                         f"contract_{section}_{name}_frozen_without_a_bound_constant")
                _require(value == frozen_constants[registered],
                         f"contract_{section}_{name}_differs_from_the_frozen_constant")

    # Ruling 46: the four recall values freeze once, after the S1-04 curve on
    # the development cache; ruling 47: the ReID projection is trained on the
    # first 30 cached development houses and judged on the last 12 only.
    recall = contract["recall_rule"]
    _require(recall["four_values_frozen_once_after_the_s1_04_curve"] is True,
             "contract_recall_freeze_rule_weakened")
    _require(recall["curve_is_measured_on_the_development_cache_only"] is True,
             "contract_recall_curve_split_weakened")
    _require(recall["chosen_by_maximum_memory_size_not_per_arm"] is True,
             "contract_recall_per_arm_tuning_allowed")
    holdout = contract["reid_adapter_head"]["holdout"]
    _require(holdout["training_houses"] == REID_TRAINING_HOUSES
             and holdout["selection_houses"] == REID_SELECTION_HOUSES,
             "contract_reid_holdout_sizes_mismatch")
    for name in (
        "development_block_ordered_by_hash_prefix",
        "training_houses_are_the_first_30_of_the_cached_development_block",
        "selection_houses_are_the_last_12_of_the_cached_development_block",
        "training_and_selection_houses_are_disjoint",
        "contrastive_labels_come_from_private_truth_on_training_houses_only",
        "separation_for_selection_is_measured_on_selection_houses_only",
        "a_house_without_a_cache_is_skipped_and_counted_never_replaced",
    ):
        _require(holdout[name] is True, f"contract_reid_holdout_weakened:{name}")

    # S1-05: the selection the contract delegated to that stage is recorded here and bound to
    # the constants above; the choice can be read by every later stage and changed by none.
    result = contract["reid_adapter_head"].get("selection_result")
    _require(type(result) is dict, "contract_reid_selection_result_missing")
    _require(result.get("selected_by_stage") == "S1-05", "contract_reid_selection_stage_mismatch")
    _require(result.get("selected") == SELECTED_DESCRIPTOR,
             "contract_reid_selection_differs_from_the_frozen_constant")
    _require(result.get("source_descriptor_set") == SELECTED_DESCRIPTOR_SOURCE_SET,
             "contract_reid_selection_source_set_differs_from_the_frozen_constant")
    _require(result.get("frozen_descriptor_baseline") == FROZEN_DESCRIPTOR_BASELINE,
             "contract_reid_selection_baseline_differs_from_the_frozen_constant")
    _require(result.get("weights_sha256") == SELECTED_REID_WEIGHTS_SHA256,
             "contract_reid_selection_weights_digest_differs_from_the_frozen_constant")
    if SELECTED_DESCRIPTOR.startswith("reid_projection:"):
        _require(result.get("frozen_descriptor_baseline_must_be_reported_alongside") is True,
                 "contract_reid_selection_baseline_report_dropped")
        _require(SELECTED_DESCRIPTOR == f"reid_projection:{SELECTED_DESCRIPTOR_SOURCE_SET}",
                 "contract_reid_selection_source_set_inconsistent")
    _require(result.get("no_further_descriptor_change") is True, "contract_reid_selection_reopenable")
    _require(result.get("cache_bytes_unchanged") is True, "contract_reid_selection_rewrites_the_cache")

    _require(
        all(value is False for value in contract["authorization"].values()),
        "contract_authorization_must_be_all_false",
    )
    return clone_json(dict(contract))


__all__ = [
    "ASSOCIATION_FEATURES",
    "BIRTH_COLUMN_PREFIX",
    "BIRTH_FEATURES",
    "REID_OUTPUT_DIMENSION",
    "REID_SELECTION_HOUSES",
    "REID_SELECTION_RULE_THRESHOLD",
    "SELECTED_DESCRIPTOR",
    "SELECTED_DESCRIPTOR_SOURCE_SET",
    "FROZEN_DESCRIPTOR_BASELINE",
    "SELECTED_REID_WEIGHTS_SHA256",
    "REID_TRAINING_HOUSES",
    "UP_AXIS_INDEX",
    "CACHE_FRAME_FIELDS",
    "CONTRACT_SCHEMA_VERSION",
    "EXISTENCE_FEATURES",
    "LeanAssignmentError",
    "assert_private_mutation_invariance",
    "assignment_cost",
    "association_feature_vector",
    "birth_feature_vector",
    "build_assignment_inputs",
    "build_cost_matrix",
    "build_recall",
    "cosine_matrix",
    "existence_feature_vector",
    "recall_for_fragment",
    "reference_untrained_scores",
    "seal_solution_and_existence",
    "solve_frame",
    "solve_rectangular_assignment",
    "validate_assignment_contract",
    "validate_cache_frame",
]
