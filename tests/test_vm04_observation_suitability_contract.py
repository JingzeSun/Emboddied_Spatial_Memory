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
        self.assertEqual(set(route["required_family_branch_types"]), {
            "natural_occlusion_then_reobservation",
            "out_of_view_then_reobservation",
        })
        self.assertEqual(set(route["required_episode_phases"]), {
            "old_relation_visible_from_pre_action_pose",
            "one_pre_registered_visibility_challenge_branch",
            "target_reobserved_from_a_translated_pose",
            "post_intervention_relation_observed_from_current_rgbd",
        })
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

    def test_identifiability_is_a_result_blind_hard_gate(self):
        gate = self.contract["l2_identifiability_admission_gate"]
        self.assertTrue(gate["rule_and_thresholds_frozen_before_generation"])
        self.assertFalse(gate["result_blind_threshold_changes_allowed"])
        self.assertEqual(gate["primary_unit"], "house_family")
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


if __name__ == "__main__":
    unittest.main()
