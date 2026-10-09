from __future__ import annotations

import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from vsmt.l1_entities import DINORegionConfig  # noqa: E402
from vsmt.l1_structures import (  # noqa: E402
    FreeSpaceMaterializationConfig,
    L1StructureConstructionError,
    PlaceMaterializationConfig,
    SurfaceMaterializationConfig,
    assemble_free_space_history,
    materialize_public_free_space,
    materialize_public_visibility,
    materialize_public_places,
    materialize_public_surfaces,
)


def descriptor_config() -> DINORegionConfig:
    return DINORegionConfig(
        image_height=224,
        image_width=224,
        patch_size_pixels=14,
        patch_token_dimension=4,
        minimum_total_patch_weight=1.0,
        unit_norm_validation_tolerance=0.00001,
    )


def surface_config() -> SurfaceMaterializationConfig:
    return SurfaceMaterializationConfig(
        tile_size_pixels=14,
        minimum_valid_depth_fraction_per_tile=0.9,
        initial_maximum_rms_point_to_plane_m=0.015,
        initial_maximum_p95_point_to_plane_m=0.03,
        merge_maximum_normal_angle_degrees=10.0,
        merge_maximum_mutual_centroid_to_plane_m=0.03,
        final_inlier_point_to_plane_m=0.02,
        final_minimum_inlier_fraction=0.9,
        final_maximum_rms_point_to_plane_m=0.01,
        minimum_inlier_pixels=784,
        minimum_depth_m=0.05,
        maximum_depth_m=20.0,
    )


def place_config() -> PlaceMaterializationConfig:
    return PlaceMaterializationConfig(
        maximum_floor_normal_angle_degrees=10.0,
        maximum_support_height_difference_m=0.05,
        cell_size_m=0.5,
        grid_origin_m=(0.0, 0.0, 0.0),
        coverage_subcell_size_m=0.1,
        minimum_covered_subcells=16,
        minimum_mask_pixels=196,
        camera_to_agent_center_y_m=0.675,
        agent_half_height_m=0.9,
        located_at_boundary_margin_m=0.02,
    )


def free_config() -> FreeSpaceMaterializationConfig:
    return FreeSpaceMaterializationConfig(
        tile_size_pixels=14,
        block_widths_in_tiles=(1, 2, 4, 8, 16),
        angular_boundary_erosion_pixels=1,
        minimum_depth_m=0.05,
        maximum_valid_depth_m=20.0,
        near_axis_depth_m=0.1,
        surface_clearance_m=0.1,
        maximum_axis_depth_m=5.0,
        minimum_longitudinal_thickness_m=0.1,
        rolling_public_observation_times=4,
    )


def calibration() -> dict[str, float]:
    return {"fx": 112.0, "fy": 112.0, "cx": 111.5, "cy": 111.5}


def patch_tokens() -> np.ndarray:
    values = np.zeros((16, 16, 4), dtype=np.float32)
    values[..., 0] = 1.0
    return values


class PublicStructureMaterializerTests(unittest.TestCase):
    def test_floor_depth_yields_surface_and_observed_place_cells(self) -> None:
        depth = np.full((224, 224), 1.575, dtype=np.float32)
        half = math.sqrt(0.5)
        pose = {
            "position_m": [0.0, 1.575, 0.0],
            "quaternion_xyzw": [half, 0.0, 0.0, half],
        }
        surfaces = materialize_public_surfaces(
            depth, calibration(), pose, patch_tokens(), descriptor_config(),
            surface_config(),
        )
        self.assertEqual(len(surfaces), 1)
        self.assertEqual(surfaces[0].structure_kind, "surface")
        self.assertGreaterEqual(surfaces[0].mask_pixel_count, 784)
        self.assertAlmostEqual(abs(surfaces[0].plane_normal[1]), 1.0, places=6)
        place_result = materialize_public_places(
            surfaces, depth, calibration(), pose, patch_tokens(),
            descriptor_config(), surface_config(), place_config(),
        )
        places = place_result.regions
        self.assertTrue(places)
        self.assertTrue(all(item.structure_kind == "place" for item in places))
        self.assertTrue(all(item.extent_m == (0.5, 0.0, 0.5) for item in places))
        self.assertTrue(all(item.reliability >= 16 / 25 for item in places))
        self.assertIsInstance(place_result.rejected, tuple)

    def test_curved_depth_does_not_pass_planar_surface_contract(self) -> None:
        rows, columns = np.indices((224, 224))
        depth = np.where((rows + columns) % 2 == 0, 1.0, 2.0).astype(np.float32)
        surfaces = materialize_public_surfaces(
            depth, calibration(), {
                "position_m": [0.0, 0.0, 0.0],
                "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
            }, patch_tokens(), descriptor_config(), surface_config(),
        )
        self.assertEqual(surfaces, ())

    def test_degenerate_place_cell_is_recorded_without_aborting_frame(self) -> None:
        depth = np.full((224, 224), 1.575, dtype=np.float32)
        half = math.sqrt(0.5)
        pose = {
            "position_m": [0.0, 1.575, 0.0],
            "quaternion_xyzw": [half, 0.0, 0.0, half],
        }
        surfaces = materialize_public_surfaces(
            depth, calibration(), pose, patch_tokens(), descriptor_config(),
            surface_config(),
        )
        with patch(
            "vsmt.l1_structures._canonical_plane",
            side_effect=L1StructureConstructionError("degenerate_plane_points"),
        ):
            result = materialize_public_places(
                surfaces, depth, calibration(), pose, patch_tokens(),
                descriptor_config(), surface_config(), place_config(),
            )
        self.assertEqual(result.regions, ())
        self.assertTrue(result.rejected)
        self.assertIn(
            "degenerate_plane_points", {item.reason for item in result.rejected},
        )

    def test_multiscale_free_space_has_341_frusta_and_rolling_history(self) -> None:
        depth = np.full((224, 224), 2.0, dtype=np.float32)
        pose = {
            "position_m": [0.0, 0.0, 0.0],
            "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
        }
        first = materialize_public_free_space(
            depth, calibration(), pose, time_s=0.0,
            depth_sha256="1" * 64,
            camera_calibration_and_pose_sha256="2" * 64,
            config=free_config(),
        )
        second = materialize_public_free_space(
            depth, calibration(), pose, time_s=0.3,
            depth_sha256="3" * 64,
            camera_calibration_and_pose_sha256="2" * 64,
            config=free_config(),
        )
        self.assertEqual(len(first), 341)
        history = assemble_free_space_history(
            [first, second], rolling_public_observation_times=4,
        )
        self.assertEqual(len(history), 682)
        self.assertEqual(history[0]["free_space_id"], "free:0000")
        self.assertEqual(history[-1]["free_space_id"], "free:0681")
        visibility = materialize_public_visibility(
            second, surface_clearance_m=free_config().surface_clearance_m,
        )
        self.assertEqual(len(visibility), 341)
        self.assertEqual(visibility[0]["visibility_id"], "visibility:0000")
        self.assertGreater(
            visibility[0]["halfspaces_world"][-1]["offset_m"],
            second[0].public_record("free:0000")["halfspaces_world"][-1]["offset_m"],
        )

    def test_invalid_depth_pixel_rejects_every_block_containing_it(self) -> None:
        depth = np.full((224, 224), 2.0, dtype=np.float32)
        depth[3, 3] = np.nan
        result = materialize_public_free_space(
            depth, calibration(), {
                "position_m": [0.0, 0.0, 0.0],
                "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
            }, time_s=0.0, depth_sha256="1" * 64,
            camera_calibration_and_pose_sha256="2" * 64,
            config=free_config(),
        )
        self.assertEqual(len(result), 336)
