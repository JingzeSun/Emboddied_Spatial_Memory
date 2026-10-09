#!/usr/bin/env python3
"""S2-06 grid review (ruling 100-2 step 2 as amended by ruling 101 (1)(a), ruling 84-2): does SAM2 need grids of its own?

The S0-05 arm grids were set from quantiles of the instance-segmentation calibration pass (ruling 68, reviewed by rulings
73/78); on the SAM2 front end the same calibration quantities may shift. This script reads the merged histograms of the SAM2
calibration pass, recomputes each decision point fixed in advance by ruling 100-2 step 2, and lists the same quantity of the
instance-segmentation calibration pass (`results/vsmt_lean_s2_05_calibration_oracle_850c533.json`) beside it:
  * TAF theta_a (HandCost's theta_b grid is the same, with the same decision point): the c maximising
    share(same-object cosine >= c) - share(different-object cosine >= c);
  * TAF distance gate d_a and LOW's d_low: the median same-object centroid distance;
  * RAC rho_rac and HandCost rho_h: the rho maximising share(gone-row free-space coverage >= rho) - share(present-row
    coverage >= rho);
  * should-be-visible floor: the distribution of the should-be-visible ratio (a single value has no endpoints; reported only).
Each point is first placed relative to the grid's finite endpoints (smallest and largest finite value): below, inside or
above. Ruling 101 (1)(a) (2026-10-01): a SAM2 point is "out of grid" only if it lies outside the grid on a side where the
instance-segmentation point does not; then exit 4, the driver writes a stop marker and halts for a separate ruling that
stores grids per mask_source (no change while looking). Outside on the same side as instance segmentation is recorded as
"same as instance segmentation", without a stop, and listed for S3-01 to rule on (whether to adjust these grids for both
front ends). Example: the instance-segmentation same-object distance median is about 0.19 m, below the LOW grid
{0.25, ..., 2.0}; a SAM2 median also below does not stop, one of 2.6 m (above) is out of grid. The absolute test of the
original ruling 100-2 would also put 4 of instance segmentation's own grids out, hence the relative test; the absolute
readings stay in the report for reference. No grid is changed, no parameter selected and no metric read. S3-03 runs the same
script on its two S3 calibration passes as a report-only job (`grid-reading`; ruling 102-6 keeps the grids, so exit 4 does
not stop that run).

Operationalisation (fixed before the run; see the code):
  * every share is an exact share at a histogram bin edge (`Histogram.share_at_or_above`), no within-bin interpolation;
    c ranges over the cosine bin edges -1.00, -0.98, ..., rho over k/64 (k = 1..63; at k = 0 both classes are 100%, no
    gate); ties take the smallest c or rho;
  * whether the median is within [lo, hi] is decided by exact shares: share(d < lo) <= 0.5 <= share(d < hi) (lo and hi are
    0.05 m bin edges); an interpolated median is reported for reading only;
  * only grids with two or more finite values have endpoints; the single-value grids of ELU-P and RAC (theta_a {0.7},
    d_a {none, 1.0}) are reported as shares, not judged.

Usage:
  python ops/vsmt/s2_06_grid_review.py --calibration <S2-06 calibration_report.json> \
      --reference results/vsmt_lean_s2_05_calibration_oracle_850c533.json --output <json>
Exit codes: 0 no grid is out by ruling 101 (1)(a); 4 at least one is out of grid; 2 refused input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vsmt import lean_arms as arms  # noqa: E402
from vsmt import lean_development as dev  # noqa: E402

STAGE = "vsmt.lean.s2_06.grid_review.v2"
RULE = ("ruling 100-2 step 2 (registered before the run): the ruling-68 calibration quantity of each grid recomputed on SAM2 and "
        "set beside the instance-segmentation value; TAF theta_a at the c maximising share(same-object cosine >= c) - "
        "share(other-object cosine >= c); the distance gate and LOW at the same-object distance median; RAC rho_rac and HandCost "
        "rho_h at the rho maximising share(gone coverage >= rho) - share(present coverage >= rho); the should-be-visible minimum "
        "against the should-be-visible distribution, reported only. Ruling 101 (1)(a) (2026-10-01, before any SAM2 data): each point "
        "is below, inside or above its grid's finite endpoints; a SAM2 point outside the grid on a side the instance-segmentation "
        "point is not on is out of grid: stop and propose a ruling storing grids per mask_source before the fit and the rule arms "
        "run; a SAM2 point outside on the same side as the instance-segmentation point is the same regime and goes to S3-01; never "
        "adjusted while looking")
OUT_OF_GRID_EXIT = 4
SAM2, INSTANCE = "sam2", "simulator_instance_masks"
#: (check name, grid owner arm, grid parameter, decision point) -- every grid the registered rule judges
JUDGED = (
    ("TAF.theta_a", "TAF", "theta_a", "cosine_crossing"),
    ("HandCost.theta_b", "HandCost", "theta_b", "cosine_crossing"),
    ("TAF.d_a", "TAF", "d_a", "distance_median"),
    ("LOW.d_low", "LOW", "d_low", "distance_median"),
    ("RAC.rho_rac", "RAC", "rho_rac", "coverage_crossing"),
    ("HandCost.rho_h", "HandCost", "rho_h", "coverage_crossing"),
)
#: single-value grids: no endpoints to bracket, reported only
REPORTED = (("ELU-P.theta_a", "ELU-P", "theta_a"), ("RAC.theta_a", "RAC", "theta_a"),
            ("ELU-P.d_a", "ELU-P", "d_a"), ("RAC.d_a", "RAC", "d_a"))


def calibration_of(payload: Mapping[str, Any]) -> dict[str, Any]:
    """A merged calibration report, either as ``calibration-report`` writes it or inside a ``lean_s2_05_export`` file."""

    report = payload.get("calibration_report", payload)
    if not isinstance(report, Mapping) or "histograms" not in report:
        raise ValueError("no merged calibration histograms in the input")
    source = report.get("mask_source") or (payload.get("pass_receipt") or {}).get("mask_source")
    histograms = {name: dev.Histogram.from_json(spec) for name, spec in report["histograms"].items()}
    missing = [name for name in dev.CALIBRATION_SERIES if name not in histograms]
    if missing:
        raise ValueError(f"calibration series missing: {missing}")
    for name, histogram in histograms.items():
        if name in dev.CALIBRATION_SERIES and tuple(histogram.edges) != tuple(float(v) for v in dev.CALIBRATION_SERIES[name]):
            raise ValueError(f"calibration series {name} has other bin edges")
    return {"mask_source": source, "frames": report.get("frames"), "histograms": histograms}


def crossing(above: dev.Histogram, below: dev.Histogram, indices: range) -> dict[str, Any]:
    """The bin edge maximising share(above >= x) - share(below >= x); ties go to the smallest x."""

    best_index, best = None, None
    for index in indices:
        gap = above.share_at_or_above(index) - below.share_at_or_above(index)
        if best is None or gap > best:
            best_index, best = index, gap
    x = above.edges[best_index]
    return {"point": x, "difference": best, "share_first": above.share_at_or_above(best_index),
            "share_second": below.share_at_or_above(best_index), "rows_first": above.total, "rows_second": below.total}


def share_below(histogram: dev.Histogram, x: float) -> float:
    """Exact share of values below a bin edge x."""

    index = [round(edge, 6) for edge in histogram.edges].index(round(float(x), 6))
    return 1.0 - histogram.share_at_or_above(index)


def finite_span(values: list[Any]) -> tuple[float, float] | None:
    finite = sorted(float(v) for v in values if v is not None)
    return (finite[0], finite[-1]) if len(finite) >= 2 else None


def points(calibration: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """The three registered decision points of one front end."""

    h = calibration["histograms"]
    cosine = h["same_object_cosine_to_mean"]
    distance = h["same_object_centroid_distance_m"]
    return {
        "cosine_crossing": crossing(cosine, h["other_object_cosine_to_mean"], range(len(cosine.counts))),
        "distance_median": {"point": distance.quantile(0.5), "point_method": "linear_within_0.05_m_bin_reading_only",
                            "rows": distance.total},
        "coverage_crossing": crossing(h["gone_free_space_coverage_ratio"], h["present_free_space_coverage_ratio"], range(1, 64)),
    }


def judge(point_kind: str, point: Mapping[str, Any], span: tuple[float, float], distance: dev.Histogram) -> dict[str, Any]:
    lo, hi = span
    if point_kind == "distance_median":  # exact: the median is within [lo, hi] iff share(d < lo) <= 0.5 <= share(d < hi)
        below_lo, below_hi = share_below(distance, lo), share_below(distance, hi)
        inside = below_lo <= 0.5 <= below_hi
        side = "inside" if inside else ("below" if below_lo > 0.5 else "above")
        return {"inside": inside, "side": side, "share_below_lo": below_lo, "share_below_hi": below_hi}
    x = float(point["point"])
    side = "below" if x < lo else ("above" if x > hi else "inside")
    return {"inside": side == "inside", "side": side}


def verdict(sam2_side: str, instance_side: str) -> str:
    """Ruling 101 (1)(a): SAM2 needs a grid of its own only where it leaves the grid on a side instance segmentation does not.

    Input: the side of the grid (below / inside / above) for each front end. Output: inside if SAM2 is inside; out_of_grid
    (stop for a ruling) if SAM2 is outside and instance segmentation is inside or on the other side;
    same_side_as_instance_segmentation (no stop, listed for S3-01) if both are outside on the same side. Example: both
    coverage crossings at 1/64, below the RAC grid, give the last. It does not judge which grid is better.
    """

    if sam2_side == "inside":
        return "inside"
    return "same_side_as_instance_segmentation" if sam2_side == instance_side else "out_of_grid"


def review(sam2: Mapping[str, Any], reference: Mapping[str, Any]) -> dict[str, Any]:
    fronts = {SAM2: sam2, INSTANCE: reference}
    by_front = {name: points(calibration) for name, calibration in fronts.items()}
    checks = []
    for name, arm, parameter, kind in JUDGED:
        grid = list(arms.FROZEN_GRIDS[arm][parameter])
        span = finite_span(grid)
        row = {"check": name, "grid": grid, "endpoints": list(span), "decision_point": kind}
        for front, calibration in fronts.items():
            row[front] = {**by_front[front][kind], **judge(kind, by_front[front][kind], span, calibration["histograms"]["same_object_centroid_distance_m"])}
        row["verdict"] = verdict(row[SAM2]["side"], row[INSTANCE]["side"])
        checks.append(row)
    reported = []
    for name, arm, parameter in REPORTED:
        grid = list(arms.FROZEN_GRIDS[arm][parameter])
        row = {"check": name, "grid": grid, "judged": False, "why": "a single finite value has no endpoints to bracket"}
        for front, calibration in fronts.items():
            h = calibration["histograms"]
            if parameter == "theta_a":
                index = [round(e, 6) for e in h["same_object_cosine_to_mean"].edges].index(round(float(grid[0]), 6))
                row[front] = {"same_object_share_at_or_above": h["same_object_cosine_to_mean"].share_at_or_above(index),
                              "other_object_share_at_or_above": h["other_object_cosine_to_mean"].share_at_or_above(index)}
            else:
                gate = [v for v in grid if v is not None][0]
                row[front] = {"same_object_share_below": share_below(h["same_object_centroid_distance_m"], gate),
                              "other_object_share_below": share_below(h["other_object_centroid_distance_m"], gate)}
        reported.append(row)
    visibility = {"judged": False, "why": "the should-be-visible minimum is one value, not a grid; reported beside the distribution",
                  "minimum": arms.SHOULD_BE_VISIBLE_MIN_RATIO}
    for front, calibration in fronts.items():
        h = calibration["histograms"]
        visibility[front] = {
            "entity_frames_at_or_above_the_minimum": h["entity_should_be_visible_ratio"].share_at_or_above(1),
            "present_rows_below_4_of_64": 1.0 - h["present_should_be_visible_ratio"].share_at_or_above(4),
            "gone_rows_below_4_of_64": 1.0 - h["gone_should_be_visible_ratio"].share_at_or_above(4),
            "present_rows_median": h["present_should_be_visible_ratio"].quantile(0.5),
            "gone_rows_median": h["gone_should_be_visible_ratio"].quantile(0.5),
        }
    out_of_grid = [row["check"] for row in checks if row["verdict"] == "out_of_grid"]
    same_side = [row["check"] for row in checks if row["verdict"] == "same_side_as_instance_segmentation"]
    return {
        "rule": RULE,
        "checks": checks,
        "reported_only": reported,
        "should_be_visible_minimum": visibility,
        "out_of_grid": out_of_grid,
        "verdict": "out_of_grid" if out_of_grid else "in_grid",
        "same_side_as_instance_segmentation_for_s3_01": same_side,
        "outside_the_finite_endpoints_reading_only": {front: [row["check"] for row in checks if not row[front]["inside"]] for front in fronts},
        "next": ("stop: propose a ruling storing grids per mask_source before the ELU-P fit and the rule arms run (ruling 100-2 step 2, "
                 "ruling 101 (1)(a))" if out_of_grid else
                 "register 'reviewed on SAM2' and continue with the ELU-P fit; the same-side checks go to S3-01 (ruling 101 (1)(a))"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--calibration", required=True, help="the SAM2 calibration report (calibration-report output or its export)")
    parser.add_argument("--reference", required=True, help="the instance-segmentation calibration export (results/...850c533.json)")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    inputs, loaded = {}, {}
    for role, path in (("sam2", Path(args.calibration)), ("reference", Path(args.reference))):
        if not path.exists():
            print(f"[s2-06-grid-review] refused: {path} missing", file=sys.stderr)
            return 2
        try:
            loaded[role] = calibration_of(json.loads(path.read_text(encoding="utf-8")))
        except ValueError as exc:
            print(f"[s2-06-grid-review] refused: {role}: {exc}", file=sys.stderr)
            return 2
        inputs[role] = {"file": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "mask_source": loaded[role]["mask_source"],
                        "frames": loaded[role]["frames"]}
    if loaded["sam2"]["mask_source"] != SAM2 or loaded["reference"]["mask_source"] != INSTANCE:
        print(f"[s2-06-grid-review] refused: expected a {SAM2} calibration and a {INSTANCE} reference, got "
              f"{loaded['sam2']['mask_source']} and {loaded['reference']['mask_source']}", file=sys.stderr)
        return 2
    result = review(loaded["sam2"], loaded["reference"])
    output = {"stage": STAGE, "inputs": inputs, "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), **result}
    Path(args.output).write_text(json.dumps(output, indent=1), encoding="utf-8")
    print(json.dumps({"verdict": result["verdict"], "out_of_grid": result["out_of_grid"],
                      "same_side_as_instance_segmentation_for_s3_01": result["same_side_as_instance_segmentation_for_s3_01"],
                      "points": {row["check"]: {front: row[front].get("point") for front in (SAM2, INSTANCE)} for row in result["checks"]}}, indent=1))
    return OUT_OF_GRID_EXIT if result["out_of_grid"] else 0


if __name__ == "__main__":
    sys.exit(main())
