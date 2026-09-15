"""Trusted VM-04 construction boundary between authored assets and architecture.

This module may run only in the private simulator/generator process. It never
creates a deployment ObservationPacket or candidate and never chooses a pose.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence


def authored_asset_ids(house: Mapping[str, Any]) -> frozenset[str]:
    """Collect author-train ``house.objects`` IDs, including nested children."""
    if type(house) is not dict or type(house.get("objects")) is not list:
        raise ValueError("house.objects must be an author asset list")
    seen: set[str] = set()

    def collect(rows: Sequence[Any]) -> None:
        for row in rows:
            if type(row) is not dict or type(row.get("id")) is not str or not row["id"]:
                raise ValueError("author asset has no stable string ID")
            object_id = row["id"]
            if object_id in seen:
                raise ValueError("duplicate author asset ID")
            seen.add(object_id)
            children = row.get("children", [])
            if type(children) is not list:
                raise ValueError("author asset children must be a list")
            collect(children)

    collect(house["objects"])
    if not seen:
        raise ValueError("author house has no assets")
    architecture_ids = set()
    for name in ("walls", "doors", "windows", "rooms"):
        rows = house.get(name, [])
        if type(rows) is not list:
            raise ValueError("author architecture must be a list")
        architecture_ids.update(
            row["id"] for row in rows
            if type(row) is dict and type(row.get("id")) is str
        )
    if seen & architecture_ids:
        raise ValueError("author asset and architecture IDs overlap")
    return frozenset(seen)


def asset_target_profiles(
    ranked_visible_ids: Sequence[str], metadata_objects: Mapping[str, Mapping[str, Any]],
    author_asset_ids: frozenset[str],
) -> dict[str, list[str]]:
    """Keep geometry order; return two private, program-independent profiles.

    ``authored_asset`` includes static furniture/decor. ``movable_asset`` also
    requires AI2-THOR moveable or pickupable. Both need a real metadata pose.
    Neither is approved as the formal generation rule by this helper.
    """
    if len(ranked_visible_ids) != len(set(ranked_visible_ids)):
        raise ValueError("ranked visible IDs must be unique")
    assets: list[str] = []
    movable: list[str] = []
    for object_id in ranked_visible_ids:
        if object_id not in author_asset_ids:
            continue
        row = metadata_objects.get(object_id)
        if type(row) is not dict or type(row.get("position")) is not dict or not all(
            type(row["position"].get(axis)) in (int, float) and
            math.isfinite(row["position"][axis]) for axis in ("x", "y", "z")
        ):
            continue
        assets.append(object_id)
        if row.get("moveable") is True or row.get("pickupable") is True:
            movable.append(object_id)
    return {"authored_asset": assets, "movable_asset": movable}
