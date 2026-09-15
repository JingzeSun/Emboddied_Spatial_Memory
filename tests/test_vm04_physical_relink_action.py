"""Physical RELINK endpoint must use the original collision-gated request."""

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops/vsmt"))
import vm04_physical_relink_action as action


class Event:
    def __init__(self, position, success=True, error="", moving=False):
        self.metadata = {"lastActionSuccess": success,
            "errorMessage": error,
            "objects": [{"objectId": "private-mug",
                         "position": dict(position), "isMoving": moving}]}


class PhysicalRelinkActionTests(unittest.TestCase):
    def setUp(self):
        self.contract = action.validate_contract(json.loads((ROOT /
            "configs/vsmt/vm04_physical_relink_endpoint_contract_v1.json").read_text()))
        self.initial = {"position": {"x": 1.0, "y": 0.8, "z": 2.0},
                        "pickupable": True, "moveable": False}
        self.registered = {"action": "TeleportObject",
            "objectId": "private-mug", "position": {"x": 1.5, "y": 0.8, "z": 2.0},
            "rotation": {"x": 0, "y": 0, "z": 0}, "forceAction": True}

    def test_request_changes_only_force_and_refuses_target_endpoint_substitution(self):
        request = action.nonforced_original_request(
            self.registered, self.initial, self.contract)
        self.assertEqual(request, dict(self.registered, forceAction=False))
        with self.assertRaisesRegex(RuntimeError, r"frozen x\+0.5"):
            action.nonforced_original_request(dict(
                self.registered, position={"x": 1.6, "y": 0.8, "z": 2.0}),
                self.initial, self.contract)
        with self.assertRaisesRegex(RuntimeError, "movable authored asset"):
            action.nonforced_original_request(self.registered, dict(
                self.initial, pickupable=False), self.contract)

    def test_collision_rejection_is_original_slot_failure_with_no_memory_label(self):
        message = "private-mug is colliding with private-chair after teleport."
        verdict = action.endpoint_verdict(
            self.registered, Event(self.initial["position"],
                                   success=False, error=message),
            None, self.contract)
        self.assertEqual(verdict["status"],
                         "simulator_endpoint_collision_rejected")
        self.assertTrue(verdict["simulator_final_pose_collision_reported"])
        self.assertFalse(verdict["memory_history_checked"])
        self.assertFalse(verdict["semantic_positive_label_issued"])

    def test_action_success_still_requires_real_settled_terminal_position(self):
        requested = self.registered["position"]
        accepted = action.endpoint_verdict(
            self.registered, Event(requested), Event(requested), self.contract)
        self.assertEqual(accepted["status"],
                         "simulator_nonforced_endpoint_accepted_and_real_poststate_matches")
        mismatch = action.endpoint_verdict(self.registered,
            Event(requested), Event({"x": 1.45, "y": 0.8, "z": 1.99}),
            self.contract)
        self.assertEqual(mismatch["status"],
                         "simulator_endpoint_poststate_mismatch")
        immediate_mismatch = action.endpoint_verdict(
            self.registered, Event({"x": 1.45, "y": 0.8, "z": 1.99}),
            Event(requested), self.contract)
        self.assertEqual(immediate_mismatch["status"],
                         "simulator_endpoint_poststate_mismatch")
        moving = action.endpoint_verdict(self.registered,
            Event(requested), Event(requested, moving=True), self.contract)
        self.assertEqual(moving["status"], "simulator_endpoint_unsettled")
        self.assertFalse(accepted["robot_manipulation_path_reachability_checked"])

    def test_contract_cannot_silently_open_generation_or_force_action(self):
        for change in ({"generation_authorized": True}, {"force_action": True},
                       {"terminal_real_position_tolerance_m": 0.05}):
            with self.assertRaisesRegex(RuntimeError, "scope/gate changed"):
                action.validate_contract(dict(self.contract, **change))


if __name__ == "__main__":
    unittest.main()
