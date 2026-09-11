"""SH-03 check/run/verify/export: fixed cases, immutable per-step receipts.

Only the isolated server children import tests or the physical generator.
Completed cases are reused; partial or runtime-failed cases are never retried.
"""
import argparse
import ast
import base64
import importlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import traceback
import unittest

from contract_check import ROOT, encode, git, require, sha, write_new
from physics_check import BOUND as SH02_BOUND, DISK, ENV, environment, now, stream

REGISTRY = "configs/spatial_history/development_audit_v1.json"
PRIOR = "results/spatial_history_physics_v2_flat_pusher.json"
TEST = "tests/spatial_world_model/test_development_audit.py"
BOUND = (*SH02_BOUND, REGISTRY, PRIOR, TEST,
         "src/spatial_world_model/development_audit.py",
         "ops/spatial_history/development_check.py")
RUN = DISK / "spatial-history/sh03-development-v1"
REPORT = ROOT / "results/spatial_history_development_audit_v1.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def log_tail(unit):
    return {name: (unit / name).read_text(encoding="utf-8", errors="replace")[-16000:]
            for name in ("run.log", "parent-error.txt") if (unit / name).exists()}


def binding():
    return {p: sha((ROOT / p).read_bytes()) for p in BOUND}


def registry():
    sys.path.insert(0, str(ROOT / "src"))
    from spatial_world_model.development_audit import validate_registry
    value = read(ROOT / REGISTRY)
    validate_registry(value)
    return value


def prerequisites():
    value = read(ROOT / PRIOR)
    receipt = value["receipt"]
    require(value["receipt_sha256"] == sha(encode(receipt)) == registry()["prior_receipt_sha256"]
            and receipt["stage"] == "SH-02" and receipt["exit_code"] == 0
            and len(receipt["test_names"]) == 32, "approved SH-02 receipt invalid")
    # Historical documents are checked against their original commit, not the
    # expanded SH-03 documents. Approved implementation bytes must still match.
    for name, digest in receipt["binding"].items():
        original = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{receipt['commit']}:{name}"])
        require(sha(original) == digest, f"original SH-02 binding invalid: {name}")
        if not name.startswith("docs/"):
            require(sha((ROOT / name).read_bytes()) == digest, f"approved implementation changed: {name}")


def names():
    tree = ast.parse((ROOT / TEST).read_text(encoding="utf-8"))
    return sorted(f"{Path(TEST).stem}.{cls.name}.{node.name}"
                  for cls in tree.body if isinstance(cls, ast.ClassDef)
                  for node in cls.body if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"))


def manifest(directory):
    return {p.relative_to(directory).as_posix(): sha(p.read_bytes())
            for p in sorted(directory.rglob("*")) if p.is_file() and p != directory / "receipt.json"}


def size(directory):
    return sum(p.stat().st_size for p in directory.rglob("*") if p.is_file())


def source_guard(started):
    require(started["binding"] == binding(), "SH-03 source/contract changed")
    require(not git("status", "--porcelain", "--", *BOUND), "bound files must be committed and clean")


def sealed(directory, started):
    require((directory / "receipt.json").is_file(), f"partial step preserved at {directory}; no automatic retry")
    receipt = read(directory / "receipt.json")
    require(receipt["binding"] == started["binding"] and receipt["commit"] == started["commit"], "step source mismatch")
    require(receipt["artifacts"] == manifest(directory), f"step artifacts changed: {directory}")
    return receipt


def launch(directory, started, step, case_id=None):
    directory.mkdir(exist_ok=False)
    write_new(directory / "started.json", {"step": step, "case_id": case_id, "started": now()})
    env = dict(os.environ, MUJOCO_GL="egl", PYTHONUNBUFFERED="1", PYTHONDONTWRITEBYTECODE="1",
               OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", SH03_CHILD_DIR=str(directory))
    command = [sys.executable, str(Path(__file__).resolve()), step, "--run-dir", str(directory.parent)]
    if case_id is not None:
        command.extend(["--case-id", case_id])
    timer, code = time.monotonic(), 1
    try:
        code = stream(command, directory / "run.log", env)
    except Exception:
        with (directory / "parent-error.txt").open("x") as handle:
            traceback.print_exc(file=handle)
    unchanged = binding() == started["binding"] and git("rev-parse", "HEAD") == started["commit"]
    if not unchanged:
        code = 1
    write_new(directory / "receipt.json", {
        "step": step, "case_id": case_id, "commit": started["commit"], "binding": started["binding"],
        "finished": now(), "elapsed_s": time.monotonic() - timer, "exit_code": code,
        "source_unchanged": unchanged, "artifacts": manifest(directory)})
    print(f"SH-03 STEP FINISHED step={case_id or 'check'} exit={code}", flush=True)
    return sealed(directory, started)


def stage(directory):
    require((directory / "started.json").is_file(), "SH-03/check required first")
    started = read(directory / "started.json")
    require(started["stage"] == "SH-03" and started["registry"] == registry(), "stage registry changed")
    source_guard(started)
    require(sha((directory / "environment.json").read_bytes()) == started["environment_sha256"], "environment record changed")
    return started


def server():
    require(platform.system() == "Linux" and DISK.is_mount(), "Linux server/data mount required")
    require(Path(sys.prefix).resolve() == ENV.resolve(), f"use {ENV}/bin/python")
    return environment()


def check(directory):
    env = server()
    prerequisites()
    if not directory.exists():
        source_guard({"binding": binding()})
        require(shutil.disk_usage(DISK).free >= registry()["output_budget_bytes"], "less than 2 GiB filesystem free; also check rental quota")
        directory.mkdir(parents=True, exist_ok=False)
        environment_record = {"setup": env, "python": sys.version, "platform": platform.platform(),
                              "repository": str(ROOT), "executable": sys.executable, "MUJOCO_GL": "egl"}
        write_new(directory / "environment.json", environment_record)
        write_new(directory / "started.json", {"stage": "SH-03", "started": now(), "commit": git("rev-parse", "HEAD"),
                  "binding": binding(), "registry": registry(), "environment_sha256": sha(encode(environment_record))})
    started = stage(directory)
    unit = directory / "check"
    receipt = sealed(unit, started) if unit.exists() else launch(unit, started, "_tests")
    require(receipt["exit_code"] == 0, "check failed; export diagnosis, do not run cases")
    result = read(unit / "tests-result.json")
    require(result["exit_code"] == 0 and result["test_names"] == names() and result["tests_run"] == len(names()), "incomplete check receipt")
    print(f"SH-03 CHECK VERIFIED tests={len(names())} exit=0", flush=True)


def inspect(directory):
    started = stage(directory)
    check_receipt = sealed(directory / "check", started)
    records, missing = [], False
    for case in started["registry"]["cases"]:
        unit = directory / case["case_id"]
        if not unit.exists():
            missing = True
            records.append({"case": case, "status": "not_run"})
            continue
        require(not missing, "case order has a gap")
        receipt = sealed(unit, started)
        record = {"case": case, "receipt": receipt, "status": "runtime_failed"}
        if receipt["exit_code"] == 0:
            audit = read(unit / "data/audit.json")
            require(audit["case"] == case and bool(audit["accepted"]) == all(audit["checks"].values()), "case audit mismatch")
            record.update(audit=audit, status="passed" if audit["accepted"] else "audit_failed")
        records.append(record)
    byte_count = size(directory)
    passed = check_receipt["exit_code"] == 0 and all(r["status"] == "passed" for r in records)
    passed = passed and byte_count <= started["registry"]["output_budget_bytes"]
    return {"stage": "SH-03", "started": started, "check_receipt": check_receipt,
            "cases": records, "status": "passed" if passed else "failed",
            "artifact_bytes": byte_count, "model_experiment_run": False}


def run(directory):
    server()
    started = stage(directory)
    require(git("rev-parse", "HEAD") == started["commit"], "checkout changed since check; no new computation")
    check_unit = directory / "check"
    require(sealed(check_unit, started)["exit_code"] == 0, "successful SH-03/check required")
    result = read(check_unit / "tests-result.json")
    require(result["exit_code"] == 0 and result["test_names"] == names() and result["tests_run"] == len(names()), "incomplete tests")
    inspect(directory)  # Verify every existing receipt before any new computation.
    for index, case in enumerate(started["registry"]["cases"]):
        unit = directory / case["case_id"]
        if unit.exists():
            receipt = sealed(unit, started)
            print(f"SH-03 REUSED {case['case_id']} exit={receipt['exit_code']}", flush=True)
        else:
            require(size(directory) < started["registry"]["output_budget_bytes"], "output budget reached; retained, export diagnosis")
            source_guard(started)
            print(f"SH-03 CASE {index + 1}/16 {case['case_id']}", flush=True)
            receipt = launch(unit, started, "_case", case["case_id"])
        require(receipt["exit_code"] == 0, f"runtime failure in {case['case_id']}; remaining cases not started; export diagnosis")
        audit = read(unit / "data/audit.json")
        print(f"SH-03 AUDIT {case['case_id']} accepted={audit['accepted']} failed={audit['failed_checks']}", flush=True)
        # Completed scientific failures remain in the fixed census. No replacement.
    value = inspect(directory)
    require(value["status"] == "passed", "fixed audit/budget failed; all completed cases retained; export diagnosis")
    print("SH-03 VERIFIED cases=16 unique_branches=64 replay_branches=64 exit=0", flush=True)


def export(directory, report):
    value = inspect(directory)
    value["kind"] = "fixed_development_physics_audit"
    value["environment"] = read(directory / "environment.json")
    value["tests"] = read(directory / "check/tests-result.json") if (directory / "check/tests-result.json").exists() else None
    from contact_diagnose import summarize
    for record in value["cases"]:
        unit = directory / record["case"]["case_id"]
        if not unit.exists():
            continue
        record["previews_png_base64"] = {p.name: base64.b64encode(p.read_bytes()).decode()
                                         for p in sorted((unit / "data/raw").glob("*.png"))}
        record["contact_process_by_branch"] = {}
        for path in sorted((unit / "data/raw").glob("world-*-action-*-trace.json")):
            if "-replay-" in path.name:
                continue
            try:
                summary = summarize(read(path))
                summary["object_pusher_episode_count"] = len(summary.pop("object_pusher_episodes"))
            except (ValueError, KeyError, TypeError, IndexError) as error:
                # A runtime failure may leave a truncated trace. Preserve its
                # manifest/hash and report the parse error rather than hiding it.
                summary = {"summary_error": str(error)}
            summary["trace_sha256"] = record["receipt"]["artifacts"][path.relative_to(unit).as_posix()]
            record["contact_process_by_branch"][path.name] = summary
        if record["status"] != "passed":
            record["failure_log_tail"] = log_tail(unit)
    if value["check_receipt"]["exit_code"] != 0:
        value["check_failure_log_tail"] = log_tail(directory / "check")
    payload = {"audit": value, "audit_sha256": sha(encode(value))}
    if report.exists():
        require(report.read_bytes() == encode(payload), "different report exists; preserved")
    else:
        write_new(report, payload)
    print(f"SH-03 EXPORTED status={value['status']} {report} exit=0", flush=True)


def worker(directory, case_id):
    if case_id is not None:
        from spatial_world_model.development_audit import generate_case
        plan = registry()
        case = next(c for c in plan["cases"] if c["case_id"] == case_id)
        generate_case(directory / "data", ROOT / "configs/spatial_history/physics_v1.json",
                      ROOT / "configs/spatial_history/physics_v1.xml", case, plan)
        return 0  # Completed scientific failure is distinct from a runtime crash.
    sys.path.insert(0, str(ROOT / "tests/spatial_world_model"))
    suite = unittest.defaultTestLoader.loadTestsFromModule(importlib.import_module(Path(TEST).stem))
    def flatten(item):
        return [n for child in item for n in flatten(child)] if isinstance(item, unittest.TestSuite) else [item.id()]
    actual = sorted(flatten(suite))
    require(actual == names(), "runtime/static test inventory mismatch")
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
    success = result.wasSuccessful() and result.testsRun == len(actual) and not result.skipped and not result.expectedFailures
    write_new(directory / "tests-result.json", {"test_names": actual, "tests_run": result.testsRun,
              "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
              "exit_code": 0 if success else 1})
    return 0 if success else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("check", "run", "verify", "export", "_tests", "_case"))
    parser.add_argument("--run-dir", type=Path, default=RUN)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--case-id")
    args = parser.parse_args()
    directory, report = args.run_dir.resolve(), args.report.resolve()
    require(directory.is_relative_to((DISK / "spatial-history").resolve()) and directory != (DISK / "spatial-history").resolve(), "named data-disk stage directory required")
    require(report.parent == (ROOT / "results").resolve() and report.suffix == ".json", "JSON report directly in results required")
    plan = registry()
    if args.step in ("_tests", "_case"):
        require(platform.system() == "Linux", "server child required")
        require(args.case_id in [c["case_id"] for c in plan["cases"]] if args.step == "_case" else args.case_id is None, "invalid child case")
        unit = directory / (args.case_id if args.step == "_case" else "check")
        require(os.environ.get("SH03_CHILD_DIR") == str(unit), "child requires stage launcher")
        return worker(unit, args.case_id)
    if args.step == "export":
        export(directory, report)
    elif args.step == "verify":
        value = inspect(directory)
        require(value["status"] == "passed", "audit not passed; export available")
        print("SH-03 VERIFIED cases=16 unique_branches=64 replay_branches=64 exit=0", flush=True)
    else:
        {"check": check, "run": run}[args.step](directory)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"SH-03 FAILED exit=1: {error}", file=sys.stderr, flush=True)
        sys.exit(1)
