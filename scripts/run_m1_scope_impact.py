#!/usr/bin/env python3
"""Read existing train audits; diagnose a proposed one-hop scope correction.

No production function is replaced. No candidates are executed, no models are
loaded, and no dataset is generated. Fixed-candidate posterior differences are
conditional diagnostics, not the result of regenerating a corrected dataset.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))


def expand_one_hop(graph, retrieved):
    """Expand against immutable retrieval seeds, including retrieved edge IDs."""
    seeds = frozenset(retrieved)
    selected = set(seeds)
    for edge in graph["edges"]:
        if edge.get("valid_to") is not None:
            continue
        ids = {str(edge[k]) for k in ("edge_id", "source", "target")}
        if seeds & ids:
            selected.update(ids)
    return selected


def diagnostic_scope(graph, event, ranks, rank):
    """Same retrieval as production; only the expansion is proposed to change."""
    observation = event["proposal_observation"]
    nodes = [str(n["node_id"]) for n in graph["nodes"] if n.get("valid_to") is None]
    edges = [str(e["edge_id"]) for e in graph["edges"] if e.get("valid_to") is None]
    places = [str(n["node_id"]) for n in graph["nodes"]
              if n.get("valid_to") is None and n["node_type"] == "place"]
    seeds = set(rank(nodes, observation["node_query"], event, kind="node")[:ranks])
    seeds.update(rank(edges, observation["edge_query"], event, kind="edge")[:ranks])
    seeds.update(rank(places, observation["place_query"], event, kind="place")[:ranks])
    for slot, query in enumerate(observation["merge_queries"]):
        seeds.update(rank(nodes, query, event, kind=f"merge-scope-{slot}")[:ranks])
    return expand_one_hop(graph, seeds)


def unrelated_pool(graph, event, scope, bind_targets):
    return [str(n["node_id"]) for n in graph["nodes"]
            if n.get("valid_to") is None and n["lifecycle"] in {"candidate", "confirmed"}
            and str(n["node_id"]) not in scope
            and str(n["node_id"]) != str(event["protected_id"])
            and str(n["node_id"]) not in set(bind_targets)]


def masked_probability(probabilities, mask):
    values = [float(p) if allowed else 0.0 for p, allowed in zip(probabilities, mask, strict=True)]
    total = sum(values)
    if total <= 0:
        raise ValueError("no admissible posterior mass")
    return [v / total for v in values]


def distribution_difference(before, after):
    return {"tv": sum(abs(a-b) for a, b in zip(before, after, strict=True)) / 2,
            "argmax_changed": max(range(len(before)), key=before.__getitem__) !=
                              max(range(len(after)), key=after.__getitem__)}


def inspect_step(step, hard, rollout):
    base = step["online"]["prior_world"]
    event = step["event_spec"]
    ranks = int(hard["candidates"]["proposal_retrieval"]["enumerated_ranks"])
    old = rollout._current_online_evidence_scope(base, event, ranks=ranks)
    if old != set(step["current_evidence_scope_ids"]):
        raise ValueError("cached scope does not match original production code")
    new = diagnostic_scope(base, event, ranks, rollout._rank_by_observation)
    if not new <= old:
        raise ValueError("one-hop scope unexpectedly exceeds original expansion")
    candidate_check = None
    if event["proposal_observation"]["unrelated_context_active"]:
        # _proposal_context only ranks existing identifiers; it does not execute.
        context = rollout._proposal_context(base, event)
        old_pool = unrelated_pool(base, event, old, context["bind_targets"])
        new_pool = unrelated_pool(base, event, new, context["bind_targets"])
        query = event["proposal_observation"]["unrelated_node_query"]
        ranked_old = rollout._rank_by_observation(old_pool, query, event, kind="unrelated-context")
        ranked_new = rollout._rank_by_observation(new_pool, query, event, kind="unrelated-context")
        if not ranked_old or ranked_old[0] != context["collateral_target"]:
            raise ValueError("original C11 target reconstruction mismatch")
        candidate_check = {"old_pool_count": len(old_pool), "new_pool_count": len(new_pool),
                           "old_target": ranked_old[0], "new_target": ranked_new[0] if ranked_new else None,
                           "target_changed": not ranked_new or ranked_new[0] != ranked_old[0]}
    weights = hard["energy"]["weights"]
    temperature = float(hard["energy"]["temperature"])
    energies = step["candidate_energies"]
    executions = step["executed_candidates"]
    changed = []
    corrected = []
    for i, (energy, execution) in enumerate(zip(energies, executions, strict=True)):
        post = execution["post_graph"]
        before = 0.0 if post is None else rollout._collateral_mutation(base, post, old)
        if abs(before - float(energy["collateral"])) > 1e-12:
            raise ValueError("cached collateral does not match original production code")
        after = before if old == new or post is None else rollout._collateral_mutation(base, post, new)
        item = dict(energy, collateral=after)
        if not item["masked"]:
            item["total"] = sum(float(weights[k]) * float(item[k]) for k in weights)
        corrected.append(item)
        if before != after:
            changed.append({"candidate_index": i, "old": before, "new": after,
                            "admissible": bool(execution["legal"] and execution["static_preflight_pass"])})
    original_p = rollout._teacher_posterior(energies, temperature)
    if any(abs(a-b) > 1e-12 for a,b in zip(original_p, step["teacher_posterior"], strict=True)):
        raise ValueError("cached posterior mismatch")
    new_p = rollout._teacher_posterior(corrected, temperature)
    mask = [bool(e["legal"] and e["static_preflight_pass"]) for e in executions]
    masked_old, masked_new = masked_probability(original_p, mask), masked_probability(new_p, mask)
    return {"step_index": step["step_index"], "family": step["scenario_family"],
            "old_scope_count": len(old), "new_scope_count": len(new),
            "removed_scope_ids": sorted(old-new), "c11": candidate_check,
            "collateral_changes": changed,
            "fixed_candidates_raw_posterior": distribution_difference(original_p, new_p),
            "fixed_candidates_shared_mask_posterior": distribution_difference(masked_old, masked_new)}


def summarize(rows):
    counts = Counter(rows=len(rows))
    for row in rows:
        counts["scope_changed_rows"] += bool(row["removed_scope_ids"])
        counts["c11_rows"] += row["c11"] is not None
        counts["c11_target_changed_rows"] += bool(row["c11"] and row["c11"]["target_changed"])
        counts["collateral_changed_rows"] += bool(row["collateral_changes"])
        counts["collateral_changed_candidates"] += len(row["collateral_changes"])
        diff = row["fixed_candidates_shared_mask_posterior"]
        counts["masked_posterior_changed_rows_tol_1e_12"] += diff["tv"] > 1e-12
        counts["masked_argmax_changed_rows"] += diff["argmax_changed"]
    return {**dict(counts), "masked_posterior_tv_max": max(
        (r["fixed_candidates_shared_mask_posterior"]["tv"] for r in rows), default=0.0)}


def run(out):
    from cpmt.m1_protocol import load_and_validate
    from cpmt.m1_s5_confirmation import complete_unit
    from cpmt.m1_s5_training import read_json, write_json, require
    from cpmt.run_provenance import capture_run_provenance, file_sha256, source_tree_sha256
    import cpmt.m1_rollout as rollout

    report_relative = "results/m1_v6_d050_train_scope_impact.json"
    status = subprocess.check_output(["git", "status", "--porcelain", "-z"], cwd=PROJECT).decode()
    require(all(x[3:] == report_relative for x in status.split("\0") if x), "unexpected checkout changes")
    changed = subprocess.check_output(["git", "diff", "--name-only", "d3a7ad34086dcdb60edebb3185d5af778d175af3",
                                      "HEAD", "--", "src", "scripts", "configs"], cwd=PROJECT, text=True).splitlines()
    require(set(changed) <= {"scripts/export_run_report.py", "scripts/run_m1_scope_impact.py"},
            "original scientific implementation changed")
    probe_path = PROJECT / "results/m1_v6_d047_endpoint_probe.json"
    require(file_sha256(probe_path) == "d15831b42057f1591dacba8b27fa85f2d944761b29ead466d6de724a0750b058",
            "accepted probe export changed")
    probe = read_json(probe_path)["endpoint_probe"]
    original = Path(probe["causal_result_directory"]).parent
    require(read_json(original / "endpoint_probe_report.json") == probe, "server probe differs from accepted export")
    groups = [g for g in range(1000) if int.from_bytes(hashlib.sha256(
        f"rollout-pair:train:{g:06d}".encode()).digest()[:8], "big") % 5 == 0]
    require(len(groups) == probe["inner_dev_paired_groups"] == 201, "inner-dev group mismatch")
    audit_dir = original / "audits"
    expected = {f"train_inner_dev_{g:06d}.json.gz" for g in groups}
    require({p.name for p in audit_dir.glob("*.json.gz")} == expected, "missing/unexpected cached train audits; no regeneration")
    print("SCOPE_IMPACT_INPUT_OK groups=201 existing_train_audits_only=true", flush=True)
    hard = load_and_validate(PROJECT / "configs/m1_hard_condition.json")
    require(hard["candidates"]["proposal_retrieval"]["enumerated_ranks"] == 3, "C11 hardcoded scope rank differs")
    provenance = capture_run_provenance(PROJECT, component="m1_train_scope_impact", entrypoint=Path(__file__))
    binding = {"schema_version": "cpmt-train-scope-impact-v1", "probe_sha256": file_sha256(probe_path),
               "hard_sha256": file_sha256(PROJECT / "configs/m1_hard_condition.json"),
               "source_tree_sha256": provenance["source_tree_sha256"], "groups": groups,
               "audit_directory": str(audit_dir), "definition": "immutable_retrieved_ids_one_edge_expansion",
               "validation_read": False, "test_access": False}
    all_rows = []
    inputs = {}
    started = time.monotonic()
    for offset, group in enumerate(groups):
        path = audit_dir / f"train_inner_dev_{group:06d}.json.gz"
        digest = file_sha256(path)
        inputs[path.name] = digest
        unit_binding = {"run": binding, "group": group, "audit_sha256": digest}
        unit = out / f"group_{group:06d}"
        def produce(staging):
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                payload = json.load(stream)
            require(payload["schema_version"] == "cpmt-m1-inner-dev-audit-v1" and payload["group"] == group,
                    "cached audit identity mismatch")
            audits = payload["audits"]
            require(len(audits) == 2 and {a["sibling_index"] for a in audits} == {0, 1}, "incomplete paired audit")
            rows = []
            for audit in audits:
                require(audit["split"] == "train" and audit["paired_group_id"] == f"rollout-pair:train:{group:06d}",
                        "non-train or wrong group audit")
                require([s["step_index"] for s in audit["steps"]] == list(range(20)), "incomplete trajectory")
                for kind, steps in (("reference", audit["steps"]), ("recovery", audit["recovery_examples"])):
                    for step in steps:
                        rows.append(dict(inspect_step(step, hard, rollout), group=group,
                                         sibling=audit["sibling_index"], kind=kind))
            require(file_sha256(path) == digest, "input audit changed during inspection")
            write_json(staging / "result.json", {"rows": rows, "summary": summarize(rows)})
        complete_unit(unit, unit_binding, produce)
        result = read_json(unit / "result.json")
        all_rows.extend(result["rows"])
        print(f"SCOPE_IMPACT_GROUP_OK group={group} completed={offset+1}/201 "
              f"scope_changed={result['summary']['scope_changed_rows']} "
              f"c11_target_changed={result['summary']['c11_target_changed_rows']}", flush=True)
    require(source_tree_sha256(PROJECT) == binding["source_tree_sha256"], "source changed during diagnosis")
    report = {"schema_version": "cpmt-train-scope-impact-v1", "binding": binding,
              "diagnostic_provenance": provenance, "input_audit_sha256": inputs,
              "summary": summarize(all_rows), "groups": 201, "rows": all_rows,
              "by_kind": {k: summarize([r for r in all_rows if r["kind"] == k]) for k in ("reference", "recovery")},
              "by_family": {k: summarize([r for r in all_rows if r["family"] == k])
                            for k in sorted({r["family"] for r in all_rows})},
              "wall_seconds": time.monotonic()-started, "validation_read": False, "test_access": False,
              "model_evaluation_performed": False, "candidates_executed": False,
              "limitations": ["Only 201 cached train/inner-dev groups, not all 1000 training groups.",
                              "Fixed original candidates and post-worlds; changed C11 targets require regeneration to measure full impact.",
                              "No new model self-rollout or revised formal metric; zero change cannot authorize reuse automatically."]}
    report_path = out / "diagnostic_report.json"
    if report_path.exists():
        previous = read_json(report_path)
        require(previous["binding"] == binding and previous["input_audit_sha256"] == inputs
                and previous["rows"] == all_rows, "completed diagnostic changed; preserve report")
    else:
        write_json(report_path, report)
    print("SCOPE_IMPACT_COMPLETE " + json.dumps(report["summary"], sort_keys=True), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    if (args.out_dir / "failure.json").exists():
        raise RuntimeError("previous attempt requires review; no automatic restart")
    try:
        run(args.out_dir)
    except BaseException as error:
        from cpmt.m1_s5_training import write_json
        write_json(args.out_dir / "failure.json", {"type": type(error).__name__, "message": str(error),
                                                  "traceback": traceback.format_exc()})
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
