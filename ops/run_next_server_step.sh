#!/usr/bin/env bash
# Unique phase: verify and export the completed D-049 selected-training artifacts.
# Inputs: original successful training marker, manifest and all 60 saved models.
# Read: training metadata/model hashes only; no arrays, training or evaluation.
# Write: export staging/logs and one exact results JSON; never change training files.
# Resume: matching export is reused; incomplete/mismatched training is rejected.
# Success: SERVER_STEP_OK id=m1_v6_d049_s5_training_export exported_reports=1
set -uo pipefail
export CPMT_SERVER_STEP_ID="m1_v6_d049_s5_training_export"
CPMT_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
export CPMT_REPO_DIR="$(git -C "$CPMT_SCRIPT_DIR" rev-parse --show-toplevel)" || exit 2
export CPMT_TRAINING_DIR="/root/autodl-tmp/cpmt_outputs/m1-v6-d049-s5-selected-training"
export CPMT_EXPORT_DIR="/root/autodl-tmp/cpmt_outputs/m1-v6-d049-s5-training-export"
export CPMT_FULL_TEST_MARKER="/root/autodl-tmp/cpmt_outputs/m1-v6-d049-full-test-c6d7644/full_test.ok.json"
export PYTHONUNBUFFERED=1
[[ "$#" -eq 0 ]] || exit 2
cd "$CPMT_REPO_DIR" || exit 2
[[ -d "$CPMT_TRAINING_DIR" && -d /root/autodl-tmp ]] || exit 2
command -v flock >/dev/null 2>&1 || exit 2
exec 9>"$CPMT_TRAINING_DIR/worker.lock"
if ! flock -n 9; then
  printf "SERVER_STEP_PENDING id=%s reason=training_worker_still_running\n" "$CPMT_SERVER_STEP_ID"
  exit 0
fi
mkdir -p "$CPMT_EXPORT_DIR" || exit 2
exec 8>"$CPMT_EXPORT_DIR/export.lock"
flock -n 8 || exit 2
python - <<'PY_EXPORT' 2>&1 | tee -a "$CPMT_EXPORT_DIR/export.log"
import os, shutil, subprocess, sys
from pathlib import Path
sys.path.insert(0,'src')
from cpmt.m1_protocol import load_and_validate,load_and_validate_endpoint_probe,protocol_sha256
from cpmt.m1_s5_training import component_spec,load_plan,read_json,require
from cpmt.m1_s5_training import validate_artifact,write_json
from cpmt.run_provenance import file_sha256

root=Path.cwd();env=os.environ
out=Path(env['CPMT_TRAINING_DIR']);staging=Path(env['CPMT_EXPORT_DIR'])
stage=env['CPMT_SERVER_STEP_ID']
training_commit='af2ed07108f52b186623bba08731a35de84ed88b'
training_stage='m1_v6_d049_s5_selected_training'
name='m1_v6_d049_s5_training'
relative='results/'+name+'.json';target=root/relative

def git(*args):
    return subprocess.check_output(['git',*args],cwd=root,text=True,encoding='utf-8').strip()

def verify_export(path,report,marker):
    exported=read_json(path)
    require(exported['schema_version']=='cpmt-exported-run-report-v2' and exported['name']==name,'wrong export identity')
    require(exported['training_manifest']==report,'export training manifest mismatch')
    require(exported['other_reports']['training.ok.json']==marker,'export success marker mismatch')
    require(exported['other_reports']['started.json']==read_json(out/'started.json'),'export start record mismatch')
    require(exported['pipeline_provenance']['training']==report['training_provenance'],'original training provenance lost')
    require(exported['pipeline_provenance']['export']['git_dirty'] is False,'dirty export checkout')
    require(exported['formal_run'] is False and exported['test_generated'] is False,'export access mismatch')
    require(not exported['causal_per_seed'],'unexpected evaluation payload')

try:
    changed=git('diff','--name-only',training_commit,'HEAD','--','src','scripts','configs','tests').splitlines()
    require(set(changed)<= {'scripts/export_run_report.py'},'scientific code changed beyond export support; review required')
    # An already exported exact result may be untracked or staged. No other dirt is allowed.
    status=subprocess.check_output(['git','status','--porcelain','-z'],cwd=root).decode('utf-8')
    require(all(row[3:]==relative for row in status.split('\0') if row),'unexpected working-tree changes')
    hard=load_and_validate(root/'configs/m1_hard_condition.json')
    overlay=load_and_validate_endpoint_probe(root/'configs/m1_endpoint_viability_probe.json',hard)
    plan,registration=load_plan(root,hard,overlay)
    require((out/'runner_exit.txt').read_text().strip()=='0','training runner did not exit successfully')
    report_path=out/'training_manifest.json';report=read_json(report_path)
    marker=read_json(out/'training.ok.json');started=read_json(out/'started.json')
    require(started['commit']==training_commit and started['stage']==training_stage,'unexpected training start')
    expected_marker={'schema_version':'cpmt-d049-s5-training-marker-v1','stage':training_stage,
        'commit':training_commit,'plan_sha256':protocol_sha256(plan),
        'training_manifest_sha256':file_sha256(report_path),'models':60,'runner_exit_code':0,
        'validation_arrays_read':False,'test_access':False,'causal_complete':False}
    require(marker==expected_marker,'training success marker mismatch')
    require(report['schema_version']=='cpmt-s5-training-manifest-v1' and report['status']=='complete','incomplete training')
    require(report['plan']==plan and report['post_probe_registration']==registration,'training recipe mismatch')
    require(all(report[k] is False for k in ('formal_run','validation_arrays_read','test_access','causal_complete','model_selection_performed')),'training access or selection mismatch')
    require(report['training_group_ids']==list(range(1000)) and report['training_rows']==40000,'wrong training population')
    require(report['label_mask_reused'] is True,'label mask policy mismatch')
    binding=report['binding'];provenance=report['training_provenance']
    require(binding['plan_sha256']==protocol_sha256(plan) and binding['registration_sha256']==protocol_sha256(registration),'binding mismatch')
    require(binding['source_protocol_sha256']==protocol_sha256(hard),'source protocol mismatch')
    require(binding['train_arrays_digest']==plan['train_arrays_digest']==report['input_arrays']['train']['arrays_digest'],'train digest mismatch')
    require(provenance['git_commit']==training_commit and provenance['git_dirty'] is False,'training provenance mismatch')
    require(provenance['source_tree_sha256']==binding['source_tree_sha256'],'training source binding mismatch')
    full_path=Path(env['CPMT_FULL_TEST_MARKER']);full=read_json(full_path)
    require(report['test_marker_sha256']==file_sha256(full_path),'original full-test marker changed')
    require(full['schema_version']=='cpmt-d049-full-test-marker-v1' and full['commit']=='c6d76441a5ca2181d593d03d47342d63e3cc3f06','wrong full-test identity')
    require(full['tests_run']==full['expected_tests']==234 and full['exit_code']==full['failures']==full['errors']==full['skipped']==0,'full-test prerequisite failed')
    require(full['plan_sha256']==protocol_sha256(plan) and full['registration_sha256']==protocol_sha256(registration),'full-test binding mismatch')
    require(full['source_tree_unchanged'] is True and full['test_access'] is False and full['formal_validation_arrays_read'] is False,'full-test boundary mismatch')
    require(full['provenance']['source_tree_sha256']==binding['source_tree_sha256'],'original training/test source mismatch')
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
        require(artifact['training']['training_provenance']==provenance,'model provenance mismatch')
        require(artifact['training']['validation_arrays_read'] is False and artifact['training']['test_access'] is False,'model access mismatch')
    print('TRAINING_EXPORT_PREREQUISITES_OK models=60 validation_arrays_read=false test_access=false',flush=True)
    if target.exists():
        verify_export(target,report,marker)
        print('EXPORT_REUSED path='+str(target),flush=True)
    else:
        require(not status,'export checkout must be clean')
        subprocess.run([sys.executable,'scripts/export_run_report.py','--out-dir',str(out),
            '--name',name,'--results-dir',str(staging),
            '--note','D-049 selected-budget train-only: 50 students and 10 scorers; S5 confirmation pending.'],check=True)
        exported_path=staging/(name+'.json');verify_export(exported_path,report,marker)
        target.parent.mkdir(parents=True,exist_ok=True)
        # Exclusive creation: never overwrite a different report on a retry.
        with target.open('xb') as destination, exported_path.open('rb') as source:
            shutil.copyfileobj(source,destination)
        verify_export(target,report,marker)
    digest=file_sha256(target)
    write_json(staging/'export.ok.json',{'stage':stage,'path':str(target),'sha256':digest,
        'training_manifest_sha256':marker['training_manifest_sha256'],'models':60,'test_access':False})
    print('EXPORT_VERIFIED path='+str(target)+' sha256='+digest,flush=True)
    print('SERVER_STEP_OK id='+stage+' exported_reports=1',flush=True)
    print('NEXT=review_export_then_commit_only_results/m1_v6_d049_s5_training.json',flush=True)
except Exception as error:
    print('SERVER_STEP_FAILED id='+stage+' reason='+str(error),flush=True)
    raise
PY_EXPORT
CPMT_PIPE_STATUS=("${PIPESTATUS[@]}")
printf "EXPORT_EXIT=%s LOG_WRITE_EXIT=%s\n" "${CPMT_PIPE_STATUS[0]}" "${CPMT_PIPE_STATUS[1]}"
[[ "${CPMT_PIPE_STATUS[0]}" -eq 0 && "${CPMT_PIPE_STATUS[1]}" -eq 0 ]]
