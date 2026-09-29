#!/usr/bin/env python3
"""Direction B probe (read-only, first order): what a position gate on BIND would have done to the sealed round-1 decisions.

白话：方向 B 的名字是“身份与位置分开确认”，意思是一个色块要接到某个活动实体上，除了“像不像它”（身份）之外，还要过
“它能不能在那儿”（位置）这道门。这个脚本不改任何规则、不跑 runner，只把已封存的第 1 轮训练记录（公开特征加 teacher
标签）和已训好的头拿来离线重算学生的分配，然后问两个问题：（1）学生的误绑定里，有多少发生在位置门之外——色块质心离
实体质心超过 T 米、且色块框与实体框不相交——也就是位置门本可以拦下的；（2）teacher 认可的正确绑定里，有多少也在门外，
也就是位置门会误伤的（真搬动后先在新地方看见、或大件家具单视角表面壳跳了一面）。对每个 T，再把门外的格子禁掉重解同
一帧，看这个色块会改去哪里、改后对不对（修好／弄坏／没变）。例如 T=0.5 m 下 1,000 次误绑定里 700 次在门外、重解后 500
次改成了正确的新建或正确实体，而正确绑定只有 60 次被挡，就说明位置门值得立项。它是一阶估计：记忆状态按当时封存的取，
不会跟着改动往后演化；真实收益要等实现后跑 5 个种子。它不是新指标，不改合同，也不读任何私有文件。

Usage:
  python ops/vsmt/direction_b_probe.py run --output-root <pass root> --arm VSMT-lean --weights <weights.json> \\
      --label A31 --tolerances 0.5,1.0,2.0 --output <json> [--workers N] [--episodes k]
  python ops/vsmt/direction_b_probe.py summarise --inputs <json> [<json> ...] --output <json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
for item in (ROOT / "src", ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from vsmt import lean_assignment as la  # noqa: E402
from vsmt import lean_model as model  # noqa: E402

STAGE = "vsmt.lean.s2_05.direction_b_probe.v1"
OWN_PASS = "dagger_round_1"
DISTANCE_INDEX = la.ASSOCIATION_FEATURES.index("centroid_distance_m")
IOU_INDEX = la.ASSOCIATION_FEATURES.index("aabb_iou")
STATE_INDEX = {"active": la.ASSOCIATION_FEATURES.index("state_is_active"),
               "dormant": la.ASSOCIATION_FEATURES.index("state_is_dormant"),
               "retracted": la.ASSOCIATION_FEATURES.index("state_is_retracted")}
DISTANCE_BINS = ((0.0, 0.25), (0.25, 0.5), (0.5, 1.0), (1.0, 2.0), (2.0, 4.0), (4.0, float("inf")))
GATE_FLOOR_MARGIN = 1000.0
CAVEAT = ("first-order estimate on the sealed round-1 records: every frame is re-solved with the memory state the record was sealed "
          "with, so a gated decision does not propagate to later frames; the true effect of a gate needs the revised executor run "
          "over five seeds; the gate's box clause uses the sealed aabb_iou > 0 as the proxy for 'inside the entity box'")


def gate_allows(distance_m: float, aabb_iou: float, tolerance_m: float, *, box_clause: bool = True) -> bool:
    """The candidate position gate: a BIND to an active entity is allowed when the fragment centroid is within
    ``tolerance_m`` of the entity centroid, or (box clause) the two boxes overlap at all."""

    return float(distance_m) <= float(tolerance_m) or (box_clause and float(aabb_iou) > 0.0)


def column_kind(column: str, features_by_pair: Mapping[str, Sequence[float]], fragment_id: str) -> str:
    if column.startswith(la.BIRTH_COLUMN_PREFIX):
        return "birth"
    row = features_by_pair[f"{fragment_id}|{column}"]
    for state, index in STATE_INDEX.items():
        if float(row[index]) >= 0.5:
            return state
    return "unknown"


def frame_decisions(record: Mapping[str, Any], assignment: Mapping[str, str]) -> list[dict[str, Any]]:
    """One row per fragment the teacher labelled (labelled or birth): what the teacher wanted, what the student chose."""

    stage_a = record["stage_a"]
    features_by_pair = {f"{r['fragment_id']}|{r['entity_id']}": r["features"] for r in stage_a["association_rows"]}
    out = []
    for fragment_id in sorted(record["targets"]):
        target = record["targets"][fragment_id]
        if target["status"] not in model.ASSOCIATION_LOSS_STATUSES:
            continue
        wanted = str(target["target"])
        chosen = str(assignment[fragment_id])
        item = {"fragment_id": fragment_id, "target": wanted, "chosen": chosen,
                "target_kind": column_kind(wanted, features_by_pair, fragment_id),
                "chosen_kind": column_kind(chosen, features_by_pair, fragment_id)}
        for role, column in (("target", wanted), ("chosen", chosen)):
            key = f"{fragment_id}|{column}"
            if column.startswith(la.BIRTH_COLUMN_PREFIX) or key not in features_by_pair:
                item[f"{role}_distance_m"] = None
                item[f"{role}_iou"] = None
            else:
                item[f"{role}_distance_m"] = float(features_by_pair[key][DISTANCE_INDEX])
                item[f"{role}_iou"] = float(features_by_pair[key][IOU_INDEX])
        if chosen == wanted:
            item["outcome"] = {"active": "correct_bind", "dormant": "correct_reactivate", "retracted": "correct_reactivate",
                               "birth": "correct_birth"}.get(item["target_kind"], "correct_other")
        elif item["chosen_kind"] == "active":
            item["outcome"] = "wrong_bind"
        elif item["chosen_kind"] in ("dormant", "retracted"):
            item["outcome"] = "wrong_reactivate"
        elif item["chosen_kind"] == "birth":
            item["outcome"] = "birth_instead_of_bind"
        else:
            item["outcome"] = "wrong_other"
        out.append(item)
    return out


def gated_association_logits(stage_a: Mapping[str, Any], association_logits: Mapping[str, float], birth_logits: Mapping[str, float],
                             tolerance_m: float, *, box_clause: bool = True) -> tuple[dict[str, float], int]:
    """The same logits with every BIND cell outside the gate pushed below every legal cost; returns the count of gated cells."""

    values = list(association_logits.values()) + list(birth_logits.values())
    floor = (min(values) if values else 0.0) - GATE_FLOOR_MARGIN
    gated = dict(association_logits)
    count = 0
    for row in stage_a["association_rows"]:
        features = row["features"]
        if float(features[STATE_INDEX["active"]]) >= 0.5 and not gate_allows(features[DISTANCE_INDEX], features[IOU_INDEX], tolerance_m,
                                                                            box_clause=box_clause):
            gated[f"{row['fragment_id']}|{row['entity_id']}"] = floor
            count += 1
    return gated, count


def distance_bin(distance_m: float) -> str:
    for low, high in DISTANCE_BINS:
        if low <= distance_m < high:
            return f"[{low},{high})" if high != float("inf") else f"[{low},inf)"
    return "nan"


def empty_tally(tolerances: Sequence[float]) -> dict[str, Any]:
    per_t = {}
    for t in tolerances:
        per_t[str(t)] = {"gated_cells": 0,
                         "wrong_bind_outside_gate": 0, "wrong_bind_repaired": 0, "wrong_bind_still_wrong": 0,
                         "wrong_bind_regated_to": {"birth": 0, "active": 0, "dormant": 0, "retracted": 0},
                         "correct_bind_outside_gate": 0, "correct_bind_blocked_to": {"birth": 0, "active": 0, "dormant": 0, "retracted": 0},
                         "birth_instead_of_bind_target_outside_gate": 0,
                         "inside_gate_decisions_changed": 0}
    return {"decisions": 0, "outcomes": {}, "histogram": {}, "per_tolerance": per_t}


def add_histogram(tally: dict[str, Any], outcome: str, distance_m: float | None, iou: float | None) -> None:
    if distance_m is None:
        return
    key = f"{outcome}|{distance_bin(distance_m)}|{'iou_pos' if (iou or 0.0) > 0.0 else 'iou_zero'}"
    tally["histogram"][key] = tally["histogram"].get(key, 0) + 1


def frame_outcomes(record: Mapping[str, Any], association_logits: Mapping[str, float], birth_logits: Mapping[str, float],
                   tolerances: Sequence[float], tally: dict[str, Any], *, box_clause: bool = True) -> None:
    """Score one sealed frame: the student's decisions as trained, then the same frame re-solved under each gate."""

    stage_a = record["stage_a"]
    base = la.solve_frame(stage_a, association_logits=association_logits, birth_logits=birth_logits)["assignment"]
    decisions = frame_decisions(record, base)
    for item in decisions:
        tally["decisions"] += 1
        tally["outcomes"][item["outcome"]] = tally["outcomes"].get(item["outcome"], 0) + 1
        if item["outcome"] in ("correct_bind", "wrong_bind"):
            add_histogram(tally, item["outcome"], item["chosen_distance_m"], item["chosen_iou"])
    for t in tolerances:
        bucket = tally["per_tolerance"][str(t)]
        gated, count = gated_association_logits(stage_a, association_logits, birth_logits, t, box_clause=box_clause)
        bucket["gated_cells"] += count
        if count == 0:
            continue
        regated = la.solve_frame(stage_a, association_logits=gated, birth_logits=birth_logits)["assignment"]
        redone = {d["fragment_id"]: d for d in frame_decisions(record, regated)}
        for item in decisions:
            after = redone[item["fragment_id"]]
            if item["outcome"] == "wrong_bind" and not gate_allows(item["chosen_distance_m"], item["chosen_iou"], t, box_clause=box_clause):
                bucket["wrong_bind_outside_gate"] += 1
                bucket["wrong_bind_regated_to"][after["chosen_kind"] if after["chosen_kind"] in bucket["wrong_bind_regated_to"] else "active"] += 1
                if after["chosen"] == item["target"]:
                    bucket["wrong_bind_repaired"] += 1
                else:
                    bucket["wrong_bind_still_wrong"] += 1
            elif item["outcome"] == "correct_bind" and not gate_allows(item["chosen_distance_m"], item["chosen_iou"], t, box_clause=box_clause):
                bucket["correct_bind_outside_gate"] += 1
                bucket["correct_bind_blocked_to"][after["chosen_kind"] if after["chosen_kind"] in bucket["correct_bind_blocked_to"] else "active"] += 1
            elif after["chosen"] != item["chosen"]:
                bucket["inside_gate_decisions_changed"] += 1
            if (item["outcome"] == "birth_instead_of_bind" and item["target_kind"] == "active"
                    and not gate_allows(item["target_distance_m"], item["target_iou"], t, box_clause=box_clause)):
                bucket["birth_instead_of_bind_target_outside_gate"] += 1


def merge_tallies(into: dict[str, Any], other: Mapping[str, Any]) -> None:
    into["decisions"] += other["decisions"]
    for k, v in other["outcomes"].items():
        into["outcomes"][k] = into["outcomes"].get(k, 0) + v
    for k, v in other["histogram"].items():
        into["histogram"][k] = into["histogram"].get(k, 0) + v
    for t, bucket in other["per_tolerance"].items():
        mine = into["per_tolerance"][t]
        for k, v in bucket.items():
            if isinstance(v, dict):
                for kk, vv in v.items():
                    mine[k][kk] += vv
            else:
                mine[k] += v


# ---------------------------------------------------------------------------------------------------------------------
_WORKER: dict[str, Any] = {}


def _worker_init(weights_path: str) -> None:
    payload = json.loads(Path(weights_path).read_text(encoding="utf-8"))
    _WORKER["scorer"] = model.LeanScorer(model.load_heads(payload))


def _probe_episode(task: tuple[str, str, list[float], bool]) -> dict[str, Any]:
    import lean_s2_05_development as entry  # noqa: WPS433 (the registered entry's record reader)

    records_path, episode_id, tolerances, box_clause = task
    scorer = _WORKER["scorer"]
    tally = empty_tally(tolerances)
    started = time.time()
    records = entry.read_jsonl_gz(Path(records_path))
    for record in records:
        logits = scorer.association_and_birth_logits(record["stage_a"])
        frame_outcomes(record, logits["association_logits"], logits["birth_logits"], tolerances, tally, box_clause=box_clause)
    return {"episode_id": episode_id, "frames": len(records), "seconds": round(time.time() - started, 1), "tally": tally,
            "records_sha256": hashlib.sha256(Path(records_path).read_bytes()).hexdigest()}


def cmd_run(args: argparse.Namespace) -> int:
    import lean_s2_05_development as entry

    pass_root = Path(args.output_root).resolve() / OWN_PASS
    weights = Path(args.weights).resolve()
    if not weights.exists():
        print(f"[direction-b-probe] refused: {weights} missing", file=sys.stderr)
        return 2
    tolerances = [float(t) for t in args.tolerances.split(",")]
    dirs = entry.episode_dirs(pass_root, args.arm)
    if args.episodes:
        dirs = dirs[: int(args.episodes)]
    tasks = [(str(d / args.arm / "training_records.jsonl.gz"), d.name, tolerances, not args.no_box_clause) for d in dirs]
    workers = max(1, int(args.workers))
    results: list[dict[str, Any]] = []
    if workers == 1:
        _worker_init(str(weights))
        results = [_probe_episode(t) for t in tasks]
    else:
        with ProcessPoolExecutor(max_workers=workers, initializer=_worker_init, initargs=(str(weights),)) as pool:
            results = list(pool.map(_probe_episode, tasks))
    results.sort(key=lambda r: r["episode_id"])  # deterministic merge order
    pooled = empty_tally(tolerances)
    for r in results:
        merge_tallies(pooled, r["tally"])
    payload = json.loads(weights.read_text(encoding="utf-8"))
    out = {"stage": STAGE, "arm": args.arm, "label": args.label, "weights_sha256": payload.get("sha256"), "weights_file": str(weights),
           "pass_root": str(pass_root), "tolerances_m": tolerances, "box_clause": not args.no_box_clause, "workers": workers,
           "episodes": len(results), "frames": sum(r["frames"] for r in results), "pooled": pooled,
           "per_episode": [{k: v for k, v in r.items() if k != "tally"} for r in results],
           "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "caveat": CAVEAT}
    Path(args.output).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({"arm": args.arm, "label": args.label, "decisions": pooled["decisions"], "outcomes": pooled["outcomes"],
                      "per_tolerance": {t: {k: v for k, v in b.items() if not isinstance(v, dict)} for t, b in pooled["per_tolerance"].items()}},
                     indent=1))
    return 0


def summarise(inputs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Per (arm, label) and per tolerance: shares of wrong binds outside the gate / repaired and of correct binds blocked; then per arm
    pooled over labels (seeds)."""

    rows = []
    pooled: dict[str, dict[str, Any]] = {}
    for run in inputs:
        p = run["pooled"]
        wrong = p["outcomes"].get("wrong_bind", 0)
        correct = p["outcomes"].get("correct_bind", 0)
        for t, b in p["per_tolerance"].items():
            rows.append({"arm": run["arm"], "label": run["label"], "tolerance_m": float(t), "wrong_bind": wrong, "correct_bind": correct,
                         "wrong_outside_gate_share": (b["wrong_bind_outside_gate"] / wrong) if wrong else None,
                         "wrong_repaired_share": (b["wrong_bind_repaired"] / wrong) if wrong else None,
                         "correct_blocked_share": (b["correct_bind_outside_gate"] / correct) if correct else None,
                         "correct_blocked_to_birth": b["correct_bind_blocked_to"]["birth"],
                         "birth_instead_of_bind_target_outside_gate": b["birth_instead_of_bind_target_outside_gate"]})
        arm = pooled.setdefault(run["arm"], {"labels": [], "tally": None})
        arm["labels"].append(run["label"])
        if arm["tally"] is None:
            arm["tally"] = empty_tally(run["tolerances_m"])
        merge_tallies(arm["tally"], p)
    per_arm = {}
    for arm, item in pooled.items():
        p = item["tally"]
        wrong = p["outcomes"].get("wrong_bind", 0)
        correct = p["outcomes"].get("correct_bind", 0)
        per_arm[arm] = {"labels": item["labels"], "decisions": p["decisions"], "outcomes": p["outcomes"], "histogram": p["histogram"],
                        "per_tolerance": {t: {**{k: v for k, v in b.items()},
                                              "wrong_outside_gate_share": (b["wrong_bind_outside_gate"] / wrong) if wrong else None,
                                              "wrong_repaired_share": (b["wrong_bind_repaired"] / wrong) if wrong else None,
                                              "correct_blocked_share": (b["correct_bind_outside_gate"] / correct) if correct else None}
                                          for t, b in p["per_tolerance"].items()}}
    return {"rows": rows, "per_arm": per_arm}


def cmd_summarise(args: argparse.Namespace) -> int:
    inputs = [json.loads(Path(p).read_text(encoding="utf-8")) for p in args.inputs]
    out = {"stage": STAGE + ".summary", "inputs": {Path(p).name: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in args.inputs},
           **summarise(inputs), "caveat": CAVEAT}
    Path(args.output).write_text(json.dumps(out, indent=1), encoding="utf-8")
    for arm, item in out["per_arm"].items():
        print(arm, item["labels"], "decisions", item["decisions"], "outcomes", item["outcomes"])
        for t, b in item["per_tolerance"].items():
            print(f"  T={t}: wrong outside {b['wrong_outside_gate_share']:.3f} repaired {b['wrong_repaired_share']:.3f} "
                  f"correct blocked {b['correct_blocked_share']:.3f} (to birth {b['correct_bind_blocked_to']['birth']})"
                  if b["wrong_outside_gate_share"] is not None and b["correct_blocked_share"] is not None else f"  T={t}: {b}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="step", required=True)
    run = sub.add_parser("run")
    run.add_argument("--output-root", required=True, help="the S2-05 pass root that holds dagger_round_1")
    run.add_argument("--arm", required=True, choices=["VSMT-lean", "AssocOnly"])
    run.add_argument("--weights", required=True)
    run.add_argument("--label", required=True, help="e.g. A31: the seed condition the weights come from")
    run.add_argument("--tolerances", default="0.5,1.0,2.0")
    run.add_argument("--no-box-clause", action="store_true", help="gate on centroid distance only")
    run.add_argument("--workers", type=int, default=1)
    run.add_argument("--episodes", type=int, default=None)
    run.add_argument("--output", required=True)
    run.set_defaults(func=cmd_run)
    summ = sub.add_parser("summarise")
    summ.add_argument("--inputs", nargs="+", required=True)
    summ.add_argument("--output", required=True)
    summ.set_defaults(func=cmd_summarise)
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
