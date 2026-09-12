"""Temporary-artifact/mocked ops tests; never run a family or emit a real receipt."""
from contextlib import redirect_stdout
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ops/spatial_history"))
spec = importlib.util.spec_from_file_location("r4_v2_ops_under_test", ROOT / "ops/spatial_history/r4_generation_check_v2.py")
ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)


class R4GenerationOpsV2Tests(unittest.TestCase):
    def test_release_requires_exact_reviewed_commit_and_finite_real_quota(self):
        checked, c = {"commit": "a" * 40}, ops.configuration()
        for code, quota in ((None, 8), ("b"*40, 8), ("a"*40, None), ("a"*40, 7), ("a"*40, float("nan")), ("a"*40, float("inf")), ("a"*40, True)):
            with self.subTest(code=code, quota=quota), self.assertRaises(ValueError):
                ops.release_checked(checked, code, quota, c)
        self.assertFalse(ops.release_checked(checked, "a"*40, 8, c)["training_authorized"])

    def test_stage_config_budget_cannot_change_silently(self):
        c = deepcopy(ops.configuration())
        c["limits_proposed"]["family_bytes"] *= 2
        with patch.object(ops, "read", return_value=c), self.assertRaises(ValueError):
            ops.configuration()

    def test_category_shortcut_stops_even_when_family_gates_pass(self):
        from spatial_world_model.r4_families_v2 import ACTIONS, NAMES
        rows = [{"family_id": name} for name in ("r4-39", "r4-47", "r4-25", "r4-03")]
        result = {"accepted": True, "checks": {"physics": True, "replay_equal": True},
                  "success_matrix": {w: {a: a == "c22" for a in ACTIONS} for w in NAMES}}
        results = [deepcopy(result) for _ in rows]
        summary = ops.summary_for(results, rows, ops.configuration())
        self.assertTrue(summary["family_gates_passed"])
        self.assertFalse(summary["accepted"])
        self.assertEqual(summary["categorical_shortcut"]["optimal_index_intersections"]["LL"], [8])
        results[-1]["success_matrix"]["LL"] = {a: a == "c00" for a in ACTIONS}
        summary = ops.summary_for(results, rows, ops.configuration())
        self.assertTrue(summary["accepted"])
        self.assertFalse(summary["remaining_inventory_executable"])
        results[-1]["accepted"] = False
        self.assertFalse(ops.summary_for(results, rows, ops.configuration())["accepted"])

    def test_partial_execution_is_never_restarted(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)/"stage"; (run/"execution").mkdir(parents=True)
            with patch.object(ops, "RUN", run), patch.object(ops, "verify_check", return_value={}), \
                    patch.object(ops, "verify", side_effect=ValueError("incomplete")), patch.object(ops, "supervise") as dispatch:
                with self.assertRaises(ValueError):
                    ops.run("a"*40, 8, 4)
                dispatch.assert_not_called()

    def test_partial_failure_export_preserves_prefix_and_failure_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, report = Path(tmp)/"stage", Path(tmp)/"report.json"
            (run/"execution/r4-39/data/audit/LL").mkdir(parents=True)
            failure = run/"execution/r4-39/data/audit/LL/history_failure.json"
            failure.write_text('{"error":"synthetic render failure"}')
            prefix = run/"execution/r4-39/data/audit/LL/history_prefix.jsonl.gz"
            prefix.write_bytes(b"synthetic incomplete bytes")
            before = ops.inventory(run)
            with patch.object(ops, "RUN", run), patch.object(ops, "REPORT", report), redirect_stdout(io.StringIO()):
                ops.export()
                value = json.loads(report.read_text())
                self.assertEqual(value["status"], "failed_or_incomplete")
                self.assertIsNone(value["export_resources"]["v1_plus_v2_generation_s_upper"])
                self.assertIn(failure.relative_to(run).as_posix(), value["artifacts_json"])
                self.assertEqual(ops.inventory(run), before)
                raw = report.read_bytes(); ops.export(); self.assertEqual(report.read_bytes(), raw)

    def test_bindings_cover_registered_tests_and_contract_dependency(self):
        for name in ops.BOUND:
            self.assertTrue((ROOT/name).is_file(), name)
        self.assertTrue(set(ops.contract_ops.BOUND) <= set(ops.BOUND))
        self.assertEqual(len(ops.test_census()), len(set(ops.test_census())))
        self.assertIn("test_r4_storage.R4StorageTests.test_incomplete_prefix_is_preserved_but_rejected", ops.test_census())
