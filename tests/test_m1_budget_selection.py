"""Cheap invariants for the v8 train/inner-dev budget runner."""
from pathlib import Path
import sys
import unittest

import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from scripts.run_m1_train_inner_dev_budget import (  # noqa: E402
    _accuracy_by_group,
    _cell_group_means,
    _checkpoint_selection,
    _grid_selection,
    _linear_runtime_projection,
    _paired_group_bootstrap_difference,
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

    def test_lr_checkpoint_grid_ties_on_less_work_then_lower_lr(self):
        selected = _grid_selection({
            (0.002, 300): [0.8],
            (0.0006, 300): [0.8],
            (0.0002, 1000): [0.8],
        }, maximum_checkpoint=1000)
        self.assertEqual(selected["selected_checkpoint"], 300)
        self.assertEqual(selected["selected_learning_rate"], 0.0006)
        self.assertFalse(selected["budget_grid_ceiling_reached"])

    def test_lr_checkpoint_grid_reports_a_ceiling_win(self):
        selected = _grid_selection({
            (0.0006, 3000): [0.7],
            (0.0006, 10000): [0.9],
        }, maximum_checkpoint=10000)
        self.assertTrue(selected["budget_grid_ceiling_reached"])
        self.assertEqual(
            selected["ceiling_action"],
            "accept_and_report_without_posthoc_extension",
        )

    def test_grid_selection_records_deterministic_runner_up(self):
        selected = _grid_selection({
            (0.0002, 300): [0.7],
            (0.0006, 300): [0.8],
            (0.002, 300): [0.8],
        }, maximum_checkpoint=300)
        self.assertEqual(selected["selected_learning_rate"], 0.0006)
        self.assertEqual(
            selected["deterministic_runner_up"]["learning_rate"], 0.002,
        )

    def test_complete_group_means_average_seeds_before_selection(self):
        runs = [
            {
                "seed": seed,
                "method": "A",
                "learning_rate": 0.0006,
                "checkpoint": 300,
                "inner_dev_online": {
                    "reference_accuracy_by_group": values,
                },
            }
            for seed, values in (
                (7, {"g0": 1.0, "g1": 0.0}),
                (19, {"g0": 0.0, "g1": 1.0}),
            )
        ]
        result = _cell_group_means(
            runs,
            metric_key="reference_accuracy_by_group",
            expected_cells={(0.0006, 300)},
            expected_observations_per_group=2,
            method="A",
        )
        self.assertEqual(result[(0.0006, 300)], {"g0": 0.5, "g1": 0.5})

    def test_complete_group_means_reject_duplicate_seed_support(self):
        run = {
            "seed": 7,
            "method": "A",
            "learning_rate": 0.0006,
            "checkpoint": 300,
            "inner_dev_online": {
                "reference_accuracy_by_group": {"g0": 1.0},
            },
        }
        with self.assertRaisesRegex(ValueError, "duplicate seed/method"):
            _cell_group_means(
                [run, dict(run)],
                metric_key="reference_accuracy_by_group",
                expected_cells={(0.0006, 300)},
                expected_observations_per_group=2,
                method="A",
            )

    def test_paired_bootstrap_is_reproducible_and_group_paired(self):
        first = _paired_group_bootstrap_difference(
            {"g0": 0.9, "g1": 0.7, "g2": 0.8},
            {"g0": 0.8, "g1": 0.6, "g2": 0.8},
            resamples=1000,
            seed=260907,
            confidence=0.95,
        )
        second = _paired_group_bootstrap_difference(
            {"g0": 0.9, "g1": 0.7, "g2": 0.8},
            {"g0": 0.8, "g1": 0.6, "g2": 0.8},
            resamples=1000,
            seed=260907,
            confidence=0.95,
        )
        self.assertEqual(first, second)
        self.assertAlmostEqual(first["observed_mean_difference"], 2.0 / 30.0)
        self.assertEqual(first["complete_paired_groups"], 3)

    def test_runtime_projection_counts_registered_paths_and_methods(self):
        projection = _linear_runtime_projection(
            scorer_path_seconds=2.0,
            scorer_evaluation_seconds=1.0,
            student_path_seconds_by_method={"A": 1.0, "E": 1.0},
            student_evaluation_seconds_by_method={"A": 0.5, "E": 0.5},
            profile_steps=100,
            maximum_steps=1000,
            learning_rate_count=3,
            seed_count=5,
            checkpoint_count=4,
        )
        self.assertEqual(projection["paths_per_component"], 15)
        self.assertEqual(projection["scorer_seconds"], 360.0)
        self.assertEqual(
            projection["student_seconds_by_method"],
            {"A": 180.0, "E": 180.0},
        )
        self.assertEqual(projection["total_seconds"], 720.0)
        self.assertFalse(projection["protocol_cap_or_selection_metric"])


if __name__ == "__main__":
    unittest.main()
