#!/usr/bin/env python3
"""Ruling 89-2 / 89-3 mechanism checks on regenerated training records (read-only diagnostics).

白话：裁决 89 的存在侧与关联侧各有训练前要过的检查，这里只读已封存的训练记录（公开特征加 teacher 标签），不跑模拟器：
  * same-input（89-2 训练前）：“同输入异答案”。在训练 house 的记录上，把可判定存在行按新特征整行（浮点完全相同才算同输入）
    分组，HandCost（ρ_h 0.8）、RAC（ρ 0.7／0.85 × n 2／3／5）、ELU-P（rollout 配置加登记拟合量）的规则决定出现“同一输入两种
    答案”的比例必须是 0；不为 0 说明历史摘要还表达不了规则，先修摘要、不训练。
  * imitation（89-2 ①、89-3 的 P3）：同架构的头在新输入与新配方（逐字段编码；存在目标加类别权重）上能不能学会规则臂的决定。
    存在目标直接由新特征算出（HandCost：当帧覆盖 ≥0.8；RAC：当帧覆盖 ≥0.7 且此前连续计数加一 ≥3；ELU-P：初值 + 增益×匹配次数
    − 衰减×(可判定帧数+1) − 权重×(累计覆盖+当帧覆盖) < 门）；关联目标 TAF、LOW 与裁决 88 相同。报三种 epoch 的读数：选择集
    损失最低（登记的检查点规则）、最后一个 epoch、训练损失最低，通过线看后两种（选择集选点不能当作拟合能力的严格检验）。
  * coverage-events（89-3 训练前）：状态覆盖按事件计。拼接训练集（第 0 轮 ELU-P 轨迹＋本臂第 1 轮）的训练 house 上，labelled 目标
    的实体处于撤回态或休眠态的，按（趟、episode、实体、状态、该段起点＝tick − 没见帧数）去重计数；每类 ≥200 个事件、分布在
    ≥15 个训练 house 才算够，否则暂停。例如同一个休眠实体被连续 5 帧的色块指向，只算一个事件。
它们都不是方法，不产生表行；P3 的权重只作诊断。

Usage:
  python ops/vsmt/ruling89_probes.py same-input --source <pass root>:dagger_round_0:ELU-P --output <json>
  python ops/vsmt/ruling89_probes.py imitation --source <pass root>:dagger_round_0:ELU-P --target rac --output-dir <dir>
  python ops/vsmt/ruling89_probes.py coverage-events --source <root>:dagger_round_0:ELU-P --source <root>:dagger_round_1:VSMT-lean --output <json>
"""

from __future__ import annotations

import argparse
import copy
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

from vsmt import lean_arms as arms  # noqa: E402
from vsmt import lean_assignment as la  # noqa: E402

import ruling88_probes as r88p  # noqa: E402  (rule assignments, agreement, record reading)

STAGE = "vsmt.lean.ruling89.probes.v1"
HANDCOST_RHO = 0.8
RAC_GRID = ((0.7, 2), (0.7, 3), (0.7, 5), (0.85, 2), (0.85, 3), (0.85, 5))
RAC_RUN_FIELD = {0.7: "rac_run_rho_070", 0.85: "rac_run_rho_085"}
#: P3 targets: the ruling-88 configurations (TAF theta 0.7 no gate, LOW d 1.0, HandCost 0.8, RAC 0.7 / 3, ELU-P rollout)
P3_RAC = (0.7, 3)
EXISTENCE_TARGETS = ("handcost", "rac", "elup")
TARGETS = tuple(r88p.ASSOCIATION_TARGETS) + EXISTENCE_TARGETS
PASS_LINE = 0.99
COVERAGE_EVENTS_MIN, COVERAGE_HOUSES_MIN = 200, 15


# --------------------------------------------------------------------------
# rule decisions as functions of one extended existence row
# --------------------------------------------------------------------------

def row_values(features: Sequence[float], order: Sequence[str]) -> dict[str, float]:
    names = [str(n) for n in order]
    if names != list(la.EXISTENCE_FEATURES):
        raise ValueError("existence_order_is_not_the_ruling_89_order")
    return {name: float(v) for name, v in zip(names, features)}


def handcost_decision(f: Mapping[str, float], rho: float = HANDCOST_RHO) -> str:
    return "RETRACT" if f["free_space_coverage_ratio"] >= rho else "NOOP"


def rac_decision(f: Mapping[str, float], rho: float, n: int) -> str:
    """RAC at this state: this frame counts if coverage >= rho, and n consecutive counts since the last match retract."""

    if f["free_space_coverage_ratio"] < rho:
        return "NOOP"
    return "RETRACT" if f[RAC_RUN_FIELD[rho]] + 1.0 >= n else "NOOP"


def elu_p_decision(f: Mapping[str, float], values: Mapping[str, float]) -> str:
    log_odds = (values["initial_log_odds"] + values["match_gain"] * f["matches_since_birth"]
                - values["persistence_log_decay_per_tick"] * (f["eligible_frames_since_birth"] + 1.0)
                - values["free_space_weight"] * (f["free_space_coverage_sum_since_birth"] + f["free_space_coverage_ratio"]))
    return "RETRACT" if log_odds < values["retract_threshold"] else "NOOP"


def rules() -> dict[str, Any]:
    elu = r88p.elu_p_values()
    out: dict[str, Any] = {f"handcost_rho{HANDCOST_RHO}": lambda f: handcost_decision(f)}
    for rho, n in RAC_GRID:
        out[f"rac_rho{rho}_n{n}"] = (lambda f, rho=rho, n=n: rac_decision(f, rho, n))
    out["elup_rollout"] = lambda f: elu_p_decision(f, elu)
    return out


def p3_existence_decision(target: str, f: Mapping[str, float]) -> str:
    if target == "handcost":
        return handcost_decision(f)
    if target == "rac":
        return rac_decision(f, *P3_RAC)
    if target == "elup":
        return elu_p_decision(f, r88p.elu_p_values())
    raise ValueError(f"existence_target_unknown:{target}")


# --------------------------------------------------------------------------
# sources
# --------------------------------------------------------------------------

def parse_source(spec: str) -> tuple[Path, str, str]:
    root, pass_name, arm = spec.rsplit(":", 2)
    return Path(root).resolve(), pass_name, arm


def source_dirs(spec: str) -> list[Path]:
    root, pass_name, arm = parse_source(spec)
    return r88p.pass_episodes(root, pass_name, arm)


def split_of(names: Sequence[str]) -> dict[str, Any]:
    entry = r88p._entry()
    seed = int(entry.load_json(entry.S1_02A_CONTRACT)["split_freeze"]["seed"])
    return entry.rh.holdout_split(sorted(set(names)), seed=seed)


def load_groups(specs: Sequence[str]) -> tuple[dict[str, list[tuple[str, str, dict[str, Any]]]], dict[str, Any], list[dict[str, Any]]]:
    """(group -> [(source, episode, record)]), the house split (on the first source's episodes) and a per-file digest list."""

    first = source_dirs(specs[0])
    split = split_of([d.name for d in first])
    groups: dict[str, list[tuple[str, str, dict[str, Any]]]] = {"train": [], "selection": []}
    files = []
    for spec in specs:
        _, pass_name, arm = parse_source(spec)
        for d in source_dirs(spec):
            path = d / arm / "training_records.jsonl.gz"
            files.append({"source": spec, "episode": d.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            group = "train" if d.name in split["training_houses"] else "selection"
            for row in r88p.read_records(path):
                groups[group].append((f"{pass_name}:{arm}", d.name, row))
    return groups, split, files


# --------------------------------------------------------------------------
# same-input-different-answer
# --------------------------------------------------------------------------

def same_input_report(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    decide = rules()
    table: dict[str, dict[tuple[float, ...], set[str]]] = {name: {} for name in decide}
    rows = 0
    for record in records:
        order = record["existence_feature_order"]
        for row in record["existence_rows"]:
            key = tuple(float(v) for v in row["features"])
            f = row_values(row["features"], order)
            rows += 1
            for name, rule in decide.items():
                table[name].setdefault(key, set()).add(rule(f))
    out = {}
    for name, groups in table.items():
        conflicting = sum(1 for answers in groups.values() if len(answers) > 1)
        retract = sum(1 for answers in groups.values() if "RETRACT" in answers)
        out[name] = {"distinct_inputs": len(groups), "inputs_with_two_answers": conflicting,
                     "share": conflicting / len(groups) if groups else None, "inputs_with_a_retract": retract}
    return {"rows": rows, "per_rule": out, "pass": all(v["inputs_with_two_answers"] == 0 for v in out.values())}


def cmd_same_input(args: argparse.Namespace) -> int:
    groups, split, files = load_groups(args.sources)
    records = [row for _, _, row in groups["train"]]
    report = same_input_report(records)
    out = {"stage": STAGE, "check": "89-2 same input, different answer (training houses)", "sources": args.sources, "holdout": split,
           "records": len(records), **report, "files": files, "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    Path(args.output).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({"rows": report["rows"], "pass": report["pass"],
                      "conflicts": {k: v["inputs_with_two_answers"] for k, v in report["per_rule"].items()},
                      "retract_inputs": {k: v["inputs_with_a_retract"] for k, v in report["per_rule"].items()}}, indent=1))
    return 0


# --------------------------------------------------------------------------
# P3 imitation on the new inputs and recipe
# --------------------------------------------------------------------------

def imitation_record(record: Mapping[str, Any], target: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    """(imitation training record, what agreement needs, the rule decisions)."""

    stripped = {k: v for k, v in record.items() if k != "tick"}
    if target in r88p.ASSOCIATION_TARGETS:
        imitation, decisions = r88p.imitation_record(stripped, target)
        return imitation, stripped, decisions
    order = stripped["existence_feature_order"]
    decisions = {str(row["entity_id"]): p3_existence_decision(target, row_values(row["features"], order)) for row in stripped["existence_rows"]}
    stage_a = stripped["stage_a"]
    minimal = {"frame_digest": stage_a.get("frame_digest"), "rows": [], "recall": {}, "association_rows": [], "birth_rows": [],
               "association_feature_order": list(stage_a["association_feature_order"]), "birth_feature_order": list(stage_a["birth_feature_order"])}
    labels = {eid: {"status": "gone" if choice == "RETRACT" else "present"} for eid, choice in decisions.items()}
    imitation = {"stage_a": minimal, "targets": {}, "existence_rows": list(stripped["existence_rows"]),
                 "existence_feature_order": list(order), "existence_labels": labels}
    keep = {"existence_rows": stripped["existence_rows"], "existence_feature_order": order,
            "existence_labels": stripped.get("existence_labels", {})}
    return imitation, keep, decisions


# --------------------------------------------------------------------------
# where the disagreements are (ruling 93, ASTRA review: a single balanced agreement cannot say whether the errors fall on
# the moments that matter or on near-ties)
# --------------------------------------------------------------------------

#: near-tie bands, report only: a rule decision this close to its own threshold is one a small numeric difference can flip
NEAR = {"taf_cosine": 0.02, "low_distance_m": 0.05, "coverage": 1.0 / 64.0, "elup_log_odds": 0.5}


def _tally(table: dict[str, list[int]], category: str, agreed: bool) -> None:
    slot = table.setdefault(category, [0, 0])
    slot[0] += 1
    slot[1] += int(not agreed)


def association_key_events(heads: Any, keep: Mapping[str, Any], target: str, decisions: Mapping[str, str],
                           table: dict[str, list[int]]) -> None:
    """Per fragment: the rule's choice by the chosen entity's state, the teacher's re-attachment events, and near-ties."""

    from vsmt import lean_model as model

    stage_a = keep["stage_a"]
    if not stage_a["rows"]:
        return
    logits = model.LeanScorer(heads).association_and_birth_logits(stage_a)
    learned = la.solve_frame(stage_a, association_logits=logits["association_logits"], birth_logits=logits["birth_logits"])["assignment"]
    names = list(la.ASSOCIATION_FEATURES)
    cos_at, dist_at = names.index("cosine_to_descriptor_mean"), names.index("centroid_distance_m")
    rows: dict[str, list[tuple[str, list[float]]]] = {}
    for row in stage_a["association_rows"]:
        rows.setdefault(str(row["fragment_id"]), []).append((str(row["entity_id"]), row["features"]))
    for fid, column in decisions.items():
        agreed = learned[fid] == column
        pairs = rows.get(fid, [])
        if column.startswith(la.BIRTH_COLUMN_PREFIX):
            _tally(table, "rule_birth", agreed)
        else:
            features = dict(pairs)[column]
            _tally(table, f"rule_bind_{r88p.state_of(features, names)}", agreed)
        teacher = keep["targets"].get(fid) or {}
        if teacher.get("status") == "labelled":
            state = r88p.state_of(dict(pairs)[str(teacher["target"])], names)
            if state in ("dormant", "retracted"):
                _tally(table, f"teacher_reattach_{state}", agreed)
        if target == "taf" and pairs:
            best = max(float(f[cos_at]) for _, f in pairs)
            if abs(best - 0.7) <= NEAR["taf_cosine"]:
                _tally(table, "near_tie", agreed)
        if target == "low" and pairs:
            nearest = min(float(f[dist_at]) for _, f in pairs)
            if abs(nearest - 1.0) <= NEAR["low_distance_m"]:
                _tally(table, "near_tie", agreed)


def existence_key_events(heads: Any, keep: Mapping[str, Any], target: str, decisions: Mapping[str, str],
                         table: dict[str, list[int]]) -> None:
    """Per eligible row: the rule's decision crossed with the teacher's existence label, and rows near the rule's threshold."""

    from vsmt import lean_model as model

    if not keep["existence_rows"]:
        return
    order = keep["existence_feature_order"]
    logits = model.LeanScorer(heads).existence_logits(keep["existence_rows"], order)
    labels = keep.get("existence_labels") or {}
    for row in keep["existence_rows"]:
        eid = str(row["entity_id"])
        choice = decisions[eid]
        agreed = (float(logits[eid]) >= 0.0) == (choice == "RETRACT")
        label = (labels.get(eid) or {}).get("status", "unlabelled")
        _tally(table, f"rule_{choice}_teacher_{label}", agreed)
        f = row_values(row["features"], order)
        c = f["free_space_coverage_ratio"]
        if target == "handcost":
            near = abs(c - HANDCOST_RHO) <= NEAR["coverage"]
        elif target == "rac":
            rho, n = P3_RAC
            near = abs(c - rho) <= NEAR["coverage"] or (c >= rho and f[RAC_RUN_FIELD[rho]] + 1.0 in (n - 1, n))
        else:
            values = r88p.elu_p_values()
            margin = (values["initial_log_odds"] + values["match_gain"] * f["matches_since_birth"]
                      - values["persistence_log_decay_per_tick"] * (f["eligible_frames_since_birth"] + 1.0)
                      - values["free_space_weight"] * (f["free_space_coverage_sum_since_birth"] + c)) - values["retract_threshold"]
            near = abs(margin) <= NEAR["elup_log_odds"]
        if near:
            _tally(table, f"near_threshold_{choice}", agreed)


def key_events(heads: Any, built: Sequence[tuple[dict[str, Any], dict[str, Any], dict[str, str]]], target: str) -> dict[str, Any]:
    table: dict[str, list[int]] = {}
    for _, keep, decisions in built:
        if target in r88p.ASSOCIATION_TARGETS:
            association_key_events(heads, keep, target, decisions, table)
        else:
            existence_key_events(heads, keep, target, decisions, table)
    return {name: {"rows": n, "disagreements": bad, "disagreement_rate": bad / n if n else None} for name, (n, bad) in sorted(table.items())}


def revision_kwargs(args: argparse.Namespace) -> dict[str, Any]:
    """Pending ruling 91 only: the proposed schedule; absent, the ruling-89 recipe as registered."""

    if not getattr(args, "revision_91", False):
        return {}
    return {"cosine_min_learning_rate": 1e-5, "gradient_clip_norm": 1.0, "existence_prior_correction": True}


def agreement(heads: Any, built: Sequence[tuple[dict[str, Any], dict[str, Any], dict[str, str]]], target: str) -> dict[str, Any]:
    return r88p.balanced_agreement(p for _, keep, decisions in built for p in r88p.agreement_pairs(heads, keep, target, decisions))


def cmd_imitation(args: argparse.Namespace) -> int:
    import torch

    from vsmt import lean_model as model

    target = args.target
    groups, split, files = load_groups(args.sources)
    built = {g: [imitation_record(row, target) for _, _, row in rows] for g, rows in groups.items()}
    snapshots: dict[int, dict[str, Any]] = {}
    fixed_train_loss: dict[int, float | None] = {}
    assoc_only = target in r88p.ASSOCIATION_TARGETS
    # ASTRA review (2026-09-30): train_heads' train_curve averages the per-step losses while the weights move, so it is not
    # the loss of the checkpoint an epoch ends on; each epoch-end checkpoint is scored again here on the whole training set
    # with its weights fixed (the same batched loss and class weight train_heads uses), and the lowest of these picks the
    # "lowest training loss" reading
    train_batched = [model.batch_prepared(model.prepare_frame(b[0])) for b in built["train"]]
    pos_weight = None
    if not assoc_only:
        gone = sum(int(round(float(p["existence"][1].sum().item()))) for p in train_batched if p["existence"] is not None)
        total = sum(p["existence"][2] for p in train_batched if p["existence"] is not None)
        pos_weight = torch.as_tensor([(total - gone) / gone], dtype=torch.float32)

    def keep_epoch(epoch: int, heads: Any) -> None:
        snapshots[epoch] = {name: {k: v.detach().cpu().clone() for k, v in m.state_dict().items()} for name, m in heads.items()}
        fixed_train_loss[epoch] = model._mean_loss(heads, train_batched, existence_pos_weight=pos_weight, loss_fn=model.batched_loss)

    started = time.time()
    result = model.train_heads([b[0] for b in built["train"]], [b[0] for b in built["selection"]],
                               learning_rate=model.LEARNING_RATE, weight_decay=arms.WEIGHT_DECAY, epochs=int(args.epochs),
                               seed=int(arms.SEEDS[0]), assoc_only=assoc_only, device="cpu", epoch_callback=keep_epoch,
                               field_encoding=True, existence_class_weight=not assoc_only, **revision_kwargs(args))
    heads = result["heads"].eval()
    last = len(result["train_curve"]) - 1
    fixed = [fixed_train_loss.get(i) for i in range(last + 1)]
    lowest_train = min((i for i, v in enumerate(fixed) if v is not None), key=lambda i: (fixed[i], i))
    readings: dict[str, Any] = {}
    for label, epoch in (("best_selection_loss", result["best_epoch"]), ("last_epoch", last), ("lowest_training_loss", lowest_train)):
        probe = copy.deepcopy(heads)
        with torch.no_grad():
            for name, state in snapshots[epoch].items():
                probe[name].load_state_dict(state)
        probe.eval()
        if getattr(args, "read_uncorrected", False):  # ruling 93-2: P3 reads the head's own logits, not the ln w corrected ones
            probe.existence_logit_offset = 0.0
        readings[label] = {"epoch": epoch, "train": agreement(probe, built["train"], target),
                           "selection": agreement(probe, built["selection"], target)}
        if getattr(args, "key_events", False) and label in ("last_epoch", "lowest_training_loss"):
            readings[label]["key_events_train"] = key_events(probe, built["train"], target)
    passes = {label: bool(readings[label]["train"]["balanced_agreement"] is not None
                          and readings[label]["train"]["balanced_agreement"] >= PASS_LINE)
              for label in ("last_epoch", "lowest_training_loss")}
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"imitation_{target}_weights.json").write_text(json.dumps(result["weights"]), encoding="utf-8")
    out = {"stage": STAGE, "check": "P3 imitation on the ruling-89 inputs and recipe", "target": target,
           "rule": {"handcost": {"rho_h": HANDCOST_RHO}, "rac": {"rho_rac": P3_RAC[0], "n_rac": P3_RAC[1]}, "elup": r88p.elu_p_values(),
                    **{k: v[1] for k, v in r88p.ASSOCIATION_TARGETS.items()}}[target],
           "sources": args.sources, "holdout": split, "frames": {g: len(r) for g, r in built.items()},
           "recipe": {"learning_rate": model.LEARNING_RATE, "weight_decay": arms.WEIGHT_DECAY, "epochs": int(args.epochs),
                      "seed": int(arms.SEEDS[0]), "field_encoding": True, "existence_class_weight": not assoc_only,
                      **revision_kwargs(args)},
           "training": {k: result["weights"]["training"].get(k) for k in ("existence_class_weight", "updates_taken", "best_epoch")},
           "train_curve": result["train_curve"], "train_loss_fixed_weights": fixed,
           "train_curve_rule": "train_curve: mean per-step loss while the epoch updates; train_loss_fixed_weights: the epoch-end checkpoint on the whole training set, which picks lowest_training_loss",
           "validation_curve": result["validation_curve"], "diverged": result["diverged"],
           "readings": readings, "reads_uncorrected_existence_logits": bool(getattr(args, "read_uncorrected", False)),
           "pass_line": PASS_LINE, "pass_by_reading": passes,
           "pass": all(passes.values()), "weights_sha256": result["weights"]["sha256"], "files": files,
           "wall_seconds": round(time.time() - started, 1), "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (out_dir / f"imitation_{target}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({"target": target, **{k: v["train"]["balanced_agreement"] for k, v in readings.items()}, "pass": out["pass"]}, indent=1))
    return 0 if not result["diverged"] else 1


# --------------------------------------------------------------------------
# state coverage in events
# --------------------------------------------------------------------------

def coverage_events(groups: Mapping[str, Sequence[tuple[str, str, Mapping[str, Any]]]]) -> dict[str, Any]:
    names = list(la.ASSOCIATION_FEATURES)
    ticks_at = names.index("ticks_since_last_seen")
    out: dict[str, Any] = {}
    for group, rows in groups.items():
        events: dict[str, set[tuple[str, str, str, int]]] = {"retracted": set(), "dormant": set()}
        target_rows = {"retracted": 0, "dormant": 0}
        for source, episode, record in rows:
            tick = int(record["tick"])
            stage_a = record["stage_a"]
            by_pair = {(str(r["fragment_id"]), str(r["entity_id"])): r["features"] for r in stage_a["association_rows"]}
            for fragment_id, target in record["targets"].items():
                if target["status"] != "labelled":
                    continue
                features = by_pair[(str(fragment_id), str(target["target"]))]
                state = r88p.state_of(features, names)
                if state not in events:
                    continue
                target_rows[state] += 1
                start = tick - int(round(float(features[ticks_at])))
                events[state].add((source, episode, str(target["target"]), start))
        out[group] = {state: {"events": len(keys), "houses": len({k[1] for k in keys}), "labelled_target_rows": target_rows[state]}
                      for state, keys in events.items()}
    train = out["train"]
    out["pass"] = all(train[s]["events"] >= COVERAGE_EVENTS_MIN and train[s]["houses"] >= COVERAGE_HOUSES_MIN for s in ("retracted", "dormant"))
    out["lines"] = {"events_per_state": COVERAGE_EVENTS_MIN, "training_houses_per_state": COVERAGE_HOUSES_MIN}
    return out


def cmd_coverage_events(args: argparse.Namespace) -> int:
    groups, split, files = load_groups(args.sources)
    report = coverage_events(groups)
    out = {"stage": STAGE, "check": "89-3 state coverage in events (training houses)", "sources": args.sources, "holdout": split,
           **report, "files": files, "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    Path(args.output).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({"train": report["train"], "pass": report["pass"]}, indent=1))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("same-input")
    s.add_argument("--source", dest="sources", action="append", required=True, help="<pass root>:<pass>:<arm>")
    s.add_argument("--output", required=True)
    s.set_defaults(func=cmd_same_input)
    i = sub.add_parser("imitation")
    i.add_argument("--source", dest="sources", action="append", required=True)
    i.add_argument("--target", required=True, choices=TARGETS)
    i.add_argument("--output-dir", required=True)
    i.add_argument("--epochs", type=int, default=20)
    i.add_argument("--revision-91", action="store_true", help="pending ruling 91 only: cosine-decayed rate and gradient clipping")
    i.add_argument("--read-uncorrected", action="store_true", help="ruling 93-2: agreement on the uncorrected existence logits")
    i.add_argument("--key-events", action="store_true", help="ruling 93: disagreements by rule choice x entity state / teacher label and near-ties")
    i.set_defaults(func=cmd_imitation)
    c = sub.add_parser("coverage-events")
    c.add_argument("--source", dest="sources", action="append", required=True)
    c.add_argument("--output", required=True)
    c.set_defaults(func=cmd_coverage_events)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
