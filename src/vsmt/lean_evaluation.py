"""D-224 / S2-04: teacher and evaluator wiring -- from the S2-01 runner's per-frame products and the
private plane to labels, the three-way decomposition, the seven metrics and the training records.

The S0-04 core (``lean_teacher``, reviewed) already defines every label rule, every metric and the
statistics.  What it does not say is *where its inputs come from* once a real arm has run on a real
cache: which fragment covers which private instance, which entity has been collecting evidence of
which object, where a removed object used to stand, whether that place has been observable to the
method since, when a moved object was re-observed for the first time, and which rows of a frame the
existence head is actually asked about.  This module fixes those derivations, in registered rules,
so that S2-05 (and S3) can run runner and teacher frame by frame and every number on the table
comes from one auditable path:

  * ``fragment_instances``: the private overlap table of a frame's fragments, from the recovered
    cache masks (digest-checked against the sealed frame) and the private instance image;
  * ``EpisodeTeacher``: consumes one ``lean_runner.run_frame`` step per frame together with the
    frame's private record, opens private truth only against the receipt's two-seal gate, and
    produces the S0-04 labels (targets and existence), the decomposition, the per-frame metric
    inputs, the S2-03 training record and the nuisance-probe rows; at the end it assembles the
    seven-metric episode report with exactly the frozen fields;
  * the intervention bookkeeping the metrics need: old and new places of intervened objects from
    the S1-04 truth tracker, "observable to the method" decided by the same sampled-box test the
    arms apply to their own entities (S2-01 ``entity_geometry`` at the S0-05 shared minimum),
    carriers before a move, first labelled re-observation after a move, and the recovery flags.

The public phase never sees this module: the runner is a pure function of the cache and the arm,
and the receipt it returns already carries the two seals.  Nothing here changes a public byte.

白话：S0-04 已经把"标签怎么打、七项指标怎么算"定死了；S2-04 补的是"跑起来之后这些输入从哪来"。
每帧：拿 runner 的一步产物（封存 A/B、分配、存在候选与决定、提交前后的记忆）和这一帧的私有记录
（实例图、物体位姿、可见像素），先核对放行回执，再算每个色块落在哪个物体上、每个实体一直在
收集谁的证据，据此给出 S0-04 的目标列与存在标签、三分解、逐帧的节点匹配与污染占比、假撤回、
规模成本，并顺手写出 S2-03 要吃的训练记录。窗口过后，从 S1-04 的真值追踪器取被移走/搬动物体的
旧位置与新位置，用臂自己那套"包围盒采样点落进可见体积"的判定决定"这个地方对方法可观察了没
有"，从而算 Missing 残留率、身份连续率和恢复延迟。它不训练、不选参、不改任何公开字节。
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import numpy as np

from cpmt.hashing import clone_json

from vsmt import lean_frontend_cache as fc
from vsmt import lean_frontend_diagnostics as fd
from vsmt import lean_model
from vsmt import lean_object_geometry as og
from vsmt import lean_runner as lr
from vsmt import lean_teacher as lt

CONTRACT_SCHEMA_VERSION = "vsmt-lean-s2-04-evaluation-v1"
STAGE_ID = "S2-04"

#: Intervention kinds of the S0-02 log and the S0-04 expectation kinds they map to.
INTERVENTION_KINDS = ("remove", "move", "add")
EXPECTATION_KIND = {"remove": "removed", "move": "moved", "add": "added"}
#: Which intervened objects each intervention-based metric judges.
MISSING_KINDS = ("remove", "move")
CONTINUITY_KINDS = ("move",)

#: Registered derivation rules (bound by the contract validator).
PLACE_OBSERVABLE_RULE = (
    "the_object_truth_box_at_the_place_(its_centroid_point_when_the_object_has_no_box)_sampled_by_the_"
    "s2_01_entity_geometry_function_has_should_be_visible_ratio_at_or_above_the_s0_05_shared_minimum_"
    "under_the_frame_public_visibility_blocks"
)
RECOVERY_PLACE_RULE = {"removed": "old_place", "added": "new_place", "moved": "old_place_or_new_place"}
OLD_PLACE_RULE = "truth_centroid_and_box_at_the_last_window_frame"
NEW_PLACE_RULE = "truth_centroid_and_box_at_the_first_frame_after_the_window"
CARRIERS_BEFORE_MOVE_RULE = (
    "entity_ids_of_any_state_whose_strict_majority_identity_resolves_to_the_object_in_the_memory_"
    "committed_at_the_last_window_frame"
)
REOBSERVATION_RULE = (
    "first_frame_after_the_window_in_which_a_fragment_dominance_resolves_to_the_moved_object;_among_"
    "several_the_most_object_pixels_then_the_larger_fragment_then_the_smaller_fragment_id"
)
EVIDENCE_INSTANCE_RULE = "per_fragment_the_dominant_private_key_under_s0_04_fragment_dominance_else_null"
STRUCTURAL_EXISTENCE_RULE = (
    "an_existence_candidate_whose_identity_resolves_to_a_structural_key_is_labelled_present_because_"
    "structure_is_never_intervened_and_has_no_point_centroid"
)
MRR_HEADLINE_RULE = "the_last_frame_of_the_episode;_the_per_frame_series_is_diagnostic"
TRAINING_RECORD_RULE = "existence_rows_and_labels_are_the_runner_eligible_candidates_only"
NUISANCE_RECORD_RULE = "one_record_per_fragment_for_the_association_labels_and_one_per_existence_candidate"

#: Every shared value the wiring needs, none with a default (S0-04 two, S0-05 one, S2-01 one).
POLICY_FIELDS = ("dominance_min_share", "delta_moved_m", "should_be_visible_min_ratio", "entity_geometry_samples_per_axis")
POLICY_INPUT_SOURCES = {
    "dominance_min_share": "S0-04 labels.fragment_dominance.dominance_min_share",
    "delta_moved_m": "S0-04 labels.existence.delta_moved_m",
    "should_be_visible_min_ratio": "S0-05 shared.should_be_visible_min_ratio",
    "entity_geometry_samples_per_axis": "S2-01 entity_geometry.samples_per_axis",
    "iou_min": "S0-04 metrics.node_prf1.iou_min (frozen 0.3)",
}
#: The scalar each metric contributes to a house-level table (size_and_cost has none).
HEADLINE_FIELD = {
    "node_prf1": "node_f1",
    "missing_residual_rate": "missing_residual_rate",
    "false_retract_rate": "false_retract_rate",
    "identity_continuity": "identity_continuity",
    "recovery_latency_frames": "recovery_latency_frames",
    "contamination_auc": "contamination_auc",
}
NUISANCE_ASSOCIATION_LABELS = ("association_status", "association_target_is_birth")
NUISANCE_EXISTENCE_LABELS = ("existence_status",)

FAILURE_REASONS = (
    "policy_value_missing",
    "private_gate_invalid",
    "private_record_out_of_order",
    "fragment_masks_do_not_match_the_sealed_frame",
    "intervened_object_unjudgeable",
    "truth_key_outside_geometry_table",
)


class LeanEvaluationError(ValueError):
    """Raised with a short machine-readable code."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LeanEvaluationError(code)


def _finite(value: Any, code: str) -> float:
    _require(type(value) in {int, float} and type(value) is not bool, code)
    result = float(value)
    _require(math.isfinite(result), code)
    return result


def _int(value: Any, code: str, *, minimum: int | None = None) -> int:
    _require(type(value) is int and type(value) is not bool, code)
    if minimum is not None:
        _require(value >= minimum, code)
    return value


# --------------------------------------------------------------------------
# 1. policy values and the private overlap table
# --------------------------------------------------------------------------

def validate_policy(policy: Mapping[str, Any]) -> dict[str, Any]:
    """Every value the wiring reads, present and in range; None anywhere is refused."""

    _require(type(policy) is dict and set(policy) == set(POLICY_FIELDS), "policy_fields_invalid")
    for name in POLICY_FIELDS:
        _require(policy[name] is not None, f"policy_value_missing:{name}")
    share = _finite(policy["dominance_min_share"], "policy_value_missing:dominance_min_share")
    _require(0.0 < share <= 1.0, "policy_value_missing:dominance_min_share")
    delta = _finite(policy["delta_moved_m"], "policy_value_missing:delta_moved_m")
    _require(delta > 0.0, "policy_value_missing:delta_moved_m")
    ratio = _finite(policy["should_be_visible_min_ratio"], "policy_value_missing:should_be_visible_min_ratio")
    _require(0.0 < ratio <= 1.0, "policy_value_missing:should_be_visible_min_ratio")
    samples = _int(policy["entity_geometry_samples_per_axis"], "policy_value_missing:entity_geometry_samples_per_axis", minimum=1)
    return {"dominance_min_share": share, "delta_moved_m": delta, "should_be_visible_min_ratio": ratio,
            "entity_geometry_samples_per_axis": samples}


def object_of_label(private_record: Mapping[str, Any]) -> dict[int, str]:
    """Instance-image label -> private object key (the S0-02 private record's mapping, inverted)."""

    mapping = private_record.get("object_id_to_entity_id")
    _require(type(mapping) is dict, "private_record_without_object_mapping")
    return {int(label): str(key) for key, label in mapping.items()}


def fragment_instances(cache_frame: Mapping[str, Any], masks: Mapping[str, Any], label_image: Any,
                       label_to_object: Mapping[int, str]) -> dict[str, dict[str, Any]]:
    """The S0-04 ``fragment_instance`` table of one frame from the recovered masks and the private instance image.

    白话：输入封印过的 cache 帧、回收的色块 mask（先按定义重算每个 mask 的摘要、与帧里钉的摘要
    逐位核对）和私有实例图，输出每个色块落在各个私有物体上的像素占比（分母是色块全部像素，背景
    是没列出的余量）和色块的公开像素数。它只是把 S1-04 已经用过的重叠算法接到 S0-04 的输入形状上。
    """

    expected = [str(row["mask_sha256"]) for row in cache_frame["fragments"]]
    _require(list(masks["mask_sha256"]) == expected, "fragment_masks_do_not_match_the_sealed_frame")
    pixels = np.asarray(masks["masks"], dtype=bool)
    _require(pixels.shape[0] == len(expected), "fragment_masks_do_not_match_the_sealed_frame")
    image = np.asarray(label_image)
    out: dict[str, dict[str, Any]] = {}
    for n, row in enumerate(cache_frame["fragments"]):
        _require(fc.mask_sha256_of(pixels[n]) == expected[n], f"fragment_masks_do_not_match_the_sealed_frame:{row['fragment_id']}")
        overlap = fd.overlap_from_masks(pixels[n], image, label_to_object)
        out[str(row["fragment_id"])] = {"overlap": overlap, "pixel_count": int(row["pixel_count"])}
    return out


def object_state_from_truth(tracker_truth: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """S0-04 ``object_state`` (present, centroid when present) from the S1-04 tracker's frame output."""

    out: dict[str, dict[str, Any]] = {}
    for key, entry in tracker_truth.items():
        state: dict[str, Any] = {"present": bool(entry["present"])}
        if entry["present"]:
            state["centroid_m"] = [float(v) for v in entry["centroid_m"]]
        out[str(key)] = state
    return out


def place_box(entry: Mapping[str, Any]) -> tuple[list[float], list[float]]:
    """The truth box of a tracker entry, or its centroid as a flat box when the object has no box."""

    if entry.get("aabb_min_m") is not None and entry.get("aabb_max_m") is not None:
        return [float(v) for v in entry["aabb_min_m"]], [float(v) for v in entry["aabb_max_m"]]
    centroid = [float(v) for v in entry["centroid_m"]]
    return list(centroid), list(centroid)


def place_observable(cache_frame: Mapping[str, Any], box: tuple[Sequence[float], Sequence[float]], *,
                     samples_per_axis: int, visible_min_ratio: float) -> bool:
    """Is a place observable to the method this frame?  The arms' own sampled-box test, applied to a truth box."""

    pseudo = {"entities": [{"entity_id": "place", "aabb_min_m": list(box[0]), "aabb_max_m": list(box[1])}]}
    ratio = lr.entity_geometry(pseudo, cache_frame, samples_per_axis=samples_per_axis)["place"]["should_be_visible_ratio"]
    return ratio >= visible_min_ratio


# --------------------------------------------------------------------------
# 2. one episode: labels, decomposition, per-frame metric inputs, intervention bookkeeping
# --------------------------------------------------------------------------

class EpisodeTeacher:
    """Runs the S0-04 teacher and evaluator over one arm's rollout of one episode, frame by frame.

    白话：一条 episode、一个臂建一个对象。每帧调用 ``label_frame`` 一次，传入 runner 的那一步和
    这一帧的私有记录、色块 mask、实例图，它返回这一帧的标签、三分解、指标输入与训练记录；跑完后
    调用 ``episode_report`` 拿七项指标（字段恰为 S0-04 冻结的那些）和诊断信息。私有真值只凭回执里
    的两段封存摘要打开，公开产物一个字节都不读写。
    """

    def __init__(
        self, *, arm: str, geometry_table: Mapping[str, Any],
        executed_interventions: Sequence[Mapping[str, Any]], window: Sequence[int] | None,
        policy: Mapping[str, Any], nuisance_meta: Mapping[str, Any], iou_min: float = lt.IOU_MIN,
    ) -> None:
        self.arm = str(arm)
        self.policy = validate_policy(policy)
        self.iou_min = _finite(iou_min, "iou_min_invalid")
        _require(type(nuisance_meta) is dict and {"path", "seed", "house_index"} <= set(nuisance_meta), "nuisance_meta_invalid")
        self.nuisance_meta = clone_json(dict(nuisance_meta))
        executed = [row for row in executed_interventions if row.get("executed", True)]
        for row in executed:
            _require(row.get("kind") in INTERVENTION_KINDS, f"intervention_kind_unknown:{row.get('kind')}")
        self.tracker = og.EpisodeTruthTracker(geometry_table, executed_interventions=executed, window=window)
        self.builder = lr.TruthTableBuilder()
        self.interventions: dict[str, str] = {str(row["object_id"]): str(row["kind"]) for row in executed}
        _require(len(self.interventions) == len(executed), "object_intervened_twice")
        self.window_end: int | None = None if window is None else int(window[1])
        self.evidence: dict[str, str | None] = {}
        self.old_place: dict[str, dict[str, Any]] = {}
        self.new_place: dict[str, dict[str, Any]] = {}
        self.carriers_before_move: dict[str, list[str]] = {}
        self.old_place_observable_since: set[str] = set()
        self.reobserved_at: dict[str, int] = {}
        self.continuity = {"kept": 0, "judged": 0, "no_prior_carrier": 0}
        self.recovery_frames: list[dict[str, dict[str, bool]]] = []
        self.frames: list[dict[str, Any]] = []
        self.last_frame_index = -1
        self.last_frame_digest: str | None = None

    # -- helpers -----------------------------------------------------------

    def _after_window(self, frame_index: int) -> bool:
        return self.window_end is not None and frame_index > self.window_end

    def _snapshot_places(self, frame_index: int, tracker_truth: Mapping[str, Mapping[str, Any]], memory_after: Mapping[str, Any]) -> None:
        """Old places at the last window frame; new places at the first frame after it."""

        if self.window_end is None:
            return
        if frame_index == self.window_end:
            identities = lt.entity_identities(memory_after, self.evidence)
            for key, kind in self.interventions.items():
                entry = tracker_truth.get(key)
                _require(entry is not None and entry["present"] is True, f"intervened_object_unjudgeable:{key}:not_present_before_the_window_end")
                self.old_place[key] = {"centroid_m": [float(v) for v in entry["centroid_m"]], "box": place_box(entry)}
                if kind in CONTINUITY_KINDS:
                    self.carriers_before_move[key] = sorted(
                        entity_id for entity_id, identity in identities.items() if identity["key"] == key)
        elif frame_index == self.window_end + 1:
            for key, kind in self.interventions.items():
                if kind == "remove":
                    continue
                entry = tracker_truth.get(key)
                _require(entry is not None and entry["present"] is True, f"intervened_object_unjudgeable:{key}:absent_after_the_window")
                self.new_place[key] = {"centroid_m": [float(v) for v in entry["centroid_m"]], "box": place_box(entry)}

    def _expectation(self, key: str) -> dict[str, Any]:
        kind = EXPECTATION_KIND[self.interventions[key]]
        record: dict[str, Any] = {"kind": kind}
        if kind in ("removed", "moved"):
            record["old_centroid_m"] = list(self.old_place[key]["centroid_m"])
        if kind in ("added", "moved"):
            record["new_centroid_m"] = list(self.new_place[key]["centroid_m"])
        return record

    def _existence_labels(self, memory_before: Mapping[str, Any], candidates: Sequence[str],
                          object_state: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
        """S0-04 existence labels, with the structural rule applied first."""

        by_id = {str(entity["entity_id"]): entity for entity in memory_before["entities"]}
        labels: dict[str, dict[str, Any]] = {}
        remaining: list[str] = []
        for entity_id in candidates:
            _require(entity_id in by_id, f"existence_candidate_unknown:{entity_id}")
            identity = lt.entity_identity(by_id[entity_id], self.evidence)
            if identity["resolvable"] and lt.structural_type_of(identity["key"]) in lt.STRUCTURAL_TYPES_EXCLUDED:
                labels[entity_id] = {"status": "present", "key": identity["key"], "reason": "structural_never_intervened", "displacement_m": None}
            else:
                remaining.append(entity_id)
        labels.update(lt.existence_labels(memory_before, candidates=remaining, object_state=object_state,
                                          evidence_instance=self.evidence, delta_moved_m=self.policy["delta_moved_m"]))
        return {entity_id: labels[entity_id] for entity_id in candidates}

    # -- one frame -----------------------------------------------------------

    def label_frame(
        self, step: Mapping[str, Any], *, cache_frame: Mapping[str, Any], private_record: Mapping[str, Any],
        masks: Mapping[str, Any], label_image: Any, runtime_s: float, peak_memory_bytes: int,
    ) -> dict[str, Any]:
        """Labels, decomposition, per-frame metric inputs and the training record of one runner step."""

        receipt = step["receipt"]
        stage_a, stage_b = step["stage_a"], step["stage_b"]
        memory_before, memory_after = step["memory_before"], step["state"]["memory"]
        frame_index = int(receipt["tick"]) - 1
        _require(frame_index == self.last_frame_index + 1, "private_record_out_of_order")
        _require(int(private_record.get("observation_index", -1)) == frame_index, "private_record_out_of_order")
        _require(str(private_record.get("frame_digest")) == str(receipt["frame_digest"]) == str(cache_frame["frame_digest"]),
                 "private_record_out_of_order:frame_digest")
        # the gate: the receipt's two seals must be the ones the step carries; nothing private opens otherwise
        gate = lt.build_private_gate(stage_a, stage_b)
        _require(gate == receipt["private_gate"], "private_gate_invalid")
        _require(gate["stage_a_seal_sha256"] == receipt["stage_a_seal_sha256"]
                 and gate["stage_b_seal_sha256"] == receipt["stage_b_seal_sha256"], "private_gate_invalid")
        self.last_frame_index = frame_index

        # private truth of the frame
        tracker_truth = self.tracker.update(frame_index, private_record)
        try:
            truth_table = self.builder.update(private_record, tracker_truth)
        except lr.LeanRunnerError as exc:
            raise LeanEvaluationError(str(exc)) from exc
        instances = fragment_instances(cache_frame, masks, label_image, object_of_label(private_record))
        object_state = object_state_from_truth(tracker_truth)

        # S0-04 labels on the sealed rows
        targets = lt.association_targets(memory_before, recall=stage_a["recall"], fragment_instance=instances,
                                         evidence_instance=self.evidence, dominance_min_share=self.policy["dominance_min_share"])
        for fragment_id, target in targets.items():
            self.evidence[f"{receipt['frame_digest']}|{fragment_id}"] = target["key"]
        candidates = [str(item) for item in receipt["existence"]["candidates"]]
        existence = self._existence_labels(memory_before, candidates, object_state)
        decisions = {str(k): str(v) for k, v in receipt["existence"]["decisions"].items()}
        assignment = {str(k): str(v) for k, v in receipt["assignment"].items()}
        decomposition = lt.decompose_frame(targets=targets, assignment=assignment, existence=existence, decisions=decisions)

        # per-frame metric inputs on the committed memory
        frame_eval = lt.evaluate_frame(memory_after, truth_objects=truth_table, evidence_instance=self.evidence,
                                       iou_min=self.iou_min, delta_moved_m=self.policy["delta_moved_m"])
        false_retract = lt.false_retract_rate(existence, decisions)
        size = lt.size_and_cost(memory_after, runtime_per_frame_s=runtime_s, peak_memory_bytes=peak_memory_bytes)

        # intervention bookkeeping (old/new places, carriers, observability, MRR, recovery, continuity)
        self._snapshot_places(frame_index, tracker_truth, memory_after)
        missing_frame: dict[str, Any] | None = None
        recovery_flags: dict[str, dict[str, bool]] | None = None
        continuity_frame: dict[str, Any] | None = None
        if self._after_window(frame_index):
            samples, minimum = self.policy["entity_geometry_samples_per_axis"], self.policy["should_be_visible_min_ratio"]
            observable_old = {key: place_observable(cache_frame, self.old_place[key]["box"], samples_per_axis=samples, visible_min_ratio=minimum)
                              for key in self.interventions}
            observable_new = {key: place_observable(cache_frame, self.new_place[key]["box"], samples_per_axis=samples, visible_min_ratio=minimum)
                              for key in self.new_place}
            for key, seen in observable_old.items():
                if seen and self.interventions[key] in MISSING_KINDS:
                    self.old_place_observable_since.add(key)
            missing_objects = {
                key: {"old_centroid_m": list(self.old_place[key]["centroid_m"]),
                      "old_place_observable_since_intervention": key in self.old_place_observable_since}
                for key, kind in self.interventions.items() if kind in MISSING_KINDS
            }
            missing_frame = lt.missing_residual_rate(memory_after, evidence_instance=self.evidence, missing_objects=missing_objects,
                                                     delta_moved_m=self.policy["delta_moved_m"])
            recovery_flags = {}
            for key, kind in self.interventions.items():
                place = RECOVERY_PLACE_RULE[EXPECTATION_KIND[kind]]
                observable = {"old_place": observable_old[key], "new_place": observable_new.get(key, False),
                              "old_place_or_new_place": observable_old[key] or observable_new.get(key, False)}[place]
                correct = lt.object_memory_correct(memory_after, evidence_instance=self.evidence, key=key,
                                                   expectation=self._expectation(key), delta_moved_m=self.policy["delta_moved_m"])
                recovery_flags[key] = {"observable": bool(observable), "correct": bool(correct)}
            self.recovery_frames.append(recovery_flags)
            reobserved: dict[str, str] = {}
            for key, kind in self.interventions.items():
                if kind not in CONTINUITY_KINDS or key in self.reobserved_at:
                    continue
                hits = [fragment_id for fragment_id, target in targets.items() if target["key"] == key]
                if hits:
                    ranked = sorted(hits, key=lambda fid: (-float(targets[fid]["share"]) * instances[fid]["pixel_count"],
                                                          -instances[fid]["pixel_count"], fid))
                    reobserved[key] = ranked[0]
                    self.reobserved_at[key] = frame_index
            if reobserved:
                continuity_frame = lt.identity_continuity(reobserved=reobserved, carriers_before_move=self.carriers_before_move,
                                                          assignment=assignment)
                for name in ("kept", "judged", "no_prior_carrier"):
                    self.continuity[name] += int(continuity_frame[name])
                continuity_frame["reobserved"] = dict(reobserved)

        # the S2-03 training record: existence rows are the runner's eligible candidates only
        rows_by_id = {str(row["entity_id"]): row for row in stage_b["existence_rows"]}
        training_record = lean_model.validate_training_record({
            "stage_a": stage_a, "targets": targets,
            "existence_rows": [rows_by_id[entity_id] for entity_id in candidates],
            "existence_feature_order": list(stage_b["existence_feature_order"]),
            "existence_labels": {entity_id: {"status": label["status"]} for entity_id, label in existence.items()},
        })
        meta = {**self.nuisance_meta, "frame_index": frame_index}
        nuisance = {
            "association": [{**meta, "association_status": target["status"],
                             "association_target_is_birth": bool(target["target"] is not None and str(target["target"]).startswith(lt.BIRTH_COLUMN_PREFIX))}
                            for target in (targets[fid] for fid in sorted(targets))],
            "existence": [{**meta, "existence_status": existence[entity_id]["status"]} for entity_id in sorted(existence)],
        }
        record = {
            "tick": int(receipt["tick"]), "frame_index": frame_index, "frame_digest": str(receipt["frame_digest"]),
            "private_gate": gate, "targets": targets, "existence_labels": existence, "decomposition": decomposition,
            "node_prf1": {name: frame_eval[name] for name in lt.METRIC_FIELDS["node_prf1"]},
            "contamination_fraction": frame_eval["contamination_fraction"],
            "stale_entities": frame_eval["stale_entities"], "wrongly_absent_objects": frame_eval["wrongly_absent_objects"],
            "out_of_scope_entities": frame_eval["out_of_scope_entities"],
            "identity_ambiguous_entities": frame_eval["identity_ambiguous_entities"],
            "false_retract": false_retract, "size_and_cost": size,
            "missing_residual": missing_frame, "recovery_flags": recovery_flags, "identity_continuity": continuity_frame,
            "truth_in_scope": sorted(key for key, row in truth_table.items() if row["present"] and row["in_scope"]),
            "training_record": training_record, "nuisance": nuisance,
        }
        self.frames.append({k: v for k, v in record.items() if k not in ("training_record", "nuisance", "targets", "existence_labels")})
        return record

    # -- the episode -----------------------------------------------------------

    def episode_report(self) -> dict[str, Any]:
        """The seven metrics with exactly the frozen fields, plus diagnostics outside the report."""

        _require(bool(self.frames), "episode_without_frames")
        frames = self.frames
        matched = sum(int(f["node_prf1"]["matched"]) for f in frames)
        predicted = sum(int(f["node_prf1"]["predicted"]) for f in frames)
        truth = sum(int(f["node_prf1"]["truth"]) for f in frames)
        precision = matched / predicted if predicted else None
        recall = matched / truth if truth else None
        if precision is None or recall is None:
            f1 = None
        elif precision + recall == 0.0:
            f1 = 0.0
        else:
            f1 = 2.0 * precision * recall / (precision + recall)
        false_retracts = sum(int(f["false_retract"]["false_retracts"]) for f in frames)
        judged_retracts = sum(int(f["false_retract"]["judged_retracts"]) for f in frames)
        ambiguous_retracts = sum(int(f["false_retract"]["ambiguous_retracts"]) for f in frames)
        last_missing = next((f["missing_residual"] for f in reversed(frames) if f["missing_residual"] is not None), None)
        recovery = lt.episode_recovery_latency(self.recovery_frames)
        contamination = lt.contamination_auc([f["contamination_fraction"] for f in frames])
        count = len(frames)
        report = {
            "node_prf1": {"node_precision": precision, "node_recall": recall, "node_f1": f1,
                          "matched": matched, "predicted": predicted, "truth": truth},
            "missing_residual_rate": (
                {name: last_missing[name] for name in lt.METRIC_FIELDS["missing_residual_rate"]} if last_missing is not None
                else {"missing_residual_rate": None, "residual": 0, "judged": 0, "not_yet_observable": 0}),
            "false_retract_rate": {"false_retract_rate": (false_retracts / judged_retracts) if judged_retracts else None,
                                   "false_retracts": false_retracts, "judged_retracts": judged_retracts,
                                   "ambiguous_retracts": ambiguous_retracts},
            "identity_continuity": {"identity_continuity": (self.continuity["kept"] / self.continuity["judged"]) if self.continuity["judged"] else None,
                                    "kept": self.continuity["kept"], "judged": self.continuity["judged"],
                                    "no_prior_carrier": self.continuity["no_prior_carrier"]},
            "recovery_latency_frames": {name: recovery[name] for name in lt.METRIC_FIELDS["recovery_latency_frames"]},
            "contamination_auc": {name: contamination[name] for name in lt.METRIC_FIELDS["contamination_auc"]},
            "size_and_cost": {
                "active_entity_count": sum(f["size_and_cost"]["active_entity_count"] for f in frames) / count,
                "lifecycle_version_count": sum(f["size_and_cost"]["lifecycle_version_count"] for f in frames) / count,
                "runtime_per_frame_s": sum(f["size_and_cost"]["runtime_per_frame_s"] for f in frames) / count,
                "peak_memory_bytes": max(int(f["size_and_cost"]["peak_memory_bytes"]) for f in frames),
            },
        }
        lt.assert_report_keys(report)
        totals = {name: 0 for name in ("recall_miss", "teacher_error", "amortization_error", "correct", "unlabelled", "duplicate_of_labelled", "decisions")}
        for f in frames:
            for name in totals:
                totals[name] += int(f["decomposition"]["totals"][name])
        diagnostics = {
            "arm": self.arm, "frames": count, "window_end": self.window_end,
            "interventions": dict(self.interventions),
            "decomposition_totals": totals,
            "missing_residual_series": [None if f["missing_residual"] is None else f["missing_residual"]["missing_residual_rate"] for f in frames],
            "contamination_series": [f["contamination_fraction"] for f in frames],
            "old_place_observable_since_intervention": sorted(self.old_place_observable_since),
            "reobserved_at": dict(self.reobserved_at),
            "carriers_before_move": dict(self.carriers_before_move),
            "recovery": {name: recovery[name] for name in ("recovered", "unrecovered", "never_observable", "per_object")},
        }
        return {"report": report, "diagnostics": diagnostics}


def nuisance_probes(frame_records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The S0-04 probes over every labelled row of an episode (or a split): association and existence rows separately."""

    association = [row for record in frame_records for row in record["nuisance"]["association"]]
    existence = [row for record in frame_records for row in record["nuisance"]["existence"]]
    out: dict[str, Any] = {"association_rows": len(association), "existence_rows": len(existence)}
    out["association"] = lt.run_nuisance_probes(association, labels=NUISANCE_ASSOCIATION_LABELS) if len(association) >= 2 else None
    out["existence"] = lt.run_nuisance_probes(existence, labels=NUISANCE_EXISTENCE_LABELS) if len(existence) >= 2 else None
    advantages = [block["largest_advantage"] for block in (out["association"], out["existence"])
                  if block is not None and block["largest_advantage"] is not None]
    out["largest_advantage"] = max(advantages) if advantages else None
    return out


def headline_values(report: Mapping[str, Mapping[str, Any]]) -> dict[str, float | None]:
    """The scalar per metric a house-level table pairs on (size_and_cost is reported, never paired)."""

    lt.assert_report_keys(report)
    return {metric: report[metric][field] for metric, field in HEADLINE_FIELD.items() if metric in report}


# --------------------------------------------------------------------------
# 3. machine contract
# --------------------------------------------------------------------------

def validate_evaluation_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Check that the S2-04 machine contract agrees with this implementation."""

    _require(type(contract) is dict, "contract_not_object")
    _require(contract.get("schema_version") == CONTRACT_SCHEMA_VERSION, "contract_schema_version_invalid")
    _require(contract.get("decision_id") == "D-224", "contract_decision_id_invalid")
    _require(contract.get("stage_id") == STAGE_ID, "contract_stage_id_invalid")
    rules = contract["derivation_rules"]
    for name, expected in (
        ("place_observable", PLACE_OBSERVABLE_RULE), ("old_place", OLD_PLACE_RULE), ("new_place", NEW_PLACE_RULE),
        ("carriers_before_move", CARRIERS_BEFORE_MOVE_RULE), ("first_labelled_reobservation", REOBSERVATION_RULE),
        ("evidence_instance", EVIDENCE_INSTANCE_RULE), ("structural_existence", STRUCTURAL_EXISTENCE_RULE),
        ("missing_residual_headline", MRR_HEADLINE_RULE), ("training_record", TRAINING_RECORD_RULE),
        ("nuisance_records", NUISANCE_RECORD_RULE),
    ):
        _require(rules[name] == expected, f"contract_rule_mismatch:{name}")
    _require(dict(rules["recovery_place"]) == RECOVERY_PLACE_RULE, "contract_rule_mismatch:recovery_place")
    _require(tuple(rules["missing_residual_kinds"]) == MISSING_KINDS and tuple(rules["identity_continuity_kinds"]) == CONTINUITY_KINDS,
             "contract_rule_mismatch:metric_kinds")
    for name in ("private_truth_opens_only_against_the_step_receipt_gate", "no_public_byte_is_read_or_written",
                 "labels_metrics_and_statistics_are_the_s0_04_functions_unchanged", "masks_are_digest_checked_against_the_sealed_frame"):
        _require(rules[name] is True, f"contract_claim_weakened:{name}")
    _require(dict(contract["policy_input_sources"]) == POLICY_INPUT_SOURCES, "contract_policy_sources_mismatch")
    _require(tuple(contract["failure_reasons"]) == FAILURE_REASONS, "contract_failure_reasons_mismatch")
    _require(dict(contract["headline_fields"]) == HEADLINE_FIELD, "contract_headline_fields_mismatch")
    _require(contract["policy_values_without_defaults"] == [] and contract["registered_value_slots"] == [],
             "contract_registers_a_value_slot_it_does_not_own")
    policy = contract.get("activation_policy")
    opened = set(policy["active_true_authorizations"]) if policy else set()
    if policy:
        _require(type(policy.get("opened_by")) is str and bool(policy["opened_by"]), "contract_activation_policy_names_no_ruling")
    for name, value in contract["authorization"].items():
        _require(type(value) is bool, f"contract_authorization_not_boolean:{name}")
        _require(value is False or name in opened, f"contract_bit_opened_without_a_ruling:{name}")
    return clone_json(dict(contract))


__all__ = [
    "CARRIERS_BEFORE_MOVE_RULE",
    "CONTINUITY_KINDS",
    "CONTRACT_SCHEMA_VERSION",
    "EVIDENCE_INSTANCE_RULE",
    "EXPECTATION_KIND",
    "EpisodeTeacher",
    "FAILURE_REASONS",
    "HEADLINE_FIELD",
    "INTERVENTION_KINDS",
    "LeanEvaluationError",
    "MISSING_KINDS",
    "MRR_HEADLINE_RULE",
    "NEW_PLACE_RULE",
    "NUISANCE_RECORD_RULE",
    "OLD_PLACE_RULE",
    "PLACE_OBSERVABLE_RULE",
    "POLICY_FIELDS",
    "POLICY_INPUT_SOURCES",
    "RECOVERY_PLACE_RULE",
    "REOBSERVATION_RULE",
    "STAGE_ID",
    "STRUCTURAL_EXISTENCE_RULE",
    "TRAINING_RECORD_RULE",
    "fragment_instances",
    "headline_values",
    "nuisance_probes",
    "object_of_label",
    "object_state_from_truth",
    "place_box",
    "place_observable",
    "validate_evaluation_contract",
    "validate_policy",
]
