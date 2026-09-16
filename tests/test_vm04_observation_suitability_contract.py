"""Fail-closed checks for the proposed post-D-180 observation contract."""

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs/vsmt/vm04_observation_suitability_proposal_v1.json"


class ObservationSuitabilityContractTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_every_execution_authorization_is_closed(self):
        self.assertEqual(
            self.contract["status"],
            "d183_design_and_numeric_values_approved_schema_review_only")
        self.assertTrue(all(value is False for value in
                            self.contract["authorization"].values()))
        self.assertFalse(
            self.contract["old_static_36_policy"]["server_run_allowed"])
        self.assertFalse(
            self.contract["old_static_36_policy"]["paper_main_table_allowed"])

    def test_route_requires_translation_and_all_visibility_phases(self):
        route = self.contract["observation_trajectory"]
        self.assertIn("MoveAhead", route["registered_post_initial_actions"])
        self.assertIn("MoveLeft", route["registered_post_initial_actions"])
        self.assertIsNone(route["registered_action_request_templates"])
        self.assertTrue(route["actual_pose_not_command_is_scored"])
        self.assertTrue(route["route_sealed_before_private_identity_and_action_outcome"])
        self.assertEqual(
            route["reobservation_translation_reference"],
            "pre_intervention_program_specific_public_precondition_pose")
        self.assertEqual(
            set(route["intervention_visibility_constraint"][
                "allowed_public_states_at_intervention"]),
            {"occluded", "out_of_view"})
        self.assertEqual(
            route["intervention_visibility_constraint"]["failure_reason"],
            "intervention_visible_to_camera")
        self.assertEqual(set(route["required_family_branch_types"]), {
            "natural_occlusion_then_reobservation",
            "out_of_view_then_reobservation",
        })
        self.assertEqual(set(route["required_episode_phases"]), {
            "program_specific_public_precondition_established",
            "one_pre_registered_visibility_challenge_branch",
            "world_intervention_while_visibility_subject_is_unobservable_if_applicable",
            "target_or_relation_observed_from_a_translated_pose",
        })
        self.assertIn(
            "no_prior_entity_node_or_relation",
            route["program_specific_public_preconditions"]["BIRTH"])
        self.assertIn(
            "old_relation_P1",
            route["program_specific_public_preconditions"]["RELINK"])
        self.assertEqual(route["numeric_review_required_before_generation"], {
            "minimum_key_pose_translation_m": 0.5,
            "minimum_reobservation_translation_m": 0.5,
            "minimum_key_pose_yaw_change_degrees": 30.0,
            "minimum_public_observations_per_visibility_state": 2,
            "maximum_route_steps": 24,
            "pose_tolerance_m": 0.02,
            "yaw_tolerance_degrees": 1.0,
        })

    def test_crosswalk_provenance_is_an_explicit_positive_label_blocker(self):
        provenance = self.contract["crosswalk_provenance"]
        self.assertEqual(
            provenance["status"],
            "receipt_schema_and_gate_binding_implemented_materializer_executor_pending")
        self.assertTrue(
            provenance["required_before_any_physical_relink_positive"])
        self.assertIn("private_crosswalk_sha256",
                      provenance["planned_receipt_must_bind"])
        self.assertEqual(
            provenance["gate_behavior_until_implemented"],
            "no_real_physical_relink_positive_may_be_issued_until_materializer_executor_is_reviewed_and_receipt_is_present")
        self.assertIsNone(provenance["expected_materializer_code_sha256"])
        self.assertIsNone(provenance["expected_materializer_config_sha256"])
        self.assertIn(
            "implement_and_review_trusted_materializer_executor_and_parent_stage_binding",
            self.contract["pre_generation_blockers"],
        )

    def test_lifecycle_visibility_is_checked_until_terminal(self):
        policy = self.contract["lifecycle_poststate_policy"]
        self.assertTrue(
            policy["disabled_target_checked_after_every_registered_camera_action"])
        self.assertTrue(policy[
            "enabled_target_checked_after_every_remaining_registered_camera_action"])
        self.assertEqual(
            policy["enabled_terminal_disappearance_failure"],
            "enabled_target_disappeared_before_terminal")
        self.assertEqual(policy["scope"], "fixed_view_worker_only")
        window = policy["multiview_terminal_reobservation_window"]
        self.assertEqual(window["scope"], "new_multiview_runner_only")
        self.assertEqual(window["minimum_registered_public_observations"], 2)
        self.assertTrue(window["must_begin_after_reobservation_pose_arrival"])
        self.assertTrue(window["observations_must_be_consecutive"])

    def test_identifiability_is_a_result_blind_hard_gate(self):
        gate = self.contract["l2_identifiability_admission_gate"]
        self.assertTrue(gate["rule_and_thresholds_frozen_before_generation"])
        self.assertFalse(gate["result_blind_threshold_changes_allowed"])
        self.assertEqual(gate["primary_unit"], "house_family")
        self.assertTrue(gate["paired_by_family"])
        self.assertTrue(gate["probe_structure_selection"][
            "single_shared_architecture_required"])
        self.assertFalse(gate["probe_structure_selection"][
            "choose_better_model_on_gate_families_allowed"])
        self.assertEqual(
            gate["current_frame_only_probe"]["input"],
            "current_L2_public_observation_packet_only")
        self.assertIn("prior_memory",
                      gate["current_frame_only_probe"]["forbidden_inputs"])
        self.assertEqual(
            gate["fail_action"],
            "dataset_version_is_engineering_or_easy_slice_only_and_cannot_enter_L2_main_table")
        numbers = gate["numeric_review_required_before_generation"]
        self.assertEqual(numbers["minimum_accuracy_gap"], 0.15)
        self.assertEqual(numbers["maximum_CFO_accuracy"], 0.6)
        self.assertEqual(numbers["minimum_sealed_catalog_oracle_recall"], 0.9)
        self.assertEqual(numbers["confidence_level"], 0.95)
        self.assertEqual(numbers["bootstrap_seed"], 260916)
        self.assertEqual(numbers["bootstrap_resamples"], 10000)
        self.assertEqual(numbers["minimum_development_families"], 32)
        self.assertIsNone(numbers["CFO_and_public_history_probe_architecture"])
        self.assertIsNone(numbers["shared_probe_training_budget"])

    def test_pilot_is_disjoint_and_formal_failures_cannot_add_houses(self):
        pilot = self.contract["development_pilot"]
        self.assertEqual(pilot["family_count"], 6)
        self.assertTrue(pilot["source_houses_disjoint_from_formal_development"])
        self.assertTrue(
            pilot["selection_rule_and_ordered_source_pool_sealed_before_pilot"])
        self.assertTrue(
            pilot["formal_house_count_sealed_after_pilot_before_formal_generation"])
        self.assertEqual(pilot["ordered_source_pool_minimum_eligible_houses"], 70)
        self.assertFalse(pilot["included_in_identifiability_gate"])
        self.assertFalse(pilot["included_in_VM05_training_or_validation"])
        formal = self.contract["formal_development_sampling"]
        self.assertIsNone(formal["source_houses_to_attempt"])
        self.assertEqual(formal["base_source_houses_to_attempt"], 48)
        self.assertEqual(formal["maximum_source_houses_to_attempt"], 64)
        self.assertEqual(
            formal["house_selection_rule"],
            "result_blind_manifest_hash_order_frozen_before_pilot")
        self.assertFalse(
            formal["additional_houses_after_observed_failures_allowed"])
        self.assertEqual(
            formal["minimum_completed_families"], 32)
        self.assertEqual(
            formal["insufficient_completed_families_action"],
            "fail_construction_gate_and_do_not_run_identifiability_VM05_or_VM06")

    def test_d183_program_and_split_merge_rules_are_merged_but_blocked(self):
        gate = self.contract["l2_identifiability_admission_gate"]
        report = gate["per_program_reporting"]
        self.assertTrue(report["required"])
        self.assertEqual(report["easy_class_CFO_threshold"], 0.6)
        self.assertEqual(
            report["easy_class_action"],
            "retain_in_aggregate_denominator_but_forbid_standalone_evidence_for_that_program")
        construction = self.contract["deterministic_SPLIT_MERGE_construction"]
        self.assertTrue(construction["program_assignment_sealed_before_generation"])
        self.assertFalse(construction[
            "posthoc_program_label_from_observed_artifact_allowed"])
        self.assertIsNone(construction["fresh_replay_repeat_count"])
        self.assertIsNone(construction["exact_geometry_parameters"])
        self.assertIsNone(construction["frozen_frontend_artifact_criteria"])

if __name__ == "__main__":
    unittest.main()
