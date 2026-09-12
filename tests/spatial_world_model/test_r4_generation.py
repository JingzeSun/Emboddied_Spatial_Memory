"""Source/scene construction and artificial trajectory audits, zero mj_step.

MuJoCo model compilation verifies numerical XML wiring only; no renderer,
history, control branch or physical success is claimed by these tests.
"""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET
import mujoco
import numpy

from spatial_world_model.r4_families import family_config, manifest
from spatial_world_model.r4_physics import build_xml
from spatial_world_model.r4_trajectory import assess_trajectory
from spatial_world_model.two_gate_contract import assess_trajectory as original_assess
from test_two_gate_contract import trajectory

ROOT = Path(__file__).resolve().parents[2]


def inputs():
    base = json.loads((ROOT / "configs/spatial_history/two_gate_engineering_v1.json").read_text())
    protocol = json.loads((ROOT / "configs/spatial_history/protocol_r4_v1.json").read_text())
    return base, family_config(base, manifest(protocol)["rows"][0])


class R4GenerationTests(unittest.TestCase):
    def test_pinned_environment(self):
        self.assertEqual(mujoco.__version__, "3.3.7")
        self.assertEqual(numpy.__version__, "2.2.6")

    def test_xml_uses_independent_gate_centers_widths_and_translation(self):
        base, c = inputs()
        reference = (ROOT / base["physics_reference"]).read_text()
        for world in ("LL", "LR", "RL", "RR"):
            xml = build_xml(reference, c, world)
            model = mujoco.MjModel.from_xml_string(xml)
            for i, side in enumerate(world):
                left, right = model.geom(f"gate_{i}_left"), model.geom(f"gate_{i}_right")
                lo, hi = left.pos[0] + left.size[0], right.pos[0] - right.size[0]
                self.assertAlmostEqual((lo + hi) / 2, c["geometry"]["gate_centers_x_m"][i][side], places=12)
                self.assertAlmostEqual(hi - lo, c["geometry"]["gate_widths_m"][i], places=12)
            self.assertEqual(model.opt.timestep, 0.002)
            self.assertAlmostEqual(model.body("camera_rig").pos[0], c["observation"]["camera_x_m"])

    def test_assessor_matches_old_at_equal_gate_parameters(self):
        base, _ = inputs()
        c = deepcopy(base)
        c["version"] = "sh04-r4-family-v1"
        g = c["geometry"]
        g["gate_centers_x_m"] = [deepcopy(g["gate_center_x_m"]), deepcopy(g.pop("gate_center_x_m"))]
        g["gate_widths_m"] = [g.pop("gate_clear_width_m")] * 2
        samples = trajectory([(0, 0, 0), (5, -0.12, 0.8), (15, -0.12, 2.65), (20, -0.12, 2.65)])
        self.assertEqual(assess_trajectory(samples, c, world_name="LL"), original_assess(samples, base, world_name="LL"))

    def test_far_gate_audit_uses_far_center(self):
        _, c = inputs()
        c["geometry"]["gate_centers_x_m"] = [{"L": -0.12, "R": 0.12}, {"L": 0.35, "R": 0.36}]
        c["geometry"]["gate_widths_m"] = [0.38, 0.34]
        samples = trajectory([(0, 0, 0), (5, -0.12, 0.8), (15, -0.12, 2.65), (20, -0.12, 2.65)])
        result = assess_trajectory(samples, c, world_name="LL")
        near = [e for e in result["gate_events"] if e["gate_index"] == 0]
        far = [e for e in result["gate_events"] if e["gate_index"] == 1]
        self.assertTrue(near and far)
        self.assertTrue(near[0]["opening_valid"])
        self.assertFalse(far[0]["opening_valid"])

    def test_run_release_requires_reviewed_commit_and_real_quota_declaration(self):
        sys.path.insert(0, str(ROOT / "ops/spatial_history"))
        spec = importlib.util.spec_from_file_location("r4_ops_under_test", ROOT / "ops/spatial_history/r4_generation_check.py")
        ops = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ops)
        checked, c = {"commit": "a" * 40}, ops.configuration()
        for code, quota in ((None, 8), ("b" * 40, 8), ("a" * 40, None), ("a" * 40, 7), ("a" * 40, float("nan"))):
            with self.assertRaises(ValueError):
                ops.release_checked(checked, code, quota, c)
        release = ops.release_checked(checked, "a" * 40, 8, c)
        self.assertTrue(release["engineering_subset_only"])
        self.assertFalse(release["confirmation_authorized"])

    def test_model_features_do_not_get_family_or_geometry_fields(self):
        from spatial_world_model.r4_query import domain_spec
        fields = set(domain_spec())
        self.assertFalse(fields & {"gate_centers_x_m", "gate_widths_m", "family_id", "split", "parameters"})
