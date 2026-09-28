#!/usr/bin/env python3
"""Ruling 82-1 reading: the spread of five training seeds and the seed-paired VSMT-lean vs AssocOnly gaps (read-only).

白话：裁决 81 发现同一训练配方下，只换初始化和种子，VSMT-lean 与 AssocOnly 的节点 F1 先后就会翻转。这个脚本读两个臂各
5 个种子（登记的 7、19、31、43、59，都是“只用本臂轨迹、20 遍”的登记配方）的节点审计 v5 合并结果，对每个指标输出：
每个种子的 house 均值、5 个种子的均值与标准差；每个种子上 VSMT-lean 减 AssocOnly 的 house 均值差（按 house 配对）、
这 5 个差的均值、标准差和同号个数。按裁决 82 预登记的规则：至少 4 个种子的差同号，且差的均值绝对值大于 5 个差的标准差，
才算在开发集层面确定了先后；否则记为“开发集上分不出”。另把每个 house 先对 5 个种子取平均、再按 house 重抽样给出区间，
只作参考。例如节点 F1 的 5 个差是 +0.04、+0.07、−0.01、+0.03、+0.05，4 个同号、均值 0.036 大于标准差 0.030，就算确定；
LOG-270 那次旧初始化的训练只作参考列，不进判定。它不是显著性检验，也不替代正式 test。

Usage:
  python ops/vsmt/ruling82_seed_analysis.py --group VSMT-lean:7:<merged audit json> ... --group AssocOnly:59:<...> \
    [--reference-table results/vsmt_lean_s2_05_development_table_oracle_8ce7b0b.json] --output <json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
import sys
from pathlib import Path
from typing import Any, Mapping

ARMS = ("VSMT-lean", "AssocOnly")
SEEDS = (7, 19, 31, 43, 59)
#: metric -> (report block, headline field, direction in which larger is better)
METRICS = {
    "node_prf1": ("node_prf1", "node_f1", "higher"),
    "missing_residual_rate": ("missing_residual_rate", "missing_residual_rate", "lower"),
    "identity_continuity": ("identity_continuity", "identity_continuity", "higher"),
    "contamination_auc": ("contamination_auc", "contamination_auc", "lower"),
    "node_prf1_iou": ("node_prf1_iou", "node_f1", "higher"),
    "recovery_latency_frames": ("recovery_latency_frames", "recovery_latency_frames", "lower"),
}
VSMT_ONLY = {"false_retract_rate_in_scope": ("false_retract_rate_in_scope", "false_retract_rate", "lower"),
             "false_retract_rate": ("false_retract_rate", "false_retract_rate", "lower")}
RULE = ("82-1: for each metric the order of VSMT-lean and AssocOnly is established at the development level iff at least 4 of the 5 "
        "seed-paired gaps (house-mean difference on houses defined for both arms) share a strict sign and |mean gap| exceeds the "
        "sample standard deviation of the 5 gaps; otherwise it is recorded as not distinguishable on the development set")
BOOTSTRAP_SEED = 82
BOOTSTRAP_ITERATIONS = 10_000


def house_values(merged: Mapping[str, Any], block: str, field: str) -> dict[str, float]:
    out = {}
    for row in merged["per_episode"]:
        value = ((row.get("report") or {}).get(block) or {}).get(field)
        if value is not None:
            out[str(row["episode_id"])] = float(value)
    return out


def spread(values: list[float]) -> dict[str, Any]:
    return {"mean": statistics.fmean(values) if values else None, "sd": statistics.stdev(values) if len(values) > 1 else None,
            "min": min(values) if values else None, "max": max(values) if values else None}


def verdict(gaps: list[float], direction: str) -> dict[str, Any]:
    """The pre-registered 82-1 rule on the seed-paired gaps (VSMT-lean minus AssocOnly)."""

    positive, negative = sum(g > 0 for g in gaps), sum(g < 0 for g in gaps)
    mean = statistics.fmean(gaps)
    sd = statistics.stdev(gaps) if len(gaps) > 1 else None
    same_sign = max(positive, negative)
    established = bool(len(gaps) == len(SEEDS) and same_sign >= 4 and sd is not None and abs(mean) > sd)
    if not established:
        order = "not_distinguishable_on_the_development_set"
    else:
        vsmt_higher = mean > 0
        order = "VSMT-lean_better" if (vsmt_higher == (direction == "higher")) else "AssocOnly_better"
    return {"gaps": gaps, "positive": positive, "negative": negative, "mean_gap": mean, "sd_of_gaps": sd,
            "established": established, "order": order}


def bootstrap_interval(differences: list[float]) -> list[float] | None:
    if not differences:
        return None
    rng = random.Random(BOOTSTRAP_SEED)
    n = len(differences)
    means = sorted(sum(differences[rng.randrange(n)] for _ in range(n)) / n for _ in range(BOOTSTRAP_ITERATIONS))
    return [means[int(0.05 * (BOOTSTRAP_ITERATIONS - 1))], means[int(0.95 * (BOOTSTRAP_ITERATIONS - 1))]]


def analyse(groups: Mapping[tuple[str, int], Mapping[str, Any]], reference: Mapping[str, Any] | None = None) -> dict[str, Any]:
    for arm in ARMS:
        for seed in SEEDS:
            if (arm, seed) not in groups:
                raise ValueError(f"group_missing:{arm}:{seed}")
    out: dict[str, Any] = {"rule": RULE, "seeds": list(SEEDS), "metrics": {}, "vsmt_lean_only": {}}
    for metric, (block, field, direction) in METRICS.items():
        per_seed = {arm: {seed: house_values(groups[(arm, seed)], block, field) for seed in SEEDS} for arm in ARMS}
        means = {arm: {seed: (statistics.fmean(v.values()) if v else None) for seed, v in per_seed[arm].items()} for arm in ARMS}
        gaps = []
        for seed in SEEDS:
            v, a = per_seed["VSMT-lean"][seed], per_seed["AssocOnly"][seed]
            houses = sorted(set(v) & set(a))
            gaps.append(statistics.fmean(v[h] - a[h] for h in houses) if houses else 0.0)
        # context only: each house averaged over the seeds first, then a house-resampling interval of the difference
        averaged = {}
        for arm in ARMS:
            houses = set.intersection(*(set(per_seed[arm][seed]) for seed in SEEDS))
            averaged[arm] = {h: statistics.fmean(per_seed[arm][seed][h] for seed in SEEDS) for h in houses}
        common = sorted(set(averaged["VSMT-lean"]) & set(averaged["AssocOnly"]))
        differences = [averaged["VSMT-lean"][h] - averaged["AssocOnly"][h] for h in common]
        entry: dict[str, Any] = {
            "direction": direction,
            "house_mean_per_seed": {arm: {str(seed): means[arm][seed] for seed in SEEDS} for arm in ARMS},
            "seed_spread": {arm: spread([m for m in means[arm].values() if m is not None]) for arm in ARMS},
            "seed_paired_gaps": verdict(gaps, direction),
            "seed_averaged_house_difference_context_only": {"houses": len(common),
                                                            "mean": statistics.fmean(differences) if differences else None,
                                                            "interval_90": bootstrap_interval(differences)},
        }
        if reference is not None:
            per_house = ((reference.get("metrics") or {}).get(metric) or {}).get("per_house") or {}
            rows = [(r.get("VSMT-lean"), r.get("AssocOnly")) for r in per_house.values()]
            rows = [(x, y) for x, y in rows if x is not None and y is not None]
            entry["reference_log_270_old_initialisation_not_in_the_rule"] = (
                {"gap": statistics.fmean(x - y for x, y in rows), "houses": len(rows)} if rows else None)
        out["metrics"][metric] = entry
    for metric, (block, field, direction) in VSMT_ONLY.items():
        means = {seed: house_values(groups[("VSMT-lean", seed)], block, field) for seed in SEEDS}
        values = [statistics.fmean(v.values()) for v in means.values() if v]
        out["vsmt_lean_only"][metric] = {"direction": direction, "house_mean_per_seed": {str(s): (statistics.fmean(v.values()) if v else None)
                                                                                          for s, v in means.items()},
                                         "seed_spread": spread(values)}
    losses = {}
    for (arm, seed), merged in groups.items():
        tally = merged.get("pooled_loss_tally") or {}
        seen = int(tally.get("uncarried_seen_object_frames") or 0)
        wrong = int(((tally.get("intervals") or {}).get("wrong_bind") or {}).get("frames") or 0)
        losses[f"{arm}:{seed}"] = {"uncarried_seen_object_frames": seen, "wrong_bind_frame_share": (wrong / seen) if seen else None}
    out["loss_tally"] = losses
    out["summary"] = {m: e["seed_paired_gaps"]["order"] for m, e in out["metrics"].items()}
    out["caveat"] = ("development reading on the 39 development houses; five registered seeds per arm under the registered recipe with "
                     "the ruling 79-5 initialisation; the LOG-270 run (earlier initialisation) is shown as a reference only; not a "
                     "significance test, not a substitute for the formal test split")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--group", action="append", required=True, help="ARM:SEED:PATH of one merged node audit")
    parser.add_argument("--reference-table", default=None)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    groups, inputs = {}, {}
    for spec in args.group:
        arm, seed, path = spec.split(":", 2)
        file = Path(path)
        if not file.exists():
            print(f"[ruling82-analysis] refused: {file} missing", file=sys.stderr)
            return 2
        groups[(arm, int(seed))] = json.loads(file.read_text(encoding="utf-8"))
        inputs[f"{arm}:{seed}"] = {"file": file.name, "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
    reference = json.loads(Path(args.reference_table).read_text(encoding="utf-8")) if args.reference_table else None
    try:
        result = analyse(groups, reference)
    except ValueError as exc:
        print(f"[ruling82-analysis] refused: {exc}", file=sys.stderr)
        return 2
    output = {"stage": "vsmt.lean.s2_05.ruling82_seed_analysis.v1", "inputs": inputs,
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), **result}
    Path(args.output).write_text(json.dumps(output, indent=1), encoding="utf-8")
    print(json.dumps(output["summary"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
