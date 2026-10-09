"""Re-run the frozen evaluation audits from the released data (level L1) and compare them with the paper's audits.

    python reproduce/l1_eval.py --data-root PATH --front sam2|instance --scope probe|test
                                [--runs VSMT-lean:7,AssocOnly:7,...] [--episodes N] [--workers N]
                                [--acknowledge-post-publication-reread]

The audits run the frozen audit entry (``ops/vsmt/lean_s2_05_node_audit.py run --metrics-only``) in a temporary clean
worktree of the S3-05 run commit ``8d58475`` (its ``src/``, ``ops/`` and ``configs/`` equal the freeze ``dea8c20``),
with the configurations, heads and ReID head the S3-04 freeze receipt fixed, one single-threaded process per audit as in
S3-03 to S3-05.  Data: Hugging Face T0 (weights, freeze directory) and T1 restored under ``--data-root`` with
``ops/vsmt/hf_fetch.py``; ``python reproduce/check_env.py --level L1`` lists what is missing.

Scopes:

- ``probe``: the S3-04 determinism probe -- every frozen run on the two validation episodes the receipt names; each
  audit is compared field by field with the probe audit released in T0.  No test data is read.
- ``test``: every frozen run on every usable test episode; each audit's metrics are compared with the per-episode values
  of ``results/vsmt_lean_s3_05_merged_<front>_8d58475.json``.  The test split was read once for the paper (S3-05); a
  re-run reproduces that read with nothing left to choose, but it is a further read of test.  It therefore requires
  ``--acknowledge-post-publication-reread``, writes ``REPRODUCTION_READ.json`` (time, commit, receipt digest, purpose)
  into its own output directory before reading anything, never writes into the test roots, and exports only the
  comparison, not new statistics.  The paper's statistics are recomputed from the committed audits by
  ``reproduce/paper.py``.

Bit identity is expected only on the hardware and library versions of the original run (Linux, Intel Xeon with
AVX-512, torch 2.8.0, numpy 2.3.2); elsewhere a few near-tie decisions can differ (docs/REPRODUCE.md, section 1), so
the report separates metric differences from differences in the error decomposition and the seal chain.  The
instance-mask ReID head is not released; ``--front instance`` needs it under ``--data-root`` at its server path.

Outputs (``outputs/reproduce/l1-<front>-<scope>-<time>/``, not tracked): the audits, ``comparison.json`` and, for test,
``REPRODUCTION_READ.json``.  Exit codes: 0 all audits ran and every metric equals the paper's; 3 a difference or a
failed audit; 2 a precondition is missing.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import functools
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (REPO_ROOT, REPORT_DIR, S3_05_RUN_COMMIT, Refusal, git, load_json, resolve,  # noqa: E402
                     worktree)

RECEIPT = REPO_ROOT / "results" / "vsmt_lean_s3_04_freeze_dea8c20.json"
SERVER_ROOT = "/root/autodl-tmp/"
TAG = "3f6ef1d"
MASK_SOURCES = {"instance": "simulator_instance_masks", "sam2": "sam2"}
REID_HEADS = {"instance": "vsmt_private/lean-s1-04-diagnostics-oracle-caa50c7/reid_head_vitb14.json",
              "sam2": "vsmt_private/exports/reid_head_vitb14_154776d.json"}
THREAD_VARIABLES = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS")
#: Audit fields that may differ between two runs of the same audit (wall time, commit, head path, mode keys).
VOLATILE = ("wall_seconds", "code_commit", "heads", "audit", "metrics_only")


def run_label(run: dict[str, Any]) -> str:
    """The run's name in the S3-03 to S3-05 outputs, e.g. ``VSMT-lean-c02-s7``."""

    return f"{run['arm']}-c{int(run['config_index']):02d}" + ("" if run["seed"] is None else f"-s{run['seed']}")


def heads_file(receipt: dict[str, Any], front: str, run: dict[str, Any], root: Path) -> Path | None:
    if run["heads_arm"] is None:
        return None
    pairs = receipt["frozen_bytes"]["heads"]
    pairs = pairs.items() if isinstance(pairs, dict) else pairs
    marker = f"/{front}/training/round1/{run['heads_arm']}/s{run['seed']}/"
    paths = [path for path, _ in pairs if marker in path]
    if len(paths) != 1:
        raise Refusal(f"the freeze receipt names no single head file for {run_label(run)}")
    return root / paths[0][len(SERVER_ROOT):]


def comparable(audit: dict[str, Any]) -> dict[str, Any]:
    out = {key: value for key, value in audit.items() if key not in VOLATILE}
    report = dict(out.get("report") or {})
    report["size_and_cost"] = {k: v for k, v in (report.get("size_and_cost") or {}).items()
                               if k not in ("runtime_per_frame_s", "peak_memory_bytes")}
    out["report"] = report
    return out


def classify(mine: dict[str, Any], theirs: dict[str, Any]) -> dict[str, Any]:
    """Which parts of two audits of the same run differ: the metrics, or only the decomposition and seal chain.

    Only the fields both records carry are compared (a merged test record keeps a subset of the audit's fields)."""

    left, right = comparable(mine), comparable(theirs)
    differing = sorted(key for key in set(left) & set(right) if left[key] != right[key])
    metrics = {k: v for k, v in (left.get("report") or {}).items() if k != "size_and_cost"}
    reference = {k: v for k, v in (right.get("report") or {}).items() if k != "size_and_cost"}
    return {"identical": not differing, "metrics_equal": metrics == reference, "differing_fields": differing}


def task_list(args: argparse.Namespace, receipt: dict[str, Any], tree: Path, out: Path) -> list[dict[str, Any]]:
    front, root = args.front, args.data_root
    split = "validation" if args.scope == "probe" else "test"
    runs = receipt["fronts"][front]["test_runs"]
    if args.runs:
        wanted = {name.strip() for name in args.runs.split(",")}
        runs = [run for run in runs if f"{run['arm']}:{run['seed']}" in wanted or run["arm"] in wanted]
    if args.scope == "probe":
        episodes = list(receipt["fronts"][front]["probe_episodes"])
    else:
        episodes = sorted({row["episode_id"] for group in merged_test_audits(front).values() if isinstance(group, dict)
                           for row in group.get("per_episode", [])})
    episodes = episodes[: args.episodes] if args.episodes else episodes
    reid = root / REID_HEADS[front]
    if not reid.exists():
        raise Refusal(f"ReID head missing: {reid}" + (" (the instance-mask head is not released on Hugging Face)"
                                                     if front == "instance" else ""))
    tasks = []
    for run in runs:
        heads = heads_file(receipt, front, run, root)
        if heads is not None and not heads.exists():
            raise Refusal(f"heads missing: {heads} (restore weights/{front}/ from T0)")
        for episode in episodes:
            argv = [sys.executable, "ops/vsmt/lean_s2_05_node_audit.py", "run",
                    "--cache-root", str(root / f"vsmt_caches/s3-02-{front}-{TAG}/{split}"),
                    "--episode-root", str(root / f"vsmt_outputs/s3-02-{TAG}/{split}/{episode}"),
                    "--geometry-root", str(root / f"vsmt_private/s3-02-geometry-{TAG}/{split}"),
                    "--episode-id", episode, "--arm", run["arm"], "--config", json.dumps(run["config"]),
                    "--descriptor", "reid_projection:vitb14", "--weights", str(reid), "--mask-source", MASK_SOURCES[front],
                    "--output-root", str(out / "audits" / run_label(run)), "--metrics-only", "--manifest-split", split]
            if heads is not None:
                argv += ["--heads", str(heads)]
            if args.scope == "test":
                argv += ["--test-receipt", str(root / "vsmt_private/s3-04-dea8c20/freeze_receipt.json")]
            tasks.append({"run": run_label(run), "arm": run["arm"], "episode": episode, "argv": argv, "cwd": str(tree),
                          "audit": str(out / "audits" / run_label(run) / episode / run["arm"] / "node_audit.json"),
                          "log": str(out / "logs" / f"{run_label(run)}-{episode}.log")})
    return tasks


def run_task(task: dict[str, Any]) -> dict[str, Any]:
    Path(task["log"]).parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, **{name: "1" for name in THREAD_VARIABLES}, "PYTHONUTF8": "1"}
    started = time.time()
    with open(task["log"], "wb") as handle:
        code = subprocess.run(task["argv"], cwd=task["cwd"], env=env, stdout=handle, stderr=subprocess.STDOUT).returncode
    return {"run": task["run"], "arm": task["arm"], "episode": task["episode"], "exit": code, "seconds": round(time.time() - started, 1),
            "audit": task["audit"], "log": task["log"]}


@functools.lru_cache(maxsize=2)
def merged_test_audits(front: str) -> dict[str, Any]:
    return load_json(REPO_ROOT / "results" / f"vsmt_lean_s3_05_merged_{front}_{S3_05_RUN_COMMIT}.json")


def reference(args: argparse.Namespace, row: dict[str, Any]) -> dict[str, Any] | None:
    """The paper's audit of the same run and episode: the S3-04 probe audit (T0) or the S3-05 per-episode record."""

    if args.scope == "probe":
        path = (args.data_root / f"vsmt_private/s3-04-dea8c20/{args.front}/probe/{row['run']}/{row['episode']}"
                / row["arm"] / "node_audit.json")
        return load_json(path) if path.exists() else None
    group = merged_test_audits(args.front).get(row["run"]) or {}
    return next((entry for entry in group.get("per_episode", []) if entry["episode_id"] == row["episode"]), None)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data-root", type=Path, required=True, help="the --dest given to ops/vsmt/hf_fetch.py")
    parser.add_argument("--front", choices=tuple(MASK_SOURCES), default="sam2")
    parser.add_argument("--scope", choices=("probe", "test"), default="probe")
    parser.add_argument("--runs", default=None, help="comma-separated arm:seed or arm names (default: all 25 frozen runs)")
    parser.add_argument("--episodes", type=int, default=None, help="only the first N episodes of the scope")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--acknowledge-post-publication-reread", action="store_true",
                        help="required for --scope test: this run is a further read of the test split")
    args = parser.parse_args(argv)
    stamp = time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime())
    out = REPORT_DIR / f"l1-{args.front}-{args.scope}-{stamp}"
    try:
        if args.scope == "test" and not args.acknowledge_post_publication_reread:
            raise Refusal("--scope test re-reads the test split, which the paper read once; add "
                          "--acknowledge-post-publication-reread to confirm a post-publication reproduction")
        commit = resolve(S3_05_RUN_COMMIT)
        receipt = load_json(RECEIPT)
        out.mkdir(parents=True, exist_ok=False)
        if args.scope == "test":
            (out / "REPRODUCTION_READ.json").write_text(json.dumps({
                "purpose": "post-publication reproduction of the S3-05 test audits with the frozen receipt; nothing is "
                           "selected or tuned; the paper's single pre-registered read is S3-05 (EXECUTE LOG-306)",
                "started_utc": stamp, "code_commit": commit, "receipt_sha256": receipt["receipt_sha256"],
                "front": args.front, "host": platform.node(), "platform": platform.platform(),
                "test_roots_written": False}, indent=1), encoding="utf-8")
        with worktree(commit) as tree:
            tasks = task_list(args, receipt, tree, out)
            print(f"[l1] {len(tasks)} audits ({args.front}, {args.scope}) on {min(args.workers, len(tasks))} workers; "
                  f"code {commit[:12]}; output {out}", flush=True)
            with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(args.workers, len(tasks)))) as pool:
                rows = list(pool.map(run_task, tasks))
    except Refusal as exc:
        print(f"[l1] refused: {exc}", file=sys.stderr)
        return 2
    problems = []
    for row in rows:
        theirs = reference(args, row)
        if row["exit"] != 0 or not Path(row["audit"]).exists():
            row["result"] = "audit failed (see log)"
            problems.append(f"{row['run']} {row['episode']}: exit {row['exit']}")
        elif theirs is None:
            row["result"] = "no reference audit"
            problems.append(f"{row['run']} {row['episode']}: no reference")
        else:
            row.update(classify(load_json(Path(row["audit"])), theirs))
            row["result"] = "identical" if row["identical"] else ("metrics equal" if row["metrics_equal"] else "metrics differ")
            if not row["metrics_equal"]:
                problems.append(f"{row['run']} {row['episode']}: metrics differ")
    summary = {"front": args.front, "scope": args.scope, "code_commit": commit, "receipt_sha256": receipt["receipt_sha256"],
               "python": sys.version.split()[0], "platform": platform.platform(), "rows": rows, "problems": problems,
               "counts": {result: sum(r["result"] == result for r in rows) for result in {r["result"] for r in rows}}}
    (out / "comparison.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(f"[l1] {summary['counts']}; comparison: {out / 'comparison.json'}")
    return 3 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
