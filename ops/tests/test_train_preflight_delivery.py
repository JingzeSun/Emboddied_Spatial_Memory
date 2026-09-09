"""Filesystem/command lifecycle checks with tiny synthetic reports, no rollouts."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("preflight_delivery", ROOT / "ops/m1_train_preflight.py")
delivery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(delivery)
from cpmt.m1_branch_preflight import GROUPS, POLICIES, fixed_plan, summarize


class TestPreflightDelivery(unittest.TestCase):
    def fixture(self, stage, failed=False, write_completion=True):
        run = stage / "run"; run.mkdir()
        binding = {"generation_marker_sha256": "marker", "source_and_tests_sha256": "source"}
        groups = []
        for group in GROUPS:
            path = run / f"group_{group:06d}"; path.mkdir()
            row = {"group": group, "status": "pass", "branches": [
                {"group": group, "sibling": sibling, "policy": policy, "completed_steps": 20}
                for sibling in (0, 1) for policy in POLICIES]}
            if failed and group == 0:
                row.update(status="failed", branches=[], failure={"message": "fixture C11 failure"})
                delivery.write_json(path / "failure_snapshot.json", {"base_world": {"graph_hash": "failed-base"}})
            delivery.write_json(path / "result.json", row)
            groups.append({**row, "files": delivery.artifact_hashes(path)})
        report = {"schema_version": "cpmt-train-branch-preflight-report-v1",
                  "binding": {**binding, "plan": fixed_plan(), "train_arrays_digest": delivery.TRAIN_DIGEST},
                  "provenance": {"git_dirty": False}, "groups": groups, "gate": summarize(groups),
                  "validation_access": False, "test_access": False, "training_performed": False,
                  "model_selection_performed": False, "scientific_acceptance_gate_changed": False}
        delivery.write_json(run / "report.json", report)
        if write_completion:
            delivery.write_json(stage / "completion.json", {"binding": binding, "exit_code": 1 if failed else 0,
                                                             "files": delivery.artifact_hashes(run)})
        return binding, report

    def test_fresh_command_records_exit_log_and_verified_report(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory)
            binding = {"generation_marker_sha256": "marker", "source_and_tests_sha256": "source"}
            owner = self
            class Process:
                stdout = ["fixture child progress\n"]
                def __enter__(self):
                    owner.fixture(stage, write_completion=False)
                    return self
                def __exit__(self, *args):
                    return False
                def wait(self):
                    return 0
            with patch.object(delivery.subprocess, "Popen", return_value=Process()) as start:
                self.assertEqual(delivery.run_check(stage, binding, 2), 0)
                command = start.call_args.args[0]
                self.assertEqual(command[-2:], ["--workers", "2"])
            self.assertEqual(delivery.read_json(stage / "completion.json")["exit_code"], 0)
            self.assertIn("fixture child progress", (stage / "check.log").read_text())

    def test_verified_success_is_reused_without_a_process(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory); binding, _ = self.fixture(stage)
            with patch.object(delivery.subprocess, "Popen", side_effect=AssertionError("must not start")):
                self.assertEqual(delivery.run_check(stage, binding, 1), 0)

    def test_failed_completed_check_exports_snapshot_and_stays_failed(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory); binding, report = self.fixture(stage, failed=True)
            with patch.object(delivery.subprocess, "Popen", side_effect=AssertionError("must not restart")):
                self.assertEqual(delivery.run_check(stage, binding, 1), 1)
            target = stage / "export.json"
            with patch.object(delivery, "capture_run_provenance", return_value={"git_dirty": False}):
                delivery.export(stage, binding, {"arrays_digest": delivery.TRAIN_DIGEST}, target)
                first = target.read_bytes()
                delivery.export(stage, binding, {"arrays_digest": delivery.TRAIN_DIGEST}, target)
                self.assertEqual(target.read_bytes(), first)
            exported = delivery.read_json(target)
            self.assertFalse(exported["report"]["gate"]["pass"])
            self.assertIn("group_000000/failure_snapshot.json", exported["failure_diagnostics"])

    def test_changed_files_cannot_be_exported(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory); binding, _ = self.fixture(stage)
            (stage / "run/group_000000/result.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "files changed"):
                delivery.verify_completion(stage, binding)

    def test_interrupted_attempt_does_not_spawn_or_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory)
            delivery.write_json(stage / "attempt.json", {"old": True})
            with patch.object(delivery.subprocess, "Popen", side_effect=AssertionError("must not restart")):
                with self.assertRaisesRegex(ValueError, "no automatic restart"):
                    delivery.run_check(stage, {}, 1)
            self.assertEqual(delivery.read_json(stage / "attempt.json"), {"old": True})

    def test_source_change_does_not_reuse_report(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory); binding, _ = self.fixture(stage)
            changed = {**binding, "source_and_tests_sha256": "other-source"}
            with self.assertRaisesRegex(ValueError, "binding changed"):
                delivery.verify_completion(stage, changed)

    def test_zero_exit_without_report_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory)
            delivery.write_json(stage / "completion.json", {"binding": {}, "exit_code": 0, "files": {}})
            with self.assertRaisesRegex(ValueError, "success without a report"):
                delivery.verify_completion(stage, {})


if __name__ == "__main__":
    unittest.main()
