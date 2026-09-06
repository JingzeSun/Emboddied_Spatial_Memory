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
        config.get("protocol") != "m1-af-causal-rollout-smoke-v1"
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
        protected_text = str(program.get("protected_ids", []))
        operation_text = str(program["operations"])
        block.append(float(any(
            protected_id in operation_text
            for protected_id in program.get("protected_ids", [])
            if protected_id in protected_text
        )))
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
) -> np.ndarray:
    """Hash audit-only structural observations into a fixed training target."""
    if len(future_trace) > horizon:
        raise ValueError("future trace exceeds configured horizon")
    values = np.zeros((horizon, bins), dtype=np.float32)
    mask = np.zeros(horizon, dtype=np.float32)
    for time_index, observation in enumerate(future_trace):
        tokens = observation["structural_observation"]
        mask[time_index] = 1.0
        scale = 1.0 / max(1, len(tokens))
        for token in tokens:
            values[time_index, _stable_bin(str(token), bins)] += scale
    return np.concatenate([values.reshape(-1), mask])


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
    for audit in audits:
        for step in audit["steps"]:
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
            penalties = []
            for energy in step["candidate_energies"]:
                if energy["masked"]:
                    penalties.append(1_000_000.0)
                else:
                    penalties.append(sum(
                        float(weights[key]) * float(energy[key])
                        for key in ("now", "edit", "growth", "collateral")
                    ))
            rows.append({
                "x": online_feature_vector(step["online"]),
                "future": future_feature_vector(
                    step["future_trace"], horizon=horizon, bins=future_hash_bins,
                ),
                "poses": np.asarray([
                    item["pose_bucket"] / 7.0 for item in step["future_trace"]
                ] + [0.0] * (horizon - len(step["future_trace"])), dtype=np.float32),
                "y": int(step["reference_program_index"]),
                "pstar": np.asarray(step["teacher_posterior"], dtype=np.float32),
                "pstar_current": _posterior_from_current_energy(
                    step, weights, temperature,
                ),
                "labelled": bool(step["transaction_label_available"]),
                "ambiguous": step["ambiguity"] == "epistemically_ambiguous_pivot",
                "group": group_ids[audit["paired_group_id"]],
                "fact_errors": np.asarray([
                    item["memory_contamination"] + item["missing_open_facts"]
                    for item in candidate_metrics
                ], dtype=np.float32),
                "excess_nodes": np.asarray([
                    item["false_birth_growth"] for item in candidate_metrics
                ], dtype=np.float32),
                "penalties": np.asarray(penalties, dtype=np.float32),
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
    predicted = np.asarray(probabilities).argmax(axis=1)
    rows = np.arange(len(target))
    predicted_template = templates[rows, predicted]
    target_template = templates[rows, target]
    template_correct = predicted_template == target_template
    correct = predicted == target

    def mean(values: np.ndarray, mask: np.ndarray | None = None) -> float | None:
        selected = values if mask is None else values[mask]
        return float(selected.mean()) if len(selected) else None

    return {
        "accuracy": mean(correct),
        "template_accuracy": mean(template_correct),
        "argument_accuracy_given_template": mean(correct, template_correct),
        "template_error": mean(~template_correct),
        "argument_error_with_correct_template": mean(template_correct & ~correct),
        "identifiable_accuracy": mean(correct, ~ambiguous),
        "ambiguous_accuracy": mean(correct, ambiguous),
        "ambiguous_fraction": mean(ambiguous),
    }


def _teacher_forced_metrics(
    probabilities: np.ndarray, data: Mapping[str, torch.Tensor],
    teacher: torch.Tensor,
) -> dict[str, float]:
    target = data["y"].detach().cpu().numpy()
    ambiguous = data["ambiguous"].detach().cpu().numpy()
    predicted = probabilities.argmax(axis=1)
    teacher_choice = teacher.argmax(dim=1).detach().cpu().numpy()
    return {
        "accuracy": float(np.mean(predicted == target)),
        "ambiguous_accuracy": float(np.mean(predicted[ambiguous] == target[ambiguous])),
        "identifiable_accuracy": float(np.mean(predicted[~ambiguous] == target[~ambiguous])),
        "teacher_accuracy": float(np.mean(teacher_choice == target)),
        "amortization_error": float(np.mean(predicted != teacher_choice)),
        "mean_confidence": float(np.mean(probabilities.max(axis=1))),
    }


def causal_rollout_metrics(
    model: OnlineModel | None, audits: Sequence[Mapping[str, Any]],
    smoke_config: Mapping[str, Any], *, oracle: bool = False,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    """Evaluate a method causally on its own persistent predicted graph."""
    device = torch.device(smoke_config["device"])
    sequence_rows = []
    forward_latencies_ms = []
    for audit in audits:
        current = clone_json(audit["initial_world"])
        predicted_states = []
        base_states = []
        choices = []
        references = []
        protected = []
        for step_index, stored in enumerate(audit["steps"]):
            materialized = materialize_rollout_step(audit, current, step_index)
            if oracle:
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
            reference = stored["executed_candidates"][
                stored["reference_program_index"]
            ]["post_graph"]
            references.append(reference)
            protected.append([stored["event_spec"]["protected_id"]])
            choices.append({
                "step_index": step_index,
                "selected_index": selected_index,
                "selected_template": selected["template"],
                "selected_legal": selected["legal"],
                "committed": committed,
                "probabilities": probabilities.tolist(),
                "base_graph_hash": base["graph_hash"],
                "post_graph_hash": current["graph_hash"],
            })
        metrics = rollout_graph_metrics(
            predicted_states, references, base_states, protected, horizon=20,
        )
        metrics.update({
            "paired_group_id": audit["paired_group_id"],
            "sequence_id": audit["sequence_id"],
            "sibling_index": audit["sibling_index"],
            "commit_rate": float(np.mean([item["committed"] for item in choices])),
            "raw_invalid_selection_rate": float(np.mean([
                not item["selected_legal"] for item in choices
            ])),
        })
        sequence_rows.append({"metrics": metrics, "choices": choices})
    metric_names = (
        "mean_post_graph_correctness", "final_post_graph_correctness",
        "memory_contamination_per_100", "missing_open_facts_per_100",
        "false_birth_growth_per_100", "collateral_violation_per_100",
        "commit_rate", "raw_invalid_selection_rate",
    )
    aggregate = {
        name: float(np.mean([row["metrics"][name] for row in sequence_rows]))
        for name in metric_names
    }
    aggregate["sequences"] = float(len(sequence_rows))
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
