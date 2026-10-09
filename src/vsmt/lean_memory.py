"""D-224 / S0-01: the VSMT-lean entity memory core.

This module is the only place where entity records are created, versioned,
closed or reopened.  It is deliberately self-contained: the archived
D-210..D-223 ``GraphRevision`` path (removed from ``main`` after the tag
``paper-v1``) was bound to the place scaffold, five relation-edge types,
``graph_hash`` and the unified-graph lifecycle, so narrowing it would have
dragged all of that back in.  Only pure helpers that would otherwise gain a
second numeric definition are reused: canonical JSON and deep clone from
``cpmt.hashing``; cosine, centroid distance and opaque IDs from
``vsmt.lean_geometry``.

Input: a sealed memory and one frame program; output: the new sealed memory
with its per-entity version chains and the frame's transaction-log record.
Any illegal atom (e.g. REACTIVATE of an active entity) rolls back the whole
frame and leaves the old memory byte-identical.  The module makes no
association decision (the assignment layer does) and reads no private,
teacher or future data.

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
  silently become an experiment constant.  The values frozen by D-224-S1
  rulings 67, 68 and 77 are ``DORMANCY_MISSED_OPPORTUNITY_LIMIT`` and
  ``SHARED_DEDUP``; callers pass them.
"""

from __future__ import annotations

import collections
import hashlib
import math
from typing import Any, Mapping, Sequence

import numpy as np

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
#: not "what did it look like", and a descriptor per version (128-d: the shared
#: ReID projection of DINOv2 ViT-B/14, METHOD section 5) would make the stored
#: memory grow linearly with frame count.
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


#: 2026-09-27, engineering (history-proportional per-frame cost): the canonical JSON of each entity and of each
#: transaction-log record, keyed by object identity (the object is kept alive in the entry so its id cannot be reused).
#: A sealed memory is never modified in place (LOG-254's premise: only ``apply_program`` seals, and it now copies an
#: entity before touching it), so an unchanged record keeps its string from one frame to the next; each call keeps
#: only the records of the memory it just serialised.
_PART_JSON: dict[int, tuple[Any, str]] = {}
#: 2026-09-27 (dagger_round_0 profile): the same per-object cache one level down, for the version and evidence items of
#: an entity.  A changed entity is a new object, but it shares every closed version and every evidence item with the
#: record it was copied from, so only its new or changed items are serialised again.
_ITEM_JSON: dict[int, tuple[Any, str]] = {}
_MEMORY_PAYLOAD_KEYS = ("entities", "episode_id", "schema_version", "tick", "transaction_log")
_ENTITY_ITEM_LISTS = ("evidence", "versions")


def _entity_canonical_json(entity: Any, item_part: Any) -> str:
    """``canonical_json(entity)`` assembled from the cached strings of its version and evidence items.

    The encoder writes a sorted-key object as ``{"k":v,...}`` and a list as ``[a,b,...]``, so joining each item's own
    canonical string reproduces the whole string byte for byte (pinned by test); anything else takes the whole path.
    """

    if (type(entity) is not dict or any(type(key) is not str for key in entity)
            or any(type(entity.get(name)) is not list for name in _ENTITY_ITEM_LISTS)):
        return canonical_json(entity)
    fields = []
    for key in sorted(entity):
        value = entity[key]
        text = ("[" + ",".join(item_part(item) for item in value) + "]") if key in _ENTITY_ITEM_LISTS else canonical_json(value)
        fields.append(canonical_json(key) + ":" + text)
    return "{" + ",".join(fields) + "}"


def _canonical_payload(memory: Mapping[str, Any]) -> str:
    """``canonical_json`` of the memory without its digest, assembled from cached per-record strings.

    It equals ``canonical_json(payload)`` byte for byte: the encoder writes a sorted-key object as ``{"k":v,...}``
    and a list as ``[a,b,...]`` with the same separators, so joining the parts' own canonical strings reproduces it.
    Any memory outside the frozen five-key shape takes the whole-object path.
    """

    global _PART_JSON, _ITEM_JSON
    payload = {key: value for key, value in memory.items() if key != "memory_digest"}
    if (tuple(sorted(payload)) != _MEMORY_PAYLOAD_KEYS or type(payload["entities"]) is not list
            or type(payload["transaction_log"]) is not list):
        return canonical_json(payload)
    previous, kept = _PART_JSON, {}
    previous_items, kept_items = _ITEM_JSON, {}

    def item_part(item: Any) -> str:
        hit = previous_items.get(id(item))
        text = hit[1] if hit is not None and hit[0] is item else canonical_json(item)
        kept_items[id(item)] = (item, text)
        return text

    def part(item: Any, *, entity: bool) -> str:
        hit = previous.get(id(item))
        if hit is not None and hit[0] is item:
            text = hit[1]
            if entity and type(item) is dict:  # carry its items' strings forward for the copy a later frame may make
                for name in _ENTITY_ITEM_LISTS:
                    for sub in item.get(name) or ():
                        sub_hit = previous_items.get(id(sub))
                        if sub_hit is not None and sub_hit[0] is sub:
                            kept_items[id(sub)] = sub_hit
        else:
            text = _entity_canonical_json(item, item_part) if entity else canonical_json(item)
        kept[id(item)] = (item, text)
        return text

    entities = ",".join(part(item, entity=True) for item in payload["entities"])
    log = ",".join(part(item, entity=False) for item in payload["transaction_log"])
    _PART_JSON = kept
    _ITEM_JSON = kept_items
    return ('{"entities":[' + entities + '],"episode_id":' + canonical_json(payload["episode_id"])
            + ',"schema_version":' + canonical_json(payload["schema_version"]) + ',"tick":' + canonical_json(payload["tick"])
            + ',"transaction_log":[' + log + ']}')


def memory_digest(memory: Mapping[str, Any]) -> str:
    """SHA-256 over the canonical memory payload, excluding the digest itself."""

    return hashlib.sha256(_canonical_payload(memory).encode("utf-8")).hexdigest()


def memory_digest_from_scratch(memory: Mapping[str, Any]) -> str:
    """The same digest serialised in one piece, without any cached part (the end-of-episode check)."""

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

    It has no entity and represents no observation; the tick is 0 and becomes 1 when the first frame commits.
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


def _validate_entity(entity: Mapping[str, Any], *, tick: int, seen_item: Any = None) -> None:
    """Check one entity in full; ``seen_item(item)`` true skips the per-item checks of an item checked before.

    The chain, ordering, uniqueness and state checks always run over every item; only the per-item field checks of a
    version or evidence item that is the very object already checked at an earlier or equal tick are skipped (their
    only tick-dependent check, ``tick <= memory tick``, stays true as the tick grows).
    """

    skip = seen_item if seen_item is not None else (lambda item: False)
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
        if skip(item):
            key = (item["frame_digest"], item["fragment_id"])
            _require(key not in seen_evidence, "entity_evidence_duplicate")
            seen_evidence.add(key)
            continue
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
        if not skip(version):
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
#: 2026-09-27: per-record validation memo (object identity -> (object, tick or minus the log position)); see validate_memory.
_VALIDATED_PARTS: dict[int, tuple[Any, int]] = {}
#: 2026-09-27 (dagger_round_0 profile): the same memo for the version and evidence items of the entities, so a changed
#: entity -- a new object sharing its closed versions and evidence with the record it was copied from -- has only its
#: new or changed items checked field by field; the chain and uniqueness checks still run over all of them.
_VALIDATED_ITEMS: dict[int, tuple[Any, int]] = {}


def _validated_key(memory: Mapping[str, Any]) -> tuple[int, str, int, int] | None:
    digest = memory.get("memory_digest")
    entities = memory.get("entities")
    tick = memory.get("tick")
    if type(digest) is not str or type(entities) is not list or type(tick) is not int:
        return None
    return (id(memory), digest, tick, len(entities))


def validate_memory(memory: Mapping[str, Any], *, verify_digest: bool = True, copy: bool = True) -> dict[str, Any]:
    """Validate one memory object and return a deep copy of it (or, with ``copy=False``, the object itself).

    ``copy=False`` (2026-09-27, engineering): for callers that only read the memory.  The memory carries its whole
    history (versions, evidence, transaction log), so every deep copy costs time in proportion to the frames already
    run; about ten copies per frame made each frame slower the longer the episode ran (00563: 0.4 s per frame in its
    first tenth, 8.7 s in its last, with the entity count flat).  The checks and the digest are unchanged; a caller
    that mutates what it gets must keep the default.

    The checks are structural only -- fields, state machine, version chains, digest (e.g. an entity with two open
    versions is refused); whether the content is true of the scene is not judged.  A memory object validated before
    with an unchanged digest is returned without the walk (``_VALIDATED_MEMORIES``).
    """

    global _VALIDATED_PARTS, _VALIDATED_ITEMS
    _require(type(memory) is dict, "memory_not_object")
    key = _validated_key(memory) if verify_digest else None
    if key is not None and _VALIDATED_MEMORIES.get(key) is memory:  # the very object validated before, digest unchanged
        _VALIDATED_MEMORIES.move_to_end(key)
        return clone_json(dict(memory)) if copy else memory
    expected = {
        "schema_version", "episode_id", "tick", "entities",
        "transaction_log", "memory_digest",
    }
    _require(set(memory.keys()) == expected, "memory_fields_invalid")
    _require(memory["schema_version"] == SCHEMA_VERSION, "memory_schema_version_invalid")
    _identifier(memory["episode_id"], "episode_id_invalid")
    tick = _int(memory["tick"], "memory_tick_invalid", minimum=0)
    # 2026-09-27, engineering: an entity or log record that is the very object already checked at an earlier or equal
    # tick (every tick check is "not after the memory's tick", so it stays true) and at the same log position is not
    # walked again; everything new or copied is checked in full, in the same order as before.
    known = _VALIDATED_PARTS
    known_items = _VALIDATED_ITEMS
    entities_raw = memory["entities"]
    log_raw = memory["transaction_log"]

    def seen(item: Any, stamp: int) -> bool:
        hit = known.get(id(item))
        return hit is not None and hit[0] is item and hit[1] <= stamp

    def seen_item(item: Any) -> bool:  # a version or evidence item checked at an earlier or equal tick
        hit = known_items.get(id(item))
        return hit is not None and hit[0] is item and hit[1] <= tick

    if type(entities_raw) is list and type(log_raw) is list:
        for key_name, value in memory.items():
            if key_name not in ("memory_digest", "entities", "transaction_log"):
                _json_native(value, "memory_not_json_native")
        for item in entities_raw:
            if seen(item, tick):
                continue
            if type(item) is dict and all(type(item.get(name)) is list for name in _ENTITY_ITEM_LISTS):
                for key_name, value in item.items():
                    _require(type(key_name) is str, "memory_not_json_native")
                    if key_name in _ENTITY_ITEM_LISTS:
                        for sub in value:
                            if not seen_item(sub):
                                _json_native(sub, "memory_not_json_native")
                    else:
                        _json_native(value, "memory_not_json_native")
            else:
                _json_native(item, "memory_not_json_native")
        for index, item in enumerate(log_raw):
            if not seen(item, -index - 1):
                _json_native(item, "memory_not_json_native")
    else:
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
        if not seen(entity, tick):
            _validate_entity(entity, tick=tick, seen_item=seen_item)
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
        if seen(record, -index - 1):
            continue
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
        # remember this memory's records as checked (entities at this tick, log records at their position; the
        # stamp for a log record is minus its 1-based position so the two kinds never compare across)
        _VALIDATED_PARTS = {**{id(item): (item, tick) for item in entities},
                            **{id(item): (item, -index - 1) for index, item in enumerate(log)}}
        _VALIDATED_ITEMS = {id(sub): (sub, tick) for item in entities for name in _ENTITY_ITEM_LISTS for sub in item[name]}
        if key is not None:
            _VALIDATED_MEMORIES[key] = memory  # keeps the object (and so its id) alive while the entry lives
            while len(_VALIDATED_MEMORIES) > _VALIDATED_MEMORIES_LIMIT:
                _VALIDATED_MEMORIES.popitem(last=False)
    else:
        _hex64(memory["memory_digest"], "memory_digest_invalid")
    return clone_json(dict(memory)) if copy else memory


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

    Each component records its composite (``REPLACE#<index>``) and source index.  Whether both halves are legal is
    checked by ``apply_program``, not here.
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


def _entity_for_write(entity: Mapping[str, Any]) -> dict[str, Any]:
    """A copy of a sealed entity that the executor may change without touching the original.

    Engineering (2026-09-27, dagger_round_0 profile): the executor used to deep-copy an entity before changing it,
    closed versions and evidence included, so a frame's cost grew with the history of the entities it touched.  The
    executor changes an entity only by assigning its fields, appending to (and, in dedup, sorting) its ``versions`` and
    ``evidence`` lists, and closing its last version; so the copy gets new lists and a new last version, and shares
    the closed versions and evidence items, which nothing changes once written.  Same content, same digests.
    """

    copy = {key: (list(value) if type(value) is list else value) for key, value in entity.items()}
    copy["versions"][-1] = dict(copy["versions"][-1])
    return copy


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

    Any illegal atom fails the whole frame and leaves the caller's memory byte-identical (e.g. two fragments bound to
    one entity: ``entity_used_twice_in_frame``).  The atoms are chosen by the assignment layer; this function reads no
    teacher, private or future data.

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
    source = validate_memory(memory, copy=False)
    # 2026-09-27, engineering: copy on write.  The new memory shares every record it does not change with the old one;
    # an entity is copied the first time this frame changes it (an operation's target, a dormancy change, every dedup
    # candidate on a dedup tick) and the log gets one new record, so the old memory stays byte for byte what it was.
    working = dict(source)
    working["entities"] = list(source["entities"])
    working["transaction_log"] = list(source["transaction_log"])
    position = {str(entity["entity_id"]): index for index, entity in enumerate(working["entities"])}
    owned: set[str] = set()

    def own(entity_id: str) -> dict[str, Any]:
        if entity_id not in owned:
            copy_of = _entity_for_write(working["entities"][position[entity_id]])
            working["entities"][position[entity_id]] = copy_of
            by_id[entity_id] = copy_of
            owned.add(entity_id)
        return by_id[entity_id]

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
        if atom in TARGET_ATOMS:
            own(operation["entity_id"])
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
            position[str(entity["entity_id"])] = len(working["entities"]) - 1
            owned.add(str(entity["entity_id"]))
            entry["entity_id"] = entity["entity_id"]
            entry["fragment_id"] = operation["fragment"]["fragment_id"]
        else:  # pragma: no cover - guarded by expand_program
            raise LeanMemoryError("operation_atom_unknown")
        log_operations.append(entry)

    working["tick"] = tick

    # ---- shared deterministic maintenance, identical for all arms ----
    for entity_id, entity in list(by_id.items()):  # the entities dormancy will change
        if entity["state"] == "active" and int(entity["missed_opportunity_count"]) >= limit:
            own(entity_id)
    dormancy_changes = _apply_dormancy(working, limit=limit, tick=tick, transaction_id=transaction_id)
    dedup_changes = _apply_dedup(
        working, dedup=dedup, tick=tick, transaction_id=transaction_id, own=own,
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
    working.pop("memory_digest", None)
    working["memory_digest"] = memory_digest(working)  # sealed in place: ``working`` is this call's own object
    return validate_memory(working, copy=False)


def _apply_dormancy(
    memory: dict[str, Any], *, limit: int, tick: int, transaction_id: str,
) -> list[dict[str, Any]]:
    """Move active entities past the missed-opportunity limit to ``dormant``.

    The record is kept, and any match resets the count (``_attach_fragment``), so only consecutive misses lead here.
    Dormancy is not RETRACT and needs no evidence of absence.
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


#: How far below the cosine minimum and above the distance maximum a pair may be and still reach the exact test.
#: Float64 rounding in a 128-term dot product or a 3-term distance is below 1e-12; the margin only has to exceed it.
DEDUP_PREFILTER_MARGIN = 1e-6
DEDUP_PREFILTER_BLOCK_ROWS = 256


def _dedup_pair_candidates(entities: Sequence[Mapping[str, Any]], policy: Mapping[str, Any]) -> list[tuple[int, int]]:
    """Index pairs (i < j, row-major) that may pass the cosine and distance tests of the dedup rule.

    Engineering (2026-09-27, the dagger_round_0 timing trial): every dedup tick compared every pair of
    active and dormant entities in pure Python, so under ELU-P, whose dormant entities pile up, the
    cost per frame grew with the square of the frames already run (01289: 0.12 s per frame in its
    first 150 frames, 1.1 s by frame 1200 with the active count flat).  This is a prefilter only: it
    drops a pair when numpy's cosine is below the minimum or its distance above the maximum by more
    than ``DEDUP_PREFILTER_MARGIN``, which float rounding cannot reach; every surviving pair is decided
    by the unchanged scalar tests, in the unchanged order, so the folds and the digests are the same.
    Rows of unequal width, or with a norm too small for a safe division, keep every pair.  The dedup rule and its
    thresholds are unchanged.
    """

    count = len(entities)
    if count < 2:
        return []
    widths = {len(entity["descriptor_mean"]) for entity in entities}
    if len(widths) != 1 or 0 in widths:
        return [(i, j) for i in range(count) for j in range(i + 1, count)]
    descriptors = np.asarray([entity["descriptor_mean"] for entity in entities], dtype=np.float64)
    centroids = np.asarray([entity["centroid_m"] for entity in entities], dtype=np.float64)
    norms = np.sqrt(np.einsum("ij,ij->i", descriptors, descriptors))
    unsafe = norms < 1e-100
    unit = descriptors / np.where(unsafe, 1.0, norms)[:, None]
    cosine_floor = float(policy["descriptor_cosine_min"]) - DEDUP_PREFILTER_MARGIN
    distance_ceiling = float(policy["centroid_distance_max_m"]) + DEDUP_PREFILTER_MARGIN
    out: list[tuple[int, int]] = []
    for start in range(0, count, DEDUP_PREFILTER_BLOCK_ROWS):
        stop = min(count, start + DEDUP_PREFILTER_BLOCK_ROWS)
        cosine = unit[start:stop] @ unit.T
        distance = np.sqrt(((centroids[start:stop, None, :] - centroids[None, :, :]) ** 2).sum(axis=2))
        keep = (cosine >= cosine_floor) | unsafe[start:stop, None] | unsafe[None, :]
        keep &= distance <= distance_ceiling
        keep &= np.arange(start, stop)[:, None] < np.arange(count)[None, :]
        rows, columns = np.nonzero(keep)
        out.extend(zip((rows + start).tolist(), columns.tolist()))
    return out


def _apply_dedup(
    memory: dict[str, Any], *, dedup: Mapping[str, Any] | None, tick: int,
    transaction_id: str, own: Any = None,
) -> list[dict[str, Any]]:
    """Fold duplicate active or dormant entities, deterministically and identically for all arms.

    Every ``period_ticks`` frames, pairs of active or dormant entities (ruling 76 (2)(a); retracted entities do not take
    part) that pass the cosine, centroid-distance and box-IoU tests are folded, highest cosine first.  The canonical
    record is the one whose first version opened earliest (ties: the smaller ``entity_id``), so identity continuity
    follows the earliest identity.  The survivor keeps the evidence of both records, takes the geometry of the more
    recently observed one (same tick: the union box and the observation-count-weighted centroid) and is active if
    either record was, dormant otherwise.  All arms run this rule byte-identically; it is not a learned decision.

    What happens to the folded record (D-224-X ruling X6).  The folded
    entity's id goes into the canonical's ``canonical_of`` and every one of
    its evidence items is carried over, so nothing that can resolve identity
    or feed the teacher is lost; its own version chain is not kept as a live
    record.  The contract states this as "archived into canonical_of, not
    deleted": it is the shared MERGE atom of the first paper, not a RETRACT,
    and ``physical_deletion_allowed: false`` refers to lifecycle history of
    live entities.  The transaction log keeps the fold under
    ``post_maintenance.dedup`` for audit.

    ``own`` (the executor's copy-on-write hook, 2026-09-27) is called on a survivor just before it is changed, so only
    the entities a fold changes are copied, not every candidate; without it the records are changed in place.
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
    for left_index, right_index in _dedup_pair_candidates(active, policy):
        left, right = active[left_index], active[right_index]
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
        if own is not None:  # a later pair must see the changed survivor, as it did when the record changed in place
            canonical = by_id[str(canonical["entity_id"])] = own(str(canonical["entity_id"]))
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

    The rows (``ENTITY_TOKEN_FIELDS`` order) are for a downstream world model or planner.  They carry no house ID,
    instance ID, teacher or private value, and they are not an experimental subject of the paper (METHOD section 3).
    """

    validate_memory(memory, copy=False)
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

    It lists the entities the frame changed and by which atom (NOOP excluded), the dormancy and dedup changes of the
    shared maintenance, and the folded entities, so a world model need not re-read the whole memory each frame.
    """

    validate_memory(memory, copy=False)
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

    Returns a copy of the contract.  Raises when the atoms (e.g. a sixth atom), composites, states, state machine, token
    field order, version record, entity-box rule, dedup rule or authorization bits disagree with this module, or when a
    shared dormancy / dedup value is neither null and registered as open nor equal to the frozen constant.
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
    # the five values were frozen by ruling 67 on 2026-09-24, the dedup values
    # re-frozen by rulings 68 and 77).
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
    "memory_digest_from_scratch",
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
