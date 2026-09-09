#!/usr/bin/env bash
# Unique phase: full tests for the isolated scope fix and v7/v9 data boundary.
# Foreground (expected minutes); show every result and also retain the log.
# Read code/configs, retained reports and existing synthetic test fixtures only.
# Write test logs/markers/tmp under a new source-bound AutoDL data-disk directory.
# No experiment training, new 1000/200-group generation, confirmation or test release.
# Matching success is reused; failed/interrupted attempts remain and never auto-restart.
set -uo pipefail
export CPMT_SERVER_STEP_ID="m1_v7_d051_scope_rebuild_full_test"
CPMT_EXPECTED_TESTS=280
CPMT_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
CPMT_REPO_DIR="$(git -C "$CPMT_SCRIPT_DIR" rev-parse --show-toplevel)" || exit 2
[[ "$#" -eq 0 ]] || exit 2
cd "$CPMT_REPO_DIR" || exit 2
[[ -d /root/autodl-tmp ]] || exit 2
[[ -z "$(git status --porcelain)" ]] || { printf 'SERVER_STEP_FAILED reason=checkout_not_clean\n'; exit 1; }
CPMT_SOURCE_SHORT="$(python -c 'import sys;sys.path.insert(0,"src");from cpmt.run_provenance import source_tree_sha256;from pathlib import Path;print(source_tree_sha256(Path.cwd(),roots=("src","scripts","configs","tests"))[:12])')" || exit 2
CPMT_OUTPUT_DIR="/root/autodl-tmp/cpmt_outputs/m1-v7-d051-full-test-$CPMT_SOURCE_SHORT"
mkdir -p "$CPMT_OUTPUT_DIR/tmp" || exit 2
export TMPDIR="$CPMT_OUTPUT_DIR/tmp"
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export CUDA_VISIBLE_DEVICES=""
export PYTHONUNBUFFERED=1
python - "$CPMT_OUTPUT_DIR" "$CPMT_EXPECTED_TESTS" <<'PY_TEST' 2>&1 | tee -a "$CPMT_OUTPUT_DIR/full_test.log"
import datetime,fcntl,os,sys,time,traceback,unittest
from pathlib import Path
sys.path.insert(0,'src')
from cpmt.m1_protocol import load_and_validate,protocol_sha256,validate_current_rollout_protocol
from cpmt.m1_s5_training import read_json,require,write_json
from cpmt.m1_scope_rebuild import validate_rebuild_test_marker
from cpmt.run_provenance import capture_run_provenance,source_tree_sha256

STAGE=os.environ['CPMT_SERVER_STEP_ID']

def main():
    root=Path.cwd();out=Path(sys.argv[1]);expected=int(sys.argv[2])
    plan=read_json(root/'configs/m1_scope_rebuild_plan.json')
    hard=load_and_validate(root/plan['corrected_source']['path'])
    validate_current_rollout_protocol(hard)
    require(protocol_sha256(hard)==plan['corrected_source']['protocol_sha256'],'corrected contract binding mismatch')
    provenance=capture_run_provenance(root,component=STAGE,entrypoint=root/'ops/run_next_server_step.sh')
    require(not provenance['git_dirty'],'checkout must be clean')
    marker_path=out/'full_test.ok.json'
    print('SERVER_STEP_BEGIN id='+STAGE+' commit='+provenance['git_commit'],flush=True)
    print('BOUNDARY corrected_protocol=v7 dataset=v9 experiment_generation=false confirmation=false test_access=false',flush=True)
    if marker_path.exists():
        marker=read_json(marker_path)
        validate_rebuild_test_marker(marker,root,plan,expected_tests=expected)
        print('FULL_TEST_REUSED tests='+str(marker['tests_run']),flush=True)
    else:
        require(not (out/'attempt.json').exists() and not list(out.glob('full_test.failed.*.json')),
                'previous failed/interrupted test attempt requires review; no automatic restart')
        before=source_tree_sha256(root,roots=('src','scripts','configs','tests'))
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        write_json(out/'attempt.json',{'stage':STAGE,'source_and_tests_sha256':before,'provenance':provenance})
        started=time.monotonic()
        try:
            import torch
            torch.set_num_threads(1)
            loader=unittest.TestLoader();suite=loader.discover('tests')
            require(not loader.errors and suite.countTestCases()==expected,
                    f'discovery mismatch actual={suite.countTestCases()} expected={expected} errors={loader.errors}')
            result=unittest.TextTestRunner(verbosity=2).run(suite)
            after=source_tree_sha256(root,roots=('src','scripts','configs','tests'))
            success=result.wasSuccessful() and not result.skipped and result.testsRun==expected and before==after
            marker={'schema_version':'cpmt-scope-rebuild-tests-v1','commit':provenance['git_commit'],
                    'corrected_protocol_sha256':protocol_sha256(hard),'rebuild_plan_sha256':protocol_sha256(plan),
                    'tests_run':result.testsRun,'expected_tests':expected,'exit_code':0 if success else 1,
                    'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
                    'wall_seconds':time.monotonic()-started,'source_and_tests_sha256':before,
                    'source_tree_unchanged':before==after,'test_access':False,
                    'validation_confirmation_run':False,'new_confirmation_groups_generated':False,
                    'fixture_access':'historical_small_train_validation_fixtures_and_retained_group78_snapshot',
                    'provenance':provenance,'failed_tests':[str(test) for test,_ in result.failures+result.errors]}
            destination=marker_path if success else out/('full_test.failed.'+stamp+'.json')
            write_json(destination,marker)
            print(f'FULL_TEST_RESULT tests={result.testsRun} exit={marker["exit_code"]} marker={destination}',flush=True)
            require(success,'full_test_failed; inspect displayed failures and retained marker')
            validate_rebuild_test_marker(marker,root,plan,expected_tests=expected)
        except BaseException as error:
            path=out/('full_test.failed.'+stamp+'.exception.json')
            write_json(path,{'type':type(error).__name__,'message':str(error),'traceback':traceback.format_exc(),
                             'source_and_tests_sha256':before,'provenance':provenance})
            raise
    print('FULL_TEST_MARKER='+str(marker_path),flush=True)
    print('SERVER_STEP_OK id='+STAGE,flush=True)
    print('NEXT=review_full_test_then_deliver_corrected_train_generation_separately',flush=True)

if __name__=='__main__':
    with (Path(sys.argv[1])/'full_test.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            main()
        except Exception as error:
            print('SERVER_STEP_FAILED id='+STAGE+' reason='+str(error),flush=True)
            raise
PY_TEST
CPMT_EXITS=("${PIPESTATUS[@]}")
printf 'FULL_TEST_EXIT=%s LOG_WRITE_EXIT=%s\n' "${CPMT_EXITS[0]}" "${CPMT_EXITS[1]}"
[[ "${CPMT_EXITS[0]}" -eq 0 && "${CPMT_EXITS[1]}" -eq 0 ]]
