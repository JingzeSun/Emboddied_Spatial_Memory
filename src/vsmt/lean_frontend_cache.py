"""D-224 / S1-03: the shared frozen frontend cache, as a pure core.

This module turns one public frame -- anonymous masks (SAM 2.1, or since ruling 72 simulator
instance segmentation), metric depth, intrinsics, the causal camera pose and two sets of DINOv2
patch tokens -- into the lean cache record all arms read, and projects that record into the frame
shape S0-03's assignment layer validates.  No simulator, no SAM, no DINOv2 and no GPU are imported
here: the runner loads the frozen models and hands their outputs in, so every rule below is
testable without a model.

Per admitted mask the record holds one fragment: pixel count, valid-depth ratio, centroid,
axis-aligned box and both descriptor sets; each frame carries a seal.  The module makes no identity
decision (that is the S2 assignment layer), trains nothing, reads no private file and stores no
per-entity should-be-visible ratio: that ratio depends on each arm's memory and is computed online
by the S2-01 runner.

Fragment geometry comes from the public front-end helpers ``vsmt.l1_entities``
(``backproject_public_entity_geometry``) and ``vsmt.shared_frontend_core`` (mask and config types),
which the D-223 production profile also composes; the D-223 contract
(``configs/vsmt/vm04_d223_f01_production_reader_v1.json``, pinned by ``D223_FRONTEND_CONFIG_SHA256``)
is read by the S1-03 and S1-04 scripts, and the D-223 reader module itself is not imported.  The
cache therefore cannot drift from the frozen frontend; the one thing this module adds is the
axis-aligned bounding box, which the frozen region record does not carry (it stores the point-cloud
mean and the box size, and the mean is not the box centre, so the two cannot be combined into a box).
"""

from __future__ import annotations

import hashlib
import math
from typing import Any, Mapping, Sequence

import numpy as np

from cpmt.hashing import canonical_json
from vsmt import lean_public_pose
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

#: Ruling 51: one packed mask file per frame, written during generation beside the frame itself,
#: in the fragment order the sealed frame lists.  No separate SAM-only recovery pass is needed.
MASK_FILE_NAME_TEMPLATE = "NNNN.masks.npz"

#: Ruling 72: where a cache's masks come from.  The main table reads the simulator's per-frame
#: instance segmentation (mask pixel geometry only, never a label, id, pose or box); SAM 2.1 is the
#: robustness appendix.  One cache root holds one source, and the episode seal says which.
MASK_SOURCE_INSTANCE = "simulator_instance_masks"
MASK_SOURCE_SAM2 = "sam2"
MASK_SOURCES = (MASK_SOURCE_INSTANCE, MASK_SOURCE_SAM2)
#: What the generator may read of the private plane under the instance source, and nothing else.
INSTANCE_MODE_PRIVATE_READS = (
    "private/NNNN.frame.json:observation_index",
    "private/NNNN.frame.json:frame_digest",
    "private/NNNN.frame.json:instance_mask_path",
    "private/NNNN.frame.json:object_id_to_entity_id:label_values_only",
    "private/NNNN.instance.png:pixel_labels_reduced_to_anonymous_boolean_masks",
)
INSTANCE_MODE_NEVER_EXPOSED = (
    "instance_label_value", "object_id", "object_type", "object_pose", "object_visibility_count",
    "truth_box", "object_id_to_entity_id_mapping",
)

#: The two descriptor sets S1 extracts.  S1-05 selects one; this stage never selects.
DESCRIPTOR_SETS = ("vits14", "vitb14")
DESCRIPTOR_DIMENSIONS = {"vits14": 384, "vitb14": 768}

#: The lean cache record.  ``entity_geometry`` is deliberately absent: the should-be-visible and
#: free-space-coverage ratios depend on M_{t-1}, which differs per arm, so the S2-01 runner derives
#: them online (``lean_runner.entity_geometry``: per-point depth tests of each entity's last-seen
#: surface points against the frame's public depth, rulings 74/75; METHOD section 5).  The two voxel
#: volumes stored here no longer enter those ratios.
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

    Masks below 196 pixels are dropped.  A duplicate mask is a construction failure of the episode
    (one object counted twice would corrupt the assignment), and more than 64 admitted masks is a
    construction failure, never a truncation (silently dropping the 65th would let the data volume
    decide the data content).  The output is sorted by mask digest, so a frame gives the same order
    on every machine.  Mask correctness and depth are not judged here.
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


def instance_label_masks(label_image: Any, label_values: Sequence[int]) -> list[np.ndarray]:
    """Ruling 72: one anonymous boolean mask per labelled value present in a private instance image.

    The fragments of the instance-segmentation front end are the pixel regions of the labelled
    instances in the simulator's instance image.  Input: one frame's private instance image (one
    integer label per pixel, 0 = background) and the frame's registered label set.  Output: one
    boolean mask per label present in the image, sorted by mask digest; the label values do not
    travel with the masks.  No pixel floor or cap is applied here: ``admit_proposals`` applies the
    same rule (>= 196 px, <= 64 per frame, overflow is a construction failure) to SAM 2.1 and
    instance masks.
    """

    image = np.asarray(label_image)
    _require(image.ndim == 2, "public_input_missing_or_malformed", "instance_image_not_two_dimensional")
    wanted = {int(value) for value in label_values}
    _require(0 not in wanted, "public_input_missing_or_malformed", "instance_label_zero_is_background")
    present = [int(value) for value in np.unique(image).tolist() if int(value) in wanted]
    masks = [np.ascontiguousarray(image == value) for value in present]
    return sorted(masks, key=mask_sha256_of)


# --------------------------------------------------------------------------
# geometry the frozen record does not carry
# --------------------------------------------------------------------------

def fragment_aabb(
    mask: Any, depth_m: Any, calibration: Mapping[str, Any], pose: Mapping[str, Any],
    config: PublicGeometryConfig,
) -> tuple[list[float], list[float]]:
    """The axis-aligned bounding box of one fragment's valid world points.

    S0-03 needs ``aabb_min_m`` and ``aabb_max_m``, while the frozen record has only the point-cloud
    mean ``centroid_m`` and the box size ``extent_m``; the mean is not the box centre, so no box
    follows from the two.  The world points are therefore recomputed with arithmetic identical, line
    for line, to the frozen back-projection, and min and max are read directly.  A test pins
    ``max - min`` to the frozen ``extent_m``, so a change of the upstream back-projection fails the
    test instead of silently giving a wrong box.

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

    The frozen surface record carries a descriptor, while the cache needs only position, size and
    orientation.  No feature reads the descriptor; keeping it would suggest a downstream use.
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

    Free space and visible volume come from the frozen D-223 materialiser; only their fields and
    reliability are checked here.  Reliability must be 1.0: the materialiser emits a block only when
    every pixel depth inside it is valid (the basis of ruling 42), so no partially reliable block
    exists, and another value means the upstream semantics changed; the frame then fails.
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

    Packs the frame's fragments, surfaces, free-space blocks and visible-volume blocks into one
    record and computes the frame seal.  The seal covers every public field of the frame plus the
    frontend asset digests, so "a private file changed while the cache stayed byte-identical" is
    checkable.  A key naming a house, scene, object id or another forbidden token fails the record.
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
    frame["frame_seal"] = {
        "payload_sha256": sha(frame_seal_payload(frame, frontend_config_sha256=frontend_config_sha256,
                                                descriptor_asset_sha256s=descriptor_asset_sha256s)),
        "frontend_config_sha256": frontend_config_sha256,
    }
    _require(tuple(frame) == CACHE_FRAME_FIELDS, "public_input_missing_or_malformed", "frame_field_order")
    return frame


def frame_seal_payload(frame: Mapping[str, Any], *, frontend_config_sha256: str,
                       descriptor_asset_sha256s: Mapping[str, str]) -> dict[str, Any]:
    """What a frame seal digests: every public field of the frame plus the frontend identity.

    The single definition ``build_frame`` writes with and ``verify_frame_seal`` reads with, so a
    consumer re-derives the seal from the bytes it actually loaded instead of trusting the stored
    digest string.
    """

    return {
        "frame_digest": frame["frame_digest"], "tick": frame["tick"],
        "camera_position_m": list(frame["camera_position_m"]), "camera_forward": list(frame["camera_forward"]),
        "fragments": list(frame["fragments"]), "surfaces": list(frame["surfaces"]),
        "free_space_sha256": sha(frame["free_space"]), "visibility_sha256": sha(frame["visibility"]),
        "frontend_config_sha256": frontend_config_sha256,
        "descriptor_asset_sha256s": dict(sorted(descriptor_asset_sha256s.items())),
    }


def verify_frame_seal(frame: Mapping[str, Any], *, frontend_config_sha256: str,
                      descriptor_asset_sha256s: Mapping[str, str]) -> None:
    """Recompute the frame seal from the loaded frame and refuse any difference.

    A reader does not copy the stored digest string: it re-derives the seal from the fragments,
    descriptors, boxes, surfaces and two volume digests it loaded, by the same definition, and
    compares it with the stored seal.  A changed descriptor under an unchanged seal is refused, and
    so is a frontend config or asset digest other than the one the cache was written with.
    """

    stored = frame.get("frame_seal") or {}
    _require(stored.get("frontend_config_sha256") == frontend_config_sha256,
             "public_input_missing_or_malformed", "frame_seal_frontend_config_mismatch")
    expected = sha(frame_seal_payload(frame, frontend_config_sha256=frontend_config_sha256,
                                      descriptor_asset_sha256s=descriptor_asset_sha256s))
    _require(stored.get("payload_sha256") == expected, "public_input_missing_or_malformed",
             f"frame_seal_mismatch_tick_{frame.get('tick')}")


def mask_sha256_of(mask: Any) -> str:
    """The digest a fragment's ``mask_sha256`` carries, recomputed from mask pixels.

    Same bytes as ``sha([height, width, *row_major_uint8_values])`` (the S1-03 runner's anonymous
    mask), built without materialising a Python list per pixel so a consumer can re-digest every
    recovered mask of every frame.
    """

    binary = np.ascontiguousarray(np.asarray(mask, dtype=bool))
    _require(binary.ndim == 2, "public_input_missing_or_malformed", "mask_not_two_dimensional")
    height, width = (int(v) for v in binary.shape)
    digits = np.where(binary.reshape(-1), np.uint8(ord("1")), np.uint8(ord("0")))
    body = np.empty((digits.size, 2), dtype=np.uint8)
    body[:, 0] = digits
    body[:, 1] = np.uint8(ord(","))
    head = f"[{height},{width}".encode("ascii") + (b"," if digits.size else b"")
    payload = head + body.reshape(-1)[:-1].tobytes() + b"]" if digits.size else head + b"]"
    return hashlib.sha256(payload).hexdigest()


def seal_episode(frames: Sequence[Mapping[str, Any]], *, frontend_config_sha256: str,
                 mask_source: str = MASK_SOURCE_SAM2) -> dict[str, Any]:
    """The episode seal over every frame seal and, since ruling 72, the cache's mask source.

    An instance-segmentation cache writes ``mask_source`` into the sealed payload, so relabelling it
    as a SAM 2.1 cache (or the reverse) breaks the seal.  A SAM 2.1 cache keeps the pre-ruling-72
    payload, so SAM 2.1 caches built before the ruling still verify without a rebuild.
    """

    _require(mask_source in MASK_SOURCES, "public_input_missing_or_malformed", f"unregistered_mask_source:{mask_source}")
    seals = [frame["frame_seal"]["payload_sha256"] for frame in frames]
    ticks = [frame["tick"] for frame in frames]
    _require(ticks == list(range(1, len(ticks) + 1)), "public_input_missing_or_malformed", "ticks_not_consecutive")
    payload = {"episode_frame_count": len(frames), "frame_seals": seals,
               "frontend_config_sha256": frontend_config_sha256}
    sealed = {"episode_frame_count": len(frames), "frontend_config_sha256": frontend_config_sha256}
    if mask_source != MASK_SOURCE_SAM2:
        payload["mask_source"] = sealed["mask_source"] = mask_source
    return {**sealed, "payload_sha256": sha(payload)}


def sealed_mask_source(seal: Mapping[str, Any]) -> str:
    """The mask source an episode seal declares: ``sam2`` when it names none (every pre-ruling-72 seal)."""

    source = seal.get("mask_source", MASK_SOURCE_SAM2)
    _require(source in MASK_SOURCES, "public_input_missing_or_malformed", f"unregistered_mask_source:{source}")
    return source


# --------------------------------------------------------------------------
# the view the assignment layer reads
# --------------------------------------------------------------------------

def assignment_view(
    frame: Mapping[str, Any], *, descriptor_set: str,
    entity_geometry: Mapping[str, Mapping[str, float]] | None = None,
) -> dict[str, Any]:
    """Project one cache frame into the frame shape S0-03 validates.

    Each cached fragment holds two descriptor sets, while S0-03 requires one dimension per frame, so
    the projection keeps one; which one is the S1-05 choice, passed by the caller.  The mask digest,
    surfaces and volumes are dropped, and the ``entity_geometry`` the runner computed online is
    attached; the cache itself never stores it.
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

    Returns a copy of the contract and refuses it when a bound frontend digest, the proposal
    boundary, a descriptor dimension, a field list, the failure reasons or an authorization bit
    disagree with this implementation; e.g. raising the per-frame cap from 64 to 128, or replacing
    the overflow failure by truncation, is refused.  Values that are still null and whether the
    cache has been generated are not checked.
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
    # Ruling 49: the pitch-sign correction every reader applies to pre-ruling S1-02 episodes is a
    # rule of this contract, bound to the pure core so neither can drift from the other.
    correction = contract["public_pose_correction"]
    _require(correction["rule"] == lean_public_pose.CORRECTION_RULE
             and correction["defect"] == lean_public_pose.DEFECT_ID,
             "public_input_missing_or_malformed", "pose_correction_rule_changed")
    _require(correction["an_episode_from_an_unlisted_commit_is_refused"] is True
             and correction["position_is_unchanged"] is True
             and correction["generated_s1_02_files_are_not_modified"] is True,
             "public_input_missing_or_malformed", "pose_correction_claim_weakened")
    # Ruling 51: the frame's masks are written during generation, so no separate SAM-only pass is
    # needed; the frame seal already binds every mask_sha256, and a consumer re-digests the pixels.
    masks = contract["fragment_masks"]
    _require(masks["file"] == MASK_FILE_NAME_TEMPLATE, "public_input_missing_or_malformed", "mask_file_name_changed")
    _require(masks["written_during_generation"] is True
             and masks["digest_must_reproduce_from_pixels"] is True
             and masks["consumer_must_re_digest_before_use"] is True
             and masks["separate_recovery_pass_no_longer_required"] is True,
             "public_input_missing_or_malformed", "fragment_mask_rule_weakened")
    _require(masks["order"] == "cache_fragment_order_the_sealed_frame_lists",
             "public_input_missing_or_malformed", "fragment_mask_order_changed")
    # Ruling 72: two registered mask sources, one per cache root, the instance source reading only
    # mask pixel geometry of the private instance image; the admission rule is the same for both.
    source = contract["mask_source"]
    _require(tuple(source["registered_values"]) == MASK_SOURCES
             and source["main_table"] == MASK_SOURCE_INSTANCE and source["robustness_appendix"] == MASK_SOURCE_SAM2,
             "public_input_missing_or_malformed", "mask_source_values_changed")
    instance = source[MASK_SOURCE_INSTANCE]
    _require(tuple(instance["private_reads"]) == INSTANCE_MODE_PRIVATE_READS
             and tuple(instance["never_exposed"]) == INSTANCE_MODE_NEVER_EXPOSED,
             "public_input_missing_or_malformed", "instance_mode_private_boundary_changed")
    _require(source["one_cache_root_holds_one_mask_source"] is True
             and source["admission_rule_is_proposal_rule_unchanged"] is True
             and source["overflow_is_a_construction_failure_never_truncation"] is True
             and source["descriptors_geometry_volumes_and_pose_unchanged"] is True
             and source["episode_seal_carries_the_source_unless_sam2"] is True
             and source["an_entry_that_names_a_source_refuses_a_cache_sealed_with_another"] is True,
             "public_input_missing_or_malformed", "mask_source_rule_weakened")
    seal_rule = contract["seal"]
    _require(tuple(seal_rule["episode_seal_payload"]) == ("episode_frame_count", "frame_seals", "frontend_config_sha256", "mask_source")
             and seal_rule["mask_source_in_the_payload_only_when_not_sam2"] is True
             and seal_rule["private_read_before_the_seal_only_under"] == MASK_SOURCE_INSTANCE
             and seal_rule["private_derived_value_admitted_only_as"]
             == "mask_pixel_geometry_under_simulator_instance_masks_anonymised_and_digest_ordered",
             "public_input_missing_or_malformed", "episode_seal_rule_changed")
    listed = list(correction["applies_to_s1_02_code_commits"]) + list(correction["correct_encoder_since_code_commits"])
    _require(all(type(c) is str and len(c) == 40 and all(ch in "0123456789abcdef" for ch in c) for c in listed)
             and len(set(listed)) == len(listed),
             "public_input_missing_or_malformed", "pose_correction_commit_list_invalid")

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
    "INSTANCE_MODE_NEVER_EXPOSED",
    "INSTANCE_MODE_PRIVATE_READS",
    "MASK_FILE_NAME_TEMPLATE",
    "MASK_SOURCES",
    "MASK_SOURCE_INSTANCE",
    "MASK_SOURCE_SAM2",
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
    "frame_seal_payload",
    "instance_label_masks",
    "mask_sha256_of",
    "project_surface",
    "seal_episode",
    "sealed_mask_source",
    "sha",
    "validate_contract",
    "verify_frame_seal",
]
