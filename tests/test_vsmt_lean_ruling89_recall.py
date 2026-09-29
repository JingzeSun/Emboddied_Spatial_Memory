"""Ruling 89-1 reading: the frozen k' rule and the rank distribution of the recall misses."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT / "src", PROJECT_ROOT / "ops" / "vsmt"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import ruling89_recall as r89  # noqa: E402


class TestRecallRule(unittest.TestCase):
    def test_first_candidate_within_the_limit_is_taken_in_order(self) -> None:
        self.assertEqual(r89.choose({5: 6, 8: 2, 12: 0})["chosen_k_prime"], 8)
        self.assertEqual(r89.choose({5: 3, 8: 1, 12: 0})["chosen_k_prime"], 5)

    def test_no_candidate_passes_means_pause(self) -> None:
        got = r89.choose({5: 9, 8: 6, 12: 4})
        self.assertIsNone(got["chosen_k_prime"])
        self.assertTrue(got["decision"].startswith("no_candidate_passes"))

    def test_rank_distribution_counts_only_misses(self) -> None:
        rows = [{"category": "carrier_not_recalled", "original_carrier_global_rank": r, "entities_in_memory": 50} for r in (4, 5, 7, 30)]
        rows += [{"category": "kept", "original_carrier_global_rank": 1, "entities_in_memory": 50}]
        got = r89.rank_distribution(rows)
        self.assertEqual(got["misses"], 4)
        self.assertEqual(got["bins"]["4-5"], 2)
        self.assertEqual(got["bins"]["6-8"], 1)
        self.assertEqual(got["bins"]["21-50"], 1)
        self.assertEqual(got["covered_by_k"], {"5": 2, "8": 3, "12": 3})


if __name__ == "__main__":
    unittest.main()
