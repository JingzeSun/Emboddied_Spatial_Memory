"""Pure planning and acceptance core for the post-D-183 VM-04 runner.

The functions here do not create a simulator, read private instance IDs, or
write an episode.  They compile the result-blind source pool and validate the
public route/receipt shape that an executable runner must use later.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any, Mapping, Sequence

from cpmt.hashing import canonical_json, clone_json


POOL_SCHEMA = "vsmt-vm04-observation-source-pool-v1"
FORMAL_SCHEMA = "vsmt-vm04-observation-formal-selection-v1"
ROUTE_SCHEMA = "vsmt-vm04-observation-route-plan-v1"
PUBLIC_ROUTE_SCHEMA = "vsmt-vm04-public-observation-route-v1"
RECEIPT_SCHEMA = "vsmt-vm04-observation-route-receipt-v1"
VISIBILITY_BUILDER_RECEIPT_SCHEMA = (
    "vsmt-vm04-public-visibility-builder-receipt-v1"
)
PROGRAMS = (
    "NOOP", "BIND", "BIRTH", "REACTIVATE", "RELINK", "RETRACT", "SPLIT",
    "MERGE", "REPLACE",
)
WORLD_INTERVENTION_PROGRAMS = {
    "BIRTH", "REACTIVATE", "RELINK", "RETRACT", "REPLACE",
}
BRANCH_STATES = {
    "natural_occlusion_then_reobservation": "occluded",
    "out_of_view_then_reobservation": "out_of_view",
}
REGISTERED_CAMERA_ACTIONS = {
    "MoveAhead", "MoveBack", "MoveLeft", "MoveRight",
    "RotateLeft", "RotateRight", "LookUp", "LookDown",
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
REVIEW_ONLY_STATUS = "d183_design_and_numeric_values_approved_schema_review_only"
NUMERIC_FROZEN_STATUS = "d205_numeric_frozen_artifacts_pending"
PLACE_LAYER_STATUS = "d206_place_layer_frozen_artifacts_pending"
EXECUTABLE_STATUS = "d183_frozen_executable"
FROZEN_STATUSES = frozenset({
    NUMERIC_FROZEN_STATUS, PLACE_LAYER_STATUS, EXECUTABLE_STATUS,
})
PILOT_COMPLETION_SCHEMA = "vsmt-vm04-pilot-family-completion-v1"


class ObservationConstructionError(ValueError):
    """Fail-closed construction or contract error."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ObservationConstructionError(message)


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _payload_sha(record: Mapping[str, Any]) -> str:
    payload = clone_json(dict(record))
    for field in (
        "manifest_sha256", "receipt_sha256", "route_plan_sha256",
        "public_route_sha256", "verdict_sha256",
    ):
        payload.pop(field, None)
    return _sha(payload)


def _hex64(value: Any, name: str) -> str:
    _require(type(value) is str and HEX64.fullmatch(value) is not None,
             f"{name} must be a lowercase SHA-256")
    return value


def validate_approved_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the approved D-182/D-183 review contract without opening work."""

    record = clone_json(dict(contract))
    status = record.get("status")
    _require(status in {REVIEW_ONLY_STATUS} | set(FROZEN_STATUSES),
             "observation contract is not a registered D-183 contract")
    authorization = record.get("authorization")
    _require(type(authorization) is dict and authorization,
             "authorization section is missing")
    if status in {REVIEW_ONLY_STATUS, NUMERIC_FROZEN_STATUS, PLACE_LAYER_STATUS}:
        _require(all(value is False for value in authorization.values()),
                 "review contract must keep every execution authorization closed")

    trajectory = record["observation_trajectory"]["frozen_numeric_values"]
    _require(trajectory == {
        "minimum_key_pose_translation_m": 0.5,
        "minimum_reobservation_translation_m": 0.5,
        "minimum_key_pose_yaw_change_degrees": 30.0,
        "minimum_public_observations_per_visibility_state": 2,
        "maximum_route_steps": 24,
        "pose_tolerance_m": 0.02,
        "yaw_tolerance_degrees": 1.0,
    }, "D-182 trajectory values changed")
    window = record["lifecycle_poststate_policy"][
        "multiview_terminal_reobservation_window"]
    _require(type(window) is dict and
             window.get("minimum_registered_public_observations") == 2 and
             window.get("observations_must_be_consecutive") is True,
             "multiview terminal reobservation window is not frozen")

    pilot = record["development_pilot"]
    _require(pilot.get("family_count") == 6, "pilot must contain six families")
    _require(pilot.get("ordered_source_pool_minimum_eligible_houses") == 70,
             "source pool must reserve six pilot plus sixty-four formal houses")
    _require(pilot.get("formal_count_rule") == {
        "pilot_completed_5_or_6": 48,
        "pilot_completed_4": 64,
        "pilot_completed_0_to_3": "stop_and_require_new_contract_version",
    }, "D-183 formal count rule changed")
    _require(
        pilot.get("family_completion_definition") ==
        "all_pre_registered_routes_visibility_states_and_required_SPLIT_MERGE_artifacts_pass_without_replacement" and
        pilot.get("family_completion_source") ==
        "mechanically_derived_from_sealed_route_receipts_and_construction_verdicts" and
        pilot.get("caller_supplied_completion_boolean_allowed") is False and
        pilot.get("mechanical_completion_derivation_status") in {
            "pending_parent_stage_family_receipt_implementation_and_review",
            "implemented_review_pending_parent_stage_family_receipt_v1",
            "implemented_and_reviewed_parent_stage_family_receipt_v1",
        },
        "pilot family completion boundary changed",
    )
    if status == REVIEW_ONLY_STATUS:
        _require(pilot["mechanical_completion_derivation_status"] ==
                 "pending_parent_stage_family_receipt_implementation_and_review",
                 "review-only contract cannot claim pilot derivation is reviewed")
    formal = record["formal_development_sampling"]
    _require(formal.get("source_houses_to_attempt") is None,
             "formal N must remain unset before pilot completion")
    _require(formal.get("minimum_completed_families") == 32,
             "formal completed-family gate changed")

    report = record["l2_identifiability_admission_gate"]["per_program_reporting"]
    _require(report.get("easy_class_CFO_threshold") == 0.6 and
             report.get("easy_class_blocks_whole_dataset") is False and
             report.get("post_result_program_removal_relabeling_or_resampling_allowed")
             is False, "D-183 easy-class rule changed")
    level = record["l2_identifiability_admission_gate"]["evidence_level"]
    _require(set(level) == {
        "target_claim_level", "current_implemented_frontend",
        "current_status", "L1_result_may_admit_L2_main_table",
        "reviewed_L2_frontend_receipt_sha256",
    } and level["target_claim_level"] == "L2_public_proposal_frontend" and
             level["L1_result_may_admit_L2_main_table"] is False,
             "L1/L2 evidence-level boundary changed")
    l2_receipt = level["reviewed_L2_frontend_receipt_sha256"]
    if status in {REVIEW_ONLY_STATUS, NUMERIC_FROZEN_STATUS, PLACE_LAYER_STATUS}:
        _require(
            level["current_implemented_frontend"] ==
            "L1_oracle_entity_masks_plus_public_geometry" and
            level["current_status"] ==
            "blocked_L1_diagnostic_only_until_L2_frontend_is_implemented_and_reviewed" and
            l2_receipt is None,
            "a contract without a real L2 frontend must remain an L1-only diagnostic",
        )
    else:
        _require(
            level["current_implemented_frontend"] ==
            "L2_public_RGBD_proposal_frontend" and
            level["current_status"] ==
            "reviewed_L2_frontend_bound_by_receipt" and
            type(l2_receipt) is str and HEX64.fullmatch(l2_receipt) is not None,
            "executable contract lacks a reviewed L2 frontend receipt",
        )
    probe_fields = {"CFO_and_public_history_probe_architecture",
                    "shared_probe_training_budget"}
    pending = record["l2_identifiability_admission_gate"][
        "pending_model_and_budget_fields"]
    frozen_probe = record["l2_identifiability_admission_gate"].get(
        "frozen_model_and_budget_values") or {}
    _require(set(pending) | set(frozen_probe) == probe_fields and
             not (set(pending) & set(frozen_probe)),
             "identifiability probe fields changed")
    l2_candidate = record["l2_public_proposal_frontend_review_candidate"]
    _require(
        l2_candidate.get("generator_input_fields") == ["current_public_RGB"] and
        l2_candidate.get("prompt_policy") ==
        "fixed_grid_only_no_text_no_private_points_or_boxes" and
        l2_candidate.get("cross_frame_video_memory_enabled") is False and
        l2_candidate.get("overlap_policy") ==
        "preserve_independent_overlapping_proposals" and
        l2_candidate.get("private_crosswalk_emitted") is False,
        "L2 public proposal boundary changed",
    )
    visibility_candidate = record["public_visibility_builder_review_candidate"]
    _require(
        visibility_candidate.get("invalid_or_missing_depth_policy") ==
        "treat_as_unoccluded_so_it_cannot_authorize_hidden_intervention" and
        visibility_candidate.get(
            "terminal_reobservation_requires_current_public_proposal_support"
        ) is True and
        visibility_candidate.get("route_receipt_binding_schema") ==
        VISIBILITY_BUILDER_RECEIPT_SCHEMA and
        visibility_candidate.get(
            "route_and_worker_must_match_subject_config_observation_assessment_and_receipt_digests"
        ) is True,
        "public visibility fail-closed policy changed",
    )
    program_candidate = record["program_construction_review_candidate"]
    _require(
        program_candidate.get(
            "RELINK_requires_open_entity_old_place_and_open_located_at_edge"
        ) is True and
        program_candidate.get(
            "SPLIT_MERGE_artifact_plan_sealed_before_generation"
        ) is True and
        program_candidate.get(
            "SPLIT_MERGE_every_fresh_replay_must_realize_registered_transition"
        ) is True and
        program_candidate.get("private_identity_used_for_program_assignment")
        is False and
        program_candidate.get("matcher_receipt_schema") ==
        "vsmt-vm04-public-program-matcher-receipt-v1" and
        program_candidate.get("episode_construction_receipt_schema") ==
        "vsmt-vm04-episode-construction-receipt-v1" and
        program_candidate.get("online_plan_request_schema") ==
        "vsmt-vm04-online-program-plan-request-v1" and
        program_candidate.get("online_plan_temporal_receipt_schema") ==
        "vsmt-vm04-online-program-plan-temporal-receipt-v2" and
        program_candidate.get("parent_plan_request_spec_schema") ==
        "vsmt-vm04-parent-program-request-spec-v1" and
        program_candidate.get("parent_selector_temporal_receipt_schema") ==
        "vsmt-vm04-parent-selector-temporal-receipt-v1" and
        program_candidate.get(
            "parent_plan_request_provenance_receipt_schema"
        ) == "vsmt-vm04-parent-program-request-provenance-receipt-v2" and
        program_candidate.get("matcher_role") ==
        "public_construction_sufficiency_gate_not_semantic_identity_oracle" and
        program_candidate.get("matcher_prior_boundary") ==
        "causal_memory_immediately_before_registered_terminal_observation" and
        program_candidate.get(
            "episode_receipt_binds_materializer_causal_prior_terminal_packet_plan_config_prior_and_matcher"
        ) is True and
        program_candidate.get(
            "failed_matcher_is_retained_as_construction_failure_without_relabel_or_replacement"
        ) is True and
        program_candidate.get(
            "construction_plan_pre_terminal_temporal_seal_status"
        ) == "online_core_implemented_review_pending_not_consumed_by_episode_receipt" and
        program_candidate.get("online_plan_seal_call_order") ==
        "after_terminal_minus_one_public_memory_update_before_terminal_public_or_private_frame_load" and
        program_candidate.get(
            "online_plan_seal_retained_if_terminal_load_or_materialization_fails"
        ) is True and
        program_candidate.get("online_plan_request_provenance_status") ==
        "parent_selector_and_request_receipts_bound_by_D202_core_review_pending_production_orchestration" and
        program_candidate.get("parent_request_derivation_core_status") ==
        "selector_temporal_receipt_bound_and_consumed_by_D202_core_review_pending" and
        program_candidate.get("parent_request_derivation_scope") ==
        "sealed_public_route_pre_registered_public_selectors_and_terminal_minus_one_causal_memory_only" and
        program_candidate.get(
            "parent_request_caller_supplied_version_ids_allowed"
        ) is False and
        program_candidate.get(
            "parent_request_episode_root_or_raw_path_argument_available"
        ) is False and
        program_candidate.get(
            "parent_selector_spec_temporal_registration_status"
        ) == "receipt_core_seals_spec_before_raw_observation_zero_production_parent_stage_pending" and
        program_candidate.get(
            "parent_request_provenance_receipt_consumed_by_D202"
        ) is True and
        program_candidate.get("online_temporal_receipt_clears_D201_pending") is False and
        program_candidate.get("offline_episode_receipt_consumes_online_temporal_seal") is False and
        program_candidate.get("episode_receipt_parent_family_eligibility") is False and
        program_candidate.get("parent_family_completion_aggregation_status") ==
        "pending_separate_review",
        "program construction boundary changed",
    )
    if status == REVIEW_ONLY_STATUS:
        _require(all(value is None for value in
                     l2_candidate["pending_fields"].values()),
                 "review-only L2 candidate cannot freeze unreviewed values")
        _require(all(value is None for value in
                     visibility_candidate["pending_fields"].values()),
                 "review-only visibility candidate cannot freeze unreviewed values")
        _require(all(value is None for value in
                     program_candidate["pending_matcher_numeric_fields"].values()),
                 "review-only matcher cannot freeze unreviewed values")
    construction = record["deterministic_SPLIT_MERGE_construction"]
    _require(construction.get("posthoc_program_label_from_observed_artifact_allowed")
             is False, "post-hoc SPLIT/MERGE labels must remain forbidden")
    if status in FROZEN_STATUSES:
        _validate_d205_numeric_freeze(record)
    if status in {PLACE_LAYER_STATUS, EXECUTABLE_STATUS}:
        _validate_d206_place_layer(record)
    return record


def _validate_d206_place_layer(record: Mapping[str, Any]) -> None:
    """Require the D-206 pose channel and place-layer freeze to stay honest."""

    pose = record.get("public_pose_channel")
    _require(type(pose) is dict and
             pose.get("world_ground_truth_pose_in_public_packet") is False and
             pose.get("world_ground_truth_pose_channel") ==
             "private_evaluation_only" and
             pose.get("public_pose_definition") ==
             "episode_relative_dead_reckoning_from_registered_actions_with_"
             "declared_noise_origin_at_observation_zero",
             "D-206 public pose channel is missing or leaks world pose")
    noise = pose.get("declared_odometry_noise_model")
    _require(type(noise) is dict and
             noise.get("seeded_and_reproducible") is True and
             noise.get("simulator_executes_the_commanded_action_unchanged")
             is True and
             noise.get("may_be_increased_after_seeing_results") is False,
             "declared odometry noise model is missing or adjustable")
    for name in ("translation_relative_sigma", "translation_absolute_sigma_m",
                 "rotation_relative_sigma", "rotation_absolute_sigma_deg",
                 "lateral_slip_sigma_m"):
        value = noise.get(name)
        _require(type(value) in {int, float} and math.isfinite(float(value)) and
                 float(value) > 0.0,
                 f"odometry noise {name} must be a positive number")

    place = record.get("place_identity_revision")
    _require(type(place) is dict and
             place.get("place_is_learnable") is True and
             place.get("place_scaffold_deterministic_identity_retired") is True
             and place.get("adjacent_to_source") ==
             "evidence_based_not_coordinate_derived" and
             place.get("new_error_category") ==
             "place_misidentification_induced_entity_error",
             "D-206 place identity revision block is missing or weakened")
    z_route = place.get("z_route_family")
    _require(type(z_route) is dict and
             z_route.get("requires_two_registered_turns") is True and
             z_route.get(
                 "corridors_must_be_visually_similar_by_construction") is True
             and z_route.get(
                 "disambiguating_observation_required_after_arrival_at_B"
             ) is not False and
             type(z_route.get("required_later_disambiguation")) is str and
             z_route.get("geometry_may_be_tuned_after_seeing_outcomes") is False,
             "Z-route family must keep its later disambiguation requirement")
    oracle = place.get("place_oracle_diagnostic_arm")
    _require(type(oracle) is dict and
             oracle.get("main_table_arm") == "inferred_place" and
             oracle.get("oracle_arm_may_enter_the_main_table") is False,
             "place oracle arm must stay a diagnostic")

    probe = record["l2_identifiability_admission_gate"]["current_frame_only_probe"]
    forbidden = probe.get("forbidden_inputs")
    _require(type(forbidden) is list and
             {"camera_pose", "past_actions"} <= set(forbidden),
             "a current-frame-only probe must not receive pose or past actions")
    masked = record["l2_identifiability_admission_gate"][
        "frozen_model_and_budget_values"][
            "CFO_and_public_history_probe_architecture"][
                "history_and_prior_inputs_masked_for_CFO"]
    _require({"pose_tokens", "past_action_tokens"} <= set(masked),
             "CFO mask must cover pose and past-action tokens")


def _artifact_digests(section: Mapping[str, Any], legacy_key: str) -> dict[str, Any]:
    """Read the artifact-digest block, tolerating the pre-D-205 layout.

    D-205 split each ``pending_fields`` block into frozen scientific numbers and
    digests that only a real artifact can produce.  Contracts written before the
    split keep every field in one bag, so both shapes stay readable here.
    """

    for key in ("pending_artifact_digests", legacy_key):
        block = section.get(key)
        if block is not None:
            _require(type(block) is dict, f"{key} must be an object")
            return dict(block)
    return {}


def _validate_d205_numeric_freeze(record: Mapping[str, Any]) -> None:
    """Require every scientific value D-205 froze, and no invented digest."""

    scope = record.get("first_paper_scope_boundary")
    _require(type(scope) is dict and
             type(scope.get("claim_level")) is str and
             type(scope.get("learnable_structure_kinds")) is list and
             type(scope.get("deterministic_shared_scaffold")) is list and
             scope.get("first_paper_may_claim") and
             scope.get("first_paper_may_not_claim"),
             "first-paper scope boundary is missing")
    kinds = set(scope["learnable_structure_kinds"])
    scaffold = set(scope["deterministic_shared_scaffold"])
    _require(kinds and kinds <= {"entity", "surface", "fragment", "place"} and
             not (kinds & scaffold),
             "a structure kind cannot be both learnable and a fixed scaffold")
    place_is_scaffolded = any("place" in str(item) for item in scaffold)
    _require(not (place_is_scaffolded and "place" in kinds),
             "place cannot be learnable and a fixed scaffold at the same time")
    if place_is_scaffolded:
        # D-205 narrowing: place is given, so the paper may not claim topology.
        _require({"place_or_room_identity_revision",
                  "spatial_topology_or_connectivity_revision"} <=
                 set(scope["first_paper_may_not_claim"]),
                 "a contract with a deterministic place scaffold may not claim "
                 "place or topology revision")
    else:
        # D-206: place became learnable, so the oracle must be genuinely gone.
        _require("place" in kinds,
                 "retiring the place scaffold requires making place learnable")

    validate_registered_action_request_templates(
        record["observation_trajectory"]["registered_action_request_templates"]
    )

    clock = record["public_packet_materialization"]["decision_time_rule"]
    _require(type(clock) is dict and
             clock.get("observation_zero_s") == 0.0 and
             type(clock.get("seconds_per_registered_camera_action")) in
             {int, float} and
             float(clock["seconds_per_registered_camera_action"]) > 0.0 and
             clock.get("strictly_increasing") is True and
             clock.get("is_wall_clock_or_simulator_physics_time") is False,
             "decision time rule must be a positive nominal registered-action clock")

    encoding = record["public_packet_materialization"]["action_command_encoding"]
    _require(type(encoding) is dict, "action command encoding must be an object")
    order = encoding.get("component_order")
    _require(type(order) is list and len(order) == len(set(order)) and
             encoding.get("vector_length") == len(order) and
             REGISTERED_CAMERA_ACTIONS.issubset(set(order)) and
             encoding.get("private_or_program_fields_encoded") is False,
             "action command encoding must cover eight distinct actions without "
             "private fields")

    l2_frozen = record["l2_public_proposal_frontend_review_candidate"].get(
        "frozen_numeric_values")
    _require(type(l2_frozen) is dict and
             type(l2_frozen.get("minimum_visible_pixels")) is int and
             l2_frozen["minimum_visible_pixels"] > 0 and
             type(l2_frozen.get("maximum_proposals_per_frame")) is int and
             l2_frozen["maximum_proposals_per_frame"] > 0 and
             type(l2_frozen.get("border_truncation_policy")) is str,
             "L2 proposal frontend numeric values are not frozen")
    amg = record["l2_public_proposal_frontend_review_candidate"].get(
        "frozen_automatic_mask_generator_config")
    _require(type(amg) is dict and amg.get("box_nms_thresh") == 1.0 and
             amg.get("crop_nms_thresh") == 1.0,
             "automatic mask generator config must keep suppression disabled so "
             "overlapping proposals survive the sealed overlap policy")

    vis_frozen = record["public_visibility_builder_review_candidate"].get(
        "frozen_numeric_values")
    _require(type(vis_frozen) is dict and
             set(vis_frozen) == {
                 "minimum_depth_m", "maximum_depth_m",
                 "occlusion_depth_tolerance_m", "sampling_stride_pixels",
                 "maximum_subject_samples", "minimum_subject_samples",
             } and
             all(type(value) in {int, float} and math.isfinite(float(value)) and
                 float(value) > 0.0 for value in vis_frozen.values()) and
             float(vis_frozen["minimum_depth_m"]) <
             float(vis_frozen["maximum_depth_m"]) and
             int(vis_frozen["minimum_subject_samples"]) <=
             int(vis_frozen["maximum_subject_samples"]),
             "public visibility numeric values are not frozen or are inconsistent")

    matcher = record["program_construction_review_candidate"].get(
        "frozen_matcher_numeric_values")
    _require(type(matcher) is dict, "matcher numeric values are not frozen")
    rules = matcher.get("association_rules_by_structure_kind")
    _require(type(rules) is dict and
             {"entity", "surface", "fragment"} <= set(rules) <=
             {"entity", "surface", "fragment", "place"},
             "matcher rules must be typed per structure kind (D-139)")
    _require(set(rules) == set(scope["learnable_structure_kinds"]),
             "every learnable structure kind needs its own association rule")
    for kind, rule in rules.items():
        _require(type(rule) is dict and set(rule) == {
            "visual_cosine_minimum", "maximum_centroid_distance_m",
            "geometry_overlap_minimum", "visual_weight", "geometry_weight",
            "combined_score_minimum",
        }, f"{kind} association rule has unexpected fields")
        _require(all(type(value) in {int, float} and
                     math.isfinite(float(value)) and float(value) >= 0.0
                     for value in rule.values()),
                 f"{kind} association rule values must be finite and nonnegative")
        _require(abs(float(rule["visual_weight"]) +
                     float(rule["geometry_weight"]) - 1.0) < 1e-9,
                 f"{kind} association weights must sum to one")
    for name in ("minimum_region_reliability", "minimum_unique_score_margin",
                 "minimum_relation_reliability", "free_space_reliability_threshold",
                 "support_envelope_reliability_threshold",
                 "support_envelope_margin_m",
                 "minimum_free_space_time_separation_s"):
        value = matcher.get(name)
        _require(type(value) in {int, float} and math.isfinite(float(value)) and
                 float(value) > 0.0, f"matcher {name} must be a positive number")
    _require(type(matcher.get("minimum_independent_negative_observations")) is int
             and matcher["minimum_independent_negative_observations"] >= 2,
             "entity RETRACT still needs at least two independent negatives (D-022)")

    gate = record["l2_identifiability_admission_gate"]
    frozen_probe = gate.get("frozen_model_and_budget_values")
    _require(type(frozen_probe) is dict, "shared probe values are not frozen")
    architecture = frozen_probe.get("CFO_and_public_history_probe_architecture")
    budget = frozen_probe.get("shared_probe_training_budget")
    _require(type(architecture) is dict and
             architecture.get("output_classes") == len(PROGRAMS) and
             architecture.get("identical_parameter_count_for_both_probes") is True
             and architecture.get("mask_is_the_only_difference") is True,
             "shared probe architecture must differ only by the registered mask")
    _require(type(budget) is dict and
             type(budget.get("max_updates")) is int and
             budget["max_updates"] > 0 and
             type(budget.get("seeds")) is list and budget["seeds"] and
             budget.get("configuration_selection") ==
             "none_single_registered_configuration",
             "shared probe budget must register exactly one configuration")
    _require(gate["probe_structure_selection"].get("selection_family_split") ==
             "none_single_registered_configuration_requires_no_selection_split",
             "probe selection split must be retired by the single-configuration rule")

    diagnostic = gate.get("pilot_report_only_diagnostic")
    _require(type(diagnostic) is dict and
             diagnostic.get("runs_on") == "six_pilot_families_only" and
             diagnostic.get("may_change_gate_thresholds") is False and
             diagnostic.get("may_change_formal_house_count") is False and
             diagnostic.get("may_change_probe_architecture_or_budget") is False and
             diagnostic.get("may_change_route_geometry_or_program_assignment")
             is False and
             diagnostic.get("pilot_results_excluded_from_all_formal_statistics")
             is True and
             diagnostic.get(
                 "result_is_never_reported_as_the_admission_gate_outcome") is True,
             "pilot report-only diagnostic must not be able to select anything")

    construction = record["deterministic_SPLIT_MERGE_construction"]
    _require(type(construction.get("fresh_replay_repeat_count")) is int and
             construction["fresh_replay_repeat_count"] >= 2,
             "fresh replay repeat count must be at least two")
    _require(type(construction.get("exact_geometry_parameters")) is dict and
             type(construction.get("frozen_frontend_artifact_criteria")) is dict,
             "SPLIT/MERGE geometry and artifact criteria are not frozen")
    criteria = construction["frozen_frontend_artifact_criteria"]
    _require(criteria.get("measured_on") ==
             "frozen_L2_public_proposal_masks_only" and
             criteria.get("all_fresh_replays_must_match") is True and
             criteria.get("private_mask_role") ==
             "post_seal_coverage_measurement_only_never_program_assignment",
             "SPLIT/MERGE artifact criteria must stay public and post-seal graded")
    floor = construction.get("pilot_artifact_yield_floor")
    _require(type(floor) is dict and
             floor.get("measured_on") == "six_pilot_families_only" and
             type(floor.get(
                 "minimum_pilot_families_with_all_SPLIT_fresh_replays_realized"))
             is int and
             type(floor.get(
                 "minimum_pilot_families_with_all_MERGE_fresh_replays_realized"))
             is int and
             floor.get("thresholds_may_change_after_seeing_pilot_results") is False
             and floor.get("below_floor_may_change_geometry_or_criteria") is False,
             "SPLIT/MERGE pilot yield floor is missing or adjustable")

    for section, legacy in (
        (record["l2_public_proposal_frontend_review_candidate"], "pending_fields"),
        (record["public_visibility_builder_review_candidate"], "pending_fields"),
        (record["program_construction_review_candidate"],
         "pending_matcher_numeric_fields"),
    ):
        for name, value in _artifact_digests(section, legacy).items():
            _require(value is None or
                     (type(value) is str and value.strip() != ""),
                     f"artifact digest {name} must be null or a real value")


def validate_registered_action_request_templates(
    templates: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Require an explicit, complete AI2-THOR request for all camera actions."""

    _require(type(templates) is dict and set(templates) == REGISTERED_CAMERA_ACTIONS,
             "registered action request templates must cover exactly eight actions")
    result: dict[str, dict[str, Any]] = {}
    for action in sorted(REGISTERED_CAMERA_ACTIONS):
        raw = templates[action]
        _require(type(raw) is dict, f"{action} request must be an object")
        magnitude_name = (
            "moveMagnitude" if action.startswith("Move") else "degrees"
        )
        _require(set(raw) == {"action", magnitude_name} and
                 raw["action"] == action,
                 f"{action} request has unexpected fields")
        magnitude = raw[magnitude_name]
        _require(type(magnitude) in {int, float} and
                 math.isfinite(float(magnitude)) and float(magnitude) > 0.0,
                 f"{action} magnitude must be finite and positive")
        if action.startswith("Rotate"):
            _require(float(magnitude) <= 180.0,
                     f"{action} degrees exceed 180")
        if action.startswith("Look"):
            _require(float(magnitude) <= 90.0,
                     f"{action} degrees exceed 90")
        result[action] = clone_json(raw)
    return result


def _probe_field(record: Mapping[str, Any], name: str) -> Any:
    """Read a shared-probe field from the frozen block or the legacy block."""

    gate = record["l2_identifiability_admission_gate"]
    frozen = gate.get("frozen_model_and_budget_values") or {}
    if name in frozen:
        return frozen[name]
    return (gate.get("pending_model_and_budget_fields") or {}).get(name)


def assert_numeric_freeze_complete(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Report that every scientific choice is frozen and list what evidence remains.

    This is deliberately weaker than :func:`assert_generation_authorized`.  It
    answers "has the operator finished deciding?", not "may the simulator run?".
    The remaining blockers it returns are digests of artifacts that do not exist
    yet; inventing one would be fabricated evidence, so they stay null until the
    real artifact is produced and reviewed.
    """

    record = validate_approved_contract(contract)
    _require(record["status"] in FROZEN_STATUSES,
             "contract has not reached the D-205 numeric freeze")
    remaining = {
        "materializer_code_sha256": record["crosswalk_provenance"]
        ["expected_materializer_code_sha256"],
        "materializer_config_sha256": record["crosswalk_provenance"]
        ["expected_materializer_config_sha256"],
        "reviewed_L2_frontend_receipt_sha256": record[
            "l2_identifiability_admission_gate"]["evidence_level"]
        ["reviewed_L2_frontend_receipt_sha256"],
    }
    for name, value in _artifact_digests(
        record["l2_public_proposal_frontend_review_candidate"], "pending_fields"
    ).items():
        remaining[f"l2_proposal_{name}"] = value
    return {
        "schema_version": "vsmt-vm04-numeric-freeze-status-v1",
        "contract_version": record.get("version"),
        "status": record["status"],
        "scientific_decisions_frozen": True,
        "pending_artifact_digests": sorted(
            key for key, value in remaining.items() if value is None
        ),
        "pilot_family_completion_reviewed": record["development_pilot"].get(
            "mechanical_completion_derivation_status"
        ) == "implemented_and_reviewed_parent_stage_family_receipt_v1",
        "generation_authorized": record["authorization"].get(
            "generation_authorized") is True,
        "numeric_freeze_does_not_authorize_generation": True,
    }


def assert_generation_authorized(contract: Mapping[str, Any]) -> None:
    """Reject simulator generation until review fields and authorization are open."""

    record = validate_approved_contract(contract)
    blockers = {
        "registered_action_request_templates": record["observation_trajectory"]
        ["registered_action_request_templates"],
        "materializer_code_sha256": record["crosswalk_provenance"]
        ["expected_materializer_code_sha256"],
        "materializer_config_sha256": record["crosswalk_provenance"]
        ["expected_materializer_config_sha256"],
        "public_packet_decision_time_rule": record[
            "public_packet_materialization"]["decision_time_rule"],
        "public_packet_action_command_encoding": record[
            "public_packet_materialization"]["action_command_encoding"],
        "shared_probe_architecture": _probe_field(
            record, "CFO_and_public_history_probe_architecture"),
        "shared_probe_training_budget": _probe_field(
            record, "shared_probe_training_budget"),
        "l2_proposal_frontend_receipt_sha256": record[
            "l2_identifiability_admission_gate"]["evidence_level"]
        ["reviewed_L2_frontend_receipt_sha256"],
        "split_merge_repeat_count": record["deterministic_SPLIT_MERGE_construction"]
        ["fresh_replay_repeat_count"],
        "split_merge_geometry": record["deterministic_SPLIT_MERGE_construction"]
        ["exact_geometry_parameters"],
        "split_merge_frontend_criteria": record[
            "deterministic_SPLIT_MERGE_construction"]
        ["frozen_frontend_artifact_criteria"],
    }
    for name, value in _artifact_digests(
        record["l2_public_proposal_frontend_review_candidate"], "pending_fields"
    ).items():
        blockers[f"l2_proposal_{name}"] = value
    for name, value in _artifact_digests(
        record["public_visibility_builder_review_candidate"], "pending_fields"
    ).items():
        blockers[f"public_visibility_{name}"] = value
    for name, value in _artifact_digests(
        record["program_construction_review_candidate"],
        "pending_matcher_numeric_fields",
    ).items():
        blockers[f"program_matcher_{name}"] = value
    if record["status"] in FROZEN_STATUSES:
        for name, value in (
            ("l2_proposal_frozen_numeric_values",
             record["l2_public_proposal_frontend_review_candidate"].get(
                 "frozen_numeric_values")),
            ("public_visibility_frozen_numeric_values",
             record["public_visibility_builder_review_candidate"].get(
                 "frozen_numeric_values")),
            ("program_matcher_frozen_numeric_values",
             record["program_construction_review_candidate"].get(
                 "frozen_matcher_numeric_values")),
            ("shared_probe_frozen_values",
             record["l2_identifiability_admission_gate"].get(
                 "frozen_model_and_budget_values")),
        ):
            blockers[name] = value
    unresolved = sorted(key for key, value in blockers.items() if value is None)
    _require(not unresolved, "unresolved generation fields: " + ",".join(unresolved))
    validate_registered_action_request_templates(
        blockers["registered_action_request_templates"]
    )
    _require(record["development_pilot"].get(
        "mechanical_completion_derivation_status") ==
        "implemented_and_reviewed_parent_stage_family_receipt_v1",
        "pilot family completion derivation is not implemented and reviewed")
    _require(record["status"] == "d183_frozen_executable",
             "observation contract is not executable")
    _require(record["authorization"].get("trajectory_implementation_authorized")
             is True, "trajectory implementation is not reviewed")
    _require(record["authorization"].get("generation_authorized") is True,
             "generation is not authorized")


def make_source_pool_manifest(
    eligible_house_ids: Sequence[str], *, source_manifest_sha256: str,
    selection_seed: int,
) -> dict[str, Any]:
    """Seal six pilot and sixty-four formal candidates before pilot outcomes."""

    source_digest = _hex64(source_manifest_sha256, "source_manifest_sha256")
    _require(type(selection_seed) is int and selection_seed >= 0,
             "selection_seed must be a nonnegative integer")
    house_ids = list(eligible_house_ids)
    _require(len(house_ids) >= 70, "need at least 70 eligible source houses")
    _require(all(type(item) is str and item for item in house_ids),
             "eligible house IDs must be nonempty strings")
    _require(len(house_ids) == len(set(house_ids)),
             "eligible house IDs must be unique")
    ordered = sorted(house_ids, key=lambda house_id: hashlib.sha256(
        f"{source_digest}|{selection_seed}|{house_id}".encode("utf-8")
    ).hexdigest())[:70]
    rows = []
    for index, source_house_id in enumerate(ordered):
        rows.append({
            "pool_index": index,
            "cohort": "pilot" if index < 6 else "formal_candidate",
            "source_house_id": source_house_id,
            "source_house_commitment": hashlib.sha256(
                f"{source_digest}|{source_house_id}".encode("utf-8")
            ).hexdigest(),
        })
    manifest = {
        "schema_version": POOL_SCHEMA,
        "source_manifest_sha256": source_digest,
        "selection_seed": selection_seed,
        "eligible_house_count": len(house_ids),
        "sealed_pool_count": 70,
        "pilot_count": 6,
        "maximum_formal_candidate_count": 64,
        "houses": rows,
    }
    manifest["manifest_sha256"] = _sha(manifest)
    return validate_source_pool_manifest(manifest)


def validate_source_pool_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    expected = {
        "schema_version", "source_manifest_sha256", "selection_seed",
        "eligible_house_count", "sealed_pool_count", "pilot_count",
        "maximum_formal_candidate_count", "houses", "manifest_sha256",
    }
    _require(set(manifest) == expected, "source pool has unexpected fields")
    _require(manifest["schema_version"] == POOL_SCHEMA, "wrong source pool schema")
    _hex64(manifest["source_manifest_sha256"], "source_manifest_sha256")
    _hex64(manifest["manifest_sha256"], "manifest_sha256")
    _require(manifest["sealed_pool_count"] == 70 and
             manifest["pilot_count"] == 6 and
             manifest["maximum_formal_candidate_count"] == 64,
             "source pool cardinalities changed")
    rows = manifest["houses"]
    _require(type(rows) is list and len(rows) == 70,
             "source pool must contain exactly seventy rows")
    _require([row.get("pool_index") for row in rows] == list(range(70)),
             "source pool indices must be canonical")
    _require(all(row.get("cohort") == ("pilot" if index < 6 else
                                       "formal_candidate")
                 for index, row in enumerate(rows)), "source pool cohort mismatch")
    ids = [row.get("source_house_id") for row in rows]
    _require(all(type(item) is str and item for item in ids) and
             len(ids) == len(set(ids)), "source pool IDs must be unique")
    for row in rows:
        _require(set(row) == {"pool_index", "cohort", "source_house_id",
                              "source_house_commitment"},
                 "source pool row has unexpected fields")
        expected_commitment = hashlib.sha256(
            f"{manifest['source_manifest_sha256']}|{row['source_house_id']}".encode(
                "utf-8")
        ).hexdigest()
        _require(row["source_house_commitment"] == expected_commitment,
                 "source house commitment mismatch")
    _require(manifest["manifest_sha256"] == _payload_sha(manifest),
             "source pool digest mismatch")
    return clone_json(dict(manifest))


def seal_formal_selection(
    source_pool: Mapping[str, Any], *,
    pilot_completion_by_pool_index: Mapping[int, bool],
) -> dict[str, Any]:
    """Apply the approved 6->48/64/stop rule without inspecting model results."""

    pool = validate_source_pool_manifest(source_pool)
    _require(set(pilot_completion_by_pool_index) == set(range(6)),
             "pilot completion must contain exactly pool indices 0..5")
    _require(all(type(value) is bool
                 for value in pilot_completion_by_pool_index.values()),
             "pilot completion values must be booleans")
    completed = sum(pilot_completion_by_pool_index.values())
    formal_count = 48 if completed >= 5 else 64 if completed == 4 else 0
    status = "sealed" if formal_count else "stopped_new_contract_required"
    selected = pool["houses"][6:6 + formal_count]
    record = {
        "schema_version": FORMAL_SCHEMA,
        "source_pool_manifest_sha256": pool["manifest_sha256"],
        "pilot_completed_families": completed,
        "status": status,
        "formal_source_house_count": formal_count,
        "selected_pool_indices": [row["pool_index"] for row in selected],
        "selected_source_house_commitments": [
            row["source_house_commitment"] for row in selected
        ],
        "pilot_inputs_used": "construction_completion_boolean_only",
        "CFO_history_or_oracle_inputs_used": False,
        "formal_failure_replacement_allowed": False,
    }
    record["manifest_sha256"] = _sha(record)
    return record


def _pose(value: Any, name: str) -> dict[str, float]:
    _require(type(value) is dict and set(value) == {"x_m", "y_m", "z_m", "yaw_deg"},
             f"{name} must contain x_m/y_m/z_m/yaw_deg")
    _require(all(type(value[key]) in {int, float} and math.isfinite(value[key])
                 for key in value), f"{name} must be finite")
    return {key: float(value[key]) for key in value}


def _translation(a: Mapping[str, float], b: Mapping[str, float]) -> float:
    return math.sqrt(sum((a[key] - b[key]) ** 2 for key in ("x_m", "y_m", "z_m")))


def _yaw_distance(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def make_public_visibility_assessment(
    *, subject_public_ref: str, subject_reference_sealed_before_frame: bool,
    projected_public_sample_count: int, unoccluded_public_sample_count: int,
    current_public_support_sha256: str | None,
    terminal_reobservation_phase: bool,
) -> dict[str, Any]:
    """Classify visibility from public projection/depth support only.

    A projected locus with public visible-volume support is conservatively
    treated as visible even when the current region matcher finds no subject;
    such a frame cannot authorize a hidden world intervention.
    """

    _require(type(subject_public_ref) is str and subject_public_ref,
             "visibility subject reference must be nonempty")
    _require(type(subject_reference_sealed_before_frame) is bool and
             subject_reference_sealed_before_frame,
             "visibility subject reference must be sealed before the frame")
    _require(type(projected_public_sample_count) is int and
             projected_public_sample_count >= 0,
             "projected sample count must be a nonnegative integer")
    _require(type(unoccluded_public_sample_count) is int and
             0 <= unoccluded_public_sample_count <= projected_public_sample_count,
             "unoccluded sample count must be within projected samples")
    _require(type(terminal_reobservation_phase) is bool,
             "terminal reobservation phase must be boolean")
    if current_public_support_sha256 is not None:
        _hex64(current_public_support_sha256, "current_public_support_sha256")

    if projected_public_sample_count == 0:
        state = "out_of_view"
    elif unoccluded_public_sample_count == 0:
        state = "occluded"
    elif terminal_reobservation_phase and current_public_support_sha256 is not None:
        state = "reobserved"
    else:
        state = "visible"
    record = {
        "schema_version": "vsmt-vm04-public-visibility-assessment-v1",
        "subject_public_ref": subject_public_ref,
        "subject_reference_sealed_before_frame": True,
        "projected_public_sample_count": projected_public_sample_count,
        "unoccluded_public_sample_count": unoccluded_public_sample_count,
        "current_public_support_sha256": current_public_support_sha256,
        "terminal_reobservation_phase": terminal_reobservation_phase,
        "visibility_state": state,
        "private_mask_or_instance_id_used": False,
    }
    record["assessment_sha256"] = _sha(record)
    return record


def validate_public_visibility_assessment(
    assessment: Mapping[str, Any], *, expected_subject_public_ref: str,
) -> dict[str, Any]:
    expected = {
        "schema_version", "subject_public_ref",
        "subject_reference_sealed_before_frame", "projected_public_sample_count",
        "unoccluded_public_sample_count", "current_public_support_sha256",
        "terminal_reobservation_phase", "visibility_state",
        "private_mask_or_instance_id_used", "assessment_sha256",
    }
    _require(set(assessment) == expected,
             "public visibility assessment has unexpected fields")
    _require(assessment["schema_version"] ==
             "vsmt-vm04-public-visibility-assessment-v1",
             "wrong public visibility assessment schema")
    _require(assessment["subject_public_ref"] == expected_subject_public_ref,
             "visibility assessment subject does not match sealed route")
    _require(assessment["private_mask_or_instance_id_used"] is False,
             "public visibility assessment used private identity")
    rebuilt = make_public_visibility_assessment(
        subject_public_ref=assessment["subject_public_ref"],
        subject_reference_sealed_before_frame=
            assessment["subject_reference_sealed_before_frame"],
        projected_public_sample_count=assessment["projected_public_sample_count"],
        unoccluded_public_sample_count=assessment["unoccluded_public_sample_count"],
        current_public_support_sha256=assessment["current_public_support_sha256"],
        terminal_reobservation_phase=assessment["terminal_reobservation_phase"],
    )
    _require(dict(assessment) == rebuilt,
             "public visibility assessment state or digest mismatch")
    return clone_json(dict(assessment))


def validate_visibility_builder_receipt_binding(
    receipt: Mapping[str, Any], *, assessment: Mapping[str, Any],
    observation_index: int, expected_subject_seal_sha256: str,
    expected_config_sha256: str,
    expected_current_public_depth_sha256: str | None = None,
    expected_camera_calibration_and_pose_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate one public geometry receipt without reopening private inputs."""

    expected = {
        "schema_version", "subject_seal_sha256", "current_observation_index",
        "current_public_depth_sha256", "camera_calibration_and_pose_sha256",
        "config_sha256", "assessment_sha256",
        "invalid_or_missing_depth_treated_as_unoccluded", "receipt_sha256",
    }
    _require(type(receipt) is dict and set(receipt) == expected,
             "visibility builder receipt has unexpected fields")
    _require(receipt["schema_version"] == VISIBILITY_BUILDER_RECEIPT_SCHEMA,
             "wrong visibility builder receipt schema")
    _require(receipt["current_observation_index"] == observation_index,
             "visibility builder receipt observation index mismatch")
    _require(receipt["subject_seal_sha256"] == expected_subject_seal_sha256,
             "visibility builder receipt subject seal mismatch")
    _require(receipt["config_sha256"] == expected_config_sha256,
             "visibility builder receipt config mismatch")
    for name in (
        "subject_seal_sha256", "current_public_depth_sha256",
        "camera_calibration_and_pose_sha256", "config_sha256",
        "assessment_sha256", "receipt_sha256",
    ):
        _hex64(receipt[name], name)
    _require(receipt["assessment_sha256"] == assessment["assessment_sha256"],
             "visibility builder receipt assessment mismatch")
    if expected_current_public_depth_sha256 is not None:
        _require(receipt["current_public_depth_sha256"] ==
                 expected_current_public_depth_sha256,
                 "visibility builder receipt depth mismatch")
    if expected_camera_calibration_and_pose_sha256 is not None:
        _require(receipt["camera_calibration_and_pose_sha256"] ==
                 expected_camera_calibration_and_pose_sha256,
                 "visibility builder receipt camera mismatch")
    _require(receipt["invalid_or_missing_depth_treated_as_unoccluded"] is True,
             "visibility builder receipt changed invalid-depth policy")
    _require(receipt["receipt_sha256"] == _payload_sha(receipt),
             "visibility builder receipt digest mismatch")
    return clone_json(dict(receipt))


def validate_route_plan(plan: Mapping[str, Any], *, contract: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the private construction plan that binds a public route."""

    approved = validate_approved_contract(contract)
    expected = {
        "schema_version", "episode_id", "program", "branch_type",
        "visibility_subject_kind", "visibility_subject_public_ref",
        "visibility_subject_seal_sha256", "visibility_builder_config_sha256",
        "initial_pose", "registered_actions", "phase_observation_indices", "planned_poses",
        "intervention_after_observation_index", "terminal_reobservation_indices",
        "split_merge_artifact_plan", "route_plan_sha256",
    }
    _require(set(plan) == expected, "route plan has unexpected fields")
    _require(plan["schema_version"] == ROUTE_SCHEMA, "wrong route plan schema")
    _require(type(plan["episode_id"]) is str and plan["episode_id"],
             "episode_id must be nonempty")
    program = plan["program"]
    _require(program in PROGRAMS, "program is not registered")
    branch = plan["branch_type"]
    _require(branch in BRANCH_STATES, "branch type is not registered")
    expected_subject = "reveal_locus" if program == "BIRTH" else (
        "old_track_and_new_reveal_locus" if program == "REPLACE" else "target_track"
    )
    _require(plan["visibility_subject_kind"] == expected_subject,
             "visibility subject kind does not match program")
    _require(type(plan["visibility_subject_public_ref"]) is str and
             plan["visibility_subject_public_ref"],
             "visibility subject requires an anonymous public reference")
    _hex64(plan["visibility_subject_seal_sha256"],
           "visibility_subject_seal_sha256")
    _hex64(plan["visibility_builder_config_sha256"],
           "visibility_builder_config_sha256")
    _pose(plan["initial_pose"], "initial pose")

    actions = plan["registered_actions"]
    allowed = set(approved["observation_trajectory"]["registered_post_initial_actions"])
    maximum_steps = approved["observation_trajectory"][
        "frozen_numeric_values"]["maximum_route_steps"]
    _require(type(actions) is list and 1 <= len(actions) <= maximum_steps,
             "registered route length is outside the frozen bound")
    _require(all(type(row) is dict and set(row) == {"step_index", "action"}
                 for row in actions), "registered action rows are malformed")
    _require([row["step_index"] for row in actions] == list(range(len(actions))),
             "registered action indices must be canonical")
    _require(all(row["action"] in allowed for row in actions),
             "route contains an unregistered camera action")

    phases = plan["phase_observation_indices"]
    _require(set(phases) == {"precondition_visible", "challenge_hidden", "reobserved"},
             "route phases are incomplete")
    minimum = approved["observation_trajectory"][
        "frozen_numeric_values"]
    for name, indices in phases.items():
        _require(type(indices) is list and len(indices) >=
                 minimum["minimum_public_observations_per_visibility_state"],
                 f"{name} has too few public observations")
        _require(all(type(index) is int and index >= 0 for index in indices) and
                 indices == sorted(set(indices)), f"{name} indices are invalid")
        _require(all(index <= len(actions) for index in indices),
                 f"{name} index is outside the registered action sequence")
    _require(max(phases["precondition_visible"]) < min(phases["challenge_hidden"]) and
             max(phases["challenge_hidden"]) < min(phases["reobserved"]),
             "route phase order is invalid")

    poses = plan["planned_poses"]
    _require(set(poses) == {"precondition", "challenge", "reobservation"},
             "planned pose anchors are incomplete")
    precondition = _pose(poses["precondition"], "precondition pose")
    challenge = _pose(poses["challenge"], "challenge pose")
    reobservation = _pose(poses["reobservation"], "reobservation pose")
    _require(_translation(precondition, challenge) >=
             minimum["minimum_key_pose_translation_m"],
             "planned challenge translation is too small")
    _require(_translation(precondition, reobservation) >=
             minimum["minimum_reobservation_translation_m"],
             "planned reobservation translation is too small")
    _require(max(_yaw_distance(precondition["yaw_deg"], challenge["yaw_deg"]),
                 _yaw_distance(precondition["yaw_deg"], reobservation["yaw_deg"])) >=
             minimum["minimum_key_pose_yaw_change_degrees"],
             "planned key-pose yaw change is too small")

    intervention = plan["intervention_after_observation_index"]
    if program in WORLD_INTERVENTION_PROGRAMS:
        _require(type(intervention) is int and
                 intervention in phases["challenge_hidden"],
                 "world intervention must follow a registered hidden observation")
    else:
        _require(intervention is None,
                 "nonintervention program may not register a world intervention")

    terminal = plan["terminal_reobservation_indices"]
    terminal_minimum = (
        approved["lifecycle_poststate_policy"]
        ["multiview_terminal_reobservation_window"]
        ["minimum_registered_public_observations"]
    )
    _require(type(terminal) is list and len(terminal) >= terminal_minimum,
             "terminal reobservation window is too short")
    _require(terminal == list(range(terminal[0], terminal[0] + len(terminal))),
             "terminal reobservation indices must be consecutive")
    _require(all(index in phases["reobserved"] for index in terminal),
             "terminal window must be inside the reobserved phase")

    artifact = plan["split_merge_artifact_plan"]
    if program in {"SPLIT", "MERGE"}:
        _require(type(artifact) is dict and artifact.get("program") == program and
                 artifact.get("assignment_sealed_before_generation") is True and
                 artifact.get("geometry_parameters_sha256") is not None and
                 artifact.get("frontend_criteria_sha256") is not None,
                 "SPLIT/MERGE requires a pre-registered artifact plan")
        _hex64(artifact["geometry_parameters_sha256"], "geometry_parameters_sha256")
        _hex64(artifact["frontend_criteria_sha256"], "frontend_criteria_sha256")
    else:
        _require(artifact is None,
                 "non-SPLIT/MERGE program may not carry an artifact plan")
    _require(plan["route_plan_sha256"] == _payload_sha(plan),
             "route plan digest mismatch")
    return clone_json(dict(plan))


def public_route_projection(
    plan: Mapping[str, Any], *, contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Remove program and artifact assignments from the observable route file."""

    route = validate_route_plan(plan, contract=contract)
    public = {
        "schema_version": PUBLIC_ROUTE_SCHEMA,
        "consumer_scope": "construction_provenance_only_not_adapter_input",
        "episode_id": route["episode_id"],
        "branch_type": route["branch_type"],
        "visibility_subject_kind": route["visibility_subject_kind"],
        "visibility_subject_public_ref": route["visibility_subject_public_ref"],
        "visibility_subject_seal_sha256":
            route["visibility_subject_seal_sha256"],
        "visibility_builder_config_sha256":
            route["visibility_builder_config_sha256"],
        "initial_pose": route["initial_pose"],
        "registered_actions": route["registered_actions"],
        "phase_observation_indices": route["phase_observation_indices"],
        "planned_poses": route["planned_poses"],
        "intervention_after_observation_index":
            route["intervention_after_observation_index"],
        "terminal_reobservation_indices":
            route["terminal_reobservation_indices"],
        "private_route_plan_sha256": route["route_plan_sha256"],
    }
    public["public_route_sha256"] = _sha(public)
    return public


def assess_route_receipt(
    receipt: Mapping[str, Any], *, plan: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Assess actual public states and poses while retaining every failed route."""

    route = validate_route_plan(plan, contract=contract)
    approved = validate_approved_contract(contract)
    _require(receipt.get("schema_version") == RECEIPT_SCHEMA,
             "wrong route receipt schema")
    _require(receipt.get("route_plan_sha256") == route["route_plan_sha256"],
             "route receipt does not bind the sealed plan")
    observations = receipt.get("observations")
    _require(type(observations) is list and observations,
             "route receipt requires public observations")
    by_index = {}
    for row in observations:
        _require(type(row) is dict and set(row) == {
            "observation_index", "visibility_assessment", "public_evidence_sha256",
            "visibility_builder_receipt", "actual_pose",
            "registered_camera_action_success",
        }, "route observation row is malformed")
        index = row["observation_index"]
        _require(type(index) is int and index >= 0 and index not in by_index,
                 "route observation indices must be unique nonnegative integers")
        _hex64(row["public_evidence_sha256"], "public_evidence_sha256")
        assessment = validate_public_visibility_assessment(
            row["visibility_assessment"],
            expected_subject_public_ref=route["visibility_subject_public_ref"],
        )
        builder_receipt = validate_visibility_builder_receipt_binding(
            row["visibility_builder_receipt"], assessment=assessment,
            observation_index=index,
            expected_subject_seal_sha256=(
                route["visibility_subject_seal_sha256"]
            ),
            expected_config_sha256=route["visibility_builder_config_sha256"],
        )
        _require(row["public_evidence_sha256"] ==
                 builder_receipt["receipt_sha256"],
                 "public evidence digest must bind the visibility builder receipt")
        row = clone_json(row)
        row["visibility_state"] = assessment["visibility_state"]
        _pose(row["actual_pose"], "actual pose")
        _require(type(row["registered_camera_action_success"]) is bool,
                 "camera action success must be boolean")
        by_index[index] = row
    _require(set(by_index) == set(range(len(route["registered_actions"]) + 1)),
             "route receipt must contain observation zero plus one observation per registered action")

    failures = []
    for name, indices in route["phase_observation_indices"].items():
        expected_state = ({
            "precondition_visible": "visible",
            "challenge_hidden": BRANCH_STATES[route["branch_type"]],
            "reobserved": "reobserved",
        })[name]
        for index in indices:
            row = by_index.get(index)
            if row is None:
                failures.append("missing_registered_observation")
            elif not row["registered_camera_action_success"]:
                failures.append("registered_camera_action_failed")
            elif row["visibility_state"] != expected_state:
                failures.append("registered_visibility_state_mismatch")

    if route["intervention_after_observation_index"] is not None:
        row = by_index.get(route["intervention_after_observation_index"])
        if row is None or row["visibility_state"] not in {"occluded", "out_of_view"}:
            failures.append("intervention_visible_to_camera")

    tolerance = approved["observation_trajectory"][
        "frozen_numeric_values"]
    anchors = {
        "precondition": route["phase_observation_indices"]["precondition_visible"][-1],
        "challenge": route["phase_observation_indices"]["challenge_hidden"][-1],
        "reobservation": route["phase_observation_indices"]["reobserved"][-1],
    }
    actual_poses = {}
    for name, index in anchors.items():
        if index not in by_index:
            continue
        actual = _pose(by_index[index]["actual_pose"], "actual pose")
        planned = _pose(route["planned_poses"][name], "planned pose")
        if (_translation(actual, planned) > tolerance["pose_tolerance_m"] or
                _yaw_distance(actual["yaw_deg"], planned["yaw_deg"]) >
                tolerance["yaw_tolerance_degrees"]):
            failures.append("actual_pose_outside_tolerance")
        actual_poses[name] = actual
    if len(actual_poses) == 3:
        if _translation(actual_poses["precondition"], actual_poses["challenge"]) < 0.5:
            failures.append("actual_key_pose_translation_too_small")
        if _translation(actual_poses["precondition"], actual_poses["reobservation"]) < 0.5:
            failures.append("actual_reobservation_translation_too_small")

    terminal_ok = all(
        index in by_index and by_index[index]["visibility_state"] == "reobserved"
        for index in route["terminal_reobservation_indices"]
    )
    if not terminal_ok:
        failures.append("terminal_reobservation_window_failed")
    unique_failures = sorted(set(failures))
    verdict = {
        "schema_version": "vsmt-vm04-observation-construction-verdict-v1",
        "route_plan_sha256": route["route_plan_sha256"],
        "constructed": not unique_failures,
        "failure_reasons": unique_failures,
        "failed_route_replacement_allowed": False,
        "actual_observation_count": len(observations),
        "terminal_reobservation_satisfied": terminal_ok,
    }
    verdict["verdict_sha256"] = _sha(verdict)
    return verdict
