"""D-224 / S2-05: read-only node-matching audit of one episode run (evidence for the pending ruling 70).

Usage:
    python ops/vsmt/lean_s2_05_node_audit.py run --cache-root <S1-03 cache root> --episode-root <S1-02 episode dir> \\
        --geometry-root <S1-04 geometry root> --episode-id <id> --arm LOW --config '{"d_low": null}' \\
        --descriptor vitb14 --weights <reid weights> --output-root <audit root> [--frames N]
    python ops/vsmt/lean_s2_05_node_audit.py merge --output-root <audit root> --arm LOW --results <results/*.json>

The ``run`` subcommand replays exactly what the S2-04 entry does (the S2-01 runner over the sealed
cache, the S2-04 teacher labelling every step behind the two-seal gate) and, after every frame,
decomposes the node precision/recall loss of the committed memory under the IoU matching rule
(max-weight matching on 3D IoU >= 0.3, ruling C; the secondary column node_prf1_iou since ruling 72 (B),
whose primary column is the centroid-within-delta rule, re-scored below as centroid_within_0.5m and
checked against the evaluator) and re-scores the same predictions
under alternative rules that a ruling could pick.  It writes one ``node_audit.json`` per episode
and arm; it writes no label, training record, receipt or contract byte and freezes nothing.
``merge`` pools the audits of one arm into a committed ``results/`` report.  No private key
enters either file: truth-side rows are grouped by the ProcTHOR type prefix and by the
pickupable / receptacle / other group only.

白话：这是给"节点 F1 为什么低"找原因的只读审计，不是新指标、不是新规则。输入和 S2-04 入口完全一样
（冻结 cache、S1-02 的 episode 目录、S1-04 几何表、臂与配置），输出每帧把"记忆里的实体"和"范围内在场
的真值物体"各自分类：实体为什么没匹配上（身份含糊、物体已不在、位置对但框太小、物体被另一个实体
占了），真值物体为什么没被匹配（有同身份实体但框太小、同身份实体离得远、只有身份含糊的实体在附近、
根本没有实体——再分从未出过色块与出过色块但丢了）；并把同一批预测按几种备选口径（IoU 0.1、IoU>0、
质心落在真值框内、质心 0.5 m 内、按私有身份并框后的 IoU 0.3 上界）重新计分。例如某帧 48 个实体里
41 个身份含糊、64 个真值物体里 62 个附近没有任何实体，就说明问题主要在记忆而不在匹配口径。它不改
任何合同或数值，产物只用于裁决 70 的讨论；按身份并框的上界用了私有身份，只能作诊断列，不是方法。

v2（裁决 76 (1)(a)）再加三块只读统计与两列：质心主列自己的分类账（"离得远"拆成物体真被搬动、物体没动两类）；
每次 BIRTH 的原因（首次出现、没有承载实体、正确实体没被召回、召回了但 logit 不过新建线——TAF 即余弦低于 θ_a、
合格却在联合分配里输了），用同一个 logit 函数在封存行上重算；每个去重时刻，去重之后剩下的实体对按状态组合
（active／dormant）与私有身份（同物体／不同物体／含糊）在余弦、距离、IoU 各档下能过几对——同物体对是还能收回
的重复，不同物体对是误合并风险；以及两列"先最大匹配数、再最大权"的匹配数。按身份并框那两列只是分组诊断，
同时改了数量与几何，不是上界（LOG-262）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
for item in (ROOT / "src", HERE.parent):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from vsmt import lean_teacher as lt  # noqa: E402

AUDIT_FILE_NAME = "node_audit.json"
SCHEMA_VERSION = "vsmt-s2-05-node-audit-v2"  # v2: ruling 76 (1)(a) centroid ledger, birth reasons, dedup tallies, count-first columns

#: Why an in-memory prediction (an entity in ``active``/``dormant`` whose object is not a present
#: out-of-scope one) did not match under the IoU 0.3 column (the primary column until ruling 72 (B), secondary since).
ENTITY_CATEGORIES = (
    "matched",
    "identity_ambiguous_unmatched",          # no strict majority over its keyed evidence, and no IoU match either
    "own_object_absent_stale",               # resolves to an object that is no longer present
    "own_object_far_stale_location",         # resolves to a present object but sits more than delta away from it
    "own_object_near_box_too_small",         # within delta of its object, IoU with the truth box below the threshold
    "own_object_taken_by_another_entity",    # IoU with its own object passes, another entity holds the match
)
#: Why a present in-scope truth object was not matched under the IoU 0.3 column (secondary since ruling 72 (B)).
TRUTH_CATEGORIES = (
    "matched",
    "resolved_entity_near_but_box_too_small",  # an entity of its identity within delta, IoU below the threshold
    "resolved_entity_far",                     # entities of its identity exist, all more than delta away
    "only_ambiguous_entity_near",              # no entity of its identity; an ambiguous entity within delta
    "no_entity_fragmented_before",             # no entity near; the object did produce a labelled fragment earlier
    "no_entity_never_fragmented",              # no entity near; the front end never produced a fragment of it
)
#: Alternative scorings of the same predictions and truth objects, each with the evaluator's matcher.
RULES = (
    "iou_0.3_secondary",
    "iou_0.1",
    "iou_positive",
    "centroid_inside_truth_box_padded_0.25m",
    "centroid_within_0.5m",
    "oracle_identity_groups_iou_0.3",
    "oracle_identity_groups_centroid_within_0.5m",
    # ruling 76 (1)(a): the same two columns under the count-first objective (most matches, then most weight);
    # since ruling 76 (3)(a) these two reproduce the evaluator and the plain two above keep the earlier max-weight objective
    "centroid_within_0.5m_count_first",
    "iou_0.3_count_first",
    # metric candidates for the pending node-metric ruling (read-only): large objects whose visible surface centroid sits
    # more than 0.5 m from the whole-box centre, and a pair that must also be the entity's own object
    "centroid_0.5m_or_in_box_0.25m_count_first",
    "identity_centroid_0.5m_count_first",
    "identity_centroid_0.5m_or_in_box_0.25m_count_first",
)
PAD_M = 0.25
CENTROID_RADIUS_M = 0.5

#: Ruling 76 (1)(a): why an in-memory prediction did not match under the primary centroid column.
CENTROID_ENTITY_CATEGORIES = (
    "matched",
    "identity_ambiguous_unmatched",
    "own_object_absent",                       # resolves to an object no longer present
    "own_object_far_object_moved",             # more than delta from its object, which moved more than delta since the entity last saw it
    "own_object_far_object_not_moved",         # more than delta from its object, which has not moved: surface centroid off the box centre, or a wrong bind
    "own_object_near_unmatched",               # within delta of its object, another entity (or the matcher) took the match
)
#: Ruling 76 (1)(a): why a present in-scope truth object was not matched under the primary centroid column.
CENTROID_TRUTH_CATEGORIES = (
    "matched",
    "resolved_entity_near_unmatched",
    "resolved_entity_far",
    "only_ambiguous_entity_near",
    "no_entity_fragmented_before",
    "no_entity_never_fragmented",
)
#: Ruling 76 (1)(a): why a fragment was born, from the sealed stage-A rows and the arm's own logits.
BIRTH_REASONS = (
    "unlabelled_fragment",                 # the fragment has no dominant private object
    "first_labelled_observation",          # no earlier fragment of this object
    "no_resolved_carrier",                 # the object was fragmented before, but no entity resolves to it now
    "correct_carrier_not_recalled",        # an entity resolves to it but is not among the sealed candidates
    "correct_carrier_below_birth_logit",   # recalled, but its association logit does not beat the birth logit (TAF: cosine below theta_a)
    "correct_carrier_lost_joint_competition",  # recalled and eligible, the joint solve still chose birth
)
#: Ruling 76 (1)(a): the dedup gate values tallied over entity pairs at every dedup tick (the frozen ones are 0.8 / 0.5 / 0.05).
DEDUP_COSINES = (0.5, 0.6, 0.7, 0.8, 0.9)
DEDUP_DISTANCES_M = (0.25, 0.5, 1.0)
DEDUP_IOUS = (0.0, 0.05, 0.1)
DEDUP_STATE_PAIRS = ("active_active", "active_dormant", "dormant_dormant")
DEDUP_IDENTITIES = ("same_object", "different_objects", "ambiguous")


def _count_first(weights: Sequence[Sequence[float]]) -> int:
    """Matches under the count-first objective (ruling 76 (3)(a), the evaluator's own since then)."""

    if not weights or not weights[0]:
        return 0
    return len(lt._max_weight_matching(weights, count_first=True))


class NodeAuditError(ValueError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise NodeAuditError(code)


_distance = lt._distance  # the evaluator's own distance, so the centroid rule reproduces its column bit for bit


def _inside_padded(point: Sequence[float], lower: Sequence[float], upper: Sequence[float], pad: float) -> bool:
    return all(float(lo) - pad <= float(p) <= float(hi) + pad for p, lo, hi in zip(point, lower, upper, strict=True))


def _union(boxes: Sequence[tuple[Sequence[float], Sequence[float]]]) -> tuple[list[float], list[float]]:
    lower = [min(float(b[0][axis]) for b in boxes) for axis in range(3)]
    upper = [max(float(b[1][axis]) for b in boxes) for axis in range(3)]
    return lower, upper


def _prf(matched: int, predicted: int, truth: int) -> dict[str, Any]:
    precision = matched / predicted if predicted else None
    recall = matched / truth if truth else None
    if precision is None or recall is None:
        f1 = None
    elif precision + recall == 0.0:
        f1 = 0.0
    else:
        f1 = 2.0 * precision * recall / (precision + recall)
    return {"matched": matched, "predicted": predicted, "truth": truth, "precision": precision, "recall": recall, "f1": f1}


def object_groups(geometry_table: Mapping[str, Any]) -> dict[str, str]:
    """pickupable / receptacle / other per private key, from the S1-04 geometry table rows."""

    groups: dict[str, str] = {}
    for row in geometry_table["objects"]:
        groups[str(row["object_id"])] = "pickupable" if row.get("pickupable") else ("receptacle" if row.get("receptacle") else "other")
    return groups


def capture_truth_table(teacher: Any) -> dict[str, Any]:
    """Make the teacher's truth-table builder hand back the table it built for the latest frame.

    The wrapper returns the builder's own table unchanged; the teacher's behaviour is not altered.
    """

    captured: dict[str, Any] = {}
    original: Callable[..., dict[str, dict[str, Any]]] = teacher.builder.update

    def capturing_update(private_record: Mapping[str, Any], tracker_truth: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
        table = original(private_record, tracker_truth)
        captured["table"] = table
        return table

    teacher.builder.update = capturing_update
    return captured


def capture_dedup_folds() -> list[dict[str, Any]]:
    """Ruling 76 (1)(a): record the two records of every shared-dedup fold as they were just before it.

    The wrapper calls the shared maintenance function unchanged and returns its result; it only keeps, per
    fold, the two records' states and evidence so the audit can file the fold by private identity once the
    teacher has labelled the frame.  Nothing reaches the method.
    """

    from vsmt import lean_memory as lm

    captured: list[dict[str, Any]] = []
    original = lm._apply_dedup
    if getattr(original, "_audit_wrapper", False):
        original = original._audit_original  # type: ignore[attr-defined]

    def capturing(memory: dict[str, Any], **kwargs: Any) -> list[dict[str, Any]]:
        before = {str(e["entity_id"]): {"state": e["state"], "evidence": [dict(item) for item in e["evidence"]], "supported_by": e.get("supported_by")}
                  for e in memory["entities"]}
        changes = original(memory, **kwargs)
        for change in changes:
            captured.append({"canonical": before[str(change["canonical_entity_id"])], "folded": before[str(change["folded_entity_id"])]})
        return changes

    capturing._audit_wrapper = True  # type: ignore[attr-defined]
    capturing._audit_original = original  # type: ignore[attr-defined]
    lm._apply_dedup = capturing
    return captured


class NodeAudit:
    """Per-frame loss decomposition and alternative scorings over one episode run."""

    def __init__(self, *, evidence: Mapping[str, str | None], iou_min: float, delta_moved_m: float,
                 groups: Mapping[str, str] | None = None, arm: str | None = None, config: Mapping[str, Any] | None = None,
                 scorer: Any = None, dedup: Mapping[str, Any] | None = None) -> None:
        self.evidence = evidence
        # ruling 76 (1)(a): the birth reasons need the arm's logits, the dedup tallies the frozen period
        self.arm = arm
        self.config = dict(config) if config is not None else None
        self.scorer = scorer
        self.dedup_period = int(dedup["period_ticks"]) if dedup else None
        self.centroid_entity_counts = {name: 0 for name in CENTROID_ENTITY_CATEGORIES}
        self.centroid_truth_counts = {name: 0 for name in CENTROID_TRUTH_CATEGORIES}
        self.birth_reasons = {scope: {name: 0 for name in BIRTH_REASONS} for scope in ("in_scope_object", "other")}
        self.dedup_ticks = 0
        self.dedup_folds = 0
        self.dedup_pairs = {f"{states}|{identity}": {"pairs": 0, "pass": {}} for states in DEDUP_STATE_PAIRS for identity in DEDUP_IDENTITIES}
        self.truth_centroid_changes: dict[str, list[tuple[int, list[float]]]] = {}
        self.fold_capture: list[dict[str, Any]] | None = None  # set by run(): capture_dedup_folds()
        self.folds_by_identity = {f"{states}|{identity}": 0 for states in DEDUP_STATE_PAIRS for identity in DEDUP_IDENTITIES}
        self.iou_min = float(iou_min)
        self.delta = float(delta_moved_m)
        self.groups = dict(groups or {})
        self.frames = 0
        self.entity_counts = {name: 0 for name in ENTITY_CATEGORIES}
        self.truth_counts = {name: 0 for name in TRUTH_CATEGORIES}
        self.rule_sums = {rule: {"matched": 0, "predicted": 0, "truth": 0} for rule in RULES}
        self.wrong_identity_matches = {rule: 0 for rule in RULES if rule.endswith("_count_first")}
        self.rule_matched_per_frame: dict[str, list[int]] = {rule: [] for rule in RULES}
        self.by_type: dict[str, dict[str, int]] = {}
        self.by_group: dict[str, dict[str, int]] = {}
        self.keys_fragmented: set[str] = set()
        self.in_memory_per_frame: list[int] = []
        self.out_of_scope_per_frame: list[int] = []
        self.own_iou_near_values: list[float] = []   # IoU of a resolved entity within delta of its present object
        self.own_distance_values: list[float] = []   # centroid distance of a resolved entity to its present object

    # -- one frame --------------------------------------------------------------

    def observe(self, step: Mapping[str, Any], labelled: Mapping[str, Any], truth_table: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
        memory_after = step["state"]["memory"]
        self._keys_before_frame = set(self.keys_fragmented)  # ruling 76 (1)(a): "first observation" means before this frame
        for target in labelled["targets"].values():
            if target.get("key") is not None:
                self.keys_fragmented.add(str(target["key"]))
        frame_eval = lt.evaluate_frame(memory_after, truth_objects=truth_table, evidence_instance=self.evidence,
                                       iou_min=self.iou_min, delta_moved_m=self.delta)
        for name in lt.METRIC_FIELDS["node_prf1"]:
            _require(frame_eval[name] == labelled["node_prf1"][name], f"audit_disagrees_with_the_labels:{name}")
        identities = lt.entity_identities(memory_after, self.evidence)
        out_of_scope = set(frame_eval["out_of_scope_entities"])
        in_memory = [e for e in memory_after["entities"] if e["state"] in lt.MEMORY_PRESENT_STATES]
        predictions = [e for e in in_memory if str(e["entity_id"]) not in out_of_scope]
        present_keys = [key for key in sorted(truth_table) if truth_table[key]["present"] and truth_table[key]["in_scope"]]
        _require(len(predictions) == frame_eval["predicted"] and len(present_keys) == frame_eval["truth"], "audit_prediction_sets_differ")
        # the categories decompose the IoU 0.3 column's loss ("box too small" only means something there)
        matched_entity = {entity_id: key for entity_id, key in frame_eval["iou_matched_pairs"]}
        matched_keys = set(matched_entity.values())
        boxes = {key: (truth_table[key]["aabb_min_m"], truth_table[key]["aabb_max_m"], truth_table[key]["centroid_m"]) for key in present_keys}

        # matrices over predictions x present keys
        iou_rows: list[list[float]] = []
        dist_rows: list[list[float]] = []
        inside_rows: list[list[bool]] = []
        for entity in predictions:
            iou_rows.append([lt._aabb_iou(entity["aabb_min_m"], entity["aabb_max_m"], boxes[key][0], boxes[key][1]) for key in present_keys])
            dist_rows.append([_distance(entity["centroid_m"], boxes[key][2]) for key in present_keys])
            inside_rows.append([_inside_padded(entity["centroid_m"], boxes[key][0], boxes[key][1], PAD_M) for key in present_keys])
        column_of = {key: index for index, key in enumerate(present_keys)}

        # entity-side categories
        resolving: dict[str, list[int]] = {key: [] for key in present_keys}
        ambiguous_rows: list[int] = []
        frame_entity = {name: 0 for name in ENTITY_CATEGORIES}
        for row, entity in enumerate(predictions):
            entity_id = str(entity["entity_id"])
            identity = identities[entity_id]
            if entity_id in matched_entity:
                category = "matched"
                if identity["resolvable"] and identity["key"] in resolving:
                    resolving[identity["key"]].append(row)
                elif not identity["resolvable"]:
                    ambiguous_rows.append(row)
            elif not identity["resolvable"]:
                category = "identity_ambiguous_unmatched"
                ambiguous_rows.append(row)
            else:
                key = identity["key"]
                if key not in column_of:  # present out-of-scope objects were filtered; only absent ones remain
                    _require(truth_table[key]["present"] is not True, f"audit_unexpected_key_state:{key}")
                    category = "own_object_absent_stale"
                else:
                    resolving[key].append(row)
                    column = column_of[key]
                    own_iou, own_distance = iou_rows[row][column], dist_rows[row][column]
                    self.own_distance_values.append(own_distance)
                    if own_iou >= self.iou_min:
                        category = "own_object_taken_by_another_entity"
                    elif own_distance <= self.delta:
                        category = "own_object_near_box_too_small"
                        self.own_iou_near_values.append(own_iou)
                    else:
                        category = "own_object_far_stale_location"
            frame_entity[category] += 1
        # truth-side categories
        frame_truth = {name: 0 for name in TRUTH_CATEGORIES}
        for key in present_keys:
            column = column_of[key]
            if key in matched_keys:
                category = "matched"
            elif resolving[key]:
                near = any(dist_rows[row][column] <= self.delta for row in resolving[key])
                category = "resolved_entity_near_but_box_too_small" if near else "resolved_entity_far"
            elif any(dist_rows[row][column] <= self.delta for row in ambiguous_rows):
                category = "only_ambiguous_entity_near"
            elif key in self.keys_fragmented:
                category = "no_entity_fragmented_before"
            else:
                category = "no_entity_never_fragmented"
            frame_truth[category] += 1
            type_row = self.by_type.setdefault(lt.structural_type_of(key), {name: 0 for name in TRUTH_CATEGORIES})
            type_row[category] += 1
            group_row = self.by_group.setdefault(self.groups.get(key, "other"), {name: 0 for name in TRUTH_CATEGORIES})
            group_row[category] += 1

        # alternative rules on the same predictions
        rule_matched: dict[str, int] = {}
        rule_predicted: dict[str, int] = {}
        threshold = self.iou_min
        weights_by_rule = {
            "iou_0.3_secondary": [[v if v >= threshold else 0.0 for v in row] for row in iou_rows],
            "iou_0.1": [[v if v >= 0.1 else 0.0 for v in row] for row in iou_rows],
            "iou_positive": [[v if v > 0.0 else 0.0 for v in row] for row in iou_rows],
            "centroid_inside_truth_box_padded_0.25m": [[(1.0 / (1.0 + d)) if inside else 0.0 for d, inside in zip(drow, irow, strict=True)]
                                                       for drow, irow in zip(dist_rows, inside_rows, strict=True)],
            # = the primary column node_prf1 since ruling 72 (B) (delta_moved_m is the frozen 0.5 m); checked against the evaluator below
            "centroid_within_0.5m": [[(1.0 / (1.0 + d)) if d <= self.delta else 0.0 for d in row] for row in dist_rows],
        }
        # oracle grouping by private identity: one union box per resolved key, ambiguous entities stay single
        groups: dict[str, list[int]] = {}
        for row, entity in enumerate(predictions):
            identity = identities[str(entity["entity_id"])]
            name = f"key:{identity['key']}" if identity["resolvable"] else f"entity:{entity['entity_id']}"
            groups.setdefault(name, []).append(row)
        group_iou: list[list[float]] = []
        group_dist: list[list[float]] = []
        for rows in groups.values():
            lower, upper = _union([(predictions[r]["aabb_min_m"], predictions[r]["aabb_max_m"]) for r in rows])
            centre = [(a + b) / 2.0 for a, b in zip(lower, upper, strict=True)]
            group_iou.append([lt._aabb_iou(lower, upper, boxes[key][0], boxes[key][1]) for key in present_keys])
            group_dist.append([_distance(centre, boxes[key][2]) for key in present_keys])
        weights_by_rule["oracle_identity_groups_iou_0.3"] = [[v if v >= threshold else 0.0 for v in row] for row in group_iou]
        weights_by_rule["oracle_identity_groups_centroid_within_0.5m"] = [[(1.0 / (1.0 + d)) if d <= CENTROID_RADIUS_M else 0.0 for d in row]
                                                                          for row in group_dist]
        weights_by_rule["centroid_within_0.5m_count_first"] = weights_by_rule["centroid_within_0.5m"]
        weights_by_rule["iou_0.3_count_first"] = weights_by_rule["iou_0.3_secondary"]
        own = [[bool(identities[str(entity["entity_id"])]["resolvable"]) and identities[str(entity["entity_id"])]["key"] == key
                for key in present_keys] for entity in predictions]
        place_or_box = [[(1.0 / (1.0 + d)) if (d <= self.delta or inside) else 0.0 for d, inside in zip(drow, irow, strict=True)]
                        for drow, irow in zip(dist_rows, inside_rows, strict=True)]
        weights_by_rule["centroid_0.5m_or_in_box_0.25m_count_first"] = place_or_box
        weights_by_rule["identity_centroid_0.5m_count_first"] = [[w if ok else 0.0 for w, ok in zip(wrow, orow, strict=True)]
                                                                 for wrow, orow in zip(weights_by_rule["centroid_within_0.5m"], own, strict=True)]
        weights_by_rule["identity_centroid_0.5m_or_in_box_0.25m_count_first"] = [[w if ok else 0.0 for w, ok in zip(wrow, orow, strict=True)]
                                                                                 for wrow, orow in zip(place_or_box, own, strict=True)]
        for rule in RULES:
            weights = weights_by_rule[rule]
            if rule.endswith("_count_first"):
                pairs = lt._max_weight_matching(weights, count_first=True) if weights and present_keys else []
                matched = len(pairs)
                self.wrong_identity_matches[rule] += sum(1 for row, column in pairs if not own[row][column])
            else:
                matched = len(lt._max_weight_matching(weights)) if weights and present_keys else 0
            rule_matched[rule] = matched
            rule_predicted[rule] = len(weights)
            sums = self.rule_sums[rule]
            sums["matched"] += matched
            sums["predicted"] += len(weights)
            sums["truth"] += len(present_keys)
            self.rule_matched_per_frame[rule].append(matched)
        # ruling 76 (3)(a): the evaluator matches count-first; the plain two columns keep the earlier max-weight objective
        _require(rule_matched["iou_0.3_count_first"] == frame_eval["node_prf1_iou"]["matched"],
                 "audit_iou_rule_does_not_reproduce_the_evaluator")
        # ruling 72 (B): the centroid rule is the primary column node_prf1
        # ruling 77 (1)(a): the primary column is the own-object-and-place candidate
        _require(rule_matched["identity_centroid_0.5m_or_in_box_0.25m_count_first"] == frame_eval["matched"],
                 "audit_centroid_rule_does_not_reproduce_the_evaluator")

        # ruling 76 (1)(a): the primary centroid column's own ledger, the birth reasons and the dedup pair tallies
        tick = int(memory_after["tick"])
        centroid_ledger = self._centroid_ledger(frame_eval, predictions, identities, present_keys, dist_rows, column_of, truth_table, tick)
        if self.arm is not None:
            self._birth_reasons(step, labelled, truth_table)
        if self.dedup_period is not None and tick % self.dedup_period == 0:
            self._dedup_pairs(memory_after, identities)
        if self.fold_capture is not None:
            self._file_folds()

        for name, count in frame_entity.items():
            self.entity_counts[name] += count
        for name, count in frame_truth.items():
            self.truth_counts[name] += count
        self.frames += 1
        self.in_memory_per_frame.append(len(in_memory))
        self.out_of_scope_per_frame.append(len(out_of_scope))
        return {"frame_index": labelled["frame_index"], "entity": frame_entity, "truth": frame_truth,
                "centroid_entity": centroid_ledger["entity"], "centroid_truth": centroid_ledger["truth"],
                "rules": {rule: {"matched": rule_matched[rule], "predicted": rule_predicted[rule], "truth": len(present_keys)} for rule in RULES}}

    # -- ruling 76 (1)(a) --------------------------------------------------------

    def _truth_centroid_at(self, key: str, tick: int) -> list[float] | None:
        """The object's truth centroid as last recorded at or before ``tick`` (None if never recorded by then)."""

        found = None
        for at, centroid in self.truth_centroid_changes.get(key, []):
            if at > tick:
                break
            found = centroid
        return found

    def _centroid_ledger(self, frame_eval: Mapping[str, Any], predictions: Sequence[Mapping[str, Any]],
                         identities: Mapping[str, Mapping[str, Any]], present_keys: Sequence[str],
                         dist_rows: Sequence[Sequence[float]], column_of: Mapping[str, int],
                         truth_table: Mapping[str, Mapping[str, Any]], tick: int) -> dict[str, dict[str, int]]:
        for key in present_keys:  # record where each present object is, only when it changes
            centroid = [float(v) for v in truth_table[key]["centroid_m"]]
            history = self.truth_centroid_changes.setdefault(key, [])
            if not history or history[-1][1] != centroid:
                history.append((tick, centroid))
        matched_entity = {str(entity_id): key for entity_id, key in frame_eval["matched_pairs"]}
        matched_keys = set(matched_entity.values())
        resolving: dict[str, list[int]] = {key: [] for key in present_keys}
        ambiguous_rows: list[int] = []
        entity_counts = {name: 0 for name in CENTROID_ENTITY_CATEGORIES}
        for row, entity in enumerate(predictions):
            entity_id = str(entity["entity_id"])
            identity = identities[entity_id]
            if not identity["resolvable"]:
                ambiguous_rows.append(row)
            elif identity["key"] in resolving:
                resolving[identity["key"]].append(row)
            if entity_id in matched_entity:
                category = "matched"
            elif not identity["resolvable"]:
                category = "identity_ambiguous_unmatched"
            elif identity["key"] not in column_of:
                category = "own_object_absent"
            elif dist_rows[row][column_of[identity["key"]]] <= self.delta:
                category = "own_object_near_unmatched"
            else:
                then = self._truth_centroid_at(identity["key"], int(entity["last_seen_tick"]))
                now = truth_table[identity["key"]]["centroid_m"]
                moved = then is not None and _distance(then, now) > self.delta
                category = "own_object_far_object_moved" if moved else "own_object_far_object_not_moved"
            entity_counts[category] += 1
        truth_counts = {name: 0 for name in CENTROID_TRUTH_CATEGORIES}
        for key in present_keys:
            column = column_of[key]
            if key in matched_keys:
                category = "matched"
            elif resolving[key]:
                near = any(dist_rows[row][column] <= self.delta for row in resolving[key])
                category = "resolved_entity_near_unmatched" if near else "resolved_entity_far"
            elif any(dist_rows[row][column] <= self.delta for row in ambiguous_rows):
                category = "only_ambiguous_entity_near"
            elif key in self.keys_fragmented:
                category = "no_entity_fragmented_before"
            else:
                category = "no_entity_never_fragmented"
            truth_counts[category] += 1
        _require(entity_counts["matched"] == frame_eval["matched"] and truth_counts["matched"] == frame_eval["matched"],
                 "audit_centroid_ledger_does_not_reproduce_the_evaluator")
        for name, count in entity_counts.items():
            self.centroid_entity_counts[name] += count
        for name, count in truth_counts.items():
            self.centroid_truth_counts[name] += count
        return {"entity": entity_counts, "truth": truth_counts}

    def _birth_reasons(self, step: Mapping[str, Any], labelled: Mapping[str, Any], truth_table: Mapping[str, Mapping[str, Any]]) -> None:
        """Why each fragment the committed program gave birth to was born (the arm's logits recomputed on the sealed rows)."""

        from vsmt import lean_arms as arms
        from vsmt import lean_assignment as la
        from vsmt import lean_runner as lr

        if step["receipt"].get("illegal_program"):
            return  # the empty program was committed: nothing was born
        births = sorted(str(fragment_id) for fragment_id, column in step["stage_b"]["assignment"].items()
                        if str(column).startswith(la.BIRTH_COLUMN_PREFIX))
        if not births:
            return
        logits = lr._association_logits(self.arm, lr.validate_arm_config(self.arm, self.config), step["stage_a"], self.scorer)
        carriers: dict[str, set[str]] = {}
        for entity_id, identity in lt.entity_identities(step["memory_before"], self.evidence).items():
            if identity["resolvable"]:
                carriers.setdefault(str(identity["key"]), set()).add(entity_id)
        recalled: dict[str, set[str]] = {}
        for row in step["stage_a"]["association_rows"]:
            recalled.setdefault(str(row["fragment_id"]), set()).add(str(row["entity_id"]))
        for fragment_id in births:
            target = labelled["targets"].get(fragment_id) or {}
            key = target.get("key")
            scope = "in_scope_object" if key is not None and truth_table.get(key, {}).get("in_scope") is True else "other"
            if key is None:
                reason = "unlabelled_fragment"
            elif key not in self._keys_before_frame:
                reason = "first_labelled_observation"
            elif not carriers.get(key):
                reason = "no_resolved_carrier"
            else:
                candidates = carriers[key] & recalled.get(fragment_id, set())
                birth_logit = float(logits["birth_logits"][fragment_id])
                eligible = [entity_id for entity_id in candidates
                            if float(logits["association_logits"][f"{fragment_id}|{entity_id}"]) > arms.INELIGIBLE_LOGIT
                            and float(logits["association_logits"][f"{fragment_id}|{entity_id}"]) >= birth_logit]
                if not candidates:
                    reason = "correct_carrier_not_recalled"
                elif not eligible:
                    reason = "correct_carrier_below_birth_logit"
                else:
                    reason = "correct_carrier_lost_joint_competition"
            self.birth_reasons[scope][reason] += 1

    def _file_folds(self) -> None:
        """File the folds captured this frame by state pair and private identity (the teacher has labelled the frame)."""

        while self.fold_capture:
            fold = self.fold_capture.pop(0)
            left, right = (lt.entity_identity(fold[side], self.evidence) for side in ("canonical", "folded"))
            states = "_".join(sorted((fold["canonical"]["state"], fold["folded"]["state"])))
            if not (left["resolvable"] and right["resolvable"]):
                identity = "ambiguous"
            else:
                identity = "same_object" if left["key"] == right["key"] else "different_objects"
            self.folds_by_identity[f"{states}|{identity}"] += 1

    def _dedup_pairs(self, memory_after: Mapping[str, Any], identities: Mapping[str, Mapping[str, Any]]) -> None:
        """At a dedup tick, tally the entity pairs left after the fold by state pair and private identity at every gate value."""

        import numpy as np

        from vsmt import lean_memory as lm

        self.dedup_ticks += 1
        record = memory_after["transaction_log"][-1]
        _require(int(record["tick"]) == int(memory_after["tick"]), "audit_dedup_log_not_at_the_tick")
        self.dedup_folds += len(record["post_maintenance"]["dedup"])
        entities = sorted((e for e in memory_after["entities"] if e["state"] in ("active", "dormant")), key=lambda e: str(e["entity_id"]))
        if len(entities) < 2:
            return
        descriptors = np.asarray([e["descriptor_mean"] for e in entities], dtype=np.float64)
        norms = np.linalg.norm(descriptors, axis=1)
        norms[norms == 0.0] = 1.0
        unit = descriptors / norms[:, None]
        cosine = unit @ unit.T
        centroids = np.asarray([e["centroid_m"] for e in entities], dtype=np.float64)
        distance = np.linalg.norm(centroids[:, None, :] - centroids[None, :, :], axis=2)
        count = len(entities)
        for i in range(count):
            left = entities[i]
            left_identity = identities[str(left["entity_id"])]
            for j in range(i + 1, count):
                right = entities[j]
                right_identity = identities[str(right["entity_id"])]
                states = "_".join(sorted((left["state"], right["state"])))
                if not (left_identity["resolvable"] and right_identity["resolvable"]):
                    identity = "ambiguous"
                elif left_identity["key"] == right_identity["key"]:
                    identity = "same_object"
                else:
                    identity = "different_objects"
                tally = self.dedup_pairs[f"{states}|{identity}"]
                tally["pairs"] += 1
                pair_cosine, pair_distance = float(cosine[i, j]), float(distance[i, j])
                if pair_cosine < DEDUP_COSINES[0] or pair_distance > DEDUP_DISTANCES_M[-1]:
                    continue
                pair_iou = lm._aabb_iou(left, right)
                for c in DEDUP_COSINES:
                    if pair_cosine < c:
                        break
                    for d in DEDUP_DISTANCES_M:
                        if pair_distance > d:
                            continue
                        for u in DEDUP_IOUS:
                            if pair_iou < u:
                                continue
                            name = f"cos{c}|d{d}|iou{u}"
                            tally["pass"][name] = tally["pass"].get(name, 0) + 1


    # -- the episode -------------------------------------------------------------

    def report(self) -> dict[str, Any]:
        def quantiles(values: Sequence[float]) -> dict[str, Any]:
            if not values:
                return {"count": 0}
            ordered = sorted(values)
            at = lambda q: ordered[min(len(ordered) - 1, int(q * len(ordered)))]  # noqa: E731
            return {"count": len(ordered), "p10": at(0.1), "p25": at(0.25), "p50": at(0.5), "p75": at(0.75), "p90": at(0.9),
                    "mean": sum(ordered) / len(ordered)}

        current = self.rule_sums["iou_0.3_secondary"]  # the categories partition the IoU column's sets, which are the primary's too
        _require(sum(self.entity_counts.values()) == current["predicted"], "audit_entity_categories_do_not_sum")
        _require(sum(self.truth_counts.values()) == current["truth"], "audit_truth_categories_do_not_sum")
        primary = self.rule_sums["centroid_within_0.5m"]
        _require(sum(self.centroid_entity_counts.values()) == primary["predicted"], "audit_centroid_entity_categories_do_not_sum")
        _require(sum(self.centroid_truth_counts.values()) == primary["truth"], "audit_centroid_truth_categories_do_not_sum")
        if self.fold_capture is not None and self.dedup_period is not None:
            _require(sum(self.folds_by_identity.values()) == self.dedup_folds, "audit_captured_folds_do_not_match_the_log")
        return {
            "schema_version": SCHEMA_VERSION,
            "frames": self.frames,
            "iou_min": self.iou_min, "delta_moved_m": self.delta, "pad_m": PAD_M, "centroid_radius_m": CENTROID_RADIUS_M,
            "rules": {rule: _prf(s["matched"], s["predicted"], s["truth"]) for rule, s in self.rule_sums.items()},
            "wrong_identity_matches": dict(self.wrong_identity_matches),
            "entity_categories": dict(self.entity_counts),
            "truth_categories": dict(self.truth_counts),
            "truth_by_group": {group: dict(row) for group, row in sorted(self.by_group.items())},
            "truth_by_type": {name: dict(row) for name, row in sorted(self.by_type.items(), key=lambda item: (-sum(item[1].values()), item[0]))},
            "in_memory_entities_per_frame_mean": (sum(self.in_memory_per_frame) / self.frames) if self.frames else None,
            "out_of_scope_entities_per_frame_mean": (sum(self.out_of_scope_per_frame) / self.frames) if self.frames else None,
            "own_object_iou_when_near": quantiles(self.own_iou_near_values),
            "own_object_centroid_distance_m": quantiles(self.own_distance_values),
            "rule_matched_per_frame": {rule: list(values) for rule, values in self.rule_matched_per_frame.items()},
            "centroid_entity_categories": dict(self.centroid_entity_counts),
            "centroid_truth_categories": dict(self.centroid_truth_counts),
            "birth_reasons": {scope: dict(row) for scope, row in self.birth_reasons.items()} if self.arm is not None else None,
            "dedup": {"period_ticks": self.dedup_period, "ticks": self.dedup_ticks, "folds": self.dedup_folds,
                      "folds_by_identity": dict(self.folds_by_identity) if self.fold_capture is not None else None,
                      "gate_values": {"cosine": list(DEDUP_COSINES), "distance_m": list(DEDUP_DISTANCES_M), "iou": list(DEDUP_IOUS)},
                      "pairs_after_fold": {name: {"pairs": row["pairs"], "pass": dict(sorted(row["pass"].items()))}
                                           for name, row in self.dedup_pairs.items()}} if self.dedup_period is not None else None,
        }


# --------------------------------------------------------------------------
# entry points
# --------------------------------------------------------------------------

def _git(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=str(ROOT), text=True).strip()


def run(args: argparse.Namespace) -> int:
    import lean_s1_04_diagnostics as diag
    import lean_s2_01_runner as s2_01
    import lean_s2_04_evaluate_episode as s2_04
    from vsmt import lean_assignment as la
    from vsmt import lean_evaluation as ev
    from vsmt import lean_object_geometry as og
    from vsmt import lean_runner as lr

    contract = ev.validate_evaluation_contract(s2_04.load_json(s2_04.S2_04_CONTRACT))
    runner_contract = lr.validate_runner_contract(s2_04.load_json(s2_01.S2_01_CONTRACT))
    closed = [f"S2-04 {name}" for name in s2_04.REQUIRED_S2_04 if contract["authorization"].get(name) is not True]
    closed += [f"S2-01 {name}" for name in s2_04.REQUIRED_S2_01 if runner_contract["authorization"].get(name) is not True]
    if closed:
        print(f"[node-audit] refused: authorization bits still closed: {closed}", file=sys.stderr)
        return 2
    policy, missing = s2_04.gather_teacher_policy()
    if missing:
        print(f"[node-audit] refused: policy values still null: {missing}", file=sys.stderr)
        return 2
    if not args.allow_dirty and _git("status", "--porcelain"):
        print("[node-audit] refused: the checkout is not clean", file=sys.stderr)
        return 2
    commit = _git("rev-parse", "HEAD")
    config = json.loads(args.config)
    if args.dedup_override:
        # diagnostic only: the same runner under another shared-dedup triple (a candidate for a ruling), recorded in the payload
        from vsmt import lean_memory as lm

        policy["runner"]["dedup"] = lm.validate_dedup_policy({**policy["runner"]["dedup"], **json.loads(args.dedup_override)})
    lr.validate_arm_config(args.arm, config)
    scorer = None
    if args.arm in lr.LEARNED_ARMS:
        if not args.heads:
            print(f"[node-audit] refused: {args.arm} needs --heads", file=sys.stderr)
            return 2
        from vsmt import lean_model

        scorer = lean_model.LeanScorer(lean_model.load_heads(s2_04.load_json(Path(args.heads)), device=args.device), device=args.device)
    projector = None
    if args.descriptor == la.SELECTED_DESCRIPTOR:
        if not args.weights:
            print("[node-audit] refused: --weights is required for the selected descriptor", file=sys.stderr)
            return 2
        payload = s2_04.load_json(Path(args.weights))
        projector = lr.descriptor_projector(payload, expected_sha256=la.SELECTED_REID_WEIGHTS_SHA256, device=args.device)

    cache_dir = Path(args.cache_root).resolve() / args.episode_id
    episode_root = Path(args.episode_root).resolve()
    seal, frame_paths = s2_04.verify_cache_episode(cache_dir, diag.registered_descriptor_asset_sha256s())
    if args.frames is not None:
        frame_paths = frame_paths[: int(args.frames)]
    table = og.validate_geometry_table(s2_04.load_json(Path(args.geometry_root).resolve() / args.episode_id / og.TABLE_FILE_NAME))
    executed, window = diag.cache_runner_read_interventions(episode_root / "provenance")
    episode_receipt = s2_04.load_json(episode_root / "receipt.json") if (episode_root / "receipt.json").exists() else {}
    split_seed = int(s2_04.load_json(s2_04.CONFIG_DIR / "lean_s1_02a_pilot_v2.json")["split_freeze"]["seed"])
    nuisance_meta = {"path": str(cache_dir), "seed": split_seed, "house_index": episode_receipt.get("source_index")}

    out_dir = Path(args.output_root).resolve() / args.episode_id / args.arm
    if (out_dir / AUDIT_FILE_NAME).exists():
        print(f"[node-audit] refused: audit exists: {out_dir / AUDIT_FILE_NAME}", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)

    teacher = ev.EpisodeTeacher(arm=args.arm, geometry_table=table, executed_interventions=executed, window=window,
                                policy=policy["teacher"], nuisance_meta=nuisance_meta)
    captured = capture_truth_table(teacher)
    audit = NodeAudit(evidence=teacher.evidence, iou_min=teacher.iou_min, delta_moved_m=policy["teacher"]["delta_moved_m"],
                      groups=object_groups(table), arm=args.arm, config=config, scorer=scorer, dedup=policy["runner"]["dedup"])
    audit.fold_capture = capture_dedup_folds()
    started = time.time()
    current: dict[str, Any] = {}

    depth_view = s2_04.episode_depth_reader(episode_root, cache_dir)

    def frames():
        for index, path in enumerate(frame_paths):
            frame = diag.cache_runner.load_cache_frame(path)
            frame[lr.PUBLIC_DEPTH_VIEW_KEY] = depth_view(index, frame)  # ruling 74
            current["frame"] = frame
            yield frame

    state = None
    receipts: list[dict[str, Any]] = []
    mark = time.time()
    for index, step in enumerate(lr.run_episode(frames(), episode_id=args.episode_id, arm=args.arm, config=config,
                                                policy=policy["runner"], descriptor=args.descriptor, projector=projector, scorer=scorer)):
        runtime = time.time() - mark
        receipts.append(step["receipt"])
        state = step["state"]
        cache_frame = current["frame"]
        masks = diag.cache_runner.read_masks_file(cache_dir / f"{index:04d}{diag.cache_runner.MASK_FILE_SUFFIX}")
        record, image = s2_04.load_private_frame(episode_root, index)
        labelled = teacher.label_frame(step, cache_frame=cache_frame, private_record=record, masks=masks,
                                       label_image=image, runtime_s=runtime, peak_memory_bytes=s2_04.peak_rss_bytes())
        audit.observe(step, labelled, captured["table"])
        mark = time.time()
    summary = lr.episode_summary(state, receipts)
    episode = teacher.episode_report()
    payload = {
        "schema_version": SCHEMA_VERSION, "stage": "S2-05 node audit (read-only)", "code_commit": commit,
        "episode_id": args.episode_id, "arm": args.arm, "config": config, "descriptor": args.descriptor,
        "dedup_policy": policy["runner"]["dedup"], "dedup_override": json.loads(args.dedup_override) if args.dedup_override else None,
        "frames": summary["frames"], "frames_requested": args.frames, "episode_seal_sha256": seal["payload_sha256"],
        "final_memory_digest": summary["final_memory_digest"], "final_entities_by_state": summary["final_entities_by_state"],
        "report_node_prf1": episode["report"]["node_prf1"], "report_node_prf1_iou": episode["report"]["node_prf1_iou"],
        "audit": audit.report(),
        "wall_seconds": round(time.time() - started, 1),
    }
    (out_dir / AUDIT_FILE_NAME).write_text(json.dumps(payload, indent=1), encoding="utf-8")
    rules = payload["audit"]["rules"]
    print(f"[node-audit] {args.arm} {args.episode_id}: {summary['frames']} frames, current F1 {rules['iou_0.3_secondary']['f1']}, "
          f"oracle-group IoU F1 {rules['oracle_identity_groups_iou_0.3']['f1']}, centroid-0.5m F1 {rules['centroid_within_0.5m']['f1']}, "
          f"{payload['wall_seconds']} s")
    return 0


def merge_audits(output_root: Path, arm: str) -> dict[str, Any]:
    """Pool the node audits of one arm under an audit root: per-episode rows and pooled sums."""

    episodes: list[dict[str, Any]] = []
    pooled_rules = {rule: {"matched": 0, "predicted": 0, "truth": 0} for rule in RULES}
    pooled_entity = {name: 0 for name in ENTITY_CATEGORIES}
    pooled_truth = {name: 0 for name in TRUTH_CATEGORIES}
    pooled_group: dict[str, dict[str, int]] = {}
    pooled_type: dict[str, dict[str, int]] = {}
    commits: set[str] = set()
    pooled_centroid_entity = {name: 0 for name in CENTROID_ENTITY_CATEGORIES}
    pooled_centroid_truth = {name: 0 for name in CENTROID_TRUTH_CATEGORIES}
    pooled_births = {scope: {name: 0 for name in BIRTH_REASONS} for scope in ("in_scope_object", "other")}
    pooled_dedup: dict[str, Any] = {"ticks": 0, "folds": 0, "folds_by_identity": {}, "pairs_after_fold": {}}
    pooled_wrong: dict[str, int] = {}
    for path in sorted(output_root.glob(f"*/{arm}/{AUDIT_FILE_NAME}")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        _require(payload.get("schema_version") == SCHEMA_VERSION and payload.get("arm") == arm, f"audit_file_invalid:{path}")
        audit = payload["audit"]
        commits.add(str(payload["code_commit"]))
        for rule in RULES:
            for name in ("matched", "predicted", "truth"):
                pooled_rules[rule][name] += int(audit["rules"][rule][name])
        for name in ENTITY_CATEGORIES:
            pooled_entity[name] += int(audit["entity_categories"][name])
        for name in TRUTH_CATEGORIES:
            pooled_truth[name] += int(audit["truth_categories"][name])
        for rule, value in (audit.get("wrong_identity_matches") or {}).items():
            pooled_wrong[rule] = pooled_wrong.get(rule, 0) + int(value)
        for name in CENTROID_ENTITY_CATEGORIES:
            pooled_centroid_entity[name] += int(audit["centroid_entity_categories"][name])
        for name in CENTROID_TRUTH_CATEGORIES:
            pooled_centroid_truth[name] += int(audit["centroid_truth_categories"][name])
        for scope, row in (audit.get("birth_reasons") or {}).items():
            for name in BIRTH_REASONS:
                pooled_births[scope][name] += int(row[name])
        if audit.get("dedup"):
            pooled_dedup["ticks"] += int(audit["dedup"]["ticks"])
            pooled_dedup["folds"] += int(audit["dedup"]["folds"])
            for name, value in (audit["dedup"].get("folds_by_identity") or {}).items():
                pooled_dedup["folds_by_identity"][name] = pooled_dedup["folds_by_identity"].get(name, 0) + int(value)
            for name, row in audit["dedup"]["pairs_after_fold"].items():
                target = pooled_dedup["pairs_after_fold"].setdefault(name, {"pairs": 0, "pass": {}})
                target["pairs"] += int(row["pairs"])
                for gate, value in row["pass"].items():
                    target["pass"][gate] = target["pass"].get(gate, 0) + int(value)
        for group, row in audit["truth_by_group"].items():
            target = pooled_group.setdefault(group, {name: 0 for name in TRUTH_CATEGORIES})
            for name in TRUTH_CATEGORIES:
                target[name] += int(row[name])
        for type_name, row in audit["truth_by_type"].items():
            target = pooled_type.setdefault(type_name, {name: 0 for name in TRUTH_CATEGORIES})
            for name in TRUTH_CATEGORIES:
                target[name] += int(row[name])
        episodes.append({
            "episode_id": payload["episode_id"], "frames": payload["frames"], "config": payload["config"],
            "final_entities_by_state": payload["final_entities_by_state"],
            "rules_f1": {rule: audit["rules"][rule]["f1"] for rule in RULES},
            "iou_0.3_secondary": audit["rules"]["iou_0.3_secondary"],
            "centroid_primary": audit["rules"]["centroid_within_0.5m"],
            "entity_categories": audit["entity_categories"], "truth_categories": audit["truth_categories"],
            "centroid_entity_categories": audit["centroid_entity_categories"], "centroid_truth_categories": audit["centroid_truth_categories"],
            "birth_reasons": audit.get("birth_reasons"), "dedup_folds": (audit.get("dedup") or {}).get("folds"),
            "in_memory_entities_per_frame_mean": audit["in_memory_entities_per_frame_mean"],
            "own_object_iou_when_near": audit["own_object_iou_when_near"],
            "own_object_centroid_distance_m": audit["own_object_centroid_distance_m"],
            "audit_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    _require(bool(episodes), f"no_audits_found:{output_root}/*/{arm}")
    return {
        "schema_version": "vsmt-s2-05-node-audit-merged-v2",
        "stage": "S2-05 node audit (read-only, pooled)", "arm": arm, "output_root": str(output_root),
        "code_commits": sorted(commits), "episodes": len(episodes),
        "pooled_rules": {rule: _prf(s["matched"], s["predicted"], s["truth"]) for rule, s in pooled_rules.items()},
        "pooled_entity_categories": pooled_entity, "pooled_truth_categories": pooled_truth,
        "pooled_centroid_entity_categories": pooled_centroid_entity, "pooled_centroid_truth_categories": pooled_centroid_truth,
        "pooled_birth_reasons": pooled_births, "pooled_dedup": pooled_dedup, "pooled_wrong_identity_matches": pooled_wrong,
        "pooled_truth_by_group": {group: row for group, row in sorted(pooled_group.items())},
        "pooled_truth_by_type": {name: row for name, row in sorted(pooled_type.items(), key=lambda item: (-sum(item[1].values()), item[0]))[:40]},
        "per_episode": episodes,
        "private_ids_exported": False,
    }


def merge(args: argparse.Namespace) -> int:
    try:
        merged = merge_audits(Path(args.output_root).resolve(), args.arm)
    except NodeAuditError as exc:
        print(f"[node-audit] refused: {exc}", file=sys.stderr)
        return 2
    results = Path(args.results)
    results.parent.mkdir(parents=True, exist_ok=True)
    results.write_text(json.dumps(merged, indent=1), encoding="utf-8")
    pooled = merged["pooled_rules"]
    print(f"[node-audit] merged {merged['episodes']} episodes of {args.arm}: " +
          ", ".join(f"{rule} F1 {pooled[rule]['f1']:.3f}" if pooled[rule]["f1"] is not None else f"{rule} F1 null" for rule in RULES))
    print(f"[node-audit] wrote {results}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run", help="audit one episode under one arm and configuration")
    run_parser.add_argument("--cache-root", required=True)
    run_parser.add_argument("--episode-root", required=True)
    run_parser.add_argument("--geometry-root", required=True)
    run_parser.add_argument("--episode-id", required=True)
    run_parser.add_argument("--arm", required=True)
    run_parser.add_argument("--config", required=True)
    run_parser.add_argument("--descriptor", required=True)
    run_parser.add_argument("--weights", default=None)
    run_parser.add_argument("--heads", default=None)
    run_parser.add_argument("--output-root", required=True)
    run_parser.add_argument("--frames", type=int, default=None)
    run_parser.add_argument("--device", default="cpu")
    run_parser.add_argument("--allow-dirty", action="store_true")
    run_parser.add_argument("--dedup-override", default=None, help="diagnostic: JSON of shared-dedup values to replace (never a run of record)")
    run_parser.set_defaults(func=run)
    merge_parser = sub.add_parser("merge", help="pool the audits of one arm into a results/ report")
    merge_parser.add_argument("--output-root", required=True)
    merge_parser.add_argument("--arm", required=True)
    merge_parser.add_argument("--results", required=True)
    merge_parser.set_defaults(func=merge)
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
