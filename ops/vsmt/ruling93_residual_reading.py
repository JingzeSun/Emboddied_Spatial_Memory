#!/usr/bin/env python3
"""Ruling 93 revised: pool the residual traces of the node audits per cell (report only).

白话：把每条节点审计里的残留追踪（residual_trace）按格（保留校正／不校正）汇总：各类残留的个数、按 house 列出、六个共同失败
house 单列，并逐个列出全部残留物体及其计数，不只挑案例。

Usage:
  python ops/vsmt/ruling93_residual_reading.py --cell corrected:<audit root group dir> ... --focus 00702,01394 --output <json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
import residual_trace as rt  # noqa: E402


def pool(group_dirs: Sequence[Path]) -> dict[str, Any]:
    tally = {name: 0 for name in rt.CATEGORY_ORDER}
    per_house: dict[str, dict[str, int]] = {}
    objects: list[dict[str, Any]] = []
    audits = 0
    for group in group_dirs:
        for path in sorted(group.glob("*/*/node_audit.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            trace = payload.get("residual_trace")
            if trace is None:
                raise SystemExit(f"audit without residual_trace: {path}")
            audits += 1
            house = str(payload["episode_id"])
            for key, row in trace["per_object"].items():
                tally[row["category"]] += 1
                per_house.setdefault(house, {n: 0 for n in rt.CATEGORY_ORDER})[row["category"]] += 1
                objects.append({"group": group.name, "episode_id": house, "object": key, **row})
    return {"audits": audits, "final_residual_objects": len(objects), "categories": tally, "per_house": per_house, "objects": objects}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cell", action="append", required=True, help="label:<group dir>[,<group dir>...]")
    parser.add_argument("--focus", default="", help="comma-separated house suffixes reported separately")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    focus = [s for s in args.focus.split(",") if s]
    out: dict[str, Any] = {"stage": "vsmt.lean.ruling93.residual_reading.v1", "role": "report only; explains residuals, decides nothing",
                           "category_order": list(rt.CATEGORY_ORDER), "cells": {}}
    for item in args.cell:
        label, dirs = item.split(":", 1)
        pooled = pool([Path(d) for d in dirs.split(",")])
        pooled["focus_houses"] = {h: v for h, v in pooled["per_house"].items() if any(h.endswith(f) for f in focus)}
        out["cells"][label] = pooled
        print(json.dumps({label: {"audits": pooled["audits"], "residual": pooled["final_residual_objects"], "categories": pooled["categories"]}}))
    out["script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    Path(args.output).write_text(json.dumps(out, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
