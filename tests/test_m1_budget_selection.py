"""Cheap invariants for the v8 train/inner-dev budget runner."""
from pathlib import Path
import sys
import unittest

import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from scripts.run_m1_train_inner_dev_budget import (  # noqa: E402
    _accuracy_by_group,
    _checkpoint_selection,
)


class TestM1BudgetSelection(unittest.TestCase):
    def test_highest_mean_wins(self):
        selected = _checkpoint_selection({
            300: [0.5, 0.7],
            1000: [0.8, 0.8],
            3000: [0.6, 0.7],
        })
        self.assertEqual(selected["selected_checkpoint"], 1000)
        self.assertFalse(selected["tie_break_applied"])

    def test_exact_tie_uses_fewer_updates(self):
        selected = _checkpoint_selection({
            300: [0.75], 1000: [0.75], 3000: [0.5],
        })
        self.assertEqual(selected["selected_checkpoint"], 300)
        self.assertTrue(selected["tie_break_applied"])

    def test_group_metric_keeps_complete_groups_separate(self):
        result = _accuracy_by_group(
            np.asarray([0, 1, 1, 0]),
            np.asarray([0, 0, 1, 0]),
            np.asarray([10, 10, 20, 20]),
            np.asarray([True, True, True, True]),
        )
        self.assertEqual(result, {"10": 0.5, "20": 1.0})


if __name__ == "__main__":
    unittest.main()
