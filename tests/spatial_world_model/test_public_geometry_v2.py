"""Independent analytic fixtures for E0-v2; no rendered family or private truth."""

from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from spatial_world_model.public_geometry_v2 import recover_openings


ROOT = Path(__file__).resolve().parents[2]


def parameters():
    value = json.loads((ROOT / "configs/spatial_history/public_geometry_boundary_v2.json")
                       .read_text(encoding="utf-8"))
    return deepcopy(value["public_sensor_spec"]), deepcopy(value["extractor"])


def observation(*, width=16, height=12, time=0.0):
    return {
        "time_s": time, "width": width, "height": height,
        "rgb": [0] * (width * height * 3),
        "depth_m": [2.0] * (width * height),
        "camera_position_m": [0.0, 0.0, 2.0],
        "camera_xyzw": [1.0, 0.0, 0.0, 0.0],
        "intrinsics": [100.0, 100.0, (width - 1) / 2, (height - 1) / 2],
        "ee_position_m": [0.0, 0.0, 0.0],
        "ee_velocity_mps": [0.0, 0.0, 0.0],
        "previous_velocity_mps": [0.0, 0.0, 0.0],
    }


def rectangle(value, columns, rows, depth=1.0):
    for v in range(rows[0], rows[1] + 1):
        for u in range(columns[0], columns[1] + 1):
            value["depth_m"][v * value["width"] + u] = depth


def opening():
    value = observation()
    rectangle(value, (1, 5), (3, 6))
    rectangle(value, (10, 14), (3, 6))
    return value


def support_for(result, kind):
    return [item for item in result["candidates"][0]["support"]
            if item["boundary_kind"] == kind]


class PublicGeometryV2Tests(unittest.TestCase):
    def setUp(self):
        self.sensor, self.extractor = parameters()

    def recover(self, history):
        return recover_openings(history, self.sensor, self.extractor)

    def test_strict_opening_remains_adjacent_and_uses_unchanged_margin(self):
        result = self.recover([opening()])
        self.assertEqual(result["schema_version"], "public-openings-v2")
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["evidence_counts"]["boundary_compatible_gap_pixels"], 0)
        self.assertTrue(all(item["transition_kind"] == "adjacent_strict_farther"
                            for item in result["candidates"][0]["support"]))

    def test_right_boundary_band_widens_wall_interval_not_free_evidence(self):
        value = opening()
        rectangle(value, (9, 9), (3, 6), 1.00025)
        result = self.recover([value])
        self.assertEqual(len(result["candidates"]), 1)
        right = support_for(result, "x_right")
        self.assertTrue(right)
        self.assertTrue(all(item["transition_kind"] == "boundary_compatible_band"
                            and item["boundary_compatible_pixels"] for item in right))
        self.assertEqual(result["evidence_counts"]["boundary_compatible_gap_pixels"], 4)
        self.assertNotIn("free", result["candidates"][0])

    def test_left_and_right_boundary_bands_are_symmetric(self):
        value = opening()
        rectangle(value, (6, 6), (3, 6), 1.00025)
        rectangle(value, (9, 9), (3, 6), 1.00025)
        result = self.recover([value])
        self.assertEqual(len(result["candidates"]), 1)
        for kind in ("x_left", "x_right"):
            self.assertTrue(all(item["transition_kind"] == "boundary_compatible_band"
                                for item in support_for(result, kind)))

    def test_boundary_compatible_pixel_in_gap_interior_is_unresolved(self):
        value = opening()
        rectangle(value, (8, 8), (3, 6), 1.00025)
        result = self.recover([value])
        self.assertEqual(result["candidates"], [])
        self.assertGreater(result["rejected_counts"]["nonboundary_gap_pairs"], 0)
        self.assertIn("gap_contains_nonboundary_or_interior_ambiguity",
                      {item["reason"] for item in result["incomplete_observations"]})

    def test_boundary_band_without_strict_farther_interior_is_unresolved(self):
        value = opening()
        rectangle(value, (6, 9), (3, 6), 1.00025)
        result = self.recover([value])
        self.assertEqual(result["candidates"], [])
        self.assertGreater(result["rejected_counts"]["gap_without_strict_farther_pairs"], 0)
        self.assertIn("gap_without_strict_farther",
                      {item["reason"] for item in result["incomplete_observations"]})

    def test_nearer_occluder_is_not_boundary_compatible(self):
        value = opening()
        rectangle(value, (9, 9), (3, 6), .5)
        result = self.recover([value])
        self.assertEqual(result["candidates"], [])
        self.assertGreater(result["rejected_counts"]["nonboundary_gap_pairs"], 0)

    def test_invalid_depth_is_not_boundary_compatible(self):
        value = opening()
        rectangle(value, (9, 9), (3, 6), 0.0)
        result = self.recover([value])
        self.assertEqual(result["candidates"], [])
        self.assertGreater(result["rejected_counts"]["invalid_gap_pairs"], 0)

    def test_front_boundary_band_requires_later_strict_farther_witness(self):
        value = opening()
        rectangle(value, (1, 5), (7, 7), 1.00025)
        rectangle(value, (10, 14), (7, 7), 1.00025)
        result = self.recover([value])
        self.assertEqual(len(result["candidates"]), 1)
        front = support_for(result, "y_front")
        self.assertTrue(front)
        self.assertTrue(all(item["transition_kind"] == "boundary_compatible_band"
                            for item in front))
        self.assertGreater(result["evidence_counts"]["boundary_compatible_front_pixels"], 0)

        blocked = opening()
        rectangle(blocked, (1, 5), (7, 11), 1.00025)
        rectangle(blocked, (10, 14), (7, 11), 1.00025)
        unresolved = self.recover([blocked])
        self.assertEqual(unresolved["candidates"], [])
        self.assertGreater(unresolved["rejected_counts"]["missing_front_groups"], 0)

    def test_rgb_robot_and_private_files_cannot_change_public_geometry(self):
        value = opening()
        before = self.recover([value])
        value["rgb"] = [index % 256 for index in range(len(value["rgb"]))]
        value["ee_position_m"] = [3.0, 4.0, 5.0]
        value["ee_velocity_mps"] = [.1, -.2, .3]
        value["previous_velocity_mps"] = [.2, .3, -.4]
        with patch("builtins.open", side_effect=AssertionError("unexpected file access")), \
                patch.object(Path, "open", side_effect=AssertionError("unexpected Path access")):
            self.assertEqual(before, self.recover([value]))

    def test_threshold_or_declaration_change_is_rejected(self):
        for field, changed in (
                ("minimum_farther_depth_separation_m", .0001),
                ("boundary_compatible_pixels_certify_free", True),
                ("private_labels_or_layout_used", True)):
            extractor = deepcopy(self.extractor)
            extractor[field] = changed
            with self.subTest(field=field), self.assertRaises(ValueError):
                recover_openings([opening()], self.sensor, extractor)


if __name__ == "__main__":
    unittest.main()
