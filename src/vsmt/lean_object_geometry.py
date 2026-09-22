"""D-224-S1 ruling 45 / S1-04: the per-episode private object geometry table and the truth boxes
built from it, as a pure core.

The S0-02 private plane records, per frame, only the world position (x/y/z) of every visible
object.  S0-04's truth table and the S1-04 fragment-versus-truth IoU diagnostic both need each
object's whole-object axis-aligned box, which was never written.  Ruling 45 (2026-09-22) fixes the
source: one reload of the house in the frozen simulator, at the house-authored agent pose and
before any action, gives every object's initial position, rotation and axis-aligned box; the box
of frame ``t`` is that initial box translated by the recorded private position, expressed in the
episode frame (world coordinates minus the observation-0 camera position, which is the origin of
every public pose).  ``move`` and ``add`` are executed by ``PlaceObjectAtPoint``, which keeps the
object rotation, so the only unrecorded change is the physics settle after placement; that
residual is measured, not assumed away, by the checks at the bottom of this module.

No simulator, no torch and no model are imported here.  The reload tool
(``ops/vsmt/lean_s1_04_object_geometry.py``) hands in what AI2-THOR's metadata reported and this
module validates it, builds the table, and turns table plus private frame records into the truth
objects S0-04 consumes.  The observed-set box (the union of back-projected private masks over the
frames an object was seen in) is also computed here, but it is a proxy that ruling 45 allows only
as a comparison column in the S1-04 report, never as the truth box.

白话：这个模块解决"评价器和 S1-04 诊断要真值整物体包围盒，而私有面逐帧只有 x/y/z"的缺口。
输入是模拟器重载一次读到的每个物体的初始位置、朝向、盒中心与尺寸，加上私有逐帧记录里的位置
和干预日志；输出是每帧每个物体的真值盒（episode 系）与在场标志，以及两项残差检查。例如一把
椅子初始盒中心 (3.1, 0.45, 2.0)、尺寸 (0.5, 0.9, 0.5)，第 t 帧记录它在 (5.6, 0.45, 2.0)，那么第
t 帧的盒子就是初始盒平移 (2.5, 0, 0) 再减去原点。它**不等于**逐帧真值：放置后的物理沉降没有
记录，是登记的残差；它也不做身份判定、不打开任何模型。

The module must stay importable under the simulator environment's Python 3.9 (the reload tool
runs there), so it uses no 3.10+ syntax at runtime.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from cpmt.hashing import canonical_json
from vsmt.l1_entities import _camera_values
from vsmt.lean_intervention import PRIVATE_HOUSE_GEOMETRY_FIELDS, PRIVATE_HOUSE_GEOMETRY_FILE

#: The table's schema version; the reload tool writes it, every reader checks it.
TABLE_SCHEMA_VERSION = "vsmt-lean-s1-04-object-geometry-v1"
#: Top-level fields of one episode's table, in order.
TABLE_FIELDS = (
    "schema_version", "episode_id", "house_id", "source_index", "code_commit",
    "episode_origin_world_m", "agent_pose_at_reload", "objects", "objects_without_box",
    "reload_digest",
)
#: Per-object fields: bound to the S0-02 v3 contract so the two cannot drift apart.
OBJECT_FIELDS = PRIVATE_HOUSE_GEOMETRY_FIELDS
#: The file name the S0-02 v3 contract registers for the table.
TABLE_FILE_NAME = PRIVATE_HOUSE_GEOMETRY_FILE
#: Position drift of a non-intervened object beyond this is reported as a residual, not hidden.
DRIFT_TOLERANCE_M = 0.01
#: Containment checks expand the truth box by this margin before counting back-projected points:
#: a depth pixel on an object's silhouette lands on its surface, and the simulator's box is tight.
CONTAINMENT_MARGIN_M = 0.05


class LeanObjectGeometryError(ValueError):
    """Raised with a short machine-readable code."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LeanObjectGeometryError(code)


def _vector3(value: Any, code: str) -> list[float]:
    _require(isinstance(value, (list, tuple)) and len(value) == 3, code)
    out = [float(v) for v in value]
    _require(all(math.isfinite(v) for v in out), code)
    return out


def _xyz(value: Any, code: str) -> list[float]:
    """AI2-THOR writes vectors as {x, y, z}; the table stores [x, y, z]."""

    if isinstance(value, Mapping):
        _require(set(value.keys()) >= {"x", "y", "z"}, code)
        return _vector3([value["x"], value["y"], value["z"]], code)
    return _vector3(value, code)


def sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# the table
# --------------------------------------------------------------------------

def build_geometry_table(
    *, episode_id: str, house_id: str, source_index: int, code_commit: str,
    metadata_objects: Sequence[Mapping[str, Any]], camera_position_world: Mapping[str, Any],
    agent_pose: Mapping[str, Any],
) -> dict[str, Any]:
    """One episode's object geometry table from the reload's metadata.

    白话：输入模拟器重载后 ``metadata.objects`` 的原始列表、此刻的相机世界位置（就是观测 0 的原
    点）和 agent 位姿，输出按 ``object_id`` 排序的表。没有 ``axisAlignedBoundingBox`` 的物体照
    样登记，但盒字段为 null 并单独计数，不静默丢掉。它不改任何一个数，只换成 [x, y, z] 列表。
    """

    _require(isinstance(episode_id, str) and bool(episode_id), "episode_id_invalid")
    _require(isinstance(house_id, str) and bool(house_id), "house_id_invalid")
    _require(isinstance(source_index, int) and source_index >= 0, "source_index_invalid")
    _require(isinstance(code_commit, str) and bool(code_commit), "code_commit_invalid")
    rows: list[dict[str, Any]] = []
    without_box: list[str] = []
    seen: set[str] = set()
    for item in metadata_objects:
        object_id = item["objectId"]
        _require(isinstance(object_id, str) and bool(object_id), "object_id_invalid")
        _require(object_id not in seen, "object_id_duplicate:" + object_id)
        seen.add(object_id)
        box = item.get("axisAlignedBoundingBox") or {}
        center = box.get("center")
        size = box.get("size")
        has_box = isinstance(center, Mapping) and isinstance(size, Mapping)
        if not has_box:
            without_box.append(object_id)
        row = {
            "object_id": object_id,
            "asset_id": item.get("assetId"),
            "object_type": item.get("objectType"),
            "pickupable": bool(item.get("pickupable")),
            "receptacle": bool(item.get("receptacle")),
            "initial_position_world_m": _xyz(item["position"], "object_position_invalid:" + object_id),
            "initial_rotation_degrees": _xyz(item["rotation"], "object_rotation_invalid:" + object_id),
            "initial_aabb_center_world_m": _xyz(center, "object_box_center_invalid:" + object_id) if has_box else None,
            "initial_aabb_size_m": _xyz(size, "object_box_size_invalid:" + object_id) if has_box else None,
        }
        if has_box:
            _require(all(v >= 0.0 for v in row["initial_aabb_size_m"]), "object_box_size_negative:" + object_id)
        rows.append(row)
    rows.sort(key=lambda row: row["object_id"])
    origin = _xyz(camera_position_world, "camera_position_invalid")
    table = {
        "schema_version": TABLE_SCHEMA_VERSION,
        "episode_id": episode_id,
        "house_id": house_id,
        "source_index": source_index,
        "code_commit": code_commit,
        "episode_origin_world_m": origin,
        "agent_pose_at_reload": {
            "position": _xyz(agent_pose["position"], "agent_position_invalid"),
            "rotation": _xyz(agent_pose["rotation"], "agent_rotation_invalid"),
            "horizon": float(agent_pose.get("cameraHorizon", agent_pose.get("horizon", 0.0))),
        },
        "objects": rows,
        "objects_without_box": sorted(without_box),
        "reload_digest": sha({"origin": origin, "objects": rows}),
    }
    return validate_geometry_table(table)


def validate_geometry_table(table: Mapping[str, Any]) -> dict[str, Any]:
    """Check a table's shape and numbers; returns a plain copy."""

    _require(isinstance(table, Mapping), "table_not_object")
    _require(tuple(table.keys()) == TABLE_FIELDS, "table_fields_invalid")
    _require(table["schema_version"] == TABLE_SCHEMA_VERSION, "table_schema_version_invalid")
    origin = _vector3(table["episode_origin_world_m"], "table_origin_invalid")
    rows = table["objects"]
    _require(isinstance(rows, list), "table_objects_invalid")
    ids: list[str] = []
    for row in rows:
        _require(isinstance(row, Mapping) and tuple(row.keys()) == OBJECT_FIELDS, "object_fields_invalid")
        _require(isinstance(row["object_id"], str) and bool(row["object_id"]), "object_id_invalid")
        ids.append(row["object_id"])
        _vector3(row["initial_position_world_m"], "object_position_invalid:" + row["object_id"])
        _vector3(row["initial_rotation_degrees"], "object_rotation_invalid:" + row["object_id"])
        if row["initial_aabb_center_world_m"] is None or row["initial_aabb_size_m"] is None:
            _require(row["initial_aabb_center_world_m"] is None and row["initial_aabb_size_m"] is None,
                     "object_box_half_missing:" + row["object_id"])
            _require(row["object_id"] in table["objects_without_box"], "object_box_missing_not_counted:" + row["object_id"])
        else:
            _vector3(row["initial_aabb_center_world_m"], "object_box_center_invalid:" + row["object_id"])
            size = _vector3(row["initial_aabb_size_m"], "object_box_size_invalid:" + row["object_id"])
            _require(all(v >= 0.0 for v in size), "object_box_size_negative:" + row["object_id"])
    _require(ids == sorted(ids) and len(set(ids)) == len(ids), "table_objects_not_sorted_unique")
    _require(sorted(table["objects_without_box"]) == list(table["objects_without_box"]), "objects_without_box_not_sorted")
    _require(set(table["objects_without_box"]) <= set(ids), "objects_without_box_unknown")
    _require(table["reload_digest"] == sha({"origin": origin, "objects": rows}), "table_digest_mismatch")
    return {key: (list(value) if isinstance(value, list) else value) for key, value in table.items()}


# --------------------------------------------------------------------------
# boxes
# --------------------------------------------------------------------------

def world_to_episode(point_world: Sequence[float], origin_world: Sequence[float]) -> list[float]:
    """The public poses are world minus the observation-0 camera position; so are the truth boxes."""

    return [float(a) - float(b) for a, b in zip(point_world, origin_world)]


def truth_box(row: Mapping[str, Any], position_world: Sequence[float], origin_world: Sequence[float]) -> tuple[list[float], list[float]]:
    """The object's box at a recorded world position, in the episode frame.

    白话：初始盒中心跟着"记录位置 − 初始位置"平移（盒尺寸不变，因为 PlaceObjectAtPoint 保持
    朝向），再减去观测 0 的相机位置换到 episode 系。输出 (min, max)。物体没有盒就拒绝，不猜。
    """

    _require(row["initial_aabb_center_world_m"] is not None, "object_has_no_box:" + str(row["object_id"]))
    center = row["initial_aabb_center_world_m"]
    size = row["initial_aabb_size_m"]
    initial = row["initial_position_world_m"]
    moved = [float(c) + (float(p) - float(i)) for c, p, i in zip(center, position_world, initial)]
    centre = world_to_episode(moved, origin_world)
    lower = [c - float(s) / 2.0 for c, s in zip(centre, size)]
    upper = [c + float(s) / 2.0 for c, s in zip(centre, size)]
    return lower, upper


def aabb_iou(
    lower_a: Sequence[float], upper_a: Sequence[float],
    lower_b: Sequence[float], upper_b: Sequence[float],
) -> float:
    """3D axis-aligned IoU, the same arithmetic as the S0-04 evaluator (pinned by test)."""

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
    return overlap / union if union > 0.0 else 0.0


def union_box(
    lower_a: Sequence[float] | None, upper_a: Sequence[float] | None,
    lower_b: Sequence[float], upper_b: Sequence[float],
) -> tuple[list[float], list[float]]:
    """Grow an accumulated box by another box (the observed-set proxy grows this way)."""

    if lower_a is None or upper_a is None:
        return [float(v) for v in lower_b], [float(v) for v in upper_b]
    return ([min(float(a), float(b)) for a, b in zip(lower_a, lower_b)],
            [max(float(a), float(b)) for a, b in zip(upper_a, upper_b)])


# --------------------------------------------------------------------------
# presence and position over an episode
# --------------------------------------------------------------------------

class EpisodeTruthTracker:
    """Present-or-not and latest known world position of every table object, frame by frame.

    白话：它把"物体现在在不在、在哪"这两件私有事实按帧维护出来。规则：没被 remove 的物体一直
    在场；被 remove 的物体从不可观测窗口的最后一帧之后起不在场（runner 在过渡段最后一帧之后、扫
    掠二第一帧之前执行全部干预）。位置取最近一次私有记录看见它的位置；被 move/add 的物体在窗口
    结束后、第一次被重新看见之前，用干预日志的放置点作位置并标注来源为 ``placement_point``。它
    不看任何公开量，也不判断方法对不对。
    """

    def __init__(
        self, table: Mapping[str, Any], *, executed_interventions: Sequence[Mapping[str, Any]],
        window: Sequence[int] | None,
    ) -> None:
        self.table = validate_geometry_table(table)
        self.rows = {row["object_id"]: row for row in self.table["objects"]}
        self.origin = self.table["episode_origin_world_m"]
        self.position: dict[str, list[float]] = {
            oid: list(row["initial_position_world_m"]) for oid, row in self.rows.items()}
        self.position_source: dict[str, str] = {oid: "initial" for oid in self.rows}
        self.removed: set[str] = set()
        self.relocated: dict[str, list[float]] = {}
        for row in executed_interventions:
            if not row.get("executed", True):
                continue
            oid = row["object_id"]
            _require(oid in self.rows, "intervened_object_not_in_table:" + str(oid))
            kind = row["kind"]
            if kind == "remove":
                self.removed.add(oid)
            elif kind in ("move", "add"):
                point = row.get("point")
                _require(point is not None, "relocation_without_point:" + str(oid))
                self.relocated[oid] = _xyz(point, "relocation_point_invalid:" + str(oid))
            else:
                raise LeanObjectGeometryError("intervention_kind_unknown:" + str(kind))
        if window is None:
            _require(not self.removed and not self.relocated, "interventions_without_window")
            self.window_end = None
        else:
            _require(len(window) == 2 and int(window[0]) <= int(window[1]), "window_invalid")
            self.window_end = int(window[1])
        self.last_frame_index = -1
        self.relocations_applied = False

    def intervened_ids(self) -> set[str]:
        return set(self.removed) | set(self.relocated)

    def update(self, frame_index: int, private_record: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
        """Advance to ``frame_index`` with that frame's private record; return the truth objects."""

        _require(frame_index == self.last_frame_index + 1, "frame_index_not_next")
        _require(private_record["observation_index"] == frame_index, "private_record_index_mismatch")
        self.last_frame_index = frame_index
        after_window = self.window_end is not None and frame_index > self.window_end
        if after_window and not self.relocations_applied:
            # the runner executes every intervention after the last window frame and before the
            # first sweep-two frame, so from here a relocated object sits at its placement point
            # until a private record sees it again (physics settle is the registered residual)
            for oid, point in self.relocated.items():
                self.position[oid] = list(point)
                self.position_source[oid] = "placement_point"
            self.relocations_applied = True
        for oid, pose in private_record["object_poses"].items():
            if oid not in self.rows:
                continue  # structure ids (walls, rooms, doors) never enter the metadata object list
            self.position[oid] = _xyz(pose, "private_pose_invalid:" + oid)
            self.position_source[oid] = "private_record"
        out: dict[str, dict[str, Any]] = {}
        for oid, row in self.rows.items():
            present = not (after_window and oid in self.removed)
            entry: dict[str, Any] = {"present": present, "position_source": self.position_source[oid]}
            if present and row["initial_aabb_center_world_m"] is not None:
                lower, upper = truth_box(row, self.position[oid], self.origin)
                entry["aabb_min_m"], entry["aabb_max_m"] = lower, upper
                entry["centroid_m"] = [(a + b) / 2.0 for a, b in zip(lower, upper)]
            elif present:
                entry["aabb_min_m"] = entry["aabb_max_m"] = None
                entry["centroid_m"] = world_to_episode(self.position[oid], self.origin)
            out[oid] = entry
        return out


# --------------------------------------------------------------------------
# residual checks
# --------------------------------------------------------------------------

def backproject_mask(
    mask: Any, depth_m: Any, calibration: Mapping[str, Any], pose: Mapping[str, Any], *,
    minimum_depth_m: float, maximum_depth_m: float,
) -> np.ndarray:
    """World points (episode frame, because the pose is) of a mask's valid depth pixels.

    The arithmetic is the frozen D-223 backprojection, line for line, so a private mask and a
    public fragment land in the same frame; the S1-03 box test pins the same expression.
    """

    binary = np.asarray(mask)
    depth = np.asarray(depth_m)
    _require(binary.ndim == 2 and binary.dtype == np.bool_, "mask_shape_invalid")
    _require(depth.shape == binary.shape, "depth_shape_invalid")
    valid = binary & np.isfinite(depth) & (depth >= minimum_depth_m) & (depth <= maximum_depth_m)
    fx, fy, cx, cy, position, rotation = _camera_values(calibration, pose)
    rows, columns = np.nonzero(valid)
    z_camera = depth[valid].astype(np.float64, copy=False)
    camera_points = np.column_stack((
        (columns.astype(np.float64) - cx) * z_camera / fx,
        (cy - rows.astype(np.float64)) * z_camera / fy,
        z_camera,
    ))
    return camera_points @ rotation.T + position


def containment_fraction(
    points: np.ndarray, lower: Sequence[float], upper: Sequence[float], *, margin_m: float = CONTAINMENT_MARGIN_M,
) -> float | None:
    """Share of points inside the box grown by ``margin_m`` on every side; None without points."""

    if points.size == 0:
        return None
    lo = np.asarray(lower, dtype=np.float64) - margin_m
    hi = np.asarray(upper, dtype=np.float64) + margin_m
    inside = np.all((points >= lo) & (points <= hi), axis=1)
    return float(inside.mean())


def drift_report(
    table: Mapping[str, Any], private_records: Iterable[Mapping[str, Any]], *, intervened_ids: Iterable[str],
    tolerance_m: float = DRIFT_TOLERANCE_M,
) -> dict[str, Any]:
    """How far non-intervened objects' recorded positions stray from the reload's initial positions.

    白话：重载得到的初始位置若与 episode 里各帧记录的位置对不上，说明重载不可复现或有物体被
    误动，这是裁决 45 这条路的前提。输入表与全部私有帧记录，输出最大漂移、超过容差的物体清单
    与只被看见过的物体数。被干预的物体不计（它们本来就会动）。
    """

    rows = {row["object_id"]: row for row in validate_geometry_table(table)["objects"]}
    skip = set(intervened_ids)
    worst: dict[str, float] = {}
    for record in private_records:
        for oid, pose in record["object_poses"].items():
            if oid not in rows or oid in skip:
                continue
            here = _xyz(pose, "private_pose_invalid:" + oid)
            initial = rows[oid]["initial_position_world_m"]
            drift = math.sqrt(sum((a - b) ** 2 for a, b in zip(here, initial)))
            if drift > worst.get(oid, -1.0):
                worst[oid] = drift
    over = sorted(oid for oid, drift in worst.items() if drift > tolerance_m)
    values = sorted(worst.values())
    return {
        "objects_observed": len(worst),
        "tolerance_m": tolerance_m,
        "max_drift_m": (values[-1] if values else None),
        "p95_drift_m": (values[int(math.floor(0.95 * (len(values) - 1)))] if values else None),
        "objects_over_tolerance": over,
        "worst_by_object": {oid: worst[oid] for oid in over},
    }


__all__ = [
    "CONTAINMENT_MARGIN_M",
    "DRIFT_TOLERANCE_M",
    "EpisodeTruthTracker",
    "LeanObjectGeometryError",
    "OBJECT_FIELDS",
    "TABLE_FIELDS",
    "TABLE_FILE_NAME",
    "TABLE_SCHEMA_VERSION",
    "aabb_iou",
    "backproject_mask",
    "build_geometry_table",
    "containment_fraction",
    "drift_report",
    "sha",
    "truth_box",
    "union_box",
    "validate_geometry_table",
    "world_to_episode",
]
