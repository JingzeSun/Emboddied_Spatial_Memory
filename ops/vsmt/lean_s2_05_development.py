"""S2-05: the development table -- run a pass over every development episode, merge, fit, train, tabulate.

Subcommands (server, frontend env; the S2-05, S2-04 and S2-01 bits must be open and every value frozen):
    run-pass            one arm over every succeeded development episode as parallel S2-04 runs
    calibration-report  merge the calibration histograms of the calibration pass
    fit-elu-p           sum the ELU-P count records of the fit pass and estimate the three scalars
    train               train the VSMT-lean (or AssocOnly) heads on a pass's training records
    table               assemble the development table from the passes' episode receipts

Every run-pass names the cache's mask source (ruling 72: ``--mask-source simulator_instance_masks`` for the
main table, ``sam2`` for the robustness appendix); an episode sealed with another source fails, a resume or
a merge over receipts of two sources is refused, and the table records the one source its rows share.

Typical order (the contract's ``passes.order``):
    run-pass --pass calibration --arm LOW --config '{"d_low": null}' --calibration ...
    calibration-report --output-root <root>
        (rulings freeze the grids, the rollout_config and the development configurations)
    run-pass --pass elu_p_fit --arm TAF --config '{"theta_a": <rollout theta_a>, "d_a": null}' --elu-p-counts ...
    fit-elu-p --output-root <root>
        (the three fitted values are registered in S0-05 by ruling)
    run-pass --pass dagger_round_0 --arm ELU-P --config '<rollout_config + fitted>' ...
    train --pass dagger_round_0 --round 0 [--assoc-only] ...
    run-pass --pass dagger_round_1 --arm VSMT-lean --heads training/round0/VSMT-lean/weights.json --config '{"tau_r": ...}' ...
    run-pass --pass dagger_round_1 --arm AssocOnly --heads training/round0/AssocOnly/weights.json --config '{}' ...
    train --pass dagger_round_1 --round 1 [--assoc-only] ...
    run-pass --pass development_table --arm <TAF|RAC|LOW|VSMT-lean|NoVersion|AssocOnly> ...
    table --output-root <root>

白话：这个入口把 S2-04 的单 episode 运行铺到全部开发 episode 上：每条 episode 一个子进程、多 worker
并行、按 episode_id 升序合并、已有回执的不重跑；再把各趟的产物合起来——校准直方图合并出分位数、拟
合计数求和后估三个量、训练记录按 S1-04 留出训练头、最后从各臂的回执装开发表。它不选参、不选赢家。
"""

from __future__ import annotations

import argparse
import gzip
import json
import multiprocessing.pool
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
for item in (ROOT / "src", HERE.parent):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import lean_s2_01_runner as s2_01  # noqa: E402
import lean_s2_04_evaluate_episode as s2_04  # noqa: E402
from vsmt import lean_arms as arms  # noqa: E402
from vsmt import lean_development as dev  # noqa: E402
from vsmt import lean_evaluation as ev  # noqa: E402
from vsmt import lean_object_geometry as og  # noqa: E402
from vsmt import lean_reid_head as rh  # noqa: E402
from vsmt import lean_runner as lr  # noqa: E402

CONFIG_DIR = ROOT / "configs" / "vsmt"
S2_05_CONTRACT = CONFIG_DIR / "lean_s2_05_development_v1.json"
S0_05_CONTRACT = CONFIG_DIR / "lean_s0_arms_v2.json"
S1_02A_CONTRACT = CONFIG_DIR / "lean_s1_02a_pilot_v2.json"
S2_04_ENTRY = HERE.parent / "lean_s2_04_evaluate_episode.py"
REQUIRED_S2_05 = ("development_run", "server_run")


def _git(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=str(ROOT), text=True).strip()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl_gz(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rb") as handle:
        return [json.loads(line) for line in handle.read().decode("utf-8").splitlines() if line]


def refuse(message: str) -> int:
    print(f"[s2-05] refused: {message}", file=sys.stderr)
    return 2


def contracts_open() -> str | None:
    """Every run bit of S2-05, S2-04 and S2-01 must be open (ruling 64: the S2 stage contracts hold the run bits)."""

    contract_05 = dev.validate_development_contract(load_json(S2_05_CONTRACT))
    contract_04 = ev.validate_evaluation_contract(load_json(s2_04.S2_04_CONTRACT))
    contract_01 = lr.validate_runner_contract(load_json(s2_01.S2_01_CONTRACT))
    closed = [f"S2-05 {n}" for n in REQUIRED_S2_05 if contract_05["authorization"].get(n) is not True]
    closed += [f"S2-04 {n}" for n in s2_04.REQUIRED_S2_04 if contract_04["authorization"].get(n) is not True]
    closed += [f"S2-01 {n}" for n in s2_04.REQUIRED_S2_01 if contract_01["authorization"].get(n) is not True]
    return f"authorization bits still closed: {closed}" if closed else None


# --------------------------------------------------------------------------
# episodes and passes
# --------------------------------------------------------------------------

def plan_episodes(cache_root: Path, episode_roots: list[Path], geometry_root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Every succeeded cached episode with its S1-02 root and S1-04 geometry table; anything missing is listed, never skipped."""

    tasks: list[dict[str, Any]] = []
    missing: list[str] = []
    for cache_dir in sorted(p for p in cache_root.iterdir() if p.is_dir() and (p / "receipt.json").exists()):
        if load_json(cache_dir / "receipt.json").get("status") != "succeeded":
            continue
        episode_id = cache_dir.name
        roots = [root / episode_id for root in episode_roots if (root / episode_id / "receipt.json").exists()]
        table = geometry_root / episode_id / og.TABLE_FILE_NAME
        if len(roots) != 1 or not table.exists():
            missing.append(f"{episode_id}: roots={len(roots)} table={table.exists()}")
            continue
        tasks.append({"episode_id": episode_id, "cache_dir": str(cache_dir), "episode_root": str(roots[0])})
    return tasks, missing


def run_episode_task(task: dict[str, Any]) -> dict[str, Any]:
    """One S2-04 run as a subprocess; its receipt, or a failure receipt with the stderr tail."""

    out_dir = Path(task["output_root"]) / task["episode_id"] / task["arm"]
    command = [sys.executable, str(S2_04_ENTRY), "--cache-root", task["cache_root"], "--episode-root", task["episode_root"],
               "--geometry-root", task["geometry_root"], "--episode-id", task["episode_id"], "--arm", task["arm"],
               "--config", task["config"], "--descriptor", task["descriptor"], "--output-root", task["output_root"], "--device", task["device"],
               "--mask-source", task["mask_source"]]
    for flag, value in (("--weights", task.get("weights")), ("--heads", task.get("heads"))):
        if value:
            command += [flag, value]
    for flag in task.get("flags", []):
        command.append(flag)
    started = time.time()
    completed = subprocess.run(command, capture_output=True, text=True, cwd=str(ROOT))
    receipt_path = out_dir / "receipt.json"
    if completed.returncode == 0 and receipt_path.exists():
        receipt = load_json(receipt_path)
        receipt["episode_id"] = task["episode_id"]
        return receipt
    return {"episode_id": task["episode_id"], "arm": task["arm"], "status": "failed", "reason": "episode_failed_in_pass",
            "returncode": completed.returncode, "detail": (completed.stderr or completed.stdout)[-1500:],
            "wall_seconds": round(time.time() - started, 1)}


#: The arms each pass may run (the contract's passes block); ELU-P's table row is its round-0 pass.
PASS_ARMS = {
    "calibration": (dev.CALIBRATION_ARM_CONFIG["arm"],),  # ruling 75: TAF at the rollout theta_a
    "elu_p_fit": ("TAF",),
    "dagger_round_0": ("ELU-P",),
    "dagger_round_1": ("VSMT-lean", "AssocOnly"),
    "development_table": tuple(arm for arm in dev.DEVELOPMENT_ARMS if arm != "ELU-P"),
}


def expected_pass_config(pass_name: str, arm: str) -> dict[str, Any] | None:
    """The registered configuration a pass runs an arm at (ruling 68), or None when the pass registers none.

    白话：每一趟该用什么配置是登记好的，不由命令行临时决定：拟合趟 TAF 取 rollout 的 theta_a 且无门；
    第 0 轮 ELU-P 取 rollout_config 加 S0-05 登记的三个拟合量；第 1 轮与开发表用 S2-05 的开发配置槽。
    命令行给的配置必须与之相等，否则拒绝。
    """

    contract = dev.validate_development_contract(load_json(S2_05_CONTRACT))
    elu_p = load_json(S0_05_CONTRACT)["arms"]["ELU-P"]
    rollout = {name: elu_p["rollout_config"][name] for name in arms.ROLLOUT_CONFIG_PARAMETERS}
    if pass_name == "elu_p_fit" and arm == "TAF":
        return {"theta_a": rollout["theta_a"], "d_a": None}
    if pass_name == "dagger_round_0" and arm == "ELU-P":
        return {**rollout, arms.ROLLOUT_CONFIG_GATE_PARAMETER: None, **{name: elu_p["fitted"][name] for name in arms.ELU_P_FITTED}}
    if pass_name in ("dagger_round_1", "development_table") and arm in dev.DEVELOPMENT_CONFIGURATIONS:
        return dev.development_configuration(contract, arm)
    return None


def cmd_run_pass(args: argparse.Namespace) -> int:
    problem = contracts_open()
    if problem:
        return refuse(problem)
    if args.pass_name not in dev.PASSES:
        return refuse(f"unknown pass {args.pass_name}; the contract's order is {list(dev.PASSES)}")
    if args.arm not in PASS_ARMS[args.pass_name]:
        return refuse(f"the {args.pass_name} pass runs {list(PASS_ARMS[args.pass_name])}, not {args.arm}")
    policy, missing = s2_04.gather_teacher_policy()
    if missing:
        return refuse(f"policy values still null: {missing}")
    if not args.allow_dirty and _git("status", "--porcelain"):
        return refuse("the checkout is not clean")
    commit = _git("rev-parse", "HEAD")
    config = json.loads(args.config)
    lr.validate_arm_config(args.arm, config)
    if args.pass_name == "calibration":
        if {"arm": args.arm, "config": config} != dev.CALIBRATION_ARM_CONFIG:
            return refuse(f"the calibration pass is {dev.CALIBRATION_ARM_CONFIG}, not {args.arm} {config}")
    expected = expected_pass_config(args.pass_name, args.arm)
    if expected is not None and config != expected:
        return refuse(f"the {args.pass_name} pass runs {args.arm} at the registered configuration {expected}, not {config}")
    if args.arm in lr.LEARNED_ARMS and not args.heads:
        return refuse(f"{args.arm} needs --heads")
    cache_root = Path(args.cache_root).resolve()
    geometry_root = Path(args.geometry_root).resolve()
    episode_roots = [Path(p).resolve() for p in args.episode_roots.split(",") if p]
    tasks, missing_episodes = plan_episodes(cache_root, episode_roots, geometry_root)
    if missing_episodes:
        return refuse(f"episode_root_or_geometry_table_missing for {len(missing_episodes)} episodes: {missing_episodes[:5]}")
    if args.episodes:
        wanted = set(args.episodes.split(","))
        tasks = [t for t in tasks if t["episode_id"] in wanted]
    output_root = Path(args.output_root).resolve() / args.pass_name
    output_root.mkdir(parents=True, exist_ok=True)
    kept: list[dict[str, Any]] = []
    todo: list[dict[str, Any]] = []
    for task in tasks:
        receipt_path = output_root / task["episode_id"] / args.arm / "receipt.json"
        if receipt_path.exists() and args.resume:
            receipt = load_json(receipt_path)
            receipt["episode_id"] = task["episode_id"]
            if receipt_mask_source(receipt) != args.mask_source:  # ruling 72: one pass, one mask source
                return refuse(f"--resume with --mask-source {args.mask_source} over a receipt of {receipt_mask_source(receipt)}: {receipt_path}")
            kept.append(receipt)
            continue
        if receipt_path.parent.exists() and any(receipt_path.parent.iterdir()):
            return refuse(f"output exists and is not empty (pass --resume to keep receipts): {receipt_path.parent}")
        todo.append({**task, "arm": args.arm, "config": json.dumps(config), "descriptor": args.descriptor, "weights": args.weights,
                     "heads": args.heads, "cache_root": str(cache_root), "geometry_root": str(geometry_root), "output_root": str(output_root),
                     "mask_source": args.mask_source,
                     "device": args.device, "flags": (["--calibration"] if args.calibration else []) + (["--elu-p-counts"] if args.elu_p_counts else [])})
    actual = max(1, min(args.workers, max(1, len(todo))))
    plan = {"stage": dev.STAGE_ID, "pass": args.pass_name, "arm": args.arm, "config": config, "descriptor": args.descriptor,
            "mask_source": args.mask_source,
            "heads": args.heads, "commit": commit, "episodes_planned": [t["episode_id"] for t in tasks], "episodes_kept": [r["episode_id"] for r in kept],
            "episodes_to_run": [t["episode_id"] for t in todo], "requested_workers": args.workers, "actual_workers": actual,
            "worker_basis": args.worker_basis, "merge_order_rule": dev.MERGE_ORDER_RULE, "policy": policy,
            "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (output_root / f"plan.{args.arm}.json").write_text(json.dumps(plan, indent=1), encoding="utf-8")
    print(f"[s2-05] pass {args.pass_name} arm {args.arm}: {len(todo)} episodes to run ({len(kept)} kept), {actual} workers, commit {commit[:12]}", flush=True)
    started = time.time()
    results = list(kept)
    if actual <= 1:
        for task in todo:
            results.append(run_episode_task(task))
            print(f"[s2-05] {len(results)}/{len(tasks)} {results[-1]['episode_id']} {results[-1]['status']}", flush=True)
    else:
        with multiprocessing.pool.ThreadPool(processes=actual) as pool:  # each task is its own subprocess
            for receipt in pool.imap_unordered(run_episode_task, todo, chunksize=1):
                results.append(receipt)
                print(f"[s2-05] {len(results)}/{len(tasks)} {receipt['episode_id']} {receipt['status']}"
                      f"{(' reason=' + str(receipt.get('reason'))) if receipt['status'] != 'succeeded' else ''}", flush=True)
    results.sort(key=lambda r: r["episode_id"])
    failed = [r for r in results if r.get("status") != "succeeded"]
    pass_receipt = {**plan, "episodes_succeeded": [r["episode_id"] for r in results if r.get("status") == "succeeded"],
                    "episodes_failed": [{"episode_id": r["episode_id"], "reason": r.get("reason"), "detail": (r.get("detail") or "")[:400]} for r in failed],
                    "wall_clock_seconds": round(time.time() - started, 1)}
    (output_root / f"pass_receipt.{args.arm}.json").write_text(json.dumps(pass_receipt, indent=1), encoding="utf-8")
    print(f"[s2-05] pass {args.pass_name} arm {args.arm}: {len(results) - len(failed)} succeeded, {len(failed)} failed, {pass_receipt['wall_clock_seconds']} s")
    return 0 if not failed else 1


# --------------------------------------------------------------------------
# merges
# --------------------------------------------------------------------------

def receipt_mask_source(receipt: dict[str, Any]) -> str:
    """The mask source an S2-04 receipt ran on; receipts from before ruling 72 carry none and ran on the SAM2 cache."""

    return str(receipt.get("mask_source") or s2_04.diag.fc.MASK_SOURCE_SAM2)


def episode_dirs(pass_root: Path, arm: str) -> list[Path]:
    """The episode directories of one arm in one pass; a pass whose receipts name two mask sources is refused (ruling 72)."""

    dirs = sorted(p for p in pass_root.iterdir() if p.is_dir() and (p / arm / "receipt.json").exists())
    sources = {receipt_mask_source(load_json(d / arm / "receipt.json")) for d in dirs}
    if len(sources) > 1:
        raise SystemExit(refuse(f"{pass_root.name} {arm}: receipts on more than one mask source {sorted(sources)}"))
    return dirs


def cmd_calibration_report(args: argparse.Namespace) -> int:
    pass_root = Path(args.output_root).resolve() / "calibration"
    arm = dev.CALIBRATION_ARM_CONFIG["arm"]
    merged = dev.CalibrationCollector()
    episodes = []
    for episode_dir in episode_dirs(pass_root, arm):
        payload = episode_dir / arm / "calibration.json"
        if not payload.exists():
            return refuse(f"pass_prerequisite_missing: {payload}")
        merged.merge(dev.CalibrationCollector.from_json(load_json(payload)))
        episodes.append(episode_dir.name)
    if not episodes:
        return refuse("pass_prerequisite_missing: no calibration episode receipts")
    report = {"stage": dev.STAGE_ID, "pass": "calibration", "arm": arm, "episodes": episodes, "code_commit": _git("rev-parse", "HEAD"),
              **merged.report(), "histograms": merged.to_json()["histograms"]}
    (pass_root / "calibration_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in report["series"].items()}, indent=1))
    return 0


def rollout_config() -> tuple[dict[str, Any], list[str]]:
    section = load_json(S0_05_CONTRACT)["arms"]["ELU-P"]
    rollout = {name: section["rollout_config"][name] for name in arms.ROLLOUT_CONFIG_PARAMETERS}
    return rollout, [f"S0-05 arms.ELU-P.rollout_config.{n}" for n, v in rollout.items() if v is None]


def cmd_fit_elu_p(args: argparse.Namespace) -> int:
    rollout, missing = rollout_config()
    if missing:
        return refuse(f"policy values still null: {missing}")
    # ruling 75 (1)(a): the calibration pass runs the fit pass's arm and configuration and writes the same counts
    pass_root = Path(args.output_root).resolve() / args.from_pass
    records, episodes = [], []
    for episode_dir in episode_dirs(pass_root, "TAF"):
        payload = episode_dir / "TAF" / "elu_p_counts.json"
        if not payload.exists():
            return refuse(f"pass_prerequisite_missing: {payload}")
        records.append(load_json(payload))
        episodes.append(episode_dir.name)
    if not episodes:
        return refuse("pass_prerequisite_missing: no fit episode receipts")
    try:
        fitted = dev.fit_elu_p(records, rollout_config=rollout)
    except dev.LeanDevelopmentError as exc:
        return refuse(str(exc))
    report = {"stage": dev.STAGE_ID, "pass": "elu_p_fit", "counts_from_pass": args.from_pass, "arm_rule": dev.ELU_P_FIT_ARM_RULE, "episodes": episodes,
              "code_commit": _git("rev-parse", "HEAD"), **fitted}
    (pass_root / "elu_p_fit.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps({"values": fitted["values"], "counts": fitted["counts"]}, indent=1))
    return 0


def cmd_train(args: argparse.Namespace) -> int:
    from vsmt import lean_model

    training = load_json(S0_05_CONTRACT)["arms"]["VSMT-lean"]["training"]
    missing = [f"S0-05 arms.VSMT-lean.training.{n}" for n in ("weight_decay", "seeds") if training.get(n) is None]
    if missing:
        return refuse(f"policy values still null: {missing}")
    lean_model.recipe_matches_contract(learning_rate=training["learning_rate"], epochs=training["epochs"], seeds=training["seeds"],
                                       dagger_rounds=training["dagger_rounds"], main_table_round=training["main_table_round"])
    seed = int(training["seeds"][0])  # development training: the first registered seed
    pass_root = Path(args.output_root).resolve() / args.pass_name
    split_seed = int(load_json(S1_02A_CONTRACT)["split_freeze"]["seed"])
    dirs = episode_dirs(pass_root, args.source_arm)
    if not dirs:
        return refuse(f"pass_prerequisite_missing: no {args.source_arm} receipts under {pass_root}")
    holdout = rh.holdout_split([d.name for d in dirs], seed=split_seed)
    train_records, validation_records = [], []
    for episode_dir in dirs:
        rows = read_jsonl_gz(episode_dir / args.source_arm / "training_records.jsonl.gz")
        (train_records if episode_dir.name in holdout["training_houses"] else validation_records).extend(
            {k: v for k, v in row.items() if k != "tick"} for row in rows)
    if not validation_records:
        return refuse("pass_prerequisite_missing: no selection-house records for early stopping")
    started = time.time()
    result = lean_model.train_heads(train_records, validation_records, learning_rate=float(training["learning_rate"]),
                                    weight_decay=float(training["weight_decay"]), epochs=int(training["epochs"]), seed=seed,
                                    assoc_only=args.assoc_only, device=args.device)
    arm = "AssocOnly" if args.assoc_only else "VSMT-lean"
    out_dir = Path(args.output_root).resolve() / "training" / f"round{args.round}" / arm
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "weights.json").write_text(json.dumps(result["weights"]), encoding="utf-8")
    receipt = {"stage": dev.STAGE_ID, "round": args.round, "arm": arm, "assoc_only": args.assoc_only, "source_pass": args.pass_name,
               "source_arm": args.source_arm, "rule": dev.DEVELOPMENT_TRAINING_RULE, "seed": seed, "holdout": holdout,
               "train_frames": len(train_records), "validation_frames": len(validation_records), "train_curve": result["train_curve"],
               "validation_curve": result["validation_curve"], "best_epoch": result["best_epoch"], "diverged": result["diverged"],
               "weights_sha256": result["weights"]["sha256"], "device": args.device, "code_commit": _git("rev-parse", "HEAD"),
               "wall_seconds": round(time.time() - started, 1)}
    (out_dir / "training_receipt.json").write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    print(f"[s2-05] trained {arm} round {args.round}: best epoch {result['best_epoch']}, diverged {result['diverged']}, "
          f"weights {result['weights']['sha256'][:12]}, {receipt['wall_seconds']} s")
    return 0 if not result["diverged"] else 1


def cmd_table(args: argparse.Namespace) -> int:
    output_root = Path(args.output_root).resolve()
    source = {arm: "development_table" for arm in dev.DEVELOPMENT_ARMS}
    source["ELU-P"] = "dagger_round_0"  # the round-0 pass is ELU-P's table row (contract passes.dagger)
    reports: dict[str, dict[str, Any]] = {}
    failures: dict[str, list[dict[str, Any]]] = {}
    illegal: dict[str, int] = {}
    sources: dict[str, set[str]] = {}
    for arm, pass_name in source.items():
        pass_root = output_root / pass_name
        receipt_path = pass_root / f"pass_receipt.{arm}.json"
        if not receipt_path.exists():
            return refuse(f"pass_prerequisite_missing: {receipt_path}")
        pass_receipt = load_json(receipt_path)
        failures[arm] = pass_receipt["episodes_failed"]
        reports[arm] = {}
        illegal[arm] = 0
        for episode_dir in episode_dirs(pass_root, arm):
            receipt = load_json(episode_dir / arm / "receipt.json")
            if receipt.get("status") != "succeeded":
                continue
            reports[arm][episode_dir.name] = receipt["report"]
            illegal[arm] += int(receipt.get("illegal_programs", 0))
            sources.setdefault(receipt_mask_source(receipt), set()).add(arm)
    if len(sources) > 1:  # ruling 72: every row of one table on one frontend
        return refuse(f"the arms ran on different mask sources: { {k: sorted(v) for k, v in sources.items()} }")
    common = set.intersection(*(set(r) for r in reports.values()))
    dropped = {arm: sorted(set(r) - common) for arm, r in reports.items()}
    try:
        table = dev.development_table({arm: {h: r for h, r in rows.items() if h in common} for arm, rows in reports.items()})
    except dev.LeanDevelopmentError as exc:
        return refuse(str(exc))
    table.update({"stage": dev.STAGE_ID, "code_commit": _git("rev-parse", "HEAD"), "mask_source": next(iter(sources), None),
                  "failures_per_arm": failures,
                  "episodes_dropped_for_missing_an_arm": dropped, "illegal_programs_per_arm": illegal,
                  "interface_issues": [f"{arm}: {len(rows)} episodes failed in the pass" for arm, rows in failures.items() if rows]
                  + [f"{arm}: {n} illegal programs fell back to the empty program" for arm, n in illegal.items() if n]
                  + [f"{arm}: dropped {len(rows)} episodes missing in another arm" for arm, rows in dropped.items() if rows],
                  "continue_gate": "development readings only: no winner, no grid change, no ablation removal; design revisions by ruling before S3-01 (ruling 66)"})
    (output_root / "development_table.json").write_text(json.dumps(table, indent=1), encoding="utf-8")
    summary = {metric: {arm: table["metrics"][metric]["mean"][arm] for arm in table["arms"]} for metric in table["metrics"] if metric != "size_and_cost"}
    print(json.dumps({"houses": len(table["houses"]), "means": summary, "interface_issues": table["interface_issues"]}, indent=1))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run-pass")
    run.add_argument("--pass", dest="pass_name", required=True, choices=list(dev.PASSES))
    run.add_argument("--arm", required=True, choices=list(lr.RUNNABLE_ARMS))
    run.add_argument("--config", required=True)
    run.add_argument("--heads", default=None)
    run.add_argument("--cache-root", required=True)
    run.add_argument("--episode-roots", required=True, help="comma-separated S1-02 output roots")
    run.add_argument("--geometry-root", required=True)
    run.add_argument("--output-root", required=True)
    run.add_argument("--descriptor", required=True, choices=list(lr.DESCRIPTOR_CHOICES))
    run.add_argument("--mask-source", required=True, choices=list(s2_04.diag.fc.MASK_SOURCES),
                     help="ruling 72: the cache's mask source; every episode's seal must carry it")
    run.add_argument("--weights", default=None)
    run.add_argument("--workers", type=int, default=1)
    run.add_argument("--worker-basis", default="")
    run.add_argument("--episodes", default=None, help="comma-separated subset (trial)")
    run.add_argument("--resume", action="store_true")
    run.add_argument("--calibration", action="store_true")
    run.add_argument("--elu-p-counts", action="store_true")
    run.add_argument("--device", default="cpu")
    run.add_argument("--allow-dirty", action="store_true")
    run.set_defaults(func=cmd_run_pass)
    cal = sub.add_parser("calibration-report")
    cal.add_argument("--output-root", required=True)
    cal.set_defaults(func=cmd_calibration_report)
    fit = sub.add_parser("fit-elu-p")
    fit.add_argument("--output-root", required=True)
    fit.add_argument("--from-pass", default="elu_p_fit", choices=["elu_p_fit", "calibration"],
                     help="ruling 75: the calibration pass (TAF at the rollout theta_a) also carries the ELU-P count records")
    fit.set_defaults(func=cmd_fit_elu_p)
    train = sub.add_parser("train")
    train.add_argument("--output-root", required=True)
    train.add_argument("--pass", dest="pass_name", required=True, choices=list(dev.PASSES))
    train.add_argument("--source-arm", required=True, help="the arm whose rollouts and labels are the training records")
    train.add_argument("--round", type=int, required=True)
    train.add_argument("--assoc-only", action="store_true")
    train.add_argument("--device", default="cpu")
    train.set_defaults(func=cmd_train)
    table = sub.add_parser("table")
    table.add_argument("--output-root", required=True)
    table.set_defaults(func=cmd_table)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
