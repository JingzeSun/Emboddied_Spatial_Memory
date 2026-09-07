#!/usr/bin/env bash
# Single mutable server handoff entrypoint for CPMT.
# Current stage: M1-v2 v5 scorer budget comparison on train/inner-dev only.

set -uo pipefail

CPMT_SERVER_STEP_ID="m1_v2_v5_s2_g40_s300_s1000_five_seeds"
CPMT_EXPECTED_INPUT_COMMIT="72afa7da33e0465e6e45d57e2a9675248ac65447"
CPMT_EXPECTED_PROTOCOL="34f76fcbef7009ece83368109cfbe4b3c7fd5e0f7e4e61c52134170fa161787a"
CPMT_EXPECTED_DATASET="m1-paired-latent-worlds-v5-shared-static-preflight"
CPMT_REGISTERED_SEEDS=(7 19 31 43 59)
CPMT_THREADS=16

cpmt_fail() {
  local CPMT_FAILURE_MESSAGE="$1"
  printf "SERVER_STEP_FAILED stage=%s reason=%s\n" \
    "$CPMT_SERVER_STEP_ID" "$CPMT_FAILURE_MESSAGE" >&2
  exit 1
}

CPMT_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" \
  || cpmt_fail "script_directory_unavailable"
CPMT_REPO_DIR="$(git -C "$CPMT_SCRIPT_DIR" rev-parse --show-toplevel)" \
  || cpmt_fail "repository_not_found"
CPMT_CURRENT_COMMIT="$(git -C "$CPMT_REPO_DIR" rev-parse HEAD)" \
  || cpmt_fail "head_unavailable"
CPMT_GIT_STATUS="$(git -C "$CPMT_REPO_DIR" status --porcelain)" \
  || cpmt_fail "git_status_failed"

CPMT_BASE_DIR="$CPMT_REPO_DIR/outputs/m1-v2-v5-shared-static-preflight-g40-72afa7d"
CPMT_ARRAYS_PATH="$CPMT_BASE_DIR/train.npz"
CPMT_MANIFEST_PATH="$CPMT_BASE_DIR/train.manifest.json"
CPMT_S1_REPORT_PATH="$CPMT_BASE_DIR/s1-g10-s60-seed7/af_report.json"
CPMT_S300_DIR="$CPMT_BASE_DIR/s2-g40-s300-seeds-7-19-31-43-59"
CPMT_S1000_DIR="$CPMT_BASE_DIR/s2-g40-s1000-seeds-7-19-31-43-59"
CPMT_S300_REPORT="$CPMT_S300_DIR/af_report.json"
CPMT_S1000_REPORT="$CPMT_S1000_DIR/af_report.json"

printf "SERVER_STEP_BEGIN stage=%s\n" "$CPMT_SERVER_STEP_ID"
printf "repo=%s\ncurrent_commit=%s\n" "$CPMT_REPO_DIR" "$CPMT_CURRENT_COMMIT"
printf "scorer_steps=300,1000 seeds=%s threads=%s\n" \
  "${CPMT_REGISTERED_SEEDS[*]}" "$CPMT_THREADS"

[[ -z "$CPMT_GIT_STATUS" ]] || cpmt_fail "working_tree_not_clean"
command -v python >/dev/null 2>&1 || cpmt_fail "python_not_found"
[[ -f "$CPMT_ARRAYS_PATH" ]] || cpmt_fail "train_arrays_missing"
[[ -f "$CPMT_MANIFEST_PATH" ]] || cpmt_fail "train_manifest_missing"
[[ -f "$CPMT_S1_REPORT_PATH" ]] || cpmt_fail "s1_prerequisite_missing"

if ! python - \
  "$CPMT_REPO_DIR" \
  "$CPMT_ARRAYS_PATH" \
  "$CPMT_MANIFEST_PATH" \
  "$CPMT_S1_REPORT_PATH" \
  "$CPMT_EXPECTED_INPUT_COMMIT" \
  "$CPMT_EXPECTED_PROTOCOL" \
  "$CPMT_EXPECTED_DATASET" <<'PY'
import json
import sys
from pathlib import Path

import numpy as np

repo = Path(sys.argv[1])
arrays_path = Path(sys.argv[2])
manifest_path = Path(sys.argv[3])
s1_report_path = Path(sys.argv[4])
expected_input_commit = sys.argv[5]
expected_protocol = sys.argv[6]
expected_dataset = sys.argv[7]

sys.path.insert(0, str(repo / "src"))

from cpmt.run_provenance import arrays_sha256, source_tree_sha256

with np.load(arrays_path, allow_pickle=True) as archive:
    arrays = {key: archive[key] for key in archive.files}

manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
s1_report = json.loads(s1_report_path.read_text(encoding="utf-8"))
arrays_digest = arrays_sha256(arrays)

assert arrays_digest == manifest["arrays_digest"]
assert arrays_digest == s1_report["input_arrays"]["train"]["arrays_digest"]
assert manifest["protocol_sha256"] == expected_protocol
assert manifest["dataset_version"] == expected_dataset
assert manifest["split"] == "train"
assert manifest["paired_groups"] == 40
assert manifest["decisions"] == 1680
assert manifest["online_chain_decisions"] == 1600
assert manifest["recovery_training_examples"] == 80
assert manifest["formal_run"] is False
assert manifest["test_generated"] is False
assert manifest["generation_provenance"]["git_commit"] == expected_input_commit
assert manifest["generation_provenance"]["git_dirty"] is False

assert s1_report["protocol_sha256"] == expected_protocol
assert s1_report["dataset_version"] == expected_dataset
assert s1_report["training_provenance"]["git_commit"] == expected_input_commit
assert s1_report["training_provenance"]["git_dirty"] is False
assert s1_report["partition"]["selected_train_groups"] == 10
assert s1_report["training_budget"]["outcome_scorer_steps"] == 60
assert s1_report["seeds"] == [7]
assert s1_report["partition"]["validation_arrays_read"] is False
assert s1_report["partition"]["validation_trial_consumed"] is False
assert source_tree_sha256(repo) == (
    s1_report["training_provenance"]["source_tree_sha256"]
)

audit = s1_report["static_preflight_diagnostics"][
    "all_selected_train_online"
]
assert audit["legal_false_rejections"] == 0
assert audit["remaining_executor_illegal_candidates"] == 0
assert audit["reference_static_preflight_pass_rate"] == 1.0

print("S2_INPUT_OK arrays_digest={}".format(arrays_digest))
print(
    "S2_SCIENCE_SOURCE_OK sha256={}".format(
        source_tree_sha256(repo)
    )
)
PY
then
  cpmt_fail "s2_input_validation_failed"
fi

cpmt_run_scorer_point() {
  local CPMT_POINT_STEPS="$1"
  local CPMT_POINT_DIR="$2"
  local CPMT_POINT_REPORT="$CPMT_POINT_DIR/af_report.json"
  local CPMT_POINT_LOG="$CPMT_POINT_DIR/run.log"
  local CPMT_POINT_EXIT

  if [[ -f "$CPMT_POINT_REPORT" ]]; then
    printf "SCORER_POINT_EXISTS steps=%s action=validate_without_rerun\n" \
      "$CPMT_POINT_STEPS"
    return 0
  fi

  if [[ -e "$CPMT_POINT_DIR" ]]; then
    printf "INCOMPLETE_POINT_CONTENTS steps=%s\n" "$CPMT_POINT_STEPS" >&2
    find "$CPMT_POINT_DIR" -maxdepth 2 -type f -print | sort >&2
    cpmt_fail "incomplete_scorer_point_${CPMT_POINT_STEPS}_refusing_overwrite"
  fi

  mkdir -p "$CPMT_POINT_DIR" || cpmt_fail "cannot_create_scorer_point_dir"
  cd "$CPMT_REPO_DIR" || cpmt_fail "cannot_enter_repository"

  PYTHONUNBUFFERED=1 python scripts/run_m1_scorer_diagnostics.py \
    --config configs/m1_hard_condition.json \
    --train "$CPMT_ARRAYS_PATH" \
    --out-dir "$CPMT_POINT_DIR" \
    --paired-groups 40 \
    --scorer-steps "$CPMT_POINT_STEPS" \
    --seeds "${CPMT_REGISTERED_SEEDS[@]}" \
    --threads "$CPMT_THREADS" \
    2>&1 | tee "$CPMT_POINT_LOG"
  CPMT_POINT_EXIT="${PIPESTATUS[0]}"

  printf "SCORER_POINT_EXIT steps=%s exit=%s\n" \
    "$CPMT_POINT_STEPS" "$CPMT_POINT_EXIT"
  [[ "$CPMT_POINT_EXIT" -eq 0 ]] \
    || cpmt_fail "scorer_point_${CPMT_POINT_STEPS}_failed"
  [[ -f "$CPMT_POINT_REPORT" ]] \
    || cpmt_fail "scorer_point_${CPMT_POINT_STEPS}_report_missing"
}

cpmt_run_scorer_point 300 "$CPMT_S300_DIR"
cpmt_run_scorer_point 1000 "$CPMT_S1000_DIR"

if ! python - \
  "$CPMT_REPO_DIR" \
  "$CPMT_MANIFEST_PATH" \
  "$CPMT_S300_REPORT" \
  "$CPMT_S1000_REPORT" \
  "$CPMT_CURRENT_COMMIT" \
  "$CPMT_EXPECTED_PROTOCOL" \
  "$CPMT_EXPECTED_DATASET" <<'PY'
import json
import math
import sys
from pathlib import Path

import numpy as np

repo = Path(sys.argv[1])
manifest_path = Path(sys.argv[2])
s300_path = Path(sys.argv[3])
s1000_path = Path(sys.argv[4])
expected_training_commit = sys.argv[5]
expected_protocol = sys.argv[6]
expected_dataset = sys.argv[7]
registered_seeds = [7, 19, 31, 43, 59]

sys.path.insert(0, str(repo / "src"))

from cpmt.m1_metrics import paired_stratified_bootstrap

manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
reports = {
    300: json.loads(s300_path.read_text(encoding="utf-8")),
    1000: json.loads(s1000_path.read_text(encoding="utf-8")),
}

expected_source_hash = None
inner_group_ids = None
for steps, report in reports.items():
    assert report["schema_version"] == "cpmt-m1-scorer-diagnostic-v3"
    assert report["runner"] == "run_m1_scorer_diagnostics_v3"
    assert report["protocol_sha256"] == expected_protocol
    assert report["dataset_version"] == expected_dataset
    assert report["formal_run"] is False
    assert report["test_generated"] is False
    assert report["causal_complete"] is False
    assert report["seeds"] == registered_seeds
    assert report["input_arrays"]["train"]["arrays_digest"] == (
        manifest["arrays_digest"]
    )
    assert report["input_arrays"]["train"]["available_paired_groups"] == 40
    assert report["input_arrays"]["train"]["selected_paired_groups"] == 40

    provenance = report["training_provenance"]
    assert provenance["git_commit"] == expected_training_commit
    assert provenance["git_dirty"] is False
    if expected_source_hash is None:
        expected_source_hash = provenance["source_tree_sha256"]
    assert provenance["source_tree_sha256"] == expected_source_hash

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
    if inner_group_ids is None:
        inner_group_ids = partition["inner_dev_group_ids"]
    assert partition["inner_dev_group_ids"] == inner_group_ids

    budget = report["training_budget"]
    assert budget["online_students_trained"] is False
    assert budget["outcome_scorer_steps"] == steps
    assert budget["total_train_groups"] == 40

    online_mask = report["online_admissibility_mask"]
    assert online_mask["name"] == "transaction_static_preflight_v1"
    assert online_mask["enabled_for_methods"] == ["A", "B", "C", "D", "E"]
    assert online_mask["executor_illegal_energy_retained"] is True

    policy = report["scorer_diagnostic_policy"]
    assert policy["budget_selection_metric"] == (
        "shared_mask_inner_dev_candidate_ranking_accuracy"
    )
    assert policy["primary_bce_mismatch_diagnostic"] == "ranking_relevant_bce"

    audit = report["static_preflight_diagnostics"][
        "all_selected_train_online"
    ]
    assert audit["rows"] == 1600
    assert audit["legal_false_rejections"] == 0
    assert audit["remaining_executor_illegal_candidates"] == 0
    assert audit["reference_static_preflight_pass_rate"] == 1.0

    runs = report["outcome_scorer_diagnostics"]
    assert [run["seed"] for run in runs] == registered_seeds
    for run in runs:
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

group_rows = []
per_group_differences = {}
for group_id in inner_group_ids:
    group_key = str(group_id)
    group_means = {}
    for steps, report in reports.items():
        values = [
            run["inner_dev_online_by_group"][group_key]["teacher_accuracy"]
            for run in report["outcome_scorer_diagnostics"]
        ]
        group_means[steps] = float(np.mean(values))
    difference = group_means[1000] - group_means[300]
    per_group_differences[group_key] = difference
    group_rows.append({
        "scenario_family": "inner_dev",
        "paired_group_id": group_key,
        "steps_1000": {"candidate_ranking_accuracy": group_means[1000]},
        "steps_300": {"candidate_ranking_accuracy": group_means[300]},
    })

comparison = paired_stratified_bootstrap(
    group_rows,
    "steps_1000",
    "steps_300",
    "candidate_ranking_accuracy",
    higher_is_better=True,
    resamples=10_000,
    confidence=0.95,
    minimum_effect=0.0,
    seed=260_906,
)
selected_steps = 1000 if comparison["ci_low"] > 0.0 else 300

print("S2_REPORT_300={}".format(s300_path))
print("S2_REPORT_1000={}".format(s1000_path))
for steps, report in reports.items():
    runs = report["outcome_scorer_diagnostics"]
    teacher = np.asarray([
        run["inner_dev_online_chain"]["teacher_accuracy"] for run in runs
    ])
    bce = np.asarray([
        run["inner_dev_online_chain"]["masked_bce"] for run in runs
    ])
    ranking_bce = np.asarray([
        run["inner_dev_online_chain"]["ranking_relevant_bce"] for run in runs
    ])
    margin = np.asarray([
        run["inner_dev_online_chain"]["reference_probability_margin_mean"]
        for run in runs
    ])
    print(
        "S2_SUMMARY steps={} teacher_mean={:.6f} teacher_by_seed={} "
        "BCE_mean={:.6f} ranking_BCE_mean={:.6f} margin_mean={:.6f}".format(
            steps,
            float(teacher.mean()),
            [round(float(value), 6) for value in teacher],
            float(bce.mean()),
            float(ranking_bce.mean()),
            float(margin.mean()),
        )
    )

print(
    "S2_PAIRED_GROUP_DIFFS_1000_MINUS_300 {}".format(
        json.dumps(per_group_differences, sort_keys=True)
    )
)
print(
    "S2_REGISTERED_COMPARISON effect={:.6f} ci95=[{:.6f},{:.6f}] "
    "p_nonpositive={:.6f} paired_groups={} resamples={}".format(
        comparison["effect"],
        comparison["ci_low"],
        comparison["ci_high"],
        comparison["one_sided_p_nonpositive"],
        int(comparison["paired_groups"]),
        int(comparison["resamples"]),
    )
)
print("S2_REGISTERED_BUDGET_SELECTION steps={}".format(selected_steps))
PY
then
  cpmt_fail "s2_report_validation_or_comparison_failed"
fi

printf "SERVER_STEP_OK stage=%s\n" "$CPMT_SERVER_STEP_ID"
