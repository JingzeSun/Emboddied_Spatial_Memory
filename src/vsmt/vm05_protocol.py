"""Fail-closed VM-05 training/validation readiness contract.

The contract distinguishes learned candidate rankers from deterministic
mechanism adapters.  It performs no data access, model construction, training,
validation, configuration search, simulation, or file writes.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from cpmt.hashing import clone_json


LEARNED_RANKERS = ("VSMT", "DRCR", "NECS")
DETERMINISTIC_ADAPTERS = ("TAF", "ELU", "WFR", "LOW")
DETERMINISTIC_CONTROLS = ("PHR",)
PAPER_MECHANISM_ADAPTERS = ("TAF", "ELU", "WFR")
PAPER_SYSTEM_MODEL_BOUNDARY_POLICY = (
    "upstream_perception_models_do_not_make_the_adapted_memory_mechanism_a_"
    "trainable_VM05_model"
)
PAPER_SYSTEM_MODEL_BOUNDARIES = {
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
}
PLANNED_STATUS = "planned_blocked_by_vm04_audit_and_numeric_freeze"
EXECUTABLE_STATUS = "frozen_executable"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
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


def validate_vm05_readiness(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the fixed VM-05 method taxonomy and fail-closed run gates."""

    _require(type(record) is dict, "VM-05 readiness must be a JSON object")
    value = clone_json(record)
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
    _require(frontend["gradient_updates"] is False,
             "shared frontend must remain frozen")
    _require(frontend["method_private_perception_models_allowed"] is False,
             "method-private perception is forbidden")
    _require(frontend["identical_cached_input_bytes_for_all_methods"] is True,
             "all methods require identical cached frontend bytes")

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
    _require(tuple(learned["methods"]) == LEARNED_RANKERS,
             "learned ranker set or order changed")
    _require(learned["requires_gradient_training"] is True,
             "learned rankers require gradient training")
    _require(learned["same_online_architecture_for_all_three"] is True,
             "learned controls must share the VSMT online architecture")
    _require(learned["maximum_complete_configurations_per_method"] == 12,
             "learned ranker configuration cap changed")

    _require(tuple(adapters["methods"]) == DETERMINISTIC_ADAPTERS,
             "deterministic adapter set or order changed")
    _require(adapters["requires_gradient_training"] is False,
             "mechanism adapters may not be relabeled as trained models")
    _require(adapters["requires_finite_train_validation_configuration_selection"] is True,
             "mechanism adapters still require finite configuration selection")
    _require(adapters["maximum_complete_configurations_per_method"] == 12,
             "deterministic adapter configuration cap changed")

    _require(tuple(controls["methods"]) == DETERMINISTIC_CONTROLS,
             "deterministic control set changed")
    _require(controls["requires_gradient_training"] is False,
             "PHR may not receive gradient training")
    _require(controls["requires_finite_train_validation_configuration_selection"] is True,
             "PHR still requires finite configuration selection")
    _require(controls["maximum_complete_configurations_per_method"] == 12,
             "PHR configuration cap changed")

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

    paper_boundary = _exact_keys(value["paper_system_model_boundary"], {
        *PAPER_MECHANISM_ADAPTERS, "policy",
    }, "paper_system_model_boundary")
    _require(paper_boundary["policy"] == PAPER_SYSTEM_MODEL_BOUNDARY_POLICY,
             "paper system/model boundary policy changed")
    for method in PAPER_MECHANISM_ADAPTERS:
        _require(paper_boundary[method] == PAPER_SYSTEM_MODEL_BOUNDARIES[method],
                 f"{method} paper system/model boundary changed")

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
    _require(fair["maximum_complete_configurations_per_primary_method"] == 12,
             "fair primary-method trial cap changed")
    _require(fair["maximum_complete_configurations_per_internal_control"] == 12,
             "fair internal-control trial cap changed")
    _require(fair["confirmation_may_not_select_or_change_any_value"] is True,
             "confirmation selection is forbidden")

    workers = _exact_keys(value["multi_worker_execution"], {
        "policy", "minimum_workers_when_at_least_two_independent_units_exist",
        "worker_count_is_selected_by_capacity_probe", "capacity_inputs",
        "feature_materialization_partition", "deterministic_adapter_grid_partition",
        "learned_ranker_partition", "validation_partition", "gpu_policy",
        "canonical_merge_independent_of_worker_completion_order", "record_required",
    }, "multi_worker_execution")
    _require(workers["minimum_workers_when_at_least_two_independent_units_exist"] == 2,
             "VM-05 requires multiple workers")
    _require(workers["worker_count_is_selected_by_capacity_probe"] is True,
             "worker count needs a capacity probe")
    _require(workers["canonical_merge_independent_of_worker_completion_order"] is True,
             "parallel output requires canonical merging")
    safety = _exact_keys(value["resource_safety"], {
        "wall_clock_timeout_allowed", "RAM_safety_check_required",
        "GPU_VRAM_safety_check_required", "disk_free_space_safety_check_required",
        "OOM_or_disk_full_may_not_be_used_as_a_capacity_probe",
        "scientific_budget_is_frozen_by_samples_configurations_steps_and_stopping_rule_not_elapsed_time",
    }, "resource_safety")
    _require(safety["wall_clock_timeout_allowed"] is False,
             "wall-clock timeout must stay disabled")
    _require(all(safety[name] is True for name in (
        "RAM_safety_check_required",
        "GPU_VRAM_safety_check_required",
        "disk_free_space_safety_check_required",
    )), "RAM, VRAM and disk safety checks are mandatory")
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
