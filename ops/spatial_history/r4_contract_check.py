"""SH-04-R4-1: server-only common query and score contract check.

Runs only hand-authored standard-library tests.  It creates one new immutable
stage directory, never reads R2/R3 result folders, runs MuJoCo, trains a model,
downloads a weight, or creates an R4 family.  A passing receipt is engineering
evidence for these value boundaries only.
"""
import argparse
import ast
import importlib
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time
import unittest
from datetime import datetime, timezone


sys.dont_write_bytecode = True
from contract_check import ROOT, Tee, encode, git, require, sha, write_new


STAGE = "SH-04-R4-1-contract-v1"
RUN = Path("/root/autodl-tmp/spatial-history/sh04-r4-contract-v1")
REPORT = ROOT / "results/spatial_history_r4_contract_v1.json"
CONFIG = "configs/spatial_history/r4_contract_check_v1.json"
TESTS = ("tests/spatial_world_model/test_r4_query.py",
         "tests/spatial_world_model/test_r4_scoring.py")
BOUND = ("src/spatial_world_model/__init__.py", "src/spatial_world_model/pair_contract.py",
         "src/spatial_world_model/two_gate_contract.py", "src/spatial_world_model/r4_query.py",
         "src/spatial_world_model/r4_scoring.py", "tests/spatial_world_model/r4_examples.py", *TESTS,
         "ops/spatial_history/contract_check.py", "ops/spatial_history/r4_contract_check.py", CONFIG,
         "configs/spatial_history/protocol_r4_v1.json", "configs/spatial_history/two_gate_engineering_v1.json",
         "docs/METHOD.md", "docs/DATA.md")
LIMIT_S = 300
LIMIT_BYTES = 8 * 1024 * 1024
LIMIT_RSS = 512 * 1024 * 1024


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def configuration():
    value = read(ROOT / CONFIG)
    require(value["version"] == "sh04-r4-contract-check-v1", "wrong R4-1 config")
    require(value["source_protocol"] == "configs/spatial_history/protocol_r4_v1.json", "wrong R4 source")
    protocol = read(ROOT / value["source_protocol"])
    require(protocol["version"] == "sh04-r4-comparison-contract-v1"
            and protocol["status"] == "frozen_for_review_not_executable", "R4 protocol changed")
    require(value["server_only"] is True and value["scope"] == "standard-library value-contract and synthetic-score checks only",
            "wrong R4-1 scope")
    require(all(value[name] is False for name in ("generation_authorized", "training_authorized",
            "weight_download_authorized", "confirmation_authorized")), "scientific work is not authorized")
    require(all(value[name] == 0 for name in ("new_simulation_steps", "new_training_steps",
            "new_weight_download_bytes")), "R4-1 must not compute new science")
    require(value["tests"] == list(TESTS), "test registration changed")
    require(value["limits"] == {"wall_clock_s": LIMIT_S, "new_stage_bytes": LIMIT_BYTES,
                                "process_rss_bytes": LIMIT_RSS}, "resource limits changed")
    require(all(flag is False for flag in value["claims"].values()), "engineering check has a scientific claim")
    return value


def binding():
    return {name: sha((ROOT / name).read_bytes()) for name in BOUND}


def test_names(commit=None):
    names = []
    for name in TESTS:
        raw = ((ROOT / name).read_bytes() if commit is None else subprocess.check_output(
            ["git", "-C", str(ROOT), "show", f"{commit}:{name}"]))
        tree = ast.parse(raw)
        names.extend(f"{Path(name).stem}.{cls.name}.{fn.name}" for cls in tree.body
                     if isinstance(cls, ast.ClassDef) for fn in cls.body
                     if isinstance(fn, ast.FunctionDef) and fn.name.startswith("test_"))
    require(names and len(names) == len(set(names)), "empty or duplicate R4-1 test census")
    return sorted(names)


def inventory():
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "tests/spatial_world_model"))
    modules = [importlib.import_module(Path(name).stem) for name in TESTS]
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(module) for module in modules)

    def flatten(item):
        return [name for child in item for name in flatten(child)] if isinstance(item, unittest.TestSuite) else [item.id()]

    names = sorted(flatten(suite))
    require(names and len(names) == len(set(names)), "invalid unittest inventory")
    require(len(names) == len(test_names()), "AST and unittest R4-1 test census differ")
    return suite, names


def used_bytes(directory):
    return sum(path.stat().st_size for path in directory.rglob("*") if path.is_file())


def stage_path(value):
    path = value.resolve()
    require(path == RUN, "R4-1 run directory is fixed to preserve failed stages")
    return path


def verify(directory):
    configuration()
    receipt = read(directory / "receipt.json")
    require(receipt["stage"] == STAGE and receipt["exit_code"] == 0, "no successful R4-1 receipt")
    require(receipt["binding"] == binding(), "source/config binding changed")
    _, names = inventory()
    require(receipt["test_names"] == names and receipt["tests_run"] == len(names), "test inventory changed")
    require(receipt["failures"] == receipt["errors"] == receipt["skipped"] == 0, "incomplete server tests")
    require(receipt["artifacts"] == {"tests.log": sha((directory / "tests.log").read_bytes())}, "artifact digest")
    require(0 <= receipt["elapsed_s"] <= LIMIT_S and receipt["stage_bytes"] <= LIMIT_BYTES
            and receipt["parent_peak_rss_bytes"] <= LIMIT_RSS, "R4-1 resource receipt invalid")
    require(receipt["new_simulation_steps"] == receipt["new_training_steps"] == receipt["new_weight_download_bytes"] == 0,
            "R4-1 cannot certify science")
    require(not any(receipt["claims"].values()), "R4-1 cannot certify a scientific claim")
    print(f"{STAGE} VERIFIED tests={len(names)} exit=0", flush=True)
    return receipt


def run(directory):
    if directory.exists():
        print(f"Existing directory: {directory}; verify only, never rerun/overwrite.", flush=True)
        return verify(directory)
    require(platform.system() == "Linux", "server-only run: use the Linux server")
    require((3, 11) <= sys.version_info[:2] < (3, 13), "requires Python 3.11 or 3.12")
    configuration()
    require(not git("status", "--porcelain", "--", *BOUND), "bound files must be committed and clean")
    before, commit, began = binding(), git("rev-parse", "HEAD"), time.monotonic()
    suite, names = inventory()
    directory.mkdir(parents=True, exist_ok=False)
    write_new(directory / "started.json", {"stage": STAGE, "started": datetime.now(timezone.utc).isoformat(),
                                            "commit": commit, "binding": before, "limits": {"wall_clock_s": LIMIT_S,
                                            "new_stage_bytes": LIMIT_BYTES, "process_rss_bytes": LIMIT_RSS}})
    with (directory / "tests.log").open("x", encoding="utf-8") as log:
        result = unittest.TextTestRunner(stream=Tee(log), verbosity=2).run(suite)
    finished, elapsed_s = datetime.now(timezone.utc), time.monotonic() - began
    rss_bytes = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    success = (result.wasSuccessful() and result.testsRun == len(names) and not result.skipped
               and before == binding() and elapsed_s <= LIMIT_S and used_bytes(directory) <= LIMIT_BYTES
               and rss_bytes <= LIMIT_RSS)
    receipt = {"stage": STAGE, "commit": commit, "binding": before, "finished": finished.isoformat(),
               "python": sys.version, "platform": platform.platform(), "repository": str(ROOT),
               "test_names": names, "tests_run": result.testsRun, "failures": len(result.failures),
               "errors": len(result.errors), "skipped": len(result.skipped),
               "artifacts": {"tests.log": sha((directory / "tests.log").read_bytes())},
               "elapsed_s": elapsed_s, "stage_bytes": used_bytes(directory), "parent_peak_rss_bytes": rss_bytes,
               "new_simulation_steps": 0, "new_training_steps": 0, "new_weight_download_bytes": 0,
               "claims": configuration()["claims"], "exit_code": 0 if success else 1}
    write_new(directory / "receipt.json", receipt)
    require(success, f"{STAGE} failed; preserved at {directory}")
    return verify(directory)


def export(directory, report_path):
    receipt = verify(directory)
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "tests/spatial_world_model"))
    examples = importlib.import_module("r4_examples").examples()
    report = {"kind": "r4_contract_engineering_check", "status": "passed", "receipt": receipt,
              "receipt_sha256": sha((directory / "receipt.json").read_bytes()), "examples": examples,
              "claims": configuration()["claims"]}
    raw = encode(report)
    if report_path.exists():
        require(report_path.read_bytes() == raw, f"different report exists: {report_path}; not overwritten")
    else:
        write_new(report_path, report)
    print(f"{STAGE} EXPORTED {report_path} exit=0", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("run", "verify", "export"))
    parser.add_argument("--run-dir", type=Path, default=RUN)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    directory = stage_path(args.run_dir)
    report_path = args.report.resolve()
    require(report_path.parent == (ROOT / "results").resolve() and report_path.suffix == ".json",
            "report must be an explicit JSON file directly in results")
    os.chdir(ROOT)
    {"run": run, "verify": verify, "export": lambda path: export(path, report_path)}[args.step](directory)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f"{STAGE} FAILED exit=1: {error}", file=sys.stderr, flush=True)
        sys.exit(1)
