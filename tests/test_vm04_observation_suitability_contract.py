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
            "requires_numeric_and_code_review_not_executable")
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
        self.assertTrue(all(value is None for value in
                            route["numeric_review_required_before_generation"].values()))

    def test_crosswalk_provenance_is_an_explicit_positive_label_blocker(self):
        provenance = self.contract["crosswalk_provenance"]
        self.assertEqual(
            provenance["status"],
            "pending_trusted_materializer_receipt_implementation")
        self.assertTrue(
            provenance["required_before_any_physical_relink_positive"])
        self.assertIn("private_crosswalk_sha256",
                      provenance["planned_receipt_must_bind"])
        self.assertEqual(
            provenance["gate_behavior_until_implemented"],
            "no_real_physical_relink_positive_may_be_issued")

    def test_lifecycle_visibility_is_checked_until_terminal(self):
        policy = self.contract["lifecycle_poststate_policy"]
        self.assertTrue(
            policy["disabled_target_checked_after_every_registered_camera_action"])
        self.assertTrue(policy[
            "enabled_target_checked_after_every_remaining_registered_camera_action"])
        self.assertEqual(
            policy["enabled_terminal_disappearance_failure"],
            "enabled_target_disappeared_before_terminal")

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
        self.assertTrue(all(value is None for value in
                            gate["numeric_review_required_before_generation"].values()))

    def test_pilot_is_disjoint_and_formal_failures_cannot_add_houses(self):
        pilot = self.contract["development_pilot"]
        self.assertEqual(pilot["family_count"], None)
        self.assertEqual(
            pilot["recommended_family_count_for_review_not_frozen"], 6)
        self.assertTrue(pilot["source_houses_disjoint_from_formal_development"])
        self.assertTrue(
            pilot["pilot_and_formal_house_manifests_sealed_before_pilot"])
        self.assertFalse(pilot["included_in_identifiability_gate"])
        self.assertFalse(pilot["included_in_VM05_training_or_validation"])
        formal = self.contract["formal_development_sampling"]
        self.assertIsNone(formal["source_houses_to_attempt"])
        self.assertEqual(
            formal["house_selection_rule"],
            "result_blind_manifest_hash_order_frozen_before_pilot")
        self.assertEqual(
            formal["recommended_values_for_review_not_frozen"][
                "source_houses_to_attempt"], 48)
        self.assertFalse(
            formal["additional_houses_after_observed_failures_allowed"])
        self.assertEqual(
            self.contract["l2_identifiability_admission_gate"][
                "recommended_values_for_review_not_frozen"][
                    "minimum_development_families"], 32)


if __name__ == "__main__":
    unittest.main()
