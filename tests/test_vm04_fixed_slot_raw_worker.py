"""New raw slot writes complete or failed files without private ID leakage."""

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops/vsmt"))
import vm04_fixed_slot_raw_worker as worker


class Event:
    def __init__(self):
        self.metadata = {"lastActionSuccess": True, "errorMessage": None,
                         "agent": {"position": {"x": 0.0, "y": 0.9,
                                                 "z": 0.0},
                                   "rotation": {"x": 0, "y": 0, "z": 0},
                                   "cameraHorizon": 0},
                         "objects": [{"objectId": "private-fixed-asset",
                                      "position": {"x": 0.0, "y": 0.9, "z": 0.0},
                                      "rotation": {"x": 0, "y": 0, "z": 0}}]}
        self.instance_masks = {}
        self.frame = np.zeros((4, 4, 3), dtype=np.uint8)
        self.depth_frame = np.ones((4, 4), dtype=np.float32)


class Controller:
    def __init__(self):
        self.event = Event()
        self.requests = []
        self.stopped = False

    def step(self, **request):
        self.requests.append(request)
        return self.event

    def stop(self):
        self.stopped = True


def fake_capture(event, public_dir, private_dir, index, actions, targets,
                 past_actions):
    public = public_dir / ("frame_%04d" % index)
    private = private_dir / ("frame_%04d" % index)
    worker.old.write_new_json(public / "camera.json", {
        "frame_index": index, "rgb_sha256": "a" * 64,
        "depth_sha256": "b" * 64,
        "past_actions": list(past_actions)})
    worker.old.write_new_json(private / "mapping.json", {
        "frame_index": index, "target_instance_ids": list(targets)})
    return {"frame_index": index,
            "public_camera_sha256": worker.old.sha256(public / "camera.json"),
            "private_mapping_sha256": worker.old.sha256(private / "mapping.json")}


class FixedSlotRawWorkerTests(unittest.TestCase):
    def setUp(self):
        self.house = {"objects": []}
        self.task = {"schema_version": "vsmt-vm04-fixed-slot-raw-task-v1",
                     "family_id": "audit-family:00", "slot": 0,
                     "source_house_id": "train:004270",
                     "episode_id": "fixed-episode-00", "program": "NOOP",
                     "replicate": 0, "fixed_pose": {"position":
                         {"x": 0.0, "y": 0.9, "z": 0.0},
                         "rotation_y_degrees": 0,
                         "horizon_degrees": 0, "standing": True},
                     "family_viewpoints_sha256": "c" * 64,
                     "source_record_sha256":
                         worker.old.canonical_sha256(self.house),
                     "source_locator": {"relative_path": "train.jsonl.gz"},
                     "target_contract_sha256":
                         worker.old.sha256(worker.TARGET_CONTRACT),
                     "semantic_positive_label_issued": False,
                     "endpoint_failure_evidence": None}

    def _run(self, task):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        output = Path(temp.name) / "episode"
        controller = Controller()
        with patch.object(worker.old, "teleport_to_initial_viewpoint",
                          return_value=controller.event):
            result = worker.run_slot(
                self.house, task, output, 10000000,
                make_controller=lambda _: controller,
                capture_frame=fake_capture)
        return output, result, controller

    def test_nonintervention_writes_32_public_frames_with_no_private_target(self):
        output, result, controller = self._run(self.task)
        self.assertTrue(controller.stopped)
        self.assertTrue(result["raw_complete"])
        self.assertFalse(result["constructed"])
        self.assertEqual(result["frame_count"], 32)
        self.assertEqual(len(list((output / "public").glob("frame_*/camera.json"))), 32)
        self.assertEqual(len(list((output / "private").glob("frame_*/mapping.json"))), 32)
        self.assertEqual(json.loads((output / "private/intervention.json").read_text())[
            "target_instance_ids"], [])
        self.assertNotIn("private-fixed-asset", (output / "raw.receipt.json").read_text())
        self.assertNotIn("private-fixed-asset", (output / "public/frame_0000/camera.json").read_text())
        with self.assertRaisesRegex(ValueError, "output exists"):
            worker.run_slot(self.house, self.task, output, 10000000,
                            make_controller=lambda _: Controller(),
                            capture_frame=fake_capture)

    def test_actual_file_writer_produces_rgb_depth_masks_and_camera(self):
        with TemporaryDirectory() as temp:
            output = Path(temp) / "episode"
            controller = Controller()
            with patch.object(worker.old, "teleport_to_initial_viewpoint",
                              return_value=controller.event):
                result = worker.run_slot(
                    self.house, self.task, output, 10000000,
                    make_controller=lambda _: controller)
            self.assertTrue(result["raw_complete"])
            self.assertEqual(np.load(output / "public/frame_0000/rgb.npy").shape,
                             (4, 4, 3))
            self.assertEqual(np.load(output / "public/frame_0000/depth.npy").shape,
                             (4, 4))
            with np.load(output / "private/frame_0000/instance_masks.npz") as masks:
                self.assertEqual(masks["masks"].shape, (0, 4, 4))
            public = (output / "public/frame_0000/camera.json").read_text()
            private = (output / "private/frame_0000/mapping.json").read_text()
            self.assertNotIn("private-fixed-asset", public)
            self.assertIn("private-fixed-asset", private)

    def test_registered_relink_failure_keeps_24_frame_prefix_and_no_force_action(self):
        task = dict(self.task, program="RELINK", slot=4,
                    endpoint_failure_evidence={
                        "family_id": "audit-family:00", "slot": 4,
                        "status": "simulator_endpoint_collision_rejected",
                        "target_object_id": "private-fixed-asset",
                        "private_slot_sha256": "d" * 64,
                        "endpoint_receipt_sha256": worker.old.read_json(
                            worker.STAGE_CONFIG)[
                                "source_d173_endpoint_receipt_sha256"]})
        with patch.object(worker, "private_targets",
                          return_value=["private-fixed-asset"]):
            output, result, controller = self._run(task)
        self.assertFalse(result["raw_complete"])
        self.assertEqual(result["reason"], "registered_relink_endpoint_collision")
        self.assertEqual(result["public_prefix_frame_count"], 24)
        self.assertEqual(len(list((output / "public").glob("frame_*/camera.json"))), 24)
        self.assertEqual(len(list((output / "private").glob("frame_*/mapping.json"))), 24)
        self.assertFalse(any(row["action"] == "TeleportObject"
                             for row in controller.requests))
        self.assertNotIn("private-fixed-asset", (output / "raw.failure.json").read_text())
        self.assertIn("private-fixed-asset",
                      (output / "private/construction-failure.json").read_text())

    def test_unregistered_relink_evidence_rejected_before_output(self):
        task = dict(self.task, program="RELINK", slot=4)
        with self.assertRaisesRegex(ValueError, "collision evidence"):
            self._run(task)


if __name__ == "__main__":
    unittest.main()
