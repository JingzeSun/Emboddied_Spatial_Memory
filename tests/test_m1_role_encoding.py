"""Train-only engineering fixtures; no optimizer, checkpoint or effect estimate."""
from copy import deepcopy
from functools import partial
import json
from pathlib import Path
import sys
import unittest

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from cpmt.dev_learning import OnlineModel
from cpmt.m1_af_rollout import (
    CANDIDATE_FEATURE_DIM, ONLINE_CONTEXT_DIM, online_feature_vector,
    resolve_af_smoke_config, rollout_learning_arrays_from_audits,
)
from cpmt.m1_rollout import generate_m1_paired_rollout_split, stable_retrieval_feature
from cpmt.m1_role_encoding import (
    ENCODINGS, ROLE_FEATURE_DIM, argument_role_ids, candidate_dim, configure,
    encode_online, learning_arrays, role_features, rollout_metrics,
)


class RoleEncodingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        cls.hard = json.loads((ROOT / 'configs/m1_hard_condition_v7.json').read_text(encoding='utf-8'))
        smoke = json.loads((ROOT / 'configs/m1_af_smoke.json').read_text(encoding='utf-8'))
        cls.config = resolve_af_smoke_config(cls.hard, smoke)
        _, cls.audits, _ = generate_m1_paired_rollout_split(cls.hard, 'train', paired_groups=1)
        cls.online = cls.audits[0]['steps'][0]['online']

    def test_all_modes_preserve_old_context_and_candidate_blocks(self):
        for audit in self.audits:
            for step in audit['steps']:
                old = online_feature_vector(step['online'])
                for mode in ENCODINGS:
                    encoded = encode_online(step['online'], encoding=mode)
                    np.testing.assert_array_equal(encoded[:ONLINE_CONTEXT_DIM], old[:ONLINE_CONTEXT_DIM])
                    blocks = encoded[ONLINE_CONTEXT_DIM:].reshape(16, candidate_dim(mode))
                    np.testing.assert_array_equal(blocks[:, :CANDIDATE_FEATURE_DIM], old[ONLINE_CONTEXT_DIM:].reshape(16, CANDIDATE_FEATURE_DIM))
                    if mode == 'pooled_padded_v1':
                        self.assertFalse(blocks[:, CANDIDATE_FEATURE_DIM:].any())

    def test_roles_read_no_extra_query_or_future_and_reject_outer_audit(self):
        before = encode_online(self.online, encoding='argument_roles_v1')
        changed = deepcopy(self.online)
        changed['proposal_observation']['merge_queries'] = ['poison']
        changed['proposal_observation']['reference_index'] = 'poison'
        np.testing.assert_array_equal(before, encode_online(changed, encoding='argument_roles_v1'))
        with self.assertRaisesRegex(ValueError, 'exactly'):
            encode_online(self.audits[0]['steps'][0], encoding='argument_roles_v1')

    def test_role_swap_and_no_identity_name_parsing(self):
        observation = {key: stable_retrieval_feature(value) for key, value in
                       zip(('node_query', 'edge_query', 'place_query'), ('opaque-a', 'opaque-edge', 'opaque-b'))}
        a = {'operations': [{'op_type': 'ADD_EDGE', 'arguments': {'edge': {'source': 'opaque-a', 'target': 'opaque-b'}}}]}
        b = deepcopy(a)
        b['operations'][0]['arguments']['edge'] = {'source': 'opaque-b', 'target': 'opaque-a'}
        self.assertFalse(np.array_equal(role_features(a, observation), role_features(b, observation)))
        self.assertEqual(argument_role_ids(a)['edge_source'], ['opaque-a'])
        self.assertEqual(argument_role_ids(a)['edge_target'], ['opaque-b'])

    def test_empty_roles_duplicate_ids_and_operation_permutation(self):
        observation = self.online['proposal_observation']
        program = {'operations': []}
        np.testing.assert_array_equal(role_features(program, observation), np.zeros(ROLE_FEATURE_DIM))
        program = {'operations': [
            {'op_type': 'CLOSE_NODE_VERSION', 'arguments': {'node_id': 'u'}},
            {'op_type': 'RECORD_PROVENANCE', 'arguments': {'node_version_id': 'u@v9'}},
        ]}
        old = role_features(program, observation)
        program['operations'].reverse()
        program['operations'].append(deepcopy(program['operations'][0]))
        np.testing.assert_array_equal(old, role_features(program, observation))
        self.assertEqual(argument_role_ids(program)['node_argument'], ['u'])

    def test_training_targets_masks_and_row_order_identical(self):
        baseline = rollout_learning_arrays_from_audits(self.hard, self.audits, future_hash_bins=self.config['future_hash_bins'])
        explicit = rollout_learning_arrays_from_audits(self.hard, self.audits, future_hash_bins=self.config['future_hash_bins'], feature_encoder=online_feature_vector)
        for key in baseline:
            np.testing.assert_array_equal(baseline[key], explicit[key])
        for mode in ('pooled_padded_v1', 'argument_roles_v1'):
            config = configure(self.config, encoding=mode)
            arrays = learning_arrays(self.hard, self.audits, config)
            self.assertEqual(set(arrays), set(baseline))
            for key in baseline:
                if key != 'x':
                    np.testing.assert_array_equal(arrays[key], baseline[key])
            new_blocks = arrays['x'][:, ONLINE_CONTEXT_DIM:].reshape(-1, 16, candidate_dim(mode))
            np.testing.assert_array_equal(new_blocks[:, :, :CANDIDATE_FEATURE_DIM], baseline['x'][:, ONLINE_CONTEXT_DIM:].reshape(-1, 16, CANDIDATE_FEATURE_DIM))

    def test_candidate_permutation_equivariance(self):
        changed = deepcopy(self.online)
        permutation = np.arange(16)[::-1]
        changed['candidate_programs'] = [changed['candidate_programs'][i] for i in permutation]
        a = encode_online(self.online, encoding='argument_roles_v1')[ONLINE_CONTEXT_DIM:].reshape(16, -1)
        b = encode_online(changed, encoding='argument_roles_v1')[ONLINE_CONTEXT_DIM:].reshape(16, -1)
        np.testing.assert_array_equal(b, a[permutation])

    def test_same_width_controls_have_identical_parameter_counts_and_can_ignore_roles(self):
        for architecture in ('shared_candidate_mlp_v1', 'cross_candidate_set_transformer_v1'):
            models = []
            for mode in ('pooled_padded_v1', 'argument_roles_v1'):
                torch.manual_seed(7)
                config = configure(self.config, encoding=mode)
                models.append(OnlineModel(config['online_feature_dim'], 16, 8, 3,
                                          num_candidates=16, candidate_dim=config['candidate_feature_dim'],
                                          architecture=architecture, attention_heads=4, set_attention_blocks=1, feedforward_dim=32))
            self.assertEqual(sum(p.numel() for p in models[0].parameters()), sum(p.numel() for p in models[1].parameters()))
            for a, b in zip(models[0].parameters(), models[1].parameters()):
                torch.testing.assert_close(a, b, rtol=0, atol=0)
            model = models[0]
            layer = model.candidate_embedding[0] if architecture == 'cross_candidate_set_transformer_v1' else model.candidate_scorer[0]
            with torch.no_grad():
                layer.weight[:, -ROLE_FEATURE_DIM:] = 0
                a = model(torch.from_numpy(encode_online(self.online, encoding='pooled_padded_v1')[None]))
                b = model(torch.from_numpy(encode_online(self.online, encoding='argument_roles_v1')[None]))
            torch.testing.assert_close(a, b, rtol=0, atol=0)

    def test_own_state_rollout_uses_expanded_encoding_every_step(self):
        class ShapeCheckedScores(torch.nn.Module):
            candidate_dim = candidate_dim('argument_roles_v1')
            context_dim = ONLINE_CONTEXT_DIM

            def __init__(self):
                super().__init__()
                self.inputs = []

            def forward(self, x):
                self.inputs.append(x.detach().cpu().numpy().copy())
                if x.shape[1] != self.context_dim + 16 * self.candidate_dim:
                    raise AssertionError('wrong online dimension')
                return torch.arange(16, device=x.device, dtype=x.dtype).expand(len(x), -1)

        model = ShapeCheckedScores()
        config = configure(dict(self.config, device='cpu', commit_probability=0.0, margin_threshold=0.0), encoding='argument_roles_v1')
        inputs = []
        def sink(materialized, choice, current):
            inputs.append(encode_online(materialized['online'], encoding='argument_roles_v1'))
        _, rows = rollout_metrics(model, self.audits, config, audit_sink=sink)
        self.assertEqual(len(model.inputs), 40)
        self.assertEqual(sum(len(row['choices']) for row in rows), 40)
        for observed, expected in zip(model.inputs, inputs):
            np.testing.assert_array_equal(observed[0], expected)

    def test_rejects_unknown_modes_dimension_mismatch_and_nontrain_audits(self):
        with self.assertRaises(ValueError):
            encode_online(self.online, encoding='unknown')
        with self.assertRaises(ValueError):
            configure(dict(self.config, test_access=True), encoding='argument_roles_v1')
        config = configure(self.config, encoding='argument_roles_v1')
        with self.assertRaisesRegex(ValueError, 'train-only'):
            learning_arrays(self.hard, [{'split': 'test'}], config)
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            learning_arrays(self.hard, self.audits, dict(config, candidate_feature_dim=33))
        with self.assertRaisesRegex(ValueError, 'model candidate width'):
            rollout_metrics(torch.nn.Identity(), self.audits, config)


if __name__ == '__main__':
    unittest.main()
