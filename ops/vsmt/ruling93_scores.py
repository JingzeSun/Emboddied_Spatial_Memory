#!/usr/bin/env python3
"""Ruling 93, revised (a): read-only reading of the five round-1 heads on the records they were trained and selected on.

白话：不重训，只把 LOG-291 那五个头（每个种子保存下来的第 0 个 epoch 检查点）放回它们的训练记录上读数：
  * 存在头的原始分数（未加 ln w 偏移的 sigmoid）在 teacher 标 gone 与 present 的行上各自的分布与 AUC，
    以及各自有多大比例超过“τ_r 0.15／0.2／0.3／0.5 减去 ln w 之后对应的原始分数门槛”；
  * 这个检查点上关联损失与存在损失分开算（训练时记录的是两者之和，没有分项）；
按“训练 house／选择 house”与记录来源（第 0 轮 ELU-P／第 1 轮 VSMT-lean）分开报。逐 epoch 的分项损失没有保存，不能补读。
分数不是准确概率，门槛换算只说明决策边界。它不改任何判定、不选阈值。

Usage:
  python ops/vsmt/ruling93_scores.py --source <root>:dagger_round_0:ELU-P --source <root>:dagger_round_1:VSMT-lean
      --weights 7:<weights.json> ... --output <json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
for item in (ROOT / "src", HERE.parent):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import ruling89_probes as probes  # noqa: E402

STAGE = "vsmt.lean.ruling93.scores.v1"
TAUS = (0.15, 0.2, 0.3, 0.5)
QUANTILES = (0.05, 0.25, 0.5, 0.75, 0.95)


def auc(positive: Sequence[float], negative: Sequence[float]) -> float | None:
    """P(score of a random gone row > score of a random present row), ties counted half (Mann-Whitney)."""

    if not positive or not negative:
        return None
    ranked = sorted([(v, 1) for v in positive] + [(v, 0) for v in negative])
    rank_sum, i = 0.0, 0
    while i < len(ranked):
        j = i
        while j < len(ranked) and ranked[j][0] == ranked[i][0]:
            j += 1
        average = (i + 1 + j) / 2.0
        rank_sum += average * sum(1 for k in range(i, j) if ranked[k][1] == 1)
        i = j
    n1, n0 = len(positive), len(negative)
    return (rank_sum - n1 * (n1 + 1) / 2.0) / (n1 * n0)


def raw_threshold(tau: float, pos_weight: float) -> float:
    """The uncorrected sigmoid score a row must reach for sigmoid(logit - ln w) >= tau."""

    return 1.0 / (1.0 + math.exp(-(math.log(tau / (1.0 - tau)) + math.log(pos_weight))))


def quantiles(values: Sequence[float]) -> dict[str, float | None]:
    if not values:
        return {str(q): None for q in QUANTILES}
    ordered = sorted(values)
    return {str(q): ordered[min(len(ordered) - 1, int(q * len(ordered)))] for q in QUANTILES}


def score_block(gone: Sequence[float], present: Sequence[float], pos_weight: float) -> dict[str, Any]:
    thresholds = {str(t): raw_threshold(t, pos_weight) for t in TAUS}
    return {"rows": {"gone": len(gone), "present": len(present)}, "auc_gone_over_present": auc(gone, present),
            "quantiles": {"gone": quantiles(gone), "present": quantiles(present)},
            "raw_threshold_for_tau": thresholds,
            "share_at_or_above": {tau: {"gone": (sum(v >= thr for v in gone) / len(gone)) if gone else None,
                                        "present": (sum(v >= thr for v in present) / len(present)) if present else None}
                                  for tau, thr in thresholds.items()}}


def frame_parts(heads: Any, batched: Mapping[str, Any], pos_weight: Any) -> dict[str, Any]:
    """The two terms of ``lean_model.batched_loss`` separately, plus the existence scores and labels."""

    import torch

    out: dict[str, Any] = {}
    with torch.no_grad():
        if batched["fragments"]:
            pair = heads["association"](batched["pairs"]).reshape(-1) if batched["pairs"] is not None else None
            birth = heads["birth"](batched["births"]).reshape(-1)
            flat = birth if pair is None else torch.cat([pair, birth])
            scores = flat[batched["index"]].masked_fill(~batched["mask"], float("-inf"))
            out["association"] = float(torch.nn.functional.cross_entropy(scores, batched["targets"]))
        if batched["existence"] is not None:
            rows, target, _ = batched["existence"]
            logits = heads["existence"](rows).reshape(-1)
            out["existence"] = float(torch.nn.functional.binary_cross_entropy_with_logits(logits, target, pos_weight=pos_weight))
            out["scores"] = (torch.sigmoid(logits).tolist(), target.tolist())
    return out


def main(argv: Sequence[str] | None = None) -> int:
    import torch

    from vsmt import lean_model as model

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", dest="sources", action="append", required=True)
    parser.add_argument("--weights", action="append", required=True, help="seed:weights.json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    started = time.time()
    groups, split, files = probes.load_groups(args.sources)
    batched: dict[str, list[Any]] = {}
    for group, rows in groups.items():
        for source, _, row in rows:
            record = {k: v for k, v in row.items() if k != "tick"}
            batched.setdefault(f"{group}|{source}", []).append(model.batch_prepared(model.prepare_frame(record)))
    out: dict[str, Any] = {"stage": STAGE, "sources": args.sources, "holdout": split, "files": files, "seeds": {}}
    for item in args.weights:
        seed, path = item.split(":", 1)
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        heads = model.load_heads(payload).eval()
        w = float(payload["training"]["existence_class_weight"]["pos_weight"])
        pw = torch.as_tensor([w], dtype=torch.float32)
        per_block: dict[str, Any] = {}
        for key, frames in sorted(batched.items()):
            assoc, exist, gone, present = [], [], [], []
            for b in frames:
                part = frame_parts(heads, b, pw)
                if "association" in part:
                    assoc.append(part["association"])
                if "existence" in part:
                    exist.append(part["existence"])
                    for score, label in zip(*part["scores"]):
                        (gone if label >= 0.5 else present).append(float(score))
            per_block[key] = {"frames": len(frames),
                              "loss_association_mean": statistics.fmean(assoc) if assoc else None,
                              "loss_existence_weighted_mean": statistics.fmean(exist) if exist else None,
                              "existence_scores": score_block(gone, present, w)}
        out["seeds"][seed] = {"weights_sha256": payload["sha256"], "best_epoch": payload["training"].get("best_epoch"),
                              "pos_weight": w, "offset": getattr(heads, "existence_logit_offset", 0.0), "blocks": per_block}
        print(json.dumps({"seed": seed, **{k: {"auc": v["existence_scores"]["auc_gone_over_present"],
                                                "assoc": v["loss_association_mean"], "exist": v["loss_existence_weighted_mean"]}
                                            for k, v in per_block.items()}}), flush=True)
    out["not_available"] = "per-epoch split losses: only the kept checkpoint of each seed was saved, so the split exists for it alone"
    out["wall_seconds"] = round(time.time() - started, 1)
    out["script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    Path(args.output).write_text(json.dumps(out, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
