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

    def test_v2_changes_only_wall_x_and_version_for_all_original_cases(self):
        v2 = json.loads((ROOT / "configs/spatial_history/development_audit_v2_wall_clearance.json").read_text())
        self.assertEqual(validate_registry(v2), self.registry["cases"])
        original = deepcopy((self.config, self.registry, v2))
        for case in v2["cases"]:
            config1, xml1 = prepare_case(self.config, self.xml, case, self.registry)
            config2, xml2 = prepare_case(self.config, self.xml, case, v2)
            self.assertEqual(config2["version"], v2["version"])
            config1["version"] = config2["version"]
            self.assertEqual(config1, config2)
            before, after = ET.fromstring(xml1), ET.fromstring(xml2)
            self.assertEqual(after.attrib["model"], v2["version"])
            before.set("model", after.attrib["model"])
            wall = before.find("./worldbody/geom[@name='wall']")
            position = wall.attrib["pos"].split()
            self.assertEqual(float(position[0]), -0.31)
            position[0] = "-0.33"
            wall.set("pos", " ".join(position))
            self.assertEqual(ET.tostring(before), ET.tostring(after))
        self.assertEqual((self.config, self.registry, v2), original)

    def test_v2_rejects_unregistered_clearance_and_missing_failure_binding(self):
        saved = json.loads((ROOT / "configs/spatial_history/development_audit_v2_wall_clearance.json").read_text())
        for mode in ("different_clearance", "boolean", "missing_clearance", "missing_failure", "wrong_failure"):
            v2 = deepcopy(saved)
            if mode == "different_clearance": v2["wall_center_abs_x_m"] = 0.34
            elif mode == "boolean": v2["wall_center_abs_x_m"] = True
            elif mode == "missing_clearance": v2.pop("wall_center_abs_x_m")
            elif mode == "missing_failure": v2.pop("prior_development_audit_sha256")
            else: v2["prior_development_audit_sha256"] = "0" * 64
            with self.assertRaises(ValueError): validate_registry(v2)

    def test_v1_cannot_silently_accept_v2_geometry_fields(self):
        self.registry["wall_center_abs_x_m"] = 0.33
        with self.assertRaises(ValueError): validate_registry(self.registry)

    def test_extra_hidden_wall_contact_still_fails_original_acceptance(self):
        # A third branch touching the wall is rejected even when fully hidden.
        extra = self.evidence["branches"][1]
        extra.update(wall_contact_steps=8, hidden_contact_steps=8, max_contact_object_pixels=0)
        result = assess(self.contract, self.evidence, self.config)
        self.assertFalse(result["accepted"])
        self.assertIn("expected_wall_contact_pattern", result["failed_checks"])
        self.assertIn("positive_contacts_out_of_view", result["failed_checks"])
