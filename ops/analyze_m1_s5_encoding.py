"""只读编码诊断；运行方式：python ops/analyze_m1_s5_encoding.py [--verify]。

输入为已验收的 S5 全体 choices 与 group 69 完整案例，输出为带来源摘要的 JSON。
角色分离仅为 proposed 探针：将同一批已有参数按操作字段分组，分别与原有三条
query 匹配。例如单独保留 ADD_EDGE 的 source/target，检查混合聚合丢失的信息；
它不接入学生、不新增 merge_queries 输入，不等于已证实的架构改善。
MERGE 配对分只用于审计答案捷径；C10 用真实保存的分支检查证据绑定，并在固定
下一步 online 上替换 prior_world 测量编码差异，不运行候选生成或反事实轨迹。
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter, defaultdict
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from cpmt.m1_af_rollout import (
    CANDIDATE_FEATURE_DIM, ONLINE_CONTEXT_DIM, QUERY_KINDS,
    _argument_features, _program_label, online_feature_vector,
)
from cpmt.m1_metrics import _active_graph_state, _open_memory_state
from cpmt.m1_rollout import ARGUMENT_ID_KEYS, candidate_argument_ids, stable_retrieval_feature

AVAILABILITY = ROOT / 'results/m1_v7_d055_s5_availability.json'
CASE = ROOT / 'results/m1_v7_d055_s5_case_group69.json'
OUTPUT = ROOT / 'results/m1_v7_d055_s5_encoding_analysis.json'
EXPECTED_AVAILABILITY = '4fa2d663e6f84d5b3b5913fd2921f384d73cd92388f997c24dae4ae3c87a28d3'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def unpack(blob):
    require(blob['encoding'] in ('gzip+base64', 'gzip+base64-json'), 'unknown encoding')
    raw = gzip.decompress(base64.b64decode(blob['payload'], validate=True))
    require(len(raw) == blob['bytes'] and digest(raw) == blob['sha256'], 'payload digest mismatch')
    return raw


def role_ids(program):
    """Retain operation/field roles, using exactly the original encoder's IDs."""
    roles = defaultdict(set)
    for operation in program['operations']:
        op, args = operation['op_type'], operation['arguments']
        for key in ARGUMENT_ID_KEYS:
            if isinstance(args.get(key), str):
                roles[f'{op}.{key}'].add(args[key].split('@')[0])
        if isinstance(args.get('edge'), dict):
            for key in ('source', 'target'):
                roles[f'{op}.edge.{key}'].add(str(args['edge'][key]))
        if isinstance(args.get('node'), dict):
            roles[f'{op}.node.node_id'].add(str(args['node']['node_id']))
    require(set().union(set(), *roles.values()) == set(candidate_argument_ids(program)),
            'role probe changed the source identifier set')
    return {key: sorted(value) for key, value in sorted(roles.items())}


def role_probe(program, observation):
    result = {}
    for role, identifiers in role_ids(program).items():
        vectors = np.asarray([stable_retrieval_feature(x) for x in identifiers])
        result[role] = {'count': len(identifiers), 'matches': {}}
        for query in QUERY_KINDS:
            values = vectors @ np.asarray(observation[query])
            result[role]['matches'][query] = [float(values.max()), float(values.mean())]
    return result


def c10_counts(export):
    counts = defaultdict(Counter)
    for model in export['models']:
        if model['method'] != 'cpmt_ctl_core':
            continue
        for sequence in json.loads(unpack(model['sequences'])):
            previous_correct = True
            for choice in sequence['choices']:
                if previous_correct and choice['scenario_family'] == 'C10':
                    counter = counts[model['architecture']]
                    counter['denominator'] += 1
                    if not choice['registered_selection_correct'] and choice['active_correct_after'] == 1:
                        counter['disagreement'] += 1
                        counter['selected_' + choice['selected_template']] += 1
                previous_correct = choice['active_correct_after'] == 1
    return {key: dict(value) for key, value in sorted(counts.items())}


def pair_score(program, observation):
    targets = sorted({op['arguments']['node_id'] for op in program['operations']
                      if op['op_type'] == 'CLOSE_NODE_VERSION'})
    require(len(targets) == 2, 'MERGE probe expects two closed source nodes')
    u, v = [np.asarray(stable_retrieval_feature(x)) for x in targets]
    a, b = [np.asarray(x) for x in observation['merge_queries']]
    return float(max(u @ a + v @ b, u @ b + v @ a))


def candidate_probe(online, executions, reference_index, selected_index):
    features = online_feature_vector(online)[ONLINE_CONTEXT_DIM:].reshape(-1, CANDIDATE_FEATURE_DIM)
    roles = [role_probe(p, online['proposal_observation']) for p in online['candidate_programs']]
    eligible = [i for i, e in enumerate(executions) if e['legal'] and e['static_preflight_pass']]
    collisions = []
    for offset, i in enumerate(eligible):
        for j in eligible[offset + 1:]:
            if np.array_equal(features[i], features[j]):
                collisions.append({'indices': [i, j], 'role_probe_distinguishes': roles[i] != roles[j],
                                   'active_equal': _active_graph_state(executions[i]['post_graph']) == _active_graph_state(executions[j]['post_graph'])})
    return {'selectable_count': len(eligible), 'candidate_feature_collisions': collisions,
            'selected_reference_feature_linf': float(np.max(np.abs(features[selected_index] - features[reference_index]))),
            'selected_reference_argument_linf': float(np.max(np.abs(features[selected_index, -7:] - features[reference_index, -7:]))),
            'selected_roles': roles[selected_index], 'reference_roles': roles[reference_index]}


def fixed_online_world_probe(online, left, right):
    """Pure feature intervention: candidate programs/observations remain fixed."""
    vectors = []
    for graph in (left, right):
        fixed = deepcopy(online)
        fixed['prior_world'] = graph
        vectors.append(online_feature_vector(fixed))
    delta = vectors[1] - vectors[0]
    without_log = delta.copy()
    # NODE_TYPES (5), LIFECYCLES (5), open/closed edges, then transaction count.
    without_log[12] = 0
    return {'changed_feature_indices': np.flatnonzero(delta).tolist(),
            'feature_deltas': delta[delta != 0].tolist(),
            'equal_after_removing_transaction_count': not bool(np.any(without_log))}


def analyze(availability_path=AVAILABILITY, case_path=CASE):
    availability_raw, case_raw = availability_path.read_bytes(), case_path.read_bytes()
    require(digest(availability_raw) == EXPECTED_AVAILABILITY, 'unexpected S5 availability source')
    availability, case = json.loads(availability_raw), json.loads(case_raw)
    require(availability['test_access'] is False and case['test_access'] is False, 'test access forbidden')
    report_path = ROOT / case['source_report']['path']
    require(digest(report_path.read_bytes()) == case['source_report']['sha256'] == availability['source']['sha256'], 'confirmation digest mismatch')
    audits = {}
    for item in case['reference_audits'].values():
        raw = unpack(item['file'])
        require(digest(raw) == item['source']['sha256'], 'audit source mismatch')
        pair = json.loads(gzip.decompress(raw))
        for audit in pair:
            require(audit['split'] == 'validation', 'only the existing S5 validation case is allowed')
            audits[audit['sibling_index']] = audit
    c10, decisions, merges = [], [], []
    for audit in audits.values():
        for step in audit['steps']:
            if step['scenario_family'] != 'C05':
                continue
            online = step['online']
            options = []
            queries = {k: np.asarray(online['proposal_observation'][k]) for k in QUERY_KINDS}
            for i, program in enumerate(online['candidate_programs']):
                execution = step['executed_candidates'][i]
                if _program_label(program) == 'MERGE' and execution['legal'] and execution['static_preflight_pass']:
                    options.append({'index': i, 'is_reference': i == step['reference_program_index'],
                                    'pair_score_audit_only': pair_score(program, online['proposal_observation']),
                                    'existing_argument_features': _argument_features(program, queries)})
            merges.append({'sibling_index': audit['sibling_index'], 'step_index': step['step_index'], 'options': options})
    for unit in case['units']:
        marker_raw = unpack(unit['complete_marker'])
        require(digest(marker_raw) == unit['source']['marker_sha256'], 'marker mismatch')
        marker = json.loads(marker_raw)
        for name, blob in unit['files'].items():
            require(blob['sha256'] == marker['files'][name], 'unit file binding mismatch')
        result = json.loads(unpack(unit['files']['result.json']))
        records = [json.loads(line) for line in gzip.decompress(unpack(unit['files']['execution.jsonl.gz'])).splitlines()]
        for sibling, audit in sorted(audits.items()):
            rows = sorted((r for r in records if r['materialized']['audit_sibling_index'] == sibling), key=lambda r: r['choice']['step_index'])
            require([r['choice']['step_index'] for r in rows] == list(range(20)), 'incomplete sequence')
            saved = next(s for s in result['sequences'] if s['metrics']['sibling_index'] == sibling)
            require([r['choice'] for r in rows] == saved['choices'], 'choice mismatch')
            for t, row in enumerate(rows):
                choice, materialized = row['choice'], row['materialized']
                online, executions = materialized['online'], materialized['executed_candidates']
                require(materialized['audit_sequence_id'] == audit['sequence_id'], 'sequence binding mismatch')
                require(online['prior_world']['graph_hash'] == choice['base_graph_hash'], 'base mismatch')
                require(row['current'] == executions[choice['selected_index']]['post_graph'], 'committed graph mismatch')
                if t:
                    require(online['prior_world'] == rows[t-1]['current'], 'world chain mismatch')
                identity = {'method': unit['method'], 'seed': unit['seed'], 'sibling_index': sibling, 'step_index': t}
                probe = candidate_probe(online, executions, choice['reference_index'], choice['selected_index'])
                probe.update(identity, family=choice['scenario_family'], selected_index=choice['selected_index'], reference_index=choice['reference_index'],
                             selected_template=choice['selected_template'], registered_selection_correct=choice['registered_selection_correct'])
                decisions.append(probe)
                if choice['scenario_family'] != 'C10':
                    continue
                a, b = [executions[choice[key]] for key in ('reference_index', 'selected_index')]
                ga, gb = a['post_graph'], b['post_graph']
                node_changes = []
                require(len(ga['nodes']) == len(gb['nodes']), 'C10 node cardinality changed')
                for na, nb in zip(ga['nodes'], gb['nodes']):
                    if na != nb:
                        node_changes.append({'node_id': na['node_id'], 'fields': {key: [na.get(key), nb.get(key)] for key in sorted(na.keys() | nb.keys()) if na.get(key) != nb.get(key)}})
                c10.append({**identity, 'reference_template': a['template'], 'selected_template': b['template'],
                            'active_equal': _active_graph_state(ga) == _active_graph_state(gb),
                            'open_memory_equal': _open_memory_state(ga) == _open_memory_state(gb),
                            'edges_equal': ga['edges'] == gb['edges'], 'node_changes': node_changes,
                            'transaction_counts': [len(g['transaction_log']) for g in (ga, gb)],
                            'fixed_next_online_probe': fixed_online_world_probe(rows[t+1]['materialized']['online'], ga, gb)})
    source_paths = [Path(__file__), ROOT / 'ops/tests/test_s5_encoding.py', ROOT / 'src/cpmt/m1_af_rollout.py', ROOT / 'src/cpmt/m1_rollout.py', ROOT / 'src/cpmt/m1_metrics.py']
    return {'schema_version': 'cpmt-s5-encoding-audit-v1', 'posthoc': True, 'training_performed': False,
            'model_execution_performed': False, 'candidate_execution_performed': False, 'test_access': False,
            'source': {availability_path.name: digest(availability_raw), case_path.name: digest(case_raw), report_path.name: case['source_report']['sha256']},
            'code_binding': {p.relative_to(ROOT).as_posix(): digest(p.read_bytes().replace(b'\r\n', b'\n')) for p in source_paths},
            'scope': {'full_choice_c10': 'all A seeds/groups, conditioned on prior active correctness',
                      'full_world_analysis': 'one selected paired group 69, two siblings, A/C seeds 7/19, 160 decisions',
                      'role_probe': 'proposed diagnostic only; original ID set and original three queries',
                      'world_intervention': 'fixed next online feature probe, not regenerated candidates or policy rollout',
                      'limitations': ['Not an independent confirmation sample', 'No accuracy gain estimated', 'No global query shortcut rate estimated', 'Reference index on an off-reference base is not guaranteed to name a correct world']},
            'c10_counts': c10_counts(availability), 'c10_worlds': c10, 'c05_reference_query_probes': merges,
            'summary': {'decisions': len(decisions), 'c10_world_pairs': len(c10),
                        'candidate_collision_pairs': sum(len(d['candidate_feature_collisions']) for d in decisions),
                        'index_disagreements': sum(not d['registered_selection_correct'] for d in decisions),
                        'index_disagreements_with_identical_candidate_features': sum(not d['registered_selection_correct'] and d['selected_reference_feature_linf'] == 0 for d in decisions)},
            'decisions': decisions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true', help='recompute and compare the existing report without writing')
    args = parser.parse_args()
    report = analyze()
    if OUTPUT.exists():
        require(json.loads(OUTPUT.read_text(encoding='utf-8')) == report, 'existing report differs; preserve it and investigate')
        action = 'verified/reused'
    else:
        require(not args.verify, 'report missing')
        with OUTPUT.open('x', encoding='utf-8', newline='\n') as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write('\n')
        action = 'written'
    print(json.dumps({'action': action, 'summary': report['summary'], 'c10_counts': report['c10_counts']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
