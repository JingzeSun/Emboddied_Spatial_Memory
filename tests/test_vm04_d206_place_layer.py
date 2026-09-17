"""Fail-closed checks for the D-206 place-layer freeze and pose channel."""

import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vsmt.vm04_observation_runner import (  # noqa: E402
    ObservationConstructionError,
    assert_generation_authorized,
    assert_numeric_freeze_complete,
    validate_approved_contract,
)


V2 = ROOT / "configs/vsmt/vm04_observation_suitability_v2.json"
V3 = ROOT / "configs/vsmt/vm04_observation_suitability_v3.json"
V2_SHA256 = "48b50df4adc162e2896145a01d2ab4eb8c87d4dbb943898abab29bb18079fa59"


class D206PlaceLayerTests(unittest.TestCase):
    def setUp(self):
        self.v2 = json.loads(V2.read_text(encoding="utf-8"))
        self.v3 = json.loads(V3.read_text(encoding="utf-8"))

    def test_v2_bytes_are_untouched_by_the_place_layer_freeze(self):
        self.assertEqual(hashlib.sha256(V2.read_bytes()).hexdigest(), V2_SHA256)
        self.assertEqual(self.v3["derived_from"]["source_config_sha256"],
                         V2_SHA256)

    def test_place_layer_freeze_keeps_every_authorization_closed(self):
        self.assertEqual(self.v3["status"],
                         "d206_place_layer_frozen_artifacts_pending")
        self.assertTrue(all(value is False
                            for value in self.v3["authorization"].values()))

    def test_place_layer_adds_no_new_artifact_digest(self):
        self.assertEqual(
            assert_numeric_freeze_complete(self.v3)["pending_artifact_digests"],
            assert_numeric_freeze_complete(self.v2)["pending_artifact_digests"],
        )

    def test_place_layer_freeze_does_not_open_generation(self):
        with self.assertRaises(ObservationConstructionError):
            assert_generation_authorized(self.v3)

    def test_world_pose_may_not_return_to_the_public_packet(self):
        pose = self.v3["public_pose_channel"]
        self.assertFalse(pose["world_ground_truth_pose_in_public_packet"])
        self.assertEqual(pose["world_ground_truth_pose_channel"],
                         "private_evaluation_only")
        leaked = copy.deepcopy(self.v3)
        leaked["public_pose_channel"][
            "world_ground_truth_pose_in_public_packet"] = True
        with self.assertRaises(ObservationConstructionError):
            validate_approved_contract(leaked)

    def test_odometry_noise_is_positive_seeded_and_not_adjustable(self):
        noise = self.v3["public_pose_channel"]["declared_odometry_noise_model"]
        self.assertTrue(noise["seeded_and_reproducible"])
        self.assertTrue(
            noise["simulator_executes_the_commanded_action_unchanged"])
        self.assertFalse(noise["may_be_increased_after_seeing_results"])
        for name in ("translation_relative_sigma", "rotation_relative_sigma",
                     "lateral_slip_sigma_m"):
            self.assertGreater(noise[name], 0.0)
        tunable = copy.deepcopy(self.v3)
        tunable["public_pose_channel"]["declared_odometry_noise_model"][
            "may_be_increased_after_seeing_results"] = True
        with self.assertRaises(ObservationConstructionError):
            validate_approved_contract(tunable)

    def test_zero_noise_is_rejected_because_it_is_an_integration_task(self):
        silent = copy.deepcopy(self.v3)
        silent["public_pose_channel"]["declared_odometry_noise_model"][
            "translation_relative_sigma"] = 0.0
        with self.assertRaises(ObservationConstructionError):
            validate_approved_contract(silent)

    def test_place_is_learnable_and_the_scaffold_is_retired(self):
        scope = self.v3["first_paper_scope_boundary"]
        self.assertIn("place", scope["learnable_structure_kinds"])
        self.assertEqual(scope["deterministic_shared_scaffold"], [])
        self.assertIn("place_identity_revision_including_false_loop_closure_correction",
                      scope["first_paper_may_claim"])
        place = self.v3["place_identity_revision"]
        self.assertTrue(place["place_is_learnable"])
        self.assertTrue(place["place_scaffold_deterministic_identity_retired"])
        self.assertEqual(place["adjacent_to_source"],
                         "evidence_based_not_coordinate_derived")

    def test_place_cannot_be_learnable_and_scaffolded_at_once(self):
        both = copy.deepcopy(self.v3)
        both["first_paper_scope_boundary"]["deterministic_shared_scaffold"] = [
            "place_identity"
        ]
        with self.assertRaises(ObservationConstructionError):
            validate_approved_contract(both)

    def test_retiring_the_scaffold_requires_making_place_learnable(self):
        halfway = copy.deepcopy(self.v3)
        halfway["first_paper_scope_boundary"]["learnable_structure_kinds"] = [
            "entity", "surface", "fragment"
        ]
        with self.assertRaises(ObservationConstructionError):
            validate_approved_contract(halfway)

    def test_every_learnable_kind_has_its_own_association_rule(self):
        rules = self.v3["program_construction_review_candidate"][
            "frozen_matcher_numeric_values"][
                "association_rules_by_structure_kind"]
        self.assertEqual(
            set(rules),
            set(self.v3["first_paper_scope_boundary"]["learnable_structure_kinds"]))
        self.assertAlmostEqual(
            rules["place"]["visual_weight"] + rules["place"]["geometry_weight"],
            1.0)
        self.assertGreater(rules["place"]["maximum_centroid_distance_m"],
                           rules["entity"]["maximum_centroid_distance_m"])
        missing = copy.deepcopy(self.v3)
        missing["program_construction_review_candidate"][
            "frozen_matcher_numeric_values"][
                "association_rules_by_structure_kind"].pop("place")
        with self.assertRaises(ObservationConstructionError):
            validate_approved_contract(missing)

    def test_cfo_probe_loses_pose_and_past_actions(self):
        forbidden = self.v3["l2_identifiability_admission_gate"][
            "current_frame_only_probe"]["forbidden_inputs"]
        self.assertIn("camera_pose", forbidden)
        self.assertIn("past_actions", forbidden)
        masked = self.v3["l2_identifiability_admission_gate"][
            "frozen_model_and_budget_values"][
                "CFO_and_public_history_probe_architecture"][
                    "history_and_prior_inputs_masked_for_CFO"]
        self.assertIn("pose_tokens", masked)
        self.assertIn("past_action_tokens", masked)

    def test_cfo_probe_cannot_regain_pose(self):
        regained = copy.deepcopy(self.v3)
        regained["l2_identifiability_admission_gate"][
            "current_frame_only_probe"]["forbidden_inputs"] = [
                "prior_memory", "observation_history", "candidate_catalog",
                "private_identity", "teacher", "future_observation",
            ]
        with self.assertRaises(ObservationConstructionError):
            validate_approved_contract(regained)

    def test_z_route_requires_later_disambiguation(self):
        z_route = self.v3["place_identity_revision"]["z_route_family"]
        self.assertTrue(z_route["requires_two_registered_turns"])
        self.assertTrue(
            z_route["corridors_must_be_visually_similar_by_construction"])
        self.assertIsInstance(z_route["required_later_disambiguation"], str)
        self.assertFalse(z_route["geometry_may_be_tuned_after_seeing_outcomes"])
        one_shot = copy.deepcopy(self.v3)
        one_shot["place_identity_revision"]["z_route_family"][
            "disambiguating_observation_required_after_arrival_at_B"] = False
        with self.assertRaises(ObservationConstructionError):
            validate_approved_contract(one_shot)

    def test_place_oracle_arm_stays_a_diagnostic(self):
        oracle = self.v3["place_identity_revision"]["place_oracle_diagnostic_arm"]
        self.assertEqual(oracle["main_table_arm"], "inferred_place")
        self.assertFalse(oracle["oracle_arm_may_enter_the_main_table"])
        promoted = copy.deepcopy(self.v3)
        promoted["place_identity_revision"]["place_oracle_diagnostic_arm"][
            "oracle_arm_may_enter_the_main_table"] = True
        with self.assertRaises(ObservationConstructionError):
            validate_approved_contract(promoted)

    def test_d205_frozen_values_survive_the_place_layer_change(self):
        for section, key in (
            ("observation_trajectory", "registered_action_request_templates"),
            ("public_packet_materialization", "decision_time_rule"),
            ("public_packet_materialization", "action_command_encoding"),
            ("public_visibility_builder_review_candidate",
             "frozen_numeric_values"),
        ):
            self.assertEqual(self.v2[section][key], self.v3[section][key],
                             f"{section}/{key} drifted")
        self.assertEqual(
            self.v2["deterministic_SPLIT_MERGE_construction"][
                "fresh_replay_repeat_count"],
            self.v3["deterministic_SPLIT_MERGE_construction"][
                "fresh_replay_repeat_count"])

    def test_place_layer_adds_only_engineering_blockers(self):
        added = [item for item in self.v3["pre_generation_blockers"]
                 if item not in self.v2["pre_generation_blockers"]]
        self.assertEqual(sorted(added), sorted([
            "replace_the_public_world_camera_pose_with_relative_noisy_odometry"
            "_in_the_raw_writer",
            "retire_the_deterministic_place_scaffold_into_the_oracle_diagnostic"
            "_arm_and_implement_place_association",
            "implement_the_real_public_reachable_position_route_scan_and_the_Z"
            "_route_family_builder",
        ]))


if __name__ == "__main__":
    unittest.main()
