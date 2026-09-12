"""Server-only receipt/provenance tests in temporary directories, no real data."""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ops/spatial_history"))
ops = importlib.import_module("r4_coverage_check")


def save_receipt(directory, value):
    evidence = sum(p.stat().st_size for p in directory.iterdir() if p.name != "receipt.json")
    for _ in range(10):
        total = evidence + len(ops.encode(value))
        if value["stage_bytes"] == total: break
        value["stage_bytes"] = total
    (directory / "receipt.json").write_bytes(ops.encode(value))


def fixture(directory):
    started = {"stage": ops.STAGE, "commit": "a" * 40, "binding": {"synthetic.py": "fixed"}}
    (directory / "started.json").write_bytes(ops.encode(started))
    (directory / "tests.log").write_text("synthetic pass\n", encoding="utf-8")
    value = {**started, "exit_code": 0, "test_names": ["synthetic.case"], "tests_run": 1,
             "failures": 0, "errors": 0, "skipped": 0, "expected_failures": 0, "unexpected_successes": 0,
             "claims": deepcopy(ops.CLAIMS), "new_simulation_steps": 0, "new_training_steps": 0,
             "new_weight_download_bytes": 0, "elapsed_s": 1.0, "peak_rss_bytes": 1024, "stage_bytes": 0,
             "artifacts": {n: ops.sha((directory/n).read_bytes()) for n in ("started.json", "tests.log")}}
    save_receipt(directory, value)
    return value


class R4CoverageOpsTests(unittest.TestCase):
    def test_configuration_matches_scientific_constants_and_census(self):
        from spatial_world_model import r4_coverage as c
        config = ops.configuration()
        self.assertEqual(config["selection"], c.parameters())
        self.assertEqual(config["sensor"], {k: c.sensor_spec()[k] for k in config["sensor"]})
        self.assertEqual(len(ops.test_names()), len(set(ops.test_names())))
        self.assertEqual(len(ops.BOUND), len(set(ops.BOUND)))

    def test_existing_stage_only_verifies_without_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "failure.json").write_bytes(b"preserve")
            with patch.object(ops, "verify", side_effect=ValueError("failed receipt")) as verify, \
                 patch.object(ops, "inventory", side_effect=AssertionError("must not execute")), patch("builtins.print"):
                with self.assertRaises(ValueError): ops.run(directory)
                verify.assert_called_once_with(directory)
            self.assertEqual((directory / "failure.json").read_bytes(), b"preserve")

    def test_verify_rejects_incomplete_tests_claims_or_resource_receipts(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            original = fixture(directory)
            with patch.object(ops, "configuration"), patch.object(ops, "source_matches_commit"), \
                 patch.object(ops, "test_names", return_value=["synthetic.case"]), patch("builtins.print"):
                ops.verify(directory)
                for field, value in [("skipped", 1), ("expected_failures", 1), ("unexpected_successes", 1),
                                     ("tests_run", 0), ("claims", {}), ("elapsed_s", 301),
                                     ("new_training_steps", 1), ("peak_rss_bytes", 0), ("exit_code", 1)]:
                    broken = deepcopy(original)
                    broken[field] = value
                    save_receipt(directory, broken)
                    with self.subTest(field=field), self.assertRaises(ValueError): ops.verify(directory)

    def test_verify_rejects_evidence_change_or_extra_failure_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            original = fixture(directory)
            with patch.object(ops, "configuration"), patch.object(ops, "source_matches_commit"), \
                 patch.object(ops, "test_names", return_value=["synthetic.case"]), patch("builtins.print"):
                (directory / "tests.log").write_text("changed\n", encoding="utf-8")
                save_receipt(directory, original)
                with self.assertRaises(ValueError): ops.verify(directory)
                fixture(directory)
                (directory / "failure.json").write_text("{}", encoding="utf-8")
                with self.assertRaises(ValueError): ops.verify(directory)

    def test_export_preserves_failure_bytes_and_rejects_different_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "stage"
            directory.mkdir()
            report = Path(temporary) / "report.json"
            (directory / "started.json").write_bytes(b'{"truncated":')
            before = (directory / "started.json").read_bytes()
            with patch.object(ops, "configuration"), patch.object(ops, "verify", side_effect=ValueError("incomplete")), \
                 patch("builtins.print"):
                ops.export(directory, report)
                value = json.loads(report.read_text(encoding="utf-8"))
                self.assertEqual(value["status"], "failed_or_incomplete")
                self.assertIsNone(value["receipt"])
                self.assertEqual(value["source_artifacts"]["started.json"]["sha256"], ops.sha(before))
                ops.export(directory, report)
                report.write_bytes(b"existing report")
                with self.assertRaises(ValueError): ops.export(directory, report)
                self.assertEqual(report.read_bytes(), b"existing report")
            self.assertEqual((directory / "started.json").read_bytes(), before)

    def test_interrupted_new_stage_keeps_failure_and_no_success_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "stage"
            with patch.object(ops, "configuration"), patch.object(ops, "git", side_effect=["", "a" * 40]), \
                 patch.object(ops, "binding", return_value={}), patch.object(ops, "source_matches_commit"), \
                 patch.object(ops, "inventory", side_effect=KeyboardInterrupt("synthetic interrupt")):
                with self.assertRaises(KeyboardInterrupt): ops.run(directory)
            self.assertTrue((directory / "started.json").exists())
            failure = json.loads((directory / "failure.json").read_text(encoding="utf-8"))
            self.assertEqual(failure["exit_code"], 1)
            self.assertIn("KeyboardInterrupt", failure["error"])
            self.assertFalse((directory / "receipt.json").exists())

    def test_recorded_commit_and_current_source_both_have_to_match(self):
        source = {"synthetic.py": ops.sha(b"original")}
        with patch.object(ops, "binding", return_value=source):
            with self.assertRaises(ValueError): ops.source_matches_commit("short", source)
            with self.assertRaises(ValueError): ops.source_matches_commit("a" * 40, {})
            with patch.object(ops.subprocess, "check_output", return_value=b"changed"):
                with self.assertRaises(ValueError): ops.source_matches_commit("a" * 40, source)

    def test_write_budget_is_checked_before_creating_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            target = directory / "new.json"
            with patch.object(ops, "used_bytes", return_value=ops.LIMIT_BYTES):
                with self.assertRaises(ValueError): ops.write_new(directory, target, {"x": 1})
            self.assertFalse(target.exists())
