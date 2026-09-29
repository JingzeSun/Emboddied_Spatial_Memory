"""D-224 / S2-05 tests: the ruling 87-2 two-tier reading of the tau_r sweep on hand-made merged audits.

Tier A needs a tau whose five-seed Missing residual is within 0.178, a node F1 drop and a kept-share drop against the
arm's own tau 0.5 within 0.03 and 0.05, and AssocOnly not established better; tier B, at the passing tau with the
lowest Missing residual, needs VSMT-lean's kept share established above NoVersion's and most of its extra kept objects
coming back from a retracted carrier.  A missing group is refused.  CPU only.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "ops" / "vsmt"))

import ruling87_sweep_analysis as sweep  # noqa: E402

HOUSES = ("h1", "h2")


def merged(f1: float, mrr: float, kept: int, *, from_retracted: int = 0, objects: int = 10):
    """Two houses with the given house values; ``objects`` first re-observations, the first ``kept`` kept."""

    reports = {h: {"node_prf1": {"node_f1": f1}, "missing_residual_rate": {"missing_residual_rate": mrr},
                   "identity_continuity": {"identity_continuity": 0.4}, "false_retract_rate_in_scope": {"false_retract_rate": 0.5},
                   "contamination_auc": {"contamination_auc": 0.3}} for h in HOUSES}
    records = []
    for i in range(objects):
        is_kept = i < kept
        state = ("retracted" if i < from_retracted else "dormant") if is_kept else None
        records.append({"ordinal": i, "judged": True, "category": "kept" if is_kept else "chose_birth", "chosen_carrier_state": state})
    return {"schema_version": "vsmt-s2-05-node-audit-merged-v8",
            "per_episode": [{"episode_id": "h1", "report": reports["h1"], "identity_attribution": records},
                            {"episode_id": "h2", "report": reports["h2"], "identity_attribution": []}]}


def world(*, mrr_at: dict, noversion_kept: int = 4, vsmt_kept: int = 5, from_retracted: int = 3):
    sweep_groups, reference = {}, {}
    for seed in sweep.SEEDS:
        reference[("VSMT-lean", seed)] = merged(0.80, 0.35, 5)
        reference[("AssocOnly", seed)] = merged(0.79, 0.30, 5)
        for tau in sweep.TAUS:
            sweep_groups[("VSMT-lean", seed, tau)] = merged(0.79, mrr_at.get(tau, 0.30), vsmt_kept, from_retracted=from_retracted)
            sweep_groups[("NoVersion", seed, tau)] = merged(0.79, mrr_at.get(tau, 0.30), noversion_kept)
    return sweep_groups, reference


class SweepReadingTests(unittest.TestCase):
    def test_tier_a_at_the_low_mrr_tau_and_tier_b_from_retracted_carriers(self) -> None:
        # MRR within the line at 0.2 and 0.15; 0.2 is lower -> chosen; each seed VSMT-lean keeps one more object than
        # NoVersion; the extra kept object (ordinal 4) comes back from a retracted carrier (the first three kept objects too)
        groups, reference = world(mrr_at={0.2: 0.12, 0.15: 0.15}, from_retracted=5)
        # vary the NoVersion gap per seed so the 82-1 rule has a spread (4/5 positive and mean above sd)
        for seed, nv_kept in zip(sweep.SEEDS, (4, 4, 3, 4, 5)):
            groups[("NoVersion", seed, 0.2)] = merged(0.79, 0.12, nv_kept)
        out = sweep.analyse(groups, reference)
        self.assertEqual(out["tier_a"]["passing_taus"], [0.15, 0.2])
        self.assertEqual(out["tier_b"]["tau"], 0.2)
        checks = out["per_tau"]["0.2"]["checks"]
        self.assertAlmostEqual(checks["mrr_five_seed_mean"], 0.12)
        self.assertAlmostEqual(statistics_mean(checks["node_f1_minus_own_tau_0_5"]), -0.01)
        self.assertEqual(checks["kept_share_vs_noversion"]["order"], "left_better")
        self.assertEqual(checks["vsmt_lean_only_kept"]["of_which_from_retracted"], checks["vsmt_lean_only_kept"]["kept_by_vsmt_lean_only"])
        self.assertEqual(out["verdict"], "tier_a_and_tier_b_hold")

    def test_tier_a_holds_but_no_reversibility_evidence(self) -> None:
        groups, reference = world(mrr_at={0.25: 0.17}, noversion_kept=5, vsmt_kept=5)
        out = sweep.analyse(groups, reference)
        self.assertEqual(out["tier_a"]["passing_taus"], [0.25])
        self.assertFalse(out["tier_b"]["tier_b"])
        self.assertEqual(out["verdict"], "tier_a_holds_tier_b_fails_threshold_was_conservative_reversibility_unsupported")

    def test_self_protection_and_the_mrr_line_can_each_stop_the_round(self) -> None:
        groups, reference = world(mrr_at={})
        self.assertEqual(sweep.analyse(groups, reference)["verdict"], "tier_a_fails_second_consecutive_miss_stop_revisions")
        # MRR fine, but the kept share falls from 0.5 to 0.3 against the arm's own tau 0.5 (drop 0.2 > 0.05)
        groups, reference = world(mrr_at={0.2: 0.1}, vsmt_kept=3, noversion_kept=2)
        out = sweep.analyse(groups, reference)
        self.assertFalse(out["per_tau"]["0.2"]["checks"]["kept_share_drop_ok"])
        self.assertFalse(out["tier_a"]["holds"])
        broken = dict(groups)
        del broken[("NoVersion", 59, 0.3)]
        with self.assertRaises(ValueError):
            sweep.analyse(broken, reference)


def statistics_mean(values):
    return sum(values) / len(values)


if __name__ == "__main__":
    unittest.main()
