#!/usr/bin/env bash
# Unique active CPMT server phase: export the completed v8 health benchmark.
#
# Prerequisites:
# - the clean repository descends from CPMT_GENERATION_COMMIT;
# - scientific/config/test paths still match the fully tested commit;
# - the exact full-test log/marker and 12-group train arrays/manifest exist;
# - use the repository's configured Python environment and pass no arguments.
#
# Read boundary: those existing ignored artifacts and tracked source/config.
# Write boundary: one exact results JSON. No arrays are regenerated or changed.
# Resume policy: an existing report is reused only if its protocol and arrays
# digest match; a mismatch fails without overwrite. This version does not test,
# generate, train, read validation/test, commit, or push.

set -uo pipefail

CPMT_SERVER_STEP_ID="m1_v5_v8_d041_health_export_g12"
CPMT_TESTED_COMMIT="c27e2581b5ced881d0d9f8283ad8c1865fdc1342"
CPMT_GENERATION_COMMIT="d0dafc23d8ee618a7f4083601025bb53888c50d3"
CPMT_FULL_TEST_STEP_ID="m1_v5_v8_d041_full_test_audit_hardening"
CPMT_EXPECTED_PROTOCOL="1af46e526e94fb0f186166bf2e34a16c61468e2e70fe583b602341eead994189"
CPMT_EXPECTED_DATASET="m1-paired-latent-worlds-v8-fixed-range-current-energy"

CPMT_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
CPMT_REPO_DIR="$(git -C "$CPMT_SCRIPT_DIR" rev-parse --show-toplevel)" || exit 2
CPMT_CURRENT_COMMIT="$(git -C "$CPMT_REPO_DIR" rev-parse HEAD)" || exit 2
CPMT_PREFLIGHT_DIR="$CPMT_REPO_DIR/outputs/m1-v5-server-preflight"
CPMT_FULL_TEST_MARKER="$CPMT_PREFLIGHT_DIR/$CPMT_FULL_TEST_STEP_ID.ok"
CPMT_FULL_TEST_LOG="$CPMT_PREFLIGHT_DIR/$CPMT_FULL_TEST_STEP_ID.log"
CPMT_HEALTH_DIR="$CPMT_REPO_DIR/outputs/m1-v5-v8-health-g12-c27e258"
CPMT_HEALTH_ARRAYS="$CPMT_HEALTH_DIR/train.npz"
CPMT_HEALTH_MANIFEST="$CPMT_HEALTH_DIR/train.manifest.json"
CPMT_HEALTH_REPORT_REL="results/m1_v5_s4_v8_health_benchmark.json"
CPMT_HEALTH_REPORT="$CPMT_REPO_DIR/$CPMT_HEALTH_REPORT_REL"

cpmt_fail() {
  local CPMT_FAILURE_MESSAGE="$1"
  printf "SERVER_STEP_FAILED id=%s reason=%s\n" \
    "$CPMT_SERVER_STEP_ID" "$CPMT_FAILURE_MESSAGE" >&2
  exit 1
}

[[ "$#" -eq 0 ]] || cpmt_fail "unexpected_arguments"
git -C "$CPMT_REPO_DIR" diff --quiet || cpmt_fail "tracked_changes_present"
git -C "$CPMT_REPO_DIR" diff --cached --quiet || \
  cpmt_fail "staged_changes_present"
while IFS= read -r CPMT_UNTRACKED_PATH; do
  [[ "$CPMT_UNTRACKED_PATH" == "$CPMT_HEALTH_REPORT_REL" ]] || \
    cpmt_fail "unexpected_untracked_path"
done < <(git -C "$CPMT_REPO_DIR" ls-files --others --exclude-standard)
git -C "$CPMT_REPO_DIR" merge-base --is-ancestor \
  "$CPMT_GENERATION_COMMIT" "$CPMT_CURRENT_COMMIT" || \
  cpmt_fail "generation_commit_not_in_history"
git -C "$CPMT_REPO_DIR" diff --quiet "$CPMT_TESTED_COMMIT" HEAD -- \
  src scripts configs tests || \
  cpmt_fail "scientific_or_test_paths_changed_since_full_test"
command -v python >/dev/null 2>&1 || cpmt_fail "python_not_found"

[[ -f "$CPMT_FULL_TEST_MARKER" ]] || cpmt_fail "full_test_marker_missing"
[[ -f "$CPMT_FULL_TEST_LOG" ]] || cpmt_fail "full_test_log_missing"
[[ -f "$CPMT_HEALTH_ARRAYS" ]] || cpmt_fail "health_arrays_missing"
[[ -f "$CPMT_HEALTH_MANIFEST" ]] || cpmt_fail "health_manifest_missing"
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
printf "repo=%s\ncurrent_commit=%s\n" \
  "$CPMT_REPO_DIR" "$CPMT_CURRENT_COMMIT"
printf "prerequisite=existing_valid_full_test_and_health_artifacts\n"
printf "read_boundary=%s,%s,%s,%s\n" \
  "$CPMT_FULL_TEST_MARKER" "$CPMT_FULL_TEST_LOG" \
  "$CPMT_HEALTH_ARRAYS" "$CPMT_HEALTH_MANIFEST"
printf "write_boundary=%s\n" "$CPMT_HEALTH_REPORT"
printf "generation=false training=false validation_access=false test_access=false\n"

if ! python - \
  "$CPMT_REPO_DIR" "$CPMT_CURRENT_COMMIT" "$CPMT_TESTED_COMMIT" \
  "$CPMT_GENERATION_COMMIT" "$CPMT_EXPECTED_PROTOCOL" \
  "$CPMT_EXPECTED_DATASET" "$CPMT_FULL_TEST_MARKER" \
  "$CPMT_FULL_TEST_LOG" "$CPMT_HEALTH_ARRAYS" \
  "$CPMT_HEALTH_MANIFEST" "$CPMT_HEALTH_REPORT" <<'PY'
import json
import re
import sys
from pathlib import Path

import numpy as np

repo = Path(sys.argv[1])
handoff_commit = sys.argv[2]
tested_commit = sys.argv[3]
generation_commit = sys.argv[4]
expected_protocol = sys.argv[5]
expected_dataset = sys.argv[6]
test_marker_path = Path(sys.argv[7])
test_log_path = Path(sys.argv[8])
arrays_path = Path(sys.argv[9])
manifest_path = Path(sys.argv[10])
report_path = Path(sys.argv[11])
sys.path.insert(0, str(repo / "src"))
from cpmt.run_provenance import arrays_sha256, capture_run_provenance

manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
arrays = {
    key: value for key, value in np.load(arrays_path, allow_pickle=True).items()
}
digest = arrays_sha256(arrays)
assert digest == manifest["arrays_digest"]
assert manifest["schema_version"] == "cpmt-m1-generation-manifest-v5"
assert manifest["runner"] == "generate_m1_parallel_v5"
assert manifest["protocol_sha256"] == expected_protocol
assert manifest["dataset_version"] == expected_dataset
assert manifest["split"] == "train"
assert manifest["paired_groups_total"] == 12
assert manifest["paired_group_count_semantics"] == (
    "total_mixed_groups_each_group_contains_all_families"
)
assert manifest["generation_provenance"]["git_commit"] == generation_commit
assert manifest["generation_provenance"]["git_dirty"] is False
assert manifest["teacher_health_gate"]["pass"] is True
assert manifest["family_mechanism_gate"][
    "all_configured_families_in_every_paired_group"
] is True
assert manifest["family_mechanism_gate"][
    "behavioral_fingerprints_unique"
] is True
assert manifest["family_mechanism_gate"][
    "c10_dynamic_static_variants_present"
] is True
assert manifest["family_mechanism_gate"][
    "c11_legal_collateral_contrast_present_each_row"
] is True
assert manifest["current_now_comparability"][
    "exact_ambiguity_current_target_identity_rate"
] == 1.0
posterior = manifest["teacher_posterior_term_influence"]
assert posterior["expected_now_activation_pattern"][
    "matches_expected_pattern"
] is True
assert posterior["expected_now_activation_pattern"][
    "unexpected_zero_families"
] == []
assert posterior["expected_now_activation_pattern"][
    "unexpected_nonzero_families"
] == []
assert manifest["formal_run"] is False
assert manifest["test_generated"] is False

test_log = test_log_path.read_text(encoding="utf-8", errors="replace")
match = re.search(r"Ran (\d+) tests in ([0-9.]+)s", test_log)
assert match is not None
assert "\nOK\n" in "\n" + test_log
test_count = int(match.group(1))
test_seconds = float(match.group(2))
assert test_count == 175

train_groups = 1000
all_groups = 1400
benchmark_groups = int(manifest["paired_groups_total"])

def cost_reference(groups: int) -> dict:
    scale = groups / benchmark_groups
    return {
        "paired_groups_total": groups,
        "learning_rows": round(manifest["decisions"] * scale),
        "candidate_slots_k16": round(manifest["decisions"] * scale * 16),
        "generation_seconds": manifest["generation_seconds"] * scale,
        "merged_npz_bytes": round(manifest["merged_npz_bytes"] * scale),
        "retained_shard_bytes": round(
            manifest["retained_shard_bytes"] * scale
        ),
        "merged_plus_shards_bytes": round(
            (
                manifest["merged_npz_bytes"]
                + manifest["retained_shard_bytes"]
            ) * scale
        ),
    }

report = {
    "schema_version": "cpmt-m1-v5-health-benchmark-v2",
    "status": "train_only_pretest_health_and_cost_benchmark_passed",
    "formal_run": False,
    "validation_access": False,
    "test_access": False,
    "test_generated": False,
    "protocol_sha256": expected_protocol,
    "dataset_version": expected_dataset,
    "scientific_tested_commit": tested_commit,
    "generation_commit": generation_commit,
    "generation_provenance": manifest["generation_provenance"],
    "export_handoff_commit": handoff_commit,
    "export_provenance": capture_run_provenance(
        repo,
        component="m1_v5_v8_health_benchmark_export",
        entrypoint=repo / "ops" / "run_next_server_step.sh",
    ),
    "full_test": {
        "marker": str(test_marker_path),
        "log": str(test_log_path),
        "tests": test_count,
        "seconds": test_seconds,
        "exit_code": 0,
    },
    "source_arrays": str(arrays_path),
    "source_manifest": str(manifest_path),
    "arrays_digest": digest,
    "benchmark": {
        "paired_groups_total": benchmark_groups,
        "paired_group_count_semantics": manifest[
            "paired_group_count_semantics"
        ],
        "learning_rows": manifest["decisions"],
        "online_chain_decisions": manifest["online_chain_decisions"],
        "recovery_training_examples": manifest[
            "recovery_training_examples"
        ],
        "workers": manifest["workers"],
        "generation_seconds": manifest["generation_seconds"],
        "merged_npz_bytes": manifest["merged_npz_bytes"],
        "retained_shard_count": manifest["retained_shard_count"],
        "retained_shard_bytes": manifest["retained_shard_bytes"],
    },
    "teacher_health_gate": manifest["teacher_health_gate"],
    "family_mechanism_audit": manifest["family_mechanism_audit"],
    "family_mechanism_gate": manifest["family_mechanism_gate"],
    "current_now_comparability": manifest["current_now_comparability"],
    "teacher_posterior_term_influence": posterior,
    "live_energy_activation_by_family": manifest[
        "live_energy_activation_by_family"
    ],
    "linear_cost_references_not_limits": {
        "formal_train_1000_total_mixed_groups": cost_reference(train_groups),
        "all_splits_1400_total_mixed_groups": cost_reference(all_groups),
    },
    "interpretation": (
        "This train-only benchmark validates v8 teacher health, registered "
        "family mechanisms, fixed current scaling, expected now activation, "
        "and posterior influence. Linear cost projections are planning "
        "references, not fixed caps or method-effect results."
    ),
}

if report_path.exists():
    existing = json.loads(report_path.read_text(encoding="utf-8"))
    assert existing["schema_version"] == report["schema_version"]
    assert existing["protocol_sha256"] == expected_protocol
    assert existing["arrays_digest"] == digest
    assert existing["scientific_tested_commit"] == tested_commit
    print("HEALTH_EXPORT_REUSED={}".format(report_path))
else:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print("HEALTH_EXPORT_WRITTEN={}".format(report_path))

print("HEALTH_ARRAYS_DIGEST={}".format(digest))
print("HEALTH_TEACHER_AGREEMENT={:.6f}".format(
    manifest["teacher_health_gate"]["overall_reference_agreement"]
))
print("HEALTH_NOW_PATTERN_MATCH=true")
print("FORMAL_TRAIN_GENERATION_MINUTES_REFERENCE={:.3f}".format(
    cost_reference(train_groups)["generation_seconds"] / 60.0
))
print("ALL_SPLITS_GENERATION_MINUTES_REFERENCE={:.3f}".format(
    cost_reference(all_groups)["generation_seconds"] / 60.0
))
PY
then
  cpmt_fail "health_export_validation_failed"
fi

printf "SERVER_STEP_OK id=%s\n" "$CPMT_SERVER_STEP_ID"
printf "NEXT=review_then_use_a_new_commit_for_git_add_commit_push\n"
