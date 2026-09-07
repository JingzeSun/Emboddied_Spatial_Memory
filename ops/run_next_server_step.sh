#!/usr/bin/env bash
# Unique active CPMT server phase: validate the D-042 budget contract/runner.
#
# Prerequisites:
# - origin/main and the clean server checkout point to this handoff commit;
# - the history contains CPMT_PREREQUISITE_COMMIT, whose v8 health passed;
# - no validation/test arrays are needed or read.
#
# Read boundary: tracked source, scripts, configs, tests and Git metadata.
# Write boundary: one ignored outputs directory containing the full-test log
# and a commit/protocol-bound success marker.
# Resume policy: reuse only a marker whose commit, protocol and test count all
# match this checkout. This stage does not generate data, train, run causal
# evaluation, read validation/test, export results, or modify Git.

set -uo pipefail

CPMT_SERVER_STEP_ID="m1_v5_v8_d042_budget_contract_full_test"
CPMT_PREREQUISITE_COMMIT="1de500d292ff90bcee889221203269df43c3515d"
CPMT_EXPECTED_PROTOCOL="876709e3c5796cd3462e01d3706abef825073336b51d1dca538b13ee2f3b7e6a"
CPMT_EXPECTED_DATASET="m1-paired-latent-worlds-v8-fixed-range-current-energy"
CPMT_EXPECTED_TESTS="181"

CPMT_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
CPMT_REPO_DIR="$(git -C "$CPMT_SCRIPT_DIR" rev-parse --show-toplevel)" || exit 2
CPMT_CURRENT_COMMIT="$(git -C "$CPMT_REPO_DIR" rev-parse HEAD)" || exit 2
CPMT_SHORT_COMMIT="$(git -C "$CPMT_REPO_DIR" rev-parse --short=7 HEAD)" || exit 2
CPMT_RUN_DIR="$CPMT_REPO_DIR/outputs/m1-v5-v8-d042-full-test-$CPMT_SHORT_COMMIT"
CPMT_TEST_LOG="$CPMT_RUN_DIR/full_test.log"
CPMT_OK_MARKER="$CPMT_RUN_DIR/full_test.ok.json"

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
  "$CPMT_PREREQUISITE_COMMIT" "$CPMT_CURRENT_COMMIT" || \
  cpmt_fail "v8_health_review_prerequisite_missing"
git -C "$CPMT_REPO_DIR" diff --quiet || cpmt_fail "tracked_changes_present"
git -C "$CPMT_REPO_DIR" diff --cached --quiet || \
  cpmt_fail "staged_changes_present"
[[ -z "$(git -C "$CPMT_REPO_DIR" ls-files --others --exclude-standard)" ]] || \
  cpmt_fail "untracked_files_present"
CPMT_REMOTE_HEAD="$(git -C "$CPMT_REPO_DIR" ls-remote \
  origin refs/heads/main | awk '{print $1}')"
[[ "$CPMT_REMOTE_HEAD" == "$CPMT_CURRENT_COMMIT" ]] || \
  cpmt_fail "origin_main_does_not_match_checkout"

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

printf "SERVER_STEP_BEGIN id=%s\n" "$CPMT_SERVER_STEP_ID"
printf "repo=%s\ncurrent_commit=%s\n" \
  "$CPMT_REPO_DIR" "$CPMT_CURRENT_COMMIT"
printf "protocol_sha256=%s dataset=%s\n" \
  "$CPMT_PROTOCOL" "$CPMT_EXPECTED_DATASET"
printf "read_boundary=tracked_source_scripts_configs_tests_and_git_metadata\n"
printf "write_boundary=%s\n" "$CPMT_RUN_DIR"
printf "generation=false training=false validation_access=false test_access=false\n"

if [[ -f "$CPMT_OK_MARKER" ]]; then
  python - \
    "$CPMT_OK_MARKER" "$CPMT_CURRENT_COMMIT" "$CPMT_PROTOCOL" \
    "$CPMT_EXPECTED_DATASET" "$CPMT_EXPECTED_TESTS" <<'PY' || \
    cpmt_fail "existing_marker_validation_failed"
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
print("FULL_TEST_REUSED tests={}".format(marker["tests"]))
PY
  printf "SERVER_STEP_OK id=%s\n" "$CPMT_SERVER_STEP_ID"
  printf "NEXT=rewrite_entry_for_1000_group_train_generation\n"
  exit 0
fi

mkdir -p "$CPMT_RUN_DIR" || cpmt_fail "cannot_create_run_directory"
(
  cd "$CPMT_REPO_DIR" || exit 2
  python -m unittest discover -s tests -p 'test_*.py'
) 2>&1 | tee "$CPMT_TEST_LOG"
CPMT_TEST_EXIT=${PIPESTATUS[0]}
printf "FULL_TEST_EXIT=%s\n" "$CPMT_TEST_EXIT"
[[ "$CPMT_TEST_EXIT" -eq 0 ]] || cpmt_fail "full_test_failed"
CPMT_TEST_COUNT="$(sed -nE \
  's/^Ran ([0-9]+) tests.*/\1/p' "$CPMT_TEST_LOG" | tail -n 1)"
[[ "$CPMT_TEST_COUNT" == "$CPMT_EXPECTED_TESTS" ]] || \
  cpmt_fail "unexpected_test_count"

python - \
  "$CPMT_OK_MARKER" "$CPMT_CURRENT_COMMIT" "$CPMT_PROTOCOL" \
  "$CPMT_EXPECTED_DATASET" "$CPMT_TEST_COUNT" <<'PY' || \
  cpmt_fail "cannot_write_success_marker"
import json
import sys
from pathlib import Path

payload = {
    "commit": sys.argv[2],
    "dataset_version": sys.argv[4],
    "exit_code": 0,
    "protocol_sha256": sys.argv[3],
    "tests": int(sys.argv[5]),
}
Path(sys.argv[1]).write_text(
    json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8",
)
PY

printf "FULL_TEST_LOG=%s\n" "$CPMT_TEST_LOG"
printf "FULL_TEST_MARKER=%s\n" "$CPMT_OK_MARKER"
printf "SERVER_STEP_OK id=%s\n" "$CPMT_SERVER_STEP_ID"
printf "NEXT=rewrite_entry_for_1000_group_train_generation\n"
