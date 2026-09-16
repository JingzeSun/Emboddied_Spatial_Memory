"""Tests for deterministic public-only VM-04 route search."""

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
    make_public_visibility_assessment,
)
from vsmt.vm04_public_route_builder import (  # noqa: E402
    build_route_plan_from_public_graph,
)


CONTRACT = json.loads((
    ROOT / "configs/vsmt/vm04_observation_suitability_proposal_v1.json"
).read_text(encoding="utf-8"))
SHA = "0" * 64
SUBJECT_SHA = "a" * 64
VISIBILITY_CONFIG_SHA = "b" * 64


def _sha(value):
    import hashlib
    from cpmt.hashing import canonical_json
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


def _assessment(state):
    if state == "out_of_view":
        projected, unoccluded, support = 0, 0, None
    elif state == "occluded":
        projected, unoccluded, support = 5, 0, None
    else:
        projected, unoccluded, support = 5, 5, SHA
    return make_public_visibility_assessment(
        subject_public_ref="subject:0001",
        subject_reference_sealed_before_frame=True,
        projected_public_sample_count=projected,
        unoccluded_public_sample_count=unoccluded,
        current_public_support_sha256=support,
        terminal_reobservation_phase=False,
    )


def _graph(hidden="occluded", *, short_translation=False):
    states = ["visible", "visible", hidden, hidden, "visible", "visible"]
    xs = [0.0, 0.0, 0.25, 0.1 if short_translation else 0.5, 0.75, 1.0]
    yaws = [0.0, 0.0, 30.0, 30.0, 0.0, 0.0]
    scans = []
    for index, state in enumerate(states):
        assessment = _assessment(state)
        receipt = _builder_receipt(assessment, index)
        scans.append({
            "pose_id": f"pose:{index}",
            "pose": {"x_m": xs[index], "y_m": 0.9, "z_m": 0.0,
                     "yaw_deg": yaws[index]},
            "visibility_assessment": assessment,
            "visibility_builder_receipt": receipt,
            "current_public_depth_sha256":
                receipt["current_public_depth_sha256"],
            "camera_calibration_and_pose_sha256":
                receipt["camera_calibration_and_pose_sha256"],
            "public_evidence_sha256": receipt["receipt_sha256"],
            "scan_phase": "pre_intervention_public_route_scan",
            "support_role": (
                "pre_intervention_public_subject_or_locus_not_post_action_confirmation"
            ),
            "future_or_action_outcome_used": False,
        })
    actions = ["RotateRight", "MoveAhead", "MoveAhead", "MoveRight", "MoveRight"]
    edges = [
        {"from_pose_id": f"pose:{index}", "to_pose_id": f"pose:{index + 1}",
         "action": action}
        for index, action in enumerate(actions)
    ]
    return scans, edges


class PublicRouteBuilderTests(unittest.TestCase):
    def test_builds_shortest_registered_occlusion_route(self):
        scans, edges = _graph()
        plan = build_route_plan_from_public_graph(
            episode_id="episode:001", program="RELINK",
            branch_type="natural_occlusion_then_reobservation",
            visibility_subject_public_ref="subject:0001",
            visibility_subject_seal_sha256=SUBJECT_SHA,
            visibility_builder_config_sha256=VISIBILITY_CONFIG_SHA,
            pose_scans=scans, edges=edges, split_merge_artifact_plan=None,
            contract=CONTRACT,
        )
        self.assertEqual(len(plan["registered_actions"]), 5)
        self.assertEqual(plan["phase_observation_indices"], {
            "precondition_visible": [0, 1],
            "challenge_hidden": [2, 3],
            "reobserved": [4, 5],
        })
        self.assertEqual(plan["intervention_after_observation_index"], 3)
        self.assertEqual(plan["terminal_reobservation_indices"], [4, 5])

    def test_input_order_does_not_change_route(self):
        scans, edges = _graph("out_of_view")
        first = build_route_plan_from_public_graph(
            episode_id="episode:002", program="BIND",
            branch_type="out_of_view_then_reobservation",
            visibility_subject_public_ref="subject:0001",
            visibility_subject_seal_sha256=SUBJECT_SHA,
            visibility_builder_config_sha256=VISIBILITY_CONFIG_SHA,
            pose_scans=scans, edges=edges, split_merge_artifact_plan=None,
            contract=CONTRACT,
        )
        second = build_route_plan_from_public_graph(
            episode_id="episode:002", program="BIND",
            branch_type="out_of_view_then_reobservation",
            visibility_subject_public_ref="subject:0001",
            visibility_subject_seal_sha256=SUBJECT_SHA,
            visibility_builder_config_sha256=VISIBILITY_CONFIG_SHA,
            pose_scans=list(reversed(scans)), edges=list(reversed(edges)),
            split_merge_artifact_plan=None, contract=CONTRACT,
        )
        self.assertEqual(first, second)
        self.assertIsNone(first["intervention_after_observation_index"])

    def test_rejects_route_without_frozen_translation(self):
        scans, edges = _graph(short_translation=True)
        with self.assertRaisesRegex(
                ObservationConstructionError, "no_registered_"):
            build_route_plan_from_public_graph(
                episode_id="episode:003", program="RELINK",
                branch_type="natural_occlusion_then_reobservation",
                visibility_subject_public_ref="subject:0001",
                visibility_subject_seal_sha256=SUBJECT_SHA,
                visibility_builder_config_sha256=VISIBILITY_CONFIG_SHA,
                pose_scans=scans, edges=edges, split_merge_artifact_plan=None,
                contract=CONTRACT,
            )

    def test_private_identity_field_is_rejected_before_search(self):
        scans, edges = _graph()
        scans[0]["instance_id"] = "private-object"
        with self.assertRaisesRegex(
                ObservationConstructionError, "unexpected fields"):
            build_route_plan_from_public_graph(
                episode_id="episode:004", program="RELINK",
                branch_type="natural_occlusion_then_reobservation",
                visibility_subject_public_ref="subject:0001",
                visibility_subject_seal_sha256=SUBJECT_SHA,
                visibility_builder_config_sha256=VISIBILITY_CONFIG_SHA,
                pose_scans=scans, edges=edges, split_merge_artifact_plan=None,
                contract=CONTRACT,
            )

    def test_future_or_action_outcome_scan_is_rejected(self):
        scans, edges = _graph()
        scans[4]["future_or_action_outcome_used"] = True
        with self.assertRaisesRegex(
                ObservationConstructionError, "future or action-outcome"):
            build_route_plan_from_public_graph(
                episode_id="episode:005", program="RELINK",
                branch_type="natural_occlusion_then_reobservation",
                visibility_subject_public_ref="subject:0001",
                visibility_subject_seal_sha256=SUBJECT_SHA,
                visibility_builder_config_sha256=VISIBILITY_CONFIG_SHA,
                pose_scans=scans, edges=edges, split_merge_artifact_plan=None,
                contract=CONTRACT,
            )


if __name__ == "__main__":
    unittest.main()
