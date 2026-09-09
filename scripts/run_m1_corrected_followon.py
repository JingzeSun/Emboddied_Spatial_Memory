"""Prepared train-only follow-on stages: reuse, capacity, interfaces, budget, refit.

All actions are separately durable. Existing probe trajectories and short GPU
weights supply the interface evidence. This entry never generates/opens held-out
data and cannot launch S5 confirmation or S6 test.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
import numpy as np
import torch
from cpmt.m1_protocol import protocol_sha256
from cpmt.m1_s5_confirmation import complete_unit, verify_unit
from cpmt.m1_s5_training import read_json, write_json, require
from cpmt.run_provenance import file_sha256, capture_run_provenance
from m1_corrected_training_plan import (ARCHES, METHODS, RATES, STEPS, SEEDS, PROBE_EXPORT, CHECK_EXPORT,
    consume_probe, consume_process_check, contracts, input_spec, base_job, seal_recipe,
    training_config, artifact_rows, select_grid, select_c, dependency, fixed_groups)
from m1_training_jobs import dispatch, execute_job, load_model
from m1_paired_evaluation import (run_serial, evaluate_parallel, serial_forward_replay,
    registered_statistics, validate_rows)
from run_m1_budget_concurrency_probe import hardware
from run_m1_parallel_training_check import no_active_probe

ORDER = ['prepare', 'capacity', 'interfaces', 'budget', 'refit']


def immutable_json(path, value):
    if path.exists(): require(read_json(path) == value, 'existing bound document changed: ' + str(path))
    else: write_json(path, value)
    return value


def load_binding(output):
    binding = read_json(output / 'binding.json')
    _, _, current = contracts()
    require(binding['source_and_tests_sha256'] == current['source_and_tests_sha256'], 'follow-on source changed')
    for name, digest in binding['input_exports'].items(): require(file_sha256(ROOT / name) == digest, 'input export changed: ' + name)
    require(binding['input'] == input_spec(), 'training source changed')
    return binding


def prepare(output):
    no_active_probe()
    _, _, current = contracts()
    exported, registered = consume_probe()
    checked = consume_process_check(current['source_and_tests_sha256'])
    output.mkdir(parents=True, exist_ok=True)
    # Pin the existing probe directory through its saved artifact bindings, not
    # the current source-derived path (the server checkout has since advanced).
    raw = exported['endpoint_probe']
    old_source = raw['binding']['source_and_tests_sha256']
    probe_dir = Path('/root/autodl-tmp/cpmt_outputs') / ('m1-v7-d054-fixed-probe-' + old_source[:12]) / 'run'
    verify_unit(probe_dir / 'summary', raw['binding'])
    require(read_json(probe_dir / 'summary/report.json') == raw, 'server probe report differs from export')
    binding = {'schema_version': 'cpmt-corrected-followon-binding-v1',
        'source_and_tests_sha256': current['source_and_tests_sha256'],
        'input_exports': {n: file_sha256(ROOT / n) for n in [PROBE_EXPORT, CHECK_EXPORT]},
        'input': input_spec(), 'registration': registered, 'registration_sha256': protocol_sha256(registered),
        'probe_dir': str(probe_dir), 'probe_binding': raw['binding'],
        'validation_access': False, 'test_access': False}
    immutable_json(output / 'binding.json', binding)
    complete_unit(output / 'prepared', binding, lambda p: write_json(p / 'report.json', {
        'pass': True, 'source_and_tests_sha256': binding['source_and_tests_sha256'],
        'reused_probe_models': 20, 'probe_decisions_not_repeated': 120600,
        'process_check_pairs_verified': checked['report']['compared_jobs'],
        'capacity_pass': False, 'interfaces_pass': False, 'formal_budget_authorized': False,
        'test_access': False, 'validation_access': False}))


def job_binding(output, binding, *, capacity=False):
    ready = output / ('prepared/report.json' if capacity else 'ready.json')
    receipt = read_json(ready); require(receipt['pass'], 'prerequisite failed')
    return {**binding, 'ready_path': str(ready), 'ready_sha256': file_sha256(ready)}


def run_jobs(output, stage, binding, jobs, selected=None):
    no_active_probe()
    machine = hardware()
    require(machine['cpu_capacity'] >= 4 and machine['host_available_gib'] >= 34 and machine['gpu_free_gib'] >= 18,
        'four-worker resource reserve unavailable; review without changing scientific recipe')
    jobs = seal_recipe(output / f'{stage}.recipe.json', stage, binding, jobs, selected)
    configs = {a: training_config(a) for a in ARCHES}
    began = time.monotonic()
    paths = dispatch(jobs, 4, lambda job: execute_job(job, output / stage / job['id'], configs[job['architecture']], machine['gpu_uuid']))
    for architecture in ARCHES:
        reports = [read_json(Path(p) / 'result.json') for p in paths.values()]
        signatures = [r['parameter_signature'] for r in reports if r['binding']['job']['architecture'] == architecture
            and r['binding']['job']['method'] != 'outcome_scorer']
        require(not signatures or all(s == signatures[0] for s in signatures), 'A-E parameter mismatch')
    value = {'stage': stage, 'artifacts': paths, 'wall_seconds': time.monotonic()-began, 'hardware_before': machine,
        'recipe_sha256': file_sha256(output / f'{stage}.recipe.json')}
    # A successful stage is reused from this file before run_jobs is called.
    write_json(output / f'{stage}.paths.json', value)
    return value


def completed_paths(output, stage):
    path = output / f'{stage}.paths.json'
    if not path.exists(): return None
    value = read_json(path)
    recipe = read_json(output / f'{stage}.recipe.json')
    require(value['recipe_sha256'] == file_sha256(output / f'{stage}.recipe.json'), 'recipe changed')
    require(set(value['artifacts']) == {j['id'] for j in recipe['jobs']}, 'incomplete successful model matrix')
    for key, p in value['artifacts'].items():
        unit = Path(p); marker = read_json(unit / 'complete.json'); verify_unit(unit, marker['binding'])
        job = marker['binding']['job']
        require(job['id'] == key and job['recipe_sha256'] == value['recipe_sha256'], 'model recipe changed')
        completion = read_json(unit.parent / 'process.completed.json')
        require(completion['exit_code'] == 0 and completion['artifact_marker_sha256'] == file_sha256(unit / 'complete.json'), 'model process not successful')
    return value


def capacity(output, binding):
    verify_unit(output / 'prepared', binding)
    require(not (output / 'capacity.paths.json').exists(), 'capacity was already executed; reuse completed report instead')
    jb = job_binding(output, binding, capacity=True)
    jobs = [base_job(jb, a, 7, m, 0.0006, [2], mode='refit') for a in ARCHES for m in ['outcome_scorer', METHODS[0]]]
    samples = []; errors = []; stopped = threading.Event()
    def monitor():
        while not stopped.is_set():
            try: samples.append(hardware())
            except Exception as error: errors.append(str(error))
            stopped.wait(1.0)
    watcher = threading.Thread(target=monitor, daemon=True); watcher.start()
    try: result = run_jobs(output, 'capacity', jb, jobs)
    finally: stopped.set(); watcher.join()
    reports = [read_json(Path(p) / 'result.json') for p in result['artifacts'].values()]
    require(samples and not errors, 'capacity monitor incomplete')
    require(all(r['binding']['job']['groups'] == list(range(1000)) for r in reports), 'not full-population capacity')
    # All four allocations + optimizer states ran on the full refit population.
    # This is a measured launch screen, not a guarantee against every future OOM.
    passed = min(s['gpu_free_gib'] for s in samples) >= 2 and min(s['host_available_gib'] for s in samples) >= 2
    report = {'pass': passed, 'capacity_pass': passed, 'source_and_tests_sha256': binding['source_and_tests_sha256'],
        'workers': 4, 'steps': 2, 'train_groups': 1000, 'modes': ['full_train_refit'],
        'sampled_resources': samples, 'peak_vram_bytes_by_job': {r['binding']['job']['id']: r['peak_vram_bytes'] for r in reports},
        'scores_used_for_selection': False, 'full_budget_completion_guaranteed': False,
        'validation_access': False, 'test_access': False}
    write_json(output / 'capacity.report.json', report)
    require(passed, 'full-population resource reserve failed; preserve capacity report')


def interfaces(output, binding):
    verify_unit(output / 'prepared', binding)
    require(read_json(output / 'capacity.report.json')['pass'], 'capacity check not passed')
    exported = read_json(ROOT / PROBE_EXPORT); checked = read_json(ROOT / CHECK_EXPORT)['report']
    probe_dir = Path(binding['probe_dir']); probe_binding = binding['probe_binding']
    groups = fixed_groups()[:4]  # Fixed by ID/hash before model outcomes; no generation.
    specs = []
    for g in groups:
        directory = probe_dir / 'audits' / f'group_{g:06d}'
        verify_unit(directory, {**probe_binding, 'group': g})
        path = directory / f'train_inner_dev_{g:06d}.json.gz'
        specs.append({'path': str(path), 'sha256': file_sha256(path), 'paired_group_id': f'rollout-pair:train:{g:06d}'})
    reports = {}; all_payloads = {}
    # Short refit weights from the existing process check; no new training.
    paths = checked['layouts']['refit_4']['artifacts']
    hard, _, _ = contracts()
    for architecture in ARCHES:
        payloads = {}
        for method in ['cpmt_ctl_core', 'direct_future_loss', 'future_no_execution']:
            key = f'refit__{architecture}__7__{method}'; path = Path(paths[key])
            marker = read_json(path / 'complete.json'); verify_unit(path, marker['binding'])
            model_spec = {'path': str(path), 'checkpoint': 30, 'marker_sha256': file_sha256(path / 'complete.json')}
            model, payload = load_model(path, marker['binding'], 30, torch.device('cpu'))
            config = {**marker['binding']['config'], 'device': 'cpu', 'cpu_threads': 1,
                'commit_probability': 0.0, 'margin_threshold': 0.0,
                'candidate_availability_policy': binding['registration']['candidate_availability_policy'],
                'current_evidence_scope_ranks': 3, 'mechanism_diagnostic_slices': hard['evaluation']['mechanism_diagnostic_slices']}
            torch.set_num_threads(1)
            location = output / 'interfaces' / architecture / method
            unit_binding = {'source': binding['source_and_tests_sha256'], 'model': model_spec, 'audits': specs, 'config': config}
            serial = run_serial(location / 'serial', unit_binding, model, specs, config)
            del model, payload
            parallel = evaluate_parallel(location / 'parallel', unit_binding, model_spec, specs, config, 4)
            first = sorted(serial['sequences'], key=lambda r: (r['metrics']['paired_group_id'], r['metrics']['sibling_index']))
            require(first == parallel['sequences'], 'serial/unsharded vs parallel/merged scientific rows differ')
            # The pool has closed before the separate forward replay.
            latency = serial_forward_replay(model_spec, parallel['shards'])
            require(latency['forward_calls'] == 160, 'latency replay incomplete')
            payloads[method] = [{'aggregate': {'seed': 7}, 'sequences': parallel['sequences']}]
            reports[key] = {'pass': True, 'paired_groups': 4, 'decisions_per_layout': 160,
                'scientific_rows_exactly_equal': True, 'parallel': parallel, 'serial_latency': latency,
                'model': model_spec, 'serial_path': str(location / 'serial'),
                'serial_marker_sha256': file_sha256(location / 'serial/complete.json')}
            print(f'INTERFACE_MODEL_OK architecture={architecture} method={method} pairs=4 exact_equal=true', flush=True)
        statistics = registered_statistics(payloads, binding['registration'], split='train',
            groups=[s['paired_group_id'] for s in specs], seeds=[7], engineering=True)
        all_payloads[architecture] = statistics
    # Reuse full 201-group probe rows to exercise five-seed registered statistics.
    # This loads JSON metrics only; it never executes another probe trajectory.
    full = {}
    for short, method in [('A', METHODS[0]), ('C', 'direct_future_loss'), ('E', 'future_no_execution')]:
        full[method] = []
        for seed in SEEDS:
            path = probe_dir / 'causal' / f'{short}_{seed}'
            marker = verify_unit(path, {**probe_binding, 'method': short, 'seed': seed})
            require(marker == exported['endpoint_probe']['causal_files'][f'{short}_{seed}'], 'probe causal artifact changed')
            result = read_json(path / 'result.json')
            full[method].append({'aggregate': {'seed': seed}, 'sequences': result['sequences']})
    reused_stats = registered_statistics(full, binding['registration'], split='train',
        groups=[f'rollout-pair:train:{g:06d}' for g in fixed_groups()], engineering=True)
    report = {'pass': True, 'interfaces_pass': True, 'source_and_tests_sha256': binding['source_and_tests_sha256'],
        'models': reports, 'small_train_statistics': all_payloads, 'reused_probe_statistics': reused_stats,
        'probe_decisions_reexecuted': 0, 'additional_models_trained': 0,
        'short_model_decisions_per_layout': 960, 'statistics_selection_effect': 'none_engineering_only',
        'formal_validation_or_test_result': False, 'validation_access': False, 'test_access': False}
    write_json(output / 'interfaces.report.json', report)
    require(read_json(output / 'interfaces.report.json') == report, 'interface report readback failed')
    immutable_json(output / 'ready.json', {'pass': True, 'capacity_pass': True, 'interfaces_pass': True,
        'source_and_tests_sha256': binding['source_and_tests_sha256'], 'binding_sha256': protocol_sha256(binding),
        'capacity_report_sha256': file_sha256(output / 'capacity.report.json'),
        'interfaces_report_sha256': file_sha256(output / 'interfaces.report.json'),
        'formal_budget_authorized': True, 'validation_access': False, 'test_access': False})


def budget(output, binding):
    jb = job_binding(output, binding)
    ready = read_json(output / 'ready.json')
    for name in ['capacity', 'interfaces']:
        require(ready[name + '_report_sha256'] == file_sha256(output / f'{name}.report.json'), 'readiness report changed')
    scorer_stage = completed_paths(output, 'scorers') or run_jobs(output, 'scorers', jb,
        [base_job(jb, a, s, 'outcome_scorer', lr, STEPS) for a in ARCHES for s in SEEDS for lr in RATES])
    scorer_rows = artifact_rows(scorer_stage['artifacts']); selected = {}
    for a in ARCHES:
        spec, _ = select_grid([r for r in scorer_rows if r['architecture'] == a], 'outcome_scorer')
        selected[a] = {'outcome_scorer': spec}
    immutable_json(output / 'scorer.selection.json', selected)
    jobs = []
    for a in ARCHES:
        for s in SEEDS:
            dep = dependency(scorer_stage['artifacts'], a, s, selected[a]['outcome_scorer'])
            for m in METHODS:
                for lr in RATES: jobs.append(base_job(jb, a, s, m, lr, STEPS, dependency=dep if m == 'future_no_execution' else None))
    student_stage = completed_paths(output, 'students') or run_jobs(output, 'students', jb, jobs, selected)
    student_rows = artifact_rows(student_stage['artifacts']); means = {}
    for a in ARCHES:
        means[a] = {}
        for m in METHODS:
            selected[a][m], means[a][m] = select_grid([r for r in student_rows if r['architecture'] == a], m)
    immutable_json(output / 'compute.selection.json', selected)
    jobs = [base_job(jb, a, s, 'direct_future_loss', selected[a]['direct_future_loss']['learning_rate'],
        [selected[a]['direct_future_loss']['steps']], weight=w) for a in ARCHES for s in SEEDS for w in [0.1, 10.0]]
    auxiliary_stage = completed_paths(output, 'c_weights') or run_jobs(output, 'c_weights', jb, jobs, selected)
    auxiliary_rows = artifact_rows(auxiliary_stage['artifacts'])
    for a in ARCHES:
        selected[a]['direct_future_loss'] = select_c([r for r in student_rows + auxiliary_rows if r['architecture'] == a], selected[a]['direct_future_loss'])
    # Preserve the registered shared-compute and A/E cross-cell diagnostics.
    from run_m1_train_inner_dev_budget import _grid_selection, _add_selection_uncertainty
    from m1_corrected_training_plan import UNCERTAINTY
    diagnostics = {}
    for a in ARCHES:
        shared_groups = {cell: {g: float(np.mean([means[a][m][cell][g] for m in METHODS])) for g in sorted(means[a][METHODS[0]][cell])}
            for cell in means[a][METHODS[0]]}
        combined = {cell: list(by_group.values()) for cell, by_group in shared_groups.items()}
        shared = _grid_selection(combined, maximum_checkpoint=10000)
        _add_selection_uncertainty(shared, shared_groups, UNCERTAINTY)
        cell = (shared['selected_learning_rate'], shared['selected_checkpoint'])
        cross = {}
        for m in [METHODS[0], 'future_no_execution']:
            point = (selected[a][m]['learning_rate'], selected[a][m]['steps'])
            cross[m] = {'learning_rate': point[0], 'steps': point[1],
                'A': float(np.mean(list(means[a][METHODS[0]][point].values()))),
                'E': float(np.mean(list(means[a]['future_no_execution'][point].values())))}
        diagnostics[a] = {'shared_compute_selection': shared,
            'shared_reference_accuracy_by_method': {m: float(np.mean(list(means[a][m][cell].values()))) for m in METHODS},
            'A_E_cross_compute': cross, 'role': 'diagnostic_not_architecture_or_seed_selection'}
    report = {'schema_version': 'cpmt-corrected-budget-report-v1', 'binding': binding,
        'selected': selected, 'compute_diagnostics': diagnostics,
        'scorer_rows': scorer_rows, 'student_rows': student_rows, 'c_auxiliary_rows': auxiliary_rows,
        'artifacts': {**scorer_stage['artifacts'], **student_stage['artifacts'], **auxiliary_stage['artifacts']},
        'optimizer_paths': 200, 'checkpoint_observations': 740, 'fitting_groups': 799, 'inner_dev_groups': 201,
        'inner_dev_is_final_unbiased_accuracy': False, 'architectures_selected': False,
        'test_access': False, 'validation_access': False, 'formal_test_release': False}
    require(len(report['artifacts']) == 200 and len(scorer_rows + student_rows + auxiliary_rows) == 740, 'budget matrix incomplete')
    immutable_json(output / 'budget.report.json', report)


def refit(output, binding):
    budget_report = read_json(output / 'budget.report.json'); require(budget_report['binding'] == binding, 'budget binding drift')
    for stage in ['scorers', 'students', 'c_weights']: require(completed_paths(output, stage), 'budget artifacts missing')
    # Recompute selections from existing checkpoint rows, not new training.
    # immutable_json rejects altered selected settings/report content.
    budget(output, binding)
    selected = budget_report['selected']; jb = job_binding(output, binding)
    jobs = []
    for a in ARCHES:
        for s in SEEDS:
            spec = selected[a]['outcome_scorer']; jobs.append(base_job(jb, a, s, 'outcome_scorer', spec['learning_rate'], [spec['steps']], mode='refit'))
    scorers = completed_paths(output, 'refit_scorers') or run_jobs(output, 'refit_scorers', jb, jobs, selected)
    jobs = []
    for a in ARCHES:
        for s in SEEDS:
            dep = dependency(scorers['artifacts'], a, s, selected[a]['outcome_scorer'])
            for m in METHODS:
                spec = selected[a][m]
                jobs.append(base_job(jb, a, s, m, spec['learning_rate'], [spec['steps']], mode='refit',
                    weight=spec['auxiliary_weight'], dependency=dep if m == 'future_no_execution' else None))
    students = completed_paths(output, 'refit_students') or run_jobs(output, 'refit_students', jb, jobs, selected)
    models = {}
    for key, value in {**scorers['artifacts'], **students['artifacts']}.items():
        path = Path(value); result = read_json(path / 'result.json'); job = result['binding']['job']
        require(all(r['inner_dev'] is None and not r['inner_dev_independent'] for r in result['checkpoints']), 'refit falsely reports independent inner-dev')
        models[key] = {'path': str(path), 'checkpoint': job['checkpoints'][0], 'marker_sha256': file_sha256(path / 'complete.json'),
            'architecture': job['architecture'], 'seed': job['seed'], 'method': job['method'],
            'model_sha256': file_sha256(path / f'checkpoint_{job["checkpoints"][0]}.pt'),
            'training': result}
    require(len(models) == 60, 'refit model matrix incomplete')
    immutable_json(output / 'refit.report.json', {'schema_version': 'cpmt-corrected-s5-training-report-v1',
        'binding': binding, 'budget_report_sha256': file_sha256(output / 'budget.report.json'),
        'selected': selected, 'models': models, 'trained_models': 60, 'train_groups': 1000,
        'label_mask_reused': True, 'inner_dev_independent': False,
        'validation_access': False, 'test_access': False, 'formal_test_release': False})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=ORDER); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); no_active_probe()
    if args.action == 'prepare': prepare(args.output)
    else: globals()[args.action](args.output, load_binding(args.output))
    print(f'CORRECTED_FOLLOWON_OK action={args.action} validation=false test_access=false', flush=True)


if __name__ == '__main__': main()
