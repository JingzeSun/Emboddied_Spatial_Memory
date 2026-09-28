#!/usr/bin/env python3
"""Ruling 81-2 / 81-3 reading of the controlled training: paired house comparisons with bootstrap intervals (read-only).

白话：输入是八组节点审计 v5 的合并结果（VSMT-lean 与 AssocOnly 各 A7、A19、B、C 四组，每组 39 条开发 episode），输出一个
判读 JSON。它按裁决 81-2 预登记的规则算：
  1. 聚合是否改善 VSMT-lean：B 对 C 的节点 F1，按 house 配对的均值、分布与 90% 重抽样区间；区间下端 > 0 且均值超过
     种子噪声（同一臂 A7 对 A19 的配对均值差的绝对值）才算改善；
  2. 生命周期的相对价值：VSMT-lean 对 AssocOnly 的差距，B 条件对 C 条件（“缩小一半”只作开发目标）；
  3. 保护指标（Missing 残留率、身份连续率、污染 AUC、范围内假撤回率）：B 相对 C 往坏的方向的配对均值不超过该指标的
     种子噪声，才算“没有变差”；
  4. 1 与 3 同时满足才判“累积有效”。
另汇总裁决 81-3 的失去承载事件与缺失时长。例如 B 比 C 的节点 F1 高 0.03、区间 [0.01, 0.05]、种子噪声 0.004，且四个保护
指标都在噪声内，就判有效。它不是显著性检验：单个 seed、反复看过的开发集，结论只是开发读数，确认要等新 house。

Usage:
  python ops/vsmt/ruling81_analysis.py --results-dir results --commit <short> --output results/vsmt_lean_s2_05_ruling81_analysis_<short>.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ARMS = ("VSMT-lean", "AssocOnly")
CONDITIONS = ("A7", "A19", "B", "C")
BOOTSTRAP_SEED = 81
BOOTSTRAP_ITERATIONS = 10_000
INTERVAL = (0.05, 0.95)
#: metric -> (report block, headline field, direction in which larger is better)
PRIMARY = ("node_prf1", "node_f1", "higher")
PROTECTIVE = {
    "missing_residual_rate": ("missing_residual_rate", "missing_residual_rate", "lower"),
    "identity_continuity": ("identity_continuity", "identity_continuity", "higher"),
    "contamination_auc": ("contamination_auc", "contamination_auc", "lower"),
    "false_retract_rate_in_scope": ("false_retract_rate_in_scope", "false_retract_rate", "lower"),
}
SECONDARY = {
    "node_prf1_iou": ("node_prf1_iou", "node_f1", "higher"),
    "false_retract_rate": ("false_retract_rate", "false_retract_rate", "lower"),
    "recovery_latency_frames": ("recovery_latency_frames", "recovery_latency_frames", "lower"),
}
RULE = ("81-2: improved iff the 90% paired bootstrap interval of VSMT-lean B-C node F1 lies above 0 and its mean exceeds the seed noise "
        "|mean(A7-A19)| of VSMT-lean node F1; a protective metric is not worse iff the paired B-C mean in the worse direction is at most "
        "its VSMT-lean seed noise; effective iff improved and every protective metric not worse; the gap halving (|gap_B| <= 0.5 |gap_C|) "
        "is a development target, reported but not part of the verdict")


def group_name(arm: str, condition: str) -> str:
    return f"{arm}-{condition}"


def house_values(merged: Mapping[str, Any], block: str, field: str) -> dict[str, float]:
    """Headline value per house (episode) of one metric; houses where it is undefined are left out."""

    out = {}
    for row in merged["per_episode"]:
        value = ((row.get("report") or {}).get(block) or {}).get(field)
        if value is not None:
            out[str(row["episode_id"])] = float(value)
    return out


def paired(left: Mapping[str, float], right: Mapping[str, float]) -> list[float]:
    return [left[house] - right[house] for house in sorted(set(left) & set(right))]


def bootstrap_interval(differences: Sequence[float], *, seed: int = BOOTSTRAP_SEED, iterations: int = BOOTSTRAP_ITERATIONS) -> list[float] | None:
    """Percentile interval of the mean paired difference under house resampling with replacement."""

    if not differences:
        return None
    rng = random.Random(seed)
    n = len(differences)
    means = sorted(sum(differences[rng.randrange(n)] for _ in range(n)) / n for _ in range(iterations))
    return [means[int(INTERVAL[0] * (iterations - 1))], means[int(INTERVAL[1] * (iterations - 1))]]


def summarise(differences: Sequence[float]) -> dict[str, Any]:
    if not differences:
        return {"houses": 0, "mean": None, "interval_90": None}
    ordered = sorted(differences)
    return {"houses": len(differences), "mean": statistics.fmean(differences), "median": statistics.median(differences),
            "min": ordered[0], "max": ordered[-1], "positive": sum(d > 0 for d in differences), "negative": sum(d < 0 for d in differences),
            "interval_90": bootstrap_interval(differences)}


def worse_direction(differences: Sequence[float], direction: str) -> list[float]:
    """B-C differences turned so that a positive value means B is worse."""

    return [-d for d in differences] if direction == "higher" else list(differences)


def analyse(groups: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """The pre-registered reading of ruling 81-2 on the eight merged audits, plus the 81-3 loss summary."""

    for arm in ARMS:
        for condition in CONDITIONS:
            if group_name(arm, condition) not in groups:
                raise ValueError(f"group_missing:{group_name(arm, condition)}")
    metrics = {"node_prf1": PRIMARY, **PROTECTIVE, **SECONDARY}
    values = {g: {m: house_values(groups[g], block, field) for m, (block, field, _) in metrics.items()} for g in groups}
    means = {g: {m: (statistics.fmean(v.values()) if v else None) for m, v in per.items()} for g, per in values.items()}
    noise = {arm: {m: (abs(statistics.fmean(d)) if (d := paired(values[group_name(arm, "A7")][m], values[group_name(arm, "A19")][m])) else None)
                   for m in metrics} for arm in ARMS}

    v_b, v_c = group_name("VSMT-lean", "B"), group_name("VSMT-lean", "C")
    primary = summarise(paired(values[v_b]["node_prf1"], values[v_c]["node_prf1"]))
    floor = noise["VSMT-lean"]["node_prf1"]
    improved = bool(primary["interval_90"] and primary["interval_90"][0] > 0 and floor is not None and primary["mean"] > floor)

    protective = {}
    for metric, (_, _, direction) in PROTECTIVE.items():
        worse = worse_direction(paired(values[v_b][metric], values[v_c][metric]), direction)
        summary = summarise(worse)
        limit = noise["VSMT-lean"][metric]
        not_worse = None if summary["mean"] is None or limit is None else bool(summary["mean"] <= limit)
        protective[metric] = {"b_minus_c_in_the_worse_direction": summary, "seed_noise": limit, "not_worse": not_worse}

    def gap(condition: str) -> dict[str, float]:
        v, a = values[group_name("VSMT-lean", condition)]["node_prf1"], values[group_name("AssocOnly", condition)]["node_prf1"]
        return {house: v[house] - a[house] for house in sorted(set(v) & set(a))}

    gaps = {condition: gap(condition) for condition in CONDITIONS}
    gap_means = {condition: (statistics.fmean(g.values()) if g else None) for condition, g in gaps.items()}
    gap_change = summarise(paired(gaps["B"], gaps["C"]))
    halved = (None if gap_means["B"] is None or gap_means["C"] is None
              else bool(abs(gap_means["B"]) <= 0.5 * abs(gap_means["C"])))
    effective = improved and all(row["not_worse"] is True for row in protective.values())

    losses = {}
    for name, merged in groups.items():
        tally = merged.get("pooled_loss_tally") or {}
        seen = int(tally.get("uncarried_seen_object_frames") or 0)
        intervals = tally.get("intervals") or {}
        events: dict[str, int] = {}
        for cause, _klass, count in tally.get("events") or []:
            events[cause] = events.get(cause, 0) + int(count)
        losses[name] = {"events_by_cause": dict(sorted(events.items())), "uncarried_seen_object_frames": seen,
                        "uncarried_without_loss_event_frames": int(tally.get("uncarried_without_loss_event_frames") or 0),
                        "interval_frames_by_cause": {cause: int(row["frames"]) for cause, row in sorted(intervals.items())},
                        "wrong_bind_frame_share": (int((intervals.get("wrong_bind") or {}).get("frames") or 0) / seen) if seen else None,
                        "wrong_bind_or_mixed_frame_share": ((int((intervals.get("wrong_bind") or {}).get("frames") or 0)
                                                             + int((intervals.get("mixed_with_wrong_bind") or {}).get("frames") or 0)) / seen) if seen else None}

    # context only, not part of the verdict: one seed pair is a single draw of the seed effect, so its per-house spread is shown too
    noise_detail = {arm: {m: summarise(paired(values[group_name(arm, "A7")][m], values[group_name(arm, "A19")][m])) for m in metrics}
                    for arm in ARMS}
    return {"rule": RULE, "bootstrap": {"seed": BOOTSTRAP_SEED, "iterations": BOOTSTRAP_ITERATIONS, "interval": list(INTERVAL), "unit": "house"},
            "house_means": means, "seed_noise": noise, "seed_noise_detail_not_in_the_verdict": noise_detail,
            "aggregation_improves_vsmt_lean": {"b_minus_c_node_f1": primary, "seed_noise": floor, "improved": improved},
            "lifecycle_gap_to_assoconly": {"mean_gap": gap_means, "gap_b_minus_gap_c": gap_change, "halved_development_target": halved},
            "protective_metrics": protective,
            "assoconly_b_minus_c_node_f1": summarise(paired(values[group_name("AssocOnly", "B")]["node_prf1"], values[group_name("AssocOnly", "C")]["node_prf1"])),
            "verdict": {"effective": effective, "improved": improved,
                        "protective_not_worse": {m: row["not_worse"] for m, row in protective.items()}},
            "loss_tally": losses,
            "caveat": "development reading on the 39 development houses with one training seed per condition (A19 only for the noise floor); "
                      "not a significance test; confirmation on the frozen confirmation houses after the method is frozen (ruling 81-1)"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--commit", required=True, help="the short commit in the merged audit file names")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    groups, inputs = {}, {}
    for arm in ARMS:
        for condition in CONDITIONS:
            name = group_name(arm, condition)
            path = Path(args.results_dir) / f"vsmt_lean_s2_05_node_audit_ruling81_{name}_{args.commit}.json"
            if not path.exists():
                print(f"[ruling81-analysis] refused: {path} missing", file=sys.stderr)
                return 2
            groups[name] = json.loads(path.read_text(encoding="utf-8"))
            inputs[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    output = {"stage": "vsmt.lean.s2_05.ruling81_analysis.v1", "inputs": inputs,
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), **analyse(groups)}
    Path(args.output).write_text(json.dumps(output, indent=1), encoding="utf-8")
    print(json.dumps({"verdict": output["verdict"], "b_minus_c": output["aggregation_improves_vsmt_lean"],
                      "gap": output["lifecycle_gap_to_assoconly"]["mean_gap"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
