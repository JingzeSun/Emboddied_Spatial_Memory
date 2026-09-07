"""Select one scorer and one shared A-E student budget from train only.

This v8 S1/S2 entrypoint reads exactly the registered 1,000 mixed train
paired groups, holds out complete groups with the frozen SHA-256 rule, and
evaluates the three registered checkpoints on one identical seeded training
trajectory. It handles one architecture arm per invocation. It never reads
validation/test, calibrates a commit gate, runs causal evaluation, or chooses
between the Set Transformer and MLP arms.
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
from cpmt.m1_protocol import load_and_validate, protocol_sha256  # noqa: E402
from cpmt.run_provenance import arrays_sha256, capture_run_provenance  # noqa: E402


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
        "--architecture", required=True,
        choices=(
            "cross_candidate_set_transformer_v1",
            "shared_candidate_mlp_v1",
        ),
    )
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--threads", type=int, default=16)
    args = parser.parse_args()

    hard = load_and_validate(args.config)
    budget = hard["training"]["pretest_budget_selection"]
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
    cfg = dict(
        smoke,
        **_architecture_settings(hard, args.architecture),
        horizon=int(hard["future"]["primary_horizon"]),
        learning_rate=float(budget["learning_rate"]),
        batch_size=int(budget["batch_size"]),
        device=device_name,
        scorer_steps=max(scorer_checkpoints),
        student_steps=max(student_checkpoints),
        distillation_weight=1.0,
        auxiliary_weight=float(budget["direct_future_auxiliary_weight_anchor"]),
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
    print(
        f"BUDGET_RUN_BEGIN architecture={args.architecture} device={device_name} "
        f"groups={len(unique_groups)} fitting={len(fitting_groups)} "
        f"inner_dev={len(inner_group_ids)} seeds={seeds}",
        flush=True,
    )

    scorer_runs = []
    learned_cache: dict[int, dict[int, dict[str, torch.Tensor]]] = {}
    scorer_parameter_count = None
    scorer_started = time.time()
    for seed in seeds:
        learned_cache[seed] = {}
        began = time.time()

        def scorer_checkpoint(step, model, teachers, trace, *, run_seed=seed):
            nonlocal scorer_parameter_count
            parameter_count = sum(parameter.numel() for parameter in model.parameters())
            if scorer_parameter_count is None:
                scorer_parameter_count = parameter_count
            elif scorer_parameter_count != parameter_count:
                raise AssertionError("scorer parameter count changed across checkpoints")
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
                "checkpoint": int(step),
                "inner_dev_online": diagnostics,
                "reference_candidate_ranking_accuracy_by_group": per_group,
                "training_trace": trace,
            })
            learned_cache[run_seed][int(step)] = {
                name: value.detach().cpu().clone()
                for name, value in teachers.items()
            }
            print(
                f"SCORER_CHECKPOINT architecture={args.architecture} "
                f"seed={run_seed} steps={step} "
                f"inner_dev_accuracy={diagnostics['teacher_accuracy']:.6f} "
                f"inner_dev_bce={diagnostics['masked_bce']:.6f}",
                flush=True,
            )

        train_outcome_scorer(
            fitting, held_out, cfg, seed, device,
            checkpoint_steps=scorer_checkpoints,
            checkpoint_callback=scorer_checkpoint,
        )
        print(
            f"SCORER_SEED_OK seed={seed} wall_seconds={time.time()-began:.3f}",
            flush=True,
        )

    scorer_values = {step: [] for step in scorer_checkpoints}
    for run in scorer_runs:
        scorer_values[int(run["checkpoint"])].extend(
            run["reference_candidate_ranking_accuracy_by_group"].values()
        )
    scorer_selection = _checkpoint_selection(scorer_values)
    selected_scorer = int(scorer_selection["selected_checkpoint"])
    selected_learned = {
        seed: {
            name: tensor.to(device)
            for name, tensor in learned_cache[seed][selected_scorer].items()
        }
        for seed in seeds
    }
    del learned_cache
    print(
        f"SCORER_SELECTED architecture={args.architecture} steps={selected_scorer} "
        f"score={scorer_selection['selected_aggregate_mean']:.6f}",
        flush=True,
    )
    scorer_wall_seconds = float(time.time() - scorer_started)

    student_runs = []
    student_parameter_counts = set()
    student_started = time.time()
    for seed in seeds:
        for method in budget["student_selection_methods"]:
            train_teacher, inner_teacher = _method_teachers(
                method, fitting, held_out, selected_learned[seed],
            )
            began = time.time()

            def student_checkpoint(step, model, trace, *, run_seed=seed,
                                   run_method=method,
                                   fixed_teacher=inner_teacher):
                student_parameter_counts.add(sum(
                    parameter.numel() for parameter in model.parameters()
                ))
                metrics = _student_checkpoint_metrics(
                    model, held_out, fixed_teacher, inner_online, inner_groups,
                )
                student_runs.append({
                    "seed": int(run_seed),
                    "method": str(run_method),
                    "checkpoint": int(step),
                    "inner_dev_online": metrics,
                    "training_trace": trace,
                })
                print(
                    f"STUDENT_CHECKPOINT architecture={args.architecture} "
                    f"seed={run_seed} method={run_method} steps={step} "
                    f"teacher_agreement={metrics['teacher_argmax_agreement']:.6f} "
                    f"reference_accuracy={metrics['reference_accuracy']:.6f}",
                    flush=True,
                )

            train_student(
                method, fitting, train_teacher, cfg, seed, device,
                checkpoint_steps=student_checkpoints,
                checkpoint_callback=student_checkpoint,
            )
            print(
                f"STUDENT_PATH_OK seed={seed} method={method} "
                f"wall_seconds={time.time()-began:.3f}",
                flush=True,
            )
        del selected_learned[seed]
        if device.type == "cuda":
            torch.cuda.empty_cache()

    if len(student_parameter_counts) != 1:
        raise AssertionError("A-E student parameter counts differ within architecture")
    student_values = {step: [] for step in student_checkpoints}
    student_method_means = {step: {} for step in student_checkpoints}
    for step in student_checkpoints:
        for method in budget["student_selection_methods"]:
            values = []
            for run in student_runs:
                if run["checkpoint"] == step and run["method"] == method:
                    values.extend(run["inner_dev_online"][
                        "teacher_argmax_agreement_by_group"
                    ].values())
            if not values:
                raise AssertionError("student checkpoint grid is incomplete")
            student_method_means[step][method] = float(np.mean(values))
            student_values[step].append(student_method_means[step][method])
    student_selection = _checkpoint_selection(student_values)
    student_selection["method_equal_weight_mean_by_checkpoint"] = {
        str(step): student_method_means[step] for step in student_checkpoints
    }
    selected_student = int(student_selection["selected_checkpoint"])

    args.out_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.out_dir / "budget_report.json"
    report = {
        "schema_version": "cpmt-m1-v8-train-inner-dev-budget-v1",
        "runner": "run_m1_train_inner_dev_budget_v1",
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
        "registered_contract": budget,
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
            "unique_student_parameter_counts": sorted(student_parameter_counts),
            "within_architecture_fractional_difference": 0.0,
            "registered_tolerance_fraction": float(
                hard["training"]["trainable_parameter_tolerance_fraction"]
            ),
            "outcome_scorer_additional_parameters_for_E": int(
                scorer_parameter_count
            ),
        },
        "scorer": {
            "selection": scorer_selection,
            "runs": scorer_runs,
            "wall_seconds": scorer_wall_seconds,
        },
        "students": {
            "selection": student_selection,
            "runs": student_runs,
            "wall_seconds": float(time.time() - student_started),
        },
        "selected": {
            "outcome_scorer_steps": selected_scorer,
            "student_steps_shared_A_to_E": selected_student,
            "direct_future_auxiliary_weight_anchor_only": float(
                budget["direct_future_auxiliary_weight_anchor"]
            ),
        },
    }
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8",
    )
    print(f"BUDGET_REPORT={report_path}", flush=True)
    print(
        f"BUDGET_RUN_OK architecture={args.architecture} "
        f"scorer_steps={selected_scorer} student_steps={selected_student}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
