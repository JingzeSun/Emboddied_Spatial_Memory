#!/usr/bin/env python3
"""D-217 plan, capacity probe, and train/calibration RGB-D generation."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
OPS = Path(__file__).resolve().parent
for item in (SRC, OPS):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt.d215_frontend_freeze import validate_d215_contract  # noqa: E402
from vsmt.d216_estimator_training import validate_d216_contract  # noqa: E402
from vsmt.d217_estimator_development import (  # noqa: E402
    make_development_plan,
    validate_d217_contract,
)
from vm04_d217_rgbd_worker import generate_house  # noqa: E402


D215_PATH = ROOT / "configs/vsmt/vm04_d215_frontend_freeze_v1.json"
D216_PATH = ROOT / "configs/vsmt/vm04_d216_estimator_training_seal_v1.json"
CONTRACT_PATH = ROOT / "configs/vsmt/vm04_d217_estimator_development_rgbd_v1.json"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"),
                      object_pairs_hook=_reject_duplicates)


def write_new_json(path: Path, value: Any, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(str(path), flags, 0o600 if private else 0o644)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json(value))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=ROOT, text=True).strip()


def load_contracts() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    d215 = validate_d215_contract(read_json(D215_PATH))
    d216 = validate_d216_contract(read_json(D216_PATH))
    d217 = validate_d217_contract(read_json(CONTRACT_PATH))
    _require(sha256(D216_PATH) == d217["d216_binding"]["file_sha256"],
             "D-216 contract file bytes changed")
    return d215, d216, d217


def _execution_checkout(d217: dict[str, Any]) -> str:
    expected = d217["expected_reviewed_implementation_commit"]
    _require(d217["status"] == d217["activation_policy"]["active_status"] and
             expected, "D-217 execution is closed pending review")
    head, parent = git("rev-parse", "HEAD"), git("rev-parse", "HEAD^")
    _require(parent == expected and head != expected,
             "D-217 requires one activation child of reviewed implementation")
    changed = git("diff", "--name-only", expected, head).splitlines()
    _require(changed == d217["activation_policy"]
             ["activation_commit_may_change_only"],
             "D-217 activation changed files outside its allowlist")
    _require(not git("status", "--porcelain"),
             "D-217 execution requires a clean checkout")
    return head


def check() -> dict[str, Any]:
    _, _, contract = load_contracts()
    return {
        "decision_id": "D-217", "status": contract["status"],
        "expected_reviewed_implementation_commit":
            contract["expected_reviewed_implementation_commit"],
        "authorization": contract["authorization"],
        "development_house_counts": contract["development_sample"]
        ["house_counts"],
        "audit_opened": False, "production_reader_opened": False,
        "route_or_raw_opened": False,
    }


def seal_plan(*, source_inventory_path: Path, output_root: Path) -> dict[str, Any]:
    d215, d216, d217 = load_contracts()
    activation = _execution_checkout(d217)
    _require(d217["authorization"]["development_plan_sealing"] is True,
             "D-217 development plan sealing is not authorized")
    _require(not output_root.exists(), "D-217 output root already exists")
    artifacts = make_development_plan(
        source_inventory=read_json(source_inventory_path),
        d215_contract=d215, d216_contract=d216, d217_contract=d217)
    write_new_json(output_root / "public/development-plan.json",
                   artifacts["public_plan"])
    for name in ("private_plan", "private_partition", "private_reserved",
                 "private_audit_seal", "private_confirmation_pool"):
        write_new_json(output_root / "private/plan" / f"{name}.json",
                       artifacts[name], private=True)
    receipt = {
        "schema_version": "vsmt-vm04-d217-plan-success-v1",
        "activation_commit": activation,
        "source_inventory_file_sha256": sha256(source_inventory_path),
        "public_plan_sha256": artifacts["public_plan"]["public_plan_sha256"],
        "private_plan_sha256": artifacts["private_plan"]["private_plan_sha256"],
        "audit_opened": False, "observations_generated": 0,
    }
    write_new_json(output_root / "private/plan/success.json", receipt,
                   private=True)
    return receipt


def _resource_snapshot(path: Path) -> dict[str, Any]:
    try:
        import psutil
        ram = int(psutil.virtual_memory().available)
        cpus = int(psutil.cpu_count(logical=True) or 1)
    except ImportError:
        ram, cpus = None, int(os.cpu_count() or 1)
    gpu = None
    try:
        output = subprocess.check_output([
            "nvidia-smi", "--query-gpu=name,memory.total,memory.free",
            "--format=csv,noheader,nounits"], text=True, timeout=30).strip()
        gpu = output.splitlines()
    except (OSError, subprocess.SubprocessError):
        pass
    return {
        "logical_cpu_count": cpus, "available_ram_bytes": ram,
        "disk_free_bytes": shutil.disk_usage(path).free,
        "gpu_name_total_free_mib_rows": gpu,
    }


def _tasks(output_root: Path, source_root: Path, contract: dict[str, Any],
           rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    d215 = validate_d215_contract(read_json(D215_PATH))
    split_salt = d215["semantic_structural_estimator"]["training_split"]
    ["split_salt"]
    return [{
        "row": row, "source_root": str(source_root),
        "output_root": str(output_root), "contract": contract,
        "d215_split_salt": split_salt,
    } for row in rows]


def _run_group(tasks: list[dict[str, Any]], workers: int) -> list[dict[str, Any]]:
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(generate_house, tasks))


def capacity_probe(*, output_root: Path, source_root: Path) -> dict[str, Any]:
    _, _, contract = load_contracts()
    activation = _execution_checkout(contract)
    _require(contract["authorization"]["capacity_probe"] is True,
             "D-217 capacity probe is not authorized")
    success_path = output_root / "private/plan/success.json"
    _require(success_path.is_file(), "D-217 plan success is missing")
    plan = read_json(output_root / "private/plan/private_plan.json")
    train_rows = [row for row in plan["rows"] if row["split"] == "train"]
    probe_counts = contract["resource_policy"]["probe_worker_counts"]
    required_rows = sum(probe_counts)
    _require(len(train_rows) >= required_rows,
             "development plan lacks capacity-probe houses")
    cursor, results, largest_safe = 0, [], 0
    for workers in probe_counts:
        before = _resource_snapshot(output_root)
        _require(before["disk_free_bytes"] >= contract["resource_policy"]
                 ["minimum_free_disk_bytes_before_batch"],
                 "capacity probe disk guard failed")
        if workers > before["logical_cpu_count"]:
            results.append({"workers": workers, "status": "not_started_cpu_limit",
                            "resources_before": before})
            break
        group_rows = train_rows[cursor:cursor + workers]
        cursor += workers
        started = time.monotonic()
        try:
            rows = _run_group(
                _tasks(output_root, source_root, contract, group_rows), workers)
            after = _resource_snapshot(output_root)
            safe = (after["disk_free_bytes"] >= contract["resource_policy"]
                    ["emergency_free_disk_bytes"])
            results.append({
                "workers": workers, "status": "completed" if safe else
                    "failed_resource_guard", "wall_seconds":
                    time.monotonic() - started,
                "resources_before": before, "resources_after": after,
                "house_results": rows,
            })
            if not safe:
                break
            largest_safe = workers
        except Exception as error:
            results.append({
                "workers": workers, "status": "worker_pool_failure",
                "error_type": type(error).__name__, "message": str(error),
                "resources_before": before,
            })
            break
    _require(largest_safe >= 1, "no safe generation worker count was measured")
    receipt = {
        "schema_version": "vsmt-vm04-d217-capacity-receipt-v1",
        "activation_commit": activation, "probe_results": results,
        "actual_batch_workers": largest_safe,
        "probe_houses_are_formal_train_rows_and_must_be_reused": True,
        "audit_opened": False,
    }
    write_new_json(output_root / "private/capacity.receipt.json", receipt,
                   private=True)
    return receipt


def _existing_result(output_root: Path, row: dict[str, Any]) -> dict[str, Any] | None:
    base = output_root / "public" / row["split"] / (
        f"sample_{row['sample_rank']:04d}")
    private = output_root / "private" / row["split"] / (
        f"sample_{row['sample_rank']:04d}")
    public_path = base / "rgbd.npz"
    public_receipt_path = base / "receipt.json"
    private_receipt_path = private / "receipt.json"
    success_paths = (public_path, public_receipt_path, private_receipt_path)
    present = [path.is_file() for path in success_paths]
    if any(present):
        _require(all(present), "existing house success is incomplete")
        public_receipt = read_json(public_receipt_path)
        private_receipt = read_json(private_receipt_path)
        _require(public_receipt.get("split") == row["split"] and
                 public_receipt.get("sample_rank") == row["sample_rank"] and
                 public_receipt.get("public_house_ref") ==
                 row["public_house_ref"],
                 "existing public house receipt does not match its plan row")
        public_digest = public_receipt.get("public_receipt_sha256")
        public_payload = dict(public_receipt)
        public_payload.pop("public_receipt_sha256", None)
        _require(public_digest == hashlib.sha256(
            canonical_json(public_payload).encode("utf-8")).hexdigest(),
            "existing public house receipt digest changed")
        _require(public_receipt.get("rgbd_npz_sha256") == sha256(public_path),
                 "existing public RGB-D bytes changed")
        _require(private_receipt.get("split") == row["split"] and
                 private_receipt.get("sample_rank") == row["sample_rank"] and
                 private_receipt.get("house_id") == row["house_id"] and
                 private_receipt.get("source_record_sha256") ==
                 row["source_record_sha256"] and
                 private_receipt.get("public_receipt_sha256") == public_digest,
                 "existing private house receipt does not match its plan row")
        private_digest = private_receipt.get("private_receipt_sha256")
        private_payload = dict(private_receipt)
        private_payload.pop("private_receipt_sha256", None)
        _require(private_digest == hashlib.sha256(
            canonical_json(private_payload).encode("utf-8")).hexdigest(),
            "existing private house receipt digest changed")
        return {
            "split": row["split"], "sample_rank": row["sample_rank"],
            "success": True, "reused": True,
            "public_receipt_sha256": public_digest,
            "private_receipt_sha256": private_digest,
            "public_file_bytes": public_path.stat().st_size,
        }
    failure = private / "failure.json"
    if failure.is_file():
        failure_record = read_json(failure)
        _require(failure_record.get("split") == row["split"] and
                 failure_record.get("sample_rank") == row["sample_rank"] and
                 failure_record.get("house_id") == row["house_id"] and
                 failure_record.get("replacement_allowed") is False,
                 "existing house failure does not match its plan row")
        return {"split": row["split"], "sample_rank": row["sample_rank"],
                "success": False, "reused": True,
                "failure_sha256": sha256(failure)}
    return None


def generate_train_calibration(*, output_root: Path,
                               source_root: Path) -> dict[str, Any]:
    _, _, contract = load_contracts()
    activation = _execution_checkout(contract)
    _require(contract["authorization"]["train_rgbd_generation"] is True and
             contract["authorization"]["calibration_rgbd_generation"] is True,
             "D-217 train/calibration RGB-D generation is not authorized")
    final_receipt_path = output_root / "private/generation.receipt.json"
    if final_receipt_path.is_file():
        return read_json(final_receipt_path)
    capacity_path = output_root / "private/capacity.receipt.json"
    _require(capacity_path.is_file(), "D-217 capacity receipt is missing")
    capacity = read_json(capacity_path)
    workers = capacity["actual_batch_workers"]
    plan = read_json(output_root / "private/plan/private_plan.json")
    rows = sorted(plan["rows"], key=lambda row: (
        ("train", "calibration").index(row["split"]), row["sample_rank"]))
    existing = {(row["split"], row["sample_rank"]):
                _existing_result(output_root, row) for row in rows}
    pending = [row for row in rows
               if existing[(row["split"], row["sample_rank"])] is None]
    before = _resource_snapshot(output_root)
    _require(before["disk_free_bytes"] >= contract["resource_policy"]
             ["minimum_free_disk_bytes_before_batch"],
             "generation disk guard failed")
    started_path = output_root / "private/generation.started.json"
    started_record = {
        "schema_version": "vsmt-vm04-d217-generation-started-v1",
        "activation_commit": activation, "actual_workers": workers,
        "total_planned_houses": len(rows),
        "reused_completed_houses": len(rows) - len(pending),
        "pending_houses": len(pending), "resources": before,
        "audit_opened": False, "wall_clock_timeout_used": False,
    }
    if not started_path.exists():
        write_new_json(started_path, started_record, private=True)
    results = _run_group(
        _tasks(output_root, source_root, contract, pending), workers) if pending else []
    all_results = []
    by_key = {(row["split"], row["sample_rank"]): row for row in results}
    for row in rows:
        key = (row["split"], row["sample_rank"])
        all_results.append(by_key.get(key, existing[key]))
    failures = [row for row in all_results if not row["success"]]
    receipt = {
        "schema_version": "vsmt-vm04-d217-generation-receipt-v1",
        "activation_commit": activation, "actual_workers": workers,
        "task_order": "train_then_calibration_then_sample_rank",
        "house_results": all_results,
        "success_count": len(all_results) - len(failures),
        "failure_count": len(failures),
        "all_planned_houses_finished": True,
        "all_planned_houses_succeeded": not failures,
        "audit_opened_or_generated": False,
        "semantic_annotation_performed": False,
        "feature_materialization_performed": False,
        "production_reader_route_or_raw_performed": False,
        "resources_after": _resource_snapshot(output_root),
    }
    write_new_json(output_root / "private/generation.receipt.json", receipt,
                   private=True)
    if not failures:
        write_new_json(output_root / "private/generation.success.json", {
            "schema_version": "vsmt-vm04-d217-generation-success-v1",
            "generation_receipt_sha256": sha256(
                output_root / "private/generation.receipt.json"),
            "house_count": len(all_results), "observation_count":
                len(all_results) * 32, "audit_opened": False,
        }, private=True)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check")
    plan = commands.add_parser("seal-plan")
    plan.add_argument("--source-inventory", type=Path, required=True)
    plan.add_argument("--output-root", type=Path, required=True)
    probe = commands.add_parser("capacity-probe")
    probe.add_argument("--source-root", type=Path, required=True)
    probe.add_argument("--output-root", type=Path, required=True)
    generate = commands.add_parser("generate-train-calibration")
    generate.add_argument("--source-root", type=Path, required=True)
    generate.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "check":
        result = check()
    elif args.command == "seal-plan":
        result = seal_plan(source_inventory_path=args.source_inventory,
                           output_root=args.output_root)
    elif args.command == "capacity-probe":
        result = capacity_probe(output_root=args.output_root,
                                source_root=args.source_root)
    else:
        result = generate_train_calibration(
            output_root=args.output_root, source_root=args.source_root)
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
