"""Server checks for immutable steps, budget stopping, and failure export.

These checks exercise orchestration with tiny temporary files/subprocesses only.
They neither create physical branches nor certify the engineering hypothesis.
"""
import importlib
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ops/spatial_history"))
ops = importlib.import_module("two_gate_check")


class TwoGateOpsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.started = {"commit": "a" * 40, "binding": {"source.py": "b" * 64},
                        "test_names": ["example.Tests.test_required"]}

    def tearDown(self):
        self.temporary.cleanup()

    def unit(self, name="check", exit_code=0, result=None):
        unit = self.directory / name
        unit.mkdir()
        (unit / "run.log").write_text("complete\n", encoding="utf-8")
        if result is not None:
            ops.write_new(unit / "result.json", result)
        receipt = {"stage": ops.STAGE, "step_id": name, "commit": self.started["commit"],
                   "binding": self.started["binding"], "exit_code": exit_code,
                   "artifacts": ops.manifest(unit)}
        ops.write_new(unit / "receipt.json", receipt)
        return unit

    def test_sealed_step_detects_output_tampering(self):
        unit = self.unit()
        self.assertEqual(ops.sealed(unit, self.started)["exit_code"], 0)
        (unit / "run.log").write_text("tampered\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "artifacts changed"):
            ops.sealed(unit, self.started)

    def test_nested_receipts_are_not_exempt_from_manifest(self):
        (self.directory / "data").mkdir()
        (self.directory / "data/receipt.json").write_text("{}", encoding="utf-8")
        (self.directory / "receipt.json").write_text("{}", encoding="utf-8")
        entries = ops.manifest(self.directory)
        self.assertIn("data/receipt.json", entries)
        self.assertNotIn("receipt.json", entries)

    def test_partial_step_is_preserved_without_retry(self):
        unit = self.directory / "primary-LL-LL"
        unit.mkdir()
        (unit / "partial.bin").write_bytes(b"partial evidence")
        before = ops.manifest(unit)
        with self.assertRaisesRegex(ValueError, "no automatic retry"):
            ops.sealed(unit, self.started)
        self.assertEqual(ops.manifest(unit), before)

    def test_receipt_from_different_source_is_rejected(self):
        unit = self.unit()
        with self.assertRaisesRegex(ValueError, "source mismatch"):
            ops.sealed(unit, {**self.started, "commit": "c" * 40})

    def test_failed_check_cannot_authorize_generation(self):
        self.unit(exit_code=1)
        with self.assertRaisesRegex(ValueError, "check failed"):
            ops.completed_tests(self.directory, self.started)

    def test_incomplete_test_inventory_is_rejected(self):
        self.unit(result={"test_names": [], "tests_run": 0, "exit_code": 0,
                          "failures": 0, "errors": 0, "skipped": 0, "egl": {"status": "passed"}})
        with self.assertRaisesRegex(ValueError, "incomplete test receipt"):
            ops.completed_tests(self.directory, self.started)

    def test_missing_egl_evidence_is_rejected(self):
        self.unit(result={"test_names": self.started["test_names"], "tests_run": 1, "exit_code": 0,
                          "failures": 0, "errors": 0, "skipped": 0, "egl": {"status": "failed"}})
        with self.assertRaisesRegex(ValueError, "EGL context"):
            ops.completed_tests(self.directory, self.started)

    def test_write_reservation_stops_before_over_budget_write(self):
        (self.directory / "saved.bin").write_bytes(b"12345")
        budget = ops.Budget(self.directory, 10, 60, reserve_bytes=1)
        budget.check(reserve_bytes=4)
        with self.assertRaisesRegex(ValueError, "output budget"):
            budget.check(reserve_bytes=5)
        self.assertEqual(ops.size(self.directory), 5)

    def test_wall_clock_budget_checked_without_output(self):
        with patch.object(ops.time, "monotonic", side_effect=[0.0, 2.0]):
            budget = ops.Budget(self.directory, 100, 1, reserve_bytes=0)
            with self.assertRaisesRegex(ValueError, "wall-clock"):
                budget.check()

    def test_silent_child_is_stopped_by_watchdog(self):
        budget = ops.Budget(self.directory, 1024 * 1024, 0.1, reserve_bytes=0)
        before = time.monotonic()
        with patch.object(ops, "stop_process", wraps=ops.stop_process) as stopping:
            with self.assertRaisesRegex(ValueError, "wall-clock"):
                ops.bounded_stream([sys.executable, "-c", "import time; time.sleep(60)"],
                                   self.directory / "silent.log", dict(os.environ), budget)
            self.assertIsNotNone(stopping.call_args.args[0].poll())
        self.assertLess(time.monotonic() - before, 10)
        self.assertTrue((self.directory / "silent.log").exists())

    def test_child_exit_code_and_failure_text_are_preserved(self):
        budget = ops.Budget(self.directory, 1024 * 1024, 10, reserve_bytes=0)
        log = self.directory / "child.log"
        code = ops.bounded_stream([sys.executable, "-c", "print('intentional failure'); raise SystemExit(7)"],
                                  log, dict(os.environ), budget)
        self.assertEqual(code, 7)
        self.assertIn("intentional failure", log.read_text(encoding="utf-8"))

    def test_export_failure_is_idempotent_and_refuses_overwrite(self):
        report = self.directory / "report.json"
        audit = {"status": "failed", "steps": [{"status": "interrupted"}]}
        with patch.object(ops, "inspect", return_value=audit):
            ops.export(self.directory, report)
            first = report.read_bytes()
            ops.export(self.directory, report)
            self.assertEqual(first, report.read_bytes())
        self.assertEqual(json.loads(first)["audit"]["status"], "failed")
        with patch.object(ops, "inspect", return_value={"status": "passed"}):
            with self.assertRaisesRegex(ValueError, "different report"):
                ops.export(self.directory, report)
        self.assertEqual(first, report.read_bytes())

    def test_historical_commit_syntax_blocks_git_revision_expressions(self):
        with patch.object(ops.subprocess, "check_output") as command:
            with self.assertRaisesRegex(ValueError, "invalid source commit"):
                ops.original_binding("HEAD:other", {"source.py": "b" * 64})
        command.assert_not_called()

    def test_log_tail_keeps_partial_failure_evidence(self):
        unit = self.directory / "failed"
        unit.mkdir()
        (unit / "run.log").write_bytes(b"x" * 17000 + b"failure-end")
        tail = ops.log_tail(unit)["run.log"]
        self.assertEqual(len(tail), 16000)
        self.assertTrue(tail.endswith("failure-end"))

    def test_frozen_approval_accepts_only_reviewed_scientific_values(self):
        active = ops.read(ROOT / ops.CONFIG)
        proposal = (ROOT / ops.PROPOSAL).read_bytes()
        ops.validate_frozen_config(active, proposal)
        for field, change in (
            ("threshold", lambda c: c["engineering_audit"].update(minimum_fixed_single_view_information_regret=0.125)),
            ("control", lambda c: c["controls"]["phase_vx_mps"]["LR"].__setitem__(6, 0.03)),
            ("budget", lambda c: c["budget_proposal"].update(generation_wall_clock_limit_s=3600)),
        ):
            with self.subTest(field=field):
                changed = deepcopy(active)
                change(changed)
                with self.assertRaisesRegex(ValueError, "scientific configuration differs"):
                    ops.validate_frozen_config(changed, proposal)

    def test_changing_both_proposal_and_active_cannot_reapprove_threshold(self):
        active = ops.read(ROOT / ops.CONFIG)
        proposal = ops.read(ROOT / ops.PROPOSAL)
        active["engineering_audit"]["minimum_fixed_single_view_information_regret"] = 0.125
        proposal["engineering_audit"]["minimum_fixed_single_view_information_regret"] = 0.125
        changed_bytes = ops.encode(proposal)
        active["proposal_sha256"] = ops.sha(changed_bytes)
        with self.assertRaisesRegex(ValueError, "proposal digest/path"):
            ops.validate_frozen_config(active, changed_bytes)

    def test_historical_verification_rejects_missing_registered_step(self):
        config = ops.read(ROOT / ops.CONFIG)
        environment = {"test_fixture": True}
        started = {"stage": ops.STAGE, "commit": "a" * 40,
                   "binding": {name: "b" * 64 for name in ops.BOUND},
                   "model_training_steps": 0, "config": config, "config_sha256": ops.sha(ops.encode(config)),
                   "environment_sha256": ops.sha(ops.encode(environment)), "step_ids": ops.step_ids(config)}
        ops.write_new(self.directory / "environment.json", environment)
        ops.write_new(self.directory / "started.json", started)
        with patch.object(ops, "original_binding"), patch.object(ops.subprocess, "check_output", return_value=ops.encode(config)):
            self.assertEqual(ops.stage(self.directory, historical=True)["step_ids"], started["step_ids"])
            del started["step_ids"][4]  # Omit a real primary branch without altering source/config evidence.
            (self.directory / "started.json").write_bytes(ops.encode(started))
            with self.assertRaisesRegex(ValueError, "registered step plan changed"):
                ops.stage(self.directory, historical=True)


if __name__ == "__main__":
    unittest.main()
