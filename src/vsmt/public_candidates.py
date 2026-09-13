"""Public-only VSMT candidate construction and post-seal teacher binding.

Candidate construction accepts no private record.  It enumerates executable
programs from the validated observation packet and prior predicted memory,
preflights every program, then seals programs and online evidence together.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
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
    association_score,
    centroid_distance,
    finite_number,
    fully_covered_by_free_space,
    next_tick,
    node_pair_score,
    observation_state,
    open_nodes,
    opaque_id,
    validate_threshold,
)


TEMPLATE_ORDER = (
    "NOOP", "BIND", "BIRTH", "REACTIVATE", "RELINK", "RETRACT",
    "SPLIT", "MERGE", "REPLACE",
)


@dataclass(frozen=True)
class PublicCandidateConfig:
    visual_weight: float
    geometry_weight: float
    geometry_scale_m: float
    bind_threshold: float
    merge_threshold: float
    split_region_threshold: float
    split_minimum_separation_m: float
    free_space_reliability_threshold: float
    maximum_candidates_per_template: int

    def __post_init__(self) -> None:
        for name in ("visual_weight", "geometry_weight"):
            validate_threshold(getattr(self, name), name, low=0.0, high=1.0)
        if not math.isclose(
            self.visual_weight + self.geometry_weight, 1.0, abs_tol=1e-12,
        ):
            raise ValueError("visual and geometry weights must sum to one")
        if finite_number(self.geometry_scale_m, "geometry_scale_m") <= 0.0:
            raise ValueError("geometry_scale_m must be positive")
        for name in ("bind_threshold", "merge_threshold", "split_region_threshold"):
            validate_threshold(getattr(self, name), name, low=0.0, high=1.0)
        if finite_number(
            self.split_minimum_separation_m, "split_minimum_separation_m",
        ) <= 0.0:
            raise ValueError("split_minimum_separation_m must be positive")
        validate_threshold(
            self.free_space_reliability_threshold,
            "free_space_reliability_threshold", low=0.0, high=1.0,
        )
        if (
            type(self.maximum_candidates_per_template) is not int
            or self.maximum_candidates_per_template <= 0
        ):
            raise ValueError("maximum_candidates_per_template must be positive")


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


def _state_from_region(region: Mapping[str, Any], decision_time_s: float) -> dict[str, Any]:
    return {
        "descriptor": [float(value) for value in region["descriptor"]],
        "centroid_m": [float(value) for value in region["centroid_m"]],
        "extent_m": [float(value) for value in region["extent_m"]],
        "reliability": float(region["reliability"]),
        "last_seen_s": decision_time_s,
        "observation_count": 1,
    }


def _node_from_region(
    region: Mapping[str, Any], *, node_id: str, version_id: str,
    transaction_id: str, tick: int, evidence_refs: list[str],
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
        "vsmt_observation_state": _state_from_region(
            region, float(region.get("decision_time_s", tick)),
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
    node: Mapping[str, Any], free_spaces: list[Mapping[str, Any]], *,
    minimum_reliability: float,
) -> list[Mapping[str, Any]]:
    rows = [
        item for item in free_spaces
        if fully_covered_by_free_space(
            node, [item], minimum_reliability=minimum_reliability,
        )
    ]
    distinct_times: dict[float, Mapping[str, Any]] = {}
    for item in rows:
        distinct_times.setdefault(float(item["time_s"]), item)
    return [distinct_times[key] for key in sorted(distinct_times)]


def _negative_evidence(
    edge: Mapping[str, Any], free_spaces: list[Mapping[str, Any]], *, tick: int,
) -> dict[str, dict[str, Any]]:
    selected = free_spaces[-2:]
    result: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(selected):
        evidence_id = opaque_id(
            edge["edge_version_id"], item["support_sha256"], item["time_s"],
            prefix="evidence",
        )
        result[evidence_id] = _support_event(
            evidence_id,
            time_index=max(0, tick - 1 + index),
            viewpoint_id=str(item["free_space_id"]),
            claim_ref=str(edge["edge_version_id"]),
            reliability=float(item["reliability"]),
            visible_empty=True,
        )
    return result


def _bind_program(
    graph: Mapping[str, Any], public_hash: str, region: Mapping[str, Any],
    node: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    program = _header(graph, public_hash, "BIND", "ASSOCIATE",
                      region["region_id"], node["node_id"])
    evidence = _region_evidence_ref(region, "bind")
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
            "op_id": "bind:attach", "op_type": "ATTACH_EVIDENCE",
            "arguments": {
                "target_kind": "node", "target_id": node["node_id"],
                "evidence_ref": evidence,
            },
        },
        {
            "op_id": "bind:provenance", "op_type": "RECORD_PROVENANCE",
            "arguments": {
                "target_kind": "node", "target_id": node["node_id"],
                "provenance_ref": program["transaction_id"],
            },
        },
    ]
    return program, {}


def _birth_program(
    graph: Mapping[str, Any], public_hash: str, region: Mapping[str, Any], tick: int,
    *, purpose: str = "birth",
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


def _reactivate_program(
    graph: Mapping[str, Any], public_hash: str, region: Mapping[str, Any],
    node: Mapping[str, Any], tick: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    program = _header(graph, public_hash, "REACTIVATE", "ASSOCIATE",
                      region["region_id"], node["node_id"])
    evidence = _region_evidence_ref(region, "reactivate")
    successor = clone_json(dict(node))
    successor.update({
        "node_version_id": opaque_id(
            node["node_version_id"], tick, "reactivate", prefix="node-version",
        ),
        "lifecycle": "confirmed",
        "valid_from": tick,
        "valid_to": None,
        "evidence_refs": list(dict.fromkeys(
            list(node["evidence_refs"]) + [evidence]
        )),
        "predecessor_ids": [node["node_version_id"]],
        "provenance": list(node["provenance"]) + [program["transaction_id"]],
        "vsmt_observation_state": _state_from_region(region, float(tick)),
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
) -> tuple[dict[str, Any], dict[str, Any]]:
    program = _header(graph, public_hash, "RELINK", "REVISE",
                      edge["edge_id"], target["node_id"])
    evidence = opaque_id(public_hash, edge["edge_id"], target["node_id"],
                         prefix="evidence")
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


def _split_program(
    graph: Mapping[str, Any], public_hash: str, node: Mapping[str, Any],
    left: Mapping[str, Any], right: Mapping[str, Any], tick: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    program = _header(graph, public_hash, "SPLIT", "REVISE",
                      node["node_id"], left["region_id"], right["region_id"])
    evidence = [
        _region_evidence_ref(left, "split-left"),
        _region_evidence_ref(right, "split-right"),
    ]
    source_evidence = list(dict.fromkeys(node["evidence_refs"]))
    partitions = [source_evidence[::2] + [evidence[0]],
                  source_evidence[1::2] + [evidence[1]]]
    program["evidence_refs"] = evidence
    program["operations"] = [
        {
            "op_id": "split:lifecycle", "op_type": "SET_LIFECYCLE",
            "arguments": {
                "node_id": node["node_id"], "from": node["lifecycle"],
                "to": "retracted",
            },
        },
        {"op_id": "split:close", "op_type": "CLOSE_NODE_VERSION",
         "arguments": {"node_id": node["node_id"], "at": tick}},
        {
            "op_id": "split:provenance", "op_type": "RECORD_PROVENANCE",
            "arguments": {
                "target_kind": "node", "node_version_id": node["node_version_id"],
                "provenance_ref": program["transaction_id"],
            },
        },
    ]
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
            predecessor_ids=[node["node_version_id"]],
        )
        program["operations"].append({
            "op_id": f"split:create:{index}", "op_type": "CREATE_NODE",
            "arguments": {"node": successor},
        })
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
        })
        operations.append({
            "op_id": f"merge:open:{source['node_id']}",
            "op_type": "OPEN_NODE_VERSION", "arguments": {"node": successor},
        })
    program["operations"] = operations
    return program, {}


def _replace_program(
    graph: Mapping[str, Any], public_hash: str, edge: Mapping[str, Any],
    region: Mapping[str, Any], free_spaces: list[Mapping[str, Any]], tick: int,
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


def _append(
    rows: dict[str, list[tuple[float, dict[str, Any], dict[str, Any]]]],
    template: str, score: float,
    candidate: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    rows[template].append((score, candidate[0], candidate[1]))


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
    regular = [node for node in nodes if node["lifecycle"] in {"candidate", "confirmed"}]
    dormant = [node for node in nodes if node["lifecycle"] == "dormant"]
    edges = [edge for edge in prior_memory["edges"] if edge.get("valid_to") is None]
    places = [node for node in regular if node.get("node_type") == "place"]
    by_id = {node["node_id"]: node for node in nodes}
    rows: dict[str, list[tuple[float, dict[str, Any], dict[str, Any]]]] = {
        template: [] for template in TEMPLATE_ORDER
    }

    noop = _header(prior_memory, deployable_hash, "NOOP", "PRESERVE", "noop")
    _append(rows, "NOOP", 1.0, (noop, {}))

    for region in regions:
        _append(rows, "BIRTH", float(region["reliability"]),
                _birth_program(prior_memory, deployable_hash, region, tick))
        for node in regular:
            score = association_score(
                region, node,
                visual_weight=config.visual_weight,
                geometry_weight=config.geometry_weight,
                geometry_scale_m=config.geometry_scale_m,
            )
            if score >= config.bind_threshold:
                _append(rows, "BIND", score,
                        _bind_program(prior_memory, deployable_hash, region, node))
        for node in dormant:
            score = association_score(
                region, node,
                visual_weight=config.visual_weight,
                geometry_weight=config.geometry_weight,
                geometry_scale_m=config.geometry_scale_m,
            )
            if score >= config.bind_threshold:
                _append(rows, "REACTIVATE", score, _reactivate_program(
                    prior_memory, deployable_hash, region, node, tick,
                ))

    for edge in edges:
        for target in places:
            if target["node_id"] != edge["target"]:
                _append(rows, "RELINK", 1.0, _relink_program(
                    prior_memory, deployable_hash, edge, target, tick,
                ))
        source = by_id.get(edge["source"])
        if source is None:
            continue
        covering = _covering_free_spaces(
            source, public["free_space_observations"],
            minimum_reliability=config.free_space_reliability_threshold,
        )
        if len(covering) >= 2:
            reliability = min(float(item["reliability"]) for item in covering[-2:])
            _append(rows, "RETRACT", reliability, _retract_program(
                prior_memory, deployable_hash, edge, covering, tick,
            ))
            for region in regions:
                if region["structure_kind"] == source.get("node_type"):
                    _append(rows, "REPLACE", reliability * float(region["reliability"]),
                            _replace_program(
                                prior_memory, deployable_hash, edge, region, covering, tick,
                            ))

    for left_index, left in enumerate(regular):
        for right in regular[left_index + 1:]:
            if not (
                "confirmed" in {left["lifecycle"], right["lifecycle"]}
                and left.get("node_type") == right.get("node_type")
            ):
                continue
            score = node_pair_score(
                left, right,
                visual_weight=config.visual_weight,
                geometry_weight=config.geometry_weight,
                geometry_scale_m=config.geometry_scale_m,
            )
            if score >= config.merge_threshold:
                _append(rows, "MERGE", score, _merge_program(
                    prior_memory, deployable_hash, left, right, tick,
                ))

    incident_node_ids = {
        endpoint
        for edge in edges
        for endpoint in (edge["source"], edge["target"])
    }
    for node in regular:
        if node["lifecycle"] not in {"candidate", "confirmed"}:
            continue
        # Until public relation reassignment is enumerated, SPLIT is executable
        # only for nodes without an open incident edge.
        if node["node_id"] in incident_node_ids:
            continue
        compatible = []
        for region in regions:
            score = association_score(
                region, node,
                visual_weight=config.visual_weight,
                geometry_weight=config.geometry_weight,
                geometry_scale_m=config.geometry_scale_m,
            )
            if score >= config.split_region_threshold:
                compatible.append((score, region))
        for left_index, (left_score, left) in enumerate(compatible):
            for right_score, right in compatible[left_index + 1:]:
                if centroid_distance(left, right) < config.split_minimum_separation_m:
                    continue
                _append(rows, "SPLIT", min(left_score, right_score), _split_program(
                    prior_memory, deployable_hash, node, left, right, tick,
                ))

    selected: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for template in TEMPLATE_ORDER:
        ranked = sorted(
            rows[template],
            key=lambda item: (-item[0], canonical_sha256(item[1])),
        )[:config.maximum_candidates_per_template]
        selected.extend((program, evidence) for _, program, evidence in ranked)

    selected.sort(key=lambda item: hashlib.sha256(
        f"{deployable_hash}|{canonical_sha256(item[0])}".encode("utf-8")
    ).hexdigest())
    programs: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    for program, evidence in selected:
        execute_transaction(
            clone_json(dict(prior_memory)), clone_json(program),
            evidence_by_id=clone_json(evidence),
            reliability_threshold=config.free_space_reliability_threshold,
        )
        programs.append(program)
        evidence_rows.append(evidence)

    derivations = [{
        "name": "vsmt.public.candidates.v1",
        "public_fields": [
            "/decision_time_s", "/region_observations",
            "/free_space_observations", "/public_constants",
        ],
        "prior_memory_fields": [
            "/graph_version", "/nodes", "/edges", "/transaction_log",
        ],
    }]
    return seal_candidate_catalog(
        public, prior_memory, generator_id="vsmt.public.generator.v1",
        derivations=derivations, programs=programs,
        online_evidence=evidence_rows,
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
