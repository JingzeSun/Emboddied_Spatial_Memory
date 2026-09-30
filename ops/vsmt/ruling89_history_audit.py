#!/usr/bin/env python3
"""Ruling 89-2 history summaries against independent rule executors (the check the same-input table could not be).

白话：LOG-288 里“同输入异答案 = 0”是先由特征行算出规则答案、再看同一行有没有两个答案——确定性函数必然为 0，即使摘要记错
也会通过（ASTRA 复核，2026-09-30）。这里换成独立核对：让 runner 真的跑 ELU-P（rollout 配置加登记拟合量）与 RAC（ρ 0.7／0.85 ×
n 2／3／5）这些臂，它们各自维护完整历史（ELU-P 的对数几率、RAC 的连续负证据计数，都与摘要分开实现）；每个可判定行上，比较
  * 臂的真实决定 与 “只由该行（含 5 个历史量）算出的规则决定”；
  * ELU-P：臂在本帧更新后的对数几率 与 初值 + 增益×匹配次数 − 衰减×(可判定帧数+1) − 权重×(累计覆盖+当帧覆盖)；
  * RAC：臂在本帧之前的计数 与 该 ρ 的连续计数摘要。
另外同时维护一份故意写错的影子摘要（匹配时不清零 RAC 计数、不计匹配次数），用同样的规则算决定；它必须和臂的真实决定出现
不一致，说明这个核对确实检得出摘要错误。输入只有公开 cache 与 runner，不读私有数据、不产生训练记录。

Usage:
  python ops/vsmt/ruling89_history_audit.py run --cache-root <c> --episode-root <e> --episode-id <id> --arm RAC --config '<json>'
      --descriptor reid_projection:vitb14 --weights <reid> --mask-source simulator_instance_masks --output <json>
  python ops/vsmt/ruling89_history_audit.py merge --input-dir <dir> --output <json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
for item in (ROOT / "src", HERE.parent):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from vsmt import lean_assignment as la  # noqa: E402
from vsmt import lean_runner as lr  # noqa: E402

import ruling89_probes as probes  # noqa: E402

STAGE = "vsmt.lean.ruling89.history_audit.v1"
LOG_ODDS_TOLERANCE = 1e-6


def mutated_update(history: Mapping[str, Mapping[str, float]], eligible: Sequence[Mapping[str, Any]], order: Sequence[str],
                   matched: Sequence[str]) -> dict[str, dict[str, float]]:
    """The negative control: the summary update with the match rules removed (no RAC reset, no match count)."""

    return lr.update_existence_history(history, eligible, order, [])


def rule_decision(arm: str, config: Mapping[str, Any], f: Mapping[str, float]) -> str:
    if arm == "ELU-P":
        return probes.elu_p_decision(f, config)
    return probes.rac_decision(f, float(config["rho_rac"]), int(config["n_rac"]))


def elu_p_log_odds(config: Mapping[str, Any], f: Mapping[str, float]) -> float:
    return (config["initial_log_odds"] + config["match_gain"] * f["matches_since_birth"]
            - config["persistence_log_decay_per_tick"] * (f["eligible_frames_since_birth"] + 1.0)
            - config["free_space_weight"] * (f["free_space_coverage_sum_since_birth"] + f["free_space_coverage_ratio"]))


class Audit:
    """Compares every eligible row of one run with the arm's own state and decisions."""

    def __init__(self, arm: str, config: Mapping[str, Any]) -> None:
        if arm not in ("ELU-P", "RAC"):
            raise ValueError("history_audit_arm_must_be_ELU-P_or_RAC")
        self.arm, self.config = arm, dict(config)
        self.shadow: dict[str, dict[str, float]] = {}
        self.counts = {"frames": 0, "illegal_frames_skipped": 0, "rows": 0, "retract_rows": 0, "decision_mismatches": 0,
                       "state_mismatches": 0, "state_compared": 0, "mutated_decision_mismatches": 0,
                       "mutated_state_mismatches": 0}
        self.max_log_odds_error = 0.0
        self.examples: list[dict[str, Any]] = []

    def observe(self, before: Mapping[str, Any], step: Mapping[str, Any]) -> None:
        receipt = step["receipt"]
        stage_b = step["stage_b"]
        order = list(stage_b["existence_feature_order"])
        rows = {str(r["entity_id"]): r for r in stage_b["existence_rows"]}
        eligible = [rows[eid] for eid in receipt["existence"]["candidates"]]
        decisions = receipt["existence"]["decisions"]
        matched = sorted(str(c) for c in receipt["assignment"].values() if not str(c).startswith(la.BIRTH_COLUMN_PREFIX))
        self.counts["frames"] += 1
        shadow_before = self.shadow
        if receipt["illegal_program"] is None:
            names = list(order)
            for row in eligible:
                eid = str(row["entity_id"])
                f = probes.row_values(row["features"], order)
                expected = rule_decision(self.arm, self.config, f)
                actual = decisions[eid]
                self.counts["rows"] += 1
                self.counts["retract_rows"] += int(actual == "RETRACT")
                if expected != actual:
                    self.counts["decision_mismatches"] += 1
                    if len(self.examples) < 10:
                        self.examples.append({"tick": receipt["tick"], "kind": "decision", "expected": expected, "actual": actual})
                if self.arm == "ELU-P":
                    after = step["state"]["arm_state"].get("log_odds", {}).get(eid)
                    if after is not None:
                        self.counts["state_compared"] += 1
                        error = abs(float(after) - elu_p_log_odds(self.config, f))
                        self.max_log_odds_error = max(self.max_log_odds_error, error)
                        self.counts["state_mismatches"] += int(error > LOG_ODDS_TOLERANCE)
                else:
                    counter = float(before["arm_state"].get("negative_renders", {}).get(eid, 0))
                    field = probes.RAC_RUN_FIELD[float(self.config["rho_rac"])]
                    self.counts["state_compared"] += 1
                    if counter != f[field]:
                        self.counts["state_mismatches"] += 1
                        if len(self.examples) < 10:
                            self.examples.append({"tick": receipt["tick"], "kind": "rac_counter", "arm": counter, "summary": f[field]})
                # the negative control: the same rule on the deliberately wrong summary
                wrong = dict(f)
                for name, value in (shadow_before.get(eid) or {n: 0.0 for n in la.EXISTENCE_HISTORY_FEATURES}).items():
                    wrong[name] = float(value)
                self.counts["mutated_decision_mismatches"] += int(rule_decision(self.arm, self.config, wrong) != actual)
                if self.arm == "ELU-P":
                    after = step["state"]["arm_state"].get("log_odds", {}).get(eid)
                    wrong_state = after is not None and abs(float(after) - elu_p_log_odds(self.config, wrong)) > LOG_ODDS_TOLERANCE
                else:
                    field = probes.RAC_RUN_FIELD[float(self.config["rho_rac"])]
                    wrong_state = float(before["arm_state"].get("negative_renders", {}).get(eid, 0)) != wrong[field]
                self.counts["mutated_state_mismatches"] += int(wrong_state)
            self.shadow = mutated_update(shadow_before, eligible, order, matched)
            live = {str(e["entity_id"]) for e in step["state"]["memory"]["entities"]}
            self.shadow = {k: v for k, v in self.shadow.items() if k in live}
        else:
            self.counts["illegal_frames_skipped"] += 1

    def report(self) -> dict[str, Any]:
        c = self.counts
        return {**c, "max_log_odds_error": self.max_log_odds_error, "examples": self.examples,
                "faithful": c["decision_mismatches"] == 0 and c["state_mismatches"] == 0,
                "control_detected": c["mutated_decision_mismatches"] + c["mutated_state_mismatches"] > 0}


def cmd_run(args: argparse.Namespace) -> int:
    import lean_s2_04_evaluate_episode as s2_04

    config = json.loads(args.config)
    lr.validate_arm_config(args.arm, config)
    policy, missing = s2_04.gather_teacher_policy()
    if missing:
        print(f"refused: policy values still null: {missing}", file=sys.stderr)
        return 2
    projector = None
    if args.descriptor == la.SELECTED_DESCRIPTOR:
        payload = s2_04.load_json(Path(args.weights))
        projector = lr.descriptor_projector(payload, expected_sha256=la.SELECTED_REID_WEIGHTS_SHA256, device="cpu")
    cache_dir = Path(args.cache_root).resolve() / args.episode_id
    episode_root = Path(args.episode_root).resolve()
    _, frame_paths = s2_04.verify_cache_episode(cache_dir, s2_04.diag.registered_descriptor_asset_sha256s(), mask_source=args.mask_source)
    if args.frames is not None:
        frame_paths = frame_paths[: int(args.frames)]
    depth_view = s2_04.episode_depth_reader(episode_root, cache_dir)

    def frames():
        for index, path in enumerate(frame_paths):
            frame = s2_04.diag.cache_runner.load_cache_frame(path)
            frame[lr.PUBLIC_DEPTH_VIEW_KEY] = depth_view(index, frame)
            yield frame

    audit = Audit(args.arm, config)
    started = time.time()
    state = lr.initial_state(episode_id=args.episode_id, arm=args.arm)
    for frame in frames():
        step = lr.run_frame(state, frame, arm=args.arm, config=config, policy=policy["runner"], descriptor=args.descriptor,
                            projector=projector)
        audit.observe(state, step)
        state = step["state"]
    out = {"stage": STAGE, "episode_id": args.episode_id, "arm": args.arm, "config": config, "frames": len(frame_paths),
           "recall_global_count": la.RECALL_GLOBAL_COUNT, **audit.report(), "wall_seconds": round(time.time() - started, 1),
           "code_commit": s2_04._git("rev-parse", "HEAD"), "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("episode_id", "arm", "rows", "retract_rows", "decision_mismatches", "state_mismatches",
                                          "mutated_decision_mismatches", "mutated_state_mismatches", "max_log_odds_error",
                                          "wall_seconds")}))
    return 0


def cmd_merge(args: argparse.Namespace) -> int:
    groups: dict[str, dict[str, Any]] = {}
    for path in sorted(Path(args.input_dir).glob("*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        key = d["arm"] if d["arm"] == "ELU-P" else f"RAC_rho{d['config']['rho_rac']}_n{d['config']['n_rac']}"
        g = groups.setdefault(key, {"episodes": 0, "rows": 0, "retract_rows": 0, "decision_mismatches": 0, "state_mismatches": 0,
                                    "state_compared": 0, "mutated_decision_mismatches": 0, "mutated_state_mismatches": 0,
                                    "illegal_frames_skipped": 0,
                                    "max_log_odds_error": 0.0})
        g["episodes"] += 1
        for name in ("rows", "retract_rows", "decision_mismatches", "state_mismatches", "state_compared", "mutated_decision_mismatches",
                     "mutated_state_mismatches", "illegal_frames_skipped"):
            g[name] += int(d[name])
        g["max_log_odds_error"] = max(g["max_log_odds_error"], float(d["max_log_odds_error"]))
    for g in groups.values():
        g["faithful"] = g["decision_mismatches"] == 0 and g["state_mismatches"] == 0
        g["control_detected"] = g["mutated_decision_mismatches"] + g["mutated_state_mismatches"] > 0
    out = {"stage": STAGE, "check": "89-2 history summaries against independent ELU-P / RAC executors", "groups": groups,
           "pass": bool(groups) and all(g["faithful"] and g["control_detected"] for g in groups.values()),
           "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    Path(args.output).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run")
    for name in ("--cache-root", "--episode-root", "--episode-id", "--arm", "--config", "--descriptor", "--mask-source", "--output"):
        r.add_argument(name, required=True)
    r.add_argument("--weights", default=None)
    r.add_argument("--frames", type=int, default=None)
    r.set_defaults(func=cmd_run)
    m = sub.add_parser("merge")
    m.add_argument("--input-dir", required=True)
    m.add_argument("--output", required=True)
    m.set_defaults(func=cmd_merge)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
