"""Proposed VM-04 v3 private target selection for a fixed pose only."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .vm04_target_eligibility import asset_target_profiles


LIFECYCLE_PROGRAMS = frozenset({"BIRTH", "REACTIVATE", "RETRACT", "REPLACE"})
TWO_TARGET_PROGRAMS = frozenset({"SPLIT", "REPLACE"})
PROGRAMS = frozenset({"NOOP", "BIND", "BIRTH", "REACTIVATE", "RELINK",
                      "RETRACT", "SPLIT", "MERGE", "REPLACE"})


def select_private_targets_at_fixed_pose(
    program: str, ranked_visible_ids: Sequence[str],
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
