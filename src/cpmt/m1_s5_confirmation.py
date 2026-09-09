"""Frozen S5 metadata and durable, non-selective confirmation units (D-050).

No tensor imports or dataset reads: heavy generation/evaluation lives in the
server runner. Original training binding and new evaluation binding are distinct.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable

from .m1_protocol import protocol_sha256
from .m1_s5_training import component_spec, load_plan, read_json, require, write_json
from .run_provenance import file_sha256, source_tree_sha256


def group_indices(plan: dict) -> list[int]:
    data = plan["data"]
    indices = list(range(data["start_group_index"], data["start_group_index"] + data["paired_groups"]))
    require(not set(indices) & set(data["excluded_historical_group_indices"]), "historical validation overlap")
    return indices


def load_confirmation_plan(root: Path, hard: dict, overlay: dict) -> tuple[dict, dict]:
    training_plan, registration = load_plan(root, hard, overlay)
    plan = read_json(root / "configs/m1_s5_confirmation_plan.json")
    require(plan["schema_version"] == "cpmt-m1-s5-confirmation-plan-v1", "wrong confirmation schema")
    require(plan["test_access"] is False and plan["formal_test_release"] is False, "test remains sealed")
    for key, value in (("training_plan_sha256", training_plan), ("source_protocol_sha256", hard),
                       ("probe_overlay_sha256", overlay), ("post_probe_registration_sha256", registration)):
        require(plan[key] == protocol_sha256(value), "confirmation contract mismatch: " + key)
    data, evaluation = plan["data"], plan["evaluation"]
    require(data["split"] == "validation" and group_indices(plan) == list(range(4, 204)), "confirmation range drift")
    require(data["excluded_historical_group_indices"] == [0, 1, 2, 3], "historical exclusion drift")
    require(data["paired_groups"] == registration["evaluation_plan"]["paired_groups"]["validation"] == 200,
            "confirmation size drift")
    require(data["siblings_per_group"] == 2 and data["horizon_decisions"] == 20 and data["future_hash_bins"] == 32,
            "paired horizon/encoding drift")
    require(data["generation_workers"] == 16, "generation scheduling drift")
    require(file_sha256(root / data["historical_evidence"]) == data["historical_evidence_sha256"],
            "historical evidence changed")
    require(evaluation["device"] == "cpu" and evaluation["torch_threads"] == 1, "evaluation device/thread drift")
    require(evaluation["scheduling"] == "serial_architecture_method_seed_no_training", "evaluation scheduling drift")
    require(evaluation["seeds"] == training_plan["seeds"], "confirmation seed drift")
    require(evaluation["methods"] == hard["training"]["pretest_budget_selection"]["student_selection_methods"],
            "confirmation method drift")
    require(evaluation["use_all_groups_once"] is True and evaluation["model_selection_performed"] is False
            and evaluation["test_access"] is False, "confirmation selection/access drift")
    require(evaluation["commit_probability"] == evaluation["margin_threshold"] == 0.0, "gate drift")
    require(evaluation["resamples"] == hard["evaluation"]["bootstrap"]["resamples"] == 10000
            and evaluation["confidence"] == 0.95 and evaluation["bootstrap_seed"] == 260906, "statistics drift")
    require(registration["evaluation_plan"]["semantic_metric"] == "final_active_graph_correctness"
            and registration["evaluation_plan"]["minimum_effects"] == [0.03, 0.03, 40.0], "endpoint drift")
    export_path = (root / plan["training_export"]).resolve()
    require(export_path.is_relative_to((root / "results").resolve()), "training export outside results")
    require(file_sha256(export_path) == plan["training_export_sha256"], "training export changed")
    exported = read_json(export_path)
    training = exported["training_manifest"]
    marker = exported["other_reports"]["training.ok.json"]
    raw = (json.dumps(training, indent=2, sort_keys=True) + "\n").encode()
    require(hashlib.sha256(raw).hexdigest() == marker["training_manifest_sha256"], "training completion hash mismatch")
    require(training["status"] == "complete" and marker["runner_exit_code"] == 0 and marker["models"] == 60,
            "training incomplete")
    require(training["plan"] == training_plan and training["post_probe_registration"] == registration,
            "training registration mismatch")
    require(all(training[k] is False for k in ("validation_arrays_read", "test_access", "model_selection_performed")),
            "training boundary mismatch")
    expected = {f"{a}/seed_{s}/{m}": component_spec(training_plan, a, s, m)
                for a in training_plan["arms"] for s in training_plan["seeds"]
                for m in ["outcome_scorer", *evaluation["methods"]]}
    require(set(training["models"]) == set(expected), "incomplete training model set")
    require(all(training["models"][k]["component"] == v for k, v in expected.items()), "model recipe drift")
    return plan, training


def validate_confirmation_test_marker(marker: dict, root: Path, plan: dict) -> None:
    require(marker["schema_version"] == "cpmt-s5-confirmation-tests-v1", "wrong confirmation full-test marker")
    require(marker["exit_code"] == marker["failures"] == marker["errors"] == marker["skipped"] == 0,
            "confirmation tests failed")
    require(marker["tests_run"] == marker["expected_tests"] and marker["tests_run"] > 234, "incomplete confirmation tests")
    require(marker["plan_sha256"] == protocol_sha256(plan), "test plan mismatch")
    require(marker["source_and_tests_sha256"] == source_tree_sha256(root, roots=("src", "scripts", "configs", "tests"))
            and marker["source_tree_unchanged"] is True, "confirmation tests do not cover this source")
    require(marker["validation_data_read"] is False and marker["test_access"] is False, "test access mismatch")


def verify_unit(path: Path, binding: dict) -> dict:
    marker = read_json(path / "complete.json")
    require(marker["schema_version"] == "cpmt-s5-unit-v1" and marker["binding"] == binding, "unit binding mismatch")
    require(marker["files"] and set(marker["files"]) == {p.name for p in path.iterdir() if p.name != "complete.json"},
            "unit file set mismatch")
    for name, digest in marker["files"].items():
        require(Path(name).name == name and file_sha256(path / name) == digest, "unit file hash mismatch")
    return marker


def reserve_trial(path: Path, binding: dict, output: Path) -> dict:
    """One data directory cannot silently start another confirmation output."""
    expected = {"schema_version": "cpmt-s5-consumption-v1", "binding": binding,
                "evaluation_output": str(output.resolve()), "validation_trial_consumed": True}
    try:
        with path.open("x", encoding="utf-8") as stream:
            json.dump(expected, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except FileExistsError:
        require(read_json(path) == expected, "validation already reserved by a different run")
    return expected


def complete_unit(path: Path, binding: dict, produce: Callable[[Path], None]) -> dict:
    """Atomic completion; preserve partial attempts and never silently repeat them."""
    if path.exists():
        return verify_unit(path, binding)
    staging = path.with_name("." + path.name + ".incomplete")
    require(not staging.exists(), "partial unit requires review: " + str(staging))
    staging.mkdir(parents=True)
    write_json(staging / "attempt.json", {"binding": binding})
    try:
        produce(staging)
        files = {p.name: file_sha256(p) for p in sorted(staging.iterdir()) if p.is_file()}
        write_json(staging / "complete.json", {"schema_version": "cpmt-s5-unit-v1", "binding": binding, "files": files})
        verify_unit(staging, binding)
        staging.rename(path)
    except BaseException as error:
        if staging.exists():
            write_json(staging / "failure.json", {"type": type(error).__name__, "message": str(error)})
        raise
    return verify_unit(path, binding)


def validate_sequence_rows(sequences: list[dict], indices: list[int], horizon: int = 20) -> None:
    expected = {(f"rollout-pair:validation:{g:06d}", s) for g in indices for s in (0, 1)}
    observed = [(str(r["metrics"]["paired_group_id"]), int(r["metrics"]["sibling_index"])) for r in sequences]
    require(len(observed) == len(expected) and set(observed) == expected, "incomplete/duplicate paired sequence rows")
    require(len({r["metrics"]["sequence_id"] for r in sequences}) == len(sequences), "duplicate sequence ids")
    for row in sequences:
        choices = row["choices"]
        require([c["step_index"] for c in choices] == list(range(horizon)), "incomplete trajectory")
        require(all(a["post_graph_hash"] == b["base_graph_hash"] for a, b in zip(choices, choices[1:])),
                "self-rollout state chain broken")
