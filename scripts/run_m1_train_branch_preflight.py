"""Bounded train engineering gate before corrected probe/budget; CPU only."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from cpmt.m1_branch_preflight import GROUPS, POLICIES, fixed_plan, require, run_branch, summarize
from cpmt.run_provenance import capture_run_provenance, source_tree_sha256


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def file_digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def generation_context(error):
    """Retain only graph/event locals from known generator frames."""
    frames = []
    tb = error.__traceback__
    while tb:
        frame = tb.tb_frame
        if frame.f_code.co_name in {"_generate_sequence", "_proposal_context", "_prepare_fixed_candidates"}:
            values = {}
            for key in ("graph", "current", "event", "step_index"):
                value = frame.f_locals.get(key)
                if value is not None:
                    values[key] = value
            frames.append({"function": frame.f_code.co_name, "line": tb.tb_lineno, "values": values})
        tb = tb.tb_next
    return frames


def run_group(task):
    config_path, data_dir, output, group = task
    directory = Path(output) / f"group_{group:06d}"
    directory.mkdir()  # No implicit retry or replacement of an attempted group.
    began = time.monotonic()
    result = {"group": group, "status": "failed", "branches": []}
    try:
        import numpy as np
        import torch
        torch.set_num_threads(1)
        from cpmt.m1_af_rollout import rollout_learning_arrays_from_audits
        from cpmt.m1_protocol import load_and_validate
        from cpmt.m1_rollout import (generate_m1_paired_rollout_split,
                                    materialize_rollout_step, _current_online_evidence_scope, _proposal_context)
        from cpmt.run_provenance import arrays_sha256
        from cpmt.executor import validate_graph

        hard = load_and_validate(Path(config_path))
        _, audits, _ = generate_m1_paired_rollout_split(
            hard, "train", paired_groups=1, start_group_index=group)
        require(sorted(a["sibling_index"] for a in audits) == [0, 1], "incomplete siblings")
        arrays = rollout_learning_arrays_from_audits(hard, audits, future_hash_bins=32)
        shard = Path(data_dir) / "shards" / f"train_{group:06d}.npz"
        with np.load(shard, allow_pickle=False) as source:
            accepted = {k: source[k] for k in source.files}
        require(arrays_sha256(arrays) == arrays_sha256(accepted), "reconstructed audit differs from accepted train shard")
        result["reconstructed_arrays_digest"] = arrays_sha256(arrays)
        del arrays, accepted
        with gzip.open(directory / "reference_audits.json.gz", "wt", encoding="utf-8") as stream:
            json.dump(audits, stream, sort_keys=True)
        with gzip.open(directory / "trace.jsonl.gz", "wt", encoding="utf-8") as stream:
            def sink(record):
                stream.write(json.dumps(record, sort_keys=True) + "\n")
                stream.flush()
                if record["kind"] == "failure":
                    write_json(directory / "failure_snapshot.json", record)
            for audit in sorted(audits, key=lambda a: a["sibling_index"]):
                for policy in POLICIES:
                    result["branches"].append(run_branch(
                        audit, group, policy, materialize=materialize_rollout_step,
                        scope=_current_online_evidence_scope, validate_graph=validate_graph, sink=sink,
                        proposal_context=_proposal_context))
                    print(f"BRANCH_OK group={group} sibling={audit['sibling_index']} policy={policy} steps=20", flush=True)
        result["status"] = "pass"
    except Exception as error:
        result["failure"] = {"type": type(error).__name__, "message": str(error),
                             "traceback": traceback.format_exc()}
        write_json(directory / "failure.json", result["failure"])
        context = generation_context(error)
        if context:
            write_json(directory / "generation_failure_context.json", context)
    result["wall_seconds"] = time.monotonic() - began
    write_json(directory / "result.json", result)
    result["files"] = {p.name: file_digest(p) for p in sorted(directory.iterdir()) if p.is_file()}
    return result


def check_generation(root, marker_path, hard):
    """Consume old generation evidence without claiming it tested new code."""
    from cpmt.m1_protocol import protocol_sha256, validate_current_rollout_protocol
    validate_current_rollout_protocol(hard)
    marker = read_json(marker_path)
    require(marker["schema_version"] == "cpmt-scope-rebuild-train-v1" and marker["exit_code"] == 0,
            "corrected train generation has not passed")
    binding = marker["binding"]
    require(binding["split"] == "train" and binding["groups"] == 1000 and binding["future_hash_bins"] == 32,
            "unexpected train generation scope")
    require(binding["protocol_sha256"] == protocol_sha256(hard), "generation protocol mismatch")
    manifest = marker["manifest"]
    require(manifest["teacher_health_gate"]["pass"] is True, "train health has not passed")
    require(marker["validation_generated"] is False and marker["test_access"] is False,
            "generation access boundary mismatch")
    old_commit = marker["attempt"]["provenance"]["git_commit"]
    require(isinstance(old_commit, str) and len(old_commit) == 40
            and all(c in "0123456789abcdef" for c in old_commit), "invalid generator commit")
    # All pre-existing production modules remain identical. The sole added src
    # module is this engineering checker, never imported by the data generator.
    diff = subprocess.run(["git", "diff", "--name-status", old_commit, "HEAD", "--", "src",
                           "scripts/generate_m1_parallel.py", "configs/m1_hard_condition_v7.json"],
                          cwd=root, text=True, capture_output=True, check=True).stdout.splitlines()
    require(all(line == "A\tsrc/cpmt/m1_branch_preflight.py" for line in diff),
            "production generator/executor changed since accepted train; review before reuse")
    data_dir = marker_path.parent.resolve()
    require(Path(marker["arrays_path"]).resolve() == data_dir / "train.npz", "train path mismatch")
    names = ["train.npz", "train.manifest.json"] + [f"shards/train_{g:06d}.npz" for g in GROUPS]
    for name in names:
        require(file_digest(data_dir / name) == marker["file_sha256"][name], "accepted input changed: " + name)
    require(read_json(data_dir / "train.manifest.json") == manifest, "generation manifest changed")
    return marker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generation-marker", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4, choices=(1, 2, 4))
    args = parser.parse_args()
    require(os.name == "posix", "real branch preflight runs on the Linux server, not the local workstation")
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[name] = "1"
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    from cpmt.m1_protocol import load_and_validate
    config_path = PROJECT / "configs/m1_hard_condition_v7.json"
    hard = load_and_validate(config_path)
    provenance = capture_run_provenance(PROJECT, component="train_branch_preflight", entrypoint=Path(__file__))
    require(provenance["git_dirty"] is False, "clean committed checkout required")
    generation = check_generation(PROJECT, args.generation_marker, hard)
    source = source_tree_sha256(PROJECT, roots=("src", "scripts", "configs", "tests"))
    binding = {"plan": fixed_plan(), "generation_marker_sha256": file_digest(args.generation_marker),
               "train_arrays_digest": generation["arrays_digest"],
               "source_and_tests_sha256": source, "generation_commit": generation["attempt"]["provenance"]["git_commit"]}
    require(not args.output.exists(), "existing preflight output requires review; no automatic retry")
    args.output.mkdir(parents=True)
    write_json(args.output / "attempt.json", {"binding": binding, "provenance": provenance, "workers": args.workers})
    began = time.monotonic()
    tasks = [(str(config_path), str(args.generation_marker.parent.resolve()), str(args.output.resolve()), g) for g in GROUPS]
    try:
        results = []
        with mp.get_context("spawn").Pool(processes=args.workers) as pool:
            for result in pool.imap_unordered(run_group, tasks, chunksize=1):
                results.append(result)
                print(f"PREFLIGHT_GROUP_DONE group={result['group']} status={result['status']} completed={len(results)}/{len(GROUPS)}", flush=True)
        results.sort(key=lambda r: r["group"])
        gate = summarize(results)
        require(source == source_tree_sha256(PROJECT, roots=("src", "scripts", "configs", "tests")),
                "source/tests changed during preflight")
        report = {"schema_version": "cpmt-train-branch-preflight-report-v1", "binding": binding,
                  "provenance": provenance, "groups": results, "gate": gate,
                  "wall_seconds": time.monotonic() - began, "workers": args.workers,
                  "validation_access": False, "test_access": False, "training_performed": False,
                  "model_selection_performed": False, "scientific_acceptance_gate_changed": False}
        write_json(args.output / "report.json", report)
        print("TRAIN_BRANCH_PREFLIGHT_RESULT=" + json.dumps(gate, sort_keys=True), flush=True)
        return 0 if gate["pass"] else 1
    except Exception as error:
        write_json(args.output / "failure.json", {"type": type(error).__name__, "message": str(error),
                                                   "traceback": traceback.format_exc()})
        raise


if __name__ == "__main__":
    raise SystemExit(main())
