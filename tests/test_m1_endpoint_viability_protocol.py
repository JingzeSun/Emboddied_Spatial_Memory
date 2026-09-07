"""Lock the accepted D-044 train-only endpoint probe contract."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from cpmt.m1_protocol import load_and_validate, protocol_sha256


class TestM1EndpointViabilityProtocol(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hard = load_and_validate(
            PROJECT / "configs" / "m1_hard_condition.json"
        )
        cls.path = PROJECT / "configs" / "m1_endpoint_viability_probe.json"
        cls.probe = json.loads(cls.path.read_text(encoding="utf-8"))

    def test_source_protocol_and_arrays_are_frozen(self):
        source = self.probe["source_protocol"]
        self.assertEqual(source["protocol_sha256"], protocol_sha256(self.hard))
        self.assertEqual(source["dataset_version"], self.hard["data"]["dataset_version"])
        self.assertEqual(source["train_paired_groups"], 1000)
        self.assertEqual(source["fitting_paired_groups"], 799)
        self.assertEqual(source["inner_dev_paired_groups"], 201)
        self.assertEqual(
            source["train_arrays_digest"],
            "e8a890f1b254a7109af641fea57fcbea5efd931b4272d8e96cb870f51604b168",
        )

    def test_probe_cannot_search_or_read_validation_test(self):
        anchor = self.probe["training_anchor"]
        self.assertEqual(anchor["architecture"], "cross_candidate_set_transformer_v1")
        self.assertEqual(anchor["methods"], ["A", "C", "E"])
        self.assertEqual(anchor["oracle"], "F")
        self.assertEqual(anchor["seeds"], [7, 19, 31, 43, 59])
        self.assertEqual(anchor["learning_rate"], 0.0006)
        self.assertEqual(anchor["student_updates"], 3000)
        self.assertFalse(anchor["grid_search"])
        self.assertFalse(anchor["checkpoint_selection"])
        access = self.probe["access_boundary"]
        self.assertFalse(access["validation_arrays_read"])
        self.assertFalse(access["test_generated"])
        self.assertFalse(access["test_access"])

    def test_switch_and_power_rules_are_fully_determined(self):
        switch = self.probe["nondegeneracy_and_one_time_switch"]
        self.assertEqual(switch["minimum_nonzero_groups_at_n_201"], 7)
        self.assertTrue(switch["sample_standard_deviation_must_be_positive"])
        self.assertTrue(
            switch["winner_identity_effect_direction_and_effect_size_forbidden_for_switch"]
        )
        power = self.probe["power_planning"]
        self.assertEqual(power["null_boundary_minimum_effect"], 0.03)
        self.assertEqual(power["planning_true_effect"], 0.06)
        self.assertEqual(power["one_sided_alpha_per_primary_contrast"], 0.025)
        self.assertEqual(power["target_power"], 0.8)
        self.assertIsNone(power["registered_test_size_cap"])
        self.assertTrue(
            self.probe["endpoints"]["open_memory_support"][
                "required_co_primary_for_both_A_vs_C_and_A_vs_E"
            ]
        )

    def test_graded_equivalence_node_safety_and_collateral_union_are_locked(self):
        graded = self.probe["endpoints"]["graded"]
        self.assertTrue(graded["duplicate_records_preserved"])
        self.assertEqual(
            graded["exact_equivalence"],
            "graded_equals_1_if_and_only_if_exact_equals_1",
        )
        safety = self.probe["always_on_reporting_and_safety"]
        self.assertEqual(
            safety["node_state_symmetric_difference_noninferiority_margin_per_100"],
            1.0,
        )
        self.assertEqual(
            safety["collateral_joint_definition"],
            "per_step_union_of_protected_state_change_and_committed_evidence_scope_external_mutation",
        )
        self.assertTrue(safety["collateral_components_reported_separately"])
        coverage = self.probe["mechanism_metric_coverage"]
        self.assertTrue(coverage["report_by_family"])
        self.assertTrue(
            coverage[
                "c10_designated_opposite_BIND_NOOP_requires_open_memory_and_evidence_detection_every_row"
            ]
        )
        self.assertTrue(
            coverage[
                "c11_designated_bind_with_collateral_requires_unrelated_collateral_detection_every_row"
            ]
        )
        self.assertIn("expected_single_step_accuracy_near_0.5", coverage[
            "c10_online_interpretation"
        ])
        self.assertIn("no_instance_level_future_prediction", coverage[
            "c10_online_interpretation"
        ])
        self.assertFalse(coverage["c10_dedicated_recovery_currently_registered"])
        self.assertEqual(len(hashlib.sha256(self.path.read_bytes()).hexdigest()), 64)


if __name__ == "__main__":
    unittest.main()
