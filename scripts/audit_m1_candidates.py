"""Run the pre-training fixed-K candidate coverage audit; never open test."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from cpmt.m1_protocol import load_and_validate, protocol_sha256
from cpmt.m1_rollout import audit_m1_candidate_coverage


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_output(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=PROJECT, capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--hard-config", type=Path,
        default=PROJECT / "configs" / "m1_hard_condition.json",
    )
    parser.add_argument("--split", choices=("train", "validation"), default="validation")
    parser.add_argument("--paired-groups", type=int, default=1)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    config = load_and_validate(args.hard_config)
    preview = {
        "operation": "fixed_k16_candidate_coverage_audit",
        "split": args.split,
        "paired_groups": args.paired_groups,
        "decisions": args.paired_groups * 20,
        "candidate_budget_k": config["candidates"]["budget_k"],
        "test_access": False,
        "future_scoring": False,
        "training": False,
    }
    print(json.dumps(preview, ensure_ascii=False), flush=True)
    if args.dry_run:
        return
    if args.paired_groups <= 0:
        raise ValueError("paired-groups must be positive")

    started = datetime.now(timezone.utc)
    run_id = started.strftime("m1-candidate-audit-%Y%m%dT%H%M%S%fZ")
    output = (
        args.output
        or PROJECT / "outputs" / "m1_candidate_audit" / run_id
    ).resolve()
    if not output.is_relative_to((PROJECT / "outputs").resolve()):
        raise ValueError("output must be inside project outputs")
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "schema_version": "cpmt-0.2",
        "run_id": run_id,
        "stage": "M1",
        "method": "fixed_deterministic_k16_candidate_coverage_audit",
        "status": "running",
        "code": {
            "commit": git_output("rev-parse", "HEAD"),
            "dirty": bool(git_output("status", "--porcelain")),
            "source_sha256": {
                "candidate_generator": sha256(
                    PROJECT / "src" / "cpmt" / "m1_rollout.py"
                ),
                "executor": sha256(PROJECT / "src" / "cpmt" / "executor.py"),
                "runner": sha256(Path(__file__)),
            },
        },
        "config": {
            "path": str(args.hard_config),
            "hash": sha256(args.hard_config),
            "canonical_protocol_sha256": protocol_sha256(config),
        },
        "data": {
            "split": args.split,
            "paired_groups": args.paired_groups,
            "test_generated": False,
            "formal_data_ready": False,
        },
        "future_use_policy": "not_used_candidate_audit_only",
        "timing": {"started_at": started.isoformat()},
        "failures": [],
    }
    write_json(output / "manifest.json", manifest)
    write_json(output / "config.json", preview)
    clock = time.perf_counter()
    try:
        rows, summary = audit_m1_candidate_coverage(
            config, args.split, paired_groups=args.paired_groups,
        )
        with (output / "candidate_rows.jsonl").open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        write_json(output / "summary.json", summary)
        manifest["status"] = "complete"
        manifest["metrics"] = summary
    except BaseException as error:
        manifest["status"] = "failed"
        manifest["failures"].append({
            "type": type(error).__name__, "message": str(error),
        })
        raise
    finally:
        manifest["timing"]["ended_at"] = datetime.now(timezone.utc).isoformat()
        manifest["timing"]["wall_seconds"] = time.perf_counter() - clock
        write_json(output / "manifest.json", manifest)


if __name__ == "__main__":
    main()
