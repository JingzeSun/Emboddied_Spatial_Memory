"""Necessary server-only R4 input/probability boundary checks."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from r4_examples import public, prediction
from spatial_world_model.r4_query import (domain_spec, from_public_query, mean_predictions,
                                        validate_prediction, validate_query)


class R4QueryTests(unittest.TestCase):
    def test_full_recent_and_prefix_clocks_preserve_raw_depth(self):
        for mode, indices, cut in (("full", range(121), None), ("recent", [119, 120], None),
                                   ("prefix", range(26), 25)):
            src = public(indices)
            q = from_public_query(src, history_mode=mode, history_cut_index=cut)
            self.assertEqual(set(q), {"history", "controls", "goal", "domain_spec"})
            self.assertEqual(q["history"]["time_s"], [(i - 120) / 10 for i in indices])
            self.assertEqual(q["history"]["depth_m"], [f["depth_m"] for f in src["history"]])
            self.assertFalse(q["history"]["depth_valid"][0][-1])
            self.assertEqual(len(q["controls"]["ee_velocity_mps"]), 200)

    def test_queries_and_domain_do_not_alias_sources_or_each_other(self):
        src = public()
        a = from_public_query(src, history_mode="recent")
        b = from_public_query(src, history_mode="recent")
        a["history"]["rgb"][0][0] = 255
        a["domain_spec"]["gravity_mps2"][2] = -1
        self.assertEqual(b["history"]["rgb"][0][0], 0)
        self.assertEqual(src["history"][0]["rgb"][0], 0)
        self.assertEqual(domain_spec()["gravity_mps2"][2], -9.81)

    def test_private_fields_at_every_boundary_rejected(self):
        for location in ("top", "frame", "control", "goal"):
            src = public()
            target = {"top": src, "frame": src["history"][0],
                      "control": src["controls"][0], "goal": src["goal"]}[location]
            target["actual_future_object_motion"] = [1, 2, 3]
            with self.subTest(location=location), self.assertRaises(ValueError):
                from_public_query(src, history_mode="recent")
        q = from_public_query(public(), history_mode="recent")
        q["domain_spec"]["gate_truth"] = [0, 0]
        with self.assertRaises(ValueError):
            validate_query(q, history_mode="recent")

    def test_wrong_mode_cut_and_unselected_source_frames_rejected(self):
        for mode, cut in (("other", None), ("recent", 1), ("prefix", True), ("prefix", 121)):
            with self.subTest(mode=mode, cut=cut), self.assertRaises(ValueError):
                from_public_query(public(), history_mode=mode, history_cut_index=cut)
        with self.assertRaises(ValueError):
            from_public_query(public(range(121)), history_mode="recent")

    def test_clock_and_resolution_corruption_rejected(self):
        for key, value in (("time_s", 12.4), ("time_s", float("nan")), ("width", 32)):
            src = public()
            src["history"][1][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                from_public_query(src, history_mode="recent")
        q = from_public_query(public(), history_mode="recent")
        q["history"]["time_s"][1] = 0.1
        with self.assertRaises(ValueError):
            validate_query(q, history_mode="recent")

    def test_depth_invalid_mask_and_nonfinite_not_silently_repaired(self):
        q = from_public_query(public(), history_mode="recent")
        q["history"]["depth_valid"][0][-1] = True
        with self.assertRaises(ValueError):
            validate_query(q, history_mode="recent")
        for value in (-1, float("inf"), True):
            src = public()
            src["history"][0]["depth_m"][0] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                from_public_query(src, history_mode="recent")

    def test_control_units_steps_and_domain_constants_are_fixed(self):
        for change in ("count", "duration", "z", "limit", "boolean"):
            src = public()
            if change == "count": src["controls"].pop()
            if change == "duration": src["controls"][0]["duration_s"] = 1.0
            if change == "z": src["controls"][0]["ee_velocity_mps"][2] = 0.1
            if change == "limit": src["controls"][0]["ee_velocity_mps"][0] = 0.51
            if change == "boolean": src["controls"][0]["ee_velocity_mps"][0] = True
            with self.subTest(change=change), self.assertRaises(ValueError):
                from_public_query(src, history_mode="recent")
        q = from_public_query(public(), history_mode="recent")
        q["domain_spec"]["force_limit_per_axis_n"] = 200
        with self.assertRaises(ValueError): validate_query(q, history_mode="recent")

    def test_goal_translation_allowed_but_task_redefinition_rejected(self):
        src = public()
        src["goal"]["goal_center_xy_m"][0] = 0.1
        src["goal"]["goal_x_bounds_m"] = [-0.15, 0.35]
        from_public_query(src, history_mode="recent")
        src["goal"]["settled_interval_s"] = [19.9, 20]
        with self.assertRaises(ValueError): from_public_query(src, history_mode="recent")

    def test_common_constants_match_d071_registration(self):
        root = Path(__file__).resolve().parents[2]
        cfg = json.loads((root / "configs/spatial_history/two_gate_engineering_v1.json").read_text())
        d = domain_spec()
        for key in ("object_radius_m", "object_half_height_m", "object_mass_kg", "pusher_half_size_m",
                    "pusher_mass_kg", "friction", "velocity_servo_kv", "control_limit_per_axis_mps", "force_limit_per_axis_n"):
            self.assertEqual(d[key], cfg["geometry"][key])
        self.assertEqual(d["obstacle_thickness_m"], cfg["geometry"]["wall_thickness_m"])

    def test_adapter_and_validator_have_no_file_access(self):
        src = public()
        with patch("builtins.open", side_effect=AssertionError("unexpected read")), \
             patch.object(Path, "open", side_effect=AssertionError("unexpected read")):
            q = from_public_query(src, history_mode="recent")
            validate_query(q, history_mode="recent")

    def test_prediction_rejects_missing_nonfinite_bool_and_future_grid_errors(self):
        for change in ("count", "time", "extra", "prob", "bool", "nan"):
            p = prediction()
            if change == "count": p["object_position_m"].pop()
            if change == "time": p["prediction_times_s"][0] = 0
            if change == "extra": p["layout"] = "LL"
            if change == "prob": p["task_success_probability"] = 1.01
            if change == "bool": p["task_success_probability"] = True
            if change == "nan": p["object_position_m"][10][0] = float("nan")
            with self.subTest(change=change), self.assertRaises(ValueError): validate_prediction(p)

    def test_stochastic_mean_averages_probabilities_and_keeps_all_samples(self):
        samples = [prediction(success=0.25 if i < 8 else 0.75, position=(i, 0, 0)) for i in range(16)]
        before = deepcopy(samples)
        value = mean_predictions(samples)
        self.assertEqual(value["task_success_probability"], 0.5)
        self.assertEqual(value["object_position_m"][0], [7.5, 0, 0])
        self.assertEqual(samples, before)
        with self.assertRaises(ValueError): mean_predictions(samples[:15])
        samples[9] = None
        with self.assertRaises(ValueError): mean_predictions(samples)
