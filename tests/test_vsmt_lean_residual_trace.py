"""Ruling 93 revised: residual trace categories and the uncorrected-weights copy."""

from __future__ import annotations

import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for item in (ROOT / "src", ROOT / "ops" / "vsmt", ROOT / "tests"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import residual_trace as rt  # noqa: E402
import ruling93_uncorrect_weights as uw  # noqa: E402


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


class UncorrectedWeightsTests(unittest.TestCase):
    def test_the_copy_drops_only_the_offset(self) -> None:
        import test_vsmt_lean_model as fixture
        from vsmt import lean_model as model
        train = [fixture.labelled_frame(s, drop=("lamp" if s % 2 else None)) for s in range(30, 36)]
        validation = [fixture.labelled_frame(s, drop="book") for s in range(50, 52)]
        for record in train + validation:
            for row in record["existence_rows"]:
                record["existence_labels"].setdefault(str(row["entity_id"]), {"status": "present"})
        result = model.train_heads(train, validation, learning_rate=1e-3, weight_decay=1e-4, epochs=1, seed=7, assoc_only=False,
                                   field_encoding=True, existence_class_weight=True, existence_prior_correction=True)
        payload = json.loads(json.dumps(result["weights"]))
        raw = uw.uncorrected(payload)
        self.assertNotIn("existence_logit_offset", raw)
        self.assertEqual(raw["tensors"], payload["tensors"])
        self.assertEqual(raw["training"]["derived"]["from_sha256"], payload["sha256"])
        a = model.LeanScorer(model.load_heads(payload))
        b = model.LeanScorer(model.load_heads(raw))
        record = validation[0]
        la_, lb = (s.existence_logits(record["existence_rows"], record["existence_feature_order"]) for s in (a, b))
        w = payload["training"]["existence_class_weight"]["pos_weight"]
        for key in la_:
            self.assertAlmostEqual(lb[key] - la_[key], math.log(w), places=4)
        with self.assertRaises(ValueError):
            uw.uncorrected(raw)


if __name__ == "__main__":
    unittest.main()
