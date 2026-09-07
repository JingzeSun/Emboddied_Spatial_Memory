#!/usr/bin/env bash
# Unique active CPMT server phase: 12-group v8 train-only health generation.
#
# Prerequisites:
# - the clean repository descends from CPMT_TESTED_COMMIT;
# - the matching full-test marker from the preceding phase exists;
# - tracked scientific/config/test paths have not changed since that test;
# - use the repository's configured Python environment and pass no arguments.
#
# Read boundary: tracked train generator/config/source plus the full-test marker.
# Write boundary: one ignored outputs/ health directory only.
# Resume policy: reuse only when both arrays and manifest already exist and pass
# all validations. A partial pair is reported for inspection and never deleted
# or overwritten. This version does not rerun tests, train, read validation/test,
# export into results/, commit, or push.

set -uo pipefail

CPMT_SERVER_STEP_ID="m1_v5_v8_d041_health_generation_g12"
CPMT_TESTED_COMMIT="c27e2581b5ced881d0d9f8283ad8c1865fdc1342"
CPMT_FULL_TEST_STEP_ID="m1_v5_v8_d041_full_test_audit_hardening"
CPMT_EXPECTED_PROTOCOL="1af46e526e94fb0f186166bf2e34a16c61468e2e70fe583b602341eead994189"
CPMT_EXPECTED_DATASET="m1-paired-latent-worlds-v8-fixed-range-current-energy"
CPMT_HEALTH_PAIRED_GROUPS="12"
CPMT_WORKERS="${CPMT_WORKERS:-16}"

CPMT_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
CPMT_REPO_DIR="$(git -C "$CPMT_SCRIPT_DIR" rev-parse --show-toplevel)" || exit 2
CPMT_CURRENT_COMMIT="$(git -C "$CPMT_REPO_DIR" rev-parse HEAD)" || exit 2
CPMT_PREFLIGHT_DIR="$CPMT_REPO_DIR/outputs/m1-v5-server-preflight"
CPMT_FULL_TEST_MARKER="$CPMT_PREFLIGHT_DIR/$CPMT_FULL_TEST_STEP_ID.ok"
CPMT_HEALTH_DIR="$CPMT_REPO_DIR/outputs/m1-v5-v8-health-g12-c27e258"
CPMT_HEALTH_ARRAYS="$CPMT_HEALTH_DIR/train.npz"
CPMT_HEALTH_MANIFEST="$CPMT_HEALTH_DIR/train.manifest.json"

cpmt_fail() {
  local CPMT_FAILURE_MESSAGE="$1"
  printf "SERVER_STEP_FAILED id=%s reason=%s\n" \
    "$CPMT_SERVER_STEP_ID" "$CPMT_FAILURE_MESSAGE" >&2
  exit 1
}

[[ "$#" -eq 0 ]] || cpmt_fail "unexpected_arguments"
[[ "$CPMT_WORKERS" =~ ^[1-9][0-9]*$ ]] || cpmt_fail "invalid_worker_count"
[[ -z "$(git -C "$CPMT_REPO_DIR" status --porcelain)" ]] || \
  cpmt_fail "working_tree_not_clean"
git -C "$CPMT_REPO_DIR" merge-base --is-ancestor \
  "$CPMT_TESTED_COMMIT" "$CPMT_CURRENT_COMMIT" || \
  cpmt_fail "tested_commit_not_in_history"
git -C "$CPMT_REPO_DIR" diff --quiet "$CPMT_TESTED_COMMIT" HEAD -- \
  src scripts configs tests || \
  cpmt_fail "scientific_or_test_paths_changed_since_full_test"
command -v python >/dev/null 2>&1 || cpmt_fail "python_not_found"

[[ -f "$CPMT_FULL_TEST_MARKER" ]] || cpmt_fail "full_test_marker_missing"
grep -Fxq "status=ok" "$CPMT_FULL_TEST_MARKER" || \
  cpmt_fail "full_test_marker_not_successful"
grep -Fxq "step_id=$CPMT_FULL_TEST_STEP_ID" "$CPMT_FULL_TEST_MARKER" || \
  cpmt_fail "full_test_step_id_mismatch"
grep -Fxq "commit=$CPMT_TESTED_COMMIT" "$CPMT_FULL_TEST_MARKER" || \
  cpmt_fail "full_test_commit_mismatch"
grep -Fxq "protocol=$CPMT_EXPECTED_PROTOCOL" "$CPMT_FULL_TEST_MARKER" || \
  cpmt_fail "full_test_protocol_mismatch"
grep -Fxq "dataset=$CPMT_EXPECTED_DATASET" "$CPMT_FULL_TEST_MARKER" || \
  cpmt_fail "full_test_dataset_mismatch"

printf "SERVER_STEP_BEGIN id=%s\n" "$CPMT_SERVER_STEP_ID"
printf "repo=%s\ncurrent_commit=%s\ntested_commit=%s\n" \
  "$CPMT_REPO_DIR" "$CPMT_CURRENT_COMMIT" "$CPMT_TESTED_COMMIT"
printf "prerequisite=matching_full_test_marker_and_unchanged_scientific_paths\n"
printf "read_boundary=train_generator_config_source_and_full_test_marker\n"
printf "write_boundary=%s\n" "$CPMT_HEALTH_DIR"
printf "train_only=true validation_access=false test_access=false\n"
printf "paired_groups=%s workers=%s\n" \
  "$CPMT_HEALTH_PAIRED_GROUPS" "$CPMT_WORKERS"

if [[ -f "$CPMT_HEALTH_ARRAYS" && -f "$CPMT_HEALTH_MANIFEST" ]]; then
  printf "HEALTH_GENERATION_REUSED arrays=%s\n" "$CPMT_HEALTH_ARRAYS"
elif [[ -e "$CPMT_HEALTH_ARRAYS" || -e "$CPMT_HEALTH_MANIFEST" ]]; then
  cpmt_fail "partial_health_artifact_pair_requires_inspection"
else
  mkdir -p "$CPMT_HEALTH_DIR"
  (
    cd "$CPMT_REPO_DIR" || exit 2
    python scripts/generate_m1_parallel.py \
      --config configs/m1_hard_condition.json \
      --split train \
      --paired-groups "$CPMT_HEALTH_PAIRED_GROUPS" \
      --future-hash-bins 32 \
      --workers "$CPMT_WORKERS" \
      --out "$CPMT_HEALTH_ARRAYS"
  )
  CPMT_GENERATION_EXIT="$?"
  printf "HEALTH_GENERATION_EXIT=%s\n" "$CPMT_GENERATION_EXIT"
  [[ "$CPMT_GENERATION_EXIT" -eq 0 ]] || \
    cpmt_fail "health_generation_or_teacher_gate_failed"
fi

if ! python - \
  "$CPMT_REPO_DIR" "$CPMT_HEALTH_ARRAYS" "$CPMT_HEALTH_MANIFEST" \
  "$CPMT_EXPECTED_PROTOCOL" "$CPMT_EXPECTED_DATASET" <<'PY'
import json
import sys
from pathlib import Path

import numpy as np

repo = Path(sys.argv[1])
arrays_path = Path(sys.argv[2])
manifest_path = Path(sys.argv[3])
expected_protocol = sys.argv[4]
expected_dataset = sys.argv[5]
sys.path.insert(0, str(repo / "src"))
from cpmt.run_provenance import arrays_sha256

manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
arrays = {
    key: value for key, value in np.load(arrays_path, allow_pickle=True).items()
}
assert arrays_sha256(arrays) == manifest["arrays_digest"]
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
assert manifest["paired_group_count_semantics"] == (
    "total_mixed_groups_each_group_contains_all_families"
)
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
assert set(scaling["natural_ranges"]).issubset({1.0, 2.0, 4.0})
posterior = manifest["teacher_posterior_term_influence"]
assert posterior["interpretation"] == "posterior_distribution_not_argmax_only"
assert set(posterior["terms"]) == {
    "now", "future", "edit", "growth", "collateral",
}
pattern = posterior["expected_now_activation_pattern"]
assert pattern["matches_expected_pattern"] is True
assert pattern["unexpected_zero_families"] == []
assert pattern["unexpected_nonzero_families"] == []
assert pattern["primary_gate"] is False
assert manifest["teacher_health_gate"]["pass"] is True
assert manifest["test_generated"] is False
assert manifest["formal_run"] is False

print("HEALTH_INPUT_OK arrays_digest={}".format(manifest["arrays_digest"]))
print("HEALTH_LEARNING_ROWS={}".format(manifest["decisions"]))
print("HEALTH_ONLINE_ROWS={}".format(manifest["online_chain_decisions"]))
print("HEALTH_RECOVERY_ROWS={}".format(manifest["recovery_training_examples"]))
print("HEALTH_GENERATION_SECONDS={:.3f}".format(
    manifest["generation_seconds"]
))
print("HEALTH_MERGED_NPZ_BYTES={}".format(manifest["merged_npz_bytes"]))
print("HEALTH_RETAINED_SHARD_BYTES={}".format(
    manifest["retained_shard_bytes"]
))
print("HEALTH_TEACHER_AGREEMENT={:.6f}".format(
    manifest["teacher_health_gate"]["overall_reference_agreement"]
))
print("HEALTH_NOW_PATTERN_MATCH=true")
print("HEALTH_NOW_MEAN_TV={:.9f}".format(
    posterior["terms"]["now"]["all"]["total_variation"]["mean"]
))
print("HEALTH_MANIFEST={}".format(manifest_path))
PY
then
  cpmt_fail "health_artifact_validation_failed"
fi

printf "SERVER_STEP_OK id=%s\n" "$CPMT_SERVER_STEP_ID"
printf "NEXT=wait_for_a_new_commit_that_rewrites_this_entry_for_health_export\n"
