#!/usr/bin/env python3
"""S3-05 (ruling 107, 2026-10-05: 「待裁 107 全按推荐」): the one test run -- the steps of ``ops/vsmt/s3_05_test.sh``.

白话：S3-05 用 S3-04 冻结回执钉住的代码、配置与权重，把 test 读一次、跑一次。每一步写本次的运行根 ``$AUTODL/vsmt_private/s3-05-run``：
  * ``check``：``lean_s3_04.verify_freeze`` 对照回执（代码、权重、ELU-P 登记值、test 清单）；回执已提交在 ``results/`` 且与服务器上的
    逐字节相同（106-5）；用户放行的口令 ``S3_05_GO`` 等于回执摘要前 12 位；
  * ``unseal``：S3-02 封印的摘要等于回执所记，``lean_test_seal.open_roots`` 逐项核对封印后把四个 test 根打开为第 1 次读取并写读取
    记录（续跑是同一次读取）；随后才看 test 根的目录结构，定下每套前端可用的 test episode（清单 ∩ 生成成功 ∩ 几何表 ∩ 该前端 cache
    成功），写 ``inputs.json``；
  * ``run``：作业池（复用 S3-03 的 ``s3_03_jobs``）：每个作业是一条 test episode 上回执里的一个运行（node audit 只算指标，
    ``--manifest-split test --test-receipt``）；崩溃同输入自动重跑一次，仍失败记为数据失败、照记、不停整趟（107-2）；准入过的工作机
    （kinds 含 test）可以分担；运行中不打印、不导出任何指标（107-5）；
  * ``merge``、``stats``：每个运行合并成一份；全部作业结束之后一次性按 107-4 算统计（``lean_s3_05``）；
  * ``export``、``verify``：导出 ``vsmt_lean_s3_05_*_<tag>.json`` 与运行清单。
输入是冻结回执、S3-03 运行根（权重）与四个 test 根；输出是两张主表、比较、固定顺序判定与逐例失败。例如回执提交之后有人改了
``src/`` 里一个文件，check 报出 ``code_changed:...`` 并以 3 停下，test 根保持封存。它不选参、不训练，也不会第二次解封。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
for item in (ROOT / "src", HERE.parent):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import s3_03_jobs as pool  # noqa: E402
import s3_03_manifest as s303  # noqa: E402
from vsmt import lean_arms as arms  # noqa: E402
from vsmt import lean_s3_03 as s3  # noqa: E402
from vsmt import lean_s3_04 as s4  # noqa: E402
from vsmt import lean_s3_05 as s5  # noqa: E402
from vsmt import lean_teacher as lt  # noqa: E402
from vsmt import lean_test_seal  # noqa: E402

STAGE = "vsmt.lean.s3_05.driver.v1"
NODE_AUDIT = HERE.parent / "lean_s2_05_node_audit.py"
REMOTE_SCRIPT = HERE.parent / "remote_hosts.py"
JOBS_SCRIPT = HERE.parent / "s3_03_jobs.py"
S0_05_CONTRACT = ROOT / "configs" / "vsmt" / "lean_s0_arms_v2.json"
#: one test audit holds about 0.85 (learned) to 1.85 GiB (rule arms) in S3-03; reserved at 2 GiB
MEMORY_GIB = {"audit": 2.0, "small": 0.5}
PRIORITY = {"learned": 2, "rule": 3}
#: Ruling 107-2: a crash reruns once with the same frozen inputs; a second failure is a data failure, recorded, the run goes on.
AUDIT_RETRIES = 1

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


def step_path(run_root: Path, name: str) -> Path:
    return run_root / f"{name}.json"


def finish(run_root: Path, name: str, payload: dict[str, Any]) -> int:
    payload = {"stage": STAGE, "step": name, "code_commit": git("rev-parse", "HEAD"), "written_utc": utc_now(), **payload}
    payload["pass"] = not payload.get("problems")
    write_json(step_path(run_root, name), payload)
    print(f"[s3-05-{name}] pass={payload['pass']}; problems: {payload.get('problems')[:6] if payload.get('problems') else 'none'}")
    return 0 if payload["pass"] else 3


def passed(run_root: Path, name: str) -> bool:
    path = step_path(run_root, name)
    return path.exists() and bool(load_json(path).get("pass")) and load_json(path).get("code_commit") == git("rev-parse", "HEAD")


def receipt_of(args: argparse.Namespace) -> dict[str, Any]:
    return load_json(Path(args.receipt))


def tracked_code_files() -> list[str]:
    return [name for name in git("ls-files", *s4.CODE_DIRECTORIES).splitlines() if name]


# --------------------------------------------------------------------------
# check (ruling 107-1)
# --------------------------------------------------------------------------

def cmd_check(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root)
    lean_test_seal.refuse_sealed([run_root, Path(args.s3_03_run_root)], reader="s3-05 check")  # never under a test root
    receipt = receipt_of(args)
    contract = load_json(S0_05_CONTRACT)
    heads = {path: s4.file_sha256(Path(path)) if Path(path).exists() else None for path in receipt["frozen_bytes"]["heads"]}
    problems = s4.verify_freeze(
        receipt, code=s4.code_digest(ROOT, tracked_code_files()), heads=heads,
        registered_values={front: arms.elu_p_fitted(contract, s4.FRONTS[front]) for front in receipt["frozen_bytes"]["elu_p_registered"]},
        test_manifest_sha256=s4.test_manifest_sha256(s3.load_manifest()))
    tag = receipt["freeze_commit"][:7]
    committed = f"results/vsmt_lean_s3_04_freeze_{tag}.json"  # ruling 106-5: published before test is read
    try:
        published = json.loads(git("show", f"HEAD:{committed}"))
        if s4.canonical_sha256(published) != s4.canonical_sha256(receipt):  # the same receipt, whatever line endings Git stored
            problems.append(f"committed_receipt_differs:{committed}")
    except (subprocess.CalledProcessError, ValueError):
        problems.append(f"receipt_not_committed:{committed}")
    go = os.environ.get("S3_05_GO", "")
    if go != receipt["receipt_sha256"][:12]:
        problems.append("s3_05_go_missing_or_wrong (ruling 107-1: S3_05_GO must equal the first 12 characters of the receipt digest)")
    return finish(run_root, "check", {"receipt": {"path": args.receipt, "receipt_sha256": receipt["receipt_sha256"],
                                                  "freeze_commit": receipt["freeze_commit"], "committed_as": committed},
                                      "problems": problems})


# --------------------------------------------------------------------------
# unseal (ruling 107-1) and the usable test episodes
# --------------------------------------------------------------------------

def seal_body(args: argparse.Namespace, receipt: Mapping[str, Any]) -> tuple[dict[str, Any], Path]:
    path = Path(args.export_dir) / f"vsmt_lean_s3_02_test_seal_{args.s3_02_tag}.json"
    seal = load_json(path)
    body = {key: value for key, value in seal.items() if key != "seal_sha256"}
    _require(lean_test_seal.seal_sha256(body) == seal.get("seal_sha256") == receipt["frozen_bytes"]["test_seal_sha256"],
             "test_seal_differs_from_the_freeze_receipt")
    return body, path


def usable_episodes(body: Mapping[str, Any], fronts: Sequence[str]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """After opening: per front end the test episodes with a succeeded raw episode, a geometry table and a succeeded cache."""

    from vsmt import lean_object_geometry as og
    import s3_02_manifest as s3_02

    houses = [str(h) for h in s3.load_manifest()["test"]]
    raw = set(body["kinds"]["raw"]["succeeded"])
    geometry_root = Path(body["kinds"]["geometry"]["root"])
    geometry = {h for h in houses if (geometry_root / h / og.TABLE_FILE_NAME).exists()}
    out, counts = {}, {"manifest_houses": len(houses), "raw_succeeded": len(raw), "geometry_tables": len(geometry)}
    for front in fronts:
        kind = f"{front}_cache"
        cache_root = Path(body["kinds"][kind]["root"])
        receipts = s3_02.receipts(cache_root)
        cache_ok = set(body["kinds"][kind]["succeeded"])
        usable = [h for h in houses if h in raw and h in geometry and h in cache_ok]
        out[front] = [{"episode_id": h, "frames": int(receipts.get(h, {}).get("frames") or 1)} for h in usable]
        counts[f"usable_{front}"] = len(usable)
    return out, counts


def cmd_unseal(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root)
    _require(passed(run_root, "check"), "unseal_needs_a_passed_check_at_this_commit")
    receipt = receipt_of(args)
    # opening is irreversible: only for the very receipt check verified, and only if its body still has its digest
    _require(load_json(step_path(run_root, "check"))["receipt"]["receipt_sha256"] == receipt["receipt_sha256"]
             == s4.receipt_body_sha256(receipt), "unseal_receipt_is_not_the_checked_one")
    body, seal_path = seal_body(args, receipt)
    record = lean_test_seal.open_roots(body, receipt_sha256=receipt["receipt_sha256"], commit=git("rev-parse", "HEAD"),
                                       purpose="S3-05 run of record (ruling 107)")
    fronts = [front for front in s4.FRONTS if front in receipt["fronts"]]
    episodes, counts = usable_episodes(body, fronts)
    s3_03 = s303.load_context(Path(args.s3_03_run_root))
    inputs = {"stage": STAGE, "written_utc": utc_now(), "code_commit": git("rev-parse", "HEAD"), "fronts": fronts,
              "receipt": {"path": str(Path(args.receipt).resolve()), "receipt_sha256": receipt["receipt_sha256"]},
              "receipt_sha256": receipt["receipt_sha256"], "s3_03_run_root": str(Path(args.s3_03_run_root).resolve()),
              "seal": {"file": str(seal_path.resolve()), "sha256": receipt["frozen_bytes"]["test_seal_sha256"]},
              "roots": {"raw": {"test": body["kinds"]["raw"]["root"]}, "geometry": {"test": body["kinds"]["geometry"]["root"]},
                        "cache": {front: {"test": body["kinds"][f"{front}_cache"]["root"]} for front in fronts}},
              "reid": {front: {"file": str(s3_03.inputs["reid"][front]["file"])} for front in fronts},
              "episodes": {front: {"test": rows} for front, rows in episodes.items()}, "counts": counts,
              "read_record": {key: record[key] for key in ("reading", "opened_utc", "commit", "receipt_sha256", "resumed")}}
    write_json(run_root / "inputs.json", inputs)
    return finish(run_root, "unseal", {"read_record": inputs["read_record"], "counts": counts, "problems": []})


# --------------------------------------------------------------------------
# the job graph and the pool (ruling 107-2)
# --------------------------------------------------------------------------

def group_root(run_root: Path, front: str, run: Mapping[str, Any]) -> Path:
    return run_root / front / "audit" / s303.group_name(run["arm"], int(run["config_index"]), run["seed"])


def merged_path(run_root: Path, front: str, run: Mapping[str, Any]) -> Path:
    return run_root / front / "merged" / f"{s303.group_name(run['arm'], int(run['config_index']), run['seed'])}.json"


def audit_argv(inputs: Mapping[str, Any], front: str, run: Mapping[str, Any], episode: str, run_root: Path,
               heads: Path | None) -> list[str]:
    cache = inputs["roots"]["cache"][front]["test"]
    entries = [{"config": dict(run["config"]), "output_root": str(group_root(run_root, front, run))}]
    return [sys.executable, str(NODE_AUDIT), "run", "--cache-root", cache, "--episode-root", str(Path(inputs["roots"]["raw"]["test"]) / episode),
            "--geometry-root", inputs["roots"]["geometry"]["test"], "--episode-id", episode, "--arm", run["arm"],
            "--descriptor", s303.s3_descriptor(), "--weights", inputs["reid"][front]["file"], "--mask-source", s4.FRONTS[front],
            "--device", "cpu", "--metrics-only", "--manifest-split", "test", "--test-receipt", inputs["receipt"]["path"],
            "--skip-existing", "--configs", json.dumps(entries), *(["--heads", str(heads)] if heads is not None else [])]


def build_jobs(run_root: Path, inputs: Mapping[str, Any], receipt: Mapping[str, Any]) -> list[pool.Job]:
    s3_03 = s303.load_context(Path(inputs["s3_03_run_root"]))
    frozen = receipt["frozen_bytes"]["heads"]
    jobs = []
    for front in inputs["fronts"]:
        _require(str(inputs["reid"][front]["file"]) in frozen, f"reid_head_not_frozen:{front}")
        frames = {row["episode_id"]: int(row["frames"]) for row in inputs["episodes"][front]["test"]}
        for run in receipt["fronts"][front]["test_runs"]:
            heads = s3_03.heads_file(front, 1, run["heads_arm"], run["seed"]) if run["seed"] is not None else None
            _require(heads is None or str(heads) in frozen, f"heads_not_frozen_by_the_receipt:{heads}")  # the S3-03 root S3-04 froze
            seeded = run["seed"] is not None
            for episode in frames:
                job_id = f"{front}/test/{run['arm']}/{'rule' if not seeded else 's%d' % run['seed']}/{episode}"

                def build(f: str = front, r: Mapping[str, Any] = run, e: str = episode, h: Path | None = heads) -> list[str]:
                    return audit_argv(inputs, f, r, e, run_root, h)

                # exit 2 is a refusal (a guard, a checkout, a configuration): systemic, never a data failure -- it stops the run
                jobs.append(pool.Job(job_id, "test", (), PRIORITY["learned" if seeded else "rule"], float(frames[episode]), 1, "audit",
                                     build, keep_partial=True, retries=AUDIT_RETRIES, stops_on_failure=False,
                                     exit_status={2: "gate_failed"},
                                     remote_push=tuple(str(p) for p in ((heads,) if heads is not None else ()) + (Path(inputs["receipt"]["path"]),)),
                                     remote_pull=(str(group_root(run_root, front, run) / episode),), group=front))
    return jobs


def cmd_run(args: argparse.Namespace) -> int:
    import remote_hosts

    run_root = Path(args.run_root)
    _require(passed(run_root, "unseal"), "run_needs_the_unseal_step_at_this_commit")
    inputs, receipt = load_json(run_root / "inputs.json"), receipt_of(args)
    _require(inputs["receipt_sha256"] == receipt["receipt_sha256"], "inputs_of_another_receipt")
    info = s303.resources()
    cores = int(args.budget_cores or info["cpu_quota"]) - pool.RESERVE_CORES
    gib = int(info["memory_bytes"]) / 2 ** 30 - pool.RESERVE_GIB
    jobs = build_jobs(run_root, inputs, receipt)
    write_json(run_root / "workers.json", {"budget_cores": cores, "budget_gib": round(gib, 1), "resources": info, "jobs": len(jobs),
                                           "memory_gib": MEMORY_GIB, "written_utc": utc_now(),
                                           "rule": "ruling 104-3 / 107-2: cgroup cores less 2 and memory less 8 GiB; single-threaded audits"})
    runner = pool.Pool(jobs, run_root=run_root, log_dir=Path(args.log_dir), budget_cores=cores, budget_gib=gib, memory_defaults=MEMORY_GIB,
                       train_threads=lambda: 1, commit=git("rev-parse", "HEAD"), poll_seconds=args.poll_seconds, disk_root=run_root,
                       min_free_gib=args.min_free_gib, memory_limit_bytes=int(info["memory_bytes"]) - int(pool.RESERVE_GIB * 2 ** 30),
                       wrapper=[sys.executable, str(JOBS_SCRIPT), "run-measured"], memory_fixed=MEMORY_GIB, group_order=inputs["fronts"],
                       hosts=lambda: remote_hosts.load_hosts(run_root), remote_runner=[sys.executable, str(REMOTE_SCRIPT), "remote-run"],
                       suspend_host=lambda name, reason: remote_hosts.suspend(run_root, name, reason))
    print(f"[s3-05-run] {len(jobs)} test audits, {cores} cores, {round(gib, 1)} GiB (no metric is printed before every audit ended)", flush=True)
    code = runner.run()
    print(f"[s3-05-run] finished: {runner.stop_reason or 'all jobs ended'}")
    return code


def job_states(run_root: Path) -> dict[str, dict[str, Any]]:
    return {load_json(p)["job_id"]: load_json(p) for p in sorted((run_root / "jobs").glob("*.json")) if not p.name.endswith(".rss.json")}


def cmd_merge(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root)
    inputs, receipt = load_json(run_root / "inputs.json"), receipt_of(args)
    states = job_states(run_root)
    graph = build_jobs(run_root, inputs, receipt)
    not_ended = [job.job_id for job in graph if states.get(job.job_id, {}).get("status") not in ("done", "failed")]
    problems = [f"jobs_not_ended:{len(not_ended)}:{not_ended[:5]}"] if not_ended else []
    rows: list[dict[str, Any]] = []
    if not problems:
        for front in inputs["fronts"]:
            for run in receipt["fronts"][front]["test_runs"]:
                target = merged_path(run_root, front, run)
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    target.unlink()  # never a merge of an earlier attempt
                audits = list(group_root(run_root, front, run).glob(f"*/{run['arm']}/*.json"))
                done = subprocess.run([sys.executable, str(NODE_AUDIT), "merge", "--output-root", str(group_root(run_root, front, run)),
                                       "--arm", run["arm"], "--results", str(target)], capture_output=True, text=True)
                rows.append({"front": front, "group": target.stem, "exit": done.returncode, "merged": target.exists(), "audits": len(audits)})
                if audits and (done.returncode != 0 or not target.exists()):  # nothing to merge only when every episode failed
                    problems.append(f"merge_failed:{front}:{target.stem}:exit{done.returncode}:{(done.stderr or '').strip()[-160:]}")
    return finish(run_root, "merge", {"groups": rows, "problems": problems})


def cmd_stats(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root)
    _require(passed(run_root, "merge"), "stats_need_the_merge_step")
    inputs, receipt = load_json(run_root / "inputs.json"), receipt_of(args)
    seed, iterations = receipt["statistics"]["bootstrap_seed"], receipt["statistics"]["bootstrap_iterations"]
    per_front, failures = {}, {}
    for front in inputs["fronts"]:
        episodes = [row["episode_id"] for row in inputs["episodes"][front]["test"]]
        runs = []
        for run in receipt["fronts"][front]["test_runs"]:
            path = merged_path(run_root, front, run)
            rows = {row["episode_id"]: row for row in load_json(path)["per_episode"]} if path.exists() else {}
            runs.append({"arm": run["arm"], "seed": run["seed"], "rows": rows})
        tables, missing = s5.tables(runs, episodes)
        per_front[front] = {**s5.front_statistics(tables, runs, seed=seed, iterations=iterations), "episodes": len(episodes),
                            "failures": missing}
        failures[front] = missing
    result = s5.test_statistics(per_front)
    write_json(run_root / "statistics.json", {**result, "receipt_sha256": receipt["receipt_sha256"], "written_utc": utc_now()})
    print(f"[s3-05-stats] written {run_root / 'statistics.json'}; failures {[len(v) for v in failures.values()]}")
    return finish(run_root, "stats", {"failures": failures, "problems": []})


def cmd_export(args: argparse.Namespace) -> int:
    run_root, export_dir = Path(args.run_root), Path(args.export_dir)
    _require(passed(run_root, "stats"), "export_needs_the_stats_step")
    tag = git("rev-parse", "HEAD")[:7]
    inputs = load_json(run_root / "inputs.json")
    states = job_states(run_root)
    by_status: dict[str, int] = {}
    for state in states.values():
        by_status[state["status"]] = by_status.get(state["status"], 0) + 1
    exports = {f"vsmt_lean_s3_05_statistics_{tag}.json": load_json(run_root / "statistics.json"),
               f"vsmt_lean_s3_05_inputs_{tag}.json": inputs,
               f"vsmt_lean_s3_05_check_{tag}.json": load_json(step_path(run_root, "check")),
               f"vsmt_lean_s3_05_jobs_{tag}.json": {"by_status": by_status, "failed": sorted(k for k, s in states.items() if s["status"] == "failed"),
                                                    "hosts": sorted({s.get("host") or "local" for s in states.values()})}}
    for front in inputs["fronts"]:
        for path in sorted((run_root / front / "merged").glob("*.json")):
            exports.setdefault(f"vsmt_lean_s3_05_merged_{front}_{tag}.json", {})[path.stem] = load_json(path)
    for name, payload in exports.items():
        write_json(export_dir / name, payload)
    manifest = {"stage": STAGE, "tag": tag, "written_utc": utc_now(), "receipt_sha256": inputs["receipt_sha256"],
                "exports": {name: {"sha256": s4.file_sha256(export_dir / name), "bytes": (export_dir / name).stat().st_size} for name in sorted(exports)},
                "read_record": inputs["read_record"]}
    write_json(export_dir / f"vsmt_lean_s3_05_manifest_{tag}.json", manifest)
    return finish(run_root, "export", {"exports": sorted(exports), "problems": []})


def cmd_status(args: argparse.Namespace) -> int:
    """Ruling 107-5: counts only, never a metric."""

    run_root = Path(args.run_root)
    by_status: dict[str, int] = {}
    for state in job_states(run_root).values() if (run_root / "jobs").exists() else ():
        by_status[state["status"]] = by_status.get(state["status"], 0) + 1
    steps = {p.stem: load_json(p).get("pass") for p in sorted(run_root.glob("*.json")) if p.stem in ("check", "unseal", "merge", "stats", "export")}
    print(json.dumps({"steps": steps, "jobs_by_status": by_status}, indent=1))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="step", required=True)
    for name, func in (("check", cmd_check), ("unseal", cmd_unseal), ("run", cmd_run), ("merge", cmd_merge), ("stats", cmd_stats),
                       ("export", cmd_export), ("status", cmd_status)):
        command = sub.add_parser(name)
        command.add_argument("--run-root", required=True)
        if name != "status":
            command.add_argument("--receipt", required=True)
            command.add_argument("--s3-03-run-root", required=True)
            command.add_argument("--export-dir", required=True)
            command.add_argument("--s3-02-tag", default="3f6ef1d")
        if name == "run":
            command.add_argument("--log-dir", required=True)
            command.add_argument("--budget-cores", type=int, default=None)
            command.add_argument("--poll-seconds", type=float, default=2.0)
            command.add_argument("--min-free-gib", type=float, default=20.0)
        command.set_defaults(func=func)
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (DriverError, s4.LeanS3_04Error, s5.LeanS3_05Error, s303.DriverError, pool.PoolError, lean_test_seal.LeanTestSealError,
            lt.LeanTeacherError) as exc:
        print(f"[s3-05] refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
