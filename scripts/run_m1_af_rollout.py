"""Run the nonformal A-F causal-rollout smoke on train/validation only."""
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
from cpmt.m1_af_rollout import (
    build_rollout_learning_arrays,
    resolve_af_smoke_config,
    run_af_seed,
)
from cpmt.m1_protocol import load_and_validate, protocol_sha256
from cpmt.m1_rollout import records_sha256


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
        "--hard-config", type=Path,
        default=PROJECT / "configs" / "m1_hard_condition.json",
    )
    parser.add_argument(
        "--smoke-config", type=Path,
        default=PROJECT / "configs" / "m1_af_smoke.json",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    hard_config = load_and_validate(args.hard_config)
    smoke_raw = json.loads(args.smoke_config.read_text(encoding="utf-8"))
    config = resolve_af_smoke_config(hard_config, smoke_raw)
    device = torch.device(config["device"])
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("configured CUDA is unavailable; use CPU for this smoke")
    preview = {
        "protocol": config["protocol"],
        "formal_run": False,
        "test_access": False,
        "methods": list(METHODS),
        "paired_groups": config["paired_groups"],
        "train_decisions": config["paired_groups"]["train"] * 2 * 20,
        "validation_decisions": config["paired_groups"]["validation"] * 2 * 20,
        "seeds": config["seeds"],
        "device": str(device),
        "candidate_count": int(hard_config["candidates"]["budget_k"]),
        "frozen_candidate_budget": hard_config["candidates"]["budget_k"],
    }
    print(json.dumps(preview, ensure_ascii=False), flush=True)
    if args.dry_run:
        return

    started = datetime.now(timezone.utc)
    run_id = started.strftime("m1-af-rollout-smoke-%Y%m%dT%H%M%S%fZ")
    output = (args.output or PROJECT / "outputs" / "m1_af_rollout" / run_id).resolve()
    if not output.is_relative_to((PROJECT / "outputs").resolve()):
        raise ValueError("output must be inside project outputs")
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "schema_version": "cpmt-0.2",
        "run_id": run_id,
        "stage": "M1",
        "method": "A-F_causal_rollout_interface_smoke_not_formal_gate",
        "status": "running",
        "code": {
            "commit": git_output("rev-parse", "HEAD"),
            "dirty": bool(git_output("status", "--porcelain")),
            "source_sha256": {
                "adapter": sha256(PROJECT / "src" / "cpmt" / "m1_af_rollout.py"),
                "rollout_generator": sha256(PROJECT / "src" / "cpmt" / "m1_rollout.py"),
                "learning": sha256(PROJECT / "src" / "cpmt" / "dev_learning.py"),
                "executor": sha256(PROJECT / "src" / "cpmt" / "executor.py"),
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
            "path": "m1_af_smoke.json",
            "hash": sha256(args.smoke_config),
            "hard_config_path": "m1_hard_condition.json",
            "hard_config_hash": sha256(args.hard_config),
            "canonical_protocol_sha256": protocol_sha256(hard_config),
        },
        "seed": int(config["seeds"][0]),
        "front_end": {
            "backbone_id": "shared-analytic-online-vector-v1",
            "depth_id": "not-applicable-m1-controlled",
            "pose_source": "actual-executed-reference-sequence",
        },
        "future_use_policy": "hindsight_train_only",
        "decision_refs": ["D-030", "D-031"],
        "timing": {"started_at": started.isoformat()},
        "failures": [],
        "metrics_ref": "metrics.json",
        "hardware": str(device),
    }
    started_clock = time.perf_counter()
    try:
        shutil.copyfile(args.hard_config, output / "m1_hard_condition.json")
        shutil.copyfile(args.smoke_config, output / "m1_af_smoke.json")
        write_json(output / "manifest.json", manifest)
        torch.set_num_threads(int(config["cpu_threads"]))
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
            "cpu_threads": int(config["cpu_threads"]),
            "deterministic_algorithms": True,
        })

        datasets = {}
        audits = {}
        summaries = {}
        digests = {}
        for split in ("train", "validation"):
            data, split_audits, summary = build_rollout_learning_arrays(
                hard_config, split,
                paired_groups=int(config["paired_groups"][split]),
                future_hash_bins=int(config["future_hash_bins"]),
            )
            datasets[split] = data
            audits[split] = split_audits
            summaries[split] = summary
            digests[split] = records_sha256(split_audits)
            np.savez_compressed(output / f"{split}_arrays.npz", **data)
            write_jsonl(output / f"{split}_audit_sequences.jsonl", split_audits)
            write_jsonl(
                output / f"{split}_online_steps.jsonl",
                [step["online"] for audit in split_audits for step in audit["steps"]],
            )
            print(
                f"{split}: cases={len(data['y'])} groups={summary['paired_groups']} "
                f"digest={digests[split][:12]}", flush=True,
            )
        if set(datasets["train"]["group"]) != set(
            range(int(config["paired_groups"]["train"]))
        ):
            raise AssertionError("train paired groups are incomplete")
        if summaries["train"]["labelled_fraction"] != 0.1:
            raise AssertionError("smoke must realize the frozen 10% group label fraction")
        manifest["data"]["manifest_hash"] = hashlib.sha256(
            json.dumps(digests, sort_keys=True).encode("utf-8")
        ).hexdigest()
        write_json(output / "data_summary.json", {
            "split_summaries": summaries,
            "audit_sha256": digests,
            "test_generated": False,
            "formal_data_ready": False,
            "candidate_count": int(hard_config["candidates"]["budget_k"]),
            "candidate_budget_k": hard_config["candidates"]["budget_k"],
            "candidate_note": "fixed deterministic K=16; nonformal train/validation smoke",
        })

        all_results = {}
        for seed in config["seeds"]:
            results, details, models = run_af_seed(
                datasets["train"], datasets["validation"], audits["validation"],
                config, int(seed),
            )
            all_results[str(seed)] = results
            write_json(output / f"details_seed{seed}.json", details)
            for name, model in models.items():
                torch.save(model.state_dict(), output / f"{name}_seed{seed}.pt")
            write_json(output / "metrics.json", all_results)
            for method in METHODS:
                teacher = results[method]["teacher_forced"]["accuracy"]
                final = results[method]["causal_rollout"]["final_post_graph_correctness"]
                print(
                    f"seed={seed} method={method} teacher_forced={teacher:.3f} "
                    f"rollout_final={final:.3f}", flush=True,
                )
        manifest["status"] = "complete"
        print(f"OUTPUT={output}", flush=True)
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
