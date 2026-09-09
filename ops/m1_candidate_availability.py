"""Foreground test/check/export for one bounded experimental repair phase."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts"), str(ROOT / "ops")]
from cpmt.m1_branch_preflight import require, summarize
from cpmt.run_provenance import capture_run_provenance, source_tree_sha256
from run_m1_train_branch_preflight import file_digest, read_json, write_json
from run_m1_candidate_availability_check import REPORT, REPORT_SHA
from m1_train_preflight import capacity

EXPORT = ROOT / "results/m1_v7_d053_candidate_availability.json"


def files(directory):
    return {p.relative_to(directory).as_posix(): file_digest(p)
            for p in sorted(directory.rglob("*")) if p.is_file()}


def command(args, log):
    with log.open("x", encoding="utf-8") as stream:
        child = subprocess.Popen(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, encoding="utf-8", errors="replace")
        for line in child.stdout:
            print(line, end="", flush=True)
            stream.write(line)
            stream.flush()
        return child.wait()


def verify(stage, binding):
    complete = read_json(stage / "check.completed.json")
    require(complete["binding"] == binding, "check source binding changed")
    require(complete["files"] == files(stage / "run"), "check artifacts changed")
    path = stage / "run/report.json"
    report = read_json(path) if path.exists() else None
    if report:
        require(report["source_and_tests_sha256"] == binding["source_and_tests_sha256"]
                and report["source_report_sha256"] == REPORT_SHA, "report provenance mismatch")
        require(report["gate"] == summarize(report["groups"]), "matrix gate mismatch")
        require(complete["exit_code"] == (0 if report["gate"]["pass"] else 1), "exit/gate mismatch")
        if report["gate"]["pass"]:
            require(report["reference_steps_verified"] == 640 and report["recovery_steps_verified"] == 32,
                    "successful check lacks all reference/recovery comparisons")
            require(all(not r["failures"] and r["reference_steps_verified"] == 40
                        and r["recovery_steps_verified"] == 2 for r in report["groups"]),
                    "successful group lacks compatibility checks")
        for row in report["groups"]:
            directory = stage / "run" / f"group_{row['group']:06d}"
            require(files(directory) == row["files"], "group files changed")
            require(read_json(directory / "result.json") == {k: v for k, v in row.items() if k != "files"},
                    "group/report contents differ")
        for key in ("validation_access", "test_access", "data_generated", "training_performed", "formal_budget_authorized"):
            require(report[key] is False, "report boundary changed: " + key)
    else:
        require(complete["exit_code"] != 0, "success without report")
    return complete, report


def run_test(stage, binding):
    marker = stage / "test.completed.json"
    if marker.exists():
        result = read_json(marker)
        require(result["binding"] == binding, "test binding changed")
        require(file_digest(stage / "test.log") == result["log_sha256"], "test log changed")
        print(f"AVAILABILITY_TEST_REUSED tests={result['tests']} exit={result['exit_code']}", flush=True)
        return result["exit_code"]
    require(not (stage / "test.attempt.json").exists(), "interrupted test retained; review before retry")
    write_json(stage / "test.attempt.json", {"binding": binding})
    code = (
        "import json,sys,unittest; "
        "r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover('tests')); "
        "json.dump({'tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skipped':len(r.skipped)},open(sys.argv[1],'x')); "
        "sys.exit(0 if r.wasSuccessful() and not r.skipped and r.testsRun>=299 else 1)"
    )
    result_path = stage / "test.result.json"
    exit_code = command([sys.executable, "-c", code, str(result_path)], stage / "test.log")
    result = read_json(result_path) if result_path.exists() else {"tests": 0, "errors": 1}
    result.update(binding=binding, exit_code=exit_code, log_sha256=file_digest(stage / "test.log"))
    write_json(marker, result)
    print(f"AVAILABILITY_TEST_RESULT tests={result['tests']} exit={exit_code}", flush=True)
    return exit_code


def run_check(stage, binding):
    tested = read_json(stage / "test.completed.json")
    require(tested["binding"] == binding and tested["exit_code"] == 0, "current full test must pass first")
    require(file_digest(stage / "test.log") == tested["log_sha256"], "test evidence changed")
    if (stage / "check.completed.json").exists():
        complete, _ = verify(stage, binding)
        print("AVAILABILITY_CHECK_REUSED exit=" + str(complete["exit_code"]), flush=True)
        return complete["exit_code"]
    require(not (stage / "check.attempt.json").exists() and not (stage / "run").exists(),
            "interrupted/unknown check retained; no automatic retry")
    resources = capacity()
    print("AVAILABILITY_RESOURCES=" + json.dumps(resources, sort_keys=True), flush=True)
    write_json(stage / "check.attempt.json", {"binding": binding, "resources": resources})
    began = time.monotonic()
    exit_code = command([sys.executable, "scripts/run_m1_candidate_availability_check.py",
                        "--output", str(stage / "run"), "--workers", str(resources["workers"])], stage / "check.log")
    write_json(stage / "check.completed.json", {"binding": binding, "exit_code": exit_code,
        "wall_seconds": time.monotonic() - began, "files": files(stage / "run")})
    verify(stage, binding)
    print("AVAILABILITY_CHECK_EXIT=" + str(exit_code), flush=True)
    print("NEXT=bash ops/m1_candidate_availability.sh export", flush=True)
    return exit_code


def export(stage, binding):
    complete, report = verify(stage, binding)
    payload = {"schema_version": "cpmt-candidate-availability-export-v1", "completion": complete,
               "report": report, "full_test": read_json(stage / "test.completed.json"),
               "check_log_tail": (stage / "check.log").read_text(encoding="utf-8").splitlines()[-100:],
               "test_access": False, "validation_access": False, "formal_budget_authorized": False}
    if EXPORT.exists():
        require(read_json(EXPORT) == payload, "different existing export retained")
    else:
        write_json(EXPORT, payload)
    require(read_json(EXPORT) == payload, "export readback mismatch")
    print(f"EXPORT_VERIFIED path={EXPORT} sha256={file_digest(EXPORT)}", flush=True)
    print("AVAILABILITY_EXPORT_OK experimental_pass=" + str(bool(report and report["gate"]["pass"])).lower(), flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("test", "check", "export"))
    action = parser.parse_args().action
    import fcntl
    require(file_digest(REPORT) == REPORT_SHA, "preserved source failure report changed")
    source = source_tree_sha256(ROOT, roots=("src", "scripts", "configs", "tests"))
    binding = {"source_and_tests_sha256": source, "source_report_sha256": REPORT_SHA,
               "ops_sha256": file_digest(Path(__file__)),
               "shell_sha256": file_digest(ROOT / "ops/m1_candidate_availability.sh")}
    provenance = capture_run_provenance(ROOT, component="availability_phase", entrypoint=Path(__file__))
    if action != "export":
        require(not provenance["git_dirty"], "clean committed checkout required")
    stage = Path("/root/autodl-tmp/cpmt_outputs") / ("m1-v7-d053-availability-" + source[:12])
    stage.mkdir(parents=True, exist_ok=True)
    print(f"AVAILABILITY_STAGE action={action} output={stage} formal_budget_authorized=false", flush=True)
    with (stage / "phase.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        path = stage / "provenance.json"
        if not path.exists():
            write_json(path, provenance)
        result = {"test": run_test, "check": run_check, "export": export}[action](stage, binding)
        require(source_tree_sha256(ROOT, roots=("src", "scripts", "configs", "tests")) == source,
                "source changed during phase")
        return result


if __name__ == "__main__":
    raise SystemExit(main())
