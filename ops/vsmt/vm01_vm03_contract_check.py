"""Server-only VM-01..VM-03 contract check and small-report exporter."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STAGE_ID = "vsmt-vm01-vm03-contract-check-v1"
EXPECTED_TESTS = 34
BOUND_PATHS = (
    "schemas/vsmt_vm01_contracts.schema.json",
    "src/vsmt/__init__.py",
    "src/vsmt/contracts.py",
    "src/vsmt/graph_ops.py",
    "src/vsmt/baselines.py",
    "src/vsmt/public_candidates.py",
    "tests/test_vsmt_contracts.py",
    "tests/test_vsmt_baselines.py",
    "tests/test_vsmt_public_candidates.py",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_new_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        value, ensure_ascii=False, indent=2, sort_keys=True,
    ).encode("utf-8") + b"\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def git(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=PROJECT_ROOT, text=True,
    ).strip()


def verify_checkout(reviewed_code: str) -> tuple[str, dict[str, str]]:
    root = Path(git("rev-parse", "--show-toplevel")).resolve()
    if root != PROJECT_ROOT.resolve():
        raise RuntimeError(f"repository root mismatch: {root}")
    head = git("rev-parse", "HEAD")
    if head != reviewed_code:
        raise RuntimeError(f"HEAD {head} is not reviewed code {reviewed_code}")
    dirty = git("status", "--porcelain", "--untracked-files=no")
    if dirty:
        raise RuntimeError("tracked checkout is dirty")
    bindings = {}
    for relative in BOUND_PATHS:
        path = PROJECT_ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"missing bound file: {relative}")
        bindings[relative] = sha256(path)
    return head, bindings


def stage_directory(output_root: Path, commit: str) -> Path:
    return output_root.resolve() / f"{STAGE_ID}-{commit[:12]}"


def run_stage(reviewed_code: str, output_root: Path) -> None:
    commit, bindings = verify_checkout(reviewed_code)
    stage = stage_directory(output_root, commit)
    if stage.exists():
        raise RuntimeError(f"stage directory already exists: {stage}")
    stage.mkdir(parents=True)
    started = {
        "schema_version": "vsmt-server-check-started-v1",
        "stage_id": STAGE_ID,
        "started_at": utc_now(),
        "repository_root": str(PROJECT_ROOT),
        "reviewed_code": commit,
        "bound_sha256": bindings,
        "expected_tests": EXPECTED_TESTS,
        "generation_authorized": False,
        "training_authorized": False,
        "private_data_opened": False,
    }
    write_new_json(stage / "started.json", started)
    command = [
        sys.executable, "-B", "-m", "unittest", "discover",
        "-s", str(PROJECT_ROOT / "tests"), "-p", "test_vsmt_*.py", "-v",
    ]
    begin = time.monotonic()
    completed = subprocess.run(
        command, cwd=PROJECT_ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    duration = time.monotonic() - begin
    output = completed.stdout
    (stage / "unittest.log").write_text(output, encoding="utf-8")
    print(output, end="")
    matches = re.findall(r"Ran (\d+) tests?", output)
    observed_tests = int(matches[-1]) if matches else None
    success = (
        completed.returncode == 0
        and observed_tests == EXPECTED_TESTS
        and "OK" in output
    )
    receipt = {
        "schema_version": "vsmt-server-check-receipt-v1",
        "stage_id": STAGE_ID,
        "reviewed_code": commit,
        "bound_sha256": bindings,
        "command": command,
        "expected_tests": EXPECTED_TESTS,
        "observed_tests": observed_tests,
        "exit_code": completed.returncode,
        "success": success,
        "wall_seconds": duration,
        "completed_at": utc_now(),
        "generation_performed": False,
        "training_steps": 0,
        "private_data_opened": False,
        "log_sha256": sha256(stage / "unittest.log"),
    }
    write_new_json(stage / "receipt.json", receipt)
    if not success:
        print(f"SERVER_STEP_FAILED stage={stage} exit={completed.returncode}")
        raise SystemExit(1)
    marker = {
        "schema_version": "vsmt-server-check-success-v1",
        "stage_id": STAGE_ID,
        "reviewed_code": commit,
        "receipt_sha256": sha256(stage / "receipt.json"),
        "observed_tests": observed_tests,
        "success": True,
    }
    write_new_json(stage / "success.json", marker)
    print(
        f"SERVER_STEP_OK stage={stage} tests={observed_tests} "
        f"wall_seconds={duration:.3f}"
    )


def export_stage(reviewed_code: str, output_root: Path) -> None:
    commit, bindings = verify_checkout(reviewed_code)
    stage = stage_directory(output_root, commit)
    receipt_path = stage / "receipt.json"
    marker_path = stage / "success.json"
    if not receipt_path.is_file() or not marker_path.is_file():
        raise RuntimeError("successful run receipt and marker are required")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if not (
        receipt.get("success") is True
        and receipt.get("reviewed_code") == commit
        and receipt.get("bound_sha256") == bindings
        and receipt.get("observed_tests") == EXPECTED_TESTS
        and marker.get("receipt_sha256") == sha256(receipt_path)
    ):
        raise RuntimeError("server check receipt binding is invalid")
    report = {
        "schema_version": "vsmt-vm01-vm03-contract-report-v1",
        "stage_id": STAGE_ID,
        "reviewed_code": commit,
        "bound_sha256": bindings,
        "tests": EXPECTED_TESTS,
        "success": True,
        "wall_seconds": receipt["wall_seconds"],
        "generation_performed": False,
        "training_steps": 0,
        "private_data_opened": False,
        "source_receipt_sha256": sha256(receipt_path),
        "source_marker_sha256": sha256(marker_path),
    }
    destination = PROJECT_ROOT / "results" / "vsmt_vm01_vm03_contract_check.json"
    if destination.exists():
        existing = json.loads(destination.read_text(encoding="utf-8"))
        if existing != report:
            raise RuntimeError(f"refusing to overwrite different report: {destination}")
        print(f"EXPORT_REUSED path={destination} sha256={sha256(destination)}")
        return
    write_new_json(destination, report)
    print(f"EXPORT_OK path={destination} sha256={sha256(destination)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("run", "export"))
    parser.add_argument("--reviewed-code", required=True)
    parser.add_argument(
        "--output-root", type=Path,
        default=Path("/root/autodl-tmp/vsmt_outputs"),
    )
    arguments = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", arguments.reviewed_code):
        raise SystemExit("--reviewed-code must be a full lowercase commit hash")
    if arguments.mode == "run":
        run_stage(arguments.reviewed_code, arguments.output_root)
    else:
        export_stage(arguments.reviewed_code, arguments.output_root)


if __name__ == "__main__":
    main()
