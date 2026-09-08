"""Lightweight metadata/continuation tests; no torch or training required."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from cpmt import m1_s5_training as s5
from cpmt.m1_protocol import protocol_sha256
from cpmt.run_provenance import source_tree_sha256


class TestM1S5TrainingMetadata(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hard = s5.read_json(PROJECT / "configs/m1_hard_condition.json")
        cls.overlay = s5.read_json(PROJECT / "configs/m1_endpoint_viability_probe.json")
        cls.plan = s5.read_json(PROJECT / "configs/m1_s5_training_plan.json")

    def load_changed(self, change):
        changed = deepcopy(self.plan)
        change(changed)
        original = s5.read_json
        with patch.object(s5, "read_json", side_effect=lambda path:
                          changed if path.name == "m1_s5_training_plan.json" else original(path)):
            return s5.load_plan(PROJECT, self.hard, self.overlay)

    def test_accepted_exports_bind_both_full_train_recipes_without_validation(self):
        plan, registration = s5.load_plan(PROJECT, self.hard, self.overlay)
        self.assertEqual(plan, self.plan)
        self.assertEqual(plan["train_paired_groups"], 1000)
        self.assertFalse(registration["evaluation_plan"]["validation_selects_settings"])

    def test_rejects_changed_selected_budget(self):
        def change(plan):
            arm = plan["arms"]["cross_candidate_set_transformer_v1"]
            arm["selected"]["student_hyperparameters_by_method"]["cpmt_ctl_core"]["student_steps"] = 10000
        with self.assertRaisesRegex(ValueError, "selected budget changed"):
            self.load_changed(change)

    def test_rejects_access_device_population_and_architecture_drift(self):
        for key, value in (("test_access", True), ("validation_arrays_read", True),
                           ("device", "cpu"), ("training_population", "inner_dev_only"),
                           ("train_paired_groups", 799), ("main_label_fraction", 1.0)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.load_changed(lambda plan: plan.update({key: value}))
        with self.assertRaisesRegex(ValueError, "architecture"):
            self.load_changed(lambda plan: plan["arms"].pop("shared_candidate_mlp_v1"))

    def test_rejects_replaced_export_even_if_filename_matches(self):
        with patch.object(s5, "file_sha256", return_value="wrong"):
            with self.assertRaisesRegex(ValueError, "budget export digest"):
                s5.load_plan(PROJECT, self.hard, self.overlay)

    def test_sixty_components_use_registered_method_and_scorer_budgets(self):
        total = 0
        for architecture, arm in self.plan["arms"].items():
            for seed in self.plan["seeds"]:
                scorer = s5.component_spec(self.plan, architecture, seed, "outcome_scorer")
                self.assertEqual(scorer["settings"]["scorer_steps"], arm["selected"]["outcome_scorer_steps"])
                for method, setting in arm["selected"]["student_hyperparameters_by_method"].items():
                    self.assertEqual(s5.component_spec(self.plan, architecture, seed, method)["settings"], setting)
                    total += 1
                total += 1
        self.assertEqual(total, 60)
        with self.assertRaises(ValueError):
            s5.component_spec(self.plan, "shared_candidate_mlp_v1", 7, "oracle_candidate_program")

    def test_completed_artifact_reuses_without_producer_and_rejects_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model"
            def produce(target):
                target.write_bytes(b"known model")
                return {"wall_seconds": 1.0}
            manifest, reused = s5.ensure_artifact(path, {"code": "a"}, {"seed": 7}, produce)
            self.assertFalse(reused)
            def forbidden(target):
                self.fail("completed artifact must not retrain")
            self.assertEqual(s5.ensure_artifact(path, {"code": "a"}, {"seed": 7}, forbidden), (manifest, True))
            with self.assertRaisesRegex(ValueError, "binding mismatch"):
                s5.ensure_artifact(path, {"code": "b"}, {"seed": 7}, forbidden)
            (path / "model.pt").write_bytes(b"corrupt")
            with self.assertRaisesRegex(ValueError, "file hash"):
                s5.ensure_artifact(path, {"code": "a"}, {"seed": 7}, forbidden)

    def test_interrupted_artifact_preserves_failure_and_never_automatically_retrains(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model"
            def fail(target):
                target.write_bytes(b"partial")
                raise RuntimeError("interrupted")
            with self.assertRaises(RuntimeError):
                s5.ensure_artifact(path, {}, {}, fail)
            self.assertFalse(path.exists())
            self.assertTrue((path.with_name(".model.incomplete") / "failure.json").exists())
            with self.assertRaisesRegex(ValueError, "requires review"):
                s5.ensure_artifact(path, {}, {}, lambda target: self.fail("must not retrain"))

    def test_new_code_requires_matching_successful_test_marker(self):
        marker = {"schema_version": "cpmt-d049-full-test-marker-v1", "exit_code": 0,
                  "failures": 0, "errors": 0, "skipped": 0, "tests_run": 234, "expected_tests": 234,
                  "plan_sha256": protocol_sha256(self.plan), "test_access": False,
                  "registration_sha256": self.plan["post_probe_registration_sha256"],
                  "source_tree_unchanged": True,
                  "formal_validation_arrays_read": False,
                  "source_and_tests_sha256": source_tree_sha256(PROJECT, roots=("src", "scripts", "configs", "tests"))}
        s5.validate_test_marker(marker, PROJECT, self.plan)
        for key, value in (("exit_code", 1), ("tests_run", 221), ("plan_sha256", "changed"),
                           ("source_and_tests_sha256", "old"), ("test_access", True)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                s5.validate_test_marker(dict(marker, **{key: value}), PROJECT, self.plan)


if __name__ == "__main__":
    unittest.main()
