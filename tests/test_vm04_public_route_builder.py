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
    scans = [
        {
            "pose_id": f"pose:{index}",
            "pose": {"x_m": xs[index], "y_m": 0.9, "z_m": 0.0,
                     "yaw_deg": yaws[index]},
            "visibility_assessment": _assessment(state),
            "public_evidence_sha256": f"{index:x}" * 64,
            "scan_phase": "pre_intervention_public_route_scan",
            "support_role": (
                "pre_intervention_public_subject_or_locus_not_post_action_confirmation"
            ),
            "future_or_action_outcome_used": False,
        }
        for index, state in enumerate(states)
    ]
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
            pose_scans=scans, edges=edges, split_merge_artifact_plan=None,
            contract=CONTRACT,
        )
        second = build_route_plan_from_public_graph(
            episode_id="episode:002", program="BIND",
            branch_type="out_of_view_then_reobservation",
            visibility_subject_public_ref="subject:0001",
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
                pose_scans=scans, edges=edges, split_merge_artifact_plan=None,
                contract=CONTRACT,
            )


if __name__ == "__main__":
    unittest.main()
