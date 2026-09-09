#!/usr/bin/env bash
# Unique phase: generate the frozen S5 validation groups 4..203 (D-050).
# Inputs: the successful 250-test marker and the frozen confirmation/training exports.
# Read: repository contracts/reports; generate validation only, never test or train.
# Write: 200 complete paired audit/array shards, manifest, logs and exit markers.
# Resume: running worker -> status only; completed data -> hash verification only.
# Interrupted/failed attempts are retained and require review, never auto-restarted.
set -uo pipefail
export CPMT_SERVER_STEP_ID="m1_v6_d050_s5_confirmation_data"
CPMT_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
export CPMT_REPO_DIR="$(git -C "$CPMT_SCRIPT_DIR" rev-parse --show-toplevel)" || exit 2
export CPMT_CURRENT_COMMIT="$(git -C "$CPMT_REPO_DIR" rev-parse HEAD)" || exit 2
export CPMT_OUTPUT_DIR="/root/autodl-tmp/cpmt_outputs/m1-v6-d050-s5-validation-g200"
export CPMT_FULL_TEST_MARKER="/root/autodl-tmp/cpmt_outputs/m1-v6-d050-full-test-4b8522e/full_test.ok.json"
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
cpmt_fail() { printf "SERVER_STEP_FAILED id=%s reason=%s\nLOG=%s/generation.log\n" "$CPMT_SERVER_STEP_ID" "$1" "$CPMT_OUTPUT_DIR" >&2; exit 1; }
[[ "$#" -eq 0 ]] || cpmt_fail unexpected_arguments
cd "$CPMT_REPO_DIR" || cpmt_fail repository_unavailable

cpmt_check_prerequisites() {
  [[ -z "$(git status --porcelain)" ]] || return 1
  python - <<'PY_CHECK'
import os,sys
from pathlib import Path
sys.path.insert(0,'src')
from cpmt.m1_protocol import load_and_validate,load_and_validate_endpoint_probe
from cpmt.m1_s5_confirmation import load_confirmation_plan,validate_confirmation_test_marker
from cpmt.m1_s5_training import read_json,require
root=Path.cwd();env=os.environ
hard=load_and_validate(root/'configs/m1_hard_condition.json')
overlay=load_and_validate_endpoint_probe(root/'configs/m1_endpoint_viability_probe.json',hard)
plan,training=load_confirmation_plan(root,hard,overlay)
marker=read_json(Path(env['CPMT_FULL_TEST_MARKER']))
validate_confirmation_test_marker(marker,root,plan)
require(marker['commit']=='4b8522e7ae4527dc505be35d3ada79698b239467' and marker['tests_run']==250,'wrong verified full-test run')
require(marker['registration_sha256']==plan['post_probe_registration_sha256'],'full-test registration mismatch')
started=Path(env['CPMT_OUTPUT_DIR'])/'started.json'
if started.exists():
    previous=read_json(started)
    require(previous['commit']==env['CPMT_CURRENT_COMMIT'] and previous['stage']==env['CPMT_SERVER_STEP_ID'],'keep the original generation checkout unchanged')
print('FULL_TEST_AND_PLAN_PREREQUISITES_OK tests=250 validation_groups=200 group_indices=4..203 workers=16 model_evaluation=false test_access=false',flush=True)
PY_CHECK
}

cpmt_finish_report() {
  python - <<'PY_FINISH'
import os,sys
from pathlib import Path
sys.path.insert(0,'src')
from cpmt.m1_protocol import protocol_sha256
from cpmt.m1_s5_confirmation import group_indices,verify_unit
from cpmt.m1_s5_training import read_json,require,write_json
from cpmt.run_provenance import file_sha256,source_tree_sha256
root=Path.cwd();env=os.environ;out=Path(env['CPMT_OUTPUT_DIR'])
require((out/'runner_exit.txt').read_text().strip()=='0','generation runner did not complete successfully')
plan=read_json(root/'configs/m1_s5_confirmation_plan.json')
path=out/'data_manifest.json';report=read_json(path);started=read_json(out/'started.json')
require(started['stage']==env['CPMT_SERVER_STEP_ID'] and started['commit']==env['CPMT_CURRENT_COMMIT'],'start record mismatch')
require(report['schema_version']=='cpmt-s5-data-v1' and report['status']=='complete','data manifest incomplete')
require(report['plan']==plan,'data plan drift')
binding={'plan_sha256':protocol_sha256(plan),'source_tree_sha256':source_tree_sha256(root),
    'training_export_sha256':plan['training_export_sha256'],'split':'validation'}
require(report['binding']==binding,'generation binding mismatch')
require(report['generation_provenance']['git_commit']==env['CPMT_CURRENT_COMMIT']
    and report['generation_provenance']['git_dirty'] is False
    and report['generation_provenance']['source_tree_sha256']==binding['source_tree_sha256'],'generation provenance mismatch')
require(all(report[k] is False for k in ('test_access','validation_trial_consumed','model_evaluation_performed')),'data stage access mismatch')
require(report['paired_groups']==200 and report['sequences']==400 and report['decisions']==8000,'wrong paired population')
require(report['gates']['candidate_coverage'] is True and report['gates']['teacher_health'] is True
    and report['gates']['invariant_violations']==0,'data gate failed; no replacement groups permitted')
indices=group_indices(plan)
require(set(report['groups'])=={str(i) for i in indices},'missing or extra group records')
require({p.name for p in out.glob('group_*')}=={f'group_{i:06d}' for i in indices},'unexpected group directories')
require(not list(out.glob('.group_*.incomplete')) and not list(out.glob('failure_*.json')),'retained partial/failure requires review')
for index in indices:
    directory=out/f'group_{index:06d}'
    marker=verify_unit(directory,{**binding,'group_index':index})
    require(marker==report['groups'][str(index)],'shard manifest mismatch')
    require(set(marker['files'])=={'attempt.json','audits.json.gz','learning.npz','summary.json'},'wrong shard artifact set')
    summary=read_json(directory/'summary.json');generated=summary['generator_summary']
    require(generated['split']=='validation' and generated['start_group_index']==index
        and generated['paired_groups']==1 and generated['sequences']==2 and generated['decisions']==40
        and generated['horizon_decisions']==20 and generated['test_generated'] is False,'wrong group summary')
    require(summary['invariant_violations']==0,'invalid persistent world')
marker={'schema_version':'cpmt-d050-s5-data-marker-v1','stage':env['CPMT_SERVER_STEP_ID'],
    'commit':env['CPMT_CURRENT_COMMIT'],'plan_sha256':protocol_sha256(plan),
    'data_manifest_sha256':file_sha256(path),'full_test_marker_sha256':file_sha256(Path(env['CPMT_FULL_TEST_MARKER'])),
    'paired_groups':200,'sequences':400,'decisions':8000,'runner_exit_code':0,
    'model_evaluation_performed':False,'validation_trial_consumed':False,'test_access':False}
marker_path=out/'generation.ok.json'
if marker_path.exists():
    require(read_json(marker_path)==marker,'existing generation success marker mismatch')
else:
    write_json(marker_path,marker)
print('S5_DATA_VERIFIED paired_groups=200 sequences=400 decisions=8000',flush=True)
print('DATA_HEALTH coverage='+str(report['candidate_coverage'])+' teacher_reference_agreement='+str(report['teacher_reference_agreement']),flush=True)
print('DATA_MANIFEST='+str(path),flush=True)
PY_FINISH
}

if [[ "${CPMT_S5_DATA_WORKER:-0}" == "1" ]]; then
  trap 'CPMT_WORKER_EXIT=$?; printf "%s\n" "$CPMT_WORKER_EXIT" > "$CPMT_OUTPUT_DIR/worker_exit.txt"' EXIT
  cpmt_check_prerequisites || cpmt_fail prerequisites_changed
  printf "S5_DATA_RUN_BEGIN groups=200 range=4..203 workers=16\n"
  python scripts/run_m1_s5_confirmation.py generate --data-dir "$CPMT_OUTPUT_DIR" --out-dir "$CPMT_OUTPUT_DIR" --test-marker "$CPMT_FULL_TEST_MARKER"
  CPMT_RUN_EXIT=$?
  printf "%s\n" "$CPMT_RUN_EXIT" > "$CPMT_OUTPUT_DIR/runner_exit.txt"
  printf "GENERATION_RUN_EXIT=%s\n" "$CPMT_RUN_EXIT"
  [[ "$CPMT_RUN_EXIT" -eq 0 ]] || cpmt_fail generation_failed_requires_review
  cpmt_check_prerequisites || cpmt_fail provenance_changed_after_generation
  cpmt_finish_report || cpmt_fail data_acceptance_failed_requires_review
  printf "SERVER_STEP_OK id=%s paired_groups=200\nNEXT=deliver_saved_model_S5_evaluation_as_a_separate_stage\n" "$CPMT_SERVER_STEP_ID"
  exit 0
fi

command -v flock >/dev/null 2>&1 || cpmt_fail flock_missing
command -v nohup >/dev/null 2>&1 || cpmt_fail nohup_missing
[[ -d /root/autodl-tmp ]] || cpmt_fail data_disk_missing
mkdir -p "$CPMT_OUTPUT_DIR" || cpmt_fail output_directory_creation_failed
exec 9>"$CPMT_OUTPUT_DIR/worker.lock"
if ! flock -n 9; then
  printf "SERVER_STEP_RUNNING id=%s\nLOG=%s/generation.log\n" "$CPMT_SERVER_STEP_ID" "$CPMT_OUTPUT_DIR"
  [[ ! -f "$CPMT_OUTPUT_DIR/generation.log" ]] || tail -n 8 "$CPMT_OUTPUT_DIR/generation.log"
  exit 0
fi
cpmt_check_prerequisites || cpmt_fail full_test_or_plan_prerequisite_failed
if [[ -f "$CPMT_OUTPUT_DIR/runner_exit.txt" || -f "$CPMT_OUTPUT_DIR/generation.ok.json" ]]; then
  cpmt_finish_report || cpmt_fail previous_attempt_requires_review_no_automatic_restart
  printf "SERVER_STEP_OK id=%s paired_groups=200\nNEXT=deliver_saved_model_S5_evaluation_as_a_separate_stage\n" "$CPMT_SERVER_STEP_ID"
  exit 0
fi
[[ ! -f "$CPMT_OUTPUT_DIR/started.json" ]] || cpmt_fail previous_attempt_interrupted_requires_review
python - <<'PY_START'
import os,sys
from pathlib import Path
sys.path.insert(0,'src')
from cpmt.m1_s5_training import require,write_json
out=Path(os.environ['CPMT_OUTPUT_DIR'])
require(not any(p.name not in {'worker.lock'} for p in out.iterdir()),'unexpected existing output files; review before starting')
write_json(out/'started.json',{'stage':os.environ['CPMT_SERVER_STEP_ID'],'commit':os.environ['CPMT_CURRENT_COMMIT']})
PY_START
[[ "$?" -eq 0 ]] || cpmt_fail start_record_failed
CPMT_S5_DATA_WORKER=1 nohup bash "$CPMT_SCRIPT_DIR/run_next_server_step.sh" >"$CPMT_OUTPUT_DIR/generation.log" 2>&1 < /dev/null &
CPMT_WORKER_PID=$!
printf "%s\n" "$CPMT_WORKER_PID" > "$CPMT_OUTPUT_DIR/worker.pid"
printf "SERVER_STEP_STARTED id=%s pid=%s\nLOG=%s/generation.log\n" "$CPMT_SERVER_STEP_ID" "$CPMT_WORKER_PID" "$CPMT_OUTPUT_DIR"
printf "Re-run bash ops/run_next_server_step.sh to inspect status; it will not launch duplicates.\nKeep this checkout unchanged while the worker runs.\n"
