"""S2-06 tests: the grid review applies the ruling 100-2 decision points and the ruling 101 (1)(a) verdict.

Pinned on hand-made histograms: the cosine and coverage crossings are the bin edges maximising the share difference, ties
go to the smallest edge, k/64 coverage starts at 1/64; the distance median is bracketed by exact shares at the grid's
finite endpoints; a SAM2 point outside its grid is out (exit 4) only where the instance-segmentation point is inside or on
the other side, and outside on the same side is listed for S3-01 (exit 0); a calibration of the wrong mask source is
refused.  Pinned on the committed instance-segmentation calibration (850c533): its cosine crossing is 0.70 (inside TAF's
{0.6, 0.7, 0.8}), its same-object distance median lies below both distance grids and its coverage crossing at 1/64 below
both coverage grids -- why ruling 101 (1)(a) judges SAM2 relative to it.  CPU only, seconds.
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
#: the same, with the coverage crossing at 48/64 = 0.75, inside both coverage grids
INSIDE = {**GOOD, "gone": (0.75, 0.8, 0.9, 0.99), "present": (0.0, 0.1, 0.2, 0.74)}


def run_review(root: Path, sam2: dict, reference: dict) -> tuple[int, dict]:
    paths = {name: root / f"{name}.json" for name in ("sam2", "reference", "review")}
    paths["sam2"].write_text(json.dumps(report("sam2", **sam2)), encoding="utf-8")
    paths["reference"].write_text(json.dumps(report("simulator_instance_masks", **reference)), encoding="utf-8")
    code = review_module.main(["--calibration", str(paths["sam2"]), "--reference", str(paths["reference"]), "--output", str(paths["review"])])
    return code, json.loads(paths["review"].read_text(encoding="utf-8"))


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

    def test_the_verdict_is_relative_to_instance_segmentation(self) -> None:
        # ruling 101 (1)(a): out only where SAM2 leaves the grid on a side instance segmentation does not
        self.assertEqual(review_module.verdict("inside", "below"), "inside")
        self.assertEqual(review_module.verdict("inside", "inside"), "inside")
        self.assertEqual(review_module.verdict("below", "below"), "same_side_as_instance_segmentation")
        self.assertEqual(review_module.verdict("above", "above"), "same_side_as_instance_segmentation")
        self.assertEqual(review_module.verdict("below", "inside"), "out_of_grid")
        self.assertEqual(review_module.verdict("above", "below"), "out_of_grid")

    def test_same_side_is_exit_0_and_listed_a_new_side_is_exit_4(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # both coverage crossings at 20/64, below both coverage grids: the same regime, listed for S3-01, not a stop
            code, result = run_review(root, GOOD, GOOD)
            self.assertEqual(code, 0)
            self.assertEqual(result["verdict"], "in_grid")
            self.assertEqual(result["same_side_as_instance_segmentation_for_s3_01"], ["RAC.rho_rac", "HandCost.rho_h"])
            self.assertEqual(result["outside_the_finite_endpoints_reading_only"]["sam2"], ["RAC.rho_rac", "HandCost.rho_h"])
            # instance segmentation inside, SAM2 below: SAM2 left the grid where instance segmentation did not -- stop
            code, result = run_review(root, GOOD, INSIDE)
            self.assertEqual(code, 4)
            self.assertEqual(result["out_of_grid"], ["RAC.rho_rac", "HandCost.rho_h"])
            # opposite sides: the same-object distance median above both distance grids for SAM2, below for instance segmentation
            code, result = run_review(root, {**INSIDE, "same_distance": (2.1, 2.2, 2.3, 0.1)}, {**INSIDE, "same_distance": (0.1, 0.15, 0.2, 3.0)})
            self.assertEqual(code, 4)
            self.assertEqual(result["out_of_grid"], ["TAF.d_a", "LOW.d_low"])
            # SAM2 inside everywhere: in grid whatever instance segmentation does
            code, result = run_review(root, INSIDE, GOOD)
            self.assertEqual(code, 0)
            self.assertEqual({row["check"]: row["verdict"] for row in result["checks"]}, {name: "inside" for name, *_ in review_module.JUDGED})
            self.assertEqual(result["same_side_as_instance_segmentation_for_s3_01"], [])

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
    def test_the_decision_points_of_the_instance_segmentation_calibration(self) -> None:
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
        outside = ["TAF.d_a", "LOW.d_low", "RAC.rho_rac", "HandCost.rho_h"]
        # the absolute reading of ruling 100-2 would judge four instance-segmentation grids out (why ruling 101 (1)(a) exists);
        # a SAM2 calibration in exactly this regime is in grid and the four go to S3-01
        self.assertEqual(result["outside_the_finite_endpoints_reading_only"]["simulator_instance_masks"], outside)
        self.assertEqual(result["out_of_grid"], [])
        self.assertEqual(result["same_side_as_instance_segmentation_for_s3_01"], outside)


if __name__ == "__main__":
    unittest.main()
