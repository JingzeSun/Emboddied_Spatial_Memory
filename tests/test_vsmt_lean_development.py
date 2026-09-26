"""D-224 / S2-05 tests: calibration histograms, the ELU-P count records and the development table.

Pinned here on the S2-04 synthetic episode (a removed mug, a moved book, a structural wall): the
histograms clip, merge and give quantiles deterministically; the calibration collector counts the
same-object and other-object pairs a pass seals, the novel fragments, the existence candidates by
label and the dominance shares; the ELU-P counter reproduces hand-counted records (an in-place
prior after an unobserved gap, one intervention event per removed or moved object over the
observed objects' ticks, the gate's hits while an object is present and its false matches at the
old place after it is gone) and the fit refuses degenerate sums; the development table takes the
headline values per house, applies the ruling-X2 exclusion over the applicable arms only, reports
the effective house count and the paired development difference of VSMT-lean against every arm,
and refuses a missing arm or house; the machine contract binds the implementation.
"""

from __future__ import annotations

import copy
import json
import math
import sys
import unittest
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for item in (SRC_ROOT, PROJECT_ROOT / "tests"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from vsmt import lean_arms as arms  # noqa: E402
from vsmt import lean_development as dev  # noqa: E402
from vsmt import lean_evaluation as ev  # noqa: E402
from vsmt import lean_runner as lr  # noqa: E402
import test_vsmt_lean_runner as runner_tests  # noqa: E402
from vsmt import lean_teacher as lt  # noqa: E402
from test_vsmt_lean_evaluation import NUISANCE_META, TEACHER_POLICY, episode, run_and_label  # noqa: E402
from test_vsmt_lean_runner import CONFIGS, POLICY  # noqa: E402

CONTRACT_PATH = PROJECT_ROOT / "configs" / "vsmt" / "lean_s2_05_development_v1.json"
ROLLOUT = {"theta_a": 0.5, "free_space_weight": 1.0, "retract_threshold": -1.0}


def run_with_counter(arm: str, config: dict[str, Any] | None = None):
    data = episode()
    steps = list(lr.run_episode(data["frames"], episode_id="ep-0001", arm=arm, config=config or CONFIGS[arm], policy=POLICY, descriptor="vitb14"))
    teacher = ev.EpisodeTeacher(arm=arm, geometry_table=data["table"], executed_interventions=data["executed"], window=data["window"],
                                policy=TEACHER_POLICY, nuisance_meta=NUISANCE_META)
    counter = dev.EluPCounter(geometry_table=data["table"], executed_interventions=data["executed"], window=data["window"], policy=TEACHER_POLICY)
    collector = dev.CalibrationCollector()
    for i, step in enumerate(steps):
        labelled = teacher.label_frame(step, cache_frame=data["frames"][i], private_record=data["records"][i], masks=data["masks"][i],
                                       label_image=data["images"][i], runtime_s=0.0, peak_memory_bytes=0)
        counter.observe(step, cache_frame=data["frames"][i], private_record=data["records"][i], evidence=teacher.evidence)
        collector.observe(step, labelled)
    return steps, counter.finish(), collector


class HistogramTests(unittest.TestCase):
    def test_bins_clip_merge_and_quantiles(self) -> None:
        h = dev.Histogram([0.0, 0.5, 1.0])
        for value in (-1.0, 0.1, 0.4, 0.6, 2.0):
            h.add(value)
        self.assertEqual(h.counts, [3, 2])
        self.assertEqual(h.total, 5)
        self.assertAlmostEqual(h.quantile(0.5), 0.5 * (2.5 / 3))  # inside the first bin
        other = dev.Histogram([0.0, 0.5, 1.0])
        other.add(0.9)
        h.merge(other)
        self.assertEqual(h.counts, [3, 3])
        again = dev.Histogram.from_json(json.loads(json.dumps(h.to_json())))
        self.assertEqual(again.counts, h.counts)
        self.assertEqual(again.summary()["count"], 6)
        self.assertIsNone(dev.Histogram([0.0, 1.0]).quantile(0.5))
        with self.assertRaises(dev.LeanDevelopmentError):
            h.merge(dev.Histogram([0.0, 1.0]))


class CalibrationTests(unittest.TestCase):
    def test_the_collector_counts_what_the_pass_sealed(self) -> None:
        _, _, collector = run_with_counter("LOW", {"d_low": None})
        report = collector.report()
        self.assertEqual(report["frames"], 5)
        self.assertEqual(report["fragments"], 3 + 3 + 2 + 2 + 1)
        series = report["series"]
        # frame 1 seals three labelled fragments (each recalled against its own entity and the two others),
        # frames 2-4 seal the book and the wall (every entity within 3 m is recalled)
        self.assertEqual(series["same_object_cosine_to_mean"]["count"], report["labelled_fragments"])
        self.assertGreater(series["same_object_cosine_to_mean"]["p50"], 0.9)
        self.assertLess(series["other_object_cosine_to_mean"]["p90"], 0.9)
        self.assertEqual(series["novel_fragment_best_cosine"]["count"], 0)  # the first frame has no entity to compare against
        self.assertEqual(series["fragment_dominance_share"]["count"], report["fragments"])
        self.assertEqual(series["gone_free_space_coverage_ratio"]["count"] + series["present_free_space_coverage_ratio"]["count"], 4)
        self.assertGreater(series["gone_free_space_coverage_ratio"]["p50"], 0.9)  # the mug's old place is covered by free space
        self.assertEqual(series["entity_should_be_visible_ratio"]["count"], 0 + 3 + 3 + 3 + 3)
        merged = dev.CalibrationCollector.from_json(json.loads(json.dumps(collector.to_json())))
        merged.merge(collector)
        self.assertEqual(merged.report()["frames"], 10)
        self.assertEqual(merged.report()["series"]["same_object_aabb_iou"]["count"], 2 * series["same_object_aabb_iou"]["count"])


class EluPCounterTests(unittest.TestCase):
    def test_counts_follow_the_s0_05_definitions_on_the_synthetic_episode(self) -> None:
        # the gate arm at the rollout theta: TAF binds the book at C and keeps the stale mug entity at A
        _, counts, _ = run_with_counter("TAF", {"theta_a": 0.5, "d_a": None})
        # (2) both objects observed at least once; both removed or moved; five frames each
        self.assertEqual(counts["persistence_log_decay_per_tick"], {"intervention_events": 2, "object_ticks": 10})
        # (1) every place stays observable throughout (one big visibility block), so no gap ever closes
        self.assertEqual(counts["initial_log_odds"], {"in_place_object_frames": 0, "object_frames": 0})
        # (3) hits: frame 1 mug and book (present, carriers from frame 0, bound), frames 2-4 book at C is "moved"
        # so it leaves p_hit; false: frames 2-4 the mug's and the book's old places are observable and only the
        # book's carrier is bound (to the fragment at C), never the mug's
        self.assertEqual(counts["match_gain"], {"hit_frames": 2, "hit_total": 2, "false_frames": 3, "false_total": 6})
        # the sum over episodes feeds the S2-02 estimators; one episode with a closed gap supplies the prior counts
        with_gap = copy.deepcopy(counts)
        with_gap["initial_log_odds"] = {"in_place_object_frames": 1, "object_frames": 2}
        fitted = dev.fit_elu_p([with_gap, counts], rollout_config=ROLLOUT)
        self.assertEqual(fitted["counts"]["match_gain"], {"hit_frames": 4, "hit_total": 4, "false_frames": 6, "false_total": 12})
        self.assertAlmostEqual(fitted["values"]["match_gain"], math.log(2.0))  # log(1.0 / 0.5)
        self.assertAlmostEqual(fitted["values"]["persistence_log_decay_per_tick"], -math.log(1 - 4 / 20))
        self.assertAlmostEqual(fitted["values"]["initial_log_odds"], 0.0)
        with self.assertRaises(dev.LeanDevelopmentError) as caught:
            dev.fit_elu_p([counts], rollout_config=ROLLOUT)  # object_frames 0 -> the prior is degenerate
        self.assertTrue(str(caught.exception).startswith("elu_p_fit_refused:fit_degenerate"))

    def test_a_gap_in_observability_yields_an_in_place_prior_count(self) -> None:
        data = episode()
        # frame 1 cannot see anything (no visibility block), frame 2 sees everything again
        data["frames"][1]["visibility"] = []
        # ruling 74: what the camera sees is the public depth view -- here it looks away from the scene
        data["frames"][1][lr.PUBLIC_DEPTH_VIEW_KEY] = runner_tests.depth_view(data["frames"][1]["frame_digest"], [], sees=False)
        counter = dev.EluPCounter(geometry_table=data["table"], executed_interventions=data["executed"], window=data["window"], policy=TEACHER_POLICY)
        steps = list(lr.run_episode(data["frames"], episode_id="ep-0001", arm="TAF", config=CONFIGS["TAF"], policy=POLICY, descriptor="vitb14"))
        teacher = ev.EpisodeTeacher(arm="TAF", geometry_table=data["table"], executed_interventions=data["executed"], window=data["window"],
                                    policy=TEACHER_POLICY, nuisance_meta=NUISANCE_META)
        for i, step in enumerate(steps):
            teacher.label_frame(step, cache_frame=data["frames"][i], private_record=data["records"][i], masks=data["masks"][i],
                                label_image=data["images"][i], runtime_s=0.0, peak_memory_bytes=0)
            counter.observe(step, cache_frame=data["frames"][i], private_record=data["records"][i], evidence=teacher.evidence)
        counts = counter.finish()
        # frame 2 is the first frame after the gap: the mug is gone (removed) and the book moved to C, neither in place
        self.assertEqual(counts["initial_log_odds"], {"in_place_object_frames": 0, "object_frames": 2})
        self.assertEqual(dev.sum_counts([counts, counts])["initial_log_odds"]["object_frames"], 4)


class DevelopmentTableTests(unittest.TestCase):
    def report(self, *, f1, mrr, frr, cont, latency, auc, active=3.0):
        return {"node_prf1": {"node_precision": 1.0, "node_recall": 1.0, "node_f1": f1, "matched": 1, "predicted": 1, "truth": 1},
                "node_prf1_iou": {"node_precision": 1.0, "node_recall": 1.0, "node_f1": f1, "matched": 1, "predicted": 1, "truth": 1},
                "missing_residual_rate": {"missing_residual_rate": mrr, "residual": 0, "judged": 0, "not_yet_observable": 0},
                "false_retract_rate": {"false_retract_rate": frr, "false_retracts": 0, "judged_retracts": 0, "ambiguous_retracts": 0},
                "identity_continuity": {"identity_continuity": cont, "kept": 0, "judged": 0, "no_prior_carrier": 0},
                "recovery_latency_frames": {"recovery_latency_frames": latency, "recovered": 0, "unrecovered": [], "never_observable": [], "per_object": {}},
                "contamination_auc": {"contamination_auc": auc, "frames": 5},
                "size_and_cost": {"active_entity_count": active, "lifecycle_version_count": 4.0, "runtime_per_frame_s": 0.01, "peak_memory_bytes": 1000}}

    def test_headline_values_exclusions_and_paired_differences(self) -> None:
        arms_ = list(dev.DEVELOPMENT_ARMS)
        reports: dict[str, dict[str, Any]] = {arm: {} for arm in arms_}
        for house, (f1, mrr) in {"h1": (0.8, 0.2), "h2": (0.6, 0.4), "h3": (0.9, None)}.items():
            for arm in arms_:
                shift = 0.0 if arm == "VSMT-lean" else 0.1
                reports[arm][house] = self.report(f1=f1 - shift, mrr=(None if mrr is None else mrr + shift), frr=(None if arm in ("TAF", "LOW", "AssocOnly") else 0.1),
                                                  cont=1.0, latency=(None if house == "h2" else 2.0), auc=0.3)
        table = dev.development_table(reports)
        self.assertEqual(table["houses"], ["h1", "h2", "h3"])
        node = table["metrics"]["node_prf1"]
        self.assertEqual(node["excluded_houses"], [])
        self.assertAlmostEqual(node["mean"]["VSMT-lean"], (0.8 + 0.6 + 0.9) / 3)
        self.assertAlmostEqual(node["method_minus_each_arm"]["TAF"]["method_advantage"], 0.1)
        self.assertIsNone(node["method_minus_each_arm"]["VSMT-lean"])
        mrr = table["metrics"]["missing_residual_rate"]
        self.assertEqual(mrr["excluded_houses"], ["h3"])  # undefined for every arm there; excluded for all
        self.assertEqual(mrr["effective_houses"], 2)
        self.assertAlmostEqual(mrr["method_minus_each_arm"]["RAC"]["method_advantage"], 0.1)  # lower is better
        frr = table["metrics"]["false_retract_rate"]
        self.assertEqual(frr["not_applicable"], ["TAF", "LOW", "AssocOnly"])
        self.assertIsNone(frr["mean"]["TAF"])
        self.assertEqual(frr["excluded_houses"], [])  # the never-retracting arms do not empty the column
        self.assertIsNone(frr["method_minus_each_arm"]["LOW"])
        latency = table["metrics"]["recovery_latency_frames"]
        self.assertEqual(latency["excluded_houses"], ["h2"])
        self.assertEqual(table["metrics"]["size_and_cost"]["TAF"]["peak_memory_bytes"], 1000)
        broken = copy.deepcopy(reports)
        del broken["LOW"]["h2"]
        with self.assertRaises(dev.LeanDevelopmentError) as caught:
            dev.development_table(broken)
        self.assertEqual(str(caught.exception), "development_table_house_sets_differ:LOW")
        with self.assertRaises(dev.LeanDevelopmentError):
            dev.development_table({arm: reports[arm] for arm in arms_ if arm != "RAC"})


class MachineContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_the_contract_binds_the_implementation(self) -> None:
        checked = dev.validate_development_contract(self.contract)
        self.assertEqual(checked["stage_id"], "S2-05")
        self.assertEqual(tuple(checked["passes"]["order"]), dev.PASSES)
        # both bits opened on 2026-09-24 (rulings 64/67, the S2-05 review) and named by the activation policy
        self.assertTrue(all(checked["authorization"].values()))
        self.assertEqual(sorted(checked["activation_policy"]["active_true_authorizations"]), sorted(checked["authorization"]))
        for path in checked["policy_values_without_defaults"]:
            node: Any = checked
            for part in path.split("."):
                node = node[part]
            self.assertIsNone(node, path)
        self.assertEqual(set(checked["development_arms"]), set(dev.DEVELOPMENT_ARMS))
        self.assertEqual(checked["passes"]["calibration_arm"]["config"], {"d_low": None})
        for arm in ("TAF", "RAC", "LOW", "VSMT-lean"):
            self.assertIn(arm, checked["development_configurations"])
        self.assertEqual(set(checked["development_configurations"]["TAF"]), set(arms.GRID_PARAMETERS["TAF"]))

    def test_the_development_configurations_are_frozen_grid_members_in_runner_form(self) -> None:
        """D-224-S1 ruling 68 (3)."""

        checked = dev.validate_development_contract(self.contract)
        self.assertEqual(checked["policy_values_without_defaults"], [])
        self.assertEqual(dev.development_configuration(checked, "TAF"), {"theta_a": 0.7, "d_a": None})
        self.assertEqual(dev.development_configuration(checked, "RAC"), {"theta_a": 0.7, "d_a": None, "rho_rac": 0.7, "n_rac": 3})
        self.assertEqual(dev.development_configuration(checked, "LOW"), {"d_low": 1.0})
        self.assertEqual(dev.development_configuration(checked, "VSMT-lean"), {"tau_r": 0.5})
        self.assertEqual(dev.development_configuration(checked, "NoVersion"), {"tau_r": 0.5})
        self.assertEqual(dev.development_configuration(checked, "AssocOnly"), {})
        for arm, config in dev.DEVELOPMENT_CONFIGURATIONS.items():
            with self.subTest(arm=arm):
                self.assertEqual(dev.development_configuration(checked, arm), config)
                lr.validate_arm_config(arm, config)
                if config:
                    self.assertIn(config, arms.enumerate_configs(arm, arms.FROZEN_GRIDS[arm]))
        still_open = copy.deepcopy(self.contract)
        still_open["development_configurations"]["TAF"]["theta_a"] = None
        still_open["policy_values_without_defaults"] = ["development_configurations.TAF.theta_a"]
        self.assertIsNone(dev.development_configuration(still_open, "TAF"))
        dev.validate_development_contract(still_open)  # an open slot is allowed while it is listed as open
        with self.assertRaises(dev.LeanDevelopmentError):
            dev.development_configuration(checked, "ELU-P")

    def test_weakened_claims_and_filled_open_slots_are_refused(self) -> None:
        for edit, code in (
            (lambda c: c["continue_gate"].__setitem__("no_winner_is_selected", False), "contract_claim_weakened:no_winner_is_selected"),
            (lambda c: c["passes"]["order"].reverse(), "contract_passes_mismatch"),
            (lambda c: c["development_configurations"]["TAF"].__setitem__("theta_a", 0.6), "contract_development_configuration_mismatch:TAF"),
            (lambda c: c["development_configurations"]["LOW"]["d_low"].__setitem__("distance_gate_m", 0.75), "development_configuration_not_a_grid_member:LOW"),
            (lambda c: c["development_configurations"]["RAC"]["d_a"].__setitem__("distance_gate_m", 1.0), "contract_development_configuration_mismatch:RAC"),
            (lambda c: c.pop("activation_policy"), "contract_bit_opened_without_a_ruling:development_run"),
            (lambda c: c["table"]["better"].__setitem__("node_prf1", "lower"), "contract_better_mismatch"),
        ):
            broken = copy.deepcopy(self.contract)
            edit(broken)
            with self.subTest(code=code), self.assertRaises(dev.LeanDevelopmentError) as caught:
                dev.validate_development_contract(broken)
            self.assertEqual(str(caught.exception), code)


if __name__ == "__main__":
    unittest.main()
