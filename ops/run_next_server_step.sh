#!/usr/bin/env bash
# Single mutable server handoff entrypoint for CPMT.
# Current stage: v5 10-group, 1000-step, five-seed data-scale anchor.

set -uo pipefail

CPMT_SERVER_STEP_ID="m1_v2_v5_s2_g10_s1000_five_seed_anchor"
CPMT_PREVIOUS_SCRIPT_COMMIT="d528ae0"
CPMT_EXPECTED_S2_TRAIN_COMMIT="d35434b410ebe473ae6400dedf9b6869c30b1cda"
CPMT_EXPECTED_PROTOCOL="34f76fcbef7009ece83368109cfbe4b3c7fd5e0f7e4e61c52134170fa161787a"
CPMT_EXPECTED_DATASET="m1-paired-latent-worlds-v5-shared-static-preflight"
CPMT_REGISTERED_SEEDS=(7 19 31 43 59)
CPMT_SCORER_STEPS=1000
CPMT_TRAIN_GROUPS=10
CPMT_THREADS=16

CPMT_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
CPMT_REPO_DIR="$(git -C "$CPMT_SCRIPT_DIR" rev-parse --show-toplevel)" || exit 2
CPMT_CURRENT_COMMIT="$(git -C "$CPMT_REPO_DIR" rev-parse HEAD)" || exit 2
CPMT_GIT_STATUS="$(git -C "$CPMT_REPO_DIR" status --porcelain)" || exit 2

CPMT_BASE_DIR="$CPMT_REPO_DIR/outputs/m1-v2-v5-shared-static-preflight-g40-72afa7d"
CPMT_ARRAYS_PATH="$CPMT_BASE_DIR/train.npz"
CPMT_MANIFEST_PATH="$CPMT_BASE_DIR/train.manifest.json"
CPMT_REFERENCE_RESULT="$CPMT_REPO_DIR/results/m1-v2-s2-g40-s1000-v5-72afa7d.json"
CPMT_ANCHOR_DIR="$CPMT_BASE_DIR/s2-g10-s1000-seeds-7-19-31-43-59"
CPMT_ANCHOR_REPORT="$CPMT_ANCHOR_DIR/af_report.json"
CPMT_ANCHOR_LOG="$CPMT_ANCHOR_DIR/run.log"

cpmt_fail() {
  local CPMT_FAILURE_MESSAGE="$1"
  printf "SERVER_STEP_FAILED stage=%s reason=%s\n" \
    "$CPMT_SERVER_STEP_ID" "$CPMT_FAILURE_MESSAGE" >&2
  exit 1
}

printf "SERVER_STEP_BEGIN stage=%s\n" "$CPMT_SERVER_STEP_ID"
printf "repo=%s\ncurrent_commit=%s\n" "$CPMT_REPO_DIR" "$CPMT_CURRENT_COMMIT"
printf "train_groups=%s scorer_steps=%s seeds=%s threads=%s\n" \
  "$CPMT_TRAIN_GROUPS" "$CPMT_SCORER_STEPS" \
  "${CPMT_REGISTERED_SEEDS[*]}" "$CPMT_THREADS"

[[ -z "$CPMT_GIT_STATUS" ]] || cpmt_fail "working_tree_not_clean"
[[ "$CPMT_CURRENT_COMMIT" != "$CPMT_PREVIOUS_SCRIPT_COMMIT" ]] || \
  cpmt_fail "script_update_commit_not_present"
command -v python >/dev/null 2>&1 || cpmt_fail "python_not_found"
[[ -f "$CPMT_ARRAYS_PATH" ]] || cpmt_fail "train_arrays_missing"
[[ -f "$CPMT_MANIFEST_PATH" ]] || cpmt_fail "train_manifest_missing"
[[ -f "$CPMT_REFERENCE_RESULT" ]] || cpmt_fail "exported_s2_reference_missing"

if ! python - \
  "$CPMT_REPO_DIR" "$CPMT_ARRAYS_PATH" "$CPMT_MANIFEST_PATH" \
  "$CPMT_REFERENCE_RESULT" "$CPMT_EXPECTED_S2_TRAIN_COMMIT" \
  "$CPMT_EXPECTED_PROTOCOL" "$CPMT_EXPECTED_DATASET" <<'PY'
import json
import sys
from pathlib import Path
import numpy as np

repo = Path(sys.argv[1])
arrays_path = Path(sys.argv[2])
manifest_path = Path(sys.argv[3])
reference_path = Path(sys.argv[4])
expected_s2_commit = sys.argv[5]
expected_protocol = sys.argv[6]
expected_dataset = sys.argv[7]
sys.path.insert(0, str(repo / "src"))
from cpmt.run_provenance import arrays_sha256

with np.load(arrays_path, allow_pickle=True) as archive:
    arrays = {key: archive[key] for key in archive.files}
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
reference = json.loads(reference_path.read_text(encoding="utf-8"))["af_report"]
assert arrays_sha256(arrays) == manifest["arrays_digest"]
assert manifest["split"] == "train" and manifest["paired_groups"] == 40
assert manifest["protocol_sha256"] == expected_protocol
assert manifest["dataset_version"] == expected_dataset
assert manifest["formal_run"] is False and manifest["test_generated"] is False
assert reference["protocol_sha256"] == expected_protocol
assert reference["dataset_version"] == expected_dataset
assert reference["training_provenance"]["git_commit"] == expected_s2_commit
assert reference["training_provenance"]["git_dirty"] is False
assert reference["input_arrays"]["train"]["arrays_digest"] == manifest["arrays_digest"]
assert reference["partition"]["selected_train_groups"] == 40
assert reference["partition"]["inner_dev_group_ids"] == [1, 10, 15, 16, 18, 30, 37, 39]
assert reference["seeds"] == [7, 19, 31, 43, 59]
assert reference["training_budget"]["outcome_scorer_steps"] == 1000
assert reference["partition"]["validation_arrays_read"] is False
assert reference["partition"]["validation_trial_consumed"] is False
print("ANCHOR_INPUT_OK arrays_digest={}".format(manifest["arrays_digest"]))
PY
then
  cpmt_fail "anchor_input_validation_failed"
fi

if [[ -f "$CPMT_ANCHOR_REPORT" ]]; then
  printf "ANCHOR_REPORT_EXISTS action=validate_without_rerun\n"
elif [[ -e "$CPMT_ANCHOR_DIR" ]]; then
  printf "INCOMPLETE_ANCHOR_CONTENTS\n" >&2
  find "$CPMT_ANCHOR_DIR" -maxdepth 2 -type f -print | sort >&2
  cpmt_fail "incomplete_anchor_refusing_overwrite"
else
  mkdir -p "$CPMT_ANCHOR_DIR" || cpmt_fail "cannot_create_anchor_dir"
  cd "$CPMT_REPO_DIR" || cpmt_fail "cannot_enter_repository"
  PYTHONUNBUFFERED=1 python scripts/run_m1_scorer_diagnostics.py \
    --config configs/m1_hard_condition.json \
    --train "$CPMT_ARRAYS_PATH" \
    --out-dir "$CPMT_ANCHOR_DIR" \
    --paired-groups "$CPMT_TRAIN_GROUPS" \
    --scorer-steps "$CPMT_SCORER_STEPS" \
    --seeds "${CPMT_REGISTERED_SEEDS[@]}" \
    --threads "$CPMT_THREADS" \
    2>&1 | tee "$CPMT_ANCHOR_LOG"
  CPMT_ANCHOR_EXIT="${PIPESTATUS[0]}"
  printf "ANCHOR_TRAIN_EXIT=%s\n" "$CPMT_ANCHOR_EXIT"
  [[ "$CPMT_ANCHOR_EXIT" -eq 0 ]] || cpmt_fail "anchor_training_failed"
  [[ -f "$CPMT_ANCHOR_REPORT" ]] || cpmt_fail "anchor_report_missing"
fi

if ! python - \
  "$CPMT_ANCHOR_REPORT" "$CPMT_REFERENCE_RESULT" \
  "$CPMT_CURRENT_COMMIT" "$CPMT_EXPECTED_PROTOCOL" \
  "$CPMT_EXPECTED_DATASET" <<'PY'
import json
import math
import sys
from pathlib import Path

anchor_path = Path(sys.argv[1])
reference_path = Path(sys.argv[2])
expected_anchor_commit = sys.argv[3]
expected_protocol = sys.argv[4]
expected_dataset = sys.argv[5]
registered_seeds = [7, 19, 31, 43, 59]

anchor = json.loads(anchor_path.read_text(encoding="utf-8"))
reference = json.loads(reference_path.read_text(encoding="utf-8"))["af_report"]
assert anchor["schema_version"] == "cpmt-m1-scorer-diagnostic-v3"
assert anchor["formal_run"] is False and anchor["test_generated"] is False
assert anchor["causal_complete"] is False
assert anchor["protocol_sha256"] == expected_protocol
assert anchor["dataset_version"] == expected_dataset
assert anchor["training_provenance"]["git_commit"] == expected_anchor_commit
assert anchor["training_provenance"]["git_dirty"] is False
assert anchor["seeds"] == registered_seeds
assert anchor["input_arrays"]["train"]["available_paired_groups"] == 40
assert anchor["input_arrays"]["train"]["selected_paired_groups"] == 10

partition = anchor["partition"]
assert partition["fitting_group_ids"] == [0, 2, 3, 4, 5, 6, 7, 8, 9]
assert partition["inner_dev_group_ids"] == [1]
assert partition["fitting_learning_rows"] == 378
assert partition["inner_dev_learning_rows"] == 42
assert partition["inner_dev_online_rows"] == 40
assert partition["validation_arrays_read"] is False
assert partition["validation_trial_consumed"] is False
assert anchor["training_budget"]["outcome_scorer_steps"] == 1000
assert anchor["training_budget"]["total_train_groups"] == 10

audit = anchor["static_preflight_diagnostics"]["all_selected_train_online"]
assert audit["rows"] == 400
assert audit["legal_false_rejections"] == 0
assert audit["remaining_executor_illegal_candidates"] == 0
assert audit["reference_static_preflight_pass_rate"] == 1.0

anchor_runs = anchor["outcome_scorer_diagnostics"]
reference_runs = reference["outcome_scorer_diagnostics"]
assert [run["seed"] for run in anchor_runs] == registered_seeds
assert [run["seed"] for run in reference_runs] == registered_seeds

anchor_by_seed = {}
reference_by_seed = {}
for run in anchor_runs:
    value = run["inner_dev_online_by_group"]["1"]["teacher_accuracy"]
    assert math.isfinite(value)
    anchor_by_seed[run["seed"]] = float(value)
for run in reference_runs:
    value = run["inner_dev_online_by_group"]["1"]["teacher_accuracy"]
    assert math.isfinite(value)
    reference_by_seed[run["seed"]] = float(value)

deltas = {seed: reference_by_seed[seed] - anchor_by_seed[seed] for seed in registered_seeds}
mean_delta = sum(deltas.values()) / len(deltas)
positive_seed_count = sum(value > 0.0 for value in deltas.values())
s3_directional_signal = positive_seed_count >= 4 and mean_delta >= 0.025

print("ANCHOR_REPORT={}".format(anchor_path))
print("ANCHOR_GROUP_1_BY_SEED={}".format(anchor_by_seed))
print("REFERENCE_40_GROUP_1_BY_SEED={}".format(reference_by_seed))
print("DATA_SCALE_DELTAS_40_MINUS_10={}".format(deltas))
print("DATA_SCALE_SCREEN mean_delta={:.6f} positive_seeds={}/5 threshold=0.025000 s3_directional_signal={}".format(mean_delta, positive_seed_count, s3_directional_signal))
print("DATA_SCALE_LIMIT one_independent_group=true ci_not_reportable=true budget_selection_unchanged=1000")
PY
then
  cpmt_fail "anchor_report_validation_failed"
fi

printf "SERVER_STEP_OK stage=%s\n" "$CPMT_SERVER_STEP_ID"
