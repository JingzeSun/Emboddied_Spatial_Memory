"""Ruling 88-2 (ii) tests: the three minute-scale checks on sealed training records (coverage, sensitivity, imitation).

Records come from the S2-04 five-frame synthetic TAF episode (a mug removed and a book moved after the window); the history
replays are pinned on hand-made existence rows.  CPU only, seconds.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for item in (PROJECT_ROOT / "src", PROJECT_ROOT / "tests", PROJECT_ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import ruling88_probes as probes  # noqa: E402
from vsmt import lean_assignment as la  # noqa: E402
from vsmt import lean_model as model  # noqa: E402
from test_vsmt_lean_evaluation import run_and_label  # noqa: E402


def taf_records() -> list[dict]:
    _, _, labelled, _ = run_and_label("TAF")
    return [{**frame["training_record"], "tick": frame["tick"]} for frame in labelled]


def existence_row(entity_id: str, *, coverage: float, observations: int, ticks_since: int, state: str = "active") -> dict:
    values = {name: 0.0 for name in la.EXISTENCE_FEATURES}
    values.update({"should_be_visible_ratio": 0.5, "free_space_coverage_ratio": coverage, "observation_count": float(observations),
                   "ticks_since_last_seen": float(ticks_since), f"state_is_{state}": 1.0})
    return {"entity_id": entity_id, "features": [values[name] for name in la.EXISTENCE_FEATURES]}


class CoverageTests(unittest.TestCase):
    def test_counts_partition_the_rows_and_the_targets(self) -> None:
        records = taf_records()
        counts = probes.coverage_counts(records)
        rows = sum(len(r["stage_a"]["association_rows"]) for r in records)
        self.assertEqual(sum(counts["association_rows_by_candidate_state"].values()), rows)
        statuses = counts["association_target_statuses"]
        self.assertEqual(sum(counts["labelled_targets_by_target_state"].values()), statuses.get("labelled", 0) + statuses.get("birth", 0))
        self.assertEqual(counts["frames"], 5)
        self.assertEqual(sum(counts["existence_rows_by_label"].values()), sum(len(r["existence_rows"]) for r in records))

    def test_the_state_one_hot_is_read_from_the_sealed_order(self) -> None:
        row = existence_row("e1", coverage=0.0, observations=1, ticks_since=1, state="dormant")
        self.assertEqual(probes.state_of(row["features"], la.EXISTENCE_FEATURES), "dormant")
        broken = list(row["features"])
        broken[list(la.EXISTENCE_FEATURES).index("state_is_active")] = 1.0
        with self.assertRaises(ValueError):
            probes.state_of(broken, la.EXISTENCE_FEATURES)


class ExistenceReplayTests(unittest.TestCase):
    def test_rac_needs_three_consecutive_see_through_frames_and_a_match_resets_it(self) -> None:
        replay = probes.ExistenceReplay("rac", la.EXISTENCE_FEATURES)
        seq = [(10, 0.8, 8), (11, 0.9, 9), (12, 0.8, 10)]  # tick, coverage, ticks since last seen (last seen at tick 2)
        self.assertEqual([replay.decide(t, [existence_row("e", coverage=c, observations=5, ticks_since=s)])["e"] for t, c, s in seq],
                         ["NOOP", "NOOP", "RETRACT"])
        replay = probes.ExistenceReplay("rac", la.EXISTENCE_FEATURES)
        seq = [(10, 0.8, 8), (11, 0.9, 9), (13, 0.8, 1), (14, 0.8, 2), (15, 0.8, 3)]  # matched at tick 12: the count restarts
        self.assertEqual([replay.decide(t, [existence_row("e", coverage=c, observations=5, ticks_since=s)])["e"] for t, c, s in seq],
                         ["NOOP", "NOOP", "NOOP", "NOOP", "RETRACT"])
        replay = probes.ExistenceReplay("rac", la.EXISTENCE_FEATURES)
        seq = [(10, 0.8, 8), (11, 0.1, 9), (12, 0.8, 10), (13, 0.8, 11)]  # a clear frame resets as well
        self.assertEqual([replay.decide(t, [existence_row("e", coverage=c, observations=5, ticks_since=s)])["e"] for t, c, s in seq],
                         ["NOOP", "NOOP", "NOOP", "NOOP"])

    def test_elu_p_accumulates_coverage_against_the_matches(self) -> None:
        values = probes.elu_p_values()
        self.assertAlmostEqual(values["initial_log_odds"], 4.75891184514327)
        replay = probes.ExistenceReplay("elup", la.EXISTENCE_FEATURES)
        # never matched after birth: 4.76 - 5 x (1 + 2e-5) < 0 on the fifth fully seen-through frame
        decisions = [replay.decide(10 + k, [existence_row("e", coverage=1.0, observations=1, ticks_since=8 + k)])["e"] for k in range(5)]
        self.assertEqual(decisions, ["NOOP", "NOOP", "NOOP", "NOOP", "RETRACT"])
        # one match more (observation count 2) buys match_gain = 3.1 more frames' worth
        replay = probes.ExistenceReplay("elup", la.EXISTENCE_FEATURES)
        decisions = [replay.decide(10 + k, [existence_row("e", coverage=1.0, observations=2, ticks_since=8 + k)])["e"] for k in range(8)]
        self.assertEqual(decisions.index("RETRACT"), 7)

    def test_handcost_reads_this_frame_only(self) -> None:
        replay = probes.ExistenceReplay("handcost", la.EXISTENCE_FEATURES)
        rows = [existence_row("a", coverage=0.8, observations=300, ticks_since=1), existence_row("b", coverage=0.79, observations=1, ticks_since=1)]
        self.assertEqual(replay.decide(5, rows), {"a": "RETRACT", "b": "NOOP"})


class ImitationTests(unittest.TestCase):
    def test_taf_binds_identical_descriptors_and_births_the_first_frame(self) -> None:
        records = taf_records()
        self.assertTrue(all(c.startswith(la.BIRTH_COLUMN_PREFIX) for c in probes.rule_assignment(records[0], "taf").values()))
        self.assertFalse(any(c.startswith(la.BIRTH_COLUMN_PREFIX) for c in probes.rule_assignment(records[1], "taf").values()))

    def test_imitation_records_are_valid_training_records(self) -> None:
        records = taf_records()
        for target in probes.TARGETS:
            replay = probes.ExistenceReplay(target, records[0]["existence_feature_order"]) if target in probes.EXISTENCE_TARGETS else None
            for row in records:
                record = {k: v for k, v in row.items() if k != "tick"}
                imitation, decisions = probes.imitation_record(record, target, replay=replay, tick=row["tick"])
                model.prepare_frame(imitation)  # validates and tensorises exactly as training would
                if target in probes.ASSOCIATION_TARGETS:
                    self.assertEqual(set(decisions), set(record["stage_a"]["rows"]))
                else:
                    self.assertEqual(set(decisions), {str(r["entity_id"]) for r in record["existence_rows"]})
                    self.assertEqual(imitation["targets"], {})

    def test_agreement_is_balanced_over_the_rule_classes(self) -> None:
        report = probes.balanced_agreement([("bind", "yes")] * 99 + [("bind", "no")] + [("birth", "no")])
        self.assertEqual(report["per_class"]["bind"]["agreement"], 0.99)
        self.assertEqual(report["per_class"]["birth"]["agreement"], 0.0)
        self.assertAlmostEqual(report["balanced_agreement"], 0.495)
        heads = model.make_heads(assoc_only=False, seed=0)
        record = {k: v for k, v in taf_records()[1].items() if k != "tick"}
        pairs = probes.agreement_pairs(heads, record, "taf", probes.rule_assignment(record, "taf"))
        self.assertEqual(len(pairs), len(record["stage_a"]["rows"]))


class LargeLogitTests(unittest.TestCase):
    def test_existence_agreement_survives_extreme_logits(self) -> None:
        import torch

        heads = model.make_heads(assoc_only=False, seed=0)
        with torch.no_grad():  # push every existence logit to about -1e4
            heads["existence"][-1].bias.fill_(-1e4)
        row = existence_row("e", coverage=0.9, observations=3, ticks_since=2)
        record = {"existence_rows": [row], "existence_feature_order": list(la.EXISTENCE_FEATURES)}
        self.assertEqual(probes.agreement_pairs(heads, record, "handcost", {"e": "RETRACT"}), [("RETRACT", "no")])
        self.assertEqual(probes.agreement_pairs(heads, record, "handcost", {"e": "NOOP"}), [("NOOP", "yes")])


class SensitivityTests(unittest.TestCase):
    def test_every_row_lands_in_one_bin(self) -> None:
        records = taf_records()
        tally = probes.SensitivityTally(model.make_heads(assoc_only=False, seed=0))
        for row in records:
            tally.add(row)
        report = tally.report()
        rows = sum(len(r["stage_a"]["association_rows"]) for r in records)
        self.assertEqual(sum(v["rows"] for v in report["association_by_ticks_since_last_seen"].values()), rows)
        self.assertEqual(sum(v["rows"] for v in report["birth_by_pixel_count"].values()), sum(len(r["stage_a"]["birth_rows"]) for r in records))
        self.assertEqual(sum(v["rows"] for v in report["existence_by_observation_count"].values()), sum(len(r["existence_rows"]) for r in records))
        self.assertIn("association_ticks_over_100_vs_1", report["ratios"])


if __name__ == "__main__":
    unittest.main()
