"""S3-07 (ruling 111-6): scene pooling and the report-only statistics (lean_s3_07)."""

from __future__ import annotations

import json
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vsmt import lean_arms as arms  # noqa: E402
from vsmt import lean_s3_05 as s5  # noqa: E402
from vsmt import lean_s3_07 as s7  # noqa: E402
from vsmt import lean_teacher as lt  # noqa: E402

SCENES = [f"{i:08x}-0000-0000-0000-000000000000" for i in (1, 2, 3, 4)]
RESCANS = {SCENES[0]: 3, SCENES[1]: 2, SCENES[2]: 1, SCENES[3]: 2}
EPISODES = [f"3rscan-{scene}-{i:08x}-1111-1111-1111-111111111111" for scene in SCENES for i in range(RESCANS[scene])]


def report(*, node: float, residual: int, judged: int, kept: int, events_judged: int, no_prior: int, successes: int, events: int,
           retracts: tuple[int, int] | None, latency: dict, auc: float) -> dict:
    """A frozen-shaped episode report with explicit counts."""

    def node_block(f1):
        return {"node_precision": f1, "node_recall": f1, "node_f1": f1, "matched": 10, "predicted": 12, "truth": 11}

    retract = ({"false_retract_rate": retracts[0] / retracts[1] if retracts[1] else None, "false_retracts": retracts[0],
                "judged_retracts": retracts[1], "ambiguous_retracts": 0} if retracts is not None
               else {"false_retract_rate": None, "false_retracts": 0, "judged_retracts": 0, "ambiguous_retracts": 0})
    finite = [v for v in latency.values() if v is not None]
    out = {
        "node_prf1": node_block(node), "node_prf1_iou": node_block(node * 0.8),
        "missing_residual_rate": {"missing_residual_rate": residual / judged if judged else None, "residual": residual,
                                  "judged": judged, "not_yet_observable": 1},
        "false_retract_rate": dict(retract), "false_retract_rate_in_scope": dict(retract),
        **lt.identity_continuity_blocks(kept=kept, judged=events_judged, no_prior_carrier=no_prior),
        "retrieval_success": lt.retrieval_success_block(successes=successes, events=events, no_query=0, empty_candidates=0),
        "recovery_latency_frames": {"recovery_latency_frames": sum(finite) / len(finite) if finite else None, "recovered": len(finite),
                                    "unrecovered": sorted(k for k, v in latency.items() if v is None), "never_observable": [],
                                    "per_object": dict(latency)},
        "contamination_auc": {"contamination_auc": auc, "frames": 100},
        "size_and_cost": {"active_entity_count": 10.0, "lifecycle_version_count": 3.0, "runtime_per_frame_s": 0.2, "peak_memory_bytes": 1000},
    }
    return lt.assert_report_keys(out)


def synthetic_runs(*, gain: float, rng: random.Random, drop: tuple[str, int | None, str] | None = None) -> list[dict]:
    plan = [(arm, None) for arm in ("TAF", "ELU-P", "RAC", "LOW", "HandCost")]
    plan += [(arm, seed) for arm in s7.LEARNED_ARMS for seed in arms.SEEDS]
    runs = []
    for arm, seed in plan:
        rows = {}
        for index, episode in enumerate(EPISODES):
            if drop == (arm, seed, episode):
                continue
            base = 0.4 + 0.02 * index + rng.uniform(-0.01, 0.01) + (gain if arm == "VSMT-lean" else 0.0)
            kept = 2 if arm == "VSMT-lean" else 1
            rows[episode] = {"episode_id": episode,
                             "report": report(node=min(base, 0.99), residual=1, judged=4, kept=kept, events_judged=3, no_prior=1,
                                              successes=2, events=3, retracts=None if arm in ("TAF", "LOW", "AssocOnly") else (1, 5),
                                              latency={"a": 2, "b": None}, auc=0.1),
                             "decomposition_totals": {"recall_miss": 1, "teacher_error": 2, "amortization_error": 3}}
        runs.append({"arm": arm, "seed": seed, "rows": rows})
    return runs


class PoolingTests(unittest.TestCase):
    def test_scene_of_reads_the_reference_scan(self) -> None:
        self.assertEqual(s7.scene_of(EPISODES[0]), SCENES[0])
        self.assertEqual({k: len(v) for k, v in s7.scenes_of(EPISODES).items()}, RESCANS)
        with self.assertRaisesRegex(s7.LeanS3_07Error, "episode_id_not_3rscan"):
            s7.scene_of("procthor10k-0.1.2-train-00001")

    def test_ratios_pool_by_summed_counts_and_frame_metrics_by_the_mean(self) -> None:
        a = report(node=0.6, residual=1, judged=2, kept=0, events_judged=2, no_prior=0, successes=1, events=1, retracts=(1, 1),
                   latency={"x": 2, "y": None}, auc=0.2)
        b = report(node=0.8, residual=0, judged=6, kept=3, events_judged=3, no_prior=1, successes=0, events=3, retracts=(0, 3),
                   latency={"x": 6}, auc=0.4)
        pooled = s7.pool_scene([a, b])
        self.assertAlmostEqual(pooled["missing_residual_rate"]["missing_residual_rate"], 1 / 8)  # not the mean of 0.5 and 0
        self.assertEqual((pooled["missing_residual_rate"]["residual"], pooled["missing_residual_rate"]["judged"]), (1, 8))
        self.assertAlmostEqual(pooled["identity_continuity"]["identity_continuity"], 3 / 6)
        self.assertAlmostEqual(pooled["identity_continuity_conditional"]["identity_continuity"], 3 / 5)
        self.assertAlmostEqual(pooled["retrieval_success"]["retrieval_success"], 1 / 4)
        self.assertAlmostEqual(pooled["false_retract_rate"]["false_retract_rate"], 1 / 4)
        self.assertAlmostEqual(pooled["node_prf1"]["node_f1"], 0.7)
        self.assertAlmostEqual(pooled["contamination_auc"]["contamination_auc"], 0.3)
        self.assertAlmostEqual(pooled["recovery_latency_frames"]["recovery_latency_frames"], 4.0)  # objects pooled: 2 and 6
        self.assertEqual(pooled["recovery_latency_frames"]["unrecovered"], ["0:y"])
        self.assertEqual(pooled["size_and_cost"]["peak_memory_bytes"], 1000)
        lt.assert_report_keys(pooled)

    def test_an_undefined_episode_makes_the_scene_undefined(self) -> None:
        a = report(node=0.6, residual=0, judged=0, kept=0, events_judged=0, no_prior=0, successes=0, events=0, retracts=None,
                   latency={}, auc=0.2)
        b = report(node=0.8, residual=1, judged=2, kept=1, events_judged=2, no_prior=0, successes=1, events=2, retracts=(1, 2),
                   latency={"x": 3}, auc=0.4)
        pooled = s7.pool_scene([a, b])
        self.assertAlmostEqual(pooled["missing_residual_rate"]["missing_residual_rate"], 0.5)  # counts pool: 0 judged adds nothing
        self.assertIsNone(s7.pool_scene([a])["missing_residual_rate"]["missing_residual_rate"])
        a["node_prf1"]["node_f1"] = None
        self.assertIsNone(s7.pool_scene([a, b])["node_prf1"]["node_f1"])  # a per-frame metric: any None -> None


class StatisticsTests(unittest.TestCase):
    def test_tables_are_by_scene_and_a_missing_episode_fails_its_scene(self) -> None:
        runs = synthetic_runs(gain=0.0, rng=random.Random(1), drop=("TAF", None, EPISODES[0]))
        block = s7.scene_tables(runs, EPISODES)
        self.assertEqual(sorted(block["per_metric"]["node_prf1"]), SCENES)
        self.assertEqual(block["failures"], [{"run": "TAF", "episode": EPISODES[0], "scene": SCENES[0]}])
        self.assertIsNone(block["per_metric"]["node_prf1"][SCENES[0]]["TAF"])
        self.assertIsNotNone(block["per_metric"]["node_prf1"][SCENES[0]]["ELU-P"])
        stats = s7.front_statistics(block, runs, seed=20261002, iterations=200)
        self.assertEqual(stats["exclusion_lists"]["node_prf1"]["excluded_scenes"], [SCENES[0]])
        self.assertEqual(stats["exclusion_lists"]["node_prf1"]["effective_scenes"], 3)
        self.assertEqual(stats["exclusion_lists"]["false_retract_rate"]["not_applicable_runs"][:1], ["AssocOnly:7"])

    def test_comparisons_report_a_difference_and_an_interval_without_a_verdict(self) -> None:
        runs = synthetic_runs(gain=0.1, rng=random.Random(2))
        block = s7.scene_tables(runs, EPISODES)
        stats = s7.front_statistics(block, runs, seed=20261002, iterations=300)
        node = stats["comparisons"]["node_prf1"]["AssocOnly"]
        self.assertTrue(node["evaluable"])
        self.assertAlmostEqual(node["mean_advantage"], 0.1, delta=0.02)
        self.assertLess(node["interval_90"][0], node["mean_advantage"])
        self.assertGreater(node["interval_90"][1], node["mean_advantage"])
        self.assertTrue(node["stable_82_1"])
        self.assertEqual(node["scenes"], 4)
        taf = stats["comparisons"]["identity_continuity"]["TAF"]
        self.assertAlmostEqual(taf["mean_advantage"], (2 - 1) / 4)  # pooled: 2 kept of 4 events against 1 of 4
        self.assertEqual(stats["comparisons"]["false_retract_rate"]["AssocOnly"], {"not_applicable": True})
        text = json.dumps(stats)
        self.assertNotIn('"passed"', text)
        self.assertNotIn("lower_bound", text)
        self.assertEqual(stats["main_table"]["identity_continuity"]["VSMT-lean"]["n"], 5)
        self.assertAlmostEqual(stats["main_table"]["identity_continuity"]["TAF"]["mean"], 0.25)
        # the interval reuses the S3-05 draws: the lower end equals the registered one-sided bound
        matrix = lt.seed_paired_matrix(block["per_metric"]["node_prf1"], arm="VSMT-lean", control="AssocOnly", direction="higher",
                                       houses=SCENES)
        self.assertEqual(node["interval_90"][0], lt.two_level_lower_bound(matrix, seed=20261002, iterations=300))

    def test_external_statistics_state_the_header_and_refuse_gate_blocks(self) -> None:
        runs = synthetic_runs(gain=0.0, rng=random.Random(3))
        block = s7.scene_tables(runs, EPISODES)
        front = s7.front_statistics(block, runs, seed=20261002, iterations=50)
        out = s7.external_statistics({"instance": front})
        self.assertEqual((out["header"], out["fronts_missing"]), (s7.HEADER, ["sam2"]))
        self.assertEqual(len(out["not_applicable"]), 5)
        self.assertNotIn("fixed_sequence", out)
        with self.assertRaisesRegex(s7.LeanS3_07Error, "gate_block_in_external_statistics"):
            s7.external_statistics({"instance": {**front, "primary_gate": {}}})
        with self.assertRaisesRegex(s7.LeanS3_07Error, "statistics_need_a_registered_front_end"):
            s7.external_statistics({"other": front})
        self.assertEqual(s5.REPORT_METRICS, s7.REPORT_METRICS)


if __name__ == "__main__":
    unittest.main()
