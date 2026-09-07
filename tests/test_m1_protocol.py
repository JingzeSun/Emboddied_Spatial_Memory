"""Pre-test M1 protocol integrity tests; these do not generate or read test data."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from cpmt.m1_protocol import load_and_validate, protocol_sha256, validate_m1_protocol


class TestM1Protocol(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = PROJECT / "configs" / "m1_hard_condition.json"
        cls.config = load_and_validate(cls.path)

    def test_candidate_is_valid_and_fingerprinted(self):
        self.assertEqual(len(protocol_sha256(self.config)), 64)
        self.assertFalse(self.config["test_access"])

    def test_test_access_cannot_be_enabled(self):
        changed = deepcopy(self.config)
        changed["test_access"] = True
        with self.assertRaisesRegex(ValueError, "test access"):
            validate_m1_protocol(changed)

    def test_required_control_cannot_be_removed(self):
        changed = deepcopy(self.config)
        changed["methods"] = changed["methods"][:-1]
        with self.assertRaisesRegex(ValueError, "six A-F"):
            validate_m1_protocol(changed)

    def test_future_cannot_switch_to_planned_actions(self):
        changed = deepcopy(self.config)
        changed["future"]["source"] = "planned_action_sequence"
        with self.assertRaisesRegex(ValueError, "executed trajectory"):
            validate_m1_protocol(changed)

    def test_future_starts_after_current_now_term(self):
        changed = deepcopy(self.config)
        changed["future"]["start_offset_decisions"] = 0
        with self.assertRaisesRegex(ValueError, "avoid duplicating now"):
            validate_m1_protocol(changed)

    def test_paired_group_bootstrap_is_required(self):
        changed = deepcopy(self.config)
        changed["evaluation"]["bootstrap"]["unit"] = "case_id"
        with self.assertRaisesRegex(ValueError, "paired groups"):
            validate_m1_protocol(changed)

    def test_endpoint_bootstrap_does_not_claim_family_strata(self):
        changed = deepcopy(self.config)
        changed["evaluation"]["bootstrap"]["stratify_by"] = "scenario_family"
        with self.assertRaisesRegex(ValueError, "one mixed registered"):
            validate_m1_protocol(changed)

    def test_e_cannot_execute_candidate_branches(self):
        changed = deepcopy(self.config)
        changed["future"]["no_execution_candidate_execution"] = (
            "allowed_during_training"
        )
        with self.assertRaisesRegex(ValueError, "may not execute"):
            validate_m1_protocol(changed)

    def test_static_preflight_is_shared_without_replacing_executor_illegal(self):
        changed = deepcopy(self.config)
        changed["candidates"]["online_admissibility_mask"][
            "shared_methods"
        ] = ["A", "E"]
        with self.assertRaisesRegex(ValueError, "identical for A-E"):
            validate_m1_protocol(changed)
        changed = deepcopy(self.config)
        changed["candidates"]["online_admissibility_mask"][
            "executor_illegal_energy_retained"
        ] = False
        with self.assertRaisesRegex(ValueError, "illegal_energy_retained"):
            validate_m1_protocol(changed)
        changed = deepcopy(self.config)
        changed["candidates"]["online_admissibility_mask"][
            "pass_semantics"
        ] = "preflight_pass_means_legal"
        with self.assertRaisesRegex(ValueError, "cannot claim executor legality"):
            validate_m1_protocol(changed)

    def test_recovery_stays_bounded_and_global_path_stays_in_m2(self):
        changed = deepcopy(self.config)
        changed["recovery"]["global_async_reconciliation"] = "M1"
        with self.assertRaisesRegex(ValueError, "global reconciliation"):
            validate_m1_protocol(changed)
        changed = deepcopy(self.config)
        changed["recovery"]["candidate_generator"] = "learned"
        with self.assertRaisesRegex(ValueError, "learned or expanded"):
            validate_m1_protocol(changed)

    def test_commit_report_partition_cannot_tune(self):
        changed = deepcopy(self.config)
        changed["training"]["commit_calibration"][
            "report_partition_selects_nothing"
        ] = False
        with self.assertRaisesRegex(ValueError, "cannot tune"):
            validate_m1_protocol(changed)

    def test_commit_grid_has_a_reachable_k_way_threshold(self):
        changed = deepcopy(self.config)
        changed["training"]["commit_calibration"][
            "commit_probability_grid"
        ] = [0.45, 0.55]
        with self.assertRaisesRegex(ValueError, "K-way softmax"):
            validate_m1_protocol(changed)

    def test_every_configured_family_is_required_by_continuous_rollout(self):
        changed = deepcopy(self.config)
        changed["data"]["continuous_rollout_required_families"] = (
            changed["data"]["continuous_rollout_required_families"][:-1]
        )
        with self.assertRaisesRegex(ValueError, "every configured family"):
            validate_m1_protocol(changed)

    def test_mixed_group_scale_is_total_not_multiplied_by_family_count(self):
        self.assertEqual(
            self.config["data"]["paired_groups"],
            {"train": 1000, "validation": 200, "test": 200},
        )
        changed = deepcopy(self.config)
        changed["data"]["generation_count_semantics"] = (
            "groups_per_family_not_total_mixed_groups"
        )
        with self.assertRaisesRegex(ValueError, "total mixed"):
            validate_m1_protocol(changed)
        changed = deepcopy(self.config)
        changed["data"]["minimum_test_support_per_family"] = 199
        with self.assertRaisesRegex(ValueError, "must remain 200"):
            validate_m1_protocol(changed)

    def test_c10_c11_behavioral_contract_cannot_be_replaced_by_labels(self):
        changed = deepcopy(self.config)
        changed["data"]["family_mechanism_contract"]["C11"] = "BIND_label_only"
        with self.assertRaisesRegex(ValueError, "behavioral family"):
            validate_m1_protocol(changed)

    def test_configured_families_cannot_be_duplicated_to_fake_twelve(self):
        changed = deepcopy(self.config)
        changed["data"]["scenario_families"][-1] = "C10"
        changed["data"]["continuous_rollout_required_families"][-1] = "C10"
        with self.assertRaisesRegex(ValueError, "canonical order"):
            validate_m1_protocol(changed)

    def test_no_execution_now_target_cannot_use_post_world(self):
        changed = deepcopy(self.config)
        changed["future"]["no_execution_now_target_inputs"] = (
            "immutable_prior_world;_current_online_observation;_candidate_post_world"
        )
        with self.assertRaisesRegex(ValueError, "may not use post-world"):
            validate_m1_protocol(changed)

    def test_no_execution_now_target_policy_is_frozen(self):
        changed = deepcopy(self.config)
        changed["future"]["no_execution_now_target_policy"][
            "argument_cosine_minimum"
        ] = 0.7
        with self.assertRaisesRegex(ValueError, "current-relation policy"):
            validate_m1_protocol(changed)

    def test_live_energy_semantics_cannot_regress_to_constant_proxies(self):
        changed = deepcopy(self.config)
        changed["energy"]["now_semantics"] = "candidate_has_evidence_ref"
        with self.assertRaisesRegex(ValueError, "current projection consistency"):
            validate_m1_protocol(changed)
        changed = deepcopy(self.config)
        changed["energy"]["collateral_semantics"] = "protected_touch_only"
        with self.assertRaisesRegex(ValueError, "unrelated open-memory churn"):
            validate_m1_protocol(changed)
        changed = deepcopy(self.config)
        changed["energy"]["now_target_source"] = "reference_post_world"
        with self.assertRaisesRegex(ValueError, "reference post-world"):
            validate_m1_protocol(changed)

    def test_both_architecture_arms_are_pre_registered(self):
        changed = deepcopy(self.config)
        changed["architecture_evaluation"]["secondary"] = None
        with self.assertRaisesRegex(ValueError, "secondary architecture"):
            validate_m1_protocol(changed)

        changed = deepcopy(self.config)
        changed["architecture_evaluation"]["run_scope"] = (
            "same_v6_arrays_and_full_A_to_F_within_each_architecture"
        )
        with self.assertRaisesRegex(ValueError, "same v8 arrays"):
            validate_m1_protocol(changed)

    def test_v8_budget_grid_is_finite_train_only_and_architecture_specific(self):
        budget = self.config["training"]["pretest_budget_selection"]
        self.assertEqual(
            budget["scorer_update_checkpoints"], [300, 1000, 3000, 10000]
        )
        self.assertEqual(
            budget["student_update_checkpoints"], [300, 1000, 3000, 10000]
        )
        self.assertEqual(budget["learning_rates"], [0.0002, 0.0006, 0.002])
        self.assertEqual(budget["train_paired_groups"], 1000)

        changed = deepcopy(self.config)
        changed["training"]["pretest_budget_selection"][
            "student_update_checkpoints"
        ].append(10000)
        with self.assertRaisesRegex(ValueError, "checkpoint grids"):
            validate_m1_protocol(changed)

        changed = deepcopy(self.config)
        changed["training"]["pretest_budget_selection"][
            "validation_arrays_read"
        ] = True
        with self.assertRaisesRegex(ValueError, "may not access"):
            validate_m1_protocol(changed)

        changed = deepcopy(self.config)
        changed["training"]["pretest_budget_selection"][
            "architecture_result_selection_forbidden"
        ] = False
        with self.assertRaisesRegex(ValueError, "architecture arms"):
            validate_m1_protocol(changed)

        changed = deepcopy(self.config)
        changed["training"]["same_student_architecture_A_to_E"] = False
        with self.assertRaisesRegex(ValueError, "share architecture"):
            validate_m1_protocol(changed)

    def test_primary_set_transformer_is_pre_layernorm(self):
        changed = deepcopy(self.config)
        changed["architecture_evaluation"][
            "cross_candidate_set_transformer_v1"
        ]["normalization"] = "post_layernorm"
        with self.assertRaisesRegex(ValueError, "specification changed"):
            validate_m1_protocol(changed)

    def test_budget_ceiling_policy_cannot_expand_after_results(self):
        changed = deepcopy(self.config)
        changed["training"]["pretest_budget_selection"][
            "upper_checkpoint_policy"
        ] = "add_more_steps_if_10000_wins"
        with self.assertRaisesRegex(ValueError, "ceiling policy"):
            validate_m1_protocol(changed)

    def test_all_methods_keep_one_identical_grid_and_dual_readout(self):
        changed = deepcopy(self.config)
        changed["training"]["pretest_budget_selection"][
            "dual_budget_readout"
        ]["grid_expansion_forbidden"] = False
        with self.assertRaisesRegex(ValueError, "cross-budget readout"):
            validate_m1_protocol(changed)

        changed = deepcopy(self.config)
        changed["training"]["same_student_search_space_A_to_E"] = False
        with self.assertRaisesRegex(ValueError, "share architecture"):
            validate_m1_protocol(changed)

    def test_selection_bootstrap_is_diagnostic_only(self):
        changed = deepcopy(self.config)
        changed["training"]["pretest_budget_selection"][
            "selection_uncertainty"
        ]["diagnostic_only_selection_rule_unchanged"] = False
        with self.assertRaisesRegex(ValueError, "uncertainty diagnostic"):
            validate_m1_protocol(changed)

    def test_validation_no_longer_selects_scorer_or_student_updates(self):
        changed = deepcopy(self.config)
        changed["training"]["validation_only_selection"].append(
            "student_updates"
        )
        with self.assertRaisesRegex(ValueError, "validation may only"):
            validate_m1_protocol(changed)

    def test_current_energy_uses_fixed_range_and_future_keeps_zscore(self):
        changed = deepcopy(self.config)
        changed["energy"]["now_normalization"] = changed["energy"][
            "future_normalization"
        ]
        with self.assertRaisesRegex(ValueError, "fixed natural-range"):
            validate_m1_protocol(changed)

        changed = deepcopy(self.config)
        changed["energy"]["future_normalization"] = changed["energy"][
            "now_normalization"
        ]
        with self.assertRaisesRegex(ValueError, "future must retain"):
            validate_m1_protocol(changed)

        changed = deepcopy(self.config)
        changed["energy"]["no_execution_current_inference_energy"] = (
            "per_decision_zscore_of_BCE"
        )
        with self.assertRaisesRegex(ValueError, "bounded probability error"):
            validate_m1_protocol(changed)

    def test_posterior_influence_audit_cannot_be_reduced_to_argmax(self):
        changed = deepcopy(self.config)
        changed["energy"]["posterior_influence_audit"][
            "primary_interpretation"
        ] = "argmax_only"
        with self.assertRaisesRegex(ValueError, "interpretation"):
            validate_m1_protocol(changed)

        changed = deepcopy(self.config)
        changed["energy"]["posterior_influence_audit"][
            "expected_now_activation_pattern"
        ]["expected_zero_mean_tv_families"] = ["C09"]
        with self.assertRaisesRegex(ValueError, "family activation pattern"):
            validate_m1_protocol(changed)

        changed = deepcopy(self.config)
        changed["energy"]["posterior_influence_audit"][
            "no_execution_comparison"
        ] = "equal_weights_imply_equal_influence"
        with self.assertRaisesRegex(ValueError, "current influence comparison"):
            validate_m1_protocol(changed)

    def test_mechanism_slices_are_generator_defined_and_nonprimary(self):
        changed = deepcopy(self.config)
        changed["evaluation"]["mechanism_diagnostic_slices"][
            "selection_rule"
        ] = "empirical_proxy_accuracy_threshold"
        with self.assertRaisesRegex(ValueError, "measured accuracy"):
            validate_m1_protocol(changed)

        changed = deepcopy(self.config)
        changed["evaluation"]["mechanism_diagnostic_slices"][
            "primary_gate"
        ] = True
        with self.assertRaisesRegex(ValueError, "may not replace"):
            validate_m1_protocol(changed)

    def test_fixed_formal_run_wall_time_cap_is_retired(self):
        changed = deepcopy(self.config)
        changed["resources"]["formal_run_wall_time_limit_hours"] = 2
        with self.assertRaisesRegex(ValueError, "wall-time cap"):
            validate_m1_protocol(changed)


if __name__ == "__main__":
    unittest.main()
