"""Scientific-boundary tests for the post-D-183 VM-04 planning core."""

import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from cpmt.hashing import canonical_json
from vsmt.vm04_observation_runner import (
    ObservationConstructionError,
    assess_route_receipt,
    assert_generation_authorized,
    make_public_visibility_assessment,
    make_source_pool_manifest,
    public_route_projection,
    seal_formal_selection,
    validate_approved_contract,
    validate_registered_action_request_templates,
    validate_route_plan,
)


CONTRACT_PATH = ROOT / "configs/vsmt/vm04_observation_suitability_proposal_v1.json"
SCHEMA_PATH = ROOT / "schemas/vsmt_vm04_observation_construction.schema.json"
ZERO_SHA = "0" * 64
SUBJECT_SHA = "a" * 64
VISIBILITY_CONFIG_SHA = "b" * 64


def _sha(value):
    import hashlib
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _builder_receipt(assessment, index):
    receipt = {
        "schema_version": "vsmt-vm04-public-visibility-builder-receipt-v1",
        "subject_seal_sha256": SUBJECT_SHA,
        "current_observation_index": index,
        "current_public_depth_sha256": f"{index + 1:x}" * 64,
        "camera_calibration_and_pose_sha256": f"{index + 2:x}" * 64,
        "config_sha256": VISIBILITY_CONFIG_SHA,
        "assessment_sha256": assessment["assessment_sha256"],
        "invalid_or_missing_depth_treated_as_unoccluded": True,
    }
    receipt["receipt_sha256"] = _sha(receipt)
    return receipt


def _contract():
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _action_requests():
    return {
        action: {
            "action": action,
            ("moveMagnitude" if action.startswith("Move") else "degrees"):
                (0.25 if action.startswith("Move") else 30.0),
        }
        for action in (
            "MoveAhead", "MoveBack", "MoveLeft", "MoveRight",
            "RotateLeft", "RotateRight", "LookUp", "LookDown",
        )
    }


def _route(program="RELINK", branch="natural_occlusion_then_reobservation"):
    artifact = None
    if program in {"SPLIT", "MERGE"}:
        artifact = {
            "program": program,
            "assignment_sealed_before_generation": True,
            "geometry_parameters_sha256": "1" * 64,
            "frontend_criteria_sha256": "2" * 64,
        }
    subject = "reveal_locus" if program == "BIRTH" else (
        "old_track_and_new_reveal_locus" if program == "REPLACE" else
        "target_track"
    )
    plan = {
        "schema_version": "vsmt-vm04-observation-route-plan-v1",
        "episode_id": "episode:opaque-0001",
        "program": program,
        "branch_type": branch,
        "visibility_subject_kind": subject,
        "visibility_subject_public_ref": "public-subject:0001",
        "visibility_subject_seal_sha256": SUBJECT_SHA,
        "visibility_builder_config_sha256": VISIBILITY_CONFIG_SHA,
        "initial_pose": {"x_m": 0.0, "y_m": 0.9, "z_m": 0.0,
                         "yaw_deg": 0.0},
        "registered_actions": [
            {"step_index": index, "action": action}
            for index, action in enumerate([
                "MoveAhead", "MoveAhead", "RotateRight",
                "MoveRight", "MoveRight",
            ])
        ],
        "phase_observation_indices": {
            "precondition_visible": [0, 1],
            "challenge_hidden": [2, 3],
            "reobserved": [4, 5],
        },
        "planned_poses": {
            "precondition": {"x_m": 0.0, "y_m": 0.9, "z_m": 0.0,
                             "yaw_deg": 0.0},
            "challenge": {"x_m": 0.5, "y_m": 0.9, "z_m": 0.0,
                          "yaw_deg": 30.0},
            "reobservation": {"x_m": 1.0, "y_m": 0.9, "z_m": 0.0,
                              "yaw_deg": 0.0},
        },
        "intervention_after_observation_index": (
            3 if program in {"BIRTH", "REACTIVATE", "RELINK", "RETRACT", "REPLACE"}
            else None
        ),
        "terminal_reobservation_indices": [4, 5],
        "split_merge_artifact_plan": artifact,
    }
    plan["route_plan_sha256"] = _sha(plan)
    return plan


def _receipt(plan, *, hidden_state="occluded"):
    phase_pose = {
        0: plan["planned_poses"]["precondition"],
        1: plan["planned_poses"]["precondition"],
        2: plan["planned_poses"]["challenge"],
        3: plan["planned_poses"]["challenge"],
        4: plan["planned_poses"]["reobservation"],
        5: plan["planned_poses"]["reobservation"],
    }
    states = ["visible", "visible", hidden_state, hidden_state,
              "reobserved", "reobserved"]

    def assessment(state):
        if state == "out_of_view":
            projected, unoccluded, support, terminal = 0, 0, None, False
        elif state == "occluded":
            projected, unoccluded, support, terminal = 5, 0, None, False
        elif state == "reobserved":
            projected, unoccluded, support, terminal = 5, 5, ZERO_SHA, True
        else:
            projected, unoccluded, support, terminal = 5, 5, ZERO_SHA, False
        return make_public_visibility_assessment(
            subject_public_ref=plan["visibility_subject_public_ref"],
            subject_reference_sealed_before_frame=True,
            projected_public_sample_count=projected,
            unoccluded_public_sample_count=unoccluded,
            current_public_support_sha256=support,
            terminal_reobservation_phase=terminal,
        )
    observations = []
    for index, state in enumerate(states):
        value = assessment(state)
        builder = _builder_receipt(value, index)
        observations.append({
            "observation_index": index,
            "visibility_assessment": value,
            "visibility_builder_receipt": builder,
            "public_evidence_sha256": builder["receipt_sha256"],
            "actual_pose": phase_pose[index],
            "registered_camera_action_success": True,
        })
    return {
        "schema_version": "vsmt-vm04-observation-route-receipt-v1",
        "route_plan_sha256": plan["route_plan_sha256"],
        "observations": observations,
    }


class ObservationRunnerTests(unittest.TestCase):
    def test_contract_is_approved_for_review_and_generation_stays_closed(self):
        record = validate_approved_contract(_contract())
        self.assertFalse(record["authorization"]["generation_authorized"])
        with self.assertRaisesRegex(
                ObservationConstructionError, "unresolved generation fields"):
            assert_generation_authorized(record)

    def test_source_pool_and_formal_count_use_only_pilot_completion(self):
        houses = [f"train:{index:06d}" for index in range(90)]
        pool = make_source_pool_manifest(
            houses, source_manifest_sha256=ZERO_SHA, selection_seed=260916)
        reversed_pool = make_source_pool_manifest(
            list(reversed(houses)), source_manifest_sha256=ZERO_SHA,
            selection_seed=260916)
        self.assertEqual(pool, reversed_pool)
        five = seal_formal_selection(
            pool, pilot_completion_by_pool_index={
                index: index < 5 for index in range(6)})
        four = seal_formal_selection(
            pool, pilot_completion_by_pool_index={
                index: index < 4 for index in range(6)})
        three = seal_formal_selection(
            pool, pilot_completion_by_pool_index={
                index: index < 3 for index in range(6)})
        self.assertEqual(five["formal_source_house_count"], 48)
        self.assertEqual(four["formal_source_house_count"], 64)
        self.assertEqual(three["formal_source_house_count"], 0)
        self.assertEqual(three["status"], "stopped_new_contract_required")
        self.assertFalse(four["CFO_history_or_oracle_inputs_used"])

    def test_public_route_projection_removes_program_and_artifact_assignment(self):
        plan = validate_route_plan(_route("SPLIT"), contract=_contract())
        public = public_route_projection(plan, contract=_contract())
        self.assertNotIn("program", public)
        self.assertNotIn("split_merge_artifact_plan", public)
        self.assertEqual(
            public["consumer_scope"],
            "construction_provenance_only_not_adapter_input")
        self.assertEqual(public["private_route_plan_sha256"],
                         plan["route_plan_sha256"])

    def test_hidden_intervention_and_terminal_window_construct(self):
        plan = _route()
        verdict = assess_route_receipt(
            _receipt(plan), plan=plan, contract=_contract())
        self.assertTrue(verdict["constructed"])
        self.assertEqual(verdict["failure_reasons"], [])
        self.assertFalse(verdict["failed_route_replacement_allowed"])

    def test_visible_intervention_is_retained_as_failure(self):
        plan = _route()
        receipt = _receipt(plan)
        value = make_public_visibility_assessment(
                subject_public_ref=plan["visibility_subject_public_ref"],
                subject_reference_sealed_before_frame=True,
                projected_public_sample_count=5,
                unoccluded_public_sample_count=5,
                current_public_support_sha256=ZERO_SHA,
                terminal_reobservation_phase=False,
            )
        builder = _builder_receipt(value, 3)
        receipt["observations"][3]["visibility_assessment"] = value
        receipt["observations"][3]["visibility_builder_receipt"] = builder
        receipt["observations"][3]["public_evidence_sha256"] = (
            builder["receipt_sha256"]
        )
        verdict = assess_route_receipt(receipt, plan=plan, contract=_contract())
        self.assertFalse(verdict["constructed"])
        self.assertIn("intervention_visible_to_camera", verdict["failure_reasons"])
        self.assertFalse(verdict["failed_route_replacement_allowed"])

    def test_visibility_state_cannot_be_self_reported_or_use_private_identity(self):
        assessment = make_public_visibility_assessment(
            subject_public_ref="public-subject:0001",
            subject_reference_sealed_before_frame=True,
            projected_public_sample_count=5,
            unoccluded_public_sample_count=0,
            current_public_support_sha256=None,
            terminal_reobservation_phase=False,
        )
        self.assertEqual(assessment["visibility_state"], "occluded")
        self.assertFalse(assessment["private_mask_or_instance_id_used"])

    def test_route_rejects_micro_motion_and_nonconsecutive_terminal_window(self):
        plan = _route()
        plan["planned_poses"]["challenge"]["x_m"] = 0.1
        plan["route_plan_sha256"] = _sha({
            key: value for key, value in plan.items()
            if key != "route_plan_sha256"
        })
        with self.assertRaisesRegex(
                ObservationConstructionError, "challenge translation"):
            validate_route_plan(plan, contract=_contract())

        plan = _route()
        plan["registered_actions"].append(
            {"step_index": 5, "action": "MoveAhead"})
        plan["phase_observation_indices"]["reobserved"] = [4, 5, 6]
        plan["terminal_reobservation_indices"] = [4, 6]
        plan["route_plan_sha256"] = _sha({
            key: value for key, value in plan.items()
            if key != "route_plan_sha256"
        })
        with self.assertRaisesRegex(
                ObservationConstructionError, "must be consecutive"):
            validate_route_plan(plan, contract=_contract())

    def test_machine_schema_is_valid_json_and_lists_all_record_types(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(len(schema["oneOf"]), 6)
        self.assertIn("privateRoutePlan", schema["$defs"])
        self.assertIn("publicRoute", schema["$defs"])

    def test_action_requests_cover_all_eight_without_force_or_defaults(self):
        requests = _action_requests()
        self.assertEqual(
            validate_registered_action_request_templates(requests), requests,
        )
        incomplete = dict(requests)
        incomplete.pop("LookDown")
        with self.assertRaisesRegex(
                ObservationConstructionError, "exactly eight"):
            validate_registered_action_request_templates(incomplete)
        forced = json.loads(json.dumps(requests))
        forced["MoveAhead"]["forceAction"] = True
        with self.assertRaisesRegex(
                ObservationConstructionError, "unexpected fields"):
            validate_registered_action_request_templates(forced)


if __name__ == "__main__":
    unittest.main()
