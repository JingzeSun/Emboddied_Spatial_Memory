"""D-224 / S2-05 tests: the per-term curve replay of ruling 79-3 (ii) on the synthetic records of the model tests.

The two term means are the two parts of the registered loss (their per-frame sum averaged is the registered validation
loss), the reproduction check needs the weights digest, the best epoch and both curves to agree bit for bit, and the
per-term best epoch ties to the earlier epoch like the registered early stopping.  CPU only, seconds.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for item in (PROJECT_ROOT / "src", PROJECT_ROOT / "tests", PROJECT_ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import lean_s2_05_term_curves as curves  # noqa: E402
from test_vsmt_lean_model import labelled_frame  # noqa: E402
from vsmt import lean_model as model  # noqa: E402


class TermCurveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.train = [labelled_frame(s, drop=("lamp" if s % 2 else None), new=(s % 3 == 0)) for s in range(30, 42)]
        cls.validation = [labelled_frame(s, drop=("book" if s % 2 else None), new=(s % 2 == 0)) for s in range(50, 54)]
        cls.prepared = [model.prepare_frame(r) for r in cls.validation]
        cls.seen = []
        cls.result = model.train_heads(cls.train, cls.validation, learning_rate=1e-3, weight_decay=1e-4, epochs=3, seed=7, assoc_only=False,
                                       epoch_callback=lambda epoch, heads: cls.seen.append(curves.term_means(heads, cls.prepared)))

    def test_the_two_terms_rebuild_the_registered_validation_loss(self) -> None:
        self.assertEqual(len(self.seen), 3)
        heads = self.result["heads"]
        means = curves.term_means(heads, self.prepared)
        self.assertEqual(means["association_frames"], len(self.prepared))
        # every synthetic frame has an association term, so the registered loss (the mean of per-frame sums) is the
        # frame-weighted sum of the two term means
        def rebuilt(m):
            return (m["association_term_mean"] * m["association_frames"] + m["existence_term_mean"] * m["existence_frames"]) / m["association_frames"]

        self.assertGreater(means["existence_frames"], 0)
        self.assertAlmostEqual(rebuilt(means), model._mean_loss(heads, self.prepared), places=6)
        best = self.result["best_epoch"]
        self.assertAlmostEqual(rebuilt(self.seen[best]), self.result["validation_curve"][best], places=6)

    def test_the_reproduction_check_needs_every_part(self) -> None:
        receipt = {"weights_sha256": self.result["weights"]["sha256"], "best_epoch": self.result["best_epoch"],
                   "train_curve": list(self.result["train_curve"]), "validation_curve": list(self.result["validation_curve"])}
        self.assertTrue(all(curves.reproduction_check(self.result, receipt).values()))
        broken = {**receipt, "validation_curve": [v + 1e-12 for v in receipt["validation_curve"]]}
        self.assertEqual(curves.reproduction_check(self.result, broken),
                         {"weights_sha256": True, "best_epoch": True, "train_curve": True, "validation_curve": False})

    def test_argmin_ties_to_the_earlier_epoch(self) -> None:
        self.assertEqual(curves.argmin_epoch([0.5, 0.3, 0.3, None]), 1)
        self.assertIsNone(curves.argmin_epoch([None, None]))

    def test_assoc_only_heads_have_no_existence_term(self) -> None:
        means = curves.term_means(model.make_heads(assoc_only=True, seed=1), self.prepared)
        self.assertIsNone(means["existence_term_mean"])
        self.assertEqual(means["existence_frames"], 0)


if __name__ == "__main__":
    unittest.main()
