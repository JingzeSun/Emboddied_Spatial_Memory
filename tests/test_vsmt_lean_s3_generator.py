"""S3-02 generator stages (ruling 103-2 / 103-4 / 103-5): the S3 manifests, the S0-02 v3 rules only, the measurement and the receipts.

Pinned: the stages generate exactly the committed S3 lists and refuse a tampered manifest; any generation option that is not the
S0-02 v3 value, another salt, an unknown split or a manifest house absent from the source is refused before anything runs; the
occupancy of the measurement takes, per resource, the larger of the worker-only and the container reading, and the container's
CPU peak is the largest rate over a 30 s window; the generate stage derives its worker count by the S1-01 rule (an assumed
simulator limit is recorded as an extrapolation), marks the test root pending from its creation, never overwrites a split root
without --resume, keeps every receipt on --resume and fails an interrupted house, and writes one receipt per split in which the
ruling-36 move minimum is judged on train only.  CPU only, no simulator: the worker pool and the capacity reading are replaced.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT / "src", PROJECT_ROOT / "ops" / "vsmt"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import lean_s1_02a_pilot as g  # noqa: E402
from vsmt import lean_s3_manifests  # noqa: E402
from vsmt import lean_test_seal as ts  # noqa: E402

SALT = "a-test-salt-that-is-long-enough-for-the-rule-0123456789"
SALT_SHA = hashlib.sha256(SALT.encode("utf-8")).hexdigest()


def house_receipt(house: str, commit: str, *, status: str = "succeeded", null: bool = False, moves: int = 0, first: int = 0,
                  reason: str | None = None) -> dict:
    receipt = {"house_id": house, "source_index": int(house.rsplit("-", 1)[1]), "code_commit": commit, "status": status,
               "null_window": null, "occupancy": {"peak_rss_gb": 4.0, "cpu_seconds": 600.0, "wall_seconds": 1200.0, "bytes_written": 2e8}}
    if status == "succeeded":
        receipt.update({"executed_interventions": 0 if null else 2, "moves_executed": moves, "moves_source_first": first,
                        "controls": 2, "controls_outside_U": 1})
    else:
        receipt.update({"reason": reason or "intervention_window_unavailable", "detail": "feasible set empty"})
    return receipt


def s3_args(out_root: Path, **overrides) -> argparse.Namespace:
    values = dict(stage="s3", s3_splits="train,validation,test", output_root=str(out_root), measure_root=None,
                  source=str(out_root / "train.jsonl.gz"), workers=None, resume=False, simulator_concurrency_limit=16,
                  stall_timeout_s=1800, private_salt=SALT, **g.S3_REQUIRED_OPTIONS)
    values.update(overrides)
    return argparse.Namespace(**values)


class TestManifestAndReceipt(unittest.TestCase):
    def test_the_committed_lists(self) -> None:
        lists = g.s3_manifest_houses()
        manifest = json.loads(g.S3_MANIFESTS.read_text(encoding="utf-8"))
        self.assertEqual({k: len(v) for k, v in lists.items()}, {"train": 300, "validation": 50, "test": 100})
        self.assertEqual(lists["test"], manifest["test"])
        broken = copy.deepcopy(manifest)
        broken["validation"][3] = broken["train"][0]
        with self.assertRaises(lean_s3_manifests.LeanS3ManifestError):
            g.s3_manifest_houses(broken)

    def test_the_split_receipt_judges_the_move_minimum_on_train_only(self) -> None:
        houses = [f"procthor10k-0.1.2-train-{i:05d}" for i in range(6)]
        results = [house_receipt(houses[0], "c1", moves=70, first=40), house_receipt(houses[1], "c1", moves=60, first=19),
                   house_receipt(houses[2], "c1", null=True), house_receipt(houses[3], "c1", status="failed"),
                   house_receipt(houses[4], "c2", status="failed", null=True, reason="frame_write_failed"),
                   house_receipt("procthor10k-0.1.2-train-09999", "c1", moves=99, first=99)]  # another split's house
        receipt = g.s3_split_receipt("train", houses, results, commit="c2", salt_sha256="s", run={"actual_workers": 16})
        self.assertEqual((receipt["houses_planned"], receipt["houses_with_receipt"], receipt["houses_missing"]), (6, 5, [houses[5]]))
        self.assertEqual((receipt["succeeded"], receipt["failed"], receipt["null_window_episodes"], receipt["null_window_failed"]),
                         (3, 2, 2, 1))
        self.assertEqual(receipt["failures_by_reason"], {"frame_write_failed": 1, "intervention_window_unavailable": 1})
        self.assertEqual(receipt["yield_house_level_non_null"], 2 / 3)  # two succeeded with interventions out of three non-null
        self.assertEqual((receipt["moves_executed"], receipt["moves_source_first"]), (130, 59))
        self.assertEqual(receipt["move_minimum"]["below_minimum"], True)  # 59 source-first moves < 60
        self.assertEqual(receipt["code_commits"], ["c1", "c2"])
        self.assertEqual(receipt["actual_workers"], 16)
        validation = g.s3_split_receipt("validation", houses, results, commit="c2", salt_sha256="s", run={})
        self.assertEqual((validation["move_minimum"]["gate_applies"], validation["move_minimum"]["below_minimum"]), (False, None))


class TestMeasurement(unittest.TestCase):
    def test_machine_peaks(self) -> None:
        samples = [(0.0, 0, 1_000, 100.0), (10.0, 20_000_000, 3_000, 900.0), (40.0, 50_000_000, 2_000, None),
                   (70.0, 140_000_000, None, 500.0)]
        out = g.summarise_machine_samples(samples, window_s=30.0)
        # windows of at least 30 s: 0->40 (1.25 cores), 10->40 (1.0), 40->70 (3.0)
        self.assertAlmostEqual(out["cpu_cores_peak_window"], 3.0)
        self.assertEqual((out["process_memory_peak_bytes"], out["gpu0_used_peak_mib"], out["samples"]), (3_000, 900.0, 4))
        short = g.summarise_machine_samples(samples[:2], window_s=30.0)
        self.assertAlmostEqual(short["cpu_cores_peak_window"], 2.0)  # shorter than a window: the mean rate
        none = g.summarise_machine_samples([(0.0, None, None, None)])
        self.assertEqual((none["cpu_cores_peak_window"], none["process_memory_peak_bytes"], none["gpu0_used_peak_mib"]), (None, None, None))

    def test_occupancy_takes_the_larger_reading(self) -> None:
        results = [house_receipt(f"procthor10k-0.1.2-train-{i:05d}", "c") for i in range(4)]
        results[3] = house_receipt(results[3]["house_id"], "c", status="failed")
        results[0]["occupancy"].update(peak_rss_gb=5.0, bytes_written=3e8)
        machine = {"cpu_cores_peak_window": 8.0, "process_memory_peak_bytes": 30e9, "gpu0_used_peak_mib": 4096.0 + 1024.0}
        baseline = {"process_memory_bytes": 2e9, "gpu0_used_mib": 1024.0}
        occupancy = g.s3_occupancy(results, workers=4, machine=machine, baseline=baseline)
        self.assertEqual(tuple(occupancy), g.lean_pilot.OCCUPANCY_RECEIPT_FIELDS)
        self.assertAlmostEqual(occupancy["cpu_cores_per_worker"], 2.0)  # the container: 8 cores / 4 > 600 s / 1200 s
        self.assertAlmostEqual(occupancy["ram_gb_per_worker"], 7.0)  # (30 - 2) GB / 4 > 5 GB
        self.assertAlmostEqual(occupancy["vram_gb_per_worker"], 1.0)
        self.assertAlmostEqual(occupancy["disk_gb_per_worker"], 0.3)
        self.assertEqual((occupancy["simulator_concurrency_limit"], occupancy["failures"]), (4, [results[3]["house_id"]]))
        quiet = g.s3_occupancy(results, workers=4, machine={"cpu_cores_peak_window": None, "process_memory_peak_bytes": None,
                                                            "gpu0_used_peak_mib": None}, baseline={})
        self.assertEqual((quiet["cpu_cores_per_worker"], quiet["ram_gb_per_worker"], quiet["vram_gb_per_worker"]), (0.5, 5.0, 0.0))


class TestGenerateStage(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "s3-02-abc"
        measure = self.out / "measure"
        measure.mkdir(parents=True)
        occupancy = {"concurrency_verified_at": 4, "cpu_cores_per_worker": 1.5, "ram_gb_per_worker": 6.5, "vram_gb_per_worker": 0.6,
                     "disk_gb_per_worker": 0.4, "simulator_concurrency_limit": 4, "statistic": g.lean_pilot.REQUIRED_STATISTIC,
                     "workload": g.lean_pilot.REQUIRED_WORKLOAD, "failures": []}
        (measure / "occupancy_receipt.json").write_text(json.dumps(occupancy), encoding="utf-8")
        (measure / "measure_receipt.json").write_text(json.dumps({"mean_wall_seconds_per_house": 1100.0}), encoding="utf-8")
        self.lists = g.s3_manifest_houses()
        self.capacity = ({"cpu_logical_cores": 100, "ram_available_gb": 240.0, "gpu_free_vram_gb": 30.0, "disk_free_gb_asset_root": 400.0},
                         {"cgroup_cpu_quota": 100.0})
        self.ran: list[list[str]] = []

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def fake_pool(self, tasks, workers, stall, commit):
        self.ran.append([t["house_id"] for t in tasks])
        self.workers = workers
        out = []
        for index, task in enumerate(tasks):
            Path(task["out"]).mkdir(parents=True, exist_ok=True)
            receipt = house_receipt(task["house_id"], commit, moves=1, first=index % 2)
            Path(task["out"], "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
            out.append(receipt)
        return out

    def run_stage(self, args: argparse.Namespace) -> tuple[int, str]:
        pool = (i for i in range(10_000))
        buffer = io.StringIO()
        with mock.patch.object(g, "S3_SALT_SHA256", SALT_SHA), mock.patch.object(g, "_run_with_timeout", self.fake_pool), \
                mock.patch.object(g, "_s3_capacity_measurements", return_value=self.capacity), \
                mock.patch.object(g.house_loader, "records_from_json", return_value=((i, None) for i in pool)), \
                contextlib.redirect_stdout(buffer):
            code = g.main_s3(args)
        return code, buffer.getvalue()

    def test_refusals_before_anything_runs(self) -> None:
        for override in ({"dry_run_destinations_per_object": 0}, {"window_mode": "whole_transition"}, {"add_source": "spawn_asset"},
                         {"s3_splits": "train,train"}, {"s3_splits": "dev"}, {"private_salt": SALT + "x"}):
            code, text = self.run_stage(s3_args(self.out, **override))
            self.assertEqual(code, 2, (override, text))
        self.assertEqual(self.ran, [])
        with mock.patch.object(g.house_loader, "records_from_json", return_value=((i, None) for i in range(100))), \
                mock.patch.object(g, "S3_SALT_SHA256", SALT_SHA), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(g.main_s3(s3_args(self.out)), 2)  # manifest houses missing from the source

    def test_generate_resume_and_receipts(self) -> None:
        code, text = self.run_stage(s3_args(self.out))
        self.assertEqual(code, 0, text)
        self.assertEqual(self.ran, [self.lists["train"] + self.lists["validation"] + self.lists["test"]])
        self.assertEqual(self.workers, 16)  # the assumed simulator limit binds: CPU 53, RAM 29, VRAM 40, disk 800
        plan = json.loads((self.out / "plan.json").read_text(encoding="utf-8"))
        self.assertEqual((plan["derived"]["binding_constraint"], plan["derived"]["is_extrapolation"]), ("simulator_concurrency_limit", True))
        self.assertEqual((plan["simulator_concurrency_limit_verified"], plan["simulator_concurrency_limit_assumed"]), (4, 16))
        self.assertAlmostEqual(plan["projected_wall_hours"], round(450 * 1100.0 / 16 / 3600, 2))
        marker = json.loads((self.out / "test" / ts.MARKER_NAME).read_text(encoding="utf-8"))
        self.assertEqual((marker["kind"], marker["state"]), ("raw", ts.STATE_PENDING))
        self.assertFalse((self.out / "train" / ts.MARKER_NAME).exists())
        train = json.loads((self.out / "train" / g.S3_RECEIPT).read_text(encoding="utf-8"))
        self.assertEqual((train["succeeded"], train["moves_executed"], train["moves_source_first"]), (300, 300, 150))
        self.assertEqual((train["move_minimum"]["gate_applies"], train["move_minimum"]["below_minimum"]), (True, False))
        self.assertIn("wall_clock_seconds", train)  # the S1-02 exporter reads the S1-02b field name
        test = json.loads((self.out / "test" / g.S3_RECEIPT).read_text(encoding="utf-8"))
        self.assertEqual((test["houses_planned"], test["move_minimum"]["gate_applies"]), (100, False))
        # a second run without --resume never overwrites
        code, _text = self.run_stage(s3_args(self.out))
        self.assertEqual(code, 2)
        # --resume: every receipt kept, an interrupted house failed, a missing one run
        interrupted, missing = self.lists["validation"][0], self.lists["test"][5]
        (self.out / "validation" / interrupted / "receipt.json").unlink()
        for path in sorted((self.out / "test" / missing).iterdir()):
            path.unlink()
        (self.out / "test" / missing).rmdir()
        code, text = self.run_stage(s3_args(self.out, resume=True))
        self.assertEqual(code, 0, text)
        self.assertEqual(self.ran[-1], [missing])
        validation = json.loads((self.out / "validation" / g.S3_RECEIPT).read_text(encoding="utf-8"))
        self.assertEqual((validation["failed"], validation["failure_receipts"][0]["detail"]), (1, "interrupted_before_receipt"))
        self.assertEqual(len(list(self.out.glob("plan.resume-*.json"))), 1)

    def test_workers_default_derived_for_s3_and_four_for_the_s1_stages(self) -> None:
        salt_file = Path(self.tmp.name) / "salt.txt"
        salt_file.write_text(SALT, encoding="utf-8")
        seen = []
        common = ["--output-root", str(self.out), "--source", "x.jsonl.gz", "--private-salt-file", str(salt_file)]
        with mock.patch.object(g, "main_s3", side_effect=lambda a: seen.append((a.stage, a.workers)) or 0), \
                mock.patch.object(g, "main_s1_02b", side_effect=lambda a: seen.append((a.stage, a.workers)) or 0):
            for extra in (["--stage", "s3"], ["--stage", "s1-02b"], ["--stage", "s3", "--workers", "12"]):
                with mock.patch.object(sys, "argv", ["gen"] + extra + common):
                    g.main()
        self.assertEqual(seen, [("s3", None), ("s1-02b", 4), ("s3", 12)])
        code, _text = self.run_stage(s3_args(self.out, stage="s3-measure", workers=8))
        self.assertEqual(code, 2)  # the measurement runs at the pilot width only

    def test_no_measurement_no_generation(self) -> None:
        (self.out / "measure" / "occupancy_receipt.json").unlink()
        code, text = self.run_stage(s3_args(self.out))
        self.assertEqual(code, 2, text)
        self.assertEqual(self.ran, [])


if __name__ == "__main__":
    unittest.main()
