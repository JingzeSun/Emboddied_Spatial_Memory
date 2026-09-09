"""Disk-backed paired-group CPU evaluation and registered statistics.

Workers receive paths, never audits or Torch models. A sibling pair stays in one
task and its 20-step worlds remain sequential. Timing under worker contention is
explicitly excluded from latency reporting; replay measures forwards separately.
"""
from __future__ import annotations
import gzip
import json
import math
import multiprocessing as mp
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
import numpy as np
import torch
from cpmt.dev_learning import masked_candidate_probabilities
from cpmt.executor import validate_graph
from cpmt.m1_af_rollout import causal_rollout_metrics
from cpmt.m1_s5_confirmation import complete_unit, verify_unit
from cpmt.m1_s5_training import read_json, write_json, require
from cpmt.run_provenance import file_sha256
from run_m1_af_scaled import _paired_causal_statistics
from run_m1_corrected_probe import contracts, SEEDS, METRICS
from m1_training_jobs import load_model


def validate_rows(rows, group_ids, seeds=None):
    expected = {(g, sibling) for g in group_ids for sibling in (0, 1)}
    keys = [(r['metrics']['paired_group_id'], r['metrics']['sibling_index']) for r in rows]
    require(len(keys) == len(expected) and set(keys) == expected, 'missing/duplicate sibling pair')
    require(len({r['metrics']['sequence_id'] for r in rows}) == len(rows), 'duplicate sequence ID')
    for row in rows:
        choices = row['choices']; require([c['step_index'] for c in choices] == list(range(20)), 'incomplete trajectory')
        require(all(a['post_graph_hash'] == b['base_graph_hash'] for a,b in zip(choices, choices[1:])), 'broken state chain')
        require(all(c['selected_static_preflight_pass'] for c in choices), 'selected masked candidate')
        require(all(math.isfinite(float(row['metrics'][m])) for m in METRICS), 'nonfinite endpoint')


def read_audits(spec):
    path = Path(spec['path']); require(file_sha256(path) == spec['sha256'], 'audit shard changed')
    with gzip.open(path, 'rt', encoding='utf-8') as stream: value = json.load(stream)
    audits = value['audits'] if isinstance(value, dict) else value
    require(len(audits) == 2 and {a['sibling_index'] for a in audits} == {0, 1}, 'audit pair incomplete')
    require(all(a['paired_group_id'] == spec['paired_group_id'] and len(a['steps']) == 20 for a in audits), 'wrong audit group')
    return audits


def run_serial(path, binding, model, specs, config):
    def produce(staging):
        began = time.monotonic()
        with gzip.open(staging / 'execution.jsonl.gz', 'wt', encoding='utf-8', compresslevel=1) as stream:
            def sink(materialized, choice, current):
                validate_graph(current)
                stream.write(json.dumps({'materialized': materialized, 'choice': choice, 'current': current}, allow_nan=False) + '\n')
            def audits():
                for spec in specs: yield from read_audits(spec)
            aggregate, rows = causal_rollout_metrics(model, audits(), config, audit_sink=sink)
        validate_rows(rows, [s['paired_group_id'] for s in specs])
        # Keep the raw value only inside the isolated worker artifact, marked
        # invalid for reported latency. Parent never averages these quantiles.
        aggregate['worker_forward_p95_ms_not_reportable'] = aggregate.pop('p95_forward_latency_ms')
        write_json(staging / 'result.json', {'binding': binding, 'aggregate': aggregate, 'sequences': rows,
            'wall_seconds': time.monotonic()-began, 'device': 'cpu', 'torch_threads': 1,
            'peak_vram_bytes': 0, 'latency_measurement_valid': False})
    complete_unit(path, binding, produce)
    result = read_json(path / 'result.json')
    validate_rows(result['sequences'], [s['paired_group_id'] for s in specs])
    return result


_WORKER = None
_MODEL = None


def init_worker(model_spec, config):
    global _WORKER, _MODEL
    torch.set_num_threads(1)
    _WORKER = (model_spec, config)
    _MODEL = None


def evaluate_group(task):
    global _MODEL
    output, binding, spec = task
    model_spec, config = _WORKER
    # Load inside the first task so failures propagate to the parent; raising
    # in Pool.initializer can otherwise cause repeated worker respawns.
    if _MODEL is None:
        saved = Path(model_spec['path'])
        require(file_sha256(saved / 'complete.json') == model_spec['marker_sha256'], 'model marker changed')
        _MODEL, _ = load_model(saved, read_json(saved / 'complete.json')['binding'], model_spec['checkpoint'], torch.device('cpu'))
    path = Path(output)
    run_serial(path, binding, _MODEL, [spec], config)
    return {'paired_group_id': spec['paired_group_id'], 'path': str(path), 'marker_sha256': file_sha256(path / 'complete.json')}


def merge_shards(shards, specs):
    require(len(shards) == len(specs) and {s['paired_group_id'] for s in shards} == {s['paired_group_id'] for s in specs}, 'shard coverage mismatch')
    rows = []
    for shard in sorted(shards, key=lambda s: s['paired_group_id']):
        path = Path(shard['path']); require(file_sha256(path / 'complete.json') == shard['marker_sha256'], 'completed shard changed')
        marker = read_json(path / 'complete.json'); verify_unit(path, marker['binding'])
        part = read_json(path / 'result.json')['sequences']; validate_rows(part, [shard['paired_group_id']]); rows.extend(part)
    rows.sort(key=lambda r: (r['metrics']['paired_group_id'], r['metrics']['sibling_index']))
    validate_rows(rows, [s['paired_group_id'] for s in specs])
    return rows


def evaluate_parallel(output, binding, model_spec, specs, config, workers=4):
    require(1 <= workers <= 4 and len({s['paired_group_id'] for s in specs}) == len(specs), 'invalid worker/group layout')
    output.mkdir(parents=True, exist_ok=True)
    tasks = [(str(output / f'group_{i:06d}'), {**binding, 'audit': spec, 'model': model_spec, 'config': config}, spec) for i,spec in enumerate(specs)]
    began = time.monotonic(); shards = []
    with mp.get_context('spawn').Pool(workers, initializer=init_worker, initargs=(model_spec, config)) as pool:
        for count, shard in enumerate(pool.imap_unordered(evaluate_group, tasks), 1):
            shards.append(shard)
            print(f'PAIRED_EVALUATION_GROUP_OK group={shard["paired_group_id"]} completed={count}/{len(specs)}', flush=True)
    rows = merge_shards(shards, specs)
    return {'sequences': rows, 'shards': sorted(shards, key=lambda s: s['paired_group_id']),
        'wall_seconds': time.monotonic()-began, 'workers': workers, 'device': 'cpu', 'torch_threads': 1,
        'peak_vram_bytes': 0, 'p95_forward_latency_ms': None, 'latency_requires_serial_replay': True}


def serial_forward_replay(model_spec, shards):
    """No training/evaluation pool may be active when the caller invokes this."""
    from cpmt.m1_af_rollout import online_feature_vector
    torch.set_num_threads(1)
    path = Path(model_spec['path']); require(file_sha256(path / 'complete.json') == model_spec['marker_sha256'], 'model changed')
    model, _ = load_model(path, read_json(path / 'complete.json')['binding'], model_spec['checkpoint'], torch.device('cpu'))
    elapsed = []; began = time.monotonic()
    for shard in shards:
        directory = Path(shard['path']); marker = read_json(directory / 'complete.json'); verify_unit(directory, marker['binding'])
        with gzip.open(directory / 'execution.jsonl.gz', 'rt', encoding='utf-8') as stream:
            for line in stream:
                record = json.loads(line); materialized = record['materialized']
                vector = online_feature_vector(materialized['online'])
                mask = torch.as_tensor([[c['static_preflight_pass'] for c in materialized['executed_candidates']]], dtype=torch.bool)
                start = time.perf_counter()
                with torch.no_grad():
                    p = masked_candidate_probabilities(model(torch.as_tensor(vector[None])), mask).cpu().numpy()[0]
                elapsed.append((time.perf_counter()-start)*1000)
                require(int(np.argmax(p)) == record['choice']['selected_index'], 'replayed online selection changed')
    require(elapsed, 'empty latency replay')
    return {'p95_forward_latency_ms': float(np.quantile(elapsed, .95)), 'forward_calls': len(elapsed),
        'wall_seconds': time.monotonic()-began, 'device': 'cpu', 'torch_threads': 1, 'peak_vram_bytes': 0,
        'conditions': 'separate_serial_forward_replay_no_phase_training_or_evaluation_pool',
        'scope': 'network_and_tensor_probability_operations_not_system_latency', 'machine_global_exclusivity_verified': False}


def registered_statistics(payloads, registered, *, split, groups, seeds=SEEDS, engineering=False):
    hard, rebuild, _ = contracts()
    require(split in ['train', 'validation', 'test'], 'invalid statistics split')
    require(split == 'train' if engineering else split != 'train', 'statistics role mismatch')
    require(registered['schema_version'] == 'cpmt-m1-corrected-post-probe-registration-v1', 'wrong registration')
    require(registered['evaluation_plan']['semantic_metric'] == METRICS[0] and registered['evaluation_plan']['support_metric'] == METRICS[1]
        and registered['evaluation_plan']['burden_metric'] == METRICS[2], 'endpoint drift')
    require(registered['evaluation_plan']['minimum_effects'] == rebuild['endpoints']['minimum_effects'], 'effect gate drift')
    if not engineering:
        require(len(groups) == registered['evaluation_plan']['paired_groups'][split] and seeds == SEEDS, 'formal statistics population mismatch')
    required = ['cpmt_ctl_core', 'direct_future_loss', 'future_no_execution']
    require(all(m in payloads for m in required), 'missing main contrast')
    for method, runs in payloads.items():
        require(len(runs) == len(seeds) and {r['aggregate']['seed'] for r in runs} == set(seeds), 'missing/duplicate seed')
        for run in runs:
            validate_rows(run['sequences'], groups)
            require(all(r['metrics']['paired_group_id'].startswith('rollout-pair:' + split + ':') for r in run['sequences']), 'wrong statistical split')
            require(all(math.isfinite(float(r['metrics'][m])) for r in run['sequences'] for m in
                [*METRICS, 'false_birth_growth_per_100', 'collateral_violation_per_100', 'active_node_state_error_per_100']), 'nonfinite statistics input')
    overlay = read_json(ROOT / 'configs/m1_endpoint_viability_probe.json')
    stats = _paired_causal_statistics(payloads, hard, overlay)
    require(stats['paired_groups'] == len(groups), 'paired reducer count mismatch')
    stats.update(scope='train_only_interface_check_not_method_evidence' if engineering else split + '_registered_statistics',
        method_effect_claim=False, formal_test_release=False,
        invariant_gate_checked_separately_from_statistics=True)
    return stats
