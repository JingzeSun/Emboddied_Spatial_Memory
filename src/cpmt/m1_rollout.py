"""Procedural continuous 20-decision rollouts for frozen-pretest M1.

This module validates the missing persistent-sequence interface.  It creates
varied spatial graphs, shuffles independent event instances, executes every
candidate from one immutable per-step base, and advances the reference world
with the actually executed reference transaction.  Only train/validation are
available; this is controlled structural data rather than PNO or formal test.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from .errors import CPMTError
from .executor import execute_transaction, validate_graph
from .hashing import canonical_json, clone_json, seal_graph
from .m1_data import project_structural_observation, validate_online_payload
from .m1_protocol import validate_m1_protocol


SPLIT_SEED_OFFSET = {"train": 0, "validation": 200_000_000}
ASSET_BUCKETS = {"train": range(100, 132), "validation": range(132, 140)}
ROLLOUT_TEMPLATE_COUNTS = {
    "NOOP": 3,
    "BIND": 4,
    "BIRTH": 3,
    "REACTIVATE": 1,
    "RELINK": 3,
    "RETRACT": 3,
    "SPLIT": 1,
    "MERGE": 1,
    "REPLACE": 1,
}
TEMPLATE_FAMILY = {
    "NOOP": "C00",
    "BIND": "C01",
    "BIRTH": "C02",
    "REACTIVATE": "C03",
    "SPLIT": "C04",
    "MERGE": "C05",
    "REPLACE": "C06",
    "RETRACT": "C07",
    "RELINK": "C08",
}


def _node(
    node_id: str, node_type: str, lifecycle: str, evidence_refs: list[str],
    latent_refs: list[str], provenance: str, *, valid_from: int = 0,
) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "node_version_id": f"{node_id}@v0",
        "node_type": node_type,
        "lifecycle": lifecycle,
        "valid_from": valid_from,
        "valid_to": None,
        "evidence_refs": evidence_refs,
        "latent_refs": latent_refs,
        "canonical_id": None,
        "predecessor_ids": [],
        "provenance": [provenance],
    }


def _edge(
    edge_id: str, source: str, target: str, relation: str,
    evidence_refs: list[str], provenance: str,
) -> dict[str, Any]:
    return {
        "edge_id": edge_id,
        "edge_version_id": f"{edge_id}@v0",
        "source": source,
        "target": target,
        "relation": relation,
        "frame": "world",
        "valid_from": 0,
        "valid_to": None,
        "evidence_refs": evidence_refs,
        "provenance": [provenance],
    }


def _open_node(graph: Mapping[str, Any], node_id: str) -> dict[str, Any]:
    matches = [
        node for node in graph["nodes"]
        if node["node_id"] == node_id and node.get("valid_to") is None
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one open node {node_id!r}, found {len(matches)}")
    return matches[0]


def _open_edge(graph: Mapping[str, Any], edge_id: str) -> dict[str, Any]:
    matches = [
        edge for edge in graph["edges"]
        if edge["edge_id"] == edge_id and edge.get("valid_to") is None
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one open edge {edge_id!r}, found {len(matches)}")
    return matches[0]


def _initial_world(
    split: str, sequence_index: int, rng: np.random.Generator,
) -> tuple[dict[str, Any], dict[str, Any]]:
    namespace = f"rollout:{split}:{sequence_index:06d}"
    provenance = f"generator:{namespace}"
    place_count = int(rng.integers(4, 8))
    surface_count = int(rng.integers(1, 4))
    filler_count = int(rng.integers(2, 8))
    places = [f"{namespace}:place:{index}" for index in range(place_count)]
    surfaces = [f"{namespace}:surface:{index}" for index in range(surface_count)]
    protected = surfaces[0]
    special = {
        "bind_target": f"{namespace}:entity:bind",
        "dormant_target": f"{namespace}:entity:dormant",
        "split_source": f"{namespace}:entity:conflated",
        "merge_a": f"{namespace}:entity:merge-a",
        "merge_b": f"{namespace}:entity:merge-b",
        "replace_entity": f"{namespace}:entity:replace-old",
        "replace_edge": f"{namespace}:edge:replace-location",
        "decoy_target": f"{namespace}:entity:decoy",
        "protected_id": protected,
        "places": places,
        "mover_ids": [f"{namespace}:entity:mover:{index}" for index in range(3)],
        "mover_edges": [f"{namespace}:edge:mover-location:{index}" for index in range(3)],
        "retract_ids": [f"{namespace}:entity:retract:{index}" for index in range(3)],
        "retract_edges": [f"{namespace}:edge:retract-location:{index}" for index in range(3)],
    }
    nodes = [
        _node(place, "place", "confirmed", [f"map:{place}"],
              [f"latent:{place}"], provenance)
        for place in places
    ]
    nodes.extend(
        _node(surface, "surface", "confirmed", [f"map:{surface}"],
              [f"latent:{surface}"], provenance)
        for surface in surfaces
    )
    nodes.extend([
        _node(special["bind_target"], "entity", "confirmed",
              [f"obs:{namespace}:bind:t0"], [f"latent:{namespace}:bind"], provenance),
        _node(special["dormant_target"], "entity", "dormant",
              [f"obs:{namespace}:dormant:t0"], [f"latent:{namespace}:dormant"], provenance),
        _node(special["split_source"], "entity", "confirmed",
              [f"obs:{namespace}:split:left:t0", f"obs:{namespace}:split:right:t0"],
              [f"latent:{namespace}:split:aggregate"], provenance),
        _node(special["merge_a"], "entity", "confirmed",
              [f"obs:{namespace}:merge:a:t0"], [f"latent:{namespace}:merge:a"], provenance),
        _node(special["merge_b"], "entity", "confirmed",
              [f"obs:{namespace}:merge:b:t0"], [f"latent:{namespace}:merge:b"], provenance),
        _node(special["replace_entity"], "entity", "confirmed",
              [f"obs:{namespace}:replace:t0"], [f"latent:{namespace}:replace"], provenance),
        _node(special["decoy_target"], "entity", "confirmed",
              [f"obs:{namespace}:decoy:t0"], [f"latent:{namespace}:decoy"], provenance),
    ])
    for node_id in special["mover_ids"] + special["retract_ids"]:
        nodes.append(_node(
            node_id, "entity", "confirmed", [f"obs:{node_id}:t0"],
            [f"latent:{node_id}"], provenance,
        ))
    filler_ids = [f"{namespace}:entity:filler:{index}" for index in range(filler_count)]
    for node_id in filler_ids:
        nodes.append(_node(
            node_id, "entity", "confirmed", [f"obs:{node_id}:t0"],
            [f"latent:{node_id}"], provenance,
        ))

    edges: list[dict[str, Any]] = []
    for index, place in enumerate(places):
        edges.append(_edge(
            f"{namespace}:edge:route:{index}", place,
            places[(index + 1) % place_count], "leads_to",
            [f"map:{namespace}:route:{index}"], provenance,
        ))
    for index, surface in enumerate(surfaces):
        edges.append(_edge(
            f"{namespace}:edge:surface:{index}", surface,
            places[index % place_count], "anchored_at",
            [f"map:{namespace}:surface:{index}"], provenance,
        ))
    located_entities = [special["bind_target"], special["replace_entity"],
                        special["decoy_target"]] + special["mover_ids"] \
        + special["retract_ids"] + filler_ids
    for index, node_id in enumerate(located_entities):
        if node_id == special["replace_entity"]:
            edge_id = special["replace_edge"]
        elif node_id in special["mover_ids"]:
            edge_id = special["mover_edges"][special["mover_ids"].index(node_id)]
        elif node_id in special["retract_ids"]:
            edge_id = special["retract_edges"][special["retract_ids"].index(node_id)]
        else:
            edge_id = f"{namespace}:edge:location:{index}"
        target_index = int(rng.integers(0, place_count))
        edges.append(_edge(
            edge_id, node_id, places[target_index], "located_at",
            [f"obs:{namespace}:location:{index}"], provenance,
        ))
    graph = seal_graph({
        "schema_version": "cpmt-0.2",
        "graph_id": f"world:{namespace}",
        "graph_version": "v0",
        "parent_version": None,
        "nodes": nodes,
        "edges": edges,
        "transaction_log": [],
        "graph_hash": None,
    })
    validate_graph(graph)
    topology = {
        "namespace": namespace,
        "place_count": place_count,
        "surface_count": surface_count,
        "filler_entity_count": filler_count,
        "initial_node_count": len(nodes),
        "initial_edge_count": len(edges),
        "special": special,
    }
    return graph, topology


def _event_plan(
    topology: Mapping[str, Any], rng: np.random.Generator,
) -> list[dict[str, Any]]:
    namespace = topology["namespace"]
    special = topology["special"]
    places = special["places"]
    templates = [
        template
        for template, count in ROLLOUT_TEMPLATE_COUNTS.items()
        for _ in range(count)
    ]
    rng.shuffle(templates)
    counters = {template: 0 for template in ROLLOUT_TEMPLATE_COUNTS}
    events = []
    for step_index, template in enumerate(templates):
        ordinal = counters[template]
        counters[template] += 1
        event_id = f"{namespace}:event:{template.lower()}:{ordinal}"
        event = {
            "event_id": event_id,
            "step_index": step_index,
            "decision_time": step_index + 1,
            "scenario_family": TEMPLATE_FAMILY[template],
            "primary_template": template,
            "candidate_seed": int(rng.integers(0, 2**31 - 1)),
            "pose_bucket": int(rng.integers(0, 8)),
            "cue_value": float(rng.choice([-1.0, -0.5, 0.5, 1.0])),
            "current_evidence_ref": f"obs:{event_id}:current",
            "contrast_birth_id": f"{namespace}:entity:contrast-birth:{step_index}",
            "protected_id": special["protected_id"],
            "bind_target": special["bind_target"],
        }
        if template == "BIRTH":
            event["new_node_id"] = f"{namespace}:entity:birth:{ordinal}"
        elif template == "REACTIVATE":
            event["target_node_id"] = special["dormant_target"]
        elif template == "RELINK":
            event["target_edge_id"] = special["mover_edges"][ordinal]
            event["new_target"] = places[(ordinal + 2) % len(places)]
        elif template == "RETRACT":
            event["target_edge_id"] = special["retract_edges"][ordinal]
        elif template == "SPLIT":
            event["target_node_id"] = special["split_source"]
            event["successor_ids"] = [
                f"{namespace}:entity:split:left",
                f"{namespace}:entity:split:right",
            ]
        elif template == "MERGE":
            event["target_node_ids"] = [special["merge_a"], special["merge_b"]]
        elif template == "REPLACE":
            event["target_edge_id"] = special["replace_edge"]
            event["new_node_id"] = f"{namespace}:entity:replace-new"
            event["new_target"] = places[-1]
        events.append(event)
    if counters != ROLLOUT_TEMPLATE_COUNTS:
        raise AssertionError("rollout event plan lost a registered template")
    return events


def _ambiguity_pivot(events: Sequence[Mapping[str, Any]]) -> int:
    """Choose one middle decision whose legal contrast changes the world."""
    for step_index in range(5, min(15, len(events))):
        if events[step_index]["primary_template"] != "NOOP":
            return step_index
    raise ValueError("20-step event plan has no eligible ambiguity pivot")


def _program_header(
    graph: Mapping[str, Any], event: Mapping[str, Any], template: str,
    *, suffix: str, intent: str,
) -> dict[str, Any]:
    return {
        "schema_version": "cpmt-0.2",
        "transaction_id": f"tx:{event['event_id']}:{suffix}",
        "intent": intent,
        "template": template,
        "base_graph_version": graph["graph_version"],
        "operations": [],
        "evidence_refs": [event["current_evidence_ref"]],
        "protected_ids": [event["protected_id"]],
        "declared_edit_cost": 0.0,
        "declared_growth_cost": 0.0,
        "proposer": "fixed_m1_rollout_generator",
    }


def _noop_program(graph: Mapping[str, Any], event: Mapping[str, Any]) -> dict[str, Any]:
    return _program_header(graph, event, "NOOP", suffix="noop", intent="PRESERVE")


def _bind_program(
    graph: Mapping[str, Any], event: Mapping[str, Any], target: str,
    *, suffix: str,
) -> dict[str, Any]:
    program = _program_header(graph, event, "BIND", suffix=suffix, intent="ASSOCIATE")
    tx = program["transaction_id"]
    evidence = f"{event['current_evidence_ref']}:{suffix}"
    program["evidence_refs"] = [evidence]
    program["declared_edit_cost"] = 0.25
    program["operations"] = [
        {"op_id": f"{suffix}:assert", "op_type": "ASSERT_PRECONDITION",
         "arguments": {"kind": "node_lifecycle", "node_id": target,
                       "allowed": ["candidate", "confirmed"]}},
        {"op_id": f"{suffix}:attach", "op_type": "ATTACH_EVIDENCE",
         "arguments": {"target_kind": "node", "target_id": target,
                       "evidence_ref": evidence}},
        {"op_id": f"{suffix}:provenance", "op_type": "RECORD_PROVENANCE",
         "arguments": {"target_kind": "node", "target_id": target,
                       "provenance_ref": tx}},
    ]
    return program


def _birth_program(
    graph: Mapping[str, Any], event: Mapping[str, Any], node_id: str,
    *, suffix: str,
) -> dict[str, Any]:
    program = _program_header(graph, event, "BIRTH", suffix=suffix, intent="EXPAND")
    tx = program["transaction_id"]
    evidence = f"{event['current_evidence_ref']}:{suffix}"
    program["evidence_refs"] = [evidence]
    program["declared_edit_cost"] = 1.0
    program["declared_growth_cost"] = 1.0
    program["operations"] = [
        {"op_id": f"{suffix}:assert", "op_type": "ASSERT_PRECONDITION",
         "arguments": {"kind": "node_absent", "node_id": node_id}},
        {"op_id": f"{suffix}:create", "op_type": "CREATE_NODE", "arguments": {
            "node": _node(
                node_id, "entity", "candidate", [evidence],
                [f"latent:{node_id}"], tx, valid_from=event["decision_time"],
            )
        }},
    ]
    return program


def _reactivate_program(
    graph: Mapping[str, Any], event: Mapping[str, Any],
) -> dict[str, Any]:
    node = _open_node(graph, event["target_node_id"])
    program = _program_header(
        graph, event, "REACTIVATE", suffix="reactivate", intent="ASSOCIATE",
    )
    tx = program["transaction_id"]
    evidence = f"{event['current_evidence_ref']}:reactivate"
    program["evidence_refs"] = [evidence]
    program["declared_edit_cost"] = 0.5
    new_version = f"{node['node_id']}@r{event['step_index']}"
    program["operations"] = [
        {"op_id": "reactivate:assert", "op_type": "ASSERT_PRECONDITION",
         "arguments": {"kind": "node_lifecycle", "node_id": node["node_id"],
                       "allowed": ["dormant"]}},
        {"op_id": "reactivate:close", "op_type": "CLOSE_NODE_VERSION",
         "arguments": {"node_id": node["node_id"], "at": event["decision_time"]}},
        {"op_id": "reactivate:old-provenance", "op_type": "RECORD_PROVENANCE",
         "arguments": {"target_kind": "node", "node_version_id": node["node_version_id"],
                       "provenance_ref": tx}},
        {"op_id": "reactivate:open", "op_type": "OPEN_NODE_VERSION", "arguments": {
            "node": {
                **_node(node["node_id"], "entity", "confirmed",
                        list(dict.fromkeys(node["evidence_refs"] + [evidence])),
                        list(node["latent_refs"]), tx,
                        valid_from=event["decision_time"]),
                "node_version_id": new_version,
                "predecessor_ids": [node["node_version_id"]],
            }
        }},
    ]
    return program


def _relink_program(
    graph: Mapping[str, Any], event: Mapping[str, Any],
) -> dict[str, Any]:
    edge = _open_edge(graph, event["target_edge_id"])
    target = event["new_target"]
    if target == edge["target"]:
        places = event["places"]
        target = places[(places.index(target) + 1) % len(places)]
    program = _program_header(graph, event, "RELINK", suffix="relink", intent="REVISE")
    tx = program["transaction_id"]
    evidence = f"{event['current_evidence_ref']}:relink"
    program["evidence_refs"] = [evidence]
    program["declared_edit_cost"] = 1.0
    program["operations"] = [
        {"op_id": "relink:assert", "op_type": "ASSERT_PRECONDITION",
         "arguments": {"kind": "edge_exists", "edge_id": edge["edge_id"]}},
        {"op_id": "relink:close", "op_type": "CLOSE_EDGE_VERSION",
         "arguments": {"edge_id": edge["edge_id"], "at": event["decision_time"]}},
        {"op_id": "relink:old-provenance", "op_type": "RECORD_PROVENANCE",
         "arguments": {"target_kind": "edge", "edge_version_id": edge["edge_version_id"],
                       "provenance_ref": tx}},
        {"op_id": "relink:open", "op_type": "ADD_EDGE", "arguments": {"edge": {
            **_edge(edge["edge_id"], edge["source"], target, edge["relation"],
                    [evidence], tx),
            "edge_version_id": f"{edge['edge_id']}@r{event['step_index']}",
            "valid_from": event["decision_time"],
        }}},
    ]
    return program


def _negative_events(
    edge: Mapping[str, Any], event: Mapping[str, Any], suffix: str,
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    evidence_ids = [
        f"ev:{event['event_id']}:{suffix}:a",
        f"ev:{event['event_id']}:{suffix}:b",
    ]
    times = [max(0, int(event["decision_time"]) - 1), int(event["decision_time"])]
    records = {}
    for index, (evidence_id, time_index) in enumerate(zip(evidence_ids, times, strict=True)):
        records[evidence_id] = {
            "schema_version": "cpmt-0.2",
            "evidence_id": evidence_id,
            "time_index": time_index,
            "viewpoint_id": f"view:{event['event_id']}:{index}",
            "kind": "visible_empty",
            "claim_ref": edge["edge_version_id"],
            "verdict": "contradicts",
            "availability": "online",
            "visibility": "visible_empty",
            "pose_valid": True,
            "depth_valid": True,
            "reliability": 1.0,
        }
    return evidence_ids, records


def _retract_program(
    graph: Mapping[str, Any], event: Mapping[str, Any], *, suffix: str = "retract",
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    edge = _open_edge(graph, event["target_edge_id"])
    evidence_ids, evidence = _negative_events(edge, event, suffix)
    program = _program_header(graph, event, "RETRACT", suffix=suffix, intent="REVISE")
    tx = program["transaction_id"]
    program["retraction_target"] = {
        "kind": "edge_version", "version_id": edge["edge_version_id"],
    }
    program["evidence_refs"] = evidence_ids
    program["declared_edit_cost"] = 1.0
    program["operations"] = [
        {"op_id": f"{suffix}:close", "op_type": "CLOSE_EDGE_VERSION",
         "arguments": {"edge_id": edge["edge_id"], "at": event["decision_time"]}},
        *[
            {"op_id": f"{suffix}:attach:{index}", "op_type": "ATTACH_EVIDENCE",
             "arguments": {"target_kind": "edge",
                           "edge_version_id": edge["edge_version_id"],
                           "evidence_ref": evidence_id}}
            for index, evidence_id in enumerate(evidence_ids)
        ],
        {"op_id": f"{suffix}:provenance", "op_type": "RECORD_PROVENANCE",
         "arguments": {"target_kind": "edge", "edge_version_id": edge["edge_version_id"],
                       "provenance_ref": tx}},
    ]
    return program, evidence


def _split_program(
    graph: Mapping[str, Any], event: Mapping[str, Any],
) -> dict[str, Any]:
    source = _open_node(graph, event["target_node_id"])
    left_new = f"{event['current_evidence_ref']}:left"
    right_new = f"{event['current_evidence_ref']}:right"
    program = _program_header(graph, event, "SPLIT", suffix="split", intent="REVISE")
    tx = program["transaction_id"]
    program["evidence_refs"] = [left_new, right_new]
    program["declared_edit_cost"] = 2.0
    program["declared_growth_cost"] = 2.0
    old_evidence = list(source["evidence_refs"])
    partitions = [
        [old_evidence[0], left_new],
        [*old_evidence[1:], right_new],
    ]
    program["operations"] = [
        {"op_id": "split:assert", "op_type": "ASSERT_PRECONDITION",
         "arguments": {"kind": "node_lifecycle", "node_id": source["node_id"],
                       "allowed": ["confirmed"]}},
        {"op_id": "split:retract", "op_type": "SET_LIFECYCLE",
         "arguments": {"node_id": source["node_id"], "from": "confirmed",
                       "to": "retracted"}},
        {"op_id": "split:close", "op_type": "CLOSE_NODE_VERSION",
         "arguments": {"node_id": source["node_id"], "at": event["decision_time"]}},
        {"op_id": "split:provenance", "op_type": "RECORD_PROVENANCE",
         "arguments": {"target_kind": "node", "node_version_id": source["node_version_id"],
                       "provenance_ref": tx}},
    ]
    for index, (node_id, evidence_refs) in enumerate(
        zip(event["successor_ids"], partitions, strict=True)
    ):
        program["operations"].append({
            "op_id": f"split:create:{index}", "op_type": "CREATE_NODE", "arguments": {
                "node": {
                    **_node(node_id, "entity", "candidate", evidence_refs,
                            [f"latent:{node_id}"], tx,
                            valid_from=event["decision_time"]),
                    "predecessor_ids": [source["node_version_id"]],
                }
            },
        })
    return program


def _merge_program(
    graph: Mapping[str, Any], event: Mapping[str, Any],
) -> dict[str, Any]:
    sources = [_open_node(graph, node_id) for node_id in event["target_node_ids"]]
    canonical = min(sources, key=lambda item: (item["valid_from"], item["node_id"]))
    program = _program_header(graph, event, "MERGE", suffix="merge", intent="REVISE")
    tx = program["transaction_id"]
    evidence = f"{event['current_evidence_ref']}:same-identity"
    program["evidence_refs"] = [evidence]
    program["declared_edit_cost"] = 2.0
    operations = []
    for source in sources:
        operations.extend([
            {"op_id": f"merge:close:{source['node_id']}",
             "op_type": "CLOSE_NODE_VERSION",
             "arguments": {"node_id": source["node_id"],
                           "at": event["decision_time"]}},
            {"op_id": f"merge:provenance:{source['node_id']}",
             "op_type": "RECORD_PROVENANCE",
             "arguments": {"target_kind": "node",
                           "node_version_id": source["node_version_id"],
                           "provenance_ref": tx}},
        ])
    merged_evidence = list(dict.fromkeys(
        [item for source in sources for item in source["evidence_refs"]] + [evidence]
    ))
    merged_latents = list(dict.fromkeys(
        item for source in sources for item in source["latent_refs"]
    ))
    predecessor_ids = [source["node_version_id"] for source in sources]
    for source in sources:
        if source["node_id"] == canonical["node_id"]:
            new_node = {
                **_node(source["node_id"], "entity", "confirmed", merged_evidence,
                        merged_latents, tx, valid_from=event["decision_time"]),
                "node_version_id": f"{source['node_id']}@m{event['step_index']}",
                "predecessor_ids": predecessor_ids,
            }
        else:
            new_node = {
                **_node(source["node_id"], "entity", "alias", [], [], tx,
                        valid_from=event["decision_time"]),
                "node_version_id": f"{source['node_id']}@m{event['step_index']}",
                "canonical_id": canonical["node_id"],
                "predecessor_ids": [source["node_version_id"]],
            }
        operations.append({
            "op_id": f"merge:open:{source['node_id']}",
            "op_type": "OPEN_NODE_VERSION", "arguments": {"node": new_node},
        })
    program["operations"] = operations
    return program


def _replace_program(
    graph: Mapping[str, Any], event: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    edge = _open_edge(graph, event["target_edge_id"])
    evidence_ids, evidence = _negative_events(edge, event, "replace")
    birth_evidence = f"{event['current_evidence_ref']}:new-object"
    evidence[birth_evidence] = {
        "schema_version": "cpmt-0.2",
        "evidence_id": birth_evidence,
        "time_index": int(event["decision_time"]),
        "viewpoint_id": f"view:{event['event_id']}:new-object",
        "kind": "observation",
        "claim_ref": event["new_node_id"],
        "verdict": "supports",
        "availability": "online",
        "visibility": "visible",
        "pose_valid": True,
        "depth_valid": True,
        "reliability": 1.0,
    }
    program = _program_header(
        graph, event, "COMPOSITE", suffix="replace", intent="REVISE",
    )
    program["composition_label"] = "REPLACE"
    program["component_templates"] = ["RETRACT", "BIRTH"]
    program["retraction_target"] = {
        "kind": "edge_version", "version_id": edge["edge_version_id"],
    }
    program["evidence_refs"] = evidence_ids + [birth_evidence]
    program["declared_edit_cost"] = 2.0
    program["declared_growth_cost"] = 1.0
    tx = program["transaction_id"]
    new_id = event["new_node_id"]
    program["operations"] = [
        {"op_id": "replace:close", "op_type": "CLOSE_EDGE_VERSION",
         "arguments": {"edge_id": edge["edge_id"], "at": event["decision_time"]}},
        *[
            {"op_id": f"replace:attach:{index}", "op_type": "ATTACH_EVIDENCE",
             "arguments": {"target_kind": "edge",
                           "edge_version_id": edge["edge_version_id"],
                           "evidence_ref": evidence_id}}
            for index, evidence_id in enumerate(evidence_ids)
        ],
        {"op_id": "replace:provenance", "op_type": "RECORD_PROVENANCE",
         "arguments": {"target_kind": "edge", "edge_version_id": edge["edge_version_id"],
                       "provenance_ref": tx}},
        {"op_id": "replace:create", "op_type": "CREATE_NODE", "arguments": {
            "node": _node(new_id, "entity", "candidate", [birth_evidence],
                          [f"latent:{new_id}"], tx,
                          valid_from=event["decision_time"]),
        }},
        {"op_id": "replace:add-location", "op_type": "ADD_EDGE", "arguments": {
            "edge": {
                **_edge(f"{new_id}:location", new_id, event["new_target"],
                        "located_at", [birth_evidence], tx),
                "valid_from": event["decision_time"],
            }
        }},
    ]
    return program, evidence


def _primary_program(
    graph: Mapping[str, Any], event: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    template = event["primary_template"]
    if template == "NOOP":
        return _noop_program(graph, event), {}
    if template == "BIND":
        return _bind_program(graph, event, event["bind_target"], suffix="bind"), {}
    if template == "BIRTH":
        return _birth_program(graph, event, event["new_node_id"], suffix="birth"), {}
    if template == "REACTIVATE":
        return _reactivate_program(graph, event), {}
    if template == "RELINK":
        return _relink_program(graph, event), {}
    if template == "RETRACT":
        return _retract_program(graph, event)
    if template == "SPLIT":
        return _split_program(graph, event), {}
    if template == "MERGE":
        return _merge_program(graph, event), {}
    if template == "REPLACE":
        return _replace_program(graph, event)
    raise ValueError(f"unsupported rollout template {template!r}")


def _candidate_programs(
    graph: Mapping[str, Any], event: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], int]:
    reference, evidence = _primary_program(graph, event)
    template = event["primary_template"]
    if template == "BIND":
        contrast = _birth_program(
            graph, event, event["contrast_birth_id"], suffix="contrast-birth",
        )
    elif template == "BIRTH":
        contrast = _bind_program(
            graph, event, event["bind_target"], suffix="contrast-bind",
        )
    elif template in {"REACTIVATE", "NOOP"}:
        contrast = _bind_program(
            graph, event, event["bind_target"], suffix="contrast-bind",
        )
    else:
        contrast = _noop_program(graph, event)
    illegal = _bind_program(
        graph, event, event["protected_id"], suffix="illegal-protected-bind",
    )
    programs = [reference, contrast, illegal]
    permutation = np.random.default_rng(event["candidate_seed"]).permutation(len(programs))
    shuffled = [programs[int(index)] for index in permutation]
    reference_index = next(
        index for index, program in enumerate(shuffled)
        if program["transaction_id"] == reference["transaction_id"]
    )
    return shuffled, evidence, reference_index


def _program_label(program: Mapping[str, Any]) -> str:
    if program["template"] == "COMPOSITE":
        return str(program.get("composition_label", "COMPOSITE"))
    return str(program["template"])


def _execute_candidates(
    base: Mapping[str, Any], programs: Sequence[Mapping[str, Any]],
    evidence: Mapping[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    before = canonical_json(base)
    records = []
    for index, raw_program in enumerate(programs):
        program = clone_json(raw_program)
        try:
            post = execute_transaction(
                clone_json(base), program, evidence_by_id=evidence,
            )
            failure = None
        except CPMTError as error:
            post = None
            failure = {"type": type(error).__name__, "message": str(error)}
        if canonical_json(base) != before:
            raise AssertionError("rollout candidate mutated its immutable base")
        records.append({
            "candidate_index": index,
            "transaction_id": program["transaction_id"],
            "template": _program_label(program),
            "base_graph_hash": base["graph_hash"],
            "legal": failure is None,
            "post_graph": post,
            "post_graph_hash": post["graph_hash"] if post is not None else None,
            "failure": failure,
        })
    return records


def _teacher_posterior(
    energies: Sequence[Mapping[str, Any]], temperature: float,
) -> list[float]:
    legal = [float(item["total"]) for item in energies if not item["masked"]]
    if not legal:
        raise ValueError("rollout step has no legal candidate")
    minimum = min(legal)
    weights = [
        0.0 if item["masked"]
        else math.exp(-(float(item["total"]) - minimum) / temperature)
        for item in energies
    ]
    denominator = sum(weights)
    return [value / denominator for value in weights]


def _counterfactual_trace(
    candidate_post: Mapping[str, Any], events: Sequence[Mapping[str, Any]],
    reference_states: Sequence[Mapping[str, Any]], step_index: int,
    horizon: int, reference_indices: Sequence[int],
) -> tuple[float, list[str]]:
    branch = clone_json(candidate_post)
    errors = []
    hashes = []
    final_index = min(len(events), step_index + horizon)
    for target_index in range(step_index, final_index):
        if target_index > step_index:
            programs, evidence, _ = _candidate_programs(branch, events[target_index])
            executions = _execute_candidates(branch, programs, evidence)
            selected = executions[int(reference_indices[target_index])]
            if not selected["legal"] or selected["post_graph"] is None:
                raise AssertionError(
                    "registered reference cannot execute on a counterfactual branch: "
                    f"step={target_index}, failure={selected['failure']}"
                )
            branch = selected["post_graph"]
        pose = int(events[target_index]["pose_bucket"])
        prediction = project_structural_observation(branch, pose)
        target = project_structural_observation(reference_states[target_index], pose)
        errors.append(float(len(prediction ^ target)))
        hashes.append(branch["graph_hash"])
    return float(np.mean(errors)), hashes


def _online_step(
    sequence_id: str, paired_group_id: str, split: str, world_seed: int,
    asset_family: str,
    base: Mapping[str, Any], event: Mapping[str, Any],
    programs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    signature_rng = np.random.default_rng(world_seed + int(event["step_index"]) + 1)
    record = {
        "schema_version": "cpmt-m1-rollout-online-v1",
        "sequence_id": sequence_id,
        "paired_group_id": paired_group_id,
        "step_index": event["step_index"],
        "decision_time": event["decision_time"],
        "scenario_family": event["scenario_family"],
        "split": split,
        "world_seed": world_seed,
        "asset_family": asset_family,
        "prior_world": clone_json(base),
        "current_regions": [{
            "region_ref": event["current_evidence_ref"],
            "anonymous_signature": signature_rng.normal(0.0, 1.0, 8).round(6).tolist(),
        }],
        "history_cues": {
            "cue_name": "sequence_local_identity_and_geometry_consistency",
            "value": event["cue_value"],
            "reliability": 1.0,
        },
        "pose_history": [{
            "time_index": event["decision_time"],
            "pose_bucket": event["pose_bucket"],
            "valid": True,
        }],
        "action_history": ["controlled_revisit"],
        "candidate_programs": clone_json(list(programs)),
    }
    validate_online_payload(record)
    return record


def _generate_sequence(
    config: Mapping[str, Any], split: str, sequence_index: int,
    *, sibling_index: int | None = None, pivot_step: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    world_seed = 360_906 + SPLIT_SEED_OFFSET[split] + sequence_index
    rng = np.random.default_rng(world_seed)
    initial, topology = _initial_world(split, sequence_index, rng)
    events = _event_plan(topology, rng)
    if sibling_index is not None and pivot_step is None:
        pivot_step = _ambiguity_pivot(events)
    for event in events:
        event["places"] = list(topology["special"]["places"])
    paired_group_id = f"rollout-pair:{split}:{sequence_index:06d}"
    sequence_id = (
        f"sequence:{split}:{sequence_index:06d}"
        if sibling_index is None
        else f"sequence:{split}:{sequence_index:06d}:s{sibling_index}"
    )
    online_sequence_id = sequence_id if sibling_index is None else paired_group_id
    asset_buckets = list(ASSET_BUCKETS[split])
    asset_family = f"rollout-asset-{asset_buckets[sequence_index % len(asset_buckets)]:03d}"
    label_fraction = float(config["training"]["main_label_fraction"])
    if split != "train" or label_fraction <= 0:
        labelled_group = False
    elif label_fraction >= 1:
        labelled_group = True
    else:
        reciprocal = round(1.0 / label_fraction)
        if not math.isclose(label_fraction, 1.0 / reciprocal):
            raise ValueError("rollout label fraction must have an integer reciprocal")
        labelled_group = sequence_index % reciprocal == 0

    reference_states = []
    reference_indices = []
    step_material = []
    current = clone_json(initial)
    for event in events:
        programs, evidence, primary_index = _candidate_programs(current, event)
        executions = _execute_candidates(current, programs, evidence)
        reference_index = primary_index
        if sibling_index == 1 and event["step_index"] == pivot_step:
            reference_index = next(
                item["candidate_index"]
                for item in executions
                if item["legal"] and item["candidate_index"] != primary_index
            )
        reference = executions[reference_index]
        if not reference["legal"] or reference["post_graph"] is None:
            raise AssertionError(
                f"reference failed at {sequence_id} step {event['step_index']}: "
                f"{reference['failure']}"
            )
        online = _online_step(
            online_sequence_id, paired_group_id, split, world_seed, asset_family,
            current, event, programs,
        )
        step_material.append({
            "event": clone_json(event),
            "online": online,
            "programs": programs,
            "evidence": evidence,
            "executions": executions,
            "primary_index": primary_index,
            "reference_index": reference_index,
        })
        current = reference["post_graph"]
        reference_states.append(current)
        reference_indices.append(reference_index)

    weights = config["energy"]["weights"]
    temperature = float(config["energy"]["temperature"])
    hindsight_horizon = int(config["future"]["primary_horizon"])
    online_steps = []
    audit_steps = []
    for step_index, material in enumerate(step_material):
        event = material["event"]
        future_trace = []
        for target_index in range(
            step_index, min(len(events), step_index + hindsight_horizon)
        ):
            pose = int(events[target_index]["pose_bucket"])
            future_trace.append({
                "sequence_step": target_index,
                "source": "actual_executed_reference_sequence",
                "pose_bucket": pose,
                "pose_valid": True,
                "visibility_valid": True,
                "structural_observation": sorted(
                    project_structural_observation(reference_states[target_index], pose)
                ),
            })
        energies = []
        for execution, program in zip(
            material["executions"], material["programs"], strict=True,
        ):
            illegal = float(not execution["legal"])
            if execution["post_graph"] is None:
                future = 0.0
                branch_hashes: list[str] = []
            else:
                future, branch_hashes = _counterfactual_trace(
                    execution["post_graph"], events, reference_states,
                    step_index, hindsight_horizon, reference_indices,
                )
            terms = {
                "now": 0.0 if program.get("evidence_refs") else 1.0,
                "future": future,
                "edit": float(program.get("declared_edit_cost", 0.0)),
                "growth": float(program.get("declared_growth_cost", 0.0)),
                "collateral": 0.0,
                "illegal": illegal,
            }
            total = None if illegal else sum(
                float(weights[key]) * terms[key] for key in weights
            )
            energies.append({
                **terms,
                "total": total,
                "masked": bool(illegal),
                "counterfactual_rollout_hashes": branch_hashes,
            })
        posterior = _teacher_posterior(energies, temperature)
        winner = int(np.argmax(posterior))
        reference_index = int(material["reference_index"])
        if winner != reference_index:
            raise AssertionError(
                f"teacher misranks {sequence_id} step {step_index}: "
                f"expected {reference_index}, got {winner}"
            )
        online_steps.append(material["online"])
        audit_steps.append({
            "schema_version": "cpmt-m1-rollout-step-audit-v1",
            "sequence_id": sequence_id,
            "step_index": step_index,
            "scenario_family": event["scenario_family"],
            "event_spec": event,
            "online": material["online"],
            "primary_program_index": material["primary_index"],
            "reference_program_index": reference_index,
            "reference_template": material["executions"][reference_index]["template"],
            "ambiguity": (
                "epistemically_ambiguous_pivot"
                if sibling_index is not None and step_index == pivot_step
                else "sequence_context"
            ),
            "reference_post_graph_hash": reference_states[step_index]["graph_hash"],
            "transaction_label_available": labelled_group,
            "candidate_coverage_at_k": 1.0,
            "executed_candidates": material["executions"],
            "candidate_energies": energies,
            "teacher_posterior": posterior,
            "teacher_winner_index": winner,
            "future_trace": future_trace,
        })
    return online_steps, {
        "schema_version": "cpmt-m1-rollout-audit-v1",
        "sequence_id": sequence_id,
        "paired_group_id": paired_group_id,
        "sibling_index": sibling_index,
        "ambiguity_pivot_step": pivot_step,
        "split": split,
        "world_seed": world_seed,
        "asset_family": asset_family,
        "initial_world": initial,
        "topology": topology,
        "primary_event_order": [event["primary_template"] for event in events],
        "event_order": [
            material["executions"][material["reference_index"]]["template"]
            for material in step_material
        ],
        "steps": audit_steps,
        "final_reference_graph_hash": reference_states[-1]["graph_hash"],
    }


def generate_m1_rollout_split(
    config: Mapping[str, Any], split: str, *, sequences: int = 1,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Generate procedural 20-step train/validation sequences, never test."""
    validate_m1_protocol(config)
    if split not in SPLIT_SEED_OFFSET:
        raise ValueError("M1 rollout generator exposes train/validation only; test is sealed")
    if sequences <= 0:
        raise ValueError("sequences must be positive")
    horizon = int(config["evaluation"]["self_rollout_horizon_decisions"])
    if horizon != sum(ROLLOUT_TEMPLATE_COUNTS.values()):
        raise ValueError("rollout template schedule must match the frozen 20-step horizon")
    online_steps = []
    audits = []
    for sequence_index in range(sequences):
        sequence_online, audit = _generate_sequence(
            config, split, sequence_index,
        )
        online_steps.extend(sequence_online)
        audits.append(audit)
    topology_signatures = {
        (
            audit["topology"]["place_count"],
            audit["topology"]["surface_count"],
            audit["topology"]["filler_entity_count"],
            tuple(audit["event_order"]),
        )
        for audit in audits
    }
    summary = {
        "status": "rollout_interface_validation_only",
        "split": split,
        "sequences": sequences,
        "decisions": len(online_steps),
        "horizon_decisions": horizon,
        "template_counts_per_sequence": ROLLOUT_TEMPLATE_COUNTS,
        "distinct_topology_and_order_signatures": len(topology_signatures),
        "place_count_range": [
            min(audit["topology"]["place_count"] for audit in audits),
            max(audit["topology"]["place_count"] for audit in audits),
        ],
        "surface_count_range": [
            min(audit["topology"]["surface_count"] for audit in audits),
            max(audit["topology"]["surface_count"] for audit in audits),
        ],
        "initial_node_count_range": [
            min(audit["topology"]["initial_node_count"] for audit in audits),
            max(audit["topology"]["initial_node_count"] for audit in audits),
        ],
        "candidate_set_size": 3,
        "test_generated": False,
        "formal_data_ready": False,
        "paired_latent_siblings_ready": False,
        "front_end": "controlled_structural_token_projector_not_pno",
        "note": (
            "Each sequence is a real chained graph trajectory and supports predicted-state "
            "replay. Formal paired latent siblings, visual PNO input, and A-F training remain pending."
        ),
    }
    return online_steps, audits, summary


def generate_m1_paired_rollout_split(
    config: Mapping[str, Any], split: str, *, paired_groups: int = 1,
    start_group_index: int = 0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Generate paired continuous worlds with one exact online ambiguity pivot.

    Siblings share their initial graph, asset, event plan, and online prefix.
    At the pivot the online payload and candidates are identical while the
    audit-only reference selects the primary program for sibling 0 and its
    legal contrast for sibling 1.  Subsequent bases then diverge naturally.
    """
    validate_m1_protocol(config)
    if split not in SPLIT_SEED_OFFSET:
        raise ValueError(
            "M1 paired rollout generator exposes train/validation only; test is sealed"
        )
    if paired_groups <= 0:
        raise ValueError("paired_groups must be positive")
    if start_group_index < 0:
        raise ValueError("paired rollout start_group_index must be nonnegative")
    horizon = int(config["evaluation"]["self_rollout_horizon_decisions"])
    if horizon != sum(ROLLOUT_TEMPLATE_COUNTS.values()):
        raise ValueError("paired rollout schedule must match the frozen 20-step horizon")

    online_steps: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    for group_index in range(start_group_index, start_group_index + paired_groups):
        pair = []
        for sibling_index in (0, 1):
            sibling_online, audit = _generate_sequence(
                config, split, group_index, sibling_index=sibling_index,
            )
            online_steps.extend(sibling_online)
            audits.append(audit)
            pair.append(audit)
        left, right = pair
        pivot = int(left["ambiguity_pivot_step"])
        if pivot != int(right["ambiguity_pivot_step"]):
            raise AssertionError("paired siblings chose different ambiguity pivots")
        if canonical_json(left["initial_world"]) != canonical_json(right["initial_world"]):
            raise AssertionError("paired siblings must share the exact initial world")
        if left["primary_event_order"] != right["primary_event_order"]:
            raise AssertionError("paired siblings must share the exact event plan")
        if canonical_json(left["steps"][pivot]["online"]) != canonical_json(
            right["steps"][pivot]["online"]
        ):
            raise AssertionError("ambiguity-pivot online inputs must be exactly identical")
        if (
            left["steps"][pivot]["reference_program_index"]
            == right["steps"][pivot]["reference_program_index"]
        ):
            raise AssertionError("ambiguity-pivot references must differ")
        if (
            left["steps"][pivot]["reference_post_graph_hash"]
            == right["steps"][pivot]["reference_post_graph_hash"]
        ):
            raise AssertionError("ambiguity pivot must create distinct reference worlds")

    group_representatives = audits[::2]
    topology_signatures = {
        (
            audit["topology"]["place_count"],
            audit["topology"]["surface_count"],
            audit["topology"]["filler_entity_count"],
            tuple(audit["primary_event_order"]),
        )
        for audit in group_representatives
    }
    summary = {
        "status": "paired_rollout_interface_validation_only",
        "split": split,
        "paired_groups": paired_groups,
        "start_group_index": start_group_index,
        "siblings_per_group": 2,
        "sequences": len(audits),
        "decisions": len(online_steps),
        "horizon_decisions": horizon,
        "template_counts_per_primary_sequence": ROLLOUT_TEMPLATE_COUNTS,
        "exact_ambiguous_decision_pairs": paired_groups,
        "distinct_topology_and_order_signatures": len(topology_signatures),
        "place_count_range": [
            min(audit["topology"]["place_count"] for audit in group_representatives),
            max(audit["topology"]["place_count"] for audit in group_representatives),
        ],
        "surface_count_range": [
            min(audit["topology"]["surface_count"] for audit in group_representatives),
            max(audit["topology"]["surface_count"] for audit in group_representatives),
        ],
        "initial_node_count_range": [
            min(audit["topology"]["initial_node_count"] for audit in group_representatives),
            max(audit["topology"]["initial_node_count"] for audit in group_representatives),
        ],
        "candidate_set_size": 3,
        "test_generated": False,
        "formal_data_ready": False,
        "paired_latent_siblings_ready": True,
        "front_end": "controlled_structural_token_projector_not_pno",
        "note": (
            "Paired siblings now provide one exact same-online/different-reference pivot "
            "inside a causal 20-step chain. K=16 and the A-F runner remain pending."
        ),
    }
    return online_steps, audits, summary


def materialize_rollout_step(
    audit_sequence: Mapping[str, Any], base: Mapping[str, Any], step_index: int,
) -> dict[str, Any]:
    """Rebuild one deployable step on a caller-provided predicted graph."""
    steps = audit_sequence["steps"]
    if not 0 <= step_index < len(steps):
        raise ValueError("step index is outside the recorded sequence")
    stored = steps[step_index]
    event = stored["event_spec"]
    programs, evidence, primary_index = _candidate_programs(base, event)
    executions = _execute_candidates(base, programs, evidence)
    source_online = stored["online"]
    online = _online_step(
        source_online["sequence_id"], source_online["paired_group_id"],
        source_online["split"], int(source_online["world_seed"]),
        source_online["asset_family"], base, event, programs,
    )
    return {
        "step_index": step_index,
        "online": online,
        "executed_candidates": executions,
        "primary_program_index": primary_index,
    }


def execute_rollout_choices(
    audit_sequence: Mapping[str, Any], selected_indices: Sequence[int],
) -> dict[str, Any]:
    """Execute choices causally, rebuilding each next step on predicted state.

    Illegal selections use the deterministic QUARANTINE-style fallback: the
    persistent graph remains the current base, while the failure is recorded.
    """
    steps = audit_sequence["steps"]
    if len(selected_indices) != len(steps):
        raise ValueError("selected indices must cover the complete ordered sequence")
    current = clone_json(audit_sequence["initial_world"])
    states = []
    bases = []
    decisions = []
    for step, selected_index in zip(steps, selected_indices, strict=True):
        event = step["event_spec"]
        programs, evidence, reference_index = _candidate_programs(current, event)
        executions = _execute_candidates(current, programs, evidence)
        if not 0 <= int(selected_index) < len(executions):
            raise ValueError("selected candidate index is outside the fixed budget")
        selected = executions[int(selected_index)]
        base = current
        if selected["legal"]:
            current = selected["post_graph"]
            committed = True
        else:
            current = clone_json(base)
            committed = False
        bases.append(base)
        states.append(current)
        decisions.append({
            "step_index": step["step_index"],
            "base_graph_hash": base["graph_hash"],
            "selected_index": int(selected_index),
            "selected_template": selected["template"],
            "selected_legal": selected["legal"],
            "committed": committed,
            "post_graph_hash": current["graph_hash"],
            "reference_index_on_predicted_base": reference_index,
            "failure": selected["failure"],
        })
    return {"states": states, "base_states": bases, "decisions": decisions}


def records_sha256(records: Iterable[Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for record in records:
        digest.update(canonical_json(record).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()
