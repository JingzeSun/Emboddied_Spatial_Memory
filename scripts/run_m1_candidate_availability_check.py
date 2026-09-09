"""Experimental train-only slot handling; never authorizes a formal budget."""
from __future__ import annotations

import argparse
from collections import Counter
from functools import partial
import gzip
import json
import multiprocessing as mp
import os
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from cpmt.m1_branch_preflight import GROUPS, POLICIES, require, run_branch, summarize
from cpmt.run_provenance import capture_run_provenance, source_tree_sha256
from run_m1_train_branch_preflight import file_digest, read_json, write_json

REPORT = ROOT / "results/m1_v7_d051_train_branch_preflight.json"
REPORT_SHA = "ea058b7468517f59027c740adbc73540c6c97357d323fc7ba43eb8e6cdd16449"
OLD_RUN = Path("/root/autodl-tmp/cpmt_outputs/m1-v7-d051-branch-preflight-a488142c3548/run")


def check_reference_step(step):
    """Actual strict and experimental generator paths on a saved reference base."""
    from cpmt.m1_rollout import generate_fixed_candidates, _execute_candidates
    graph, event = step["online"]["prior_world"], step["event_spec"]
    strict, evidence, _ = generate_fixed_candidates(graph, event)
    optional, optional_evidence, availability = generate_fixed_candidates(graph, event, allow_unavailable=True)
    require(strict == step["online"]["candidate_programs"], "strict reference programs changed")
    require(optional == strict and optional_evidence == evidence, "experimental reference programs/evidence changed")
    require(availability["unavailable_slots"] == 0, "reference has an unavailable slot")
    require(_execute_candidates(graph, strict, evidence) == step["executed_candidates"],
            "reference executions changed")


def run_group(task):
    group, output, expected_sha = task
    from cpmt.executor import validate_graph
    from cpmt.m1_rollout import materialize_rollout_step, _current_online_evidence_scope, _proposal_context
    directory = Path(output) / f"group_{group:06d}"
    directory.mkdir()
    source = OLD_RUN / directory.name / "reference_audits.json.gz"
    result = {"group": group, "status": "failed", "branches": [], "failures": [],
              "reference_steps_verified": 0, "recovery_steps_verified": 0,
              "unavailable_reasons": {}, "c11_zero_target_steps": 0}
    try:
        require(file_digest(source) == expected_sha, "saved audit hash mismatch")
        with gzip.open(source, "rt", encoding="utf-8") as stream:
            audits = json.load(stream)
        require(sorted(a["sibling_index"] for a in audits) == [0, 1], "missing sibling")
        for audit in audits:
            require(audit["paired_group_id"] == f"rollout-pair:train:{group:06d}", "wrong audit group")
            for step in audit["steps"]:
                check_reference_step(step)
                result["reference_steps_verified"] += 1
            require(len(audit["recovery_examples"]) == 1, "missing reference recovery example")
            for step in audit["recovery_examples"]:
                check_reference_step(step)
                result["recovery_steps_verified"] += 1
        require(result["reference_steps_verified"] == 40 and result["recovery_steps_verified"] == 2,
                "reference step count mismatch")
        for audit in sorted(audits, key=lambda a: a["sibling_index"]):
            for policy in POLICIES:
                stem = f"sibling_{audit['sibling_index']}_{policy}"
                counts = Counter()
                with gzip.open(directory / (stem + ".jsonl.gz"), "wt", encoding="utf-8") as stream:
                    def sink(record):
                        stream.write(json.dumps(record, sort_keys=True) + "\n")
                        stream.flush()
                        if record["kind"] == "failure":
                            write_json(directory / (stem + ".failure.json"), record)
                        else:
                            counts.update(r["reason"] for r in record["unavailable_slots"])
                            result["c11_zero_target_steps"] += int(
                                record["proposal_availability"].get("c11_unrelated_candidates") == 0)
                    try:
                        branch = run_branch(
                            audit, group, policy,
                            materialize=partial(materialize_rollout_step, allow_unavailable=True),
                            scope=_current_online_evidence_scope, validate_graph=validate_graph, sink=sink,
                            proposal_context=partial(_proposal_context, allow_unavailable=True),
                            allow_unavailable=True)
                        branch["unavailable_reasons"] = dict(counts)
                        result["branches"].append(branch)
                    except Exception as error:
                        result["failures"].append({"sibling": audit["sibling_index"], "policy": policy,
                            "error": str(error), "traceback": traceback.format_exc()})
                # Count even incomplete trajectories; never discard failure exposure.
                total = Counter(result["unavailable_reasons"])
                total.update(counts)
                result["unavailable_reasons"] = dict(total)
        if not result["failures"]:
            result["status"] = "pass"
    except Exception as error:
        result["failures"].append({"error": str(error), "traceback": traceback.format_exc()})
    write_json(directory / "result.json", result)
    result["files"] = {p.name: file_digest(p) for p in sorted(directory.iterdir()) if p.is_file()}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, choices=(1, 2, 4), default=4)
    args = parser.parse_args()
    require(os.name == "posix", "full matrix runs on the Linux server only")
    for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[key] = "1"
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    require(file_digest(REPORT) == REPORT_SHA, "original failure report changed")
    original = read_json(REPORT)
    require(original["test_access"] is False and original["validation_access"] is False, "wrong source boundary")
    require(original["report"]["gate"]["pass"] is False, "expected the preserved failed report")
    provenance = capture_run_provenance(ROOT, component="candidate_availability_experiment", entrypoint=Path(__file__))
    require(provenance["git_dirty"] is False, "clean committed checkout required")
    source = source_tree_sha256(ROOT, roots=("src", "scripts", "configs", "tests"))
    require(not args.output.exists(), "existing attempt requires review; no restart")
    tasks = []
    for row in original["report"]["groups"]:
        group = row["group"]
        expected = row["files"]["reference_audits.json.gz"]
        require(file_digest(OLD_RUN / f"group_{group:06d}" / "reference_audits.json.gz") == expected,
                "saved audit missing or changed")
        tasks.append((group, str(args.output), expected))
    require(sorted(t[0] for t in tasks) == list(GROUPS), "incomplete fixed source group set")
    args.output.mkdir(parents=True)
    write_json(args.output / "attempt.json", {"source_and_tests_sha256": source, "provenance": provenance,
        "source_report_sha256": REPORT_SHA, "groups": list(GROUPS), "policies": list(POLICIES),
        "mode": "experimental_explicit_unavailable_slots_v1", "formal_budget_authorized": False})
    began = time.monotonic()
    results = []
    with mp.get_context("spawn").Pool(args.workers) as pool:
        for row in pool.imap_unordered(run_group, tasks, chunksize=1):
            results.append(row)
            print(f"AVAILABILITY_GROUP group={row['group']} status={row['status']} branches={len(row['branches'])}/14", flush=True)
            for failure in row["failures"]:
                print("AVAILABILITY_FAILURE=" + json.dumps({"group": row["group"], **failure}), flush=True)
    results.sort(key=lambda r: r["group"])
    gate = summarize(results)
    require(source_tree_sha256(ROOT, roots=("src", "scripts", "configs", "tests")) == source,
            "source changed during check")
    failures = {}
    for path in sorted(args.output.rglob("*.failure.json")):
        failures[path.relative_to(args.output).as_posix()] = read_json(path)
    report = {"schema_version": "cpmt-candidate-availability-experiment-v1", "provenance": provenance,
        "source_and_tests_sha256": source, "source_report_sha256": REPORT_SHA, "gate": gate,
        "groups": results, "failure_snapshots": failures, "wall_seconds": time.monotonic() - began,
        "workers": args.workers, "validation_access": False, "test_access": False,
        "training_performed": False, "data_generated": False, "formal_budget_authorized": False,
        "reference_compatibility_scope": "saved_16_train_groups_not_all_1000",
        "reference_steps_verified": sum(r["reference_steps_verified"] for r in results),
        "recovery_steps_verified": sum(r["recovery_steps_verified"] for r in results)}
    write_json(args.output / "report.json", report)
    print("AVAILABILITY_RESULT=" + json.dumps(gate, sort_keys=True), flush=True)
    return 0 if gate["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
