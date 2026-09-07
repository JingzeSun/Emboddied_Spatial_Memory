#!/usr/bin/env bash
# Unique active CPMT server phase: profile both registered architecture arms.
#
# Prerequisites:
# - the clean checkout descends from CPMT_TESTED_COMMIT;
# - its matching 192-test marker exists;
# - the verified 1,000-group train arrays and manifest exist.
#
# Read boundary: the frozen train arrays/manifest, tested runner/config/source,
# the full-test marker and Git metadata.
# Write boundary: one ignored profile root with an independent report/log for
# each architecture arm.
# Resume policy: validate and reuse each complete report independently. A
# missing arm is run without rerunning the completed arm. This stage does not
# select a budget, export scientific metrics, read validation/test, run causal
# evaluation, generate data, or modify Git.

set -uo pipefail

CPMT_SERVER_STEP_ID="m1_v6_v8_d043_two_architecture_runtime_profile"
CPMT_TESTED_COMMIT="8b304e39403731bc6be28c26ff38699da71d879a"
CPMT_EXPECTED_PROTOCOL="73666cabb77b4884302d77ca621669bfdc77e86a44951b8a92b97208509c0eec"
CPMT_EXPECTED_DATASET="m1-paired-latent-worlds-v8-fixed-range-current-energy"
CPMT_EXPECTED_TESTS="192"
CPMT_EXPECTED_ARRAYS_DIGEST="e8a890f1b254a7109af641fea57fcbea5efd931b4272d8e96cb870f51604b168"
CPMT_PROFILE_SEED="7"
CPMT_PROFILE_LEARNING_RATE="0.0006"
CPMT_PROFILE_STEPS="300"
CPMT_THREADS="${CPMT_THREADS:-16}"

CPMT_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
CPMT_REPO_DIR="$(git -C "$CPMT_SCRIPT_DIR" rev-parse --show-toplevel)" || exit 2
CPMT_CURRENT_COMMIT="$(git -C "$CPMT_REPO_DIR" rev-parse HEAD)" || exit 2
CPMT_TESTED_SHORT="$(git -C "$CPMT_REPO_DIR" rev-parse --short=7 \
  "$CPMT_TESTED_COMMIT")" || exit 2
CPMT_FULL_TEST_DIR="$CPMT_REPO_DIR/outputs/m1-v6-v8-d043-profile-full-test-$CPMT_TESTED_SHORT"
CPMT_FULL_TEST_MARKER="$CPMT_FULL_TEST_DIR/full_test.ok.json"
CPMT_TRAIN_DIR="$CPMT_REPO_DIR/outputs/m1-v6-v8-d043-train-g1000-53539ce"
CPMT_TRAIN_ARRAYS="$CPMT_TRAIN_DIR/train.npz"
CPMT_TRAIN_MANIFEST="$CPMT_TRAIN_DIR/train.manifest.json"
CPMT_PROFILE_ROOT="$CPMT_REPO_DIR/outputs/m1-v6-v8-d043-runtime-profile-$CPMT_TESTED_SHORT"

cpmt_fail() {
  local CPMT_FAILURE_MESSAGE="$1"
  printf "SERVER_STEP_FAILED id=%s reason=%s\n" \
    "$CPMT_SERVER_STEP_ID" "$CPMT_FAILURE_MESSAGE" >&2
  exit 1
}

[[ "$#" -eq 0 ]] || cpmt_fail "unexpected_arguments"
[[ "$CPMT_THREADS" =~ ^[1-9][0-9]*$ ]] || cpmt_fail "invalid_thread_count"
command -v python >/dev/null 2>&1 || cpmt_fail "python_not_found"
command -v git >/dev/null 2>&1 || cpmt_fail "git_not_found"
git -C "$CPMT_REPO_DIR" merge-base --is-ancestor \
  "$CPMT_TESTED_COMMIT" "$CPMT_CURRENT_COMMIT" || \
  cpmt_fail "tested_commit_not_in_history"
git -C "$CPMT_REPO_DIR" diff --quiet || cpmt_fail "tracked_changes_present"
git -C "$CPMT_REPO_DIR" diff --cached --quiet || \
  cpmt_fail "staged_changes_present"
[[ -z "$(git -C "$CPMT_REPO_DIR" ls-files --others --exclude-standard)" ]] || \
  cpmt_fail "untracked_files_present"
CPMT_REMOTE_HEAD="$(git -C "$CPMT_REPO_DIR" ls-remote \
  origin refs/heads/main | awk '{print $1}')"
[[ "$CPMT_REMOTE_HEAD" == "$CPMT_CURRENT_COMMIT" ]] || \
  cpmt_fail "origin_main_does_not_match_checkout"
git -C "$CPMT_REPO_DIR" diff --quiet "$CPMT_TESTED_COMMIT" HEAD -- \
  src scripts configs tests || \
  cpmt_fail "scientific_or_test_paths_changed_since_full_test"

CPMT_PROTOCOL="$({
  cd "$CPMT_REPO_DIR" || exit 2
  python - <<'PY'
from pathlib import Path
from src.cpmt.m1_protocol import load_and_validate, protocol_sha256

config = load_and_validate(Path("configs/m1_hard_condition.json"))
print(protocol_sha256(config))
PY
})" || cpmt_fail "protocol_validation_failed"
[[ "$CPMT_PROTOCOL" == "$CPMT_EXPECTED_PROTOCOL" ]] || \
  cpmt_fail "protocol_hash_mismatch"

[[ -f "$CPMT_FULL_TEST_MARKER" ]] || cpmt_fail "full_test_marker_missing"
python - \
  "$CPMT_FULL_TEST_MARKER" "$CPMT_TESTED_COMMIT" "$CPMT_EXPECTED_PROTOCOL" \
  "$CPMT_EXPECTED_DATASET" "$CPMT_EXPECTED_TESTS" <<'PY' || \
  cpmt_fail "full_test_marker_validation_failed"
import json
import sys
from pathlib import Path

marker = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert marker == {
    "commit": sys.argv[2],
    "dataset_version": sys.argv[4],
    "exit_code": 0,
    "protocol_sha256": sys.argv[3],
    "tests": int(sys.argv[5]),
}
print("FULL_TEST_PREREQUISITE_OK tests={}".format(marker["tests"]))
PY

[[ -f "$CPMT_TRAIN_ARRAYS" && -f "$CPMT_TRAIN_MANIFEST" ]] || \
  cpmt_fail "train_artifact_pair_missing"
python - \
  "$CPMT_TRAIN_MANIFEST" "$CPMT_EXPECTED_PROTOCOL" \
  "$CPMT_EXPECTED_DATASET" "$CPMT_EXPECTED_ARRAYS_DIGEST" <<'PY' || \
  cpmt_fail "train_manifest_validation_failed"
import json
import sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert manifest["protocol_sha256"] == sys.argv[2]
assert manifest["dataset_version"] == sys.argv[3]
assert manifest["arrays_digest"] == sys.argv[4]
assert manifest["split"] == "train"
assert manifest["paired_groups_total"] == 1000
assert manifest["decisions"] == 40000
assert manifest["online_chain_decisions"] == 38000
assert manifest["recovery_training_examples"] == 2000
assert manifest["teacher_health_gate"]["pass"] is True
assert manifest["teacher_reference_agreement"] == 1.0
assert manifest["test_generated"] is False
assert manifest["formal_run"] is False
print("TRAIN_INPUT_PREREQUISITE_OK arrays_digest={}".format(sys.argv[4]))
PY

printf "SERVER_STEP_BEGIN id=%s\n" "$CPMT_SERVER_STEP_ID"
printf "repo=%s\ncurrent_commit=%s\ntested_commit=%s\n" \
  "$CPMT_REPO_DIR" "$CPMT_CURRENT_COMMIT" "$CPMT_TESTED_COMMIT"
printf "protocol_sha256=%s dataset=%s\n" \
  "$CPMT_PROTOCOL" "$CPMT_EXPECTED_DATASET"
printf "read_boundary=frozen_train_arrays_manifest_tested_code_full_test_and_git\n"
printf "write_boundary=%s\n" "$CPMT_PROFILE_ROOT"
printf "profile_seed=%s learning_rate=%s steps=%s threads=%s\n" \
  "$CPMT_PROFILE_SEED" "$CPMT_PROFILE_LEARNING_RATE" \
  "$CPMT_PROFILE_STEPS" "$CPMT_THREADS"
printf "selection=false scientific_metrics_exported=false validation_access=false test_access=false\n"

cpmt_validate_profile() {
  local CPMT_REPORT_PATH="$1"
  local CPMT_ARCHITECTURE="$2"
  python - \
    "$CPMT_REPORT_PATH" "$CPMT_ARCHITECTURE" "$CPMT_EXPECTED_PROTOCOL" \
    "$CPMT_EXPECTED_DATASET" "$CPMT_EXPECTED_ARRAYS_DIGEST" \
    "$CPMT_PROFILE_SEED" "$CPMT_PROFILE_LEARNING_RATE" \
    "$CPMT_PROFILE_STEPS" <<'PY'
import json
import math
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert report["schema_version"] == "cpmt-m1-v8-budget-runtime-profile-v1"
assert report["runner"] == "run_m1_train_inner_dev_budget_runtime_profile_v1"
assert report["architecture"] == sys.argv[2]
assert report["protocol_sha256"] == sys.argv[3]
assert report["dataset_version"] == sys.argv[4]
assert report["input_arrays"]["train"]["arrays_digest"] == sys.argv[5]
assert report["formal_run"] is False
assert report["selection_performed"] is False
assert report["scientific_metrics_exported"] is False
assert report["validation_arrays_read"] is False
assert report["test_access"] is False
profile = report["profile"]
assert profile["seed"] == int(sys.argv[6])
assert math.isclose(profile["learning_rate"], float(sys.argv[7]))
assert profile["steps"] == int(sys.argv[8])
assert profile["registered_grid_point"] is True
projection = report["registered_grid_projection"]
assert projection["protocol_cap_or_selection_metric"] is False
assert projection["total_seconds"] > 0.0
assert projection["total_hours"] > 0.0
assert report["parameter_fairness"]["student_parameters"] > 0
print(
    "PROFILE_VALID architecture={} estimated_hours={:.3f} peak_mb={}".format(
        report["architecture"],
        projection["total_hours"],
        report["device"]["peak_allocated_mb"],
    )
)
PY
}

cpmt_run_profile() {
  local CPMT_ARCHITECTURE="$1"
  local CPMT_ARM_NAME="$2"
  local CPMT_ARM_DIR="$CPMT_PROFILE_ROOT/$CPMT_ARM_NAME"
  local CPMT_REPORT_PATH="$CPMT_ARM_DIR/runtime_profile.json"
  local CPMT_LOG_PATH="$CPMT_ARM_DIR/runtime_profile.log"

  if [[ -f "$CPMT_REPORT_PATH" ]]; then
    cpmt_validate_profile "$CPMT_REPORT_PATH" "$CPMT_ARCHITECTURE" || \
      cpmt_fail "existing_${CPMT_ARM_NAME}_profile_invalid"
    printf "PROFILE_REUSED architecture=%s\n" "$CPMT_ARCHITECTURE"
    return 0
  fi
  mkdir -p "$CPMT_ARM_DIR" || cpmt_fail "cannot_create_${CPMT_ARM_NAME}_directory"
  (
    cd "$CPMT_REPO_DIR" || exit 2
    python scripts/run_m1_train_inner_dev_budget.py \
      --train "$CPMT_TRAIN_ARRAYS" \
      --out-dir "$CPMT_ARM_DIR" \
      --architecture "$CPMT_ARCHITECTURE" \
      --device auto \
      --threads "$CPMT_THREADS" \
      --runtime-profile-only
  ) 2>&1 | tee -a "$CPMT_LOG_PATH"
  local CPMT_PROFILE_EXIT=${PIPESTATUS[0]}
  printf "PROFILE_EXIT architecture=%s exit=%s\n" \
    "$CPMT_ARCHITECTURE" "$CPMT_PROFILE_EXIT"
  [[ "$CPMT_PROFILE_EXIT" -eq 0 ]] || \
    cpmt_fail "${CPMT_ARM_NAME}_profile_failed"
  [[ -f "$CPMT_REPORT_PATH" ]] || \
    cpmt_fail "${CPMT_ARM_NAME}_profile_report_missing"
  cpmt_validate_profile "$CPMT_REPORT_PATH" "$CPMT_ARCHITECTURE" || \
    cpmt_fail "${CPMT_ARM_NAME}_profile_validation_failed"
}

cpmt_run_profile "cross_candidate_set_transformer_v1" "set_transformer"
cpmt_run_profile "shared_candidate_mlp_v1" "shared_mlp"

python - \
  "$CPMT_PROFILE_ROOT/set_transformer/runtime_profile.json" \
  "$CPMT_PROFILE_ROOT/shared_mlp/runtime_profile.json" <<'PY' || \
  cpmt_fail "combined_projection_failed"
import json
import sys
from pathlib import Path

reports = [json.loads(Path(path).read_text(encoding="utf-8")) for path in sys.argv[1:]]
hours = {
    report["architecture"]: report["registered_grid_projection"]["total_hours"]
    for report in reports
}
for architecture, value in hours.items():
    print("RUNTIME_PROFILE_PROJECTED_HOURS architecture={} hours={:.3f}".format(
        architecture, value,
    ))
print("RUNTIME_PROFILE_PROJECTED_HOURS_BOTH={:.3f}".format(sum(hours.values())))
print("RUNTIME_PROFILE_PROJECTION_IS_PLANNING_ONLY=true")
PY

printf "SET_TRANSFORMER_REPORT=%s\n" \
  "$CPMT_PROFILE_ROOT/set_transformer/runtime_profile.json"
printf "SHARED_MLP_REPORT=%s\n" \
  "$CPMT_PROFILE_ROOT/shared_mlp/runtime_profile.json"
printf "SERVER_STEP_OK id=%s\n" "$CPMT_SERVER_STEP_ID"
printf "NEXT=review_projection_then_schedule_registered_budget_grid\n"
