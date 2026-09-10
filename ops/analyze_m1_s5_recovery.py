"""只读汇总全部 S5 已导出序列，区分全图首错和已登记局部恢复。

输入是固定 confirmation 报告，输出是两架构、五方法、全部 seed/group
的描述计数。例如只在已登记 bounded 错误内计算恢复比例；它不是
错误分支候选覆盖审计，也不是方法间因果恢复效应。中文定义见
HARD_CONDITION_EXPERIMENT.md 的“S5 事后恢复分层”。不加载实验模块。
"""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'results/m1_v7_d055_s5_confirmation.json'
SOURCE_SHA = 'fa6426a96d0a1e8ca4cd7bb409ba9e6bbebf852d322a50cd47c6ea023e917e67'
OUTPUT = ROOT / 'results/m1_v7_d055_s5_recovery_analysis.json'
SEEDS = {7, 19, 31, 43, 59}
METHODS = {'cpmt_ctl_core', 'direct_classifier', 'direct_future_loss',
           'execute_current_only', 'future_no_execution'}
ARCHITECTURES = {'cross_candidate_set_transformer_v1', 'shared_candidate_mlp_v1'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def summarize(rows):
    counts = Counter()
    first_errors = Counter()
    burden = defaultdict(float)
    for row in rows:
        first = int(row['first_active_error_step'])
        delay = row['any_first_error_time_to_recovery']
        ever = first >= 0
        recovered = delay >= 0
        bounded = row['designed_bounded_pivot_error']
        outside = row['designed_pivot_error_out_of_scope']
        triggered = row['designed_revisit_triggered']
        success = row['designed_recovery_success']
        require(first == row['first_active_error_step'] and -1 <= first < 20,
                'invalid first error step')
        require(row['any_first_error_recovery_eligible'] == float(ever), 'eligibility mismatch')
        require(not recovered or (ever and delay >= 1 and first + delay < 20), 'recovery timing mismatch')
        require(row['any_first_error_recovered_within_window'] == float(recovered and delay <= 3),
                'first error window mismatch')
        require(all(row[k] in (0, 1) for k in ('designed_pivot_error',
                'designed_bounded_pivot_error', 'designed_pivot_error_out_of_scope',
                'designed_revisit_triggered', 'designed_recovery_success',
                'final_active_graph_correctness')), 'nonbinary flag')
        require(bounded + outside == row['designed_pivot_error'], 'pivot partition mismatch')
        require(0 <= success <= triggered <= bounded <= int(ever), 'bounded nesting mismatch')
        final_correct = row['final_active_graph_correctness'] == 1
        require(not ever or not final_correct or recovered, 'final recovery mismatch')
        require(ever or (final_correct and row['mean_active_graph_correctness'] == 1),
                'error-free sequence mismatch')
        category = ('never_wrong' if not ever else 'first_error_recovered'
                    if recovered else 'first_error_never_recovered')
        counts[category] += 1
        counts['sequences'] += 1
        counts['ever_wrong'] += int(ever)
        counts['first_step_wrong'] += int(first == 0)
        counts['final_wrong'] += int(not final_correct)
        counts['recovered_then_final_wrong'] += int(recovered and not final_correct)
        counts['first_error_recovered_within_3'] += int(recovered and delay <= 3)
        for name, value in (('pivot_wrong', bounded + outside), ('bounded_pivot_wrong', bounded),
                            ('pivot_wrong_outside_registered_scope', outside),
                            ('bounded_revisit_triggered', triggered), ('bounded_recovered', success)):
            counts[name] += int(value)
        counts['bounded_not_recovered'] += int(bounded - success)
        first_errors[str(first)] += 1
        value = row['open_fact_error_auc_per_100_decisions']
        require(value >= 0 and (ever or value == 0), 'burden mismatch')
        burden['total'] += value
        burden[category] += value
        if first == 0:
            burden['first_step_wrong_sequences'] += value
    require(sum(counts[k] for k in ('never_wrong', 'first_error_recovered',
            'first_error_never_recovered')) == len(rows), 'partition incomplete')
    return {'counts': dict(counts), 'first_active_error_step_histogram': dict(sorted(first_errors.items())),
            'burden_sum_by_sequence_stratum': dict(burden),
            'mean_burden': burden['total'] / len(rows),
            'bounded_recovery_fraction': counts['bounded_recovered'] / counts['bounded_pivot_wrong']
                if counts['bounded_pivot_wrong'] else None,
            'first_error_eventual_recovery_fraction': counts['first_error_recovered'] / counts['ever_wrong']
                if counts['ever_wrong'] else None}


def main():
    raw = SOURCE.read_bytes()
    require(sha(raw) == SOURCE_SHA, 'source report changed')
    source = json.loads(raw)
    require(source['engineering_pass'] and source['test_access'] is False
            and source['formal_test_release'] is False, 'source scope mismatch')
    models = list(source['report']['per_model'].values())
    require(len(models) == 50 and {(m['architecture'], m['method'], m['seed']) for m in models}
            == {(a, m, s) for a in ARCHITECTURES for m in METHODS for s in SEEDS}, 'model matrix mismatch')
    aggregate = defaultdict(list)
    per_model = []
    per_group = []
    for model in sorted(models, key=lambda m: (m['architecture'], m['method'], m['seed'])):
        rows = model['metrics']
        expected = {(f'rollout-pair:validation:{g:06d}', s) for g in range(4, 204) for s in (0, 1)}
        require(len(rows) == 400 and {(r['paired_group_id'], r['sibling_index']) for r in rows}
                == expected, 'sequence matrix mismatch')
        metadata = {k: model[k] for k in ('architecture', 'method', 'seed', 'model_sha256')}
        per_model.append({**metadata, **summarize(rows)})
        aggregate[model['architecture'], model['method']].extend(rows)
        grouped = defaultdict(list)
        for row in rows:
            grouped[row['paired_group_id']].append(row)
        for group, pair in sorted(grouped.items()):
            per_group.append({**metadata, 'paired_group_id': group, **summarize(pair)})
    arms = [{'architecture': a, 'method': m, **summarize(rows)}
            for (a, m), rows in sorted(aggregate.items())]
    output = {'schema_version': 'cpmt-s5-posthoc-recovery-summary-v1', 'posthoc': True,
              'source': {'path': SOURCE.relative_to(ROOT).as_posix(), 'sha256': sha(raw)},
              'analysis_script_sha256': sha(Path(__file__).read_bytes()),
              'metric_definition_sources': {p: sha((ROOT / p).read_bytes()) for p in
                  ('src/cpmt/m1_metrics.py', 'src/cpmt/m1_af_rollout.py')},
              'training_performed': False, 'model_execution_performed': False,
              'candidate_execution_performed': False, 'test_access': False,
              'formal_denominators_changed': False, 'inference_performed': False,
              'scope': 'All 200 validation paired groups, 50 models, 20000 sequence-seed rows. '
                  'Conditional recovery denominators differ across models; not a causal comparison. '
                  'Outside registered bounded scope does not imply absent repair candidates. '
                  'Burden strata sum whole-sequence burden, not burden caused by first error. '
                  'General post-error candidate availability and teacher error are not in source metrics.',
              'arms': arms, 'per_model': per_model, 'per_paired_group_seed': per_group}
    serialized = (json.dumps(output, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    if OUTPUT.exists():
        require(OUTPUT.read_bytes() == serialized, 'different existing analysis preserved')
    else:
        with OUTPUT.open('xb') as stream:
            stream.write(serialized)
    print('RECOVERY_ANALYSIS_OK models=50 sequence_seed_rows=20000 paired_groups=200 test_access=false')
    for arm in arms:
        print(arm['architecture'], arm['method'], json.dumps(arm['counts'], sort_keys=True),
              'mean_burden=', arm['mean_burden'])


if __name__ == '__main__':
    main()
