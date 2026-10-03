#!/usr/bin/env python3
"""Ruling 88-2 reading: the step-0 package (decision ceiling, 2x2 attribution, the three probes) under the frozen rules.

白话：输入是第 0 步诊断包的全部产物——决定上限（teacher 当策略）六个确定性格的节点审计合并结果、2×2 两个混合格各 5 个种子的合并
结果、学习版（裁决 86 的 VSMT-lean 5 个种子）、开发表四个规则臂（LOG-270）的逐 house 报告，以及 P1／P2／P3 三个核验的输出；输出按
DECISIONS 裁决 88-2 事先冻结的读法给出的判读。
  * G0-a 词表价值：O-V-主列相对 O-A，Missing 残留率低 ≥ 0.05，身份连续率与全部重见物体接回比例各不低于 O-A 超过 0.05。
  * G0-b 版本价值：O-V-主列相对 O-N-主列，身份连续率高 ≥ 0.05。
  * G0-c 主门可达：O-V-主列的 Missing 残留率比四个规则臂里最低的低 ≥ 0.05，身份连续率比最高的高 ≥ 0.05。
  都在各自共同有效的 house 上按 house 配对取均值。判读：a 与 c 都过 → 进重设计；a 不过 → 先改主张或词表；a 过 c 不过 → 先裁主门或框架；
  b 不过 → 不主张保留档案的价值。归因：换成 teacher 关联、换成 teacher 存在各自关掉学习版到上限差距的比例，比例大的一侧排前面。
  P2：>100 帧两档对 1 帧档、观察次数 >100 两档对 1～10 档的中位 |Δlogit| 比值（五种子取中位），<0.1 证实、0.1～0.5 部分、≥0.5 不证实。
  P3：训练 house 上的分类均衡一致率 ≥0.99 能表达、0.95～0.99 部分、<0.95 不能。
例如 O-V-主列 Missing 残留率 0.02、O-A 0.30、RAC 0.089，身份连续率 0.80 对 0.78／0.149，则 a、c 都过。它不是显著性检验，也不选配置。

Usage:
  python ops/vsmt/ruling88_analysis.py --cell O-V-node:<merged> ... --mixed OA-LE:7:<merged> ... --learned 7:<merged> ...
      --rule-arm RAC:<development-table arm export> ... [--coverage <json>] [--sensitivity A7:<json> ...] [--imitation rac:<json> ...]
      --output <json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ruling82_seed_analysis as r82  # noqa: E402  (per-house report values, byte for byte)

STAGE = "vsmt.lean.ruling88.analysis.v1"
CELLS = ("O-V-node", "O-V-legacy", "O-N-node", "O-N-legacy", "O-A", "O-V-node-recall")
MIXED = ("OA-LE", "LA-OE")
SEEDS = (7, 19, 31, 43, 59)
RULE_ARMS = ("TAF", "ELU-P", "RAC", "LOW")
MARGIN = 0.05                      # ruling 88-2: G0-a/b/c margin, the learned arms' seed-to-seed scale
LAYERNORM_CONFIRMED, LAYERNORM_PARTIAL = 0.1, 0.5
IMITATION_PASS, IMITATION_PARTIAL = 0.99, 0.95
POSITIVE_CONTROLS = ("taf", "low", "handcost")
HISTORY_RULES = ("rac", "elup")
METRICS = {
    "node_f1": ("node_prf1", "node_f1", "higher"),
    "missing_residual_rate": ("missing_residual_rate", "missing_residual_rate", "lower"),
    "identity_continuity": ("identity_continuity", "identity_continuity", "higher"),
    "contamination_auc": ("contamination_auc", "contamination_auc", "lower"),
    "false_retract_rate_in_scope": ("false_retract_rate_in_scope", "false_retract_rate", "lower"),
}
MERGED_SCHEMAS = ("vsmt-s2-05-node-audit-merged-v7", "vsmt-s2-05-node-audit-merged-v8", "vsmt-s2-05-node-audit-merged-v9",
                  "vsmt-s2-05-node-audit-merged-v10", "vsmt-s2-05-node-audit-merged-v11", "vsmt-s2-05-node-audit-merged-v12")


def as_merged(payload: Mapping[str, Any]) -> dict[str, Any]:
    """A merged node audit as is, or a development-table arm export turned into the same per-episode report shape."""

    if payload.get("schema_version") in MERGED_SCHEMAS:
        return dict(payload)
    episodes = payload.get("episodes")
    if isinstance(episodes, dict):
        return {"per_episode": [{"episode_id": key, "report": row["report"]} for key, row in sorted(episodes.items())
                                if row.get("status") == "succeeded"]}
    raise ValueError("input_is_neither_a_merged_audit_nor_a_development_table_export")


def house_values(merged: Mapping[str, Any], metric: str) -> dict[str, float]:
    block, field, _ = METRICS[metric]
    return r82.house_values(merged, block, field)


def kept_share(merged: Mapping[str, Any]) -> float | None:
    rows = [r for e in merged.get("per_episode", []) for r in (e.get("identity_attribution") or [])]
    return (sum(r["category"] == "kept" for r in rows) / len(rows)) if rows else None


def paired(left: Mapping[str, Any], right: Mapping[str, Any], metric: str) -> dict[str, Any]:
    """Mean over the common valid houses of (left - right); both metric directions are reported as raw differences."""

    a, b = house_values(left, metric), house_values(right, metric)
    common = sorted(set(a) & set(b))
    return {"left_minus_right": statistics.fmean(a[h] - b[h] for h in common) if common else None, "houses": len(common)}


def advantage(left: Mapping[str, Any], right: Mapping[str, Any], metric: str) -> dict[str, Any]:
    """How much better left is than right on the common houses (positive = better, whichever the metric's direction)."""

    out = paired(left, right, metric)
    sign = 1.0 if METRICS[metric][2] == "higher" else -1.0
    out["advantage"] = None if out["left_minus_right"] is None else sign * out["left_minus_right"]
    return out


def g0(cells: Mapping[str, Mapping[str, Any]], rule_arms: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    v, a, n = cells["O-V-node"], cells["O-A"], cells["O-N-node"]
    mrr_vs_a = advantage(v, a, "missing_residual_rate")
    identity_vs_a = advantage(v, a, "identity_continuity")
    kept_v, kept_a = kept_share(v), kept_share(a)
    kept_vs_a = None if kept_v is None or kept_a is None else kept_v - kept_a
    g0a = bool(mrr_vs_a["advantage"] is not None and mrr_vs_a["advantage"] >= MARGIN
               and identity_vs_a["advantage"] is not None and identity_vs_a["advantage"] >= -MARGIN
               and kept_vs_a is not None and kept_vs_a >= -MARGIN)
    identity_vs_n = advantage(v, n, "identity_continuity")
    g0b = bool(identity_vs_n["advantage"] is not None and identity_vs_n["advantage"] >= MARGIN)
    per_arm = {arm: {"missing_residual_rate": advantage(v, merged, "missing_residual_rate"),
                     "identity_continuity": advantage(v, merged, "identity_continuity")} for arm, merged in sorted(rule_arms.items())}
    mrr_margins = [row["missing_residual_rate"]["advantage"] for row in per_arm.values()]
    identity_margins = [row["identity_continuity"]["advantage"] for row in per_arm.values()]
    g0c = bool(len(per_arm) == len(RULE_ARMS) and None not in mrr_margins and None not in identity_margins
               and min(mrr_margins) >= MARGIN and min(identity_margins) >= MARGIN)
    if g0a and g0c:
        decision = "proceed_to_the_redesign_track"
    elif not g0a:
        decision = "no_ceiling_for_the_lifecycle_vocabulary_ruling_on_claim_or_vocabulary_before_any_training"
    else:
        decision = "main_gate_out_of_reach_at_the_ceiling_ruling_on_the_gate_or_framing_before_any_training"
    return {"margin": MARGIN,
            "G0-a": {"pass": g0a, "missing_residual_rate_vs_O-A": mrr_vs_a, "identity_continuity_vs_O-A": identity_vs_a,
                     "kept_share_all_reobserved": {"O-V-node": kept_v, "O-A": kept_a, "difference": kept_vs_a}},
            "G0-b": {"pass": g0b, "identity_continuity_vs_O-N-node": identity_vs_n,
                     "reading": None if g0b else "the paper does not claim a value of keeping retracted archives"},
            "G0-c": {"pass": g0c, "per_rule_arm": per_arm,
                     "worst_margin": {"missing_residual_rate": min(mrr_margins) if None not in mrr_margins and mrr_margins else None,
                                      "identity_continuity": min(identity_margins) if None not in identity_margins and identity_margins else None}},
            "decision": decision}


def attribution(oracle: Mapping[str, Any], learned: Mapping[int, Mapping[str, Any]], mixed: Mapping[str, Mapping[int, Mapping[str, Any]]],
                metric: str) -> dict[str, Any]:
    """Share of the learned-to-ceiling gap closed by the teacher's association (OA-LE) and by the teacher's existence (LA-OE)."""

    runs = [oracle, *learned.values(), *mixed.get("OA-LE", {}).values(), *mixed.get("LA-OE", {}).values()]
    common = set(house_values(oracle, metric))
    for run in runs:
        common &= set(house_values(run, metric))
    if not common or not learned or not mixed.get("OA-LE") or not mixed.get("LA-OE"):
        return {"houses": len(common), "judged": False}

    def mean_of(run: Mapping[str, Any]) -> float:
        values = house_values(run, metric)
        return statistics.fmean(values[h] for h in sorted(common))

    sign = 1.0 if METRICS[metric][2] == "higher" else -1.0
    ceiling = mean_of(oracle)
    base = statistics.fmean(mean_of(r) for r in learned.values())
    oa = statistics.fmean(mean_of(r) for r in mixed["OA-LE"].values())
    oe = statistics.fmean(mean_of(r) for r in mixed["LA-OE"].values())
    gap = sign * (ceiling - base)
    shares = {"association": None, "existence": None}
    if abs(gap) > 1e-12:
        shares = {"association": sign * (oa - base) / gap, "existence": sign * (oe - base) / gap}
    leading = None
    if None not in shares.values():
        leading = "tie" if shares["association"] == shares["existence"] else max(shares, key=lambda k: shares[k])
    return {"houses": len(common), "judged": True, "ceiling": ceiling, "learned_mean_over_seeds": base,
            "teacher_association_learned_existence": oa, "learned_association_teacher_existence": oe,
            "gap_learned_to_ceiling": gap, "share_closed": shares, "leading_side": leading}


def sensitivity_reading(reports: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {"per_seed": {label: r["ratios"] for label, r in sorted(reports.items())}}
    for name in ("association_ticks_over_100_vs_1", "existence_observations_over_100_vs_1_to_10"):
        values = [r["ratios"][name] for r in reports.values() if r["ratios"].get(name) is not None]
        median = statistics.median(values) if values else None
        reading = None if median is None else ("layernorm_harm_confirmed" if median < LAYERNORM_CONFIRMED
                                               else "partial" if median < LAYERNORM_PARTIAL else "compensated_not_confirmed")
        out[name] = {"median_over_seeds": median, "reading": reading}
    return out


def imitation_reading(reports: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    def verdict(value: float | None) -> str | None:
        if value is None:
            return None
        return "representable" if value >= IMITATION_PASS else "partial" if value >= IMITATION_PARTIAL else "not_representable"

    per_target = {}
    for target, report in sorted(reports.items()):
        train = report["agreement"]["train"]["balanced_agreement"]
        per_target[target] = {"train_balanced_agreement": train, "selection_balanced_agreement": report["agreement"]["selection"]["balanced_agreement"],
                              "verdict": verdict(train), "positive_control": target in POSITIVE_CONTROLS, "diverged": report.get("diverged")}
    controls = [per_target[t]["verdict"] for t in POSITIVE_CONTROLS if t in per_target]
    history = [per_target[t]["verdict"] for t in HISTORY_RULES if t in per_target]
    if len(controls) < len(POSITIVE_CONTROLS) or len(history) < len(HISTORY_RULES):
        grid = "incomplete"
    elif any(v != "representable" for v in controls):
        grid = "encoding_or_optimisation_is_the_bottleneck"
    elif any(v != "representable" for v in history):
        grid = "history_is_missing"
    else:
        grid = "heads_sufficient_weakness_in_labels_or_data"
    return {"per_target": per_target, "reading": grid, "lines": {"representable": IMITATION_PASS, "partial": IMITATION_PARTIAL}}


def comparisons(cells: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    pairs = {"label_rule_V": ("O-V-legacy", "O-V-node"), "label_rule_N": ("O-N-legacy", "O-N-node"), "oracle_recall": ("O-V-node-recall", "O-V-node")}
    return {name: {metric: paired(cells[left], cells[right], metric) for metric in METRICS} for name, (left, right) in pairs.items()}


def cell_summary(merged: Mapping[str, Any]) -> dict[str, Any]:
    out = {metric: (statistics.fmean(v.values()) if (v := house_values(merged, metric)) else None) for metric in METRICS}
    out["houses"] = {metric: len(house_values(merged, metric)) for metric in METRICS}
    out["kept_share_all_reobserved"] = kept_share(merged)
    out["oracle"] = merged.get("oracle")
    return out


def analyse(cells: Mapping[str, Mapping[str, Any]], rule_arms: Mapping[str, Mapping[str, Any]], learned: Mapping[int, Mapping[str, Any]],
            mixed: Mapping[str, Mapping[int, Mapping[str, Any]]], coverage: Mapping[str, Any] | None,
            sensitivity: Mapping[str, Mapping[str, Any]], imitation: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    missing = [name for name in CELLS if name not in cells] + [arm for arm in RULE_ARMS if arm not in rule_arms]
    if missing:
        raise ValueError(f"inputs_missing:{missing}")
    return {
        "stage": STAGE,
        "cells": {name: cell_summary(cells[name]) for name in CELLS},
        "rule_arms": {arm: cell_summary(rule_arms[arm]) for arm in RULE_ARMS},
        "G0": g0(cells, rule_arms),
        "attribution_2x2": {metric: attribution(cells["O-V-node"], learned, mixed, metric)
                            for metric in ("missing_residual_rate", "identity_continuity")},
        "comparisons_reported_only": comparisons(cells),
        "P1_coverage": coverage,
        "P2_sensitivity": sensitivity_reading(sensitivity) if sensitivity else None,
        "P3_imitation": imitation_reading(imitation) if imitation else None,
    }


def _load(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cell", action="append", default=[], help="NAME:path, NAME in " + ", ".join(CELLS))
    parser.add_argument("--mixed", action="append", default=[], help="OA-LE|LA-OE:seed:path")
    parser.add_argument("--learned", action="append", default=[], help="seed:path (the ruling-86 VSMT-lean merges)")
    parser.add_argument("--rule-arm", action="append", default=[], help="ARM:path (development-table arm exports, LOG-270)")
    parser.add_argument("--coverage", default=None)
    parser.add_argument("--sensitivity", action="append", default=[], help="label:path")
    parser.add_argument("--imitation", action="append", default=[], help="target:path")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    inputs: dict[str, str] = {}

    def load(path: str) -> dict[str, Any]:
        inputs[path] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        return _load(path)

    cells = {spec.split(":", 1)[0]: as_merged(load(spec.split(":", 1)[1])) for spec in args.cell}
    rule_arms = {spec.split(":", 1)[0]: as_merged(load(spec.split(":", 1)[1])) for spec in args.rule_arm}
    learned = {int(spec.split(":", 1)[0]): as_merged(load(spec.split(":", 1)[1])) for spec in args.learned}
    mixed: dict[str, dict[int, dict[str, Any]]] = {}
    for spec in args.mixed:
        name, seed, path = spec.split(":", 2)
        mixed.setdefault(name, {})[int(seed)] = as_merged(load(path))
    sensitivity = {spec.split(":", 1)[0]: load(spec.split(":", 1)[1]) for spec in args.sensitivity}
    imitation = {spec.split(":", 1)[0]: load(spec.split(":", 1)[1]) for spec in args.imitation}
    coverage = load(args.coverage) if args.coverage else None
    out = analyse(cells, rule_arms, learned, mixed, coverage, sensitivity, imitation)
    out["inputs_sha256"] = inputs
    out["script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    Path(args.output).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({"G0": {k: out["G0"][k]["pass"] for k in ("G0-a", "G0-b", "G0-c")}, "decision": out["G0"]["decision"],
                      "attribution": {m: out["attribution_2x2"][m].get("leading_side") for m in out["attribution_2x2"]},
                      "P2": None if out["P2_sensitivity"] is None else {k: v["reading"] for k, v in out["P2_sensitivity"].items() if k != "per_seed"},
                      "P3": None if out["P3_imitation"] is None else out["P3_imitation"]["reading"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
