"""Tests for the nonformal M1 trainability ladder."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from cpmt.m1_af_rollout import build_rollout_learning_arrays
from cpmt.m1_trainability import (
    observable_accuracy_ceiling,
    reference_candidate_audit,
    resolve_trainability_ladder,
    run_label_rich_capacity_point,
    subset_paired_groups,
)


class TestM1TrainabilityLadder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hard = json.loads(
            (PROJECT / "configs" / "m1_hard_condition.json").read_text(
                encoding="utf-8"
            )
        )
        cls.af = json.loads(
            (PROJECT / "configs" / "m1_af_smoke.json").read_text(encoding="utf-8")
        )
        cls.raw = json.loads(
            (PROJECT / "configs" / "m1_trainability_ladder.json").read_text(
                encoding="utf-8"
            )
        )
        cls.config = resolve_trainability_ladder(cls.hard, cls.af, cls.raw)
        base = cls.config["base_af_config"]
        cls.arrays, cls.audits, _ = build_rollout_learning_arrays(
            cls.hard, "train", paired_groups=2,
            future_hash_bins=int(base["future_hash_bins"]),
        )

    def test_config_remains_nonformal_and_test_sealed(self):
        opened = deepcopy(self.raw)
        opened["test_access"] = True
        with self.assertRaisesRegex(ValueError, "test-sealed"):
            resolve_trainability_ladder(self.hard, self.af, opened)
        formal = deepcopy(self.raw)
        formal["formal_run"] = True
        with self.assertRaisesRegex(ValueError, "nonformal"):
            resolve_trainability_ladder(self.hard, self.af, formal)

    def test_subset_keeps_complete_siblings_and_rows(self):
        arrays, audits = subset_paired_groups(self.arrays, self.audits, 1)
        self.assertEqual(len(audits), 2)
        self.assertEqual(len(arrays["y"]), 40)
        self.assertEqual(set(arrays["group"].tolist()), {0})
        self.assertEqual({audit["sibling_index"] for audit in audits}, {0, 1})

    def test_reference_coverage_and_observable_ceiling_are_explicit(self):
        arrays, audits = subset_paired_groups(self.arrays, self.audits, 1)
        audit = reference_candidate_audit(audits)
        self.assertEqual(audit["candidate_reference_coverage"], 1.0)
        self.assertEqual(audit["candidate_miss_rate"], 0.0)
        self.assertEqual(audit["illegal_reference_rate"], 0.0)
        self.assertAlmostEqual(observable_accuracy_ceiling(arrays), 0.975)

    def test_label_rich_capacity_point_runs_without_claiming_oracle(self):
        arrays, audits = subset_paired_groups(self.arrays, self.audits, 1)
        base = deepcopy(self.config["base_af_config"])
        metrics, _, _ = run_label_rich_capacity_point(
            arrays, audits, base, student_steps=2, seed=7,
        )
        self.assertEqual(metrics["label_fraction"], 1.0)
        self.assertEqual(metrics["observable_accuracy_ceiling"], 0.975)
        self.assertGreater(metrics["student_parameters"], 0)
        self.assertIn("final_post_graph_correctness", metrics["causal_rollout"])


if __name__ == "__main__":
    unittest.main()
