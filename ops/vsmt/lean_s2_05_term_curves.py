#!/usr/bin/env python3
"""S2-05 per-term training curves (ruling 79-3 (ii)): replay one registered development training, read-only.

白话：开发训练只保存了"关联＋新建"与"存在"两项相加后的 validation 曲线和最佳那一轮的权重，看不出联合早停有没有
在关联项还在下降时就停了（候选 A）。这个脚本按 ``lean_s2_05_development.py train`` 的同一数据、同一划分、同一
seed 与配方把那次训练原样重放一遍，每个 epoch 结束时额外记下两项各自的 validation 平均损失（在本臂自己的选择
house 记录上，以及可选的另一臂同一批选择 house 的记录上），并保存每个 epoch 的权重；跑完核对最终权重摘要和两条
曲线与原训练回执逐位相同，不同就判"未复现"并以退出码 3 结束。输入是开发趟根目录、趟名、轮次、源臂；输出是诊断
根目录下的 ``term_curves.json`` 与 ``epochs/epoch_NN.weights.json``。例如第 1 轮 VSMT-lean 若关联项在第 18 个
epoch 才最低、而联合损失在第 7 个 epoch 最低，就说明联合早停让关联头少训练了。它不产生任何用于表格的新权重，
不改训练规则，也不读 validation/test（开发 house 全在 train 块）。

Usage (clean worktree on the server, one thread like the registered training):
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python ops/vsmt/lean_s2_05_term_curves.py \
    --output-root <lean-s2-05-oracle-c150be0> --pass dagger_round_1 --round 1 --source-arm VSMT-lean \
    --also-score-arm AssocOnly --out-dir <vsmt_private/ruling79-term-curves-<commit>>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
for item in (ROOT / "src", HERE.parent):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import lean_s2_05_development as entry  # noqa: E402  (the registered training entry: same helpers, same data assembly)

RESULT_FILE = "term_curves.json"


def term_means(heads: Any, prepared: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Mean per-frame association(+birth) cross-entropy and existence BCE of ``heads`` on prepared frames.

    The same two terms ``lean_model.prepared_loss`` adds; each is averaged over the frames that have it (the registered
    validation loss averages their per-frame sum instead, so the two means do not add up to it).
    """

    import torch

    from vsmt import lean_model

    association: list[float] = []
    existence: list[float] = []
    with torch.no_grad():
        for frame in prepared:
            terms = []
            for pair_rows, birth_row, index in frame["association"]:
                logits = []
                if pair_rows is not None:
                    logits.append(heads["association"](pair_rows).reshape(-1))
                logits.append(heads["birth"](birth_row).reshape(-1))
                terms.append(torch.nn.functional.cross_entropy(torch.cat(logits).unsqueeze(0), index))
            if terms:
                association.append(float(torch.stack(terms).mean().item()))
            if frame["existence"] is not None and not lean_model.is_assoc_only(heads):
                rows, target, _ = frame["existence"]
                existence.append(float(torch.nn.functional.binary_cross_entropy_with_logits(heads["existence"](rows).reshape(-1), target).item()))
    return {"association_term_mean": sum(association) / len(association) if association else None, "association_frames": len(association),
            "existence_term_mean": sum(existence) / len(existence) if existence else None, "existence_frames": len(existence)}


def reproduction_check(result: Mapping[str, Any], receipt: Mapping[str, Any]) -> dict[str, bool]:
    """Did the replay reproduce the registered training bit for bit (weights digest, best epoch, both curves)?"""

    return {"weights_sha256": result["weights"]["sha256"] == receipt["weights_sha256"],
            "best_epoch": result["best_epoch"] == receipt["best_epoch"],
            "train_curve": list(result["train_curve"]) == list(receipt["train_curve"]),
            "validation_curve": list(result["validation_curve"]) == list(receipt["validation_curve"])}


def argmin_epoch(values: Sequence[float | None]) -> int | None:
    finite = [(value, epoch) for epoch, value in enumerate(values) if value is not None]
    return min(finite)[1] if finite else None  # ties to the earlier epoch, like the registered early stopping


def records_of(pass_root: Path, arm: str, houses: set[str] | None) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    """The arm's training records in cmd_train's order, split by the registered holdout (houses: the selection set)."""

    dirs = entry.episode_dirs(pass_root, arm)
    names = [d.name for d in dirs]
    holdout = entry.rh.holdout_split(names, seed=int(entry.load_json(entry.S1_02A_CONTRACT)["split_freeze"]["seed"]))
    train, validation = [], []
    for episode_dir in dirs:
        rows = entry.read_jsonl_gz(episode_dir / arm / "training_records.jsonl.gz")
        (train if episode_dir.name in holdout["training_houses"] else validation).extend(
            {k: v for k, v in row.items() if k != "tick"} for row in rows)
    if houses is not None:
        entry_selection = set(holdout["selection_houses"])
        if entry_selection != houses:
            raise SystemExit(f"[term-curves] refused: {arm} selection houses differ from the source arm's")
    return names, train, validation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-root", required=True, help="the S2-05 development root (holds <pass>/ and training/)")
    parser.add_argument("--pass", dest="pass_name", required=True)
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--source-arm", required=True)
    parser.add_argument("--assoc-only", action="store_true")
    parser.add_argument("--also-score-arm", default=None, help="also score each epoch on this arm's selection-house records of the same pass")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    import torch

    from vsmt import lean_model

    torch.set_num_threads(int(args.threads))
    out_dir = Path(args.out_dir).resolve()
    if (out_dir / RESULT_FILE).exists():
        print(f"[term-curves] refused: {out_dir / RESULT_FILE} exists", file=sys.stderr)
        return 2
    (out_dir / "epochs").mkdir(parents=True, exist_ok=True)
    commit = entry._git("rev-parse", "HEAD")
    dirty = bool(entry._git("status", "--porcelain"))
    output_root = Path(args.output_root).resolve()
    pass_root = output_root / args.pass_name
    arm = "AssocOnly" if args.assoc_only else "VSMT-lean"
    receipt_path = output_root / "training" / f"round{args.round}" / arm / "training_receipt.json"
    receipt = entry.load_json(receipt_path)
    training = entry.load_json(entry.S0_05_CONTRACT)["arms"]["VSMT-lean"]["training"]
    seed = int(training["seeds"][0])
    checks = {"source_pass": receipt["source_pass"] == args.pass_name, "source_arm": receipt["source_arm"] == args.source_arm,
              "seed": int(receipt["seed"]) == seed, "assoc_only": bool(receipt["assoc_only"]) == bool(args.assoc_only)}
    if not all(checks.values()):
        print(f"[term-curves] refused: the registered receipt does not describe this replay: {checks}", file=sys.stderr)
        return 2

    names, train_records, validation_records = records_of(pass_root, args.source_arm, None)
    selection = set(receipt["holdout"]["selection_houses"])
    if sorted(names) != sorted(receipt["holdout"]["training_houses"] + receipt["holdout"]["selection_houses"]):
        print("[term-curves] refused: the pass holds other houses than the registered training saw", file=sys.stderr)
        return 2
    if (len(train_records), len(validation_records)) != (receipt["train_frames"], receipt["validation_frames"]):
        print("[term-curves] refused: frame counts differ from the registered training", file=sys.stderr)
        return 2
    score_sets = {f"{args.pass_name}/{args.source_arm}": [lean_model.prepare_frame(r) for r in validation_records]}
    if args.also_score_arm:
        _, _, extra = records_of(pass_root, args.also_score_arm, selection)
        score_sets[f"{args.pass_name}/{args.also_score_arm}"] = [lean_model.prepare_frame(r) for r in extra]

    curves: dict[str, list[dict[str, Any]]] = {name: [] for name in score_sets}
    epoch_weights: list[dict[str, Any]] = []

    def callback(epoch: int, heads: Any) -> None:
        for name, prepared in score_sets.items():
            curves[name].append(term_means(heads, prepared))
        payload = lean_model.weights_payload(heads, training={"diagnostic": "ruling 79-3 (ii) replay", "epoch": epoch})
        path = out_dir / "epochs" / f"epoch_{epoch:02d}.weights.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        epoch_weights.append({"epoch": epoch, "weights_sha256": payload["sha256"], "file": str(path.relative_to(out_dir))})
        print(f"[term-curves] epoch {epoch}: " + ", ".join(
            f"{name} assoc {c[-1]['association_term_mean']:.4f}" + (f" exist {c[-1]['existence_term_mean']:.4f}" if c[-1]["existence_term_mean"] is not None else "")
            for name, c in curves.items()), flush=True)

    started = time.time()
    result = lean_model.train_heads(train_records, validation_records, learning_rate=float(training["learning_rate"]),
                                    weight_decay=float(training["weight_decay"]), epochs=int(training["epochs"]), seed=seed,
                                    assoc_only=args.assoc_only, device=args.device, epoch_callback=callback)
    reproduced = reproduction_check(result, receipt)
    summary = {name: {"association_best_epoch": argmin_epoch([c["association_term_mean"] for c in rows]),
                      "existence_best_epoch": argmin_epoch([c["existence_term_mean"] for c in rows])} for name, rows in curves.items()}
    output = {
        "stage": "vsmt.lean.s2_05.term_curves.v1", "ruling": "D-224-S1 ruling 79-3 (ii)", "code_commit": commit, "checkout_dirty": dirty,
        "script_sha256": hashlib.sha256(HERE.read_bytes()).hexdigest(), "argv": sys.argv[1:], "threads": args.threads,
        "registered_receipt": {"path": str(receipt_path), "sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
                               "weights_sha256": receipt["weights_sha256"], "best_epoch": receipt["best_epoch"],
                               "code_commit": receipt.get("code_commit")},
        "reproduced": reproduced, "reproduced_all": all(reproduced.values()),
        "epoch_numbering": "0-based (the registered best_epoch field)",
        "joint_validation_curve": result["validation_curve"], "train_curve": result["train_curve"], "joint_best_epoch": result["best_epoch"],
        "term_curves": curves, "term_best_epochs": summary, "epoch_weights": epoch_weights,
        "wall_seconds": round(time.time() - started, 1),
    }
    (out_dir / RESULT_FILE).write_text(json.dumps(output, indent=1), encoding="utf-8")
    print(f"[term-curves] reproduced {reproduced}; joint best {result['best_epoch']}; per-term best {summary}; {output['wall_seconds']} s")
    return 0 if output["reproduced_all"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
