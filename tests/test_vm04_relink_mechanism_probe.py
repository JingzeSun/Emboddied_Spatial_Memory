"""Original-slot RELINK controls keep target/pose fixed and export no identity."""

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops/vsmt"))
sys.path.insert(0, str(ROOT / "src"))
import vm04_relink_mechanism_probe as probe


class Event:
    def __init__(self, position, success=True):
        self.instance_masks = {"secret-asset": [[1]]}
        self.metadata = {"lastActionSuccess": success, "errorCode": None,
            "errorMessage": None, "isSceneAtRest": True,
            "objects": [{"objectId": "secret-asset", "objectType": "Mug",
                "position": dict(position), "pickupable": True,
                "moveable": False, "isMoving": False}]}


class FakeController:
    def __init__(self):
        self.position = {"x": 1.0, "y": 0.8, "z": 2.0}
        self.actions = []
        self.stopped = False

    def step(self, **kwargs):
        self.actions.append(kwargs)
        if kwargs["action"] == "TeleportObject":
            if not kwargs["forceAction"]:
                return Event(self.position, success=False)
            self.position = dict(kwargs["position"])
        return Event(self.position)

    def stop(self):
        self.stopped = True


class RelinkMechanismProbeTests(unittest.TestCase):
    def test_only_original_fixed_scope_is_authorized_and_no_generation(self):
        config, contract = probe.load_config()
        self.assertEqual(config["fixed_slot"], 12)
        self.assertEqual(config["fixed_family_id"], "audit-family:01")
        self.assertFalse(config["generation_authorized"])
        self.assertFalse(config["training_authorized"])
        self.assertEqual(contract["status"], "frozen_target_probe_only")
        with patch.object(probe.audit, "read_json", side_effect=lambda path:
                          dict(config, fixed_slot=13) if path == probe.CONFIG_PATH
                          else json.loads(probe.TARGET_PATH.read_text())):
            with self.assertRaisesRegex(RuntimeError, "scope/gate/source changed"):
                probe.load_config()

    def test_registered_action_replay_and_independent_controls(self):
        initial = {"secret-asset": {"position": {"x": 1.0, "y": 0.8, "z": 2.0},
                                    "rotation": {"x": 0, "y": 0, "z": 0}}}
        registered = probe.generator.intervention_actions(
            "RELINK", 24, ["secret-asset"], initial)[0]
        original = {"slot": 12, "replicate": 1,
                    "v3_target_instance_ids": ["secret-asset"],
                    "live_scan_top2_instance_ids": ["secret-asset", "other"],
                    "actions": [{"phase": "external_intervention",
                                 "frame_index": 24, "arguments": registered}]}
        contract = json.loads(probe.TARGET_PATH.read_text())
        for mode, expected_success in (("registered_forced", True),
                                       ("same_request_nonforced", False),
                                       ("registered_forced_physics_paused", True)):
            controller = FakeController()
            with patch.object(probe.generator, "make_controller",
                              return_value=controller), patch.object(
                probe.generator, "teleport_to_initial_viewpoint",
                return_value=Event(initial["secret-asset"]["position"])), patch.object(
                probe.generator, "rank_visible_instance_ids",
                return_value=["secret-asset", "other"]), patch.object(
                probe, "authored_asset_ids", return_value={"secret-asset"}), patch.object(
                probe, "select_private_targets_at_fixed_pose",
                return_value=["secret-asset"]):
                trial = probe.execute_trial({}, {}, original,
                    ["secret-asset", "other"], contract, mode)
            self.assertTrue(controller.stopped)
            self.assertEqual(trial["attempted_request"]["objectId"],
                             "secret-asset")
            self.assertEqual(trial["intervention_diagnostic"][
                "last_action_success"], expected_success)
            self.assertEqual(sum(action["action"] == "TeleportObject"
                                 for action in controller.actions), 1)
            self.assertEqual(sum(action["action"] in ("RotateRight", "RotateLeft")
                                 for action in controller.actions),
                             32 if expected_success else 24)
            if mode == "registered_forced_physics_paused":
                self.assertEqual(sum(action["action"] == "PausePhysicsAutoSim"
                                     for action in controller.actions), 1)
            else:
                self.assertFalse(any(action["action"] == "PausePhysicsAutoSim"
                                     for action in controller.actions))

    def test_resource_demand_and_public_summary_fail_closed_and_hide_ids(self):
        safe, demand = probe.resource_gate(20, 18, 8, 4.0, 8)
        self.assertTrue(safe)
        self.assertEqual(demand, 2)
        self.assertFalse(probe.resource_gate(20, 18, 7, 4.0, 8)[0])
        self.assertFalse(probe.resource_gate(20, 20, 20, 4.0, 8)[0])
        self.assertFalse(probe.resource_gate(None, 18, 20, 4.0, 8)[0])
        trial = {"mode": "registered_forced", "status": "recorded_full_registered_path",
            "target_object_id": "secret-asset",
            "registered_request": {"position": {"x": 1.5, "y": 0.8, "z": 2.0}},
            "immediate_post_intervention": {
                "position": {"x": 1.45, "y": 0.8, "z": 1.99}},
            "terminal_poststate": {"position": {"x": 1.45, "y": 0.8, "z": 1.99}}}
        summary = probe.anonymous_trial_summary(trial)
        self.assertEqual(summary["immediate_delta_xyz_m"],
                         {"x": -0.05, "y": 0.0, "z": -0.01})
        self.assertNotIn("secret", str(summary))
        self.assertFalse(summary["collision_or_reachability_verified"])
        self.assertFalse(summary["memory_history_checked"])


if __name__ == "__main__":
    unittest.main()
