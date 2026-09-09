"""Foreground test/check/export delivery for the bounded GPU process check."""
from pathlib import Path
import argparse
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts'), str(ROOT / 'ops')]
from cpmt.m1_s5_training import read_json, write_json, require
from cpmt.run_provenance import source_tree_sha256, capture_run_provenance, file_sha256
from m1_candidate_availability import command, run_test
from run_m1_parallel_training_check import no_active_probe, fixed_plan
from m1_training_jobs import compare_artifacts

EXPORT = ROOT / 'results/m1_v7_d054_training_process_check.json'


def verify(stage, binding):
    complete = read_json(stage / 'check.completed.json')
    require(complete['binding'] == binding, 'check binding changed')
    require(file_sha256(stage / 'check.log') == complete['log_sha256'], 'check log changed')
    files = {p.relative_to(stage / 'run').as_posix(): file_sha256(p)
             for p in (stage / 'run').rglob('*') if p.is_file()}
    require(files == complete['files'], 'check outputs changed')
    report_path = stage / 'run/report.json'
    report = read_json(report_path) if report_path.exists() else None
    if report:
        require(report['binding']['plan'] == fixed_plan(), 'check plan changed')
        require(report['binding']['source_and_tests_sha256'] == binding['source_and_tests_sha256'], 'report source mismatch')
        require(report['training_jobs_executed'] == 96 and report['compared_jobs'] == 48, 'incomplete job matrix')
        expected = all(v['pass'] for mode in report['comparisons'].values() for v in mode.values())
        require(report['pass'] == expected and complete['exit_code'] == (0 if expected else 1), 'check gate/exit mismatch')
    else: require(complete['exit_code'] != 0, 'success without check report')
    return complete, report


def check(stage, binding):
    # Guard runs before any new attempt or child process.
    no_active_probe()
    tested = read_json(stage / 'test.completed.json')
    require(tested['binding'] == binding and tested['exit_code'] == 0, 'current full test must pass')
    require(file_sha256(stage / 'test.log') == tested['log_sha256'], 'test log changed')
    if (stage / 'check.completed.json').exists():
        completed, _ = verify(stage, binding)
        print('PARALLEL_TRAINING_CHECK_REUSED exit=' + str(completed['exit_code']))
        return completed['exit_code']
    require(not (stage / 'check.attempt.json').exists() and not (stage / 'run').exists(), 'incomplete attempt retained; no retry')
    require(shutil.disk_usage(stage).free >= 5 * 2**30, 'need 5 GiB free for small check artifacts')
    write_json(stage / 'check.attempt.json', {'binding': binding})
    began = time.monotonic()
    code = command([sys.executable, 'scripts/run_m1_parallel_training_check.py', '--output', str(stage / 'run')],
                   stage / 'check.log')
    files = {p.relative_to(stage / 'run').as_posix(): file_sha256(p)
             for p in (stage / 'run').rglob('*') if p.is_file()}
    write_json(stage / 'check.completed.json', {'binding': binding, 'exit_code': code,
        'wall_seconds': time.monotonic()-began, 'log_sha256': file_sha256(stage / 'check.log'), 'files': files})
    verify(stage, binding)
    print(f'PARALLEL_TRAINING_CHECK_EXIT={code}', flush=True)
    print('NEXT=bash ops/m1_parallel_training_check.sh export', flush=True)
    return code


def export(stage, binding):
    completed, report = verify(stage, binding)
    if report:
        for mode in ['budget', 'refit']:
            a = report['layouts'][f'{mode}_1']['artifacts']
            b = report['layouts'][f'{mode}_4']['artifacts']
            require(a.keys() == b.keys() == report['comparisons'][mode].keys(), 'export matrix mismatch')
            for key in a:
                require(compare_artifacts(a[key], b[key]) == report['comparisons'][mode][key], 'numerical comparison changed')
    failed_jobs = {}
    for path in (stage / 'run').rglob('process.completed.json'):
        marker = read_json(path)
        if marker['exit_code'] != 0:
            failed_jobs[path.parent.relative_to(stage / 'run').as_posix()] = {
                'completion': marker, 'request': read_json(path.parent / 'request.json'),
                'log_tail': (path.parent / 'worker.log').read_text(encoding='utf-8').splitlines()[-100:]}
    payload = {'schema_version': 'cpmt-training-process-check-export-v1', 'completion': completed,
        'report': report, 'full_test': read_json(stage / 'test.completed.json'),
        'failed_jobs': failed_jobs,
        'failure': read_json(stage / 'run/failure.json') if (stage / 'run/failure.json').exists() else None,
        'log_tail': (stage / 'check.log').read_text(encoding='utf-8').splitlines()[-100:],
        'formal_budget_authorized': False, 'validation_access': False, 'test_access': False}
    if EXPORT.exists(): require(read_json(EXPORT) == payload, 'different prior export retained')
    else: write_json(EXPORT, payload)
    require(read_json(EXPORT) == payload, 'export readback mismatch')
    print(f'EXPORT_VERIFIED path={EXPORT} sha256={file_sha256(EXPORT)}', flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['test', 'check', 'export'])
    action = parser.parse_args().action
    no_active_probe()  # Also avoid a full-suite CPU load during current latency measurement.
    source = source_tree_sha256(ROOT, roots=('src', 'scripts', 'configs', 'tests'))
    binding = {'source_and_tests_sha256': source, 'plan': fixed_plan(),
        'ops_sha256': file_sha256(Path(__file__)), 'shell_sha256': file_sha256(ROOT / 'ops/m1_parallel_training_check.sh'),
        'test_delivery_sha256': file_sha256(ROOT / 'ops/m1_candidate_availability.py')}
    if action != 'export':
        from m1_corrected_training_plan import require_clean_science
        require_clean_science()
    stage = Path('/root/autodl-tmp/cpmt_outputs') / ('m1-v7-d054-training-process-check-' + source[:12])
    stage.mkdir(parents=True, exist_ok=True)
    print(f'PARALLEL_TRAINING_CHECK_STAGE action={action} output={stage} formal_budget_authorized=false', flush=True)
    import fcntl
    with (stage / 'phase.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        code = {'test': run_test, 'check': check, 'export': export}[action](stage, binding)
        require(source_tree_sha256(ROOT, roots=('src', 'scripts', 'configs', 'tests')) == source, 'source changed during check')
        return code


if __name__ == '__main__': raise SystemExit(main())
