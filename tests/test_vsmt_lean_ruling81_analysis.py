"""D-224 / S2-05 tests: the pre-registered reading of ruling 81-2 on hand-made merged audits.

A clear improvement with every protective metric inside its seed noise reads effective; the same improvement with
Missing residual worsened beyond its noise reads not effective; an improvement inside the seed noise reads not improved;
the bootstrap interval is deterministic under its registered seed.  CPU only.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "ops" / "vsmt"))

import ruling81_analysis as analysis  # noqa: E402

HOUSES = [f"h{i:02d}" for i in range(12)]


def merged(f1, *, mrr=0.2, ic=0.5, auc=0.4, frr=0.3, wrong_bind_frames=10):
    episodes = []
    for index, house in enumerate(HOUSES):
        wiggle = 0.001 * (index % 3)
        episodes.append({"episode_id": house, "report": {
            "node_prf1": {"node_f1": f1 + wiggle}, "node_prf1_iou": {"node_f1": f1 / 2},
            "missing_residual_rate": {"missing_residual_rate": mrr}, "identity_continuity": {"identity_continuity": ic},
            "contamination_auc": {"contamination_auc": auc}, "false_retract_rate_in_scope": {"false_retract_rate": frr},
            "false_retract_rate": {"false_retract_rate": frr + 0.3}, "recovery_latency_frames": {"recovery_latency_frames": 100.0}}})
    return {"per_episode": episodes, "pooled_loss_tally": {
        "events": [["wrong_bind", "never_intervened", 3], ["retract", "move", 1]], "uncarried_seen_object_frames": 100,
        "uncarried_without_loss_event_frames": 100 - wrong_bind_frames - 5,
        "intervals": {"wrong_bind": {"frames": wrong_bind_frames}, "retract": {"frames": 5}}}}


def groups(*, vsmt_b=0.75, vsmt_c=0.70, vsmt_b_mrr=0.2):
    return {
        "VSMT-lean-A7": merged(0.70), "VSMT-lean-A19": merged(0.702, mrr=0.21), "VSMT-lean-B": merged(vsmt_b, mrr=vsmt_b_mrr),
        "VSMT-lean-C": merged(vsmt_c), "AssocOnly-A7": merged(0.78), "AssocOnly-A19": merged(0.781), "AssocOnly-B": merged(0.79),
        "AssocOnly-C": merged(0.78),
    }


class RulingEightyOneAnalysisTests(unittest.TestCase):
    def test_a_clear_improvement_inside_every_noise_band_reads_effective(self) -> None:
        out = analysis.analyse(groups())
        primary = out["aggregation_improves_vsmt_lean"]
        self.assertAlmostEqual(primary["b_minus_c_node_f1"]["mean"], 0.05)
        self.assertAlmostEqual(primary["seed_noise"], 0.002)
        self.assertTrue(primary["improved"])
        self.assertTrue(out["verdict"]["effective"])
        self.assertAlmostEqual(out["lifecycle_gap_to_assoconly"]["mean_gap"]["C"], -0.08)
        self.assertAlmostEqual(out["lifecycle_gap_to_assoconly"]["mean_gap"]["B"], -0.04)
        self.assertTrue(out["lifecycle_gap_to_assoconly"]["halved_development_target"])
        self.assertAlmostEqual(out["loss_tally"]["VSMT-lean-B"]["wrong_bind_frame_share"], 0.1)
        self.assertEqual(out["loss_tally"]["VSMT-lean-B"]["events_by_cause"], {"retract": 1, "wrong_bind": 3})

    def test_a_protective_metric_worse_than_its_noise_blocks_the_verdict(self) -> None:
        out = analysis.analyse(groups(vsmt_b_mrr=0.3))  # Missing residual up 0.1 against a 0.01 seed noise
        self.assertTrue(out["verdict"]["improved"])
        self.assertFalse(out["protective_metrics"]["missing_residual_rate"]["not_worse"])
        self.assertFalse(out["verdict"]["effective"])

    def test_an_improvement_inside_the_seed_noise_is_not_an_improvement(self) -> None:
        out = analysis.analyse(groups(vsmt_b=0.7015, vsmt_c=0.70))
        self.assertFalse(out["aggregation_improves_vsmt_lean"]["improved"])
        self.assertFalse(out["verdict"]["effective"])

    def test_the_interval_is_deterministic_and_a_missing_group_is_refused(self) -> None:
        differences = [0.01 * (i % 5) - 0.01 for i in range(20)]
        self.assertEqual(analysis.bootstrap_interval(differences), analysis.bootstrap_interval(differences))
        low, high = analysis.bootstrap_interval(differences)
        self.assertLessEqual(low, sum(differences) / len(differences))
        self.assertGreaterEqual(high, sum(differences) / len(differences))
        broken = groups()
        del broken["AssocOnly-C"]
        with self.assertRaises(ValueError):
            analysis.analyse(broken)


if __name__ == "__main__":
    unittest.main()
