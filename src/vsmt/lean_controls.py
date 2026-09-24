"""D-224 / S2-02: the four controls' provenance, the ELU-P fitted quantities and the LLM-op interface.

The controls' mechanics -- how TAF, ELU-P, RAC and LOW fill the shared S0-03 cost matrix and decide
existence -- live in ``lean_arms`` (S0-05, reviewed) and are wired into every frame by ``lean_runner``
(S2-01).  What S2-02 adds is what the PLAN row asks for and nothing more:

1. **Provenance.**  Each control is a clean-room, mechanism-level adaptation of a published idea,
   written from the papers' descriptions in this project's own terms.  No upstream source, class
   layout, default threshold, prompt or test was copied, and no result of this project may be
   described as a reproduction of the cited systems.  ``CONTROL_PROVENANCE`` records, per arm, the
   idea borrowed, where this adaptation departs from it, and that it is not an official
   implementation; the contract's one-line ``source`` string is bound to it.
2. **ELU-P's three fitted quantities** (S0-05 v2 ``fitting_procedure``, D-224-X ruling X4): pure
   estimators over counts taken from the train split after its feature seals -- the prior that an
   object still stands in place after an unobserved gap (``initial_log_odds``), the per-tick hazard of
   being removed or moved (``persistence_log_decay_per_tick``) and the log-likelihood ratio of the
   association gate binding when the object is there versus when it is not (``match_gain``).  The
   counting over episodes needs the S0-04 teacher's identities and is orchestrated with the
   development run (S2-05); the estimators here refuse degenerate counts instead of clamping.
3. **The LLM-op interface** (appendix arm, validation only): the sealed feature tables rendered as
   text, the strict parser for the model's one-atom-per-row answer, and the translation of those
   choices into logits for the *same* cost matrix and solver every arm uses (a chosen pair costs 0,
   an unchosen recalled pair is the registered sentinel, BIRTH is 0 when chosen and -1 otherwise, so
   two fragments choosing one entity fall back to BIRTH for one of them by the solver's rule).  The
   split guard refuses anything but validation; the runner refuses the arm outright in S2; the
   prompt wording is registered as not part of this stage.

白话：S2-02 补三样东西。第一，四个对照各自借了哪篇论文的机制、改了什么、并明写"不是官方实现、没有
抄代码"，供论文如实引用；第二，ELU-P 三个只在 train 上估一次的量的算式（先验 log-odds、每帧被移走
的风险率换成的衰减、门内配上与配错的对数似然比），输入是计数，计数为零或全部命中这类退化情况直接
拒绝而不是硬钳；第三，附录臂 LLM-op 的接口：把封存的特征表渲染成文本、严格解析"每行选一个原子"的
回答、再把选择变成喂给同一个求解器的 logit，只允许 validation。它不训练、不读私有数据，也不真的调
用任何模型。
"""

from __future__ import annotations

import math
import re
from typing import Any, Callable, Mapping, Sequence

from cpmt.hashing import clone_json

from vsmt import lean_arms as arms
from vsmt import lean_assignment as la

STAGE_ID = "S2-02"
NOT_AN_OFFICIAL_IMPLEMENTATION = "mechanism-level clean-room adaptation written from the papers' descriptions; no upstream source, class layout, default threshold, prompt or test was copied"

#: Per control: the idea borrowed, how this adaptation departs from it, and the contract's own source line.
CONTROL_PROVENANCE: dict[str, dict[str, Any]] = {
    "TAF": {
        "contract_source": "ConceptGraphs-style threshold association and fusion; unofficial adapter",
        "inspired_by": ["ConceptGraphs (Gu et al., ICRA 2024)"],
        "source_urls": ["https://arxiv.org/abs/2309.16650"],
        "borrowed": "associate a new segment to an existing object when the descriptor similarity clears a threshold (optionally within a distance), then fuse by running the descriptor mean; otherwise create a new object",
        "departs": "the gate fills the shared rectangular cost matrix (graded cost = cosine inside the gate, the registered sentinel outside, BIRTH logit = theta_a) and one solve per frame decides all fragments jointly; no captions, language features or semantic nodes; never retracts, the shared dormancy rule and the shared dedup are this project's, not the source's",
        "not_an_official_implementation": True, "upstream_code_copied": False,
    },
    "ELU-P": {
        "contract_source": "Fusion++ existence log-odds with a Perpetua-style persistence decay; unofficial adapter",
        "inspired_by": ["Fusion++ (McCormac et al., 3DV 2018)", "Dengler et al. (ECMR 2021)", "POCD (Qian et al., RSS 2022)", "Perpetua-style persistence modelling (title-level; the exact reference is registered at writing time)"],
        "source_urls": ["https://arxiv.org/abs/1808.08378", "https://arxiv.org/abs/2011.06895", "https://www.roboticsproceedings.org/rss18/p013.html"],
        "borrowed": "a per-object existence log-odds that falls under negative evidence and rises on a match, with a persistence decay per tick",
        "departs": "negative evidence is the shared frontend's free-space coverage ratio of the entity box (not a per-voxel TSDF or rendered mask); the decay, the initial log-odds and the match gain are three scalars fitted once on the train split by the registered procedure and never grid-searched; association is the TAF gate; a retracted entity is REACTIVATED through the shared compile step when it matches again",
        "not_an_official_implementation": True, "upstream_code_copied": False,
    },
    "RAC": {
        "contract_source": "DSG-style render-and-compare; unofficial adapter",
        "inspired_by": ["the dynamic scene graph render-and-compare update behind the Dyn-THOR benchmark (title-level; the exact reference is registered at writing time)"],
        "source_urls": [],
        "borrowed": "compare what memory predicts should be seen against the current depth; consecutive negative comparisons remove the node; a removed node re-appearing is re-created, never revived",
        "departs": "rendering is replaced by the shared frontend's free-space test on the entity box (S0-05: rendering_is_the_shared_frontend_free_space_test), so RAC and ELU-P differ only in the decision rule; association is the TAF gate; no Gaussian or mesh rendering, no semantic labels",
        "not_an_official_implementation": True, "upstream_code_copied": False,
    },
    "LOW": {
        "contract_source": "last-observation-wins overwrite; deliberately weak control",
        "inspired_by": [],
        "source_urls": [],
        "borrowed": "nothing: the nearest remembered entity within a distance takes the fragment, otherwise a new entity; never retracts",
        "departs": "not an adaptation of any published system; it bounds what pure overwrite achieves under the same frontend",
        "not_an_official_implementation": True, "upstream_code_copied": False,
    },
    arms.APPENDIX_ARM: {
        "contract_source": "the same sealed feature tables rendered as text; a frozen LLM chooses one atom per row",
        "inspired_by": ["Mem0-style zero-training memory operation selection (title-level; the exact reference is registered at writing time)"],
        "source_urls": [],
        "borrowed": "let a frozen language model choose the memory operation per item from a textual rendering of the candidates",
        "departs": "the rendering is the sealed S0-03 feature table (no captions, no images); the model's per-row choice is turned into logits for the shared cost matrix and solver rather than executed directly; validation only, appendix only, no configuration budget",
        "not_an_official_implementation": True, "upstream_code_copied": False,
    },
}

#: The ELU-P quantities and the count record each one is estimated from.
ELU_P_COUNT_FIELDS: dict[str, tuple[str, ...]] = {
    "initial_log_odds": ("in_place_object_frames", "object_frames"),
    "persistence_log_decay_per_tick": ("intervention_events", "object_ticks"),
    "match_gain": ("hit_frames", "hit_total", "false_frames", "false_total"),
}
ELU_P_DEFINITIONS: dict[str, str] = {
    "initial_log_odds": "logit of the train-split prior that an object still stands within delta_moved_m of its last-observed centroid at the first frame after an unobserved gap in which its place should be visible again: in_place_object_frames / object_frames",
    "persistence_log_decay_per_tick": "-log(1 - h), h = intervention_events / object_ticks over train-split objects observable at least once",
    "match_gain": "log(p_hit / p_false): p_hit = hit_frames / hit_total (should-be-visible frames of a present in-place object in which the ELU-P gate at the rollout_config binds some fragment to its carrier entity), p_false = false_frames / false_total (the same over frames in which the object is absent or moved and its old place should be visible)",
}

#: LLM-op text interface.
LLM_OP_ARM = arms.APPENDIX_ARM
TEXT_DECIMALS = 4
BIRTH_WORD = "BIRTH"
ANSWER_LINE = re.compile(r"^\s*(\S+)\s*->\s*(\S+)\s*$")
PROMPT_STATUS = "not_in_this_stage"  # S0-05 appendix_arm.prompt: the instruction wording is registered later


class LeanControlsError(ValueError):
    """Raised with a short machine-readable code."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LeanControlsError(code)


def _count(value: Any, code: str) -> int:
    _require(type(value) is int and type(value) is not bool and value >= 0, code)
    return value


# --------------------------------------------------------------------------
# 1. provenance
# --------------------------------------------------------------------------

def provenance(arm: str) -> dict[str, Any]:
    _require(arm in CONTROL_PROVENANCE, f"arm_without_provenance:{arm}")
    return clone_json(CONTROL_PROVENANCE[arm])


def assert_provenance_matches_contract(contract: Mapping[str, Any]) -> dict[str, str]:
    """Every rule control's contract ``source`` line and the appendix arm's ``input`` line must be the registered ones."""

    out = {}
    for arm in arms.CONTROL_ARMS:
        line = contract["arms"][arm]["source"]
        _require(line == CONTROL_PROVENANCE[arm]["contract_source"], f"provenance_source_differs:{arm}")
        out[arm] = line
    line = contract["appendix_arm"]["input"]
    _require(line == CONTROL_PROVENANCE[LLM_OP_ARM]["contract_source"], f"provenance_source_differs:{LLM_OP_ARM}")
    out[LLM_OP_ARM] = line
    for arm, record in CONTROL_PROVENANCE.items():
        _require(record["not_an_official_implementation"] is True and record["upstream_code_copied"] is False,
                 f"provenance_claim_weakened:{arm}")
    return out


# --------------------------------------------------------------------------
# 2. ELU-P fitted quantities (estimators over train-split counts)
# --------------------------------------------------------------------------

def fit_initial_log_odds(*, in_place_object_frames: int, object_frames: int) -> dict[str, Any]:
    """logit(p), p = in-place object-frames / object-frames; a prior of exactly 0 or 1 is refused, not clamped."""

    hits = _count(in_place_object_frames, "count_invalid:in_place_object_frames")
    total = _count(object_frames, "count_invalid:object_frames")
    _require(total > 0, "fit_degenerate:no_object_frames")
    _require(0 < hits < total, "fit_degenerate:prior_is_zero_or_one")
    p = hits / total
    return {"value": math.log(p / (1.0 - p)), "prior": p, "in_place_object_frames": hits, "object_frames": total}


def fit_persistence_log_decay(*, intervention_events: int, object_ticks: int) -> dict[str, Any]:
    """-log(1 - h), h = events / object-ticks; h must be below one."""

    events = _count(intervention_events, "count_invalid:intervention_events")
    ticks = _count(object_ticks, "count_invalid:object_ticks")
    _require(ticks > 0, "fit_degenerate:no_object_ticks")
    hazard = events / ticks
    _require(hazard < 1.0, "fit_degenerate:hazard_at_or_above_one")
    return {"value": -math.log(1.0 - hazard), "hazard_per_tick": hazard, "intervention_events": events, "object_ticks": ticks}


def fit_match_gain(*, hit_frames: int, hit_total: int, false_frames: int, false_total: int) -> dict[str, Any]:
    """log(p_hit / p_false); both rates must be strictly between 0 and 1 so the ratio is finite and informative."""

    hits = _count(hit_frames, "count_invalid:hit_frames")
    hit_n = _count(hit_total, "count_invalid:hit_total")
    false = _count(false_frames, "count_invalid:false_frames")
    false_n = _count(false_total, "count_invalid:false_total")
    _require(hit_n > 0 and false_n > 0, "fit_degenerate:no_frames")
    _require(0 < hits <= hit_n and 0 < false <= false_n, "fit_degenerate:rate_is_zero")
    p_hit, p_false = hits / hit_n, false / false_n
    return {"value": math.log(p_hit / p_false), "p_hit": p_hit, "p_false": p_false,
            "hit_frames": hits, "hit_total": hit_n, "false_frames": false, "false_total": false_n}


def fit_elu_p_quantities(counts: Mapping[str, Mapping[str, int]], *, split: str, seals_written: bool,
                         rollout_config: Mapping[str, Any]) -> dict[str, Any]:
    """The three quantities from their count records; train split only, after the feature seals, at the registered rollout_config."""

    _require(split == "train", f"elu_p_fit_split_not_train:{split}")
    _require(seals_written is True, "elu_p_fit_before_feature_seals")
    _require(tuple(rollout_config) == arms.ROLLOUT_CONFIG_PARAMETERS, "rollout_config_parameters_mismatch")
    for name in arms.ROLLOUT_CONFIG_PARAMETERS:
        _require(rollout_config[name] is not None, f"rollout_config_value_not_frozen:{name}")
    _require(set(counts) == set(ELU_P_COUNT_FIELDS), "elu_p_counts_fields_invalid")
    for name, fields in ELU_P_COUNT_FIELDS.items():
        _require(set(counts[name]) == set(fields), f"elu_p_counts_fields_invalid:{name}")
    fitted = {
        "initial_log_odds": fit_initial_log_odds(**counts["initial_log_odds"]),
        "persistence_log_decay_per_tick": fit_persistence_log_decay(**counts["persistence_log_decay_per_tick"]),
        "match_gain": fit_match_gain(**counts["match_gain"]),
    }
    return {
        "values": {name: fitted[name]["value"] for name in arms.ELU_P_FITTED},
        "evidence": fitted,
        "definitions": dict(ELU_P_DEFINITIONS),
        "split": split, "fitted_after_feature_seals": True, "rollout_config": dict(rollout_config),
        "shared_by_every_elu_p_configuration": True,
    }


# --------------------------------------------------------------------------
# 3. the LLM-op interface
# --------------------------------------------------------------------------

def _fmt(value: float) -> str:
    return f"{float(value):.{TEXT_DECIMALS}f}"


def render_frame_text(stage_a: Mapping[str, Any], eligible_rows: Sequence[Mapping[str, Any]], *, existence_feature_order: Sequence[str]) -> str:
    """The sealed tables as deterministic text: one block per fragment with its recalled candidates and its BIRTH option, one line per existence candidate.

    白话：把封存 A 的每个色块及其召回候选的 14 个特征、新建选项的 4 个特征，以及阶段 B 可判定实体的
    12 个特征，按冻结顺序、固定小数位写成文本。文本里只有匿名的色块 ID、实体 ID 和公开特征值。
    """

    assoc_order = list(stage_a["association_feature_order"])
    birth_order = list(stage_a["birth_feature_order"])
    exist_order = list(existence_feature_order)
    _require(tuple(assoc_order) == la.ASSOCIATION_FEATURES and tuple(birth_order) == la.BIRTH_FEATURES
             and tuple(exist_order) == la.EXISTENCE_FEATURES, "feature_orders_drifted")
    by_fragment: dict[str, list[Mapping[str, Any]]] = {}
    for row in stage_a["association_rows"]:
        by_fragment.setdefault(str(row["fragment_id"]), []).append(row)
    births = {str(row["fragment_id"]): row for row in stage_a["birth_rows"]}
    lines = [f"FRAME {stage_a['frame_digest'][:12]} TICK {int(stage_a['tick'])}"]
    for fragment_id in stage_a["rows"]:
        lines.append(f"FRAGMENT {fragment_id}")
        for row in by_fragment.get(str(fragment_id), []):
            values = ", ".join(f"{n}={_fmt(v)}" for n, v in zip(assoc_order, row["features"]))
            lines.append(f"  candidate {row['entity_id']}: {values}")
        values = ", ".join(f"{n}={_fmt(v)}" for n, v in zip(birth_order, births[str(fragment_id)]["features"]))
        lines.append(f"  option {BIRTH_WORD}: {values}")
    for row in eligible_rows:
        values = ", ".join(f"{n}={_fmt(v)}" for n, v in zip(exist_order, row["features"]))
        lines.append(f"EXISTENCE {row['entity_id']}: {values}")
    lines.append(f"ANSWER one line per FRAGMENT '<fragment_id> -> <candidate entity_id or {BIRTH_WORD}>' and one line per EXISTENCE '<entity_id> -> RETRACT or NOOP'.")
    return "\n".join(lines) + "\n"


def parse_llm_response(text: str, stage_a: Mapping[str, Any], eligible_ids: Sequence[str]) -> dict[str, Any]:
    """Strict parse: every fragment and every existence candidate exactly once, choices within the rendered options."""

    recall = {str(k): [str(v) for v in vs] for k, vs in stage_a["recall"].items()}
    fragments = [str(f) for f in stage_a["rows"]]
    entities = [str(e) for e in eligible_ids]
    _require(len(set(fragments)) == len(fragments) and len(set(entities)) == len(entities), "llm_op_rows_duplicated")
    _require(not (set(fragments) & set(entities)), "llm_op_rows_collide")
    fragment_choices: dict[str, str] = {}
    existence_choices: dict[str, str] = {}
    for raw in str(text).splitlines():
        if not raw.strip():
            continue
        match = ANSWER_LINE.match(raw)
        _require(match is not None, f"llm_op_response_malformed:line:{raw.strip()[:60]}")
        key, choice = match.group(1), match.group(2)
        if key in recall:
            _require(key not in fragment_choices, f"llm_op_response_malformed:duplicate_fragment:{key}")
            _require(choice == BIRTH_WORD or choice in recall[key], f"llm_op_response_malformed:choice_not_offered:{key}")
            fragment_choices[key] = choice
        elif key in entities:
            _require(key not in existence_choices, f"llm_op_response_malformed:duplicate_entity:{key}")
            _require(choice in ("RETRACT", "NOOP"), f"llm_op_response_malformed:decision_not_retract_or_noop:{key}")
            existence_choices[key] = choice
        else:
            raise LeanControlsError(f"llm_op_response_malformed:unknown_row:{key}")
    _require(set(fragment_choices) == set(fragments), "llm_op_response_malformed:fragment_rows_incomplete")
    _require(set(existence_choices) == set(entities), "llm_op_response_malformed:existence_rows_incomplete")
    return {"fragment_choices": fragment_choices, "existence_choices": existence_choices}


def choices_to_logits(fragment_choices: Mapping[str, str], stage_a: Mapping[str, Any]) -> dict[str, Any]:
    """Turn per-fragment choices into logits for the shared cost matrix: chosen pair 0, other recalled pairs the sentinel, BIRTH 0 if chosen else -1."""

    association: dict[str, float] = {}
    birth: dict[str, float] = {}
    for row in stage_a["association_rows"]:
        key = f"{row['fragment_id']}|{row['entity_id']}"
        chosen = fragment_choices.get(str(row["fragment_id"]))
        association[key] = 0.0 if chosen == str(row["entity_id"]) else arms.INELIGIBLE_LOGIT
    for fragment_id in stage_a["rows"]:
        _require(str(fragment_id) in fragment_choices, f"llm_op_choice_missing:{fragment_id}")
        birth[str(fragment_id)] = 0.0 if fragment_choices[str(fragment_id)] == BIRTH_WORD else -1.0
    return {"association_logits": association, "birth_logits": birth}


def llm_op_frame(stage_a: Mapping[str, Any], eligible_rows: Sequence[Mapping[str, Any]], *, existence_feature_order: Sequence[str],
                 llm: Callable[[str], str], split: str) -> dict[str, Any]:
    """Validation-only entry: render, ask, parse, and return logits plus existence decisions for the shared solver and compile step."""

    arms.assert_split_allowed(LLM_OP_ARM, split)
    prompt = render_frame_text(stage_a, eligible_rows, existence_feature_order=existence_feature_order)
    response = llm(prompt)
    _require(type(response) is str, "llm_op_response_not_text")
    choices = parse_llm_response(response, stage_a, [str(row["entity_id"]) for row in eligible_rows])
    return {
        "arm": LLM_OP_ARM, "split": split, "prompt_status": PROMPT_STATUS,
        "prompt_text": prompt, "response_text": response,
        "logits": choices_to_logits(choices["fragment_choices"], stage_a),
        "decisions": dict(choices["existence_choices"]),
        "fragment_choices": dict(choices["fragment_choices"]),
    }


__all__ = [
    "ANSWER_LINE",
    "BIRTH_WORD",
    "CONTROL_PROVENANCE",
    "ELU_P_COUNT_FIELDS",
    "ELU_P_DEFINITIONS",
    "LLM_OP_ARM",
    "LeanControlsError",
    "NOT_AN_OFFICIAL_IMPLEMENTATION",
    "PROMPT_STATUS",
    "STAGE_ID",
    "TEXT_DECIMALS",
    "assert_provenance_matches_contract",
    "choices_to_logits",
    "fit_elu_p_quantities",
    "fit_initial_log_odds",
    "fit_match_gain",
    "fit_persistence_log_decay",
    "llm_op_frame",
    "parse_llm_response",
    "provenance",
    "render_frame_text",
]
