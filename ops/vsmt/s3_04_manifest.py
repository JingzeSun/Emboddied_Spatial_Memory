#!/usr/bin/env python3
"""S3-04 (ruling 106, 2026-10-05: 「待裁 106 全按推荐」): the choice on validation and the freeze before test -- the steps of
``ops/vsmt/s3_04_freeze.sh``.

S3-04 runs once, after S3-03's closing verify passed and before S3-05 unseals test, and freezes both front ends together.
Each step reads the S3-03 run root (read only) and exports, and writes this commit's output root
``$AUTODL/vsmt_private/s3-04-<commit>``:
  * ``check`` (G1, G5): S3-03's verify at the registration commit found no problem, its exports equal its manifest, the 30
    round-1 weights files equal their training receipts, the contract's registered values equal the run's; the four test
    roots' seal markers still say sealed with the digest of the seal S3-02 exported (marker files only);
  * ``select --front`` (G2, G3 and the choice): recomputes the selection readings from the merged audits with the frozen code
    and compares them value by value with S3-03's, checks the common events, then picks each arm's configuration by 102-4 and
    fixes the S3-05 run list and the probe episodes;
  * ``probe --front`` (G4): reruns every selected run (learned arms at the five seeds) on 2 validation episodes at this commit
    and compares them bit for bit with S3-03's audits;
  * ``receipt``: only when G1-G5 passed and S3-05's entry is in this commit, writes the freeze receipt (choice, test run
    list, statistics plan, code digests, weight and registered-value digests, environment) and the exports;
  * ``verify``: recomputes the exports' digests and writes the run manifest and the verification file.
Inputs: the S3-03 run root and exports. Outputs: ``exports/vsmt_lean_s3_04_*_<commit>.json``. Example: if G4 finds that a
rule arm's rerun audit differs from S3-03's by one memory digest, probe stops with exit 3 and no receipt is written. It reads
no test data, trains nothing, computes no main gate and changes no file in the S3-03 run root.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
for item in (ROOT / "src", HERE.parent):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import s3_03_manifest as s303  # noqa: E402
from vsmt import lean_arms as arms  # noqa: E402
from vsmt import lean_s3_03 as s3  # noqa: E402
from vsmt import lean_s3_04 as s4  # noqa: E402
from vsmt import lean_test_seal  # noqa: E402

STAGE = "vsmt.lean.s3_04.driver.v1"
#: Ruling 106-1 (a): the freeze covers the code S3-05 runs, so S3-04 refuses to write a receipt before S3-05's entry exists.
S3_05_ENTRY = "ops/vsmt/s3_05_test.sh"
S0_05_CONTRACT = ROOT / "configs" / "vsmt" / "lean_s0_arms_v2.json"
#: A rerun audit of the probe keeps this much memory per process (S3-03 measured 0.85 / 1.85 GiB for learned / rule arms).
PROBE_GIB = 2.0
RESERVE_CORES, RESERVE_GIB = 2, 8.0

load_json = s303.load_json
write_json = s303.write_json
utc_now = s303.utc_now


class DriverError(ValueError):
    """Raised with a short machine-readable code."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DriverError(code)


def git(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=str(ROOT), text=True).strip()


def step_path(out_root: Path, name: str) -> Path:
    return out_root / f"{name}.json"


def finish(out_root: Path, name: str, payload: dict[str, Any]) -> int:
    payload = {"stage": STAGE, "step": name, "code_commit": git("rev-parse", "HEAD"), "written_utc": utc_now(), **payload}
    payload["pass"] = not payload.get("problems")
    write_json(step_path(out_root, name), payload)
    print(f"[s3-04-{name}] pass={payload['pass']}; problems: {payload.get('problems')[:6] if payload.get('problems') else 'none'}")
    return 0 if payload["pass"] else 3


def passed(out_root: Path, name: str) -> bool:
    path = step_path(out_root, name)
    if not path.exists():
        return False
    payload = load_json(path)
    return bool(payload.get("pass")) and payload.get("code_commit") == git("rev-parse", "HEAD")


def context(args: argparse.Namespace) -> s303.RunContext:
    run_root = Path(args.s3_03_run_root)
    lean_test_seal.refuse_sealed([run_root, Path(args.out_root)], reader="s3-04")  # never a test root
    return s303.load_context(run_root)


# --------------------------------------------------------------------------
# check: G1 and G5
# --------------------------------------------------------------------------

def heads_record(ctx: s303.RunContext, front: str) -> tuple[dict[str, Any], list[str]]:
    """G1: each round-1 training's heads file against its receipt (grouped heads for the grouped arms), with the file's sha256."""

    rows, problems = {}, []
    for arm in s3.TRAINED_ARMS:
        for seed in arms.SEEDS:
            job = f"{front}/t1/{arm}/s{seed}"
            status = s303.job_status(ctx.run_root, job)
            heads = ctx.heads_file(front, 1, arm, seed)
            receipt_path = ctx.training_dir(front, 1, arm, seed) / "training_receipt.json"
            row: dict[str, Any] = {"job_status": status, "heads": str(heads)}
            state_file = ctx.run_root / "jobs" / f"{s303.pool.state_key(job)}.json"
            reason = str((load_json(state_file) if state_file.exists() else {}).get("reason") or "")
            if status == "diverged" or (status == "skipped" and reason.startswith("dependency_")):
                row["usable"] = False  # a result (ruling 102-9): its own or its round-0 training diverged; S3-03 counts it absent
                row["reason"] = reason or None
            elif status != "done" or not heads.exists() or not receipt_path.exists():
                problems.append(f"training_not_done_or_files_missing:{job}:{status}")
                row["usable"] = False
            else:
                receipt = load_json(receipt_path)
                expected = (receipt.get("group_selection") or {}).get("weights_sha256") if heads.name == "weights_grouped.json" \
                    else receipt.get("weights_sha256")
                payload = load_json(heads).get("sha256")
                row.update({"usable": payload == expected and not receipt.get("diverged"), "payload_sha256": payload,
                            "receipt_weights_sha256": expected, "file_sha256": s4.file_sha256(heads)})
                if payload != expected:
                    problems.append(f"heads_differ_from_the_training_receipt:{job}")
            rows[f"{arm}|{seed}"] = row
    return rows, problems


def cmd_check(args: argparse.Namespace) -> int:
    out_root, export_dir, tag = Path(args.out_root), Path(args.export_dir), args.s3_03_tag
    ctx = context(args)
    problems: list[str] = []
    verify_path = export_dir / f"vsmt_lean_s3_03_verify_{tag}.json"
    manifest_path = export_dir / f"vsmt_lean_s3_03_manifest_{tag}.json"
    s3_03: dict[str, Any] = {"tag": tag, "verify": str(verify_path), "manifest": str(manifest_path)}
    if not verify_path.exists() or not manifest_path.exists():
        problems.append("s3_03_verify_or_manifest_missing")
    else:
        verify, manifest = load_json(verify_path), load_json(manifest_path)
        s3_03.update({"verify_sha256": s4.file_sha256(verify_path), "manifest_sha256": s4.file_sha256(manifest_path),
                      "verified_at_commit": manifest.get("code_commit")})
        if verify.get("problems"):
            problems.append(f"s3_03_verify_has_problems:{verify['problems'][:4]}")
        if verify.get("manifest_sha256") != s3_03["manifest_sha256"]:
            problems.append("s3_03_manifest_differs_from_its_verify")
        for name, record in sorted((manifest.get("exports") or {}).items()):
            path = export_dir / name
            if not path.exists() or s4.file_sha256(path) != record.get("sha256"):
                problems.append(f"s3_03_export_differs_from_its_manifest:{name}")
        for front in ctx.fronts:
            if not ((manifest.get("registered_values") or {}).get(front) or {}).get("equal"):
                problems.append(f"s3_03_registered_values_not_equal:{front}")
    if ctx.inputs.get("provisional") or ctx.inputs.get("problems"):
        problems.append("s3_03_inputs_provisional_or_with_problems")
    contract = load_json(S0_05_CONTRACT)
    registered, heads = {}, {}
    for front in ctx.fronts:
        here = arms.elu_p_fitted(contract, s4.FRONTS[front])
        registered[front] = here
        if here != ctx.fit_values(front):
            problems.append(f"elu_p_registered_values_differ_from_the_run:{front}")
        heads[front], more = heads_record(ctx, front)
        problems += more
    seal = s303.test_seal_report(export_dir / f"vsmt_lean_s3_02_test_seal_{ctx.inputs['s3_02']['tag']}.json", problems)
    return finish(out_root, "check", {"rule": s4.CHECKS_RULE, "s3_03": s3_03, "elu_p_registered": registered, "heads": heads,
                                      "test_seal": seal, "problems": problems})


# --------------------------------------------------------------------------
# select: G2, G3 and the choice
# --------------------------------------------------------------------------

def cmd_select(args: argparse.Namespace) -> int:
    out_root, front = Path(args.out_root), args.front
    ctx = context(args)
    problems: list[str] = []
    runs, merge_problems, absent = s303.readings_runs(ctx, front)
    problems += merge_problems
    if merge_problems:
        return finish(out_root, f"select_{front}", {"front": front, "problems": problems})
    recomputed = s3.selection_readings(runs, mask_source=s4.FRONTS[front], absent_arms=absent)
    recorded_path = ctx.front_dir(front) / "selection_readings.json"
    recorded = load_json(recorded_path) if recorded_path.exists() else {}
    differing = s4.readings_differences(recorded, recomputed) if recorded else ["s3_03_readings_missing"]
    problems += [f"g2_readings_differ:{item}" for item in differing]
    problems += [f"g3_{item}" for item in s4.event_problems(recomputed)]
    selection = s4.select_front(recomputed)
    coverage_path = ctx.front_dir(front) / "coverage.json"  # ruling 104-2 / 106-3: state coverage, report only
    # the events are the same in every run (G3), so any run names the episodes; AssocOnly's when it exists
    reference = next((run for run in runs if run["arm"] == arms.SELECTION_REFERENCE_ARM), runs[0])
    episodes = s4.probe_episodes(reference["reports"], ctx.frames(front, "validation"))
    return finish(out_root, f"select_{front}", {
        "front": front, "mask_source": s4.FRONTS[front],
        "g2": {"recorded": str(recorded_path), "recorded_sha256": s4.file_sha256(recorded_path) if recorded else None,
               "differences": differing},
        "g3": recomputed["key_events"], "selection": selection,
        "test_runs": s4.test_runs(selection, elu_p_values=ctx.fit_values(front)),
        "state_coverage": load_json(coverage_path) if coverage_path.exists() else None,
        "probe_episodes": episodes, "readings": recomputed, "problems": problems})


# --------------------------------------------------------------------------
# probe: G4
# --------------------------------------------------------------------------

def probe_tasks(ctx: s303.RunContext, front: str, select: Mapping[str, Any], out_root: Path) -> list[dict[str, Any]]:
    import lean_s2_05_node_audit as audit

    tasks = []
    for run in select["test_runs"]:
        arm, index, seed = run["arm"], int(run["config_index"]), run["seed"]
        config = dict(run["config"])  # the runner configuration S3-05 will run (ELU-P with its fitted values, as in S3-03)
        heads = ctx.heads_file(front, 1, run["heads_arm"], seed) if seed is not None else None
        group = s303.group_name(arm, index, seed)
        for episode in select["probe_episodes"]:
            root = out_root / front / "probe" / group
            argv = ctx.audit(front, episode, arm, seed, [(index, config)], heads=heads)
            argv[argv.index("--configs") + 1] = json.dumps([{"config": config, "output_root": str(root)}])
            span = next(f"c{part[0]:02d}-{part[-1]:02d}" for part in audit_chunks(arm) if index in part)
            job = f"{front}/audit/{arm}/{'rule' if seed is None else f's{seed}'}/{span}/{episode}"
            state_path = ctx.run_root / "jobs" / f"{s303.pool.state_key(job)}.json"
            state = load_json(state_path) if state_path.exists() else {}
            tasks.append({"group": group, "episode": episode, "arm": arm, "argv": argv,
                          "original_job": job, "original_host": state.get("host") or "local", "original_status": state.get("status"),
                          "original": str(ctx.group_root(front, arm, index, seed) / episode / arm / audit.AUDIT_FILE_NAME),
                          "rerun": str(root / episode / arm / audit.AUDIT_FILE_NAME),
                          "log": str(out_root / front / "probe" / "logs" / f"{group}-{episode}.log")})
    return tasks


def audit_chunks(arm: str) -> list[list[int]]:
    """The configuration chunks S3-03's audit jobs ran (CONFIGS_PER_AUDIT_JOB), to name the job of an original audit."""

    count = len(s303.audit_configs(arm))
    size = s303.CONFIGS_PER_AUDIT_JOB["learned" if s3.SELECTION_ARMS[arm] else "rule"]
    return [list(range(start, min(start + size, count))) for start in range(0, count, size)]


def worker_count(tasks: int, requested: int | None) -> dict[str, Any]:
    """The largest safe number of single-threaded audits here (cgroup cores less 2, memory less 8 GiB at 2 GiB each)."""

    info = s303.resources()
    by_cores = max(1, int(info["cpu_quota"]) - RESERVE_CORES)
    by_memory = max(1, int((int(info["memory_bytes"]) / 2 ** 30 - RESERVE_GIB) // PROBE_GIB))
    actual = max(1, min(by_cores, by_memory, tasks, requested or tasks))
    return {"requested": requested, "actual": actual, "by_cores": by_cores, "by_memory": by_memory, "tasks": tasks,
            "resources": {"cpu_quota": info["cpu_quota"], "memory_bytes": info["memory_bytes"]}}


def run_task(task: Mapping[str, Any]) -> dict[str, Any]:
    Path(task["log"]).parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, **s303.pool.thread_environment(1)}  # exactly the S3-03 pool's environment for a single-threaded audit
    with open(task["log"], "ab") as handle:
        code = subprocess.run(task["argv"], stdout=handle, stderr=subprocess.STDOUT, cwd=str(ROOT), env=env).returncode
    keys = ("group", "episode", "arm", "original", "rerun", "log", "original_job", "original_host", "original_status")
    return {**{key: task[key] for key in keys}, "exit": code}


def cmd_probe(args: argparse.Namespace) -> int:
    import lean_s2_05_node_audit as audit

    out_root, front = Path(args.out_root), args.front
    _require(passed(out_root, f"select_{front}"), f"probe_needs_a_passed_select_at_this_commit:{front}")
    ctx = context(args)
    tasks = probe_tasks(ctx, front, load_json(step_path(out_root, f"select_{front}")), out_root)
    workers = worker_count(len(tasks), args.workers)
    print(f"[s3-04-probe] {front}: {len(tasks)} audits on {workers['actual']} workers", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers["actual"]) as executor:
        rows = list(executor.map(run_task, tasks))  # results in task order, whatever the finishing order
    problems = []
    for row in rows:
        if row["exit"] != 0 or not Path(row["rerun"]).exists() or not Path(row["original"]).exists():
            row["identical"] = False
            problems.append(f"g4_audit_failed_or_missing:{row['group']}:{row['episode']}:exit{row['exit']}")
            continue
        first, again = load_json(Path(row["original"])), load_json(Path(row["rerun"]))
        left, right = audit.comparable_metrics(first), audit.comparable_metrics(again)
        row["differing_fields"] = sorted(key for key in set(left) | set(right) if left.get(key) != right.get(key))
        row["identical"] = not row["differing_fields"] and first.get("audit") == again.get("audit")
        if not row["identical"]:
            problems.append(f"g4_differs:{row['group']}:{row['episode']}:{row['differing_fields'][:4]}")
    return finish(out_root, f"probe_{front}", {"front": front, "workers": workers, "rows": rows, "problems": problems,
                                                "compared": "every audit field but wall time, commit and head path (comparable_metrics)"})


# --------------------------------------------------------------------------
# receipt, export and verify
# --------------------------------------------------------------------------

def environment() -> dict[str, Any]:
    facts: dict[str, Any] = {"python": sys.version.split()[0], "executable": sys.executable, "platform": platform.platform()}
    for name in ("torch", "numpy"):
        try:
            facts[name] = __import__(name).__version__
        except Exception as exc:  # recorded, the receipt states what the freeze ran with
            facts[name] = f"missing:{type(exc).__name__}"
    try:
        facts["cpu_model"] = next(line.split(":", 1)[1].strip() for line in open("/proc/cpuinfo") if line.startswith("model name"))
    except (OSError, StopIteration):
        facts["cpu_model"] = None
    return facts


def tracked_code_files() -> list[str]:
    return [name for name in git("ls-files", *s4.CODE_DIRECTORIES).splitlines() if name]


def cmd_receipt(args: argparse.Namespace) -> int:
    out_root, export_dir = Path(args.out_root), Path(args.export_dir)
    ctx = context(args)
    problems = [f"{name}_not_passed_at_this_commit" for name in
                ("check", *(f"{step}_{front}" for step in ("select", "probe") for front in ctx.fronts)) if not passed(out_root, name)]
    if not (ROOT / S3_05_ENTRY).exists():
        problems.append(f"s3_05_entry_missing:{S3_05_ENTRY} (ruling 106-1 (a): the freeze covers the code S3-05 runs)")
    if git("status", "--porcelain"):
        problems.append("worktree_not_clean")
    if problems:
        return finish(out_root, "receipt", {"problems": problems})
    previous = load_json(Path(args.previous_receipt)) if args.previous_receipt else None
    check = load_json(step_path(out_root, "check"))
    fronts: dict[str, Any] = {}
    heads: dict[str, str] = {}
    for front in ctx.fronts:
        select = load_json(step_path(out_root, f"select_{front}"))
        probe = load_json(step_path(out_root, f"probe_{front}"))
        for run in select["test_runs"]:
            if run["seed"] is not None:
                row = check["heads"][front][f"{run['heads_arm']}|{run['seed']}"]
                heads[row["heads"]] = row["file_sha256"]
        fronts[front] = {"mask_source": s4.FRONTS[front], "selection": select["selection"], "test_runs": select["test_runs"],
                         "runs_per_test_episode": len(select["test_runs"]), "probe_episodes": select["probe_episodes"],
                         "probe_audits_identical": sum(1 for row in probe["rows"] if row.get("identical")),
                         "validation_events": select["g3"], "state_coverage_report_only": select.get("state_coverage"),
                         "step_sha256": {
                             "select": s4.file_sha256(step_path(out_root, f"select_{front}")),
                             "probe": s4.file_sha256(step_path(out_root, f"probe_{front}"))}}
    for front in ctx.fronts:
        reid = ctx.inputs["reid"][front]
        heads[str(reid["file"])] = s4.file_sha256(Path(reid["file"]))
    manifest = s3.load_manifest()
    head = git("rev-parse", "HEAD")
    receipt: dict[str, Any] = {
        "stage": STAGE, "ruling": "106 (2026-10-05, 「待裁 106 全按推荐」)", "freeze_commit": head, "written_utc": utc_now(),
        "rules": {"selection": s4.SELECTION_RULE, "checks": s4.CHECKS_RULE, "changes": s4.FREEZE_CHANGE_RULE,
                  "publication": s4.PUBLICATION_RULE},
        "checks": {"g1_g5": s4.file_sha256(step_path(out_root, "check")), "all_passed": True},
        "s3_03": check["s3_03"], "fronts": fronts, "not_frozen": dict(s4.NOT_FROZEN),
        "statistics": s4.statistics_plan(),
        "code": {**s4.code_digest(ROOT, tracked_code_files()),
                 "git_trees": {name: git("rev-parse", f"HEAD:{name}") for name in s4.CODE_DIRECTORIES}, "s3_05_entry": S3_05_ENTRY},
        "frozen_bytes": {"heads": heads, "elu_p_registered": check["elu_p_registered"],
                         "test_manifest_sha256": s4.test_manifest_sha256(manifest), "test_manifest_houses": len(manifest["test"]),
                         "test_seal_sha256": check["test_seal"].get("seal_sha256")},
        "environment": environment(),
        "plain_language_zh": ("S3-04 冻结回执：两套前端每个臂进 test 的唯一配置、test 上每条 episode 要跑的 25 个运行、S3-05 要算的统计、"
                              "test 当天会运行的每个代码文件与权重文件的指纹；S3-05 解封前逐项重算，任何一项不同就不开封。"),
    }
    if previous is not None:  # ruling 106-4 (a): a re-freeze after an ops-only fix chooses exactly what the previous one chose
        differing = s4.selection_differences(previous, receipt)
        receipt["refreeze"] = {"previous_receipt_sha256": previous.get("receipt_sha256"),
                               "previous_freeze_commit": previous.get("freeze_commit"),
                               "code_changes": s4.code_differences(previous["code"], receipt["code"]),
                               "selection_differences": differing}
        if differing:
            return finish(out_root, "receipt", {"problems": [f"refreeze_selection_differs:{item}" for item in differing[:10]]})
    receipt["receipt_sha256"] = s4.receipt_body_sha256(receipt)
    write_json(out_root / "freeze_receipt.json", receipt)
    tag = head[:7]
    exports = {f"vsmt_lean_s3_04_freeze_{tag}.json": receipt, f"vsmt_lean_s3_04_check_{tag}.json": check}
    for front in ctx.fronts:
        exports[f"vsmt_lean_s3_04_selection_{front}_{tag}.json"] = load_json(step_path(out_root, f"select_{front}"))
        exports[f"vsmt_lean_s3_04_probe_{front}_{tag}.json"] = load_json(step_path(out_root, f"probe_{front}"))
    for name, payload in exports.items():
        write_json(export_dir / name, payload)
    return finish(out_root, "receipt", {"receipt_sha256": receipt["receipt_sha256"], "exports": sorted(exports), "problems": []})


def cmd_verify(args: argparse.Namespace) -> int:
    out_root, export_dir = Path(args.out_root), Path(args.export_dir)
    problems: list[str] = []
    if not passed(out_root, "receipt"):
        problems.append("receipt_not_passed_at_this_commit")
        return finish(out_root, "verify", {"problems": problems})
    receipt = load_json(out_root / "freeze_receipt.json")
    tag = receipt["freeze_commit"][:7]
    contract = load_json(S0_05_CONTRACT)
    # the same check S3-05's entry makes before it unseals (one code path)
    problems += s4.verify_freeze(
        receipt, code=s4.code_digest(ROOT, tracked_code_files()),
        heads={path: s4.file_sha256(Path(path)) if Path(path).exists() else None for path in receipt["frozen_bytes"]["heads"]},
        registered_values={front: arms.elu_p_fitted(contract, s4.FRONTS[front]) for front in receipt["frozen_bytes"]["elu_p_registered"]},
        test_manifest_sha256=s4.test_manifest_sha256(s3.load_manifest()))
    exports = {path.name: {"sha256": s4.file_sha256(path), "bytes": path.stat().st_size}
               for path in sorted(export_dir.glob(f"vsmt_lean_s3_04_*_{tag}.json"))
               if not path.name.startswith(("vsmt_lean_s3_04_manifest_", "vsmt_lean_s3_04_verify_"))}
    manifest = {"stage": STAGE, "step": "manifest", "tag": tag, "freeze_commit": receipt["freeze_commit"], "written_utc": utc_now(),
                "receipt_sha256": receipt["receipt_sha256"], "exports": exports, "problems": problems,
                "next": ("ruling 106-5 (a): commit these exports to results/, push main and s1-02a-runner, and wait for the user's "
                         "go before S3-05 unseals any test root"),
                "reproduction": "bash ops/vsmt/s3_04_freeze.sh all at the freeze commit (README 'How to reproduce S3-04')"}
    write_json(export_dir / f"vsmt_lean_s3_04_manifest_{tag}.json", manifest)
    write_json(export_dir / f"vsmt_lean_s3_04_verify_{tag}.json",
               {"stage": STAGE, "step": "verify", "problems": problems, "exports_checked": len(exports),
                "manifest_sha256": s4.file_sha256(export_dir / f"vsmt_lean_s3_04_manifest_{tag}.json")})
    return finish(out_root, "verify", {"exports": len(exports), "problems": problems})


def cmd_status(args: argparse.Namespace) -> int:
    out_root = Path(args.out_root)
    rows = {}
    for path in sorted(out_root.glob("*.json")):
        payload = load_json(path)
        if "step" in payload:
            rows[payload["step"]] = {"pass": payload.get("pass"), "commit": str(payload.get("code_commit"))[:12],
                                     "problems": (payload.get("problems") or [])[:3], "written_utc": payload.get("written_utc")}
    print(json.dumps(rows, indent=1))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="step", required=True)
    for name, func in (("check", cmd_check), ("select", cmd_select), ("probe", cmd_probe), ("receipt", cmd_receipt),
                       ("verify", cmd_verify), ("status", cmd_status)):
        command = sub.add_parser(name)
        command.add_argument("--out-root", required=True)
        if name != "status":
            command.add_argument("--s3-03-run-root", required=True)
            command.add_argument("--export-dir", required=True)
            command.add_argument("--s3-03-tag", required=True)
        if name in ("select", "probe"):
            command.add_argument("--front", required=True, choices=list(s4.FRONTS))
        if name == "probe":
            command.add_argument("--workers", type=int, default=None)
        if name == "receipt":
            command.add_argument("--previous-receipt", default=None,
                                 help="a re-freeze after an ops-only fix (ruling 106-4 (a)): the selection must equal this receipt's")
        command.set_defaults(func=func)
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (DriverError, s4.LeanS3_04Error, s303.DriverError, s3.LeanS3_03Error, lean_test_seal.LeanTestSealError) as exc:
        print(f"[s3-04] refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
