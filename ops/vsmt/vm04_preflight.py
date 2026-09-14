"""Fixed server entry for VM-04 contracts and read-only source audit.

Modes run in order: ``contracts``, ``source-audit``, then ``export``.  No mode
installs dependencies, downloads model/data payloads, runs a simulator,
generates observations, opens confirmation data, or trains a model.
"""

from __future__ import annotations

import argparse
import ctypes.util
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time
from typing import Any
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "configs" / "vsmt" / "vm04_source_audit_v1.json"
STAGE_ID = "vsmt-vm04-preflight-v1"
BOUND_PATHS = (
    "configs/vsmt/vm04_data_protocol_proposal_v1.json",
    "configs/vsmt/vm04_l1_action_symmetry_v1.json",
    "configs/vsmt/vm04_source_audit_v1.json",
    "schemas/transaction_program.schema.json",
    "schemas/vsmt_causal_prior_receipt.schema.json",
    "schemas/vsmt_vm01_contracts.schema.json",
    "schemas/vsmt_vm04_manifests.schema.json",
    "src/cpmt/executor.py",
    "src/vsmt/__init__.py",
    "src/vsmt/baselines.py",
    "src/vsmt/causal_prior.py",
    "src/vsmt/contracts.py",
    "src/vsmt/graph_ops.py",
    "src/vsmt/l1_structures.py",
    "src/vsmt/place_scaffold.py",
    "src/vsmt/public_candidates.py",
    "src/vsmt/shared_memory.py",
    "src/vsmt/vm04_protocol.py",
    "tests/test_vsmt_baselines.py",
    "tests/test_vsmt_causal_prior.py",
    "tests/test_vsmt_contracts.py",
    "tests/test_vsmt_place_scaffold.py",
    "tests/test_vsmt_public_candidates.py",
    "tests/test_vsmt_shared_memory.py",
    "tests/test_vsmt_vm04_protocol.py",
    "ops/vsmt/vm04_preflight.py",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_new_json(path: Path, value: Any, *, maximum_bytes: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        value, ensure_ascii=False, indent=2, sort_keys=True,
    ).encode("utf-8") + b"\n"
    if len(encoded) > maximum_bytes:
        raise RuntimeError(f"refusing oversized JSON output: {len(encoded)} bytes")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def load_config() -> dict[str, Any]:
    value = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if value.get("status") != "executable_read_only":
        raise RuntimeError("source audit config is not executable_read_only")
    for flag in (
        "asset_download_authorized", "dependency_install_authorized",
        "generation_authorized", "training_authorized", "confirmation_authorized",
    ):
        if value.get(flag) is not False:
            raise RuntimeError(f"read-only source audit requires {flag}=false")
    if value.get("source_audit_authorized") is not True:
        raise RuntimeError("source audit is not authorized")
    return value


def git(*arguments: str, cwd: Path = PROJECT_ROOT) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=cwd, text=True, timeout=120,
    ).strip()


def verify_checkout(reviewed_code: str) -> tuple[str, dict[str, str]]:
    root = Path(git("rev-parse", "--show-toplevel")).resolve()
    if root != PROJECT_ROOT.resolve():
        raise RuntimeError(f"repository root mismatch: {root}")
    head = git("rev-parse", "HEAD")
    if head != reviewed_code:
        raise RuntimeError(f"HEAD {head} is not reviewed code {reviewed_code}")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError("tracked checkout is dirty")
    bindings: dict[str, str] = {}
    for relative in BOUND_PATHS:
        path = PROJECT_ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"missing bound file: {relative}")
        bindings[relative] = sha256(path)
    return head, bindings


def stage_directory(output_root: Path, commit: str) -> Path:
    return output_root.resolve() / f"{STAGE_ID}-{commit[:12]}"


def run_command(command: list[str], *, timeout: int, cwd: Path = PROJECT_ROOT) -> dict[str, Any]:
    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    )
    return {
        "command": command,
        "exit_code": completed.returncode,
        "wall_seconds": time.monotonic() - started,
        "output": completed.stdout,
    }


def require_contract_success(stage: Path, commit: str, expected_tests: int) -> dict[str, Any]:
    receipt_path = stage / "contracts.receipt.json"
    marker_path = stage / "contracts.success.json"
    if not receipt_path.is_file() or not marker_path.is_file():
        raise RuntimeError("contract receipt and success marker are required")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if not (
        receipt.get("reviewed_code") == commit
        and receipt.get("success") is True
        and receipt.get("observed_tests") == expected_tests
        and marker.get("receipt_sha256") == sha256(receipt_path)
    ):
        raise RuntimeError("contract success binding is invalid")
    return receipt


def run_contracts(reviewed_code: str, output_root: Path) -> None:
    config = load_config()
    commit, bindings = verify_checkout(reviewed_code)
    stage = stage_directory(output_root, commit)
    if stage.exists():
        raise RuntimeError(f"stage directory already exists: {stage}")
    stage.mkdir(parents=True)
    maximum = int(config["limits"]["report_bytes"])
    expected_tests = int(config["expected_contract_tests"])
    write_new_json(stage / "started.json", {
        "schema_version": "vsmt-vm04-preflight-started-v1",
        "stage_id": STAGE_ID,
        "started_at": utc_now(),
        "repository_root": str(PROJECT_ROOT),
        "reviewed_code": commit,
        "bound_sha256": bindings,
        "expected_contract_tests": expected_tests,
        "asset_download_authorized": False,
        "dependency_install_authorized": False,
        "generation_authorized": False,
        "training_authorized": False,
        "confirmation_authorized": False,
    }, maximum_bytes=maximum)
    command = [
        sys.executable, "-B", "-m", "unittest", "discover",
        "-s", str(PROJECT_ROOT / "tests"), "-p", "test_vsmt_*.py", "-v",
    ]
    result = run_command(command, timeout=int(config["limits"]["wall_clock_seconds"]))
    log_path = stage / "contracts.unittest.log"
    log_path.write_text(result["output"], encoding="utf-8")
    print(result["output"], end="")
    matches = re.findall(r"Ran (\d+) tests?", result["output"])
    observed = int(matches[-1]) if matches else None
    success = result["exit_code"] == 0 and observed == expected_tests and "OK" in result["output"]
    receipt = {
        "schema_version": "vsmt-vm04-contract-receipt-v1",
        "stage_id": STAGE_ID,
        "reviewed_code": commit,
        "bound_sha256": bindings,
        "command": command,
        "expected_tests": expected_tests,
        "observed_tests": observed,
        "exit_code": result["exit_code"],
        "success": success,
        "wall_seconds": result["wall_seconds"],
        "completed_at": utc_now(),
        "generation_performed": False,
        "training_steps": 0,
        "private_data_opened": False,
        "confirmation_data_opened": False,
        "log_sha256": sha256(log_path),
    }
    receipt_path = stage / "contracts.receipt.json"
    write_new_json(receipt_path, receipt, maximum_bytes=maximum)
    if not success:
        print(f"VM04_CONTRACTS_FAILED stage={stage} exit={result['exit_code']}")
        raise SystemExit(1)
    write_new_json(stage / "contracts.success.json", {
        "schema_version": "vsmt-vm04-contract-success-v1",
        "stage_id": STAGE_ID,
        "reviewed_code": commit,
        "receipt_sha256": sha256(receipt_path),
        "observed_tests": observed,
        "success": True,
    }, maximum_bytes=maximum)
    print(f"VM04_CONTRACTS_OK stage={stage} tests={observed}")


def fetch_json(url: str, *, maximum_bytes: int, timeout: int) -> tuple[dict[str, Any], dict[str, Any]]:
    request = Request(url, headers={"User-Agent": "vsmt-vm04-read-only-audit/1"})
    with urlopen(request, timeout=timeout) as response:
        payload = response.read(maximum_bytes + 1)
        if len(payload) > maximum_bytes:
            raise RuntimeError(f"response exceeds {maximum_bytes} bytes: {url}")
        metadata = {
            "status": response.status,
            "final_url": response.geturl(),
            "content_length_header": response.headers.get("Content-Length"),
            "payload_bytes": len(payload),
            "payload_sha256": hashlib.sha256(payload).hexdigest(),
        }
    return json.loads(payload.decode("utf-8")), metadata


def audit_remote_git(item: dict[str, Any], *, timeout: int) -> dict[str, Any]:
    base_ref = item["ref"].removesuffix("^{}")
    preferred_ref = f"{base_ref}^{{}}"
    result = run_command(
        ["git", "ls-remote", item["repository"], base_ref, preferred_ref],
        timeout=timeout,
    )
    lines = [line.split() for line in result["output"].splitlines() if line.strip()]
    refs = {row[1]: row[0] for row in lines if len(row) == 2}
    observed = refs.get(preferred_ref, refs.get(base_ref))
    return {
        "name": item["name"],
        "repository": item["repository"],
        "ref": item["ref"],
        "expected_commit": item["expected_commit"],
        "observed_commit": observed,
        "observed_refs": refs,
        "exit_code": result["exit_code"],
        "match": result["exit_code"] == 0 and observed == item["expected_commit"],
    }


def audit_remote_commit(
    item: dict[str, Any], *, maximum_bytes: int, timeout: int,
) -> dict[str, Any]:
    value, metadata = fetch_json(item["url"], maximum_bytes=maximum_bytes, timeout=timeout)
    observed = value.get("sha")
    return {
        "name": item["name"],
        "url": item["url"],
        "expected_commit": item["expected_commit"],
        "observed_commit": observed,
        "match": observed == item["expected_commit"],
        "response": metadata,
    }


def audit_pypi(
    item: dict[str, Any], *, maximum_bytes: int, timeout: int,
) -> dict[str, Any]:
    url = f"https://pypi.org/pypi/{item['project']}/{item['version']}/json"
    value, metadata = fetch_json(url, maximum_bytes=maximum_bytes, timeout=timeout)
    files = [{
        "filename": row.get("filename"),
        "packagetype": row.get("packagetype"),
        "python_version": row.get("python_version"),
        "requires_python": row.get("requires_python"),
        "size": row.get("size"),
        "sha256": (row.get("digests") or {}).get("sha256"),
    } for row in value.get("urls", [])]
    return {
        "project": item["project"],
        "version": item["version"],
        "release_exists": bool(files),
        "files": files,
        "response": metadata,
    }


def audit_http_asset(item: dict[str, Any], *, timeout: int) -> dict[str, Any]:
    request = Request(
        item["url"], method="HEAD",
        headers={"User-Agent": "vsmt-vm04-read-only-audit/1"},
    )
    with urlopen(request, timeout=timeout) as response:
        observed_header = response.headers.get("Content-Length")
        observed = int(observed_header) if observed_header is not None else None
        return {
            "name": item["name"],
            "url": item["url"],
            "expected_content_length": item["expected_content_length"],
            "observed_content_length": observed,
            "status": response.status,
            "final_url": response.geturl(),
            "body_bytes_read": 0,
            "match": observed == item["expected_content_length"],
        }


def audit_local_asset(item: dict[str, Any]) -> dict[str, Any]:
    path = Path(item["path"])
    if item["kind"] == "file":
        observed = sha256(path) if path.is_file() else None
        return {
            **item,
            "exists": path.is_file(),
            "observed_sha256": observed,
            "size": path.stat().st_size if path.is_file() else None,
            "match": observed == item["expected_sha256"],
        }
    observed = None
    if path.is_dir() and (path / ".git").exists():
        observed = git("rev-parse", "HEAD", cwd=path)
    return {
        **item,
        "exists": path.is_dir(),
        "observed_commit": observed,
        "match": observed == item["expected_commit"],
    }


def source_audit(reviewed_code: str, output_root: Path, *, attempt: int) -> None:
    config = load_config()
    commit, bindings = verify_checkout(reviewed_code)
    stage = stage_directory(output_root, commit)
    maximum = int(config["limits"]["report_bytes"])
    timeout = min(120, int(config["limits"]["wall_clock_seconds"]))
    response_limit = int(config["limits"]["network_response_bytes_per_request"])
    contract = require_contract_success(
        stage, commit, int(config["expected_contract_tests"]),
    )
    prefix = f"source_audit.attempt-{attempt:02d}"
    audit_path = stage / f"{prefix}.receipt.json"
    if audit_path.exists() or (stage / f"{prefix}.failure.json").exists():
        raise RuntimeError(f"source audit attempt {attempt} already has a terminal record")
    started = time.monotonic()
    errors: list[str] = []

    def collect(name: str, function: Any) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            rows = function()
        except Exception as error:  # preserve the exact failed audit, never retry here
            errors.append(f"{name}: {type(error).__name__}: {error}")
        return rows

    remote_git = collect("remote_git_refs", lambda: [
        audit_remote_git(item, timeout=timeout) for item in config["remote_git_refs"]
    ])
    remote_commits = collect("remote_commit_urls", lambda: [
        audit_remote_commit(item, maximum_bytes=response_limit, timeout=timeout)
        for item in config["remote_commit_urls"]
    ])
    pypi = collect("pypi_releases", lambda: [
        audit_pypi(item, maximum_bytes=response_limit, timeout=timeout)
        for item in config["pypi_releases"]
    ])
    http_assets = collect("http_assets", lambda: [
        audit_http_asset(item, timeout=timeout) for item in config["http_assets"]
    ])
    local_assets = collect("known_local_assets", lambda: [
        audit_local_asset(item) for item in config["known_local_assets"]
    ])
    modules = [{
        "name": name,
        "available": importlib.util.find_spec(name) is not None,
    } for name in config["python_modules_to_probe_without_install"]]
    libraries = [{
        "name": name,
        "resolved": ctypes.util.find_library(name),
    } for name in config["system_libraries_to_probe"]]
    disk = []
    for path in (Path("/"), Path("/root/autodl-tmp")):
        if path.exists():
            usage = shutil.disk_usage(path)
            disk.append({
                "path": str(path), "total_bytes": usage.total,
                "used_bytes": usage.used, "free_bytes": usage.free,
            })
    gpu = collect("nvidia_smi", lambda: [run_command([
        "nvidia-smi",
        "--query-gpu=name,memory.total,memory.free,driver_version",
        "--format=csv,noheader,nounits",
    ], timeout=timeout)])
    torch_probe = collect("torch_probe", lambda: [run_command([
        sys.executable, "-c",
        "import json,torch; print(json.dumps({'version':torch.__version__,"
        "'cuda_available':torch.cuda.is_available(),"
        "'cuda_version':torch.version.cuda}))",
    ], timeout=timeout)])
    match_rows = remote_git + remote_commits + http_assets + local_assets
    success = (
        not errors
        and all(row.get("match") is True for row in match_rows)
        and all(row.get("release_exists") is True for row in pypi)
        and time.monotonic() - started <= int(config["limits"]["wall_clock_seconds"])
    )
    receipt = {
        "schema_version": "vsmt-vm04-source-audit-receipt-v1",
        "stage_id": STAGE_ID,
        "reviewed_code": commit,
        "bound_sha256": bindings,
        "contract_receipt_sha256": sha256(stage / "contracts.receipt.json"),
        "contract_tests": contract["observed_tests"],
        "host": {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "executable": sys.executable,
            "disk": disk,
            "gpu": gpu,
            "torch": torch_probe,
            "python_modules": modules,
            "system_libraries": libraries,
        },
        "remote_git_refs": remote_git,
        "remote_commits": remote_commits,
        "pypi_releases": pypi,
        "http_assets": http_assets,
        "known_local_assets": local_assets,
        "candidate_environment": config["candidate_environment"],
        "errors": errors,
        "success": success,
        "wall_seconds": time.monotonic() - started,
        "completed_at": utc_now(),
        "network_body_bytes_for_model_or_dataset": 0,
        "asset_download_performed": False,
        "dependency_install_performed": False,
        "generation_performed": False,
        "training_steps": 0,
        "private_data_opened": False,
        "confirmation_data_opened": False,
    }
    write_new_json(audit_path, receipt, maximum_bytes=maximum)
    if not success:
        write_new_json(stage / f"{prefix}.failure.json", {
            "schema_version": "vsmt-vm04-source-audit-failure-v1",
            "reviewed_code": commit,
            "receipt_sha256": sha256(audit_path),
            "errors": errors,
        }, maximum_bytes=maximum)
        print(f"VM04_SOURCE_AUDIT_FAILED stage={stage}")
        raise SystemExit(1)
    write_new_json(stage / f"{prefix}.success.json", {
        "schema_version": "vsmt-vm04-source-audit-success-v1",
        "reviewed_code": commit,
        "receipt_sha256": sha256(audit_path),
        "success": True,
    }, maximum_bytes=maximum)
    print(f"VM04_SOURCE_AUDIT_OK stage={stage}")


def export_stage(reviewed_code: str, output_root: Path, *, source_attempt: int) -> None:
    config = load_config()
    commit, bindings = verify_checkout(reviewed_code)
    stage = stage_directory(output_root, commit)
    contract = require_contract_success(
        stage, commit, int(config["expected_contract_tests"]),
    )
    prefix = f"source_audit.attempt-{source_attempt:02d}"
    audit_path = stage / f"{prefix}.receipt.json"
    marker_path = stage / f"{prefix}.success.json"
    if not audit_path.is_file() or not marker_path.is_file():
        raise RuntimeError("successful source audit receipt and marker are required")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if not (
        audit.get("success") is True
        and audit.get("reviewed_code") == commit
        and audit.get("bound_sha256") == bindings
        and marker.get("receipt_sha256") == sha256(audit_path)
    ):
        raise RuntimeError("source audit binding is invalid")
    report = {
        "schema_version": "vsmt-vm04-preflight-report-v1",
        "stage_id": STAGE_ID,
        "reviewed_code": commit,
        "bound_sha256": bindings,
        "contract_tests": contract["observed_tests"],
        "contract_success": True,
        "source_audit_success": True,
        "source_summary": {
            "remote_git_refs": audit["remote_git_refs"],
            "remote_commits": audit["remote_commits"],
            "pypi_releases": audit["pypi_releases"],
            "http_assets": audit["http_assets"],
            "known_local_assets": audit["known_local_assets"],
            "candidate_environment": audit["candidate_environment"],
        },
        "host_summary": audit["host"],
        "asset_download_performed": False,
        "dependency_install_performed": False,
        "generation_performed": False,
        "training_steps": 0,
        "private_data_opened": False,
        "confirmation_data_opened": False,
        "contract_receipt_sha256": sha256(stage / "contracts.receipt.json"),
        "source_audit_receipt_sha256": sha256(audit_path),
        "source_audit_marker_sha256": sha256(marker_path),
    }
    destination = PROJECT_ROOT / "results" / "vsmt_vm04_preflight.json"
    if destination.exists():
        existing = json.loads(destination.read_text(encoding="utf-8"))
        if existing != report:
            raise RuntimeError(f"refusing to overwrite different report: {destination}")
        print(f"VM04_EXPORT_REUSED path={destination} sha256={sha256(destination)}")
        return
    write_new_json(
        destination, report, maximum_bytes=int(config["limits"]["report_bytes"]),
    )
    print(f"VM04_EXPORT_OK path={destination} sha256={sha256(destination)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("contracts", "source-audit", "export"))
    parser.add_argument("--reviewed-code", required=True)
    parser.add_argument(
        "--output-root", type=Path,
        default=Path("/root/autodl-tmp/vsmt_outputs"),
    )
    parser.add_argument(
        "--attempt", type=int, default=1,
        help="positive source-audit attempt number; export reads the same attempt",
    )
    arguments = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", arguments.reviewed_code):
        raise SystemExit("--reviewed-code must be a full lowercase commit hash")
    if arguments.attempt <= 0:
        raise SystemExit("--attempt must be positive")
    if arguments.mode == "contracts":
        run_contracts(arguments.reviewed_code, arguments.output_root)
    elif arguments.mode == "source-audit":
        source_audit(
            arguments.reviewed_code, arguments.output_root,
            attempt=arguments.attempt,
        )
    else:
        export_stage(
            arguments.reviewed_code, arguments.output_root,
            source_attempt=arguments.attempt,
        )


if __name__ == "__main__":
    main()
