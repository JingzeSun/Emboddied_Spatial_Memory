"""Small server integration tests for the new pilot, not efficacy results."""
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
import numpy as np
import torch
from cpmt.m1_af_method import run_af_method
from cpmt.m1_role_encoding import ENCODINGS, learning_arrays, rollout_metrics
from cpmt.m1_role_pilot import encoded_arrays, error_diagnostics, paired_differences, partition, split_arrays
from cpmt.m1_rollout import generate_m1_paired_rollout_split
from run_m1_role_pilot import config_for


class RolePilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        cls.plan = json.loads((ROOT / 'configs/m1_role_pilot.json').read_text(encoding='utf-8'))
        cls.hard = json.loads((ROOT / 'configs/m1_hard_condition_v7.json').read_text(encoding='utf-8'))
        _, cls.audits, _ = generate_m1_paired_rollout_split(cls.hard, 'train', paired_groups=1)
        cls.matrices = encoded_arrays(cls.hard, cls.audits, 0)

    def test_row_capture_targets_and_partition(self):
        for mode in ENCODINGS:
            expected = learning_arrays(self.hard, self.audits, config_for(self.plan, mode))
            for key in expected:
                np.testing.assert_array_equal(self.matrices[mode][key], expected[key])
        fit, dev = partition(self.plan)
        groups = np.repeat(sorted(fit + dev), 40)
        left, right = split_arrays({'group': groups, 'x': groups[:, None]}, self.plan)
        self.assertEqual(set(left['group']), set(fit))
        self.assertEqual(set(right['group']), set(dev))
        bad = deepcopy(self.audits)
        bad[0]['split'] = 'validation'
        with self.assertRaises(ValueError): encoded_arrays(self.hard, bad, 0)
        with self.assertRaises(ValueError): split_arrays({'group': groups[:-40]}, self.plan)

    def test_real_one_update_all_methods_callback_reload_and_matched_batches(self):
        batches = {}
        original_randint = torch.randint
        for mode in ENCODINGS:
            for method in self.plan['methods']:
                cfg = config_for(self.plan, mode)
                cfg.update(student_steps=1, scorer_steps=1, batch_size=4)
                sampled, called = [], []
                def sample(*args, **kwargs):
                    value = original_randint(*args, **kwargs)
                    sampled.append(value.clone())
                    return value
                def evaluate(model, audits, config):
                    called.append(config['online_encoding'])
                    stream = io.BytesIO()
                    torch.save({'config': config, 'state_dict': model.state_dict()}, stream)
                    stream.seek(0)
                    checkpoint = torch.load(stream, map_location='cpu', weights_only=True)
                    self.assertEqual(checkpoint['config'], config)
                    loaded = deepcopy(model)
                    loaded.load_state_dict(checkpoint['state_dict'], strict=True)
                    with torch.no_grad():
                        x = torch.as_tensor(self.matrices[mode]['x'])
                        torch.testing.assert_close(model(x), loaded(x), atol=0, rtol=0)
                    if mode == 'argument_roles_v1' and method == 'cpmt_ctl_core':
                        aggregate, rows = rollout_metrics(loaded, audits, config)
                        self.assertEqual(sum(len(r['choices']) for r in rows), 40)
                        for key in ['final_active_graph_correctness', 'final_open_memory_correctness',
                                    'open_fact_error_auc_per_100_decisions']:
                            self.assertIn(key, rows[0]['metrics'])
                        return aggregate, rows
                    return {'engineering_stub': True}, []
                with patch('torch.randint', side_effect=sample):
                    metrics, _, models = run_af_method(self.matrices[mode], self.matrices[mode], self.audits,
                                                      cfg, 7, method, causal_evaluator=evaluate)
                self.assertEqual(called, [mode])
                self.assertIn(method, models)
                self.assertTrue(metrics['student_parameters'] > 0)
                batches[mode, method] = sampled
        for method in self.plan['methods']:
            left, right = batches['pooled_padded_v1', method], batches['argument_roles_v1', method]
            self.assertEqual(len(left), len(right))
            self.assertGreater(len(left), 0)
            for a, b in zip(left, right): torch.testing.assert_close(a, b, atol=0, rtol=0)
        cfg = config_for(self.plan, 'pooled_v1')
        cfg.update(student_steps=1, scorer_steps=1, batch_size=4)
        with patch('cpmt.m1_af_method.causal_rollout_metrics', return_value=({}, [])) as legacy:
            run_af_method(self.matrices['pooled_v1'], self.matrices['pooled_v1'], self.audits,
                          cfg, 7, 'cpmt_ctl_core')
            legacy.assert_called_once()

    def test_onset_denominators_and_c10_are_separate(self):
        def choice(family, correct, label, ambiguity='identifiable', registered=True):
            return {'scenario_family': family, 'active_correct_after': float(correct),
                    'selected_template': label, 'selected_program_label': label,
                    'ambiguity': ambiguity, 'registered_selection_correct': registered}
        rows = [{'choices': [choice('C06', False, 'RELINK'), choice('C08', False, 'REPLACE'),
                             choice('C10', True, 'BIND', registered=False),
                             choice('C08', False, 'REPLACE')]}]
        result = error_diagnostics(rows)
        self.assertEqual(result['family_onsets']['C06']['identity_confusions'], 1)
        self.assertEqual(result['family_onsets']['C08']['eligible'], 1)
        self.assertEqual(result['c10_index_active_disagreement']['index_disagrees_active_correct'], 1)
        rows = [{'choices': [choice('C06', False, 'RELINK', 'epistemically_ambiguous_pivot')]}]
        self.assertEqual(error_diagnostics(rows)['family_onsets'], {})

    def test_paired_difference_sign_and_missing_group_rejection(self):
        keys = ['final_active_graph_correctness', 'final_open_memory_correctness',
                'final_graded_open_memory_correctness', 'open_fact_error_auc_per_100_decisions']
        left = [{'metrics': {'sequence_id': f's{s}', 'paired_group_id': 'rollout-pair:train:001001',
                             **{key: float(s) for key in keys}}} for s in (0, 1)]
        right = deepcopy(left)
        for row in right:
            for key in keys: row['metrics'][key] += 0.25
        differences = paired_differences(left, right, [1001])
        self.assertEqual(differences['mean'], {key: -0.25 for key in keys})
        with self.assertRaises(ValueError): paired_differences(left, right[:-1], [1001])
        with self.assertRaises(ValueError): paired_differences(left, right, [1001, 1004])


if __name__ == '__main__': unittest.main()
