#!/usr/bin/env bash
# Unique active CPMT server phase.
#
# Prerequisites:
# - run from a clean clone containing CPMT_REQUIRED_ANCESTOR;
# - use the repository's configured Python environment;
# - do not pass arguments.
#
# Read boundary: tracked repository source, config, and tests only.
# Write boundary: ignored outputs/m1-v5-server-preflight/<step-id>.* only.
# Resume policy: a marker matching this exact commit, protocol, dataset, and
# step id is accepted; otherwise the full test is run once and a new marker is
# written. This version does not generate arrays, train, export, or push.

set -uo pipefail

CPMT_SERVER_STEP_ID="m1_v5_v8_d041_full_test_audit_hardening"
CPMT_REQUIRED_ANCESTOR="5b21ef1ab380a681b8d3daa3a5a967285e41c194"
CPMT_EXPECTED_PROTOCOL="1af46e526e94fb0f186166bf2e34a16c61468e2e70fe583b602341eead994189"
CPMT_EXPECTED_DATASET="m1-paired-latent-worlds-v8-fixed-range-current-energy"

CPMT_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
CPMT_REPO_DIR="$(git -C "$CPMT_SCRIPT_DIR" rev-parse --show-toplevel)" || exit 2
CPMT_CURRENT_COMMIT="$(git -C "$CPMT_REPO_DIR" rev-parse HEAD)" || exit 2
CPMT_PREFLIGHT_DIR="$CPMT_REPO_DIR/outputs/m1-v5-server-preflight"
CPMT_TEST_LOG="$CPMT_PREFLIGHT_DIR/$CPMT_SERVER_STEP_ID.log"
CPMT_TEST_MARKER="$CPMT_PREFLIGHT_DIR/$CPMT_SERVER_STEP_ID.ok"

cpmt_fail() {
  local CPMT_FAILURE_MESSAGE="$1"
  printf "SERVER_STEP_FAILED id=%s reason=%s\n" \
    "$CPMT_SERVER_STEP_ID" "$CPMT_FAILURE_MESSAGE" >&2
  exit 1
}

[[ "$#" -eq 0 ]] || cpmt_fail "unexpected_arguments"
[[ -z "$(git -C "$CPMT_REPO_DIR" status --porcelain)" ]] || \
  cpmt_fail "working_tree_not_clean"
git -C "$CPMT_REPO_DIR" merge-base --is-ancestor \
  "$CPMT_REQUIRED_ANCESTOR" "$CPMT_CURRENT_COMMIT" || \
  cpmt_fail "required_protocol_commit_not_in_history"
command -v python >/dev/null 2>&1 || cpmt_fail "python_not_found"

printf "SERVER_STEP_BEGIN id=%s\n" "$CPMT_SERVER_STEP_ID"
printf "repo=%s\ncurrent_commit=%s\n" \
  "$CPMT_REPO_DIR" "$CPMT_CURRENT_COMMIT"
printf "prerequisite=clean_descendant_of_%s\n" "$CPMT_REQUIRED_ANCESTOR"
printf "read_boundary=tracked_source_config_tests\n"
printf "write_boundary=%s\n" "$CPMT_PREFLIGHT_DIR"
printf "test_access=false dataset=%s\n" "$CPMT_EXPECTED_DATASET"

if ! python - "$CPMT_REPO_DIR" "$CPMT_EXPECTED_PROTOCOL" \
  "$CPMT_EXPECTED_DATASET" <<'PY'
import sys
from pathlib import Path

repo = Path(sys.argv[1])
sys.path.insert(0, str(repo / "src"))
from cpmt.m1_protocol import load_and_validate, protocol_sha256

config = load_and_validate(repo / "configs" / "m1_hard_condition.json")
assert protocol_sha256(config) == sys.argv[2]
assert config["data"]["dataset_version"] == sys.argv[3]
assert config["status"] == "pretest_lock_candidate"
assert config["test_access"] is False
assert config["data"]["paired_groups"] == {
    "train": 1000, "validation": 200, "test": 200,
}
pattern = config["energy"]["posterior_influence_audit"][
    "expected_now_activation_pattern"
]
assert pattern["expected_nonzero_mean_tv_families"] == [
    "C01", "C02", "C04", "C06", "C07", "C08",
]
assert pattern["expected_zero_mean_tv_families"] == [
    "C00", "C03", "C05", "C09", "C10", "C11",
]
assert pattern["numerical_zero_tolerance"] == 1e-6
assert config["energy"]["posterior_influence_audit"][
    "no_execution_comparison"
].startswith("S1_reports_the_same_leave_current_out_posterior_metrics_for_E")
print("PROTOCOL_INPUT_OK sha256={}".format(sys.argv[2]))
PY
then
  cpmt_fail "protocol_validation_failed"
fi

mkdir -p "$CPMT_PREFLIGHT_DIR"

if [[ -f "$CPMT_TEST_MARKER" ]] \
  && grep -Fxq "status=ok" "$CPMT_TEST_MARKER" \
  && grep -Fxq "step_id=$CPMT_SERVER_STEP_ID" "$CPMT_TEST_MARKER" \
  && grep -Fxq "commit=$CPMT_CURRENT_COMMIT" "$CPMT_TEST_MARKER" \
  && grep -Fxq "protocol=$CPMT_EXPECTED_PROTOCOL" "$CPMT_TEST_MARKER" \
  && grep -Fxq "dataset=$CPMT_EXPECTED_DATASET" "$CPMT_TEST_MARKER"; then
  printf "FULL_TEST_REUSED marker=%s\n" "$CPMT_TEST_MARKER"
  printf "SERVER_STEP_OK id=%s\n" "$CPMT_SERVER_STEP_ID"
  exit 0
fi

(
  cd "$CPMT_REPO_DIR" || exit 2
  python -m unittest discover -s tests -p 'test_*.py'
) 2>&1 | tee "$CPMT_TEST_LOG"
CPMT_TEST_EXIT="${PIPESTATUS[0]}"
printf "FULL_TEST_EXIT=%s\n" "$CPMT_TEST_EXIT"
[[ "$CPMT_TEST_EXIT" -eq 0 ]] || cpmt_fail "full_test_failed"

{
  printf "status=ok\n"
  printf "step_id=%s\n" "$CPMT_SERVER_STEP_ID"
  printf "commit=%s\n" "$CPMT_CURRENT_COMMIT"
  printf "protocol=%s\n" "$CPMT_EXPECTED_PROTOCOL"
  printf "dataset=%s\n" "$CPMT_EXPECTED_DATASET"
} > "$CPMT_TEST_MARKER"

printf "FULL_TEST_LOG=%s\n" "$CPMT_TEST_LOG"
printf "FULL_TEST_MARKER=%s\n" "$CPMT_TEST_MARKER"
printf "SERVER_STEP_OK id=%s\n" "$CPMT_SERVER_STEP_ID"
printf "NEXT=wait_for_a_new_commit_that_rewrites_this_entry_for_health_benchmark\n"
