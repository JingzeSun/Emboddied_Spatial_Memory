"""Server-only provenance and reuse regression checks for the reader stage."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ops/spatial_history"))
import public_input_check as ops


class PublicInputOpsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def test_nested_receipts_are_part_of_output_manifest(self):
        (self.directory / "receipt.json").write_text("root")
        nested = self.directory / "nested"
        nested.mkdir()
        (nested / "receipt.json").write_text("nested")
        self.assertEqual(set(ops.manifest(self.directory)), {"nested/receipt.json"})

    def test_existing_failed_or_interrupted_run_is_not_restarted(self):
        sentinel = self.directory / "started.json"
        sentinel.write_text("preserved")
        with patch.object(ops, "verify", side_effect=ValueError("interrupted")), \
                patch.object(ops, "source_inputs") as source, patch.object(ops.subprocess, "run") as child:
            with self.assertRaises(ValueError):
                ops.run(self.directory, ops.SOURCE)
            source.assert_not_called()
            child.assert_not_called()
        self.assertEqual(sentinel.read_text(), "preserved")

    def test_original_source_rejects_revision_expression_and_wrong_digest(self):
        with self.assertRaises(ValueError):
            ops.original_binding("HEAD:README.md", {})
        with patch.object(ops.subprocess, "check_output", return_value=b"changed"):
            with self.assertRaises(ValueError):
                ops.original_binding("a" * 40, {"some.py": "0" * 64})

    def test_source_metadata_cannot_substitute_another_r2_run(self):
        report = json.loads((ops.ROOT / ops.R2_REPORT).read_text(encoding="utf-8"))
        (self.directory / "started.json").write_text(json.dumps({**report["audit"]["started"], "commit": "0" * 40}))
        with patch.object(ops, "original_binding"):
            with self.assertRaisesRegex(ValueError, "started.json differs"):
                ops.source_inputs(self.directory)

    def test_export_is_idempotent_and_never_overwrites_different_report(self):
        saved = {"exit_code": 1}
        (self.directory / "receipt.json").write_text(json.dumps(saved))
        (self.directory / "started.json").write_text("{}")
        report = self.directory / "export.json"
        with patch.object(ops, "verify", return_value=saved):
            ops.export(self.directory, report)
            raw = report.read_bytes()
            ops.export(self.directory, report)
            self.assertEqual(report.read_bytes(), raw)
            report.write_text("preserve a different report")
            with self.assertRaises(ValueError):
                ops.export(self.directory, report)
            self.assertEqual(report.read_text(), "preserve a different report")

    def test_query_census_rejects_missing_and_duplicate_world_action(self):
        rows = []
        for w in ("LL", "LR", "RL", "RR"):
            for action in ("LL", "LR", "RL", "RR"):
                for mode in ("full", "recent"):
                    rows.append({"world": w, "action": action, "mode": mode,
                                 "query_sha256": action if mode == "recent" else w + action,
                                 "history_sha256": "recent" if mode == "recent" else w,
                                 "controls_sha256": action, "goal_sha256": "goal",
                                 "history_frames": 121 if mode == "full" else 2,
                                 "control_steps": 200, "query_keys": ["controls", "goal", "history"]})
        self.assertTrue(all(ops.query_checks(rows).values()))
        self.assertFalse(ops.query_checks(rows[:-1])["complete_32_query_inventory"])
        self.assertFalse(ops.query_checks(rows[:-1] + [rows[0]])["complete_32_query_inventory"])


if __name__ == "__main__":
    unittest.main()
