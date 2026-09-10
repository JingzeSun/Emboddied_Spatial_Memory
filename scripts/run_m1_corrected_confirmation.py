"""D-055 S5 generation, saved-model evaluation and summary. Never trains.

All algorithms are reused from the verified v7 pipeline. New validation is
fixed at groups 4..203. A training-only rehearsal precedes validation generation.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import gzip
import json
import multiprocessing as mp
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts'), str(ROOT / 'ops')]
import numpy as np
import torch
from cpmt.executor import validate_graph
from cpmt.m1_af_rollout import causal_rollout_metrics, rollout_learning_arrays_from_audits
from cpmt.m1_rollout import generate_m1_paired_rollout_split
from cpmt.m1_protocol import load_and_validate, protocol_sha256
from cpmt.m1_s5_training import read_json, write_json, require
from cpmt.m1_s5_confirmation import complete_unit, verify_unit, reserve_trial
from cpmt.run_provenance import file_sha256, arrays_sha256, capture_run_provenance
from m1_corrected_confirmation_plan import binding_now, consume, model_spec, verify_saved, ARCHES, METHODS, SEEDS
from m1_paired_evaluation import (ReplayableAudits, read_audits, validate_rows, run_serial,
    evaluate_parallel, merge_shards, serial_forward_replay, registered_statistics)
from run_m1_s5_confirmation import write_gzip, evaluation_config, teacher_forced
from run_m1_corrected_probe import F_REQUIRED, contracts
from run_m1_corrected_followon import immutable_json

ORDER = ['prepare', 'smoke', 'generate', 'evaluate', 'summarize']


def make_group(task):
    config_path, directory, split, index, binding = task
    require(split in ['train', 'validation'], 'test generation forbidden')
    require(index == 1 if split == 'train' else index in range(4, 204), 'unregistered sample')
    torch.set_num_threads(1)
    hard = load_and_validate(Path(config_path)); path = Path(directory) / f'group_{index:06d}'
    unit_binding = {**binding, 'split': split, 'group_index': index}
    def produce(staging):
        began = time.monotonic()
        _, audits, summary = generate_m1_paired_rollout_split(hard, split, paired_groups=1, start_group_index=index)
        require(len(audits) == 2 and {a['sibling_index'] for a in audits} == {0, 1}, 'incomplete generated pair')
        require(all(a['paired_group_id'] == f'rollout-pair:{split}:{index:06d}' and len(a['steps']) == 20 for a in audits), 'generated identity drift')
        arrays = rollout_learning_arrays_from_audits(hard, audits, future_hash_bins=32)
        arrays['group'][:] = index
        require(len(arrays['y']) == 40 and int(arrays['recovery'].sum()) == 2, 'learning/recovery count drift')
        np.savez(staging / 'learning.npz', **arrays); write_gzip(staging / 'audits.json.gz', audits)
        coverage = defaultdict(lambda: {'decisions': 0, 'covered': 0})
        for audit in audits:
            validate_graph(audit['initial_world'])
            for step in audit['steps']:
                ref = step['executed_candidates'][step['reference_program_index']]
                c = coverage[step['scenario_family']]; c['decisions'] += 1
                c['covered'] += int(ref['legal'] and ref['static_preflight_pass'])
                for candidate in step['executed_candidates']:
                    if candidate['legal']: validate_graph(candidate['post_graph'])
        write_json(staging / 'summary.json', {'generator_summary': summary, 'coverage': dict(coverage),
            'arrays_digest': arrays_sha256(arrays), 'learning_rows': 40, 'recovery_rows': 2,
            'invariant_violations': 0, 'wall_seconds': time.monotonic()-began})
    marker = complete_unit(path, unit_binding, produce)
    return {'index': index, 'path': str(path), 'marker': marker}


def data_health(summaries, hard):
    family = defaultdict(lambda: {'decisions': 0, 'covered': 0, 'teacher_rows': 0, 'teacher_correct': 0.0})
    for summary in summaries:
        require(summary['invariant_violations'] == 0, 'generated world invalid')
        for name, row in summary['coverage'].items():
            for k in ['decisions', 'covered']: family[name][k] += row[k]
        for name, row in summary['generator_summary']['teacher_reference_agreement_by_family'].items():
            family[name]['teacher_rows'] += row['support']
            family[name]['teacher_correct'] += row['support'] * (row['reference_agreement'] or 0.0)
    require(set(family) == set(hard['data']['scenario_families']), 'missing family support')
    require(all(r['decisions'] > 0 and r['teacher_rows'] > 0 for r in family.values()), 'empty health denominator')
    coverage = sum(r['covered'] for r in family.values()) / sum(r['decisions'] for r in family.values())
    agreement = sum(r['teacher_correct'] for r in family.values()) / sum(r['teacher_rows'] for r in family.values())
    gate = hard['energy']['teacher_health_gate']
    gates = {'candidate_coverage': coverage >= hard['candidates']['coverage_gate_overall'] and all(
        r['covered']/r['decisions'] >= hard['candidates']['coverage_gate_each_family'] for r in family.values()),
        'teacher_health': agreement >= gate['reference_agreement_overall_minimum'] and all(
        r['teacher_correct']/r['teacher_rows'] >= gate['reference_agreement_each_family_minimum'] for r in family.values()),
        'invariant_violations': 0}
    return {'family_health': dict(family), 'candidate_coverage': coverage, 'teacher_reference_agreement': agreement, 'gates': gates}


def group_spec(row, split):
    p = Path(row['path']) / 'audits.json.gz'
    return {'path': str(p), 'sha256': file_sha256(p), 'paired_group_id': f'rollout-pair:{split}:{row["index"]:06d}'}


def read_groups(rows, binding, split):
    specs, pieces = [], []
    for row in sorted(rows, key=lambda r: r['index']):
        path = Path(row['path']); expected = {**binding, 'split': split, 'group_index': row['index']}
        require(verify_unit(path, expected) == row['marker'], 'data marker changed')
        with np.load(path / 'learning.npz', allow_pickle=False) as saved: arrays = {k: saved[k] for k in saved.files}
        require(arrays_sha256(arrays) == read_json(path / 'summary.json')['arrays_digest'], 'data digest drift')
        require(set(arrays['group'].tolist()) == {row['index']}, 'array group drift')
        specs.append(group_spec(row, split)); read_audits(specs[-1]); pieces.append(arrays)
    return specs, {k: np.concatenate([p[k] for p in pieces]) for k in pieces[0]}


def config_for(binding, saved=None):
    hard, _, _ = contracts()
    return evaluation_config(hard, {'evaluation': {**binding['plan'],
        'candidate_availability_policy': binding['registration']['candidate_availability_policy']}}, saved)


def run_oracle(task):
    output, binding, spec, method, config = task
    torch.set_num_threads(1); path = Path(output)
    require(method in ['oracle_candidate_program', 'observable_information_oracle'], 'wrong oracle')
    def produce(staging):
        began = time.monotonic()
        with gzip.open(staging / 'execution.jsonl.gz', 'wt', encoding='utf-8', compresslevel=1) as stream:
            def sink(materialized, choice, current):
                validate_graph(current)
                stream.write(json.dumps({'materialized': materialized, 'choice': choice, 'current': current}, allow_nan=False)+'\n')
            aggregate, rows = causal_rollout_metrics(None, ReplayableAudits([spec]), config,
                oracle=method == 'oracle_candidate_program', observable_oracle=method == 'observable_information_oracle', audit_sink=sink)
        validate_rows(rows, [spec['paired_group_id']])
        if method == 'oracle_candidate_program':
            require(all(r['metrics'][k] == v for r in rows for k,v in F_REQUIRED.items()), 'F integrity failure')
        aggregate.pop('p95_forward_latency_ms', None)
        write_json(staging / 'result.json', {'binding': binding, 'aggregate': aggregate, 'sequences': rows,
            'wall_seconds': time.monotonic()-began, 'peak_vram_bytes': 0, 'latency_scope': 'not_a_learned_network'})
    complete_unit(path, binding, produce)
    return {'paired_group_id': spec['paired_group_id'], 'path': str(path), 'marker_sha256': file_sha256(path / 'complete.json')}


def oracle_layout(output, binding, specs, method, workers):
    tasks = [(str(output / f'group_{i:06d}'), {**binding, 'method': method, 'audit': spec}, spec, method, config_for(binding)) for i,spec in enumerate(specs)]
    shards = []
    with mp.get_context('spawn').Pool(workers) as pool:
        for n, shard in enumerate(pool.imap_unordered(run_oracle, tasks), 1):
            shards.append(shard); print(f'S5_ORACLE_GROUP_OK method={method} completed={n}/{len(specs)}', flush=True)
    rows = merge_shards(shards, specs)
    return {'sequences': rows, 'shards': sorted(shards, key=lambda r:r['paired_group_id'])}


def run_model(output, binding, key, row, specs, arrays):
    path = output / key
    unit_binding = {**binding, 'model_key': key, 'model': model_spec(row), 'audits': specs}
    if path.exists():
        verify_unit(path, unit_binding); result = read_json(path / 'result.json')
        # Verify shard contents as well as the compact parent artifact.
        require(merge_shards(result['evaluation']['shards'], specs) == result['sequences'], 'reused evaluation rows changed')
        verify_saved(row)
        return result
    def produce(staging):
        began = time.monotonic()
        model, payload = verify_saved(row, load=True)
        config = config_for(binding, payload['binding']['config'])
        forced = teacher_forced(model, arrays); del model, payload
        # Shards are outside the atomic parent, so their recorded paths do not
        # change when the parent staging directory is renamed on completion.
        ev = evaluate_parallel(output / 'shards' / key, unit_binding, model_spec(row), specs, config, workers=4)
        latency = serial_forward_replay(model_spec(row), ev['shards'])
        require(latency['forward_calls'] == len(specs)*40, 'incomplete serial forward replay')
        rows = ev.pop('sequences')
        write_json(staging / 'result.json', {'binding': unit_binding, 'sequences': rows, 'teacher_forced': forced,
            'evaluation': ev, 'latency': latency, 'aggregate': {'seed': row['seed'], 'method': row['method']},
            'wall_seconds': time.monotonic()-began, 'validation_access': specs[0]['paired_group_id'].startswith('rollout-pair:validation:'),
            'test_access': False, 'model_selection_performed': False})
    complete_unit(path, unit_binding, produce)
    return read_json(path / 'result.json')


def prepare(output, binding):
    _, refit, _ = consume(); verified = {}
    torch.set_num_threads(1)
    for n,(key,row) in enumerate(sorted(refit['models'].items()), 1):
        model, payload = verify_saved(row, load=True); del model, payload
        verified[key] = {'model_sha256':row['model_sha256'], 'marker_sha256':row['marker_sha256'], 'checkpoint':row['checkpoint']}
        print(f'S5_MODEL_LOAD_OK completed={n}/60', flush=True)
    immutable_json(output / 'binding.json', binding)
    complete_unit(output / 'prepared', binding, lambda p: write_json(p / 'report.json', {
        'pass':True, 'verified_models':verified, 'models':60, 'validation_access':False, 'test_access':False,
        'training_performed':False, 'provenance':capture_run_provenance(ROOT,component='s5_prepare',entrypoint=Path(__file__))}))


def smoke(output, binding):
    verify_unit(output / 'prepared', binding)
    hard, _, _ = contracts(); _, refit, _ = consume()
    row = make_group((str(ROOT / 'configs/m1_hard_condition_v7.json'),str(output / 'smoke_data'),'train',1,binding))
    specs, arrays = read_groups([row], binding, 'train')
    # Verify the new writer against the already accepted fixed train anchor.
    old = Path(refit['binding']['probe_dir']) / 'audits/group_000001/train_inner_dev_000001.json.gz'
    old_spec = {'path':str(old), 'sha256':file_sha256(old), 'paired_group_id':'rollout-pair:train:000001'}
    expected = rollout_learning_arrays_from_audits(hard, read_audits(old_spec), future_hash_bins=32); expected['group'][:] = 1
    require(arrays_sha256(arrays) == arrays_sha256(expected), 'new writer differs from accepted train arrays')
    oracles = {m:oracle_layout(output/'smoke_oracles'/m,binding,specs,m,1) for m in binding['plan']['oracle_methods']}
    completed = []
    for key,model in sorted(refit['models'].items()):
        if model['seed'] != 7 or model['method'] not in ['cpmt_ctl_core','direct_future_loss','future_no_execution']: continue
        run_model(output/'smoke_models',binding,key,model,specs,arrays); completed.append(key)
        print(f'S5_SMOKE_MODEL_OK completed={len(completed)}/6',flush=True)
    stored=lambda p:sum(f.stat().st_size for f in p.rglob('*') if f.is_file())
    estimate=int(1.25*(stored(output/'smoke_data')*200 + stored(output/'smoke_models')*(50/6)*200 + stored(output/'smoke_oracles')*200))
    complete_unit(output/'smoke',binding,lambda p:write_json(p/'report.json',{'pass':True,'new_writer_matches_train':True,
        'models':completed,'learned_decisions':240,'oracle_decisions':80,'oracles':oracles,
        'estimated_additional_disk_bytes':estimate,'disk_estimate_scope':'one_train_pair_extrapolation_with_25_percent_margin_not_guarantee',
        'validation_access':False,'test_access':False,'training_performed':False}))


def generate(output, binding):
    verify_unit(output/'smoke',binding)
    estimate=read_json(output/'smoke/report.json')['estimated_additional_disk_bytes']
    free=shutil.disk_usage(output).free
    print(f'S5_DISK_PLAN estimated_bytes={estimate} available_bytes={free}',flush=True)
    require(free>=estimate,'insufficient disk for planned audit retention; no data generated')
    from m1_train_preflight import capacity
    machine = capacity(); workers = min(16, max(1,int(machine['cpu_capacity'])), max(1,int((machine['available_memory_gib']-2)//4)))
    require(machine['available_memory_gib'] >= 6, 'insufficient generation memory')
    print('S5_GENERATION_RESOURCES='+json.dumps({**machine,'workers':workers}),flush=True)
    indices = binding['plan']['indices']; rows=[]
    tasks=[(str(ROOT/'configs/m1_hard_condition_v7.json'),str(output/'data'),'validation',i,binding) for i in indices]
    with mp.get_context('spawn').Pool(workers) as pool:
        for row in pool.imap_unordered(make_group,tasks):
            rows.append(row)
            write_json(output/'generation_progress.json',{'binding':binding,'groups':sorted(rows,key=lambda r:r['index'])})
            print(f'S5_DATA_GROUP_OK index={row["index"]} completed={len(rows)}/200',flush=True)
    require(sorted(r['index'] for r in rows)==indices,'incomplete generated population')
    hard,_,_=contracts(); health=data_health([read_json(Path(r['path'])/'summary.json') for r in rows],hard)
    manifest={'binding':binding,'groups':sorted(rows,key=lambda r:r['index']),'paired_groups':200,'sequences':400,
        'decisions':8000,'learning_rows':8000,'recovery_rows':400,**health,
        'model_evaluation_performed':False,'validation_trial_consumed':False,'test_access':False,
        'resources':{**machine,'workers':workers},'provenance':capture_run_provenance(ROOT,component='s5_generate',entrypoint=Path(__file__))}
    immutable_json(output/'data_manifest.json',manifest)
    require(all(health['gates'][k] for k in ['candidate_coverage','teacher_health']), 'data health failed; no replacement groups')


def manifest_for(output,binding):
    manifest=read_json(output/'data_manifest.json')
    require(manifest['binding']==binding and [r['index'] for r in manifest['groups']]==binding['plan']['indices'],'wrong validation manifest')
    require(manifest['gates']['candidate_coverage'] and manifest['gates']['teacher_health'] and manifest['gates']['invariant_violations']==0,'data health failed')
    return manifest


def evaluate(output,binding):
    from m1_train_preflight import capacity
    machine=capacity();require(machine['workers']>=4,'four-worker CPU/RAM capacity unavailable')
    print('S5_EVALUATION_RESOURCES='+json.dumps(machine),flush=True)
    _,refit,_=consume(); verify_unit(output/'prepared',binding)
    for row in refit['models'].values():verify_saved(row)
    # Reservation precedes opening validation arrays/audits for model evaluation.
    manifest=manifest_for(output,binding)
    trial_binding={**binding,'data_manifest_sha256':file_sha256(output/'data_manifest.json')}
    consumption=reserve_trial(output/'data/confirmation_consumption.json',trial_binding,output/'evaluation')
    immutable_json(output/'validation_trial.json',consumption)
    specs,arrays=read_groups(manifest['groups'],binding,'validation')
    oracles={}
    for method in binding['plan']['oracle_methods']:
        value=oracle_layout(output/'evaluation/oracles'/method,binding,specs,method,4)
        immutable_json(output/f'{method}.json',value);oracles[method]=file_sha256(output/f'{method}.json')
    models={}
    for key,row in sorted(refit['models'].items()):
        if row['method']=='outcome_scorer':continue
        result=run_model(output/'evaluation/models',binding,key,row,specs,arrays)
        path=output/'evaluation/models'/key
        models[key]={'path':str(path),'marker_sha256':file_sha256(path/'complete.json'),'model_sha256':row['model_sha256'],
            'architecture':row['architecture'],'method':row['method'],'seed':row['seed']}
        print(f'S5_MODEL_EVALUATION_OK completed={len(models)}/50 architecture={row["architecture"]} method={row["method"]} seed={row["seed"]}',flush=True)
    require(len(models)==50,'incomplete evaluation model matrix')
    immutable_json(output/'evaluation_manifest.json',{'binding':binding,'models':models,'oracles':oracles,
        'validation_trial_consumed':True,'test_access':False,'learned_decisions':400000,'oracle_decisions':16000})


def summarize(output,binding):
    manifest=manifest_for(output,binding); ev=read_json(output/'evaluation_manifest.json')
    require(ev['binding']==binding and len(ev['models'])==50,'wrong evaluation manifest')
    require(set(ev['oracles'])==set(binding['plan']['oracle_methods']),'missing oracle evaluation')
    identities=[(r['architecture'],r['method'],r['seed']) for r in ev['models'].values()]
    require(len(identities)==len(set(identities)) and set(identities)=={(a,m,s) for a in ARCHES for m in METHODS for s in SEEDS},'incomplete final model matrix')
    trial=read_json(output/'validation_trial.json')
    require(trial==read_json(output/'data/confirmation_consumption.json') and trial['binding']=={**binding,'data_manifest_sha256':file_sha256(output/'data_manifest.json')},'validation reservation changed')
    groups=[f'rollout-pair:validation:{i:06d}' for i in binding['plan']['indices']]
    arms={a:defaultdict(list) for a in ARCHES}; compact={}
    for key,row in ev['models'].items():
        path=Path(row['path']);require(file_sha256(path/'complete.json')==row['marker_sha256'],'evaluation marker changed')
        marker=read_json(path/'complete.json');verify_unit(path,marker['binding'])
        result=read_json(path/'result.json');validate_rows(result['sequences'],groups)
        # Validate all execution shards; never infer completeness from a counter.
        require(merge_shards(result['evaluation']['shards'],marker['binding']['audits'])==result['sequences'],'evaluation shard rows changed')
        arms[row['architecture']][row['method']].append(result)
        compact[key]={'architecture':row['architecture'],'method':row['method'],'seed':row['seed'],
            'teacher_forced':result['teacher_forced'],'latency':result['latency'],'evaluation':result['evaluation'],
            'wall_seconds':result['wall_seconds'],'metrics':[r['metrics'] for r in result['sequences']],
            'model_sha256':row['model_sha256'],'evaluation_marker_sha256':row['marker_sha256']}
    stats={a:registered_statistics(v,binding['registration'],split='validation',groups=groups) for a,v in arms.items()}
    oracle_rows={}
    for method,digest in ev['oracles'].items():
        require(file_sha256(output/f'{method}.json')==digest,'oracle report changed')
        value=read_json(output/f'{method}.json')
        specs=[group_spec(r,'validation') for r in manifest['groups']]
        require(merge_shards(value['shards'],specs)==value['sequences'],'oracle shard drift')
        if method=='oracle_candidate_program':require(all(r['metrics'][k]==v for r in value['sequences'] for k,v in F_REQUIRED.items()),'F failed')
        oracle_rows[method]={'metrics':[r['metrics'] for r in value['sequences']],'shards':value['shards']}
    report={'schema_version':'cpmt-s5-corrected-confirmation-report-v1','binding':binding,'status':'complete',
        'arms':stats,'per_model':compact,'oracles':oracle_rows,'data_manifest_sha256':file_sha256(output/'data_manifest.json'),
        'evaluation_manifest_sha256':file_sha256(output/'evaluation_manifest.json'),'validation_consumption':trial,
        'candidate_coverage':manifest['candidate_coverage'],'teacher_reference_agreement':manifest['teacher_reference_agreement'],
        'invariant_violations':0,'models_evaluated':50,'paired_groups':200,'learned_decisions':400000,
        'validation_trial_consumed':True,'model_selection_performed':False,'formal_test_release':False,'test_access':False,
        'disposition':'review_S5_confirmation_under_registered_stop_rule_no_automatic_test_release',
        'architecture_selection_performed':False,'primary_architecture':ARCHES[0],
        'provenance':capture_run_provenance(ROOT,component='s5_summarize',entrypoint=Path(__file__))}
    immutable_json(output/'confirmation_report.json',report)
    print('S5_CONFIRMATION_SUMMARY_OK models=50 paired_groups=200 test_access=false',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=ORDER)
    parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    binding=binding_now();args.output.mkdir(parents=True,exist_ok=True);torch.set_num_threads(1)
    from m1_corrected_confirmation import current_binding, prerequisites, reserve_generation
    ops_binding=current_binding();require(ops_binding['science']==binding,'ops/science binding mismatch')
    prerequisites(args.output.parent,args.action,ops_binding)
    if args.action in ['generate','evaluate','summarize']:reserve_generation(args.output.parent,ops_binding)
    if args.action!='prepare':require(read_json(args.output/'binding.json')==binding,'stage source/runtime/input changed')
    globals()[args.action](args.output,binding)
    print(f'S5_CORRECTED_STEP_OK action={args.action} test_access=false',flush=True)


if __name__=='__main__':main()
