"""S3-05 (ruling 107): opening the seal once, the test-audit guard, the statistics, the driver's graph and the remote test kind."""

from __future__ import annotations

import argparse
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for item in (ROOT / "src", ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from vsmt import lean_arms as arms  # noqa: E402
from vsmt import lean_evaluation as ev  # noqa: E402
from vsmt import lean_s3_03 as s3  # noqa: E402
from vsmt import lean_s3_05 as s5  # noqa: E402
from vsmt import lean_teacher as lt  # noqa: E402
from vsmt import lean_test_seal as ts  # noqa: E402

HOUSES = ["procthor10k-0.1.2-train-00001", "procthor10k-0.1.2-train-00002", "procthor10k-0.1.2-train-00003"]


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sealed_roots(base: Path) -> tuple[dict[str, Path], dict]:
    roots = {kind: base / kind / "test" for kind in ts.SEAL_KINDS}
    for kind, root in roots.items():
        for house in HOUSES:
            write(root / house / "receipt.json", json.dumps({"status": "succeeded", "frames": 100}))
            write(root / house / "public" / "0000.frame.json", f"{kind}-{house}")
        write(root / "stage_receipt.json", json.dumps({"kind": kind}))
        ts.write_marker(root, kind=kind, state=ts.STATE_PENDING)
    seal, _digest = ts.seal_roots(roots, houses=HOUSES, tag="abc1234")
    return roots, seal


def report(base: float, *, events: int = 3, retract: bool = True) -> dict:
    out = {metric: {field: base} for metric, field in ev.HEADLINE_FIELD.items()}
    for metric in ("identity_continuity", "retrieval_success"):
        out[metric]["events"] = events
    if not retract:
        out["false_retract_rate"]["false_retract_rate"] = None
        out["false_retract_rate_in_scope"]["false_retract_rate"] = None
    out["size_and_cost"] = {"active_entity_count": 10.0, "runtime_per_frame_s": 0.2}
    return out


def synthetic_runs(houses: list[str], *, gain: float, rng: random.Random, drop: tuple[str, int | None, str] | None = None) -> list[dict]:
    runs = []
    plan = [(arm, None) for arm in ("TAF", "ELU-P", "RAC", "LOW", "HandCost")]
    plan += [(arm, seed) for arm in ("VSMT-lean", "NoVersion", "HeuristicLabel", "AssocOnly") for seed in arms.SEEDS]
    for arm, seed in plan:
        rows = {}
        for index, house in enumerate(houses):
            if drop is not None and (arm, seed, house) == drop:
                continue
            base = 0.3 + 0.01 * index + rng.uniform(-0.01, 0.01) + (gain if arm == "VSMT-lean" else 0.0)
            rows[house] = {"episode_id": house, "report": report(base, retract=arm not in ("TAF", "LOW", "AssocOnly")),
                           "decomposition_totals": {"recall_miss": 1, "teacher_error": 2, "amortization_error": 3}}
        runs.append({"arm": arm, "seed": seed, "rows": rows})
    return runs


class StatisticsTests(unittest.TestCase):
    """Ruling 107-4."""

    def test_the_interval_draws_as_the_registered_lower_bound(self):
        rng = random.Random(3)
        matrix = [[rng.uniform(-1, 1) for _ in range(5)] for _ in range(12)]
        low, high = s5.two_level_interval(matrix, seed=20261002, iterations=500)
        self.assertEqual(low, lt.two_level_lower_bound(matrix, seed=20261002, iterations=500))
        self.assertLess(low, high)

    def test_tables_mark_a_failure_none_everywhere(self):
        houses = [f"h{i}" for i in range(6)]
        runs = synthetic_runs(houses, gain=0.0, rng=random.Random(1), drop=("NoVersion", 19, "h2"))
        tables, failures = s5.tables(runs, houses)
        self.assertEqual(failures, [{"run": "NoVersion:19", "episode": "h2"}])
        self.assertIsNone(tables["node_prf1"]["h2"]["NoVersion:19"])
        self.assertEqual(tables["node_prf1"]["h2"]["TAF"], runs[0]["rows"]["h2"]["report"]["node_prf1"]["node_f1"])

    def test_both_front_ends_and_the_fixed_sequence(self):
        houses = [f"h{i}" for i in range(8)]
        per_front = {}
        for front, gain in (("instance", 0.2), ("sam2", 0.0)):
            runs = synthetic_runs(houses, gain=gain, rng=random.Random(7), drop=("HeuristicLabel", 31, "h5"))
            tables, failures = s5.tables(runs, houses)
            per_front[front] = s5.front_statistics(tables, runs, seed=20261002, iterations=300)
        out = s5.test_statistics(per_front)
        instance = per_front["instance"]
        self.assertTrue(instance["primary_gate"]["metrics"]["identity_continuity"]["passed"])  # VSMT-lean higher everywhere
        self.assertFalse(instance["primary_gate"]["metrics"]["missing_residual_rate"]["passed"])  # ...and so higher residual
        self.assertFalse(out["fixed_sequence"]["instance_segmentation_established"])
        self.assertTrue(instance["comparisons"]["false_retract_rate"]["TAF"]["not_applicable"])
        self.assertIn("h5", instance["comparisons"]["node_prf1"]["HeuristicLabel"]["extra_excluded_for_this_control"])
        self.assertEqual(instance["exclusion_lists"]["node_prf1"]["effective_houses"], 8)  # an ablation's failure is not in the main list
        self.assertEqual(len(instance["node_f1_vs_assoc_only"]["interval_90"]), 2)
        self.assertAlmostEqual(instance["node_f1_vs_assoc_only"]["difference"], 0.2, places=2)
        self.assertEqual(instance["main_table"]["node_prf1"]["VSMT-lean"]["n"], 5)
        self.assertEqual(instance["decomposition_totals"]["TAF"]["recall_miss"], 8)
        self.assertEqual(instance["main_table"]["false_retract_rate"]["TAF"], {"not_applicable": True})
        self.assertEqual(json.loads(json.dumps(out))["fixed_sequence"], out["fixed_sequence"])


class DriverTests(unittest.TestCase):
    """ops/vsmt/s3_05_manifest.py: the usable episodes after opening, the job graph, and the remote test kind."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_usable_episodes_and_the_graph(self):
        import s3_03_manifest as s303
        import s3_05_manifest as driver
        from vsmt import lean_object_geometry as og

        houses = [str(h) for h in s3.load_manifest()["test"][:3]]
        body = {"kinds": {}}
        for kind in ts.SEAL_KINDS:
            root = self.base / kind / "test"
            for house in houses:
                if kind == "sam2_cache" and house == houses[2]:
                    continue  # one SAM2 cache failed
                write(root / house / "receipt.json", json.dumps({"status": "succeeded", "frames": 50 + len(house)}))
                if kind == "geometry":
                    write(root / house / og.TABLE_FILE_NAME, "{}")
            body["kinds"][kind] = {"root": str(root), "succeeded": [h for h in houses if (root / h).exists()]}
        episodes, counts = driver.usable_episodes(body, ["instance", "sam2"])
        self.assertEqual([row["episode_id"] for row in episodes["instance"]], houses)
        self.assertEqual(len(episodes["sam2"]), 2)
        self.assertEqual(counts["usable_sam2"], 2)
        s3_03_root = self.base / "s3-03-run"
        s303.write_json(s3_03_root / "inputs.json", {"fronts": ["instance"], "roots": {}, "reid": {}, "episodes": {}})
        inputs = {"fronts": ["instance"], "s3_03_run_root": str(s3_03_root), "receipt": {"path": str(self.base / "receipt.json")},
                  "roots": {"raw": {"test": str(self.base / "raw" / "test")}, "geometry": {"test": str(self.base / "geometry" / "test")},
                            "cache": {"instance": {"test": str(self.base / "instance_cache" / "test")}}},
                  "reid": {"instance": {"file": "/reid.json"}}, "episodes": {"instance": {"test": episodes["instance"]}}}
        runs = [{"arm": "TAF", "config_index": 1, "config": {"theta_a": 0.7, "d_a": 0.5}, "seed": None, "heads_arm": None},
                {"arm": "NoVersion", "config_index": 4, "config": {"tau_r": 0.4}, "seed": 19, "heads_arm": "VSMT-lean"}]
        s3_03 = s303.load_context(s3_03_root)
        heads = str(s3_03.heads_file("instance", 1, "VSMT-lean", 19))
        receipt = {"fronts": {"instance": {"test_runs": runs}}, "frozen_bytes": {"heads": {heads: "x", "/reid.json": "y"}}}
        jobs = driver.build_jobs(self.base / "s3-05-run", inputs, receipt)
        self.assertEqual(len(jobs), 6)
        self.assertTrue(all(job.kind == "test" and not job.stops_on_failure and job.retries == 1 for job in jobs))
        self.assertTrue(all(job.exit_status == {2: "gate_failed"} for job in jobs))  # a refusal stops the run, never a data failure
        with self.assertRaisesRegex(driver.DriverError, "heads_not_frozen_by_the_receipt"):
            driver.build_jobs(self.base / "s3-05-run", inputs, {**receipt, "frozen_bytes": {"heads": {"/reid.json": "y"}}})
        argv = next(job for job in jobs if "NoVersion" in job.job_id).build()
        self.assertEqual(argv[argv.index("--manifest-split") + 1], "test")
        self.assertEqual(argv[argv.index("--test-receipt") + 1], str(self.base / "receipt.json"))
        self.assertIn("VSMT-lean", argv[argv.index("--heads") + 1])
        self.assertIn(str(self.base / "receipt.json"), next(job for job in jobs if "TAF" in job.job_id).remote_push)

    def test_the_remote_test_kind_needs_the_unsealed_inputs(self):
        import remote_hosts

        run_root = self.base / "s3-05-run"
        remote_hosts.write_json(run_root / "inputs.json", {"fronts": ["instance"], "reid": {"instance": {"file": "/reid.json"}},
                                                          "roots": {"raw": {"validation": "/v"}, "geometry": {"validation": "/g"},
                                                                    "cache": {"instance": {"validation": "/c"}}}})
        with self.assertRaises(remote_hosts.RemoteError):
            remote_hosts.static_paths(run_root, kinds=["test"])
        remote_hosts.write_json(run_root / "inputs.json", {
            "fronts": ["instance"], "reid": {"instance": {"file": "/reid.json"}}, "seal": {"file": "/seal.json"},
            "receipt": {"path": "/receipt.json"},
            "roots": {"raw": {"test": "/t/raw"}, "geometry": {"test": "/t/geo"}, "cache": {"instance": {"test": "/t/cache"}}}})
        with self.assertRaises(KeyError):  # the S3-05 inputs name the S3-03 run whose validation inputs come along
            remote_hosts.static_paths(run_root, kinds=["test"])
        s3_03_root = self.base / "s3-03-run"
        remote_hosts.write_json(s3_03_root / "inputs.json", {"roots": {"raw": {"validation": "/v/raw"}, "geometry": {"validation": "/v/geo"},
                                                                      "cache": {"instance": {"validation": "/v/cache"}}}})
        inputs = remote_hosts.load_json(run_root / "inputs.json")
        remote_hosts.write_json(run_root / "inputs.json", {**inputs, "s3_03_run_root": str(s3_03_root)})
        paths = remote_hosts.static_paths(run_root, kinds=["test"])
        for path in ("/t/raw", "/t/geo", "/t/cache", "/seal.json", "/receipt.json", "/reid.json", "/v/raw", "/v/geo", "/v/cache"):
            self.assertIn(path, paths)
        self.assertTrue(remote_hosts.skipped("/t/raw/TEST_READ.json"))  # rewritten by every copy: outside the comparison
        self.assertTrue(remote_hosts.skipped("/t/raw/TEST_SEALED.json.tmp"))
        self.assertFalse(remote_hosts.skipped("/t/raw/procthor10k-0.1.2-train-00001/receipt.json"))

    def test_unseal_opens_only_for_the_checked_receipt(self):
        import s3_05_manifest as driver
        from vsmt import lean_s3_04 as s4

        run_root = self.base / "s3-05-run"
        receipt = {"freeze_commit": "f" * 40, "fronts": {}}
        receipt["receipt_sha256"] = s4.receipt_body_sha256(receipt)
        other = {**receipt, "fronts": {"instance": {}}}
        other["receipt_sha256"] = s4.receipt_body_sha256(other)
        path = self.base / "other.json"
        path.write_text(json.dumps(other), encoding="utf-8")
        driver.write_json(run_root / "check.json", {"pass": True, "code_commit": driver.git("rev-parse", "HEAD"),
                                                     "receipt": {"receipt_sha256": receipt["receipt_sha256"]}})
        code = driver.main(["unseal", "--run-root", str(run_root), "--receipt", str(path), "--s3-03-run-root", str(self.base / "s3-03"),
                            "--export-dir", str(self.base)])
        self.assertEqual(code, 2)  # refused before any seal is touched

    def test_relay_runs_rsync_on_the_relay_host(self):
        import remote_hosts

        relay = remote_hosts.Host({"name": "w4", "address": "a.example", "port": 1, "key": "/k", "budget_cores": 1, "budget_gib": 1,
                                   "kinds": ["test"]})
        target = remote_hosts.Host({"name": "w1", "address": "b.example", "port": 2, "key": "/k", "budget_cores": 1, "budget_gib": 1,
                                    "kinds": ["test"]})
        argv = remote_hosts.relay_argv(relay, target, "/root/data", key="/root/.ssh/relay")
        self.assertIn("root@a.example", argv)
        self.assertIn("rsync", argv[-1])
        self.assertIn("root@b.example:/", argv[-1])


if __name__ == "__main__":
    unittest.main()
