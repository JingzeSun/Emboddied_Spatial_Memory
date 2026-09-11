"""Synthetic contract tests, to run on the server; not physics evidence."""
from copy import deepcopy
import json
import math
from pathlib import Path
import unittest

from spatial_world_model.two_gate_contract import (
    NAMES, assess_trajectory, audit_family, expand_controls, make_public, model_input,
    validate_config,
)


ROOT = Path(__file__).resolve().parents[2]


def configuration():
    return json.loads((ROOT / "configs/spatial_history/two_gate_engineering_proposal_v1.json").read_text(encoding="utf-8"))


def history(world="LL"):
    result = []
    for index in range(121):
        bit = 0 if index >= 119 else int(world[0 if index < 61 else 1] == "R")
        result.append({"time_s": 0.5 + index * 0.1, "width": 1, "height": 1,
                       "rgb": [bit, 0, 0], "depth_m": [1.0],
                       "camera_position_m": [0, 0, 1.4], "camera_xyzw": [1, 0, 0, 0],
                       "intrinsics": [1, 1, 0.5, 0.5], "ee_position_m": [0, -0.25, 0.05],
                       "ee_velocity_mps": [0, 0, 0], "previous_velocity_mps": [0, 0, 0]})
    return result


def trajectory(waypoints=None, final_x=-0.12):
    """Hand-authored smooth positions for scorer tests, never a simulator."""
    if waypoints is None:
        waypoints = [(0, -0.12, 0), (10, -0.12, 2.65), (18, final_x, 2.65), (20, final_x, 2.65)]
    result, segment = [], 0
    for index in range(10001):
        time = index * 0.002
        while segment + 2 < len(waypoints) and time > waypoints[segment + 1][0]:
            segment += 1
        start, end = waypoints[segment:segment + 2]
        fraction = (time - start[0]) / (end[0] - start[0])
        x = start[1] + fraction * (end[1] - start[1])
        y = start[2] + fraction * (end[2] - start[2])
        velocity = [(end[1] - start[1]) / (end[0] - start[0]),
                    (end[2] - start[2]) / (end[0] - start[0]), 0]
        result.append({"step_index": index, "time_s": time,
                       "object_position_m": [x, y, 0.04], "object_axis_world": [0, 0, 1],
                       "object_linear_velocity_mps": velocity,
                       "pusher_position_m": [x, y - 0.095, 0.05],
                       "actuator_force_n": [0, 0], "contacts": [], "object_visible_pixels": 0})
    return result


class TwoGateContractTests(unittest.TestCase):
    def test_registered_expansion_and_common_clock(self):
        config = configuration()
        validate_config(config)
        controls = expand_controls(config)
        self.assertEqual(list(controls), list(NAMES))
        self.assertTrue(all(len(v) == 200 for v in controls.values()))
        self.assertTrue(all(abs(sum(c["duration_s"] for c in v) - 20) < 1e-9 for v in controls.values()))
        self.assertEqual(controls["LR"][-52:], [{"duration_s": .1, "ee_velocity_mps": [0, 0, 0]}] * 52)

    def test_boolean_control_number_rejected(self):
        config = configuration()
        config["controls"]["phase_duration_s"][0] = True
        with self.assertRaises(ValueError):
            expand_controls(config)

    def test_public_allowlist_and_deep_copy(self):
        original = history()
        public = make_public(original, configuration())
        query = model_input(public, "LR", [25, 65, 119, 120])
        self.assertEqual(set(query), {"history", "controls", "goal"})
        self.assertEqual(len(query["history"]), 4)
        query["history"][0]["rgb"][0] = 200
        query["controls"][0]["ee_velocity_mps"][0] = 999
        self.assertEqual(original[25]["rgb"][0], 0)
        self.assertEqual(public["actions"]["LR"][0]["ee_velocity_mps"][0], 0)

    def test_private_fields_and_future_rejected_before_slicing(self):
        public = make_public(history(), configuration())
        for extra in ("world_id", "initial_state", "future", "layout_truth"):
            contaminated = deepcopy(public)
            contaminated[extra] = {}
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                model_input(contaminated, "LL", [119, 120])
        contaminated = deepcopy(public)
        contaminated["history"][0]["future_object_position_m"] = [0, 0, 0]
        with self.assertRaises(ValueError):
            model_input(contaminated, "LL", [119, 120])
        contaminated = deepcopy(public)
        contaminated["history"][-1]["time_s"] = 12.6
        with self.assertRaises(ValueError):
            model_input(contaminated, "LL", [25])

    def test_goal_layout_leak_and_boolean_sensor_rejected(self):
        public = make_public(history(), configuration())
        contaminated = deepcopy(public)
        contaminated["goal"]["gate_centers"] = [-.12, -.12]
        with self.assertRaises(ValueError):
            model_input(contaminated, "LL")
        contaminated = deepcopy(public)
        contaminated["history"][0]["depth_m"][0] = True
        with self.assertRaises(ValueError):
            model_input(contaminated, "LL")
        for indices in ([True], [65, 25], [25, 25], [121], []):
            with self.subTest(indices=indices), self.assertRaises(ValueError):
                model_input(public, "LL", indices)

    def test_crossed_partitions_accept_nondiagonal_successes(self):
        config = configuration()
        public = {w: make_public(history(w), config) for w in NAMES}
        outcomes = {w: {a: ((w in ("LL", "RR")) == (a in ("LL", "LR"))) for a in NAMES}
                    for w in NAMES}
        result = audit_family(public, outcomes, config)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["minimum_information_regret"], .5)
        self.assertEqual(len(result["frame_information"][0]["equivalence_groups"]), 2)
        self.assertEqual(len(result["frame_information"][120]["equivalence_groups"]), 1)
        self.assertFalse(result["physics_and_geometry_recovery_verified"])

    def test_common_successful_action_has_zero_information_value(self):
        config = configuration()
        public = {w: make_public(history(w), config) for w in NAMES}
        outcomes = {w: {a: a == "LL" for a in NAMES} for w in NAMES}
        result = audit_family(public, outcomes, config)
        self.assertFalse(result["accepted"])
        self.assertTrue(result["checks"]["each_world_has_success"])
        self.assertEqual(result["minimum_information_regret"], 0)

    def test_metadata_shortcut_and_invalid_physics_outcome_rejected(self):
        config = configuration()
        public = {w: make_public(history(w), config) for w in NAMES}
        outcomes = {w: {a: a == w for a in NAMES} for w in NAMES}
        public["LR"]["history"][0]["camera_position_m"][0] = .01
        result = audit_family(public, outcomes, config)
        self.assertFalse(result["checks"]["same_history_metadata"])
        self.assertFalse(result["accepted"])
        outcomes["LL"]["LL"] = None
        with self.assertRaises(ValueError):
            audit_family(public, outcomes, config)

    def test_ordered_passage_settlement_and_missing_visibility(self):
        samples = trajectory()
        result = assess_trajectory(samples, configuration(), world_name="LL")
        self.assertTrue(result["raw_task_success"])
        self.assertTrue(result["physics_valid"])
        self.assertTrue(result["visibility_valid"])
        completed = [e for e in result["gate_events"] if e["status"] == "completed"]
        self.assertEqual([e["gate_index"] for e in completed], [0, 1])
        self.assertLess(completed[0]["completion_time_s"], completed[1]["cross_time_s"])
        for index in result["critical_visibility_indices"]:
            samples[index]["object_visible_pixels"] = None
        missing = assess_trajectory(samples, configuration(), world_name="LL")
        self.assertFalse(missing["visibility_valid"])
        self.assertTrue(missing["raw_task_success"])
        self.assertTrue(set(missing["critical_visibility_indices"]) <= set(missing["required_visibility_indices"]))

    def test_retreat_cancels_attempt_and_later_invalid_crossing_cannot_complete_it(self):
        samples = trajectory([(0, -.12, 0), (2, -.12, .63), (3, -.12, .59),
                              (4, .4, .59), (5, .4, .8), (6, -.12, .9),
                              (10, -.12, 2.65), (20, -.12, 2.65)])
        result = assess_trajectory(samples, configuration(), world_name="LL")
        near = [e for e in result["gate_events"] if e["gate_index"] == 0]
        self.assertEqual([e["status"] for e in near], ["cancelled", "invalid"])
        self.assertIsNone(near[0]["completion_index"])
        self.assertFalse(result["raw_task_success"])

    def test_center_plane_equality_does_not_create_duplicate_attempts(self):
        samples = trajectory([(0, -.12, 0), (2, -.12, .6), (3, -.12, .6),
                              (10, -.12, 2.65), (20, -.12, 2.65)])
        result = assess_trajectory(samples, configuration(), world_name="LL")
        self.assertEqual(sum(e["gate_index"] == 0 for e in result["gate_events"]), 1)
        self.assertTrue(result["raw_task_success"])

    def test_settlement_checks_every_step_not_only_terminal(self):
        samples = trajectory()
        samples[9700]["object_linear_velocity_mps"] = [.021, 0, 0]
        result = assess_trajectory(samples, configuration(), world_name="LL")
        self.assertEqual(result["terminal"]["object_linear_speed_mps"], 0)
        self.assertFalse(result["settled_speed"])
        self.assertFalse(result["raw_task_success"])

    def test_goal_tolerance_and_actual_tilted_projection(self):
        inside = assess_trajectory(trajectory(final_x=.1805), configuration(), world_name="LL")
        outside = assess_trajectory(trajectory(final_x=.182), configuration(), world_name="LL")
        self.assertTrue(inside["raw_task_success"])
        self.assertFalse(outside["raw_task_success"])
        samples = trajectory(final_x=.179)
        for sample in samples[9500:]:
            sample["object_axis_world"] = [math.sin(.2), 0, math.cos(.2)]
        tilted = assess_trajectory(samples, configuration(), world_name="LL")
        self.assertTrue(tilted["physics_valid"])
        self.assertFalse(tilted["settled_containment"])

    def test_unfiltered_contact_penetration_and_translation_are_engineering_failures(self):
        samples = trajectory()
        samples[500]["contacts"] = [{"geoms": ["object", "floor"], "distance_m": -.0051, "normal_force_n": 0}]
        samples[501]["pusher_position_m"][0] += .006
        result = assess_trajectory(samples, configuration(), world_name="LL")
        self.assertTrue(result["raw_task_success"])
        self.assertFalse(result["physics_valid"])
        self.assertIsNone(result["task_success"])
        self.assertIn("penetration", result["physics_failures"])
        self.assertIn("step_translation", result["physics_failures"])

    def test_collision_is_not_task_failure_and_visibility_is_real_count(self):
        samples = trajectory()
        samples[1400]["contacts"] = [{"geoms": ["object", "gate_0_left"], "distance_m": -.0001, "normal_force_n": .1}]
        samples[1400]["object_visible_pixels"] = 1
        result = assess_trajectory(samples, configuration(), world_name="LL")
        self.assertTrue(result["raw_task_success"])
        self.assertTrue(result["physics_valid"])
        self.assertFalse(result["visibility_valid"])
        self.assertEqual(result["positive_gate_contact_steps"], [1400])
        self.assertIn(1400, result["visible_critical_indices"])


if __name__ == "__main__":
    unittest.main()
