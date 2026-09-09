"""Small metadata/statistical checks; no generated worlds or model training."""
from copy import deepcopy
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
from run_m1_corrected_probe import (assess, registration, contracts, fixed_groups, check_rows,
                                    F_REQUIRED, METRICS, SEEDS)


def rows():
    result = []
    for group in range(201):
        for method, seeds in [('A', SEEDS), ('C', SEEDS), ('E', SEEDS), ('F', [None])]:
            for seed in seeds:
                for sibling in (0, 1):
                    metrics = {**F_REQUIRED, 'sibling_index': sibling, 'final_active_reference_record_count': 10}
                    if method != 'F':
                        delta = 0 if method == 'A' else (0.1 if method == 'C' else 0.2) * (1 + group % 2)
                        for k in METRICS[:2]: metrics[k] = 0.9 - delta
                        metrics[METRICS[2]] = 2 + delta * 100
                        metrics['final_graded_active_world_correctness'] = 0.9 - delta
                    result.append({'paired_group_id': f'rollout-pair:train:{group:06d}',
                                   'method': method, 'seed': seed, 'metrics': metrics})
    return result


class TestCorrectedProbe(unittest.TestCase):
    def test_fixed_contracts_and_partition(self):
        _, rebuild, binding = contracts()
        self.assertEqual(len(fixed_groups()), 201)
        self.assertEqual(binding['config']['student_steps'], 3000)
        self.assertEqual(binding['config']['learning_rate'], 0.0006)
        self.assertFalse(rebuild['endpoints']['endpoint_reselection'])

    def test_floor_and_six_cell_maximum(self):
        value = assess(rows())
        self.assertEqual(value['selected_metric'], METRICS[0])
        self.assertEqual(value['selected_test_groups'], 1350)
        self.assertFalse(value['endpoint_reselection'])

    def test_n_can_increase_using_fixed_formula(self):
        data = rows()
        for row in data:
            g = int(row['paired_group_id'].split(':')[-1])
            if row['method'] in ['A', 'E']:
                row['metrics'][METRICS[0]] = float(g % 2 if row['method'] == 'A' else 1-g % 2)
        value = assess(data)
        sd = value['by_metric'][METRICS[0]]['A_vs_E']['paired_group_standard_deviation']
        expected = max(1350, math.ceil((((1.959963984540054+0.8416212335729143)*sd/0.03)**2)/10)*10)
        self.assertGreater(value['selected_test_groups'], 1350)
        self.assertEqual(value['selected_test_groups'], expected)

    def test_no_graded_fallback(self):
        data = rows()
        for r in data:
            if r['method'] != 'F': r['metrics'][METRICS[0]] = 0.8
        value = assess(data)
        self.assertTrue(value['by_metric']['final_graded_active_world_correctness']['A_vs_C']['nondegenerate'])
        self.assertIsNone(value['selected_test_groups'])
        self.assertIsNone(value['selected_metric'])

    def test_oracle_failure_stops(self):
        data = rows()
        next(r for r in data if r['method'] == 'F')['metrics'][METRICS[2]] = 1
        self.assertEqual(assess(data)['disposition'], 'abort_oracle_integrity_failure')

    def test_missing_seed_row_rejected(self):
        with self.assertRaisesRegex(ValueError, 'matrix'): assess(rows()[1:])

    def test_duplicate_sibling_rejected(self):
        data = rows(); data[1] = deepcopy(data[0])
        with self.assertRaisesRegex(ValueError, 'matrix'): assess(data)

    def test_nonfinite_row_rejected(self):
        data = rows(); data[0]['metrics'][METRICS[0]] = float('nan')
        with self.assertRaisesRegex(ValueError, 'nonfinite'): assess(data)

    def test_registration_is_sealed_and_recomputed(self):
        _, rebuild, binding = contracts()
        data = rows()
        report = {'endpoint_rows': data, 'endpoint_assessment': assess(data), 'binding': binding}
        value = registration(report, rebuild)
        self.assertFalse(value['test_access'])
        self.assertFalse(value['formal_test_release'])
        self.assertEqual(value['evaluation_plan']['paired_groups']['test'], 1350)
        report['endpoint_assessment']['selected_test_groups'] = 1340
        with self.assertRaisesRegex(ValueError, 'assessment'): registration(report, rebuild)

    def test_failed_assessment_has_no_registration(self):
        _, rebuild, binding = contracts()
        data = rows()
        for r in data:
            if r['method'] != 'F': r['metrics'][METRICS[0]] = 0.8
        self.assertIsNone(registration({'endpoint_rows': data, 'endpoint_assessment': assess(data), 'binding': binding}, rebuild))

    def test_broken_chain_rejected(self):
        data = [{'metrics': {**F_REQUIRED, 'paired_group_id': 'rollout-pair:train:000000', 'sibling_index': s},
            'choices': [{'step_index': i, 'base_graph_hash': str(i), 'post_graph_hash': str(i+1),
                         'selected_static_preflight_pass': True} for i in range(20)]} for s in (0, 1)]
        check_rows(data, [0])
        data[0]['choices'][5]['post_graph_hash'] = 'broken'
        with self.assertRaisesRegex(ValueError, 'chain'): check_rows(data, [0])


if __name__ == '__main__': unittest.main()
