"""Read-only R4-5 resource/contract audit; never runs a model or opens data.

The single output is a provenance-bearing results JSON. See D-097 and DATA.
An audit exit of zero does not authorize or certify training.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / 'results/spatial_history_r4_learning_preflight_v1.json'
CONTRACT = 'configs/spatial_history/learning_contract_r4_v2.json'
PARENT = 'results/spatial_history_r4_three_model_public_v1.json'
PARENT_SHA = 'e91c351b8696db94c44d29cbfaa060f91707fffbb2d428dc029d1ada3e913fee'
BEGAN = time.monotonic()


def record(path):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'bytes': path.stat().st_size, 'sha256': digest}


def command(args, timeout=30):
    remaining = 180 - (time.monotonic() - BEGAN)
    if remaining <= 0:
        raise TimeoutError('preflight 180-second budget exhausted')
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                            timeout=min(timeout, remaining), env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    return {'argv': args, 'exit_code': result.returncode,
            'stdout': result.stdout, 'stderr': result.stderr}


def audit():
    if not sys.platform.startswith('linux'):
        raise RuntimeError('server only')
    if REPORT.exists():
        raise FileExistsError('preserve existing report; no automatic repeat')
    began = time.monotonic()
    root = command(['git', 'rev-parse', '--show-toplevel'])
    if root['exit_code'] or Path(root['stdout'].strip()).resolve() != ROOT:
        raise RuntimeError('repository root mismatch')
    bound_paths = [CONTRACT, PARENT, 'ops/spatial_history/r4_learning_preflight_v1.py',
                   'configs/spatial_history/r4_family_design_v2.json',
                   'configs/spatial_history/protocol_r4_v1.json',
                   'docs/METHOD.md', 'docs/DATA.md', 'docs/DECISIONS.md']
    binding = {name: record(ROOT / name) for name in bound_paths}
    if binding[PARENT]['sha256'] != PARENT_SHA:
        raise ValueError('parent report digest changed')
    parent = json.loads((ROOT / PARENT).read_text())
    if parent['engineering_ready'] is not True or parent['trained_model_ready'] is not False:
        raise ValueError('unexpected parent status')
    verified = 0
    for artifact in parent['artifacts'].values():
        raw = artifact['text'].encode()
        if len(raw) != artifact['bytes'] or hashlib.sha256(raw).hexdigest() != artifact['sha256']:
            raise ValueError('embedded evidence changed')
        verified += 1
    if verified != 33:
        raise ValueError('expected all 33 parent artifacts')
    contract = json.loads((ROOT / CONTRACT).read_text())
    design = json.loads((ROOT / contract['dataset']['design_path']).read_text())
    splits = {}
    for row in design['rows']:
        splits.setdefault(row['split'], []).append(row['family_id'])
    if {key: len(value) for key, value in splits.items()} != contract['dataset']['split_counts']:
        raise ValueError('split contract mismatch')
    disks = {}
    for name in ('/', '/root/autodl-tmp'):
        path = Path(name).resolve(strict=True)
        usage = shutil.disk_usage(path)
        disks[name] = {'resolved_path': str(path), 'device_id': path.stat().st_dev,
                       'total_bytes': usage.total, 'used_bytes': usage.used,
                       'free_bytes': usage.free}
    devices = {v['device_id']: v['free_bytes'] for v in disks.values()}
    free = sum(devices.values())
    reserve = contract['resource_proposal']['disk_reserve_gib_per_filesystem'] * 2**30 * len(devices)
    requested = sum(contract['resource_proposal'][key] for key in
                    ('remaining_data_features_gib', 'new_checkpoints_states_reports_gib')) * 2**30
    probes = {
        'gpu': command(['nvidia-smi', '--query-gpu=name,memory.total,memory.used', '--format=csv,noheader']),
        'processes': command(['ps', '-eo', 'pid,etime,comm']),
        'dreamer': command(['/root/sh05-assets-v1/dreamer-env-v1/bin/python', '-B', '-c',
                           'import json,jax; print(json.dumps({"jax":jax.__version__,"devices":[d.platform for d in jax.devices()]}))']),
        'torch': command(['/root/sh05-assets-v1/flowm-env-v1/bin/python', '-B', '-c',
                         'import json,torch; print(json.dumps({"torch":torch.__version__,"cuda_available":torch.cuda.is_available()}))']),
        'git_head': command(['git', 'rev-parse', 'HEAD']),
        'git_status': command(['git', 'status', '--porcelain']),
        'clock': command(['date', '-u', '+%Y-%m-%dT%H:%M:%SZ']),
    }
    # Retain only process metadata relevant to computation; no environment or credentials.
    probes['processes']['stdout'] = '\n'.join(line for line in probes['processes']['stdout'].splitlines()
        if any(word in line for word in ('python', 'train', 'r4_', 'PID')))
    errors = [key for key, value in probes.items() if value['exit_code'] != 0]
    dreamer_gpu = False
    if not probes['dreamer']['exit_code']:
        dreamer_gpu = 'gpu' in json.loads(probes['dreamer']['stdout'])['devices']
    now = datetime.datetime.now(datetime.timezone.utc)
    deadline = datetime.datetime.fromisoformat(contract['resource_proposal']['previous_window_deadline_utc'])
    remaining = max(0, (deadline - now).total_seconds())
    reasons = list(contract['execution_gates']['unmet_at_registration'])
    if not dreamer_gpu:
        reasons.append('dreamer_cuda_backend_unavailable')
    if free < requested + reserve:
        reasons.append('registered_storage_envelope_exceeds_available_capacity')
    if remaining < contract['resource_proposal']['total_gpu_hours'] * 3600:
        reasons.append('previous_online_window_does_not_cover_full_gpu_hour_ceiling')
    reasons.extend('probe_failed:' + key for key in errors)
    if binding != {name: record(ROOT / name) for name in bound_paths}:
        raise ValueError('source changed during preflight')
    return {'schema_version': 'spatial-history-r4-learning-preflight-v1',
            'time_utc': now.isoformat(), 'repository_root': str(ROOT), 'binding': binding,
            'parent_embedded_artifacts_verified': verified, 'split_family_ids': splits,
            'disks': disks, 'probes': probes, 'dreamer_cuda_backend_available': dreamer_gpu,
            'capacity': {'unique_filesystem_free_bytes': free, 'required_reserve_bytes': reserve,
                         'requested_data_and_results_bytes': requested,
                         'shortfall_bytes': max(0, requested + reserve - free),
                         'new_environment_installation_bytes_not_yet_measured': True,
                         'previous_window_remaining_s': remaining},
            'audit_completed': True, 'training_executable': False,
            'confirmation_executable': False, 'unmet_conditions': reasons,
            'new_training_steps': 0, 'new_simulations': 0, 'dataset_files_read': 0,
            'new_weight_downloads': 0, 'elapsed_s': time.monotonic() - began, 'exit_code': 0}


if __name__ == '__main__':
    result = audit()
    encoded = json.dumps(result, indent=2, sort_keys=True) + '\n'
    if len(encoded.encode()) > 2**20 or time.monotonic() - BEGAN > 180:
        raise RuntimeError('preflight output/time budget exceeded')
    with REPORT.open('x') as stream:
        stream.write(encoded)
    print(json.dumps({'report': str(REPORT), **record(REPORT),
                      'training_executable': False, 'unmet_conditions': result['unmet_conditions'],
                      'exit_code': 0}), flush=True)
