"""Proposed VM-04 v3 private target selection for a fixed pose only."""

from __future__ import annotations

import hashlib
from typing import Any, Mapping

from cpmt.hashing import canonical_json

from .vm04_target_contract import validate_target_boundary_proposal
from .vm04_target_eligibility import asset_target_profiles


def rank_visible_assets_by_geometry(
    instance_masks: Mapping[str, Any], authored_ids: frozenset[str], *,
    minimum_mask_pixels: int,
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
        if support < minimum_mask_pixels:
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
    contract: Mapping[str, Any],
) -> list[str]:
    """Filter the frozen geometry order in private construction; never choose pose.

    The validated contract is the only source for eligibility/program values.
    This pure function does not authorize a simulator probe or generation.
    A shortage is a hard construction failure for the original fixed slot.
    """
    policy = validate_target_boundary_proposal(contract)
    if policy["status"] not in ("approved_semantics_implementation_only",
                                "frozen_target_probe_only"):
        raise ValueError("v3 target semantics have not been approved")
    if program not in policy["physical_intervention_programs"]:
        raise ValueError("program has no physical intervention target")
    # The trusted author/metadata/finite-position intersection precedes rank.
    eligible = asset_target_profiles(list(instance_masks),
                                     current_metadata_objects, authored_ids)[
                                         "authored_asset"]
    ranked_visible_ids = rank_visible_assets_by_geometry(
        instance_masks, frozenset(eligible),
        minimum_mask_pixels=policy["minimum_mask_pixels"])
    profiles = asset_target_profiles(ranked_visible_ids,
                                     current_metadata_objects, authored_ids)
    if program == "RELINK":
        qualified = profiles["movable_asset"]
    else:
        qualified = profiles["authored_asset"]
    required = (policy["minimum_qualified_visible_assets_for_replace"]
                if program == "REPLACE" else 1)
    if len(qualified) < required:
        raise ValueError("original fixed slot has insufficient qualified assets")
    return qualified[:required]
