"""SH-03 adaptation tests; saved SH-02 evidence is not a new physical run."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from spatial_world_model.development_audit import assess, prepare_case, validate_registry

ROOT = Path(__file__).resolve().parents[2]


class DevelopmentAuditTests(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads((ROOT / "configs/spatial_history/development_audit_v1.json").read_text())
        self.config = json.loads((ROOT / "configs/spatial_history/physics_v1.json").read_text())
        self.xml = (ROOT / "configs/spatial_history/physics_v1.xml").read_text()
        report = json.loads((ROOT / "results/spatial_history_physics_v2_flat_pusher.json").read_text())
        self.evidence = report["diagnostics"]["fixture/evidence.json"]
        # Contract status of the approved fixture, independently tested by SH-02.
        self.contract = {"contract_valid": True, "early_visual_evidence_differs": True}

    def test_all_sixteen_registered_cases_preserve_unmodified_parameters(self):
        for case in validate_registry(self.registry):
            config, xml = prepare_case(self.config, self.xml, case)
            expected = deepcopy(self.config)
            expected.update(version="sh03-development-v1", history_arc_samples=case["history_arc_samples"])
            expected["camera_target_m"][0] = case["start_x_m"]
            self.assertEqual(config, expected)
            before, after = ET.fromstring(self.xml), ET.fromstring(xml)
            self.assertEqual(float(after.find("./worldbody/geom[@name='wall']").attrib["pos"].split()[1]), case["wall_y_m"])
            for body in ("object", "pusher"):
                self.assertEqual(float(after.find(f"./worldbody/body[@name='{body}']").attrib["pos"].split()[0]), case["start_x_m"])
            before.set("model", after.attrib["model"])
            for path in ("./worldbody/geom[@name='wall']", "./worldbody/body[@name='object']", "./worldbody/body[@name='pusher']"):
                before.find(path).set("pos", after.find(path).attrib["pos"])
            self.assertEqual(ET.tostring(before), ET.tostring(after))

    def test_preparation_does_not_mutate_base_or_registry(self):
        original = deepcopy((self.config, self.registry))
        config, _ = prepare_case(self.config, self.xml, self.registry["cases"][0])
        config["left_control_phases"][0]["ee_velocity_mps"][0] = 99
        self.assertEqual((self.config, self.registry), original)

    def test_duplicate_or_missing_cases_and_non_development_rejected(self):
        for mode in ("duplicate", "missing", "split"):
            registry = deepcopy(self.registry)
            if mode == "duplicate": registry["cases"][1] = registry["cases"][0]
            elif mode == "missing": registry["cases"].pop()
            else: registry["split"] = "test"
            with self.assertRaises(ValueError): validate_registry(registry)

    def test_unregistered_case_fields_and_unsafe_ids_rejected(self):
        for name, value in (("case_id", "../escape"), ("wall_y_m", 0.9), ("history_arc_samples", True), ("answer", 1)):
            case = deepcopy(self.registry["cases"][0]); case[name] = value
            with self.assertRaises(ValueError): prepare_case(self.config, self.xml, case)

    def test_approved_sh02_evidence_meets_same_acceptance_conditions(self):
        self.assertTrue(assess(self.contract, self.evidence, self.config)["accepted"])

    def test_zero_contact_does_not_vacuously_pass_visibility(self):
        for b in self.evidence["branches"]: b.update(hidden_contact_steps=0, wall_contact_steps=0)
        result = assess(self.contract, self.evidence, self.config)
        self.assertIn("positive_contacts_out_of_view", result["failed_checks"])
        self.assertIn("expected_wall_contact_pattern", result["failed_checks"])

    def test_visibility_leak_and_failed_contract_are_retained(self):
        self.evidence["branches"][0]["max_contact_object_pixels"] = 1
        self.contract["contract_valid"] = False
        result = assess(self.contract, self.evidence, self.config)
        self.assertFalse(result["accepted"])
        self.assertEqual(len(result["branches"]), 4)
        self.assertIn("paired_input_contract", result["failed_checks"])
        self.assertIn("positive_contacts_out_of_view", result["failed_checks"])

    def test_missing_replay_and_collapsed_outcomes_rejected(self):
        self.evidence["replay_equal"].pop()
        self.evidence["final_separation_m_by_action"] = [0, 0]
        result = assess(self.contract, self.evidence, self.config)
        self.assertIn("independent_replay_exact", result["failed_checks"])
        self.assertIn("both_actions_have_contrast", result["failed_checks"])
