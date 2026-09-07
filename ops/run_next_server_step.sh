#!/usr/bin/env bash
# Unique active CPMT server phase: generate the sole 1,000-group v8 train arrays.
#
# Prerequisites:
# - the clean checkout descends from CPMT_TESTED_COMMIT;
# - its matching 191-test JSON marker exists from the preceding phase;
# - source/scripts/configs/tests are unchanged since that tested commit.
# - the 12-group D-043 health artifact exists and has the frozen v8 digest.
#
# Read boundary: tracked train generator/config/source, Git metadata, the
# matching full-test marker and the verified 12-group health artifact.
# Write boundary: one ignored outputs directory containing the 1,000-group
# train-only arrays, retained per-group shards and manifest.
# Resume policy: reuse only a complete arrays/manifest pair that passes every
# check below. Any partial output directory is reported and never overwritten
# or deleted. This stage does not rerun tests/health, train, run causal
# evaluation, read validation/test, export results, or modify Git.

set -uo pipefail

CPMT_SERVER_STEP_ID="m1_v6_v8_d043_train_generation_g1000"
CPMT_TESTED_COMMIT="53539ce54320c8098f210c7a62eaee05f9ecd41f"
CPMT_FULL_TEST_STEP_ID="m1_v6_v8_d043_architecture_budget_full_test"
CPMT_EXPECTED_PROTOCOL="73666cabb77b4884302d77ca621669bfdc77e86a44951b8a92b97208509c0eec"
CPMT_EXPECTED_DATASET="m1-paired-latent-worlds-v8-fixed-range-current-energy"
CPMT_EXPECTED_TESTS="191"
CPMT_EXPECTED_HEALTH_ARRAYS_DIGEST="e924f96d4cf28179df010766e4275244cbb78cb9f9425ed514093bdbca3958c3"
CPMT_TRAIN_PAIRED_GROUPS="1000"
CPMT_WORKERS="${CPMT_WORKERS:-16}"

CPMT_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
CPMT_REPO_DIR="$(git -C "$CPMT_SCRIPT_DIR" rev-parse --show-toplevel)" || exit 2
CPMT_CURRENT_COMMIT="$(git -C "$CPMT_REPO_DIR" rev-parse HEAD)" || exit 2
CPMT_TESTED_SHORT="$(git -C "$CPMT_REPO_DIR" rev-parse --short=7 \
  "$CPMT_TESTED_COMMIT")" || exit 2
CPMT_FULL_TEST_DIR="$CPMT_REPO_DIR/outputs/m1-v6-v8-d043-full-test-$CPMT_TESTED_SHORT"
CPMT_FULL_TEST_MARKER="$CPMT_FULL_TEST_DIR/full_test.ok.json"
CPMT_HEALTH_DIR="$CPMT_REPO_DIR/outputs/m1-v6-v8-d043-health-g12-$CPMT_TESTED_SHORT"
CPMT_HEALTH_ARRAYS="$CPMT_HEALTH_DIR/train.npz"
CPMT_HEALTH_MANIFEST="$CPMT_HEALTH_DIR/train.manifest.json"
CPMT_TRAIN_DIR="$CPMT_REPO_DIR/outputs/m1-v6-v8-d043-train-g1000-$CPMT_TESTED_SHORT"
CPMT_TRAIN_ARRAYS="$CPMT_TRAIN_DIR/train.npz"
CPMT_TRAIN_MANIFEST="$CPMT_TRAIN_DIR/train.manifest.json"

cpmt_fail() {
  local CPMT_FAILURE_MESSAGE="$1"
  printf "SERVER_STEP_FAILED id=%s reason=%s\n" \
    "$CPMT_SERVER_STEP_ID" "$CPMT_FAILURE_MESSAGE" >&2
  exit 1
}

[[ "$#" -eq 0 ]] || cpmt_fail "unexpected_arguments"
[[ "$CPMT_WORKERS" =~ ^[1-9][0-9]*$ ]] || cpmt_fail "invalid_worker_count"
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

printf "SERVER_STEP_BEGIN id=%s\n" "$CPMT_SERVER_STEP_ID"
printf "repo=%s\ncurrent_commit=%s\n" \
  "$CPMT_REPO_DIR" "$CPMT_CURRENT_COMMIT"
printf "tested_commit=%s\n" "$CPMT_TESTED_COMMIT"
printf "protocol_sha256=%s dataset=%s\n" \
  "$CPMT_PROTOCOL" "$CPMT_EXPECTED_DATASET"
printf "read_boundary=train_generator_config_source_git_full_test_and_health\n"
printf "write_boundary=%s\n" "$CPMT_TRAIN_DIR"
printf "train_only=true paired_groups=%s workers=%s\n" \
  "$CPMT_TRAIN_PAIRED_GROUPS" "$CPMT_WORKERS"
printf "training=false validation_access=false test_access=false\n"
printf "expected_health_arrays_digest=%s\n" \
  "$CPMT_EXPECTED_HEALTH_ARRAYS_DIGEST"

[[ -f "$CPMT_HEALTH_ARRAYS" && -f "$CPMT_HEALTH_MANIFEST" ]] || \
  cpmt_fail "verified_health_artifact_pair_missing"

python - \
  "$CPMT_REPO_DIR" "$CPMT_HEALTH_ARRAYS" "$CPMT_HEALTH_MANIFEST" \
  "$CPMT_EXPECTED_PROTOCOL" "$CPMT_EXPECTED_DATASET" \
  "$CPMT_EXPECTED_HEALTH_ARRAYS_DIGEST" <<'PY' || \
  cpmt_fail "health_prerequisite_validation_failed"
import json
import sys
from pathlib import Path

import numpy as np

repo = Path(sys.argv[1])
arrays_path = Path(sys.argv[2])
manifest_path = Path(sys.argv[3])
expected_protocol = sys.argv[4]
expected_dataset = sys.argv[5]
expected_arrays_digest = sys.argv[6]
sys.path.insert(0, str(repo / "src"))
from cpmt.run_provenance import arrays_sha256

manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
arrays = {
    key: value for key, value in np.load(arrays_path, allow_pickle=True).items()
}
actual_arrays_digest = arrays_sha256(arrays)
assert actual_arrays_digest == manifest["arrays_digest"]
assert actual_arrays_digest == expected_arrays_digest
assert manifest["schema_version"] == "cpmt-m1-generation-manifest-v5"
assert manifest["runner"] == "generate_m1_parallel_v5"
assert manifest["protocol_sha256"] == expected_protocol
assert manifest["dataset_version"] == expected_dataset
assert manifest["split"] == "train"
assert manifest["configured_scenario_families"] == [
    "C00", "C01", "C02", "C03", "C04", "C05",
    "C06", "C07", "C08", "C09", "C10", "C11",
]
assert manifest["paired_groups_total"] == 12
assert set(manifest["causal_paired_group_support_by_family"].values()) == {12}
family_gate = manifest["family_mechanism_gate"]
assert family_gate["all_configured_families_in_every_paired_group"] is True
assert family_gate["behavioral_fingerprints_unique"] is True
assert family_gate["duplicate_behavioral_fingerprint_groups"] == []
assert family_gate["c10_dynamic_static_variants_present"] is True
assert family_gate["c11_legal_collateral_contrast_present_each_row"] is True
current_audit = manifest["current_now_comparability"]
assert current_audit["exact_ambiguity_current_target_identity_rate"] == 1.0
scaling = current_audit["fixed_natural_range_scaling"]
assert scaling["all_available_values_within_0_1"] is True
assert scaling["maximum_absolute_scaling_error"] <= 1e-6
posterior = manifest["teacher_posterior_term_influence"]
pattern = posterior["expected_now_activation_pattern"]
assert pattern["matches_expected_pattern"] is True
assert pattern["unexpected_zero_families"] == []
assert pattern["unexpected_nonzero_families"] == []
assert manifest["teacher_health_gate"]["pass"] is True
assert manifest["test_generated"] is False
assert manifest["formal_run"] is False

print("HEALTH_INPUT_OK arrays_digest={}".format(actual_arrays_digest))
print("HEALTH_ARRAYS_DIGEST_INVARIANT=true")
print("HEALTH_LEARNING_ROWS={}".format(manifest["decisions"]))
print("HEALTH_ONLINE_ROWS={}".format(manifest["online_chain_decisions"]))
print("HEALTH_RECOVERY_ROWS={}".format(manifest["recovery_training_examples"]))
print("HEALTH_GENERATION_SECONDS={:.3f}".format(
    manifest["generation_seconds"]
))
print("HEALTH_MERGED_NPZ_BYTES={}".format(manifest["merged_npz_bytes"]))
print("HEALTH_TEACHER_AGREEMENT={:.6f}".format(
    manifest["teacher_health_gate"]["overall_reference_agreement"]
))
print("HEALTH_NOW_PATTERN_MATCH=true")
print("HEALTH_MANIFEST={}".format(manifest_path))
PY

if [[ -f "$CPMT_TRAIN_ARRAYS" && -f "$CPMT_TRAIN_MANIFEST" ]]; then
  printf "TRAIN_GENERATION_REUSED arrays=%s\n" "$CPMT_TRAIN_ARRAYS"
elif [[ -d "$CPMT_TRAIN_DIR" && -n "$(find "$CPMT_TRAIN_DIR" \
  -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
  cpmt_fail "partial_train_output_directory_requires_inspection"
else
  mkdir -p "$CPMT_TRAIN_DIR" || cpmt_fail "cannot_create_train_directory"
  (
    cd "$CPMT_REPO_DIR" || exit 2
    python scripts/generate_m1_parallel.py \
      --config configs/m1_hard_condition.json \
      --split train \
      --paired-groups "$CPMT_TRAIN_PAIRED_GROUPS" \
      --future-hash-bins 32 \
      --workers "$CPMT_WORKERS" \
      --out "$CPMT_TRAIN_ARRAYS"
  )
  CPMT_GENERATION_EXIT="$?"
  printf "TRAIN_GENERATION_EXIT=%s\n" "$CPMT_GENERATION_EXIT"
  [[ "$CPMT_GENERATION_EXIT" -eq 0 ]] || \
    cpmt_fail "train_generation_or_teacher_gate_failed"
fi

python - \
  "$CPMT_REPO_DIR" "$CPMT_TRAIN_ARRAYS" "$CPMT_TRAIN_MANIFEST" \
  "$CPMT_EXPECTED_PROTOCOL" "$CPMT_EXPECTED_DATASET" \
  "$CPMT_TRAIN_PAIRED_GROUPS" <<'PY' || \
  cpmt_fail "train_artifact_validation_failed"
import json
import sys
from pathlib import Path

import numpy as np

repo = Path(sys.argv[1])
arrays_path = Path(sys.argv[2])
manifest_path = Path(sys.argv[3])
expected_protocol = sys.argv[4]
expected_dataset = sys.argv[5]
expected_groups = int(sys.argv[6])
sys.path.insert(0, str(repo / "src"))
from cpmt.run_provenance import arrays_sha256

manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
arrays = {
    key: value for key, value in np.load(arrays_path, allow_pickle=True).items()
}
actual_arrays_digest = arrays_sha256(arrays)
assert actual_arrays_digest == manifest["arrays_digest"]
assert manifest["schema_version"] == "cpmt-m1-generation-manifest-v5"
assert manifest["runner"] == "generate_m1_parallel_v5"
assert manifest["protocol_sha256"] == expected_protocol
assert manifest["dataset_version"] == expected_dataset
assert manifest["split"] == "train"
assert manifest["paired_groups_total"] == expected_groups
assert manifest["paired_group_count_semantics"] == (
    "total_mixed_groups_each_group_contains_all_families"
)
assert manifest["configured_scenario_families"] == [
    "C00", "C01", "C02", "C03", "C04", "C05",
    "C06", "C07", "C08", "C09", "C10", "C11",
]
assert set(manifest["causal_paired_group_support_by_family"].values()) == {
    expected_groups
}
assert set(np.asarray(arrays["group"], dtype=np.int64)) == set(
    range(expected_groups)
)
assert manifest["decisions"] == expected_groups * 40
assert manifest["online_chain_decisions"] == expected_groups * 38
assert manifest["recovery_training_examples"] == expected_groups * 2
assert manifest["retained_shard_count"] == expected_groups
family_gate = manifest["family_mechanism_gate"]
assert family_gate["all_configured_families_in_every_paired_group"] is True
assert family_gate["behavioral_fingerprints_unique"] is True
assert family_gate["duplicate_behavioral_fingerprint_groups"] == []
assert family_gate["c10_dynamic_static_variants_present"] is True
assert family_gate["c11_legal_collateral_contrast_present_each_row"] is True
current_audit = manifest["current_now_comparability"]
assert current_audit["exact_ambiguity_current_target_identity_rate"] == 1.0
scaling = current_audit["fixed_natural_range_scaling"]
assert scaling["all_available_values_within_0_1"] is True
assert scaling["maximum_absolute_scaling_error"] <= 1e-6
posterior = manifest["teacher_posterior_term_influence"]
pattern = posterior["expected_now_activation_pattern"]
assert pattern["matches_expected_pattern"] is True
assert pattern["unexpected_zero_families"] == []
assert pattern["unexpected_nonzero_families"] == []
assert manifest["teacher_health_gate"]["pass"] is True
assert manifest["test_generated"] is False
assert manifest["formal_run"] is False

print("TRAIN_INPUT_OK arrays_digest={}".format(actual_arrays_digest))
print("TRAIN_PAIRED_GROUPS={}".format(manifest["paired_groups_total"]))
print("TRAIN_LEARNING_ROWS={}".format(manifest["decisions"]))
print("TRAIN_ONLINE_ROWS={}".format(manifest["online_chain_decisions"]))
print("TRAIN_RECOVERY_ROWS={}".format(manifest["recovery_training_examples"]))
print("TRAIN_GENERATION_SECONDS={:.3f}".format(
    manifest["generation_seconds"]
))
print("TRAIN_MERGED_NPZ_BYTES={}".format(manifest["merged_npz_bytes"]))
print("TRAIN_RETAINED_SHARD_BYTES={}".format(
    manifest["retained_shard_bytes"]
))
print("TRAIN_TEACHER_AGREEMENT={:.6f}".format(
    manifest["teacher_health_gate"]["overall_reference_agreement"]
))
print("TRAIN_NOW_PATTERN_MATCH=true")
print("TRAIN_MANIFEST={}".format(manifest_path))
PY

printf "SERVER_STEP_OK id=%s\n" "$CPMT_SERVER_STEP_ID"
printf "NEXT=review_manifest_then_profile_registered_budget_runtime\n"
