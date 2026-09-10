"""Frozen S5 confirmation consumers; no data generation or training here.

See D-055 and the experiment contract for the one-use validation boundary.
"""
from __future__ import annotations
import hashlib
import io
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
from cpmt.m1_s5_training import read_json, require
from cpmt.m1_protocol import protocol_sha256
from cpmt.run_provenance import file_sha256, source_tree_sha256
from m1_corrected_training_plan import ARCHES, METHODS, SEEDS, consume_probe

PLAN = 'configs/m1_s5_confirmation_v7.json'
BASE = '4c89e59'
OUTPUT_ROOT = Path('/root/autodl-tmp/cpmt_outputs')
EXPORTS = {k: f'results/m1_v7_d055_s5_{k}.json' for k in ['data', 'confirmation']}


def source_bridge(root=ROOT):
    """Reuse tested algorithms byte-for-byte, admitting only new stage files."""
    raw = subprocess.check_output(['git', 'archive', BASE, 'src', 'scripts', 'configs'], cwd=root)
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        names = []
        for member in archive.getmembers():
            if not member.isfile(): continue
            before = archive.extractfile(member).read().replace(b'\r\n', b'\n')
            require((root / member.name).read_bytes().replace(b'\r\n', b'\n') == before,
                    'previously verified algorithm/config changed: ' + member.name)
            names.append(member.name)
    return {'base_commit': subprocess.check_output(['git', 'rev-parse', BASE], cwd=root, text=True).strip(),
            'verified_existing_files': len(names), 'existing_algorithms_unchanged': True}


def validate_plan(plan):
    require(plan['schema_version'] == 'cpmt-s5-corrected-confirmation-plan-v1', 'wrong S5 plan')
    require(plan['indices'] == list(range(4, 204)) and plan['excluded_historical_indices'] == [0, 1, 2, 3],
            'fixed validation range changed')
    require(plan['split'] == 'validation' and plan['seeds'] == SEEDS and plan['methods'] == METHODS
            and plan['architectures'] == ARCHES, 'confirmation matrix changed')
    require(plan['siblings'] == 2 and plan['horizon'] == 20 and plan['future_hash_bins'] == 32, 'data shape drift')
    require(plan['generation_workers_max'] == 16 and plan['evaluation_workers'] == 4
            and plan['torch_threads'] == 1 and plan['device'] == 'cpu', 'runtime policy drift')
    require(plan['smoke_train_group'] == 1 and plan['smoke_seed'] == 7, 'engineering sample drift')
    require(not plan['test_access'] and not plan['model_selection_performed'] and not plan['formal_test_release'],
            'held-out selection/test release forbidden')
    require(plan['commit_probability'] == plan['margin_threshold'] == 0.0, 'commit gate drift')
    require(plan['oracle_methods'] == ['oracle_candidate_program', 'observable_information_oracle'], 'oracle drift')


def validate_exports(exports, plan):
    for kind, value in exports.items():
        require(value['kind'] == kind and value['pass'] and not value['failures'] and not value['failed_jobs'],
                'upstream export failed: ' + kind)
        require(not value['validation_access'] and not value['test_access'], 'upstream held-out access')
        require(all(m['exit_code'] == 0 for m in value['completion'].values()), 'upstream step failed')
        require(value['binding']['source_and_tests_sha256'] == plan['training_source_sha256'], 'wrong upstream source')
    budget = exports['budget']['reports']['budget']; refit = exports['refit']['reports']['refit']
    require(exports['refit']['reports']['budget'] == budget and refit['selected'] == budget['selected'], 'selection changed')
    require(budget['optimizer_paths'] == len(budget['artifacts']) == 200
            and budget['checkpoint_observations'] == 740, 'incomplete budget')
    require(refit['trained_models'] == len(refit['models']) == 60 and refit['train_groups'] == 1000
            and not refit['inner_dev_independent'], 'incomplete/wrong refit')
    seen = set()
    for key, row in refit['models'].items():
        a, m, s = row['architecture'], row['method'], row['seed']; identity = (a, m, s)
        require(identity not in seen, 'duplicate model'); seen.add(identity)
        choice = budget['selected'][a][m]; job = row['training']['binding']['job']
        require(job['id'] == key and job['architecture'] == a and job['method'] == m and job['seed'] == s, 'wrong model identity')
        require(job['mode'] == 'refit' and job['groups'] == list(range(1000)), 'wrong fitting population')
        require(job['learning_rate'] == choice['learning_rate'] and job['checkpoints'] == [choice['steps']]
                and row['checkpoint'] == choice['steps'] and job['auxiliary_weight'] == choice['auxiliary_weight'], 'model recipe changed')
        require(all(c['inner_dev'] is None and not c['inner_dev_independent'] for c in row['training']['checkpoints']), 'refit claims held-out scores')
    require(seen == {(a, m, s) for a in ARCHES for m in ['outcome_scorer', *METHODS] for s in SEEDS}, 'model matrix missing')
    return refit


def consume(root=ROOT):
    plan = read_json(root / PLAN); validate_plan(plan)
    exports = {}
    for kind, spec in plan['input_exports'].items():
        require(file_sha256(root / spec['path']) == spec['sha256'], 'accepted export changed: ' + kind)
        exports[kind] = read_json(root / spec['path'])
    refit = validate_exports(exports, plan)
    _, registration = consume_probe(root)
    require(refit['binding']['registration'] == registration, 'corrected registration differs')
    require(protocol_sha256(registration) == plan['registration_sha256'], 'registration pin drift')
    require(registration['evaluation_plan']['paired_groups']['validation'] == 200, 'wrong confirmation N')
    return plan, refit, registration


def binding_now(root=ROOT):
    plan, refit, registration = consume(root)
    return {'schema_version': 'cpmt-s5-corrected-binding-v1', 'plan': plan,
            'plan_sha256': protocol_sha256(plan), 'registration': registration,
            'source_and_tests_sha256': source_tree_sha256(root, roots=('src', 'scripts', 'configs', 'tests')),
            'source_bridge': source_bridge(root), 'training_source_sha256': plan['training_source_sha256'],
            'selected': refit['selected'], 'runtime': runtime(), 'test_access': False, 'model_selection_performed': False}


def clean_checkout(root=ROOT):
    allowed = set(EXPORTS.values()) | {'results/m1_v7_d054_training_process_check.json'}
    lines = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=root, text=True).splitlines()
    require(all(l[3:] in allowed and not any(c in l[:2] for c in 'DR') for l in lines), 'uncommitted stage source/input changes')


def runtime():
    import platform
    import socket
    import numpy as np
    import torch
    return {'python': platform.python_version(), 'numpy': str(np.__version__), 'torch': str(torch.__version__),
            'platform': platform.platform(), 'hostname': socket.gethostname(), 'device': 'cpu', 'torch_threads': 1}


def model_spec(row):
    return {k: row[k] for k in ['path', 'checkpoint', 'marker_sha256']}


def verify_saved(row, *, load=False):
    from cpmt.m1_s5_confirmation import verify_unit
    path = Path(row['path']); checkpoint = row['checkpoint']
    require(file_sha256(path / 'complete.json') == row['marker_sha256'], 'model completion changed')
    require(file_sha256(path / f'checkpoint_{checkpoint}.pt') == row['model_sha256'], 'model weights changed')
    binding = row['training']['binding']; verify_unit(path, binding)
    require(read_json(path / 'result.json') == row['training'], 'saved training report changed')
    if load:
        import torch
        from m1_training_jobs import load_model
        return load_model(path, binding, checkpoint, torch.device('cpu'))
    return binding
