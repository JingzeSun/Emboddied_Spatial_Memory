#!/usr/bin/env python3
"""Ruling 88 (read-only): what the existence head's "gone" labels actually are, from the merged node audits.

白话：存在头的正例（teacher 标为“已不在”的存在候选）里，究竟有多少是论文要检测的真实世界变化。输入是已合并的节点
审计导出（v3 起每个存在候选按八项归档：标签状态、原因、干预类别、窗口阶段、实体按节点主列是否仍在原处、是否另有
实体承载、本帧有无色块、学生决定），输出每个导出里 gone 标签按五类的行数与占比：窗口后真的被拿走或搬动；实体自己按
节点主列仍在原处且没有别的承载（撤回它就删掉唯一正确的记录）；在原处但另有重复承载；不在原处但另有承载；漂移且无
承载。例如一个沙发实体的表面质心离沙发中心 0.7 m、但落在外扩后的沙发框里，标签是 gone，节点主列却算它在原处，它落在
第二类。它只读已提交的 results/ 导出，不改任何标签、规则或合同；五类互斥，按下面的顺序取第一个成立的。

Usage:
  python ops/vsmt/ruling88_label_partition.py results/vsmt_lean_s2_05_node_audit_ruling86_*_378008c.json --output <json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

STAGE = "vsmt.lean.ruling88.label_partition.v1"
CLASSES = (
    "world_change_after_window",       # a removed or moved object, frame after the window end
    "in_place_no_other_carrier",       # the node primary rule counts the entity in place; no other entity carries the object
    "in_place_with_duplicate",         # in place, and another entity also carries the object
    "off_place_with_other_carrier",    # not in place; another entity carries the object
    "drift_no_carrier",                # not in place; no entity carries the object
    "other",                           # an intervened object before or at the window end
)
WORLD_CHANGE_KINDS = ("remove", "move")


def classify(row: Mapping[str, Any]) -> str:
    """The first class that applies to one gone tally row (fields as the node audit's EXISTENCE_TALLY_FIELDS)."""

    if row["object_class"] in WORLD_CHANGE_KINDS:
        return "world_change_after_window" if row["phase"] == "after_window" else "other"
    in_place = row["entity_in_place_node_rule"] == "yes"
    carried = row["another_entity_carries_the_object"] == "yes"
    if in_place:
        return "in_place_with_duplicate" if carried else "in_place_no_other_carrier"
    return "off_place_with_other_carrier" if carried else "drift_no_carrier"


def partition(audit: Mapping[str, Any]) -> dict[str, Any]:
    """Gone rows by class (and how many of each the student retracted) for one merged node audit."""

    fields = list(audit["existence_tally_fields"])
    rows = {name: 0 for name in CLASSES}
    retracted = {name: 0 for name in CLASSES}
    for entry in audit["pooled_existence_tally"]:
        row = dict(zip(fields, entry[:-1]))
        count = int(entry[-1])
        if row["status"] != "gone":
            continue
        name = classify(row)
        rows[name] += count
        if row["decision"] == "RETRACT":
            retracted[name] += count
    total = sum(rows.values())
    return {"gone_rows": total, "rows": rows, "share": {k: (v / total if total else None) for k, v in rows.items()},
            "retracted": retracted}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("audits", nargs="+")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    groups: list[dict[str, Any]] = []
    pooled: dict[str, dict[str, int]] = {}
    for path in sorted(args.audits):
        raw = Path(path).read_bytes()
        audit = json.loads(raw)
        if "pooled_existence_tally" not in audit or not audit["pooled_existence_tally"]:
            continue  # AssocOnly makes no existence decisions
        part = partition(audit)
        groups.append({"file": Path(path).name, "sha256": hashlib.sha256(raw).hexdigest(), "arm": audit["arm"], **part})
        arm = pooled.setdefault(audit["arm"], {name: 0 for name in CLASSES})
        for name in CLASSES:
            arm[name] += part["rows"][name]
    summary = {arm: {"gone_rows": sum(rows.values()),
                     "share": {k: v / sum(rows.values()) for k, v in rows.items()}} for arm, rows in sorted(pooled.items())}
    out = {"stage": STAGE, "classes": list(CLASSES), "rule": "first class that applies, in the order listed",
           "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "groups": groups, "pooled_by_arm": summary}
    Path(args.output).write_text(json.dumps(out, indent=1), encoding="utf-8")
    for arm, block in summary.items():
        print(arm, block["gone_rows"], {k: round(v, 3) for k, v in block["share"].items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
