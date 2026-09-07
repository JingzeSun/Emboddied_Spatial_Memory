#!/usr/bin/env bash
# Single mutable server handoff entrypoint for CPMT.
# Current stage: export and validate the completed v5 S2 scorer reports.

set -uo pipefail

CPMT_SERVER_STEP_ID="m1_v2_v5_s2_export_reports"
CPMT_EXPECTED_TRAIN_COMMIT="d35434b410ebe473ae6400dedf9b6869c30b1cda"
CPMT_EXPECTED_GENERATION_COMMIT="72afa7da33e0465e6e45d57e2a9675248ac65447"
CPMT_EXPECTED_PROTOCOL="34f76fcbef7009ece83368109cfbe4b3c7fd5e0f7e4e61c52134170fa161787a"
CPMT_EXPECTED_DATASET="m1-paired-latent-worlds-v5-shared-static-preflight"

CPMT_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" \
  || exit 2
CPMT_REPO_DIR="$(git -C "$CPMT_SCRIPT_DIR" rev-parse --show-toplevel)" \
  || exit 2
CPMT_CURRENT_COMMIT="$(git -C "$CPMT_REPO_DIR" rev-parse HEAD)" \
  || exit 2
CPMT_GIT_STATUS="$(git -C "$CPMT_REPO_DIR" status --porcelain)" \
  || exit 2

CPMT_BASE_DIR="$CPMT_REPO_DIR/outputs/m1-v2-v5-shared-static-preflight-g40-72afa7d"
CPMT_S300_DIR="$CPMT_BASE_DIR/s2-g40-s300-seeds-7-19-31-43-59"
CPMT_S1000_DIR="$CPMT_BASE_DIR/s2-g40-s1000-seeds-7-19-31-43-59"
CPMT_ARRAYS_PATH="$CPMT_BASE_DIR/train.npz"
CPMT_MANIFEST_PATH="$CPMT_BASE_DIR/train.manifest.json"
CPMT_S1_REPORT_PATH="$CPMT_BASE_DIR/s1-g10-s60-seed7/af_report.json"
CPMT_TEMP_RESULTS_DIR="$CPMT_BASE_DIR/export_tmp_s2"
CPMT_RESULTS_DIR="$CPMT_REPO_DIR/results"
CPMT_NAME_300="m1-v2-s2-g40-s300-v5-72afa7d"
CPMT_NAME_1000="m1-v2-s2-g40-s1000-v5-72afa7d"
CPMT_TARGET_300="$CPMT_RESULTS_DIR/$CPMT_NAME_300.json"
CPMT_TARGET_1000="$CPMT_RESULTS_DIR/$CPMT_NAME_1000.json"

cpmt_fail() {
  local CPMT_FAILURE_MESSAGE="$1"
  printf "SERVER_STEP_FAILED stage=%s reason=%s\n" \
    "$CPMT_SERVER_STEP_ID" "$CPMT_FAILURE_MESSAGE" >&2
  exit 1
}

printf "SERVER_STEP_BEGIN stage=%s\n" "$CPMT_SERVER_STEP_ID"
printf "repo=%s\ncurrent_commit=%s\n" "$CPMT_REPO_DIR" "$CPMT_CURRENT_COMMIT"

[[ -z "$CPMT_GIT_STATUS" ]] || cpmt_fail "working_tree_not_clean"
[[ "$CPMT_CURRENT_COMMIT" != "$CPMT_EXPECTED_TRAIN_COMMIT" ]] || \
  cpmt_fail "script_update_commit_not_present"
command -v python >/dev/null 2>&1 || cpmt_fail "python_not_found"
[[ -f "$CPMT_ARRAYS_PATH" ]] || cpmt_fail "train_arrays_missing"
[[ -f "$CPMT_MANIFEST_PATH" ]] || cpmt_fail "train_manifest_missing"
[[ -f "$CPMT_S1_REPORT_PATH" ]] || cpmt_fail "s1_report_missing"
[[ -f "$CPMT_S300_DIR/af_report.json" ]] || cpmt_fail "s300_report_missing"
[[ -f "$CPMT_S1000_DIR/af_report.json" ]] || cpmt_fail "s1000_report_missing"

if ! python - \
  "$CPMT_REPO_DIR" \
  "$CPMT_ARRAYS_PATH" \
  "$CPMT_MANIFEST_PATH" \
  "$CPMT_S1_REPORT_PATH" \
  "$CPMT_S300_DIR/af_report.json" \
  "$CPMT_S1000_DIR/af_report.json" \
  "$CPMT_EXPECTED_TRAIN_COMMIT" \
  "$CPMT_EXPECTED_GENERATION_COMMIT" \
  "$CPMT_EXPECTED_PROTOCOL" \
  "$CPMT_EXPECTED_DATASET" <<'PY'
import json
import math
import sys
from pathlib import Path

import numpy as np

repo = Path(sys.argv[1])
arrays_path = Path(sys.argv[2])
manifest_path = Path(sys.argv[3])
s1_path = Path(sys.argv[4])
s300_path = Path(sys.argv[5])
s1000_path = Path(sys.argv[6])
expected_train_commit = sys.argv[7]
expected_generation_commit = sys.argv[8]
expected_protocol = sys.argv[9]
expected_dataset = sys.argv[10]

sys.path.insert(0, str(repo / "src"))
from cpmt.run_provenance import arrays_sha256

with np.load(arrays_path, allow_pickle=True) as archive:
    arrays = {key: archive[key] for key in archive.files}
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
s1 = json.loads(s1_path.read_text(encoding="utf-8"))
reports = {
    300: json.loads(s300_path.read_text(encoding="utf-8")),
    1000: json.loads(s1000_path.read_text(encoding="utf-8")),
}

digest = arrays_sha256(arrays)
assert digest == manifest["arrays_digest"]
assert manifest["protocol_sha256"] == expected_protocol
assert manifest["dataset_version"] == expected_dataset
assert manifest["generation_provenance"]["git_commit"] == expected_generation_commit
assert manifest["generation_provenance"]["git_dirty"] is False
assert manifest["formal_run"] is False
assert manifest["test_generated"] is False

assert s1["protocol_sha256"] == expected_protocol
assert s1["dataset_version"] == expected_dataset
assert s1["training_provenance"]["git_commit"] == expected_generation_commit
assert s1["training_provenance"]["git_dirty"] is False
assert s1["partition"]["validation_arrays_read"] is False
assert s1["partition"]["validation_trial_consumed"] is False

registered_seeds = [7, 19, 31, 43, 59]
for steps, report in reports.items():
    assert report["schema_version"] == "cpmt-m1-scorer-diagnostic-v3"
    assert report["runner"] == "run_m1_scorer_diagnostics_v3"
    assert report["protocol_sha256"] == expected_protocol
    assert report["dataset_version"] == expected_dataset
    assert report["formal_run"] is False
    assert report["test_generated"] is False
    assert report["causal_complete"] is False
    assert report["seeds"] == registered_seeds
    assert report["input_arrays"]["train"]["arrays_digest"] == digest
    assert report["input_arrays"]["train"]["available_paired_groups"] == 40
    assert report["input_arrays"]["train"]["selected_paired_groups"] == 40
    provenance = report["training_provenance"]
    assert provenance["git_commit"] == expected_train_commit
    assert provenance["git_dirty"] is False
    partition = report["partition"]
    assert partition["available_train_groups"] == 40
    assert partition["selected_train_groups"] == 40
    assert len(partition["fitting_group_ids"]) == 32
    assert len(partition["inner_dev_group_ids"]) == 8
    assert partition["fitting_learning_rows"] == 1344
    assert partition["inner_dev_learning_rows"] == 336
    assert partition["inner_dev_online_rows"] == 320
    assert partition["validation_arrays_read"] is False
    assert partition["validation_report_partition_accessed"] is False
    assert partition["validation_trial_consumed"] is False
    assert report["training_budget"]["online_students_trained"] is False
    assert report["training_budget"]["outcome_scorer_steps"] == steps
    assert report["training_budget"]["total_train_groups"] == 40
    audit = report["static_preflight_diagnostics"][
        "all_selected_train_online"
    ]
    assert audit["rows"] == 1600
    assert audit["legal_false_rejections"] == 0
    assert audit["remaining_executor_illegal_candidates"] == 0
    assert audit["reference_static_preflight_pass_rate"] == 1.0
    assert [run["seed"] for run in report[
        "outcome_scorer_diagnostics"
    ]] == registered_seeds
    for run in report["outcome_scorer_diagnostics"]:
        inner = run["inner_dev_online_chain"]
        for value in (
            inner["masked_bce"],
            inner["ranking_relevant_bce"],
            inner["target_discriminative_bce"],
            inner["teacher_accuracy"],
            inner["reference_probability_margin_mean"],
            inner["reference_positive_margin_rate"],
        ):
            assert math.isfinite(value)

print("S2_EXPORT_INPUT_OK arrays_digest={}".format(digest))
PY
then
  cpmt_fail "s2_input_validation_failed"
fi

mkdir -p "$CPMT_TEMP_RESULTS_DIR" || cpmt_fail "cannot_create_export_staging"
mkdir -p "$CPMT_RESULTS_DIR" || cpmt_fail "cannot_create_results_dir"

cpmt_export_one() {
  local CPMT_EXPORT_RUN_DIR="$1"
  local CPMT_EXPORT_NAME="$2"
  local CPMT_EXPORT_STAGE="$CPMT_TEMP_RESULTS_DIR/$CPMT_EXPORT_NAME.json"
  local CPMT_EXPORT_TARGET="$CPMT_RESULTS_DIR/$CPMT_EXPORT_NAME.json"
  local CPMT_EXPORT_EXIT

  if [[ -f "$CPMT_EXPORT_TARGET" ]]; then
    printf "RESULT_EXPORT_EXISTS name=%s action=validate_without_overwrite\n" \
      "$CPMT_EXPORT_NAME"
    return 0
  fi

  if [[ ! -f "$CPMT_EXPORT_STAGE" ]]; then
    cd "$CPMT_REPO_DIR" || cpmt_fail "cannot_enter_repository"
    python scripts/export_run_report.py \
      --out-dir "$CPMT_EXPORT_RUN_DIR" \
      --name "$CPMT_EXPORT_NAME" \
      --results-dir "$CPMT_TEMP_RESULTS_DIR" \
      --note "v5 S2 scorer diagnostic; train/inner-dev only; no validation or test" \
      2>&1 | tee "$CPMT_TEMP_RESULTS_DIR/$CPMT_EXPORT_NAME.log"
    CPMT_EXPORT_EXIT="${PIPESTATUS[0]}"
    printf "RESULT_EXPORT_EXIT name=%s exit=%s\n" \
      "$CPMT_EXPORT_NAME" "$CPMT_EXPORT_EXIT"
    [[ "$CPMT_EXPORT_EXIT" -eq 0 ]] || \
      cpmt_fail "result_export_failed_${CPMT_EXPORT_NAME}"
  else
    printf "RESULT_EXPORT_STAGE_EXISTS name=%s action=validate_and_reuse\n" \
      "$CPMT_EXPORT_NAME"
  fi
  [[ -f "$CPMT_EXPORT_STAGE" ]] || \
    cpmt_fail "result_export_stage_missing_${CPMT_EXPORT_NAME}"
}

# Both exporter calls happen before copying into tracked results/, so the
# exporter provenance is captured from a clean tree. The copy is the final
# handoff action and is intentionally followed by a separate Git commit block.
cpmt_export_one "$CPMT_S300_DIR" "$CPMT_NAME_300"
cpmt_export_one "$CPMT_S1000_DIR" "$CPMT_NAME_1000"

if [[ ! -f "$CPMT_TARGET_300" ]]; then
  cp -- "$CPMT_TEMP_RESULTS_DIR/$CPMT_NAME_300.json" "$CPMT_TARGET_300" \
    || cpmt_fail "cannot_copy_s300_result"
fi
if [[ ! -f "$CPMT_TARGET_1000" ]]; then
  cp -- "$CPMT_TEMP_RESULTS_DIR/$CPMT_NAME_1000.json" "$CPMT_TARGET_1000" \
    || cpmt_fail "cannot_copy_s1000_result"
fi

if ! python - \
  "$CPMT_TARGET_300" \
  "$CPMT_TARGET_1000" \
  "$CPMT_EXPECTED_TRAIN_COMMIT" \
  "$CPMT_EXPECTED_PROTOCOL" \
  "$CPMT_EXPECTED_DATASET" <<'PY'
import json
import sys
from pathlib import Path

report_paths = [Path(sys.argv[1]), Path(sys.argv[2])]
expected_train_commit = sys.argv[3]
expected_protocol = sys.argv[4]
expected_dataset = sys.argv[5]

for path in report_paths:
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["formal_run"] is False
    assert report["test_generated"] is False
    assert report["af_report"]["protocol_sha256"] == expected_protocol
    assert report["af_report"]["dataset_version"] == expected_dataset
    assert report["af_report"]["training_provenance"]["git_commit"] == (
        expected_train_commit
    )
    assert report["af_report"]["training_provenance"]["git_dirty"] is False
    assert report["pipeline_provenance"]["export"]["git_dirty"] is False
    print("RESULT_READY {} bytes={}".format(path, path.stat().st_size))
PY
then
  cpmt_fail "exported_result_validation_failed"
fi

CPMT_POST_EXPORT_STATUS="$(git -C "$CPMT_REPO_DIR" status --porcelain)"
printf "RESULTS_WORKTREE_STATUS_AFTER_EXPORT\n%s\n" "$CPMT_POST_EXPORT_STATUS"
printf "SERVER_STEP_OK stage=%s\n" "$CPMT_SERVER_STEP_ID"
printf "NEXT: git add results && git commit && git push\n"
