#!/usr/bin/env python3
"""Ruling 88-2 (ii): three minute-scale mechanism checks on the sealed S2-05 training records (read-only diagnostics).

Step 0 of ruling 88: three cheap checks that read only sealed training records (public features plus teacher labels); no
simulator, no rule changed.
  * coverage (P1, state coverage): in the round-0 (ELU-P) and round-1 (VSMT-lean) records, the number of association rows by
    candidate state (active / dormant / retracted), of labelled targets by the target entity's state and of existence rows
    by label and state. Example: if round 1 has only a few dozen labelled targets in the retracted state, the main-table heads have
    not learned to recover from it.
  * sensitivity (P2, trained-head sensitivity): the logit change of a trained head under a perturbation of its key cue
    (association: both cosine features + 0.1; existence: free-space coverage 0 -> 1; birth: highest cosine + 0.1), binned by
    ticks since last seen, observation count and pixel count. Example: a candidate unseen for 300 frames whose logit barely
    moves with the cosine shows that the row LayerNorm (pre-ruling-89 recipe) flattened the cosine and training did not
    restore it.
  * imitation (P3, imitation sufficiency): whether a head of the same architecture learns a rule arm's decisions on the same
    rows. The joint assignments of TAF and LOW and the existence decisions of HandCost read only this frame's features
    (positive controls); the existence decisions of RAC and ELU-P depend on history and are replayed along the records entity
    by entity (whether and how often an entity was matched between two candidacies is derived from its last-seen frame and
    observation count; counts after deduplication merges are approximated by the recorded values). Output: class-balanced
    agreement on the training and selection houses.
None of these is a method or produces anything but readings and diagnostic weights (P3 weights enter no run). The reading
rules are frozen in DECISIONS ruling 88-2 and applied by ruling88_analysis.py.

Reused outside S2-R through ruling89_probes.py: `_entry`, `read_records` and `state_of` (the record reader and state decoder
behind ruling89_train.py, the S2-06 training entry, and the S3-03 coverage reading); `_entry` also by s3_02_bench.py.

Usage:
  python ops/vsmt/ruling88_probes.py coverage --output-root <pass root> --pass dagger_round_0:ELU-P --pass dagger_round_1:VSMT-lean --output <json>
  python ops/vsmt/ruling88_probes.py sensitivity --output-root <pass root> --weights <weights.json> --label A7 --output <json>
  python ops/vsmt/ruling88_probes.py imitation --output-root <pass root> --target rac --output-dir <dir> [--epochs 20]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
for item in (ROOT / "src", HERE.parent):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from vsmt import lean_arms as arms  # noqa: E402
from vsmt import lean_assignment as la  # noqa: E402

STAGE = "vsmt.lean.ruling88.probes.v1"
OWN_PASS, OWN_ARM = "dagger_round_1", "VSMT-lean"
STATES = ("active", "dormant", "retracted")
TICK_BINS = ((1, "1"), (10, "2-10"), (100, "11-100"), (500, "101-500"), (None, ">500"))
OBSERVATION_BINS = ((10, "1-10"), (100, "11-100"), (1000, "101-1000"), (None, ">1000"))
PIXEL_BINS = ((500, "<500"), (2000, "500-2000"), (10000, "2000-10000"), (None, ">10000"))
COSINE_STEP = 0.1
#: Ruling 88-2 (ii) P3: the rule targets.  The first three read only this frame's features (positive controls); RAC and
#: ELU-P carry per-entity history.  Values are the development configurations (lean_development) and a HandCost grid member.
ASSOCIATION_TARGETS = {"taf": ("TAF", {"theta_a": 0.7, "d_a": None}), "low": ("LOW", {"d_low": 1.0})}
EXISTENCE_TARGETS = ("handcost", "rac", "elup")
HANDCOST_RHO = 0.8
RAC_RHO, RAC_N = 0.7, 3
TARGETS = tuple(ASSOCIATION_TARGETS) + EXISTENCE_TARGETS
POSITIVE_CONTROLS = ("taf", "low", "handcost")


def _bin(value: float, bins: Sequence[tuple[float | None, str]]) -> str:
    for upper, label in bins:
        if upper is None or value <= upper:
            return label
    raise AssertionError("unreachable")


def state_of(features: Sequence[float], order: Sequence[str]) -> str:
    """The entity state a sealed feature row encodes in its one-hot."""

    names = [str(item) for item in order]
    hot = [s for s in STATES if float(features[names.index(f"state_is_{s}")]) == 1.0]
    if len(hot) != 1:
        raise ValueError("state_one_hot_invalid")
    return hot[0]


def elu_p_values() -> dict[str, float]:
    fitted = {path.split(".")[-1]: float(value) for path, value, _ in arms.FROZEN_VALUES_BY_RULING
              if path.startswith("arms.ELU-P.fitted.")}
    rollout = dict(arms.ROLLOUT_CONFIG)
    return {**fitted, "free_space_weight": float(rollout["free_space_weight"]), "retract_threshold": float(rollout["retract_threshold"])}


# --------------------------------------------------------------------------
# P1 coverage
# --------------------------------------------------------------------------

def coverage_counts(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Association rows by candidate state, labelled targets by target state, existence rows by label and state."""

    rows_by_state = {s: 0 for s in STATES}
    targets_by_state = {**{s: 0 for s in STATES}, "birth": 0}
    statuses: dict[str, int] = {}
    existence_by_label: dict[str, int] = {}
    existence_by_state: dict[str, int] = {}
    frames = 0
    for record in records:
        frames += 1
        stage_a = record["stage_a"]
        order = stage_a["association_feature_order"]
        state_by_pair = {}
        for row in stage_a["association_rows"]:
            state = state_of(row["features"], order)
            rows_by_state[state] += 1
            state_by_pair[(str(row["fragment_id"]), str(row["entity_id"]))] = state
        for fragment_id, target in record["targets"].items():
            statuses[target["status"]] = statuses.get(target["status"], 0) + 1
            if target["status"] == "birth":
                targets_by_state["birth"] += 1
            elif target["status"] == "labelled":
                targets_by_state[state_by_pair[(str(fragment_id), str(target["target"]))]] += 1
        for row in record["existence_rows"]:
            state = state_of(row["features"], record["existence_feature_order"])
            existence_by_state[state] = existence_by_state.get(state, 0) + 1
            label = (record["existence_labels"].get(str(row["entity_id"])) or {}).get("status", "unlabelled")
            existence_by_label[label] = existence_by_label.get(label, 0) + 1
    return {"frames": frames, "association_rows_by_candidate_state": rows_by_state,
            "labelled_targets_by_target_state": targets_by_state, "association_target_statuses": dict(sorted(statuses.items())),
            "existence_rows_by_label": dict(sorted(existence_by_label.items())), "existence_rows_by_state": dict(sorted(existence_by_state.items()))}


# --------------------------------------------------------------------------
# P2 sensitivity of trained heads
# --------------------------------------------------------------------------

class SensitivityTally:
    """|delta logit| per bin for the three perturbations; ``add`` takes one record."""

    def __init__(self, heads: Any) -> None:
        self.heads = heads
        self.association: dict[str, list[float]] = {}
        self.association_by_state: dict[str, list[float]] = {}
        self.existence: dict[str, list[float]] = {}
        self.birth: dict[str, list[float]] = {}

    @staticmethod
    def _logits(head: Any, rows: list[list[float]]) -> list[float]:
        import numpy as np
        import torch

        if not rows:
            return []
        with torch.no_grad():
            out = head(torch.as_tensor(np.asarray(rows, dtype=np.float32)))
        return [float(v) for v in out.reshape(-1).cpu().numpy()]

    def add(self, record: Mapping[str, Any]) -> None:
        stage_a = record["stage_a"]
        order = list(stage_a["association_feature_order"])
        cosines = [order.index("cosine_to_descriptor_mean"), order.index("cosine_to_best_view_descriptor")]
        ticks_at = order.index("ticks_since_last_seen")
        base, bumped, labels = [], [], []
        for row in stage_a["association_rows"]:
            features = [float(v) for v in row["features"]]
            moved = list(features)
            for index in cosines:
                moved[index] = min(1.0, moved[index] + COSINE_STEP)
            base.append(features)
            bumped.append(moved)
            labels.append((_bin(features[ticks_at], TICK_BINS), state_of(features, order)))
        for (tick_bin, state), a, b in zip(labels, self._logits(self.heads["association"], base),
                                           self._logits(self.heads["association"], bumped), strict=True):
            self.association.setdefault(tick_bin, []).append(abs(b - a))
            self.association_by_state.setdefault(f"{state}|{tick_bin}", []).append(abs(b - a))
        if "existence" in self.heads and record["existence_rows"]:
            e_order = list(record["existence_feature_order"])
            coverage_at, obs_at = e_order.index("free_space_coverage_ratio"), e_order.index("observation_count")
            zero, one, bins = [], [], []
            for row in record["existence_rows"]:
                features = [float(v) for v in row["features"]]
                low, high = list(features), list(features)
                low[coverage_at], high[coverage_at] = 0.0, 1.0
                zero.append(low)
                one.append(high)
                bins.append(_bin(features[obs_at], OBSERVATION_BINS))
            for label, a, b in zip(bins, self._logits(self.heads["existence"], zero), self._logits(self.heads["existence"], one), strict=True):
                self.existence.setdefault(label, []).append(abs(b - a))
        b_order = list(stage_a["birth_feature_order"])
        best_at, pixels_at = b_order.index("best_cosine_to_any_entity"), b_order.index("pixel_count")
        base, bumped, bins = [], [], []
        for row in stage_a["birth_rows"]:
            features = [float(v) for v in row["features"]]
            moved = list(features)
            moved[best_at] = min(1.0, moved[best_at] + COSINE_STEP)
            base.append(features)
            bumped.append(moved)
            bins.append(_bin(features[pixels_at], PIXEL_BINS))
        for label, a, b in zip(bins, self._logits(self.heads["birth"], base), self._logits(self.heads["birth"], bumped), strict=True):
            self.birth.setdefault(label, []).append(abs(b - a))

    @staticmethod
    def _summary(table: Mapping[str, list[float]], order: Sequence[str]) -> dict[str, Any]:
        out = {}
        for label in order:
            values = sorted(table.get(label, []))
            out[label] = {"rows": len(values), "median_abs_delta": statistics.median(values) if values else None,
                          "p25": values[len(values) // 4] if values else None, "p75": values[(3 * len(values)) // 4] if values else None}
        return out

    def report(self) -> dict[str, Any]:
        def pooled_median(table: Mapping[str, list[float]], labels: Sequence[str]) -> float | None:
            values = [v for label in labels for v in table.get(label, [])]
            return statistics.median(values) if values else None

        a_ref, a_far = pooled_median(self.association, ["1"]), pooled_median(self.association, ["101-500", ">500"])
        e_ref, e_far = pooled_median(self.existence, ["1-10"]), pooled_median(self.existence, ["101-1000", ">1000"])
        return {
            "association_by_ticks_since_last_seen": self._summary(self.association, [label for _, label in TICK_BINS]),
            "association_by_state_and_ticks": self._summary(self.association_by_state, sorted(self.association_by_state)),
            "existence_by_observation_count": self._summary(self.existence, [label for _, label in OBSERVATION_BINS]),
            "birth_by_pixel_count": self._summary(self.birth, [label for _, label in PIXEL_BINS]),
            "ratios": {
                "association_ticks_over_100_vs_1": (a_far / a_ref) if a_ref and a_far is not None else None,
                "existence_observations_over_100_vs_1_to_10": (e_far / e_ref) if e_ref and e_far is not None else None,
            },
            "perturbations": {"association": f"both cosine features +{COSINE_STEP} (capped at 1)",
                              "existence": "free_space_coverage_ratio 0 -> 1", "birth": f"best_cosine_to_any_entity +{COSINE_STEP} (capped at 1)"},
        }


# --------------------------------------------------------------------------
# P3 imitation sufficiency
# --------------------------------------------------------------------------

def rule_assignment(record: Mapping[str, Any], target: str) -> dict[str, str]:
    """The rule arm's joint assignment on the sealed stage-A rows (TAF or LOW at the development configuration)."""

    from vsmt import lean_runner as lr

    arm, config = ASSOCIATION_TARGETS[target]
    stage_a = record["stage_a"]
    logits = lr._association_logits(arm, lr.validate_arm_config(arm, config), stage_a, None)
    solved = la.solve_frame(stage_a, association_logits=logits["association_logits"], birth_logits=logits["birth_logits"])
    arms.assert_no_sentinel_chosen(solved["assignment"], logits["association_logits"])
    return {str(k): str(v) for k, v in solved["assignment"].items()}


class ExistenceReplay:
    """A rule's existence decisions replayed along one episode's records, entity by entity (history rules keep state)."""

    def __init__(self, target: str, order: Sequence[str]) -> None:
        if target not in EXISTENCE_TARGETS:
            raise ValueError(f"existence_target_unknown:{target}")
        self.target = target
        names = [str(item) for item in order]
        self.coverage_at = names.index("free_space_coverage_ratio")
        self.observations_at = names.index("observation_count")
        self.ticks_at = names.index("ticks_since_last_seen")
        self.elu = elu_p_values()
        self.state: dict[str, dict[str, float]] = {}

    def decide(self, tick: int, rows: Sequence[Mapping[str, Any]]) -> dict[str, str]:
        decisions: dict[str, str] = {}
        for row in rows:
            entity_id = str(row["entity_id"])
            features = row["features"]
            coverage = float(features[self.coverage_at])
            if self.target == "handcost":
                decisions[entity_id] = "RETRACT" if coverage >= HANDCOST_RHO else "NOOP"
                continue
            last_seen = int(tick) - int(round(float(features[self.ticks_at])))
            observations = float(features[self.observations_at])
            if self.target == "rac":
                # rac_existence / rac_observe_matches: consecutive eligible frames with coverage >= rho; a match in between resets
                memo = self.state.setdefault(entity_id, {"count": 0.0, "last_seen": float(last_seen)})
                if last_seen > memo["last_seen"]:
                    memo["count"] = 0.0
                memo["last_seen"] = float(last_seen)
                memo["count"] = memo["count"] + 1.0 if coverage >= RAC_RHO else 0.0
                if memo["count"] >= RAC_N:
                    decisions[entity_id] = "RETRACT"
                    memo["count"] = 0.0
                else:
                    decisions[entity_id] = "NOOP"
                continue
            # elu_p_existence / elu_p_observe_matches: log-odds = initial + gain * matches - sum over eligible frames of
            # (decay + weight * coverage); matches since birth = observation_count - 1
            memo = self.state.setdefault(entity_id, {"negative": 0.0})
            memo["negative"] += self.elu["persistence_log_decay_per_tick"] + self.elu["free_space_weight"] * coverage
            log_odds = self.elu["initial_log_odds"] + self.elu["match_gain"] * (observations - 1.0) - memo["negative"]
            decisions[entity_id] = "RETRACT" if log_odds < self.elu["retract_threshold"] else "NOOP"
        return decisions


def imitation_record(record: Mapping[str, Any], target: str, *, replay: ExistenceReplay | None = None,
                     tick: int | None = None) -> tuple[dict[str, Any], dict[str, str]]:
    """One training record whose labels are the rule's decisions, and those decisions (fragment or entity -> choice)."""

    stage_a = record["stage_a"]
    if target in ASSOCIATION_TARGETS:
        assignment = rule_assignment(record, target)
        targets = {fid: {"status": "birth" if column.startswith(la.BIRTH_COLUMN_PREFIX) else "labelled", "target": column}
                   for fid, column in assignment.items()}
        return ({"stage_a": stage_a, "targets": targets, "existence_rows": [], "existence_feature_order": list(record["existence_feature_order"]),
                 "existence_labels": {}}, assignment)
    decisions = replay.decide(int(tick), record["existence_rows"]) if replay is not None else {}
    minimal = {"frame_digest": stage_a.get("frame_digest"), "rows": [], "recall": {}, "association_rows": [], "birth_rows": [],
               "association_feature_order": list(stage_a["association_feature_order"]), "birth_feature_order": list(stage_a["birth_feature_order"])}
    labels = {eid: {"status": "gone" if choice == "RETRACT" else "present"} for eid, choice in decisions.items()}
    return ({"stage_a": minimal, "targets": {}, "existence_rows": list(record["existence_rows"]),
             "existence_feature_order": list(record["existence_feature_order"]), "existence_labels": labels}, decisions)


def balanced_agreement(pairs: Iterable[tuple[str, str]]) -> dict[str, Any]:
    """(rule class, agreed?) pairs -> per-class agreement and their mean over the classes present."""

    counts: dict[str, list[int]] = {}
    for rule_class, agreed in pairs:
        slot = counts.setdefault(rule_class, [0, 0])
        slot[0] += 1
        slot[1] += int(agreed == "yes")
    per_class = {name: {"rows": n, "agreement": k / n} for name, (n, k) in sorted(counts.items())}
    return {"per_class": per_class, "balanced_agreement": statistics.fmean(v["agreement"] for v in per_class.values()) if per_class else None}


def agreement_pairs(heads: Any, record: Mapping[str, Any], target: str, decisions: Mapping[str, str]) -> list[tuple[str, str]]:
    """(rule class, agreed) per fragment (association targets) or per existence row (existence targets)."""

    from vsmt import lean_model as model

    if target in ASSOCIATION_TARGETS:
        stage_a = record["stage_a"]
        if not stage_a["rows"]:
            return []
        logits = model.LeanScorer(heads).association_and_birth_logits(stage_a)
        learned = la.solve_frame(stage_a, association_logits=logits["association_logits"], birth_logits=logits["birth_logits"])["assignment"]
        return [("birth" if column.startswith(la.BIRTH_COLUMN_PREFIX) else "bind", "yes" if learned[fid] == column else "no")
                for fid, column in decisions.items()]
    if not record["existence_rows"]:
        return []
    logits = model.LeanScorer(heads).existence_logits(record["existence_rows"], record["existence_feature_order"])
    # sigmoid(logit) >= 0.5 exactly when logit >= 0; comparing the logit avoids exp overflow on large negative logits (a trained
    # imitation head reached them; the first step-0 run crashed on it after training)
    return [(choice, "yes" if (float(logits[eid]) >= 0.0) == (choice == "RETRACT") else "no")
            for eid, choice in decisions.items()]


# --------------------------------------------------------------------------
# data and commands
# --------------------------------------------------------------------------

def _entry():
    import lean_s2_05_development as entry  # the registered entry's record reader, episode listing and split

    return entry


def pass_episodes(output_root: Path, pass_name: str, arm: str) -> list[Path]:
    entry = _entry()
    return entry.episode_dirs(output_root / pass_name, arm)


def holdout(dirs: Sequence[Path]) -> dict[str, Any]:
    entry = _entry()
    seed = int(entry.load_json(entry.S1_02A_CONTRACT)["split_freeze"]["seed"])
    return entry.rh.holdout_split([d.name for d in dirs], seed=seed)


def read_records(path: Path) -> list[dict[str, Any]]:
    return _entry().read_jsonl_gz(path)


def cmd_coverage(args: argparse.Namespace) -> int:
    root = Path(args.output_root).resolve()
    out: dict[str, Any] = {"stage": STAGE, "probe": "P1 state coverage", "passes": {}}
    for spec in args.passes:
        pass_name, arm = spec.split(":")
        dirs = pass_episodes(root, pass_name, arm)
        records = (row for d in dirs for row in read_records(d / arm / "training_records.jsonl.gz"))
        out["passes"][spec] = {"episodes": len(dirs), **coverage_counts(records)}
    out["script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    Path(args.output).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out["passes"], indent=1))
    return 0


def cmd_sensitivity(args: argparse.Namespace) -> int:
    from vsmt import lean_model as model

    root = Path(args.output_root).resolve()
    payload = json.loads(Path(args.weights).read_text(encoding="utf-8"))
    heads = model.load_heads(payload).eval()
    dirs = pass_episodes(root, OWN_PASS, OWN_ARM)
    split = holdout(dirs)
    tally = SensitivityTally(heads)
    used = [d for d in dirs if d.name in split["selection_houses"]]
    for d in used:
        for record in read_records(d / OWN_ARM / "training_records.jsonl.gz"):
            tally.add(record)
    out = {"stage": STAGE, "probe": "P2 trained-head sensitivity", "label": args.label, "weights_sha256": payload.get("sha256"),
           "records": f"{OWN_PASS}/{OWN_ARM}, the {len(used)} selection houses", "houses": [d.name for d in used], **tally.report(),
           "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    Path(args.output).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({"label": args.label, **out["ratios"]}, indent=1))
    return 0


def cmd_imitation(args: argparse.Namespace) -> int:
    from vsmt import lean_model as model

    target = args.target
    root = Path(args.output_root).resolve()
    dirs = pass_episodes(root, OWN_PASS, OWN_ARM)
    split = holdout(dirs)
    built: dict[str, list[tuple[dict[str, Any], dict[str, Any], dict[str, str]]]] = {"train": [], "selection": []}
    for d in dirs:
        group = "train" if d.name in split["training_houses"] else "selection"
        records = read_records(d / OWN_ARM / "training_records.jsonl.gz")
        replay = ExistenceReplay(target, records[0]["existence_feature_order"]) if target in EXISTENCE_TARGETS and records else None
        for row in records:
            record = {k: v for k, v in row.items() if k != "tick"}
            imitation, decisions = imitation_record(record, target, replay=replay, tick=int(row["tick"]))
            keep = record if target in ASSOCIATION_TARGETS else {"existence_rows": record["existence_rows"],
                                                                 "existence_feature_order": record["existence_feature_order"]}
            built[group].append((imitation, keep, decisions))
    started = time.time()
    result = model.train_heads([b[0] for b in built["train"]], [b[0] for b in built["selection"]],
                               learning_rate=model.LEARNING_RATE, weight_decay=arms.WEIGHT_DECAY, epochs=int(args.epochs),
                               seed=int(arms.SEEDS[0]), assoc_only=target in ASSOCIATION_TARGETS, device="cpu")
    heads = result["heads"].eval()
    agreement = {group: balanced_agreement(p for imitation, keep, decisions in rows for p in agreement_pairs(heads, keep, target, decisions))
                 for group, rows in built.items()}
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"imitation_{target}_weights.json").write_text(json.dumps(result["weights"]), encoding="utf-8")
    out = {"stage": STAGE, "probe": "P3 imitation sufficiency", "target": target, "positive_control": target in POSITIVE_CONTROLS,
           "rule": ASSOCIATION_TARGETS.get(target) or {"handcost": {"rho_h": HANDCOST_RHO}, "rac": {"rho_rac": RAC_RHO, "n_rac": RAC_N},
                                                       "elup": elu_p_values()}[target],
           "records": f"{OWN_PASS}/{OWN_ARM}", "holdout": split, "frames": {g: len(r) for g, r in built.items()},
           "recipe": {"learning_rate": model.LEARNING_RATE, "weight_decay": arms.WEIGHT_DECAY, "epochs": int(args.epochs), "seed": int(arms.SEEDS[0])},
           "best_epoch": result["best_epoch"], "diverged": result["diverged"], "weights_sha256": result["weights"]["sha256"],
           "agreement": agreement, "wall_seconds": round(time.time() - started, 1),
           "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (out_dir / f"imitation_{target}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({"target": target, "train": agreement["train"]["balanced_agreement"],
                      "selection": agreement["selection"]["balanced_agreement"], "best_epoch": result["best_epoch"]}, indent=1))
    return 0 if not result["diverged"] else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("coverage")
    c.add_argument("--output-root", required=True)
    c.add_argument("--pass", dest="passes", action="append", required=True, help="pass:arm, e.g. dagger_round_1:VSMT-lean")
    c.add_argument("--output", required=True)
    c.set_defaults(func=cmd_coverage)
    s = sub.add_parser("sensitivity")
    s.add_argument("--output-root", required=True)
    s.add_argument("--weights", required=True)
    s.add_argument("--label", required=True)
    s.add_argument("--output", required=True)
    s.set_defaults(func=cmd_sensitivity)
    i = sub.add_parser("imitation")
    i.add_argument("--output-root", required=True)
    i.add_argument("--target", required=True, choices=TARGETS)
    i.add_argument("--output-dir", required=True)
    i.add_argument("--epochs", type=int, default=20)
    i.set_defaults(func=cmd_imitation)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
