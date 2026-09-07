#!/usr/bin/env bash
# Unique active CPMT server phase: export the completed runtime profiles.
#
# Prerequisites: both architecture profile reports from the tested profiler
# exist and the checkout is clean and synchronized with origin/main.
# Read boundary: the two ignored runtime-profile JSON files and Git metadata.
# Write boundary: one small tracked results JSON. Arrays and profile sources
# remain untouched. Resume policy: validate and reuse an identical export;
# refuse to overwrite any conflicting result. This stage does not generate,
# train, select, evaluate causal metrics, or read validation/test.

set -uo pipefail

CPMT_SERVER_STEP_ID="m1_v6_v8_d043_runtime_profile_export"
CPMT_PROFILE_COMMIT="8b304e39403731bc6be28c26ff38699da71d879a"
CPMT_EXPECTED_PROTOCOL="73666cabb77b4884302d77ca621669bfdc77e86a44951b8a92b97208509c0eec"
CPMT_EXPECTED_DATASET="m1-paired-latent-worlds-v8-fixed-range-current-energy"
CPMT_EXPECTED_ARRAYS_DIGEST="e8a890f1b254a7109af641fea57fcbea5efd931b4272d8e96cb870f51604b168"
CPMT_RESULT_NAME="m1_v6_d043_runtime_profile"

CPMT_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
CPMT_REPO_DIR="$(git -C "$CPMT_SCRIPT_DIR" rev-parse --show-toplevel)" || exit 2
CPMT_CURRENT_COMMIT="$(git -C "$CPMT_REPO_DIR" rev-parse HEAD)" || exit 2
CPMT_PROFILE_SHORT="$(git -C "$CPMT_REPO_DIR" rev-parse --short=7 \
  "$CPMT_PROFILE_COMMIT")" || exit 2
CPMT_PROFILE_ROOT="$CPMT_REPO_DIR/outputs/m1-v6-v8-d043-runtime-profile-$CPMT_PROFILE_SHORT"
CPMT_RESULT_PATH="$CPMT_REPO_DIR/results/$CPMT_RESULT_NAME.json"

cpmt_fail() {
  local CPMT_FAILURE_MESSAGE="$1"
  printf "SERVER_STEP_FAILED id=%s reason=%s\n" \
    "$CPMT_SERVER_STEP_ID" "$CPMT_FAILURE_MESSAGE" >&2
  exit 1
}

[[ "$#" -eq 0 ]] || cpmt_fail "unexpected_arguments"
command -v python >/dev/null 2>&1 || cpmt_fail "python_not_found"
command -v git >/dev/null 2>&1 || cpmt_fail "git_not_found"
git -C "$CPMT_REPO_DIR" merge-base --is-ancestor \
  "$CPMT_PROFILE_COMMIT" "$CPMT_CURRENT_COMMIT" || \
  cpmt_fail "profile_commit_not_in_history"
git -C "$CPMT_REPO_DIR" diff --quiet || cpmt_fail "tracked_changes_present"
git -C "$CPMT_REPO_DIR" diff --cached --quiet || \
  cpmt_fail "staged_changes_present"
[[ -z "$(git -C "$CPMT_REPO_DIR" ls-files --others --exclude-standard)" ]] || \
  cpmt_fail "untracked_files_present"
CPMT_REMOTE_HEAD="$(git -C "$CPMT_REPO_DIR" ls-remote \
  origin refs/heads/main | awk '{print $1}')"
[[ "$CPMT_REMOTE_HEAD" == "$CPMT_CURRENT_COMMIT" ]] || \
  cpmt_fail "origin_main_does_not_match_checkout"

printf "SERVER_STEP_BEGIN id=%s\n" "$CPMT_SERVER_STEP_ID"
printf "repo=%s\ncurrent_commit=%s\nprofile_commit=%s\n" \
  "$CPMT_REPO_DIR" "$CPMT_CURRENT_COMMIT" "$CPMT_PROFILE_COMMIT"
printf "read_boundary=%s\nwrite_boundary=%s\n" \
  "$CPMT_PROFILE_ROOT" "$CPMT_RESULT_PATH"
printf "generation=false training=false selection=false scientific_metrics=false validation_access=false test_access=false\n"

python - \
  "$CPMT_PROFILE_ROOT/set_transformer/runtime_profile.json" \
  "$CPMT_PROFILE_ROOT/shared_mlp/runtime_profile.json" \
  "$CPMT_EXPECTED_PROTOCOL" "$CPMT_EXPECTED_DATASET" \
  "$CPMT_EXPECTED_ARRAYS_DIGEST" <<'PY' || \
  cpmt_fail "source_profile_validation_failed"
import json
import sys
from pathlib import Path

expected_architectures = [
    "cross_candidate_set_transformer_v1", "shared_candidate_mlp_v1",
]
for path, architecture in zip(sys.argv[1:3], expected_architectures, strict=True):
    report = json.loads(Path(path).read_text(encoding="utf-8"))
    assert report["schema_version"] == "cpmt-m1-v8-budget-runtime-profile-v1"
    assert report["architecture"] == architecture
    assert report["protocol_sha256"] == sys.argv[3]
    assert report["dataset_version"] == sys.argv[4]
    assert report["input_arrays"]["train"]["arrays_digest"] == sys.argv[5]
    assert report["selection_performed"] is False
    assert report["scientific_metrics_exported"] is False
    assert report["validation_arrays_read"] is False
    assert report["test_access"] is False
    assert report["registered_grid_projection"]["total_hours"] > 0.0
print("PROFILE_SOURCES_OK architectures=2")
PY

if [[ ! -f "$CPMT_RESULT_PATH" ]]; then
  (
    cd "$CPMT_REPO_DIR" || exit 2
    python scripts/export_run_report.py \
      --out-dir "$CPMT_PROFILE_ROOT" \
      --name "$CPMT_RESULT_NAME" \
      --note "D-043 planning-only two-architecture runtime projection; no selection or scientific metrics"
  ) || cpmt_fail "profile_export_failed"
fi

python - \
  "$CPMT_RESULT_PATH" "$CPMT_EXPECTED_PROTOCOL" \
  "$CPMT_EXPECTED_DATASET" "$CPMT_EXPECTED_ARRAYS_DIGEST" <<'PY' || \
  cpmt_fail "export_validation_failed"
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert payload["schema_version"] == "cpmt-exported-run-report-v2"
profiles = payload["runtime_profiles"]
assert set(profiles) == {
    "set_transformer/runtime_profile.json",
    "shared_mlp/runtime_profile.json",
}
hours = []
for report in profiles.values():
    assert report["protocol_sha256"] == sys.argv[2]
    assert report["dataset_version"] == sys.argv[3]
    assert report["input_arrays"]["train"]["arrays_digest"] == sys.argv[4]
    assert report["selection_performed"] is False
    assert report["scientific_metrics_exported"] is False
    hours.append(report["registered_grid_projection"]["total_hours"])
assert all(value > 0.0 for value in hours)
print("PROFILE_EXPORT_OK projected_hours_both={:.3f}".format(sum(hours)))
PY

printf "RESULT_PATH=%s\n" "$CPMT_RESULT_PATH"
printf "SERVER_STEP_OK id=%s\n" "$CPMT_SERVER_STEP_ID"
printf "NEXT=git_add_commit_push_exported_runtime_profile\n"
