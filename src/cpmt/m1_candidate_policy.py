"""D-054 explicit-slot evaluation policy and post-selection diagnostics.

This module does not generate training data, choose actions, or release test.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Mapping, Any


POLICY = {
    "schema_version": "cpmt-m1-candidate-availability-policy-v1",
    "decision": "D-054",
    "policy_id": "shared_explicit_candidate_slots_v1",
    "candidate_slots": 16,
    "reference_generation": "strict_k16_unchanged",
    "online_selection": "shared_availability_and_static_preflight_mask",
    "empty_slot_execution": "not_attempted_no_post_world",
    "canonical_duplicates": "retain_first_mark_later_slots_unavailable",
    "c11_missing_target": "record_keep_full_trajectory_and_all_original_metric_denominators",
    "reference_reachability": "post_selection_semantic_exact_over_selectable_legal_candidates",
    "formal_test_release": False,
}


def validate_candidate_policy(policy: Mapping[str, Any]) -> dict:
    if dict(policy) != POLICY:
        raise ValueError("candidate availability policy differs from D-054")
    return deepcopy(POLICY)


def step_availability(materialized, event, reference, *, is_c11):
    """Offline diagnostics called only after the selected world is committed."""
    from .m1_metrics import graph_error_counts
    from .m1_rollout import _collateral_mutation, _current_online_evidence_scope
    candidates = materialized["executed_candidates"]
    programs = materialized["online"]["candidate_programs"]
    base = materialized["online"]["prior_world"]
    if len(candidates) != 16 or len(programs) != 16:
        raise ValueError("registered evaluation requires exactly 16 slots")
    unavailable = [c for c in candidates if c.get("slot_status") == "unavailable"]
    for candidate in unavailable:
        if (candidate["static_preflight_pass"] or candidate["legal"]
                or candidate["post_graph"] is not None or candidate.get("execution_attempted") is not False):
            raise ValueError("unavailable slot became selectable or acquired a post-world")
    real = [c for c in candidates if c.get("slot_status") != "unavailable"]
    selectable = [c for c in real if c["legal"] and c["static_preflight_pass"]]
    reasons = Counter(c["failure"]["message"] for c in unavailable)
    reachable = any(graph_error_counts(c["post_graph"], reference, base, [event["protected_id"]])[
        "active_graph_correct"] for c in selectable)
    c11_target = c11_contrast = None
    if is_c11:
        c11_target = reasons["c11_scope_complement_empty"] == 0
        scope = _current_online_evidence_scope(base, event, ranks=3)
        c11_contrast = any(
            "bind-with-collateral" in p["transaction_id"]
            and c["legal"] and c["static_preflight_pass"]
            and _collateral_mutation(base, c["post_graph"], scope)
            for p, c in zip(programs, candidates, strict=True))
    return {
        "unavailable_slot_count": len(unavailable), "unavailable_reasons": dict(reasons),
        "constructed_candidate_count": len(real),
        "executor_illegal_candidate_count": sum(not c["legal"] for c in real),
        "static_rejected_constructed_count": sum(not c["static_preflight_pass"] for c in real),
        "selectable_legal_candidate_count": len(selectable),
        "exact_reference_reachable": bool(reachable),
        "c11_event": bool(is_c11), "c11_scope_target_available": c11_target,
        "c11_legal_collateral_contrast_available": c11_contrast,
    }


def summarize_availability(choices):
    """Keep all decisions; C11-only ratios are descriptive, never safety gates."""
    rows = [c["candidate_availability"] for c in choices]
    count = len(rows)
    reasons = Counter()
    for row in rows:
        reasons.update(row["unavailable_reasons"])
    c11 = [r for r in rows if r["c11_event"]]
    return {
        "policy_id": POLICY["policy_id"], "decisions": count,
        "unavailable_slots": sum(r["unavailable_slot_count"] for r in rows),
        "decisions_with_unavailable_slots": sum(r["unavailable_slot_count"] > 0 for r in rows),
        "unavailable_reasons": dict(reasons),
        "constructed_candidates": sum(r["constructed_candidate_count"] for r in rows),
        "executor_illegal_candidates": sum(r["executor_illegal_candidate_count"] for r in rows),
        "decisions_without_exact_reference_reachable": sum(not r["exact_reference_reachable"] for r in rows),
        "exact_reference_unreachable_rate": (sum(not r["exact_reference_reachable"] for r in rows) / count
                                             if count else None),
        "c11_events": len(c11),
        "c11_missing_scope_target_events": sum(not r["c11_scope_target_available"] for r in c11),
        "c11_missing_legal_contrast_events": sum(not r["c11_legal_collateral_contrast_available"] for r in c11),
        "c11_legal_contrast_availability_rate": (sum(r["c11_legal_collateral_contrast_available"] for r in c11) / len(c11)
                                                if c11 else None),
        "scientific_metric_denominators_changed": False,
    }
