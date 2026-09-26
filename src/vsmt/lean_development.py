"""D-224 / S2-05: the development table -- calibration, the ELU-P fit counts and the table itself.

S2-05 runs the arms of the main table (and the NoVersion / AssocOnly ablations) over the succeeded
episodes of the development cache and produces the first table, the per-episode failures, the
runtime and memory readings and the interface-issue list.  The per-episode work is S2-01 + S2-04
(``ops/vsmt/lean_s2_04_evaluate_episode.py``); this module holds the pure pieces the orchestration
composes and that the contract binds:

  * ``Histogram`` and ``CalibrationCollector``: mergeable fixed-bin histograms of the sealed
    quantities the still-null values and grids are chosen against (same-object and other-object
    cosines, target-pair centroid distances and box IoU, best cosine of novel fragments, the two
    geometry ratios of existence candidates by gone/present, fragment dominance shares).  They read
    the sealed rows and the S0-04 labels of a pass, never anything private beyond the labels;
  * ``EluPCounter``: the S0-05 v2 fitting procedure's four count records over one episode, from the
    private truth tracker, the frame's public visibility and the gate arm's assignment; the counts
    of every development episode are summed and ``lean_controls.fit_elu_p_quantities`` turns them
    into ELU-P's three fitted scalars;
  * ``development_table``: house-level headline values per arm and metric from the S2-04 episode
    reports, the ruling-X2 exclusion list per metric over the applicable arms (never-retracting arms
    are not applicable to the false retract rate), the mean per arm over the effective houses and the
    paired development difference of VSMT-lean against every other arm (no bootstrap: that is S3),
    plus the size-and-cost readings;
  * ``validate_development_contract``: the machine contract.

白话：S2-05 要出第一张开发表，但跑之前有一堆数值还没定（去重阈值、dormancy 次数、各臂网格与开发
配置、ELU-P 的三个拟合量），定它们需要看到真实分布。本模块提供三件纯工具：一是"校准直方图"，从
封存的特征行和 S0-04 标签里统计同物体/异物体余弦、目标对距离与 IoU、新物体的最高余弦、存在候选的
两个比例等，用来给网格与阈值提议；二是 ELU-P 拟合量的计数器，按 S0-05 v2 的定义逐帧数"看不见一
阵子后还在原处"、"每帧被移走的风险"、"物体在时门内配上 vs 物体不在时门内仍配上"；三是开发表的装
配：按 house 取每臂每指标的主值，按裁决 X2 算排除清单，取均值与 VSMT-lean 对每臂的配对差。它不做
bootstrap（S3）、不选参、不训练。
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping, Sequence

from cpmt.hashing import clone_json

from vsmt import lean_arms as arms
from vsmt import lean_assignment as la
from vsmt import lean_controls as lc
from vsmt import lean_evaluation as ev
from vsmt import lean_frontend_cache as fc
from vsmt import lean_object_geometry as og
from vsmt import lean_teacher as lt

CONTRACT_SCHEMA_VERSION = "vsmt-lean-s2-05-development-v1"
STAGE_ID = "S2-05"

#: Arms of the development table (the main-table arms plus the NoVersion ablation; AssocOnly is a main-table arm).
DEVELOPMENT_ARMS = ("VSMT-lean", "TAF", "ELU-P", "RAC", "LOW", "NoVersion", "AssocOnly")
METHOD_ARM = arms.METHOD_ARM
#: Direction in which a larger headline value is better (size_and_cost is reported, never compared).
BETTER = {"node_prf1": "higher", "node_prf1_iou": "higher", "missing_residual_rate": "lower", "false_retract_rate": "lower",
          "identity_continuity": "higher", "recovery_latency_frames": "lower", "contamination_auc": "lower"}
#: The passes of S2-05 in order; each pass is one S2-04 run per episode.
PASSES = (
    "calibration",          # TAF at the rollout theta_a, no distance gate (ruling 75): the histograms and the ELU-P counts
    "elu_p_fit",            # TAF at the registered rollout theta_a with no gate: the ELU-P count records
    "dagger_round_0",       # ELU-P at the rollout_config: rollouts and labels for round-0 training (also ELU-P's table row)
    "dagger_round_1",       # VSMT-lean and AssocOnly round-0 heads on their own rollouts: labels for round-1 training
    "development_table",    # TAF, RAC, LOW at the development configurations; VSMT-lean, NoVersion, AssocOnly at the round-1 heads
)
#: Ruling 75 (1)(a) (2026-09-26): the calibration pass runs the gated development association -- TAF at the ELU-P
#: rollout theta_a with no distance gate -- instead of LOW with no gate, whose nearest-entity-takes-all memory merged
#: several objects and background into one entity (LOG-261: present boxes read as seen through).  It is exactly the
#: ELU-P fit pass's arm and configuration, so the same pass also writes the ELU-P count records and ``fit-elu-p`` may
#: read them from the calibration root; the evidence ceiling on an ideal memory is a separate read-only diagnostic.
CALIBRATION_ARM_CONFIG = {"arm": "TAF", "config": {"theta_a": arms.ROLLOUT_CONFIG["theta_a"], "d_a": None}}
CALIBRATION_WRITES_ELU_P_COUNTS_RULE = "the_calibration_pass_is_the_elu_p_fit_arm_and_configuration_and_also_writes_the_elu_p_count_records"
ELU_P_FIT_ARM_RULE = "TAF_at_the_registered_rollout_theta_a_with_no_distance_gate"
DEVELOPMENT_TRAINING_RULE = "one_development_training_per_round_at_the_first_registered_seed"
MERGE_ORDER_RULE = "episode_id_ascending_regardless_of_worker_completion_order"
EPISODE_SET_RULE = "every_succeeded_episode_of_the_development_cache_no_refill_no_regeneration"

#: Fixed histogram bins (mergeable across episodes and workers).
COSINE_EDGES = tuple(round(-1.0 + 0.02 * i, 2) for i in range(101))
DISTANCE_EDGES = tuple(round(0.05 * i, 2) for i in range(201))
RATIO_EDGES = tuple(i / 64.0 for i in range(65))
COUNT_EDGES = tuple(float(i) for i in range(0, 65))
CALIBRATION_SERIES = {
    "same_object_cosine_to_mean": COSINE_EDGES,
    "same_object_cosine_to_best_view": COSINE_EDGES,
    "other_object_cosine_to_mean": COSINE_EDGES,
    "novel_fragment_best_cosine": COSINE_EDGES,
    "same_object_centroid_distance_m": DISTANCE_EDGES,
    "other_object_centroid_distance_m": DISTANCE_EDGES,
    "same_object_aabb_iou": RATIO_EDGES,
    "fragment_dominance_share": RATIO_EDGES,
    "entity_should_be_visible_ratio": RATIO_EDGES,
    "gone_free_space_coverage_ratio": RATIO_EDGES,
    "present_free_space_coverage_ratio": RATIO_EDGES,
    "gone_missed_opportunity_count": COUNT_EDGES,
    "present_missed_opportunity_count": COUNT_EDGES,
    "same_object_fragments_per_frame": COUNT_EDGES,
    # ruling 74 (2)(a): the gone rows split by cause -- the object has left the scene (absent) or it is present
    # but more than delta from where the entity remembers it (moved, which also holds mislocated entities) --
    # the should-be-visible ratio of the existence rows by label, and how well a present entity's box sits on
    # its object's truth box; read-only diagnostics for the re-freeze after the per-point depth test
    "gone_absent_free_space_coverage_ratio": RATIO_EDGES,
    "gone_moved_free_space_coverage_ratio": RATIO_EDGES,
    "gone_should_be_visible_ratio": RATIO_EDGES,
    "present_should_be_visible_ratio": RATIO_EDGES,
    "present_entity_truth_box_iou": RATIO_EDGES,
}
QUANTILES = (0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95)

#: The contract spells "no distance gate" as this string in a frozen slot (null means unfrozen).
NO_GATE_STRING = "no_gate"
#: D-224-S1 ruling 68 (3) (2026-09-25, LOG-256 sequel): the one configuration each development arm runs at
#: in the development-table pass (and the learned arms in DAgger round 1), in runner form; every one is
#: a member of the S0-05 grid.  The three rule arms take no gate like the ELU-P rollout, so the table
#: and the round-0 rollouts read side by side; LOW takes 1.0 m to differ from the no-gate calibration
#: arm; NoVersion shares VSMT-lean's tau_r (a runner switch, not a configuration); AssocOnly has none.
DEVELOPMENT_CONFIGURATIONS: dict[str, dict[str, Any]] = {
    "TAF": {"theta_a": 0.7, "d_a": None},
    "RAC": {"theta_a": 0.7, "d_a": None, "rho_rac": 0.7, "n_rac": 3},
    "LOW": {"d_low": 1.0},
    "VSMT-lean": {"tau_r": 0.5},
    "NoVersion": {"tau_r": 0.5},
    "AssocOnly": {},
}


class LeanDevelopmentError(ValueError):
    """Raised with a short machine-readable code."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LeanDevelopmentError(code)


def development_configuration(contract: Mapping[str, Any], arm: str) -> dict[str, Any] | None:
    """The registered development configuration of an arm in runner form, or None while a slot is still null.

    白话：把合同里 development_configurations 的槽位翻译成 runner 吃的配置：距离门 "no_gate" 变成 None、
    数字原样；NoVersion 用 VSMT-lean 的 tau_r；AssocOnly 没有参数。任一槽仍是 null 就返回 None（未冻结）。
    翻译出来的配置必须是 S0-05 已冻结网格的一格，否则拒绝（ruling 68 (3)）。
    """

    _require(arm in DEVELOPMENT_CONFIGURATIONS, f"development_configuration_unknown_arm:{arm}")
    if arm == "AssocOnly":
        return {}
    source = "VSMT-lean" if arm == "NoVersion" else arm
    section = contract["development_configurations"][source]
    config: dict[str, Any] = {}
    for name in arms.GRID_PARAMETERS[source]:
        value = section[name]
        if name == arms.NO_GATE_PARAMETER.get(source):
            value = value["distance_gate_m"]
            if value == NO_GATE_STRING:
                value = None
            elif value is None:
                return None
            else:
                _require(type(value) in (int, float) and value > 0, f"development_configuration_gate_invalid:{source}")
        elif value is None:
            return None
        config[name] = value
    members = arms.enumerate_configs(arm, arms.FROZEN_GRIDS[arm])
    _require(any(member == config for member in members), f"development_configuration_not_a_grid_member:{arm}")
    return config


# --------------------------------------------------------------------------
# 1. histograms and the calibration collector
# --------------------------------------------------------------------------

class Histogram:
    """Fixed-edge counts, clipped into the outer bins; mergeable; quantiles by linear interpolation within a bin."""

    def __init__(self, edges: Sequence[float], counts: Sequence[int] | None = None) -> None:
        self.edges = [float(v) for v in edges]
        _require(len(self.edges) >= 2 and all(a < b for a, b in zip(self.edges, self.edges[1:])), "histogram_edges_invalid")
        self.counts = [int(v) for v in (counts if counts is not None else [0] * (len(self.edges) - 1))]
        _require(len(self.counts) == len(self.edges) - 1, "histogram_counts_invalid")
        self.total = sum(self.counts)
        self.sum = 0.0

    def add(self, value: float) -> None:
        v = float(value)
        _require(math.isfinite(v), "histogram_value_invalid")
        index = 0
        while index < len(self.counts) - 1 and v >= self.edges[index + 1]:
            index += 1
        self.counts[index] += 1
        self.total += 1
        self.sum += v

    def merge(self, other: "Histogram") -> None:
        _require(self.edges == other.edges, "histogram_edges_differ")
        self.counts = [a + b for a, b in zip(self.counts, other.counts)]
        self.total += other.total
        self.sum += other.sum

    def quantile(self, q: float) -> float | None:
        if self.total == 0:
            return None
        target = q * self.total
        seen = 0
        for index, count in enumerate(self.counts):
            if seen + count >= target and count > 0:
                lo, hi = self.edges[index], self.edges[index + 1]
                inside = (target - seen) / count
                return lo + inside * (hi - lo)
            seen += count
        return self.edges[-1]

    def summary(self) -> dict[str, Any]:
        return {"count": self.total, "mean": (self.sum / self.total) if self.total else None,
                **{f"p{int(q * 100):02d}": self.quantile(q) for q in QUANTILES}}

    def to_json(self) -> dict[str, Any]:
        return {"edges": list(self.edges), "counts": list(self.counts), "sum": self.sum}

    @classmethod
    def from_json(cls, payload: Mapping[str, Any]) -> "Histogram":
        out = cls(payload["edges"], payload["counts"])
        out.sum = float(payload.get("sum", 0.0))
        return out


class CalibrationCollector:
    """Histograms of the sealed quantities the open values and grids are chosen against, from one pass's steps and labels.

    白话：每帧拿 runner 的一步（封存 A 的特征行、封存 B 的存在行、实体几何比例）和 S2-04 的标签，把
    "被标为同一物体的目标对"的余弦/距离/IoU、"其他候选对"的余弦、新物体色块的最高余弦、存在候选按
    gone/present 分的两个比例与错失次数、色块主导占比等记进固定边界的直方图。直方图可跨 episode、跨
    worker 合并，分位数由直方图算出，用来给网格与阈值提建议；它不读任何私有字节（只读标签）。
    """

    def __init__(self) -> None:
        self.histograms = {name: Histogram(edges) for name, edges in CALIBRATION_SERIES.items()}
        self.frames = 0
        self.fragments = 0
        self.labelled_fragments = 0

    def observe(self, step: Mapping[str, Any], labelled: Mapping[str, Any]) -> None:
        stage_a, stage_b = step["stage_a"], step["stage_b"]
        order = stage_a["association_feature_order"]
        cosine_at = arms.feature_index(order, "cosine_to_descriptor_mean")
        best_at = arms.feature_index(order, "cosine_to_best_view_descriptor")
        distance_at = arms.feature_index(order, "centroid_distance_m")
        iou_at = arms.feature_index(order, "aabb_iou")
        birth_order = stage_a["birth_feature_order"]
        novel_at = arms.feature_index(birth_order, "best_cosine_to_any_entity")
        rows_by_fragment: dict[str, list[Mapping[str, Any]]] = {}
        for row in stage_a["association_rows"]:
            rows_by_fragment.setdefault(str(row["fragment_id"]), []).append(row)
        births = {str(row["fragment_id"]): row for row in stage_a["birth_rows"]}
        targets = labelled["targets"]
        per_object: dict[str, int] = {}
        for fragment_id, target in targets.items():
            self.fragments += 1
            if target.get("key") is not None:
                per_object[str(target["key"])] = per_object.get(str(target["key"]), 0) + 1
                self.histograms["fragment_dominance_share"].add(float(target["share"]))
            status = target["status"]
            if status == "labelled":
                self.labelled_fragments += 1
                wanted = str(target["target"])
                for row in rows_by_fragment.get(fragment_id, []):
                    features = row["features"]
                    if str(row["entity_id"]) == wanted:
                        self.histograms["same_object_cosine_to_mean"].add(features[cosine_at])
                        self.histograms["same_object_cosine_to_best_view"].add(features[best_at])
                        self.histograms["same_object_centroid_distance_m"].add(features[distance_at])
                        self.histograms["same_object_aabb_iou"].add(features[iou_at])
                    else:
                        self.histograms["other_object_cosine_to_mean"].add(features[cosine_at])
                        self.histograms["other_object_centroid_distance_m"].add(features[distance_at])
            elif status == "birth" and fragment_id in births and fragment_id in rows_by_fragment:
                # a novel fragment that had recalled candidates: its best cosine is what a gate must reject
                self.histograms["novel_fragment_best_cosine"].add(births[fragment_id]["features"][novel_at])
        for count in per_object.values():
            self.histograms["same_object_fragments_per_frame"].add(float(count))
        for geometry in step["entity_geometry"].values():
            self.histograms["entity_should_be_visible_ratio"].add(float(geometry["should_be_visible_ratio"]))
        existence_order = stage_b["existence_feature_order"]
        coverage_at = arms.feature_index(existence_order, "free_space_coverage_ratio")
        missed_at = arms.feature_index(existence_order, "missed_opportunity_count")
        rows_by_id = {str(row["entity_id"]): row for row in stage_b["existence_rows"]}
        box_iou = labelled.get("existence_truth_box_iou") or {}
        for entity_id, label in labelled["existence_labels"].items():
            if label["status"] not in ("gone", "present"):
                continue
            features = rows_by_id[entity_id]["features"]
            self.histograms[f"{label['status']}_free_space_coverage_ratio"].add(features[coverage_at])
            self.histograms[f"{label['status']}_missed_opportunity_count"].add(features[missed_at])
            self.histograms[f"{label['status']}_should_be_visible_ratio"].add(float(step["entity_geometry"][entity_id]["should_be_visible_ratio"]))
            if label["status"] == "gone" and label.get("reason") in ("absent", "moved"):
                self.histograms[f"gone_{label['reason']}_free_space_coverage_ratio"].add(features[coverage_at])
            if label["status"] == "present" and entity_id in box_iou:
                self.histograms["present_entity_truth_box_iou"].add(float(box_iou[entity_id]))
        self.frames += 1

    def merge(self, other: "CalibrationCollector") -> None:
        for name, histogram in self.histograms.items():
            histogram.merge(other.histograms[name])
        self.frames += other.frames
        self.fragments += other.fragments
        self.labelled_fragments += other.labelled_fragments

    def to_json(self) -> dict[str, Any]:
        return {"frames": self.frames, "fragments": self.fragments, "labelled_fragments": self.labelled_fragments,
                "histograms": {name: histogram.to_json() for name, histogram in self.histograms.items()}}

    @classmethod
    def from_json(cls, payload: Mapping[str, Any]) -> "CalibrationCollector":
        out = cls()
        out.frames, out.fragments, out.labelled_fragments = int(payload["frames"]), int(payload["fragments"]), int(payload["labelled_fragments"])
        for name in out.histograms:
            out.histograms[name] = Histogram.from_json(payload["histograms"][name])
        return out

    def report(self) -> dict[str, Any]:
        return {"frames": self.frames, "fragments": self.fragments, "labelled_fragments": self.labelled_fragments,
                "series": {name: histogram.summary() for name, histogram in self.histograms.items()}}


# --------------------------------------------------------------------------
# 2. the ELU-P count records (S0-05 v2 fitting procedure)
# --------------------------------------------------------------------------

class EluPCounter:
    """The four count records of one episode under the gate arm's rollout, per the S0-05 v2 definitions.

    白话：逐帧数三件事。(1) 初始 log-odds 的先验：某物体被看见过之后，它上次被看见的位置有一阵子对
    方法不可观察（用 S2-04 那套采样盒判定），等那个位置再次可观察的第一帧，记一次"物体帧"，若物体仍
    在场且离上次被看见的位置不超过 delta_moved，记一次"在位"。(2) 持续性风险：本 episode 至少被看见过
    一次的物体各贡献"帧数"个物体-tick，其中被移走或搬动的记一次事件。(3) 匹配增益：对有承载实体的物
    体，物体在场、未被干预、其真值盒可观察的帧记一次"应命中"，若门把某个色块绑到了它的承载实体记一次
    命中；被移走/搬动之后，旧位置可观察的帧记一次"应误配"，若门仍把色块绑到承载实体记一次误配。
    它只读追踪器真值、公开可见体积、门臂的分配和 teacher 的证据映射。
    """

    def __init__(self, *, geometry_table: Mapping[str, Any], executed_interventions: Sequence[Mapping[str, Any]],
                 window: Sequence[int] | None, policy: Mapping[str, Any],
                 observable_min_pixels: int = fc.MINIMUM_VISIBLE_PIXELS) -> None:
        self.policy = ev.validate_policy(policy)
        executed = [row for row in executed_interventions if row.get("executed", True)]
        self.tracker = og.EpisodeTruthTracker(geometry_table, executed_interventions=executed, window=window)
        self.kinds = {str(row["object_id"]): str(row["kind"]) for row in executed}
        self.window_end: int | None = None if window is None else int(window[1])
        self.min_pixels = int(observable_min_pixels)
        self.last_observed_centroid: dict[str, list[float]] = {}
        self.last_observed_box: dict[str, tuple[list[float], list[float]]] = {}
        self.pending_gap: set[str] = set()
        self.ever_observed: set[str] = set()
        self.old_place: dict[str, tuple[list[float], list[float]]] = {}
        self.frames = 0
        self.counts = {"in_place_object_frames": 0, "object_frames": 0, "hit_frames": 0, "hit_total": 0,
                       "false_frames": 0, "false_total": 0}

    def _observable(self, cache_frame: Mapping[str, Any], box: tuple[Sequence[float], Sequence[float]]) -> bool:
        return ev.place_observable(cache_frame, box, samples_per_axis=self.policy["entity_geometry_samples_per_axis"],
                                   visible_min_ratio=self.policy["should_be_visible_min_ratio"])

    def observe(self, step: Mapping[str, Any], *, cache_frame: Mapping[str, Any], private_record: Mapping[str, Any],
                evidence: Mapping[str, str | None]) -> None:
        frame_index = int(step["receipt"]["tick"]) - 1
        truth = self.tracker.update(frame_index, private_record)
        visibility = private_record["object_visibility"]
        delta = self.policy["delta_moved_m"]
        after = self.window_end is not None and frame_index > self.window_end
        identities = lt.entity_identities(step["memory_before"], evidence)
        carriers: dict[str, list[str]] = {}
        for entity_id, identity in identities.items():
            if identity["resolvable"]:
                carriers.setdefault(identity["key"], []).append(entity_id)
        bound = {str(v) for v in step["receipt"]["assignment"].values() if not str(v).startswith(la.BIRTH_COLUMN_PREFIX)}
        for key in sorted(truth):
            entry = truth[key]
            present = bool(entry["present"])
            observed = int(visibility.get(key, 0)) >= self.min_pixels
            # (1) the in-place prior after an unobserved gap of the last-observed place
            if key in self.last_observed_box:
                if self._observable(cache_frame, self.last_observed_box[key]):
                    if key in self.pending_gap:
                        self.counts["object_frames"] += 1
                        in_place = present and lt._distance(entry["centroid_m"], self.last_observed_centroid[key]) <= delta
                        self.counts["in_place_object_frames"] += int(in_place)
                        self.pending_gap.discard(key)
                else:
                    self.pending_gap.add(key)
            if observed and present:
                self.last_observed_centroid[key] = [float(v) for v in entry["centroid_m"]]
                self.last_observed_box[key] = ev.place_box(entry)
                self.ever_observed.add(key)
            # (3) the gate's hit and false-match rates for objects that have a carrier entity
            holders = carriers.get(key, [])
            if holders:
                matched = any(entity_id in bound for entity_id in holders)
                intervened_away = after and self.kinds.get(key) in ("remove", "move")
                if present and not intervened_away:
                    if self._observable(cache_frame, ev.place_box(entry)):
                        self.counts["hit_total"] += 1
                        self.counts["hit_frames"] += int(matched)
                elif intervened_away and key in self.old_place and self._observable(cache_frame, self.old_place[key]):
                    self.counts["false_total"] += 1
                    self.counts["false_frames"] += int(matched)
        if self.window_end is not None and frame_index == self.window_end:
            for key, kind in self.kinds.items():
                if kind in ("remove", "move") and truth.get(key, {}).get("present"):
                    self.old_place[key] = ev.place_box(truth[key])
        self.frames += 1

    def finish(self) -> dict[str, dict[str, int]]:
        """The count records in the ``lean_controls.ELU_P_COUNT_FIELDS`` shape (record 2 is per episode)."""

        events = sum(1 for key in self.ever_observed if self.kinds.get(key) in ("remove", "move"))
        return {
            "initial_log_odds": {"in_place_object_frames": self.counts["in_place_object_frames"], "object_frames": self.counts["object_frames"]},
            "persistence_log_decay_per_tick": {"intervention_events": events, "object_ticks": len(self.ever_observed) * self.frames},
            "match_gain": {name: self.counts[name] for name in ("hit_frames", "hit_total", "false_frames", "false_total")},
        }


def sum_counts(records: Iterable[Mapping[str, Mapping[str, int]]]) -> dict[str, dict[str, int]]:
    """Sum the count records of several episodes field by field."""

    total = {name: {field: 0 for field in fields} for name, fields in lc.ELU_P_COUNT_FIELDS.items()}
    for record in records:
        _require(set(record) == set(total), "elu_p_count_record_invalid")
        for name, fields in total.items():
            _require(set(record[name]) == set(fields), f"elu_p_count_record_invalid:{name}")
            for field in fields:
                fields[field] += int(record[name][field])
    return total


def fit_elu_p(records: Iterable[Mapping[str, Mapping[str, int]]], *, rollout_config: Mapping[str, Any]) -> dict[str, Any]:
    """The three ELU-P scalars from the summed development counts (train split, after the seals)."""

    counts = sum_counts(records)
    try:
        fitted = lc.fit_elu_p_quantities(counts, split="train", seals_written=True, rollout_config=rollout_config)
    except lc.LeanControlsError as exc:
        raise LeanDevelopmentError(f"elu_p_fit_refused:{exc}") from exc
    return {"counts": counts, **fitted}


# --------------------------------------------------------------------------
# 3. the development table
# --------------------------------------------------------------------------

def not_applicable_arms(metric: str, table_arms: Sequence[str]) -> list[str]:
    """Arms for which a metric is undefined by construction (S0-04 metric_not_applicable_rule)."""

    if metric == "false_retract_rate":
        return [arm for arm in table_arms if arm in arms.arms_without_atom("RETRACT")]
    return []


def development_table(reports: Mapping[str, Mapping[str, Mapping[str, Any]]], *, table_arms: Sequence[str] = DEVELOPMENT_ARMS,
                      method_arm: str = METHOD_ARM) -> dict[str, Any]:
    """House-level headline values, ruling-X2 exclusions, per-arm means and paired development differences.

    白话：输入每个臂在每条 episode 上的 S2-04 报告，输出开发表：每个指标按 house 取各臂主值，某个 house
    在任一适用臂上没法算就对所有臂一并排除（裁决 X2；从不撤回的臂对假撤回率不适用、不参与排除），报告有
    效 house 数、各臂均值和 VSMT-lean 对每个臂的配对差均值（不做 bootstrap，那是 S3）。缺任一臂的 house
    直接拒绝而不是跳过。它不选赢家。
    """

    names = [str(arm) for arm in table_arms]
    _require(method_arm in names, "development_table_lacks_the_method_arm")
    _require(set(reports) == set(names), f"development_table_arms_mismatch:{sorted(set(reports) ^ set(names))}")
    houses = sorted(reports[method_arm])
    for arm in names:
        _require(sorted(reports[arm]) == houses, f"development_table_house_sets_differ:{arm}")
    _require(bool(houses), "development_table_without_houses")
    out: dict[str, Any] = {"arms": names, "method_arm": method_arm, "houses": houses, "metrics": {}}
    for metric in lt.METRICS:
        if metric == "size_and_cost":
            out["metrics"][metric] = {
                arm: {field: (sum(float(reports[arm][h]["size_and_cost"][field]) for h in houses) / len(houses)
                              if field != "peak_memory_bytes" else max(int(reports[arm][h]["size_and_cost"][field]) for h in houses))
                      for field in lt.METRIC_FIELDS["size_and_cost"]}
                for arm in names
            }
            continue
        field = ev.HEADLINE_FIELD[metric]
        skipped = not_applicable_arms(metric, names)
        applicable = [arm for arm in names if arm not in skipped]
        per_house = {house: {arm: reports[arm][house][metric][field] for arm in applicable} for house in houses}
        excluded = lt.undefined_houses(per_house, arms=applicable, not_applicable=skipped)
        effective = [house for house in houses if house not in excluded]
        means: dict[str, float | None] = {}
        for arm in names:
            if arm in skipped:
                means[arm] = None
                continue
            means[arm] = (sum(float(per_house[h][arm]) for h in effective) / len(effective)) if effective else None
        differences: dict[str, Any] = {}
        for arm in names:
            if arm == method_arm or arm in skipped or method_arm in skipped or not effective:
                differences[arm] = None
                continue
            diffs = [float(per_house[h][method_arm]) - float(per_house[h][arm]) for h in effective]
            mean_diff = sum(diffs) / len(diffs)
            advantage = mean_diff if BETTER[metric] == "higher" else -mean_diff
            differences[arm] = {"method_minus_arm": mean_diff, "method_advantage": advantage, "houses": len(diffs)}
        out["metrics"][metric] = {"headline_field": field, "better": BETTER[metric], "not_applicable": skipped,
                                  "excluded_houses": excluded, "effective_houses": len(effective),
                                  "mean": means, "method_minus_each_arm": differences, "per_house": per_house}
    return out


# --------------------------------------------------------------------------
# 4. machine contract
# --------------------------------------------------------------------------

def validate_development_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Check that the S2-05 machine contract agrees with this implementation."""

    _require(type(contract) is dict, "contract_not_object")
    _require(contract.get("schema_version") == CONTRACT_SCHEMA_VERSION, "contract_schema_version_invalid")
    _require(contract.get("decision_id") == "D-224", "contract_decision_id_invalid")
    _require(contract.get("stage_id") == STAGE_ID, "contract_stage_id_invalid")
    _require(tuple(contract["development_arms"]) == DEVELOPMENT_ARMS, "contract_development_arms_mismatch")
    _require(tuple(contract["passes"]["order"]) == PASSES, "contract_passes_mismatch")
    _require(dict(contract["passes"]["calibration_arm"]) == CALIBRATION_ARM_CONFIG, "contract_calibration_arm_mismatch")
    _require(contract["passes"].get("calibration_writes_elu_p_counts") == CALIBRATION_WRITES_ELU_P_COUNTS_RULE,
             "contract_calibration_elu_p_counts_rule_mismatch")
    _require(contract["passes"]["elu_p_fit_arm_rule"] == ELU_P_FIT_ARM_RULE, "contract_elu_p_fit_rule_mismatch")
    _require(contract["passes"]["development_training_rule"] == DEVELOPMENT_TRAINING_RULE, "contract_training_rule_mismatch")
    _require(contract["episodes"]["rule"] == EPISODE_SET_RULE, "contract_episode_rule_mismatch")
    _require(contract["workers"]["merge_order_rule"] == MERGE_ORDER_RULE, "contract_merge_order_mismatch")
    _require(dict(contract["table"]["better"]) == BETTER, "contract_better_mismatch")
    _require(tuple(contract["calibration"]["series"]) == tuple(CALIBRATION_SERIES), "contract_calibration_series_mismatch")
    _require(tuple(contract["calibration"]["quantiles"]) == QUANTILES, "contract_calibration_quantiles_mismatch")
    for name in ("no_winner_is_selected", "no_grid_is_tuned", "no_ablation_is_deleted", "design_revisions_go_through_a_ruling_before_s3_01",
                 "validation_and_test_are_never_read", "every_pass_is_an_s2_04_run_per_episode"):
        _require(contract["continue_gate"][name] is True, f"contract_claim_weakened:{name}")
    slots = contract["policy_values_without_defaults"]
    for path in slots:
        node: Any = contract
        for part in path.split("."):
            node = node[part]
        _require(node is None, f"contract_slot_filled_but_listed_as_open:{path}")
    registered = contract.get("registered_value_slots") or slots
    _require(set(slots) <= set(registered), "contract_open_slot_not_registered")
    for arm, expected in DEVELOPMENT_CONFIGURATIONS.items():  # ruling 68 (3): a frozen slot must carry the bound value
        config = development_configuration(contract, arm)
        if config is not None:
            _require(config == expected, f"contract_development_configuration_mismatch:{arm}")
    policy = contract.get("activation_policy")
    opened = set(policy["active_true_authorizations"]) if policy else set()
    if policy:
        _require(type(policy.get("opened_by")) is str and bool(policy["opened_by"]), "contract_activation_policy_names_no_ruling")
    for name, value in contract["authorization"].items():
        _require(type(value) is bool, f"contract_authorization_not_boolean:{name}")
        _require(value is False or name in opened, f"contract_bit_opened_without_a_ruling:{name}")
    return clone_json(dict(contract))


__all__ = [
    "BETTER",
    "CALIBRATION_ARM_CONFIG",
    "CALIBRATION_WRITES_ELU_P_COUNTS_RULE",
    "CALIBRATION_SERIES",
    "CONTRACT_SCHEMA_VERSION",
    "CalibrationCollector",
    "DEVELOPMENT_ARMS",
    "DEVELOPMENT_CONFIGURATIONS",
    "DEVELOPMENT_TRAINING_RULE",
    "NO_GATE_STRING",
    "development_configuration",
    "ELU_P_FIT_ARM_RULE",
    "EPISODE_SET_RULE",
    "EluPCounter",
    "Histogram",
    "LeanDevelopmentError",
    "MERGE_ORDER_RULE",
    "METHOD_ARM",
    "PASSES",
    "QUANTILES",
    "STAGE_ID",
    "development_table",
    "fit_elu_p",
    "not_applicable_arms",
    "sum_counts",
    "validate_development_contract",
]
