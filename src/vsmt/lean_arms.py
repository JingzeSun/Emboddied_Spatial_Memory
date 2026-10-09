"""D-224 / S0-05: control arms, ablations and configuration grids.

Every arm in the first paper shares the frozen frontend, the S0-03 recall,
the S0-03 cost matrix and solver, the S0-01 executor, the shared dedup and
dormancy rules and the S0-04 evaluator.  An arm differs from the others
only in how the association and birth logits of the cost matrix are
produced, how the existence decision (RETRACT or NOOP) is made for an
unassigned, should-be-visible entity, and, for the ablations, which atoms
its vocabulary allows and what a retraction does.  This module holds the
first two for the rule arms (the four controls and HandCost), the
vocabulary restrictions of the four ablations, the split guard for the
appendix arm, the admission rule for the optional arm (VSMT-lean-ctx,
registered but not run: dropped from S3, METHOD section 10), the
configuration-grid budget, ``compile_program``, NoVersion's deletion and the
ruling-102-4 selection rule.  Features are read from the sealed S0-03 rows by
their registered order.

Nothing here trains, reads private data or selects a parameter.  The values
are frozen in code and bound to the S0-05 contract: the grids
(``FROZEN_GRIDS``, ruling 68 (1), tau_r extended by ruling 87-1), the ELU-P
rollout configuration (``ROLLOUT_CONFIG``, ruling 68 (2)), and the shared
should-be-visible minimum, the training values and ELU-P's fitted scalars
(``FROZEN_VALUES_BY_RULING``, rulings 68 and 104-1 1b).

Three constraints from D-224-R shape the rule arms:

1. Inside its gate a rule arm gives a *graded* cost (cosine, or negative
   centroid distance for LOW).  A binary 0/inf cost would leave the
   solver's lexicographic tie-break, which orders columns by opaque entity
   id, to decide which eligible entity a fragment binds to.
2. Every rule arm's grid must contain a wide or absent distance gate.  The
   recall no longer excludes distant candidates, so the gate is the only
   thing that stops a control from re-associating a moved object; a grid
   with only tight gates would hand the identity-continuity half of the
   main gate to VSMT-lean by construction.
3. An ineligible pair is expressed with one registered sentinel logit.  The
   S0-03 cost matrix needs a logit for every recalled pair, and its derived
   forbidden cost stays above the sentinel automatically.
"""

from __future__ import annotations

import itertools
import math
from typing import Any, Mapping, Sequence

from cpmt.hashing import clone_json

from vsmt.lean_memory import memory_digest, validate_memory


CONTRACT_SCHEMA_VERSION = "vsmt-lean-s0-arms-v2"

BIRTH_COLUMN_PREFIX = "birth:"
ATOMS = ("NOOP", "BIND", "BIRTH", "RETRACT", "REACTIVATE")
ENTITY_STATES = ("active", "dormant", "retracted")
SPLITS = ("train", "validation", "test")

METHOD_ARM = "VSMT-lean"
CONTROL_ARMS = ("TAF", "ELU-P", "RAC", "LOW")
ABLATION_ARMS = ("NoVersion", "HandCost", "HeuristicLabel", "AssocOnly")
APPENDIX_ARM = "LLM-op"
#: Registered but not run: VSMT-lean-ctx was dropped from S3 (METHOD section 10).  Its entries in the
#: tables below stay because the S0-05 contract still registers the optional arm.
OPTIONAL_ARM = "VSMT-lean-ctx"
MAIN_TABLE_ARMS = (METHOD_ARM, *CONTROL_ARMS, "AssocOnly")
ALL_ARMS = (METHOD_ARM, *CONTROL_ARMS, *ABLATION_ARMS, APPENDIX_ARM, OPTIONAL_ARM)

#: Arms whose association and birth logits come from a learned head.
LEARNED_ARMS = (METHOD_ARM, "NoVersion", "HeuristicLabel", "AssocOnly", OPTIONAL_ARM)
#: Arms whose logits come from a hand-written rule; none of them has a gradient.
RULE_ARMS = (*CONTROL_ARMS, "HandCost")
#: Rule arms that use the ConceptGraphs-style cosine gate.  HandCost does
#: not: D-224-SW ruling S made it a stateless hand score in VSMT-lean's own
#: three head slots, so it has no distance gate and no temporal state.
GATE_ARMS = ("TAF", "ELU-P", "RAC")

#: D-224-SW rulings T and V.
HEURISTIC_LABEL_SOURCE = "ELU-P"
#: Ruling 104-1 1c (2026-10-03): HeuristicLabel's label function, implemented by ``lean_heuristic_label``; the S0-05
#: HeuristicLabel block carries this string.
HEURISTIC_LABEL_RULE = (
    "ruling 104-1 1c: HeuristicLabel's targets are ELU-P's decisions at the registered rollout_config with the "
    "registered fitted values of the episodes' mask source: each fragment's target is its column in the joint "
    "solve of ELU-P's gate logits over the same recalled columns; each eligible existence row is present when "
    "that solve binds a fragment to the entity, otherwise gone when ELU-P's log-odds -- the arm's own recursion "
    "(decay and weighted free-space coverage per eligible frame, gain per match) along this trajectory's eligible "
    "rows and matches, rolled back with an illegal frame -- fall below the retract threshold; every fragment and "
    "every eligible row carries a label; round 0 labels ELU-P's round-0 trajectory, round 1 HeuristicLabel's own "
    "trajectory under its round-0 heads"
)
SELECTION_METRIC = "node_f1"
RULINGS_DECISION_ID = "D-224-SW"

#: Ruling 102-4 (2026-10-02, 「待裁 102 修订稿二全按推荐」; ruling 83-1 required a pre-registered constraint, 79-7 the reason):
#: every arm whose vocabulary has RETRACT chooses only among the configurations whose validation Missing residual rate is below
#: the same front end's AssocOnly validation value -- one bar for all six arms, no per-arm counterfactual, no rule arm's score
#: and no identity-continuity condition (a real "fewer stale entities, weaker identity" trade-off stays admissible).
SELECTION_CONSTRAINED_ARMS = ("VSMT-lean", "NoVersion", "HeuristicLabel", "HandCost", "ELU-P", "RAC")
SELECTION_REFERENCE_ARM = "AssocOnly"
SELECTION_CONSTRAINT_METRIC = "missing_residual_rate"
SELECTION_RULE = (
    "one configuration per method by node F1 on validation (D-224-SW ruling V); ruling 102-4: an arm whose vocabulary has RETRACT "
    "(VSMT-lean, NoVersion, HeuristicLabel, HandCost, ELU-P, RAC) chooses only among configurations whose validation Missing "
    "residual rate is below the same front end's AssocOnly validation Missing residual rate (learned arms and AssocOnly as five-seed "
    "means); when none qualifies the node-F1 maximum is chosen and recorded as constraint_not_satisfiable, and its result cannot "
    "support a claim that the arm's retraction reduces stale entities; ties to the smallest configuration index; main-gate metrics "
    "select nothing else"
)

FULL_VOCABULARY = ATOMS
#: Which atoms each arm may emit.  TAF and LOW never retract, so they never
#: hold a retracted entity, but a dormant one (shared dormancy rule) is
#: legally re-attached through REACTIVATE.  AssocOnly skips the existence
#: step entirely, so it never emits NOOP either, and therefore never
#: accumulates missed opportunities and never goes dormant.
VOCABULARY: dict[str, tuple[str, ...]] = {
    METHOD_ARM: FULL_VOCABULARY,
    "TAF": ("NOOP", "BIND", "BIRTH", "REACTIVATE"),
    "ELU-P": FULL_VOCABULARY,
    "RAC": FULL_VOCABULARY,
    "LOW": ("NOOP", "BIND", "BIRTH", "REACTIVATE"),
    "NoVersion": FULL_VOCABULARY,
    "HandCost": FULL_VOCABULARY,
    "HeuristicLabel": FULL_VOCABULARY,
    "AssocOnly": ("BIND", "BIRTH"),
    APPENDIX_ARM: FULL_VOCABULARY,
    OPTIONAL_ARM: FULL_VOCABULARY,
}

#: Whether an arm may re-attach a *retracted* entity.  RAC follows the DSG
#: adapter it stands in for: a removed node is re-created, never revived.
#: NoVersion deletes retracted entities, so the question never arises.
REACTIVATES_RETRACTED: dict[str, bool] = {
    METHOD_ARM: True,
    "TAF": False,
    "ELU-P": True,
    "RAC": False,
    "LOW": False,
    "NoVersion": False,
    "HandCost": True,
    "HeuristicLabel": True,
    "AssocOnly": False,
    APPENDIX_ARM: True,
    OPTIONAL_ARM: True,
}

#: The registered sentinel logit for an ineligible recalled pair.  A birth
#: column always exists with a bounded logit, so a sentinel cell can never
#: be part of an optimal assignment; the S0-03 forbidden cost is derived
#: from the matrix and therefore stays above it.
INELIGIBLE_LOGIT = -1.0e6

MAX_CONFIGS_PER_METHOD = 12

#: Grid parameters per arm, in the order configurations are enumerated.
GRID_PARAMETERS: dict[str, tuple[str, ...]] = {
    METHOD_ARM: ("tau_r",),
    "TAF": ("theta_a", "d_a"),
    "ELU-P": ("theta_a", "d_a", "free_space_weight", "retract_threshold"),
    "RAC": ("theta_a", "d_a", "rho_rac", "n_rac"),
    "LOW": ("d_low",),
    "NoVersion": ("tau_r",),
    "HandCost": ("theta_b", "rho_h"),
    "HeuristicLabel": ("tau_r",),
    "AssocOnly": (),
    OPTIONAL_ARM: ("tau_r",),
}

#: The distance-gate parameter of each rule arm; its grid must contain None.
NO_GATE_PARAMETER: dict[str, str] = {
    "TAF": "d_a", "ELU-P": "d_a", "RAC": "d_a", "LOW": "d_low",
}

#: ELU-P quantities fitted once on the train split, not grid-searched.
ELU_P_FITTED = ("initial_log_odds", "persistence_log_decay_per_tick", "match_gain")
#: Ruling 100-1 (ii) (2026-10-01): the three fitted scalars are kept per mask source.  ``arms.ELU-P.fitted`` holds the
#: simulator_instance_masks set (ruling 68 (10), unchanged); every other source has its own block under
#: ``fitted_by_mask_source``, null until that source's calibration pass is fitted by the same registered procedure and
#: the values are registered in place.  A pass reads the set of its episodes' mask source.  Since ruling 104-1 1b
#: (2026-10-05) both sets hold the S3-03 refit (``FROZEN_VALUES_BY_RULING`` below).
ELU_P_FITTED_MAIN_MASK_SOURCE = "simulator_instance_masks"
ELU_P_FITTED_PATHS = {
    "simulator_instance_masks": "arms.ELU-P.fitted",
    "sam2": "arms.ELU-P.fitted_by_mask_source.sam2",
}
ELU_P_FITTED_BY_MASK_SOURCE_RULE = (
    "ruling 100-1 (ii): the fitted block holds the three values of the simulator_instance_masks front end (ruling 68 (10)); "
    "every other mask source keeps its own three values under fitted_by_mask_source, null until that source's calibration "
    "pass is fitted by the same registered procedure (fit-elu-p over the calibration pass, ruling 75 (1)(a)) and the values "
    "are registered in place; a pass runs ELU-P at the set of its episodes' mask source and refuses while that set is null")

#: D-224-X ruling X4: one pre-registered ELU-P configuration produces the
#: memory rollouts for VSMT-lean's DAgger round 0 and the public decisions
#: HeuristicLabel trains on, in S2-05 and S3-03 alike.  It is a member of
#: the ELU-P grid with no distance gate, and it is fixed before any run, so
#: the learned arms' training data never depends on validation selection.
ROLLOUT_CONFIG_ARM = "ELU-P"
ROLLOUT_CONFIG_PATH = "arms.ELU-P.rollout_config"
ROLLOUT_CONFIG_PARAMETERS = ("theta_a", "free_space_weight", "retract_threshold")
ROLLOUT_CONFIG_GATE_PARAMETER = "d_a"

#: D-224-S1 ruling 68 (2026-09-25, LOG-256 sequel): the pre-registered grids, frozen from the
#: 39-episode calibration quantiles (same-object cosine to the entity mean p50 0.78 against 0.60 for
#: other objects, crossing near 0.7; 35 / 46 / 65 percent of same-object pairs within 0.5 / 1 / 2 m;
#: free-space coverage not separating gone from present under the geometry rule of the time -- the
#: block frustum, replaced by ruling 74 on 2026-09-26 -- so the RAC and ELU-P grids bracket the
#: 0.65 baseline).  At most twelve configurations per method, every
#: rule arm with a no-gate member; the contract must carry exactly these values.
#: D-224-S1 ruling 87-1 (2026-09-29, LOG-283/284): every tau_r grid extended down by 0.15, 0.2 and 0.25 (ten values,
#: within the twelve-configuration budget) because the trained existence heads score almost every candidate below
#: 0.3; the four tau_r grids stay identical so the ablations share VSMT-lean's configuration space.
FROZEN_GRIDS: dict[str, dict[str, list[Any]]] = {
    METHOD_ARM: {"tau_r": [0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]},
    "TAF": {"theta_a": [0.6, 0.7, 0.8], "d_a": [None, 0.5, 1.0, 2.0]},
    "ELU-P": {"theta_a": [0.7], "d_a": [None, 1.0], "free_space_weight": [0.5, 1.0, 2.0], "retract_threshold": [0.0, -1.0]},
    "RAC": {"theta_a": [0.7], "d_a": [None, 1.0], "rho_rac": [0.7, 0.85], "n_rac": [2, 3, 5]},
    "LOW": {"d_low": [None, 0.25, 0.5, 1.0, 2.0]},
    "NoVersion": {"tau_r": [0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]},
    "HandCost": {"theta_b": [0.6, 0.7, 0.8], "rho_h": [0.6, 0.7, 0.8, 0.9]},
    "HeuristicLabel": {"tau_r": [0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]},
    "AssocOnly": {},
    OPTIONAL_ARM: {"tau_r": [0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]},
}
#: Ruling 68 (2): the ELU-P rollout configuration (theta_a, free_space_weight, retract_threshold), a
#: no-gate member of the ELU-P grid; DAgger round 0 and the HeuristicLabel labels use exactly it.
ROLLOUT_CONFIG: dict[str, float] = {"theta_a": 0.7, "free_space_weight": 1.0, "retract_threshold": 0.0}
#: Ruling 68 (4): the two training values METHOD proposed; the seeds are not configurations and the
#: development training uses the first one only.
WEIGHT_DECAY = 1e-4
SEEDS = (7, 19, 31, 43, 59)

SPLIT_ALLOWED: dict[str, tuple[str, ...]] = {
    **{arm: SPLITS for arm in ALL_ARMS},
    APPENDIX_ARM: ("validation",),
}

#: VSMT-lean training recipe values already frozen by D-224 (its "base model" item).
TRAINING_FROZEN = (
    ("arms.VSMT-lean.training.learning_rate", 1e-3),
    ("arms.VSMT-lean.training.epochs", 20),
    ("arms.VSMT-lean.training.seed_count", 5),
    ("arms.VSMT-lean.training.dagger_rounds", 2),
    ("arms.VSMT-lean.training.main_table_round", 1),
)

DECOMPOSITION = ("recall_miss", "teacher_error", "amortization_error")


class LeanArmsError(ValueError):
    """Raised for any malformed arm input, illegal atom or contract mismatch."""


# --------------------------------------------------------------------------
# small validators
# --------------------------------------------------------------------------

def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LeanArmsError(code)


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


def _arm(arm: str) -> str:
    _require(arm in ALL_ARMS, f"arm_unknown:{arm}")
    return arm


def feature_index(order: Sequence[str], name: str) -> int:
    """Position of a feature in a sealed feature order; the order is the contract."""

    names = [str(item) for item in order]
    _require(name in names, f"feature_missing:{name}")
    return names.index(name)


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        return 1.0 / (1.0 + math.exp(-value))
    exponent = math.exp(value)
    return exponent / (1.0 + exponent)


# --------------------------------------------------------------------------
# 1. association and birth logits of the rule arms
# --------------------------------------------------------------------------

def gate_association_logits(
    inputs: Mapping[str, Any], *, theta_a: float, d_a: float | None,
    reactivates_retracted: bool,
) -> dict[str, Any]:
    """ConceptGraphs-style gate with a graded cost inside it (TAF, ELU-P, RAC; also the HeuristicLabel labeller).

    HandCost has its own ``hand_cost_association_logits``.  From the sealed stage-A rows: a pair with cosine
    >= theta_a and centroid distance <= d_a (None: no distance gate) gets logit = cosine, any other pair the
    registered sentinel; every BIRTH logit is theta_a.  Under the joint solve a fragment therefore binds when
    its best eligible cosine is at least theta_a and is born otherwise, and between two eligible entities the
    higher cosine wins, not the id order.  An arm that does not revive retracted entities gives retracted rows
    the sentinel.  Reads only the sealed rows, not the memory.
    """

    theta = _finite(theta_a, "theta_a_invalid")
    _require(-1.0 <= theta <= 1.0, "theta_a_invalid")
    if d_a is not None:
        gate = _finite(d_a, "d_a_invalid")
        _require(gate > 0.0, "d_a_invalid")
    order = inputs["association_feature_order"]
    cosine_at = feature_index(order, "cosine_to_descriptor_mean")
    distance_at = feature_index(order, "centroid_distance_m")
    retracted_at = feature_index(order, "state_is_retracted")
    association: dict[str, float] = {}
    for row in inputs["association_rows"]:
        features = row["features"]
        cosine = float(features[cosine_at])
        distance = float(features[distance_at])
        retracted = float(features[retracted_at]) == 1.0
        eligible = cosine >= theta and (d_a is None or distance <= gate)
        if retracted and not reactivates_retracted:
            eligible = False
        association[f"{row['fragment_id']}|{row['entity_id']}"] = cosine if eligible else INELIGIBLE_LOGIT
    birth = {str(fragment_id): theta for fragment_id in inputs["rows"]}
    return {"association_logits": association, "birth_logits": birth}


def low_association_logits(inputs: Mapping[str, Any], *, d_low: float | None) -> dict[str, Any]:
    """Last-observation-wins: the nearest centroid within d_low takes the fragment (LOW).

    Logit = -centroid distance inside the gate, the sentinel outside it or for a retracted entity; BIRTH logit
    = -d_low, so the nearest entity wins and a fragment farther than d_low is born.  With d_low None (no gate)
    the BIRTH logit is -(the fragment's largest eligible recalled distance + 1), so any recalled entity beats
    BIRTH.  LOW reads no descriptor, never retracts and never revives a retracted entity.
    """

    if d_low is not None:
        gate = _finite(d_low, "d_low_invalid")
        _require(gate > 0.0, "d_low_invalid")
    order = inputs["association_feature_order"]
    distance_at = feature_index(order, "centroid_distance_m")
    retracted_at = feature_index(order, "state_is_retracted")
    association: dict[str, float] = {}
    farthest: dict[str, float] = {str(fragment_id): 0.0 for fragment_id in inputs["rows"]}
    for row in inputs["association_rows"]:
        features = row["features"]
        distance = float(features[distance_at])
        retracted = float(features[retracted_at]) == 1.0
        eligible = (d_low is None or distance <= gate) and not retracted
        key = f"{row['fragment_id']}|{row['entity_id']}"
        association[key] = -distance if eligible else INELIGIBLE_LOGIT
        if eligible:
            farthest[str(row["fragment_id"])] = max(farthest[str(row["fragment_id"])], distance)
    birth = {
        fragment_id: (-(farthest[fragment_id] + 1.0) if d_low is None else -gate)
        for fragment_id in farthest
    }
    return {"association_logits": association, "birth_logits": birth}


def hand_cost_association_logits(inputs: Mapping[str, Any], *, theta_b: float) -> dict[str, Any]:
    """Stateless hand scores in VSMT-lean's association and birth slots (HandCost, D-224-SW ruling S).

    Logit = cosine for every recalled pair (no gate; a retracted entity may be revived) and BIRTH logit =
    theta_b.  The decision structure and the solver are VSMT-lean's with the learned heads replaced by two hand
    scores, so HandCost measures what learned costs add under the same structure; ELU-P separately measures
    temporally accumulated probabilistic forgetting.  No gradient.
    """

    theta = _finite(theta_b, "theta_b_invalid")
    _require(-1.0 <= theta <= 1.0, "theta_b_invalid")
    order = inputs["association_feature_order"]
    cosine_at = feature_index(order, "cosine_to_descriptor_mean")
    association = {
        f"{row['fragment_id']}|{row['entity_id']}": float(row["features"][cosine_at])
        for row in inputs["association_rows"]
    }
    birth = {str(fragment_id): theta for fragment_id in inputs["rows"]}
    return {"association_logits": association, "birth_logits": birth}


def hand_cost_existence(rows: Sequence[Mapping[str, Any]], order: Sequence[str], *, rho_h: float) -> dict[str, str]:
    """Stateless hand score in VSMT-lean's existence slot: this frame's free-space coverage against rho_h."""

    rho = _finite(rho_h, "rho_h_invalid")
    _require(0.0 < rho <= 1.0, "rho_h_invalid")
    coverage_at = feature_index(order, "free_space_coverage_ratio")
    return {
        str(row["entity_id"]): ("RETRACT" if float(row["features"][coverage_at]) >= rho else "NOOP")
        for row in rows
    }


def sentinel_pairs(association_logits: Mapping[str, float]) -> list[str]:
    """Keys whose logit is the ineligible sentinel; an assignment must contain none."""

    return sorted(key for key, value in association_logits.items() if value == INELIGIBLE_LOGIT)


def assert_no_sentinel_chosen(assignment: Mapping[str, str], association_logits: Mapping[str, float]) -> None:
    """The solver must never have picked an ineligible pair."""

    for fragment_id, column in assignment.items():
        if str(column).startswith(BIRTH_COLUMN_PREFIX):
            continue
        key = f"{fragment_id}|{column}"
        _require(key in association_logits, f"assignment_pair_not_scored:{key}")
        _require(association_logits[key] != INELIGIBLE_LOGIT, f"sentinel_pair_chosen:{key}")


# --------------------------------------------------------------------------
# 2. existence decisions
# --------------------------------------------------------------------------

def eligible_existence_rows(
    rows: Sequence[Mapping[str, Any]], order: Sequence[str], *, visible_min_ratio: float,
) -> dict[str, Any]:
    """Keep the stage B rows that are active or dormant and should be visible this frame.

    Also returns the two excluded lists: rows below the should-be-visible minimum (not seen this frame, so not
    a miss) and retracted rows (no RETRACT or NOOP to decide).  The filter is shared by all arms because it
    decides which entities accumulate missed opportunities and go dormant.
    """

    minimum = _finite(visible_min_ratio, "visible_min_ratio_invalid")
    _require(0.0 < minimum <= 1.0, "visible_min_ratio_invalid")
    visible_at = feature_index(order, "should_be_visible_ratio")
    retracted_at = feature_index(order, "state_is_retracted")
    eligible: list[Mapping[str, Any]] = []
    not_visible: list[str] = []
    retracted: list[str] = []
    for row in rows:
        entity_id = str(row["entity_id"])
        if float(row["features"][retracted_at]) == 1.0:
            retracted.append(entity_id)
        elif float(row["features"][visible_at]) < minimum:
            not_visible.append(entity_id)
        else:
            eligible.append(row)
    return {"eligible": eligible, "excluded_not_visible": not_visible, "excluded_retracted": retracted}


def never_retract(rows: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    """TAF and LOW: every eligible candidate gets NOOP; misses still accumulate."""

    return {str(row["entity_id"]): "NOOP" for row in rows}


def skip_existence(rows: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    """AssocOnly: no existence decision at all, so no NOOP and hence no dormancy."""

    return {}


def elu_p_existence(
    rows: Sequence[Mapping[str, Any]], order: Sequence[str], *, state: Mapping[str, float],
    initial_log_odds: float, persistence_log_decay_per_tick: float, free_space_weight: float,
    retract_threshold: float,
) -> dict[str, Any]:
    """Fusion++ log-odds existence with a Perpetua-style persistence decay (ELU-P; also the HeuristicLabel labeller).

    HandCost has its own ``hand_cost_existence``.  For every eligible row (should be visible, unassigned) the
    entity's log-odds (``initial_log_odds`` when it has none yet) loses the persistence decay and
    ``free_space_weight`` x its free-space coverage; below ``retract_threshold`` the decision is RETRACT,
    otherwise NOOP.  Returns the decisions and the updated log-odds.  Reads no future and no private data; the
    persistence decay and the match gain are fitted on train only and are not grid parameters.
    """

    initial = _finite(initial_log_odds, "initial_log_odds_invalid")
    decay = _finite(persistence_log_decay_per_tick, "persistence_decay_invalid")
    _require(decay >= 0.0, "persistence_decay_invalid")
    weight = _finite(free_space_weight, "free_space_weight_invalid")
    _require(weight >= 0.0, "free_space_weight_invalid")
    threshold = _finite(retract_threshold, "retract_threshold_invalid")
    coverage_at = feature_index(order, "free_space_coverage_ratio")
    decisions: dict[str, str] = {}
    updated = {str(key): float(value) for key, value in state.items()}
    for row in rows:
        entity_id = str(row["entity_id"])
        coverage = float(row["features"][coverage_at])
        log_odds = updated.get(entity_id, initial) - decay - weight * coverage
        updated[entity_id] = log_odds
        decisions[entity_id] = "RETRACT" if log_odds < threshold else "NOOP"
    return {"decisions": decisions, "state": updated}


def elu_p_observe_matches(
    state: Mapping[str, float], entity_ids: Sequence[str], *, initial_log_odds: float, match_gain: float,
) -> dict[str, float]:
    """A match raises the entity's log-odds by the fitted gain."""

    initial = _finite(initial_log_odds, "initial_log_odds_invalid")
    gain = _finite(match_gain, "match_gain_invalid")
    _require(gain >= 0.0, "match_gain_invalid")
    updated = {str(key): float(value) for key, value in state.items()}
    for entity_id in entity_ids:
        updated[str(entity_id)] = updated.get(str(entity_id), initial) + gain
    return updated


def rac_existence(
    rows: Sequence[Mapping[str, Any]], order: Sequence[str], *, state: Mapping[str, int],
    rho_rac: float, n_rac: int,
) -> dict[str, Any]:
    """DSG-style render-and-compare: n consecutive negative renders retract (RAC).

    The comparison is the shared ``free_space_coverage_ratio`` of the existence row (rulings 74/75): of the
    entity's last seen surface points that fall on a valid depth in this frame and are not occluded, the share
    whose measured depth lies more than the margin (0.05 m) beyond the point.  An eligible frame with that share
    >= rho_rac adds one negative render, any other eligible frame resets the run to 0; reaching n_rac records
    RETRACT and resets the run.  A match also resets it (``rac_observe_matches``).  Returns the decisions and the
    updated runs.  RAC and ELU-P differ only in the decision rule, not in the comparison.
    """

    rho = _finite(rho_rac, "rho_rac_invalid")
    _require(0.0 < rho <= 1.0, "rho_rac_invalid")
    limit = _int(n_rac, "n_rac_invalid", minimum=1)
    coverage_at = feature_index(order, "free_space_coverage_ratio")
    decisions: dict[str, str] = {}
    updated = {str(key): int(value) for key, value in state.items()}
    for row in rows:
        entity_id = str(row["entity_id"])
        coverage = float(row["features"][coverage_at])
        count = updated.get(entity_id, 0) + 1 if coverage >= rho else 0
        if count >= limit:
            decisions[entity_id] = "RETRACT"
            updated[entity_id] = 0
        else:
            decisions[entity_id] = "NOOP"
            updated[entity_id] = count
    return {"decisions": decisions, "state": updated}


def rac_observe_matches(state: Mapping[str, int], entity_ids: Sequence[str]) -> dict[str, int]:
    """A match clears the entity's negative-evidence counter."""

    updated = {str(key): int(value) for key, value in state.items()}
    for entity_id in entity_ids:
        updated[str(entity_id)] = 0
    return updated


def learned_existence(existence_logits: Mapping[str, float], *, tau_r: float) -> dict[str, str]:
    """VSMT-lean and its learned ablations: sigmoid(r) >= tau_r retracts."""

    tau = _finite(tau_r, "tau_r_invalid")
    _require(0.0 < tau < 1.0, "tau_r_invalid")
    return {
        str(entity_id): ("RETRACT" if _sigmoid(_finite(value, "existence_logit_invalid")) >= tau else "NOOP")
        for entity_id, value in sorted(existence_logits.items())
    }


# --------------------------------------------------------------------------
# 3. compiling an arm's frame program
# --------------------------------------------------------------------------

def compile_program(
    assignment: Mapping[str, str], entity_states: Mapping[str, str], *, arm: str,
    existence_decisions: Mapping[str, str],
) -> list[dict[str, Any]]:
    """Turn an assignment plus existence decisions into atoms, within the arm's vocabulary.

    A fragment assigned to an active entity gives BIND, to a dormant or retracted entity REACTIVATE, to its own
    birth column BIRTH; the existence decisions become RETRACT or NOOP as given.  An atom outside the arm's
    vocabulary is refused (AssocOnly allows only BIND and BIRTH), and so is an assignment to a retracted entity
    for an arm that does not revive retracted entities.  Executes nothing: that is the S0-01 executor's job.
    """

    name = _arm(arm)
    vocabulary = VOCABULARY[name]
    operations: list[dict[str, Any]] = []
    for fragment_id in sorted(assignment):
        column = str(assignment[fragment_id])
        if column.startswith(BIRTH_COLUMN_PREFIX):
            _require(column == f"{BIRTH_COLUMN_PREFIX}{fragment_id}", "fragment_took_another_birth_column")
            atom = "BIRTH"
            record: dict[str, Any] = {"atom": atom, "fragment_id": str(fragment_id)}
        else:
            _require(column in entity_states, f"assigned_entity_unknown:{column}")
            state = entity_states[column]
            _require(state in ENTITY_STATES, f"entity_state_invalid:{column}")
            if state == "active":
                atom = "BIND"
            else:
                atom = "REACTIVATE"
                _require(
                    state != "retracted" or REACTIVATES_RETRACTED[name],
                    f"arm_cannot_reactivate_retracted:{name}",
                )
            record = {"atom": atom, "entity_id": column, "fragment_id": str(fragment_id)}
        _require(atom in vocabulary, f"atom_outside_arm_vocabulary:{name}:{atom}")
        operations.append(record)
    assigned = {op["entity_id"] for op in operations if "entity_id" in op}
    for entity_id in sorted(existence_decisions):
        decision = existence_decisions[entity_id]
        _require(decision in {"RETRACT", "NOOP"}, "decision_not_retract_or_noop")
        _require(entity_id not in assigned, f"existence_decision_on_assigned_entity:{entity_id}")
        _require(decision in vocabulary, f"atom_outside_arm_vocabulary:{name}:{decision}")
        operations.append({"atom": decision, "entity_id": str(entity_id)})
    return operations


# --------------------------------------------------------------------------
# 4. the NoVersion ablation
# --------------------------------------------------------------------------

def apply_no_version(memory: Mapping[str, Any]) -> dict[str, Any]:
    """Physically delete every retracted entity and reseal (NoVersion).

    This is the NoVersion ablation's definition: a retraction is a deletion, the record disappears with its
    versions, and a reappearance can only be a BIRTH.  The recall rule, the cost heads and the training are
    unchanged.
    """

    # 2026-09-27, engineering: no deep copies.  The memory carries its whole history, and the three copies this made
    # per frame (validate, seal, validate) grew with the frames already run.  The result is a new top-level object
    # that shares the kept records with the input; sealed records are never changed in place (LOG-254), so the
    # content and the digest are the same as the copying version's.
    checked = validate_memory(memory, copy=False)
    deleted = sorted(str(entity["entity_id"]) for entity in checked["entities"] if entity["state"] == "retracted")
    kept = {key: value for key, value in checked.items() if key != "memory_digest"}
    kept["entities"] = [entity for entity in checked["entities"] if entity["state"] != "retracted"]
    kept["memory_digest"] = memory_digest(kept)
    result = validate_memory(kept, copy=False)
    result["no_version_deleted"] = deleted
    return result


# --------------------------------------------------------------------------
# 5. configuration grids, split guard and the optional arm
# --------------------------------------------------------------------------

def enumerate_configs(arm: str, grid: Mapping[str, Sequence[Any]]) -> list[dict[str, Any]]:
    """Cartesian product of the registered parameters, in registered order."""

    name = _arm(arm)
    parameters = GRID_PARAMETERS.get(name)
    _require(parameters is not None, f"arm_has_no_grid:{name}")
    _require(set(grid.keys()) == set(parameters), f"grid_parameters_mismatch:{name}")
    for parameter in parameters:
        values = grid[parameter]
        _require(type(values) is list and values, f"grid_values_invalid:{name}.{parameter}")
        _require(len(set(map(repr, values))) == len(values), f"grid_values_duplicate:{name}.{parameter}")
    combos = itertools.product(*(grid[parameter] for parameter in parameters))
    return [dict(zip(parameters, combo, strict=True)) for combo in combos]


def assert_config_budget(configs: Sequence[Mapping[str, Any]], *, limit: int = MAX_CONFIGS_PER_METHOD) -> int:
    _require(len(configs) <= limit, f"config_budget_exceeded:{len(configs)}>{limit}")
    return len(configs)


def assert_no_gate_option(arm: str, grid: Mapping[str, Sequence[Any]]) -> None:
    """D-224-R precondition two: a rule arm's distance grid must contain None (no gate)."""

    name = _arm(arm)
    parameter = NO_GATE_PARAMETER.get(name)
    _require(parameter is not None, f"arm_has_no_distance_gate:{name}")
    _require(None in list(grid.get(parameter, [])), f"grid_lacks_no_gate_option:{name}.{parameter}")


def assert_rollout_config(
    rollout: Mapping[str, Any], grid: Mapping[str, Sequence[Any]],
) -> dict[str, Any]:
    """The registered ELU-P rollout configuration must be a no-gate member of the grid.

    Returns the three registered values completed with d_a = None, refused when that is not a grid member
    (D-224-X ruling X4).  The configuration produces VSMT-lean's DAgger round-0 memory rollouts and
    HeuristicLabel's public labels, the same cell in S2-05 and S3-03, independent of validation selection.
    Selects nothing.
    """

    _require(tuple(rollout.keys()) == ROLLOUT_CONFIG_PARAMETERS, "rollout_config_parameters_mismatch")
    for name in ROLLOUT_CONFIG_PARAMETERS:
        _finite(rollout[name], f"rollout_config_value_invalid:{name}")
    full = {**{name: rollout[name] for name in ROLLOUT_CONFIG_PARAMETERS}, ROLLOUT_CONFIG_GATE_PARAMETER: None}
    members = enumerate_configs(ROLLOUT_CONFIG_ARM, grid)
    _require(
        any(all(member[key] == full[key] for key in member) for member in members),
        "rollout_config_not_a_grid_member",
    )
    return full


def arms_without_atom(atom: str) -> tuple[str, ...]:
    """Arms whose vocabulary lacks ``atom``, in registered order.

    For RETRACT these are TAF, LOW and AssocOnly: they never retract, the false retract rate is undefined for
    them by construction, and the S0-04 exclusion list and pairing treat them as not applicable (D-224-X ruling
    X2, review revision, LOG-225).
    """

    _require(atom in ATOMS, f"atom_unknown:{atom}")
    return tuple(arm for arm in ALL_ARMS if atom not in VOCABULARY[arm])


def assert_split_allowed(arm: str, split: str) -> None:
    """LLM-op runs on validation only; every other arm may see each split (test read once, S0-04)."""

    name = _arm(arm)
    _require(split in SPLITS, f"split_unknown:{split}")
    _require(split in SPLIT_ALLOWED[name], f"split_not_allowed:{name}:{split}")


def ctx_admission(totals: Mapping[str, int]) -> dict[str, Any]:
    """VSMT-lean-ctx is admitted only if amortization error is the largest S2-05 class.

    Input: VSMT-lean's three decomposition counts on the S2-05 development table.  Only when the model's own
    errors (amortization error) exceed both recall misses and teacher errors does a stronger decision network
    have a target; otherwise the bottleneck is the front end or the labels and, per D-224-EFG, the front end
    is changed first.  Reads no metric value.  The optional arm was dropped from S3 (registered, not run;
    METHOD section 10); only the tests call this function.
    """

    counts = {name: _int(totals[name], f"decomposition_count_invalid:{name}", minimum=0) for name in DECOMPOSITION}
    largest = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
    admitted = (
        counts["amortization_error"] > counts["recall_miss"]
        and counts["amortization_error"] > counts["teacher_error"]
    )
    return {"admitted": admitted, "largest": largest, "counts": counts}


# --------------------------------------------------------------------------
# machine contract
# --------------------------------------------------------------------------

def _arm_section_path(arm: str) -> str:
    """Where an arm's section lives in the contract."""

    if arm == APPENDIX_ARM:
        return "appendix_arm"
    if arm == OPTIONAL_ARM:
        return "optional_arm"
    if arm in ABLATION_ARMS:
        return f"ablations.{arm}"
    return f"arms.{arm}"


#: Every boolean claim the contract may make, with the value this
#: implementation enforces.  The per-arm reactivation flags and the no-gate
#: declarations are generated from the tables above so the contract cannot
#: drift from the code.
EXPECTED_BOOLEAN_CLAIMS: dict[str, bool] = {
    "authorization.arm_implementation_run": False,
    "authorization.grid_selection": False,
    "authorization.training": False,
    "authorization.llm_op_run": False,
    "authorization.test_split_read": False,
    "authorization.server_run": False,
    "shared.same_frontend_recall_dedup_dormancy_executor_and_evaluator": True,
    "shared.all_arms_fill_the_same_cost_matrix_and_use_the_same_solver": True,
    "shared.rule_arms_have_no_gradient": True,
    "shared.existence_candidates_are_active_or_dormant_and_should_be_visible": True,
    "cost_interface.rule_arm_costs_are_graded_inside_the_gate": True,
    "cost_interface.ineligible_pairs_use_the_registered_sentinel": True,
    "cost_interface.sentinel_never_wins_because_a_birth_column_always_exists": True,
    "cost_interface.feature_positions_read_from_the_sealed_order": True,
    "arms.VSMT-lean.retracts": True,
    "arms.VSMT-lean.training.seeds_are_not_configurations": True,
    "arms.VSMT-lean.training.early_stopping_on_validation_loss": True,
    "arms.TAF.retracts": False,
    "arms.ELU-P.retracts": True,
    "arms.ELU-P.fitted_quantities_never_grid_searched": True,
    "arms.RAC.retracts": True,
    "arms.RAC.rendering_is_the_shared_frontend_free_space_test": True,
    "arms.LOW.retracts": False,
    "ablations.NoVersion.retracted_entities_physically_deleted": True,
    "ablations.NoVersion.recall_heads_and_training_unchanged": True,
    "ablations.HandCost.no_gradient": True,
    "ablations.HeuristicLabel.labels_are_the_public_decisions_of_the_rollout_arm": True,
    "ablations.HeuristicLabel.private_truth_enters_only_through_the_rollout_arms_three_fitted_scalars": True,
    "ablations.AssocOnly.existence_step_skipped_so_no_dormancy": True,
    "ablations.AssocOnly.reported_in_main_table": True,
    "appendix_arm.validation_only": True,
    "appendix_arm.never_in_main_table": True,
    "appendix_arm.never_in_test": True,
    "appendix_arm.config_budget_not_applicable": True,
    "optional_arm.admission_requires_amortization_error_largest_in_s2_05": True,
    "optional_arm.shares_training_budget_and_config_count_with_mlp": True,
    "optional_arm.reported_separately": True,
    "optional_arm.may_not_replace_main_row_after_test": True,
    "budget.grids_preregistered_before_any_run": True,
    "budget.every_rule_arm_grid_includes_a_no_gate_option": True,
    "budget.thresholds_selected_on_validation_only": True,
    "budget.no_values_copied_from_other_datasets": True,
    "budget.test_never_selects": True,
    "continue_gate.every_method_grid_at_most_twelve_and_preregistered": True,
    "continue_gate.rule_arms_no_gradient": True,
    "continue_gate.every_boolean_claim_is_bound_by_the_validator": True,
    # D-224-X (v2)
    "supersedes_contract.v1_bytes_frozen": True,
    "arms.VSMT-lean.training.dagger_round_0_uses_the_registered_rollout_config": True,
    "arms.ELU-P.rollout_config_is_a_grid_member_with_no_distance_gate": True,
    "arms.ELU-P.rollout_config_independent_of_validation_selection": True,
    "arms.ELU-P.fitting_procedure.uses_train_private_truth_only": True,
    "arms.ELU-P.fitting_procedure.runs_after_the_train_split_feature_seals": True,
    "arms.ELU-P.fitting_procedure.match_gain_fitted_at_the_rollout_config_and_shared_by_every_config": True,
    "ablations.HeuristicLabel.labels_from_the_registered_rollout_config": True,
    "ablations.HeuristicLabel.retrained_not_weight_reuse": True,
    "ablations.AssocOnly.retrained_not_weight_reuse": True,
    "ablations.AssocOnly.existence_loss_term_removed": True,
    "ablations.AssocOnly.same_architecture_recipe_budget_and_dagger_rounds": True,
}

#: D-224-X rulings this v2 implements; the contract must name them.
V2_RULINGS_DECISION_ID = "D-224-X"
V2_RULING_KEYS = ("X3", "X4")
EXPECTED_BOOLEAN_CLAIMS.update({
    f"{_arm_section_path(arm)}.reactivates_retracted": flag
    for arm, flag in REACTIVATES_RETRACTED.items()
})
EXPECTED_BOOLEAN_CLAIMS.update({
    f"{_arm_section_path(arm)}.grid.{parameter}.must_include_none_meaning_no_gate": True
    for arm, parameter in NO_GATE_PARAMETER.items()
})

#: The shared should-be-visible minimum.
#: D-224-S1 ruling 67 (2026-09-24) froze the shared should-be-visible minimum at 0.5; ruling 68
#: (2026-09-25, LOG-256 sequel) superseded it with 1/64: the cache's visible volume lies before the
#: depth surface while entity boxes are surface shells, so 0.5 admitted 0.2 percent of entity-frames
#: (2,068 existence candidates in 44,097 frames); one of the 64 cell centres before the surface now
#: makes an entity should-be-visible (3.5 percent of entity-frames).  That rationale counted the 64
#: cell centres of the entity box grid; since ruling 75 the ratio is over the entity's last seen
#: surface points (up to 64 per fragment of its latest evidence frame), so one observed point suffices
#: for an entity with at most 64 points and an entity with more needs proportionally more.
SHOULD_BE_VISIBLE_MIN_RATIO = 1.0 / 64.0
FROZEN_VALUES_BY_RULING = (
    ("shared.should_be_visible_min_ratio", SHOULD_BE_VISIBLE_MIN_RATIO, "D-224-S1 ruling 68"),
    ("arms.VSMT-lean.training.weight_decay", WEIGHT_DECAY, "D-224-S1 ruling 68"),
    ("arms.VSMT-lean.training.seeds", list(SEEDS), "D-224-S1 ruling 68"),
    # Ruling 104-1 1b (2026-10-05): the S3 refit replaces the development sets in place (the development values -- ruling
    # 68 (10), 2026-09-27, and the SAM2 set of 2026-10-02 -- are recorded in S0-05 user_rulings.superseded_values and in the
    # cross-contract ledger).  Counts of the S3-03 calibration pass (TAF at the rollout theta_a, no gate) over the usable S3
    # train episodes, fit at 24df324 (run s3-03-run, tag 10f7013):
    # instance segmentation, 252 episodes (the adopted 74905f4 pre-fit): 773,589 of 780,515 object frames in place, 804
    # events in 41,298,511 object ticks, hits 1,699,298 of 5,448,054 against false matches 448 of 48,538.
    *((f"arms.ELU-P.fitted.{name}", value, "D-224-S1 ruling 104-1 1b") for name, value in (
        ("initial_log_odds", 4.715758278823018),
        ("persistence_log_decay_per_tick", 1.9468203738496008e-05),
        ("match_gain", 3.5202657867949485),
    )),
    # SAM2, 249 episodes (three train caches failed, so the truth-only values differ from the instance set too): 759,272 of
    # 766,085 object frames in place, 792 events in 40,367,761 object ticks, hits 1,298,322 of 5,158,352 against false
    # matches 376 of 46,734.
    *((f"{ELU_P_FITTED_PATHS['sam2']}.{name}", value, "D-224-S1 ruling 104-1 1b") for name, value in (
        ("initial_log_odds", 4.713527527677658),
        ("persistence_log_decay_per_tick", 1.961980922031749e-05),
        ("match_gain", 3.4430935995987832),
    )),
)

#: Policy values that must still be null: none since the SAM2 fit was registered (2026-10-02); the SAM2 set was open
#: from ruling 100-1 (ii) (2026-10-01) until then.
NULL_POLICY_PATHS: tuple[str, ...] = ()

FROZEN_CONSTANTS = (
    ("cost_interface.ineligible_logit", INELIGIBLE_LOGIT, "D-224-R"),
    ("budget.max_full_configs_per_method", MAX_CONFIGS_PER_METHOD, "D-224"),
    ("budget.selection_metric", SELECTION_METRIC, "D-224-SW"),
    *((path, value, "D-224") for path, value in TRAINING_FROZEN),
)


def _walk(value: Any, prefix: str, out: dict[str, bool]) -> None:
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


def elu_p_fitted(contract: Mapping[str, Any], mask_source: str) -> dict[str, Any]:
    """ELU-P's three fitted scalars for one mask source, as the S0-05 contract registers them (ruling 100-1 (ii)).

    The initial log-odds, the persistence decay and the match gain are fitted on each front end's calibration
    pass.  Instance segmentation reads the ``fitted`` block (ruling 68 (10)), SAM2 ``fitted_by_mask_source.sam2``;
    before a set is fitted and registered its values are None and the entries refuse to run ELU-P (as SAM2's
    round 0 was refused before the S2-06 fit).  Since ruling 104-1 1b both sets hold the S3-03 refit
    (``FROZEN_VALUES_BY_RULING``).  Fits and changes nothing.
    """

    _require(mask_source in ELU_P_FITTED_PATHS, f"elu_p_fitted_unregistered_mask_source:{mask_source}")
    block = _lookup(contract, ELU_P_FITTED_PATHS[mask_source])
    _require(type(block) is dict and tuple(block) == ELU_P_FITTED, f"contract_elu_p_fitted_mismatch:{mask_source}")
    return {name: block[name] for name in ELU_P_FITTED}


def validate_arms_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Check that the S0-05 machine contract agrees with this implementation.

    Returns a copy and refuses any claim that disagrees with the code: every boolean leaf must be in
    ``EXPECTED_BOOLEAN_CLAIMS`` with the same value; the arm lists, vocabularies, grid parameter names,
    reactivation flags, sentinel, configuration limit and D-224 training constants are compared exactly; the
    paths in ``NULL_POLICY_PATHS`` must be null (none since 2026-10-02) and ``FROZEN_VALUES_BY_RULING`` must
    match; filled grids must equal ``FROZEN_GRIDS``, stay within 12 configurations and, for a rule arm, include
    the no-gate option.
    """

    _require(type(contract) is dict, "contract_not_object")
    _require(contract.get("schema_version") == CONTRACT_SCHEMA_VERSION, "contract_schema_version_invalid")
    _require(contract.get("decision_id") == "D-224", "contract_decision_id_invalid")
    _require(contract.get("stage_id") == "S0-05", "contract_stage_id_invalid")
    required = {
        "authorization", "shared", "cost_interface", "arms", "ablations",
        "appendix_arm", "optional_arm", "budget", "continue_gate", "user_rulings",
    }
    missing = sorted(required - set(contract.keys()))
    _require(not missing, f"contract_missing_sections:{','.join(missing)}")

    found: dict[str, bool] = {}
    _walk(contract, "", found)
    for path in sorted(set(found) - set(EXPECTED_BOOLEAN_CLAIMS)):
        raise LeanArmsError(f"contract_unbound_boolean_claim:{path}")
    for path in sorted(set(EXPECTED_BOOLEAN_CLAIMS) - set(found)):
        raise LeanArmsError(f"contract_missing_boolean_claim:{path}")
    for path, expected in EXPECTED_BOOLEAN_CLAIMS.items():
        _require(found[path] is expected, f"contract_claim_flipped:{path}")

    arms = contract["arms"]
    _require(arms["method"] == METHOD_ARM, "contract_method_arm_mismatch")
    _require(tuple(arms["controls"]) == CONTROL_ARMS, "contract_controls_mismatch")
    _require(tuple(arms["main_table"]) == MAIN_TABLE_ARMS, "contract_main_table_mismatch")
    _require(tuple(contract["ablations"]["names"]) == ABLATION_ARMS, "contract_ablations_mismatch")
    _require(contract["appendix_arm"]["name"] == APPENDIX_ARM, "contract_appendix_arm_mismatch")
    _require(tuple(contract["appendix_arm"]["splits_allowed"]) == SPLIT_ALLOWED[APPENDIX_ARM], "contract_appendix_split_mismatch")
    _require(contract["optional_arm"]["name"] == OPTIONAL_ARM, "contract_optional_arm_mismatch")

    for arm in ALL_ARMS:
        section = _lookup(contract, _arm_section_path(arm))
        _require(type(section) is dict, f"contract_arm_section_missing:{arm}")
        _require(tuple(section["vocabulary"]) == VOCABULARY[arm], f"contract_vocabulary_mismatch:{arm}")
        if arm in GRID_PARAMETERS:
            grid = section["grid"]
            _require(tuple(grid.keys()) == GRID_PARAMETERS[arm], f"contract_grid_parameters_mismatch:{arm}")
            frozen = {name: spec.get("values") for name, spec in grid.items()}
            if all(values is not None for values in frozen.values()) and frozen:
                configs = enumerate_configs(arm, frozen)
                assert_config_budget(configs)
                if arm in NO_GATE_PARAMETER:
                    assert_no_gate_option(arm, frozen)
                _require(frozen == FROZEN_GRIDS[arm], f"contract_grid_values_mismatch:{arm}")  # ruling 68 (1)
            elif arm in NO_GATE_PARAMETER:
                _require(
                    grid[NO_GATE_PARAMETER[arm]].get("must_include_none_meaning_no_gate") is True,
                    f"contract_no_gate_option_not_declared:{arm}",
                )
    for arm in RULE_ARMS:
        section = _lookup(contract, _arm_section_path(arm))
        _require(section.get("gradient") == "none", f"contract_rule_arm_gradient_mismatch:{arm}")
    _require(tuple(arms["ELU-P"]["fitted"].keys()) == ELU_P_FITTED, "contract_elu_p_fitted_mismatch")
    # ruling 100-1 (ii): one set of fitted scalars per mask source, the fitted block being the main table's
    _require(arms["ELU-P"].get("fitted_mask_source") == ELU_P_FITTED_MAIN_MASK_SOURCE, "contract_elu_p_fitted_mask_source_mismatch")
    by_source = arms["ELU-P"].get("fitted_by_mask_source")
    _require(type(by_source) is dict
             and tuple(by_source) == tuple(source for source in ELU_P_FITTED_PATHS if source != ELU_P_FITTED_MAIN_MASK_SOURCE),
             "contract_elu_p_fitted_by_mask_source_mismatch")
    for source in ELU_P_FITTED_PATHS:
        elu_p_fitted(contract, source)
    _require(arms["ELU-P"].get("fitted_by_mask_source_rule") == ELU_P_FITTED_BY_MASK_SOURCE_RULE, "contract_elu_p_fitted_by_mask_source_rule_mismatch")
    _require(
        contract["ablations"]["HeuristicLabel"]["label_source_arm"] == HEURISTIC_LABEL_SOURCE,
        "contract_heuristic_label_source_mismatch",
    )
    _require(contract["ablations"]["HeuristicLabel"].get("label_rule") == HEURISTIC_LABEL_RULE, "contract_heuristic_label_rule_mismatch")
    # D-224-X ruling X4: the registered rollout configuration.
    rollout = arms[ROLLOUT_CONFIG_ARM]["rollout_config"]
    _require(tuple(rollout.keys()) == ROLLOUT_CONFIG_PARAMETERS, "contract_rollout_config_parameters_mismatch")
    _require(
        arms[METHOD_ARM]["training"]["dagger_round_0_memory_source"] == ROLLOUT_CONFIG_ARM
        and arms[METHOD_ARM]["training"]["dagger_round_0_memory_config"] == ROLLOUT_CONFIG_PATH,
        "contract_dagger_round_0_source_mismatch",
    )
    _require(
        contract["ablations"]["HeuristicLabel"]["label_source_config"] == ROLLOUT_CONFIG_PATH,
        "contract_heuristic_label_config_mismatch",
    )
    _require(
        tuple(arms[ROLLOUT_CONFIG_ARM]["fitting_procedure"]["quantities"].keys()) == ELU_P_FITTED,
        "contract_fitting_procedure_mismatch",
    )
    elu_grid = {name: spec.get("values") for name, spec in arms[ROLLOUT_CONFIG_ARM]["grid"].items()}
    if all(values is not None for values in elu_grid.values()) and all(
        rollout[name] is not None for name in ROLLOUT_CONFIG_PARAMETERS
    ):
        assert_rollout_config(rollout, elu_grid)
        _require({name: rollout[name] for name in ROLLOUT_CONFIG_PARAMETERS} == ROLLOUT_CONFIG, "contract_rollout_config_mismatch")  # ruling 68 (2)
    v2 = contract.get("user_rulings_v2")
    _require(type(v2) is dict and v2.get("decision_id") == V2_RULINGS_DECISION_ID, "contract_v2_rulings_decision_mismatch")
    _require(set(v2) >= set(V2_RULING_KEYS), "contract_v2_rulings_incomplete")
    _require(contract["user_rulings"]["decision_id"] == RULINGS_DECISION_ID, "contract_rulings_decision_mismatch")
    _require(set(contract["user_rulings"]) >= {"S", "T", "U", "V", "W"}, "contract_rulings_incomplete")

    for path, expected_value, _source in FROZEN_CONSTANTS:
        _require(_lookup(contract, path) == expected_value, f"contract_frozen_constant_mismatch:{path}")
    _require(
        tuple(contract.get("frozen_by_decision", ())) == tuple(path for path, _v, _s in FROZEN_CONSTANTS),
        "contract_frozen_constant_list_mismatch",
    )
    for path in NULL_POLICY_PATHS:
        _require(_lookup(contract, path) is None, f"contract_{path.replace('.', '_').replace('-', '_')}_must_be_null_before_freeze")
    _require(
        tuple(contract.get("policy_values_without_defaults", ())) == NULL_POLICY_PATHS,
        "contract_policy_value_list_mismatch",
    )
    for path, expected_value, _ruling in FROZEN_VALUES_BY_RULING:
        _require(_lookup(contract, path) == expected_value, f"contract_frozen_value_mismatch:{path}")
    # ruling 102-4: the selection rule and its constraint block
    budget = contract["budget"]
    _require(budget.get("selection_rule") == SELECTION_RULE, "contract_selection_rule_mismatch")
    constraint = budget.get("selection_constraint") or {}
    _require(tuple(constraint.get("arms") or ()) == SELECTION_CONSTRAINED_ARMS
             and constraint.get("reference_arm") == SELECTION_REFERENCE_ARM
             and constraint.get("metric") == SELECTION_CONSTRAINT_METRIC, "contract_selection_constraint_mismatch")
    return clone_json(dict(contract))


def select_configuration(validation: Mapping[int, Mapping[str, Any]], *, arm: str,
                         reference_missing_residual_rate: float | None) -> dict[str, Any]:
    """Ruling 102-4: the one configuration an arm takes to test, from its validation readings.

    Inputs: the arm's node F1 and Missing residual rate per validation configuration (learned arms: means over
    the five seeds) and the same front end's AssocOnly validation Missing residual rate.  The six arms with a
    retraction mechanism take the node-F1 maximum among the configurations whose residual rate is below
    AssocOnly's; when none qualifies (or the reference is undefined) they take the overall node-F1 maximum,
    recorded as not satisfiable -- its numbers are computed as usual but cannot support a claim that the arm's
    retraction reduces stale entities.  TAF, LOW and AssocOnly select by node F1 only.  Ties go to the smallest
    configuration index.  Reads no test data.
    """

    _require(type(validation) is dict and bool(validation), "selection_needs_validation_readings")
    for index, reading in validation.items():
        _require(type(index) is int and index >= 0, "selection_config_index_invalid")
        _require(reading.get(SELECTION_METRIC) is not None, f"selection_node_f1_missing:{index}")

    def best(indices: Sequence[int]) -> int:
        return sorted(indices, key=lambda i: (-float(validation[i][SELECTION_METRIC]), i))[0]

    everything = sorted(validation)
    out: dict[str, Any] = {"arm": arm, "rule": SELECTION_RULE, "constrained": arm in SELECTION_CONSTRAINED_ARMS,
                           "reference_missing_residual_rate": reference_missing_residual_rate}
    if arm not in SELECTION_CONSTRAINED_ARMS:
        return {**out, "admissible": everything, "selected": best(everything), "constraint_satisfiable": None}
    if reference_missing_residual_rate is None:
        return {**out, "admissible": [], "selected": best(everything), "constraint_satisfiable": False,
                "reason": "reference_missing_residual_rate_undefined"}
    reference = float(reference_missing_residual_rate)
    admissible = [i for i in everything if validation[i].get(SELECTION_CONSTRAINT_METRIC) is not None
                  and float(validation[i][SELECTION_CONSTRAINT_METRIC]) < reference]
    if not admissible:
        return {**out, "admissible": [], "selected": best(everything), "constraint_satisfiable": False,
                "reason": "constraint_not_satisfiable"}
    return {**out, "admissible": admissible, "selected": best(admissible), "constraint_satisfiable": True}


__all__ = [
    "ABLATION_ARMS",
    "SHOULD_BE_VISIBLE_MIN_RATIO",
    "SEEDS",
    "WEIGHT_DECAY",
    "ROLLOUT_CONFIG",
    "FROZEN_GRIDS",
    "ALL_ARMS",
    "APPENDIX_ARM",
    "CONTRACT_SCHEMA_VERSION",
    "CONTROL_ARMS",
    "ELU_P_FITTED",
    "ELU_P_FITTED_BY_MASK_SOURCE_RULE",
    "ELU_P_FITTED_MAIN_MASK_SOURCE",
    "ELU_P_FITTED_PATHS",
    "elu_p_fitted",
    "EXPECTED_BOOLEAN_CLAIMS",
    "GATE_ARMS",
    "GRID_PARAMETERS",
    "HEURISTIC_LABEL_RULE",
    "HEURISTIC_LABEL_SOURCE",
    "INELIGIBLE_LOGIT",
    "LEARNED_ARMS",
    "LeanArmsError",
    "MAIN_TABLE_ARMS",
    "MAX_CONFIGS_PER_METHOD",
    "METHOD_ARM",
    "NO_GATE_PARAMETER",
    "NULL_POLICY_PATHS",
    "OPTIONAL_ARM",
    "REACTIVATES_RETRACTED",
    "RULINGS_DECISION_ID",
    "ROLLOUT_CONFIG_ARM",
    "ROLLOUT_CONFIG_GATE_PARAMETER",
    "ROLLOUT_CONFIG_PARAMETERS",
    "ROLLOUT_CONFIG_PATH",
    "SELECTION_METRIC",
    "SELECTION_CONSTRAINED_ARMS",
    "SELECTION_CONSTRAINT_METRIC",
    "SELECTION_REFERENCE_ARM",
    "SELECTION_RULE",
    "select_configuration",
    "RULE_ARMS",
    "SPLIT_ALLOWED",
    "VOCABULARY",
    "apply_no_version",
    "arms_without_atom",
    "assert_config_budget",
    "assert_no_gate_option",
    "assert_no_sentinel_chosen",
    "assert_rollout_config",
    "assert_split_allowed",
    "compile_program",
    "ctx_admission",
    "eligible_existence_rows",
    "elu_p_existence",
    "elu_p_observe_matches",
    "enumerate_configs",
    "feature_index",
    "gate_association_logits",
    "hand_cost_association_logits",
    "hand_cost_existence",
    "learned_existence",
    "low_association_logits",
    "never_retract",
    "rac_existence",
    "rac_observe_matches",
    "sentinel_pairs",
    "skip_existence",
    "validate_arms_contract",
]
