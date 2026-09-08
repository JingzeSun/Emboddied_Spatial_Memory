#!/usr/bin/env bash
# Unique phase: export the two accepted D-048 budget reports.
# Inputs: runner_exit=0, budget.ok.json and budget.acceptance.json for both arms.
# Read: accepted reports/JSON metadata only; no arrays, validation, test or training.
# Write: results/m1_v6_d048_budget_{set_transformer,mlp}.json and export log/staging.
# Resume: validate and reuse complete exports; never overwrite mismatched results.
# Success: SERVER_STEP_OK id=m1_v6_d048_budget_reports_export exported_arms=2
set -uo pipefail
CPMT_SERVER_STEP_ID="m1_v6_d048_budget_reports_export"
CPMT_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
CPMT_REPO_DIR="$(git -C "$CPMT_SCRIPT_DIR" rev-parse --show-toplevel)" || exit 2
CPMT_EXPORT_DIR="/root/autodl-tmp/cpmt_outputs/m1-v6-d048-budget-export"
[[ "$#" -eq 0 ]] || exit 2
cd "$CPMT_REPO_DIR" || exit 2
mkdir -p "$CPMT_EXPORT_DIR" || exit 2
python - "$CPMT_REPO_DIR" "$CPMT_EXPORT_DIR" <<'PY' 2>&1 | tee -a "$CPMT_EXPORT_DIR/export.log"
import fcntl,hashlib,json,subprocess,sys
from pathlib import Path

STAGE='m1_v6_d048_budget_reports_export'
REGISTRATION='d366935b14975a18cf3e0af58833fcb8a1151c5929c8848d40677d692fd51e1d'
TRAIN_DIGEST='e8a890f1b254a7109af641fea57fcbea5efd931b4272d8e96cb870f51604b168'
ARMS=[
 ('cross_candidate_set_transformer_v1','set-transformer','set_transformer','72f1b8a879b86c6b37f107ac29a14989a6b67f07'),
 ('shared_candidate_mlp_v1','mlp','mlp','04c8319460df47a0a17960341880d28497897709'),
]

def require(ok,message):
    if not ok:
        raise ValueError(message)

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def validate_export(value,name,report,marker,acceptance,started,root):
    require(value['schema_version']=='cpmt-exported-run-report-v2' and value['name']==name,'wrong export identity')
    require(value['formal_run'] is False and value['test_generated'] is False,'export access boundary mismatch')
    require(value['budget_report']==report,'exported budget differs from accepted report')
    require(value['pipeline_provenance']['training']==report['training_provenance'],'training provenance lost')
    for key,expected in [('budget.ok.json',marker),('budget.acceptance.json',acceptance),('started.json',started)]:
        require(value['other_reports'][key]==expected,'exported metadata differs: '+key)
    export=value['pipeline_provenance']['export']
    require(export['git_dirty'] is False,'dirty export provenance')
    # A prior completed export is reusable only with the same scientific/export code.
    from cpmt.run_provenance import source_tree_sha256
    require(export['source_tree_sha256']==source_tree_sha256(root),'export source tree mismatch')

def main():
    root=Path(sys.argv[1]);stage=Path(sys.argv[2]);sys.path.insert(0,str(root/'src'))
    # Untracked result JSONs are expected when resuming this phase.
    status=subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=root,text=True)
    require(not status.strip(),'tracked checkout changes; inspect before export')
    untracked=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=root,text=True).splitlines()
    allowed={'results/m1_v6_d048_budget_'+arm[2]+'.json' for arm in ARMS}
    require(set(untracked)<=allowed,'unexpected untracked files; inspect before export')
    base=Path('/root/autodl-tmp/cpmt_outputs');prepared=[]
    for architecture,suffix,label,commit in ARMS:
        out=base/('m1-v6-d048-budget-'+suffix)
        with (out/'worker.lock').open('r+') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            require((out/'runner_exit.txt').read_text().strip()=='0','runner not completed: '+suffix)
            raw=(out/'budget_report.json').read_bytes();report=json.loads(raw)
            marker=read(out/'budget.ok.json');acceptance=read(out/'budget.acceptance.json');started=read(out/'started.json')
            require(marker['schema_version']=='cpmt-d048-budget-arm-marker-v1','wrong acceptance marker')
            require(marker['report_sha256']==hashlib.sha256(raw).hexdigest(),'accepted report hash changed')
            require(marker['architecture']==architecture and marker['commit']==commit,'wrong accepted arm')
            require(marker['registration_sha256']==REGISTRATION and marker['train_arrays_digest']==TRAIN_DIGEST,'accepted input mismatch')
            require(marker['runner_exit_code']==0 and marker['validation_arrays_read'] is False and marker['test_access'] is False,'accepted run boundary mismatch')
            require(acceptance['validated_marker']==marker and acceptance['training_restarted'] is False and acceptance['report_rewritten'] is False,'acceptance evidence mismatch')
            require(started['commit']==commit and report['training_provenance']['git_commit']==commit,'original commit mismatch')
            require(report['training_provenance']['git_dirty'] is False,'dirty original training')
            require(report['architecture']==architecture and report['post_probe_registration_sha256']==REGISTRATION,'report identity mismatch')
            require(all(report[k] is False for k in ('formal_run','test_generated','causal_complete')),'unexpected formal or causal report')
            require(all(report['partition'][k] is False for k in ('validation_arrays_read','validation_trial_consumed','test_access')),'report held-out access mismatch')
            changed=subprocess.check_output(['git','diff','--name-only',commit,'HEAD','--','src','scripts','configs','tests'],cwd=root,text=True).splitlines()
            require(set(changed)<={'scripts/export_run_report.py'},'science/config changes beyond exporter')
            prepared.append((out,label,report,marker,acceptance,started))
    # Both arms must pass prerequisites before writing either export.
    pending_exports=[]
    for out,label,report,marker,acceptance,started in prepared:
        name='m1_v6_d048_budget_'+label;target=root/'results'/(name+'.json')
        if target.exists():
            validate_export(read(target),name,report,marker,acceptance,started,root)
            print('EXPORT_REUSED path='+str(target),flush=True)
            continue
        staged=stage/(name+'.json')
        if not staged.exists():
            subprocess.run([sys.executable,str(root/'scripts/export_run_report.py'),
                '--out-dir',str(out),'--name',name,'--results-dir',str(stage),
                '--note','Accepted D-048 train/inner-dev budget only; no validation/test or causal evaluation; shared GPU runtime is not an exclusive benchmark.'],cwd=root,check=True)
        validate_export(read(staged),name,report,marker,acceptance,started,root)
        pending_exports.append((staged,target))
    # Stage and verify both before creating untracked result files in the checkout.
    for staged,target in pending_exports:
        target.parent.mkdir(parents=True,exist_ok=True)
        temporary=target.with_suffix('.json.export-tmp')
        temporary.write_bytes(staged.read_bytes())
        require(not target.exists(),'result appeared during export; inspect before resuming')
        temporary.replace(target)
        print('EXPORT_VERIFIED path='+str(target)+' sha256='+hashlib.sha256(target.read_bytes()).hexdigest(),flush=True)
    print('SERVER_STEP_OK id='+STAGE+' exported_arms=2',flush=True)
    print('NEXT=review_exports_then_commit_only_the_two_exact_results_paths',flush=True)

if __name__=='__main__':
    try:
        main()
    except Exception as error:
        print('SERVER_STEP_FAILED id='+STAGE+' reason='+str(error),flush=True)
        raise
PY
CPMT_EXITS=("${PIPESTATUS[@]}")
printf "EXPORT_EXIT=%s LOG_WRITE_EXIT=%s\n" "${CPMT_EXITS[0]}" "${CPMT_EXITS[1]}"
[[ "${CPMT_EXITS[0]}" -eq 0 && "${CPMT_EXITS[1]}" -eq 0 ]]
