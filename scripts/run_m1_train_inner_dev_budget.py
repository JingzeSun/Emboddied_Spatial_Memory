"""Select one scorer and per-method A-E student budgets from train only.

This v8 S1/S2 entrypoint reads exactly the registered 1,000 mixed train
paired groups, holds out complete groups with the frozen SHA-256 rule, and
evaluates the registered checkpoints on one identical seeded trajectory per
learning rate. Every A-E method first gets the same finite lr/update search at
C's auxiliary-weight anchor. D-046 then freezes C's selected compute cell and
compares its three registered auxiliary weights by reusing the anchor path and
adding two paths per seed. It handles one architecture arm per invocation. It never reads
validation/test, calibrates a commit gate, runs causal evaluation, or chooses
between the Set Transformer and MLP arms.

With ``--runtime-profile-only`` it instead measures one fixed, registered
300-update path for the scorer and A--E.  That mode exports timing and parameter
counts only: it performs no selection and exports no scientific metric.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from cpmt.dev_learning import (  # noqa: E402
    apply_candidate_admissibility_to_probabilities,
    candidate_admissibility_mask,
    masked_candidate_probabilities,
    outcome_scorer_diagnostics,
    tensors,
    train_outcome_scorer,
    train_student,
)
from cpmt.m1_af_rollout import (  # noqa: E402
    CANDIDATE_FEATURE_DIM,
    CURRENT_RELATION_QUERIES,
    training_inner_dev_mask,
)
from cpmt.m1_protocol import (  # noqa: E402
    load_and_validate,
    load_and_validate_endpoint_probe,
    protocol_sha256,
)
from cpmt.run_provenance import arrays_sha256, capture_run_provenance  # noqa: E402
from cpmt.m1_registration import load_registration  # noqa: E402


def _load_train(
    path: Path, *, expected_protocol_sha256: str,
    expected_dataset_version: str,
) -> tuple[dict[str, np.ndarray], dict]:
    arrays = {
        key: value for key, value in np.load(path, allow_pickle=True).items()
    }
    digest = arrays_sha256(arrays)
    manifest_path = path.with_suffix(".manifest.json")
    if not manifest_path.exists():
        raise ValueError(f"generation manifest is required for {path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("arrays_digest") != digest:
        raise ValueError("train arrays do not match their generation manifest")
    if manifest.get("protocol_sha256") != expected_protocol_sha256:
        raise ValueError("train arrays do not match the active protocol")
    if manifest.get("dataset_version") != expected_dataset_version:
        raise ValueError("train arrays do not match the active dataset version")
    if manifest.get("split") != "train":
        raise ValueError("budget selection accepts train arrays only")
    health = manifest.get("teacher_health_gate")
    if not health or health.get("pass") is not True:
        raise ValueError("train arrays did not pass the teacher health gate")
    return arrays, {
        "path": str(path),
        "manifest_path": str(manifest_path),
        "arrays_digest": digest,
        "manifest": manifest,
    }


def _subset_rows(
    arrays: dict[str, np.ndarray], mask: np.ndarray,
) -> dict[str, np.ndarray]:
    return {
        key: value[mask]
        if isinstance(value, np.ndarray) and len(value) == len(mask)
        else value
        for key, value in arrays.items()
    }


def _architecture_settings(hard: dict, architecture: str) -> dict:
    spec = hard["architecture_evaluation"][architecture]
    return {
        "architecture": architecture,
        "hidden_dim": int(spec.get("model_dim", spec.get("hidden_dim"))),
        "attention_heads": int(spec.get("attention_heads", 4)),
        "set_attention_blocks": int(spec.get("set_attention_blocks", 2)),
        "feedforward_dim": int(spec.get("feedforward_dim", 256)),
        "architecture_dropout": float(spec.get("dropout", 0.0)),
    }


def _accuracy_by_group(
    predicted: np.ndarray, target: np.ndarray, groups: np.ndarray,
    row_mask: np.ndarray,
) -> dict[str, float]:
    result = {}
    for group_id in sorted(set(int(value) for value in groups[row_mask])):
        selected = row_mask & (groups == group_id)
        result[str(group_id)] = float(np.mean(predicted[selected] == target[selected]))
    if not result:
        raise ValueError("budget-selection group metric is empty")
    return result


def _checkpoint_selection(
    checkpoint_values: dict[int, list[float]],
) -> dict:
    """Pick the highest registered mean and break exact ties toward less work."""
    if not checkpoint_values or any(not values for values in checkpoint_values.values()):
        raise ValueError("each budget checkpoint needs at least one group metric")
    aggregate = {
        int(step): float(np.mean(values))
        for step, values in checkpoint_values.items()
    }
    best = max(aggregate.values())
    selected = min(step for step, value in aggregate.items() if value == best)
    return {
        "aggregate_mean_by_checkpoint": {
            str(step): aggregate[step] for step in sorted(aggregate)
        },
        "selected_checkpoint": int(selected),
        "selected_aggregate_mean": float(best),
        "tie_break_applied": sum(value == best for value in aggregate.values()) > 1,
    }


def _grid_selection(
    cell_values: dict[tuple[float, int], list[float]], *,
    maximum_checkpoint: int,
) -> dict:
    """Select a learning-rate/checkpoint cell with a deterministic tie break."""
    if not cell_values or any(not values for values in cell_values.values()):
        raise ValueError("each optimization-grid cell needs group metrics")
    aggregate = {
        (float(learning_rate), int(step)): float(np.mean(values))
        for (learning_rate, step), values in cell_values.items()
    }
    if not all(np.isfinite(value) for value in aggregate.values()):
        raise ValueError("optimization-grid aggregate must be finite")
    ranked = sorted(
        aggregate,
        key=lambda cell: (-aggregate[cell], cell[1], cell[0]),
    )
    selected_learning_rate, selected_checkpoint = ranked[0]
    best = aggregate[ranked[0]]
    winners = [cell for cell, value in aggregate.items() if value == best]
    runner_up = ranked[1] if len(ranked) > 1 else None
    return {
        "aggregate_mean_by_cell": [
            {
                "learning_rate": learning_rate,
                "checkpoint": checkpoint,
                "aggregate_mean": aggregate[(learning_rate, checkpoint)],
            }
            for learning_rate, checkpoint in sorted(
                aggregate, key=lambda cell: (cell[0], cell[1])
            )
        ],
        "selected_learning_rate": float(selected_learning_rate),
        "selected_checkpoint": int(selected_checkpoint),
        "selected_aggregate_mean": float(best),
        "deterministic_runner_up": (
            {
                "learning_rate": float(runner_up[0]),
                "checkpoint": int(runner_up[1]),
                "aggregate_mean": float(aggregate[runner_up]),
            }
            if runner_up is not None else None
        ),
        "tie_break_applied": len(winners) > 1,
        "budget_grid_ceiling_reached": bool(
            selected_checkpoint == int(maximum_checkpoint)
        ),
        "ceiling_action": (
            "accept_and_report_without_posthoc_extension"
            if selected_checkpoint == int(maximum_checkpoint) else None
        ),
    }


def _cell_group_means(
    runs: list[dict], *, metric_key: str,
    expected_cells: set[tuple[float, int]],
    expected_observations_per_group: int,
    method: str | None = None,
) -> dict[tuple[float, int], dict[str, float]]:
    """Average seeds (and optionally methods) inside each complete paired group."""
    collected = {cell: {} for cell in expected_cells}
    seen_support = set()
    for run in runs:
        if method is not None and run.get("method") != method:
            continue
        cell = (float(run["learning_rate"]), int(run["checkpoint"]))
        if cell not in expected_cells:
            raise ValueError(f"unexpected optimization-grid cell: {cell}")
        metric_container = (
            run if metric_key in run else run.get("inner_dev_online", {})
        )
        by_group = metric_container.get(metric_key)
        if not isinstance(by_group, dict) or not by_group:
            raise ValueError(f"missing complete-group metric: {metric_key}")
        for group_id, value in by_group.items():
            support_key = (
                cell, str(group_id), run.get("method"), int(run["seed"]),
            )
            if support_key in seen_support:
                raise ValueError(
                    "duplicate seed/method support in optimization-grid cell: "
                    f"{support_key}"
                )
            seen_support.add(support_key)
            collected[cell].setdefault(str(group_id), []).append(float(value))

    group_ids = None
    means = {}
    for cell in sorted(expected_cells):
        groups = collected[cell]
        if not groups:
            raise ValueError(f"optimization-grid cell has no observations: {cell}")
        if any(
            len(values) != int(expected_observations_per_group)
            for values in groups.values()
        ):
            raise ValueError(
                "optimization-grid cell does not have equal seed/method support "
                f"for every complete paired group: {cell}"
            )
        current_group_ids = set(groups)
        if group_ids is None:
            group_ids = current_group_ids
        elif current_group_ids != group_ids:
            raise ValueError("optimization-grid cells do not share complete groups")
        means[cell] = {
            group_id: float(np.mean(values))
            for group_id, values in sorted(groups.items())
        }
    return means


def _auxiliary_weight_group_means(
    runs: list[dict], *, expected_weights: list[float],
    expected_observations_per_group: int,
) -> dict[float, dict[str, float]]:
    """Average the fixed-compute C weight trials within complete groups."""
    weights = [float(value) for value in expected_weights]
    if len(weights) != len(set(weights)):
        raise ValueError("auxiliary-weight grid must be unique")
    collected = {weight: {} for weight in weights}
    seen_support = set()
    for run in runs:
        weight = float(run["auxiliary_weight"])
        if weight not in collected:
            raise ValueError(f"unexpected auxiliary weight: {weight}")
        by_group = run.get("inner_dev_online", {}).get(
            "reference_accuracy_by_group"
        )
        if not isinstance(by_group, dict) or not by_group:
            raise ValueError("missing auxiliary-weight complete-group metric")
        for group_id, value in by_group.items():
            support_key = (weight, str(group_id), int(run["seed"]))
            if support_key in seen_support:
                raise ValueError(
                    "duplicate seed support in auxiliary-weight cell: "
                    f"{support_key}"
                )
            seen_support.add(support_key)
            collected[weight].setdefault(str(group_id), []).append(float(value))

    group_ids = None
    means = {}
    for weight in weights:
        groups = collected[weight]
        if not groups:
            raise ValueError(f"auxiliary-weight cell has no observations: {weight}")
        if any(
            len(values) != int(expected_observations_per_group)
            for values in groups.values()
        ):
            raise ValueError(
                "auxiliary-weight cell does not have equal seed support for "
                f"every complete paired group: {weight}"
            )
        current_group_ids = set(groups)
        if group_ids is None:
            group_ids = current_group_ids
        elif current_group_ids != group_ids:
            raise ValueError(
                "auxiliary-weight cells do not share complete paired groups"
            )
        means[weight] = {
            group_id: float(np.mean(values))
            for group_id, values in sorted(groups.items())
        }
    return means


def _auxiliary_weight_selection(
    group_means_by_weight: dict[float, dict[str, float]], *,
    anchor_weight: float,
    uncertainty: dict,
) -> dict:
    """Select C's weight after compute is fixed, preferring the anchor on ties."""
    anchor_weight = float(anchor_weight)
    if anchor_weight not in group_means_by_weight:
        raise ValueError("auxiliary-weight selection lacks its registered anchor")
    aggregate = {
        float(weight): float(np.mean(list(by_group.values())))
        for weight, by_group in group_means_by_weight.items()
    }
    if not aggregate or not all(np.isfinite(value) for value in aggregate.values()):
        raise ValueError("auxiliary-weight aggregates must be finite")
    ranked = sorted(
        aggregate,
        key=lambda weight: (
            -aggregate[weight],
            0 if weight == anchor_weight else 1,
            weight,
        ),
    )
    selected = ranked[0]
    runner_up = ranked[1] if len(ranked) > 1 else None
    result = {
        "aggregate_mean_by_weight": [
            {
                "auxiliary_weight": float(weight),
                "aggregate_mean": float(aggregate[weight]),
            }
            for weight in sorted(aggregate)
        ],
        "selected_auxiliary_weight": float(selected),
        "selected_aggregate_mean": float(aggregate[selected]),
        "deterministic_runner_up": (
            {
                "auxiliary_weight": float(runner_up),
                "aggregate_mean": float(aggregate[runner_up]),
            }
            if runner_up is not None else None
        ),
        "tie_break_applied": sum(
            value == aggregate[selected] for value in aggregate.values()
        ) > 1,
        "tie_break_rule": "prefer_anchor_1.0_then_lower_registered_weight",
    }
    result["selected_vs_deterministic_runner_up_paired_bootstrap"] = (
        _paired_group_bootstrap_difference(
            group_means_by_weight[selected],
            group_means_by_weight[runner_up],
            resamples=int(uncertainty["bootstrap_resamples"]),
            seed=int(uncertainty["bootstrap_seed"]),
            confidence=float(uncertainty["confidence"]),
        )
        if runner_up is not None else None
    )
    return result


def _paired_group_bootstrap_difference(
    selected_by_group: dict[str, float],
    runner_up_by_group: dict[str, float], *,
    resamples: int, seed: int, confidence: float,
) -> dict:
    """Diagnose selected-minus-runner-up uncertainty without changing selection."""
    if set(selected_by_group) != set(runner_up_by_group):
        raise ValueError("paired bootstrap requires the same complete groups")
    group_ids = sorted(selected_by_group)
    if not group_ids:
        raise ValueError("paired bootstrap requires at least one complete group")
    if int(resamples) <= 0 or not 0.0 < float(confidence) < 1.0:
        raise ValueError("invalid paired-bootstrap settings")
    differences = np.asarray([
        selected_by_group[group_id] - runner_up_by_group[group_id]
        for group_id in group_ids
    ], dtype=np.float64)
    generator = np.random.default_rng(int(seed))
    indices = generator.integers(
        0, len(differences), size=(int(resamples), len(differences)),
    )
    bootstrap_means = differences[indices].mean(axis=1)
    tail = (1.0 - float(confidence)) / 2.0
    return {
        "unit": "complete_paired_group_after_equal_seed_averaging",
        "complete_paired_groups": len(group_ids),
        "observed_mean_difference": float(differences.mean()),
        "bootstrap_resamples": int(resamples),
        "bootstrap_seed": int(seed),
        "confidence": float(confidence),
        "confidence_interval": [
            float(np.quantile(bootstrap_means, tail)),
            float(np.quantile(bootstrap_means, 1.0 - tail)),
        ],
        "diagnostic_only_selection_rule_unchanged": True,
    }


def _add_selection_uncertainty(
    selection: dict,
    group_means_by_cell: dict[tuple[float, int], dict[str, float]],
    uncertainty: dict,
) -> None:
    """Attach the pre-registered selected-versus-runner-up paired diagnostic."""
    runner_up = selection.get("deterministic_runner_up")
    if runner_up is None:
        selection["selected_vs_deterministic_runner_up_paired_bootstrap"] = None
        return
    selected_cell = (
        float(selection["selected_learning_rate"]),
        int(selection["selected_checkpoint"]),
    )
    runner_up_cell = (
        float(runner_up["learning_rate"]), int(runner_up["checkpoint"]),
    )
    selection["selected_vs_deterministic_runner_up_paired_bootstrap"] = (
        _paired_group_bootstrap_difference(
            group_means_by_cell[selected_cell],
            group_means_by_cell[runner_up_cell],
            resamples=int(uncertainty["bootstrap_resamples"]),
            seed=int(uncertainty["bootstrap_seed"]),
            confidence=float(uncertainty["confidence"]),
        )
    )


def _cell_score(
    group_means_by_cell: dict[tuple[float, int], dict[str, float]],
    cell: tuple[float, int],
) -> float:
    return float(np.mean(list(group_means_by_cell[cell].values())))


def _linear_runtime_projection(
    *, scorer_path_seconds: float, scorer_evaluation_seconds: float,
    student_path_seconds_by_method: dict[str, float],
    student_evaluation_seconds_by_method: dict[str, float],
    profile_steps: int, maximum_steps: int,
    learning_rate_count: int, seed_count: int,
    checkpoint_count: int,
    additional_student_paths_by_method: dict[str, int] | None = None,
) -> dict:
    """Project registered-grid cost from one fixed, non-selective profile path."""
    if profile_steps <= 0 or maximum_steps < profile_steps:
        raise ValueError("runtime projection needs valid update counts")
    if set(student_path_seconds_by_method) != set(
        student_evaluation_seconds_by_method
    ):
        raise ValueError("student runtime methods do not match")
    if min(learning_rate_count, seed_count, checkpoint_count) <= 0:
        raise ValueError("runtime projection counts must be positive")
    additional_paths = additional_student_paths_by_method or {
        method: 0 for method in student_path_seconds_by_method
    }
    if set(additional_paths) != set(student_path_seconds_by_method):
        raise ValueError("additional student path methods do not match")
    if any(int(value) < 0 for value in additional_paths.values()):
        raise ValueError("additional student path counts must be non-negative")
    scale = float(maximum_steps) / float(profile_steps)
    paths_per_component = int(learning_rate_count) * int(seed_count)
    scorer_seconds = paths_per_component * (
        float(scorer_path_seconds) * scale
        + float(scorer_evaluation_seconds) * int(checkpoint_count)
    )
    student_seconds_by_method = {
        method: (
            paths_per_component * (
                float(student_path_seconds_by_method[method]) * scale
                + float(student_evaluation_seconds_by_method[method])
                * int(checkpoint_count)
            )
            + int(additional_paths[method]) * (
                float(student_path_seconds_by_method[method]) * scale
                + float(student_evaluation_seconds_by_method[method])
            )
        )
        for method in sorted(student_path_seconds_by_method)
    }
    total_seconds = scorer_seconds + sum(student_seconds_by_method.values())
    return {
        "assumption": (
            "linear_updates;_profile_path_final_full_teacher_materialization_is_"
            "also_scaled_so_the_scorer_projection_is_conservative"
        ),
        "protocol_cap_or_selection_metric": False,
        "paths_per_component": paths_per_component,
        "additional_student_paths_by_method": {
            method: int(additional_paths[method])
            for method in sorted(additional_paths)
        },
        "profile_steps": int(profile_steps),
        "maximum_steps": int(maximum_steps),
        "checkpoint_evaluations_per_path": int(checkpoint_count),
        "scorer_seconds": float(scorer_seconds),
        "student_seconds_by_method": student_seconds_by_method,
        "total_seconds": float(total_seconds),
        "total_hours": float(total_seconds / 3600.0),
    }


def _synchronize(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def _run_runtime_profile(
    *, args: argparse.Namespace, hard: dict, budget: dict,
    budget_amendment: dict,
    active_protocol: str, train_input: dict,
    fitting: dict[str, torch.Tensor], held_out: dict[str, torch.Tensor],
    inner_online: np.ndarray, inner_groups: np.ndarray,
    cfg: dict, diagnostic_kwargs: dict, seeds: list[int],
    learning_rates: list[float], scorer_checkpoints: list[int],
    student_checkpoints: list[int], device: torch.device,
    device_name: str,
) -> int:
    """Measure cost only; do not select, save, or report scientific metrics."""
    profile_steps = min(min(scorer_checkpoints), min(student_checkpoints))
    anchor = budget["shared_diagnostic_anchor"]
    profile_learning_rate = float(anchor["learning_rate"])
    if profile_learning_rate not in learning_rates:
        raise ValueError("runtime profile learning rate is outside registered grid")
    profile_seed = int(seeds[0])
    profile_cfg = dict(
        cfg,
        learning_rate=profile_learning_rate,
        scorer_steps=profile_steps,
        student_steps=profile_steps,
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.out_dir / "runtime_profile.json"
    if report_path.exists():
        raise ValueError("runtime profile report already exists; refusing overwrite")

    print(
        f"RUNTIME_PROFILE_BEGIN architecture={args.architecture} "
        f"device={device_name} seed={profile_seed} "
        f"lr={profile_learning_rate:.6g} steps={profile_steps}",
        flush=True,
    )
    _synchronize(device)
    scorer_started = time.time()
    scorer, learned, _ = train_outcome_scorer(
        fitting, held_out, profile_cfg, profile_seed, device,
    )
    _synchronize(device)
    scorer_path_seconds = float(time.time() - scorer_started)
    _synchronize(device)
    scorer_evaluation_started = time.time()
    outcome_scorer_diagnostics(
        scorer, held_out, learned["validation"],
        row_mask=inner_online, **diagnostic_kwargs,
    )
    _synchronize(device)
    scorer_evaluation_seconds = float(
        time.time() - scorer_evaluation_started
    )
    scorer_parameter_count = sum(
        parameter.numel() for parameter in scorer.parameters()
    )
    del scorer

    student_path_seconds_by_method = {}
    student_evaluation_seconds_by_method = {}
    student_parameter_signatures = set()
    for method in budget["student_selection_methods"]:
        train_teacher, inner_teacher = _method_teachers(
            method, fitting, held_out, learned,
        )
        _synchronize(device)
        student_started = time.time()
        model, _ = train_student(
            method, fitting, train_teacher,
            profile_cfg, profile_seed, device,
        )
        _synchronize(device)
        student_path_seconds_by_method[method] = float(
            time.time() - student_started
        )
        student_parameter_signatures.add(tuple(
            (name, tuple(parameter.shape), bool(parameter.requires_grad))
            for name, parameter in model.named_parameters()
        ))
        _synchronize(device)
        evaluation_started = time.time()
        _student_checkpoint_metrics(
            model, held_out, inner_teacher, inner_online, inner_groups,
        )
        _synchronize(device)
        student_evaluation_seconds_by_method[method] = float(
            time.time() - evaluation_started
        )
        del model, train_teacher, inner_teacher
    del learned
    if len(student_parameter_signatures) != 1:
        raise AssertionError(
            "A-E runtime-profile student parameter shapes differ"
        )
    student_parameter_signature = next(iter(student_parameter_signatures))

    projection = _linear_runtime_projection(
        scorer_path_seconds=scorer_path_seconds,
        scorer_evaluation_seconds=scorer_evaluation_seconds,
        student_path_seconds_by_method=student_path_seconds_by_method,
        student_evaluation_seconds_by_method=(
            student_evaluation_seconds_by_method
        ),
        profile_steps=profile_steps,
        maximum_steps=max(max(scorer_checkpoints), max(student_checkpoints)),
        learning_rate_count=len(learning_rates),
        seed_count=len(seeds),
        checkpoint_count=max(
            len(scorer_checkpoints), len(student_checkpoints)
        ),
        additional_student_paths_by_method={
            method: (
                int(budget_amendment[
                    "additional_c_auxiliary_weight_paths_per_seed"
                ]) * len(seeds)
                if method == budget_amendment["direct_future_method_name"]
                else 0
            )
            for method in student_path_seconds_by_method
        },
    )
    report = {
        "schema_version": "cpmt-m1-v8-budget-runtime-profile-v2",
        "runner": "run_m1_train_inner_dev_budget_runtime_profile_v2",
        "formal_run": False,
        "selection_performed": False,
        "scientific_metrics_exported": False,
        "validation_arrays_read": False,
        "test_access": False,
        "protocol_sha256": active_protocol,
        "dataset_version": hard["data"]["dataset_version"],
        "architecture": args.architecture,
        "D046_budget_amendment": budget_amendment,
        "input_arrays": {"train": train_input},
        "profile": {
            "seed": profile_seed,
            "learning_rate": profile_learning_rate,
            "steps": profile_steps,
            "registered_grid_point": True,
            "scorer_path_seconds": scorer_path_seconds,
            "scorer_evaluation_seconds": scorer_evaluation_seconds,
            "student_path_seconds_by_method": student_path_seconds_by_method,
            "student_evaluation_seconds_by_method": (
                student_evaluation_seconds_by_method
            ),
        },
        "parameter_fairness": {
            "outcome_scorer_parameters": int(scorer_parameter_count),
            "student_parameters": int(sum(
                int(np.prod(shape)) for _, shape, _ in student_parameter_signature
            )),
            "student_parameter_signature_A_to_E": [
                {
                    "name": name,
                    "shape": list(shape),
                    "requires_grad": requires_grad,
                }
                for name, shape, requires_grad in student_parameter_signature
            ],
        },
        "registered_grid_projection": projection,
        "device": {
            "resolved": device_name,
            "torch_version": torch.__version__,
            "cuda_version": torch.version.cuda,
            "cuda_device": (
                torch.cuda.get_device_name(device)
                if device.type == "cuda" else None
            ),
            "peak_allocated_mb": (
                float(torch.cuda.max_memory_allocated(device) / 2**20)
                if device.type == "cuda" else None
            ),
            "threads": int(args.threads),
        },
        "training_provenance": capture_run_provenance(
            PROJECT,
            component="m1_v8_budget_runtime_profile",
            entrypoint=Path(__file__),
        ),
    }
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8",
    )
    print(f"RUNTIME_PROFILE_REPORT={report_path}", flush=True)
    print(
        f"RUNTIME_PROFILE_ESTIMATED_HOURS={projection['total_hours']:.3f}",
        flush=True,
    )
    print(
        f"RUNTIME_PROFILE_OK architecture={args.architecture} "
        "selection=false scientific_metrics_exported=false",
        flush=True,
    )
    return 0


def _student_checkpoint_metrics(
    model: torch.nn.Module, held_out: dict[str, torch.Tensor],
    teacher: torch.Tensor, inner_online: np.ndarray,
    inner_groups: np.ndarray,
) -> dict:
    with torch.no_grad():
        logits = model(held_out["x"])
        probabilities = masked_candidate_probabilities(
            logits, candidate_admissibility_mask(held_out, logits),
        )
        teacher = apply_candidate_admissibility_to_probabilities(
            teacher,
            candidate_admissibility_mask(held_out, held_out["penalties"]),
        )
        predicted = probabilities.argmax(dim=1).cpu().numpy()
        teacher_choice = teacher.argmax(dim=1).cpu().numpy()
        reference = held_out["y"].cpu().numpy()
        positive = teacher > 0
        teacher_log = torch.where(
            positive, torch.log(teacher), torch.zeros_like(teacher),
        )
        student_log = torch.log(probabilities.clamp_min(1e-12))
        kl_rows = torch.where(
            positive, teacher * (teacher_log - student_log),
            torch.zeros_like(teacher),
        ).sum(dim=1).cpu().numpy()
    return {
        "rows": int(inner_online.sum()),
        "teacher_argmax_agreement": float(np.mean(
            predicted[inner_online] == teacher_choice[inner_online]
        )),
        "reference_accuracy": float(np.mean(
            predicted[inner_online] == reference[inner_online]
        )),
        "teacher_reference_accuracy": float(np.mean(
            teacher_choice[inner_online] == reference[inner_online]
        )),
        "mean_teacher_to_student_kl": float(np.mean(kl_rows[inner_online])),
        "teacher_argmax_agreement_by_group": _accuracy_by_group(
            predicted, teacher_choice, inner_groups, inner_online,
        ),
        "reference_accuracy_by_group": _accuracy_by_group(
            predicted, reference, inner_groups, inner_online,
        ),
    }


def _method_teachers(
    method: str, fitting: dict[str, torch.Tensor],
    held_out: dict[str, torch.Tensor], learned: dict[str, torch.Tensor],
) -> tuple[torch.Tensor, torch.Tensor]:
    if method == "future_no_execution":
        train_teacher = learned["train"]
        held_out_teacher = learned["validation"]
    elif method == "execute_current_only":
        train_teacher = fitting["pstar_current"]
        held_out_teacher = held_out["pstar_current"]
    else:
        train_teacher = fitting["pstar"]
        held_out_teacher = held_out["pstar"]
    return (
        apply_candidate_admissibility_to_probabilities(
            train_teacher,
            candidate_admissibility_mask(fitting, fitting["penalties"]),
        ),
        apply_candidate_admissibility_to_probabilities(
            held_out_teacher,
            candidate_admissibility_mask(held_out, held_out["penalties"]),
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--config", type=Path,
        default=PROJECT / "configs" / "m1_hard_condition.json",
    )
    parser.add_argument(
        "--overlay", type=Path,
        default=PROJECT / "configs" / "m1_endpoint_viability_probe.json",
        help="accepted D-044--D-047 train-only evaluation/budget overlay",
    )
    parser.add_argument(
        "--architecture", required=True,
        choices=(
            "cross_candidate_set_transformer_v1",
            "shared_candidate_mlp_v1",
        ),
    )
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--threads", type=int, default=16)
    parser.add_argument(
        "--runtime-profile-only", action="store_true",
        help=(
            "measure one fixed registered path for cost planning; do not "
            "select budgets or export scientific metrics"
        ),
    )
    args = parser.parse_args()

    hard = load_and_validate(args.config)
    overlay = load_and_validate_endpoint_probe(args.overlay, hard)
    registration = load_registration(PROJECT, hard, overlay)
    budget = hard["training"]["pretest_budget_selection"]
    budget_amendment = overlay["post_probe_train_inner_dev_budget_amendment"]
    if args.architecture not in budget["architectures"]:
        parser.error("--architecture is outside the registered budget arms")
    active_protocol = protocol_sha256(hard)
    train_np, train_input = _load_train(
        args.train,
        expected_protocol_sha256=active_protocol,
        expected_dataset_version=str(hard["data"]["dataset_version"]),
    )
    groups = np.asarray(train_np["group"], dtype=np.int64)
    unique_groups = sorted(set(int(value) for value in groups))
    expected_groups = int(budget["train_paired_groups"])
    if len(unique_groups) != expected_groups:
        raise ValueError(
            f"registered budget selection requires exactly {expected_groups} "
            f"train paired groups, found {len(unique_groups)}"
        )
    inner_mask = training_inner_dev_mask(train_np)
    fitting_np = _subset_rows(train_np, ~inner_mask)
    inner_np = _subset_rows(train_np, inner_mask)
    fitting_groups = sorted(set(int(value) for value in fitting_np["group"]))
    inner_group_ids = sorted(set(int(value) for value in inner_np["group"]))
    if set(fitting_groups) & set(inner_group_ids):
        raise AssertionError("train inner-dev partition split a paired group")
    inner_online = ~np.asarray(inner_np["recovery"], dtype=bool)
    inner_groups = np.asarray(inner_np["group"], dtype=np.int64)

    if args.device == "cuda" and not torch.cuda.is_available():
        raise ValueError("--device cuda requested but CUDA is unavailable")
    device_name = (
        "cuda" if args.device == "auto" and torch.cuda.is_available()
        else "cpu" if args.device == "auto" else args.device
    )
    device = torch.device(device_name)
    torch.set_num_threads(args.threads)
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    fitting = tensors(fitting_np, device)
    held_out = tensors(inner_np, device)

    smoke = json.loads(
        (PROJECT / "configs" / "m1_af_smoke.json").read_text(encoding="utf-8")
    )
    scorer_checkpoints = [int(value) for value in budget["scorer_update_checkpoints"]]
    student_checkpoints = [int(value) for value in budget["student_update_checkpoints"]]
    learning_rates = [float(value) for value in budget["learning_rates"]]
    expected_scorer_cells = {
        (learning_rate, step)
        for learning_rate in learning_rates for step in scorer_checkpoints
    }
    expected_student_cells = {
        (learning_rate, step)
        for learning_rate in learning_rates for step in student_checkpoints
    }
    uncertainty = budget["selection_uncertainty"]
    cfg = dict(
        smoke,
        **_architecture_settings(hard, args.architecture),
        horizon=int(hard["future"]["primary_horizon"]),
        batch_size=int(budget["batch_size"]),
        device=device_name,
        scorer_steps=max(scorer_checkpoints),
        student_steps=max(student_checkpoints),
        distillation_weight=1.0,
        auxiliary_weight=float(
            budget_amendment["direct_future_auxiliary_weight_anchor"]
        ),
        candidate_feature_dim=CANDIDATE_FEATURE_DIM,
        current_relation_dim=len(CURRENT_RELATION_QUERIES),
        standardize_future_term=True,
        energy_weights=hard["energy"]["weights"],
        temperature=float(hard["energy"]["temperature"]),
    )
    influence = hard["energy"]["posterior_influence_audit"]
    diagnostic_kwargs = {
        "energy_weights": hard["energy"]["weights"],
        "temperature": float(hard["energy"]["temperature"]),
        "total_variation_thresholds": tuple(
            influence["total_variation_thresholds"]
        ),
    }
    seeds = [int(value) for value in budget["seeds"]]
    if args.runtime_profile_only:
        return _run_runtime_profile(
            args=args,
            hard=hard,
            budget=budget,
            budget_amendment=budget_amendment,
            active_protocol=active_protocol,
            train_input=train_input,
            fitting=fitting,
            held_out=held_out,
            inner_online=inner_online,
            inner_groups=inner_groups,
            cfg=cfg,
            diagnostic_kwargs=diagnostic_kwargs,
            seeds=seeds,
            learning_rates=learning_rates,
            scorer_checkpoints=scorer_checkpoints,
            student_checkpoints=student_checkpoints,
            device=device,
            device_name=device_name,
        )
    print(
        f"BUDGET_RUN_BEGIN architecture={args.architecture} device={device_name} "
        f"groups={len(unique_groups)} fitting={len(fitting_groups)} "
        f"inner_dev={len(inner_group_ids)} seeds={seeds} "
        f"learning_rates={learning_rates}",
        flush=True,
    )

    scorer_runs = []
    learned_cache: dict[
        tuple[float, int, int], dict[str, torch.Tensor]
    ] = {}
    scorer_parameter_count = None
    scorer_started = time.time()
    for learning_rate in learning_rates:
        for seed in seeds:
            began = time.time()

            def scorer_checkpoint(
                step, model, teachers, trace, *, run_seed=seed,
                run_learning_rate=learning_rate,
            ):
                nonlocal scorer_parameter_count
                parameter_count = sum(
                    parameter.numel() for parameter in model.parameters()
                )
                if scorer_parameter_count is None:
                    scorer_parameter_count = parameter_count
                elif scorer_parameter_count != parameter_count:
                    raise AssertionError(
                        "scorer parameter count changed across checkpoints"
                    )
                prediction = teachers["validation"].argmax(dim=1).cpu().numpy()
                reference = held_out["y"].cpu().numpy()
                per_group = _accuracy_by_group(
                    prediction, reference, inner_groups, inner_online,
                )
                diagnostics = outcome_scorer_diagnostics(
                    model, held_out, teachers["validation"],
                    row_mask=inner_online, **diagnostic_kwargs,
                )
                scorer_runs.append({
                    "seed": int(run_seed),
                    "learning_rate": float(run_learning_rate),
                    "checkpoint": int(step),
                    "inner_dev_online": diagnostics,
                    "reference_candidate_ranking_accuracy_by_group": per_group,
                    "training_trace": trace,
                })
                learned_cache[(
                    float(run_learning_rate), int(run_seed), int(step)
                )] = {
                    name: value.detach().cpu().clone()
                    for name, value in teachers.items()
                }
                print(
                    f"SCORER_CHECKPOINT architecture={args.architecture} "
                    f"seed={run_seed} lr={run_learning_rate:.6g} steps={step} "
                    f"inner_dev_accuracy={diagnostics['teacher_accuracy']:.6f} "
                    f"inner_dev_bce={diagnostics['masked_bce']:.6f}",
                    flush=True,
                )

            train_outcome_scorer(
                fitting, held_out,
                dict(cfg, learning_rate=float(learning_rate)),
                seed, device,
                checkpoint_steps=scorer_checkpoints,
                checkpoint_callback=scorer_checkpoint,
            )
            print(
                f"SCORER_PATH_OK seed={seed} lr={learning_rate:.6g} "
                f"wall_seconds={time.time()-began:.3f}",
                flush=True,
            )

    scorer_group_means = _cell_group_means(
        scorer_runs,
        metric_key="reference_candidate_ranking_accuracy_by_group",
        expected_cells=expected_scorer_cells,
        expected_observations_per_group=len(seeds),
    )
    scorer_values = {
        cell: list(by_group.values())
        for cell, by_group in scorer_group_means.items()
    }
    scorer_selection = _grid_selection(
        scorer_values, maximum_checkpoint=max(scorer_checkpoints),
    )
    _add_selection_uncertainty(
        scorer_selection, scorer_group_means, uncertainty,
    )
    selected_scorer_learning_rate = float(
        scorer_selection["selected_learning_rate"]
    )
    selected_scorer = int(scorer_selection["selected_checkpoint"])
    selected_learned = {
        seed: {
            name: tensor.to(device)
            for name, tensor in learned_cache[(
                selected_scorer_learning_rate, seed, selected_scorer
            )].items()
        }
        for seed in seeds
    }
    del learned_cache
    print(
        f"SCORER_SELECTED architecture={args.architecture} "
        f"lr={selected_scorer_learning_rate:.6g} steps={selected_scorer} "
        f"score={scorer_selection['selected_aggregate_mean']:.6f}",
        flush=True,
    )
    scorer_wall_seconds = float(time.time() - scorer_started)

    student_runs = []
    student_parameter_counts = set()
    student_parameter_signatures = set()
    student_started = time.time()
    for seed in seeds:
        for method in budget["student_selection_methods"]:
            train_teacher, inner_teacher = _method_teachers(
                method, fitting, held_out, selected_learned[seed],
            )
            for learning_rate in learning_rates:
                began = time.time()

                def student_checkpoint(
                    step, model, trace, *, run_seed=seed,
                    run_method=method, run_learning_rate=learning_rate,
                    fixed_teacher=inner_teacher,
                ):
                    student_parameter_counts.add(sum(
                        parameter.numel() for parameter in model.parameters()
                    ))
                    student_parameter_signatures.add(tuple(
                        (
                            name, tuple(parameter.shape),
                            bool(parameter.requires_grad),
                        )
                        for name, parameter in model.named_parameters()
                    ))
                    metrics = _student_checkpoint_metrics(
                        model, held_out, fixed_teacher,
                        inner_online, inner_groups,
                    )
                    student_runs.append({
                        "seed": int(run_seed),
                        "method": str(run_method),
                        "learning_rate": float(run_learning_rate),
                        "checkpoint": int(step),
                        "auxiliary_weight": float(cfg["auxiliary_weight"]),
                        "selection_stage": "learning_rate_and_updates_at_auxiliary_anchor",
                        "inner_dev_online": metrics,
                        "training_trace": trace,
                    })
                    print(
                        f"STUDENT_CHECKPOINT architecture={args.architecture} "
                        f"seed={run_seed} method={run_method} "
                        f"lr={run_learning_rate:.6g} steps={step} "
                        f"teacher_agreement="
                        f"{metrics['teacher_argmax_agreement']:.6f} "
                        f"reference_accuracy="
                        f"{metrics['reference_accuracy']:.6f}",
                        flush=True,
                    )

                train_student(
                    method, fitting, train_teacher,
                    dict(cfg, learning_rate=float(learning_rate)),
                    seed, device,
                    checkpoint_steps=student_checkpoints,
                    checkpoint_callback=student_checkpoint,
                )
                print(
                    f"STUDENT_PATH_OK seed={seed} method={method} "
                    f"lr={learning_rate:.6g} "
                    f"wall_seconds={time.time()-began:.3f}",
                    flush=True,
                )
        del selected_learned[seed]
        if device.type == "cuda":
            torch.cuda.empty_cache()

    if len(student_parameter_counts) != 1:
        raise AssertionError("A-E student parameter counts differ within architecture")
    if len(student_parameter_signatures) != 1:
        raise AssertionError("A-E student parameter shapes differ within architecture")
    student_parameter_signature = next(iter(student_parameter_signatures))
    student_selections = {}
    student_group_means_by_method = {}
    anchor = budget["shared_diagnostic_anchor"]
    anchor_cell = (
        float(anchor["learning_rate"]), int(anchor["student_updates"]),
    )
    for method in budget["student_selection_methods"]:
        method_group_means = _cell_group_means(
            student_runs,
            metric_key="reference_accuracy_by_group",
            expected_cells=expected_student_cells,
            expected_observations_per_group=len(seeds),
            method=method,
        )
        student_group_means_by_method[method] = method_group_means
        cell_values = {
            cell: list(by_group.values())
            for cell, by_group in method_group_means.items()
        }
        selection = _grid_selection(
            cell_values, maximum_checkpoint=max(student_checkpoints),
        )
        _add_selection_uncertainty(
            selection, method_group_means, uncertainty,
        )
        anchor_score = float(np.mean(cell_values[anchor_cell]))
        selection["shared_diagnostic_anchor"] = {
            "learning_rate": anchor_cell[0],
            "checkpoint": anchor_cell[1],
            "aggregate_mean": anchor_score,
            "own_optimum_minus_anchor": float(
                selection["selected_aggregate_mean"] - anchor_score
            ),
        }
        student_selections[method] = selection

    # D-046 uses a sequential C search. First, C receives exactly the same
    # lr/update grid as A--E at auxiliary weight 1.0. Only after that compute
    # cell is frozen do two additional fixed-compute paths compare 0.1 and 10.
    # This prevents a 36-cell joint search while keeping validation untouched.
    direct_future_method = str(budget_amendment["direct_future_method_name"])
    auxiliary_weights = [
        float(value)
        for value in budget_amendment["direct_future_auxiliary_weights"]
    ]
    auxiliary_anchor = float(
        budget_amendment["direct_future_auxiliary_weight_anchor"]
    )
    c_compute_selection = student_selections[direct_future_method]
    c_selected_learning_rate = float(
        c_compute_selection["selected_learning_rate"]
    )
    c_selected_checkpoint = int(c_compute_selection["selected_checkpoint"])
    auxiliary_weight_runs = [
        {
            "seed": int(run["seed"]),
            "method": direct_future_method,
            "learning_rate": c_selected_learning_rate,
            "checkpoint": c_selected_checkpoint,
            "auxiliary_weight": auxiliary_anchor,
            "selection_stage": "reused_anchor_run_at_fixed_selected_compute",
            "inner_dev_online": run["inner_dev_online"],
            "training_trace_reused_from_learning_rate_updates_grid": True,
        }
        for run in student_runs
        if run["method"] == direct_future_method
        and float(run["learning_rate"]) == c_selected_learning_rate
        and int(run["checkpoint"]) == c_selected_checkpoint
    ]
    for seed in seeds:
        train_teacher, inner_teacher = _method_teachers(
            direct_future_method, fitting, held_out, {},
        )
        for auxiliary_weight in auxiliary_weights:
            if auxiliary_weight == auxiliary_anchor:
                continue
            began = time.time()

            def auxiliary_checkpoint(
                step, model, trace, *, run_seed=seed,
                run_auxiliary_weight=auxiliary_weight,
                fixed_teacher=inner_teacher,
            ):
                student_parameter_counts.add(sum(
                    parameter.numel() for parameter in model.parameters()
                ))
                student_parameter_signatures.add(tuple(
                    (
                        name, tuple(parameter.shape),
                        bool(parameter.requires_grad),
                    )
                    for name, parameter in model.named_parameters()
                ))
                metrics = _student_checkpoint_metrics(
                    model, held_out, fixed_teacher,
                    inner_online, inner_groups,
                )
                auxiliary_weight_runs.append({
                    "seed": int(run_seed),
                    "method": direct_future_method,
                    "learning_rate": c_selected_learning_rate,
                    "checkpoint": int(step),
                    "auxiliary_weight": float(run_auxiliary_weight),
                    "selection_stage": "auxiliary_weight_at_fixed_selected_compute",
                    "inner_dev_online": metrics,
                    "training_trace": trace,
                })
                print(
                    f"C_AUXILIARY_CHECKPOINT architecture={args.architecture} "
                    f"seed={run_seed} lr={c_selected_learning_rate:.6g} "
                    f"steps={step} weight={run_auxiliary_weight:.6g} "
                    f"reference_accuracy={metrics['reference_accuracy']:.6f}",
                    flush=True,
                )

            train_student(
                direct_future_method, fitting, train_teacher,
                dict(
                    cfg,
                    learning_rate=c_selected_learning_rate,
                    student_steps=c_selected_checkpoint,
                    auxiliary_weight=auxiliary_weight,
                ),
                seed, device,
                checkpoint_steps=[c_selected_checkpoint],
                checkpoint_callback=auxiliary_checkpoint,
            )
            print(
                f"C_AUXILIARY_PATH_OK seed={seed} "
                f"lr={c_selected_learning_rate:.6g} "
                f"steps={c_selected_checkpoint} "
                f"weight={auxiliary_weight:.6g} "
                f"wall_seconds={time.time()-began:.3f}",
                flush=True,
            )
        del train_teacher, inner_teacher
        if device.type == "cuda":
            torch.cuda.empty_cache()

    if len(student_parameter_counts) != 1:
        raise AssertionError(
            "C auxiliary paths changed the shared student parameter count"
        )
    if len(student_parameter_signatures) != 1:
        raise AssertionError(
            "C auxiliary paths changed the shared student parameter shapes"
        )
    auxiliary_group_means = _auxiliary_weight_group_means(
        auxiliary_weight_runs,
        expected_weights=auxiliary_weights,
        expected_observations_per_group=len(seeds),
    )
    auxiliary_selection = _auxiliary_weight_selection(
        auxiliary_group_means,
        anchor_weight=auxiliary_anchor,
        uncertainty=uncertainty,
    )
    weight_runner_up = auxiliary_selection["deterministic_runner_up"]
    c_final_selection = {
        "selected_learning_rate": c_selected_learning_rate,
        "selected_checkpoint": c_selected_checkpoint,
        "selected_auxiliary_weight": auxiliary_selection[
            "selected_auxiliary_weight"
        ],
        "selected_aggregate_mean": auxiliary_selection[
            "selected_aggregate_mean"
        ],
        "deterministic_runner_up": (
            {
                "learning_rate": c_selected_learning_rate,
                "checkpoint": c_selected_checkpoint,
                **weight_runner_up,
            }
            if weight_runner_up is not None else None
        ),
        "selected_vs_deterministic_runner_up_paired_bootstrap": (
            auxiliary_selection[
                "selected_vs_deterministic_runner_up_paired_bootstrap"
            ]
        ),
        "tie_break_applied": auxiliary_selection["tie_break_applied"],
        "budget_grid_ceiling_reached": c_compute_selection[
            "budget_grid_ceiling_reached"
        ],
        "ceiling_action": c_compute_selection["ceiling_action"],
        "shared_diagnostic_anchor": c_compute_selection[
            "shared_diagnostic_anchor"
        ],
        "selection_order": list(budget_amendment["selection_order"]),
        "selected_aggregate_mean_at_auxiliary_anchor": c_compute_selection[
            "selected_aggregate_mean"
        ],
        "learning_rate_updates_selection_at_auxiliary_anchor": (
            c_compute_selection
        ),
        "auxiliary_weight_selection_at_fixed_compute": auxiliary_selection,
    }
    student_selections[direct_future_method] = c_final_selection
    print(
        f"C_AUXILIARY_SELECTED architecture={args.architecture} "
        f"lr={c_selected_learning_rate:.6g} steps={c_selected_checkpoint} "
        f"weight={c_final_selection['selected_auxiliary_weight']:.6g} "
        f"score={c_final_selection['selected_aggregate_mean']:.6f}",
        flush=True,
    )

    methods = list(budget["student_selection_methods"])
    shared_group_means = _cell_group_means(
        student_runs,
        metric_key="reference_accuracy_by_group",
        expected_cells=expected_student_cells,
        expected_observations_per_group=len(seeds) * len(methods),
    )
    shared_selection = _grid_selection(
        {
            cell: list(by_group.values())
            for cell, by_group in shared_group_means.items()
        },
        maximum_checkpoint=max(student_checkpoints),
    )
    _add_selection_uncertainty(
        shared_selection, shared_group_means, uncertainty,
    )
    shared_cell = (
        float(shared_selection["selected_learning_rate"]),
        int(shared_selection["selected_checkpoint"]),
    )
    shared_by_method = {
        method: _cell_score(student_group_means_by_method[method], shared_cell)
        for method in methods
    }
    method_specific_scores = {
        method: float(selection["selected_aggregate_mean"])
        for method, selection in student_selections.items()
    }
    primary_method = "cpmt_ctl_core"
    no_execution_method = "future_no_execution"
    primary_cell = (
        float(student_selections[primary_method]["selected_learning_rate"]),
        int(student_selections[primary_method]["selected_checkpoint"]),
    )
    no_execution_cell = (
        float(student_selections[no_execution_method]["selected_learning_rate"]),
        int(student_selections[no_execution_method]["selected_checkpoint"]),
    )

    def a_e_cross_readout(cell: tuple[float, int]) -> dict:
        a_score = _cell_score(
            student_group_means_by_method[primary_method], cell,
        )
        e_score = _cell_score(
            student_group_means_by_method[no_execution_method], cell,
        )
        return {
            "learning_rate": float(cell[0]),
            "checkpoint": int(cell[1]),
            "A_cpmt_ctl_core_reference_accuracy": a_score,
            "E_future_no_execution_reference_accuracy": e_score,
            "A_minus_E": float(a_score - e_score),
        }

    dual_budget_readout = {
        "method_specific": {
            "role": "formal_selected_training_configuration",
            "reference_accuracy_by_method": method_specific_scores,
            "A_minus_C": float(
                method_specific_scores[primary_method]
                - method_specific_scores[direct_future_method]
            ),
            "A_minus_E": float(
                method_specific_scores[primary_method]
                - method_specific_scores[no_execution_method]
            ),
        },
        "shared": {
            "role": "pre_registered_compute_sensitivity_diagnostic",
            "selection": shared_selection,
            "reference_accuracy_by_method": shared_by_method,
            "A_minus_C": float(
                shared_by_method[primary_method]
                - shared_by_method[direct_future_method]
            ),
            "A_minus_E": float(
                shared_by_method[primary_method]
                - shared_by_method[no_execution_method]
            ),
        },
        "cross": {
            "role": "pre_registered_A_E_compute_sensitivity_diagnostic",
            "at_A_selected_cell": a_e_cross_readout(primary_cell),
            "at_E_selected_cell": a_e_cross_readout(no_execution_cell),
        },
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.out_dir / "budget_report.json"
    report = {
        "schema_version": "cpmt-m1-v8-train-inner-dev-budget-v3",
        "post_probe_registration": registration,
        "post_probe_registration_sha256": protocol_sha256(registration),
        "runner": "run_m1_train_inner_dev_budget_v3",
        "formal_run": False,
        "test_generated": False,
        "causal_complete": False,
        "protocol_sha256": active_protocol,
        "dataset_version": hard["data"]["dataset_version"],
        "architecture": args.architecture,
        "architecture_result_selection_forbidden": True,
        "training_provenance": capture_run_provenance(
            PROJECT,
            component="m1_v8_train_inner_dev_budget_selection",
            entrypoint=Path(__file__),
        ),
        "input_arrays": {"train": train_input},
        "partition": {
            "rule": budget["inner_dev_partition"],
            "train_paired_groups": len(unique_groups),
            "fitting_group_ids": fitting_groups,
            "inner_dev_group_ids": inner_group_ids,
            "fitting_learning_rows": int(len(fitting_np["y"])),
            "inner_dev_learning_rows": int(len(inner_np["y"])),
            "inner_dev_online_rows": int(inner_online.sum()),
            "validation_arrays_read": False,
            "validation_trial_consumed": False,
            "test_access": False,
        },
        "registered_source_budget_contract": budget,
        "D046_budget_amendment": budget_amendment,
        "device": {
            "requested": args.device,
            "resolved": device_name,
            "torch_version": torch.__version__,
            "cuda_version": torch.version.cuda,
            "cuda_device": (
                torch.cuda.get_device_name(device) if device.type == "cuda" else None
            ),
            "peak_allocated_mb": (
                float(torch.cuda.max_memory_allocated(device) / 2**20)
                if device.type == "cuda" else None
            ),
            "threads": int(args.threads),
        },
        "parameter_fairness": {
            "student_parameter_count_A_to_E": int(next(iter(student_parameter_counts))),
            "student_parameter_signature_A_to_E": [
                {
                    "name": name,
                    "shape": list(shape),
                    "requires_grad": requires_grad,
                }
                for name, shape, requires_grad in student_parameter_signature
            ],
            "unique_student_parameter_counts": sorted(student_parameter_counts),
            "within_architecture_fractional_difference": 0.0,
            "exact_architecture_shared_A_to_E": True,
            "hyperparameter_search_space_shared_A_to_E": True,
            "selected_hyperparameters_may_differ_by_method": True,
            "registered_tolerance_fraction": float(
                hard["training"]["trainable_parameter_tolerance_fraction"]
            ),
            "outcome_scorer_additional_parameters_for_E": int(
                scorer_parameter_count
            ),
            "learning_rate_updates_grid_cells_per_method": len(
                expected_student_cells
            ),
            "learning_rate_updates_grid_identical_A_to_E_at_auxiliary_anchor": True,
            "C_additional_auxiliary_weight_paths_per_seed": int(
                budget_amendment[
                    "additional_c_auxiliary_weight_paths_per_seed"
                ]
            ),
            "C_joint_lr_updates_auxiliary_weight_grid": False,
            "unregistered_method_specific_grid_expansion": False,
        },
        "scorer": {
            "selection": scorer_selection,
            "runs": scorer_runs,
            "wall_seconds": scorer_wall_seconds,
        },
        "students": {
            "selection_by_method": student_selections,
            "dual_budget_readout": dual_budget_readout,
            "runs": student_runs,
            "C_auxiliary_weight_runs": auxiliary_weight_runs,
            "wall_seconds": float(time.time() - student_started),
        },
        "selected": {
            "outcome_scorer_learning_rate": selected_scorer_learning_rate,
            "outcome_scorer_steps": selected_scorer,
            "student_hyperparameters_by_method": {
                method: {
                    "learning_rate": selection["selected_learning_rate"],
                    "student_steps": selection["selected_checkpoint"],
                    **(
                        {
                            "direct_future_auxiliary_weight": selection[
                                "selected_auxiliary_weight"
                            ]
                        }
                        if method == direct_future_method else {}
                    ),
                    "budget_grid_ceiling_reached": selection[
                        "budget_grid_ceiling_reached"
                    ],
                }
                for method, selection in student_selections.items()
            },
            "direct_future_auxiliary_weight_selection_stage": (
                "train_inner_dev_after_fixed_learning_rate_and_updates"
            ),
        },
    }
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8",
    )
    print(f"BUDGET_REPORT={report_path}", flush=True)
    print(
        f"BUDGET_RUN_OK architecture={args.architecture} "
        f"scorer_lr={selected_scorer_learning_rate:.6g} "
        f"scorer_steps={selected_scorer} "
        f"student_hyperparameters="
        f"{report['selected']['student_hyperparameters_by_method']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
