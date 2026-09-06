"""Generate procedural chained M1 train/validation rollouts; test stays sealed."""
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

from cpmt.m1_protocol import load_and_validate, protocol_sha256
from cpmt.m1_rollout import (
    generate_m1_paired_rollout_split,
    generate_m1_rollout_split,
    records_sha256,
)


def write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )


def write_jsonl(path: Path, records) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_output(*args: str) -> str:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={PROJECT.parents[1].as_posix()}", *args],
        cwd=PROJECT, capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path,
        default=PROJECT / "configs" / "m1_hard_condition.json",
    )
    parser.add_argument("--split", choices=("train", "validation"), required=True)
    size = parser.add_mutually_exclusive_group()
    size.add_argument(
        "--paired-groups", type=int,
        help="Generate two latent siblings per group (default mode).",
    )
    size.add_argument(
        "--sequences", type=int,
        help="Generate legacy unpaired interface-validation sequences.",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    config = load_and_validate(args.config)
    paired = args.sequences is None
    if paired:
        generation_args = {"paired_groups": args.paired_groups or 1}
        generator = generate_m1_paired_rollout_split
    else:
        generation_args = {"sequences": args.sequences}
        generator = generate_m1_rollout_split
    if args.dry_run:
        online, audit, summary = generator(config, args.split, **generation_args)
        print(json.dumps({
            **summary,
            "online_sha256": records_sha256(online),
            "audit_sha256": records_sha256(audit),
            "write": False,
        }, ensure_ascii=False, indent=2))
        return

    started = datetime.now(timezone.utc)
    mode = "paired" if paired else "unpaired"
    run_id = started.strftime(
        f"m1-rollout-{mode}-{args.split}-%Y%m%dT%H%M%S%fZ"
    )
    output = (args.output or PROJECT / "outputs" / "m1_rollout" / run_id).resolve()
    if not output.is_relative_to((PROJECT / "outputs").resolve()):
        raise ValueError("output must be inside project outputs")
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "schema_version": "cpmt-0.2",
        "run_id": run_id,
        "stage": "M1",
        "method": (
            "procedural_paired_continuous_rollout_validation"
            if paired else "procedural_continuous_rollout_validation"
        ),
        "status": "running",
        "code": {
            "commit": git_output("rev-parse", "HEAD"),
            "dirty": bool(git_output("status", "--porcelain")),
            "source_sha256": {
                "rollout_generator": sha256(PROJECT / "src" / "cpmt" / "m1_rollout.py"),
                "executor": sha256(PROJECT / "src" / "cpmt" / "executor.py"),
                "protocol_validator": sha256(PROJECT / "src" / "cpmt" / "m1_protocol.py"),
                "runner": sha256(Path(__file__)),
            },
        },
        "data": {
            "dataset_version": config["data"]["dataset_version"],
            "manifest_hash": "pending",
            "split": args.split,
            "test_generated": False,
            "formal_data_ready": False,
            "paired_latent_siblings": paired,
        },
        "config": {
            "path": "config.json",
            "hash": sha256(args.config),
            "canonical_protocol_sha256": protocol_sha256(config),
        },
        "seed": 360_906 + (0 if args.split == "train" else 200_000_000),
        "front_end": {
            "backbone_id": "controlled-structural-token-projector-v1",
            "depth_id": "not-applicable-m1-controlled",
            "pose_source": "actual-executed-reference-sequence",
        },
        "future_use_policy": "hindsight_train_only",
        "decision_refs": list(config["decision_refs"]),
        "timing": {"started_at": started.isoformat()},
        "failures": [],
        "metrics_ref": "summary.json",
        "hardware": "CPU procedural rollout generation",
    }
    started_clock = time.perf_counter()
    try:
        shutil.copyfile(args.config, output / "config.json")
        write_json(output / "manifest.json", manifest)
        online, audit, summary = generator(config, args.split, **generation_args)
        write_jsonl(output / "online_steps.jsonl", online)
        write_jsonl(output / "audit_sequences.jsonl", audit)
        summary.update({
            "online_sha256": records_sha256(online),
            "audit_sha256": records_sha256(audit),
        })
        write_json(output / "summary.json", summary)
        manifest["status"] = "complete"
        manifest["data"]["manifest_hash"] = summary["audit_sha256"]
        print(f"OUTPUT={output}")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    except BaseException:
        manifest["status"] = "failed"
        manifest["failures"].append(traceback.format_exc())
        raise
    finally:
        manifest["timing"]["ended_at"] = datetime.now(timezone.utc).isoformat()
        manifest["timing"]["wall_seconds"] = time.perf_counter() - started_clock
        write_json(output / "manifest.json", manifest)


if __name__ == "__main__":
    main()
