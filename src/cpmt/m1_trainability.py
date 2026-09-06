"""Trainability diagnostics before expanding the controlled M1 candidate set.

This module is deliberately nonformal and test-sealed.  It separates three
questions: whether the small online student can fit observable training cases,
whether more updates/data improve held-out behavior, and whether residual error
comes from candidate coverage, the offline teacher, or student amortization.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

import numpy as np
import torch
from torch.nn import functional as F

from .dev_learning import (
    OnlineModel,
    candidate_admissibility_mask,
    masked_candidate_probabilities,
    train_student,
    tensors,
)
from .hashing import clone_json
from .m1_af_rollout import (
    _teacher_forced_metrics,
    selection_error_decomposition,
    causal_rollout_metrics,
    resolve_af_smoke_config,
    run_af_seed,
)


TEACHER_SOURCES = {
    "cpmt_ctl_core": "executed_hindsight_posterior",
    "direct_classifier": "label_only_no_soft_teacher",
    "direct_future_loss": "label_plus_future_auxiliary_no_soft_teacher",
    "execute_current_only": "executed_current_only_posterior",
    "future_no_execution": "learned_outcome_scorer_posterior",
    "oracle_candidate_program": "audit_reference_index_upper_bound",
}


def resolve_trainability_ladder(
    hard_config: Mapping[str, Any], af_smoke_config: Mapping[str, Any],
    ladder_config: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate a nonformal trainability ladder and attach the A-F base config."""
    base = resolve_af_smoke_config(hard_config, af_smoke_config)
    ladder = deepcopy(dict(ladder_config))
    if (
        ladder.get("protocol") != "m1-trainability-ladder-v1"
        or ladder.get("stage") != "M1-development"
        or ladder.get("formal_run") is not False
        or ladder.get("test_access") is not False
    ):
        raise ValueError("trainability ladder must remain nonformal and test-sealed")
    if int(ladder.get("seed", -1)) < 0:
        raise ValueError("trainability seed must be nonnegative")
    maximum = int(ladder.get("max_train_paired_groups", 0))
    validation_groups = int(ladder.get("validation_paired_groups", 0))
    if maximum <= 0 or validation_groups <= 0:
        raise ValueError("trainability paired-group counts must be positive")
    points = ladder.get("optimization_curve", [])
    if not points:
        raise ValueError("trainability optimization curve must be nonempty")
    names = set()
    for point in points:
        groups = int(point.get("train_paired_groups", 0))
        steps = int(point.get("student_steps", 0))
        if groups <= 0 or groups > maximum or steps <= 0:
            raise ValueError("invalid trainability optimization point")
        name = f"g{groups}_s{steps}"
        if name in names:
            raise ValueError("duplicate trainability optimization point")
        names.add(name)
    capacity = ladder.get("label_rich_capacity", {})
    if capacity.get("method") != "direct_classifier":
        raise ValueError("capacity diagnostic must use the direct classifier")
    if float(capacity.get("label_fraction", 0.0)) != 1.0:
        raise ValueError("capacity diagnostic must expose all training labels")
    capacity_groups = int(capacity.get("train_paired_groups", 0))
    capacity_steps = [int(value) for value in capacity.get("student_steps", [])]
    if (
        capacity_groups <= 0 or capacity_groups > maximum
        or not capacity_steps or any(value <= 0 for value in capacity_steps)
        or len(set(capacity_steps)) != len(capacity_steps)
    ):
        raise ValueError("invalid label-rich capacity ladder")
    for name in ("identifiable_accuracy_required", "ceiling_gap_allowed"):
        value = float(capacity.get(name, -1.0))
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"invalid capacity criterion {name}")
    ladder["base_af_config"] = base
    return ladder


def subset_paired_groups(
    arrays: Mapping[str, np.ndarray], audits: Sequence[Mapping[str, Any]],
    paired_groups: int,
) -> tuple[dict[str, np.ndarray], list[Mapping[str, Any]]]:
    """Take a deterministic prefix of complete paired groups without splitting siblings."""
    names = sorted({str(audit["paired_group_id"]) for audit in audits})
    if paired_groups <= 0 or paired_groups > len(names):
        raise ValueError("paired-group subset is outside available data")
    selected_names = set(names[:paired_groups])
    selected_audits = [
        audit for audit in audits
        if str(audit["paired_group_id"]) in selected_names
    ]
    counts = {
        name: sum(str(audit["paired_group_id"]) == name for audit in selected_audits)
        for name in selected_names
    }
    if set(counts.values()) != {2}:
        raise AssertionError("paired-group subset split one or more siblings")
    subset = subset_paired_array_groups(arrays, paired_groups)
    return subset, selected_audits


def subset_paired_array_groups(
    arrays: Mapping[str, np.ndarray], paired_groups: int,
) -> dict[str, np.ndarray]:
    """Take a deterministic prefix of complete tensor groups without audit objects."""
    groups = np.asarray(arrays["group"])
    row_count = len(groups)
    for key, value in arrays.items():
        if len(np.asarray(value)) != row_count:
            raise AssertionError(
                f"paired-group tensor {key!r} has an inconsistent row count"
            )
    available_group_ids = sorted(set(int(value) for value in groups))
    if paired_groups <= 0 or paired_groups > len(available_group_ids):
        raise ValueError("paired-array subset is outside available data")
    selected_group_ids = set(available_group_ids[:paired_groups])
    source_counts = {
        group_id: int(np.sum(groups == group_id))
        for group_id in available_group_ids
    }
    if len(set(source_counts.values())) != 1:
        raise AssertionError("source paired groups have inconsistent row counts")
    mask = np.asarray([
        int(group) in selected_group_ids for group in groups
    ], dtype=bool)
    subset = {key: np.asarray(value)[mask].copy() for key, value in arrays.items()}
    counts = [
        int(np.sum(np.asarray(subset["group"]) == group_id))
        for group_id in selected_group_ids
    ]
    if len(set(counts)) != 1:
        raise AssertionError("paired-group tensor subset split a group")
    if "recovery" in subset:
        if "ambiguous" not in subset:
            raise AssertionError(
                "recovery-aware paired arrays require the ambiguous row label"
            )
        recovery = np.asarray(subset["recovery"], dtype=bool)
        ambiguity = np.asarray(subset["ambiguous"], dtype=bool)
        for group_id in selected_group_ids:
            group_mask = np.asarray(subset["group"]) == group_id
            ambiguity_rows = int(np.sum(group_mask & ambiguity & ~recovery))
            recovery_rows = int(np.sum(group_mask & recovery))
            if ambiguity_rows != 2:
                raise AssertionError(
                    "paired group must retain one online ambiguity pivot per sibling"
                )
            if recovery_rows != ambiguity_rows:
                raise AssertionError(
                    "paired group must retain one bounded recovery row per pivot"
                )
    remap = {old: new for new, old in enumerate(sorted(selected_group_ids))}
    subset["group"] = np.asarray([
        remap[int(group)] for group in subset["group"]
    ], dtype=np.int64)
    return subset


def reference_candidate_audit(
    audits: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Report whether each stored reference exists and is legally executable."""
    total = 0
    covered = 0
    illegal_reference = 0
    family_totals: dict[str, int] = {}
    family_covered: dict[str, int] = {}
    candidate_counts: list[int] = []
    generators: set[str] = set()
    for audit in audits:
        for step in audit["steps"]:
            total += 1
            family = str(step["scenario_family"])
            family_totals[family] = family_totals.get(family, 0) + 1
            candidate_counts.append(len(step["executed_candidates"]))
            generation = step.get("candidate_generation", {})
            if generation.get("generator"):
                generators.add(str(generation["generator"]))
            index = int(step["reference_program_index"])
            candidates = step["executed_candidates"]
            if 0 <= index < len(candidates):
                covered += 1
                family_covered[family] = family_covered.get(family, 0) + 1
                if not bool(candidates[index]["legal"]):
                    illegal_reference += 1
    if total == 0:
        raise ValueError("candidate audit requires at least one decision")
    family_coverage = {
        family: float(family_covered.get(family, 0) / count)
        for family, count in sorted(family_totals.items())
    }
    return {
        "decisions": float(total),
        "candidate_reference_coverage": float(covered / total),
        "candidate_miss_rate": float(1.0 - covered / total),
        "illegal_reference_rate": float(illegal_reference / total),
        "coverage_by_family": family_coverage,
        "support_by_family": dict(sorted(family_totals.items())),
        "minimum_family_coverage": min(family_coverage.values()),
        "candidate_count_min": min(candidate_counts),
        "candidate_count_max": max(candidate_counts),
        "candidate_generators": sorted(generators),
    }


def observable_accuracy_ceiling(arrays: Mapping[str, np.ndarray]) -> float:
    """Return the deterministic ceiling induced by exact paired contradictions."""
    ambiguous = np.asarray(arrays["ambiguous"], dtype=float)
    online = ~np.asarray(
        arrays.get("recovery", np.zeros(len(ambiguous), dtype=bool)), dtype=bool,
    )
    ambiguous_fraction = float(ambiguous[online].mean())
    return 1.0 - 0.5 * ambiguous_fraction


def run_label_rich_capacity_point(
    arrays: Mapping[str, np.ndarray], audits: Sequence[Mapping[str, Any]],
    base_config: Mapping[str, Any], *, student_steps: int, seed: int,
) -> tuple[dict[str, Any], dict[str, Any], OnlineModel]:
    """Fit the direct classifier on all observable training labels and replay causally."""
    labelled_arrays = {key: np.asarray(value).copy() for key, value in arrays.items()}
    labelled_arrays["labelled"] = np.ones_like(labelled_arrays["labelled"], dtype=bool)
    config = deepcopy(dict(base_config))
    config["student_steps"] = int(student_steps)
    device = torch.device(config["device"])
    train = tensors(labelled_arrays, device)
    candidate_count = int(train["penalties"].shape[1])
    target_teacher = F.one_hot(train["y"], candidate_count).float()
    model, trace = train_student(
        "direct_classifier", train, target_teacher, config, int(seed), device,
    )
    with torch.no_grad():
        logits = model(train["x"])
        probabilities = masked_candidate_probabilities(
            logits, candidate_admissibility_mask(train, logits),
        ).cpu().numpy()
    teacher_forced = _teacher_forced_metrics(probabilities, train, target_teacher)
    selection = selection_error_decomposition(probabilities, labelled_arrays)
    teacher_forced["online_chain_accuracy"] = float(
        selection["online_chain_accuracy"]
    )
    causal, causal_rows = causal_rollout_metrics(model, audits, config)
    ceiling = observable_accuracy_ceiling(labelled_arrays)
    metrics = {
        "student_steps": int(student_steps),
        "label_fraction": 1.0,
        "observable_accuracy_ceiling": ceiling,
        "ceiling_gap": float(
            ceiling - teacher_forced["online_chain_accuracy"]
        ),
        "teacher_forced": teacher_forced,
        "selection_error": selection,
        "causal_rollout": causal,
        "student_parameters": sum(parameter.numel() for parameter in model.parameters()),
    }
    details = {"training_trace": trace, "causal_sequences": causal_rows}
    return metrics, details, model


def error_decomposition(results: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Separate teacher and student errors while marking methods without a soft teacher."""
    rows = {}
    for method, result in results.items():
        teacher_forced = result["teacher_forced"]
        teacher_used = method in {
            "cpmt_ctl_core", "execute_current_only", "future_no_execution",
        }
        rows[method] = {
            "teacher_source": TEACHER_SOURCES[method],
            "soft_teacher_used_for_student": teacher_used,
            "teacher_error": (
                float(1.0 - teacher_forced["teacher_accuracy"])
                if teacher_used else None
            ),
            "amortization_error": (
                float(teacher_forced["amortization_error"])
                if teacher_used else None
            ),
            "target_error": float(1.0 - teacher_forced["accuracy"]),
            "causal_final_error": float(
                1.0 - result["causal_rollout"][
                    "final_active_graph_correctness"
                ]
            ),
        }
    return rows


def run_optimization_point(
    train_arrays: Mapping[str, np.ndarray], validation_arrays: Mapping[str, np.ndarray],
    validation_audits: Sequence[Mapping[str, Any]], base_config: Mapping[str, Any],
    *, student_steps: int, seed: int,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, torch.nn.Module]]:
    """Run one matched A-F diagnostic point and attach an error decomposition."""
    config = deepcopy(dict(base_config))
    config["student_steps"] = int(student_steps)
    config["scorer_steps"] = int(student_steps)
    results, details, models = run_af_seed(
        train_arrays, validation_arrays, validation_audits, config, int(seed),
    )
    return {
        "student_steps": int(student_steps),
        "results": results,
        "error_decomposition": error_decomposition(results),
    }, details, models
