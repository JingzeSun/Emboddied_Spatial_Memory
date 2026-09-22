"""D-224-E / ruling 47: the shared ReID adapter head core.

What is pinned here: the 30/12 hold-out follows the S0-02 split rank and never overlaps; training
refuses a null value; two trainings with the same values give identical weights; the loss falls
on separable synthetic data and the projection is unit-norm; the weights file round-trips through
its digest; and the S1-05 selection rule keeps the frozen descriptor unless the projection gains
the ledgered margin.  Runs on CPU torch in seconds.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from vsmt import lean_frontend_diagnostics as fd  # noqa: E402
from vsmt import lean_reid_head as rh  # noqa: E402
from vsmt.lean_assignment import REID_SELECTION_HOUSES, REID_TRAINING_HOUSES  # noqa: E402
from vsmt.lean_intervention import house_split_rank  # noqa: E402

VALUES = {"temperature": 0.07, "epochs": 15, "batch_fragments": 64, "learning_rate": 1e-2, "seed": 20260922}


def unit(vector) -> list[float]:
    array = np.asarray(vector, dtype=np.float64)
    return (array / np.linalg.norm(array)).tolist()


def episodes(seed: int = 5, houses: int = 3, frames: int = 10, objects: int = 4, dimension: int = 24) -> dict:
    """Per house: objects with a base direction masked by strong nuisance dimensions; noise per view."""

    rng = np.random.default_rng(seed)
    out = {}
    for h in range(houses):
        bases = {f"obj:{i}": rng.normal(size=dimension) for i in range(objects)}
        rows = []
        for t in range(frames):
            fragments = []
            for n, key in enumerate(sorted(bases)):
                signal = bases[key] * np.r_[np.ones(dimension // 2), np.zeros(dimension - dimension // 2)]
                nuisance = rng.normal(scale=3.0, size=dimension) * np.r_[np.zeros(dimension // 2), np.ones(dimension - dimension // 2)]
                fragments.append({"fragment_id": f"f{t}:{n}", "object": key, "descriptor": unit(signal + nuisance + rng.normal(scale=0.3, size=dimension)),
                                  "centroid_m": [float(n), 0.0, float(t)]})
            fragments.append({"fragment_id": f"f{t}:x", "object": None, "descriptor": unit(rng.normal(size=dimension)), "centroid_m": [9, 9, 9]})
            rows.append({"tick": t + 1, "fragments": fragments})
        out[f"procthor10k-0.1.2-train-{h:05d}"] = rows
    return out


class HoldoutTests(unittest.TestCase):
    def test_first_30_by_split_rank_train_and_the_next_12_select_without_overlap(self) -> None:
        ids = [f"procthor10k-0.1.2-train-{i:05d}" for i in range(50)]
        cached = ids[:20] + ids[21:43]  # 42 houses, one lost to overflow
        split = rh.holdout_split(cached, seed=20260920)
        self.assertEqual(len(split["training_houses"]), REID_TRAINING_HOUSES)
        self.assertEqual(len(split["selection_houses"]), REID_SELECTION_HOUSES)
        self.assertEqual(set(split["training_houses"]) & set(split["selection_houses"]), set())
        self.assertEqual((split["training_shortfall"], split["selection_shortfall"]), (0, 0))
        ranked = sorted(cached, key=lambda h: (house_split_rank(h, seed=20260920), h))
        self.assertEqual(split["training_houses"], ranked[:30])
        self.assertEqual(split["selection_houses"], ranked[30:42])
        short = rh.holdout_split(cached[:35], seed=20260920)
        self.assertEqual(short["selection_shortfall"], 7)
        with self.assertRaises(rh.LeanReIDError):
            rh.holdout_split(cached + [cached[0]], seed=20260920)


class TrainingTests(unittest.TestCase):
    def test_training_refuses_a_null_value(self) -> None:
        data = rh.training_set(episodes(), descriptor_key="descriptor")
        with self.assertRaises(rh.LeanReIDError) as caught:
            rh.train_head(data["descriptors"], data["classes"], output_dimension=8, **{**VALUES, "temperature": None})
        self.assertEqual(str(caught.exception), "training_value_not_frozen:temperature")

    def test_training_is_deterministic_lowers_the_loss_and_projects_to_unit_norm(self) -> None:
        houses = episodes()
        data = rh.training_set(houses, descriptor_key="descriptor")
        self.assertEqual(data["class_count"], 12)
        self.assertEqual(data["classes_with_positives"], 12)
        first = rh.train_head(data["descriptors"], data["classes"], output_dimension=8, **VALUES)
        second = rh.train_head(data["descriptors"], data["classes"], output_dimension=8, **VALUES)
        self.assertFalse(first["diverged"])
        self.assertEqual(first["weights"]["weight"], second["weights"]["weight"])
        self.assertEqual(first["weights"]["sha256"], second["weights"]["sha256"])
        self.assertLess(first["loss_curve"][-1], first["loss_curve"][0])
        projected = rh.project_with(first["head"], data["descriptors"][:5])
        self.assertEqual(projected.shape, (5, 8))
        np.testing.assert_allclose(np.linalg.norm(projected, axis=1), 1.0, atol=1e-5)
        # the projection separates the synthetic objects better than the raw descriptor on a held-out house
        held_out = {"procthor10k-0.1.2-train-00009": episodes(seed=11, houses=1)["procthor10k-0.1.2-train-00000"]}
        frames = held_out["procthor10k-0.1.2-train-00009"]
        before = fd.separation_statistics(frames)["statistics"]["median"]
        projected_frames = rh.project_frames(frames, first["head"], source_key="descriptor")
        after = fd.separation_statistics(projected_frames, descriptor_key="reid_projection")["statistics"]["median"]
        self.assertGreater(after, before)

    def test_weights_round_trip_through_their_digest(self) -> None:
        data = rh.training_set(episodes(houses=1), descriptor_key="descriptor")
        trained = rh.train_head(data["descriptors"], data["classes"], output_dimension=8, **{**VALUES, "epochs": 2})
        payload = json.loads(json.dumps(trained["weights"]))
        head = rh.load_head(payload)
        np.testing.assert_allclose(rh.project_with(head, data["descriptors"][:3]),
                                   rh.project_with(trained["head"], data["descriptors"][:3]), atol=1e-6)
        self.assertNotIn("object", json.dumps(payload))
        payload["bias"][0] += 1.0
        with self.assertRaises(rh.LeanReIDError):
            rh.load_head(payload)


class SelectionTests(unittest.TestCase):
    def test_the_projection_needs_the_ledgered_margin_over_the_best_frozen_set(self) -> None:
        keep = rh.select_descriptor({"vits14": 0.20, "vitb14": 0.22, "reid_projection:vitb14": 0.26})
        self.assertEqual((keep["chosen"], keep["best_frozen"]), ("vitb14", "vitb14"))
        self.assertAlmostEqual(keep["projection_gain_over_best_frozen"], 0.04)
        self.assertFalse(keep["frozen_descriptor_baseline_must_be_reported"])
        take = rh.select_descriptor({"vits14": 0.20, "vitb14": 0.22, "reid_projection:vits14": 0.27, "reid_projection:vitb14": 0.30})
        self.assertEqual(take["chosen"], "reid_projection:vitb14")
        self.assertTrue(take["frozen_descriptor_baseline_must_be_reported"])
        tie = rh.select_descriptor({"vits14": 0.20, "vitb14": 0.20})
        self.assertEqual(tie["chosen"], "vits14")
        with self.assertRaises(rh.LeanReIDError):
            rh.select_descriptor({"vits14": 0.2})


if __name__ == "__main__":
    unittest.main()
