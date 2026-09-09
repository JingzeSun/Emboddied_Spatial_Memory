"""Fixed ten-group CUDA process equivalence check for shared budget/refit paths.

Does not run alongside the current CPU probe: timing claims require recorded,
uncontended conditions. No new data generation or formal selection/refit release.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
import numpy as np
from cpmt.m1_s5_training import read_json, write_json, require
from cpmt.m1_s5_confirmation import complete_unit
from cpmt.m1_scope_rebuild import feasible_layouts
from cpmt.run_provenance import arrays_sha256, file_sha256, capture_run_provenance
from run_m1_budget_concurrency_probe import hardware
from run_m1_corrected_probe import contracts, TRAIN_DIR
from m1_training_jobs import (ARCHITECTURES, METHODS, CHECK_SEEDS, CHECK_GROUPS, CHECKPOINTS,
    dispatch, execute_job, compare_artifacts, validate_job, populations, check_config)


def no_active_probe():
    require(sys.platform == 'linux', 'AutoDL only')
    active = []
    for path in Path('/proc').glob('[0-9]*/cmdline'):
        try: command = path.read_bytes().replace(b'\0', b' ')
        except (FileNotFoundError, PermissionError, ProcessLookupError): continue
        if b'run_m1_corrected_probe.py' in command and b'evaluate' in command:
            active.append(int(path.parent.name))
    require(not active, 'current probe evaluation is still running; GPU check deferred: ' + str(active))


def fixed_plan():
    return {'schema_version': 'cpmt-training-process-check-plan-v1', 'groups': CHECK_GROUPS,
        'architectures': ARCHITECTURES, 'seeds': CHECK_SEEDS, 'modes': ['budget', 'refit'],
        'methods': ['outcome_scorer', *METHODS], 'checkpoints': CHECKPOINTS,
        'learning_rate': 0.0006, 'auxiliary_weight': 1.0, 'serial_workers': 1,
        'parallel_workers': 4, 'torch_threads': 1, 'device': 'cuda',
        'comparison': 'exact_tensor_values_and_checkpoint_metrics', 'relax_tolerance_after_result': False,
        'hyperparameters_selected': False, 'model_selection_performed': False,
        'formal_budget_authorized': False, 'validation_access': False, 'test_access': False,
        'population_reference': 'budget_hash_holdout_vs_refit_all_ten_train_groups',
        'resource_check_role': 'fixed_small_sample_only_not_full_1000_group_peak_memory',
        'runtime_role': 'engineering_measurement_not_full_budget_eta'}


def create_input(output, binding):
    policy = read_json(ROOT / 'configs/m1_train_reuse_policy.json')
    require(file_sha256(TRAIN_DIR / 'generation.ok.json') == policy['generation_marker_sha256'], 'generation marker changed')
    marker = read_json(TRAIN_DIR / 'generation.ok.json')
    def produce(staging):
        pieces = []; sources = {}
        for group in CHECK_GROUPS:
            name = f'shards/train_{group:06d}.npz'; p = TRAIN_DIR / name
            require(file_sha256(p) == marker['file_sha256'][name], 'training shard changed: ' + name)
            with np.load(p, allow_pickle=False) as source:
                arrays = {k: source[k] for k in source.files}
            require(len(arrays['y']) == 40 and set(arrays['group'].tolist()) == {0}, 'unexpected shard row numbering')
            arrays['group'] = np.full(40, group, dtype=np.int64)
            pieces.append(arrays); sources[name] = marker['file_sha256'][name]
        combined = {key: np.concatenate([piece[key] for piece in pieces]) for key in pieces[0]}
        np.savez(staging / 'train_subset.npz', **combined)
        fit, inner, _ = populations(combined, 'budget')
        write_json(staging / 'manifest.json', {'arrays_digest': arrays_sha256(combined), 'sources': sources,
            'original_arrays_digest': policy['arrays_digest'], 'groups': CHECK_GROUPS,
            'fit_groups': sorted(set(fit['group'].tolist())), 'inner_dev_groups': sorted(set(inner['group'].tolist())),
            'label_mask_reused': True, 'data_regenerated': False, 'validation_access': False, 'test_access': False})
    complete_unit(output / 'input', binding, produce)
    manifest = read_json(output / 'input/manifest.json')
    return output / 'input/train_subset.npz', manifest


def make_job(mode, architecture, seed, method, input_path, manifest, binding, dependency=None):
    job = {'schema_version': 'cpmt-training-path-job-v1', 'authorization': 'fixed_train_only_engineering_check',
        'id': f'{mode}__{architecture}__{seed}__{method}', 'mode': mode, 'architecture': architecture,
        'seed': seed, 'method': method, 'groups': CHECK_GROUPS, 'checkpoints': CHECKPOINTS,
        'learning_rate': 0.0006, 'auxiliary_weight': 1.0, 'device': 'cuda', 'torch_threads': 1,
        'input_path': str(input_path), 'input_file_sha256': file_sha256(input_path), 'arrays_digest': manifest['arrays_digest'],
        'source_and_tests_sha256': binding['source_and_tests_sha256'], 'scorer_dependency': dependency,
        'validation_access': False, 'test_access': False, 'formal_budget_authorized': False}
    validate_job(job)
    return job


def run(output):
    no_active_probe()
    hard, rebuild, science = contracts()
    from m1_corrected_training_plan import require_clean_science
    require_clean_science()
    binding = {'source_and_tests_sha256': science['source_and_tests_sha256'], 'science': science, 'plan': fixed_plan()}
    output.mkdir(parents=True, exist_ok=True)
    require(not (output / 'attempt.json').exists(), 'previous check retained; no automatic restart')
    machine = hardware()
    layouts, _ = feasible_layouts(rebuild, cpu_capacity=machine['cpu_capacity'],
        gpu_free_gib=machine['gpu_free_gib'], host_available_gib=machine['host_available_gib'])
    require({'workers': 4, 'threads': 1} in layouts, 'four-worker headroom unavailable; do not silently change fixed comparison')
    write_json(output / 'attempt.json', {'binding': binding, 'hardware': machine,
        'provenance': capture_run_provenance(ROOT, component='parallel_training_check')})
    try:
        input_path, manifest = create_input(output, binding)
        all_runs, comparisons = {}, {}
        for mode in ['budget', 'refit']:
            for workers in [1, 4]:
                no_active_probe()
                layout = output / f'{mode}_workers_{workers}'; began = time.monotonic()
                configs = {a: check_config(a) for a in ARCHITECTURES}
                def execute(job):
                    return execute_job(job, layout / job['id'], configs[job['architecture']], machine['gpu_uuid'])
                scorers = [make_job(mode, a, s, 'outcome_scorer', input_path, manifest, binding)
                           for a in ARCHITECTURES for s in CHECK_SEEDS]
                scorer_results = dispatch(scorers, workers, execute)
                students = []
                for a in ARCHITECTURES:
                    for s in CHECK_SEEDS:
                        key = f'{mode}__{a}__{s}__outcome_scorer'
                        path = Path(scorer_results[key])
                        for method in METHODS:
                            dep = {'path': str(path), 'checkpoint': 30, 'marker_sha256': file_sha256(path / 'complete.json')} if method == 'future_no_execution' else None
                            students.append(make_job(mode, a, s, method, input_path, manifest, binding, dep))
                results = {**scorer_results, **dispatch(students, workers, execute)}
                # The same declared student architecture is used by every method.
                for a in ARCHITECTURES:
                    signatures = [read_json(Path(path) / 'result.json')['parameter_signature']
                        for key, path in results.items() if f'__{a}__' in key and not key.endswith('__outcome_scorer')]
                    require(all(signature == signatures[0] for signature in signatures), 'A-E parameter mismatch')
                all_runs[f'{mode}_{workers}'] = {'workers': workers, 'wall_seconds': time.monotonic()-began, 'artifacts': results}
                print(f'TRAINING_CHECK_LAYOUT_OK mode={mode} workers={workers} jobs={len(results)}', flush=True)
            first, second = all_runs[f'{mode}_1']['artifacts'], all_runs[f'{mode}_4']['artifacts']
            require(first.keys() == second.keys(), 'incomplete comparison job matrix')
            comparisons[mode] = {key: compare_artifacts(first[key], second[key]) for key in first}
        passed = all(row['pass'] for mode in comparisons.values() for row in mode.values())
        report = {'schema_version': 'cpmt-training-process-check-report-v1', 'binding': binding,
            'hardware': machine, 'input_manifest': manifest, 'layouts': all_runs, 'comparisons': comparisons,
            'pass': passed, 'compared_jobs': sum(map(len, comparisons.values())),
            'training_jobs_executed': 96, 'formal_budget_authorized': False,
            'validation_access': False, 'test_access': False,
            'full_budget_or_s5_registration_consumption_implemented': True,
            'full_budget_or_s5_server_validation_completed': False,
            'full_population_resource_check_completed': False}
        write_json(output / 'report.json', report)
        print(f'TRAINING_PROCESS_CHECK_RESULT pass={str(passed).lower()} compared_jobs=48', flush=True)
        return 0 if passed else 1
    except BaseException:
        write_json(output / 'failure.json', {'traceback': traceback.format_exc(), 'test_access': False})
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    raise SystemExit(run(parser.parse_args().output))
