"""S1-05 descriptor selection tool: synthetic S1-04 reports and the committed real one.

Pinned here: the tool re-derives the ruling-47 hold-out from the cache membership the report pins and
refuses a report whose groups differ, overlap or were scored outside their group; it recomputes the rule
from the selection-house medians and refuses a report whose stored verdict, threshold or exclusion list
differs; a diverged projection never enters the rule; the shortfall is recorded, never refilled; the frozen
block names the source set, the weights digest and the frozen baseline when a projection wins and no
weights or baseline when a frozen set is kept; and on the committed S1-04 report the tool yields exactly
the constants ``lean_assignment`` binds, with the committed receipt agreeing with a fresh recomputation.
Standard library plus the lean modules; no torch, no cache, no private file.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path


def lf_sha256(path: Path) -> str:
    """Content digest ignoring line endings, as the tool and the reviewed-contract digests use."""

    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for item in (PROJECT_ROOT / "src", PROJECT_ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import lean_s1_05_select_descriptor as s105  # noqa: E402
from vsmt import lean_assignment as la  # noqa: E402
from vsmt import lean_reid_head as rh  # noqa: E402

SEED = 20260920
CONTRACT = la.validate_assignment_contract(json.loads(s105.S0_03_CONTRACT.read_text(encoding="utf-8")))
S1_03_CONTRACT = json.loads(s105.S1_03_CONTRACT.read_text(encoding="utf-8"))
REAL_REPORT = PROJECT_ROOT / "results" / "vsmt_lean_s1_04_diagnostics_oracle_caa50c7.json"  # ruling 73 (3)
REAL_RECEIPT = PROJECT_ROOT / "results" / "vsmt_lean_s1_05_descriptor_freeze_oracle_caa50c7.json"
SYNTHETIC_PATH = PROJECT_ROOT / "results" / "synthetic_s1_04_report.json"  # never written; only a name


def house_ids(count: int) -> list[str]:
    return [f"procthor10k-0.1.2-train-{index:05d}" for index in range(count)]


def stats(median: float) -> dict:
    return {"count": 1000, "mean": median, "median": median, "p10": median - 0.2, "p25": median - 0.1, "p75": median + 0.1}


def curve(miss_rate: float) -> dict:
    points = []
    for k in (1, 5):
        for k_prime in (0, 3):
            for radius in (1.0, 3.0):
                points.append({"local_count": k, "global_count": k_prime, "local_radius_m": radius,
                               "decisions": 1000, "recall_miss": int(1000 * miss_rate), "recall_miss_rate": miss_rate})
    return {"grid_points": points}


def make_report(*, cached: int = 39, frozen=None, projected=None, diverged=(), threshold: float = 0.05) -> dict:
    """A report shaped like the S1-04 runner's stage receipt, with the verdict computed the way the runner does."""

    frozen = frozen or {"vits14": 0.10, "vitb14": 0.14}
    projected = projected or {"vits14": 0.19, "vitb14": 0.23}
    ids = house_ids(cached)
    split = rh.holdout_split(ids, seed=SEED)
    by_set, medians = {}, {}
    for name in rh.FROZEN_SETS:
        entry = {"weights_file": f"reid_head_{name}.json", "training_houses_used": len(split["training_houses"]),
                 "selection_houses_used": len(split["selection_houses"]),
                 "selection_houses_separation_frozen": stats(frozen[name]), "selection_houses_recall_curve_frozen": curve(0.02),
                 "weights_reused": False, "training_fragments": 100, "training_classes": 10, "classes_with_positives": 9,
                 "loss_curve": [2.0, 1.5], "diverged": name in diverged}
        medians[name] = frozen[name]
        if name in diverged:
            entry.update({"status": "failed", "reason": "training_diverged", "weights_written": False, "weights_sha256": None})
        else:
            entry.update({"status": "succeeded", "weights_written": True, "weights_sha256": hashlib.sha256(name.encode()).hexdigest(),
                          "selection_houses_separation_projection": stats(projected[name]),
                          "selection_houses_recall_curve_projection": curve(0.01)})
            medians[f"reid_projection:{name}"] = projected[name]
        by_set[name] = entry
    rule = rh.select_descriptor(medians, threshold=threshold)
    rule.update({"status": "computed", "projections_excluded_after_divergence": sorted(diverged), "note": "S1-05 applies this"})
    holdout = {**split, "membership_rule": "frozen_on_cache_succeeded_episodes_before_any_diagnostic_no_backfill_across_groups",
               "training_houses_used": list(split["training_houses"]), "selection_houses_used": list(split["selection_houses"]),
               "training_houses_failed_diagnostics": [], "selection_houses_failed_diagnostics": []}
    return {
        "stage": "s1-04-diagnostics", "code_commit": "0" * 40, "episodes_planned": cached, "episodes_run": cached,
        "episodes_failed": [], "episodes_used": cached, "fragments_labelled": 1, "fragments_unlabelled": 0,
        "cache_episode_seals": {house: hashlib.sha256(house.encode()).hexdigest() for house in ids},
        "per_house": {house: {"separation_median": {"vits14": 0.1, "vitb14": 0.14}} for house in ids},
        "separation_by_set": {name: {"median": frozen[name]} for name in rh.FROZEN_SETS},
        "fragment_truth_iou": {"truth": {"median": 0.0004}, "median_below_gate": True},
        "reid": {"holdout": holdout, "values": {}, "weights_plan": {"reuse": [], "train": list(rh.FROZEN_SETS)},
                 "by_set": by_set, "failed_sets": sorted(diverged), "selection_rule": rule},
    }


def receipt_for(report: dict) -> dict:
    return s105.build_receipt(report, report_path=SYNTHETIC_PATH, report_sha256="0" * 64, contract=CONTRACT,
                              s1_03_contract=S1_03_CONTRACT, seed=SEED, closeout=None,
                              written_at_utc="2026-09-24T00:00:00Z", checkout={"commit": None, "clean": None})


class SelectionOnSyntheticReports(unittest.TestCase):
    def test_a_projection_that_clears_the_margin_is_frozen_with_its_weights_and_the_baseline(self) -> None:
        receipt = receipt_for(make_report())
        frozen, selection = receipt["frozen"], receipt["selection"]
        self.assertEqual(selection["chosen"], "reid_projection:vitb14")
        self.assertEqual(selection["best_frozen"], "vitb14")
        self.assertAlmostEqual(selection["projection_gain_over_best_frozen"], 0.09)
        self.assertTrue(selection["matches_the_report_block"])
        self.assertEqual(frozen["selected_descriptor"], "reid_projection:vitb14")
        self.assertEqual((frozen["source_descriptor_set"], frozen["source_dimension"]), ("vitb14", 768))
        self.assertEqual(frozen["projection"]["weights_sha256"], hashlib.sha256(b"vitb14").hexdigest())
        self.assertEqual(frozen["projection"]["output_dimension"], la.REID_OUTPUT_DIMENSION)
        self.assertEqual(frozen["frozen_descriptor_baseline"], "vitb14")
        self.assertTrue(frozen["frozen_descriptor_baseline_must_be_reported_alongside"])
        self.assertEqual(frozen["unselected_dropped_from_the_assignment_view"], ["reid_projection:vits14", "vits14"])
        self.assertTrue(frozen["no_further_descriptor_change"])
        self.assertEqual(receipt["candidates_on_selection_houses"]["vitb14"]["recall_miss_at_frozen_recall_values_on_selection_houses"]["recall_miss_rate"], 0.02)
        self.assertEqual(receipt["candidates_on_selection_houses"]["reid_projection:vitb14"]["recall_miss_at_frozen_recall_values_on_selection_houses"]["recall_miss_rate"], 0.01)
        self.assertEqual(receipt["rule"]["selection_rule_threshold"], la.REID_SELECTION_RULE_THRESHOLD)
        self.assertTrue(receipt["training_houses_annotation"]["projection_was_not_scored_on_training_houses"])
        self.assertEqual(len(receipt["training_houses_annotation"]["frozen_set_separation_median_by_training_house"]), 30)

    def test_a_frozen_set_is_kept_below_the_margin_with_no_weights_and_no_baseline(self) -> None:
        receipt = receipt_for(make_report(projected={"vits14": 0.13, "vitb14": 0.18}))
        frozen = receipt["frozen"]
        self.assertEqual(frozen["selected_descriptor"], "vitb14")
        self.assertEqual(frozen["source_descriptor_set"], "vitb14")
        self.assertIsNone(frozen["projection"])
        self.assertIsNone(frozen["frozen_descriptor_baseline"])
        self.assertFalse(frozen["frozen_descriptor_baseline_must_be_reported_alongside"])
        self.assertEqual(frozen["unselected_dropped_from_the_assignment_view"],
                         ["reid_projection:vitb14", "reid_projection:vits14", "vits14"])
        self.assertAlmostEqual(receipt["selection_shortfall"]["margin_over_threshold"], -0.01)

    def test_a_stored_verdict_that_differs_from_the_recomputation_is_refused(self) -> None:
        for field, value, code in (
            ("chosen", "vitb14", "report_selection_rule_chosen_differs_from_recomputation"),
            ("best_frozen", "vits14", "report_selection_rule_best_frozen_differs_from_recomputation"),
            ("projection_gain_over_best_frozen", 0.2, "report_projection_gain_differs_from_recomputation"),
            ("threshold", 0.02, "report_threshold_differs_from_contract"),
            ("status", "undefined", "report_selection_rule_not_computed"),
        ):
            report = make_report()
            report["reid"]["selection_rule"][field] = value
            with self.subTest(field=field), self.assertRaises(s105.S105Refused) as caught:
                receipt_for(report)
            self.assertEqual(str(caught.exception), code)
        # A median edited in the report body without the verdict following it is caught the same way.
        report = make_report()
        report["reid"]["by_set"]["vitb14"]["selection_houses_separation_projection"]["median"] = 0.15
        with self.assertRaises(s105.S105Refused) as caught:
            receipt_for(report)
        self.assertEqual(str(caught.exception), "report_selection_rule_chosen_differs_from_recomputation")

    def test_a_holdout_that_differs_overlaps_or_leaks_is_refused(self) -> None:
        report = make_report()
        holdout = report["reid"]["holdout"]
        moved = holdout["training_houses"][-1]
        # Swap a house across the groups: the recomputation from the seals does not agree.
        broken = copy.deepcopy(report)
        broken["reid"]["holdout"]["training_houses"][-1] = holdout["selection_houses"][0]
        broken["reid"]["holdout"]["selection_houses"][0] = moved
        with self.assertRaises(s105.S105Refused) as caught:
            receipt_for(broken)
        self.assertEqual(str(caught.exception), "holdout_training_houses_differs_from_recomputation")
        # Score a training house as a selection house: refused even when the groups themselves are right.
        broken = copy.deepcopy(report)
        broken["reid"]["holdout"]["selection_houses_used"].append(moved)
        with self.assertRaises(s105.S105Refused) as caught:
            receipt_for(broken)
        self.assertEqual(str(caught.exception), "holdout_selection_house_used_outside_its_group")
        # A different seed or order is not the registered hold-out.
        broken = copy.deepcopy(report)
        broken["reid"]["holdout"]["seed"] = SEED + 1
        with self.assertRaises(s105.S105Refused) as caught:
            receipt_for(broken)
        self.assertEqual(str(caught.exception), "holdout_order_or_seed_differs")
        # Understating the shortfall is refused too.
        broken = copy.deepcopy(report)
        broken["reid"]["holdout"]["selection_shortfall"] = 0
        with self.assertRaises(s105.S105Refused) as caught:
            receipt_for(broken)
        self.assertEqual(str(caught.exception), "holdout_selection_shortfall_differs_from_recomputation")

    def test_a_diverged_projection_is_excluded_and_never_enters_the_rule(self) -> None:
        report = make_report(diverged=("vitb14",), projected={"vits14": 0.20, "vitb14": 0.23})
        receipt = receipt_for(report)
        self.assertEqual(receipt["selection"]["projections_excluded_after_divergence"], ["vitb14"])
        self.assertNotIn("reid_projection:vitb14", receipt["selection"]["candidate_medians_on_selection_houses"])
        # vits14's projection clears the margin over the best frozen set (0.20 - 0.14 = 0.06) and is taken.
        self.assertEqual(receipt["frozen"]["selected_descriptor"], "reid_projection:vits14")
        self.assertEqual(receipt["frozen"]["source_descriptor_set"], "vits14")
        self.assertTrue(receipt["candidates_on_selection_houses"]["reid_projection:vitb14"]["excluded_from_the_rule"])
        # The report must say it excluded the diverged set.
        report["reid"]["selection_rule"]["projections_excluded_after_divergence"] = []
        with self.assertRaises(s105.S105Refused) as caught:
            receipt_for(report)
        self.assertEqual(str(caught.exception), "report_excluded_projections_differ")

    def test_the_shortfall_is_recorded_and_never_refilled(self) -> None:
        short = receipt_for(make_report(cached=39))
        self.assertEqual((len(short["holdout"]["training_houses"]), len(short["holdout"]["selection_houses"])), (30, 9))
        self.assertEqual(short["selection_shortfall"]["shortfall"], 3)
        self.assertEqual(short["selection_shortfall"]["registered_selection_houses"], la.REID_SELECTION_HOUSES)
        self.assertTrue(short["selection_shortfall"]["flagged_for_the_user"])
        full = receipt_for(make_report(cached=42))
        self.assertEqual(full["selection_shortfall"]["shortfall"], 0)
        self.assertFalse(full["selection_shortfall"]["flagged_for_the_user"])
        with self.assertRaises(s105.S105Refused) as caught:
            receipt_for(make_report(cached=45))  # three houses beyond the 42 the hold-out covers
        self.assertEqual(str(caught.exception), "holdout_houses_beyond_the_holdout")

    def test_the_report_must_be_a_completed_s1_04_diagnostics_stage(self) -> None:
        for edit, code in (
            (lambda r: r.__setitem__("stage", "s1-03"), "report_is_not_an_s1_04_diagnostics_receipt"),
            (lambda r: r.__setitem__("episodes_failed", ["procthor10k-0.1.2-train-00001"]), "report_stage_incomplete_or_episodes_failed"),
            (lambda r: r.__setitem__("episodes_run", r["episodes_planned"] - 1), "report_stage_incomplete_or_episodes_failed"),
            (lambda r: r.update(episodes_run=r["episodes_planned"] - 1,
                                episodes_kept_from_receipts=["procthor10k-0.1.2-train-00001", "procthor10k-0.1.2-train-00001"]),
             "report_stage_incomplete_or_episodes_failed"),
            (lambda r: r["per_house"].pop("procthor10k-0.1.2-train-00001"), "report_per_house_differs_from_cache_seals"),
            (lambda r: r.pop("reid"), "report_has_no_reid_block"),
        ):
            report = make_report()
            edit(report)
            with self.subTest(code=code), self.assertRaises(s105.S105Refused) as caught:
                receipt_for(report)
            self.assertEqual(str(caught.exception), code)

    def test_a_resumed_stage_counts_the_kept_receipts(self) -> None:
        # S1-04 --resume keeps succeeded receipts and runs the rest; the stage receipt reports both
        report = make_report()
        kept = sorted(report["cache_episode_seals"])[:3]
        report.update(episodes_run=report["episodes_planned"] - len(kept), episodes_kept_from_receipts=kept)
        receipt_for(report)

    def test_recall_at_the_frozen_values_reads_the_ruling_57_grid_point(self) -> None:
        point = s105.recall_at_frozen_values(curve(0.05))
        self.assertEqual((point["local_count"], point["global_count"], point["local_radius_m"]),
                         (la.RECALL_LOCAL_COUNT, la.RECALL_GLOBAL_COUNT, la.RECALL_LOCAL_RADIUS_M))
        self.assertIsNone(s105.recall_at_frozen_values(None))
        self.assertIsNone(s105.recall_at_frozen_values({"grid_points": []}))


class SelectionOnTheCommittedReport(unittest.TestCase):
    """The real S1-04 report is committed, so the freeze is reproducible from the tree alone."""

    def setUp(self) -> None:
        self.report = json.loads(REAL_REPORT.read_text(encoding="utf-8"))
        self.report_sha256 = lf_sha256(REAL_REPORT)
        self.fresh = s105.build_receipt(self.report, report_path=REAL_REPORT, report_sha256=self.report_sha256, contract=CONTRACT,
                                        s1_03_contract=S1_03_CONTRACT, seed=SEED, closeout=None,
                                        written_at_utc="2026-09-24T00:00:00Z", checkout={"commit": None, "clean": None})

    def test_the_committed_report_selects_the_constants_lean_assignment_binds(self) -> None:
        frozen = self.fresh["frozen"]
        self.assertEqual(frozen["selected_descriptor"], la.SELECTED_DESCRIPTOR)
        self.assertEqual(frozen["source_descriptor_set"], la.SELECTED_DESCRIPTOR_SOURCE_SET)
        self.assertEqual(frozen["frozen_descriptor_baseline"], la.FROZEN_DESCRIPTOR_BASELINE)
        self.assertEqual(frozen["projection"]["weights_sha256"], la.SELECTED_REID_WEIGHTS_SHA256)
        self.assertEqual(frozen["projection"]["output_dimension"], la.REID_OUTPUT_DIMENSION)
        self.assertGreaterEqual(self.fresh["selection"]["projection_gain_over_best_frozen"], la.REID_SELECTION_RULE_THRESHOLD)
        self.assertEqual((len(self.fresh["holdout"]["training_houses_used"]), len(self.fresh["holdout"]["selection_houses_used"])), (30, 9))
        self.assertEqual(self.fresh["selection_shortfall"]["shortfall"], 3)

    def test_the_committed_receipt_agrees_with_a_fresh_recomputation(self) -> None:
        committed = json.loads(REAL_RECEIPT.read_text(encoding="utf-8"))
        self.assertEqual(committed["schema_version"], s105.SCHEMA_VERSION)
        self.assertEqual(committed["input"]["s1_04_report_sha256"], self.report_sha256)
        for block in ("rule", "input", "holdout", "candidates_on_selection_houses", "selection", "frozen",
                      "training_houses_annotation", "selection_shortfall"):
            with self.subTest(block=block):
                self.assertEqual(committed[block], self.fresh[block])
        closeout = committed["s1_closeout"]
        self.assertEqual(closeout["s1_04"]["sha256"], self.report_sha256)
        for name in ("s1_03", "s1_04_iou_gate_recheck_under_the_ruled_matching_rule"):
            path = PROJECT_ROOT / (closeout[name]["report"] if name == "s1_03" else closeout[name]["estimate_report"])
            self.assertEqual(lf_sha256(path), closeout[name]["sha256"], name)
        for row in closeout["s1_02"]["reports"]:
            self.assertEqual(lf_sha256(PROJECT_ROOT / row["report"]), row["sha256"], row["report"])
        self.assertTrue(closeout["s1_04_iou_gate_recheck_under_the_ruled_matching_rule"]["passes"])
        self.assertFalse(committed["private_ids_exported"])


if __name__ == "__main__":
    unittest.main()
