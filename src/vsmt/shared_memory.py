"""Method-independent place and dormancy preparation for VSMT comparisons.

白话：这个包装在五个方法运行前逐字节相同地更新地点证据，并把长期没有
公开重观测的 confirmed entity 置为 dormant。它不表示实体已经消失，也不
读取 teacher、future 或 private 数据。
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

from cpmt.hashing import clone_json

from .contracts import build_adapter_input, canonical_sha256, validate_observation_packet
from .graph_ops import GraphRevision, observation_state, open_nodes
from .place_scaffold import prepare_place_scaffold


SHARED_MAINTENANCE_ID = "vsmt.shared.dormancy.v1"


@dataclass(frozen=True)
class SharedMemoryConfig:
    """All scientific values are explicit; no dormancy horizon is implicit."""

    dormancy_inactivity_horizon_s: float

    def __post_init__(self) -> None:
        value = self.dormancy_inactivity_horizon_s
        if (
            type(value) not in {int, float}
            or not math.isfinite(float(value))
            or float(value) <= 0.0
        ):
            raise ValueError("dormancy_inactivity_horizon_s must be positive")


def prepare_shared_memory(
    packet: Mapping[str, Any],
    prior_memory: Mapping[str, Any],
    *,
    config: SharedMemoryConfig,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Return one shared packet/memory pair and a public preparation audit."""

    prepared, scaffold_memory = prepare_place_scaffold(packet, prior_memory)
    model_input = build_adapter_input(prepared, scaffold_memory)
    decision_time_s = float(model_input["decision_time_s"])
    revision = GraphRevision(scaffold_memory, method_id=SHARED_MAINTENANCE_ID)
    dormant_node_ids: list[str] = []
    for node in sorted(open_nodes(revision.graph), key=lambda item: str(item["node_id"])):
        if node.get("node_type") != "entity" or node.get("lifecycle") != "confirmed":
            continue
        state = observation_state(node)
        if state is None:
            continue
        last_seen_s = state.get("last_seen_s")
        if (
            type(last_seen_s) not in {int, float}
            or not math.isfinite(float(last_seen_s))
            or float(last_seen_s) > decision_time_s
        ):
            raise ValueError("confirmed entity has invalid public last_seen_s")
        if (
            decision_time_s - float(last_seen_s)
            < float(config.dormancy_inactivity_horizon_s)
        ):
            continue
        revision.lifecycle_node(
            node,
            lifecycle="dormant",
            template=None,
            state_updates={"dormancy_started_s": decision_time_s},
        )
        dormant_node_ids.append(str(node["node_id"]))

    result = revision.finish(
        confidence=1.0,
        runtime_ms=0.0,
        diagnostics={"dormant_node_ids": dormant_node_ids},
    )
    memory = result["post_memory"]
    final_packet = clone_json(prepared)
    final_packet["prior_memory_ref"] = {
        "graph_version": memory["graph_version"],
        "graph_sha256": memory["graph_hash"],
    }
    validated = validate_observation_packet(final_packet)
    audit = {
        "schema_version": "vsmt-shared-memory-audit-v1",
        "input_pre_memory_sha256": prior_memory["graph_hash"],
        "place_scaffold_post_memory_sha256": scaffold_memory["graph_hash"],
        "post_memory_sha256": memory["graph_hash"],
        "dormancy_inactivity_horizon_s": float(
            config.dormancy_inactivity_horizon_s
        ),
        "dormant_node_ids": dormant_node_ids,
    }
    audit["audit_sha256"] = canonical_sha256(audit)
    return validated, memory, audit
