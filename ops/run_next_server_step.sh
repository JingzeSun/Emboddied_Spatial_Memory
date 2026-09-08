#!/usr/bin/env bash
# Unique active phase: validate D-048 registration and the complete test suite.
# Inputs: clean synced checkout, pinned scientific commit and exported D-047 report.
# Read: repository/tests only; no existing train/validation/test arrays.
# Write: this phase's log/markers and temporary unit-test fixtures on the data disk.
# Resume: reuse a matching success marker; preserve failed logs; never rerun the probe.
set -uo pipefail
CPMT_SERVER_STEP_ID="m1_v6_d048_registration_boundary_full_test"
CPMT_EXPECTED_SCIENCE_COMMIT="c94fc1f45aff6de5993d159657e24a8f8fd9e02d"
CPMT_EXPECTED_REGISTRATION="d366935b14975a18cf3e0af58833fcb8a1151c5929c8848d40677d692fd51e1d"
CPMT_EXPECTED_TESTS=221
CPMT_DATA_ROOT="/root/autodl-tmp"
CPMT_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
CPMT_REPO_DIR="$(git -C "$CPMT_SCRIPT_DIR" rev-parse --show-toplevel)" || exit 2
CPMT_CURRENT_COMMIT="$(git -C "$CPMT_REPO_DIR" rev-parse HEAD)" || exit 2
CPMT_COMMIT_SHORT="$(git -C "$CPMT_REPO_DIR" rev-parse --short=7 HEAD)" || exit 2
CPMT_OUTPUT_DIR="$CPMT_DATA_ROOT/cpmt_outputs/m1-v6-d048-full-test-$CPMT_COMMIT_SHORT"
CPMT_MARKER="$CPMT_OUTPUT_DIR/full_test.ok.json"
cpmt_fail() { printf "SERVER_STEP_FAILED id=%s reason=%s\n" "$CPMT_SERVER_STEP_ID" "$1" >&2; exit 1; }
[[ "$#" -eq 0 ]] || cpmt_fail unexpected_arguments
command -v python >/dev/null 2>&1 || cpmt_fail python_not_found
git -C "$CPMT_REPO_DIR" diff --quiet || cpmt_fail tracked_changes_present
git -C "$CPMT_REPO_DIR" diff --cached --quiet || cpmt_fail staged_changes_present
[[ -z "$(git -C "$CPMT_REPO_DIR" ls-files --others --exclude-standard)" ]] || cpmt_fail untracked_files_present
CPMT_REMOTE_HEAD="$(git -C "$CPMT_REPO_DIR" ls-remote origin refs/heads/main | awk '{print $1}')"
[[ "$CPMT_REMOTE_HEAD" == "$CPMT_CURRENT_COMMIT" ]] || cpmt_fail origin_main_does_not_match_checkout
git -C "$CPMT_REPO_DIR" merge-base --is-ancestor "$CPMT_EXPECTED_SCIENCE_COMMIT" HEAD || cpmt_fail scientific_commit_missing
git -C "$CPMT_REPO_DIR" diff --quiet "$CPMT_EXPECTED_SCIENCE_COMMIT" HEAD -- src scripts configs tests || cpmt_fail scientific_tree_changed
[[ -d "$CPMT_DATA_ROOT" ]] || cpmt_fail data_disk_missing
mkdir -p "$CPMT_OUTPUT_DIR/tmp" || cpmt_fail output_directory_creation_failed
export TMPDIR="$CPMT_OUTPUT_DIR/tmp"
export OMP_NUM_THREADS=8
export MKL_NUM_THREADS=8
export PYTHONUNBUFFERED=1
cd "$CPMT_REPO_DIR" || cpmt_fail repository_unavailable
printf "SERVER_STEP_BEGIN id=%s\nrepo=%s\ncommit=%s\n" "$CPMT_SERVER_STEP_ID" "$CPMT_REPO_DIR" "$CPMT_CURRENT_COMMIT"
printf "read_boundary=repository_and_unit_test_fixtures_only\nwrite_boundary=%s\nformal_validation_arrays_read=false test_access=false\n" "$CPMT_OUTPUT_DIR"
python scripts/validate_m1_protocol.py > "$CPMT_OUTPUT_DIR/protocol_validation.json" || cpmt_fail registration_validation_failed
python - "$CPMT_OUTPUT_DIR/protocol_validation.json" "$CPMT_EXPECTED_REGISTRATION" <<'PY' || cpmt_fail registration_binding_failed
import json,sys
from pathlib import Path
r=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
assert r['post_probe_registration_sha256']==sys.argv[2]
assert r['evaluation_plan']['paired_groups']['test']==1350 and r['test_access'] is False and r['test_release_authorized'] is False
print('POST_PROBE_REGISTRATION_OK exact=true planned_test_groups=1350 test_access=false')
PY
if [[ -f "$CPMT_MARKER" ]]; then
  python - "$CPMT_MARKER" "$CPMT_CURRENT_COMMIT" "$CPMT_EXPECTED_REGISTRATION" "$CPMT_EXPECTED_TESTS" <<'PY' || cpmt_fail existing_full_test_marker_mismatch
import json,sys
from pathlib import Path
sys.path.insert(0,'src')
from cpmt.run_provenance import source_tree_sha256
m=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
assert m['schema_version']=='cpmt-d048-full-test-marker-v1' and m['commit']==sys.argv[2]
assert m['registration_sha256']==sys.argv[3] and m['tests_run']==int(sys.argv[4]) and m['exit_code']==0
assert m['source_and_tests_sha256']==source_tree_sha256(Path.cwd(),roots=('src','scripts','configs','tests'))
assert m['test_access'] is False and m['formal_validation_arrays_read'] is False
print(f"FULL_TEST_REUSED tests={m['tests_run']}")
PY
else
  python - "$CPMT_OUTPUT_DIR" "$CPMT_CURRENT_COMMIT" "$CPMT_EXPECTED_REGISTRATION" "$CPMT_EXPECTED_TESTS" <<'PY' 2>&1 | tee -a "$CPMT_OUTPUT_DIR/full_test.log"
import datetime,json,sys,time,unittest
from pathlib import Path
import torch
sys.path.insert(0,'src')
from cpmt.run_provenance import capture_run_provenance,source_tree_sha256
torch.set_num_threads(8)
root=Path.cwd(); out=Path(sys.argv[1]); expected=int(sys.argv[4])
started=time.monotonic(); stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
print(f'FULL_TEST_ATTEMPT={stamp}',flush=True)
provenance=capture_run_provenance(root,component='d048_registration_boundary_full_test',entrypoint=root/'ops/run_next_server_step.sh')
loader=unittest.TestLoader(); suite=loader.discover('tests')
if loader.errors or suite.countTestCases()!=expected:
    raise RuntimeError(f'test discovery mismatch: {suite.countTestCases()} expected {expected}; {loader.errors}')
result=unittest.TextTestRunner(verbosity=2).run(suite)
code=0 if result.wasSuccessful() and result.testsRun==expected else 1
marker={'schema_version':'cpmt-d048-full-test-marker-v1','commit':sys.argv[2],
        'registration_sha256':sys.argv[3],'tests_run':result.testsRun,'exit_code':code,
        'skipped':len(result.skipped),'failures':len(result.failures),'errors':len(result.errors),
        'elapsed_seconds':time.monotonic()-started,'attempt':stamp,
        'source_and_tests_sha256':source_tree_sha256(root,roots=('src','scripts','configs','tests')),
        'provenance':provenance,'formal_validation_arrays_read':False,'test_access':False}
name='full_test.ok.json' if code==0 else f'full_test.failed.{stamp}.json'
(out/name).write_text(json.dumps(marker,indent=2)+'\n',encoding='utf-8')
print(f"FULL_TEST_RESULT tests={result.testsRun} exit={code} marker={out/name}",flush=True)
sys.exit(code)
PY
  CPMT_PIPE_EXITS=("${PIPESTATUS[@]}")
  printf "FULL_TEST_EXIT=%s LOG_WRITE_EXIT=%s\n" "${CPMT_PIPE_EXITS[0]}" "${CPMT_PIPE_EXITS[1]}"
  [[ "${CPMT_PIPE_EXITS[0]}" -eq 0 && "${CPMT_PIPE_EXITS[1]}" -eq 0 ]] || cpmt_fail full_test_failed
fi
printf "FULL_TEST_MARKER=%s\nSERVER_STEP_OK id=%s\n" "$CPMT_MARKER" "$CPMT_SERVER_STEP_ID"
printf "NEXT=review_full_test_marker_before_a_separate_train_inner_dev_budget_stage\n"
