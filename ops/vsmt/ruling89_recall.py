#!/usr/bin/env python3
"""Ruling 89-1 reading: the recall diagnostic on the decision-ceiling cell (O-V-node) and the frozen k' choice.

Input: merged node audits of the decision-ceiling cell (teacher association + teacher existence, node-primary-column labels)
at global candidate counts k' = 3, 5, 8, 12, 39 development episodes each. Output: (1) at k' = 3, the distribution of the
original entity's public rank in the global cosine order whenever it was not recalled; (2) per k', the first-re-observation
categories of the 65 moved objects (kept / original entity not recalled / BIRTH / bound to another entity / no pre-move
carrier) and the house means of the five ruling-88 metrics; (3) k' by the rule frozen in ruling 89-1: the first of
{5, 8, 12} with at most 3 of 65 recall misses; if none passes, pause for a new ruling, no larger k'. Example: 6 misses at
k' = 5 and 2 at k' = 8 give 8. Not a significance test; no learned arm is read and no recall value is changed (changing
S0-03 is a separate commit). Development stage (S2-R) only.

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
