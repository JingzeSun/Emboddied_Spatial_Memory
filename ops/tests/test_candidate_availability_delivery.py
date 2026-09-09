"""Tiny file/exit fixtures for experimental phase delivery; no real rollout."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("availability_delivery", ROOT / "ops/m1_candidate_availability.py")
delivery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(delivery)
from cpmt.m1_branch_preflight import GROUPS, summarize


class TestAvailabilityDelivery(unittest.TestCase):
    binding = {"source_and_tests_sha256": "fixture", "source_report_sha256": delivery.REPORT_SHA}

    def complete_failure(self, stage):
        run = stage / "run"
        run.mkdir()
        groups = []
        for group in GROUPS:
            folder = run / f"group_{group:06d}"
            folder.mkdir()
            row = {"group": group, "status": "failed", "branches": [], "failures": [{"error": "fixture"}],
                   "reference_steps_verified": 0, "recovery_steps_verified": 0}
            delivery.write_json(folder / "result.json", row)
            groups.append({**row, "files": delivery.files(folder)})
        report = {"source_and_tests_sha256": "fixture", "source_report_sha256": delivery.REPORT_SHA,
                  "groups": groups, "gate": summarize(groups)}
        for key in ("validation_access", "test_access", "training_performed", "data_generated", "formal_budget_authorized"):
            report[key] = False
        delivery.write_json(run / "report.json", report)
        (stage / "check.log").write_text("failure preserved\n", encoding="utf-8")
        delivery.write_json(stage / "check.completed.json", {"binding": self.binding,
                            "exit_code": 1, "files": delivery.files(run)})
        (stage / "test.log").write_text("fixture test\n", encoding="utf-8")
        delivery.write_json(stage / "test.completed.json", {"binding": self.binding, "exit_code": 0,
                            "log_sha256": delivery.file_digest(stage / "test.log")})

    def test_failed_check_reused_without_launching_process(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            self.complete_failure(stage)
            with patch.object(delivery, "command", side_effect=AssertionError("relaunched")):
                self.assertEqual(delivery.run_check(stage, self.binding), 1)

    def test_failure_export_and_idempotent_readback(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            self.complete_failure(stage)
            target = stage / "export.json"
            with patch.object(delivery, "EXPORT", target):
                self.assertEqual(delivery.export(stage, self.binding), 0)
                old = target.read_bytes()
                self.assertEqual(delivery.export(stage, self.binding), 0)
                self.assertEqual(target.read_bytes(), old)
            self.assertFalse(delivery.read_json(target)["report"]["gate"]["pass"])

    def test_changed_artifacts_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            self.complete_failure(stage)
            (stage / "run/report.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "artifacts changed"):
                delivery.verify(stage, self.binding)

    def test_interruption_does_not_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            (stage / "test.log").write_text("ok")
            delivery.write_json(stage / "test.completed.json", {"binding": self.binding, "exit_code": 0,
                                "log_sha256": delivery.file_digest(stage / "test.log")})
            delivery.write_json(stage / "check.attempt.json", {})
            with patch.object(delivery, "command", side_effect=AssertionError("relaunched")):
                with self.assertRaisesRegex(ValueError, "no automatic retry"):
                    delivery.run_check(stage, self.binding)

    def test_failed_full_test_blocks_check(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            delivery.write_json(stage / "test.completed.json", {"binding": self.binding, "exit_code": 1})
            with self.assertRaisesRegex(ValueError, "full test must pass"):
                delivery.run_check(stage, self.binding)


if __name__ == "__main__":
    unittest.main()
