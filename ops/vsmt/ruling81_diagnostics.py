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

--stage ruling82 (ruling 82-1, 2026-09-29) runs the same steps for the seed-spread study: conditions A31, A43, A59 (the other
three registered seeds under the registered recipe) for both arms, and merge reads them together with seeds 7 and 19 of the
ruling-81 run (exports of commit 0e4494d) through ruling82_seed_analysis.py.
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
#: memory admission (2026-09-28: 8 trainings of about 10.5 GiB each on a 62 GiB container, two killed at start);
#: since 2026-09-29 own-data conditions only count the round-0 records, so they are charged less than aggregated ones
TRAINING_MEMORY_GIB = 11.0
OWN_DATA_TRAINING_MEMORY_GIB = 7.0
AUDIT_MEMORY_GIB = 1.5
MEMORY_RESERVE_GIB = 4.0
CONDITIONS = ("A7", "A19", "B", "C")
#: ruling 82-1: the seed-spread study (the other three registered seeds; seeds 7 and 19 come from the ruling-81 run)
SEED_STUDY_CONDITIONS = ("A31", "A43", "A59")
RULING81_COMMIT = "0e4494d"
STAGES = {"ruling81": CONDITIONS, "ruling82": SEED_STUDY_CONDITIONS}
STAGE = {"name": "ruling81", "conditions": CONDITIONS}  # set by --stage before any path is built
TIMING_UPDATES = 300


def diag_root() -> Path:
    return r79.AUTODL / f"vsmt_private/{STAGE['name']}-{r79.short_commit()}"


def training_memory_gib(condition: str) -> float:
    return TRAINING_MEMORY_GIB if condition == "B" else OWN_DATA_TRAINING_MEMORY_GIB


def group(arm: str, condition: str) -> str:
    return f"{arm}-{condition}"


def training_dir(arm: str, condition: str) -> Path:
    return diag_root() / "training" / arm / condition


def training_done(arm: str, condition: str) -> bool:
    return (training_dir(arm, condition) / "training_receipt.json").exists() and (training_dir(arm, condition) / "weights.json").exists()


def training_usable(arm: str, condition: str) -> bool:
    """Weights exist and the receipt says the training did not diverge (a diverged run also writes both files)."""

    if not training_done(arm, condition):
        return False
    return json.loads((training_dir(arm, condition) / "training_receipt.json").read_text()).get("diverged") is not True


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


def memory_budget_gib() -> float | None:
    """The container memory the queue may plan with (limit minus a reserve); None when unlimited."""

    limit = r79.cgroup_memory_gib().get("max")
    return None if limit is None else limit - MEMORY_RESERVE_GIB


def fits(budget: float | None, running: list[float], cost: float) -> bool:
    """Would one more task of memory ``cost`` (GiB) stay within the budget, given the costs already running?"""

    if budget is None:
        return True
    return sum(running) + cost <= budget or not running


def cmd_check(args: argparse.Namespace) -> int:
    code = r79.cmd_check(args)
    problems = []
    for pass_name, arm in (("dagger_round_0", "ELU-P"), ("dagger_round_1", "VSMT-lean"), ("dagger_round_1", "AssocOnly")):
        files = sorted((r79.PASS_ROOT / pass_name).glob(f"procthor*/{arm}/training_records.jsonl.gz"))
        if len(files) != 39:
            problems.append(f"{pass_name}/{arm}: {len(files)} training record files, expected 39")
    budget = memory_budget_gib()
    costs = [training_memory_gib(c) for c in STAGE["conditions"]]
    concurrent = None if budget is None else int(budget // max(costs))
    print(json.dumps({"stage": STAGE["name"], "conditions": list(STAGE["conditions"]), "stage_diag_root": str(diag_root()),
                      "record_problems": problems, "memory_budget_gib": budget,
                      "trainings_that_fit_at_once": concurrent}, indent=1))
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
    # a group's audits may start only once its training is usable: finished before this run, or exit 0 in this run
    conditions = STAGE["conditions"]
    ready_groups = {group(arm, c) for arm in ARMS for c in conditions if training_usable(arm, c)}
    trainings = [(arm, c) for arm in ARMS for c in conditions if group(arm, c) not in ready_groups]
    audits = sorted(((arm, c, e) for arm in ARMS for c in conditions for e in episodes if not audit_path(arm, c, e).exists()),
                    key=lambda t: (-r79.expected_seconds(t[0], t[2]), t))
    failed_groups: set[str] = set()
    results: list[dict[str, Any]] = []
    running: dict[subprocess.Popen, dict[str, Any]] = {}
    print(f"[{STAGE['name']}] {time.strftime('%F %T')} run at {r79.short_commit()}: {len(trainings)} trainings and {len(audits)} audits on "
          f"{args.workers} workers (cgroup {r79.cpu_quota()} CPUs)", flush=True)

    budget = memory_budget_gib()

    def launch(task: dict[str, Any], command: list[str], log: Path) -> None:
        log.parent.mkdir(parents=True, exist_ok=True)
        task["started"] = time.time()
        task["started_at"] = time.strftime("%F %T")
        proc = subprocess.Popen(command, cwd=r79.ROOT, stdout=log.open("w"), stderr=subprocess.STDOUT, env={**os.environ, **r79.THREAD_ENV})
        running[proc] = task

    while trainings or audits or running:
        while len(running) < args.workers:
            costs = [t["memory_gib"] for t in running.values()]
            if trainings and fits(budget, costs, training_memory_gib(trainings[0][1])):
                arm, condition = trainings.pop(0)
                launch({"kind": "training", "arm": arm, "condition": condition, "memory_gib": training_memory_gib(condition)},
                       training_command(arm, condition, training_dir(arm, condition)), root / "logs" / "training" / f"{group(arm, condition)}.log")
                continue
            ready = next((t for t in audits if group(t[0], t[1]) in ready_groups), None)
            if ready is None or not fits(budget, costs, AUDIT_MEMORY_GIB):
                break
            audits.remove(ready)
            arm, condition, episode_id = ready
            launch({"kind": "audit", "arm": arm, "condition": condition, "episode": episode_id, "memory_gib": AUDIT_MEMORY_GIB},
                   audit_command(arm, condition, episode_id), root / "logs" / "audit" / group(arm, condition) / f"{episode_id}.log")
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
            task.update({"exit": proc.returncode, "seconds": round(time.time() - task.pop("started"), 1), "ended_at": time.strftime("%F %T")})
            results.append(task)
            if task["kind"] == "training":
                if proc.returncode == 0 and training_usable(task["arm"], task["condition"]):
                    ready_groups.add(group(task["arm"], task["condition"]))
                else:
                    failed_groups.add(group(task["arm"], task["condition"]))
            label = task.get("episode") or "training"
            print(f"[{STAGE['name']}] {time.strftime('%F %T')} {task['kind']} {group(task['arm'], task['condition'])} {label} exit {task['exit']} "
                  f"{task['seconds']} s; {len(trainings)} trainings and {len(audits)} audits left, {len(running)} running", flush=True)

    status = {"commit": r79.git("rev-parse", "HEAD"), "diag_root": str(root), "workers": args.workers, "cgroup_cpus": r79.cpu_quota(),
              "worker_basis": f"{args.workers} single-thread slots on one dependency-aware queue: trainings first, then each group's audits "
                              "as soon as its weights exist, largest episodes first; admitted within the container memory "
                              f"(budget {budget} GiB, {TRAINING_MEMORY_GIB} GiB per aggregated training, {OWN_DATA_TRAINING_MEMORY_GIB} GiB "
                              f"per own-data training, {AUDIT_MEMORY_GIB} GiB per audit)",
              "results": results, "failed": [r for r in results if r.get("exit") not in (0,)], "finished_cst": time.strftime("%F %T")}
    r79.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    (r79.EXPORT_DIR / f"{STAGE['name']}_diagnostics_{r79.short_commit()}.status.json").write_text(json.dumps(status, indent=1))
    print(f"[{STAGE['name']}] {len(status['failed'])} failed or skipped tasks; status written", flush=True)
    return 0 if not status["failed"] else 1


def cmd_merge(args: argparse.Namespace) -> int:
    commit = r79.short_commit()
    summary: dict[str, Any] = {"commit": r79.git("rev-parse", "HEAD"), "diag_root": str(diag_root()), "groups": {}, "trainings": {}}
    code = 0
    for arm in ARMS:
        for condition in STAGE["conditions"]:
            name = group(arm, condition)
            results = r79.EXPORT_DIR / f"vsmt_lean_s2_05_node_audit_{STAGE['name']}_{name}_{commit}.json"
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
    if STAGE["name"] == "ruling81":
        analysis_out = r79.EXPORT_DIR / f"vsmt_lean_s2_05_ruling81_analysis_{commit}.json"
        command = [r79.PY, str(r79.ROOT / "ops/vsmt/ruling81_analysis.py"), "--results-dir", str(r79.EXPORT_DIR), "--commit", commit,
                   "--output", str(analysis_out)]
    else:  # ruling 82-1: seeds 7 and 19 from the ruling-81 run, 31/43/59 from this one
        analysis_out = r79.EXPORT_DIR / f"vsmt_lean_s2_05_ruling82_seed_analysis_{commit}.json"
        command = [r79.PY, str(r79.ROOT / "ops/vsmt/ruling82_seed_analysis.py"), "--output", str(analysis_out)]
        for arm in ARMS:
            for condition, source in (("A7", f"ruling81_{arm}-A7_{RULING81_COMMIT}"), ("A19", f"ruling81_{arm}-A19_{RULING81_COMMIT}"),
                                      *((c, f"ruling82_{arm}-{c}_{commit}") for c in SEED_STUDY_CONDITIONS)):
                command += ["--group", f"{arm}:{condition[1:]}:{r79.EXPORT_DIR / f'vsmt_lean_s2_05_node_audit_{source}.json'}"]
    analysed = subprocess.run(command, cwd=r79.ROOT, capture_output=True, text=True)
    summary["analysis"] = {"exit": analysed.returncode, "results": str(analysis_out), "stdout_tail": analysed.stdout[-3000:],
                           "stderr_tail": analysed.stderr[-2000:]}
    code |= int(analysed.returncode != 0)
    (r79.EXPORT_DIR / f"vsmt_lean_s2_05_{STAGE['name']}_summary_{commit}.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({"groups": {g: {k: v for k, v in row.items() if k != "merge_stderr_tail"} for g, row in summary["groups"].items()},
                      "trainings": summary["trainings"], "analysis_exit": analysed.returncode}, indent=1))
    print(analysed.stdout[-3000:])
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stage", choices=sorted(STAGES), default="ruling81")
    sub = parser.add_subparsers(dest="step", required=True)
    sub.add_parser("check").set_defaults(func=cmd_check)
    sub.add_parser("timing").set_defaults(func=cmd_timing)
    run = sub.add_parser("run")
    run.add_argument("--workers", type=int, required=True)
    run.set_defaults(func=cmd_run)
    sub.add_parser("merge").set_defaults(func=cmd_merge)
    args = parser.parse_args()
    STAGE.update({"name": args.stage, "conditions": STAGES[args.stage]})
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
