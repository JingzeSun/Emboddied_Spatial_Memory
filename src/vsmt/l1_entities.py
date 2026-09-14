"""Public L1 entity descriptors and visible geometry.

The caller supplies already-anonymized masks, current public RGB/depth, public
camera calibration/pose, and frozen DINOv2 patch tokens.  This module never
reads simulator identity, class, mesh, bounding boxes, future observations, or
teacher data.  It describes only the currently visible pixels and deliberately
does not complete hidden object geometry.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

import numpy as np

from .l1_masks import AnonymousMask


AI2THOR_CAMERA_AXIS_Z = "ai2thor_linear01_camera_axis_z_m"
PROPOSAL_SOURCE_ID = "l1.oracle_mask.dinov2_vits14.public_depth.v1"


class L1EntityConstructionError(ValueError):
    """A stable public failure reason, suitable for preserving in receipts."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class DINORegionConfig:
    image_height: int
    image_width: int
    patch_size_pixels: int
    patch_token_dimension: int
    minimum_total_patch_weight: float
    unit_norm_validation_tolerance: float

    def __post_init__(self) -> None:
        integers = (
            self.image_height,
            self.image_width,
            self.patch_size_pixels,
            self.patch_token_dimension,
        )
        if any(type(value) is not int or value < 1 for value in integers):
            raise ValueError("DINO image, patch, and token sizes must be positive integers")
        if (
            self.image_height % self.patch_size_pixels != 0
            or self.image_width % self.patch_size_pixels != 0
        ):
            raise ValueError("DINO image dimensions must be divisible by patch size")
        if not math.isfinite(self.minimum_total_patch_weight) or self.minimum_total_patch_weight <= 0:
            raise ValueError("minimum_total_patch_weight must be finite and positive")
        if (
            not math.isfinite(self.unit_norm_validation_tolerance)
            or not 0 < self.unit_norm_validation_tolerance < 1
        ):
            raise ValueError("unit_norm_validation_tolerance must lie within (0, 1)")

    @property
    def patch_grid(self) -> tuple[int, int]:
        return (
            self.image_height // self.patch_size_pixels,
            self.image_width // self.patch_size_pixels,
        )


@dataclass(frozen=True)
class PublicGeometryConfig:
    depth_convention: str
    minimum_depth_m: float
    maximum_depth_m: float
    absolute_minimum_valid_depth_points: int
    minimum_valid_depth_fraction: float

    def __post_init__(self) -> None:
        if self.depth_convention != AI2THOR_CAMERA_AXIS_Z:
            raise ValueError(f"unsupported depth convention: {self.depth_convention!r}")
        if not (
            math.isfinite(self.minimum_depth_m)
            and math.isfinite(self.maximum_depth_m)
            and 0 < self.minimum_depth_m < self.maximum_depth_m
        ):
            raise ValueError("depth range must be finite, positive, and ordered")
        if (
            type(self.absolute_minimum_valid_depth_points) is not int
            or self.absolute_minimum_valid_depth_points < 1
        ):
            raise ValueError("absolute minimum depth support must be a positive integer")
        if (
            not math.isfinite(self.minimum_valid_depth_fraction)
            or not 0 < self.minimum_valid_depth_fraction <= 1
        ):
            raise ValueError("minimum_valid_depth_fraction must lie within (0, 1]")

    def required_valid_depth_points(self, visible_pixel_count: int) -> int:
        if type(visible_pixel_count) is not int or visible_pixel_count < 1:
            raise ValueError("visible_pixel_count must be a positive integer")
        return max(
            self.absolute_minimum_valid_depth_points,
            math.ceil(self.minimum_valid_depth_fraction * visible_pixel_count),
        )


@dataclass(frozen=True)
class DINORegionDescriptor:
    values: tuple[float, ...]
    total_patch_weight: float


@dataclass(frozen=True)
class PublicEntityGeometry:
    centroid_m: tuple[float, float, float]
    extent_m: tuple[float, float, float]
    reliability: float
    valid_depth_point_count: int
    required_valid_depth_point_count: int


@dataclass(frozen=True)
class L1EntityObservation:
    region_id: str
    mask_sha256: str
    descriptor: DINORegionDescriptor
    geometry: PublicEntityGeometry

    def public_record(self) -> dict[str, Any]:
        return {
            "region_id": self.region_id,
            "structure_kind": "entity",
            "mask_sha256": self.mask_sha256,
            "descriptor": list(self.descriptor.values),
            "centroid_m": list(self.geometry.centroid_m),
            "extent_m": list(self.geometry.extent_m),
            "reliability": self.geometry.reliability,
            "proposal_source_id": PROPOSAL_SOURCE_ID,
        }


def preprocess_dinov2_rgb(rgb: Any, config: DINORegionConfig) -> np.ndarray:
    """Convert exact uint8 sRGB bytes to a normalized CHW float32 tensor."""

    array = np.asarray(rgb)
    expected = (config.image_height, config.image_width, 3)
    if array.dtype != np.uint8 or array.shape != expected:
        raise ValueError(f"RGB must be uint8 with shape {expected}")
    value = np.ascontiguousarray(array.transpose(2, 0, 1), dtype=np.float32)
    value /= np.float32(255.0)
    mean = np.asarray([0.485, 0.456, 0.406], dtype=np.float32)[:, None, None]
    standard_deviation = np.asarray(
        [0.229, 0.224, 0.225], dtype=np.float32,
    )[:, None, None]
    return np.ascontiguousarray((value - mean) / standard_deviation)


def extract_dinov2_patch_tokens(
    model: Any, rgb: Any, config: DINORegionConfig, *, device: str,
) -> np.ndarray:
    """Run a caller-provided frozen DINOv2 model without reading any assets."""

    import torch

    if getattr(model, "training", True):
        raise ValueError("DINOv2 model must be in evaluation mode")
    if any(parameter.requires_grad for parameter in model.parameters()):
        raise ValueError("DINOv2 model parameters must be frozen")
    image = torch.from_numpy(preprocess_dinov2_rgb(rgb, config)).unsqueeze(0).to(device)
    with torch.inference_mode():
        features = model.forward_features(image)
    if type(features) is not dict or "x_norm_patchtokens" not in features:
        raise ValueError("DINOv2 forward_features did not return patch tokens")
    tokens = features["x_norm_patchtokens"].detach().to("cpu", torch.float32).numpy()
    expected = (1, config.patch_grid[0] * config.patch_grid[1], config.patch_token_dimension)
    if tokens.shape != expected or not np.isfinite(tokens).all():
        raise ValueError(f"DINOv2 patch tokens must be finite with shape {expected}")
    return np.ascontiguousarray(tokens[0].reshape(*config.patch_grid, -1))


def mask_patch_weights(mask: Any, config: DINORegionConfig) -> np.ndarray:
    array = np.asarray(mask)
    expected = (config.image_height, config.image_width)
    if array.shape != expected or array.dtype != np.bool_:
        raise ValueError(f"anonymous mask must be bool with shape {expected}")
    patch = config.patch_size_pixels
    grid_height, grid_width = config.patch_grid
    weights = array.reshape(grid_height, patch, grid_width, patch).mean(axis=(1, 3))
    return np.ascontiguousarray(weights, dtype=np.float64)


def pool_dinov2_region_descriptor(
    patch_tokens: Any, mask: Any, config: DINORegionConfig,
) -> DINORegionDescriptor:
    """Occupancy-weighted patch mean followed by float32 L2 normalization."""

    tokens = np.asarray(patch_tokens)
    expected = (*config.patch_grid, config.patch_token_dimension)
    if tokens.shape != expected or not np.issubdtype(tokens.dtype, np.floating):
        raise ValueError(f"patch tokens must be floating point with shape {expected}")
    if not np.isfinite(tokens).all():
        raise L1EntityConstructionError("nonfinite_patch_tokens")
    weights = mask_patch_weights(mask, config)
    total_weight = float(weights.sum(dtype=np.float64))
    if total_weight < config.minimum_total_patch_weight:
        raise L1EntityConstructionError("insufficient_dino_patch_support")
    pooled = np.sum(
        tokens.astype(np.float64, copy=False) * weights[..., None], axis=(0, 1),
    ) / total_weight
    norm = float(np.linalg.norm(pooled))
    if not math.isfinite(norm) or norm <= 0:
        raise L1EntityConstructionError("zero_or_nonfinite_dino_descriptor")
    values = np.asarray(pooled / norm, dtype=np.float32)
    stored_norm = float(np.linalg.norm(values.astype(np.float64)))
    if abs(stored_norm - 1.0) > config.unit_norm_validation_tolerance:
        raise L1EntityConstructionError("dino_descriptor_unit_norm_failure")
    return DINORegionDescriptor(
        values=tuple(float(value) for value in values),
        total_patch_weight=total_weight,
    )


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
        raise ValueError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _camera_values(
    calibration: Mapping[str, Any], pose: Mapping[str, Any],
) -> tuple[float, float, float, float, np.ndarray, np.ndarray]:
    if set(calibration) != {"fx", "fy", "cx", "cy"}:
        raise ValueError("camera calibration must contain exactly fx, fy, cx, cy")
    fx = _finite_number(calibration["fx"], "fx")
    fy = _finite_number(calibration["fy"], "fy")
    cx = _finite_number(calibration["cx"], "cx")
    cy = _finite_number(calibration["cy"], "cy")
    if fx <= 0 or fy <= 0:
        raise ValueError("camera focal lengths must be positive")
    if set(pose) != {"position_m", "quaternion_xyzw"}:
        raise ValueError("camera pose must contain exactly position_m and quaternion_xyzw")
    position = np.asarray(pose["position_m"], dtype=np.float64)
    quaternion = np.asarray(pose["quaternion_xyzw"], dtype=np.float64)
    if position.shape != (3,) or quaternion.shape != (4,):
        raise ValueError("camera position/quaternion must have lengths 3/4")
    if not np.isfinite(position).all() or not np.isfinite(quaternion).all():
        raise ValueError("camera pose must be finite")
    if abs(float(np.linalg.norm(quaternion)) - 1.0) > 1e-6:
        raise ValueError("camera quaternion must have unit norm")
    x, y, z, w = quaternion
    rotation = np.asarray([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ], dtype=np.float64)
    return fx, fy, cx, cy, position, rotation


def backproject_public_entity_geometry(
    mask: Any,
    depth_m: Any,
    calibration: Mapping[str, Any],
    pose: Mapping[str, Any],
    config: PublicGeometryConfig,
) -> PublicEntityGeometry:
    """Backproject AI2-THOR camera-axis depth into visible world points.

    Camera coordinates use +x right, +y up, and +z forward.  Pixel coordinates
    use u=column and v=row with no half-pixel offset: x=(u-cx)z/fx,
    y=(cy-v)z/fy.  The public xyzw camera-to-world quaternion and translation
    then transform those points.  Depth is axial z, not Euclidean ray length.
    """

    binary = np.asarray(mask)
    depth = np.asarray(depth_m)
    if binary.ndim != 2 or binary.dtype != np.bool_:
        raise ValueError("anonymous mask must be a two-dimensional bool array")
    if depth.shape != binary.shape or not np.issubdtype(depth.dtype, np.floating):
        raise ValueError("depth must be floating point and match the mask shape")
    visible_pixel_count = int(binary.sum())
    if visible_pixel_count < 1:
        raise L1EntityConstructionError("empty_anonymous_mask")
    valid = (
        binary
        & np.isfinite(depth)
        & (depth >= config.minimum_depth_m)
        & (depth <= config.maximum_depth_m)
    )
    valid_count = int(valid.sum())
    required = config.required_valid_depth_points(visible_pixel_count)
    if valid_count < required:
        raise L1EntityConstructionError("insufficient_valid_depth_support")
    fx, fy, cx, cy, position, rotation = _camera_values(calibration, pose)
    rows, columns = np.nonzero(valid)
    z_camera = depth[valid].astype(np.float64, copy=False)
    camera_points = np.column_stack((
        (columns.astype(np.float64) - cx) * z_camera / fx,
        (cy - rows.astype(np.float64)) * z_camera / fy,
        z_camera,
    ))
    world_points = camera_points @ rotation.T + position
    centroid = world_points.mean(axis=0)
    extent = world_points.max(axis=0) - world_points.min(axis=0)
    if not np.isfinite(centroid).all() or not np.isfinite(extent).all():
        raise L1EntityConstructionError("nonfinite_public_geometry")
    return PublicEntityGeometry(
        centroid_m=tuple(float(value) for value in centroid),
        extent_m=tuple(float(value) for value in extent),
        reliability=float(valid_count / visible_pixel_count),
        valid_depth_point_count=valid_count,
        required_valid_depth_point_count=required,
    )


def materialize_l1_entity_observation(
    region: AnonymousMask,
    patch_tokens: Any,
    depth_m: Any,
    calibration: Mapping[str, Any],
    pose: Mapping[str, Any],
    descriptor_config: DINORegionConfig,
    geometry_config: PublicGeometryConfig,
) -> L1EntityObservation:
    mask = region.as_array()
    descriptor = pool_dinov2_region_descriptor(
        patch_tokens, mask, descriptor_config,
    )
    geometry = backproject_public_entity_geometry(
        mask, depth_m, calibration, pose, geometry_config,
    )
    return L1EntityObservation(
        region_id=region.region_id,
        mask_sha256=region.mask_sha256,
        descriptor=descriptor,
        geometry=geometry,
    )
