"""Ruling 105 tests: the LLM-op run of record through the node-audit entry, and the driver (plan, run loop), without the network.

Pinned here: the node audit runs --arm LLM-op only as a metrics-only run of record on validation with one archive per
episode, refuses it while the contract bit is closed or the pilot has not registered the model, and a replay from the
archive alone reproduces the live audit with no call; the driver's plan refuses a sealed test root, draws fifteen episodes
by the salted order and lists the paths to copy (the pilot's private plane excluded); its run loop starts every episode once,
starts none once the ledger reaches the cap, and writes STOP at the safety stop.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for item in (PROJECT_ROOT / "src", PROJECT_ROOT / "ops" / "vsmt", PROJECT_ROOT / "tests"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import lean_s2_05_node_audit as audit_module  # noqa: E402
import llm_op as driver  # noqa: E402
from vsmt import lean_llm_op as llm  # noqa: E402
from test_vsmt_lean_llm_op import SERVED, ScriptedTransport, TempDir, opened_contract  # noqa: E402
from test_vsmt_lean_node_audit import SyntheticEntryFixture  # noqa: E402


class NodeAuditIntegrationTests(SyntheticEntryFixture, unittest.TestCase):
    """The run of record: --arm LLM-op through the real node-audit entry, live past the archive's end, then replay alone."""

    def llm_args(self, out: Path, archive: Path, run_root: Path, *, mode: str, **override) -> argparse.Namespace:
        args = self.args("TAF", out=out, metrics_only=True)
        values = dict(arm="LLM-op", config="{}", episode_id=self.validation_id, manifest_split="validation",
                      llm_op_archive=str(archive), llm_op_mode=mode, llm_op_run_root=str(run_root))
        values.update(override)
        for name, value in values.items():
            setattr(args, name, value)
        return args

    def audit(self, out: Path) -> dict[str, Any]:
        return json.loads((out / self.validation_id / "LLM-op" / audit_module.AUDIT_FILE_NAME).read_text(encoding="utf-8"))

    def test_refused_while_the_bit_is_closed_and_off_the_run_of_record(self) -> None:
        run_root = self.tmp / "refusals"
        run_root.mkdir(exist_ok=True)
        archive = run_root / "a.jsonl"
        self.assertEqual(self.run_entry(self.llm_args(self.tmp / "r0", archive, run_root, mode="replay")), 2)  # bit closed
        with mock.patch.object(llm, "load_contract", opened_contract):
            for override in ({"metrics_only": False}, {"manifest_split": None}, {"llm_op_archive": None}, {"config": '{"tau_r": 0.5}'}):
                with self.subTest(override=override):
                    self.assertEqual(self.run_entry(self.llm_args(self.tmp / "r1", archive, run_root, mode="replay", **override)), 2)
            with mock.patch.dict(os.environ, {llm.KEY_ENV: "sk-test"}):  # live without the pilot's model.json
                self.assertEqual(self.run_entry(self.llm_args(self.tmp / "r2", archive, run_root, mode="live")), 2)
        self.assertFalse(archive.exists())

    def test_live_then_replay_alone_gives_the_same_audit_and_no_call(self) -> None:
        run_root = self.tmp / "llm-op-run"
        run_root.mkdir(exist_ok=True)
        (run_root / llm.MODEL_FILE).write_text(json.dumps({"model": SERVED}), encoding="utf-8")
        archive = run_root / "archive" / "instance" / f"{self.validation_id}.jsonl"
        transports: list[ScriptedTransport] = []

        def fake_transport(**kwargs: Any) -> ScriptedTransport:
            transports.append(ScriptedTransport())
            return transports[-1]

        with mock.patch.object(llm, "load_contract", opened_contract), mock.patch.object(llm, "HttpTransport", fake_transport), \
                mock.patch.dict(os.environ, {llm.KEY_ENV: "sk-test"}):
            self.assertEqual(self.run_entry(self.llm_args(self.tmp / "live", archive, run_root, mode="live")), 0)
            self.assertEqual(self.run_entry(self.llm_args(self.tmp / "replay", archive, run_root, mode="replay")), 0)
        live, replay = self.audit(self.tmp / "live"), self.audit(self.tmp / "replay")
        self.assertEqual(len(transports), 1)
        self.assertGreater(len(transports[0].bodies), 0)
        self.assertEqual(live["trajectory_sha256"], replay["trajectory_sha256"])
        # everything but timing, commit and mode (the comparison the driver's replay-check makes)
        self.assertEqual(audit_module.comparable_metrics({k: v for k, v in live.items() if k != "llm_op"}),
                         audit_module.comparable_metrics({k: v for k, v in replay.items() if k != "llm_op"}))
        self.assertEqual(live["llm_op"]["archive_sha256"], replay["llm_op"]["archive_sha256"])
        self.assertEqual(replay["llm_op"]["mode"], "replay")
        self.assertEqual(replay["llm_op"]["association"]["replayed_attempts"], replay["llm_op"]["association"]["attempts"])
        self.assertTrue(live["metrics_only"])
        self.assertTrue(driver.audit_complete(self.tmp / "live" / self.validation_id / "LLM-op" / audit_module.AUDIT_FILE_NAME,
                                              self.validation_id))


class DriverPlanTests(TempDir):
    def build(self, validation: int = 20, train: int = 5) -> Path:
        roots = {"raw": {}, "geometry": {}, "cache": {"instance": {}, "sam2": {}}}
        episodes: dict[str, dict[str, list]] = {"instance": {"validation": [], "train": []}, "sam2": {"validation": [], "train": []}}
        for split, count, frames in (("validation", validation, 300), ("train", train, 180)):
            roots["raw"][split] = str(self.tmp / "raw" / split)
            roots["geometry"][split] = str(self.tmp / "geometry" / split)
            for front in llm.FRONTS:
                roots["cache"][front][split] = str(self.tmp / f"cache-{front}" / split)
            for index in range(count):
                episode = f"procthor10k-0.1.2-train-{index + (0 if split == 'validation' else 5000):05d}"
                n = frames + index * 10
                raw = self.tmp / "raw" / split / episode
                (raw / "public").mkdir(parents=True)
                (raw / "receipt.json").write_text(json.dumps({"code_commit": "x"}), encoding="utf-8")
                geometry = self.tmp / "geometry" / split / episode
                geometry.mkdir(parents=True)
                (geometry / "object_geometry.json").write_text("{}", encoding="utf-8")
                for front in llm.FRONTS:
                    cache = self.tmp / f"cache-{front}" / split / episode
                    cache.mkdir(parents=True)
                    (cache / "episode_seal.json").write_text(json.dumps({"payload_sha256": f"{front}-{episode}"}), encoding="utf-8")
                    episodes[front][split].append({"episode_id": episode, "frames": n})
        s3 = self.tmp / "s3-03-run"
        for front in llm.FRONTS:
            receipt = s3 / front / "round0" / "procthor10k-0.1.2-train-05000" / "ELU-P" / "receipt.json"
            receipt.parent.mkdir(parents=True)
            receipt.write_text(json.dumps({"status": "succeeded", "frames": 100, "existence_candidates": 3600,
                                           "nuisance_probes": {"association_rows": 980}}), encoding="utf-8")
        for front in llm.FRONTS:
            head = self.tmp / f"reid-{front}.json"
            head.write_text("{}", encoding="utf-8")
        inputs = {"run_root": str(s3), "code_commit": "s3commit", "provisional": True, "roots": roots, "episodes": episodes,
                  "reid": {front: {"file": str(self.tmp / f"reid-{front}.json"), "file_sha256": "f", "payload_sha256": "p"} for front in llm.FRONTS}}
        path = self.tmp / "inputs.json"
        path.write_text(json.dumps(inputs), encoding="utf-8")
        return path

    def test_the_plan_refuses_a_sealed_test_root(self) -> None:
        inputs = self.build()
        (self.tmp / "raw" / "validation" / "TEST_SEALED.json").write_text("{}", encoding="utf-8")
        with mock.patch.object(driver, "git", lambda *a: "c0ffee"):
            self.assertEqual(driver.plan(argparse.Namespace(run_root=str(self.tmp / "run"), inputs=str(inputs))), 2)
        self.assertFalse((self.tmp / "run" / "plan.json").exists())

    def test_the_plan_draws_fifteen_by_the_salted_order_and_lists_what_to_copy(self) -> None:
        inputs = self.build()
        run_root = self.tmp / "run"
        with mock.patch.object(driver, "git", lambda *a: "c0ffee"):
            self.assertEqual(driver.plan(argparse.Namespace(run_root=str(run_root), inputs=str(inputs))), 0)
            self.assertEqual(driver.plan(argparse.Namespace(run_root=str(run_root), inputs=str(inputs))), 2)  # written once
        plan = json.loads((run_root / "plan.json").read_text(encoding="utf-8"))
        everyone = [f"procthor10k-0.1.2-train-{i:05d}" for i in range(20)]
        order = sorted(everyone, key=lambda e: hashlib.sha256((llm.DRAW_SALT + e).encode()).hexdigest())
        self.assertEqual([row["episode_id"] for row in plan["draw"]["episodes"]], order[:15])
        self.assertEqual(plan["draw"]["order"], order)
        train_ok = [e for e in llm.draw_order([f"procthor10k-0.1.2-train-{5000 + i:05d}" for i in range(5)])
                    if 180 + (int(e[-5:]) - 5000) * 10 >= 200]
        self.assertEqual(plan["pilot"]["episode_id"], train_ok[0])
        self.assertEqual(plan["planned_frames"]["instance"], sum(300 + int(e[-5:]) * 10 for e in order[:15]))
        self.assertAlmostEqual(plan["rows_per_frame"]["sam2"]["existence_rows"], 36.0)
        self.assertAlmostEqual(plan["rows_per_frame"]["sam2"]["association_rows"], 9 * 9.8)
        lines = set((run_root / "transfer.txt").read_text(encoding="utf-8").split())
        for episode in order[:15]:
            self.assertIn(str(self.tmp / "raw" / "validation" / episode), lines)
            self.assertIn(str(self.tmp / "cache-sam2" / "validation" / episode), lines)
        pilot = plan["pilot"]["episode_id"]
        self.assertIn(str(self.tmp / "raw" / "train" / pilot / "public"), lines)
        self.assertNotIn(str(self.tmp / "raw" / "train" / pilot), lines)  # never the pilot's private plane
        self.assertIn(str(run_root / "plan.json"), lines)

    def test_workers_exit_codes_and_the_call_totals(self) -> None:
        chosen = driver.choose_workers({"cpu_quota": 16, "memory_bytes": 64 * 2 ** 30}, 30, None)
        self.assertEqual((chosen["by_memory"], chosen["by_cores"], chosen["actual"]), (37, 14, 14))
        self.assertEqual(driver.choose_workers({"cpu_quota": 64, "memory_bytes": 256 * 2 ** 30}, 30, 8)["actual"], 8)
        self.assertEqual([driver.classify(c) for c in (0, 75, 76, 77, 78, 79, 2, 1)],
                         ["done", "stopped", "model_changed", "api_fatal", "interrupted", "archive_problem", "refused", "failed"])
        stats = {"calls": 100, "attempts": 103, "fallbacks": 3, "skipped_without_rows": 0, "rows": 900, "invalid": {"empty": 3},
                 "tokens": {"input_cache_hit": 1, "input_cache_miss": 2, "output": 3, "reasoning": 1}, "cost_usd": 0.5}
        totals = driver.call_totals([{"association": stats, "existence": {**stats, "fallbacks": 1}}])
        self.assertEqual(totals["association"]["fallback_rate"], 0.03)
        self.assertTrue(totals["format_unreliable"])

class DriverRunLoopTests(TempDir):
    """The run loop with stand-in processes: every episode dispatched under the cap, none after it, STOP at the safety stop."""

    def setUp(self) -> None:
        super().setUp()
        self.run_root = self.tmp / "run"
        episodes = [{"episode_id": f"ep-{i}", "frames": 100 + i} for i in range(3)]
        roots = {"raw": {"validation": str(self.tmp / "raw")}, "geometry": {"validation": str(self.tmp / "geometry")},
                 "cache": {front: {"validation": str(self.tmp / front)} for front in llm.FRONTS}}
        driver.write_json(self.run_root / "plan.json", {"draw": {"episodes": episodes}, "roots": roots,
                                                        "reid": {front: {"file": "h"} for front in llm.FRONTS}, "pilot": {"episode_id": "p"}})
        driver.write_json(self.run_root / "pilot" / "report.json", {"within_cap": True, "projected_usd_expected_total": 50.0})
        driver.write_json(self.run_root / llm.MODEL_FILE, {"model": SERVED})
        self.started: list[list[str]] = []
        self.spend_per_job = 0.0

    def fake_popen(self, command: list[str], **kwargs: Any) -> Any:
        test = self
        test.started.append(command)
        episode = command[command.index("--episode-id") + 1]
        front = next(f for f, source in llm.FRONTS.items() if source == command[command.index("--mask-source") + 1])

        class Process:
            pid = 1000 + len(test.started)

            def poll(self) -> int:
                driver.write_json(driver.audit_path(test.run_root, front, episode),
                                  {"episode_id": episode, "arm": llm.ARM, "report": {}, "llm_op": {}, "metrics_only": True})
                ledger = driver.archive_path(test.run_root, front, episode).with_name(f"{episode}.jsonl.ledger.json")
                driver.write_json(ledger, {"cost_usd": test.spend_per_job, "last_tick": 1})
                return 0

        return Process()

    def run_loop(self, workers: int = 2) -> int:
        args = argparse.Namespace(run_root=str(self.run_root), workers=workers, accept_projection=False, resume_after_stop=False,
                                  retry_failed=False)
        with mock.patch.object(driver, "require_check", lambda root: {"checked_utc": "t"}), \
                mock.patch.object(driver, "resources", lambda: {"cpu_quota": 16, "memory_bytes": 64 * 2 ** 30}), \
                mock.patch.object(driver, "git", lambda *a: "c0ffee"), mock.patch.object(driver, "memory_ok", lambda info: True), \
                mock.patch.object(llm, "load_contract", opened_contract), mock.patch.object(driver.time, "sleep", lambda s: None), \
                mock.patch.object(driver.subprocess, "Popen", self.fake_popen):
            return driver.run(args)

    def test_every_episode_runs_once_under_the_cap(self) -> None:
        self.assertEqual(self.run_loop(), 0)
        self.assertEqual(len(self.started), 6)
        command = self.started[0]
        self.assertEqual(command[command.index("--llm-op-mode") + 1], "live")
        self.assertIn("--metrics-only", command)
        self.assertEqual(command[command.index("--manifest-split") + 1], "validation")
        self.assertEqual(self.run_loop(), 0)  # rerun: everything done, nothing started again
        self.assertEqual(len(self.started), 6)

    def test_no_new_episode_once_the_ledger_reaches_the_cap(self) -> None:
        self.spend_per_job = 80.0  # the first two finished episodes bring the ledger to $160, over the $150 cap
        self.assertEqual(self.run_loop(workers=2), driver.EXIT_DECISION)
        self.assertEqual(len(self.started), 2)
        self.assertFalse((self.run_root / llm.STOP_FILE).exists())
        self.assertEqual(self.run_loop(workers=2), driver.EXIT_DECISION)  # a rerun starts nothing either
        self.assertEqual(len(self.started), 2)

    def test_the_safety_stop_writes_stop_and_a_rerun_waits_for_the_user(self) -> None:
        self.spend_per_job = 120.0  # $240, over the $200 safety stop
        self.assertEqual(self.run_loop(workers=2), driver.EXIT_DECISION)
        self.assertIn("safety_stop_usd", (self.run_root / llm.STOP_FILE).read_text(encoding="utf-8"))
        self.assertEqual(self.run_loop(workers=2), driver.EXIT_DECISION)  # refused while STOP stands
        self.assertEqual(len(self.started), 2)


if __name__ == "__main__":
    unittest.main()
