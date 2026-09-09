"""Tiny control-flow fixtures; never launch a runner or read server arrays."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ops'))
import m1_corrected_probe as ops


class TestCorrectedProbeDelivery(unittest.TestCase):
    def test_failed_step_is_reused_without_training(self):
        with tempfile.TemporaryDirectory() as d:
            stage = Path(d); (stage / 'train.completed.json').touch()
            with patch.object(ops, 'prerequisite'), patch.object(ops, 'verify_step', return_value={'exit_code': 1}), patch.object(ops, 'command') as command:
                self.assertEqual(ops.run_step(stage, 'train', {}), 1)
                command.assert_not_called()

    def test_interrupted_attempt_is_not_restarted(self):
        with tempfile.TemporaryDirectory() as d:
            stage = Path(d); (stage / 'train.attempt.json').touch()
            with patch.object(ops, 'prerequisite'), patch.object(ops, 'command') as command:
                with self.assertRaisesRegex(ValueError, 'incomplete'): ops.run_step(stage, 'train', {})
                command.assert_not_called()

    def test_prior_failure_blocks_dependent_step(self):
        with tempfile.TemporaryDirectory() as d:
            stage = Path(d); (stage / 'test.log').write_text('ok')
            ops.write_json(stage / 'test.completed.json', {'binding': {}, 'exit_code': 0,
                'log_sha256': ops.file_sha256(stage / 'test.log')})
            with patch.object(ops, 'verify_step', return_value={'exit_code': 1}):
                with self.assertRaisesRegex(ValueError, 'prior step failed'): ops.prerequisite(stage, 'train', {})


if __name__ == '__main__': unittest.main()
