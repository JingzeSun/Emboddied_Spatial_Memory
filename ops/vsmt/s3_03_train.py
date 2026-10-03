#!/usr/bin/env python3
"""S3-03 training (ruling 104): one learned arm, one DAgger round, one registered seed, on streamed records.

白话：S3-03 要训练三个学习臂（VSMT-lean、AssocOnly、HeuristicLabel），每臂第 0 轮一次（种子 7）、第 1 轮五个种子。这个入口训练
其中一次：
  * 输入：一个或多个记录来源（``<趟根>:<臂>:<标签来源>``，例如第 0 轮 ELU-P 轨迹的 teacher 记录与本臂第 1 轮记录）、臂、轮、
    登记种子；训练 house 与选点 house 按裁决 104-1 1a 由 S3 train 清单定（前 240 训练、后 60 选点）；
  * 配方：裁决 99-1 冻结的那一版（逐字段编码、存在损失按类别加权、学习率余弦 1e-3 → 1e-5、梯度裁剪 1.0、存在决策用减去
    ln w 的 logit；第 1 轮的 VSMT-lean 与 HeuristicLabel 另存分组选点的权重），与开发集入口 ``ruling89_train.py
    --revision-91 [--group-selection]`` 同一份代码；
  * 内存：记录流式读两遍（第一遍只取算编码统计的列，第二遍逐条转张量、读完即丢），不再把全部原始记录放进内存；
  * 输出：``weights.json``（总损失选点）、第 1 轮分组臂的 ``weights_grouped.json``、``training_receipt.json``（逐 epoch 的
    train／validation 关联损失与存在损失、选中 epoch、类别权重、输入文件摘要、线程数、峰值内存）；``--best-so-far`` 时另在
    ``best_so_far/`` 下按摘要写出每个 epoch 末“到目前最好”的权重与指针，供调度器推测执行（裁决 104-7）。
例如第 1 轮 VSMT-lean 种子 31：读第 0 轮 ELU-P 记录与 VSMT-lean 第 1 轮记录，训 20 个 epoch，留下分组选点的头。它不选配置、
不读 validation 或 test 的任何记录（来源里的 episode 必须都在 S3 train 清单里），也不改配方。

Usage:
  python ops/vsmt/s3_03_train.py train --source <pass root>:<arm>:<teacher|heuristic> [--source ...] --arm VSMT-lean --round 1
      --seed 31 --out-dir <dir> [--threads 4] [--best-so-far]
  python ops/vsmt/s3_03_train.py probe --source ... --arm VSMT-lean --round 0 --seed 7 --houses 12 [--epochs 1] --out <probe.json>
      (ruling 104-2's training equivalence probe: the list-based ``train_heads`` and the streamed path on the same records)
  python ops/vsmt/s3_03_train.py time --source ... --arm VSMT-lean --round 0 --houses 20 --threads 1,2,3,4 --out <timing.json>
      (ruling 104-3: the per-epoch time of one training at each thread count, for the TRAIN_THREADS rule)

Exit codes: 0 trained; 3 diverged (the receipt is written: a result, ruling 102-9) or the probe differs; 2 refused.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
for item in (ROOT / "src", HERE.parent):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from vsmt import lean_arms as arms  # noqa: E402
from vsmt import lean_s3_03 as s3  # noqa: E402
from vsmt import lean_test_seal  # noqa: E402

STAGE = "vsmt.lean.s3_03.train.v1"
MANIFEST = ROOT / "configs" / "vsmt" / "lean_s3_01_manifests.json"
S0_05_CONTRACT = ROOT / "configs" / "vsmt" / "lean_s0_arms_v2.json"


class Refusal(Exception):
    """An input this entry will not train on; the message says why."""


def load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json_atomic(path: Path, payload: Any, *, indent: int | None = None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=indent), encoding="utf-8")
    os.replace(tmp, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def peak_rss_bytes() -> int | None:
    try:
        import resource

        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024  # Linux reports KiB
    except (ImportError, AttributeError):
        return None


# --------------------------------------------------------------------------
# sources: which episodes, which records, in which order
# --------------------------------------------------------------------------

def parse_source(spec: str) -> dict[str, Any]:
    """``<pass root>:<arm>:<teacher|heuristic>`` (the label source is always written, so a Windows drive letter cannot confuse it)."""

    parts = spec.rsplit(":", 2)
    if len(parts) != 3 or parts[2] not in s3.RECORD_FILES or not parts[0] or not parts[1]:
        raise Refusal(f"source must be <pass root>:<arm>:<{'|'.join(s3.RECORD_FILES)}>, not {spec!r}")
    return {"spec": spec, "root": Path(parts[0]).resolve(), "arm": parts[1], "label_source": parts[2]}


def source_episodes(source: dict[str, Any]) -> list[dict[str, Any]]:
    """The succeeded episodes of one source, sorted by episode id, with their record file and mask source."""

    root, arm = source["root"], source["arm"]
    if not root.is_dir():
        raise Refusal(f"source root missing: {root}")
    out = []
    for directory in sorted(p for p in root.iterdir() if p.is_dir()):
        receipt_path = directory / arm / "receipt.json"
        if not receipt_path.exists():
            continue
        receipt = load_json(receipt_path)
        if receipt.get("status") != "succeeded":
            continue
        records = directory / arm / s3.RECORD_FILES[source["label_source"]]
        if not records.exists():
            raise Refusal(f"records missing next to a succeeded receipt: {records}")
        out.append({"episode": directory.name, "path": records, "mask_source": receipt.get("mask_source")})
    if not out:
        raise Refusal(f"no succeeded {arm} episode under {root}")
    return out


def read_records(path: Path) -> Iterator[dict[str, Any]]:
    """One record at a time, in file order, without the tick (as the development entry passed them)."""

    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                row.pop("tick", None)
                yield row


def plan_sources(specs: Sequence[str], *, arm: str, round_index: int, manifest: dict[str, Any]) -> dict[str, Any]:
    """Every check before any record is read: the sources, the label source, the S3 train manifest, the split, one mask source."""

    settings = s3.training_settings(arm, round_index)
    sources = [parse_source(spec) for spec in specs]
    refusal = lean_test_seal.refusal([source["root"] for source in sources], reader="s3-03 train")  # ruling 103-1 / 104-6
    if refusal:
        raise Refusal(refusal)
    for source in sources:
        if source["label_source"] != settings["label_source"]:
            raise Refusal(f"{arm} trains on {settings['label_source']} records (ruling 104-1), not {source['spec']}")
        source["episodes"] = source_episodes(source)
    train_houses = s3.manifest_houses(manifest, "train")
    split = s3.checkpoint_split(train_houses)
    allowed = set(train_houses)
    outside = sorted({e["episode"] for source in sources for e in source["episodes"] if e["episode"] not in allowed})
    if outside:  # ruling 104-6: only S3 train episodes are trained on (never validation, test or development data)
        raise Refusal(f"{len(outside)} episodes are not in the S3 train manifest: {outside[:3]}")
    mask_sources = sorted({str(e["mask_source"]) for source in sources for e in source["episodes"]})
    if len(mask_sources) != 1 or mask_sources[0] == "None":
        raise Refusal(f"one mask source per training (ruling 72), found {mask_sources}")
    training, selection = set(split["training_houses"]), set(split["selection_houses"])
    present = {e["episode"] for source in sources for e in source["episodes"]}
    return {"settings": settings, "sources": sources, "split": split, "mask_source": mask_sources[0],
            "training_houses_present": sorted(present & training), "selection_houses_present": sorted(present & selection),
            "training_houses_absent": sorted(training - present), "selection_houses_absent": sorted(selection - present)}


def record_stream(plan: dict[str, Any], group: str, *, houses: set[str] | None = None) -> Callable[[], Iterator[dict[str, Any]]]:
    """A callable returning a fresh iterator over one group's records: sources in the given order, episodes sorted, rows in file order."""

    members = set(plan["split"]["training_houses" if group == "train" else "selection_houses"])
    if houses is not None:
        members &= houses

    def stream() -> Iterator[dict[str, Any]]:
        for source in plan["sources"]:
            for episode in source["episodes"]:
                if episode["episode"] in members:
                    yield from read_records(episode["path"])

    return stream


def recipe(settings: dict[str, Any]) -> dict[str, Any]:
    from vsmt import lean_model as model

    training = load_json(S0_05_CONTRACT)["arms"]["VSMT-lean"]["training"]
    model.recipe_matches_contract(learning_rate=training["learning_rate"], epochs=training["epochs"], seeds=training["seeds"],
                                  dagger_rounds=training["dagger_rounds"], main_table_round=training["main_table_round"])
    return {"learning_rate": float(training["learning_rate"]), "weight_decay": float(training["weight_decay"]),
            "epochs": int(training["epochs"]), "assoc_only": settings["assoc_only"], **settings["kwargs"]}


def set_threads(threads: int) -> dict[str, Any]:
    import torch

    torch.set_num_threads(int(threads))
    return {"requested": int(threads), "torch_num_threads": torch.get_num_threads(),
            "env": {name: os.environ.get(name) for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")}}


# --------------------------------------------------------------------------
# train
# --------------------------------------------------------------------------

def best_so_far_writer(out_dir: Path, *, uses: str) -> Callable[[dict[str, Any]], None]:
    """Ruling 104-7: at every epoch end, the weights the run would keep if it ended now, under their digest, and a pointer."""

    from vsmt import lean_model as model

    folder = out_dir / "best_so_far"

    def write(snapshot: dict[str, Any]) -> None:
        weights = model.snapshot_weights(snapshot)
        pointer: dict[str, Any] = {"epoch": snapshot["epoch"], "uses": uses, "total": None, "grouped": None,
                                   "written_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        for key, payload, epoch in (("total", weights["weights"], weights["best_epoch"]),
                                    ("grouped", weights["grouped"], weights["best_epoch_by_group"])):
            if payload is None:
                continue
            name = f"weights_{payload['sha256'][:16]}.json"
            if not (folder / name).exists():
                write_json_atomic(folder / name, payload)
            pointer[key] = {"sha256": payload["sha256"], "file": f"best_so_far/{name}", "best_epoch": epoch}
        write_json_atomic(folder / "pointer.json", pointer, indent=1)

    return write


def cmd_train(args: argparse.Namespace) -> int:
    from vsmt import lean_model as model

    if args.seed not in arms.SEEDS:
        raise Refusal(f"seed {args.seed} is not a registered seed {list(arms.SEEDS)}")
    if args.round == 0 and args.seed != arms.SEEDS[0]:
        raise Refusal(f"round 0 trains once, at the first registered seed {arms.SEEDS[0]} (ruling 99-1)")
    plan = plan_sources(args.sources, arm=args.arm, round_index=args.round, manifest=load_json(MANIFEST))
    out_dir = Path(args.out_dir).resolve()
    if (out_dir / "training_receipt.json").exists():
        raise Refusal(f"a training receipt already exists in {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    threads = set_threads(args.threads)
    values = recipe(plan["settings"])
    started = time.time()
    callback = best_so_far_writer(out_dir, uses=plan["settings"]["uses"]) if args.best_so_far else None
    result = model.train_heads_streamed(record_stream(plan, "train"), record_stream(plan, "selection"), seed=int(args.seed),
                                        device="cpu", best_callback=callback, **values)
    wall = round(time.time() - started, 1)
    write_json_atomic(out_dir / "weights.json", result["weights"])
    grouped = result.get("grouped")
    if grouped is not None:
        write_json_atomic(out_dir / "weights_grouped.json", grouped["weights"])
    files = [{"source": source["spec"], "episode": e["episode"], "sha256": sha256_file(e["path"]), "bytes": e["path"].stat().st_size}
             for source in plan["sources"] for e in source["episodes"]]
    receipt = {
        "stage": STAGE, "arm": args.arm, "round": args.round, "seed": args.seed, "assoc_only": plan["settings"]["assoc_only"],
        "label_source": plan["settings"]["label_source"], "uses": plan["settings"]["uses"], "mask_source": plan["mask_source"],
        "sources": [source["spec"] for source in plan["sources"]],
        "split": {"rule": plan["split"]["rule"], "training_houses_present": len(plan["training_houses_present"]),
                  "selection_houses_present": len(plan["selection_houses_present"]),
                  "training_houses_absent": plan["training_houses_absent"], "selection_houses_absent": plan["selection_houses_absent"]},
        "recipe": {**values, "registered_by": "ruling 99-1 (S0-05 arms.VSMT-lean.training.s2r_recipe); ruling 104-1",
                   "concatenation": "every source in full, no resampling; the budget is the registered epochs over the concatenation",
                   "preparation": "streamed in two passes (ruling 104-3): the encoding statistics, then the tensors; no raw record kept"},
        "train_frames": result["weights"]["training"]["train_frames"], "validation_frames": result["weights"]["training"]["validation_frames"],
        "updates_taken": result["updates_taken"], "existence_class_weight": result["weights"]["training"].get("existence_class_weight"),
        "train_curve": result["train_curve"], "validation_curve": result["validation_curve"], "best_epoch": result["best_epoch"],
        "train_curve_terms": result["train_curve_terms"], "validation_curve_terms": result["validation_curve_terms"],
        "diverged": result["diverged"], "weights_sha256": result["weights"]["sha256"],
        "group_selection": None if grouped is None else {"rule": model.GROUP_SELECTION_RULE, "best_epoch_by_group": grouped["best_epoch_by_group"],
                                                         "weights_sha256": grouped["weights"]["sha256"], "file": "weights_grouped.json"},
        "best_so_far": "best_so_far/pointer.json" if args.best_so_far else None,
        "threads": threads, "device": "cpu", "files": files, "code_commit": git_commit(), "wall_seconds": wall,
        "peak_rss_bytes": peak_rss_bytes(), "script_sha256": hashlib.sha256(HERE.read_bytes()).hexdigest(),
    }
    write_json_atomic(out_dir / "training_receipt.json", receipt, indent=1)
    print(f"[s3-03-train] {args.arm} round {args.round} seed {args.seed}: best epoch {result['best_epoch']}, diverged {result['diverged']}, "
          f"{result['updates_taken']} updates, weights {result['weights']['sha256'][:12]}"
          + ("" if grouped is None else f", grouped {grouped['weights']['sha256'][:12]} {grouped['best_epoch_by_group']}") + f", {wall} s")
    return 3 if result["diverged"] else 0


# --------------------------------------------------------------------------
# probe and timing on a subset of the houses
# --------------------------------------------------------------------------

def subset(plan: dict[str, Any], houses: int) -> set[str]:
    """The first ``houses`` training houses present (manifest order) and the first quarter as many selection houses present."""

    order = {house: i for i, house in enumerate(plan["split"]["training_houses"] + plan["split"]["selection_houses"])}
    training = sorted(plan["training_houses_present"], key=order.get)[:max(1, int(houses))]
    selection = sorted(plan["selection_houses_present"], key=order.get)[:max(1, int(houses) // 4)]
    if not training or not selection:
        raise Refusal("the subset needs at least one training and one selection house present")
    return set(training) | set(selection)


def cmd_probe(args: argparse.Namespace) -> int:
    from vsmt import lean_model as model

    plan = plan_sources(args.sources, arm=args.arm, round_index=args.round, manifest=load_json(MANIFEST))
    threads = set_threads(args.threads)
    chosen = subset(plan, args.houses)
    values = {**recipe(plan["settings"]), "epochs": int(args.epochs)}
    train_stream, selection_stream = record_stream(plan, "train", houses=chosen), record_stream(plan, "selection", houses=chosen)
    listed = model.train_heads(list(train_stream()), list(selection_stream()), seed=int(args.seed), device="cpu", **values)
    streamed = model.train_heads_streamed(train_stream, selection_stream, seed=int(args.seed), device="cpu", **values)
    compared = {
        "weights_sha256": [listed["weights"]["sha256"], streamed["weights"]["sha256"]],
        "grouped_sha256": [(listed.get("grouped") or {}).get("weights", {}).get("sha256"), (streamed.get("grouped") or {}).get("weights", {}).get("sha256")],
        "train_curve": [listed["train_curve"], streamed["train_curve"]],
        "validation_curve": [listed["validation_curve"], streamed["validation_curve"]],
        "validation_curve_terms": [listed["validation_curve_terms"], streamed["validation_curve_terms"]],
        "train_curve_terms": [listed["train_curve_terms"], streamed["train_curve_terms"]],
    }
    identical = all(a == b for a, b in compared.values())
    write_json_atomic(Path(args.out), {
        "stage": STAGE, "check": "ruling 104-2 training equivalence probe: the list-based train_heads and the streamed path",
        "arm": args.arm, "round": args.round, "seed": args.seed, "epochs": args.epochs, "houses": sorted(chosen),
        "identical": identical, "compared": {k: (v[0] == v[1]) for k, v in compared.items()},
        "weights_sha256": compared["weights_sha256"], "threads": threads, "code_commit": git_commit(),
        "checked_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=1)
    print(f"[s3-03-train probe] {args.arm} round {args.round}: identical={identical}")
    return 0 if identical else 3


def cmd_time(args: argparse.Namespace) -> int:
    """Two epochs on the subset at each thread count; the second epoch's wall time is the per-epoch time."""

    from vsmt import lean_model as model

    plan = plan_sources(args.sources, arm=args.arm, round_index=args.round, manifest=load_json(MANIFEST))
    chosen = subset(plan, args.houses)
    values = {**recipe(plan["settings"]), "epochs": 2}
    rows = []
    for count in [int(item) for item in str(args.threads).split(",") if item]:
        threads = set_threads(count)
        marks: list[float] = []
        model.train_heads_streamed(record_stream(plan, "train", houses=chosen), record_stream(plan, "selection", houses=chosen),
                                   seed=arms.SEEDS[0], device="cpu", epoch_callback=lambda epoch, heads: marks.append(time.time()), **values)
        rows.append({"threads": count, "thread_settings": threads, "epoch_seconds": round(marks[1] - marks[0], 3)})
        print(f"[s3-03-train time] {count} threads: {rows[-1]['epoch_seconds']} s per epoch")
    write_json_atomic(Path(args.out), {"stage": STAGE, "check": "ruling 104-3 per-epoch time by thread count on a fixed subset",
                                       "arm": args.arm, "round": args.round, "houses": sorted(chosen), "timings": rows,
                                       "code_commit": git_commit(), "measured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
                      indent=1)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("train", "probe", "time"):
        command = sub.add_parser(name)
        command.add_argument("--source", dest="sources", action="append", required=True)
        command.add_argument("--arm", required=True, choices=list(s3.TRAINED_ARMS))
        command.add_argument("--round", type=int, required=True, choices=list(s3.ROUNDS))
        if name == "train":
            command.add_argument("--seed", type=int, required=True)
            command.add_argument("--out-dir", required=True)
            command.add_argument("--threads", type=int, default=4)
            command.add_argument("--best-so-far", action="store_true")
        elif name == "probe":
            command.add_argument("--seed", type=int, default=arms.SEEDS[0])
            command.add_argument("--houses", type=int, default=12)
            command.add_argument("--epochs", type=int, default=1)
            command.add_argument("--threads", type=int, default=4)
            command.add_argument("--out", required=True)
        else:
            command.add_argument("--houses", type=int, default=20)
            command.add_argument("--threads", default="1,2,3,4")
            command.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        return {"train": cmd_train, "probe": cmd_probe, "time": cmd_time}[args.command](args)
    except (Refusal, s3.LeanS3_03Error) as exc:
        print(f"[s3-03-train] refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
