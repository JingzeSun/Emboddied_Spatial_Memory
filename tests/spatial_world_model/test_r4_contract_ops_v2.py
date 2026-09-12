"""Server-only checks of v2 immutable receipt/export boundaries; no simulation."""
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ops/spatial_history'))
ops = importlib.import_module('r4_contract_check_v2')


class R4ContractOpsV2Tests(unittest.TestCase):
    def test_config_dimensions_match_modules_and_old_run_path_is_rejected(self):
        from spatial_world_model import r4_query_v2, r4_scoring_v2
        config = ops.configuration()
        self.assertEqual(config['candidate_count'], r4_scoring_v2.CANDIDATES)
        self.assertEqual(config['native_resolution_hw'], [r4_query_v2.RESOLUTION] * 2)
        self.assertEqual(config['query_schema'], r4_query_v2.VERSION)
        self.assertEqual(config['prediction_schema'], r4_query_v2.PREDICTION_VERSION)
        self.assertEqual(config['scoring_schema'], r4_scoring_v2.VERSION)
        with self.assertRaises(ValueError):
            ops.stage_path(Path('/root/autodl-tmp/spatial-history/sh04-r4-contract-v1'))

    def test_failed_export_preserves_evidence_and_never_overwrites_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / 'stage'
            directory.mkdir()
            report = Path(temporary) / 'report.json'
            (directory / 'started.json').write_text('{}\n', encoding='utf-8')
            (directory / 'tests.log').write_text('synthetic failure\n', encoding='utf-8')
            before = {p.name: p.read_bytes() for p in directory.iterdir()}
            with patch.object(ops, 'configuration', return_value={'claims': {'model': False}}), \
                 patch.object(ops, 'verify', side_effect=ValueError('synthetic failure')), patch('builtins.print'):
                ops.export(directory, report)
                value = json.loads(report.read_text())
                self.assertEqual(value['status'], 'failed_or_incomplete')
                self.assertIsNone(value['examples'])
                self.assertEqual(before, {p.name: p.read_bytes() for p in directory.iterdir()})
                ops.export(directory, report)  # Identical report is reusable.
                report.write_bytes(b'keep existing different report')
                with self.assertRaises(ValueError):
                    ops.export(directory, report)
                self.assertEqual(report.read_bytes(), b'keep existing different report')

    def test_verify_rejects_changed_artifacts_or_skipped_checks(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            binding = {'synthetic.py': 'fixed'}
            ops.write_new(directory / 'started.json', {'stage': ops.STAGE, 'commit': 'synthetic', 'binding': binding})
            (directory / 'tests.log').write_text('synthetic pass\n', encoding='utf-8')
            receipt = {'stage': ops.STAGE, 'commit': 'synthetic', 'binding': binding, 'exit_code': 0,
                       'test_names': ['synthetic.case'], 'tests_run': 1, 'failures': 0, 'errors': 0, 'skipped': 0,
                       'artifacts': {n: ops.sha((directory/n).read_bytes()) for n in ('started.json', 'tests.log')},
                       'elapsed_s': 1, 'stage_bytes': 1000, 'parent_peak_rss_bytes': 1024,
                       'new_simulation_steps': 0, 'new_training_steps': 0, 'new_weight_download_bytes': 0,
                       'claims': {'model': False}}
            ops.write_new(directory / 'receipt.json', receipt)
            with patch.object(ops, 'configuration'), patch.object(ops, 'binding', return_value=binding), \
                 patch.object(ops, 'inventory', return_value=(None, ['synthetic.case'])), patch('builtins.print'):
                ops.verify(directory)
                receipt['skipped'] = 1
                (directory / 'receipt.json').write_bytes(ops.encode(receipt))
                with self.assertRaises(ValueError): ops.verify(directory)
                receipt['skipped'] = 0
                (directory / 'receipt.json').write_bytes(ops.encode(receipt))
                (directory / 'tests.log').write_text('changed', encoding='utf-8')
                with self.assertRaises(ValueError): ops.verify(directory)
