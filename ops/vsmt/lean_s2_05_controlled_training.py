#!/usr/bin/env python3
"""S2-05 controlled training for ruling 81-2: own-trajectory vs aggregated DAgger data at matched update budgets (diagnostics).

白话：裁决 81-2 要分清“第 1 轮加上第 0 轮的数据”（数据累积）和“单纯多训练”各自的作用。输入是开发趟根目录里已有的
两份训练记录——第 0 轮 ELU-P 轨迹和本臂第 1 轮轨迹——以及臂名和条件；输出是这一组的最佳检查点权重和训练回执。
四组条件（两个学习臂都跑）：
  A7   只用本臂第 1 轮记录，更新预算 U（= 20 遍本臂记录的更新次数），seed 7：新初始化下的参照；
  A19  同 A7，seed 19（登记的第二个 seed）：种子噪声底线；
  B    第 0 轮记录 + 本臂第 1 轮记录（都只取训练分区），更新预算 V（= 20 遍累积记录的更新次数），seed 7；
  C    只用本臂第 1 轮记录重复取样，更新预算同样是 V，seed 7：单纯多训练的作用。
四组都每 K 次更新（K = 本臂记录一遍的更新次数）在同一批验证记录（本臂第 1 轮、选择 house）上打分，取最低的检查点。
例如 VSMT-lean 的 B 比 C 好，说明好处来自数据而不是训练次数。它不改登记的训练配方，不写开发趟的 training/ 目录，
也不读 validation/test（开发 house 全在 train 块）。

Usage (clean worktree on the server, one thread like the registered training):
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python ops/vsmt/lean_s2_05_controlled_training.py \
    --output-root <lean-s2-05-oracle-c150be0> --arm VSMT-lean --condition B --out-dir <diag root>/training/VSMT-lean/B
  add --timing-updates N for a timing run (N updates, one checkpoint, projected wall time for every condition)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
for item in (ROOT / "src", HERE.parent):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import lean_s2_05_development as entry  # noqa: E402  (the registered training entry: same helpers and data assembly)

RECEIPT_FILE = "training_receipt.json"
WEIGHTS_FILE = "weights.json"
ROUND_0 = ("dagger_round_0", "ELU-P")
OWN_PASS = "dagger_round_1"
#: condition -> (training data, budget symbol, index into the registered seed list)
CONDITIONS: dict[str, tuple[str, str, int]] = {
    "A7": ("own", "U", 0),
    "A19": ("own", "U", 1),
    "B": ("aggregated", "V", 0),
    "C": ("own", "V", 0),
}
ARMS = ("VSMT-lean", "AssocOnly")


def plan_condition(condition: str, *, own_updates_per_pass: int, round0_updates_per_pass: int, epochs: int,
                   seeds: list[int]) -> dict[str, Any]:
    """The data, update budget, validation interval and seed of one condition (pure; ruling 81-2)."""

    if condition not in CONDITIONS:
        raise ValueError(f"condition_unknown:{condition}")
    if own_updates_per_pass < 1 or round0_updates_per_pass < 0 or epochs < 1:
        raise ValueError("update_counts_invalid")
    data, budget, seed_index = CONDITIONS[condition]
    u_budget = epochs * own_updates_per_pass
    v_budget = epochs * (own_updates_per_pass + round0_updates_per_pass)
    return {"condition": condition, "data": data, "update_budget": u_budget if budget == "U" else v_budget, "budget_symbol": budget,
            "U": u_budget, "V": v_budget, "evaluate_every": own_updates_per_pass, "seed": int(seeds[seed_index])}


def load_split(pass_root: Path, arm: str) -> dict[str, Any]:
    """One arm's training records in the registered entry's order, split by the registered holdout, with file digests."""

    dirs = entry.episode_dirs(pass_root, arm)
    names = [d.name for d in dirs]
    holdout = entry.rh.holdout_split(names, seed=int(entry.load_json(entry.S1_02A_CONTRACT)["split_freeze"]["seed"]))
    train, validation, files = [], [], {}
    for episode_dir in dirs:
        path = episode_dir / arm / "training_records.jsonl.gz"
        files[f"{pass_root.name}/{episode_dir.name}/{arm}/training_records.jsonl.gz"] = hashlib.sha256(path.read_bytes()).hexdigest()
        rows = entry.read_jsonl_gz(path)
        (train if episode_dir.name in holdout["training_houses"] else validation).extend(
            {k: v for k, v in row.items() if k != "tick"} for row in rows)
    return {"names": names, "holdout": holdout, "train": train, "validation": validation, "files": files}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-root", required=True, help="the S2-05 development root (holds dagger_round_0/ and dagger_round_1/)")
    parser.add_argument("--arm", required=True, choices=ARMS)
    parser.add_argument("--condition", required=True, choices=sorted(CONDITIONS))
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--timing-updates", type=int, default=None, help="timing run: stop after N updates with one checkpoint")
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    import torch

    from vsmt import lean_model

    torch.set_num_threads(int(args.threads))
    out_dir = Path(args.out_dir).resolve()
    if (out_dir / RECEIPT_FILE).exists():
        print(f"[controlled-training] refused: {out_dir / RECEIPT_FILE} exists", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)
    training = entry.load_json(entry.S0_05_CONTRACT)["arms"]["VSMT-lean"]["training"]
    lean_model.recipe_matches_contract(learning_rate=training["learning_rate"], epochs=training["epochs"], seeds=training["seeds"],
                                       dagger_rounds=training["dagger_rounds"], main_table_round=training["main_table_round"])
    assoc_only = args.arm == "AssocOnly"
    output_root = Path(args.output_root).resolve()
    started = time.time()
    own = load_split(output_root / OWN_PASS, args.arm)
    round0 = load_split(output_root / ROUND_0[0], ROUND_0[1])
    if sorted(own["holdout"]["selection_houses"]) != sorted(round0["holdout"]["selection_houses"]):
        print("[controlled-training] refused: the two sources' holdout splits differ", file=sys.stderr)
        return 2
    own_per_pass = lean_model.updates_per_pass(own["train"], assoc_only=assoc_only, device=args.device)
    round0_per_pass = lean_model.updates_per_pass(round0["train"], assoc_only=assoc_only, device=args.device)
    plan = plan_condition(args.condition, own_updates_per_pass=own_per_pass, round0_updates_per_pass=round0_per_pass,
                          epochs=int(training["epochs"]), seeds=list(training["seeds"]))
    train_records = (round0["train"] + own["train"]) if plan["data"] == "aggregated" else own["train"]
    budget, every = plan["update_budget"], plan["evaluate_every"]
    marks: list[tuple[int, float]] = []  # timing run: (updates, wall time) at every checkpoint, after its validation
    if args.timing_updates is not None:
        # two checkpoints, so the update rate is measured between them and the one-off record preparation inside the
        # training call is not spread over the updates (2026-09-28: the first timing did that and projected 24-47 h)
        budget = int(args.timing_updates)
        every = max(1, budget // 2)
    prepared_seconds = round(time.time() - started, 1)
    trained_at = time.time()
    result = lean_model.train_heads_by_updates(train_records, own["validation"], learning_rate=float(training["learning_rate"]),
                                               weight_decay=float(training["weight_decay"]), update_budget=budget, evaluate_every=every,
                                               seed=plan["seed"], assoc_only=assoc_only, device=args.device,
                                               checkpoint_callback=(lambda updates, heads: marks.append((updates, time.time())))
                                               if args.timing_updates is not None else None)
    train_seconds = time.time() - trained_at
    receipt: dict[str, Any] = {
        "stage": "vsmt.lean.s2_05.controlled_training.v1", "ruling": "D-224-S1 ruling 81-2", "arm": args.arm, "condition": args.condition,
        "timing_run": args.timing_updates is not None, "plan": plan, "update_budget_used": budget, "evaluate_every_used": every,
        "own_source": f"{OWN_PASS}/{args.arm}", "round0_source": f"{ROUND_0[0]}/{ROUND_0[1]}",
        "own_updates_per_pass": own_per_pass, "round0_updates_per_pass": round0_per_pass,
        "train_frames": len(train_records), "validation_frames": len(own["validation"]), "holdout": own["holdout"],
        "validation_records": f"{OWN_PASS}/{args.arm} selection houses", "input_files": {**round0["files"], **own["files"]},
        "training_values": {k: training[k] for k in ("learning_rate", "weight_decay", "epochs", "seeds")},
        "initialisation": lean_model.INITIALISATION_RULE, "early_stopping": lean_model.UPDATE_BUDGET_RULE,
        "checkpoints": result["checkpoints"], "best_update": result["best_update"], "updates_taken": result["updates_taken"],
        "diverged": result["diverged"], "weights_sha256": result["weights"]["sha256"],
        "code_commit": entry._git("rev-parse", "HEAD"), "checkout_dirty": bool(entry._git("status", "--porcelain")),
        "script_sha256": hashlib.sha256(HERE.read_bytes()).hexdigest(), "threads": args.threads, "device": args.device,
        "prepare_seconds": prepared_seconds, "train_seconds": round(train_seconds, 1), "wall_seconds": round(time.time() - started, 1),
    }
    if args.timing_updates is not None:
        # one validation pass timed on its own, so the projection charges every scheduled checkpoint
        timed = time.time()
        lean_model._mean_loss(result["heads"], [lean_model.prepare_frame(r, device=args.device) for r in own["validation"]])
        validation_seconds = time.time() - timed
        (first_updates, first_time), (last_updates, last_time) = marks[0], marks[-1]
        between = max(1, last_updates - first_updates)
        per_update = max(0.0, (last_time - first_time) - (len(marks) - 1) * validation_seconds) / between
        in_call_preparation = max(0.0, (first_time - trained_at) - first_updates * per_update - validation_seconds)
        projected = {}
        for condition in CONDITIONS:
            spec = plan_condition(condition, own_updates_per_pass=own_per_pass, round0_updates_per_pass=round0_per_pass,
                                  epochs=int(training["epochs"]), seeds=list(training["seeds"]))
            checkpoints = -(-spec["update_budget"] // spec["evaluate_every"])
            projected[condition] = round(prepared_seconds + in_call_preparation + spec["update_budget"] * per_update
                                         + checkpoints * validation_seconds)
        receipt.update({"projected_seconds": projected, "seconds_per_update": per_update, "validation_seconds": round(validation_seconds, 1),
                        "in_call_preparation_seconds": round(in_call_preparation, 1), "timing_marks": marks})
    else:
        (out_dir / WEIGHTS_FILE).write_text(json.dumps(result["weights"]), encoding="utf-8")
    (out_dir / RECEIPT_FILE).write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    print(f"[controlled-training] {args.arm} {args.condition}: U {plan['U']}, V {plan['V']}, K {plan['evaluate_every']}, budget {budget}, "
          f"best update {result['best_update']}, diverged {result['diverged']}, {receipt['wall_seconds']} s"
          + (f", projected {receipt['projected_seconds']}" if args.timing_updates is not None else ""), flush=True)
    return 1 if result["diverged"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
