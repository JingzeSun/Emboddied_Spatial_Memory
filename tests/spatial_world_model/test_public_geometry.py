"""Server-only analytic depth fixtures; these are not rendered physical data."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from spatial_world_model.public_geometry import (
    _boundary_interval, _fuse_candidates, _height_clusters, recover_openings,
)


def parameters():
    value = json.loads((Path(__file__).resolve().parents[2] / "configs" / "spatial_history" /
                        "public_geometry_proposal_v1.json").read_text(encoding="utf-8"))
    return deepcopy(value["public_sensor_spec"]), deepcopy(value["extractor"])


def observation(*, width=16, height=12, time=0.0):
    return {"time_s": time, "width": width, "height": height,
            "rgb": [0] * (width * height * 3), "depth_m": [2.0] * (width * height),
            "camera_position_m": [0.0, 0.0, 2.0], "camera_xyzw": [1.0, 0.0, 0.0, 0.0],
            "intrinsics": [100.0, 100.0, (width - 1) / 2, (height - 1) / 2],
            "ee_position_m": [0.0, 0.0, 0.0], "ee_velocity_mps": [0.0, 0.0, 0.0],
            "previous_velocity_mps": [0.0, 0.0, 0.0]}


def rectangle(value, columns, rows, depth=1.0):
    for v in range(rows[0], rows[1] + 1):
        for u in range(columns[0], columns[1] + 1):
            value["depth_m"][v * value["width"] + u] = depth


def opening():
    value = observation()
    rectangle(value, (1, 5), (3, 6))
    rectangle(value, (10, 14), (3, 6))
    return value


def candidate(lower, upper):
    intervals = [[lower, upper], [5.0, 6.0], [10.0, 11.0]]
    return {"coordinate_intervals_m": intervals,
            "coordinates_m": [(a + b) / 2 for a, b in intervals],
            "plane_height_interval_m": [1.0, 1.0], "support": []}


class PublicGeometryTests(unittest.TestCase):
    def setUp(self):
        self.sensor, self.extractor = parameters()

    def recover(self, history):
        return recover_openings(history, self.sensor, self.extractor)

    def test_analytic_opening_contains_three_boundaries_and_plane(self):
        result = self.recover([opening()])
        self.assertEqual(result["schema_version"], "public-openings-v1")
        self.assertEqual(result["history_frames"], 1)
        self.assertEqual(len(result["candidates"]), 1)
        self.assertFalse(result["conflicts"])
        item = result["candidates"][0]
        # Rectangles end/begin between columns 5/6 and 9/10; their front is row 6/7.
        for truth, interval in zip((-.02, .02, -.01), item["coordinate_intervals_m"]):
            self.assertLessEqual(interval[0], truth)
            self.assertGreaterEqual(interval[1], truth)
            self.assertLess(interval[1] - interval[0], .025)
        self.assertLessEqual(item["plane_height_interval_m"][0], 1.0)
        self.assertGreaterEqual(item["plane_height_interval_m"][1], 1.0)
        self.assertEqual({support["boundary_kind"] for support in item["support"]},
                         {"x_left", "x_right", "y_front"})
        for support in item["support"]:
            self.assertEqual(support["local_frame_index"], 0)
            (u, v), (other_u, other_v) = support["pixel_pair"]
            self.assertEqual(abs(u - other_u) + abs(v - other_v), 1)

    def test_pixel_centers_and_full_footprints_match_analytic_example(self):
        value = observation(width=64, height=64)
        interval = _boundary_interval(value, self.sensor["camera_to_world_rotation"],
                                      [(32, 31), (33, 31)], [1.0, 1.0], 0, self.extractor)
        self.assertAlmostEqual(interval[0], -.000001)
        self.assertAlmostEqual(interval[1], .020001)

    def test_depth_is_axis_distance_not_normalized_ray_length(self):
        value = observation(width=32)
        value["intrinsics"] = [10.0, 10.0, 0.0, 0.0]
        interval = _boundary_interval(value, self.sensor["camera_to_world_rotation"],
                                      [(20, 1), (21, 1)], [1.0, 1.0], 0, self.extractor)
        self.assertAlmostEqual(interval[0], 1.949999)
        self.assertAlmostEqual(interval[1], 2.150001)

    def test_background_rays_intersect_top_plane_not_background_xy(self):
        before = self.recover([opening()])["candidates"]
        value = opening()
        value["depth_m"] = [8.0 if depth == 2.0 else depth for depth in value["depth_m"]]
        after = self.recover([value])["candidates"]
        self.assertEqual(before, after)

    def test_signed_quaternions_and_world_translation(self):
        value = opening()
        initial = self.recover([value])["candidates"][0]
        value["camera_xyzw"] = [-1.0, 0.0, 0.0, 0.0]
        self.assertEqual(initial, self.recover([value])["candidates"][0])
        value["camera_position_m"] = [.75, -.4, 5.0]
        shifted = self.recover([value])["candidates"][0]
        for axis, shift in enumerate((.75, .75, -.4)):
            for before, after in zip(initial["coordinate_intervals_m"][axis],
                                     shifted["coordinate_intervals_m"][axis]):
                self.assertAlmostEqual(before + shift, after)
        for before, after in zip(initial["plane_height_interval_m"], shifted["plane_height_interval_m"]):
            self.assertAlmostEqual(before + 3.0, after)

    def test_height_clusters_bound_total_span_not_neighbor_links(self):
        clusters = _height_clusters([(0.00030, 2), (0.0, 0), (0.00015, 1)], .0002)
        self.assertEqual(clusters, [[(0.0, 0), (.00015, 1)], [(.00030, 2)]])

    def test_no_surfaces_do_not_invent_openings(self):
        self.assertEqual(self.recover([observation()])["candidates"], [])
        value = observation()
        value["depth_m"] = [0.0] * len(value["depth_m"])
        result = self.recover([value])
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["rejected_counts"]["zero_depth_pixels"], 192)

    def test_candidate_count_is_not_forced_to_two(self):
        value = observation(width=24)
        for columns in ((1, 3), (7, 9), (13, 15), (19, 21)):
            rectangle(value, columns, (3, 6))
        self.assertEqual(len(self.recover([value])["candidates"]), 3)

    def test_every_gap_pixel_must_be_valid_including_nonadjacent_pixels(self):
        for depth in (0.0, .04, .0401, 19.9999, 20.0, 25.0):
            value = opening()
            rectangle(value, (7, 7), (3, 6), depth)
            with self.subTest(depth=depth):
                result = self.recover([value])
                self.assertEqual(result["candidates"], [])
                self.assertGreater(result["rejected_counts"]["invalid_gap_pairs"], 0)
                self.assertIn("gap_invalid_depth", [item["reason"] for item in result["incomplete_observations"]])

    def test_nearer_occluder_and_insufficient_farther_margin_are_not_gaps(self):
        for depth in (.5, 1.00025):
            value = opening()
            rectangle(value, (7, 7), (3, 6), depth)
            with self.subTest(depth=depth):
                result = self.recover([value])
                self.assertEqual(result["candidates"], [])
                self.assertGreater(result["rejected_counts"]["nonfarther_gap_pairs"], 0)

    def test_side_runs_and_consecutive_rows_require_two_dimensions(self):
        value = observation()
        rectangle(value, (1, 1), (3, 6))
        rectangle(value, (10, 14), (3, 6))
        self.assertEqual(self.recover([value])["candidates"], [])
        value = observation()
        rectangle(value, (1, 5), (3, 3))
        rectangle(value, (10, 14), (3, 3))
        result = self.recover([value])
        self.assertEqual(result["candidates"], [])
        self.assertGreater(result["rejected_counts"]["insufficient_row_groups"], 0)

    def test_exactly_two_visible_rows_are_sufficient_for_thin_top_surface(self):
        value = observation()
        rectangle(value, (1, 5), (0, 1))
        rectangle(value, (10, 14), (0, 1))
        result = self.recover([value])
        self.assertEqual(len(result["candidates"]), 1)
        # The rear is cropped above row zero; the observed front at v=1.5 is enough.
        front = result["candidates"][0]["coordinate_intervals_m"][2]
        self.assertLessEqual(front[0], .04)
        self.assertGreaterEqual(front[1], .04)

    def test_incomplete_cropped_frame_does_not_abort_later_complete_observation(self):
        cropped = observation()
        cropped["camera_position_m"][1] = .07  # The same wall shifts down by seven pixels.
        rectangle(cropped, (1, 5), (10, 11))
        rectangle(cropped, (10, 14), (10, 11))
        complete = opening()
        complete["time_s"] = 1.0
        result = self.recover([cropped, complete])
        self.assertEqual(len(result["candidates"]), 1)
        self.assertIn({"local_frame_index": 0, "row_span": [10, 11],
                       "plane_height_interval_m": [.9999, 1.0001], "reason": "missing_front_witnesses"},
                      result["incomplete_observations"])
        self.assertEqual({item["local_frame_index"] for item in result["candidates"][0]["support"]}, {1})

    def test_offset_runs_without_two_by_two_patch_are_incomplete(self):
        value = observation()
        for columns, rows in (((1, 2), (3, 3)), ((7, 8), (3, 3)),
                              ((2, 3), (4, 4)), ((8, 9), (4, 4))):
            rectangle(value, columns, rows)
        result = self.recover([value])
        self.assertEqual(result["candidates"], [])
        self.assertGreater(result["rejected_counts"]["insufficient_side_patch_groups"], 0)

    def test_image_boundary_is_not_a_front_witness(self):
        value = observation()
        rectangle(value, (1, 5), (3, 11))
        rectangle(value, (10, 14), (3, 11))
        result = self.recover([value])
        self.assertEqual(result["candidates"], [])
        self.assertGreater(result["rejected_counts"]["missing_front_groups"], 0)

    def test_zero_and_nearer_front_pixels_never_close_boundary(self):
        for depth in (0.0, .5):
            value = opening()
            rectangle(value, (1, 5), (7, 7), depth)
            rectangle(value, (10, 14), (7, 7), depth)
            with self.subTest(depth=depth):
                self.assertEqual(self.recover([value])["candidates"], [])

    def test_two_front_columns_are_required_on_each_side(self):
        value = opening()
        rectangle(value, (2, 5), (7, 7), 0.0)
        rectangle(value, (11, 14), (7, 7), 0.0)
        result = self.recover([value])
        self.assertEqual(result["candidates"], [])
        self.assertGreater(result["rejected_counts"]["missing_front_groups"], 0)

    def test_front_intervals_on_both_sides_must_share_intersection(self):
        value = observation()
        rectangle(value, (1, 5), (3, 5))
        rectangle(value, (10, 14), (3, 8))
        result = self.recover([value])
        self.assertEqual(result["candidates"], [])
        self.assertIn("incompatible_front_intervals", [item["reason"] for item in result["incomplete_observations"]])

    def test_full_history_fuses_without_discarding_support_or_adding_precision(self):
        first, second = opening(), opening()
        second["time_s"] = 1.0
        before = self.recover([first])["candidates"][0]
        result = self.recover([first, second])
        self.assertEqual(len(result["candidates"]), 1)
        after = result["candidates"][0]
        self.assertEqual(before["coordinate_intervals_m"], after["coordinate_intervals_m"])
        self.assertEqual(len(after["support"]), 2 * len(before["support"]))
        self.assertEqual({item["local_frame_index"] for item in after["support"]}, {0, 1})

    def test_overlap_chain_conflict_is_preserved_instead_of_averaged(self):
        members = [candidate(0, 1), candidate(.75, 1.75), candidate(1.5, 2.5)]
        fused, conflicts = _fuse_candidates(members)
        self.assertEqual(fused, [])
        self.assertEqual(conflicts, [{"reason": "empty_common_intersection", "members": members}])
        conflicts[0]["members"][0]["coordinates_m"][0] = 99
        self.assertEqual(members[0]["coordinates_m"][0], .5)

    def test_fusion_takes_common_interval_and_retains_disjoint_candidates(self):
        fused, conflicts = _fuse_candidates([candidate(0, 2), candidate(1, 3), candidate(5, 6)])
        self.assertFalse(conflicts)
        self.assertEqual([item["coordinate_intervals_m"][0] for item in fused], [[1, 2], [5, 6]])

    def test_rgb_and_nonvisual_robot_values_do_not_change_geometry(self):
        value = opening()
        before = self.recover([value])
        value["rgb"] = [index % 256 for index in range(len(value["rgb"]))]
        value["ee_position_m"] = [3.0, 4.0, 5.0]
        value["ee_velocity_mps"] = [.1, -.2, .3]
        value["previous_velocity_mps"] = [.2, .3, -.4]
        self.assertEqual(before, self.recover([value]))

    def test_outputs_do_not_alias_inputs_or_persist_between_queries(self):
        value = opening()
        original = deepcopy(value)
        result = self.recover([value])
        result["candidates"][0]["support"][0]["pixel_pair"][0][0] = 99
        self.assertEqual(value, original)
        self.assertNotEqual(result, self.recover([value]))
        self.assertEqual(self.recover([observation()])["candidates"], [])

    def test_extractor_has_no_filesystem_access(self):
        value = opening()
        with patch("builtins.open", side_effect=AssertionError("unexpected file access")), \
                patch.object(Path, "open", side_effect=AssertionError("unexpected Path access")):
            self.assertEqual(len(self.recover([value])["candidates"]), 1)

    def test_private_parameters_and_entire_proposal_are_rejected(self):
        for field in ("gate_count", "world", "gate_height", "layout", "history_indices", "path", "goal"):
            for location in ("sensor", "extractor"):
                sensor, extractor = deepcopy(self.sensor), deepcopy(self.extractor)
                (sensor if location == "sensor" else extractor)[field] = 2
                with self.subTest(field=field, location=location), self.assertRaises(ValueError):
                    recover_openings([opening()], sensor, extractor)
        with self.assertRaises(ValueError):
            recover_openings([opening()], self.sensor, {"extractor": self.extractor, "evaluation_only": {}})

    def test_false_declarations_and_weakened_support_are_rejected(self):
        for field, value in (("rgb_used", True), ("rgb_used", 0), ("controls_or_goal_used", True),
                             ("minimum_each_side_run_pixels", 1), ("minimum_consecutive_support_rows", True),
                             ("pixel_footprint_half_width", .1), ("plane_tolerance_m", float("nan"))):
            extractor = deepcopy(self.extractor)
            extractor[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                recover_openings([opening()], self.sensor, extractor)

    def test_invalid_pose_time_and_complete_frame_fields_are_rejected(self):
        for field, value in (("camera_xyzw", [0.0, 0.0, 0.0, 1.0]),
                             ("camera_xyzw", [2.0, 0.0, 0.0, 0.0]),
                             ("intrinsics", [0.0, 100.0, 7.5, 5.5]),
                             ("time_s", -1.0), ("rgb", [0])):
            item = opening()
            item[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.recover([item])
        item = opening()
        item["private_mask"] = []
        with self.assertRaises(ValueError):
            self.recover([item])
        for history in ([], [opening(), opening()], [observation(time=1.0), observation(time=0.0)]):
            with self.subTest(history_length=len(history)), self.assertRaises(ValueError):
                self.recover(history)

    def test_nonfinite_depths_and_unsupported_sensor_are_rejected(self):
        for depth in (float("nan"), float("inf"), -.1, True):
            value = opening()
            value["depth_m"][0] = depth
            with self.subTest(depth=depth), self.assertRaises(ValueError):
                self.recover([value])
        sensor = deepcopy(self.sensor)
        sensor["camera_to_world_rotation"] = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        with self.assertRaises(ValueError):
            recover_openings([opening()], sensor, self.extractor)


if __name__ == "__main__":
    unittest.main()
