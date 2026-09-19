"""Mechanical core shared by every scenario-blind front-end cache profile.

Two profiles seal caches from the same public geometry primitives:

* the D-214 legacy profile (``d214_shared_frontend``), whose bytes explain
  already executed receipts and therefore must never move, and
* the D-223/F-01 production profile (``d223_f01_production_reader``), which
  carries no learned semantic or structural field.

They deliberately seal different schemas.  What they share is the mechanics:
validating a causal pose and pose belief, materializing anonymous fragments
and public planar surfaces into ordinal packet-local regions, pooling the
full-frame place descriptor with its free-space and visibility support,
checking region records, sealing an ordered episode, and cloning it once per
main method.  That machinery lives here exactly once.

Each profile keeps its own explicit validator with its own literal field set,
so no validator in this repository accepts more than one byte layout.  The
helpers take the calling profile's error type so a failure surfaces under the
profile's own exception, and they take no scenario, private, teacher, or
future argument.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from cpmt.hashing import canonical_json, clone_json

from .l1_entities import (
    DINORegionConfig,
    PublicGeometryConfig,
    materialize_l1_entity_observation,
    pool_dinov2_region_descriptor,
)
from .l1_masks import AnonymousMask
from .l1_structures import (
    FreeSpaceFrustum,
    FreeSpaceMaterializationConfig,
    SurfaceMaterializationConfig,
    assemble_free_space_history,
    materialize_public_free_space,
    materialize_public_surfaces,
    materialize_public_visibility,
)


MAIN_METHODS = ("VSMT", "TAF", "ELU", "WFR", "LOW")
SURFACE_SOURCE_ID = "l1.public_depth.planar_surface.v1"
POSE_BELIEF_FIELDS = frozenset({
    "schema_version", "observation_index", "frame", "mean_x_y_z_yaw",
    "covariance_diagonal", "source_id", "is_world_pose",
    "defines_place_identity", "belief_sha256",
})
CAUSAL_POSE_FIELDS = frozenset({
    "position_m", "quaternion_xyzw", "is_world_pose", "source_id",
})
REGION_RECORD_FIELDS = frozenset({
    "region_id", "structure_kind", "mask_sha256", "descriptor",
    "centroid_m", "extent_m", "reliability", "proposal_source_id",
})

ErrorType = type[ValueError]


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def payload_sha256(value: Mapping[str, Any], field: str) -> str:
    """Digest a record with its own seal field removed."""

    payload = clone_json(dict(value))
    payload.pop(field, None)
    return canonical_sha256(payload)


def _finite(value: Any, name: str, error: ErrorType) -> float:
    if type(value) not in {int, float} or not math.isfinite(float(value)):
        raise error(f"{name} must be finite")
    return float(value)


def validate_pose_belief(
    value: Mapping[str, Any], observation_index: int, *, error: ErrorType,
    label: str,
) -> dict[str, Any]:
    """Accept only a causal, episode-relative belief for this observation."""

    record = clone_json(dict(value))
    if type(record) is not dict or set(record) != POSE_BELIEF_FIELDS:
        raise error(f"{label} pose belief has unexpected fields")
    if not (record["observation_index"] == observation_index and
            record["frame"] == "episode_relative_observation_zero_origin" and
            record["is_world_pose"] is False and
            record["defines_place_identity"] is False):
        raise error(f"{label} pose belief is not causal episode-relative evidence")
    mean = [_finite(item, "pose belief mean", error)
            for item in record["mean_x_y_z_yaw"]]
    covariance = [_finite(item, "pose belief covariance", error)
                  for item in record["covariance_diagonal"]]
    if not (len(mean) == 4 and len(covariance) == 4 and
            all(item >= 0.0 for item in covariance)):
        raise error(f"{label} pose belief needs four means and variances")
    if record["belief_sha256"] != payload_sha256(record, "belief_sha256"):
        raise error(f"{label} pose belief digest mismatch")
    return record


def validate_causal_pose(
    value: Mapping[str, Any], *, error: ErrorType, label: str,
) -> dict[str, Any]:
    """Reduce a causal camera pose to the position and unit quaternion."""

    record = clone_json(dict(value))
    if type(record) is not dict or set(record) != CAUSAL_POSE_FIELDS:
        raise error(f"{label} causal camera pose has unexpected fields")
    if not (record["is_world_pose"] is False and
            type(record["source_id"]) is str and record["source_id"]):
        raise error(f"{label} camera pose must be causal and episode-relative")
    position = [_finite(item, "camera position", error)
                for item in record["position_m"]]
    quaternion = [_finite(item, "camera quaternion", error)
                  for item in record["quaternion_xyzw"]]
    if not (len(position) == 3 and len(quaternion) == 4 and
            abs(math.sqrt(sum(item * item for item in quaternion)) - 1.0)
            <= 1e-6):
        raise error(f"{label} camera pose shape or quaternion is invalid")
    return {"position_m": position, "quaternion_xyzw": quaternion}


def materialize_public_regions(
    *, masks: Sequence[AnonymousMask], patch_tokens: Any, depth_m: Any,
    calibration: Mapping[str, Any], geometry_pose: Mapping[str, Any],
    descriptor: DINORegionConfig, fragment_geometry: PublicGeometryConfig,
    surface: SurfaceMaterializationConfig, fragment_source_id: str,
    error: ErrorType, label: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Materialize anonymous fragments and public surfaces as ordinal regions.

    Fragments and surfaces are each sorted by mask digest and centroid, then
    numbered ``region:NNNN`` across the concatenation.  A fragment is a
    proposal, never an entity; the ordinals are packet-local and carry no
    identity across frames.
    """

    if not all(type(item) is AnonymousMask for item in masks):
        raise error(f"{label} fragment proposals must be AnonymousMask values")
    fragments = []
    for mask in masks:
        observed = materialize_l1_entity_observation(
            mask, patch_tokens, depth_m, calibration, geometry_pose,
            descriptor, fragment_geometry,
        )
        fragments.append({
            "region_id": "",
            "structure_kind": "fragment",
            "mask_sha256": observed.mask_sha256,
            "descriptor": list(observed.descriptor.values),
            "centroid_m": list(observed.geometry.centroid_m),
            "extent_m": list(observed.geometry.extent_m),
            "reliability": observed.geometry.reliability,
            "proposal_source_id": fragment_source_id,
        })
    fragments.sort(key=lambda row: (row["mask_sha256"], row["centroid_m"]))
    surfaces = materialize_public_surfaces(
        depth_m, calibration, geometry_pose, patch_tokens, descriptor, surface,
    )
    surface_records = [item.public_record("") for item in surfaces]
    surface_records.sort(key=lambda row: (row["mask_sha256"], row["centroid_m"]))
    for ordinal, record in enumerate([*fragments, *surface_records]):
        record["region_id"] = f"region:{ordinal:04d}"
    return fragments, surface_records


@dataclass(frozen=True)
class PlaceSupport:
    """Full-frame descriptor plus the public volumes that support a place."""

    place_descriptor: list[float]
    free_space: list[dict[str, Any]]
    visibility: list[dict[str, Any]]
    current_free_space: tuple[FreeSpaceFrustum, ...]


def materialize_place_support(
    *, depth_m: Any, calibration: Mapping[str, Any],
    geometry_pose: Mapping[str, Any], patch_tokens: Any,
    descriptor: DINORegionConfig, free_space: FreeSpaceMaterializationConfig,
    time_s: float, depth_sha256: str, calibration_and_pose_sha256: str,
    prior_free_space: Sequence[Sequence[FreeSpaceFrustum]],
) -> PlaceSupport:
    """Pool the whole frame and assemble rolling free-space and visibility."""

    full_mask = np.ones(
        (descriptor.image_height, descriptor.image_width), dtype=np.bool_,
    )
    pooled = pool_dinov2_region_descriptor(patch_tokens, full_mask, descriptor)
    current = materialize_public_free_space(
        depth_m, calibration, geometry_pose, time_s=time_s,
        depth_sha256=depth_sha256,
        camera_calibration_and_pose_sha256=calibration_and_pose_sha256,
        config=free_space,
    )
    history = assemble_free_space_history(
        [*prior_free_space, current],
        rolling_public_observation_times=free_space.rolling_public_observation_times,
    )
    visibility = materialize_public_visibility(
        current, surface_clearance_m=free_space.surface_clearance_m,
    )
    return PlaceSupport(
        place_descriptor=list(pooled.values), free_space=history,
        visibility=visibility, current_free_space=current,
    )


def validate_region_records(
    fragments: Any, surfaces: Any, *, fragment_source_id: str,
    require_unit_descriptor: bool, error: ErrorType, label: str,
) -> list[dict[str, Any]]:
    """Check ordinal, kind, source, digest, and geometry of every region.

    ``require_unit_descriptor`` is the one place the two profiles differ on
    regions: the production profile additionally insists every region
    descriptor is unit normalized.  The legacy profile keeps its historical
    acceptance so its validator still explains executed receipts.
    """

    if type(fragments) is not list or type(surfaces) is not list:
        raise error(f"{label} region observations must be arrays")
    regions = [*fragments, *surfaces]
    if [row.get("region_id") for row in regions] != [
        f"region:{ordinal:04d}" for ordinal in range(len(regions))
    ]:
        raise error(f"{label} regions must use contiguous packet-local ordinals")
    if not (all(row.get("structure_kind") == "fragment" for row in fragments)
            and all(row.get("structure_kind") == "surface" for row in surfaces)):
        raise error(f"{label} fragments or surfaces changed structure kind")
    for ordinal, row in enumerate(regions):
        if type(row) is not dict or set(row) != REGION_RECORD_FIELDS:
            raise error(f"{label} region {ordinal} has unexpected fields")
        digest = row["mask_sha256"]
        if type(digest) is not str or len(digest) != 64 or any(
                character not in "0123456789abcdef" for character in digest):
            raise error(f"{label} region {ordinal} mask digest must be a "
                        "lowercase SHA-256")
        descriptor = [_finite(item, f"{label} region descriptor", error)
                      for item in row["descriptor"]]
        centroid = [_finite(item, f"{label} region centroid", error)
                    for item in row["centroid_m"]]
        extent = [_finite(item, f"{label} region extent", error)
                  for item in row["extent_m"]]
        reliability = _finite(row["reliability"],
                              f"{label} region reliability", error)
        if not (descriptor and len(centroid) == 3 and len(extent) == 3 and
                all(item >= 0.0 for item in extent) and
                0.0 <= reliability <= 1.0):
            raise error(f"{label} region geometry or reliability is invalid")
        if require_unit_descriptor and abs(
                math.sqrt(sum(item * item for item in descriptor)) - 1.0) > 1e-5:
            raise error(f"{label} region descriptor must be unit normalized")
        expected_source = (fragment_source_id
                           if row["structure_kind"] == "fragment"
                           else SURFACE_SOURCE_ID)
        if row["proposal_source_id"] != expected_source:
            raise error(f"{label} region proposal source changed")
    return regions


def validate_ordered_frames(
    frames: Sequence[Mapping[str, Any]], *,
    frame_validator: Callable[[Mapping[str, Any]], dict[str, Any]],
    error: ErrorType, label: str,
) -> list[dict[str, Any]]:
    """Validate every frame and require a contiguous, strictly timed sequence."""

    rows = [frame_validator(frame) for frame in frames]
    if not rows or [row["observation_index"] for row in rows] != list(
            range(len(rows))):
        raise error(f"{label} frames must be contiguous from zero")
    if not all(left["decision_time_s"] < right["decision_time_s"]
               for left, right in zip(rows, rows[1:])):
        raise error(f"{label} frame times must be strictly increasing")
    if len({row["frontend_config_sha256"] for row in rows}) != 1:
        raise error(f"{label} frames used different front-end configs")
    return rows


def seal_ordered_episode(
    frames: Sequence[Mapping[str, Any]], *, schema_version: str,
    episode_public_id: str, extra_fields: Mapping[str, Any],
    frame_validator: Callable[[Mapping[str, Any]], dict[str, Any]],
    reject_forbidden_keys: Callable[[Any], None],
    error: ErrorType, label: str,
) -> dict[str, Any]:
    """Seal an ordered episode shared by all five main methods.

    ``extra_fields`` carries the profile's own receipt bindings and boundary
    flags; the shared fields are the schema, the anonymous episode ID, the
    frame count, the frames, their ordered digests, the single front-end
    config digest, and the fixed main-method list.
    """

    if type(episode_public_id) is not str or not episode_public_id:
        raise error(f"{label} episode public ID is invalid")
    rows = validate_ordered_frames(
        frames, frame_validator=frame_validator, error=error, label=label,
    )
    value = {
        "schema_version": schema_version,
        "episode_public_id": episode_public_id,
        "frame_count": len(rows),
        "frames": rows,
        "ordered_frame_cache_sha256s": [row["frame_cache_sha256"] for row in rows],
        "frontend_config_sha256": rows[0]["frontend_config_sha256"],
        **clone_json(dict(extra_fields)),
        "main_methods": list(MAIN_METHODS),
    }
    reject_forbidden_keys(value)
    value["episode_cache_sha256"] = canonical_sha256(value)
    return value


def identical_method_cache_views(
    episode_cache: Mapping[str, Any], *,
    episode_validator: Callable[[Mapping[str, Any]], dict[str, Any]],
    error: ErrorType, label: str,
) -> dict[str, dict[str, Any]]:
    """Return five independent clones whose canonical bytes are identical."""

    value = episode_validator(episode_cache)
    views = {method: clone_json(value) for method in MAIN_METHODS}
    if len({canonical_sha256(item) for item in views.values()}) != 1:
        raise error(f"{label} main methods received different cache bytes")
    return views
