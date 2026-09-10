"""Read-only D-057 export audit using only the standard library.

Recompute exported sequence aggregates, paired differences and error onsets;
bind embedded run results to server manifests and Git source bytes. This cannot
re-hash remote checkpoints/arrays or re-execute worlds absent from this export.
"""
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'results/m1_d057_role_pilot.json'
EXPECTED_SHA256 = '689871f848f4d997c88a086933204e6c039e7d0e803dd52d37535915a9bc5781'
METRICS = ['final_active_graph_correctness', 'final_open_memory_correctness',
           'final_graded_open_memory_correctness', 'open_fact_error_auc_per_100_decisions']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def close(a, b):
    require(math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12), f'numeric mismatch: {a} != {b}')


def git_files(commit):
    # Match Linux checkout line endings while retaining explicit .gitattributes
    # rules (e.g. PS1 CRLF); Windows git archive otherwise converts Python to CRLF.
    raw = subprocess.check_output(['git', '-c', 'core.autocrlf=input', 'archive', commit,
                                   'src', 'scripts', 'configs', 'tests'], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        return {m.name: archive.extractfile(m).read() for m in archive.getmembers() if m.isfile()}


def main():
    raw = REPORT.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == EXPECTED_SHA256, 'export bytes changed')
    report = json.loads(raw)
    plan = report['plan']
    require(report['complete'] and report['models'] == 18 and report['additional_scorers'] == 6, 'incomplete matrix')
    require(all(report[k] is False for k in ['test_access', 'validation_access', 'formal_acceptance', 'checkpoint_selection_performed']), 'boundary mismatch')
    commit = report['data_manifest']['provenance']['git_commit']
    files = git_files(commit)
    digest = hashlib.sha256()
    for name in sorted(files):
        digest.update(name.encode() + b'\0' + files[name] + b'\0')
    require(digest.hexdigest() == report['binding']['source_sha256'], 'source differs from bound Git commit')
    require(hashlib.sha256(files['configs/m1_role_pilot.json']).hexdigest() == report['binding']['plan_sha256'], 'plan hash mismatch')
    require(json.loads(files['configs/m1_role_pilot.json']) == plan, 'plan body mismatch')
    expected = {f'{e}__{m}__seed_{s}' for e in plan['encodings'] for m in plan['methods'] for s in plan['seeds']}
    require(set(report['runs']) == set(report['artifacts']) == expected, 'wrong run set')
    indexed, decisions, aggregates = {}, 0, 0
    for name, value in report['runs'].items():
        artifact = report['artifacts'][name]['marker']
        result_bytes = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
        require(hashlib.sha256(result_bytes).hexdigest() == artifact['files']['result.json'], 'embedded result differs from server digest')
        encoding, method, seed_text = name.split('__')
        binding = artifact['binding']
        require(all(binding[k] == v for k, v in report['binding'].items()), 'run provenance mismatch')
        require(binding['encoding'] == encoding and binding['method'] == method and binding['seed'] == int(seed_text[5:]), 'run identity mismatch')
        require(binding['config']['online_encoding'] == encoding and binding['config']['student_steps'] == 300
                and binding['config']['scorer_steps'] == 300 and value['runner_exit_code'] == 0, 'run recipe/exit mismatch')
        require(value['provenance']['git_commit'] == commit and not value['provenance']['git_dirty'], 'dirty/different execution source')
        require(value['details']['training_trace'][-1]['step'] == 300, 'student stopped at wrong step')
        if method == 'future_no_execution':
            require(value['details']['outcome_scorer_training'][-1]['step'] == 300, 'scorer stopped at wrong step')
        require('student.pt' in artifact['files'] and 'execution.jsonl.gz' in artifact['files'], 'missing student/execution artifact')
        require(('scorer.pt' in artifact['files']) == (method == 'future_no_execution'), 'scorer inventory mismatch')
        rows = value['details']['causal_sequences']
        require(len(rows) == 16, 'incomplete sequences')
        pairkeys = [(r['metrics']['paired_group_id'], r['metrics']['sibling_index']) for r in rows]
        require(len(set(pairkeys)) == 16 and set(pairkeys) == {(f'rollout-pair:train:{g:06d}', s) for g in plan['dev_group_indices'] for s in (0, 1)}, 'paired groups differ')
        indexed[name] = {r['metrics']['sequence_id']: r for r in rows}
        require(len(indexed[name]) == 16, 'duplicate sequence ID')
        family, c10 = {}, {'decisions': 0, 'index_disagrees_active_correct': 0}
        for row in rows:
            choices = row['choices']
            require([c['step_index'] for c in choices] == list(range(20)), 'missing decisions')
            previous = True
            for i, choice in enumerate(choices):
                require(choice['selected_static_preflight_pass'], 'masked choice selected')
                require(choice['selected_index'] == max(range(16), key=lambda j: choice['probabilities'][j]), 'argmax mismatch')
                require(len(choice['probabilities']) == 16 and all(math.isfinite(p) and 0 <= p <= 1 for p in choice['probabilities'])
                        and abs(sum(choice['probabilities']) - 1.0) <= 1e-6, 'invalid probabilities')
                if i:
                    require(choices[i-1]['post_graph_hash'] == choice['base_graph_hash'], 'broken state chain')
                f, correct = choice['scenario_family'], choice['active_correct_after'] == 1.0
                if f == 'C10':
                    c10['decisions'] += 1
                    c10['index_disagrees_active_correct'] += int(correct and not choice['registered_selection_correct'])
                if previous and choice['ambiguity'] != 'epistemically_ambiguous_pivot':
                    counts = family.setdefault(f, {'eligible': 0, 'new_active_errors': 0, 'identity_confusions': 0, 'selected_labels_on_error': {}})
                    counts['eligible'] += 1
                    if not correct:
                        counts['new_active_errors'] += 1
                        label = choice['selected_program_label']
                        counts['selected_labels_on_error'][label] = counts['selected_labels_on_error'].get(label, 0) + 1
                        counts['identity_confusions'] += int((f, label) in [('C06', 'RELINK'), ('C08', 'REPLACE')])
                previous = correct
                decisions += 1
            close(row['metrics']['final_active_graph_correctness'], choices[-1]['active_correct_after'])
        for counts in family.values():
            counts['new_active_error_rate'] = counts['new_active_errors'] / counts['eligible']
        require(value['details']['onset_diagnostics'] == {'family_onsets': family, 'c10_index_active_disagreement': c10}, 'onset counts differ')
        triggered = [c for row in rows for c in row['choices'] if c['revisit_triggered']]
        for key, original in value['metrics']['causal_rollout'].items():
            if isinstance(original, (float, int)) and all(isinstance(row['metrics'].get(key), (float, int)) for row in rows):
                if key == 'triggered_revisit_count':
                    recalculated = len(triggered)
                elif key in ['triggered_revisit_commit_rate', 'triggered_revisit_active_resolution_rate']:
                    field = 'committed' if key == 'triggered_revisit_commit_rate' else 'active_correct_after'
                    require(bool(triggered), 'empty triggered denominator')
                    recalculated = sum(c[field] for c in triggered) / len(triggered)
                else:
                    recalculated = sum(row['metrics'][key] for row in rows) / 16
                close(original, recalculated)
                aggregates += 1
    comparisons = 0
    for entry in report['paired_descriptive_comparisons'] + report['method_descriptive_comparisons']:
        seed = entry['seed']
        if entry['contrast'] == 'roles_minus_padded':
            left, right = [f'{e}__{entry["method"]}__seed_{seed}' for e in ['argument_roles_v1', 'pooled_padded_v1']]
            require(report['runs'][left]['metrics']['student_parameters'] == report['runs'][right]['metrics']['student_parameters'], 'capacity mismatch')
        else:
            left = f'{entry["encoding"]}__cpmt_ctl_core__seed_{seed}'
            right = f'{entry["encoding"]}__{entry["contrast"][8:]}__seed_{seed}'
        require(indexed[left].keys() == indexed[right].keys(), 'comparison ID mismatch')
        for group in plan['dev_group_indices']:
            ids = [sid for sid, row in indexed[left].items() if row['metrics']['paired_group_id'] == f'rollout-pair:train:{group:06d}']
            require(len(ids) == 2, 'comparison pair incomplete')
            for key in METRICS:
                diff = sum(indexed[left][sid]['metrics'][key] - indexed[right][sid]['metrics'][key] for sid in ids) / 2
                close(diff, entry['by_paired_group'][str(group)][key])
        for key in METRICS:
            close(entry['mean'][key], sum(row[key] for row in entry['by_paired_group'].values()) / 8)
        comparisons += 1
    print(json.dumps({'status': 'ROLE_PILOT_EXPORT_AUDITED', 'models': len(indexed), 'sequences': len(indexed)*16,
                      'decisions': decisions, 'recomputed_sequence_aggregates': aggregates,
                      'paired_comparisons': comparisons, 'source_commit': commit, 'export_sha256': EXPECTED_SHA256,
                      'scope': 'export consistency and Git source; remote arrays/checkpoints/executions not locally rehashed or rerun'}, indent=2))


if __name__ == '__main__':
    main()
