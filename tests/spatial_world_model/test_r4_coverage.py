"""Server-only analytic/synthetic coverage tests; no rendered data or models."""
from copy import deepcopy
import math
import unittest
from unittest.mock import patch

from spatial_world_model import r4_coverage as c


def history(indices):
    focal = 40 / math.tan(math.radians(21))
    return {"schema_version": c.HISTORY_VERSION, "frames": [
        {"time_s": (i - 120) / 10, "width": 80, "height": 80,
         "depth_m": [0.0] * 6400, "camera_position_m": [0.0, -0.2, 1.4],
         "camera_xyzw": [1, 0, 0, 0], "intrinsics": [focal, focal, 39.5, 39.5]}
        for i in indices]}


def select(value, mode="recent", cut=None):
    return c.select_history(value, c.sensor_spec(), c.parameters(),
                            history_mode=mode, history_cut_index=cut)


class R4CoverageTests(unittest.TestCase):
    def test_axis_depth_integer_centres_and_world_floor(self):
        h = history([119, 120])
        for row in h["frames"]:
            row["depth_m"][40 * 80 + 40] = 1.4
            row["depth_m"][39 * 80 + 39] = 1.4
        result = select(h)["frame_surfaces"]["frames"][0]
        self.assertEqual(result["voxel_keys"], [[-1, -10, 0], [0, -11, 0]])
        self.assertEqual(result["source_pixels"], [[[39, 39]], [[40, 40]]])
        self.assertEqual(result["valid_pixels"], 2)
        # Camera-axis depth keeps the world z at zero, even off optical axis.
        h["frames"][0]["depth_m"][0] = 1.4
        projected = select(h)["frame_surfaces"]["frames"][0]
        self.assertTrue(all(k[2] == 0 for k in projected["voxel_keys"]))

    def test_equal_rotations_have_identical_coverage(self):
        h = history([119, 120])
        h["frames"][0]["depth_m"][112] = 1.2
        original = select(h)
        for row in h["frames"]:
            row["camera_xyzw"] = [-q for q in row["camera_xyzw"]]
        self.assertEqual(select(h), original)

    def test_all_duplicate_pixel_sources_retained_but_counted_once(self):
        h = history([119, 120])
        h["frames"][0]["depth_m"][40 * 80 + 40] = 0.1
        h["frames"][0]["depth_m"][40 * 80 + 41] = 0.1
        frame = select(h)["frame_surfaces"]["frames"][0]
        self.assertEqual(len(frame["voxel_keys"]), 1)
        self.assertEqual(frame["source_pixels"], [[[40, 40], [40, 41]]])
        self.assertEqual(frame["valid_pixels"], 2)

    def test_strict_clip_boundaries_and_zero_are_distinct(self):
        h = history([119, 120])
        s = c.sensor_spec()
        low, high = s["near_depth_m"] + s["clip_margin_m"], s["far_depth_m"] - s["clip_margin_m"]
        h["frames"][0]["depth_m"][:8] = [0, low, high, 0.01, 25,
                                          math.nextafter(low, math.inf), math.nextafter(high, 0), 1.0]
        frame = select(h)["frame_surfaces"]["frames"][0]
        self.assertEqual((frame["valid_pixels"], frame["clipped_depth_pixels"],
                          frame["zero_depth_pixels"]), (3, 4, 6393))

    def test_nonfinite_negative_boolean_depth_rejected_before_selection(self):
        for value in [float("nan"), float("inf"), -1, True, "1", 10**1000]:
            h = history([119, 120])
            h["frames"][0]["depth_m"][0] = value
            with self.subTest(value=str(value)[:20]), self.assertRaises(ValueError):
                select(h)

    def test_non_native_calibration_and_pose_are_rejected(self):
        changes = [("width", 64), ("height", True), ("intrinsics", [100, 100, 39.5, 39.5]),
                   ("camera_xyzw", [0, 0, 0, 1]), ("camera_position_m", [0, -0.2, 2]),
                   ("camera_position_m", [0.13, -0.2, 1.4]), ("camera_position_m", [0, 0, 1.4])]
        for field, value in changes:
            h = history([119, 120])
            h["frames"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError): select(h)

    def test_camera_translation_must_be_shared(self):
        h = history([119, 120])
        h["frames"][0]["camera_position_m"][0] = 0.01
        with self.assertRaises(ValueError): select(h)

    def test_finite_but_overflowing_projection_is_rejected(self):
        h = history(range(3))
        h["frames"][1]["camera_position_m"][1] = 1e308
        h["frames"][1]["depth_m"][0] = 1.0
        with self.assertRaises(ValueError): select(h, "prefix", 2)

    def test_foreign_fields_are_rejected_at_every_public_boundary(self):
        for name in ["rgb", "controls", "goal", "world_id", "actual_future_robot_motion", "private_masks"]:
            for location in ["history", "frame", "sensor", "parameters"]:
                h, s, p = history([119, 120]), c.sensor_spec(), c.parameters()
                target = {"history": h, "frame": h["frames"][0], "sensor": s, "parameters": p}[location]
                target[name] = []
                with self.subTest(name=name, location=location), self.assertRaises(ValueError):
                    c.select_history(h, s, p, history_mode="recent")

    def test_frozen_parameters_and_sensor_cannot_be_tuned(self):
        for field, value in [("voxel_m", 0.01), ("recent_keep", True), ("recent_keep", 2.0),
                             ("additional_frames", 8.0), ("additional_frames", 9),
                             ("origin_m", [0.01, 0, 0])]:
            p = c.parameters()
            p[field] = value
            with self.assertRaises(ValueError): c.select_history(history([119, 120]), c.sensor_spec(), p, history_mode="recent")
        for field in ["near_depth_m", "far_depth_m", "clip_margin_m"]:
            s = c.sensor_spec()
            s[field] *= 2
            with self.assertRaises(ValueError): c.select_history(history([119, 120]), s, c.parameters(), history_mode="recent")

    def test_history_mode_count_clock_and_version_enforced(self):
        h = history([119, 120])
        for mode, cut in [("full", None), ("prefix", True), ("prefix", 121), ("recent", 120), ("unknown", None)]:
            with self.subTest(mode=mode, cut=cut), self.assertRaises(ValueError): select(h, mode, cut)
        for value in [0.1, -0.2, float("nan")]:
            broken = deepcopy(h)
            broken["frames"][-1]["time_s"] = value
            with self.assertRaises(ValueError): select(broken)
        h["schema_version"] = "spatial-history-r4-query-v2"
        with self.assertRaises(ValueError): select(h)

    def test_zero_coverage_still_selects_earliest_eight_plus_recent(self):
        result = select(history(range(121)), "full")
        self.assertEqual(result["selected_local_indices"], list(range(8)) + [119, 120])
        self.assertEqual(result["selected_union_voxels"], 0)
        self.assertEqual([t["local_index"] for t in result["selection_trace"]], [119, 120] + list(range(8)))
        self.assertTrue(all(t["new_voxels"] == 0 for t in result["selection_trace"]))

    def test_greedy_recomputes_marginal_gain_and_breaks_ties_by_time(self):
        # D-085 hand example: seeds {a,b}, then {d,e}, then earliest {a,c}.
        coverages = [{"a", "c"}, {"d", "e"}, {"c", "d"}, {"a"}, {"b"}]
        selected, trace, size = c._select(coverages, [-4, -3, -2, -1, 0], 2, 2)
        self.assertEqual([t["local_index"] for t in trace], [3, 4, 1, 0])
        self.assertEqual([t["new_voxels"] for t in trace], [1, 1, 2, 1])
        self.assertEqual(selected, [0, 1, 3, 4])
        self.assertEqual(size, 5)

    def test_public_projection_drives_greedy_choice(self):
        h = history(range(12))
        h["frames"][7]["depth_m"][40 * 80 + 40] = 1.4
        result = select(h, "prefix", 11)
        self.assertEqual(result["selection_trace"][2], {"local_index": 7, "role": "greedy", "new_voxels": 1})
        self.assertEqual(result["selected_local_indices"], list(range(8)) + [10, 11])

    def test_recent_uses_local_indices_and_preserves_original_time(self):
        result = select(history([119, 120]))
        self.assertEqual(result["selected_local_indices"], [0, 1])
        self.assertEqual(result["selected_time_s"], [-0.1, 0.0])

    def test_short_prefixes_keep_all_without_future_access(self):
        for count in [1, 2, 9, 10]:
            result = select(history(range(count)), "prefix", count - 1)
            self.assertEqual(result["selected_local_indices"], list(range(count)))
            self.assertEqual(result["selected_time_s"][-1], (count - 121) / 10)
        # Full histories cannot be smuggled into a prefix and then silently cut.
        with self.assertRaises(ValueError): select(history(range(121)), "prefix", 8)

    def test_no_mutation_or_aliasing_and_repeatable_outputs(self):
        h = history([119, 120])
        h["frames"][0]["depth_m"][40 * 80 + 40] = 1.4
        before = deepcopy(h)
        a, b = select(h), select(h)
        self.assertEqual(a, b)
        a["frame_surfaces"]["frames"][0]["source_pixels"][0][0][0] = -1
        self.assertEqual(select(h), b)
        self.assertEqual(h, before)

    def test_value_functions_do_not_open_files(self):
        h = history([119, 120])
        with patch("builtins.open", side_effect=AssertionError("file read forbidden")):
            self.assertEqual(select(h)["selected_local_indices"], [0, 1])

    def test_every_source_pixel_is_accounted_once(self):
        h = history([119, 120])
        for index in [0, 1, 79, 80, 200, 6399]: h["frames"][0]["depth_m"][index] = 1.2
        row = select(h)["frame_surfaces"]["frames"][0]
        pixels = [v * 80 + u for sources in row["source_pixels"] for v, u in sources]
        self.assertEqual(sorted(pixels), [0, 1, 79, 80, 200, 6399])
        self.assertEqual(len(pixels), row["valid_pixels"])
