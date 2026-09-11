"""SH-01: run/verify/export server contract tests without loading legacy models.

Writes only a new outputs directory and the explicitly requested small report.
Successful matching receipts are reused; failed/interrupted directories persist.
"""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import unittest
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN = ROOT / "outputs/spatial-history/contract-v1"
REPORT = ROOT / "results/spatial_history_contract_v1.json"
BOUND_FILES = (
    "src/spatial_world_model/__init__.py",
    "src/spatial_world_model/pair_contract.py",
    "tests/spatial_world_model/test_pair_contract.py",
    "data/fixtures/spatial_history/manual_pair.json",
    "ops/spatial_history/contract_check.py",
    "docs/METHOD.md", "docs/DATA.md",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def write_new(path, value):
    with path.open("xb") as handle:
        handle.write(encode(value))


def binding():
    # Store actual server bytes. The Git tree also records canonical repository bytes.
    return {name: sha((ROOT / name).read_bytes()) for name in BOUND_FILES}


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def inventory():
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "tests/spatial_world_model"))
    module = importlib.import_module("test_pair_contract")
    suite = unittest.defaultTestLoader.loadTestsFromModule(module)

    def flatten(item):
        if isinstance(item, unittest.TestSuite):
            return [name for child in item for name in flatten(child)]
        return [item.id()]

    names = flatten(suite)
    require(names and len(names) == len(set(names)), "empty or duplicate test inventory")
    return suite, names


class Tee:
    def __init__(self, log):
        self.log = log

    def write(self, value):
        sys.stdout.write(value)
        self.log.write(value)

    def flush(self):
        sys.stdout.flush()
        self.log.flush()


def verify(directory):
    saved = json.loads((directory / "receipt.json").read_text(encoding="utf-8"))
    require(saved["stage"] == "SH-01" and saved["exit_code"] == 0, "no successful SH-01 receipt")
    require(saved["binding"] == binding(), "contract/code binding changed; old receipt cannot certify it")
    _, names = inventory()
    require(saved["test_names"] == names and saved["tests_run"] == len(names), "test inventory mismatch")
    require(saved["failures"] == saved["errors"] == saved["skipped"] == 0, "incomplete test receipt")
    require(set(saved["artifacts"]) == {"tests.log", "example_audit.json", "example_public_input.json"},
            "artifact inventory mismatch")
    for name, digest in saved["artifacts"].items():
        require(sha((directory / name).read_bytes()) == digest, f"artifact changed: {name}")
    require(saved["physics_and_visibility_verified"] is False, "contract test is not physics evidence")
    print(f"SH-01 VERIFIED tests={len(names)} original_commit={saved['commit']} exit=0", flush=True)
    return saved


def run(directory):
    if directory.exists():
        print(f"Existing directory: {directory}; verify only, never rerun/overwrite.", flush=True)
        return verify(directory)
    require(platform.system() == "Linux", "server-only run: use the Linux server, not the local computer")
    require((3, 11) <= sys.version_info[:2] < (3, 13), "requires Python 3.11 or 3.12")
    require(not git("status", "--porcelain", "--", *BOUND_FILES), "bound files must be committed and clean")
    before = binding()
    commit = git("rev-parse", "HEAD")
    suite, names = inventory()
    directory.mkdir(parents=True, exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    # Any interruption leaves this directory intact; no later automatic retry.
    write_new(directory / "started.json", {"stage": "SH-01", "started": started,
                                          "commit": commit, "binding": before})
    with (directory / "tests.log").open("x", encoding="utf-8") as log:
        result = unittest.TextTestRunner(stream=Tee(log), verbosity=2).run(suite)
    success = (result.wasSuccessful() and result.testsRun == len(names)
               and not result.skipped and not result.expectedFailures and before == binding())
    artifacts = {"tests.log": sha((directory / "tests.log").read_bytes())}
    if success:
        from spatial_world_model.pair_contract import audit_pair, model_input
        pair = json.loads((ROOT / BOUND_FILES[3]).read_text(encoding="utf-8"))
        for name, value in (("example_audit.json", audit_pair(pair)),
                            ("example_public_input.json", model_input(pair, 0, 0))):
            write_new(directory / name, value)
            artifacts[name] = sha((directory / name).read_bytes())
    saved = {"stage": "SH-01", "commit": commit, "binding": before,
             "started": started, "finished": datetime.now(timezone.utc).isoformat(),
             "python": sys.version, "platform": platform.platform(), "repository": str(ROOT),
             "test_names": names, "tests_run": result.testsRun,
             "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
             "artifacts": artifacts, "exit_code": 0 if success else 1,
             "physics_and_visibility_verified": False, "model_experiment_run": False}
    write_new(directory / "receipt.json", saved)
    require(success, f"SH-01 failed; preserved at {directory}")
    return verify(directory)


def export(directory, report_path=REPORT):
    saved = verify(directory)
    audit = json.loads((directory / "example_audit.json").read_text(encoding="utf-8"))
    report = {"kind": "engineering_contract_check", "receipt": saved,
              "receipt_sha256": sha((directory / "receipt.json").read_bytes()), "example": audit}
    if report_path.exists():
        require(report_path.read_bytes() == encode(report), f"different report exists: {report_path}; not overwritten")
    else:
        write_new(report_path, report)
    print(f"SH-01 EXPORTED {report_path} exit=0", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("run", "verify", "export"))
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    directory = args.run_dir.resolve()
    require(directory.is_relative_to((ROOT / "outputs").resolve()) and directory != (ROOT / "outputs").resolve(),
            "run directory must be a child of this repository's outputs")
    report_path = args.report.resolve()
    require(report_path.parent == (ROOT / "results").resolve() and report_path.suffix == ".json",
            "report must be an explicit JSON file directly in results")
    os.chdir(ROOT)
    if args.step == "export":
        export(directory, report_path)
    else:
        {"run": run, "verify": verify}[args.step](directory)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f"SH-01 FAILED exit=1: {error}", file=sys.stderr, flush=True)
        sys.exit(1)
