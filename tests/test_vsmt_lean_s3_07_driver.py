"""S3-07 (ruling 111-8 step 6): the driver ops/vsmt/s3_07_manifest.py -- E1 whitelist, E2 comparison, the job graph, the inputs
and the statistics step on synthetic merged audits."""

from __future__ import annotations

import json
import random
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for item in (ROOT / "src", ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import s3_07_manifest as drv  # noqa: E402
from vsmt import lean_arms as arms  # noqa: E402
from vsmt import lean_s3_04 as s4  # noqa: E402
from vsmt import lean_s3_07 as s7  # noqa: E402

SCENES = [f"{i:08x}-0000-0000-0000-000000000000" for i in (1, 2, 3)]
EPISODES = [f"3rscan-{scene}-{i:08x}-1111-1111-1111-111111111111" for scene in SCENES for i in range(2)]


class WhitelistTests(unittest.TestCase):
    def test_e1_allows_only_the_s3_07_files_and_the_registration_edits(self) -> None:
        recorded = {"files": {"src/vsmt/lean_memory.py": "a", "ops/vsmt/lean_s1_03_cache.py": "b",
                              "configs/vsmt/lean_s1_03_frontend_cache_v1.json": "c", "ops/vsmt/s3_05_manifest.py": "d"}}
        current = {"files": {"src/vsmt/lean_memory.py": "a", "ops/vsmt/lean_s1_03_cache.py": "b2",
                             "configs/vsmt/lean_s1_03_frontend_cache_v1.json": "c2", "ops/vsmt/s3_05_manifest.py": "d",
                             "src/vsmt/lean_s3_07.py": "e", "ops/vsmt/s3_07_manifest.py": "f", "configs/vsmt/lean_s3_07_3rscan_v1.json": "g"}}
        self.assertEqual(drv.disallowed_code_differences(recorded, current), [])
        current["files"]["src/vsmt/lean_memory.py"] = "changed"
        current["files"]["ops/vsmt/s3_06_new.py"] = "x"
        self.assertEqual(drv.disallowed_code_differences(recorded, current), ["added:ops/vsmt/s3_06_new.py", "changed:src/vsmt/lean_memory.py"])
        del current["files"]["ops/vsmt/s3_05_manifest.py"]
        self.assertIn("removed:ops/vsmt/s3_05_manifest.py", drv.disallowed_code_differences(recorded, current))

    def test_registration_problems_name_an_unregistered_commit_and_the_glob(self) -> None:
        problems = drv.registration_problems("0" * 40)
        self.assertTrue(any(p.startswith("converter_commit_not_registered") for p in problems))
        import lean_s1_03_cache as cache_runner

        globs = getattr(cache_runner, "EPISODE_DIRECTORY_GLOBS", ("procthor10k-*",))
        self.assertEqual(any(p.startswith("cache_generator_does_not_scan_3rscan") for p in problems), "3rscan-*" not in globs)


class E2Tests(unittest.TestCase):
    def test_e2_compares_seals_front_by_front(self) -> None:
        exports = {front: {"episodes": [{"episode_id": e, "episode_seal_sha256": f"{front}-{e}"} for e in drv.E2_EPISODES]}
                   for front in drv.FRONTS}
        regenerated = {front: {e: {"status": "succeeded", "episode_seal_sha256": f"{front}-{e}"} for e in drv.E2_EPISODES}
                       for front in drv.FRONTS}
        rows = drv.e2_comparison(regenerated, exports)
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row["identical"] for row in rows))
        regenerated["sam2"][drv.E2_EPISODES[1]]["episode_seal_sha256"] = "other"
        regenerated["instance"][drv.E2_EPISODES[0]] = {"status": "failed", "episode_seal_sha256": None}
        rows = drv.e2_comparison(regenerated, exports)
        self.assertEqual([(r["front"], r["episode_id"]) for r in rows if not r["identical"]],
                         [("instance", drv.E2_EPISODES[0]), ("sam2", drv.E2_EPISODES[1])])


def receipt_fixture() -> dict:
    runs = []
    for arm in ("TAF", "ELU-P"):
        runs.append({"arm": arm, "config_index": 0, "seed": None, "config": {"theta_a": 0.6}, "heads_arm": None})
    for arm in ("VSMT-lean", "AssocOnly"):
        for seed in arms.SEEDS:
            runs.append({"arm": arm, "config_index": 1, "seed": seed, "config": {"tau_r": 0.5}, "heads_arm": s4.heads_arm(arm)})
    return {"receipt_sha256": "r" * 64, "freeze_commit": "f" * 40, "fronts": {"instance": {"test_runs": runs, "probe_episodes": []}},
            "frozen_bytes": {"heads": {}, "elu_p_registered": {}}, "statistics": {"bootstrap_seed": 20261002, "bootstrap_iterations": 50}}


class GraphAndInputsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.run_root = self.root / "run"
        self.run_root.mkdir()
        self.s3_03 = self.root / "s3-03"
        (self.s3_03 / "instance" / "training" / "round1" / "VSMT-lean").mkdir(parents=True)
        drv.write_json(self.s3_03 / "inputs.json", {"fronts": ["instance"], "reid": {"instance": {"file": str(self.root / "reid.json")}},
                                                    "roots": {"raw": {}, "geometry": {}, "cache": {"instance": {}}}, "episodes": {}})
        self.inputs = {"fronts": ["instance"], "s3_03_run_root": str(self.s3_03), "receipt_sha256": "r" * 64,
                       "receipt": {"path": str(self.root / "receipt.json")},
                       "roots": {"raw": {"validation": str(self.root / "episodes")}, "geometry": {"validation": str(self.root / "geometry")},
                                 "cache": {"instance": {"validation": str(self.root / "cache" / "instance")}}},
                       "reid": {"instance": {"file": str(self.root / "reid.json")}},
                       "episodes": {"instance": {"validation": [{"episode_id": e, "frames": 100 + i} for i, e in enumerate(EPISODES)]}},
                       "cache_data_failures": {"instance": []}, "reader_check_failed": []}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_jobs_cover_every_run_and_episode_without_a_manifest_split(self) -> None:
        receipt = receipt_fixture()
        heads_paths = {}
        for seed in arms.SEEDS:
            for arm in ("VSMT-lean", "AssocOnly"):
                path = self.s3_03 / "instance" / "training" / "round1" / arm / f"s{seed}" / ("weights_grouped.json" if arm == "VSMT-lean" else "weights.json")
                heads_paths[str(path)] = "h"
        receipt["frozen_bytes"]["heads"] = heads_paths
        with mock.patch.object(drv.s303, "s3_descriptor", return_value="reid_projection:vitb14"):
            jobs = drv.build_jobs(self.run_root, self.inputs, receipt)
            self.assertEqual(len(jobs), 12 * len(EPISODES))
            argv = jobs[0].build()
        self.assertNotIn("--manifest-split", argv)
        self.assertNotIn("--test-receipt", argv)
        self.assertIn("--metrics-only", argv)
        self.assertEqual(argv[argv.index("--episode-root") + 1], str(Path(self.inputs["roots"]["raw"]["validation"]) / EPISODES[0]))
        self.assertEqual((jobs[0].kind, jobs[0].exit_status, jobs[0].retries), ("audit", {2: "gate_failed"}, 1))
        learned = [job for job in jobs if job.job_id.startswith("instance/external/VSMT-lean/s7/")]
        self.assertEqual(len(learned), len(EPISODES))
        self.assertTrue(learned[0].remote_push and learned[0].remote_push[0].endswith("weights_grouped.json"))
        receipt["frozen_bytes"]["heads"] = {}
        with self.assertRaisesRegex(drv.DriverError, "heads_not_frozen_by_the_receipt"), \
                mock.patch.object(drv.s303, "s3_descriptor", return_value="reid_projection:vitb14"):
            drv.build_jobs(self.run_root, self.inputs, receipt)

    def test_usable_episodes_drop_the_reader_check_failures(self) -> None:
        handoff = {"episodes": {"instance": [{"episode_id": e, "frames": 7} for e in EPISODES], "sam2": []}}
        out = drv.usable_episodes(handoff, [EPISODES[2]])
        self.assertEqual([row["episode_id"] for row in out["instance"]], [e for e in EPISODES if e != EPISODES[2]])

    def test_statistics_from_merged_files(self) -> None:
        receipt = receipt_fixture()
        rng = random.Random(5)
        for run in receipt["fronts"]["instance"]["test_runs"]:
            rows = []
            for index, episode in enumerate(EPISODES):
                node = 0.4 + 0.02 * index + rng.uniform(-0.01, 0.01) + (0.1 if run["arm"] == "VSMT-lean" else 0.0)
                rows.append({"episode_id": episode, "report": _report(node, run["arm"]),
                             "decomposition_totals": {"recall_miss": 1, "teacher_error": 0, "amortization_error": 2}})
            path = drv.merged_path(self.run_root, "instance", run)
            path.parent.mkdir(parents=True, exist_ok=True)
            drv.write_json(path, {"per_episode": rows})
        result = drv.statistics_from_merged(self.run_root, self.inputs, receipt)
        self.assertEqual(result["header"], s7.HEADER)
        front = result["fronts"]["instance"]
        self.assertEqual((front["scenes"], front["episodes"]), (3, 6))
        node = front["comparisons"]["node_prf1"]["AssocOnly"]
        self.assertTrue(node["evaluable"])
        self.assertAlmostEqual(node["mean_advantage"], 0.1, delta=0.03)
        self.assertNotIn("passed", json.dumps(result))
        self.assertEqual(front["decomposition_totals"]["TAF"]["amortization_error"], 2 * len(EPISODES))


def _report(node: float, arm: str) -> dict:
    from vsmt import lean_teacher as lt

    def block(f1):
        return {"node_precision": f1, "node_recall": f1, "node_f1": f1, "matched": 1, "predicted": 1, "truth": 1}

    retract = {"false_retract_rate": None if arm in ("TAF", "AssocOnly") else 0.2, "false_retracts": 0 if arm in ("TAF", "AssocOnly") else 1,
               "judged_retracts": 0 if arm in ("TAF", "AssocOnly") else 5, "ambiguous_retracts": 0}
    return lt.assert_report_keys({
        "node_prf1": block(node), "node_prf1_iou": block(node * 0.8),
        "missing_residual_rate": {"missing_residual_rate": 0.25, "residual": 1, "judged": 4, "not_yet_observable": 0},
        "false_retract_rate": dict(retract), "false_retract_rate_in_scope": dict(retract),
        **lt.identity_continuity_blocks(kept=2 if arm == "VSMT-lean" else 1, judged=3, no_prior_carrier=1),
        "retrieval_success": lt.retrieval_success_block(successes=1, events=2, no_query=0, empty_candidates=0),
        "recovery_latency_frames": {"recovery_latency_frames": 2.0, "recovered": 1, "unrecovered": [], "never_observable": [], "per_object": {"a": 2}},
        "contamination_auc": {"contamination_auc": 0.1, "frames": 50},
        "size_and_cost": {"active_entity_count": 5.0, "lifecycle_version_count": 2.0, "runtime_per_frame_s": 0.1, "peak_memory_bytes": 10},
    })


if __name__ == "__main__":
    unittest.main()
