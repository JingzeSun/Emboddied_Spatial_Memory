"""Server-only actual evaluator integration on one fixed train fixture."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from cpmt.m1_af_rollout import causal_rollout_metrics, ONLINE_CONTEXT_DIM, CANDIDATE_FEATURE_DIM, TEMPLATES
from cpmt.m1_candidate_policy import POLICY
from cpmt.m1_protocol import load_and_validate
from cpmt.m1_rollout import generate_m1_paired_rollout_split
from run_m1_s5_confirmation import evaluation_config


class MergePreference(torch.nn.Module):
    """Test-only deterministic scores from public candidate template features."""
    def forward(self, features):
        slots = features[:, ONLINE_CONTEXT_DIM:].reshape(-1, 16, CANDIDATE_FEATURE_DIM)
        return 10 * slots[:, :, TEMPLATES.index("MERGE")] + slots[:, :, TEMPLATES.index("NOOP")]


class TestCandidatePolicyRollout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        cls.hard = load_and_validate(ROOT / "configs/m1_hard_condition_v7.json")
        _, cls.audits, _ = generate_m1_paired_rollout_split(cls.hard, "train", paired_groups=1)
        cls.cfg = {"device": "cpu", "commit_probability": 0.0, "margin_threshold": 0.0,
                   "current_evidence_scope_ranks": 3}

    def test_oracle_metrics_unchanged_with_extra_diagnostics(self):
        strict, old_rows = causal_rollout_metrics(None, self.audits, self.cfg, oracle=True)
        current, rows = causal_rollout_metrics(None, self.audits,
            {**self.cfg, "candidate_availability_policy": deepcopy(POLICY)}, oracle=True)
        self.assertEqual(strict, {k: v for k, v in current.items() if not k.startswith("candidate_availability")})
        self.assertEqual(current["candidate_availability"]["decisions"], 40)
        self.assertEqual(current["candidate_availability"]["unavailable_slots"], 0)
        self.assertEqual(current["candidate_availability"]["decisions_without_exact_reference_reachable"], 0)
        self.assertEqual(current["candidate_availability"]["c11_missing_legal_contrast_events"], 0)
        self.assertEqual([r["metrics"] for r in rows], [r["metrics"] for r in old_rows])

    def test_actual_evaluator_survives_merge_exhaustion_and_records_missing_slots(self):
        aggregate, rows = causal_rollout_metrics(MergePreference(), self.audits,
            {**self.cfg, "candidate_availability_policy": deepcopy(POLICY)})
        self.assertEqual(aggregate["candidate_availability"]["decisions"], 40)
        self.assertGreater(aggregate["candidate_availability"]["unavailable_slots"], 0)
        for row in rows:
            self.assertEqual(len(row["choices"]), 20)
            self.assertTrue(all(c["selected_static_preflight_pass"] for c in row["choices"]))
            self.assertTrue(all(a["post_graph_hash"] == b["base_graph_hash"]
                                for a, b in zip(row["choices"], row["choices"][1:])))

    def test_saved_model_cannot_enable_policy_without_plan(self):
        plan = {"evaluation": {"commit_probability": 0.0, "margin_threshold": 0.0}}
        config = evaluation_config(self.hard, plan, {"candidate_availability_policy": POLICY})
        self.assertNotIn("candidate_availability_policy", config)
        plan["evaluation"]["candidate_availability_policy"] = deepcopy(POLICY)
        self.assertEqual(evaluation_config(self.hard, plan)["candidate_availability_policy"], POLICY)


if __name__ == "__main__":
    unittest.main()
