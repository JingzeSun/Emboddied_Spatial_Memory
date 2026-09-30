#!/usr/bin/env python3
"""Ruling 89-2 / 89-3 reading: each side's mechanism check under the lines frozen in DECISIONS ruling 89 (revised).

白话：输入是两侧检查的全部产物，输出按冻结通过线的判读，不选配置、不做显著性检验。
  * 89-2 存在侧：① 同输入异答案为 0（训练前）；② P3 在新输入与新配方上 HandCost、RAC、ELU-P 的训练 house 分类均衡一致率 ≥0.99
    （最后一个 epoch 与训练损失最低 epoch 都要过）；③ “teacher 关联＋新存在头”格 5 种子的 Missing 残留率均值 ≤0.05、节点 F1 均值
    ≥0.93，范围内假撤回率另报。
  * 89-3 关联侧：① 状态覆盖按事件（训练前）；② P3 的 TAF、LOW ≥0.99（同样两种 epoch）；③ 同一新召回下，新头的“学习关联＋teacher
    存在”格相对旧头基线，身份连续率与全部重见接回比例按 82-1 规则确定更高（同种子配对，至少 4/5 同号且均值大于标准差），且“选了
    新建”减少（5 种子均值）。
例如 5 个种子的 Missing 残留率 0.02～0.06、均值 0.04，节点 F1 均值 0.94，就算 ③ 过。

Usage:
  python ops/vsmt/ruling89_checks.py --same-input <json> --coverage-events <json> --imitation rac:<json> ...
      --oa-le 7:<merged> ... --la-oe-new 7:<merged> ... --la-oe-old 7:<merged> ... --output <json>
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
import ruling82_seed_analysis as r82  # noqa: E402
import ruling88_analysis as r88  # noqa: E402
import ruling89_recall as r89r  # noqa: E402

STAGE = "vsmt.lean.ruling89.checks.v1"
SEEDS = (7, 19, 31, 43, 59)
EXISTENCE_P3 = ("handcost", "rac", "elup")
ASSOCIATION_P3 = ("taf", "low")
MRR_LINE, NODE_F1_LINE = 0.05, 0.93
#: ruling 93-2 (2026-09-30): P3 is reported only, not a condition of 89-2 / 89-3 (set by --p3-report-only)
P3_REPORT_ONLY = {"on": False}
#: 89-4 joint closed-loop lines (five-seed means), frozen in ruling 89 (revised)
JOINT_LINES = {"missing_residual_rate": ("at_most", 0.10), "identity_continuity": ("at_least", 0.45),
               "node_f1": ("at_least", 0.76), "false_retract_rate_in_scope": ("at_most", 0.35)}


def house_mean(merged: Mapping[str, Any], metric: str) -> float | None:
    values = r88.house_values(merged, metric)
    return statistics.fmean(values.values()) if values else None


def seed_means(runs: Mapping[int, Mapping[str, Any]], metric: str) -> dict[str, Any]:
    per_seed = {seed: house_mean(run, metric) for seed, run in sorted(runs.items())}
    values = [v for v in per_seed.values() if v is not None]
    return {"per_seed": per_seed, "mean": statistics.fmean(values) if values else None}


def reobservation(merged: Mapping[str, Any]) -> dict[str, Any]:
    rows = r89r.records(merged)
    counts = r89r.categories(rows)
    return {"rows": len(rows), "categories": counts, "kept_share": (counts["kept"] / len(rows)) if rows else None}


def p3_reading(reports: Mapping[str, Mapping[str, Any]], targets: Sequence[str]) -> dict[str, Any]:
    out = {}
    for target in targets:
        report = reports.get(target)
        if report is None:
            out[target] = {"present": False, "pass": False}
            continue
        out[target] = {"present": True, "pass": bool(report["pass"]),
                       **{label: report["readings"][label]["train"]["balanced_agreement"] for label in report["readings"]},
                       "selection_last_epoch": report["readings"]["last_epoch"]["selection"]["balanced_agreement"]}
    return {"per_target": out, "pass": all(v["pass"] for v in out.values())}


def existence_side(same_input: Mapping[str, Any] | None, imitation: Mapping[str, Mapping[str, Any]],
                   oa_le: Mapping[int, Mapping[str, Any]], history_audit: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """89-2.  Check 1 is read only from the independent-executor history audit (ASTRA review, 2026-09-30: the same-input
    table computes the rule from the row and so cannot fail; it is reported only).  Without the audit, check 1 fails --
    there is no fallback to the table."""

    mrr = seed_means(oa_le, "missing_residual_rate") if oa_le else None
    f1 = seed_means(oa_le, "node_f1") if oa_le else None
    fr = seed_means(oa_le, "false_retract_rate_in_scope") if oa_le else None
    cell_pass = bool(mrr and f1 and len(oa_le) == len(SEEDS) and mrr["mean"] is not None and f1["mean"] is not None
                     and mrr["mean"] <= MRR_LINE and f1["mean"] >= NODE_F1_LINE)
    p3 = p3_reading(imitation, EXISTENCE_P3)
    same = bool(same_input and same_input.get("pass"))
    first = bool(history_audit is not None and history_audit.get("pass"))
    return {"same_input_reported_only":
                None if same_input is None else {"pass": same, "conflicts": {k: v["inputs_with_two_answers"] for k, v in same_input["per_rule"].items()}},
            "history_audit": {"pass": False, "reason": "history_audit_missing"} if history_audit is None
                             else {"pass": first, "groups": history_audit["groups"]},
            "p3": p3, "cell_teacher_association_new_existence": {"missing_residual_rate": mrr, "node_f1": f1,
                                                                  "false_retract_rate_in_scope_reported": fr,
                                                                  "lines": {"missing_residual_rate_mean_at_most": MRR_LINE, "node_f1_mean_at_least": NODE_F1_LINE},
                                                                  "pass": cell_pass},
            "p3_role": "reported_only" if P3_REPORT_ONLY["on"] else "required",
            "pass": bool(first and (P3_REPORT_ONLY["on"] or p3["pass"]) and cell_pass)}


def association_side(coverage: Mapping[str, Any] | None, imitation: Mapping[str, Mapping[str, Any]],
                     new: Mapping[int, Mapping[str, Any]], old: Mapping[int, Mapping[str, Any]]) -> dict[str, Any]:
    seeds = [s for s in SEEDS if s in new and s in old]
    identity_gaps, kept_gaps = [], []
    births = {"new": {}, "old": {}}
    for seed in seeds:
        gap = r88.paired(new[seed], old[seed], "identity_continuity")["left_minus_right"]
        identity_gaps.append(gap)
        a, b = reobservation(new[seed]), reobservation(old[seed])
        kept_gaps.append(None if a["kept_share"] is None or b["kept_share"] is None else a["kept_share"] - b["kept_share"])
        births["new"][seed] = a["categories"]["chose_birth"]
        births["old"][seed] = b["categories"]["chose_birth"]
    complete = len(seeds) == len(SEEDS) and None not in identity_gaps and None not in kept_gaps
    identity = r82.verdict(identity_gaps, "higher") if complete else None
    kept = r82.verdict(kept_gaps, "higher") if complete else None
    birth_new = statistics.fmean(births["new"].values()) if births["new"] else None
    birth_old = statistics.fmean(births["old"].values()) if births["old"] else None
    paired_pass = bool(complete and identity["established"] and identity["mean_gap"] > 0 and kept["established"] and kept["mean_gap"] > 0
                       and birth_new is not None and birth_old is not None and birth_new < birth_old)
    p3 = p3_reading(imitation, ASSOCIATION_P3)
    cov = bool(coverage and coverage.get("pass"))
    return {"coverage_events": None if coverage is None else {"pass": cov, "train": coverage["train"]},
            "p3": p3,
            "paired_same_recall": {"seeds": seeds, "identity_continuity_new_minus_old": identity, "kept_share_new_minus_old": kept,
                                   "chose_birth": {"new": births["new"], "old": births["old"], "mean_new": birth_new, "mean_old": birth_old},
                                   "rule": r82.RULE, "pass": paired_pass},
            "p3_role": "reported_only" if P3_REPORT_ONLY["on"] else "required",
            "pass": bool(cov and (P3_REPORT_ONLY["on"] or p3["pass"]) and paired_pass)}


def joint_check(runs: Mapping[int, Mapping[str, Any]]) -> dict[str, Any]:
    """89-4: VSMT-lean with both sides' heads, tau_r 0.5, the new recall, five seeds x 39 episodes; the four frozen lines."""

    out: dict[str, Any] = {"seeds": sorted(runs), "lines": {}}
    ok = len(runs) == len(SEEDS)
    for metric, (kind, line) in JOINT_LINES.items():
        means = seed_means(runs, metric)
        value = means["mean"]
        passed = value is not None and (value <= line if kind == "at_most" else value >= line)
        out["lines"][metric] = {**means, kind: line, "pass": bool(passed)}
        ok = ok and bool(passed)
    out["pass"] = bool(ok)
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--same-input")
    parser.add_argument("--history-audit", help="merged ruling89_history_audit.py output (89-2 check 1)")
    parser.add_argument("--p3-report-only", action="store_true", help="ruling 93-2: P3 is reported, not required")
    parser.add_argument("--coverage-events")
    parser.add_argument("--imitation", action="append", default=[], help="target:json")
    parser.add_argument("--oa-le", action="append", default=[], help="seed:merged audit")
    parser.add_argument("--la-oe-new", action="append", default=[])
    parser.add_argument("--la-oe-old", action="append", default=[])
    parser.add_argument("--joint", action="append", default=[], help="89-4: seed:merged audit of the joint closed-loop run")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    P3_REPORT_ONLY["on"] = bool(args.p3_report_only)
    inputs: dict[str, str] = {}

    def load(path: str | None) -> dict[str, Any] | None:
        if not path:
            return None
        inputs[path] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def by_seed(items: Sequence[str]) -> dict[int, dict[str, Any]]:
        out = {}
        for item in items:
            seed, path = item.split(":", 1)
            out[int(seed)] = r88.as_merged(load(path))
        return out

    imitation = {}
    for item in args.imitation:
        target, path = item.split(":", 1)
        imitation[target] = load(path)
    out = {"stage": STAGE,
           "existence_side_89_2": existence_side(load(args.same_input), imitation, by_seed(args.oa_le), load(args.history_audit)),
           "association_side_89_3": association_side(load(args.coverage_events), imitation, by_seed(args.la_oe_new), by_seed(args.la_oe_old)),
           "joint_89_4": joint_check(by_seed(args.joint)) if args.joint else None,
           "inputs_sha256": inputs, "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    Path(args.output).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({"89-2": out["existence_side_89_2"]["pass"], "89-3": out["association_side_89_3"]["pass"],
                      "mrr": (out["existence_side_89_2"]["cell_teacher_association_new_existence"]["missing_residual_rate"] or {}).get("mean"),
                      "f1": (out["existence_side_89_2"]["cell_teacher_association_new_existence"]["node_f1"] or {}).get("mean"),
                      "89-4": None if out["joint_89_4"] is None else out["joint_89_4"]["pass"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
