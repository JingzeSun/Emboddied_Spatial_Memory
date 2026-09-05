"""Conservative equality for counterfactual post-edit memory states.

Equivalence removes only representational nuisance: permitted identity
renaming, audit IDs and order-insensitive serialization. It never merges
states merely because finite-horizon projections happen to look similar.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from .errors import ContractError, PreconditionError
from .executor import validate_graph
from .hashing import canonical_json
from .pending import validate_pending_store


SCHEMA_VERSION = "cpmt-0.2"
POLICY_KEYS = {
    "schema_version",
    "policy_id",
    "base_graph_version",
    "fixed_identity_ids",
    "exchangeable_identity_sets",
    "externally_anchored_new_ids",
    "raw_latent_exact_match",
    "comparison_mode",
    "future_projection_defines_equivalence",
}


def _stable_identity_ids(graph: dict[str, Any]) -> set[str]:
    return {node["node_id"] for node in graph["nodes"]}


def _validate_policy(
    base_graph: dict[str, Any],
    policy: Mapping[str, Any],
) -> tuple[set[str], list[set[str]], set[str]]:
    if set(policy) != POLICY_KEYS:
        raise ContractError(
            "equivalence policy fields do not match cpmt-0.2"
        )
    if policy["schema_version"] != SCHEMA_VERSION:
        raise ContractError("unsupported equivalence policy schema")
    if not policy["policy_id"]:
        raise ContractError("equivalence policy_id must be non-empty")
    if policy["base_graph_version"] != base_graph["graph_version"]:
        raise PreconditionError(
            "equivalence policy targets a different base version"
        )
    if policy["raw_latent_exact_match"] is not False:
        raise ContractError(
            "D-024 forbids raw-latent exact equality as identity rule"
        )
    if policy["comparison_mode"] != "canonical_memory_state":
        raise ContractError(
            "D-025 requires conservative canonical memory-state equality"
        )
    if policy["future_projection_defines_equivalence"] is not False:
        raise ContractError(
            "D-025 forbids future projection from defining equivalence"
        )

    base_ids = _stable_identity_ids(base_graph)
    fixed = set(policy["fixed_identity_ids"])
    if len(fixed) != len(policy["fixed_identity_ids"]):
        raise ContractError("fixed_identity_ids must be unique")
    if not fixed <= base_ids:
        raise ContractError(
            "fixed_identity_ids must already exist in the base"
        )

    groups: list[set[str]] = []
    grouped: set[str] = set()
    for raw_group in policy["exchangeable_identity_sets"]:
        group = set(raw_group)
        if len(group) != len(raw_group) or len(group) < 2:
            raise ContractError(
                "exchangeable sets need at least two unique IDs"
            )
        if not group <= base_ids:
            raise ContractError(
                "exchangeable old IDs must exist in the base"
            )
        if group & grouped:
            raise ContractError(
                "exchangeable identity sets must be disjoint"
            )
        if group & fixed:
            raise ContractError(
                "an identity cannot be both fixed and exchangeable"
            )
        groups.append(group)
        grouped.update(group)

    externally_anchored = set(
        policy["externally_anchored_new_ids"]
    )
    if len(externally_anchored) != len(
        policy["externally_anchored_new_ids"]
    ):
        raise ContractError(
            "externally_anchored_new_ids must be unique"
        )
    return fixed, groups, externally_anchored


def validate_identity_correspondence(
    base_graph: dict[str, Any],
    left_graph: dict[str, Any],
    right_graph: dict[str, Any],
    *,
    identity_mapping: Mapping[str, str],
    policy: Mapping[str, Any],
) -> None:
    """Validate a strict global bijection without comparing graph fields."""

    validate_graph(base_graph)
    validate_graph(left_graph)
    validate_graph(right_graph)
    fixed, exchangeable_groups, externally_anchored = (
        _validate_policy(base_graph, policy)
    )

    base_ids = _stable_identity_ids(base_graph)
    left_ids = _stable_identity_ids(left_graph)
    right_ids = _stable_identity_ids(right_graph)
    if not base_ids <= left_ids or not base_ids <= right_ids:
        raise PreconditionError(
            "post-worlds must preserve every base identity record"
        )
    if set(identity_mapping) != left_ids:
        raise ContractError(
            "identity mapping must cover every left stable ID exactly once"
        )
    mapped_ids = list(identity_mapping.values())
    if (
        len(mapped_ids) != len(set(mapped_ids))
        or set(mapped_ids) != right_ids
    ):
        raise ContractError(
            "identity mapping must be a bijection onto right stable IDs"
        )

    exchangeable_by_id = {
        identity_id: group
        for group in exchangeable_groups
        for identity_id in group
    }
    for identity_id in base_ids:
        target_id = identity_mapping[identity_id]
        group = exchangeable_by_id.get(identity_id)
        if group is None:
            if target_id != identity_id:
                raise ContractError(
                    f"anchored old identity {identity_id!r} must be fixed"
                )
        elif target_id not in group:
            raise ContractError(
                f"old identity {identity_id!r} may only permute "
                "within its declared exchangeable set"
            )

    left_new = left_ids - base_ids
    right_new = right_ids - base_ids
    if {
        identity_mapping[identity_id]
        for identity_id in left_new
    } != right_new:
        raise ContractError(
            "new identities may map only to new identities"
        )
    if not externally_anchored <= left_new & right_new:
        raise ContractError(
            "externally anchored new IDs must exist as new IDs "
            "in both post-worlds"
        )
    for identity_id in externally_anchored:
        if identity_mapping[identity_id] != identity_id:
            raise ContractError(
                f"externally anchored new identity "
                f"{identity_id!r} must be fixed"
            )


def _mapped_identity(
    identity_id: str | None,
    identity_mapping: Mapping[str, str],
) -> str | None:
    if identity_id is None:
        return None
    try:
        return identity_mapping[identity_id]
    except KeyError as error:
        raise ContractError(
            f"identity reference {identity_id!r} is not mapped"
        ) from error


def _semantic_provenance(
    values: list[str],
    transaction_ids: set[str],
) -> list[str]:
    """Keep source lineage but erase arbitrary committed transaction names."""

    semantic = {
        value for value in values if value not in transaction_ids
    }
    if any(value in transaction_ids for value in values):
        semantic.add("__committed_transaction__")
    return sorted(semantic)


def _node_version_tokens(
    graph: dict[str, Any],
    identity_mapping: Mapping[str, str],
) -> dict[str, str]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for node in graph["nodes"]:
        grouped.setdefault(node["node_id"], []).append(node)

    tokens: dict[str, str] = {}
    for source_id, versions in grouped.items():
        target_id = _mapped_identity(source_id, identity_mapping)
        ordered = sorted(
            versions,
            key=lambda node: (
                node["valid_from"],
                node.get("valid_to") is None,
                node.get("valid_to") or -1,
                node["lifecycle"],
                node["node_version_id"],
            ),
        )
        for index, node in enumerate(ordered):
            tokens[node["node_version_id"]] = (
                f"{target_id}::history::{index}"
            )
    return tokens


def _canonical_nodes(
    graph: dict[str, Any],
    identity_mapping: Mapping[str, str],
) -> list[dict[str, Any]]:
    transaction_ids = set(graph["transaction_log"])
    version_tokens = _node_version_tokens(graph, identity_mapping)
    canonical: list[dict[str, Any]] = []
    for node in graph["nodes"]:
        try:
            predecessors = sorted(
                version_tokens[value]
                for value in node.get("predecessor_ids", [])
            )
        except KeyError as error:
            raise ContractError(
                f"predecessor version {error.args[0]!r} is not present"
            ) from error
        canonical.append(
            {
                "identity": _mapped_identity(
                    node["node_id"], identity_mapping
                ),
                "version": version_tokens[node["node_version_id"]],
                "node_type": node["node_type"],
                "lifecycle": node["lifecycle"],
                "valid_from": node["valid_from"],
                "valid_to": node.get("valid_to"),
                "evidence_refs": sorted(node["evidence_refs"]),
                "latent_refs": sorted(node["latent_refs"]),
                "canonical_identity": _mapped_identity(
                    node.get("canonical_id"), identity_mapping
                ),
                "predecessor_versions": predecessors,
                "source_provenance": _semantic_provenance(
                    node["provenance"], transaction_ids
                ),
            }
        )
    return sorted(canonical, key=canonical_json)


def _canonical_edge_lineages(
    graph: dict[str, Any],
    identity_mapping: Mapping[str, str],
) -> list[list[dict[str, Any]]]:
    """Preserve fact-version grouping while ignoring local edge names."""

    transaction_ids = set(graph["transaction_log"])
    grouped: dict[str, list[dict[str, Any]]] = {}
    for edge in graph["edges"]:
        grouped.setdefault(edge["edge_id"], []).append(edge)

    lineages: list[list[dict[str, Any]]] = []
    for versions in grouped.values():
        normalized = [
            {
                "source": _mapped_identity(
                    edge["source"], identity_mapping
                ),
                "target": _mapped_identity(
                    edge["target"], identity_mapping
                ),
                "relation": edge["relation"],
                "frame": edge["frame"],
                "valid_from": edge["valid_from"],
                "valid_to": edge.get("valid_to"),
                "evidence_refs": sorted(edge["evidence_refs"]),
                "source_provenance": _semantic_provenance(
                    edge["provenance"], transaction_ids
                ),
            }
            for edge in versions
        ]
        lineages.append(sorted(normalized, key=canonical_json))
    return sorted(lineages, key=canonical_json)


def _canonical_pending_store(
    store: dict[str, Any] | None,
    transaction_ids: set[str],
) -> dict[str, Any] | None:
    if store is None:
        return None
    validate_pending_store(store)
    result = deepcopy(store)
    result.pop("store_id", None)
    result.pop("store_version", None)
    for record in result["records"]:
        consumer = record.get("consumed_by_transaction")
        audit_ids = set(transaction_ids)
        if consumer:
            audit_ids.add(consumer)
            record["consumed_by_transaction"] = (
                "__committed_transaction__"
            )
        record["provenance"] = _semantic_provenance(
            record["provenance"], audit_ids
        )
        record["evidence"] = sorted(
            record["evidence"],
            key=lambda item: item["evidence_id"],
        )
        for item in record["evidence"]:
            item["semantic_hints"] = sorted(item["semantic_hints"])
        for key in (
            "latent_refs",
            "spatial_refs",
            "semantic_hints",
        ):
            record["retrieval"][key] = sorted(
                record["retrieval"][key]
            )
        record["relevant_opportunity_ids"] = sorted(
            record["relevant_opportunity_ids"]
        )
        record["opportunity_history"] = sorted(
            record["opportunity_history"], key=canonical_json
        )
        record["archive_history"] = sorted(
            record["archive_history"], key=canonical_json
        )
    result["records"] = sorted(
        result["records"], key=lambda record: record["pending_id"]
    )
    return result


def canonicalize_memory_state(
    base_graph: dict[str, Any],
    graph: dict[str, Any],
    *,
    identity_mapping: Mapping[str, str],
    protected_ids: set[str] | frozenset[str] = frozenset(),
    pending_store: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Remove audit-only names while retaining future-relevant memory."""

    validate_graph(base_graph)
    validate_graph(graph)
    if graph["graph_id"] != base_graph["graph_id"]:
        raise PreconditionError(
            "post-world must belong to the same base graph"
        )
    normalized_protected = sorted(
        identity_mapping.get(value, value) for value in protected_ids
    )
    return {
        "schema_version": graph["schema_version"],
        "nodes": _canonical_nodes(graph, identity_mapping),
        "edge_lineages": _canonical_edge_lineages(
            graph, identity_mapping
        ),
        "protected_ids": normalized_protected,
        "pending_store": _canonical_pending_store(
            pending_store, set(graph["transaction_log"])
        ),
    }


def validate_canonical_memory_state_equality(
    base_graph: dict[str, Any],
    left_graph: dict[str, Any],
    right_graph: dict[str, Any],
    *,
    identity_mapping: Mapping[str, str],
    policy: Mapping[str, Any],
    left_protected_ids: set[str] | frozenset[str] = frozenset(),
    right_protected_ids: set[str] | frozenset[str] = frozenset(),
    left_pending_store: dict[str, Any] | None = None,
    right_pending_store: dict[str, Any] | None = None,
) -> None:
    """Require equality of every retained, decision-relevant state field."""

    validate_identity_correspondence(
        base_graph,
        left_graph,
        right_graph,
        identity_mapping=identity_mapping,
        policy=policy,
    )
    right_mapping = {
        identity_id: identity_id
        for identity_id in _stable_identity_ids(right_graph)
    }
    left_state = canonicalize_memory_state(
        base_graph,
        left_graph,
        identity_mapping=identity_mapping,
        protected_ids=left_protected_ids,
        pending_store=left_pending_store,
    )
    right_state = canonicalize_memory_state(
        base_graph,
        right_graph,
        identity_mapping=right_mapping,
        protected_ids=right_protected_ids,
        pending_store=right_pending_store,
    )
    for field in (
        "nodes",
        "edge_lineages",
        "protected_ids",
        "pending_store",
    ):
        if left_state[field] != right_state[field]:
            raise ContractError(
                f"canonical memory states differ in {field}"
            )
