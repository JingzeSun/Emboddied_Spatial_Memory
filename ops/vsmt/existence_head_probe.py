#!/usr/bin/env python3
"""Existence-head probe (read-only, first order): how the trained existence heads score the sealed existence candidates.

白话：LOG-283 的归因发现，被搬走或移除的物体在窗口后成为存在候选时，VSMT-lean 的存在头几乎从不撤回（0.1%～0.5%）。
这个脚本要分清原因是“阈值 τ_r 选高了”还是“头本身把已不在和还在分不开”。输入是第 1 轮已封存的训练记录里的存在候选行
（公开特征）和 teacher 的 gone／present 标签，以及每个种子训好的头；输出每个种子上存在头 σ(r) 对 gone 与 present 的区分度
（AUC）、两类的 σ 分位数，以及 τ_r 网格每一档下两类各有多少比例会被撤回。例如 τ_r=0.3 时 gone 的撤回比例仍只有 2%，
说明问题在头而不在阈值；若到 40% 而 present 只有 3%，说明头分得开、只是阈值选高了。它是一阶估计：候选集合与记忆状态按
封存时的取，撤回之后记忆怎么变不在其内；它不改任何规则、阈值或合同，也不读私有文件以外的新东西（标签本来就在记录里）。

Usage:
  python ops/vsmt/existence_head_probe.py --output-root <pass root> --weights <weights.json> --label A31 --output <json> [--workers N]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
for item in (ROOT / "src", ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from vsmt import lean_model as model  # noqa: E402

STAGE = "vsmt.lean.s2_05.existence_head_probe.v1"
OWN_PASS = "dagger_round_1"
ARM = "VSMT-lean"
TAU_GRID = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
QUANTILES = (0.1, 0.25, 0.5, 0.75, 0.9, 0.99)


def sigmoid(x: float) -> float:
    import math

    return 1.0 / (1.0 + math.exp(-x)) if x >= 0 else math.exp(x) / (1.0 + math.exp(x))


def auc(positive: Sequence[float], negative: Sequence[float]) -> float | None:
    """Probability that a random gone candidate scores above a random present one (ties count half), by ranks."""

    if not positive or not negative:
        return None
    labelled = sorted([(v, 1) for v in positive] + [(v, 0) for v in negative])
    rank_sum, index = 0.0, 0
    while index < len(labelled):
        end = index
        while end + 1 < len(labelled) and labelled[end + 1][0] == labelled[index][0]:
            end += 1
        mean_rank = (index + end) / 2.0 + 1.0
        rank_sum += mean_rank * sum(1 for k in range(index, end + 1) if labelled[k][1] == 1)
        index = end + 1
    n_pos, n_neg = len(positive), len(negative)
    return (rank_sum - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def quantiles(values: Sequence[float]) -> dict[str, float | None]:
    ordered = sorted(values)
    if not ordered:
        return {str(q): None for q in QUANTILES}
    return {str(q): ordered[min(len(ordered) - 1, int(q * len(ordered)))] for q in QUANTILES}


def summarise(scores: Mapping[str, Sequence[float]]) -> dict[str, Any]:
    gone, present = list(scores.get("gone", [])), list(scores.get("present", []))
    return {"candidates": {"gone": len(gone), "present": len(present)}, "auc_gone_over_present": auc(gone, present),
            "sigma_quantiles": {"gone": quantiles(gone), "present": quantiles(present)},
            "retract_share_at_tau": {str(t): {"gone": (sum(v >= t for v in gone) / len(gone)) if gone else None,
                                              "present": (sum(v >= t for v in present) / len(present)) if present else None}
                                     for t in TAU_GRID}}


_HEADS: dict[str, Any] = {}


def _init(weights: str) -> None:
    _HEADS["scorer"] = model.LeanScorer(model.load_heads(json.loads(Path(weights).read_text(encoding="utf-8"))))


def _episode(path: str) -> dict[str, list[float]]:
    import lean_s2_05_development as entry  # the registered entry's record reader

    scorer = _HEADS["scorer"]
    out: dict[str, list[float]] = {"gone": [], "present": []}
    for record in entry.read_jsonl_gz(Path(path)):
        rows = record["existence_rows"]
        if not rows:
            continue
        logits = scorer.existence_logits(rows, record["existence_feature_order"])
        for entity_id, label in record["existence_labels"].items():
            status = label["status"]
            if status in out and entity_id in logits:
                out[status].append(sigmoid(float(logits[entity_id])))
    return out


def main() -> int:
    import lean_s2_05_development as entry

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--weights", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    dirs = entry.episode_dirs(Path(args.output_root).resolve() / OWN_PASS, ARM)
    paths = [str(d / ARM / "training_records.jsonl.gz") for d in dirs]
    with ProcessPoolExecutor(max_workers=max(1, args.workers), initializer=_init, initargs=(args.weights,)) as pool:
        parts = list(pool.map(_episode, paths))
    pooled: dict[str, list[float]] = {"gone": [], "present": []}
    for part in parts:  # deterministic order: the entry's sorted episode directories
        for status, values in part.items():
            pooled[status].extend(values)
    weights = json.loads(Path(args.weights).read_text(encoding="utf-8"))
    out = {"stage": STAGE, "label": args.label, "weights_sha256": weights.get("sha256"), "episodes": len(paths),
           "records": f"{OWN_PASS}/{ARM} (the round-1 trajectories rolled out with the seed-7 round-0 heads, dev tau_r 0.5)",
           "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), **summarise(pooled),
           "caveat": "first order: the candidate sets are those sealed in the round-1 trajectories; retracting changes later memories"}
    Path(args.output).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("label", "candidates", "auc_gone_over_present", "retract_share_at_tau")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
