"""Run a reproducible CTL development experiment, never a formal test run."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

import numpy as np
import torch

from cpmt.dev_data import dataset_digest, generate_split
from cpmt.dev_learning import METHODS, run_seed


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False),
                    encoding="utf-8")


def git_output(*args: str) -> str:
    result = subprocess.run(["git", "-c", f"safe.directory={PROJECT.parents[1].as_posix()}",
                             *args], cwd=PROJECT, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def snapshot_sources(output: Path) -> dict:
    paths = sorted(set(
        list((PROJECT / "src" / "cpmt").glob("*.py"))
        + list((PROJECT / "tests").glob("*.py"))
        + [Path(__file__), PROJECT / "configs" / "ctl_dev.json",
           PROJECT / "experiments" / "counterfactual_transaction_learning" / "DEVELOPMENT.md"]
    ))
    hashes = {}
    snapshot = output / "source_snapshot"
    for path in paths:
        if not path.exists():
            continue
        relative = path.relative_to(PROJECT)
        target = snapshot / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        hashes[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    write_json(output / "source_hashes.json", hashes)
    return dict(commit=git_output("rev-parse", "HEAD"),
                dirty=bool(git_output("status", "--porcelain")),
                source_sha256=digest)


def check_config(config: dict) -> None:
    if config["protocol"] != "ctl-development-v1" or config["stage"] != "M1-development":
        raise ValueError("runner only supports explicitly marked development runs")
    if config["test_access"] is not False:
        raise ValueError("test access is forbidden")
    for name in ("train_groups", "validation_groups", "horizon", "student_steps",
                 "scorer_steps", "batch_size", "hidden_dim", "latent_dim"):
        if not isinstance(config[name], int) or config[name] <= 0:
            raise ValueError(f"invalid {name}")
    if not 0 < config["label_fraction"] <= 1 or not 0 <= config["ambiguous_fraction"] <= 1:
        raise ValueError("invalid label or ambiguity fraction")
    if not config["seeds"] or len(set(config["seeds"])) != len(config["seeds"]):
        raise ValueError("seeds must be nonempty and distinct")
    if config["temperature"] <= 0 or config["learning_rate"] <= 0:
        raise ValueError("temperature and learning rate must be positive")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PROJECT / "configs" / "ctl_dev.json")
    parser.add_argument("--output", type=Path, help="new directory within project outputs")
    parser.add_argument("--dry-run", action="store_true", help="inspect config/hardware without writes")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    check_config(config)
    device = torch.device(config["device"])
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable; choose CPU explicitly in dev config")
    hardware = torch.cuda.get_device_name(device) if device.type == "cuda" else "CPU"
    print(json.dumps(dict(protocol=config["protocol"], hardware=hardware,
                          train_cases=config["train_groups"] * 3,
                          validation_cases=config["validation_groups"] * 3,
                          seeds=config["seeds"], methods=METHODS), ensure_ascii=False), flush=True)
    if args.dry_run:
        return
    started_at = datetime.now(timezone.utc)
    run_id = started_at.strftime("ctl-dev-%Y%m%dT%H%M%S%fZ")
    output = (args.output or PROJECT / "outputs" / "ctl_dev" / run_id).resolve()
    if not output.is_relative_to((PROJECT / "outputs").resolve()):
        raise ValueError("output must be inside project outputs")
    output.mkdir(parents=True, exist_ok=False)
    manifest = dict(schema_version="cpmt-0.2", run_id=run_id, stage="M1",
                    method="development_comparison_not_formal_gate", status="running",
                    code=dict(commit="pending", dirty=True),
                    data=dict(dataset_version="spatial-toy-v1", manifest_hash="pending",
                              split="validation"),
                    config=dict(path="config.json", hash=hashlib.sha256(
                        args.config.read_bytes()).hexdigest()), seed=config["data_seed"],
                    front_end=dict(backbone_id="synthetic-appearance-v1",
                                   depth_id="three-place-oracle-geometry",
                                   pose_source="actual-synthetic-camera-sequence"),
                    future_use_policy="hindsight_train_only",
                    decision_refs=["D-018", "D-026", "D-027"],
                    timing=dict(started_at=started_at.isoformat()), failures=[],
                    metrics_ref="metrics.json", hardware=hardware)
    start = time.perf_counter()
    try:
        shutil.copyfile(args.config, output / "config.json")
        manifest["code"] = snapshot_sources(output)
        write_json(output / "manifest.json", manifest)
        torch.set_num_threads(2)
        torch.use_deterministic_algorithms(True)
        if device.type == "cuda":
            torch.backends.cudnn.benchmark = False
            torch.backends.cuda.matmul.allow_tf32 = False
        write_json(output / "environment.json", dict(
            python=sys.version, executable=sys.executable, torch=torch.__version__,
            numpy=np.__version__, torch_cuda=torch.version.cuda, device=hardware,
            deterministic_algorithms=True, cpu_threads=2,
            cuda_device_memory_bytes=(torch.cuda.get_device_properties(device).total_memory
                                      if device.type == "cuda" else None)))
        datasets, digests = {}, {}
        for split in ("train", "validation"):
            data, audit = generate_split(config, split)
            datasets[split] = data
            digests[split] = dataset_digest(audit)
            # Physically separate deployable input from hindsight/evaluation data.
            with (output / f"{split}_online.jsonl").open("w", encoding="utf-8") as handle:
                for case in audit:
                    handle.write(json.dumps(case["online"], ensure_ascii=False) + "\n")
            with (output / f"{split}_audit.jsonl").open("w", encoding="utf-8") as handle:
                for case in audit:
                    handle.write(json.dumps(case, ensure_ascii=False) + "\n")
            np.savez_compressed(output / f"{split}_training_arrays.npz", **data)
            print(f"{split}: {len(audit)} cases, digest={digests[split][:12]}", flush=True)
        if set(datasets["train"]["group"]) & set(datasets["validation"]["group"]):
            raise AssertionError("paired groups overlap across splits")
        manifest["data"]["manifest_hash"] = hashlib.sha256(
            json.dumps(digests, sort_keys=True).encode()).hexdigest()
        write_json(output / "data_manifest.json", dict(
            version="spatial-toy-v1", digests=digests, test_generated=False,
            label_fraction_realized=float(datasets["train"]["labelled"].mean()),
            indistinguishable_validation_fraction=float(datasets["validation"]["ambiguous"].mean()),
            candidate_count=3, candidate_coverage=1.0,
            candidate_coverage_note="generator guarantees all three choices; not a benchmark result",
            primitive_execution="existing cpmt.executor.execute_transaction",
            controls="siblings share assets/noise/camera path; groups never cross splits"))
        all_results = {}
        for seed in config["seeds"]:
            metrics, details = run_seed(datasets["train"], datasets["validation"],
                                       config, seed, output, device)
            all_results[str(seed)] = metrics
            write_json(output / f"details_seed{seed}.json", details)
            write_json(output / "metrics.json", all_results)
        aggregate = {}
        for method in METHODS:
            fields = ("accuracy", "identifiable_accuracy", "indistinguishable_accuracy",
                      "indistinguishable_quarantine_rate", "commit_coverage",
                      "toy_location_fact_error", "toy_excess_node_count", "nll",
                      "brier", "teacher_accuracy", "student_seconds", "peak_allocated_mb")
            aggregate[method] = {
                field: dict(mean=float(np.mean(values)), std=float(np.std(values)))
                for field in fields
                if (values := [all_results[str(seed)][method][field] for seed in config["seeds"]])
                and all(v is not None for v in values)
            }
        write_json(output / "aggregate.json", aggregate)
        manifest["status"] = "complete"
        print(f"OUTPUT={output}", flush=True)
    except BaseException:
        manifest["status"] = "failed"
        manifest["failures"].append(traceback.format_exc())
        raise
    finally:
        manifest["timing"]["ended_at"] = datetime.now(timezone.utc).isoformat()
        manifest["timing"]["wall_seconds"] = time.perf_counter() - start
        write_json(output / "manifest.json", manifest)


if __name__ == "__main__":
    main()
