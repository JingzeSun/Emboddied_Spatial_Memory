"""One delivery for S5: tests, prepare, train rehearsal, generate, evaluate,
summarize and export. A successful launch is explicitly NOT completion.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts'),str(ROOT/'ops')]
from cpmt.m1_s5_training import read_json,write_json,require
from cpmt.run_provenance import file_sha256
from m1_corrected_confirmation_plan import binding_now,clean_checkout,OUTPUT_ROOT,EXPORTS
from m1_candidate_availability import command,run_test
from run_m1_corrected_confirmation import ORDER

FILES={'prepare':['binding.json','prepared/report.json'],'smoke':['smoke/report.json'],
       'generate':['data_manifest.json'],'evaluate':['evaluation_manifest.json','validation_trial.json'],
       'summarize':['confirmation_report.json']}


def current_binding():
    return {'science':binding_now(),'ops_sha256':file_sha256(Path(__file__)),
            'shell_sha256':file_sha256(ROOT/'ops/m1_corrected_confirmation.sh')}


def verify_step(stage,action,binding):
    value=read_json(stage/f'{action}.completed.json')
    require(value['binding']==binding and file_sha256(stage/f'{action}.log')==value['log_sha256'],'step source/log changed')
    for name,digest in value['result_files'].items():require(file_sha256(stage/'run'/name)==digest,'step result changed: '+name)
    if value['exit_code']==0:require(set(value['result_files'])==set(FILES[action]),'successful step missing outputs')
    return value


def prerequisites(stage,action,binding):
    tested=read_json(stage/'test.completed.json')
    require(tested['binding']==binding and tested['exit_code']==0 and not any(tested[k] for k in ['errors','failures','skipped']), 'current full tests required')
    require(file_sha256(stage/'test.log')==tested['log_sha256'],'full-test log changed')
    for previous in ORDER[:ORDER.index(action)]:
        require(verify_step(stage,previous,binding)['exit_code']==0,'previous step incomplete/failed: '+previous)


def reserve_generation(stage,binding):
    # Fixed global pathname prevents changing source-derived output directories
    # to create another validation dataset or restart a failed confirmation.
    path=OUTPUT_ROOT/'m1-v7-d055-s5-validation-reservation.json'
    value={'binding':binding,'output':str((stage/'run').resolve()),'indices':list(range(4,204)),
           'test_access':False,'replacement_samples_allowed':False}
    try:
        with path.open('x',encoding='utf-8') as stream:
            import json
            json.dump(value,stream,indent=2,sort_keys=True);stream.write('\n')
    except FileExistsError:require(read_json(path)==value,'validation dataset already reserved by another source/run; review required')
    return value


def run_step(stage,action,binding):
    prerequisites(stage,action,binding)
    if (stage/f'{action}.completed.json').exists():
        result=verify_step(stage,action,binding)
        print(f'S5_CORRECTED_REUSED action={action} completed=true exit={result["exit_code"]}',flush=True)
        return result['exit_code']
    require(not (stage/f'{action}.attempt.json').exists(),'interrupted attempt retained; no automatic retry')
    if action in ['generate','evaluate','summarize']:reserve_generation(stage,binding)
    write_json(stage/f'{action}.attempt.json',{'binding':binding,'action':action})
    began=time.monotonic()
    code=command([sys.executable,'scripts/run_m1_corrected_confirmation.py',action,'--output',str(stage/'run')],stage/f'{action}.log')
    require(current_binding()==binding,'source/runtime changed during step')
    outputs={n:file_sha256(stage/'run'/n) for n in FILES[action] if (stage/'run'/n).is_file()}
    if code==0:require(len(outputs)==len(FILES[action]),'runner success missing required outputs')
    write_json(stage/f'{action}.completed.json',{'binding':binding,'exit_code':code,
        'wall_seconds':time.monotonic()-began,'log_sha256':file_sha256(stage/f'{action}.log'),'result_files':outputs})
    print(f'S5_CORRECTED_STEP_{"OK" if code==0 else "FAILED"} action={action} completed=true exit={code}',flush=True)
    return code


def status(stage,binding):
    for action in ['test',*ORDER]:
        p=stage/f'{action}.completed.json'
        if p.exists():
            value=read_json(p) if action=='test' else verify_step(stage,action,binding)
            print(f'S5_STATUS action={action} completed=true exit={value["exit_code"]} wall_seconds={value.get("wall_seconds")}',flush=True)
        else:print(f'S5_STATUS action={action} completed=false',flush=True)
    launch=stage/'evaluate.launch.json'
    if launch.exists():
        pid=read_json(launch)['pid']
        try:os.kill(pid,0);running=True
        except ProcessLookupError:running=False
        print(f'S5_PROCESS action=evaluate pid={pid} running={str(running).lower()}',flush=True)
    log=stage/'evaluate.log'
    if log.exists():print('\n'.join(log.read_text(encoding='utf-8').splitlines()[-12:]),flush=True)
    return 0


def export(stage,kind,binding):
    last='generate' if kind=='data' else 'summarize';actions=ORDER[:ORDER.index(last)+1]
    completed={};failures={}
    for action in actions:
        if not (stage/f'{action}.completed.json').exists():
            if (stage/f'{action}.attempt.json').exists():failures[action]={'reason':'interrupted_without_completion'};break
            require(bool(failures),'not ready to export; missing step '+action);break
        value=verify_step(stage,action,binding);completed[action]=value
        if value['exit_code']!=0:
            failures[action]={'exit_code':value['exit_code'],'log_tail':(stage/f'{action}.log').read_text(encoding='utf-8').splitlines()[-100:]};break
    run=stage/'run'
    report_path=run/('data_manifest.json' if kind=='data' else 'confirmation_report.json')
    report=read_json(report_path) if report_path.exists() else None
    if not failures:require(last in completed and report is not None,'incomplete export')
    failure_units={str(p.relative_to(run)):read_json(p) for p in run.rglob('failure.json')} if run.exists() else {}
    result={'schema_version':'cpmt-s5-corrected-export-v1','kind':kind,'binding':binding,'completion':completed,
        'full_test':read_json(stage/'test.completed.json'),'engineering_pass':not failures and not failure_units,
        'failures':failures,'failure_units':failure_units,'report':report,
        'report_sha256':file_sha256(report_path) if report is not None else None,
        'validation_trial_consumed':(run/'validation_trial.json').exists(),'test_access':False,'formal_test_release':False}
    path=ROOT/EXPORTS[kind]
    if path.exists():require(read_json(path)==result,'different export exists; preserve and review')
    else:
        # Full per-sequence metrics remain present. Compact JSON avoids paying
        # for deeply indented repeated metric names in Git-sized exports.
        with path.open('x',encoding='utf-8') as stream:
            json.dump(result,stream,sort_keys=True,separators=(',',':'),allow_nan=False)
            stream.write('\n')
    print(f'EXPORT_VERIFIED path={path} sha256={file_sha256(path)}',flush=True)
    print(f'S5_EXPORT_OK kind={kind} engineering_pass={str(result["engineering_pass"]).lower()}',flush=True)
    return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['test',*ORDER,'status','export-data','export-confirmation'])
    parser.add_argument('--foreground',action='store_true');args=parser.parse_args()
    clean_checkout();binding=current_binding()
    stage=OUTPUT_ROOT/('m1-v7-d055-s5-'+binding['science']['source_and_tests_sha256'][:12]);stage.mkdir(parents=True,exist_ok=True)
    print(f'S5_STAGE id=m1_v7_d055_s5_{args.action} action={args.action} output={stage} test_access=false',flush=True)
    if args.action=='status':return status(stage,binding)
    import fcntl
    with (stage/'phase.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|(0 if os.environ.get('CPMT_S5_WAIT_LOCK')=='1' else fcntl.LOCK_NB))
        except BlockingIOError:
            print('S5_BUSY completed=false; use status; requested action was NOT executed',flush=True);return 2
        if args.action=='test':return run_test(stage,binding)
        if args.action.startswith('export-'):return export(stage,args.action[7:],binding)
        if args.action=='evaluate' and not args.foreground:
            prerequisites(stage,args.action,binding)
            if (stage/'evaluate.completed.json').exists():return run_step(stage,'evaluate',binding)
            require(not (stage/'evaluate.launch.json').exists() and not (stage/'evaluate.attempt.json').exists(),'previous launch retained; no automatic restart')
            with (stage/'evaluate.worker.log').open('x',encoding='utf-8') as log:
                process=subprocess.Popen([sys.executable,str(Path(__file__)),'evaluate','--foreground'],cwd=ROOT,
                    env={**os.environ,'CPMT_S5_WAIT_LOCK':'1'},stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            write_json(stage/'evaluate.launch.json',{'binding':binding,'pid':process.pid})
            print(f'S5_STARTED action=evaluate pid={process.pid} completed=false; this is launch only',flush=True)
            print('NEXT=bash ops/m1_corrected_confirmation.sh status',flush=True);return 0
        return run_step(stage,args.action,binding)


if __name__=='__main__':raise SystemExit(main())
