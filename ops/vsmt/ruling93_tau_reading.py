#!/usr/bin/env python3
"""Ruling 93, revised (a): the threshold-sensitivity reading of the teacher-association + new-existence cell.

白话：同一批五个头、同一个格（teacher 关联＋学习存在），τ_r 取 0.15／0.2／0.3（事先登记）加上已有的 0.5 作参照，逐种子列出
Missing 残留率、节点 F1、范围内假撤回率，以及每次决策在 teacher 标 present／gone 的候选上撤回的比例，并标出哪些 (τ, 种子)
同时满足 89-2 格的两条线。它只是阈值敏感性诊断：有达标点说明这批固定权重在这个开发诊断条件下有可行工作点，不证明其他问题
不存在；都不达标只说明这几个点没解决问题，不能推出头分不开。不据此选定正式阈值。

Usage:
  python ops/vsmt/ruling93_tau_reading.py --cell 0.15:7:<merged> ... --output <json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ruling88_analysis as r88  # noqa: E402

STAGE = "vsmt.lean.ruling93.tau_reading.v1"
MRR_LINE, NODE_F1_LINE = 0.05, 0.93
METRICS = ("missing_residual_rate", "node_f1", "false_retract_rate_in_scope")


def retract_rates(payload: dict[str, Any]) -> dict[str, float | None]:
    fields = payload["existence_tally_fields"]
    totals: dict[tuple[str, str], int] = {}
    for row in payload["pooled_existence_tally"]:
        record = dict(zip(fields, row[:-1]))
        key = (record["status"], record["decision"])
        totals[key] = totals.get(key, 0) + int(row[-1])
    out = {}
    for status in ("present", "gone"):
        retract, noop = totals.get((status, "RETRACT"), 0), totals.get((status, "NOOP"), 0)
        out[f"{status}_retracted_per_decision"] = retract / (retract + noop) if retract + noop else None
    return out


def seed_row(payload: dict[str, Any]) -> dict[str, Any]:
    merged = r88.as_merged(payload)
    row = {}
    for metric in METRICS:
        values = r88.house_values(merged, metric)
        row[metric] = statistics.fmean(values.values()) if values else None
    row.update(retract_rates(payload))
    row["meets_both_cell_lines"] = bool(row["missing_residual_rate"] is not None and row["node_f1"] is not None
                                        and row["missing_residual_rate"] <= MRR_LINE and row["node_f1"] >= NODE_F1_LINE)
    row["per_house_missing_residual"] = {e["episode_id"]: ((e.get("report") or {}).get("missing_residual_rate") or {}).get("missing_residual_rate")
                                         for e in merged["per_episode"]}
    return row


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cell", action="append", required=True, help="tau:seed:merged audit")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    table: dict[str, dict[str, Any]] = {}
    inputs = {}
    for item in args.cell:
        tau, seed, path = item.split(":", 2)
        inputs[path] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        table.setdefault(tau, {})[seed] = seed_row(json.loads(Path(path).read_text(encoding="utf-8")))
    summary = {}
    for tau, seeds in sorted(table.items(), key=lambda kv: float(kv[0])):
        means = {m: statistics.fmean(s[m] for s in seeds.values() if s[m] is not None) for m in METRICS}
        summary[tau] = {"seeds": len(seeds), "means": means,
                        "seed_mean_meets_both_lines": means["missing_residual_rate"] <= MRR_LINE and means["node_f1"] >= NODE_F1_LINE,
                        "seeds_meeting_both_lines": sorted(k for k, v in seeds.items() if v["meets_both_cell_lines"])}
    out = {"stage": STAGE, "role": "threshold-sensitivity diagnostic on the development cell; selects nothing",
           "lines": {"missing_residual_rate_at_most": MRR_LINE, "node_f1_at_least": NODE_F1_LINE},
           "summary": summary, "per_tau_per_seed": table, "inputs_sha256": inputs,
           "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    Path(args.output).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({tau: {"mrr": round(v["means"]["missing_residual_rate"], 3), "f1": round(v["means"]["node_f1"], 3),
                            "fr": round(v["means"]["false_retract_rate_in_scope"], 3), "seeds_ok": v["seeds_meeting_both_lines"]}
                      for tau, v in summary.items()}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
