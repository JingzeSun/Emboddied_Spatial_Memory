"""Fail-closed VM-05 training/validation readiness contract.

The contract distinguishes learned candidate rankers from deterministic
mechanism adapters.  It performs no data access, model construction, training,
validation, configuration search, simulation, or file writes.
"""

from __future__ import annotations

from collections.abc import Mapping
import re
from types import MappingProxyType
from typing import Any

from cpmt.hashing import clone_json


def _freeze_json(value: Any) -> Any:
    """Return a recursively immutable, order-preserving JSON value."""

    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    return value


LEARNED_RANKERS = ("VSMT", "DRCR", "NECS")
DETERMINISTIC_ADAPTERS = ("TAF", "ELU", "WFR", "LOW")
DETERMINISTIC_CONTROLS = ("PHR",)
PAPER_MECHANISM_ADAPTERS = ("TAF", "ELU", "WFR")
PAPER_SYSTEM_MODEL_BOUNDARY_POLICY = (
    "upstream_perception_models_do_not_make_the_adapted_memory_mechanism_a_"
    "trainable_VM05_model"
)
PAPER_SYSTEM_MODEL_BOUNDARIES = _freeze_json({
    "TAF": {
        "source_system": "ConceptGraphs",
        "source_system_uses_pretrained_perception_models": True,
        "adapted_memory_update_is_gradient_trained": False,
        "adaptation_scope": (
            "visual_geometric_association_incremental_fusion_and_periodic_"
            "duplicate_merge"
        ),
    },
    "ELU": {
        "source_system": "Fusion++_and_Dengler_et_al",
        "source_system_uses_pretrained_perception_models": True,
        "adapted_memory_update_is_gradient_trained": False,
        "adaptation_scope": (
            "existence_evidence_update_reliable_negative_observation_and_"
            "identity_lifecycle"
        ),
    },
    "WFR": {
        "source_system": "Khronos",
        "source_system_may_consume_external_or_pretrained_semantic_segmentation": True,
        "adapted_memory_update_is_gradient_trained": False,
        "adaptation_scope": (
            "active_window_fragments_and_periodic_global_reconciliation"
        ),
    },
})
SHARED_FRONTEND_CONTRACT = _freeze_json({
    "method_id": "frozen_DINOv2_and_shared_L1_or_L2_region_geometry_frontend",
    "gradient_updates": False,
    "method_private_perception_models_allowed": False,
    "identical_cached_input_bytes_for_all_methods": True,
})
LEARNED_RANKER_CONTRACT = _freeze_json({
    "methods": LEARNED_RANKERS,
    "requires_gradient_training": True,
    "same_online_architecture_for_all_three": True,
    "differences": {
        "VSMT": "post_execution_candidate_state_and_sealed_hindsight_teacher",
        "DRCR": "direct_reference_equivalence_labels_without_post_execution_teacher",
        "NECS": "sealed_teacher_targets_without_candidate_post_state_or_delta_features",
    },
    "maximum_complete_configurations_per_method": 12,
    "blocking_reason": "freeze_after_VM04_candidate_capacity_and_yield_audit",
})
DETERMINISTIC_ADAPTER_CONTRACT = _freeze_json({
    "methods": DETERMINISTIC_ADAPTERS,
    "requires_gradient_training": False,
    "requires_finite_train_validation_configuration_selection": True,
    "maximum_complete_configurations_per_method": 12,
    "blocking_reason": (
        "freeze_finite_grids_after_VM04_audit_without_confirmation_access"
    ),
})
DETERMINISTIC_CONTROL_CONTRACT = _freeze_json({
    "methods": DETERMINISTIC_CONTROLS,
    "requires_gradient_training": False,
    "requires_finite_train_validation_configuration_selection": True,
    "maximum_complete_configurations_per_method": 12,
    "blocking_reason": (
        "freeze_positive_negative_examples_and_S01_to_S12_consistent_formula"
    ),
})
FAIR_SELECTION_CONTRACT = _freeze_json({
    "same_train_families": True,
    "same_validation_families": True,
    "same_frozen_primary_selection_metric": True,
    "maximum_complete_configurations_per_primary_method": 12,
    "maximum_complete_configurations_per_internal_control": 12,
    "unused_trials_need_not_be_spent": True,
    "failed_configuration_counts_against_cap_unless_infrastructure_failure": True,
    "confirmation_may_not_select_or_change_any_value": True,
    "learned_and_deterministic_methods_are_not_forced_to_share_numeric_parameters": True,
})
MULTI_WORKER_EXECUTION_CONTRACT = _freeze_json({
    "policy": "maximum_safe_parallel_workers_for_every_independent_server_work_unit",
    "minimum_workers_when_at_least_two_independent_units_exist": 2,
    "worker_count_is_selected_by_capacity_probe": True,
    "capacity_inputs": (
        "visible_CPU_cores",
        "free_RAM_bytes",
        "free_GPU_VRAM_bytes",
        "free_data_disk_bytes",
        "measured_single_worker_CPU_RAM_GPU_and_IO",
    ),
    "feature_materialization_partition": "sealed_episode_or_complete_family",
    "deterministic_adapter_grid_partition": "method_configuration_seed_or_family",
    "learned_ranker_partition": "independent_method_configuration_seed_training_job",
    "validation_partition": "sealed_episode_or_complete_family",
    "gpu_policy": (
        "run_the_maximum_number_of_independent_learner_workers_that_a_probe_shows_"
        "fit_safely_and_use_multiple_data_workers_inside_each_learner"
    ),
    "canonical_merge_independent_of_worker_completion_order": True,
    "record_required": (
        "requested_workers",
        "actual_workers",
        "task_partition",
        "worker_pid_or_job_id",
        "worker_exit_code",
        "artifact_sha256",
        "actual_completion_order",
        "canonical_merge_order",
    ),
})
RESOURCE_SAFETY_CONTRACT = _freeze_json({
    "wall_clock_timeout_allowed": False,
    "RAM_safety_check_required": True,
    "GPU_VRAM_safety_check_required": True,
    "disk_free_space_safety_check_required": True,
    "OOM_or_disk_full_may_not_be_used_as_a_capacity_probe": True,
    "scientific_budget_is_frozen_by_samples_configurations_steps_and_stopping_rule_not_elapsed_time": True,
})
PLANNED_STATUS = "planned_blocked_by_vm04_audit_and_numeric_freeze"
EXECUTABLE_STATUS = "frozen_executable"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
EMPTY_FILE_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
REQUIRED_INPUTS = (
    "VM04_verified_two_house_public_and_private_audit_receipt",
    "accepted_candidate_capacity_and_yield_interpretation",
    "frozen_train_validation_family_manifests",
    "frozen_S01_to_S12_selection_semantics",
    "frozen_finite_configuration_spaces",
    "frozen_selector_architecture_optimizer_steps_and_seeds",
    "per_version_template_attribution_for_common_post_update_audit",
    "server_capacity_probe_for_parallel_CPU_and_GPU_jobs",
)
PROHIBITED = (
    "training_before_all_required_inputs_are_bound",
    "using_confirmation_to_select_thresholds_models_or_stopping",
    "giving_TAF_ELU_WFR_or_LOW_a_method_private_visual_frontend",
    "calling_threshold_search_gradient_training",
    "calling_a_pretrained_perception_dependency_a_trained_memory_updater",
    "serial_execution_when_two_or_more_independent_safe_work_units_exist",
    "terminating_a_valid_run_only_because_elapsed_time_exceeded_an_estimate",
)
TOP_LEVEL_KEYS = {
    "version", "status", "decision", "training_authorized",
    "validation_effect_authorized", "confirmation_authorized",
    "wall_clock_timeout_seconds", "shared_frontend", "execution_classes",
    "paper_system_model_boundary", "fair_selection", "multi_worker_execution",
    "resource_safety", "required_inputs_before_executable",
    "satisfied_input_sha256s", "prohibited",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _exact_keys(value: Any, expected: set[str], name: str) -> Mapping[str, Any]:
    _require(type(value) is dict and set(value) == expected,
             f"{name} must contain exactly the registered fields")
    return value


def _require_static_contract(
    value: Mapping[str, Any], expected: Mapping[str, Any], name: str,
    *, dynamic_fields: tuple[str, ...] = (),
) -> None:
    static_value = {key: item for key, item in value.items() if key not in dynamic_fields}
    _require(_freeze_json(static_value) == expected, f"{name} frozen values changed")


def validate_vm05_readiness(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the fixed VM-05 method taxonomy and fail-closed run gates."""

    _require(isinstance(record, Mapping), "VM-05 readiness must be a JSON object")
    value = clone_json(dict(record))
    _exact_keys(value, TOP_LEVEL_KEYS, "VM-05 readiness")
    _require(
        value.get("version") == "vsmt-vm05-training-validation-readiness-v1",
        "wrong VM-05 readiness version",
    )
    _require(value.get("decision") == "D-157", "wrong VM-05 decision binding")
    _require(value["status"] in {PLANNED_STATUS, EXECUTABLE_STATUS},
             "wrong VM-05 readiness status")
    for gate in (
        "training_authorized",
        "validation_effect_authorized",
        "confirmation_authorized",
    ):
        _require(type(value[gate]) is bool, f"{gate} must be boolean")
    _require(value["wall_clock_timeout_seconds"] is None,
             "VM-05 may not use a wall-clock timeout")

    frontend = _exact_keys(value["shared_frontend"], {
        "method_id", "gradient_updates", "method_private_perception_models_allowed",
        "identical_cached_input_bytes_for_all_methods",
    }, "shared_frontend")
    _require_static_contract(frontend, SHARED_FRONTEND_CONTRACT, "shared_frontend")

    classes = _exact_keys(value["execution_classes"], {
        "learned_candidate_rankers", "deterministic_mechanism_adapters",
        "deterministic_internal_control",
    }, "execution_classes")
    learned = _exact_keys(classes["learned_candidate_rankers"], {
        "methods", "requires_gradient_training", "same_online_architecture_for_all_three",
        "differences", "architecture", "optimizer", "training_steps", "seed_count",
        "maximum_complete_configurations_per_method", "blocking_reason",
    }, "learned_candidate_rankers")
    adapters = _exact_keys(classes["deterministic_mechanism_adapters"], {
        "methods", "requires_gradient_training",
        "requires_finite_train_validation_configuration_selection",
        "maximum_complete_configurations_per_method", "configuration_spaces",
        "blocking_reason",
    }, "deterministic_mechanism_adapters")
    controls = _exact_keys(classes["deterministic_internal_control"], {
        "methods", "requires_gradient_training",
        "requires_finite_train_validation_configuration_selection",
        "maximum_complete_configurations_per_method", "decision_formula",
        "blocking_reason",
    }, "deterministic_internal_control")
    _require_static_contract(
        learned, LEARNED_RANKER_CONTRACT, "learned_candidate_rankers",
        dynamic_fields=("architecture", "optimizer", "training_steps", "seed_count"),
    )
    _require_static_contract(
        adapters, DETERMINISTIC_ADAPTER_CONTRACT,
        "deterministic_mechanism_adapters", dynamic_fields=("configuration_spaces",),
    )
    _require_static_contract(
        controls, DETERMINISTIC_CONTROL_CONTRACT,
        "deterministic_internal_control", dynamic_fields=("decision_formula",),
    )

    unresolved_values = (
        *(learned[name] for name in (
            "architecture", "optimizer", "training_steps", "seed_count"
        )),
        adapters["configuration_spaces"],
        controls["decision_formula"],
    )
    if value["status"] == PLANNED_STATUS:
        _require(all(value[gate] is False for gate in (
            "training_authorized", "validation_effect_authorized",
            "confirmation_authorized",
        )), "planned VM-05 gates must remain false")
        _require(all(item is None for item in unresolved_values),
                 "planned VM-05 scientific values must remain explicitly null")
        _require(value["satisfied_input_sha256s"] == {},
                 "planned VM-05 may not claim satisfied prerequisite inputs")
    else:
        _require(type(learned["architecture"]) is dict and learned["architecture"],
                 "frozen VM-05 architecture must be a nonempty object")
        _require(type(learned["optimizer"]) is dict and learned["optimizer"],
                 "frozen VM-05 optimizer must be a nonempty object")
        _require(type(learned["training_steps"]) is int
                 and learned["training_steps"] >= 1,
                 "frozen VM-05 training_steps must be an integer >= 1")
        _require(type(learned["seed_count"]) is int and learned["seed_count"] >= 1,
                 "frozen VM-05 seed_count must be an integer >= 1")
        _require(type(adapters["configuration_spaces"]) is dict
                 and adapters["configuration_spaces"],
                 "frozen adapter configuration_spaces must be a nonempty object")
        _require(type(controls["decision_formula"]) is dict
                 and controls["decision_formula"],
                 "frozen PHR decision_formula must be a nonempty object")
        satisfied = value["satisfied_input_sha256s"]
        _require(type(satisfied) is dict and set(satisfied) == set(REQUIRED_INPUTS),
                 "frozen VM-05 must bind every required input")
        _require(all(type(digest) is str and HEX64.fullmatch(digest) is not None
                     for digest in satisfied.values()),
                 "every satisfied VM-05 input must bind a lowercase SHA-256")
        _require(EMPTY_FILE_SHA256 not in satisfied.values(),
                 "a satisfied VM-05 input may not bind the empty-file SHA-256")
        _require(len(set(satisfied.values())) == len(REQUIRED_INPUTS),
                 "satisfied VM-05 inputs must bind distinct SHA-256 values")

    paper_boundary = _exact_keys(value["paper_system_model_boundary"], {
        *PAPER_MECHANISM_ADAPTERS, "policy",
    }, "paper_system_model_boundary")
    _require(paper_boundary["policy"] == PAPER_SYSTEM_MODEL_BOUNDARY_POLICY,
             "paper system/model boundary policy changed")
    _require(
        _freeze_json({method: paper_boundary[method]
                      for method in PAPER_MECHANISM_ADAPTERS})
        == PAPER_SYSTEM_MODEL_BOUNDARIES,
        "paper system/model boundaries changed",
    )

    fair = _exact_keys(value["fair_selection"], {
        "same_train_families", "same_validation_families",
        "same_frozen_primary_selection_metric",
        "maximum_complete_configurations_per_primary_method",
        "maximum_complete_configurations_per_internal_control",
        "unused_trials_need_not_be_spent",
        "failed_configuration_counts_against_cap_unless_infrastructure_failure",
        "confirmation_may_not_select_or_change_any_value",
        "learned_and_deterministic_methods_are_not_forced_to_share_numeric_parameters",
    }, "fair_selection")
    _require_static_contract(fair, FAIR_SELECTION_CONTRACT, "fair_selection")

    workers = _exact_keys(value["multi_worker_execution"], {
        "policy", "minimum_workers_when_at_least_two_independent_units_exist",
        "worker_count_is_selected_by_capacity_probe", "capacity_inputs",
        "feature_materialization_partition", "deterministic_adapter_grid_partition",
        "learned_ranker_partition", "validation_partition", "gpu_policy",
        "canonical_merge_independent_of_worker_completion_order", "record_required",
    }, "multi_worker_execution")
    _require_static_contract(
        workers, MULTI_WORKER_EXECUTION_CONTRACT, "multi_worker_execution",
    )
    safety = _exact_keys(value["resource_safety"], {
        "wall_clock_timeout_allowed", "RAM_safety_check_required",
        "GPU_VRAM_safety_check_required", "disk_free_space_safety_check_required",
        "OOM_or_disk_full_may_not_be_used_as_a_capacity_probe",
        "scientific_budget_is_frozen_by_samples_configurations_steps_and_stopping_rule_not_elapsed_time",
    }, "resource_safety")
    _require_static_contract(safety, RESOURCE_SAFETY_CONTRACT, "resource_safety")
    _require(tuple(value["required_inputs_before_executable"]) == REQUIRED_INPUTS,
             "VM-05 prerequisite list changed")
    _require(tuple(value["prohibited"]) == PROHIBITED,
             "VM-05 prohibited-action list changed")
    return value


def assert_vm05_action_authorized(
    record: Mapping[str, Any], *, action: str,
) -> dict[str, Any]:
    """Authorize only a later reviewed, fully resolved frozen configuration."""

    value = validate_vm05_readiness(record)
    gates = {
        "train": "training_authorized",
        "validate": "validation_effect_authorized",
        "confirm": "confirmation_authorized",
    }
    _require(action in gates, f"unknown VM-05 action: {action}")
    _require(value["status"] == EXECUTABLE_STATUS,
             "VM-05 status is not frozen_executable")
    _require(value[gates[action]] is True, f"VM-05 {action} is not authorized")
    return value
