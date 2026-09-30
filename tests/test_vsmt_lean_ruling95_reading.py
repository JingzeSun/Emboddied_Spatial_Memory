"""D-224 / S2-R tests: the ruling 95 (a) reading on hand-made merged audits (five seeds per learned arm, four rule arms).

A Missing residual rate that is established lower for VSMT-lean, with node F1 and identity continuity not established worse,
reads as a gain on the development set; the same Missing gain with node F1 established worse reads as a trade-off; Missing
gaps of mixed sign read as no gain shown.  The 85-4 ratio is taken against the best rule arm and the 89-4 lines are only
reported.  A missing rule arm is refused.  CPU only.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "ops" / "vsmt"))

import ruling95_reading as reading  # noqa: E402

HOUSES = [f"h{i:02d}" for i in range(10)]
SEEDS = (7, 19, 31, 43, 59)


def merged(*, f1: float = 0.8, mrr: float = 0.3, identity: float = 0.5, false_retract: float | None = 0.3):
    report = {"node_prf1": {"node_f1": f1}, "node_prf1_iou": {"node_f1": f1 / 2},
              "missing_residual_rate": {"missing_residual_rate": mrr}, "identity_continuity": {"identity_continuity": identity},
              "contamination_auc": {"contamination_auc": 0.4}, "recovery_latency_frames": {"recovery_latency_frames": 100.0},
              "false_retract_rate_in_scope": {"false_retract_rate": false_retract}, "false_retract_rate": {"false_retract_rate": false_retract}}
    return {"per_episode": [{"episode_id": h, "report": report} for h in HOUSES], "pooled_loss_tally": {}}


def groups(vsmt: dict, assoc: dict):
    out = {}
    for index, seed in enumerate(SEEDS):
        out[("VSMT-lean", seed)] = merged(**{name: values[index] for name, values in vsmt.items()})
        out[("AssocOnly", seed)] = merged(false_retract=None, **{name: values[index] for name, values in assoc.items()})
    return out


def rule_arms(rac_mrr: float = 0.09):
    return {"TAF": merged(mrr=0.5, false_retract=None), "ELU-P": merged(mrr=0.1), "RAC": merged(mrr=rac_mrr), "LOW": merged(mrr=0.6, false_retract=None)}


class Ruling95ReadingTests(unittest.TestCase):
    def test_an_established_missing_gain_without_harm_reads_as_a_gain(self) -> None:
        out = reading.read(groups({"mrr": [0.10, 0.12, 0.11, 0.13, 0.12], "f1": [0.80, 0.81, 0.79, 0.80, 0.80]},
                                  {"mrr": [0.30, 0.32, 0.31, 0.29, 0.33], "f1": [0.80, 0.80, 0.80, 0.81, 0.79]}), rule_arms())
        self.assertEqual(out["orders_82_1"]["missing_residual_rate"], "VSMT-lean_better")
        self.assertEqual(out["orders_82_1"]["node_prf1"], "not_distinguishable_on_the_development_set")
        self.assertEqual(out["classification"], "gain_shown_on_development")
        rule = out["rule_85_4"]
        self.assertEqual(rule["best_rule_arm"], "RAC")
        self.assertAlmostEqual(rule["ratio"], 0.116 / 0.09)
        self.assertFalse(rule["at_least_twice"])
        lines = out["lines_89_4_reference_only"]
        self.assertFalse(lines["missing_residual_rate"]["met"])  # 0.116 is above the 0.10 line: the lines do not decide the gain
        self.assertTrue(lines["false_retract_rate_in_scope"]["met"])
        self.assertTrue(lines["identity_continuity"]["met"])
        self.assertIsNone(out["rule_arms"]["TAF"]["false_retract_rate_in_scope"]["mean"])

    def test_a_missing_gain_bought_with_node_f1_is_a_trade_off(self) -> None:
        out = reading.read(groups({"mrr": [0.10, 0.12, 0.11, 0.13, 0.12], "f1": [0.70, 0.71, 0.69, 0.70, 0.72]},
                                  {"mrr": [0.30, 0.32, 0.31, 0.29, 0.33], "f1": [0.80, 0.80, 0.80, 0.81, 0.79]}), rule_arms())
        self.assertEqual(out["orders_82_1"]["node_prf1"], "AssocOnly_better")
        self.assertEqual(out["classification"], "trade_off_no_gain_claimed")
        self.assertFalse(out["lines_89_4_reference_only"]["node_prf1"]["met"])

    def test_mixed_missing_gaps_show_no_gain_and_the_85_4_ratio_flags_twice(self) -> None:
        out = reading.read(groups({"mrr": [0.20, 0.40, 0.25, 0.35, 0.30]}, {"mrr": [0.30, 0.30, 0.30, 0.30, 0.30]}),
                           rule_arms(rac_mrr=0.1))
        self.assertEqual(out["orders_82_1"]["missing_residual_rate"], "not_distinguishable_on_the_development_set")
        self.assertEqual(out["classification"], "no_gain_shown_on_development")
        self.assertEqual(out["rule_85_4"]["best_rule_arm"], "ELU-P")  # tie at 0.1 broken by name
        self.assertTrue(out["rule_85_4"]["at_least_twice"])
        self.assertFalse(out["lines_89_4_reference_only"]["missing_residual_rate"]["met"])

    def test_a_missing_rule_arm_is_refused(self) -> None:
        arms = rule_arms()
        del arms["LOW"]
        with self.assertRaises(ValueError):
            reading.read(groups({"mrr": [0.3] * 5}, {"mrr": [0.3] * 5}), arms)


if __name__ == "__main__":
    unittest.main()
