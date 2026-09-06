"""Graph metrics and paired statistics for the frozen M1 protocol.

Single-step helpers operate on executed audit branches. Rollout metrics require
an actual ordered state sequence and deliberately reject the wrong horizon;
independent cases cannot be passed off as persistent self-rollout.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from .hashing import canonical_json


def _open_fact_tokens(graph: Mapping[str, Any]) -> set[str]:
    return {
        canonical_json({
            "source": edge["source"],
            "target": edge["target"],
            "relation": edge["relation"],
            "frame": edge["frame"],
        })
        for edge in graph["edges"]
        if edge.get("valid_to") is None
    }


def _open_entity_ids(graph: Mapping[str, Any]) -> set[str]:
    return {
        node["node_id"]
        for node in graph["nodes"]
        if node["node_type"] == "entity"
        and node.get("valid_to") is None
        and node["lifecycle"] not in {"retracted", "alias"}
    }


def _decision_state(graph: Mapping[str, Any]) -> str:
    nodes = [{
        key: node.get(key)
        for key in (
            "node_id", "node_version_id", "node_type", "lifecycle",
            "valid_from", "valid_to", "canonical_id", "predecessor_ids",
            "evidence_refs", "latent_refs",
        )
    } for node in graph["nodes"]]
    edges = [{
        key: edge.get(key)
        for key in (
            "edge_id", "edge_version_id", "source", "target", "relation",
            "frame", "valid_from", "valid_to", "evidence_refs",
        )
    } for edge in graph["edges"]]
    return canonical_json({
        "nodes": sorted(nodes, key=canonical_json),
        "edges": sorted(edges, key=canonical_json),
    })


def protected_signature(graph: Mapping[str, Any], protected_ids: Iterable[str]) -> str:
    """Canonical view of the protected subgraph, shared with the generator."""
    return _protected_signature(graph, set(str(value) for value in protected_ids))


def _protected_signature(graph: Mapping[str, Any], protected_ids: set[str]) -> str:
    nodes = [
        node for node in graph["nodes"]
        if node.get("node_id") in protected_ids
        or node.get("node_version_id") in protected_ids
    ]
    edges = [
        edge for edge in graph["edges"]
        if edge.get("edge_id") in protected_ids
        or edge.get("edge_version_id") in protected_ids
    ]
    return canonical_json({
        "nodes": sorted(nodes, key=canonical_json),
        "edges": sorted(edges, key=canonical_json),
    })


def graph_error_counts(
    predicted: Mapping[str, Any], reference: Mapping[str, Any],
    base: Mapping[str, Any], protected_ids: Iterable[str],
) -> dict[str, float]:
    """Count persistent graph errors without combining them into one score."""
    predicted_facts = _open_fact_tokens(predicted)
    reference_facts = _open_fact_tokens(reference)
    false_births = max(
        0, len(_open_entity_ids(predicted)) - len(_open_entity_ids(reference))
    )
    protected = set(protected_ids)
    return {
        "post_graph_correct": float(_decision_state(predicted) == _decision_state(reference)),
        "memory_contamination": float(len(predicted_facts - reference_facts)),
        "missing_open_facts": float(len(reference_facts - predicted_facts)),
        "false_birth_growth": float(false_births),
        "collateral_violation": float(
            _protected_signature(predicted, protected)
            != _protected_signature(base, protected)
        ),
    }


def evaluate_selected_candidate(
    audit_record: Mapping[str, Any], selected_index: int,
) -> dict[str, float]:
    """Apply QUARANTINE fallback semantics to one recorded candidate choice."""
    candidates = audit_record["executed_candidates"]
    if not 0 <= selected_index < len(candidates):
        raise ValueError("selected candidate index is outside the recorded budget")
    selected = candidates[selected_index]
    reference = candidates[audit_record["reference_program_index"]]["post_graph"]
    if reference is None:
        raise ValueError("reference candidate is not executable")
    base = audit_record["online"]["prior_world"]
    if selected["legal"]:
        predicted = selected["post_graph"]
        committed = 1.0
    else:
        # Invalid raw programs are reported, then deterministic fallback keeps
        # persistent world unchanged, matching QUARANTINE semantics.
        predicted = base
        committed = 0.0
    protected_ids = {
        protected_id
        for program in audit_record["online"]["candidate_programs"]
        for protected_id in program.get("protected_ids", [])
    }
    metrics = graph_error_counts(predicted, reference, base, protected_ids)
    metrics.update({
        "raw_invalid_program": float(not selected["legal"]),
        "committed": committed,
        "candidate_miss": float(audit_record["candidate_coverage_at_k"] < 1.0),
    })
    return metrics


def rollout_graph_metrics(
    predicted_states: Sequence[Mapping[str, Any]],
    reference_states: Sequence[Mapping[str, Any]],
    base_states: Sequence[Mapping[str, Any]],
    protected_ids_by_step: Sequence[Iterable[str]],
    *, horizon: int,
) -> dict[str, float]:
    """Evaluate a real ordered rollout; independent cases are not accepted."""
    lengths = {
        len(predicted_states), len(reference_states), len(base_states),
        len(protected_ids_by_step),
    }
    if lengths != {horizon}:
        raise ValueError("rollout inputs must be one ordered sequence at the frozen horizon")
    per_step = [
        graph_error_counts(predicted, reference, base, protected)
        for predicted, reference, base, protected in zip(
            predicted_states, reference_states, base_states,
            protected_ids_by_step, strict=True,
        )
    ]
    final = per_step[-1]
    return {
        "mean_post_graph_correctness": float(np.mean([
            row["post_graph_correct"] for row in per_step
        ])),
        "final_post_graph_correctness": final["post_graph_correct"],
        "memory_contamination_per_100": 100.0 * final["memory_contamination"] / horizon,
        "missing_open_facts_per_100": 100.0 * final["missing_open_facts"] / horizon,
        "false_birth_growth_per_100": 100.0 * final["false_birth_growth"] / horizon,
        "collateral_violation_per_100": 100.0 * sum(
            row["collateral_violation"] for row in per_step
        ) / horizon,
    }


def paired_stratified_bootstrap(
    rows: Sequence[Mapping[str, Any]], method_a: str, method_b: str,
    metric: str, *, higher_is_better: bool, resamples: int = 10_000,
    confidence: float = 0.95, seed: int = 260_906,
) -> dict[str, float]:
    """Bootstrap A-vs-B improvements without breaking paired groups."""
    if not rows or resamples <= 0 or not 0 < confidence < 1:
        raise ValueError("bootstrap needs rows, positive resamples, and valid confidence")
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        raw = float(row[method_a][metric]) - float(row[method_b][metric])
        improvement = raw if higher_is_better else -raw
        grouped[(str(row["scenario_family"]), str(row["paired_group_id"]))].append(
            improvement
        )
    by_family: dict[str, list[float]] = defaultdict(list)
    for (family, _), values in grouped.items():
        by_family[family].append(float(np.mean(values)))
    family_names = sorted(by_family)
    observed = np.asarray([
        value for family in family_names for value in by_family[family]
    ], dtype=np.float64)
    rng = np.random.default_rng(seed)
    samples = np.empty(resamples, dtype=np.float64)
    for index in range(resamples):
        draw = []
        for family in family_names:
            values = np.asarray(by_family[family], dtype=np.float64)
            draw.extend(rng.choice(values, size=len(values), replace=True))
        samples[index] = float(np.mean(draw))
    alpha = 1.0 - confidence
    return {
        "effect": float(observed.mean()),
        "ci_low": float(np.quantile(samples, alpha / 2)),
        "ci_high": float(np.quantile(samples, 1 - alpha / 2)),
        "one_sided_p_nonpositive": float((1 + np.sum(samples <= 0)) / (resamples + 1)),
        "paired_groups": float(len(grouped)),
        "families": float(len(by_family)),
        "resamples": float(resamples),
    }


def holm_bonferroni(p_values: Mapping[str, float]) -> dict[str, float]:
    """Return monotone Holm-adjusted p-values for the registered contrasts."""
    if not p_values or any(not 0 <= value <= 1 for value in p_values.values()):
        raise ValueError("p-values must be a non-empty mapping within [0,1]")
    ordered = sorted(p_values.items(), key=lambda item: item[1])
    adjusted: dict[str, float] = {}
    running = 0.0
    total = len(ordered)
    for rank, (name, value) in enumerate(ordered):
        running = max(running, min(1.0, (total - rank) * float(value)))
        adjusted[name] = running
    return adjusted
