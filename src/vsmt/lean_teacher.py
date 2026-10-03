"""D-224 / S0-04: instance-truth teacher, error decomposition and metrics.

Everything in this module runs *after* the two S0-03 seals exist.  It is the
only place that reads private instance truth, and it does so through one
gate receipt rather than by opening files itself.  It depends on the S0-03
products only as data shapes (recall lists, an assignment dict whose values
are an ``entity_id`` or ``"birth:<fragment_id>"``, the existence candidate
list, the two seal digests), never on that module's functions, so the two
stages can be reviewed and revised independently.

白话：这个模块解决"答案怎么来、错在哪一层、论文表上的每个数怎么算"。输入是封
存后的召回与分配、旧记忆、当前帧的私有实例真值；输出是逐色块与逐实体的标签、
三分解计数、七项指标，以及 house 级配对 bootstrap。例如一个色块的主导实例是旧
杯子、旧杯子实体也在召回集合里、但学生把它分到了新建列，这一例记为 amortization
error 而不是 recall miss。它不生成候选、不改召回、不进入部署推理。

Four rules carry the S0-04 continue gate:

1. Private truth opens only against a gate receipt that names both seals.
2. Every label is either resolvable or explicitly counted as unresolvable;
   nothing ambiguous is silently dropped or silently guessed.
3. The evaluator's box matching is its own code.  It deliberately does not
   import the method's assignment solver, so a solver bug cannot hide inside
   the numbers that judge it.
4. The machine contract binds every boolean claim it makes; flipping any one
   of them, or adding one the validator does not know, is rejected.

Six semantic choices below were frozen by the user as D-224-LQ (rulings L
to Q, 2026-09-20): dormant entities count as "still in memory" for node
P/R/F1 and for the Missing residual rate; identity continuity does not credit
the shared dedup's ``canonical_of`` folding; fragment dominance is measured
over all fragment pixels and entity identity is a strict majority; recovery
latency starts at the first observable frame; existence candidates are active
and dormant; truth nodes are objects observable at least once and displacement
is measured from the entity's remembered centroid.
"""

from __future__ import annotations

import math
import random
import re
from collections import OrderedDict
from typing import Any, Mapping, Sequence

from cpmt.hashing import clone_json

from vsmt.lean_memory import validate_memory


CONTRACT_SCHEMA_VERSION = "vsmt-lean-s0-teacher-metrics-v2"

#: The decision that froze the six evaluation semantics this module implements.
RULINGS_DECISION_ID = "D-224-LQ"

BIRTH_COLUMN_PREFIX = "birth:"

ENTITY_STATES = ("active", "dormant", "retracted")

#: Per-fragment association label statuses.  Every fragment gets exactly one.
#: ``duplicate_of_labelled`` (D-224-X ruling X1): a second fragment of the
#: same object aimed at the same target entity in the same frame; the
#: executor lets an entity take one fragment per frame, so only the fragment
#: with the most pixels on the object keeps the target and the others are
#: excluded from the loss and charged to no error class.
ASSOCIATION_STATUSES = (
    "labelled", "birth", "recall_miss", "unlabelled", "identity_ambiguous",
    "duplicate_of_labelled",
)

#: Per-entity existence label statuses.
EXISTENCE_STATUSES = ("gone", "present", "identity_ambiguous")

#: Which entity states count as "still in memory" for node P/R/F1, the
#: Missing residual rate, contamination and recovery.  D-224-LQ ruling L:
#: dormancy is a shared rule that fires without evidence, so it must not be
#: credited as a correct "missing" judgement.
MEMORY_PRESENT_STATES = ("active", "dormant")

#: Which entity states may receive an existence label (D-224-LQ ruling P).
#: S0-01 lets RETRACT target ``dormant`` as well as ``active``; ``retracted``
#: has no RETRACT/NOOP decision to judge and is rejected, not skipped.
EXISTENCE_CANDIDATE_STATES = ("active", "dormant")

#: The metrics the paper may report and no other: the seven, their registered secondary or diagnostic columns, and the eighth
#: (retrieval success, ruling 83-5, defined by ruling 102-5).
METRICS = (
    "node_prf1",
    "node_prf1_iou",
    "missing_residual_rate",
    "false_retract_rate",
    "false_retract_rate_in_scope",   # D-224-S1 ruling 80-5 (b): secondary column beside false_retract_rate
    "identity_continuity",
    "identity_continuity_conditional",  # ruling 102-0: the pre-ruling conditional definition, a diagnostic column
    "retrieval_success",  # ruling 83-5 / 102-5: the eighth metric, reported, never gated, never selecting
    "recovery_latency_frames",
    "contamination_auc",
    "size_and_cost",
)

#: The only fields a report may carry under each metric.
METRIC_FIELDS: dict[str, tuple[str, ...]] = {
    "node_prf1": ("node_precision", "node_recall", "node_f1", "matched", "predicted", "truth"),
    "node_prf1_iou": ("node_precision", "node_recall", "node_f1", "matched", "predicted", "truth"),
    "missing_residual_rate": ("missing_residual_rate", "residual", "judged", "not_yet_observable"),
    "false_retract_rate": ("false_retract_rate", "false_retracts", "judged_retracts", "ambiguous_retracts"),
    "false_retract_rate_in_scope": ("false_retract_rate", "false_retracts", "judged_retracts", "ambiguous_retracts"),
    "identity_continuity": ("identity_continuity", "kept", "events", "no_prior_carrier"),
    "identity_continuity_conditional": ("identity_continuity", "kept", "judged"),
    "retrieval_success": ("retrieval_success", "successes", "events", "no_query", "empty_candidates"),
    "recovery_latency_frames": ("recovery_latency_frames", "recovered", "unrecovered", "never_observable", "per_object"),
    "contamination_auc": ("contamination_auc", "frames"),
    "size_and_cost": ("active_entity_count", "lifecycle_version_count", "runtime_per_frame_s", "peak_memory_bytes"),
}

#: Versions opened by BIND are one-per-observation bookkeeping, not lifecycle
#: events; the size metric counts the others (D-224-X ruling X6).
LIFECYCLE_VERSION_EXCLUDES = ("bind",)

#: Three-way decomposition of every wrong decision.
DECOMPOSITION = ("recall_miss", "teacher_error", "amortization_error")

#: Metrics some arms cannot define by construction (D-224-X ruling X2 as
#: corrected after review, LOG-225).  An arm named by the rule reports the
#: metric as "not applicable": it never enters that metric's exclusion
#: list, its pairings or its strongest-control choice.  Without this, the
#: three never-retracting arms would make false_retract_rate undefined in
#: every house and the whole column would be excluded for everyone.  The
#: rule names the vocabulary test; the arms contract supplies the arms.
METRIC_NOT_APPLICABLE_RULE: dict[str, str] = {
    "false_retract_rate": "arms_whose_vocabulary_lacks_RETRACT",
    "false_retract_rate_in_scope": "arms_whose_vocabulary_lacks_RETRACT",
}

#: D-224-S1 ruling 80-5 (b), 2026-09-28: existence labels the evaluator sets to present by rule for objects outside the truth
#: node scope (the structural types of rulings 56 continued / 69, and objects spawned after the reload).  A RETRACT on such an
#: entity counts as a false retract in false_retract_rate; the secondary column leaves these candidates out (LOG-273: 530 of
#: VSMT-lean's 744 development false retracts were structural entities, which the node metric never scores).
PRESENT_BY_RULE_REASONS = ("structural_never_intervened", "spawned_after_reload")
FALSE_RETRACT_IN_SCOPE_RULE = ("false_retract_rate over the existence candidates whose label reason is not one of "
                               "PRESENT_BY_RULE_REASONS (entities resolving to objects outside the truth node scope are left out)")
FALSE_RETRACT_IN_SCOPE_ROLE = "secondary_column_reported_beside_false_retract_rate_never_the_selection_metric_never_in_the_main_gate"

#: Fields a nuisance probe may see.  If any of them predicts a label better
#: than the majority class, the data leaks through metadata.
NUISANCE_FIELDS = ("path", "seed", "frame_index", "house_index")

#: Every label kind the probe must be run against.
NUISANCE_LABELS = ("association_status", "association_target_is_birth", "existence_status")

#: Main-gate metrics and the direction in which VSMT-lean must win.
MAIN_GATE = (
    ("missing_residual_rate", "lower"),
    ("identity_continuity", "higher"),
)

#: Ruling 102-2 / 102-3 (2026-10-02, 「待裁 102 修订稿二全按推荐」): the S3 main gate.  The primary comparison is VSMT-lean
#: against the same-recipe AssocOnly (ruling 99-2); each gate metric is tested on one exclusion list over every run of the
#: main table, by two-level resampling of houses and seeds plus the 82-1 seed-stability condition; the two front ends are
#: tested in a fixed sequence.  The original gate (against the strongest control) is computed the same way and reported.
PRIMARY_COMPARISON = ("VSMT-lean", "AssocOnly")
GATE_SEEDS = (7, 19, 31, 43, 59)
MAIN_GATE_RULE = (
    "per front end, VSMT-lean against the same-recipe AssocOnly: on both main-gate metrics the two-level lower bound of the "
    "seed-averaged paired advantage exceeds 0 and the 82-1 seed-stability condition holds; the target is the training "
    "procedure under fixed training data, recipe and selection (ruling 99-2, ruling 102-3)"
)
EXCLUSION_OVER_RUNS_RULE = (
    "one list per metric and front end: a house is excluded for every arm and every test when the metric is undefined in any "
    "run of the main-table arms (each learned arm at each of its seeds, each rule arm once); the same list serves the primary "
    "test, the seed-paired gaps, the original gate, the strongest-control choice and the power statement (X2 extended to seeds)"
)
TWO_LEVEL_RESAMPLING_RULE = (
    "each draw resamples the houses with replacement and, independently, the seed indices with replacement; every drawn seed "
    "is evaluated on the same drawn houses (houses and seeds are crossed) and the two arms are paired by seed index; the "
    "statistic is the mean paired advantage over drawn houses x drawn seeds; the lower bound is the floor(0.05 x iterations)-th "
    "of the sorted draws; a seedless arm (a rule arm) contributes its one value at every seed"
)
SEED_STABILITY_RULE = (
    "82-1 in the favourable direction: all five seeds present, at least four of the five seed-paired house-mean gaps favour "
    "VSMT-lean, their mean favours VSMT-lean and its absolute value exceeds the sample standard deviation of the five gaps"
)
ORIGINAL_GATE_RULE = (
    "the gate written before ruling 99 -- VSMT-lean against the strongest control on both metrics -- computed with the same "
    "exclusion list, resampling and stability rule and reported, never gating"
)
#: Ruling 102-2: the fixed sequence over the two front ends; a step is tested only when every earlier step passed.
FIXED_SEQUENCE = (
    ("simulator_instance_masks", ("missing_residual_rate", "identity_continuity")),
    ("sam2", ("missing_residual_rate",)),
    ("sam2", ("identity_continuity",)),
)
FIXED_SEQUENCE_RULE = (
    "fixed-sequence testing at one-sided 5% per step: (1) instance segmentation, both main-gate metrics together; (2) only if (1) "
    "passed, SAM 2.1 Missing residual rate; (3) only if (2) passed, SAM 2.1 identity continuity; a step not reached is reported "
    "with its difference and interval only; the order (designed after the S2-06 development readings, frozen before validation "
    "and test) follows the main-table front end of rulings 72 / 83-3 and the metric order of main_gate"
)

METHOD_ARM = "VSMT-lean"
CONTROL_ARMS = ("TAF", "ELU-P", "RAC", "LOW")
ABLATION_ARMS = ("NoVersion", "HandCost", "HeuristicLabel", "AssocOnly")
APPENDIX_ARM = "LLM-op"
OPTIONAL_ARM = "VSMT-lean-ctx"

#: Constants frozen by an approved decision, not policy values: D-224 ruling
#: C fixes the 3D IoU threshold, METHOD section 11 fixes the bootstrap size
#: and the one-sided 95% bound.
IOU_MIN = 0.3
BOOTSTRAP_ITERATIONS = 10000
CONFIDENCE_ONE_SIDED = 0.95

#: Rule strings the contract must carry verbatim; each names code behaviour.
ENTITY_IDENTITY_RULE = "strict_majority_over_keyed_evidence"
FRAGMENT_DOMINANCE_DENOMINATOR = "all_fragment_pixels_background_included"
EXISTENCE_DISPLACEMENT_REFERENCE = "entity_remembered_centroid"
IDENTITY_CONTINUITY_JUDGED_AT = "first_labelled_reobservation_after_move"
#: Ruling 102-0 (2026-10-02): every arm is judged on the same events -- the moved objects re-observed with a labelled
#: fragment after the window, which depend only on the front end and the truth; an object the arm's memory did not carry
#: before the move counts as not kept.  The pre-ruling definition (kept over the objects that had a pre-move carrier in
#: that arm, so each arm answered a different set of questions) stays as a diagnostic column.
IDENTITY_CONTINUITY_DENOMINATOR = (
    "every moved object re-observed with a labelled fragment after the window, the same events for every arm; an object "
    "without a carrier in the arm's memory at the last window frame counts as not kept"
)
#: Ruling 102-5 (2026-10-02): retrieval success, the eighth metric registered by ruling 83-5.  The events are the identity
#: continuity events (front end and truth only); the query is built by the evaluator from private labels the method never sees.
RETRIEVAL_EVENT_RULE = (
    "each moved object at its first labelled re-observation after the window (the identity_continuity events: front end and truth "
    "only, the same for every arm)"
)
RETRIEVAL_QUERY_RULE = (
    "the evaluator's query: the unit-normalised mean of the run's selected-descriptor vectors of every fragment whose dominance "
    "resolves to the object in the frames up to the last window frame; an object without such a fragment has no query, is not an "
    "event and is counted as no_query"
)
RETRIEVAL_CANDIDATE_RULE = (
    "every active or dormant entity of the memory committed at the event frame, by its descriptor_mean unit-normalised; the highest "
    "cosine is retrieved, ties to the smaller entity_id; no candidate counts as a failure (empty_candidates)"
)
RETRIEVAL_SUCCESS_RULE = (
    "the retrieved entity pairs with the object under the node primary rule: its strict-majority identity is the object and its "
    "centroid is within delta_moved_m of the object's truth centroid or inside the truth box padded 0.25 m"
)
RETRIEVAL_ROLE = "eighth_metric_reported_beside_the_seven_never_in_the_main_gate_never_selects"

IDENTITY_CONTINUITY_CONDITIONAL_ROLE = (
    "diagnostic_column_kept_over_the_events_with_a_pre_move_carrier_reported_beside_identity_continuity_"
    "never_in_the_main_gate_never_selects"
)
RECOVERY_LATENCY_START = "first_frame_the_intervened_place_is_observable_to_the_method"
CONTAMINATION_INTEGRATION = "trapezoid_over_frames_normalised_to_unit_length"
TRUTH_NODE_SCOPE = "objects_present_at_t_that_have_been_observable_at_least_once_since_episode_start_excluding_structural_types"
#: D-224-S1 ruling 56 continued (2026-09-24): house structure never enters the truth node scope.
#: Ruling 69 (2026-09-24) adds the room ceilings (``Ceiling_room|<room>|...``): the same grounds,
#: structure that is never intervened and seen one patch at a time.
STRUCTURAL_TYPES_EXCLUDED = ("Ceiling_room", "door", "room", "wall", "window")
#: D-224-S1 ruling 69 (2026-09-24): a private key that is outside the reload geometry table because
#: the object was spawned by a physics event after the reload (a cracked egg, a sliced item) carries
#: a spawn tag as its last ``|`` field (letters, an underscore, digits, e.g. ``EggCracked_0``).  It
#: is present, out of the truth node scope, has no box, and is counted; any other key outside the
#: table still fails the episode (S2-01).
SPAWNED_AFTER_RELOAD_RULE = (
    "a_private_key_outside_the_geometry_table_whose_last_field_is_a_spawn_tag_(letters_underscore_"
    "digits)_is_present_out_of_scope_without_a_box_and_counted"
)
SPAWN_TAG = re.compile(r"^[A-Za-z][A-Za-z0-9]*_\d+$")
#: D-224-S1 ruling 45 (2026-09-22): where the truth boxes of the truth table come from.  The
#: per-frame private record only ever carried x/y/z, so the box is the initial axis-aligned box
#: read from one simulator reload of the house, translated by the recorded private position into
#: the episode frame.  The observed-set box (union of back-projected private masks) is a proxy
#: and may only be reported as a comparison column, never used as the truth box.
TRUTH_BOX_SOURCE = "simulator_initial_axis_aligned_box_plus_recorded_translation"
#: D-224-S1 ruling 70 (2026-09-24) added a centroid column beside the IoU one; ruling 72 (B)
#: (2026-09-25) swapped them.  ``node_prf1`` -- the primary column and the selection metric -- is the
#: evaluator-owned matching (count-first since ruling 76 (3)(a), see below) of the in-memory predictions to the present in-scope truth
#: objects where a pair qualifies when the centroid distance is within the frozen ``delta_moved_m``,
#: weighted 1/(1+distance) so nearer pairs win.  ``node_prf1_iou`` is the same two sets and the same
#: matcher with the 3D AABB IoU >= 0.3 test of ruling C (the Dyn-THOR overlap test), reported beside it
#: and never selecting.  LOG-257 sequel read the identity-grouped union as a ceiling (0.64 against 0.86);
#: LOG-262 corrected that: the grouping changes the count and the geometry together and is a diagnostic only.
#: D-224-S1 ruling 76 (3)(a) (2026-09-26, LOG-262): both columns match count-first -- the most pairs, and
#: among those the most weight -- because F1 counts pairs and the weight was meant to break ties, not to
#: trade a pair for a shorter distance (four pairs 0.5 m apart had lost to three pairs at 0 m).
NODE_MATCHING_OBJECTIVE = "most_pairs_then_most_weight"
#: D-224-S1 ruling 77 (1)(a) (2026-09-26, LOG-263 sequel): a primary-column pair must also be the entity's own object (the
#: evaluator's evidence-majority identity), and the place test is "centroid within delta_moved_m OR inside the truth box
#: padded by NODE_BOX_PAD_M".  Under the bare distance test 18 percent (TAF) and 34 percent (LOW) of the matched pairs were an entity of
#: another object or of none; a large object seen from one side has its visible-surface centroid beyond 0.5 m of the box centre.
NODE_BOX_PAD_M = 0.25
#: D-224-S1 ruling 88-4 (2026-09-29, LOG-284 continued): the existence label uses the node primary column's place test, so an
#: entity the evaluator counts as correctly placed is never labelled gone.  Under the centroid-only rule 28.9 percent of the
#: gone labels of the ruling-86 development rollouts sat on entities in place by the node rule with no other carrier, against
#: 13.3 percent real world change after the window (ops/vsmt/ruling88_label_partition.py).  In-place duplicates are
#: present too; redundancy is the shared dedup's job.  "centroid_only" is the pre-88 rule, kept for the ruling-88 decision
#: ceiling diagnostic only, never for training, selection or a table.
EXISTENCE_PLACE_RULE = "node_primary"
EXISTENCE_PLACE_RULES = ("node_primary", "centroid_only")
EXISTENCE_GONE_RULE = ("object absent from the scene, or the entity fails the node primary place test for its own object: "
                       "centroid farther than delta_moved_m from the object's centroid and outside the object's truth box "
                       "padded by box_pad_m (centroid only when the object has no box)")
NODE_IDENTITY_RULE ="the_entity_resolves_to_the_object_by_the_strict_majority_of_its_evidence_an_ambiguous_entity_matches_nothing"
CENTROID_MATCHING_RULE = "same_predictions_and_truth_objects_most_pairs_then_maximum_weight_matching_on_1_over_1_plus_centroid_distance_m_a_pair_qualifies_when_the_entity_resolves_to_the_object_and_its_centroid_is_within_delta_moved_m_or_inside_the_truth_box_padded_by_box_pad_m"
CENTROID_MATCHING_DISTANCE_SOURCE = "labels.existence.delta_moved_m"
CENTROID_MATCHING_ROLE = "primary_node_column_and_the_selection_metric_never_in_the_main_gate"
IOU_MATCHING_RULE = "same_predictions_and_truth_objects_most_pairs_then_maximum_total_3d_aabb_iou_matching_pairs_below_iou_min_excluded"
IOU_MATCHING_ROLE = "secondary_column_reported_beside_node_prf1_never_the_selection_metric_never_in_the_main_gate"
NODE_DYN_THOR_RELATION = "primary_adds_an_identity_test_and_a_box_test_the_secondary_iou_column_keeps_the_dyn_thor_original_overlap_test"
STRONGEST_CONTROL_RULE = "best_house_mean_per_metric_among_controls_ties_to_smallest_name"


class LeanTeacherError(ValueError):
    """Raised for any malformed truth, gate, label or metric input."""


# --------------------------------------------------------------------------
# small validators
# --------------------------------------------------------------------------

def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LeanTeacherError(code)


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


def _ratio(value: Any, code: str) -> float:
    result = _finite(value, code)
    _require(0.0 <= result <= 1.0, code)
    return result


def _hex64(value: Any, code: str) -> str:
    _require(type(value) is str and len(value) == 64, code)
    _require(all(char in "0123456789abcdef" for char in value), code)
    return value


def _vector3(value: Any, code: str) -> list[float]:
    _require(type(value) is list and len(value) == 3, code)
    return [_finite(item, code) for item in value]


def _distance(left: Sequence[float], right: Sequence[float]) -> float:
    return math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(left, right, strict=True)))


def _aabb_iou(
    lower_a: Sequence[float], upper_a: Sequence[float],
    lower_b: Sequence[float], upper_b: Sequence[float],
) -> float:
    overlap = 1.0
    volume_a = 1.0
    volume_b = 1.0
    for axis in range(3):
        low = max(float(lower_a[axis]), float(lower_b[axis]))
        high = min(float(upper_a[axis]), float(upper_b[axis]))
        overlap *= max(0.0, high - low)
        volume_a *= max(0.0, float(upper_a[axis]) - float(lower_a[axis]))
        volume_b *= max(0.0, float(upper_b[axis]) - float(lower_b[axis]))
    union = volume_a + volume_b - overlap
    return overlap / union if union > 0.0 else 0.0


def _boxes_overlap(left: Sequence[Mapping[str, Any]], right: Sequence[Mapping[str, Any]]) -> list[list[bool]]:
    """Whether each pair of boxes overlaps with positive extent on all three axes.

    Engineering (2026-09-27, LOG-266 profile): the node IoU column scored every prediction against every present
    truth object in pure Python (01289: 26.5 million ``_aabb_iou`` calls in 1,500 frames).  A pair without positive
    overlap on some axis has an IoU of exactly 0.0, which ``_aabb_iou`` returns too; ``max``, ``min`` and ``>`` are
    exact on floats, so this test marks exactly the pairs whose IoU can be non-zero and those alone are scored.
    """

    import numpy as np

    if not left or not right:
        return [[False] * len(right) for _ in left]
    left_low = np.asarray([item["aabb_min_m"] for item in left], dtype=np.float64)
    left_high = np.asarray([item["aabb_max_m"] for item in left], dtype=np.float64)
    right_low = np.asarray([item["aabb_min_m"] for item in right], dtype=np.float64)
    right_high = np.asarray([item["aabb_max_m"] for item in right], dtype=np.float64)
    high = np.minimum(left_high[:, None, :], right_high[None, :, :])
    low = np.maximum(left_low[:, None, :], right_low[None, :, :])
    return (high > low).all(axis=2).tolist()


def _precision_recall_f1(matched: int, predicted: int, truth: int) -> tuple[float | None, float | None, float | None]:
    precision = matched / predicted if predicted else None
    recall = matched / truth if truth else None
    if precision is None or recall is None:
        return precision, recall, None
    if precision + recall == 0.0:
        return precision, recall, 0.0
    return precision, recall, 2.0 * precision * recall / (precision + recall)


def _states(states: Sequence[str], code: str) -> tuple[str, ...]:
    result = tuple(str(item) for item in states)
    _require(result and all(item in ENTITY_STATES for item in result), code)
    _require(len(set(result)) == len(result), code)
    return result


def _delta(delta_moved_m: Any) -> float:
    delta = _finite(delta_moved_m, "delta_moved_invalid")
    _require(delta > 0.0, "delta_moved_invalid")
    return delta


# --------------------------------------------------------------------------
# 1. the private gate
# --------------------------------------------------------------------------

def assert_private_gate(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Accept private truth only against a receipt naming both S0-03 seals.

    白话：输入 S0-03 放行回执，输出同样内容的副本，并在缺任一段摘要、摘要格式不
    对或放行位不为真时拒绝。teacher 与评价器只能拿着这份回执打开私有数据。它不
    重算摘要，那是 S0-03 的职责；它只保证"没有两段封存就没有私有数据"。
    """

    _require(type(receipt) is dict, "private_gate_not_object")
    _require(
        set(receipt.keys()) == {
            "frame_digest", "stage_a_seal_sha256", "stage_b_seal_sha256", "private_may_open",
        },
        "private_gate_fields_invalid",
    )
    _hex64(receipt["frame_digest"], "private_gate_frame_digest_invalid")
    _hex64(receipt["stage_a_seal_sha256"], "private_gate_stage_a_seal_invalid")
    _hex64(receipt["stage_b_seal_sha256"], "private_gate_stage_b_seal_invalid")
    _require(receipt["private_may_open"] is True, "private_gate_not_open")
    return clone_json(dict(receipt))


def build_private_gate(stage_a: Mapping[str, Any], stage_b: Mapping[str, Any]) -> dict[str, Any]:
    """Turn the two S0-03 seal payloads into the one receipt this module accepts.

    白话：输入 S0-03 的阶段 A 与阶段 B 两份封存产物，输出放行回执。只做结构核对：
    两段都有合法摘要、指向同一帧、阶段 B 记录的阶段 A 摘要与阶段 A 自己的摘要一
    致、两段各自带着它们该带的表。例如阶段 B 指向的阶段 A 摘要对不上，说明有人在
    求解之后又改了召回，回执不发。它不重算任何摘要，那是 S0-03 自己的校验器的职
    责；这里只保证"没有两段封存就没有私有数据"。
    """

    _require(type(stage_a) is dict and type(stage_b) is dict, "gate_inputs_not_objects")
    a_seal = _hex64(stage_a.get("seal_sha256"), "gate_stage_a_seal_invalid")
    b_seal = _hex64(stage_b.get("seal_sha256"), "gate_stage_b_seal_invalid")
    frame_digest = _hex64(stage_a.get("frame_digest"), "gate_frame_digest_invalid")
    _require(stage_b.get("frame_digest") == frame_digest, "gate_frame_mismatch")
    _require(stage_b.get("stage_a_seal_sha256") == a_seal, "gate_chain_broken")
    for key in ("recall", "association_rows", "birth_rows"):
        _require(key in stage_a, f"gate_stage_a_incomplete:{key}")
    for key in ("assignment", "existence_rows"):
        _require(key in stage_b, f"gate_stage_b_incomplete:{key}")
    return assert_private_gate({
        "frame_digest": frame_digest,
        "stage_a_seal_sha256": a_seal,
        "stage_b_seal_sha256": b_seal,
        "private_may_open": True,
    })


# --------------------------------------------------------------------------
# 2. entity identity, fragment dominance and the labels
# --------------------------------------------------------------------------

def entity_identity(
    entity: Mapping[str, Any], evidence_instance: Mapping[str, str | None],
) -> dict[str, Any]:
    """Resolve which private object an entity has been collecting evidence of.

    白话：输入一个实体和"历史上每个证据色块对应哪个私有物体"的映射，输出该实体
    的私有身份。取全部带物体的证据中的严格多数（超过一半）；没有严格多数（并列
    或最多者不过半）就判为身份含糊，不另设阈值。例如五条证据里四条是杯子 A、一条
    是杯子 B，身份为 A；三比三则含糊。背景色块（没有物体）不参与投票。它不改实
    体，也不把含糊当成某一种答案。
    """

    counts: dict[str, int] = {}
    keyed = 0
    for item in entity["evidence"]:
        key = evidence_instance.get(f"{item['frame_digest']}|{item['fragment_id']}")
        if key is None:
            continue
        counts[key] = counts.get(key, 0) + 1
        keyed += 1
    keys_seen = sorted(counts)
    if keyed == 0:
        return {
            "key": None, "share": 0.0, "resolvable": False, "reason": "no_keyed_evidence",
            "evidence_keyed": 0, "evidence_total": len(entity["evidence"]), "keys_seen": keys_seen,
        }
    best_key = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
    share = counts[best_key] / keyed
    resolvable = share > 0.5
    return {
        "key": best_key if resolvable else None,
        "share": share,
        "resolvable": resolvable,
        "reason": None if resolvable else "no_strict_majority",
        "evidence_keyed": keyed,
        "evidence_total": len(entity["evidence"]),
        "keys_seen": keys_seen,
    }


#: Engineering (ruling 104-7, 2026-10-03): the teacher resolves the same memory's identities several times per frame (the
#: association targets, the frame evaluation, the Missing residual rate, object correctness), and the next frame's
#: memory_before is that memory again.  The identities are a function of the entities' evidence lists, which the memory
#: digest covers (a canonical sha256 of the whole sealed memory), and of the evidence map, which the teacher only ever
#: extends by new keys (one per labelled fragment, lean_evaluation.EpisodeTeacher.label_frame), so the same map object at
#: the same length holds the same entries.  The memo keys on exactly these three things and keeps the map object itself, so
#: its id cannot be reused while an entry lives; every caller gets its own copy.  The uncached form is kept in the tests.
IDENTITY_MEMO_SIZE = 8
_IDENTITY_MEMO: "OrderedDict[tuple[str, int, int], tuple[Mapping[str, Any], dict[str, dict[str, Any]]]]" = OrderedDict()


def entity_identities(
    memory: Mapping[str, Any], evidence_instance: Mapping[str, str | None],
) -> dict[str, dict[str, Any]]:
    """Identity of every entity in a validated memory, keyed by entity id (memoised per sealed memory, ruling 104-7)."""

    digest = memory.get("memory_digest")
    if type(digest) is not str:
        return {str(entity["entity_id"]): entity_identity(entity, evidence_instance) for entity in memory["entities"]}
    key = (digest, id(evidence_instance), len(evidence_instance))
    hit = _IDENTITY_MEMO.get(key)
    if hit is not None and hit[0] is evidence_instance:
        _IDENTITY_MEMO.move_to_end(key)
        result = hit[1]
    else:
        result = {str(entity["entity_id"]): entity_identity(entity, evidence_instance) for entity in memory["entities"]}
        _IDENTITY_MEMO[key] = (evidence_instance, result)
        _IDENTITY_MEMO.move_to_end(key)
        while len(_IDENTITY_MEMO) > IDENTITY_MEMO_SIZE:
            _IDENTITY_MEMO.popitem(last=False)
    return {entity_id: {**row, "keys_seen": list(row["keys_seen"])} for entity_id, row in result.items()}


def fragment_dominance(overlap: Mapping[str, Any], *, dominance_min_share: float) -> dict[str, Any]:
    """Which private object, if any, dominates one fragment's mask.

    白话：输入一个色块的 mask 与各私有物体实例 mask 的重叠占比（分母是色块全部像
    素，背景是没列出的余量），输出主导物体。没有任何物体记 unlabelled；覆盖两个及
    以上物体且最大占比低于登记阈值、或最大占比并列，记 identity_ambiguous；只覆盖
    一个物体但占比低于阈值（大半是背景）记 unlabelled；否则主导物体成立。例如杯
    子 0.7、书 0.2 是杯子主导；杯子 0.45、书 0.45 是含糊。它不看记忆，不决定目标列。
    """

    threshold = _ratio(dominance_min_share, "dominance_share_invalid")
    _require(type(overlap) is dict, "fragment_overlap_not_object")
    total = 0.0
    for key, share in overlap.items():
        _require(type(key) is str and key, "fragment_overlap_key_invalid")
        total += _ratio(share, "fragment_overlap_share_invalid")
    _require(total <= 1.0 + 1e-9, "fragment_overlap_exceeds_one")
    if not overlap:
        return {"status": "unlabelled", "key": None, "share": 0.0, "instance_count": 0, "reason": "no_instance"}
    ranked = sorted(overlap.items(), key=lambda item: (-float(item[1]), item[0]))
    key, share = ranked[0][0], float(ranked[0][1])
    count = len(ranked)
    tie = count >= 2 and float(ranked[1][1]) == share
    if count >= 2 and (share < threshold or tie):
        return {
            "status": "identity_ambiguous", "key": None, "share": share,
            "instance_count": count, "reason": "fragment_dominance",
        }
    if share < threshold:
        return {
            "status": "unlabelled", "key": None, "share": share,
            "instance_count": count, "reason": "dominant_share_below_threshold",
        }
    return {"status": "dominant", "key": key, "share": share, "instance_count": count, "reason": None}


def _first_opened_at(entity: Mapping[str, Any]) -> int:
    return int(entity["versions"][0]["opened_at"])


def association_targets(
    memory: Mapping[str, Any], *, recall: Mapping[str, Sequence[str]],
    fragment_instance: Mapping[str, Mapping[str, Any]],
    evidence_instance: Mapping[str, str | None],
    dominance_min_share: float,
) -> dict[str, dict[str, Any]]:
    """One target column per fragment, with an explicit status.

    白话：输入旧记忆、封存的召回、本帧每个色块的实例重叠表和历史证据映射，输出每
    个色块该分到哪一列。主导物体不成立按 fragment_dominance 记 unlabelled 或
    identity_ambiguous；记忆里没有这个物体记 birth；有但没被召回记 recall_miss；
    有且被召回则目标是它（重复实体取首版本最早、并列取 ID 最小者；只有重复者被召
    回时以被召回者为目标）；这个物体的证据只落在身份含糊的实体里，记
    identity_ambiguous 而不是猜 birth。它不改召回、不补候选、不重排召回。
    """

    checked = validate_memory(memory, copy=False)  # read only
    _require(type(recall) is dict, "recall_not_object")
    recall_snapshot = clone_json(dict(recall))
    identities = entity_identities(checked, evidence_instance)
    known_ids = set(identities)
    by_key: dict[str, list[Mapping[str, Any]]] = {}
    ambiguous_keys: set[str] = set()
    for entity in checked["entities"]:
        identity = identities[str(entity["entity_id"])]
        if identity["resolvable"]:
            by_key.setdefault(identity["key"], []).append(entity)
        else:
            ambiguous_keys.update(identity["keys_seen"])

    targets: dict[str, dict[str, Any]] = {}
    object_pixels: dict[str, float] = {}
    pixel_counts: dict[str, int] = {}
    for fragment_id in sorted(recall):
        instance = fragment_instance.get(fragment_id)
        _require(
            type(instance) is dict and "overlap" in instance and "pixel_count" in instance,
            f"fragment_instance_missing:{fragment_id}",
        )
        pixel_counts[fragment_id] = _int(instance["pixel_count"], f"fragment_pixel_count_invalid:{fragment_id}", minimum=1)
        recalled = [str(item) for item in recall[fragment_id]]
        for entity_id in recalled:
            _require(entity_id in known_ids, f"recall_entity_unknown:{entity_id}")
        dominance = fragment_dominance(instance["overlap"], dominance_min_share=dominance_min_share)
        record: dict[str, Any] = {
            "key": dominance["key"], "share": dominance["share"],
            "instance_count": dominance["instance_count"], "duplicate_identity_count": 0,
            "reason": dominance["reason"],
        }
        if dominance["status"] != "dominant":
            record.update({"status": dominance["status"], "target": None})
            targets[fragment_id] = record
            continue
        key = dominance["key"]
        matching = sorted(
            by_key.get(key, []),
            key=lambda item: (_first_opened_at(item), str(item["entity_id"])),
        )
        record["duplicate_identity_count"] = max(0, len(matching) - 1)
        if matching:
            recalled_matches = [item for item in matching if str(item["entity_id"]) in recalled]
            if recalled_matches:
                record.update({"status": "labelled", "target": str(recalled_matches[0]["entity_id"])})
            else:
                record.update({"status": "recall_miss", "target": str(matching[0]["entity_id"])})
        elif key in ambiguous_keys:
            record.update({"status": "identity_ambiguous", "target": None, "reason": "entity_identity"})
        else:
            record.update({"status": "birth", "target": f"{BIRTH_COLUMN_PREFIX}{fragment_id}"})
        object_pixels[fragment_id] = float(dominance["share"]) * pixel_counts[fragment_id]
        targets[fragment_id] = record

    # D-224-X ruling X1.  SAM routinely cuts one object into several
    # fragments (seat and back of a chair).  If two of them resolve to the
    # same object and the same target entity in one frame, the executor's
    # one-fragment-per-entity rule makes it impossible to satisfy both, and
    # charging the second to amortization error would blame the student for
    # a structural impossibility.  The fragment with the most pixels on the
    # object keeps the target (ties: larger fragment, then smaller id); the
    # rest become ``duplicate_of_labelled``: excluded from the loss, charged
    # to no class, counted.  Fragments with different targets, birth targets
    # or recall misses are left alone because nothing structural stops them.
    groups: dict[tuple[str, str], list[str]] = {}
    for fragment_id, record in targets.items():
        if record["status"] == "labelled":
            groups.setdefault((str(record["key"]), str(record["target"])), []).append(fragment_id)
    for (_key, keeper_target), members in sorted(groups.items()):
        if len(members) < 2:
            continue
        ranked = sorted(
            members,
            key=lambda item: (-object_pixels[item], -pixel_counts[item], item),
        )
        for fragment_id in ranked[1:]:
            targets[fragment_id].update({
                "status": "duplicate_of_labelled", "target": None,
                "duplicate_of": ranked[0], "reason": "same_object_same_target_this_frame",
            })
            targets[fragment_id]["displaced_target"] = keeper_target
    _require(clone_json(dict(recall)) == recall_snapshot, "teacher_edited_recall")
    return targets


def place_holds(
    centroid: Sequence[float], state: Mapping[str, Any], *, delta_moved_m: float, place_rule: str = EXISTENCE_PLACE_RULE,
) -> tuple[bool, float, str | None]:
    """Is an entity's centroid at its own present object's place?  Returns (holds, distance_m, which test held).

    白话：输入实体记住的质心和它自己那个物体此刻的真值（质心，以及有的话真值框），输出“它是否还在原处”。
    节点主列的规则（裁决 77，裁决 88-4 起存在标签同用）：质心离物体质心不超过 δ_moved，或落在真值框外扩
    0.25 m 内，任一成立即在原处；物体没有真值框时只看质心。例如沙发只看到一侧、表面质心离沙发中心 0.7 m
    但在沙发框里，算在原处。"centroid_only" 是裁决 88 之前的规则，只供诊断对照。它不判断身份，调用方先确认
    实体属于这个物体。
    """

    _require(place_rule in EXISTENCE_PLACE_RULES, "existence_place_rule_unknown")
    delta = _delta(delta_moved_m)
    point = _vector3(centroid, "entity_centroid_invalid")
    distance = _distance(_vector3(state["centroid_m"], "object_centroid_invalid"), point)
    if distance <= delta:
        return True, distance, "centroid"
    if place_rule == "centroid_only":
        return False, distance, None
    lower, upper = state.get("aabb_min_m"), state.get("aabb_max_m")
    if lower is None or upper is None:
        return False, distance, None
    lower = _vector3(lower, "object_box_invalid")
    upper = _vector3(upper, "object_box_invalid")
    inside = all(lo - NODE_BOX_PAD_M <= c <= hi + NODE_BOX_PAD_M for c, lo, hi in zip(point, lower, upper, strict=True))
    return inside, distance, ("padded_box" if inside else None)


def existence_labels(
    memory: Mapping[str, Any], *, candidates: Sequence[str],
    object_state: Mapping[str, Mapping[str, Any]],
    evidence_instance: Mapping[str, str | None],
    delta_moved_m: float, candidate_states: Sequence[str] = EXISTENCE_CANDIDATE_STATES,
    place_rule: str = EXISTENCE_PLACE_RULE,
) -> dict[str, dict[str, Any]]:
    """One gone/present label per existence candidate.

    白话：输入旧记忆、本帧的存在判定候选、每个私有物体当前是否存在及在哪里（质心，有的话还有真值框），
    输出每个候选是"已不在原处"还是"仍在"。物体已被移出场景记 gone；物体在场时，实体按节点主列的地点规则
    （质心 ≤ δ_moved 或落在真值框外扩 0.25 m 内，裁决 77；裁决 88-4 起标签同用）对自己的物体不成立才记
    gone，否则 present；身份含糊的候选记 identity_ambiguous。在原处的重复实体因此记 present，冗余交给共享
    去重。候选状态不在登记集合内（例如 retracted）直接拒绝而不是跳过，因为那说明上游把不该判的实体送了
    进来。它不知道候选是否本该被看见，那由 S0-03 的应可见比例决定谁进候选。``place_rule="centroid_only"``
    是裁决 88 之前的规则，只供决定上限诊断对照。
    """

    checked = validate_memory(memory, copy=False)  # read only
    delta = _delta(delta_moved_m)
    _require(place_rule in EXISTENCE_PLACE_RULES, "existence_place_rule_unknown")
    eligible = _states(candidate_states, "existence_candidate_states_invalid")
    by_id = {str(entity["entity_id"]): entity for entity in checked["entities"]}
    _require(len(set(candidates)) == len(list(candidates)), "existence_candidate_duplicate")
    labels: dict[str, dict[str, Any]] = {}
    for entity_id in candidates:
        _require(entity_id in by_id, f"existence_candidate_unknown:{entity_id}")
        entity = by_id[entity_id]
        _require(
            entity["state"] in eligible,
            f"existence_candidate_state_not_eligible:{entity_id}:{entity['state']}",
        )
        identity = entity_identity(entity, evidence_instance)
        if not identity["resolvable"]:
            labels[entity_id] = {"status": "identity_ambiguous", "key": None, "reason": identity["reason"]}
            continue
        key = identity["key"]
        state = object_state.get(key)
        _require(type(state) is dict and "present" in state, f"object_state_missing:{key}")
        if state["present"] is not True:
            labels[entity_id] = {"status": "gone", "key": key, "reason": "absent"}
            continue
        holds, displacement, test = place_holds(entity["centroid_m"], state, delta_moved_m=delta, place_rule=place_rule)
        if not holds:
            labels[entity_id] = {"status": "gone", "key": key, "reason": "moved", "displacement_m": displacement}
        else:
            labels[entity_id] = {"status": "present", "key": key, "reason": None, "displacement_m": displacement,
                                 "place_test": test}
    return labels


# --------------------------------------------------------------------------
# 3. three-way decomposition
# --------------------------------------------------------------------------

def decompose_frame(
    *, targets: Mapping[str, Mapping[str, Any]], assignment: Mapping[str, str],
    existence: Mapping[str, Mapping[str, Any]], decisions: Mapping[str, str],
) -> dict[str, Any]:
    """Count where every decision of one frame landed; classes are exclusive and additive.

    白话：输入本帧的标签、学生的分配和存在决定，输出三分解计数。recall_miss 是正确
    实体不在召回里，学生无从选起；teacher_error 是标签本身含糊、无法评判；
    amortization_error 是标签明确、候选也在，学生仍然选错（含假撤回与漏撤回）。
    每个决定恰好落入 recall_miss / teacher_error / amortization_error / correct /
    unlabelled / duplicate_of_labelled 之一，六类之和等于决定总数；分配与标签、决定
    与候选的集合必须一一对应，缺一个或多一个都拒绝。它不把未标注色块算进任何错误。
    同帧被折叠的重复色块和它的保留块按一组判：组内任一块分到了目标实体、且没有一块
    被绑到别的既有实体，保留块记 correct；否则记 amortization_error。哪一块去承载物
    体是学生的选择，teacher 只挑保留块来放标签，不能反过来因此扣分。
    """

    _require(set(assignment) == set(targets), "assignment_fragments_differ_from_targets")
    _require(set(decisions) == set(existence), "decisions_differ_from_existence_candidates")

    # D-224-X ruling X1, group accounting (correction after review, LOG-225).
    # The keeper carries the target for the whole group; the student may put
    # the object on the target through any member.  Duplicates stay charged
    # to no class; the keeper is judged on the group.
    groups: dict[str, list[str]] = {}
    for fragment_id, target in targets.items():
        if target["status"] == "duplicate_of_labelled":
            keeper = str(target["duplicate_of"])
            _require(
                keeper in targets and targets[keeper]["status"] == "labelled",
                f"duplicate_keeper_invalid:{fragment_id}",
            )
            groups.setdefault(keeper, []).append(str(fragment_id))

    association = {
        "fragments": 0, "unlabelled": 0, "duplicate_of_labelled": 0, "recall_miss": 0,
        "teacher_error": 0, "correct": 0, "amortization_error": 0, "birth_targets": 0,
    }
    for fragment_id in sorted(targets):
        target = targets[fragment_id]
        status = target["status"]
        _require(status in ASSOCIATION_STATUSES, "association_status_unknown")
        chosen = assignment[fragment_id]
        _require(type(chosen) is str and chosen, "assignment_value_invalid")
        _require(
            not chosen.startswith(BIRTH_COLUMN_PREFIX) or chosen == f"{BIRTH_COLUMN_PREFIX}{fragment_id}",
            "assignment_took_another_fragments_birth_column",
        )
        association["fragments"] += 1
        if status == "unlabelled":
            association["unlabelled"] += 1
        elif status == "duplicate_of_labelled":
            association["duplicate_of_labelled"] += 1
        elif status == "recall_miss":
            association["recall_miss"] += 1
        elif status == "identity_ambiguous":
            association["teacher_error"] += 1
        else:
            if status == "birth":
                association["birth_targets"] += 1
            wanted = str(target["target"])
            members = [fragment_id] + sorted(groups.get(fragment_id, []))
            reached = any(str(assignment[member]) == wanted for member in members)
            misbound = any(
                not str(assignment[member]).startswith(BIRTH_COLUMN_PREFIX)
                and str(assignment[member]) != wanted
                for member in members
            )
            if reached and not misbound:
                association["correct"] += 1
            else:
                association["amortization_error"] += 1

    existence_counts = {
        "candidates": 0, "teacher_error": 0, "correct": 0, "false_retract": 0, "missed_retract": 0,
    }
    for entity_id in sorted(existence):
        label = existence[entity_id]
        _require(label["status"] in EXISTENCE_STATUSES, "existence_status_unknown")
        decision = decisions[entity_id]
        _require(decision in {"RETRACT", "NOOP"}, "decision_not_retract_or_noop")
        existence_counts["candidates"] += 1
        if label["status"] == "identity_ambiguous":
            existence_counts["teacher_error"] += 1
            continue
        gone = label["status"] == "gone"
        if decision == "RETRACT" and gone:
            existence_counts["correct"] += 1
        elif decision == "NOOP" and not gone:
            existence_counts["correct"] += 1
        elif decision == "RETRACT":
            existence_counts["false_retract"] += 1
        else:
            existence_counts["missed_retract"] += 1

    totals = {
        "recall_miss": association["recall_miss"],
        "teacher_error": association["teacher_error"] + existence_counts["teacher_error"],
        "amortization_error": (
            association["amortization_error"]
            + existence_counts["false_retract"] + existence_counts["missed_retract"]
        ),
        "correct": association["correct"] + existence_counts["correct"],
        "unlabelled": association["unlabelled"],
        "duplicate_of_labelled": association["duplicate_of_labelled"],
        "decisions": association["fragments"] + existence_counts["candidates"],
    }
    _require(
        totals["recall_miss"] + totals["teacher_error"] + totals["amortization_error"]
        + totals["correct"] + totals["unlabelled"] + totals["duplicate_of_labelled"]
        == totals["decisions"],
        "decomposition_not_additive",
    )
    return {"association": association, "existence": existence_counts, "totals": totals}


# --------------------------------------------------------------------------
# 4. the evaluator's own box matching and the per-frame metrics
# --------------------------------------------------------------------------

def _max_weight_matching(weights: Sequence[Sequence[float]], *, count_first: bool = False) -> list[tuple[int, int]]:
    """Maximum total weight matching over positive weights, evaluator-owned.

    ``count_first`` (D-224-S1 ruling 76 (3)(a), what both node columns use): the most pairs first, and among
    matchings with that many pairs the most weight.  Every positive cell of a component is lifted by a
    constant larger than the component's size before the same solve: with weights in (0, 1], a matching
    of k pairs then weighs more than k * lift and one of k - 1 pairs less than (k - 1) * (lift + 1),
    which is smaller whenever lift + 1 > k.

    A plain augmenting-path assignment on ``-weight`` with zero-weight cells
    treated as unmatched.  It is written here on purpose: the numbers that
    judge the method's solver must not be produced by that solver.

    D-224-X ruling X5: the dense solve is applied per connected component of
    the positive-weight graph instead of to the whole padded matrix.  Most
    components are one entity against one truth box, so the cubic cost of
    the padded solve (measured 3.1 s per frame at 300 entities × 100 truth
    objects) collapses; the matched count and total weight are identical,
    which is all any metric reads.
    """

    rows = len(weights)
    if rows == 0:
        return []
    columns = len(weights[0])
    if columns == 0:
        return []
    pairs: list[tuple[int, int]] = []
    for component_rows, component_columns in _positive_components(weights):
        lift = float(len(component_rows) + len(component_columns) + 1) if count_first else 0.0
        block = [
            [(lift + float(weights[row][column])) if float(weights[row][column]) > 0.0 else 0.0
             for column in component_columns]
            for row in component_rows
        ]
        for local_row, local_column in _max_weight_matching_dense(block):
            pairs.append((component_rows[local_row], component_columns[local_column]))
    return sorted(pairs)


def _positive_components(
    weights: Sequence[Sequence[float]],
) -> list[tuple[list[int], list[int]]]:
    """Connected components of the bipartite graph of positive cells, in row order."""

    rows = len(weights)
    columns = len(weights[0])
    row_edges = [[c for c in range(columns) if float(weights[r][c]) > 0.0] for r in range(rows)]
    column_edges: dict[int, list[int]] = {}
    for row, cells in enumerate(row_edges):
        for column in cells:
            column_edges.setdefault(column, []).append(row)
    seen_rows: set[int] = set()
    seen_columns: set[int] = set()
    components: list[tuple[list[int], list[int]]] = []
    for start in range(rows):
        if start in seen_rows or not row_edges[start]:
            continue
        stack_rows = [start]
        seen_rows.add(start)
        component_rows: list[int] = []
        component_columns: set[int] = set()
        while stack_rows:
            row = stack_rows.pop()
            component_rows.append(row)
            for column in row_edges[row]:
                if column in seen_columns:
                    continue
                seen_columns.add(column)
                component_columns.add(column)
                for other in column_edges[column]:
                    if other not in seen_rows:
                        seen_rows.add(other)
                        stack_rows.append(other)
        components.append((sorted(component_rows), sorted(component_columns)))
    return components


def _max_weight_matching_dense(weights: Sequence[Sequence[float]]) -> list[tuple[int, int]]:
    """The padded square Hungarian solve, applied to one component."""

    rows = len(weights)
    columns = len(weights[0])
    size = rows + columns
    cost = [[0.0] * size for _ in range(size)]
    for row in range(rows):
        for column in range(columns):
            cost[row][column] = -float(weights[row][column])
    u = [0.0] * (size + 1)
    v = [0.0] * (size + 1)
    match = [0] * (size + 1)
    path = [0] * (size + 1)
    for row in range(1, size + 1):
        match[0] = row
        free = 0
        minimum = [math.inf] * (size + 1)
        used = [False] * (size + 1)
        while True:
            used[free] = True
            current = match[free]
            delta = math.inf
            nxt = 0
            for column in range(1, size + 1):
                if used[column]:
                    continue
                candidate = cost[current - 1][column - 1] - u[current] - v[column]
                if candidate < minimum[column]:
                    minimum[column] = candidate
                    path[column] = free
                if minimum[column] < delta:
                    delta = minimum[column]
                    nxt = column
            for column in range(size + 1):
                if used[column]:
                    u[match[column]] += delta
                    v[column] -= delta
                else:
                    minimum[column] -= delta
            free = nxt
            if match[free] == 0:
                break
        while free:
            previous = path[free]
            match[free] = match[previous]
            free = previous
    pairs: list[tuple[int, int]] = []
    for column in range(1, size + 1):
        row = match[column]
        if 1 <= row <= rows and column <= columns and weights[row - 1][column - 1] > 0.0:
            pairs.append((row - 1, column - 1))
    return sorted(pairs)


def structural_type_of(object_key: str) -> str:
    """The ProcTHOR type prefix of a private object key: everything up to the first ``|``."""

    _require(type(object_key) is str and object_key, "object_key_invalid")
    return object_key.split("|", 1)[0]


def in_truth_node_scope(object_key: str, *, observable_before: bool) -> bool:
    """D-224-S1 ruling 56 continued: the in_scope flag the truth table must carry.

    白话：真值表里每个物体的 ``in_scope`` 由这里算：此前至少可观测过一次，并且不是墙、房间（地面）、
    门、窗这四类房屋结构件。例如 ``wall|6|...`` 永远不在范围内，``Mug|surface|2|4`` 被看见过一次
    之后就在范围内。它不删除真值表里的行，只决定该行进不进节点指标的分母。
    """

    _require(observable_before in {True, False}, "observable_before_invalid")
    return (bool(observable_before) and structural_type_of(object_key) not in STRUCTURAL_TYPES_EXCLUDED
            and not is_spawned_after_reload(object_key))


def is_spawned_after_reload(object_key: str) -> bool:
    """D-224-S1 ruling 69: does the key's last ``|`` field carry a spawn tag (``EggCracked_0``)?

    白话：鸡蛋碎裂、面包切片这类物理事件会在运行时生成新物体，它们重载时不存在、没有初始盒；
    它们的私有键最后一段是"字母_数字"的生成标签。这样的键记在场、范围外、无盒并计数，不算数据
    损坏。普通键的最后一段是纯数字，不会误判。
    """

    _require(type(object_key) is str and object_key, "object_key_invalid")
    fields = object_key.split("|")
    return len(fields) >= 2 and SPAWN_TAG.fullmatch(fields[-1]) is not None


def _truth_table(truth_objects: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    table: dict[str, dict[str, Any]] = {}
    for key in sorted(truth_objects):
        record = truth_objects[key]
        _require(type(key) is str and key and type(record) is dict, f"truth_object_invalid:{key}")
        _require(record.get("present") in {True, False}, f"truth_object_present_invalid:{key}")
        _require(record.get("in_scope") in {True, False}, f"truth_object_in_scope_invalid:{key}")
        # ruling 56 continued: a structural object marked in scope is a malformed table, not a judgement call
        _require(not (record["in_scope"] and structural_type_of(key) in STRUCTURAL_TYPES_EXCLUDED),
                 f"truth_object_structural_in_scope:{key}")
        _require(not (record["in_scope"] and is_spawned_after_reload(key)), f"truth_object_spawned_in_scope:{key}")
        entry: dict[str, Any] = {"present": record["present"], "in_scope": record["in_scope"]}
        # A present in-scope object must carry its box and centroid: they enter the matching and
        # the stale test.  A present object *outside* the scope (S2-01: the structural types, which
        # never enter the simulator's object metadata and so have no box) may carry none; the
        # evaluator only counts the entities that resolve to it, and never reads its geometry.
        has_box = record.get("aabb_min_m") is not None or record.get("aabb_max_m") is not None
        if record["present"] and (record["in_scope"] or has_box):
            entry["centroid_m"] = _vector3(record.get("centroid_m"), f"truth_object_centroid_invalid:{key}")
            lower = _vector3(record.get("aabb_min_m"), f"truth_object_aabb_invalid:{key}")
            upper = _vector3(record.get("aabb_max_m"), f"truth_object_aabb_invalid:{key}")
            _require(all(a <= b for a, b in zip(lower, upper, strict=True)), f"truth_object_aabb_invalid:{key}")
            entry["aabb_min_m"], entry["aabb_max_m"] = lower, upper
        table[key] = entry
    return table


def evaluate_frame(
    memory_after: Mapping[str, Any], *, truth_objects: Mapping[str, Mapping[str, Any]],
    evidence_instance: Mapping[str, str | None], iou_min: float, delta_moved_m: float,
    present_states: Sequence[str] = MEMORY_PRESENT_STATES,
) -> dict[str, Any]:
    """Node precision/recall/F1, stale entities and the contamination fraction for one frame.

    白话：输入提交后的记忆、本帧真值物体表（范围内每个物体是否在场及其框）和历史
    证据映射，输出节点级精确率、召回率、F1，以及本帧的"污染占比"。预测集合是状
    态在登记的"仍在记忆里"集合（推荐 active 与 dormant）中的实体。裁决 72 (B) 后主列
    的匹配是"实体质心到真值质心的距离不超过已冻结的 δ_moved"、权重 1/(1+距离)，
    按"先最大匹配数、再最大权"配对（裁决 76 (3)(a)：F1 数的是对数，权重只在对数相同时偏向更近的对），
    回答"实体记在了对的地方吗"，是选参指标；同一批实体与真值、同一个匹配器
    再按三维交并比 ≥ 0.3（Dyn-THOR 原口径）算一列次级指标 ``node_prf1_iou``，回答"框
    重叠够吗"，不选配置、不进主门。陈旧实体是仍在记忆里、但
    其物体已不在它记住的位置的实体；错误缺席是范围内在场、但记忆里没有任何该身份
    实体在其位置附近的物体。污染占比 =（陈旧＋错误缺席）/（记忆里的实体＋错误缺
    席）。它不评价撤回决定本身，那由假撤回率单独算。
    """

    checked = validate_memory(memory_after, copy=False)  # read only
    threshold = _ratio(iou_min, "iou_min_invalid")
    delta = _delta(delta_moved_m)
    states = _states(present_states, "present_states_invalid")
    truth = _truth_table(truth_objects)
    identities = entity_identities(checked, evidence_instance)
    in_memory = [entity for entity in checked["entities"] if entity["state"] in states]
    # D-224-X ruling X6: the table carries every private object any entity can
    # resolve to, with an ``in_scope`` flag; the truth node scope (present and
    # observable at least once) is applied here, not by pre-filtering the
    # table, so an entity resolving to an out-of-scope object is a counted
    # case instead of a crash.
    present_keys = [key for key in sorted(truth) if truth[key]["present"] and truth[key]["in_scope"]]
    # Correction after review (LOG-225): the scope rule removed those objects
    # from the recall side, so an entity that resolves to a *present* object
    # outside the scope leaves the precision denominator too, instead of
    # being counted as a false positive it can never match.  It is counted.
    # An entity whose object is absent stays in and is judged stale as usual.
    out_of_scope: list[str] = []
    predictions: list[Mapping[str, Any]] = []
    for entity in in_memory:
        identity = identities[str(entity["entity_id"])]
        if identity["resolvable"]:
            key = identity["key"]
            _require(key in truth, f"truth_object_unknown:{key}")
            if truth[key]["present"] is True and truth[key]["in_scope"] is not True:
                out_of_scope.append(str(entity["entity_id"]))
                continue
        predictions.append(entity)

    # D-224-S1 ruling 72 (B): the primary column -- nearer pairs weighted higher; ruling 77 (1)(a): the pair must be the
    # entity's own object, and its centroid within delta or inside the truth box padded by NODE_BOX_PAD_M
    def _qualifies(entity: Mapping[str, Any], key: str) -> bool:
        identity = identities[str(entity["entity_id"])]
        if not identity["resolvable"] or identity["key"] != key:
            return False
        if _distance(entity["centroid_m"], truth[key]["centroid_m"]) <= delta:
            return True
        return all(float(lo) - NODE_BOX_PAD_M <= float(c) <= float(hi) + NODE_BOX_PAD_M
                   for c, lo, hi in zip(entity["centroid_m"], truth[key]["aabb_min_m"], truth[key]["aabb_max_m"], strict=True))

    weights = [
        [
            (1.0 / (1.0 + _distance(entity["centroid_m"], truth[key]["centroid_m"]))) if _qualifies(entity, key) else 0.0
            for key in present_keys
        ]
        for entity in predictions
    ]
    pairs = _max_weight_matching(weights, count_first=True)
    matched = len(pairs)
    precision, recall, f1 = _precision_recall_f1(matched, len(predictions), len(present_keys))
    # the secondary column -- the same two sets and the same matcher with ruling C's 3D IoU >= iou_min test
    overlapping = _boxes_overlap(predictions, [truth[key] for key in present_keys])
    iou_weights = [
        [
            (lambda iou: iou if iou >= threshold else 0.0)(_aabb_iou(
                entity["aabb_min_m"], entity["aabb_max_m"],
                truth[key]["aabb_min_m"], truth[key]["aabb_max_m"],
            )) if overlapping[row][column] else 0.0
            for column, key in enumerate(present_keys)
        ]
        for row, entity in enumerate(predictions)
    ]
    iou_pairs = _max_weight_matching(iou_weights, count_first=True)
    iou_precision, iou_recall, iou_f1 = _precision_recall_f1(len(iou_pairs), len(predictions), len(present_keys))

    stale: list[str] = []
    ambiguous: list[str] = []
    carriers_near: dict[str, bool] = {key: False for key in present_keys}
    for entity in predictions:
        entity_id = str(entity["entity_id"])
        identity = identities[entity_id]
        if not identity["resolvable"]:
            ambiguous.append(entity_id)
            continue
        key = identity["key"]
        _require(key in truth, f"truth_object_unknown:{key}")
        record = truth[key]
        if record["present"] is not True:
            stale.append(entity_id)
        elif _distance(record["centroid_m"], entity["centroid_m"]) > delta:
            stale.append(entity_id)
        else:
            _require(key in carriers_near, f"truth_object_scope_inconsistent:{key}")
            carriers_near[key] = True
    wrongly_absent = [key for key in present_keys if not carriers_near[key]]
    denominator = len(predictions) + len(wrongly_absent)
    contamination = (len(stale) + len(wrongly_absent)) / denominator if denominator else 0.0
    return {
        "node_precision": precision,
        "node_recall": recall,
        "node_f1": f1,
        "matched": matched,
        "predicted": len(predictions),
        "truth": len(present_keys),
        "matched_pairs": [(str(predictions[row]["entity_id"]), present_keys[column]) for row, column in pairs],
        "node_prf1_iou": {
            "node_precision": iou_precision, "node_recall": iou_recall, "node_f1": iou_f1,
            "matched": len(iou_pairs), "predicted": len(predictions), "truth": len(present_keys),
        },
        "iou_matched_pairs": [(str(predictions[row]["entity_id"]), present_keys[column]) for row, column in iou_pairs],
        "stale_entities": stale,
        "wrongly_absent_objects": wrongly_absent,
        "identity_ambiguous_entities": ambiguous,
        "out_of_scope_entities": out_of_scope,
        "contamination_fraction": contamination,
    }


def missing_residual_rate(
    memory_after: Mapping[str, Any], *, evidence_instance: Mapping[str, str | None],
    missing_objects: Mapping[str, Mapping[str, Any]], delta_moved_m: float,
    present_states: Sequence[str] = MEMORY_PRESENT_STATES,
) -> dict[str, Any]:
    """Share of missing objects still represented at their old place (Dyn-THOR MRR).

    白话：输入提交后的记忆、历史证据映射和"已被移走或搬走的物体及其原位置、原位置
    是否已对方法可观察"，输出这些物体中仍有一个在记忆里（推荐 active 或 dormant）
    的同身份实体留在原位置的比例。分母只算原位置已经可观察过的物体：还没重访过的
    地方，任何方法都无从清理，单独计数。例如三件被搬走且都重访过，两件的旧记录
    还挂在原位，残留率 2/3。它不惩罚在新位置正确恢复的实体，只看旧位置有没有清干净。
    """

    checked = validate_memory(memory_after, copy=False)  # read only
    delta = _delta(delta_moved_m)
    states = _states(present_states, "present_states_invalid")
    identities = entity_identities(checked, evidence_instance)
    in_memory = [entity for entity in checked["entities"] if entity["state"] in states]
    judged: list[str] = []
    waiting: list[str] = []
    for key in sorted(missing_objects):
        record = missing_objects[key]
        _require(type(record) is dict, f"missing_object_invalid:{key}")
        _vector3(record.get("old_centroid_m"), f"missing_object_old_centroid_invalid:{key}")
        observable = record.get("old_place_observable_since_intervention")
        _require(observable in {True, False}, f"missing_object_observability_invalid:{key}")
        (judged if observable else waiting).append(key)
    residual: list[str] = []
    ambiguous_near_old_place: list[str] = []
    for key in judged:
        old = missing_objects[key]["old_centroid_m"]
        for entity in in_memory:
            if _distance(entity["centroid_m"], old) > delta:
                continue
            identity = identities[str(entity["entity_id"])]
            if not identity["resolvable"]:
                ambiguous_near_old_place.append(str(entity["entity_id"]))
            elif identity["key"] == key and key not in residual:
                residual.append(key)
    return {
        "missing_residual_rate": (len(residual) / len(judged)) if judged else None,
        "residual": len(residual),
        "judged": len(judged),
        "not_yet_observable": len(waiting),
        "residual_keys": residual,
        "identity_ambiguous_near_old_place": sorted(set(ambiguous_near_old_place)),
    }


def false_retract_rate(
    existence: Mapping[str, Mapping[str, Any]], decisions: Mapping[str, str],
) -> dict[str, Any]:
    """Share of RETRACT decisions whose object was still in place.

    白话：输入存在标签与存在决定，输出被撤回的实体中真值仍在原处的比例；身份含糊
    的撤回不进分母，只计数。例如撤回了三个，一个其实还在，假撤回率 1/3。
    """

    _require(set(decisions) == set(existence), "decisions_differ_from_existence_candidates")
    retracts = [entity_id for entity_id in sorted(decisions) if decisions[entity_id] == "RETRACT"]
    judged = [entity_id for entity_id in retracts if existence[entity_id]["status"] in {"gone", "present"}]
    ambiguous = len(retracts) - len(judged)
    wrong = sum(1 for entity_id in judged if existence[entity_id]["status"] == "present")
    return {
        "false_retract_rate": (wrong / len(judged)) if judged else None,
        "false_retracts": wrong,
        "judged_retracts": len(judged),
        "ambiguous_retracts": ambiguous,
    }


def false_retract_rate_in_scope(
    existence: Mapping[str, Mapping[str, Any]], decisions: Mapping[str, str],
) -> dict[str, Any]:
    """false_retract_rate without the candidates labelled present by rule for out-of-scope objects (ruling 80-5 (b)).

    白话：输入同 false_retract_rate，输出只算"节点范围内"候选的假撤回率。墙、门、窗、房间、天花板和运行时生成物
    按规则一律记 present，撤回它们在原列里算假撤回，但节点指标从不计它们；这一列把它们剔出分母，与节点范围一致。
    例如撤回了 10 个，其中 7 个是墙，另外 3 个里 1 个其实还在，原列 8/10，这一列 1/3。它不替代原列，也不进主门。
    """

    _require(set(decisions) == set(existence), "decisions_differ_from_existence_candidates")
    kept = [entity_id for entity_id in existence if existence[entity_id].get("reason") not in PRESENT_BY_RULE_REASONS]
    return false_retract_rate({e: existence[e] for e in kept}, {e: decisions[e] for e in kept})


def identity_continuity(
    *, reobserved: Mapping[str, str], carriers_before_move: Mapping[str, Sequence[str]],
    assignment: Mapping[str, str],
) -> dict[str, Any]:
    """Share of moved objects whose first labelled re-observation kept a pre-move entity id.

    白话：输入本帧首次重见的被搬动物体及其色块、搬动前承载该物体的全部实体 ID，
    以及学生分配，输出保住原身份的比例。判定时刻是搬动后第一次带标签的重见，看
    的是当时的分配（BIND/REACTIVATE 到搬动前任一承载实体即算保住）；此后共享去重
    把新实体折进旧实体（canonical_of）不予承认，因为那是无学习的共享规则。裁决
    102-0（2026-10-02）起分母是全部重见事件（events，与臂无关），搬动前没有任何
    实体承载的物体记“没接回”并单独计数；只数有承载实体的那部分（judged）是裁决
    之前的条件定义，留作诊断列。例如 4 个重见事件、3 个有承载实体、接回 1 个：
    本列 1/4，条件列 1/3。它只看被搬动且重见的物体。
    """

    kept = 0
    judged = 0
    no_prior = 0
    for key in sorted(reobserved):
        fragment_id = reobserved[key]
        _require(fragment_id in assignment, f"assignment_missing_fragment:{fragment_id}")
        carriers = [str(item) for item in carriers_before_move.get(key, [])]
        if not carriers:
            no_prior += 1
            continue
        judged += 1
        if assignment[fragment_id] in carriers:
            kept += 1
    events = judged + no_prior
    return {
        "identity_continuity": (kept / events) if events else None,
        "kept": kept,
        "events": events,
        "judged": judged,
        "no_prior_carrier": no_prior,
    }


def _unit_vector(values: Sequence[float], code: str) -> list[float]:
    vector = [_finite(v, code) for v in values]
    norm = math.sqrt(sum(v * v for v in vector))
    _require(norm > 0.0, code)
    return [v / norm for v in vector]


def retrieval_success(
    memory_after: Mapping[str, Any], *, queries: Mapping[str, Sequence[float]], object_state: Mapping[str, Mapping[str, Any]],
    evidence_instance: Mapping[str, str | None], delta_moved_m: float, present_states: Sequence[str] = MEMORY_PRESENT_STATES,
) -> dict[str, Any]:
    """Ruling 102-5: retrieval success of the events of one frame.

    白话：输入这一帧提交后的记忆、这一帧要考的被搬动物体及其查询向量（评价器用私有标签从搬动前的色块描述子算出，方法看不到）、
    物体此刻的真值与证据映射，输出考了几个、成功几个、候选为空几个。每个事件在记忆里全部 active／dormant 实体中按
    descriptor_mean 的余弦取最像的一个（并列取 entity_id 小者），它的多数身份就是这个物体、且按节点主列的地点规则在物体此刻的
    位置，就算成功。例如只学关联的方法在旧位置留着杯子的陈旧实体、在新位置又新建了一个，旧实体更像查询，就会被拿错，记失败。
    """

    candidates = [entity for entity in memory_after["entities"] if entity["state"] in present_states]
    unit = {str(entity["entity_id"]): _unit_vector(entity["descriptor_mean"], "entity_descriptor_invalid") for entity in candidates}
    by_id = {str(entity["entity_id"]): entity for entity in candidates}
    out: dict[str, Any] = {"successes": 0, "events": 0, "empty_candidates": 0, "per_object": {}}
    for key in sorted(queries):
        out["events"] += 1
        query = _unit_vector(queries[key], "retrieval_query_invalid")
        if not candidates:
            out["empty_candidates"] += 1
            out["per_object"][str(key)] = {"retrieved": None, "success": False, "reason": "empty_candidates"}
            continue
        scored = sorted(((-sum(a * b for a, b in zip(query, unit[entity_id], strict=True)), entity_id) for entity_id in unit))
        cosine, retrieved = -scored[0][0], scored[0][1]
        identity = entity_identity(by_id[retrieved], evidence_instance)
        state = object_state.get(str(key)) or {"present": False}
        success = bool(identity["resolvable"] and identity["key"] == str(key) and state.get("present")
                       and place_holds(by_id[retrieved]["centroid_m"], state, delta_moved_m=delta_moved_m)[0])
        out["successes"] += int(success)
        out["per_object"][str(key)] = {"retrieved": retrieved, "cosine": cosine, "retrieved_identity": identity["key"],
                                       "success": success}
    return out


def retrieval_success_block(*, successes: int, events: int, no_query: int, empty_candidates: int) -> dict[str, Any]:
    """The episode report block of retrieval success from its summed counts; no event -> None, never 0."""

    for name, value in (("successes", successes), ("events", events), ("no_query", no_query), ("empty_candidates", empty_candidates)):
        _require(type(value) is int and value >= 0, f"retrieval_count_invalid:{name}")
    _require(successes <= events and empty_candidates <= events, "retrieval_count_invalid:successes")
    return {"retrieval_success": (successes / events) if events else None, "successes": successes, "events": events,
            "no_query": no_query, "empty_candidates": empty_candidates}


def identity_continuity_blocks(*, kept: int, judged: int, no_prior_carrier: int) -> dict[str, dict[str, Any]]:
    """The two report blocks of an episode from its summed counts: identity_continuity (ruling 102-0) and the conditional column.

    白话：输入一条 episode 累计的接回数、有承载实体的事件数与没有承载实体的事件数，输出两块报告：主列
    identity_continuity＝接回数 ÷ 全部重见事件数（各臂同一批事件），诊断列 identity_continuity_conditional＝
    接回数 ÷ 有承载实体的事件数（裁决之前的定义）。没有事件时值为 None，不填 0。
    """

    for name, value in (("kept", kept), ("judged", judged), ("no_prior_carrier", no_prior_carrier)):
        _require(type(value) is int and value >= 0, f"identity_continuity_count_invalid:{name}")
    _require(kept <= judged, "identity_continuity_count_invalid:kept")
    events = judged + no_prior_carrier
    return {
        "identity_continuity": {"identity_continuity": (kept / events) if events else None, "kept": kept, "events": events,
                                "no_prior_carrier": no_prior_carrier},
        "identity_continuity_conditional": {"identity_continuity": (kept / judged) if judged else None, "kept": kept,
                                            "judged": judged},
    }


def object_memory_correct(
    memory_after: Mapping[str, Any], *, evidence_instance: Mapping[str, str | None],
    key: str, expectation: Mapping[str, Any], delta_moved_m: float,
    present_states: Sequence[str] = MEMORY_PRESENT_STATES,
) -> bool:
    """Is the memory's state for one intervened object correct?

    白话：输入提交后的记忆、历史证据映射、一个被干预物体的身份和干预类型，输出记
    忆对它是否正确。移走：旧位置附近没有任何该身份的在记忆里实体；新增：新位置附
    近有一个；搬动：旧位置附近没有且新位置附近有。例如杯子搬走后旧实体仍 active
    在旧位置，记忆不正确。它不看身份是否连续，那由身份连续率负责。
    """

    checked = validate_memory(memory_after, copy=False)  # read only
    delta = _delta(delta_moved_m)
    states = _states(present_states, "present_states_invalid")
    kind = expectation.get("kind")
    _require(kind in {"removed", "moved", "added"}, "expectation_kind_invalid")
    identities = entity_identities(checked, evidence_instance)
    carriers = [
        entity for entity in checked["entities"]
        if entity["state"] in states and identities[str(entity["entity_id"])]["key"] == key
    ]

    def near(centroid: Any) -> bool:
        point = _vector3(centroid, "expectation_centroid_invalid")
        return any(_distance(entity["centroid_m"], point) <= delta for entity in carriers)

    if kind == "removed":
        return not near(expectation.get("old_centroid_m"))
    if kind == "added":
        return near(expectation.get("new_centroid_m"))
    return (not near(expectation.get("old_centroid_m"))) and near(expectation.get("new_centroid_m"))


def episode_recovery_latency(frames: Sequence[Mapping[str, Mapping[str, bool]]]) -> dict[str, Any]:
    """Frames from first post-intervention observability to memory correctness.

    白话：输入逐帧、逐物体的两个布尔量（干预处本帧对方法是否可观察、记忆对它是否
    正确），输出每个物体从干预后第一次可观察到记忆正确所经过的帧数。起点是第一次
    可观察的帧而不是干预发生的帧：看不见的时候方法不可能反应。例如杯子在第 10 帧
    可观察、第 13 帧记忆才正确，延迟 3；到 episode 结束都不正确记为未恢复，单独列
    出、不进平均；从未可观察的物体也单独列出。它不评价没有干预的物体。
    """

    first_observable: dict[str, int] = {}
    recovered_at: dict[str, int] = {}
    keys: set[str] = set()
    for index, frame in enumerate(frames):
        _require(type(frame) is dict, "recovery_frame_not_object")
        for key, flags in frame.items():
            _require(type(flags) is dict and set(flags) == {"observable", "correct"}, f"recovery_flags_invalid:{key}")
            _require(flags["observable"] in {True, False} and flags["correct"] in {True, False}, f"recovery_flags_invalid:{key}")
            keys.add(key)
            if flags["observable"] and key not in first_observable:
                first_observable[key] = index
            if key in first_observable and key not in recovered_at and flags["correct"]:
                recovered_at[key] = index
    per_object = {
        key: (recovered_at[key] - first_observable[key]) if key in recovered_at else None
        for key in sorted(keys) if key in first_observable
    }
    finite = [value for value in per_object.values() if value is not None]
    return {
        "recovery_latency_frames": (sum(finite) / len(finite)) if finite else None,
        "recovered": len(finite),
        "unrecovered": sorted(key for key, value in per_object.items() if value is None),
        "never_observable": sorted(key for key in keys if key not in first_observable),
        "per_object": per_object,
    }


def contamination_auc(contamination_series: Sequence[float]) -> dict[str, Any]:
    """Area under the per-frame contamination fraction, trapezoid rule, unit-normalised.

    白话：输入逐帧的污染占比（evaluate_frame 的 contamination_fraction），输出它对
    帧数的梯形积分再除以帧数减一，即归一化的曲线下面积，落在 [0,1]。一次错误若
    持续十帧，面积就是十帧的累加，因此"错得久"比"错一下就改"分高。单帧序列取
    该帧的值。它不区分错误类型，那由三分解负责。
    """

    values = [_ratio(value, "contamination_fraction_invalid") for value in contamination_series]
    if not values:
        return {"contamination_auc": None, "frames": 0}
    if len(values) == 1:
        return {"contamination_auc": values[0], "frames": 1}
    area = sum((left + right) / 2.0 for left, right in zip(values, values[1:])) / (len(values) - 1)
    return {"contamination_auc": area, "frames": len(values)}


def size_and_cost(
    memory_after: Mapping[str, Any], *, runtime_per_frame_s: float, peak_memory_bytes: int,
) -> dict[str, Any]:
    """Active entity count, version count, runtime and peak memory for one frame."""

    checked = validate_memory(memory_after, copy=False)  # read only
    runtime = _finite(runtime_per_frame_s, "runtime_per_frame_invalid")
    _require(runtime >= 0.0, "runtime_per_frame_invalid")
    return {
        "active_entity_count": sum(1 for entity in checked["entities"] if entity["state"] == "active"),
        # Lifecycle versions only (birth, retract, reactivate, dormant, dedup):
        # a BIND opens a version per observation, which would make this number
        # track observation count instead of lifecycle churn (D-224-X X6).
        "lifecycle_version_count": sum(
            1
            for entity in checked["entities"]
            for version in entity["versions"]
            if version["opened_by"] not in LIFECYCLE_VERSION_EXCLUDES
        ),
        "runtime_per_frame_s": runtime,
        "peak_memory_bytes": _int(peak_memory_bytes, "peak_memory_invalid", minimum=0),
    }


def assert_report_keys(report: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Reject any report that names a metric or field outside the frozen list."""

    _require(type(report) is dict, "report_not_object")
    for metric in report:
        _require(metric in METRICS, f"report_metric_outside_frozen_list:{metric}")
        _require(type(report[metric]) is dict, f"report_metric_not_object:{metric}")
        for field in report[metric]:
            _require(field in METRIC_FIELDS[metric], f"report_field_outside_frozen_list:{metric}.{field}")
    return clone_json(dict(report))


def micro_average(
    records: Sequence[Mapping[str, Any]], *, numerator: str, denominator: str,
) -> float | None:
    """House-level ratio: sum of numerators over sum of denominators, None when empty."""

    top = 0
    bottom = 0
    for record in records:
        top += _int(record[numerator], "micro_numerator_invalid", minimum=0)
        bottom += _int(record[denominator], "micro_denominator_invalid", minimum=0)
    return (top / bottom) if bottom else None


# --------------------------------------------------------------------------
# 5. house-level paired bootstrap, the strongest control and the main gate
# --------------------------------------------------------------------------

def undefined_houses(
    per_house: Mapping[str, Mapping[str, Any]], *, arms: Sequence[str],
    not_applicable: Sequence[str] = (),
) -> list[str]:
    """Houses whose metric is undefined (``None``) for any applicable reported arm.

    白话：输入每个 house 上各臂的某项指标值和本表要报告的全部臂，输出该指标在任一
    臂上"没法算"（值为 None，例如这个 house 里没有一件被搬走后重访过的物体）的
    house 清单。这份清单按指标算一次、对所有臂一并生效（D-224-X 裁决 X2），配对
    bootstrap 与最强对照选取都必须传入同一份，主表报告有效 house 数。缺臂仍然是错
    误而不是"未定义"。它不填补、不猜值。
    按构造就没法算的臂（例如从不撤回的臂之于假撤回率）以 ``not_applicable`` 传入，
    它们不参与清单计算、也不进入这项指标的任何配对，表里报"不适用"；否则三个从不
    撤回的臂会让每个 house 都被排除，整列对谁都报不出来（复审修订，LOG-225）。
    """

    skipped = {str(item) for item in not_applicable}
    names = [str(item) for item in arms if str(item) not in skipped]
    _require(bool(names), "undefined_houses_needs_arms")
    out: list[str] = []
    for house in sorted(per_house):
        values = per_house[house]
        for name in names:
            _require(name in values, f"bootstrap_house_missing_arm:{house}")
        if any(values[name] is None for name in names):
            out.append(house)
    return out


def paired_house_bootstrap(
    per_house: Mapping[str, Mapping[str, float]], *, arm: str, control: str,
    seed: int, direction: str, iterations: int = BOOTSTRAP_ITERATIONS,
    confidence: float = CONFIDENCE_ONE_SIDED, excluded_houses: Sequence[str] = (),
    not_applicable: Sequence[str] = (),
) -> dict[str, Any]:
    """One-sided lower bound on the paired house-level advantage of ``arm``.

    白话：输入每个 house 上两臂的指标值，输出配对差的均值和单侧下界；house 是配对
    与重采样的单位。direction 为 higher 时差取臂减对照，lower 时取对照减臂，因此下
    界大于零永远表示臂更好。某个 house 缺了任一臂就拒绝而不是跳过，否则配对被悄悄
    打破。例如 100 个 house 上 VSMT 的残留率平均低 0.08、下界 0.03，则本项过门。
    它不做多重比较校正，那在 S3-01 冻结。

    Undefined values (D-224-X ruling X2).  A house can legitimately have no
    judged object for a metric, and then its value is ``None``.  Such a
    house must be named in ``excluded_houses`` (computed once per metric by
    :func:`undefined_houses` over every reported arm) and is skipped for
    every pair; a ``None`` outside that list is an error, never imputed.
    The result reports the effective house count and the exclusions.
    """

    _require(direction in {"higher", "lower"}, "bootstrap_direction_invalid")
    _int(iterations, "bootstrap_iterations_invalid", minimum=1)
    _int(seed, "bootstrap_seed_invalid", minimum=0)
    level = _finite(confidence, "bootstrap_confidence_invalid")
    _require(0.5 < level < 1.0, "bootstrap_confidence_invalid")
    for name in (arm, control):
        _require(str(name) not in {str(item) for item in not_applicable}, f"bootstrap_arm_not_applicable:{name}")
    excluded = {str(item) for item in excluded_houses}
    diffs: list[float] = []
    skipped: list[str] = []
    for house in sorted(per_house):
        values = per_house[house]
        _require(arm in values and control in values, f"bootstrap_house_missing_arm:{house}")
        if house in excluded:
            skipped.append(house)
            continue
        _require(
            values[arm] is not None and values[control] is not None,
            f"bootstrap_house_metric_undefined:{house}",
        )
        a = _finite(values[arm], "bootstrap_value_invalid")
        c = _finite(values[control], "bootstrap_value_invalid")
        diffs.append(a - c if direction == "higher" else c - a)
    _require(len(diffs) >= 2, "bootstrap_needs_two_houses")
    rng = random.Random(seed)
    means: list[float] = []
    count = len(diffs)
    for _ in range(iterations):
        sample = [diffs[rng.randrange(count)] for _ in range(count)]
        means.append(sum(sample) / count)
    means.sort()
    lower_index = int(math.floor((1.0 - level) * iterations))
    return {
        "arm": arm,
        "control": control,
        "houses": count,
        "mean_advantage": sum(diffs) / count,
        "lower_bound_one_sided": means[min(lower_index, iterations - 1)],
        "confidence": level,
        "iterations": iterations,
        "seed": seed,
        "excluded_undefined": len(skipped),
        "excluded_houses": skipped,
    }


def strongest_control(
    per_house: Mapping[str, Mapping[str, float]], *, controls: Sequence[str], direction: str,
    excluded_houses: Sequence[str] = (), not_applicable: Sequence[str] = (),
) -> str:
    """The control arm with the best house mean on one metric; ties go to the smallest name.

    The mean is taken over the same houses the paired bootstrap uses, so the
    same ``excluded_houses`` list (ruling X2) must be passed here.  Controls
    for which the metric is not applicable by construction are skipped.
    """

    _require(direction in {"higher", "lower"}, "control_direction_invalid")
    skipped = {str(item) for item in not_applicable}
    controls = [str(item) for item in controls if str(item) not in skipped]
    _require(len(controls) >= 1 and len(per_house) >= 1, "control_selection_needs_input")
    excluded = {str(item) for item in excluded_houses}
    houses = [house for house in sorted(per_house) if house not in excluded]
    _require(bool(houses), "control_selection_needs_input")
    means: dict[str, float] = {}
    for control in controls:
        total = 0.0
        for house in houses:
            _require(control in per_house[house], f"bootstrap_house_missing_arm:{house}")
            _require(per_house[house][control] is not None, f"bootstrap_house_metric_undefined:{house}")
            total += _finite(per_house[house][control], "bootstrap_value_invalid")
        means[str(control)] = total / len(houses)
    sign = -1.0 if direction == "higher" else 1.0
    return sorted(means.items(), key=lambda item: (sign * item[1], item[0]))[0][0]


def main_gate(bounds: Mapping[str, float]) -> dict[str, Any]:
    """Both main-gate metrics must show a positive one-sided lower bound."""

    verdict = {}
    for metric, _direction in MAIN_GATE:
        _require(metric in bounds, f"main_gate_metric_missing:{metric}")
        verdict[metric] = _finite(bounds[metric], "main_gate_bound_invalid") > 0.0
    return {"per_metric": verdict, "passed": all(verdict.values())}


# --------------------------------------------------------------------------
# 5b. the S3 main gate (ruling 102-2 / 102-3): runs, one exclusion list, two-level resampling, 82-1, fixed sequence
# --------------------------------------------------------------------------

def run_key(arm: str, seed: int | None = None) -> str:
    """The key of one run in a per-house table: ``VSMT-lean:7`` for a learned arm at a seed, the bare name for a seedless arm."""

    return str(arm) if seed is None else f"{arm}:{int(seed)}"


def main_table_runs(*, learned: Sequence[str] = PRIMARY_COMPARISON, seeds: Sequence[int] = GATE_SEEDS,
                    rule_arms: Sequence[str] = CONTROL_ARMS) -> list[str]:
    """Every run of the main table: each learned arm at each seed and each rule arm once (the runs the exclusion list covers)."""

    return [run_key(arm, seed) for arm in learned for seed in seeds] + [run_key(arm) for arm in rule_arms]


def exclusion_over_runs(per_house: Mapping[str, Mapping[str, Any]], *, runs: Sequence[str],
                        not_applicable: Sequence[str] = ()) -> list[str]:
    """Ruling 102-3: the one exclusion list of a metric over every run (X2 extended to seeds); a missing run is an error.

    白话：输入每个 house 上每次运行（学习臂的每个种子、每个规则臂）的某项指标值，输出该指标的排除清单：只要有一次运行
    在这个 house 上不可算，这个 house 就对所有臂、所有检验一并排除。缺一次运行不是“不可算”，而是错误。
    """

    return undefined_houses(per_house, arms=list(runs), not_applicable=not_applicable)


def seed_paired_matrix(per_house: Mapping[str, Mapping[str, Any]], *, arm: str, control: str, direction: str,
                       houses: Sequence[str], seeds: Sequence[int] = GATE_SEEDS, control_seeded: bool = True) -> list[list[float]]:
    """d[h][s]: the advantage of ``arm`` at seed s over ``control`` at seed s (or its one value), positive when ``arm`` is better."""

    _require(direction in {"higher", "lower"}, "gate_direction_invalid")
    sign = 1.0 if direction == "higher" else -1.0
    matrix: list[list[float]] = []
    for house in houses:
        values = per_house[house]
        row = []
        for seed in seeds:
            a_key, c_key = run_key(arm, seed), run_key(control, seed if control_seeded else None)
            _require(a_key in values and c_key in values, f"gate_run_missing:{house}")
            _require(values[a_key] is not None and values[c_key] is not None, f"gate_value_undefined:{house}")
            row.append(sign * (_finite(values[a_key], "gate_value_invalid") - _finite(values[c_key], "gate_value_invalid")))
        matrix.append(row)
    return matrix


def two_level_mean(matrix: Sequence[Sequence[float]], house_idx: Sequence[int], seed_idx: Sequence[int]) -> float:
    """The two-level statistic for given draws: the mean of matrix[h][s] over drawn houses x drawn seeds (crossed draws)."""

    _require(bool(house_idx) and bool(seed_idx), "two_level_draw_empty")
    return sum(matrix[h][s] for h in house_idx for s in seed_idx) / (len(house_idx) * len(seed_idx))


def two_level_lower_bound(matrix: Sequence[Sequence[float]], *, seed: int, iterations: int = BOOTSTRAP_ITERATIONS,
                          confidence: float = CONFIDENCE_ONE_SIDED) -> float:
    """One-sided lower bound of the mean advantage by two-level resampling (ruling 102-3).

    白话：每一次抽样先有放回地抽种子编号，再有放回地抽 house，所有抽中的种子都用这同一批 house，算抽中 house × 抽中种子上
    配对差的均值；抽 10,000 次，取第 floor(0.05 × 次数) 小的那个作单侧 95% 下界。它同时把“换一批 house”和“换一次训练”
    两种随机性放进区间；五个种子时覆盖率没有理论保证，S3-01 用零效应校准核验过（results/vsmt_lean_s3_01_planning_6c57903.json）。
    """

    _int(iterations, "bootstrap_iterations_invalid", minimum=1)
    _int(seed, "bootstrap_seed_invalid", minimum=0)
    level = _finite(confidence, "bootstrap_confidence_invalid")
    _require(0.5 < level < 1.0, "bootstrap_confidence_invalid")
    n = len(matrix)
    _require(n >= 2, "bootstrap_needs_two_houses")
    width = len(matrix[0])
    _require(width >= 1 and all(len(row) == width for row in matrix), "two_level_matrix_ragged")
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(iterations):
        weights = [0] * width
        for _s in range(width):
            weights[rng.randrange(width)] += 1
        row_values = [sum(w * v for w, v in zip(weights, row)) for row in matrix]
        total = sum(row_values[rng.randrange(n)] for _h in range(n))
        means.append(total / (n * width))
    means.sort()
    return means[min(int(math.floor((1.0 - level) * iterations)), iterations - 1)]


def seed_stability(gaps: Sequence[float], *, seeds: Sequence[int] = GATE_SEEDS) -> bool:
    """82-1 in the favourable direction (gaps are signed so that positive favours the method)."""

    if len(gaps) != len(seeds) or len(gaps) < 2:
        return False
    mean = sum(gaps) / len(gaps)
    sd = math.sqrt(sum((g - mean) ** 2 for g in gaps) / (len(gaps) - 1))
    favourable = sum(1 for g in gaps if g > 0)
    return favourable >= len(gaps) - 1 and mean > 0 and abs(mean) > sd


def gate_metric(
    per_house: Mapping[str, Mapping[str, Any]], *, direction: str, arm: str, control: str, excluded_houses: Sequence[str],
    seed: int, seeds: Sequence[int] = GATE_SEEDS, control_seeded: bool = True, iterations: int = BOOTSTRAP_ITERATIONS,
    confidence: float = CONFIDENCE_ONE_SIDED,
) -> dict[str, Any]:
    """One metric of one comparison: two-level lower bound plus 82-1; passed only when both hold and all five seeds exist.

    白话：输入每个 house 每次运行的指标值、排除清单、比较的两臂与方向，输出这一项的读数：有效 house 数、种子平均后的
    平均优势、5 个按种子配对的 house 均值差、82-1 是否成立、两级重采样下界（主检验）与只按 house 重采样的下界（敏感性），
    以及是否成立（下界大于 0 且 82-1 成立）。任何一臂少一个种子的运行，这一项记“不可判”，不删掉坏种子后照算。
    """

    excluded = {str(h) for h in excluded_houses}
    houses = [str(h) for h in sorted(per_house) if str(h) not in excluded]
    keys = [run_key(arm, s) for s in seeds] + ([run_key(control, s) for s in seeds] if control_seeded else [run_key(control)])
    missing = sorted({key for h in houses for key in keys if key not in per_house[h]})
    base = {"arm": arm, "control": control, "direction": direction, "houses": len(houses), "excluded_houses": sorted(excluded)}
    if missing:
        return {**base, "evaluable": False, "reason": f"runs_missing:{','.join(missing)}", "passed": False}
    if len(houses) < 2:
        return {**base, "evaluable": False, "reason": "fewer_than_two_houses", "passed": False}
    matrix = seed_paired_matrix(per_house, arm=arm, control=control, direction=direction, houses=houses, seeds=seeds,
                                control_seeded=control_seeded)
    gaps = [sum(row[s] for row in matrix) / len(matrix) for s in range(len(seeds))]
    mean = sum(sum(row) for row in matrix) / (len(matrix) * len(seeds))
    lower_two_level = two_level_lower_bound(matrix, seed=seed, iterations=iterations, confidence=confidence)
    row_means = {str(i): {"m": sum(row) / len(row), "z": 0.0} for i, row in enumerate(matrix)}
    lower_house = paired_house_bootstrap(row_means, arm="m", control="z", seed=seed, direction="higher",
                                         iterations=iterations, confidence=confidence)["lower_bound_one_sided"]
    stable = seed_stability(gaps, seeds=seeds)
    return {**base, "evaluable": True, "mean_advantage": mean, "seed_paired_gaps": gaps, "stable_82_1": stable,
            "lower_bound_two_level": lower_two_level, "lower_bound_house_only_sensitivity": lower_house,
            "passed": bool(lower_two_level > 0.0 and stable)}


def _present_runs(table: Mapping[str, Mapping[str, Any]], runs: Sequence[str], rule_arms: Sequence[str]) -> list[str]:
    """The main-table runs present in every house; a missing rule arm is an error, a missing learned seed is left to gate_metric
    (which then reports the comparison as not evaluable rather than dropping the seed)."""

    present = [r for r in runs if all(r in table[h] for h in table)]
    for arm in rule_arms:
        _require(run_key(arm) in present, f"main_table_run_missing:{arm}")
    return present


def primary_gate(
    per_house_by_metric: Mapping[str, Mapping[str, Mapping[str, Any]]], *, seed: int, seeds: Sequence[int] = GATE_SEEDS,
    rule_arms: Sequence[str] = CONTROL_ARMS, iterations: int = BOOTSTRAP_ITERATIONS,
) -> dict[str, Any]:
    """Ruling 99-2 / 102-3: VSMT-lean against AssocOnly on both main-gate metrics of one front end, each on its own one list."""

    runs = main_table_runs(seeds=seeds, rule_arms=rule_arms)
    out: dict[str, Any] = {"rule": MAIN_GATE_RULE, "metrics": {}}
    for metric, direction in MAIN_GATE:
        _require(metric in per_house_by_metric, f"main_gate_metric_missing:{metric}")
        table = per_house_by_metric[metric]
        present = _present_runs(table, runs, rule_arms)
        excluded = exclusion_over_runs(table, runs=present)
        out["metrics"][metric] = {
            **gate_metric(table, direction=direction, arm=PRIMARY_COMPARISON[0], control=PRIMARY_COMPARISON[1],
                          excluded_houses=excluded, seed=seed, seeds=seeds, iterations=iterations),
            "exclusion_runs": present,
        }
    out["passed"] = all(block["passed"] for block in out["metrics"].values())
    return out


def original_gate(
    per_house_by_metric: Mapping[str, Mapping[str, Mapping[str, Any]]], *, seed: int, seeds: Sequence[int] = GATE_SEEDS,
    rule_arms: Sequence[str] = CONTROL_ARMS, iterations: int = BOOTSTRAP_ITERATIONS,
) -> dict[str, Any]:
    """The gate written before ruling 99 (against the strongest control), the same lists and rules; reported, never gating."""

    runs = main_table_runs(seeds=seeds, rule_arms=rule_arms)
    out: dict[str, Any] = {"rule": ORIGINAL_GATE_RULE, "metrics": {}}
    for metric, direction in MAIN_GATE:
        table = per_house_by_metric[metric]
        present = _present_runs(table, runs, rule_arms)
        excluded = exclusion_over_runs(table, runs=present)
        houses = [h for h in sorted(table) if h not in set(excluded)]
        averaged = {h: {arm: table[h][arm] for arm in rule_arms} for h in houses}
        strongest = strongest_control(averaged, controls=rule_arms, direction=direction)
        out["metrics"][metric] = {
            **gate_metric(table, direction=direction, arm=METHOD_ARM, control=strongest, excluded_houses=excluded, seed=seed,
                          seeds=seeds, control_seeded=False, iterations=iterations),
            "strongest_control": strongest,
        }
    out["met"] = all(block["passed"] for block in out["metrics"].values())
    return out


def fixed_sequence(primary_by_front_end: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Ruling 102-2: the three steps over the two front ends; a step is tested only when every earlier step passed.

    白话：输入两套前端各自的首要检验结果，输出三步的判定：第一步实例分割两项都成立才看第二步（SAM2 的 Missing 残留率），
    第二步成立才看第三步（SAM2 的身份连续率）；没走到的步骤记“未检验”，只报差值与区间。三步都成立才可以说“跨两种分割
    都成立”。
    """

    steps: list[dict[str, Any]] = []
    reached = True
    for front_end, metrics in FIXED_SEQUENCE:
        _require(front_end in primary_by_front_end, f"fixed_sequence_front_end_missing:{front_end}")
        blocks = primary_by_front_end[front_end]["metrics"]
        passed = all(blocks[m]["passed"] for m in metrics)
        steps.append({"front_end": front_end, "metrics": list(metrics), "tested": reached, "passed": bool(reached and passed)})
        reached = reached and passed
    return {"rule": FIXED_SEQUENCE_RULE, "steps": steps,
            "instance_segmentation_established": steps[0]["passed"],
            "sam2_missing_residual_established": steps[1]["passed"],
            "sam2_identity_continuity_established": steps[2]["passed"],
            "across_both_front_ends": all(step["passed"] for step in steps)}


def ablation_report(
    per_house: Mapping[str, Mapping[str, float]], *, direction: str, seed: int,
    iterations: int = BOOTSTRAP_ITERATIONS, ablations: Sequence[str] = ABLATION_ARMS,
    excluded_houses: Sequence[str] = (), not_applicable: Sequence[str] = (),
) -> dict[str, Any]:
    """VSMT-lean against each ablation with the same paired bootstrap; reported, never gated.

    An ablation for which the metric is not applicable by construction gets a
    ``not_applicable`` row instead of a bootstrap.
    """

    skipped = {str(item) for item in not_applicable}
    rows: dict[str, Any] = {}
    for ablation in ablations:
        if str(ablation) in skipped:
            rows[str(ablation)] = {"not_applicable": True}
            continue
        rows[str(ablation)] = paired_house_bootstrap(
            per_house, arm=METHOD_ARM, control=str(ablation), seed=seed,
            direction=direction, iterations=iterations, excluded_houses=excluded_houses,
            not_applicable=not_applicable,
        )
    return {"per_ablation": rows, "gated": False, "in_main_table": ["AssocOnly"]}


# --------------------------------------------------------------------------
# 6. nuisance probe
# --------------------------------------------------------------------------

def nuisance_probe(records: Sequence[Mapping[str, Any]], *, field: str, label: str) -> dict[str, Any]:
    """Leave-one-out majority-per-value accuracy of a nuisance field vs. majority.

    白话：输入一批只含元数据与标签的记录，输出用某个元数据字段（路径、seed、帧号、
    house 序号）去猜标签能达到的留一法准确率，以及只猜多数类的准确率。前者若明
    显高于后者，说明答案从元数据漏出来了。例如帧号能猜出撤回标签，就说明干预总在
    固定帧发生。它不设阈值，阈值在合同里待冻结。
    """

    _require(field in NUISANCE_FIELDS, "nuisance_field_unknown")
    _require(len(records) >= 2, "nuisance_probe_needs_records")
    labels = [str(record[label]) for record in records]
    values = [str(record[field]) for record in records]
    label_counts: dict[str, int] = {}
    for item in labels:
        label_counts[item] = label_counts.get(item, 0) + 1
    majority = max(label_counts, key=lambda item: (label_counts[item], item))
    majority_accuracy = label_counts[majority] / len(labels)
    # Leave-one-out by counting, not by rescanning (2026-09-27): the label counts of each value group, minus the row
    # itself, give exactly the table the pairwise loop built; the pairwise loop was quadratic in the rows and ran for
    # hours on a large TAF episode (tens of thousands of association rows).  Same guesses, same ties, same numbers.
    groups: dict[str, dict[str, int]] = {}
    for value, item in zip(values, labels, strict=True):
        group = groups.setdefault(value, {})
        group[item] = group.get(item, 0) + 1
    hits = 0
    for value, item in zip(values, labels, strict=True):
        table = {name: count - (1 if name == item else 0) for name, count in groups[value].items()}
        table = {name: count for name, count in table.items() if count > 0}
        guess = max(table, key=lambda name: (table[name], name)) if table else majority
        hits += 1 if guess == item else 0
    return {
        "field": field,
        "label": label,
        "probe_accuracy": hits / len(records),
        "majority_accuracy": majority_accuracy,
        "advantage": hits / len(records) - majority_accuracy,
    }


def run_nuisance_probes(
    records: Sequence[Mapping[str, Any]], *, labels: Sequence[str] = NUISANCE_LABELS,
) -> dict[str, Any]:
    """Every nuisance field against every label kind; the largest advantage is reported."""

    table = {
        str(label): {field: nuisance_probe(records, field=field, label=str(label)) for field in NUISANCE_FIELDS}
        for label in labels
    }
    largest = max(
        (probe["advantage"] for probes in table.values() for probe in probes.values()),
        default=None,
    )
    return {"per_label": table, "largest_advantage": largest}


# --------------------------------------------------------------------------
# machine contract
# --------------------------------------------------------------------------

#: Every boolean claim the contract may make, with the value this
#: implementation actually enforces.  The validator requires the contract's
#: boolean leaves to be exactly this set: a flipped value, a missing claim or
#: an unknown claim is rejected.
EXPECTED_BOOLEAN_CLAIMS: dict[str, bool] = {
    "authorization.private_truth_read": False,
    "authorization.label_generation": False,
    "authorization.evaluation_run": False,
    "authorization.bootstrap_run": False,
    "authorization.test_split_read": False,
    "authorization.server_run": False,
    "private_gate.requires_both_stage_seals": True,
    "private_gate.teacher_never_opens_files_itself": True,
    "private_gate.teacher_uses_current_policy_assignment_not_its_own": True,
    "private_gate.teacher_never_edits_recall": True,
    "labels.entity_identity_has_no_threshold": True,
    "labels.canonical_target_is_earliest_first_version_then_smallest_id": True,
    "labels.recalled_duplicate_may_be_target": True,
    "labels.ambiguous_identity_is_teacher_error_not_a_guess": True,
    "labels.unlabelled_fragments_excluded_from_loss_and_counted": True,
    "labels.fragment_dominance.tie_at_the_top_is_ambiguous": True,
    "labels.existence.ineligible_candidate_state_is_rejected_not_skipped": True,
    "decomposition.per_frame": True,
    "decomposition.mutually_exclusive_and_additive": True,
    "decomposition.unlabelled_fragments_charged_to_no_class": True,
    "metrics.no_metric_outside_this_list_may_be_reported": True,
    "metrics.no_composite_score": True,
    "metrics.evaluator_matching_is_independent_of_method_solver": True,
    "metrics.evaluator_reads_no_surface_ids": True,
    "metrics.node_prf1.dormant_counts_as_in_memory": True,
    "metrics.missing_residual_rate.dormant_counts_as_in_memory": True,
    "metrics.missing_residual_rate.not_yet_observable_objects_excluded_and_counted": True,
    "metrics.identity_continuity.canonical_of_folding_recognised": False,
    "metrics.identity_continuity.any_prior_carrier_counts": True,
    # ruling 102-0 (2026-10-02): the same events for every arm; no pre-move carrier counts as not kept
    "metrics.identity_continuity.same_events_for_every_arm": True,
    "metrics.identity_continuity.no_prior_carrier_counts_as_not_kept": True,
    "metrics.identity_continuity_conditional.never_in_the_main_gate_never_selects": True,
    # ruling 102-5 (2026-10-02)
    "metrics.retrieval_success.same_events_for_every_arm": True,
    "metrics.retrieval_success.query_built_by_the_evaluator_never_seen_by_the_method": True,
    "metrics.retrieval_success.never_in_the_main_gate_never_selects": True,
    "metrics.recovery_latency_frames.starts_at_first_observable_frame_not_intervention_frame": True,
    "metrics.recovery_latency_frames.unrecovered_reported_separately_never_averaged": True,
    "statistics.paired": True,
    "statistics.test_read_once": True,
    "statistics.assoc_only_reported_in_main_table": True,
    "statistics.ablations_reported_not_gated": True,
    "statistics.appendix_arm_validation_only_never_main_table_or_test": True,
    "continue_gate.metric_list_frozen_before_any_data_generation": True,
    "continue_gate.private_opens_only_against_a_two_seal_receipt": True,
    "continue_gate.every_label_is_resolvable_or_counted": True,
    "continue_gate.evaluator_matching_independent_and_brute_force_checked": True,
    "continue_gate.every_boolean_claim_is_bound_by_the_validator": True,
    # D-224-X (v2)
    "supersedes_contract.v1_bytes_frozen": True,
    "labels.same_frame_duplicates.excluded_from_loss_and_counted": True,
    "labels.same_frame_duplicates.only_labelled_fragments_with_the_same_target_are_folded": True,
    "decomposition.duplicate_fragments_charged_to_no_class": True,
    "metrics.node_prf1.truth_table_carries_in_scope_flag": True,
    "private_truth_inputs.truth_box_source.boxes_are_in_the_episode_frame": True,
    "private_truth_inputs.truth_box_source.observed_set_box_is_a_proxy_reported_only_as_a_comparison_column": True,
    "metrics.node_prf1.present_out_of_scope_entities_excluded_from_precision_denominator": True,
    "labels.same_frame_duplicates.keeper_correct_iff_any_member_reaches_the_target_and_none_is_misbound": True,
    "statistics.undefined_house_rule_over_applicable_arms_only": True,
    "metrics.size_and_cost.bind_versions_excluded_from_lifecycle_version_count": True,
    "metrics.evaluator_matching_per_component_equals_dense_solve": True,
    "statistics.undefined_house_excluded_for_all_arms_and_counted": True,
    "statistics.undefined_house_never_imputed": True,
    # ruling 102-3 (2026-10-02)
    "statistics.all_five_seeds_required": True,
    "statistics.target_is_the_training_procedure_under_fixed_data_recipe_and_selection": True,
    "statistics.every_drawn_seed_uses_the_same_drawn_houses": True,
    "statistics.original_gate_reported_never_gating": True,
}

#: D-224-X rulings this v2 implements; the contract must name them.
V2_RULINGS_DECISION_ID = "D-224-X"
V2_RULING_KEYS = ("X1", "X2", "X5", "X6")

#: Policy values that must still be null: none since ruling 102-3 (2026-10-02) froze the bootstrap seed and the effect-size slot.
NULL_POLICY_PATHS: tuple[str, ...] = ()

#: Ruling 102-3: the S3 bootstrap seed (any fixed integer, registered before any S3 data existed) and the effect-size slot, which
#: holds planning numbers only (the gate stays "lower bound above 0", ruling 99-2); the numbers are the seed-averaged development
#: and confirmation advantages of results/vsmt_lean_s3_01_planning_6c57903.json under the ruling 102-0 definition.
BOOTSTRAP_SEED = 20261002
MAIN_GATE_EFFECT_SIZE = {
    "role": "planning_only_not_a_threshold",
    "source": "results/vsmt_lean_s3_01_planning_6c57903.json",
    "instance_segmentation_confirmation": {"missing_residual_rate": 0.6054, "identity_continuity": 0.091},
    "sam2_development": {"missing_residual_rate": 0.1745, "identity_continuity": 0.0147},
}

#: D-224-S1 ruling 67 (2026-09-24): the two label values, frozen once.  Callers still pass them
#: explicitly; the validator requires the contract to carry exactly these numbers.
DOMINANCE_MIN_SHARE = 0.5
DELTA_MOVED_M = 0.5
#: D-224-S1 ruling 68 (2026-09-25, LOG-256 sequel): the nuisance probe's largest admissible advantage,
#: judged over the pooled rows of one split.  Path, seed and house index are constant within an
#: episode (advantage 0) and only discriminate once houses are pooled, which is the leakage the probe
#: exists to catch; frame_index within one episode reaches 0.128 through temporal clustering of the
#: statuses (a frame where a new object enters is mostly births), which is not leakage, so the
#: per-episode largest_advantage is reported and never judged.
NUISANCE_MAXIMUM_ADVANTAGE = 0.05
NUISANCE_SCOPE_RULE = "judged_over_the_pooled_rows_of_one_split; the per_episode largest_advantage is reported and never judged"
FROZEN_VALUES_BY_RULING = (
    ("labels.fragment_dominance.dominance_min_share", DOMINANCE_MIN_SHARE, "D-224-S1 ruling 67"),
    ("labels.existence.delta_moved_m", DELTA_MOVED_M, "D-224-S1 ruling 67"),
    ("nuisance_probe.maximum_advantage", NUISANCE_MAXIMUM_ADVANTAGE, "D-224-S1 ruling 68"),
    ("statistics.bootstrap_seed", BOOTSTRAP_SEED, "D-224-S1 ruling 102-3"),
    ("statistics.main_gate_effect_size", MAIN_GATE_EFFECT_SIZE, "D-224-S1 ruling 102-3"),
)

#: Constants already frozen by an approved decision; the validator binds their values.
FROZEN_CONSTANTS = (
    ("metrics.node_prf1_iou.iou_min", IOU_MIN, "D-224-C"),
    ("statistics.bootstrap_iterations", BOOTSTRAP_ITERATIONS, "METHOD-11"),
    ("statistics.confidence_one_sided", CONFIDENCE_ONE_SIDED, "METHOD-11"),
)


def _walk(value: Any, prefix: str, out: dict[str, Any]) -> None:
    if type(value) is dict:
        for key, item in value.items():
            _walk(item, f"{prefix}.{key}" if prefix else str(key), out)
    elif type(value) is bool:
        out[prefix] = value


def _lookup(contract: Mapping[str, Any], path: str) -> Any:
    node: Any = contract
    for part in path.split("."):
        _require(type(node) is dict and part in node, f"contract_path_missing:{path}")
        node = node[part]
    return node


def validate_teacher_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Check that the S0-04 machine contract agrees with this implementation.

    白话：输入合同 JSON，输出同样内容的副本，并在任何一条声称与实现不符时拒绝。
    合同里的每一个布尔值都必须在实现登记的清单里且取值一致：翻转任何一条、少一
    条、或加一条实现不认识的，都拒绝。指标清单、状态集合、规则字符串和已冻结常
    量按字节比对；待冻结数值必须为 null；授权位必须全 false。
    """

    _require(type(contract) is dict, "contract_not_object")
    _require(contract.get("schema_version") == CONTRACT_SCHEMA_VERSION, "contract_schema_version_invalid")
    _require(contract.get("decision_id") == "D-224", "contract_decision_id_invalid")
    _require(contract.get("stage_id") == "S0-04", "contract_stage_id_invalid")
    required = {
        "authorization", "private_gate", "labels", "decomposition", "metrics",
        "statistics", "nuisance_probe", "continue_gate", "user_rulings",
    }
    missing = sorted(required - set(contract.keys()))
    _require(not missing, f"contract_missing_sections:{','.join(missing)}")

    # Every boolean leaf is a claim; the set of claims must match exactly.
    found: dict[str, bool] = {}
    _walk(contract, "", found)
    for path in sorted(set(found) - set(EXPECTED_BOOLEAN_CLAIMS)):
        raise LeanTeacherError(f"contract_unbound_boolean_claim:{path}")
    for path in sorted(set(EXPECTED_BOOLEAN_CLAIMS) - set(found)):
        raise LeanTeacherError(f"contract_missing_boolean_claim:{path}")
    for path, expected in EXPECTED_BOOLEAN_CLAIMS.items():
        _require(found[path] is expected, f"contract_claim_flipped:{path}")
    _require(
        set(contract["authorization"].keys()) == {path.split(".")[1] for path in EXPECTED_BOOLEAN_CLAIMS if path.startswith("authorization.")},
        "contract_authorization_fields_invalid",
    )

    labels = contract["labels"]
    _require(tuple(labels["association_statuses"]) == ASSOCIATION_STATUSES, "contract_association_statuses_mismatch")
    _require(tuple(labels["existence_statuses"]) == EXISTENCE_STATUSES, "contract_existence_statuses_mismatch")
    _require(labels["entity_identity_rule"] == ENTITY_IDENTITY_RULE, "contract_entity_identity_rule_mismatch")
    _require(labels["fragment_dominance"]["denominator"] == FRAGMENT_DOMINANCE_DENOMINATOR, "contract_dominance_denominator_mismatch")
    _require(tuple(labels["existence"]["candidate_states"]) == EXISTENCE_CANDIDATE_STATES, "contract_existence_candidate_states_mismatch")
    _require(labels["existence"]["displacement_reference"] == EXISTENCE_DISPLACEMENT_REFERENCE, "contract_displacement_reference_mismatch")
    _require(labels["existence"].get("place_rule") == EXISTENCE_PLACE_RULE, "contract_existence_place_rule_mismatch")  # ruling 88-4
    _require(labels["existence"].get("gone_rule") == EXISTENCE_GONE_RULE, "contract_existence_gone_rule_mismatch")

    _require(tuple(contract["decomposition"]["classes"]) == DECOMPOSITION, "contract_decomposition_mismatch")

    metrics = contract["metrics"]
    _require(tuple(metrics["names"]) == METRICS, "contract_metric_names_mismatch")
    _require(
        {name: tuple(fields) for name, fields in metrics["reported_fields"].items()} == METRIC_FIELDS,
        "contract_metric_fields_mismatch",
    )
    _require(tuple(metrics["memory_present_states"]) == MEMORY_PRESENT_STATES, "contract_memory_present_states_mismatch")
    _require(metrics["node_prf1"]["truth_node_scope"] == TRUTH_NODE_SCOPE, "contract_truth_node_scope_mismatch")
    _require(metrics["node_prf1"].get("spawned_after_reload_rule") == SPAWNED_AFTER_RELOAD_RULE, "contract_spawned_rule_mismatch")
    node = metrics["node_prf1"]
    _require(node.get("matching") == CENTROID_MATCHING_RULE, "contract_centroid_matching_mismatch")
    _require(node.get("objective") == NODE_MATCHING_OBJECTIVE, "contract_node_matching_objective_mismatch")
    _require(node.get("identity_requirement") == NODE_IDENTITY_RULE, "contract_node_identity_requirement_mismatch")
    _require(node.get("box_pad_m") == NODE_BOX_PAD_M, "contract_node_box_pad_mismatch")
    _require(node.get("distance_max_source") == CENTROID_MATCHING_DISTANCE_SOURCE, "contract_centroid_distance_source_mismatch")
    _require(node.get("role") == CENTROID_MATCHING_ROLE, "contract_centroid_role_mismatch")
    _require(node.get("dyn_thor_relation") == NODE_DYN_THOR_RELATION, "contract_dyn_thor_relation_mismatch")
    iou_column = metrics.get("node_prf1_iou") or {}
    _require(iou_column.get("matching") == IOU_MATCHING_RULE, "contract_iou_matching_mismatch")
    _require(iou_column.get("objective") == NODE_MATCHING_OBJECTIVE, "contract_node_matching_objective_mismatch")
    _require(iou_column.get("role") == IOU_MATCHING_ROLE, "contract_iou_role_mismatch")
    _require("node_prf1_centroid" not in metrics, "contract_retired_centroid_block_present")
    _require(tuple(metrics["node_prf1"].get("structural_types_excluded_from_scope") or ()) == STRUCTURAL_TYPES_EXCLUDED,
             "contract_structural_scope_mismatch")
    _require(contract["private_truth_inputs"]["truth_box_source"]["rule"] == TRUTH_BOX_SOURCE,
             "contract_truth_box_source_mismatch")
    _require(metrics["identity_continuity"]["judged_at"] == IDENTITY_CONTINUITY_JUDGED_AT, "contract_identity_judged_at_mismatch")
    _require(metrics["identity_continuity"].get("denominator") == IDENTITY_CONTINUITY_DENOMINATOR,
             "contract_identity_denominator_mismatch")  # ruling 102-0
    retrieval = metrics.get("retrieval_success") or {}
    for field, expected in (("events", RETRIEVAL_EVENT_RULE), ("query", RETRIEVAL_QUERY_RULE), ("candidates", RETRIEVAL_CANDIDATE_RULE),
                            ("success", RETRIEVAL_SUCCESS_RULE), ("role", RETRIEVAL_ROLE)):
        _require(retrieval.get(field) == expected, f"contract_retrieval_rule_mismatch:{field}")  # ruling 102-5
    conditional = metrics.get("identity_continuity_conditional") or {}
    _require(conditional.get("role") == IDENTITY_CONTINUITY_CONDITIONAL_ROLE, "contract_identity_conditional_role_mismatch")
    _require(conditional.get("judged_at") == IDENTITY_CONTINUITY_JUDGED_AT, "contract_identity_judged_at_mismatch")
    in_scope = metrics.get("false_retract_rate_in_scope") or {}
    _require(in_scope.get("rule") == FALSE_RETRACT_IN_SCOPE_RULE, "contract_false_retract_in_scope_rule_mismatch")
    _require(tuple(in_scope.get("excluded_reasons") or ()) == PRESENT_BY_RULE_REASONS, "contract_false_retract_in_scope_reasons_mismatch")
    _require(in_scope.get("role") == FALSE_RETRACT_IN_SCOPE_ROLE, "contract_false_retract_in_scope_role_mismatch")
    _require(metrics["recovery_latency_frames"]["start"] == RECOVERY_LATENCY_START, "contract_recovery_start_mismatch")
    _require(metrics["contamination_auc"]["integration"] == CONTAMINATION_INTEGRATION, "contract_contamination_integration_mismatch")

    statistics = contract["statistics"]
    _require(statistics.get("unit") == "house", "contract_statistics_unit_mismatch")
    _require(tuple(tuple(item) for item in statistics["main_gate"]) == MAIN_GATE, "contract_main_gate_mismatch")
    _require(statistics["method_arm"] == METHOD_ARM, "contract_method_arm_mismatch")
    _require(tuple(statistics["controls"]) == CONTROL_ARMS, "contract_controls_mismatch")
    _require(tuple(statistics["ablations"]) == ABLATION_ARMS, "contract_ablations_mismatch")
    _require(statistics["appendix_arm"] == APPENDIX_ARM, "contract_appendix_arm_mismatch")
    _require(statistics["optional_arm"] == OPTIONAL_ARM, "contract_optional_arm_mismatch")
    _require(statistics["strongest_control_rule"] == STRONGEST_CONTROL_RULE, "contract_strongest_control_rule_mismatch")
    # ruling 102-2 / 102-3
    _require(tuple(statistics.get("primary_comparison") or ()) == PRIMARY_COMPARISON, "contract_primary_comparison_mismatch")
    _require(tuple(statistics.get("seeds") or ()) == GATE_SEEDS, "contract_gate_seeds_mismatch")
    for field, expected in (("main_gate_rule", MAIN_GATE_RULE), ("exclusion_rule", EXCLUSION_OVER_RUNS_RULE),
                            ("resampling", TWO_LEVEL_RESAMPLING_RULE), ("seed_stability_rule", SEED_STABILITY_RULE),
                            ("original_gate_rule", ORIGINAL_GATE_RULE), ("multiple_comparison_correction", FIXED_SEQUENCE_RULE)):
        _require(statistics.get(field) == expected, f"contract_statistics_rule_mismatch:{field}")
    _require(tuple((str(front), tuple(metrics)) for front, metrics in statistics.get("fixed_sequence") or ()) == FIXED_SEQUENCE,
             "contract_fixed_sequence_mismatch")

    _require(contract["user_rulings"]["decision_id"] == RULINGS_DECISION_ID, "contract_rulings_decision_mismatch")
    _require(set(contract["user_rulings"]) >= {"L", "M", "N", "O", "P", "Q"}, "contract_rulings_incomplete")
    _require(tuple(contract["nuisance_probe"]["fields"]) == NUISANCE_FIELDS, "contract_nuisance_fields_mismatch")
    _require(tuple(contract["nuisance_probe"]["labels"]) == NUISANCE_LABELS, "contract_nuisance_labels_mismatch")
    _require(contract["nuisance_probe"].get("scope") == NUISANCE_SCOPE_RULE, "contract_nuisance_scope_mismatch")  # ruling 68 (5)
    v2 = contract.get("user_rulings_v2")
    _require(type(v2) is dict and v2.get("decision_id") == V2_RULINGS_DECISION_ID, "contract_v2_rulings_decision_mismatch")
    _require(set(v2) >= set(V2_RULING_KEYS), "contract_v2_rulings_incomplete")
    _require(
        tuple(metrics["size_and_cost"]["lifecycle_version_excludes"]) == LIFECYCLE_VERSION_EXCLUDES,
        "contract_lifecycle_version_excludes_mismatch",
    )
    _require(
        labels["same_frame_duplicates"]["others_status"] == "duplicate_of_labelled",
        "contract_duplicate_status_mismatch",
    )
    _require(
        dict(statistics["metric_not_applicable_rule"]) == METRIC_NOT_APPLICABLE_RULE,
        "contract_metric_not_applicable_rule_mismatch",
    )

    for path, expected_value, _source in FROZEN_CONSTANTS:
        _require(_lookup(contract, path) == expected_value, f"contract_frozen_constant_mismatch:{path}")
    _require(
        tuple(contract.get("frozen_by_decision", ())) == tuple(path for path, _v, _s in FROZEN_CONSTANTS),
        "contract_frozen_constant_list_mismatch",
    )
    for path in NULL_POLICY_PATHS:
        _require(_lookup(contract, path) is None, f"contract_{path.replace('.', '_')}_must_be_null_before_freeze")
    _require(
        tuple(contract.get("policy_values_without_defaults", ())) == NULL_POLICY_PATHS,
        "contract_policy_value_list_mismatch",
    )
    for path, expected_value, _ruling in FROZEN_VALUES_BY_RULING:
        _require(_lookup(contract, path) == expected_value, f"contract_frozen_value_mismatch:{path}")
    return clone_json(dict(contract))


__all__ = [
    "SPAWNED_AFTER_RELOAD_RULE",
    "STRUCTURAL_TYPES_EXCLUDED",
    "in_truth_node_scope",
    "is_spawned_after_reload",
    "structural_type_of",
    "ABLATION_ARMS",
    "APPENDIX_ARM",
    "ASSOCIATION_STATUSES",
    "BIRTH_COLUMN_PREFIX",
    "BOOTSTRAP_ITERATIONS",
    "CENTROID_MATCHING_DISTANCE_SOURCE",
    "CENTROID_MATCHING_ROLE",
    "CENTROID_MATCHING_RULE",
    "NODE_DYN_THOR_RELATION",
    "NODE_BOX_PAD_M",
    "EXISTENCE_GONE_RULE",
    "EXISTENCE_PLACE_RULE",
    "EXISTENCE_PLACE_RULES",
    "NODE_IDENTITY_RULE",
    "CONFIDENCE_ONE_SIDED",
    "CONTRACT_SCHEMA_VERSION",
    "CONTROL_ARMS",
    "DECOMPOSITION",
    "EXISTENCE_CANDIDATE_STATES",
    "EXISTENCE_STATUSES",
    "EXPECTED_BOOLEAN_CLAIMS",
    "FROZEN_CONSTANTS",
    "IOU_MATCHING_ROLE",
    "IOU_MATCHING_RULE",
    "NODE_MATCHING_OBJECTIVE",
    "IOU_MIN",
    "LIFECYCLE_VERSION_EXCLUDES",
    "LeanTeacherError",
    "MAIN_GATE",
    "MEMORY_PRESENT_STATES",
    "METHOD_ARM",
    "METRICS",
    "METRIC_FIELDS",
    "METRIC_NOT_APPLICABLE_RULE",
    "NULL_POLICY_PATHS",
    "NUISANCE_FIELDS",
    "NUISANCE_LABELS",
    "NUISANCE_MAXIMUM_ADVANTAGE",
    "NUISANCE_SCOPE_RULE",
    "OPTIONAL_ARM",
    "RULINGS_DECISION_ID",
    "ablation_report",
    "assert_private_gate",
    "assert_report_keys",
    "association_targets",
    "build_private_gate",
    "contamination_auc",
    "decompose_frame",
    "entity_identities",
    "entity_identity",
    "episode_recovery_latency",
    "evaluate_frame",
    "existence_labels",
    "place_holds",
    "false_retract_rate",
    "false_retract_rate_in_scope",
    "FALSE_RETRACT_IN_SCOPE_ROLE",
    "FALSE_RETRACT_IN_SCOPE_RULE",
    "PRESENT_BY_RULE_REASONS",
    "fragment_dominance",
    "identity_continuity",
    "identity_continuity_blocks",
    "RETRIEVAL_CANDIDATE_RULE",
    "RETRIEVAL_EVENT_RULE",
    "RETRIEVAL_QUERY_RULE",
    "RETRIEVAL_ROLE",
    "RETRIEVAL_SUCCESS_RULE",
    "retrieval_success",
    "retrieval_success_block",
    "IDENTITY_CONTINUITY_CONDITIONAL_ROLE",
    "IDENTITY_CONTINUITY_DENOMINATOR",
    "main_gate",
    "BOOTSTRAP_SEED",
    "EXCLUSION_OVER_RUNS_RULE",
    "FIXED_SEQUENCE",
    "FIXED_SEQUENCE_RULE",
    "GATE_SEEDS",
    "MAIN_GATE_EFFECT_SIZE",
    "MAIN_GATE_RULE",
    "ORIGINAL_GATE_RULE",
    "PRIMARY_COMPARISON",
    "SEED_STABILITY_RULE",
    "TWO_LEVEL_RESAMPLING_RULE",
    "exclusion_over_runs",
    "fixed_sequence",
    "gate_metric",
    "main_table_runs",
    "original_gate",
    "primary_gate",
    "run_key",
    "seed_paired_matrix",
    "seed_stability",
    "two_level_lower_bound",
    "two_level_mean",
    "micro_average",
    "missing_residual_rate",
    "nuisance_probe",
    "object_memory_correct",
    "paired_house_bootstrap",
    "run_nuisance_probes",
    "size_and_cost",
    "strongest_control",
    "undefined_houses",
    "validate_teacher_contract",
]
