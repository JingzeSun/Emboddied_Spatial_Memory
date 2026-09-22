"""The S1-03 runner's model-free parts: the on-disk frame format, the episode seal over written
frames, the camera axis, and the asset check refusing a digest that does not match its registry.

The models themselves run only on the server; nothing here loads torch, SAM 2.1 or DINOv2.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT / "src", PROJECT_ROOT / "ops" / "vsmt"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import lean_s1_03_cache as runner  # noqa: E402
from vsmt import lean_frontend_cache as fc  # noqa: E402


class FrameFileTests(unittest.TestCase):
    def test_a_written_frame_decodes_to_the_object_the_seal_covers(self) -> None:
        frame = {"tick": 1, "frame_digest": "a" * 64, "fragments": [], "frame_seal": {"payload_sha256": "b" * 64},
                 "camera_position_m": [0.0, 1.5, 0.25]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / f"0000{runner.FRAME_FILE_SUFFIX}"
            path.write_bytes(gzip.compress(json.dumps(frame).encode("utf-8"), compresslevel=6))
            self.assertEqual(runner.load_cache_frame(path), frame)
            self.assertTrue(path.name.endswith(".cache.json.gz"))

    def test_episode_seal_needs_only_tick_and_frame_seal_of_each_frame(self) -> None:
        full = [{"tick": i + 1, "frame_seal": {"payload_sha256": hashlib.sha256(bytes([i])).hexdigest()},
                 "fragments": [{"x": i}], "surfaces": []} for i in range(3)]
        reduced = [{"tick": f["tick"], "frame_seal": f["frame_seal"]} for f in full]
        digest = fc.D223_FRONTEND_CONFIG_SHA256
        self.assertEqual(fc.seal_episode(full, frontend_config_sha256=digest),
                         fc.seal_episode(reduced, frontend_config_sha256=digest))


class CameraForwardTests(unittest.TestCase):
    def test_identity_rotation_looks_along_positive_z(self) -> None:
        self.assertEqual(runner.camera_forward([0.0, 0.0, 0.0, 1.0]), [0.0, 0.0, 1.0])

    def test_quarter_turn_about_y_looks_along_positive_x(self) -> None:
        half = 2 ** -0.5
        forward = runner.camera_forward([0.0, half, 0.0, half])
        self.assertAlmostEqual(forward[0], 1.0, places=9)
        self.assertAlmostEqual(forward[1], 0.0, places=9)
        self.assertAlmostEqual(forward[2], 0.0, places=9)

    def test_a_non_unit_quaternion_is_refused_at_the_frozen_tolerance(self) -> None:
        for bad in ([0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0 + 1e-5], [float("nan"), 0.0, 0.0, 1.0]):
            with self.assertRaises(runner.CacheFailure):
                runner.camera_forward(bad)
        self.assertEqual(runner.camera_forward([0.0, 0.0, 0.0, 1.0 + 1e-7]), [0.0, 0.0, 1.0])


class RegisteredNullSlotTests(unittest.TestCase):
    """Ruling 42: the supported_by thresholds stay null and do not block generation; any other
    null registered value, or the same slots once the contract stops recording the field as
    null-until-frozen, still refuses the run."""

    def setUp(self) -> None:
        self.contract = json.loads(runner.CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_the_live_contract_has_no_blocking_null_value(self) -> None:
        self.assertEqual(runner.blocking_null_slots(self.contract), [])
        self.assertEqual(len(self.contract["policy_values_without_defaults"]), 5)

    def test_the_exemption_rests_on_the_recorded_null_rule(self) -> None:
        self.contract["supported_by_rule"]["recorded_as_null_until_the_thresholds_are_frozen"] = False
        self.assertEqual(runner.blocking_null_slots(self.contract),
                         self.contract["policy_values_without_defaults"])

    def test_a_threshold_that_entered_the_features_would_block(self) -> None:
        self.contract["supported_by_rule"]["enters_association_features"] = True
        self.assertEqual(len(runner.blocking_null_slots(self.contract)), 5)

    def test_any_other_null_registered_value_blocks(self) -> None:
        self.contract["volumes"]["free_space_reliability_gate_rho_free"] = None
        self.contract["policy_values_without_defaults"].append("volumes.free_space_reliability_gate_rho_free")
        self.assertEqual(runner.blocking_null_slots(self.contract), ["volumes.free_space_reliability_gate_rho_free"])


class ResumeAndAbortTests(unittest.TestCase):
    """A resume keeps every final receipt (succeeded or failed), redoes aborted or receipt-less
    episodes, and a run that aborted or was interrupted never produces the stage receipt."""

    def _root(self, directory: str) -> Path:
        root = Path(directory)
        for episode_id, status in (("e-succ", "succeeded"), ("e-fail", "failed"), ("e-abort", "aborted")):
            (root / episode_id).mkdir()
            (root / episode_id / "receipt.json").write_text(json.dumps({"episode_id": episode_id, "status": status}))
        (root / "e-partial").mkdir()
        (root / "e-partial" / f"0000{runner.FRAME_FILE_SUFFIX}").write_bytes(b"x")
        return root

    def test_resume_keeps_final_receipts_and_redoes_the_rest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan = runner.resume_plan(self._root(directory), ["e-succ", "e-fail", "e-abort", "e-partial", "e-new"])
            self.assertEqual(plan, {"kept_succeeded": ["e-succ"], "kept_failed": ["e-fail"],
                                    "redo": ["e-abort", "e-partial", "e-new"]})

    def test_a_failed_episode_is_never_replaced_by_a_resume(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan = runner.resume_plan(self._root(directory), ["e-fail"])
            self.assertEqual(plan["redo"], [])
            self.assertEqual(plan["kept_failed"], ["e-fail"])

    def _receipt(self, results, *, planned, aborted=None, interrupted=()):
        import argparse
        args = argparse.Namespace(workers=2, worker_basis="t", trial_frame_limit=None, disk_floor_gib=2.0)
        return runner.stage_receipt(results, tasks_planned=planned, commit="c", trial=False,
                                    verified={"descriptor_asset_sha256s": {}}, args=args, actual_workers=2,
                                    snapshot={}, started=0.0, aborted=aborted, interrupted=list(interrupted))

    def test_a_complete_run_reports_exit_0_and_planned_equals_succeeded_plus_failed(self) -> None:
        rows = [{"episode_id": "a", "status": "succeeded", "frames": 2, "fragments": 3, "frames_with_fragments": 2,
                 "fragments_per_frame_histogram": {"1": 1, "2": 1}},
                {"episode_id": "b", "status": "failed", "reason": "proposal_overflow", "detail": "65"}]
        receipt = self._receipt(rows, planned=2)
        self.assertTrue(receipt["complete"])
        self.assertEqual((receipt["exit_status"], receipt["episodes_succeeded"], receipt["episodes_failed"]), (1, 1, 1))
        self.assertEqual(receipt["frames_total"], 2)
        self.assertEqual(receipt["fragments_per_frame_histogram"], {"1": 1, "2": 1})

    def test_the_stage_receipt_totals_the_masks_written_during_generation(self) -> None:
        rows = [{"episode_id": "a", "status": "succeeded", "frames": 2, "fragments": 3, "frames_with_fragments": 2,
                 "fragments_per_frame_histogram": {"1": 1, "2": 1}, "mask_bytes_written": 1200, "frames_with_masks": 2},
                {"episode_id": "b", "status": "succeeded", "frames": 1, "fragments": 1, "frames_with_fragments": 1,
                 "fragments_per_frame_histogram": {"1": 1}, "mask_bytes_written": 600, "frames_with_masks": 1}]
        receipt = self._receipt(rows, planned=2)
        self.assertEqual((receipt["mask_bytes_total"], receipt["frames_with_masks_total"]), (1800, 3))
        self.assertIs(receipt["masks_written_during_generation"], True)
        self.assertEqual(receipt["frames_with_masks_total"], receipt["frames_total"])

    def test_an_aborted_or_interrupted_run_is_not_complete_and_exits_3(self) -> None:
        rows = [{"episode_id": "a", "status": "succeeded", "frames": 2, "fragments": 0, "frames_with_fragments": 0,
                 "fragments_per_frame_histogram": {"0": 2}},
                {"episode_id": "b", "status": "aborted", "reason": "disk_floor", "detail": "free 1 bytes"}]
        receipt = self._receipt(rows, planned=3, aborted={"episode_id": "b", "reason": "disk_floor"}, interrupted=["c"])
        self.assertFalse(receipt["complete"])
        self.assertEqual(receipt["exit_status"], 3)
        self.assertEqual(receipt["interrupted_episodes"], ["c"])
        self.assertEqual(receipt["episodes_failed"], 0)
        receipt = self._receipt(rows[:1], planned=2)
        self.assertFalse(receipt["complete"])


class AssetVerificationTests(unittest.TestCase):
    """A repository at the wrong commit or a checkpoint with the wrong digest is refused before
    any model is built; the digests the frames carry come from the bytes on disk."""

    def _repository(self, directory: Path) -> str:
        subprocess.run(["git", "init", "-q", str(directory)], check=True)
        (directory / "f").write_text("x")
        env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
               "GIT_COMMITTER_EMAIL": "t@t"}
        subprocess.run(["git", "-C", str(directory), "add", "f"], check=True)
        subprocess.run(["git", "-C", str(directory), "-c", "commit.gpgsign=false", "commit", "-q", "-m", "x"],
                       check=True, env={**dict(__import__("os").environ), **env})
        return subprocess.run(["git", "-C", str(directory), "rev-parse", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()

    def test_a_sam2_repository_at_another_commit_is_refused(self) -> None:
        contract = json.loads(runner.CONTRACT_PATH.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "sam2"
            repository.mkdir()
            self._repository(repository)
            assets = {"sam2_repository": str(repository), "sam2_checkpoint": str(repository / "f"),
                      "dinov2_repository": str(repository)}
            with self.assertRaises(runner.CacheFailure) as caught:
                runner.verify_assets(assets, contract)
            self.assertIn("not the pinned commit", caught.exception.detail)

    def test_file_sha256_matches_hashlib(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "blob"
            path.write_bytes(b"\x00\x01" * 1000)
            self.assertEqual(runner.file_sha256(path), hashlib.sha256(b"\x00\x01" * 1000).hexdigest())


class Ruling49Tests(unittest.TestCase):
    """The pose is read under the registered correction policy and --masks-from re-digests every mask."""

    def setUp(self) -> None:
        self.policy = json.loads(runner.CONTRACT_PATH.read_text(encoding="utf-8"))["public_pose_correction"]
        self.defective = self.policy["applies_to_s1_02_code_commits"][0]

    def test_causal_pose_restores_the_pitch_sign_for_a_registered_commit_and_refuses_others(self) -> None:
        from vsmt import lean_public_pose as pp
        import math
        written = pp.quaternion_xyzw_from_rotation(pp.rotation_x(-math.radians(30.0)))  # the old encoder: looks up
        record = {"relative_pose": {"position_m": [0.5, 0.0, -1.0], "quaternion_xyzw": written, "origin": "observation_0_camera"}}
        pose = runner.causal_pose(record, code_commit=self.defective, policy=self.policy)
        self.assertEqual(pose["position_m"], [0.5, 0.0, -1.0])
        self.assertAlmostEqual(runner.camera_forward(pose["quaternion_xyzw"])[1], -0.5, places=9)
        self.assertAlmostEqual(runner.camera_forward(written)[1], 0.5, places=9)
        with self.assertRaises(runner.CacheFailure) as caught:
            runner.causal_pose(record, code_commit="0" * 40, policy=self.policy)
        self.assertIn("episode_code_commit_not_registered", caught.exception.detail)

    def test_recovered_masks_are_re_digested_from_pixels_and_shape_checked(self) -> None:
        import numpy as np
        rng = np.random.default_rng(49)
        masks = [rng.random((20, 30)) > 0.5 for _ in range(3)]
        shas = [fc.mask_sha256_of(m) for m in masks]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / f"0000{runner.MASK_FILE_SUFFIX}"
            runner.write_masks_file(path, masks, shas, shape=(20, 30))
            back = runner.recovered_masks(path, (20, 30))
            self.assertEqual(len(back), 3)
            for original, restored in zip(masks, back):
                np.testing.assert_array_equal(original, restored)
            with self.assertRaises(runner.CacheFailure):
                runner.recovered_masks(path, (30, 20))
            with self.assertRaises(runner.CacheFailure):
                runner.recovered_masks(Path(directory) / f"0001{runner.MASK_FILE_SUFFIX}", (20, 30))
            # a mask changed on disk while its stored digest stays: refused
            tampered = [masks[0], ~masks[1], masks[2]]
            runner.write_masks_file(path, tampered, shas, shape=(20, 30))
            with self.assertRaises(runner.CacheFailure) as caught:
                runner.recovered_masks(path, (20, 30))
            self.assertIn("do not reproduce", caught.exception.detail)
            # an empty frame round-trips to no masks
            empty = Path(directory) / f"0002{runner.MASK_FILE_SUFFIX}"
            runner.write_masks_file(empty, [], [], shape=(20, 30))
            self.assertEqual(runner.recovered_masks(empty, (20, 30)), [])


if __name__ == "__main__":
    unittest.main()
