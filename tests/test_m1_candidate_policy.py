"""Saved-graph metadata tests; no rollout generation or model training."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cpmt.m1_candidate_policy import POLICY, validate_candidate_policy, step_availability, summarize_availability
from cpmt.m1_rollout import generate_fixed_candidates, _execute_candidates


class TestCandidatePolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        report = json.loads((ROOT / "results/m1_v7_d051_train_branch_preflight.json").read_text())
        cls.saved = report["failure_diagnostics"]["group_000066/failure_snapshot.json"]

    def materialized(self):
        base, event = self.saved["base_world"], self.saved["event"]
        programs, evidence, _ = generate_fixed_candidates(base, event, allow_unavailable=True)
        return {"online": {"prior_world": base, "candidate_programs": programs},
                "executed_candidates": _execute_candidates(base, programs, evidence)}

    def test_policy_file_matches_code_and_rejects_semantic_drift(self):
        self.assertEqual(validate_candidate_policy(json.loads(
            (ROOT / "configs/m1_candidate_availability_policy.json").read_text())), POLICY)
        changed = deepcopy(POLICY)
        changed["c11_missing_target"] = "drop_failed_steps"
        with self.assertRaises(ValueError):
            validate_candidate_policy(changed)

    def test_c11_unavailable_is_not_executor_failure_and_keeps_denominator(self):
        material = self.materialized()
        row = step_availability(material, self.saved["event"], self.saved["base_world"], is_c11=True)
        self.assertEqual(row["unavailable_slot_count"], 1)
        self.assertEqual(row["constructed_candidate_count"], 15)
        self.assertFalse(row["c11_scope_target_available"])
        self.assertFalse(row["c11_legal_collateral_contrast_available"])
        self.assertTrue(row["exact_reference_reachable"])  # NOOP reaches this test's reference.
        expected = sum(not c["legal"] for c in material["executed_candidates"]
                       if c.get("slot_status") != "unavailable")
        self.assertEqual(row["executor_illegal_candidate_count"], expected)
        summary = summarize_availability([{"candidate_availability": row}])
        self.assertEqual(summary["decisions"], 1)
        self.assertEqual(summary["c11_events"], 1)
        self.assertEqual(summary["c11_legal_contrast_availability_rate"], 0)
        self.assertFalse(summary["scientific_metric_denominators_changed"])

    def test_empty_c11_denominator_is_null(self):
        summary = summarize_availability([])
        self.assertEqual(summary["c11_events"], 0)
        self.assertIsNone(summary["c11_legal_contrast_availability_rate"])
        self.assertIsNone(summary["exact_reference_unreachable_rate"])

    def test_unavailable_cannot_become_selectable(self):
        material = self.materialized()
        missing = next(c for c in material["executed_candidates"] if c.get("slot_status") == "unavailable")
        missing["static_preflight_pass"] = True
        with self.assertRaisesRegex(ValueError, "unavailable slot"):
            step_availability(material, self.saved["event"], self.saved["base_world"], is_c11=True)


if __name__ == "__main__":
    unittest.main()
