"""Injected-event tests for the post-D-183 multiview worker core."""

import importlib.util
import json
import numpy as np
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

PATH = ROOT / "ops" / "vsmt" / "vm04_multiview_worker.py"
SPEC = importlib.util.spec_from_file_location("vm04_multiview_worker", PATH)
worker = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(worker)

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt.vm04_observation_runner import make_public_visibility_assessment  # noqa: E402


CONTRACT = json.loads((
    ROOT / "configs/vsmt/vm04_observation_suitability_proposal_v1.json"
).read_text(encoding="utf-8"))
SHA = "0" * 64
ACTION_REQUESTS = {
    "RotateRight": {"action": "RotateRight", "degrees": 30.0},
    "MoveAhead": {"action": "MoveAhead", "moveMagnitude": 0.25},
    "MoveRight": {"action": "MoveRight", "moveMagnitude": 0.25},
}


def _sha(value):
    import hashlib
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _plan():
    plan = {
        "schema_version": "vsmt-vm04-observation-route-plan-v1",
        "episode_id": "episode:worker",
        "program": "RELINK",
        "branch_type": "natural_occlusion_then_reobservation",
        "visibility_subject_kind": "target_track",
        "visibility_subject_public_ref": "subject:0001",
        "initial_pose": {"x_m": 0.0, "y_m": 0.9, "z_m": 0.0,
                         "yaw_deg": 0.0},
        "registered_actions": [
            {"step_index": index, "action": action}
            for index, action in enumerate([
                "RotateRight", "MoveAhead", "MoveAhead", "MoveRight", "MoveRight"
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
        "intervention_after_observation_index": 3,
        "terminal_reobservation_indices": [4, 5],
        "split_merge_artifact_plan": None,
    }
    plan["route_plan_sha256"] = _sha(plan)
    return plan


class Event:
    def __init__(self, pose, success=True):
        self.metadata = {
            "lastActionSuccess": success,
            "fov": 90.0,
            "agent": {
                "position": {"x": pose[0], "y": 0.9, "z": 0.0},
                "rotation": {"x": 0.0, "y": pose[1], "z": 0.0},
            },
            "objects": [{"objectId": "private|object"}],
        }
        self.frame = np.zeros((2, 3, 3), dtype=np.uint8)
        self.depth_frame = np.ones((2, 3), dtype=np.float32)
        self.instance_masks = {
            "private|object": np.ones((2, 3), dtype=np.uint8),
        }


class Controller:
    def __init__(self, fail_action_call=None):
        self.calls = []
        self.fail_action_call = fail_action_call
        self.poses = [(0.0, 0.0), (0.0, 0.0), (0.25, 30.0),
                      (0.5, 30.0), (0.75, 0.0), (1.0, 0.0)]

    def step(self, **request):
        self.calls.append(request)
        index = len(self.calls) - 1
        return Event(self.poses[index], success=index != self.fail_action_call)


def _extract_public_frame(event, observation_index):
    return {
        "rgb": b"rgb",
        "depth_m": (1.0,),
        "camera": {"projection": "public"},
        "source_frame_sha256": SHA,
        "private_fields_removed": True,
    }


def _capture(hidden_visible=False, seen_frames=None):
    states = ["visible", "visible", "occluded", "occluded",
              "reobserved", "reobserved"]
    if hidden_visible:
        states[3] = "visible"

    def capture(frame, index, subject_ref, terminal):
        if seen_frames is not None:
            seen_frames.append(frame)
        assert set(frame) == worker.PUBLIC_FRAME_KEYS
        assert "metadata" not in frame
        state = states[index]
        if state == "occluded":
            projected, unoccluded, support = 5, 0, None
        elif state == "reobserved":
            projected, unoccluded, support = 5, 5, SHA
        else:
            projected, unoccluded, support = 5, 5, SHA
        return {
            "visibility_assessment": make_public_visibility_assessment(
                subject_public_ref=subject_ref,
                subject_reference_sealed_before_frame=True,
                projected_public_sample_count=projected,
                unoccluded_public_sample_count=unoccluded,
                current_public_support_sha256=support,
                terminal_reobservation_phase=terminal,
            ),
            "public_evidence_sha256": SHA,
        }
    return capture


class MultiviewWorkerTests(unittest.TestCase):
    def test_complete_route_intervenes_only_after_hidden_public_seal(self):
        controller = Controller()
        interventions = []
        seen_frames = []
        result = worker._execute_route_core(
            controller, plan=_plan(), contract=CONTRACT,
            action_request_templates=ACTION_REQUESTS,
            trusted_public_frame_extractor=_extract_public_frame,
            public_capture=_capture(seen_frames=seen_frames),
            private_intervention=lambda event, route: (
                interventions.append(len(controller.calls)) or
                {"success": True, "private_id_exported": False}
            ),
        )
        self.assertEqual(result["status"], "raw_complete")
        self.assertEqual(interventions, [4])
        self.assertEqual(len(controller.calls), 6)
        self.assertEqual(controller.calls[0]["action"], "TeleportFull")
        self.assertEqual(len(seen_frames), 6)
        self.assertTrue(all("objects" not in frame for frame in seen_frames))

    def test_visible_intervention_stops_before_private_action(self):
        controller = Controller()
        interventions = []
        result = worker._execute_route_core(
            controller, plan=_plan(), contract=CONTRACT,
            action_request_templates=ACTION_REQUESTS,
            trusted_public_frame_extractor=_extract_public_frame,
            public_capture=_capture(hidden_visible=True),
            private_intervention=lambda event, route: interventions.append(True) or {},
        )
        self.assertEqual(result["status"], "raw_failure")
        self.assertEqual(result["reason"], "intervention_visible_to_camera")
        self.assertEqual(interventions, [])
        self.assertEqual(len(result["public_observation_prefix"]), 4)

    def test_failed_camera_action_keeps_prefix_and_does_not_continue(self):
        controller = Controller(fail_action_call=2)
        result = worker._execute_route_core(
            controller, plan=_plan(), contract=CONTRACT,
            action_request_templates=ACTION_REQUESTS,
            trusted_public_frame_extractor=_extract_public_frame,
            public_capture=_capture(), private_intervention=lambda event, route: {},
        )
        self.assertEqual(result["reason"], "registered_camera_action_failed")
        self.assertEqual(len(result["public_observation_prefix"]), 3)
        self.assertEqual(len(controller.calls), 3)

    def test_production_wrapper_refuses_before_controller_use(self):
        controller = Controller()
        with tempfile.TemporaryDirectory() as temporary:
            episode_root = Path(temporary) / "must-not-be-created"
            with self.assertRaisesRegex(
                    worker.ObservationConstructionError,
                    "unresolved generation fields"):
                worker.run_authorized_route(
                    controller, plan=_plan(), contract=CONTRACT,
                    episode_root=episode_root,
                    public_capture=_capture(),
                    private_intervention=lambda event, route: {},
                )
            self.assertFalse(episode_root.exists())
        self.assertEqual(controller.calls, [])

    def test_artificially_authorized_wrapper_persists_complete_episode(self):
        contract = json.loads(json.dumps(CONTRACT))
        contract["status"] = "d183_frozen_executable"
        contract["authorization"]["trajectory_implementation_authorized"] = True
        contract["authorization"]["generation_authorized"] = True
        contract["observation_trajectory"][
            "registered_action_request_templates"] = ACTION_REQUESTS
        contract["crosswalk_provenance"][
            "expected_materializer_code_sha256"] = "1" * 64
        contract["crosswalk_provenance"][
            "expected_materializer_config_sha256"] = "2" * 64
        contract["public_packet_materialization"][
            "decision_time_rule"] = "test_observation_index_seconds"
        contract["public_packet_materialization"][
            "action_command_encoding"] = {
                "id": "test_one_hot_v1", "dimension": 8,
            }
        numeric = contract["l2_identifiability_admission_gate"][
            "numeric_review_required_before_generation"]
        numeric["CFO_and_public_history_probe_architecture"] = {"test": True}
        numeric["shared_probe_training_budget"] = {"test": True}
        construction = contract["deterministic_SPLIT_MERGE_construction"]
        construction["fresh_replay_repeat_count"] = 1
        construction["exact_geometry_parameters"] = {"test": True}
        construction["frozen_frontend_artifact_criteria"] = {"test": True}
        controller = Controller()
        with tempfile.TemporaryDirectory() as temporary:
            episode_root = Path(temporary) / "episode"
            result = worker.run_authorized_route(
                controller, plan=_plan(), contract=contract,
                episode_root=episode_root, public_capture=_capture(),
                private_intervention=lambda event, route: {
                    "success": True, "private_id_exported": False,
                },
            )
            self.assertEqual(result["worker_result"]["status"], "raw_complete")
            self.assertEqual(result["raw_receipt"]["frame_count"], 6)
            self.assertTrue((episode_root / "public/raw.manifest.json").is_file())
            self.assertTrue((episode_root / "private/raw.manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
