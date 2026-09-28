#!/usr/bin/env python3
"""Ruling 80 diagnostics on the server (80-3 dormancy off, 80-4 association errors by target state), read-only.

白话：裁决 80 批准的两项开机诊断用固定命令跑。输入与裁决 79 相同（开发趟 lean-s2-05-oracle-c150be0 的第 1 轮头、
S1-03 oracle cache、S1-02 episode、S1-04 几何表、ReID 权重）；输出写进新的诊断根和 exports/。三组各 39 条节点审计 v4：
VSMT-lean 与 AssocOnly 用开发表配置（报告须与开发表逐项一致），VSMT-lean-dormancy-off 用同一配置和头、只把共享休眠
上限换成 10^9（等于关闭休眠；只作诊断，不是登记的臂）。它不产生权重、不读 validation/test。

Steps (each stops; the next is started by hand after reading the previous output):
  check                 commit, clean checkout, inputs, CPUs, memory, disk, leftover shutdown timers (ruling 79's check)
  trial                 01289 under VSMT-lean and under VSMT-lean-dormancy-off side by side, timed
  run --workers N       all 3 x 39 audits on one shared queue, largest first, resuming by skipping finished audits
  merge                 pooled audits per group, determinism check of the two registered groups, one summary
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))

import ruling79_diagnostics as r79  # noqa: E402  (same paths, helpers and determinism rule)

DORMANCY_OFF_LIMIT = 10 ** 9
#: group -> (arm, extra node-audit arguments, compared with the development table)
GROUPS = {
    "VSMT-lean": ("VSMT-lean", [], True),
    "AssocOnly": ("AssocOnly", [], True),
    "VSMT-lean-dormancy-off": ("VSMT-lean", ["--dormancy-override", str(DORMANCY_OFF_LIMIT)], False),
}


def diag_root() -> Path:
    return r79.AUTODL / f"vsmt_private/ruling80-{r79.short_commit()}"


def audit_path(group: str, episode_id: str) -> Path:
    return diag_root() / "audit" / group / episode_id / GROUPS[group][0] / "node_audit.json"


def audit_task(group: str, episode_id: str) -> dict[str, Any]:
    arm, extra, _ = GROUPS[group]
    if audit_path(group, episode_id).exists():
        return {"group": group, "episode": episode_id, "exit": 0, "seconds": None, "reused": True}
    command = r79.audit_command(arm, episode_id, diag_root() / "audit" / group) + extra
    code, seconds = r79.run_logged(command, diag_root() / "logs" / group / f"{episode_id}.log")
    return {"group": group, "episode": episode_id, "exit": code, "seconds": seconds, "reused": False}


def cmd_trial(args: argparse.Namespace) -> int:
    trial = [("VSMT-lean", r79.TRIAL_EPISODE), ("VSMT-lean-dormancy-off", r79.TRIAL_EPISODE)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(trial)) as pool:
        results = list(pool.map(lambda task: audit_task(*task), trial))
    out: dict[str, Any] = {}
    for result in results:
        path = audit_path(result["group"], r79.TRIAL_EPISODE)
        if result["exit"] != 0 or not path.exists():
            out[result["group"]] = {"failed": result}
            continue
        payload = json.loads(path.read_text())
        registered = r79.devtable_receipt("VSMT-lean", r79.TRIAL_EPISODE)["report"]
        out[result["group"]] = {"audit_wall_seconds": payload["wall_seconds"], "frames": payload["frames"],
                                "dormancy_override": payload.get("dormancy_override"),
                                "final_entities_by_state": payload["final_entities_by_state"],
                                "report_identical_to_devtable": r79.strip_runtime(payload["report"]) == r79.strip_runtime(registered),
                                "node_f1": payload["report"]["node_prf1"]["node_f1"], "devtable_node_f1": registered["node_prf1"]["node_f1"]}
    out["devtable_runner_seconds_all_39"] = {g: round(sum(r79.expected_seconds(GROUPS[g][0], e) for e in r79.episodes())) for g in GROUPS}
    print(json.dumps(out, indent=1))
    ok = all("failed" not in v for k, v in out.items() if k in GROUPS) and out["VSMT-lean"].get("report_identical_to_devtable") is True
    return 0 if ok else 3


def cmd_run(args: argparse.Namespace) -> int:
    tasks = sorted(((g, e) for g in GROUPS for e in r79.episodes()), key=lambda t: (-r79.expected_seconds(GROUPS[t[0]][0], t[1]), t))
    print(f"[ruling80] {time.strftime('%F %T')} run at {r79.short_commit()}: {len(tasks)} audits on {args.workers} workers "
          f"(cgroup {r79.cpu_quota()} CPUs)", flush=True)
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(audit_task, g, e) for g, e in tasks]
        for done, future in enumerate(concurrent.futures.as_completed(futures), 1):
            result = future.result()
            results.append(result)
            print(f"[ruling80] {time.strftime('%F %T')} {done}/{len(tasks)} {result['group']} {result['episode']} exit {result['exit']} "
                  f"{result['seconds']} s{' (reused)' if result['reused'] else ''}", flush=True)
    status = {"commit": r79.git("rev-parse", "HEAD"), "diag_root": str(diag_root()), "workers": args.workers, "cgroup_cpus": r79.cpu_quota(),
              "worker_basis": f"{args.workers} audit workers x 1 thread on one shared queue, largest first",
              "audits": sorted(results, key=lambda r: (r["group"], r["episode"])), "failed": [r for r in results if r["exit"] != 0],
              "finished_cst": time.strftime("%F %T")}
    r79.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    (r79.EXPORT_DIR / f"ruling80_diagnostics_{r79.short_commit()}.status.json").write_text(json.dumps(status, indent=1))
    print(f"[ruling80] {len(status['failed'])} failed audits; status written", flush=True)
    return 0 if not status["failed"] else 1


def cmd_merge(args: argparse.Namespace) -> int:
    commit = r79.short_commit()
    summary: dict[str, Any] = {"commit": r79.git("rev-parse", "HEAD"), "diag_root": str(diag_root()), "groups": {}}
    code = 0
    for group, (arm, extra, compared) in GROUPS.items():
        results = r79.EXPORT_DIR / f"vsmt_lean_s2_05_node_audit_ruling80_{group}_{commit}.json"
        merged = subprocess.run([r79.PY, str(r79.ROOT / "ops/vsmt/lean_s2_05_node_audit.py"), "merge", "--output-root",
                                 str(diag_root() / "audit" / group), "--arm", arm, "--results", str(results)],
                                cwd=r79.ROOT, capture_output=True, text=True)
        same, differ, missing = [], [], []
        for episode_id in r79.episodes():
            path = audit_path(group, episode_id)
            if not path.exists():
                missing.append(episode_id)
                continue
            if compared:
                report = json.loads(path.read_text())["report"]
                (same if r79.strip_runtime(report) == r79.strip_runtime(r79.devtable_receipt(arm, episode_id)["report"]) else differ).append(episode_id)
        summary["groups"][group] = {"arm": arm, "extra_arguments": extra, "merge_exit": merged.returncode, "merge_stderr_tail": merged.stderr[-2000:],
                                    "results": str(results), "compared_with_devtable": compared,
                                    "reports_identical_to_devtable": len(same) if compared else None, "reports_differ": differ,
                                    "audits_missing": missing}
        code |= int(merged.returncode != 0 or bool(differ) or bool(missing))
    (r79.EXPORT_DIR / f"vsmt_lean_s2_05_ruling80_summary_{commit}.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({g: {k: v for k, v in row.items() if k != "merge_stderr_tail"} for g, row in summary["groups"].items()}, indent=1))
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="step", required=True)
    sub.add_parser("check").set_defaults(func=r79.cmd_check)
    sub.add_parser("trial").set_defaults(func=cmd_trial)
    run = sub.add_parser("run")
    run.add_argument("--workers", type=int, required=True)
    run.set_defaults(func=cmd_run)
    sub.add_parser("merge").set_defaults(func=cmd_merge)
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
