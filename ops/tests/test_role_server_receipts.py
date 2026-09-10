"""Standard-library-only receipt checks; no models, data generation or torch."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('role_receipts', Path(__file__).parents[1] / 'm1_role_encoding_server_check.py')
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class ReceiptTests(unittest.TestCase):
    def fixture(self, root):
        binding = {mod.ENTRY: 'new-entry', mod.REPAIR_TEST: 'new-test', 'src/cpmt/fixture.py': 'science-sha'}
        expected = mod.old_binding(binding)
        key = mod.sha(json.dumps(expected, sort_keys=True).encode())[:16]
        directory = root / 'outputs/m1-role-encoding-server-check' / key
        directory.mkdir(parents=True)
        names = {name: [f'{Path(pattern).stem}.Fixture.test_{i}' for i in range(count)]
                 for name, pattern, count in mod.SUITES}
        runtime = {'system': 'Linux', 'release': '6.8-fixture', 'source_commit': 'fixture'}
        mod.write_new(directory / 'attempt.json', {'step_id': 'ROLE-S1', 'code_binding': expected, 'runtime': runtime})
        mod.write_new(directory / 'failure.json', {'exit_code': 1, 'error': mod.COUNT_FAILURE,
                                                 'completed_suites': ['prototype', 'legacy'], 'runtime': runtime})
        for name, pattern, count in mod.SUITES:
            output = ''.join(f'{item.rsplit(".", 1)[1]} ({item}) ... ok\n' for item in names[name])
            output += f'\n----------------------------------------------------------------------\nRan {count} tests in 1.000s\n\nOK\n'
            (directory / f'{name}.log').write_text(output, encoding='utf-8', newline='\n')
            mod.write_new(directory / f'{name}.exit.json', {'name': name, 'pattern': pattern, 'exit_code': 0,
                                                           'tests_run': count, 'output': output,
                                                           'output_sha256': mod.sha(output.encode('utf-8'))})
        return directory, binding, expected, names

    def test_actual_static_inventory_is_9_and_28(self):
        self.assertEqual({k: len(v) for k, v in mod.inventories().items()}, {'prototype': 9, 'legacy': 28})
        self.assertEqual(mod.TOTAL_TESTS, 37)

    def test_recover_publishes_without_running_tests_or_mutating_originals(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory, binding, expected, names = self.fixture(root)
            output = root / 'report.json'
            originals = {p.name: p.read_bytes() for p in directory.iterdir()}
            with patch.object(mod, 'ROOT', root), patch.object(mod, 'OUTPUT', output), \
                 patch.object(mod, 'code_binding', return_value=binding), patch.object(mod, 'inventories', return_value=names), \
                 patch.object(mod.subprocess, 'Popen', side_effect=AssertionError('must not rerun')), \
                 patch.object(mod.subprocess, 'check_output', side_effect=AssertionError('must not execute')):
                mod.recover()
                report = json.loads(output.read_bytes())
                mod.verify(report, binding)
                self.assertEqual(report['executed_code_binding'], expected)
                self.assertFalse(report['recovery']['tests_rerun'])
                mod.recover()
            for name, raw in originals.items():
                self.assertEqual((directory / name).read_bytes(), raw)

    def test_changed_science_binding_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory, _, expected, names = self.fixture(Path(temp))
            expected['src/cpmt/fixture.py'] = 'different-science'
            with self.assertRaisesRegex(ValueError, 'source mismatch'):
                mod.load_count_failure(directory, expected, names)

    def test_changed_log_is_rejected_even_if_receipt_is_valid(self):
        with tempfile.TemporaryDirectory() as temp:
            directory, _, expected, names = self.fixture(Path(temp))
            (directory / 'legacy.log').write_text('tampered', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'log differs'):
                mod.load_count_failure(directory, expected, names)

    def test_real_test_failure_is_not_recovered(self):
        with tempfile.TemporaryDirectory() as temp:
            directory, _, expected, names = self.fixture(Path(temp))
            path = directory / 'legacy.exit.json'
            receipt = json.loads(path.read_bytes())
            receipt['exit_code'] = 1
            path.write_text(json.dumps(receipt), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'suite failed'):
                mod.load_count_failure(directory, expected, names)

    def test_other_wrapper_failure_is_not_recovered(self):
        with tempfile.TemporaryDirectory() as temp:
            directory, _, expected, names = self.fixture(Path(temp))
            path = directory / 'failure.json'
            failure = json.loads(path.read_bytes())
            failure['error'] = 'source changed during checks'
            path.write_text(json.dumps(failure), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'count-only'):
                mod.load_count_failure(directory, expected, names)

    def test_summary_count_cannot_hide_missing_or_duplicate_test_names(self):
        with tempfile.TemporaryDirectory() as temp:
            directory, _, _, names = self.fixture(Path(temp))
            receipt = json.loads((directory / 'legacy.exit.json').read_bytes())
            receipt['output'] = receipt['output'].replace(names['legacy'][0], names['legacy'][1])
            receipt['output_sha256'] = mod.sha(receipt['output'].encode())
            with self.assertRaisesRegex(ValueError, 'test names'):
                mod.validate_receipt(receipt, mod.SUITES[1], names['legacy'])

    def test_older_unittest_display_format_is_supported(self):
        with tempfile.TemporaryDirectory() as temp:
            directory, _, _, names = self.fixture(Path(temp))
            receipt = json.loads((directory / 'legacy.exit.json').read_bytes())
            for name in names['legacy']:
                receipt['output'] = receipt['output'].replace(f'({name})', f'({name.rsplit(".", 1)[0]})')
            receipt['output_sha256'] = mod.sha(receipt['output'].encode())
            mod.validate_receipt(receipt, mod.SUITES[1], names['legacy'])


if __name__ == '__main__':
    unittest.main()
