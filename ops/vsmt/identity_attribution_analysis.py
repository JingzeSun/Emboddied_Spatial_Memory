#!/usr/bin/env python3
"""Ruling 86-0 reading: where moved objects lose their pre-move identity, per arm and seed and on commonly judged objects.

白话：输入是节点审计 v7 合并结果（每个臂、每个种子一份），每个被搬动物体第一次重见都有一条归因记录（接回了、原实体已不在、
原实体没进召回、学生选了新建、学生选了别的实体、搬动前就没有承载实体）。输出三块：每个臂每个种子的类别计数；两臂在
“都可判”的同一批物体上的 2×2 对照（按 episode 与干预序号配对，同一种子）；以及 VSMT-lean 在“对照臂接回了、它没接回”的物体上
失败落在哪一侧。按裁决 86-0 事前登记的判读：这批失败里，原实体被撤回过或此刻处于休眠／撤回状态的占一半以上，第 2 轮修生命周期
一侧；原实体已被合并掉或不再按多数票认它的占一半以上，第 2 轮修同帧共现否决；都不到一半，把两侧读数交用户裁定。例如
VSMT-lean 在 30 个 AssocOnly 接回的物体上失败，其中 18 个的原实体曾被撤回，就指向生命周期一侧。它只读，不是新指标，不替代正式 test。

Usage:
  python ops/vsmt/identity_attribution_analysis.py --group VSMT-lean:7:<merged v7 json> ... --output <json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ARMS = ("VSMT-lean", "AssocOnly", "NoVersion")
COMPARISONS = (("VSMT-lean", "AssocOnly"), ("VSMT-lean", "NoVersion"))
CATEGORIES = ("kept", "carrier_gone", "carrier_not_recalled", "chose_birth", "chose_other_entity", "no_prior_carrier")
READING_RULE = ("86-0: among VSMT-lean's failures on objects judged in both arms that the comparison arm kept (VSMT-lean vs AssocOnly, "
                "pooled over the five seeds): if more than half are lifecycle-side (a carrier was retracted at some point before the "
                "re-observation, or every present carrier is dormant or retracted) the second revision round targets the lifecycle "
                "side; if more than half are hygiene-side (every carrier gone by a fold, or no present carrier still resolves to the "
                "object) it targets the co-observation veto; otherwise both readings go to the user")


def side_of(record: Mapping[str, Any]) -> str:
    """The pre-registered side of one failed, judged re-observation (86-0)."""

    states = set(record.get("carrier_states") or [])
    if record.get("carrier_ever_retracted") or (states and states <= {"dormant", "retracted"}):
        return "lifecycle"
    if record["category"] == "carrier_gone" or int(record.get("carriers_still_resolving") or 0) == 0:
        return "hygiene"
    return "association"


def records_of(merged: Mapping[str, Any]) -> dict[tuple[str, int], dict[str, Any]]:
    out = {}
    for episode in merged["per_episode"]:
        for record in episode.get("identity_attribution") or []:
            out[(str(episode["episode_id"]), int(record["ordinal"]))] = record
    return out


def counts(records: Mapping[Any, Mapping[str, Any]]) -> dict[str, Any]:
    by = {name: 0 for name in CATEGORIES}
    no_prior = {}
    for record in records.values():
        by[record["category"]] += 1
        if record["category"] == "no_prior_carrier":
            no_prior[record["no_prior_reason"]] = no_prior.get(record["no_prior_reason"], 0) + 1
    judged = sum(v for k, v in by.items() if k != "no_prior_carrier")
    return {"categories": by, "judged": judged, "kept": by["kept"], "identity_continuity_pooled": (by["kept"] / judged) if judged else None,
            "no_prior_reasons": no_prior}


def analyse(groups: Mapping[tuple[str, int], Mapping[str, Any]]) -> dict[str, Any]:
    seeds = sorted({seed for _, seed in groups})
    per_group = {f"{arm}:{seed}": counts(records_of(merged)) for (arm, seed), merged in sorted(groups.items())}
    paired: dict[str, Any] = {}
    failure_sides: dict[str, dict[str, int]] = {}
    for left, right in COMPARISONS:
        name = f"{left}_vs_{right}"
        table = {"both_kept": 0, "only_left_kept": 0, "only_right_kept": 0, "neither": 0, "common_judged": 0}
        left_failures: dict[str, int] = {c: 0 for c in CATEGORIES}
        sides = {"lifecycle": 0, "hygiene": 0, "association": 0}
        states: dict[str, int] = {}
        per_seed = {}
        for seed in seeds:
            if (left, seed) not in groups or (right, seed) not in groups:
                continue
            a, b = records_of(groups[(left, seed)]), records_of(groups[(right, seed)])
            common = sorted(k for k in set(a) & set(b) if a[k]["judged"] and b[k]["judged"])
            seed_table = {"both_kept": 0, "only_left_kept": 0, "only_right_kept": 0, "neither": 0, "common_judged": len(common)}
            for k in common:
                ka, kb = a[k]["category"] == "kept", b[k]["category"] == "kept"
                cell = "both_kept" if ka and kb else ("only_left_kept" if ka else ("only_right_kept" if kb else "neither"))
                seed_table[cell] += 1
                if cell == "only_right_kept":
                    left_failures[a[k]["category"]] += 1
                    sides[side_of(a[k])] += 1
                    for s in a[k].get("carrier_states") or ["none_present"]:
                        states[s] = states.get(s, 0) + 1
            per_seed[str(seed)] = seed_table
            for cell, value in seed_table.items():
                table[cell] += value
        paired[name] = {"pooled": table, "per_seed": per_seed, "left_failures_where_right_kept": left_failures,
                        "left_failure_carrier_states": states, "left_failure_sides": sides}
        failure_sides[name] = sides
    main = failure_sides.get("VSMT-lean_vs_AssocOnly") or {"lifecycle": 0, "hygiene": 0, "association": 0}
    total = sum(main.values())
    if total == 0:
        verdict = "no_failures_to_attribute"
    elif main["lifecycle"] * 2 > total:
        verdict = "round_2_targets_the_lifecycle_side"
    elif main["hygiene"] * 2 > total:
        verdict = "round_2_targets_the_co_observation_veto"
    else:
        verdict = "neither_side_holds_a_majority_user_decides"
    return {"rule": READING_RULE, "seeds": seeds, "per_group": per_group, "paired": paired,
            "reading": {"failures": total, "sides": main, "verdict": verdict}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--group", action="append", required=True, help="ARM:SEED:PATH of one merged node audit v7")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    groups, inputs = {}, {}
    for spec in args.group:
        arm, seed, path = spec.split(":", 2)
        file = Path(path)
        if arm not in ARMS or not file.exists():
            print(f"[identity-attribution] refused: {spec}", file=sys.stderr)
            return 2
        merged = json.loads(file.read_text(encoding="utf-8"))
        if merged.get("schema_version") != "vsmt-s2-05-node-audit-merged-v7":
            print(f"[identity-attribution] refused: {file.name} is not a merged v7 audit", file=sys.stderr)
            return 2
        groups[(arm, int(seed))] = merged
        inputs[f"{arm}:{seed}"] = {"file": file.name, "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
    out = {"stage": "vsmt.lean.s2_05.identity_attribution.v1", "inputs": inputs,
           "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), **analyse(groups),
           "caveat": "development reading on the 39 development houses; descriptive attribution of first re-observations, not a "
                     "significance test and not a new metric"}
    Path(args.output).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({"reading": out["reading"], "paired": {k: v["pooled"] for k, v in out["paired"].items()}}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
