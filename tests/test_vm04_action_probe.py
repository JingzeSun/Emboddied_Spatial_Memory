"""Action-probe boundaries; no simulator or episode generation is invoked."""

import json
from pathlib import Path
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "ops/vsmt"))
import vm04_action_probe as parent  # noqa: E402
import vm04_action_probe_worker as worker  # noqa: E402


class Event:
    def __init__(self, success, error_code=None, objects=None):
        self.metadata = {
            "lastActionSuccess": success, "errorCode": error_code,
            "errorMessage": "simulated action failure" if not success else "",
            "objects": [] if objects is None else objects,
        }
        self.instance_masks = {}


class Controller:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.steps = []
        self.last_event = Event(True)
        self.stopped = False

    def step(self, **kwargs):
        self.steps.append(kwargs)
        self.last_event = self.outcomes.pop(0)
        return self.last_event

    def stop(self):
        self.stopped = True


class ActionProbeTests(unittest.TestCase):
    def test_proposed_contract_and_run_gate(self):
        value = parent.load_config()
        self.assertFalse(value["probe_execution_authorized"])
        self.assertFalse(value["generation_authorized"])
        self.assertEqual(len(value["source_public_episode_manifest_sha256"]), 64)
        self.assertEqual(len(value["source_private_episode_manifest_sha256"]), 64)
        changed = dict(value, source_public_episode_manifest_sha256="a" * 64)
        with self.assertRaisesRegex(RuntimeError, "episode plans changed"):
            parent.validate_config(changed)
        with mock.patch.object(parent, "verify_code") as verify:
            with self.assertRaisesRegex(RuntimeError, "closed pending user code review"):
                parent.run("unreviewed", Path("scan"), Path("source"), Path("out"))
            verify.assert_not_called()

    def test_approved_status_requires_reviewed_commit(self):
        value = dict(parent.load_config(), status="frozen_executable",
                     probe_execution_authorized=True)
        with self.assertRaisesRegex(RuntimeError, "exact reviewed commit"):
            parent.validate_config(value)
        value["expected_reviewed_probe_code"] = "a" * 40
        self.assertTrue(parent.validate_config(value)["probe_execution_authorized"])
        value["generation_authorized"] = True
        with self.assertRaisesRegex(RuntimeError, "never authorize generation"):
            parent.validate_config(value)

    def test_setup_action_failure_keeps_simulator_diagnostic(self):
        controller = Controller([Event(False, "object_missing")])
        status, actions, count, failure = worker.probe_intervention_path(
            controller, "BIRTH", 0, ["private-id"], {}
        )
        self.assertEqual(status, "intervention_rejected")
        self.assertEqual(count, 0)
        self.assertIsNone(failure)
        self.assertEqual(actions[0]["frame_index"], -1)
        self.assertEqual(actions[0]["diagnostic"]["error_code"], "object_missing")
        self.assertEqual(len(controller.steps), 1)

    def test_relink_missing_true_position_is_recorded_without_teleport(self):
        controller = Controller([Event(True) for _ in range(24)])
        status, actions, count, failure = worker.probe_intervention_path(
            controller, "RELINK", 0, ["private-id"],
            {"private-id": {"objectId": "private-id"}}
        )
        self.assertEqual(status, "missing_action_precondition")
        self.assertEqual(failure["frame_index"], 24)
        self.assertIn("initial position", failure["error"])
        self.assertEqual(actions, [])
        self.assertEqual(count, 24)
        self.assertEqual(len(controller.steps), 24)
        self.assertNotIn("TeleportObject", [step["action"] for step in controller.steps])

    def test_retract_replays_registered_yaw_before_frame_22(self):
        controller = Controller([Event(True) for _ in range(23)])
        status, actions, count, failure = worker.probe_intervention_path(
            controller, "RETRACT", 1, ["private-id"], {}
        )
        self.assertEqual(status, "interventions_succeeded")
        self.assertIsNone(failure)
        self.assertEqual(count, 22)
        self.assertEqual(actions[0]["frame_index"], 22)
        self.assertEqual(controller.steps[-1]["action"], "DisableObject")

    def test_reactivate_frame_16_failure_preserves_phase_and_code(self):
        controller = Controller([Event(True) for _ in range(16)] +
                                [Event(False, "disabled_not_allowed")])
        status, actions, count, failure = worker.probe_intervention_path(
            controller, "REACTIVATE", 1, ["private-id"], {}
        )
        self.assertEqual(status, "intervention_rejected")
        self.assertEqual(count, 16)
        self.assertEqual(actions[0]["frame_index"], 16)
        self.assertEqual(actions[0]["diagnostic"]["error_code"],
                         "disabled_not_allowed")
        self.assertIsNone(failure)

    def test_replace_keeps_secondary_setup_and_enable_target(self):
        controller = Controller([Event(True) for _ in range(27)])
        status, actions, count, failure = worker.probe_intervention_path(
            controller, "REPLACE", 0, ["primary-id", "secondary-id"], {}
        )
        self.assertEqual(status, "interventions_succeeded")
        self.assertEqual(count, 24)
        self.assertIsNone(failure)
        self.assertEqual(
            [(row["frame_index"], row["arguments"]["action"],
              row["arguments"]["objectId"]) for row in actions],
            [(-1, "DisableObject", "secondary-id"),
             (22, "DisableObject", "primary-id"),
             (24, "EnableObject", "secondary-id")],
        )

    def test_scan_live_target_mismatch_stops_without_intervention(self):
        controller = Controller([])
        teleported = Event(True, objects=[{"objectId": "live-id"}])
        with mock.patch.object(worker.generator, "make_controller", return_value=controller), \
             mock.patch.object(worker.generator, "teleport_to_initial_viewpoint",
                               return_value=teleported), \
             mock.patch.object(worker.generator, "rank_visible_instance_ids",
                               return_value=["live-id", "other-id"]), \
             mock.patch.object(worker, "probe_intervention_path") as path:
            result = worker.probe_slot({}, {
                "episode_id": "episode:x", "slot": 0, "program": "BIRTH", "replicate": 0,
            }, {"position": {"x": 0, "y": 0, "z": 0}},
                ["scan-id", "other-id"])
        self.assertEqual(result["status"], "scan_live_target_mismatch")
        self.assertEqual(result["actions"], [])
        self.assertTrue(controller.stopped)
        path.assert_not_called()

    def test_public_report_contains_counts_and_hash_not_private_ids(self):
        rows = [{"family_id": "audit-family:00", "program": "BIRTH",
                 "status": "intervention_rejected", "count": 36}]
        payload = parent.public_report_payload("a" * 40, "b" * 64, {
            "scan_receipt_sha256": "c" * 64, "requested_workers": 2,
            "actual_workers": 2, "worker_exits": [],
            "target_instance_ids": ["private-simulator-id"],
        }, rows)
        self.assertNotIn("private-simulator-id", json.dumps(payload))
        self.assertEqual(payload["counts_by_family_program_status"], rows)
        self.assertEqual(payload["episodes_generated"], 0)


if __name__ == "__main__":
    unittest.main()
