#!/usr/bin/env python3
"""F-00 contract check and closed-by-default two-house topology precheck."""

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
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
OPS = Path(__file__).resolve().parent
for item in (SRC, OPS):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt.d215_frontend_freeze import validate_d215_contract  # noqa: E402
from vsmt.d223_f00_topology_precheck import (  # noqa: E402
    assert_real_precheck_authorized,
    make_public_summary,
    validate_f00_contract,
)
from vsmt.two_house_audit import validate_source_inventory  # noqa: E402
from vm04_d223_f00_worker import precheck_house  # noqa: E402


F00_PATH = ROOT / "configs/vsmt/vm04_d223_f00_topology_precheck_v1.json"
D223_PATH = ROOT / "configs/vsmt/vm04_d223_p08_topological_qualification_v1.json"
D215_PATH = ROOT / "configs/vsmt/vm04_d215_frontend_freeze_v1.json"
D211_PATH = ROOT / "configs/vsmt/vm04_d211_p0_seal_single_smoke_v2.json"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"),
                      object_pairs_hook=_reject_duplicates)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_new_json(path: Path, value: Any, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                         0o600 if private else 0o644)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json(value))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def git(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=ROOT, text=True).strip()


def load_contracts() -> tuple[dict[str, Any], dict[str, Any]]:
    raw_f00, d223, raw_d215, d211 = (
        read_json(F00_PATH), read_json(D223_PATH), read_json(D215_PATH),
        read_json(D211_PATH))
    d215 = validate_d215_contract(raw_d215)
    bindings = raw_f00["bindings"]
    for path, field in (
        (D223_PATH, "d223_file_sha256"),
        (D215_PATH, "d215_file_sha256"),
        (D211_PATH, "d211_source_binding_file_sha256"),
    ):
        _require(sha256(path) == bindings[field],
                 f"bound contract bytes changed: {path.name}")
    f00 = validate_f00_contract(
        raw_f00, d223_contract=d223, d215_contract=d215,
        d211_contract=d211)
    return f00, d223


def check() -> dict[str, Any]:
    contract, _ = load_contracts()
    return {
        "stage_id": "F-00", "status": contract["status"],
        "authorization": contract["authorization"],
        "fixed_house_slots": [row["house_slot"]
                              for row in contract["fixed_houses"]],
        "requested_worker_count":
            contract["resource_policy"]["requested_worker_count"],
        "real_simulator_queried": False, "outputs_written": False,
    }


def _execution_checkout(contract: dict[str, Any]) -> str:
    """Authorize one real F-00 run under the D-220 execution protocol.

    The earlier activation-child gate is gone; see the same function in
    ``vm04_d223_f01_production_reader.py`` for why D-220 removed it.  The
    already exported F-00 result stays valid: it was produced from these same
    reachable positions and the same frozen rule, and only the gate around the
    run changed.
    """

    assert_real_precheck_authorized(contract)
    _require(not git("status", "--porcelain"),
             "F-00 execution requires a clean checkout")
    return git("rev-parse", "HEAD")


def _resource_snapshot(path: Path) -> dict[str, Any]:
    try:
        import psutil
        cpus = int(psutil.cpu_count(logical=True) or 1)
        ram = int(psutil.virtual_memory().available)
    except ImportError:
        cpus, ram = int(os.cpu_count() or 1), None
    return {
        "logical_cpu_count": cpus, "available_ram_bytes": ram,
        "disk_free_bytes": shutil.disk_usage(path).free,
        "gpu_required": False,
    }


def run(*, source_inventory_path: Path, source_root: Path,
        output_root: Path) -> dict[str, Any]:
    contract, _ = load_contracts()
    execution_commit = _execution_checkout(contract)
    _require(not output_root.exists(), "F-00 output root already exists")
    resources = _resource_snapshot(output_root.parent.resolve())
    policy = contract["resource_policy"]
    _require(resources["logical_cpu_count"] >= 2,
             "F-00 needs two safe workers for two independent houses")
    _require(resources["available_ram_bytes"] is None or
             resources["available_ram_bytes"] >=
             policy["minimum_available_ram_bytes"],
             "F-00 available RAM guard failed")
    _require(resources["disk_free_bytes"] >= policy["minimum_free_disk_bytes"],
             "F-00 free disk guard failed")

    inventory = validate_source_inventory(read_json(source_inventory_path))
    indexed = {row["house_id"]: row for row in inventory["houses"]}
    tasks = []
    for fixed in contract["fixed_houses"]:
        row = indexed.get(fixed["source_house_id"])
        _require(row is not None and
                 row["source_record_sha256"] == fixed["source_record_sha256"],
                 "fixed house is absent from inventory or its digest changed")
        tasks.append({
            "row": {**fixed, "source_locator": row["source_locator"]},
            "source_root": str(source_root), "contract": contract,
        })
    with ProcessPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(precheck_house, tasks))
    outcomes.sort(key=lambda row: row["house_slot"])
    for outcome in outcomes:
        write_new_json(output_root / "private" /
                       f"house_slot_{outcome['house_slot']}.json",
                       outcome, private=True)
    summary = make_public_summary(
        outcomes, requested_worker_count=2, actual_worker_count=2,
        resource_basis=resources, execution_commit=execution_commit)
    write_new_json(output_root / "public" / "summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check")
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--source-inventory", type=Path, required=True)
    run_parser.add_argument("--source-root", type=Path, required=True)
    run_parser.add_argument("--output-root", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == "check":
        result = check()
    else:
        result = run(
            source_inventory_path=arguments.source_inventory,
            source_root=arguments.source_root,
            output_root=arguments.output_root)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
