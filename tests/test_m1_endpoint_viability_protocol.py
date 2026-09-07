"""Lock the accepted D-044--D-046 train-only endpoint probe contract."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from cpmt.m1_protocol import (
    load_and_validate, load_and_validate_endpoint_probe, protocol_sha256,
)


class TestM1EndpointViabilityProtocol(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hard = load_and_validate(
            PROJECT / "configs" / "m1_hard_condition.json"
        )
        cls.path = PROJECT / "configs" / "m1_endpoint_viability_probe.json"
        cls.probe = load_and_validate_endpoint_probe(cls.path, cls.hard)

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
        self.assertEqual(
            self.probe["construct_alignment"][
                "registered_long_horizon_co_primary"
            ],
            "open_fact_error_auc_per_100_decisions",
        )
        self.assertTrue(
            power[
                "take_maximum_across_primary_contrasts_and_selected_semantic_plus_open_memory_support_plus_open_fact_error_AUC_endpoints"
            ]
        )
        self.assertEqual(
            power["open_fact_error_auc_null_boundary_minimum_effect"], 40.0,
        )
        self.assertEqual(
            power["open_fact_error_auc_planning_true_effect"], 80.0,
        )
        self.assertIn(
            "not_a_unit_conversion", power["open_fact_error_auc_effect_model"]
        )
        self.assertEqual(
            power[
                "open_fact_error_auc_minimum_error_fact_decision_exposures_reduced_per_group"
            ],
            8.0,
        )
        self.assertTrue(power["probe_observed_scale_or_SD_may_not_change_40_or_80"])

    def test_c_weight_moves_to_sequential_train_inner_dev_selection(self):
        amendment = self.probe[
            "post_probe_train_inner_dev_budget_amendment"
        ]
        self.assertEqual(
            amendment["direct_future_auxiliary_weights"], [0.1, 1.0, 10.0]
        )
        self.assertEqual(
            amendment["learning_rate_and_updates_search_cells_per_method"], 12
        )
        self.assertEqual(
            amendment["additional_c_auxiliary_weight_paths_per_seed"], 2
        )
        self.assertFalse(
            amendment["joint_learning_rate_updates_auxiliary_weight_search"]
        )
        self.assertFalse(amendment["validation_arrays_read"])
        budget_runner = (
            PROJECT / "scripts" / "run_m1_train_inner_dev_budget.py"
        ).read_text(encoding="utf-8")
        self.assertIn("load_and_validate_endpoint_probe", budget_runner)
        self.assertIn("C_AUXILIARY_SELECTED", budget_runner)
        self.assertIn("reuse_anchor_weight_run_without_retraining", str(amendment))
        confirmation = self.probe["validation_confirmation"]
        self.assertEqual(confirmation["selection"], "none")
        self.assertTrue(confirmation["use_all_registered_groups_once"])
        self.assertTrue(confirmation["historical_calibration_report_partition_ignored"])

    def test_gate_is_fixed_and_does_not_select_on_one_step_proxy(self):
        gate = self.probe["commit_rule"]
        self.assertEqual(gate["mode"], "fixed_always_attempt_shared_gate")
        self.assertEqual(gate["commit_probability"], 0.0)
        self.assertEqual(gate["margin_threshold"], 0.0)
        self.assertEqual(gate["selection"], "none")
        self.assertEqual(gate["validation_rows_used_for_gate_selection"], 0)
        self.assertEqual(gate["commit_attempt_rate_under_fixed_gate"], 1.0)
        self.assertIn("COMMIT_request", gate["actual_commit_rate_definition"])
        self.assertIn("executor_illegal", gate["executor_quarantine_rate_definition"])
        self.assertIn("one_step_vs_20_step", gate["reason"])
        self.assertEqual(
            gate["executor_illegal_action"],
            "deterministic_QUARANTINE_without_persistent_write",
        )
        output = self.probe["output"]
        self.assertTrue(output["save_fixed_commit_rule"])
        self.assertNotIn("save_cross_fitted_gate_by_fold", output)

        runner = (PROJECT / "scripts" / "run_m1_af_scaled.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("calibrate_shared_commit_rule(", runner)
        self.assertIn('"validation_rows_used_for_gate_selection": 0', runner)
        self.assertNotIn("cfg.update(commit_", runner)
        self.assertNotIn('"commit_calibration":', runner)
        self.assertIn('"validation_selection": "none"', runner)
        self.assertIn('"commit_attempt_rate": col("commit_attempt_rate")', runner)
        self.assertIn(
            'report_mask = np.ones(len(validation_np["y"]), dtype=bool)',
            runner,
        )
        self.assertNotIn("paired_group_is_calibration", runner)

    def test_aliases_are_excluded_and_empty_recovery_is_null(self):
        naming = self.probe["naming_and_scope"]
        excluded = set(naming["formal_primary_table_excludes"])
        self.assertIn("final_post_graph_correctness", excluded)
        self.assertIn("unresolved_active_error", excluded)
        self.assertIn("memory_contamination_per_100", excluded)
        self.assertIn("excess_nodes", excluded)
        self.assertEqual(
            naming["compatibility_aliases"]["post_graph_correct"],
            "history_exact",
        )
        reporting = self.probe["always_on_reporting_and_safety"]
        self.assertIsNone(reporting["empty_conditional_denominator_value"])
        self.assertIn(
            "without_net_cardinality_cancellation",
            reporting["false_birth_growth_definition"],
        )

    def test_m1_does_not_claim_the_original_dynamic_memory_construct(self):
        alignment = self.probe["construct_alignment"]
        self.assertIn(
            "not_claimed_in_M1", alignment["dynamic_contamination_rate_mapping"]
        )
        scope = self.probe["naming_and_scope"]
        self.assertEqual(
            scope["m1_scope"],
            "controlled_embodied_persistent_world_revision_only",
        )
        self.assertIn("decay", scope["deferred_to_M2_M3"])
        self.assertEqual(
            scope["minimal_world_change_interpretation"],
            "registered_prior_or_regularizer_only_not_a_validated_primary_mechanism",
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
