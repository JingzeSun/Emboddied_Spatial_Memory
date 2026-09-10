"""事后只读分析：从已导出的候选执行结果计算错误事实与恢复机会。

输入是 group 69 的八条完整轨迹及参考审计，输出为逐步差异和候选可达性。
例如分别判断选错 REPLACE 和后续候选无法补回缺失节点；不把索引匹配
当作世界修复，不执行模型、候选生成或 executor，不搜索其他反事实路径。
"""
import base64
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from cpmt.m1_metrics import _active_graph_state, _active_record_counters, _open_fact_tokens

SOURCE = ROOT / 'results/m1_v7_d055_s5_case_group69.json'
OUTPUT = ROOT / 'results/m1_v7_d055_s5_case_group69_analysis.json'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def unpack(blob):
    raw = gzip.decompress(base64.b64decode(blob['payload']))
    assert len(raw) == blob['bytes'] and sha(raw) == blob['sha256']
    return raw


def difference(graph, reference):
    nodes, edges = _active_record_counters(graph)
    rn, re = _active_record_counters(reference)
    return {'extra_nodes': [json.loads(x) for x in (nodes-rn).elements()],
            'missing_nodes': [json.loads(x) for x in (rn-nodes).elements()],
            'extra_edges': [json.loads(x) for x in (edges-re).elements()],
            'missing_edges': [json.loads(x) for x in (re-edges).elements()]}


def main():
    raw = SOURCE.read_bytes()
    export = json.loads(raw)
    original_report = ROOT / export['source_report']['path']
    assert sha(original_report.read_bytes()) == export['source_report']['sha256']
    reference_blob = next(iter(export['reference_audits'].values()))
    audit_raw = unpack(reference_blob['file'])
    assert sha(audit_raw) == reference_blob['source']['sha256']
    pair = json.loads(gzip.decompress(audit_raw))
    pair = pair['audits'] if isinstance(pair, dict) else pair
    audits = {a['sibling_index']: a for a in pair}
    summaries = []
    first_inputs = {0: [], 1: []}
    for unit in export['units']:
        marker_raw = unpack(unit['complete_marker'])
        assert sha(marker_raw) == unit['source']['marker_sha256']
        marker = json.loads(marker_raw)
        for name, blob in unit['files'].items():
            assert blob['sha256'] == marker['files'][name]
        result = json.loads(unpack(unit['files']['result.json']))
        records = [json.loads(line) for line in gzip.decompress(unpack(unit['files']['execution.jsonl.gz'])).splitlines()]
        assert len(records) == 40
        for sibling in (0, 1):
            audit = audits[sibling]
            rows = sorted([r for r in records if r['materialized']['audit_sibling_index'] == sibling],
                          key=lambda r: r['choice']['step_index'])
            assert [r['choice']['step_index'] for r in rows] == list(range(20))
            assert [r['materialized']['audit_sequence_id'] for r in rows] == [audit['sequence_id']] * 20
            saved = next(r for r in result['sequences'] if r['metrics']['sibling_index'] == sibling)
            assert [r['choice'] for r in rows] == saved['choices']
            first_inputs[sibling].append(rows[0]['materialized']['online'])
            target_node = audit['steps'][0]['event_spec']['reference_spec']['new_node_id']
            first_ref = audit['steps'][0]
            first_graph = first_ref['executed_candidates'][first_ref['reference_program_index']]['post_graph']
            initial_extra = _open_fact_tokens(rows[0]['current']) - _open_fact_tokens(first_graph)
            initial_missing = _open_fact_tokens(first_graph) - _open_fact_tokens(rows[0]['current'])
            steps = []
            for row, reference in zip(rows, audit['steps']):
                choice, mat = row['choice'], row['materialized']
                graph = reference['executed_candidates'][reference['reference_program_index']]['post_graph']
                assert graph['graph_hash'] == reference['reference_post_graph_hash']
                reference_facts = _open_fact_tokens(graph)
                current_facts = _open_fact_tokens(row['current'])
                base = mat['online']['prior_world']
                assert base['graph_hash'] == choice['base_graph_hash']
                assert row['current']['graph_hash'] == choice['post_graph_hash']
                correct = _active_graph_state(row['current']) == _active_graph_state(graph)
                assert float(correct) == choice['active_correct_after']
                candidates = []
                assert len(mat['executed_candidates']) == len(choice['probabilities']) == 16
                for candidate, probability in zip(mat['executed_candidates'], choice['probabilities']):
                    selectable = candidate['legal'] and candidate['static_preflight_pass']
                    post = candidate['post_graph']
                    item = {'index': candidate['candidate_index'], 'template': candidate['template'],
                            'probability': probability, 'selectable': selectable}
                    if selectable:
                        facts = _open_fact_tokens(post)
                        item.update(exact=_active_graph_state(post) == _active_graph_state(graph),
                                    fact_error_count=len(facts ^ reference_facts),
                                    contains_original_replacement_node=any(n['node_id'] == target_node and n['valid_to'] is None for n in post['nodes']),
                                    initial_extra_remaining_count=len(initial_extra & facts),
                                    initial_missing_remaining_count=len(initial_missing - facts))
                    candidates.append(item)
                reachable = [c['index'] for c in candidates if c['selectable'] and c['exact']]
                assert bool(reachable) == choice['candidate_availability']['exact_reference_reachable']
                steps.append({'step_index': choice['step_index'], 'family': choice['scenario_family'],
                              'selected_index': choice['selected_index'], 'selected_template': choice['selected_template'],
                              'reference_index_on_reference_history': choice['reference_index'],
                              'registered_selection_correct': choice['registered_selection_correct'],
                              'active_world_correct': correct, 'exact_reachable_indices': reachable,
                              'extra_facts': sorted(current_facts-reference_facts),
                              'missing_facts': sorted(reference_facts-current_facts),
                              'initial_extra_remaining': sorted(initial_extra & current_facts),
                              'initial_missing_remaining': sorted(initial_missing-current_facts),
                              'active_state_difference': difference(row['current'], graph),
                              'candidates': candidates})
            burden = 100 * sum(len(s['extra_facts'])+len(s['missing_facts']) for s in steps) / 20
            assert burden == saved['metrics']['open_fact_error_auc_per_100_decisions']
            assert float(steps[-1]['active_world_correct']) == saved['metrics']['final_active_graph_correctness']
            summaries.append({'seed': unit['seed'], 'method': unit['method'], 'sibling': sibling,
                              'metrics': saved['metrics'], 'burden_recomputed': burden,
                              'registered_pivot_step': audit['ambiguity_pivot_step'],
                              'registered_recovery_step': audit['recovery_revisit_step'],
                              'first_step_teacher_posterior': first_ref['teacher_posterior'],
                              'first_step_teacher_winner_index': first_ref['teacher_winner_index'],
                              'first_step_candidate_energies': first_ref['candidate_energies'],
                              'original_replacement_node_id': target_node, 'steps': steps})
    assert all(all(item == values[0] for item in values) for values in first_inputs.values())
    output = {'schema_version': 'cpmt-s5-posthoc-case-analysis-v1',
              'source': {'path': SOURCE.relative_to(ROOT).as_posix(), 'sha256': sha(raw)},
              'analysis_script_sha256': sha(Path(__file__).read_bytes()),
              'metric_source_sha256': sha((ROOT/'src/cpmt/m1_metrics.py').read_bytes()),
              'first_online_input_equal_across_four_models_per_sibling': True,
              'posthoc': True, 'training_performed': False, 'model_execution_performed': False,
              'candidate_execution_performed': False, 'test_access': False,
              'scope': 'Stored candidates on actual trajectories only; no search of alternative multistep paths. Teacher values apply to stored reference history.',
              'sequences': summaries}
    serialized = (json.dumps(output, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()
    if OUTPUT.exists():
        assert OUTPUT.read_bytes() == serialized, 'different analysis exists; preserved'
    else:
        with OUTPUT.open('xb') as stream:
            stream.write(serialized)
    print(f'CASE_ANALYSIS_OK sequences={len(summaries)} decisions=160 candidate_slots=2560 output={OUTPUT}')
    for s in summaries:
        first=s['steps'][0]
        print(s['seed'], s['method'], s['sibling'], 'first='+first['selected_template'],
              'unreachable='+str(sum(not row['exact_reachable_indices'] for row in s['steps'])),
              'burden='+str(s['burden_recomputed']))


if __name__ == '__main__':
    main()
