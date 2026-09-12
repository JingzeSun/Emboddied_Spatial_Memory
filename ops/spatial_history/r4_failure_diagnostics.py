"""Read sealed R4 failures; export contact and E0 rejection summaries only.

No simulator, scientific-module import, rescoring, fitting or input writes.
Scope and Chinese field explanations: docs/PLAN.md, R4-2 failure diagnostics.
"""
import collections
import gzip
import hashlib
import io
import json
import platform
from pathlib import Path
import signal
import subprocess
import time


ROOT = Path(__file__).resolve().parents[2]
RUN = Path('/root/autodl-tmp/spatial-history/sh04-r4-engineering-subset-v1')
PARENT = ROOT / 'results/spatial_history_r4_engineering_subset_v1.json'
OUTPUT = ROOT / 'results/spatial_history_r4_failure_diagnostics_v1.json'
PARENT_SHA = '95da3e3e2a75a92b15c7774cfcb88875ebefe2bdbd3bf685e67400d46fb94341'
FAMILIES = ('r4-39', 'r4-47', 'r4-25', 'r4-03')
NAMES = ('LL', 'LR', 'RL', 'RR')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def record(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def contact_summary(raw, threshold):
    """Count positive-contact time steps per geom pair, not solver contacts."""
    pairs = {}
    count = 0
    first = last = None
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
        for line in stream:
            sample = json.loads(line)
            require(sample['step_index'] == count, 'trace step order changed')
            count += 1
            state = {key: sample[key] for key in ('step_index', 'time_s', 'object_position_m',
                     'pusher_position_m', 'actuator_force_n')}
            if first is None:
                first = state
            last = state
            positive = {}
            for contact in sample['contacts']:
                names = tuple(sorted(contact['geoms']))
                if not {'object', 'pusher'}.intersection(names):
                    continue
                if contact['distance_m'] > 0 or contact['normal_force_n'] <= threshold:
                    continue
                # Several solver points in one step count once. Peak is a
                # single-point normal force, not total pair force.
                positive[names] = max(positive.get(names, 0), contact['normal_force_n'])
            for names, force in positive.items():
                if names not in pairs:
                    pairs[names] = {'geoms': list(names), 'positive_steps': 0,
                                    'first': state, 'peak_point_normal_force_n': -1}
                item = pairs[names]
                item['positive_steps'] += 1
                item['last'] = state
                if force > item['peak_point_normal_force_n']:
                    item.update(peak_point_normal_force_n=force, peak=state)
    require(count == 10001, f'incomplete trace: {count} rows')
    return {'trace_rows': count, 'initial': first, 'terminal': last,
            'positive_contact_pairs': [pairs[key] for key in sorted(pairs)]}


def main():
    require(platform.system() == 'Linux', 'server-only read-only diagnosis')
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
    def timeout(signum, frame):
        raise TimeoutError('300 s diagnostic limit; original files preserved')
    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(300)
    began = time.monotonic()
    require(not OUTPUT.exists(), 'diagnostic report already exists; preserve and reuse it')
    parent_raw = PARENT.read_bytes()
    require(record(parent_raw)['sha256'] == PARENT_SHA, 'unexpected parent report bytes')
    parent = json.loads(parent_raw)
    require(parent['status'] == 'failed' and parent['verification_error'] is None,
            'requires the sealed engineering failure report')
    inv = parent['source_inventory']
    inputs = {}
    def bound(relative):
        path = RUN / relative
        require(path.resolve().is_relative_to(RUN.resolve()), 'input outside stage')
        require(path.is_file() and not path.is_symlink(), f'missing/unsafe input: {relative}')
        require(path.stat().st_size <= 32 * 1024**2, 'diagnostic input exceeds 32 MiB')
        raw = path.read_bytes()
        require(record(raw) == inv[relative], f'input digest mismatch: {relative}')
        inputs[relative] = record(raw)
        return raw
    require(json.loads(bound('run_receipt.json')) == parent['receipt'], 'receipt mismatch')
    summary = json.loads(bound('execution/summary.json'))
    require(summary == parent['artifacts_json']['execution/summary.json'], 'summary mismatch')
    require(tuple(f['family_id'] for f in summary['families']) == FAMILIES, 'family order changed')
    # Read the old bound config as a Git blob, not a potentially changed worktree.
    config_name = 'configs/spatial_history/two_gate_engineering_v1.json'
    config_raw = subprocess.check_output(['git', 'show', parent['receipt']['commit'] + ':' + config_name], cwd=ROOT)
    require(record(config_raw) == parent['receipt']['binding'][config_name], 'contact threshold source mismatch')
    threshold = json.loads(config_raw)['engineering_audit']['contact_force_min_n']
    result = []
    for family in summary['families']:
        fid = family['family_id']
        prefix = f'execution/{fid}/data/audit/'
        geometry, branches = [], []
        for world in NAMES:
            for mode in ('full', 'view_a', 'view_b', 'recent'):
                path = prefix + f'geometry/{world}-{mode}.json.gz'
                with gzip.GzipFile(fileobj=io.BytesIO(bound(path))) as stream:
                    prediction = json.load(stream)
                original = next(row['assessment'] for row in family['result']['geometry']['rows']
                                if row['world'] == world and row['mode'] == mode)
                require(len(prediction['candidates']) == original['candidate_count']
                        and len(prediction['conflicts']) == original['conflict_count'],
                        'original geometry summary mismatch')
                geometry.append({'world': world, 'mode': mode, 'source': path,
                    'candidate_count': len(prediction['candidates']),
                    'conflict_count': len(prediction['conflicts']),
                    'history_frames': prediction['history_frames'],
                    'rejected_counts': prediction['rejected_counts'],
                    'incomplete_reasons': dict(collections.Counter(
                        row['reason'] for row in prediction['incomplete_observations']))})
            for action in NAMES:
                path = prefix + f'{world}/primary-{action}/trace_raw.jsonl.gz'
                branch = next(b for b in family['result']['branches'] if b['world'] == world and b['action'] == action)
                contacts = contact_summary(bound(path), threshold)
                require(contacts['terminal']['object_position_m']
                        == branch['assessment']['terminal']['object_position_m'], 'original terminal mismatch')
                branches.append({'world': world, 'action': action, 'source': path,
                    'original_task_success': branch['assessment']['task_success'],
                    'contacts': contacts})
        result.append({'family_id': fid, 'geometry': geometry, 'branches': branches})
        print(f'{fid} READ geometry=16 branches=16', flush=True)
    # Check all consumed inputs again after analysis; this never changes the run.
    for path, expected in list(inputs.items()):
        require(record(bound(path)) == expected, f'input changed during diagnosis: {path}')
    require(PARENT.read_bytes() == parent_raw, 'parent report changed during diagnosis')
    output = {'version': 'sh04-r4-failure-diagnostics-v1', 'parent_report': record(parent_raw),
        'original_run_commit': parent['receipt']['commit'], 'inputs': inputs,
        'diagnostic_source': record(Path(__file__).read_bytes()),
        'threshold_source': {'path': config_name, **record(config_raw)},
        'contact_force_min_n': threshold, 'families': result,
        'scope': 'existing E0 rejection counters and raw positive-contact step summaries; no rescoring',
        'simulation_steps': 0, 'training_steps': 0, 'weight_download_bytes': 0,
        'elapsed_s_before_write': time.monotonic() - began}
    raw = encode(output)
    require(len(raw) <= 8 * 1024**2, 'diagnostic report exceeds 8 MiB')
    with OUTPUT.open('xb') as stream:
        stream.write(raw)
    require(OUTPUT.read_bytes() == raw, 'diagnostic output verification failed; preserve file')
    print(f'SH-04-R4-2 DIAGNOSTICS EXPORTED families=4 branches=64 geometry=64 path={OUTPUT} exit=0')


if __name__ == '__main__':
    main()
