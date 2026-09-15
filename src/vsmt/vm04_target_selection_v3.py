"""Proposed VM-04 v3 private target selection for a fixed pose only."""

from __future__ import annotations

import hashlib
from typing import Any, Mapping

from cpmt.hashing import canonical_json

from .vm04_target_eligibility import asset_target_profiles


LIFECYCLE_PROGRAMS = frozenset({"BIRTH", "REACTIVATE", "RETRACT", "REPLACE"})
TWO_TARGET_PROGRAMS = frozenset({"SPLIT", "REPLACE"})
PROGRAMS = frozenset({"NOOP", "BIND", "BIRTH", "REACTIVATE", "RELINK",
                      "RETRACT", "SPLIT", "MERGE", "REPLACE"})
MINIMUM_MASK_PIXELS = 196


def rank_visible_assets_by_geometry(
    instance_masks: Mapping[str, Any], authored_ids: frozenset[str],
) -> list[str]:
    """Use mask geometry only; refuse indistinguishable ties instead of ID sort."""
    keys: dict[tuple[int, int, str], str] = {}
    shape = None
    for object_id, raw in instance_masks.items():
        if object_id not in authored_ids:
            continue
        rows = raw.tolist() if hasattr(raw, "tolist") else raw
        if type(rows) is not list or not rows or any(type(row) is not list for row in rows):
            raise ValueError("asset instance mask must be a 2D array")
        width = len(rows[0])
        if width == 0 or any(len(row) != width for row in rows):
            raise ValueError("asset instance mask is not rectangular")
        current_shape = (len(rows), width)
        if shape is not None and current_shape != shape:
            raise ValueError("asset instance masks have inconsistent shapes")
        shape = current_shape
        flat = []
        for row in rows:
            for value in row:
                if type(value) is bool:
                    flat.append(int(value))
                elif type(value) is int and value in (0, 1):
                    flat.append(value)
                else:
                    raise ValueError("asset mask contains nonbinary pixels")
        support = sum(flat)
        if support < MINIMUM_MASK_PIXELS:
            continue
        first = flat.index(1)
        digest = hashlib.sha256(
            canonical_json([*current_shape, *flat]).encode("utf-8")
        ).hexdigest()
        key = (first, support, digest)
        if key in keys:
            raise ValueError("two asset masks have indistinguishable public geometry")
        keys[key] = object_id
    return [keys[key] for key in sorted(keys)]


def select_private_targets_at_fixed_pose(
    program: str, instance_masks: Mapping[str, Any],
    current_metadata_objects: Mapping[str, Mapping[str, Any]],
    authored_ids: frozenset[str], *,
    static_authored_asset_lifecycle_policy: str,
    relink_requires_moveable_or_pickupable: bool,
) -> list[str]:
    """Filter the frozen geometry order in private construction; never choose pose.

    The policy parameters must be explicitly frozen by the user before a
    simulator probe or episode calls this function. A shortage is a hard
    construction failure for the original fixed slot.
    """
    if program not in PROGRAMS:
        raise ValueError("unknown VM-04 program")
    if static_authored_asset_lifecycle_policy not in (
        "allow_visibility_lifecycle_if_simulator_action_and_poststate_verified",
        "exclude_static_assets_from_physical_lifecycle_targets",
    ):
        raise ValueError("static authored-asset lifecycle policy is unresolved")
    if relink_requires_moveable_or_pickupable is not True:
        raise ValueError("physical RELINK requires explicit movable-asset gate")
    ranked_visible_ids = rank_visible_assets_by_geometry(instance_masks, authored_ids)
    profiles = asset_target_profiles(ranked_visible_ids,
                                     current_metadata_objects, authored_ids)
    if program == "RELINK" or (program in LIFECYCLE_PROGRAMS and
        static_authored_asset_lifecycle_policy ==
            "exclude_static_assets_from_physical_lifecycle_targets"
    ):
        qualified = profiles["movable_asset"]
    else:
        qualified = profiles["authored_asset"]
    required = 2 if program in TWO_TARGET_PROGRAMS else 1
    if len(qualified) < required:
        raise ValueError("original fixed slot has insufficient qualified assets")
    return qualified[:required]
