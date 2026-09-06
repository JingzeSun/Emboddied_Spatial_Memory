"""Isolated single-method execution for the nonformal M1 A-F diagnostic.

The full A-F comparison still uses matched data, seeds, student architecture,
and update counts.  This module only shortens the failure domain: one process
trains and causally evaluates one registered method before writing a complete
result, so a later process failure cannot erase earlier methods.
"""
from __future__ import annotations

import time
from typing import Any, Mapping, Sequence

import numpy as np
import torch
from torch.nn import functional as F

from .dev_learning import (
    METHODS,
    apply_candidate_admissibility_to_probabilities,
    candidate_admissibility_mask,
    masked_candidate_probabilities,
    train_outcome_scorer,
    train_student,
    tensors,
)
from .m1_af_rollout import _teacher_forced_metrics, causal_rollout_metrics


def run_af_method(
    train_np: Mapping[str, np.ndarray],
    validation_np: Mapping[str, np.ndarray],
    validation_audits: Sequence[Mapping[str, Any]],
    smoke_config: Mapping[str, Any],
    seed: int,
    method: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, torch.nn.Module]]:
    """Train and evaluate exactly one registered A-F method.

    Input is the same train/validation arrays and causal validation sequences
    used by the joint runner.  Output is one method's metrics, detailed trace,
    and any learned modules.  For example, the E worker trains its outcome
    scorer and matched online student, while the F worker only replays the
    audit reference index.  This is process isolation, not a different method,
    extra supervision, checkpoint selection, or permission to read test.
    """
    if method not in METHODS:
        raise ValueError(f"unknown A-F method {method!r}")
    device = torch.device(smoke_config["device"])
    train = tensors(dict(train_np), device)
    validation = tensors(dict(validation_np), device)
    models: dict[str, torch.nn.Module] = {}

    if method == "oracle_candidate_program":
        candidate_count = int(validation["penalties"].shape[1])
        probabilities = np.eye(candidate_count, dtype=np.float32)[
            validation["y"].detach().cpu().numpy()
        ]
        teacher = F.one_hot(validation["y"], candidate_count).float()
        teacher_metrics = _teacher_forced_metrics(
            probabilities, validation, teacher,
        )
        causal, causal_rows = causal_rollout_metrics(
            None, validation_audits, smoke_config, oracle=True,
        )
        return {
            "teacher_forced": teacher_metrics,
            "causal_rollout": causal,
            "student_parameters": 0,
            "additional_scorer_parameters": 0,
            "student_seconds": 0.0,
            "oracle_upper_bound": True,
        }, {"training_trace": [], "causal_sequences": causal_rows}, models

    scorer_parameters = 0
    scorer_trace: list[dict[str, Any]] = []
    if method == "future_no_execution":
        scorer, learned_teachers, scorer_trace = train_outcome_scorer(
            train, validation, dict(smoke_config), seed, device,
        )
        scorer_parameters = sum(
            parameter.numel() for parameter in scorer.parameters()
        )
        models["future_no_execution_scorer"] = scorer
        train_teacher = learned_teachers["train"]
        validation_teacher = learned_teachers["validation"]
    elif method == "execute_current_only":
        train_teacher = train["pstar_current"]
        validation_teacher = validation["pstar_current"]
    else:
        train_teacher = train["pstar"]
        validation_teacher = validation["pstar"]
    train_teacher = apply_candidate_admissibility_to_probabilities(
        train_teacher, candidate_admissibility_mask(train, train["penalties"]),
    )
    validation_teacher = apply_candidate_admissibility_to_probabilities(
        validation_teacher,
        candidate_admissibility_mask(validation, validation["penalties"]),
    )

    started = time.perf_counter()
    model, trace = train_student(
        method, train, train_teacher, dict(smoke_config), seed, device,
    )
    seconds = time.perf_counter() - started
    with torch.no_grad():
        logits = model(validation["x"])
        probabilities = masked_candidate_probabilities(
            logits, candidate_admissibility_mask(validation, logits),
        ).cpu().numpy()
    teacher_metrics = _teacher_forced_metrics(
        probabilities, validation, validation_teacher,
    )
    causal, causal_rows = causal_rollout_metrics(
        model, validation_audits, smoke_config,
    )
    models[method] = model
    return {
        "teacher_forced": teacher_metrics,
        "causal_rollout": causal,
        "student_parameters": sum(
            parameter.numel() for parameter in model.parameters()
        ),
        "additional_scorer_parameters": (
            scorer_parameters if method == "future_no_execution" else 0
        ),
        "student_seconds": seconds,
        "oracle_upper_bound": False,
    }, {
        "training_trace": trace,
        "causal_sequences": causal_rows,
        "outcome_scorer_training": scorer_trace,
    }, models
