#!/usr/bin/env python3
"""Ruling 79 diagnostics on the server: one boot, fixed commands, read-only with respect to every registered pass.

白话：裁决 79 批准的开机诊断包（79-2 只读导出 v2、79-3 (i) 学习臂节点审计 v3、79-3 (ii) 第 1 轮 VSMT-lean 分项
曲线重放）按固定命令跑，不再为每一步改脚本。输入是已登记的开发趟产物（lean-s2-05-oracle-c150be0）、校准根、S1-02
episode、S1-03 oracle cache、S1-04 几何表和 ReID 权重；输出全部写进新的诊断根和 exports/，任何已登记趟的根目录都
不写。它不是新方法、不产生表格用的权重，也不读 validation/test（39 条开发 house 全在 train 块）。

Steps (each one stops; the next is started by hand after reading the previous one's output):
  check                      commit, clean checkout, inputs, cgroup CPUs, memory, disk, leftover shutdown timers
  export  --workers N        79-2: attribution export v2 -> exports/vsmt_lean_s2_05_attribution_export_<commit>.json
  trial                      one node audit (01289, VSMT-lean) into the audit root, timed; reused by run
  run     --workers N        79-3: node audits of VSMT-lean, NoVersion, AssocOnly x 39 on one shared queue (largest
                             episodes first) plus the per-term replay on one more CPU; resumes by skipping finished audits
  merge                      pooled audits per arm, determinism check against the development-table receipts, term
                             curves -> exports/, one summary file
Usage:
  /root/miniconda3/bin/python3.12 ops/vsmt/ruling79_diagnostics.py <step> [--workers N] [--shutdown-grace S]
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
PY = sys.executable
AUTODL = Path("/root/autodl-tmp")
PASS_ROOT = AUTODL / "vsmt_private/lean-s2-05-oracle-c150be0"
CALIBRATION_ROOT = AUTODL / "vsmt_private/lean-s2-05-oracle-850c533"
CACHE_ROOT = AUTODL / "vsmt_caches/lean-s1-03-oracle-8ebbd05"
EPISODE_ROOTS = (AUTODL / "vsmt_outputs/lean-s1-02a-5f9aa71", AUTODL / "vsmt_outputs/lean-s1-02b-5f9aa71")
GEOMETRY_ROOT = AUTODL / "vsmt_private/lean-s1-04-geometry-154776d"
REID_WEIGHTS = AUTODL / "vsmt_private/lean-s1-04-diagnostics-oracle-caa50c7/reid_head_vitb14.json"
EXPORT_DIR = AUTODL / "vsmt_outputs/exports"
DESCRIPTOR = "reid_projection:vitb14"
TRIAL_EPISODE = "procthor10k-0.1.2-train-01289"
#: the development-table configurations and round-1 heads of the three learned arms (LOG-270)
ARMS = {
    "VSMT-lean": ('{"tau_r": 0.5}', PASS_ROOT / "training/round1/VSMT-lean/weights.json"),
    "NoVersion": ('{"tau_r": 0.5}', PASS_ROOT / "training/round1/VSMT-lean/weights.json"),
    "AssocOnly": ("{}", PASS_ROOT / "training/round1/AssocOnly/weights.json"),
}
THREAD_ENV = {"OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}


def git(*arguments: str) -> str:
    return subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def short_commit() -> str:
    return git("rev-parse", "--short=7", "HEAD")


def diag_root() -> Path:
    return AUTODL / f"vsmt_private/ruling79-{short_commit()}"


def cpu_quota() -> int:
    try:
        quota, period = Path("/sys/fs/cgroup/cpu.max").read_text().split()
        return (os.cpu_count() or 1) if quota == "max" else max(1, int(int(quota) / int(period)))
    except (OSError, ValueError):
        return os.cpu_count() or 1


def episode_root(episode_id: str) -> Path:
    found = [root / episode_id for root in EPISODE_ROOTS if (root / episode_id / "receipt.json").exists()]
    if len(found) != 1:
        raise SystemExit(f"[ruling79] episode root for {episode_id}: {len(found)} found")
    return found[0]


def devtable_receipt(arm: str, episode_id: str) -> dict[str, Any]:
    return json.loads((PASS_ROOT / "development_table" / episode_id / arm / "receipt.json").read_text())


def episodes() -> list[str]:
    return sorted(p.name for p in (PASS_ROOT / "development_table").iterdir() if p.is_dir() and p.name.startswith("procthor"))


def expected_seconds(arm: str, episode_id: str) -> float:
    """Queue order: the development-table run of the same arm (frames x runtime per frame); largest first."""

    report = devtable_receipt(arm, episode_id).get("report") or {}
    per_frame = float((report.get("size_and_cost") or {}).get("runtime_per_frame_s") or 1.0)
    frames = int((report.get("contamination_auc") or {}).get("frames") or 1)
    return per_frame * frames


def audit_command(arm: str, episode_id: str, output_root: Path) -> list[str]:
    config, heads = ARMS[arm]
    return [PY, str(ROOT / "ops/vsmt/lean_s2_05_node_audit.py"), "run", "--cache-root", str(CACHE_ROOT),
            "--episode-root", str(episode_root(episode_id)), "--geometry-root", str(GEOMETRY_ROOT), "--episode-id", episode_id,
            "--arm", arm, "--config", config, "--heads", str(heads), "--descriptor", DESCRIPTOR, "--weights", str(REID_WEIGHTS),
            "--output-root", str(output_root), "--device", "cpu"]


def run_logged(command: list[str], log: Path) -> tuple[int, float]:
    log.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    with log.open("w") as handle:
        code = subprocess.run(command, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT, env={**os.environ, **THREAD_ENV}).returncode
    return code, round(time.time() - started, 1)


def audit_task(arm: str, episode_id: str) -> dict[str, Any]:
    root = diag_root() / "audit"
    if (root / episode_id / arm / "node_audit.json").exists():
        return {"arm": arm, "episode": episode_id, "exit": 0, "seconds": None, "reused": True}
    code, seconds = run_logged(audit_command(arm, episode_id, root), diag_root() / "logs" / arm / f"{episode_id}.log")
    return {"arm": arm, "episode": episode_id, "exit": code, "seconds": seconds, "reused": False}


# --------------------------------------------------------------------------
# steps
# --------------------------------------------------------------------------

def cmd_check(args: argparse.Namespace) -> int:
    problems = []
    dirty = git("status", "--porcelain")
    if dirty:
        problems.append("checkout not clean")
    inputs = [PASS_ROOT / "development_table", CALIBRATION_ROOT / "calibration", CACHE_ROOT, GEOMETRY_ROOT, REID_WEIGHTS,
              *EPISODE_ROOTS, *(heads for _, heads in ARMS.values()), PASS_ROOT / "training/round1/VSMT-lean/training_receipt.json"]
    for path in inputs:
        if not path.exists():
            problems.append(f"missing {path}")
    found = episodes() if (PASS_ROOT / "development_table").exists() else []
    if len(found) != 39:
        problems.append(f"{len(found)} development-table episodes, expected 39")
    usage = shutil.disk_usage(AUTODL)
    timers = subprocess.run(["bash", "-c", "ps -eo pid,etime,args | grep -E 'sleep|shutdown' | grep -v grep"], capture_output=True, text=True).stdout
    memory = subprocess.run(["bash", "-c", "free -g | sed -n 2p"], capture_output=True, text=True).stdout.strip()
    print(json.dumps({"commit": git("rev-parse", "HEAD"), "diag_root": str(diag_root()), "cgroup_cpus": cpu_quota(),
                      "memory_free_g_line": memory, "data_disk_free_gb": round(usage.free / 2**30, 1),
                      "leftover_sleep_or_shutdown": timers.strip().splitlines(), "episodes": len(found), "problems": problems}, indent=1))
    return 1 if problems else 0


def cmd_export(args: argparse.Namespace) -> int:
    output = EXPORT_DIR / f"vsmt_lean_s2_05_attribution_export_{short_commit()}.json"
    if output.exists():
        print(f"[ruling79] export exists: {output}")
        return 0
    command = [PY, str(ROOT / "ops/vsmt/lean_s2_05_attribution_export.py"), "--pass-root", str(PASS_ROOT),
               "--calibration-root", str(CALIBRATION_ROOT), "--episode-roots", ",".join(str(r) for r in EPISODE_ROOTS),
               "--output", str(output), "--workers", str(args.workers)]
    code, seconds = run_logged(command, diag_root() / "logs" / "attribution_export.log")
    print(f"[ruling79] attribution export exit {code}, {seconds} s -> {output}")
    return code


def cmd_trial(args: argparse.Namespace) -> int:
    result = audit_task("VSMT-lean", TRIAL_EPISODE)
    path = diag_root() / "audit" / TRIAL_EPISODE / "VSMT-lean" / "node_audit.json"
    if result["exit"] != 0 or not path.exists():
        print(f"[ruling79] trial failed: {result}; log {diag_root() / 'logs/VSMT-lean' / (TRIAL_EPISODE + '.log')}")
        return 1
    payload = json.loads(path.read_text())
    registered = devtable_receipt("VSMT-lean", TRIAL_EPISODE)
    same = strip_runtime(payload["report"]) == strip_runtime(registered["report"])
    frames = int(payload["frames"])
    estimate = {arm: round(sum(expected_seconds(arm, e) for e in episodes())) for arm in ARMS}
    ratio = (payload["wall_seconds"] / expected_seconds("VSMT-lean", TRIAL_EPISODE)) if expected_seconds("VSMT-lean", TRIAL_EPISODE) else None
    print(json.dumps({"episode": TRIAL_EPISODE, "frames": frames, "audit_wall_seconds": payload["wall_seconds"],
                      "devtable_runner_seconds": round(expected_seconds("VSMT-lean", TRIAL_EPISODE), 1), "audit_over_runner": ratio,
                      "report_identical_to_devtable": same, "devtable_runner_seconds_per_arm_all_39": estimate}, indent=1))
    return 0 if same else 3


def cmd_run(args: argparse.Namespace) -> int:
    root = diag_root()
    tasks = sorted(((arm, e) for arm in ARMS for e in episodes()), key=lambda t: (-expected_seconds(*t), t))
    curves_out = root / "term_curves"
    curves_proc = None
    if args.with_term_curves and not (curves_out / "term_curves.json").exists():
        command = [PY, str(ROOT / "ops/vsmt/lean_s2_05_term_curves.py"), "--output-root", str(PASS_ROOT), "--pass", "dagger_round_1",
                   "--round", "1", "--source-arm", "VSMT-lean", "--also-score-arm", "AssocOnly", "--out-dir", str(curves_out)]
        (root / "logs").mkdir(parents=True, exist_ok=True)
        curves_log = (root / "logs" / "term_curves.log").open("w")
        curves_proc = subprocess.Popen(command, cwd=ROOT, stdout=curves_log, stderr=subprocess.STDOUT, env={**os.environ, **THREAD_ENV})
    print(f"[ruling79] {time.strftime('%F %T')} run at {short_commit()}: {len(tasks)} audits on {args.workers} workers "
          f"(cgroup {cpu_quota()} CPUs), term curves {'started' if curves_proc else 'skipped/done'}", flush=True)
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(audit_task, arm, e) for arm, e in tasks]
        for done, future in enumerate(concurrent.futures.as_completed(futures), 1):
            result = future.result()
            results.append(result)
            print(f"[ruling79] {time.strftime('%F %T')} {done}/{len(tasks)} {result['arm']} {result['episode']} exit {result['exit']} "
                  f"{result['seconds']} s{' (reused)' if result['reused'] else ''}", flush=True)
    curves_exit = None
    if curves_proc is not None:
        curves_exit = curves_proc.wait()
        print(f"[ruling79] {time.strftime('%F %T')} term curves exit {curves_exit}", flush=True)
    status = {"commit": git("rev-parse", "HEAD"), "diag_root": str(root), "workers": args.workers, "cgroup_cpus": cpu_quota(),
              "worker_basis": f"{args.workers} audit workers x 1 thread on one shared queue, largest first; term curves on one more CPU",
              "audits": sorted(results, key=lambda r: (r["arm"], r["episode"])), "failed": [r for r in results if r["exit"] != 0],
              "term_curves_exit": curves_exit, "finished_cst": time.strftime("%F %T")}
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    (EXPORT_DIR / f"ruling79_diagnostics_{short_commit()}.status.json").write_text(json.dumps(status, indent=1))
    print(f"[ruling79] {len(status['failed'])} failed audits; status written", flush=True)
    code = 0 if not status["failed"] and curves_exit in (None, 0) else 1
    if args.shutdown_grace is not None:
        time.sleep(int(args.shutdown_grace))
        print(f"[ruling79] {time.strftime('%F %T')} shutting down (AutoDL)", flush=True)
        subprocess.run(["/usr/bin/shutdown"])
    return code


def strip_runtime(report: dict[str, Any]) -> dict[str, Any]:
    """The report without the wall-clock fields (runtime and peak memory differ between any two runs)."""

    out = json.loads(json.dumps(report))
    size = out.get("size_and_cost") or {}
    for name in ("runtime_per_frame_s", "peak_memory_bytes"):
        size.pop(name, None)
    return out


def cmd_merge(args: argparse.Namespace) -> int:
    root = diag_root()
    commit = short_commit()
    summary: dict[str, Any] = {"commit": git("rev-parse", "HEAD"), "diag_root": str(root), "arms": {}}
    code = 0
    for arm in ARMS:
        results = EXPORT_DIR / f"vsmt_lean_s2_05_node_audit_ruling79_{arm}_{commit}.json"
        merged = subprocess.run([PY, str(ROOT / "ops/vsmt/lean_s2_05_node_audit.py"), "merge", "--output-root", str(root / "audit"),
                                 "--arm", arm, "--results", str(results)], cwd=ROOT, capture_output=True, text=True)
        same, differ, missing = [], [], []
        for episode_id in episodes():
            path = root / "audit" / episode_id / arm / "node_audit.json"
            if not path.exists():
                missing.append(episode_id)
                continue
            report = json.loads(path.read_text())["report"]
            (same if strip_runtime(report) == strip_runtime(devtable_receipt(arm, episode_id)["report"]) else differ).append(episode_id)
        summary["arms"][arm] = {"merge_exit": merged.returncode, "merge_stderr_tail": merged.stderr[-2000:], "results": str(results),
                                "reports_identical_to_devtable": len(same), "reports_differ": differ, "audits_missing": missing}
        code |= int(merged.returncode != 0 or bool(differ) or bool(missing))
    curves = root / "term_curves" / "term_curves.json"
    if curves.exists():
        target = EXPORT_DIR / f"vsmt_lean_s2_05_term_curves_round1_VSMT-lean_{commit}.json"
        shutil.copyfile(curves, target)
        summary["term_curves"] = {"results": str(target), "reproduced_all": json.loads(curves.read_text())["reproduced_all"]}
    else:
        summary["term_curves"] = None
    (EXPORT_DIR / f"vsmt_lean_s2_05_ruling79_summary_{commit}.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({arm: {k: v for k, v in row.items() if k != "merge_stderr_tail"} for arm, row in summary["arms"].items()}, indent=1))
    print(json.dumps(summary["term_curves"]))
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="step", required=True)
    sub.add_parser("check").set_defaults(func=cmd_check)
    export = sub.add_parser("export")
    export.add_argument("--workers", type=int, required=True)
    export.set_defaults(func=cmd_export)
    sub.add_parser("trial").set_defaults(func=cmd_trial)
    run = sub.add_parser("run")
    run.add_argument("--workers", type=int, required=True)
    run.add_argument("--no-term-curves", dest="with_term_curves", action="store_false")
    run.add_argument("--shutdown-grace", type=int, default=None, help="seconds to wait after the status file, then power off")
    run.set_defaults(func=cmd_run)
    sub.add_parser("merge").set_defaults(func=cmd_merge)
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
