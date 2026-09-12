"""XML compilation and synthetic trajectory checks. Zero mj_step/render calls."""
import ast
from copy import deepcopy
from pathlib import Path
import unittest
import tempfile
import json
from unittest.mock import patch
import mujoco
import numpy

from test_r4_families_v2 import inputs
from r4_examples_v2 import trace
from spatial_world_model.r4_families_v2 import manifest, family_config
from spatial_world_model.r4_physics_v2 import build_xml
from spatial_world_model.r4_generation_v2 import contact_summary
from spatial_world_model.r4_scoring_v2 import labels_from_trajectory
from spatial_world_model.r4_trajectory_v2 import assess_trajectory

ROOT = Path(__file__).resolve().parents[2]


class R4GenerationV2Tests(unittest.TestCase):
    def test_pinned_environment(self):
        self.assertEqual(mujoco.__version__, "3.3.7")
        self.assertEqual(numpy.__version__, "2.2.6")

    def test_native_xml_independent_gates_and_unchanged_force_physics(self):
        proposal, base = inputs()
        reference = (ROOT / base["physics_reference"]).read_text()
        for row in manifest(proposal)["rows"][:4]:
            c = family_config(base, row)
            for world in base["worlds"]:
                model = mujoco.MjModel.from_xml_string(build_xml(reference, c, world))
                for i, side in enumerate(world):
                    left, right = model.geom(f"gate_{i}_left"), model.geom(f"gate_{i}_right")
                    lo, hi = left.pos[0] + left.size[0], right.pos[0] - right.size[0]
                    self.assertAlmostEqual((lo + hi) / 2, c["geometry"]["gate_centers_x_m"][i][side], places=12)
                    self.assertAlmostEqual(hi - lo, c["geometry"]["gate_widths_m"][i], places=12)
                    self.assertAlmostEqual(left.pos[1], c["geometry"]["gate_y_m"][i], places=12)
                self.assertEqual((model.vis.global_.offheight, model.vis.global_.offwidth), (80,80))
                self.assertEqual(model.opt.timestep, .002)
                self.assertEqual(model.cam_fovy[model.camera("ego").id], 42)
                self.assertEqual(list(model.body("camera_rig").pos), [c["observation"]["camera_x_m"], -.2, 1.4])
                self.assertTrue(numpy.array_equal(model.actuator_forcerange, [[-20,20],[-20,20]]))

    def test_assessor_body_unchanged_from_v1(self):
        # Function AST equality proves no event, threshold or success-rule edit;
        # only its imported exact-v2 config validator changed.
        def body(name):
            tree = ast.parse((ROOT / f"src/spatial_world_model/{name}.py").read_text())
            return ast.dump(next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "assess_trajectory"))
        self.assertEqual(body("r4_trajectory"), body("r4_trajectory_v2"))

    def test_contact_diagnostics_do_not_turn_pusher_contact_into_object_label(self):
        samples = trace()
        contact = {"geoms": ["pusher", "gate_0_left"], "distance_m": -.0001, "normal_force_n": .5}
        samples[1]["contacts"] = [contact, deepcopy(contact)]
        result = contact_summary(samples, 1e-6)
        pair = result["positive_contact_pairs"][0]
        self.assertEqual(pair["positive_steps"], 1)
        self.assertEqual(pair["peak_point_normal_force_n"], .5)
        labels = labels_from_trajectory(samples, {"physics_valid": True, "visibility_valid": True, "task_success": False})
        self.assertFalse(any(labels["interval_contact"]))
        samples[2]["contacts"] = [{**contact, "geoms": ["object", "gate_0_left"]}]
        self.assertTrue(labels_from_trajectory(samples, {"physics_valid": True, "visibility_valid": True, "task_success": False})["interval_contact"][0])

    def test_assessor_rejects_unregistered_geometry_before_scoring(self):
        proposal, base = inputs()
        c = family_config(base, manifest(proposal)["rows"][0])
        c["geometry"]["gate_widths_m"][1] = 1.0
        with self.assertRaises(ValueError):
            assess_trajectory([], c, world_name="LL")

    def test_raw_native_storage_size_static_expectation(self):
        # 4 worlds * (9 primaries + 9 replays); includes all five arrays.
        per_branch = 10001*67*8 + 201*80*80*3 + 201*80*80*8 + 201*8*2
        self.assertEqual(per_branch * 72, 1405018944)

    def test_false_gates_do_not_skip_any_registered_branch_or_replay(self):
        from spatial_world_model import r4_generation_v2 as generation
        from spatial_world_model import r4_physics_v2 as physics
        from spatial_world_model import r4_scoring_v2 as scoring
        from spatial_world_model.r4_families_v2 import ACTIONS, NAMES
        proposal, base = inputs()
        config = family_config(base, manifest(proposal)["rows"][0])
        events = []
        def history(root, config, reference, world, progress):
            private = root/"audit"/world; private.mkdir()
            (private/"world.xml").write_text("<synthetic/>")
            (private/"snapshot.json").write_text("{}")
            (root/"public"/f"{world}.json.gz").write_bytes(b"synthetic")
            return {}, {}, {}
        class FakeScene:
            def __init__(self, *args):
                pass
            def close(self):
                pass
            def rollout(self, snapshot, controls, directory, **kwargs):
                directory.mkdir()
                for name in ("integration", "rgb", "depth", "sensor_times", "sensor_step_indices"):
                    (directory/f"{name}.npy.gz").write_bytes(b"synthetic")
                import gzip
                with gzip.open(directory/"trajectory.jsonl.gz", "wt") as stream:
                    stream.write('{"synthetic":true}\n')
                result = {"assessment": {"physics_valid": False, "visibility_valid": False,
                          "task_success": None, "raw_task_success": False, "gate_contact_steps": 0}}
                (directory/"rollout.json").write_text(json.dumps(result))
                return result
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(generation, "_history", side_effect=history), \
                patch.object(generation, "_geometry", return_value={"accepted": False}), \
                patch.object(physics, "R4SceneV2", FakeScene), \
                patch.object(generation, "array_summary", return_value={"raw_bytes": 1}), \
                patch.object(generation, "compare_replay", return_value={"equal": True}), \
                patch.object(generation, "observation_checks", return_value={"synthetic": False}), \
                patch.object(generation, "audit_family", return_value={"checks": {"synthetic": False}}), \
                patch.object(generation, "contact_summary", return_value={"synthetic": True}), \
                patch.object(scoring, "labels_from_trajectory", return_value={"synthetic": True}):
            result = generation.run_family(Path(tmp)/"data", config, "synthetic", {}, events.append)
        order = [(e["kind"], e["world"], e["action"]) for e in events if e["phase"] == "branch_start"]
        self.assertEqual(order, [("primary", w, a) for w in NAMES for a in ACTIONS]
                         + [("replay", w, a) for w in reversed(NAMES) for a in reversed(ACTIONS)])
        self.assertFalse(result["accepted"])
        self.assertEqual(len(result["branches"]), 36)
        self.assertEqual(len(result["array_storage"]), 72)
