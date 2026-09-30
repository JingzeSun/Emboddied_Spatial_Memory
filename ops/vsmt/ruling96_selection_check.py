#!/usr/bin/env python3
"""Ruling 96 (a): the reproduction check and per-seed selection summary of the grouped-selection retraining (read-only).

白话：裁决 96 只检验一件事——节点 F1 的差距是不是由“选哪一轮权重”造成的。重训时训练过程一点不改，只多记一份分组选点。
这个脚本读 9722290 五个头的训练回执与这次重训的五份回执，逐个种子输出：原规则（总验证损失）选中的 epoch 与权重摘要、是否与
9722290 逐位相同；分组规则下“关联＋新建”与“存在”各自选中的 epoch 与权重摘要、分组权重是否与原规则相同；逐 epoch 的总损失、
关联项、存在项。权重摘要只覆盖张量、编码与 ln w 偏移，不含训练记录，所以同数据同种子同线程的重训应当摘要相同。例如种子 7
原规则仍选第 0 个 epoch、摘要与 d0c44f40… 相同，分组规则选关联第 4 轮、存在第 0 轮，就记“复现、分组不同于原规则”。只有五个
种子全部复现，才把之后的差异归到选点规则上；否则退出码 3，后续审计不跑。它不判任何结果好坏。

Usage:
  python ops/vsmt/ruling96_selection_check.py --previous <dir holding A<seed>/training_receipt.json> --retrained <dir> --output <json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

SEEDS = (7, 19, 31, 43, 59)
STAGE = "vsmt.lean.ruling96.selection_check.v1"
RULE = ("every seed's total-loss selection of the retraining must carry the previous weights digest (tensors, encoding and offset; the "
        "training block lies outside the digest) before any difference in the joint loop is put down to the selection rule")


def check(previous: Path, retrained: Path) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for seed in SEEDS:
        old = json.loads((previous / f"A{seed}" / "training_receipt.json").read_text(encoding="utf-8"))
        new = json.loads((retrained / f"A{seed}" / "training_receipt.json").read_text(encoding="utf-8"))
        grouped = new.get("group_selection")
        if not grouped:
            raise ValueError(f"retrained_receipt_without_group_selection:A{seed}")
        rows[str(seed)] = {
            "previous_weights_sha256": old["weights_sha256"], "retrained_weights_sha256": new["weights_sha256"],
            "reproduced": old["weights_sha256"] == new["weights_sha256"],
            "previous_best_epoch": old["best_epoch"], "retrained_best_epoch": new["best_epoch"],
            "grouped_best_epoch_by_group": grouped["best_epoch_by_group"], "grouped_weights_sha256": grouped["weights_sha256"],
            "grouped_equals_total_selection": grouped["weights_sha256"] == new["weights_sha256"],
            "validation_terms_per_epoch": [{k: t.get(k) for k in ("total", "association", "existence")}
                                           for t in new.get("validation_curve_terms") or []],
        }
    return {"rule": RULE, "seeds": rows, "all_reproduced": all(row["reproduced"] for row in rows.values())}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--previous", required=True)
    parser.add_argument("--retrained", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        result = check(Path(args.previous), Path(args.retrained))
    except (OSError, KeyError, ValueError) as exc:
        print(f"[ruling96-selection] refused: {exc}", file=sys.stderr)
        return 2
    output = {"stage": STAGE, "previous": args.previous, "retrained": args.retrained,
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), **result}
    Path(args.output).write_text(json.dumps(output, indent=1), encoding="utf-8")
    for seed, row in result["seeds"].items():
        print(f"[ruling96-selection] A{seed}: reproduced {row['reproduced']} (epoch {row['previous_best_epoch']} -> {row['retrained_best_epoch']}), "
              f"grouped {row['grouped_best_epoch_by_group']}, same as total {row['grouped_equals_total_selection']}")
    return 0 if result["all_reproduced"] else 3


if __name__ == "__main__":
    sys.exit(main())
