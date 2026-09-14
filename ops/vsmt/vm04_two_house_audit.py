#!/usr/bin/env python3
"""Fixed entrypoint for the D-148 VM-04 two-house development audit.

Run boundaries are intentionally separate:

``contracts`` -> ``inventory`` -> ``select`` -> user confirmation ->
``capacity`` -> ``generate`` -> ``materialize`` -> ``public-seal`` ->
``private-eval`` -> ``verify`` -> ``export``.

The implementation may be reviewed while every action bit is closed.  The
entrypoint never treats implementation authorization as permission to inspect
the source dataset or generate an episode.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import subprocess
import sys
import time
from typing import Any, Iterable, Iterator, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt.two_house_audit import (  # noqa: E402
    assert_two_house_action_authorized,
    capacity_probe,
    evaluate_private_recall,
    make_episode_plans,
    make_public_seal,
    make_source_inventory,
    select_audit_houses,
    validate_episode_plans,
    validate_house_selection,
    validate_public_episode_plan,
    validate_source_inventory,
    validate_two_house_config,
)


STAGE_ID = "vsmt-vm04-two-house-audit-v1"
CONFIG_PATH = PROJECT_ROOT / "configs/vsmt/vm04_l1_two_house_audit_proposal_v1.json"
ENVIRONMENT_PATH = PROJECT_ROOT / "configs/vsmt/vm04_l1_environment_v1.json"
ACTION_PATH = PROJECT_ROOT / "configs/vsmt/vm04_l1_action_symmetry_v1.json"
STRUCTURE_PATH = PROJECT_ROOT / "configs/vsmt/vm04_l1_non_entity_geometry_review_v1.json"
REPORT_PATH = PROJECT_ROOT / "results/vsmt_vm04_l1_two_house_audit.json"
BOUND_PATHS = (
    "configs/vsmt/vm04_l1_two_house_audit_proposal_v1.json",
    "configs/vsmt/vm04_l1_environment_v1.json",
    "configs/vsmt/vm04_l1_action_symmetry_v1.json",
    "configs/vsmt/vm04_l1_non_entity_geometry_review_v1.json",
    "ops/vsmt/vm04_two_house_audit.py",
    "ops/vsmt/vm04_two_house_worker.py",
    "src/vsmt/two_house_audit.py",
    "src/vsmt/l1_entities.py",
    "src/vsmt/l1_masks.py",
    "src/vsmt/l1_structures.py",
    "src/vsmt/causal_prior.py",
    "src/vsmt/public_candidates.py",
    "src/vsmt/shared_memory.py",
    "src/vsmt/contracts.py",
    "tests/test_vsmt_two_house_audit.py",
    "tests/test_vsmt_two_house_ops.py",
)
TEST_GROUPS = (
    ("executor", "test_executor.py", 42),
    ("l1", "test_l1_*.py", 31),
    ("vsmt", "test_vsmt_*.py", 131),
)
HEX40 = re.compile(r"^[0-9a-f]{40}$")


class ResourceLimitReached(RuntimeError):
    """A frozen stage resource ceiling was reached."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_new_json(path: Path, value: Any, *, maximum_bytes: int | None = None) -> None:
    payload = (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )
    if maximum_bytes is not None and len(payload) > maximum_bytes:
        raise RuntimeError(f"JSON exceeds {maximum_bytes} bytes: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def write_new_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def git(*arguments: str, cwd: Path = PROJECT_ROOT) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=cwd, text=True, timeout=120,
    ).strip()


def load_config() -> dict[str, Any]:
    return validate_two_house_config(read_json(CONFIG_PATH))


def verify_checkout(reviewed_code: str) -> tuple[str, dict[str, str]]:
    root = Path(git("rev-parse", "--show-toplevel")).resolve()
    require(root == PROJECT_ROOT.resolve(), f"repository root mismatch: {root}")
    head = git("rev-parse", "HEAD")
    require(head == reviewed_code, f"HEAD {head} is not reviewed code {reviewed_code}")
    require(not git("status", "--porcelain"), "checkout is not clean")
    bindings: dict[str, str] = {}
    for relative in BOUND_PATHS:
        path = PROJECT_ROOT / relative
        require(path.is_file(), f"missing bound file: {relative}")
        bindings[relative] = sha256(path)
    return head, bindings


def stage_directory(output_root: Path, reviewed_code: str) -> Path:
    return output_root.resolve() / f"{STAGE_ID}-{reviewed_code[:12]}"


def run_command(
    command: Sequence[str], *, timeout: int, cwd: Path = PROJECT_ROOT,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    completed = subprocess.run(
        list(command), cwd=cwd, env=None if environment is None else dict(environment),
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout,
    )
    return {
        "command": list(command), "exit_code": completed.returncode,
        "wall_seconds": time.monotonic() - started, "output": completed.stdout,
    }


def _marker(stage: Path, name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    receipt_path = stage / f"{name}.receipt.json"
    success_path = stage / f"{name}.success.json"
    require(receipt_path.is_file() and success_path.is_file(),
            f"{name} receipt and success marker are required")
    receipt = read_json(receipt_path)
    success = read_json(success_path)
    require(receipt.get("success") is True
            and success.get("receipt_sha256") == sha256(receipt_path),
            f"{name} receipt binding is invalid")
    return receipt, success


def run_contracts(reviewed_code: str, output_root: Path) -> None:
    config = load_config()
    commit, bindings = verify_checkout(reviewed_code)
    stage = stage_directory(output_root, commit)
    require(not stage.exists(), f"stage directory already exists: {stage}")
    stage.mkdir(parents=True)
    maximum = int(config["resource_and_worker_proposal"]["maximum_report_bytes"])
    write_new_json(stage / "started.json", {
        "schema_version": "vsmt-vm04-two-house-started-v1",
        "stage_id": STAGE_ID,
        "reviewed_code": commit,
        "bound_sha256": bindings,
        "implementation_authorized": True,
        "source_inventory_authorized": config["source_inventory_authorized"],
        "generation_authorized": config["generation_authorized"],
        "private_audit_authorized": config["private_audit_authorized"],
        "training_authorized": False,
        "confirmation_authorized": False,
    }, maximum_bytes=maximum)
    groups: list[dict[str, Any]] = []
    test_environment = dict(os.environ)
    test_environment["PYTHONPATH"] = os.pathsep.join(filter(None, (
        str(SRC_ROOT), test_environment.get("PYTHONPATH", ""),
    )))
    for name, pattern, expected in TEST_GROUPS:
        require(expected > 0, f"reviewed exact test count is unset for {name}")
        result = run_command([
            sys.executable, "-B", "-m", "unittest", "discover", "-s",
            str(PROJECT_ROOT / "tests"), "-p", pattern, "-v",
        ], timeout=600, environment=test_environment)
        log_path = stage / f"contracts.{name}.unittest.log"
        log_path.write_text(result["output"], encoding="utf-8")
        print(result["output"], end="")
        observed_values = re.findall(r"Ran (\d+) tests?", result["output"])
        observed = int(observed_values[-1]) if observed_values else None
        groups.append({
            "name": name, "pattern": pattern, "expected_tests": expected,
            "observed_tests": observed, "exit_code": result["exit_code"],
            "success": result["exit_code"] == 0 and observed == expected,
            "wall_seconds": result["wall_seconds"], "log_sha256": sha256(log_path),
        })
    success = all(row["success"] for row in groups)
    receipt = {
        "schema_version": "vsmt-vm04-two-house-contract-receipt-v1",
        "stage_id": STAGE_ID, "reviewed_code": commit,
        "bound_sha256": bindings, "groups": groups,
        "observed_tests": sum(int(row["observed_tests"] or 0) for row in groups),
        "success": success, "source_inventory_performed": False,
        "selection_performed": False, "generation_performed": False,
        "training_steps": 0, "private_data_opened": False,
        "confirmation_data_opened": False,
    }
    receipt_path = stage / "contracts.receipt.json"
    write_new_json(receipt_path, receipt, maximum_bytes=maximum)
    if not success:
        raise SystemExit(1)
    write_new_json(stage / "contracts.success.json", {
        "schema_version": "vsmt-vm04-two-house-contract-success-v1",
        "reviewed_code": commit, "receipt_sha256": sha256(receipt_path),
        "observed_tests": receipt["observed_tests"], "success": True,
    }, maximum_bytes=maximum)
    print(f"VM04_TWO_HOUSE_CONTRACTS_OK stage={stage} tests={receipt['observed_tests']}")


def _open_text(path: Path):
    return gzip.open(path, "rt", encoding="utf-8") if path.name.endswith(".gz") else path.open(
        "r", encoding="utf-8"
    )


def _source_json_files(source_root: Path, explicit: Sequence[Path]) -> list[Path]:
    root = source_root.resolve()
    require(root.is_dir(), f"source root does not exist: {root}")
    if explicit:
        files = [(path if path.is_absolute() else root / path).resolve() for path in explicit]
    else:
        files = sorted(path.resolve() for path in root.rglob("*") if path.is_file()
                       and any(path.name.endswith(suffix) for suffix in (
                           ".json", ".jsonl", ".json.gz", ".jsonl.gz",
                       )) and "train" in "/".join(path.relative_to(root).parts).lower())
    require(files, "no author-train JSON source files were found")
    for path in files:
        require(path.is_file(), f"source file is missing: {path}")
        require(root == path or root in path.parents,
                f"source file escapes source root: {path}")
        require("train" in "/".join(path.relative_to(root).parts).lower(),
                f"source file is not explicitly author-train: {path}")
    return sorted(set(files))


def _records_from_json(path: Path) -> Iterator[tuple[int, Mapping[str, Any]]]:
    with _open_text(path) as handle:
        if path.name.endswith(".jsonl") or path.name.endswith(".jsonl.gz"):
            for index, line in enumerate(handle):
                if line.strip():
                    value = json.loads(line)
                    require(type(value) is dict, f"source JSONL row is not an object: {path}")
                    yield index, value
            return
        value = json.load(handle)
    if type(value) is dict and type(value.get("train")) is list:
        rows = value["train"]
    elif type(value) is dict and type(value.get("houses")) is list:
        rows = value["houses"]
    elif type(value) is list:
        rows = value
    elif type(value) is dict:
        rows = [value]
    else:
        raise RuntimeError(f"unsupported source JSON shape: {path}")
    for index, row in enumerate(rows):
        require(type(row) is dict, f"source row {index} is not an object: {path}")
        yield index, row


def _explicit_house_id(row: Mapping[str, Any]) -> str | None:
    for key in ("house_id", "houseId", "id"):
        value = row.get(key)
        if type(value) in (str, int) and str(value):
            return str(value)
    metadata = row.get("metadata")
    if type(metadata) is dict:
        for key in ("sceneName", "houseId", "id"):
            value = metadata.get(key)
            if type(value) in (str, int) and str(value):
                return str(value)
    return None


def inventory_source_rows(
    source_root: Path, source_files: Sequence[Path], license_paths: Sequence[Path],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Read a local author-train snapshot without ranking or selecting a house."""

    root = source_root.resolve()
    files = _source_json_files(root, source_files)
    rows: list[dict[str, Any]] = []
    ordinal = 0
    for path in files:
        file_digest = sha256(path)
        relative = path.relative_to(root).as_posix()
        for index, record in _records_from_json(path):
            house_id = _explicit_house_id(record) or f"train:{ordinal:06d}"
            rows.append({
                "house_id": house_id,
                "source_file_sha256": file_digest,
                "source_record_sha256": canonical_sha256(record),
                "source_locator": {"relative_path": relative, "index": index},
            })
            ordinal += 1
    licenses: list[dict[str, Any]] = []
    require(license_paths, "at least one explicit license path is required")
    for raw in license_paths:
        path = raw.resolve()
        require(path.is_file(), f"license file is missing: {path}")
        require(root == path or root in path.parents,
                f"license file escapes source root: {path}")
        licenses.append({"name": path.name, "sha256": sha256(path), "bytes": path.stat().st_size})
    return rows, licenses


def run_inventory(
    reviewed_code: str, output_root: Path, *, source_root: Path,
    source_files: Sequence[Path], license_paths: Sequence[Path],
) -> None:
    config = assert_two_house_action_authorized(load_config(), action="inventory")
    commit, bindings = verify_checkout(reviewed_code)
    stage = stage_directory(output_root, commit)
    _marker(stage, "contracts")
    require(not (stage / "inventory.receipt.json").exists(),
            "inventory already has a terminal receipt")
    started = time.monotonic()
    source = config["source_inventory_proposal"]
    require((source_root.resolve() / ".git").exists(),
            "source root must be the pinned ProcTHOR-10K git checkout")
    observed_source_commit = git("rev-parse", "HEAD", cwd=source_root.resolve())
    require(observed_source_commit == source["data_release_commit"],
            "ProcTHOR-10K source checkout commit mismatch")
    houses, licenses = inventory_source_rows(source_root, source_files, license_paths)
    inventory = make_source_inventory(
        houses, source_release_commit=source["data_release_commit"],
        license_files=licenses,
    )
    maximum = int(config["resource_and_worker_proposal"]["maximum_report_bytes"])
    private_path = stage / "private/inventory.json"
    write_new_json(private_path, inventory, maximum_bytes=maximum)
    public_inventory = {
        key: value for key, value in inventory.items() if key not in {"houses"}
    }
    public_inventory["house_locator_rows_withheld"] = len(inventory["houses"])
    receipt = {
        "schema_version": "vsmt-vm04-two-house-inventory-receipt-v1",
        "stage_id": STAGE_ID, "reviewed_code": commit,
        "bound_sha256": bindings, "success": True,
        "source_release_commit": observed_source_commit,
        "source_root_sha256": hashlib.sha256(
            str(source_root.resolve()).encode("utf-8")
        ).hexdigest(),
        "inventory": public_inventory,
        "private_inventory_sha256": sha256(private_path),
        "wall_seconds": time.monotonic() - started,
        "selection_performed": False, "generation_performed": False,
        "training_steps": 0, "private_data_opened": False,
        "confirmation_data_opened": False,
    }
    receipt_path = stage / "inventory.receipt.json"
    write_new_json(receipt_path, receipt, maximum_bytes=maximum)
    write_new_json(stage / "inventory.success.json", {
        "schema_version": "vsmt-vm04-two-house-inventory-success-v1",
        "reviewed_code": commit, "receipt_sha256": sha256(receipt_path),
        "inventory_sha256": inventory["inventory_sha256"], "success": True,
    }, maximum_bytes=maximum)
    print(
        "VM04_TWO_HOUSE_INVENTORY_OK "
        f"stage={stage} houses={inventory['house_count']} "
        f"manifest={inventory['source_manifest_sha256']}"
    )


def run_selection(reviewed_code: str, output_root: Path) -> None:
    config = assert_two_house_action_authorized(load_config(), action="select")
    commit, bindings = verify_checkout(reviewed_code)
    stage = stage_directory(output_root, commit)
    _marker(stage, "contracts")
    inventory_receipt, _ = _marker(stage, "inventory")
    require(not (stage / "selection.receipt.json").exists(),
            "selection already has a terminal receipt")
    inventory_path = stage / "private/inventory.json"
    require(sha256(inventory_path) == inventory_receipt["private_inventory_sha256"],
            "private inventory changed after its receipt")
    inventory = validate_source_inventory(read_json(inventory_path))
    source = config["source_inventory_proposal"]
    require(inventory["source_manifest_sha256"] == inventory_receipt["inventory"][
        "source_manifest_sha256"
    ], "inventory public/private digest mismatch")
    selection = select_audit_houses(
        inventory, split_seed=int(config["family_selection_proposal"]["split_seed"]),
    )
    salt = secrets.token_bytes(32)
    plans = make_episode_plans(
        selection, inventory=inventory, assignment_salt=salt,
        config_version=config["version"],
    )
    maximum = int(config["resource_and_worker_proposal"]["maximum_report_bytes"])
    write_new_json(stage / "selection.json", selection, maximum_bytes=maximum)
    write_new_json(stage / "public/episode_plan.json", plans["public"], maximum_bytes=maximum)
    write_new_json(stage / "private/episode_plan.json", plans["private"], maximum_bytes=maximum)
    write_new_bytes(stage / "private/assignment_salt.bin", salt)
    receipt = {
        "schema_version": "vsmt-vm04-two-house-selection-receipt-v1",
        "stage_id": STAGE_ID, "reviewed_code": commit,
        "bound_sha256": bindings, "success": True,
        "inventory_sha256": inventory["inventory_sha256"],
        "source_manifest_sha256": inventory["source_manifest_sha256"],
        "license_snapshot_sha256": inventory["license_snapshot_sha256"],
        "eligible_house_ids_sha256": inventory["eligible_house_ids_sha256"],
        "selection_sha256": selection["selection_sha256"],
        "audit_house_ids": selection["audit_house_ids"],
        "public_episode_manifest_sha256": plans["public"]["manifest_sha256"],
        "private_episode_manifest_sha256": plans["private"]["manifest_sha256"],
        "private_program_assignment_salt_sha256": hashlib.sha256(salt).hexdigest(),
        "house_selection_shared_inventory_run": False,
        "generation_performed": False, "training_steps": 0,
        "private_data_opened": False, "confirmation_data_opened": False,
    }
    receipt_path = stage / "selection.receipt.json"
    write_new_json(receipt_path, receipt, maximum_bytes=maximum)
    write_new_json(stage / "selection.success.json", {
        "schema_version": "vsmt-vm04-two-house-selection-success-v1",
        "reviewed_code": commit, "receipt_sha256": sha256(receipt_path),
        "selection_sha256": selection["selection_sha256"], "success": True,
    }, maximum_bytes=maximum)
    print(
        "VM04_TWO_HOUSE_SELECTION_OK "
        f"stage={stage} audit_house_ids={json.dumps(selection['audit_house_ids'])}"
    )


def run_capacity(
    reviewed_code: str, output_root: Path, *, planning_stage: Path,
    predicted_wall_seconds: float, predicted_stage_bytes: int,
) -> None:
    config = assert_two_house_action_authorized(load_config(), action="generate")
    commit, bindings = verify_checkout(reviewed_code)
    stage = stage_directory(output_root, commit)
    _marker(stage, "contracts")
    selection_receipt, _ = _marker(planning_stage.resolve(), "selection")
    _verify_frozen_selection(config, selection_receipt)
    resources = config["resource_and_worker_proposal"]
    probe = capacity_probe(
        free_bytes=shutil.disk_usage(output_root.resolve()).free,
        visible_cpu_count=os.cpu_count() or 0,
        requested_workers=int(resources["simulator_house_family_workers"]),
        predicted_wall_seconds=predicted_wall_seconds,
        predicted_stage_bytes=predicted_stage_bytes,
        config=config,
    )
    receipt = {
        "schema_version": "vsmt-vm04-two-house-capacity-receipt-v1",
        "stage_id": STAGE_ID, "reviewed_code": commit,
        "bound_sha256": bindings, "planning_selection_receipt_sha256": sha256(
            planning_stage.resolve() / "selection.receipt.json"
        ), "probe": probe, "success": probe["ready"],
        "generation_started": False,
    }
    receipt_path = stage / "capacity.receipt.json"
    write_new_json(receipt_path, receipt)
    if not probe["ready"]:
        print(f"VM04_TWO_HOUSE_CAPACITY_NOT_READY stage={stage}")
        raise SystemExit(1)
    write_new_json(stage / "capacity.success.json", {
        "schema_version": "vsmt-vm04-two-house-capacity-success-v1",
        "reviewed_code": commit, "receipt_sha256": sha256(receipt_path),
        "success": True,
    })
    print(f"VM04_TWO_HOUSE_CAPACITY_OK stage={stage}")


def _verify_frozen_selection(
    config: Mapping[str, Any], selection_receipt: Mapping[str, Any],
) -> None:
    source = config["source_inventory_proposal"]
    expected = {
        "source_manifest_sha256": source["source_manifest_sha256"],
        "license_snapshot_sha256": source["license_snapshot_sha256"],
        "eligible_house_ids_sha256": source["eligible_house_ids_sha256"],
        "audit_house_ids": source["audit_house_ids"],
        "private_program_assignment_salt_sha256": config[
            "family_selection_proposal"
        ]["private_program_assignment_salt_sha256"],
    }
    for key, value in expected.items():
        require(selection_receipt.get(key) == value,
                f"frozen selection mismatch: {key}")


def _directory_bytes(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _linux_process_tree_rss_bytes(root_pids: Iterable[int]) -> int:
    """Read Linux process-tree RSS without adding a runtime dependency."""

    pending = [int(pid) for pid in root_pids]
    observed: set[int] = set()
    total = 0
    while pending:
        pid = pending.pop()
        if pid in observed:
            continue
        observed.add(pid)
        status = Path(f"/proc/{pid}/status")
        children = Path(f"/proc/{pid}/task/{pid}/children")
        if status.is_file():
            for line in status.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("VmRSS:"):
                    total += int(line.split()[1]) * 1024
                    break
        if children.is_file():
            pending.extend(int(value) for value in children.read_text().split())
    return total


def _resource_checkpoint(
    stage: Path, config: Mapping[str, Any], *, started: float,
    root_pids: Iterable[int] = (), include_gpu: bool = False,
) -> dict[str, float | int]:
    """Fail closed on the frozen wall, stage, process-tree, and GPU ceilings."""

    resources = config["resource_and_worker_proposal"]
    elapsed = time.monotonic() - started
    stage_bytes = _directory_bytes(stage)
    roots = list(root_pids) or [os.getpid()]
    rss_bytes = _linux_process_tree_rss_bytes(roots)
    gpu_bytes = 0
    if include_gpu:
        import torch

        gpu_bytes = int(torch.cuda.memory_allocated())
    limits = (
        (elapsed <= int(resources["hard_wall_clock_seconds"]),
         "stage wall-clock limit reached"),
        (stage_bytes <= int(resources["maximum_stage_bytes"]),
         "stage byte limit reached"),
        (rss_bytes <= int(resources["maximum_process_tree_RSS_bytes"]),
         "process-tree RSS limit reached"),
        (gpu_bytes <= int(resources["maximum_GPU_allocated_bytes"]),
         "GPU allocation limit reached"),
    )
    for allowed, message in limits:
        if not allowed:
            raise ResourceLimitReached(message)
    return {
        "wall_seconds": elapsed, "stage_bytes": stage_bytes,
        "process_tree_RSS_bytes": rss_bytes, "GPU_allocated_bytes": gpu_bytes,
    }


def _abort_process(child: subprocess.Popen[str]) -> None:
    if child.poll() is not None:
        child.wait()
        return
    os.killpg(child.pid, signal.SIGTERM)
    try:
        child.wait(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGKILL)
        child.wait(timeout=10)


def run_generation(
    reviewed_code: str, output_root: Path, *, planning_stage: Path,
    source_root: Path,
) -> None:
    config = assert_two_house_action_authorized(load_config(), action="generate")
    commit, bindings = verify_checkout(reviewed_code)
    stage = stage_directory(output_root, commit)
    _marker(stage, "contracts")
    _marker(stage, "capacity")
    planning = planning_stage.resolve()
    selection_receipt, _ = _marker(planning, "selection")
    _verify_frozen_selection(config, selection_receipt)
    require(not (stage / "execution").exists(),
            "generation execution already exists; preserve it and verify")
    inventory_receipt, _ = _marker(planning, "inventory")
    require(hashlib.sha256(str(source_root.resolve()).encode("utf-8")).hexdigest()
            == inventory_receipt["source_root_sha256"],
            "generation source root differs from inventory")
    for relative in (
        "private/inventory.json", "private/episode_plan.json",
        "private/assignment_salt.bin", "public/episode_plan.json", "selection.json",
    ):
        source = planning / relative
        require(source.is_file(), f"planning artifact is missing: {relative}")
        write_new_bytes(stage / relative, source.read_bytes())
    salt = (stage / "private/assignment_salt.bin").read_bytes()
    require(hashlib.sha256(salt).hexdigest() == config["family_selection_proposal"][
        "private_program_assignment_salt_sha256"
    ], "private assignment salt changed")
    plans = validate_episode_plans({
        "public": read_json(stage / "public/episode_plan.json"),
        "private": read_json(stage / "private/episode_plan.json"),
    })
    family_ids = sorted({row["family_id"] for row in plans["public"]["episodes"]})
    require(len(family_ids) == 2, "generation needs exactly two families")
    execution = stage / "execution"
    execution.mkdir()
    environment_config = read_json(ENVIRONMENT_PATH)
    simulator_python = Path(environment_config["environment_separation"][
        "simulator_process"
    ]["environment_path"]) / "bin/python"
    require(simulator_python.is_file(), "reviewed simulator Python is missing")
    environment = dict(os.environ, XDG_RUNTIME_DIR=str(output_root.resolve() / "runtime"),
                       PYTHONUNBUFFERED="1", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
    Path(environment["XDG_RUNTIME_DIR"]).mkdir(parents=True, exist_ok=True)
    children: dict[str, subprocess.Popen[str]] = {}
    logs: dict[str, Any] = {}
    launches: list[dict[str, Any]] = []
    exits: list[dict[str, Any]] = []
    started = time.monotonic()
    resources = config["resource_and_worker_proposal"]
    try:
        for family_id in family_ids:
            family_root = execution / family_id
            family_root.mkdir()
            log_path = family_root / "worker.log"
            log = log_path.open("x", encoding="utf-8")
            child = subprocess.Popen([
                str(simulator_python), "-B",
                str(PROJECT_ROOT / "ops/vsmt/vm04_two_house_worker.py"),
                "--run-stage", str(stage), "--source-root", str(source_root.resolve()),
                "--family-id", family_id,
                "--family-byte-limit", str(resources["maximum_bytes_per_family"]),
                "--process-address-limit", str(resources["maximum_process_tree_RSS_bytes"]),
            ], cwd=PROJECT_ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT,
               text=True, start_new_session=True)
            log.close()
            children[family_id] = child
            logs[family_id] = log_path.open("r", encoding="utf-8", errors="replace")
            launches.append({"family_id": family_id, "pid": child.pid})
            write_new_json(family_root / "launched.json", launches[-1])
        active = set(family_ids)
        while active:
            _resource_checkpoint(
                stage, config, started=started,
                root_pids=(children[family_id].pid for family_id in active),
            )
            require(shutil.disk_usage(output_root.resolve()).free >= int(
                resources["minimum_free_data_disk_bytes_before_start"]
            ), "generation data-disk reserve crossed")
            for family_id in list(active):
                output = logs[family_id].read(8192)
                if output:
                    print(f"[{family_id}] {output}", end="", flush=True)
                child = children[family_id]
                if child.poll() is None:
                    continue
                child.wait()
                row = {"family_id": family_id, "pid": child.pid,
                       "exit_code": child.returncode}
                exits.append(row)
                write_new_json(execution / family_id / "exit.json", row)
                require(child.returncode == 0, f"family worker failed: {family_id}")
                active.remove(family_id)
            if active:
                time.sleep(0.1)
    except BaseException as error:
        for family_id, child in children.items():
            if child.poll() is None:
                try:
                    _abort_process(child)
                except BaseException:
                    pass
        not_started = [family for family in family_ids if family not in children]
        missing_exit = [family for family in children
                        if family not in {row["family_id"] for row in exits}]
        write_new_json(execution / "failure.json", {
            "error_type": type(error).__name__, "error": str(error),
            "launched": launches, "exits": exits, "not_started": not_started,
            "missing_exit": missing_exit, "wall_seconds": time.monotonic() - started,
        })
        raise
    finally:
        for family_id, handle in logs.items():
            output = handle.read()
            if output:
                print(f"[{family_id}] {output}", end="", flush=True)
            handle.close()
    worker_receipts = []
    for family_id in family_ids:
        path = execution / family_id / "worker.receipt.json"
        require(path.is_file(), f"family worker receipt missing: {family_id}")
        worker_receipts.append({"family_id": family_id, "sha256": sha256(path),
                                "summary": read_json(path)})
    process_record = {
        "requested_workers": 2, "actual_workers": len(children),
        "launched": launches, "exits": exits, "not_started": [], "missing_exit": [],
        "worker_completion_order": [row["family_id"] for row in exits],
        "wall_seconds": time.monotonic() - started,
    }
    write_new_json(execution / "processes.json", process_record)
    receipt = {
        "schema_version": "vsmt-vm04-two-house-generation-receipt-v1",
        "stage_id": STAGE_ID, "reviewed_code": commit, "bound_sha256": bindings,
        "success": True, "planning_selection_receipt_sha256": sha256(
            planning / "selection.receipt.json"
        ), "source_root_sha256": inventory_receipt["source_root_sha256"],
        "workers": process_record, "family_receipts": worker_receipts,
        "attempted_episode_count": sum(
            row["summary"]["completed_count"] + row["summary"]["failed_count"]
            for row in worker_receipts
        ),
        "raw_complete_episode_count": sum(
            row["summary"]["completed_count"] for row in worker_receipts
        ),
        "raw_failed_episode_count": sum(
            row["summary"]["failed_count"] for row in worker_receipts
        ),
        "raw_not_started_episode_count": sum(
            row["summary"].get("not_started_count", 0) for row in worker_receipts
        ),
        "generation_performed": True, "training_steps": 0,
        "private_data_opened_for_evaluation": False,
        "confirmation_data_opened": False,
    }
    receipt_path = stage / "generate.receipt.json"
    write_new_json(receipt_path, receipt)
    write_new_json(stage / "generate.success.json", {
        "schema_version": "vsmt-vm04-two-house-generation-success-v1",
        "reviewed_code": commit, "receipt_sha256": sha256(receipt_path),
        "attempted_episode_count": receipt["attempted_episode_count"],
        "not_started_episode_count": receipt["raw_not_started_episode_count"],
        "success": True,
    })
    print(f"VM04_TWO_HOUSE_GENERATE_OK stage={stage} slots=36")


def _materialization_configs() -> dict[str, Any]:
    from vsmt.l1_entities import AI2THOR_CAMERA_AXIS_Z, DINORegionConfig, PublicGeometryConfig
    from vsmt.l1_masks import KEEP_SUPPORTED_BORDER_REGIONS, L1MaskConfig
    from vsmt.l1_structures import (
        FreeSpaceMaterializationConfig, PlaceMaterializationConfig,
        SurfaceMaterializationConfig,
    )

    environment = read_json(ENVIRONMENT_PATH)
    structures = read_json(STRUCTURE_PATH)
    dino = environment["entity_materialization"]["dinov2"]
    geometry = environment["entity_materialization"]["public_geometry"]
    surface = structures["surface_proposal"]
    place = structures["place_proposal"]
    free = structures["free_space_proposal"]
    return {
        "mask": L1MaskConfig(
            minimum_visible_pixels=environment["entity_materialization"]["anonymous_mask"][
                "minimum_visible_pixels"
            ], border_truncation_policy=KEEP_SUPPORTED_BORDER_REGIONS,
        ),
        "descriptor": DINORegionConfig(
            image_height=dino["image_shape"][0], image_width=dino["image_shape"][1],
            patch_size_pixels=dino["patch_size_pixels"],
            patch_token_dimension=dino["patch_token_dimension"],
            minimum_total_patch_weight=dino["minimum_total_patch_weight"],
            unit_norm_validation_tolerance=dino["unit_norm_validation_tolerance"],
        ),
        "entity_geometry": PublicGeometryConfig(
            depth_convention=AI2THOR_CAMERA_AXIS_Z,
            minimum_depth_m=geometry["depth_valid_range_m"][0],
            maximum_depth_m=geometry["depth_valid_range_m"][1],
            absolute_minimum_valid_depth_points=geometry[
                "absolute_minimum_valid_depth_points"
            ], minimum_valid_depth_fraction=geometry["minimum_valid_depth_fraction"],
        ),
        "surface": SurfaceMaterializationConfig(
            tile_size_pixels=surface["base_tile_pixels"][0],
            minimum_valid_depth_fraction_per_tile=surface[
                "minimum_valid_depth_fraction_per_tile"
            ],
            initial_maximum_rms_point_to_plane_m=surface[
                "initial_maximum_rms_point_to_plane_m"
            ],
            initial_maximum_p95_point_to_plane_m=surface[
                "initial_maximum_p95_point_to_plane_m"
            ],
            merge_maximum_normal_angle_degrees=surface[
                "merge_maximum_normal_angle_degrees"
            ],
            merge_maximum_mutual_centroid_to_plane_m=surface[
                "merge_maximum_mutual_centroid_to_plane_m"
            ], final_inlier_point_to_plane_m=surface["final_inlier_point_to_plane_m"],
            final_minimum_inlier_fraction=surface["final_minimum_inlier_fraction"],
            final_maximum_rms_point_to_plane_m=surface[
                "final_maximum_rms_point_to_plane_m"
            ], minimum_inlier_pixels=surface["minimum_inlier_pixels"],
            minimum_depth_m=0.05, maximum_depth_m=20.0,
        ),
        "place": PlaceMaterializationConfig(
            maximum_floor_normal_angle_degrees=place[
                "maximum_floor_normal_angle_degrees"
            ], maximum_support_height_difference_m=place[
                "maximum_surface_height_difference_from_agent_support_m"
            ], cell_size_m=place["world_aligned_cell_size_m"],
            grid_origin_m=tuple(place["grid_origin_m"]),
            coverage_subcell_size_m=place["coverage_subcell_size_m"],
            minimum_covered_subcells=place["minimum_covered_subcells"],
            minimum_mask_pixels=place["minimum_mask_pixels"],
            camera_to_agent_center_y_m=structures["source_audit"][
                "standard_agent_camera_local_y_m"
            ], agent_half_height_m=structures["source_audit"][
                "standard_agent_character_controller_height_m"
            ] / 2.0, located_at_boundary_margin_m=0.02,
        ),
        "free": FreeSpaceMaterializationConfig(
            tile_size_pixels=free["base_tile_pixels"][0],
            block_widths_in_tiles=tuple(free["aligned_multiscale_block_widths_in_base_tiles"]),
            angular_boundary_erosion_pixels=free["angular_boundary_erosion_pixels"],
            minimum_depth_m=0.05, maximum_valid_depth_m=20.0,
            near_axis_depth_m=free["near_axis_depth_m"],
            surface_clearance_m=free["surface_clearance_m"],
            maximum_axis_depth_m=free["maximum_axis_depth_m"],
            minimum_longitudinal_thickness_m=free["minimum_longitudinal_thickness_m"],
            rolling_public_observation_times=free["rolling_public_observation_times"],
        ),
    }


def _mask_sha256(mask: Any) -> str:
    import numpy as np

    value = np.asarray(mask, dtype=np.bool_)
    return hashlib.sha256(canonical_json([
        value.shape[0], value.shape[1], *value.reshape(-1).astype(int).tolist(),
    ]).encode("utf-8")).hexdigest()


def materialize_public_frame(
    *, rgb: Any, depth: Any, camera: Mapping[str, Any],
    private_instance_ids: Sequence[str], mask_stack: Any,
    private_program: str, private_target_ids: Sequence[str],
    frame_index: int, patch_tokens: Any, prior_free_space: Sequence[Sequence[Mapping[str, Any]]],
    configs: Mapping[str, Any], episode_id: str,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Materialize one anonymous frame and return public bytes plus private crosswalk."""

    from dataclasses import replace
    import numpy as np

    from vsmt.l1_entities import DINORegionDescriptor, materialize_l1_entity_observation
    from vsmt.l1_masks import anonymize_instance_masks
    from vsmt.l1_structures import (
        assemble_free_space_history, assemble_region_records, entity_regions_with_masks,
        materialize_public_free_space, materialize_public_places,
        materialize_public_relations, materialize_public_surfaces,
        materialize_public_visibility,
    )

    stack = np.asarray(mask_stack, dtype=np.bool_)
    require(stack.ndim == 3 and stack.shape[0] == len(private_instance_ids),
            "private mask stack does not match its private ID list")
    source_masks = {str(key): stack[index] for index, key in enumerate(private_instance_ids)}
    final_masks: list[tuple[Any, list[str]]] = []
    targets = list(private_target_ids)
    if private_program == "SPLIT" and frame_index < 24 and len(targets) >= 2:
        require(targets[0] in source_masks and targets[1] in source_masks,
                "SPLIT target is not visible during its combined prefix")
        combined = np.logical_or(source_masks.pop(targets[0]), source_masks.pop(targets[1]))
        final_masks.append((combined, targets[:2]))
    final_masks.extend((mask, [private_id]) for private_id, mask in source_masks.items())
    anonymous_inputs = {
        f"anonymous-input:{index:04d}": mask
        for index, (mask, _) in enumerate(final_masks)
    }
    private_by_digest = {
        _mask_sha256(mask): ids for mask, ids in final_masks
    }
    anonymous = anonymize_instance_masks(anonymous_inputs, configs["mask"])
    entities = []
    for region in anonymous.regions:
        observation = materialize_l1_entity_observation(
            region, patch_tokens, depth, camera["calibration"], camera["pose"],
            configs["descriptor"], configs["entity_geometry"],
        )
        private_ids = private_by_digest[region.mask_sha256]
        if (private_program == "MERGE" and 8 <= frame_index <= 23
                and private_target_ids and private_target_ids[0] in private_ids):
            observation = replace(observation, descriptor=DINORegionDescriptor(
                values=tuple(-float(value) for value in observation.descriptor.values),
                total_patch_weight=observation.descriptor.total_patch_weight,
            ))
        entities.append(observation)
    surfaces = materialize_public_surfaces(
        depth, camera["calibration"], camera["pose"], patch_tokens,
        configs["descriptor"], configs["surface"],
    )
    places = materialize_public_places(
        surfaces, depth, camera["calibration"], camera["pose"], patch_tokens,
        configs["descriptor"], configs["surface"], configs["place"],
    ).regions
    entity_regions = entity_regions_with_masks(entities, anonymous.regions)
    regions, indexed = assemble_region_records(entity_regions, places, surfaces)
    relations = materialize_public_relations(
        indexed, place_config=configs["place"],
        supported_by_maximum_normal_angle_degrees=10.0,
        supported_by_minimum_gap_m=-0.02,
        supported_by_maximum_gap_m=0.05,
        supported_by_minimum_projected_overlap=0.25,
        supported_by_maximum_mask_overlap_fraction=0.05,
    )
    free_current = materialize_public_free_space(
        depth, camera["calibration"], camera["pose"],
        time_s=float(camera["time_s"]), depth_sha256=camera["depth_sha256"],
        camera_calibration_and_pose_sha256=canonical_sha256({
            "calibration": camera["calibration"], "pose": camera["pose"],
        }), config=configs["free"],
    )
    history = assemble_free_space_history(
        [*prior_free_space, free_current],
        rolling_public_observation_times=configs["free"].rolling_public_observation_times,
    )
    visibility = materialize_public_visibility(
        free_current, surface_clearance_m=configs["free"].surface_clearance_m,
    )
    public = {
        "schema_version": "vsmt-l1-anonymous-public-frame-v1",
        "episode_id_hash": hashlib.sha256(episode_id.encode("utf-8")).hexdigest(),
        "frame_index": frame_index, "decision_time_s": float(camera["time_s"]),
        "rgb_sha256": camera["rgb_sha256"], "depth_sha256": camera["depth_sha256"],
        "camera_pose": camera["pose"], "camera_calibration": camera["calibration"],
        "past_actions": camera["past_actions"],
        "region_observations": regions, "relation_observations": relations,
        "free_space_observations": history, "visibility_observations": visibility,
        "anonymous_mask_cache_sha256": anonymous.public_cache_sha256(),
        "private_mapping_present": False,
    }
    private_mapping = {
        "schema_version": "vsmt-l1-private-frame-crosswalk-v1",
        "episode_id": episode_id, "frame_index": frame_index,
        "entity_region_to_private_instance_ids": {
            region.region_id: private_by_digest[region.mask_sha256]
            for region in anonymous.regions
        },
        "public_frame_sha256": canonical_sha256(public),
    }
    return public, private_mapping, free_current


def _load_dino() -> tuple[Any, str]:
    import torch

    environment = read_json(ENVIRONMENT_PATH)
    frontend = environment["environment_separation"]["public_materializer_process"]
    repository = Path(frontend["DINOv2_repository"])
    checkpoint = Path(frontend["DINOv2_checkpoint"])
    require(repository.is_dir() and checkpoint.is_file(), "reviewed DINO assets are missing")
    require(git("rev-parse", "HEAD", cwd=repository) == frontend["DINOv2_repository_commit"],
            "DINO repository commit mismatch")
    require(sha256(checkpoint) == frontend["DINOv2_checkpoint_sha256"],
            "DINO checkpoint digest mismatch")
    require(torch.cuda.is_available(), "CUDA is required for L1 descriptor materialization")
    sys.path.insert(0, str(repository))
    from dinov2.hub.backbones import dinov2_vits14

    model = dinov2_vits14(pretrained=False)
    state = torch.load(checkpoint, map_location="cpu", weights_only=True)
    model.load_state_dict(state, strict=True)
    model.requires_grad_(False).eval().to("cuda")
    return model, str(frontend["DINOv2_repository_commit"])


def run_materializer(reviewed_code: str, output_root: Path) -> None:
    config = assert_two_house_action_authorized(load_config(), action="generate")
    commit, bindings = verify_checkout(reviewed_code)
    stage = stage_directory(output_root, commit)
    generate, _ = _marker(stage, "generate")
    require(not (stage / "materialized").exists(),
            "materialization already started; preserve and verify")
    from vsmt.l1_entities import extract_dinov2_patch_tokens
    import numpy as np

    plans = validate_episode_plans({
        "public": read_json(stage / "public/episode_plan.json"),
        "private": read_json(stage / "private/episode_plan.json"),
    })
    private_by_id = {row["episode_id"]: row for row in plans["private"]["assignments"]}
    model, dino_commit = _load_dino()
    configs = _materialization_configs()
    materialized = stage / "materialized"
    materialized.mkdir()
    public_root = materialized / "public"
    private_root = materialized / "private"
    started = time.monotonic()
    peak_rss_bytes = 0
    peak_gpu_bytes = 0
    results: list[dict[str, Any]] = []
    for public_plan in plans["public"]["episodes"]:
        episode_id = public_plan["episode_id"]
        assignment = private_by_id[episode_id]
        family_root = stage / "execution" / public_plan["family_id"] / "episodes" / episode_id
        output_public = public_root / episode_id
        output_private = private_root / episode_id
        output_public.mkdir(parents=True)
        output_private.mkdir(parents=True)
        raw_failure = family_root / "raw.failure.json"
        raw_not_started = family_root / "raw.not-started.json"
        if raw_failure.exists() or raw_not_started.exists():
            terminal_path = raw_failure if raw_failure.exists() else raw_not_started
            failure = read_json(terminal_path)
            write_new_json(output_public / "failure.json", {
                "episode_id": episode_id,
                "reason": ("raw_generation_failed" if raw_failure.exists()
                           else "not_started_after_resource_stop"),
                "raw_terminal_sha256": sha256(terminal_path),
            })
            write_new_json(output_private / "failure.json", {
                "episode_id": episode_id, "program": assignment["program"],
                "raw_terminal": failure,
            })
            results.append({"episode_id": episode_id, "status": "failed",
                            "reason": ("raw_generation_failed" if raw_failure.exists()
                                       else "not_started_after_resource_stop")})
            continue
        intervention = read_json(family_root / "private/intervention.json")
        prior_free: list[list[dict[str, Any]]] = []
        frame_records: list[dict[str, Any]] = []
        failed: str | None = None
        failed_type: str | None = None
        for frame_index in range(32):
            try:
                raw_public = family_root / "public" / f"frame_{frame_index:04d}"
                raw_private = family_root / "private" / f"frame_{frame_index:04d}"
                rgb = np.load(raw_public / "rgb.npy", allow_pickle=False)
                depth = np.load(raw_public / "depth.npy", allow_pickle=False)
                camera = read_json(raw_public / "camera.json")
                private = read_json(raw_private / "mapping.json")
                masks = np.load(raw_private / "instance_masks.npz", allow_pickle=False)["masks"]
                tokens = extract_dinov2_patch_tokens(
                    model, rgb, configs["descriptor"], device="cuda",
                )
                public_frame, crosswalk, free_current = materialize_public_frame(
                    rgb=rgb, depth=depth, camera=camera,
                    private_instance_ids=private["private_instance_ids"],
                    mask_stack=masks, private_program=assignment["program"],
                    private_target_ids=intervention["target_instance_ids"],
                    frame_index=frame_index, patch_tokens=tokens,
                    prior_free_space=prior_free, configs=configs, episode_id=episode_id,
                )
                public_path = output_public / f"frame_{frame_index:04d}.json"
                private_path = output_private / f"frame_{frame_index:04d}.json"
                write_new_json(public_path, public_frame)
                write_new_json(private_path, crosswalk)
                frame_records.append({
                    "frame_index": frame_index, "public_sha256": sha256(public_path),
                    "private_crosswalk_sha256": sha256(private_path),
                })
                prior_free.append(free_current)
                resources = _resource_checkpoint(
                    stage, config, started=started, include_gpu=True,
                )
                peak_rss_bytes = max(
                    peak_rss_bytes, int(resources["process_tree_RSS_bytes"])
                )
                peak_gpu_bytes = max(
                    peak_gpu_bytes, int(resources["GPU_allocated_bytes"])
                )
            except Exception as error:
                if isinstance(error, ResourceLimitReached):
                    write_new_json(materialized / "resource-stop.json", {
                        "episode_id": episode_id, "frame_index": frame_index,
                        "error": str(error), "preserved_completed_frames": len(frame_records),
                    })
                    raise
                failed = f"{type(error).__name__}: {error}"
                failed_type = type(error).__name__
                break
        if failed is not None:
            write_new_json(output_public / "failure.json", {
                "episode_id": episode_id, "reason": "materialization_failed",
                "error_type": failed_type,
                "completed_frame_count": len(frame_records),
            })
            write_new_json(output_private / "failure.json", {
                "episode_id": episode_id, "program": assignment["program"],
                "reason": "materialization_failed", "error": failed,
                "completed_frame_count": len(frame_records),
            })
            results.append({"episode_id": episode_id, "status": "failed",
                            "reason": "materialization_failed"})
        else:
            write_new_json(output_public / "receipt.json", {
                "schema_version": "vsmt-vm04-two-house-materialized-episode-v1",
                "episode_id_hash": hashlib.sha256(episode_id.encode()).hexdigest(),
                "frame_count": 32,
                "public_frame_sha256s": [row["public_sha256"] for row in frame_records],
                "DINO_repository_commit": dino_commit,
                "DINO_checkpoint_sha256": read_json(ENVIRONMENT_PATH)[
                    "environment_separation"
                ]["public_materializer_process"]["DINOv2_checkpoint_sha256"],
            })
            write_new_json(output_private / "receipt.json", {
                "episode_id": episode_id, "program": assignment["program"],
                "replicate": assignment["replicate"],
                "private_crosswalk_sha256s": [
                    row["private_crosswalk_sha256"] for row in frame_records
                ], "public_receipt_sha256": sha256(output_public / "receipt.json"),
            })
            results.append({"episode_id": episode_id, "status": "complete",
                            "public_receipt_sha256": sha256(output_public / "receipt.json")})
    receipt = {
        "schema_version": "vsmt-vm04-two-house-materializer-receipt-v1",
        "stage_id": STAGE_ID, "reviewed_code": commit, "bound_sha256": bindings,
        "generation_receipt_sha256": sha256(stage / "generate.receipt.json"),
        "episode_count": 36, "episodes": results,
        "completed_count": sum(row["status"] == "complete" for row in results),
        "failed_count": sum(row["status"] == "failed" for row in results),
        "GPU_descriptor_consumers": 1, "wall_seconds": time.monotonic() - started,
        "peak_process_tree_RSS_bytes": peak_rss_bytes,
        "peak_GPU_allocated_bytes": peak_gpu_bytes,
        "success": True, "training_steps": 0,
        "private_data_opened_for_evaluation": False,
        "confirmation_data_opened": False,
    }
    receipt_path = stage / "materialize.receipt.json"
    write_new_json(receipt_path, receipt)
    write_new_json(stage / "materialize.success.json", {
        "schema_version": "vsmt-vm04-two-house-materializer-success-v1",
        "reviewed_code": commit, "receipt_sha256": sha256(receipt_path), "success": True,
    })
    print(f"VM04_TWO_HOUSE_MATERIALIZE_OK stage={stage} complete={receipt['completed_count']}")


def _packet_from_frame(
    frame: Mapping[str, Any], *, prior_memory: Mapping[str, Any], sample_suffix: str,
) -> dict[str, Any]:
    from vsmt.contracts import validate_observation_packet

    packet = {
        "schema_version": "vsmt-observation-packet-v3",
        "sample_id_hash": hashlib.sha256(
            f"{frame['episode_id_hash']}|{frame['frame_index']}|{sample_suffix}".encode("utf-8")
        ).hexdigest(),
        "decision_time_s": frame["decision_time_s"],
        "rgbd_refs": {"rgb_sha256": frame["rgb_sha256"],
                       "depth_sha256": frame["depth_sha256"]},
        "camera_pose": frame["camera_pose"],
        "robot_state": {"feature_names": [], "values": []},
        "past_actions": frame["past_actions"],
        "region_observations": frame["region_observations"],
        "relation_observations": frame["relation_observations"],
        "free_space_observations": frame["free_space_observations"],
        "visibility_observations": frame["visibility_observations"],
        "prior_memory_ref": {
            "graph_version": prior_memory["graph_version"],
            "graph_sha256": prior_memory["graph_hash"],
        },
        "public_constants": {
            "coordinate_frame": "map", "depth_unit": "metre",
            "descriptor_model_id": "dinov2.vits14",
            "proposal_model_id": "l1.oracle-mask.public-depth.v1",
        },
    }
    return validate_observation_packet(packet)


def _candidate_label(program: Mapping[str, Any]) -> str:
    return str(program.get("composition_label")) if program.get("template") == "COMPOSITE" else str(
        program.get("template")
    )


def canonical_candidate_key(candidate: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    """Canonical public target key used by the post-seal private matcher."""

    program = candidate["program"]
    closed_nodes: list[str] = []
    closed_edges: list[str] = []
    opened_nodes: list[str] = []
    opened_edges: list[str] = []
    for operation in program.get("operations", []):
        arguments = operation.get("arguments", {})
        if operation.get("op_type") == "CLOSE_NODE_VERSION":
            closed_nodes.append(str(arguments.get("node_id")))
        elif operation.get("op_type") == "CLOSE_EDGE_VERSION":
            closed_edges.append(str(arguments.get("edge_id")))
        elif operation.get("op_type") == "OPEN_NODE_VERSION":
            node = arguments.get("node", {})
            if type(node) is dict and node.get("node_id") is not None:
                opened_nodes.append(str(node["node_id"]))
        elif operation.get("op_type") == "ADD_NODE":
            node = arguments.get("node", {})
            if type(node) is dict and node.get("node_id") is not None:
                opened_nodes.append(str(node["node_id"]))
        elif operation.get("op_type") in {"OPEN_EDGE_VERSION", "ADD_EDGE"}:
            edge = arguments.get("edge", {})
            if type(edge) is dict and edge.get("edge_id") is not None:
                opened_edges.append(str(edge["edge_id"]))
    value = {
        "program": _candidate_label(program),
        "closed_node_ids": sorted(set(closed_nodes)),
        "closed_edge_ids": sorted(set(closed_edges)),
        "opened_node_ids": sorted(set(opened_nodes)),
        "opened_edge_ids": sorted(set(opened_edges)),
        "public_evidence_refs": sorted(
            ref for ref in program.get("evidence_refs", []) if type(ref) is str
        ),
        "observation_evidence_refs": sorted(
            ref for ref in program.get("evidence_refs", [])
            if type(ref) is str and ref.startswith("observation:")
        ),
        "retraction_target": program.get("retraction_target"),
    }
    return canonical_sha256(value), value


def _profile_configs(profile: Mapping[str, Any], capacity: int, values: Mapping[str, Any]):
    from vsmt.causal_prior import PublicBootstrapConfig
    from vsmt.public_candidates import PublicCandidateConfig
    from vsmt.shared_memory import SharedMemoryConfig

    rules = {kind: dict(profile[kind]) for kind in ("entity", "surface", "fragment")}
    bootstrap = PublicBootstrapConfig(
        association_rules={
            kind: {
                "visual_weight": rule["visual_weight"],
                "geometry_weight": rule["geometry_weight"],
                "geometry_scale_m": rule["geometry_scale_m"],
                "association_threshold": rule["bind_threshold"],
            } for kind, rule in rules.items()
        }, support_envelope_reliability_threshold=values[
            "support_envelope_reliability_threshold"
        ], maximum_regions_per_packet=512, builder_revision="two-house-audit-v1",
    )
    shared = SharedMemoryConfig(
        support_envelope_reliability_threshold=values[
            "support_envelope_reliability_threshold"
        ], support_envelope_margin_m=values["support_envelope_margin_m_per_side"],
        minimum_consecutive_missed_opportunities=values[
            "minimum_consecutive_missed_opportunities"
        ], opportunity_reliability_threshold=values["opportunity_reliability_threshold"],
        free_space_reliability_threshold=values["free_space_reliability_threshold"],
        association_visual_weight=rules["entity"]["visual_weight"],
        association_geometry_weight=rules["entity"]["geometry_weight"],
        association_geometry_scale_m=rules["entity"]["geometry_scale_m"],
        association_bind_threshold=rules["entity"]["bind_threshold"],
    )
    candidate = PublicCandidateConfig(
        association_rules=rules,
        split_minimum_separation_m=values["split_minimum_region_separation_m"],
        free_space_reliability_threshold=values["free_space_reliability_threshold"],
        support_envelope_reliability_threshold=values[
            "support_envelope_reliability_threshold"
        ], support_envelope_margin_m=values["support_envelope_margin_m_per_side"],
        minimum_free_space_time_separation_s=values[
            "minimum_free_space_time_separation_s"
        ], maximum_candidates_per_bucket=capacity,
        maximum_ambiguous_relation_variables=values[
            "maximum_ambiguous_relation_variables"
        ], maximum_relation_variants=values["maximum_relation_variants"],
        maximum_split_total_incident_edges=values["maximum_total_incident_edges"],
    )
    return bootstrap, shared, candidate


def replay_public_episode(
    frames: Sequence[Mapping[str, Any]], *, profile: Mapping[str, Any],
    profile_id: str, capacities: Sequence[int], values: Mapping[str, Any],
) -> dict[str, Any]:
    """Build one public-only prior and replay the decision catalog at three caps."""

    from vsmt.causal_prior import advance_public_bootstrap, empty_public_memory
    from vsmt.public_candidates import generate_public_candidate_catalog
    from vsmt.shared_memory import prepare_shared_memory

    require(len(frames) == 25, "public replay must receive frames zero through 24 only")
    memory = empty_public_memory()
    bootstrap, shared, _ = _profile_configs(profile, 64, values)
    bootstrap_trace: list[dict[str, Any]] = []
    for frame in frames[:24]:
        packet = _packet_from_frame(frame, prior_memory=memory, sample_suffix=profile_id)
        prepared_packet, prepared_memory, shared_audit = prepare_shared_memory(
            packet, memory, config=shared,
        )
        result = advance_public_bootstrap(
            prepared_packet, prepared_memory, config=bootstrap,
        )
        bootstrap_trace.append({
            "frame_index": frame["frame_index"],
            "bootstrap_decisions": result["diagnostics"]["bootstrap_decisions"],
            "shared_memory_audit_sha256": shared_audit["audit_sha256"],
            "post_memory_sha256": result["post_memory_sha256"],
        })
        memory = result["post_memory"]
    decision_packet = _packet_from_frame(
        frames[24], prior_memory=memory, sample_suffix=profile_id,
    )
    prepared_packet, prepared_memory, shared_audit = prepare_shared_memory(
        decision_packet, memory, config=shared,
    )
    catalogs: dict[str, Any] = {}
    full_catalogs: dict[str, Any] = {}
    for capacity in capacities:
        _, _, candidate_config = _profile_configs(profile, int(capacity), values)
        catalog = generate_public_candidate_catalog(
            prepared_packet, prepared_memory, config=candidate_config,
        )
        keys = [canonical_candidate_key(item)[0] for item in catalog["candidates"]]
        catalogs[str(capacity)] = {
            "catalog_sha256": catalog["catalog_sha256"],
            "candidate_count": len(catalog["candidates"]),
            "capacity_audit": catalog["capacity_audit"],
            "capacity_summary": catalog["capacity_summary"],
            "canonical_candidate_key_sha256s": keys,
            "relink_endpoint_pair_evaluation_count": sum(
                row["endpoint_pair_evaluation_count"] for row in catalog["capacity_audit"]
            ),
        }
        full_catalogs[str(capacity)] = catalog
    return {
        "profile_id": profile_id, "prior_memory_sha256": prepared_memory["graph_hash"],
        "bootstrap_trace": bootstrap_trace,
        "decision_shared_memory_audit_sha256": shared_audit["audit_sha256"],
        "catalogs": catalogs, "full_catalogs": full_catalogs,
        "full_prior_memory": prepared_memory,
    }


def _empty_profile_result(profile_id: str) -> dict[str, Any]:
    return {
        "profile_id": profile_id,
        "prior_memory_sha256": None,
        "prior_memory_file_sha256": None,
        "bootstrap_trace": [],
        "decision_shared_memory_audit_sha256": None,
        "catalogs": {
            str(capacity): {
                "catalog_sha256": None, "candidate_count": 0,
                "capacity_audit": [],
                "capacity_summary": {
                    "bucket_count": 0, "total_capacity": 0,
                    "total_pre_cap_candidate_count": 0,
                    "total_retained_candidate_count": 0,
                    "total_truncated_candidate_count": 0,
                }, "canonical_candidate_key_sha256s": [],
                "relink_endpoint_pair_evaluation_count": 0,
            } for capacity in (16, 32, 64)
        }, "full_catalogs": {},
    }


def run_public_seal(reviewed_code: str, output_root: Path) -> None:
    config = assert_two_house_action_authorized(load_config(), action="generate")
    commit, bindings = verify_checkout(reviewed_code)
    stage = stage_directory(output_root, commit)
    materializer, _ = _marker(stage, "materialize")
    require(not (stage / "public.seal.json").exists(), "public seal already exists")
    public_plan = validate_public_episode_plan(
        read_json(stage / "public/episode_plan.json")
    )
    profiles = config["audit_only_association_profiles"]["profiles"]
    require([profile["profile_id"] for profile in profiles] == [
        "strict", "balanced", "permissive_capacity_upper_bound",
    ], "association profile order changed")
    values = config["audit_only_lifecycle_and_capacity_values"]
    capacities = values["candidate_capacity_replay_values"]
    rows: list[dict[str, Any]] = []
    public_audit_root = stage / "public_audit"
    public_audit_root.mkdir()
    started = time.monotonic()
    for plan in public_plan["episodes"]:
        episode_id = plan["episode_id"]
        materialized_root = stage / "materialized/public" / episode_id
        failure_path = materialized_root / "failure.json"
        profile_results: dict[str, Any] = {}
        if failure_path.exists():
            status = "failed"
            failure_sha = sha256(failure_path)
            for profile in profiles:
                profile_results[profile["profile_id"]] = _empty_profile_result(
                    profile["profile_id"]
                )
        else:
            status = "constructed"
            failure_sha = None
            frames = [read_json(materialized_root / f"frame_{index:04d}.json")
                      for index in range(25)]
            for profile in profiles:
                profile_id = profile["profile_id"]
                result = replay_public_episode(
                    frames, profile=profile, profile_id=profile_id,
                    capacities=capacities, values=values,
                )
                catalog_root = public_audit_root / "catalogs" / episode_id / profile_id
                prior_root = public_audit_root / "priors" / episode_id
                prior = result.pop("full_prior_memory")
                write_new_json(prior_root / f"{profile_id}.json", prior)
                result["prior_memory_file_sha256"] = sha256(
                    prior_root / f"{profile_id}.json"
                )
                for capacity, catalog in result.pop("full_catalogs").items():
                    write_new_json(catalog_root / f"cap_{capacity}.json", catalog)
                    result["catalogs"][capacity]["catalog_file_sha256"] = sha256(
                        catalog_root / f"cap_{capacity}.json"
                    )
                profile_results[profile_id] = result
        try:
            checkpoint = _resource_checkpoint(stage, config, started=started)
        except ResourceLimitReached as error:
            write_new_json(public_audit_root / "resource-stop.json", {
                "episode_id": episode_id, "error": str(error),
                "completed_episode_count": len(rows),
            })
            raise
        rows.append({
            "episode_id": episode_id, "family_id": plan["family_id"],
            "slot": plan["slot"], "status": status,
            "failure_sha256": failure_sha, "profiles": profile_results,
            "capacity_audit": {
                profile_id: {capacity: result["capacity_summary"]
                             for capacity, result in value["catalogs"].items()}
                for profile_id, value in profile_results.items()
            }, "runtime": {"wall_seconds": checkpoint["wall_seconds"],
                            "peak_rss_bytes": checkpoint["process_tree_RSS_bytes"]},
        })
    processes = read_json(stage / "execution/processes.json")
    seal = make_public_seal(
        rows, public_manifest_sha256=public_plan["manifest_sha256"],
        capacities=capacities,
        worker_completion_order=processes["worker_completion_order"],
    )
    write_new_json(stage / "public.seal.json", seal)
    receipt = {
        "schema_version": "vsmt-vm04-two-house-public-seal-receipt-v1",
        "stage_id": STAGE_ID, "reviewed_code": commit, "bound_sha256": bindings,
        "materializer_receipt_sha256": sha256(stage / "materialize.receipt.json"),
        "public_seal_sha256": sha256(stage / "public.seal.json"),
        "canonical_episode_digest": seal["canonical_episode_digest"],
        "episode_count": 36,
        "constructed_count": sum(row["status"] == "constructed" for row in rows),
        "failed_count": sum(row["status"] == "failed" for row in rows),
        "success": True, "private_data_opened": False,
        "teacher_computed": False, "method_predictions_computed": False,
        "wall_seconds": time.monotonic() - started,
    }
    receipt_path = stage / "public-seal.receipt.json"
    write_new_json(receipt_path, receipt)
    write_new_json(stage / "public-seal.success.json", {
        "schema_version": "vsmt-vm04-two-house-public-seal-success-v1",
        "reviewed_code": commit, "receipt_sha256": sha256(receipt_path),
        "public_seal_sha256": seal["public_seal_sha256"], "success": True,
    })
    print(f"VM04_TWO_HOUSE_PUBLIC_SEAL_OK stage={stage} episodes=36")


def _target_regions(
    crosswalk: Mapping[str, Any], target_id: str,
) -> list[str]:
    """Return anonymous regions containing one private target in one frame."""

    return sorted(
        str(region_id)
        for region_id, private_ids in crosswalk[
            "entity_region_to_private_instance_ids"
        ].items()
        if target_id in private_ids
    )


def _target_node_ids(
    bootstrap_trace: Sequence[Mapping[str, Any]],
    crosswalks: Sequence[Mapping[str, Any]], target_id: str,
) -> list[str]:
    """Map a private target to public node IDs without exposing it to replay."""

    observed: list[str] = []
    for trace, crosswalk in zip(bootstrap_trace, crosswalks[:24], strict=True):
        regions = set(_target_regions(crosswalk, target_id))
        for decision in trace["bootstrap_decisions"]:
            if decision["region_id"] in regions:
                observed.append(str(decision["node_id"]))
    return list(dict.fromkeys(observed))


def _region_evidence_refs(
    frame: Mapping[str, Any], region_ids: Sequence[str], purposes: Sequence[str],
) -> set[str]:
    from vsmt.graph_ops import opaque_id

    regions = {
        str(region["region_id"]): region
        for region in frame["region_observations"]
        if region.get("structure_kind") == "entity"
    }
    selected = [regions[region_id] for region_id in sorted(region_ids) if region_id in regions]
    if len(purposes) == 1:
        return {
            opaque_id(region["mask_sha256"], purposes[0], prefix="evidence")
            for region in selected
        }
    require(len(selected) == len(purposes), "region/evidence purpose count mismatch")
    return {
        opaque_id(region["mask_sha256"], purpose, prefix="evidence")
        for region, purpose in zip(selected, purposes, strict=True)
    }


def _open_entity_nodes(memory: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(node["node_id"]): node for node in memory["nodes"]
        if node.get("valid_to") is None and node.get("node_type") == "entity"
    }


def _strict_candidate_matches(
    candidate: Mapping[str, Any], *, program: str,
    target_node_ids: Sequence[str], current_evidence_refs: set[str],
    incident_edge_ids: set[str], target_node_version_id: str | None,
) -> bool:
    """Apply the private exact-program predicate to one already sealed candidate."""

    key_hash, key = canonical_candidate_key(candidate)
    del key_hash
    if key["program"] != program:
        return False
    closed_nodes = set(key["closed_node_ids"])
    closed_edges = set(key["closed_edge_ids"])
    evidence = set(key["public_evidence_refs"])
    target_nodes = set(target_node_ids)
    if program == "NOOP":
        return not closed_nodes and not closed_edges
    if program == "BIRTH":
        return bool(current_evidence_refs & evidence) and not closed_nodes
    if program in {"BIND", "REACTIVATE"}:
        return bool(target_nodes & closed_nodes) and bool(current_evidence_refs & evidence)
    if program == "SPLIT":
        return bool(target_nodes & closed_nodes) and current_evidence_refs <= evidence
    if program == "MERGE":
        return len(target_nodes) >= 2 and target_nodes <= closed_nodes
    if program == "RELINK":
        return bool(incident_edge_ids & closed_edges)
    if program in {"RETRACT", "REPLACE"}:
        target = key["retraction_target"]
        exact_target = bool(
            type(target) is dict
            and target.get("kind") == "node_version"
            and target.get("version_id") == target_node_version_id
        )
        if program == "RETRACT":
            return exact_target and bool(target_nodes & closed_nodes)
        return (
            exact_target and bool(target_nodes & closed_nodes)
            and bool(current_evidence_refs & evidence)
        )
    return False


def strict_reference_key(
    catalog: Mapping[str, Any], *, program: str,
    target_node_ids: Sequence[str], current_evidence_refs: set[str],
    incident_edge_ids: set[str], target_node_version_id: str | None,
) -> tuple[str, int]:
    """Return a unique sealed key, or a deterministic absent-key commitment."""

    matches = [
        candidate for candidate in catalog["candidates"]
        if _strict_candidate_matches(
            candidate, program=program, target_node_ids=target_node_ids,
            current_evidence_refs=current_evidence_refs,
            incident_edge_ids=incident_edge_ids,
            target_node_version_id=target_node_version_id,
        )
    ]
    if len(matches) == 1:
        return canonical_candidate_key(matches[0])[0], 1
    expected = {
        "program": program,
        "target_node_ids": sorted(set(target_node_ids)),
        "current_evidence_refs": sorted(current_evidence_refs),
        "incident_edge_ids": sorted(incident_edge_ids),
        "target_node_version_id": target_node_version_id,
        "match_count": len(matches),
        "sentinel": "exact_reference_absent_or_ambiguous",
    }
    return canonical_sha256(expected), len(matches)


def _object_position(mapping: Mapping[str, Any], target_id: str) -> list[float] | None:
    value = mapping.get("objects", {}).get(target_id, {}).get("position")
    if type(value) is not dict or any(axis not in value for axis in ("x", "y", "z")):
        return None
    return [float(value[axis]) for axis in ("x", "y", "z")]


def assess_private_construction(
    *, program: str, target_ids: Sequence[str],
    crosswalks: Sequence[Mapping[str, Any]], raw_mappings: Sequence[Mapping[str, Any]],
    target_node_ids: Sequence[str],
) -> tuple[bool, str | None]:
    """Check whether the predeclared physical stress actually occurred."""

    require(len(crosswalks) == len(raw_mappings) == 32, "construction needs 32 frames")
    required = 2 if program in {"SPLIT", "REPLACE"} else 1
    if len(target_ids) != required:
        return False, "wrong_target_count"

    def visible(frame_index: int, target_index: int = 0) -> bool:
        return bool(_target_regions(crosswalks[frame_index], target_ids[target_index]))

    if program in {"NOOP", "BIND"}:
        ok = visible(0) and visible(24)
    elif program == "BIRTH":
        ok = not any(visible(index) for index in range(24)) and visible(24)
    elif program == "REACTIVATE":
        ok = any(visible(index) for index in range(16)) and not any(
            visible(index) for index in range(16, 24)
        ) and visible(24)
    elif program == "RETRACT":
        ok = visible(0) and not any(visible(index) for index in range(22, 32))
    elif program == "REPLACE":
        ok = (
            visible(0, 0)
            and not any(visible(index, 0) for index in range(22, 32))
            and not any(visible(index, 1) for index in range(24))
            and visible(24, 1)
        )
    elif program == "SPLIT":
        combined = all(
            any(set(private_ids) >= set(target_ids) for private_ids in crosswalk[
                "entity_region_to_private_instance_ids"
            ].values())
            for crosswalk in crosswalks[:24]
        )
        decision_regions = [_target_regions(crosswalks[24], target) for target in target_ids]
        ok = combined and all(len(value) == 1 for value in decision_regions) and (
            decision_regions[0] != decision_regions[1]
        )
    elif program == "MERGE":
        ok = visible(0) and visible(24) and len(set(target_node_ids)) >= 2
    elif program == "RELINK":
        before = _object_position(raw_mappings[0], target_ids[0])
        after = _object_position(raw_mappings[24], target_ids[0])
        ok = before is not None and after is not None and math.dist(before, after) >= 0.25
    else:
        raise RuntimeError(f"unknown construction program: {program}")
    return (True, None) if ok else (False, f"{program.lower()}_construction_not_observed")


def _retract_legal_at_margin(
    memory: Mapping[str, Any], target_node_id: str | None,
    decision_frame: Mapping[str, Any], *, margin_m: float,
    values: Mapping[str, Any],
) -> bool:
    from vsmt.graph_ops import fully_covered_by_free_space

    if target_node_id is None:
        return False
    node = _open_entity_nodes(memory).get(target_node_id)
    if node is None:
        return False
    return fully_covered_by_free_space(
        node, decision_frame["free_space_observations"],
        minimum_reliability=values["free_space_reliability_threshold"],
        target_expansion_m=margin_m,
        support_reliability_threshold=values["support_envelope_reliability_threshold"],
    )


def run_private_evaluation(reviewed_code: str, output_root: Path) -> None:
    config = assert_two_house_action_authorized(load_config(), action="private-eval")
    commit, bindings = verify_checkout(reviewed_code)
    stage = stage_directory(output_root, commit)
    public_receipt, _ = _marker(stage, "public-seal")
    require(not (stage / "private-evaluation.json").exists(),
            "private evaluation already exists")
    seal = read_json(stage / "public.seal.json")
    require(public_receipt["public_seal_sha256"] == sha256(stage / "public.seal.json"),
            "public seal changed before private opening")
    plans = validate_episode_plans({
        "public": read_json(stage / "public/episode_plan.json"),
        "private": read_json(stage / "private/episode_plan.json"),
    })
    public_by_id = {row["episode_id"]: row for row in seal["episodes"]}
    values = config["audit_only_lifecycle_and_capacity_values"]
    rows: list[dict[str, Any]] = []
    matcher_records: list[dict[str, Any]] = []
    started = time.monotonic()
    for assignment in plans["private"]["assignments"]:
        episode_id = assignment["episode_id"]
        try:
            _resource_checkpoint(stage, config, started=started)
        except ResourceLimitReached as error:
            write_new_json(stage / "private/private-eval-resource-stop.json", {
                "episode_id": episode_id, "error": str(error),
                "completed_episode_count": len(rows),
            })
            raise
        public_row = public_by_id[episode_id]
        base = {
            "episode_id": episode_id, "family_id": assignment["family_id"],
            "program": assignment["program"], "replicate": assignment["replicate"],
        }
        if public_row["status"] != "constructed":
            rows.append({
                **base, "constructed": False,
                "construction_failure_reason": "raw_or_materialization_failure",
                "canonical_reference_key_sha256_by_profile": None,
                "entity_retract_legal_at_margin_0_02": False,
                "entity_retract_legal_at_margin_0_05": False,
            })
            continue
        family_root = stage / "execution" / assignment["family_id"] / "episodes" / episode_id
        intervention = read_json(family_root / "private/intervention.json")
        targets = intervention["target_instance_ids"]
        crosswalks = [
            read_json(stage / "materialized/private" / episode_id / f"frame_{index:04d}.json")
            for index in range(32)
        ]
        raw_mappings = [
            read_json(family_root / "private" / f"frame_{index:04d}" / "mapping.json")
            for index in range(32)
        ]
        decision_frame = read_json(
            stage / "materialized/public" / episode_id / "frame_0024.json"
        )
        references: dict[str, str] = {}
        match_counts: dict[str, int] = {}
        strict_memory: Mapping[str, Any] | None = None
        strict_target_node: str | None = None
        construction_nodes: list[str] = []
        for profile_id in ("strict", "balanced", "permissive_capacity_upper_bound"):
            profile = public_row["profiles"][profile_id]
            target_nodes = _target_node_ids(
                profile["bootstrap_trace"], crosswalks, targets[0]
            )
            construction_nodes = target_nodes if profile_id == "strict" else construction_nodes
            memory_path = stage / "public_audit/priors" / episode_id / f"{profile_id}.json"
            require(sha256(memory_path) == profile["prior_memory_file_sha256"],
                    "sealed prior memory digest mismatch")
            memory = read_json(memory_path)
            open_nodes = _open_entity_nodes(memory)
            latest_target = next(
                (node_id for node_id in reversed(target_nodes) if node_id in open_nodes), None
            )
            current_target_index = 1 if assignment["program"] == "REPLACE" else 0
            current_regions = (
                sorted({
                    region_id for target in targets
                    for region_id in _target_regions(crosswalks[24], target)
                })
                if assignment["program"] == "SPLIT"
                else _target_regions(crosswalks[24], targets[current_target_index])
            )
            purpose_by_program = {
                "BIND": ["bind"], "BIRTH": ["birth"],
                "REACTIVATE": ["reactivate"], "SPLIT": ["split-left", "split-right"],
                "REPLACE": ["node-replace-birth"],
            }
            current_evidence = _region_evidence_refs(
                decision_frame, current_regions,
                purpose_by_program.get(assignment["program"], ["unused"]),
            ) if assignment["program"] in purpose_by_program else set()
            incident_edges = {
                str(edge["edge_id"]) for edge in memory["edges"]
                if edge.get("valid_to") is None and latest_target in {
                    str(edge["source"]), str(edge["target"])
                }
            }
            target_version = (
                str(open_nodes[latest_target]["node_version_id"])
                if latest_target in open_nodes else None
            )
            catalog_path = stage / "public_audit/catalogs" / episode_id / profile_id / "cap_64.json"
            require(sha256(catalog_path) == profile["catalogs"]["64"]["catalog_file_sha256"],
                    "sealed capacity-64 catalog digest mismatch")
            reference, count = strict_reference_key(
                read_json(catalog_path), program=assignment["program"],
                target_node_ids=(target_nodes[-2:] if assignment["program"] == "MERGE"
                                 else ([] if latest_target is None else [latest_target])),
                current_evidence_refs=current_evidence,
                incident_edge_ids=incident_edges,
                target_node_version_id=target_version,
            )
            references[profile_id] = reference
            match_counts[profile_id] = count
            if profile_id == "strict":
                strict_memory = memory
                strict_target_node = latest_target
        constructed, failure_reason = assess_private_construction(
            program=assignment["program"], target_ids=targets,
            crosswalks=crosswalks, raw_mappings=raw_mappings,
            target_node_ids=construction_nodes,
        )
        retract = assignment["program"] == "RETRACT" and constructed
        rows.append({
            **base, "constructed": constructed,
            "construction_failure_reason": failure_reason,
            "canonical_reference_key_sha256_by_profile": references if constructed else None,
            "entity_retract_legal_at_margin_0_02": bool(
                retract and strict_memory is not None and _retract_legal_at_margin(
                    strict_memory, strict_target_node, decision_frame,
                    margin_m=0.02, values=values,
                )
            ),
            "entity_retract_legal_at_margin_0_05": bool(
                retract and strict_memory is not None and _retract_legal_at_margin(
                    strict_memory, strict_target_node, decision_frame,
                    margin_m=0.05, values=values,
                )
            ),
        })
        matcher_records.append({
            "episode_id": episode_id,
            "canonical_reference_match_count_by_profile": match_counts,
            "reference_is_existing_candidate_only_when_match_count_is_one": True,
        })
        try:
            _resource_checkpoint(stage, config, started=started)
        except ResourceLimitReached as error:
            write_new_json(stage / "private/private-eval-resource-stop.json", {
                "episode_id": episode_id, "error": str(error),
                "completed_episode_count": len(rows),
            })
            raise
    evaluation = evaluate_private_recall(seal, rows)
    write_new_json(stage / "private-evaluation.json", evaluation)
    matcher_path = stage / "private/matcher-receipt.json"
    write_new_json(matcher_path, {
        "schema_version": "vsmt-vm04-two-house-private-matcher-receipt-v1",
        "records": matcher_records,
        "strict_reference_uses_preexisting_sealed_candidates_only": True,
    })
    receipt = {
        "schema_version": "vsmt-vm04-two-house-private-eval-receipt-v1",
        "stage_id": STAGE_ID, "reviewed_code": commit, "bound_sha256": bindings,
        "public_seal_file_sha256": sha256(stage / "public.seal.json"),
        "evaluation_file_sha256": sha256(stage / "private-evaluation.json"),
        "matcher_receipt_sha256": sha256(matcher_path),
        "episode_count": 36,
        "constructed_count": sum(row["constructed"] for row in rows),
        "failed_construction_count": sum(not row["constructed"] for row in rows),
        "private_opened_after_public_seal": True,
        "teacher_ranking_or_probability_computed": False,
        "method_predictions_or_effects_computed": False,
        "wall_seconds": time.monotonic() - started, "success": True,
    }
    receipt_path = stage / "private-eval.receipt.json"
    write_new_json(receipt_path, receipt)
    write_new_json(stage / "private-eval.success.json", {
        "schema_version": "vsmt-vm04-two-house-private-eval-success-v1",
        "reviewed_code": commit, "receipt_sha256": sha256(receipt_path),
        "evaluation_sha256": evaluation["evaluation_sha256"], "success": True,
    })
    print(f"VM04_TWO_HOUSE_PRIVATE_EVAL_OK stage={stage} constructed={receipt['constructed_count']}")


def _terminal_episode_ids(receipt: Mapping[str, Any]) -> set[str]:
    return {
        str(row["episode_id"])
        for worker in receipt["family_receipts"]
        for row in worker["summary"]["episodes"]
        if row["status"] in {"complete", "failed", "not_started"}
    }


def run_verify(reviewed_code: str, output_root: Path) -> None:
    config = assert_two_house_action_authorized(load_config(), action="private-eval")
    commit, bindings = verify_checkout(reviewed_code)
    stage = stage_directory(output_root, commit)
    receipts = {
        name: _marker(stage, name)[0]
        for name in (
            "contracts", "capacity", "generate", "materialize",
            "public-seal", "private-eval",
        )
    }
    require(not (stage / "verify.receipt.json").exists(), "verification already exists")
    plans = validate_episode_plans({
        "public": read_json(stage / "public/episode_plan.json"),
        "private": read_json(stage / "private/episode_plan.json"),
    })
    planned_ids = {row["episode_id"] for row in plans["public"]["episodes"]}
    generated_ids = _terminal_episode_ids(receipts["generate"])
    require(planned_ids == generated_ids and len(generated_ids) == 36,
            "all 36 fixed slots need one terminal generation record")
    processes = read_json(stage / "execution/processes.json")
    require(
        processes["requested_workers"] == processes["actual_workers"] == 2
        and len(processes["exits"]) == 2
        and not processes["not_started"] and not processes["missing_exit"]
        and all(row["exit_code"] == 0 for row in processes["exits"]),
        "worker process exit accounting is incomplete",
    )
    materialized_ids = {row["episode_id"] for row in receipts["materialize"]["episodes"]}
    require(materialized_ids == planned_ids, "materializer lacks fixed-slot terminal records")
    seal = read_json(stage / "public.seal.json")
    evaluation = read_json(stage / "private-evaluation.json")
    require(receipts["private-eval"]["public_seal_file_sha256"] == sha256(
        stage / "public.seal.json"
    ), "private evaluator is not bound to the sealed public bytes")
    require(evaluation["public_seal_sha256"] == seal["public_seal_sha256"],
            "private evaluation references another public seal")
    replayed = make_public_seal(
        list(reversed(seal["episodes"])),
        public_manifest_sha256=seal["public_manifest_sha256"],
        capacities=seal["capacity_replay_values"],
        worker_completion_order=list(reversed(processes["worker_completion_order"])),
    )
    require(replayed["canonical_episode_digest"] == seal["canonical_episode_digest"],
            "canonical merge digest depends on worker completion order")
    stage_bytes = _directory_bytes(stage)
    maximum_stage = int(config["resource_and_worker_proposal"]["maximum_stage_bytes"])
    require(stage_bytes <= maximum_stage, "verified stage exceeds frozen byte ceiling")
    receipt_digests = {
        name: sha256(stage / f"{name}.receipt.json") for name in receipts
    }
    merged_digest = canonical_sha256({
        "reviewed_code": commit,
        "public_canonical_episode_digest": seal["canonical_episode_digest"],
        "private_evaluation_sha256": evaluation["evaluation_sha256"],
        "receipt_sha256s": receipt_digests,
    })
    receipt = {
        "schema_version": "vsmt-vm04-two-house-verify-receipt-v1",
        "stage_id": STAGE_ID, "reviewed_code": commit, "bound_sha256": bindings,
        "receipt_sha256s": receipt_digests,
        "planned_episode_count": 36, "terminal_generation_episode_count": 36,
        "worker_requested_count": 2, "worker_actual_count": 2,
        "worker_exit_count": 2, "not_started": [], "missing_exit": [],
        "public_sealed_before_private_evaluation": True,
        "canonical_merge_digest_independent_of_worker_completion_order": True,
        "canonical_merged_output_digest": merged_digest,
        "stage_bytes": stage_bytes, "maximum_stage_bytes": maximum_stage,
        "generation_performed": True, "training_steps": 0,
        "private_data_opened_for_evaluation": True,
        "confirmation_data_opened": False, "success": True,
    }
    receipt_path = stage / "verify.receipt.json"
    write_new_json(receipt_path, receipt)
    write_new_json(stage / "verify.success.json", {
        "schema_version": "vsmt-vm04-two-house-verify-success-v1",
        "reviewed_code": commit, "receipt_sha256": sha256(receipt_path),
        "canonical_merged_output_digest": merged_digest, "success": True,
    })
    print(f"VM04_TWO_HOUSE_VERIFY_OK stage={stage} digest={merged_digest}")


def _capacity_totals(seal: Mapping[str, Any]) -> dict[str, Any]:
    totals: dict[str, Any] = {}
    for profile_id in ("strict", "balanced", "permissive_capacity_upper_bound"):
        totals[profile_id] = {}
        for capacity in (16, 32, 64):
            rows = [
                episode["profiles"][profile_id]["catalogs"][str(capacity)]
                for episode in seal["episodes"]
            ]
            totals[profile_id][str(capacity)] = {
                "candidate_count": sum(row["candidate_count"] for row in rows),
                "pre_cap_candidate_count": sum(
                    row["capacity_summary"]["total_pre_cap_candidate_count"] for row in rows
                ),
                "retained_candidate_count": sum(
                    row["capacity_summary"]["total_retained_candidate_count"] for row in rows
                ),
                "truncated_candidate_count": sum(
                    row["capacity_summary"]["total_truncated_candidate_count"] for row in rows
                ),
                "relink_endpoint_pair_evaluation_count": sum(
                    row["relink_endpoint_pair_evaluation_count"] for row in rows
                ),
            }
    return totals


def run_export(reviewed_code: str, output_root: Path) -> None:
    config = assert_two_house_action_authorized(load_config(), action="private-eval")
    commit, bindings = verify_checkout(reviewed_code)
    stage = stage_directory(output_root, commit)
    verify, _ = _marker(stage, "verify")
    require(not REPORT_PATH.exists(), f"report already exists: {REPORT_PATH}")
    seal = read_json(stage / "public.seal.json")
    evaluation = read_json(stage / "private-evaluation.json")
    selection = read_json(stage / "selection.json")
    generation = read_json(stage / "generate.receipt.json")
    materialize = read_json(stage / "materialize.receipt.json")
    report = {
        "schema_version": "vsmt-vm04-l1-two-house-audit-report-v1",
        "stage_id": STAGE_ID, "reviewed_code": commit,
        "bound_sha256": bindings,
        "config_sha256": sha256(CONFIG_PATH),
        "source_manifest_sha256": selection["source_manifest_sha256"],
        "eligible_house_ids_sha256": selection["eligible_house_ids_sha256"],
        "selection_sha256": selection["selection_sha256"],
        "audit_house_ids": selection["audit_house_ids"],
        "episode_count": 36, "observation_count": 1152,
        "raw_complete_episode_count": generation["raw_complete_episode_count"],
        "raw_failed_episode_count": generation["raw_failed_episode_count"],
        "raw_not_started_episode_count": generation["raw_not_started_episode_count"],
        "materialized_complete_episode_count": materialize["completed_count"],
        "materialized_failed_episode_count": materialize["failed_count"],
        "public_seal_sha256": seal["public_seal_sha256"],
        "canonical_episode_digest": seal["canonical_episode_digest"],
        "capacity_totals": _capacity_totals(seal),
        "private_evaluation": {
            "evaluation_sha256": evaluation["evaluation_sha256"],
            "by_family_and_program": evaluation["by_family_and_program"],
            "episodes": evaluation["episodes"],
            "semantic_equivalence_class_recall": None,
        },
        "canonical_merged_output_digest": verify[
            "canonical_merged_output_digest"
        ],
        "generation_performed": True, "training_steps": 0,
        "private_data_opened_for_evaluation": True,
        "confirmation_data_opened": False,
        "formal_threshold_or_cap_selected": False,
        "method_predictions_or_effects_computed": False,
        "scientific_success_claim_allowed": False,
    }
    write_new_json(
        REPORT_PATH, report,
        maximum_bytes=int(config["resource_and_worker_proposal"]["maximum_report_bytes"]),
    )
    print(
        "VM04_TWO_HOUSE_EXPORT_OK "
        f"report={REPORT_PATH} sha256={sha256(REPORT_PATH)}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=(
        "contracts", "inventory", "select", "capacity", "generate", "materialize",
        "public-seal", "private-eval", "verify", "export",
    ))
    parser.add_argument("--reviewed-code", required=True)
    parser.add_argument("--output-root", type=Path,
                        default=Path("/root/autodl-tmp/vsmt_outputs"))
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--source-file", type=Path, action="append", default=[])
    parser.add_argument("--license-path", type=Path, action="append", default=[])
    parser.add_argument("--planning-stage", type=Path)
    parser.add_argument("--predicted-wall-seconds", type=float)
    parser.add_argument("--predicted-stage-bytes", type=int)
    arguments = parser.parse_args()
    if HEX40.fullmatch(arguments.reviewed_code) is None:
        raise SystemExit("--reviewed-code must be a full lowercase commit")
    if arguments.mode == "contracts":
        run_contracts(arguments.reviewed_code, arguments.output_root)
    elif arguments.mode == "inventory":
        require(arguments.source_root is not None, "inventory requires --source-root")
        run_inventory(
            arguments.reviewed_code, arguments.output_root,
            source_root=arguments.source_root, source_files=arguments.source_file,
            license_paths=arguments.license_path,
        )
    elif arguments.mode == "select":
        run_selection(arguments.reviewed_code, arguments.output_root)
    elif arguments.mode == "capacity":
        require(arguments.planning_stage is not None,
                "capacity requires --planning-stage")
        require(arguments.predicted_wall_seconds is not None
                and arguments.predicted_stage_bytes is not None,
                "capacity requires declared predictions")
        run_capacity(
            arguments.reviewed_code, arguments.output_root,
            planning_stage=arguments.planning_stage,
            predicted_wall_seconds=arguments.predicted_wall_seconds,
            predicted_stage_bytes=arguments.predicted_stage_bytes,
        )
    elif arguments.mode == "generate":
        require(arguments.planning_stage is not None,
                "generate requires --planning-stage")
        require(arguments.source_root is not None, "generate requires --source-root")
        run_generation(
            arguments.reviewed_code, arguments.output_root,
            planning_stage=arguments.planning_stage,
            source_root=arguments.source_root,
        )
    elif arguments.mode == "materialize":
        run_materializer(arguments.reviewed_code, arguments.output_root)
    elif arguments.mode == "public-seal":
        run_public_seal(arguments.reviewed_code, arguments.output_root)
    elif arguments.mode == "private-eval":
        run_private_evaluation(arguments.reviewed_code, arguments.output_root)
    elif arguments.mode == "verify":
        run_verify(arguments.reviewed_code, arguments.output_root)
    elif arguments.mode == "export":
        run_export(arguments.reviewed_code, arguments.output_root)


if __name__ == "__main__":
    main()
