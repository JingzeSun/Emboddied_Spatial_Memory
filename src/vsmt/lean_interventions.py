"""D-224 / S1-02 I1: the intervention selector, as a pure function.

Decides which objects an episode changes and how: object eligibility, the
set F of feasible (object, kind, shared window) triples, the dry-run
destinations, sampling of at most 6 interventions, the twin-control
containers (ruling 34), the null-window draw (p = 0.2, ruling 37) and the
sweep-two revisit order.  It is distinct from ``lean_intervention``
(singular), which holds the S0-02 data-contract checks and the constants
this module imports.

Every feasible triple is enumerated first, then sampled without replacement
with an RNG derived from the frozen split seed and the house id, each object
used at most once.  Never sample-then-retry: that would favour objects in
easily hidden places, which is selecting samples by how concealable they
are.  Input: the house's object table (pickupable, parent receptacle), the
maximum visible pixels per object in sweep one, the set U of containers
unobservable throughout the window and per-destination placement results.
No simulator is started and no image is read.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any, Mapping, Sequence

from cpmt.hashing import canonical_json
from vsmt.lean_intervention import (
    DRY_RUN_DESTINATIONS_PER_OBJECT,
    INTERVENTION_KINDS,
    MAXIMUM_INTERVENTIONS_PER_EPISODE,
    MIN_VISIBLE_PIXELS,
    P_NULL_WINDOW,
    RNG_PURPOSE_TAGS,
)


class LeanSelectionError(ValueError):
    """Raised for an inadmissible object table or an unregistered RNG tag."""


FLOOR_RECEPTACLE_ID = "Floor"


def parent_receptacle_of(parents: Sequence[str] | None) -> str | None:
    """The receptacle an object counts as sitting in or on (ruling 52).

    AI2-THOR's ``parentReceptacles`` lists every receptacle whose trigger box holds the object and
    puts the room ``Floor`` first for anything on low furniture (sofa, TV stand, side table,
    shelving unit, dining table).  Taking entry 0 attributed 99 of the 987 eligible objects of the
    7c10d2c development run to the floor, so they could never be a remove/move source or a control
    holder (LOG-243 supplement).  The first non-Floor entry is the receptacle; an object listed only
    under Floor sits on the floor and has no container; an empty list has none either.  Returns a
    receptacle id or None (the object is then not eligible); visibility and U are not touched.
    """

    for parent in parents or []:
        if parent != FLOOR_RECEPTACLE_ID:
            return str(parent)
    return None


def derive_rng(split_seed: int, house_id: str, purpose: str, private_salt: str | None = None) -> random.Random:
    """A Random seeded from (split seed, house id, purpose tag) and, for the null draw only, a private salt.

    No new seed is introduced: the same house draws the same interventions on
    every machine, and each registered purpose tag gives a separate stream; an
    unregistered tag raises.  The null-window draw (ruling 37) is the one
    exception: the seed is in the public contract and the house id is the
    directory name, so both are known, and a private salt kept outside the
    repository is mixed in; provenance records only the salt's sha256.
    """

    if purpose not in RNG_PURPOSE_TAGS:
        raise LeanSelectionError(f"rng_purpose_not_registered:{purpose}")
    if (purpose == "null_window") != (private_salt is not None):
        raise LeanSelectionError("private_salt_is_required_for_null_window_and_forbidden_elsewhere")
    parts: list[Any] = [split_seed, house_id, purpose]
    if private_salt is not None:
        if type(private_salt) is not str or len(private_salt) < 32:
            raise LeanSelectionError("private_salt_must_be_a_string_of_at_least_32_characters")
        parts.append(private_salt)
    digest = hashlib.sha256(canonical_json(parts).encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


def is_null_window(split_seed: int, house_id: str, private_salt: str) -> bool:
    """Whether this episode executes zero interventions by design (p = 0.2), salted (ruling 37)."""

    return derive_rng(split_seed, house_id, "null_window", private_salt).random() < P_NULL_WINDOW


def select_controls(
    eligible: Sequence[Mapping[str, Any]], receptacles: Sequence[str], invisible_containers: set[str],
    interventions: Sequence[Mapping[str, Any]], *, split_seed: int, house_id: str,
) -> dict[str, Any]:
    """The unintervened control containers sweep two revisits (ruling 34, twin control).

    If sweep two revisited only intervened containers, "revisited implies
    changed" would be a perfect structural shortcut.  One control is drawn per
    intervened container, without replacement and with the derived RNG, from U
    minus the intervened set, restricted to containers holding at least one
    eligible object seen in sweep one; only when U runs short are holders
    outside U added, and their number is recorded.  Nothing changes on a
    control, so revisiting it tests "unchanged must not be retracted".  A null
    window episode passes the interventions it would have executed.  Returns
    the controls, source counts and the shortfall.  Empty containers are never
    controls (revisiting an empty drawer tests nothing).
    """

    involved: set[str] = set()
    for row in interventions:
        for key in ("source", "destination"):
            if row.get(key):
                involved.add(row[key])
    holders: dict[str, list[str]] = {}
    for obj in eligible:
        holders.setdefault(obj["parent_receptacle"], []).append(obj["object_id"])
    intervened = sorted({c for c in involved if c in set(receptacles)})
    wanted = len({row.get("destination") or row.get("source") for row in interventions if row.get("kind")}
                 | {row["source"] for row in interventions if row.get("kind") == "move"})
    inside = [c for c in sorted(receptacles) if c in invisible_containers and c not in involved and holders.get(c)]
    outside = [c for c in sorted(receptacles) if c not in invisible_containers and c not in involved and holders.get(c)]
    rng = derive_rng(split_seed, house_id, "control_revisit")
    chosen: list[dict[str, Any]] = []
    pool = list(inside)
    while pool and len(chosen) < wanted:
        c = pool.pop(rng.randrange(len(pool)))
        chosen.append({"container": c, "from_U": True, "seen_objects": sorted(holders[c])})
    pool = list(outside)
    while pool and len(chosen) < wanted:
        c = pool.pop(rng.randrange(len(pool)))
        chosen.append({"container": c, "from_U": False, "seen_objects": sorted(holders[c])})
    return {"controls": chosen, "wanted": wanted, "intervened_containers": intervened,
            "from_U": sum(1 for c in chosen if c["from_U"]), "from_outside_U": sum(1 for c in chosen if not c["from_U"]),
            "shortfall": wanted - len(chosen), "candidates_in_U": len(inside), "candidates_outside_U": len(outside)}


def eligible_objects(
    objects: Sequence[Mapping[str, Any]],
    visible_pixels: Mapping[str, int],
) -> list[dict[str, Any]]:
    """Objects that may be intervened on.

    Eligible: pickupable, in or on a receptacle, at least 196 visible pixels in
    some sweep-one frame, and neither the agent nor a structure.  Returns the
    eligible objects sorted by id.  An object never seen has no entity in
    memory, so changing it would test nothing.
    """

    out: list[dict[str, Any]] = []
    for obj in objects:
        if not obj.get("pickupable"):
            continue
        if obj.get("parent_receptacle") is None:
            continue
        if obj.get("is_agent") or obj.get("is_structure"):
            continue
        if visible_pixels.get(obj["object_id"], 0) < MIN_VISIBLE_PIXELS:
            continue
        out.append(dict(obj))
    return sorted(out, key=lambda o: o["object_id"])


def unseen_objects(objects: Sequence[Mapping[str, Any]], visible_pixels: Mapping[str, int]) -> list[dict[str, Any]]:
    """Pickupable objects on a receptacle that have never been rendered so far (0 px).

    Ruling 30 (adopted): the ``add`` source is a real object of the house that
    has never appeared in any private mask, relocated onto a U container,
    instead of a copy of a seen object.  For the memory it is a new entity
    (BIRTH), and as a real prefab it is registered by instance segmentation.
    Returns the 0-px objects sorted by id; a single visible pixel counts as
    seen.
    """

    out: list[dict[str, Any]] = []
    for obj in objects:
        if not obj.get("pickupable") or obj.get("parent_receptacle") is None:
            continue
        if obj.get("is_agent") or obj.get("is_structure"):
            continue
        if visible_pixels.get(obj["object_id"], 0) > 0:
            continue
        out.append(dict(obj))
    return sorted(out, key=lambda o: o["object_id"])


def feasible_triples(
    eligible: Sequence[Mapping[str, Any]],
    receptacles: Sequence[str],
    invisible_containers: set[str],
    placement_ok: Mapping[str, bool],
    unseen: Sequence[Mapping[str, Any]] | None = None,
    pair_ok: Mapping[tuple[str, str], Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Every (object, kind, ...) whose involved containers are all in U.

    With U fixed for the window: ``remove`` needs the source in U; ``move``
    needs source and destination in U, a destination that accepts the object
    and differs from the source; ``add`` needs a destination in U that accepts
    the object (a copy of an eligible object when ``unseen`` is None, otherwise
    an unseen existing object, ruling 30).  Returns the feasible list F in a
    deterministic order; sampling draws only from F.
    """

    out: list[dict[str, Any]] = []
    sorted_receptacles = sorted(receptacles)
    for obj in eligible:
        src = obj["parent_receptacle"]
        oid = obj["object_id"]
        if src in invisible_containers:
            out.append({"kind": "remove", "object_id": oid, "asset_id": obj.get("asset_id"),
                        "source": src, "destination": None})
        for dst in sorted_receptacles:
            if dst not in invisible_containers or not placement_ok.get(dst, False):
                continue
            if dst != src and src in invisible_containers:
                out.append({"kind": "move", "object_id": oid, "asset_id": obj.get("asset_id"),
                            "source": src, "destination": dst})
            if unseen is None:
                out.append({"kind": "add", "object_id": oid, "asset_id": obj.get("asset_id"),
                            "source": None, "destination": dst})
    if unseen is not None:
        for obj in unseen:
            for dst in sorted_receptacles:
                if dst not in invisible_containers or not placement_ok.get(dst, False) or dst == obj["parent_receptacle"]:
                    continue
                out.append({"kind": "add", "object_id": obj["object_id"], "asset_id": obj.get("asset_id"),
                            "source": obj["parent_receptacle"], "destination": dst, "add_source": "unseen_existing"})
    if pair_ok is not None:
        # dry-run prescreen (ruling 31, adopted): a move/add is feasible only if the simulator
        # actually placed the object there and it was visible from the destination's viewpoint
        kept = []
        for row in out:
            if row["kind"] == "remove":
                kept.append(row); continue
            hit = pair_ok.get((row["object_id"], row["destination"]))
            if hit is None:
                continue
            kept.append({**row, "point": hit["point"], "verified_pixels": hit["pixels"], "dry_run_tries": hit["tries"]})
        out = kept
    for t in out:
        if t["kind"] not in INTERVENTION_KINDS:
            raise LeanSelectionError("unregistered_kind")
    return out


def dry_run_destinations(
    candidates: Sequence[Mapping[str, Any]], invisible_containers: set[str], *, split_seed: int, house_id: str,
    per_object: int = DRY_RUN_DESTINATIONS_PER_OBJECT,
) -> dict[str, list[str]]:
    """Which U destinations the dry run tests for each candidate object (ruling 39, m=8).

    The dry run costs candidates x |U| x at most 32 points.  Since ruling 39 each candidate object
    tests at most m destinations drawn from U with the derived RNG (tag ``dry_run_order``), its own
    container excluded.  The tested subset is uniformly random, so every truly feasible
    (object, destination) pair has the same chance and sampling stays fair; the cost is that the
    feasible set covers only the tested pairs, so the receipt records pairs_tested and pairs_total.
    m = 0 tests every destination and exists only to replay the 50 S1 episodes.  Returns objects in
    id order, each with its destinations in draw order.
    """

    if type(per_object) is not int or per_object < 0:
        raise LeanSelectionError("dry_run_destinations_per_object_invalid")
    rng = derive_rng(split_seed, house_id, "dry_run_order")
    out: dict[str, list[str]] = {}
    for obj in sorted(candidates, key=lambda o: o["object_id"]):
        pool = [c for c in sorted(invisible_containers) if c != obj.get("parent_receptacle")]
        if per_object and len(pool) > per_object:
            chosen = []
            for _ in range(per_object):
                chosen.append(pool.pop(rng.randrange(len(pool))))
            out[obj["object_id"]] = chosen
        else:
            rng.shuffle(pool)
            out[obj["object_id"]] = pool
    return out


def sample_interventions(
    feasible: Sequence[Mapping[str, Any]], *, split_seed: int, house_id: str,
    maximum: int = MAXIMUM_INTERVENTIONS_PER_EPISODE, stratify_by_kind: bool = True,
    one_placement_per_destination: bool = True,
) -> list[dict[str, Any]]:
    """Draw up to ``maximum`` triples without replacement, one object at most once.

    Draws from F with the derived RNG; a drawn object is never drawn again (copying it in an
    ``add`` counts as using it).  Returns the indexed interventions; a copy's new id is derived from
    (house, object, index).

    ``stratify_by_kind`` (ruling 29, adopted, on by default): each slot first draws a kind uniformly
    among the kinds with triples left, then a triple uniformly within that kind.  Off reproduces the
    first S1-02b run's uniform draw over triples, in which ``add`` was nearly always drawn because
    it has the most triples; it is kept only to replay old runs.
    ``one_placement_per_destination`` (ruling 32, adopted, on by default): at most one placement per
    destination container per episode; ``remove`` is unlimited.
    """

    rng = derive_rng(split_seed, house_id, "intervention")
    pool = list(feasible)
    chosen: list[dict[str, Any]] = []
    used: set[str] = set()
    placed: set[str] = set()
    while pool and len(chosen) < maximum:
        if one_placement_per_destination:
            pool = [t for t in pool if t["kind"] == "remove" or t["destination"] not in placed]
            if not pool:
                break
        if stratify_by_kind:
            pool = [t for t in pool if t["object_id"] not in used]
            if not pool:
                break
            kinds = sorted({t["kind"] for t in pool})
            kind = kinds[rng.randrange(len(kinds))]
            of_kind = [i for i, t in enumerate(pool) if t["kind"] == kind]
            pick = pool.pop(of_kind[rng.randrange(len(of_kind))])
        else:
            pick = pool.pop(rng.randrange(len(pool)))
        if pick["object_id"] in used:
            continue
        used.add(pick["object_id"])
        if pick["kind"] != "remove":
            placed.add(pick["destination"])
        row = dict(pick)
        row["index"] = len(chosen)
        if row["kind"] == "add" and row.get("add_source") != "unseen_existing":
            tag = hashlib.sha256(canonical_json([house_id, row["object_id"], row["index"]]).encode("utf-8")).hexdigest()[:12]
            row["generated_id"] = f"dup_{tag}"
        chosen.append(row)
    return chosen


def revisit_sequence(
    interventions: Sequence[Mapping[str, Any]], *, split_seed: int, house_id: str,
    controls: Sequence[str] = (),
) -> list[str]:
    """Containers sweep two revisits, in order; move's two ends ordered by RNG; controls interleaved.

    ``remove`` revisits the source, ``add`` the destination, ``move`` both ends,
    source or destination first decided per move by the derived RNG; a repeated
    container keeps only its first occurrence.  The control containers (ruling
    34) are then inserted one by one at random positions from the same stream,
    so the order carries no "changed first, unchanged later" signal.
    """

    rng = derive_rng(split_seed, house_id, "revisit_order")
    seq: list[str] = []
    for row in interventions:
        if row["kind"] == "remove":
            ends = [row["source"]]
        elif row["kind"] == "add":
            ends = [row["destination"]]
        else:
            ends = [row["source"], row["destination"]]
            if rng.random() < 0.5:
                ends.reverse()
        for c in ends:
            if c not in seq:
                seq.append(c)
    for c in controls:
        if c in seq:
            raise LeanSelectionError(f"control_is_also_intervened:{c}")
        seq.insert(rng.randrange(len(seq) + 1), c)
    return seq


__all__ = [
    "LeanSelectionError",
    "derive_rng",
    "dry_run_destinations",
    "eligible_objects",
    "feasible_triples",
    "is_null_window",
    "revisit_sequence",
    "sample_interventions",
    "select_controls",
]
