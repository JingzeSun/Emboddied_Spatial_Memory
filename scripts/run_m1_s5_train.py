"""Train the frozen S5 recipes on train only and durably save every model.

There is no budget search, validation pass, causal rollout, or test access here.
Each of the two registered arms saves five scorers and 25 online students.
Completed artifacts resume by exact binding and file hash; failed partial
artifacts are preserved for review. Run through ops/run_next_server_step.sh.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
import traceback
from pathlib import Path

import numpy as np
import torch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from cpmt.dev_learning import (  # noqa: E402
    OnlineModel, OutcomeScorer, architecture_kwargs,
    tensors, train_outcome_scorer, train_student,
)
from cpmt.m1_af_rollout import CANDIDATE_FEATURE_DIM, CURRENT_RELATION_QUERIES  # noqa: E402
from cpmt.m1_protocol import load_and_validate, load_and_validate_endpoint_probe, protocol_sha256  # noqa: E402
from cpmt.m1_s5_training import (  # noqa: E402
    component_spec, ensure_artifact, load_plan, read_json, require,
    validate_test_marker, write_json,
)
from cpmt.run_provenance import capture_run_provenance, file_sha256, source_tree_sha256  # noqa: E402
from run_m1_train_inner_dev_budget import _architecture_settings, _load_train  # noqa: E402


def training_config(hard: dict, plan: dict, registration: dict, component: dict) -> dict:
    selected = plan["arms"][component["architecture"]]["selected"]
    settings = component["settings"]
    return {
        **_architecture_settings(hard, component["architecture"]),
        "horizon": int(hard["future"]["primary_horizon"]),
        "batch_size": int(hard["training"]["pretest_budget_selection"]["batch_size"]),
        "device": plan["device"], "cpu_threads": plan["torch_threads"],
        "learning_rate": float(settings["learning_rate"]),
        "scorer_steps": int(selected["outcome_scorer_steps"]),
        "student_steps": int(settings.get("student_steps", 0)),
        "auxiliary_weight": float(settings.get("direct_future_auxiliary_weight", 1.0)),
        "distillation_weight": 1.0,
        "candidate_feature_dim": CANDIDATE_FEATURE_DIM,
        "current_relation_dim": len(CURRENT_RELATION_QUERIES),
        "standardize_future_term": True,
        "energy_weights": hard["energy"]["weights"],
        "temperature": float(hard["energy"]["temperature"]),
        "commit_probability": registration["evaluation_plan"]["commit_probability"],
        "margin_threshold": registration["evaluation_plan"]["margin_threshold"],
        "formal_run": False, "test_access": False,
    }


def model_kwargs(train: dict, config: dict, scorer: bool) -> dict:
    kwargs = {
        "input_dim": int(train["x"].shape[1]), "hidden": config["hidden_dim"],
        "future_dim": int(train["relation_targets" if scorer else "future"].shape[-1]),
        "horizon": config["horizon"], "num_candidates": int(train["penalties"].shape[1]),
        "candidate_dim": config["candidate_feature_dim"], **architecture_kwargs(config),
    }
    kwargs["current_relation_dim" if scorer else "relation_dim"] = (
        config["current_relation_dim"] if scorer else int(train["relation_targets"].shape[-1])
    )
    return kwargs


def load_saved_model(path: Path, binding: dict, component: dict, device: torch.device):
    """Load only tensor/primitive payloads, preserving the declared architecture."""
    from cpmt.m1_s5_training import validate_artifact
    manifest = validate_artifact(path, binding, component)
    payload = torch.load(path / "model.pt", map_location=device, weights_only=True)
    require(payload["binding"] == binding and payload["component"] == component,
            "checkpoint payload binding mismatch")
    scorer = component["method"] == "outcome_scorer"
    require(payload["model_class"] == ("OutcomeScorer" if scorer else "OnlineModel"),
            "wrong saved model class")
    require(payload["model_kwargs"] == manifest["training"]["model_kwargs"], "model shape metadata mismatch")
    # Initialization must not perturb a later consumer's random stream.
    with torch.random.fork_rng(devices=[]):
        model = (OutcomeScorer if scorer else OnlineModel)(**payload["model_kwargs"])
    model.load_state_dict(payload["state_dict"], strict=True)
    model.to(device).eval()
    return model, payload


def train_component(train: dict, config: dict, binding: dict, component: dict,
                    teacher, model_path: Path, device: torch.device, provenance: dict) -> dict:
    scorer = component["method"] == "outcome_scorer"
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
        torch.cuda.synchronize(device)
    started = time.perf_counter()
    if scorer:
        # The legacy API names its second argument validation. Both arguments
        # deliberately alias train; no held-out file is read or evaluated.
        model, teachers, trace = train_outcome_scorer(
            train, train, config, component["seed"], device,
        )
        train_teacher = teachers["train"].detach().cpu()
        del teachers
    else:
        require(teacher is not None, "student teacher is missing")
        model, trace = train_student(component["method"], train, teacher, config,
                                     component["seed"], device)
        train_teacher = None
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    seconds = time.perf_counter() - started
    kwargs = model_kwargs(train, config, scorer)
    state = {key: value.detach().cpu() for key, value in model.state_dict().items()}
    require(all(bool(torch.isfinite(value).all()) for value in state.values()), "non-finite model weights")
    payload = {"schema_version": "cpmt-s5-model-payload-v1", "binding": binding,
               "component": component, "model_class": "OutcomeScorer" if scorer else "OnlineModel",
               "model_kwargs": kwargs, "state_dict": state, "config": config}
    if scorer:
        require(tuple(train_teacher.shape) == tuple(train["penalties"].shape), "scorer teacher shape mismatch")
        require(bool(torch.isfinite(train_teacher).all()), "non-finite scorer teacher")
        payload["train_teacher"] = train_teacher
    torch.save(payload, model_path)
    result = {"config": config, "model_kwargs": kwargs, "trace": trace,
              "wall_seconds": seconds, "parameter_count": sum(p.numel() for p in model.parameters()),
              "peak_allocated_mb": torch.cuda.max_memory_allocated(device) / 2**20 if device.type == "cuda" else None,
              "training_provenance": provenance, "validation_arrays_read": False, "test_access": False}
    del model
    return result


def run_training(root: Path, train_path: Path, output: Path, test_marker: Path) -> dict:
    hard = load_and_validate(root / "configs/m1_hard_condition.json")
    overlay = load_and_validate_endpoint_probe(root / "configs/m1_endpoint_viability_probe.json", hard)
    plan, registration = load_plan(root, hard, overlay)
    validate_test_marker(read_json(test_marker), root, plan)
    provenance = capture_run_provenance(root, component="m1_s5_selected_training", entrypoint=Path(__file__))
    require(provenance["git_dirty"] is False, "training checkout must be clean")
    require(torch.cuda.is_available(), "registered CUDA device is unavailable; do not silently switch device")
    torch.set_num_threads(plan["torch_threads"])
    device = torch.device(plan["device"])
    arrays, input_record = _load_train(train_path, expected_protocol_sha256=protocol_sha256(hard),
                                     expected_dataset_version=hard["data"]["dataset_version"])
    require(input_record["arrays_digest"] == plan["train_arrays_digest"], "training array digest mismatch")
    groups = sorted(set(int(g) for g in arrays["group"]))
    require(len(groups) == plan["train_paired_groups"], "wrong number of full train groups")
    # Digest binds the original 10% annotation mask; do not resample or treat
    # previously selected inner-dev groups as independent validation results.
    runtime = {"device": str(device), "torch_threads": plan["torch_threads"],
               "torch_version": str(torch.__version__), "numpy_version": str(np.__version__),
               "cuda_version": torch.version.cuda, "cuda_device": torch.cuda.get_device_name(device)}
    binding = {"plan_sha256": protocol_sha256(plan),
               "registration_sha256": protocol_sha256(registration),
               "source_tree_sha256": source_tree_sha256(root),
               "source_protocol_sha256": protocol_sha256(hard),
               "train_arrays_digest": input_record["arrays_digest"], "runtime": runtime}
    run_path = output / "training_manifest.json"
    if run_path.exists():
        require(read_json(run_path)["binding"] == binding, "existing run binding mismatch")
    run = {"schema_version": "cpmt-s5-training-manifest-v1", "status": "running", "binding": binding,
           "plan": plan, "post_probe_registration": registration, "input_arrays": {"train": input_record},
           "training_group_ids": groups, "training_rows": len(arrays["y"]),
           "labelled_rows": int(arrays["labelled"].sum()), "label_mask_reused": True,
           "formal_run": False, "validation_arrays_read": False, "test_access": False,
           "causal_complete": False, "model_selection_performed": False, "models": {},
           "future_use_policy": {"training_hindsight_and_auxiliary_targets": True,
                                 "online_future_access": False,
                                 "execution_boundary": registration["execution_boundary"]},
           "frozen_front_end_components": hard["training"]["frozen"],
           "evaluation_metrics_status": "pending_separate_S5_confirmation",
           "training_provenance": provenance, "test_marker_sha256": file_sha256(test_marker)}
    write_json(run_path, run)
    train = tensors(arrays, device)
    del arrays
    for architecture in hard["architecture_evaluation"]["registered"]:
        for seed in plan["seeds"]:
            learned_teacher = None
            methods = ["outcome_scorer", *hard["training"]["pretest_budget_selection"]["student_selection_methods"]]
            for method in methods:
                component = component_spec(plan, architecture, seed, method)
                config = training_config(hard, plan, registration, component)
                key = f"{architecture}/seed_{seed}/{method}"
                path = output / "models" / key
                teacher = (learned_teacher if method == "future_no_execution" else
                           train["pstar_current"] if method == "execute_current_only" else train["pstar"])
                print(f"MODEL_BEGIN key={key} settings={json.dumps(component['settings'],sort_keys=True)}", flush=True)
                manifest, reused = ensure_artifact(path, binding, component,
                    lambda model_path: train_component(train, config, binding, component, teacher,
                                                       model_path, device, provenance))
                # Exercise the same public loading path needed by S5/S6 before
                # counting the artifact complete. This also checks state shapes.
                model, payload = load_saved_model(path, binding, component, device)
                if method == "outcome_scorer":
                    learned_teacher = payload["train_teacher"]
                    require(tuple(learned_teacher.shape) == tuple(train["penalties"].shape), "cached teacher shape mismatch")
                    require(bool(torch.isfinite(learned_teacher).all()), "cached teacher is non-finite")
                run["models"][key] = {"path": str(path), "model_sha256": manifest["model_sha256"],
                                      "component": component, "training": manifest["training"]}
                write_json(run_path, run)
                print(f"MODEL_{'REUSED' if reused else 'SAVED'} key={key} completed={len(run['models'])}/60", flush=True)
                del model, payload
                torch.cuda.empty_cache()
            del learned_teacher
    require(len(run["models"]) == 60, "incomplete registered model set")
    for architecture in hard["architecture_evaluation"]["registered"]:
        counts = {v["training"]["parameter_count"] for v in run["models"].values()
                  if v["component"]["architecture"] == architecture and v["component"]["method"] != "outcome_scorer"}
        require(len(counts) == 1, "A-E student parameter count mismatch")
    run["status"] = "complete"
    write_json(run_path, run)
    print("S5_TRAIN_OK models=60 validation_arrays_read=false test_access=false", flush=True)
    return run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--test-marker", type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    import fcntl  # AutoDL execution only; pure metadata tests also work on Windows.
    with (args.out_dir / "training.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            run_training(PROJECT, args.train, args.out_dir, args.test_marker)
        except BaseException:
            stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            write_json(args.out_dir / f"failure_{stamp}.json", {"traceback": traceback.format_exc(),
                       "test_access": False, "validation_arrays_read": False})
            raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
