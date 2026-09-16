"""Public RGB-D visibility geometry for the reviewed VM-04 science layer.

A subject is sealed from an already-public mask, depth map, and camera pose.
Later frames project those public world samples into current public depth.  A
missing or invalid depth sample is treated conservatively as unoccluded, so it
can never authorize a hidden intervention.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import math
import re
from typing import Any, Mapping

import numpy as np

from cpmt.hashing import canonical_json, clone_json

from .l1_entities import _camera_values
from .vm04_observation_runner import make_public_visibility_assessment


HEX64 = re.compile(r"^[0-9a-f]{64}$")
SUBJECT_SCHEMA = "vsmt-vm04-public-visibility-subject-v1"
RECEIPT_SCHEMA = "vsmt-vm04-public-visibility-builder-receipt-v1"


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Vm04PublicVisibilityConfig:
    """All geometric and sampling tolerances are explicit review fields."""

    minimum_depth_m: float
    maximum_depth_m: float
    occlusion_depth_tolerance_m: float
    sampling_stride_pixels: int
    maximum_subject_samples: int
    minimum_subject_samples: int

    def __post_init__(self) -> None:
        numeric = (
            self.minimum_depth_m, self.maximum_depth_m,
            self.occlusion_depth_tolerance_m,
        )
        if any(type(value) not in {int, float} or not math.isfinite(float(value))
               for value in numeric):
            raise ValueError("visibility depth values must be finite")
        if not 0 < self.minimum_depth_m < self.maximum_depth_m:
            raise ValueError("visibility depth range must be ordered and positive")
        if self.occlusion_depth_tolerance_m < 0:
            raise ValueError("occlusion depth tolerance must be nonnegative")
        for name in (
            "sampling_stride_pixels", "maximum_subject_samples",
            "minimum_subject_samples",
        ):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.minimum_subject_samples > self.maximum_subject_samples:
            raise ValueError("minimum subject samples exceed maximum")


def _array_sha(array: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(array)
    return _sha({
        "dtype": str(contiguous.dtype),
        "shape": list(contiguous.shape),
        "bytes_sha256": hashlib.sha256(contiguous.tobytes()).hexdigest(),
    })


def seal_public_visibility_subject(
    *, subject_public_ref: str, source_public_packet_sha256: str,
    source_observation_index: int, public_mask: Any, public_depth_m: Any,
    camera_calibration: Mapping[str, Any], camera_pose: Mapping[str, Any],
    config: Vm04PublicVisibilityConfig,
) -> dict[str, Any]:
    """Seal sparse public world samples without accepting simulator identity."""

    if type(subject_public_ref) is not str or not subject_public_ref:
        raise ValueError("subject_public_ref must be nonempty")
    if HEX64.fullmatch(source_public_packet_sha256) is None:
        raise ValueError("source_public_packet_sha256 must be a lowercase SHA-256")
    if type(source_observation_index) is not int or source_observation_index < 0:
        raise ValueError("source_observation_index must be nonnegative")
    if type(config) is not Vm04PublicVisibilityConfig:
        raise ValueError("config must be Vm04PublicVisibilityConfig")
    mask = np.asarray(public_mask)
    depth = np.asarray(public_depth_m)
    if mask.ndim != 2 or mask.dtype != np.bool_ or depth.shape != mask.shape:
        raise ValueError("public mask/depth shape or dtype is invalid")
    if not np.issubdtype(depth.dtype, np.floating):
        raise ValueError("public depth must be floating point")
    fx, fy, cx, cy, position, rotation = _camera_values(
        camera_calibration, camera_pose,
    )
    rows, columns = np.nonzero(mask)
    stride = config.sampling_stride_pixels
    selected = (rows % stride == 0) & (columns % stride == 0)
    rows, columns = rows[selected], columns[selected]
    z = depth[rows, columns].astype(np.float64, copy=False)
    valid = (np.isfinite(z) & (z >= config.minimum_depth_m) &
             (z <= config.maximum_depth_m))
    rows, columns, z = rows[valid], columns[valid], z[valid]
    camera_points = np.column_stack((
        (columns.astype(np.float64) - cx) * z / fx,
        (cy - rows.astype(np.float64)) * z / fy,
        z,
    )) if len(z) else np.empty((0, 3), dtype=np.float64)
    world = camera_points @ rotation.T + position
    if len(world) > config.maximum_subject_samples:
        indices = np.linspace(
            0, len(world) - 1, config.maximum_subject_samples, dtype=np.int64,
        )
        world = world[indices]
    if len(world) < config.minimum_subject_samples:
        raise ValueError("insufficient_public_subject_samples")
    points = [[float(value) for value in row] for row in world]
    record = {
        "schema_version": SUBJECT_SCHEMA,
        "subject_public_ref": subject_public_ref,
        "source_public_packet_sha256": source_public_packet_sha256,
        "source_observation_index": source_observation_index,
        "source_public_mask_sha256": _array_sha(mask.astype(np.uint8)),
        "source_public_depth_sha256": _array_sha(depth),
        "camera_calibration_and_pose_sha256": _sha({
            "calibration": dict(camera_calibration), "pose": dict(camera_pose),
        }),
        "sample_points_world_m": points,
        "sample_points_sha256": _sha(points),
        "config_sha256": _sha(asdict(config)),
        "source_fields": [
            "public_mask", "public_depth", "public_camera_calibration",
            "public_camera_pose",
        ],
    }
    record["subject_seal_sha256"] = _sha(record)
    return record


def assess_public_visibility_from_depth(
    *, subject: Mapping[str, Any], current_observation_index: int,
    public_depth_m: Any, camera_calibration: Mapping[str, Any],
    camera_pose: Mapping[str, Any], current_public_support_sha256: str | None,
    terminal_reobservation_phase: bool,
    config: Vm04PublicVisibilityConfig,
) -> dict[str, Any]:
    """Project a sealed subject and return assessment plus an input receipt."""

    value = clone_json(dict(subject))
    seal = value.pop("subject_seal_sha256", None)
    if seal != _sha(value) or value.get("schema_version") != SUBJECT_SCHEMA:
        raise ValueError("public visibility subject seal mismatch")
    if value.get("config_sha256") != _sha(asdict(config)):
        raise ValueError("visibility subject config mismatch")
    if (type(current_observation_index) is not int or
            current_observation_index <= value["source_observation_index"]):
        raise ValueError("visibility assessment must follow subject sealing")
    depth = np.asarray(public_depth_m)
    if depth.ndim != 2 or not np.issubdtype(depth.dtype, np.floating):
        raise ValueError("current public depth must be a floating matrix")
    fx, fy, cx, cy, position, rotation = _camera_values(
        camera_calibration, camera_pose,
    )
    world = np.asarray(value["sample_points_world_m"], dtype=np.float64)
    camera = (world - position) @ rotation
    positive = camera[:, 2] > 0.0
    u = np.rint(fx * camera[:, 0] / np.where(positive, camera[:, 2], 1.0) + cx)
    v = np.rint(cy - fy * camera[:, 1] / np.where(positive, camera[:, 2], 1.0))
    inside = (positive & (u >= 0) & (u < depth.shape[1]) &
              (v >= 0) & (v < depth.shape[0]))
    projected_indices = np.flatnonzero(inside)
    unoccluded = 0
    for index in projected_indices:
        observed = float(depth[int(v[index]), int(u[index])])
        subject_z = float(camera[index, 2])
        if (not math.isfinite(observed) or
                observed < config.minimum_depth_m or
                observed > config.maximum_depth_m or
                observed + config.occlusion_depth_tolerance_m >= subject_z):
            unoccluded += 1
    assessment = make_public_visibility_assessment(
        subject_public_ref=value["subject_public_ref"],
        subject_reference_sealed_before_frame=True,
        projected_public_sample_count=len(projected_indices),
        unoccluded_public_sample_count=unoccluded,
        current_public_support_sha256=current_public_support_sha256,
        terminal_reobservation_phase=terminal_reobservation_phase,
    )
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "subject_seal_sha256": seal,
        "current_observation_index": current_observation_index,
        "current_public_depth_sha256": _array_sha(depth),
        "camera_calibration_and_pose_sha256": _sha({
            "calibration": dict(camera_calibration), "pose": dict(camera_pose),
        }),
        "config_sha256": _sha(asdict(config)),
        "assessment_sha256": assessment["assessment_sha256"],
        "invalid_or_missing_depth_treated_as_unoccluded": True,
    }
    receipt["receipt_sha256"] = _sha(receipt)
    return {"assessment": assessment, "receipt": receipt}
