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

from cpmt.hashing import canonical_json, clone_json

from vsmt.graph_ops import cosine_similarity
from vsmt.lean_memory import ENTITY_STATES, validate_memory


CONTRACT_SCHEMA_VERSION = "vsmt-lean-s0-assignment-v1"

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
    "supported_by_agrees",
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

#: Cost used for a pair the recall rule did not return.  It is finite so the
#: solver stays well defined, and large enough that any legal pairing or any
#: birth is preferred to it.
FORBIDDEN_COST = 1.0e9


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
    active_count: int, dormant_count: int, active_radius_m: float,
) -> list[str]:
    """Return the recalled entity ids for one fragment, in a fixed order.

    白话：输入一个色块和旧记忆，输出这次要为它考虑的实体列表。活动实体按余弦取
    前 k 个且质心距离不超过登记半径；休眠与已撤回实体按余弦取前 k′ 个且**不设距
    离上限**，因为被搬走的物体可以出现在很远处。例如杯子从厨房搬到卧室后，只有
    不设上限的那一路才能把旧杯子召回来。它不判断谁是正确答案，也不读取私有身份。

    Ties in cosine are broken by ``entity_id`` so the order never depends on
    dict iteration or on the order entities happen to sit in the memory list.
    """

    k_active = _int(active_count, "recall_active_count_invalid", minimum=0)
    k_dormant = _int(dormant_count, "recall_dormant_count_invalid", minimum=0)
    radius = _finite(active_radius_m, "recall_active_radius_invalid")
    _require(radius > 0.0, "recall_active_radius_invalid")

    descriptor = fragment["descriptor"]
    centroid = fragment["centroid_m"]
    active: list[tuple[float, str]] = []
    resting: list[tuple[float, str]] = []
    for entity in memory["entities"]:
        entity_id = str(entity["entity_id"])
        cosine = cosine_similarity(descriptor, entity["descriptor_mean"])
        if entity["state"] == "active":
            if _distance(centroid, entity["centroid_m"]) <= radius:
                active.append((cosine, entity_id))
        else:
            resting.append((cosine, entity_id))

    active.sort(key=lambda item: (-item[0], item[1]))
    resting.sort(key=lambda item: (-item[0], item[1]))
    return (
        [item[1] for item in active[:k_active]]
        + [item[1] for item in resting[:k_dormant]]
    )


def build_recall(
    frame: Mapping[str, Any], memory: Mapping[str, Any], *,
    active_count: int, dormant_count: int, active_radius_m: float,
) -> dict[str, list[str]]:
    """Recall for every fragment of the frame, keyed by fragment id."""

    return {
        str(fragment["fragment_id"]): recall_for_fragment(
            fragment, memory, active_count=active_count,
            dormant_count=dormant_count, active_radius_m=active_radius_m,
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
    mutual_best: bool, tick: int,
) -> list[float]:
    """One association feature row, in the frozen ASSOCIATION_FEATURES order."""

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
        cosine_similarity(fragment["descriptor"], entity["best_view_descriptor"]),
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
        1.0 if fragment["supported_by"] == entity["supported_by"] else 0.0,
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
        cosine = cosine_similarity(
            fragment["descriptor"], entity["descriptor_mean"],
        )
        candidate = str(fragment["fragment_id"])
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
    active_count: int, dormant_count: int, active_radius_m: float,
    birth_neighbourhood_radius_m: float,
) -> dict[str, Any]:
    """Build recall, the association rows and the birth rows, then seal them.

    白话：输入一帧和旧记忆，输出召回集合、两张特征矩阵、列顺序和一个封存摘要。
    它在任何模型运行前、任何私有文件打开前完成；此后私有数据怎么变，这份摘要都
    必须逐字节不变。例如只换模拟器实例映射，摘要必须一模一样。
    """

    checked_frame = validate_cache_frame(frame)
    checked_memory = validate_memory(memory)
    tick = int(checked_frame["tick"])
    _require(tick == int(checked_memory["tick"]) + 1, "frame_tick_not_next")

    by_id = {
        str(entity["entity_id"]): entity for entity in checked_memory["entities"]
    }
    recall = build_recall(
        checked_frame, checked_memory, active_count=active_count,
        dormant_count=dormant_count, active_radius_m=active_radius_m,
    )

    cosines: dict[str, dict[str, float]] = {}
    for fragment in checked_frame["fragments"]:
        fragment_id = str(fragment["fragment_id"])
        cosines[fragment_id] = {
            entity_id: cosine_similarity(
                fragment["descriptor"], by_id[entity_id]["descriptor_mean"],
            )
            for entity_id in recall[fragment_id]
        }

    # "Mutual best" needs both directions, so it is resolved once here.
    best_for_entity: dict[str, tuple[float, str]] = {}
    for fragment_id, table in cosines.items():
        for entity_id, value in table.items():
            current = best_for_entity.get(entity_id)
            if current is None or (-value, fragment_id) < (-current[0], current[1]):
                best_for_entity[entity_id] = (value, fragment_id)

    association_rows: list[dict[str, Any]] = []
    birth_rows: list[dict[str, Any]] = []
    for fragment in checked_frame["fragments"]:
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
                ),
            })
        birth_rows.append({
            "fragment_id": fragment_id,
            "features": birth_feature_vector(
                fragment, checked_memory, cosines=table,
                neighbourhood_radius_m=birth_neighbourhood_radius_m,
            ),
        })

    columns = sorted({row["entity_id"] for row in association_rows})
    columns += [
        f"{BIRTH_COLUMN_PREFIX}{str(fragment['fragment_id'])}"
        for fragment in checked_frame["fragments"]
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
) -> list[list[float]]:
    """Turn head outputs into the rectangular cost matrix ``-log sigmoid(x)``.

    白话：输入封存好的特征矩阵和三个头给出的 logit，输出代价矩阵：行是色块，列是
    被召回的实体加上每个色块自己的新建列。召回之外的组合给一个有限但很大的代价，
    因此求解器永远不会选它。例如一个实体没有被某个色块召回，它们就不可能配对。
    它不决定 logit 怎么来，也不做任何学习。
    """

    rows = list(inputs["rows"])
    columns = list(inputs["columns"])
    _require(bool(columns), "cost_matrix_has_no_column")
    _require(len(columns) >= len(rows), "cost_matrix_more_rows_than_columns")

    index_of_column = {name: index for index, name in enumerate(columns)}
    index_of_row = {name: index for index, name in enumerate(rows)}
    matrix = [[FORBIDDEN_COST] * len(columns) for _ in rows]
    for row_index, fragment_id in enumerate(rows):
        birth_column = index_of_column[f"{BIRTH_COLUMN_PREFIX}{fragment_id}"]
        matrix[row_index][birth_column] = _neg_log_sigmoid(
            _finite(birth_logits[fragment_id], "birth_logit_invalid")
        )
    for item in inputs["association_rows"]:
        row_index = index_of_row[str(item["fragment_id"])]
        column_index = index_of_column[str(item["entity_id"])]
        key = f"{item['fragment_id']}|{item['entity_id']}"
        matrix[row_index][column_index] = _neg_log_sigmoid(
            _finite(association_logits[key], "association_logit_invalid")
        )
    return matrix


def _neg_log_sigmoid(logit: float) -> float:
    # softplus(-x), evaluated in the numerically stable branch.
    if logit >= 0.0:
        return math.log1p(math.exp(-logit))
    return -logit + math.log1p(math.exp(logit))


def solve_rectangular_assignment(matrix: Sequence[Sequence[float]]) -> list[int]:
    """Minimum-cost assignment of every row to a distinct column.

    白话：输入行数不超过列数的代价矩阵，输出每一行选中的列号，使总代价最小。例
    如两个色块都最像同一个实体时，只有一个能拿到它，另一个会被推向次优列或新建
    列。它是确定性的：同样的矩阵永远给出同一组列号。

    This is the Jonker-Volgenant style shortest augmenting path method with
    potentials, O(rows^2 * columns).  It is written here because scipy is not
    a dependency and because the tie-breaking must be ours: ties are resolved
    towards the smaller column index, so the result depends only on the
    matrix and on the caller's own canonical row and column order.
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
    return result


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

    matrix = build_cost_matrix(
        inputs, association_logits=association_logits, birth_logits=birth_logits,
    )
    chosen = solve_rectangular_assignment(matrix)
    rows = list(inputs["rows"])
    columns = list(inputs["columns"])
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
        "seal_sha256": inputs["seal_sha256"],
    }


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
    scores: list[float] = []
    for item in list(inputs["association_rows"]) + list(inputs["birth_rows"]):
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
    for index, candidate in enumerate(runs[1:], start=1):
        _require(
            candidate["seal_sha256"] == baseline["seal_sha256"],
            f"seal_changed_under_private_mutation:{index}",
        )
        _require(
            canonical_json(candidate["recall"]) == canonical_json(baseline["recall"]),
            f"recall_changed_under_private_mutation:{index}",
        )
        _require(
            canonical_json(candidate["association_rows"])
            == canonical_json(baseline["association_rows"]),
            f"features_changed_under_private_mutation:{index}",
        )
        _require(
            reference_untrained_scores(candidate, seed=seed) == baseline_scores,
            f"logits_changed_under_private_mutation:{index}",
        )
    return {
        "runs": len(runs),
        "seal_sha256": baseline["seal_sha256"],
        "score_count": len(baseline_scores),
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
    _require(
        contract["recall_rule"]["dormant_and_retracted_have_no_distance_limit"] is True,
        "contract_recall_distance_rule_weakened",
    )
    _require(
        contract["seal"]["existence_features_computed_after_the_solve"] is True,
        "contract_existence_ordering_weakened",
    )
    _require(
        contract["seal"]["private_mutation_must_not_change_public_bytes"] is True,
        "contract_invariance_weakened",
    )
    _require(
        contract["solver"]["implementation"] == "self_written_no_new_dependency",
        "contract_solver_source_mismatch",
    )
    _require(
        contract["solver"]["tie_break"] == "smaller_column_index",
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

    for section, names in (
        ("recall_rule", ("active_count", "dormant_count", "active_radius_m",
                         "birth_neighbourhood_radius_m")),
        ("cost_matrix", ("existence_threshold_tau_r",)),
        ("seal", ("reference_score_seed",)),
        ("reid_adapter_head", ("output_dimension", "selection_rule_threshold")),
    ):
        for name in names:
            _require(
                contract[section][name] is None,
                f"contract_{section}_{name}_must_be_null_before_freeze",
            )

    _require(
        all(value is False for value in contract["authorization"].values()),
        "contract_authorization_must_be_all_false",
    )
    return clone_json(dict(contract))


__all__ = [
    "ASSOCIATION_FEATURES",
    "BIRTH_COLUMN_PREFIX",
    "BIRTH_FEATURES",
    "CACHE_FRAME_FIELDS",
    "CONTRACT_SCHEMA_VERSION",
    "EXISTENCE_FEATURES",
    "FORBIDDEN_COST",
    "LeanAssignmentError",
    "assert_private_mutation_invariance",
    "assignment_cost",
    "association_feature_vector",
    "birth_feature_vector",
    "build_assignment_inputs",
    "build_cost_matrix",
    "build_recall",
    "existence_feature_vector",
    "recall_for_fragment",
    "reference_untrained_scores",
    "solve_frame",
    "solve_rectangular_assignment",
    "validate_assignment_contract",
    "validate_cache_frame",
]
