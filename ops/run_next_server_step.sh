#!/usr/bin/env bash
# Unique phase: selected-budget S5 preparation, train and save both registered arms.
# Inputs: D-049 234-test success + accepted budget exports + existing 1000-group train.
# Read: train/manifest and frozen contracts only; no validation/test or new grid.
# Write: this phase's model artifacts, training manifest, logs and exit markers.
# Resume: nohup + lock prevents duplicate launch; verify completed models by hash.
# Failed/interrupted attempts stay on disk and require review, never auto-retrain.
set -uo pipefail
export CPMT_SERVER_STEP_ID="m1_v6_d049_s5_selected_training"
CPMT_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
export CPMT_REPO_DIR="$(git -C "$CPMT_SCRIPT_DIR" rev-parse --show-toplevel)" || exit 2
export CPMT_CURRENT_COMMIT="$(git -C "$CPMT_REPO_DIR" rev-parse HEAD)" || exit 2
CPMT_COMMON_GIT_DIR="$(git -C "$CPMT_REPO_DIR" rev-parse --path-format=absolute --git-common-dir)" || exit 2
CPMT_MAIN_REPO_DIR="$(cd -- "$CPMT_COMMON_GIT_DIR/.." && pwd -P)" || exit 2
export CPMT_TRAIN="$CPMT_MAIN_REPO_DIR/outputs/m1-v6-v8-d043-train-g1000-53539ce/train.npz"
export CPMT_OUTPUT_DIR="/root/autodl-tmp/cpmt_outputs/m1-v6-d049-s5-selected-training"
export CPMT_FULL_TEST_MARKER="/root/autodl-tmp/cpmt_outputs/m1-v6-d049-full-test-c6d7644/full_test.ok.json"
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=8
export MKL_NUM_THREADS=8
cpmt_fail() { printf "SERVER_STEP_FAILED id=%s reason=%s\nLOG=%s/training.log\n" "$CPMT_SERVER_STEP_ID" "$1" "$CPMT_OUTPUT_DIR" >&2; exit 1; }
[[ "$#" -eq 0 ]] || cpmt_fail unexpected_arguments
cd "$CPMT_REPO_DIR" || cpmt_fail repository_unavailable

cpmt_check_prerequisites() {
  [[ -z "$(git status --porcelain)" ]] || return 1
  python - <<'PY_CHECK'
import os,sys
from pathlib import Path
sys.path.insert(0,'src')
from cpmt.m1_protocol import load_and_validate,load_and_validate_endpoint_probe,protocol_sha256
from cpmt.m1_s5_training import load_plan,read_json,require,validate_test_marker
root=Path.cwd();env=os.environ
hard=load_and_validate(root/'configs/m1_hard_condition.json')
overlay=load_and_validate_endpoint_probe(root/'configs/m1_endpoint_viability_probe.json',hard)
plan,registration=load_plan(root,hard,overlay)
marker=read_json(Path(env['CPMT_FULL_TEST_MARKER']));validate_test_marker(marker,root,plan)
require(marker['commit']=='c6d76441a5ca2181d593d03d47342d63e3cc3f06' and marker['tests_run']==234,'wrong verified test run')
train=Path(env['CPMT_TRAIN']);require(train.is_file(),'existing train arrays not found')
manifest=read_json(train.with_suffix('.manifest.json'))
require(manifest['arrays_digest']==plan['train_arrays_digest'],'train manifest digest mismatch')
require(manifest['protocol_sha256']==protocol_sha256(hard) and manifest['split']=='train','train source/split mismatch')
require(manifest['teacher_health_gate']['pass'] is True,'train health prerequisite failed')
started=Path(env['CPMT_OUTPUT_DIR'])/'started.json'
if started.exists():
    previous=read_json(started)
    require(previous['commit']==env['CPMT_CURRENT_COMMIT'] and previous['stage']==env['CPMT_SERVER_STEP_ID'],'keep original training checkout unchanged')
print('FULL_TEST_AND_PLAN_PREREQUISITES_OK tests=234 models=60 train_groups=1000 validation_arrays_read=false test_access=false',flush=True)
print('TRAIN_INPUT='+str(train.resolve()),flush=True)
PY_CHECK
}

cpmt_finish_report() {
  python - <<'PY_FINISH'
import os,sys
from pathlib import Path
sys.path.insert(0,'src')
from cpmt.m1_protocol import protocol_sha256
from cpmt.m1_s5_training import component_spec,read_json,require,validate_artifact,write_json
from cpmt.run_provenance import file_sha256,source_tree_sha256
root=Path.cwd();env=os.environ;out=Path(env['CPMT_OUTPUT_DIR'])
require((out/'runner_exit.txt').read_text().strip()=='0','training runner did not complete successfully')
plan=read_json(root/'configs/m1_s5_training_plan.json');report_path=out/'training_manifest.json';report=read_json(report_path)
started=read_json(out/'started.json')
require(started['stage']==env['CPMT_SERVER_STEP_ID'] and started['commit']==env['CPMT_CURRENT_COMMIT'],'start record mismatch')
require(report['schema_version']=='cpmt-s5-training-manifest-v1' and report['status']=='complete','training manifest incomplete')
require(report['plan']==plan,'training recipe drift')
require(all(report[k] is False for k in ('formal_run','validation_arrays_read','test_access','causal_complete','model_selection_performed')),'training access/selection mismatch')
binding=report['binding']
require(binding['plan_sha256']==protocol_sha256(plan) and binding['registration_sha256']==plan['post_probe_registration_sha256'],'training binding mismatch')
require(binding['source_tree_sha256']==source_tree_sha256(root),'scientific source changed during training')
require(binding['train_arrays_digest']==plan['train_arrays_digest']==report['input_arrays']['train']['arrays_digest'],'train data mismatch')
require(report['test_marker_sha256']==file_sha256(Path(env['CPMT_FULL_TEST_MARKER'])),'full test evidence changed')
require(len(report['training_group_ids'])==len(set(report['training_group_ids']))==1000 and report['training_rows']==40000,'wrong training population')
require(report['label_mask_reused'] is True,'label mask was resampled')
require(report['training_provenance']['git_commit']==env['CPMT_CURRENT_COMMIT'] and report['training_provenance']['git_dirty'] is False,'training provenance mismatch')
expected={}
for architecture,arm in plan['arms'].items():
    for seed in plan['seeds']:
        for method in ['outcome_scorer',*arm['selected']['student_hyperparameters_by_method']]:
            key=f'{architecture}/seed_{seed}/{method}'
            expected[key]=component_spec(plan,architecture,seed,method)
require(set(report['models'])==set(expected) and len(expected)==60,'missing or extra model artifacts')
for key,component in expected.items():
    path=out/'models'/key;row=report['models'][key]
    require(Path(row['path']).resolve()==path.resolve(),'unexpected model path')
    artifact=validate_artifact(path,binding,component)
    require(row['component']==component and row['model_sha256']==artifact['model_sha256'] and row['training']==artifact['training'],'model manifest mismatch')
    provenance=artifact['training']['training_provenance']
    require(provenance['git_dirty'] is False and provenance['source_tree_sha256']==binding['source_tree_sha256'],'model provenance mismatch')
marker={'schema_version':'cpmt-d049-s5-training-marker-v1','stage':env['CPMT_SERVER_STEP_ID'],
        'commit':env['CPMT_CURRENT_COMMIT'],'plan_sha256':protocol_sha256(plan),
        'training_manifest_sha256':file_sha256(report_path),'models':60,'runner_exit_code':0,
        'validation_arrays_read':False,'test_access':False,'causal_complete':False}
marker_path=out/'training.ok.json'
if marker_path.exists():
    require(read_json(marker_path)==marker,'existing success marker mismatch')
else:
    write_json(marker_path,marker)
print('TRAINING_ARTIFACTS_VERIFIED models=60',flush=True)
print('TRAINING_MANIFEST='+str(report_path),flush=True)
PY_FINISH
}

if [[ "${CPMT_S5_WORKER:-0}" == "1" ]]; then
  trap 'CPMT_WORKER_EXIT=$?; printf "%s\n" "$CPMT_WORKER_EXIT" > "$CPMT_OUTPUT_DIR/worker_exit.txt"' EXIT
  cpmt_check_prerequisites || cpmt_fail prerequisites_changed
  printf "TRAINING_RUN_BEGIN models=60 arms=2 seeds=5\n"
  python scripts/run_m1_s5_train.py --train "$CPMT_TRAIN" --out-dir "$CPMT_OUTPUT_DIR" --test-marker "$CPMT_FULL_TEST_MARKER"
  CPMT_RUN_EXIT=$?
  printf "%s\n" "$CPMT_RUN_EXIT" > "$CPMT_OUTPUT_DIR/runner_exit.txt"
  printf "TRAINING_RUN_EXIT=%s\n" "$CPMT_RUN_EXIT"
  [[ "$CPMT_RUN_EXIT" -eq 0 ]] || cpmt_fail training_failed_requires_review
  cpmt_check_prerequisites || cpmt_fail provenance_changed_after_training
  cpmt_finish_report || cpmt_fail model_acceptance_failed_requires_review
  printf "SERVER_STEP_OK id=%s models=60\nNEXT=separate_S5_confirmation_preparation\n" "$CPMT_SERVER_STEP_ID"
  exit 0
fi

command -v flock >/dev/null 2>&1 || cpmt_fail flock_missing
command -v nohup >/dev/null 2>&1 || cpmt_fail nohup_missing
[[ -d /root/autodl-tmp ]] || cpmt_fail data_disk_missing
mkdir -p "$CPMT_OUTPUT_DIR" || cpmt_fail output_directory_creation_failed
exec 9>"$CPMT_OUTPUT_DIR/worker.lock"
if ! flock -n 9; then
  printf "SERVER_STEP_RUNNING id=%s\nLOG=%s/training.log\n" "$CPMT_SERVER_STEP_ID" "$CPMT_OUTPUT_DIR"
  [[ ! -f "$CPMT_OUTPUT_DIR/training.log" ]] || tail -n 8 "$CPMT_OUTPUT_DIR/training.log"
  exit 0
fi
cpmt_check_prerequisites || cpmt_fail full_test_or_train_prerequisite_failed
if [[ -f "$CPMT_OUTPUT_DIR/runner_exit.txt" || -f "$CPMT_OUTPUT_DIR/training.ok.json" ]]; then
  cpmt_finish_report || cpmt_fail previous_attempt_requires_review_no_automatic_restart
  printf "SERVER_STEP_OK id=%s models=60\nNEXT=separate_S5_confirmation_preparation\n" "$CPMT_SERVER_STEP_ID"
  exit 0
fi
[[ ! -f "$CPMT_OUTPUT_DIR/started.json" && ! -f "$CPMT_OUTPUT_DIR/training.log" && ! -f "$CPMT_OUTPUT_DIR/training_manifest.json" && ! -d "$CPMT_OUTPUT_DIR/models" ]] || cpmt_fail interrupted_attempt_requires_review
python - <<'PY_START' || cpmt_fail start_record_failed
import datetime,os,sys
from pathlib import Path
sys.path.insert(0,'src')
from cpmt.m1_s5_training import write_json
e=os.environ
write_json(Path(e['CPMT_OUTPUT_DIR'])/'started.json',{
    'stage':e['CPMT_SERVER_STEP_ID'],'commit':e['CPMT_CURRENT_COMMIT'],
    'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'train_path':e['CPMT_TRAIN'],'models':60,'validation_arrays_read':False,'test_access':False})
PY_START
CPMT_S5_WORKER=1 nohup bash "$CPMT_SCRIPT_DIR/run_next_server_step.sh" > "$CPMT_OUTPUT_DIR/training.log" 2>&1 < /dev/null 9>&9 &
CPMT_WORKER_PID=$!
printf "%s\n" "$CPMT_WORKER_PID" > "$CPMT_OUTPUT_DIR/worker.pid"
printf "SERVER_STEP_STARTED id=%s pid=%s\nLOG=%s/training.log\n" "$CPMT_SERVER_STEP_ID" "$CPMT_WORKER_PID" "$CPMT_OUTPUT_DIR"
printf "Re-run bash ops/run_next_server_step.sh to inspect status; completed models are not retrained.\n"
printf "Keep this checkout unchanged while training runs; validation/test remain unopened.\n"
