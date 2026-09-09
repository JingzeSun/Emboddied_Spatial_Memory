"""D-051/D-054 fixed train anchor, durable models, causal evaluation and sealed N.

The old v6 runner/registration remain historical. No search, endpoint switch,
validation/test reads or release occur here. Use ops/m1_corrected_probe.sh.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import multiprocessing as mp
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import numpy as np
import torch
from cpmt.dev_learning import (OnlineModel, OutcomeScorer, tensors, train_outcome_scorer, train_student,
    masked_candidate_probabilities, outcome_scorer_diagnostics)
from cpmt.m1_af_rollout import causal_rollout_metrics, training_inner_dev_mask, selection_error_decomposition
from cpmt.m1_candidate_policy import validate_candidate_policy
from cpmt.executor import validate_graph
from cpmt.m1_metrics import endpoint_viability_assessment
from cpmt.m1_protocol import load_and_validate, protocol_sha256
from cpmt.m1_rollout import teacher_horizon_contrast
from cpmt.m1_s5_confirmation import complete_unit, verify_unit
from cpmt.m1_s5_training import read_json, require, write_json
from cpmt.m1_train_reuse import source_changes
from cpmt.run_provenance import capture_run_provenance, file_sha256, source_tree_sha256
from run_m1_endpoint_probe import METHODS, _load_train, _subset, _train_cfg, _method_teacher, _reconstruct_audits
from run_m1_s5_train import model_kwargs

TRAIN_DIR = Path('/root/autodl-tmp/cpmt_outputs/m1-v7-d051-train-719bb2d494d9')
REUSE_REPORT = 'results/m1_v7_d054_candidate_policy_and_train_reuse.json'
REUSE_SHA = '2d7ff07ccb1cf9ff29084d39ccd0faa653c678ae40dfaf6f3388aabb1c1a965c'
SEEDS = [7, 19, 31, 43, 59]
METRICS = ['final_active_graph_correctness', 'final_graded_open_memory_correctness',
           'open_fact_error_auc_per_100_decisions']
F_REQUIRED = {METRICS[0]: 1.0, METRICS[1]: 1.0, METRICS[2]: 0.0,
              'final_graded_active_world_correctness': 1.0, 'active_node_state_error_per_100': 0.0}
PINNED = {
    'configs/m1_scope_rebuild_plan.json': '8fbfd9df8eafd035999fa3d7852aca5dfb82a2d898461fa7660022c870833a27',
    'configs/m1_endpoint_viability_probe.json': '6816ce3ab3b524bad493609511582de0eb7f6ac9c12399c0137e9083b48b2d67',
    'configs/m1_candidate_availability_policy.json': '2db6ab0c84163fad8f6a5572b3ef7de94acaf2d16740bb886545782814ac5b48',
    'configs/m1_train_reuse_policy.json': '7777175a687a1e01d10f98f74b49456910053168d51bd4b77855c6fd96769e36',
}


def contracts(root=ROOT):
    for name, digest in PINNED.items():
        require(protocol_sha256(read_json(root / name)) == digest, 'fixed contract changed: ' + name)
    hard = load_and_validate(root / 'configs/m1_hard_condition_v7.json')
    rebuild = read_json(root / 'configs/m1_scope_rebuild_plan.json')
    require(protocol_sha256(hard) == rebuild['corrected_source']['protocol_sha256'], 'wrong corrected protocol')
    require(file_sha256(root / REUSE_REPORT) == REUSE_SHA, 'accepted reuse report changed')
    reuse = read_json(root / REUSE_REPORT)
    policy = read_json(root / 'configs/m1_train_reuse_policy.json')
    require(reuse['report']['accepted'] and reuse['report']['verified_files'] == 1002
            and reuse['report']['verified_train_groups'] == 1000, 'train reuse not accepted')
    require(source_changes(root, policy['generation_commit']) == policy['reviewed_source_changes'],
            'unreviewed generation/encoding change')
    cfg = _train_cfg(hard, read_json(root / 'configs/m1_af_smoke.json'))
    # This phase fixes CPU/one thread before observing outcomes. It does not
    # select a device by measured accuracy or change the scientific anchor.
    cfg.update(protocol='m1-corrected-fixed-anchor-v1', stage='M1-v7-train-only-fixed-anchor',
        paired_groups={'train': 1000, 'fitting': 799, 'inner_dev': 201}, seeds=SEEDS,
        device='cpu', cpu_threads=1, candidate_availability_policy=validate_candidate_policy(
        read_json(root / 'configs/m1_candidate_availability_policy.json')))
    binding = {'schema_version': 'cpmt-corrected-fixed-probe-binding-v1',
        'source_and_tests_sha256': source_tree_sha256(root, roots=('src', 'scripts', 'configs', 'tests')),
        'contracts': PINNED, 'hard_sha256': protocol_sha256(hard), 'reuse_report_sha256': REUSE_SHA,
        'arrays_digest': policy['arrays_digest'], 'config': cfg, 'seeds': SEEDS,
        'runtime': {'torch': str(torch.__version__), 'numpy': str(np.__version__),
                    'device': 'cpu', 'torch_threads': 1},
        'validation_access': False, 'test_access': False}
    return hard, rebuild, binding


def fixed_groups():
    ids = np.arange(1000)
    return ids[training_inner_dev_mask({'group': ids})].tolist()


def check_rows(rows, groups):
    expected = {(f'rollout-pair:train:{g:06d}', s) for g in groups for s in (0, 1)}
    keys = [(r['metrics']['paired_group_id'], int(r['metrics']['sibling_index'])) for r in rows]
    require(len(keys) == len(expected) and set(keys) == expected, 'missing/duplicate paired trajectories')
    for row in rows:
        choices = row['choices']
        require([c['step_index'] for c in choices] == list(range(20)), 'incomplete 20-step trajectory')
        require(all(a['post_graph_hash'] == b['base_graph_hash'] for a, b in zip(choices, choices[1:])),
                'broken persistent-memory chain')
        require(all(c['selected_static_preflight_pass'] for c in choices), 'selected unavailable/rejected candidate')
        require(all(math.isfinite(float(row['metrics'][k])) for k in [*METRICS, *F_REQUIRED]), 'nonfinite metric')


def assess(rows, expected_groups=201):
    # Enforce full seed x sibling support BEFORE the historical group reducer.
    expected = {(m, s, sibling) for m in METHODS for s in SEEDS for sibling in (0, 1)}
    expected |= {('F', None, s) for s in (0, 1)}
    by_group = {}
    for r in rows:
        require(all(math.isfinite(float(r['metrics'][k])) for k in
                    set([*METRICS, *F_REQUIRED, 'final_active_reference_record_count'])), 'nonfinite endpoint row')
        key = (r['method'], r['seed'], int(r['metrics']['sibling_index']))
        by_group.setdefault(r['paired_group_id'], []).append(key)
    require(len(by_group) == expected_groups and all(len(v) == len(expected) and set(v) == expected
            for v in by_group.values()), 'incomplete/duplicate seed-sibling assessment matrix')
    result = endpoint_viability_assessment(rows, expected_groups=expected_groups, minimum_test_groups=1350)
    exact_ok = all(result['by_metric'][m][c]['nondegenerate'] for m in METRICS for c in ('A_vs_C', 'A_vs_E'))
    oracle_ok = all(all(r['metrics'][k] == value for k, value in F_REQUIRED.items())
                    for r in rows if r['method'] == 'F')
    result.update(endpoint_reselection=False, selected_metric=None, selected_test_groups=None,
                  oracle_integrity_pass=oracle_ok, winner_or_effect_sign_used_for_switch=False)
    if not oracle_ok:
        result['disposition'] = 'abort_oracle_integrity_failure'
    elif not exact_ok:
        result['disposition'] = 'stop_fixed_coprimary_not_viable_without_switch'
    else:
        result.update(disposition='retain_exact_endpoint', selected_metric=METRICS[0],
            selected_test_groups=max(result['by_metric'][m][c]['required_test_groups_for_planning_effect']
                for m in METRICS for c in ('A_vs_C', 'A_vs_E')))
    return result


def registration(report, rebuild):
    assessment = assess(report['endpoint_rows'], expected_groups=201)
    require(assessment == report['endpoint_assessment'], 'assessment differs from complete rows')
    if assessment['disposition'] != 'retain_exact_endpoint':
        return None
    count = assessment['selected_test_groups']
    require(count >= 1350 and count % 10 == 0, 'invalid corrected N')
    return {'schema_version': 'cpmt-m1-corrected-post-probe-registration-v1',
        'status': 'registered_pretest_not_test_release', 'decisions': ['D-051', 'D-054'],
        'endpoint_probe_sha256': protocol_sha256(report), 'binding': report['binding'],
        'candidate_availability_policy': report['binding']['config']['candidate_availability_policy'],
        'execution_boundary': {'candidate_slots': 16, 'constructed_candidates_execute_from_same_base': True,
            'unavailable_slots_execute': False, 'only_selected_legal_world_persists': True,
            'online_reads_future_or_candidate_post_world': False,
            'single_execution_deployment_implemented': False,
            'p95_forward_latency_scope': 'network_and_associated_tensor_probability_operations'},
        'evaluation_plan': {'paired_groups': {'train': 1000, 'validation': 200, 'test': count},
            'semantic_metric': METRICS[0], 'support_metric': METRICS[1], 'burden_metric': METRICS[2],
            'minimum_effects': rebuild['endpoints']['minimum_effects'],
            'planning_effects': rebuild['endpoints']['planning_effects'],
            'primary_contrasts': ['A_vs_C', 'A_vs_E'], 'commit_probability': 0.0, 'margin_threshold': 0.0,
            'validation_selects_settings': False, 'safety': {k: v for k, v in rebuild['endpoints'].items()
                if k.endswith('margin_per_100') or k == 'invariant_violation_gate'}},
        'test_size_rule': rebuild['test_size'], 'formal_test_release': False, 'test_access': False,
        'formal_budget_authorized': False}


def prepare_group(task):
    torch.set_num_threads(1)
    output, train_dir, group, binding = task
    output, train_dir = Path(output), Path(train_dir)
    unit_binding = {**binding, 'group': group}
    def produce(staging):
        hard = load_and_validate(ROOT / 'configs/m1_hard_condition_v7.json')
        shard_path = train_dir / f'shards/train_{group:06d}.npz'
        marker = read_json(train_dir / 'generation.ok.json')
        require(file_sha256(shard_path) == marker['file_sha256'][f'shards/train_{group:06d}.npz'], 'shard changed')
        with np.load(shard_path, allow_pickle=False) as z:
            shard = {k: z[k] for k in z.files}
        shard['group'] = np.full(len(shard['y']), group, dtype=np.int64)
        # Reuse the original exact-array comparison, with one group per child.
        audits = reconstruct_pair(ROOT / 'configs/m1_hard_condition_v7.json', hard, shard, group, staging)
        require(len(audits) == 2 and all(len(a['steps']) == 20 for a in audits), 'invalid reconstructed pair')
        write_json(staging / 'summary.json', {'group': group, 'learning_rows': len(shard['y']),
                                             'arrays_equal': True})
    complete_unit(output / f'group_{group:06d}', unit_binding, produce)
    return group


class Audits:
    """Repeatable disk stream: each group keeps both siblings, never all worlds in RAM."""
    def __init__(self, output, groups):
        self.output, self.groups = Path(output), groups

    def __iter__(self):
        for g in self.groups:
            p = self.output / f'group_{g:06d}' / f'train_inner_dev_{g:06d}.json.gz'
            with gzip.open(p, 'rt', encoding='utf-8') as f:
                payload = json.load(f)
            require(payload['group'] == g and len(payload['audits']) == 2, 'audit identity mismatch')
            yield from payload['audits']


def reconstruct_pair(config_path, hard, shard, group, staging):
    """Avoid a nested multiprocessing pool inside a reconstruction worker."""
    from run_m1_endpoint_probe import _write_audit, _audit_path
    _write_audit((str(config_path), group, str(_audit_path(staging, group))))
    return _reconstruct_audits(config_path, hard, shard, [group], staging, 1)


def evaluate_unit(path, binding, model, audits, groups, *, oracle=False):
    def produce(staging):
        began = time.monotonic()
        with gzip.open(staging / 'execution.jsonl.gz', 'wt', encoding='utf-8') as stream:
            def sink(materialized, choice, current):
                validate_graph(current)
                # Keep actual online candidates, every execution failure and the
                # evolving selected world; reference future stays offline.
                stream.write(json.dumps({'materialized': materialized, 'choice': choice,
                                         'current': current}, allow_nan=False) + '\n')
            aggregate, rows = causal_rollout_metrics(model, audits, binding['config'],
                                                     oracle=oracle, audit_sink=sink)
        check_rows(rows, groups)
        aggregate.update(wall_seconds=time.monotonic()-began, device='cpu', torch_threads=1,
                         peak_vram_bytes=0, latency_conditions='serial_cpu_no_phase_training')
        write_json(staging / 'result.json', {'aggregate': aggregate, 'sequences': rows})
    complete_unit(path, binding, produce)
    result = read_json(path / 'result.json')
    check_rows(result['sequences'], groups)
    return result


def prepare(output, hard, binding, workers):
    policy = read_json(ROOT / 'configs/m1_train_reuse_policy.json')
    marker = read_json(TRAIN_DIR / 'generation.ok.json')
    require(file_sha256(TRAIN_DIR / 'generation.ok.json') == policy['generation_marker_sha256'], 'generation marker changed')
    for name in ('train.npz', 'train.manifest.json'):
        require(file_sha256(TRAIN_DIR / name) == marker['file_sha256'][name], 'train input changed: ' + name)
    groups = fixed_groups()
    require(len(groups) == 201, 'inner-dev partition changed')
    tasks = [(str(output / 'audits'), str(TRAIN_DIR), g, binding) for g in groups]
    with mp.get_context('spawn').Pool(workers) as pool:
        for done, group in enumerate(pool.imap_unordered(prepare_group, tasks), 1):
            print(f'PROBE_AUDIT_OK group={group} completed={done}/201', flush=True)
    def finish(staging):
        write_json(staging / 'horizon.json', teacher_horizon_contrast(hard, Audits(output / 'audits', groups), contrast_horizon=1))
    complete_unit(output / 'horizon', binding, finish)
    f = evaluate_unit(output / 'oracle', {**binding, 'method': 'F', 'seed': None}, None,
                      Audits(output / 'audits', groups), groups, oracle=True)
    require(all(all(r['metrics'][k] == v for k, v in F_REQUIRED.items()) for r in f['sequences']),
            'F oracle integrity failed; no training, switch or budget grid')
    complete_unit(output / 'prepared', binding, lambda p: write_json(p / 'groups.json', groups))
    print('CORRECTED_PROBE_PREPARE_OK groups=201 reference_arrays_equal=true oracle_integrity=true', flush=True)


def load_checkpoint(path, binding):
    verify_unit(path, binding)
    payload = torch.load(path / 'model.pt', map_location='cpu', weights_only=True)
    require(payload['binding'] == binding, 'checkpoint binding mismatch')
    cls = OutcomeScorer if binding['method'] == 'scorer' else OnlineModel
    with torch.random.fork_rng(devices=[]):
        model = cls(**payload['model_kwargs'])
    model.load_state_dict(payload['state_dict'], strict=True)
    model.eval()
    return model, payload


def forced_diagnostic(model, arrays):
    probabilities = []
    with torch.no_grad():
        for start in range(0, len(arrays['y']), 64):
            logits = model(torch.as_tensor(arrays['x'][start:start+64]))
            mask = torch.as_tensor(arrays['candidate_static_preflight_pass'][start:start+64], dtype=torch.bool)
            probabilities.append(masked_candidate_probabilities(logits, mask).numpy())
    result = selection_error_decomposition(np.concatenate(probabilities), arrays)
    return {**result, 'reference_history_only': True, 'checkpoint_selection': False}


def train(output, hard, binding):
    verify_unit(output / 'prepared', binding)
    oracle = read_json(output / 'oracle/result.json')
    verify_unit(output / 'oracle', {**binding, 'method': 'F', 'seed': None})
    require(all(all(r['metrics'][k] == v for k, v in F_REQUIRED.items()) for r in oracle['sequences']),
            'F oracle integrity failed; training blocked')
    arrays, record = _load_train(TRAIN_DIR / 'train.npz', hard)
    require(record['arrays_digest'] == binding['arrays_digest'], 'train digest drift')
    mask = training_inner_dev_mask(arrays)
    require(set(arrays['group'][mask].tolist()) == set(fixed_groups()), 'training partition mismatch')
    fit_np, inner_np = _subset(arrays, ~mask), _subset(arrays, mask)
    require(len(set(fit_np['group'].tolist())) == 799, 'fitting group count mismatch')
    fit, inner = tensors(fit_np, torch.device('cpu')), tensors(inner_np, torch.device('cpu'))
    del arrays
    cfg = binding['config']
    for seed in SEEDS:
        learned = None
        for short in ['scorer', *METHODS]:
            unit_binding = {**binding, 'method': short, 'seed': seed}
            path = output / 'models' / f'{short}_{seed}'
            def produce(staging):
                started = time.monotonic()
                if short == 'scorer':
                    model, teacher, trace = train_outcome_scorer(fit, inner, cfg, seed, torch.device('cpu'))
                else:
                    teacher = _method_teacher(METHODS[short], fit,
                        {'train': learned if short == 'E' else fit['pstar']})
                    model, trace = train_student(METHODS[short], fit, teacher, cfg, seed, torch.device('cpu'))
                state = model.state_dict()
                require(all(bool(torch.isfinite(v).all()) for v in state.values()), 'nonfinite checkpoint')
                payload = {'binding': unit_binding, 'model_kwargs': model_kwargs(fit, cfg, short == 'scorer'),
                           'state_dict': state}
                if short == 'scorer':
                    payload['train_teacher'] = teacher['train'].detach().cpu()
                    require(bool(torch.isfinite(payload['train_teacher']).all()), 'nonfinite scorer teacher')
                    write_json(staging / 'scorer_diagnostics.json', outcome_scorer_diagnostics(
                        model, inner, teacher['validation'], row_mask=~inner['recovery'],
                        energy_weights=cfg['energy_weights'], temperature=cfg['temperature']))
                else:
                    fitting_diagnostic = forced_diagnostic(model, fit_np)
                    inner_diagnostic = forced_diagnostic(model, inner_np)
                    write_json(staging / 'fit_inner_dev.json', {'fitting': fitting_diagnostic,
                        'inner_dev': inner_diagnostic, 'accuracy_gap': fitting_diagnostic['accuracy']-inner_diagnostic['accuracy'],
                        'role': 'fixed_anchor_diagnostic_only_not_selection'})
                torch.save(payload, staging / 'model.pt')
                write_json(staging / 'training.json', {'trace': trace, 'wall_seconds': time.monotonic()-started,
                    'parameter_count': sum(p.numel() for p in model.parameters()),
                    'fitting_groups': 799, 'inner_dev_groups': 201, 'checkpoint_selection': False})
            print(f'PROBE_MODEL_BEGIN method={short} seed={seed}', flush=True)
            complete_unit(path, unit_binding, produce)
            model, payload = load_checkpoint(path, unit_binding)
            if short == 'scorer':
                learned = payload['train_teacher']
                require(tuple(learned.shape) == tuple(fit['penalties'].shape), 'scorer teacher shape mismatch')
            del model, payload
            print(f'PROBE_MODEL_SAVED method={short} seed={seed}', flush=True)
    complete_unit(output / 'trained', binding, lambda p: write_json(p / 'summary.json', {'models': 20}))
    print('CORRECTED_PROBE_TRAIN_OK models=20 student_models=15 scorer_models=5', flush=True)


def evaluate(output, binding):
    verify_unit(output / 'prepared', binding)
    verify_unit(output / 'trained', binding)
    groups = fixed_groups()
    for short in METHODS:
        for seed in SEEDS:
            unit_binding = {**binding, 'method': short, 'seed': seed}
            model, _ = load_checkpoint(output / 'models' / f'{short}_{seed}', unit_binding)
            result = evaluate_unit(output / 'causal' / f'{short}_{seed}', unit_binding, model,
                                   Audits(output / 'audits', groups), groups)
            print(f"PROBE_CAUSAL_OK method={short} seed={seed} exact={result['aggregate'][METRICS[0]]:.6f}", flush=True)
    complete_unit(output / 'evaluated', binding, lambda p: write_json(p / 'summary.json', {'runs': 15}))
    print('CORRECTED_PROBE_EVALUATE_OK runs=15 groups_per_run=201 decisions_per_run=8040', flush=True)


def summarize(output, rebuild, binding):
    verify_unit(output / 'evaluated', binding)
    def produce(staging):
        rows, results, files, training = [], {}, {}, {}
        for seed in SEEDS:
            for short in ['scorer', *METHODS]:
                path = output / 'models' / f'{short}_{seed}'
                marker = verify_unit(path, {**binding, 'method': short, 'seed': seed})
                training[f'{short}_{seed}'] = {'files': marker['files'], 'training': read_json(path / 'training.json'),
                    'diagnostics': read_json(path / ('scorer_diagnostics.json' if short == 'scorer' else 'fit_inner_dev.json'))}
        for short, seeds in [*[(m, SEEDS) for m in METHODS], ('F', [None])]:
            for seed in seeds:
                path = output / 'oracle' if short == 'F' else output / 'causal' / f'{short}_{seed}'
                marker = verify_unit(path, {**binding, 'method': short, 'seed': seed})
                result = read_json(path / 'result.json')
                check_rows(result['sequences'], fixed_groups())
                key = f'{short}_{seed}'
                results[key] = result['aggregate']
                files[key] = marker
                rows.extend({'paired_group_id': r['metrics']['paired_group_id'], 'method': short,
                    'seed': seed, 'metrics': {k: r['metrics'][k] for k in
                        set([*METRICS, *F_REQUIRED, 'sibling_index', 'final_active_reference_record_count'])}}
                    for r in result['sequences'])
        verify_unit(output / 'horizon', binding)
        report = {'schema_version': 'cpmt-m1-corrected-fixed-probe-report-v1', 'status': 'complete',
            'binding': binding, 'provenance': capture_run_provenance(ROOT, component='corrected_fixed_probe'),
            'endpoint_rows': rows, 'endpoint_assessment': assess(rows), 'aggregate_by_run': results, 'training': training,
            'causal_files': files, 'teacher_horizon_contrast': read_json(output / 'horizon/horizon.json'),
            'formal_method_effect_claim': False, 'validation_access': False, 'test_access': False,
            'formal_budget_authorized': False}
        write_json(staging / 'report.json', report)
        write_json(staging / 'registration.json', registration(report, rebuild))
    complete_unit(output / 'summary', binding, produce)
    report = read_json(output / 'summary/report.json')
    print('CORRECTED_PROBE_SUMMARY disposition=' + report['endpoint_assessment']['disposition']
          + ' N=' + str(report['endpoint_assessment']['selected_test_groups']), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'train', 'evaluate', 'summarize'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    require(1 <= args.workers <= 4, 'reconstruction workers must be 1..4')
    torch.set_num_threads(1)
    hard, rebuild, binding = contracts()
    require(not capture_run_provenance(ROOT, component='corrected_fixed_probe')['git_dirty'], 'clean checkout required')
    args.output.mkdir(parents=True, exist_ok=True)
    # Every consumer rechecks the saved audit files once before streaming them.
    if args.action != 'prepare':
        for group in fixed_groups():
            verify_unit(args.output / 'audits' / f'group_{group:06d}', {**binding, 'group': group})
    if args.action == 'prepare': prepare(args.output, hard, binding, args.workers)
    elif args.action == 'train': train(args.output, hard, binding)
    elif args.action == 'evaluate': evaluate(args.output, binding)
    else: summarize(args.output, rebuild, binding)


if __name__ == '__main__':
    main()
