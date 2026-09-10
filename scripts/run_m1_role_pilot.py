"""D-057 server pilot: test -> prepare -> run --seed 7/19 -> export -> verify.

Each completed unit is hashed and reused. Partial units stop for review; there
is no retry, checkpoint selection, test access, or automatic larger experiment.
Chinese definitions and step boundaries are in HARD_CONDITION_EXPERIMENT.md.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
import gzip
import json
import multiprocessing as mp
from pathlib import Path
import platform
import socket
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts'), str(ROOT / 'tests')]

import numpy as np
import torch
from cpmt.dev_learning import candidate_admissibility_mask, masked_candidate_probabilities, tensors
from cpmt.executor import validate_graph
from cpmt.m1_af_method import run_af_method
from cpmt.m1_af_rollout import _program_label, resolve_af_smoke_config, selection_error_decomposition
from cpmt.m1_protocol import load_and_validate
from cpmt.m1_role_encoding import ENCODINGS, configure, rollout_metrics
from cpmt.m1_role_pilot import encoded_arrays, error_diagnostics, paired_differences, partition, split_arrays
from cpmt.m1_rollout import generate_m1_paired_rollout_split
from cpmt.m1_s5_confirmation import complete_unit, verify_unit
from cpmt.m1_s5_training import read_json, require, write_json
from cpmt.run_provenance import arrays_sha256, capture_run_provenance, file_sha256, source_tree_sha256
from m1_paired_evaluation import ReplayableAudits, validate_rows
from run_m1_corrected_confirmation import data_health

PLAN = ROOT / 'configs/m1_role_pilot.json'
CERTIFICATE = ROOT / 'results/m1_d056_role_encoding_server_check.json'
CERTIFICATE_SHA256 = 'aa4586be7a0ad37c29f765afbba97ffea377adfdaa93238bd7f2acfcfdcfc833'
METHODS = ['cpmt_ctl_core', 'direct_future_loss', 'future_no_execution']


def setup():
    require(platform.system() == 'Linux' and 'microsoft' not in platform.release().lower(),
            'run on the independent Linux server; local Windows/WSL CPU is excluded')
    actual = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=ROOT, text=True).strip()
    require(Path(actual).resolve() == ROOT, 'repository root mismatch')
    code_roots = ['src', 'scripts', 'configs', 'tests']
    dirty = subprocess.check_output(['git', 'status', '--porcelain', '--', *code_roots], cwd=ROOT, text=True)
    require(not dirty.strip(), 'commit/push/pull the complete stage before running')
    require(file_sha256(CERTIFICATE) == CERTIFICATE_SHA256, 'accepted D-056 server evidence changed/missing')
    plan = read_json(PLAN)
    require(plan['schema_version'] == 'cpmt-m1-role-pilot-v1' and plan['decision'] == 'D-057', 'wrong pilot contract')
    require(all(plan[k] is False for k in ['formal_run', 'test_access', 'validation_access', 'automatic_expansion']), 'pilot boundary drift')
    require(plan['split'] == 'train' and plan['start_group_index'] == 1000 and plan['paired_groups'] == 20, 'pilot data drift')
    require(plan['encodings'] == list(ENCODINGS) and plan['methods'] == METHODS and plan['seeds'] == [7, 19], 'pilot matrix drift')
    require(plan['student_steps'] == plan['scorer_steps'] == 300 and plan['learning_rate'] == 0.0006, 'pilot budget drift')
    require(plan['device'] == 'cpu' and plan['cpu_threads'] == 1, 'pilot execution drift')
    partition(plan)
    torch.set_num_threads(1)
    binding = {'plan_sha256': file_sha256(PLAN),
               'source_sha256': source_tree_sha256(ROOT, roots=code_roots),
               'd056_server_certificate_sha256': CERTIFICATE_SHA256,
               'environment': {'python': platform.python_version(), 'numpy': np.__version__,
                               'torch': str(torch.__version__), 'platform': platform.platform(),
                               'hostname': socket.gethostname(), 'python_executable': sys.executable}}
    return plan, binding, ROOT / plan['output']


def test_stage(out, binding):
    def produce(staging):
        suite = unittest.defaultTestLoader.loadTestsFromName('test_m1_role_pilot')
        expected = suite.countTestCases()
        class Tee:
            def __init__(self, log): self.log = log
            def write(self, value):
                sys.stdout.write(value)
                self.log.write(value)
            def flush(self):
                sys.stdout.flush()
                self.log.flush()
        with (staging / 'tests.log').open('w', encoding='utf-8') as log:
            result = unittest.TextTestRunner(stream=Tee(log), verbosity=2).run(suite)
        receipt = {'tests_run': result.testsRun, 'expected': expected, 'failures': len(result.failures),
                   'errors': len(result.errors), 'skipped': len(result.skipped),
                   'exit_code': 0 if result.wasSuccessful() else 1}
        write_json(staging / 'receipt.json', receipt)
        require(result.wasSuccessful() and result.testsRun == expected and expected > 0 and not result.skipped,
                'pilot integration tests failed/incomplete')
    complete_unit(out / 'tests', binding, produce)
    print('ROLE-P0_TESTS_OK exit=0', flush=True)


def dependency(out, binding):
    verify_unit(out / 'tests', binding)
    return {**binding, 'pilot_tests_marker_sha256': file_sha256(out / 'tests/complete.json')}


def make_group(task):
    index, directory, binding = task
    torch.set_num_threads(1)
    path = Path(directory) / f'group_{index:06d}'
    unit_binding = {**binding, 'group_index': index, 'split': 'train'}
    def produce(staging):
        began = time.monotonic()
        hard = load_and_validate(ROOT / 'configs/m1_hard_condition_v7.json')
        _, audits, summary = generate_m1_paired_rollout_split(hard, 'train', paired_groups=1, start_group_index=index)
        matrices = encoded_arrays(hard, audits, index)
        for mode, arrays in matrices.items():
            np.savez(staging / f'{mode}.npz', **arrays)
        with gzip.open(staging / 'audits.json.gz', 'wt', encoding='utf-8', compresslevel=1) as stream:
            json.dump(audits, stream, allow_nan=False)
        coverage = {}
        for audit in audits:
            validate_graph(audit['initial_world'])
            for step in [*audit['steps'], *audit.get('recovery_examples', [])]:
                for candidate in step['executed_candidates']:
                    if candidate['legal']:
                        validate_graph(candidate['post_graph'])
            for step in audit['steps']:
                ref = step['executed_candidates'][step['reference_program_index']]
                row = coverage.setdefault(step['scenario_family'], {'decisions': 0, 'covered': 0})
                row['decisions'] += 1
                row['covered'] += int(ref['legal'] and ref['static_preflight_pass'])
        write_json(staging / 'summary.json', {'generator_summary': summary, 'coverage': coverage,
            'arrays_digests': {m: arrays_sha256(a) for m, a in matrices.items()},
            'learning_rows': 40, 'recovery_rows': 2, 'invariant_violations': 0,
            'wall_seconds': time.monotonic() - began})
    complete_unit(path, unit_binding, produce)
    return index


def prepare(plan, binding, out):
    base = dependency(out, binding)
    fit, dev = partition(plan)
    tasks = [(g, str(out / 'groups'), base) for g in sorted(fit + dev)]
    with ProcessPoolExecutor(max_workers=plan['generation_workers'], mp_context=mp.get_context('spawn')) as pool:
        for i, g in enumerate(pool.map(make_group, tasks), 1):
            print(f'ROLE-P1 group={g} completed={i}/{len(tasks)}', flush=True)
    def produce(staging):
        summaries, specs = [], []
        markers = {}
        for g in sorted(fit + dev):
            directory = out / 'groups' / f'group_{g:06d}'
            verify_unit(directory, {**base, 'group_index': g, 'split': 'train'})
            markers[str(g)] = file_sha256(directory / 'complete.json')
            summaries.append(read_json(directory / 'summary.json'))
            specs.append({'group_index': g, 'paired_group_id': f'rollout-pair:train:{g:06d}',
                          'path': str(directory / 'audits.json.gz'), 'sha256': file_sha256(directory / 'audits.json.gz')})
        hard = load_and_validate(ROOT / 'configs/m1_hard_condition_v7.json')
        health = data_health(summaries, hard)
        require(health['gates']['candidate_coverage'] and health['gates']['teacher_health'], 'pilot data health failed; no replacement groups')
        matrices = {}
        for mode in ENCODINGS:
            parts = []
            for g in sorted(fit + dev):
                with np.load(out / 'groups' / f'group_{g:06d}' / f'{mode}.npz', allow_pickle=False) as shard:
                    parts.append({k: shard[k] for k in shard.files})
            matrices[mode] = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
            training, heldout = split_arrays(matrices[mode], plan)
            require(len(training['y']) == 480 and len(heldout['y']) == 320, 'pilot size mismatch')
            np.savez(staging / f'{mode}.npz', **matrices[mode])
        for mode in ENCODINGS[1:]:
            for key in matrices['pooled_v1']:
                if key != 'x':
                    np.testing.assert_array_equal(matrices[mode][key], matrices['pooled_v1'][key])
        write_json(staging / 'manifest.json', {'plan': plan, 'group_markers': markers, 'audits': specs,
            'health': health, 'arrays_digests': {m: arrays_sha256(a) for m, a in matrices.items()},
            'fit_labelled_rows': int(split_arrays(matrices['pooled_v1'], plan)[0]['labelled'].sum()),
            'provenance': capture_run_provenance(ROOT, component='D057_prepare', entrypoint=Path(__file__)),
            'future_use_policy': 'future only in stored training targets and offline evaluation; online receives online payload only',
            'front_end': 'frozen M1 v7 procedural proposals and retrieval queries; no visual backbone'})
    complete_unit(out / 'prepared', base, produce)
    print('ROLE-P1_PREPARED fit=12 dev=8 exit=0', flush=True)


def prepared(plan, binding, out):
    base = dependency(out, binding)
    verify_unit(out / 'prepared', base)
    manifest = read_json(out / 'prepared/manifest.json')
    require(manifest['plan'] == plan, 'prepared plan differs')
    specs = [s for s in manifest['audits'] if s['group_index'] in plan['dev_group_indices']]
    require(len(specs) == 8, 'held-out audit set incomplete')
    for g in plan['fit_group_indices'] + plan['dev_group_indices']:
        directory = out / 'groups' / f'group_{g:06d}'
        # File manifests bind the full saved raw reference executions and arrays.
        verify_unit(directory, {**base, 'group_index': g, 'split': 'train'})
        require(file_sha256(directory / 'complete.json') == manifest['group_markers'][str(g)], 'group marker changed')
    return {**base, 'prepared_marker_sha256': file_sha256(out / 'prepared/complete.json')}, manifest, specs


def config_for(plan, mode):
    smoke = read_json(ROOT / 'configs/m1_af_smoke.json')
    for key in ['seeds', 'student_steps', 'scorer_steps', 'learning_rate', 'batch_size', 'auxiliary_weight',
                'distillation_weight', 'architecture', 'device', 'cpu_threads', 'commit_probability', 'margin_threshold']:
        smoke[key] = plan[key]
    # Legacy API calls its second array "validation"; it is our train inner-dev.
    smoke['paired_groups'] = {'train': 12, 'validation': 8}
    smoke['evaluation_population'] = 'train_inner_dev_only'
    smoke['candidate_availability_policy'] = read_json(ROOT / 'configs/m1_candidate_availability_policy.json')
    return configure(resolve_af_smoke_config(load_and_validate(ROOT / 'configs/m1_hard_condition_v7.json'), smoke), encoding=mode)


def run_seed(plan, binding, out, seed):
    require(seed in plan['seeds'], 'unregistered seed')
    base, manifest, specs = prepared(plan, binding, out)
    if seed == 19:
        for previous_mode in ENCODINGS:
            for previous_method in METHODS:
                verify_unit(out / 'runs' / f'{previous_mode}__{previous_method}__seed_7',
                            {**base, 'encoding': previous_mode, 'method': previous_method, 'seed': 7,
                             'config': config_for(plan, previous_mode)})
    for mode in ENCODINGS:
        with np.load(out / 'prepared' / f'{mode}.npz', allow_pickle=False) as source:
            arrays = {k: source[k] for k in source.files}
        require(arrays_sha256(arrays) == manifest['arrays_digests'][mode], 'prepared arrays changed')
        train, dev = split_arrays(arrays, plan)
        config = config_for(plan, mode)
        for method in METHODS:
            name = f'{mode}__{method}__seed_{seed}'
            unit_binding = {**base, 'encoding': mode, 'method': method, 'seed': seed, 'config': config}
            print(f'ROLE-P2 start {name}', flush=True)
            def produce(staging):
                began = time.monotonic()
                count = 0
                with gzip.open(staging / 'execution.jsonl.gz', 'wt', encoding='utf-8', compresslevel=1) as stream:
                    def sink(materialized, choice, current):
                        nonlocal count
                        validate_graph(current)
                        choice['selected_program_label'] = _program_label(materialized['online']['candidate_programs'][choice['selected_index']])
                        stream.write(json.dumps({'materialized': materialized, 'choice': choice, 'current': current}, allow_nan=False) + '\n')
                        count += 1
                        if count % 40 == 0:
                            print(f'ROLE-P2 {name} decisions={count}/320', flush=True)
                    def evaluator(model, audits, cfg):
                        # Persist the trained student before expensive rollout; verify reload.
                        checkpoint = {'binding': unit_binding, 'config': cfg, 'state_dict': model.state_dict()}
                        torch.save(checkpoint, staging / 'student.pt')
                        saved = torch.load(staging / 'student.pt', map_location='cpu', weights_only=True)
                        require(saved['binding'] == unit_binding and saved['config'] == cfg, 'checkpoint encoding/binding drift')
                        reloaded = deepcopy(model)
                        reloaded.load_state_dict(saved['state_dict'], strict=True)
                        reloaded.eval()
                        with torch.no_grad():
                            x = torch.as_tensor(dev['x'])
                            torch.testing.assert_close(reloaded(x), model(x), rtol=0, atol=0)
                        return rollout_metrics(reloaded, audits, cfg, audit_sink=sink)
                    metrics, details, models = run_af_method(train, dev, ReplayableAudits(specs), config, seed,
                                                          method, causal_evaluator=evaluator)
                require(count == 320, 'incomplete self-rollout recorder')
                validate_rows(details['causal_sequences'], [s['paired_group_id'] for s in specs])
                details['onset_diagnostics'] = error_diagnostics(details['causal_sequences'])
                model = models[method]
                dev_t = tensors(dev, torch.device('cpu'))
                with torch.no_grad():
                    logits = model(dev_t['x'])
                    probs = masked_candidate_probabilities(logits, candidate_admissibility_mask(dev_t, logits)).numpy()
                details['reference_history_selection'] = selection_error_decomposition(probs, dev)
                for model_name, module in models.items():
                    if model_name != method:
                        torch.save({'binding': unit_binding, 'config': config, 'state_dict': module.state_dict()}, staging / 'scorer.pt')
                write_json(staging / 'result.json', {'metrics': metrics, 'details': details,
                    'wall_seconds': time.monotonic() - began, 'runner_exit_code': 0,
                    'provenance': capture_run_provenance(ROOT, component='D057_fit_rollout', entrypoint=Path(__file__))})
            complete_unit(out / 'runs' / name, unit_binding, produce)
            print(f'ROLE-P2 complete {name} exit=0', flush=True)
    print(f'ROLE-P2_SEED_OK seed={seed} models=9 exit=0', flush=True)


def build_report(plan, binding, out):
    base, manifest, _ = prepared(plan, binding, out)
    runs, artifacts, comparisons, method_comparisons = {}, {}, [], []
    for seed in plan['seeds']:
        for mode in ENCODINGS:
            for method in METHODS:
                name = f'{mode}__{method}__seed_{seed}'
                path = out / 'runs' / name
                expected = {**base, 'encoding': mode, 'method': method, 'seed': seed, 'config': config_for(plan, mode)}
                marker = verify_unit(path, expected)
                value = read_json(path / 'result.json')
                require(value['runner_exit_code'] == 0, 'unsuccessful run')
                validate_rows(value['details']['causal_sequences'], [f'rollout-pair:train:{g:06d}' for g in plan['dev_group_indices']])
                require(value['details']['onset_diagnostics'] == error_diagnostics(value['details']['causal_sequences']), 'diagnostic mismatch')
                runs[name] = value
                artifacts[name] = {'directory': str(path), 'marker': marker}
        for method in METHODS:
            left = runs[f'argument_roles_v1__{method}__seed_{seed}']
            right = runs[f'pooled_padded_v1__{method}__seed_{seed}']
            require(left['metrics']['student_parameters'] == right['metrics']['student_parameters'], 'matched capacity failed')
            comparisons.append({'seed': seed, 'method': method, 'contrast': 'roles_minus_padded',
                **paired_differences(left['details']['causal_sequences'], right['details']['causal_sequences'], plan['dev_group_indices'])})
        for mode in ENCODINGS:
            for control in METHODS[1:]:
                left = runs[f'{mode}__cpmt_ctl_core__seed_{seed}']
                right = runs[f'{mode}__{control}__seed_{seed}']
                method_comparisons.append({'seed': seed, 'encoding': mode, 'contrast': f'A_minus_{control}',
                    **paired_differences(left['details']['causal_sequences'], right['details']['causal_sequences'], plan['dev_group_indices'])})
    return {'schema_version': 'cpmt-m1-role-pilot-result-v1', 'plan': plan, 'binding': base,
            'data_manifest': manifest, 'runs': runs, 'artifacts': artifacts, 'paired_descriptive_comparisons': comparisons,
            'method_descriptive_comparisons': method_comparisons,
            'complete': True, 'models': 18, 'additional_scorers': 6, 'test_access': False, 'validation_access': False,
            'formal_acceptance': False, 'checkpoint_selection_performed': False,
            'interpretation': 'Fixed short-budget pilot only. No p-value, winner selection, automatic expansion, or S5 no-go reversal. '
                              'Both seeds and every group retained. Conditional onset denominators differ across policies. '
                              'Padded/roles initialization and batch RNG match; 33-dim anchor has different initialization RNG consumption.'}


def export(plan, binding, out, verify=False):
    report = build_report(plan, binding, out)
    path = ROOT / plan['export']
    if verify or path.exists():
        require(read_json(path) == report, 'export differs from verified artifacts')
    else:
        write_json(path, report)
    print(f'ROLE-P3_{"VERIFIED" if verify else "EXPORTED"} models=18 exit=0 report={path} sha256={file_sha256(path)}', flush=True)
    for row in report['paired_descriptive_comparisons']:
        print(json.dumps({'seed': row['seed'], 'method': row['method'], 'roles_minus_padded': row['mean']}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('step', choices=['test', 'prepare', 'run', 'export', 'verify'])
    parser.add_argument('--seed', type=int)
    args = parser.parse_args()
    plan, binding, out = setup()
    if args.step == 'test': test_stage(out, binding)
    elif args.step == 'prepare': prepare(plan, binding, out)
    elif args.step == 'run': run_seed(plan, binding, out, args.seed)
    else: export(plan, binding, out, verify=args.step == 'verify')


if __name__ == '__main__':
    main()
