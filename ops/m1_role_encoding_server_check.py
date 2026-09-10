"""ROLE-S1/S2：服务器工程验收，run 后 verify；不训练正式模型。

输入为 Git 中的角色原型及既有测试；输出为新服务器的独立测试回执。
例如重新运行 9 项专项检查和 30 项旧路径回归，不复用故障电脑的成功记录。
这不是科学效果评测，也不读取已封存 test 或已有 S5 数据。
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'results/m1_d056_role_encoding_server_check.json'
SUITES = [('prototype', 'test_m1_role_encoding.py', 9), ('legacy', 'test_m1_af_rollout.py', 30)]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def code_binding():
    files = sorted((ROOT / 'src/cpmt').glob('*.py')) + [
        Path(__file__), ROOT / 'tests/test_m1_role_encoding.py', ROOT / 'tests/test_m1_af_rollout.py',
        ROOT / 'configs/m1_hard_condition_v7.json', ROOT / 'configs/m1_af_smoke.json',
    ]
    return {p.relative_to(ROOT).as_posix(): sha(p.read_bytes().replace(b'\r\n', b'\n')) for p in files}


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def write_new(path, value):
    with path.open('xb') as handle:
        handle.write(encode(value))


def verify(report, binding):
    require(report['schema_version'] == 'cpmt-d056-role-server-check-v1', 'wrong server report schema')
    require(report['code_binding'] == binding, 'source binding changed; result cannot certify this checkout')
    require(report['formal_training_performed'] is False and report['test_access'] is False,
            'incorrect experiment boundary')
    require(report['local_preflight_reused'] is False, 'faulty local CPU results must not certify server checks')
    require(report['runtime']['system'] == 'Linux' and 'microsoft' not in report['runtime']['release'].lower(),
            'expected independent Linux server runtime')
    require(report['exit_code'] == 0 and report['tests_run'] == 39, 'server tests incomplete')
    require(len(report['suites']) == len(SUITES), 'missing suite')
    for saved, (name, pattern, count) in zip(report['suites'], SUITES):
        require(saved['name'] == name and saved['pattern'] == pattern, 'suite order/identity changed')
        require(saved['exit_code'] == 0 and saved['tests_run'] == count, 'suite failed or skipped')
        output = saved['output']
        require(sha(output.encode('utf-8')) == saved['output_sha256'], 'suite receipt hash mismatch')
        require(re.search(rf'Ran {count} tests? in .+\n\nOK\s*$', output), 'unittest success receipt missing')


def run():
    require(platform.system() == 'Linux' and 'microsoft' not in platform.release().lower(),
            'run on the independent server; local Windows/WSL CPU is unreliable')
    binding = code_binding()
    git_root = Path(subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=ROOT, text=True).strip()).resolve()
    require(git_root == ROOT.resolve(), 'actual Git root mismatch')
    tracked = set(subprocess.check_output(['git', 'ls-files'], cwd=ROOT, text=True).splitlines())
    require(set(binding) <= tracked, 'commit all source inputs before server execution')
    require(not subprocess.check_output(['git', 'status', '--porcelain', '--', *binding], cwd=ROOT, text=True).strip(),
            'server check inputs must have no uncommitted changes')
    print(f'ROLE_SERVER_ROOT={git_root}', flush=True)
    if OUTPUT.exists():
        verify(json.loads(OUTPUT.read_text(encoding='utf-8')), binding)
        print('ROLE_SERVER_CHECK_REUSED exit=0', flush=True)
        return
    key = sha(json.dumps(binding, sort_keys=True).encode())[:16]
    attempt_dir = ROOT / 'outputs/m1-role-encoding-server-check' / key
    attempt_dir.mkdir(parents=True, exist_ok=True)
    require(not (attempt_dir / 'attempt.json').exists(), 'previous server attempt exists; preserve and investigate it')
    runtime = {'system': platform.system(), 'release': platform.release(), 'python': platform.python_version(),
               'hostname': socket.gethostname(), 'executable': sys.executable, 'repository_root': str(git_root),
               'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()}
    write_new(attempt_dir / 'attempt.json', {'step_id': 'ROLE-S1', 'code_binding': binding, 'runtime': runtime,
                                          'started_utc': datetime.now(timezone.utc).isoformat()})
    receipts = []
    try:
        env = dict(os.environ, OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', PYTHONIOENCODING='utf-8')
        version_output = subprocess.check_output(
            [sys.executable, '-c', 'import json,numpy,torch; print(json.dumps(dict(numpy=numpy.__version__,torch=torch.__version__)))'],
            cwd=ROOT, env=env, text=True, encoding='utf-8',
        )
        runtime['packages'] = json.loads(version_output)
        for name, pattern, count in SUITES:
            print(f'ROLE-S1 suite={name} expected_tests={count}', flush=True)
            command = [sys.executable, '-X', 'faulthandler', '-m', 'unittest', 'discover', '-s', 'tests', '-p', pattern, '-v']
            lines = []
            with (attempt_dir / f'{name}.log').open('x', encoding='utf-8') as log:
                with subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                      text=True, encoding='utf-8', errors='replace') as child:
                    for line in child.stdout:
                        print(line, end='', flush=True)
                        log.write(line)
                        log.flush()
                        lines.append(line)
                    exit_code = child.wait()
            output = ''.join(lines)
            match = re.search(r'Ran (\d+) tests? in ', output)
            receipt = {'name': name, 'pattern': pattern, 'exit_code': exit_code,
                       'tests_run': int(match.group(1)) if match else 0,
                       'output': output, 'output_sha256': sha(output.encode('utf-8'))}
            receipts.append(receipt)
            write_new(attempt_dir / f'{name}.exit.json', receipt)
            print(f'ROLE-S1 suite={name} exit={exit_code}', flush=True)
            require(exit_code == 0 and receipt['tests_run'] == count
                    and re.search(rf'Ran {count} tests? in .+\n\nOK\s*$', output),
                    f'{name} failed/incomplete; dependent checks stopped')
        require(code_binding() == binding, 'source changed during checks')
        report = {'schema_version': 'cpmt-d056-role-server-check-v1', 'step_id': 'ROLE-S1',
                  'formal_training_performed': False, 'test_access': False, 'local_preflight_reused': False,
                  'scope': 'engineering fixtures only; legacy tests generate tiny train/validation fixtures; no S5/test artifacts read',
                  'runtime': runtime, 'code_binding': binding, 'suites': receipts,
                  'exit_code': 0, 'tests_run': sum(r['tests_run'] for r in receipts)}
        verify(report, binding)
        partial = attempt_dir / 'server-report.json'
        write_new(partial, report)
        # Same filesystem hard link installs the complete report without overwriting.
        os.link(partial, OUTPUT)
        write_new(attempt_dir / 'complete.json', {'exit_code': 0, 'report_sha256': sha(OUTPUT.read_bytes())})
        print('ROLE_SERVER_CHECK_OK tests=39 exit=0', flush=True)
    except BaseException as error:
        write_new(attempt_dir / 'failure.json', {'exit_code': 1, 'error': repr(error),
                                              'completed_suites': [r['name'] for r in receipts], 'runtime': runtime})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['run', 'verify'])
    args = parser.parse_args()
    if args.action == 'run':
        run()
    else:
        verify(json.loads(OUTPUT.read_text(encoding='utf-8')), code_binding())
        print('ROLE_SERVER_CHECK_VERIFIED tests=39 exit=0', flush=True)


if __name__ == '__main__':
    main()
