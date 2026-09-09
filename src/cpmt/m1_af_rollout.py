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
from typing import Any, Callable, Mapping, Sequence

import numpy as np
import torch
from torch.nn import functional as F

from .dev_learning import (
    METHODS,
    OnlineModel,
    apply_candidate_admissibility_to_probabilities,
    candidate_admissibility_mask,
    masked_candidate_probabilities,
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
    _collateral_mutation,
    _current_online_evidence_scope,
    candidate_argument_ids,
    generate_m1_paired_rollout_split,
    materialize_rollout_step,
    stable_retrieval_feature,
)
from .m1_protocol import validate_m1_protocol, validate_rollout_source
from .pending import decide_commit
from .m1_candidate_policy import validate_candidate_policy, step_availability, summarize_availability


NODE_TYPES = ("entity", "surface", "place", "chart", "region")
LIFECYCLES = ("candidate", "confirmed", "dormant", "retracted", "alias")
TEMPLATES = (
    "NOOP", "BIND", "BIRTH", "REACTIVATE", "RELINK", "RETRACT",
    "SPLIT", "MERGE", "REPLACE",
)
CANDIDATE_FAILURE_TYPES = (
    "NONE",
    "ContractError",
    "VersionMismatchError",
    "DuplicateTransactionError",
    "PreconditionError",
    "ProtectedMutationError",
    "UnsupportedTemplateError",
    "InvariantViolation",
)
CANDIDATE_FAILURE_TYPE_TO_CODE = {
    name: index for index, name in enumerate(CANDIDATE_FAILURE_TYPES)
}
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
CURRENT_RELATION_QUERIES = (
    "candidate_action_supported_by_current_evidence",
    "candidate_required_arguments_match_current_query",
    "current_region_is_reliably_empty",
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
    architecture = str(config.get(
        "architecture", "shared_candidate_mlp_v1",
    ))
    architecture_contract = hard_config["architecture_evaluation"]
    if architecture not in architecture_contract["registered"]:
        raise ValueError(f"unregistered M1 architecture {architecture!r}")
    architecture_spec = architecture_contract[architecture]
    config["architecture"] = architecture
    if architecture == "cross_candidate_set_transformer_v1":
        config["hidden_dim"] = int(architecture_spec["model_dim"])
        config["attention_heads"] = int(
            architecture_spec["attention_heads"]
        )
        config["set_attention_blocks"] = int(
            architecture_spec["set_attention_blocks"]
        )
        config["feedforward_dim"] = int(
            architecture_spec["feedforward_dim"]
        )
        config["architecture_dropout"] = float(
            architecture_spec["dropout"]
        )
    else:
        config["hidden_dim"] = int(architecture_spec["hidden_dim"])
    config["candidate_feature_dim"] = CANDIDATE_FEATURE_DIM
    config["current_relation_dim"] = len(CURRENT_RELATION_QUERIES)
    config["standardize_future_term"] = True
    config["horizon"] = int(hard_config["future"]["primary_horizon"])
    config["temperature"] = float(hard_config["energy"]["temperature"])
    config["energy_weights"] = deepcopy(hard_config["energy"]["weights"])
    config["mechanism_diagnostic_slices"] = deepcopy(
        hard_config["evaluation"]["mechanism_diagnostic_slices"]
    )
    config["current_evidence_scope_ranks"] = int(
        hard_config["candidates"]["proposal_retrieval"]["enumerated_ranks"]
    )
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


def training_inner_dev_mask(
    arrays: Mapping[str, np.ndarray],
) -> np.ndarray:
    """Hold out a stable fifth of train groups for development diagnostics.

    The canonical procedural paired-group name is reconstructed from the
    stored group index and hashed. Every row in a sibling pair, including its
    recovery examples, receives the same assignment. Validation is never read.
    """
    groups = np.asarray(arrays["group"], dtype=np.int64)
    if groups.ndim != 1 or len(groups) == 0:
        raise ValueError("train inner-dev partition requires a nonempty group vector")
    assignments = {}
    for group in np.unique(groups):
        paired_group_id = f"rollout-pair:train:{int(group):06d}"
        digest = hashlib.sha256(paired_group_id.encode("utf-8")).digest()
        assignments[int(group)] = int.from_bytes(digest[:8], "big") % 5 == 0
    mask = np.asarray([assignments[int(group)] for group in groups], dtype=bool)
    if not mask.any() or mask.all():
        raise ValueError(
            "train inner-dev hash partition needs both fitting and held-out groups"
        )
    return mask


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


def candidate_current_relation_targets(
    program: Mapping[str, Any], online: Mapping[str, Any],
    policy: Mapping[str, float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build current-evidence queries without executing the candidate.

    Targets come only from the immutable online payload.  Desired values encode
    what the program would need to be consistent with that evidence, so the
    scorer can amortize a now term without receiving a post-world or legality
    label.
    """
    region = online["current_regions"][0]
    actionable = bool(
        region["visibility"] in {"visible", "visible_empty"}
        and region["pose_valid"]
        and region["depth_valid"]
        and float(region["reliability"]) > 0.0
    )
    reliably_empty = bool(actionable and region["visibility"] == "visible_empty")
    label = _program_label(program)
    identifiers = candidate_argument_ids(program)
    queries = online["proposal_observation"]
    vectors = [
        np.asarray(stable_retrieval_feature(identifier), dtype=np.float64)
        for identifier in identifiers
    ]

    def query_matches(query: Sequence[float]) -> bool:
        target = np.asarray(query, dtype=np.float64)
        return bool(vectors) and max(
            float(np.dot(vector, target)) for vector in vectors
        ) >= float(policy["argument_cosine_minimum"])

    node_matches = query_matches(queries["node_query"])
    edge_matches = query_matches(queries["edge_query"])
    place_matches = query_matches(queries["place_query"])
    merge_matches = all(
        query_matches(query) for query in queries["merge_queries"]
    )
    required_arguments_match = {
        "NOOP": True,
        "BIND": node_matches,
        "BIRTH": True,
        "REACTIVATE": node_matches,
        "RELINK": edge_matches and place_matches,
        "RETRACT": edge_matches,
        "SPLIT": node_matches,
        "MERGE": merge_matches,
        "REPLACE": place_matches,
    }[label]
    match = region["appearance_match"]
    best = float(match["best"])
    second = float(match["second"])
    recorded_here = bool(match["best_match_recorded_here"])
    recorded_elsewhere = bool(match["best_match_recorded_elsewhere"])
    place_occupied = bool(match["place_has_recorded_entity"])
    novel = bool(region["evidence_novel"])
    action_supported = {
        "NOOP": not novel and recorded_here,
        "BIND": novel and recorded_here and node_matches,
        "BIRTH": (
            novel and best < float(policy["novel_entity_best_maximum"])
            and float(match["best_dormant"])
            < float(policy["dormant_match_minimum"])
            and not place_occupied
        ),
        "REACTIVATE": (
            novel and float(match["best_dormant"])
            >= float(policy["dormant_match_minimum"]) and node_matches
        ),
        "RELINK": novel and recorded_elsewhere and required_arguments_match,
        "RETRACT": reliably_empty and edge_matches,
        "SPLIT": (
            novel and not place_occupied
            and float(policy["split_best_minimum"]) <= best
            < float(policy["split_best_maximum"])
            and node_matches
        ),
        "MERGE": (
            novel and not place_occupied
            and best >= float(policy["merge_best_minimum"])
            and second >= float(policy["merge_second_minimum"])
            and merge_matches
        ),
        "REPLACE": (
            novel and place_occupied
            and best < float(policy["novel_entity_best_maximum"])
            and place_matches
        ),
    }[label]
    targets = np.asarray([
        float(action_supported), float(required_arguments_match),
        float(reliably_empty),
    ], dtype=np.float32)
    masks = np.asarray([
        float(actionable),
        float(actionable and label not in {"NOOP", "BIRTH"}),
        float(actionable),
    ], dtype=np.float32)
    desired = np.asarray([
        1.0,
        1.0,
        float(label == "RETRACT"),
    ], dtype=np.float32)
    return targets, masks, desired


def _candidate_failure_code(
    candidate: Mapping[str, Any], key: str,
) -> int:
    failure = candidate.get(key)
    name = "NONE" if failure is None else str(failure.get("type"))
    if name not in CANDIDATE_FAILURE_TYPE_TO_CODE:
        raise ValueError(f"unregistered candidate failure type {name!r}")
    return CANDIDATE_FAILURE_TYPE_TO_CODE[name]


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
        "current_relation_target_dim": len(CURRENT_RELATION_QUERIES),
        "future_relation_target_dim": (
            int(arrays["relation_targets"].shape[2])
            - len(CURRENT_RELATION_QUERIES)
        ),
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
    for audit in audits:
        validate_rollout_source(audit, hard_config)
    rows = []
    group_ids = {
        name: index for index, name in enumerate(sorted({
            audit["paired_group_id"] for audit in audits
        }))
    }
    weights = hard_config["energy"]["weights"]
    scenario_family_index = {
        family: index
        for index, family in enumerate(hard_config["data"]["scenario_families"])
    }
    temperature = float(hard_config["energy"]["temperature"])
    horizon = int(hard_config["future"]["primary_horizon"])
    representation = str(hard_config["future"]["target_representation"])
    for audit in audits:
        learning_steps = list(enumerate(audit["steps"])) + [
            (int(step["source_step_index"]), step)
            for step in audit.get("recovery_examples", [])
        ]
        for step_index, step in learning_steps:
            future_states = [
                audit["steps"][target_index]["executed_candidates"][
                    audit["steps"][target_index]["reference_program_index"]
                ]["post_graph"]
                for target_index in range(
                    step_index + 1,
                    min(len(audit["steps"]), step_index + 1 + horizon),
                )
            ]
            # The final online decision remains in the audit/causal sequence,
            # but with no later observation it cannot train a hindsight term.
            if not future_states:
                continue
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
                no_execution_penalties.append(
                    float(weights["edit"])
                    * float(program.get("declared_edit_cost", 0.0))
                    + float(weights["growth"])
                    * float(program.get("declared_growth_cost", 0.0))
                )
            relation_rows = [
                tuple(np.concatenate((current, future)).astype(np.float32)
                      for current, future in zip(
                          candidate_current_relation_targets(
                              program, step["online"],
                              hard_config["future"][
                                  "no_execution_now_target_policy"
                              ],
                          ),
                          candidate_future_relation_targets(
                              program, base, future_states, horizon=horizon,
                          ),
                          strict=True,
                      ))
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
                "teacher_matches_reference": bool(
                    step["teacher_winner_matches_reference"]
                ),
                "scenario_family_index": int(scenario_family_index.get(
                    str(step["scenario_family"]), -1,
                )),
                "candidate_energy_now": np.asarray([
                    energy["now"] for energy in step["candidate_energies"]
                ], dtype=np.float32),
                "candidate_energy_future": np.asarray([
                    energy["future"] for energy in step["candidate_energies"]
                ], dtype=np.float32),
                "candidate_energy_edit": np.asarray([
                    energy["edit"] for energy in step["candidate_energies"]
                ], dtype=np.float32),
                "candidate_energy_growth": np.asarray([
                    energy["growth"] for energy in step["candidate_energies"]
                ], dtype=np.float32),
                "candidate_energy_collateral": np.asarray([
                    energy["collateral"]
                    for energy in step["candidate_energies"]
                ], dtype=np.float32),
                "candidate_energy_illegal": np.asarray([
                    energy["illegal"] for energy in step["candidate_energies"]
                ], dtype=np.float32),
                "candidate_energy_now_raw": np.asarray([
                    np.nan if energy["now_raw"] is None else energy["now_raw"]
                    for energy in step["candidate_energies"]
                ], dtype=np.float32),
                "candidate_energy_now_natural_range": np.asarray([
                    energy["now_natural_range"]
                    for energy in step["candidate_energies"]
                ], dtype=np.float32),
                "candidate_energy_future_raw": np.asarray([
                    np.nan if energy["future_raw"] is None else energy["future_raw"]
                    for energy in step["candidate_energies"]
                ], dtype=np.float32),
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
                "candidate_static_preflight_pass": np.asarray([
                    candidate["static_preflight_pass"]
                    for candidate in step["executed_candidates"]
                ], dtype=bool),
                "candidate_execution_failure_code": np.asarray([
                    _candidate_failure_code(candidate, "failure")
                    for candidate in step["executed_candidates"]
                ], dtype=np.int64),
                "candidate_static_preflight_failure_code": np.asarray([
                    _candidate_failure_code(
                        candidate, "static_preflight_failure",
                    )
                    for candidate in step["executed_candidates"]
                ], dtype=np.int64),
                "active_correct": np.asarray([
                    item["active_graph_correct"] for item in candidate_metrics
                ], dtype=np.float32),
                "base_active_correct": float(
                    base_metrics["active_graph_correct"]
                ),
                "fact_errors": np.asarray([
                    item["extra_open_fact_error"]
                    + item["missing_open_fact_error"]
                    for item in candidate_metrics
                ], dtype=np.float32),
                "base_fact_errors": float(
                    base_metrics["extra_open_fact_error"]
                    + base_metrics["missing_open_fact_error"]
                ),
                "excess_nodes": np.asarray([
                    # Preserve the v8 train-array digest.  This legacy field
                    # was used only by the now-superseded one-step gate audit;
                    # D-045 formal causal reports recompute false births from
                    # entity-ID set difference in ``graph_error_counts``.
                    max(
                        0.0,
                        item["false_birth_growth"]
                        - item["missing_open_entities"],
                    )
                    for item in candidate_metrics
                ], dtype=np.float32),
                "base_excess_nodes": float(max(
                    0.0,
                    base_metrics["false_birth_growth"]
                    - base_metrics["missing_open_entities"],
                )),
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
    static_preflight_pass = np.asarray(
        arrays.get(
            "candidate_static_preflight_pass",
            np.ones_like(probabilities, dtype=bool),
        ),
        dtype=bool,
    )
    if static_preflight_pass.shape != np.asarray(probabilities).shape:
        raise ValueError(
            "candidate preflight mask and probabilities must have equal shape"
        )
    raw_static_rejected = ~static_preflight_pass[rows, predicted]
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
        "raw_static_rejected_selection_rate": mean(
            raw_static_rejected, online_chain,
        ),
        "mean_effective_candidate_count": mean(
            static_preflight_pass.sum(axis=1), online_chain,
        ),
        "illegal_wrong_template_rate": (
            mean(raw_illegal & ~template_correct, online_chain)
            if raw_illegal is not None else None
        ),
        "legal_wrong_template_rate": (
            mean(~raw_illegal & ~template_correct, online_chain)
            if raw_illegal is not None else None
        ),
        "ambiguous_pair_containment": mean(pair_contains, ambiguous),
        "ambiguous_paired_groups": ambiguous_groups,
        "ambiguous_fraction": mean(ambiguous, online_chain),
        "recovery_fraction": mean(recovery),
    }


def uniform_admissible_random_accuracy(
    static_preflight_pass: np.ndarray, *,
    row_mask: np.ndarray | None = None,
) -> float:
    """Expected accuracy when sampling uniformly from each row's admitted set."""
    admitted = np.asarray(static_preflight_pass, dtype=bool)
    if admitted.ndim != 2:
        raise ValueError("static preflight mask must be row by candidate")
    counts = admitted.sum(axis=1)
    if np.any(counts <= 0):
        raise ValueError("static preflight rejected every candidate in a row")
    if row_mask is None:
        selected = np.ones(len(admitted), dtype=bool)
    else:
        selected = np.asarray(row_mask, dtype=bool)
        if selected.ndim != 1 or len(selected) != len(admitted):
            raise ValueError("random-floor row mask has the wrong shape")
    if not selected.any():
        raise ValueError("random-floor row mask is empty")
    return float(np.mean(1.0 / counts[selected]))


def structured_relation_oracle_probabilities(
    arrays: Mapping[str, np.ndarray], *, future_weight: float,
    temperature: float,
    static_preflight_pass: np.ndarray | None = None,
    now_weight: float = 1.0, current_relation_dim: int = 0,
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
    if not 0 <= int(current_relation_dim) <= targets.shape[2]:
        raise ValueError("current relation dimension is out of range")
    denominators = masks.sum(axis=2)
    if np.any(denominators <= 0.0):
        raise ValueError("every candidate needs at least one relation query")
    available = np.ones_like(penalties, dtype=bool)
    if static_preflight_pass is not None:
        available = np.asarray(static_preflight_pass, dtype=bool)
        if available.shape != penalties.shape:
            raise ValueError(
                "static preflight mask and candidate energy must have equal shape"
            )
        if np.any(~available.any(axis=1)):
            raise ValueError("static preflight rejected every candidate in a row")

    def relation_mismatch(start: int, stop: int) -> np.ndarray:
        selected_mask = masks[:, :, start:stop]
        selected_error = np.abs(
            targets[:, :, start:stop] - desired[:, :, start:stop]
        ) * selected_mask
        selected_denominator = selected_mask.sum(axis=2)
        return np.divide(
            selected_error.sum(axis=2), selected_denominator,
            out=np.zeros_like(selected_denominator),
            where=selected_denominator > 0.0,
        )

    def masked_standardize(values: np.ndarray) -> np.ndarray:
        active = available.astype(np.float64)
        counts = active.sum(axis=1, keepdims=True)
        centre = (values * active).sum(axis=1, keepdims=True) / counts
        variance = (((values - centre) ** 2) * active).sum(
            axis=1, keepdims=True,
        ) / counts
        spread = np.sqrt(variance)
        standardized = np.divide(
            values - centre, spread,
            out=np.zeros_like(values), where=spread > 0.0,
        )
        return np.where(available, standardized, 0.0)

    current_mismatch = relation_mismatch(0, int(current_relation_dim))
    future_mismatch = relation_mismatch(
        int(current_relation_dim), targets.shape[2],
    )
    # Current relation mismatch is already an absolute error between binary
    # probabilities/targets, hence it has the fixed natural range [0, 1].
    # Candidate-spread z-scoring would amplify nearly tied rows. Future query
    # counts still need per-row standardization to match executed-future units.
    scaled_current = np.where(available, current_mismatch, 0.0)
    energy = (
        float(now_weight) * scaled_current
        + float(future_weight) * masked_standardize(future_mismatch)
        + penalties
    )
    energy = np.where(available, energy, np.inf)
    logits = -energy / float(temperature)
    logits -= logits.max(axis=1, keepdims=True)
    probabilities = np.exp(logits)
    probabilities /= probabilities.sum(axis=1, keepdims=True)
    return probabilities.astype(np.float32)


def posterior_term_influence_diagnostics(
    arrays: Mapping[str, np.ndarray], *, weights: Mapping[str, float],
    temperature: float, scenario_families: Sequence[str],
    terms: Sequence[str], total_variation_thresholds: Sequence[float],
    expected_now_activation_pattern: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Measure each executed-teacher term through the full soft posterior.

    CTL distils the complete hindsight distribution, so an energy term can
    materially change supervision without changing the winning candidate.
    This audit removes one finite term at a time and reports total variation,
    KL divergence, argmax changes, and the reference-probability shift.  It is
    diagnostic only: it neither reweights the teacher nor selects a method.
    """
    if temperature <= 0.0:
        raise ValueError("posterior influence temperature must be positive")
    reference = np.asarray(arrays["y"], dtype=np.int64)
    full = np.asarray(arrays["pstar"], dtype=np.float64)
    recovery = np.asarray(
        arrays.get("recovery", np.zeros(len(reference), dtype=bool)),
        dtype=bool,
    )
    family_indices = np.asarray(
        arrays["scenario_family_index"], dtype=np.int64,
    )
    illegal = np.asarray(
        arrays["candidate_energy_illegal"], dtype=np.float64,
    ) > 0.0
    if full.ndim != 2 or illegal.shape != full.shape:
        raise ValueError("posterior influence candidate arrays differ in shape")
    if len(reference) != len(full) or len(family_indices) != len(full):
        raise ValueError("posterior influence row arrays differ in shape")
    finite_terms = tuple(str(term) for term in terms)
    if any(term not in weights for term in finite_terms):
        raise ValueError("posterior influence requested an unweighted term")
    components = {
        term: np.asarray(
            arrays[f"candidate_energy_{term}"], dtype=np.float64,
        )
        for term in finite_terms
    }
    if any(value.shape != full.shape for value in components.values()):
        raise ValueError("posterior influence energy arrays differ in shape")
    total = np.zeros_like(full)
    for term, values in components.items():
        total += float(weights[term]) * values
    total = np.where(illegal, np.inf, total)

    def posterior(energy: np.ndarray) -> np.ndarray:
        logits = -energy / float(temperature)
        logits = np.where(np.isfinite(logits), logits, -np.inf)
        row_max = np.max(logits, axis=1, keepdims=True)
        raw = np.exp(logits - row_max)
        raw = np.where(np.isfinite(raw), raw, 0.0)
        denominator = raw.sum(axis=1, keepdims=True)
        if np.any(denominator <= 0.0):
            raise ValueError("posterior influence found a row with no legal candidate")
        return raw / denominator

    reconstructed = posterior(total)
    if not np.allclose(reconstructed, full, rtol=1e-5, atol=1e-7):
        raise ValueError("stored teacher posterior does not match energy components")
    thresholds = tuple(float(value) for value in total_variation_thresholds)
    if any(value <= 0.0 for value in thresholds):
        raise ValueError("posterior influence thresholds must be positive")
    online = ~recovery
    rows = np.arange(len(reference))

    def summarize(
        ablated: np.ndarray, row_mask: np.ndarray,
    ) -> dict[str, Any] | None:
        selected = online & row_mask
        if not selected.any():
            return None
        tv = 0.5 * np.abs(full - ablated).sum(axis=1)
        epsilon = np.finfo(np.float64).tiny
        kl = np.sum(
            full * (
                np.log(np.clip(full, epsilon, 1.0))
                - np.log(np.clip(ablated, epsilon, 1.0))
            ),
            axis=1,
        )
        reference_delta = (
            full[rows, reference] - ablated[rows, reference]
        )
        return {
            "rows": int(selected.sum()),
            "total_variation": {
                "mean": float(tv[selected].mean()),
                "median": float(np.median(tv[selected])),
                "p95": float(np.quantile(tv[selected], 0.95)),
                "maximum": float(tv[selected].max()),
                "fraction_above": {
                    format(threshold, ".6g"): float(
                        np.mean(tv[selected] > threshold)
                    )
                    for threshold in thresholds
                },
            },
            "argmax_change_rate": float(np.mean(
                full[selected].argmax(axis=1)
                != ablated[selected].argmax(axis=1)
            )),
            "mean_kl_full_to_ablated": float(kl[selected].mean()),
            "full_minus_ablated_reference_probability": {
                "mean": float(reference_delta[selected].mean()),
                "minimum": float(reference_delta[selected].min()),
                "maximum": float(reference_delta[selected].max()),
            },
        }

    result: dict[str, Any] = {
        "scope": "executed_hindsight_teacher_online_learning_rows",
        "interpretation": "posterior_distribution_not_argmax_only",
        "total_variation_thresholds": list(thresholds),
        "terms": {},
    }
    all_rows = np.ones(len(reference), dtype=bool)
    for term in finite_terms:
        ablated_energy = total.copy()
        legal = ~illegal
        ablated_energy[legal] -= (
            float(weights[term]) * components[term][legal]
        )
        ablated = posterior(ablated_energy)
        result["terms"][term] = {
            "all": summarize(ablated, all_rows),
            "by_family": {
                str(family): summarize(
                    ablated, family_indices == family_index,
                )
                for family_index, family in enumerate(scenario_families)
            },
        }
    if expected_now_activation_pattern is not None:
        if "now" not in result["terms"]:
            raise ValueError(
                "expected now activation pattern requires a now-term audit"
            )
        expected_nonzero = tuple(str(value) for value in
                                 expected_now_activation_pattern[
                                     "expected_nonzero_mean_tv_families"
                                 ])
        expected_zero = tuple(str(value) for value in
                              expected_now_activation_pattern[
                                  "expected_zero_mean_tv_families"
                              ])
        configured = tuple(str(value) for value in scenario_families)
        if (
            len(set(expected_nonzero)) != len(expected_nonzero)
            or len(set(expected_zero)) != len(expected_zero)
            or set(expected_nonzero) & set(expected_zero)
            or set(expected_nonzero) | set(expected_zero) != set(configured)
        ):
            raise ValueError(
                "expected now activation families must partition the protocol"
            )
        tolerance = float(expected_now_activation_pattern[
            "numerical_zero_tolerance"
        ])
        if tolerance < 0.0:
            raise ValueError("now activation numerical tolerance is negative")
        by_family = result["terms"]["now"]["by_family"]
        unobserved = sorted(
            family for family in configured if by_family[family] is None
        )
        observed_zero = sorted(
            family for family in configured
            if by_family[family] is not None
            and float(by_family[family]["total_variation"]["mean"])
            <= tolerance
        )
        observed_nonzero = sorted(
            family for family in configured
            if by_family[family] is not None and family not in observed_zero
        )
        unexpected_zero = sorted(set(expected_nonzero) & set(observed_zero))
        unexpected_nonzero = sorted(
            set(expected_zero) & set(observed_nonzero)
        )
        result["expected_now_activation_pattern"] = {
            "metric": "leave_now_out_posterior_mean_total_variation",
            "numerical_zero_tolerance": tolerance,
            "expected_nonzero_mean_tv_families": list(expected_nonzero),
            "expected_zero_mean_tv_families": list(expected_zero),
            "observed_nonzero_mean_tv_families": observed_nonzero,
            "observed_zero_mean_tv_families": observed_zero,
            "unobserved_families": unobserved,
            "unexpected_zero_families": unexpected_zero,
            "unexpected_nonzero_families": unexpected_nonzero,
            "matches_expected_pattern": not (
                unobserved or unexpected_zero or unexpected_nonzero
            ),
            "deviation_action": expected_now_activation_pattern[
                "deviation_action"
            ],
            "primary_gate": False,
        }
    return result


def _mechanism_slice_name(
    scenario_family: str, ambiguity: str | bool,
    slice_contract: Mapping[str, Any],
) -> str:
    """Assign one pre-registered, generator-defined diagnostic slice."""
    is_ambiguous = (
        bool(ambiguity) if isinstance(ambiguity, (bool, np.bool_))
        else str(ambiguity) == "epistemically_ambiguous_pivot"
    )
    conditions = {
        "exact_online_ambiguity": is_ambiguous,
        "temporal_underdetermination": str(scenario_family) == "C10",
        "execution_side_effect_sensitive": str(scenario_family) == "C11",
        "current_sensor_unavailable": str(scenario_family) == "C09",
        "other_registered_mechanisms": True,
    }
    for name in slice_contract["precedence"]:
        if conditions.get(str(name), False):
            return str(name)
    raise ValueError("mechanism slice contract did not cover an online row")


def mechanism_slice_selection_diagnostics(
    probabilities: np.ndarray, arrays: Mapping[str, np.ndarray],
    slice_contract: Mapping[str, Any], *, row_mask: np.ndarray | None = None,
    commit_probability: float | None = None,
    margin_threshold: float | None = None,
) -> dict[str, Any]:
    """Report descriptive one-step behavior on fixed mechanism slices."""
    probabilities = np.asarray(probabilities, dtype=np.float64)
    reference = np.asarray(arrays["y"], dtype=np.int64)
    recovery = np.asarray(arrays["recovery"], dtype=bool)
    family_indices = np.asarray(arrays["scenario_family_index"], dtype=np.int64)
    ambiguous = np.asarray(arrays["ambiguous"], dtype=bool)
    if probabilities.ndim != 2 or len(probabilities) != len(reference):
        raise ValueError("mechanism slice probabilities have the wrong shape")
    selected_rows = ~recovery
    if row_mask is not None:
        requested = np.asarray(row_mask, dtype=bool)
        if requested.shape != selected_rows.shape:
            raise ValueError("mechanism slice row mask has the wrong shape")
        selected_rows &= requested
    family_names = [f"C{index:02d}" for index in family_indices]
    names = np.asarray([
        _mechanism_slice_name(family, is_ambiguous, slice_contract)
        for family, is_ambiguous in zip(
            family_names, ambiguous, strict=True,
        )
    ], dtype=object)
    predicted = probabilities.argmax(axis=1)
    rows = np.arange(len(reference))
    calibrated = commit_probability is not None and margin_threshold is not None
    if calibrated:
        ordered = np.sort(probabilities, axis=1)
        requested_commit = (
            (ordered[:, -1] >= float(commit_probability))
            & (
                np.round(ordered[:, -1] - ordered[:, -2], 12)
                >= float(margin_threshold)
            )
        )
        legal = np.asarray(arrays["candidate_legal"], dtype=bool)
        committed = requested_commit & legal[rows, predicted]
        executor_quarantined = requested_commit & ~legal[rows, predicted]
        active = np.asarray(arrays["active_correct"], dtype=np.float64)
        base_active = np.asarray(
            arrays["base_active_correct"], dtype=np.float64,
        )
        active_after = np.where(
            committed, active[rows, predicted], base_active,
        )
        collateral = np.asarray(
            arrays["candidate_energy_collateral"], dtype=np.float64,
        )
        selected_collateral = np.where(
            committed, collateral[rows, predicted], 0.0,
        )
    else:
        requested_commit = np.zeros(len(reference), dtype=bool)
        committed = np.zeros(len(reference), dtype=bool)
        executor_quarantined = np.zeros(len(reference), dtype=bool)
        active_after = np.full(len(reference), np.nan)
        selected_collateral = np.full(len(reference), np.nan)
    output = {
        "selection_rule": slice_contract["selection_rule"],
        "primary_gate": False,
        "full_mixed_20_step_causal_endpoint_remains_primary": True,
        "slices": {},
    }
    for name in slice_contract["precedence"]:
        mask = selected_rows & (names == name)
        item = {
            "definition": slice_contract[name]["definition"],
            "expected_behavior": slice_contract[name]["expected_behavior"],
            "rows": int(mask.sum()),
            "selection_accuracy": (
                float(np.mean(predicted[mask] == reference[mask]))
                if mask.any() else None
            ),
        }
        if calibrated:
            committed_mask = mask & committed
            item.update({
                "commit_attempt_rate": (
                    float(np.mean(requested_commit[mask]))
                    if mask.any() else None
                ),
                "commit_rate": float(np.mean(committed[mask])) if mask.any() else None,
                "executor_quarantine_rate": (
                    float(np.mean(executor_quarantined[mask]))
                    if mask.any() else None
                ),
                "committed_registered_accuracy": (
                    float(np.mean(
                        predicted[committed_mask] == reference[committed_mask]
                    )) if committed_mask.any() else None
                ),
                "active_correctness_after_decision": (
                    float(np.mean(active_after[mask])) if mask.any() else None
                ),
                "selected_collateral_rate": (
                    float(np.mean(selected_collateral[mask])) if mask.any() else None
                ),
            })
        output["slices"][str(name)] = item
    return output


def structured_relation_target_only_diagnostics(
    arrays: Mapping[str, np.ndarray],
    *, static_preflight_pass: np.ndarray | None = None,
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
    available = np.ones_like(mismatch, dtype=bool)
    if static_preflight_pass is not None:
        available = np.asarray(static_preflight_pass, dtype=bool)
        if available.shape != mismatch.shape:
            raise ValueError(
                "static preflight mask and relation mismatch must have equal shape"
            )
        if np.any(~available.any(axis=1)):
            raise ValueError("static preflight rejected every candidate in a row")
        mismatch = np.where(available, mismatch, np.inf)
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
        "uses_static_preflight_filter": static_preflight_pass is not None,
        "mean_available_candidates": float(available.sum(axis=1).mean()),
        "minimum_available_candidates": int(available.sum(axis=1).min()),
        "maximum_available_candidates": int(available.sum(axis=1).max()),
        "all": summarize(all_rows),
        "identifiable": summarize(~ambiguous),
        "ambiguous": summarize(ambiguous),
    }


def current_now_comparability_diagnostics(
    arrays: Mapping[str, np.ndarray], scenario_families: Sequence[str],
) -> dict[str, Any]:
    """Compare proxy and executed-now ranking on exactly the same support.

    Missing executed-now rows are reported, never counted as failures while an
    all-tied proxy row is counted as success. Both channels use the same
    admitted, executor-legal candidates solely for this offline audit; this
    legality mask is not available to C/E at deployment.
    """
    targets = np.asarray(arrays["relation_targets"], dtype=np.float64)
    masks = np.asarray(arrays["relation_mask"], dtype=np.float64)
    desired = np.asarray(arrays["relation_desired"], dtype=np.float64)
    reference = np.asarray(arrays["y"], dtype=np.int64)
    executed = np.asarray(arrays["candidate_energy_now_raw"], dtype=np.float64)
    executed_scaled = np.asarray(
        arrays["candidate_energy_now"], dtype=np.float64,
    )
    executed_natural_range = np.asarray(
        arrays["candidate_energy_now_natural_range"], dtype=np.float64,
    )
    admitted = np.asarray(
        arrays["candidate_static_preflight_pass"], dtype=bool,
    )
    legal = np.asarray(arrays["candidate_legal"], dtype=bool)
    recovery = np.asarray(arrays["recovery"], dtype=bool)
    if targets.shape != masks.shape or targets.shape != desired.shape:
        raise ValueError("current-now audit relation arrays differ in shape")
    if (
        targets.shape[:2] != executed.shape
        or admitted.shape != executed.shape
        or executed_scaled.shape != executed.shape
        or executed_natural_range.shape != executed.shape
    ):
        raise ValueError("current-now audit candidate arrays differ in shape")
    if np.any(executed_natural_range <= 0.0):
        raise ValueError("current-now audit natural ranges must be positive")
    current_dim = len(CURRENT_RELATION_QUERIES)
    current_targets = targets[:, :, :current_dim]
    current_masks = masks[:, :, :current_dim]
    current_desired = desired[:, :, :current_dim]
    denominators = current_masks.sum(axis=2)
    proxy = np.divide(
        (np.abs(current_targets - current_desired) * current_masks).sum(axis=2),
        denominators,
        out=np.full_like(denominators, np.nan),
        where=denominators > 0.0,
    )
    common_available = (
        admitted & legal & np.isfinite(proxy) & np.isfinite(executed)
    )
    rows = np.arange(len(reference))
    common_rows = (
        ~recovery
        & common_available[rows, reference]
        & common_available.any(axis=1)
    )

    def summarize(values: np.ndarray, row_mask: np.ndarray) -> dict[str, Any] | None:
        selected = common_rows & row_mask
        if not selected.any():
            return None
        scored = np.where(common_available, values, np.inf)
        minima = scored.min(axis=1, keepdims=True)
        minimum_set = np.isclose(scored, minima, rtol=1e-9, atol=1e-12)
        tie_size = minimum_set.sum(axis=1)
        reference_is_minimum = minimum_set[rows, reference]
        return {
            "rows": int(selected.sum()),
            "reference_in_minimum_set_rate": float(
                reference_is_minimum[selected].mean()
            ),
            "unique_reference_minimum_rate": float((
                reference_is_minimum[selected] & (tie_size[selected] == 1)
            ).mean()),
            "uniform_tie_break_expected_accuracy": float(
                (reference_is_minimum[selected] / tie_size[selected]).mean()
            ),
            "mean_minimum_set_size": float(tie_size[selected].mean()),
        }

    family_indices = np.asarray(arrays["scenario_family_index"], dtype=np.int64)
    by_family = {}
    for family_index, family in enumerate(scenario_families):
        family_rows = family_indices == family_index
        by_family[str(family)] = {
            "proxy": summarize(proxy, family_rows),
            "executed_now_raw": summarize(executed, family_rows),
        }

    pair_checks = []
    ambiguous = np.asarray(arrays["ambiguous"], dtype=bool) & ~recovery
    groups = np.asarray(arrays["group"], dtype=np.int64)
    for group in np.unique(groups[ambiguous]):
        pair_rows = np.flatnonzero(ambiguous & (groups == group))
        if len(pair_rows) != 2:
            pair_checks.append(False)
            continue
        left, right = pair_rows
        pair_checks.append(
            int(reference[left]) != int(reference[right])
            and np.array_equal(current_targets[left], current_targets[right])
            and np.array_equal(current_masks[left], current_masks[right])
            and np.array_equal(current_desired[left], current_desired[right])
        )
    all_rows = np.ones(len(reference), dtype=bool)
    scale_available = admitted & legal & np.isfinite(executed)
    expected_scaled = np.divide(
        executed,
        executed_natural_range,
        out=np.zeros_like(executed),
        where=scale_available,
    )
    scaling_error = np.abs(executed_scaled - expected_scaled)
    return {
        "online_rows": int((~recovery).sum()),
        "common_support_rows": int(common_rows.sum()),
        "executed_now_unavailable_online_rows": int((
            (~recovery) & ~np.isfinite(executed[rows, reference])
        ).sum()),
        "proxy": summarize(proxy, all_rows),
        "executed_now_raw": summarize(executed, all_rows),
        "fixed_natural_range_scaling": {
            "available_candidates": int(scale_available.sum()),
            "natural_ranges": sorted({
                float(value) for value in executed_natural_range[
                    scale_available
                ]
            }),
            "scaled_minimum": (
                float(executed_scaled[scale_available].min())
                if scale_available.any() else None
            ),
            "scaled_maximum": (
                float(executed_scaled[scale_available].max())
                if scale_available.any() else None
            ),
            "maximum_absolute_scaling_error": (
                float(scaling_error[scale_available].max())
                if scale_available.any() else None
            ),
            "all_available_values_within_0_1": bool(
                np.all(executed_scaled[scale_available] >= -1e-7)
                and np.all(executed_scaled[scale_available] <= 1.0 + 1e-7)
            ),
        },
        "by_family": by_family,
        "exact_ambiguity_pairs": len(pair_checks),
        "exact_ambiguity_current_target_identity_rate": (
            float(np.mean(pair_checks)) if pair_checks else None
        ),
        "strength_cap_enforced": False,
        "interpretation": (
            "same-support audit; a strong deployable proxy is not capped, but "
            "missing executed-now rows cannot be counted asymmetrically"
        ),
    }


def static_preflight_diagnostics(
    arrays: Mapping[str, np.ndarray],
) -> dict[str, Any]:
    """Compare read-only rejection with executed legality after the fact.

    The static flag is computed before any operation is applied.  Executor
    legality is used here only as an audit label: it is never returned as an
    online feature or substituted for the preflight flag.
    """
    required = (
        "candidate_static_preflight_pass",
        "candidate_legal",
        "candidate_templates",
        "candidate_execution_failure_code",
        "candidate_static_preflight_failure_code",
        "relation_targets",
        "relation_mask",
        "relation_desired",
        "no_execution_penalties",
        "y",
    )
    missing = [key for key in required if key not in arrays]
    if missing:
        raise ValueError(
            f"static preflight diagnostics require arrays {missing}"
        )
    passed = np.asarray(
        arrays["candidate_static_preflight_pass"], dtype=bool,
    )
    legal = np.asarray(arrays["candidate_legal"], dtype=bool)
    templates = np.asarray(arrays["candidate_templates"], dtype=np.int64)
    execution_failure = np.asarray(
        arrays["candidate_execution_failure_code"], dtype=np.int64,
    )
    preflight_failure = np.asarray(
        arrays["candidate_static_preflight_failure_code"], dtype=np.int64,
    )
    if not (
        passed.shape == legal.shape == templates.shape
        == execution_failure.shape == preflight_failure.shape
    ):
        raise ValueError("static preflight candidate arrays must have equal shape")
    if passed.ndim != 2:
        raise ValueError("static preflight candidate arrays must be row by candidate")
    if not np.array_equal(execution_failure == 0, legal):
        raise ValueError("execution failure codes disagree with candidate legality")
    if not np.array_equal(preflight_failure == 0, passed):
        raise ValueError("preflight failure codes disagree with preflight pass flags")
    reference = np.asarray(arrays["y"], dtype=np.int64)
    if len(reference) != len(passed):
        raise ValueError("static preflight references have the wrong row count")
    rows = np.arange(len(reference))
    rejected = ~passed
    illegal = ~legal
    detected = rejected & illegal
    false_reject = rejected & legal
    remaining_illegal = passed & illegal
    rows_with_remaining_illegal = remaining_illegal.any(axis=1)
    relation_targets = np.asarray(arrays["relation_targets"], dtype=np.float64)
    relation_mask = np.asarray(arrays["relation_mask"], dtype=np.float64)
    relation_desired = np.asarray(arrays["relation_desired"], dtype=np.float64)
    no_execution_penalties = np.asarray(
        arrays["no_execution_penalties"], dtype=np.float64,
    )
    if not (
        relation_targets.shape == relation_mask.shape == relation_desired.shape
        and relation_targets.shape[:2] == passed.shape
        and no_execution_penalties.shape == passed.shape
    ):
        raise ValueError("relation tie audit arrays have incompatible shapes")
    query_counts = relation_mask.sum(axis=2)
    if np.any(query_counts <= 0.0):
        raise ValueError("every candidate needs at least one relation query")
    mismatch = (
        np.abs(relation_targets - relation_desired) * relation_mask
    ).sum(axis=2) / query_counts
    minimum_set = np.isclose(
        mismatch, mismatch.min(axis=1, keepdims=True),
        rtol=1e-9, atol=1e-12,
    )
    illegal_minimum = minimum_set & illegal
    legal_minimum = minimum_set & legal

    def ratio(numerator: int, denominator: int) -> float | None:
        return float(numerator / denominator) if denominator else None

    def masked_mean(values: np.ndarray, mask: np.ndarray) -> float | None:
        return float(values[mask].mean()) if mask.any() else None

    def summarize(mask: np.ndarray) -> dict[str, Any]:
        count = int(mask.sum())
        illegal_count = int((mask & illegal).sum())
        rejected_count = int((mask & rejected).sum())
        detected_count = int((mask & detected).sum())
        legal_count = int((mask & legal).sum())
        false_reject_count = int((mask & false_reject).sum())
        return {
            "candidate_slots": count,
            "executor_illegal_candidates": illegal_count,
            "executor_illegal_fraction": ratio(illegal_count, count),
            "static_rejected_candidates": rejected_count,
            "static_reject_fraction": ratio(rejected_count, count),
            "illegal_detected_by_static_preflight": detected_count,
            "illegal_detection_recall": ratio(detected_count, illegal_count),
            "legal_candidates": legal_count,
            "legal_false_rejections": false_reject_count,
            "legal_false_rejection_rate": ratio(
                false_reject_count, legal_count,
            ),
        }

    all_mask = np.ones_like(passed, dtype=bool)
    result = summarize(all_mask)
    result.update({
        "rows": int(len(passed)),
        "static_reject_precision": ratio(
            int(detected.sum()), int(rejected.sum()),
        ),
        "remaining_executor_illegal_candidates": int(remaining_illegal.sum()),
        "remaining_illegal_fraction_among_preflight_pass": ratio(
            int(remaining_illegal.sum()), int(passed.sum()),
        ),
        "rows_with_remaining_executor_illegal_candidates": int(
            rows_with_remaining_illegal.sum()
        ),
        "maximum_teacher_decision_change_rate_due_to_residual_executor_illegal": (
            float(rows_with_remaining_illegal.mean())
        ),
        "residual_decision_impact_semantics": (
            "strict_rowwise_upper_bound; no counterfactual future is invented "
            "for candidates that failed execution"
        ),
        "reference_static_preflight_pass_rate": float(
            passed[rows, reference].mean()
        ),
        "mean_effective_candidate_count": float(passed.sum(axis=1).mean()),
        "admitted_uniform_random_accuracy": (
            uniform_admissible_random_accuracy(passed)
        ),
        "minimum_effective_candidate_count": int(passed.sum(axis=1).min()),
        "maximum_effective_candidate_count": int(passed.sum(axis=1).max()),
        "by_template": {
            name: summarize(templates == index)
            for index, name in enumerate(TEMPLATES)
        },
        "by_executor_failure_type": {
            name: {
                "candidates": int((execution_failure == code).sum()),
                "static_rejected": int((
                    (execution_failure == code) & rejected
                ).sum()),
                "static_reject_rate": ratio(
                    int(((execution_failure == code) & rejected).sum()),
                    int((execution_failure == code).sum()),
                ),
            }
            for code, name in enumerate(CANDIDATE_FAILURE_TYPES)
            if code != 0 and np.any(execution_failure == code)
        },
        "by_static_preflight_failure_type": {
            name: int((preflight_failure == code).sum())
            for code, name in enumerate(CANDIDATE_FAILURE_TYPES)
            if code != 0 and np.any(preflight_failure == code)
        },
        "relation_tie_audit": {
            "minimum_set_contains_executor_illegal_row_rate": float(
                illegal_minimum.any(axis=1).mean()
            ),
            "minimum_set_executor_illegal_members": int(
                illegal_minimum.sum()
            ),
            "minimum_set_legal_members": int(legal_minimum.sum()),
            "static_preflight_recall_on_illegal_minimum_members": ratio(
                int((illegal_minimum & rejected).sum()),
                int(illegal_minimum.sum()),
            ),
            "mean_relation_queries_executor_illegal": masked_mean(
                query_counts, illegal,
            ),
            "mean_relation_queries_executor_legal": masked_mean(
                query_counts, legal,
            ),
            "mean_no_execution_penalty_illegal_minimum": masked_mean(
                no_execution_penalties, illegal_minimum,
            ),
            "mean_no_execution_penalty_legal_minimum": masked_mean(
                no_execution_penalties, legal_minimum,
            ),
        },
        "executor_legality_used_as_audit_label_only": True,
        "fed_to_online_model": False,
        "filter_enabled_for_method_selection": True,
        "shared_online_admissibility_methods": ["A", "B", "C", "D", "E"],
        "preflight_pass_claims_executor_legality": False,
    })
    return result


def calibrate_shared_commit_rule(
    probabilities_by_run: Mapping[str, np.ndarray],
    arrays: Mapping[str, np.ndarray], hard_config: Mapping[str, Any],
) -> dict[str, Any]:
    """Compatibility helper for pre-D-045 reports; never use for M1 primary runs.

    Historical reports selected one A-E gate from one-step post-world outcomes
    on a validation-calibration half. D-045 supersedes that policy with the
    fixed ``(commit_probability=0, margin_threshold=0)`` always-attempt rule.
    This function remains only so old fixtures and reports stay reproducible.
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
    static_preflight_pass = arrays.get("candidate_static_preflight_pass")
    if static_preflight_pass is not None:
        static_preflight_pass = np.asarray(
            static_preflight_pass, dtype=bool,
        )
        if static_preflight_pass.shape != candidate_legal.shape:
            raise ValueError("calibration static-preflight mask shape differs")
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
                if (
                    static_preflight_pass is not None
                    and np.any(probabilities[~static_preflight_pass] > 1e-8)
                ):
                    raise ValueError(
                        f"calibration run {run_name} assigned probability to "
                        "a static-preflight rejection"
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
    static_preflight_pass = data.get("candidate_static_preflight_pass")
    if static_preflight_pass is None:
        static_preflight_pass_np = np.ones_like(probabilities, dtype=bool)
    else:
        static_preflight_pass_np = (
            static_preflight_pass.detach().cpu().numpy().astype(bool)
        )
    if static_preflight_pass_np.shape != probabilities.shape:
        raise ValueError("teacher-forced static-preflight mask shape differs")
    if np.any(probabilities[~static_preflight_pass_np] > 1e-8):
        raise ValueError(
            "teacher-forced probabilities include a preflight rejection"
        )
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
        "mean_effective_candidate_count": mean(
            static_preflight_pass_np.sum(axis=1), online,
        ),
        "static_rejected_selection_rate": mean(
            ~static_preflight_pass_np[
                np.arange(len(predicted)), predicted
            ],
            online,
        ),
    }


def causal_rollout_metrics(
    model: OnlineModel | None, audits: Sequence[Mapping[str, Any]],
    smoke_config: Mapping[str, Any], *, oracle: bool = False,
    observable_oracle: bool = False,
    audit_sink: Callable[[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]], None] | None = None,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    """Evaluate a method causally on its own persistent predicted graph."""
    if oracle and observable_oracle:
        raise ValueError("full and observable oracle modes are mutually exclusive")
    policy = smoke_config.get("candidate_availability_policy")
    if policy is not None:
        policy = validate_candidate_policy(policy)
        if int(smoke_config["current_evidence_scope_ranks"]) != 3:
            raise ValueError("D-054 requires the registered one-hop scope ranks=3")
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
            if policy is None:
                materialized = materialize_rollout_step(audit, current, step_index)
            else:
                materialized = materialize_rollout_step(audit, current, step_index, allow_unavailable=True)
                materialized["candidate_availability"]["availability_policy"] = policy["policy_id"]
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
                            errors["extra_open_fact_error"]
                            + errors["missing_open_fact_error"],
                            errors["false_birth_growth"],
                            not candidate["static_preflight_pass"],
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
                static_preflight_pass = torch.as_tensor(
                    [[
                        candidate["static_preflight_pass"]
                        for candidate in materialized["executed_candidates"]
                    ]],
                    dtype=torch.bool,
                    device=device,
                )
                started = time.perf_counter()
                with torch.no_grad():
                    logits = model(torch.as_tensor(vector[None], device=device))
                    probabilities = masked_candidate_probabilities(
                        logits, static_preflight_pass,
                    ).cpu().numpy()[0]
                forward_latencies_ms.append((time.perf_counter() - started) * 1000.0)
                selected_index = int(np.argmax(probabilities))
            selected = materialized["executed_candidates"][selected_index]
            if not selected["static_preflight_pass"]:
                raise AssertionError(
                    "online selection returned a static-preflight rejection"
                )
            decision = decide_commit(
                {str(index): float(value) for index, value in enumerate(probabilities)},
                decision_id=f"{audit['sequence_id']}:{step_index}",
                at=int(stored["event_spec"]["decision_time"]),
                commit_probability=float(smoke_config["commit_probability"]),
                margin_threshold=float(smoke_config["margin_threshold"]),
            )
            base = current
            commit_requested = decision["action"] == "COMMIT"
            committed = commit_requested and selected["legal"]
            executor_quarantined = commit_requested and not selected["legal"]
            current = selected["post_graph"] if committed else clone_json(base)
            evidence_scope = _current_online_evidence_scope(
                base, stored["event_spec"],
                ranks=int(smoke_config["current_evidence_scope_ranks"]),
            )
            selected_collateral = float(
                committed
                and _collateral_mutation(base, current, evidence_scope) > 0.0
            )
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
                "selected_static_preflight_pass": selected[
                    "static_preflight_pass"
                ],
                "selected_legal": selected["legal"],
                "effective_candidate_count": int(sum(
                    candidate["static_preflight_pass"]
                    for candidate in materialized["executed_candidates"]
                )),
                "committed": committed,
                "commit_requested": commit_requested,
                "executor_quarantined": executor_quarantined,
                "registered_selection_correct": registered_correct,
                "committed_registered_correct": committed and registered_correct,
                "revisit_opportunity": revisit_opportunity,
                "revisit_triggered": revisit_triggered,
                "active_correct_after": active_correct_after,
                "selected_collateral": selected_collateral,
                "probabilities": probabilities.tolist(),
                "base_graph_hash": base["graph_hash"],
                "post_graph_hash": current["graph_hash"],
            })
            if policy is not None:
                choices[-1]["candidate_availability"] = step_availability(
                    materialized, stored["event_spec"], reference_state,
                    is_c11=stored["scenario_family"] == "C11")
            # Optional offline recorder runs only after the online choice and
            # persistence decision. It is not a model input or selection hook.
            if audit_sink is not None:
                audit_sink({**materialized, "audit_sequence_id": audit["sequence_id"],
                            "audit_sibling_index": audit["sibling_index"]}, choices[-1], current)
        metrics = rollout_graph_metrics(
            predicted_states, references, base_states, protected, horizon=20,
            unrelated_collateral_by_step=[
                choice["selected_collateral"] for choice in choices
            ],
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
            "commit_attempt_rate": float(np.mean([
                item["commit_requested"] for item in choices
            ])),
            "commit_rate": float(np.mean([item["committed"] for item in choices])),
            "executor_quarantine_rate": float(np.mean([
                item["executor_quarantined"] for item in choices
            ])),
            "raw_invalid_selection_rate": float(np.mean([
                not item["selected_legal"] for item in choices
            ])),
            "raw_static_rejected_selection_rate": float(np.mean([
                not item["selected_static_preflight_pass"] for item in choices
            ])),
            "mean_effective_candidate_count": float(np.mean([
                item["effective_candidate_count"] for item in choices
            ])),
            # Step zero starts from the registered initial world, before the
            # method can create self-rollout drift. The all-step rate above
            # intentionally retains the compounded failure signal.
            "initial_step_raw_invalid_selection_rate": float(
                not choices[0]["selected_legal"]
            ),
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
        row = {"metrics": metrics, "choices": choices}
        if policy is not None:
            row["candidate_availability"] = summarize_availability(choices)
        sequence_rows.append(row)
    metric_names = (
        "mean_active_graph_correctness", "final_active_graph_correctness",
        "mean_graded_active_world_correctness",
        "final_graded_active_world_correctness",
        "mean_graded_open_memory_correctness",
        "final_graded_open_memory_correctness",
        "mean_open_memory_correctness", "final_open_memory_correctness",
        "mean_history_exactness", "final_history_exactness",
        "mean_post_graph_correctness", "final_post_graph_correctness",
        "terminal_extra_open_fact_error_per_100_decisions",
        "terminal_missing_open_fact_error_per_100_decisions",
        "terminal_new_incorrect_open_fact_write_per_100_decisions",
        "terminal_retained_stale_open_fact_per_100_decisions",
        "memory_contamination_per_100", "missing_open_facts_per_100",
        "false_birth_growth_per_100", "collateral_violation_per_100",
        "protected_collateral_violation_per_100",
        "unrelated_collateral_violation_per_100",
        "active_node_state_error_per_100",
        "active_edge_state_error_per_100",
        "open_evidence_attachment_error_per_100",
        "open_memory_node_error_per_100",
        "open_memory_edge_error_per_100",
        "final_active_reference_node_count",
        "final_active_reference_edge_count",
        "final_active_reference_record_count",
        "final_active_record_union_count",
        "final_open_memory_reference_record_count",
        "final_open_memory_record_union_count",
        "final_open_memory_reference_evidence_attachment_count",
        "mean_extra_open_fact_error", "mean_missing_open_fact_error",
        "mean_memory_contamination",
        "extra_open_fact_error_auc_per_100_decisions",
        "missing_open_fact_error_auc_per_100_decisions",
        "open_fact_error_auc_per_100_decisions",
        "new_incorrect_open_fact_write_auc_per_100_decisions",
        "retained_stale_open_fact_auc_per_100_decisions",
        "false_birth_growth_auc_per_100_decisions",
        "missing_open_entity_auc_per_100_decisions",
        "memory_contamination_auc_per_100_decisions",
        "unresolved_active_error", "commit_attempt_rate", "commit_rate",
        "executor_quarantine_rate", "raw_invalid_selection_rate",
        "raw_static_rejected_selection_rate", "mean_effective_candidate_count",
        "initial_step_raw_invalid_selection_rate",
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
        ])) if generic_eligible else None
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
        ])) if designed_eligible else None
    )
    aggregate["designed_recovery_rate_within_window"] = (
        float(np.mean([
            row["designed_recovery_success"] for row in designed_eligible
        ])) if designed_eligible else None
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
        float(np.mean(generic_recovered)) if generic_recovered else None
    )
    designed_recovered = [
        row["designed_recovery_time"] for row in designed_eligible
        if row["designed_recovery_time"] >= 0.0
    ]
    aggregate["mean_time_to_first_recovery"] = (
        float(np.mean(designed_recovered)) if designed_recovered else None
    )
    aggregate["p95_forward_latency_ms"] = (
        float(np.quantile(forward_latencies_ms, 0.95))
        if forward_latencies_ms else 0.0
    )
    slice_contract = smoke_config.get("mechanism_diagnostic_slices")
    if slice_contract is not None:
        all_choices = [
            choice for row in sequence_rows for choice in row["choices"]
        ]
        slice_report = {
            "selection_rule": slice_contract["selection_rule"],
            "primary_gate": False,
            "full_mixed_20_step_causal_endpoint_remains_primary": True,
            "slices": {},
        }
        for name in slice_contract["precedence"]:
            selected = [
                choice for choice in all_choices
                if _mechanism_slice_name(
                    choice["scenario_family"], choice["ambiguity"],
                    slice_contract,
                ) == name
            ]
            committed = [choice for choice in selected if choice["committed"]]
            slice_report["slices"][name] = {
                "definition": slice_contract[name]["definition"],
                "expected_behavior": slice_contract[name]["expected_behavior"],
                "decisions": len(selected),
                "selection_accuracy": (
                    float(np.mean([
                        choice["registered_selection_correct"]
                        for choice in selected
                    ])) if selected else None
                ),
                "commit_rate": (
                    float(np.mean([
                        choice["committed"] for choice in selected
                    ])) if selected else None
                ),
                "commit_attempt_rate": (
                    float(np.mean([
                        choice["commit_requested"] for choice in selected
                    ])) if selected else None
                ),
                "executor_quarantine_rate": (
                    float(np.mean([
                        choice["executor_quarantined"] for choice in selected
                    ])) if selected else None
                ),
                "committed_registered_accuracy": (
                    float(np.mean([
                        choice["registered_selection_correct"]
                        for choice in committed
                    ])) if committed else None
                ),
                "active_correctness_after_decision": (
                    float(np.mean([
                        choice["active_correct_after"] for choice in selected
                    ])) if selected else None
                ),
                "selected_collateral_rate": (
                    float(np.mean([
                        choice["selected_collateral"] for choice in selected
                    ])) if selected else None
                ),
            }
        aggregate["mechanism_diagnostic_slices"] = slice_report
    if policy is not None:
        aggregate["candidate_availability_policy"] = policy
        aggregate["candidate_availability"] = summarize_availability(
            [choice for row in sequence_rows for choice in row["choices"]])
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
        train_teacher = apply_candidate_admissibility_to_probabilities(
            train_teacher,
            candidate_admissibility_mask(train, train["penalties"]),
        )
        validation_teacher = apply_candidate_admissibility_to_probabilities(
            validation_teacher,
            candidate_admissibility_mask(
                validation, validation["penalties"],
            ),
        )
        started = time.perf_counter()
        model, trace = train_student(
            method, train, train_teacher, dict(smoke_config), seed, device,
        )
        seconds = time.perf_counter() - started
        with torch.no_grad():
            logits = model(validation["x"])
            probabilities = masked_candidate_probabilities(
                logits, candidate_admissibility_mask(validation, logits),
            ).cpu().numpy()
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
