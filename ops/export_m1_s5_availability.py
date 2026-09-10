"""S5 已有逐步选择的只读导出、分层及离线复核；仅标准库。

输入是固定 confirmation 和其绑定的 complete/result 文件；输出是带来源
哈希、全部逐步可达性及分层计数的 JSON。例如把错误后无完整候选与有
候选却仍错分开；不重算图、不调用模型/执行器、不推断教师对错或多步
可恢复性。中文定义及操作边界见 HARD_CONDITION_EXPERIMENT.md。
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'results/m1_v7_d055_s5_confirmation.json'
SOURCE_SHA = 'fa6426a96d0a1e8ca4cd7bb409ba9e6bbebf852d322a50cd47c6ea023e917e67'
OUTPUT = ROOT / 'results/m1_v7_d055_s5_availability.json'
TEST_FILE = ROOT / 'ops/tests/test_s5_availability_export.py'
ARCHS = {'cross_candidate_set_transformer_v1', 'shared_candidate_mlp_v1'}
METHODS = {'cpmt_ctl_core', 'direct_classifier', 'direct_future_loss',
           'execute_current_only', 'future_no_execution'}
SEEDS = {7, 19, 31, 43, 59}
GROUPS = {f'rollout-pair:validation:{g:06d}' for g in range(4, 204)}
CELLS = [f'{prior}_{reach}_{after}' for prior in ('prior_correct', 'prior_wrong')
         for reach in ('reachable', 'unreachable') for after in ('correct', 'wrong')]
CHOICE_FIELDS = ('step_index', 'scenario_family', 'ambiguity', 'selected_index',
                 'selected_template', 'reference_index', 'registered_selection_correct',
                 'active_correct_after', 'committed', 'commit_requested',
                 'selected_legal', 'selected_static_preflight_pass', 'executor_quarantined',
                 'revisit_opportunity', 'revisit_triggered', 'candidate_availability')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def code_binding():
    # Normalize checkout line endings only; data/report hashes always use raw bytes.
    return {p.relative_to(ROOT).as_posix(): digest(p.read_bytes().replace(b'\r\n', b'\n'))
            for p in (Path(__file__), TEST_FILE)}


def pack(value):
    raw = encode(value)
    return {'encoding': 'gzip+base64-json', 'sha256': digest(raw), 'bytes': len(raw),
            'payload': base64.b64encode(gzip.compress(raw, compresslevel=6, mtime=0)).decode('ascii')}


def unpack(blob):
    require(blob['encoding'] == 'gzip+base64-json', 'payload encoding mismatch')
    raw = gzip.decompress(base64.b64decode(blob['payload'], validate=True))
    require(len(raw) == blob['bytes'] and digest(raw) == blob['sha256'], 'payload digest mismatch')
    return json.loads(raw)


def model_matrix(report):
    require(report['engineering_pass'] is True and report['test_access'] is False
            and report['formal_test_release'] is False, 'expected completed S5 with sealed test')
    models = report['report']['per_model']
    require(len(models) == 50 and {(m['architecture'], m['method'], m['seed']) for m in models.values()}
            == {(a, m, s) for a in ARCHS for m in METHODS for s in SEEDS}, 'model matrix mismatch')
    paths = set()
    for model in models.values():
        rows, shards = model['metrics'], model['evaluation']['shards']
        require(len(rows) == 400 and {(r['paired_group_id'], r['sibling_index']) for r in rows}
                == {(g, s) for g in GROUPS for s in (0, 1)}, 'metric matrix mismatch')
        require(len(shards) == 200 and {s['paired_group_id'] for s in shards} == GROUPS,
                'shard matrix mismatch')
        for spec in shards:
            require(spec['path'] not in paths, 'duplicate shard path')
            paths.add(spec['path'])
    return models


def timeline(choices, metrics):
    require(len(choices) == 20 and [c['step_index'] for c in choices] == list(range(20)),
            'choice horizon incomplete or duplicated')
    correct = [c['active_correct_after'] for c in choices]
    require(all(v in (0, 1) for v in correct), 'nonbinary active correctness')
    first = next((t for t, v in enumerate(correct) if not v), -1)
    recovered = next((t - first for t in range(first + 1, 20) if correct[t]), -1) if first >= 0 else -1
    expected = {'first_active_error_step': first, 'final_active_graph_correctness': correct[-1],
                'mean_active_graph_correctness': sum(correct) / 20,
                'any_first_error_recovery_eligible': int(first >= 0),
                'any_first_error_time_to_recovery': recovered,
                'any_first_error_recovered_within_window': int(0 < recovered <= 3),
                'registered_selection_accuracy': sum(c['registered_selection_correct'] for c in choices) / 20}
    for key, value in expected.items():
        require(math.isclose(metrics[key], value, abs_tol=1e-12, rel_tol=0), f'timeline metric mismatch: {key}')
    for c in choices:
        for name in ('committed', 'commit_requested', 'selected_legal', 'selected_static_preflight_pass',
                     'executor_quarantined', 'registered_selection_correct', 'revisit_opportunity', 'revisit_triggered'):
            require(type(c[name]) is bool, f'nonboolean choice: {name}')
        require(c['commit_requested'], 'fixed always-attempt gate changed')
        require(c['committed'] == c['selected_legal']
                and c['executor_quarantined'] == (not c['selected_legal']), 'commit legality mismatch')
        require(c['selected_static_preflight_pass'], 'selected statically rejected slot')
        require(c['registered_selection_correct'] == (c['selected_index'] == c['reference_index']),
                'registered index mismatch')
        require(all(type(c[k]) is int and 0 <= c[k] < 16 for k in ('selected_index', 'reference_index')),
                'candidate index out of range')
        a = c['candidate_availability']
        require(type(a['exact_reference_reachable']) is bool, 'reachability is not boolean')
        for key in ('constructed_candidate_count', 'unavailable_slot_count', 'selectable_legal_candidate_count',
                    'executor_illegal_candidate_count', 'static_rejected_constructed_count'):
            require(type(a[key]) is int and 0 <= a[key] <= 16, f'invalid candidate count: {key}')
        require(a['constructed_candidate_count'] + a['unavailable_slot_count'] == 16,
                'candidate slot partition mismatch')
        require(a['selectable_legal_candidate_count'] <= a['constructed_candidate_count']
                - a['executor_illegal_candidate_count'], 'legal candidate count mismatch')
        require(not a['exact_reference_reachable'] or a['selectable_legal_candidate_count'] > 0,
                'reachable without selectable candidate')
        require(not (c['committed'] and c['active_correct_after']) or a['exact_reference_reachable'],
                'correct committed world marked unreachable')


def validate_unit(marker, result, science, model_key, model, group):
    require(marker['schema_version'] == 'cpmt-s5-unit-v1', 'unit schema mismatch')
    require(marker['binding'] == result['binding'], 'unit binding mismatch')
    b = marker['binding']
    require(all(b.get(k) == v for k, v in science.items()), 'science binding mismatch')
    require(b['model_key'] == model_key and b['audit']['paired_group_id'] == group,
            'model/group binding mismatch')
    pairs = sorted(result['sequences'], key=lambda r: r['metrics']['sibling_index'])
    expected = sorted((r for r in model['metrics'] if r['paired_group_id'] == group),
                      key=lambda r: r['sibling_index'])
    require(len(pairs) == 2 and [r['metrics']['sibling_index'] for r in pairs] == [0, 1], 'sibling pair missing')
    require([s['metrics'] for s in pairs] == expected, 'metrics differ from sealed report')
    output = []
    for s in pairs:
        choices, metrics = s['choices'], s['metrics']
        timeline(choices, metrics)
        require(all(a['post_graph_hash'] == z['base_graph_hash'] for a, z in zip(choices, choices[1:])),
                'broken persistent state chain')
        unreachable = sum(not c['candidate_availability']['exact_reference_reachable'] for c in choices)
        require(s['candidate_availability']['decisions'] == 20
                and s['candidate_availability']['decisions_without_exact_reference_reachable'] == unreachable,
                'saved availability aggregate mismatch')
        output.append({k: metrics[k] for k in ('paired_group_id', 'sibling_index', 'sequence_id')})
        output[-1].update(choices=[{k: c[k] for k in CHOICE_FIELDS} for c in choices],
                             state_chain_sha256=digest(encode([[c['base_graph_hash'], c['post_graph_hash']]
                                                             for c in choices])))
    return output


def read_unit(spec, science, model_key, model):
    path = Path(spec['path'])
    marker_raw = (path / 'complete.json').read_bytes()
    require(digest(marker_raw) == spec['marker_sha256'], f'completion marker changed: {path}')
    marker = json.loads(marker_raw)
    raw = (path / 'result.json').read_bytes()
    require(digest(raw) == marker['files']['result.json'], f'result digest changed: {path}')
    result = json.loads(raw)
    sequences = validate_unit(marker, result, science, model_key, model, spec['paired_group_id'])
    provenance = {**spec, 'result_sha256': digest(raw), 'result_bytes': len(raw),
                  'audit': marker['binding']['audit']}
    return sequences, provenance


def summarize(sequences):
    total = Counter({k: 0 for k in CELLS})
    family, template = defaultdict(Counter), defaultdict(Counter)
    sequence_counts = Counter()
    for sequence in sequences:
        previous_correct = True  # Registered initial world, before decision zero.
        seq = Counter()
        for c in sequence['choices']:
            reachable = c['candidate_availability']['exact_reference_reachable']
            current_correct = bool(c['active_correct_after'])
            cell = ('prior_correct' if previous_correct else 'prior_wrong') + '_' + (
                'reachable' if reachable else 'unreachable') + '_' + ('correct' if current_correct else 'wrong')
            total[cell] += 1
            family[c['scenario_family']][cell] += 1
            template[c['selected_template']][cell] += 1
            seq[cell] += 1
            previous_correct = current_correct
        sequence_counts['sequences'] += 1
        sequence_counts['with_prior_error_and_no_complete_option'] += int(any(
            seq['prior_wrong_unreachable_' + x] for x in ('correct', 'wrong')))
        sequence_counts['with_prior_error_and_complete_option'] += int(any(
            seq['prior_wrong_reachable_' + x] for x in ('correct', 'wrong')))
        sequence_counts['with_reachable_selection_error'] += int(any(
            seq[x + '_reachable_wrong'] for x in ('prior_correct', 'prior_wrong')))
    return finish_summary(total, family, template, sequence_counts)


def finish_summary(total, family, template, sequence_counts):
    prior_wrong = sum(v for k, v in total.items() if k.startswith('prior_wrong_'))
    opportunities = total['prior_wrong_reachable_correct'] + total['prior_wrong_reachable_wrong']
    return {'decision_cells': dict(total), 'sequence_counts': dict(sequence_counts),
            'by_current_family': {k: dict(v) for k, v in sorted(family.items())},
            'by_selected_template': {k: dict(v) for k, v in sorted(template.items())},
            'post_error_complete_option_fraction': opportunities / prior_wrong if prior_wrong else None,
            'observed_recovery_given_complete_option_fraction': total['prior_wrong_reachable_correct']
                / opportunities if opportunities else None}


def combine(summaries):
    total = Counter({k: 0 for k in CELLS})
    families, templates, sequences = defaultdict(Counter), defaultdict(Counter), Counter()
    for summary in summaries:
        total.update(summary['decision_cells'])
        sequences.update(summary['sequence_counts'])
        for name, cells in summary['by_current_family'].items():
            families[name].update(cells)
        for name, cells in summary['by_selected_template'].items():
            templates[name].update(cells)
    return finish_summary(total, families, templates, sequences)


def verify_export(export, report):
    require(export['schema_version'] == 'cpmt-s5-availability-export-v1', 'export schema mismatch')
    require(export['source'] == {'path': SOURCE.relative_to(ROOT).as_posix(), 'sha256': SOURCE_SHA},
            'export source mismatch')
    require(export['code_binding'] == code_binding(), 'exporter/test code binding changed')
    require(export['preflight_tests']['passed'] is True and export['preflight_tests']['tests_run'] > 0,
            'missing preflight test success')
    require(export['test_access'] is False and export['model_execution_performed'] is False
            and export['candidate_execution_performed'] is False and export['training_performed'] is False
            and export['teacher_error_assessed'] is False and export['reachability_recomputed_from_graphs'] is False
            and export['full_execution_files_reread'] is False and export['formal_denominators_changed'] is False,
            'export scope mismatch')
    models = model_matrix(report)
    require(len(export['models']) == 50 and {m['model_key'] for m in export['models']} == set(models),
            'export model matrix incomplete')
    arms = defaultdict(list)
    audits = {}
    for item in export['models']:
        model = models[item['model_key']]
        require(all(item[k] == model[k] for k in ('architecture', 'method', 'seed', 'model_sha256')),
                'export model metadata mismatch')
        specs = {s['paired_group_id']: s for s in model['evaluation']['shards']}
        require(len(item['units']) == 200 and {u['paired_group_id'] for u in item['units']} == GROUPS,
                'export unit matrix incomplete')
        for unit in item['units']:
            group = unit['paired_group_id']
            require(all(unit[k] == v for k, v in specs[group].items()), 'export unit source mismatch')
            require(unit['audit']['paired_group_id'] == group, 'export audit group mismatch')
            require(audits.setdefault(group, unit['audit']) == unit['audit'], 'reference audit differs across models')
        rows = unpack(item['sequences'])
        expected = {(r['paired_group_id'], r['sibling_index']): r for r in model['metrics']}
        require(len(rows) == 400 and {(r['paired_group_id'], r['sibling_index']) for r in rows} == set(expected),
                'export sequence matrix incomplete')
        for sequence in rows:
            metric = expected[sequence['paired_group_id'], sequence['sibling_index']]
            require(sequence['sequence_id'] == metric['sequence_id'], 'export sequence ID mismatch')
            timeline(sequence['choices'], metric)
        require(item['summary'] == summarize(rows), 'model summary differs from payload')
        arms[item['architecture'], item['method']].append(item['summary'])
    expected_arms = [{'architecture': a, 'method': m, **combine(summaries)}
                     for (a, m), summaries in sorted(arms.items())]
    require(export['arms'] == expected_arms, 'arm summary differs from payload')
    require(export['counts'] == {'models': 50, 'units': 10000, 'sequences': 20000,
                                 'decisions': 400000, 'paired_groups': 200}, 'export counts mismatch')
    return export['counts']


def run_tests():
    suite = unittest.defaultTestLoader.discover(str(TEST_FILE.parent), pattern=TEST_FILE.name)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    require(result.wasSuccessful() and result.testsRun > 0 and not result.skipped, 'preflight tests failed')
    return {'passed': True, 'tests_run': result.testsRun, 'failures': 0, 'errors': 0, 'skipped': 0}


def write_once(path, value):
    raw = encode(value)
    require(len(raw) < 49_000_000, 'export exceeds 49 MB Git limit; no output written')
    if path.exists():
        require(path.read_bytes() == raw, f'different export preserved: {path}')
        return 'REUSED'
    partial = path.with_suffix(path.suffix + '.partial')
    require(not partial.exists(), f'incomplete output preserved; inspect before retry: {partial}')
    with partial.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    # Hard link installs without replacing any racing destination; leave partial on failure.
    os.link(partial, path)
    partial.unlink()
    return 'WRITTEN'


def stage_path():
    return ROOT / 'outputs' / 'm1-s5-availability-export' / digest(encode(code_binding()))[:16]


def extract_all(report, models, receipt, stage):
    exported_models, arms = [], defaultdict(list)
    started, units_done = time.monotonic(), 0
    for key, model in sorted(models.items()):
        sequences, units = [], []
        for spec in sorted(model['evaluation']['shards'], key=lambda s: s['paired_group_id']):
            rows, provenance = read_unit(spec, report['binding']['science'], key, model)
            sequences.extend(rows)
            units.append(provenance)
            units_done += 1
            if units_done % 100 == 0:
                elapsed = time.monotonic()-started
                print(f'AVAILABILITY_PROGRESS units={units_done}/10000 elapsed_s={elapsed:.1f}', flush=True)
                with (stage/'progress.jsonl').open('ab') as stream:
                    stream.write(encode({'units_verified': units_done, 'elapsed_seconds': elapsed,
                                         'last_unit': spec['path']}))
        exported_models.append({'model_key': key, **{k: model[k] for k in
            ('architecture', 'method', 'seed', 'model_sha256')}, 'units': units,
            'sequences': pack(sequences), 'summary': summarize(sequences)})
    # Merge counts, not full trajectories, to bound live memory.
    for item in exported_models:
        arms[item['architecture'], item['method']].append(item['summary'])
    return {'schema_version': 'cpmt-s5-availability-export-v1',
            'source': {'path': SOURCE.relative_to(ROOT).as_posix(), 'sha256': SOURCE_SHA},
            'code_binding': code_binding(), 'preflight_tests': receipt, 'posthoc': True,
            'test_access': False, 'training_performed': False, 'model_execution_performed': False,
            'candidate_execution_performed': False, 'teacher_error_assessed': False,
            'reachability_recomputed_from_graphs': False, 'full_execution_files_reread': False,
            'formal_denominators_changed': False,
            'scope': 'Saved choice diagnostics only, current reference after each decision. '
                'Prior wrong means previous decision was incorrect against its own reference. '
                'Observed recovery may include reference changes; no causal recovery effect or multistep search. '
                'Complete markers and result bytes verified live; audit/execution provenance is referenced, not reread. '
                'Teacher error versus amortization error remains unassessed on diverged worlds. '
                'Probabilities and graph hashes omitted from payload; full originals remain in bound result files.',
            'models': exported_models,
            'arms': [{'architecture': a, 'method': m, **combine(summaries)}
                     for (a, m), summaries in sorted(arms.items())],
            'counts': {'models': 50, 'units': 10000, 'sequences': 20000, 'decisions': 400000, 'paired_groups': 200}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('export', 'verify'))
    action = parser.parse_args().action
    source_raw = SOURCE.read_bytes()
    require(digest(source_raw) == SOURCE_SHA, 'sealed S5 report digest changed')
    report = json.loads(source_raw)
    models = model_matrix(report)
    if action == 'verify' or OUTPUT.exists():
        export = json.loads(OUTPUT.read_bytes())
        verify_export(export, report)
        print('AVAILABILITY_VERIFY_OK models=50 units=10000 decisions=400000 test_access=false', flush=True)
        print('Existing verified export reused; server shard files were not reread.', flush=True)
        return
    require(not OUTPUT.with_suffix(OUTPUT.suffix + '.partial').exists(), 'partial export preserved; inspect before retry')
    stage = stage_path()
    stage.mkdir(parents=True, exist_ok=True)
    require(not (stage/'attempt.json').exists(), f'prior export attempt preserved; inspect before retry: {stage}')
    receipt = run_tests()
    with (stage/'attempt.json').open('xb') as stream:
        stream.write(encode({'source_sha256': SOURCE_SHA, 'code_binding': code_binding(),
                             'preflight_tests': receipt, 'output': str(OUTPUT), 'pid': os.getpid()}))
        stream.flush()
        os.fsync(stream.fileno())
    started = time.monotonic()
    try:
        export = extract_all(report, models, receipt, stage)
        verify_export(export, report)
        status = write_once(OUTPUT, export)
        write_once(stage/'complete.json', {'output': str(OUTPUT), 'sha256': digest(OUTPUT.read_bytes()),
                                          'counts': export['counts'], 'exit_code': 0})
    except BaseException as error:
        with (stage/'failure.json').open('xb') as stream:
            stream.write(encode({'error_type': type(error).__name__, 'error': str(error),
                                 'exit_code': 130 if isinstance(error, KeyboardInterrupt) else 1}))
        raise
    print(f'AVAILABILITY_EXPORT_OK status={status} models=50 units=10000 decisions=400000 '
          f'exit=0 elapsed_s={time.monotonic()-started:.1f} output={OUTPUT}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('AVAILABILITY_INTERRUPTED exit=130 attempt preserved', file=sys.stderr, flush=True)
        raise SystemExit(130)
    except Exception as error:
        print(f'AVAILABILITY_FAILED exit=1 {type(error).__name__}: {error}', file=sys.stderr, flush=True)
        raise SystemExit(1)
