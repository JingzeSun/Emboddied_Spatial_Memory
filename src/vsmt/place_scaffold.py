"""Deterministic coordinate-defined place scaffold shared by every method."""

from __future__ import annotations

from typing import Any, Mapping

from cpmt.hashing import clone_json

from .contracts import build_adapter_input, validate_observation_packet
from .graph_ops import (
    GraphRevision,
    PLACE_SCAFFOLD_ID,
    observation_state,
    place_scaffold_key,
)


def prepare_place_scaffold(
    packet: Mapping[str, Any], prior_memory: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Advance public place versions before any method-specific decision."""

    public = validate_observation_packet(packet)
    model_input = build_adapter_input(public, prior_memory)
    places = [
        region for region in model_input["region_observations"]
        if region["structure_kind"] == "place"
    ]
    revision = GraphRevision(prior_memory, method_id=PLACE_SCAFFOLD_ID)
    for region in places:
        revision.upsert_place_scaffold(
            region, float(model_input["decision_time_s"]),
        )
    result = revision.finish(
        confidence=1.0,
        runtime_ms=0.0,
        diagnostics={"place_scaffold_regions": len(places)},
    )
    memory = result["post_memory"]
    prepared = clone_json(public)
    prepared["prior_memory_ref"] = {
        "graph_version": memory["graph_version"],
        "graph_sha256": memory["graph_hash"],
    }
    return validate_observation_packet(prepared), memory


def place_region_node_ids(
    regions: list[Mapping[str, Any]], memory: Mapping[str, Any],
) -> dict[str, str]:
    """Bind current place ordinals only to the matching public scaffold nodes."""

    by_key: dict[str, str] = {}
    for node in memory["nodes"]:
        state = observation_state(node)
        if (
            node.get("valid_to") is None
            and node.get("node_type") == "place"
            and state is not None
            and type(state.get("place_scaffold_key")) is str
        ):
            key = state["place_scaffold_key"]
            if key in by_key:
                raise ValueError("place scaffold key has multiple open node identities")
            by_key[key] = str(node["node_id"])
    result: dict[str, str] = {}
    for region in regions:
        if region["structure_kind"] != "place":
            continue
        key = place_scaffold_key(region)
        if key not in by_key:
            raise ValueError("place region is missing its deterministic scaffold node")
        result[str(region["region_id"])] = by_key[key]
    return result
