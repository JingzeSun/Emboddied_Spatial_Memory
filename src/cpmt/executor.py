"""Versioned deterministic execution for the CPMT C00-C11 M0 slice.

Implemented templates: NOOP, BIND, BIRTH, REACTIVATE, RELINK, RETRACT,
SPLIT, MERGE and COMPOSITE:REPLACE. RETRACT and REPLACE accept either an
edge version or an entity node version. QUARANTINE remains unsupported.
Execution always happens on a deep copy of an immutable base graph.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping

from .errors import (
    ContractError,
    DuplicateTransactionError,
    InvariantViolation,
    PreconditionError,
    ProtectedMutationError,
    UnsupportedTemplateError,
    VersionMismatchError,
)
from .hashing import clone_json, compute_graph_hash


SCHEMA_VERSION = "cpmt-0.2"
LIFECYCLES = {"candidate", "confirmed", "dormant", "retracted", "alias"}
IMPLEMENTED_TEMPLATES = {
    "NOOP",
    "BIND",
    "BIRTH",
    "REACTIVATE",
    "RELINK",
    "SPLIT",
    "MERGE",
    "RETRACT",
    "COMPOSITE",
}
INTENT_TEMPLATES = {
    "PRESERVE": {"NOOP"},
    "ASSOCIATE": {"BIND", "REACTIVATE"},
    "EXPAND": {"BIRTH"},
    "REVISE": {"RELINK", "RETRACT", "SPLIT", "MERGE", "COMPOSITE"},
}


def _duplicates(values: Iterable[str]) -> set[str]:
    return {
        value
        for value, count in Counter(values).items()
        if count > 1
    }


def _open_nodes(graph: dict[str, Any], node_id: str) -> list[dict[str, Any]]:
    return [
        node
        for node in graph["nodes"]
        if node["node_id"] == node_id and node.get("valid_to") is None
    ]


def _open_node(graph: dict[str, Any], node_id: str) -> dict[str, Any]:
    matches = _open_nodes(graph, node_id)
    if len(matches) != 1:
        raise PreconditionError(
            f"expected exactly one open version for node {node_id!r}, "
            f"found {len(matches)}"
        )
    return matches[0]


def _node_version(graph: dict[str, Any], version_id: str) -> dict[str, Any]:
    matches = [
        node
        for node in graph["nodes"]
        if node["node_version_id"] == version_id
    ]
    if len(matches) != 1:
        raise PreconditionError(
            f"expected node_version_id {version_id!r} exactly once, "
            f"found {len(matches)}"
        )
    return matches[0]


def _open_edges(graph: dict[str, Any], edge_id: str) -> list[dict[str, Any]]:
    return [
        edge
        for edge in graph["edges"]
        if edge["edge_id"] == edge_id and edge.get("valid_to") is None
    ]


def _open_edge(graph: dict[str, Any], edge_id: str) -> dict[str, Any]:
    matches = _open_edges(graph, edge_id)
    if len(matches) != 1:
        raise PreconditionError(
            f"expected exactly one open version for edge {edge_id!r}, "
            f"found {len(matches)}"
        )
    return matches[0]


def _edge_version(graph: dict[str, Any], version_id: str) -> dict[str, Any]:
    matches = [
        edge
        for edge in graph["edges"]
        if edge["edge_version_id"] == version_id
    ]
    if len(matches) != 1:
        raise PreconditionError(
            f"expected edge_version_id {version_id!r} exactly once, "
            f"found {len(matches)}"
        )
    return matches[0]


def validate_graph(
    graph: dict[str, Any],
    *,
    verify_hash: bool = True,
) -> None:
    required = {
        "schema_version",
        "graph_id",
        "graph_version",
        "parent_version",
        "nodes",
        "edges",
        "transaction_log",
    }
    missing = required - graph.keys()
    if missing:
        raise ContractError(f"graph missing keys: {sorted(missing)}")
    if graph["schema_version"] != SCHEMA_VERSION:
        raise ContractError(
            f"unsupported graph schema {graph['schema_version']!r}"
        )

    node_versions = [
        node.get("node_version_id", "") for node in graph["nodes"]
    ]
    edge_versions = [
        edge.get("edge_version_id", "") for edge in graph["edges"]
    ]
    if "" in node_versions or _duplicates(node_versions):
        raise InvariantViolation(
            "node_version_id values must be non-empty and unique"
        )
    if "" in edge_versions or _duplicates(edge_versions):
        raise InvariantViolation(
            "edge_version_id values must be non-empty and unique"
        )

    for node in graph["nodes"]:
        lifecycle = node.get("lifecycle")
        if lifecycle not in LIFECYCLES:
            raise InvariantViolation(f"invalid lifecycle {lifecycle!r}")
        valid_from = node.get("valid_from")
        valid_to = node.get("valid_to")
        if not isinstance(valid_from, int) or valid_from < 0:
            raise InvariantViolation(
                "node valid_from must be a non-negative integer"
            )
        if valid_to is not None and (
            not isinstance(valid_to, int) or valid_to < valid_from
        ):
            raise InvariantViolation(
                "node valid_to must be null or >= valid_from"
            )
        if not node.get("provenance"):
            raise InvariantViolation(
                "every node version needs provenance"
            )
        if lifecycle == "retracted" and valid_to is None:
            raise InvariantViolation(
                "retracted identity cannot have an open version"
            )
        if lifecycle == "alias" and not node.get("canonical_id"):
            raise InvariantViolation(
                "alias node must name a canonical_id"
            )

    # One pass instead of rescanning every node version per identifier.
    open_node_counts: dict[str, int] = {}
    open_node_ids: set[str] = set()
    for node in graph["nodes"]:
        if node.get("valid_to") is None:
            identity = node["node_id"]
            open_node_counts[identity] = open_node_counts.get(identity, 0) + 1
            open_node_ids.add(identity)
    for node_id, count in open_node_counts.items():
        if count > 1:
            raise InvariantViolation(
                f"node {node_id!r} has multiple open versions"
            )

    for edge in graph["edges"]:
        valid_from = edge.get("valid_from")
        valid_to = edge.get("valid_to")
        if not isinstance(valid_from, int) or valid_from < 0:
            raise InvariantViolation(
                "edge valid_from must be a non-negative integer"
            )
        if valid_to is not None and (
            not isinstance(valid_to, int) or valid_to < valid_from
        ):
            raise InvariantViolation(
                "edge valid_to must be null or >= valid_from"
            )
        if not edge.get("provenance"):
            raise InvariantViolation(
                "every edge version needs provenance"
            )
        if valid_to is None:
            for endpoint in (edge["source"], edge["target"]):
                if endpoint not in open_node_ids:
                    # Reproduce the original error from the scanning helper.
                    _open_node(graph, endpoint)

    open_edge_counts: dict[str, int] = {}
    for edge in graph["edges"]:
        if edge.get("valid_to") is None:
            identity = edge["edge_id"]
            open_edge_counts[identity] = open_edge_counts.get(identity, 0) + 1
    for edge_id, count in open_edge_counts.items():
        if count > 1:
            raise InvariantViolation(
                f"edge {edge_id!r} has multiple open versions"
            )

    stored_hash = graph.get("graph_hash")
    if verify_hash and stored_hash is not None:
        actual_hash = compute_graph_hash(graph)
        if stored_hash != actual_hash:
            raise InvariantViolation(
                "stored graph_hash does not match graph contents"
            )


def _validate_program_header(program: dict[str, Any]) -> None:
    required = {
        "schema_version",
        "transaction_id",
        "intent",
        "template",
        "base_graph_version",
        "operations",
        "evidence_refs",
        "protected_ids",
    }
    missing = required - program.keys()
    if missing:
        raise ContractError(f"program missing keys: {sorted(missing)}")
    if program["schema_version"] != SCHEMA_VERSION:
        raise ContractError(
            f"unsupported program schema {program['schema_version']!r}"
        )
    allowed = INTENT_TEMPLATES.get(program["intent"])
    if allowed is None or program["template"] not in allowed:
        raise ContractError(
            f"template {program['template']!r} is incompatible with "
            f"intent {program['intent']!r}"
        )
    if program["template"] not in IMPLEMENTED_TEMPLATES:
        raise UnsupportedTemplateError(
            f"template {program['template']} is not implemented "
            "in the C00-C11 slice"
        )


def operation_argument_ids(
    value: Any,
    key: str | None = None,
) -> set[str]:
    """Return exact structured identifiers touched by operation arguments."""
    ids: set[str] = set()
    if isinstance(value, dict):
        for child_key, child in value.items():
            ids.update(operation_argument_ids(child, child_key))
    elif isinstance(value, list):
        for child in value:
            ids.update(operation_argument_ids(child, key))
    elif isinstance(value, str) and key is not None and (
        key.endswith("_id")
        or key.endswith("_ids")
        or key in {"source", "target"}
    ):
        ids.add(value)
    return ids


def _check_protected(
    operation: dict[str, Any],
    protected_ids: set[str],
) -> None:
    touched = operation_argument_ids(operation.get("arguments", {}))
    overlap = touched & protected_ids
    if overlap:
        raise ProtectedMutationError(
            f"operation {operation.get('op_id')!r} touches protected "
            f"IDs {sorted(overlap)}"
        )


def _assert_precondition(
    graph: dict[str, Any],
    arguments: dict[str, Any],
) -> None:
    kind = arguments.get("kind")
    if kind == "node_lifecycle":
        node = _open_node(graph, arguments["node_id"])
        allowed = set(arguments["allowed"])
        if node["lifecycle"] not in allowed:
            raise PreconditionError(
                f"node {node['node_id']!r} lifecycle "
                f"{node['lifecycle']!r} is not in {sorted(allowed)}"
            )
    elif kind == "node_exists":
        _open_node(graph, arguments["node_id"])
    elif kind == "node_absent":
        if any(
            node["node_id"] == arguments["node_id"]
            for node in graph["nodes"]
        ):
            raise PreconditionError(
                f"node {arguments['node_id']!r} already exists"
            )
    elif kind == "edge_exists":
        _open_edge(graph, arguments["edge_id"])
    else:
        raise ContractError(
            f"unsupported precondition kind {kind!r}"
        )


def _record_for_arguments(
    graph: dict[str, Any],
    arguments: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    target_kind = arguments["target_kind"]
    if target_kind == "node":
        if "node_version_id" in arguments:
            record = _node_version(
                graph,
                arguments["node_version_id"],
            )
        else:
            record = _open_node(graph, arguments["target_id"])
        return ("node", record)
    if target_kind == "edge":
        if "edge_version_id" in arguments:
            record = _edge_version(
                graph,
                arguments["edge_version_id"],
            )
        else:
            record = _open_edge(graph, arguments["target_id"])
        return ("edge", record)
    raise ContractError(
        f"unsupported target_kind {target_kind!r}"
    )


def _apply_operation(
    graph: dict[str, Any],
    operation: dict[str, Any],
    touched: set[tuple[str, str]],
) -> None:
    op_type = operation["op_type"]
    arguments = operation["arguments"]

    if op_type == "ASSERT_PRECONDITION":
        _assert_precondition(graph, arguments)
        return

    if op_type == "CREATE_NODE":
        node = clone_json(arguments["node"])
        if any(
            existing["node_id"] == node["node_id"]
            for existing in graph["nodes"]
        ):
            raise PreconditionError(
                f"node {node['node_id']!r} already exists"
            )
        if any(
            existing["node_version_id"] == node["node_version_id"]
            for existing in graph["nodes"]
        ):
            raise PreconditionError(
                f"node version {node['node_version_id']!r} "
                "already exists"
            )
        graph["nodes"].append(node)
        touched.add(("node", node["node_version_id"]))
        return

    if op_type == "OPEN_NODE_VERSION":
        node = clone_json(arguments["node"])
        if not any(
            existing["node_id"] == node["node_id"]
            for existing in graph["nodes"]
        ):
            raise PreconditionError(
                f"cannot open version for unknown node "
                f"{node['node_id']!r}"
            )
        if _open_nodes(graph, node["node_id"]):
            raise PreconditionError(
                f"node {node['node_id']!r} already has an open version"
            )
        if any(
            existing["node_version_id"] == node["node_version_id"]
            for existing in graph["nodes"]
        ):
            raise PreconditionError(
                f"node version {node['node_version_id']!r} "
                "already exists"
            )
        graph["nodes"].append(node)
        touched.add(("node", node["node_version_id"]))
        return

    if op_type == "CLOSE_NODE_VERSION":
        node = _open_node(graph, arguments["node_id"])
        node["valid_to"] = arguments["at"]
        touched.add(("node", node["node_version_id"]))
        return

    if op_type == "ADD_EDGE":
        edge = clone_json(arguments["edge"])
        if _open_edges(graph, edge["edge_id"]):
            raise PreconditionError(
                f"edge {edge['edge_id']!r} already has an open version"
            )
        if any(
            existing["edge_version_id"] == edge["edge_version_id"]
            for existing in graph["edges"]
        ):
            raise PreconditionError(
                f"edge version {edge['edge_version_id']!r} "
                "already exists"
            )
        _open_node(graph, edge["source"])
        _open_node(graph, edge["target"])
        graph["edges"].append(edge)
        touched.add(("edge", edge["edge_version_id"]))
        return

    if op_type == "CLOSE_EDGE_VERSION":
        edge = _open_edge(graph, arguments["edge_id"])
        edge["valid_to"] = arguments["at"]
        touched.add(("edge", edge["edge_version_id"]))
        return

    if op_type == "ATTACH_EVIDENCE":
        target_kind, record = _record_for_arguments(
            graph,
            arguments,
        )
        evidence_ref = arguments["evidence_ref"]
        if evidence_ref not in record["evidence_refs"]:
            record["evidence_refs"].append(evidence_ref)
        version_key = (
            record["node_version_id"]
            if target_kind == "node"
            else record["edge_version_id"]
        )
        touched.add((target_kind, version_key))
        return

    if op_type == "MOVE_EVIDENCE":
        source_kind, source = _record_for_arguments(
            graph,
            arguments["from"],
        )
        target_kind, target = _record_for_arguments(
            graph,
            arguments["to"],
        )
        evidence_ref = arguments["evidence_ref"]
        if evidence_ref not in source["evidence_refs"]:
            raise PreconditionError(
                f"source does not contain evidence "
                f"{evidence_ref!r}"
            )
        source["evidence_refs"].remove(evidence_ref)
        if evidence_ref not in target["evidence_refs"]:
            target["evidence_refs"].append(evidence_ref)
        source_key = (
            source["node_version_id"]
            if source_kind == "node"
            else source["edge_version_id"]
        )
        target_key = (
            target["node_version_id"]
            if target_kind == "node"
            else target["edge_version_id"]
        )
        touched.update(
            {
                (source_kind, source_key),
                (target_kind, target_key),
            }
        )
        return

    if op_type == "SET_CANONICAL_ALIAS":
        alias = _open_node(graph, arguments["alias_node_id"])
        canonical = _open_node(
            graph,
            arguments["canonical_node_id"],
        )
        if canonical["lifecycle"] == "alias":
            raise PreconditionError(
                "canonical target cannot itself be an alias"
            )
        alias["lifecycle"] = "alias"
        alias["canonical_id"] = canonical["node_id"]
        touched.add(("node", alias["node_version_id"]))
        return

    if op_type == "SET_LIFECYCLE":
        node = _open_node(graph, arguments["node_id"])
        expected = arguments["from"]
        if node["lifecycle"] != expected:
            raise PreconditionError(
                f"expected lifecycle {expected!r}, "
                f"found {node['lifecycle']!r}"
            )
        destination = arguments["to"]
        if destination not in LIFECYCLES:
            raise ContractError(
                f"invalid destination lifecycle {destination!r}"
            )
        if expected == "retracted":
            raise PreconditionError(
                "retracted identity cannot change lifecycle directly"
            )
        if (
            expected == "candidate"
            and destination == "confirmed"
            and len(set(node["evidence_refs"])) < 2
        ):
            raise PreconditionError(
                "candidate confirmation needs at least two unique "
                "evidence references"
            )
        node["lifecycle"] = destination
        touched.add(("node", node["node_version_id"]))
        return

    if op_type == "RECORD_PROVENANCE":
        target_kind, record = _record_for_arguments(
            graph,
            arguments,
        )
        provenance_ref = arguments["provenance_ref"]
        if provenance_ref not in record["provenance"]:
            record["provenance"].append(provenance_ref)
        version_key = (
            record["node_version_id"]
            if target_kind == "node"
            else record["edge_version_id"]
        )
        touched.add((target_kind, version_key))
        return

    raise ContractError(f"unsupported primitive {op_type!r}")


def _validate_reliable_negative_evidence(
    program: dict[str, Any],
    *,
    target_version_id: str,
    evidence_by_id: Mapping[str, dict[str, Any]],
    reliability_threshold: float,
) -> None:
    _validate_reliable_negative_evidence_refs(
        program["evidence_refs"],
        target_version_id=target_version_id,
        evidence_by_id=evidence_by_id,
        reliability_threshold=reliability_threshold,
    )


def _validate_reliable_negative_evidence_refs(
    evidence_refs: Iterable[str],
    *,
    target_version_id: str,
    evidence_by_id: Mapping[str, dict[str, Any]],
    reliability_threshold: float,
) -> None:
    if not 0 <= reliability_threshold <= 1:
        raise ContractError(
            "reliability_threshold must be between 0 and 1"
        )
    evidence_refs = list(evidence_refs)
    if any(type(evidence_id) is not str for evidence_id in evidence_refs):
        raise ContractError("negative evidence refs must be strings")
    missing = [
        evidence_id
        for evidence_id in evidence_refs
        if evidence_id not in evidence_by_id
    ]
    if missing:
        raise PreconditionError(
            f"missing evidence records: {sorted(missing)}"
        )

    referenced = [
        evidence_by_id[evidence_id]
        for evidence_id in evidence_refs
    ]
    negatives = [
        event
        for event in referenced
        if event.get("claim_ref") == target_version_id
        and event.get("kind") == "visible_empty"
        and event.get("verdict") == "contradicts"
    ]
    if len(negatives) < 2:
        raise PreconditionError(
            "reliable absence needs at least two visible_empty "
            "contradicting events"
        )
    for event in negatives:
        if event.get("availability") != "online":
            raise PreconditionError(
                "reliable absence evidence must be available online"
            )
        if event.get("visibility") != "visible_empty":
            raise PreconditionError(
                "reliable absence evidence must mark visible_empty"
            )
        if event.get("pose_valid") is not True:
            raise PreconditionError(
                "reliable absence evidence requires valid pose"
            )
        if event.get("depth_valid") is not True:
            raise PreconditionError(
                "reliable absence evidence requires valid depth"
            )
        if event.get("reliability", 0) < reliability_threshold:
            raise PreconditionError(
                "reliable absence evidence is below reliability threshold"
            )

    distinct_keys = {
        (event.get("time_index"), event.get("viewpoint_id"))
        for event in negatives
    }
    if len(distinct_keys) < 2:
        raise PreconditionError(
            "reliable absence evidence needs two distinct time/view keys"
        )

    first_time = min(event["time_index"] for event in negatives)
    last_time = max(event["time_index"] for event in negatives)
    intervening_positive = [
        event
        for event in evidence_by_id.values()
        if event.get("claim_ref") == target_version_id
        and event.get("kind") == "observation"
        and event.get("verdict") == "supports"
        and first_time < event.get("time_index", -1) < last_time
    ]
    if intervening_positive:
        raise PreconditionError(
            "supporting observation interrupts the negative chain"
        )


def _validate_current_support_evidence_refs(
    evidence_refs: Iterable[str],
    *,
    claim_refs: set[str],
    evidence_by_id: Mapping[str, dict[str, Any]],
) -> None:
    """Require explicit online support for a newly born node or relation."""

    evidence_refs = list(evidence_refs)
    if not evidence_refs or len(evidence_refs) != len(set(evidence_refs)):
        raise ContractError(
            "new structure support needs unique nonempty evidence refs"
        )
    missing = [
        evidence_id for evidence_id in evidence_refs
        if evidence_id not in evidence_by_id
    ]
    if missing:
        raise PreconditionError(
            f"missing evidence records: {sorted(missing)}"
        )
    for evidence_id in evidence_refs:
        event = evidence_by_id[evidence_id]
        if (
            event.get("claim_ref") not in claim_refs
            or event.get("kind") != "observation"
            or event.get("verdict") != "supports"
            or event.get("availability") != "online"
        ):
            raise PreconditionError(
                "new structure evidence must be an online supporting "
                "observation for that structure"
            )


def _validate_node_retraction(
    graph: dict[str, Any],
    program: dict[str, Any],
    operations: list[dict[str, Any]],
    *,
    target_version_id: str,
    evidence_by_id: Mapping[str, dict[str, Any]],
    reliability_threshold: float,
) -> tuple[
    dict[str, Any], dict[str, Any], list[dict[str, Any]], int, list[str]
]:
    """Validate the shared entity-retirement portion of RETRACT/REPLACE."""

    source = _node_version(graph, target_version_id)
    if source.get("valid_to") is not None:
        raise PreconditionError("RETRACT target node version is already closed")
    if _open_node(graph, source["node_id"])["node_version_id"] != target_version_id:
        raise PreconditionError("RETRACT must target the current open node version")
    if source.get("node_type") != "entity":
        raise UnsupportedTemplateError(
            "node-level RETRACT is currently limited to entity nodes"
        )
    if source.get("lifecycle") not in {"candidate", "confirmed", "dormant"}:
        raise PreconditionError(
            "node-level RETRACT needs a candidate, confirmed, or dormant entity"
        )

    node_closes = [
        operation for operation in operations
        if operation["op_type"] == "CLOSE_NODE_VERSION"
    ]
    if len(node_closes) != 1:
        raise ContractError("node RETRACT must close exactly one node version")
    close = node_closes[0]
    if close["arguments"]["node_id"] != source["node_id"]:
        raise ContractError("node RETRACT close does not match retraction_target")
    close_at = close["arguments"]["at"]

    terminal_versions = [
        operation["arguments"]["node"] for operation in operations
        if operation["op_type"] == "OPEN_NODE_VERSION"
    ]
    if len(terminal_versions) != 1:
        raise ContractError(
            "node RETRACT must append exactly one terminal retracted version"
        )
    terminal = terminal_versions[0]
    negative_refs = [
        evidence_id for evidence_id in program["evidence_refs"]
        if evidence_id in evidence_by_id
        and evidence_by_id[evidence_id].get("claim_ref") == target_version_id
        and evidence_by_id[evidence_id].get("kind") == "visible_empty"
        and evidence_by_id[evidence_id].get("verdict") == "contradicts"
    ]
    expected_terminal = clone_json(source)
    expected_terminal.update({
        "node_version_id": terminal.get("node_version_id"),
        "lifecycle": "retracted",
        "valid_from": close_at,
        "valid_to": close_at,
        "evidence_refs": list(dict.fromkeys(
            list(source.get("evidence_refs", [])) + negative_refs
        )),
        "predecessor_ids": [source["node_version_id"]],
        "provenance": list(dict.fromkeys(
            list(source.get("provenance", [])) + [program["transaction_id"]]
        )),
    })
    if (
        terminal.get("node_version_id") == source["node_version_id"]
        or any(
            node["node_version_id"] == terminal.get("node_version_id")
            for node in graph["nodes"]
        )
        or terminal != expected_terminal
    ):
        raise ContractError(
            "node RETRACT terminal version must preserve identity, evidence, "
            "latents, history, and transaction provenance"
        )

    incident_edges = [
        edge for edge in graph["edges"]
        if edge.get("valid_to") is None
        and source["node_id"] in {edge["source"], edge["target"]}
    ]
    edge_closes = [
        operation for operation in operations
        if operation["op_type"] == "CLOSE_EDGE_VERSION"
    ]
    closed_edge_ids = [
        operation["arguments"]["edge_id"] for operation in edge_closes
    ]
    expected_edge_ids = [edge["edge_id"] for edge in incident_edges]
    if (
        len(closed_edge_ids) != len(set(closed_edge_ids))
        or set(closed_edge_ids) != set(expected_edge_ids)
    ):
        raise ContractError(
            "node RETRACT must close every open incident edge exactly once"
        )
    if any(
        operation["arguments"]["at"] != close_at for operation in edge_closes
    ):
        raise ContractError(
            "node RETRACT and all incident edges must close at one tick"
        )

    evidence_attaches = [
        operation for operation in operations
        if operation["op_type"] == "ATTACH_EVIDENCE"
    ]
    attached_refs = [
        operation["arguments"].get("evidence_ref")
        for operation in evidence_attaches
    ]
    if (
        len(attached_refs) != len(set(attached_refs))
        or set(attached_refs) != set(negative_refs)
        or any(
            operation["arguments"].get("target_kind") != "node"
            or operation["arguments"].get("node_version_id")
            != source["node_version_id"]
            for operation in evidence_attaches
        )
    ):
        raise ContractError(
            "node RETRACT may attach only its declared negative evidence "
            "to the retired source version"
        )

    expected_provenance_targets = {
        ("node", source["node_version_id"]),
        *{
            ("edge", edge["edge_version_id"])
            for edge in incident_edges
        },
    }
    provenance_records = [
        operation for operation in operations
        if operation["op_type"] == "RECORD_PROVENANCE"
    ]
    actual_provenance_targets = [
        (
            operation["arguments"].get("target_kind"),
            operation["arguments"].get(
                "node_version_id"
                if operation["arguments"].get("target_kind") == "node"
                else "edge_version_id"
            ),
        )
        for operation in provenance_records
    ]
    if (
        len(actual_provenance_targets) != len(set(actual_provenance_targets))
        or set(actual_provenance_targets) != expected_provenance_targets
        or any(
            operation["arguments"].get("provenance_ref")
            != program["transaction_id"]
            for operation in provenance_records
        )
    ):
        raise ContractError(
            "node RETRACT provenance must cover only the source entity and "
            "all retired incident edges"
        )

    _validate_reliable_negative_evidence(
        program,
        target_version_id=target_version_id,
        evidence_by_id=evidence_by_id,
        reliability_threshold=reliability_threshold,
    )
    return source, terminal, incident_edges, close_at, negative_refs


def _validate_template_preconditions(
    graph: dict[str, Any],
    program: dict[str, Any],
    *,
    evidence_by_id: Mapping[str, dict[str, Any]],
    reliability_threshold: float,
) -> None:
    template = program["template"]
    operations = program["operations"]
    op_types = [
        operation["op_type"] for operation in operations
    ]

    if template == "NOOP":
        if operations:
            raise ContractError("NOOP must have zero operations")
        return

    if template == "BIND":
        if any(
            op in {"CREATE_NODE", "OPEN_NODE_VERSION", "ADD_EDGE"}
            for op in op_types
        ):
            raise ContractError(
                "BIND cannot create an identity or open a version"
            )
        attach_ops = [
            operation
            for operation in operations
            if operation["op_type"] == "ATTACH_EVIDENCE"
        ]
        target_kinds = {
            operation["arguments"].get("target_kind")
            for operation in attach_ops
        }
        if not attach_ops or len(target_kinds) != 1 or not target_kinds <= {"node", "edge"}:
            raise ContractError(
                "BIND needs ATTACH_EVIDENCE operations for exactly one node or edge"
            )
        target_kind = next(iter(target_kinds))
        attachment_targets = {
            operation["arguments"].get("target_id")
            for operation in attach_ops
        }
        if target_kind == "edge" and len(attachment_targets) != 1:
            raise ContractError("relation BIND must target exactly one edge identity")
        if target_kind == "node":
            for operation in attach_ops:
                node = _open_node(
                    graph,
                    operation["arguments"]["target_id"],
                )
                if node["lifecycle"] not in {
                    "candidate",
                    "confirmed",
                }:
                    raise PreconditionError(
                        f"BIND target {node['node_id']!r} is "
                        f"{node['lifecycle']!r}"
                    )
        else:
            for operation in attach_ops:
                _open_edge(graph, operation["arguments"]["target_id"])
        lifecycle_ops = [
            operation
            for operation in operations
            if operation["op_type"] == "SET_LIFECYCLE"
        ]
        bind_targets = {
            operation["arguments"]["target_id"]
            for operation in attach_ops
        } if target_kind == "node" else set()
        if target_kind == "edge" and lifecycle_ops:
            raise ContractError("relation BIND cannot change node lifecycle")
        for operation in lifecycle_ops:
            arguments = operation["arguments"]
            if (
                arguments.get("node_id") not in bind_targets
                or arguments.get("from") != "candidate"
                or arguments.get("to") != "confirmed"
            ):
                raise ContractError(
                    "BIND may only explicitly promote its own "
                    "candidate target to confirmed"
                )
        return

    if template == "BIRTH":
        creates = [
            operation
            for operation in operations
            if operation["op_type"] == "CREATE_NODE"
        ]
        adds = [
            operation
            for operation in operations
            if operation["op_type"] == "ADD_EDGE"
        ]
        if (len(creates), len(adds)) not in {(1, 0), (0, 1)}:
            raise ContractError(
                "BIRTH must create exactly one node or edge identity"
            )
        if adds:
            edge = adds[0]["arguments"]["edge"]
            if any(
                existing["edge_id"] == edge["edge_id"]
                for existing in graph["edges"]
            ):
                raise PreconditionError(
                    f"BIRTH edge identity {edge['edge_id']!r} already exists"
                )
            _open_node(graph, edge["source"])
            _open_node(graph, edge["target"])
            return
        node = creates[0]["arguments"]["node"]
        if node["lifecycle"] != "candidate":
            raise ContractError(
                "BIRTH must initialize lifecycle=candidate"
            )
        if any(
            existing["node_id"] == node["node_id"]
            for existing in graph["nodes"]
        ):
            raise PreconditionError(
                f"BIRTH identity {node['node_id']!r} already exists"
            )
        return

    if template == "REACTIVATE":
        closes = [
            operation
            for operation in operations
            if operation["op_type"] == "CLOSE_NODE_VERSION"
        ]
        opens = [
            operation
            for operation in operations
            if operation["op_type"] == "OPEN_NODE_VERSION"
        ]
        if len(closes) != 1 or len(opens) != 1:
            raise ContractError(
                "REACTIVATE needs exactly one CLOSE_NODE_VERSION "
                "and one OPEN_NODE_VERSION"
            )
        node_id = closes[0]["arguments"]["node_id"]
        old = _open_node(graph, node_id)
        new = opens[0]["arguments"]["node"]
        if old["lifecycle"] != "dormant":
            raise PreconditionError(
                f"REACTIVATE target {node_id!r} is "
                f"{old['lifecycle']!r}, not dormant"
            )
        if (
            new["node_id"] != node_id
            or new["lifecycle"] != "confirmed"
        ):
            raise ContractError(
                "REACTIVATE must open a confirmed version "
                "of the same identity"
            )
        return

    if template == "RELINK":
        closes = [
            operation
            for operation in operations
            if operation["op_type"] == "CLOSE_EDGE_VERSION"
        ]
        adds = [
            operation
            for operation in operations
            if operation["op_type"] == "ADD_EDGE"
        ]
        if len(closes) != 1 or len(adds) != 1:
            raise ContractError(
                "current RELINK contract needs exactly one "
                "closed and one added edge"
            )
        old = _open_edge(
            graph,
            closes[0]["arguments"]["edge_id"],
        )
        new = adds[0]["arguments"]["edge"]
        if old["edge_id"] != new["edge_id"]:
            raise ContractError(
                "RELINK must preserve edge identity"
            )
        if (
            old["source"] != new["source"]
            or old["relation"] != new["relation"]
        ):
            raise ContractError(
                "RELINK must preserve subject identity "
                "and relation type"
            )
        if old["target"] == new["target"]:
            raise ContractError(
                "RELINK must change the relation target"
            )
        return

    if template == "SPLIT":
        closes = [
            operation
            for operation in operations
            if operation["op_type"] == "CLOSE_NODE_VERSION"
        ]
        retracts = [
            operation
            for operation in operations
            if operation["op_type"] == "SET_LIFECYCLE"
            and operation["arguments"].get("to") == "retracted"
        ]
        creates = [
            operation
            for operation in operations
            if operation["op_type"] == "CREATE_NODE"
        ]
        if (
            len(closes) != 1
            or len(retracts) != 1
            or len(creates) < 2
        ):
            raise ContractError(
                "SPLIT needs one retracted/closed source and "
                "at least two created successors"
            )
        source_id = closes[0]["arguments"]["node_id"]
        retract = retracts[0]["arguments"]
        if (
            retract.get("node_id") != source_id
            or retract.get("from") not in {"candidate", "confirmed"}
        ):
            raise ContractError(
                "SPLIT must retract and close the same "
                "candidate/confirmed source"
            )
        source = _open_node(graph, source_id)
        if source["lifecycle"] != retract["from"]:
            raise PreconditionError(
                "SPLIT source lifecycle does not match "
                "the declared transition"
            )

        successors = [
            operation["arguments"]["node"]
            for operation in creates
        ]
        successor_ids = [
            node["node_id"] for node in successors
        ]
        if len(set(successor_ids)) != len(successor_ids):
            raise ContractError(
                "SPLIT successor IDs must be unique"
            )
        for node in successors:
            if node["lifecycle"] != "candidate":
                raise ContractError(
                    "SPLIT successors must start as candidate"
                )
            if source["node_version_id"] not in node.get(
                "predecessor_ids",
                [],
            ):
                raise ContractError(
                    "every SPLIT successor must reference "
                    "the source node_version_id"
                )
            if any(
                existing["node_id"] == node["node_id"]
                for existing in graph["nodes"]
            ):
                raise PreconditionError(
                    f"SPLIT successor {node['node_id']!r} "
                    "already exists"
                )

        evidence_lists = [
            node["evidence_refs"] for node in successors
        ]
        flattened_evidence = [
            evidence
            for evidence_list in evidence_lists
            for evidence in evidence_list
        ]
        latent_lists = [
            node["latent_refs"] for node in successors
        ]
        flattened_latents = [
            latent
            for latent_list in latent_lists
            for latent in latent_list
        ]
        if any(not latent_list for latent_list in latent_lists):
            raise ContractError(
                "every SPLIT successor needs its own latent refs"
            )
        if len(flattened_latents) != len(set(flattened_latents)):
            raise ContractError(
                "SPLIT successor latent refs must be disjoint"
            )
        if set(flattened_latents) & set(source["latent_refs"]):
            raise ContractError(
                "SPLIT successors cannot inherit the old "
                "conflated aggregate latent"
            )

        successor_evidence = program.get(
            "split_successor_evidence_refs", program["evidence_refs"],
        )
        if (
            type(successor_evidence) is not list
            or any(type(item) is not str for item in successor_evidence)
            or not set(successor_evidence) <= set(program["evidence_refs"])
        ):
            raise ContractError(
                "SPLIT successor evidence must be a string-list subset "
                "of program evidence_refs"
            )
        expected_evidence = set(source["evidence_refs"]) | set(
            successor_evidence
        )
        if (
            len(flattened_evidence) != len(set(flattened_evidence))
            or set(flattened_evidence) != expected_evidence
        ):
            raise ContractError(
                "SPLIT must partition source/successor evidence "
                "exactly once"
            )

        incident_edges = [
            edge for edge in graph["edges"]
            if edge.get("valid_to") is None
            and source_id in {edge["source"], edge["target"]}
        ]
        if any(
            edge["source"] == source_id and edge["target"] == source_id
            for edge in incident_edges
        ):
            raise ContractError(
                "relation-aware SPLIT does not support a source self-edge"
            )
        assignments = program.get("split_relation_assignments", [])
        if type(assignments) is not list or any(
            type(row) is not dict for row in assignments
        ):
            raise ContractError("SPLIT relation assignments must be objects")
        assignment_versions = [
            row.get("source_edge_version_id") for row in assignments
        ]
        expected_versions = [
            edge["edge_version_id"] for edge in incident_edges
        ]
        if (
            len(assignment_versions) != len(set(assignment_versions))
            or set(assignment_versions) != set(expected_versions)
        ):
            raise ContractError(
                "SPLIT must assign every open incident edge exactly once"
            )

        close_edge_ids = [
            operation["arguments"]["edge_id"]
            for operation in operations
            if operation["op_type"] == "CLOSE_EDGE_VERSION"
        ]
        if (
            len(close_edge_ids) != len(set(close_edge_ids))
            or set(close_edge_ids) != {edge["edge_id"] for edge in incident_edges}
        ):
            raise ContractError(
                "SPLIT must close every open incident edge exactly once"
            )
        close_edge_at = {
            operation["arguments"]["edge_id"]: operation["arguments"]["at"]
            for operation in operations
            if operation["op_type"] == "CLOSE_EDGE_VERSION"
        }

        added_edges = [
            operation["arguments"]["edge"]
            for operation in operations
            if operation["op_type"] == "ADD_EDGE"
        ]
        accounted_versions: list[str] = []
        edge_by_version = {
            edge["edge_version_id"]: edge for edge in incident_edges
        }
        successor_id_set = set(successor_ids)
        for assignment in assignments:
            source_edge_version = assignment["source_edge_version_id"]
            old_edge = edge_by_version[source_edge_version]
            assigned_ids = assignment.get("successor_node_ids")
            negative_refs = assignment.get("negative_evidence_refs")
            if type(assigned_ids) is not list or type(negative_refs) is not list:
                raise ContractError(
                    "SPLIT relation assignment lists are required"
                )
            if (
                len(assigned_ids) != len(set(assigned_ids))
                or len(assigned_ids) > 2
                or not set(assigned_ids) <= successor_id_set
            ):
                raise ContractError(
                    "SPLIT relation assignment names invalid successors"
                )
            if assigned_ids and negative_refs:
                raise ContractError(
                    "retained SPLIT relation cannot also claim reliable absence"
                )
            if not set(negative_refs) <= set(program["evidence_refs"]):
                raise ContractError(
                    "SPLIT relation absence evidence must appear in "
                    "program evidence_refs"
                )
            if not assigned_ids:
                _validate_reliable_negative_evidence_refs(
                    negative_refs,
                    target_version_id=source_edge_version,
                    evidence_by_id=evidence_by_id,
                    reliability_threshold=reliability_threshold,
                )

            marker = f"split_source_edge:{source_edge_version}"
            replacements = [
                edge for edge in added_edges if marker in edge["provenance"]
            ]
            if len(replacements) != len(assigned_ids):
                raise ContractError(
                    "SPLIT relation assignment and replacement edge count differ"
                )
            replacement_ids: list[str] = []
            for new_edge in replacements:
                replacement_id = (
                    new_edge["source"]
                    if old_edge["source"] == source_id
                    else new_edge["target"]
                )
                other_old = (
                    old_edge["target"]
                    if old_edge["source"] == source_id
                    else old_edge["source"]
                )
                other_new = (
                    new_edge["target"]
                    if old_edge["source"] == source_id
                    else new_edge["source"]
                )
                if (
                    replacement_id not in assigned_ids
                    or other_new != other_old
                    or new_edge["relation"] != old_edge["relation"]
                    or new_edge["frame"] != old_edge["frame"]
                    or not set(old_edge["evidence_refs"])
                    <= set(new_edge["evidence_refs"])
                    or not set(old_edge["provenance"])
                    <= set(new_edge["provenance"])
                    or new_edge.get("valid_from") != close_edge_at[old_edge["edge_id"]]
                    or new_edge.get("valid_to") is not None
                ):
                    raise ContractError(
                        "SPLIT replacement edge changed or lost old relation state"
                    )
                replacement_ids.append(replacement_id)
                accounted_versions.append(new_edge["edge_version_id"])
            if (
                len(replacement_ids) != len(set(replacement_ids))
                or set(replacement_ids) != set(assigned_ids)
            ):
                raise ContractError(
                    "SPLIT must recreate one relation for each named successor"
                )
        if (
            len(accounted_versions) != len(set(accounted_versions))
            or set(accounted_versions)
            != {edge["edge_version_id"] for edge in added_edges}
        ):
            raise ContractError(
                "SPLIT contains an unassigned or duplicate replacement edge"
            )
        return

    if template == "MERGE":
        closes = [
            operation
            for operation in operations
            if operation["op_type"] == "CLOSE_NODE_VERSION"
        ]
        opens = [
            operation["arguments"]["node"]
            for operation in operations
            if operation["op_type"] == "OPEN_NODE_VERSION"
        ]
        if len(closes) < 2 or len(opens) != len(closes):
            raise ContractError(
                "MERGE needs at least two closed sources and "
                "one new version for each source identity"
            )
        source_ids = [
            operation["arguments"]["node_id"]
            for operation in closes
        ]
        if len(set(source_ids)) != len(source_ids):
            raise ContractError(
                "MERGE source IDs must be unique"
            )
        if {
            node["node_id"] for node in opens
        } != set(source_ids):
            raise ContractError(
                "MERGE must reopen exactly the source identities"
            )
        sources = [
            _open_node(graph, node_id)
            for node_id in source_ids
        ]
        if any(
            node["lifecycle"] not in {"candidate", "confirmed"}
            for node in sources
        ):
            raise PreconditionError(
                "MERGE sources must be candidate/confirmed"
            )
        confirmed = [
            node
            for node in sources
            if node["lifecycle"] == "confirmed"
        ]
        if not confirmed:
            raise PreconditionError(
                "MERGE needs at least one confirmed source"
            )
        canonical_source = min(
            confirmed,
            key=lambda node: (
                node["valid_from"],
                node["node_id"],
            ),
        )
        canonical_id = canonical_source["node_id"]
        canonical_versions = [
            node
            for node in opens
            if node["node_id"] == canonical_id
        ]
        if len(canonical_versions) != 1:
            raise ContractError(
                "MERGE canonical version is missing or duplicated"
            )
        canonical = canonical_versions[0]
        if (
            canonical["lifecycle"] != "confirmed"
            or canonical.get("canonical_id") is not None
        ):
            raise ContractError(
                "MERGE canonical must reopen as confirmed "
                "without canonical_id"
            )

        expected_evidence = set(program["evidence_refs"])
        expected_latents: set[str] = set()
        expected_predecessors: set[str] = set()
        for source in sources:
            expected_evidence.update(source["evidence_refs"])
            expected_latents.update(source["latent_refs"])
            expected_predecessors.add(
                source["node_version_id"]
            )
        if (
            len(canonical["evidence_refs"])
            != len(set(canonical["evidence_refs"]))
            or set(canonical["evidence_refs"])
            != expected_evidence
        ):
            raise ContractError(
                "MERGE canonical must preserve the unique union "
                "of source/program evidence"
            )
        if set(canonical["latent_refs"]) != expected_latents:
            raise ContractError(
                "MERGE canonical must preserve all source latent refs"
            )
        if set(canonical.get("predecessor_ids", [])) != expected_predecessors:
            raise ContractError(
                "MERGE canonical must reference every source version"
            )

        aliases = [
            node
            for node in opens
            if node["node_id"] != canonical_id
        ]
        for alias in aliases:
            if (
                alias["lifecycle"] != "alias"
                or alias.get("canonical_id") != canonical_id
            ):
                raise ContractError(
                    "noncanonical MERGE sources must reopen "
                    "as aliases of the deterministic canonical ID"
                )
            source_version = next(
                source["node_version_id"]
                for source in sources
                if source["node_id"] == alias["node_id"]
            )
            if set(alias.get("predecessor_ids", [])) != {
                source_version
            }:
                raise ContractError(
                    "MERGE alias must reference its prior version"
                )
            if alias["evidence_refs"] or alias["latent_refs"]:
                raise ContractError(
                    "active MERGE aliases hold pointers only; "
                    "evidence and latents live in history/canonical"
                )

        source_id_set = set(source_ids)
        incident_edges = [
            edge for edge in graph["edges"]
            if edge.get("valid_to") is None
            and source_id_set & {edge["source"], edge["target"]}
        ]
        edge_closes = [
            operation for operation in operations
            if operation["op_type"] == "CLOSE_EDGE_VERSION"
        ]
        closed_edge_ids = [
            operation["arguments"]["edge_id"] for operation in edge_closes
        ]
        expected_edge_ids = [edge["edge_id"] for edge in incident_edges]
        if (
            len(closed_edge_ids) != len(set(closed_edge_ids))
            or set(closed_edge_ids) != set(expected_edge_ids)
        ):
            raise ContractError(
                "MERGE must close every open incident edge exactly once"
            )
        close_times = {
            operation["arguments"]["edge_id"]: operation["arguments"]["at"]
            for operation in edge_closes
        }
        if close_times and len(set(close_times.values())) != 1:
            raise ContractError("MERGE incident edges must close at one tick")

        expected_groups: dict[
            tuple[str, str, str, str], list[dict[str, Any]]
        ] = {}
        collapsed_versions: set[str] = set()
        for edge in incident_edges:
            rewritten_source = (
                canonical_id if edge["source"] in source_id_set else edge["source"]
            )
            rewritten_target = (
                canonical_id if edge["target"] in source_id_set else edge["target"]
            )
            if rewritten_source == rewritten_target:
                collapsed_versions.add(edge["edge_version_id"])
                continue
            signature = (
                rewritten_source, rewritten_target, edge["relation"], edge["frame"],
            )
            expected_groups.setdefault(signature, []).append(edge)

        edge_adds = [
            operation["arguments"]["edge"]
            for operation in operations if operation["op_type"] == "ADD_EDGE"
        ]
        actual_by_signature: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        for edge in edge_adds:
            signature = (
                edge["source"], edge["target"], edge["relation"], edge["frame"],
            )
            if signature in actual_by_signature:
                raise ContractError("MERGE cannot reopen duplicate semantic edges")
            actual_by_signature[signature] = edge
        if set(actual_by_signature) != set(expected_groups):
            raise ContractError(
                "MERGE must reopen every non-self relation on canonical endpoints"
            )

        expected_rewrites: list[tuple[tuple[str, ...], str | None, str]] = []
        for signature, group in expected_groups.items():
            successor = actual_by_signature[signature]
            identity = min(group, key=lambda edge: (
                edge["valid_from"], edge["edge_id"], edge["edge_version_id"],
            ))
            predecessor_versions = tuple(sorted(
                edge["edge_version_id"] for edge in group
            ))
            expected_evidence = {
                reference for edge in group for reference in edge["evidence_refs"]
            }
            expected_provenance = {
                reference for edge in group for reference in edge["provenance"]
            } | {
                f"merge_source_edge:{version}" for version in predecessor_versions
            } | {program["transaction_id"]}
            close_at = close_times[identity["edge_id"]]
            if (
                successor["edge_id"] != identity["edge_id"]
                or successor["edge_version_id"] in {
                    edge["edge_version_id"] for edge in graph["edges"]
                }
                or successor["valid_from"] != close_at
                or successor.get("valid_to") is not None
                or set(successor["evidence_refs"]) != expected_evidence
                or not expected_provenance <= set(successor["provenance"])
            ):
                raise ContractError(
                    "MERGE relation successor does not preserve identity, "
                    "evidence, provenance, or version timing"
                )
            expected_rewrites.append((
                predecessor_versions, successor["edge_version_id"],
                "canonicalized_or_deduplicated",
            ))
        expected_rewrites.extend(
            ((version,), None, "collapsed_self_relation")
            for version in sorted(collapsed_versions)
        )
        declared_rewrites = program.get("merge_relation_rewrites", [])
        if type(declared_rewrites) is not list:
            raise ContractError("MERGE relation rewrites must be a list")
        actual_rewrites = []
        for row in declared_rewrites:
            if type(row) is not dict or set(row) != {
                "source_edge_version_ids", "successor_edge_version_id", "reason",
            }:
                raise ContractError("MERGE relation rewrite record is malformed")
            actual_rewrites.append((
                tuple(row["source_edge_version_ids"]),
                row["successor_edge_version_id"], row["reason"],
            ))
        if sorted(actual_rewrites, key=str) != sorted(expected_rewrites, key=str):
            raise ContractError("MERGE relation rewrite audit is incomplete")
        return

    if template == "RETRACT":
        target = program.get("retraction_target")
        if not target:
            raise ContractError(
                "RETRACT requires an explicit retraction_target"
            )
        if target["kind"] == "node_version":
            _, _, _, _, negative_refs = _validate_node_retraction(
                graph,
                program,
                operations,
                target_version_id=target["version_id"],
                evidence_by_id=evidence_by_id,
                reliability_threshold=reliability_threshold,
            )
            forbidden = {
                "CREATE_NODE", "ADD_EDGE", "MOVE_EVIDENCE",
                "SET_CANONICAL_ALIAS", "SET_LIFECYCLE",
            }
            if any(op_type in forbidden for op_type in op_types):
                raise ContractError(
                    "node RETRACT may only retire its entity and incident edges"
                )
            if (
                len(program["evidence_refs"])
                != len(set(program["evidence_refs"]))
                or set(program["evidence_refs"]) != set(negative_refs)
            ):
                raise ContractError(
                    "node RETRACT may declare only its negative evidence"
                )
            return
        if target["kind"] != "edge_version":
            raise ContractError("RETRACT target kind is not supported")
        edge = _edge_version(graph, target["version_id"])
        if edge.get("valid_to") is not None:
            raise PreconditionError(
                "RETRACT target edge version is already closed"
            )
        closes = [
            operation
            for operation in operations
            if operation["op_type"] == "CLOSE_EDGE_VERSION"
        ]
        if len(closes) != 1:
            raise ContractError(
                "fact RETRACT must close exactly one edge version"
            )
        if closes[0]["arguments"]["edge_id"] != edge["edge_id"]:
            raise ContractError(
                "RETRACT operation does not match retraction_target"
            )
        forbidden = {
            "CREATE_NODE",
            "OPEN_NODE_VERSION",
            "ADD_EDGE",
            "SET_LIFECYCLE",
            "CLOSE_NODE_VERSION",
        }
        if any(op_type in forbidden for op_type in op_types):
            raise ContractError(
                "fact RETRACT cannot create, relink or retract identity"
            )
        _validate_reliable_negative_evidence(
            program,
            target_version_id=target["version_id"],
            evidence_by_id=evidence_by_id,
            reliability_threshold=reliability_threshold,
        )
        return

    if template == "COMPOSITE":
        if (
            program.get("composition_label") != "REPLACE"
            or program.get("component_templates")
            != ["RETRACT", "BIRTH"]
        ):
            raise ContractError(
                "only COMPOSITE:REPLACE=[RETRACT,BIRTH] is supported"
            )
        target = program.get("retraction_target")
        if not target:
            raise ContractError(
                "REPLACE must retract an explicit node or edge version"
            )
        if target["kind"] == "node_version":
            source, _, _, _, negative_refs = _validate_node_retraction(
                graph,
                program,
                operations,
                target_version_id=target["version_id"],
                evidence_by_id=evidence_by_id,
                reliability_threshold=reliability_threshold,
            )
            creates = [
                operation for operation in operations
                if operation["op_type"] == "CREATE_NODE"
            ]
            if len(creates) != 1:
                raise ContractError(
                    "node REPLACE must BIRTH exactly one new entity"
                )
            created = creates[0]["arguments"]["node"]
            if (
                created.get("node_type") != "entity"
                or created.get("lifecycle") != "candidate"
                or created.get("valid_to") is not None
                or created.get("node_id") == source["node_id"]
                or any(
                    node["node_id"] == created.get("node_id")
                    for node in graph["nodes"]
                )
                or set(created.get("evidence_refs", []))
                & set(source.get("evidence_refs", []))
                or program["transaction_id"] not in created.get("provenance", [])
            ):
                raise ContractError(
                    "node REPLACE BIRTH must create a distinct candidate entity "
                    "without inheriting old identity or evidence"
                )
            _validate_current_support_evidence_refs(
                created.get("evidence_refs", []),
                claim_refs={created["node_id"], created["node_version_id"]},
                evidence_by_id=evidence_by_id,
            )
            if not set(created["evidence_refs"]) <= set(program["evidence_refs"]):
                raise ContractError(
                    "node REPLACE program must declare all new-node evidence"
                )
            create_index = next(
                index for index, operation in enumerate(operations)
                if operation is creates[0]
            )
            close_indices = [
                index for index, operation in enumerate(operations)
                if operation["op_type"]
                in {"CLOSE_NODE_VERSION", "CLOSE_EDGE_VERSION"}
            ]
            if close_indices and max(close_indices) >= create_index:
                raise ContractError(
                    "node REPLACE must finish RETRACT before BIRTH"
                )

            adds = [
                (index, operation) for index, operation in enumerate(operations)
                if operation["op_type"] == "ADD_EDGE"
            ]
            signatures: set[tuple[str, str, str, str]] = set()
            for operation_index, operation in adds:
                if operation_index <= create_index:
                    raise ContractError(
                        "node REPLACE relation BIRTH must follow entity BIRTH"
                    )
                edge = operation["arguments"]["edge"]
                signature = (
                    edge["source"], edge["target"], edge["relation"], edge["frame"],
                )
                if signature in signatures:
                    raise ContractError(
                        "node REPLACE cannot create duplicate semantic relations"
                    )
                signatures.add(signature)
                if (
                    edge["source"] != created["node_id"]
                    or edge["relation"] not in {"located_at", "supported_by"}
                    or not edge.get("evidence_refs")
                    or set(edge["evidence_refs"])
                    & set(source.get("evidence_refs", []))
                    or program["transaction_id"] not in edge.get("provenance", [])
                ):
                    raise ContractError(
                        "node REPLACE relations must be current public facts of "
                        "the new entity and must not inherit old evidence"
                    )
                _validate_current_support_evidence_refs(
                    edge["evidence_refs"],
                    claim_refs={edge["edge_id"], edge["edge_version_id"]},
                    evidence_by_id=evidence_by_id,
                )
                if not set(edge["evidence_refs"]) <= set(program["evidence_refs"]):
                    raise ContractError(
                        "node REPLACE program must declare all new-relation evidence"
                    )
            forbidden = {"MOVE_EVIDENCE", "SET_CANONICAL_ALIAS", "SET_LIFECYCLE"}
            if any(op_type in forbidden for op_type in op_types):
                raise ContractError(
                    "node REPLACE cannot move old evidence, alias identities, or "
                    "rewrite lifecycle in place"
                )
            replacement_evidence = [
                *created["evidence_refs"],
                *[
                    evidence_ref
                    for _, operation in adds
                    for evidence_ref in operation["arguments"]["edge"][
                        "evidence_refs"
                    ]
                ],
            ]
            if (
                len(program["evidence_refs"])
                != len(set(program["evidence_refs"]))
                or set(program["evidence_refs"])
                != set(negative_refs) | set(replacement_evidence)
            ):
                raise ContractError(
                    "node REPLACE must declare exactly its negative, new-node, "
                    "and new-relation evidence"
                )
            return
        if target["kind"] != "edge_version":
            raise ContractError("REPLACE target kind is not supported")
        old_edge = _edge_version(graph, target["version_id"])
        if old_edge.get("valid_to") is not None:
            raise PreconditionError(
                "REPLACE target edge version is already closed"
            )
        close_indices = [
            index
            for index, operation in enumerate(operations)
            if operation["op_type"] == "CLOSE_EDGE_VERSION"
        ]
        create_indices = [
            index
            for index, operation in enumerate(operations)
            if operation["op_type"] == "CREATE_NODE"
        ]
        add_indices = [
            index
            for index, operation in enumerate(operations)
            if operation["op_type"] == "ADD_EDGE"
        ]
        if (
            len(close_indices) != 1
            or len(create_indices) != 1
            or len(add_indices) != 1
        ):
            raise ContractError(
                "REPLACE needs one RETRACT close, one BIRTH create "
                "and one new fact edge"
            )
        if not (
            close_indices[0] < create_indices[0] < add_indices[0]
        ):
            raise ContractError(
                "REPLACE order must be RETRACT then BIRTH then ADD_EDGE"
            )
        close = operations[close_indices[0]]
        created = operations[create_indices[0]]["arguments"]["node"]
        added = operations[add_indices[0]]["arguments"]["edge"]
        if close["arguments"]["edge_id"] != old_edge["edge_id"]:
            raise ContractError(
                "REPLACE close does not match retraction_target"
            )
        if created["lifecycle"] != "candidate":
            raise ContractError(
                "REPLACE BIRTH must create a candidate identity"
            )
        if any(
            node["node_id"] == created["node_id"]
            for node in graph["nodes"]
        ):
            raise PreconditionError(
                "REPLACE BIRTH identity already exists"
            )
        if added["source"] != created["node_id"]:
            raise ContractError(
                "REPLACE new fact must originate at the new identity"
            )
        if created["node_id"] == old_edge["source"]:
            raise ContractError(
                "REPLACE cannot reuse the old identity as BIRTH"
            )
        if any(
            operation["op_type"]
            in {"CLOSE_NODE_VERSION", "SET_LIFECYCLE"}
            for operation in operations
        ):
            raise ContractError(
                "REPLACE must preserve the old object identity"
            )
        _validate_reliable_negative_evidence(
            program,
            target_version_id=target["version_id"],
            evidence_by_id=evidence_by_id,
            reliability_threshold=reliability_threshold,
        )
        return


def _verify_touched_provenance(
    graph: dict[str, Any],
    touched: set[tuple[str, str]],
    transaction_id: str,
) -> None:
    for kind, version_id in touched:
        record = (
            _node_version(graph, version_id)
            if kind == "node"
            else _edge_version(graph, version_id)
        )
        if transaction_id not in record["provenance"]:
            raise InvariantViolation(
                f"touched {kind} version {version_id!r} "
                "lacks transaction provenance"
            )


def preflight_transaction(
    base_graph: dict[str, Any],
    program: dict[str, Any],
    *,
    protected_ids: Iterable[str] = (),
    evidence_by_id: Mapping[str, dict[str, Any]] | None = None,
    reliability_threshold: float = 1.0,
) -> None:
    """Reject failures knowable before applying any transaction operation.

    This validates the immutable base, program header, template-level
    preconditions and protected identifiers.  Passing preflight is not proof
    that execution will succeed: operation ordering and post-state invariants
    are deliberately left to ``execute_transaction``.
    """
    validate_graph(base_graph)
    _validate_program_header(program)

    transaction_id = program["transaction_id"]
    if transaction_id in base_graph["transaction_log"]:
        raise DuplicateTransactionError(
            f"transaction {transaction_id!r} is already committed"
        )
    if (
        program["base_graph_version"]
        != base_graph["graph_version"]
    ):
        raise VersionMismatchError(
            f"program base {program['base_graph_version']!r} != "
            f"graph version {base_graph['graph_version']!r}"
        )

    _validate_template_preconditions(
        base_graph,
        program,
        evidence_by_id=evidence_by_id or {},
        reliability_threshold=reliability_threshold,
    )
    combined_protected = (
        set(protected_ids) | set(program["protected_ids"])
    )
    for operation in program["operations"]:
        _check_protected(operation, combined_protected)


def execute_transaction(
    base_graph: dict[str, Any],
    program: dict[str, Any],
    *,
    protected_ids: Iterable[str] = (),
    evidence_by_id: Mapping[str, dict[str, Any]] | None = None,
    reliability_threshold: float = 1.0,
) -> dict[str, Any]:
    """Execute one program atomically and return a new graph snapshot.

    The input graph is never mutated. Invalid programs raise an explicit
    CPMT exception and do not return a partial state.
    """

    preflight_transaction(
        base_graph,
        program,
        protected_ids=protected_ids,
        evidence_by_id=evidence_by_id,
        reliability_threshold=reliability_threshold,
    )
    transaction_id = program["transaction_id"]

    if program["template"] == "NOOP":
        result = clone_json(base_graph)
        result["graph_hash"] = compute_graph_hash(result)
        return result

    working = clone_json(base_graph)
    working["graph_hash"] = None
    touched: set[tuple[str, str]] = set()

    for operation in program["operations"]:
        _apply_operation(working, operation, touched)

    _verify_touched_provenance(
        working,
        touched,
        transaction_id,
    )
    working["parent_version"] = base_graph["graph_version"]
    working["graph_version"] = (
        f"{base_graph['graph_version']}::{transaction_id}"
    )
    working["transaction_log"].append(transaction_id)
    working["graph_hash"] = compute_graph_hash(working)
    validate_graph(working)
    return working
