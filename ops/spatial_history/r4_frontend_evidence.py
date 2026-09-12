"""Copy existing sealed frontend evidence; never execute scientific modules.

白话：解决旧报告省略分量和地图原文的问题。输入为已封存的16份地图、
16份原公开历史及16份仅供评估的XML，输出带原字节摘要的JSON证据包。
例如近期帧的6个未排除分量会随完整地图原样回传；这不是重新分割、
建图、推演或放宽唯一性检查，也不预先把小分量判为噪声。

payloads分别保留map/public_input/evaluation_xml，record是原bytes/sha256；
base64是原文件字节的无损文本编码，原.gz仍为gzip，不是重新计算的数组。
XML仅用于封存后的独立归因，不能作为预测输入。所有科学字段保持原schema。
"""
import base64
import hashlib
import json
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
STAGE = Path('/root/autodl-tmp/spatial-history/sh04-r4-cd-audit-v1')
ORIGINAL = Path('/root/autodl-tmp/spatial-history/sh04-r4-engineering-subset-v2')
PARENT = ROOT / 'results/spatial_history_r4_map_control_v1.json'
PARENT_SHA = 'd3635655e5594df1406167f2e15dfc7fbcf6f5d588979dcac2c883990cc8e868'
OUTPUT = ROOT / 'results/spatial_history_r4_frontend_evidence_v1.json'
VERSION = 'sh04-r4-frontend-evidence-v1'
LIMIT = 32 * 1024**2
FAMILIES = ('r4-39', 'r4-47', 'r4-25', 'r4-03')
WORLDS = ('LL', 'LR', 'RL', 'RR')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def record(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def read_bound(root, relative, expected):
    path = root / relative
    require(path.resolve().is_relative_to(root.resolve()), 'input path escape: ' + relative)
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'symlink input: ' + relative)
    require(path.is_file() and path.stat().st_size <= LIMIT, 'missing/oversized input: ' + relative)
    raw = path.read_bytes()
    require(record(raw) == expected, 'input digest changed: ' + relative)
    return raw


def main():
    require(platform.system() == 'Linux', 'server-only evidence export')
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
    def timeout(signum, frame):
        raise TimeoutError('300 s export limit; original evidence preserved')
    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(300)
    began = time.monotonic()
    source = Path(__file__).resolve().relative_to(ROOT).as_posix()
    source_raw = Path(__file__).read_bytes()
    commit = git('rev-parse', 'HEAD').decode().strip()
    require(not git('status', '--porcelain', '--', source), 'exporter must be committed and clean')
    require(git('show', commit + ':' + source) == source_raw, 'exporter Git bytes differ')
    parent_raw = PARENT.read_bytes()
    require(record(parent_raw)['sha256'] == PARENT_SHA, 'unexpected parent report')
    parent = json.loads(parent_raw)
    require(parent['status'] == 'passed' and parent['verification_error'] is None,
            'requires complete engineering evidence')
    require(parent['malformed_json'] == {},
            'malformed_json must be an empty object (original exporter schema)')
    receipt, seal, summary = (parent[k] for k in ('receipt', 'public_seal', 'summary'))
    require(receipt['exit_code'] == receipt['prediction']['exit_code']
            == receipt['evaluation']['exit_code'] == 0, 'successful phase exits required')
    require(seal['private_truth_read'] is False and seal['commit'] == receipt['commit']
            and seal['binding'] == receipt['binding'], 'public seal boundary mismatch')
    require(summary['history_count'] == seal['history_count'] == 16
            and summary['branch_count'] == seal['branch_count'] == 144, 'original census mismatch')
    require(summary['proxy_status_counts'] == {'perception_unresolved': 144}
            and summary['nominal_complete_count'] == summary['nominal_task_readout_count'] == 0,
            'unexpected parent outcome; review scope before export')
    require(len(receipt['binding']) == 22, 'source binding census changed')
    for name, digest in receipt['binding'].items():
        require(record(git('show', receipt['commit'] + ':' + name))['sha256'] == digest,
                'original Git source mismatch: ' + name)
    inputs = {'stage': {}, 'original': {}}
    def stage(relative):
        expected = parent['stage_inventory'][relative]
        raw = read_bound(STAGE, relative, expected)
        inputs['stage'][relative] = expected
        return raw
    def original(relative, expected):
        raw = read_bound(ORIGINAL, relative, expected)
        inputs['original'][relative] = expected
        return raw
    # Check existing markers only; never call the old check/run/verify entry.
    for name, value in (('audit_receipt.json', receipt), ('public_seal.json', seal),
                        ('summary.json', summary), ('predict_exit.json', receipt['prediction']),
                        ('evaluate_exit.json', receipt['evaluation'])):
        raw = stage(name)
        require(json.loads(raw) == value, 'original marker mismatch: ' + name)
        if name in receipt['files']:
            require(record(raw) == receipt['files'][name], 'receipt/marker digest mismatch')
    require(record(stage('public_seal.json')) == receipt['prediction']['public_seal']
            == summary['public_seal'], 'prediction exit/seal binding mismatch')
    checked = json.loads(stage('check/receipt.json'))
    require(checked['tests_run'] == 36 and checked['exit_code'] == 0
            and checked['binding'] == receipt['binding'] and checked['commit'] == receipt['commit'],
            'check receipt mismatch')
    require(all(checked[k] == 0 for k in ('failures', 'errors', 'skipped',
            'expected_failures', 'unexpected_successes')), 'incomplete checks')
    rows = {(w['family'], w['world']): w for w in summary['worlds']}
    require(len(summary['worlds']) == len(rows) == 16 and set(rows) ==
            {(f, w) for f in FAMILIES for w in WORLDS}, 'world identities changed')
    payloads = []
    print(f'{VERSION} READ stage={STAGE} original={ORIGINAL}', flush=True)
    for family in FAMILIES:
        for world in WORLDS:
            map_name = f'public/{family}/{world}/map.json.gz'
            public_name = f'execution/{family}/data/public/{world}.json.gz'
            xml_name = f'execution/{family}/data/audit/{world}/world.xml'
            require(parent['stage_inventory'][map_name] == seal['files'][map_name]
                    == receipt['files'][map_name], 'map seal mismatch')
            raw_files = (
                ('map', 'stage', map_name, stage(map_name)),
                ('public_input', 'original', public_name,
                 original(public_name, seal['source_public_files'][public_name])),
                ('evaluation_xml', 'original', xml_name,
                 original(xml_name, summary['source_truth_files'][xml_name])),
            )
            for kind, root, name, raw in raw_files:
                payloads.append({'family': family, 'world': world, 'kind': kind,
                    'root': root, 'path': name, 'record': record(raw),
                    'encoding': 'base64_of_original_file_bytes',
                    'base64': base64.b64encode(raw).decode('ascii')})
        print(f'{VERSION} READ {family} maps=4 public_inputs=4 evaluation_xml=4', flush=True)
    require(len(payloads) == 48 and len(inputs['stage']) == 22
            and len(inputs['original']) == 32, 'export input census mismatch')
    # Re-read only the consumed files to catch changes during copying.
    for root_name, root in (('stage', STAGE), ('original', ORIGINAL)):
        for name, expected in inputs[root_name].items():
            read_bound(root, name, expected)
    require(PARENT.read_bytes() == parent_raw and Path(__file__).read_bytes() == source_raw,
            'report/exporter changed during copy')
    output = {'version': VERSION, 'parent_report': record(parent_raw),
        'original_run_commit': receipt['commit'], 'exporter_source': {'path': source, **record(source_raw)},
        'inputs': inputs, 'payloads': payloads, 'history_count': 16,
        'original_branch_count': 144, 'new_simulation_steps': 0, 'new_training_steps': 0,
        'new_prediction_calls': 0, 'new_segmentation_calls': 0, 'new_map_build_calls': 0,
        'new_weight_download_bytes': 0, 'formal_model_ready': False,
        'interpretation': 'original_byte_evidence_only_no_new_scoring_or_causal_conclusion',
        'exit_code': 0}
    raw = encode(output)
    require(len(raw) <= LIMIT, 'evidence report exceeds 32 MiB')
    for item in payloads:
        require(record(base64.b64decode(item['base64'], validate=True)) == item['record'],
                'payload transport mismatch')
    if OUTPUT.exists():
        require(OUTPUT.read_bytes() == raw, 'different/incomplete existing report; preserve for diagnosis')
        action = 'REUSED'
    else:
        with OUTPUT.open('xb') as handle:
            handle.write(raw)
        require(OUTPUT.read_bytes() == raw, 'written report differs; preserve for diagnosis')
        action = 'EXPORTED'
    print(f'{VERSION} {action} payloads=48 inputs=54 bytes={len(raw)} '
          f'elapsed_s={time.monotonic()-began:.3f} path={OUTPUT} exit=0', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'{VERSION} FAILED {type(error).__name__}: {error} exit=1', file=sys.stderr, flush=True)
        sys.exit(1)
