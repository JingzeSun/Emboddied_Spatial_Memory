"""Ruling 88-2 reading tests: G0-a/b/c, the 2x2 attribution and the probe readings on hand-made inputs.  Seconds."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "ops" / "vsmt"))

import ruling88_analysis as r88  # noqa: E402

HOUSES = ("h1", "h2", "h3", "h4")


def merged(mrr, identity, *, f1=0.8, kept=(1, 1), oracle=None):
    """A merged audit whose houses all carry the given values (a value of None leaves the metric undefined there)."""

    def value(v, i):
        return v[i] if isinstance(v, (list, tuple)) else v

    episodes = []
    for i, house in enumerate(HOUSES):
        report = {"node_prf1": {"node_f1": f1}, "missing_residual_rate": {"missing_residual_rate": value(mrr, i)},
                  "identity_continuity": {"identity_continuity": value(identity, i)}, "contamination_auc": {"contamination_auc": 0.3},
                  "false_retract_rate_in_scope": {"false_retract_rate": 0.2}}
        rows = [{"ordinal": k, "category": "kept" if k < kept[0] else "carrier_not_recalled", "judged": True} for k in range(kept[1])] if i == 0 else []
        episodes.append({"episode_id": house, "report": report, "identity_attribution": rows})
    return {"schema_version": "vsmt-s2-05-node-audit-merged-v9", "per_episode": episodes, "oracle": oracle}


def rule_arms(mrr_rac=0.089):
    return {"TAF": merged(0.76, 0.149), "ELU-P": merged(0.092, 0.149), "RAC": merged(mrr_rac, 0.018), "LOW": merged(0.28, 0.0)}


def cells(v_mrr=0.0, v_identity=0.8, a_mrr=0.3, a_identity=0.78, n_identity=0.6):
    base = merged(v_mrr, v_identity)
    return {"O-V-node": base, "O-V-legacy": merged(v_mrr, v_identity, f1=0.7), "O-N-node": merged(v_mrr, n_identity),
            "O-N-legacy": merged(v_mrr, n_identity, f1=0.7), "O-A": merged(a_mrr, a_identity), "O-V-node-recall": merged(v_mrr, 0.9)}


class GateTests(unittest.TestCase):
    def test_all_three_pass_and_the_decision_is_to_proceed(self) -> None:
        out = r88.g0(cells(), rule_arms())
        self.assertTrue(out["G0-a"]["pass"] and out["G0-b"]["pass"] and out["G0-c"]["pass"])
        self.assertEqual(out["decision"], "proceed_to_the_redesign_track")
        self.assertAlmostEqual(out["G0-a"]["missing_residual_rate_vs_O-A"]["advantage"], 0.3)
        self.assertAlmostEqual(out["G0-c"]["worst_margin"]["missing_residual_rate"], 0.089)

    def test_no_vocabulary_advantage_stops_before_training(self) -> None:
        out = r88.g0(cells(v_mrr=0.28), rule_arms())
        self.assertFalse(out["G0-a"]["pass"])
        self.assertEqual(out["decision"], "no_ceiling_for_the_lifecycle_vocabulary_ruling_on_claim_or_vocabulary_before_any_training")

    def test_a_ceiling_too_close_to_rac_puts_the_main_gate_out_of_reach(self) -> None:
        out = r88.g0(cells(v_mrr=0.06), rule_arms())
        self.assertTrue(out["G0-a"]["pass"])
        self.assertFalse(out["G0-c"]["pass"])
        self.assertEqual(out["decision"], "main_gate_out_of_reach_at_the_ceiling_ruling_on_the_gate_or_framing_before_any_training")

    def test_losing_identity_to_assoc_only_by_more_than_the_margin_fails_g0a(self) -> None:
        self.assertFalse(r88.g0(cells(v_identity=0.70, a_identity=0.78), rule_arms())["G0-a"]["pass"])
        self.assertTrue(r88.g0(cells(v_identity=0.74, a_identity=0.78), rule_arms())["G0-a"]["pass"])

    def test_versioning_value_needs_the_margin_over_noversion(self) -> None:
        out = r88.g0(cells(v_identity=0.8, n_identity=0.77), rule_arms())
        self.assertFalse(out["G0-b"]["pass"])
        self.assertIsNotNone(out["G0-b"]["reading"])

    def test_houses_undefined_in_one_run_are_left_out_of_the_pair(self) -> None:
        left, right = merged([0.0, 0.0, None, 0.0], 0.8), merged([0.3, 0.3, 0.3, None], 0.8)
        out = r88.advantage(left, right, "missing_residual_rate")
        self.assertEqual(out["houses"], 2)
        self.assertAlmostEqual(out["advantage"], 0.3)


class AttributionTests(unittest.TestCase):
    def test_the_side_that_closes_more_of_the_gap_leads(self) -> None:
        oracle = merged(0.0, 0.9)
        learned = {s: merged(0.35, 0.4) for s in r88.SEEDS}
        mixed = {"OA-LE": {s: merged(0.30, 0.8) for s in r88.SEEDS}, "LA-OE": {s: merged(0.10, 0.45) for s in r88.SEEDS}}
        mrr = r88.attribution(oracle, learned, mixed, "missing_residual_rate")
        self.assertAlmostEqual(mrr["share_closed"]["association"], 0.05 / 0.35)
        self.assertAlmostEqual(mrr["share_closed"]["existence"], 0.25 / 0.35)
        self.assertEqual(mrr["leading_side"], "existence")
        identity = r88.attribution(oracle, learned, mixed, "identity_continuity")
        self.assertEqual(identity["leading_side"], "association")

    def test_a_missing_mixed_cell_is_not_judged(self) -> None:
        out = r88.attribution(merged(0.0, 0.9), {7: merged(0.3, 0.4)}, {"OA-LE": {7: merged(0.2, 0.5)}}, "missing_residual_rate")
        self.assertFalse(out["judged"])


class ProbeReadingTests(unittest.TestCase):
    def test_sensitivity_lines(self) -> None:
        reports = {f"A{s}": {"ratios": {"association_ticks_over_100_vs_1": r, "existence_observations_over_100_vs_1_to_10": 0.7}}
                   for s, r in zip(r88.SEEDS, (0.02, 0.05, 0.08, 0.3, 0.6))}
        out = r88.sensitivity_reading(reports)
        self.assertEqual(out["association_ticks_over_100_vs_1"]["reading"], "layernorm_harm_confirmed")
        self.assertEqual(out["existence_observations_over_100_vs_1_to_10"]["reading"], "compensated_not_confirmed")

    def test_imitation_grid(self) -> None:
        def report(train):
            return {"agreement": {"train": {"balanced_agreement": train}, "selection": {"balanced_agreement": train}}, "diverged": False}

        passing = {t: report(0.995) for t in r88.POSITIVE_CONTROLS}
        self.assertEqual(r88.imitation_reading({**passing, "rac": report(0.8), "elup": report(0.99)})["reading"], "history_is_missing")
        self.assertEqual(r88.imitation_reading({**passing, "rac": report(0.995), "elup": report(0.99)})["reading"],
                         "heads_sufficient_weakness_in_labels_or_data")
        self.assertEqual(r88.imitation_reading({**passing, "handcost": report(0.9), "rac": report(0.8), "elup": report(0.8)})["reading"],
                         "encoding_or_optimisation_is_the_bottleneck")
        self.assertEqual(r88.imitation_reading({"rac": report(0.8)})["reading"], "incomplete")


class InputTests(unittest.TestCase):
    def test_a_development_table_export_becomes_per_episode_reports(self) -> None:
        export = {"episodes": {"h2": {"status": "succeeded", "report": {"missing_residual_rate": {"missing_residual_rate": 0.1}}},
                               "h1": {"status": "failed"}}}
        out = r88.as_merged(export)
        self.assertEqual([e["episode_id"] for e in out["per_episode"]], ["h2"])
        with self.assertRaises(ValueError):
            r88.as_merged({"schema_version": "something-else"})

    def test_the_full_reading_needs_every_cell_and_rule_arm(self) -> None:
        full = r88.analyse(cells(), rule_arms(), {}, {}, None, {}, {})
        self.assertEqual(full["G0"]["decision"], "proceed_to_the_redesign_track")
        self.assertAlmostEqual(full["comparisons_reported_only"]["label_rule_V"]["node_f1"]["left_minus_right"], -0.1)
        partial = cells()
        del partial["O-A"]
        with self.assertRaises(ValueError):
            r88.analyse(partial, rule_arms(), {}, {}, None, {}, {})


if __name__ == "__main__":
    unittest.main()
