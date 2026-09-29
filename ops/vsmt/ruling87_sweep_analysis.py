#!/usr/bin/env python3
"""Ruling 87-2 reading: the tau_r sweep on frozen heads, tier A (a feasible operating point) and tier B (reversibility).

白话：输入是 VSMT-lean 与 NoVersion 在 τ_r = 0.15／0.2／0.25／0.3 下、5 个种子、39 条开发 house 的节点审计 v8 合并结果，以及
裁决 86 已有的 VSMT-lean（τ_r=0.5）与 AssocOnly 合并结果；输出按裁决 87 修订版事前冻结的两层判读。
甲层（开发继续线，计入 81-1 的达标）：四档里至少一档同时满足——VSMT-lean 五种子 Missing 残留率均值 ≤ 0.178（LOG-270 最强规则臂 RAC
0.089 的两倍）；相对自己 τ_r=0.5 按种子配对，节点 F1 平均降幅 ≤ 0.03、全部重见物体接回比例平均降幅 ≤ 0.05；节点 F1 与接回比例都不被
82-1 规则判为 AssocOnly 更好。它只是继续线，不是论文主门。
乙层（可逆性证据，不计入达标）：在满足甲层且 Missing 残留率最低的那一档（并列取较大的 τ_r），VSMT-lean 的接回比例按 82-1 规则确定高于
NoVersion，且 VSMT-lean 接回、NoVersion 没接回的物体里过半是从“已撤回”状态接回的（NoVersion 会删掉已撤回实体，但保留休眠实体）。
例如 τ_r=0.2 时 Missing 残留率 0.16、F1 只降 0.01、接回比例降 0.02 且 AssocOnly 不更好，甲层成立；该档 VSMT-lean 多接回 9 个、其中 6 个从
已撤回接回、且五种子 5/5 同号，乙层成立。它不选最终档（S3 在 validation 上按 83-1 选），不是显著性检验，不替代正式 test。

Usage:
  python ops/vsmt/ruling87_sweep_analysis.py --sweep VSMT-lean:7:0.2:<merged json> ... --reference VSMT-lean:7:0.5:<json> \\
      --reference AssocOnly:7:-:<json> ... --output <json>
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
import ruling82_seed_analysis as r82  # noqa: E402  (the pre-registered 82-1 rule, reused byte for byte)

SEEDS = (7, 19, 31, 43, 59)
TAUS = (0.15, 0.2, 0.25, 0.3)
MRR_LINE = 0.178            # ruling 87-2: twice the strongest rule arm's Missing residual rate (RAC 0.0891, LOG-270)
F1_DROP_MAX = 0.03          # ruling 87-2: node F1 mean drop against the arm's own tau_r 0.5, about one seed-to-seed sd
KEPT_DROP_MAX = 0.05        # ruling 87-2: all-re-observed kept-share mean drop, about 3 of 65 move events per seed
HOUSE_METRICS = {"node_f1": ("node_prf1", "node_f1"), "missing_residual_rate": ("missing_residual_rate", "missing_residual_rate"),
                 "identity_continuity": ("identity_continuity", "identity_continuity"),
                 "false_retract_rate_in_scope": ("false_retract_rate_in_scope", "false_retract_rate"),
                 "contamination_auc": ("contamination_auc", "contamination_auc")}
MERGED_SCHEMAS = ("vsmt-s2-05-node-audit-merged-v7", "vsmt-s2-05-node-audit-merged-v8")


def house_values(merged: Mapping[str, Any], block: str, field: str) -> dict[str, float]:
    return r82.house_values(merged, block, field)


def records(merged: Mapping[str, Any]) -> dict[tuple[str, int], dict[str, Any]]:
    return {(str(e["episode_id"]), int(r["ordinal"])): r for e in merged["per_episode"] for r in (e.get("identity_attribution") or [])}


def kept_share(merged: Mapping[str, Any]) -> float | None:
    rows = records(merged)
    return (sum(r["category"] == "kept" for r in rows.values()) / len(rows)) if rows else None


def summary(merged: Mapping[str, Any]) -> dict[str, Any]:
    out = {name: (statistics.fmean(v.values()) if (v := house_values(merged, *spec)) else None) for name, spec in HOUSE_METRICS.items()}
    rows = records(merged)
    out["kept_share_all_reobserved"] = kept_share(merged)
    out["reobserved"] = len(rows)
    out["judged"] = sum(1 for r in rows.values() if r["judged"])
    out["no_prior_carrier"] = sum(1 for r in rows.values() if not r["judged"])
    out["kept_by_carrier_state"] = {s: sum(1 for r in rows.values() if r["category"] == "kept" and r.get("chosen_carrier_state") == s)
                                    for s in ("active", "dormant", "retracted")}
    return out


def paired_house_gap(left: Mapping[str, Any], right: Mapping[str, Any], block: str, field: str) -> float:
    a, b = house_values(left, block, field), house_values(right, block, field)
    common = sorted(set(a) & set(b))
    return statistics.fmean(a[h] - b[h] for h in common) if common else 0.0


def order_of(gaps: Sequence[float], direction: str) -> str:
    """82-1 on seed-paired gaps (left minus right): 'left_better', 'right_better' or 'not_distinguishable'."""

    label = r82.verdict(list(gaps), direction)["order"]
    return {"VSMT-lean_better": "left_better", "AssocOnly_better": "right_better"}.get(label, "not_distinguishable")


def analyse(sweep: Mapping[tuple[str, int, float], Mapping[str, Any]], reference: Mapping[tuple[str, int], Mapping[str, Any]]) -> dict[str, Any]:
    for seed in SEEDS:
        for key in (("VSMT-lean", seed), ("AssocOnly", seed)):
            if key not in reference:
                raise ValueError(f"reference_missing:{key}")
        for tau in TAUS:
            for arm in ("VSMT-lean", "NoVersion"):
                if (arm, seed, tau) not in sweep:
                    raise ValueError(f"sweep_missing:{arm}:{seed}:{tau}")
    per_tau: dict[str, Any] = {}
    for tau in TAUS:
        v = {s: sweep[("VSMT-lean", s, tau)] for s in SEEDS}
        n = {s: sweep[("NoVersion", s, tau)] for s in SEEDS}
        v05 = {s: reference[("VSMT-lean", s)] for s in SEEDS}
        a = {s: reference[("AssocOnly", s)] for s in SEEDS}
        mrr = [statistics.fmean(house_values(v[s], "missing_residual_rate", "missing_residual_rate").values()) for s in SEEDS]
        f1_self = [paired_house_gap(v[s], v05[s], "node_prf1", "node_f1") for s in SEEDS]
        kept_self = [kept_share(v[s]) - kept_share(v05[s]) for s in SEEDS]
        f1_vs_assoc = [paired_house_gap(v[s], a[s], "node_prf1", "node_f1") for s in SEEDS]
        kept_vs_assoc = [kept_share(v[s]) - kept_share(a[s]) for s in SEEDS]
        kept_vs_noversion = [kept_share(v[s]) - kept_share(n[s]) for s in SEEDS]
        checks = {
            "mrr_five_seed_mean": statistics.fmean(mrr), "mrr_per_seed": mrr,
            "mrr_within_line": statistics.fmean(mrr) <= MRR_LINE,
            "node_f1_minus_own_tau_0_5": f1_self, "node_f1_drop_ok": statistics.fmean(f1_self) >= -F1_DROP_MAX,
            "kept_share_minus_own_tau_0_5": kept_self, "kept_share_drop_ok": statistics.fmean(kept_self) >= -KEPT_DROP_MAX,
            "node_f1_vs_assoc_only": {"gaps": f1_vs_assoc, "order": order_of(f1_vs_assoc, "higher")},
            "kept_share_vs_assoc_only": {"gaps": kept_vs_assoc, "order": order_of(kept_vs_assoc, "higher")},
        }
        checks["assoc_only_not_better"] = (checks["node_f1_vs_assoc_only"]["order"] != "right_better"
                                          and checks["kept_share_vs_assoc_only"]["order"] != "right_better")
        checks["tier_a"] = bool(checks["mrr_within_line"] and checks["node_f1_drop_ok"] and checks["kept_share_drop_ok"]
                                and checks["assoc_only_not_better"])
        # tier B material, computed at every tau and judged only at the chosen one
        extra = {"kept_by_vsmt_lean_only": 0, "of_which_from_retracted": 0, "from_dormant": 0, "from_active": 0}
        for s in SEEDS:
            rv, rn = records(v[s]), records(n[s])
            for k in set(rv) & set(rn):
                if rv[k]["category"] == "kept" and rn[k]["category"] != "kept":
                    extra["kept_by_vsmt_lean_only"] += 1
                    state = rv[k].get("chosen_carrier_state")
                    extra["of_which_from_retracted" if state == "retracted" else ("from_dormant" if state == "dormant" else "from_active")] += 1
        checks["kept_share_vs_noversion"] = {"gaps": kept_vs_noversion, "order": order_of(kept_vs_noversion, "higher")}
        checks["vsmt_lean_only_kept"] = extra
        per_tau[str(tau)] = {"checks": checks,
                             "vsmt_lean": {str(s): summary(v[s]) for s in SEEDS}, "noversion": {str(s): summary(n[s]) for s in SEEDS}}
    passing = [t for t in TAUS if per_tau[str(t)]["checks"]["tier_a"]]
    tier_a = bool(passing)
    chosen = None
    tier_b: dict[str, Any] = {"judged": False}
    if tier_a:
        chosen = min(passing, key=lambda t: (per_tau[str(t)]["checks"]["mrr_five_seed_mean"], -t))
        c = per_tau[str(chosen)]["checks"]
        extra = c["vsmt_lean_only_kept"]
        b1 = c["kept_share_vs_noversion"]["order"] == "left_better"
        b2 = extra["kept_by_vsmt_lean_only"] > 0 and extra["of_which_from_retracted"] * 2 > extra["kept_by_vsmt_lean_only"]
        tier_b = {"judged": True, "tau": chosen, "kept_share_vs_noversion_established": b1, "extra_kept_mostly_from_retracted": b2,
                  "tier_b": bool(b1 and b2)}
    references = {"VSMT-lean_tau_0.5": {str(s): summary(reference[("VSMT-lean", s)]) for s in SEEDS},
                  "AssocOnly": {str(s): summary(reference[("AssocOnly", s)]) for s in SEEDS}}
    if not tier_a:
        verdict = "tier_a_fails_second_consecutive_miss_stop_revisions"
    elif tier_b["tier_b"]:
        verdict = "tier_a_and_tier_b_hold"
    else:
        verdict = "tier_a_holds_tier_b_fails_threshold_was_conservative_reversibility_unsupported"
    return {"constants": {"mrr_line": MRR_LINE, "f1_drop_max": F1_DROP_MAX, "kept_drop_max": KEPT_DROP_MAX, "taus": list(TAUS), "seeds": list(SEEDS)},
            "per_tau": per_tau, "references": references, "tier_a": {"holds": tier_a, "passing_taus": passing},
            "tier_b": tier_b, "verdict": verdict}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sweep", action="append", required=True, help="ARM:SEED:TAU:PATH (VSMT-lean or NoVersion)")
    parser.add_argument("--reference", action="append", required=True, help="ARM:SEED:-:PATH (VSMT-lean at tau 0.5, AssocOnly)")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    sweep, reference, inputs = {}, {}, {}
    for spec in args.sweep + args.reference:
        arm, seed, tau, path = spec.split(":", 3)
        file = Path(path)
        merged = json.loads(file.read_text(encoding="utf-8"))
        if merged.get("schema_version") not in MERGED_SCHEMAS:
            print(f"[ruling87] refused: {file.name} is not a merged v7/v8 audit", file=sys.stderr)
            return 2
        inputs[spec.rsplit(":", 1)[0]] = {"file": file.name, "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
        if spec in args.sweep:
            sweep[(arm, int(seed), float(tau))] = merged
        else:
            reference[(arm, int(seed))] = merged
    try:
        result = analyse(sweep, reference)
    except ValueError as exc:
        print(f"[ruling87] refused: {exc}", file=sys.stderr)
        return 2
    out = {"stage": "vsmt.lean.s2_05.ruling87_sweep.v1", "inputs": inputs,
           "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), **result,
           "caveat": "development reading on the 39 development houses, frozen heads of the ruling-81/82 runs; tier A is a continuation "
                     "line, not the paper's main gate; the final tau_r is selected on validation at S3 under ruling 83-1"}
    Path(args.output).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({"verdict": out["verdict"], "tier_a": out["tier_a"], "tier_b": out["tier_b"],
                      "mrr": {t: round(v["checks"]["mrr_five_seed_mean"], 4) for t, v in out["per_tau"].items()}}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
