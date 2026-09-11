"""Server-only XML, control, snapshot, and small real-sensor smoke checks.

Two histories and a few zero-control steps are exercised; no full control
branch, 4x4 outcome matrix, learner, or formal experiment runs in this suite.
All generated sensor evidence remains in SH04R2_TEST_ARTIFACT_DIR on failure.
"""
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

import mujoco as mj
import numpy as np

from spatial_world_model.two_gate_physics import (
    TwoGateScene, build_xml, encode, expand_controls, save_png, sha,
)


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "configs/spatial_history/two_gate_engineering_v1.json"
REFERENCE_PATH = ROOT / "configs/spatial_history/physics_v1.xml"


class TwoGateXmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.reference = REFERENCE_PATH.read_text(encoding="utf-8")

    def test_gate_openings_and_side_wall_junctions(self):
        for world in ("LL", "LR", "RL", "RR"):
            tree = ET.fromstring(build_xml(self.reference, self.config, world))
            geoms = {node.get("name"): node for node in tree.findall("./worldbody/geom")}
            self.assertNotIn("screen", geoms)
            self.assertNotIn("wall", geoms)
            for index, label in enumerate(world):
                left, right = geoms[f"gate_{index}_left"], geoms[f"gate_{index}_right"]
                lp, ls = [float(x) for x in left.get("pos").split()], [float(x) for x in left.get("size").split()]
                rp, rs = [float(x) for x in right.get("pos").split()], [float(x) for x in right.get("size").split()]
                expected = -0.12 if label == "L" else 0.12
                self.assertAlmostEqual(lp[0] + ls[0], expected - 0.19)
                self.assertAlmostEqual(rp[0] - rs[0], expected + 0.19)
                self.assertAlmostEqual(lp[0] - ls[0], -0.80)
                self.assertAlmostEqual(rp[0] + rs[0], 0.80)
                self.assertEqual(lp[1:], [0.6 if index == 0 else 2.2, 0.15])
                self.assertEqual(ls[1:], [0.025, 0.15])
            for label, center in (("left", -0.825), ("right", 0.825)):
                node = geoms["side_" + label]
                self.assertTrue(np.allclose([float(x) for x in node.get("pos").split()],
                                            [center, 1.3, 0.15], rtol=0, atol=1e-15))
                self.assertTrue(np.allclose([float(x) for x in node.get("size").split()],
                                            [0.025, 1.7, 0.15], rtol=0, atol=1e-15))

    def test_only_gate_geometry_changes_between_worlds(self):
        normalized = []
        for world in ("LL", "LR", "RL", "RR"):
            tree = ET.fromstring(build_xml(self.reference, self.config, world))
            for node in tree.findall("./worldbody/geom"):
                if node.get("name", "").startswith("gate_"):
                    node.set("pos", "layout")
                    node.set("size", "layout")
            normalized.append(ET.tostring(tree))
        self.assertTrue(all(value == normalized[0] for value in normalized))
        self.assertEqual(self.reference, REFERENCE_PATH.read_text(encoding="utf-8"))
        with self.assertRaises(ValueError):
            build_xml(self.reference, self.config, "LX")

    def test_preserved_force_mass_friction_and_degrees_of_freedom(self):
        tree = ET.fromstring(build_xml(self.reference, self.config, "LL"))
        self.assertEqual([float(x) for x in tree.find("./default/geom").get("friction").split()],
                         [0.25, 0.005, 0.0001])
        for name, mass in (("object", 0.15), ("pusher", 0.5)):
            self.assertEqual(float(tree.find("./worldbody/body/geom[@name='" + name + "']").get("mass")), mass)
        self.assertIsNotNone(tree.find("./worldbody/body[@name='object']/freejoint"))
        joints = tree.findall("./worldbody/body[@name='pusher']/joint")
        self.assertEqual([node.get("axis") for node in joints], ["1 0 0", "0 1 0"])
        for actuator in tree.findall("./actuator/velocity"):
            self.assertEqual(float(actuator.get("kv")), 100)
            self.assertEqual([float(x) for x in actuator.get("forcerange").split()], [-20, 20])

    def test_control_integrals_common_clock_and_independent_rows(self):
        for action in ("LL", "LR", "RL", "RR"):
            controls = expand_controls(self.config, action)
            self.assertEqual(len(controls), 200)
            self.assertAlmostEqual(sum(row["duration_s"] for row in controls), 20)
            self.assertAlmostEqual(sum(row["duration_s"] * row["ee_velocity_mps"][1] for row in controls), 2.8)
            self.assertAlmostEqual(sum(row["duration_s"] * row["ee_velocity_mps"][0] for row in controls),
                                   -0.12 if action[1] == "L" else 0.12)
            self.assertTrue(all(abs(row["ee_velocity_mps"][0]) <= 0.04 for row in controls))
            self.assertEqual(controls[-52:], [{"duration_s": 0.1, "ee_velocity_mps": [0, 0, 0]}] * 52)
            controls[0]["ee_velocity_mps"][0] = 9
            self.assertEqual(controls[1]["ee_velocity_mps"][0], 0)


class TwoGateSensorSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.reference = REFERENCE_PATH.read_text(encoding="utf-8")
        cls.directory = Path(os.environ["SH04R2_TEST_ARTIFACT_DIR"])
        cls.directory.mkdir(parents=True, exist_ok=False)
        cls.scenes, cls.histories, cls.visibility, cls.snapshots = {}, {}, {}, {}
        for world in ("LL", "LR"):
            xml = build_xml(cls.reference, cls.config, world)
            with (cls.directory / (world + ".xml")).open("x", encoding="utf-8") as handle:
                handle.write(xml)
            scene = TwoGateScene(xml, cls.config)
            cls.addClassCleanup(scene.close)
            cls.scenes[world] = scene
            history, visible = scene.history()
            cls.histories[world], cls.visibility[world] = history, visible
            cls.snapshots[world] = scene.snapshot()
            with (cls.directory / (world + "-history.json")).open("xb") as handle:
                handle.write(encode({"history": history, "visibility": visible, "snapshot": scene.snapshot()}))
            for name, index in (("A", 25), ("B", 65), ("recent", 120)):
                pixels = np.asarray(history[index]["rgb"], dtype=np.uint8).reshape(64, 64, 3)
                save_png(cls.directory / f"{world}-{name}.png", pixels)

    def test_real_histories_have_registered_clock_and_local_gate_views(self):
        for world, history in self.histories.items():
            self.assertEqual(len(history), 121)
            self.assertAlmostEqual(history[0]["time_s"], 0.5, places=10)
            self.assertAlmostEqual(history[-1]["time_s"], 12.5, places=9)
            visible = self.visibility[world]
            for index, target, hidden in ((25, 0, 1), (65, 1, 0)):
                for side in ("left", "right"):
                    self.assertGreaterEqual(visible[index][f"gate_{target}_{side}"], 4)
                    self.assertEqual(visible[index][f"gate_{hidden}_{side}"], 0)
            for counts in visible:
                near = counts["gate_0_left"] + counts["gate_0_right"]
                far = counts["gate_1_left"] + counts["gate_1_right"]
                self.assertFalse(near and far)

    def test_recent_sensors_and_nonlayout_integration_match(self):
        self.assertEqual(self.histories["LL"][-2:], self.histories["LR"][-2:])
        self.assertEqual(self.histories["LL"][25], self.histories["LR"][25])
        self.assertNotEqual(self.histories["LL"][65]["rgb"], self.histories["LR"][65]["rgb"])
        self.assertEqual(self.snapshots["LL"]["state"], self.snapshots["LR"]["state"])
        for counts in (self.visibility["LL"][-1], self.visibility["LR"][-1]):
            self.assertGreater(counts["object"], 0)
            self.assertGreater(counts["pusher"], 0)

    def test_top_down_rotation_and_metric_floor_depth(self):
        scene = self.scenes["LL"]
        scene.restore(self.snapshots["LL"], scene.digest(self.snapshots["LL"]))
        frame, seg = scene.observe(), scene.render("segmentation")
        quat = np.asarray(frame["camera_xyzw"])[[3, 0, 1, 2]]
        rotation = np.empty(9)
        mj.mju_quat2Mat(rotation, quat)
        self.assertTrue(np.allclose(rotation.reshape(3, 3), np.diag([1, -1, -1]), atol=1e-12, rtol=0))
        rows, cols = np.nonzero((seg[:, :, 0] == scene.geom_ids["floor"])
                               & (seg[:, :, 1] == int(mj.mjtObj.mjOBJ_GEOM)))
        self.assertGreater(len(rows), 8)
        fx, fy, cx, cy = frame["intrinsics"]
        depth = np.asarray(frame["depth_m"]).reshape(64, 64)[rows, cols]
        local = np.column_stack(((cols - cx) / fx * depth, (rows - cy) / fy * depth, depth))
        world = local @ rotation.reshape(3, 3).T + frame["camera_position_m"]
        self.assertLess(float(np.max(np.abs(world[:, 2]))), 0.002)

    def test_observation_does_not_change_full_integration_state(self):
        scene = self.scenes["LL"]
        scene.restore(self.snapshots["LL"], scene.digest(self.snapshots["LL"]))
        before = scene.snapshot()
        scene.observe()
        scene.visibility()
        self.assertEqual(scene.snapshot(), before)

    def test_camera_path_endpoints_and_fixed_orientation(self):
        scene = self.scenes["LL"]
        for seconds, y in ((0, -0.1), (2, 0.6), (3, 0.6), (6, 2.2), (7, 2.2), (11, -0.1), (12, -0.1)):
            self.assertAlmostEqual(scene.camera_y_at(seconds), y)
        with self.assertRaises(ValueError):
            scene.camera_y_at(-0.1)
        self.assertEqual(self.histories["LL"][-1]["camera_position_m"], [0, -0.1, 1.4])

    def test_snapshot_tampering_and_cross_world_rejected(self):
        scene = self.scenes["LL"]
        saved = self.snapshots["LL"]
        bad = deepcopy(saved)
        bad["state"][0] += 0.1
        with self.assertRaises(ValueError):
            scene.restore(bad, scene.digest(saved))
        with self.assertRaises(ValueError):
            scene.restore(self.snapshots["LR"], scene.digest(self.snapshots["LR"]))

    def test_invalid_controls_rejected_without_stepping(self):
        scene = self.scenes["LL"]
        scene.restore(self.snapshots["LL"], scene.digest(self.snapshots["LL"]))
        before = scene.snapshot()
        for command in ([0, 0, 0.1], [0.51, 0, 0], [float("nan"), 0, 0], [0, 0]):
            with self.assertRaises(ValueError):
                scene.step(command)
        self.assertEqual(scene.snapshot(), before)

    def test_unfiltered_contacts_and_saved_state_observation(self):
        scene = self.scenes["LL"]
        scene.restore(self.snapshots["LL"], scene.digest(self.snapshots["LL"]))
        start_time = scene.data.time
        for _ in range(5):
            scene.step([0, 0, 0])
        sample = scene._sample(5, start_time)
        self.assertEqual(len(sample["contacts"]), scene.data.ncon)
        self.assertEqual(len(sample["actuator_force_n"]), 2)
        self.assertAlmostEqual(math.sqrt(sum(x * x for x in sample["object_axis_world"])), 1)
        saved = scene.state()
        for _ in range(5):
            scene.step([0, 0, 0])
        later = scene.snapshot()
        scene._restore_state(saved)
        before = scene.snapshot()
        scene.visibility()
        self.assertEqual(scene.snapshot(), before)
        scene.restore(later, scene.digest(later))
        self.assertEqual(scene.snapshot(), later)

    def test_tiny_streamed_rollout_and_fresh_instance_replay(self):
        # This shortened zero-control fixture checks I/O/state mechanics only;
        # it does not call the task scorer or shorten a production experiment.
        config = deepcopy(self.config)
        config["controls"]["control_steps"] = 2
        config["controls"]["horizon_s"] = 0.2
        controls = expand_controls(self.config, "LL")[-2:]
        requested = [0, 1, 49, 50, 51, 99, 100]

        def assessor(samples, _config, *, world_name):
            self.assertEqual(world_name, "LL")
            self.assertEqual(len(samples), 101)
            return {"required_visibility_indices": requested,
                    "all_requested_observed": all(samples[i]["object_visible_pixels"] is not None for i in requested)}

        results = []
        events = []
        for label in ("primary", "fresh-replay"):
            scene = TwoGateScene(build_xml(self.reference, config, "LL"), config)
            try:
                result = scene.rollout(self.snapshots["LL"], controls,
                                       self.directory / ("tiny-" + label), world_name="LL",
                                       assessor=assessor, progress=events.append)
                results.append(result)
                self.assertTrue(result["assessment"]["all_requested_observed"])
                self.assertEqual(result["sensor_count"], 3)
                self.assertEqual(result["step_count"], 100)
                self.assertEqual(scene.snapshot(), result["end_snapshot"])
            finally:
                scene.close()
        self.assertEqual(results[0], results[1])
        self.assertTrue(any(event.get("reserve_bytes", 0) > 0 for event in events))
        path = self.directory / "tiny-primary"
        with (path / "trajectory.jsonl").open("rb") as handle:
            samples = [json.loads(line) for line in handle]
        raw_state = np.load(path / "integration.npy", mmap_mode="r")
        self.assertTrue(np.array_equal(raw_state[0], self.snapshots["LL"]["state"]))
        self.assertTrue(np.array_equal(raw_state[-1], results[0]["end_snapshot"]["state"]))
        self.assertAlmostEqual(samples[-1]["time_s"], 0.2)
        self.assertEqual(set(results[0]["files"]), {
            "trace_raw.jsonl", "trajectory.jsonl", "integration.npy", "rgb.npy", "depth.npy",
            "sensor_times.npy", "sensor_step_indices.npy", "visibility.jsonl", "end_snapshot.json",
            "final_ego.png", "private_overview.png",
        })


if __name__ == "__main__":
    unittest.main()
