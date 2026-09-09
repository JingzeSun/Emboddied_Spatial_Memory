#!/usr/bin/env bash
# Unique phase: diagnose the retained S5 C11 generation failure.
# Read original failed output metadata; reproduce ONE recorded failing group in memory.
# Write only separate diagnostic output and its exact committable report.
# Never resume/replace data shards, train/evaluate models, change the generator, or open test.
# Completed matching diagnosis/export is reused; all original failure files stay intact.
set -uo pipefail
export CPMT_SERVER_STEP_ID="m1_v6_d050_s5_generation_diagnostic"
CPMT_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
export CPMT_REPO_DIR="$(git -C "$CPMT_SCRIPT_DIR" rev-parse --show-toplevel)" || exit 2
export CPMT_FAILED_DIR="/root/autodl-tmp/cpmt_outputs/m1-v6-d050-s5-validation-g200"
export CPMT_DIAGNOSTIC_DIR="/root/autodl-tmp/cpmt_outputs/m1-v6-d050-s5-generation-diagnostic"
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
[[ "$#" -eq 0 ]] || exit 2
cd "$CPMT_REPO_DIR" || exit 2
[[ -d "$CPMT_FAILED_DIR" && -d /root/autodl-tmp ]] || exit 2
command -v flock >/dev/null 2>&1 || exit 2
exec 9>"$CPMT_FAILED_DIR/worker.lock"
if ! flock -n 9; then
  printf "SERVER_STEP_PENDING id=%s reason=original_worker_still_running\n" "$CPMT_SERVER_STEP_ID"
  exit 0
fi
mkdir -p "$CPMT_DIAGNOSTIC_DIR" || exit 2
exec 8>"$CPMT_DIAGNOSTIC_DIR/diagnostic.lock"
flock -n 8 || exit 2
python - <<'PY_DIAG' 2>&1 | tee -a "$CPMT_DIAGNOSTIC_DIR/diagnostic.log"
import inspect,json,os,subprocess,sys,time,traceback
from pathlib import Path
sys.path.insert(0,'src')
from cpmt.m1_protocol import load_and_validate,load_and_validate_endpoint_probe,protocol_sha256
from cpmt.m1_s5_confirmation import group_indices,load_confirmation_plan
from cpmt.m1_s5_training import read_json,require,write_json
from cpmt.run_provenance import capture_run_provenance,file_sha256

root=Path.cwd();env=os.environ;original=Path(env['CPMT_FAILED_DIR']);out=Path(env['CPMT_DIAGNOSTIC_DIR'])
stage=env['CPMT_SERVER_STEP_ID'];generation_commit='d3a7ad34086dcdb60edebb3185d5af778d175af3'
message='C11 collateral stress requires an unprotected node outside the current evidence scope'
name='m1_v6_d050_s5_generation_failure';relative='results/'+name+'.json';target=root/relative

def fingerprint_original():
    names=['started.json','runner_exit.txt','worker_exit.txt','data_manifest.json','generation.log']
    paths=[original/n for n in names if (original/n).is_file()]
    paths+=sorted(original.glob('failure_*.json'))
    paths+=sorted(original.glob('.group_*.incomplete/attempt.json'))
    paths+=sorted(original.glob('.group_*.incomplete/failure.json'))
    paths+=sorted(original.glob('group_*/complete.json'))
    return {p.relative_to(original).as_posix():file_sha256(p) for p in paths}

try:
    changed=subprocess.check_output(['git','diff','--name-only',generation_commit,'HEAD','--','src','scripts','configs','tests'],text=True).splitlines()
    require(set(changed)<={'scripts/export_run_report.py'},'generator/training/evaluation changed; diagnose original science first')
    status=subprocess.check_output(['git','status','--porcelain','-z']).decode()
    require(all(row[3:]==relative for row in status.split('\0') if row),'unexpected checkout changes')
    hard=load_and_validate(root/'configs/m1_hard_condition.json')
    overlay=load_and_validate_endpoint_probe(root/'configs/m1_endpoint_viability_probe.json',hard)
    plan,training=load_confirmation_plan(root,hard,overlay)
    started=read_json(original/'started.json');manifest=read_json(original/'data_manifest.json')
    require(started['commit']==generation_commit and started['stage']=='m1_v6_d050_s5_confirmation_data','unexpected failed run')
    require((original/'runner_exit.txt').read_text().strip()!='0','original generation did not fail')
    require(manifest['plan']==plan and manifest['status']=='running','unexpected original manifest state')
    before=fingerprint_original()
    inventory=[];failed=[]
    for index in group_indices(plan):
        complete=original/f'group_{index:06d}';partial=original/f'.group_{index:06d}.incomplete'
        row={'group_index':index,'complete_directory':complete.is_dir(),'partial_directory':partial.is_dir(),
            'in_parent_manifest':str(index) in manifest['groups']}
        failure_path=partial/'failure.json'
        if failure_path.exists():
            row['failure']=read_json(failure_path)
            row['attempt']=read_json(partial/'attempt.json')
            require(row['attempt']['binding']['group_index']==index,'failure group identity mismatch')
            if row['failure']['type']=='ValueError' and row['failure']['message']==message:
                failed.append(index)
        inventory.append(row)
    require(failed,'no recorded C11 failure found; inspect original log without guessing group')
    selected=min(failed)
    print('FAILURE_INVENTORY completed_directories='+str(sum(r['complete_directory'] for r in inventory))+
        ' parent_manifest_groups='+str(len(manifest['groups']))+' recorded_C11_failures='+str(failed),flush=True)
    report_path=out/'diagnostic_report.json'
    if report_path.exists():
        report=read_json(report_path)
        require(report['original_metadata_sha256']==before and report['selected_group_index']==selected,'diagnostic input changed; preserve previous evidence')
        print('DIAGNOSTIC_REUSED group='+str(selected),flush=True)
    else:
        require(not status,'first diagnosis requires clean checkout')
        import cpmt.m1_rollout as rollout
        proposal_code=rollout._proposal_context.__code__
        scope_code=rollout._current_online_evidence_scope.__code__
        lines,first=inspect.getsourcelines(rollout._current_online_evidence_scope)
        loop_line=first+next(i for i,line in enumerate(lines) if line.strip()=='for edge in open_edges:')
        scope_frames={};scope_returns={};capture={}
        def trace(frame,event,arg):
            if frame.f_code==scope_code:
                frame_key=id(frame)
                if event=='call': scope_frames[frame_key]=None
                elif event=='line' and frame.f_lineno==loop_line and scope_frames.get(frame_key) is None:
                    scope_frames[frame_key]=sorted(frame.f_locals['selected'])
                elif event=='return':
                    local=frame.f_locals
                    key=(local['graph']['graph_hash'],local['event']['event_id'])
                    scope_returns[key]={'retrieved_seed_ids':scope_frames.pop(frame_key,None),'returned_scope_ids':sorted(arg) if isinstance(arg,set) else None}
                return trace
            if frame.f_code==proposal_code:
                if event=='exception' and isinstance(arg[1],ValueError) and str(arg[1])==message:
                    local=frame.f_locals;graph=local['graph'];event_spec=local['event']
                    context={};parent=frame
                    while parent is not None:
                        if parent.f_code.co_name=='_generate_sequence':
                            context={k:parent.f_locals.get(k) for k in ('split','sequence_index','sibling_index','step_index','world_seed')}
                            break
                        parent=parent.f_back
                    value={'graph':graph,'event':event_spec,'sequence_context':context,
                        'bind_targets':local.get('bind_targets'),'unrelated_candidates':local.get('unrelated_candidates'),
                        'evidence_scope':sorted(local['evidence_scope']),
                        'scope_trace':scope_returns.get((graph['graph_hash'],event_spec['event_id']))}
                    capture.update(json.loads(json.dumps(value)))
                return trace
            return None
        began=time.monotonic();reproduction=None;previous_trace=sys.gettrace()
        print('REPRODUCE_RECORDED_FAILURE group='+str(selected)+' split=validation groups=1 original_rules=true',flush=True)
        try:
            sys.settrace(trace)
            rollout.generate_m1_paired_rollout_split(hard,'validation',paired_groups=1,start_group_index=selected)
            reproduction={'status':'did_not_reproduce'}
        except Exception as error:
            reproduction={'status':'reproduced_expected_failure' if isinstance(error,ValueError) and str(error)==message else 'different_failure',
                'type':type(error).__name__,'message':str(error),'traceback':traceback.format_exc()}
        finally:
            sys.settrace(previous_trace)
        report={'schema_version':'cpmt-s5-generation-diagnostic-v1','selected_group_index':selected,
            'selection_rule':'minimum_group_index_among_retained_exact_C11_failure_records',
            'original_run_commit':generation_commit,'original_generation_binding':manifest['binding'],
            'original_metadata_sha256':before,'original_inventory':inventory,'reproduction':reproduction,'failure_snapshot':capture,
            'wall_seconds':time.monotonic()-began,'plan_sha256':protocol_sha256(plan),
            'diagnostic_provenance':capture_run_provenance(root,component=stage,entrypoint=root/'ops/run_next_server_step.sh'),
            'instrumentation':'sys.settrace_reads_scope_and_exception_locals_only_no_function_replacement',
            'test_access':False,'model_evaluation_performed':False,'replacement_groups_generated':False,
            'original_metadata_unchanged':fingerprint_original()==before}
        require(report['original_metadata_unchanged'],'original failure metadata changed during diagnosis')
        write_json(report_path,report)
    require(fingerprint_original()==before,'original outputs changed')
    capture=report['failure_snapshot'];scope=capture.get('scope_trace') or {}
    print('REPRODUCTION_STATUS='+report['reproduction']['status'],flush=True)
    print('FAILED_SEQUENCE_CONTEXT='+json.dumps(capture.get('sequence_context'),sort_keys=True),flush=True)
    print('SCOPE_COUNTS retrieved='+str(len(scope.get('retrieved_seed_ids') or []))+' expanded='+str(len(capture.get('evidence_scope') or []))+' unrelated_candidates='+str(len(capture.get('unrelated_candidates') or [])),flush=True)
    if target.exists():
        require(read_json(target)['diagnostic_report']==report,'existing diagnostic export mismatch')
    else:
        subprocess.run([sys.executable,'scripts/export_run_report.py','--out-dir',str(out),'--name',name,
            '--results-dir',str(out),'--note','Single recorded S5 C11 failure diagnosis; original data and all models unchanged.'],check=True)
        exported=out/(name+'.json');require(read_json(exported)['diagnostic_report']==report,'diagnostic export mismatch')
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream: stream.write(exported.read_bytes())
    print('EXPORT_VERIFIED path='+str(target)+' sha256='+file_sha256(target),flush=True)
    print('SERVER_STEP_OK id='+stage+' inspected_groups=1',flush=True)
    print('NEXT=review_diagnostic_then_commit_only_'+relative+';_do_not_restart_generation',flush=True)
except Exception as error:
    print('SERVER_STEP_FAILED id='+stage+' reason='+str(error),flush=True)
    raise
PY_DIAG
CPMT_EXITS=("${PIPESTATUS[@]}")
printf "DIAGNOSTIC_EXIT=%s LOG_WRITE_EXIT=%s\n" "${CPMT_EXITS[0]}" "${CPMT_EXITS[1]}"
[[ "${CPMT_EXITS[0]}" -eq 0 && "${CPMT_EXITS[1]}" -eq 0 ]]
