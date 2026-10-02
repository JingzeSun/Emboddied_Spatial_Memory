"""S3-02 speed bench tests: the summaries the bench driver writes (user 2026-10-03, 「1 卡 5090 测速，写测速脚本，测 ①②③④⑤」).

Pinned: episodes are picked from succeeded development receipts (median or largest); a cache trial's throughput is the frames it
completed over its whole wall clock, a data failure leaves a trial usable and any other failure drops it, every trial must have done
the same work, and episode seals are compared across trials and across the sequential and parallel cache runs; the sampler summary
gives the container's CPU, memory and GPU peaks; the profile summary groups time by project module and library; prepared tensors
are counted in bytes; the S1-01 bounds are computed at one, two and four cards; the check refuses an input root inside a sealed S3
test root; the driver's stage list matches its functions.  CPU only, a few seconds.
"""
from __future__ import annotations

import contextlib
import cProfile
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for item in (PROJECT_ROOT / "src", PROJECT_ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import s3_02_bench as bench  # noqa: E402
from vsmt import lean_test_seal as ts  # noqa: E402

DRIVER = PROJECT_ROOT / "ops" / "vsmt" / "s3_02_bench.sh"


def write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")


def quiet(function, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return function(*args, **kwargs)


def trial(root: Path, wall: float, rows: dict) -> Path:
    write(root / "trial_receipt.json", {"wall_clock_seconds": wall, "actual_workers": 2, "peak_vram_reserved_mib_max": 5300.0})
    for episode, row in rows.items():
        write(root / episode / "receipt.json", row)
    return root


def ok(frames: int, seal: str) -> dict:
    return {"status": "succeeded", "frames_processed": frames, "episode_seal_sha256": seal}


class TestEpisodes(unittest.TestCase):
    def test_succeeded_episodes_largest_first_and_the_median(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a, b, cache = Path(tmp) / "a", Path(tmp) / "b", Path(tmp) / "cache"
            write(a / "procthor10k-0.1.2-train-00001" / "receipt.json", {"status": "succeeded", "observations": 300})
            write(a / "procthor10k-0.1.2-train-00002" / "receipt.json", {"status": "failed", "observations": 900})
            write(b / "procthor10k-0.1.2-train-00003" / "receipt.json", {"status": "succeeded", "observations": 700})
            write(b / "procthor10k-0.1.2-train-00004" / "receipt.json", {"status": "succeeded", "observations": 500})
            rows = bench.episode_sizes([str(a), str(b)])
            self.assertEqual([r[0][-5:] for r in rows], ["00003", "00004", "00001"])
            self.assertEqual(bench.pick_episode(rows, "median")[0][-5:], "00004")
            self.assertEqual(bench.pick_episode(rows, "largest")[2], 700)
            write(cache / "procthor10k-0.1.2-train-00003" / "receipt.json", {"status": "failed"})
            write(cache / "procthor10k-0.1.2-train-00001" / "receipt.json", {"status": "succeeded"})
            self.assertEqual([r[0][-5:] for r in bench.episode_sizes([str(a), str(b)], str(cache))], ["00001"])


class TestTrials(unittest.TestCase):
    def test_throughput_choice_failures_and_seals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            e1, e2 = "procthor10k-0.1.2-train-00001", "procthor10k-0.1.2-train-00002"
            roots = {1: trial(base / "k1", 120.0, {e1: ok(60, "s1"), e2: ok(60, "s2")}),
                     2: trial(base / "k2", 80.0, {e1: ok(60, "s1"), e2: {"status": "failed", "reason": "proposal_overflow",
                                                                           "frames_processed": 20}}),
                     3: trial(base / "k3", 50.0, {e1: ok(60, "s1"), e2: {"status": "failed", "reason": "public_input_missing_or_malformed",
                                                                           "frames_processed": 0}})}
            out = bench.scaling_summary(roots)
        trials = out["trials"]
        self.assertEqual((trials["1"]["frames_per_second"], trials["2"]["frames_per_second"]), (1.0, 1.0))
        self.assertEqual((trials["2"]["data_failures"], trials["3"]["other_failures"]), (1, 1))
        self.assertEqual(out["best_workers_per_card"], 1)  # 3 is fastest but failed for a non-data reason; 1 and 2 tie, fewer wins
        self.assertTrue(out["same_work_in_every_trial"])
        self.assertEqual((out["seals"]["episodes_compared"], out["seals"]["all_equal"]), (1, True))

    def test_different_seals_and_different_work_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            e1, e2 = "procthor10k-0.1.2-train-00001", "procthor10k-0.1.2-train-00002"
            out = bench.scaling_summary({1: trial(base / "k1", 60.0, {e1: ok(60, "a")}),
                                         2: trial(base / "k2", 60.0, {e1: ok(60, "b"), e2: ok(60, "c")})})
        self.assertFalse(out["same_work_in_every_trial"])
        self.assertEqual(out["seals"]["differ"], ["procthor10k-0.1.2-train-00001"])

    def test_the_caches_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            e1 = "procthor10k-0.1.2-train-00001"
            roots = {"seq-instance": trial(base / "si", 100.0, {e1: ok(600, "i")}),
                     "seq-sam2": trial(base / "ss", 200.0, {e1: ok(120, "s")}),
                     "par-instance": trial(base / "pi", 150.0, {e1: ok(600, "i")}),
                     "par-sam2": trial(base / "ps", 220.0, {e1: ok(120, "x")})}
            samples = base / "samples.jsonl"
            write(samples, "\n".join(json.dumps(r) for r in (
                {"t": 0.0, "cpu_usec": 0, "memory_bytes": 2 ** 30, "gpu_memory_mib": 1000.0, "gpu_utilization_pct": 50.0},
                {"t": 2.0, "cpu_usec": 8_000_000, "memory_bytes": 3 * 2 ** 30, "gpu_memory_mib": 9000.0, "gpu_utilization_pct": 90.0},
                {"t": 4.0, "cpu_usec": 12_000_000, "memory_bytes": 2 * 2 ** 30, "gpu_memory_mib": 8000.0, "gpu_utilization_pct": 100.0})) + "\n{cut")
            out = bench.caches_summary(roots, {"sequential": 300.0, "parallel": 225.0}, {"parallel": samples})
        self.assertEqual(out["parallel_over_sequential"], 0.75)
        self.assertEqual((out["instance_rate_together_over_alone"], out["sam2_rate_together_over_alone"]), (0.667, 0.909))
        self.assertTrue(out["instance_seals"]["all_equal"])
        self.assertEqual(out["sam2_seals"]["differ"], [e1])
        resources = out["resources"]["parallel"]
        self.assertEqual((resources["samples"], resources["cpu_cores_peak"], resources["cpu_cores_mean"]), (3, 4.0, 3.0))
        self.assertEqual((resources["memory_peak_gib"], resources["gpu_memory_peak_mib"], resources["gpu_utilization_mean_pct"]), (3.0, 9000.0, 80.0))
        self.assertEqual(bench.summarise_samples(base / "none.jsonl"), {"samples": 0})


class TestProfileTensorsCompat(unittest.TestCase):
    def test_profile_summary_groups_time(self) -> None:
        def work() -> int:
            return sum(json.loads(json.dumps(list(range(2000))))[:10])

        with tempfile.TemporaryDirectory() as tmp:
            prof = Path(tmp) / "x.prof"
            profiler = cProfile.Profile()
            profiler.runcall(work)
            profiler.dump_stats(str(prof))
            out = bench.profile_summary(prof, top=5)
            measured = Path(tmp) / "m.json"
            write(measured, {"wall_seconds": 10.0, "exit": 0})
            report = Path(tmp) / "r.json"
            self.assertEqual(quiet(bench.main, ["profile", "--prof", f"TAF={prof},{measured}", "--episode", "e", "--frames", "4",
                                                "--out", str(report)]), 0)
            written = json.loads(report.read_text(encoding="utf-8"))
        self.assertIn("json", out["by_bucket"])
        self.assertLessEqual(len(out["top_cumulative"]), 5)
        self.assertEqual(written["profiles"]["TAF"]["seconds_per_frame_under_profile"], 2.5)
        self.assertEqual(bench.bucket_of("/root/x/src/vsmt/lean_runner.py"), "lean_runner.py")
        self.assertEqual(bench.bucket_of("/usr/lib/python3/site-packages/numpy/core/x.py"), "numpy")

    def test_tensor_bytes_and_worker_bounds(self) -> None:
        import torch

        prepared = {"pairs": torch.zeros((3, 14)), "index": torch.zeros((2, 4), dtype=torch.long),
                    "existence": (torch.zeros((5, 17)), torch.zeros(5), 5), "fragments": 2, "nothing": None}
        self.assertEqual(bench.tensor_bytes(prepared), 3 * 14 * 4 + 2 * 4 * 8 + 5 * 17 * 4 + 5 * 4)
        bounds = bench.workers_at({"cpu_cores_per_worker": 2.0, "ram_gb_per_worker": 5.0}, cores=25, memory_gib=90)
        self.assertEqual((bounds["by_cpu"], bounds["by_memory"], bounds["bound"]), (10, 15, 10))

    def test_compat_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            measure, out = Path(tmp) / "measure", Path(tmp) / "out.json"
            self.assertEqual(quiet(bench.main, ["compat", "--measure-root", str(measure), "--measured", str(measure / "m.json"),
                                                "--out", str(out)]), 3)
            write(measure / "measure_receipt.json", {"houses": ["a", "b", "c", "d"], "succeeded": 3, "failed": 1, "wall_clock_seconds": 900,
                                                      "occupancy": {"cpu_cores_per_worker": 2.5, "ram_gb_per_worker": 6.0}})
            self.assertEqual(quiet(bench.main, ["compat", "--measure-root", str(measure), "--measured", str(measure / "m.json"),
                                                "--out", str(out)]), 0)
            report = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual([b["bound"] for b in report["workers_by_quota"]], [8, 16, 32])


class TestCheckAndDriver(unittest.TestCase):
    def test_the_check_refuses_a_sealed_test_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            sealed = base / "caches" / "test"
            ts.write_marker(sealed, kind="sam2_cache", state=ts.STATE_PENDING)
            out = base / "check.json"
            args = ["check", "--out", str(out), "--repo-root", str(PROJECT_ROOT), "--autodl-root", str(base),
                    "--episode-roots", str(base / "raw"), "--sam2-cache", str(sealed), "--instance-cache", str(base / "i"),
                    "--geometry-root", str(base / "g"), "--assets-json", str(base / "a.json"), "--sam2-reid", str(base / "s.json"),
                    "--instance-reid", str(base / "r.json"), "--source", str(base / "src.gz"), "--salt-file", str(base / "salt"),
                    "--sim-python", str(base / "no-python"), "--heads", str(base / "h.json"), "--record-source", f"{base}:dagger_round_0:ELU-P"]
            self.assertEqual(quiet(bench.main, args), 3)
            report = json.loads(out.read_text(encoding="utf-8"))
        self.assertTrue(any(p.startswith("sealed:") for p in report["problems"]))
        self.assertEqual(report["inputs"]["record_sources"][f"{base}:dagger_round_0:ELU-P"]["episodes"], 0)

    def test_the_driver_runs_each_stage_with_its_function(self) -> None:
        text = DRIVER.read_text(encoding="utf-8")
        stages = re.search(r'^STAGES="([^"]+)"', text, re.M).group(1).split()
        self.assertEqual(stages, ["check", "compat", "sam2-scaling", "caches", "audit-profile", "train-device", "collect"])
        for stage in stages:
            self.assertRegex(text, rf"(?m)^stage_{stage.replace('-', '_')}\(\) \{{", stage)
        self.assertNotIn("\r\n", DRIVER.read_bytes().decode("utf-8"))
        for needle in ("--stage s3-measure", "--trial-frame-limit", "--gpus 0", "-m cProfile", "train-bench", "--devices cpu,cuda"):
            self.assertIn(needle, text)
        self.assertNotIn("vsmt_outputs/s3-02", text)  # the bench never writes into the S3-02 roots
        # the cache builder refuses a trial whose output root does not end in -trial (the first bench run stopped there)
        roots = re.findall(r'"\$\{CACHE\[@\]\}" --output-root "([^"]+)"', text)
        self.assertEqual(len(roots), 5)
        self.assertTrue(all(root.endswith("-trial") for root in roots), roots)
        self.assertIn('T=$OUT/sam2-k$K-trial', text)
        self.assertTrue(all(run.endswith('-trial"') for run in re.findall(r'--run "[a-z0-9-]+=\$ROOT/[a-z0-9-]+"', text)))


if __name__ == "__main__":
    unittest.main()
