"""Manual physics advances are explicit, finite, and private-ID free on export."""

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops/vsmt"))
sys.path.insert(0, str(ROOT / "src"))
import vm04_relink_physics_step_probe as probe
from tests.test_vm04_relink_mechanism_probe import Event, FakeController


class PhysicsController(FakeController):
    def step(self, **kwargs):
        if kwargs["action"] == "AdvancePhysicsStep":
            self.actions.append(kwargs)
            self.position["x"] = min(self.position["x"], 1.45)
            return Event(self.position)
        return super().step(**kwargs)


class RelinkPhysicsStepTests(unittest.TestCase):
    def test_physics_contract_uses_original_fixed_slot_only(self):
        config = probe.load_config()
        self.assertEqual(config["fixed_slot"], 12)
        self.assertEqual(config["replicas"], 2)
        self.assertEqual(config["manual_physics_steps_per_replica"], 50)
        self.assertFalse(config["generation_authorized"])
        self.assertFalse(config["training_authorized"])
        original_read = probe.audit.read_json
        with patch.object(probe.audit, "read_json", side_effect=lambda path:
                          dict(config, replicas=1) if path == probe.CONFIG_PATH
                          else original_read(path)):
            with self.assertRaisesRegex(RuntimeError, "scope/gate/source changed"):
                probe.load_config()

    def test_paused_replay_advances_physics_and_reports_only_deltas(self):
        initial = {"secret-asset": {"position": {"x": 1.0, "y": 0.8, "z": 2.0},
                                    "rotation": {"x": 0, "y": 0, "z": 0}}}
        registered = probe.generator.intervention_actions(
            "RELINK", 24, ["secret-asset"], initial)[0]
        original = {"slot": 12, "replicate": 1,
            "v3_target_instance_ids": ["secret-asset"],
            "live_scan_top2_instance_ids": ["secret-asset", "other"],
            "actions": [{"phase": "external_intervention",
                         "frame_index": 24, "arguments": registered}]}
        controller = PhysicsController()
        contract = json.loads(probe.base.TARGET_PATH.read_text())
        with patch.object(probe.base.generator, "make_controller",
                          return_value=controller), patch.object(
            probe.base.generator, "teleport_to_initial_viewpoint",
            return_value=Event(initial["secret-asset"]["position"])), patch.object(
            probe.base.generator, "rank_visible_instance_ids",
            return_value=["secret-asset", "other"]), patch.object(
            probe.base, "authored_asset_ids", return_value={"secret-asset"}), patch.object(
            probe.base, "select_private_targets_at_fixed_pose",
            return_value=["secret-asset"]):
            trial = probe.base.execute_trial({}, {}, original,
                ["secret-asset", "other"], contract,
                "registered_forced_physics_paused", physics_step_count=50)
        trial["replica"] = 0
        self.assertEqual(trial["status"], "recorded_full_registered_path")
        self.assertEqual(len(trial["manual_physics_steps"]), 50)
        self.assertEqual(sum(action["action"] == "AdvancePhysicsStep"
                             for action in controller.actions), 50)
        summary = probe.replica_summary(trial)
        self.assertEqual(summary["initial_paused_delta_xyz_m"],
                         {"x": 0.0, "y": 0.0, "z": 0.0})
        self.assertEqual(summary["first_changed_step_index"], 0)
        self.assertEqual(summary["last_step_delta_xyz_m"]["x"], -0.05)
        self.assertNotIn("secret", str(summary))
        self.assertFalse(summary["memory_history_checked"])


if __name__ == "__main__":
    unittest.main()
