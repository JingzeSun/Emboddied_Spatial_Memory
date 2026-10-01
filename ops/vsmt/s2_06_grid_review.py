#!/usr/bin/env python3
"""S2-06 grid review (ruling 100-2 step 2 as amended by ruling 101 (1)(a), ruling 84-2): does SAM2 need grids of its own?

白话：S0-05 的各臂网格是按实例分割校准趟的分位数定的（裁决 68，裁决 73／78 复核）。换成 SAM2 前端后，同一批校准量可能
挪位置。这个脚本读 SAM2 校准趟的合并直方图，按裁决 100-2 第 2 步事先写死的判定点逐项重算，并把实例分割校准趟
（`results/vsmt_lean_s2_05_calibration_oracle_850c533.json`）的同一量并排列出：
  * TAF θ_a（HandCost θ_b 网格与它相同、同一判定点）：取使“同物体余弦 ≥ c 的占比 − 异物体余弦 ≥ c 的占比”最大的 c；
  * TAF 距离门 d_a 与 LOW 的 d_low：取同物体质心距离的中位数；
  * RAC ρ_rac 与 HandCost ρ_h：取使“gone 行自由空间覆盖 ≥ ρ 的占比 − present 行覆盖 ≥ ρ 的占比”最大的 ρ；
  * 应可见下限：报应可见比例的分布（单个值没有端点可括，只报告）。
每个点先看它落在网格有限端点（最小与最大的有限值）的哪一侧：之下、之内或之上。裁决 101 (1)(a)（2026-10-01）：SAM2 的点落在
网格之外、而且与实例分割的点不在同一侧，才判“出界”——退出码 4，驱动写停止标记、停下，等用户另提按 mask_source 分存网格的
裁决，不边看边改；与实例分割同在网格外的同一侧，记“与实例分割同一状况”，不停，列给 S3-01 裁定（两套前端的这些网格要不要调）。
例如实例分割的同物体距离中位数约 0.19 m、在 LOW 网格 {0.25, …, 2.0} 之下，SAM2 若也在之下就不停；SAM2 若是 2.6 m、在之上，
就出界。原文（裁决 100-2）的绝对判定会把实例分割自己的 4 个网格也判为出界，所以改为相对判定；绝对读数仍列在报告里供阅读。
它不改网格、不选参，也不读任何指标。

操作化（运行前写死，见代码）：
  * 占比都是直方图箱边界上的精确占比（`Histogram.share_at_or_above`），不用箱内插值；c 取余弦箱边界 −1.00, −0.98, …，
    ρ 取 k/64（k = 1…63，k = 0 时两类都是 100%，不构成门）；最大值并列时取最小的 c 或 ρ；
  * 中位数是否落在 [lo, hi] 用精确占比判：share(d < lo) ≤ 0.5 ≤ share(d < hi)（lo、hi 都是 0.05 m 箱边界）；报告里另给
    箱内插值的中位数，只供阅读；
  * 只有两个及以上有限值的网格才有“端点”可括；ELU-P 与 RAC 的 θ_a {0.7}、d_a {无, 1.0} 是单值，只报告对应占比，不判。

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

    白话：输入两套前端各自落在网格的哪一侧（below／inside／above），输出这一项的判定：SAM2 在网格之内为 inside；SAM2 在网格外、
    实例分割在网格内或在另一侧，为 out_of_grid（停下另提裁决）；两者同在网格外的同一侧，为 same_side_as_instance_segmentation
    （不停，列给 S3-01）。例如实例分割与 SAM2 的覆盖交叉点都在 1/64、都在 RAC 网格之下，就是后者。它不判断哪套网格更好。
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
