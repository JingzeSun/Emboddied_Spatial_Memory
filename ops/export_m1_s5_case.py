"""Read-only extraction of the existing S5 group-69 case; standard library only.

中文：从已完成的四个评测分片读取八条完整轨迹，用于解释跨 seed
胜负反转。输入是固定 S5 报告及其绑定的磁盘文件，输出是带原始文件
hash 的 JSON。例如保留第一步全部候选及第 20 步状态，而非只挑失败步。
这不是新评测或新的 teacher 计算，不加载模型，也不调用 executor。
文件 payload 使用 gzip+base64 无损封装，避免展开所有候选世界导致 Git
产物过大；解码后原始字节的 SHA-256 必须与 sha256 相同。
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REPORT = 'results/m1_v7_d055_s5_confirmation.json'
REPORT_SHA = 'fa6426a96d0a1e8ca4cd7bb409ba9e6bbebf852d322a50cd47c6ea023e917e67'
OUTPUT = 'results/m1_v7_d055_s5_case_group69.json'
GROUP = 'rollout-pair:validation:000069'
ARCH = 'cross_candidate_set_transformer_v1'
METHODS = ('cpmt_ctl_core', 'direct_future_loss')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def pack(raw):
    return {'encoding': 'gzip+base64', 'sha256': digest(raw), 'bytes': len(raw),
            'payload': base64.b64encode(gzip.compress(raw, compresslevel=6, mtime=0)).decode('ascii')}


def verified_unit(path, expected_sha):
    marker_raw = (path / 'complete.json').read_bytes()
    require(digest(marker_raw) == expected_sha, f'completion marker changed: {path}')
    marker = json.loads(marker_raw)
    require(marker['schema_version'] == 'cpmt-s5-unit-v1', 'wrong unit schema')
    require(set(marker['files']) == {p.name for p in path.iterdir() if p.name != 'complete.json'},
            f'unit file inventory changed: {path}')
    files = {}
    for name, sha in marker['files'].items():
        require(Path(name).name == name and name not in ('.', '..'), 'unsafe unit filename')
        raw = (path / name).read_bytes()
        require(digest(raw) == sha, f'unit file changed: {path / name}')
        files[name] = raw
    return marker, marker_raw, files


def extract(report):
    require(report['engineering_pass'] is True and report['test_access'] is False,
            'expected completed S5 report with sealed test')
    models = [v for v in report['report']['per_model'].values()
              if v['architecture'] == ARCH and v['method'] in METHODS]
    require(len(models) == 10 and {(m['seed'], m['method']) for m in models}
            == {(s, m) for s in (7, 19, 31, 43, 59) for m in METHODS}, 'model matrix mismatch')
    table, units, audits = [], [], {}
    for model in sorted(models, key=lambda m: (m['seed'], m['method'])):
        metrics = sorted([r for r in model['metrics'] if r['paired_group_id'] == GROUP],
                         key=lambda r: r['sibling_index'])
        require([r['sibling_index'] for r in metrics] == [0, 1], 'report pair mismatch')
        table.append({'seed': model['seed'], 'method': model['method'], 'metrics': metrics})
        if model['seed'] not in (7, 19):
            continue
        matches = [s for s in model['evaluation']['shards'] if s['paired_group_id'] == GROUP]
        require(len(matches) == 1, 'missing/duplicate group shard')
        spec = matches[0]
        directory = Path(spec['path'])
        print(f'CASE_READING seed={model["seed"]} method={model["method"]} path={directory}', flush=True)
        marker, marker_raw, files = verified_unit(directory, spec['marker_sha256'])
        result = json.loads(files['result.json'])
        require(result['binding'] == marker['binding'], 'result binding mismatch')
        sequences = sorted(result['sequences'], key=lambda r: r['metrics']['sibling_index'])
        require([r['metrics'] for r in sequences] == metrics, 'shard metrics differ from exported report')
        records = [json.loads(line) for line in gzip.decompress(files['execution.jsonl.gz']).splitlines()]
        require(len(records) == 40, 'expected 40 recorded decisions per unit')
        indexed = {}
        for row in records:
            mat, choice = row['materialized'], row['choice']
            key = (mat['audit_sibling_index'], choice['step_index'])
            require(key not in indexed, 'duplicate execution decision')
            indexed[key] = row
        require(set(indexed) == {(s, t) for s in (0, 1) for t in range(20)}, 'execution matrix incomplete')
        for sequence in sequences:
            sibling = sequence['metrics']['sibling_index']
            choices = sequence['choices']
            require([c['step_index'] for c in choices] == list(range(20)), 'choice horizon mismatch')
            require(all(a['post_graph_hash'] == b['base_graph_hash'] for a, b in zip(choices, choices[1:])),
                    'broken persistent state chain')
            for choice in choices:
                row = indexed[sibling, choice['step_index']]
                require(row['choice'] == choice, 'execution choice mismatch')
                require(row['materialized']['audit_sequence_id'] == sequence['metrics']['sequence_id'],
                        'execution sequence mismatch')
                require(row['current']['graph_hash'] == choice['post_graph_hash'], 'recorded current hash mismatch')
        audit = marker['binding']['audit']
        require(audit['paired_group_id'] == GROUP, 'wrong bound reference group')
        audit_raw = Path(audit['path']).read_bytes()
        require(digest(audit_raw) == audit['sha256'], 'bound reference audit changed')
        value = json.loads(gzip.decompress(audit_raw))
        pair = value['audits'] if isinstance(value, dict) else value
        require(len(pair) == 2 and {a['sibling_index'] for a in pair} == {0, 1}
                and all(a['paired_group_id'] == GROUP and len(a['steps']) == 20 for a in pair),
                'reference audit pair/horizon mismatch')
        audits[audit['sha256']] = {'source': audit, 'file': pack(audit_raw)}
        units.append({'seed': model['seed'], 'method': model['method'], 'source': spec,
                      'model_sha256': model['model_sha256'], 'reference_audit_sha256': audit['sha256'],
                      'sequences': sequences, 'complete_marker': pack(marker_raw),
                      'files': {name: pack(files[name]) for name in ('result.json', 'execution.jsonl.gz')}})
        print(f'CASE_UNIT_OK seed={model["seed"]} method={model["method"]} sequences=2 decisions=40', flush=True)
    require(len(units) == 4 and len(audits) == 1, 'expected four units sharing one reference pair')
    return {'schema_version': 'cpmt-s5-posthoc-case-export-v1', 'paired_group_id': GROUP,
            'architecture': ARCH, 'posthoc': True, 'model_execution_performed': False,
            'training_performed': False, 'test_access': False, 'formal_test_release': False,
            'selection': 'LOG-091: extreme A-vs-C burden advantage, tie seed/group ascending; include all five seeds in table and full seed 7/19 reversal traces',
            'source_report': {'path': REPORT, 'sha256': REPORT_SHA},
            'source_science_binding': report['binding']['science'],
            'five_seed_metrics': table, 'units': units, 'reference_audits': audits,
            'counts': {'units': 4, 'sequences': 8, 'decisions': 160},
            'limitations': 'Existing observations only; reference-history teacher is not a recomputed teacher on diverged worlds.'}


def write_once(path, raw):
    if path.exists():
        require(path.read_bytes() == raw, f'existing export differs; preserved: {path}')
        return 'REUSED'
    with path.open('xb') as stream:
        stream.write(raw)
    return 'VERIFIED'


def main():
    source = (ROOT / REPORT).read_bytes()
    require(digest(source) == REPORT_SHA, 'S5 exported report hash mismatch')
    exported = extract(json.loads(source))
    exported['exporter_sha256'] = digest(Path(__file__).read_bytes())
    raw = (json.dumps(exported, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    require(len(raw) < 49_000_000, 'export exceeds bounded Git size; no output written')
    output = ROOT / OUTPUT
    status = write_once(output, raw)
    print(f'EXPORT_{status} path={output} sha256={digest(raw)} bytes={len(raw)}', flush=True)
    print('CASE_EXPORT_OK units=4 sequences=8 decisions=160 model_execution=false test_access=false', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'CASE_EXPORT_FAILED {type(error).__name__}: {error}', file=sys.stderr, flush=True)
        raise SystemExit(1)
