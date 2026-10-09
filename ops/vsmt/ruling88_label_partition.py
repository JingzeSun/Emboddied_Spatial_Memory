#!/usr/bin/env python3
"""Ruling 88 (read-only): what the existence head's "gone" labels actually are, from the merged node audits.

How many of the existence head's positives (existence candidates the teacher labels "gone") are the real-world changes the
paper sets out to detect. Input: merged node-audit exports (from v3 on, each existence candidate is tallied by eight fields:
label status, reason, intervention class, window phase, whether the entity is in place by the node primary column, whether
another entity carries the object, whether a fragment exists this frame, the student's decision). Output per export: gone
rows and shares by class -- removed or moved after the window; in place by the node primary column with no other carrier
(retracting it deletes the only correct record); in place with a duplicate carrier; not in place with another carrier;
drifted with no carrier. Example: a sofa entity whose surface centroid is 0.7 m from the sofa centre but inside the
expanded sofa box is labelled gone while the node primary column counts it in place: the second class. Reads committed
results/ exports only and changes no label, rule or contract; the classes are exclusive, the first that applies in the
order below is taken. Cited by a comment in `lean_teacher` (the 13.3 percent world-change share); imported by no code.

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
