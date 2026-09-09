"""Shared model-path worker and process dispatcher for budget and S5 recipes.

The executable interface currently accepts only the fixed train-only engineering
check. Formal grid/refit release still requires the corrected probe and plans.
No generator, learning algorithm, optimizer, or scientific gate is changed.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
import numpy as np
import torch
from cpmt.dev_learning import (OnlineModel, OutcomeScorer, tensors, train_student,
    train_outcome_scorer, masked_candidate_probabilities,
    apply_candidate_admissibility_to_probabilities, candidate_admissibility_mask)
from cpmt.m1_af_rollout import training_inner_dev_mask
from cpmt.m1_s5_confirmation import complete_unit, verify_unit
from cpmt.m1_s5_training import read_json, require, write_json
from cpmt.run_provenance import arrays_sha256, capture_run_provenance, file_sha256, source_tree_sha256
from run_m1_s5_train import model_kwargs
from run_m1_train_inner_dev_budget import _accuracy_by_group, _subset_rows, _architecture_settings

ARCHITECTURES = ['cross_candidate_set_transformer_v1', 'shared_candidate_mlp_v1']
METHODS = ['cpmt_ctl_core', 'direct_classifier', 'direct_future_loss', 'execute_current_only', 'future_no_execution']
CHECK_SEEDS = [7, 19]
CHECK_GROUPS = list(range(10))
CHECKPOINTS = [10, 30]


def check_config(architecture):
    from run_m1_corrected_probe import contracts
    require(architecture in ARCHITECTURES, 'unknown check architecture')
    hard, _, science = contracts()
    return {**science['config'], **_architecture_settings(hard, architecture),
        'protocol': 'm1-fixed-training-process-engineering-check', 'device': 'cuda',
        'paired_groups': {'train_subset': 10}, 'seeds': CHECK_SEEDS,
        'student_steps': 30, 'scorer_steps': 30}


def validate_job(job):
    require(job['schema_version'] == 'cpmt-training-path-job-v1', 'wrong training job schema')
    require(job['authorization'] == 'fixed_train_only_engineering_check', 'formal training not released by this entry')
    require(job['mode'] in ['budget', 'refit'], 'unknown training population')
    require(job['architecture'] in ARCHITECTURES and job['seed'] in CHECK_SEEDS, 'unregistered check arm/seed')
    require(job['method'] in ['outcome_scorer', *METHODS], 'unknown method')
    require(job['groups'] == CHECK_GROUPS and job['checkpoints'] == CHECKPOINTS, 'fixed diagnostic sample/budget drift')
    require(job['learning_rate'] == 0.0006 and job['auxiliary_weight'] == 1.0, 'fixed check parameters drift')
    require(job['device'] == 'cuda' and job['torch_threads'] == 1, 'GPU/one-thread check required')
    require(job['validation_access'] is False and job['test_access'] is False
            and job['formal_budget_authorized'] is False, 'training job crossed boundary')
    require(bool(job.get('scorer_dependency')) == (job['method'] == 'future_no_execution'), 'scorer dependency mismatch')


def populations(arrays, mode):
    require(mode in ['budget', 'refit'], 'unknown population mode')
    if mode == 'refit':
        # A diagnostic alias is deliberately not called independent inner-dev.
        return arrays, arrays, False
    mask = training_inner_dev_mask(arrays)
    fit, inner = _subset_rows(arrays, ~mask), _subset_rows(arrays, mask)
    require(not set(fit['group']) & set(inner['group']), 'paired group crosses population')
    return fit, inner, True


def ranking_metrics(probabilities, teacher, arrays):
    """Identical fit/inner-dev metric; complete groups, ordinary rows only."""
    p, t = np.asarray(probabilities), np.asarray(teacher)
    require(p.shape == t.shape == arrays['candidate_static_preflight_pass'].shape, 'probability shape mismatch')
    require(np.isfinite(p).all() and np.isfinite(t).all(), 'nonfinite probabilities')
    mask = np.asarray(arrays['candidate_static_preflight_pass'], dtype=bool)
    require(np.all(p[~mask] == 0) and np.all(t[~mask] == 0), 'probabilities selected masked candidates')
    require(np.allclose(p.sum(1), 1, atol=1e-6) and np.allclose(t.sum(1), 1, atol=1e-6), 'probabilities not normalized')
    keep = ~np.asarray(arrays['recovery'], dtype=bool)
    require(keep.any(), 'no ordinary rows')
    predicted, target = p.argmax(1), np.asarray(arrays['y'])
    groups = np.asarray(arrays['group'])
    by_group = _accuracy_by_group(predicted, target, groups, keep)
    return {'rows': int(keep.sum()), 'paired_groups': len(by_group),
        'reference_accuracy': float(np.mean(predicted[keep] == target[keep])),
        'reference_accuracy_by_group': by_group,
        'group_mean_reference_accuracy': float(np.mean(list(by_group.values()))),
        'teacher_argmax_agreement': float(np.mean(predicted[keep] == t.argmax(1)[keep])),
        'teacher_reference_accuracy': float(np.mean(t.argmax(1)[keep] == target[keep])),
        'population_is_reference_history': True}


def student_probabilities(model, data):
    parts = []
    with torch.no_grad():
        for start in range(0, len(data['x']), 64):
            logits = model(data['x'][start:start+64])
            mask = data['candidate_static_preflight_pass'][start:start+64].bool()
            parts.append(masked_candidate_probabilities(logits, mask).detach().cpu())
    return torch.cat(parts)


def load_model(path, binding, checkpoint, device):
    """Common readback for later budget/refit consumers; checks every artifact."""
    verify_unit(path, binding)
    payload = torch.load(path / f'checkpoint_{checkpoint}.pt', map_location='cpu', weights_only=True)
    require(payload['binding'] == binding and payload['checkpoint'] == checkpoint, 'checkpoint identity changed')
    scorer = binding['job']['method'] == 'outcome_scorer'
    require(payload['model_class'] == ('OutcomeScorer' if scorer else 'OnlineModel'), 'model class changed')
    with torch.random.fork_rng(devices=[]):
        model = (OutcomeScorer if scorer else OnlineModel)(**payload['model_kwargs'])
    model.load_state_dict(payload['state_dict'], strict=True)
    model.to(device).eval()
    return model, payload


def validate_scorer_dependency(job, dependency_job):
    require(dependency_job['method'] == 'outcome_scorer', 'dependency is not a scorer')
    for key in ['mode', 'architecture', 'seed', 'groups', 'arrays_digest', 'input_file_sha256', 'source_and_tests_sha256']:
        require(job[key] == dependency_job[key], 'scorer dependency mismatch: ' + key)


def run_training_path(job, path, config):
    """One process, one uninterrupted optimizer path, all requested checkpoints."""
    validate_job(job)
    require(config == check_config(job['architecture']), 'unregistered check model/config')
    require(sys.platform == 'linux' and torch.cuda.is_available(), 'AutoDL CUDA required; no CPU fallback')
    torch.set_num_threads(1)
    device = torch.device('cuda')
    require(file_sha256(Path(job['input_path'])) == job['input_file_sha256'], 'input bytes changed')
    with np.load(job['input_path'], allow_pickle=False) as saved:
        arrays = {k: saved[k] for k in saved.files}
    require(arrays_sha256(arrays) == job['arrays_digest'] and sorted(set(arrays['group'].tolist())) == job['groups'],
            'input arrays/group identity mismatch')
    fit_np, inner_np, independent = populations(arrays, job['mode'])
    fit, inner = tensors(fit_np, device), tensors(inner_np, device)
    config = {**config, 'architecture': job['architecture'], 'device': 'cuda', 'cpu_threads': 1,
        'learning_rate': job['learning_rate'], 'auxiliary_weight': job['auxiliary_weight'],
        'student_steps': max(job['checkpoints']), 'scorer_steps': max(job['checkpoints'])}
    binding = {'job': job, 'config': config, 'runtime': {'torch': str(torch.__version__),
        'numpy': str(np.__version__), 'cuda': torch.version.cuda, 'gpu': torch.cuda.get_device_name(device)}}
    scorer = job['method'] == 'outcome_scorer'
    if job['method'] == 'future_no_execution':
        dep = job['scorer_dependency']; dep_path = Path(dep['path'])
        require(file_sha256(dep_path / 'complete.json') == dep['marker_sha256'], 'scorer completion changed')
        dependency_binding = read_json(dep_path / 'complete.json')['binding']
        validate_scorer_dependency(job, dependency_binding['job'])
        dependency_model, payload = load_model(dep_path, dependency_binding, dep['checkpoint'], device)
        require(payload['fit_groups'] == sorted(set(fit_np['group'].tolist()))
                and payload['evaluation_groups'] == sorted(set(inner_np['group'].tolist())), 'scorer row populations differ')
        teachers = {name: value.to(device) for name, value in payload['teachers'].items()}
        del dependency_model, payload
    else:
        key = 'pstar_current' if job['method'] == 'execute_current_only' else 'pstar'
        teachers = {'train': fit[key], 'validation': inner[key]}
    teachers = {name: apply_candidate_admissibility_to_probabilities(value,
        candidate_admissibility_mask(data, data['penalties'])) for name, value, data in
        [('train', teachers['train'], fit), ('validation', teachers['validation'], inner)]}
    def produce(staging):
        began = time.monotonic(); rows = []
        torch.cuda.reset_peak_memory_stats(device)
        def checkpoint(step, model, learned, trace):
            active_teachers = learned if scorer else teachers
            fit_p = active_teachers['train'].detach().cpu() if scorer else student_probabilities(model, fit)
            inner_p = active_teachers['validation'].detach().cpu() if scorer else student_probabilities(model, inner)
            fit_score = ranking_metrics(fit_p.numpy(), active_teachers['train'].detach().cpu().numpy(), fit_np)
            inner_score = ranking_metrics(inner_p.numpy(), active_teachers['validation'].detach().cpu().numpy(), inner_np)
            state = {k: v.detach().cpu() for k, v in model.state_dict().items()}
            require(all(bool(torch.isfinite(v).all()) for v in state.values()), 'nonfinite model weights')
            payload = {'schema_version': 'cpmt-training-path-checkpoint-v1', 'binding': binding,
                'checkpoint': step, 'model_class': 'OutcomeScorer' if scorer else 'OnlineModel',
                'model_kwargs': model_kwargs(fit, config, scorer), 'state_dict': state,
                'fit_groups': sorted(set(fit_np['group'].tolist())),
                'evaluation_groups': sorted(set(inner_np['group'].tolist())),
                'fit_probabilities': fit_p, 'evaluation_probabilities': inner_p,
                'teachers': {k: v.detach().cpu() for k, v in active_teachers.items()} if scorer else {}}
            torch.save(payload, staging / f'checkpoint_{step}.pt')
            rows.append({'checkpoint': step, 'fitting': fit_score,
                'inner_dev': inner_score if independent else None,
                'reference_accuracy_gap': fit_score['group_mean_reference_accuracy']-inner_score['group_mean_reference_accuracy'] if independent else None,
                'inner_dev_independent': independent, 'training_trace': trace})
            print(f"TRAINING_PATH_CHECKPOINT mode={job['mode']} method={job['method']} seed={job['seed']} step={step}", flush=True)
        if scorer:
            model, _, _ = train_outcome_scorer(fit, inner, config, job['seed'], device,
                checkpoint_steps=job['checkpoints'], checkpoint_callback=checkpoint)
        else:
            model, _ = train_student(job['method'], fit, teachers['train'], config, job['seed'], device,
                checkpoint_steps=job['checkpoints'], checkpoint_callback=lambda step, model, trace: checkpoint(step, model, None, trace))
        torch.cuda.synchronize(device)
        write_json(staging / 'result.json', {'binding': binding, 'checkpoints': rows,
            'wall_seconds': time.monotonic()-began, 'peak_vram_bytes': torch.cuda.max_memory_allocated(device),
            'parameter_count': sum(p.numel() for p in model.parameters()),
            'parameter_signature': [[n, list(p.shape), p.requires_grad] for n, p in model.named_parameters()],
            'provenance': capture_run_provenance(ROOT, component='shared_training_path'),
            'model_selection_performed': False, 'formal_run': False})
    complete_unit(path, binding, produce)
    # Reload through the common consumer without modifying future RNG streams.
    loaded, payload = load_model(path, binding, max(job['checkpoints']), device)
    with torch.no_grad():
        actual = loaded.predict_candidates(fit['x'][:1], fit['poses'][:1]) if scorer else loaded(fit['x'][:1])
    require(bool(torch.isfinite(actual).all()), 'loaded model produced nonfinite output')
    if not scorer:
        require(torch.equal(student_probabilities(loaded, fit), payload['fit_probabilities']), 'saved student readback changed predictions')
    return read_json(path / 'result.json')


def dispatch(jobs, workers, execute):
    """Scheduling threads only manage fresh child processes, never Torch state."""
    require(1 <= workers <= 4, 'worker count must be 1..4')
    keys = [job['id'] for job in jobs]
    require(len(keys) == len(set(keys)), 'duplicate job ids')
    results = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = {pool.submit(execute, job): job['id'] for job in jobs}
        for future in as_completed(pending):
            try:
                results[pending[future]] = future.result()
            except BaseException:
                for queued in pending: queued.cancel()
                # Already running jobs finish and retain their output; no retries.
                raise
    return {key: results[key] for key in sorted(keys)}


def execute_job(job, destination, config, gpu_uuid):
    destination = Path(destination); destination.mkdir(parents=True, exist_ok=True)
    request = {'job': job, 'config': config}
    request_path = destination / 'request.json'
    if request_path.exists(): require(read_json(request_path) == request, 'job request changed')
    else: write_json(request_path, request)
    completed = destination / 'process.completed.json'
    if completed.exists():
        marker = read_json(completed)
        require(marker['request_sha256'] == file_sha256(request_path)
                and marker['log_sha256'] == file_sha256(destination / 'worker.log'), 'completed job evidence changed')
        require(marker['exit_code'] == 0, 'completed failed job retained; no retry')
        unit = destination / 'artifact'
        require(file_sha256(unit / 'complete.json') == marker['artifact_marker_sha256'], 'artifact marker changed')
        verify_unit(unit, read_json(unit / 'complete.json')['binding'])
        return str(unit)
    require(not (destination / 'process.attempt.json').exists(), 'interrupted job retained; no automatic restart')
    write_json(destination / 'process.attempt.json', {'request_sha256': file_sha256(request_path)})
    env = {**os.environ, 'CUDA_VISIBLE_DEVICES': gpu_uuid, 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
           'OPENBLAS_NUM_THREADS': '1', 'PYTHONUNBUFFERED': '1'}
    with (destination / 'worker.log').open('x', encoding='utf-8') as log:
        child = subprocess.run([sys.executable, str(Path(__file__)), '--request', str(request_path),
            '--output', str(destination / 'artifact')], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    unit_marker = destination / 'artifact/complete.json'
    write_json(completed, {'request_sha256': file_sha256(request_path), 'exit_code': child.returncode,
        'log_sha256': file_sha256(destination / 'worker.log'),
        'artifact_marker_sha256': file_sha256(unit_marker) if unit_marker.exists() else None})
    require(child.returncode == 0, f"job {job['id']} failed; preserved {destination / 'worker.log'}")
    print(f"TRAINING_JOB_OK id={job['id']}", flush=True)
    return str(destination / 'artifact')


def compare_artifacts(first, second):
    a, b = Path(first), Path(second)
    ma, mb = read_json(a / 'complete.json'), read_json(b / 'complete.json')
    verify_unit(a, ma['binding']); verify_unit(b, mb['binding'])
    ja, jb = ma['binding']['job'], mb['binding']['job']
    require(ma['binding']['config'] == mb['binding']['config']
            and ma['binding']['runtime'] == mb['binding']['runtime'], 'different config/runtime compared')
    require({k: v for k, v in ja.items() if k != 'scorer_dependency'} ==
            {k: v for k, v in jb.items() if k != 'scorer_dependency'}, 'different scientific jobs compared')
    differences = []
    for step in ja['checkpoints']:
        pa = torch.load(a / f'checkpoint_{step}.pt', map_location='cpu', weights_only=True)
        pb = torch.load(b / f'checkpoint_{step}.pt', map_location='cpu', weights_only=True)
        for name in ['model_class', 'model_kwargs', 'fit_groups', 'evaluation_groups']:
            require(pa[name] == pb[name], 'checkpoint metadata differs: ' + name)
        for name in ['state_dict', 'teachers']:
            require(pa[name].keys() == pb[name].keys(), 'tensor key mismatch')
            for key in pa[name]:
                if not torch.equal(pa[name][key], pb[name][key]): differences.append(f'{step}/{name}/{key}')
        for name in ['fit_probabilities', 'evaluation_probabilities']:
            if not torch.equal(pa[name], pb[name]): differences.append(f'{step}/{name}')
    ra, rb = read_json(a / 'result.json'), read_json(b / 'result.json')
    if ra['checkpoints'] != rb['checkpoints']: differences.append('checkpoint_scores_or_trace')
    require(ra['parameter_signature'] == rb['parameter_signature'], 'parameter fairness mismatch')
    return {'pass': not differences, 'comparison': 'exact_tensor_values_and_checkpoint_metrics',
        'different_fields': differences, 'checkpoints': ja['checkpoints'],
        'serial_artifact_sha256': file_sha256(a / 'complete.json'),
        'parallel_artifact_sha256': file_sha256(b / 'complete.json')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    request = read_json(args.request); job = request['job']
    require(source_tree_sha256(ROOT, roots=('src', 'scripts', 'configs', 'tests')) == job['source_and_tests_sha256'], 'worker source changed')
    require(not capture_run_provenance(ROOT, component='training_worker')['git_dirty'], 'worker needs clean checkout')
    run_training_path(job, args.output, request['config'])


if __name__ == '__main__': main()
