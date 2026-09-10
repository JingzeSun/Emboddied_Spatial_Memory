"""Bounded read-only exporter checks; tiny synthetic worlds, no model execution."""
import base64
import copy
import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('availability_export',
    Path(__file__).resolve().parents[1] / 'export_m1_s5_availability.py')
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def fixture():
    sequences = []
    for sibling in (0, 1):
        choices = []
        for t in range(20):
            wrong = sibling == 0 and t < 3
            reachable = not (sibling == 0 and t == 1)
            choices.append({
                'step_index': t, 'scenario_family': 'C06' if t == 0 else 'C08',
                'ambiguity': 'sequence_context', 'selected_index': int(wrong), 'reference_index': 0,
                'selected_template': 'RELINK', 'registered_selection_correct': not wrong,
                'active_correct_after': float(not wrong), 'committed': True, 'commit_requested': True,
                'selected_legal': True, 'selected_static_preflight_pass': True,
                'executor_quarantined': False, 'revisit_opportunity': t == 3, 'revisit_triggered': t == 3,
                'base_graph_hash': f'{sibling}:{t}', 'post_graph_hash': f'{sibling}:{t+1}',
                'candidate_availability': {'constructed_candidate_count': 16, 'unavailable_slot_count': 0,
                    'selectable_legal_candidate_count': 15, 'executor_illegal_candidate_count': 1,
                    'static_rejected_constructed_count': 1, 'exact_reference_reachable': reachable}})
        metrics = {'paired_group_id': 'group', 'sibling_index': sibling, 'sequence_id': f'group:s{sibling}',
                   'first_active_error_step': 0 if sibling == 0 else -1,
                   'final_active_graph_correctness': 1.0, 'mean_active_graph_correctness': 0.85 if sibling == 0 else 1.0,
                   'any_first_error_recovery_eligible': float(sibling == 0),
                   'any_first_error_time_to_recovery': 3 if sibling == 0 else -1,
                   'any_first_error_recovered_within_window': float(sibling == 0),
                   'registered_selection_accuracy': 0.85 if sibling == 0 else 1.0}
        sequences.append({'choices': choices, 'metrics': metrics, 'candidate_availability': {
            'decisions': 20, 'decisions_without_exact_reference_reachable': int(sibling == 0)}})
    binding = {'model_key': 'model', 'audit': {'paired_group_id': 'group', 'sha256': 'audit', 'path': 'saved'},
               'test_access': False}
    result = {'binding': binding, 'sequences': sequences}
    marker = {'schema_version': 'cpmt-s5-unit-v1', 'binding': binding, 'files': {}}
    model = {'metrics': [s['metrics'] for s in sequences]}
    return marker, result, model


class AvailabilityTests(unittest.TestCase):
    def validate(self, marker, result, model):
        return mod.validate_unit(marker, result, {'test_access': False}, 'model', model, 'group')

    def test_error_opportunity_partitions_and_zero_denominator(self):
        rows = self.validate(*fixture())
        summary = mod.summarize(rows)
        cells = summary['decision_cells']
        self.assertEqual(sum(cells.values()), 40)
        self.assertEqual(cells['prior_correct_reachable_wrong'], 1)
        self.assertEqual(cells['prior_wrong_unreachable_wrong'], 1)
        self.assertEqual(cells['prior_wrong_reachable_wrong'], 1)
        self.assertEqual(cells['prior_wrong_reachable_correct'], 1)
        self.assertEqual(cells['prior_correct_reachable_correct'], 36)
        self.assertEqual(summary['post_error_complete_option_fraction'], 2/3)
        self.assertEqual(summary['observed_recovery_given_complete_option_fraction'], 0.5)
        self.assertIsNone(mod.summarize(rows[1:])['post_error_complete_option_fraction'])
        self.assertIsNone(mod.summarize(rows[1:])['observed_recovery_given_complete_option_fraction'])
        self.assertEqual(mod.combine([mod.summarize(rows[:1]), mod.summarize(rows[1:])]), summary)

    def test_missing_step_and_broken_state_chain_rejected(self):
        marker, result, model = fixture()
        broken = copy.deepcopy(result)
        broken['sequences'][0]['choices'].pop()
        with self.assertRaisesRegex(ValueError, 'horizon'):
            self.validate(marker, broken, model)
        result['sequences'][0]['choices'][2]['base_graph_hash'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'state chain'):
            self.validate(marker, result, model)

    def test_sibling_and_metric_mismatches_rejected(self):
        marker, result, model = fixture()
        broken = copy.deepcopy(result)
        broken['sequences'][1]['metrics']['sibling_index'] = 0
        with self.assertRaisesRegex(ValueError, 'sibling'):
            self.validate(marker, broken, model)
        result = copy.deepcopy(result)
        result['sequences'][0]['metrics']['sequence_id'] = 'another'
        with self.assertRaisesRegex(ValueError, 'metrics differ'):
            self.validate(marker, result, model)

    def test_reachability_contradiction_and_bad_counts_rejected(self):
        marker, result, model = fixture()
        result['sequences'][1]['choices'][0]['candidate_availability']['exact_reference_reachable'] = False
        with self.assertRaisesRegex(ValueError, 'correct committed world'):
            self.validate(marker, result, model)
        marker, result, model = fixture()
        result['sequences'][0]['choices'][0]['candidate_availability']['unavailable_slot_count'] = 1
        with self.assertRaisesRegex(ValueError, 'slot partition'):
            self.validate(marker, result, model)

    def test_timeline_and_aggregate_mismatch_rejected(self):
        marker, result, model = fixture()
        result['sequences'][0]['metrics']['first_active_error_step'] = 2
        with self.assertRaisesRegex(ValueError, 'timeline metric'):
            self.validate(marker, result, model)
        marker, result, model = fixture()
        result['sequences'][0]['candidate_availability']['decisions_without_exact_reference_reachable'] = 0
        with self.assertRaisesRegex(ValueError, 'aggregate mismatch'):
            self.validate(marker, result, model)

    def test_sealed_marker_result_and_science_bindings(self):
        marker, result, model = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            raw = mod.encode(result)
            marker['files']['result.json'] = mod.digest(raw)
            (path/'result.json').write_bytes(raw)
            marker_raw = mod.encode(marker)
            (path/'complete.json').write_bytes(marker_raw)
            spec = {'path': str(path), 'marker_sha256': mod.digest(marker_raw), 'paired_group_id': 'group'}
            rows, provenance = mod.read_unit(spec, {'test_access': False}, 'model', model)
            self.assertEqual(len(rows), 2)
            self.assertEqual(provenance['result_sha256'], mod.digest(raw))
            with self.assertRaisesRegex(ValueError, 'science binding'):
                mod.read_unit(spec, {'test_access': True}, 'model', model)
            with self.assertRaisesRegex(ValueError, 'model/group'):
                mod.read_unit(spec, {'test_access': False}, 'other', model)
            (path/'result.json').write_bytes(raw+b' ')
            with self.assertRaisesRegex(ValueError, 'result digest'):
                mod.read_unit(spec, {'test_access': False}, 'model', model)
            (path/'complete.json').write_bytes(marker_raw+b' ')
            with self.assertRaisesRegex(ValueError, 'completion marker'):
                mod.read_unit(spec, {'test_access': False}, 'model', model)

    def test_payload_integrity_write_once_and_partial_preservation(self):
        rows = self.validate(*fixture())
        blob = mod.pack(rows)
        self.assertEqual(mod.unpack(blob), rows)
        blob['sha256'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'digest'):
            mod.unpack(blob)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'out.json'
            self.assertEqual(mod.write_once(path, {'x': 1}), 'WRITTEN')
            self.assertEqual(mod.write_once(path, {'x': 1}), 'REUSED')
            with self.assertRaisesRegex(ValueError, 'preserved'):
                mod.write_once(path, {'x': 2})
            self.assertEqual(json.loads(path.read_bytes()), {'x': 1})
            other = Path(tmp)/'other.json'
            other.with_suffix('.json.partial').write_bytes(b'interrupted')
            with self.assertRaisesRegex(ValueError, 'incomplete output'):
                mod.write_once(other, {'x': 1})
            self.assertFalse(other.exists())

    def test_existing_group69_saved_choices_regression(self):
        # Only the eight already-exported trajectories; never original server data or a model.
        case = json.loads((mod.ROOT/'results/m1_v7_d055_s5_case_group69.json').read_bytes())
        summaries = []
        for unit in case['units']:
            def restored(blob):
                raw = gzip.decompress(base64.b64decode(blob['payload']))
                self.assertEqual(mod.digest(raw), blob['sha256'])
                return json.loads(raw)
            marker = restored(unit['complete_marker'])
            result = restored(unit['files']['result.json'])
            model = {'metrics': [s['metrics'] for s in result['sequences']]}
            rows = mod.validate_unit(marker, result, case['source_science_binding'],
                                     marker['binding']['model_key'], model, case['paired_group_id'])
            summaries.append(mod.summarize(rows))
        summary = mod.combine(summaries)
        self.assertEqual(sum(summary['decision_cells'].values()), 160)
        self.assertEqual(summary['decision_cells']['prior_wrong_unreachable_wrong'], 76)
        self.assertEqual(summary['decision_cells']['prior_wrong_reachable_correct'], 2)

    def test_failed_export_preserves_attempt_and_refuses_automatic_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, output, stage = root/'source.json', root/'out.json', root/'stage'
            source.write_bytes(b'{}')
            with patch.object(mod, 'SOURCE', source), patch.object(mod, 'SOURCE_SHA', mod.digest(b'{}')), \
                 patch.object(mod, 'OUTPUT', output), patch.object(mod, 'stage_path', return_value=stage), \
                 patch.object(mod, 'model_matrix', return_value={}), \
                 patch.object(mod, 'run_tests', return_value={'passed': True, 'tests_run': 1}), \
                 patch.object(mod, 'extract_all', side_effect=OSError('missing source shard')) as extract, \
                 patch.object(mod.sys, 'argv', ['exporter', 'export']):
                with self.assertRaisesRegex(OSError, 'missing source shard'):
                    mod.main()
                self.assertTrue((stage/'attempt.json').exists())
                self.assertEqual(json.loads((stage/'failure.json').read_bytes())['exit_code'], 1)
                self.assertFalse(output.exists())
                with self.assertRaisesRegex(ValueError, 'prior export attempt preserved'):
                    mod.main()
                self.assertEqual(extract.call_count, 1)


if __name__ == '__main__':
    unittest.main()
