"""Public-depth L1 surfaces, places, free-space frusta, and relations.

All geometry is derived from current or already-public RGB-D packets, camera
calibration, camera pose, and the fixed standing-agent calibration.  This
module has no simulator metadata, navigation mesh, room label, teacher,
reference transaction, or future-data input.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from itertools import product
import math
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from cpmt.hashing import canonical_json

from .l1_entities import (
    DINORegionConfig,
    L1EntityConstructionError,
    L1EntityObservation,
    _camera_values,
    pool_dinov2_region_descriptor,
)
from .l1_masks import AnonymousMask


SURFACE_PROPOSAL_SOURCE_ID = "l1.public_depth.planar_surface.v1"
PLACE_PROPOSAL_SOURCE_ID = "l1.public_depth.floor_place_cell.v1"
RELATION_TYPES = {"located_at", "contains", "supported_by", "adjacent_to"}


class L1StructureConstructionError(ValueError):
    """A stable public failure reason for receipts and audit summaries."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _positive(value: float, name: str) -> float:
    if not math.isfinite(float(value)) or float(value) <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return float(value)


def _fraction(value: float, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or not 0.0 < result <= 1.0:
        raise ValueError(f"{name} must lie within (0, 1]")
    return result


def _positive_integer(value: int, name: str) -> int:
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


@dataclass(frozen=True)
class SurfaceMaterializationConfig:
    tile_size_pixels: int
    minimum_valid_depth_fraction_per_tile: float
    initial_maximum_rms_point_to_plane_m: float
    initial_maximum_p95_point_to_plane_m: float
    merge_maximum_normal_angle_degrees: float
    merge_maximum_mutual_centroid_to_plane_m: float
    final_inlier_point_to_plane_m: float
    final_minimum_inlier_fraction: float
    final_maximum_rms_point_to_plane_m: float
    minimum_inlier_pixels: int
    minimum_depth_m: float
    maximum_depth_m: float

    def __post_init__(self) -> None:
        _positive_integer(self.tile_size_pixels, "tile_size_pixels")
        _fraction(
            self.minimum_valid_depth_fraction_per_tile,
            "minimum_valid_depth_fraction_per_tile",
        )
        _positive(
            self.initial_maximum_rms_point_to_plane_m,
            "initial_maximum_rms_point_to_plane_m",
        )
        _positive(
            self.initial_maximum_p95_point_to_plane_m,
            "initial_maximum_p95_point_to_plane_m",
        )
        _positive(
            self.merge_maximum_normal_angle_degrees,
            "merge_maximum_normal_angle_degrees",
        )
        _positive(
            self.merge_maximum_mutual_centroid_to_plane_m,
            "merge_maximum_mutual_centroid_to_plane_m",
        )
        _positive(
            self.final_inlier_point_to_plane_m,
            "final_inlier_point_to_plane_m",
        )
        _fraction(self.final_minimum_inlier_fraction, "final_minimum_inlier_fraction")
        _positive(
            self.final_maximum_rms_point_to_plane_m,
            "final_maximum_rms_point_to_plane_m",
        )
        _positive_integer(self.minimum_inlier_pixels, "minimum_inlier_pixels")
        minimum = _positive(self.minimum_depth_m, "minimum_depth_m")
        maximum = _positive(self.maximum_depth_m, "maximum_depth_m")
        if minimum >= maximum:
            raise ValueError("depth range must be ordered")


@dataclass(frozen=True)
class PlaceMaterializationConfig:
    maximum_floor_normal_angle_degrees: float
    maximum_support_height_difference_m: float
    cell_size_m: float
    grid_origin_m: tuple[float, float, float]
    coverage_subcell_size_m: float
    minimum_covered_subcells: int
    minimum_mask_pixels: int
    camera_to_agent_center_y_m: float
    agent_half_height_m: float
    located_at_boundary_margin_m: float

    def __post_init__(self) -> None:
        _positive(
            self.maximum_floor_normal_angle_degrees,
            "maximum_floor_normal_angle_degrees",
        )
        _positive(
            self.maximum_support_height_difference_m,
            "maximum_support_height_difference_m",
        )
        cell = _positive(self.cell_size_m, "cell_size_m")
        subcell = _positive(self.coverage_subcell_size_m, "coverage_subcell_size_m")
        if not math.isclose(cell / subcell, round(cell / subcell), abs_tol=1e-12):
            raise ValueError("place cell must contain an integer subcell grid")
        if len(self.grid_origin_m) != 3 or not all(
            math.isfinite(float(value)) for value in self.grid_origin_m
        ):
            raise ValueError("grid_origin_m must contain three finite values")
        per_axis = int(round(cell / subcell))
        if not 1 <= self.minimum_covered_subcells <= per_axis * per_axis:
            raise ValueError("minimum_covered_subcells is outside the place cell")
        _positive_integer(self.minimum_mask_pixels, "minimum_mask_pixels")
        _positive(self.camera_to_agent_center_y_m, "camera_to_agent_center_y_m")
        _positive(self.agent_half_height_m, "agent_half_height_m")
        margin = _positive(self.located_at_boundary_margin_m, "located_at_boundary_margin_m")
        if 2.0 * margin >= cell:
            raise ValueError("located-at boundary margin leaves no place interior")

    @property
    def subcells_per_axis(self) -> int:
        return int(round(self.cell_size_m / self.coverage_subcell_size_m))


@dataclass(frozen=True)
class FreeSpaceMaterializationConfig:
    tile_size_pixels: int
    block_widths_in_tiles: tuple[int, ...]
    angular_boundary_erosion_pixels: int
    minimum_depth_m: float
    maximum_valid_depth_m: float
    near_axis_depth_m: float
    surface_clearance_m: float
    maximum_axis_depth_m: float
    minimum_longitudinal_thickness_m: float
    rolling_public_observation_times: int

    def __post_init__(self) -> None:
        _positive_integer(self.tile_size_pixels, "tile_size_pixels")
        if (
            not self.block_widths_in_tiles
            or tuple(sorted(set(self.block_widths_in_tiles)))
            != self.block_widths_in_tiles
            or any(type(value) is not int or value < 1 for value in self.block_widths_in_tiles)
        ):
            raise ValueError("block widths must be unique ascending positive integers")
        if (
            type(self.angular_boundary_erosion_pixels) is not int
            or not 0 <= self.angular_boundary_erosion_pixels
            < self.tile_size_pixels / 2
        ):
            raise ValueError("angular erosion must leave a nonempty base tile")
        minimum = _positive(self.minimum_depth_m, "minimum_depth_m")
        maximum = _positive(self.maximum_valid_depth_m, "maximum_valid_depth_m")
        if minimum >= maximum:
            raise ValueError("valid depth range must be ordered")
        near = _positive(self.near_axis_depth_m, "near_axis_depth_m")
        clearance = _positive(self.surface_clearance_m, "surface_clearance_m")
        far = _positive(self.maximum_axis_depth_m, "maximum_axis_depth_m")
        thickness = _positive(
            self.minimum_longitudinal_thickness_m,
            "minimum_longitudinal_thickness_m",
        )
        if near + thickness > far or clearance >= far:
            raise ValueError("free-space near/far/clearance values are inconsistent")
        _positive_integer(
            self.rolling_public_observation_times,
            "rolling_public_observation_times",
        )


@dataclass(frozen=True)
class MaterializedRegion:
    structure_kind: str
    mask_sha256: str
    mask_bytes: bytes
    mask_first_true_index: int
    mask_pixel_count: int
    height: int
    width: int
    descriptor: tuple[float, ...]
    centroid_m: tuple[float, float, float]
    extent_m: tuple[float, float, float]
    reliability: float
    proposal_source_id: str
    plane_normal: tuple[float, float, float] | None = None
    plane_offset_m: float | None = None
    place_cell_xz: tuple[int, int] | None = None

    def mask_array(self) -> np.ndarray:
        values = np.frombuffer(self.mask_bytes, dtype=np.uint8)
        if len(values) != self.height * self.width:
            raise L1StructureConstructionError("materialized_mask_shape_mismatch")
        return values.astype(np.bool_, copy=True).reshape(self.height, self.width)

    def public_record(self, region_id: str) -> dict[str, Any]:
        return {
            "region_id": region_id,
            "structure_kind": self.structure_kind,
            "mask_sha256": self.mask_sha256,
            "descriptor": list(self.descriptor),
            "centroid_m": list(self.centroid_m),
            "extent_m": list(self.extent_m),
            "reliability": self.reliability,
            "proposal_source_id": self.proposal_source_id,
        }


@dataclass(frozen=True)
class RejectedPlaceCell:
    place_cell_xz: tuple[int, int]
    mask_sha256: str
    mask_pixel_count: int
    covered_subcells: int
    reason: str

    def public_record(self) -> dict[str, Any]:
        return {
            "place_cell_xz": list(self.place_cell_xz),
            "mask_sha256": self.mask_sha256,
            "mask_pixel_count": self.mask_pixel_count,
            "covered_subcells": self.covered_subcells,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class PlaceMaterialization:
    regions: tuple[MaterializedRegion, ...]
    rejected: tuple[RejectedPlaceCell, ...]


@dataclass(frozen=True)
class FreeSpaceFrustum:
    time_s: float
    halfspaces_world: tuple[tuple[tuple[float, float, float], float], ...]
    support_sha256: str
    block_width_tiles: int
    block_row: int
    block_column: int

    def public_record(self, free_space_id: str) -> dict[str, Any]:
        return {
            "free_space_id": free_space_id,
            "time_s": self.time_s,
            "halfspaces_world": [
                {"normal": list(normal), "offset_m": offset}
                for normal, offset in self.halfspaces_world
            ],
            "reliability": 1.0,
            "support_sha256": self.support_sha256,
        }


@dataclass(frozen=True)
class VisibilityFrustum:
    """Node-independent public volume in which a structure could be observed."""

    time_s: float
    halfspaces_world: tuple[tuple[tuple[float, float, float], float], ...]
    support_sha256: str
    block_width_tiles: int
    block_row: int
    block_column: int

    def public_record(self, visibility_id: str) -> dict[str, Any]:
        return {
            "visibility_id": visibility_id,
            "time_s": self.time_s,
            "halfspaces_world": [
                {"normal": list(normal), "offset_m": offset}
                for normal, offset in self.halfspaces_world
            ],
            "reliability": 1.0,
            "support_sha256": self.support_sha256,
        }


def _mask_sha256(mask: np.ndarray) -> str:
    height, width = mask.shape
    payload = [int(height), int(width), *mask.astype(np.uint8).reshape(-1).tolist()]
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _mask_storage(mask: np.ndarray) -> tuple[bytes, int, int]:
    """Store one byte per pixel and cache deterministic ordering statistics."""

    binary = np.ascontiguousarray(mask, dtype=np.uint8).reshape(-1)
    indices = np.flatnonzero(binary)
    if not len(indices):
        raise L1StructureConstructionError("empty_materialized_mask")
    return binary.tobytes(), int(indices[0]), int(len(indices))


def _world_point_grid(
    depth_m: Any, calibration: Mapping[str, Any], pose: Mapping[str, Any], *,
    minimum_depth_m: float, maximum_depth_m: float,
) -> tuple[np.ndarray, np.ndarray]:
    depth = np.asarray(depth_m)
    if depth.ndim != 2 or not np.issubdtype(depth.dtype, np.floating):
        raise ValueError("depth must be a two-dimensional floating array")
    valid = (
        np.isfinite(depth)
        & (depth >= minimum_depth_m)
        & (depth <= maximum_depth_m)
    )
    fx, fy, cx, cy, position, rotation = _camera_values(calibration, pose)
    rows, columns = np.indices(depth.shape, dtype=np.float64)
    z = depth.astype(np.float64, copy=False)
    camera = np.stack((
        (columns - cx) * z / fx,
        (cy - rows) * z / fy,
        z,
    ), axis=-1)
    world = camera @ rotation.T + position
    world[~valid] = np.nan
    return world, valid


def _canonical_plane(points: np.ndarray) -> tuple[np.ndarray, float, float, float]:
    if points.ndim != 2 or points.shape[1] != 3 or len(points) < 3:
        raise L1StructureConstructionError("insufficient_plane_points")
    centroid = points.mean(axis=0)
    covariance = (points - centroid).T @ (points - centroid) / float(len(points))
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    if not np.isfinite(eigenvalues).all() or eigenvalues[1] <= 1e-12:
        raise L1StructureConstructionError("degenerate_plane_points")
    normal = eigenvectors[:, 0]
    pivot = int(np.argmax(np.abs(normal)))
    if normal[pivot] < 0.0:
        normal = -normal
    normal /= np.linalg.norm(normal)
    offset = float(normal @ centroid)
    residuals = np.abs(points @ normal - offset)
    rms = float(math.sqrt(float(np.mean(residuals * residuals))))
    ordered = np.sort(residuals)
    p95 = float(ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)])
    return normal, offset, rms, p95


def _normal_angle_degrees(left: np.ndarray, right: np.ndarray) -> float:
    cosine = abs(float(left @ right))
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))


def materialize_public_surfaces(
    depth_m: Any, calibration: Mapping[str, Any], pose: Mapping[str, Any],
    patch_tokens: Any, descriptor_config: DINORegionConfig,
    config: SurfaceMaterializationConfig,
) -> tuple[MaterializedRegion, ...]:
    """Return deterministic planar regions using public depth only."""

    world, valid = _world_point_grid(
        depth_m, calibration, pose,
        minimum_depth_m=config.minimum_depth_m,
        maximum_depth_m=config.maximum_depth_m,
    )
    height, width = valid.shape
    tile = config.tile_size_pixels
    if height % tile or width % tile:
        raise ValueError("image dimensions must be divisible by the surface tile size")
    tile_rows = height // tile
    tile_columns = width // tile
    minimum_tile_points = math.ceil(
        config.minimum_valid_depth_fraction_per_tile * tile * tile
    )
    accepted: dict[tuple[int, int], tuple[np.ndarray, float, np.ndarray]] = {}
    for tile_row in range(tile_rows):
        for tile_column in range(tile_columns):
            row_slice = slice(tile_row * tile, (tile_row + 1) * tile)
            column_slice = slice(tile_column * tile, (tile_column + 1) * tile)
            tile_valid = valid[row_slice, column_slice]
            if int(tile_valid.sum()) < minimum_tile_points:
                continue
            points = world[row_slice, column_slice][tile_valid]
            try:
                normal, offset, rms, p95 = _canonical_plane(points)
            except L1StructureConstructionError:
                continue
            if (
                rms <= config.initial_maximum_rms_point_to_plane_m
                and p95 <= config.initial_maximum_p95_point_to_plane_m
            ):
                accepted[(tile_row, tile_column)] = (
                    normal, offset, points.mean(axis=0),
                )

    parent = {key: key for key in accepted}

    def find(key: tuple[int, int]) -> tuple[int, int]:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(left: tuple[int, int], right: tuple[int, int]) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    for key in sorted(accepted):
        for neighbor in ((key[0], key[1] + 1), (key[0] + 1, key[1])):
            if neighbor not in accepted:
                continue
            left_normal, left_offset, left_centroid = accepted[key]
            right_normal, right_offset, right_centroid = accepted[neighbor]
            if _normal_angle_degrees(left_normal, right_normal) > (
                config.merge_maximum_normal_angle_degrees
            ):
                continue
            residual = max(
                abs(float(left_normal @ right_centroid) - left_offset),
                abs(float(right_normal @ left_centroid) - right_offset),
            )
            if residual <= config.merge_maximum_mutual_centroid_to_plane_m:
                union(key, neighbor)

    components: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for key in sorted(accepted):
        components.setdefault(find(key), []).append(key)

    results: list[MaterializedRegion] = []
    for keys in components.values():
        candidate_mask = np.zeros((height, width), dtype=np.bool_)
        for tile_row, tile_column in keys:
            row_slice = slice(tile_row * tile, (tile_row + 1) * tile)
            column_slice = slice(tile_column * tile, (tile_column + 1) * tile)
            candidate_mask[row_slice, column_slice] = valid[row_slice, column_slice]
        candidate_points = world[candidate_mask]
        try:
            normal, offset, _, _ = _canonical_plane(candidate_points)
        except L1StructureConstructionError:
            continue
        residuals = np.abs(candidate_points @ normal - offset)
        inlier_values = residuals <= config.final_inlier_point_to_plane_m
        inlier_count = int(inlier_values.sum())
        if (
            inlier_count < config.minimum_inlier_pixels
            or inlier_count / len(candidate_points)
            < config.final_minimum_inlier_fraction
        ):
            continue
        candidate_indices = np.flatnonzero(candidate_mask)
        inlier_mask = np.zeros((height, width), dtype=np.bool_)
        inlier_mask.reshape(-1)[candidate_indices[inlier_values]] = True
        inlier_points = world[inlier_mask]
        try:
            normal, offset, rms, _ = _canonical_plane(inlier_points)
        except L1StructureConstructionError:
            continue
        if rms > config.final_maximum_rms_point_to_plane_m:
            continue
        descriptor = pool_dinov2_region_descriptor(
            patch_tokens, inlier_mask, descriptor_config,
        )
        centroid = inlier_points.mean(axis=0)
        extent = inlier_points.max(axis=0) - inlier_points.min(axis=0)
        mask_bytes, first_true, pixel_count = _mask_storage(inlier_mask)
        results.append(MaterializedRegion(
            structure_kind="surface",
            mask_sha256=_mask_sha256(inlier_mask),
            mask_bytes=mask_bytes,
            mask_first_true_index=first_true,
            mask_pixel_count=pixel_count,
            height=height,
            width=width,
            descriptor=descriptor.values,
            centroid_m=tuple(float(value) for value in centroid),
            extent_m=tuple(float(value) for value in extent),
            reliability=float(inlier_count / len(candidate_points)),
            proposal_source_id=SURFACE_PROPOSAL_SOURCE_ID,
            plane_normal=tuple(float(value) for value in normal),
            plane_offset_m=float(offset),
        ))
    return tuple(sorted(results, key=lambda item: (
        item.mask_first_true_index, item.mask_pixel_count, item.mask_sha256,
    )))


def materialize_public_places(
    surfaces: Sequence[MaterializedRegion], depth_m: Any,
    calibration: Mapping[str, Any], pose: Mapping[str, Any], patch_tokens: Any,
    descriptor_config: DINORegionConfig, surface_config: SurfaceMaterializationConfig,
    config: PlaceMaterializationConfig,
) -> PlaceMaterialization:
    """Return accepted place cells and stable public reasons for rejected cells."""

    world, _ = _world_point_grid(
        depth_m, calibration, pose,
        minimum_depth_m=surface_config.minimum_depth_m,
        maximum_depth_m=surface_config.maximum_depth_m,
    )
    _, _, _, _, camera_position, _ = _camera_values(calibration, pose)
    support_height = (
        float(camera_position[1])
        - config.camera_to_agent_center_y_m
        - config.agent_half_height_m
    )
    up = np.asarray([0.0, 1.0, 0.0], dtype=np.float64)
    cell_masks: dict[tuple[int, int], np.ndarray] = {}
    origin_x = float(config.grid_origin_m[0])
    origin_z = float(config.grid_origin_m[2])
    for surface in surfaces:
        if surface.plane_normal is None or surface.plane_offset_m is None:
            continue
        normal = np.asarray(surface.plane_normal, dtype=np.float64)
        if _normal_angle_degrees(normal, up) > config.maximum_floor_normal_angle_degrees:
            continue
        if abs(float(surface.centroid_m[1]) - support_height) > (
            config.maximum_support_height_difference_m
        ):
            continue
        mask = surface.mask_array()
        rows, columns = np.nonzero(mask)
        points = world[rows, columns]
        keys = np.column_stack((
            np.floor((points[:, 0] - origin_x) / config.cell_size_m).astype(int),
            np.floor((points[:, 2] - origin_z) / config.cell_size_m).astype(int),
        ))
        for key_values in np.unique(keys, axis=0):
            key = (int(key_values[0]), int(key_values[1]))
            selected = np.logical_and(keys[:, 0] == key[0], keys[:, 1] == key[1])
            cell_mask = cell_masks.setdefault(
                key, np.zeros(mask.shape, dtype=np.bool_),
            )
            cell_mask[rows[selected], columns[selected]] = True

    results: list[MaterializedRegion] = []
    rejected: list[RejectedPlaceCell] = []
    for key, mask in sorted(cell_masks.items()):
        pixel_count = int(mask.sum())
        mask_sha256 = _mask_sha256(mask)
        if pixel_count < config.minimum_mask_pixels:
            rejected.append(RejectedPlaceCell(
                place_cell_xz=key,
                mask_sha256=mask_sha256,
                mask_pixel_count=pixel_count,
                covered_subcells=0,
                reason="below_minimum_place_mask_pixels",
            ))
            continue
        points = world[mask]
        cell_x0 = origin_x + key[0] * config.cell_size_m
        cell_z0 = origin_z + key[1] * config.cell_size_m
        sub_x = np.floor(
            (points[:, 0] - cell_x0) / config.coverage_subcell_size_m
        ).astype(int)
        sub_z = np.floor(
            (points[:, 2] - cell_z0) / config.coverage_subcell_size_m
        ).astype(int)
        per_axis = config.subcells_per_axis
        inside = (
            (0 <= sub_x) & (sub_x < per_axis)
            & (0 <= sub_z) & (sub_z < per_axis)
        )
        covered = len(set(zip(sub_x[inside].tolist(), sub_z[inside].tolist())))
        if covered < config.minimum_covered_subcells:
            rejected.append(RejectedPlaceCell(
                place_cell_xz=key,
                mask_sha256=mask_sha256,
                mask_pixel_count=pixel_count,
                covered_subcells=covered,
                reason="below_minimum_place_subcell_coverage",
            ))
            continue
        try:
            normal, offset, _, _ = _canonical_plane(points)
        except L1StructureConstructionError as caught:
            rejected.append(RejectedPlaceCell(
                place_cell_xz=key,
                mask_sha256=mask_sha256,
                mask_pixel_count=pixel_count,
                covered_subcells=covered,
                reason=caught.reason,
            ))
            continue
        if abs(float(normal[1])) <= 1e-9:
            rejected.append(RejectedPlaceCell(
                place_cell_xz=key,
                mask_sha256=mask_sha256,
                mask_pixel_count=pixel_count,
                covered_subcells=covered,
                reason="place_plane_vertical_component_too_small",
            ))
            continue
        center_x = cell_x0 + config.cell_size_m / 2.0
        center_z = cell_z0 + config.cell_size_m / 2.0
        center_y = (
            offset - float(normal[0]) * center_x - float(normal[2]) * center_z
        ) / float(normal[1])
        try:
            descriptor = pool_dinov2_region_descriptor(
                patch_tokens, mask, descriptor_config,
            )
        except L1EntityConstructionError as caught:
            rejected.append(RejectedPlaceCell(
                place_cell_xz=key,
                mask_sha256=mask_sha256,
                mask_pixel_count=pixel_count,
                covered_subcells=covered,
                reason=caught.reason,
            ))
            continue
        mask_bytes, first_true, stored_pixel_count = _mask_storage(mask)
        results.append(MaterializedRegion(
            structure_kind="place",
            mask_sha256=mask_sha256,
            mask_bytes=mask_bytes,
            mask_first_true_index=first_true,
            mask_pixel_count=stored_pixel_count,
            height=mask.shape[0],
            width=mask.shape[1],
            descriptor=descriptor.values,
            centroid_m=(center_x, float(center_y), center_z),
            extent_m=(config.cell_size_m, 0.0, config.cell_size_m),
            reliability=float(covered / (per_axis * per_axis)),
            proposal_source_id=PLACE_PROPOSAL_SOURCE_ID,
            plane_normal=tuple(float(value) for value in normal),
            plane_offset_m=float(offset),
            place_cell_xz=key,
        ))
    return PlaceMaterialization(
        regions=tuple(sorted(results, key=lambda item: (
            item.mask_first_true_index, item.mask_pixel_count, item.mask_sha256,
        ))),
        rejected=tuple(rejected),
    )


def _normalized_halfspace(
    normal: np.ndarray, offset: float,
) -> tuple[np.ndarray, float]:
    norm = float(np.linalg.norm(normal))
    if not math.isfinite(norm) or norm <= 0.0:
        raise L1StructureConstructionError("degenerate_free_space_halfspace")
    return normal / norm, float(offset / norm)


def _world_halfspace(
    camera_normal: np.ndarray, camera_offset: float,
    position: np.ndarray, rotation: np.ndarray,
) -> tuple[tuple[float, float, float], float]:
    normal, offset = _normalized_halfspace(camera_normal, camera_offset)
    world_normal = rotation @ normal
    world_offset = offset + float(world_normal @ position)
    return (
        tuple(float(value) for value in world_normal),
        float(world_offset),
    )


def materialize_public_free_space(
    depth_m: Any, calibration: Mapping[str, Any], pose: Mapping[str, Any], *,
    time_s: float, depth_sha256: str,
    camera_calibration_and_pose_sha256: str,
    config: FreeSpaceMaterializationConfig,
) -> tuple[FreeSpaceFrustum, ...]:
    """Build at most 341 conservative multiscale frusta for one public frame."""

    if not math.isfinite(float(time_s)) or float(time_s) < 0.0:
        raise ValueError("time_s must be finite and non-negative")
    for name, digest in (
        ("depth_sha256", depth_sha256),
        ("camera_calibration_and_pose_sha256", camera_calibration_and_pose_sha256),
    ):
        if type(digest) is not str or len(digest) != 64 or any(
            character not in "0123456789abcdef" for character in digest
        ):
            raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    depth = np.asarray(depth_m)
    if depth.ndim != 2 or not np.issubdtype(depth.dtype, np.floating):
        raise ValueError("depth must be a two-dimensional floating array")
    height, width = depth.shape
    tile = config.tile_size_pixels
    if height % tile or width % tile or height != width:
        raise ValueError("free-space image must be square and divisible by tile size")
    tile_count = height // tile
    if config.block_widths_in_tiles[-1] != tile_count:
        raise ValueError("largest free-space block must span the image")
    if any(tile_count % block_width for block_width in config.block_widths_in_tiles):
        raise ValueError("every free-space block width must divide the tile grid")
    fx, fy, cx, cy, position, rotation = _camera_values(calibration, pose)
    valid = (
        np.isfinite(depth)
        & (depth >= config.minimum_depth_m)
        & (depth <= config.maximum_valid_depth_m)
    )
    erosion = config.angular_boundary_erosion_pixels
    results: list[FreeSpaceFrustum] = []
    for block_width in config.block_widths_in_tiles:
        pixel_width = block_width * tile
        blocks_per_axis = tile_count // block_width
        for block_row, block_column in product(
            range(blocks_per_axis), range(blocks_per_axis),
        ):
            row0 = block_row * pixel_width
            row1 = row0 + pixel_width
            column0 = block_column * pixel_width
            column1 = column0 + pixel_width
            block_valid = valid[row0:row1, column0:column1]
            if not bool(block_valid.all()):
                continue
            far = min(
                float(np.min(depth[row0:row1, column0:column1]))
                - config.surface_clearance_m,
                config.maximum_axis_depth_m,
            )
            if far - config.near_axis_depth_m < (
                config.minimum_longitudinal_thickness_m
            ):
                continue
            left_u = float(column0 + erosion)
            right_u = float(column1 - 1 - erosion)
            top_v = float(row0 + erosion)
            bottom_v = float(row1 - 1 - erosion)
            if left_u >= right_u or top_v >= bottom_v:
                continue
            left_slope = (left_u - cx) / fx
            right_slope = (right_u - cx) / fx
            bottom_slope = (cy - bottom_v) / fy
            top_slope = (cy - top_v) / fy
            camera_planes = (
                (np.asarray([-1.0, 0.0, left_slope]), 0.0),
                (np.asarray([1.0, 0.0, -right_slope]), 0.0),
                (np.asarray([0.0, -1.0, bottom_slope]), 0.0),
                (np.asarray([0.0, 1.0, -top_slope]), 0.0),
                (np.asarray([0.0, 0.0, -1.0]), -config.near_axis_depth_m),
                (np.asarray([0.0, 0.0, 1.0]), far),
            )
            halfspaces = tuple(
                _world_halfspace(normal, offset, position, rotation)
                for normal, offset in camera_planes
            )
            support = hashlib.sha256(canonical_json({
                "depth_sha256": depth_sha256,
                "time_s": float(time_s),
                "pixel_block": [row0, row1, column0, column1],
                "near_axis_depth_m": config.near_axis_depth_m,
                "far_axis_depth_m": far,
                "camera_calibration_and_pose_sha256": (
                    camera_calibration_and_pose_sha256
                ),
            }).encode("utf-8")).hexdigest()
            results.append(FreeSpaceFrustum(
                time_s=float(time_s),
                halfspaces_world=halfspaces,
                support_sha256=support,
                block_width_tiles=block_width,
                block_row=block_row,
                block_column=block_column,
            ))
    return tuple(results)


def assemble_free_space_history(
    observations: Iterable[Sequence[FreeSpaceFrustum]], *,
    rolling_public_observation_times: int,
) -> list[dict[str, Any]]:
    """Keep the latest distinct public times and assign packet-local ordinals."""

    _positive_integer(
        rolling_public_observation_times, "rolling_public_observation_times",
    )
    by_time: dict[float, list[FreeSpaceFrustum]] = {}
    for group in observations:
        for item in group:
            by_time.setdefault(float(item.time_s), []).append(item)
    retained_times = sorted(by_time)[-rolling_public_observation_times:]
    ordered: list[FreeSpaceFrustum] = []
    for time_s in retained_times:
        ordered.extend(sorted(by_time[time_s], key=lambda item: (
            item.block_width_tiles,
            item.block_row,
            item.block_column,
            item.support_sha256,
        )))
    return [
        item.public_record(f"free:{index:04d}")
        for index, item in enumerate(ordered)
    ]


def materialize_public_visibility(
    free_spaces: Sequence[FreeSpaceFrustum], *, surface_clearance_m: float,
) -> list[dict[str, Any]]:
    """Recover current node-agnostic visibility volumes from public frusta.

    Free space stops before the measured surface.  Visibility extends the far
    plane back to that surface, so a remembered node behind it is occluded and
    a node on or before it is an observation opportunity.
    """

    clearance = _positive(surface_clearance_m, "surface_clearance_m")
    ordered = sorted(free_spaces, key=lambda item: (
        item.block_width_tiles,
        item.block_row,
        item.block_column,
        item.support_sha256,
    ))
    records: list[dict[str, Any]] = []
    for index, item in enumerate(ordered):
        if len(item.halfspaces_world) != 6:
            raise L1StructureConstructionError("visibility_requires_six_halfspaces")
        halfspaces = list(item.halfspaces_world)
        far_normal, far_offset = halfspaces[-1]
        halfspaces[-1] = (far_normal, float(far_offset) + clearance)
        support = hashlib.sha256(canonical_json({
            "free_space_support_sha256": item.support_sha256,
            "surface_clearance_m": clearance,
            "purpose": "node_agnostic_visibility",
        }).encode("utf-8")).hexdigest()
        records.append(VisibilityFrustum(
            time_s=item.time_s,
            halfspaces_world=tuple(halfspaces),
            support_sha256=support,
            block_width_tiles=item.block_width_tiles,
            block_row=item.block_row,
            block_column=item.block_column,
        ).public_record(f"visibility:{index:04d}"))
    return records


def entity_regions_with_masks(
    entities: Sequence[L1EntityObservation], masks: Sequence[AnonymousMask],
) -> tuple[MaterializedRegion, ...]:
    """Join already-anonymized entity records to their public masks by ordinal."""

    mask_by_id = {item.region_id: item for item in masks}
    results: list[MaterializedRegion] = []
    for entity in entities:
        mask = mask_by_id.get(entity.region_id)
        if mask is None or mask.mask_sha256 != entity.mask_sha256:
            raise ValueError("entity observation and anonymous mask do not match")
        mask_bytes, first_true, pixel_count = _mask_storage(mask.as_array())
        results.append(MaterializedRegion(
            structure_kind="entity",
            mask_sha256=entity.mask_sha256,
            mask_bytes=mask_bytes,
            mask_first_true_index=first_true,
            mask_pixel_count=pixel_count,
            height=mask.height,
            width=mask.width,
            descriptor=entity.descriptor.values,
            centroid_m=entity.geometry.centroid_m,
            extent_m=entity.geometry.extent_m,
            reliability=entity.geometry.reliability,
            proposal_source_id="l1.oracle_mask.dinov2_vits14.public_depth.v1",
        ))
    return tuple(results)


def assemble_region_records(
    entities: Sequence[MaterializedRegion], places: Sequence[MaterializedRegion],
    surfaces: Sequence[MaterializedRegion],
) -> tuple[list[dict[str, Any]], dict[str, tuple[str, MaterializedRegion]]]:
    """Assign opaque ordinals after canonical kind/mask ordering."""

    ordered = [
        *sorted(entities, key=lambda item: (
            item.mask_first_true_index, item.mask_pixel_count, item.mask_sha256,
        )),
        *sorted(places, key=lambda item: (
            item.mask_first_true_index, item.mask_pixel_count, item.mask_sha256,
        )),
        *sorted(surfaces, key=lambda item: (
            item.mask_first_true_index, item.mask_pixel_count, item.mask_sha256,
        )),
    ]
    records: list[dict[str, Any]] = []
    indexed: dict[str, tuple[str, MaterializedRegion]] = {}
    for index, item in enumerate(ordered):
        region_id = f"region:{index:04d}"
        records.append(item.public_record(region_id))
        indexed[region_id] = (item.structure_kind, item)
    return records, indexed


def _aabb_overlap_ratio_xz(
    entity: MaterializedRegion, surface: MaterializedRegion,
) -> float:
    entity_x0 = entity.centroid_m[0] - entity.extent_m[0] / 2.0
    entity_x1 = entity.centroid_m[0] + entity.extent_m[0] / 2.0
    entity_z0 = entity.centroid_m[2] - entity.extent_m[2] / 2.0
    entity_z1 = entity.centroid_m[2] + entity.extent_m[2] / 2.0
    area = (entity_x1 - entity_x0) * (entity_z1 - entity_z0)
    if area <= 0.0:
        return 0.0
    surface_x0 = surface.centroid_m[0] - surface.extent_m[0] / 2.0
    surface_x1 = surface.centroid_m[0] + surface.extent_m[0] / 2.0
    surface_z0 = surface.centroid_m[2] - surface.extent_m[2] / 2.0
    surface_z1 = surface.centroid_m[2] + surface.extent_m[2] / 2.0
    overlap_x = max(0.0, min(entity_x1, surface_x1) - max(entity_x0, surface_x0))
    overlap_z = max(0.0, min(entity_z1, surface_z1) - max(entity_z0, surface_z0))
    return float(overlap_x * overlap_z / area)


def materialize_public_relations(
    indexed_regions: Mapping[str, tuple[str, MaterializedRegion]], *,
    place_config: PlaceMaterializationConfig,
    supported_by_maximum_normal_angle_degrees: float,
    supported_by_minimum_gap_m: float,
    supported_by_maximum_gap_m: float,
    supported_by_minimum_projected_overlap: float,
    supported_by_maximum_mask_overlap_fraction: float,
) -> list[dict[str, Any]]:
    """Derive anonymous typed relations from public region geometry only."""

    _positive(
        supported_by_maximum_normal_angle_degrees,
        "supported_by_maximum_normal_angle_degrees",
    )
    if not (
        math.isfinite(supported_by_minimum_gap_m)
        and math.isfinite(supported_by_maximum_gap_m)
        and supported_by_minimum_gap_m <= supported_by_maximum_gap_m
    ):
        raise ValueError("supported-by gap interval must be finite and ordered")
    _fraction(
        supported_by_minimum_projected_overlap,
        "supported_by_minimum_projected_overlap",
    )
    _fraction(
        supported_by_maximum_mask_overlap_fraction,
        "supported_by_maximum_mask_overlap_fraction",
    )
    entities = [
        (region_id, item) for region_id, (kind, item) in indexed_regions.items()
        if kind == "entity"
    ]
    places = [
        (region_id, item) for region_id, (kind, item) in indexed_regions.items()
        if kind == "place"
    ]
    surfaces = [
        (region_id, item) for region_id, (kind, item) in indexed_regions.items()
        if kind == "surface"
    ]
    place_by_cell = {
        item.place_cell_xz: (region_id, item)
        for region_id, item in places if item.place_cell_xz is not None
    }
    rows: list[tuple[str, str, str, float, str]] = []
    origin_x = float(place_config.grid_origin_m[0])
    origin_z = float(place_config.grid_origin_m[2])
    for entity_id, entity in entities:
        x = float(entity.centroid_m[0])
        z = float(entity.centroid_m[2])
        cell = (
            math.floor((x - origin_x) / place_config.cell_size_m),
            math.floor((z - origin_z) / place_config.cell_size_m),
        )
        place_match = place_by_cell.get(cell)
        if place_match is not None:
            place_id, place = place_match
            x0 = origin_x + cell[0] * place_config.cell_size_m
            z0 = origin_z + cell[1] * place_config.cell_size_m
            margin = place_config.located_at_boundary_margin_m
            if (
                x0 + margin <= x <= x0 + place_config.cell_size_m - margin
                and z0 + margin <= z <= z0 + place_config.cell_size_m - margin
            ):
                support = hashlib.sha256(canonical_json([
                    entity.mask_sha256, place.mask_sha256, "located_at",
                ]).encode("utf-8")).hexdigest()
                reliability = min(entity.reliability, place.reliability)
                rows.append(("located_at", entity_id, place_id, reliability, support))
                rows.append(("contains", place_id, entity_id, reliability, support))

        entity_mask = entity.mask_array()
        entity_bottom = entity.centroid_m[1] - entity.extent_m[1] / 2.0
        for surface_id, surface in surfaces:
            if surface.plane_normal is None or surface.plane_offset_m is None:
                continue
            normal = np.asarray(surface.plane_normal, dtype=np.float64)
            if _normal_angle_degrees(
                normal, np.asarray([0.0, 1.0, 0.0]),
            ) > supported_by_maximum_normal_angle_degrees:
                continue
            if abs(float(normal[1])) <= 1e-9:
                continue
            plane_y = (
                surface.plane_offset_m
                - float(normal[0]) * entity.centroid_m[0]
                - float(normal[2]) * entity.centroid_m[2]
            ) / float(normal[1])
            gap = entity_bottom - plane_y
            if not supported_by_minimum_gap_m <= gap <= supported_by_maximum_gap_m:
                continue
            if _aabb_overlap_ratio_xz(entity, surface) < (
                supported_by_minimum_projected_overlap
            ):
                continue
            mask_overlap = int(np.logical_and(entity_mask, surface.mask_array()).sum())
            if mask_overlap / max(1, int(entity_mask.sum())) > (
                supported_by_maximum_mask_overlap_fraction
            ):
                continue
            support = hashlib.sha256(canonical_json([
                entity.mask_sha256, surface.mask_sha256, "supported_by",
            ]).encode("utf-8")).hexdigest()
            rows.append((
                "supported_by", entity_id, surface_id,
                min(entity.reliability, surface.reliability), support,
            ))

    for left_index, (left_id, left) in enumerate(places):
        if left.place_cell_xz is None:
            continue
        for right_id, right in places[left_index + 1:]:
            if right.place_cell_xz is None:
                continue
            delta = (
                abs(left.place_cell_xz[0] - right.place_cell_xz[0]),
                abs(left.place_cell_xz[1] - right.place_cell_xz[1]),
            )
            if delta not in {(1, 0), (0, 1)}:
                continue
            source_id, target_id = sorted((left_id, right_id))
            source = indexed_regions[source_id][1]
            target = indexed_regions[target_id][1]
            support = hashlib.sha256(canonical_json([
                source.mask_sha256, target.mask_sha256, "adjacent_to",
            ]).encode("utf-8")).hexdigest()
            rows.append((
                "adjacent_to", source_id, target_id,
                min(source.reliability, target.reliability), support,
            ))

    ordered = sorted(rows, key=lambda item: (item[0], item[1], item[2], item[4]))
    return [
        {
            "relation_id": f"relation:{index:04d}",
            "source_region_id": source_id,
            "target_region_id": target_id,
            "relation": relation,
            "reliability": float(reliability),
            "support_sha256": support,
        }
        for index, (relation, source_id, target_id, reliability, support)
        in enumerate(ordered)
    ]
