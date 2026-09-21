"""D-224 / S1-03: the shared frozen frontend cache, as a pure core.

This module turns one public frame -- RGB-derived anonymous masks, metric depth, intrinsics and
the causal camera pose -- into the lean cache record the five arms read, and projects that record
into the frame shape S0-03's assignment layer validates.  No simulator, no SAM, no DINOv2 and no
GPU are imported here: the runner loads the frozen models and hands their outputs in, so every
rule below is testable without a model.

白话：这个模块解决「一帧公开画面怎样变成五个臂共读的一条 cache 记录」。输入是本帧的匿名 mask
列表、公开深度、内参、因果位姿，以及两套 DINOv2 patch token；输出是每个色块的像素数、深度有效
率、质心、三维包围盒、两套描述子，加上逐帧封印。例如一帧 18 个 mask 就写 18 条 fragment 记录。
它**不判断身份**（那是 S2 的分配层），**不训练任何部件**，**不读 private 面**，也**不存逐实体的
应可见比例**——那个量因臂而异，由 S2-01 的 runner 在线算。

Everything geometric is delegated to the already reviewed D-223 implementation so the cache cannot
drift from the frozen frontend; the one thing this module adds is the axis-aligned bounding box,
which the D-223 region record does not carry (it stores the point-cloud mean and the box size, and
the mean is not the box centre, so the two cannot be combined into a box).
"""

from __future__ import annotations

import hashlib
import math
from typing import Any, Mapping, Sequence

import numpy as np

from cpmt.hashing import canonical_json
from vsmt.l1_entities import _camera_values, backproject_public_entity_geometry
from vsmt.shared_frontend_core import AnonymousMask, DINORegionConfig, PublicGeometryConfig

CONTRACT_SCHEMA_VERSION = "vsmt-lean-s1-03-frontend-cache-v1"

#: The frozen frontend this stage binds to.  Restated so that acquiring an asset cannot quietly
#: aim at another commit, config or checkpoint; no value of the frozen frontend is redefined here.
D223_FRONTEND_CONFIG_SHA256 = "f1fb5839b196591429c052f04681b3aa3500f3cf53c201032983642e2ebb2337"
SAM2_REPOSITORY_COMMIT = "2b90b9f5ceec907a1c18123530e92e794ad901a4"
SAM2_CHECKPOINT_SHA256 = "6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38"
#: D-215's frozen automatic-mask digest, and the digest of the config that is actually in effect
#: after ruling 43 (box/crop NMS 1.0 -> 0.7, every other argument unchanged).  D-215's bytes are
#: not rewritten; the supersession lives in the S1-03 contract by reference.
D215_AUTOMATIC_CONFIG_SHA256 = "df828bcfac74c8dc0dcb0d82731c978f8a17958755822aa44c90e5ac23db2c33"
EFFECTIVE_AUTOMATIC_CONFIG_SHA256 = "c56fb6252a1c8b49e62b10270cb1320789bebd8346c87a68c2279ebffe1847c8"
NMS_SUPERSEDED_CLAUSES = ("sam2.automatic_mask_generator.box_nms_thresh",
                          "sam2.automatic_mask_generator.crop_nms_thresh")
NMS_FROM, NMS_TO = 1.0, 0.7
#: The whole effective generator argument set, bound here the way D-223 binds D-215's, so that a
#: third changed argument is refused even when the recorded digest was updated to match it.
EFFECTIVE_AUTOMATIC_MASK_GENERATOR = {"box_nms_thresh": 0.7, "crop_n_layers": 0, "crop_nms_thresh": 0.7, "min_mask_region_area": 0, "output_mode": "binary_mask", "points_per_batch": 64, "points_per_side": 32, "pred_iou_thresh": 0.8, "stability_score_offset": 1.0, "stability_score_thresh": 0.95}

#: D-215 proposal boundary.
MINIMUM_VISIBLE_PIXELS = 196
MAXIMUM_PROPOSALS_PER_FRAME = 64

#: The two descriptor sets S1 extracts.  S1-05 selects one; this stage never selects.
DESCRIPTOR_SETS = ("vits14", "vitb14")
DESCRIPTOR_DIMENSIONS = {"vits14": 384, "vitb14": 768}

#: The lean cache record.  ``entity_geometry`` is deliberately absent: the should-be-visible and
#: free-space-coverage ratios depend on M_{t-1}, which differs per arm, so they are derived online
#: by the S2-01 runner from the public volumes stored here (METHOD section 5).
CACHE_FRAME_FIELDS = (
    "frame_digest", "tick", "camera_position_m", "camera_forward",
    "fragments", "surfaces", "free_space", "visibility", "frame_seal",
)
#: What the cache keeps of a public surface: where it is, how big, how it lies.  The frozen record
#: also carries a descriptor, which this stage drops -- no feature reads it, and the surface exists
#: only to serve the shared ``supported_by`` rule whose thresholds are still unfrozen.
SURFACE_FIELDS = (
    "surface_id", "centroid_m", "extent_m", "plane_normal", "plane_offset_m", "mask_sha256",
)
#: The two public volumes, kept exactly as the frozen materialiser writes them.
FREE_SPACE_FIELDS = (
    "free_space_id", "time_s", "halfspaces_world", "reliability", "support_sha256",
)
VISIBILITY_FIELDS = (
    "visibility_id", "time_s", "halfspaces_world", "reliability", "support_sha256",
)

FRAGMENT_FIELDS = (
    "fragment_id", "descriptor_vits14", "descriptor_vitb14", "centroid_m",
    "aabb_min_m", "aabb_max_m", "pixel_count", "depth_valid_ratio",
    "supported_by", "mask_sha256",
)
#: What the assignment layer receives; ``entity_geometry`` is injected by its runner.
VIEW_FRAME_FIELDS = (
    "frame_digest", "tick", "camera_position_m", "camera_forward",
    "fragments", "entity_geometry",
)
VIEW_FRAGMENT_FIELDS = (
    "fragment_id", "descriptor", "centroid_m", "aabb_min_m", "aabb_max_m",
    "pixel_count", "depth_valid_ratio", "supported_by",
)

#: Reasons a frame may fail.  The list is closed so a generator cannot invent one that quietly
#: means "dropped".  Any frame failure fails the whole episode.
FAILURE_REASONS = (
    "proposal_overflow",
    "duplicate_proposal_mask",
    "fragment_depth_support_insufficient",
    "descriptor_not_unit_norm",
    "public_input_missing_or_malformed",
    "forbidden_key_in_cache",
)

#: No cache value may carry a scene, house, simulator object or private identity.
FORBIDDEN_KEY_TOKENS = (
    "house", "scene", "object_id", "instance", "private", "teacher",
    "reference", "future", "world_pose", "reachable", "intervention",
)

UNIT_NORM_TOLERANCE = 1e-5


class LeanFrontendCacheError(ValueError):
    """Raised for an inadmissible frame, proposal set or cache record."""

    def __init__(self, reason: str, detail: str = "") -> None:
        if reason not in FAILURE_REASONS:
            raise ValueError(f"unregistered_failure_reason:{reason}")
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason, self.detail = reason, detail


def _require(condition: bool, reason: str, detail: str = "") -> None:
    if not condition:
        raise LeanFrontendCacheError(reason, detail)


def sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _reject_forbidden(value: Any, path: str = "") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            for token in FORBIDDEN_KEY_TOKENS:
                _require(token not in lowered, "forbidden_key_in_cache", f"{path}/{key}")
            _reject_forbidden(item, f"{path}/{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_forbidden(item, f"{path}/{index}")


# --------------------------------------------------------------------------
# proposals
# --------------------------------------------------------------------------

def admit_proposals(
    masks: Sequence[AnonymousMask], *,
    minimum_pixels: int = MINIMUM_VISIBLE_PIXELS,
    maximum: int = MAXIMUM_PROPOSALS_PER_FRAME,
) -> list[AnonymousMask]:
    """Admit one frame's proposals under the D-215 boundary, or fail the frame.

    白话：一帧里 SAM 返回的 mask 要先过三道门：像素数 ≥196 的才算色块；重复的 mask 直接判
    整条 episode 构造失败（同一个东西被数成两个会污染分配）；数量超过 64 也是构造失败而**不是**
    截断——悄悄丢掉第 65 个等于让数据规模决定数据内容。输出按 mask 摘要排序，所以同一帧在任何
    机器上得到同样的顺序。它不判断 mask 对不对、也不看深度。
    """

    kept: list[AnonymousMask] = []
    seen: set[str] = set()
    for mask in masks:
        _require(type(mask) is AnonymousMask, "public_input_missing_or_malformed", "proposal_not_anonymous_mask")
        pixels = int(np.asarray(mask.as_array()).sum())
        if pixels < minimum_pixels:
            continue
        digest = mask.mask_sha256
        _require(digest not in seen, "duplicate_proposal_mask", digest)
        seen.add(digest)
        kept.append(mask)
    _require(
        len(kept) <= maximum,
        "proposal_overflow",
        f"{len(kept)} proposals of at least {minimum_pixels} px exceed the cap of {maximum}",
    )
    return sorted(kept, key=lambda item: item.mask_sha256)


# --------------------------------------------------------------------------
# geometry the frozen record does not carry
# --------------------------------------------------------------------------

def fragment_aabb(
    mask: Any, depth_m: Any, calibration: Mapping[str, Any], pose: Mapping[str, Any],
    config: PublicGeometryConfig,
) -> tuple[list[float], list[float]]:
    """The axis-aligned bounding box of one fragment's valid world points.

    白话：S0-03 要 `aabb_min_m` 与 `aabb_max_m`，而冻结前端的记录里只有点云均值 `centroid_m`
    和包围盒尺寸 `extent_m`；均值不是盒心，两者推不出盒子。所以这里用与冻结反投影**逐行相同**
    的算式重新取一次世界点，直接读 min 与 max。测试钉住 `max − min` 与冻结 `extent_m` 完全相等，
    一旦上游反投影改了，测试立刻失败而不是悄悄给出错误的盒子。

    The arithmetic below is the same as ``backproject_public_entity_geometry``: camera axes are
    +x right, +y up, +z forward, pixel coordinates carry no half-pixel offset, depth is axial z.
    """

    binary = np.asarray(mask)
    depth = np.asarray(depth_m)
    _require(binary.ndim == 2 and binary.dtype == np.bool_, "public_input_missing_or_malformed", "mask_shape")
    _require(depth.shape == binary.shape, "public_input_missing_or_malformed", "depth_shape")
    valid = (
        binary
        & np.isfinite(depth)
        & (depth >= config.minimum_depth_m)
        & (depth <= config.maximum_depth_m)
    )
    _require(int(valid.sum()) >= 1, "fragment_depth_support_insufficient", "no_valid_depth_pixel")
    fx, fy, cx, cy, position, rotation = _camera_values(calibration, pose)
    rows, columns = np.nonzero(valid)
    z_camera = depth[valid].astype(np.float64, copy=False)
    camera_points = np.column_stack((
        (columns.astype(np.float64) - cx) * z_camera / fx,
        (cy - rows.astype(np.float64)) * z_camera / fy,
        z_camera,
    ))
    world_points = camera_points @ rotation.T + position
    lower = world_points.min(axis=0)
    upper = world_points.max(axis=0)
    _require(
        bool(np.isfinite(lower).all() and np.isfinite(upper).all()),
        "public_input_missing_or_malformed", "nonfinite_world_points",
    )
    return [float(v) for v in lower], [float(v) for v in upper]


def _unit_norm(vector: Sequence[float], name: str) -> list[float]:
    values = [float(v) for v in vector]
    _require(all(math.isfinite(v) for v in values), "descriptor_not_unit_norm", f"{name}_nonfinite")
    norm = math.sqrt(sum(v * v for v in values))
    _require(abs(norm - 1.0) <= UNIT_NORM_TOLERANCE, "descriptor_not_unit_norm", f"{name}_norm_{norm:.6f}")
    return values


# --------------------------------------------------------------------------
# records
# --------------------------------------------------------------------------

def build_fragment(
    *, ordinal: int, mask: AnonymousMask, depth_m: Any, calibration: Mapping[str, Any],
    pose: Mapping[str, Any], geometry_config: PublicGeometryConfig,
    descriptors: Mapping[str, Sequence[float]], supported_by: str | None = None,
) -> dict[str, Any]:
    """One lean fragment record: frozen geometry, both descriptors, and the added bounding box.

    ``supported_by`` stays ``None`` until the five surface-relation thresholds are frozen; no
    feature reads it (S0-03 uses ``support_height_difference_m`` instead), so a null is honest
    rather than a gap.
    """

    _require(set(descriptors) == set(DESCRIPTOR_SETS), "public_input_missing_or_malformed",
             f"descriptor_sets_{sorted(descriptors)}")
    try:
        geometry = backproject_public_entity_geometry(
            mask.as_array(), depth_m, calibration, pose, geometry_config)
    except ValueError as exc:
        raise LeanFrontendCacheError("fragment_depth_support_insufficient", str(exc)[:160]) from exc
    lower, upper = fragment_aabb(mask.as_array(), depth_m, calibration, pose, geometry_config)
    record = {
        "fragment_id": f"fragment:{ordinal:04d}",
        "descriptor_vits14": _unit_norm(descriptors["vits14"], "vits14"),
        "descriptor_vitb14": _unit_norm(descriptors["vitb14"], "vitb14"),
        "centroid_m": [float(v) for v in geometry.centroid_m],
        "aabb_min_m": lower,
        "aabb_max_m": upper,
        "pixel_count": int(np.asarray(mask.as_array()).sum()),
        "depth_valid_ratio": float(geometry.reliability),
        "supported_by": supported_by,
        "mask_sha256": mask.mask_sha256,
    }
    for name, expected in DESCRIPTOR_DIMENSIONS.items():
        _require(len(record[f"descriptor_{name}"]) == expected,
                 "public_input_missing_or_malformed", f"{name}_dimension")
    _require(tuple(record) == FRAGMENT_FIELDS, "public_input_missing_or_malformed", "fragment_field_order")
    return record


def project_surface(record: Mapping[str, Any], *, ordinal: int) -> dict[str, Any]:
    """Keep the geometry of one public surface and drop its descriptor.

    白话：支撑面在冻结记录里带一条描述子，而 cache 只需要「面在哪、多大、朝向如何」。没有任何
    特征读这个描述子，所以丢掉它比留着更诚实——留着会让人以为下游用了它。
    """

    projected = {
        "surface_id": f"surface:{ordinal:04d}",
        "centroid_m": [float(v) for v in record["centroid_m"]],
        "extent_m": [float(v) for v in record["extent_m"]],
        "plane_normal": [float(v) for v in record["plane_normal"]],
        "plane_offset_m": float(record["plane_offset_m"]),
        "mask_sha256": record["mask_sha256"],
    }
    _require(tuple(projected) == SURFACE_FIELDS, "public_input_missing_or_malformed", "surface_field_order")
    return projected


def check_volume_records(records: Sequence[Mapping[str, Any]], *, fields: Sequence[str],
                         label: str) -> list[dict[str, Any]]:
    """Check the public volume records the frozen materialiser produced.

    白话：自由空间与可见体积由已冻结的材化算出，这里只核对它们的字段与可靠性。可靠性必须是 1.0：
    D-223 的材化只在一个体块内每个像素深度都有效时才生成该体块（裁决 42 的依据），所以不存在部分
    可靠的体块；出现别的值说明上游语义变了，必须整帧失败而不是照收。
    """

    out = []
    for record in records:
        _require(tuple(record) == tuple(fields), "public_input_missing_or_malformed", f"{label}_field_order")
        _require(float(record["reliability"]) == 1.0,
                 "public_input_missing_or_malformed", f"{label}_reliability_not_one")
        _require(len(record["halfspaces_world"]) == 6,
                 "public_input_missing_or_malformed", f"{label}_not_six_halfspaces")
        out.append(dict(record))
    return out


def build_frame(
    *, tick: int, frame_digest: str, camera_position_m: Sequence[float],
    camera_forward: Sequence[float], fragments: Sequence[Mapping[str, Any]],
    surfaces: Sequence[Mapping[str, Any]], free_space: Any, visibility: Any,
    frontend_config_sha256: str, descriptor_asset_sha256s: Mapping[str, str],
) -> dict[str, Any]:
    """One sealed lean cache frame.

    白话：把本帧的色块、支撑面、自由空间体素与可见体积体素封成一条记录，并算出帧封印。封印覆盖
    本帧全部公开内容加前端资产摘要，所以「换了私有文件而 cache 逐字节不变」可以被检验。记录里不
    允许出现 house、场景、对象 ID 等字样，出现即整条失败。
    """

    for name, value in (("fragments", fragments), ("surfaces", surfaces),
                        ("free_space", free_space), ("visibility", visibility)):
        _reject_forbidden(value, f"/{name}")
    _require(type(tick) is int and tick >= 1, "public_input_missing_or_malformed", "tick")
    _require(len(frame_digest) == 64 and all(c in "0123456789abcdef" for c in frame_digest),
             "public_input_missing_or_malformed", "frame_digest")
    position = [float(v) for v in camera_position_m]
    forward = [float(v) for v in camera_forward]
    _require(len(position) == 3 and len(forward) == 3, "public_input_missing_or_malformed", "camera_vectors")
    norm = math.sqrt(sum(v * v for v in forward))
    _require(abs(norm - 1.0) < 1e-6, "public_input_missing_or_malformed", "camera_forward_not_unit")
    surface_rows = [dict(row) for row in surfaces]
    for row in surface_rows:
        _require(tuple(row) == SURFACE_FIELDS, "public_input_missing_or_malformed", "surface_field_order")
    check_volume_records(free_space, fields=FREE_SPACE_FIELDS, label="free_space")
    check_volume_records(visibility, fields=VISIBILITY_FIELDS, label="visibility")
    ids = [row["fragment_id"] for row in fragments]
    _require(len(set(ids)) == len(ids), "public_input_missing_or_malformed", "fragment_id_duplicate")
    _require(len(fragments) <= MAXIMUM_PROPOSALS_PER_FRAME, "proposal_overflow", str(len(fragments)))

    frame: dict[str, Any] = {
        "frame_digest": frame_digest,
        "tick": tick,
        "camera_position_m": position,
        "camera_forward": forward,
        "fragments": [dict(row) for row in fragments],
        "surfaces": surface_rows,
        "free_space": [dict(row) for row in free_space],
        "visibility": [dict(row) for row in visibility],
    }
    _reject_forbidden(frame)
    seal_payload = {
        "frame_digest": frame_digest, "tick": tick,
        "camera_position_m": position, "camera_forward": forward,
        "fragments": frame["fragments"], "surfaces": frame["surfaces"],
        "free_space_sha256": sha(frame["free_space"]), "visibility_sha256": sha(frame["visibility"]),
        "frontend_config_sha256": frontend_config_sha256,
        "descriptor_asset_sha256s": dict(sorted(descriptor_asset_sha256s.items())),
    }
    frame["frame_seal"] = {"payload_sha256": sha(seal_payload),
                           "frontend_config_sha256": frontend_config_sha256}
    _require(tuple(frame) == CACHE_FRAME_FIELDS, "public_input_missing_or_malformed", "frame_field_order")
    return frame


def seal_episode(frames: Sequence[Mapping[str, Any]], *, frontend_config_sha256: str) -> dict[str, Any]:
    """The episode seal over every frame seal, written before any private file is opened."""

    seals = [frame["frame_seal"]["payload_sha256"] for frame in frames]
    ticks = [frame["tick"] for frame in frames]
    _require(ticks == list(range(1, len(ticks) + 1)), "public_input_missing_or_malformed", "ticks_not_consecutive")
    payload = {"episode_frame_count": len(frames), "frame_seals": seals,
               "frontend_config_sha256": frontend_config_sha256}
    return {"episode_frame_count": len(frames), "payload_sha256": sha(payload),
            "frontend_config_sha256": frontend_config_sha256}


# --------------------------------------------------------------------------
# the view the assignment layer reads
# --------------------------------------------------------------------------

def assignment_view(
    frame: Mapping[str, Any], *, descriptor_set: str,
    entity_geometry: Mapping[str, Mapping[str, float]] | None = None,
) -> dict[str, Any]:
    """Project one cache frame into the frame shape S0-03 validates.

    白话：cache 里每个色块存了两套描述子，而 S0-03 要求一帧里维度一致，所以投影时只取一套；
    选哪一套是 S1-05 的裁决，这里由调用方指定。同时丢掉 mask 摘要、支撑面与体素（它们只用来在
    线算 entity_geometry），并接收 runner 算好的 entity_geometry。cache 本身永远不存它。
    """

    _require(descriptor_set in DESCRIPTOR_SETS, "public_input_missing_or_malformed", descriptor_set)
    fragments = []
    for row in frame["fragments"]:
        projected = {
            "fragment_id": row["fragment_id"],
            "descriptor": list(row[f"descriptor_{descriptor_set}"]),
            "centroid_m": list(row["centroid_m"]),
            "aabb_min_m": list(row["aabb_min_m"]),
            "aabb_max_m": list(row["aabb_max_m"]),
            "pixel_count": row["pixel_count"],
            "depth_valid_ratio": row["depth_valid_ratio"],
            "supported_by": row["supported_by"],
        }
        _require(tuple(projected) == VIEW_FRAGMENT_FIELDS,
                 "public_input_missing_or_malformed", "view_fragment_field_order")
        fragments.append(projected)
    view = {
        "frame_digest": frame["frame_digest"],
        "tick": frame["tick"],
        "camera_position_m": list(frame["camera_position_m"]),
        "camera_forward": list(frame["camera_forward"]),
        "fragments": fragments,
        "entity_geometry": {k: dict(v) for k, v in (entity_geometry or {}).items()},
    }
    _require(tuple(view) == VIEW_FRAME_FIELDS, "public_input_missing_or_malformed", "view_field_order")
    return view


# --------------------------------------------------------------------------
# contract
# --------------------------------------------------------------------------

def validate_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Check that the S1-03 machine contract agrees with this implementation.

    白话：输入 S1-03 合同，输出副本，并在绑定的前端摘要、色块边界、描述子维度、字段清单、失败
    原因或授权位与本实现不一致时拒绝。例如把每帧上限从 64 改成 128、或把溢出改成截断，都会被拒。
    它不检查仍为 null 的数值，也不检查 cache 是否已经生成。
    """

    _require(type(contract) is dict, "public_input_missing_or_malformed", "contract_not_object")
    _require(contract.get("schema_version") == CONTRACT_SCHEMA_VERSION,
             "public_input_missing_or_malformed", "contract_schema")
    _require(contract.get("stage_id") == "S1-03", "public_input_missing_or_malformed", "contract_stage")

    bound = contract["bound_frozen_frontend"]
    _require(bound["d223_frontend_config_sha256"] == D223_FRONTEND_CONFIG_SHA256,
             "public_input_missing_or_malformed", "frontend_config_digest_changed")
    _require(bound["sam2_repository_commit"] == SAM2_REPOSITORY_COMMIT,
             "public_input_missing_or_malformed", "sam2_commit_changed")
    _require(bound["sam2_checkpoint_sha256"] == SAM2_CHECKPOINT_SHA256,
             "public_input_missing_or_malformed", "sam2_checkpoint_changed")
    _require(bound["no_parameter_of_the_frozen_frontend_is_redefined_here"] is True,
             "public_input_missing_or_malformed", "frontend_redefined")
    _require(bound["sam2_automatic_mask_and_boundary_config_sha256"] == D215_AUTOMATIC_CONFIG_SHA256,
             "public_input_missing_or_malformed", "d215_automatic_digest_changed")
    nms = contract["sam2_nms_supersession"]
    _require(tuple(nms["d215_clauses_replaced"]) == NMS_SUPERSEDED_CLAUSES,
             "public_input_missing_or_malformed", "nms_clauses_changed")
    _require(nms["from"] == {"box_nms_thresh": NMS_FROM, "crop_nms_thresh": NMS_FROM}
             and nms["to"] == {"box_nms_thresh": NMS_TO, "crop_nms_thresh": NMS_TO},
             "public_input_missing_or_malformed", "nms_values_changed")
    _require(nms["every_other_generator_argument_unchanged"] is True
             and nms["predecessor_bytes_must_not_change"] is True
             and nms["supersession_is_by_reference_not_by_rewrite"] is True,
             "public_input_missing_or_malformed", "nms_supersession_weakened")
    _require(nms["effective_automatic_mask_and_boundary_config_sha256"] == EFFECTIVE_AUTOMATIC_CONFIG_SHA256,
             "public_input_missing_or_malformed", "effective_automatic_digest_changed")
    effective = nms["effective_automatic_mask_generator"]
    _require(effective == EFFECTIVE_AUTOMATIC_MASK_GENERATOR,
             "public_input_missing_or_malformed", "effective_generator_config_changed")

    rule = contract["proposal_rule"]
    _require(rule["minimum_visible_pixels"] == MINIMUM_VISIBLE_PIXELS,
             "public_input_missing_or_malformed", "minimum_pixels_changed")
    _require(rule["maximum_proposals_per_frame"] == MAXIMUM_PROPOSALS_PER_FRAME,
             "public_input_missing_or_malformed", "proposal_cap_changed")
    _require(rule["overflow_action"] == "construction_failure_never_silent_truncation",
             "public_input_missing_or_malformed", "overflow_action_weakened")
    _require(rule["duplicate_mask_action"] == "construction_failure",
             "public_input_missing_or_malformed", "duplicate_action_weakened")
    _require(rule["cross_frame_memory_enabled"] is False,
             "public_input_missing_or_malformed", "cross_frame_memory_enabled")

    sets = contract["descriptor_sets"]
    _require(sets["primary"]["dimension"] == DESCRIPTOR_DIMENSIONS["vits14"],
             "public_input_missing_or_malformed", "primary_dimension")
    _require(sets["optional_upgrade"]["dimension"] == DESCRIPTOR_DIMENSIONS["vitb14"],
             "public_input_missing_or_malformed", "upgrade_dimension")
    _require(sets["selection_is_not_made_in_this_stage"] is True,
             "public_input_missing_or_malformed", "selection_leaked_into_s1_03")

    _require(tuple(contract["cache_frame_fields"]) == CACHE_FRAME_FIELDS,
             "public_input_missing_or_malformed", "cache_fields_changed")
    _require(tuple(contract["fragment_fields"]) == FRAGMENT_FIELDS,
             "public_input_missing_or_malformed", "fragment_fields_changed")
    view = contract["assignment_view"]
    _require(tuple(view["produces"]) == VIEW_FRAME_FIELDS,
             "public_input_missing_or_malformed", "view_fields_changed")
    _require(tuple(view["fragment_fields"]) == VIEW_FRAGMENT_FIELDS,
             "public_input_missing_or_malformed", "view_fragment_fields_changed")
    _require(view["entity_geometry_is_injected_by_the_s2_runner_not_stored"] is True,
             "public_input_missing_or_malformed", "entity_geometry_stored")
    _require(contract["aabb_rule"]["not_derived_from_centroid_and_extent"] is True,
             "public_input_missing_or_malformed", "aabb_rule_weakened")
    _require(contract["supported_by_rule"]["enters_association_features"] is False,
             "public_input_missing_or_malformed", "supported_by_entered_features")
    _require(tuple(contract["failure_reasons"]) == FAILURE_REASONS,
             "public_input_missing_or_malformed", "failure_reasons_changed")
    _require(contract["failure_rules"]["any_frame_failure_fails_the_episode"] is True,
             "public_input_missing_or_malformed", "frame_failure_tolerated")
    _require(contract["seal"]["sealed_before_any_private_file_is_opened"] is True,
             "public_input_missing_or_malformed", "seal_after_private")

    open_slots = contract["policy_values_without_defaults"]
    _require(contract["volumes"]["free_space_reliability_gate_rho_free"] is None
             or "volumes.free_space_reliability_gate_rho_free" not in open_slots,
             "public_input_missing_or_malformed", "rho_free_frozen_but_still_open")
    # A bit may be true only if a ruling opened it by name, which is what makes "who authorised
    # this run" auditable; the runner separately refuses while any required bit is still closed.
    policy = contract.get("activation_policy")
    opened = set(policy["active_true_authorizations"]) if policy else set()
    if policy:
        _require(type(policy.get("opened_by")) is str and bool(policy["opened_by"]),
                 "public_input_missing_or_malformed", "activation_policy_names_no_ruling")
    for name, value in contract["authorization"].items():
        _require(type(value) is bool, "public_input_missing_or_malformed", f"authorization_{name}_not_boolean")
        _require(value is False or name in opened,
                 "public_input_missing_or_malformed", f"bit_opened_without_a_ruling:{name}")
    return dict(contract)


__all__ = [
    "CACHE_FRAME_FIELDS",
    "CONTRACT_SCHEMA_VERSION",
    "D215_AUTOMATIC_CONFIG_SHA256",
    "D223_FRONTEND_CONFIG_SHA256",
    "EFFECTIVE_AUTOMATIC_CONFIG_SHA256",
    "EFFECTIVE_AUTOMATIC_MASK_GENERATOR",
    "NMS_SUPERSEDED_CLAUSES",
    "DESCRIPTOR_DIMENSIONS",
    "DESCRIPTOR_SETS",
    "FAILURE_REASONS",
    "FRAGMENT_FIELDS",
    "FREE_SPACE_FIELDS",
    "SURFACE_FIELDS",
    "VISIBILITY_FIELDS",
    "LeanFrontendCacheError",
    "MAXIMUM_PROPOSALS_PER_FRAME",
    "MINIMUM_VISIBLE_PIXELS",
    "VIEW_FRAGMENT_FIELDS",
    "VIEW_FRAME_FIELDS",
    "admit_proposals",
    "assignment_view",
    "build_frame",
    "build_fragment",
    "check_volume_records",
    "fragment_aabb",
    "project_surface",
    "seal_episode",
    "sha",
    "validate_contract",
]
