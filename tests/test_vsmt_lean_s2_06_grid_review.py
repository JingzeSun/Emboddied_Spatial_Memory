"""S2-06 tests: the grid review applies the ruling 100-2 decision points exactly as registered.

Pinned on hand-made histograms: the cosine and coverage crossings are the bin edges maximising the share difference, ties
go to the smallest edge, k/64 coverage starts at 1/64; the distance median is bracketed by exact shares at the grid's
finite endpoints; any judged grid out is exit 4, all inside exit 0; a calibration of the wrong mask source is refused.
Pinned on the committed instance-segmentation calibration (850c533): the registered rule puts its cosine crossing at
0.70 (inside TAF's {0.6, 0.7, 0.8}) but its same-object distance median below both distance grids and its coverage
crossing at 1/64, below both coverage grids -- the reading that pending ruling 101 is about.  CPU only, seconds.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for item in (PROJECT_ROOT / "src", PROJECT_ROOT / "tests", PROJECT_ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import s2_06_grid_review as review_module  # noqa: E402
from vsmt import lean_development as dev  # noqa: E402

REFERENCE = PROJECT_ROOT / "results" / "vsmt_lean_s2_05_calibration_oracle_850c533.json"


def report(mask_source: str, *, same_cosine, other_cosine, same_distance, gone, present, visible=(0.25,)) -> dict:
    collector = dev.CalibrationCollector()
    h = collector.histograms
    for name, values in (("same_object_cosine_to_mean", same_cosine), ("other_object_cosine_to_mean", other_cosine),
                         ("same_object_centroid_distance_m", same_distance), ("other_object_centroid_distance_m", (3.0,)),
                         ("gone_free_space_coverage_ratio", gone), ("present_free_space_coverage_ratio", present),
                         ("entity_should_be_visible_ratio", visible), ("present_should_be_visible_ratio", visible),
                         ("gone_should_be_visible_ratio", visible)):
        for value in values:
            h[name].add(value)
    return {"mask_source": mask_source, "frames": 10, "histograms": collector.to_json()["histograms"]}


GOOD = dict(same_cosine=(0.75, 0.85, 0.9, 0.95), other_cosine=(0.1, 0.3, 0.5, 0.65), same_distance=(0.4, 1.1, 1.3, 2.5),
            gone=(0.8, 0.9, 0.95, 0.99), present=(0.0, 0.1, 0.2, 0.3))


class TestDecisionPoints(unittest.TestCase):
    def test_crossings_are_bin_edges_and_ties_go_to_the_smallest(self) -> None:
        calibration = review_module.calibration_of(report("sam2", **GOOD))
        points = review_module.points(calibration)
        # every same-object cosine >= 0.66 and no other-object one: the difference is 1.0 from 0.66 to 0.74, the smallest wins
        self.assertAlmostEqual(points["cosine_crossing"]["point"], 0.66)
        self.assertEqual(points["cosine_crossing"]["difference"], 1.0)
        # gone all >= 0.8, present all < 0.31: the coverage difference reaches 1.0 first at 20/64
        self.assertEqual(points["coverage_crossing"]["point"], 20 / 64)
        self.assertEqual(points["coverage_crossing"]["difference"], 1.0)

    def test_all_inside_is_exit_0_and_any_out_is_exit_4(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sam2 = root / "sam2.json"
            out = root / "review.json"
            sam2.write_text(json.dumps(report("sam2", **GOOD)), encoding="utf-8")
            reference = root / "reference.json"
            reference.write_text(json.dumps(report("simulator_instance_masks", **GOOD)), encoding="utf-8")
            # the cosine crossing at 0.66 is inside [0.6, 0.8]; the distance median between 1.1 and 1.3 inside [0.5, 2] and
            # [0.25, 2]; the coverage crossing 20/64 = 0.3125 is below both coverage grids
            self.assertEqual(review_module.main(["--calibration", str(sam2), "--reference", str(reference), "--output", str(out)]), 4)
            result = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(result["out_of_grid"], ["RAC.rho_rac", "HandCost.rho_h"])
            inside = {**GOOD, "gone": (0.75, 0.8, 0.9, 0.99), "present": (0.0, 0.1, 0.2, 0.74)}
            sam2.write_text(json.dumps(report("sam2", **inside)), encoding="utf-8")
            self.assertEqual(review_module.main(["--calibration", str(sam2), "--reference", str(reference), "--output", str(out)]), 0)
            result = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(result["verdict"], "in_grid")
            self.assertEqual({row["check"]: row["sam2"]["side"] for row in result["checks"]},
                             {name: "inside" for name, *_ in review_module.JUDGED})

    def test_the_median_is_bracketed_by_exact_shares(self) -> None:
        far = {**GOOD, "same_distance": (2.1, 2.2, 2.3, 0.1)}
        calibration = review_module.calibration_of(report("sam2", **far))
        h = calibration["histograms"]["same_object_centroid_distance_m"]
        self.assertEqual(review_module.judge("distance_median", {}, (0.5, 2.0), h)["side"], "above")
        near = {**GOOD, "same_distance": (0.1, 0.15, 0.2, 3.0)}
        h = review_module.calibration_of(report("sam2", **near))["histograms"]["same_object_centroid_distance_m"]
        self.assertEqual(review_module.judge("distance_median", {}, (0.25, 2.0), h)["side"], "below")
        half = {**GOOD, "same_distance": (0.1, 0.2, 1.0, 1.5)}  # exactly half below 0.25: still bracketed
        h = review_module.calibration_of(report("sam2", **half))["histograms"]["same_object_centroid_distance_m"]
        self.assertEqual(review_module.judge("distance_median", {}, (0.25, 2.0), h)["side"], "inside")

    def test_the_wrong_mask_source_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a, b = root / "a.json", root / "b.json"
            a.write_text(json.dumps(report("simulator_instance_masks", **GOOD)), encoding="utf-8")
            b.write_text(json.dumps(report("simulator_instance_masks", **GOOD)), encoding="utf-8")
            self.assertEqual(review_module.main(["--calibration", str(a), "--reference", str(b), "--output", str(root / "o.json")]), 2)


class TestOnTheCommittedInstanceSegmentationCalibration(unittest.TestCase):
    def test_the_registered_rule_read_on_the_instance_segmentation_calibration(self) -> None:
        payload = json.loads(REFERENCE.read_text(encoding="utf-8"))
        self.assertEqual(payload["pass_receipt"]["mask_source"], "simulator_instance_masks")
        calibration = review_module.calibration_of(payload)
        result = review_module.review({**calibration, "mask_source": "sam2"}, calibration)
        rows = {row["check"]: row["simulator_instance_masks"] for row in result["checks"]}
        self.assertAlmostEqual(rows["TAF.theta_a"]["point"], 0.70)
        self.assertEqual(rows["TAF.theta_a"]["side"], "inside")
        self.assertEqual((rows["TAF.d_a"]["side"], rows["LOW.d_low"]["side"]), ("below", "below"))
        self.assertLess(rows["TAF.d_a"]["point"], 0.25)  # interpolated median about 0.19 m
        self.assertEqual(rows["RAC.rho_rac"]["point"], 1 / 64)
        self.assertEqual((rows["RAC.rho_rac"]["side"], rows["HandCost.rho_h"]["side"]), ("below", "below"))
        self.assertEqual(result["instance_segmentation_out_of_grid_under_the_same_rule"],
                         ["TAF.d_a", "LOW.d_low", "RAC.rho_rac", "HandCost.rho_h"])


if __name__ == "__main__":
    unittest.main()
