"""Delivery control fixtures; no server process or GPU work."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ops'))
import m1_parallel_training_check as ops


class TestParallelTrainingDelivery(unittest.TestCase):
    def test_active_probe_blocks_before_attempt(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(ops, 'no_active_probe', side_effect=ValueError('probe running')), patch.object(ops, 'command') as command:
                with self.assertRaisesRegex(ValueError, 'probe running'): ops.check(Path(temp), {})
                command.assert_not_called()
                self.assertEqual(list(Path(temp).iterdir()), [])

    def stage(self, path):
        (path/'test.log').write_text('ok')
        ops.write_json(path/'test.completed.json', {'binding': {}, 'exit_code': 0,
                                                   'log_sha256': ops.file_sha256(path/'test.log')})

    def test_completed_failure_not_restarted(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp); self.stage(path); (path/'check.completed.json').touch()
            with patch.object(ops, 'no_active_probe'), patch.object(ops, 'verify', return_value=({'exit_code': 1}, None)), patch.object(ops, 'command') as command:
                self.assertEqual(ops.check(path, {}), 1); command.assert_not_called()

    def test_incomplete_attempt_not_restarted(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp); self.stage(path); (path/'check.attempt.json').touch()
            with patch.object(ops, 'no_active_probe'), patch.object(ops, 'command') as command:
                with self.assertRaisesRegex(ValueError, 'incomplete'): ops.check(path, {})
                command.assert_not_called()

    def test_failed_check_can_be_exported_and_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp); self.stage(path); (path/'check.log').write_text('failed before report')
            ops.write_json(path/'check.completed.json', {'binding': {}, 'exit_code': 1,
                'log_sha256': ops.file_sha256(path/'check.log'), 'files': {}})
            with patch.object(ops, 'EXPORT', path/'export.json'):
                self.assertEqual(ops.export(path, {}), 0)
                before = (path/'export.json').read_bytes()
                self.assertEqual(ops.export(path, {}), 0)
                self.assertEqual(before, (path/'export.json').read_bytes())
                self.assertIsNone(ops.read_json(path/'export.json')['report'])


if __name__ == '__main__': unittest.main()
