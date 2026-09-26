"""D-224 / S0-01: the VSMT-lean entity memory core.

This module is the only place where entity records are created, versioned,
closed or reopened.  It is deliberately self-contained: the D-210..D-223
``GraphRevision`` path is bound to the place scaffold, five relation-edge
types, ``graph_hash`` and the unified-graph lifecycle, so narrowing it would
drag all of that back in.  Only pure helpers that would otherwise gain a
second numeric definition are reused (canonical JSON, deep clone, cosine,
centroid distance, AABB, opaque IDs).

白话：这个模块解决"实体档案怎样被合法地改并留底"。输入是一份旧记忆和本帧
的程序，输出是新记忆、逐实体版本链和本帧审计记录；任何一步非法则整帧回滚，
旧记忆逐字节不变。例如 REACTIVATE 一个未关闭的活动实体是非法的，整帧不生效。
它不做关联判断（那是分配层），不读 private/teacher/future，也不是旧统一图执行器。

Scope, restated so it cannot drift:

* Nodes are entities only.  No place, surface, fragment or relation nodes.
* Atoms are ``NOOP``, ``BIND``, ``BIRTH``, ``RETRACT``, ``REACTIVATE``.
  ``REPLACE`` is a composite of ``RETRACT`` + ``BIRTH`` and is not a sixth
  atom.  ``SPLIT`` and ``RELINK`` do not exist here.
* The executor checks *structural* preconditions only.  "Should have been
  visible" and "existence probability over threshold" are decision-layer
  conditions: the caller records them in ``decision_basis``, this module
  copies them into provenance and never re-derives them.
* Every numeric policy value (dormancy count, dedup thresholds) must be
  passed in explicitly.  There are no defaults, so an unfrozen value cannot
  silently become an experiment constant.
"""

from __future__ import annotations

import collections
import hashlib
import math
from typing import Any, Mapping, Sequence

from cpmt.hashing import canonical_json, clone_json

from vsmt.lean_geometry import centroid_distance, cosine_similarity, opaque_id


SCHEMA_VERSION = "vsmt-lean-entity-memory-v2"
CONTRACT_SCHEMA_VERSION = "vsmt-lean-s0-entity-memory-v2"

#: Why a version was opened (D-224-X ruling X6).  The value is what lets the
#: S0-04 size metric count lifecycle versions without the BIND-per-observation
#: versions, and what makes the chain readable in an audit.  Each value binds
#: the state the version must snapshot.
#: D-224-S1 ruling 76 (2)(a): ``dedup_dormant`` opens the survivor's version when both folded
#: records were dormant (the survivor stays dormant); ``dedup`` when either was active.
VERSION_OPENED_BY = ("birth", "bind", "reactivate", "retract", "dormant", "dedup", "dedup_dormant")
VERSION_OPENED_BY_STATE: dict[str, str] = {
    "birth": "active", "bind": "active", "reactivate": "active",
    "retract": "retracted", "dormant": "dormant", "dedup": "active", "dedup_dormant": "dormant",
}

#: The five atoms.  ``REPLACE`` is expanded before validation and is not here.
ATOMS = ("NOOP", "BIND", "BIRTH", "RETRACT", "REACTIVATE")
COMPOSITES = ("REPLACE",)

#: Atoms that attach a fragment to an entity (or create one from it).
FRAGMENT_ATOMS = frozenset({"BIND", "BIRTH", "REACTIVATE"})
#: Atoms that name an existing entity.
TARGET_ATOMS = frozenset({"NOOP", "BIND", "RETRACT", "REACTIVATE"})

ENTITY_STATES = ("active", "dormant", "retracted")

#: D-224-S1 ruling 67 (2026-09-24): the shared dormancy and dedup values, frozen once for every
#: arm.  The contract carries the same numbers; the validator refuses any other.  Callers still
#: pass them explicitly (no default slips in), the S2 entries read them from the contract.
#: D-224-S1 ruling 68 (2026-09-25, LOG-256 sequel): the dedup triple re-frozen from the 39-episode
#: calibration quantiles -- cosine 0.9 -> 0.8, centroid distance 0.25 -> 0.5 m, box IoU 0.3 -> 0.05
#: (the ruling-67 triple was almost never satisfiable: same-object box IoU has p50 0.012 and the
#: development runs kept 3.5 entities per truth object).  The period stays 10.
DORMANCY_MISSED_OPPORTUNITY_LIMIT = 3
#: D-224-S1 ruling 77 (2)(a) (2026-09-26, LOG-263 sequel): descriptor_cosine_min 0.8 -> 0.6.  On the four audit episodes
#: under ruling 76, 0.8 folded the same object in only 23 of 41 identified folds and left TAF with 27,869 entity-frames;
#: 0.6 folded the same object in 110 of 137 and cut them to 19,175 (TAF own-object-and-place F1 0.500 -> 0.638, LOW ~0.70).
SHARED_DEDUP = {"period_ticks": 10, "descriptor_cosine_min": 0.6, "centroid_distance_max_m": 0.5, "aabb_iou_min": 0.05}
#: D-224-S1 ruling 76 (2)(a) (2026-09-26, LOG-262): dormant records join the shared dedup, so the fold no
#: longer depends on each arm's existence decisions (AssocOnly never goes dormant and had kept every
#: record eligible while the other arms' abandoned duplicates escaped it).  The survivor takes the
#: geometry of the more recently observed record (same-tick records keep the union box and the
#: count-weighted centroid), and it is active when either record was.
DEDUP_RULE = "periodic_deterministic_merge_of_duplicate_active_or_dormant_entities"
DEDUP_ELIGIBLE_STATES = ("active", "dormant")
DEDUP_SURVIVOR_GEOMETRY = "latest_observed_record_centroid_and_box_same_tick_union_box_and_count_weighted_centroid"
DEDUP_SURVIVOR_STATE = "active_if_either_record_active_else_dormant"

#: state -> atoms that may legally target an entity in that state.
STATE_ALLOWED_ATOMS: dict[str, frozenset[str]] = {
    "active": frozenset({"NOOP", "BIND", "RETRACT"}),
    "dormant": frozenset({"NOOP", "RETRACT", "REACTIVATE"}),
    "retracted": frozenset({"REACTIVATE"}),
}

#: Frozen field order for the D-224-G entity token.  Downstream world-model
#: consumers may rely on this order; changing it is a contract change.
ENTITY_TOKEN_FIELDS = (
    "entity_id",
    "state_one_hot",
    "descriptor",
    "centroid_m",
    "extent_m",
    "observation_count",
    "age_ticks",
    "version_count",
    "missed_opportunity_count",
    "supported_by_present",
)

FRAGMENT_FIELDS = frozenset({
    "fragment_id", "descriptor", "centroid_m", "aabb_min_m", "aabb_max_m",
    "pixel_count", "supported_by",
})

#: Fields a version record snapshots when it is opened.  Descriptors are
#: deliberately excluded: the audit needs "where did memory think it was",
#: not "what did it look like", and a 384-d vector per version would make the
#: stored memory grow linearly with frame count.
#:
#: The snapshot is the entity *as of the moment that version opened* and is
#: deliberately never re-synced afterwards.  A ``NOOP`` bumps the live
#: ``missed_opportunity_count`` without opening a version, so the open
#: version's copy of that count can legitimately lag the entity.  Only
#: ``state`` is held equal to the live entity, because that is what makes the
#: version chain readable as a lifecycle.
VERSION_SNAPSHOT_FIELDS = (
    "state", "centroid_m", "aabb_min_m", "aabb_max_m",
    "observation_count", "missed_opportunity_count", "supported_by",
)


class LeanMemoryError(ValueError):
    """Raised for any illegal memory, program or policy value."""


# --------------------------------------------------------------------------
# small validators
# --------------------------------------------------------------------------

def _require(condition: bool, code: str) -> None:
    if not condition:
        raise LeanMemoryError(code)


def _finite(value: Any, code: str) -> float:
    _require(type(value) in {int, float}, code)
    result = float(value)
    _require(math.isfinite(result), code)
    return result


def _int(value: Any, code: str, *, minimum: int | None = None) -> int:
    _require(type(value) is int and type(value) is not bool, code)
    if minimum is not None:
        _require(value >= minimum, code)
    return value


def _identifier(value: Any, code: str) -> str:
    _require(type(value) is str and 1 <= len(value) <= 128, code)
    _require(all(char.isalnum() or char in "-_:." for char in value), code)
    return value


def _hex64(value: Any, code: str) -> str:
    _require(type(value) is str and len(value) == 64, code)
    _require(all(char in "0123456789abcdef" for char in value), code)
    return value


def _vector(value: Any, code: str, *, length: int | None = None) -> list[float]:
    _require(type(value) is list and value, code)
    if length is not None:
        _require(len(value) == length, code)
    return [_finite(item, code) for item in value]


def _threshold(value: Any, code: str, *, low: float, high: float) -> float:
    result = _finite(value, code)
    _require(low <= result <= high, code)
    return result


def _json_native(value: Any, code: str) -> None:
    if value is None or type(value) in {bool, int, float, str}:
        if type(value) is float:
            _require(math.isfinite(value), code)
        return
    if type(value) is list:
        for item in value:
            _json_native(item, code)
        return
    if type(value) is dict:
        for key, item in value.items():
            _require(type(key) is str, code)
            _json_native(item, code)
        return
    raise LeanMemoryError(code)


def memory_digest(memory: Mapping[str, Any]) -> str:
    """SHA-256 over the canonical memory payload, excluding the digest itself."""

    payload = {key: value for key, value in memory.items() if key != "memory_digest"}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def seal_memory(memory: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of ``memory`` carrying its own digest."""

    result = clone_json(dict(memory))
    result.pop("memory_digest", None)
    result["memory_digest"] = memory_digest(result)
    return result


# --------------------------------------------------------------------------
# memory construction and validation
# --------------------------------------------------------------------------

def empty_memory(*, episode_id: str) -> dict[str, Any]:
    """Return the sealed t=0 memory for one episode.

    白话：输入一个 episode 标识，输出一份没有任何实体的初始记忆；tick 从 0 开始，
    第一帧提交后为 1。它不代表任何观测，也不分配 entity_id。
    """

    memory = {
        "schema_version": SCHEMA_VERSION,
        "episode_id": _identifier(episode_id, "episode_id_invalid"),
        "tick": 0,
        "entities": [],
        "transaction_log": [],
    }
    return seal_memory(memory)


def _validate_version(version: Mapping[str, Any], *, entity_id: str) -> None:
    expected = {
        "version_id", "predecessor", "opened_at", "closed_at",
        "opening_transaction", "closing_transaction", "opened_by",
    } | set(VERSION_SNAPSHOT_FIELDS)
    _require(set(version.keys()) == expected, "version_fields_invalid")
    _identifier(version["version_id"], "version_id_invalid")
    _require(version["opened_by"] in VERSION_OPENED_BY, "version_opened_by_invalid")
    _require(
        version["state"] == VERSION_OPENED_BY_STATE[version["opened_by"]],
        "version_state_disagrees_with_opened_by",
    )
    if version["predecessor"] is not None:
        _identifier(version["predecessor"], "version_predecessor_invalid")
    opened = _int(version["opened_at"], "version_opened_at_invalid", minimum=0)
    if version["closed_at"] is not None:
        closed = _int(version["closed_at"], "version_closed_at_invalid", minimum=0)
        _require(closed >= opened, "version_closed_before_open")
        _identifier(version["closing_transaction"], "version_closing_transaction_invalid")
    else:
        _require(
            version["closing_transaction"] is None,
            "version_open_but_closing_transaction_present",
        )
    _identifier(version["opening_transaction"], "version_opening_transaction_invalid")
    _require(version["state"] in ENTITY_STATES, "version_state_invalid")
    _vector(version["centroid_m"], "version_centroid_invalid", length=3)
    _vector(version["aabb_min_m"], "version_aabb_min_invalid", length=3)
    _vector(version["aabb_max_m"], "version_aabb_max_invalid", length=3)
    _int(version["observation_count"], "version_observation_count_invalid", minimum=0)
    _int(
        version["missed_opportunity_count"],
        "version_missed_count_invalid",
        minimum=0,
    )
    if version["supported_by"] is not None:
        _identifier(version["supported_by"], "version_supported_by_invalid")
    del entity_id  # only used for error context by callers


def _validate_entity(entity: Mapping[str, Any], *, tick: int) -> None:
    expected = {
        "entity_id", "state", "canonical_of", "descriptor_mean",
        "descriptor_count", "best_view_descriptor", "best_view_pixel_count",
        "centroid_m", "aabb_min_m", "aabb_max_m", "observation_count",
        "last_seen_tick", "missed_opportunity_count", "supported_by",
        "evidence", "versions",
    }
    _require(set(entity.keys()) == expected, "entity_fields_invalid")
    entity_id = _identifier(entity["entity_id"], "entity_id_invalid")
    _require(entity["state"] in ENTITY_STATES, "entity_state_invalid")

    _require(type(entity["canonical_of"]) is list, "entity_canonical_of_invalid")
    folded = [
        _identifier(item, "entity_canonical_of_invalid")
        for item in entity["canonical_of"]
    ]
    _require(len(set(folded)) == len(folded), "entity_canonical_of_duplicate")
    _require(entity_id not in folded, "entity_canonical_of_self")

    descriptor = _vector(entity["descriptor_mean"], "entity_descriptor_invalid")
    best_view = _vector(
        entity["best_view_descriptor"], "entity_best_view_descriptor_invalid",
    )
    _require(len(best_view) == len(descriptor), "entity_descriptor_dimension_mismatch")
    _int(entity["descriptor_count"], "entity_descriptor_count_invalid", minimum=1)
    _int(
        entity["best_view_pixel_count"],
        "entity_best_view_pixel_count_invalid",
        minimum=1,
    )

    _vector(entity["centroid_m"], "entity_centroid_invalid", length=3)
    lower = _vector(entity["aabb_min_m"], "entity_aabb_min_invalid", length=3)
    upper = _vector(entity["aabb_max_m"], "entity_aabb_max_invalid", length=3)
    _require(
        all(low <= high for low, high in zip(lower, upper, strict=True)),
        "entity_aabb_inverted",
    )

    _int(entity["observation_count"], "entity_observation_count_invalid", minimum=1)
    last_seen = _int(entity["last_seen_tick"], "entity_last_seen_invalid", minimum=0)
    _require(last_seen <= tick, "entity_last_seen_in_future")
    _int(entity["missed_opportunity_count"], "entity_missed_count_invalid", minimum=0)
    if entity["supported_by"] is not None:
        _identifier(entity["supported_by"], "entity_supported_by_invalid")

    _require(type(entity["evidence"]) is list and entity["evidence"], "entity_evidence_invalid")
    seen_evidence: set[tuple[str, str]] = set()
    for item in entity["evidence"]:
        _require(type(item) is dict, "entity_evidence_item_not_object")
        _require(
            set(item.keys()) == {"frame_digest", "fragment_id", "tick"},
            "entity_evidence_fields_invalid",
        )
        digest = _hex64(item["frame_digest"], "entity_evidence_digest_invalid")
        fragment_id = _identifier(item["fragment_id"], "entity_evidence_fragment_invalid")
        _int(item["tick"], "entity_evidence_tick_invalid", minimum=1)
        _require(item["tick"] <= tick, "entity_evidence_tick_in_future")
        key = (digest, fragment_id)
        _require(key not in seen_evidence, "entity_evidence_duplicate")
        seen_evidence.add(key)

    versions = entity["versions"]
    _require(type(versions) is list and versions, "entity_versions_invalid")
    open_versions = 0
    previous_id: str | None = None
    for index, version in enumerate(versions):
        _validate_version(version, entity_id=entity_id)
        if index == 0:
            _require(version["predecessor"] is None, "entity_first_version_has_predecessor")
            _require(version["opened_by"] == "birth", "entity_first_version_not_birth")
        else:
            _require(version["opened_by"] != "birth", "entity_birth_version_not_first")
            _require(
                version["predecessor"] == previous_id,
                "entity_version_chain_broken",
            )
            _require(
                versions[index - 1]["closed_at"] is not None,
                "entity_version_opened_over_open_version",
            )
            _require(
                int(version["opened_at"]) >= int(versions[index - 1]["closed_at"]),
                "entity_version_opened_before_predecessor_closed",
            )
        if version["closed_at"] is None:
            open_versions += 1
        previous_id = str(version["version_id"])
    _require(open_versions == 1, "entity_must_have_exactly_one_open_version")
    _require(
        versions[-1]["closed_at"] is None,
        "entity_open_version_must_be_last",
    )
    _require(
        versions[-1]["state"] == entity["state"],
        "entity_state_disagrees_with_open_version",
    )


#: Engineering (S2-05 profiling, LOG-254): the S0-03 and S0-04 functions each validate the memory
#: they are handed, so one frame validated the same sealed memory nine times and the walk over
#: every entity and version plus the digest recomputation took half of the per-frame time.  A
#: memory object this process has already validated with its digest verified is remembered by
#: (object id, digest, tick, entity count); a later call on that same object with the same digest
#: returns the copy without the walk.  Memories are sealed by ``apply_program`` and never mutated
#: in place afterwards, so the invariant holds; a copy, a tampered copy or a resealed memory is a
#: different object or a different digest and is validated in full.  The result is bit-identical.
#: The entry holds the object itself: an object id is only unique while the object is alive, and a
#: freed memory's address can be reused by a new memory with the same digest (two sealed memories of
#: one episode at one tick with the same content, as test fixtures produce), which would let an
#: in-place tamper of the new object slip past the digest check (server suite at 4e8028d).  The
#: limit is small because a frame touches two or three memory objects; holding them costs nothing.
_VALIDATED_MEMORIES: "collections.OrderedDict[tuple[int, str, int, int], dict[str, Any]]" = collections.OrderedDict()
_VALIDATED_MEMORIES_LIMIT = 8


def _validated_key(memory: Mapping[str, Any]) -> tuple[int, str, int, int] | None:
    digest = memory.get("memory_digest")
    entities = memory.get("entities")
    tick = memory.get("tick")
    if type(digest) is not str or type(entities) is not list or type(tick) is not int:
        return None
    return (id(memory), digest, tick, len(entities))


def validate_memory(memory: Mapping[str, Any], *, verify_digest: bool = True) -> dict[str, Any]:
    """Validate one memory object and return a deep copy of it.

    白话：输入一份记忆，输出同样内容的副本，并在任何字段、状态机或版本链不合法时
    抛错。例如一个实体同时有两个未关闭的版本会被拒绝。它不判断记忆内容在现实中
    是否正确，只判断结构合法。同一个已验证过、摘要未变的记忆对象再次传入时直接
    返回副本（工程缓存，见上）。
    """

    _require(type(memory) is dict, "memory_not_object")
    key = _validated_key(memory) if verify_digest else None
    if key is not None and _VALIDATED_MEMORIES.get(key) is memory:  # the very object validated before, digest unchanged
        _VALIDATED_MEMORIES.move_to_end(key)
        return clone_json(dict(memory))
    expected = {
        "schema_version", "episode_id", "tick", "entities",
        "transaction_log", "memory_digest",
    }
    _require(set(memory.keys()) == expected, "memory_fields_invalid")
    _require(memory["schema_version"] == SCHEMA_VERSION, "memory_schema_version_invalid")
    _identifier(memory["episode_id"], "episode_id_invalid")
    tick = _int(memory["tick"], "memory_tick_invalid", minimum=0)
    _json_native(
        {key: value for key, value in memory.items() if key != "memory_digest"},
        "memory_not_json_native",
    )

    entities = memory["entities"]
    _require(type(entities) is list, "memory_entities_invalid")
    ids: list[str] = []
    folded_ids: list[str] = []
    dimensions: set[int] = set()
    for entity in entities:
        _require(type(entity) is dict, "memory_entity_not_object")
        _validate_entity(entity, tick=tick)
        ids.append(str(entity["entity_id"]))
        folded_ids.extend(str(item) for item in entity["canonical_of"])
        dimensions.add(len(entity["descriptor_mean"]))
    _require(len(dimensions) <= 1, "memory_descriptor_dimension_mixed")
    _require(len(set(ids)) == len(ids), "memory_entity_id_duplicate")
    _require(len(set(folded_ids)) == len(folded_ids), "memory_folded_id_duplicate")
    _require(not (set(folded_ids) & set(ids)), "memory_folded_id_still_live")
    _require(ids == sorted(ids), "memory_entities_not_sorted_by_id")

    log = memory["transaction_log"]
    _require(type(log) is list, "memory_transaction_log_invalid")
    _require(len(log) == tick, "memory_transaction_log_length_mismatch")
    for index, record in enumerate(log):
        _require(type(record) is dict, "memory_log_record_not_object")
        _require(
            set(record.keys()) == {
                "transaction_id", "tick", "frame_digest", "operations",
                "post_maintenance",
            },
            "memory_log_fields_invalid",
        )
        _identifier(record["transaction_id"], "memory_log_transaction_id_invalid")
        _require(record["tick"] == index + 1, "memory_log_tick_not_monotone")
        _hex64(record["frame_digest"], "memory_log_frame_digest_invalid")

    if verify_digest:
        _require(
            memory["memory_digest"] == memory_digest(memory),
            "memory_digest_mismatch",
        )
        if key is not None:
            _VALIDATED_MEMORIES[key] = memory  # keeps the object (and so its id) alive while the entry lives
            while len(_VALIDATED_MEMORIES) > _VALIDATED_MEMORIES_LIMIT:
                _VALIDATED_MEMORIES.popitem(last=False)
    else:
        _hex64(memory["memory_digest"], "memory_digest_invalid")
    return clone_json(dict(memory))


# --------------------------------------------------------------------------
# program validation
# --------------------------------------------------------------------------

def _validate_fragment(fragment: Any, *, descriptor_length: int | None) -> dict[str, Any]:
    _require(type(fragment) is dict, "fragment_not_object")
    _require(set(fragment.keys()) == FRAGMENT_FIELDS, "fragment_fields_invalid")
    _identifier(fragment["fragment_id"], "fragment_id_invalid")
    descriptor = _vector(fragment["descriptor"], "fragment_descriptor_invalid")
    if descriptor_length is not None:
        _require(
            len(descriptor) == descriptor_length,
            "fragment_descriptor_dimension_mismatch",
        )
    _vector(fragment["centroid_m"], "fragment_centroid_invalid", length=3)
    lower = _vector(fragment["aabb_min_m"], "fragment_aabb_min_invalid", length=3)
    upper = _vector(fragment["aabb_max_m"], "fragment_aabb_max_invalid", length=3)
    _require(
        all(low <= high for low, high in zip(lower, upper, strict=True)),
        "fragment_aabb_inverted",
    )
    _int(fragment["pixel_count"], "fragment_pixel_count_invalid", minimum=1)
    if fragment["supported_by"] is not None:
        _identifier(fragment["supported_by"], "fragment_supported_by_invalid")
    return clone_json(dict(fragment))


def expand_program(program: Mapping[str, Any]) -> dict[str, Any]:
    """Expand ``REPLACE`` into its ``RETRACT`` + ``BIRTH`` components.

    白话：输入可能含 REPLACE 的帧程序，输出只含五个原子的等价程序，并在每个展开
    分量上记下它来自哪一个复合操作。例如一个 REPLACE 展开成先关闭旧实体、再从
    同一 fragment 新建实体两步。它不判断这两半是否都合法，那由 apply_program 检查。
    """

    _require(type(program) is dict, "program_not_object")
    _require(
        set(program.keys()) == {"frame_digest", "operations"},
        "program_fields_invalid",
    )
    _hex64(program["frame_digest"], "program_frame_digest_invalid")
    _require(type(program["operations"]) is list, "program_operations_invalid")

    expanded: list[dict[str, Any]] = []
    for index, operation in enumerate(program["operations"]):
        _require(type(operation) is dict, "operation_not_object")
        atom = operation.get("atom")
        _require(
            atom in ATOMS or atom in COMPOSITES,
            "operation_atom_unknown",
        )
        basis = operation.get("decision_basis")
        if basis is not None:
            _require(type(basis) is dict, "operation_decision_basis_invalid")
            _json_native(basis, "operation_decision_basis_not_json_native")
        if atom == "REPLACE":
            _require(
                set(operation.keys())
                <= {"atom", "retract_entity_id", "fragment", "decision_basis"},
                "replace_fields_invalid",
            )
            _require("retract_entity_id" in operation, "replace_missing_target")
            _require("fragment" in operation, "replace_missing_fragment")
            composite = f"REPLACE#{index}"
            expanded.append({
                "atom": "RETRACT",
                "entity_id": operation["retract_entity_id"],
                "decision_basis": clone_json(basis) if basis is not None else None,
                "composite": composite,
                "source_index": index,
            })
            expanded.append({
                "atom": "BIRTH",
                "fragment": clone_json(operation["fragment"]),
                "decision_basis": clone_json(basis) if basis is not None else None,
                "composite": composite,
                "source_index": index,
            })
            continue

        allowed = {"atom", "decision_basis"}
        if atom in TARGET_ATOMS:
            allowed.add("entity_id")
        if atom in FRAGMENT_ATOMS:
            allowed.add("fragment")
        _require(set(operation.keys()) <= allowed, "operation_fields_invalid")
        if atom in TARGET_ATOMS:
            _require("entity_id" in operation, "operation_missing_entity_id")
        if atom in FRAGMENT_ATOMS:
            _require("fragment" in operation, "operation_missing_fragment")
        record: dict[str, Any] = {
            "atom": atom,
            "decision_basis": clone_json(basis) if basis is not None else None,
            "composite": None,
            "source_index": index,
        }
        if atom in TARGET_ATOMS:
            record["entity_id"] = operation["entity_id"]
        if atom in FRAGMENT_ATOMS:
            record["fragment"] = clone_json(operation["fragment"])
        expanded.append(record)

    return {"frame_digest": program["frame_digest"], "operations": expanded}


# --------------------------------------------------------------------------
# execution
# --------------------------------------------------------------------------

#: D-224-S1 ruling 56 continued (2026-09-24): how an entity's box follows its fragments.
ENTITY_BOX_RULE = "union_of_the_fragment_boxes_attached_in_the_entity_latest_observed_frame_no_cross_frame_accumulation"


def _union_aabb(
    lower_a: Sequence[float], upper_a: Sequence[float],
    lower_b: Sequence[float], upper_b: Sequence[float],
) -> tuple[list[float], list[float]]:
    lower = [min(float(a), float(b)) for a, b in zip(lower_a, lower_b, strict=True)]
    upper = [max(float(a), float(b)) for a, b in zip(upper_a, upper_b, strict=True)]
    return lower, upper


def _blend(old: Sequence[float], old_weight: int, new: Sequence[float], new_weight: int) -> list[float]:
    total = old_weight + new_weight
    return [
        (old_weight * float(a) + new_weight * float(b)) / total
        for a, b in zip(old, new, strict=True)
    ]


def _snapshot(entity: Mapping[str, Any]) -> dict[str, Any]:
    return {field: clone_json(entity[field]) for field in VERSION_SNAPSHOT_FIELDS}


def _open_version(
    entity: dict[str, Any], *, tick: int, transaction_id: str, purpose: str,
) -> None:
    versions = entity["versions"]
    predecessor = str(versions[-1]["version_id"]) if versions else None
    version_id = opaque_id(
        transaction_id, entity["entity_id"], purpose, len(versions),
        prefix="entity-version",
    )
    _require(purpose in VERSION_OPENED_BY, "version_opened_by_invalid")
    version = {
        "version_id": version_id,
        "predecessor": predecessor,
        "opened_at": tick,
        "closed_at": None,
        "opening_transaction": transaction_id,
        "closing_transaction": None,
        "opened_by": purpose,
    }
    version.update(_snapshot(entity))
    versions.append(version)


def _close_version(entity: dict[str, Any], *, tick: int, transaction_id: str) -> None:
    version = entity["versions"][-1]
    _require(version["closed_at"] is None, "close_of_already_closed_version")
    version["closed_at"] = tick
    version["closing_transaction"] = transaction_id


def _attach_fragment(
    entity: dict[str, Any], fragment: Mapping[str, Any], *, tick: int, frame_digest: str,
) -> None:
    count = int(entity["descriptor_count"])
    entity["descriptor_mean"] = _blend(
        entity["descriptor_mean"], count, fragment["descriptor"], 1,
    )
    entity["descriptor_count"] = count + 1
    if int(fragment["pixel_count"]) > int(entity["best_view_pixel_count"]):
        entity["best_view_descriptor"] = clone_json(fragment["descriptor"])
        entity["best_view_pixel_count"] = int(fragment["pixel_count"])
    entity["centroid_m"] = clone_json(fragment["centroid_m"])
    # ruling 56 continued: a later frame replaces the box, a second fragment in the same frame joins it
    if int(entity["last_seen_tick"]) == int(tick):
        entity["aabb_min_m"], entity["aabb_max_m"] = _union_aabb(
            entity["aabb_min_m"], entity["aabb_max_m"], fragment["aabb_min_m"], fragment["aabb_max_m"],
        )
    else:
        entity["aabb_min_m"] = clone_json(fragment["aabb_min_m"])
        entity["aabb_max_m"] = clone_json(fragment["aabb_max_m"])
    entity["observation_count"] = int(entity["observation_count"]) + 1
    entity["last_seen_tick"] = tick
    entity["missed_opportunity_count"] = 0
    entity["supported_by"] = clone_json(fragment["supported_by"])
    entity["evidence"].append({
        "frame_digest": frame_digest,
        "fragment_id": fragment["fragment_id"],
        "tick": tick,
    })


def _birth_entity(
    fragment: Mapping[str, Any], *, tick: int, frame_digest: str,
    transaction_id: str, ordinal: int,
) -> dict[str, Any]:
    entity_id = opaque_id(
        transaction_id, fragment["fragment_id"], ordinal, prefix="entity",
    )
    entity = {
        "entity_id": entity_id,
        "state": "active",
        "canonical_of": [],
        "descriptor_mean": clone_json(fragment["descriptor"]),
        "descriptor_count": 1,
        "best_view_descriptor": clone_json(fragment["descriptor"]),
        "best_view_pixel_count": int(fragment["pixel_count"]),
        "centroid_m": clone_json(fragment["centroid_m"]),
        "aabb_min_m": clone_json(fragment["aabb_min_m"]),
        "aabb_max_m": clone_json(fragment["aabb_max_m"]),
        "observation_count": 1,
        "last_seen_tick": tick,
        "missed_opportunity_count": 0,
        "supported_by": clone_json(fragment["supported_by"]),
        "evidence": [{
            "frame_digest": frame_digest,
            "fragment_id": fragment["fragment_id"],
            "tick": tick,
        }],
        "versions": [],
    }
    _open_version(entity, tick=tick, transaction_id=transaction_id, purpose="birth")
    return entity


def apply_program(
    memory: Mapping[str, Any], program: Mapping[str, Any], *,
    method_id: str,
    dormancy_missed_opportunity_limit: int,
    dedup: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply one frame program atomically and return the new sealed memory.

    白话：输入旧记忆和本帧程序，输出新记忆；任何一个原子不合法则整笔失败，调用者
    手里的旧记忆逐字节不变。例如程序里两个 fragment 都想绑到同一个实体，整帧拒绝。
    它不选择该做哪个原子（那是分配层），不读 teacher/private/future。

    ``dormancy_missed_opportunity_limit`` and every ``dedup`` value must be
    supplied explicitly; there is no default, because an unfrozen policy value
    must not be able to slip in as a constant.
    """

    _identifier(method_id, "method_id_invalid")
    limit = _int(
        dormancy_missed_opportunity_limit,
        "dormancy_limit_invalid",
        minimum=1,
    )
    working = validate_memory(memory)
    expanded = expand_program(program)
    frame_digest = expanded["frame_digest"]
    tick = int(working["tick"]) + 1
    transaction_id = opaque_id(
        working["memory_digest"], method_id, tick, frame_digest,
        prefix="transaction",
    )

    by_id = {str(entity["entity_id"]): entity for entity in working["entities"]}
    descriptor_length = None
    if working["entities"]:
        descriptor_length = len(working["entities"][0]["descriptor_mean"])

    # ---- structural checks over the whole program, before any mutation ----
    used_fragments: set[str] = set()
    used_entities: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for operation in expanded["operations"]:
        atom = operation["atom"]
        record = dict(operation)
        if atom in FRAGMENT_ATOMS:
            fragment = _validate_fragment(
                operation["fragment"], descriptor_length=descriptor_length,
            )
            fragment_id = str(fragment["fragment_id"])
            _require(fragment_id not in used_fragments, "fragment_used_twice_in_frame")
            used_fragments.add(fragment_id)
            record["fragment"] = fragment
        if atom in TARGET_ATOMS:
            entity_id = _identifier(operation["entity_id"], "operation_entity_id_invalid")
            _require(entity_id in by_id, "operation_target_entity_unknown")
            _require(entity_id not in used_entities, "entity_used_twice_in_frame")
            used_entities.add(entity_id)
            state = str(by_id[entity_id]["state"])
            _require(
                atom in STATE_ALLOWED_ATOMS[state],
                f"atom_{atom.lower()}_illegal_for_state_{state}",
            )
            record["entity_id"] = entity_id
        normalized.append(record)

    # ---- apply; nothing above this line mutated ``working`` ----
    log_operations: list[dict[str, Any]] = []
    born = 0
    for operation in normalized:
        atom = operation["atom"]
        entry: dict[str, Any] = {
            "atom": atom,
            "composite": operation["composite"],
            "decision_basis": operation["decision_basis"],
        }
        if atom == "NOOP":
            entity = by_id[operation["entity_id"]]
            entity["missed_opportunity_count"] = int(
                entity["missed_opportunity_count"]
            ) + 1
            entry["entity_id"] = entity["entity_id"]
        elif atom == "BIND":
            entity = by_id[operation["entity_id"]]
            _close_version(entity, tick=tick, transaction_id=transaction_id)
            _attach_fragment(
                entity, operation["fragment"], tick=tick, frame_digest=frame_digest,
            )
            _open_version(
                entity, tick=tick, transaction_id=transaction_id, purpose="bind",
            )
            entry["entity_id"] = entity["entity_id"]
            entry["fragment_id"] = operation["fragment"]["fragment_id"]
        elif atom == "REACTIVATE":
            entity = by_id[operation["entity_id"]]
            _close_version(entity, tick=tick, transaction_id=transaction_id)
            entity["state"] = "active"
            _attach_fragment(
                entity, operation["fragment"], tick=tick, frame_digest=frame_digest,
            )
            _open_version(
                entity, tick=tick, transaction_id=transaction_id, purpose="reactivate",
            )
            entry["entity_id"] = entity["entity_id"]
            entry["fragment_id"] = operation["fragment"]["fragment_id"]
        elif atom == "RETRACT":
            entity = by_id[operation["entity_id"]]
            _close_version(entity, tick=tick, transaction_id=transaction_id)
            entity["state"] = "retracted"
            _open_version(
                entity, tick=tick, transaction_id=transaction_id, purpose="retract",
            )
            entry["entity_id"] = entity["entity_id"]
        elif atom == "BIRTH":
            entity = _birth_entity(
                operation["fragment"], tick=tick, frame_digest=frame_digest,
                transaction_id=transaction_id, ordinal=born,
            )
            born += 1
            _require(
                str(entity["entity_id"]) not in by_id,
                "birth_entity_id_collision",
            )
            by_id[str(entity["entity_id"])] = entity
            working["entities"].append(entity)
            entry["entity_id"] = entity["entity_id"]
            entry["fragment_id"] = operation["fragment"]["fragment_id"]
        else:  # pragma: no cover - guarded by expand_program
            raise LeanMemoryError("operation_atom_unknown")
        log_operations.append(entry)

    working["tick"] = tick

    # ---- shared deterministic maintenance, identical for all five arms ----
    dormancy_changes = _apply_dormancy(working, limit=limit, tick=tick, transaction_id=transaction_id)
    dedup_changes = _apply_dedup(
        working, dedup=dedup, tick=tick, transaction_id=transaction_id,
    )

    working["entities"].sort(key=lambda entity: str(entity["entity_id"]))
    working["transaction_log"].append({
        "transaction_id": transaction_id,
        "tick": tick,
        "frame_digest": frame_digest,
        "operations": log_operations,
        "post_maintenance": {
            "dormancy": dormancy_changes,
            "dedup": dedup_changes,
        },
    })
    result = seal_memory(working)
    return validate_memory(result)


def _apply_dormancy(
    memory: dict[str, Any], *, limit: int, tick: int, transaction_id: str,
) -> list[dict[str, Any]]:
    """Move active entities past the missed-opportunity limit to ``dormant``.

    白话：连续"应可见却没匹配"达到登记次数的活动实体转为 dormant，档案不删；任何
    一次匹配会把计数清零，因此不会因偶发漏检就休眠。它不是 RETRACT，也不需要负证据。
    """

    changes: list[dict[str, Any]] = []
    for entity in sorted(memory["entities"], key=lambda item: str(item["entity_id"])):
        if entity["state"] != "active":
            continue
        if int(entity["missed_opportunity_count"]) < limit:
            continue
        _close_version(entity, tick=tick, transaction_id=transaction_id)
        entity["state"] = "dormant"
        _open_version(
            entity, tick=tick, transaction_id=transaction_id, purpose="dormant",
        )
        changes.append({
            "entity_id": entity["entity_id"],
            "missed_opportunity_count": int(entity["missed_opportunity_count"]),
        })
    return changes


def _aabb_iou(entity_a: Mapping[str, Any], entity_b: Mapping[str, Any]) -> float:
    lower_a, upper_a = entity_a["aabb_min_m"], entity_a["aabb_max_m"]
    lower_b, upper_b = entity_b["aabb_min_m"], entity_b["aabb_max_m"]
    overlap = 1.0
    for axis in range(3):
        low = max(float(lower_a[axis]), float(lower_b[axis]))
        high = min(float(upper_a[axis]), float(upper_b[axis]))
        overlap *= max(0.0, high - low)
    volume_a = 1.0
    volume_b = 1.0
    for axis in range(3):
        volume_a *= max(0.0, float(upper_a[axis]) - float(lower_a[axis]))
        volume_b *= max(0.0, float(upper_b[axis]) - float(lower_b[axis]))
    union = volume_a + volume_b - overlap
    if union <= 0.0:
        return 0.0
    return overlap / union


def validate_dedup_policy(dedup: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the shared dedup policy.  Every value must be present."""

    _require(type(dedup) is dict, "dedup_not_object")
    _require(
        set(dedup.keys()) == {
            "period_ticks", "descriptor_cosine_min", "centroid_distance_max_m",
            "aabb_iou_min",
        },
        "dedup_fields_invalid",
    )
    return {
        "period_ticks": _int(dedup["period_ticks"], "dedup_period_invalid", minimum=1),
        "descriptor_cosine_min": _threshold(
            dedup["descriptor_cosine_min"], "dedup_cosine_invalid", low=-1.0, high=1.0,
        ),
        "centroid_distance_max_m": _finite(
            dedup["centroid_distance_max_m"], "dedup_distance_invalid",
        ),
        "aabb_iou_min": _threshold(
            dedup["aabb_iou_min"], "dedup_iou_invalid", low=0.0, high=1.0,
        ),
    }


def _first_opened_at(entity: Mapping[str, Any]) -> int:
    return int(entity["versions"][0]["opened_at"])


def _apply_dedup(
    memory: dict[str, Any], *, dedup: Mapping[str, Any] | None, tick: int,
    transaction_id: str,
) -> list[dict[str, Any]]:
    """Fold duplicate active or dormant entities, deterministically and identically for all arms.

    白话：每隔登记的帧数，把外观、位置和包围盒都足够接近的一对实体（active 或 dormant，
    裁决 76 (2)(a)；retracted 不参加）合并成一条记录，保留较早建立的身份并保存两边证据；
    合并后的位置和框取两者中较晚被看到的那一条（同一帧看到的两条取并框、质心按观测数
    加权），任一方 active 则合并结果为 active，否则仍为 dormant。它是五个方法逐字节共用的确定性规则，
    不是学习决定；canonical 取首版本最早、并列取 ID 字典序最小，使身份连续率以最早
    建立的身份为准。

    What happens to the folded record (D-224-X ruling X6).  The folded
    entity's id goes into the canonical's ``canonical_of`` and every one of
    its evidence items is carried over, so nothing that can resolve identity
    or feed the teacher is lost; its own version chain is not kept as a live
    record.  The contract states this as "archived into canonical_of, not
    deleted": it is the shared MERGE atom of the first paper, not a RETRACT,
    and ``physical_deletion_allowed: false`` refers to lifecycle history of
    live entities.  The transaction log keeps the fold under
    ``post_maintenance.dedup`` for audit.
    """

    if dedup is None:
        return []
    policy = validate_dedup_policy(dedup)
    if tick % policy["period_ticks"] != 0:
        return []

    active = sorted(
        (entity for entity in memory["entities"] if entity["state"] in DEDUP_ELIGIBLE_STATES),
        key=lambda item: str(item["entity_id"]),
    )
    pairs: list[tuple[float, str, str]] = []
    for index, left in enumerate(active):
        for right in active[index + 1:]:
            cosine = cosine_similarity(left["descriptor_mean"], right["descriptor_mean"])
            if cosine < policy["descriptor_cosine_min"]:
                continue
            distance = centroid_distance(
                {"centroid_m": left["centroid_m"]},
                {"centroid_m": right["centroid_m"]},
            )
            if distance > policy["centroid_distance_max_m"]:
                continue
            if _aabb_iou(left, right) < policy["aabb_iou_min"]:
                continue
            pairs.append((cosine, str(left["entity_id"]), str(right["entity_id"])))

    # Highest cosine first; ties broken by the two ids so the order never
    # depends on dict iteration or float noise beyond the compared values.
    pairs.sort(key=lambda item: (-item[0], item[1], item[2]))

    by_id = {str(entity["entity_id"]): entity for entity in memory["entities"]}
    merged: set[str] = set()
    changes: list[dict[str, Any]] = []
    for cosine, left_id, right_id in pairs:
        if left_id in merged or right_id in merged:
            continue
        left, right = by_id[left_id], by_id[right_id]
        ordered = sorted(
            (left, right),
            key=lambda item: (_first_opened_at(item), str(item["entity_id"])),
        )
        canonical, folded = ordered[0], ordered[1]
        _close_version(canonical, tick=tick, transaction_id=transaction_id)
        canonical_count = int(canonical["descriptor_count"])
        folded_count = int(folded["descriptor_count"])
        canonical["descriptor_mean"] = _blend(
            canonical["descriptor_mean"], canonical_count,
            folded["descriptor_mean"], folded_count,
        )
        canonical["descriptor_count"] = canonical_count + folded_count
        if int(folded["best_view_pixel_count"]) > int(canonical["best_view_pixel_count"]):
            canonical["best_view_descriptor"] = clone_json(folded["best_view_descriptor"])
            canonical["best_view_pixel_count"] = int(folded["best_view_pixel_count"])
        # ruling 56 continued: union only records last seen in the same frame; otherwise the later box wins.
        # Ruling 76 (2)(a): the centroid follows the box -- the later record's, a count-weighted blend only
        # for two records of the same frame (a stale and a fresh position are no longer averaged).
        if int(canonical["last_seen_tick"]) == int(folded["last_seen_tick"]):
            lower, upper = _union_aabb(
                canonical["aabb_min_m"], canonical["aabb_max_m"],
                folded["aabb_min_m"], folded["aabb_max_m"],
            )
            canonical["centroid_m"] = _blend(
                canonical["centroid_m"], int(canonical["observation_count"]),
                folded["centroid_m"], int(folded["observation_count"]),
            )
        elif int(folded["last_seen_tick"]) > int(canonical["last_seen_tick"]):
            lower, upper = clone_json(folded["aabb_min_m"]), clone_json(folded["aabb_max_m"])
            canonical["centroid_m"] = clone_json(folded["centroid_m"])
        else:
            lower, upper = clone_json(canonical["aabb_min_m"]), clone_json(canonical["aabb_max_m"])
        canonical["aabb_min_m"], canonical["aabb_max_m"] = lower, upper
        survivor_active = canonical["state"] == "active" or folded["state"] == "active"
        canonical["state"] = "active" if survivor_active else "dormant"
        canonical["observation_count"] = int(canonical["observation_count"]) + int(
            folded["observation_count"]
        )
        canonical["last_seen_tick"] = max(
            int(canonical["last_seen_tick"]), int(folded["last_seen_tick"]),
        )
        canonical["missed_opportunity_count"] = min(
            int(canonical["missed_opportunity_count"]),
            int(folded["missed_opportunity_count"]),
        )
        if canonical["supported_by"] is None:
            canonical["supported_by"] = clone_json(folded["supported_by"])
        known = {
            (item["frame_digest"], item["fragment_id"])
            for item in canonical["evidence"]
        }
        for item in folded["evidence"]:
            key = (item["frame_digest"], item["fragment_id"])
            if key in known:
                continue
            known.add(key)
            canonical["evidence"].append(clone_json(item))
        canonical["evidence"].sort(
            key=lambda item: (int(item["tick"]), str(item["fragment_id"])),
        )
        canonical["canonical_of"] = sorted(
            set(canonical["canonical_of"])
            | set(folded["canonical_of"])
            | {str(folded["entity_id"])}
        )
        _open_version(
            canonical, tick=tick, transaction_id=transaction_id,
            purpose="dedup" if survivor_active else "dedup_dormant",
        )
        merged.add(str(folded["entity_id"]))
        changes.append({
            "canonical_entity_id": canonical["entity_id"],
            "folded_entity_id": folded["entity_id"],
            "descriptor_cosine": cosine,
        })

    if merged:
        memory["entities"] = [
            entity for entity in memory["entities"]
            if str(entity["entity_id"]) not in merged
        ]
    return changes


# --------------------------------------------------------------------------
# D-224-G: world-model facing views
# --------------------------------------------------------------------------

def entity_tokens(
    memory: Mapping[str, Any], *, include_retracted: bool = False,
) -> list[dict[str, Any]]:
    """Serialize memory as one fixed-field token per entity (D-224-G).

    白话：输入当前记忆，输出每个实体一行、字段顺序固定的 token，供下游世界模型或
    规划器消费。例如对象中心世界模型可以只读这些 token 做状态转移预测。它不含
    house ID、实例 ID、teacher 或任何私有量，也不是首篇的实验对象。
    """

    validate_memory(memory)
    tick = int(memory["tick"])
    tokens: list[dict[str, Any]] = []
    for entity in sorted(memory["entities"], key=lambda item: str(item["entity_id"])):
        state = str(entity["state"])
        if state == "retracted" and not include_retracted:
            continue
        lower = entity["aabb_min_m"]
        upper = entity["aabb_max_m"]
        token = {
            "entity_id": str(entity["entity_id"]),
            "state_one_hot": [
                1 if state == candidate else 0 for candidate in ENTITY_STATES
            ],
            "descriptor": clone_json(entity["descriptor_mean"]),
            "centroid_m": clone_json(entity["centroid_m"]),
            "extent_m": [
                float(upper[axis]) - float(lower[axis]) for axis in range(3)
            ],
            "observation_count": int(entity["observation_count"]),
            "age_ticks": tick - _first_opened_at(entity),
            "version_count": len(entity["versions"]),
            "missed_opportunity_count": int(entity["missed_opportunity_count"]),
            "supported_by_present": entity["supported_by"] is not None,
        }
        _require(
            tuple(token.keys()) == ENTITY_TOKEN_FIELDS,
            "entity_token_field_order_changed",
        )
        tokens.append(token)
    return tokens


def frame_delta(memory: Mapping[str, Any], *, tick: int | None = None) -> dict[str, Any]:
    """Return the sparse residual for one committed frame (D-224-G).

    白话：输入记忆和一个帧号，输出该帧只改动了哪些实体、各自被哪个原子改动，以及
    共享维护造成的休眠与去重。例如一帧里只有一个 BIND 和一个 BIRTH 时，残差只列
    这两个实体。它让世界模型不必每帧重算整份记忆。
    """

    validate_memory(memory)
    log = memory["transaction_log"]
    _require(bool(log), "frame_delta_on_empty_log")
    target = int(memory["tick"]) if tick is None else _int(tick, "frame_delta_tick_invalid", minimum=1)
    matches = [record for record in log if int(record["tick"]) == target]
    _require(len(matches) == 1, "frame_delta_tick_not_found")
    record = matches[0]
    changed: dict[str, list[str]] = {}
    for operation in record["operations"]:
        if operation["atom"] == "NOOP":
            continue
        changed.setdefault(str(operation["entity_id"]), []).append(str(operation["atom"]))
    maintenance = record["post_maintenance"]
    for item in maintenance["dormancy"]:
        changed.setdefault(str(item["entity_id"]), []).append("DORMANT")
    for item in maintenance["dedup"]:
        changed.setdefault(str(item["canonical_entity_id"]), []).append("DEDUP_CANONICAL")
    return {
        "tick": target,
        "transaction_id": str(record["transaction_id"]),
        "frame_digest": str(record["frame_digest"]),
        "changed_entities": {
            entity_id: changed[entity_id] for entity_id in sorted(changed)
        },
        "folded_entities": sorted(
            str(item["folded_entity_id"]) for item in maintenance["dedup"]
        ),
        "unchanged_entity_count": sum(
            1 for entity in memory["entities"]
            if str(entity["entity_id"]) not in changed
        ),
    }


# --------------------------------------------------------------------------
# machine contract
# --------------------------------------------------------------------------

def validate_entity_memory_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Check that the S0-01 machine contract agrees with this implementation.

    白话：输入 S0-01 机器合同，输出同一份合同的副本，并在原子集合、状态机、token
    字段顺序或授权位与本实现不一致时抛错。例如合同里多出一个第六原子会被拒绝。
    它不检查那些仍为 null 的数值，只检查结构与本实现同值。
    """

    _require(type(contract) is dict, "contract_not_object")
    _require(
        contract.get("schema_version") == CONTRACT_SCHEMA_VERSION,
        "contract_schema_version_invalid",
    )
    _require(contract.get("decision_id") == "D-224", "contract_decision_id_invalid")
    _require(contract.get("stage_id") == "S0-01", "contract_stage_id_invalid")

    required = {
        "atoms", "composites", "entity_states", "entity_token_schema",
        "version_record", "state_machine", "shared_dormancy", "shared_dedup",
        "authorization", "not_in_first_paper", "entity_box",
    }
    missing = sorted(required - set(contract.keys()))
    _require(not missing, f"contract_missing_sections:{','.join(missing)}")

    _require(tuple(contract["atoms"]) == ATOMS, "contract_atoms_mismatch")
    _require(contract["entity_box"].get("rule") == ENTITY_BOX_RULE
             and contract["entity_box"].get("cross_frame_accumulation") is False, "contract_entity_box_rule_mismatch")
    _require(tuple(contract["composites"]) == COMPOSITES, "contract_composites_mismatch")
    _require(
        tuple(contract["entity_states"]) == ENTITY_STATES,
        "contract_entity_states_mismatch",
    )
    _require(
        tuple(contract["entity_token_schema"]["field_order"]) == ENTITY_TOKEN_FIELDS,
        "contract_token_field_order_mismatch",
    )
    _require(
        tuple(contract["version_record"]["snapshot_fields"]) == VERSION_SNAPSHOT_FIELDS,
        "contract_version_snapshot_fields_mismatch",
    )
    _require(
        "opened_by" in contract["version_record"]["fields"],
        "contract_version_record_lacks_opened_by",
    )
    _require(
        tuple(contract["version_record"]["opened_by_values"]) == VERSION_OPENED_BY,
        "contract_version_opened_by_values_mismatch",
    )
    _require(
        dict(contract["version_record"]["opened_by_state"]) == VERSION_OPENED_BY_STATE,
        "contract_version_opened_by_state_mismatch",
    )
    _require(
        contract["shared_dedup"]["folded_record_is_archived_into_canonical_of_not_deleted"] is True,
        "contract_dedup_fold_semantics_weakened",
    )
    _require(
        contract["shared_dedup"].get("rule") == DEDUP_RULE
        and tuple(contract["shared_dedup"].get("eligible_states", ())) == DEDUP_ELIGIBLE_STATES
        and contract["shared_dedup"].get("survivor_geometry") == DEDUP_SURVIVOR_GEOMETRY
        and contract["shared_dedup"].get("survivor_state") == DEDUP_SURVIVOR_STATE,
        "contract_dedup_rule_mismatch",
    )
    _require(
        contract["state_machine"]["physical_deletion_allowed"] is False,
        "contract_physical_deletion_claim_weakened",
    )

    allowed = contract["state_machine"]["allowed_atoms_by_state"]
    _require(
        set(allowed.keys()) == set(STATE_ALLOWED_ATOMS.keys()),
        "contract_state_machine_states_mismatch",
    )
    for state, atoms in allowed.items():
        _require(
            frozenset(atoms) == STATE_ALLOWED_ATOMS[state],
            f"contract_state_machine_atoms_mismatch_{state}",
        )

    # A registered value is either still open, and then it must say so in
    # policy_values_without_defaults, or frozen, and then it must have left that
    # list and equal the constant this implementation binds (D-224-S1 ruling 24;
    # the five values were frozen by ruling 67 on 2026-09-24).
    open_values = contract["policy_values_without_defaults"]
    frozen = {
        ("shared_dormancy", "dormancy_missed_opportunity_limit", "dormancy_missed_opportunity_limit"): DORMANCY_MISSED_OPPORTUNITY_LIMIT,
        **{("shared_dedup", name, f"shared_dedup.{name}"): value for name, value in SHARED_DEDUP.items()},
    }
    for (section, name, registered), expected in frozen.items():
        value = contract[section][name]
        if value is None:
            _require(registered in open_values, f"contract_{name}_null_but_not_registered_as_open")
        else:
            _require(registered not in open_values, f"contract_{name}_frozen_but_still_listed_as_open")
            _require(value == expected, f"contract_{name}_differs_from_the_frozen_constant")

    authorization = contract["authorization"]
    _require(
        all(value is False for value in authorization.values()),
        "contract_authorization_must_be_all_false",
    )
    for forbidden in contract["not_in_first_paper"]:
        _require(
            forbidden not in ATOMS,
            "contract_forbidden_list_contains_live_atom",
        )
    return clone_json(dict(contract))


__all__ = [
    "ATOMS",
    "ENTITY_BOX_RULE",
    "COMPOSITES",
    "CONTRACT_SCHEMA_VERSION",
    "ENTITY_STATES",
    "ENTITY_TOKEN_FIELDS",
    "LeanMemoryError",
    "SCHEMA_VERSION",
    "STATE_ALLOWED_ATOMS",
    "VERSION_OPENED_BY",
    "VERSION_OPENED_BY_STATE",
    "DEDUP_RULE",
    "DEDUP_ELIGIBLE_STATES",
    "DEDUP_SURVIVOR_GEOMETRY",
    "DEDUP_SURVIVOR_STATE",
    "VERSION_SNAPSHOT_FIELDS",
    "apply_program",
    "empty_memory",
    "entity_tokens",
    "expand_program",
    "frame_delta",
    "memory_digest",
    "seal_memory",
    "validate_dedup_policy",
    "validate_entity_memory_contract",
    "validate_memory",
]
