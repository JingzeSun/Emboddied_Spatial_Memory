"""Run the nonformal M1 trainability ladder on train/validation only."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

import numpy as np
import torch

from cpmt.dev_learning import METHODS
from cpmt.m1_protocol import load_and_validate, protocol_sha256
from cpmt.m1_trainability import (
    error_decomposition,
    resolve_trainability_ladder,
)


def write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hash_matches(path: Path, expected: str | None) -> bool:
    """Accept exact source bytes or a pure CRLF/LF checkout conversion."""
    if expected is None:
        return False
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() == expected:
        return True
    lf = raw.replace(b"\r\n", b"\n")
    crlf = lf.replace(b"\n", b"\r\n")
    return expected in {
        hashlib.sha256(lf).hexdigest(),
        hashlib.sha256(crlf).hexdigest(),
    }


def git_output(*args: str) -> str:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={PROJECT.parents[1].as_posix()}", *args],
        cwd=PROJECT, capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def build_sharded_split(
    hard_config, hard_config_path: Path, split: str, paired_groups: int,
    future_hash_bins: int, shard_root: Path, *, keep_paired_groups: int,
    max_attempts: int = 10,
):
    """Generate each paired group in a restartable isolated Python process."""
    array_parts = []
    kept_audits = []
    digest = hashlib.sha256()
    summaries = []
    attempt_log = []
    total_decisions = covered = illegal_reference = 0
    family_totals = {}
    family_covered = {}
    candidate_count_min = None
    candidate_count_max = None
    candidate_generators = set()
    shard_root.mkdir(parents=True, exist_ok=True)
    worker = PROJECT / "scripts" / "generate_m1_trainability_shard.py"
    for group_index in range(paired_groups):
        completed = None
        prefix = f"{split}_{group_index:06d}_attempt"
        existing_attempts = []
        for path in shard_root.glob(f"{prefix}*"):
            suffix = path.name.removeprefix(prefix)
            if path.is_dir() and suffix.isdigit():
                existing_attempts.append((int(suffix), path))
        existing_attempts.sort(key=lambda item: item[0])
        for attempt, attempt_dir in existing_attempts:
            complete_path = attempt_dir / "complete.json"
            if complete_path.is_file():
                completed = attempt_dir
                attempt_log.append({
                    "split": split,
                    "group_index": group_index,
                    "attempt": attempt,
                    "returncode": 0,
                    "stdout": "",
                    "stderr": "",
                    "output": str(attempt_dir.relative_to(shard_root.parent)),
                    "reused_complete_attempt": True,
                })
                break
        next_attempt = (
            max((attempt for attempt, _ in existing_attempts), default=0) + 1
        )
        for attempt in range(next_attempt, next_attempt + max_attempts):
            if completed is not None:
                break
            attempt_dir = shard_root / (
                f"{split}_{group_index:06d}_attempt{attempt}"
            )
            command = [
                sys.executable, "-B", str(worker),
                "--hard-config", str(hard_config_path),
                "--split", split,
                "--group-index", str(group_index),
                "--future-hash-bins", str(future_hash_bins),
                "--output", str(attempt_dir),
            ]
            result = subprocess.run(
                command, cwd=PROJECT, capture_output=True, text=True,
            )
            record = {
                "split": split,
                "group_index": group_index,
                "attempt": attempt,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "output": str(attempt_dir.relative_to(shard_root.parent)),
            }
            attempt_log.append(record)
            complete_path = attempt_dir / "complete.json"
            if result.returncode == 0 and complete_path.is_file():
                completed = attempt_dir
                break
            print(
                f"{split} shard={group_index + 1}/{paired_groups} "
                f"attempt={attempt} failed returncode={result.returncode}",
                flush=True,
            )
        if completed is None:
            raise RuntimeError(
                f"{split} group {group_index} failed all {max_attempts} isolated attempts"
            )
        completed_attempt = int(completed.name.removeprefix(prefix))
        with np.load(completed / "arrays.npz", allow_pickle=False) as stored:
            arrays = {key: stored[key].copy() for key in stored.files}
        summary = json.loads(
            (completed / "summary.json").read_text(encoding="utf-8")
        )
        array_parts.append(arrays)
        summaries.append(summary)
        group_candidate = summary["candidate_audit"]
        decisions = int(group_candidate["decisions"])
        total_decisions += decisions
        covered += int(round(
            group_candidate["candidate_reference_coverage"] * decisions
        ))
        illegal_reference += int(round(
            group_candidate["illegal_reference_rate"] * decisions
        ))
        for family, support in group_candidate["support_by_family"].items():
            family_totals[family] = family_totals.get(family, 0) + int(support)
            family_covered[family] = family_covered.get(family, 0) + int(round(
                float(group_candidate["coverage_by_family"][family]) * int(support)
            ))
        low = int(group_candidate["candidate_count_min"])
        high = int(group_candidate["candidate_count_max"])
        candidate_count_min = low if candidate_count_min is None else min(
            candidate_count_min, low,
        )
        candidate_count_max = high if candidate_count_max is None else max(
            candidate_count_max, high,
        )
        candidate_generators.update(group_candidate["candidate_generators"])
        digest.update(summary["audit_sha256"].encode("utf-8"))
        digest.update(b"\n")
        if group_index < keep_paired_groups:
            with (completed / "audit_sequences.jsonl").open(
                "r", encoding="utf-8"
            ) as handle:
                kept_audits.extend(json.loads(line) for line in handle if line.strip())
        print(
            f"{split} shard={group_index + 1}/{paired_groups} "
            f"cases={len(arrays['y'])} attempt={completed_attempt}",
            flush=True,
        )
    combined = {
        key: np.concatenate([part[key] for part in array_parts], axis=0)
        for key in array_parts[0]
    }
    first = summaries[0]
    summary = {
        "status": "sharded_paired_rollout_interface_validation_only",
        "split": split,
        "paired_groups": paired_groups,
        "siblings_per_group": 2,
        "sequences": paired_groups * 2,
        "decisions": int(len(combined["y"])),
        "horizon_decisions": first["horizon_decisions"],
        "template_counts_per_primary_sequence": first[
            "template_counts_per_primary_sequence"
        ],
        "exact_ambiguous_decision_pairs": paired_groups,
        "distinct_topology_and_order_signatures": len({
            (
                item["place_count_range"][0],
                item["surface_count_range"][0],
                item["initial_node_count_range"][0],
            )
            for item in summaries
        }),
        "place_count_range": [
            min(item["place_count_range"][0] for item in summaries),
            max(item["place_count_range"][1] for item in summaries),
        ],
        "surface_count_range": [
            min(item["surface_count_range"][0] for item in summaries),
            max(item["surface_count_range"][1] for item in summaries),
        ],
        "initial_node_count_range": [
            min(item["initial_node_count_range"][0] for item in summaries),
            max(item["initial_node_count_range"][1] for item in summaries),
        ],
        "candidate_set_size": int(summaries[0]["candidate_set_size"]),
        "test_generated": False,
        "formal_data_ready": False,
        "paired_latent_siblings_ready": True,
        "front_end": "controlled_structural_token_projector_not_pno",
        "learning_cases": int(len(combined["y"])),
        "online_feature_dim": int(combined["x"].shape[1]),
        "future_target_dim": int(combined["future"].shape[1]),
        "labelled_fraction": float(combined["labelled"].mean()),
        "ambiguous_decision_fraction": float(combined["ambiguous"].mean()),
        "generation_mode": "one_paired_group_per_shard",
        "shard_attempts": attempt_log,
    }
    family_coverage = {
        family: float(family_covered.get(family, 0) / support)
        for family, support in sorted(family_totals.items())
    }
    candidate_audit = {
        "decisions": float(total_decisions),
        "candidate_reference_coverage": float(covered / total_decisions),
        "candidate_miss_rate": float(1.0 - covered / total_decisions),
        "illegal_reference_rate": float(illegal_reference / total_decisions),
        "coverage_by_family": family_coverage,
        "support_by_family": dict(sorted(family_totals.items())),
        "minimum_family_coverage": min(family_coverage.values()),
        "candidate_count_min": candidate_count_min,
        "candidate_count_max": candidate_count_max,
        "candidate_generators": sorted(candidate_generators),
    }
    return combined, kept_audits, summary, digest.hexdigest(), candidate_audit


def run_isolated_point(
    run_root: Path, name: str, mode: str, train_paired_groups: int,
    student_steps: int, seed: int, *, max_attempts: int = 10,
):
    """Run one training/evaluation point in a restartable short process."""
    worker = PROJECT / "scripts" / "run_m1_trainability_point.py"
    point_root = run_root / "points"
    point_root.mkdir(parents=True, exist_ok=True)
    attempts = []
    prefix = f"{name}_attempt"
    existing_attempts = []
    for path in point_root.glob(f"{prefix}*"):
        suffix = path.name.removeprefix(prefix)
        if path.is_dir() and suffix.isdigit():
            existing_attempts.append((int(suffix), path))
    existing_attempts.sort(key=lambda item: item[0])
    for attempt, attempt_dir in existing_attempts:
        if (attempt_dir / "complete.json").is_file():
            result = json.loads(
                (attempt_dir / "result.json").read_text(encoding="utf-8")
            )
            attempts.append({
                "name": name,
                "attempt": attempt,
                "returncode": 0,
                "stdout": "",
                "stderr": "",
                "output": str(attempt_dir.relative_to(run_root)),
                "reused_complete_attempt": True,
            })
            return result, attempts
    next_attempt = max(
        (attempt for attempt, _ in existing_attempts), default=0,
    ) + 1
    for attempt in range(next_attempt, next_attempt + max_attempts):
        attempt_dir = point_root / f"{name}_attempt{attempt}"
        command = [
            sys.executable, "-B", str(worker),
            "--run-root", str(run_root),
            "--mode", mode,
            "--train-paired-groups", str(train_paired_groups),
            "--student-steps", str(student_steps),
            "--seed", str(seed),
            "--output", str(attempt_dir),
        ]
        completed = subprocess.run(
            command, cwd=PROJECT, capture_output=True, text=True,
        )
        record = {
            "name": name,
            "attempt": attempt,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "output": str(attempt_dir.relative_to(run_root)),
        }
        attempts.append(record)
        if completed.returncode == 0 and (attempt_dir / "complete.json").is_file():
            result = json.loads(
                (attempt_dir / "result.json").read_text(encoding="utf-8")
            )
            return result, attempts
        print(
            f"point={name} attempt={attempt} failed "
            f"returncode={completed.returncode}",
            flush=True,
        )
    raise RuntimeError(f"trainability point {name} failed all isolated attempts")


def run_isolated_method_point(
    run_root: Path, name: str, method: str, train_paired_groups: int,
    student_steps: int, seed: int, *, max_attempts: int = 10,
):
    """Run and persist one A-F method without sharing a failure domain."""
    worker = PROJECT / "scripts" / "run_m1_trainability_method.py"
    point_root = run_root / "points"
    point_root.mkdir(parents=True, exist_ok=True)
    attempts = []
    prefix = f"{name}_{method}_attempt"
    existing_attempts = []
    for path in point_root.glob(f"{prefix}*"):
        suffix = path.name.removeprefix(prefix)
        if path.is_dir() and suffix.isdigit():
            existing_attempts.append((int(suffix), path))
    existing_attempts.sort(key=lambda item: item[0])
    for attempt, attempt_dir in existing_attempts:
        if (attempt_dir / "complete.json").is_file():
            result = json.loads(
                (attempt_dir / "result.json").read_text(encoding="utf-8")
            )
            attempts.append({
                "name": name,
                "method": method,
                "attempt": attempt,
                "returncode": 0,
                "stdout": "",
                "stderr": "",
                "output": str(attempt_dir.relative_to(run_root)),
                "reused_complete_attempt": True,
            })
            return result, attempts
    next_attempt = max(
        (attempt for attempt, _ in existing_attempts), default=0,
    ) + 1
    for attempt in range(next_attempt, next_attempt + max_attempts):
        attempt_dir = point_root / f"{name}_{method}_attempt{attempt}"
        command = [
            sys.executable, "-B", str(worker),
            "--run-root", str(run_root),
            "--method", method,
            "--train-paired-groups", str(train_paired_groups),
            "--student-steps", str(student_steps),
            "--seed", str(seed),
            "--output", str(attempt_dir),
        ]
        completed = subprocess.run(
            command, cwd=PROJECT, capture_output=True, text=True,
        )
        record = {
            "name": name,
            "method": method,
            "attempt": attempt,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "output": str(attempt_dir.relative_to(run_root)),
        }
        attempts.append(record)
        if completed.returncode == 0 and (attempt_dir / "complete.json").is_file():
            result = json.loads(
                (attempt_dir / "result.json").read_text(encoding="utf-8")
            )
            return result, attempts
        print(
            f"point={name} method={method} attempt={attempt} failed "
            f"returncode={completed.returncode}",
            flush=True,
        )
    raise RuntimeError(
        f"trainability point {name} method {method} failed all isolated attempts"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hard-config", type=Path,
        default=PROJECT / "configs" / "m1_hard_condition.json",
    )
    parser.add_argument(
        "--af-config", type=Path,
        default=PROJECT / "configs" / "m1_af_smoke.json",
    )
    parser.add_argument(
        "--ladder-config", type=Path,
        default=PROJECT / "configs" / "m1_trainability_ladder.json",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--resume-output", type=Path,
        help=(
            "Resume an existing failed/interrupted run using only shard or point "
            "directories that contain complete.json."
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.output is not None and args.resume_output is not None:
        raise ValueError("--output and --resume-output are mutually exclusive")

    hard_config = load_and_validate(args.hard_config)
    af_raw = json.loads(args.af_config.read_text(encoding="utf-8"))
    ladder_raw = json.loads(args.ladder_config.read_text(encoding="utf-8"))
    ladder = resolve_trainability_ladder(hard_config, af_raw, ladder_raw)
    base = ladder["base_af_config"]
    preview = {
        "protocol": ladder["protocol"],
        "formal_run": False,
        "test_access": False,
        "seed": ladder["seed"],
        "max_train_paired_groups": ladder["max_train_paired_groups"],
        "validation_paired_groups": ladder["validation_paired_groups"],
        "optimization_curve": ladder["optimization_curve"],
        "label_rich_capacity": ladder["label_rich_capacity"],
        "candidate_count": int(hard_config["candidates"]["budget_k"]),
        "frozen_candidate_budget": hard_config["candidates"]["budget_k"],
        "device": base["device"],
    }
    print(json.dumps(preview, ensure_ascii=False), flush=True)
    if args.dry_run:
        return

    device = torch.device(base["device"])
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("configured CUDA is unavailable; use CPU for this diagnostic")
    started = datetime.now(timezone.utc)
    previous_manifest = None
    if args.resume_output is not None:
        output = args.resume_output.resolve()
        if not output.is_dir() or not (output / "manifest.json").is_file():
            raise ValueError("--resume-output must contain an existing manifest.json")
        previous_manifest = json.loads(
            (output / "manifest.json").read_text(encoding="utf-8")
        )
        run_id = str(previous_manifest["run_id"])
    else:
        run_id = started.strftime("m1-trainability-%Y%m%dT%H%M%S%fZ")
        output = (
            args.output or PROJECT / "outputs" / "m1_trainability" / run_id
        ).resolve()
    if not output.is_relative_to((PROJECT / "outputs").resolve()):
        raise ValueError("output must be inside project outputs")
    if previous_manifest is None:
        output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "schema_version": "cpmt-0.2",
        "run_id": run_id,
        "stage": "M1",
        "method": "trainability_ladder_with_fixed_K16_not_formal_gate",
        "status": "running",
        "code": {
            "commit": git_output("rev-parse", "HEAD"),
            "dirty": bool(git_output("status", "--porcelain")),
            "source_sha256": {
                "trainability": sha256(PROJECT / "src" / "cpmt" / "m1_trainability.py"),
                "af_adapter": sha256(PROJECT / "src" / "cpmt" / "m1_af_rollout.py"),
                "rollout_generator": sha256(PROJECT / "src" / "cpmt" / "m1_rollout.py"),
                "learning": sha256(PROJECT / "src" / "cpmt" / "dev_learning.py"),
                "executor": sha256(PROJECT / "src" / "cpmt" / "executor.py"),
                "shard_worker": sha256(
                    PROJECT / "scripts" / "generate_m1_trainability_shard.py"
                ),
                "point_worker": sha256(
                    PROJECT / "scripts" / "run_m1_trainability_point.py"
                ),
                "method_adapter": sha256(
                    PROJECT / "src" / "cpmt" / "m1_af_method.py"
                ),
                "method_point_worker": sha256(
                    PROJECT / "scripts" / "run_m1_trainability_method.py"
                ),
                "runner": sha256(Path(__file__)),
            },
        },
        "data": {
            "dataset_version": hard_config["data"]["dataset_version"],
            "manifest_hash": "pending",
            "split": "validation",
            "test_generated": False,
            "formal_data_ready": False,
            "candidate_count": int(hard_config["candidates"]["budget_k"]),
        },
        "config": {
            "path": "m1_trainability_ladder.json",
            "hash": sha256(args.ladder_config),
            "af_config_path": "m1_af_smoke.json",
            "af_config_hash": sha256(args.af_config),
            "hard_config_path": "m1_hard_condition.json",
            "hard_config_hash": sha256(args.hard_config),
            "canonical_protocol_sha256": protocol_sha256(hard_config),
        },
        "seed": int(ladder["seed"]),
        "front_end": {
            "backbone_id": "shared-analytic-online-vector-v1",
            "depth_id": "not-applicable-m1-controlled",
            "pose_source": "actual-executed-reference-sequence",
        },
        "future_use_policy": "hindsight_train_only",
        "decision_refs": ["D-030", "D-031"],
        "timing": {"started_at": started.isoformat()},
        "failures": (
            list(previous_manifest.get("failures", []))
            if previous_manifest is not None else []
        ),
        "metrics_ref": "metrics.json",
        "hardware": str(device),
    }
    if previous_manifest is not None:
        previous_sources = previous_manifest.get("code", {}).get(
            "source_sha256", {},
        )
        scientific_sources = {
            "trainability", "af_adapter", "rollout_generator", "learning",
            "executor", "shard_worker", "point_worker",
        }
        for name in ("method_adapter", "method_point_worker"):
            if name in previous_sources:
                scientific_sources.add(name)
        source_paths = {
            "trainability": PROJECT / "src" / "cpmt" / "m1_trainability.py",
            "af_adapter": PROJECT / "src" / "cpmt" / "m1_af_rollout.py",
            "rollout_generator": PROJECT / "src" / "cpmt" / "m1_rollout.py",
            "learning": PROJECT / "src" / "cpmt" / "dev_learning.py",
            "executor": PROJECT / "src" / "cpmt" / "executor.py",
            "shard_worker": PROJECT / "scripts" / "generate_m1_trainability_shard.py",
            "point_worker": PROJECT / "scripts" / "run_m1_trainability_point.py",
            "method_adapter": PROJECT / "src" / "cpmt" / "m1_af_method.py",
            "method_point_worker": (
                PROJECT / "scripts" / "run_m1_trainability_method.py"
            ),
        }
        if any(
            not source_hash_matches(source_paths[name], previous_sources.get(name))
            for name in scientific_sources
        ):
            raise ValueError("resume scientific source hashes do not match")
        if previous_manifest.get("config") != manifest["config"]:
            raise ValueError("resume configuration hashes do not match")
        manifest["timing"]["original_started_at"] = previous_manifest.get(
            "timing", {},
        ).get("original_started_at", previous_manifest.get("timing", {}).get("started_at"))
        manifest["resume"] = {
            "previous_status": previous_manifest.get("status"),
            "previous_commit": previous_manifest.get("code", {}).get("commit"),
            "resumed_at": started.isoformat(),
            "reuse_requires_complete_json": True,
            "source_match_policy": "exact_sha256_or_crlf_lf_only",
        }
    started_clock = time.perf_counter()
    metrics = {
        "status": "running",
        "label_rich_capacity": [],
        "optimization_curve": {},
    }
    try:
        shutil.copyfile(args.hard_config, output / "m1_hard_condition.json")
        shutil.copyfile(args.af_config, output / "m1_af_smoke.json")
        shutil.copyfile(args.ladder_config, output / "m1_trainability_ladder.json")
        write_json(output / "manifest.json", manifest)
        torch.set_num_threads(int(base["cpu_threads"]))
        torch.use_deterministic_algorithms(True)
        if device.type == "cuda":
            torch.backends.cudnn.benchmark = False
            torch.backends.cuda.matmul.allow_tf32 = False
        write_json(output / "environment.json", {
            "python": sys.version,
            "executable": sys.executable,
            "torch": torch.__version__,
            "numpy": np.__version__,
            "device": str(device),
            "cpu_threads": int(base["cpu_threads"]),
            "deterministic_algorithms": True,
        })

        capacity_groups = int(
            ladder["label_rich_capacity"]["train_paired_groups"]
        )
        train_arrays, _, train_summary, train_digest, (
            train_candidate_audit
        ) = build_sharded_split(
            hard_config, args.hard_config, "train",
            int(ladder["max_train_paired_groups"]),
            int(base["future_hash_bins"]),
            output / "shards",
            keep_paired_groups=0,
        )
        validation_arrays, _, validation_summary, (
            validation_digest
        ), validation_candidate_audit = build_sharded_split(
            hard_config, args.hard_config, "validation",
            int(ladder["validation_paired_groups"]),
            int(base["future_hash_bins"]),
            output / "shards",
            keep_paired_groups=0,
        )
        manifest["data"]["manifest_hash"] = hashlib.sha256(
            json.dumps(
                {"train": train_digest, "validation": validation_digest},
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        np.savez_compressed(
            output / "train_arrays.npz",
            **train_arrays,  # pyright: ignore[reportArgumentType]
        )
        np.savez_compressed(
            output / "validation_arrays.npz",
            **validation_arrays,  # pyright: ignore[reportArgumentType]
        )
        write_json(output / "data_summary.json", {
            "train": train_summary,
            "validation": validation_summary,
            "shard_audit_bundle_sha256": {
                "train": train_digest,
                "validation": validation_digest,
            },
            "candidate_audit": {
                "train": train_candidate_audit,
                "validation": validation_candidate_audit,
            },
            "test_generated": False,
            "formal_data_ready": False,
            "candidate_count": int(hard_config["candidates"]["budget_k"]),
            "frozen_candidate_budget": hard_config["candidates"]["budget_k"],
            "warning": "fixed deterministic K=16; nonformal train/validation diagnostic",
        })
        print(
            f"data: train_cases={len(train_arrays['y'])} "
            f"validation_cases={len(validation_arrays['y'])}",
            flush=True,
        )

        capacity = ladder["label_rich_capacity"]
        metrics["point_attempts"] = {}
        for steps in capacity["student_steps"]:
            name = f"capacity_g{capacity_groups}_s{steps}"
            point, attempts = run_isolated_point(
                output, name, "capacity", capacity_groups, int(steps),
                int(ladder["seed"]),
            )
            metrics["label_rich_capacity"].append(point)
            metrics["point_attempts"][name] = attempts
            write_json(output / "metrics.json", metrics)
            print(
                f"capacity steps={steps} accuracy="
                f"{point['teacher_forced']['accuracy']:.4f} "
                f"identifiable={point['teacher_forced']['identifiable_accuracy']:.4f} "
                f"final_active={point['causal_rollout']['final_active_graph_correctness']:.4f}",
                flush=True,
            )

        for spec in ladder["optimization_curve"]:
            groups = int(spec["train_paired_groups"])
            steps = int(spec["student_steps"])
            name = f"g{groups}_s{steps}"
            available_groups = sorted(set(
                int(value) for value in train_arrays["group"]
            ))
            point_mask = np.isin(
                train_arrays["group"], available_groups[:groups],
            )
            all_recovery_rows = np.asarray(
                train_arrays.get(
                    "recovery", np.zeros(len(train_arrays["y"])),
                ),
                dtype=bool,
            )
            method_results = {}
            for method in METHODS:
                method_result, attempts = run_isolated_method_point(
                    output, name, method, groups, steps,
                    int(ladder["seed"]),
                )
                method_results[method] = {
                    key: value for key, value in method_result.items()
                    if key not in {
                        "method", "student_steps", "train_paired_groups",
                        "train_decisions", "labelled_fraction",
                    }
                }
                metrics["point_attempts"][f"{name}_{method}"] = attempts
                write_json(output / "metrics.json", metrics)
            parameter_counts = {
                method_results[method]["student_parameters"]
                for method in METHODS
                if method != "oracle_candidate_program"
            }
            if len(parameter_counts) != 1:
                raise AssertionError("A-E isolated students must have matched size")
            point = {
                "student_steps": steps,
                "results": method_results,
                "error_decomposition": error_decomposition(method_results),
                "train_paired_groups": groups,
                "train_decisions": int(np.sum(point_mask & ~all_recovery_rows)),
                "train_recovery_examples": int(np.sum(
                    point_mask & all_recovery_rows
                )),
                "train_learning_rows": int(np.sum(point_mask)),
                "labelled_fraction": float(
                    train_arrays["labelled"][point_mask].mean()
                ),
                "execution_mode": "one_isolated_process_per_method",
            }
            point["candidate_audit"] = validation_candidate_audit
            metrics["optimization_curve"][name] = point
            write_json(output / "metrics.json", metrics)
            a = point["results"]["cpmt_ctl_core"]
            print(
                f"curve {name}: A_accuracy={a['teacher_forced']['accuracy']:.4f} "
                f"A_final_active={a['causal_rollout']['final_active_graph_correctness']:.4f}",
                flush=True,
            )

        last_capacity = metrics["label_rich_capacity"][-1]
        criteria = capacity
        capacity_pass = (
            last_capacity["teacher_forced"]["identifiable_accuracy"]
            >= float(criteria["identifiable_accuracy_required"])
            and last_capacity["ceiling_gap"] <= float(criteria["ceiling_gap_allowed"])
        )
        metrics["conclusion"] = {
            "capacity_pass": bool(capacity_pass),
            "capacity_criterion": {
                "identifiable_accuracy_required": float(
                    criteria["identifiable_accuracy_required"]
                ),
                "ceiling_gap_allowed": float(criteria["ceiling_gap_allowed"]),
            },
            "candidate_miss_rate": validation_candidate_audit["candidate_miss_rate"],
            "formal_claim_supported": False,
            "formal_gate_run": False,
            "test_generated": False,
            "next_if_pass": "implement deterministic deduplicated K=16 candidates",
            "next_if_fail": "inspect online representation and optimization before K=16",
        }
        metrics["status"] = "complete"
        write_json(output / "metrics.json", metrics)
        manifest["status"] = "complete"
        print(f"capacity_pass={str(capacity_pass).lower()}", flush=True)
        print(f"OUTPUT={output}", flush=True)
    except BaseException:
        metrics["status"] = "failed"
        write_json(output / "metrics.json", metrics)
        manifest["status"] = "failed"
        manifest["failures"].append(traceback.format_exc())
        raise
    finally:
        manifest["timing"]["ended_at"] = datetime.now(timezone.utc).isoformat()
        manifest["timing"]["wall_seconds"] = time.perf_counter() - started_clock
        write_json(output / "manifest.json", manifest)


if __name__ == "__main__":
    main()
