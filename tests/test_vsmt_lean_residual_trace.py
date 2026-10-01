"""Ruling 93 revised: the residual-trace categories (ops/vsmt/residual_trace.py, used by the node audit's --trace-residuals)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for item in (ROOT / "src", ROOT / "ops" / "vsmt", ROOT / "tests"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import residual_trace as rt  # noqa: E402


def item(status: str, **extra) -> dict:
    return {"frame": 1, "state": "active", "status": status, **extra}


class CategoryTests(unittest.TestCase):
    def test_precedence_and_counts(self) -> None:
        cases = [
            ({"e1": [item("not_visible"), item("assigned")]}, "carrier_rebound"),
            ({"e1": [item("candidate", label="gone", decision="RETRACT", logit_uncorrected=1.0)], "e2": [item("not_visible")]}, "retracted_then_back"),
            ({"e1": [item("not_visible"), item("retracted")]}, "never_eligible"),
            ({"e1": [item("candidate", label="present", decision="NOOP")]}, "eligible_teacher_never_gone"),
            ({"e1": [item("candidate", label="gone", decision="NOOP", logit_uncorrected=-2.0),
                     item("candidate", label="gone", decision="NOOP", logit_uncorrected=-0.5)]}, "eligible_gone_below_threshold"),
        ]
        for entities, expected in cases:
            category, counts = rt.ResidualTracer.classify(entities)
            self.assertEqual(category, expected)
            self.assertEqual(counts["entities"], len(entities))
        _, counts = rt.ResidualTracer.classify(cases[-1][0])
        self.assertEqual(counts["max_uncorrected_logit_when_gone"], -0.5)
        self.assertEqual(counts["candidate_labelled_gone"], 2)


if __name__ == "__main__":
    unittest.main()
