#!/usr/bin/env python3
"""S2-06 run support (ruling 100-6): input checks, stage markers, worker sizing, measured jobs, the pilot summary and the final verify.

Ruling 100-6 requires S2-06 to run as one command, every stage resumable, every input pinned, every output kept and the
digests checkable at the end. `s2_06_sam2.sh` starts each stage's computation in order; this script keeps the books:
  * check: before anything runs, verifies every input -- both caches with 39 episodes each, sealed with the right mask
    source; the geometry reloads and S1-02 episodes complete; both ReID heads at the digests S0-03 pins for their source;
    the instance-segmentation grouped heads at the frozen digests; the committed exports read side by side at the digests the
    committed readings register -- and writes them, with the code commit, thread count, cgroup quota and disk, to the run
    manifest inputs.json; lists the episodes by frame count, largest first;
  * stage-state / mark: one marker file per stage (done / hold / stopped / failed, with commit and exit code); after a commit
    change, a stage finished earlier stays valid only if every changed file is in the "SAM2 fitted-value registration and
    documents" set; otherwise resuming is refused unless the operator accepts it explicitly (recorded in the marker);
  * workers: worker counts from the cgroup CPU quota and memory and the per-job peak memory measured in the pilot;
  * run-measured: runs one command and records wall clock, exit code and the children's peak memory; pilot: summarises the
    two pilot jobs and compares them with the TAF audit time of the same episode under instance segmentation;
  * probe: compares a re-run node audit with the original one or with a merged export row;
  * verify: at the end recomputes every export's sha256, checks each training receipt's weight digest against its weights
    file, each merged audit for 39 episodes and the right source, and the determinism probe (one audit run again) against
    the original audit; writes the final run manifest.
It runs no method, reads no metric to decide anything and changes nothing outside its own files.

Usage (from the driver):
  python ops/vsmt/s2_06_manifest.py check --run-root R --repo-root W --autodl-root A ...   (see the driver)
  python ops/vsmt/s2_06_manifest.py stage-state --run-root R --stage calibration
  python ops/vsmt/s2_06_manifest.py mark --run-root R --stage calibration --status done --exit 0 --started <utc>
  python ops/vsmt/s2_06_manifest.py workers --run-root R
  python ops/vsmt/s2_06_manifest.py run-measured --out <json> -- <command ...>
  python ops/vsmt/s2_06_manifest.py pilot --run-root R --instance-audit <node_audit.json>
  python ops/vsmt/s2_06_manifest.py verify --run-root R --export-dir E --tag T
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
for item in (ROOT / "src", HERE.parent):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

STAGE = "vsmt.lean.s2_06.manifest.v1"
STAGES = ("check", "pilot", "calibration", "grid-review", "elu-p-fit", "round0", "train0", "round1", "train1",
          "audits", "instance-noversion", "merge", "reading", "verify")
STATUSES = ("done", "hold", "stopped", "failed")
SEEDS = (7, 19, 31, 43, 59)
EXPECTED_EPISODES = 39
SAM2, INSTANCE = "sam2", "simulator_instance_masks"
RULE_ARMS = ("TAF", "ELU-P", "RAC", "LOW")
#: the 19 SAM2 audit groups (ruling 100-2 step 8) and the 5 instance-segmentation NoVersion groups (step 9)
AUDIT_GROUPS = (tuple(f"VSMT-A{s}" for s in SEEDS) + tuple(f"NOVER-A{s}" for s in SEEDS) + tuple(f"ASSOC-A{s}" for s in SEEDS)
                + tuple(f"RULE-{arm}" for arm in RULE_ARMS))
INSTANCE_GROUPS = tuple(f"INSTANCE-NOVER-A{s}" for s in SEEDS)
GROUP_ARM = {**{f"VSMT-A{s}": "VSMT-lean" for s in SEEDS}, **{f"NOVER-A{s}": "NoVersion" for s in SEEDS},
             **{f"ASSOC-A{s}": "AssocOnly" for s in SEEDS}, **{f"RULE-{arm}": arm for arm in RULE_ARMS},
             **{f"INSTANCE-NOVER-A{s}": "NoVersion" for s in SEEDS}}
#: files a commit may change without invalidating a stage finished at an earlier commit: the registration of the SAM2 fitted
#: values (ruling 68 (10), ruling 100-1 (ii)) and the documents.  Anything else needs ACCEPT_CODE_CHANGE=1, recorded in the marker.
REGISTRATION_FILES = ("configs/vsmt/lean_s0_arms_v2.json", "src/vsmt/lean_arms.py", "tests/test_vsmt_lean_cross_contract.py",
                      "tests/test_vsmt_lean_arms.py", "tests/test_vsmt_lean_s2_05_entry.py")
DOCUMENT_PREFIXES = ("docs/", "results/")
DOCUMENT_FILES = ("README.md", "EXECUTE.md", "AGENTS.md")
#: keys of a node audit that change from run to run without any decision changing
VOLATILE_AUDIT_KEYS = ("wall_seconds", "code_commit", "heads")
VOLATILE_REPORT_FIELDS = ("runtime_per_frame_s", "peak_memory_bytes")  # S0-04 size_and_cost: measured, never decided on


def load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def git(*arguments: str, cwd: Path = ROOT) -> str:
    return subprocess.check_output(["git", *arguments], cwd=str(cwd), text=True).strip()


def payload_digest_ok(payload: Mapping[str, Any]) -> bool:
    """A weights payload's own digest (lean_model / lean_reid_head convention) recomputed without loading torch."""

    from cpmt.hashing import canonical_json

    body = {k: v for k, v in payload.items() if k not in ("training", "sha256")}
    return payload.get("sha256") == hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# check: every input pinned before anything runs
# --------------------------------------------------------------------------

def cache_episodes(cache_root: Path, expected_source: str) -> tuple[dict[str, int], list[str]]:
    """{episode: frames} of the succeeded episodes of one cache root, and the problems found."""

    from vsmt import lean_frontend_cache as fc

    episodes, problems = {}, []
    if not cache_root.is_dir():
        return {}, [f"cache_root_missing:{cache_root}"]
    for directory in sorted(p for p in cache_root.iterdir() if p.is_dir()):
        receipt = directory / "receipt.json"
        if not receipt.exists() or load_json(receipt).get("status") != "succeeded":
            continue
        seal_path = directory / "episode_seal.json"
        if not seal_path.exists():
            problems.append(f"episode_seal_missing:{directory.name}")
            continue
        seal = load_json(seal_path)
        source = fc.sealed_mask_source(seal)
        if source != expected_source:
            problems.append(f"episode_sealed_with_{source}:{directory.name}")
        episodes[directory.name] = int(seal["episode_frame_count"])
    if len(episodes) != EXPECTED_EPISODES:
        problems.append(f"{cache_root.name}: {len(episodes)} succeeded episodes, expected {EXPECTED_EPISODES}")
    return episodes, problems


def check_inputs(args: argparse.Namespace) -> dict[str, Any]:
    from vsmt import lean_arms as arms
    from vsmt import lean_assignment as la
    from vsmt import lean_object_geometry as og

    problems: list[str] = []
    repo = Path(args.repo_root).resolve()
    sam2, problems_sam2 = cache_episodes(Path(args.sam2_cache), SAM2)
    instance, problems_instance = cache_episodes(Path(args.instance_cache), INSTANCE)
    problems += problems_sam2 + problems_instance
    if set(sam2) != set(instance):
        problems.append(f"the two caches hold different episodes: {sorted(set(sam2) ^ set(instance))[:5]}")
    roots = [Path(p) for p in args.episode_roots.split(",") if p]
    geometry = Path(args.geometry_root)
    for episode in sorted(set(sam2) | set(instance)):
        found = [root for root in roots if (root / episode / "receipt.json").exists()]
        if len(found) != 1:
            problems.append(f"episode_root_count_{len(found)}:{episode}")
        if not (geometry / episode / og.TABLE_FILE_NAME).exists():
            problems.append(f"geometry_table_missing:{episode}")
    heads: dict[str, Any] = {}
    for source, path in ((SAM2, Path(args.sam2_reid)), (INSTANCE, Path(args.instance_reid))):
        if not path.exists():
            problems.append(f"reid_head_missing:{source}:{path}")
            continue
        payload = load_json(path)
        ok = payload.get("sha256") == la.reid_weights_sha256_for(source) and payload_digest_ok(payload)
        if not ok:
            problems.append(f"reid_head_digest_differs:{source}")
        heads[source] = {"file": str(path), "file_sha256": sha256_file(path), "payload_sha256": payload.get("sha256"),
                         "pinned_sha256": la.reid_weights_sha256_for(source), "matches": ok}
    freeze = load_json(repo / "ops" / "vsmt" / "ruling97_freeze.json")
    instance_heads = {}
    for seed, head in sorted(freeze["arms"]["VSMT-lean grouped (primary)"]["heads"].items(), key=lambda item: int(item[0])):
        path = Path(args.autodl_root) / head["path"]
        entry = {"file": str(path), "frozen_sha256": head["sha256"]}
        if not path.exists():
            problems.append(f"instance_grouped_head_missing:A{seed}")
        else:
            payload = load_json(path)
            entry["payload_sha256"] = payload.get("sha256")
            if payload.get("sha256") != head["sha256"] or not payload_digest_ok(payload):
                problems.append(f"instance_grouped_head_digest_differs:A{seed}")
        instance_heads[seed] = entry
    committed = load_json(repo / "results" / "vsmt_lean_ruling96_reading_7c76970.json")
    references = {}
    for key, spec in committed["inputs"].items():
        path = repo / "results" / spec["file"]
        digest = sha256_file(path) if path.exists() else None
        if digest != spec["sha256"]:
            problems.append(f"committed_reading_input_differs:{spec['file']}")
        references[key] = {"file": f"results/{spec['file']}", "sha256": digest}
    for name in ("vsmt_lean_s2_05_calibration_oracle_850c533.json", "vsmt_lean_ruling96_reading_7c76970.json"):
        path = repo / "results" / name
        if not path.exists():
            problems.append(f"reference_missing:{name}")
        references[name] = {"file": f"results/{name}", "sha256": sha256_file(path) if path.exists() else None}
    s0_05 = load_json(repo / "configs" / "vsmt" / "lean_s0_arms_v2.json")
    fitted = arms.elu_p_fitted(s0_05, SAM2)
    return {
        "problems": problems,
        "episodes": {SAM2: sam2, INSTANCE: instance},
        "frames": {SAM2: sum(sam2.values()), INSTANCE: sum(instance.values())},
        "reid_heads": heads,
        "instance_grouped_heads_7c76970": instance_heads,
        "references": references,
        "sam2_elu_p_fitted_registered": all(value is not None for value in fitted.values()),
        "sam2_elu_p_fitted": fitted,
    }


def resources() -> dict[str, Any]:
    def read(path: str) -> str | None:
        try:
            return Path(path).read_text(encoding="utf-8").strip()
        except OSError:
            return None

    cpu = read("/sys/fs/cgroup/cpu.max")
    quota = None
    if cpu and cpu.split()[0] != "max":
        quota = int(int(cpu.split()[0]) / int(cpu.split()[1]))
    memory = read("/sys/fs/cgroup/memory.max")
    memory_bytes = int(memory) if memory and memory != "max" else None
    if memory_bytes is None:
        for line in (read("/proc/meminfo") or "").splitlines():
            if line.startswith("MemTotal:"):
                memory_bytes = int(line.split()[1]) * 1024
    disks = {}
    for mount in ("/root/autodl-tmp", "/root"):
        if Path(mount).exists():
            usage = shutil.disk_usage(mount)
            disks[mount] = {"free_gib": round(usage.free / 2 ** 30, 1), "total_gib": round(usage.total / 2 ** 30, 1)}
    return {"cpu_quota": quota or os.cpu_count(), "cpu_quota_source": "cgroup cpu.max" if quota else "os.cpu_count",
            "memory_bytes": memory_bytes, "memory_source": "cgroup memory.max" if memory and memory != "max" else "MemTotal",
            "disks": disks}


def environment() -> dict[str, Any]:
    out: dict[str, Any] = {"python": sys.version.split()[0], "platform": platform.platform(),
                           "threads": {name: os.environ.get(name) for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                                                                              "TRAIN_THREADS")}}
    try:
        import numpy

        out["numpy"] = numpy.__version__
    except ImportError:
        out["numpy"] = None
    try:
        import torch

        out["torch"] = torch.__version__
    except ImportError:
        out["torch"] = None
    return out


def cmd_check(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root)
    run_root.mkdir(parents=True, exist_ok=True)
    result = check_inputs(args)
    commit = git("rev-parse", "HEAD", cwd=Path(args.repo_root))
    dirty = git("status", "--porcelain", cwd=Path(args.repo_root))
    if dirty:
        result["problems"].append("the worktree is not clean")
    usage = shutil.disk_usage(run_root)
    if usage.free / 2 ** 30 < args.min_free_gib:  # ruling 100-4: outputs estimated at no more than 15 GB
        result["problems"].append(f"{usage.free / 2 ** 30:.1f} GiB free under the run root, below {args.min_free_gib} GiB")
    for front, episodes in result["episodes"].items():
        lines = "".join(f"{frames}\t{episode}\n" for episode, frames in sorted(episodes.items(), key=lambda item: (-item[1], item[0])))
        (run_root / f"episodes_{front}.tsv").write_text(lines, encoding="utf-8")
    report = {"stage": STAGE, "step": "check", "checked_utc": utc_now(), "code_commit": commit, "run_root": str(run_root),
              "paths": {name: getattr(args, name) for name in ("sam2_cache", "instance_cache", "geometry_root", "episode_roots",
                                                               "sam2_reid", "instance_reid", "autodl_root")},
              "resources": resources(), "environment": environment(), **result}
    write_json(run_root / "inputs.json", report)
    print(f"[s2-06-check] {len(result['episodes'][SAM2])} SAM2 episodes ({result['frames'][SAM2]} frames), "
          f"{len(result['episodes'][INSTANCE])} instance episodes; SAM2 ELU-P fitted registered: {result['sam2_elu_p_fitted_registered']}; "
          f"problems: {result['problems'] or 'none'}")
    return 0 if not result["problems"] else 3


# --------------------------------------------------------------------------
# stage markers
# --------------------------------------------------------------------------

def marker_path(run_root: Path, stage: str) -> Path:
    if stage not in STAGES:
        raise SystemExit(f"unknown stage {stage}")
    return Path(run_root) / "stages" / f"{stage}.json"


def changed_files(since: str, head: str, repo: Path) -> list[str]:
    return [line for line in git("diff", "--name-only", since, head, cwd=repo).splitlines() if line]


def allowed_change(path: str) -> bool:
    return path in REGISTRATION_FILES or path in DOCUMENT_FILES or path.startswith(DOCUMENT_PREFIXES)


def stage_state(run_root: Path, stage: str, head: str, repo: Path, accept_code_change: bool) -> tuple[str, str]:
    """('done' | 'todo' | 'blocked', reason) for one stage at the current commit."""

    path = marker_path(run_root, stage)
    if not path.exists():
        return "todo", "no marker"
    marker = load_json(path)
    if marker.get("status") != "done":
        return "todo", f"marker status {marker.get('status')}"
    if marker.get("commit") == head:
        return "done", "same commit"
    if stage == "check":
        return "todo", "a new commit is checked again"
    changes = changed_files(marker["commit"], head, repo)
    outside = [p for p in changes if not allowed_change(p)]
    if not outside:
        return "done", f"commit changed only registration/document files: {changes}"
    if accept_code_change:
        return "done", f"code changed since {marker['commit'][:12]} and ACCEPT_CODE_CHANGE=1: {outside}"
    return "blocked", f"code changed since the stage ran at {marker['commit'][:12]}: {outside}"


def cmd_stage_state(args: argparse.Namespace) -> int:
    head = git("rev-parse", "HEAD", cwd=Path(args.repo_root))
    state, reason = stage_state(Path(args.run_root), args.stage, head, Path(args.repo_root), args.accept_code_change)
    print(f"{state}\t{reason}")
    return {"done": 0, "todo": 1, "blocked": 2}[state]


def cmd_mark(args: argparse.Namespace) -> int:
    if args.status not in STATUSES:
        raise SystemExit(f"unknown status {args.status}")
    commit = git("rev-parse", "HEAD", cwd=Path(args.repo_root))
    path = marker_path(Path(args.run_root), args.stage)
    history = []
    if path.exists():
        previous = load_json(path)
        history = previous.get("history", []) + [{k: previous.get(k) for k in ("status", "commit", "exit", "finished_utc", "detail")}]
    marker = {"stage": args.stage, "status": args.status, "commit": commit, "exit": args.exit, "started_utc": args.started,
              "finished_utc": utc_now(), "detail": args.detail, "accept_code_change": bool(args.accept_code_change),
              "history": history}
    write_json(path, marker)
    print(f"[s2-06] stage {args.stage}: {args.status} (exit {args.exit}) at {commit[:12]}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    for stage in STAGES:
        path = marker_path(Path(args.run_root), stage)
        if path.exists():
            marker = load_json(path)
            print(f"{stage:20s} {marker['status']:8s} {marker['commit'][:12]} exit {marker['exit']} {marker['finished_utc']} {marker.get('detail') or ''}")
        else:
            print(f"{stage:20s} -")
    return 0


# --------------------------------------------------------------------------
# measured jobs, worker sizing and the pilot
# --------------------------------------------------------------------------

def cmd_run_measured(args: argparse.Namespace) -> int:
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    started = time.time()
    completed = subprocess.run(command)
    try:  # the largest descendant waited for (Linux reports KiB); unavailable on Windows
        import resource

        peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * 1024
    except ImportError:
        peak = None
    write_json(Path(args.out), {"command": command, "exit": completed.returncode, "wall_seconds": round(time.time() - started, 1),
                                "max_rss_children_bytes": peak, "finished_utc": utc_now()})
    return completed.returncode


def plan_workers(cpu_quota: int, memory_bytes: int, *, audit_gib: float, train_gib: float, train_threads: int,
                 reserve_gib: float = 8.0) -> dict[str, Any]:
    """Worker counts from the cgroup quota and memory: audits and passes are single-threaded processes, trainings use train_threads."""

    memory_gib = memory_bytes / 2 ** 30
    usable = max(1.0, memory_gib - reserve_gib)
    workers = max(1, min(cpu_quota - 4, int(usable // audit_gib)))
    train_parallel = max(1, min(2 * len(SEEDS), int(usable // train_gib), max(1, cpu_quota // train_threads)))
    return {"workers": workers, "pass_workers": min(EXPECTED_EPISODES, workers), "train_parallel": train_parallel,
            "audit_gib": audit_gib, "train_gib": train_gib, "train_threads": train_threads, "cpu_quota": cpu_quota,
            "memory_gib": round(memory_gib, 1), "reserve_gib": reserve_gib,
            "basis": ("audits and passes: one single-threaded process each, at most cpu_quota - 4 and (memory - reserve) / audit_gib; "
                      "trainings: train_threads threads each, at most (memory - reserve) / train_gib, cpu_quota / train_threads and 10")}


def measured_gib(path: Path, default: float) -> tuple[float, str]:
    if path.exists():
        peak = load_json(path).get("max_rss_children_bytes") or 0
        if peak > 0:
            return max(1.0, math.ceil(1.25 * peak / 2 ** 30 * 2) / 2), f"1.25 x the measured peak of {path.name}"
    return default, "default (no measurement yet)"


def cmd_workers(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root)
    info = resources()
    audit_gib, audit_basis = max((measured_gib(run_root / "pilot" / f"{name}_job.json", args.audit_gib) for name in ("calibration", "audit")),
                                 key=lambda item: item[0])
    train_gib, train_basis = max((measured_gib(run_root / "training" / "round0" / arm / "measured.json", args.train_gib)
                                  for arm in ("VSMT-lean", "AssocOnly")), key=lambda item: item[0])
    plan = plan_workers(int(args.cpu_quota or info["cpu_quota"]), int(args.memory_bytes or info["memory_bytes"]),
                        audit_gib=audit_gib, train_gib=train_gib, train_threads=args.train_threads)
    if args.workers:
        plan["workers"] = int(args.workers)
        plan["pass_workers"] = min(EXPECTED_EPISODES, int(args.workers))
        plan["override"] = "WORKERS set by the operator"
    plan.update({"audit_gib_basis": audit_basis, "train_gib_basis": train_basis})
    write_json(run_root / "workers.json", plan)
    print(f"{plan['workers']} {plan['pass_workers']} {plan['train_parallel']}")
    return 0


def cmd_pilot(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root)
    pilot = run_root / "pilot"
    largest = (run_root / f"episodes_{SAM2}.tsv").read_text(encoding="utf-8").splitlines()[0].split("\t")
    frames, episode = int(largest[0]), largest[1]
    jobs = {name: load_json(pilot / f"{name}_job.json") for name in ("calibration", "audit")}
    out: dict[str, Any] = {"stage": STAGE, "step": "pilot", "episode": episode, "frames": frames, "jobs": {}}
    for name, job in jobs.items():
        out["jobs"][name] = {**job, "seconds_per_frame": round(job["wall_seconds"] / frames, 3),
                             "peak_gib": round(job["max_rss_children_bytes"] / 2 ** 30, 2) if job["max_rss_children_bytes"] else None}
    reference = Path(args.instance_audit) if args.instance_audit else None
    if reference is not None and reference.exists():
        instance = load_json(reference)
        out["instance_segmentation_same_episode_taf_audit"] = {"file": str(reference), "wall_seconds": instance.get("wall_seconds"),
                                                               "frames": instance.get("frames"), "code_commit": instance.get("code_commit")}
        if instance.get("wall_seconds"):
            out["sam2_over_instance_audit_time"] = round(jobs["audit"]["wall_seconds"] / float(instance["wall_seconds"]), 2)
    else:
        out["instance_segmentation_same_episode_taf_audit"] = None
        out["sam2_over_instance_audit_time"] = None
    inputs = load_json(run_root / "inputs.json")
    out["sam2_frames_total"] = inputs["frames"][SAM2]
    out["note"] = ("timing of one largest episode only; the per-frame cost grows with the memory size, the learned arms and the trainings "
                   "are not timed here; the operator turns this into the total estimate reported to the user")
    write_json(pilot / "pilot.json", out)
    print(json.dumps({k: out[k] for k in ("episode", "frames", "sam2_over_instance_audit_time")}
                     | {name: {"wall_seconds": job["wall_seconds"], "peak_gib": job["peak_gib"]} for name, job in out["jobs"].items()}))
    return 0 if all(job["exit"] == 0 for job in jobs.values()) else 1


# --------------------------------------------------------------------------
# verify: every recorded digest checked at the end
# --------------------------------------------------------------------------

def comparable_audit(payload: Mapping[str, Any]) -> dict[str, Any]:
    """A node audit without the fields that change between identical runs (wall time, commit, file paths, timings)."""

    out = {k: v for k, v in payload.items() if k not in VOLATILE_AUDIT_KEYS}
    report = dict(out.get("report") or {})
    if "size_and_cost" in report:
        report["size_and_cost"] = {k: v for k, v in report["size_and_cost"].items() if k not in VOLATILE_REPORT_FIELDS}
    out["report"] = report
    return out


def comparable_report(report: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in report.items() if k != "size_and_cost"}


def verify(run_root: Path, export_dir: Path, tag: str, repo: Path) -> dict[str, Any]:
    problems: list[str] = []
    stages = {stage: (load_json(marker_path(run_root, stage)) if marker_path(run_root, stage).exists() else None) for stage in STAGES}
    for stage in STAGES[:-1]:
        if not stages[stage] or stages[stage]["status"] != "done":
            problems.append(f"stage_not_done:{stage}")
    exports = sorted(p for p in export_dir.glob(f"*_{tag}.json") if not p.name.startswith(("vsmt_lean_s2_06_manifest_", "vsmt_lean_s2_06_verify_")))
    files = {p.name: {"sha256": sha256_file(p), "bytes": p.stat().st_size} for p in exports}
    trainings = {}
    for receipt_path in sorted((run_root / "training").glob("round*/*/**/training_receipt.json")):
        receipt = load_json(receipt_path)
        directory = receipt_path.parent
        entry = {"receipt": str(receipt_path), "weights_sha256": receipt["weights_sha256"], "best_epoch": receipt["best_epoch"],
                 "code_commit": receipt["code_commit"], "has_per_epoch_terms": bool(receipt.get("validation_curve_terms"))}
        payload = load_json(directory / "weights.json")
        if payload.get("sha256") != receipt["weights_sha256"] or not payload_digest_ok(payload):
            problems.append(f"weights_differ_from_the_receipt:{directory.relative_to(run_root).as_posix()}")
        grouped = receipt.get("group_selection")
        if grouped:
            payload = load_json(directory / "weights_grouped.json")
            entry["grouped_weights_sha256"] = grouped["weights_sha256"]
            if payload.get("sha256") != grouped["weights_sha256"] or not payload_digest_ok(payload):
                problems.append(f"grouped_weights_differ_from_the_receipt:{directory.relative_to(run_root).as_posix()}")
        if not entry["has_per_epoch_terms"]:
            problems.append(f"training_without_per_epoch_terms:{directory.relative_to(run_root).as_posix()}")
        trainings[str(directory.relative_to(run_root).as_posix())] = entry
    if len(trainings) != 2 + 2 * len(SEEDS):
        problems.append(f"trainings_found_{len(trainings)}_expected_{2 + 2 * len(SEEDS)}")
    merges = {}
    for group in AUDIT_GROUPS + INSTANCE_GROUPS:
        path = export_dir / f"vsmt_lean_s2_06_audit_{group}_{tag}.json"
        if not path.exists():
            problems.append(f"merged_audit_missing:{group}")
            continue
        merged = load_json(path)
        source = INSTANCE if group.startswith("INSTANCE-") else SAM2
        if merged.get("mask_source") != source or merged.get("episodes") != EXPECTED_EPISODES or merged.get("arm") != GROUP_ARM[group]:
            problems.append(f"merged_audit_inconsistent:{group}")
        merges[group] = {"episodes": merged.get("episodes"), "mask_source": merged.get("mask_source"), "code_commits": merged.get("code_commits")}
    probes = {}
    for name in ("sam2", "instance"):
        path = run_root / "verify" / f"probe_{name}.json"
        if path.exists():
            probes[name] = load_json(path)
            if not probes[name].get("identical"):
                problems.append(f"determinism_probe_differs:{name}")
        else:
            problems.append(f"determinism_probe_missing:{name}")
    return {"problems": problems, "stages": stages, "exports": files, "trainings": trainings, "merged_audits": merges, "probes": probes}


def cmd_probe(args: argparse.Namespace) -> int:
    """Compare a re-run node audit with the original one (identical apart from the volatile fields), or with a merged export row."""

    rerun = load_json(Path(args.rerun))
    if args.original:
        identical = comparable_audit(load_json(Path(args.original))) == comparable_audit(rerun)
        against = args.original
    else:
        merged = load_json(Path(args.merged))
        rows = [row for row in merged["per_episode"] if row["episode_id"] == rerun["episode_id"]]
        identical = len(rows) == 1 and comparable_report(rows[0]["report"]) == comparable_report(rerun["report"])
        against = args.merged
    write_json(Path(args.out), {"rerun": args.rerun, "against": against, "episode_id": rerun["episode_id"], "identical": identical,
                                "compared": "everything but wall time, commit, head path and timings" if args.original
                                else "the seven-metric report but size and cost", "checked_utc": utc_now()})
    print(f"[s2-06-probe] {rerun['episode_id']}: identical={identical}")
    return 0 if identical else 3


def cmd_verify(args: argparse.Namespace) -> int:
    run_root, export_dir = Path(args.run_root), Path(args.export_dir)
    result = verify(run_root, export_dir, args.tag, Path(args.repo_root))
    inputs = load_json(run_root / "inputs.json")
    manifest = {"stage": STAGE, "step": "manifest", "tag": args.tag, "written_utc": utc_now(),
                "code_commit": git("rev-parse", "HEAD", cwd=Path(args.repo_root)),
                "stage_commits": {stage: (marker or {}).get("commit") for stage, marker in result["stages"].items()},
                "inputs": inputs, "workers": load_json(run_root / "workers.json") if (run_root / "workers.json").exists() else None,
                "exports": result["exports"], "trainings": result["trainings"], "merged_audits": result["merged_audits"],
                "probes": result["probes"], "problems": result["problems"],
                "reproduction": ("bash ops/vsmt/s2_06_sam2.sh all at the recorded commits reproduces every export; trainings are bit-identical at "
                                 "the same commit and TRAIN_THREADS (ruling 96), audits are deterministic (the probes), README 'How to reproduce S2-06'")}
    write_json(export_dir / f"vsmt_lean_s2_06_manifest_{args.tag}.json", manifest)
    write_json(export_dir / f"vsmt_lean_s2_06_verify_{args.tag}.json",
               {"stage": STAGE, "step": "verify", "problems": result["problems"], "exports_checked": len(result["exports"]),
                "trainings_checked": len(result["trainings"]), "merged_audits_checked": len(result["merged_audits"]),
                "probes": result["probes"], "manifest_sha256": sha256_file(export_dir / f"vsmt_lean_s2_06_manifest_{args.tag}.json")})
    print(f"[s2-06-verify] {len(result['exports'])} exports, {len(result['trainings'])} trainings, {len(result['merged_audits'])} merged audits; "
          f"problems: {result['problems'] or 'none'}")
    return 0 if not result["problems"] else 3


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    for name in ("run-root", "repo-root", "autodl-root", "sam2-cache", "instance-cache", "geometry-root", "episode-roots", "sam2-reid", "instance-reid"):
        check.add_argument(f"--{name}", required=True)
    check.add_argument("--min-free-gib", type=float, default=20.0)
    check.set_defaults(func=cmd_check)
    state = sub.add_parser("stage-state")
    state.add_argument("--run-root", required=True)
    state.add_argument("--repo-root", default=str(ROOT))
    state.add_argument("--stage", required=True, choices=STAGES)
    state.add_argument("--accept-code-change", action="store_true")
    state.set_defaults(func=cmd_stage_state)
    mark = sub.add_parser("mark")
    mark.add_argument("--run-root", required=True)
    mark.add_argument("--repo-root", default=str(ROOT))
    mark.add_argument("--stage", required=True, choices=STAGES)
    mark.add_argument("--status", required=True, choices=STATUSES)
    mark.add_argument("--exit", type=int, required=True)
    mark.add_argument("--started", required=True)
    mark.add_argument("--detail", default="")
    mark.add_argument("--accept-code-change", action="store_true")
    mark.set_defaults(func=cmd_mark)
    status = sub.add_parser("status")
    status.add_argument("--run-root", required=True)
    status.set_defaults(func=cmd_status)
    workers = sub.add_parser("workers")
    workers.add_argument("--run-root", required=True)
    workers.add_argument("--train-threads", type=int, default=4)
    workers.add_argument("--audit-gib", type=float, default=4.0)
    workers.add_argument("--train-gib", type=float, default=24.0)
    workers.add_argument("--workers", default=None)
    workers.add_argument("--cpu-quota", default=None)
    workers.add_argument("--memory-bytes", default=None)
    workers.set_defaults(func=cmd_workers)
    measured = sub.add_parser("run-measured")
    measured.add_argument("--out", required=True)
    measured.add_argument("command", nargs=argparse.REMAINDER)
    measured.set_defaults(func=cmd_run_measured)
    pilot = sub.add_parser("pilot")
    pilot.add_argument("--run-root", required=True)
    pilot.add_argument("--instance-audit", default=None)
    pilot.set_defaults(func=cmd_pilot)
    probe = sub.add_parser("probe")
    probe.add_argument("--rerun", required=True)
    probe.add_argument("--original", default=None)
    probe.add_argument("--merged", default=None)
    probe.add_argument("--out", required=True)
    probe.set_defaults(func=cmd_probe)
    ver = sub.add_parser("verify")
    ver.add_argument("--run-root", required=True)
    ver.add_argument("--repo-root", default=str(ROOT))
    ver.add_argument("--export-dir", required=True)
    ver.add_argument("--tag", required=True)
    ver.set_defaults(func=cmd_verify)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
