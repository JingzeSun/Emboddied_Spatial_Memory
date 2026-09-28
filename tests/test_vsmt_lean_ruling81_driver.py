"""D-224 / S2-05 tests: the ruling-81 driver's dependency-aware queue, with stand-in training and audit commands.

Every audit starts only after its group's weights exist (the stand-in audit fails otherwise), the audits of a failed
training are skipped and reported, finished work is reused on a second run, and the status file lists every task.
CPU only, a few seconds.
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "ops" / "vsmt"))

import ruling79_diagnostics as r79  # noqa: E402
import ruling81_diagnostics as driver  # noqa: E402

TRAIN = ("import json, pathlib, sys, time; start = time.time(); time.sleep(0.2); out = pathlib.Path(sys.argv[1]); "
         "out.mkdir(parents=True, exist_ok=True); (out / 'times').write_text(f'{start} {time.time()}'); "
         "(out / 'weights.json').write_text('{}'); "
         "(out / 'training_receipt.json').write_text(json.dumps({'diverged': sys.argv[2] != '0'})); sys.exit(int(sys.argv[2]))")
AUDIT = ("import pathlib, sys; weights = pathlib.Path(sys.argv[1]); target = pathlib.Path(sys.argv[2]); "
         "sys.exit(7) if not weights.exists() else (target.parent.mkdir(parents=True, exist_ok=True), target.write_text('{}'))")


class DriverQueueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.saved = {name: getattr(r79, name) for name in ("episodes", "expected_seconds", "git", "short_commit", "cpu_quota", "EXPORT_DIR",
                                                            "cgroup_memory_gib")}
        r79.cgroup_memory_gib = lambda: {"max": None, "current": None}
        self.saved_driver = {name: getattr(driver, name) for name in ("diag_root", "training_command", "audit_command", "time")}
        self.saved_stage = dict(driver.STAGE)
        r79.episodes = lambda: ["e1", "e2", "e3"]
        r79.expected_seconds = lambda arm, episode: {"e1": 3.0, "e2": 2.0, "e3": 1.0}[episode]
        r79.git = lambda *arguments: "abc1234"
        r79.short_commit = lambda: "abc1234"
        r79.cpu_quota = lambda: 4
        r79.EXPORT_DIR = root / "exports"
        driver.diag_root = lambda: root / "diag"
        driver.training_command = lambda arm, condition, out, *extra: [sys.executable, "-c", TRAIN, str(out),
                                                                      "1" if (arm, condition) == ("AssocOnly", "C") else "0"]
        driver.audit_command = lambda arm, condition, episode: [sys.executable, "-c", AUDIT,
                                                               str(driver.training_dir(arm, condition) / "weights.json"),
                                                               str(driver.audit_path(arm, condition, episode))]
        driver.time = types.SimpleNamespace(sleep=lambda seconds: time.sleep(0.02), time=time.time, strftime=time.strftime)

    def tearDown(self) -> None:
        for name, value in self.saved.items():
            setattr(r79, name, value)
        for name, value in self.saved_driver.items():
            setattr(driver, name, value)
        driver.STAGE.clear()
        driver.STAGE.update(self.saved_stage)
        self.tmp.cleanup()

    def test_the_queue_respects_dependencies_skips_a_failed_group_and_resumes(self) -> None:
        code = driver.cmd_run(types.SimpleNamespace(workers=4))
        self.assertEqual(code, 1)  # AssocOnly-C failed on purpose
        status = json.loads((r79.EXPORT_DIR / "ruling81_diagnostics_abc1234.status.json").read_text())
        trainings = [r for r in status["results"] if r["kind"] == "training"]
        audits = [r for r in status["results"] if r["kind"] == "audit"]
        self.assertEqual(len(trainings), 8)
        self.assertEqual(sorted(r["exit"] for r in trainings), [0] * 7 + [1])
        self.assertEqual(len(audits), 24)
        skipped = [r for r in audits if r.get("skipped")]
        self.assertEqual({(r["arm"], r["condition"]) for r in skipped}, {("AssocOnly", "C")})
        self.assertEqual(len(skipped), 3)
        self.assertTrue(all(r["exit"] == 0 for r in audits if not r.get("skipped")))  # none started before its weights
        # a second run reuses everything that finished and only retries the failed group
        driver.training_command = lambda arm, condition, out, *extra: [sys.executable, "-c", TRAIN, str(out), "0"]
        self.assertEqual(driver.cmd_run(types.SimpleNamespace(workers=4)), 0)
        second = json.loads((r79.EXPORT_DIR / "ruling81_diagnostics_abc1234.status.json").read_text())
        self.assertEqual([(r["kind"], r["arm"], r["condition"]) for r in second["results"] if r["kind"] == "training"], [("training", "AssocOnly", "C")])
        self.assertEqual(sum(1 for r in second["results"] if r["kind"] == "audit"), 3)


class DriverMemoryTests(DriverQueueTests):
    """2026-09-28: trainings are admitted within the container memory (two of eight were killed at start on 62 GiB)."""

    def test_the_queue_respects_dependencies_skips_a_failed_group_and_resumes(self) -> None:  # covered by the parent class
        pass

    def test_no_more_trainings_run_at_once_than_the_memory_budget_allows(self) -> None:
        # room for B + one own-data training, or two own-data trainings, never three
        r79.cgroup_memory_gib = lambda: {"max": driver.MEMORY_RESERVE_GIB + 2 * driver.OWN_DATA_TRAINING_MEMORY_GIB + 0.5, "current": 1.0}
        driver.training_command = lambda arm, condition, out, *extra: [sys.executable, "-c", TRAIN, str(out), "0"]
        self.assertEqual(driver.cmd_run(types.SimpleNamespace(workers=8)), 0)
        spans = []
        for arm in driver.ARMS:
            for condition in driver.CONDITIONS:
                start, end = map(float, (driver.training_dir(arm, condition) / "times").read_text().split())
                spans.append((start, end))
        peak = max(sum(1 for s, e in spans if s <= t < e) for t, _ in spans)
        self.assertLessEqual(peak, 2)
        self.assertGreaterEqual(peak, 1)
        self.assertTrue(driver.fits(None, [11.0] * 9, 11.0))
        self.assertTrue(driver.fits(1.0, [], 11.0))  # a lone task always runs, so the queue cannot stall
        self.assertFalse(driver.fits(20.0, [11.0], 11.0))
        self.assertEqual((driver.training_memory_gib("B"), driver.training_memory_gib("A31")),
                         (driver.TRAINING_MEMORY_GIB, driver.OWN_DATA_TRAINING_MEMORY_GIB))

    def test_the_seed_study_stage_runs_only_its_three_seeds_under_its_own_names(self) -> None:
        driver.STAGE.update({"name": "ruling82", "conditions": driver.SEED_STUDY_CONDITIONS})
        driver.training_command = lambda arm, condition, out, *extra: [sys.executable, "-c", TRAIN, str(out), "0"]
        self.assertEqual(driver.cmd_run(types.SimpleNamespace(workers=4)), 0)
        status = json.loads((r79.EXPORT_DIR / "ruling82_diagnostics_abc1234.status.json").read_text())
        self.assertEqual(sorted({(r["arm"], r["condition"]) for r in status["results"] if r["kind"] == "training"}),
                         sorted((arm, c) for arm in driver.ARMS for c in ("A31", "A43", "A59")))
        self.assertEqual(sum(1 for r in status["results"] if r["kind"] == "audit" and r["exit"] == 0), 18)


if __name__ == "__main__":
    unittest.main()
