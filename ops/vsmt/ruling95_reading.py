#!/usr/bin/env python3
"""Ruling 95 (a): the main question read directly on the development houses (report; the reading rule is fixed before the run).

Ruling 95 brings S2-R back to the main question: do the learned lifecycle operations maintain memory better than AssocOnly,
which learns association the same way but has no lifecycle operations? Inputs: merged node audits of joint VSMT-lean (five
round-1 heads; association and existence both decided by the learned heads; registered configuration tau_r 0.5, ln w
correction, k' = 3), AssocOnly retrained with the same association-side changes (five seeds) and the four rule arms (TAF,
ELU-P, RAC, LOW; development configurations, no seeds). Outputs:
  * the 82-1 order of VSMT-lean against AssocOnly on six metrics under the pre-registered rule (at least 4 seeds with the
    same sign and |mean gap| above the standard deviation of the 5 gaps), computed by ruling82_seed_analysis as is;
  * the ruling-95 classification, fixed before the run: Missing residual rate established better and neither node F1 nor
    identity continuity established worse -> gain shown on development; Missing residual rate better but node F1 or identity
    continuity established worse -> trade-off, no gain claimed; Missing residual rate not established better -> no gain shown
    on development (not distinguishable is not evidence of no effect);
  * the rule arms' house means and the ruling-85-4 reading: VSMT-lean's five-seed mean Missing residual rate as a multiple of
    the best rule arm's (>= 2 calls for a framing ruling before S3-01, per 85-4); the four ruling-89-4 lines are reported for
    reference only, without pass/fail.
Example: Missing residual gaps -0.10, -0.08, -0.12, -0.05, +0.01 have 4 of the same sign and |mean| 0.068 > sd 0.050; with
node F1 and identity continuity not distinguishable, the class is gain shown on development. Not a significance test; 30 of
the 39 development houses are training houses, so development readings are in-sample and a claim is checked once on the
confirmation set.

Reused outside S2-R: `read` by s2_06_reading.py (S2-06 ruling 100-3 reading, both front ends).

Usage:
  python ops/vsmt/ruling95_reading.py --group VSMT-lean:7:<merged audit> ... --group AssocOnly:59:<merged audit> \
      --rule-arm TAF:<merged audit> --rule-arm ELU-P:<...> --rule-arm RAC:<...> --rule-arm LOW:<...> \
      [--reference-82 results/vsmt_lean_s2_05_ruling82_seed_analysis_18f943f.json] --output <json>
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
import ruling82_seed_analysis as r82  # noqa: E402

STAGE = "vsmt.lean.ruling95.reading.v1"
RULE_ARMS = ("TAF", "ELU-P", "RAC", "LOW")
#: Ruling 95 (a), registered before the run: how the three 82-1 orders are read together.
CLASSIFICATION_RULE = (
    "ruling 95 (a): gain_shown_on_development iff the 82-1 order of missing_residual_rate is VSMT-lean_better and neither "
    "node_prf1 nor identity_continuity is AssocOnly_better; trade_off_no_gain_claimed iff missing_residual_rate is VSMT-lean_better "
    "and node_prf1 or identity_continuity is AssocOnly_better; otherwise no_gain_shown_on_development (not distinguishable is not "
    "evidence of no effect)")
#: Ruling 89-4's four lines on the five-seed means, reported for reference only (ruling 95 makes no pass/fail of them).
LINES_89_4 = {"missing_residual_rate": ("at_most", 0.10), "identity_continuity": ("at_least", 0.45),
              "node_prf1": ("at_least", 0.76), "false_retract_rate_in_scope": ("at_most", 0.35)}
#: Ruling 85-4: a Missing residual rate at least this many times the best rule arm's calls for a framing ruling before S3-01.
RATIO_85_4 = 2.0


def classify(orders: Mapping[str, str]) -> str:
    mrr, f1, identity = orders["missing_residual_rate"], orders["node_prf1"], orders["identity_continuity"]
    if mrr != "VSMT-lean_better":
        return "no_gain_shown_on_development"
    if f1 == "AssocOnly_better" or identity == "AssocOnly_better":
        return "trade_off_no_gain_claimed"
    return "gain_shown_on_development"


def house_mean(merged: Mapping[str, Any], block: str, field: str) -> dict[str, Any]:
    values = r82.house_values(merged, block, field)
    return {"mean": statistics.fmean(values.values()) if values else None, "houses": len(values)}


def rule_arm_rows(rule_arms: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    out = {}
    for arm, merged in sorted(rule_arms.items()):
        row = {metric: house_mean(merged, block, field) for metric, (block, field, _) in r82.METRICS.items()}
        for metric, (block, field, _) in r82.VSMT_ONLY.items():
            row[metric] = house_mean(merged, block, field)
        out[arm] = row
    return out


def lines_89_4(means: Mapping[str, float | None]) -> dict[str, Any]:
    out = {}
    for metric, (kind, line) in LINES_89_4.items():
        value = means.get(metric)
        met = None if value is None else (value <= line if kind == "at_most" else value >= line)
        out[metric] = {"five_seed_mean": value, kind: line, "met": met}
    return out


def reference_summary(reference: Mapping[str, Any]) -> dict[str, Any]:
    """The LOG-279 (ruling 82-1, earlier recipe) orders and five-seed means, side by side only."""

    metrics = {}
    for metric, entry in (reference.get("metrics") or {}).items():
        spread = entry.get("seed_spread") or {}
        metrics[metric] = {"order": (entry.get("seed_paired_gaps") or {}).get("order"),
                           "mean_gap": (entry.get("seed_paired_gaps") or {}).get("mean_gap"),
                           "five_seed_means": {arm: (spread.get(arm) or {}).get("mean") for arm in r82.ARMS}}
    return {"stage": reference.get("stage"), "metrics": metrics}


def read(groups: Mapping[tuple[str, int], Mapping[str, Any]], rule_arms: Mapping[str, Mapping[str, Any]],
         reference: Mapping[str, Any] | None = None) -> dict[str, Any]:
    missing = [arm for arm in RULE_ARMS if arm not in rule_arms]
    if missing:
        raise ValueError(f"rule_arm_missing:{','.join(missing)}")
    base = r82.analyse(groups)
    orders = dict(base["summary"])
    vsmt_means = {metric: entry["seed_spread"]["VSMT-lean"]["mean"] for metric, entry in base["metrics"].items()}
    vsmt_means.update({metric: entry["seed_spread"]["mean"] for metric, entry in base["vsmt_lean_only"].items()})
    rules = rule_arm_rows(rule_arms)
    rule_mrr = {arm: row["missing_residual_rate"]["mean"] for arm, row in rules.items() if row["missing_residual_rate"]["mean"] is not None}
    best_arm = min(rule_mrr, key=lambda arm: (rule_mrr[arm], arm)) if rule_mrr else None
    ratio = None
    if best_arm is not None and vsmt_means.get("missing_residual_rate") is not None and rule_mrr[best_arm] > 0:
        ratio = vsmt_means["missing_residual_rate"] / rule_mrr[best_arm]
    out = {
        "classification": classify(orders),
        "classification_rule": CLASSIFICATION_RULE,
        "orders_82_1": orders,
        "comparison_82_1": base,
        "rule_arms": rules,
        "rule_85_4": {"vsmt_lean_five_seed_mean": vsmt_means.get("missing_residual_rate"), "best_rule_arm": best_arm,
                      "best_rule_arm_value": rule_mrr.get(best_arm) if best_arm else None, "ratio": ratio,
                      "at_least_twice": None if ratio is None else ratio >= RATIO_85_4,
                      "rule": "ruling 85-4: at least twice the best rule arm calls for a framing ruling before S3-01 (report only)"},
        "lines_89_4_reference_only": lines_89_4(vsmt_means),
        "caveat": ("development reading: 30 of the 39 development houses are training houses of the learned heads (in-sample); "
                   "the claim is tested once on the confirmation set after the method is frozen; not a significance test"),
    }
    if reference is not None:
        out["reference_log_279_earlier_recipe"] = reference_summary(reference)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--group", action="append", required=True, help="ARM:SEED:PATH of one merged node audit (VSMT-lean, AssocOnly)")
    parser.add_argument("--rule-arm", action="append", required=True, help="ARM:PATH of one merged node audit (TAF, ELU-P, RAC, LOW)")
    parser.add_argument("--reference-82", default=None)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    groups, rule_arms, inputs = {}, {}, {}
    for spec in args.group:
        arm, seed, path = spec.split(":", 2)
        file = Path(path)
        if not file.exists():
            print(f"[ruling95-reading] refused: {file} missing", file=sys.stderr)
            return 2
        groups[(arm, int(seed))] = json.loads(file.read_text(encoding="utf-8"))
        inputs[f"{arm}:{seed}"] = {"file": file.name, "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
    for spec in args.rule_arm:
        arm, path = spec.split(":", 1)
        file = Path(path)
        if not file.exists():
            print(f"[ruling95-reading] refused: {file} missing", file=sys.stderr)
            return 2
        rule_arms[arm] = json.loads(file.read_text(encoding="utf-8"))
        inputs[arm] = {"file": file.name, "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
    reference = None
    if args.reference_82:
        file = Path(args.reference_82)
        reference = json.loads(file.read_text(encoding="utf-8"))
        inputs["reference_82"] = {"file": file.name, "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
    try:
        result = read(groups, rule_arms, reference)
    except ValueError as exc:
        print(f"[ruling95-reading] refused: {exc}", file=sys.stderr)
        return 2
    output = {"stage": STAGE, "inputs": inputs, "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), **result}
    Path(args.output).write_text(json.dumps(output, indent=1), encoding="utf-8")
    print(json.dumps({"classification": result["classification"], "orders_82_1": result["orders_82_1"],
                      "rule_85_4": result["rule_85_4"], "lines_89_4": result["lines_89_4_reference_only"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
