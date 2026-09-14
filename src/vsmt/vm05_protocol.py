"""Fail-closed VM-05 training/validation readiness contract.

The contract distinguishes learned candidate rankers from deterministic
mechanism adapters.  It performs no data access, model construction, training,
validation, configuration search, simulation, or file writes.
"""

from __future__ import annotations

from typing import Any, Mapping


LEARNED_RANKERS = ("VSMT", "DRCR", "NECS")
DETERMINISTIC_ADAPTERS = ("TAF", "ELU", "WFR", "LOW")
DETERMINISTIC_CONTROLS = ("PHR",)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_vm05_readiness(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the fixed VM-05 method taxonomy and fail-closed run gates."""

    value = dict(record)
    _require(
        value.get("version") == "vsmt-vm05-training-validation-readiness-v1",
        "wrong VM-05 readiness version",
    )
    _require(value.get("decision") == "D-157", "wrong VM-05 decision binding")
    for gate in (
        "training_authorized",
        "validation_effect_authorized",
        "confirmation_authorized",
    ):
        _require(value.get(gate) is False, f"{gate} must remain false")
    _require(value.get("wall_clock_timeout_seconds") is None,
             "VM-05 may not use a wall-clock timeout")

    frontend = value.get("shared_frontend", {})
    _require(frontend.get("gradient_updates") is False,
             "shared frontend must remain frozen")
    _require(frontend.get("method_private_perception_models_allowed") is False,
             "method-private perception is forbidden")
    _require(frontend.get("identical_cached_input_bytes_for_all_methods") is True,
             "all methods require identical cached frontend bytes")

    classes = value.get("execution_classes", {})
    learned = classes.get("learned_candidate_rankers", {})
    adapters = classes.get("deterministic_mechanism_adapters", {})
    controls = classes.get("deterministic_internal_control", {})
    _require(tuple(learned.get("methods", ())) == LEARNED_RANKERS,
             "learned ranker set or order changed")
    _require(learned.get("requires_gradient_training") is True,
             "learned rankers require gradient training")
    _require(learned.get("same_online_architecture_for_all_three") is True,
             "learned controls must share the VSMT online architecture")
    for unresolved in ("architecture", "optimizer", "training_steps", "seed_count"):
        _require(learned.get(unresolved) is None,
                 f"{unresolved} must remain unresolved before audit freeze")

    _require(tuple(adapters.get("methods", ())) == DETERMINISTIC_ADAPTERS,
             "deterministic adapter set or order changed")
    _require(adapters.get("requires_gradient_training") is False,
             "mechanism adapters may not be relabeled as trained models")
    _require(adapters.get("requires_finite_train_validation_configuration_selection") is True,
             "mechanism adapters still require finite configuration selection")
    _require(adapters.get("maximum_complete_configurations_per_method") == 12,
             "deterministic adapter configuration cap changed")
    _require(adapters.get("configuration_spaces") is None,
             "configuration grids may not be invented before audit freeze")

    _require(tuple(controls.get("methods", ())) == DETERMINISTIC_CONTROLS,
             "deterministic control set changed")
    _require(controls.get("requires_gradient_training") is False,
             "PHR may not receive gradient training")
    _require(controls.get("decision_formula") is None,
             "PHR formula is not frozen")

    paper_boundary = value.get("paper_system_model_boundary", {})
    for method in DETERMINISTIC_ADAPTERS[:-1]:
        row = paper_boundary.get(method, {})
        _require(row.get("adapted_memory_update_is_gradient_trained") is False,
                 f"{method} memory adaptation is mechanism-only")

    fair = value.get("fair_selection", {})
    _require(fair.get("maximum_complete_configurations_per_primary_method") == 12,
             "fair primary-method trial cap changed")
    _require(fair.get("confirmation_may_not_select_or_change_any_value") is True,
             "confirmation selection is forbidden")

    workers = value.get("multi_worker_execution", {})
    _require(workers.get("minimum_workers_when_at_least_two_independent_units_exist") == 2,
             "VM-05 requires multiple workers")
    _require(workers.get("worker_count_is_selected_by_capacity_probe") is True,
             "worker count needs a capacity probe")
    _require(workers.get("canonical_merge_independent_of_worker_completion_order") is True,
             "parallel output requires canonical merging")
    safety = value.get("resource_safety", {})
    _require(safety.get("wall_clock_timeout_allowed") is False,
             "wall-clock timeout must stay disabled")
    _require(all(safety.get(name) is True for name in (
        "RAM_safety_check_required",
        "GPU_VRAM_safety_check_required",
        "disk_free_space_safety_check_required",
    )), "RAM, VRAM and disk safety checks are mandatory")
    _require(type(value.get("required_inputs_before_executable")) is list
             and len(value["required_inputs_before_executable"]) == 8,
             "VM-05 prerequisite list changed")
    return value


def assert_vm05_action_authorized(
    record: Mapping[str, Any], *, action: str,
) -> dict[str, Any]:
    """Reject every effectful VM-05 action until a later reviewed freeze."""

    value = validate_vm05_readiness(record)
    gates = {
        "train": "training_authorized",
        "validate": "validation_effect_authorized",
        "confirm": "confirmation_authorized",
    }
    _require(action in gates, f"unknown VM-05 action: {action}")
    _require(value[gates[action]] is True, f"VM-05 {action} is not authorized")
    return value
