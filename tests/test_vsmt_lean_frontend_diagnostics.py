"""D-224 / S1-04: the frontend diagnostics core and its machine contract.

What is pinned here: the strict-majority diagnostic label; the cross-view separation definition
(positive minus hardest negative on another frame, capped and seeded sampling); the ideal memory
and a recall curve whose per-grid-point decisions agree exactly with the S0-03 recall function on
random cases; the IoU statistics against the gate; and the contract validator binding every
constant, the ReID values staying open, and the authorization bits staying closed.
"""

from __future__ import annotations

import json
import random
import sys
import unittest
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from vsmt import lean_frontend_diagnostics as fd  # noqa: E402
from vsmt.lean_assignment import recall_for_fragment  # noqa: E402

CONTRACT_PATH = PROJECT_ROOT / "configs" / "vsmt" / "lean_s1_04_frontend_diagnostics_v1.json"


def unit(vector) -> list[float]:
    array = np.asarray(vector, dtype=np.float64)
    return (array / np.linalg.norm(array)).tolist()


def synthetic_frames(seed: int = 3, frames: int = 12, objects: int = 5, dimension: int = 16) -> list[dict]:
    """Objects have a base direction; each view adds small noise; one unlabelled fragment per frame."""

    rng = np.random.default_rng(seed)
    bases = {f"obj:{i}": unit(rng.normal(size=dimension)) for i in range(objects)}
    centres = {key: rng.uniform(-3, 3, size=3) for key in bases}
    out = []
    for t in range(frames):
        fragments = []
        visible = sorted(rng.choice(list(bases), size=3, replace=False).tolist())
        for n, key in enumerate(visible):
            noise = rng.normal(scale=0.15, size=dimension)
            centre = centres[key] + rng.normal(scale=0.05, size=3)
            fragments.append({"fragment_id": f"f{t:03d}:{n}", "object": key,
                              "descriptor": unit(np.asarray(bases[key]) + noise),
                              "centroid_m": centre.tolist(),
                              "aabb_min_m": (centre - 0.2).tolist(), "aabb_max_m": (centre + 0.2).tolist()})
        fragments.append({"fragment_id": f"f{t:03d}:x", "object": None, "descriptor": unit(rng.normal(size=dimension)),
                          "centroid_m": [9.0, 9.0, 9.0], "aabb_min_m": [8.9] * 3, "aabb_max_m": [9.1] * 3})
        out.append({"tick": t + 1, "fragments": fragments})
    return out


class LabelTests(unittest.TestCase):
    def test_strict_majority_labels_and_ties_or_minorities_do_not(self) -> None:
        self.assertEqual(fd.label_fragment({"cup": 0.7, "book": 0.2}), "cup")
        self.assertIsNone(fd.label_fragment({"cup": 0.5, "book": 0.5}))
        self.assertIsNone(fd.label_fragment({"cup": 0.5}))
        self.assertIsNone(fd.label_fragment({}))
        self.assertEqual(fd.label_fragment({"cup": 0.51}), "cup")

    def test_overlap_counts_every_fragment_pixel_including_background(self) -> None:
        labels = np.zeros((6, 6), dtype=np.uint16)
        labels[0:3, :] = 1
        labels[3:5, :] = 2
        mask = np.zeros((6, 6), dtype=bool)
        mask[1:6, 0:2] = True  # 10 pixels: 4 on label 1, 4 on label 2, 2 on background
        overlap = fd.overlap_from_masks(mask, labels, {1: "cup", 2: "book"})
        self.assertEqual(overlap, {"book": 0.4, "cup": 0.4})
        self.assertIsNone(fd.label_fragment(overlap))
        with self.assertRaises(fd.LeanDiagnosticsError):
            fd.overlap_from_masks(np.zeros((6, 6), dtype=bool), labels, {})


class SeparationTests(unittest.TestCase):
    def test_well_separated_objects_score_positive_and_sampling_is_deterministic(self) -> None:
        frames = synthetic_frames()
        first = fd.separation_statistics(frames)
        second = fd.separation_statistics(frames)
        self.assertEqual(first["values"], second["values"])
        self.assertGreater(first["pairs"], 20)
        self.assertGreater(first["statistics"]["median"], 0.3)
        self.assertEqual(first["objects"], 5)
        self.assertEqual(first["separate_objects_statistics"]["count"], 0)
        split = fd.separation_statistics(frames, separate_objects=["obj:0"])
        self.assertEqual(split["statistics"]["count"] + split["separate_objects_statistics"]["count"], first["pairs"])

    def test_a_pair_needs_another_object_on_the_other_frame(self) -> None:
        frames = [{"tick": 1, "fragments": [{"fragment_id": "a", "object": "o", "descriptor": [1.0, 0.0], "centroid_m": [0, 0, 0]}]},
                  {"tick": 2, "fragments": [{"fragment_id": "b", "object": "o", "descriptor": [0.0, 1.0], "centroid_m": [0, 0, 0]}]}]
        self.assertEqual(fd.separation_statistics(frames)["pairs"], 0)


class RecallCurveTests(unittest.TestCase):
    def test_ranks_reproduce_the_s0_03_recall_function_on_random_cases(self) -> None:
        rng = random.Random(46)
        for case in range(200):
            n = rng.randint(1, 12)
            dimension = 6
            entities = []
            for i in range(n):
                vector = [rng.gauss(0, 1) for _ in range(dimension)]
                entities.append({"entity_id": f"e{rng.randint(0, 30):02d}", "descriptor_mean": unit(vector),
                                 "centroid_m": [rng.uniform(-2, 2) for _ in range(3)], "state": "active"})
            # unique ids, some deliberately tied descriptors
            seen = set()
            unique = []
            for e in entities:
                if e["entity_id"] in seen:
                    continue
                seen.add(e["entity_id"])
                unique.append(e)
            entities = unique
            if rng.random() < 0.3 and len(entities) >= 2:
                entities[1]["descriptor_mean"] = list(entities[0]["descriptor_mean"])
            memory = {"entities": entities}
            fragment = {"descriptor": unit([rng.gauss(0, 1) for _ in range(dimension)]),
                        "centroid_m": [rng.uniform(-2, 2) for _ in range(3)]}
            if rng.random() < 0.3:
                fragment["descriptor"] = list(entities[0]["descriptor_mean"])
            target = rng.choice(entities)["entity_id"]
            ranks = fd.recall_ranks(fragment, memory, target)
            for k in (1, 2, 3):
                for g in (0, 1, 2):
                    for r in (0.5, 1.5, 3.0):
                        expected = target in recall_for_fragment(fragment, memory, local_count=k, global_count=g, local_radius_m=r)
                        self.assertEqual(fd.recalled_at(ranks, local_count=k, global_count=g, local_radius_m=r), expected,
                                         msg=f"case {case} k={k} g={g} r={r}")

    def test_the_curve_counts_decisions_births_and_memory_sizes(self) -> None:
        frames = synthetic_frames()
        curve = fd.recall_curve(frames)
        self.assertEqual(len(curve["grid_points"]), 5 * 5 * 5)
        labelled = sum(1 for f in frames for x in f["fragments"] if x["object"] is not None)
        self.assertEqual(curve["decisions_total"] + curve["births_total"], labelled)
        self.assertEqual(curve["births_total"], 5)
        self.assertEqual(curve["memory_size_max"], 5)
        # a generous global channel never misses; a tiny local radius with no global channel misses a lot
        generous = next(r for r in curve["grid_points"] if r["global_count"] == 5 and r["local_count"] == 8)
        self.assertEqual(generous["recall_miss"], 0)
        strict = next(r for r in curve["grid_points"] if r["global_count"] == 0 and r["local_count"] == 1 and r["local_radius_m"] == 0.5)
        self.assertGreaterEqual(strict["recall_miss"], generous["recall_miss"])
        merged = fd.merge_recall_curves([curve, curve])
        self.assertEqual(merged["decisions_total"], 2 * curve["decisions_total"])
        self.assertEqual(merged["grid_points"][0]["decisions"], 2 * curve["grid_points"][0]["decisions"])
        self.assertIn("0.5", curve["birth_neighbourhood"])


class IoUStatisticsTests(unittest.TestCase):
    def test_gate_is_judged_on_the_truth_median_and_groups_are_reported(self) -> None:
        rows = [{"iou_truth": 0.2, "iou_proxy": 0.6, "pickupable": True, "receptacle": False},
                {"iou_truth": 0.25, "iou_proxy": None, "pickupable": False, "receptacle": True},
                {"iou_truth": 0.5, "iou_proxy": 0.9, "pickupable": False, "receptacle": False}]
        stats = fd.iou_statistics(rows)
        self.assertEqual(stats["truth"]["count"], 3)
        self.assertTrue(stats["median_below_gate"])
        self.assertEqual(stats["proxy_observed_set_box"]["count"], 2)
        self.assertEqual({k: v["count"] for k, v in stats["by_group"].items()}, {"pickupable": 1, "receptacle": 1, "other": 1})
        self.assertIsNone(fd.iou_statistics([])["median_below_gate"])
        self.assertEqual(fd.summarise([])["count"], 0)


class ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_the_contract_agrees_with_the_implementation(self) -> None:
        fd.validate_contract(self.contract)
        self.assertEqual(tuple(self.contract["policy_values_without_defaults"]),
                         tuple("reid_training." + name for name in fd.REID_VALUE_SLOTS))
        for name in fd.REID_VALUE_SLOTS:
            self.assertIsNone(self.contract["reid_training"][name])
        self.assertTrue(all(value is False for value in self.contract["authorization"].values()))
        self.assertIsNone(self.contract["activation_policy"])

    def test_changing_a_registered_constant_or_opening_a_bit_is_refused(self) -> None:
        for path, value, code in (
            ("recall_curve.grid.local_count", [1, 2, 3], "contract_recall_grid_mismatch"),
            ("separation.sampling_seed", 7, "contract_separation_sampling_mismatch"),
            ("fragment_truth_iou.gate_median_iou", 0.2, "contract_iou_gate_mismatch"),
            ("reid_training.output_dimension", 256, "contract_reid_dimension_mismatch"),
            ("reid_training.holdout.selection_houses", 10, "contract_reid_holdout_mismatch"),
            ("fragment_labelling.majority_share_exclusive", 0.4, "contract_majority_share_mismatch"),
            ("object_geometry.truth_box_rule", "observed_set_box", "contract_truth_box_rule_mismatch"),
            ("authorization.reid_adapter_head_training", True, "contract_bit_opened_without_a_ruling:reid_adapter_head_training"),
        ):
            broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
            node = broken
            parts = path.split(".")
            for part in parts[:-1]:
                node = node[part]
            node[parts[-1]] = value
            with self.assertRaises(fd.LeanDiagnosticsError, msg=path) as caught:
                fd.validate_contract(broken)
            self.assertEqual(str(caught.exception), code)
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["reid_training"]["temperature"] = 0.07
        with self.assertRaises(fd.LeanDiagnosticsError) as caught:
            fd.validate_contract(broken)
        self.assertEqual(str(caught.exception), "contract_reid_value_frozen_but_still_listed_as_open:temperature")


if __name__ == "__main__":
    unittest.main()
