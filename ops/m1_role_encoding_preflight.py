"""D-056 原型工程检查：python ops/m1_role_encoding_preflight.py [--verify]。

输入为当前绑定源码、固定 train 单组测试夹具；输出为测试退出证据及来源 hash。
例如检查 68 维角色候选在自身状态 rollout 中每步都正确接线，而不测方法效果。
本入口不训练正式模型、不读取 S5/test；失败保留现场，成功同绑定直接复用。
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'results/m1_d056_role_encoding_preflight.json'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def binding():
    files = sorted((ROOT / 'src/cpmt').glob('*.py')) + [
        Path(__file__), ROOT / 'tests/test_m1_role_encoding.py',
        ROOT / 'configs/m1_hard_condition_v7.json', ROOT / 'configs/m1_af_smoke.json',
    ]
    return {p.relative_to(ROOT).as_posix(): sha(p.read_bytes().replace(b'\r\n', b'\n')) for p in files}


def write_new(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write('\n')


def verify(report, code_binding):
    require(report['schema_version'] == 'cpmt-d056-role-preflight-v1', 'wrong report schema')
    require(report['code_binding'] == code_binding, 'source changed; old preflight cannot certify this version')
    require(report['exit_code'] == 0 and report['tests_run'] == 9, 'incomplete preflight')
    require(report['scope'] == 'train-fixture engineering only; no method efficacy claim', 'wrong scope')
    require(report['test_access'] is False and report['formal_training_performed'] is False, 'wrong data/training boundary')
    require(sha(report['test_output'].encode('utf-8')) == report['test_output_sha256'], 'test receipt hash mismatch')
    require(re.search(r'Ran 9 tests? in .+\n\nOK\s*$', report['test_output']), 'test success receipt missing')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    code_binding = binding()
    if OUTPUT.exists():
        verify(json.loads(OUTPUT.read_text(encoding='utf-8')), code_binding)
        print('ROLE_ENCODING_PREFLIGHT_VERIFIED (existing result reused)', flush=True)
        return
    require(not args.verify, 'preflight report missing')
    key = sha(json.dumps(code_binding, sort_keys=True).encode())[:16]
    attempt_dir = ROOT / 'outputs/m1-role-encoding-preflight' / key
    attempt_dir.mkdir(parents=True, exist_ok=True)
    require(not (attempt_dir / 'attempt.json').exists(), 'previous attempt exists; preserve it and investigate before retry')
    write_new(attempt_dir / 'attempt.json', {'step_id': 'ROLE-P1', 'code_binding': code_binding,
                                          'started_utc': datetime.now(timezone.utc).isoformat()})
    try:
        command = [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_m1_role_encoding.py', '-v']
        process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding='utf-8', errors='strict')
        lines = []
        for line in process.stdout:
            print(line, end='', flush=True)
            lines.append(line)
        exit_code = process.wait()
        output = ''.join(lines)
        (attempt_dir / 'tests.log').write_text(output, encoding='utf-8')
        require(exit_code == 0, f'preflight failed, exit={exit_code}')
        match = re.search(r'Ran (\d+) tests? in ', output)
        report = {'schema_version': 'cpmt-d056-role-preflight-v1', 'step_id': 'ROLE-P1',
                  'scope': 'train-fixture engineering only; no method efficacy claim',
                  'test_access': False, 'formal_training_performed': False,
                  'code_binding': code_binding, 'python_version': platform.python_version(),
                  'exit_code': exit_code, 'tests_run': int(match.group(1)) if match else 0,
                  'test_output': output, 'test_output_sha256': sha(output.encode('utf-8'))}
        verify(report, code_binding)
        write_new(OUTPUT, report)
        write_new(attempt_dir / 'complete.json', {'exit_code': 0, 'report_sha256': sha(OUTPUT.read_bytes())})
        print('ROLE_ENCODING_PREFLIGHT_OK exit=0', flush=True)
    except Exception as error:
        write_new(attempt_dir / 'failure.json', {'exit_code': 1, 'error': str(error)})
        raise


if __name__ == '__main__':
    main()
