"""Corrected train-only recipes and consumers; validation/test stay sealed.

Recipes bind one fixed matrix before dispatch. Selection reuses the registered
group-first reducers; neither concurrency nor diagnostic scores expand the grid.
"""
from __future__ import annotations
from pathlib import Path
import subprocess
import sys
import math

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
import numpy as np
from cpmt.m1_protocol import protocol_sha256
from cpmt.m1_s5_training import read_json, write_json, require
from cpmt.m1_s5_confirmation import verify_unit
from cpmt.run_provenance import file_sha256
from run_m1_corrected_probe import contracts, registration, fixed_groups, TRAIN_DIR, SEEDS
from run_m1_train_inner_dev_budget import (_architecture_settings, _grid_selection,
    _cell_group_means, _add_selection_uncertainty, _auxiliary_weight_selection)

PROBE_EXPORT = 'results/m1_v7_d054_corrected_endpoint_probe.json'
CHECK_EXPORT = 'results/m1_v7_d054_training_process_check.json'
ARCHES = ['cross_candidate_set_transformer_v1', 'shared_candidate_mlp_v1']
METHODS = ['cpmt_ctl_core', 'direct_classifier', 'direct_future_loss', 'execute_current_only', 'future_no_execution']
RATES = [0.0002, 0.0006, 0.002]
STEPS = [300, 1000, 3000, 10000]
UNCERTAINTY = {'bootstrap_resamples': 10000, 'bootstrap_seed': 260907, 'confidence': 0.95}


def require_clean_science():
    allowed = {PROBE_EXPORT, CHECK_EXPORT,
        *[f'results/m1_v7_d054_corrected_{k}.json' for k in ['checks', 'budget', 'refit']]}
    lines = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=ROOT, text=True).splitlines()
    require(all(line[3:] in allowed and 'D' not in line[:2] and 'R' not in line[:2] for line in lines),
        'source checkout must be clean; only exact phase exports may be uncommitted')


def training_config(architecture):
    hard, _, science = contracts()
    require(architecture in ARCHES, 'unregistered architecture')
    return {**science['config'], **_architecture_settings(hard, architecture),
        'protocol': 'm1-corrected-registered-training', 'device': 'cuda', 'cpu_threads': 1}


def consume_probe(root=ROOT):
    hard, rebuild, current = contracts(root)
    exported = read_json(root / PROBE_EXPORT)
    require(exported['schema_version'] == 'cpmt-corrected-probe-export-v1', 'wrong probe export')
    report = exported['endpoint_probe']
    require(report is not None and report['status'] == 'complete' and not exported['failures'], 'probe incomplete/failed')
    for action in ['prepare', 'train', 'evaluate', 'summarize']:
        require(exported['completion'][action]['exit_code'] == 0, 'probe stage failed: ' + action)
    require(exported['full_test']['exit_code'] == 0, 'probe full test failed')
    registered = registration(report, rebuild)
    require(registered is not None and registered == exported['post_probe_registration'], 'probe gate/registration failed')
    for key in ['contracts', 'hard_sha256', 'reuse_report_sha256', 'arrays_digest', 'config', 'seeds']:
        require(report['binding'][key] == current[key], 'probe scientific binding drift: ' + key)
    require(report['validation_access'] is False and report['test_access'] is False, 'probe crossed held-out boundary')
    # The old CPU run has a different global source hash. Check the actual probe
    # implementation and all scientific src files against its recorded commit.
    commit = report['provenance']['git_commit']
    names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', commit, '--', 'src'], cwd=root, text=True).splitlines()
    names += ['scripts/run_m1_corrected_probe.py', 'scripts/run_m1_endpoint_probe.py']
    for name in names:
        old = subprocess.check_output(['git', 'show', f'{commit}:{name}'], cwd=root)
        require(old.replace(b'\r\n', b'\n') == (root / name).read_bytes().replace(b'\r\n', b'\n'), 'probe source changed: ' + name)
    return exported, registered


def consume_process_check(source, root=ROOT):
    from run_m1_parallel_training_check import fixed_plan
    from m1_training_jobs import compare_artifacts
    payload = read_json(root / CHECK_EXPORT); report = payload['report']
    require(report is not None and payload['completion']['exit_code'] == payload['full_test']['exit_code'] == 0,
            'process check incomplete/failed')
    require(report['binding']['source_and_tests_sha256'] == source and report['binding']['plan'] == fixed_plan(), 'stale process check')
    require(report['pass'] and report['compared_jobs'] == 48 and report['training_jobs_executed'] == 96, 'incomplete process comparison')
    for mode in ['budget', 'refit']:
        first, second = (report['layouts'][f'{mode}_{n}']['artifacts'] for n in [1, 4])
        require(first.keys() == second.keys() == report['comparisons'][mode].keys(), 'process matrix mismatch')
        for key in first:
            actual = compare_artifacts(first[key], second[key])
            require(actual['pass'] and actual == report['comparisons'][mode][key], 'process comparison changed')
    return payload


def input_spec():
    policy = read_json(ROOT / 'configs/m1_train_reuse_policy.json')
    require(file_sha256(TRAIN_DIR / 'generation.ok.json') == policy['generation_marker_sha256'], 'generation marker changed')
    marker = read_json(TRAIN_DIR / 'generation.ok.json')
    path = TRAIN_DIR / 'train.npz'
    require(file_sha256(path) == marker['file_sha256']['train.npz'], 'train arrays bytes changed')
    return {'input_path': str(path), 'input_file_sha256': file_sha256(path),
        'arrays_digest': policy['arrays_digest'], 'groups': list(range(1000))}


def base_job(binding, architecture, seed, method, lr, checkpoints, *, mode='budget', weight=1.0, dependency=None):
    return {'schema_version': 'cpmt-training-path-job-v1', 'authorization': 'registered_train_only_path',
        'id': f'{mode}__{architecture}__{seed}__{method}__lr{lr:g}__w{weight:g}',
        'mode': mode, 'architecture': architecture, 'seed': seed, 'method': method,
        'learning_rate': lr, 'checkpoints': checkpoints, 'auxiliary_weight': weight,
        'device': 'cuda', 'torch_threads': 1, 'scorer_dependency': dependency,
        **binding['input'], 'source_and_tests_sha256': binding['source_and_tests_sha256'],
        'validation_access': False, 'test_access': False, 'formal_budget_authorized': mode == 'budget'}


def validate_recipe(recipe):
    require(recipe['schema_version'] == 'cpmt-corrected-training-recipe-v1', 'wrong recipe')
    stage = recipe['stage']; require(stage in ['capacity', 'scorers', 'students', 'c_weights', 'refit_scorers', 'refit_students'], 'wrong recipe stage')
    jobs = recipe['jobs']; require(len(jobs) == len({j['id'] for j in jobs}), 'duplicate job')
    expected = set()
    seeds = [7] if stage == 'capacity' else SEEDS
    methods = ['outcome_scorer', METHODS[0]] if stage == 'capacity' else (
        ['outcome_scorer'] if stage in ['scorers', 'refit_scorers'] else (['direct_future_loss'] if stage == 'c_weights' else METHODS))
    rates = RATES if stage in ['scorers', 'students'] else [None]
    weights = [0.1, 10.0] if stage == 'c_weights' else [1.0]
    for a in ARCHES:
        for s in seeds:
            for m in methods:
                for lr in rates:
                    for w in weights: expected.add((a, s, m, lr, w))
    observed = set()
    for j in jobs:
        require(j['architecture'] in ARCHES and j['seed'] in seeds and j['method'] in methods, 'job outside matrix')
        require(j['groups'] == list(range(1000)) and j['device'] == 'cuda' and j['torch_threads'] == 1, 'job population/device drift')
        require(j['validation_access'] is False and j['test_access'] is False, 'held-out access forbidden')
        mode = 'refit' if stage.startswith('refit') or stage == 'capacity' else 'budget'
        require(j['mode'] == mode and j['formal_budget_authorized'] == (mode == 'budget'), 'wrong population role')
        require(j['source_and_tests_sha256'] == recipe['binding']['source_and_tests_sha256'], 'source mismatch')
        require(all(j[k] == v for k, v in recipe['binding']['input'].items()), 'job input drift')
        lr = j['learning_rate']; steps = j['checkpoints']; weight = j['auxiliary_weight']
        if stage == 'capacity':
            require(lr == 0.0006 and steps == [2] and weight == 1.0, 'capacity diagnostic drift')
        elif stage in ['scorers', 'students']:
            require(lr in RATES and steps == STEPS and weight == 1.0, 'grid drift')
        else:
            spec = recipe['selected'][j['architecture']][j['method']]
            require(lr == spec['learning_rate'] and steps == [spec['steps']], 'selected compute drift')
            require(weight in [0.1, 10.0] if stage == 'c_weights' else weight == spec.get('auxiliary_weight', 1.0), 'selected weight drift')
        require(bool(j['scorer_dependency']) == (j['method'] == 'future_no_execution'), 'wrong scorer dependency')
        key = (j['architecture'], j['seed'], j['method'], lr if stage in ['scorers', 'students'] else None,
               weight if stage == 'c_weights' else 1.0)
        require(key not in observed, 'duplicate scientific job'); observed.add(key)
    require(observed == expected, 'incomplete recipe matrix')


def seal_recipe(path, stage, binding, jobs, selected=None):
    recipe = {'schema_version': 'cpmt-corrected-training-recipe-v1', 'stage': stage,
        'binding': binding, 'jobs': jobs, 'selected': selected or {}}
    validate_recipe(recipe)
    if path.exists(): require(read_json(path) == recipe, 'recipe changed; no new search')
    else: write_json(path, recipe)
    return [{**job, 'recipe_path': str(path), 'recipe_sha256': file_sha256(path)} for job in jobs]


def validate_registered_job(job):
    require(job['authorization'] == 'registered_train_only_path', 'unknown job authorization')
    path = Path(job['recipe_path'])
    require(file_sha256(path) == job['recipe_sha256'], 'recipe changed')
    recipe = read_json(path); validate_recipe(recipe)
    stripped = {k: v for k, v in job.items() if k not in ['recipe_path', 'recipe_sha256']}
    require(stripped in recipe['jobs'], 'unregistered job')
    ready = Path(recipe['binding']['ready_path'])
    require(file_sha256(ready) == recipe['binding']['ready_sha256'], 'prerequisite receipt changed')
    receipt = read_json(ready)
    require(receipt['pass'] and receipt['source_and_tests_sha256'] == job['source_and_tests_sha256'], 'prerequisites not passed')
    if recipe['stage'] != 'capacity':
        require(receipt.get('capacity_pass') and receipt.get('interfaces_pass'), 'formal budget before all checks')


def artifact_rows(paths):
    rows = []
    for name, value in sorted(paths.items()):
        path = Path(value); marker = read_json(path / 'complete.json'); verify_unit(path, marker['binding'])
        report = read_json(path / 'result.json'); job = report['binding']['job']
        require(report['binding'] == marker['binding'] and job['id'] == name, 'artifact identity drift')
        require([r['checkpoint'] for r in report['checkpoints']] == job['checkpoints'], 'incomplete checkpoint path')
        for r in report['checkpoints']:
            require(r['inner_dev_independent'] and r['inner_dev'] is not None, 'refit scores cannot select budgets')
            require(set(r['inner_dev']['reference_accuracy_by_group']) == {str(g) for g in fixed_groups()}, 'inner-dev groups changed')
            rows.append({'architecture': job['architecture'], 'method': job['method'], 'seed': job['seed'],
                'learning_rate': job['learning_rate'], 'auxiliary_weight': job['auxiliary_weight'], **r,
                'reference_accuracy_by_group': r['inner_dev']['reference_accuracy_by_group'],
                'artifact_path': str(path), 'marker_sha256': file_sha256(path / 'complete.json')})
    return rows


def select_grid(rows, method):
    subset = [r for r in rows if r['method'] == method]
    require({r['seed'] for r in subset} == set(SEEDS), 'selection missing registered seed')
    means = _cell_group_means(subset, metric_key='reference_accuracy_by_group',
        expected_cells={(lr, n) for lr in RATES for n in STEPS}, expected_observations_per_group=5, method=method)
    selected = _grid_selection({cell: list(groups.values()) for cell, groups in means.items()}, maximum_checkpoint=10000)
    _add_selection_uncertainty(selected, means, UNCERTAINTY)
    return {'learning_rate': selected['selected_learning_rate'], 'steps': selected['selected_checkpoint'],
            'auxiliary_weight': 1.0, 'selection': selected}, means


def select_c(rows, selected):
    lr, steps = selected['learning_rate'], selected['steps']
    values = {w: {} for w in [0.1, 1.0, 10.0]}; seen = set()
    for row in rows:
        if row['method'] != 'direct_future_loss' or row['learning_rate'] != lr or row['checkpoint'] != steps: continue
        key = (row['auxiliary_weight'], row['seed'])
        require(key not in seen and key[0] in values and key[1] in SEEDS, 'duplicate/unregistered C observation'); seen.add(key)
        for group, score in row['reference_accuracy_by_group'].items(): values[key[0]].setdefault(group, []).append(score)
    require(seen == {(w,s) for w in values for s in SEEDS}, 'incomplete sequential C weights')
    means = {}
    for weight, groups in values.items():
        require(set(groups) == {str(g) for g in fixed_groups()} and all(len(v) == 5 for v in groups.values()), 'C group/seed coverage drift')
        means[weight] = {g: float(np.mean(scores)) for g, scores in groups.items()}
    result = _auxiliary_weight_selection(means, anchor_weight=1.0, uncertainty=UNCERTAINTY)
    return {**selected, 'auxiliary_weight': result['selected_auxiliary_weight'], 'auxiliary_selection': result}


def dependency(paths, architecture, seed, selected):
    matches = []
    for value in paths.values():
        path = Path(value); marker = read_json(path / 'complete.json'); job = marker['binding']['job']
        if job['architecture'] == architecture and job['seed'] == seed and job['method'] == 'outcome_scorer' and job['learning_rate'] == selected['learning_rate']:
            require(selected['steps'] in job['checkpoints'], 'scorer selected checkpoint absent')
            matches.append({'path': str(path), 'checkpoint': selected['steps'], 'marker_sha256': file_sha256(path / 'complete.json')})
    require(len(matches) == 1, 'scorer dependency missing/ambiguous')
    return matches[0]
