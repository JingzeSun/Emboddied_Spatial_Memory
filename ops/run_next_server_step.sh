#!/usr/bin/env bash
# Unique active CPMT server phase: publish the exported v8 health JSON.
#
# Prerequisites:
# - the report was exported by CPMT_EXPORT_COMMIT and is the only untracked file;
# - scientific/config/test paths still match CPMT_TESTED_COMMIT;
# - the server branch starts at this handoff commit and origin/main agrees.
#
# Read boundary: one results JSON plus Git metadata.
# Write boundary: stage that exact JSON, create one commit, push origin/main.
# Resume policy: if the exact report is already tracked, validate it and accept
# only when local HEAD already equals origin/main. This version does not touch
# outputs/, regenerate, test, train, read validation/test, or stage other files.

set -uo pipefail

CPMT_SERVER_STEP_ID="m1_v5_v8_d041_health_report_git_publish"
CPMT_TESTED_COMMIT="c27e2581b5ced881d0d9f8283ad8c1865fdc1342"
CPMT_GENERATION_COMMIT="d0dafc23d8ee618a7f4083601025bb53888c50d3"
CPMT_EXPORT_COMMIT="9435d6f333a4a7cdbe18979b141eae00f3dd291d"
CPMT_EXPECTED_PROTOCOL="1af46e526e94fb0f186166bf2e34a16c61468e2e70fe583b602341eead994189"
CPMT_EXPECTED_DATASET="m1-paired-latent-worlds-v8-fixed-range-current-energy"
CPMT_HEALTH_REPORT_REL="results/m1_v5_s4_v8_health_benchmark.json"

CPMT_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
CPMT_REPO_DIR="$(git -C "$CPMT_SCRIPT_DIR" rev-parse --show-toplevel)" || exit 2
CPMT_CURRENT_COMMIT="$(git -C "$CPMT_REPO_DIR" rev-parse HEAD)" || exit 2
CPMT_HEALTH_REPORT="$CPMT_REPO_DIR/$CPMT_HEALTH_REPORT_REL"

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
  "$CPMT_EXPORT_COMMIT" "$CPMT_CURRENT_COMMIT" || \
  cpmt_fail "export_commit_not_in_history"
git -C "$CPMT_REPO_DIR" diff --quiet "$CPMT_TESTED_COMMIT" HEAD -- \
  src scripts configs tests || \
  cpmt_fail "scientific_or_test_paths_changed_since_full_test"
git -C "$CPMT_REPO_DIR" diff --quiet || cpmt_fail "tracked_changes_present"
git -C "$CPMT_REPO_DIR" diff --cached --quiet || \
  cpmt_fail "staged_changes_present"
[[ -f "$CPMT_HEALTH_REPORT" ]] || cpmt_fail "exported_health_report_missing"

if ! python - \
  "$CPMT_HEALTH_REPORT" "$CPMT_EXPECTED_PROTOCOL" \
  "$CPMT_EXPECTED_DATASET" "$CPMT_TESTED_COMMIT" \
  "$CPMT_GENERATION_COMMIT" "$CPMT_EXPORT_COMMIT" <<'PY'
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert report["schema_version"] == "cpmt-m1-v5-health-benchmark-v2"
assert report["status"] == "train_only_pretest_health_and_cost_benchmark_passed"
assert report["protocol_sha256"] == sys.argv[2]
assert report["dataset_version"] == sys.argv[3]
assert report["scientific_tested_commit"] == sys.argv[4]
assert report["generation_commit"] == sys.argv[5]
assert report["export_handoff_commit"] == sys.argv[6]
assert len(report["arrays_digest"]) == 64
assert report["full_test"]["tests"] == 175
assert report["full_test"]["exit_code"] == 0
assert report["benchmark"]["paired_groups_total"] == 12
assert report["benchmark"]["learning_rows"] == 480
assert report["benchmark"]["online_chain_decisions"] == 456
assert report["benchmark"]["recovery_training_examples"] == 24
assert report["teacher_health_gate"]["pass"] is True
assert report["teacher_health_gate"]["overall_reference_agreement"] == 1.0
assert report["family_mechanism_gate"][
    "all_configured_families_in_every_paired_group"
] is True
assert report["family_mechanism_gate"]["behavioral_fingerprints_unique"] is True
assert report["family_mechanism_gate"][
    "c10_dynamic_static_variants_present"
] is True
assert report["family_mechanism_gate"][
    "c11_legal_collateral_contrast_present_each_row"
] is True
pattern = report["teacher_posterior_term_influence"][
    "expected_now_activation_pattern"
]
assert pattern["matches_expected_pattern"] is True
assert pattern["unexpected_zero_families"] == []
assert pattern["unexpected_nonzero_families"] == []
assert report["formal_run"] is False
assert report["validation_access"] is False
assert report["test_access"] is False
assert report["test_generated"] is False
print("HEALTH_REPORT_OK arrays_digest={}".format(report["arrays_digest"]))
print("HEALTH_REPORT_PROTOCOL={}".format(report["protocol_sha256"]))
PY
then
  cpmt_fail "health_report_validation_failed"
fi

printf "SERVER_STEP_BEGIN id=%s\n" "$CPMT_SERVER_STEP_ID"
printf "repo=%s\ncurrent_commit=%s\n" \
  "$CPMT_REPO_DIR" "$CPMT_CURRENT_COMMIT"
printf "read_boundary=%s_and_git_metadata\n" "$CPMT_HEALTH_REPORT"
printf "write_boundary=one_commit_containing_only_%s_then_origin_main\n" \
  "$CPMT_HEALTH_REPORT_REL"
printf "generation=false training=false validation_access=false test_access=false\n"

if git -C "$CPMT_REPO_DIR" ls-files --error-unmatch \
  "$CPMT_HEALTH_REPORT_REL" >/dev/null 2>&1; then
  CPMT_REMOTE_HEAD="$(git -C "$CPMT_REPO_DIR" ls-remote \
    origin refs/heads/main | awk '{print $1}')"
  [[ "$CPMT_REMOTE_HEAD" == "$CPMT_CURRENT_COMMIT" ]] || \
    cpmt_fail "tracked_report_but_remote_main_differs"
  printf "HEALTH_REPORT_COMMIT_REUSED commit=%s\n" "$CPMT_CURRENT_COMMIT"
  printf "SERVER_STEP_OK id=%s\n" "$CPMT_SERVER_STEP_ID"
  exit 0
fi

CPMT_UNTRACKED_COUNT=0
while IFS= read -r CPMT_UNTRACKED_PATH; do
  CPMT_UNTRACKED_COUNT=$((CPMT_UNTRACKED_COUNT + 1))
  [[ "$CPMT_UNTRACKED_PATH" == "$CPMT_HEALTH_REPORT_REL" ]] || \
    cpmt_fail "unexpected_untracked_path"
done < <(git -C "$CPMT_REPO_DIR" ls-files --others --exclude-standard)
[[ "$CPMT_UNTRACKED_COUNT" -eq 1 ]] || \
  cpmt_fail "health_report_is_not_the_only_untracked_file"

CPMT_REMOTE_BEFORE="$(git -C "$CPMT_REPO_DIR" ls-remote \
  origin refs/heads/main | awk '{print $1}')"
[[ "$CPMT_REMOTE_BEFORE" == "$CPMT_CURRENT_COMMIT" ]] || \
  cpmt_fail "origin_main_changed_before_publish"

git -C "$CPMT_REPO_DIR" add -- "$CPMT_HEALTH_REPORT_REL" || \
  cpmt_fail "git_add_failed"
mapfile -t CPMT_STAGED_PATHS < <(
  git -C "$CPMT_REPO_DIR" diff --cached --name-only
)
[[ "${#CPMT_STAGED_PATHS[@]}" -eq 1 \
   && "${CPMT_STAGED_PATHS[0]}" == "$CPMT_HEALTH_REPORT_REL" ]] || \
  cpmt_fail "staged_scope_is_not_exact_health_report"

git -C "$CPMT_REPO_DIR" commit \
  -m "record M1 v8 health benchmark" -- "$CPMT_HEALTH_REPORT_REL" || \
  cpmt_fail "git_commit_failed"
CPMT_PUBLISHED_COMMIT="$(git -C "$CPMT_REPO_DIR" rev-parse HEAD)" || \
  cpmt_fail "cannot_resolve_published_commit"
git -C "$CPMT_REPO_DIR" push origin HEAD:main || cpmt_fail "git_push_failed"
CPMT_REMOTE_AFTER="$(git -C "$CPMT_REPO_DIR" ls-remote \
  origin refs/heads/main | awk '{print $1}')"
[[ "$CPMT_REMOTE_AFTER" == "$CPMT_PUBLISHED_COMMIT" ]] || \
  cpmt_fail "remote_main_does_not_match_published_commit"

printf "HEALTH_REPORT_COMMIT=%s\n" "$CPMT_PUBLISHED_COMMIT"
printf "SERVER_STEP_OK id=%s\n" "$CPMT_SERVER_STEP_ID"
printf "NEXT=local_pull_and_review_exported_health_report\n"
