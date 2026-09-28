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

TRAIN = ("import json, pathlib, sys; out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True); "
         "(out / 'weights.json').write_text('{}'); "
         "(out / 'training_receipt.json').write_text(json.dumps({'diverged': sys.argv[2] != '0'})); sys.exit(int(sys.argv[2]))")
AUDIT = ("import pathlib, sys; weights = pathlib.Path(sys.argv[1]); target = pathlib.Path(sys.argv[2]); "
         "sys.exit(7) if not weights.exists() else (target.parent.mkdir(parents=True, exist_ok=True), target.write_text('{}'))")


class DriverQueueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.saved = {name: getattr(r79, name) for name in ("episodes", "expected_seconds", "git", "short_commit", "cpu_quota", "EXPORT_DIR")}
        self.saved_driver = {name: getattr(driver, name) for name in ("diag_root", "training_command", "audit_command", "time")}
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


if __name__ == "__main__":
    unittest.main()
