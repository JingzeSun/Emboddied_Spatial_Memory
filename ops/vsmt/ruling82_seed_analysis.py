#!/usr/bin/env python3
"""Ruling 82-1 reading: the spread of five training seeds and the seed-paired VSMT-lean vs AssocOnly gaps (read-only).

Ruling 81 found that, under one training recipe, changing only the initialisation and seed flips the node-F1 order of
VSMT-lean and AssocOnly. This script reads merged node audits (schema v5 when written) of both arms at the five registered
seeds (7, 19, 31, 43, 59; the registered recipe at the time: own-arm records only, 20 epochs) and reports per metric: each
seed's house mean, the mean and standard deviation over the five seeds; per seed, the house-paired mean difference VSMT-lean
minus AssocOnly, and the mean, standard deviation and same-sign count of these five gaps. Pre-registered rule of ruling 82:
the order is established at the development level only if at least 4 gaps share a sign and |mean gap| exceeds the standard
deviation of the 5 gaps; otherwise "not distinguishable on the development set". A house-resampling interval of the
seed-averaged house differences is added for context only. Example: node-F1 gaps +0.04, +0.07, -0.01, +0.03, +0.05 have 4
of the same sign and mean 0.036 > sd 0.030: established. The LOG-270 training with the old initialisation is a reference
column only. Not a significance test and no substitute for test.

Reused outside S2-R: `analyse` and `METRICS` by s2_06_reading.py (S2-06 ruling 100-3 reading); `house_values`, `ARMS` and
`VSMT_ONLY` by ruling95_reading.py, whose `read` S2-06 also reuses. The S3 gate's 82-1 condition is implemented separately
in `lean_teacher`.

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


def verdict(gaps: list[float], direction: str, arms: tuple[str, str] = ARMS) -> dict[str, Any]:
    """The pre-registered 82-1 rule on the seed-paired gaps (first arm minus second; VSMT-lean minus AssocOnly by default)."""

    positive, negative = sum(g > 0 for g in gaps), sum(g < 0 for g in gaps)
    mean = statistics.fmean(gaps)
    sd = statistics.stdev(gaps) if len(gaps) > 1 else None
    same_sign = max(positive, negative)
    established = bool(len(gaps) == len(SEEDS) and same_sign >= 4 and sd is not None and abs(mean) > sd)
    if not established:
        order = "not_distinguishable_on_the_development_set"
    else:
        first_higher = mean > 0
        order = f"{arms[0]}_better" if (first_higher == (direction == "higher")) else f"{arms[1]}_better"
    return {"gaps": gaps, "positive": positive, "negative": negative, "mean_gap": mean, "sd_of_gaps": sd,
            "established": established, "order": order}


def bootstrap_interval(differences: list[float]) -> list[float] | None:
    if not differences:
        return None
    rng = random.Random(BOOTSTRAP_SEED)
    n = len(differences)
    means = sorted(sum(differences[rng.randrange(n)] for _ in range(n)) / n for _ in range(BOOTSTRAP_ITERATIONS))
    return [means[int(0.05 * (BOOTSTRAP_ITERATIONS - 1))], means[int(0.95 * (BOOTSTRAP_ITERATIONS - 1))]]


def analyse(groups: Mapping[tuple[str, int], Mapping[str, Any]], reference: Mapping[str, Any] | None = None, *,
            arms: tuple[str, str] = ARMS) -> dict[str, Any]:
    """The 82-1 reading of two arms at the five seeds: ``arms[0]`` minus ``arms[1]`` (VSMT-lean against AssocOnly by default).

    S2-06 (ruling 100-3) reads VSMT-lean against NoVersion the same way, without a gate; the default output is unchanged.
    """

    first, second = arms
    for arm in arms:
        for seed in SEEDS:
            if (arm, seed) not in groups:
                raise ValueError(f"group_missing:{arm}:{seed}")
    out: dict[str, Any] = {"rule": RULE if arms == ARMS else RULE.replace("VSMT-lean and AssocOnly", f"{first} and {second}"),
                           "seeds": list(SEEDS), "metrics": {}, "vsmt_lean_only": {}}
    if arms != ARMS:
        out["arms"] = list(arms)
    for metric, (block, field, direction) in METRICS.items():
        per_seed = {arm: {seed: house_values(groups[(arm, seed)], block, field) for seed in SEEDS} for arm in arms}
        means = {arm: {seed: (statistics.fmean(v.values()) if v else None) for seed, v in per_seed[arm].items()} for arm in arms}
        gaps = []
        for seed in SEEDS:
            v, a = per_seed[first][seed], per_seed[second][seed]
            houses = sorted(set(v) & set(a))
            gaps.append(statistics.fmean(v[h] - a[h] for h in houses) if houses else 0.0)
        # context only: each house averaged over the seeds first, then a house-resampling interval of the difference
        averaged = {}
        for arm in arms:
            houses = set.intersection(*(set(per_seed[arm][seed]) for seed in SEEDS))
            averaged[arm] = {h: statistics.fmean(per_seed[arm][seed][h] for seed in SEEDS) for h in houses}
        common = sorted(set(averaged[first]) & set(averaged[second]))
        differences = [averaged[first][h] - averaged[second][h] for h in common]
        entry: dict[str, Any] = {
            "direction": direction,
            "house_mean_per_seed": {arm: {str(seed): means[arm][seed] for seed in SEEDS} for arm in arms},
            "seed_spread": {arm: spread([m for m in means[arm].values() if m is not None]) for arm in arms},
            "seed_paired_gaps": verdict(gaps, direction, arms),
            "seed_averaged_house_difference_context_only": {"houses": len(common),
                                                            "mean": statistics.fmean(differences) if differences else None,
                                                            "interval_90": bootstrap_interval(differences)},
        }
        if reference is not None:
            per_house = ((reference.get("metrics") or {}).get(metric) or {}).get("per_house") or {}
            rows = [(r.get(first), r.get(second)) for r in per_house.values()]
            rows = [(x, y) for x, y in rows if x is not None and y is not None]
            entry["reference_log_270_old_initialisation_not_in_the_rule"] = (
                {"gap": statistics.fmean(x - y for x, y in rows), "houses": len(rows)} if rows else None)
        out["metrics"][metric] = entry
    for metric, (block, field, direction) in VSMT_ONLY.items():
        means = {seed: house_values(groups[(first, seed)], block, field) for seed in SEEDS}
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
