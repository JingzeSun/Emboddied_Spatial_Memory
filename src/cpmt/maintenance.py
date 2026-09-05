"""Deterministic lifecycle maintenance outside CTL candidate competition.

白话：这个模块只把长期没看到的 confirmed entity 放入 dormant；
它不表示对象消失，也不删除任何身份、latent、evidence 或历史版本。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping

from .errors import ContractError, DuplicateTransactionError
from .executor import validate_graph
from .hashing import compute_graph_hash


def apply_dormancy_maintenance(
    base_graph: dict[str, Any],
    *,
    at: int,
    inactivity_horizon: int,
    last_seen_by_node: Mapping[str, int],
    maintenance_id: str,
    eligible_node_types: Iterable[str] = ("entity",),
) -> dict[str, Any]:
    """Close stale confirmed versions and open traceable dormant versions."""

    validate_graph(base_graph)
    if at < 0:
        raise ContractError("maintenance time must be non-negative")
    if inactivity_horizon <= 0:
        raise ContractError("inactivity_horizon must be positive")
    event_id = f"maintenance:{maintenance_id}"
    if event_id in base_graph["transaction_log"]:
        raise DuplicateTransactionError(
            f"maintenance event {event_id!r} is already committed"
        )

    eligible_types = set(eligible_node_types)
    working = deepcopy(base_graph)
    working["graph_hash"] = None
    transitioned = 0

    for node in list(working["nodes"]):
        if node.get("valid_to") is not None:
            continue
        if node["lifecycle"] != "confirmed":
            continue
        if node["node_type"] not in eligible_types:
            continue
        last_seen = last_seen_by_node.get(node["node_id"])
        if last_seen is None:
            continue
        if last_seen < 0 or last_seen > at:
            raise ContractError(
                f"invalid last_seen={last_seen} for {node['node_id']!r}"
            )
        if at - last_seen < inactivity_horizon:
            continue

        node["valid_to"] = at
        if event_id not in node["provenance"]:
            node["provenance"].append(event_id)
        dormant = deepcopy(node)
        dormant["node_version_id"] = (
            f"{node['node_id']}@dormant-{at}"
        )
        dormant["lifecycle"] = "dormant"
        dormant["valid_from"] = at
        dormant["valid_to"] = None
        dormant["predecessor_ids"] = [
            node["node_version_id"]
        ]
        dormant["provenance"] = [event_id]
        working["nodes"].append(dormant)
        transitioned += 1

    if transitioned == 0:
        result = deepcopy(base_graph)
        result["graph_hash"] = compute_graph_hash(result)
        return result

    working["parent_version"] = base_graph["graph_version"]
    working["graph_version"] = (
        f"{base_graph['graph_version']}::{event_id}"
    )
    working["transaction_log"].append(event_id)
    working["graph_hash"] = compute_graph_hash(working)
    validate_graph(working)
    return working
