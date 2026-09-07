"""Graph metrics and paired statistics for the frozen M1 protocol.

Single-step helpers operate on executed audit branches. Rollout metrics require
an actual ordered state sequence and deliberately reject the wrong horizon;
independent cases cannot be passed off as persistent self-rollout.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import math
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
    """Serialize the complete retained version history (legacy exact metric)."""
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


def _active_graph_state(graph: Mapping[str, Any]) -> str:
    """Serialize only current semantic world state, excluding audit history.

    This view answers whether the memory that is usable *now* has recovered.
    Closed versions, timestamps, evidence IDs and provenance stay available in
    the graph, but they cannot make an otherwise corrected active world fail.
    """
    nodes = [{
        key: node.get(key)
        for key in (
            "node_id", "node_type", "lifecycle", "canonical_id", "latent_refs",
        )
    } for node in graph["nodes"] if node.get("valid_to") is None]
    edges = [{
        key: edge.get(key)
        for key in ("source", "target", "relation", "frame")
    } for edge in graph["edges"] if edge.get("valid_to") is None]
    return canonical_json({
        "nodes": sorted(nodes, key=canonical_json),
        "edges": sorted(edges, key=canonical_json),
    })


def _active_record_counters(
    graph: Mapping[str, Any],
) -> tuple[Counter[str], Counter[str]]:
    """Return multiplicity-preserving active node and edge records."""
    nodes = Counter(
        canonical_json({
            key: node.get(key)
            for key in (
                "node_id", "node_type", "lifecycle", "canonical_id",
                "latent_refs",
            )
        })
        for node in graph["nodes"] if node.get("valid_to") is None
    )
    edges = Counter(
        canonical_json({
            key: edge.get(key)
            for key in ("source", "target", "relation", "frame")
        })
        for edge in graph["edges"] if edge.get("valid_to") is None
    )
    return nodes, edges


def _counter_symmetric_difference(
    left: Counter[str], right: Counter[str],
) -> int:
    return sum((left - right).values()) + sum((right - left).values())


def active_world_record_metrics(
    predicted: Mapping[str, Any], reference: Mapping[str, Any],
) -> dict[str, float]:
    """Grade the exact active-world state without losing duplicate records.

    The multiset Jaccard score uses exactly the semantic node and edge fields
    used by ``_active_graph_state``. Consequently, it is one exactly when the
    registered binary active-world endpoint is one; it is only a finer-grained
    relaxation of that same construct, not a different edge-only metric.
    """
    predicted_nodes, predicted_edges = _active_record_counters(predicted)
    reference_nodes, reference_edges = _active_record_counters(reference)
    predicted_all = predicted_nodes + predicted_edges
    reference_all = reference_nodes + reference_edges
    intersection = sum((predicted_all & reference_all).values())
    union = sum((predicted_all | reference_all).values())
    return {
        "graded_active_world_correctness": (
            float(intersection / union) if union else 1.0
        ),
        "active_node_state_symmetric_difference": float(
            _counter_symmetric_difference(predicted_nodes, reference_nodes)
        ),
        "active_edge_state_symmetric_difference": float(
            _counter_symmetric_difference(predicted_edges, reference_edges)
        ),
        "active_reference_node_count": float(sum(reference_nodes.values())),
        "active_reference_edge_count": float(sum(reference_edges.values())),
        "active_reference_record_count": float(sum(reference_all.values())),
        "active_record_union_count": float(union),
    }


def _open_memory_state(graph: Mapping[str, Any]) -> str:
    """Serialize current open records while retaining their evidence support."""
    nodes = [{
        key: node.get(key)
        for key in (
            "node_id", "node_type", "lifecycle", "canonical_id",
            "evidence_refs", "latent_refs",
        )
    } for node in graph["nodes"] if node.get("valid_to") is None]
    edges = [{
        key: edge.get(key)
        for key in (
            "source", "target", "relation", "frame", "evidence_refs",
        )
    } for edge in graph["edges"] if edge.get("valid_to") is None]
    return canonical_json({
        "nodes": sorted(nodes, key=canonical_json),
        "edges": sorted(edges, key=canonical_json),
    })


def _open_memory_record_counters(
    graph: Mapping[str, Any],
) -> tuple[Counter[str], Counter[str], Counter[str]]:
    """Return open records and their evidence attachments as multisets."""
    open_nodes = [
        node for node in graph["nodes"] if node.get("valid_to") is None
    ]
    open_edges = [
        edge for edge in graph["edges"] if edge.get("valid_to") is None
    ]
    node_records = Counter(
        canonical_json({
            key: node.get(key)
            for key in (
                "node_id", "node_type", "lifecycle", "canonical_id",
                "evidence_refs", "latent_refs",
            )
        })
        for node in open_nodes
    )
    edge_records = Counter(
        canonical_json({
            key: edge.get(key)
            for key in (
                "source", "target", "relation", "frame", "evidence_refs",
            )
        })
        for edge in open_edges
    )
    attachments: Counter[str] = Counter()
    for node in open_nodes:
        semantic = {
            key: node.get(key)
            for key in (
                "node_id", "node_type", "lifecycle", "canonical_id",
                "latent_refs",
            )
        }
        for evidence_ref in node.get("evidence_refs", []):
            attachments[canonical_json({
                "record_kind": "node",
                "semantic_record": semantic,
                "evidence_ref": evidence_ref,
            })] += 1
    for edge in open_edges:
        semantic = {
            key: edge.get(key)
            for key in ("source", "target", "relation", "frame")
        }
        for evidence_ref in edge.get("evidence_refs", []):
            attachments[canonical_json({
                "record_kind": "edge",
                "semantic_record": semantic,
                "evidence_ref": evidence_ref,
            })] += 1
    return node_records, edge_records, attachments


def open_memory_record_metrics(
    predicted: Mapping[str, Any], reference: Mapping[str, Any],
) -> dict[str, float]:
    """Grade current semantic records together with their evidence support."""
    predicted_nodes, predicted_edges, predicted_evidence = (
        _open_memory_record_counters(predicted)
    )
    reference_nodes, reference_edges, reference_evidence = (
        _open_memory_record_counters(reference)
    )
    predicted_all = predicted_nodes + predicted_edges
    reference_all = reference_nodes + reference_edges
    intersection = sum((predicted_all & reference_all).values())
    union = sum((predicted_all | reference_all).values())
    return {
        "graded_open_memory_correctness": (
            float(intersection / union) if union else 1.0
        ),
        "open_memory_node_symmetric_difference": float(
            _counter_symmetric_difference(predicted_nodes, reference_nodes)
        ),
        "open_memory_edge_symmetric_difference": float(
            _counter_symmetric_difference(predicted_edges, reference_edges)
        ),
        "open_evidence_attachment_symmetric_difference": float(
            _counter_symmetric_difference(
                predicted_evidence, reference_evidence,
            )
        ),
        "open_memory_reference_record_count": float(sum(reference_all.values())),
        "open_memory_record_union_count": float(union),
        "open_memory_reference_evidence_attachment_count": float(
            sum(reference_evidence.values())
        ),
    }


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
    predicted_entities = _open_entity_ids(predicted)
    reference_entities = _open_entity_ids(reference)
    predicted_extra_facts = predicted_facts - reference_facts
    reference_missing_facts = reference_facts - predicted_facts
    base_facts = _open_fact_tokens(base)
    # A state-only endpoint cannot say how an error arose.  Preserve the
    # symmetric state discrepancy and additionally separate facts introduced
    # by this decision from already-open facts that this decision retained.
    # Across a rollout the latter includes both genuinely newly stale facts and
    # earlier bad writes that have not yet been repaired.
    new_incorrect_facts = predicted_extra_facts - base_facts
    retained_incorrect_facts = predicted_extra_facts & base_facts
    protected = set(protected_ids)
    history_exact = float(_decision_state(predicted) == _decision_state(reference))
    result = {
        # Keep the old field as an explicit compatibility alias.  M1-v2 uses
        # active_graph_correct as the deployable outcome and reports the full
        # retained-history comparison separately.
        "post_graph_correct": history_exact,
        "active_graph_correct": float(
            _active_graph_state(predicted) == _active_graph_state(reference)
        ),
        "open_memory_correct": float(
            _open_memory_state(predicted) == _open_memory_state(reference)
        ),
        "history_exact": history_exact,
        "extra_open_fact_error": float(len(predicted_extra_facts)),
        "missing_open_fact_error": float(len(reference_missing_facts)),
        "new_incorrect_open_fact_write": float(len(new_incorrect_facts)),
        "retained_stale_open_fact": float(len(retained_incorrect_facts)),
        # Compatibility aliases for reports produced before D-045.  The new
        # names above are canonical because they state polarity explicitly.
        "memory_contamination": float(len(predicted_extra_facts)),
        "missing_open_facts": float(len(reference_missing_facts)),
        # Set difference, rather than a net cardinality difference, prevents
        # one missing real entity from cancelling one extra false entity.
        "false_birth_growth": float(len(
            predicted_entities - reference_entities
        )),
        "missing_open_entities": float(len(
            reference_entities - predicted_entities
        )),
        "collateral_violation": float(
            _protected_signature(predicted, protected)
            != _protected_signature(base, protected)
        ),
    }
    result.update(active_world_record_metrics(predicted, reference))
    result.update(open_memory_record_metrics(predicted, reference))
    if result["extra_open_fact_error"] != (
        result["new_incorrect_open_fact_write"]
        + result["retained_stale_open_fact"]
    ):
        raise AssertionError(
            "new-write and retained-stale counts must partition extra open facts"
        )
    if result["active_graph_correct"] != float(
        result["graded_active_world_correctness"] == 1.0
    ):
        raise AssertionError(
            "graded active-world endpoint must be exact iff binary endpoint is exact"
        )
    if result["open_memory_correct"] != float(
        result["graded_open_memory_correctness"] == 1.0
    ):
        raise AssertionError(
            "graded open-memory endpoint must be exact iff binary endpoint is exact"
        )
    return result


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
    *, horizon: int, recovery_window: int = 3,
    unrelated_collateral_by_step: Sequence[float] | None = None,
) -> dict[str, float]:
    """Evaluate a real ordered rollout; independent cases are not accepted."""
    lengths = {
        len(predicted_states), len(reference_states), len(base_states),
        len(protected_ids_by_step),
    }
    if lengths != {horizon}:
        raise ValueError("rollout inputs must be one ordered sequence at the frozen horizon")
    if unrelated_collateral_by_step is None:
        unrelated_collateral_by_step = [0.0] * horizon
    if len(unrelated_collateral_by_step) != horizon:
        raise ValueError("unrelated collateral must align with the frozen horizon")
    per_step = [
        graph_error_counts(predicted, reference, base, protected)
        for predicted, reference, base, protected in zip(
            predicted_states, reference_states, base_states,
            protected_ids_by_step, strict=True,
        )
    ]
    if recovery_window <= 0:
        raise ValueError("recovery window must be positive")
    final = per_step[-1]
    protected_collateral = [
        float(row["collateral_violation"] > 0.0) for row in per_step
    ]
    unrelated_collateral = [
        float(value > 0.0) for value in unrelated_collateral_by_step
    ]
    joint_collateral = [
        max(protected_value, unrelated_value)
        for protected_value, unrelated_value in zip(
            protected_collateral, unrelated_collateral, strict=True,
        )
    ]
    active = np.asarray([
        row["active_graph_correct"] for row in per_step
    ], dtype=np.float64)
    error_steps = np.flatnonzero(active == 0.0)
    first_error = int(error_steps[0]) if len(error_steps) else None
    first_recovery = None
    if first_error is not None:
        recovered = np.flatnonzero(active[first_error + 1:] == 1.0)
        if len(recovered):
            first_recovery = first_error + 1 + int(recovered[0])
    recovery_eligible = float(first_error is not None)
    recovered_within_window = float(
        first_recovery is not None
        and first_recovery - first_error <= recovery_window
    )
    result = {
        "mean_active_graph_correctness": float(active.mean()),
        "final_active_graph_correctness": final["active_graph_correct"],
        "mean_graded_active_world_correctness": float(np.mean([
            row["graded_active_world_correctness"] for row in per_step
        ])),
        "final_graded_active_world_correctness": final[
            "graded_active_world_correctness"
        ],
        "mean_graded_open_memory_correctness": float(np.mean([
            row["graded_open_memory_correctness"] for row in per_step
        ])),
        "final_graded_open_memory_correctness": final[
            "graded_open_memory_correctness"
        ],
        "mean_open_memory_correctness": float(np.mean([
            row["open_memory_correct"] for row in per_step
        ])),
        "final_open_memory_correctness": final["open_memory_correct"],
        "mean_history_exactness": float(np.mean([
            row["history_exact"] for row in per_step
        ])),
        "final_history_exactness": final["history_exact"],
        # Compatibility aliases for reports produced under M1-v1.
        "mean_post_graph_correctness": float(np.mean([
            row["post_graph_correct"] for row in per_step
        ])),
        "final_post_graph_correctness": final["post_graph_correct"],
        "terminal_extra_open_fact_error_per_100_decisions": (
            100.0 * final["extra_open_fact_error"] / horizon
        ),
        "terminal_missing_open_fact_error_per_100_decisions": (
            100.0 * final["missing_open_fact_error"] / horizon
        ),
        "terminal_new_incorrect_open_fact_write_per_100_decisions": (
            100.0 * final["new_incorrect_open_fact_write"] / horizon
        ),
        "terminal_retained_stale_open_fact_per_100_decisions": (
            100.0 * final["retained_stale_open_fact"] / horizon
        ),
        # Compatibility aliases.  Formal D-045 reports label these as aliases
        # and use the explicit terminal/AUC names below.
        "memory_contamination_per_100": (
            100.0 * final["extra_open_fact_error"] / horizon
        ),
        "missing_open_facts_per_100": (
            100.0 * final["missing_open_fact_error"] / horizon
        ),
        "false_birth_growth_per_100": 100.0 * final["false_birth_growth"] / horizon,
        # The registered collateral construct is the union of protected-state
        # and evidence-scope-external mutations. Components remain visible so
        # neither route can hide behind the aggregate.
        "collateral_violation_per_100": (
            100.0 * sum(joint_collateral) / horizon
        ),
        "protected_collateral_violation_per_100": (
            100.0 * sum(protected_collateral) / horizon
        ),
        "unrelated_collateral_violation_per_100": (
            100.0 * sum(unrelated_collateral) / horizon
        ),
        "active_node_state_error_per_100": (
            100.0 * final["active_node_state_symmetric_difference"] / horizon
        ),
        "active_edge_state_error_per_100": (
            100.0 * final["active_edge_state_symmetric_difference"] / horizon
        ),
        "open_evidence_attachment_error_per_100": (
            100.0
            * final["open_evidence_attachment_symmetric_difference"]
            / horizon
        ),
        "open_memory_node_error_per_100": (
            100.0 * final["open_memory_node_symmetric_difference"] / horizon
        ),
        "open_memory_edge_error_per_100": (
            100.0 * final["open_memory_edge_symmetric_difference"] / horizon
        ),
        "final_active_reference_node_count": final[
            "active_reference_node_count"
        ],
        "final_active_reference_edge_count": final[
            "active_reference_edge_count"
        ],
        "final_active_reference_record_count": final[
            "active_reference_record_count"
        ],
        "final_active_record_union_count": final["active_record_union_count"],
        "final_open_memory_reference_record_count": final[
            "open_memory_reference_record_count"
        ],
        "final_open_memory_record_union_count": final[
            "open_memory_record_union_count"
        ],
        "final_open_memory_reference_evidence_attachment_count": final[
            "open_memory_reference_evidence_attachment_count"
        ],
        "mean_extra_open_fact_error": float(np.mean([
            row["extra_open_fact_error"] for row in per_step
        ])),
        "mean_missing_open_fact_error": float(np.mean([
            row["missing_open_fact_error"] for row in per_step
        ])),
        "mean_memory_contamination": float(np.mean([
            row["extra_open_fact_error"] for row in per_step
        ])),
        "extra_open_fact_error_auc_per_100_decisions": 100.0 * sum(
            row["extra_open_fact_error"] for row in per_step
        ) / horizon,
        "missing_open_fact_error_auc_per_100_decisions": 100.0 * sum(
            row["missing_open_fact_error"] for row in per_step
        ) / horizon,
        "open_fact_error_auc_per_100_decisions": 100.0 * sum(
            row["extra_open_fact_error"] + row["missing_open_fact_error"]
            for row in per_step
        ) / horizon,
        "new_incorrect_open_fact_write_auc_per_100_decisions": 100.0 * sum(
            row["new_incorrect_open_fact_write"] for row in per_step
        ) / horizon,
        "retained_stale_open_fact_auc_per_100_decisions": 100.0 * sum(
            row["retained_stale_open_fact"] for row in per_step
        ) / horizon,
        "false_birth_growth_auc_per_100_decisions": 100.0 * sum(
            row["false_birth_growth"] for row in per_step
        ) / horizon,
        "missing_open_entity_auc_per_100_decisions": 100.0 * sum(
            row["missing_open_entities"] for row in per_step
        ) / horizon,
        "memory_contamination_auc_per_100_decisions": 100.0 * sum(
            row["extra_open_fact_error"] for row in per_step
        ) / horizon,
        "any_first_error_recovery_eligible": recovery_eligible,
        "any_first_error_recovered_within_window": recovered_within_window,
        "unresolved_active_error": float(final["active_graph_correct"] == 0.0),
        "first_active_error_step": (
            float(first_error) if first_error is not None else -1.0
        ),
        "any_first_error_time_to_recovery": (
            float(first_recovery - first_error)
            if first_recovery is not None and first_error is not None else -1.0
        ),
        # Compatibility aliases.  Causal M1-v2 aggregation no longer uses
        # these generic first-error fields as its registered recovery metric.
        "recovery_eligible": recovery_eligible,
        "recovered_within_window": recovered_within_window,
        "time_to_first_recovery": (
            float(first_recovery - first_error)
            if first_recovery is not None and first_error is not None else -1.0
        ),
    }
    return result


def paired_stratified_bootstrap(
    rows: Sequence[Mapping[str, Any]], method_a: str, method_b: str,
    metric: str, *, higher_is_better: bool, resamples: int = 10_000,
    confidence: float = 0.95, minimum_effect: float = 0.0,
    seed: int = 260_906,
) -> dict[str, float]:
    """Bootstrap A-vs-B improvements without breaking paired groups.

    ``minimum_effect`` is the registered improvement threshold under the null,
    not a shift applied to the reported effect or confidence interval. This
    supports superiority, meaningful-effect, and non-inferiority checks with
    the same paired resampling.
    """
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
        "minimum_effect": float(minimum_effect),
        "one_sided_p_at_or_below_minimum": float(
            (1 + np.sum(samples <= float(minimum_effect))) / (resamples + 1)
        ),
        # Compatibility alias for old reports. It is meaningful only with the
        # default zero threshold.
        "one_sided_p_nonpositive": float(
            (1 + np.sum(samples <= 0.0)) / (resamples + 1)
        ),
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


def endpoint_viability_assessment(
    rows: Sequence[Mapping[str, Any]], *, expected_groups: int,
    exact_metric: str = "final_active_graph_correctness",
    graded_metric: str = "final_graded_active_world_correctness",
    support_metric: str = "final_graded_open_memory_correctness",
    burden_metric: str = "open_fact_error_auc_per_100_decisions",
    minimum_effect: float = 0.03, planning_effect: float = 0.06,
    burden_minimum_effect: float = 2.0,
    burden_planning_effect: float = 4.0,
    z_one_sided_alpha: float = 1.959963984540054,
    z_power: float = 0.8416212335729143,
    minimum_test_groups: int = 200,
) -> dict[str, Any]:
    """Apply the pre-registered train-only endpoint switch and power rules.

    Rows are averaged first within a complete paired group, so seeds and the
    two siblings never become fake independent samples. The endpoint choice
    depends only on whether paired differences are observable, never on which
    method wins or the sign of its effect.
    """
    if not rows or expected_groups <= 1:
        raise ValueError("endpoint assessment needs multiple paired groups")
    if not 0.0 < minimum_effect < planning_effect <= 1.0:
        raise ValueError("endpoint effect thresholds must be ordered in (0, 1]")
    if not 0.0 < burden_minimum_effect < burden_planning_effect:
        raise ValueError("burden effect thresholds must be positive and ordered")
    required_methods = {"A", "C", "E", "F"}
    grouped: dict[str, dict[str, dict[str, list[float]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    for row in rows:
        group = str(row["paired_group_id"])
        method = str(row["method"])
        if method not in required_methods:
            continue
        metrics = row["metrics"]
        for name in (
            exact_metric, graded_metric, support_metric, burden_metric,
            "active_node_state_error_per_100",
            "final_active_reference_record_count",
        ):
            grouped[group][method][name].append(float(metrics[name]))
    if len(grouped) != expected_groups:
        raise ValueError(
            f"expected {expected_groups} complete paired groups, got {len(grouped)}"
        )
    group_means: dict[str, dict[str, dict[str, float]]] = {}
    for group, methods in grouped.items():
        if set(methods) != required_methods:
            raise ValueError(f"paired group {group} lacks A/C/E/F rows")
        group_means[group] = {
            method: {
                metric: float(np.mean(values))
                for metric, values in metrics.items()
            }
            for method, metrics in methods.items()
        }
    oracle_failures = [
        group for group, methods in group_means.items()
        if methods["F"][exact_metric] != 1.0
        or methods["F"][graded_metric] != 1.0
        or methods["F"][support_metric] != 1.0
        or methods["F"][burden_metric] != 0.0
        or methods["F"]["active_node_state_error_per_100"] != 0.0
    ]
    minimum_nonzero_groups = int(math.ceil(minimum_effect * expected_groups))

    def contrast(
        metric: str, baseline: str, *, higher_is_better: bool,
        null_minimum_effect: float, planned_effect: float,
    ) -> dict[str, Any]:
        differences = np.asarray([
            (
                methods["A"][metric] - methods[baseline][metric]
                if higher_is_better
                else methods[baseline][metric] - methods["A"][metric]
            )
            for _, methods in sorted(group_means.items())
        ], dtype=np.float64)
        standard_deviation = float(np.std(differences, ddof=1))
        nonzero = int(np.count_nonzero(np.abs(differences) > 1e-12))
        nondegenerate = bool(
            standard_deviation > 0.0 and nonzero >= minimum_nonzero_groups
        )
        detectable_effect = float(
            null_minimum_effect
            + (z_one_sided_alpha + z_power)
            * standard_deviation / math.sqrt(expected_groups)
        )
        required = int(math.ceil((
            (z_one_sided_alpha + z_power) * standard_deviation
            / (planned_effect - null_minimum_effect)
        ) ** 2))
        required = max(minimum_test_groups, required)
        required = int(math.ceil(required / 10.0) * 10)
        return {
            "baseline": baseline,
            "paired_groups": expected_groups,
            "mean_effect": float(np.mean(differences)),
            "paired_group_standard_deviation": standard_deviation,
            "nonzero_paired_groups": nonzero,
            "minimum_nonzero_paired_groups": minimum_nonzero_groups,
            "nondegenerate": nondegenerate,
            "higher_is_better": higher_is_better,
            "null_minimum_effect": float(null_minimum_effect),
            "planning_effect": float(planned_effect),
            "detectable_true_effect_at_registered_power": detectable_effect,
            "required_test_groups_for_planning_effect": required,
        }

    by_metric = {}
    for metric in (exact_metric, graded_metric, support_metric, burden_metric):
        is_burden = metric == burden_metric
        by_metric[metric] = {
            f"A_vs_{baseline}": contrast(
                metric, baseline,
                higher_is_better=not is_burden,
                null_minimum_effect=(
                    burden_minimum_effect if is_burden else minimum_effect
                ),
                planned_effect=(
                    burden_planning_effect if is_burden else planning_effect
                ),
            )
            for baseline in ("C", "E")
        }
    exact_ok = all(
        value["nondegenerate"] for value in by_metric[exact_metric].values()
    )
    graded_ok = all(
        value["nondegenerate"] for value in by_metric[graded_metric].values()
    )
    support_ok = all(
        value["nondegenerate"] for value in by_metric[support_metric].values()
    )
    burden_ok = all(
        value["nondegenerate"] for value in by_metric[burden_metric].values()
    )
    if oracle_failures:
        disposition = "abort_oracle_integrity_failure"
        selected_metric = None
    elif not support_ok:
        disposition = "stop_open_memory_support_endpoint_not_viable"
        selected_metric = None
    elif not burden_ok:
        disposition = "stop_open_fact_burden_endpoint_not_viable"
        selected_metric = None
    elif exact_ok:
        disposition = "retain_exact_endpoint"
        selected_metric = exact_metric
    elif graded_ok:
        disposition = "switch_once_to_graded_endpoint"
        selected_metric = graded_metric
    else:
        disposition = "stop_endpoint_not_viable_new_decision_required"
        selected_metric = None
    selected_test_groups = None
    if selected_metric is not None:
        selected_test_groups = max(
            value["required_test_groups_for_planning_effect"]
            for metric in (selected_metric, support_metric, burden_metric)
            for value in by_metric[metric].values()
        )
    reference_counts = np.asarray([
        methods["F"]["final_active_reference_record_count"]
        for methods in group_means.values()
    ], dtype=np.float64)
    return {
        "disposition": disposition,
        "selected_metric": selected_metric,
        "required_support_metric": support_metric,
        "required_burden_metric": burden_metric,
        "oracle_integrity_pass": not oracle_failures,
        "oracle_failure_groups": sorted(oracle_failures),
        "minimum_effect": float(minimum_effect),
        "planning_effect": float(planning_effect),
        "burden_minimum_effect": float(burden_minimum_effect),
        "burden_planning_effect": float(burden_planning_effect),
        "one_sided_alpha_per_primary_contrast": 0.025,
        "target_power": 0.8,
        "by_metric": by_metric,
        "selected_test_groups": selected_test_groups,
        "reference_record_count": {
            "minimum": float(reference_counts.min()),
            "mean": float(reference_counts.mean()),
            "median": float(np.median(reference_counts)),
            "maximum": float(reference_counts.max()),
        },
        "winner_or_effect_sign_used_for_switch": False,
    }
