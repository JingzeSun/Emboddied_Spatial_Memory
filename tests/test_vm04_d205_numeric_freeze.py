"""Fail-closed checks for the D-205 numeric freeze and pilot completion derivation."""

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
    make_source_pool_manifest,
    validate_approved_contract,
)
from vsmt.vm04_pilot_family_completion import (  # noqa: E402
    derive_pilot_family_completion,
    seal_formal_selection_from_pilot,
    validate_pilot_family_completion,
)


V1 = ROOT / "configs/vsmt/vm04_observation_suitability_proposal_v1.json"
V2 = ROOT / "configs/vsmt/vm04_observation_suitability_v2.json"
V1_SHA256 = "2d99d51995e1b8f0ded5e66f1f0df9b8fab94c452655324ba289105eb38ba4c3"


def _route_digest(seed):
    return hashlib.sha256(f"route:{seed}".encode("utf-8")).hexdigest()


def _verdict(seed, *, constructed, reasons=()):
    return {
        "schema_version": "vsmt-vm04-observation-construction-verdict-v1",
        "route_plan_sha256": _route_digest(seed),
        "constructed": constructed,
        "failure_reasons": list(reasons),
        "failed_route_replacement_allowed": False,
        "actual_observation_count": 9,
        "terminal_reobservation_satisfied": constructed,
    }


def _artifact(program, *, realized, repeats=3):
    far, near = (1, 2) if program == "SPLIT" else (2, 1)
    replays = []
    for index in range(repeats):
        ok = realized if index == repeats - 1 else True
        replays.append({
            "replay_index": index,
            "far_proposal_count_covering_target": far if ok else far + 1,
            "near_proposal_count_covering_target": near,
            "registered_transition_realized": ok,
        })
    return {
        "schema_version": "vsmt-vm04-split-merge-artifact-receipt-v1",
        "program": program,
        "fresh_replays": replays,
    }


def _family(pool_index, *, complete=True, split_realized=True,
            merge_realized=True):
    episodes = [
        {"program": "BIND", "route_plan_sha256": _route_digest((pool_index, 0)),
         "construction_verdict": _verdict(
             (pool_index, 0), constructed=complete,
             reasons=() if complete else ("terminal_reobservation_window_failed",))},
        {"program": "SPLIT", "route_plan_sha256": _route_digest((pool_index, 1)),
         "construction_verdict": _verdict((pool_index, 1), constructed=True)},
        {"program": "MERGE", "route_plan_sha256": _route_digest((pool_index, 2)),
         "construction_verdict": _verdict((pool_index, 2), constructed=True)},
    ]
    return {
        "pool_index": pool_index,
        "registered_episodes": episodes,
        "artifact_receipts": {
            "SPLIT": _artifact("SPLIT", realized=split_realized),
            "MERGE": _artifact("MERGE", realized=merge_realized),
        },
    }


class D205ContractFreezeTests(unittest.TestCase):
    def setUp(self):
        self.v1 = json.loads(V1.read_text(encoding="utf-8"))
        self.v2 = json.loads(V2.read_text(encoding="utf-8"))

    def test_v1_bytes_are_untouched_by_the_freeze(self):
        digest = hashlib.sha256(V1.read_bytes()).hexdigest()
        self.assertEqual(digest, V1_SHA256)
        self.assertEqual(self.v2["derived_from"]["source_config_sha256"],
                         V1_SHA256)

    def test_unchanged_sections_are_copied_verbatim(self):
        touched = {
            "version", "status", "decision", "derived_from",
            "first_paper_scope_boundary", "observation_trajectory",
            "public_packet_materialization",
            "l2_public_proposal_frontend_review_candidate",
            "public_visibility_builder_review_candidate",
            "program_construction_review_candidate",
            "l2_identifiability_admission_gate",
            "deterministic_SPLIT_MERGE_construction", "development_pilot",
            "pre_generation_blockers", "blocker_taxonomy",
        }
        for key in self.v1:
            if key not in touched:
                self.assertEqual(self.v1[key], self.v2[key], key)

    def test_numeric_freeze_leaves_only_artifact_digests_null(self):
        nulls = []

        def walk(node, path=""):
            if isinstance(node, dict):
                for key, value in node.items():
                    walk(value, f"{path}/{key}")
            elif isinstance(node, list):
                for index, value in enumerate(node):
                    walk(value, f"{path}/[{index}]")
            elif node is None:
                nulls.append(path)

        walk(self.v2)
        self.assertEqual(sorted(nulls), sorted([
            "/crosswalk_provenance/expected_materializer_code_sha256",
            "/crosswalk_provenance/expected_materializer_config_sha256",
            "/l2_public_proposal_frontend_review_candidate"
            "/pending_artifact_digests/repository_commit",
            "/l2_public_proposal_frontend_review_candidate"
            "/pending_artifact_digests/checkpoint_sha256",
            "/l2_public_proposal_frontend_review_candidate"
            "/pending_artifact_digests/automatic_mask_generator_config_sha256",
            "/l2_public_proposal_frontend_review_candidate"
            "/pending_artifact_digests/assets_receipt_sha256",
            "/l2_public_proposal_frontend_review_candidate"
            "/pending_artifact_digests/generator_code_sha256",
            "/l2_identifiability_admission_gate/evidence_level"
            "/reviewed_L2_frontend_receipt_sha256",
            "/formal_development_sampling/source_houses_to_attempt",
        ]))

    def test_numeric_freeze_keeps_every_authorization_closed(self):
        self.assertEqual(self.v2["status"],
                         "d205_numeric_frozen_artifacts_pending")
        self.assertTrue(all(value is False
                            for value in self.v2["authorization"].values()))

    def test_freeze_status_report_lists_only_pending_artifacts(self):
        report = assert_numeric_freeze_complete(self.v2)
        self.assertTrue(report["scientific_decisions_frozen"])
        self.assertFalse(report["generation_authorized"])
        self.assertFalse(report["pilot_family_completion_reviewed"])
        self.assertTrue(report["numeric_freeze_does_not_authorize_generation"])
        self.assertEqual(len(report["pending_artifact_digests"]), 8)

    def test_v1_cannot_claim_the_numeric_freeze(self):
        with self.assertRaises(ObservationConstructionError):
            assert_numeric_freeze_complete(self.v1)

    def test_numeric_freeze_does_not_open_generation(self):
        with self.assertRaises(ObservationConstructionError):
            assert_generation_authorized(self.v2)

    def test_paper_scope_boundary_cannot_be_weakened(self):
        scope = self.v2["first_paper_scope_boundary"]
        self.assertIn("place_or_room_identity_revision",
                      scope["first_paper_may_not_claim"])
        self.assertIn("spatial_topology_or_connectivity_revision",
                      scope["first_paper_may_not_claim"])
        self.assertEqual(scope["learnable_structure_kinds"],
                         ["entity", "surface", "fragment"])
        weakened = copy.deepcopy(self.v2)
        weakened["first_paper_scope_boundary"]["first_paper_may_not_claim"] = [
            "robustness_to_pose_estimation_or_SLAM_drift"
        ]
        with self.assertRaises(ObservationConstructionError):
            validate_approved_contract(weakened)

    def test_camera_actions_are_explicit_without_defaults_or_force(self):
        templates = self.v2["observation_trajectory"][
            "registered_action_request_templates"]
        self.assertEqual(len(templates), 8)
        for action, request in templates.items():
            self.assertEqual(request["action"], action)
            self.assertNotIn("forceAction", request)
            key = "moveMagnitude" if action.startswith("Move") else "degrees"
            self.assertGreater(request[key], 0.0)
        rotation = templates["RotateLeft"]["degrees"]
        minimum_yaw = self.v2["observation_trajectory"][
            "frozen_numeric_values"]["minimum_key_pose_yaw_change_degrees"]
        self.assertGreaterEqual(rotation, minimum_yaw)

    def test_action_encoding_is_distinct_and_carries_no_private_field(self):
        encoding = self.v2["public_packet_materialization"][
            "action_command_encoding"]
        order = encoding["component_order"]
        self.assertEqual(len(order), len(set(order)))
        self.assertEqual(encoding["vector_length"], len(order))
        self.assertFalse(encoding["private_or_program_fields_encoded"])
        broken = copy.deepcopy(self.v2)
        broken["public_packet_materialization"][
            "action_command_encoding"]["component_order"] = order[:-1]
        with self.assertRaises(ObservationConstructionError):
            validate_approved_contract(broken)

    def test_proposal_suppression_stays_disabled_for_overlap_policy(self):
        amg = self.v2["l2_public_proposal_frontend_review_candidate"][
            "frozen_automatic_mask_generator_config"]
        self.assertEqual(amg["box_nms_thresh"], 1.0)
        self.assertEqual(amg["crop_nms_thresh"], 1.0)
        suppressed = copy.deepcopy(self.v2)
        suppressed["l2_public_proposal_frontend_review_candidate"][
            "frozen_automatic_mask_generator_config"]["box_nms_thresh"] = 0.7
        with self.assertRaises(ObservationConstructionError):
            validate_approved_contract(suppressed)

    def test_matcher_rules_are_typed_per_structure_kind(self):
        matcher = self.v2["program_construction_review_candidate"][
            "frozen_matcher_numeric_values"]
        rules = matcher["association_rules_by_structure_kind"]
        self.assertEqual(set(rules), {"entity", "surface", "fragment"})
        for rule in rules.values():
            self.assertAlmostEqual(
                rule["visual_weight"] + rule["geometry_weight"], 1.0)
        self.assertGreater(rules["entity"]["maximum_centroid_distance_m"],
                           rules["surface"]["maximum_centroid_distance_m"])
        self.assertGreaterEqual(
            matcher["minimum_independent_negative_observations"], 2)
        collapsed = copy.deepcopy(self.v2)
        collapsed["program_construction_review_candidate"][
            "frozen_matcher_numeric_values"][
                "association_rules_by_structure_kind"].pop("fragment")
        with self.assertRaises(ObservationConstructionError):
            validate_approved_contract(collapsed)

    def test_shared_probe_registers_exactly_one_configuration(self):
        frozen = self.v2["l2_identifiability_admission_gate"][
            "frozen_model_and_budget_values"]
        self.assertEqual(
            frozen["shared_probe_training_budget"]["configuration_selection"],
            "none_single_registered_configuration")
        self.assertTrue(frozen["CFO_and_public_history_probe_architecture"][
            "mask_is_the_only_difference"])
        self.assertEqual(
            self.v2["l2_identifiability_admission_gate"][
                "probe_structure_selection"]["selection_family_split"],
            "none_single_registered_configuration_requires_no_selection_split")

    def test_pilot_diagnostic_cannot_select_anything(self):
        diagnostic = self.v2["l2_identifiability_admission_gate"][
            "pilot_report_only_diagnostic"]
        for field in ("may_change_gate_thresholds",
                      "may_change_formal_house_count",
                      "may_change_probe_architecture_or_budget",
                      "may_change_route_geometry_or_program_assignment",
                      "may_change_matcher_or_visibility_numerics"):
            self.assertFalse(diagnostic[field], field)
        self.assertTrue(
            diagnostic["pilot_results_excluded_from_all_formal_statistics"])
        selective = copy.deepcopy(self.v2)
        selective["l2_identifiability_admission_gate"][
            "pilot_report_only_diagnostic"]["may_change_formal_house_count"] = True
        with self.assertRaises(ObservationConstructionError):
            validate_approved_contract(selective)

    def test_split_merge_yield_floor_is_not_adjustable(self):
        floor = self.v2["deterministic_SPLIT_MERGE_construction"][
            "pilot_artifact_yield_floor"]
        self.assertFalse(floor["thresholds_may_change_after_seeing_pilot_results"])
        self.assertFalse(floor["below_floor_may_change_geometry_or_criteria"])
        tunable = copy.deepcopy(self.v2)
        tunable["deterministic_SPLIT_MERGE_construction"][
            "pilot_artifact_yield_floor"][
                "thresholds_may_change_after_seeing_pilot_results"] = True
        with self.assertRaises(ObservationConstructionError):
            validate_approved_contract(tunable)


class PilotFamilyCompletionTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads(V2.read_text(encoding="utf-8"))
        self.pool = make_source_pool_manifest(
            [f"train:{index:06d}" for index in range(80)],
            source_manifest_sha256="a" * 64,
            selection_seed=260916,
        )

    def _derive(self, families):
        return derive_pilot_family_completion(
            self.pool, families, contract=self.contract)

    def test_six_complete_families_seal_forty_eight_formal_houses(self):
        record = self._derive([_family(index) for index in range(6)])
        self.assertEqual(record["pilot_completed_families"], 6)
        validate_pilot_family_completion(record)
        selection = seal_formal_selection_from_pilot(self.pool, record)
        self.assertEqual(selection["status"], "sealed")
        self.assertEqual(selection["formal_source_house_count"], 48)
        self.assertEqual(selection["pilot_inputs_used"],
                         "mechanically_derived_construction_completion")
        self.assertFalse(selection["CFO_history_or_oracle_inputs_used"])

    def test_four_complete_families_seal_sixty_four_formal_houses(self):
        families = [_family(index, complete=index < 4) for index in range(6)]
        record = self._derive(families)
        self.assertEqual(record["pilot_completed_families"], 4)
        selection = seal_formal_selection_from_pilot(self.pool, record)
        self.assertEqual(selection["formal_source_house_count"], 64)

    def test_three_complete_families_stop_the_contract_version(self):
        families = [_family(index, complete=index < 3) for index in range(6)]
        record = self._derive(families)
        selection = seal_formal_selection_from_pilot(self.pool, record)
        self.assertEqual(selection["status"], "stopped_new_contract_required")
        self.assertEqual(selection["formal_source_house_count"], 0)

    def test_formal_houses_never_overlap_the_pilot_cohort(self):
        record = self._derive([_family(index) for index in range(6)])
        selection = seal_formal_selection_from_pilot(self.pool, record)
        self.assertEqual(min(selection["selected_pool_indices"]), 6)

    def test_incomplete_family_retains_its_reason(self):
        families = [_family(index, complete=index != 2) for index in range(6)]
        record = self._derive(families)
        row = record["families"][2]
        self.assertFalse(row["family_complete"])
        self.assertIn("BIND:terminal_reobservation_window_failed",
                      row["incompletion_reasons"])

    def test_unrealized_fresh_replay_fails_the_family(self):
        families = [_family(index, split_realized=index != 1)
                    for index in range(6)]
        record = self._derive(families)
        self.assertFalse(record["families"][1]["family_complete"])
        self.assertIn("SPLIT:fresh_replay_transition_not_realized",
                      record["families"][1]["incompletion_reasons"])

    def test_yield_floor_demotes_split_when_below_the_frozen_minimum(self):
        families = [_family(index, split_realized=index < 2)
                    for index in range(6)]
        record = self._derive(families)
        floor = record["split_merge_pilot_yield_floor"]
        self.assertEqual(floor["demoted_from_confirmatory_set"], ["SPLIT"])
        self.assertEqual(floor["remaining_confirmatory_atoms"],
                         ["MERGE", "entity_RETRACT"])
        self.assertEqual(floor["programs"]["SPLIT"]
                         ["families_with_all_replays_realized"], 2)

    def test_yield_floor_keeps_both_atoms_when_met(self):
        record = self._derive([_family(index) for index in range(6)])
        floor = record["split_merge_pilot_yield_floor"]
        self.assertEqual(floor["demoted_from_confirmatory_set"], [])
        self.assertEqual(floor["remaining_confirmatory_atoms"],
                         ["MERGE", "SPLIT", "entity_RETRACT"])

    def test_caller_supplied_completion_boolean_is_rejected(self):
        families = [_family(index) for index in range(6)]
        families[0]["registered_episodes"][0]["constructed"] = True
        with self.assertRaises(ObservationConstructionError):
            self._derive(families)

    def test_verdict_must_bind_the_sealed_route_plan(self):
        families = [_family(index) for index in range(6)]
        families[0]["registered_episodes"][0]["construction_verdict"][
            "route_plan_sha256"] = _route_digest("other")
        with self.assertRaises(ObservationConstructionError):
            self._derive(families)

    def test_realization_flag_must_match_public_proposal_counts(self):
        families = [_family(index) for index in range(6)]
        receipt = families[0]["artifact_receipts"]["SPLIT"]
        receipt["fresh_replays"][0]["registered_transition_realized"] = False
        with self.assertRaises(ObservationConstructionError):
            self._derive(families)

    def test_unregistered_artifact_receipt_is_rejected(self):
        families = [_family(index) for index in range(6)]
        families[0]["registered_episodes"] = [
            families[0]["registered_episodes"][0]
        ]
        with self.assertRaises(ObservationConstructionError):
            self._derive(families)

    def test_tampered_completion_digest_is_rejected(self):
        record = self._derive([_family(index) for index in range(6)])
        record["pilot_completed_families"] = 4
        with self.assertRaises(ObservationConstructionError):
            validate_pilot_family_completion(record)

    def test_completion_record_must_bind_its_source_pool(self):
        record = self._derive([_family(index) for index in range(6)])
        other = make_source_pool_manifest(
            [f"train:{index:06d}" for index in range(80)],
            source_manifest_sha256="b" * 64,
            selection_seed=260916,
        )
        with self.assertRaises(ObservationConstructionError):
            seal_formal_selection_from_pilot(other, record)


if __name__ == "__main__":
    unittest.main()
