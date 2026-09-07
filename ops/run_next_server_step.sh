#!/usr/bin/env bash
# Unique active CPMT server phase: full test of accepted D-044--D-046.
#
# Prerequisites: clean checkout synchronized with origin/main; Python environment
# already configured. Read boundary: tracked source/config/docs/tests and Git
# metadata. Write boundary: one ignored outputs directory containing the test log
# and success marker. Resume policy: a marker is reused only when commit, protocol,
# dataset, probe config hash and test count all match. This stage does not generate
# arrays, train, select an endpoint, evaluate causal metrics, or read validation/test.

set -uo pipefail

CPMT_SERVER_STEP_ID="m1_v6_v8_d046_persistent_auc_full_test"
CPMT_EXPECTED_PROTOCOL="73666cabb77b4884302d77ca621669bfdc77e86a44951b8a92b97208509c0eec"
CPMT_EXPECTED_DATASET="m1-paired-latent-worlds-v8-fixed-range-current-energy"
CPMT_PROBE_CONFIG="configs/m1_endpoint_viability_probe.json"

CPMT_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
CPMT_REPO_DIR="$(git -C "$CPMT_SCRIPT_DIR" rev-parse --show-toplevel)" || exit 2
CPMT_CURRENT_COMMIT="$(git -C "$CPMT_REPO_DIR" rev-parse HEAD)" || exit 2
CPMT_COMMIT_SHORT="$(git -C "$CPMT_REPO_DIR" rev-parse --short=7 HEAD)" || exit 2
CPMT_OUTPUT_DIR="$CPMT_REPO_DIR/outputs/m1-v6-v8-d046-full-test-$CPMT_COMMIT_SHORT"
CPMT_TEST_LOG="$CPMT_OUTPUT_DIR/full_test.log"
CPMT_TEST_MARKER="$CPMT_OUTPUT_DIR/full_test.ok.json"

cpmt_fail() {
  local CPMT_FAILURE_MESSAGE="$1"
  printf "SERVER_STEP_FAILED id=%s reason=%s\n" \
    "$CPMT_SERVER_STEP_ID" "$CPMT_FAILURE_MESSAGE" >&2
  exit 1
}

[[ "$#" -eq 0 ]] || cpmt_fail "unexpected_arguments"
command -v python >/dev/null 2>&1 || cpmt_fail "python_not_found"
command -v git >/dev/null 2>&1 || cpmt_fail "git_not_found"
git -C "$CPMT_REPO_DIR" diff --quiet || cpmt_fail "tracked_changes_present"
git -C "$CPMT_REPO_DIR" diff --cached --quiet || \
  cpmt_fail "staged_changes_present"
[[ -z "$(git -C "$CPMT_REPO_DIR" ls-files --others --exclude-standard)" ]] || \
  cpmt_fail "untracked_files_present"
CPMT_REMOTE_HEAD="$(git -C "$CPMT_REPO_DIR" ls-remote \
  origin refs/heads/main | awk '{print $1}')"
[[ "$CPMT_REMOTE_HEAD" == "$CPMT_CURRENT_COMMIT" ]] || \
  cpmt_fail "origin_main_does_not_match_checkout"

mkdir -p "$CPMT_OUTPUT_DIR" || cpmt_fail "output_directory_creation_failed"
CPMT_PROBE_SHA256="$(python - "$CPMT_REPO_DIR/$CPMT_PROBE_CONFIG" <<'PY'
import hashlib
import sys
from pathlib import Path
print(hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest())
PY
)" || cpmt_fail "probe_config_hash_failed"

printf "SERVER_STEP_BEGIN id=%s\n" "$CPMT_SERVER_STEP_ID"
printf "repo=%s\ncurrent_commit=%s\n" "$CPMT_REPO_DIR" "$CPMT_CURRENT_COMMIT"
printf "protocol_sha256=%s dataset=%s\n" \
  "$CPMT_EXPECTED_PROTOCOL" "$CPMT_EXPECTED_DATASET"
printf "probe_config=%s probe_config_sha256=%s\n" \
  "$CPMT_PROBE_CONFIG" "$CPMT_PROBE_SHA256"
printf "read_boundary=tracked_source_config_docs_tests_and_git_metadata\n"
printf "write_boundary=%s\n" "$CPMT_OUTPUT_DIR"
printf "generation=false training=false selection=false scientific_metrics=false validation_access=false test_access=false\n"

if [[ -f "$CPMT_TEST_MARKER" ]]; then
  python - "$CPMT_TEST_MARKER" "$CPMT_CURRENT_COMMIT" \
    "$CPMT_EXPECTED_PROTOCOL" "$CPMT_EXPECTED_DATASET" \
    "$CPMT_PROBE_SHA256" <<'PY' || cpmt_fail "existing_marker_mismatch"
import json
import sys
from pathlib import Path
marker = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert marker["schema_version"] == "cpmt-full-test-marker-v1"
assert marker["commit"] == sys.argv[2]
assert marker["protocol_sha256"] == sys.argv[3]
assert marker["dataset_version"] == sys.argv[4]
assert marker["probe_config_sha256"] == sys.argv[5]
assert marker["exit_code"] == 0
assert marker["tests_run"] >= 210
print("FULL_TEST_MARKER_REUSED tests={}".format(marker["tests_run"]))
PY
else
  (
    cd "$CPMT_REPO_DIR" || exit 2
    python -m unittest discover -s tests -p 'test_*.py'
  ) 2>&1 | tee "$CPMT_TEST_LOG"
  CPMT_TEST_EXIT=${PIPESTATUS[0]}
  printf "FULL_TEST_EXIT=%s\n" "$CPMT_TEST_EXIT"
  [[ "$CPMT_TEST_EXIT" -eq 0 ]] || cpmt_fail "full_test_failed"
  CPMT_TEST_COUNT="$(python - "$CPMT_TEST_LOG" <<'PY'
import re
import sys
from pathlib import Path
text = Path(sys.argv[1]).read_text(encoding="utf-8")
matches = re.findall(r"Ran (\d+) tests? in", text)
assert len(matches) == 1
print(matches[0])
PY
)" || cpmt_fail "test_count_parse_failed"
  [[ "$CPMT_TEST_COUNT" -ge 210 ]] || cpmt_fail "unexpected_test_count"
  python - "$CPMT_TEST_MARKER" "$CPMT_CURRENT_COMMIT" \
    "$CPMT_EXPECTED_PROTOCOL" "$CPMT_EXPECTED_DATASET" \
    "$CPMT_PROBE_SHA256" "$CPMT_TEST_COUNT" <<'PY' || \
    cpmt_fail "marker_write_failed"
import json
import sys
from pathlib import Path
path = Path(sys.argv[1])
payload = {
    "schema_version": "cpmt-full-test-marker-v1",
    "stage": "m1_v6_v8_d046_persistent_auc_full_test",
    "commit": sys.argv[2],
    "protocol_sha256": sys.argv[3],
    "dataset_version": sys.argv[4],
    "probe_config_sha256": sys.argv[5],
    "tests_run": int(sys.argv[6]),
    "exit_code": 0,
    "generation": False,
    "training": False,
    "selection": False,
    "scientific_metrics": False,
    "validation_access": False,
    "test_access": False,
}
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
fi

printf "FULL_TEST_LOG=%s\n" "$CPMT_TEST_LOG"
printf "FULL_TEST_MARKER=%s\n" "$CPMT_TEST_MARKER"
printf "SERVER_STEP_OK id=%s\n" "$CPMT_SERVER_STEP_ID"
printf "NEXT=rewrite_entry_for_fixed_train_only_d044_d046_endpoint_probe\n"
