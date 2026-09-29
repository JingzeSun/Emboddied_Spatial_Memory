#!/usr/bin/env python3
"""Ruling 89-1 reading: the recall diagnostic on the decision-ceiling cell (O-V-node) and the frozen k' choice.

白话：输入是决定上限格（teacher 关联＋teacher 存在、节点主列标签）在全局候选数 k′ = 3、5、8、12 下各 39 条开发 episode 的合并节点审计，
输出三样东西：① k′=3 下每次“原实体没进召回”时原实体在全局余弦排序里的公开名次分布；② 每个 k′ 下 65 个搬动物体首次重见的分类计数
（接回／原实体没进召回／新建／绑到别的实体／搬动前已无承载）与五项指标的 house 均值；③ 按裁决 89-1 冻结的规则取 k′：{5, 8, 12} 里
第一个让漏召回 ≤ 3/65 的值；三个都不过即“暂停另提裁决”，不继续加大。例如 k′=5 漏 6 个、k′=8 漏 2 个，就取 8。它不是显著性检验，
不看学习臂，也不改任何召回值（改 S0-03 是另一个提交）。

Usage:
  python ops/vsmt/ruling89_recall.py --cell 3:<merged> --cell 5:<merged> --cell 8:<merged> --cell 12:<merged> --output <json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ruling88_analysis as r88  # noqa: E402

STAGE = "vsmt.lean.ruling89.recall.v1"
BASELINE_K = 3
CANDIDATE_KS = (5, 8, 12)          # ruling 89-1 (a): tried in this order, the first that passes is taken
MISS_LIMIT = 3                     # ruling 89-1 (a): recall misses on the ceiling cell at most 3 of the 65 moved objects
MISS_CATEGORY = "carrier_not_recalled"
RANK_BINS = ((4, 5), (6, 8), (9, 12), (13, 20), (21, 50), (51, None))


def records(merged: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(r) for e in merged.get("per_episode", []) for r in (e.get("identity_attribution") or [])]


def categories(rows: list[Mapping[str, Any]]) -> dict[str, int]:
    out = {name: 0 for name in ("kept", "carrier_gone", "carrier_not_recalled", "chose_birth", "chose_other_entity", "no_prior_carrier")}
    for row in rows:
        out[str(row["category"])] = out.get(str(row["category"]), 0) + 1
    return out


def rank_distribution(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    ranks = sorted(int(r["original_carrier_global_rank"]) for r in rows
                   if r["category"] == MISS_CATEGORY and r.get("original_carrier_global_rank") is not None)
    bins = {}
    for low, high in RANK_BINS:
        label = f"{low}-{high}" if high is not None else f">={low}"
        bins[label] = sum(1 for v in ranks if v >= low and (high is None or v <= high))
    misses = sum(1 for r in rows if r["category"] == MISS_CATEGORY)
    return {"misses": misses, "ranked": len(ranks), "ranks": ranks, "bins": bins,
            "covered_by_k": {str(k): sum(1 for v in ranks if v <= k) for k in CANDIDATE_KS},
            "median": statistics.median(ranks) if ranks else None,
            "entities_in_memory_at_miss": sorted(int(r["entities_in_memory"]) for r in rows
                                                 if r["category"] == MISS_CATEGORY and r.get("entities_in_memory") is not None)}


def metric_means(merged: Mapping[str, Any]) -> dict[str, Any]:
    out = {}
    for metric in r88.METRICS:
        values = r88.house_values(merged, metric)
        out[metric] = {"mean": statistics.fmean(values.values()) if values else None, "houses": len(values)}
    return out


def choose(miss_by_k: Mapping[int, int]) -> dict[str, Any]:
    for k in CANDIDATE_KS:
        if k in miss_by_k and miss_by_k[k] <= MISS_LIMIT:
            return {"chosen_k_prime": k, "decision": "set_k_prime_in_s0_03"}
    return {"chosen_k_prime": None,
            "decision": "no_candidate_passes_pause_and_propose_a_ruling_do_not_increase_further"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--cell", action="append", required=True, help="k:<merged O-V-node audit at that k'>")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    cells: dict[int, dict[str, Any]] = {}
    sources = {}
    for item in args.cell:
        k, path = item.split(":", 1)
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("recall_global_count") != int(k):
            raise SystemExit(f"cell {k} was merged from audits at k'={payload.get('recall_global_count')}")
        oracle = payload.get("oracle") or {}
        if not (oracle.get("association") and oracle.get("existence_rule") == "node_primary" and not oracle.get("recall")):
            raise SystemExit(f"cell {k} is not the O-V-node ceiling cell")
        cells[int(k)] = payload
        sources[k] = {"path": str(path), "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(), "episodes": payload["episodes"]}
    if BASELINE_K not in cells:
        raise SystemExit("the k'=3 cell is required for the rank distribution")
    per_k = {}
    miss_by_k = {}
    for k in sorted(cells):
        rows = records(cells[k])
        counted = categories(rows)
        miss_by_k[k] = counted[MISS_CATEGORY]
        per_k[str(k)] = {"reobserved_moved_objects": len(rows), "categories": counted, "metrics": metric_means(cells[k]),
                         "oracle_counts_recall_miss_births": sum(int(((e.get("oracle") or {}).get("counts") or {})
                                                                     .get("association_fallback_birth", {}).get("recall_miss", 0))
                                                                 for e in cells[k]["per_episode"])}
    result = {"stage": STAGE, "rule": {"candidates_in_order": list(CANDIDATE_KS), "miss_limit": MISS_LIMIT, "miss_category": MISS_CATEGORY,
                                       "cell": "O-V-node (teacher association + teacher existence, node-primary labels)",
                                       "source": "DECISIONS ruling 89-1 (a), approved 2026-09-30"},
              "rank_distribution_at_k3": rank_distribution(records(cells[BASELINE_K])),
              "per_k": per_k, **choose(miss_by_k), "inputs": sources, "private_ids_exported": False}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps({"misses_by_k": miss_by_k, "rank_bins_at_k3": result["rank_distribution_at_k3"]["bins"],
                      "chosen_k_prime": result["chosen_k_prime"], "decision": result["decision"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
