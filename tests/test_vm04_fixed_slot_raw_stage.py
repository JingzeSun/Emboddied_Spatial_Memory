"""Raw stage dispatch capacity and terminal not-started boundary."""

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops/vsmt"))
import vm04_fixed_slot_raw_stage as stage


class FixedSlotRawStageTests(unittest.TestCase):
    def test_isolated_simulator_versions_must_match_existing_contract(self):
        contract = {"environment_separation": {"simulator_process": {
            "python": "3.9.25", "packages": {
                "ai2thor": "5.0.0", "procthor": "0.0.1.dev2"}}}}
        installed = {"python": "3.9.25", "ai2thor": "5.0.0",
                     "procthor": "0.0.1.dev2"}
        with patch.object(stage.subprocess, "check_output",
                          return_value=json.dumps(installed)):
            self.assertEqual(stage.verify_simulator_environment(
                Path("/exact/simulator/bin/python"), contract), installed)
        installed["ai2thor"] = "5.1.0"
        with patch.object(stage.subprocess, "check_output",
                          return_value=json.dumps(installed)):
            with self.assertRaisesRegex(RuntimeError, "versions differ"):
                stage.verify_simulator_environment(
                    Path("/exact/simulator/bin/python"), contract)

    def test_current_config_rejects_generation_before_any_stage_output(self):
        with TemporaryDirectory() as temp, patch.object(stage, "bound_code",
                                                    return_value={}):
            root = Path(temp)
            with self.assertRaisesRegex(RuntimeError, "gate remain closed"):
                stage.run("f" * 40, root / "scan", root / "endpoint",
                          root / "source", root)
            self.assertEqual(list(root.iterdir()), [])

    def test_chooses_maximum_safe_worker_count_from_sampled_demand(self):
        gib = 1 << 30
        self.assertEqual(stage.safe_worker_count(
            16, 20 * gib, 3 * gib, 16 * gib, 2 * gib,
            4 * gib, 4 * gib, 4), 4)
        self.assertEqual(stage.safe_worker_count(
            16, 10 * gib, 3 * gib, 16 * gib, 2 * gib,
            4 * gib, 4 * gib, 4), 2)
        self.assertEqual(stage.safe_worker_count(
            16, 6 * gib, 3 * gib, 16 * gib, 2 * gib,
            4 * gib, 4 * gib, 4), 0)
        with self.assertRaisesRegex(RuntimeError, "demand is missing"):
            stage.safe_worker_count(8, 20 * gib, 0, 16 * gib, 2 * gib,
                                    4 * gib, 4 * gib, 4)

    def test_not_started_retains_original_slot_once(self):
        task = {"family_id": "audit-family:01", "slot": 12,
                "episode_id": "audit-episode:original", "program": "RELINK",
                "source_record_sha256": "a" * 64,
                "family_viewpoints_sha256": "b" * 64,
                "fixed_pose": {"position": {"x": 1.0, "y": 0.9,
                                            "z": 0.0}}}
        with TemporaryDirectory() as temp:
            root = Path(temp)
            stage.not_started(root, task, "sampled_capacity_insufficient")
            path = stage.episode_path(root, task) / "raw.not_started.json"
            row = json.loads(path.read_text())
            self.assertFalse(row["attempted"])
            self.assertFalse(row["constructed"])
            self.assertTrue(row["relink_coverage_gap"])
            self.assertNotIn("target_instance_ids", path.read_text())
            with self.assertRaisesRegex(RuntimeError, "cannot mark attempted"):
                stage.not_started(root, task, "retry")

    def test_crashed_process_retains_existing_public_prefix_digest(self):
        task = {"family_id": "audit-family:00", "slot": 4,
                "episode_id": "audit-episode:original", "program": "RELINK",
                "source_record_sha256": "a" * 64,
                "family_viewpoints_sha256": "b" * 64,
                "fixed_pose": {"position": {"x": 1.0, "y": 0.9,
                                            "z": 0.0}}}
        with TemporaryDirectory() as temp:
            episode = stage.episode_path(Path(temp), task)
            camera = episode / "public/frame_0000/camera.json"
            stage.audit.write_new_json(camera, {"frame_index": 0,
                                                "rgb_sha256": "c" * 64})
            terminal = stage._terminal_after_exit(episode, task, 137)
            failure = json.loads(terminal.read_text())
            self.assertEqual(failure["public_prefix_frame_count"], 1)
            self.assertEqual(failure["public_prefix_camera_sha256"],
                             [stage.audit.sha256(camera)])
            self.assertTrue(failure["relink_coverage_gap"])
            self.assertEqual(stage._terminal_after_exit(episode, task, 137),
                             terminal)


if __name__ == "__main__":
    unittest.main()
