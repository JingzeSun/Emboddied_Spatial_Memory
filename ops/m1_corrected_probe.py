"""Deliver the fixed corrected anchor; short steps foreground, long evaluation background."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts'), str(ROOT / 'ops')]
from cpmt.m1_s5_training import read_json, write_json, require
from cpmt.m1_s5_confirmation import verify_unit
from cpmt.run_provenance import file_sha256, capture_run_provenance, source_tree_sha256
from m1_candidate_availability import run_test, command
from m1_train_preflight import capacity
from run_m1_corrected_probe import contracts, registration, REUSE_SHA

EXPORT = ROOT / 'results/m1_v7_d054_corrected_endpoint_probe.json'
ORDER = ['prepare', 'train', 'evaluate', 'summarize']


def binding_now():
    # Metadata only; do not open train arrays in test/status/export.
    _, _, science = contracts()
    return {'science': science, 'source_and_tests_sha256': science['source_and_tests_sha256'],
        'ops_sha256': file_sha256(Path(__file__)), 'shell_sha256': file_sha256(ROOT / 'ops/m1_corrected_probe.sh'),
        'test_delivery_sha256': file_sha256(ROOT / 'ops/m1_candidate_availability.py')}


def verify_step(stage, action, binding):
    marker = read_json(stage / f'{action}.completed.json')
    require(marker['binding'] == binding, 'completed step source changed')
    require(file_sha256(stage / f'{action}.log') == marker['log_sha256'], 'completed log changed')
    return marker


def prerequisite(stage, action, binding):
    tested = read_json(stage / 'test.completed.json')
    require(tested['binding'] == binding and tested['exit_code'] == 0, 'current full test must pass')
    require(file_sha256(stage / 'test.log') == tested['log_sha256'], 'test log changed')
    for previous in ORDER[:ORDER.index(action)]:
        require(verify_step(stage, previous, binding)['exit_code'] == 0, 'prior step failed: ' + previous)


def run_step(stage, action, binding):
    prerequisite(stage, action, binding)
    if (stage / f'{action}.completed.json').exists():
        m = verify_step(stage, action, binding)
        print(f"CORRECTED_PROBE_REUSED action={action} exit={m['exit_code']}", flush=True)
        return m['exit_code']
    attempt = stage / f'{action}.attempt.json'
    require(not attempt.exists(), 'previous incomplete attempt retained; review required, no automatic restart')
    resources = capacity()
    require(shutil.disk_usage(stage).free >= 20 * 2**30, 'need 20 GiB free for preserved audits/checkpoints')
    write_json(attempt, {'binding': binding, 'resources': resources,
                        'provenance': capture_run_provenance(ROOT, component='corrected_probe_' + action)})
    print('PROBE_RESOURCES=' + json.dumps(resources), flush=True)
    began = time.monotonic()
    code = command([sys.executable, 'scripts/run_m1_corrected_probe.py', action,
                    '--output', str(stage / 'run'), '--workers', str(resources['workers'])],
                   stage / f'{action}.log')
    require(binding_now() == binding, 'source changed during phase; retain outputs for review')
    write_json(stage / f'{action}.completed.json', {'binding': binding, 'exit_code': code,
        'wall_seconds': time.monotonic()-began, 'log_sha256': file_sha256(stage / f'{action}.log')})
    print(f"CORRECTED_PROBE_STEP_{'OK' if code == 0 else 'FAILED'} action={action} exit={code}", flush=True)
    return code


def export(stage, binding):
    completions = {a: verify_step(stage, a, binding) for a in ORDER
                   if (stage / f'{a}.completed.json').exists()}
    require(completions, 'no completed calculation to export')
    report = registered = None
    unit_path = stage / 'run/summary'
    if unit_path.exists():
        verify_unit(unit_path, binding['science'])
        report = read_json(unit_path / 'report.json')
        registered = read_json(unit_path / 'registration.json')
        _, rebuild, _ = contracts()
        require(registered == registration(report, rebuild), 'registration mismatch')
        for key, recorded in report['causal_files'].items():
            short, seed = key.split('_')
            path = stage / 'run/oracle' if short == 'F' else stage / 'run/causal' / key
            unit_binding = {**binding['science'], 'method': short, 'seed': None if seed == 'None' else int(seed)}
            require(verify_unit(path, unit_binding) == recorded, 'causal evidence changed')
    if report is None:
        require(any(m['exit_code'] != 0 for m in completions.values()), 'run incomplete; export after summarize')
    failures = {}
    for path in (stage / 'run').rglob('failure.json'):
        failures[path.relative_to(stage / 'run').as_posix()] = read_json(path)
    payload = {'schema_version': 'cpmt-corrected-probe-export-v1', 'binding': binding,
        'completion': completions, 'full_test': read_json(stage / 'test.completed.json'),
        'endpoint_probe': report, 'post_probe_registration': registered, 'failures': failures,
        'failed_log_tails': {a: (stage / f'{a}.log').read_text(encoding='utf-8').splitlines()[-100:]
                            for a, m in completions.items() if m['exit_code'] != 0},
        'test_access': False, 'validation_access': False, 'formal_budget_authorized': False}
    if EXPORT.exists():
        require(read_json(EXPORT) == payload, 'different prior export retained')
    else:
        write_json(EXPORT, payload)
    require(read_json(EXPORT) == payload, 'export readback mismatch')
    print(f'EXPORT_VERIFIED path={EXPORT} sha256={file_sha256(EXPORT)}', flush=True)
    print('CORRECTED_PROBE_EXPORT_OK registration_created=' + str(registered is not None).lower(), flush=True)
    return 0


def status(stage, binding):
    launch = stage / 'evaluate.launch.json'
    if launch.exists() and not (stage / 'evaluate.completed.json').exists():
        launched = read_json(launch)
        require(launched['binding'] == binding, 'launch binding changed')
        cmdline = Path(f"/proc/{launched['pid']}/cmdline")
        running = cmdline.exists() and b'm1_corrected_probe.py' in cmdline.read_bytes()
        print(f"PROBE_EVALUATION_PROCESS pid={launched['pid']} running={str(running).lower()}")
        if not running:
            print('EVALUATION_INCOMPLETE_REVIEW_REQUIRED no automatic restart')
    for action in ['test', *ORDER]:
        path = stage / f'{action}.completed.json'
        if path.exists():
            value = read_json(path)
            require(value['binding'] == binding, 'status source mismatch')
            print(f"PROBE_STATUS action={action} completed=true exit={value['exit_code']}")
        else:
            print(f"PROBE_STATUS action={action} completed=false")
    log = stage / ('evaluate.worker.log' if (stage / 'evaluate.worker.log').exists() else 'evaluate.log')
    if log.exists():
        with log.open('rb') as f:
            f.seek(max(0, log.stat().st_size - 4096))
            print(f.read().decode('utf-8', errors='replace'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['test', *ORDER, 'status', 'export'])
    parser.add_argument('--foreground', action='store_true')
    args = parser.parse_args()
    import fcntl
    binding = binding_now()
    stage = Path('/root/autodl-tmp/cpmt_outputs') / ('m1-v7-d054-fixed-probe-' + binding['source_and_tests_sha256'][:12])
    stage.mkdir(parents=True, exist_ok=True)
    print(f'CORRECTED_PROBE_STAGE action={args.action} output={stage} validation=false test_access=false', flush=True)
    if args.action == 'status':
        status(stage, binding)
        return 0
    if args.action != 'export':
        require(not capture_run_provenance(ROOT, component='corrected_probe_ops')['git_dirty'], 'clean checkout required')
    with (stage / 'phase.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | (0 if os.environ.get('CPMT_PROBE_WAIT_LOCK') == '1' else fcntl.LOCK_NB))
        if args.action == 'test':
            result = run_test(stage, binding)
        elif args.action == 'evaluate' and not args.foreground:
            prerequisite(stage, args.action, binding)
            if (stage / 'evaluate.completed.json').exists():
                return verify_step(stage, 'evaluate', binding)['exit_code']
            require(not (stage / 'evaluate.launch.json').exists() and not (stage / 'evaluate.attempt.json').exists(),
                    'evaluation already launched; use status, no duplicate start')
            # Release phase lock on return; child blocks on a separate invocation
            # until then. A durable launch marker prevents any second launcher.
            with (stage / 'evaluate.worker.log').open('x', encoding='utf-8') as log:
                child = subprocess.Popen([sys.executable, str(Path(__file__)), 'evaluate', '--foreground'],
                    cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                    start_new_session=True, env={**os.environ, 'CPMT_PROBE_WAIT_LOCK': '1'})
            write_json(stage / 'evaluate.launch.json', {'pid': child.pid, 'binding': binding})
            print(f'CORRECTED_PROBE_STARTED action=evaluate pid={child.pid} log={stage / "evaluate.worker.log"}')
            print('NEXT=bash ops/m1_corrected_probe.sh status; keep checkout unchanged while running')
            return 0
        elif args.action == 'export': result = export(stage, binding)
        else: result = run_step(stage, args.action, binding)
        require(binding_now() == binding, 'source changed during phase')
        return result


if __name__ == '__main__':
    raise SystemExit(main())
