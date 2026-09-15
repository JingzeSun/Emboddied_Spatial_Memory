"""The four-slot diagnostic keeps simulator and memory conclusions separate."""

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops/vsmt"))
import vm04_relink_endpoint_two_house_probe as probe


class RelinkEndpointTwoHouseProbeTests(unittest.TestCase):
    def setUp(self):
        _, self.contract = probe.load_config()
        self.registered = {"action": "TeleportObject", "objectId": "private-mug",
                           "position": {"x": 1.5, "y": 0.8, "z": 2.0},
                           "forceAction": True}
        self.pre = {"position": {"x": 1.0, "y": 0.8, "z": 2.0},
                    "pickupable": True, "moveable": False}

    def trial(self, success, terminal=None, error=""):
        attempted = dict(self.registered, forceAction=False)
        immediate = {"position": self.registered["position"] if success else
                     self.pre["position"], "is_moving": False,
                     "last_action_success": success, "error_message": error}
        return {"status": "recorded_full_registered_path" if success else
                "simulator_action_rejected", "registered_request": self.registered,
                "attempted_request": attempted, "pre_intervention": self.pre,
                "target_object_id": "private-mug",
                "immediate_post_intervention": immediate,
                "terminal_poststate": None if terminal is None else
                    {"position": terminal, "is_moving": False,
                     "last_action_success": True, "error_message": ""}}

    def test_same_original_endpoint_collision_rejects_without_memory_claim(self):
        trial = self.trial(False,
            error="private-mug is colliding with private-chair after teleport.")
        result = probe.endpoint_record(trial, self.contract)
        self.assertEqual(result["status"], "simulator_endpoint_collision_rejected")
        self.assertTrue(result["simulator_final_pose_collision_reported"])
        self.assertFalse(result["memory_history_checked"])
        self.assertFalse(result["semantic_positive_label_issued"])

    def test_success_requires_immediate_and_terminal_real_metadata_position(self):
        terminal = self.registered["position"]
        result = probe.endpoint_record(self.trial(True, terminal), self.contract)
        self.assertEqual(result["status"],
                         "simulator_nonforced_endpoint_accepted_and_real_poststate_matches")
        mismatch = probe.endpoint_record(self.trial(True,
            {"x": 1.45, "y": 0.8, "z": 1.99}), self.contract)
        self.assertEqual(mismatch["status"], "simulator_endpoint_poststate_mismatch")

    def test_private_identity_and_original_destination_cannot_be_reselected(self):
        trial = self.trial(False)
        trial["attempted_request"] = dict(trial["attempted_request"],
                                           objectId="another-private-mug")
        with self.assertRaisesRegex(RuntimeError, "more than forceAction"):
            probe.endpoint_record(trial, self.contract)
        trial = self.trial(False)
        trial["registered_request"] = dict(trial["registered_request"],
            position={"x": 1.6, "y": 0.8, "z": 2.0})
        with self.assertRaisesRegex(RuntimeError, "more than forceAction"):
            probe.endpoint_record(trial, self.contract)

    def test_closed_execution_and_original_four_slot_scope(self):
        config = json.loads((ROOT /
            "configs/vsmt/vm04_relink_endpoint_two_house_probe_v1.json").read_text())
        self.assertFalse(config["generation_authorized"])
        self.assertFalse(config["training_authorized"])
        self.assertEqual(config["all_original_relink_slots_per_family"], 2)
        self.assertEqual(config["requested_independent_slot_workers"], 4)
        self.assertEqual(config["failure_policy"],
            "original_slot_diagnosis_no_target_pose_destination_house_reselection")


if __name__ == "__main__":
    unittest.main()
