#!/usr/bin/env python3
"""Closed-by-default D-216 split, training-bundle, and fit/seal stage."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any
import zipfile

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt.d215_frontend_freeze import validate_d215_contract  # noqa: E402
from vsmt.d216_estimator_training import (  # noqa: E402
    NPZ_ARRAY_NAMES,
    SPLITS,
    fit_and_seal_estimator,
    make_house_split_manifest,
    make_training_bundle_manifest,
    validate_d216_contract,
    validate_house_split_manifest,
    validate_training_bundle_manifest,
)


CONTRACT_PATH = ROOT / "configs/vsmt/vm04_d216_estimator_training_seal_v1.json"
D215_PATH = ROOT / "configs/vsmt/vm04_d215_frontend_freeze_v1.json"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"),
                      object_pairs_hook=_reject_duplicate_pairs)


def write_new_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json(value))
        handle.write("\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=ROOT, text=True).strip()


def load_contracts() -> tuple[dict[str, Any], dict[str, Any]]:
    d216 = validate_d216_contract(read_json(CONTRACT_PATH))
    d215 = validate_d215_contract(read_json(D215_PATH))
    _require(sha256(D215_PATH) == d216["d215_binding"]["file_sha256"],
             "D-215 contract file bytes changed")
    return d215, d216


def _execution_checkout(d216: dict[str, Any]) -> str:
    expected = d216["expected_reviewed_implementation_commit"]
    _require(d216["status"] ==
             d216["activation_policy"]["active_status"] and expected,
             "D-216 execution is closed pending implementation review")
    head = git("rev-parse", "HEAD")
    parent = git("rev-parse", "HEAD^")
    _require(parent == expected and head != expected,
             "execution requires one activation commit whose parent is the reviewed implementation")
    changed = git("diff", "--name-only", expected, head).splitlines()
    _require(changed == d216["activation_policy"]
             ["activation_commit_may_change_only"],
             "D-216 activation commit changed files outside its allowlist")
    _require(not git("status", "--porcelain"),
             "D-216 execution requires a clean checkout")
    return head


def check() -> dict[str, Any]:
    _, d216 = load_contracts()
    return {
        "decision_id": "D-216",
        "status": d216["status"],
        "reviewed_baseline_commit": d216["reviewed_baseline_commit"],
        "expected_reviewed_implementation_commit":
            d216["expected_reviewed_implementation_commit"],
        "authorization": d216["authorization"],
        "production_reader_implemented": False,
        "route_or_raw_execution_opened": False,
        "legacy_grid_deletion_opened": False,
    }


def seal_split(*, source_inventory_path: Path, reserved_manifest_path: Path,
               output_path: Path) -> dict[str, Any]:
    d215, d216 = load_contracts()
    activation = _execution_checkout(d216)
    _require(d216["authorization"]["split_manifest_materialization"] is True,
             "D-216 split-manifest materialization is not authorized")
    _require(not output_path.exists(), "D-216 split output already exists")
    manifest = make_house_split_manifest(
        source_inventory=read_json(source_inventory_path),
        reserved_house_manifest=read_json(reserved_manifest_path),
        d215_contract=d215, d216_contract=d216,
    )
    write_new_json(output_path, manifest)
    receipt = {
        "command": "seal-split", "activation_commit": activation,
        "source_inventory_file_sha256": sha256(source_inventory_path),
        "reserved_manifest_file_sha256": sha256(reserved_manifest_path),
        "output_file_sha256": sha256(output_path),
        "partition_manifest_receipt_sha256":
            manifest["partition_manifest_receipt_sha256"],
    }
    return receipt


def _load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        _require(set(archive.files) == set(NPZ_ARRAY_NAMES),
                 f"NPZ array schema changed: {path}")
        return {name: archive[name] for name in NPZ_ARRAY_NAMES}


def _parse_shard_spec(spec: str, bundle_root: Path) -> dict[str, Any]:
    split, separator, relative = spec.partition("=")
    _require(separator == "=" and split in SPLITS and relative,
             "--shard must use train|calibration|audit=relative/path.npz")
    pure = Path(relative)
    _require(not pure.is_absolute() and ".." not in pure.parts,
             "shard path must remain under bundle root")
    path = (bundle_root / pure).resolve()
    _require(path.is_relative_to(bundle_root.resolve()) and path.is_file(),
             f"training shard is missing or escapes bundle root: {relative}")
    return {"relative_path": pure.as_posix(), "path": path, "split": split}


def _available_ram_bytes() -> int | None:
    try:
        import psutil
        return int(psutil.virtual_memory().available)
    except ImportError:
        if hasattr(os, "sysconf"):
            try:
                return int(os.sysconf("SC_AVPHYS_PAGES") *
                           os.sysconf("SC_PAGE_SIZE"))
            except (ValueError, OSError):
                return None
        return None


def _npz_uncompressed_bytes(path: Path) -> int:
    with zipfile.ZipFile(path) as archive:
        return sum(item.file_size for item in archive.infolist())


def _resource_workers(requested: int | None,
                      specs: list[dict[str, Any]]) -> tuple[int, dict[str, Any]]:
    logical = os.cpu_count() or 1
    unit_count = len(specs)
    sizes = [_npz_uncompressed_bytes(item["path"]) for item in specs]
    available = _available_ram_bytes()
    reserve = max(4 * 1024 ** 3, int((available or 0) * 0.2))
    per_worker = max(sizes) * 2 + 256 * 1024 ** 2
    memory_workers = (unit_count if available is None else
                      max(1, (available - reserve) // max(1, per_worker)))
    safe_maximum = max(1, min(unit_count, logical, memory_workers))
    if requested is None:
        actual = safe_maximum
    else:
        _require(requested >= 1, "requested workers must be positive")
        actual = min(requested, safe_maximum)
    return actual, {
        "requested_workers": requested,
        "actual_workers": actual,
        "maximum_safe_workers": safe_maximum,
        "logical_cpu_count": logical,
        "unit_count": unit_count,
        "available_ram_bytes_before_load": available,
        "reserved_ram_bytes": reserve,
        "largest_uncompressed_shard_bytes": max(sizes),
        "total_uncompressed_shard_bytes": sum(sizes),
        "estimated_bytes_per_parallel_loader": per_worker,
        "basis": "min(shards,logical_cpu,available_ram_after_reserve)_for_parallel_hash_and_npz_validation",
        "merge_order": "split_order_then_relative_path",
    }


def _read_shard(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "relative_path": item["relative_path"],
        "file_sha256": sha256(item["path"]),
        "split": item["split"],
        "arrays": _load_npz(item["path"]),
    }


def seal_bundle(*, partition_path: Path, bundle_root: Path,
                evidence_index_path: Path, shard_specs: list[str], output_path: Path,
                requested_workers: int | None) -> dict[str, Any]:
    d215, d216 = load_contracts()
    activation = _execution_checkout(d216)
    _require(d216["authorization"]["semantic_annotation_import"] is True and
             d216["authorization"]["training_bundle_sealing"] is True,
             "D-216 training-bundle sealing is not authorized")
    _require(not output_path.exists(), "D-216 bundle output already exists")
    partition = validate_house_split_manifest(read_json(partition_path))
    specs = [_parse_shard_spec(item, bundle_root) for item in shard_specs]
    _require(specs, "at least one training shard is required")
    workers, resource = _resource_workers(requested_workers, specs)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        shards = list(pool.map(_read_shard, specs))
    manifest = make_training_bundle_manifest(
        shards=shards, partition_manifest=partition,
        training_evidence_index=read_json(evidence_index_path),
        d215_contract=d215, d216_contract=d216)
    write_new_json(output_path, manifest)
    return {
        "command": "seal-bundle", "activation_commit": activation,
        "partition_file_sha256": sha256(partition_path),
        "training_evidence_index_file_sha256": sha256(evidence_index_path),
        "output_file_sha256": sha256(output_path),
        "training_bundle_sha256": manifest["training_bundle_sha256"],
        "resources": resource,
    }


def _combine_shards(shards: list[dict[str, Any]]) -> dict[str, dict[str, np.ndarray]]:
    result: dict[str, dict[str, np.ndarray]] = {}
    for split in SPLITS:
        selected = [row["arrays"] for row in shards if row["split"] == split]
        _require(selected, f"missing {split} arrays")
        result[split] = {
            name: np.concatenate([row[name] for row in selected], axis=0)
            for name in NPZ_ARRAY_NAMES
        }
    return result


def train_seal(*, partition_path: Path, bundle_manifest_path: Path,
               evidence_index_path: Path, bundle_root: Path, output_root: Path, device: str,
               requested_workers: int | None) -> dict[str, Any]:
    d215, d216 = load_contracts()
    activation = _execution_checkout(d216)
    _require(d216["authorization"]["estimator_training"] is True and
             d216["authorization"]["artifact_sealing"] is True,
             "D-216 estimator training/artifact sealing is not authorized")
    _require(not output_root.exists(), "D-216 training output root exists")
    partition = validate_house_split_manifest(read_json(partition_path))
    bundle = validate_training_bundle_manifest(read_json(bundle_manifest_path))
    specs = [{
        "relative_path": row["relative_path"],
        "path": (bundle_root / Path(row["relative_path"])).resolve(),
        "split": row["split"],
    } for row in bundle["shards"]]
    for item in specs:
        _require(item["path"].is_relative_to(bundle_root.resolve()) and
                 item["path"].is_file(), "sealed shard is missing or escapes root")
    workers, resource = _resource_workers(requested_workers, specs)
    available = resource["available_ram_bytes_before_load"]
    required = resource["total_uncompressed_shard_bytes"] * 4 + 4 * 1024 ** 3
    _require(available is None or available >= required,
             "insufficient RAM for sealed arrays, normalization, and training copies")
    if device.startswith("cuda"):
        import torch
        _require(torch.cuda.is_available(), "requested CUDA device is unavailable")
        device_index = torch.device(device).index
        if device_index is None:
            device_index = torch.cuda.current_device()
        free_gpu, total_gpu = torch.cuda.mem_get_info(device_index)
        required_gpu = (resource["total_uncompressed_shard_bytes"] * 2 +
                        1024 ** 3)
        _require(free_gpu >= required_gpu,
                 "insufficient free GPU memory for the sealed training arrays")
        resource["gpu"] = {
            "device_index": device_index,
            "name": torch.cuda.get_device_name(device_index),
            "free_bytes_before_training": int(free_gpu),
            "total_bytes": int(total_gpu),
            "required_free_bytes_estimate": int(required_gpu),
        }
    else:
        resource["gpu"] = None
    with ThreadPoolExecutor(max_workers=workers) as pool:
        shards = list(pool.map(_read_shard, specs))
    reconstructed = make_training_bundle_manifest(
        shards=shards, partition_manifest=partition,
        training_evidence_index=read_json(evidence_index_path),
        d215_contract=d215, d216_contract=d216)
    _require(reconstructed == bundle,
             "training shard bytes or summaries differ from the sealed bundle")
    output_root.mkdir(parents=True, exist_ok=False)
    started = {
        "schema_version": "vsmt-vm04-d216-training-started-v1",
        "activation_commit": activation, "device": device,
        "resources": resource,
        "free_disk_bytes": shutil.disk_usage(output_root.parent).free,
        "wall_clock_timeout_used": False,
    }
    write_new_json(output_root / "started.json", started)
    try:
        artifacts = fit_and_seal_estimator(
            split_arrays=_combine_shards(shards),
            partition_manifest=partition, training_bundle_manifest=bundle,
            d215_contract=d215, d216_contract=d216,
            implementation_commit=d216["expected_reviewed_implementation_commit"],
            device=device,
        )
    except Exception as error:
        write_new_json(output_root / "failure.json", {
            "schema_version": "vsmt-vm04-d216-training-failure-v1",
            "error_type": type(error).__name__, "message": str(error),
            "rerun_or_overwrite_allowed": False,
        })
        raise
    for name, value in artifacts.items():
        write_new_json(output_root / f"{name}.json", value)
    stage_receipt = {
        "schema_version": "vsmt-vm04-d216-stage-receipt-v1",
        "command": "train-seal", "activation_commit": activation,
        "partition_file_sha256": sha256(partition_path),
        "bundle_manifest_file_sha256": sha256(bundle_manifest_path),
        "training_evidence_index_file_sha256": sha256(evidence_index_path),
        "resources": resource,
        "device": device,
        "artifact_file_sha256": {
            name: sha256(output_root / f"{name}.json") for name in artifacts
        },
        "production_reader_executed": False,
    }
    write_new_json(output_root / "stage_receipt.json", stage_receipt)
    return stage_receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check")
    split = commands.add_parser("seal-split")
    split.add_argument("--source-inventory", type=Path, required=True)
    split.add_argument("--reserved-manifest", type=Path, required=True)
    split.add_argument("--output", type=Path, required=True)
    bundle = commands.add_parser("seal-bundle")
    bundle.add_argument("--partition", type=Path, required=True)
    bundle.add_argument("--bundle-root", type=Path, required=True)
    bundle.add_argument("--evidence-index", type=Path, required=True)
    bundle.add_argument("--shard", action="append", required=True)
    bundle.add_argument("--output", type=Path, required=True)
    bundle.add_argument("--workers", type=int)
    train = commands.add_parser("train-seal")
    train.add_argument("--partition", type=Path, required=True)
    train.add_argument("--bundle-manifest", type=Path, required=True)
    train.add_argument("--bundle-root", type=Path, required=True)
    train.add_argument("--evidence-index", type=Path, required=True)
    train.add_argument("--output-root", type=Path, required=True)
    train.add_argument("--device", default="cuda")
    train.add_argument("--workers", type=int)
    args = parser.parse_args()
    if args.command == "check":
        result = check()
    elif args.command == "seal-split":
        result = seal_split(
            source_inventory_path=args.source_inventory,
            reserved_manifest_path=args.reserved_manifest, output_path=args.output)
    elif args.command == "seal-bundle":
        result = seal_bundle(
            partition_path=args.partition, bundle_root=args.bundle_root,
            evidence_index_path=args.evidence_index,
            shard_specs=args.shard, output_path=args.output,
            requested_workers=args.workers)
    else:
        result = train_seal(
            partition_path=args.partition,
            bundle_manifest_path=args.bundle_manifest,
            evidence_index_path=args.evidence_index,
            bundle_root=args.bundle_root, output_root=args.output_root,
            device=args.device, requested_workers=args.workers)
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
