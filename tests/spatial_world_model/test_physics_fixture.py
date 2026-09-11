"""Server engineering checks; all failed scenes persist in the stage directory."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

import mujoco as mj
import numpy as np

from spatial_world_model.pair_contract import audit_pair, model_input
from spatial_world_model.physics_fixture import Scene, encode, generate_fixture, sha


ROOT = Path(__file__).resolve().parents[2]


class PhysicsFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = Path(os.environ["SH02_ARTIFACT_DIR"]) / "fixture"
        cls.pair, cls.evidence = generate_fixture(cls.directory,
            ROOT / "configs/spatial_history/physics_v1.json", ROOT / "configs/spatial_history/physics_v1.xml")
        cls.config = json.loads((cls.directory / "config.json").read_text())

    def test_contract_and_public_boundary(self):
        self.assertTrue(audit_pair(self.pair)["contract_valid"])
        for action in range(2):
            a = model_input(self.pair, 0, action, recent_only=True)
            b = model_input(self.pair, 1, action, recent_only=True)
            self.assertEqual(a, b)
            self.assertEqual(set(a), {"history", "controls", "goal"})
            self.assertNotEqual(model_input(self.pair, 0, action), model_input(self.pair, 1, action))

    def test_identical_recent_independently_rendered_sensors(self):
        a, b = self.pair["worlds"]
        self.assertEqual(a["history"][-2:], b["history"][-2:])
        self.assertGreater(len(set(a["history"][-1]["rgb"])), 4)
        self.assertTrue(all(0 < z <= 20.01 for z in a["history"][-1]["depth_m"]))

    def test_early_wall_visible_recent_wall_hidden_object_visible(self):
        for history in self.evidence["history_visibility"]:
            self.assertGreaterEqual(history[0]["wall"], self.config["minimum_early_wall_pixels"])
            for recent in history[-self.config["recent_frames"]:]:
                self.assertEqual(recent["wall"], 0)
                self.assertGreater(recent["object"], 0)

    def test_complete_nonlayout_initial_state_matches(self):
        self.assertTrue(self.evidence["nonlayout_integration_equal"])
        self.assertEqual(self.pair["worlds"][0]["initial_state"], self.pair["worlds"][1]["initial_state"])

    def test_observing_preserves_integration_state(self):
        self.assertEqual(self.evidence["observation_preserves_snapshot"], [True, True])

    def test_independent_reverse_order_replay_is_exact(self):
        self.assertEqual(self.evidence["replay_equal"], [True] * 4)

    def test_actual_wall_contact_and_counterfactual_separation(self):
        branches = self.evidence["branches"]
        self.assertEqual([b["wall_contact_steps"] > 0 for b in branches], [True, False, False, True])
        a, b = self.pair["worlds"]
        for action in range(2):
            x = np.asarray(a["branches"][action]["future"][-1]["object_position_m"])
            y = np.asarray(b["branches"][action]["future"][-1]["object_position_m"])
            self.assertGreaterEqual(float(np.linalg.norm(x-y)), self.config["minimum_outcome_separation_m"])

    def test_all_obstacle_contact_steps_are_out_of_view(self):
        hits = [b for b in self.evidence["branches"] if b["hidden_contact_steps"] > 0]
        self.assertEqual(len(hits), 2, "must not pass visibility on zero contacts")
        self.assertTrue(all(b["max_contact_object_pixels"] == 0 for b in hits))
        self.assertTrue(all(b["screen_contact_steps"] == 0 for b in self.evidence["branches"]))

    def test_planar_task_and_force_limits(self):
        for branch in self.evidence["branches"]:
            self.assertGreaterEqual(branch["object_z_range_m"][0], self.config["minimum_object_height_m"])
            self.assertLessEqual(branch["object_z_range_m"][1], self.config["maximum_object_height_m"])
            self.assertLessEqual(branch["max_tilt_rad"], self.config["maximum_tilt_rad"])
            self.assertLessEqual(branch["max_actuator_force_n"], 20 + 1e-9)

    def test_interval_contact_labels_come_from_recorded_steps(self):
        for world in range(2):
            for action in range(2):
                raw = json.loads((self.directory / f"world-{world}-action-{action}-trace.json").read_text())
                previous = self.pair["worlds"][world]["history"][-1]["time_s"]
                for sample in raw["future"]:
                    interval = [t for t in raw["trace"] if previous < t["time_s"] <= sample["time_s"]]
                    self.assertEqual(len(interval), 50)
                    self.assertEqual(sample["contact"], any(t["contact_visibility"] is not None for t in interval))
                    self.assertEqual(sample["object_position_m"], interval[-1]["object_position_m"])
                    previous = sample["time_s"]

    def test_snapshot_tampering_and_other_world_rejected(self):
        xml = (self.directory / "world-0.xml").read_text()
        snapshot = json.loads((self.directory / "world-0-snapshot.json").read_text())
        scene = Scene(xml, self.config)
        try:
            corrupted = deepcopy(snapshot)
            corrupted["state"][0] += .1
            with self.assertRaises(ValueError):
                scene.restore(corrupted, sha(encode(snapshot)))
            other = json.loads((self.directory / "world-1-snapshot.json").read_text())
            with self.assertRaises(ValueError):
                scene.restore(other, sha(encode(other)))
            for bad in ([0, 0, 1], [float("nan"), 0, 0], [0.6, 0, 0]):
                with self.assertRaises(ValueError):
                    scene.step(bad)
        finally:
            scene.close()

    def test_metric_depth_and_camera_convention_against_floor(self):
        scene = Scene((self.directory / "world-0.xml").read_text(), self.config)
        try:
            snapshot = json.loads((self.directory / "world-0-snapshot.json").read_text())
            scene.restore(snapshot, sha(encode(snapshot)))
            frame, seg = scene.observe(), scene.render("segmentation")
            rows, cols = np.nonzero((seg[:, :, 0] == scene.model.geom("floor").id)
                                    & (seg[:, :, 1] == int(mj.mjtObj.mjOBJ_GEOM)))
            self.assertGreater(len(rows), 8)
            # Reconstruct rendered floor pixels using the PUBLIC camera fields.
            quat = np.asarray(frame["camera_xyzw"])[[3, 0, 1, 2]]
            rotation = np.empty(9)
            mj.mju_quat2Mat(rotation, quat)
            fx, fy, cx, cy = frame["intrinsics"]
            depth = np.asarray(frame["depth_m"]).reshape(frame["height"], frame["width"])[rows, cols]
            points = np.column_stack(((cols-cx)/fx*depth, (rows-cy)/fy*depth, depth))
            world = points @ rotation.reshape(3, 3).T + frame["camera_position_m"]
            self.assertLess(float(np.max(np.abs(world[:, 2]))), 0.002)
        finally:
            scene.close()
