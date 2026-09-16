"""Build VM-04 public packets and their causal prior in one sealed sequence.

The input rows contain only values produced by the public front end or frozen
public constants.  The prior-memory reference is deliberately absent from the
input: this module derives it from the memory produced by the preceding row.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from cpmt.executor import validate_graph
from cpmt.hashing import clone_json

from .causal_prior import (
    PublicBootstrapConfig,
    advance_public_bootstrap,
    build_causal_prior,
    empty_public_memory,
)
from .contracts import validate_observation_packet


PUBLIC_FRONTEND_ROW_KEYS = {
    "sample_id_hash",
    "decision_time_s",
    "rgbd_refs",
    "camera_pose",
    "robot_state",
    "past_actions",
    "region_observations",
    "relation_observations",
    "free_space_observations",
    "visibility_observations",
    "public_constants",
}


def _validated_memory(memory: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(memory, Mapping):
        raise ValueError("prior_memory must be an object")
    result = clone_json(dict(memory))
    validate_graph(result, verify_hash=True)
    graph_hash = result.get("graph_hash")
    graph_version = result.get("graph_version")
    if type(graph_hash) is not str or len(graph_hash) != 64:
        raise ValueError("prior_memory must carry a sealed graph_hash")
    if type(graph_version) is not str or not graph_version:
        raise ValueError("prior_memory must carry a graph_version")
    return result


def make_public_packet(
    frontend_row: Mapping[str, Any], prior_memory: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind one exact public-front-end row to the preceding sealed memory."""

    if not isinstance(frontend_row, Mapping):
        raise ValueError("public front-end row must be an object")
    keys = set(frontend_row)
    if keys != PUBLIC_FRONTEND_ROW_KEYS:
        raise ValueError(
            "public front-end row must contain exactly "
            f"{sorted(PUBLIC_FRONTEND_ROW_KEYS)}"
        )
    memory = _validated_memory(prior_memory)
    packet = clone_json(dict(frontend_row))
    packet["schema_version"] = "vsmt-observation-packet-v3"
    packet["prior_memory_ref"] = {
        "graph_version": memory["graph_version"],
        "graph_sha256": memory["graph_hash"],
    }
    return validate_observation_packet(packet)


def build_public_packet_sequence(
    frontend_rows: Sequence[Mapping[str, Any]], *,
    bootstrap_config: PublicBootstrapConfig,
    builder_code_sha256: str,
) -> dict[str, Any]:
    """Build packets online, then independently replay them for a receipt."""

    if isinstance(frontend_rows, (str, bytes)) or not isinstance(
        frontend_rows, Sequence,
    ):
        raise ValueError("frontend_rows must be an ordered sequence")

    memory = empty_public_memory()
    packets: list[dict[str, Any]] = []
    previous_time = -math.inf
    for frontend_row in frontend_rows:
        packet = make_public_packet(frontend_row, memory)
        decision_time = float(packet["decision_time_s"])
        if decision_time < previous_time:
            raise ValueError(
                "public front-end rows must be ordered by decision_time_s"
            )
        previous_time = decision_time
        result = advance_public_bootstrap(
            packet, memory, config=bootstrap_config,
        )
        memory = clone_json(result["post_memory"])
        packets.append(packet)

    replay = build_causal_prior(
        packets,
        config=bootstrap_config,
        builder_code_sha256=builder_code_sha256,
    )
    if replay["prior_memory"] != memory:
        raise ValueError("online public memory differs from independent replay")
    return {
        "public_packets": clone_json(packets),
        "prior_memory": clone_json(memory),
        "causal_prior_receipt": clone_json(replay["receipt"]),
    }
