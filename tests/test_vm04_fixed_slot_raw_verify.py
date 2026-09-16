"""Raw digest tamper detection without semantic labels or simulator access."""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops/vsmt"))
import vm04_fixed_slot_raw_verify as verify
import vm04_fixed_slot_raw_stage as stage


class FixedSlotRawVerifyTests(unittest.TestCase):
    def task(self):
        return {"family_id": "audit-family:00", "slot": 0,
                "episode_id": "audit-episode:00", "program": "NOOP",
                "source_record_sha256": "a" * 64,
                "fixed_pose": {"position": {"x": 1.0, "y": 0.9,
                                            "z": 0.0}}}

    def frame(self, episode, index):
        public = episode / "public" / ("frame_%04d" % index)
        private = episode / "private" / ("frame_%04d" % index)
        public.mkdir(parents=True)
        private.mkdir(parents=True)
        rgb = public / "rgb.npy"
        depth = public / "depth.npy"
        mask = private / "instance_masks.npz"
        rgb.write_bytes(b"rgb" + bytes([index]))
        depth.write_bytes(b"depth" + bytes([index]))
        mask.write_bytes(b"private-mask" + bytes([index]))
        camera = public / "camera.json"
        verify.audit.write_new_json(camera, {
            "frame_index": index, "time_s": index * 0.3,
            "pose": {}, "calibration": {}, "last_action_success": True,
            "past_actions": [], "rgb_sha256": verify.audit.sha256(rgb),
            "depth_sha256": verify.audit.sha256(depth)})
        camera_sha = verify.audit.sha256(camera)
        mapping = private / "mapping.json"
        verify.audit.write_new_json(mapping, {
            "frame_index": index, "private_instance_ids": ["private:A"],
            "public_camera_sha256": camera_sha,
            "instance_masks_sha256": verify.audit.sha256(mask)})
        return {"frame_index": index, "public_camera_sha256": camera_sha,
                "private_mapping_sha256": verify.audit.sha256(mapping)}

    def terminal(self, episode, task, kind, **extra):
        path = episode / kind
        verify.audit.write_new_json(path, {
            "family_id": task["family_id"], "slot": task["slot"],
            "episode_id": task["episode_id"],
            "task_sha256": verify.audit.canonical_sha256(task),
            "source_record_sha256": task["source_record_sha256"],
            "fixed_pose_sha256":
                verify.audit.canonical_sha256(task["fixed_pose"]),
            "constructed": False, "semantic_positive_label_issued": False,
            "relink_coverage_gap": False, **extra})
        return path

    def test_complete_verifies_all_public_and_private_bytes_then_detects_tamper(self):
        with TemporaryDirectory() as temp:
            episode = Path(temp) / "episode"
            episode.mkdir()
            task = self.task()
            frames = [self.frame(episode, index) for index in range(32)]
            intervention = episode / "private/intervention.json"
            verify.audit.write_new_json(intervention, {"actions": []})
            terminal = self.terminal(
                episode, task, "raw.receipt.json",
                attempted=True, raw_complete=True, frame_count=32,
                frame_receipts=frames,
                construction_assessment_pending=True,
                private_intervention_sha256=verify.audit.sha256(intervention))
            self.assertEqual(verify.verify_slot(
                episode, task, terminal, verify.audit.sha256(terminal))[
                    "private_frames"], 32)
            leak = episode / "public/frame_0000/private_truth.json"
            leak.write_text('{"objectId":"private:A"}', encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "public frame contains"):
                verify.verify_slot(episode, task, terminal,
                                   verify.audit.sha256(terminal))
            leak.unlink()
            (episode / "private/frame_0010/instance_masks.npz").write_bytes(
                b"altered private masks")
            with self.assertRaisesRegex(RuntimeError, "private mask/mapping"):
                verify.verify_slot(episode, task, terminal,
                                   verify.audit.sha256(terminal))

    def test_failed_prefix_is_kept_and_public_tamper_is_rejected(self):
        with TemporaryDirectory() as temp:
            episode = Path(temp) / "episode"
            episode.mkdir()
            task = self.task()
            frame = self.frame(episode, 0)
            private_failure = episode / "private/construction-failure.json"
            verify.audit.write_new_json(private_failure, {"error": "private"})
            terminal = self.terminal(
                episode, task, "raw.failure.json", attempted=True,
                raw_complete=False,
                schema_version="vsmt-vm04-fixed-slot-raw-failure-v1",
                reason="simulator_or_raw_construction_failed",
                public_prefix_frame_count=1,
                public_prefix_frame_receipts=[{
                    "frame_index": 0,
                    "public_camera_sha256": frame["public_camera_sha256"],
                    "private_mapping_sha256":
                        frame["private_mapping_sha256"]}],
                private_failure_sha256=verify.audit.sha256(private_failure),
                relink_collision_observed_this_run=False)
            self.assertEqual(verify.verify_slot(
                episode, task, terminal, verify.audit.sha256(terminal))[
                    "public_frames"], 1)
            (episode / "public/frame_0000/rgb.npy").write_bytes(b"altered")
            with self.assertRaisesRegex(RuntimeError, "public RGB-D"):
                verify.verify_slot(episode, task, terminal,
                                   verify.audit.sha256(terminal))

    def test_not_started_cannot_contain_public_or_private_frames(self):
        with TemporaryDirectory() as temp:
            episode = Path(temp) / "episode"
            episode.mkdir()
            task = self.task()
            terminal = self.terminal(
                episode, task, "raw.not_started.json", attempted=False,
                raw_complete=False)
            self.assertEqual(verify.verify_slot(
                episode, task, terminal, verify.audit.sha256(terminal))[
                    "public_frames"], 0)
            (episode / "public").mkdir()
            with self.assertRaisesRegex(RuntimeError, "acquired attempted data"):
                verify.verify_slot(episode, task, terminal,
                                   verify.audit.sha256(terminal))

    def test_parent_verifies_all_36_slots_and_export_requires_marker(self):
        with TemporaryDirectory() as temp:
            output_root = Path(temp)
            reviewed_code = "f" * 40
            stage_root = stage.stage_path(output_root, reviewed_code)
            public_rows, private_rows, merge_rows = [], [], []
            for slot in range(36):
                task = {**self.task(), "slot": slot,
                        "episode_id": "audit-episode:%02d" % slot}
                key = (task["family_id"], slot)
                relative = "private/audit-family_00/slot_%02d.json" % slot
                task_path = stage_root / "tasks" / relative
                verify.audit.write_new_json(task_path, task)
                public_rows.append({"family_id": key[0], "slot": slot,
                                    "episode_id": task["episode_id"]})
                private_rows.append({**public_rows[-1],
                                     "private_task_path": relative,
                                     "private_task_sha256":
                                         verify.audit.sha256(task_path)})
                episode = stage.episode_path(stage_root, task)
                terminal = self.terminal(
                    episode, task, "raw.not_started.json",
                    attempted=False, raw_complete=False)
                merge_rows.append({"family_id": key[0], "slot": slot,
                                   "program": "NOOP",
                                   "kind": "raw.not_started.json",
                                   "terminal_sha256":
                                       verify.audit.sha256(terminal)})
            verify.audit.write_new_json(
                stage_root / "tasks/public/task-manifest.json",
                {"rows": public_rows})
            private_manifest = stage_root / "tasks/private/task-manifest.json"
            verify.audit.write_new_json(private_manifest,
                                        {"rows": private_rows})
            run = stage_root / "run.receipt.json"
            verify.audit.write_new_json(run, {
                "reviewed_code": reviewed_code,
                "terminal_slot_count": 36,
                "deterministic_merge_order": merge_rows,
                "private_task_manifest_sha256":
                    verify.audit.sha256(private_manifest),
                "requested_workers": 2, "actual_peak_workers": 2,
                "stop_reason": "resource_stop"})
            with self.assertRaisesRegex(Exception, "verify"):
                stage.export(reviewed_code, output_root,
                             output_root / "premature.json")
            with (patch.object(stage.audit, "_cgroup_memory_headroom_bytes",
                               return_value=8 * (1 << 30)),
                  patch.object(stage.resource_probe, "safe_visible_cpu_count",
                               return_value=6),
                  patch.object(stage.shutil, "disk_usage") as disk):
                disk.return_value.free = 8 * (1 << 30)
                stage.verify(reviewed_code, output_root)
                report = output_root / "raw-report.json"
                stage.export(reviewed_code, output_root, report)
                tampered_episode = stage.episode_path(stage_root, self.task())
                (tampered_episode / "public").mkdir()
                late_report = output_root / "late-report.json"
                with self.assertRaisesRegex(RuntimeError,
                                            "raw bytes changed after verify"):
                    stage.export(reviewed_code, output_root, late_report)
                self.assertFalse(late_report.exists())
                self.assertTrue((stage_root /
                    "private/export-verify-failures.json").is_file())
            receipt = verify.audit.read_json(stage_root / "verify.receipt.json")
            self.assertTrue(receipt["success"])
            self.assertEqual(receipt["requested_workers"], 6)
            self.assertEqual(len(receipt["verified_slots"]), 36)
            self.assertTrue(verify.audit.read_json(report)[
                "raw_file_digests_verified"])


if __name__ == "__main__":
    unittest.main()
