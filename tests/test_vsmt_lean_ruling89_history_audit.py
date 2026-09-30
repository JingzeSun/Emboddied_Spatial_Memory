"""Ruling 89-2: the history summaries checked against the ELU-P and RAC arms' own state, and a broken summary is caught."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for item in (ROOT / "src", ROOT / "ops" / "vsmt", ROOT / "tests"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from vsmt import lean_runner as lr  # noqa: E402

import ruling89_history_audit as audit  # noqa: E402
import test_vsmt_lean_runner as fixture  # noqa: E402


def run_audit(arm: str) -> dict:
    config = dict(fixture.CONFIGS[arm])
    if arm == "RAC":
        config["rho_rac"] = 0.7  # the summaries carry the grid values 0.70 / 0.85; full coverage in the fixture
    checker = audit.Audit(arm, config)
    state = lr.initial_state(episode_id="ep-0001", arm=arm)
    for frame in fixture.scenario():
        step = lr.run_frame(state, frame, arm=arm, config=config, policy=fixture.POLICY, descriptor=fixture.la.FROZEN_DESCRIPTOR_BASELINE)
        checker.observe(state, step)
        state = step["state"]
    return checker.report()


class HistoryAuditTests(unittest.TestCase):
    def test_the_summaries_agree_with_both_executors(self) -> None:
        for arm in ("ELU-P", "RAC"):
            report = run_audit(arm)
            self.assertGreaterEqual(report["rows"], 2, arm)
            self.assertGreaterEqual(report["retract_rows"], 1, arm)
            self.assertEqual(report["decision_mismatches"], 0, arm)
            self.assertEqual(report["state_mismatches"], 0, arm)
            self.assertTrue(report["faithful"], arm)
            self.assertLess(report["max_log_odds_error"], audit.LOG_ODDS_TOLERANCE)

    def test_a_summary_that_forgets_matches_is_caught(self) -> None:
        real = lr.update_existence_history

        def forgetful(history, eligible, order, matched):
            return real(history, eligible, order, [])  # no match count, no RAC reset

        with mock.patch.object(lr, "update_existence_history", side_effect=forgetful):
            elu = run_audit("ELU-P")
        self.assertFalse(elu["faithful"])
        self.assertGreater(elu["state_mismatches"], 0)


if __name__ == "__main__":
    unittest.main()
