"""Stage commands delivered together; durable success reuse and explicit exports.

Budget defaults to background; refit uses its measured budget-based estimate.
All checks remain foreground. No
validation/test command exists here. A failed/partial attempt is never retried.
"""
from __future__ import annotations
import argparse
import math
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts'), str(ROOT / 'ops')]
from cpmt.m1_s5_training import read_json, write_json, require
from cpmt.m1_s5_confirmation import verify_unit
from cpmt.run_provenance import source_tree_sha256, file_sha256
from m1_candidate_availability import command
from run_m1_parallel_training_check import no_active_probe
from m1_corrected_training_plan import PROBE_EXPORT, CHECK_EXPORT, require_clean_science
from run_m1_corrected_followon import ORDER, load_binding, completed_paths

EXPORTS = {key: f'results/m1_v7_d054_corrected_{key}.json' for key in ['checks', 'budget', 'refit']}


def binding_now():
    source = source_tree_sha256(ROOT, roots=('src', 'scripts', 'configs', 'tests'))
    return {'source_and_tests_sha256': source, 'ops_sha256': file_sha256(Path(__file__)),
        'shell_sha256': file_sha256(ROOT / 'ops/m1_corrected_followon.sh')}


def refit_runtime_estimate(stage):
    """Runtime-only planning from this machine's completed GPU budget paths."""
    report = read_json(stage / 'run/budget.report.json'); times = {'scorer': [], 'student': []}
    artifacts = [read_json(Path(p) / 'result.json') for p in report['artifacts'].values()]
    for architecture, methods in report['selected'].items():
        for method, selected in methods.items():
            for seed in [7, 19, 31, 43, 59]:
                matches = [r for r in artifacts if r['binding']['job']['architecture'] == architecture
                    and r['binding']['job']['method'] == method and r['binding']['job']['seed'] == seed
                    and r['binding']['job']['learning_rate'] == selected['learning_rate']
                    and r['binding']['job']['auxiliary_weight'] == selected['auxiliary_weight']]
                require(len(matches) == 1, 'runtime estimate requires unique registered budget path')
                r = matches[0]; maximum = max(r['binding']['job']['checkpoints'])
                # Retain 20% fixed overhead, scale the remainder by updates and
                # 1000/799 population, then add a 20% planning cushion.
                seconds = r['wall_seconds'] * (.2 + .8*selected['steps']/maximum) * (1000/799) * 1.2
                require(math.isfinite(seconds) and seconds > 0, 'invalid measured runtime')
                times['scorer' if method == 'outcome_scorer' else 'student'].append(seconds)
    return sum(max(sum(v)/4, max(v)) for v in times.values())


def verify_step(stage, action, binding):
    marker = read_json(stage / f'{action}.completed.json')
    require(marker['binding'] == binding and file_sha256(stage / f'{action}.log') == marker['log_sha256'], 'step binding/log changed')
    for name, digest in marker['result_files'].items(): require(file_sha256(stage / 'run' / name) == digest, 'completed report changed: ' + name)
    return marker


def prerequisite(stage, action, binding):
    # Reuse the exact current-source full suite from the GPU check. No duplicate
    # full test just because a different operations script consumes the result.
    checked = read_json(ROOT / CHECK_EXPORT)
    require(checked['full_test']['exit_code'] == checked['completion']['exit_code'] == 0 and checked['report']['pass'], 'process check must pass')
    require(checked['report']['binding']['source_and_tests_sha256'] == binding['source_and_tests_sha256'], 'process check source changed')
    for previous in ORDER[:ORDER.index(action)]:
        require(verify_step(stage, previous, binding)['exit_code'] == 0, 'prior stage failed: ' + previous)


def run_step(stage, action, binding):
    prerequisite(stage, action, binding)
    complete = stage / f'{action}.completed.json'
    if complete.exists():
        marker = verify_step(stage, action, binding)
        print(f'FOLLOWON_REUSED action={action} exit={marker["exit_code"]}', flush=True)
        return marker['exit_code']
    attempt = stage / f'{action}.attempt.json'
    require(not attempt.exists(), 'previous incomplete attempt retained; no automatic restart')
    write_json(attempt, {'binding': binding, 'action': action})
    began = time.monotonic()
    code = command([sys.executable, 'scripts/run_m1_corrected_followon.py', action, '--output', str(stage / 'run')], stage / f'{action}.log')
    require(binding_now() == binding, 'source changed while running; preserve evidence')
    names = {'prepare': ['binding.json', 'prepared/report.json'], 'capacity': ['capacity.report.json'],
        'interfaces': ['interfaces.report.json', 'ready.json'], 'budget': ['budget.report.json'], 'refit': ['refit.report.json']}[action]
    files = {n: file_sha256(stage / 'run' / n) for n in names if (stage / 'run' / n).exists()}
    if code == 0: require(len(files) == len(names), 'successful runner missing required report')
    write_json(complete, {'binding': binding, 'exit_code': code, 'wall_seconds': time.monotonic()-began,
        'result_files': files, 'log_sha256': file_sha256(stage / f'{action}.log')})
    print(f'FOLLOWON_STEP_{"OK" if code == 0 else "FAILED"} id=m1_v7_d054_followon_{action} action={action} exit={code}', flush=True)
    return code


def status(stage, binding):
    for action in ORDER:
        if (stage / f'{action}.completed.json').exists():
            marker = verify_step(stage, action, binding)
            print(f'FOLLOWON_STATUS action={action} completed=true exit={marker["exit_code"]}')
        else:
            launch = stage / f'{action}.launch.json'; running = False
            if launch.exists():
                saved = read_json(launch); require(saved['binding'] == binding, 'launch source changed')
                path = Path(f'/proc/{saved["pid"]}/cmdline')
                try: running = b'm1_corrected_followon.py' in path.read_bytes()
                except (FileNotFoundError, ProcessLookupError): pass
            print(f'FOLLOWON_STATUS action={action} completed=false running={str(running).lower()}')
            log = stage / f'{action}.log'
            if log.exists():
                with log.open('rb') as stream:
                    stream.seek(max(0, log.stat().st_size-3000)); print(stream.read().decode('utf-8', errors='replace'))
    return 0


def export(stage, kind, binding):
    actions = ORDER[:3] if kind == 'checks' else (ORDER[:4] if kind == 'budget' else ORDER)
    completions = {a: verify_step(stage, a, binding) for a in actions if (stage / f'{a}.completed.json').exists()}
    require(completions, 'no completed stage to export')
    failed = any(v['exit_code'] != 0 for v in completions.values())
    require(failed or set(completions) == set(actions), 'stage not complete; wait before export')
    run = stage / 'run'; reports = {}
    for name in ['capacity', 'interfaces', 'budget', 'refit']:
        if name not in actions: continue
        p = run / f'{name}.report.json'
        if p.exists(): reports[name] = read_json(p)
    if not failed:
        science = load_binding(run)
        if kind in ['budget', 'refit']:
            for name in ['scorers', 'students', 'c_weights']: completed_paths(run, name)
        if kind == 'refit':
            for name in ['refit_scorers', 'refit_students']: completed_paths(run, name)
        if kind == 'checks':
            for model in reports['interfaces']['models'].values():
                for path_key, hash_key in [('serial_path', 'serial_marker_sha256')]:
                    path = Path(model[path_key]); require(file_sha256(path / 'complete.json') == model[hash_key], 'serial evidence changed')
                    verify_unit(path, read_json(path / 'complete.json')['binding'])
                path = Path(model['model']['path'])
                require(file_sha256(path / 'complete.json') == model['model']['marker_sha256'], 'diagnostic model changed')
                verify_unit(path, read_json(path / 'complete.json')['binding'])
                for shard in model['parallel']['shards']:
                    path = Path(shard['path']); require(file_sha256(path / 'complete.json') == shard['marker_sha256'], 'interface shard changed')
                    verify_unit(path, read_json(path / 'complete.json')['binding'])
        require(all(reports[n]['pass'] for n in ['capacity', 'interfaces']), 'engineering gate failed')
    failures = {p.relative_to(run).as_posix(): read_json(p) for p in run.rglob('failure.json')}
    failed_jobs = {}
    for path in run.rglob('process.completed.json'):
        if read_json(path)['exit_code'] != 0:
            failed_jobs[path.parent.relative_to(run).as_posix()] = {'completion': read_json(path),
                'log_tail': (path.parent / 'worker.log').read_text(encoding='utf-8').splitlines()[-80:]}
    payload = {'schema_version': 'cpmt-corrected-followon-export-v1', 'kind': kind, 'binding': binding,
        'completion': completions, 'reports': reports, 'failures': failures, 'failed_jobs': failed_jobs,
        'pass': not failed, 'validation_access': False, 'test_access': False,
        'log_tails': {a: (stage / f'{a}.log').read_text(encoding='utf-8').splitlines()[-60:] for a,m in completions.items() if m['exit_code'] != 0}}
    path = ROOT / EXPORTS[kind]
    if path.exists(): require(read_json(path) == payload, 'different prior export retained; review before replacement')
    else: write_json(path, payload)
    require(read_json(path) == payload, 'export readback differs')
    print(f'EXPORT_VERIFIED path={path} sha256={file_sha256(path)}', flush=True)
    print(f'FOLLOWON_EXPORT_OK kind={kind} pass={str(not failed).lower()}', flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=[*ORDER, 'test', 'process-check', 'process-export', 'status',
        'export-checks', 'export-budget', 'export-refit'])
    parser.add_argument('--foreground', action='store_true')
    args = parser.parse_args(); no_active_probe(); require_clean_science()
    if args.action in ['test', 'process-check', 'process-export']:
        action = {'test': 'test', 'process-check': 'check', 'process-export': 'export'}[args.action]
        return subprocess.call([sys.executable, 'ops/m1_parallel_training_check.py', action], cwd=ROOT)
    binding = binding_now()
    stage = Path('/root/autodl-tmp/cpmt_outputs') / ('m1-v7-d054-followon-' + binding['source_and_tests_sha256'][:12])
    stage.mkdir(parents=True, exist_ok=True)
    print(f'FOLLOWON_STAGE id=m1_v7_d054_followon_{args.action} action={args.action} output={stage} validation=false test_access=false', flush=True)
    if args.action == 'status': return status(stage, binding)
    import fcntl
    with (stage / 'phase.lock').open('a') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | (0 if os.environ.get('CPMT_FOLLOWON_WAIT_LOCK') == '1' else fcntl.LOCK_NB))
        except BlockingIOError:
            print('FOLLOWON_ALREADY_RUNNING use status; no duplicate launched', flush=True)
            return 0
        if args.action.startswith('export-'): return export(stage, args.action[7:], binding)
        background = args.action == 'budget'  # Historical same-grid work exceeds 30 min even at four workers.
        if args.action == 'refit' and not args.foreground:
            prerequisite(stage, args.action, binding)
            estimate = refit_runtime_estimate(stage)
            background = estimate > 1800
            print(f'FOLLOWON_RUNTIME_ESTIMATE action=refit seconds={estimate:.1f} background={str(background).lower()} planning_only=true', flush=True)
        if background and not args.foreground:
            prerequisite(stage, args.action, binding)
            if (stage / f'{args.action}.completed.json').exists(): return run_step(stage, args.action, binding)
            launch = stage / f'{args.action}.launch.json'
            require(not launch.exists() and not (stage / f'{args.action}.attempt.json').exists(), 'previous launch retained; inspect status, no restart')
            with (stage / f'{args.action}.worker.log').open('x', encoding='utf-8') as stream:
                child = subprocess.Popen([sys.executable, str(Path(__file__)), args.action, '--foreground'], cwd=ROOT,
                    env={**os.environ, 'CPMT_FOLLOWON_WAIT_LOCK': '1'}, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            write_json(launch, {'binding': binding, 'pid': child.pid})
            print(f'FOLLOWON_STARTED action={args.action} pid={child.pid}; next: bash ops/m1_corrected_followon.sh status', flush=True)
            return 0
        return run_step(stage, args.action, binding)


if __name__ == '__main__': raise SystemExit(main())
