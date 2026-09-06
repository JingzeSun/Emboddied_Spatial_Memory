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
from functools import lru_cache
from collections import Counter
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from .errors import CPMTError
from .equivalence import canonicalize_memory_state
from .executor import execute_transaction, validate_graph
from .hashing import canonical_json, clone_json, seal_graph
from .m1_data import project_structural_observation, validate_online_payload
from .m1_metrics import protected_signature
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
CANDIDATE_BUDGET = 16
RELINK_RANK_PAIRS = ((0, 0), (1, 0), (0, 1))
CANDIDATE_EVENT_FIELDS = (
    "event_id", "step_index", "decision_time", "candidate_seed",
    "current_evidence_ref", "protected_id", "proposal_observation",
)
PROPOSAL_FEATURE_DIM = 16
PROPOSAL_OBSERVATION_FIELDS = {
    "node_query", "edge_query", "place_query", "merge_queries", "source",
}
PROPOSAL_RETRIEVAL_SOURCE = "controlled_noisy_retrieval_features_v2"
PROPOSAL_RETRIEVAL_FIELDS = {
    "source", "noise_sigma", "distractor_weight", "enumerated_ranks",
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


@lru_cache(maxsize=16_384)
def _cached_retrieval_feature(value: str) -> tuple[float, ...]:
    raw = np.frombuffer(
        hashlib.sha256(value.encode("utf-8")).digest()[:PROPOSAL_FEATURE_DIM],
        dtype=np.uint8,
    ).astype(np.float64)
    vector = (raw - 127.5) / 127.5
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        raise AssertionError("stable retrieval feature unexpectedly has zero norm")
    return tuple((vector / norm).round(8).tolist())


def stable_retrieval_feature(value: str) -> list[float]:
    """Map an online identity signature to a fixed, nonlearned unit vector."""
    return list(_cached_retrieval_feature(value))


_stable_retrieval_feature = stable_retrieval_feature


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


def _latest_node(graph: Mapping[str, Any], node_id: str) -> dict[str, Any]:
    matches = [node for node in graph["nodes"] if node["node_id"] == node_id]
    if not matches:
        raise ValueError(f"expected a node lineage {node_id!r}")
    return max(
        matches,
        key=lambda node: (
            int(node.get("valid_from", 0)),
            node.get("valid_to") is None,
            str(node["node_version_id"]),
        ),
    )


def _latest_edge(graph: Mapping[str, Any], edge_id: str) -> dict[str, Any]:
    matches = [edge for edge in graph["edges"] if edge["edge_id"] == edge_id]
    if not matches:
        raise ValueError(f"expected an edge lineage {edge_id!r}")
    return max(
        matches,
        key=lambda edge: (
            int(edge.get("valid_from", 0)),
            edge.get("valid_to") is None,
            str(edge["edge_version_id"]),
        ),
    )


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
        "appearance_dim": APPEARANCE_DIM,
        "semantic_latents": _semantic_latents(special, rng),
        "place_count": place_count,
        "surface_count": surface_count,
        "filler_entity_count": filler_count,
        "initial_node_count": len(nodes),
        "initial_edge_count": len(edges),
        "initial_edge_targets": {
            str(edge["edge_id"]): str(edge["target"]) for edge in edges
        },
        "special": special,
    }
    return graph, topology


ARGUMENT_ID_KEYS = ("edge_id", "node_id", "node_version_id")
APPEARANCE_DIM = PROPOSAL_FEATURE_DIM
VISIBILITY_KINDS = ("visible", "visible_empty", "occluded")


def _unit(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        raise AssertionError("appearance vector unexpectedly has zero norm")
    return vector / norm


def default_appearance(node_id: str) -> np.ndarray:
    """Fixed appearance descriptor for a node with no semantic override.

    Memory stores this descriptor when a node is created; an observation is the
    same descriptor plus sensor noise.  Nodes created during a rollout get one
    without any extra bookkeeping because it is a function of the identifier.
    """
    return _unit(np.asarray(
        stable_retrieval_feature(str(node_id))[:APPEARANCE_DIM], dtype=np.float64,
    ))


def appearance_of(node_id: str, latents: Mapping[str, Any]) -> np.ndarray:
    """Remembered appearance, honouring the world's semantic overrides."""
    override = latents.get(str(node_id))
    if override is None:
        return default_appearance(node_id)
    return _unit(np.asarray(override, dtype=np.float64))


def _semantic_latents(
    special: Mapping[str, Any], rng: np.random.Generator,
) -> dict[str, list[float]]:
    """Override appearances where a family's semantics require it.

    C05 MERGE is "two records of one object", so its pair must look alike.  C04
    SPLIT is "one record conflating two objects", so the stored appearance is a
    mixture that matches either component only partially.
    """
    latents: dict[str, list[float]] = {}
    merge_base = _unit(rng.normal(0.0, 1.0, APPEARANCE_DIM))
    latents[str(special["merge_a"])] = merge_base.round(8).tolist()
    latents[str(special["merge_b"])] = _unit(
        merge_base + 0.08 * rng.normal(0.0, 1.0, APPEARANCE_DIM)
    ).round(8).tolist()
    left = _unit(rng.normal(0.0, 1.0, APPEARANCE_DIM))
    right = _unit(rng.normal(0.0, 1.0, APPEARANCE_DIM))
    latents[str(special["split_source"])] = _unit(left + right).round(8).tolist()
    latents[f"{special['split_source']}::component:0"] = left.round(8).tolist()
    latents[f"{special['split_source']}::component:1"] = right.round(8).tolist()
    return latents


def candidate_argument_ids(program: Mapping[str, Any]) -> list[str]:
    """List the concrete world entities one candidate program touches."""
    found: list[str] = []
    for operation in program["operations"]:
        arguments = operation["arguments"]
        for key in ARGUMENT_ID_KEYS:
            value = arguments.get(key)
            if isinstance(value, str):
                found.append(value.split("@")[0])
        edge = arguments.get("edge")
        if isinstance(edge, Mapping):
            found.extend(str(edge[key]) for key in ("source", "target"))
        node = arguments.get("node")
        if isinstance(node, Mapping):
            found.append(str(node["node_id"]))
    return list(dict.fromkeys(found))


def _query_decides_reference(
    programs: Sequence[Mapping[str, Any]], observation: Mapping[str, Any],
    reference_index: int,
) -> bool:
    """Would ranking candidates by query similarity alone give the reference?

    A true answer here means the retrieval channel is an oracle pointer and the
    remaining choice is a lookup, not an inference.
    """
    queries = [
        np.asarray(observation[kind], dtype=np.float64)
        for kind in ("node_query", "edge_query", "place_query")
    ]
    scores = []
    for program in programs:
        identifiers = candidate_argument_ids(program)
        if not identifiers:
            scores.append(-np.inf)
            continue
        vectors = np.asarray(
            [stable_retrieval_feature(value) for value in identifiers],
            dtype=np.float64,
        )
        scores.append(max(float((vectors @ query).max()) for query in queries))
    best = float(np.max(scores))
    winners = [i for i, value in enumerate(scores) if value == best]
    return winners == [reference_index]


def _proposal_query(
    identifier: Any, distractors: Sequence[str], rng: np.random.Generator,
    retrieval: Mapping[str, Any],
) -> list[float]:
    """Blend the proposer's target with a controlled distractor and noise.

    An exact hash of the hidden argument makes retrieval a lookup: the true
    argument always outranks every other entity, so the reference is always the
    same generator slot and coverage is guaranteed for the wrong reason.  The
    query stays informative here, but it is no longer decisive on its own.
    """
    vector = np.asarray(
        stable_retrieval_feature(str(identifier)), dtype=np.float64,
    )
    pool = [
        value for value in dict.fromkeys(str(item) for item in distractors)
        if value != str(identifier)
    ]
    weight = float(retrieval["distractor_weight"])
    if weight > 0.0 and pool:
        choice = pool[int(rng.integers(0, len(pool)))]
        vector = vector + weight * np.asarray(
            stable_retrieval_feature(choice), dtype=np.float64,
        )
    sigma = float(retrieval["noise_sigma"])
    if sigma > 0.0:
        vector = vector + sigma * rng.normal(0.0, 1.0, PROPOSAL_FEATURE_DIM)
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        raise AssertionError("proposal query unexpectedly has zero norm")
    return (vector / norm).round(8).tolist()


OBSERVATION_MODEL_SOURCE = "world_generated_appearance_v1"
OBSERVATION_MODEL_FIELDS = {
    "source", "appearance_noise", "occlusion_is_neutral",
}


def validate_observation_model(observation: Mapping[str, Any]) -> dict[str, Any]:
    """Reject an observation model that stops depending on the world."""
    if set(observation) != OBSERVATION_MODEL_FIELDS:
        raise ValueError(
            f"observation must declare exactly {sorted(OBSERVATION_MODEL_FIELDS)}"
        )
    if observation["source"] != OBSERVATION_MODEL_SOURCE:
        raise ValueError("unsupported observation model source")
    noise = float(observation["appearance_noise"])
    if not 0.0 <= noise <= 1.0:
        raise ValueError("appearance noise must be within [0, 1]")
    if observation["occlusion_is_neutral"] is not True:
        raise ValueError("occlusion must stay neutral evidence, never a negative")
    return dict(observation)


def validate_proposal_retrieval(retrieval: Mapping[str, Any]) -> dict[str, Any]:
    """Reject a retrieval spec that silently restores the oracle pointer."""
    if set(retrieval) != PROPOSAL_RETRIEVAL_FIELDS:
        raise ValueError(
            "proposal_retrieval must declare exactly "
            f"{sorted(PROPOSAL_RETRIEVAL_FIELDS)}"
        )
    if retrieval["source"] != PROPOSAL_RETRIEVAL_SOURCE:
        raise ValueError("unsupported proposal retrieval source")
    sigma = float(retrieval["noise_sigma"])
    weight = float(retrieval["distractor_weight"])
    if sigma < 0.0 or weight < 0.0:
        raise ValueError("proposal retrieval noise and distractor weight must be >= 0")
    if sigma == 0.0 and weight == 0.0:
        raise ValueError(
            "a noiseless, distractor-free query is an exact hash of the hidden "
            "reference argument and makes candidate choice a lookup"
        )
    ranks = int(retrieval["enumerated_ranks"])
    if not 1 <= ranks <= 3:
        raise ValueError("enumerated_ranks must be between 1 and 3")
    return dict(retrieval)


def _event_plan(
    topology: Mapping[str, Any], rng: np.random.Generator,
    retrieval: Mapping[str, Any], *, observation_noise: float = 0.0,
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
        # The event identifier is deliberately neutral.  Candidate generation
        # must not recover the hidden reference template from an ID string.
        event_id = f"{namespace}:event:{step_index:02d}"
        current_evidence_ref = f"obs:{event_id}:current"
        candidate_seed = int(rng.integers(0, 2**31 - 1))
        event = {
            "event_id": event_id,
            "step_index": step_index,
            "decision_time": step_index + 1,
            "scenario_family": TEMPLATE_FAMILY[template],
            "candidate_seed": candidate_seed,
            "pose_bucket": int(rng.integers(0, 8)),
            "observation_seed": int(rng.integers(0, 2**31 - 1)),
            "current_evidence_ref": current_evidence_ref,
            "contrast_birth_id": f"{namespace}:entity:contrast-birth:{step_index}",
            "protected_id": special["protected_id"],
        }
        reference_spec: dict[str, Any] = {"template": template}
        if template == "NOOP":
            reference_spec["noop_cause"] = ordinal % 3
        if template == "BIRTH":
            reference_spec["new_node_id"] = (
                f"candidate:{current_evidence_ref}:birth"
            )
        elif template == "REACTIVATE":
            reference_spec["target_node_id"] = special["dormant_target"]
        elif template == "RELINK":
            target_edge_id = special["mover_edges"][ordinal]
            old_target = topology["initial_edge_targets"][target_edge_id]
            old_index = places.index(old_target)
            reference_spec.update({
                "target_edge_id": target_edge_id,
                "new_target": places[(old_index + ordinal + 1) % len(places)],
                "places": list(places),
            })
        elif template == "RETRACT":
            reference_spec["target_edge_id"] = special["retract_edges"][ordinal]
        elif template == "SPLIT":
            reference_spec["target_node_id"] = special["split_source"]
            reference_spec["successor_ids"] = [
                f"candidate:{current_evidence_ref}:split:0:left",
                f"candidate:{current_evidence_ref}:split:0:right",
            ]
        elif template == "MERGE":
            reference_spec["target_node_ids"] = [
                special["merge_a"], special["merge_b"],
            ]
        elif template == "REPLACE":
            reference_spec.update({
                "target_edge_id": special["replace_edge"],
                "new_node_id": f"candidate:{current_evidence_ref}:replace",
                "new_target": places[-1],
            })
        elif template == "BIND":
            reference_spec["target_node_id"] = special["bind_target"]

        node_observation_id = str(
            reference_spec.get("target_node_id")
            or next(iter(reference_spec.get("target_node_ids", [])),
                    f"{event_id}:unmatched-node")
        )
        edge_observation_id = str(reference_spec.get(
            "target_edge_id", f"{event_id}:unmatched-edge",
        ))
        place_observation_id = str(reference_spec.get(
            "new_target", f"{event_id}:unmatched-place",
        ))
        merge_observation_ids = list(reference_spec.get(
            "target_node_ids",
            [f"{event_id}:merge-a", f"{event_id}:merge-b"],
        ))
        node_pool = [
            str(value) for key, value in special.items()
            if key in {"bind_target", "dormant_target", "split_source",
                       "merge_a", "merge_b", "replace_entity", "decoy_target"}
        ] + [str(value) for value in special["mover_ids"] + special["retract_ids"]]
        edge_pool = [str(value) for value in topology["initial_edge_targets"]]
        event["proposal_observation"] = {
            "node_query": _proposal_query(
                node_observation_id, node_pool, rng, retrieval),
            "edge_query": _proposal_query(
                edge_observation_id, edge_pool, rng, retrieval),
            "place_query": _proposal_query(
                place_observation_id, places, rng, retrieval),
            "merge_queries": [
                _proposal_query(str(value), node_pool, rng, retrieval)
                for value in merge_observation_ids
            ],
            "source": PROPOSAL_RETRIEVAL_SOURCE,
        }
        event["reference_spec"] = reference_spec
        # Generated from the world truth, so the observation is evidence about
        # the decision instead of an independent random cue.
        event["observation_spec"] = _observation_spec(
            template, reference_spec, event, topology, ambiguous=False,
        )
        event["observation_noise"] = float(observation_noise)
        events.append(event)
    if counters != ROLLOUT_TEMPLATE_COUNTS:
        raise AssertionError("rollout event plan lost a registered template")
    return events


def _mark_decision_ambiguous(event: dict[str, Any]) -> None:
    """Occlude the decisive observation so both siblings see identical input."""
    event["observation_spec"] = _observation_spec(
        str(event["reference_spec"]["template"]), event["reference_spec"],
        event, {"special": {}}, ambiguous=True,
    )


def _ambiguity_pivot(events: Sequence[Mapping[str, Any]]) -> int:
    """Choose one middle decision whose legal contrast changes the world."""
    for step_index in range(5, min(15, len(events))):
        if events[step_index]["reference_spec"]["template"] != "NOOP":
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
    node = _latest_node(graph, event["target_node_id"])
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
    edge = _latest_edge(graph, event["target_edge_id"])
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
    edge = _latest_edge(graph, event["target_edge_id"])
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
    source = _latest_node(graph, event["target_node_id"])
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
    sources = [_latest_node(graph, node_id) for node_id in event["target_node_ids"]]
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
    edge = _latest_edge(graph, event["target_edge_id"])
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


def _ranked_ids(
    records: Iterable[Mapping[str, Any]], event: Mapping[str, Any], *,
    kind: str, id_key: str,
) -> list[str]:
    """Rank online-visible arguments without consulting the hidden label."""
    seed = int(event["candidate_seed"])
    return [
        str(record[id_key])
        for record in sorted(
            records,
            key=lambda record: hashlib.sha256(
                f"{seed}|{kind}|{record[id_key]}".encode("utf-8")
            ).hexdigest(),
        )
    ]


def _repeat_to(values: Sequence[str], count: int, *, name: str) -> list[str]:
    if not values:
        raise ValueError(f"fixed candidate generator found no {name}")
    return [str(values[index % len(values)]) for index in range(count)]


def _rank_by_observation(
    ranked: Sequence[str], query: Sequence[float],
    event: Mapping[str, Any], *, kind: str,
) -> list[str]:
    """Rank current-world IDs by anonymous fixed observation similarity."""
    query_vector = np.asarray(query, dtype=np.float64)
    if query_vector.shape != (PROPOSAL_FEATURE_DIM,) or not np.isfinite(
        query_vector
    ).all():
        raise ValueError("proposal observation query has invalid shape or values")
    unique = list(dict.fromkeys(str(value) for value in ranked))
    seed = int(event["candidate_seed"])
    return sorted(
        unique,
        key=lambda value: (
            -float(np.dot(
                query_vector,
                np.asarray(_stable_retrieval_feature(value), dtype=np.float64),
            )),
            hashlib.sha256(
                f"{seed}|observation-tie|{kind}|{value}".encode("utf-8")
            ).hexdigest(),
        ),
    )


WORLD_LATENT_DIM = 3 * APPEARANCE_DIM + 12


def project_world_latent(
    graph: Mapping[str, Any], pose_bucket: int, latents: Mapping[str, Any],
) -> list[float]:
    """Continuous, pose-conditioned descriptor of one world state.

    The hashed structural projection is exact but has no metric structure: two
    worlds differing by one edge land in unrelated buckets, so a regression
    target built from it carries almost no gradient about *how* wrong a
    prediction is.  This keeps the same information in a space where distance
    means something, which is what makes a learned outcome scorer a fair
    baseline rather than a strawman.  It is still an analytic projector, not a
    Projective Node Orbit.
    """
    pose_gate = np.asarray(
        appearance_of(f"pose-bucket:{int(pose_bucket)}", latents), dtype=np.float64,
    )
    open_nodes = [n for n in graph["nodes"] if n.get("valid_to") is None]
    open_edges = [e for e in graph["edges"] if e.get("valid_to") is None]
    placement = np.zeros(APPEARANCE_DIM, dtype=np.float64)
    for edge in open_edges:
        if edge["relation"] != "located_at":
            continue
        placement += (appearance_of(str(edge["source"]), latents)
                      * appearance_of(str(edge["target"]), latents))
    placement *= pose_gate
    confirmed, dormant = [], []
    for node in open_nodes:
        if node["node_type"] != "entity":
            continue
        (dormant if node["lifecycle"] == "dormant" else confirmed).append(
            appearance_of(str(node["node_id"]), latents))
    values: list[float] = list(placement)
    for group in (confirmed, dormant):
        mean = (np.mean(np.asarray(group, dtype=np.float64), axis=0)
                if group else np.zeros(APPEARANCE_DIM))
        values.extend(float(item) for item in mean)
    counts = Counter(n["node_type"] for n in open_nodes)
    values.extend(counts[name] / 32.0 for name in
                  ("entity", "surface", "place", "chart", "region"))
    lifecycles = Counter(n["lifecycle"] for n in graph["nodes"])
    values.extend(lifecycles[name] / 32.0 for name in
                  ("candidate", "confirmed", "dormant", "retracted", "alias"))
    values.extend([len(open_edges) / 32.0,
                   (len(graph["edges"]) - len(open_edges)) / 32.0])
    if len(values) != WORLD_LATENT_DIM:
        raise AssertionError("world latent changed size without a constant update")
    return [round(float(item), 8) for item in values]


def _observation_spec(
    template: str, reference_spec: Mapping[str, Any], event: Mapping[str, Any],
    topology: Mapping[str, Any], *, ambiguous: bool,
) -> dict[str, Any]:
    """Describe what a sensor reports at this decision, given the world truth.

    Each family is distinguished by observable evidence rather than by a label:
    C01 sees a remembered appearance, C02 an unfamiliar one, C07 a reliably
    empty place, C08 a known appearance where memory does not record it, and so
    on.  An ambiguous decision reports occlusion, which is not evidence either
    way, so both siblings receive byte-identical input.
    """
    special = topology["special"]
    spec: dict[str, Any] = {
        "visibility": "visible",
        "pose_valid": True,
        "depth_valid": True,
        "reliability": 1.0,
        "appearance_source": None,
        "place_id": None,
        "place_from_edge": None,
        "place_from_entity": None,
        "evidence_novel": True,
    }
    if ambiguous:
        # Occlusion is not evidence that a fact is false; it carries nothing.
        spec.update(visibility="occluded", reliability=0.0)
        return spec
    if template == "NOOP":
        # C00 pure viewpoint change, C09 pose fault, and a depth fault: in all
        # three the world did not change, so memory must be left alone.
        target = str(special["bind_target"])
        spec.update(appearance_source=target, place_from_entity=target,
                    evidence_novel=False)
        cause = int(reference_spec.get("noop_cause", 0))
        if cause == 1:
            spec.update(pose_valid=False, reliability=0.0)
        elif cause == 2:
            spec.update(depth_valid=False, reliability=0.0)
    elif template == "BIND":
        # C01 identity continuity: a known object, seen again from a new
        # viewpoint, so there is fresh evidence worth attaching.
        target = str(reference_spec["target_node_id"])
        spec.update(appearance_source=target, place_from_entity=target)
    elif template == "BIRTH":
        # A newly revealed object: its appearance is in no memory record yet.
        spec["appearance_source"] = str(reference_spec["new_node_id"])
    elif template == "REACTIVATE":
        target = str(reference_spec["target_node_id"])
        spec.update(appearance_source=target, place_from_entity=target)
    elif template == "SPLIT":
        # One stored record conflates two objects; only one is seen now.
        spec["appearance_source"] = f"{reference_spec['target_node_id']}::component:0"
    elif template == "MERGE":
        target = str(reference_spec["target_node_ids"][0])
        spec.update(appearance_source=target, place_from_entity=target)
    elif template == "RETRACT":
        spec.update(visibility="visible_empty",
                    place_from_edge=str(reference_spec["target_edge_id"]))
    elif template == "RELINK":
        spec["appearance_source"] = str(special["mover_ids"][
            special["mover_edges"].index(str(reference_spec["target_edge_id"]))
        ])
        spec["place_id"] = str(reference_spec["new_target"])
    elif template == "REPLACE":
        # Identity discontinuity: a different object now occupies the place.
        spec["appearance_source"] = str(reference_spec["new_node_id"])
        spec["place_id"] = str(reference_spec["new_target"])
    else:
        raise ValueError(f"unsupported observation template {template!r}")
    return spec


def _observed_appearance(
    spec: Mapping[str, Any], latents: Mapping[str, Any],
    rng: np.random.Generator, noise: float,
) -> list[float]:
    source = spec["appearance_source"]
    if spec["visibility"] != "visible" or source is None:
        return [0.0] * APPEARANCE_DIM
    observed = appearance_of(str(source), latents) + noise * rng.normal(
        0.0, 1.0, APPEARANCE_DIM,
    )
    return _unit(observed).round(8).tolist()


def _appearance_match(
    graph: Mapping[str, Any], observed: Sequence[float],
    spec: Mapping[str, Any], latents: Mapping[str, Any],
) -> dict[str, float]:
    """Compare the observation with what memory already stores.

    This is a fixed analytic perception summary standing in for the M2
    Projective Node Orbit, in the same controlled role as the retrieval
    features; it is not a learned representation.
    """
    vector = np.asarray(observed, dtype=np.float64)
    open_nodes = [
        node for node in graph["nodes"]
        if node.get("valid_to") is None and node["node_type"] == "entity"
    ]
    place_of: dict[str, str] = {
        str(edge["source"]): str(edge["target"])
        for edge in graph["edges"]
        if edge.get("valid_to") is None and edge["relation"] == "located_at"
    }
    observed_place = spec.get("resolved_place")
    scores: list[tuple[float, str]] = []
    dormant: list[float] = []
    for node in open_nodes:
        node_id = str(node["node_id"])
        similarity = float(appearance_of(node_id, latents) @ vector)
        if node["lifecycle"] == "dormant":
            dormant.append(similarity)
        else:
            scores.append((similarity, node_id))
    scores.sort(reverse=True)
    visible = spec["visibility"] == "visible" and float(np.linalg.norm(vector)) > 0.0
    best, best_id = (scores[0] if scores else (0.0, ""))
    second = scores[1][0] if len(scores) > 1 else 0.0
    return {
        "best": float(best) if visible else 0.0,
        "second": float(second) if visible else 0.0,
        "margin": float(best - second) if visible else 0.0,
        "best_dormant": float(max(dormant)) if visible and dormant else 0.0,
        "place_has_recorded_entity": float(
            observed_place is not None
            and observed_place in set(place_of.values())
        ),
        "best_match_recorded_here": float(
            visible and observed_place is not None
            and place_of.get(best_id) == observed_place
        ),
        # Memory puts this appearance somewhere else: the topology changed
        # rather than the identity being new.
        "best_match_recorded_elsewhere": float(
            visible and observed_place is not None
            and best_id in place_of and place_of[best_id] != observed_place
        ),
    }


def _event_variant(event: Mapping[str, Any], **updates: Any) -> dict[str, Any]:
    variant = clone_json(dict(event))
    variant.update(updates)
    return variant


def _proposal_context(
    graph: Mapping[str, Any], event: Mapping[str, Any],
) -> dict[str, Any]:
    """Build fixed argument ranks using only the current executable world.

    The audit-only ``reference_spec`` and scenario family are not read here.
    This makes it possible to mutate the complete reference transaction while
    proving that the proposed candidate list remains byte-for-byte unchanged.
    """
    open_nodes = [
        node for node in graph["nodes"] if node.get("valid_to") is None
    ]
    open_edges = [
        edge for edge in graph["edges"] if edge.get("valid_to") is None
    ]
    latest_nodes = {
        str(node["node_id"]): _latest_node(graph, str(node["node_id"]))
        for node in graph["nodes"]
    }
    latest_edges = {
        str(edge["edge_id"]): _latest_edge(graph, str(edge["edge_id"]))
        for edge in graph["edges"]
    }
    observation = event["proposal_observation"]
    bindable = _rank_by_observation(_ranked_ids(
        (
            node for node in open_nodes
            if node["node_type"] == "entity"
            and node["lifecycle"] in {"candidate", "confirmed"}
        ),
        event, kind="bind", id_key="node_id",
    ), observation["node_query"], event, kind="bind")
    confirmed = _rank_by_observation(_ranked_ids(
        (
            node for node in open_nodes
            if node["node_type"] == "entity"
            and node["lifecycle"] == "confirmed"
            and node.get("evidence_refs")
        ),
        event, kind="confirmed", id_key="node_id",
    ), observation["node_query"], event, kind="confirmed")
    dormant = _rank_by_observation(_ranked_ids(
        (
            node for node in open_nodes
            if node["node_type"] == "entity"
            and node["lifecycle"] == "dormant"
        ),
        event, kind="dormant", id_key="node_id",
    ), observation["node_query"], event, kind="dormant")
    fallback_entities = _rank_by_observation(_ranked_ids(
        (node for node in latest_nodes.values() if node["node_type"] == "entity"),
        event, kind="fallback-entity", id_key="node_id",
    ), observation["node_query"], event, kind="fallback-entity")
    if not bindable:
        bindable = fallback_entities
    if not confirmed:
        confirmed = fallback_entities
    edges = _rank_by_observation(_ranked_ids(
        open_edges or latest_edges.values(), event, kind="edge", id_key="edge_id",
    ), observation["edge_query"], event, kind="edge")
    open_places = [node for node in open_nodes if node["node_type"] == "place"]
    places = _rank_by_observation(_ranked_ids(
        open_places or [
            node for node in latest_nodes.values() if node["node_type"] == "place"
        ],
        event, kind="place", id_key="node_id",
    ), observation["place_query"], event, kind="place")
    bind_targets = _repeat_to(bindable, 2, name="bindable entity")
    connected_ids = {
        str(value)
        for edge in open_edges
        for value in (edge["source"], edge["target"])
    }
    split_pool = [value for value in confirmed if value not in connected_ids]
    split_targets = _repeat_to(
        split_pool or confirmed, 2, name="confirmed split source",
    )
    merge_targets = _repeat_to(confirmed, 4, name="confirmed merge source")
    merge_pairs: list[list[str]] = []
    observed_pair = []
    for slot, query in enumerate(observation["merge_queries"]):
        ranking = _rank_by_observation(
            confirmed, query, event, kind=f"merge-{slot}",
        )
        for value in ranking:
            if value not in observed_pair:
                observed_pair.append(value)
                break
        if len(observed_pair) == 2:
            break
    if len(observed_pair) == 2:
        merge_pairs.append(observed_pair)
    fallback_pairs = [
        [merge_targets[0], merge_targets[1]],
        [merge_targets[2], merge_targets[3]],
    ]
    for pair in fallback_pairs:
        if pair[0] != pair[1] and set(pair) not in [set(item) for item in merge_pairs]:
            merge_pairs.append(pair)
    if len(merge_pairs) < 2:
        raise ValueError("fixed candidate generator found fewer than two merge pairs")
    edge_targets = _repeat_to(edges, 6, name="open edge")
    place_targets = _repeat_to(places, 4, name="open place")
    # The three RELINK slots used to walk the diagonal (edge[i], place[i]).
    # Under a noisy query the true edge and the true place need not share a
    # rank, so a diagonal drops the reference pair; a small cross-product keeps
    # it reachable without pinning it to one slot.  Relinking an edge to the
    # place it already points at is a no-op that the canonical deduplication
    # would collapse into NOOP, so each slot skips its own current target.
    current_target = {
        str(edge["edge_id"]): str(edge["target"]) for edge in open_edges
    }
    relink_pairs = []
    for edge_rank, place_rank in RELINK_RANK_PAIRS:
        target_edge = edge_targets[edge_rank]
        options = [
            place for place in place_targets
            if place != current_target.get(target_edge)
        ] or place_targets
        relink_pairs.append([target_edge, options[place_rank % len(options)]])
    return {
        "relink_pairs": relink_pairs,
        "bind_targets": bind_targets,
        "reactivate_target": (dormant or bindable)[0],
        "edge_targets": edge_targets,
        "place_targets": place_targets,
        "split_targets": split_targets,
        "merge_pairs": merge_pairs[:2],
        "birth_id": f"candidate:{event['current_evidence_ref']}:birth",
        "split_successors": [
            [
                f"candidate:{event['current_evidence_ref']}:split:{slot}:left",
                f"candidate:{event['current_evidence_ref']}:split:{slot}:right",
            ]
            for slot in range(2)
        ],
        "replace_id": f"candidate:{event['current_evidence_ref']}:replace",
    }


def _build_fixed_candidate_catalog(
    graph: Mapping[str, Any], event: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Create the sixteen fixed proposals without reading the reference."""
    missing = set(CANDIDATE_EVENT_FIELDS) - set(event)
    if missing:
        raise ValueError(f"candidate event is missing fields {sorted(missing)}")
    event = {key: event[key] for key in CANDIDATE_EVENT_FIELDS}
    observation = event["proposal_observation"]
    if set(observation) != PROPOSAL_OBSERVATION_FIELDS:
        raise ValueError(
            "proposal_observation fields do not match the fixed generator contract"
        )
    if observation["source"] != PROPOSAL_RETRIEVAL_SOURCE:
        raise ValueError("unsupported fixed proposal-observation source")
    if len(observation["merge_queries"]) != 2:
        raise ValueError("proposal observation requires two merge queries")
    context = _proposal_context(graph, event)
    evidence: dict[str, dict[str, Any]] = {}
    programs: list[dict[str, Any]] = [_noop_program(graph, event)]
    programs.extend(
        _bind_program(graph, event, target, suffix=f"bind-{slot}")
        for slot, target in enumerate(context["bind_targets"])
    )
    programs.append(_bind_program(
        graph, event, str(event["protected_id"]),
        suffix="bind-protected-illegal",
    ))
    programs.append(_birth_program(
        graph, event, context["birth_id"], suffix="birth",
    ))
    reactivate_event = _event_variant(
        event, target_node_id=context["reactivate_target"],
    )
    programs.append(_reactivate_program(graph, reactivate_event))
    for slot, (target_edge, new_place) in enumerate(context["relink_pairs"]):
        relink_event = _event_variant(
            event,
            target_edge_id=target_edge,
            new_target=new_place,
            places=context["place_targets"],
        )
        program = _relink_program(graph, relink_event)
        program["transaction_id"] = f"{program['transaction_id']}:slot-{slot}"
        for operation in program["operations"]:
            if operation["op_type"] == "RECORD_PROVENANCE":
                operation["arguments"]["provenance_ref"] = program["transaction_id"]
            elif operation["op_type"] == "ADD_EDGE":
                operation["arguments"]["edge"]["provenance"] = [
                    program["transaction_id"]
                ]
        programs.append(program)
    for slot in range(2):
        retract_event = _event_variant(
            event, target_edge_id=context["edge_targets"][slot],
        )
        program, records = _retract_program(
            graph, retract_event, suffix=f"retract-{slot}",
        )
        programs.append(program)
        evidence.update(records)
    for slot in range(2):
        split_event = _event_variant(
            event,
            target_node_id=context["split_targets"][slot],
            successor_ids=context["split_successors"][slot],
        )
        program = _split_program(graph, split_event)
        program["transaction_id"] = f"{program['transaction_id']}:slot-{slot}"
        for operation in program["operations"]:
            if operation["op_type"] == "RECORD_PROVENANCE":
                operation["arguments"]["provenance_ref"] = program["transaction_id"]
            elif operation["op_type"] == "CREATE_NODE":
                operation["arguments"]["node"]["provenance"] = [
                    program["transaction_id"]
                ]
        programs.append(program)
    for slot, pair in enumerate(context["merge_pairs"]):
        merge_event = _event_variant(event, target_node_ids=pair)
        program = _merge_program(graph, merge_event)
        program["transaction_id"] = f"{program['transaction_id']}:slot-{slot}"
        for operation in program["operations"]:
            if operation["op_type"] == "RECORD_PROVENANCE":
                operation["arguments"]["provenance_ref"] = program["transaction_id"]
            elif operation["op_type"] == "OPEN_NODE_VERSION":
                operation["arguments"]["node"]["provenance"] = [
                    program["transaction_id"]
                ]
        programs.append(program)
    replace_event = _event_variant(
        event,
        target_edge_id=context["edge_targets"][0],
        new_node_id=context["replace_id"],
        new_target=context["place_targets"][0],
    )
    replace, records = _replace_program(graph, replace_event)
    programs.append(replace)
    evidence.update(records)
    if len(programs) != CANDIDATE_BUDGET:
        raise AssertionError("fixed candidate catalog must contain exactly K=16")
    return programs, evidence


def _primary_program(
    graph: Mapping[str, Any], event: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Construct the audit-only truth from its pre-frozen full transaction spec."""
    spec = event["reference_spec"]
    template = str(spec["template"])
    if template == "NOOP":
        return _noop_program(graph, event), {}
    if template == "BIND":
        return _bind_program(
            graph, event, str(spec["target_node_id"]), suffix="bind-0",
        ), {}
    if template == "BIRTH":
        return _birth_program(
            graph, event, str(spec["new_node_id"]), suffix="birth",
        ), {}
    if template == "REACTIVATE":
        return _reactivate_program(graph, _event_variant(
            event, target_node_id=spec["target_node_id"],
        )), {}
    if template == "RELINK":
        relink_event = _event_variant(
            event, target_edge_id=spec["target_edge_id"],
            new_target=spec["new_target"], places=spec["places"],
        )
        return _relink_program(graph, relink_event), {}
    if template == "RETRACT":
        return _retract_program(graph, _event_variant(
            event, target_edge_id=spec["target_edge_id"],
        ), suffix="retract-0")
    if template == "SPLIT":
        return _split_program(graph, _event_variant(
            event, target_node_id=spec["target_node_id"],
            successor_ids=spec["successor_ids"],
        )), {}
    if template == "MERGE":
        return _merge_program(graph, _event_variant(
            event, target_node_ids=spec["target_node_ids"],
        )), {}
    if template == "REPLACE":
        return _replace_program(graph, _event_variant(
            event, target_edge_id=spec["target_edge_id"],
            new_node_id=spec["new_node_id"],
            new_target=spec["new_target"],
        ))
    raise ValueError(f"unsupported rollout template {template!r}")


def _candidate_state_signature(
    base: Mapping[str, Any], graph: Mapping[str, Any],
    protected_ids: Iterable[str],
) -> str:
    identity_mapping = {
        str(node["node_id"]): str(node["node_id"]) for node in graph["nodes"]
    }
    state = canonicalize_memory_state(
        dict(base), dict(graph),
        identity_mapping=identity_mapping,
        protected_ids=frozenset(str(value) for value in protected_ids),
    )
    return canonical_json(state)


def _prepare_fixed_candidates(
    graph: Mapping[str, Any], event: Mapping[str, Any],
) -> tuple[
    list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any],
    list[str | None],
]:
    programs, evidence = _build_fixed_candidate_catalog(graph, event)
    executions = _execute_candidates(graph, programs, evidence)
    kept: list[dict[str, Any]] = []
    kept_signatures: list[str | None] = []
    signatures: set[str] = set()
    duplicate_count = 0
    legal_count = 0
    illegal_count = 0
    for program, execution in zip(programs, executions, strict=True):
        if not execution["legal"]:
            illegal_count += 1
            kept.append(program)
            kept_signatures.append(None)
            continue
        legal_count += 1
        signature = _candidate_state_signature(
            graph, execution["post_graph"], program.get("protected_ids", []),
        )
        if signature in signatures:
            duplicate_count += 1
            continue
        signatures.add(signature)
        kept.append(program)
        kept_signatures.append(signature)
    if len(kept) != CANDIDATE_BUDGET:
        raise AssertionError(
            "fixed K=16 catalog collapsed under canonical state deduplication: "
            f"kept={len(kept)} duplicates={duplicate_count}"
        )
    permutation = np.random.default_rng(
        int(event["candidate_seed"])
    ).permutation(len(kept))
    ordered = [kept[int(index)] for index in permutation]
    ordered_signatures = [kept_signatures[int(index)] for index in permutation]
    audit = {
        "generator": "fixed_deterministic_k16_v1",
        "budget_k": CANDIDATE_BUDGET,
        "raw_programs": len(programs),
        "deduplicated_programs": len(kept),
        "legal_programs": legal_count,
        "illegal_programs": illegal_count,
        "canonical_duplicates_removed": duplicate_count,
        "reference_fields_read": False,
    }
    return ordered, evidence, audit, ordered_signatures


def generate_fixed_candidates(
    graph: Mapping[str, Any], event: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    """Execute, canonicalize and deduplicate the fixed K=16 proposal set.

    Input is the current versioned world plus online event metadata.  Output is
    an ordered candidate program list, evidence records and a generation audit.
    The function does not decide which candidate is correct and does not read
    the hidden template, future trace or reference graph.
    """
    programs, evidence, audit, _ = _prepare_fixed_candidates(graph, event)
    return programs, evidence, audit


def _candidate_programs(
    graph: Mapping[str, Any], event: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], int]:
    programs, evidence, _, candidate_signatures = _prepare_fixed_candidates(
        graph, event,
    )
    reference, reference_evidence = _primary_program(graph, event)
    combined_evidence = {**evidence, **reference_evidence}
    reference_execution = _execute_candidates(
        graph, [reference], combined_evidence,
    )[0]
    if not reference_execution["legal"]:
        raise AssertionError(
            f"hidden reference is illegal: {reference_execution['failure']}"
        )
    reference_signature = _candidate_state_signature(
        graph, reference_execution["post_graph"], reference.get("protected_ids", []),
    )
    matches = [
        index for index, signature in enumerate(candidate_signatures)
        if signature == reference_signature
    ]
    if len(matches) != 1:
        raise AssertionError(
            "fixed candidate coverage requires exactly one canonical reference "
            f"match, found {len(matches)} for {event['reference_spec']['template']}"
        )
    return programs, combined_evidence, matches[0]


def audit_m1_candidate_coverage(
    config: Mapping[str, Any], split: str, *, paired_groups: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Audit K=16 against independently executed hidden references.

    This lightweight pre-training path advances the hidden reference world but
    does not build future traces, learning arrays or test data.  A missing
    canonical match is recorded as a candidate miss instead of being converted
    into a scorer or student error.
    """
    validate_m1_protocol(config)
    if split not in SPLIT_SEED_OFFSET:
        raise ValueError("M1 candidate audit exposes train/validation only; test is sealed")
    if paired_groups <= 0:
        raise ValueError("candidate audit paired_groups must be positive")
    retrieval = validate_proposal_retrieval(
        config["candidates"]["proposal_retrieval"]
    )
    observation = validate_observation_model(config["observation"])
    rows: list[dict[str, Any]] = []
    family_totals: dict[str, int] = {}
    family_covered: dict[str, int] = {}
    query_decided: list[bool] = []
    for group_index in range(paired_groups):
        world_seed = 360_906 + SPLIT_SEED_OFFSET[split] + group_index
        rng = np.random.default_rng(world_seed)
        current, topology = _initial_world(split, group_index, rng)
        events = _event_plan(
            topology, rng, retrieval,
            observation_noise=float(observation["appearance_noise"]),
        )
        for event in events:
            event["places"] = list(topology["special"]["places"])
            programs, evidence, generation, candidate_signatures = (
                _prepare_fixed_candidates(current, event)
            )
            reference, reference_evidence = _primary_program(current, event)
            combined_evidence = {**evidence, **reference_evidence}
            reference_execution = _execute_candidates(
                current, [reference], combined_evidence,
            )[0]
            reference_signature = (
                _candidate_state_signature(
                    current, reference_execution["post_graph"],
                    reference.get("protected_ids", []),
                )
                if reference_execution["legal"] else None
            )
            matches = [
                index for index, signature in enumerate(candidate_signatures)
                if reference_signature is not None and signature == reference_signature
            ]
            covered = bool(reference_execution["legal"] and len(matches) == 1)
            family = str(event["scenario_family"])
            family_totals[family] = family_totals.get(family, 0) + 1
            family_covered[family] = family_covered.get(family, 0) + int(covered)
            rows.append({
                "split": split,
                "paired_group_id": f"rollout-pair:{split}:{group_index:06d}",
                "world_seed": world_seed,
                "step_index": int(event["step_index"]),
                "scenario_family": family,
                "base_graph_hash": current["graph_hash"],
                "reference_template": str(event["reference_spec"]["template"]),
                "reference_legal": bool(reference_execution["legal"]),
                "reference_match_indices": matches,
                "candidate_covered": covered,
                "candidate_miss": not covered,
                "candidate_count": len(programs),
                "generation": generation,
                "reference_failure": reference_execution["failure"],
            })
            if covered:
                query_decided.append(_query_decides_reference(
                    programs, event["proposal_observation"], matches[0],
                ))
            if not reference_execution["legal"]:
                raise AssertionError(
                    "candidate audit hidden reference is illegal: "
                    f"{reference_execution['failure']}"
                )
            current = reference_execution["post_graph"]
    family_coverage = {
        family: float(family_covered.get(family, 0) / support)
        for family, support in sorted(family_totals.items())
    }
    overall = float(sum(family_covered.values()) / sum(family_totals.values()))
    overall_gate = float(config["candidates"]["coverage_gate_overall"])
    family_gate = float(config["candidates"]["coverage_gate_each_family"])
    summary = {
        "status": "candidate_coverage_audit_only_not_formal_gate",
        "split": split,
        "paired_groups": paired_groups,
        "decisions": len(rows),
        "candidate_budget_k": CANDIDATE_BUDGET,
        "candidate_reference_coverage": overall,
        "candidate_miss_rate": 1.0 - overall,
        "coverage_by_family": family_coverage,
        "support_by_family": dict(sorted(family_totals.items())),
        "minimum_family_coverage": min(family_coverage.values()),
        "coverage_gate_overall": overall_gate,
        "coverage_gate_each_family": family_gate,
        "coverage_thresholds_met": (
            overall >= overall_gate
            and min(family_coverage.values()) >= family_gate
        ),
        # The complete hidden transaction is frozen under reference_spec and is
        # never passed to the generator.  The query is derived from the hidden
        # argument, so it is only argument-independent once it carries noise or
        # a distractor; the exact-hash form made it an oracle pointer.
        "reference_template_independent": True,
        "proposal_retrieval": dict(retrieval),
        # Measured, not asserted: how often ranking candidates by query
        # similarity alone already returns the hidden reference.
        "reference_argument_decided_by_query": (
            float(sum(query_decided) / len(query_decided)) if query_decided else None
        ),
        "formal_gate_eligible": False,
        "coverage_gate_pass": False,
        "test_generated": False,
        "formal_data_ready": False,
        "future_scoring_run": False,
        "training_run": False,
    }
    return rows, summary


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


def standardize_future_term(values: Sequence[float | None]) -> list[float]:
    """Put a future term on a unit per-decision scale across candidates.

    The energy weights are shared by every method, but each method measures
    "future" in its own units: executed hindsight counts differing structural
    tokens (tens to hundreds) while a learned scorer reports a mean squared
    error over hashed features (about 1e-3).  One weight applied to both makes
    the learned term numerically irrelevant, so the method that predicts the
    future collapses onto the method that ignores it.  Dividing by the spread
    across this decision's candidates makes the weight mean the same thing for
    both, and preserves the ordering and the relative gaps within a decision.
    """
    present = [float(value) for value in values if value is not None]
    if not present:
        return [0.0 for _ in values]
    centre = float(np.mean(present))
    spread = float(np.std(present))
    if spread == 0.0:
        return [0.0 if value is None else 0.0 for value in values]
    return [
        0.0 if value is None else (float(value) - centre) / spread
        for value in values
    ]


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
    horizon: int,
) -> tuple[float, list[str], list[dict[str, Any]]]:
    branch = clone_json(candidate_post)
    errors = []
    hashes = []
    failures: list[dict[str, Any]] = []
    final_index = min(len(events), step_index + horizon)
    for target_index in range(step_index, final_index):
        if target_index > step_index:
            try:
                reference, evidence = _primary_program(
                    branch, events[target_index],
                )
                selected = _execute_candidates(
                    branch, [reference], evidence,
                )[0]
                failure = selected["failure"]
            except (CPMTError, LookupError, ValueError) as error:
                # A wrong earlier transaction can also make construction of a
                # later oracle program impossible (for example, SPLIT after its
                # source evidence was removed).  This is a causal branch
                # failure, not permission to restore the reference world.
                selected = None
                failure = {
                    "type": type(error).__name__,
                    "message": str(error),
                    "phase": "REFERENCE_PROGRAM_CONSTRUCTION",
                }
            if (
                selected is None
                or not selected["legal"]
                or selected["post_graph"] is None
            ):
                # A previous wrong edit can remove a later oracle target.  The
                # deterministic QUARANTINE fallback records that causal
                # consequence and leaves persistent memory unchanged.
                failures.append({
                    "step_index": target_index,
                    "reference_template": events[target_index][
                        "reference_spec"
                    ]["template"],
                    "failure": failure,
                    "fallback": "QUARANTINE_KEEP_CURRENT_WORLD",
                })
            else:
                branch = selected["post_graph"]
        pose = int(events[target_index]["pose_bucket"])
        prediction = project_structural_observation(branch, pose)
        target = project_structural_observation(reference_states[target_index], pose)
        errors.append(float(len(prediction ^ target)))
        hashes.append(branch["graph_hash"])
    return float(np.mean(errors)), hashes, failures


def _resolve_observed_place(
    graph: Mapping[str, Any], spec: Mapping[str, Any],
) -> str | None:
    """Resolve where the sensor is looking against the world at this step."""
    if spec.get("place_id"):
        return str(spec["place_id"])
    edge_id = spec.get("place_from_edge")
    entity_id = spec.get("place_from_entity")
    for edge in graph["edges"]:
        if edge.get("valid_to") is not None or edge["relation"] != "located_at":
            continue
        if edge_id and str(edge["edge_id"]) == str(edge_id):
            return str(edge["target"])
        if entity_id and str(edge["source"]) == str(entity_id):
            return str(edge["target"])
    return None


def _online_step(
    sequence_id: str, paired_group_id: str, split: str, world_seed: int,
    asset_family: str,
    base: Mapping[str, Any], event: Mapping[str, Any],
    programs: Sequence[Mapping[str, Any]],
    latents: Mapping[str, Any],
) -> dict[str, Any]:
    observation_rng = np.random.default_rng(int(event["observation_seed"]))
    spec = dict(event["observation_spec"])
    spec["resolved_place"] = _resolve_observed_place(base, spec)
    signature = _observed_appearance(
        spec, latents, observation_rng, float(event["observation_noise"]),
    )
    match = _appearance_match(base, signature, spec, latents)
    record = {
        "schema_version": "cpmt-m1-rollout-online-v1",
        "sequence_id": sequence_id,
        "paired_group_id": paired_group_id,
        "step_index": event["step_index"],
        "decision_time": event["decision_time"],
        "split": split,
        "world_seed": world_seed,
        "asset_family": asset_family,
        "prior_world": clone_json(base),
        "current_regions": [{
            "region_ref": event["current_evidence_ref"],
            "anonymous_signature": signature,
            "visibility": spec["visibility"],
            "pose_valid": bool(spec["pose_valid"]),
            "depth_valid": bool(spec["depth_valid"]),
            "reliability": float(spec["reliability"]),
            "evidence_novel": bool(spec["evidence_novel"]),
            "appearance_match": {
                key: float(value) for key, value in sorted(match.items())
            },
        }],
        "pose_history": [{
            "time_index": event["decision_time"],
            "pose_bucket": event["pose_bucket"],
            "valid": bool(spec["pose_valid"]),
        }],
        "action_history": ["controlled_revisit"],
        # The retrieval query the proposer was allowed to use.  Withholding it
        # while the generator ranks candidates by it leaves the student unable
        # to tell two same-template candidates apart.
        "proposal_observation": clone_json(dict(event["proposal_observation"])),
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
    observation = validate_observation_model(config["observation"])
    events = _event_plan(
        topology, rng,
        validate_proposal_retrieval(config["candidates"]["proposal_retrieval"]),
        observation_noise=float(observation["appearance_noise"]),
    )
    if sibling_index is not None and pivot_step is None:
        pivot_step = _ambiguity_pivot(events)
    if pivot_step is not None:
        _mark_decision_ambiguous(events[pivot_step])
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
    step_material = []
    current = clone_json(initial)
    for event in events:
        programs, evidence, primary_index = _candidate_programs(current, event)
        executions = _execute_candidates(current, programs, evidence)
        reference_index = primary_index
        if sibling_index == 1 and event["step_index"] == pivot_step:
            primary_template = str(event["reference_spec"]["template"])
            contrast_template = (
                "BIRTH" if primary_template == "BIND"
                else "BIND" if primary_template in {
                    "BIRTH", "REACTIVATE", "NOOP",
                }
                else "NOOP"
            )
            reference_index = next(
                item["candidate_index"]
                for item in executions
                if item["legal"] and item["template"] == contrast_template
            )
        reference = executions[reference_index]
        if not reference["legal"] or reference["post_graph"] is None:
            raise AssertionError(
                f"reference failed at {sequence_id} step {event['step_index']}: "
                f"{reference['failure']}"
            )
        online = _online_step(
            online_sequence_id, paired_group_id, split, world_seed, asset_family,
            current, event, programs, topology["semantic_latents"],
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
                # Same state in two representations: the exact token set the
                # executed teacher compares, and a continuous descriptor a
                # learned scorer can actually regress towards.
                "world_latent": project_world_latent(
                    reference_states[target_index], pose,
                    topology["semantic_latents"]),
                "structural_observation": sorted(
                    project_structural_observation(reference_states[target_index], pose)
                ),
            })
        raw_futures: list[float | None] = []
        traces: list[tuple[list[str], list[dict[str, Any]]]] = []
        for execution in material["executions"]:
            if execution["post_graph"] is None:
                raw_futures.append(None)
                traces.append(([], []))
                continue
            value, branch_hashes, branch_failures = _counterfactual_trace(
                execution["post_graph"], events, reference_states,
                step_index, hindsight_horizon,
            )
            raw_futures.append(value)
            traces.append((branch_hashes, branch_failures))
        scaled_futures = standardize_future_term(raw_futures)
        energies = []
        for index, (execution, program) in enumerate(zip(
            material["executions"], material["programs"], strict=True,
        )):
            illegal = float(not execution["legal"])
            future = scaled_futures[index]
            branch_hashes, branch_failures = traces[index]
            protected = [str(event["protected_id"])]
            # Both terms are computed rather than assumed, and the split summary
            # reports how often each one is nonzero.  In this fixture both are
            # structurally zero: _program_header gives every candidate an
            # evidence_ref, and the executor raises ProtectedMutationError for
            # any operation touching a protected id, so a collateral violation
            # cannot survive as a legal candidate.  Leaving them hardcoded would
            # imply the protocol's six energy terms are all active when three
            # are, with the largest weight (collateral, 10.0) on a constant.
            post = execution["post_graph"]
            collateral = 0.0 if post is None else float(
                protected_signature(post, protected)
                != protected_signature(material["online"]["prior_world"], protected)
            )
            terms = {
                "now": 0.0 if program.get("evidence_refs") else 1.0,
                "future": future,
                "edit": float(program.get("declared_edit_cost", 0.0)),
                "growth": float(program.get("declared_growth_cost", 0.0)),
                "collateral": collateral,
                "illegal": illegal,
            }
            total = None if illegal else sum(
                float(weights[key]) * terms[key] for key in weights
            )
            energies.append({
                **terms,
                "future_raw": raw_futures[index],
                "total": total,
                "masked": bool(illegal),
                "counterfactual_rollout_hashes": branch_hashes,
                "counterfactual_rollout_failures": branch_failures,
            })
        posterior = _teacher_posterior(energies, temperature)
        winner = int(np.argmax(posterior))
        reference_index = int(material["reference_index"])
        # The teacher is allowed to disagree with the reference, and that
        # disagreement is measured rather than treated as a generator bug.  It
        # happens where two candidates are nearly tied on future consistency
        # and the minimal-change cost then decides, which is what the energy is
        # for.  In the paired design it concentrates in the horizon-1 decisions
        # before the ambiguity pivot of sibling 1, whose executed future already
        # contains the contrast choice.  See docs/01_research_contract.md.
        teacher_disagrees = winner != reference_index
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
            "teacher_winner_matches_reference": not teacher_disagrees,
            "reference_template": material["executions"][reference_index]["template"],
            "ambiguity": (
                "epistemically_ambiguous_pivot"
                if sibling_index is not None and step_index == pivot_step
                else "sequence_context"
            ),
            "reference_post_graph_hash": reference_states[step_index]["graph_hash"],
            "transaction_label_available": labelled_group,
            "candidate_coverage_at_k": 1.0,
            "candidate_generation": {
                "generator": "fixed_deterministic_k16_v1",
                "budget_k": CANDIDATE_BUDGET,
                "raw_programs": CANDIDATE_BUDGET,
                "deduplicated_programs": len(material["programs"]),
                "legal_programs": sum(
                    bool(item["legal"]) for item in material["executions"]
                ),
                "illegal_programs": sum(
                    not bool(item["legal"]) for item in material["executions"]
                ),
                "reference_matching": "canonical_memory_state",
                "reference_fields_read_by_generator": False,
            },
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
        "primary_event_order": [
            event["reference_spec"]["template"] for event in events
        ],
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
        "candidate_set_size": CANDIDATE_BUDGET,
        "test_generated": False,
        "formal_data_ready": False,
        "paired_latent_siblings_ready": False,
        "front_end": "controlled_structural_token_projector_not_pno",
        "note": (
            "Each sequence is a real chained graph trajectory and supports predicted-state "
            "replay. Fixed deterministic K=16 candidates are active; formal-scale "
            "coverage, visual PNO input, and A-F training remain pending."
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
        # Surfaced so a rise in teacher disagreement cannot pass unnoticed.
        # Which declared energy terms actually vary. A term that is always the
        # same value carries no signal no matter what weight the protocol gives
        # it, and the reader should not have to guess which ones those are.
        "energy_term_variation": {
            term: {
                "nonzero_fraction": float(np.mean([
                    float(energy[term]) != 0.0
                    for audit in audits for step in audit["steps"]
                    for energy in step["candidate_energies"]
                ])),
                "distinct_values": len({
                    round(float(energy[term]), 9)
                    for audit in audits for step in audit["steps"]
                    for energy in step["candidate_energies"]
                }),
            }
            for term in ("now", "future", "edit", "growth", "collateral", "illegal")
        },
        "teacher_reference_agreement": float(np.mean([
            bool(step["teacher_winner_matches_reference"])
            for audit in audits for step in audit["steps"]
        ])),
        "teacher_disagreement_decisions": int(sum(
            not step["teacher_winner_matches_reference"]
            for audit in audits for step in audit["steps"]
        )),
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
        "candidate_set_size": CANDIDATE_BUDGET,
        "test_generated": False,
        "formal_data_ready": False,
        "paired_latent_siblings_ready": True,
        "front_end": "controlled_structural_token_projector_not_pno",
        "note": (
            "Paired siblings now provide one exact same-online/different-reference pivot "
            "inside a causal 20-step chain with fixed deterministic K=16 candidates. "
            "Formal-scale coverage and A-F training remain pending."
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
    programs, evidence, _ = generate_fixed_candidates(base, event)
    executions = _execute_candidates(base, programs, evidence)
    source_online = stored["online"]
    online = _online_step(
        source_online["sequence_id"], source_online["paired_group_id"],
        source_online["split"], int(source_online["world_seed"]),
        source_online["asset_family"], base, event, programs,
        audit_sequence["topology"]["semantic_latents"],
    )
    return {
        "step_index": step_index,
        "online": online,
        "executed_candidates": executions,
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
        programs, evidence, _ = generate_fixed_candidates(current, event)
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
            "failure": selected["failure"],
        })
    return {"states": states, "base_states": bases, "decisions": decisions}


def records_sha256(records: Iterable[Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for record in records:
        digest.update(canonical_json(record).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()
