"""Fixed-slot v3 probe checks simulator capability without semantic labels."""

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops/vsmt"))
sys.path.insert(0, str(ROOT / "src"))
import vm04_target_action_probe_worker as probe
import vm04_two_house_worker as generator


def mask(top, left):
    return [[top <= row < top + 14 and left <= column < left + 14
             for column in range(28)] for row in range(28)]


class FakeEvent:
    def __init__(self, objects, masks, *, success=True, code=None):
        self.instance_masks = dict(masks)
        self.metadata = {
            "objects": [dict(value, objectId=key) for key, value in objects.items()],
            "lastActionSuccess": success, "errorCode": code,
            "errorMessage": "registered rejection" if not success else "",
        }


class FakeController:
    def __init__(self, *, fail_action=None, invisible_after_enable=None,
                 visible_names=None, disable_without_hiding=False,
                 teleport_without_moving=False, reappear_on_camera=None):
        self.initial_objects = {
            "wall": {"position": {"x": 0.0, "y": 0.0, "z": 0.0}},
            "painting": {"position": {"x": 1.0, "y": 0.0, "z": 0.0}},
            "chair": {"position": {"x": 2.0, "y": 0.0, "z": 0.0},
                      "moveable": True},
            "mug": {"position": {"x": 3.0, "y": 0.0, "z": 0.0},
                    "pickupable": True},
        }
        all_masks = {"wall": mask(0, 0), "painting": mask(0, 14),
                     "chair": mask(14, 0), "mug": mask(14, 14)}
        names = set(all_masks) if visible_names is None else set(visible_names)
        self.objects = {key: dict(value) for key, value in
                        self.initial_objects.items()}
        self.masks = {key: value for key, value in all_masks.items()
                      if key in names}
        self.all_masks = all_masks
        self.fail_action = fail_action
        self.invisible_after_enable = invisible_after_enable
        self.disable_without_hiding = disable_without_hiding
        self.teleport_without_moving = teleport_without_moving
        self.reappear_on_camera = reappear_on_camera
        self.calls = []
        self.stopped = False
        self.last_event = self.event()

    def event(self, *, success=True, code=None):
        return FakeEvent(self.objects, self.masks, success=success, code=code)

    def step(self, **action):
        self.calls.append(action)
        name = action["action"]
        if name == self.fail_action:
            self.last_event = self.event(success=False, code="FAKE_REJECTED")
            return self.last_event
        if name == "DisableObject":
            target = action["objectId"]
            if not self.disable_without_hiding:
                self.objects.pop(target, None)
                self.masks.pop(target, None)
        elif name == "EnableObject":
            target = action["objectId"]
            self.objects[target] = dict(self.initial_objects[target])
            if target != self.invisible_after_enable:
                self.masks[target] = self.all_masks[target]
        elif name == "TeleportObject":
            if not self.teleport_without_moving:
                self.objects[action["objectId"]]["position"] = dict(action["position"])
        elif name in {"RotateRight", "RotateLeft"} and self.reappear_on_camera:
            target = self.reappear_on_camera
            if target not in self.masks:
                self.objects[target] = dict(self.initial_objects[target])
                self.masks[target] = self.all_masks[target]
        self.last_event = self.event()
        return self.last_event

    def stop(self):
        self.stopped = True


class TargetActionProbeWorkerTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads((
            ROOT / "configs/vsmt/vm04_target_boundary_proposal_v3.json"
        ).read_text(encoding="utf-8"))
        self.house = {"objects": [{"id": "painting"}, {"id": "chair"},
                                  {"id": "mug"}],
                      "walls": [{"id": "wall"}]}

    def run_slot(self, program, controller=None):
        controller = controller or FakeController()
        initial = controller.event()
        scan_top2 = generator.rank_visible_instance_ids(
            initial.instance_masks, set(probe.metadata_objects(initial)))[:2]
        assignment = {"episode_id": "sample", "slot": 0,
                      "program": program, "replicate": 0}
        with patch.object(generator, "make_controller", return_value=controller), \
             patch.object(generator, "teleport_to_initial_viewpoint",
                          return_value=initial):
            result = probe.probe_slot(
                self.house, assignment, {"pose": "fixed"}, scan_top2,
                self.contract, relink_tolerance_m=0.005)
        return result, controller

    def test_static_birth_is_action_and_visibility_only(self):
        result, controller = self.run_slot("BIRTH")
        self.assertEqual(result["v3_target_instance_ids"], ["painting"])
        self.assertEqual(result["status"],
                         "visibility_action_terminal_verified_memory_unchecked")
        self.assertFalse(result["memory_history_checked"])
        self.assertFalse(result["semantic_positive_label_issued"])
        self.assertEqual(result["agent_action_count"], 32)
        self.assertEqual(result["actions"][-1]["phase"],
                         "registered_camera_action")
        self.assertEqual(result["actions"][-1]["frame_index"], 31)
        self.assertEqual([row["arguments"]["action"] for row in result["actions"]
                          if row["phase"] == "external_intervention"],
                         ["DisableObject", "EnableObject"])
        self.assertTrue(controller.stopped)

    def test_rejected_setup_action_keeps_code_and_attempt(self):
        result, _ = self.run_slot(
            "BIRTH", FakeController(fail_action="DisableObject"))
        self.assertEqual(result["status"], "intervention_rejected")
        self.assertEqual(result["actions"][0]["frame_index"], -1)
        self.assertEqual(result["actions"][0]["diagnostic"]["error_code"],
                         "FAKE_REJECTED")

    def test_action_success_without_terminal_visibility_is_failure(self):
        result, _ = self.run_slot(
            "BIRTH", FakeController(invisible_after_enable="painting"))
        self.assertEqual(result["status"], "terminal_poststate_mismatch")
        self.assertEqual(result["terminal_target_states"][0]
                         ["visible_mask_pixels"], 0)
        self.assertFalse(result["semantic_positive_label_issued"])

    def test_disable_success_with_visible_mask_is_rejected_immediately(self):
        result, _ = self.run_slot(
            "BIRTH", FakeController(disable_without_hiding=True))
        self.assertEqual(result["status"], "intervention_poststate_mismatch")
        self.assertEqual(result["actions"][0]["frame_index"], -1)
        self.assertTrue(result["actions"][0]["diagnostic"]
                        ["last_action_success"])
        self.assertEqual(result["actions"][0]["target_poststate"][0]
                         ["visible_mask_pixels"], 196)

    def test_disabled_mask_reappearing_during_camera_path_fails_original_slot(self):
        result, _ = self.run_slot(
            "BIRTH", FakeController(reappear_on_camera="painting"))
        self.assertEqual(result["status"],
                         "disabled_target_reappeared_between_actions")
        self.assertEqual(result["actions"][-1]["frame_index"], 0)
        self.assertEqual(result["actions"][-1]["target_poststate"][0]
                         ["visible_mask_pixels"], 196)

    def test_physical_relink_uses_movable_asset_and_records_force_limit(self):
        result, _ = self.run_slot("RELINK")
        self.assertEqual(result["v3_target_instance_ids"], ["chair"])
        self.assertEqual(result["status"],
                         "relink_forced_action_terminal_verified_collision_unchecked")
        edit = [row for row in result["actions"]
                if row["phase"] == "external_intervention"]
        self.assertEqual(len(edit), 1)
        self.assertTrue(edit[0]["arguments"]["forceAction"])
        self.assertFalse(result["terminal_target_states"][0]
                         ["collision_or_reachability_checked"])

    def test_forced_teleport_success_without_position_change_is_failure(self):
        result, _ = self.run_slot(
            "RELINK", FakeController(teleport_without_moving=True))
        self.assertEqual(result["status"], "terminal_poststate_mismatch")
        self.assertEqual(result["terminal_target_states"][0]
                         ["planned_position"]["x"], 2.5)
        self.assertEqual(result["terminal_target_states"][0]
                         ["position"]["x"], 2.0)

    def test_reactivate_frame_16_rejection_retains_private_diagnostic(self):
        result, _ = self.run_slot(
            "REACTIVATE", FakeController(fail_action="DisableObject"))
        self.assertEqual(result["status"], "intervention_rejected")
        rejected = result["actions"][-1]
        self.assertEqual(rejected["frame_index"], 16)
        self.assertEqual(rejected["diagnostic"]["error_code"], "FAKE_REJECTED")

    def test_retract_frame_22_rejection_retains_private_diagnostic(self):
        result, _ = self.run_slot(
            "RETRACT", FakeController(fail_action="DisableObject"))
        self.assertEqual(result["status"], "intervention_rejected")
        self.assertEqual(result["actions"][-1]["frame_index"], 22)

    def test_replace_preserves_both_registered_lifecycle_edits(self):
        result, _ = self.run_slot("REPLACE")
        self.assertEqual(result["v3_target_instance_ids"],
                         ["painting", "chair"])
        self.assertEqual(result["status"],
                         "visibility_action_terminal_verified_memory_unchecked")
        edits = [(row["frame_index"], row["arguments"]["action"],
                  row["arguments"]["objectId"])
                 for row in result["actions"]
                 if row["phase"] == "external_intervention"]
        self.assertEqual(edits, [(-1, "DisableObject", "chair"),
                                 (22, "DisableObject", "painting"),
                                 (24, "EnableObject", "chair")])

    def test_fixed_slot_shortage_does_not_substitute_architecture(self):
        result, _ = self.run_slot(
            "RELINK", FakeController(visible_names={"wall", "painting"}))
        self.assertEqual(result["status"],
                         "fixed_slot_target_eligibility_failed")
        self.assertEqual(result["v3_target_instance_ids"], [])
        self.assertEqual(result["actions"], [])

    def test_nonintervention_does_not_create_controller_or_private_target(self):
        with patch.object(generator, "make_controller",
                          side_effect=AssertionError("unexpected controller")):
            result = probe.probe_slot(
                self.house, {"episode_id": "sample", "slot": 1,
                             "program": "MERGE", "replicate": 0},
                {"pose": "fixed"}, ["wall", "painting"], self.contract,
                relink_tolerance_m=0.005)
        self.assertEqual(result["status"],
                         "non_intervention_public_region_out_of_probe_scope")
        self.assertEqual(result["v3_target_instance_ids"], [])

    def test_scene_mismatch_stops_before_selecting_new_asset(self):
        controller = FakeController()
        assignment = {"episode_id": "sample", "slot": 0,
                      "program": "RELINK", "replicate": 0}
        with patch.object(generator, "make_controller", return_value=controller), \
             patch.object(generator, "teleport_to_initial_viewpoint",
                          return_value=controller.event()):
            result = probe.probe_slot(
                self.house, assignment, {"pose": "fixed"},
                ["painting", "wall"], self.contract,
                relink_tolerance_m=0.005)
        self.assertEqual(result["status"], "scan_live_scene_mismatch")
        self.assertEqual(result["v3_target_instance_ids"], [])
        self.assertEqual(controller.calls, [])


if __name__ == "__main__":
    unittest.main()
