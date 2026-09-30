"""Ruling 93 revised (a): the read-only score reading and the threshold-sensitivity reading."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for item in (ROOT / "src", ROOT / "ops" / "vsmt", ROOT / "tests"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import ruling93_scores as scores  # noqa: E402
import ruling93_tau_reading as reading  # noqa: E402


class ScoreTests(unittest.TestCase):
    def test_auc_counts_ties_half(self) -> None:
        self.assertEqual(scores.auc([0.9, 0.8], [0.1, 0.2]), 1.0)
        self.assertEqual(scores.auc([0.1], [0.9]), 0.0)
        self.assertEqual(scores.auc([0.5], [0.5]), 0.5)
        self.assertIsNone(scores.auc([], [0.1]))

    def test_the_raw_threshold_undoes_the_ln_w_offset(self) -> None:
        for tau in (0.15, 0.2, 0.3, 0.5):
            raw = scores.raw_threshold(tau, 65.0)
            corrected = 1.0 / (1.0 + math.exp(-(math.log(raw / (1.0 - raw)) - math.log(65.0))))
            self.assertAlmostEqual(corrected, tau, places=9)
        self.assertAlmostEqual(scores.raw_threshold(0.15, 65.0), 0.920, places=3)

    def test_the_two_terms_add_up_to_the_training_loss(self) -> None:
        import torch
        import test_vsmt_lean_model as fixture
        from vsmt import lean_model as model
        record = fixture.labelled_frame(21, drop="lamp", new=True)
        for row in record["existence_rows"]:
            record["existence_labels"].setdefault(str(row["entity_id"]), {"status": "present"})
        clean = {k: v for k, v in record.items() if not k.startswith("_")}
        heads = model.make_heads(assoc_only=False, seed=2)
        batched = model.batch_prepared(model.prepare_frame(clean))
        w = torch.as_tensor([5.0])
        parts = scores.frame_parts(heads, batched, w)
        total = float(model.batched_loss(heads, batched, existence_pos_weight=w)["loss"])
        self.assertAlmostEqual(parts["association"] + parts["existence"], total, places=5)
        values, labels = parts["scores"]
        self.assertEqual(len(values), len(labels))


class ReadingTests(unittest.TestCase):
    def test_a_seed_row_reads_metrics_retract_rates_and_the_lines(self) -> None:
        payload = {
            "schema_version": "vsmt-s2-05-node-audit-merged-v10",
            "existence_tally_fields": ["status", "decision"],
            "pooled_existence_tally": [["present", "RETRACT", 1], ["present", "NOOP", 99], ["gone", "RETRACT", 3], ["gone", "NOOP", 1]],
            "per_episode": [{"episode_id": "h1", "report": {"missing_residual_rate": {"missing_residual_rate": 0.04},
                                                            "node_prf1": {"node_f1": 0.95},
                                                            "false_retract_rate_in_scope": {"false_retract_rate": 0.1}}}],
        }
        row = reading.seed_row(payload)
        self.assertAlmostEqual(row["present_retracted_per_decision"], 0.01)
        self.assertAlmostEqual(row["gone_retracted_per_decision"], 0.75)
        self.assertTrue(row["meets_both_cell_lines"])
        self.assertEqual(row["per_house_missing_residual"], {"h1": 0.04})


if __name__ == "__main__":
    unittest.main()
