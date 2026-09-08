"""Pure metadata contracts and durable artifacts for selected-budget S5 training.

This module does not import torch, train a model, or open validation/test arrays.
The recipe is bound to the already accepted budget exports; it is not a new
hyperparameter search. See D-049 and HARD_CONDITION_EXPERIMENT.md.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable

from .m1_protocol import protocol_sha256
from .m1_registration import load_registration
from .run_provenance import file_sha256, source_tree_sha256


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def load_plan(root: Path, hard: dict, overlay: dict) -> tuple[dict, dict]:
    registration = load_registration(root, hard, overlay)
    plan = read_json(root / "configs/m1_s5_training_plan.json")
    require(plan["schema_version"] == "cpmt-m1-s5-training-plan-v1", "wrong plan schema")
    require(plan["stage"] == "S5_train_only_preparation", "wrong training stage")
    require(all(plan[k] is False for k in
                ("formal_run", "validation_arrays_read", "test_access")), "held-out access forbidden")
    require(plan["post_probe_registration_sha256"] == protocol_sha256(registration),
            "plan registration mismatch")
    require(plan["training_population"] == "all_registered_train_groups_after_inner_dev_selection",
            "training population drift")
    require(plan["train_paired_groups"] == registration["evaluation_plan"]["paired_groups"]["train"] == 1000,
            "training group count drift")
    require(plan["main_label_fraction"] == hard["training"]["main_label_fraction"] == 0.1,
            "label budget drift")
    require(plan["label_policy"] == "reuse_existing_train_label_mask_without_resampling",
            "label policy drift")
    require(plan["seeds"] == hard["training"]["formal_seeds"], "seed drift")
    require(plan["device"] == "cuda" and plan["torch_threads"] == 8, "device/thread drift")
    require(plan["arm_execution"] == "sequential_no_architecture_selection", "arm scheduling drift")
    require(set(plan["arms"]) == set(hard["architecture_evaluation"]["registered"]),
            "missing or additional architecture")
    methods = set(hard["training"]["pretest_budget_selection"]["student_selection_methods"])
    for architecture, spec in plan["arms"].items():
        path = (root / spec["budget_report"]).resolve()
        require(path.is_relative_to((root / "results").resolve()), "budget path outside results")
        require(file_sha256(path) == spec["budget_export_sha256"], "budget export digest mismatch")
        exported = read_json(path)
        report = exported["budget_report"]
        marker = exported["other_reports"]["budget.ok.json"]
        acceptance = exported["other_reports"]["budget.acceptance.json"]
        raw = json.dumps(report, indent=2, sort_keys=True).encode("utf-8")
        require(hashlib.sha256(raw).hexdigest() == marker["report_sha256"], "accepted budget hash mismatch")
        require(acceptance["validated_marker"] == marker, "acceptance marker mismatch")
        require(report["architecture"] == marker["architecture"] == architecture, "budget architecture mismatch")
        require(report["post_probe_registration_sha256"] == plan["post_probe_registration_sha256"],
                "budget registration mismatch")
        require(report["input_arrays"]["train"]["arrays_digest"] == marker["train_arrays_digest"]
                == plan["train_arrays_digest"], "budget train digest mismatch")
        require(report["selected"] == spec["selected"], "selected budget changed")
        require(set(spec["selected"]["student_hyperparameters_by_method"]) == methods, "method set drift")
        require(all(report[k] is False for k in ("formal_run", "test_generated", "causal_complete")),
                "unexpected formal budget report")
        require(all(report["partition"][k] is False for k in
                    ("test_access", "validation_arrays_read", "validation_trial_consumed")),
                "budget held-out boundary mismatch")
    return plan, registration


def validate_test_marker(marker: dict, root: Path, plan: dict) -> None:
    require(marker["schema_version"] == "cpmt-d049-full-test-marker-v1", "wrong full-test marker")
    require(marker["exit_code"] == 0 and marker["failures"] == marker["errors"] == marker["skipped"] == 0,
            "full tests did not pass")
    require(marker["tests_run"] == marker["expected_tests"] and marker["tests_run"] > 221,
            "incomplete full test discovery")
    require(marker["plan_sha256"] == protocol_sha256(plan), "full-test plan mismatch")
    require(marker["registration_sha256"] == plan["post_probe_registration_sha256"],
            "full-test registration mismatch")
    require(marker["source_tree_unchanged"] is True, "source changed during full tests")
    require(marker["source_and_tests_sha256"] == source_tree_sha256(
        root, roots=("src", "scripts", "configs", "tests")), "full-test scientific tree mismatch")
    require(marker["test_access"] is False and marker["formal_validation_arrays_read"] is False,
            "full-test access boundary mismatch")


def component_spec(plan: dict, architecture: str, seed: int, method: str) -> dict:
    require(architecture in plan["arms"] and seed in plan["seeds"], "unregistered arm or seed")
    selected = plan["arms"][architecture]["selected"]
    if method == "outcome_scorer":
        settings = {"learning_rate": selected["outcome_scorer_learning_rate"],
                    "scorer_steps": selected["outcome_scorer_steps"]}
    else:
        require(method in selected["student_hyperparameters_by_method"], "unregistered learned method")
        settings = selected["student_hyperparameters_by_method"][method]
    return {"architecture": architecture, "seed": seed, "method": method, "settings": settings}


def validate_artifact(path: Path, binding: dict, component: dict) -> dict:
    manifest = read_json(path / "manifest.json")
    require(manifest["schema_version"] == "cpmt-s5-model-artifact-v1", "wrong artifact schema")
    require(manifest["status"] == "complete", "incomplete model artifact")
    require(manifest["binding"] == binding and manifest["component"] == component,
            "model binding mismatch")
    require(manifest["model_sha256"] == file_sha256(path / "model.pt"), "model file hash mismatch")
    return manifest


def ensure_artifact(path: Path, binding: dict, component: dict,
                    produce: Callable[[Path], dict]) -> tuple[dict, bool]:
    """Commit model + metadata together; never silently retrain an interrupted model."""
    if path.exists():
        return validate_artifact(path, binding, component), True
    staging = path.with_name("." + path.name + ".incomplete")
    require(not staging.exists(), "incomplete attempt requires review: " + str(staging))
    staging.mkdir(parents=True)
    write_json(staging / "attempt.json", {"binding": binding, "component": component})
    try:
        metadata = produce(staging / "model.pt")
        manifest = {"schema_version": "cpmt-s5-model-artifact-v1", "status": "complete",
                    "binding": binding, "component": component, "training": metadata,
                    "model_sha256": file_sha256(staging / "model.pt")}
        write_json(staging / "manifest.json", manifest)
        validate_artifact(staging, binding, component)
        staging.rename(path)
    except BaseException as error:
        if staging.exists():
            write_json(staging / "failure.json", {"type": type(error).__name__, "message": str(error)})
        raise
    return validate_artifact(path, binding, component), False
