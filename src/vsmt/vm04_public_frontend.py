"""Trusted VM-04 current-frame L1 materialization without program labels.

Private instance masks are visible only long enough to create packet-local
anonymous entity masks and a separate private crosswalk.  Every public
structure and relation is then derived from current RGB-D geometry and frozen
patch tokens.  Program, target, teacher and future values are absent from the
API by design.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Any, Mapping, Sequence

import numpy as np

from cpmt.hashing import canonical_json, clone_json

from .contracts import canonical_sha256
from .l1_entities import (
    DINORegionConfig,
    PublicGeometryConfig,
    materialize_l1_entity_observation,
)
from .l1_masks import L1MaskConfig, anonymize_instance_masks
from .l1_structures import (
    FreeSpaceFrustum,
    FreeSpaceMaterializationConfig,
    PlaceMaterializationConfig,
    SurfaceMaterializationConfig,
    assemble_free_space_history,
    assemble_region_records,
    entity_regions_with_masks,
    materialize_public_free_space,
    materialize_public_places,
    materialize_public_relations,
    materialize_public_surfaces,
    materialize_public_visibility,
)


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _positive(value: Any, name: str) -> float:
    result = _finite(value, name)
    if result <= 0.0:
        raise ValueError(f"{name} must be positive")
    return result


def _fraction(value: Any, name: str) -> float:
    result = _finite(value, name)
    if not 0.0 < result <= 1.0:
        raise ValueError(f"{name} must lie within (0, 1]")
    return result


@dataclass(frozen=True)
class Vm04PublicFrontendConfig:
    """All front-end structures and relation thresholds are explicit."""

    mask: L1MaskConfig
    descriptor: DINORegionConfig
    entity_geometry: PublicGeometryConfig
    surface: SurfaceMaterializationConfig
    place: PlaceMaterializationConfig
    free_space: FreeSpaceMaterializationConfig
    supported_by_maximum_normal_angle_degrees: float
    supported_by_minimum_gap_m: float
    supported_by_maximum_gap_m: float
    supported_by_minimum_projected_overlap: float
    supported_by_maximum_mask_overlap_fraction: float

    def __post_init__(self) -> None:
        expected_types = (
            (self.mask, L1MaskConfig, "mask"),
            (self.descriptor, DINORegionConfig, "descriptor"),
            (self.entity_geometry, PublicGeometryConfig, "entity_geometry"),
            (self.surface, SurfaceMaterializationConfig, "surface"),
            (self.place, PlaceMaterializationConfig, "place"),
            (self.free_space, FreeSpaceMaterializationConfig, "free_space"),
        )
        for value, expected, name in expected_types:
            if type(value) is not expected:
                raise ValueError(f"{name} must be an explicit {expected.__name__}")
        _positive(
            self.supported_by_maximum_normal_angle_degrees,
            "supported_by_maximum_normal_angle_degrees",
        )
        minimum = _finite(
            self.supported_by_minimum_gap_m,
            "supported_by_minimum_gap_m",
        )
        maximum = _finite(
            self.supported_by_maximum_gap_m,
            "supported_by_maximum_gap_m",
        )
        if minimum > maximum:
            raise ValueError("supported-by gap interval must be ordered")
        _fraction(
            self.supported_by_minimum_projected_overlap,
            "supported_by_minimum_projected_overlap",
        )
        _fraction(
            self.supported_by_maximum_mask_overlap_fraction,
            "supported_by_maximum_mask_overlap_fraction",
        )


def _mask_sha256(mask: np.ndarray) -> str:
    value = np.ascontiguousarray(mask, dtype=np.uint8)
    height, width = value.shape
    payload = [int(height), int(width), *value.reshape(-1).tolist()]
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _private_mask_map(
    private_instance_ids: Sequence[str], private_instance_masks: Any,
) -> dict[str, np.ndarray]:
    if isinstance(private_instance_ids, (str, bytes)):
        raise ValueError("private_instance_ids must be a sequence")
    ids = list(private_instance_ids)
    if not ids or any(type(item) is not str or not item for item in ids):
        raise ValueError("private instance IDs must be nonempty strings")
    if len(ids) != len(set(ids)):
        raise ValueError("private instance IDs must be unique within a frame")
    masks = np.asarray(private_instance_masks)
    if masks.ndim != 3 or masks.shape[0] != len(ids):
        raise ValueError("private mask stack does not match its ID sequence")
    return {
        private_id: np.ascontiguousarray(masks[index], dtype=np.uint8)
        for index, private_id in enumerate(ids)
    }


def materialize_vm04_public_frontend_frame(
    *, sample_id_hash: str, decision_time_s: float,
    rgbd_refs: Mapping[str, Any], camera: Mapping[str, Any],
    robot_state: Mapping[str, Any], past_actions: Sequence[Mapping[str, Any]],
    depth_m: Any, patch_tokens: Any,
    private_instance_ids: Sequence[str], private_instance_masks: Any,
    prior_free_space: Sequence[Sequence[FreeSpaceFrustum]],
    public_constants: Mapping[str, Any], frame_role: str,
    config: Vm04PublicFrontendConfig,
) -> dict[str, Any]:
    """Materialize one anonymous public row plus its private crosswalk."""

    if type(config) is not Vm04PublicFrontendConfig:
        raise ValueError("config must be Vm04PublicFrontendConfig")
    if type(frame_role) is not str or not frame_role:
        raise ValueError("frame_role must be a nonempty token")
    if not isinstance(camera, Mapping) or not {
        "pose", "calibration",
    }.issubset(camera):
        raise ValueError("camera must contain public pose and calibration")

    source_masks = _private_mask_map(
        private_instance_ids, private_instance_masks,
    )
    anonymous = anonymize_instance_masks(source_masks, config.mask)
    private_id_by_mask = {
        _mask_sha256(mask): private_id
        for private_id, mask in source_masks.items()
        if bool(mask.any())
    }
    if len(private_id_by_mask) != sum(bool(mask.any()) for mask in source_masks.values()):
        raise ValueError("private instance masks must have unique content digests")

    entities = tuple(
        materialize_l1_entity_observation(
            region,
            patch_tokens,
            depth_m,
            camera["calibration"],
            camera["pose"],
            config.descriptor,
            config.entity_geometry,
        )
        for region in anonymous.regions
    )
    surfaces = materialize_public_surfaces(
        depth_m,
        camera["calibration"],
        camera["pose"],
        patch_tokens,
        config.descriptor,
        config.surface,
    )
    places = materialize_public_places(
        surfaces,
        depth_m,
        camera["calibration"],
        camera["pose"],
        patch_tokens,
        config.descriptor,
        config.surface,
        config.place,
    )
    entity_regions = entity_regions_with_masks(entities, anonymous.regions)
    region_records, indexed = assemble_region_records(
        entity_regions, places.regions, surfaces,
    )
    relation_records = materialize_public_relations(
        indexed,
        place_config=config.place,
        supported_by_maximum_normal_angle_degrees=(
            config.supported_by_maximum_normal_angle_degrees
        ),
        supported_by_minimum_gap_m=config.supported_by_minimum_gap_m,
        supported_by_maximum_gap_m=config.supported_by_maximum_gap_m,
        supported_by_minimum_projected_overlap=(
            config.supported_by_minimum_projected_overlap
        ),
        supported_by_maximum_mask_overlap_fraction=(
            config.supported_by_maximum_mask_overlap_fraction
        ),
    )

    current_free_space = materialize_public_free_space(
        depth_m,
        camera["calibration"],
        camera["pose"],
        time_s=float(decision_time_s),
        depth_sha256=str(rgbd_refs.get("depth_sha256")),
        camera_calibration_and_pose_sha256=canonical_sha256({
            "calibration": camera["calibration"],
            "pose": camera["pose"],
        }),
        config=config.free_space,
    )
    free_space_records = assemble_free_space_history(
        [*prior_free_space, current_free_space],
        rolling_public_observation_times=(
            config.free_space.rolling_public_observation_times
        ),
    )
    visibility_records = materialize_public_visibility(
        current_free_space,
        surface_clearance_m=config.free_space.surface_clearance_m,
    )

    public_region_by_mask = {
        row["mask_sha256"]: row
        for row in region_records
        if row["structure_kind"] == "entity"
    }
    bindings = []
    for region in anonymous.regions:
        public_region = public_region_by_mask.get(region.mask_sha256)
        if public_region is None:
            raise ValueError("anonymous entity is missing from public regions")
        bindings.append({
            "instance_id": private_id_by_mask[region.mask_sha256],
            "region_id": public_region["region_id"],
            "mask_sha256": region.mask_sha256,
        })
    bindings.sort(key=lambda row: row["region_id"])

    frontend_row = {
        "sample_id_hash": sample_id_hash,
        "decision_time_s": decision_time_s,
        "rgbd_refs": clone_json(dict(rgbd_refs)),
        "camera_pose": clone_json(dict(camera["pose"])),
        "robot_state": clone_json(dict(robot_state)),
        "past_actions": clone_json(list(past_actions)),
        "region_observations": region_records,
        "relation_observations": relation_records,
        "free_space_observations": free_space_records,
        "visibility_observations": visibility_records,
        "public_constants": clone_json(dict(public_constants)),
    }
    return {
        "frontend_row": frontend_row,
        "private_crosswalk": {
            "schema_version": "vsmt-vm04-private-region-crosswalk-v1",
            "frame_role": frame_role,
            "bindings": bindings,
        },
        "current_free_space": current_free_space,
        "public_frontend_diagnostics": {
            "anonymous_mask_cache_sha256": anonymous.public_cache_sha256(),
            "anonymous_mask_rejections": [
                item.public_record() for item in anonymous.rejected
            ],
            "place_rejections": [
                item.public_record() for item in places.rejected
            ],
        },
    }
