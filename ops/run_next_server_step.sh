#!/usr/bin/env bash
# Unique phase: full tests for the D-049 selected-budget training/checkpoint entry.
# Inputs: clean checkout, accepted budget exports, frozen S5 training recipe.
# Read: repository JSON/code and synthetic unit-test fixtures only; no run arrays.
# Write: full-test log/markers and temporary fixtures on the AutoDL data disk.
# Resume: reuse a matching successful marker; retain every failed attempt.
# No training, data generation, validation confirmation, test release or export.
set -uo pipefail
CPMT_SERVER_STEP_ID="m1_v6_d049_s5_training_full_test"
CPMT_EXPECTED_TESTS=234
CPMT_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
CPMT_REPO_DIR="$(git -C "$CPMT_SCRIPT_DIR" rev-parse --show-toplevel)" || exit 2
CPMT_COMMIT_SHORT="$(git -C "$CPMT_REPO_DIR" rev-parse --short=7 HEAD)" || exit 2
CPMT_OUTPUT_DIR="/root/autodl-tmp/cpmt_outputs/m1-v6-d049-full-test-$CPMT_COMMIT_SHORT"
[[ "$#" -eq 0 ]] || exit 2
cd "$CPMT_REPO_DIR" || exit 2
[[ -z "$(git status --porcelain)" ]] || { printf 'SERVER_STEP_FAILED reason=checkout_not_clean\n'; exit 1; }
mkdir -p "$CPMT_OUTPUT_DIR/tmp" || exit 2
export TMPDIR="$CPMT_OUTPUT_DIR/tmp"
export OMP_NUM_THREADS=8
export MKL_NUM_THREADS=8
export PYTHONUNBUFFERED=1
python - "$CPMT_OUTPUT_DIR" "$CPMT_EXPECTED_TESTS" <<'PY' 2>&1 | tee -a "$CPMT_OUTPUT_DIR/full_test.log"
import datetime,fcntl,sys,time,unittest
from pathlib import Path
sys.path.insert(0,'src')
from cpmt.m1_protocol import load_and_validate,load_and_validate_endpoint_probe,protocol_sha256
from cpmt.m1_s5_training import load_plan,read_json,require,validate_test_marker,write_json
from cpmt.run_provenance import capture_run_provenance,source_tree_sha256

STAGE='m1_v6_d049_s5_training_full_test'

def main():
    root=Path.cwd();out=Path(sys.argv[1]);expected=int(sys.argv[2])
    hard=load_and_validate(root/'configs/m1_hard_condition.json')
    overlay=load_and_validate_endpoint_probe(root/'configs/m1_endpoint_viability_probe.json',hard)
    plan,registration=load_plan(root,hard,overlay)
    provenance=capture_run_provenance(root,component=STAGE,entrypoint=root/'ops/run_next_server_step.sh')
    require(provenance['git_dirty'] is False,'checkout must be clean')
    print('SERVER_STEP_BEGIN id='+STAGE+' commit='+provenance['git_commit'],flush=True)
    print('PLAN_BOUND models=60 train_groups=1000 validation_arrays_read=false test_access=false',flush=True)
    marker_path=out/'full_test.ok.json'
    if marker_path.exists():
        marker=read_json(marker_path);validate_test_marker(marker,root,plan)
        require(marker['expected_tests']==expected,'test-count mismatch')
        print('FULL_TEST_REUSED tests='+str(marker['tests_run']),flush=True)
    else:
        import torch
        torch.set_num_threads(8)
        before=source_tree_sha256(root,roots=('src','scripts','configs','tests'))
        started=time.monotonic()
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        print('FULL_TEST_ATTEMPT='+stamp,flush=True)
        loader=unittest.TestLoader();suite=loader.discover('tests')
        require(not loader.errors and suite.countTestCases()==expected,
                f'discovery mismatch actual={suite.countTestCases()} expected={expected} errors={loader.errors}')
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        after=source_tree_sha256(root,roots=('src','scripts','configs','tests'))
        success=result.wasSuccessful() and not result.skipped and result.testsRun==expected and before==after
        marker={'schema_version':'cpmt-d049-full-test-marker-v1','commit':provenance['git_commit'],
                'plan_sha256':protocol_sha256(plan),'registration_sha256':protocol_sha256(registration),
                'tests_run':result.testsRun,'expected_tests':expected,'exit_code':0 if success else 1,
                'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
                'wall_seconds':time.monotonic()-started,'source_and_tests_sha256':before,
                'source_tree_unchanged':before==after,'test_access':False,'formal_validation_arrays_read':False,
                'provenance':provenance,'failed_tests':[str(test) for test,_ in result.failures+result.errors]}
        destination=marker_path if success else out/('full_test.failed.'+stamp+'.json')
        write_json(destination,marker)
        print(f'FULL_TEST_RESULT tests={result.testsRun} exit={marker["exit_code"]} marker={destination}',flush=True)
        require(success,'full_test_failed; inspect retained failure marker')
        validate_test_marker(marker,root,plan)
    print('FULL_TEST_MARKER='+str(marker_path),flush=True)
    print('SERVER_STEP_OK id='+STAGE,flush=True)
    print('NEXT=deliver_selected_budget_training_as_a_separate_stage',flush=True)

if __name__=='__main__':
    with (Path(sys.argv[1])/'full_test.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            main()
        except Exception as error:
            print('SERVER_STEP_FAILED id='+STAGE+' reason='+str(error),flush=True)
            raise
PY
CPMT_EXITS=("${PIPESTATUS[@]}")
printf "FULL_TEST_EXIT=%s LOG_WRITE_EXIT=%s\n" "${CPMT_EXITS[0]}" "${CPMT_EXITS[1]}"
[[ "${CPMT_EXITS[0]}" -eq 0 && "${CPMT_EXITS[1]}" -eq 0 ]]
