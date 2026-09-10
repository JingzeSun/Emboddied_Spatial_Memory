"""Diagnostic contracts on tiny synthetic programs; no validation data or models."""
import base64
from copy import deepcopy
import gzip
import importlib.util
import json
from pathlib import Path
import unittest

import numpy as np

SPEC = importlib.util.spec_from_file_location('s5_encoding', Path(__file__).parents[1] / 'analyze_m1_s5_encoding.py')
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class EncodingDiagnosticTests(unittest.TestCase):
    def observation(self):
        return {key: mod.stable_retrieval_feature(identifier)
                for key, identifier in zip(mod.QUERY_KINDS, ('u', 'edge', 'v'))}

    def program(self):
        return {'operations': [
            {'op_type': 'CLOSE_EDGE_VERSION', 'arguments': {'edge_id': 'edge'}},
            {'op_type': 'ADD_EDGE', 'arguments': {'edge': {'source': 'u', 'target': 'v'}}},
        ]}

    def test_swapped_roles_collide_under_old_aggregation_but_not_probe(self):
        a, b = self.program(), self.program()
        b['operations'][1]['arguments']['edge'] = {'source': 'v', 'target': 'u'}
        observation = self.observation()
        queries = {k: np.asarray(v) for k, v in observation.items()}
        np.testing.assert_allclose(mod._argument_features(a, queries), mod._argument_features(b, queries), atol=1e-14)
        self.assertNotEqual(mod.role_probe(a, observation), mod.role_probe(b, observation))

    def test_role_probe_does_not_read_merge_query_or_labels(self):
        observation = self.observation()
        before = mod.role_probe(self.program(), observation)
        observation.update(merge_queries=['not numeric'], reference_program_index=123)
        self.assertEqual(before, mod.role_probe(self.program(), observation))

    def test_role_id_set_preserved_with_versions_and_duplicate_operations(self):
        program = self.program()
        program['operations'].extend([
            {'op_type': 'RECORD_PROVENANCE', 'arguments': {'node_version_id': 'u@v3', 'provenance_ref': 'not-an-input'}},
            deepcopy(program['operations'][0]),
        ])
        roles = mod.role_ids(program)
        self.assertEqual(set().union(*map(set, roles.values())), {'u', 'v', 'edge'})

    def test_pair_score_is_invariant_to_node_and_query_permutation(self):
        program = {'operations': [{'op_type': 'CLOSE_NODE_VERSION', 'arguments': {'node_id': n}} for n in ('u', 'v')]}
        observation = {'merge_queries': [mod.stable_retrieval_feature(n) for n in ('u', 'v')]}
        score = mod.pair_score(program, observation)
        program['operations'].reverse()
        observation['merge_queries'].reverse()
        self.assertAlmostEqual(score, mod.pair_score(program, observation))

    def test_payload_corruption_rejected(self):
        raw = b'[]'
        blob = {'encoding': 'gzip+base64-json', 'payload': base64.b64encode(gzip.compress(raw)).decode(), 'sha256': mod.digest(raw), 'bytes': len(raw)}
        self.assertEqual(mod.unpack(blob), raw)
        blob['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'digest'):
            mod.unpack(blob)

    def test_c10_denominator_uses_previous_not_current_correctness(self):
        choices = [
            {'scenario_family': 'C10', 'registered_selection_correct': False, 'active_correct_after': 1, 'selected_template': 'BIND'},
            {'scenario_family': 'C08', 'active_correct_after': 0},
            {'scenario_family': 'C10', 'registered_selection_correct': False, 'active_correct_after': 1, 'selected_template': 'BIND'},
        ]
        raw = json.dumps([{'choices': choices}]).encode()
        blob = {'encoding': 'gzip+base64-json', 'payload': base64.b64encode(gzip.compress(raw)).decode(), 'sha256': mod.digest(raw), 'bytes': len(raw)}
        result = mod.c10_counts({'models': [{'method': 'cpmt_ctl_core', 'architecture': 'fixture', 'sequences': blob}]})
        self.assertEqual(result['fixture'], {'denominator': 1, 'disagreement': 1, 'selected_BIND': 1})


if __name__ == '__main__':
    unittest.main()
