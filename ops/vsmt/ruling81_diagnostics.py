#!/usr/bin/env python3
"""Ruling 81 diagnostics on the server: controlled training (81-2) and node audits v5 (81-3), one shared queue.

白话：裁决 81 批准的开机任务用固定命令跑。输入是开发趟根目录（lean-s2-05-oracle-c150be0）里第 0 轮与第 1 轮的训练记录、
S1-03 oracle cache、S1-02 episode、S1-04 几何表和 ReID 权重；输出全部写进新的诊断根与 exports/，任何已登记趟都不写。
八次训练（VSMT-lean 与 AssocOnly × A7、A19、B、C）先开跑，每组训练一完成，它的 39 条节点审计 v5 就进同一个队列，
大 episode 先派发；空出来的 CPU 立刻接下一个任务。它不产生表格用的权重，也不读 validation/test。

Steps (each stops; the next is started by hand after reading the previous output):
  check                 commit, clean checkout, inputs (both record sources for both arms), CPUs, memory, disk, leftover timers
  timing                a 300-update timing run of condition B for both arms side by side: projected hours for every condition
  run --workers N       the eight trainings and the 8 x 39 audits on one dependency-aware queue, resuming by skipping finished work
  merge                 pooled audits per group, training receipts and the ruling-81 analysis -> exports/, one summary
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))

import ruling79_diagnostics as r79  # noqa: E402  (same paths, helpers and runtime estimates)

ARMS = {"VSMT-lean": '{"tau_r": 0.5}', "AssocOnly": "{}"}
CONDITIONS = ("A7", "A19", "B", "C")
TIMING_UPDATES = 300


def diag_root() -> Path:
    return r79.AUTODL / f"vsmt_private/ruling81-{r79.short_commit()}"


def group(arm: str, condition: str) -> str:
    return f"{arm}-{condition}"


def training_dir(arm: str, condition: str) -> Path:
    return diag_root() / "training" / arm / condition


def training_done(arm: str, condition: str) -> bool:
    return (training_dir(arm, condition) / "training_receipt.json").exists() and (training_dir(arm, condition) / "weights.json").exists()


def audit_path(arm: str, condition: str, episode_id: str) -> Path:
    return diag_root() / "audit" / group(arm, condition) / episode_id / arm / "node_audit.json"


def training_command(arm: str, condition: str, out_dir: Path, *extra: str) -> list[str]:
    return [r79.PY, str(r79.ROOT / "ops/vsmt/lean_s2_05_controlled_training.py"), "--output-root", str(r79.PASS_ROOT), "--arm", arm,
            "--condition", condition, "--out-dir", str(out_dir), *extra]


def audit_command(arm: str, condition: str, episode_id: str) -> list[str]:
    return [r79.PY, str(r79.ROOT / "ops/vsmt/lean_s2_05_node_audit.py"), "run", "--cache-root", str(r79.CACHE_ROOT),
            "--episode-root", str(r79.episode_root(episode_id)), "--geometry-root", str(r79.GEOMETRY_ROOT), "--episode-id", episode_id,
            "--arm", arm, "--config", ARMS[arm], "--heads", str(training_dir(arm, condition) / "weights.json"),
            "--descriptor", r79.DESCRIPTOR, "--weights", str(r79.REID_WEIGHTS),
            "--output-root", str(diag_root() / "audit" / group(arm, condition)), "--device", "cpu"]


def cmd_check(args: argparse.Namespace) -> int:
    code = r79.cmd_check(args)
    problems = []
    for pass_name, arm in (("dagger_round_0", "ELU-P"), ("dagger_round_1", "VSMT-lean"), ("dagger_round_1", "AssocOnly")):
        files = sorted((r79.PASS_ROOT / pass_name).glob(f"procthor*/{arm}/training_records.jsonl.gz"))
        if len(files) != 39:
            problems.append(f"{pass_name}/{arm}: {len(files)} training record files, expected 39")
    print(json.dumps({"ruling81_diag_root": str(diag_root()), "record_problems": problems}, indent=1))
    return 1 if (code or problems) else 0


def cmd_timing(args: argparse.Namespace) -> int:
    procs = []
    for arm in ARMS:
        out = diag_root() / "timing" / arm
        log = diag_root() / "logs" / f"timing-{arm}.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        procs.append((arm, out, subprocess.Popen(training_command(arm, "B", out, "--timing-updates", str(TIMING_UPDATES)), cwd=r79.ROOT,
                                                 stdout=log.open("w"), stderr=subprocess.STDOUT, env={**os.environ, **r79.THREAD_ENV})))
    report: dict[str, Any] = {}
    for arm, out, proc in procs:
        code = proc.wait()
        receipt_path = out / "training_receipt.json"
        if code != 0 or not receipt_path.exists():
            report[arm] = {"failed": code}
            continue
        receipt = json.loads(receipt_path.read_text())
        report[arm] = {"projected_hours": {c: round(s / 3600, 2) for c, s in receipt["projected_seconds"].items()},
                       "seconds_per_update": receipt["seconds_per_update"], "validation_seconds": receipt["validation_seconds"],
                       "prepare_seconds": receipt["prepare_seconds"], "U": receipt["plan"]["U"], "V": receipt["plan"]["V"],
                       "K": receipt["plan"]["evaluate_every"]}
    audit_seconds = {arm: round(sum(r79.expected_seconds(arm, e) for e in r79.episodes()) * 1.25) for arm in ARMS}
    report["audit_cpu_hours_all_groups"] = round(sum(4 * s for s in audit_seconds.values()) / 3600, 1)
    report["note"] = "audit CPU hours = 4 conditions x the development-table runtime of each arm x 1.25 (the v4 audit overhead)"
    print(json.dumps(report, indent=1))
    return 0 if all("failed" not in v for k, v in report.items() if k in ARMS) else 3


def cmd_run(args: argparse.Namespace) -> int:
    root = diag_root()
    episodes = r79.episodes()
    trainings = [(arm, c) for arm in ARMS for c in CONDITIONS if not training_done(arm, c)]
    audits = sorted(((arm, c, e) for arm in ARMS for c in CONDITIONS for e in episodes if not audit_path(arm, c, e).exists()),
                    key=lambda t: (-r79.expected_seconds(t[0], t[2]), t))
    failed_groups: set[str] = set()
    results: list[dict[str, Any]] = []
    running: dict[subprocess.Popen, dict[str, Any]] = {}
    print(f"[ruling81] {time.strftime('%F %T')} run at {r79.short_commit()}: {len(trainings)} trainings and {len(audits)} audits on "
          f"{args.workers} workers (cgroup {r79.cpu_quota()} CPUs)", flush=True)

    def launch(task: dict[str, Any], command: list[str], log: Path) -> None:
        log.parent.mkdir(parents=True, exist_ok=True)
        task["started"] = time.time()
        proc = subprocess.Popen(command, cwd=r79.ROOT, stdout=log.open("w"), stderr=subprocess.STDOUT, env={**os.environ, **r79.THREAD_ENV})
        running[proc] = task

    while trainings or audits or running:
        while len(running) < args.workers:
            if trainings:
                arm, condition = trainings.pop(0)
                launch({"kind": "training", "arm": arm, "condition": condition}, training_command(arm, condition, training_dir(arm, condition)),
                       root / "logs" / "training" / f"{group(arm, condition)}.log")
                continue
            ready = next((t for t in audits if training_done(t[0], t[1])), None)
            if ready is None:
                break
            audits.remove(ready)
            arm, condition, episode_id = ready
            launch({"kind": "audit", "arm": arm, "condition": condition, "episode": episode_id}, audit_command(arm, condition, episode_id),
                   root / "logs" / "audit" / group(arm, condition) / f"{episode_id}.log")
        # audits whose training failed can never start
        for t in [t for t in audits if group(t[0], t[1]) in failed_groups]:
            audits.remove(t)
            results.append({"kind": "audit", "arm": t[0], "condition": t[1], "episode": t[2], "exit": None, "skipped": "training_failed"})
        if not running:
            if audits:  # nothing runs and nothing can start: the remaining audits wait on trainings that never finished
                for t in audits:
                    results.append({"kind": "audit", "arm": t[0], "condition": t[1], "episode": t[2], "exit": None, "skipped": "no_weights"})
                audits.clear()
            break
        time.sleep(5)
        for proc in [p for p in running if p.poll() is not None]:
            task = running.pop(proc)
            task.update({"exit": proc.returncode, "seconds": round(time.time() - task.pop("started"), 1)})
            results.append(task)
            if task["kind"] == "training" and (proc.returncode != 0 or not training_done(task["arm"], task["condition"])):
                failed_groups.add(group(task["arm"], task["condition"]))
            label = task.get("episode") or "training"
            print(f"[ruling81] {time.strftime('%F %T')} {task['kind']} {group(task['arm'], task['condition'])} {label} exit {task['exit']} "
                  f"{task['seconds']} s; {len(trainings)} trainings and {len(audits)} audits left, {len(running)} running", flush=True)

    status = {"commit": r79.git("rev-parse", "HEAD"), "diag_root": str(root), "workers": args.workers, "cgroup_cpus": r79.cpu_quota(),
              "worker_basis": f"{args.workers} single-thread slots on one dependency-aware queue: trainings first, then each group's audits "
                              "as soon as its weights exist, largest episodes first",
              "results": results, "failed": [r for r in results if r.get("exit") not in (0,)], "finished_cst": time.strftime("%F %T")}
    r79.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    (r79.EXPORT_DIR / f"ruling81_diagnostics_{r79.short_commit()}.status.json").write_text(json.dumps(status, indent=1))
    print(f"[ruling81] {len(status['failed'])} failed or skipped tasks; status written", flush=True)
    return 0 if not status["failed"] else 1


def cmd_merge(args: argparse.Namespace) -> int:
    commit = r79.short_commit()
    summary: dict[str, Any] = {"commit": r79.git("rev-parse", "HEAD"), "diag_root": str(diag_root()), "groups": {}, "trainings": {}}
    code = 0
    for arm in ARMS:
        for condition in CONDITIONS:
            name = group(arm, condition)
            results = r79.EXPORT_DIR / f"vsmt_lean_s2_05_node_audit_ruling81_{name}_{commit}.json"
            merged = subprocess.run([r79.PY, str(r79.ROOT / "ops/vsmt/lean_s2_05_node_audit.py"), "merge", "--output-root",
                                     str(diag_root() / "audit" / name), "--arm", arm, "--results", str(results)],
                                    cwd=r79.ROOT, capture_output=True, text=True)
            missing = [e for e in r79.episodes() if not audit_path(arm, condition, e).exists()]
            summary["groups"][name] = {"merge_exit": merged.returncode, "merge_stderr_tail": merged.stderr[-2000:], "results": str(results),
                                       "audits_missing": missing}
            code |= int(merged.returncode != 0 or bool(missing))
            receipt = training_dir(arm, condition) / "training_receipt.json"
            if receipt.exists():
                target = r79.EXPORT_DIR / f"vsmt_lean_s2_05_controlled_training_{name}_{commit}.json"
                shutil.copyfile(receipt, target)
                content = json.loads(receipt.read_text())
                summary["trainings"][name] = {"results": str(target), "best_update": content["best_update"], "updates_taken": content["updates_taken"],
                                              "diverged": content["diverged"], "weights_sha256": content["weights_sha256"]}
            else:
                summary["trainings"][name] = None
                code |= 1
    analysis_out = r79.EXPORT_DIR / f"vsmt_lean_s2_05_ruling81_analysis_{commit}.json"
    analysed = subprocess.run([r79.PY, str(r79.ROOT / "ops/vsmt/ruling81_analysis.py"), "--results-dir", str(r79.EXPORT_DIR), "--commit", commit,
                               "--output", str(analysis_out)], cwd=r79.ROOT, capture_output=True, text=True)
    summary["analysis"] = {"exit": analysed.returncode, "results": str(analysis_out), "stdout_tail": analysed.stdout[-3000:],
                           "stderr_tail": analysed.stderr[-2000:]}
    code |= int(analysed.returncode != 0)
    (r79.EXPORT_DIR / f"vsmt_lean_s2_05_ruling81_summary_{commit}.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({"groups": {g: {k: v for k, v in row.items() if k != "merge_stderr_tail"} for g, row in summary["groups"].items()},
                      "trainings": summary["trainings"], "analysis_exit": analysed.returncode}, indent=1))
    print(analysed.stdout[-3000:])
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="step", required=True)
    sub.add_parser("check").set_defaults(func=cmd_check)
    sub.add_parser("timing").set_defaults(func=cmd_timing)
    run = sub.add_parser("run")
    run.add_argument("--workers", type=int, required=True)
    run.set_defaults(func=cmd_run)
    sub.add_parser("merge").set_defaults(func=cmd_merge)
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
