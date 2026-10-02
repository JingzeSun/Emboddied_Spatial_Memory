"""S3-01 planning tests (pending ruling 102): the resampling, rule and definition pieces of ops/vsmt/s3_01_planning.py.

Pinned: (1) the two-level statistic draws houses and seeds independently and every drawn seed uses the same drawn houses;
(2) the lower bound uses the same index rule as lean_teacher.paired_house_bootstrap; (3) the favourable 82-1 condition needs all
five seeds, at least four favourable gaps and a mean above the sd of the gaps; (4) the conditional and common identity-continuity
definitions and the one-list exclusion; (5) the difference sign (positive = VSMT-lean better) for a lower-is-better metric;
(6) the simulation is reproducible from its seed and its rows carry no seed effect.  CPU only, seconds.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for item in (PROJECT_ROOT / "src", PROJECT_ROOT / "tests", PROJECT_ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import s3_01_planning as plan  # noqa: E402


def ic_report(kept: int, judged: int, no_prior: int) -> dict:
    return {"identity_continuity": {"identity_continuity": (kept / judged) if judged else None, "kept": kept, "judged": judged,
                                    "no_prior_carrier": no_prior},
            "missing_residual_rate": {"missing_residual_rate": None, "residual": 0, "judged": 0, "not_yet_observable": 0}}


class TestResampling(unittest.TestCase):
    def test_two_level_uses_the_same_drawn_houses_for_every_drawn_seed(self):
        matrix = np.arange(15, dtype=float).reshape(3, 5)  # house h, seed s -> 5h + s
        house_idx = np.array([[0, 0, 2], [1, 2, 2]])
        seed_idx = np.array([[1, 1, 1, 4, 4], [0, 1, 2, 3, 4]])
        got = plan.two_level_means(matrix, house_idx, seed_idx)
        for b in range(2):
            expected = np.mean([[matrix[h, s] for s in seed_idx[b]] for h in house_idx[b]])
            self.assertAlmostEqual(float(got[b]), float(expected))
        # with a single drawn seed column the statistic is that seed's mean over the drawn houses
        one = plan.two_level_means(matrix, np.array([[0, 1, 2]]), np.array([[3, 3, 3, 3, 3]]))
        self.assertAlmostEqual(float(one[0]), float(matrix[:, 3].mean()))

    def test_house_only_resamples_seed_averaged_rows(self):
        matrix = np.array([[0.0, 2.0, 4.0, 6.0, 8.0], [10.0, 10.0, 10.0, 10.0, 10.0]])
        got = plan.house_means(matrix, np.array([[0, 0], [1, 0]]))
        self.assertEqual(list(got), [4.0, 7.0])

    def test_lower_index_matches_the_registered_bootstrap(self):
        self.assertEqual(plan.lower_index(10_000), 500)
        self.assertEqual(plan.lower_index(1_000), 50)
        self.assertEqual(plan.lower_index(1), 0)


class TestRules(unittest.TestCase):
    def test_favourable_82_1_needs_five_seeds_four_favourable_and_mean_above_sd(self):
        self.assertTrue(plan.stable_in_favour([0.1, 0.1, 0.1, 0.1, -0.01]))
        self.assertFalse(plan.stable_in_favour([0.1, 0.1, -0.1, 0.1, 0.1]))  # mean 0.06 < sd 0.089
        self.assertFalse(plan.stable_in_favour([0.1, 0.1, 0.1, 0.1]))  # four seeds cannot be judged
        self.assertFalse(plan.stable_in_favour([-0.1, -0.1, -0.1, -0.1, -0.1]))  # stable but against VSMT-lean

    def test_identity_continuity_definitions(self):
        self.assertEqual(plan.identity_continuity_conditional(ic_report(2, 4, 4)), 0.5)
        self.assertEqual(plan.identity_continuity_common(ic_report(2, 4, 4)), 0.25)
        self.assertIsNone(plan.identity_continuity_conditional(ic_report(0, 0, 3)))
        self.assertEqual(plan.identity_continuity_common(ic_report(0, 0, 3)), 0.0)
        self.assertIsNone(plan.identity_continuity_common(ic_report(0, 0, 0)))

    def test_one_exclusion_list_over_the_listed_runs(self):
        values = {("VSMT-lean", 7): {"a": 0.1, "b": None, "c": 0.3}, ("AssocOnly", 7): {"a": 0.2, "b": 0.1, "c": None},
                  ("TAF", None): {"a": 0.0, "b": 0.0, "c": 0.0}}
        self.assertEqual(plan.defined_houses(values, list(values)), ["a"])
        self.assertEqual(plan.defined_houses(values, [("TAF", None)]), ["a", "b", "c"])

    def test_difference_is_positive_when_vsmt_lean_is_better(self):
        values = {(arm, s): {"h": (0.1 if arm == "VSMT-lean" else 0.4)} for arm in plan.LEARNED for s in plan.SEEDS}
        lower = plan.difference_matrix(values, ["h"], "lower")
        higher = plan.difference_matrix(values, ["h"], "higher")
        self.assertTrue(np.allclose(lower, 0.3))
        self.assertTrue(np.allclose(higher, -0.3))


class TestSimulation(unittest.TestCase):
    def test_reproducible_and_rows_carry_no_seed_effect(self):
        matrix = np.random.default_rng(0).normal(0.05, 0.2, size=(12, 5)) + np.array([0.0, 0.1, -0.1, 0.05, 0.0])
        rows = plan.centred_rows(matrix)
        self.assertTrue(np.allclose(rows.mean(axis=0), 0.0))
        first = plan.simulate(rows, effect=0.0, sd_seed=0.05, houses=10, replicates=20, iterations=200, rng=np.random.default_rng(5))
        second = plan.simulate(rows, effect=0.0, sd_seed=0.05, houses=10, replicates=20, iterations=200, rng=np.random.default_rng(5))
        self.assertEqual(first, second)
        self.assertEqual(set(first), {"house_only", "house_and_82_1", "two_level_and_82_1", "two_level_only"})

    def test_components_recover_a_constant_shift(self):
        matrix = np.full((6, 5), 0.2)
        comp = plan.components(matrix)
        self.assertAlmostEqual(comp["mean"], 0.2)
        self.assertEqual(comp["sd_seed"], 0.0)
        self.assertEqual(comp["sd_house"], 0.0)


if __name__ == "__main__":
    unittest.main()
