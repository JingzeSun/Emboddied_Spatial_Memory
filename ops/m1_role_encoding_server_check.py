"""ROLE-S1/S2：服务器工程验收，run 后 verify；不训练正式模型。

输入为 Git 中的角色原型及既有测试；输出为新服务器的独立测试回执。
例如运行 9 项专项检查和 28 项旧路径回归，不复用故障电脑的成功记录。
recover 只核验旧版误写 30 项而拒收的完整服务器回执，不重跑或改写原始测试。
这不是科学效果评测，也不读取已封存 test 或已有 S5 数据。
"""
import argparse
import ast
from collections import Counter
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
SUITES = [('prototype', 'test_m1_role_encoding.py', 9), ('legacy', 'test_m1_af_rollout.py', 28)]
TOTAL_TESTS = sum(count for _, _, count in SUITES)
ENTRY = 'ops/m1_role_encoding_server_check.py'
REPAIR_TEST = 'ops/tests/test_role_server_receipts.py'
OLD_ENTRY_SHA256 = 'b9591407403cc2e0f14be02b21f80e4da76fcc7b8dcef285f4f5438d04964f03'
COUNT_FAILURE = "ValueError('legacy failed/incomplete; dependent checks stopped')"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def code_binding():
    files = sorted((ROOT / 'src/cpmt').glob('*.py')) + [
        Path(__file__), ROOT / REPAIR_TEST, ROOT / 'tests/test_m1_role_encoding.py', ROOT / 'tests/test_m1_af_rollout.py',
        ROOT / 'configs/m1_hard_condition_v7.json', ROOT / 'configs/m1_af_smoke.json',
    ]
    return {p.relative_to(ROOT).as_posix(): sha(p.read_bytes().replace(b'\r\n', b'\n')) for p in files}


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def write_new(path, value):
    with path.open('xb') as handle:
        handle.write(encode(value))


def inventories():
    """Static inventory of these two explicit unittest classes; no torch import."""
    result = {}
    for name, pattern, count in SUITES:
        tree = ast.parse((ROOT / 'tests' / pattern).read_text(encoding='utf-8'))
        names = []
        for cls in tree.body:
            if isinstance(cls, ast.ClassDef) and any(ast.unparse(base) == 'unittest.TestCase' for base in cls.bases):
                names.extend(f'{Path(pattern).stem}.{cls.name}.{node.name}' for node in cls.body
                             if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'))
        require(len(names) == len(set(names)) == count, f'{name} declared count differs from source test inventory')
        result[name] = sorted(names)
    return result


def validate_receipt(saved, spec, names):
    name, pattern, count = spec
    require(saved['name'] == name and saved['pattern'] == pattern, 'suite order/identity changed')
    require(saved['exit_code'] == 0 and saved['tests_run'] == count, 'suite failed or skipped')
    output = saved['output']
    require(sha(output.encode('utf-8')) == saved['output_sha256'], 'suite receipt hash mismatch')
    require(re.search(rf'Ran {count} tests? in .+\n\nOK\s*$', output), 'unittest success receipt missing')
    lines = re.findall(r'^(test_\w+) \(([^)]+)\)', output, re.MULTILINE)
    # Python versions differ on whether __str__ includes the method inside ().
    observed = [detail if detail.endswith('.' + method) else detail + '.' + method
                for method, detail in lines]
    require(Counter(observed) == Counter(names), 'executed test names differ from source inventory')


def old_binding(binding):
    result = dict(binding)
    result.pop(REPAIR_TEST, None)
    result[ENTRY] = OLD_ENTRY_SHA256
    return result


def verify(report, binding):
    require(report['schema_version'] == 'cpmt-d056-role-server-check-v1', 'wrong server report schema')
    require(report['code_binding'] == binding, 'source binding changed; result cannot certify this checkout')
    require(report['formal_training_performed'] is False and report['test_access'] is False,
            'incorrect experiment boundary')
    require(report['local_preflight_reused'] is False, 'faulty local CPU results must not certify server checks')
    require(report['runtime']['system'] == 'Linux' and 'microsoft' not in report['runtime']['release'].lower(),
            'expected independent Linux server runtime')
    require(report['exit_code'] == 0 and report['tests_run'] == TOTAL_TESTS, 'server tests incomplete')
    require(len(report['suites']) == len(SUITES), 'missing suite')
    names = inventories()
    require(report['test_inventory'] == names, 'report inventory differs from source')
    for saved, spec in zip(report['suites'], SUITES):
        validate_receipt(saved, spec, names[spec[0]])
    recovery = report.get('recovery')
    if recovery:
        require(report['executed_code_binding'] == old_binding(binding), 'tested scientific inputs changed since old attempt')
        require(recovery['reason'] == 'correct_30_to_28_test_count' and recovery['tests_rerun'] is False,
                'unsupported recovery')
        require(recovery['original_failure']['error'] == COUNT_FAILURE
                and recovery['original_failure']['completed_suites'] == ['prototype', 'legacy'], 'wrong original failure')
    else:
        require(report['executed_code_binding'] == binding, 'executed source mismatch')


def load_count_failure(attempt_dir, expected_binding, names):
    """Accept only complete successful receipts rejected by the known count bug."""
    evidence = {}
    def read(name):
        raw = (attempt_dir / name).read_bytes()
        evidence[name] = sha(raw)
        return raw
    attempt = json.loads(read('attempt.json'))
    failure = json.loads(read('failure.json'))
    require(attempt['step_id'] == 'ROLE-S1' and attempt['code_binding'] == expected_binding, 'old attempt source mismatch')
    require(failure['exit_code'] == 1 and failure['error'] == COUNT_FAILURE
            and failure['completed_suites'] == ['prototype', 'legacy'], 'not the known count-only failure')
    runtime = failure['runtime']
    require(all(runtime.get(key) == value for key, value in attempt['runtime'].items()), 'old runtime mismatch')
    receipts = []
    for spec in SUITES:
        name = spec[0]
        receipt = json.loads(read(f'{name}.exit.json'))
        require(read(f'{name}.log').decode('utf-8') == receipt['output'], 'saved log differs from exit receipt')
        validate_receipt(receipt, spec, names[name])
        receipts.append(receipt)
    return runtime, receipts, failure, evidence


def recover():
    """Read-only recovery of the executed branches; writes only a new report."""
    binding = code_binding()
    if OUTPUT.exists():
        verify(json.loads(OUTPUT.read_text(encoding='utf-8')), binding)
        print(f'ROLE_SERVER_CHECK_VERIFIED tests={TOTAL_TESTS} exit=0', flush=True)
        return
    expected = old_binding(binding)
    key = sha(json.dumps(expected, sort_keys=True).encode())[:16]
    attempt_dir = ROOT / 'outputs/m1-role-encoding-server-check' / key
    names = inventories()
    runtime, receipts, failure, evidence = load_count_failure(attempt_dir, expected, names)
    report = {'schema_version': 'cpmt-d056-role-server-check-v1', 'step_id': 'ROLE-S1',
              'formal_training_performed': False, 'test_access': False, 'local_preflight_reused': False,
              'scope': 'recover completed server tests rejected solely by the 30-versus-28 count bug',
              'runtime': runtime, 'code_binding': binding, 'executed_code_binding': expected,
              'test_inventory': names, 'suites': receipts, 'exit_code': 0, 'tests_run': TOTAL_TESTS,
              'recovery': {'reason': 'correct_30_to_28_test_count', 'tests_rerun': False,
                           'source_attempt': attempt_dir.relative_to(ROOT).as_posix(),
                           'source_file_sha256': evidence, 'original_failure': failure}}
    verify(report, binding)
    require(code_binding() == binding, 'source changed during recovery')
    partial = attempt_dir / 'count-correction-report.json'
    if partial.exists():
        require(partial.read_bytes() == encode(report), 'existing recovery differs; preserve and investigate')
    else:
        write_new(partial, report)
    os.link(partial, OUTPUT)
    print(f'ROLE_SERVER_CHECK_RECOVERED tests={TOTAL_TESTS} rerun=0 exit=0', flush=True)


def run():
    require(platform.system() == 'Linux' and 'microsoft' not in platform.release().lower(),
            'run on the independent server; local Windows/WSL CPU is unreliable')
    binding = code_binding()
    names = inventories()
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
    previous_key = sha(json.dumps(old_binding(binding), sort_keys=True).encode())[:16]
    require(not (ROOT / 'outputs/m1-role-encoding-server-check' / previous_key / 'attempt.json').exists(),
            'old attempt exists; use recover to verify saved receipts instead of rerunning tests')
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
            validate_receipt(receipt, (name, pattern, count), names[name])
        require(code_binding() == binding, 'source changed during checks')
        report = {'schema_version': 'cpmt-d056-role-server-check-v1', 'step_id': 'ROLE-S1',
                  'formal_training_performed': False, 'test_access': False, 'local_preflight_reused': False,
                  'scope': 'engineering fixtures only; legacy tests generate tiny train/validation fixtures; no S5/test artifacts read',
                  'runtime': runtime, 'code_binding': binding, 'executed_code_binding': binding,
                  'test_inventory': names, 'suites': receipts,
                  'exit_code': 0, 'tests_run': sum(r['tests_run'] for r in receipts)}
        verify(report, binding)
        partial = attempt_dir / 'server-report.json'
        write_new(partial, report)
        # Same filesystem hard link installs the complete report without overwriting.
        os.link(partial, OUTPUT)
        write_new(attempt_dir / 'complete.json', {'exit_code': 0, 'report_sha256': sha(OUTPUT.read_bytes())})
        print(f'ROLE_SERVER_CHECK_OK tests={TOTAL_TESTS} exit=0', flush=True)
    except BaseException as error:
        write_new(attempt_dir / 'failure.json', {'exit_code': 1, 'error': repr(error),
                                              'completed_suites': [r['name'] for r in receipts], 'runtime': runtime})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['run', 'recover', 'verify'])
    args = parser.parse_args()
    if args.action == 'run':
        run()
    elif args.action == 'recover':
        recover()
    else:
        verify(json.loads(OUTPUT.read_text(encoding='utf-8')), code_binding())
        print(f'ROLE_SERVER_CHECK_VERIFIED tests={TOTAL_TESTS} exit=0', flush=True)


if __name__ == '__main__':
    main()
