"""D-224 / S2-05 tests: the pre-registered reading of ruling 82-1 on hand-made merged audits of five seeds per arm.

Four same-signed gaps whose mean exceeds their spread read as an established order (in the metric's own direction);
three against two, or a mean inside the spread, read as not distinguishable; a missing seed is refused.  CPU only.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "ops" / "vsmt"))

import ruling82_seed_analysis as seeds  # noqa: E402

HOUSES = [f"h{i:02d}" for i in range(10)]


def merged(f1: float, mrr: float = 0.3):
    return {"per_episode": [{"episode_id": h, "report": {
        "node_prf1": {"node_f1": f1}, "node_prf1_iou": {"node_f1": f1 / 2}, "missing_residual_rate": {"missing_residual_rate": mrr},
        "identity_continuity": {"identity_continuity": 0.5}, "contamination_auc": {"contamination_auc": 0.4},
        "recovery_latency_frames": {"recovery_latency_frames": 100.0}, "false_retract_rate_in_scope": {"false_retract_rate": 0.4},
        "false_retract_rate": {"false_retract_rate": 0.6}}} for h in HOUSES],
        "pooled_loss_tally": {"uncarried_seen_object_frames": 100, "intervals": {"wrong_bind": {"frames": 45}}}}


def groups(vsmt_f1, assoc_f1, vsmt_mrr=None, assoc_mrr=None):
    out = {}
    for index, seed in enumerate(seeds.SEEDS):
        out[("VSMT-lean", seed)] = merged(vsmt_f1[index], mrr=(vsmt_mrr or [0.3] * 5)[index])
        out[("AssocOnly", seed)] = merged(assoc_f1[index], mrr=(assoc_mrr or [0.3] * 5)[index])
    return out


class SeedAnalysisTests(unittest.TestCase):
    def test_four_same_signed_gaps_above_their_spread_establish_the_order(self) -> None:
        out = seeds.analyse(groups([0.82, 0.79, 0.80, 0.81, 0.77], [0.78, 0.72, 0.81, 0.78, 0.72]))
        node = out["metrics"]["node_prf1"]["seed_paired_gaps"]
        self.assertEqual((node["positive"], node["negative"]), (4, 1))
        self.assertTrue(node["established"])
        self.assertEqual(node["order"], "VSMT-lean_better")
        self.assertAlmostEqual(out["metrics"]["node_prf1"]["seed_spread"]["VSMT-lean"]["mean"], 0.798)
        self.assertEqual(out["summary"]["node_prf1"], "VSMT-lean_better")
        self.assertAlmostEqual(out["loss_tally"]["VSMT-lean:7"]["wrong_bind_frame_share"], 0.45)

    def test_a_lower_is_better_metric_reads_in_its_own_direction(self) -> None:
        out = seeds.analyse(groups([0.8] * 5, [0.8] * 5, vsmt_mrr=[0.10, 0.12, 0.11, 0.13, 0.12], assoc_mrr=[0.30, 0.32, 0.31, 0.29, 0.33]))
        self.assertEqual(out["metrics"]["missing_residual_rate"]["seed_paired_gaps"]["order"], "VSMT-lean_better")
        self.assertEqual(out["metrics"]["node_prf1"]["seed_paired_gaps"]["order"], "not_distinguishable_on_the_development_set")

    def test_flipping_gaps_are_not_distinguishable_and_a_missing_seed_is_refused(self) -> None:
        # the three draws seen so far (-0.071, +0.039, +0.069) plus two more of mixed sign
        out = seeds.analyse(groups([0.715, 0.820, 0.789, 0.75, 0.76], [0.786, 0.782, 0.720, 0.77, 0.74]))
        node = out["metrics"]["node_prf1"]["seed_paired_gaps"]
        self.assertFalse(node["established"])
        self.assertEqual(node["order"], "not_distinguishable_on_the_development_set")
        broken = groups([0.8] * 5, [0.8] * 5)
        del broken[("AssocOnly", 59)]
        with self.assertRaises(ValueError):
            seeds.analyse(broken)


if __name__ == "__main__":
    unittest.main()
