"""The ruling-73 depth probe's model-free parts: the per-point depth test inverts the frozen back-projection
pixel for pixel, sorts points into seen-through / on-surface / occluded / unobserved, and the AUC read from
two histograms matches the pairwise definition."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT / "src", PROJECT_ROOT / "ops" / "vsmt"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import lean_s2_05_depth_probe as probe  # noqa: E402
from vsmt.l1_entities import _camera_values  # noqa: E402

CALIBRATION = {"fx": 112.0, "fy": 112.0, "cx": 112.0, "cy": 112.0}
IDENTITY = {"position_m": [0.0, 0.0, 0.0], "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0]}
YAWED = {"position_m": [1.0, 1.5, -2.0], "quaternion_xyzw": [0.0, float(np.sin(np.pi / 8)), 0.0, float(np.cos(np.pi / 8))]}


def backproject(row: int, column: int, z: float, pose) -> np.ndarray:
    """The frozen convention (l1_entities.backproject_public_entity_geometry) for one pixel."""

    fx, fy, cx, cy, position, rotation = _camera_values(CALIBRATION, pose)
    camera = np.array([(column - cx) * z / fx, (cy - row) * z / fy, z])
    return rotation @ camera + position


class PointDepthTests(unittest.TestCase):
    def test_a_back_projected_point_lands_on_its_own_pixel_and_reads_as_surface(self) -> None:
        depth = np.full((224, 224), 3.0)
        for pose in (IDENTITY, YAWED):
            for row, column in ((10, 20), (112, 112), (200, 5)):
                point = backproject(row, column, 3.0, pose)
                counts = probe.point_depth_counts(point[None, None, :], depth, CALIBRATION, pose, margin_m=0.05)
                self.assertEqual((int(counts["surface"][0]), int(counts["through"][0]), int(counts["occluded"][0])), (1, 0, 0), (pose, row, column))

    def test_through_surface_occluded_and_unobserved(self) -> None:
        depth = np.full((224, 224), 3.0)
        depth[0, 0] = np.nan
        points = np.stack([backproject(50, 60, z, IDENTITY) for z in (2.0, 2.97, 3.5)]
                          + [backproject(0, 0, 2.0, IDENTITY), np.array([0.0, 0.0, -1.0]), np.array([100.0, 0.0, 1.0])])[None]
        counts = probe.point_depth_counts(points, depth, CALIBRATION, IDENTITY, margin_m=0.05)
        # 2.0 m point in front of a 3.0 m surface: seen through; 2.97 m: on the surface; 3.5 m: behind it
        self.assertEqual(int(counts["through"][0]), 1)
        self.assertEqual(int(counts["surface"][0]), 1)
        self.assertEqual(int(counts["occluded"][0]), 1)
        # invalid depth, behind the camera, outside the image
        self.assertEqual(int(counts["unobserved"][0]), 3)
        self.assertEqual(int(counts["points"][0]), 6)

    def test_the_margin_moves_points_between_surface_and_the_other_two(self) -> None:
        depth = np.full((224, 224), 3.0)
        points = np.stack([backproject(80, 90, z, IDENTITY) for z in (2.85, 3.15)])[None]
        tight = probe.point_depth_counts(points, depth, CALIBRATION, IDENTITY, margin_m=0.05)
        loose = probe.point_depth_counts(points, depth, CALIBRATION, IDENTITY, margin_m=0.20)
        self.assertEqual((int(tight["through"][0]), int(tight["occluded"][0]), int(tight["surface"][0])), (1, 1, 0))
        self.assertEqual(int(loose["surface"][0]), 2)


class AucTests(unittest.TestCase):
    def test_histogram_auc_matches_the_pairwise_definition(self) -> None:
        rng = np.random.default_rng(73)
        high, low = rng.beta(4, 2, 400), rng.beta(2, 4, 500)
        edges = np.linspace(0, 1, probe.BINS + 1)
        h_high, _ = np.histogram(high, bins=edges)
        h_low, _ = np.histogram(low, bins=edges)
        high_bin, low_bin = np.digitize(high, edges[1:-1]), np.digitize(low, edges[1:-1])
        pairwise = ((high_bin[:, None] > low_bin[None, :]) + 0.5 * (high_bin[:, None] == low_bin[None, :])).mean()
        self.assertAlmostEqual(probe.auc_from_histograms(h_high, h_low), float(pairwise), places=12)
        self.assertEqual(probe.auc_from_histograms(h_low, h_low), 0.5)
        self.assertIsNone(probe.auc_from_histograms([0] * probe.BINS, h_low))

    def test_structural_present_rows_are_kept_apart(self) -> None:
        self.assertEqual(probe.group_of({"status": "present", "reason": "structural_never_intervened"}), "present_structural")
        self.assertEqual(probe.group_of({"status": "present", "reason": None}), "present")
        self.assertEqual(probe.group_of({"status": "gone"}), "gone")


if __name__ == "__main__":
    unittest.main()
