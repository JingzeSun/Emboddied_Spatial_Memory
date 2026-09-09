"""Light metadata, metric and artifact tests; no training or GPU allocation."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

import numpy as np
import torch
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
from m1_training_jobs import (validate_job, populations, ranking_metrics, dispatch,
    compare_artifacts, validate_scorer_dependency, CHECK_GROUPS, CHECKPOINTS, check_config)
from cpmt.m1_s5_confirmation import complete_unit
from cpmt.m1_s5_training import write_json
from run_m1_train_inner_dev_budget import _student_checkpoint_metrics


def job():
    return {'schema_version': 'cpmt-training-path-job-v1', 'authorization': 'fixed_train_only_engineering_check',
        'id': 'example', 'mode': 'budget', 'architecture': 'shared_candidate_mlp_v1', 'seed': 7,
        'method': 'cpmt_ctl_core', 'groups': CHECK_GROUPS, 'checkpoints': CHECKPOINTS,
        'learning_rate': 0.0006, 'auxiliary_weight': 1.0, 'device': 'cuda', 'torch_threads': 1,
        'scorer_dependency': None, 'validation_access': False, 'test_access': False, 'formal_budget_authorized': False,
        'arrays_digest': 'arrays', 'input_file_sha256': 'file', 'source_and_tests_sha256': 'source'}


class TestTrainingJobs(unittest.TestCase):
    def test_fixed_architecture_configs(self):
        for name in ['cross_candidate_set_transformer_v1', 'shared_candidate_mlp_v1']:
            config = check_config(name)
            self.assertEqual(config['architecture'], name)
            self.assertEqual(config['device'], 'cuda')
            self.assertEqual(config['cpu_threads'], 1)
            self.assertEqual(config['student_steps'], 30)

    def test_fixed_diagnostic_recipe(self):
        validate_job(job())
        for key, value in [('authorization', 'formal'), ('groups', list(range(1000))),
                           ('device', 'cpu'), ('torch_threads', 8), ('test_access', True)]:
            changed = job(); changed[key] = value
            with self.assertRaises(ValueError): validate_job(changed)

    def test_e_requires_its_scorer(self):
        value = job(); value['method'] = 'future_no_execution'
        with self.assertRaisesRegex(ValueError, 'dependency'): validate_job(value)
        value['scorer_dependency'] = {'path': 'scorer'}; validate_job(value)
        dep = job(); dep['method'] = 'outcome_scorer'
        validate_scorer_dependency(value, dep)
        dep['seed'] = 19
        with self.assertRaisesRegex(ValueError, 'seed'): validate_scorer_dependency(value, dep)

    def test_budget_keeps_complete_groups_and_refit_has_no_independent_holdout(self):
        arrays = {'group': np.repeat(np.arange(10), 40), 'y': np.zeros(400), 'labelled': np.arange(400) % 10 == 0}
        fit, inner, independent = populations(arrays, 'budget')
        self.assertTrue(independent)
        self.assertFalse(set(fit['group']) & set(inner['group']))
        self.assertEqual(len(fit['y'])+len(inner['y']), 400)
        self.assertTrue(all(np.sum(fit['group'] == g) == 40 for g in set(fit['group'])))
        full, alias, independent = populations(arrays, 'refit')
        self.assertIs(full, arrays); self.assertIs(alias, arrays); self.assertFalse(independent)

    def test_same_metric_matches_legacy_definition(self):
        logits = torch.tensor([[2., 0.], [2., 0.], [0., 2.], [0., 2.]])
        teacher = torch.tensor([[1., 0.], [0., 1.], [1., 0.], [0., 1.]])
        arrays = {'y': np.array([0, 1, 0, 1]), 'group': np.array([0, 0, 1, 1]),
                  'recovery': np.array([False, True, False, False]), 'candidate_static_preflight_pass': np.ones((4, 2), bool)}
        data = {'x': logits, 'y': torch.as_tensor(arrays['y']), 'penalties': torch.zeros(4, 2),
                'candidate_static_preflight_pass': torch.ones(4, 2, dtype=torch.bool)}
        legacy = _student_checkpoint_metrics(torch.nn.Identity(), data, teacher, ~arrays['recovery'], arrays['group'])
        current = ranking_metrics(logits.softmax(1).numpy(), teacher.numpy(), arrays)
        for key in ['reference_accuracy', 'reference_accuracy_by_group', 'teacher_argmax_agreement', 'teacher_reference_accuracy']:
            self.assertEqual(current[key], legacy[key])
        self.assertEqual(current['rows'], 3)

    def test_masked_or_nonfinite_predictions_rejected(self):
        arrays = {'y': np.array([0]), 'group': np.array([0]), 'recovery': np.array([False]),
                  'candidate_static_preflight_pass': np.array([[True, False]])}
        with self.assertRaises(ValueError): ranking_metrics(np.array([[.5, .5]]), np.array([[1., 0.]]), arrays)
        with self.assertRaises(ValueError): ranking_metrics(np.array([[float('nan'), 0.]]), np.array([[1., 0.]]), arrays)

    def test_dispatch_is_bounded_and_returns_canonical_order(self):
        lock = threading.Lock(); active = 0; peak = 0
        def execute(j):
            nonlocal active, peak
            with lock: active += 1; peak = max(peak, active)
            time.sleep(.005)
            with lock: active -= 1
            return j['id']
        result = dispatch([{'id': str(i)} for i in range(8, -1, -1)], 4, execute)
        self.assertEqual(list(result), sorted(result)); self.assertLessEqual(peak, 4); self.assertGreater(peak, 1)

    def test_duplicate_jobs_rejected_before_launch(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            dispatch([{'id': 'a'}, {'id': 'a'}], 4, lambda _: self.fail('must not launch'))

    def test_dispatch_failure_is_not_retried(self):
        calls = []
        def execute(j):
            calls.append(j['id']); raise ValueError('fixture failure')
        with self.assertRaisesRegex(ValueError, 'fixture failure'):
            dispatch([{'id': 'a'}], 1, execute)
        self.assertEqual(calls, ['a'])

    def artifact(self, path, *, delta=0., config=None):
        specification = job(); specification['checkpoints'] = [10]
        binding = {'job': specification, 'config': config or {'x': 1}, 'runtime': {'device': 'fixture'}}
        def write(staging):
            torch.save({'model_class': 'OnlineModel', 'model_kwargs': {'input_dim': 1},
                'fit_groups': [0], 'evaluation_groups': [1], 'state_dict': {'w': torch.tensor([1.+delta])},
                'teachers': {}, 'fit_probabilities': torch.tensor([[1., 0.]]),
                'evaluation_probabilities': torch.tensor([[1., 0.]])}, staging / 'checkpoint_10.pt')
            write_json(staging / 'result.json', {'checkpoints': [{'checkpoint': 10, 'score': 1}], 'parameter_signature': [['w', [1], True]]})
        complete_unit(path, binding, write)

    def test_exact_tensor_comparison_not_torch_archive_byte_comparison(self):
        with tempfile.TemporaryDirectory() as temp:
            a, b = Path(temp)/'a', Path(temp)/'b'
            self.artifact(a); self.artifact(b)
            self.assertTrue(compare_artifacts(a, b)['pass'])

    def test_tiny_tensor_difference_is_not_accepted_as_equivalent(self):
        with tempfile.TemporaryDirectory() as temp:
            a, b = Path(temp)/'a', Path(temp)/'b'
            self.artifact(a); self.artifact(b, delta=1e-6)
            self.assertFalse(compare_artifacts(a, b)['pass'])

    def test_comparison_rejects_different_config(self):
        with tempfile.TemporaryDirectory() as temp:
            a, b = Path(temp)/'a', Path(temp)/'b'
            self.artifact(a); self.artifact(b, config={'x': 2})
            with self.assertRaisesRegex(ValueError, 'config'): compare_artifacts(a, b)

    def test_changed_checkpoint_rejected_before_numerical_comparison(self):
        with tempfile.TemporaryDirectory() as temp:
            a, b = Path(temp)/'a', Path(temp)/'b'
            self.artifact(a); self.artifact(b)
            (b/'checkpoint_10.pt').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'hash'): compare_artifacts(a, b)


if __name__ == '__main__': unittest.main()
