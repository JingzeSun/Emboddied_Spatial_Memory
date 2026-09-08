"""Lightweight checks for sealed post-probe registration and evidence binding."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from cpmt.m1_protocol import protocol_sha256
from cpmt.m1_registration import load_registration, validate_registration


class TestM1Registration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def read(name):
            return json.loads((PROJECT / name).read_text(encoding="utf-8"))
        cls.source = read("configs/m1_hard_condition.json")
        cls.overlay = read("configs/m1_endpoint_viability_probe.json")
        cls.probe = read("results/m1_v6_d047_endpoint_probe.json")["endpoint_probe"]
        cls.registration = read("configs/m1_post_probe_registration.json")

    def test_completed_probe_registers_exact_and_1350_without_opening_test(self):
        actual = load_registration(PROJECT, self.source, self.overlay)
        self.assertEqual(actual, self.registration)
        self.assertFalse(actual["test_access"])
        # The generation fingerprint remains usable for existing train arrays.
        self.assertEqual(protocol_sha256(self.source),
                         "73666cabb77b4884302d77ca621669bfdc77e86a44951b8a92b97208509c0eec")

    def test_rejects_test_release_endpoint_switch_and_weakened_gate(self):
        for key, value in (("semantic_metric", "final_graded_active_world_correctness"),
                           ("minimum_effects", [0.03, 0.03, 3.0]),
                           ("paired_groups", {"train": 1000, "validation": 200, "test": 200}),
                           ("validation_selects_settings", True)):
            with self.subTest(key=key):
                changed = deepcopy(self.registration)
                changed["evaluation_plan"][key] = value
                with self.assertRaisesRegex(ValueError, "evaluation plan"):
                    validate_registration(changed, self.source, self.overlay, self.probe)
        changed = dict(self.registration, test_access=True)
        with self.assertRaisesRegex(ValueError, "sealed"):
            validate_registration(changed, self.source, self.overlay, self.probe)

    def test_rejects_replaced_evidence_even_if_report_still_says_complete(self):
        changed = deepcopy(self.probe)
        changed["endpoint_assessment"]["selected_test_groups"] = 200
        with self.assertRaisesRegex(ValueError, "endpoint_probe_sha256"):
            validate_registration(self.registration, self.source, self.overlay, changed)

    def test_power_recomputed_even_if_evidence_hash_is_updated(self):
        changed = deepcopy(self.probe)
        changed["endpoint_assessment"]["by_metric"][
            "final_active_graph_correctness"]["A_vs_E"][
                "paired_group_standard_deviation"] = 0.01
        registration = dict(self.registration, endpoint_probe_sha256=protocol_sha256(changed))
        with self.assertRaisesRegex(ValueError, "power arithmetic"):
            validate_registration(registration, self.source, self.overlay, changed)


if __name__ == "__main__":
    unittest.main()
