#!/usr/bin/env python3
"""S4 E1 (user 2026-10-08: 「第 2～5 项全按推荐」, item 3 (a)): the read-only context for the LLM-op appendix table.

白话：LLM-op 附录只跑了一条 validation episode（``train-08800``，每套前端 n＝1）。审稿人会问“这条是不是特意挑的难题”。这个
脚本回答它：输入是 S3-03 运行根里九个臂按 S3-04 冻结配置跑出的合并 validation 审计（每个运行 43 条 episode 的逐条报告）、
validation cache 的逐条回执（帧数、色块数）、已提交的 S3-04 冻结回执（每臂选中的配置）、S3-03 读数导出（核对用）与 LLM-op
导出；输出一份 ``results/vsmt_lean_s4_llm_op_context_<commit>.json``：每套前端、每个臂在这条 episode 上的节点 F1（两列）、
假撤回率与污染 AUC，同一臂在全部 validation episode 上的均值、标准差与这条的百分位，LLM-op 自己的值，以及这条 episode 的
帧数、每帧色块数与 VSMT-lean 收尾时在记忆里的实体数在 validation 里的百分位。例如 TAF 在这条上的节点 F1 若排在它自己
validation 分布的第 20 百分位，就说明这条对 TAF 偏难但不反常。学习臂先在每条 episode 上取 5 个种子的均值，再看分布。
它只读文件：不跑审计、不训练、不读 test、不调用 LLM；它是描述性读数，不做显著性检验（裁决 105／108 的附录口径）。

一致性核对（任一不过即退出码 4，照写不过的项）：每个合并文件的臂名与色块来源对得上、43 条 episode 与读数导出的清单相同；
按冻结配置读出的节点 F1、节点 F1（IoU）与污染 AUC 在全部 43 条上的均值，与已提交读数导出 ``readings[arm][config].mean``
相等（学习臂为种子均值的均值）。

Usage (on the host that holds the S3-03 run root, from a clean checkout of a commit that contains this script):
    python ops/vsmt/s4_llm_op_context.py --run-root /root/autodl-tmp/vsmt_private/s3-03-run \
        --cache-root instance=/root/autodl-tmp/vsmt_caches/s3-02-instance-3f6ef1d \
        --cache-root sam2=/root/autodl-tmp/vsmt_caches/s3-02-sam2-3f6ef1d [--out-dir results] [--replace]
Exit codes: 0 written; 2 refused (uncommitted changes to this script or the committed inputs, a missing input, or an existing
output without --replace); 4 written, but a consistency check failed; 1 an unexpected error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
STAGE = "vsmt.lean.s4.llm_op_context.v1"
FRONTS = ("instance", "sam2")
ARMS = ("VSMT-lean", "AssocOnly", "NoVersion", "HeuristicLabel", "HandCost", "TAF", "ELU-P", "RAC", "LOW")
SEEDED = ("VSMT-lean", "AssocOnly", "NoVersion", "HeuristicLabel")
SEEDS = (7, 19, 31, 43, 59)
MASK_SOURCE = {"instance": "simulator_instance_masks", "sam2": "sam2"}
#: (output key, report block, field)
METRICS = (
    ("node_f1", "node_prf1", "node_f1"),
    ("node_f1_iou", "node_prf1_iou", "node_f1"),
    ("false_retract_rate", "false_retract_rate", "false_retract_rate"),
    ("contamination_auc", "contamination_auc", "contamination_auc"),
)
#: metrics without an exclusion list on validation, whose all-episode mean must equal the committed reading
CHECKED = {"node_f1": "node_prf1", "node_f1_iou": "node_prf1_iou", "contamination_auc": "contamination_auc"}
FREEZE = "results/vsmt_lean_s3_04_freeze_dea8c20.json"
READINGS = "results/vsmt_lean_s3_03_readings_{front}_10f7013.json"
LLM_OP = "results/vsmt_lean_llm_op_dea8c20.json"
TOLERANCE = 1e-12
EXIT_OK, EXIT_REFUSED, EXIT_PROBLEMS = 0, 2, 4


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(ROOT), check=True, capture_output=True, text=True).stdout


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, indent=1))
    os.replace(tmp, path)


def percentile(value: float, population: Sequence[float]) -> float:
    """Mid-rank percentile of ``value`` in ``population``: share below plus half the share equal, times 100."""

    below = sum(1 for item in population if item < value)
    equal = sum(1 for item in population if item == value)
    return 100.0 * (below + 0.5 * equal) / len(population)


def summary(values: Mapping[str, float | None], episode: str) -> dict[str, Any]:
    """The arm's value on ``episode`` and its distribution over the validation episodes where the metric is defined."""

    defined = [value for value in values.values() if value is not None]
    target = values.get(episode)
    return {
        "episode_value": target,
        "validation_mean": statistics.fmean(defined) if defined else None,
        "validation_sd": statistics.stdev(defined) if len(defined) > 1 else None,
        "episodes_defined": len(defined),
        "episode_percentile": percentile(target, defined) if target is not None and defined else None,
    }


def run_files(run_root: Path, front: str, arm: str, config: int) -> list[Path]:
    stem = f"{arm}-c{config:02d}"
    names = [f"{stem}-s{seed}.json" for seed in SEEDS] if arm in SEEDED else [f"{stem}.json"]
    return [run_root / front / "merged" / name for name in names]


def per_episode_values(merged: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, float | None]]:
    """Per metric and episode the value, averaged over the runs (seeds) that define it."""

    out: dict[str, dict[str, float | None]] = {}
    episodes = [row["episode_id"] for row in merged[0]["per_episode"]]
    for key, block, field in METRICS:
        out[key] = {}
        for episode in episodes:
            values = []
            for run in merged:
                row = next(item for item in run["per_episode"] if item["episode_id"] == episode)
                value = (row["report"].get(block) or {}).get(field)
                if value is not None:
                    values.append(float(value))
            out[key][episode] = statistics.fmean(values) if len(values) == len(merged) else None
    return out


def in_memory_entities(merged: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    episodes = [row["episode_id"] for row in merged[0]["per_episode"]]
    out = {}
    for episode in episodes:
        counts = []
        for run in merged:
            row = next(item for item in run["per_episode"] if item["episode_id"] == episode)
            states = row["final_entities_by_state"]
            counts.append(int(states.get("active", 0)) + int(states.get("dormant", 0)))
        out[episode] = statistics.fmean(counts)
    return out


def front_context(front: str, run_root: Path, cache_root: Path, freeze: Mapping[str, Any], readings: Mapping[str, Any],
                  llm_op: Mapping[str, Any], inputs: dict[str, str], problems: list[str]) -> dict[str, Any]:
    llm_front = llm_op["fronts"][front]["episodes"][0]
    episode = llm_front["episode_id"]
    validation = sorted(readings["episodes"])
    arms: dict[str, Any] = {}
    vsmt_entities: dict[str, float] | None = None
    for arm in ARMS:
        selected = freeze["fronts"][front]["selection"]["arms"][arm]
        config = int(selected["selected"])
        paths = run_files(run_root, front, arm, config)
        merged = []
        for path in paths:
            inputs[str(path)] = file_sha256(path)
            run = load(path)
            if run.get("arm") != arm or run.get("mask_source") != MASK_SOURCE[front]:
                problems.append(f"{front}/{path.name}: arm {run.get('arm')!r} / mask_source {run.get('mask_source')!r}")
            if sorted(row["episode_id"] for row in run["per_episode"]) != validation:
                problems.append(f"{front}/{path.name}: episode list differs from the committed readings")
            merged.append(run)
        values = per_episode_values(merged)
        reading = readings["readings"][arm][str(config)]["mean"]
        for key, metric in CHECKED.items():
            mean = statistics.fmean(value for value in values[key].values() if value is not None)
            if reading.get(metric) is None or abs(mean - reading[metric]) > TOLERANCE:
                problems.append(f"{front}/{arm}: {metric} mean {mean!r} differs from the committed reading {reading.get(metric)!r}")
        if arm == "VSMT-lean":
            vsmt_entities = in_memory_entities(merged)
        arms[arm] = {"config_index": config, "config": selected["config"], "runs": [path.name for path in paths],
                     **{key: summary(values[key], episode) for key, _, _ in METRICS}}
    receipts = {}
    for name in validation:
        path = cache_root / "validation" / name / "receipt.json"
        inputs[str(path)] = file_sha256(path)
        receipt = load(path)
        receipts[name] = {"frames": int(receipt["frames"]), "fragments_per_frame": receipt["fragments"] / receipt["frames"]}
    report = llm_front["report"]
    describe = {
        "frames": receipts[episode]["frames"],
        "frames_percentile": percentile(receipts[episode]["frames"], [item["frames"] for item in receipts.values()]),
        "fragments_per_frame": receipts[episode]["fragments_per_frame"],
        "fragments_per_frame_percentile": percentile(receipts[episode]["fragments_per_frame"],
                                                     [item["fragments_per_frame"] for item in receipts.values()]),
        "vsmt_lean_entities_in_memory_at_end": vsmt_entities[episode] if vsmt_entities else None,
        "vsmt_lean_entities_in_memory_at_end_percentile": percentile(vsmt_entities[episode], list(vsmt_entities.values()))
        if vsmt_entities else None,
    }
    return {
        "episode_id": episode,
        "validation_episodes": len(validation),
        "episode": describe,
        "llm_op": {key: (report.get(block) or {}).get(field) for key, block, field in METRICS},
        "arms": arms,
    }


def sealed_refusal(paths: Sequence[Path]) -> str | None:
    """The test-seal guard (ruling 103) on what this script reads: the S3-03 run root and ``<cache root>/validation``.

    The guard is given the validation directory, not the cache root named on the command line: a marker in a directory
    directly below a path also covers that path, and the cache root is the parent of the sealed test root.
    """

    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from vsmt import lean_test_seal

    return lean_test_seal.refusal(paths, reader="s4-llm-op-context")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S4 E1: read-only context for the LLM-op appendix table")
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--cache-root", action="append", required=True, help="front=path, once per front end")
    parser.add_argument("--out-dir", default="results", type=Path)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args(argv)

    committed = [FREEZE, LLM_OP, *(READINGS.format(front=front) for front in FRONTS)]
    script = str(Path(__file__).resolve().relative_to(ROOT)).replace("\\", "/")
    dirty = [line[3:] for line in git("status", "--porcelain", "--", script, *committed).splitlines() if line.strip()]
    if dirty:
        print(f"refused: uncommitted changes in {dirty}", file=sys.stderr)
        return EXIT_REFUSED
    cache_roots = dict(item.split("=", 1) for item in args.cache_root)
    missing = [front for front in FRONTS if front not in cache_roots]
    if missing:
        print(f"refused: no --cache-root for {missing}", file=sys.stderr)
        return EXIT_REFUSED
    refusal = sealed_refusal([args.run_root, *(Path(cache_roots[front]) / "validation" for front in FRONTS)])
    if refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return EXIT_REFUSED
    head = git("rev-parse", "HEAD").strip()
    out_dir = args.out_dir if args.out_dir.is_absolute() else ROOT / args.out_dir
    out = out_dir / f"vsmt_lean_s4_llm_op_context_{head[:7]}.json"
    if out.exists() and not args.replace:
        print(f"refused: {out} exists (use --replace)", file=sys.stderr)
        return EXIT_REFUSED

    try:
        freeze, llm_op = load(ROOT / FREEZE), load(ROOT / LLM_OP)
        inputs = {name: file_sha256(ROOT / name) for name in committed}
        problems: list[str] = []
        fronts = {front: front_context(front, args.run_root, Path(cache_roots[front]), freeze,
                                       load(ROOT / READINGS.format(front=front)), llm_op, inputs, problems)
                  for front in FRONTS}
    except (OSError, KeyError, ValueError) as error:
        print(f"refused: {type(error).__name__}: {error}", file=sys.stderr)
        return EXIT_REFUSED
    payload = {
        "stage": STAGE,
        "authorization": "user 2026-10-08 「推送 e422b4d、d9889a6、3aba063；第 2～5 项全按推荐」, item 3 (a): read-only export on B1",
        "code_commit": head,
        "role": "descriptive context for the LLM-op appendix (n = 1 per front end); validation only, no test, no audit rerun",
        "rule": ("per arm the S3-04 frozen configuration; learned arms averaged over five seeds per episode; mean and sample SD over "
                 "the validation episodes where the metric is defined (false-retract rate is undefined where an arm made no "
                 "judged retraction); percentile = 100 x (share below + half the share equal)"),
        "inputs_sha256": dict(sorted(inputs.items())),
        "problems": problems,
        "fronts": fronts,
    }
    write_json(out, payload)
    print(f"{out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}: {len(problems)} problem(s)")
    return EXIT_PROBLEMS if problems else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
