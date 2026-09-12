"""Server-only deterministic design checks; no physical observations generated."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from spatial_world_model.r4_families import (manifest, validate_manifest, engineering_rows,
    family_config, controls, camera_design, categorical_shortcut, parameter_word)

ROOT = Path(__file__).resolve().parents[2]


def inputs():
    return [json.loads((ROOT / "configs/spatial_history" / name).read_text())
            for name in ("protocol_r4_v1.json", "two_gate_engineering_v1.json")]


class R4FamilyTests(unittest.TestCase):
    def test_independent_hash_split_and_four_subset(self):
        protocol, _ = inputs()
        design = manifest(protocol)
        expected = sorted(range(64), key=lambda i: hashlib.sha256(f"sh04-r4-v1:split:{i}".encode()).hexdigest())
        self.assertEqual([r["index"] for r in design["rows"]], expected)
        self.assertEqual([r["index"] for r in engineering_rows(design)], expected[:4])
        self.assertEqual(len({r["normalized_design_sha256"] for r in design["rows"]}), 64)
        self.assertFalse(design["confirmation_observations_generated"])

    def test_registered_design_file_matches_algorithm(self):
        protocol, _ = inputs()
        saved = json.loads((ROOT / "configs/spatial_history/r4_family_design_v1.json").read_text())
        validate_manifest(saved, protocol)

    def test_reordered_or_modified_manifest_rejected(self):
        protocol, _ = inputs()
        for field in ("split", "parameters", "family_id"):
            design = manifest(protocol)
            design["rows"][0][field] = None
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_manifest(design, protocol)

    def test_parameters_independent_of_layout_and_control_values(self):
        protocol, base = inputs()
        for row in manifest(protocol)["rows"]:
            c = family_config(base, row)
            tx = row["parameters"]["global_translation_x_m"]
            self.assertEqual(c["observation"]["camera_x_m"], tx)
            for a in base["worlds"]:
                for i, value in enumerate(base["controls"]["phase_vx_mps"][a]):
                    scale = row["parameters"]["control_near_scale" if i < 5 else "control_far_scale"]
                    self.assertEqual(c["controls"]["phase_vx_mps"][a][i], value * scale)
            self.assertTrue(all(len(v) == 200 for v in controls(c).values()))
            self.assertFalse(c["generation_authorized"])
            self.assertNotIn("gate_center_x_m", c["geometry"])

    def test_hash_domain_separation_and_index_validation(self):
        expected = int.from_bytes(hashlib.sha256(b"sh04-r4-v1:param:0:camera_order").digest()[:8], "big")
        self.assertEqual(parameter_word(0, "camera_order"), expected)
        for value in (-1, 64, True, "0"):
            with self.assertRaises(ValueError):
                parameter_word(value, "camera_order")

    def test_camera_continuity_order_and_semantic_view_indices(self):
        orders = set()
        for i in range(64):
            camera = camera_design(i)
            orders.add(camera["order"])
            segments = camera["segments"]
            self.assertEqual(segments[0]["time_s"][0], 0)
            self.assertEqual(segments[-1], {"time_s": [11, 12], "y_m": [-0.1, -0.1]})
            for a, b in zip(segments, segments[1:]):
                self.assertEqual(a["time_s"][1], b["time_s"][0])
                self.assertEqual(a["y_m"][1], b["y_m"][0])
            for name, expected_y in (("A", 0.6), ("B", 2.2)):
                t = camera["view_frame_indices"][name] / 10
                segment = next(s for s in segments if s["time_s"][0] <= t <= s["time_s"][1])
                self.assertEqual(segment["y_m"], [expected_y, expected_y])
        self.assertEqual(orders, {"near_first", "far_first"})

    def test_common_optimum_not_identical_sets_is_shortcut(self):
        names = ("LL", "LR", "RL", "RR")
        first = {w: {a: i in (0, 1) for i, a in enumerate(names)} for w in names}
        second = {w: {a: i in (1, 2) for i, a in enumerate(names)} for w in names}
        result = categorical_shortcut([first, second])
        self.assertTrue(result["categorical_shortcut_unexcluded"])
        self.assertTrue(all(v == [1] for v in result["optimal_index_intersections"].values()))
        second["LL"] = {a: i == 3 for i, a in enumerate(names)}
        self.assertFalse(categorical_shortcut([first, second])["categorical_shortcut_unexcluded"])

    def test_changed_protocol_split_or_ranges_rejected(self):
        protocol, _ = inputs()
        for field in ("ranges", "split_counts"):
            bad = deepcopy(protocol)
            bad["dataset"][field] = None
            with self.assertRaises(ValueError):
                manifest(bad)
