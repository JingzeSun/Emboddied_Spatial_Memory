"""Public seal, pre-registered branches and action/actual-state boundaries."""

import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops/vsmt"))
import vm04_relink_interaction_runner as runner


def event(*, agent_x=0.0, success=True, picked=False, parent=None,
          object_x=0.0, error=None, pickupable=False):
    class Snapshot:
        pass
    value = Snapshot()
    value.metadata = {
        "agent": {"position": {"x": agent_x, "y": 0.9, "z": 0.0},
                  "rotation": {"y": 0.0}},
        "objects": [
            {"objectId": "fixed-target", "position":
             {"x": object_x, "y": 0.9, "z": 0.0}, "isMoving": False,
             "isPickedUp": picked, "parentReceptacles": parent or [],
             "pickupable": pickupable, "moveable": not pickupable},
            {"objectId": "fixed-receptacle", "position":
             {"x": 0.0, "y": 0.9, "z": 0.0}, "isMoving": False,
             "isPickedUp": False, "parentReceptacles": [],
             "receptacle": True}],
        "lastActionSuccess": success, "errorMessage": error, "errorCode": None}
    value.instance_masks = {"fixed-receptacle": bytes([1, 1, 0, 0]),
                            "fixed-target": bytes([0, 0, 1, 1])}
    return value


class FakeController:
    def __init__(self, outcomes, *, pickupable=False, agent_x=0.0):
        self.last_event = event(pickupable=pickupable, agent_x=agent_x)
        self.outcomes = iter(outcomes)
        self.requests = []

    def step(self, **request):
        self.requests.append(request)
        return next(self.outcomes)


class InteractionRunnerTests(unittest.TestCase):
    def setUp(self):
        self.public_mask = bytes([1, 1, 0, 0])
        self.public_regions = [{"region_id": "r2", "semantic_type": "receptacle",
                                "evidence_source": "public_current_rgb_depth",
                                "mask_sha256": hashlib.sha256(
                                    self.public_mask).hexdigest(),
                                "reliability": 0.8}]
        self.reachable = [{"x": 0.0, "y": 0.9, "z": 0.0}]
        self.sealed = runner.freeze_public_plan(
            self.reachable[0], 0.0, [0.0, 0.9, 0.0], self.reachable,
            self.public_regions, snap_tolerance_m=0.02)

    def test_independent_force_ladder_is_nonadaptive_and_counts_all_branches(self):
        value = runner.force_prereg()
        self.assertEqual(value["force_ladder_newtons"], [20.0, 80.0, 160.0])
        self.assertEqual(value["expected_force_branches"], 3 * 2 * 3)
        self.assertFalse(value["probe_authorized"])
        self.assertIsNone(runner.pinned_api_spec()["real_smoke_receipt_sha256"])

    def test_public_receptacle_is_sealed_before_private_mapping_and_ignores_outcome(self):
        second = runner.freeze_public_plan(
            self.reachable[0], 0.0, [0.0, 0.9, 0.0], self.reachable,
            list(reversed(self.public_regions)), snap_tolerance_m=0.02)
        self.assertEqual(self.sealed, second)
        self.assertNotIn("fixed-receptacle", json.dumps(self.sealed))
        self.assertEqual(runner.private_receptacle_mapping(
            self.sealed, {"r2": "fixed-receptacle"}), "fixed-receptacle")
        for mapping in ({"another-region": "fixed-receptacle"},
                        {"r2": "fixed-receptacle", "another": "winner"}):
            with self.assertRaises(ValueError):
                runner.private_receptacle_mapping(self.sealed, mapping)
        mutated = copy.deepcopy(self.sealed)
        mutated["plan"]["receptacle"]["region_id"] = "another-region"
        with self.assertRaisesRegex(ValueError, "not sealed"):
            runner.private_receptacle_mapping(mutated, {"another-region": "winner"})
        self.assertEqual(runner.map_sealed_public_mask_to_private_id(
            self.sealed, self.public_mask,
            {"fixed-receptacle": bytes([1, 1, 0, 0]),
             "other": bytes([0, 0, 1, 1])}),
            {"r2": "fixed-receptacle"})
        with self.assertRaisesRegex(ValueError, "no unique"):
            runner.map_sealed_public_mask_to_private_id(
                self.sealed, self.public_mask,
                {"one": bytes([1, 0, 0, 0]),
                 "two": bytes([0, 1, 0, 0])})

    def test_generic_surface_and_private_metadata_cannot_choose_put_target(self):
        with self.assertRaisesRegex(ValueError, "no public typed receptacle"):
            runner.public_receptacle_choice([{"region_id": "s1",
                                              "structure_kind": "surface"}])
        row = dict(self.public_regions[0], objectId="private-receptacle")
        with self.assertRaisesRegex(ValueError, "private identity"):
            runner.public_receptacle_choice([row])

    def test_push_records_return_success_even_when_actual_displacement_is_zero(self):
        controller = FakeController([event(success=True, object_x=0.0)])
        with patch.object(runner.design, "load_proposal",
                          return_value={"probe_authorized": True}):
            result = runner.execute_fixed_branch(
                controller, self.sealed, target_id="fixed-target",
                receptacle_mapping=None, modality="push", force_newtons=80.0,
                agent_pose_tolerance_m=0.02)
        self.assertEqual(result["status"], "actions_recorded_no_memory_verdict")
        self.assertEqual(result["displacement_m"]["x"], 0.0)
        self.assertEqual(controller.requests[0], {"action": "PushObject",
            "objectId": "fixed-target", "moveMagnitude": 80.0,
            "forceAction": False})
        self.assertFalse(result["semantic_positive_label_issued"])

    def test_pickup_put_uses_preselected_private_mapping_and_checks_parent(self):
        controller = FakeController([
            event(picked=True, pickupable=True),
            event(picked=False, parent=["fixed-receptacle"], pickupable=True)],
            pickupable=True)
        with patch.object(runner.design, "load_proposal",
                          return_value={"probe_authorized": True}):
            result = runner.execute_fixed_branch(
                controller, self.sealed, target_id="fixed-target",
                receptacle_mapping={"r2": "fixed-receptacle"},
                modality="pickup_put", force_newtons=None,
                agent_pose_tolerance_m=0.02,
                public_receptacle_mask_bytes=self.public_mask)
        self.assertEqual(result["status"], "actions_recorded_no_memory_verdict")
        self.assertEqual(controller.requests[0]["manualInteract"], False)
        self.assertEqual(controller.requests[1]["objectId"], "fixed-receptacle")
        self.assertTrue(controller.requests[1]["placeStationary"])
        rejected = FakeController([event(picked=True, pickupable=True),
                                   event(picked=False, pickupable=True)],
                                  pickupable=True)
        with patch.object(runner.design, "load_proposal",
                          return_value={"probe_authorized": True}):
            result = runner.execute_fixed_branch(
                rejected, self.sealed, target_id="fixed-target",
                receptacle_mapping={"r2": "fixed-receptacle"},
                modality="pickup_put", force_newtons=None,
                agent_pose_tolerance_m=0.02,
                public_receptacle_mask_bytes=self.public_mask)
        self.assertEqual(result["status"], "put_parent_or_pickup_state_mismatch")

    def test_real_branch_entry_is_closed_before_first_action(self):
        controller = FakeController([event()])
        with self.assertRaisesRegex(ValueError, "real interaction probe is closed"):
            runner.execute_fixed_branch(
                controller, self.sealed, target_id="fixed-target",
                receptacle_mapping=None, modality="push", force_newtons=80.0,
                agent_pose_tolerance_m=0.02)
        self.assertEqual(controller.requests, [])

    def test_actual_start_pose_mismatch_preserves_branch_before_any_action(self):
        controller = FakeController([event()], agent_x=0.1)
        with patch.object(runner.design, "load_proposal",
                          return_value={"probe_authorized": True}):
            result = runner.execute_fixed_branch(
                controller, self.sealed, target_id="fixed-target",
                receptacle_mapping=None, modality="push", force_newtons=20.0,
                agent_pose_tolerance_m=0.02)
        self.assertEqual(result["status"], "navigation_real_start_pose_mismatch")
        self.assertEqual(controller.requests, [])

    def test_api_smoke_does_not_conflate_action_success_with_target_parent(self):
        success = FakeController([
            event(picked=True), event(picked=False, parent=["fixed-receptacle"])])
        result = runner.putobject_api_smoke(
            success, "fixed-target", "fixed-receptacle")
        self.assertEqual(result["status"], "target_receptacle_parameter_confirmed")
        failed = FakeController([event(success=False, error="too far")])
        result = runner.putobject_api_smoke(
            failed, "fixed-target", "fixed-receptacle")
        self.assertEqual(result["status"], "smoke_action_rejected_inconclusive")
        self.assertEqual(result["actions"][0]["diagnostic"]["error_message"],
                         "too far")


if __name__ == "__main__":
    unittest.main()
