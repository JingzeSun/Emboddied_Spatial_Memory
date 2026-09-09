"""Local metadata tests for read-only reuse delivery and failure preservation."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("policy_delivery", ROOT / "ops/m1_candidate_policy.py")
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)


class TestPolicyDelivery(unittest.TestCase):
    binding = {"source_and_tests_sha256": "fixture"}

    def fixture(self, stage):
        (stage / "test.log").write_text("ok\n")
        delivery.write(stage / "test.completed.json", {"binding": self.binding, "exit_code": 0,
                       "log_sha256": delivery.file_digest(stage / "test.log")})
        report = {"accepted": False, "error": "changed shard", "source_and_tests_sha256": "fixture"}
        delivery.write(stage / "reuse.report.json", report)
        delivery.write(stage / "reuse.completed.json", {"binding": self.binding, "exit_code": 1,
                       "report_sha256": delivery.file_digest(stage / "reuse.report.json")})

    def test_completed_failure_is_not_retried(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            self.fixture(stage)
            with patch.object(delivery, "validate_train_reuse", side_effect=AssertionError("retried")):
                self.assertEqual(delivery.reuse(stage, self.binding), 1)

    def test_failure_export_reuses_exact_payload(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            self.fixture(stage)
            with patch.object(delivery, "EXPORT", stage / "export.json"):
                self.assertEqual(delivery.export(stage, self.binding), 0)
                self.assertEqual(delivery.export(stage, self.binding), 0)
                self.assertFalse(delivery.read(stage / "export.json")["report"]["accepted"])

    def test_completed_report_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            self.fixture(stage)
            (stage / "reuse.report.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "report changed"):
                delivery.verified(stage, self.binding)


if __name__ == "__main__":
    unittest.main()
