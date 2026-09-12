"""Necessary R4 scoring checks using only hand-authored values."""
from copy import deepcopy
import unittest

from r4_examples import prediction, registry_rows, trace, truth
from spatial_world_model.r4_scoring import (labels_from_trajectory, paired_effects,
                                            score_prediction, score_world,
                                            select_candidates, summarize_registered,
                                            validate_labels)


class R4ScoringTests(unittest.TestCase):
    def test_trace_projection_uses_every_physics_row_and_fixed_endpoints(self):
        value = labels_from_trajectory(trace(), {"physics_valid": True,
                                                  "visibility_valid": True,
                                                  "task_success": True})
        self.assertEqual(len(value["object_position_m"]), 200)
        self.assertEqual(value["prediction_times_s"], [k / 10 for k in range(1, 201)])
        self.assertEqual(value["object_position_m"][0], [0.005, 0, 0.04])
        self.assertEqual(value["object_position_m"][-1], [1.0, 0, 0.04])
        self.assertEqual(value["object_visible_pixels"], [0] * 200)

    def test_trace_contact_uses_the_registered_half_open_interval(self):
        rows = trace()
        rows[50]["contacts"] = [{"geoms": ["gate_near", "object"],
                                  "distance_m": -0.001, "normal_force_n": 1.0}]
        rows[100]["contacts"] = [{"geoms": ["object", "side_right"],
                                   "distance_m": 0.0, "normal_force_n": 0.1}]
        value = labels_from_trajectory(rows, {"physics_valid": True,
                                              "visibility_valid": True, "task_success": False})
        self.assertEqual([i for i, flag in enumerate(value["interval_contact"]) if flag], [0, 1])

    def test_trace_and_assessment_reject_short_or_privileged_success(self):
        with self.assertRaises(ValueError):
            labels_from_trajectory(trace()[:-1], {"physics_valid": True,
                                                  "visibility_valid": True, "task_success": True})
        with self.assertRaises(ValueError):
            labels_from_trajectory(trace(), {"physics_valid": False,
                                             "visibility_valid": True, "task_success": True})
        invalid = truth(True)
        invalid["physics_valid"] = False
        invalid["task_success"] = None
        validate_labels(invalid)

    def test_position_contact_and_invisible_metrics_are_separate(self):
        actual = truth(True, position=(1, 0, 0))
        actual["interval_contact"][10:12] = [True, True]
        actual["object_visible_pixels"][0] = 90
        actual["object_visible_pixels"][1] = None
        predicted = prediction(success=0.0, position=(0, 0, 0))
        predicted["obstacle_contact_probability"][11] = 1.0
        predicted["obstacle_contact_probability"][30] = 1.0
        score = score_prediction(predicted, actual)
        self.assertEqual(score["position_mean_error_m"], 1.0)
        self.assertEqual(score["position_invisible_mean_error_m"], 1.0)
        self.assertEqual(score["invisible_endpoint_count"], 198)
        self.assertEqual(score["positive_interval_recall"], 0.5)
        self.assertAlmostEqual(score["negative_interval_false_positive_rate"], 1 / 198)
        self.assertEqual(score["first_contact_error_s"], 0.1)
        self.assertEqual(score["contact_events"]["matched_runs"], 1)
        self.assertEqual(score["success_brier"], 1.0)

    def test_candidate_selection_uses_exact_uniform_ties(self):
        predictions = [prediction(success=0.7) for _ in range(4)]
        self.assertEqual(select_candidates(predictions), [0.25] * 4)
        predictions[2]["task_success_probability"] = 0.8
        self.assertEqual(select_candidates(predictions), [0.0, 0.0, 1.0, 0.0])

    def test_world_score_reports_regret_and_missing_prediction_bounds(self):
        labels = [truth(True), truth(False), truth(False), truth(False)]
        predictions = [prediction(0.0), prediction(1.0), prediction(0.0), prediction(0.0)]
        score = score_world(predictions, labels)
        self.assertTrue(score["valid"])
        self.assertEqual(score["expected_actual_cost"], 1.0)
        self.assertEqual(score["selection_regret"], 1.0)
        self.assertEqual(score["expected_actual_cost_bounds"], [1.0, 1.0])
        predictions[1] = None
        missing = score_world(predictions, labels)
        self.assertFalse(missing["valid"])
        self.assertEqual(missing["expected_actual_cost_bounds"], [0, 1])
        self.assertEqual(missing["valid_prediction_candidates"], 3)

    def test_invalid_truth_cannot_be_scored_as_a_negative_outcome(self):
        labels = [truth(True) for _ in range(4)]
        labels[0]["visibility_valid"] = False
        score = score_world([prediction() for _ in range(4)], labels)
        self.assertFalse(score["valid"])
        self.assertIsNone(score["expected_actual_cost"])
        self.assertEqual(score["expected_actual_cost_bounds"], [0.0, 1.0])

    def test_paired_effects_require_identical_registered_controls(self):
        controls = {"ee_velocity_mps": [[0, 0.2, 0] for _ in range(200)],
                    "duration_s": [0.1] * 200}
        a, b = prediction(position=(0, 0, 0)), prediction(position=(1, 0, 0))
        left, right = truth(True, position=(0, 0, 0)), truth(False, position=(2, 0, 0))
        effect = paired_effects(a, left, b, right, left_controls=controls, right_controls=controls)
        self.assertEqual(effect["direction"], "right_minus_left")
        self.assertEqual(effect["pair_position_error_m"], 1.0)
        different = deepcopy(controls)
        different["ee_velocity_mps"][0][0] = 0.1
        with self.assertRaises(ValueError):
            paired_effects(a, left, b, right, left_controls=controls, right_controls=different)

    def test_registered_summary_keeps_family_as_the_only_statistical_unit(self):
        rows, registry = registry_rows()
        result = summarize_registered(rows, registry)
        self.assertEqual(result["bootstrap_unit"], "family_after_seed_and_world_mean")
        self.assertEqual(result["models"]["D"]["registered_families"], 2)
        self.assertEqual(result["models"]["D"]["registered_world_seed_rows"], 24)
        self.assertEqual(result["models"]["D"]["mean_regret"], 1.0)
        self.assertEqual(result["models"]["F"]["mean_regret"], 0.0)
        comparison = result["comparisons"][0]
        self.assertEqual(comparison["mean_regret_difference"], 1.0)
        self.assertEqual(comparison["paired_families"], 2)

    def test_missing_registered_result_remains_incomplete_not_a_smaller_sample(self):
        rows, registry = registry_rows()
        rows.pop()
        result = summarize_registered(rows, registry)
        model = result["models"]["F"]
        self.assertEqual(model["complete_families"], 1)
        self.assertIsNone(model["mean_regret"])
        self.assertEqual(result["comparisons"][0]["reason"], "incomplete_registered_families")

    def test_truth_change_across_seed_or_model_is_rejected(self):
        rows, registry = registry_rows()
        rows[4]["labels"][0]["task_success"] = False
        with self.assertRaises(ValueError):
            summarize_registered(rows, registry)
