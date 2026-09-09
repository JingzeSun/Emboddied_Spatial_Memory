"""D-054 full test, read-only train reuse validation, and exact report export."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "ops")]
from cpmt.m1_candidate_policy import validate_candidate_policy
from cpmt.m1_train_reuse import validate_train_reuse, file_digest, require
from cpmt.run_provenance import capture_run_provenance, source_tree_sha256
from m1_candidate_availability import run_test

MARKER = Path("/root/autodl-tmp/cpmt_outputs/m1-v7-d051-train-719bb2d494d9/generation.ok.json")
EXPORT = ROOT / "results/m1_v7_d054_candidate_policy_and_train_reuse.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")


def verified(stage, binding):
    done = read(stage / "reuse.completed.json")
    require(done["binding"] == binding, "reuse completion source drift")
    require(file_digest(stage / "reuse.report.json") == done["report_sha256"], "reuse report changed")
    report = read(stage / "reuse.report.json")
    require(done["exit_code"] == (0 if report["accepted"] else 1), "reuse exit mismatch")
    require(report["source_and_tests_sha256"] == binding["source_and_tests_sha256"], "reuse report source mismatch")
    if report["accepted"]:
        policy = read(ROOT / "configs/m1_train_reuse_policy.json")
        require(report["verified_files"] == 1002 and report["verified_train_groups"] == 1000,
                "accepted reuse lacks complete file verification")
        require(report["arrays_digest"] == policy["arrays_digest"]
                and report["generation_marker_sha256"] == policy["generation_marker_sha256"]
                and report["source_changes"] == policy["reviewed_source_changes"], "accepted reuse identity mismatch")
        validate_candidate_policy(report["candidate_availability_policy"])
        for key in ("data_generated", "training_performed", "test_access", "validation_access", "formal_budget_authorized"):
            require(report[key] is False, "accepted reuse crossed boundary: " + key)
    return done, report


def reuse(stage, binding):
    tested = read(stage / "test.completed.json")
    require(tested["binding"] == binding and tested["exit_code"] == 0, "current full test must pass first")
    require(file_digest(stage / "test.log") == tested["log_sha256"], "full test log changed")
    if (stage / "reuse.completed.json").exists():
        done, _ = verified(stage, binding)
        print("TRAIN_REUSE_REUSED exit=" + str(done["exit_code"]), flush=True)
        return done["exit_code"]
    require(not (stage / "reuse.attempt.json").exists(), "interrupted verification retained; no automatic restart")
    provenance = capture_run_provenance(ROOT, component="candidate_policy_train_reuse", entrypoint=Path(__file__))
    write(stage / "reuse.attempt.json", {"binding": binding, "provenance": provenance})
    try:
        policy = validate_candidate_policy(read(ROOT / "configs/m1_candidate_availability_policy.json"))
        report = validate_train_reuse(ROOT, MARKER, read(ROOT / "configs/m1_train_reuse_policy.json"),
            progress=lambda n, total: print(f"TRAIN_REUSE_FILES_OK completed={n}/{total}", flush=True))
        report["candidate_availability_policy"] = policy
        exit_code = 0
    except Exception as error:
        report = {"accepted": False, "error": str(error), "traceback": traceback.format_exc(),
                  "data_generated": False, "training_performed": False, "test_access": False,
                  "validation_access": False, "formal_budget_authorized": False}
        print(report["traceback"], flush=True)
        exit_code = 1
    report.update(provenance=provenance, source_and_tests_sha256=binding["source_and_tests_sha256"])
    write(stage / "reuse.report.json", report)
    write(stage / "reuse.completed.json", {"binding": binding, "exit_code": exit_code,
          "report_sha256": file_digest(stage / "reuse.report.json")})
    verified(stage, binding)
    print("TRAIN_REUSE_RESULT accepted=" + str(report["accepted"]).lower(), flush=True)
    print("NEXT=bash ops/m1_candidate_policy.sh export", flush=True)
    return exit_code


def export(stage, binding):
    done, report = verified(stage, binding)
    payload = {"schema_version": "cpmt-candidate-policy-train-reuse-export-v1", "completion": done,
               "report": report, "full_test": read(stage / "test.completed.json"),
               "test_access": False, "validation_access": False, "formal_budget_authorized": False}
    if EXPORT.exists():
        require(read(EXPORT) == payload, "different prior export retained")
    else:
        write(EXPORT, payload)
    require(read(EXPORT) == payload, "export readback mismatch")
    print(f"EXPORT_VERIFIED path={EXPORT} sha256={file_digest(EXPORT)}", flush=True)
    print("CANDIDATE_POLICY_EXPORT_OK train_reuse=" + str(report["accepted"]).lower(), flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("test", "reuse", "export"))
    action = parser.parse_args().action
    import fcntl
    source = source_tree_sha256(ROOT, roots=("src", "scripts", "configs", "tests"))
    binding = {"source_and_tests_sha256": source, "ops_sha256": file_digest(Path(__file__)),
               "shell_sha256": file_digest(ROOT / "ops/m1_candidate_policy.sh"),
               "test_delivery_sha256": file_digest(ROOT / "ops/m1_candidate_availability.py")}
    if action != "export":
        require(not capture_run_provenance(ROOT, component="candidate_policy_phase")["git_dirty"],
                "clean committed checkout required")
    stage = Path("/root/autodl-tmp/cpmt_outputs") / ("m1-v7-d054-policy-" + source[:12])
    stage.mkdir(parents=True, exist_ok=True)
    print(f"CANDIDATE_POLICY_STAGE action={action} output={stage} training=false test_access=false", flush=True)
    with (stage / "phase.lock").open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = {"test": run_test, "reuse": reuse, "export": export}[action](stage, binding)
        require(source_tree_sha256(ROOT, roots=("src", "scripts", "configs", "tests")) == source,
                "source changed during phase")
        return result


if __name__ == "__main__":
    raise SystemExit(main())
