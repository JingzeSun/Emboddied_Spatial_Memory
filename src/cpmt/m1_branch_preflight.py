"""Train-only engineering checks; no model selection or scientific score gate."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from copy import deepcopy


POLICIES = ("noop", "prefer_merge", "prefer_retract", "prefer_relink",
            "prefer_split", "prefer_birth", "fixed_random")
GROUPS = tuple(i * 999 // 15 for i in range(16))  # Fixed coverage of train 0..999.


def fixed_plan():
    return {
        "schema_version": "cpmt-train-branch-preflight-v1",
        "split": "train", "group_indices": list(GROUPS),
        "policies": list(POLICIES), "horizon": 20, "siblings": 2,
        "selection_seed": 260909, "candidate_budget": 16,
        "selection_input": "static_preflight_and_template_and_index_only",
        "preferred_template_unavailable": "select_noop_and_record",
        "execution_illegal": "keep_current_world_and_record",
        "construction_failure": "retain_snapshot_fail_gate_no_sample_replacement",
        "pass_requires": "all_fixed_groups_policies_siblings_complete_without_engineering_failure",
        "model_selection": False, "validation_access": False, "test_access": False,
        "scientific_acceptance_gate_changed": False,
        "coverage_claim": "bounded_train_engineering_check_not_all_reachable_states",
    }


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_audit(audit, group):
    require(group in GROUPS, "group is outside the fixed train engineering set")
    require(audit["paired_group_id"] == f"rollout-pair:train:{group:06d}",
            "non-train or unexpected paired group")
    require(audit["sibling_index"] in (0, 1), "invalid sibling")
    require(len(audit["steps"]) == 20, "incomplete 20-step audit")
    for step in audit["steps"]:
        require(step["online"]["split"] == "train", "non-train online row")


def choose_candidate(candidates, policy, *, group, sibling, step):
    """Deliberately cannot inspect reference/future scores or executed worlds."""
    require(policy in POLICIES, "unknown engineering policy")
    eligible = sorted((c for c in candidates if c["static_preflight_pass"]),
                      key=lambda c: int(c["candidate_index"]))
    require(bool(eligible), "no static-preflight-admissible candidate")
    if policy == "fixed_random":
        key = f"260909:{group}:{sibling}:{step}".encode()
        index = int.from_bytes(hashlib.sha256(key).digest()[:8], "big") % len(eligible)
        return int(eligible[index]["candidate_index"]), False
    template = "NOOP" if policy == "noop" else policy.removeprefix("prefer_").upper()
    choices = [c for c in eligible if c["template"] == template]
    unavailable = not choices
    if not choices:
        choices = [c for c in eligible if c["template"] == "NOOP"]
    require(bool(choices), "admissible NOOP fallback is missing")
    return int(choices[0]["candidate_index"]), unavailable


def run_branch(audit, group, policy, *, materialize, scope, validate_graph, sink, proposal_context=None, allow_unavailable=False):
    """Run the production materializer on evolving memory; persist each step."""
    validate_audit(audit, group)
    current = deepcopy(audit["initial_world"])
    rows = []
    templates = Counter()
    unavailable = 0
    for step_index, stored in enumerate(audit["steps"]):
        context = {"group": group, "sibling": audit["sibling_index"],
                   "policy": policy, "step_index": step_index,
                   "base_world": deepcopy(current), "event": stored["event_spec"]}
        try:
            before = json.dumps(current, sort_keys=True)
            validate_graph(current)
            materialized = materialize(audit, current, step_index)
            candidates = materialized["executed_candidates"]
            require(len(candidates) == 16, "candidate budget is not K=16")
            require([c["candidate_index"] for c in candidates] == list(range(16)),
                    "candidate indices are not a complete ordered K=16")
            require(json.dumps(current, sort_keys=True) == before, "base world mutated")
            require(all(c["base_graph_hash"] == current["graph_hash"] for c in candidates),
                    "candidates do not share immutable base")
            event = stored["event_spec"]
            evidence_scope = scope(current, event, ranks=3)
            availability = {}
            if proposal_context is not None:
                proposal = proposal_context(current, event)
                availability["distinct_merge_pairs"] = len({tuple(sorted(pair)) for pair in proposal["merge_pairs"]})
                if not allow_unavailable:
                    require(availability["distinct_merge_pairs"] == 2, "MERGE pair coverage is incomplete")
                if event["proposal_observation"]["unrelated_context_active"]:
                    availability["c11_unrelated_candidates"] = sum(
                        node.get("valid_to") is None
                        and node["lifecycle"] in {"candidate", "confirmed"}
                        and node["node_id"] not in evidence_scope
                        and node["node_id"] != event["protected_id"]
                        and node["node_id"] not in proposal["bind_targets"]
                        for node in current["nodes"])
                    if not allow_unavailable:
                        require(availability["c11_unrelated_candidates"] > 0, "C11 scope complement is empty")
            reordered = deepcopy(current)
            reordered["edges"].reverse()
            require(evidence_scope == scope(reordered, event, ranks=3), "scope depends on edge order")
            selection_view = [{k: c[k] for k in ("candidate_index", "template", "static_preflight_pass")}
                              for c in candidates]
            selected_index, missing = choose_candidate(
                selection_view, policy, group=group, sibling=audit["sibling_index"], step=step_index)
            selected = candidates[selected_index]
            context["candidates"] = candidates
            base_hash = current["graph_hash"]
            if selected["legal"]:
                require(selected["post_graph"] is not None, "legal candidate has no post world")
                current = deepcopy(selected["post_graph"])
            validate_graph(current)
            unavailable += int(missing)
            templates[selected["template"]] += 1
            row = {"group": group, "sibling": audit["sibling_index"], "policy": policy,
                   "step_index": step_index, "base_graph_hash": base_hash,
                   "post_graph_hash": current["graph_hash"], "selected_index": selected_index,
                   "selected_template": selected["template"], "selected_legal": selected["legal"],
                   "preferred_template_unavailable": missing,
                   "proposal_availability": availability,
                   "scope_ids": sorted(evidence_scope),
                   "static_admissible_count": sum(c["static_preflight_pass"] for c in candidates),
                   "legal_count": sum(c["legal"] for c in candidates),
                   "candidate_failures": [{k: c[k] for k in ("candidate_index", "template", "legal", "failure")}
                                          for c in candidates if not c["legal"]]}
            if allow_unavailable:
                row["unavailable_slots"] = [{"candidate_index": c["candidate_index"],
                    "template": c["template"], "reason": c["failure"]["message"]}
                    for c in candidates if c.get("slot_status") == "unavailable"]
                for candidate in candidates:
                    if candidate.get("slot_status") == "unavailable":
                        require(not candidate["static_preflight_pass"] and not candidate["legal"]
                                and candidate["post_graph"] is None and candidate["execution_attempted"] is False,
                                "unavailable slot acquired a world or became selectable")
            sink({"kind": "step", **row})
            rows.append(row)
        except Exception as error:
            sink({"kind": "failure", **context, "error_type": type(error).__name__,
                  "error_message": str(error), "completed_steps": len(rows)})
            raise
    return {"group": group, "sibling": audit["sibling_index"], "policy": policy,
            "completed_steps": len(rows), "selected_templates": dict(templates),
            "preferred_template_unavailable": unavailable,
            "executor_quarantined": sum(not r["selected_legal"] for r in rows),
            "minimum_c11_unrelated_candidates": min(
                (r["proposal_availability"]["c11_unrelated_candidates"] for r in rows
                 if "c11_unrelated_candidates" in r["proposal_availability"]), default=None),
            "final_graph_hash": current["graph_hash"]}


def summarize(groups):
    require(sorted(r["group"] for r in groups) == list(GROUPS), "incomplete/duplicate preflight groups")
    failures = [r["group"] for r in groups if r["status"] != "pass"]
    expected = {(g, s, p) for g in GROUPS for s in (0, 1) for p in POLICIES}
    rows = [r for g in groups for r in g.get("branches", [])]
    observed = [(r["group"], r["sibling"], r["policy"]) for r in rows]
    complete = len(observed) == len(expected) and set(observed) == expected
    return {"pass": not failures and complete and all(r["completed_steps"] == 20 for r in rows),
            "failed_groups": failures, "complete_branch_matrix": complete,
            "expected_branches": len(expected), "completed_branches": len(rows),
            "completed_decisions": sum(r["completed_steps"] for r in rows),
            "expected_decisions": len(expected) * 20}
