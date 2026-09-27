#!/usr/bin/env python3
"""S2-05 attribution export (after LOG-270): read-only statistics for the checks before ruling 79.

白话：开发表显示 VSMT-lean 在节点 F1 上输给 AssocOnly、在陈旧实体上赢它。裁决 79 之前要分清原因：
存在标签有多少是"真被干预拿走/搬走"、多少只是"实体位置记偏"（D1），错误集中在变化过的物体还是
从未变化的物体（H2），关联与存在两类决定各错多少（H3），以及两个学习臂的关联头在同一批留出记录上
谁的关联损失更低（H1）。输入是服务器上已完成的三趟产物、训练权重与 S1-02 的干预记录；输出是一个
带来源提交、脚本摘要与输入文件摘要的 JSON。它只读，不写任何趟的根目录，不读 validation/test
（开发 house 全在 train 块）。它不能给出每帧学生选了哪个原子或去重合并了谁：这些没有落盘，需要确定性
重跑（LOG-270）。

v2（裁决 79-2，2026-09-28）：窗口阶段改用评价器的口径（帧号 > window_end 才算窗口后；v1 用 >= 把窗口最后一帧、
也就是干预前的状态算进了窗口后，LOG-271 的"被拿走物体窗口后漏记"因此全是边界帧）；另把 gone(moved) 标签按
三项交叉拆开：本帧该物体有没有色块、该物体此刻有没有别的实体在 δ_moved 内承载（它不在 wrongly_absent 里）、
实体离物体中心多远（分档）。白话：输入是已落盘的逐帧标签，输出"撤回正标签到底落在什么实体上"。例如物体本帧
有色块、又有别的实体承载，这个未被匹配的实体多半是重复实体，撤回它不伤节点指标，不能直接叫噪声。标签行里没有
逐实体的存在决定、也没有 gone 候选的框，所以"框内/框外"与假撤回的拆分放在节点审计 v3 的重跑里（同一裁决）。

Usage (from a clean worktree on the server):
  python ops/vsmt/lean_s2_05_attribution_export.py --pass-root <lean-s2-05-oracle-c150be0> \
    --calibration-root <lean-s2-05-oracle-850c533> --episode-roots <02a>,<02b> --output <exports/...json> --workers 15
"""

from __future__ import annotations

import argparse
import collections
import glob
import gzip
import hashlib
import json
import multiprocessing
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

PASS_ARMS = {
    "dagger_round_0": ("ELU-P",),
    "dagger_round_1": ("VSMT-lean", "AssocOnly"),
    "development_table": ("VSMT-lean", "AssocOnly", "NoVersion", "TAF", "RAC", "LOW"),
}
DIAGNOSTIC_KEYS = ("interventions", "carriers_before_move", "reobserved_at", "old_place_observable_since_intervention")


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def episode_dir(roots: list[str], episode: str) -> str:
    for root in roots:
        if os.path.isdir(os.path.join(root, episode)):
            return os.path.join(root, episode)
    raise SystemExit(f"episode root missing for {episode}")


def read_interventions(roots: list[str], episode: str) -> dict[str, Any]:
    base = episode_dir(roots, episode)
    record = json.load(open(os.path.join(base, "provenance", "interventions.json")))
    window = json.load(open(os.path.join(base, "provenance", "window_segment.json")))
    executed = [{k: item.get(k) for k in ("kind", "object_id", "source", "destination", "verified_pixels",
                                         "executor", "placement_tries", "error", "executed")}
                for item in record.get("executed", [])]
    return {"null_window": record.get("null_window"), "executed": executed, "window_segment": window.get("segment"),
            "window_mode": window.get("mode"),
            "files": {name: sha256_file(os.path.join(base, "provenance", name)) for name in ("interventions.json", "window_segment.json")}}


PHASE_AFTER = "after_window"
PHASE_BEFORE = "at_or_before_window_end"
#: gone(moved) displacement bins in metres (the label needs more than delta_moved_m = 0.5 m)
DISPLACEMENT_BINS_M = (0.75, 1.0, 2.0)


def phase_of(frame_index: int, window_end: int | None) -> str:
    """The evaluator's rule (lean_evaluation._after_window): after the window means frame_index > window_end."""

    return PHASE_AFTER if window_end is not None and int(frame_index) > window_end else PHASE_BEFORE


def displacement_bin(value: Any) -> str:
    if value is None:
        return "unknown"
    lower = 0.5
    for upper in DISPLACEMENT_BINS_M:
        if float(value) <= upper:
            return f"{lower}-{upper}"
        lower = upper
    return f">{lower}"


def new_counters() -> dict[str, Any]:
    return {"existence": collections.Counter(),         # (status, reason, class, phase) -> entity-frames
            "gone_moved_split": collections.Counter(),  # (class, phase, fragment this frame, other near carrier, displacement bin)
            "stale": collections.Counter(),             # (class, phase) -> entity-frames (class via that frame's existence label key)
            "absent": collections.Counter(),            # (class, phase) -> object-frames wrongly absent
            "in_scope": collections.Counter(),          # (class, phase) -> object-frames in the truth scope
            "decomposition": {"association": collections.Counter(), "existence": collections.Counter()},
            "node": collections.Counter(), "node_iou": collections.Counter()}


def tally_row(row: dict[str, Any], intervened: dict[str, str], window_end: int | None, counters: dict[str, Any]) -> None:
    """Add one labels.jsonl.gz row to the counters (pure bookkeeping, no file access)."""

    phase = phase_of(int(row["frame_index"]), window_end)
    fragment_keys = {str(t.get("key")) for t in (row.get("targets") or {}).values() if t.get("key") is not None}
    wrongly_absent = set(row.get("wrongly_absent_objects") or [])
    in_scope_now = set(row.get("truth_in_scope") or [])
    key_of: dict[str, str] = {}
    for entity_id, label in (row.get("existence_labels") or {}).items():
        key = label.get("key")
        if key is not None:
            key_of[entity_id] = key
        klass = intervened.get(key, "never_intervened") if key is not None else "no_key"
        counters["existence"][(label.get("status"), label.get("reason"), klass, phase)] += 1
        if label.get("status") == "gone" and label.get("reason") == "moved":
            # the candidate itself sits more than delta away (that is the label), so a carrier within delta is another
            # entity; wrongly_absent is scored on the committed memory of the same frame with the strict centroid rule
            carrier = "not_in_scope" if key not in in_scope_now else ("no" if key in wrongly_absent else "yes")
            counters["gone_moved_split"][(klass, phase, "yes" if key in fragment_keys else "no", carrier,
                                         displacement_bin(label.get("displacement_m")))] += 1
    for entity_id in row.get("stale_entities") or []:
        key = key_of.get(entity_id)
        counters["stale"][(intervened.get(key, "never_intervened") if key else "key_not_in_frame_labels", phase)] += 1
    for key in wrongly_absent:
        counters["absent"][(intervened.get(key, "never_intervened"), phase)] += 1
    for key in in_scope_now:
        counters["in_scope"][(intervened.get(key, "never_intervened"), phase)] += 1
    for part in ("association", "existence"):
        for name, value in ((row.get("decomposition") or {}).get(part) or {}).items():
            if isinstance(value, (int, float)):
                counters["decomposition"][part][name] += value
    for target, source in ((counters["node"], "node_prf1"), (counters["node_iou"], "node_prf1_iou")):
        for name in ("matched", "predicted", "truth"):
            target[name] += int((row.get(source) or {}).get(name) or 0)


def _rows(counter: collections.Counter) -> list[list[Any]]:
    return [[*k, v] for k, v in sorted(counter.items(), key=lambda kv: tuple(map(str, kv[0])))]


def unit_stats(task: tuple[str, str, str, str, dict[str, str]]) -> dict[str, Any]:
    """One (pass, arm, episode): label cross-tabs, decomposition sums, node counts and the receipt diagnostics."""

    pass_root, pass_name, arm, episode, intervened = task
    base = os.path.join(pass_root, pass_name, episode, arm)
    receipt = json.load(open(os.path.join(base, "receipt.json")))
    window_end = int(receipt["window"][1]) if receipt.get("window") else None
    counters = new_counters()
    frames = 0
    with gzip.open(os.path.join(base, "labels.jsonl.gz"), "rt") as handle:
        for line in handle:
            tally_row(json.loads(line), intervened, window_end, counters)
            frames += 1
    diagnostics = receipt.get("diagnostics", {})
    return {
        "pass": pass_name, "arm": arm, "episode": episode, "frames": frames, "window_end": window_end,
        "existence_labels": _rows(counters["existence"]),
        "gone_moved_split": _rows(counters["gone_moved_split"]),
        "stale_entity_frames": _rows(counters["stale"]),
        "wrongly_absent_object_frames": _rows(counters["absent"]),
        "in_scope_object_frames": _rows(counters["in_scope"]),
        "decomposition": {part: dict(counter) for part, counter in counters["decomposition"].items()},
        "node_counts": dict(counters["node"]), "node_iou_counts": dict(counters["node_iou"]),
        "atoms": receipt.get("atoms"), "final_entities_by_state": receipt.get("final_entities_by_state"),
        "report": receipt.get("report"),
        "diagnostics": {**{k: diagnostics.get(k) for k in DIAGNOSTIC_KEYS},
                        "recovery_per_object": (diagnostics.get("recovery") or {}).get("per_object"),
                        "decomposition_totals": diagnostics.get("decomposition_totals")},
        "files": {name: sha256_file(os.path.join(base, name)) for name in ("labels.jsonl.gz", "receipt.json")},
    }


def head_term_losses(pass_root: str, records_by_source: dict[str, list[str]]) -> dict[str, Any]:
    """H1: per-term mean validation losses of every trained head set on the same sealed selection-house records."""

    import torch
    from vsmt import lean_model

    torch.set_num_threads(1)
    heads = {}
    for round_name in ("round0", "round1"):
        for arm in ("VSMT-lean", "AssocOnly"):
            path = os.path.join(pass_root, "training", round_name, arm, "weights.json")
            payload = json.load(open(path))
            loaded = lean_model.load_heads(payload)
            loaded.eval()
            heads[f"{round_name}/{arm}"] = {"heads": loaded, "sha256": payload["sha256"], "file_sha256": sha256_file(path)}
    out: dict[str, Any] = {"head_sets": {name: {"weights_sha256": h["sha256"], "file_sha256": h["file_sha256"]} for name, h in heads.items()},
                           "record_sets": {}}
    for source, files in records_by_source.items():
        prepared = []
        for path in files:
            with gzip.open(path, "rt") as handle:
                for line in handle:
                    row = json.loads(line)
                    prepared.append(lean_model.prepare_frame({k: v for k, v in row.items() if k != "tick"}))
        result: dict[str, Any] = {"frames": len(prepared), "files": {os.path.relpath(p, pass_root): sha256_file(p) for p in files}}
        for name, entry in heads.items():
            model = entry["heads"]
            association, existence = [], []
            with torch.no_grad():
                for frame in prepared:
                    terms = []
                    for pair_rows, birth_row, index in frame["association"]:
                        logits = []
                        if pair_rows is not None:
                            logits.append(model["association"](pair_rows).reshape(-1))
                        logits.append(model["birth"](birth_row).reshape(-1))
                        terms.append(torch.nn.functional.cross_entropy(torch.cat(logits).unsqueeze(0), index))
                    if terms:
                        association.append(float(torch.stack(terms).mean().item()))
                    if frame["existence"] is not None and not lean_model.is_assoc_only(model):
                        rows, target, _ = frame["existence"]
                        existence.append(float(torch.nn.functional.binary_cross_entropy_with_logits(
                            model["existence"](rows).reshape(-1), target).item()))
            result[name] = {"association_term_mean": sum(association) / len(association) if association else None,
                            "association_frames": len(association),
                            "existence_term_mean": sum(existence) / len(existence) if existence else None,
                            "existence_frames": len(existence)}
        out["record_sets"][source] = result
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pass-root", required=True)
    parser.add_argument("--calibration-root", required=True)
    parser.add_argument("--episode-roots", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    started = time.time()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip())
    roots = [r for r in args.episode_roots.split(",") if r]
    pass_root = os.path.abspath(args.pass_root)
    episodes = sorted(os.path.basename(p) for p in glob.glob(os.path.join(pass_root, "development_table", "procthor*")))
    interventions = {e: read_interventions(roots, e) for e in episodes}
    intervened = {e: {item["object_id"]: item["kind"] for item in interventions[e]["executed"] if item.get("executed", True)}
                  for e in episodes}
    tasks = [(pass_root, p, a, e, intervened[e]) for p, arms in PASS_ARMS.items() for a in arms for e in episodes]
    with multiprocessing.Pool(max(1, args.workers)) as pool:
        units = pool.map(unit_stats, tasks, chunksize=1)
    calibration = [unit_stats((os.path.abspath(args.calibration_root), "calibration", "TAF", e, intervened[e])) for e in episodes]

    training = {}
    selection: dict[str, list[str]] = {}
    for round_name in ("round0", "round1"):
        for arm in ("VSMT-lean", "AssocOnly"):
            path = os.path.join(pass_root, "training", round_name, arm, "training_receipt.json")
            receipt = json.load(open(path))
            training[f"{round_name}/{arm}"] = {k: receipt.get(k) for k in ("best_epoch", "train_curve", "validation_curve", "weights_sha256",
                                                                           "source_pass", "source_arm", "seed", "wall_seconds")}
            training[f"{round_name}/{arm}"]["file_sha256"] = sha256_file(path)
            selection[f"{receipt['source_pass']}/{receipt['source_arm']}"] = sorted(receipt["holdout"]["selection_houses"])
    records = {source: [os.path.join(pass_root, source.split("/")[0], house, source.split("/")[1], "training_records.jsonl.gz")
                        for house in houses] for source, houses in selection.items()}
    h1 = head_term_losses(pass_root, records)

    from vsmt.lean_intervention import assign_split

    pool_ids = [f"procthor10k-0.1.2-train-{i:05d}" for i in range(10000)]
    split = assign_split(pool_ids, seed=20260920, train=10000 - 150, validation=50, test=100)
    position = {h: i for i, h in enumerate(split["train"])}
    manifests = {}
    for pattern in ("lean-s1-02a-5f9aa71/*.json", "lean-s1-02b-5f9aa71/*.json"):
        for path in glob.glob(os.path.join("/root/autodl-tmp/vsmt_outputs", pattern)):
            manifests[os.path.relpath(path, "/root/autodl-tmp")] = sha256_file(path)
    for path in (glob.glob("/root/autodl-tmp/vsmt_caches/lean-s1-03-oracle-8ebbd05/*.json")
                 + glob.glob("/root/autodl-tmp/vsmt_private/lean-s1-04-geometry-154776d/*.json")
                 + glob.glob(os.path.join(pass_root, "*", "*.json")) + [os.path.join(pass_root, "development_table.json")]):
        manifests[os.path.relpath(path, "/root/autodl-tmp")] = sha256_file(path)

    output = {
        "stage": "vsmt.lean.s2_05.attribution_export.v2", "code_commit": commit, "checkout_dirty": dirty,
        "script_sha256": sha256_file(__file__), "argv": sys.argv[1:], "workers": args.workers,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)), "wall_seconds": round(time.time() - started, 1),
        "not_available_without_rerun": ["per-frame student atom choices", "memory transaction log and dedup merge events",
                                        "per-epoch checkpoints and per-term training curves",
                                        "per-entity existence decisions and the box test of gone candidates (node audit v3, ruling 79-2)"],
        "phase_rule": "after_window means frame_index > window_end (the evaluator's rule); v1 used >=",
        "gone_moved_split_fields": ["object_class", "phase", "fragment_of_the_object_this_frame",
                                    "other_entity_within_delta_on_the_committed_memory", "displacement_bin_m"],
        "episodes": episodes,
        "split_check": {"rule": "assign_split over procthor10k-0.1.2-train-00000..09999, seed 20260920, test 100, validation 50",
                        "in_test": [e for e in episodes if e in split["test"]], "in_validation": [e for e in episodes if e in split["validation"]],
                        "train_block_positions": {e: position.get(e) for e in episodes}},
        "interventions": interventions,
        "units": units, "calibration_units": calibration,
        "training": training, "h1_term_losses": h1, "manifests": manifests,
    }
    Path(args.output).write_text(json.dumps(output), encoding="utf-8")
    print(f"[attribution-export] {len(units)} units + {len(calibration)} calibration, {len(manifests)} manifests, "
          f"{output['wall_seconds']} s -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
