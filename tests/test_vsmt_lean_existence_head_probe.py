"""D-224 / S2-05 tests: the existence-head probe's AUC, quantiles and per-tau retract shares on hand-made scores."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for item in (PROJECT_ROOT / "src", PROJECT_ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import existence_head_probe as probe  # noqa: E402


class ExistenceProbeTests(unittest.TestCase):
    def test_auc_by_ranks_with_ties(self) -> None:
        self.assertEqual(probe.auc([0.9, 0.8], [0.1, 0.2]), 1.0)
        self.assertEqual(probe.auc([0.1], [0.9]), 0.0)
        self.assertEqual(probe.auc([0.5], [0.5]), 0.5)
        self.assertAlmostEqual(probe.auc([0.6, 0.4], [0.5, 0.3]), 0.75)
        self.assertIsNone(probe.auc([], [0.1]))

    def test_retract_shares_follow_the_grid(self) -> None:
        out = probe.summarise({"gone": [0.35, 0.45, 0.95, 0.1], "present": [0.05, 0.31, 0.2, 0.1]})
        self.assertEqual(out["candidates"], {"gone": 4, "present": 4})
        self.assertEqual(out["retract_share_at_tau"]["0.3"], {"gone": 0.75, "present": 0.25})
        self.assertEqual(out["retract_share_at_tau"]["0.5"], {"gone": 0.25, "present": 0.0})
        fine = probe.summarise({"gone": [0.15, 0.25], "present": [0.12]}, taus=(0.1, 0.2))
        self.assertEqual(fine["retract_share_at_tau"], {"0.1": {"gone": 1.0, "present": 1.0}, "0.2": {"gone": 0.5, "present": 0.0}})
        self.assertAlmostEqual(probe.sigmoid(0.0), 0.5)
        self.assertAlmostEqual(probe.sigmoid(-800.0), 0.0)


if __name__ == "__main__":
    unittest.main()
