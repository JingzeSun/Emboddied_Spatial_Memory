"""The ruling-49 window audit's model-free parts: the container mask lookup, the ruling-35
invisible rule over per-frame unoccluded counts, the three-way comparison (stored, control,
corrected) and its outcome categories, the stage report, and an end-to-end episode on a synthetic
two-frame episode where the control reproduces what "generation" stored.  No simulator, no models.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT / "src", PROJECT_ROOT / "ops" / "vsmt"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import lean_s1_02_window_audit as audit  # noqa: E402
import lean_s1_02a_pilot as pilot  # noqa: E402
from vsmt import lean_public_pose as pp  # noqa: E402

S1_03_CONTRACT_PATH = PROJECT_ROOT / "configs" / "vsmt" / "lean_s1_03_frontend_cache_v1.json"
S1_04_CONTRACT_PATH = PROJECT_ROOT / "configs" / "vsmt" / "lean_s1_04_frontend_diagnostics_v1.json"
SIZE = 224


def policy() -> dict:
    return json.loads(S1_03_CONTRACT_PATH.read_text(encoding="utf-8"))["public_pose_correction"]


class MaskAndRuleTests(unittest.TestCase):
    def test_container_mask_follows_the_label_mapping_and_is_none_when_absent(self) -> None:
        labels = np.zeros((8, 8), dtype=np.uint16)
        labels[2:6, 2:6] = 3
        record = {"object_id_to_entity_id": {"Fridge|1": 3, "Mug|2": 4}}
        mask = audit.container_mask(record, labels, "Fridge|1")
        self.assertEqual(int(mask.sum()), 16)
        self.assertEqual(int(audit.container_mask(record, labels, "Mug|2").sum()), 0)
        self.assertIsNone(audit.container_mask(record, labels, "Chair|9"))

    def test_the_invisible_rule_needs_every_frame_to_be_zero(self) -> None:
        counts = {"a": [0, 0, 0], "b": [0, 1, 0], "c": [0], "d": []}
        self.assertEqual(audit.invisible_from_counts(counts), ["a", "c"])  # d has no frame: not a verdict

    def test_rendered_pixels_sum_the_simulators_own_visibility_over_the_window(self) -> None:
        records = [{"object_visibility": {"Fridge|1": 0, "Bed|2": 12}},
                   {"object_visibility": {"Fridge|1": 5}},
                   {"object_visibility": {}}]
        totals = audit.rendered_pixels_in_window(records, ["Fridge|1", "Bed|2", "Sink|3"])
        self.assertEqual(totals, {"Fridge|1": 5, "Bed|2": 12, "Sink|3": 0})

    def test_the_comparison_separates_the_control_check_from_the_finding(self) -> None:
        same = audit.compare_sets(["a", "b"], ["b", "a"], ["a", "b"])
        self.assertTrue(same["control_reproduces_generation"])
        self.assertFalse(same["verdicts_change"])
        changed = audit.compare_sets(["a", "b"], ["a", "b"], ["a", "c"])
        self.assertTrue(changed["control_reproduces_generation"])
        self.assertTrue(changed["verdicts_change"])
        self.assertEqual((changed["corrected_adds"], changed["corrected_removes"]), (["c"], ["b"]))
        broken = audit.compare_sets(["a", "b"], ["a"], ["a"])
        self.assertFalse(broken["control_reproduces_generation"])
        self.assertEqual(broken["stored_only"], ["b"])


class StageReportTests(unittest.TestCase):
    def test_the_report_counts_outcomes_and_never_calls_a_change_a_correction(self) -> None:
        results = [
            {"episode_id": "e1", "status": "succeeded", "outcome": "agrees", "verdicts_change": False,
             "control_reproduces_generation": True, "corrected_adds": [], "corrected_removes": [],
             "stored_u_size": 3, "corrected_u_size": 3, "stored_u_rendered_count": 0, "corrected_u_rendered_count": 0},
            {"episode_id": "e2", "status": "succeeded", "outcome": "verdicts_differ", "verdicts_change": True,
             "control_reproduces_generation": True, "corrected_adds": ["Fridge|1"], "corrected_removes": [],
             "stored_u_size": 5, "corrected_u_size": 6, "stored_u_rendered_count": 2, "corrected_u_rendered_count": 1},
            {"episode_id": "e3", "status": "failed", "outcome": "no_window", "detail": "window is null"},
        ]
        report = audit.stage_report(results, commit="c" * 40, requested_workers=4, actual_workers=3,
                                    worker_basis="test", wall_seconds=2.0)
        self.assertEqual(report["episodes_audited"], 2)
        self.assertEqual(report["episodes_by_outcome"]["verdicts_differ"], 1)
        self.assertEqual(report["episodes_by_outcome"]["no_window"], 1)
        self.assertEqual(report["control_reproduced_generation"], 2)
        self.assertEqual(report["episodes_with_changed_verdicts"], [{"episode_id": "e2", "adds": ["Fridge|1"], "removes": []}])
        self.assertEqual(report["containers_added_by_correction"], 1)
        self.assertEqual((report["stored_u_total"], report["corrected_u_total"]), (8, 9))
        self.assertEqual(report["stored_u_containers_the_simulator_rendered"], 2)
        self.assertEqual(report["corrected_u_containers_the_simulator_rendered"], 1)
        self.assertEqual(len(report["failures"]), 1)
        self.assertTrue(report["reads_only"] and report["modifies_no_generated_file"])
        self.assertIn("never a correction applied here", report["note"])

    def test_every_outcome_name_is_registered(self) -> None:
        self.assertEqual(audit.OUTCOMES, ("agrees", "verdicts_differ", "control_mismatch", "no_window", "episode_unreadable"))
        with self.assertRaises(AssertionError):
            audit.AuditFailure("some_other_outcome")


def write_episode(root: Path, episode_id: str, *, stored_invisible: list[str], yaw_of_frame1: float = 0.0) -> Path:
    """Two frames: the container fills a patch at 2 m; frame 1 may look from another yaw."""

    from PIL import Image

    episode = root / episode_id
    for plane in ("public", "private", "provenance"):
        (episode / plane).mkdir(parents=True)
    (episode / "receipt.json").write_text(json.dumps({"status": "succeeded", "code_commit": policy()["applies_to_s1_02_code_commits"][0]}))
    for index, yaw in enumerate((0.0, yaw_of_frame1)):
        # the pre-ruling encoder: Ry(yaw) * Rx(-pitch) with the agent looking down 30 degrees
        import math
        rotation = np.array([[math.cos(math.radians(yaw)), 0, math.sin(math.radians(yaw))],
                             [0, 1, 0], [-math.sin(math.radians(yaw)), 0, math.cos(math.radians(yaw))]]) @ pp.rotation_x(-math.radians(30.0))
        quaternion = pp.quaternion_xyzw_from_rotation(rotation)
        depth = np.full((SIZE, SIZE), 2.0, dtype=np.float32)
        np.save(episode / "public" / f"{index:04d}.depth.npy", depth)
        (episode / "public" / f"{index:04d}.frame.json").write_text(json.dumps({
            "observation_index": index, "rgb_path": f"{index:04d}.rgb.png", "depth_path": f"{index:04d}.depth.npy",
            "intrinsics": pilot.intrinsics(),
            "relative_pose": {"position_m": [0.0, 0.0, 0.0], "quaternion_xyzw": quaternion, "origin": "observation_0_camera"},
            "action_summary": {}, "frame_digest": f"{index:064d}".replace("0", "a", 1)[:64] or "a" * 64}))
        labels = np.zeros((SIZE, SIZE), dtype=np.uint16)
        labels[40:180, 40:180] = 1  # far above the 512 px subject floor
        Image.fromarray(labels).save(episode / "private" / f"{index:04d}.instance.png", format="PNG")
        (episode / "private" / f"{index:04d}.frame.json").write_text(json.dumps({
            "observation_index": index, "instance_mask_path": f"{index:04d}.instance.png",
            "object_id_to_entity_id": {"Fridge|1": 1}, "object_poses": {"Fridge|1": {"x": 0.0, "y": 0.0, "z": 2.0}},
            "object_visibility": {"Fridge|1": int((labels == 1).sum())}, "frame_digest": "a" * 64}))
    (episode / "provenance" / "window_verdicts.json").write_text(json.dumps({
        "window": [0, 1], "frames": 1, "invisible": stored_invisible,
        "subjects": {"Fridge|1": {"frame": 0, "pixels": int(140 * 140), "sealed": True}}, "verdicts": []}))
    return episode


class EpisodeAuditTests(unittest.TestCase):
    def _task(self, episode: Path, out: Path) -> dict:
        return {"episode_id": episode.name, "episode_root": str(episode), "out": str(out), "commit": "d" * 40,
                "episode_code_commit": policy()["applies_to_s1_02_code_commits"][0], "pose_policy": policy()}

    def test_same_yaw_the_control_reproduces_generation_and_the_correction_changes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # the container is visible in the window frame, so generation recorded it as not invisible
            episode = write_episode(root, "procthor10k-0.1.2-train-00001", stored_invisible=[], yaw_of_frame1=0.0)
            receipt = audit.audit_episode(self._task(episode, root / "out" / "e1"))
            self.assertEqual(receipt["status"], "succeeded", receipt)
            self.assertTrue(receipt["control_reproduces_generation"], receipt)
            # within one yaw the pitch error cancels between sealing and projecting: no change
            self.assertFalse(receipt["verdicts_change"], receipt)
            self.assertEqual(receipt["outcome"], "agrees")
            report = json.loads((root / "out" / "e1" / "window_audit.json").read_text(encoding="utf-8"))
            self.assertEqual(report["comparison"]["corrected_adds"], [])
            self.assertIs(report["pose_correction_applied"], True)

    def test_a_stored_verdict_the_audit_cannot_reproduce_is_reported_as_a_control_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # generation "recorded" the container invisible although it is plainly visible
            episode = write_episode(root, "procthor10k-0.1.2-train-00002", stored_invisible=["Fridge|1"], yaw_of_frame1=0.0)
            receipt = audit.audit_episode(self._task(episode, root / "out" / "e2"))
            self.assertEqual(receipt["status"], "succeeded", receipt)
            self.assertFalse(receipt["control_reproduces_generation"])
            self.assertEqual(receipt["outcome"], "control_mismatch")

    def test_an_episode_without_a_window_is_a_registered_failure_not_a_finding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            episode = write_episode(root, "procthor10k-0.1.2-train-00003", stored_invisible=[])
            (episode / "provenance" / "window_verdicts.json").write_text(json.dumps({"window": None}))
            receipt = audit.audit_episode(self._task(episode, root / "out" / "e3"))
            self.assertEqual((receipt["status"], receipt["outcome"]), ("failed", "no_window"))
            (episode / "provenance" / "window_verdicts.json").unlink()
            receipt = audit.audit_episode(self._task(episode, root / "out" / "e3b"))
            self.assertEqual(receipt["outcome"], "no_window")


class GuardTests(unittest.TestCase):
    def test_the_bits_this_audit_needs_are_open_by_name(self) -> None:
        contract = json.loads(S1_04_CONTRACT_PATH.read_text(encoding="utf-8"))
        for name in audit.REQUIRED_AUTHORIZATION:
            self.assertIs(contract["authorization"][name], True, name)
            self.assertIn(name, contract["activation_policy"]["active_true_authorizations"])


if __name__ == "__main__":
    unittest.main()
