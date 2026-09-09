"""Generate frozen S5 data or evaluate saved models, in separate server stages.

No training function is called. Validation indices 4..203 are fixed before read.
Paired 20-step trajectories, selected-model fingerprints and each completed unit
are indivisible. See D-050 and HARD_CONDITION_EXPERIMENT.md for interpretation.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import datetime
import gzip
import io
import json
import multiprocessing as mp
import platform
from pathlib import Path
import sys
import time
import traceback

import numpy as np
import torch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from cpmt.dev_learning import masked_candidate_probabilities
from cpmt.executor import validate_graph
from cpmt.m1_af_rollout import causal_rollout_metrics, rollout_learning_arrays_from_audits, selection_error_decomposition
from cpmt.m1_protocol import load_and_validate, load_and_validate_endpoint_probe, protocol_sha256
from cpmt.m1_rollout import generate_m1_paired_rollout_split
from cpmt.m1_s5_confirmation import (complete_unit, group_indices, load_confirmation_plan,
    reserve_trial, validate_confirmation_test_marker, validate_sequence_rows, verify_unit)
from cpmt.m1_s5_training import read_json, require, validate_artifact, write_json
from cpmt.run_provenance import arrays_sha256, capture_run_provenance, file_sha256, source_tree_sha256
from run_m1_s5_train import load_saved_model
from run_m1_af_scaled import _paired_causal_statistics


def write_gzip(path, value):
    with path.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
        with io.TextIOWrapper(compressed, encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, sort_keys=True, separators=(",", ":"))


def read_gzip(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def make_group(task):
    # Spawn-safe: only paths, integers and small JSON binding cross processes.
    config_path, output_path, index, binding = task
    torch.set_num_threads(1)
    hard = load_and_validate(Path(config_path))
    destination = Path(output_path) / f"group_{index:06d}"
    unit_binding = {**binding, "group_index": index}
    def produce(staging):
        began = time.monotonic()
        _, audits, summary = generate_m1_paired_rollout_split(hard, "validation", paired_groups=1, start_group_index=index)
        arrays = rollout_learning_arrays_from_audits(hard, audits, future_hash_bins=32)
        arrays["group"][:] = index
        np.savez(staging / "learning.npz", **arrays)
        write_gzip(staging / "audits.json.gz", audits)
        coverage = defaultdict(lambda: {"decisions": 0, "covered": 0})
        for audit in audits:
            validate_graph(audit["initial_world"])
            for step in audit["steps"]:
                ref = step["executed_candidates"][step["reference_program_index"]]
                row = coverage[step["scenario_family"]]
                row["decisions"] += 1
                row["covered"] += int(ref["legal"] and ref["static_preflight_pass"])
                for candidate in step["executed_candidates"]:
                    if candidate["legal"]:
                        validate_graph(candidate["post_graph"])
        write_json(staging / "summary.json", {"generator_summary": summary, "coverage": dict(coverage),
            "arrays_digest": arrays_sha256(arrays), "learning_rows": len(arrays["y"]),
            "invariant_violations": 0, "wall_seconds": time.monotonic() - began})
    marker = complete_unit(destination, unit_binding, produce)
    return index, marker


def generate_data(root, output, plan, training, provenance):
    binding = {"plan_sha256": protocol_sha256(plan), "source_tree_sha256": source_tree_sha256(root),
               "training_export_sha256": plan["training_export_sha256"], "split": "validation"}
    manifest_path = output / "data_manifest.json"
    if manifest_path.exists():
        previous = read_json(manifest_path)
        require(previous["binding"] == binding, "data generation binding changed")
        provenance = previous["generation_provenance"]
        if previous["status"] == "complete":
            require(set(previous["groups"]) == {str(i) for i in group_indices(plan)}, "data group set mismatch")
            for index in group_indices(plan):
                marker = verify_unit(output / f"group_{index:06d}", {**binding, "group_index": index})
                require(marker == previous["groups"][str(index)], "completed data changed")
            require(previous["gates"]["candidate_coverage"] and previous["gates"]["teacher_health"], "completed data failed gates; review required")
            print("S5_DATA_OK paired_groups=200 sequences=400 decisions=8000 reused=true test_access=false", flush=True)
            return previous
    manifest = {"schema_version": "cpmt-s5-data-v1", "status": "running", "binding": binding,
        "plan": plan, "generation_provenance": provenance, "groups": {}, "test_access": False,
        "validation_trial_consumed": False, "model_evaluation_performed": False}
    write_json(manifest_path, manifest)
    tasks = [(str(root / "configs/m1_hard_condition.json"), str(output), index, binding) for index in group_indices(plan)]
    with mp.get_context("spawn").Pool(plan["data"]["generation_workers"]) as pool:
        for index, marker in pool.imap_unordered(make_group, tasks):
            manifest["groups"][str(index)] = marker
            write_json(manifest_path, manifest)
            print(f"S5_DATA_GROUP_OK index={index} completed={len(manifest['groups'])}/200", flush=True)
    family = defaultdict(lambda: {"decisions": 0, "covered": 0, "teacher_rows": 0, "teacher_correct": 0.0})
    for index in group_indices(plan):
        summary = read_json(output / f"group_{index:06d}" / "summary.json")
        for name, row in summary["coverage"].items():
            family[name]["decisions"] += row["decisions"]
            family[name]["covered"] += row["covered"]
        for name, row in summary["generator_summary"]["teacher_reference_agreement_by_family"].items():
            family[name]["teacher_rows"] += row["support"]
            family[name]["teacher_correct"] += row["support"] * (row["reference_agreement"] or 0.0)
    hard = load_and_validate(root / "configs/m1_hard_condition.json")
    require(set(family) == set(hard["data"]["scenario_families"]), "missing registered family")
    health = hard["energy"]["teacher_health_gate"]
    coverage = sum(r["covered"] for r in family.values()) / sum(r["decisions"] for r in family.values())
    agreement = sum(r["teacher_correct"] for r in family.values()) / sum(r["teacher_rows"] for r in family.values())
    gates = {"candidate_coverage": coverage >= hard["candidates"]["coverage_gate_overall"] and all(
        r["covered"] / r["decisions"] >= hard["candidates"]["coverage_gate_each_family"] for r in family.values()),
        "teacher_health": agreement >= health["reference_agreement_overall_minimum"] and all(
        r["teacher_rows"] and r["teacher_correct"] / r["teacher_rows"] >= health["reference_agreement_each_family_minimum"] for r in family.values()),
        "invariant_violations": 0}
    manifest.update(status="complete", family_health=dict(family), candidate_coverage=coverage,
        teacher_reference_agreement=agreement, gates=gates, paired_groups=200, sequences=400, decisions=8000)
    write_json(manifest_path, manifest)
    # Failed gates never select replacement groups. Keep the complete data for review.
    require(gates["candidate_coverage"] and gates["teacher_health"], "data gate failed; preserve all groups for review")
    print("S5_DATA_OK paired_groups=200 sequences=400 decisions=8000 test_access=false", flush=True)
    return manifest


class AuditCollection:
    """Repeatable disk iterator avoids keeping every full candidate world in RAM."""
    def __init__(self, data_dir, indices):
        self.data_dir, self.indices = data_dir, indices

    def __iter__(self):
        for index in self.indices:
            audits = read_gzip(self.data_dir / f"group_{index:06d}" / "audits.json.gz")
            require(len(audits) == 2 and {a["sibling_index"] for a in audits} == {0, 1}, "broken sibling pair")
            require(all(a["paired_group_id"] == f"rollout-pair:validation:{index:06d}" and len(a["steps"]) == 20 for a in audits), "wrong audit identity")
            yield from audits


def load_data(data_dir, plan):
    manifest = read_json(data_dir / "data_manifest.json")
    require(manifest["schema_version"] == "cpmt-s5-data-v1" and manifest["status"] == "complete", "data incomplete")
    require(manifest["plan"] == plan and manifest["binding"]["plan_sha256"] == protocol_sha256(plan), "wrong data plan")
    require(manifest["gates"]["candidate_coverage"] and manifest["gates"]["teacher_health"] and manifest["gates"]["invariant_violations"] == 0, "data gates failed")
    indices = group_indices(plan)
    require(set(manifest["groups"]) == {str(i) for i in indices}, "data group set mismatch")
    pieces = []
    for index in indices:
        directory = data_dir / f"group_{index:06d}"
        marker = verify_unit(directory, {**manifest["binding"], "group_index": index})
        require(marker == manifest["groups"][str(index)], "data shard changed")
        with np.load(directory / "learning.npz", allow_pickle=False) as source:
            arrays = {k: source[k] for k in source.files}
        require(arrays_sha256(arrays) == read_json(directory / "summary.json")["arrays_digest"], "learning arrays changed")
        require(set(arrays["group"].tolist()) == {index}, "learning row group mismatch")
        pieces.append(arrays)
    arrays = {key: np.concatenate([piece[key] for piece in pieces]) for key in pieces[0]}
    return manifest, arrays, AuditCollection(data_dir, indices)


def evaluation_config(hard, plan, saved=None):
    config = {**(saved or {}), "device": "cpu", "cpu_threads": 1,
        "commit_probability": plan["evaluation"]["commit_probability"],
        "margin_threshold": plan["evaluation"]["margin_threshold"],
        "mechanism_diagnostic_slices": hard["evaluation"]["mechanism_diagnostic_slices"],
        "current_evidence_scope_ranks": hard["candidates"]["proposal_retrieval"]["enumerated_ranks"]}

    # Only the evaluation plan may authorize the new policy, never a checkpoint.
    config.pop("candidate_availability_policy", None)
    if "candidate_availability_policy" in plan["evaluation"]:
        from cpmt.m1_candidate_policy import validate_candidate_policy
        config["candidate_availability_policy"] = validate_candidate_policy(
            plan["evaluation"]["candidate_availability_policy"])
    return config


def teacher_forced(model, arrays):
    # Fixed reference-history diagnostic only, never used for model selection.
    keep = ~arrays["recovery"].astype(bool)
    data = {k: v[keep] for k, v in arrays.items()}
    probabilities = []
    with torch.no_grad():
        for start in range(0, len(data["y"]), 64):
            logits = model(torch.as_tensor(data["x"][start:start+64]))
            mask = torch.as_tensor(data["candidate_static_preflight_pass"][start:start+64], dtype=torch.bool)
            probabilities.append(masked_candidate_probabilities(logits, mask).numpy())
    p = np.concatenate(probabilities)
    require(bool(np.isfinite(p).all()), "non-finite model probabilities")
    diagnostics = selection_error_decomposition(p, data)
    teacher = data["pstar"].argmax(1)
    diagnostics.update(teacher_error=float(np.mean(teacher != data["y"])),
        amortization_disagreement_with_teacher=float(np.mean(p.argmax(1) != teacher)),
        reference_candidate_unavailable=float(np.mean(~data["candidate_static_preflight_pass"][np.arange(len(teacher)), data["y"]].astype(bool))),
        reference_history_only=True, model_selection_performed=False)
    return diagnostics


def evaluate_one(directory, binding, model, audits, config, indices, *, oracle=False, observable=False, forced=None):
    def produce(staging):
        began = time.monotonic()
        with gzip.open(staging / "execution_audit.jsonl.gz", "wt", encoding="utf-8") as stream:
            def sink(materialized, choice, current):
                validate_graph(current)
                # Candidate failures and actual online payload are retained. The
                # offline teacher energies/future branches remain in data audits.
                record = {"sequence_id": materialized["audit_sequence_id"],
                    "sibling_index": materialized["audit_sibling_index"],
                    "online": materialized["online"], "choice": choice,
                    "candidates": [{k: v for k, v in c.items() if k != "post_graph"} for c in materialized["executed_candidates"]]}
                stream.write(json.dumps(record, sort_keys=True) + "\n")
            aggregate, sequences = causal_rollout_metrics(model, audits, config, oracle=oracle,
                observable_oracle=observable, audit_sink=sink)
        validate_sequence_rows(sequences, indices)
        aggregate.update(seed=binding["seed"], method=binding["method"], wall_seconds=time.monotonic()-began,
            peak_vram_bytes=0, device="cpu", torch_threads=1, invariant_violations=0)
        write_json(staging / "result.json", {"schema_version": "cpmt-s5-causal-unit-v1", "binding": binding,
            "aggregate": aggregate, "sequences": sequences, "teacher_forced": forced,
            "config": config, "test_access": False, "model_selection_performed": False})
    complete_unit(directory, binding, produce)
    result = read_json(directory / "result.json")
    require(result["binding"] == binding, "causal payload binding mismatch")
    validate_sequence_rows(result["sequences"], indices)
    return result


def evaluate(root, data_dir, training_dir, output, plan, training, provenance):
    # Validate all saved artifacts before opening validation data. Old model
    # provenance must equal the accepted training export, not the new source hash.
    for key, row in training["models"].items():
        artifact = validate_artifact(training_dir / "models" / key, training["binding"], row["component"])
        require(artifact["model_sha256"] == row["model_sha256"] and artifact["training"] == row["training"], "saved model drift")
    header = read_json(data_dir / "data_manifest.json")
    require(header["status"] == "complete" and header["plan"] == plan, "confirmation data not ready")
    require(header["gates"]["candidate_coverage"] and header["gates"]["teacher_health"]
            and header["gates"]["invariant_violations"] == 0, "data gate failed; review required")
    binding = {"plan_sha256": protocol_sha256(plan), "training_export_sha256": plan["training_export_sha256"],
        "data_manifest_sha256": file_sha256(data_dir / "data_manifest.json"),
        "evaluation_source_sha256": source_tree_sha256(root), "device": "cpu", "torch_threads": 1,
        "runtime": {"torch_version": str(torch.__version__), "numpy_version": str(np.__version__),
                    "python_version": platform.python_version(), "hostname": platform.node(), "machine": platform.machine()}}
    consumption = reserve_trial(data_dir / "confirmation_consumption.json", binding, output)
    trial_path = output / "validation_trial.json"
    if trial_path.exists():
        trial = read_json(trial_path)
        require(trial["binding"] == binding, "validation trial binding changed; no new selection/retry")
        provenance = trial["evaluation_provenance"]
    else:
        trial = {"schema_version": "cpmt-s5-trial-v1", "binding": binding, "status": "started",
            "validation_trial_consumed": True, "test_access": False, "evaluation_provenance": provenance}
        write_json(trial_path, trial)
    data_manifest, arrays, audits = load_data(data_dir, plan)
    torch.set_num_threads(1)
    indices = group_indices(plan)
    config = evaluation_config(load_and_validate(root / "configs/m1_hard_condition.json"), plan)
    oracle_results = {}
    for method, observable in [("oracle_candidate_program", False), ("observable_information_oracle", True)]:
        unit_binding = {**binding, "architecture": None, "seed": None, "method": method}
        result = evaluate_one(output / method, unit_binding, None, audits, config, indices, oracle=not observable, observable=observable)
        oracle_results[method] = result
        if not observable:
            requirements = load_and_validate_endpoint_probe(root / "configs/m1_endpoint_viability_probe.json", load_and_validate(root / "configs/m1_hard_condition.json"))["oracle_integrity_gate"]["all_F_groups_require"]
            require(all(row["metrics"][k] == value for row in result["sequences"] for k, value in requirements.items()), "F oracle integrity failed; stop for engineering review")
        print("S5_ORACLE_OK method="+method, flush=True)
    hard = load_and_validate(root / "configs/m1_hard_condition.json")
    overlay = load_and_validate_endpoint_probe(root / "configs/m1_endpoint_viability_probe.json", hard)
    arms = {}
    for architecture in training["plan"]["arms"]:
        methods = defaultdict(list)
        for method in plan["evaluation"]["methods"]:
            for seed in plan["evaluation"]["seeds"]:
                key = f"{architecture}/seed_{seed}/{method}";row = training["models"][key]
                unit_binding = {**binding, "architecture": architecture, "seed": seed, "method": method, "model_sha256": row["model_sha256"]}
                directory = output / "causal" / key
                if directory.exists():
                    verify_unit(directory, unit_binding)
                    result = read_json(directory / "result.json")
                    require(result["binding"] == unit_binding, "causal payload changed")
                    validate_sequence_rows(result["sequences"], indices)
                else:
                    require(not directory.with_name("."+directory.name+".incomplete").exists(), "partial evaluation requires review")
                    model, payload = load_saved_model(training_dir / "models" / key, training["binding"], row["component"], torch.device("cpu"))
                    config = evaluation_config(hard, plan, payload["config"])
                    result = evaluate_one(directory, unit_binding, model, audits, config, indices,
                        forced=teacher_forced(model, arrays))
                    del model, payload
                methods[method].append(result)
                print(f"S5_CAUSAL_OK architecture={architecture} method={method} seed={seed} decisions=8000", flush=True)
        statistics = _paired_causal_statistics(methods, hard, overlay)
        require(statistics["paired_groups"] == 200 and statistics["sequence_seed_rows"] == 2000, "incomplete paired statistics")
        arms[architecture] = {"paired_statistics": statistics,
            "per_method_seed": {method: [{"aggregate": p["aggregate"], "teacher_forced": p["teacher_forced"]} for p in payloads] for method, payloads in methods.items()}}
    report = {"schema_version": "cpmt-s5-confirmation-report-v1", "status": "complete", "plan": plan,
        "binding": binding, "training_provenance": training["training_provenance"], "evaluation_provenance": provenance,
        "data_manifest": data_manifest, "arms": arms, "oracle_aggregates": {k:v["aggregate"] for k,v in oracle_results.items()},
        "validation_consumption": consumption,
        "architecture_roles": {k: hard["architecture_evaluation"][k] for k in ("primary", "secondary", "between_architecture_selection")},
        "formal_run": False, "test_generated": False, "test_access": False, "causal_complete": True,
        "validation_trial_consumed": True, "model_selection_performed": False,
        "future_use_policy": training["future_use_policy"], "frozen_front_end_components": training["frozen_front_end_components"],
        "disposition": "review_S5_confirmation_under_registered_stop_rule_no_automatic_test_release",
        "cost_scope": plan["evaluation"]["resource_measurement"], "latency_scope": plan["evaluation"]["latency_scope"]}
    write_json(output / "s5_confirmation_report.json", report)
    trial["status"] = "complete";trial["report_sha256"] = file_sha256(output / "s5_confirmation_report.json")
    write_json(trial_path, trial)
    print("S5_CONFIRMATION_OK arms=2 learned_models=50 paired_groups=200 test_access=false", flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("generate", "evaluate"))
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--training-dir", type=Path)
    parser.add_argument("--test-marker", required=True, type=Path)
    args = parser.parse_args()
    hard = load_and_validate(PROJECT / "configs/m1_hard_condition.json")
    overlay = load_and_validate_endpoint_probe(PROJECT / "configs/m1_endpoint_viability_probe.json", hard)
    plan, training = load_confirmation_plan(PROJECT, hard, overlay)
    validate_confirmation_test_marker(read_json(args.test_marker), PROJECT, plan)
    provenance = capture_run_provenance(PROJECT, component="m1_s5_"+args.phase, entrypoint=Path(__file__))
    require(provenance["git_dirty"] is False, "confirmation checkout must be clean")
    require(args.phase != "evaluate" or args.training_dir is not None, "saved training directory required")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    import fcntl
    with (args.out_dir / "runner.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(not list(args.out_dir.glob("failure_*.json")), "previous failure requires review; no automatic restart")
        try:
            if args.phase == "generate":
                require(args.data_dir.resolve() == args.out_dir.resolve(), "generation output must equal data-dir")
                generate_data(PROJECT, args.data_dir, plan, training, provenance)
            else:
                require(args.out_dir.resolve() != args.data_dir.resolve(), "evaluation must not write into generated data")
                evaluate(PROJECT, args.data_dir, args.training_dir, args.out_dir, plan, training, provenance)
        except BaseException:
            stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            write_json(args.out_dir / f"failure_{stamp}.json", {"phase":args.phase,"traceback":traceback.format_exc(),"test_access":False})
            raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
