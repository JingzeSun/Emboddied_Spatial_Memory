#!/usr/bin/env bash
# Unique phase: accept already-written budget reports, correcting method-name validation.
# Inputs: existing two arm outputs + D-048 full-test marker + unchanged science/config.
# Read: reports, exit records and provenance only. Never read arrays or launch training.
# Write: acceptance log and verified budget.ok.json / budget.acceptance.json markers only.
# Resume: reuse verified markers; a locked/running arm is reported pending, never restarted.
set -uo pipefail
CPMT_SERVER_STEP_ID="m1_v6_d048_budget_reports_acceptance"
CPMT_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
CPMT_REPO_DIR="$(git -C "$CPMT_SCRIPT_DIR" rev-parse --show-toplevel)" || exit 2
CPMT_AUDIT_DIR="/root/autodl-tmp/cpmt_outputs/m1-v6-d048-budget-acceptance"
[[ "$#" -eq 0 ]] || exit 2
cd "$CPMT_REPO_DIR" || exit 2
mkdir -p "$CPMT_AUDIT_DIR" || exit 2
python - "$CPMT_REPO_DIR" <<'PY' 2>&1 | tee -a "$CPMT_AUDIT_DIR/acceptance.log"
import datetime,hashlib,itertools,json,subprocess,sys
from pathlib import Path

STAGE='m1_v6_d048_budget_reports_acceptance'
REGISTRATION='d366935b14975a18cf3e0af58833fcb8a1151c5929c8848d40677d692fd51e1d'
TRAIN_DIGEST='e8a890f1b254a7109af641fea57fcbea5efd931b4272d8e96cb870f51604b168'
TEST_COMMIT='27d79eaa8f2312f62fff411d249bf574af061d8e'
ARMS=[
 ('cross_candidate_set_transformer_v1','set-transformer','72f1b8a879b86c6b37f107ac29a14989a6b67f07','m1_v6_d048_set_transformer_train_inner_dev_budget'),
 ('shared_candidate_mlp_v1','mlp','04c8319460df47a0a17960341880d28497897709','m1_v6_d048_mlp_train_inner_dev_budget'),
]

def require(condition,message):
    if not condition:
        raise ValueError(message)

def validate_report(r,started,architecture,run_commit,arm_stage,hard,overlay,source_hash):
    require(started['commit']==run_commit and started['stage']==arm_stage,'unexpected original start record')
    require(r['schema_version']=='cpmt-m1-v8-train-inner-dev-budget-v3','wrong budget report schema')
    require(r['architecture']==architecture and r['architecture_result_selection_forbidden'] is True,'architecture boundary mismatch')
    require(r['protocol_sha256']==overlay['source_protocol']['protocol_sha256'],'source protocol mismatch')
    require(r['post_probe_registration_sha256']==REGISTRATION,'registration mismatch')
    require(all(r[k] is False for k in ('formal_run','test_generated','causal_complete')),'unexpected formal/test/causal access')
    provenance=r['training_provenance']
    require(provenance['git_commit']==run_commit and provenance['git_dirty'] is False,'original training provenance mismatch')
    require(provenance['source_tree_sha256']==source_hash,'training scientific source differs from verified source')
    require(r['input_arrays']['train']['arrays_digest']==TRAIN_DIGEST,'train digest mismatch')
    p=r['partition']
    fitting=set(p['fitting_group_ids']); inner=set(p['inner_dev_group_ids'])
    require(p['train_paired_groups']==1000 and len(fitting)==799 and len(inner)==201 and not(fitting & inner),'paired partition mismatch')
    require(all(p[k] is False for k in ('validation_arrays_read','validation_trial_consumed','test_access')),'held-out access boundary mismatch')
    budget=hard['training']['pretest_budget_selection']
    methods=set(budget['student_selection_methods'])
    # The runner serializes full method names, not the human-facing A-E IDs.
    selected=r['selected']['student_hyperparameters_by_method']
    require(set(selected)==methods,'selected methods must match registered full method names')
    require(r['registered_source_budget_contract']==budget,'source budget contract drift')
    require(r['D046_budget_amendment']==overlay['post_probe_train_inner_dev_budget_amendment'],'C weight amendment drift')
    def check_grid(rows,expected,keys,label):
        actual=[tuple(row[k] for k in keys) for row in rows]
        require(len(actual)==len(expected) and set(actual)==expected,label+' grid is missing, duplicated or expanded')
    scorer_cells=set(itertools.product(budget['seeds'],budget['learning_rates'],budget['scorer_update_checkpoints']))
    check_grid(r['scorer']['runs'],scorer_cells,('seed','learning_rate','checkpoint'),'scorer')
    student_cells=set(itertools.product(methods,budget['seeds'],budget['learning_rates'],budget['student_update_checkpoints']))
    check_grid(r['students']['runs'],student_cells,('method','seed','learning_rate','checkpoint'),'students')
    for method,value in selected.items():
        require(value['learning_rate'] in budget['learning_rates'] and value['student_steps'] in budget['student_update_checkpoints'],method+' selected an unregistered setting')
    weights=overlay['post_probe_train_inner_dev_budget_amendment']['direct_future_auxiliary_weights']
    anchor=overlay['post_probe_train_inner_dev_budget_amendment']['direct_future_auxiliary_weight_anchor']
    aux=r['students']['C_auxiliary_weight_runs']
    check_grid(aux,set(itertools.product(budget['seeds'],weights)),('seed','auxiliary_weight'),'C weight')
    c=selected['direct_future_loss']
    require(c['direct_future_auxiliary_weight'] in weights,'unregistered selected C weight')
    for row in aux:
        require(row['method']=='direct_future_loss' and row['learning_rate']==c['learning_rate'] and row['checkpoint']==c['student_steps'],'C weight comparison changed frozen compute')
        expected='reused_anchor_run_at_fixed_selected_compute' if row['auxiliary_weight']==anchor else 'auxiliary_weight_at_fixed_selected_compute'
        require(row['selection_stage']==expected,'C anchor reuse/additional path mismatch')
    require(r['parameter_fairness']['learning_rate_updates_grid_cells_per_method']==12,'wrong number of compute settings')

def write_or_verify(path,value):
    if path.exists():
        require(json.loads(path.read_text(encoding='utf-8'))==value,'existing marker mismatch: '+str(path))
    else:
        tmp=path.with_suffix('.tmp')
        tmp.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
        tmp.replace(path)

def main():
    import fcntl
    root=Path(sys.argv[1]);sys.path.insert(0,str(root/'src'))
    from cpmt.m1_protocol import load_and_validate,load_and_validate_endpoint_probe,protocol_sha256
    from cpmt.m1_registration import load_registration
    from cpmt.run_provenance import capture_run_provenance,source_tree_sha256
    require(not subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip(),'acceptance checkout must be clean')
    print('ACCEPTANCE_BEGIN utc='+datetime.datetime.now(datetime.timezone.utc).isoformat(),flush=True)
    hard=load_and_validate(root/'configs/m1_hard_condition.json')
    overlay=load_and_validate_endpoint_probe(root/'configs/m1_endpoint_viability_probe.json',hard)
    require(protocol_sha256(load_registration(root,hard,overlay))==REGISTRATION,'active registration mismatch')
    base=Path('/root/autodl-tmp/cpmt_outputs')
    test=json.loads((base/'m1-v6-d048-full-test-27d79ea/full_test.ok.json').read_text())
    require(test['commit']==TEST_COMMIT and test['tests_run']==221 and test['exit_code']==0,'full-test prerequisite failed')
    require(test['registration_sha256']==REGISTRATION and test['test_access'] is False and test['formal_validation_arrays_read'] is False,'full-test boundary mismatch')
    require(test['source_and_tests_sha256']==source_tree_sha256(root,roots=('src','scripts','configs','tests')),'scientific/test tree changed')
    source_hash=source_tree_sha256(root)
    accepted=0;pending=[];failed=[]
    for architecture,suffix,run_commit,arm_stage in ARMS:
        out=base/('m1-v6-d048-budget-'+suffix)
        if not (out/'worker.lock').exists():
            pending.append(architecture);print('BUDGET_ARM_PENDING architecture='+architecture+' reason=no_run_lock',flush=True);continue
        with (out/'worker.lock').open('r+') as lock:
            try:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                pending.append(architecture);print('BUDGET_ARM_RUNNING architecture='+architecture,flush=True);continue
            try:
                require((out/'runner_exit.txt').exists(),'no completed runner exit record; do not restart automatically')
                require((out/'runner_exit.txt').read_text().strip()=='0','training runner did not exit successfully')
                path=out/'budget_report.json';raw=path.read_bytes();r=json.loads(raw)
                started=json.loads((out/'started.json').read_text())
                validate_report(r,started,architecture,run_commit,arm_stage,hard,overlay,source_hash)
                marker={'schema_version':'cpmt-d048-budget-arm-marker-v1','stage':arm_stage,
                        'commit':run_commit,'architecture':architecture,'registration_sha256':REGISTRATION,
                        'train_arrays_digest':TRAIN_DIGEST,'report_sha256':hashlib.sha256(raw).hexdigest(),
                        'runner_exit_code':0,'validation_arrays_read':False,'test_access':False}
                write_or_verify(out/'budget.ok.json',marker)
                audit_path=out/'budget.acceptance.json'
                if audit_path.exists():
                    require(json.loads(audit_path.read_text())['validated_marker']==marker,'previous acceptance mismatch')
                else:
                    previous_exit=out/'worker_exit.txt'
                    audit={'schema_version':'cpmt-budget-acceptance-v1','validated_marker':marker,
                           'accepted_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                           'acceptance_provenance':capture_run_provenance(root,component=STAGE,entrypoint=root/'ops/run_next_server_step.sh'),
                           'original_worker_exit':previous_exit.read_text().strip() if previous_exit.exists() else None,
                           'repair':'validate_registered_full_method_names_instead_of_letter_ids',
                           'training_restarted':False,'report_rewritten':False,
                           'runtime_not_an_exclusive_gpu_benchmark':True}
                    write_or_verify(audit_path,audit)
                accepted+=1
                print(f'BUDGET_ARM_ACCEPTED architecture={architecture} training_commit={run_commit} report={path}',flush=True)
            except (ValueError,KeyError,OSError,TypeError) as error:
                failed.append(architecture);print(f'BUDGET_ARM_FAILED architecture={architecture} reason={error}',flush=True)
    if failed:
        print(f'SERVER_STEP_FAILED id={STAGE} failed={failed} pending={pending}',flush=True);return 1
    if pending:
        print(f'SERVER_STEP_PENDING id={STAGE} accepted={accepted} pending={pending}',flush=True);return 0
    print(f'SERVER_STEP_OK id={STAGE} accepted_arms={accepted}',flush=True)
    print('NEXT=export_verified_budget_reports_in_a_separate_stage',flush=True)
    return 0

if __name__=='__main__':
    sys.exit(main())
PY
CPMT_EXITS=("${PIPESTATUS[@]}")
printf "ACCEPTANCE_EXIT=%s LOG_WRITE_EXIT=%s\n" "${CPMT_EXITS[0]}" "${CPMT_EXITS[1]}"
[[ "${CPMT_EXITS[0]}" -eq 0 && "${CPMT_EXITS[1]}" -eq 0 ]]
