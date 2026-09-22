"""The S1-04 object geometry reload tool's simulator-free parts: task discovery over S1-02 output
roots, the intervention/window reader, the residual checks over a synthetic episode directory, the
stage receipt, and the authorization guard.  No simulator is started here; ``reload_metadata`` is
replaced by a stub that returns what AI2-THOR's metadata would.
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

import lean_s1_04_object_geometry as tool  # noqa: E402
from vsmt import lean_object_geometry as og  # noqa: E402

CONTRACT_PATH = PROJECT_ROOT / "configs" / "vsmt" / "lean_s1_04_frontend_diagnostics_v1.json"
SIZE = 32


def xyz(x, y, z):
    return {"x": x, "y": y, "z": z}


def write_episode(root: Path, episode_id: str, *, status: str = "succeeded", with_interventions: bool = True) -> Path:
    """A two-frame synthetic episode: a chair seen at frame 0 straight ahead, a mug removed later."""

    episode = root / episode_id
    for plane in ("public", "private", "provenance"):
        (episode / plane).mkdir(parents=True)
    (episode / "receipt.json").write_text(json.dumps({"house_id": episode_id, "source_index": 7, "status": status}))
    calibration = {"fx": 16.0, "fy": 16.0, "cx": 15.5, "cy": 15.5}
    for index in range(2):
        pose = {"position_m": [0.0, 0.0, 0.0], "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0], "origin": "observation_0_camera"}
        depth = np.full((SIZE, SIZE), 2.0, dtype=np.float32)
        np.save(episode / "public" / f"{index:04d}.depth.npy", depth)
        (episode / "public" / f"{index:04d}.frame.json").write_text(json.dumps({
            "observation_index": index, "rgb_path": f"{index:04d}.rgb.png", "depth_path": f"{index:04d}.depth.npy",
            "intrinsics": calibration, "relative_pose": pose, "action_summary": {}, "frame_digest": "a" * 64}))
        labels = np.zeros((SIZE, SIZE), dtype=np.uint16)
        labels[8:24, 8:24] = 1  # the chair: 256 px, centred in the image, 2 m ahead
        from PIL import Image
        Image.fromarray(labels).save(episode / "private" / f"{index:04d}.instance.png", format="PNG")
        (episode / "private" / f"{index:04d}.frame.json").write_text(json.dumps({
            "observation_index": index, "instance_mask_path": f"{index:04d}.instance.png",
            "object_id_to_entity_id": {"Chair|1": 1},
            "object_poses": {"Chair|1": xyz(1.0, 0.0, 3.0)}, "object_visibility": {"Chair|1": 256},
            "frame_digest": "a" * 64}))
    if with_interventions:
        (episode / "provenance" / "interventions.json").write_text(json.dumps({
            "executed": [{"kind": "remove", "object_id": "Mug|2", "executed": True},
                         {"kind": "move", "object_id": "Bowl|3", "executed": False}]}))
        (episode / "provenance" / "window_verdicts.json").write_text(json.dumps({"window": [1, 1]}))
    return episode


def stub_metadata() -> dict:
    # the camera at the reload sits at world (1, 1.5, 1): the chair at world (1, 0, 3) is 2 m ahead
    return {
        "cameraPosition": xyz(1.0, 1.5, 1.0),
        "agent": {"position": xyz(1.0, 0.9, 1.0), "rotation": xyz(0.0, 0.0, 0.0), "cameraHorizon": 0.0},
        "objects": [
            {"objectId": "Chair|1", "assetId": "Chair_A", "objectType": "Chair", "pickupable": False, "receptacle": True,
             "position": xyz(1.0, 0.0, 3.0), "rotation": xyz(0, 0, 0),
             "axisAlignedBoundingBox": {"center": xyz(1.0, 1.5, 3.0), "size": xyz(2.2, 2.2, 0.4)}},
            {"objectId": "Mug|2", "assetId": "Mug_A", "objectType": "Mug", "pickupable": True, "receptacle": False,
             "position": xyz(0.0, 0.9, 0.0), "rotation": xyz(0, 0, 0),
             "axisAlignedBoundingBox": {"center": xyz(0.0, 0.95, 0.0), "size": xyz(0.1, 0.1, 0.1)}},
            {"objectId": "Bowl|3", "assetId": "Bowl_A", "objectType": "Bowl", "pickupable": True, "receptacle": False,
             "position": xyz(0.5, 0.9, 0.0), "rotation": xyz(0, 0, 0),
             "axisAlignedBoundingBox": {"center": xyz(0.5, 0.95, 0.0), "size": xyz(0.2, 0.1, 0.2)}},
        ],
    }


class TaskDiscoveryTests(unittest.TestCase):
    def test_every_receipt_is_a_task_in_a_fixed_order_including_failed_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_episode(root, "procthor10k-0.1.2-train-00002")
            write_episode(root, "procthor10k-0.1.2-train-00001", status="failed")
            tasks = tool.episode_tasks([root])
            self.assertEqual([t["episode_id"] for t in tasks],
                             ["procthor10k-0.1.2-train-00001", "procthor10k-0.1.2-train-00002"])
            self.assertEqual(tasks[0]["source_status"], "failed")
            self.assertEqual(tasks[1]["source_index"], 7)

    def test_interventions_and_window_are_read_and_a_null_episode_has_neither(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            episode = write_episode(Path(directory), "procthor10k-0.1.2-train-00002")
            executed, window = tool.read_interventions(episode / "provenance")
            self.assertEqual([r["object_id"] for r in executed], ["Mug|2"])  # the unexecuted move is dropped
            self.assertEqual(window, [1, 1])
            empty = write_episode(Path(directory), "procthor10k-0.1.2-train-00003", with_interventions=False)
            self.assertEqual(tool.read_interventions(empty / "provenance"), ([], None))


class EpisodeBuildTests(unittest.TestCase):
    def test_a_stubbed_reload_writes_the_table_and_the_residual_checks(self) -> None:
        original = tool.reload_metadata
        tool.reload_metadata = lambda *args, **kwargs: (stub_metadata(), None)
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                episode = write_episode(root, "procthor10k-0.1.2-train-00002")
                task = {"episode_id": episode.name, "episode_root": str(episode), "house_id": episode.name,
                        "source_index": 7, "source_status": "succeeded", "out": str(root / "out" / episode.name),
                        "source_root": str(root), "source_rel": "train.jsonl.gz", "commit": "deadbeef",
                        "minimum_depth_m": 0.05, "maximum_depth_m": 20.0}
                receipt = tool.build_episode(task)
                self.assertEqual(receipt["status"], "succeeded", receipt)
                table = json.loads((root / "out" / episode.name / og.TABLE_FILE_NAME).read_text(encoding="utf-8"))
                og.validate_geometry_table(table)
                self.assertEqual(table["episode_origin_world_m"], [1.0, 1.5, 1.0])
                self.assertEqual(receipt["objects"], 3)
                residual = receipt["residual"]
                self.assertEqual(residual["intervened_objects"], ["Mug|2"])
                self.assertEqual(residual["drift"]["max_drift_m"], 0.0)
                self.assertEqual(residual["frame0_containment"]["objects_checked"], 1)
                # the chair mask back-projects to z=2 m ahead of the camera in the episode frame; its truth box
                # (world centre (1,1.5,3), size 2.2 x 2.2 x 0.4, minus origin) is [-1.1,-1.1,1.8]..[1.1,1.1,2.2]
                self.assertEqual(residual["frame0_containment"]["per_object"]["Chair|1"]["inside_fraction"], 1.0)
                # a failed source episode leaves a failure receipt and no table
                failed = write_episode(root, "procthor10k-0.1.2-train-00001", status="failed")
                task2 = dict(task, episode_id=failed.name, episode_root=str(failed), house_id=failed.name,
                             source_status="failed", out=str(root / "out" / failed.name))
                receipt2 = tool.build_episode(task2)
                self.assertEqual((receipt2["status"], receipt2["reason"]), ("failed", "source_episode_not_succeeded"))
                self.assertFalse((root / "out" / failed.name / og.TABLE_FILE_NAME).exists())
                stage = tool.stage_receipt([receipt, receipt2], planned=2, commit="deadbeef", requested_workers=2,
                                           actual_workers=2, worker_basis="test", wall_seconds=1.0)
                self.assertEqual((stage["episodes_succeeded"], stage["episodes_failed"]), (1, 1))
                self.assertEqual(stage["frame0_containment_median_over_episodes"], 1.0)
                self.assertEqual(stage["episodes_with_drift_over_tolerance"], [])
        finally:
            tool.reload_metadata = original


class GuardTests(unittest.TestCase):
    def test_the_bits_were_opened_by_ruling_48_and_closing_one_refuses(self) -> None:
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(tool.blocking_authorization(contract), [])
        for name in tool.REQUIRED_AUTHORIZATION:
            self.assertIn(name, contract["activation_policy"]["active_true_authorizations"])
        closed = json.loads(json.dumps(contract))
        closed["authorization"]["object_geometry_reload"] = False
        self.assertEqual(tool.blocking_authorization(closed), ["object_geometry_reload"])

    def test_the_frozen_depth_bounds_come_from_the_bound_d223_contract(self) -> None:
        geometry = tool.frozen_fragment_geometry()
        self.assertEqual((geometry["minimum_depth_m"], geometry["maximum_depth_m"]), (0.05, 20.0))


if __name__ == "__main__":
    unittest.main()
