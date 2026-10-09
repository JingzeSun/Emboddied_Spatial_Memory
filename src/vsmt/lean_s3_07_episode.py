"""S3-07 (ruling 111-8 step 4): one (reference, rescan) pair assembled into the files the frozen readers read, as pure functions.

白话：转换器（``ops/vsmt/s3_07_convert.py``）对每一对“参考扫描＋一次重扫描”要写出与 ProcTHOR episode 同样格式的三面文件；
这个模块把其中的计算写成纯函数，不读写文件：
  * ``plan_pair``：两次扫描的物体键、物体盒（对齐后、换轴后）、111-3 的变化分类、干预日志行、几何表行；
  * ``public_record`` / ``private_record``：一帧的公开记录（含帧摘要）与私有记录（实例标签到私有键、可见像素数、物体位置）；
  * ``geometry_table`` / ``window_record``：几何补充表（冻结的 ``validate_geometry_table`` 逐键核对）与退化窗口；
  * ``frame_diagnostics``：一帧在实例列上会不会撞冻结前端的两条整条失败规则（每帧 >64 个色块、色块深度支撑不足），
    分别按网格深度与传感器深度算——传感器深度只作诊断；
  * 小样本核对（111-5 与修订一）：平移单位（几何残差）、OBB 轴的排布（顶点包含率）、旋正（滚转中位数）、ambiguity 结构。
输入是已经解析好的扫描内容（``lean_s3_07_3rscan`` 的输出）与渲染结果，输出是要写进文件的字典与数组。例如参考扫描 203 帧、重扫描
174 帧的一对，输出 377 条公开记录与私有记录、窗口 [202, 202]、几张移除与搬动的干预行和一张几何表。它不渲染、不跑方法、不读 test。
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from vsmt import lean_frontend_cache as fc
from vsmt import lean_object_geometry as og
from vsmt import lean_s3_07_3rscan as r3
from vsmt.lean_intervention import FORBIDDEN_PUBLIC_KEYS, PRIVATE_FRAME_FIELDS, PUBLIC_FRAME_FIELDS

STAGE = "vsmt.lean.s3_07.episode.v1"
WINDOW_PROTOCOL = "s3_07_zero_frames_between_the_scans"
#: OBB containment tolerance for the layout check: annotated vertices sit on the object's surface, the OBB is tight
OBB_CONTAINMENT_TOLERANCE_M = 0.02
OBB_CONTAINMENT_MINIMUM = 0.95
#: the translation-unit check stops when neither reading brings unchanged objects within this median distance
UNIT_CHECK_MAXIMUM_M = 0.10
#: at most this many vertices per object enter a nearest-distance computation (every k-th by index, deterministic)
DISTANCE_SAMPLE = 400


class LeanS307EpisodeError(ValueError):
    """Raised with a short machine-readable code."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LeanS307EpisodeError(code)


# --------------------------------------------------------------------------
# objects, boxes, changes
# --------------------------------------------------------------------------

def object_keys(reference: Mapping[int, Mapping[str, Any]], rescan: Mapping[int, Mapping[str, Any]],
                labels: Mapping[str, int], rescan_id_of: Mapping[str, int]) -> dict[str, Any]:
    """Private keys of both scans' objects: a rescan instance carries its reference instance's key (identity), a rescan-only
    instance its own; labels must be in the class sheet; a label that differs between the scans keeps the reference one."""

    for objects in (reference, rescan):
        for object_id, row in objects.items():
            _require(row["label"] in labels, f"label_not_in_mapping:{row['label']}")
    reference_keys = {oid: r3.object_key(oid, row["label"], labels[row["label"]]) for oid, row in reference.items()}
    reference_of = {int(rescan_id): int(ref) for ref, rescan_id in rescan_id_of.items()}
    rescan_keys: dict[int, str] = {}
    label_changed: list[int] = []
    for oid, row in rescan.items():
        source = reference_of.get(oid, oid if oid in reference and oid not in reference_of.values() else None)
        if source is not None and source in reference:
            rescan_keys[oid] = reference_keys[source]
            if reference[source]["label"] != row["label"]:
                label_changed.append(oid)
        else:
            rescan_keys[oid] = r3.object_key(oid, row["label"], labels[row["label"]])
    structural_reference = {oid for oid, row in reference.items() if r3.is_structural(labels[row["label"]])}
    structural_rescan = {oid for oid, row in rescan.items() if r3.is_structural(labels[row["label"]])}
    return {"reference": reference_keys, "rescan": rescan_keys, "structural_reference": structural_reference,
            "structural_rescan": structural_rescan, "label_changed": sorted(label_changed)}


def object_boxes(objects: Mapping[int, Mapping[str, Any]], *, layout: str | None,
                 alignment: np.ndarray | None = None) -> dict[int, dict[str, list[float]]]:
    return {oid: r3.object_box(row["obb"], layout=layout, alignment=alignment) for oid, row in sorted(objects.items())}


def coverage_of(reference: Mapping[int, Mapping[str, Any]], rescan_vertices_aligned: np.ndarray) -> dict[int, bool]:
    """Amendment 2: per reference object, whether a rescan mesh vertex (aligned to the reference frame) lies within
    ``COVERAGE_RADIUS_M`` of its OBB centre -- the rescan looked at that place."""

    sample = _sample(np.asarray(rescan_vertices_aligned, dtype=np.float64)) if len(rescan_vertices_aligned) else np.zeros((0, 3))
    out = {}
    for oid, row in reference.items():
        centre = np.asarray(row["obb"]["centroid"], dtype=np.float64)
        if not len(sample):
            out[oid] = False
            continue
        d2 = (sample[:, 0] - centre[0]) ** 2 + (sample[:, 1] - centre[1]) ** 2 + (sample[:, 2] - centre[2]) ** 2
        out[oid] = bool(float(d2.min()) <= r3.COVERAGE_RADIUS_M ** 2)
    return out


def residual_ratios(reference_vertices: Mapping[int, np.ndarray], rescan_vertices: Mapping[int, np.ndarray],
                    removed: Iterable[int]) -> dict[int, float]:
    """Amendment 2: for each official removal still annotated in the rescan, rescan vertices / reference vertices."""

    out = {}
    for oid in removed:
        if oid in rescan_vertices and len(rescan_vertices[oid]):
            out[oid] = len(rescan_vertices[oid]) / max(1, len(reference_vertices.get(oid, ())))
    return out


def plan_pair(scene: Mapping[str, Any], rescan_scan: str, reference: Mapping[int, Mapping[str, Any]],
              rescan: Mapping[int, Mapping[str, Any]], labels: Mapping[str, int], *, unit: str | None,
              layout: str | None, reference_mesh: Mapping[str, np.ndarray] | None = None,
              rescan_mesh: Mapping[str, np.ndarray] | None = None) -> dict[str, Any]:
    """Everything about a pair that does not depend on its frames: alignment, boxes, keys, change classification, intervention
    rows (keyed), and the geometry-table rows (every non-structural object of both scans, structure stays out as in ProcTHOR).
    With both meshes (``read_ply`` output) the amendment-2 coverage and residual readings enter the classification; without them
    every place counts as covered (the synthetic tests)."""

    changes = r3.rescan_changes(scene, rescan_scan)
    alignment = r3.alignment_matrix(changes["transform"], unit=unit)
    box_reference = object_boxes(reference, layout=layout)
    box_rescan = object_boxes(rescan, layout=layout, alignment=alignment)
    structural = {oid for oid, row in reference.items() if r3.is_structural(labels[row["label"]])} | \
                 {oid for oid, row in rescan.items() if r3.is_structural(labels[row["label"]])}
    covered = residual = None
    if reference_mesh is not None and rescan_mesh is not None:
        aligned = r3.transform_points(r3.orthonormal_rigid(alignment)[0], np.asarray(rescan_mesh["vertices"], dtype=np.float64))
        covered = coverage_of(reference, aligned)
        residual = residual_ratios(vertices_by_object(reference_mesh), vertices_by_object(rescan_mesh), changes["removed"])
    classified = r3.classify_changes(box_reference, box_rescan, changes, structural=structural, covered=covered, residual_ratio=residual)
    keys = object_keys(reference, rescan, labels, classified["rescan_id_of"])
    rows = []
    for row in classified["interventions"]:
        key = keys["reference"][row["object_id"]] if row["kind"] != "add" else keys["rescan"][row["object_id"]]
        rows.append({**row, "object_id": key, "instance": int(row["object_id"])})
    table_rows: list[dict[str, Any]] = []
    reference_of = {int(v): int(k) for k, v in classified["rescan_id_of"].items()}
    for oid in sorted(reference):
        if oid in keys["structural_reference"]:
            continue
        table_rows.append(_table_row(keys["reference"][oid], reference[oid]["label"], box_reference[oid]))
    for oid in sorted(rescan):
        if oid in keys["structural_rescan"] or oid in reference_of or oid in reference:
            continue
        table_rows.append(_table_row(keys["rescan"][oid], rescan[oid]["label"], box_rescan[oid]))
    table_rows.sort(key=lambda row: row["object_id"])
    _require(len({row["object_id"] for row in table_rows}) == len(table_rows), "geometry_key_repeated")
    return {"changes": changes, "alignment": alignment, "box_reference": box_reference, "box_rescan": box_rescan,
            "keys": keys, "classified": classified, "interventions": rows, "table_rows": table_rows,
            "coverage": None if covered is None else {str(k): v for k, v in sorted(covered.items())}}


def _table_row(key: str, label: str, box: Mapping[str, Sequence[float]]) -> dict[str, Any]:
    centre = [float(v) for v in box["centroid_m"]]
    return {"object_id": key, "asset_id": None, "object_type": str(label), "pickupable": None, "receptacle": None,
            "initial_position_world_m": centre, "initial_rotation_degrees": [0.0, 0.0, 0.0],
            "initial_aabb_center_world_m": centre, "initial_aabb_size_m": [float(v) for v in box["size_m"]]}


def geometry_table(*, episode_id: str, house_id: str, source_index: int, code_commit: str,
                   origin_world_m: Sequence[float], rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The per-episode ``object_geometry.json`` in the S1-04 schema, checked by the frozen ``validate_geometry_table``."""

    origin = [float(v) for v in origin_world_m]
    objects = [dict(row) for row in rows]
    table = {"schema_version": og.TABLE_SCHEMA_VERSION, "episode_id": episode_id, "house_id": house_id,
             "source_index": int(source_index), "code_commit": code_commit, "episode_origin_world_m": origin,
             "agent_pose_at_reload": None, "objects": objects, "objects_without_box": [],
             "reload_digest": og.sha({"origin": origin, "objects": objects})}
    og.validate_geometry_table(table)
    return table


def window_record(reference_frames: int) -> dict[str, Any]:
    return {"window": r3.degenerate_window(reference_frames), "frames": 0, "window_protocol": WINDOW_PROTOCOL}


# --------------------------------------------------------------------------
# frames
# --------------------------------------------------------------------------

def public_record(index: int, rgb: np.ndarray, depth: np.ndarray, *, intrinsics: Mapping[str, float],
                  relative_pose: Mapping[str, Any]) -> dict[str, Any]:
    """One public frame record, field for field as the S1-02 generator writes it, with its frame digest."""

    record = {"observation_index": int(index), "rgb_path": f"{index:04d}.rgb.png", "depth_path": f"{index:04d}.depth.npy",
              "intrinsics": {key: float(intrinsics[key]) for key in ("fx", "fy", "cx", "cy")},
              "relative_pose": dict(relative_pose), "action_summary": dict(r3.ACTION_SUMMARY)}
    record["frame_digest"] = r3.frame_digest(rgb, depth, observation_index=index, relative_pose_record=record["relative_pose"],
                                             action_summary=record["action_summary"])
    _require(tuple(record) == PUBLIC_FRAME_FIELDS, "public_record_fields")
    _reject_forbidden(record)
    return record


def _reject_forbidden(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            _require(key not in FORBIDDEN_PUBLIC_KEYS, "public_record_forbidden_key:" + str(key))
            _reject_forbidden(child)
    elif isinstance(value, list):
        for child in value:
            _reject_forbidden(child)


def private_record(index: int, instance: np.ndarray, *, key_of_label: Mapping[int, str],
                   position_of_key: Mapping[str, Sequence[float]], frame_digest: str) -> tuple[dict[str, Any], dict[str, int]]:
    """One private frame record and the pixels of labels with no semseg object (counted, left as unlabelled background).

    ``key_of_label`` maps this scan's objectIds to private keys; every label present in the rendered image and known there is
    listed with its pixel count (``object_visibility``) and its box centre (``object_poses``, world, as {x, y, z}).
    """

    image = np.asarray(instance)
    _require(image.dtype == np.uint16 and image.shape == (r3.TARGET_SIZE, r3.TARGET_SIZE), "instance_image_invalid")
    values, counts = np.unique(image, return_counts=True)
    mapping: dict[str, int] = {}
    visibility: dict[str, int] = {}
    poses: dict[str, dict[str, float]] = {}
    unknown: dict[int, int] = {}
    for value, count in zip(values.tolist(), counts.tolist()):
        if value == 0:
            continue
        key = key_of_label.get(int(value))
        if key is None:
            unknown[int(value)] = int(count)
            continue
        mapping[key] = int(value)
        visibility[key] = int(count)
        x, y, z = (float(v) for v in position_of_key[key])
        poses[key] = {"x": x, "y": y, "z": z}
    record = {"observation_index": int(index), "instance_mask_path": f"{index:04d}.instance.png",
              "object_id_to_entity_id": dict(sorted(mapping.items())), "object_poses": dict(sorted(poses.items())),
              "object_visibility": dict(sorted(visibility.items())), "frame_digest": frame_digest}
    _require(tuple(record) == PRIVATE_FRAME_FIELDS, "private_record_fields")
    return record, unknown


def frame_diagnostics(instance: np.ndarray, mesh_depth: np.ndarray, sensor_depth: np.ndarray | None, *,
                      labels: Iterable[int], geometry: Any) -> dict[str, Any]:
    """Would this frame trip the frozen front end's whole-episode failures on the instance column?

    ``geometry`` is the frozen ``PublicGeometryConfig`` (depth range and the support rule max(32, 25% of the pixels)); labels
    are the frame's listed label values.  Counted per frame: regions of at least 196 px (``fc.MINIMUM_VISIBLE_PIXELS``), whether
    there are more than 64 of them, and how many fail the depth support under the rendered (mesh) depth and, as a diagnostic
    only, under the sensor depth.  The SAM 2.1 column's masks are not known here.
    """

    image = np.asarray(instance)
    regions = 0
    failing = {"mesh": 0, "sensor": 0}
    for value in sorted(set(int(v) for v in labels)):
        mask = image == value
        pixels = int(mask.sum())
        if pixels < fc.MINIMUM_VISIBLE_PIXELS:
            continue
        regions += 1
        required = geometry.required_valid_depth_points(pixels)
        for name, depth in (("mesh", mesh_depth), ("sensor", sensor_depth)):
            if depth is None:
                continue
            d = np.asarray(depth)
            valid = mask & np.isfinite(d) & (d >= geometry.minimum_depth_m) & (d <= geometry.maximum_depth_m)
            if int(valid.sum()) < required:
                failing[name] += 1
    out: dict[str, Any] = {"regions": regions, "over_cap": regions > fc.MAXIMUM_PROPOSALS_PER_FRAME,
                           "mesh_support_failures": failing["mesh"]}
    if sensor_depth is not None:
        s = np.asarray(sensor_depth)
        m = np.asarray(mesh_depth)
        both = (s >= geometry.minimum_depth_m) & (s <= geometry.maximum_depth_m) & (m >= geometry.minimum_depth_m) & \
               (m <= geometry.maximum_depth_m)
        out.update({"sensor_support_failures": failing["sensor"],
                    "sensor_valid_share": float(((s >= geometry.minimum_depth_m) & (s <= geometry.maximum_depth_m)).mean()),
                    "mesh_minus_sensor_median_m": float(np.median((m[both] - s[both]).astype(np.float64))) if both.any() else None})
    return out


# --------------------------------------------------------------------------
# the sample check (ruling 111-5, amendment 1)
# --------------------------------------------------------------------------

def vertices_by_object(mesh: Mapping[str, np.ndarray]) -> dict[int, np.ndarray]:
    ids = np.asarray(mesh["object_ids"])
    return {int(oid): np.asarray(mesh["vertices"])[ids == oid] for oid in np.unique(ids).tolist() if int(oid) != 0}


def _sample(points: np.ndarray) -> np.ndarray:
    step = max(1, int(math.ceil(len(points) / DISTANCE_SAMPLE)))
    return points[::step]


def nearest_distances(points: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """Distance of each (subsampled) point to the nearest (subsampled) reference point, element by element (no BLAS)."""

    a, b = _sample(np.asarray(points, dtype=np.float64)), _sample(np.asarray(reference, dtype=np.float64))
    if not len(a) or not len(b):
        return np.zeros(0)
    d2 = (a[:, None, 0] - b[None, :, 0]) ** 2 + (a[:, None, 1] - b[None, :, 1]) ** 2 + (a[:, None, 2] - b[None, :, 2]) ** 2
    return np.sqrt(d2.min(axis=1))


def translation_unit_check(reference_vertices: Mapping[int, np.ndarray], rescan_vertices: Mapping[int, np.ndarray],
                           unchanged: Iterable[int], transform_values: Sequence[float]) -> dict[str, Any]:
    """Median nearest-vertex distance of unchanged objects after aligning the rescan under each translation unit."""

    out: dict[str, Any] = {}
    for unit in r3.TRANSLATION_UNITS:
        alignment, _moved = r3.orthonormal_rigid(r3.alignment_matrix(transform_values, unit=unit))
        distances = [nearest_distances(r3.transform_points(alignment, rescan_vertices[oid]), reference_vertices[oid])
                     for oid in sorted(unchanged) if oid in reference_vertices and oid in rescan_vertices]
        joined = np.concatenate(distances) if distances else np.zeros(0)
        out[unit] = float(np.median(joined)) if len(joined) else None
    readings = {unit: value for unit, value in out.items() if value is not None}
    best = min(readings, key=lambda unit: readings[unit]) if readings else None
    out["objects"] = len([oid for oid in unchanged if oid in reference_vertices and oid in rescan_vertices])
    out["chosen"] = best if best is not None and readings[best] <= UNIT_CHECK_MAXIMUM_M else None
    return out


def obb_containment(obb: Mapping[str, Any], points: np.ndarray, *, layout: str) -> float:
    """Share of an object's annotated vertices inside its OBB (tolerance ``OBB_CONTAINMENT_TOLERANCE_M``) under one layout."""

    axes = np.asarray(obb["normalizedAxes"], dtype=np.float64).reshape(3, 3)
    if layout == "columns":
        axes = axes.T
    half = 0.5 * np.asarray(obb["axesLengths"], dtype=np.float64)
    offset = np.asarray(points, dtype=np.float64) - np.asarray(obb["centroid"], dtype=np.float64)
    inside = np.ones(len(offset), dtype=bool)
    for k in range(3):
        projection = offset[:, 0] * axes[k, 0] + offset[:, 1] * axes[k, 1] + offset[:, 2] * axes[k, 2]
        inside &= np.abs(projection) <= half[k] + OBB_CONTAINMENT_TOLERANCE_M
    return float(inside.mean()) if len(inside) else float("nan")


def obb_layout_check(objects: Mapping[int, Mapping[str, Any]], vertices: Mapping[int, np.ndarray]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for layout in r3.OBB_AXES_LAYOUTS:
        shares = [obb_containment(objects[oid]["obb"], vertices[oid], layout=layout) for oid in sorted(objects) if oid in vertices]
        out[layout] = float(np.median(shares)) if shares else None
    best = max(r3.OBB_AXES_LAYOUTS, key=lambda layout: -1.0 if out[layout] is None else out[layout])
    out["chosen"] = best if out[best] is not None and out[best] >= OBB_CONTAINMENT_MINIMUM else None
    return out


def roll_check(poses_raw: Sequence[np.ndarray]) -> dict[str, Any]:
    """Amendment 1 of ruling 111: the median roll cosine under each candidate turn; passes when the clockwise turn's median is at
    least cos 45 deg and the largest."""

    medians: dict[str, float | None] = {}
    for turn in r3.ROLL_CANDIDATE_TURNS:
        values = np.asarray([r3.image_roll_cosine(r3.turned_rotation(pose, turn)) for pose in poses_raw], dtype=np.float64)
        judged = values[~np.isnan(values)]
        medians[turn] = float(np.median(judged)) if len(judged) else None
    clockwise = medians["clockwise_90"]
    others = [value for turn, value in medians.items() if turn != "clockwise_90" and value is not None]
    passed = clockwise is not None and clockwise >= math.cos(math.radians(45)) and all(clockwise > value for value in others)
    return {"medians": medians, "passed": bool(passed), "frames": len(poses_raw)}


def ambiguity_structure_ok(scenes: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Every ambiguity value is empty or a (nested) list whose leaves are dicts naming instance_source and instance_target."""

    leaves = 0
    bad: list[str] = []

    def walk(item: Any, scene: str) -> None:
        nonlocal leaves
        if isinstance(item, list):
            for child in item:
                walk(child, scene)
        elif isinstance(item, Mapping) and "instance_source" in item and "instance_target" in item:
            leaves += 1
        else:
            bad.append(scene)

    for scene in scenes:
        walk(scene.get("ambiguity", []), str(scene.get("reference")))
    return {"leaves": leaves, "scenes_with_unrecognised_entries": sorted(set(bad)), "passed": not bad}
