#!/usr/bin/env bash
# Single mutable server handoff entrypoint for CPMT.
# Current stage: export the completed v5 10-group data-scale anchor only.

set -uo pipefail

CPMT_SERVER_STEP_ID="m1_v2_v5_s2_g10_anchor_export"
CPMT_ANCHOR_TRAIN_COMMIT="d8665d8068a55847bc6a5d38f8e52f2e34c2eca4"
CPMT_EXPECTED_PROTOCOL="34f76fcbef7009ece83368109cfbe4b3c7fd5e0f7e4e61c52134170fa161787a"
CPMT_EXPECTED_DATASET="m1-paired-latent-worlds-v5-shared-static-preflight"
CPMT_REGISTERED_SEEDS=(7 19 31 43 59)
CPMT_SCORER_STEPS=1000
CPMT_TRAIN_GROUPS=10

CPMT_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
CPMT_REPO_DIR="$(git -C "$CPMT_SCRIPT_DIR" rev-parse --show-toplevel)" || exit 2
CPMT_CURRENT_COMMIT="$(git -C "$CPMT_REPO_DIR" rev-parse HEAD)" || exit 2
CPMT_GIT_STATUS="$(git -C "$CPMT_REPO_DIR" status --porcelain)" || exit 2
CPMT_BASE_DIR="$CPMT_REPO_DIR/outputs/m1-v2-v5-shared-static-preflight-g40-72afa7d"
CPMT_ANCHOR_DIR="$CPMT_BASE_DIR/s2-g10-s1000-seeds-7-19-31-43-59"
CPMT_ANCHOR_REPORT="$CPMT_ANCHOR_DIR/af_report.json"
CPMT_RESULTS_DIR="$CPMT_REPO_DIR/results"
CPMT_RESULT_NAME="m1-v2-s2-g10-s1000-v5-72afa7d"
CPMT_RESULT_PATH="$CPMT_RESULTS_DIR/$CPMT_RESULT_NAME.json"

cpmt_fail() {
  local CPMT_FAILURE_MESSAGE="$1"
  printf "SERVER_STEP_FAILED stage=%s reason=%s\n" \
    "$CPMT_SERVER_STEP_ID" "$CPMT_FAILURE_MESSAGE" >&2
  exit 1
}

printf "SERVER_STEP_BEGIN stage=%s\n" "$CPMT_SERVER_STEP_ID"
printf "repo=%s\ncurrent_commit=%s\n" "$CPMT_REPO_DIR" "$CPMT_CURRENT_COMMIT"
printf "anchor_report=%s\nresult_target=%s\n" \
  "$CPMT_ANCHOR_REPORT" "$CPMT_RESULT_PATH"

[[ -z "$CPMT_GIT_STATUS" ]] || cpmt_fail "working_tree_not_clean"
[[ "$CPMT_CURRENT_COMMIT" != "$CPMT_ANCHOR_TRAIN_COMMIT" ]] || \
  cpmt_fail "export_script_update_commit_not_present"
command -v python >/dev/null 2>&1 || cpmt_fail "python_not_found"
[[ -f "$CPMT_ANCHOR_REPORT" ]] || cpmt_fail "anchor_report_missing"

if ! python - \
  "$CPMT_ANCHOR_REPORT" "$CPMT_ANCHOR_TRAIN_COMMIT" \
  "$CPMT_EXPECTED_PROTOCOL" "$CPMT_EXPECTED_DATASET" <<'PY'
import json
import math
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
expected_commit = sys.argv[2]
expected_protocol = sys.argv[3]
expected_dataset = sys.argv[4]
registered_seeds = [7, 19, 31, 43, 59]

report = json.loads(report_path.read_text(encoding="utf-8"))
assert report["schema_version"] == "cpmt-m1-scorer-diagnostic-v3"
assert report["formal_run"] is False and report["test_generated"] is False
assert report["causal_complete"] is False
assert report["protocol_sha256"] == expected_protocol
assert report["dataset_version"] == expected_dataset
assert report["training_provenance"]["git_commit"] == expected_commit
assert report["training_provenance"]["git_dirty"] is False
assert report["seeds"] == registered_seeds
assert report["input_arrays"]["train"]["available_paired_groups"] == 40
assert report["input_arrays"]["train"]["selected_paired_groups"] == 10
assert report["partition"]["fitting_group_ids"] == [0, 2, 3, 4, 5, 6, 7, 8, 9]
assert report["partition"]["inner_dev_group_ids"] == [1]
assert report["partition"]["validation_arrays_read"] is False
assert report["partition"]["validation_trial_consumed"] is False
assert report["training_budget"]["outcome_scorer_steps"] == 1000
assert report["training_budget"]["total_train_groups"] == 10

audit = report["static_preflight_diagnostics"]["all_selected_train_online"]
assert audit["rows"] == 400
assert audit["legal_false_rejections"] == 0
assert audit["remaining_executor_illegal_candidates"] == 0

values = {}
for run in report["outcome_scorer_diagnostics"]:
    value = float(run["inner_dev_online_by_group"]["1"]["teacher_accuracy"])
    assert math.isfinite(value)
    values[run["seed"]] = value
assert sorted(values) == registered_seeds
assert values == {
    7: 0.925000011920929,
    19: 0.925000011920929,
    31: 0.875,
    43: 0.875,
    59: 0.925000011920929,
}
print("ANCHOR_EXPORT_INPUT_OK group_1_by_seed={}".format(values))
PY
then
  cpmt_fail "anchor_report_validation_failed"
fi

if [[ -e "$CPMT_RESULT_PATH" ]]; then
  printf "RESULT_EXISTS action=validate_without_overwrite\n"
else
  cd "$CPMT_REPO_DIR" || cpmt_fail "cannot_enter_repository"
  python scripts/export_run_report.py \
    --out-dir "$CPMT_ANCHOR_DIR" \
    --name "$CPMT_RESULT_NAME" \
    --results-dir "$CPMT_RESULTS_DIR" \
    --note "v5 S2 10-group 1000-step five-seed data-scale anchor; train/inner-dev only; S3 screen did not trigger" || \
    cpmt_fail "result_export_failed"
fi

if ! python - \
  "$CPMT_RESULT_PATH" "$CPMT_ANCHOR_TRAIN_COMMIT" \
  "$CPMT_EXPECTED_PROTOCOL" "$CPMT_EXPECTED_DATASET" <<'PY'
import json
import sys
from pathlib import Path

result_path = Path(sys.argv[1])
expected_commit = sys.argv[2]
expected_protocol = sys.argv[3]
expected_dataset = sys.argv[4]
result = json.loads(result_path.read_text(encoding="utf-8"))
report = result["af_report"]

assert result["schema_version"] == "cpmt-exported-run-report-v2"
assert result["formal_run"] is False and result["test_generated"] is False
assert result["causal_per_seed"] == {}
assert "S3 screen did not trigger" in result["note"]
assert report["protocol_sha256"] == expected_protocol
assert report["dataset_version"] == expected_dataset
assert report["training_provenance"]["git_commit"] == expected_commit
assert report["training_provenance"]["git_dirty"] is False
assert report["partition"]["selected_train_groups"] == 10
assert report["training_budget"]["outcome_scorer_steps"] == 1000
assert report["seeds"] == [7, 19, 31, 43, 59]
assert result["pipeline_provenance"]["export"]["git_dirty"] is False
print("RESULT_VALIDATED bytes={}".format(result_path.stat().st_size))
PY
then
  cpmt_fail "exported_result_validation_failed"
fi

printf "RESULT_READY path=%s\n" "$CPMT_RESULT_PATH"
printf "RESULTS_WORKTREE_STATUS_AFTER_EXPORT\n"
git -C "$CPMT_REPO_DIR" status --short -- "$CPMT_RESULT_PATH" || \
  cpmt_fail "cannot_read_result_status"
printf "SERVER_STEP_OK stage=%s\n" "$CPMT_SERVER_STEP_ID"
printf "NEXT=commit_only_the_result_file_after_review\n"
