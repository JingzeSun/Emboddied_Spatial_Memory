"""D-090 fixed 16/144 revision: check, public seal, independent evaluation, export.

Original artifacts are immutable. A failed or interrupted step is never restarted.
Successful steps are reused only after checking receipts and original byte hashes.
"""
import argparse
import gzip
import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import signal
import subprocess
import sys
import time
import unittest
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests/spatial_world_model')]
CONFIG='configs/spatial_history/r4_frontend_stage_v2r1.json'
CFG=json.loads((ROOT/CONFIG).read_text())
RUN=Path(CFG['run_directory']); SOURCE=Path(CFG['source_directory'])
REPORT=ROOT/CFG['report']; STAGE=CFG['stage']


def require(value,message):
    if not value:raise ValueError(message)


def encode(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def record(path):
    digest=hashlib.sha256(); size=0
    with path.open('rb') as handle:
        for block in iter(lambda:handle.read(1024**2),b''):
            digest.update(block);size+=len(block)
    return {'bytes':size,'sha256':digest.hexdigest()}


def read(path):
    with (gzip.open(path,'rt') if path.suffix=='.gz' else path.open()) as handle:return json.load(handle)


def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args]).decode().strip()


def verify_parent_bytes():
    path=ROOT/CFG['source_report']
    require(record(path)['sha256']==CFG['source_report_sha256'],'original report hash')
    # Hash only: the old report contains private evaluation values.


def bound_files():
    verify_parent_bytes()
    return sorted(set(CFG['source_code_files']) | {CONFIG,
        'src/spatial_world_model/r4_object_surfaces.py','src/spatial_world_model/r4_observed_map_v2.py',
        'src/spatial_world_model/r4_control_bridge_v2.py','tests/spatial_world_model/test_r4_frontend_v2.py',
        'ops/spatial_history/r4_frontend_stage_v2r1.py','tests/spatial_world_model/test_r4_frontend_isolation.py','docs/DECISIONS.md'})


def binding():return {name:record(ROOT/name) for name in bound_files()}


def used():return sum(p.stat().st_size for p in RUN.rglob('*') if p.is_file()) if RUN.exists() else 0


def write(path,value):
    raw=encode(value)
    if path.suffix=='.gz':raw=gzip.compress(raw,mtime=0)
    require(used()+len(raw)<=CFG['limits']['stage_bytes']-CFG['limits']['report_bytes'],'stage storage limit')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as handle:handle.write(raw)
    return record(path)


def inventory(directory):return {p.relative_to(RUN).as_posix():record(p) for p in sorted(directory.rglob('*')) if p.is_file()}


def verify_step(step):
    directory=RUN/step
    require((directory/'receipt.json').is_file() and not (directory/'failure.json').exists(),'missing/failed step '+step)
    receipt=read(directory/'receipt.json')
    require(receipt['exit_code']==0 and receipt['stage']==STAGE,'step exit/stage')
    for name,expected in receipt['binding'].items():
        blob=subprocess.check_output(['git','-C',str(ROOT),'show',receipt['commit']+':'+name])
        require({'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest()}==expected,'original code changed '+name)
    files=inventory(directory);files.pop(step+'/receipt.json')
    require(files==receipt['files'],'step evidence changed '+step)
    return receipt


def start(step):
    directory=RUN/step
    if directory.exists():
        result=verify_step(step)
        require(result['binding']==binding(),'successful step belongs to different source version')
        print(STAGE,step,'REUSED exit=0',flush=True)
        return None
    require(not git('status','--porcelain','--',*bound_files()),'bound sources must be committed and clean')
    require(shutil.disk_usage(SOURCE).free>=CFG['limits']['stage_bytes']-used(),'insufficient stage disk budget')
    source=binding();commit=git('rev-parse','HEAD')
    for name,expected in source.items():
        raw=subprocess.check_output(['git','-C',str(ROOT),'show',commit+':'+name])
        require(hashlib.sha256(raw).hexdigest()==expected['sha256'],'Git/source byte mismatch')
    write(directory/'started.json',{'stage':STAGE,'step':step,'commit':commit,'binding':source,
          'time_utc':datetime.now(timezone.utc).isoformat(),'parent_report':record(ROOT/CFG['source_report'])})
    return time.monotonic()


def finish(step,began,extra):
    started=read(RUN/step/'started.json')
    require(binding()==started['binding'],'source changed during step')
    value={**started,'exit_code':0,'elapsed_s':time.monotonic()-began,
           'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
           'files':inventory(RUN/step),**extra}
    write(RUN/step/'receipt.json',value)
    verify_step(step)
    print(STAGE,step,'COMPLETE exit=0',flush=True)


def source_file(name,registration):
    require(name in registration,'unregistered original input')
    path=SOURCE/name
    require(path.resolve().is_relative_to(SOURCE.resolve()),'source path escape')
    require(record(path)==registration[name],'original input changed '+name)
    return path


def public_read_guard(event,args):
    if event!='open' or not isinstance(args[0],(str,bytes,os.PathLike)):
        return
    path=Path(os.fsdecode(args[0])).resolve()
    if path.is_relative_to(SOURCE.resolve()):
        relative=path.relative_to(SOURCE.resolve()).as_posix()
        require(relative in CFG['public_registration'],'public process forbidden original read: '+relative)


def dependency(step):
    value=verify_step(step)
    require(value['binding']==binding(),'dependency source differs')
    return value


def check():
    began=start('check')
    if began is None:return
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(importlib.import_module(name))
                             for name in ('test_r4_frontend_v2','test_r4_frontend_isolation'))
    require(suite.countTestCases()==CFG['check_test_count'],'test census')
    class Tee:
        def __init__(self,log):self.log=log
        def write(self,text):self.log.write(text);sys.stdout.write(text);self.flush()
        def flush(self):self.log.flush();sys.stdout.flush()
    with (RUN/'check/tests.log').open('x') as log:
        result=unittest.TextTestRunner(stream=Tee(log),verbosity=2).run(suite)
    require(result.wasSuccessful() and not result.skipped and not result.expectedFailures,'checks failed')
    finish('check',began,{'tests_run':result.testsRun,'failures':0,'errors':0,'skipped':0})


def predict():
    checked=dependency('check')
    began=start('public')
    if began is None:return
    from spatial_world_model import r4_object_association as objects, r4_observed_map_v2 as maps
    from spatial_world_model import r4_control_bridge_v2 as bridge, r4_control_proxy as dynamics, r4_proxy_readout as readout
    from spatial_world_model.r4_query_v2 import from_public_query, SOURCE_VERSION, domain_spec
    registration=CFG['public_registration']; sources={};worlds=[]
    sys.addaudithook(public_read_guard)
    for family in CFG['families']:
        for world in CFG['worlds']:
            name=f'execution/{family}/data/public/{world}.json.gz'
            path=source_file(name,registration);sources[name]=registration[name];value=read(path)
            require(len(value['actions'])==9,'nine original actions')
            from_public_query({'schema_version':SOURCE_VERSION,'history':value['history'],
                               'controls':value['actions'][0],'goal':value['goal']})
            frames=[{k:f[k] for k in objects.FIELDS.split()} for f in value['history']]
            for i,f in enumerate(frames):f['time_s']=(i-120)/10
            mapped=maps.build_map({'schema_version':maps.HISTORY_VERSION,'frames':frames},
                                 objects.sensor_spec(),objects.common_shape_spec(),maps.parameters())
            stem=RUN/'public'/family/world
            write(stem/'map.json.gz',mapped)
            row={'family':family,'world':world,'association_status':mapped['current_object']['status'],
                 'opening_count':len(readout.public_openings(mapped)),'branches':[]}
            print(STAGE,'MAP',family,world,row['association_status'],'openings='+str(row['opening_count']),flush=True)
            for action,control in zip(CFG['actions'],value['actions']):
                controls={k:[r[k] for r in control] for k in ('ee_velocity_mps','duration_s')}
                proxy=bridge.predict_control(mapped,controls,domain_spec(),dynamics.parameters())
                task=readout.readout(mapped,proxy,value['goal'],readout.parameters())
                require(proxy['main_prediction'] is None and not proxy['eligible_for_P'] and task['formal_prediction'] is None,'formal scope')
                write(stem/(action+'.json.gz'),{'proxy':proxy,'task':task})
                row['branches'].append({'action':action,'proxy_status':proxy['status'],'task_status':task['status']})
                print(STAGE,'PUBLIC',family,world,action,proxy['status'],task['status'],flush=True)
            worlds.append(row)
    for name in sources:source_file(name,registration)
    write(RUN/'public/seal.json',{'stage':STAGE,'worlds':worlds,'sources':sources,'private_truth_read':False,
                                'check_receipt':record(RUN/'check/receipt.json'),'files':inventory(RUN/'public')})
    finish('public',began,{'history_count':16,'branch_count':144,'private_truth_read':False})


def evaluate():
    sealed=dependency('public')
    process_exit=read(RUN/'predict_exit.json')
    require(process_exit['exit_code']==0 and process_exit['receipt']==record(RUN/'public/receipt.json'),
            'public child process must exit successfully before private evaluation')
    began=start('evaluation')
    if began is None:return
    from spatial_world_model import r4_proxy_audit as evaluator
    from r4_map_control_check import actual_geometry
    registration=CFG['truth_registration'];sources={};worlds=[]
    for family in CFG['families']:
        for world in CFG['worlds']:
            mapped=read(RUN/'public'/family/world/'map.json.gz')
            name=f'execution/{family}/data/audit/{world}/world.xml'
            boxes,floor=actual_geometry(source_file(name,registration));sources[name]=registration[name]
            row={'family':family,'world':world,'map':evaluator.compare_map(mapped,boxes,floor),
                 'frame_audit':mapped['frame_audit'],'association_status':mapped['current_object']['status'],
                 'current_object':mapped['current_object'],'branches':[]}
            for action in CFG['actions']:
                prediction=read(RUN/'public'/family/world/(action+'.json.gz'))
                trace=f'execution/{family}/data/audit/{world}/primary-{action}/trajectory.jsonl.gz'
                label=f'execution/{family}/data/labels/{world}-{action}.json.gz'
                with gzip.open(source_file(trace,registration),'rt') as handle:actual=[json.loads(line) for line in handle if line.strip()]
                target=read(source_file(label,registration))
                require(target['trajectory']==registration[trace],'label/trace binding')
                sources[trace]=registration[trace];sources[label]=registration[label]
                metrics=evaluator.compare_branch(prediction['proxy'],prediction['task'],actual,target['labels'])
                metrics['object_association']=evaluator.compare_object(mapped['current_object'],actual[0])
                row['branches'].append({'action':action,'opening_count':len(prediction['task']['openings']),**metrics})
            row['selection']=evaluator.nominal_selection(row['branches'])
            write(RUN/'evaluation'/(family+'-'+world+'.json.gz'),row);worlds.append(row)
            print(STAGE,'EVALUATED',family,world,'exit=0',flush=True)
    for name in sources:source_file(name,registration)
    branches=[b for w in worlds for b in w['branches']]
    actual={'resolved_histories':sum(w['association_status']=='association_ready' for w in worlds),
            'two_opening_histories':sum(all(b['opening_count']==2 for b in w['branches']) for w in worlds),
            'nominal_complete_branches':sum(b['proxy_status']=='nominal_complete' for b in branches),
            'task_readout_branches':sum(b['nominal_success'] is not None for b in branches),
            'selection_histories':sum(w['selection']['status']=='diagnostic_only' for w in worlds),
            'false_free_cells':sum(w['map']['false_free_cells'] for w in worlds),
            'false_occupied_cells':sum(round(w['map']['nominal_occupied_cells']*(1-w['map']['occupied_cell_precision']))
                                       for w in worlds if w['map']['nominal_occupied_cells'])}
    require(len(worlds)==16 and len(branches)==144 and len(sources)==304,'fixed evaluation census')
    summary={'stage':STAGE,'worlds':worlds,'source_truth_files':sources,'history_count':16,'branch_count':144,
             'acceptance_observed':actual,'acceptance_required':CFG['acceptance'],'engineering_accepted':actual==CFG['acceptance'],
             'formal_model_ready':False,'public_receipt':record(RUN/'public/receipt.json'),
             'new_simulation_steps':0,'new_training_steps':0,'new_weight_download_bytes':0}
    write(RUN/'evaluation/summary.json',summary)
    finish('evaluation',began,{'engineering_accepted':summary['engineering_accepted']})


def run():
    for command,step in (('check','check'),('predict','public'),('evaluate','evaluation')):
        path=RUN/(command+'_exit.json')
        if path.exists():
            value=read(path)
            require(value['exit_code']==0,'failed child preserved: '+command)
            dependency(step)
            require(value['receipt']==record(RUN/step/'receipt.json'),'child receipt changed')
            print(STAGE,command,'PROCESS REUSED exit=0',flush=True)
            continue
        began=time.monotonic()
        process=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),command],cwd=ROOT)
        try:
            code=process.wait()
        except BaseException as error:
            process.kill();process.wait()
            write(path,{'command':command,'exit_code':process.returncode,'elapsed_s':time.monotonic()-began,
                        'error':type(error).__name__})
            raise
        result={'command':command,'exit_code':code,'elapsed_s':time.monotonic()-began}
        if code==0:result['receipt']=record(RUN/step/'receipt.json')
        write(path,result)
        require(code==0,'child failed; preserve and export: '+command)
    print(STAGE,'RUN COMPLETE engineering_accepted='+str(read(RUN/'evaluation/summary.json')['engineering_accepted']),'exit=0',flush=True)


def export():
    errors={}
    for step in ('check','public','evaluation'):
        try:verify_step(step)
        except Exception as e:errors[step]=str(e)
    summary=read(RUN/'evaluation/summary.json') if (RUN/'evaluation/summary.json').exists() else None
    artifacts={}
    for step in ('check','public','evaluation'):
        for name in ('started.json','receipt.json','failure.json','tests.log'):
            path=RUN/step/name
            if path.exists():artifacts[step+'/'+name]={**record(path),'text':path.read_text()}
    value={'stage':STAGE,'status':'passed' if not errors else 'failed_or_incomplete','verification_errors':errors,
           'summary':summary,'source_artifacts':artifacts,'stage_inventory':inventory(RUN),
           'formal_model_ready':False,'configuration':CFG,'exporter':record(Path(__file__))}
    raw=encode(value);require(len(raw)<=CFG['limits']['report_bytes'],'report byte limit')
    if REPORT.exists():require(REPORT.read_bytes()==raw,'different existing report; preserve it')
    else:
        with REPORT.open('xb') as handle:handle.write(raw)
    print(STAGE,'EXPORTED',value['status'],'path='+str(REPORT),'exit=0',flush=True)


def main():
    require(platform.system()=='Linux','server only')
    parser=argparse.ArgumentParser();parser.add_argument('step',choices=['check','predict','evaluate','run','verify','export']);args=parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS,(CFG['limits']['process_bytes'],)*2)
    def timeout(signum,frame):raise TimeoutError('step time limit; preserve state')
    signal.signal(signal.SIGALRM,timeout)
    remaining=(datetime.fromisoformat(CFG['deadline_utc'].replace('Z','+00:00'))-datetime.now(timezone.utc)).total_seconds()
    if args.step in ('verify','export'):
        signal.alarm(CFG['limits']['check_wall_s'])
    else:
        require(remaining>1,'authorized server window expired')
        signal.alarm(int(min(remaining,CFG['limits']['check_wall_s'] if args.step=='check' else CFG['limits']['run_wall_s'])))
    step={'predict':'public','evaluate':'evaluation'}.get(args.step,args.step)
    try:
        if args.step=='verify':
            for name in ('check','public','evaluation'):verify_step(name)
            print(STAGE,'VERIFIED exit=0',flush=True)
        else:globals()[args.step]()
    except BaseException as e:
        path=RUN/step/'failure.json'
        if (RUN/step/'started.json').exists() and not (RUN/step/'receipt.json').exists() and not path.exists():
            write(path,{'exit_code':1,'error':f'{type(e).__name__}: {e}','stage':STAGE,'step':step})
        raise


if __name__=='__main__':main()
