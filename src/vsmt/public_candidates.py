"""Public-only VSMT candidate construction and post-seal teacher binding.

Candidate construction accepts no private record.  It enumerates executable
programs from the validated observation packet and prior predicted memory,
preflights every program, then seals programs and online evidence together.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from itertools import product
import math
from typing import Any, Callable, Mapping

from cpmt.executor import execute_transaction
from cpmt.hashing import canonical_json, clone_json

from .contracts import (
    build_adapter_input,
    canonical_sha256,
    seal_candidate_catalog,
    seal_teacher_targets,
    validate_candidate_catalog,
    validate_observation_packet,
    validate_private_evaluation,
)
from .graph_ops import (
    SCAFFOLD_RELATIONS,
    association_components,
    association_score,
    centroid_distance,
    covering_free_space_times,
    finite_number,
    next_tick,
    node_pair_components,
    node_pair_score,
    observation_state,
    open_nodes,
    opaque_id,
    state_from_region,
    validate_threshold,
)
from .place_scaffold import place_region_node_ids
from .d213_unified_graph import validate_unsealed_candidate_rows


TEMPLATE_ORDER = (
    "NOOP", "BIND", "BIRTH", "REACTIVATE", "RELINK", "RETRACT",
    "SPLIT", "MERGE", "REPLACE",
)
LEARNED_STRUCTURE_KINDS = {"entity", "surface", "fragment"}


@dataclass(frozen=True)
class PublicCandidateConfig:
    association_rules: Mapping[str, Mapping[str, float]]
    split_minimum_separation_m: float
    free_space_reliability_threshold: float
    support_envelope_reliability_threshold: float
    support_envelope_margin_m: float
    minimum_free_space_time_separation_s: float
    maximum_candidates_per_bucket: int
    maximum_ambiguous_relation_variables: int
    maximum_relation_variants: int
    maximum_split_total_incident_edges: int
    typed_gate_contract: Mapping[str, Any] | None = None
    candidate_variant: str | None = None

    def __post_init__(self) -> None:
        if set(self.association_rules) != LEARNED_STRUCTURE_KINDS:
            raise ValueError(
                "candidate association_rules must explicitly cover "
                "entity, surface, and fragment but not place"
            )
        expected = {
            "visual_weight", "geometry_weight", "geometry_scale_m",
            "bind_threshold", "merge_threshold", "split_region_threshold",
        }
        for kind, rule in self.association_rules.items():
            if type(rule) is not dict or set(rule) != expected:
                raise ValueError(f"candidate {kind} association rule is malformed")
            visual = validate_threshold(
                rule["visual_weight"], f"{kind}.visual_weight", low=0.0, high=1.0,
            )
            geometry = validate_threshold(
                rule["geometry_weight"], f"{kind}.geometry_weight", low=0.0, high=1.0,
            )
            if not math.isclose(visual + geometry, 1.0, abs_tol=1e-12):
                raise ValueError(f"{kind} visual and geometry weights must sum to one")
            if finite_number(
                rule["geometry_scale_m"], f"{kind}.geometry_scale_m",
            ) <= 0.0:
                raise ValueError(f"{kind}.geometry_scale_m must be positive")
            for name in (
                "bind_threshold", "merge_threshold", "split_region_threshold",
            ):
                validate_threshold(
                    rule[name], f"{kind}.{name}", low=0.0, high=1.0,
                )
        if finite_number(
            self.split_minimum_separation_m, "split_minimum_separation_m",
        ) <= 0.0:
            raise ValueError("split_minimum_separation_m must be positive")
        validate_threshold(
            self.free_space_reliability_threshold,
            "free_space_reliability_threshold", low=0.0, high=1.0,
        )
        validate_threshold(
            self.support_envelope_reliability_threshold,
            "support_envelope_reliability_threshold", low=0.0, high=1.0,
        )
        if finite_number(
            self.support_envelope_margin_m,
            "support_envelope_margin_m",
        ) < 0.0:
            raise ValueError("support_envelope_margin_m must be non-negative")
        if finite_number(
            self.minimum_free_space_time_separation_s,
            "minimum_free_space_time_separation_s",
        ) <= 0.0:
            raise ValueError(
                "minimum_free_space_time_separation_s must be positive"
            )
        if (
            type(self.maximum_candidates_per_bucket) is not int
            or self.maximum_candidates_per_bucket <= 0
        ):
            raise ValueError("maximum_candidates_per_bucket must be positive")
        for name, value in (
            (
                "maximum_ambiguous_relation_variables",
                self.maximum_ambiguous_relation_variables,
            ),
            ("maximum_relation_variants", self.maximum_relation_variants),
            (
                "maximum_split_total_incident_edges",
                self.maximum_split_total_incident_edges,
            ),
        ):
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if (self.typed_gate_contract is None) != (self.candidate_variant is None):
            raise ValueError(
                "typed_gate_contract and candidate_variant must be supplied together"
            )

    def rule(self, structure_kind: str) -> Mapping[str, float]:
        return self.association_rules[structure_kind]


def _transaction_id(public_hash: str, template: str, *parts: object) -> str:
    return opaque_id(public_hash, template, *parts, prefix="transaction")


def _header(
    graph: Mapping[str, Any], public_hash: str, template: str, intent: str,
    *parts: object,
) -> dict[str, Any]:
    return {
        "schema_version": "cpmt-0.2",
        "transaction_id": _transaction_id(public_hash, template, *parts),
        "intent": intent,
        "template": template,
        "base_graph_version": graph["graph_version"],
        "operations": [],
        "evidence_refs": [],
        "protected_ids": [],
        "proposer": "deterministic",
    }


def _region_evidence_ref(region: Mapping[str, Any], purpose: str) -> str:
    return opaque_id(region["mask_sha256"], purpose, prefix="evidence")


def _node_from_region(
    region: Mapping[str, Any], *, node_id: str, version_id: str,
    transaction_id: str, tick: int, evidence_refs: list[str],
    support_envelope_reliability_threshold: float,
    predecessor_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "node_version_id": version_id,
        "node_type": region["structure_kind"],
        "lifecycle": "candidate",
        "valid_from": tick,
        "valid_to": None,
        "evidence_refs": evidence_refs,
        "latent_refs": [opaque_id(node_id, version_id, prefix="latent")],
        "canonical_id": None,
        "predecessor_ids": predecessor_ids or [],
        "provenance": [transaction_id],
        "vsmt_observation_state": state_from_region(
            region, float(region.get("decision_time_s", tick)),
            support_envelope_reliability_threshold=(
                support_envelope_reliability_threshold
            ),
        ),
    }


def _edge_successor(
    edge: Mapping[str, Any], *, target: str, version_id: str,
    transaction_id: str, tick: int, evidence_ref: str,
) -> dict[str, Any]:
    successor = clone_json(dict(edge))
    successor.update({
        "edge_version_id": version_id,
        "target": target,
        "valid_from": tick,
        "valid_to": None,
        "evidence_refs": list(dict.fromkeys(
            list(edge["evidence_refs"]) + [evidence_ref]
        )),
        "provenance": list(edge["provenance"]) + [transaction_id],
    })
    return successor


def _support_event(
    evidence_id: str, *, time_index: int, viewpoint_id: str,
    claim_ref: str, reliability: float, visible_empty: bool,
) -> dict[str, Any]:
    return {
        "schema_version": "cpmt-0.2",
        "evidence_id": evidence_id,
        "time_index": time_index,
        "viewpoint_id": viewpoint_id,
        "kind": "visible_empty" if visible_empty else "observation",
        "claim_ref": claim_ref,
        "verdict": "contradicts" if visible_empty else "supports",
        "availability": "online",
        "visibility": "visible_empty" if visible_empty else "visible",
        "pose_valid": True,
        "depth_valid": True,
        "reliability": reliability,
    }


def _covering_free_spaces(
    node: Mapping[str, Any],
    free_spaces: list[Mapping[str, Any]], *,
    minimum_reliability: float, target_expansion_m: float,
    minimum_time_separation_s: float, support_reliability_threshold: float,
) -> list[Mapping[str, Any]]:
    return covering_free_space_times(
        node, free_spaces, minimum_reliability=minimum_reliability,
        target_expansion_m=target_expansion_m,
        minimum_time_separation_s=minimum_time_separation_s,
        support_reliability_threshold=support_reliability_threshold,
    )


def _negative_evidence(
    target: Mapping[str, Any], free_spaces: list[Mapping[str, Any]], *, tick: int,
) -> dict[str, dict[str, Any]]:
    selected = free_spaces[-2:]
    target_version_id = str(
        target.get("node_version_id", target.get("edge_version_id"))
    )
    result: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(selected):
        evidence_id = opaque_id(
            target_version_id, item["support_sha256"], item["time_s"],
            prefix="evidence",
        )
        result[evidence_id] = _support_event(
            evidence_id,
            time_index=max(0, tick - 1 + index),
            viewpoint_id=str(item["free_space_id"]),
            claim_ref=target_version_id,
            reliability=float(item["reliability"]),
            visible_empty=True,
        )
    return result


def _bind_program(
    graph: Mapping[str, Any], public_hash: str, region: Mapping[str, Any],
    node: Mapping[str, Any], tick: int, *,
    support_envelope_reliability_threshold: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    program = _header(graph, public_hash, "BIND", "ASSOCIATE",
                      region["region_id"], node["node_id"])
    evidence = _region_evidence_ref(region, "bind")
    previous_state = observation_state(node)
    if previous_state is None:
        raise ValueError("node BIND target lacks shared observation state")
    successor = clone_json(dict(node))
    successor.update({
        "node_version_id": opaque_id(
            node["node_version_id"], tick, "bind", prefix="node-version",
        ),
        "valid_from": tick,
        "valid_to": None,
        "evidence_refs": list(dict.fromkeys(
            list(node["evidence_refs"]) + [evidence]
        )),
        "predecessor_ids": [node["node_version_id"]],
        "provenance": list(dict.fromkeys(
            list(node["provenance"]) + [program["transaction_id"]]
        )),
        "vsmt_observation_state": state_from_region(
            region, float(region.get("decision_time_s", tick)),
            support_envelope_reliability_threshold=(
                support_envelope_reliability_threshold
            ),
            previous=previous_state,
            fused=True,
        ),
    })
    program["evidence_refs"] = [evidence]
    program["operations"] = [
        {
            "op_id": "bind:assert", "op_type": "ASSERT_PRECONDITION",
            "arguments": {
                "kind": "node_lifecycle", "node_id": node["node_id"],
                "allowed": ["candidate", "confirmed"],
            },
        },
        {
            "op_id": "bind:close", "op_type": "CLOSE_NODE_VERSION",
            "arguments": {
                "node_id": node["node_id"], "at": tick,
            },
        },
        {
            "op_id": "bind:provenance", "op_type": "RECORD_PROVENANCE",
            "arguments": {
                "target_kind": "node", "node_version_id": node["node_version_id"],
                "provenance_ref": program["transaction_id"],
            },
        },
        {
            "op_id": "bind:open", "op_type": "OPEN_NODE_VERSION",
            "arguments": {"node": successor},
        },
    ]
    return program, {}


def _birth_program(
    graph: Mapping[str, Any], public_hash: str, region: Mapping[str, Any], tick: int,
    *, purpose: str = "birth", support_envelope_reliability_threshold: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    program = _header(graph, public_hash, "BIRTH", "EXPAND",
                      region["region_id"], purpose)
    node_id = opaque_id(public_hash, region["region_id"], purpose, prefix="node")
    evidence = _region_evidence_ref(region, purpose)
    program["evidence_refs"] = [evidence]
    node = _node_from_region(
        region, node_id=node_id,
        version_id=opaque_id(node_id, tick, purpose, prefix="node-version"),
        transaction_id=program["transaction_id"], tick=tick,
        evidence_refs=[evidence],
        support_envelope_reliability_threshold=(
            support_envelope_reliability_threshold
        ),
    )
    program["operations"] = [
        {
            "op_id": "birth:assert", "op_type": "ASSERT_PRECONDITION",
            "arguments": {"kind": "node_absent", "node_id": node_id},
        },
        {"op_id": "birth:create", "op_type": "CREATE_NODE",
         "arguments": {"node": node}},
    ]
    return program, {}


def _relation_birth_program(
    graph: Mapping[str, Any], public_hash: str,
    relation: Mapping[str, Any], *, source_node_id: str,
    target_node_id: str, tick: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    program = _header(
        graph, public_hash, "BIRTH", "EXPAND", "relation",
        relation["relation_id"], source_node_id, target_node_id,
        relation["relation"],
    )
    edge_id = opaque_id(
        public_hash, relation["relation_id"], source_node_id,
        target_node_id, relation["relation"], prefix="edge",
    )
    evidence = f"observation:{relation['support_sha256']}"
    program["evidence_refs"] = [evidence]
    program["operations"] = [{
        "op_id": "birth:relation-add",
        "op_type": "ADD_EDGE",
        "arguments": {"edge": {
            "edge_id": edge_id,
            "edge_version_id": opaque_id(edge_id, tick, prefix="edge-version"),
            "source": source_node_id,
            "target": target_node_id,
            "relation": relation["relation"],
            "frame": "map",
            "valid_from": tick,
            "valid_to": None,
            "evidence_refs": [evidence],
            "provenance": [program["transaction_id"]],
        }},
    }]
    return program, {}


def _relation_bind_program(
    graph: Mapping[str, Any], public_hash: str,
    relation: Mapping[str, Any], edge: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    program = _header(
        graph, public_hash, "BIND", "ASSOCIATE", "relation",
        relation["relation_id"], edge["edge_version_id"],
    )
    evidence = f"observation:{relation['support_sha256']}"
    program["evidence_refs"] = [evidence]
    program["operations"] = [
        {
            "op_id": "bind:relation-evidence",
            "op_type": "ATTACH_EVIDENCE",
            "arguments": {
                "target_kind": "edge",
                "target_id": edge["edge_id"],
                "evidence_ref": evidence,
            },
        },
        {
            "op_id": "bind:relation-provenance",
            "op_type": "RECORD_PROVENANCE",
            "arguments": {
                "target_kind": "edge",
                "target_id": edge["edge_id"],
                "provenance_ref": program["transaction_id"],
            },
        },
    ]
    return program, {}


def _relation_reactivate_program(
    graph: Mapping[str, Any], public_hash: str, relation: Mapping[str, Any],
    edge: Mapping[str, Any], tick: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reopen one historical relation identity from current public support."""

    program = _header(
        graph, public_hash, "REACTIVATE", "ASSOCIATE",
        edge["edge_version_id"], relation["relation_id"],
    )
    evidence = opaque_id(
        relation["support_sha256"], edge["edge_version_id"],
        "relation-reactivate", prefix="evidence",
    )
    successor = clone_json(dict(edge))
    successor.update({
        "edge_version_id": opaque_id(
            edge["edge_id"], tick, relation["support_sha256"],
            "reactivate", prefix="edge-version",
        ),
        "valid_from": tick,
        "valid_to": None,
        "evidence_refs": list(dict.fromkeys(
            list(edge["evidence_refs"]) + [evidence]
        )),
        "provenance": list(dict.fromkeys(
            list(edge["provenance"]) + [program["transaction_id"]]
        )),
    })
    program["reactivation_target"] = {
        "kind": "edge_version", "version_id": edge["edge_version_id"],
    }
    program["evidence_refs"] = [evidence]
    program["operations"] = [{
        "op_id": "relation-reactivate:add",
        "op_type": "ADD_EDGE",
        "arguments": {"edge": successor},
    }]
    return program, {evidence: _support_event(
        evidence, time_index=tick,
        viewpoint_id=str(relation["relation_id"]),
        claim_ref=successor["edge_version_id"],
        reliability=float(relation["reliability"]), visible_empty=False,
    )}


def _reactivate_program(
    graph: Mapping[str, Any], public_hash: str, region: Mapping[str, Any],
    node: Mapping[str, Any], tick: int, *,
    support_envelope_reliability_threshold: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    program = _header(graph, public_hash, "REACTIVATE", "ASSOCIATE",
                      region["region_id"], node["node_id"])
    evidence = _region_evidence_ref(region, "reactivate")
    evidence_refs = list(dict.fromkeys(
        list(node["evidence_refs"]) + [evidence]
    ))
    prior_lifecycle = (observation_state(node) or {}).get(
        "pre_dormancy_lifecycle", "confirmed",
    )
    successor_lifecycle = (
        "candidate"
        if prior_lifecycle == "candidate" and len(evidence_refs) < 2
        else "confirmed"
    )
    successor_state = state_from_region(
        region, float(region.get("decision_time_s", tick)),
        support_envelope_reliability_threshold=(
            support_envelope_reliability_threshold
        ),
        previous=observation_state(node), fused=True,
    )
    successor_state["missed_observation_opportunities"] = 0
    successor = clone_json(dict(node))
    successor.update({
        "node_version_id": opaque_id(
            node["node_version_id"], tick, "reactivate", prefix="node-version",
        ),
        "lifecycle": successor_lifecycle,
        "valid_from": tick,
        "valid_to": None,
        "evidence_refs": evidence_refs,
        "predecessor_ids": [node["node_version_id"]],
        "provenance": list(node["provenance"]) + [program["transaction_id"]],
        "vsmt_observation_state": successor_state,
    })
    program["evidence_refs"] = [evidence]
    program["operations"] = [
        {
            "op_id": "reactivate:assert", "op_type": "ASSERT_PRECONDITION",
            "arguments": {
                "kind": "node_lifecycle", "node_id": node["node_id"],
                "allowed": ["dormant"],
            },
        },
        {"op_id": "reactivate:close", "op_type": "CLOSE_NODE_VERSION",
         "arguments": {"node_id": node["node_id"], "at": tick}},
        {
            "op_id": "reactivate:provenance", "op_type": "RECORD_PROVENANCE",
            "arguments": {
                "target_kind": "node", "node_version_id": node["node_version_id"],
                "provenance_ref": program["transaction_id"],
            },
        },
        {"op_id": "reactivate:open", "op_type": "OPEN_NODE_VERSION",
         "arguments": {"node": successor}},
    ]
    return program, {}


def _relink_program(
    graph: Mapping[str, Any], public_hash: str, edge: Mapping[str, Any],
    target: Mapping[str, Any], tick: int,
    relation_observation: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    program = _header(graph, public_hash, "RELINK", "REVISE",
                      edge["edge_id"], target["node_id"])
    evidence = (
        f"observation:{relation_observation['support_sha256']}"
        if relation_observation is not None
        else opaque_id(public_hash, edge["edge_id"], target["node_id"],
                       prefix="evidence")
    )
    successor = _edge_successor(
        edge, target=str(target["node_id"]),
        version_id=opaque_id(edge["edge_version_id"], tick, target["node_id"],
                             prefix="edge-version"),
        transaction_id=program["transaction_id"], tick=tick,
        evidence_ref=evidence,
    )
    program["evidence_refs"] = [evidence]
    program["operations"] = [
        {"op_id": "relink:assert", "op_type": "ASSERT_PRECONDITION",
         "arguments": {"kind": "edge_exists", "edge_id": edge["edge_id"]}},
        {"op_id": "relink:close", "op_type": "CLOSE_EDGE_VERSION",
         "arguments": {"edge_id": edge["edge_id"], "at": tick}},
        {
            "op_id": "relink:provenance", "op_type": "RECORD_PROVENANCE",
            "arguments": {
                "target_kind": "edge", "edge_version_id": edge["edge_version_id"],
                "provenance_ref": program["transaction_id"],
            },
        },
        {"op_id": "relink:add", "op_type": "ADD_EDGE",
         "arguments": {"edge": successor}},
    ]
    return program, {}


def _retract_program(
    graph: Mapping[str, Any], public_hash: str, edge: Mapping[str, Any],
    free_spaces: list[Mapping[str, Any]], tick: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    program = _header(graph, public_hash, "RETRACT", "REVISE", edge["edge_id"])
    evidence = _negative_evidence(edge, free_spaces, tick=tick)
    program["evidence_refs"] = list(evidence)
    program["retraction_target"] = {
        "kind": "edge_version", "version_id": edge["edge_version_id"],
    }
    program["operations"] = [
        {"op_id": "retract:close", "op_type": "CLOSE_EDGE_VERSION",
         "arguments": {"edge_id": edge["edge_id"], "at": tick}},
        *[
            {
                "op_id": f"retract:attach:{index}",
                "op_type": "ATTACH_EVIDENCE",
                "arguments": {
                    "target_kind": "edge",
                    "edge_version_id": edge["edge_version_id"],
                    "evidence_ref": evidence_id,
                },
            }
            for index, evidence_id in enumerate(evidence)
        ],
        {
            "op_id": "retract:provenance", "op_type": "RECORD_PROVENANCE",
            "arguments": {
                "target_kind": "edge", "edge_version_id": edge["edge_version_id"],
                "provenance_ref": program["transaction_id"],
            },
        },
    ]
    return program, evidence


def _retired_entity_version(
    node: Mapping[str, Any], *, transaction_id: str, tick: int,
    negative_evidence_refs: list[str], purpose: str,
) -> dict[str, Any]:
    terminal = clone_json(dict(node))
    terminal.update({
        "node_version_id": opaque_id(
            node["node_version_id"], transaction_id, purpose,
            prefix="node-version",
        ),
        "lifecycle": "retracted",
        "valid_from": tick,
        "valid_to": tick,
        "evidence_refs": list(dict.fromkeys(
            list(node["evidence_refs"]) + negative_evidence_refs
        )),
        "predecessor_ids": [node["node_version_id"]],
        "provenance": list(dict.fromkeys(
            list(node["provenance"]) + [transaction_id]
        )),
    })
    return terminal


def _node_retraction_operations(
    node: Mapping[str, Any], incident_edges: list[Mapping[str, Any]], *,
    transaction_id: str, negative_evidence_refs: list[str], tick: int,
    purpose: str,
) -> list[dict[str, Any]]:
    operations: list[dict[str, Any]] = []
    for index, edge in enumerate(incident_edges):
        operations.extend([
            {
                "op_id": f"{purpose}:edge-close:{index}",
                "op_type": "CLOSE_EDGE_VERSION",
                "arguments": {"edge_id": edge["edge_id"], "at": tick},
            },
            {
                "op_id": f"{purpose}:edge-provenance:{index}",
                "op_type": "RECORD_PROVENANCE",
                "arguments": {
                    "target_kind": "edge",
                    "edge_version_id": edge["edge_version_id"],
                    "provenance_ref": transaction_id,
                },
            },
        ])
    operations.append({
        "op_id": f"{purpose}:node-close",
        "op_type": "CLOSE_NODE_VERSION",
        "arguments": {"node_id": node["node_id"], "at": tick},
    })
    operations.extend(
        {
            "op_id": f"{purpose}:node-evidence:{index}",
            "op_type": "ATTACH_EVIDENCE",
            "arguments": {
                "target_kind": "node",
                "node_version_id": node["node_version_id"],
                "evidence_ref": evidence_ref,
            },
        }
        for index, evidence_ref in enumerate(negative_evidence_refs)
    )
    operations.extend([
        {
            "op_id": f"{purpose}:node-provenance",
            "op_type": "RECORD_PROVENANCE",
            "arguments": {
                "target_kind": "node",
                "node_version_id": node["node_version_id"],
                "provenance_ref": transaction_id,
            },
        },
        {
            "op_id": f"{purpose}:terminal",
            "op_type": "OPEN_NODE_VERSION",
            "arguments": {"node": _retired_entity_version(
                node,
                transaction_id=transaction_id,
                tick=tick,
                negative_evidence_refs=negative_evidence_refs,
                purpose=purpose,
            )},
        },
    ])
    return operations


def _node_retract_program(
    graph: Mapping[str, Any], public_hash: str, node: Mapping[str, Any],
    incident_edges: list[Mapping[str, Any]],
    free_spaces: list[Mapping[str, Any]], tick: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    program = _header(
        graph, public_hash, "RETRACT", "REVISE", "node", node["node_id"],
    )
    evidence = _negative_evidence(node, free_spaces, tick=tick)
    negative_refs = list(evidence)
    program["evidence_refs"] = negative_refs
    program["retraction_target"] = {
        "kind": "node_version", "version_id": node["node_version_id"],
    }
    program["operations"] = _node_retraction_operations(
        node,
        incident_edges,
        transaction_id=program["transaction_id"],
        negative_evidence_refs=negative_refs,
        tick=tick,
        purpose="node-retract",
    )
    return program, evidence


def _split_program(
    graph: Mapping[str, Any], public_hash: str, node: Mapping[str, Any],
    left: Mapping[str, Any], right: Mapping[str, Any], tick: int, *,
    incident_edges: list[Mapping[str, Any]],
    assignment_indices: tuple[tuple[int, ...], ...],
    support_envelope_reliability_threshold: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if len(incident_edges) != len(assignment_indices):
        raise ValueError("each incident edge needs one public assignment")
    if any(
        edge["source"] == node["node_id"] and edge["target"] == node["node_id"]
        for edge in incident_edges
    ):
        raise ValueError("relation-aware SPLIT does not support a source self-edge")
    assignment_signature = [
        [edge["edge_version_id"], list(indices)]
        for edge, indices in zip(incident_edges, assignment_indices, strict=True)
    ]
    program = _header(graph, public_hash, "SPLIT", "REVISE",
                      node["node_id"], left["region_id"], right["region_id"],
                      assignment_signature)
    evidence = [
        _region_evidence_ref(left, "split-left"),
        _region_evidence_ref(right, "split-right"),
    ]
    source_evidence = list(dict.fromkeys(node["evidence_refs"]))
    partitions = [source_evidence[::2] + [evidence[0]],
                  source_evidence[1::2] + [evidence[1]]]
    program["evidence_refs"] = evidence
    program["split_successor_evidence_refs"] = evidence
    program["operations"] = []
    for edge_index, edge in enumerate(incident_edges):
        program["operations"].extend([
            {
                "op_id": f"split:edge-close:{edge_index}",
                "op_type": "CLOSE_EDGE_VERSION",
                "arguments": {"edge_id": edge["edge_id"], "at": tick},
            },
            {
                "op_id": f"split:edge-provenance:{edge_index}",
                "op_type": "RECORD_PROVENANCE",
                "arguments": {
                    "target_kind": "edge",
                    "edge_version_id": edge["edge_version_id"],
                    "provenance_ref": program["transaction_id"],
                },
            },
        ])
    program["operations"].extend([
        {"op_id": "split:close", "op_type": "CLOSE_NODE_VERSION",
         "arguments": {"node_id": node["node_id"], "at": tick}},
        {
            "op_id": "split:provenance", "op_type": "RECORD_PROVENANCE",
            "arguments": {
                "target_kind": "node", "node_version_id": node["node_version_id"],
                "provenance_ref": program["transaction_id"],
            },
        },
        {
            "op_id": "split:terminal", "op_type": "OPEN_NODE_VERSION",
            "arguments": {"node": _retired_entity_version(
                node,
                transaction_id=program["transaction_id"],
                tick=tick,
                negative_evidence_refs=[],
                purpose="split",
            )},
        },
    ])
    successors: list[dict[str, Any]] = []
    for index, (region, evidence_refs) in enumerate(
        zip((left, right), partitions, strict=True)
    ):
        node_id = opaque_id(
            public_hash, node["node_id"], region["region_id"], prefix="node",
        )
        successor = _node_from_region(
            region, node_id=node_id,
            version_id=opaque_id(node_id, tick, "split", prefix="node-version"),
            transaction_id=program["transaction_id"], tick=tick,
            evidence_refs=evidence_refs,
            support_envelope_reliability_threshold=(
                support_envelope_reliability_threshold
            ),
            predecessor_ids=[node["node_version_id"]],
        )
        successors.append(successor)
        program["operations"].append({
            "op_id": f"split:create:{index}", "op_type": "CREATE_NODE",
            "arguments": {"node": successor},
        })

    assignments: list[dict[str, Any]] = []
    for edge_index, (edge, indices) in enumerate(
        zip(incident_edges, assignment_indices, strict=True)
    ):
        successor_ids = [successors[index]["node_id"] for index in indices]
        assignments.append({
            "source_edge_version_id": edge["edge_version_id"],
            "successor_node_ids": successor_ids,
            "negative_evidence_refs": [],
        })
        for successor_index in indices:
            successor_id = successors[successor_index]["node_id"]
            replacement = clone_json(dict(edge))
            replacement.update({
                "edge_id": opaque_id(
                    public_hash, edge["edge_id"], successor_id, "split",
                    prefix="edge",
                ),
                "edge_version_id": opaque_id(
                    public_hash, edge["edge_version_id"], successor_id, tick,
                    "split", prefix="edge-version",
                ),
                "source": (
                    successor_id
                    if edge["source"] == node["node_id"] else edge["source"]
                ),
                "target": (
                    successor_id
                    if edge["target"] == node["node_id"] else edge["target"]
                ),
                "valid_from": tick,
                "valid_to": None,
                "evidence_refs": list(dict.fromkeys(
                    list(edge["evidence_refs"]) + [evidence[successor_index]]
                )),
                "provenance": list(dict.fromkeys(
                    list(edge["provenance"])
                    + [f"split_source_edge:{edge['edge_version_id']}",
                       program["transaction_id"]]
                )),
            })
            program["operations"].append({
                "op_id": f"split:edge-add:{edge_index}:{successor_index}",
                "op_type": "ADD_EDGE",
                "arguments": {"edge": replacement},
            })
    program["split_relation_assignments"] = assignments
    return program, {}


def _merge_program(
    graph: Mapping[str, Any], public_hash: str, left: Mapping[str, Any],
    right: Mapping[str, Any], tick: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    sources = [left, right]
    confirmed = [node for node in sources if node["lifecycle"] == "confirmed"]
    canonical = min(confirmed, key=lambda node: (
        int(node["valid_from"]), str(node["node_id"]),
    ))
    program = _header(graph, public_hash, "MERGE", "REVISE",
                      left["node_id"], right["node_id"])
    evidence = opaque_id(public_hash, left["node_id"], right["node_id"],
                         prefix="evidence")
    program["evidence_refs"] = [evidence]
    operations: list[dict[str, Any]] = []
    for source in sources:
        operations.extend([
            {"op_id": f"merge:close:{source['node_id']}",
             "op_type": "CLOSE_NODE_VERSION",
             "arguments": {"node_id": source["node_id"], "at": tick}},
            {"op_id": f"merge:provenance:{source['node_id']}",
             "op_type": "RECORD_PROVENANCE",
             "arguments": {
                 "target_kind": "node", "node_version_id": source["node_version_id"],
                 "provenance_ref": program["transaction_id"],
             }},
        ])
    all_evidence = list(dict.fromkeys(
        [item for source in sources for item in source["evidence_refs"]] + [evidence]
    ))
    all_latents = list(dict.fromkeys(
        item for source in sources for item in source["latent_refs"]
    ))
    predecessors = [source["node_version_id"] for source in sources]
    canonical_state = clone_json(observation_state(canonical) or {})
    source_states = [observation_state(source) or {} for source in sources]
    lowers = [state.get("support_envelope_min_m") for state in source_states]
    uppers = [state.get("support_envelope_max_m") for state in source_states]
    if all(type(value) is list and len(value) == 3 for value in lowers + uppers):
        canonical_state["support_envelope_min_m"] = [
            min(float(value[axis]) for value in lowers) for axis in range(3)
        ]
        canonical_state["support_envelope_max_m"] = [
            max(float(value[axis]) for value in uppers) for axis in range(3)
        ]
        canonical_state["support_envelope_observation_count"] = sum(
            int(state.get("support_envelope_observation_count", 0))
            for state in source_states
        )
    for source in sources:
        successor = clone_json(dict(source))
        successor.update({
            "node_version_id": opaque_id(
                source["node_version_id"], tick, "merge", prefix="node-version",
            ),
            "valid_from": tick,
            "valid_to": None,
            "predecessor_ids": (
                predecessors if source["node_id"] == canonical["node_id"]
                else [source["node_version_id"]]
            ),
            "provenance": list(source["provenance"]) + [program["transaction_id"]],
            "lifecycle": (
                "confirmed" if source["node_id"] == canonical["node_id"] else "alias"
            ),
            "canonical_id": (
                None if source["node_id"] == canonical["node_id"]
                else canonical["node_id"]
            ),
            "evidence_refs": (
                all_evidence if source["node_id"] == canonical["node_id"] else []
            ),
            "latent_refs": (
                all_latents if source["node_id"] == canonical["node_id"] else []
            ),
            "vsmt_observation_state": (
                canonical_state
                if source["node_id"] == canonical["node_id"]
                else source.get("vsmt_observation_state")
            ),
        })
        operations.append({
            "op_id": f"merge:open:{source['node_id']}",
            "op_type": "OPEN_NODE_VERSION", "arguments": {"node": successor},
        })
    source_ids = {str(source["node_id"]) for source in sources}
    incident_edges = sorted((
        edge for edge in graph["edges"]
        if edge.get("valid_to") is None
        and source_ids & {str(edge["source"]), str(edge["target"])}
    ), key=lambda edge: (
        int(edge["valid_from"]), str(edge["edge_id"]),
        str(edge["edge_version_id"]),
    ))
    rewritten_groups: dict[
        tuple[str, str, str, str], list[Mapping[str, Any]]
    ] = {}
    rewrite_rows: list[dict[str, Any]] = []
    for edge_index, edge in enumerate(incident_edges):
        source_id = (
            canonical["node_id"] if edge["source"] in source_ids else edge["source"]
        )
        target_id = (
            canonical["node_id"] if edge["target"] in source_ids else edge["target"]
        )
        operations.extend([
            {
                "op_id": f"merge:edge-close:{edge_index}",
                "op_type": "CLOSE_EDGE_VERSION",
                "arguments": {"edge_id": edge["edge_id"], "at": tick},
            },
            {
                "op_id": f"merge:edge-provenance:{edge_index}",
                "op_type": "RECORD_PROVENANCE",
                "arguments": {
                    "target_kind": "edge",
                    "edge_version_id": edge["edge_version_id"],
                    "provenance_ref": program["transaction_id"],
                },
            },
        ])
        if source_id == target_id:
            rewrite_rows.append({
                "source_edge_version_ids": [edge["edge_version_id"]],
                "successor_edge_version_id": None,
                "reason": "collapsed_self_relation",
            })
            continue
        signature = (
            str(source_id), str(target_id), str(edge["relation"]), str(edge["frame"]),
        )
        rewritten_groups.setdefault(signature, []).append(edge)

    for group_index, (signature, group) in enumerate(sorted(
        rewritten_groups.items(), key=lambda item: item[0],
    )):
        source_id, target_id, relation, frame = signature
        edge_identity = min(group, key=lambda edge: (
            int(edge["valid_from"]), str(edge["edge_id"]),
            str(edge["edge_version_id"]),
        ))
        predecessor_versions = sorted(str(edge["edge_version_id"]) for edge in group)
        successor = clone_json(dict(edge_identity))
        successor.update({
            "edge_version_id": opaque_id(
                public_hash, predecessor_versions, canonical["node_id"], tick,
                "merge-relation", prefix="edge-version",
            ),
            "source": source_id,
            "target": target_id,
            "relation": relation,
            "frame": frame,
            "valid_from": tick,
            "valid_to": None,
            "evidence_refs": list(dict.fromkeys(
                reference for edge in group for reference in edge["evidence_refs"]
            )),
            "provenance": list(dict.fromkeys([
                *(reference for edge in group for reference in edge["provenance"]),
                *(f"merge_source_edge:{version}" for version in predecessor_versions),
                program["transaction_id"],
            ])),
        })
        operations.append({
            "op_id": f"merge:edge-open:{group_index}",
            "op_type": "ADD_EDGE",
            "arguments": {"edge": successor},
        })
        rewrite_rows.append({
            "source_edge_version_ids": predecessor_versions,
            "successor_edge_version_id": successor["edge_version_id"],
            "reason": "canonicalized_or_deduplicated",
        })
    program["merge_relation_rewrites"] = sorted(
        rewrite_rows,
        key=lambda row: (
            row["source_edge_version_ids"],
            str(row["successor_edge_version_id"]),
        ),
    )
    program["operations"] = operations
    return program, {}


def _replace_program(
    graph: Mapping[str, Any], public_hash: str, edge: Mapping[str, Any],
    region: Mapping[str, Any], free_spaces: list[Mapping[str, Any]], tick: int, *,
    support_envelope_reliability_threshold: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    program = _header(graph, public_hash, "COMPOSITE", "REVISE",
                      edge["edge_id"], region["region_id"])
    program["composition_label"] = "REPLACE"
    program["component_templates"] = ["RETRACT", "BIRTH"]
    program["retraction_target"] = {
        "kind": "edge_version", "version_id": edge["edge_version_id"],
    }
    evidence = _negative_evidence(edge, free_spaces, tick=tick)
    birth_evidence = _region_evidence_ref(region, "replace-birth")
    node_id = opaque_id(public_hash, edge["edge_id"], region["region_id"],
                        prefix="node")
    evidence[birth_evidence] = _support_event(
        birth_evidence, time_index=tick,
        viewpoint_id=str(region["region_id"]), claim_ref=node_id,
        reliability=float(region["reliability"]), visible_empty=False,
    )
    new_node = _node_from_region(
        region, node_id=node_id,
        version_id=opaque_id(node_id, tick, "replace", prefix="node-version"),
        transaction_id=program["transaction_id"], tick=tick,
        evidence_refs=[birth_evidence],
        support_envelope_reliability_threshold=(
            support_envelope_reliability_threshold
        ),
    )
    new_edge_id = opaque_id(node_id, edge["target"], prefix="edge")
    new_edge = {
        "edge_id": new_edge_id,
        "edge_version_id": opaque_id(new_edge_id, tick, prefix="edge-version"),
        "source": node_id,
        "target": edge["target"],
        "relation": edge["relation"],
        "frame": edge["frame"],
        "valid_from": tick,
        "valid_to": None,
        "evidence_refs": [birth_evidence],
        "provenance": [program["transaction_id"]],
    }
    negative_ids = [key for key in evidence if key != birth_evidence]
    program["evidence_refs"] = negative_ids + [birth_evidence]
    program["operations"] = [
        {"op_id": "replace:close", "op_type": "CLOSE_EDGE_VERSION",
         "arguments": {"edge_id": edge["edge_id"], "at": tick}},
        *[
            {"op_id": f"replace:attach:{index}", "op_type": "ATTACH_EVIDENCE",
             "arguments": {
                 "target_kind": "edge", "edge_version_id": edge["edge_version_id"],
                 "evidence_ref": evidence_id,
             }}
            for index, evidence_id in enumerate(negative_ids)
        ],
        {"op_id": "replace:provenance", "op_type": "RECORD_PROVENANCE",
         "arguments": {
             "target_kind": "edge", "edge_version_id": edge["edge_version_id"],
             "provenance_ref": program["transaction_id"],
         }},
        {"op_id": "replace:create", "op_type": "CREATE_NODE",
         "arguments": {"node": new_node}},
        {"op_id": "replace:add", "op_type": "ADD_EDGE",
         "arguments": {"edge": new_edge}},
    ]
    return program, evidence


def _node_replace_program(
    graph: Mapping[str, Any], public_hash: str, node: Mapping[str, Any],
    region: Mapping[str, Any], incident_edges: list[Mapping[str, Any]],
    free_spaces: list[Mapping[str, Any]], tick: int, *,
    current_relations: list[tuple[Mapping[str, Any], str]],
    support_envelope_reliability_threshold: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build entity REPLACE without inheriting the retired identity or facts."""

    relation_signature = [
        [relation["relation_id"], target_node_id]
        for relation, target_node_id in current_relations
    ]
    program = _header(
        graph, public_hash, "COMPOSITE", "REVISE", "node", node["node_id"],
        region["region_id"], relation_signature,
    )
    program["composition_label"] = "REPLACE"
    program["component_templates"] = ["RETRACT", "BIRTH"]
    program["retraction_target"] = {
        "kind": "node_version", "version_id": node["node_version_id"],
    }
    evidence = _negative_evidence(node, free_spaces, tick=tick)
    negative_refs = list(evidence)
    birth_evidence = _region_evidence_ref(region, "node-replace-birth")
    node_id = opaque_id(
        public_hash, node["node_version_id"], region["region_id"], prefix="node",
    )
    evidence[birth_evidence] = _support_event(
        birth_evidence,
        time_index=tick,
        viewpoint_id=str(region["region_id"]),
        claim_ref=node_id,
        reliability=float(region["reliability"]),
        visible_empty=False,
    )
    created = _node_from_region(
        region,
        node_id=node_id,
        version_id=opaque_id(node_id, tick, "node-replace", prefix="node-version"),
        transaction_id=program["transaction_id"],
        tick=tick,
        evidence_refs=[birth_evidence],
        support_envelope_reliability_threshold=(
            support_envelope_reliability_threshold
        ),
    )
    operations = _node_retraction_operations(
        node,
        incident_edges,
        transaction_id=program["transaction_id"],
        negative_evidence_refs=negative_refs,
        tick=tick,
        purpose="node-replace",
    )
    operations.append({
        "op_id": "node-replace:create",
        "op_type": "CREATE_NODE",
        "arguments": {"node": created},
    })
    relation_evidence_refs: list[str] = []
    for index, (relation, target_node_id) in enumerate(current_relations):
        edge_id = opaque_id(
            node_id, relation["relation_id"], target_node_id, prefix="edge",
        )
        edge_version_id = opaque_id(
            edge_id, tick, "node-replace", prefix="edge-version",
        )
        evidence_id = opaque_id(
            relation["support_sha256"], edge_version_id,
            "node-replace-relation", prefix="evidence",
        )
        evidence[evidence_id] = _support_event(
            evidence_id,
            time_index=tick,
            viewpoint_id=str(relation["relation_id"]),
            claim_ref=edge_version_id,
            reliability=float(relation["reliability"]),
            visible_empty=False,
        )
        relation_evidence_refs.append(evidence_id)
        operations.append({
            "op_id": f"node-replace:add-relation:{index}",
            "op_type": "ADD_EDGE",
            "arguments": {"edge": {
                "edge_id": edge_id,
                "edge_version_id": edge_version_id,
                "source": node_id,
                "target": target_node_id,
                "relation": relation["relation"],
                "frame": "map",
                "valid_from": tick,
                "valid_to": None,
                "evidence_refs": [evidence_id],
                "provenance": [program["transaction_id"]],
            }},
        })
    program["evidence_refs"] = [
        *negative_refs, birth_evidence, *relation_evidence_refs,
    ]
    program["operations"] = operations
    return program, evidence


def _rank_key(score: float, signature: str) -> tuple[float, str]:
    """Return the deterministic public enumeration order of one candidate group.

    白话：这是候选组的排队号码，先按枚举优先分从高到低，同分再按程序摘要排序。
    输入一个组的优先分和其程序摘要，输出一个可比较的排队号码；例如两个同分的
    SPLIT 变体组只会按摘要决定先后，不会按枚举时间先后。它不是最终选择分，也
    不参与 teacher 打分。
    """

    return (-float(score), str(signature))


class _CandidateBucket:
    """One (template, scope) capacity bucket with an order-independent cutoff.

    白话：这个桶解决“同一批候选按不同枚举顺序产生时，封存目录不能不一样”的
    问题。输入是逐个到达的候选组和该桶容量，输出是按排队号码取到第一个放不下
    为止的保留集合，以及截断统计。例如先来 3 个候选的组放不下被截断后，后到的
    2 个候选的低分组也不能因为“恰好塞得进”而顶替它进入目录。它不改变任何阈值，
    也不决定最终提交哪个事务；超出整桶容量的组和护栏拒绝的组单独计数，不设截断线。
    """

    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.groups: list[
            tuple[
                float, str,
                list[tuple[dict[str, Any], dict[str, Any], dict[str, float]]],
            ]
        ] = []
        self.pre_cap_candidate_count = 0
        self.pre_cap_group_count = 0
        self.oversized_group_count = 0
        self.ambiguity_guard_rejected_group_count = 0
        self.total_incident_guard_rejected_node_count = 0
        self.cutoff_group_count = 0
        self.cutoff_candidate_count = 0
        self.cutoff_rank_key: tuple[float, str] | None = None
        self.current_positive_blocked_node_count = 0
        self.endpoint_pair_evaluation_count = 0

    def append_group(
        self, score: float,
        candidates: list[
            tuple[dict[str, Any], dict[str, Any], dict[str, float]]
        ],
    ) -> None:
        if not candidates:
            return
        self.pre_cap_group_count += 1
        self.pre_cap_candidate_count += len(candidates)
        if len(candidates) > self.capacity:
            self.oversized_group_count += 1
            return
        signature = canonical_sha256([
            canonical_sha256(program) for program, _, _ in candidates
        ])
        rank_key = _rank_key(score, signature)
        if self.cutoff_rank_key is not None and rank_key >= self.cutoff_rank_key:
            self.cutoff_group_count += 1
            self.cutoff_candidate_count += len(candidates)
            return
        self.groups.append((score, signature, candidates))
        ranked = sorted(self.groups, key=lambda item: _rank_key(item[0], item[1]))
        retained = []
        retained_count = 0
        cutoff_index = len(ranked)
        for index, group in enumerate(ranked):
            if retained_count + len(group[2]) > self.capacity:
                cutoff_index = index
                break
            retained.append(group)
            retained_count += len(group[2])
        discarded = ranked[cutoff_index:]
        if discarded:
            stop_key = _rank_key(discarded[0][0], discarded[0][1])
            self.cutoff_rank_key = (
                stop_key if self.cutoff_rank_key is None
                else min(stop_key, self.cutoff_rank_key)
            )
        self.cutoff_group_count += len(discarded)
        self.cutoff_candidate_count += sum(len(group[2]) for group in discarded)
        self.groups = retained

    def reject_oversized_group(self, candidate_count: int) -> None:
        if type(candidate_count) is not int or candidate_count <= self.capacity:
            raise ValueError("oversized candidate group count must exceed capacity")
        self.pre_cap_group_count += 1
        self.pre_cap_candidate_count += candidate_count
        self.oversized_group_count += 1

    def reject_ambiguity_guarded_group(self, candidate_count: int) -> None:
        if type(candidate_count) is not int or candidate_count < 1:
            raise ValueError("guarded candidate group count must be positive")
        self.pre_cap_group_count += 1
        self.pre_cap_candidate_count += candidate_count
        self.ambiguity_guard_rejected_group_count += 1
        if candidate_count > self.capacity:
            self.oversized_group_count += 1

    def reject_total_incident_guarded_node(self) -> None:
        self.total_incident_guard_rejected_node_count += 1

    def block_current_positive_node(self) -> None:
        self.current_positive_blocked_node_count += 1

    def count_endpoint_pair_evaluation(self) -> None:
        self.endpoint_pair_evaluation_count += 1

    def selected(
        self,
    ) -> list[tuple[float, dict[str, Any], dict[str, Any], dict[str, float]]]:
        return [
            (score, program, evidence, components)
            for score, _, candidates in sorted(
                self.groups, key=lambda item: _rank_key(item[0], item[1]),
            )
            for program, evidence, components in candidates
        ]


def _append(
    rows: dict[tuple[str, str], _CandidateBucket],
    template: str, scope: str, score: float,
    candidate: tuple[dict[str, Any], dict[str, Any]], *, capacity: int,
    priority_components: Mapping[str, float],
) -> None:
    bucket = rows.setdefault((template, scope), _CandidateBucket(capacity))
    bucket.append_group(score, [(
        candidate[0], candidate[1], dict(priority_components),
    )])


def _association_priority_components(
    region: Mapping[str, Any], node: Mapping[str, Any],
    rule: Mapping[str, float],
) -> dict[str, float]:
    components = association_components(
        region, node, geometry_scale_m=rule["geometry_scale_m"],
    )
    if components is None:
        raise ValueError("association priority requested for incompatible structures")
    return {
        **components,
        "visual_weight": float(rule["visual_weight"]),
        "geometry_weight": float(rule["geometry_weight"]),
    }


def _normalized_relation_endpoints(
    relation: Mapping[str, Any],
) -> tuple[str, str, str]:
    source = str(relation["source_region_id"])
    target = str(relation["target_region_id"])
    relation_type = str(relation["relation"])
    if relation_type == "contains":
        source, target = target, source
        relation_type = "located_at"
    return source, target, relation_type


def _region_match_node_ids(
    matches_by_region: Mapping[str, list[tuple[float, Mapping[str, Any]]]],
    region_id: str,
) -> set[str]:
    return {
        str(node["node_id"])
        for _, node in matches_by_region.get(region_id, [])
    }


def _public_split_assignment_options(
    *, edge: Mapping[str, Any], split_node_id: str,
    left_region_id: str, right_region_id: str,
    relation_observations: list[Mapping[str, Any]],
    matches_by_region: Mapping[str, list[tuple[float, Mapping[str, Any]]]],
) -> tuple[tuple[int, ...], ...]:
    """Use only public relation support to constrain one SPLIT edge assignment."""

    support = [False, False]
    for successor_index, successor_region_id in enumerate(
        (left_region_id, right_region_id)
    ):
        for relation in relation_observations:
            source_region_id, target_region_id, relation_type = (
                _normalized_relation_endpoints(relation)
            )
            if relation_type != edge["relation"]:
                continue
            if relation_type == "adjacent_to":
                if successor_region_id == source_region_id:
                    other_region_id = target_region_id
                elif successor_region_id == target_region_id:
                    other_region_id = source_region_id
                else:
                    continue
                other_node_id = (
                    str(edge["target"])
                    if edge["source"] == split_node_id else str(edge["source"])
                )
                if other_node_id in _region_match_node_ids(
                    matches_by_region, other_region_id,
                ):
                    support[successor_index] = True
                    break
            elif edge["source"] == split_node_id:
                if (
                    source_region_id == successor_region_id
                    and str(edge["target"]) in _region_match_node_ids(
                        matches_by_region, target_region_id,
                    )
                ):
                    support[successor_index] = True
                    break
            elif (
                target_region_id == successor_region_id
                and str(edge["source"]) in _region_match_node_ids(
                    matches_by_region, source_region_id,
                )
            ):
                support[successor_index] = True
                break
    if support == [True, False]:
        return ((0,),)
    if support == [False, True]:
        return ((1,),)
    if support == [True, True]:
        return ((0, 1),)
    return ((0,), (1,), (0, 1))


def _current_relation_choice_groups_for_new_entity(
    *,
    entity_region_id: str,
    relation_observations: list[Mapping[str, Any]],
    matches_by_region: Mapping[str, list[tuple[float, Mapping[str, Any]]]],
) -> list[list[tuple[Mapping[str, Any], str]]]:
    """Return node-agnostic public endpoint choices without taking their product."""

    groups: list[list[tuple[Mapping[str, Any], str]]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for original in relation_observations:
        relation = clone_json(dict(original))
        source_region_id, target_region_id, relation_type = (
            _normalized_relation_endpoints(relation)
        )
        relation["relation"] = relation_type
        if source_region_id != entity_region_id:
            continue
        if relation_type not in {"located_at", "supported_by"}:
            continue
        signature = (
            source_region_id,
            target_region_id,
            relation_type,
            str(relation["support_sha256"]),
        )
        if signature in seen:
            continue
        seen.add(signature)
        choices = [
            (relation, str(node["node_id"]))
            for _, node in sorted(
                matches_by_region.get(target_region_id, []),
                key=lambda item: (-item[0], str(item[1]["node_id"])),
            )
        ]
        if choices:
            groups.append(choices)
    return groups


def generate_public_candidate_catalog(
    packet: Mapping[str, Any], prior_memory: Mapping[str, Any], *,
    config: PublicCandidateConfig,
) -> dict[str, Any]:
    """Enumerate, preflight, public-shuffle, and seal executable candidates."""

    public = validate_observation_packet(packet)
    deployable_hash = canonical_sha256(build_adapter_input(public, prior_memory))
    tick = next_tick(prior_memory)
    decision_time = float(public["decision_time_s"])
    regions = [clone_json(dict(region)) for region in public["region_observations"]]
    for region in regions:
        region["decision_time_s"] = decision_time
    nodes = open_nodes(prior_memory)
    regular = [
        node for node in nodes
        if node["lifecycle"] in {"candidate", "confirmed"}
        and node.get("node_type") != "place"
    ]
    dormant = [
        node for node in nodes
        if node["lifecycle"] == "dormant" and node.get("node_type") != "place"
    ]
    edges = [edge for edge in prior_memory["edges"] if edge.get("valid_to") is None]
    historical_edges = [
        edge for edge in prior_memory["edges"] if edge.get("valid_to") is not None
    ]
    incident_by_node: dict[str, list[Mapping[str, Any]]] = {}
    for edge in edges:
        for endpoint in {edge["source"], edge["target"]}:
            incident_by_node.setdefault(endpoint, []).append(edge)
    by_id = {node["node_id"]: node for node in nodes}
    rows: dict[tuple[str, str], _CandidateBucket] = {}
    capacity = config.maximum_candidates_per_bucket

    noop = _header(prior_memory, deployable_hash, "NOOP", "PRESERVE", "noop")
    _append(
        rows, "NOOP", "global", 1.0, (noop, {}), capacity=capacity,
        priority_components={"fixed_priority": 1.0},
    )

    for region in regions:
        if region["structure_kind"] == "place":
            continue
        rule = config.rule(str(region["structure_kind"]))
        _append(
            rows, "BIRTH", str(region["structure_kind"]),
            float(region["reliability"]),
            _birth_program(
                prior_memory, deployable_hash, region, tick,
                support_envelope_reliability_threshold=(
                    config.support_envelope_reliability_threshold
                ),
            ),
            capacity=capacity,
            priority_components={
                "region_reliability": float(region["reliability"]),
            },
        )
        for node in regular:
            score = association_score(
                region, node,
                visual_weight=rule["visual_weight"],
                geometry_weight=rule["geometry_weight"],
                geometry_scale_m=rule["geometry_scale_m"],
            )
            if score >= rule["bind_threshold"]:
                _append(
                    rows, "BIND", str(region["structure_kind"]), score,
                    _bind_program(
                        prior_memory, deployable_hash, region, node, tick,
                        support_envelope_reliability_threshold=(
                            config.support_envelope_reliability_threshold
                        ),
                    ),
                    capacity=capacity,
                    priority_components=_association_priority_components(
                        region, node, rule,
                    ),
                )
        for node in dormant:
            score = association_score(
                region, node,
                visual_weight=rule["visual_weight"],
                geometry_weight=rule["geometry_weight"],
                geometry_scale_m=rule["geometry_scale_m"],
            )
            if score >= rule["bind_threshold"]:
                _append(
                    rows, "REACTIVATE", str(region["structure_kind"]), score,
                    _reactivate_program(
                        prior_memory, deployable_hash, region, node, tick,
                        support_envelope_reliability_threshold=(
                            config.support_envelope_reliability_threshold
                        ),
                    ), capacity=capacity,
                    priority_components=_association_priority_components(
                        region, node, rule,
                    ),
                )

    region_by_id = {region["region_id"]: region for region in regions}
    place_node_ids = place_region_node_ids(regions, prior_memory)
    matches_by_region: dict[str, list[tuple[float, Mapping[str, Any]]]] = {}
    for region in regions:
        if region["structure_kind"] == "place":
            node_id = place_node_ids[region["region_id"]]
            matches_by_region[region["region_id"]] = [(1.0, by_id[node_id])]
        else:
            rule = config.rule(str(region["structure_kind"]))
            matches_by_region[region["region_id"]] = [
                (score, node)
                for node in regular
                if (score := association_score(
                    region, node,
                    visual_weight=rule["visual_weight"],
                    geometry_weight=rule["geometry_weight"],
                    geometry_scale_m=rule["geometry_scale_m"],
                )) >= rule["bind_threshold"]
            ]
    seen_relation_signatures: set[tuple[str, str, str, str]] = set()
    for relation_observation in public["relation_observations"]:
        if str(relation_observation["relation"]) in SCAFFOLD_RELATIONS:
            # 由确定性地点骨架维护并在骨架回执里计数，不是方法的修订决定。
            continue
        relation = clone_json(dict(relation_observation))
        source_region_id = relation["source_region_id"]
        target_region_id = relation["target_region_id"]
        if relation["relation"] == "contains":
            source_region_id, target_region_id = target_region_id, source_region_id
            relation["relation"] = "located_at"
        if (
            relation["relation"] == "adjacent_to"
            and target_region_id < source_region_id
        ):
            source_region_id, target_region_id = target_region_id, source_region_id
        relation_signature = (
            source_region_id,
            target_region_id,
            relation["relation"],
            relation["support_sha256"],
        )
        if relation_signature in seen_relation_signatures:
            continue
        seen_relation_signatures.add(relation_signature)
        if source_region_id not in region_by_id or target_region_id not in region_by_id:
            continue
        for source_score, source_node_match in matches_by_region[source_region_id]:
            for target_score, target_node_match in matches_by_region[target_region_id]:
                if relation["relation"] in {"located_at", "supported_by"}:
                    rows.setdefault(
                        ("RELINK", f"relation:{relation['relation']}"),
                        _CandidateBucket(capacity),
                    ).count_endpoint_pair_evaluation()
                source_node = source_node_match
                target_node = target_node_match
                source_id = str(source_node["node_id"])
                target_id = str(target_node["node_id"])
                if relation["relation"] == "adjacent_to" and target_id < source_id:
                    source_id, target_id = target_id, source_id
                    source_node, target_node = target_node, source_node
                if source_id == target_id:
                    continue
                relation_score = min(
                    float(relation["reliability"]), source_score, target_score,
                )
                exact = [
                    edge for edge in edges
                    if edge["source"] == source_id
                    and edge["target"] == target_id
                    and edge["relation"] == relation["relation"]
                ]
                if exact:
                    _append(
                        rows, "BIND", f"relation:{relation['relation']}",
                        relation_score, _relation_bind_program(
                            prior_memory, deployable_hash, relation,
                            sorted(exact, key=lambda item: str(item["edge_id"]))[0],
                        ), capacity=capacity,
                        priority_components={
                            "relation_reliability": float(relation["reliability"]),
                            "source_association_score": source_score,
                            "target_association_score": target_score,
                        },
                    )
                    continue
                historical_exact = [
                    edge for edge in historical_edges
                    if edge["source"] == source_id
                    and edge["target"] == target_id
                    and edge["relation"] == relation["relation"]
                    and not any(
                        current["edge_id"] == edge["edge_id"] for current in edges
                    )
                ]
                if historical_exact:
                    historical = sorted(
                        historical_exact,
                        key=lambda item: (
                            int(item["valid_to"]), str(item["edge_version_id"]),
                        ),
                    )[-1]
                    _append(
                        rows, "REACTIVATE", f"relation:{relation['relation']}",
                        relation_score, _relation_reactivate_program(
                            prior_memory, deployable_hash, relation,
                            historical, tick,
                        ), capacity=capacity,
                        priority_components={
                            "relation_reliability": float(relation["reliability"]),
                            "source_association_score": source_score,
                            "target_association_score": target_score,
                        },
                    )
                    continue
                movable = [
                    edge for edge in edges
                    if edge["source"] == source_id
                    and edge["relation"] == relation["relation"]
                    and relation["relation"] in {
                        "located_at", "supported_by", "route_transition",
                    }
                ]
                if movable:
                    _append(
                        rows, "RELINK", f"relation:{relation['relation']}",
                        relation_score, _relink_program(
                            prior_memory, deployable_hash,
                            sorted(movable, key=lambda item: str(item["edge_id"]))[0],
                            target_node, tick, relation_observation=relation,
                        ), capacity=capacity,
                        priority_components={
                            "relation_reliability": float(relation["reliability"]),
                            "source_association_score": source_score,
                            "target_association_score": target_score,
                        },
                    )
                else:
                    _append(
                        rows, "BIRTH", f"relation:{relation['relation']}",
                        relation_score, _relation_birth_program(
                            prior_memory, deployable_hash, relation,
                            source_node_id=source_id, target_node_id=target_id,
                            tick=tick,
                        ), capacity=capacity,
                        priority_components={
                            "relation_reliability": float(relation["reliability"]),
                            "source_association_score": source_score,
                            "target_association_score": target_score,
                        },
                    )

    for node in nodes:
        if (
            node.get("node_type") not in LEARNED_STRUCTURE_KINDS
            or node.get("lifecycle") not in {"candidate", "confirmed", "dormant"}
        ):
            continue
        covering = _covering_free_spaces(
            node,
            public["free_space_observations"],
            minimum_reliability=config.free_space_reliability_threshold,
            target_expansion_m=config.support_envelope_margin_m,
            minimum_time_separation_s=config.minimum_free_space_time_separation_s,
            support_reliability_threshold=(
                config.support_envelope_reliability_threshold
            ),
        )
        if len(covering) < 2:
            continue
        reliability = min(float(item["reliability"]) for item in covering[-2:])
        incident_edges = sorted(
            incident_by_node.get(str(node["node_id"]), []),
            key=lambda edge: str(edge["edge_version_id"]),
        )
        structure_kind = str(node["node_type"])
        structure_rule = config.rule(structure_kind)
        has_current_bind_region = any(
            region["structure_kind"] == structure_kind
            and association_score(
                region, node,
                visual_weight=structure_rule["visual_weight"],
                geometry_weight=structure_rule["geometry_weight"],
                geometry_scale_m=structure_rule["geometry_scale_m"],
            ) >= structure_rule["bind_threshold"]
            for region in regions
        )
        retract_bucket = rows.setdefault(
            ("RETRACT", structure_kind), _CandidateBucket(capacity),
        )
        if has_current_bind_region:
            retract_bucket.block_current_positive_node()
        else:
            retract_program, retract_evidence = _node_retract_program(
                prior_memory, deployable_hash, node, incident_edges, covering, tick,
            )
            retract_bucket.append_group(
                reliability,
                [(retract_program, retract_evidence, {
                    "free_space_minimum_reliability": reliability,
                })],
            )
        if structure_kind != "entity":
            continue
        for region in regions:
            if region["structure_kind"] != "entity":
                continue
            relation_groups = _current_relation_choice_groups_for_new_entity(
                entity_region_id=str(region["region_id"]),
                relation_observations=public["relation_observations"],
                matches_by_region=matches_by_region,
            )
            ambiguous_variables = sum(len(group) > 1 for group in relation_groups)
            variant_count = math.prod(len(group) for group in relation_groups)
            if not relation_groups:
                variant_count = 1
            replace_bucket = rows.setdefault(
                ("REPLACE", "entity"), _CandidateBucket(capacity),
            )
            if (
                ambiguous_variables
                > config.maximum_ambiguous_relation_variables
                or variant_count > config.maximum_relation_variants
            ):
                replace_bucket.reject_ambiguity_guarded_group(variant_count)
                continue
            if variant_count > capacity:
                replace_bucket.reject_oversized_group(variant_count)
                continue
            variants = product(*relation_groups) if relation_groups else [()]
            candidate_group = []
            for variant in variants:
                current_relations = list(variant)
                program, online_evidence = _node_replace_program(
                        prior_memory,
                        deployable_hash,
                        node,
                        region,
                        incident_edges,
                        covering,
                        tick,
                        current_relations=current_relations,
                        support_envelope_reliability_threshold=(
                            config.support_envelope_reliability_threshold
                        ),
                    )
                candidate_group.append((
                    program, online_evidence, {
                        "free_space_minimum_reliability": reliability,
                        "region_reliability": float(region["reliability"]),
                        "current_relation_count": len(current_relations),
                    },
                ))
            replace_bucket.append_group(
                reliability * float(region["reliability"]), candidate_group,
            )

    for edge in edges:
        source = by_id.get(edge["source"])
        if source is None or str(edge["relation"]) in SCAFFOLD_RELATIONS:
            continue
        covering = _covering_free_spaces(
            source, public["free_space_observations"],
            minimum_reliability=config.free_space_reliability_threshold,
            target_expansion_m=config.support_envelope_margin_m,
            minimum_time_separation_s=(
                config.minimum_free_space_time_separation_s
            ),
            support_reliability_threshold=(
                config.support_envelope_reliability_threshold
            ),
        )
        if len(covering) >= 2:
            reliability = min(float(item["reliability"]) for item in covering[-2:])
            relation_scope = f"relation:{edge['relation']}"
            _append(
                rows, "RETRACT", relation_scope, reliability,
                _retract_program(
                    prior_memory, deployable_hash, edge, covering, tick,
                ), capacity=capacity,
                priority_components={
                    "free_space_minimum_reliability": reliability,
                },
            )
            for region in regions:
                if region["structure_kind"] == source.get("node_type"):
                    _append(
                        rows, "REPLACE", relation_scope,
                        reliability * float(region["reliability"]),
                        _replace_program(
                            prior_memory, deployable_hash, edge, region, covering, tick,
                            support_envelope_reliability_threshold=(
                                config.support_envelope_reliability_threshold
                            ),
                        ), capacity=capacity,
                        priority_components={
                            "free_space_minimum_reliability": reliability,
                            "region_reliability": float(region["reliability"]),
                        },
                    )

    for left_index, left in enumerate(regular):
        for right in regular[left_index + 1:]:
            if not (
                "confirmed" in {left["lifecycle"], right["lifecycle"]}
                and left.get("node_type") == right.get("node_type")
            ):
                continue
            rule = config.rule(str(left["node_type"]))
            score = node_pair_score(
                left, right,
                visual_weight=rule["visual_weight"],
                geometry_weight=rule["geometry_weight"],
                geometry_scale_m=rule["geometry_scale_m"],
            )
            if score >= rule["merge_threshold"]:
                pair_components = node_pair_components(
                    left, right, geometry_scale_m=rule["geometry_scale_m"],
                )
                if pair_components is None:
                    raise ValueError("MERGE priority requires compatible nodes")
                _append(
                    rows, "MERGE", str(left["node_type"]), score,
                    _merge_program(
                        prior_memory, deployable_hash, left, right, tick,
                    ), capacity=capacity,
                    priority_components={
                        **pair_components,
                        "visual_weight": float(rule["visual_weight"]),
                        "geometry_weight": float(rule["geometry_weight"]),
                    },
                )

    for node in regular:
        if node["lifecycle"] not in {"candidate", "confirmed"}:
            continue
        incident_edges = sorted(
            incident_by_node.get(node["node_id"], []),
            key=lambda edge: str(edge["edge_version_id"]),
        )
        split_bucket = rows.setdefault(
            ("SPLIT", str(node["node_type"])),
            _CandidateBucket(capacity),
        )
        if len(incident_edges) > config.maximum_split_total_incident_edges:
            split_bucket.reject_total_incident_guarded_node()
            continue
        if any(
                edge["source"] == node["node_id"]
                and edge["target"] == node["node_id"]
                for edge in incident_edges
        ):
            continue
        compatible = []
        rule = config.rule(str(node["node_type"]))
        for region in regions:
            if region["structure_kind"] == "place":
                continue
            score = association_score(
                region, node,
                visual_weight=rule["visual_weight"],
                geometry_weight=rule["geometry_weight"],
                geometry_scale_m=rule["geometry_scale_m"],
            )
            if score >= rule["split_region_threshold"]:
                compatible.append((score, region))
        for left_index, (left_score, left) in enumerate(compatible):
            for right_score, right in compatible[left_index + 1:]:
                if centroid_distance(left, right) < config.split_minimum_separation_m:
                    continue
                assignment_options = [
                    _public_split_assignment_options(
                        edge=edge,
                        split_node_id=str(node["node_id"]),
                        left_region_id=str(left["region_id"]),
                        right_region_id=str(right["region_id"]),
                        relation_observations=public["relation_observations"],
                        matches_by_region=matches_by_region,
                    )
                    for edge in incident_edges
                ]
                assignment_count = math.prod(
                    len(options) for options in assignment_options
                )
                ambiguous_edge_count = sum(
                    len(options) > 1 for options in assignment_options
                )
                if (
                    ambiguous_edge_count
                    > config.maximum_ambiguous_relation_variables
                ):
                    split_bucket.reject_ambiguity_guarded_group(assignment_count)
                    continue
                if assignment_count > config.maximum_relation_variants:
                    split_bucket.reject_ambiguity_guarded_group(assignment_count)
                    continue
                if assignment_count > capacity:
                    split_bucket.reject_oversized_group(assignment_count)
                    continue
                candidates = [
                    (*_split_program(
                            prior_memory, deployable_hash, node, left, right, tick,
                            incident_edges=incident_edges,
                            assignment_indices=assignment_indices,
                            support_envelope_reliability_threshold=(
                                config.support_envelope_reliability_threshold
                            ),
                        ), {
                            "left_association_score": left_score,
                            "right_association_score": right_score,
                        })
                    for assignment_indices in product(*assignment_options)
                ]
                split_bucket.append_group(
                    min(left_score, right_score), candidates,
                )

    selected: list[
        tuple[dict[str, Any], dict[str, Any], dict[str, Any]]
    ] = []
    for template in TEMPLATE_ORDER:
        for (bucket_template, scope), bucket in sorted(rows.items()):
            if bucket_template != template:
                continue
            selected.extend(
                (
                    program,
                    evidence,
                    {
                        "bucket_id": f"{bucket_template}|{scope}",
                        "enumeration_priority": score,
                        "priority_components": components,
                    },
                )
                for score, program, evidence, components in bucket.selected()
            )

    selected.sort(key=lambda item: hashlib.sha256(
        f"{deployable_hash}|{canonical_sha256(item[0])}".encode("utf-8")
    ).hexdigest())
    if config.typed_gate_contract is not None:
        validate_unsealed_candidate_rows(
            [
                {"program": program, "enumeration": enumeration}
                for program, _, enumeration in selected
            ],
            variant=str(config.candidate_variant),
            contract=config.typed_gate_contract,
        )
    programs: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    enumeration_rows: list[dict[str, Any]] = []
    for program, evidence, enumeration in selected:
        execute_transaction(
            clone_json(dict(prior_memory)), clone_json(program),
            evidence_by_id=clone_json(evidence),
            reliability_threshold=config.free_space_reliability_threshold,
        )
        programs.append(program)
        evidence_rows.append(evidence)
        enumeration_rows.append(enumeration)

    capacity_rows = [
        {
            "bucket_id": f"{template}|{scope}",
            "template": template,
            "scope": scope,
            "capacity": bucket.capacity,
            "pre_cap_candidate_count": bucket.pre_cap_candidate_count,
            "pre_cap_group_count": bucket.pre_cap_group_count,
            "retained_candidate_count": sum(
                len(group[2]) for group in bucket.groups
            ),
            "retained_group_count": len(bucket.groups),
            "oversized_group_count": bucket.oversized_group_count,
            "ambiguity_guard_rejected_group_count": (
                bucket.ambiguity_guard_rejected_group_count
            ),
            "total_incident_guard_rejected_node_count": (
                bucket.total_incident_guard_rejected_node_count
            ),
            "cutoff_group_count": bucket.cutoff_group_count,
            "cutoff_candidate_count": bucket.cutoff_candidate_count,
            "unused_capacity": bucket.capacity - sum(
                len(group[2]) for group in bucket.groups
            ),
            "current_positive_blocked_node_count": (
                bucket.current_positive_blocked_node_count
            ),
            "endpoint_pair_evaluation_count": (
                bucket.endpoint_pair_evaluation_count
            ),
            "minimum_retained_priority": (
                min(group[0] for group in bucket.groups)
                if bucket.groups else None
            ),
            "minimum_retained_priority_group_count": (
                sum(
                    group[0] == min(item[0] for item in bucket.groups)
                    for group in bucket.groups
                )
                if bucket.groups else 0
            ),
        }
        for (template, scope), bucket in sorted(rows.items())
    ]

    derivations = [{
        "name": "vsmt.public.candidates.v1",
        "public_fields": [
            "/decision_time_s", "/region_observations",
            "/relation_observations", "/free_space_observations",
            "/public_constants",
        ],
        "prior_memory_fields": [
            "/graph_version", "/nodes", "/edges", "/transaction_log",
        ],
    }]
    return seal_candidate_catalog(
        public, prior_memory, generator_id="vsmt.public.generator.v1",
        derivations=derivations, programs=programs,
        online_evidence=evidence_rows,
        enumeration_audits=enumeration_rows,
        capacity_audit=capacity_rows,
    )


CandidateScorer = Callable[[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]], float]


def label_sealed_candidates(
    catalog: Mapping[str, Any], private_evaluation: Mapping[str, Any], *,
    scorer: CandidateScorer, teacher_id: str, temperature: float,
) -> dict[str, Any]:
    """Score only the already-sealed slots; candidate generation is unreachable."""

    sealed = validate_candidate_catalog(catalog)
    private = validate_private_evaluation(private_evaluation)
    if private["public_sha256"] != sealed["public_sha256"]:
        raise ValueError("private evaluation is bound to a different public packet")
    finite_temperature = finite_number(temperature, "temperature")
    if finite_temperature <= 0.0:
        raise ValueError("temperature must be positive")
    scores = [
        finite_number(
            scorer(candidate["program"], candidate["online_evidence"], private),
            f"candidate score {candidate['candidate_id']}",
        )
        for candidate in sealed["candidates"]
    ]
    maximum = max(scores)
    weights = [math.exp((score - maximum) / finite_temperature) for score in scores]
    total = sum(weights)
    probabilities = [weight / total for weight in weights]
    return seal_teacher_targets(
        sealed, teacher_id=teacher_id, scores=scores,
        probabilities=probabilities,
    )
