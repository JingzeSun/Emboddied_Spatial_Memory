#!/usr/bin/env python3
"""Ruling 89-2 / 89-3 training: the registered recipe on concatenated record sources, with the field-wise encoding and the
class-weighted existence loss, at a given registered seed (development diagnostics, S2-R track).

白话：输入一个或多个训练记录来源（趟根目录:趟名:臂，例如第 0 轮 ELU-P 轨迹与本臂第 1 轮轨迹）、一个登记种子和臂（VSMT-lean 或
AssocOnly），输出一份头权重与训练回执。做法与登记配方相同（AdamW、lr 1e-3、wd 1e-4、20 遍、按选择 house 的验证损失选检查点，
按 split 种子把 39 个 house 留出 30／9），只加裁决 89 的两处：逐字段编码（统计量只用训练 house）与存在损失的类别权重（gone 权重 ＝
训练 house 的 present 行数 ／ gone 行数，AssocOnly 没有存在项）。各来源全量拼接、不重采样；训练预算是拼接集上的 20 遍，实际
更新次数写进回执。它不是正式训练，不产生表行，也不读 validation／test。

Usage:
  python ops/vsmt/ruling89_train.py --source <root>:dagger_round_0:ELU-P [--source <root>:dagger_round_1:VSMT-lean] --arm VSMT-lean
      --seed 7 --out-dir <dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Sequence

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
for item in (ROOT / "src", HERE.parent):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from vsmt import lean_arms as arms  # noqa: E402

import ruling89_probes as probes  # noqa: E402  (sources, the house split)

STAGE = "vsmt.lean.ruling89.train.v1"


def main(argv: Sequence[str] | None = None) -> int:
    from vsmt import lean_model as model

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", dest="sources", action="append", required=True)
    parser.add_argument("--arm", required=True, choices=["VSMT-lean", "AssocOnly"])
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args(argv)
    if args.seed not in arms.SEEDS:
        print(f"seed {args.seed} is not a registered seed {arms.SEEDS}", file=sys.stderr)
        return 2
    entry = probes.r88p._entry()
    training = entry.load_json(entry.S0_05_CONTRACT)["arms"]["VSMT-lean"]["training"]
    model.recipe_matches_contract(learning_rate=training["learning_rate"], epochs=training["epochs"], seeds=training["seeds"],
                                  dagger_rounds=training["dagger_rounds"], main_table_round=training["main_table_round"])
    groups, split, files = probes.load_groups(args.sources)
    train_records = [{k: v for k, v in row.items() if k != "tick"} for _, _, row in groups["train"]]
    validation_records = [{k: v for k, v in row.items() if k != "tick"} for _, _, row in groups["selection"]]
    assoc_only = args.arm == "AssocOnly"
    started = time.time()
    result = model.train_heads(train_records, validation_records, learning_rate=float(training["learning_rate"]),
                               weight_decay=float(training["weight_decay"]), epochs=int(training["epochs"]), seed=int(args.seed),
                               assoc_only=assoc_only, device=args.device, field_encoding=True, existence_class_weight=not assoc_only)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "weights.json").write_text(json.dumps(result["weights"]), encoding="utf-8")
    receipt = {"stage": STAGE, "arm": args.arm, "assoc_only": assoc_only, "seed": args.seed, "sources": args.sources, "holdout": split,
               "recipe": {"learning_rate": training["learning_rate"], "weight_decay": training["weight_decay"], "epochs": training["epochs"],
                          "field_encoding": True, "existence_class_weight": not assoc_only,
                          "concatenation": "every source in full, no resampling; the budget is the registered epochs over the concatenation"},
               "train_frames": len(train_records), "validation_frames": len(validation_records),
               "updates_taken": result["updates_taken"], "existence_class_weight": result["weights"]["training"].get("existence_class_weight"),
               "train_curve": result["train_curve"], "validation_curve": result["validation_curve"], "best_epoch": result["best_epoch"],
               "diverged": result["diverged"], "weights_sha256": result["weights"]["sha256"], "files": files, "device": args.device,
               "code_commit": entry._git("rev-parse", "HEAD"), "wall_seconds": round(time.time() - started, 1),
               "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (out_dir / "training_receipt.json").write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    print(f"[ruling89-train] {args.arm} seed {args.seed}: best epoch {result['best_epoch']}, diverged {result['diverged']}, "
          f"{result['updates_taken']} updates, weights {result['weights']['sha256'][:12]}, {receipt['wall_seconds']} s")
    return 0 if not result["diverged"] else 1


if __name__ == "__main__":
    sys.exit(main())
