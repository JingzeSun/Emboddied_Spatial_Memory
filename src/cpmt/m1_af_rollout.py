"""A-F learning adapters and causal evaluation for procedural M1 rollouts.

This is an interface-validation runner, not the frozen formal gate.  A-E share
one online feature boundary and one student architecture; future information
is used only by training targets/auxiliary losses.  Deployment rebuilds every
next candidate set from the method's own predicted persistent graph.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import math
import time
from typing import Any, Mapping, Sequence

import numpy as np
import torch
from torch.nn import functional as F

from .dev_learning import (
    METHODS,
    OnlineModel,
    train_outcome_scorer,
    train_student,
    tensors,
)
from .executor import operation_argument_ids
from .hashing import clone_json
from .m1_metrics import graph_error_counts, rollout_graph_metrics
from .m1_rollout import (
    CANDIDATE_BUDGET,
    APPEARANCE_DIM,
    PROPOSAL_FEATURE_DIM,
    VISIBILITY_KINDS,
    candidate_argument_ids,
    generate_m1_paired_rollout_split,
    materialize_rollout_step,
    stable_retrieval_feature,
)
from .m1_protocol import validate_m1_protocol
from .pending import decide_commit


NODE_TYPES = ("entity", "surface", "place", "chart", "region")
LIFECYCLES = ("candidate", "confirmed", "dormant", "retracted", "alias")
TEMPLATES = (
    "NOOP", "BIND", "BIRTH", "REACTIVATE", "RELINK", "RETRACT",
    "SPLIT", "MERGE", "REPLACE",
)
INTENTS = ("PRESERVE", "ASSOCIATE", "EXPAND", "REVISE")
OP_TYPES = (
    "ASSERT_PRECONDITION", "ATTACH_EVIDENCE", "CREATE_NODE",
    "OPEN_NODE_VERSION", "CLOSE_NODE_VERSION", "ADD_EDGE",
    "CLOSE_EDGE_VERSION", "SET_LIFECYCLE", "RECORD_PROVENANCE",
)
QUERY_KINDS = ("node_query", "edge_query", "place_query")
FUTURE_RELATION_QUERIES = (
    "added_edge_holds",
    "closed_edge_absent",
    "affected_node_active",
    "requested_lifecycle_holds",
    "candidate_evidence_associated",
    "no_revision_needed_now",
)
MATCH_KEYS = (
    "best", "second", "margin", "best_dormant",
    "place_has_recorded_entity", "best_match_recorded_here",
    "best_match_recorded_elsewhere",
)
# Per-candidate block: template, intent, three costs, op-type counts, the
# protected-id flag, then two similarities per query plus an argument count.
CANDIDATE_FEATURE_DIM = (
    len(TEMPLATES) + len(INTENTS) + 3 + len(OP_TYPES) + 1
    + 2 * len(QUERY_KINDS) + 1
)
# World summary, observed appearance, the evidence report that replaces the
# scenario-family one-hot, pose, and step position.
ONLINE_CONTEXT_DIM = (
    len(NODE_TYPES) + len(LIFECYCLES) + 3 + 8 + APPEARANCE_DIM
    + len(VISIBILITY_KINDS) + 4 + len(MATCH_KEYS) + 8 + 1
)


def resolve_af_smoke_config(
    hard_config: Mapping[str, Any], smoke_config: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the nonformal runner config and attach frozen M1 constants."""
    validate_m1_protocol(hard_config)
    config = deepcopy(dict(smoke_config))
    if (
        config.get("protocol") != "m1-af-causal-rollout-smoke-v2"
        or config.get("stage") != "M1-development"
        or config.get("formal_run") is not False
        or config.get("test_access") is not False
    ):
        raise ValueError("A-F smoke config must remain nonformal and test-sealed")
    for split in ("train", "validation"):
        if int(config["paired_groups"][split]) <= 0:
            raise ValueError("A-F smoke paired-group counts must be positive")
    for name in (
        "future_hash_bins", "hidden_dim", "student_steps", "scorer_steps",
        "batch_size", "cpu_threads",
    ):
        if int(config[name]) <= 0:
            raise ValueError(f"invalid A-F smoke setting {name}")
    if not config["seeds"] or len(set(config["seeds"])) != len(config["seeds"]):
        raise ValueError("A-F smoke seeds must be nonempty and unique")
    config["candidate_feature_dim"] = CANDIDATE_FEATURE_DIM
    config["standardize_future_term"] = True
    config["horizon"] = int(hard_config["future"]["primary_horizon"])
    config["temperature"] = float(hard_config["energy"]["temperature"])
    config["energy_weights"] = deepcopy(hard_config["energy"]["weights"])
    return config


def _program_label(program: Mapping[str, Any]) -> str:
    return (
        str(program.get("composition_label", "COMPOSITE"))
        if program["template"] == "COMPOSITE"
        else str(program["template"])
    )


def _one_hot(value: str, values: Sequence[str]) -> list[float]:
    return [float(value == candidate) for candidate in values]


def _stable_bin(value: str, bins: int) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:16], 16) % bins


def paired_group_is_calibration(paired_group_id: str) -> bool:
    """Deterministically keep both siblings in one validation half."""
    digest = hashlib.sha256(str(paired_group_id).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % 2 == 0


def _argument_features(
    program: Mapping[str, Any], queries: Mapping[str, np.ndarray],
) -> list[float]:
    """Align a candidate's arguments to the proposer's retrieval query.

    Without this the three RELINK candidates, and every other same-template
    slot, encode to identical blocks and no scorer can separate them.  Only
    anonymous similarities are exported, never an identity string.
    """
    identifiers = candidate_argument_ids(program)
    vectors = (
        np.asarray([stable_retrieval_feature(value) for value in identifiers],
                   dtype=np.float64)
        if identifiers else np.zeros((1, PROPOSAL_FEATURE_DIM), dtype=np.float64)
    )
    values: list[float] = []
    for kind in QUERY_KINDS:
        similarity = vectors @ queries[kind]
        values.extend([float(similarity.max()), float(similarity.mean())])
    values.append(len(identifiers) / 6.0)
    return values


def _program_touches_protected(program: Mapping[str, Any]) -> bool:
    """Match protected IDs by executor-style structured fields, never substrings."""
    touched_ids = set().union(*(
        operation_argument_ids(operation.get("arguments", {}))
        for operation in program["operations"]
    )) if program["operations"] else set()
    protected_ids = {
        str(value) for value in program.get("protected_ids", [])
    }
    return bool(touched_ids & protected_ids)


def online_feature_vector(online: Mapping[str, Any]) -> np.ndarray:
    """Encode only one deployable online record; audit records are rejected."""
    required = {
        "schema_version", "sequence_id", "paired_group_id", "step_index",
        "decision_time", "split", "world_seed",
        "asset_family", "prior_world", "current_regions",
        "pose_history", "action_history", "proposal_observation",
        "candidate_programs",
    }
    if set(online) != required:
        raise ValueError("online feature encoder accepts exactly the rollout online schema")
    graph = online["prior_world"]
    open_nodes = [node for node in graph["nodes"] if node.get("valid_to") is None]
    open_edges = [edge for edge in graph["edges"] if edge.get("valid_to") is None]
    closed_edges = len(graph["edges"]) - len(open_edges)
    values: list[float] = []
    node_type_counts = Counter(node["node_type"] for node in open_nodes)
    lifecycle_counts = Counter(node["lifecycle"] for node in graph["nodes"])
    values.extend(node_type_counts[name] / 32.0 for name in NODE_TYPES)
    values.extend(lifecycle_counts[name] / 32.0 for name in LIFECYCLES)
    values.extend([
        len(open_edges) / 32.0,
        closed_edges / 32.0,
        len(graph["transaction_log"]) / 20.0,
    ])
    relation_bins = [0.0] * 8
    for edge in open_edges:
        relation_bins[_stable_bin(str(edge["relation"]), len(relation_bins))] += 1 / 16.0
    values.extend(relation_bins)
    region = online["current_regions"][0]
    signature = region["anonymous_signature"]
    if len(signature) != APPEARANCE_DIM:
        raise ValueError(
            f"rollout online appearance must have length {APPEARANCE_DIM}"
        )
    values.extend(float(item) for item in signature)
    # Evidence about the decision, generated from the executed world.  This
    # replaces a scenario-family one-hot that named the reference template.
    values.extend(_one_hot(str(region["visibility"]), VISIBILITY_KINDS))
    values.extend([
        float(bool(region["pose_valid"])),
        float(bool(region["depth_valid"])),
        float(region["reliability"]),
        float(bool(region["evidence_novel"])),
    ])
    match = region["appearance_match"]
    values.extend(float(match[key]) for key in MATCH_KEYS)
    pose = int(online["pose_history"][-1]["pose_bucket"])
    values.extend(float(index == pose) for index in range(8))
    values.append(float(online["step_index"]) / 19.0)
    if len(values) != ONLINE_CONTEXT_DIM:
        raise AssertionError("online context block changed size without a constant update")

    observation = online["proposal_observation"]
    queries = {
        kind: np.asarray(observation[kind], dtype=np.float64)
        for kind in QUERY_KINDS
    }
    for query in queries.values():
        if query.shape != (PROPOSAL_FEATURE_DIM,) or not np.isfinite(query).all():
            raise ValueError("online proposal query has invalid shape or values")
    programs = online["candidate_programs"]
    if len(programs) != CANDIDATE_BUDGET:
        raise ValueError(
            f"A-F adapter requires the frozen K={CANDIDATE_BUDGET} candidates"
        )
    for program in programs:
        block: list[float] = []
        block.extend(_one_hot(_program_label(program), TEMPLATES))
        block.extend(_one_hot(str(program["intent"]), INTENTS))
        block.extend([
            float(program.get("declared_edit_cost", 0.0)) / 2.0,
            float(program.get("declared_growth_cost", 0.0)) / 2.0,
            len(program["operations"]) / 10.0,
        ])
        operation_counts = Counter(
            operation["op_type"] for operation in program["operations"]
        )
        block.extend(operation_counts[name] / 4.0 for name in OP_TYPES)
        block.append(float(_program_touches_protected(program)))
        block.extend(_argument_features(program, queries))
        if len(block) != CANDIDATE_FEATURE_DIM:
            raise AssertionError(
                "candidate block changed size without a constant update"
            )
        values.extend(block)
    vector = np.asarray(values, dtype=np.float32)
    if not np.isfinite(vector).all():
        raise ValueError("online feature vector contains a non-finite value")
    return vector


def future_feature_vector(
    future_trace: Sequence[Mapping[str, Any]], *, horizon: int, bins: int,
    representation: str = "hashed_tokens",
) -> np.ndarray:
    """Build the training-time future target from audit-only observations.

    ``hashed_tokens`` buckets the exact structural tokens, which is faithful but
    metric-free: two worlds differing by one edge land in unrelated buckets, so
    the regression error says almost nothing about how wrong a prediction is.
    ``world_latent`` keeps the same state in a continuous space where distance
    is meaningful, so a learned scorer is a fair baseline instead of one
    handicapped by its target.
    """
    if len(future_trace) > horizon:
        raise ValueError("future trace exceeds configured horizon")
    if representation == "world_latent":
        width = len(future_trace[0]["world_latent"]) if future_trace else 0
        if width == 0:
            raise ValueError("future trace carries no world_latent")
        values = np.zeros((horizon, width), dtype=np.float32)
        mask = np.zeros(horizon, dtype=np.float32)
        for time_index, observation in enumerate(future_trace):
            values[time_index] = np.asarray(
                observation["world_latent"], dtype=np.float32)
            mask[time_index] = 1.0
        return np.concatenate([values.reshape(-1), mask])
    if representation != "hashed_tokens":
        raise ValueError(f"unsupported future target representation {representation!r}")
    values = np.zeros((horizon, bins), dtype=np.float32)
    mask = np.zeros(horizon, dtype=np.float32)
    for time_index, observation in enumerate(future_trace):
        tokens = observation["structural_observation"]
        mask[time_index] = 1.0
        scale = 1.0 / max(1, len(tokens))
        for token in tokens:
            values[time_index, _stable_bin(str(token), bins)] += scale
    return np.concatenate([values.reshape(-1), mask])


def candidate_future_relation_targets(
    program: Mapping[str, Any], base: Mapping[str, Any],
    future_states: Sequence[Mapping[str, Any]], *, horizon: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build candidate-scoped relation queries from actual future worlds.

    Each query asks whether a concrete effect named by the transaction program
    is true later (for example, whether its proposed ``located_at`` edge holds).
    The target is read from the real reference trajectory, not from executing
    this candidate.  The desired vector says which queried effects the
    candidate claims should hold.  This is the structured no-execution target
    used by C and E; it is not a transaction label or a post-world embedding.
    """
    width = len(FUTURE_RELATION_QUERIES)
    targets = np.zeros((horizon, width), dtype=np.float32)
    masks = np.zeros((horizon, width), dtype=np.float32)
    desired = np.zeros((horizon, width), dtype=np.float32)
    operations = list(program["operations"])
    added_edges = [
        operation["arguments"]["edge"] for operation in operations
        if operation["op_type"] == "ADD_EDGE"
    ]
    closed_edges = []
    for operation in operations:
        if operation["op_type"] != "CLOSE_EDGE_VERSION":
            continue
        edge_id = str(operation["arguments"]["edge_id"])
        match = next((
            edge for edge in base["edges"]
            if str(edge["edge_id"]) == edge_id and edge.get("valid_to") is None
        ), None)
        if match is not None:
            closed_edges.append(match)
    affected_nodes = [
        operation["arguments"]["node"] for operation in operations
        if operation["op_type"] in {"CREATE_NODE", "OPEN_NODE_VERSION"}
    ]
    requested_lifecycles: list[tuple[str, str]] = []
    for operation in operations:
        if operation["op_type"] == "SET_LIFECYCLE":
            requested_lifecycles.append((
                str(operation["arguments"]["node_id"]),
                str(operation["arguments"]["to"]),
            ))
        elif operation["op_type"] in {"CREATE_NODE", "OPEN_NODE_VERSION"}:
            node = operation["arguments"]["node"]
            requested_lifecycles.append((
                str(node["node_id"]), str(node["lifecycle"]),
            ))
    evidence_queries: list[tuple[str, str | None, str | None, str]] = []
    for operation in operations:
        if operation["op_type"] != "ATTACH_EVIDENCE":
            continue
        arguments = operation["arguments"]
        evidence_queries.append((
            str(arguments["target_kind"]),
            str(arguments["target_id"]) if "target_id" in arguments else None,
            str(arguments.get("node_version_id") or arguments.get("edge_version_id"))
            if (arguments.get("node_version_id") or arguments.get("edge_version_id"))
            else None,
            str(arguments["evidence_ref"]),
        ))

    def open_edges(graph: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        return [edge for edge in graph["edges"] if edge.get("valid_to") is None]

    def edge_holds(graph: Mapping[str, Any], query: Mapping[str, Any]) -> bool:
        return any(
            all(edge.get(key) == query.get(key) for key in (
                "source", "target", "relation", "frame",
            ))
            for edge in open_edges(graph)
        )

    def evidence_holds(
        graph: Mapping[str, Any], query: tuple[str, str | None, str | None, str],
    ) -> bool:
        kind, stable_id, version_id, evidence_ref = query
        records = graph["nodes"] if kind == "node" else graph["edges"]
        id_key = "node_id" if kind == "node" else "edge_id"
        version_key = "node_version_id" if kind == "node" else "edge_version_id"
        return any(
            (stable_id is None or str(record[id_key]) == stable_id)
            and (version_id is None or str(record[version_key]) == version_id)
            and evidence_ref in record.get("evidence_refs", [])
            for record in records
        )

    for time_index, graph in enumerate(future_states[:horizon]):
        if added_edges:
            masks[time_index, 0] = desired[time_index, 0] = 1.0
            targets[time_index, 0] = float(all(
                edge_holds(graph, edge) for edge in added_edges
            ))
        if closed_edges:
            masks[time_index, 1] = desired[time_index, 1] = 1.0
            targets[time_index, 1] = float(all(
                not edge_holds(graph, edge) for edge in closed_edges
            ))
        if affected_nodes:
            masks[time_index, 2] = desired[time_index, 2] = 1.0
            targets[time_index, 2] = float(all(any(
                str(node["node_id"]) == str(query["node_id"])
                and node.get("valid_to") is None
                for node in graph["nodes"]
            ) for query in affected_nodes))
        if requested_lifecycles:
            masks[time_index, 3] = desired[time_index, 3] = 1.0
            targets[time_index, 3] = float(all(any(
                str(node["node_id"]) == node_id
                and node.get("valid_to") is None
                and str(node["lifecycle"]) == lifecycle
                for node in graph["nodes"]
            ) for node_id, lifecycle in requested_lifecycles))
        if evidence_queries:
            masks[time_index, 4] = desired[time_index, 4] = 1.0
            targets[time_index, 4] = float(all(
                evidence_holds(graph, query) for query in evidence_queries
            ))
    if _program_label(program) == "NOOP" and future_states:
        masks[0, 5] = desired[0, 5] = 1.0
        targets[0, 5] = graph_error_counts(
            base, future_states[0], base, [],
        )["open_memory_correct"]
    if not masks.any():
        raise ValueError(
            f"candidate {_program_label(program)!r} produced no future relation query"
        )
    return targets.reshape(-1), masks.reshape(-1), desired.reshape(-1)


def _posterior_from_current_energy(
    step: Mapping[str, Any], weights: Mapping[str, float], temperature: float,
) -> np.ndarray:
    totals = []
    for energy in step["candidate_energies"]:
        if energy["masked"]:
            totals.append(math.inf)
        else:
            totals.append(sum(
                float(weights[key]) * float(energy[key])
                for key in ("now", "edit", "growth", "collateral")
            ))
    finite = [value for value in totals if math.isfinite(value)]
    minimum = min(finite)
    raw = np.asarray([
        0.0 if not math.isfinite(value)
        else math.exp(-(value - minimum) / temperature)
        for value in totals
    ], dtype=np.float64)
    return (raw / raw.sum()).astype(np.float32)


def build_rollout_learning_arrays(
    hard_config: Mapping[str, Any], split: str, *, paired_groups: int,
    future_hash_bins: int,
) -> tuple[dict[str, np.ndarray], list[dict[str, Any]], dict[str, Any]]:
    """Convert paired rollout audit into shared online tensors and targets."""
    online, audits, summary = generate_m1_paired_rollout_split(
        hard_config, split, paired_groups=paired_groups,
    )
    del online
    arrays = rollout_learning_arrays_from_audits(
        hard_config, audits, future_hash_bins=future_hash_bins,
    )
    summary = deepcopy(summary)
    summary.update({
        "learning_cases": len(arrays["y"]),
        "online_feature_dim": int(arrays["x"].shape[1]),
        "future_target_dim": int(arrays["future"].shape[1]),
        "future_relation_target_dim": int(arrays["relation_targets"].shape[2]),
        "labelled_fraction": float(arrays["labelled"].mean()),
        "ambiguous_decision_fraction": float(arrays["ambiguous"].mean()),
    })
    return arrays, audits, summary


def rollout_learning_arrays_from_audits(
    hard_config: Mapping[str, Any], audits: Sequence[Mapping[str, Any]], *,
    future_hash_bins: int,
) -> dict[str, np.ndarray]:
    """Encode already generated audit sequences without retaining online duplicates."""
    if not audits:
        raise ValueError("rollout learning arrays require at least one audit sequence")
    rows = []
    group_ids = {
        name: index for index, name in enumerate(sorted({
            audit["paired_group_id"] for audit in audits
        }))
    }
    weights = hard_config["energy"]["weights"]
    temperature = float(hard_config["energy"]["temperature"])
    horizon = int(hard_config["future"]["primary_horizon"])
    representation = str(hard_config["future"]["target_representation"])
    for audit in audits:
        learning_steps = list(enumerate(audit["steps"])) + [
            (int(step["source_step_index"]), step)
            for step in audit.get("recovery_examples", [])
        ]
        for step_index, step in learning_steps:
            candidate_metrics = []
            base = step["online"]["prior_world"]
            reference = step["executed_candidates"][
                step["reference_program_index"]
            ]["post_graph"]
            protected = [step["event_spec"]["protected_id"]]
            for candidate in step["executed_candidates"]:
                predicted = candidate["post_graph"] if candidate["legal"] else base
                candidate_metrics.append(
                    graph_error_counts(predicted, reference, base, protected)
                )
            base_metrics = graph_error_counts(base, reference, base, protected)
            penalties = []
            for energy in step["candidate_energies"]:
                if energy["masked"]:
                    penalties.append(1_000_000.0)
                else:
                    penalties.append(sum(
                        float(weights[key]) * float(energy[key])
                        for key in ("now", "edit", "growth", "collateral")
                    ))
            no_execution_penalties = []
            for program in step["online"]["candidate_programs"]:
                protected_touch = float(_program_touches_protected(program))
                no_execution_penalties.append(
                    float(weights["now"])
                    * (0.0 if program.get("evidence_refs") else 1.0)
                    + float(weights["edit"])
                    * float(program.get("declared_edit_cost", 0.0))
                    + float(weights["growth"])
                    * float(program.get("declared_growth_cost", 0.0))
                    + float(weights["collateral"]) * protected_touch
                )
            future_states = [
                audit["steps"][target_index]["executed_candidates"][
                    audit["steps"][target_index]["reference_program_index"]
                ]["post_graph"]
                for target_index in range(
                    step_index, min(len(audit["steps"]), step_index + horizon)
                )
            ]
            relation_rows = [
                candidate_future_relation_targets(
                    program, base, future_states, horizon=horizon,
                )
                for program in step["online"]["candidate_programs"]
            ]
            rows.append({
                "x": online_feature_vector(step["online"]),
                "future": future_feature_vector(
                    step["future_trace"], horizon=horizon, bins=future_hash_bins,
                    representation=representation,
                ),
                "poses": np.asarray([
                    item["pose_bucket"] / 7.0 for item in step["future_trace"]
                ] + [0.0] * (horizon - len(step["future_trace"])), dtype=np.float32),
                "relation_targets": np.asarray([
                    item[0] for item in relation_rows
                ], dtype=np.float32),
                "relation_mask": np.asarray([
                    item[1] for item in relation_rows
                ], dtype=np.float32),
                "relation_desired": np.asarray([
                    item[2] for item in relation_rows
                ], dtype=np.float32),
                "y": int(step["reference_program_index"]),
                "pstar": np.asarray(step["teacher_posterior"], dtype=np.float32),
                "pstar_current": _posterior_from_current_energy(
                    step, weights, temperature,
                ),
                "labelled": bool(step["transaction_label_available"]),
                "ambiguous": step["ambiguity"] == "epistemically_ambiguous_pivot",
                "recovery": step["ambiguity"] == "counterfactual_recovery_training",
                "group": group_ids[audit["paired_group_id"]],
                "calibration": paired_group_is_calibration(
                    str(audit["paired_group_id"])
                ),
                "candidate_legal": np.asarray([
                    candidate["legal"] for candidate in step["executed_candidates"]
                ], dtype=bool),
                "active_correct": np.asarray([
                    item["active_graph_correct"] for item in candidate_metrics
                ], dtype=np.float32),
                "base_active_correct": float(
                    base_metrics["active_graph_correct"]
                ),
                "fact_errors": np.asarray([
                    item["memory_contamination"] + item["missing_open_facts"]
                    for item in candidate_metrics
                ], dtype=np.float32),
                "base_fact_errors": float(
                    base_metrics["memory_contamination"]
                    + base_metrics["missing_open_facts"]
                ),
                "excess_nodes": np.asarray([
                    item["false_birth_growth"] for item in candidate_metrics
                ], dtype=np.float32),
                "base_excess_nodes": float(base_metrics["false_birth_growth"]),
                "penalties": np.asarray(penalties, dtype=np.float32),
                "no_execution_penalties": np.asarray(
                    no_execution_penalties, dtype=np.float32,
                ),
                # Template index per candidate, so selection error can be split
                # into a template part and an argument part.
                "candidate_templates": np.asarray([
                    TEMPLATES.index(_program_label(program))
                    for program in step["online"]["candidate_programs"]
                ], dtype=np.int64),
            })
    arrays = {
        key: np.asarray([row[key] for row in rows])
        for key in rows[0]
    }
    return arrays


def selection_error_decomposition(
    probabilities: np.ndarray, arrays: Mapping[str, np.ndarray],
) -> dict[str, Any]:
    """Split selection error into template, argument and ambiguous-pivot parts.

    A model can fail because it picked the wrong kind of edit, or because it
    picked the right kind and pointed it at the wrong node/edge/place.  These
    have different causes and only the first is what hindsight supervision is
    meant to improve, so reporting one accuracy hides the result.
    """
    templates = np.asarray(arrays["candidate_templates"])
    target = np.asarray(arrays["y"])
    ambiguous = np.asarray(arrays["ambiguous"], dtype=bool)
    recovery = np.asarray(
        arrays.get("recovery", np.zeros(len(target), dtype=bool)), dtype=bool,
    )
    online_chain = ~recovery
    identifiable = ~ambiguous & online_chain
    predicted = np.asarray(probabilities).argmax(axis=1)
    rows = np.arange(len(target))
    predicted_template = templates[rows, predicted]
    target_template = templates[rows, target]
    template_correct = predicted_template == target_template
    correct = predicted == target
    candidate_legal = arrays.get("candidate_legal")
    raw_illegal = None
    if candidate_legal is not None:
        candidate_legal = np.asarray(candidate_legal, dtype=bool)
        if candidate_legal.shape != np.asarray(probabilities).shape:
            raise ValueError(
                "candidate legality and probabilities must have equal shape"
            )
        raw_illegal = ~candidate_legal[rows, predicted]
    pair_contains = np.zeros(len(target), dtype=bool)
    ambiguous_groups = 0
    for group in np.unique(np.asarray(arrays["group"])[ambiguous]):
        mask = ambiguous & (np.asarray(arrays["group"]) == group)
        legal_pair = set(int(value) for value in target[mask])
        if len(legal_pair) != 2:
            raise ValueError(
                "each exact ambiguity group must expose two distinct references"
            )
        pair_contains[mask] = np.isin(predicted[mask], list(legal_pair))
        ambiguous_groups += 1

    def mean(values: np.ndarray, mask: np.ndarray | None = None) -> float | None:
        selected = values if mask is None else values[mask]
        return float(selected.mean()) if len(selected) else None

    return {
        "accuracy": mean(correct, online_chain),
        "all_learning_rows_accuracy": mean(correct),
        "online_chain_accuracy": mean(correct, online_chain),
        "template_accuracy": mean(template_correct, online_chain),
        "argument_accuracy_given_template": mean(
            correct, template_correct & online_chain,
        ),
        "template_error": mean(~template_correct, online_chain),
        "argument_error_with_correct_template": mean(
            template_correct & ~correct, online_chain,
        ),
        "identifiable_accuracy": mean(correct, identifiable),
        "ambiguous_accuracy": mean(correct, ambiguous),
        "recovery_accuracy": mean(correct, recovery),
        # Legality audits the already selected candidate. It is never fed back
        # into E or another online selector.
        "raw_illegal_selection_rate": (
            mean(raw_illegal, online_chain) if raw_illegal is not None else None
        ),
        "ambiguous_pair_containment": mean(pair_contains, ambiguous),
        "ambiguous_paired_groups": ambiguous_groups,
        "ambiguous_fraction": mean(ambiguous, online_chain),
        "recovery_fraction": mean(recovery),
    }


def structured_relation_oracle_probabilities(
    arrays: Mapping[str, np.ndarray], *, future_weight: float,
    temperature: float,
) -> np.ndarray:
    """Rank candidates with perfect knowledge of the registered relation target.

    This diagnostic reads the audit-only truth of each candidate-scoped query,
    compares it with the effect claimed by that candidate, and combines the
    resulting mismatch with the same no-execution declaration penalty used by
    E.  It never reads or executes a candidate post-world.  Its accuracy is an
    information ceiling for the structured target, not a deployable method.
    """
    if temperature <= 0.0:
        raise ValueError("relation oracle temperature must be positive")
    targets = np.asarray(arrays["relation_targets"], dtype=np.float64)
    masks = np.asarray(arrays["relation_mask"], dtype=np.float64)
    desired = np.asarray(arrays["relation_desired"], dtype=np.float64)
    penalties = np.asarray(
        arrays["no_execution_penalties"], dtype=np.float64,
    )
    if targets.shape != masks.shape or targets.shape != desired.shape:
        raise ValueError("structured relation target tensors must have equal shape")
    if targets.ndim != 3 or penalties.shape != targets.shape[:2]:
        raise ValueError("structured relation oracle received incompatible shapes")
    denominators = masks.sum(axis=2)
    if np.any(denominators <= 0.0):
        raise ValueError("every candidate needs at least one relation query")
    mismatch = (
        np.abs(targets - desired) * masks
    ).sum(axis=2) / denominators
    centre = mismatch.mean(axis=1, keepdims=True)
    # Match OutcomeScorer's torch.std default (sample standard deviation), so
    # the diagnostic uses the same future/penalty scale as E.
    spread = mismatch.std(axis=1, keepdims=True, ddof=1)
    standardized = np.divide(
        mismatch - centre, spread,
        out=np.zeros_like(mismatch), where=spread > 0.0,
    )
    energy = float(future_weight) * standardized + penalties
    logits = -energy / float(temperature)
    logits -= logits.max(axis=1, keepdims=True)
    probabilities = np.exp(logits)
    probabilities /= probabilities.sum(axis=1, keepdims=True)
    return probabilities.astype(np.float32)


def structured_relation_target_only_diagnostics(
    arrays: Mapping[str, np.ndarray],
) -> dict[str, Any]:
    """Measure what the relation target identifies before energy assembly.

    This diagnostic ranks candidates only by their raw masked relation
    mismatch. It reports the entire minimum set instead of letting numpy's
    first-index tie break look like information supplied by the target.
    Penalties, standardization and executor legality never affect the ranking.
    """
    targets = np.asarray(arrays["relation_targets"], dtype=np.float64)
    masks = np.asarray(arrays["relation_mask"], dtype=np.float64)
    desired = np.asarray(arrays["relation_desired"], dtype=np.float64)
    reference = np.asarray(arrays["y"], dtype=np.int64)
    if targets.shape != masks.shape or targets.shape != desired.shape:
        raise ValueError("structured relation target tensors must have equal shape")
    if targets.ndim != 3 or len(reference) != targets.shape[0]:
        raise ValueError(
            "structured relation target-only diagnostic received incompatible shapes"
        )
    denominators = masks.sum(axis=2)
    if np.any(denominators <= 0.0):
        raise ValueError("every candidate needs at least one relation query")
    mismatch = (
        np.abs(targets - desired) * masks
    ).sum(axis=2) / denominators
    minima = mismatch.min(axis=1, keepdims=True)
    minimum_set = np.isclose(mismatch, minima, rtol=1e-9, atol=1e-12)
    tie_size = minimum_set.sum(axis=1)
    rows = np.arange(len(reference))
    reference_is_minimum = minimum_set[rows, reference]
    expected_correct = reference_is_minimum / tie_size
    ambiguous = np.asarray(
        arrays.get("ambiguous", np.zeros(len(reference), dtype=bool)),
        dtype=bool,
    )

    def summarize(row_mask: np.ndarray) -> dict[str, Any] | None:
        if not row_mask.any():
            return None
        return {
            "rows": int(row_mask.sum()),
            "reference_in_minimum_set_rate": float(
                reference_is_minimum[row_mask].mean()
            ),
            "unique_reference_minimum_rate": float((
                reference_is_minimum[row_mask] & (tie_size[row_mask] == 1)
            ).mean()),
            "uniform_tie_break_expected_accuracy": float(
                expected_correct[row_mask].mean()
            ),
            "mean_minimum_set_size": float(tie_size[row_mask].mean()),
            "maximum_minimum_set_size": int(tie_size[row_mask].max()),
        }

    all_rows = np.ones(len(reference), dtype=bool)
    return {
        "ranking": "raw_masked_relation_mismatch_only",
        "uses_penalties": False,
        "uses_standardization": False,
        "uses_executor_legality_for_selection": False,
        "all": summarize(all_rows),
        "identifiable": summarize(~ambiguous),
        "ambiguous": summarize(ambiguous),
    }


def calibrate_shared_commit_rule(
    probabilities_by_run: Mapping[str, np.ndarray],
    arrays: Mapping[str, np.ndarray], hard_config: Mapping[str, Any],
) -> dict[str, Any]:
    """Select one A-E commit rule on the sealed validation-calibration half.

    The score is computed on independent one-step post-world outcomes from
    online rows only, so the grid does not require hundreds of expensive causal
    replays. Recovery-only training examples are excluded. Every model and seed
    contributes equally, and the report half is never inspected.
    """
    if not probabilities_by_run:
        raise ValueError("commit calibration requires model probabilities")
    group_calibration = np.asarray(arrays["calibration"], dtype=bool)
    recovery = np.asarray(
        arrays.get("recovery", np.zeros(len(group_calibration), dtype=bool)),
        dtype=bool,
    )
    calibration = group_calibration & ~recovery
    report = ~group_calibration & ~recovery
    if not calibration.any() or not report.any():
        raise ValueError("validation must contain both calibration and report groups")
    candidate_legal = np.asarray(arrays["candidate_legal"], dtype=bool)
    active_correct = np.asarray(arrays["active_correct"], dtype=np.float64)
    base_active = np.asarray(arrays["base_active_correct"], dtype=np.float64)
    fact_errors = np.asarray(arrays["fact_errors"], dtype=np.float64)
    base_fact = np.asarray(arrays["base_fact_errors"], dtype=np.float64)
    excess_nodes = np.asarray(arrays["excess_nodes"], dtype=np.float64)
    base_excess = np.asarray(arrays["base_excess_nodes"], dtype=np.float64)
    spec = hard_config["training"]["commit_calibration"]
    trials = []
    rows = np.arange(len(calibration))
    for commit_probability in spec["commit_probability_grid"]:
        for margin_threshold in spec["margin_threshold_grid"]:
            run_scores = []
            for run_name, raw_probabilities in sorted(
                probabilities_by_run.items()
            ):
                probabilities = np.asarray(raw_probabilities, dtype=np.float64)
                if probabilities.shape != candidate_legal.shape:
                    raise ValueError(
                        f"probability shape mismatch for calibration run {run_name}"
                    )
                predicted = probabilities.argmax(axis=1)
                ordered = np.sort(probabilities, axis=1)
                top = ordered[:, -1]
                margin = np.round(top - ordered[:, -2], 12)
                requested = (
                    (top >= float(commit_probability))
                    & (margin >= float(margin_threshold))
                )
                committed = requested & candidate_legal[rows, predicted]
                selected_active = active_correct[rows, predicted]
                selected_fact = fact_errors[rows, predicted]
                selected_excess = excess_nodes[rows, predicted]
                mask = calibration
                run_scores.append({
                    "active_correctness": float(np.mean(np.where(
                        committed[mask], selected_active[mask], base_active[mask],
                    ))),
                    "fact_error": float(np.mean(np.where(
                        committed[mask], selected_fact[mask], base_fact[mask],
                    ))),
                    "false_birth": float(np.mean(np.where(
                        committed[mask], selected_excess[mask], base_excess[mask],
                    ))),
                    "commit_rate": float(np.mean(committed[mask])),
                })
            aggregate = {
                key: float(np.mean([score[key] for score in run_scores]))
                for key in run_scores[0]
            }
            trials.append({
                "commit_probability": float(commit_probability),
                "margin_threshold": float(margin_threshold),
                **aggregate,
            })
    winner = max(
        trials,
        key=lambda item: (
            item["active_correctness"],
            -item["fact_error"],
            -item["false_birth"],
            item["commit_rate"],
            -item["commit_probability"],
            -item["margin_threshold"],
        ),
    )
    return {
        "partition_rule": spec["partition"],
        "calibration_rows": int(calibration.sum()),
        "report_rows": int(report.sum()),
        "excluded_recovery_training_rows": int(recovery.sum()),
        "runs": len(probabilities_by_run),
        "selection": spec["selection"],
        "selected": {
            "commit_probability": winner["commit_probability"],
            "margin_threshold": winner["margin_threshold"],
        },
        "selected_calibration_metrics": {
            key: winner[key] for key in (
                "active_correctness", "fact_error", "false_birth", "commit_rate",
            )
        },
        "trials": trials,
    }


def _teacher_forced_metrics(
    probabilities: np.ndarray, data: Mapping[str, torch.Tensor],
    teacher: torch.Tensor,
) -> dict[str, float]:
    target = data["y"].detach().cpu().numpy()
    ambiguous = data["ambiguous"].detach().cpu().numpy()
    recovery = (
        data["recovery"].detach().cpu().numpy()
        if "recovery" in data else np.zeros(len(target), dtype=bool)
    )
    online = ~recovery
    identifiable = ~ambiguous & online
    predicted = probabilities.argmax(axis=1)
    teacher_choice = teacher.argmax(dim=1).detach().cpu().numpy()
    def mean(values: np.ndarray, mask: np.ndarray) -> float:
        return float(np.mean(values[mask])) if mask.any() else 0.0
    return {
        "accuracy": mean(predicted == target, online),
        "all_learning_rows_accuracy": float(np.mean(predicted == target)),
        "ambiguous_accuracy": mean(predicted == target, ambiguous),
        "identifiable_accuracy": mean(predicted == target, identifiable),
        "recovery_accuracy": mean(predicted == target, recovery),
        "teacher_accuracy": mean(teacher_choice == target, online),
        "amortization_error": mean(predicted != teacher_choice, online),
        "mean_confidence": mean(probabilities.max(axis=1), online),
    }


def causal_rollout_metrics(
    model: OnlineModel | None, audits: Sequence[Mapping[str, Any]],
    smoke_config: Mapping[str, Any], *, oracle: bool = False,
    observable_oracle: bool = False,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    """Evaluate a method causally on its own persistent predicted graph."""
    if oracle and observable_oracle:
        raise ValueError("full and observable oracle modes are mutually exclusive")
    device = torch.device(smoke_config["device"])
    sequence_rows = []
    forward_latencies_ms = []
    ambiguity_choice_by_group: dict[str, int] = {}
    pivot_reference_hashes_by_group: dict[str, set[str]] = {}
    for audit in audits:
        pivot = int(audit["ambiguity_pivot_step"])
        stored = audit["steps"][pivot]
        reference = stored["executed_candidates"][
            stored["reference_program_index"]
        ]
        pivot_reference_hashes_by_group.setdefault(
            str(audit["paired_group_id"]), set(),
        ).add(str(reference["post_graph_hash"]))
    if any(len(hashes) != 2 for hashes in pivot_reference_hashes_by_group.values()):
        raise ValueError(
            "bounded recovery evaluation requires two distinct paired pivot states"
        )
    if observable_oracle:
        references_by_group: dict[str, set[int]] = {}
        for audit in audits:
            pivot = int(audit["ambiguity_pivot_step"])
            references_by_group.setdefault(
                str(audit["paired_group_id"]), set(),
            ).add(int(audit["steps"][pivot]["reference_program_index"]))
        for group, references in references_by_group.items():
            if len(references) != 2:
                raise ValueError(
                    "observable oracle requires exact paired ambiguity references"
                )
            # Both indistinguishable siblings receive the same deterministic
            # choice.  Independent coin flips could get both siblings right
            # and would exceed the deployable information ceiling.
            ambiguity_choice_by_group[group] = min(references)
    for audit in audits:
        current = clone_json(audit["initial_world"])
        predicted_states = []
        base_states = []
        choices = []
        references = []
        protected = []
        for step_index, stored in enumerate(audit["steps"]):
            materialized = materialize_rollout_step(audit, current, step_index)
            reference_state = stored["executed_candidates"][
                stored["reference_program_index"]
            ]["post_graph"]
            ambiguous = (
                stored["ambiguity"] == "epistemically_ambiguous_pivot"
            )
            if oracle or observable_oracle:
                if observable_oracle and ambiguous:
                    selected_index = ambiguity_choice_by_group[
                        str(audit["paired_group_id"])
                    ]
                elif observable_oracle:
                    scored = []
                    for candidate in materialized["executed_candidates"]:
                        predicted = (
                            candidate["post_graph"]
                            if candidate["legal"] else current
                        )
                        errors = graph_error_counts(
                            predicted, reference_state, current,
                            [stored["event_spec"]["protected_id"]],
                        )
                        scored.append((
                            -errors["active_graph_correct"],
                            -errors["open_memory_correct"],
                            errors["memory_contamination"]
                            + errors["missing_open_facts"],
                            errors["false_birth_growth"],
                            not candidate["legal"],
                            int(candidate["candidate_index"]),
                        ))
                    selected_index = int(min(scored)[-1])
                else:
                    selected_index = int(stored["reference_program_index"])
                probabilities = np.eye(
                    len(materialized["executed_candidates"]), dtype=np.float32,
                )[selected_index]
            else:
                vector = online_feature_vector(materialized["online"])
                started = time.perf_counter()
                with torch.no_grad():
                    probabilities = model(
                        torch.as_tensor(vector[None], device=device)
                    ).softmax(dim=1).cpu().numpy()[0]
                forward_latencies_ms.append((time.perf_counter() - started) * 1000.0)
                selected_index = int(np.argmax(probabilities))
            selected = materialized["executed_candidates"][selected_index]
            decision = decide_commit(
                {str(index): float(value) for index, value in enumerate(probabilities)},
                decision_id=f"{audit['sequence_id']}:{step_index}",
                at=int(stored["event_spec"]["decision_time"]),
                commit_probability=float(smoke_config["commit_probability"]),
                margin_threshold=float(smoke_config["margin_threshold"]),
            )
            base = current
            committed = decision["action"] == "COMMIT" and selected["legal"]
            current = selected["post_graph"] if committed else clone_json(base)
            predicted_states.append(current)
            base_states.append(base)
            reference = reference_state
            references.append(reference)
            protected.append([stored["event_spec"]["protected_id"]])
            match = materialized["online"]["current_regions"][0][
                "appearance_match"
            ]
            revisit_opportunity = (
                "delayed_contradiction_revisit"
                in materialized["online"]["action_history"]
            )
            revisit_triggered = bool(
                revisit_opportunity
                and match["best_match_recorded_elsewhere"] > 0.5
                and materialized["online"]["current_regions"][0]["reliability"]
                > 0.0
            )
            active_correct_after = graph_error_counts(
                current, reference, base,
                [stored["event_spec"]["protected_id"]],
            )["active_graph_correct"]
            registered_correct = (
                selected_index == int(stored["reference_program_index"])
            )
            choices.append({
                "step_index": step_index,
                "scenario_family": stored["scenario_family"],
                "ambiguity": stored["ambiguity"],
                "reference_index": int(stored["reference_program_index"]),
                "selected_index": selected_index,
                "selected_template": selected["template"],
                "selected_legal": selected["legal"],
                "committed": committed,
                "registered_selection_correct": registered_correct,
                "committed_registered_correct": committed and registered_correct,
                "revisit_opportunity": revisit_opportunity,
                "revisit_triggered": revisit_triggered,
                "active_correct_after": active_correct_after,
                "probabilities": probabilities.tolist(),
                "base_graph_hash": base["graph_hash"],
                "post_graph_hash": current["graph_hash"],
            })
        metrics = rollout_graph_metrics(
            predicted_states, references, base_states, protected, horizon=20,
        )
        pivot_step = int(audit["ambiguity_pivot_step"])
        revisit_step = int(audit["recovery_revisit_step"])
        pivot_choice = choices[pivot_step]
        revisit_choice = choices[revisit_step]
        reference_pivot_hash = str(
            audit["steps"][pivot_step]["executed_candidates"][
                audit["steps"][pivot_step]["reference_program_index"]
            ]["post_graph_hash"]
        )
        covered_wrong_hashes = (
            pivot_reference_hashes_by_group[str(audit["paired_group_id"])]
            - {reference_pivot_hash}
        )
        pivot_error = pivot_choice["active_correct_after"] == 0.0
        bounded_pivot_error = bool(
            pivot_error
            and str(pivot_choice["post_graph_hash"]) in covered_wrong_hashes
        )
        designed_triggered = bool(
            bounded_pivot_error and revisit_choice["revisit_triggered"]
        )
        designed_success = bool(
            designed_triggered
            and revisit_choice["active_correct_after"] == 1.0
        )
        metrics.update({
            "paired_group_id": audit["paired_group_id"],
            "sequence_id": audit["sequence_id"],
            "sibling_index": audit["sibling_index"],
            "commit_rate": float(np.mean([item["committed"] for item in choices])),
            "raw_invalid_selection_rate": float(np.mean([
                not item["selected_legal"] for item in choices
            ])),
            "registered_selection_accuracy": float(np.mean([
                item["registered_selection_correct"] for item in choices
            ])),
            "committed_registered_accuracy": (
                float(np.mean([
                    item["registered_selection_correct"]
                    for item in choices if item["committed"]
                ])) if any(item["committed"] for item in choices) else 0.0
            ),
            "ambiguity_commit_rate": float(np.mean([
                item["committed"] for item in choices
                if item["ambiguity"] == "epistemically_ambiguous_pivot"
            ])),
            "identifiable_commit_rate": float(np.mean([
                item["committed"] for item in choices
                if item["ambiguity"] != "epistemically_ambiguous_pivot"
            ])),
            "first_registered_selection_error_step": float(next(
                (
                    item["step_index"] for item in choices
                    if not item["registered_selection_correct"]
                ),
                -1,
            )),
            "triggered_revisit_count": float(sum(
                item["revisit_triggered"] for item in choices
            )),
            "triggered_revisit_commit_rate": (
                float(np.mean([
                    item["committed"] for item in choices
                    if item["revisit_triggered"]
                ])) if any(item["revisit_triggered"] for item in choices)
                else 0.0
            ),
            "triggered_revisit_active_resolution_rate": (
                float(np.mean([
                    item["active_correct_after"] for item in choices
                    if item["revisit_triggered"]
                ])) if any(item["revisit_triggered"] for item in choices)
                else 0.0
            ),
            "designed_pivot_error": float(pivot_error),
            "designed_bounded_pivot_error": float(bounded_pivot_error),
            "designed_pivot_error_out_of_scope": float(
                pivot_error and not bounded_pivot_error
            ),
            "designed_revisit_triggered": float(designed_triggered),
            "designed_recovery_success": float(designed_success),
            "designed_recovery_time": (
                float(revisit_step - pivot_step) if designed_success else -1.0
            ),
        })
        sequence_rows.append({"metrics": metrics, "choices": choices})
    metric_names = (
        "mean_active_graph_correctness", "final_active_graph_correctness",
        "mean_open_memory_correctness", "final_open_memory_correctness",
        "mean_history_exactness", "final_history_exactness",
        "mean_post_graph_correctness", "final_post_graph_correctness",
        "memory_contamination_per_100", "missing_open_facts_per_100",
        "false_birth_growth_per_100", "collateral_violation_per_100",
        "mean_memory_contamination",
        "memory_contamination_auc_per_100_decisions",
        "unresolved_active_error", "commit_rate", "raw_invalid_selection_rate",
        "registered_selection_accuracy", "committed_registered_accuracy",
        "ambiguity_commit_rate", "identifiable_commit_rate",
        "triggered_revisit_count", "triggered_revisit_commit_rate",
        "triggered_revisit_active_resolution_rate",
        "designed_pivot_error", "designed_bounded_pivot_error",
        "designed_pivot_error_out_of_scope", "designed_revisit_triggered",
        "designed_recovery_success",
    )
    aggregate = {
        name: float(np.mean([row["metrics"][name] for row in sequence_rows]))
        for name in metric_names
    }
    aggregate["sequences"] = float(len(sequence_rows))
    aggregate["commit_probability"] = float(smoke_config["commit_probability"])
    aggregate["margin_threshold"] = float(smoke_config["margin_threshold"])
    generic_eligible = [
        row["metrics"] for row in sequence_rows
        if row["metrics"]["any_first_error_recovery_eligible"] > 0.0
    ]
    aggregate["any_first_error_recovery_eligible_sequences"] = float(
        len(generic_eligible)
    )
    aggregate["any_first_error_recovery_rate_within_window"] = (
        float(np.mean([
            row["any_first_error_recovered_within_window"]
            for row in generic_eligible
        ])) if generic_eligible else 0.0
    )
    designed_eligible = [
        row["metrics"] for row in sequence_rows
        if row["metrics"]["designed_bounded_pivot_error"] > 0.0
    ]
    aggregate["designed_recovery_eligible_sequences"] = float(
        len(designed_eligible)
    )
    aggregate["designed_recovery_trigger_rate"] = (
        float(np.mean([
            row["designed_revisit_triggered"] for row in designed_eligible
        ])) if designed_eligible else 0.0
    )
    aggregate["designed_recovery_rate_within_window"] = (
        float(np.mean([
            row["designed_recovery_success"] for row in designed_eligible
        ])) if designed_eligible else 0.0
    )
    # Registered name now refers specifically to the bounded pivot recovery;
    # the arbitrary first-error diagnostic remains separately available.
    aggregate["recovery_eligible_sequences"] = aggregate[
        "designed_recovery_eligible_sequences"
    ]
    aggregate["recovery_rate_within_window"] = aggregate[
        "designed_recovery_rate_within_window"
    ]
    triggered_choices = [
        choice
        for row in sequence_rows
        for choice in row["choices"]
        if choice["revisit_triggered"]
    ]
    # These are conditional rates. Sequences with no relevant contradiction
    # are not failed recovery attempts and therefore cannot dilute them.
    aggregate["triggered_revisit_count"] = float(len(triggered_choices))
    aggregate["triggered_revisit_commit_rate"] = (
        float(np.mean([choice["committed"] for choice in triggered_choices]))
        if triggered_choices else 0.0
    )
    aggregate["triggered_revisit_active_resolution_rate"] = (
        float(np.mean([
            choice["active_correct_after"] for choice in triggered_choices
        ])) if triggered_choices else 0.0
    )
    generic_recovered = [
        row["any_first_error_time_to_recovery"] for row in generic_eligible
        if row["any_first_error_time_to_recovery"] >= 0.0
    ]
    aggregate["any_first_error_mean_time_to_recovery"] = (
        float(np.mean(generic_recovered)) if generic_recovered else -1.0
    )
    designed_recovered = [
        row["designed_recovery_time"] for row in designed_eligible
        if row["designed_recovery_time"] >= 0.0
    ]
    aggregate["mean_time_to_first_recovery"] = (
        float(np.mean(designed_recovered)) if designed_recovered else -1.0
    )
    aggregate["p95_forward_latency_ms"] = (
        float(np.quantile(forward_latencies_ms, 0.95))
        if forward_latencies_ms else 0.0
    )
    return aggregate, sequence_rows


def run_af_seed(
    train_np: Mapping[str, np.ndarray], validation_np: Mapping[str, np.ndarray],
    validation_audits: Sequence[Mapping[str, Any]],
    smoke_config: Mapping[str, Any], seed: int,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, torch.nn.Module]]:
    """Train A-E with matched students and evaluate A-F on causal rollout."""
    device = torch.device(smoke_config["device"])
    train = tensors(dict(train_np), device)
    validation = tensors(dict(validation_np), device)
    scorer, learned_teachers, scorer_trace = train_outcome_scorer(
        train, validation, dict(smoke_config), seed, device,
    )
    scorer_parameters = sum(parameter.numel() for parameter in scorer.parameters())
    results: dict[str, Any] = {}
    details: dict[str, Any] = {"outcome_scorer_training": scorer_trace}
    models: dict[str, torch.nn.Module] = {
        "future_no_execution_scorer": scorer,
    }
    for method in METHODS:
        if method == "oracle_candidate_program":
            candidate_count = int(validation["penalties"].shape[1])
            probabilities = np.eye(candidate_count, dtype=np.float32)[
                validation["y"].detach().cpu().numpy()
            ]
            teacher = F.one_hot(validation["y"], candidate_count).float()
            teacher_metrics = _teacher_forced_metrics(probabilities, validation, teacher)
            causal, causal_rows = causal_rollout_metrics(
                None, validation_audits, smoke_config, oracle=True,
            )
            results[method] = {
                "teacher_forced": teacher_metrics,
                "selection_error": selection_error_decomposition(
                    probabilities, validation_np),
                "causal_rollout": causal,
                "student_parameters": 0,
                "additional_scorer_parameters": 0,
                "student_seconds": 0.0,
                "oracle_upper_bound": True,
            }
            details[method] = {"training_trace": [], "causal_sequences": causal_rows}
            continue
        if method == "future_no_execution":
            train_teacher = learned_teachers["train"]
            validation_teacher = learned_teachers["validation"]
        elif method == "execute_current_only":
            train_teacher = train["pstar_current"]
            validation_teacher = validation["pstar_current"]
        else:
            train_teacher = train["pstar"]
            validation_teacher = validation["pstar"]
        started = time.perf_counter()
        model, trace = train_student(
            method, train, train_teacher, dict(smoke_config), seed, device,
        )
        seconds = time.perf_counter() - started
        with torch.no_grad():
            probabilities = model(validation["x"]).softmax(dim=1).cpu().numpy()
        teacher_metrics = _teacher_forced_metrics(
            probabilities, validation, validation_teacher,
        )
        causal, causal_rows = causal_rollout_metrics(
            model, validation_audits, smoke_config,
        )
        results[method] = {
            "teacher_forced": teacher_metrics,
            "selection_error": selection_error_decomposition(
                probabilities, validation_np),
            "causal_rollout": causal,
            "student_parameters": sum(
                parameter.numel() for parameter in model.parameters()
            ),
            "additional_scorer_parameters": (
                scorer_parameters if method == "future_no_execution" else 0
            ),
            "student_seconds": seconds,
            "oracle_upper_bound": False,
        }
        details[method] = {
            "training_trace": trace,
            "causal_sequences": causal_rows,
        }
        models[method] = model
    parameter_counts = {
        results[method]["student_parameters"]
        for method in METHODS if method != "oracle_candidate_program"
    }
    if len(parameter_counts) != 1:
        raise AssertionError("A-E must use the same student parameter count")
    return results, details, models
