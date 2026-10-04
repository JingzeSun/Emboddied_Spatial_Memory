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
3. **The LLM-op interface** (appendix arm; two calls per frame since ruling 105, 2026-10-04): the
   existence features exist only after the solve, so a frame asks twice.  The association call renders
   the sealed stage-A rows as two CSV tables with one header row each (every recalled pair with its 14
   features, every fragment's 4 BIRTH features; the frozen order, 4 decimals, anonymous ids) under the
   registered ``ASSOCIATION_INSTRUCTION`` and wants one line per fragment, a recalled candidate or
   BIRTH; the existence call renders the eligible stage-B rows as one table under
   ``EXISTENCE_INSTRUCTION`` and wants RETRACT or NOOP per entity.  The strict parsers accept exactly
   one offered choice per row (blank and code-fence lines aside, nothing else); the choices become
   logits for the *same* cost matrix and solver every arm uses (a chosen pair costs 0, an unchosen
   recalled pair is the registered sentinel, BIRTH is 0 when chosen and -1 otherwise, so two fragments
   choosing one entity fall back to BIRTH for one of them by the solver's rule); the fallbacks (every
   fragment BIRTH, every entity NOOP) are what ruling 105-6 applies after three invalid answers.
   Asking the model, the attempts, the call archive and the split guard live in ``lean_llm_op``.

白话：S2-02 补三样东西。第一，四个对照各自借了哪篇论文的机制、改了什么、并明写"不是官方实现、没有
抄代码"，供论文如实引用；第二，ELU-P 三个只在 train 上估一次的量的算式（先验 log-odds、每帧被移走
的风险率换成的衰减、门内配上与配错的对数似然比），输入是计数，计数为零或全部命中这类退化情况直接
拒绝而不是硬钳；第三，附录臂 LLM-op 的接口（裁决 105 起每帧问两次）：存在特征要等关联求解后才有，
所以先把封存 A 渲染成两张带表头的表（召回对的 14 个特征、每个色块新建选项的 4 个特征）连同登记的
关联指令发出去，要每个色块一行"选哪个候选或 BIRTH"；求解后再把可判定实体渲染成一张表，要每个实体
一行 RETRACT 或 NOOP。解析器严格：每行恰好一个给出过的选项，只容忍空行和代码围栏行；选择变成喂给
同一个求解器的 logit；三次无效回答后的回退是色块全 BIRTH、实体全 NOOP。这里不训练、不读私有数据，
也不真的调用模型——调用、重问、存档和 split 守卫在 ``lean_llm_op``。
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any, Mapping, Sequence

from cpmt.hashing import canonical_json, clone_json

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
EXISTENCE_WORDS = ("RETRACT", "NOOP")
ANSWER_LINE = re.compile(r"^\s*(\S+)\s*->\s*(\S+)\s*$")
#: Ruling 105-6: a line holding only a Markdown code fence carries no answer and is skipped; nothing else is.
CODE_FENCE_LINE = re.compile(r"^\s*```[A-Za-z]*\s*$")
CALL_KINDS = ("association", "existence")
#: Ruling 105-4: how the sealed rows become text.
RENDERING_RULE = (
    "csv tables with one header row each: CANDIDATES (fragment, candidate, the 14 association features) and NEW (fragment, "
    "the 4 birth features) for the association call, ENTITIES (entity, the 17 existence features) for the existence call; "
    "rows in sealed order, every feature in the frozen order, 4 decimals, anonymous ids only"
)


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
    """log(p_hit / p_false); both rates must be positive and p_hit must exceed p_false.

    A zero rate makes the ratio infinite; p_hit <= p_false means the gate binds no more often when
    the object is there than when it is not, so a match carries no positive evidence and ELU-P's
    ``elu_p_observe_matches`` would refuse the gain anyway.  Both are refused here as degenerate
    counts instead of surfacing at the first S2-05 frame (D-224-S1 ruling 62, 2026-09-24).
    """

    hits = _count(hit_frames, "count_invalid:hit_frames")
    hit_n = _count(hit_total, "count_invalid:hit_total")
    false = _count(false_frames, "count_invalid:false_frames")
    false_n = _count(false_total, "count_invalid:false_total")
    _require(hit_n > 0 and false_n > 0, "fit_degenerate:no_frames")
    _require(0 < hits <= hit_n and 0 < false <= false_n, "fit_degenerate:rate_is_zero")
    p_hit, p_false = hits / hit_n, false / false_n
    _require(p_hit > p_false, "fit_degenerate:gain_not_positive")
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

#: Ruling 105-5: the two registered instructions (zero-training: the task, what every column means, a made-up format example;
#: no threshold, no statistic and no example from any split).  They are sent as the system message of each call; their
#: digest is bound in the LLM-op contract, so a changed word is a contract change.
ASSOCIATION_INSTRUCTION = """\
You keep an object memory for a robot that walks through a house with an RGB-D camera. The memory holds entities: objects \
the robot has seen before, each with an appearance descriptor, a 3D position and box, and a lifecycle state (active, \
dormant or retracted). In every camera frame a segmenter cuts out fragments: image regions that each show one object. \
This call decides, for every fragment of the current frame, which remembered entity it shows, or that it shows an object \
that is not in the memory.

You receive two tables.

CANDIDATES has one row per (fragment, recalled entity) pair. A fragment recalls at most 8 entities in any state: up to 5 \
entities within 3 m of it ranked by appearance similarity, plus the 3 most similar entities anywhere in the memory. Columns:
- fragment, candidate: anonymous ids.
- cosine_to_descriptor_mean: cosine similarity between the fragment's appearance descriptor and the entity's mean \
descriptor (from -1 to 1; higher means more alike).
- cosine_to_best_view_descriptor: cosine similarity between the fragment's descriptor and the descriptor of the entity's stored \
view with the largest mask.
- centroid_distance_m: distance in metres between the fragment's 3D centroid and the entity's last known centroid.
- aabb_iou: overlap (intersection over union, 0 to 1) of the fragment's and the entity's axis-aligned 3D boxes.
- log_size_ratio: natural log of the fragment's box volume over the entity's box volume (0 means the same size).
- ticks_since_last_seen: frames since the entity was last observed (created or matched to a fragment).
- missed_opportunity_count: since the entity was last matched, how many times it should have been visible, was not matched \
and was kept (reset by any match).
- state_is_active, state_is_dormant, state_is_retracted: the entity's state; exactly one is 1. Dormant means missed several \
times in a row and set aside; retracted means judged earlier to be no longer at its place. Both can be matched again.
- cosine_rank_within_recall: the entity's rank by cosine_to_descriptor_mean among the fragment's candidates (0 is the most \
similar).
- cosine_margin_to_runner_up: for the top-ranked candidate, its cosine minus the second-best cosine (its cosine plus 1 when \
it is the only candidate); for every other candidate, its cosine minus the top cosine.
- mutual_best: 1 if the entity is the fragment's most similar candidate and, among this frame's fragments that recalled the \
entity, the fragment is the most similar to it, else 0.
- support_height_difference_m: absolute difference in metres between the bottom heights of the two boxes.

NEW has one row per fragment and describes the option of creating a new entity for it. Columns:
- fragment: anonymous id.
- best_cosine_to_any_entity: the highest cosine between the fragment and any remembered entity (-1 when the memory is empty).
- active_entities_within_radius: the number of active entities whose centroid lies within 1 m of the fragment's centroid.
- pixel_count: the fragment's area in pixels.
- depth_valid_ratio: the share of the fragment's pixels with a valid depth reading.

For every fragment choose exactly one option:
- the id of one of its candidates, if the fragment shows that entity (choosing a dormant or retracted entity brings it back);
- BIRTH, if the fragment shows an object that is none of its candidates.
An entity can be matched to at most one fragment per frame; if two fragments choose the same entity, one of them becomes BIRTH.

Answer with one line per fragment and nothing else, in the form
<fragment> -> <candidate id or BIRTH>
For example (made-up ids):
f12 -> e7
f13 -> BIRTH
"""

EXISTENCE_INSTRUCTION = """\
You keep an object memory for a robot that walks through a house with an RGB-D camera. The memory holds entities: objects \
the robot has seen before, each with a 3D position and box and a lifecycle state. The fragments of the current camera frame \
have already been matched to entities. This call is about the active or dormant entities that should be visible in the \
current view but were not matched in this frame: for each of them, decide whether the object is still at its remembered place.

You receive one table, ENTITIES, with one row per entity. Columns:
- entity: anonymous id.
- should_be_visible_ratio: of the points on the entity's last observed surface, the share that project into the current \
depth image onto a valid depth reading and are not hidden behind a nearer surface.
- free_space_coverage_ratio: of those visible points, the share where the measured depth lies more than 5 cm beyond the \
point, i.e. the camera sees through the place where the surface should be (0 when no point is visible).
- camera_distance_m: distance in metres from the camera to the entity's centroid.
- camera_view_cosine: cosine between the camera's viewing direction and the direction from the camera to the entity's \
centroid (1 means straight ahead).
- missed_opportunity_count: since the entity was last matched, how many earlier times it was listed in this table and kept \
(reset by any match).
- observation_count: how many times the entity has been observed (created or matched).
- ticks_since_last_seen: frames since the entity was last observed (created or matched).
- best_fragment_cosine: the highest appearance cosine between the entity and any fragment of the current frame (-1 when the \
frame has no fragment).
- best_fragment_still_unassigned: 1 if that most similar fragment was matched to no remembered entity in this frame (it \
becomes a new entity), else 0.
- state_is_active, state_is_dormant, state_is_retracted: the entity's state; exactly one is 1 (retracted never occurs here).
- rac_run_rho_070, rac_run_rho_085: how many of the entity's most recent earlier listings in this table, in a row, had a \
free_space_coverage_ratio of at least 0.70 (respectively 0.85); a listing below that value or any match resets it, and a frame \
in which the entity is not listed changes nothing.
- matches_since_birth: how many times the entity has been matched since it was created.
- eligible_frames_since_birth: earlier frames, since the entity was created, in which it was listed in this table.
- free_space_coverage_sum_since_birth: the sum of free_space_coverage_ratio over those frames.

For every entity choose exactly one decision:
- NOOP: keep the entity (for example the object is hidden, or was simply not segmented this time). Its missed count grows; \
after several misses in a row it becomes dormant, which still keeps it.
- RETRACT: the object is no longer at its remembered place (removed or moved). The entity is closed but kept in the \
history, and a later fragment can bring it back.

Answer with one line per entity and nothing else, in the form
<entity> -> <NOOP or RETRACT>
For example (made-up ids):
e7 -> NOOP
e9 -> RETRACT
"""

INSTRUCTIONS: dict[str, str] = {"association": ASSOCIATION_INSTRUCTION, "existence": EXISTENCE_INSTRUCTION}
INSTRUCTION_SHA256 = hashlib.sha256(canonical_json(INSTRUCTIONS).encode("utf-8")).hexdigest()


def _fmt(value: float) -> str:
    return f"{float(value):.{TEXT_DECIMALS}f}"


def _cell_id(value: Any) -> str:
    """An id as one table cell and one answer token: no whitespace, comma or arrow, or the table and the answer turn ambiguous."""

    text = str(value)
    _require(bool(text) and not any(ch.isspace() or ch == "," for ch in text) and "->" not in text,
             f"llm_op_id_not_renderable:{text[:40]}")
    return text


def _table(title: str, header: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    return [title, ",".join(header), *(",".join(row) for row in rows)]


def render_association_tables(stage_a: Mapping[str, Any]) -> str:
    """Ruling 105-4: the sealed stage-A rows as two CSV tables -- every recalled pair, then every fragment's BIRTH option.

    白话：输入封存 A，输出发给关联调用的表格文本。CANDIDATES 每行一个（色块，召回实体）对和它的 14 个特征，
    NEW 每行一个色块新建选项的 4 个特征；行序按封存顺序，特征按冻结顺序，统一 4 位小数，只有匿名 ID。
    例如三个色块各召回两个实体，就是 6 行候选加 3 行新建。它不挑行、不排序、不加任何真值。
    """

    assoc_order = list(stage_a["association_feature_order"])
    birth_order = list(stage_a["birth_feature_order"])
    _require(tuple(assoc_order) == la.ASSOCIATION_FEATURES and tuple(birth_order) == la.BIRTH_FEATURES, "feature_orders_drifted")
    fragments = [_cell_id(fragment_id) for fragment_id in stage_a["rows"]]
    _require(len(set(fragments)) == len(fragments), "llm_op_rows_duplicated")
    by_fragment: dict[str, list[Mapping[str, Any]]] = {}
    for row in stage_a["association_rows"]:
        by_fragment.setdefault(str(row["fragment_id"]), []).append(row)
    _require(set(by_fragment) <= set(fragments), "association_rows_name_an_unknown_fragment")
    births = {str(row["fragment_id"]): row for row in stage_a["birth_rows"]}
    _require(set(births) == set(fragments), "birth_rows_do_not_match_the_fragments")
    candidates: list[list[str]] = []
    for fragment_id in fragments:
        for row in by_fragment.get(fragment_id, []):
            _require(len(row["features"]) == len(assoc_order), "association_feature_arity")
            candidates.append([fragment_id, _cell_id(row["entity_id"]), *(_fmt(value) for value in row["features"])])
    news: list[list[str]] = []
    for fragment_id in fragments:
        features = births[fragment_id]["features"]
        _require(len(features) == len(birth_order), "birth_feature_arity")
        news.append([fragment_id, *(_fmt(value) for value in features)])
    lines = _table("CANDIDATES", ["fragment", "candidate", *assoc_order], candidates)
    lines += ["", *_table("NEW", ["fragment", *birth_order], news)]
    return "\n".join(lines) + "\n"


def render_existence_table(eligible_rows: Sequence[Mapping[str, Any]], existence_feature_order: Sequence[str]) -> str:
    """Ruling 105-4: the eligible stage-B rows as one CSV table (entity, the 17 existence features)."""

    order = list(existence_feature_order)
    _require(tuple(order) == la.EXISTENCE_FEATURES, "feature_orders_drifted")
    rows: list[list[str]] = []
    for row in eligible_rows:
        _require(len(row["features"]) == len(order), "existence_feature_arity")
        rows.append([_cell_id(row["entity_id"]), *(_fmt(value) for value in row["features"])])
    _require(len({row[0] for row in rows}) == len(rows), "llm_op_rows_duplicated")
    return "\n".join(_table("ENTITIES", ["entity", *order], rows)) + "\n"


def association_messages(stage_a: Mapping[str, Any]) -> list[dict[str, str]]:
    """The association call's two messages: the registered instruction and this frame's tables."""

    return [{"role": "system", "content": ASSOCIATION_INSTRUCTION}, {"role": "user", "content": render_association_tables(stage_a)}]


def existence_messages(eligible_rows: Sequence[Mapping[str, Any]], existence_feature_order: Sequence[str]) -> list[dict[str, str]]:
    """The existence call's two messages: the registered instruction and this frame's table."""

    return [{"role": "system", "content": EXISTENCE_INSTRUCTION},
            {"role": "user", "content": render_existence_table(eligible_rows, existence_feature_order)}]


def _answer_pairs(text: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for raw in str(text).splitlines():
        if not raw.strip() or CODE_FENCE_LINE.match(raw):
            continue
        match = ANSWER_LINE.match(raw)
        _require(match is not None, f"llm_op_answer_malformed:line:{raw.strip()[:60]}")
        pairs.append((match.group(1), match.group(2)))
    return pairs


def parse_association_answer(text: str, stage_a: Mapping[str, Any]) -> dict[str, str]:
    """Strict: one line per fragment, each choice BIRTH or one of that fragment's recalled candidates."""

    recall = {str(key): {str(value) for value in values} for key, values in stage_a["recall"].items()}
    fragments = [str(fragment_id) for fragment_id in stage_a["rows"]]
    _require(set(recall) == set(fragments), "recall_does_not_match_the_fragments")
    choices: dict[str, str] = {}
    for key, choice in _answer_pairs(text):
        _require(key in recall, f"llm_op_answer_malformed:unknown_row:{key}")
        _require(key not in choices, f"llm_op_answer_malformed:duplicate_row:{key}")
        _require(choice == BIRTH_WORD or choice in recall[key], f"llm_op_answer_malformed:choice_not_offered:{key}")
        choices[key] = choice
    _require(set(choices) == set(fragments), "llm_op_answer_malformed:rows_incomplete")
    return choices


def parse_existence_answer(text: str, eligible_ids: Sequence[str]) -> dict[str, str]:
    """Strict: one line per eligible entity, each decision RETRACT or NOOP."""

    entities = [str(entity_id) for entity_id in eligible_ids]
    _require(len(set(entities)) == len(entities), "llm_op_rows_duplicated")
    allowed = set(entities)
    decisions: dict[str, str] = {}
    for key, choice in _answer_pairs(text):
        _require(key in allowed, f"llm_op_answer_malformed:unknown_row:{key}")
        _require(key not in decisions, f"llm_op_answer_malformed:duplicate_row:{key}")
        _require(choice in EXISTENCE_WORDS, f"llm_op_answer_malformed:decision_not_retract_or_noop:{key}")
        decisions[key] = choice
    _require(set(decisions) == allowed, "llm_op_answer_malformed:rows_incomplete")
    return decisions


def fallback_association(stage_a: Mapping[str, Any]) -> dict[str, str]:
    """Ruling 105-6: after three invalid answers every fragment of the frame becomes BIRTH."""

    return {str(fragment_id): BIRTH_WORD for fragment_id in stage_a["rows"]}


def fallback_existence(eligible_ids: Sequence[str]) -> dict[str, str]:
    """Ruling 105-6: after three invalid answers every eligible entity of the frame gets NOOP."""

    return {str(entity_id): "NOOP" for entity_id in eligible_ids}


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


__all__ = [
    "ANSWER_LINE",
    "ASSOCIATION_INSTRUCTION",
    "BIRTH_WORD",
    "CALL_KINDS",
    "CODE_FENCE_LINE",
    "CONTROL_PROVENANCE",
    "ELU_P_COUNT_FIELDS",
    "ELU_P_DEFINITIONS",
    "EXISTENCE_INSTRUCTION",
    "EXISTENCE_WORDS",
    "INSTRUCTIONS",
    "INSTRUCTION_SHA256",
    "LLM_OP_ARM",
    "LeanControlsError",
    "NOT_AN_OFFICIAL_IMPLEMENTATION",
    "RENDERING_RULE",
    "STAGE_ID",
    "TEXT_DECIMALS",
    "assert_provenance_matches_contract",
    "association_messages",
    "choices_to_logits",
    "existence_messages",
    "fallback_association",
    "fallback_existence",
    "fit_elu_p_quantities",
    "fit_initial_log_odds",
    "fit_match_gain",
    "fit_persistence_log_decay",
    "parse_association_answer",
    "parse_existence_answer",
    "provenance",
    "render_association_tables",
    "render_existence_table",
]
