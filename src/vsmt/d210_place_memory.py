"""D-210 dual-layer place memory, twelve-slot P0, adapter, and metrics.

The exact low-level action stream remains in raw/provenance.  Deployable
methods receive keyframes, a causal continuous pose belief, and a compact
transition summary.  A metric grid may retrieve candidates but never defines
place identity.  Private place regions and loop labels are accepted only by
the evaluator after predictions have been sealed.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any, Mapping, Sequence

from cpmt.hashing import canonical_json, clone_json


CONTRACT_SCHEMA = "vsmt-vm04-d210-dual-layer-p0-contract-v1"
ROUTE_SCHEMA = "vsmt-vm04-d210-p0-route-plan-v1"
PUBLIC_MANIFEST_SCHEMA = "vsmt-vm04-d210-p0-public-manifest-v1"
PRIVATE_MANIFEST_SCHEMA = "vsmt-vm04-d210-p0-private-manifest-v1"
KEYFRAME_SCHEMA = "vsmt-d210-public-keyframe-v1"
POSE_BELIEF_SCHEMA = "vsmt-d210-continuous-pose-belief-v1"
ADAPTER_PACKET_SCHEMA = "vsmt-d210-place-adapter-packet-v1"
ACTION_SUMMARY_SCHEMA = "vsmt-d210-transition-action-summary-v1"
METRIC_SCHEMA = "vsmt-d210-place-episode-metrics-v1"

REGISTERED_ACTIONS = (
    "MoveAhead", "MoveBack", "MoveLeft", "MoveRight",
    "RotateLeft", "RotateRight", "LookUp", "LookDown",
)
MOVE_ACTIONS = frozenset(REGISTERED_ACTIONS[:4])
ROTATE_ACTIONS = frozenset(REGISTERED_ACTIONS[4:6])
LOOK_ACTIONS = frozenset(REGISTERED_ACTIONS[6:])
P0_SCENARIOS = frozenset(f"P{index:02d}" for index in range(1, 9))
HEADLINE_SCENARIOS = frozenset({"P03", "P04", "P06", "P07", "P08"})
HEX64 = re.compile(r"^[0-9a-f]{64}$")
EPISODE_ID = re.compile(r"^d210:p0:[0-9a-f]{24}$")
FORBIDDEN_ADAPTER_TOKENS = (
    "raw_action_sequence", "past_action", "world_pose", "simulator_pose",
    "grid_place", "private", "reference_place", "future", "teacher",
    "route_phase", "instance_id", "object_id",
)


class D210Error(ValueError):
    """A D-210 record changed the approved scientific or data boundary."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise D210Error(message)


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _payload_sha(record: Mapping[str, Any], field: str) -> str:
    value = clone_json(dict(record))
    value.pop(field, None)
    return _sha(value)


def _exact_keys(value: Any, keys: set[str], name: str) -> None:
    _require(type(value) is dict and set(value) == keys,
             f"{name} has unexpected fields")


def _hex64(value: Any, name: str) -> str:
    _require(type(value) is str and HEX64.fullmatch(value) is not None,
             f"{name} must be a lowercase SHA-256")
    return value


def _finite(value: Any, name: str) -> float:
    _require(type(value) in {int, float} and math.isfinite(float(value)),
             f"{name} must be finite")
    return float(value)


def validate_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the user-approved D-210 values without opening a run gate."""

    record = clone_json(dict(contract))
    _exact_keys(record, {
        "schema_version", "decision_id", "status", "authorization", "scope",
        "movement", "memory_layers", "information_channels", "action_summary",
        "reference_policy", "batch", "scenarios", "slot_plan", "metrics",
        "diagnostic_oracles",
    }, "D-210 contract")
    _require(record["schema_version"] == CONTRACT_SCHEMA and
             record["decision_id"] == "D-210",
             "D-210 contract identity changed")
    _require(record["status"] in {
        "approved_implementation_not_generation_authorized",
        "frozen_executable",
    }, "D-210 contract status is invalid")
    authorization = record["authorization"]
    _exact_keys(authorization, {
        "source_house_binding_authorized", "route_plan_sealing_authorized",
        "raw_generation_authorized", "adapter_materialization_authorized",
        "private_evaluation_authorized",
    }, "D-210 authorization")
    _require(all(type(value) is bool for value in authorization.values()),
             "D-210 authorization values must be booleans")
    if record["status"] != "frozen_executable":
        _require(not any(authorization.values()),
                 "the implementation-review contract cannot authorize work")

    scope = record["scope"]
    _require(scope == {
        "purpose": "two_house_twelve_episode_raw_engineering_pilot",
        "training_allowed": False,
        "validation_allowed": False,
        "confirmation_allowed": False,
        "paper_effect_table_allowed": False,
        "place_identity_is_a_metric_grid_cell": False,
        "claims_metric_slam_or_pose_estimation": False,
    }, "D-210 scope changed")

    movement = record["movement"]
    _exact_keys(movement, {
        "move_magnitude_m", "body_rotation_degrees", "camera_pitch_degrees",
        "snap_to_grid", "force_action", "scientific_maximum_route_actions",
        "mechanical_route_action_guard", "guard_checked_before_route_seal",
        "runtime_truncation_allowed", "observation_zero_before_actions",
        "raw_observation_after_every_completed_action",
        "failed_action_retained_with_terminal_failure",
        "registered_action_requests",
    }, "D-210 movement")
    _require(movement["move_magnitude_m"] == 0.25 and
             movement["body_rotation_degrees"] == 90.0 and
             movement["camera_pitch_degrees"] == 30.0 and
             movement["snap_to_grid"] is True and
             movement["force_action"] is False and
             movement["scientific_maximum_route_actions"] is None and
             movement["mechanical_route_action_guard"] == 128 and
             movement["guard_checked_before_route_seal"] is True and
             movement["runtime_truncation_allowed"] is False and
             movement["observation_zero_before_actions"] is True and
             movement["raw_observation_after_every_completed_action"] is True and
             movement["failed_action_retained_with_terminal_failure"] is True,
             "D-210 movement values changed")
    requests = movement["registered_action_requests"]
    _require(type(requests) is dict and set(requests) == set(REGISTERED_ACTIONS),
             "D-210 must register exactly eight action requests")
    for name in REGISTERED_ACTIONS:
        expected = {"action": name}
        if name in MOVE_ACTIONS:
            expected["moveMagnitude"] = 0.25
        elif name in ROTATE_ACTIONS:
            expected["degrees"] = 90.0
        else:
            expected["degrees"] = 30.0
        _require(requests[name] == expected,
                 f"D-210 request for {name} changed")

    layers = record["memory_layers"]
    _exact_keys(layers, {"continuous_pose_belief",
                         "versioned_topological_place_graph"},
                "D-210 memory layers")
    pose_layer = layers["continuous_pose_belief"]
    _require(pose_layer == {
        "role": "causal_metric_prior_for_retrieval_not_place_identity_truth",
        "frame": "episode_relative_observation_zero_origin",
        "required_fields": [
            "observation_index", "mean_x_y_z_yaw", "covariance_diagonal",
            "source_id", "belief_sha256",
        ],
        "world_pose_allowed": False,
        "fixed_grid_quantization_may_define_place_identity": False,
    }, "D-210 continuous pose-belief layer changed")
    topology = layers["versioned_topological_place_graph"]
    _require(topology == {
        "role": "learned_and_revisable_place_relation_entity_memory",
        "place_node_fields": [
            "place_id", "lifecycle", "visual_geometry_summary",
            "pose_belief_envelope", "contained_entity_refs", "evidence_refs",
            "version",
        ],
        "transition_edge_fields": [
            "edge_id", "from_place_id", "to_place_id", "action_summary",
            "estimated_delta_distribution", "evidence_refs", "confidence",
            "version",
        ],
        "place_operations": ["NOOP", "BIND", "BIRTH", "MERGE"],
        "relation_operations": ["CREATE", "RELINK"],
        "place_split_in_p0": False,
        "new_relation_is_relink": False,
    }, "D-210 P0 topological layer changed")

    channels = record["information_channels"]
    _require(channels == {
        "raw_and_provenance": {
            "stores_complete_per_action_sequence": True,
            "stores_every_raw_observation": True,
            "deployable_adapter_may_read_complete_per_action_sequence": False,
            "purpose": "reproduction_audit_and_exact_action_oracle_only",
        },
        "deployable_adapter": {
            "reads": [
                "current_keyframe", "continuous_pose_belief",
                "incoming_transition_action_summary",
                "public_region_and_relation_observations",
                "prior_predicted_memory", "public_constants",
            ],
            "forbidden": [
                "raw_action_sequence", "past_actions", "world_pose",
                "simulator_pose", "fixed_grid_place_identity",
                "private_reference_place", "future_observation",
                "teacher_target", "route_phase_label",
            ],
        },
        "private_evaluation": {
            "opened_after_candidate_seal": True,
            "stores": [
                "simulator_pose", "reference_place_region",
                "reference_reachable_component", "loop_pair_label",
                "reference_relation_endpoint",
                "reference_entity_place_attachment",
            ],
        },
    }, "D-210 information-channel boundary changed")

    summary = record["action_summary"]
    _require(summary == {
        "schema_version": ACTION_SUMMARY_SCHEMA,
        "required_fields": [
            "start_observation_index", "end_observation_index", "step_count",
            "action_histogram", "ordered_quarter_turns",
            "nominal_translation_m_total", "estimated_delta_mean_x_z_yaw",
            "estimated_delta_covariance_diagonal", "confidence",
            "raw_action_span_sha256", "summary_sha256",
        ],
        "contains_per_step_action_sequence": False,
        "may_directly_assign_place_identity": False,
    }, "D-210 action summary boundary changed")
    reference = record["reference_policy"]
    _require(reference == {
        "planner_grid_size_m": 0.5,
        "planner_grid_role": "route_planning_and_candidate_retrieval_only",
        "loop_positive_max_position_error_m": 0.35,
        "loop_positive_requires_same_reachable_component": True,
        "loop_positive_requires_same_yaw": False,
        "negative_minimum_position_separation_m": 1.5,
        "negative_alternative": "pre_registered_distinct_branch_or_room",
        "unlabelled_distance_gap_m": [0.35, 1.5],
        "reference_regions_private_only": True,
        "reference_regions_may_generate_candidates": False,
    }, "D-210 reference policy changed")

    batch = record["batch"]
    _require(batch == {
        "house_count": 2, "episode_count": 12,
        "failed_episode_replacement_allowed": False,
        "failed_route_role_change_allowed": False,
        "p01_to_p04_each_run_in_both_houses": True,
        "p05_to_p08_each_run_once": True,
        "p09_p10_deferred_to_p1": True,
    }, "D-210 P0 batch changed")
    _validate_scenarios_and_slots(record)
    _require(record["metrics"] == {
        "primary": [
            "place_pairwise_precision", "place_pairwise_recall",
            "place_pairwise_f1", "duplicate_place_rate", "false_merge_rate",
            "loop_closure_precision", "loop_closure_recall",
            "topology_edge_endpoint_f1",
            "entity_place_attachment_accuracy", "contamination_auc",
        ],
        "error_decomposition": [
            "candidate_miss", "teacher_error", "amortization_error",
            "illegal_transaction", "collateral_change",
        ],
        "headline_scenarios": ["P03", "P04", "P06", "P07", "P08"],
        "control_scenarios": ["P01", "P02"],
        "supporting_scenarios": ["P05"],
        "p09_p10_excluded_from_p0": True,
    }, "D-210 metric or scenario evidence roles changed")
    oracles = record["diagnostic_oracles"]
    _require(oracles == {
        "exact_action_integration": {
            "input_advantage": "complete_per_step_action_sequence",
            "main_table": False,
            "role": "show_which_inverse_or_nominal_routes_collapse_under_exact_command_integration",
        },
        "true_pose": {
            "input_advantage": "private_simulator_world_pose",
            "main_table": False,
            "role": "separate_place_reasoning_error_from_localization_upper_bound",
        },
        "d206_noisy_grid_duplicate_rate": {
            "registered_observation": 0.855,
            "unit": "episode_fraction_with_at_least_one_duplicate_place_in_3000_diagnostic_round_trips",
            "main_metric": False,
            "role": "historical_diagnostic_not_model_accuracy_or_coverage",
        },
    }, "D-210 diagnostic oracle boundary changed")
    return record


def _validate_scenarios_and_slots(contract: Mapping[str, Any]) -> None:
    scenarios = contract["scenarios"]
    _require(set(scenarios) == {f"P{index:02d}" for index in range(1, 11)},
             "D-210 scenario set changed")
    for scenario_id, row in scenarios.items():
        _exact_keys(row, {"name", "phase", "planning_action_count_hint",
                          "evidence_role", "claim"}, scenario_id)
        hint = row["planning_action_count_hint"]
        _require(type(hint) is list and len(hint) == 2 and
                 all(type(value) is int and 0 < value <= 128 for value in hint) and
                 hint[0] <= hint[1],
                 f"{scenario_id} planning hint is invalid")
        _require(row["phase"] == ("P0" if scenario_id in P0_SCENARIOS else "P1"),
                 f"{scenario_id} phase changed")
    expected = [
        (0, 0, "P01", 26091800), (1, 0, "P02", 26091801),
        (2, 0, "P03", 26091802), (3, 0, "P04", 26091803),
        (4, 1, "P01", 26091804), (5, 1, "P02", 26091805),
        (6, 1, "P03", 26091806), (7, 1, "P04", 26091807),
        (8, 0, "P05", 26091808), (9, 0, "P07", 26091809),
        (10, 1, "P06", 26091810), (11, 1, "P08", 26091811),
    ]
    slots = contract["slot_plan"]
    _require(type(slots) is list and len(slots) == 12,
             "D-210 requires twelve fixed slots")
    for row, values in zip(slots, expected, strict=True):
        slot, house_slot, scenario_id, seed = values
        _require(row == {"slot": slot, "house_slot": house_slot,
                         "scenario_id": scenario_id, "seed": seed},
                 f"D-210 slot {slot} changed")


def build_route_plan(
    *, slot: int, action_names: Sequence[str],
    keyframe_observation_indices: Sequence[int],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Seal one complete action route; planning hints never reject a route."""

    approved = validate_contract(contract)
    _require(type(slot) is int and 0 <= slot < 12, "route slot is invalid")
    _require(type(action_names) in {list, tuple} and action_names,
             "route action list must be complete and nonempty")
    count = len(action_names)
    _require(count <= approved["movement"]["mechanical_route_action_guard"],
             "route exceeds the 128-action mechanical guard")
    requests = approved["movement"]["registered_action_requests"]
    actions = []
    for index, name in enumerate(action_names):
        _require(type(name) is str and name in requests,
                 f"route action {index} is not registered")
        actions.append({"step_index": index, "action": name,
                        "request": clone_json(requests[name])})
    keyframes = list(keyframe_observation_indices)
    _require(keyframes == sorted(set(keyframes)) and keyframes[0] == 0 and
             keyframes[-1] == count and
             all(type(value) is int and 0 <= value <= count for value in keyframes),
             "keyframes must be sorted unique and include observations 0 and N")
    slot_spec = approved["slot_plan"][slot]
    plan = {
        "schema_version": ROUTE_SCHEMA,
        "slot": slot,
        "house_slot": slot_spec["house_slot"],
        "scenario_id": slot_spec["scenario_id"],
        "seed": slot_spec["seed"],
        "route_source": "pre_intervention_public_reachable_scan_and_rgbd_only",
        "complete_action_sequence_sealed_before_execution": True,
        "future_or_action_outcome_used": False,
        "private_reference_used": False,
        "runtime_truncation_allowed": False,
        "actions": actions,
        "planned_action_count": count,
        "observation_count": count + 1,
        "keyframe_observation_indices": keyframes,
    }
    plan["route_plan_sha256"] = _payload_sha(plan, "route_plan_sha256")
    return validate_route_plan(plan, approved)


def validate_route_plan(
    plan: Mapping[str, Any], contract: Mapping[str, Any],
) -> dict[str, Any]:
    approved = validate_contract(contract)
    record = clone_json(dict(plan))
    _exact_keys(record, {
        "schema_version", "slot", "house_slot", "scenario_id", "seed",
        "route_source", "complete_action_sequence_sealed_before_execution",
        "future_or_action_outcome_used", "private_reference_used",
        "runtime_truncation_allowed", "actions", "planned_action_count",
        "observation_count", "keyframe_observation_indices",
        "route_plan_sha256",
    }, "D-210 route plan")
    _require(record["schema_version"] == ROUTE_SCHEMA,
             "D-210 route schema changed")
    slot = record["slot"]
    _require(type(slot) is int and 0 <= slot < 12, "route slot is invalid")
    spec = approved["slot_plan"][slot]
    _require((record["house_slot"], record["scenario_id"], record["seed"]) ==
             (spec["house_slot"], spec["scenario_id"], spec["seed"]),
             "route disagrees with its fixed slot")
    _require(record["route_source"] ==
             "pre_intervention_public_reachable_scan_and_rgbd_only" and
             record["complete_action_sequence_sealed_before_execution"] is True and
             record["future_or_action_outcome_used"] is False and
             record["private_reference_used"] is False and
             record["runtime_truncation_allowed"] is False,
             "route source or execution boundary changed")
    actions = record["actions"]
    _require(type(actions) is list and actions, "route has no actions")
    count = len(actions)
    _require(count <= 128, "route exceeds the 128-action mechanical guard")
    _require(record["planned_action_count"] == count and
             record["observation_count"] == count + 1,
             "route action and observation counts disagree")
    requests = approved["movement"]["registered_action_requests"]
    for index, action in enumerate(actions):
        _require(type(action) is dict and set(action) == {
            "step_index", "action", "request",
        }, f"route action {index} fields changed")
        name = action["action"]
        _require(type(name) is str and name in requests,
                 f"route action {index} is not registered")
        _require(action == {"step_index": index, "action": name,
                            "request": requests[name]},
                 f"route action {index} changed its explicit request")
    keyframes = record["keyframe_observation_indices"]
    _require(type(keyframes) is list and keyframes == sorted(set(keyframes)) and
             keyframes[0] == 0 and keyframes[-1] == count and
             all(type(value) is int and 0 <= value <= count for value in keyframes),
             "route keyframes are invalid")
    _require(record["route_plan_sha256"] ==
             _payload_sha(record, "route_plan_sha256"),
             "route plan digest mismatch")
    return record


def build_p0_manifests(
    *, source_houses: Sequence[Mapping[str, Any]],
    route_plans: Sequence[Mapping[str, Any]], contract: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Bind two private source houses to twelve opaque public episodes."""

    approved = validate_contract(contract)
    _require(type(source_houses) in {list, tuple} and len(source_houses) == 2,
             "D-210 P0 requires two source houses")
    houses = []
    for index, house in enumerate(source_houses):
        _exact_keys(house, {"house_slot", "source_house_id",
                            "source_record_sha256"}, f"source house {index}")
        _require(house["house_slot"] == index and
                 type(house["source_house_id"]) is str and
                 house["source_house_id"], "source house identity is invalid")
        _hex64(house["source_record_sha256"], "source record digest")
        houses.append(clone_json(dict(house)))
    _require(houses[0]["source_house_id"] != houses[1]["source_house_id"],
             "the two source houses must be distinct")
    _require(type(route_plans) in {list, tuple} and len(route_plans) == 12,
             "D-210 P0 requires twelve route plans")
    checked = {plan["slot"]: validate_route_plan(plan, approved)
               for plan in route_plans}
    _require(set(checked) == set(range(12)) and len(checked) == 12,
             "route plans must cover twelve unique slots")
    contract_sha = _sha(approved)
    public_rows, private_rows = [], []
    for slot in range(12):
        plan = checked[slot]
        episode_id = "d210:p0:" + _sha({
            "contract_sha256": contract_sha, "slot": slot,
            "route_plan_sha256": plan["route_plan_sha256"],
        })[:24]
        public_rows.append({
            "episode_id": episode_id, "slot": slot,
            "scenario_id": plan["scenario_id"],
            "route_plan_sha256": plan["route_plan_sha256"],
            "planned_action_count": plan["planned_action_count"],
            "observation_count": plan["observation_count"],
            "keyframe_count": len(plan["keyframe_observation_indices"]),
        })
        private_rows.append({
            "episode_id": episode_id, "slot": slot,
            "house_slot": plan["house_slot"],
            "source_house_id": houses[plan["house_slot"]]["source_house_id"],
            "scenario_id": plan["scenario_id"],
            "route_plan_sha256": plan["route_plan_sha256"],
        })
    public = {
        "schema_version": PUBLIC_MANIFEST_SCHEMA,
        "contract_sha256": contract_sha, "episode_count": 12,
        "episodes": public_rows, "source_house_ids_exported": False,
        "private_reference_regions_exported": False,
    }
    public["manifest_sha256"] = _payload_sha(public, "manifest_sha256")
    private = {
        "schema_version": PRIVATE_MANIFEST_SCHEMA,
        "public_manifest_sha256": public["manifest_sha256"],
        "houses": houses, "episode_count": 12, "episodes": private_rows,
    }
    private["manifest_sha256"] = _payload_sha(private, "manifest_sha256")
    return public, private


def build_transition_action_summary(
    *, actions: Sequence[Mapping[str, Any]], start_observation_index: int,
    end_observation_index: int, estimated_delta_mean_x_z_yaw: Sequence[float],
    estimated_delta_covariance_diagonal: Sequence[float], confidence: float,
    raw_action_span_sha256: str, contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Compress an exact raw span into the action-labelled graph-edge input."""

    approved = validate_contract(contract)
    _require(type(start_observation_index) is int and
             type(end_observation_index) is int and
             0 <= start_observation_index < end_observation_index,
             "transition observation interval is invalid")
    _require(len(actions) == end_observation_index - start_observation_index,
             "transition span length disagrees with its observation interval")
    histogram = {name: 0 for name in REGISTERED_ACTIONS}
    rotations = []
    for row in actions:
        _require(type(row) is dict and row.get("action") in histogram,
                 "transition contains an unregistered action")
        name = row["action"]
        histogram[name] += 1
        if name in ROTATE_ACTIONS:
            direction = "left" if name == "RotateLeft" else "right"
            if rotations and rotations[-1]["direction"] == direction:
                rotations[-1]["quarter_turns"] += 1
            else:
                rotations.append({"direction": direction, "quarter_turns": 1})
    mean = [_finite(value, "estimated delta mean")
            for value in estimated_delta_mean_x_z_yaw]
    covariance = [_finite(value, "estimated delta covariance")
                  for value in estimated_delta_covariance_diagonal]
    _require(len(mean) == 3 and len(covariance) == 3 and
             all(value >= 0.0 for value in covariance),
             "transition delta must have three means and nonnegative variances")
    conf = _finite(confidence, "transition confidence")
    _require(0.0 <= conf <= 1.0, "transition confidence must be in [0,1]")
    summary = {
        "schema_version": ACTION_SUMMARY_SCHEMA,
        "start_observation_index": start_observation_index,
        "end_observation_index": end_observation_index,
        "step_count": len(actions),
        "action_histogram": histogram,
        "ordered_quarter_turns": rotations,
        "nominal_translation_m_total": sum(
            histogram[name] for name in MOVE_ACTIONS
        ) * approved["movement"]["move_magnitude_m"],
        "estimated_delta_mean_x_z_yaw": mean,
        "estimated_delta_covariance_diagonal": covariance,
        "confidence": conf,
        "raw_action_span_sha256": _hex64(
            raw_action_span_sha256, "raw action span digest"),
        "contains_per_step_action_sequence": False,
        "may_directly_assign_place_identity": False,
    }
    summary["summary_sha256"] = _payload_sha(summary, "summary_sha256")
    return validate_transition_action_summary(summary, approved)


def validate_transition_action_summary(
    summary: Mapping[str, Any], contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate a compact edge label without accepting a hidden action list."""

    approved = validate_contract(contract)
    value = clone_json(dict(summary))
    _exact_keys(value, {
        "schema_version", "start_observation_index", "end_observation_index",
        "step_count", "action_histogram", "ordered_quarter_turns",
        "nominal_translation_m_total", "estimated_delta_mean_x_z_yaw",
        "estimated_delta_covariance_diagonal", "confidence",
        "raw_action_span_sha256", "contains_per_step_action_sequence",
        "may_directly_assign_place_identity", "summary_sha256",
    }, "D-210 transition action summary")
    _require(value["schema_version"] == ACTION_SUMMARY_SCHEMA and
             type(value["start_observation_index"]) is int and
             type(value["end_observation_index"]) is int and
             0 <= value["start_observation_index"] <
             value["end_observation_index"] and
             type(value["step_count"]) is int and value["step_count"] > 0 and
             value["step_count"] == value["end_observation_index"] -
             value["start_observation_index"] and
             value["contains_per_step_action_sequence"] is False and
             value["may_directly_assign_place_identity"] is False,
             "D-210 transition summary boundary changed")
    histogram = value["action_histogram"]
    _require(type(histogram) is dict and set(histogram) == set(REGISTERED_ACTIONS)
             and all(type(count) is int and count >= 0
                     for count in histogram.values())
             and sum(histogram.values()) == value["step_count"],
             "transition action histogram is invalid")
    rotations = value["ordered_quarter_turns"]
    _require(type(rotations) is list and all(
        type(row) is dict and set(row) == {"direction", "quarter_turns"} and
        row["direction"] in {"left", "right"} and
        type(row["quarter_turns"]) is int and row["quarter_turns"] > 0
        for row in rotations
    ) and all(left["direction"] != right["direction"]
              for left, right in zip(rotations, rotations[1:])),
             "ordered quarter turns are invalid")
    _require(sum(row["quarter_turns"] for row in rotations) ==
             histogram["RotateLeft"] + histogram["RotateRight"],
             "ordered quarter turns disagree with the histogram")
    nominal = _finite(value["nominal_translation_m_total"],
                      "nominal translation")
    expected_nominal = sum(histogram[name] for name in MOVE_ACTIONS) * (
        approved["movement"]["move_magnitude_m"])
    _require(math.isclose(nominal, expected_nominal, abs_tol=1e-12),
             "nominal translation disagrees with the action histogram")
    mean = [_finite(item, "estimated delta mean")
            for item in value["estimated_delta_mean_x_z_yaw"]]
    covariance = [_finite(item, "estimated delta covariance")
                  for item in value["estimated_delta_covariance_diagonal"]]
    confidence = _finite(value["confidence"], "transition confidence")
    _require(len(mean) == 3 and len(covariance) == 3 and
             all(item >= 0.0 for item in covariance) and
             0.0 <= confidence <= 1.0,
             "transition estimate or confidence is invalid")
    _hex64(value["raw_action_span_sha256"], "raw action span digest")
    _require(value["summary_sha256"] ==
             _payload_sha(value, "summary_sha256"),
             "transition summary digest mismatch")
    return value


def _reject_forbidden_adapter_keys(value: Any, path: str = "") -> None:
    if type(value) is dict:
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered == "is_world_pose" and child is False:
                continue
            _require(not any(token in lowered for token in FORBIDDEN_ADAPTER_TOKENS),
                     f"D-210 adapter input contains forbidden field {path}/{key}")
            _reject_forbidden_adapter_keys(child, f"{path}/{key}")
    elif type(value) is list:
        for index, child in enumerate(value):
            _reject_forbidden_adapter_keys(child, f"{path}/{index}")


def build_public_keyframe(
    *, observation_index: int, rgb_sha256: str, depth_sha256: str,
    visual_geometry_sha256: str, visible_entity_refs: Sequence[str],
) -> dict[str, Any]:
    """Seal one deployable RGB-D keyframe reference without source paths."""

    _require(type(observation_index) is int and observation_index >= 0,
             "keyframe observation index is invalid")
    refs = list(visible_entity_refs)
    _require(all(type(item) is str and item for item in refs),
             "keyframe entity refs must be nonempty strings")
    value = {
        "schema_version": KEYFRAME_SCHEMA,
        "observation_index": observation_index,
        "rgb_sha256": _hex64(rgb_sha256, "RGB digest"),
        "depth_sha256": _hex64(depth_sha256, "depth digest"),
        "visual_geometry_sha256": _hex64(
            visual_geometry_sha256, "visual geometry digest"),
        "visible_entity_refs": sorted(set(refs)),
    }
    value["keyframe_sha256"] = _payload_sha(value, "keyframe_sha256")
    return _validate_keyframe(value)


def build_continuous_pose_belief(
    *, observation_index: int, mean_x_y_z_yaw: Sequence[float],
    covariance_diagonal: Sequence[float], source_id: str,
) -> dict[str, Any]:
    """Seal a causal episode-relative pose distribution, never a world pose."""

    value = {
        "schema_version": POSE_BELIEF_SCHEMA,
        "observation_index": observation_index,
        "frame": "episode_relative_observation_zero_origin",
        "mean_x_y_z_yaw": [
            _finite(item, "pose mean") for item in mean_x_y_z_yaw
        ],
        "covariance_diagonal": [
            _finite(item, "pose covariance") for item in covariance_diagonal
        ],
        "source_id": source_id,
        "is_world_pose": False,
        "defines_place_identity": False,
    }
    value["belief_sha256"] = _payload_sha(value, "belief_sha256")
    return _validate_pose_belief(value)


def _validate_keyframe(record: Mapping[str, Any]) -> dict[str, Any]:
    value = clone_json(dict(record))
    _exact_keys(value, {
        "schema_version", "observation_index", "rgb_sha256", "depth_sha256",
        "visual_geometry_sha256", "visible_entity_refs", "keyframe_sha256",
    }, "D-210 keyframe")
    _require(value["schema_version"] == KEYFRAME_SCHEMA and
             type(value["observation_index"]) is int and
             value["observation_index"] >= 0,
             "D-210 keyframe identity is invalid")
    for field in ("rgb_sha256", "depth_sha256", "visual_geometry_sha256"):
        _hex64(value[field], field)
    _require(type(value["visible_entity_refs"]) is list and
             value["visible_entity_refs"] == sorted(set(
                 value["visible_entity_refs"])) and
             all(type(item) is str and item for item in value["visible_entity_refs"]),
             "keyframe entity refs must be sorted unique public strings")
    _require(value["keyframe_sha256"] == _payload_sha(value, "keyframe_sha256"),
             "keyframe digest mismatch")
    return value


def _validate_pose_belief(record: Mapping[str, Any]) -> dict[str, Any]:
    value = clone_json(dict(record))
    _exact_keys(value, {
        "schema_version", "observation_index", "frame", "mean_x_y_z_yaw",
        "covariance_diagonal", "source_id", "is_world_pose",
        "defines_place_identity", "belief_sha256",
    }, "D-210 pose belief")
    _require(value["schema_version"] == POSE_BELIEF_SCHEMA and
             value["frame"] == "episode_relative_observation_zero_origin" and
             value["is_world_pose"] is False and
             value["defines_place_identity"] is False and
             type(value["observation_index"]) is int and
             value["observation_index"] >= 0,
             "D-210 pose-belief boundary changed")
    mean = [_finite(item, "pose mean") for item in value["mean_x_y_z_yaw"]]
    covariance = [_finite(item, "pose covariance")
                  for item in value["covariance_diagonal"]]
    _require(len(mean) == 4 and len(covariance) == 4 and
             all(item >= 0.0 for item in covariance),
             "pose belief needs four means and nonnegative variances")
    _require(type(value["source_id"]) is str and value["source_id"],
             "pose belief source must be nonempty")
    _require(value["belief_sha256"] == _payload_sha(value, "belief_sha256"),
             "pose belief digest mismatch")
    return value


def build_place_adapter_input(
    packet: Mapping[str, Any], *, prior_memory: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the only D-210 value a deployable memory method may receive."""

    approved = validate_contract(contract)
    _require(approved["status"] in {
        "approved_implementation_not_generation_authorized", "frozen_executable",
    }, "D-210 contract is unavailable")
    value = clone_json(dict(packet))
    _exact_keys(value, {
        "schema_version", "decision_time_s", "current_keyframe", "pose_belief",
        "incoming_transition_action_summary", "region_observations",
        "relation_observations", "prior_memory_ref", "public_constants",
    }, "D-210 adapter packet")
    _require(value["schema_version"] == ADAPTER_PACKET_SCHEMA,
             "D-210 adapter packet schema changed")
    _finite(value["decision_time_s"], "decision time")
    keyframe = _validate_keyframe(value["current_keyframe"])
    belief = _validate_pose_belief(value["pose_belief"])
    _require(keyframe["observation_index"] == belief["observation_index"],
             "keyframe and pose belief indices differ")
    transition = value["incoming_transition_action_summary"]
    if keyframe["observation_index"] == 0:
        _require(transition is None,
                 "observation zero cannot have an incoming transition")
    else:
        _require(type(transition) is dict,
                 "incoming transition summary is invalid")
        transition = validate_transition_action_summary(transition, approved)
        _require(transition["end_observation_index"] ==
                 keyframe["observation_index"],
                 "incoming transition ends at the wrong keyframe")
    prior = clone_json(dict(prior_memory))
    ref = value["prior_memory_ref"]
    _exact_keys(ref, {"graph_version", "graph_sha256"},
                "D-210 prior memory ref")
    _require(ref["graph_version"] == prior.get("graph_version") and
             ref["graph_sha256"] == _sha(prior),
             "D-210 prior memory binding mismatch")
    _require(type(value["region_observations"]) is list and
             type(value["relation_observations"]) is list and
             type(value["public_constants"]) is dict,
             "D-210 public observation fields have invalid types")
    adapter = {
        "decision_time_s": float(value["decision_time_s"]),
        "current_keyframe": keyframe,
        "continuous_pose_belief": belief,
        "incoming_transition_action_summary": clone_json(transition),
        "region_observations": clone_json(value["region_observations"]),
        "relation_observations": clone_json(value["relation_observations"]),
        "prior_memory": prior,
        "public_constants": clone_json(value["public_constants"]),
    }
    _reject_forbidden_adapter_keys(adapter)
    return adapter


def _safe_div(numerator: float, denominator: float, *, empty: float) -> float:
    return numerator / denominator if denominator else empty


def _f1(precision: float, recall: float) -> float:
    return _safe_div(2.0 * precision * recall, precision + recall, empty=0.0)


def _membership_map(rows: Any, name: str) -> dict[str, str]:
    _require(type(rows) is list and rows, f"{name} must be a nonempty list")
    result = {}
    for row in rows:
        _exact_keys(row, {"observation_id", "place_id"}, name)
        observation = row["observation_id"]
        place = row["place_id"]
        _require(type(observation) is str and observation and
                 type(place) is str and place and observation not in result,
                 f"{name} row is invalid or duplicated")
        result[observation] = place
    return result


def classify_private_loop_pair(
    *, position_error_m: float, same_reachable_component: bool,
    pre_registered_distinct_branch_or_room: bool,
    contract: Mapping[str, Any],
) -> str:
    """Apply the private continuous-space loop policy after candidate seal."""

    approved = validate_contract(contract)
    distance = _finite(position_error_m, "loop-pair position error")
    _require(distance >= 0.0 and type(same_reachable_component) is bool and
             type(pre_registered_distinct_branch_or_room) is bool,
             "private loop-pair evidence is invalid")
    policy = approved["reference_policy"]
    if (distance <= policy["loop_positive_max_position_error_m"] and
            same_reachable_component and
            not pre_registered_distinct_branch_or_room):
        return "positive"
    if (distance >= policy["negative_minimum_position_separation_m"] or
            pre_registered_distinct_branch_or_room):
        return "negative"
    return "unlabelled"


def evaluate_place_episode(
    *, scenario_id: str, prediction: Mapping[str, Any],
    reference: Mapping[str, Any], contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate label-invariant place identity, topology, entities, and process."""

    approved = validate_contract(contract)
    _require(scenario_id in P0_SCENARIOS, "metric scenario is not in D-210 P0")
    _exact_keys(prediction, {
        "place_membership", "loop_pair_predictions", "edge_endpoint_pairs",
        "entity_place_attachments", "contamination_series",
        "error_decomposition", "candidate_catalog_sha256",
    }, "D-210 prediction")
    _exact_keys(reference, {
        "place_membership", "loop_pairs", "edge_endpoint_pairs",
        "entity_place_attachments", "candidate_catalog_sha256",
    }, "D-210 reference")
    candidate_sha = _hex64(prediction["candidate_catalog_sha256"],
                           "prediction candidate catalog digest")
    _require(reference["candidate_catalog_sha256"] == candidate_sha,
             "private reference is not bound to the sealed candidate catalog")
    predicted = _membership_map(prediction["place_membership"],
                                "predicted place membership")
    truth = _membership_map(reference["place_membership"],
                           "reference place membership")
    _require(set(predicted) == set(truth),
             "prediction and reference observation sets differ")
    observations = sorted(truth)
    tp = fp = fn = tn = 0
    for left_index, left in enumerate(observations):
        for right in observations[left_index + 1:]:
            expected_same = truth[left] == truth[right]
            predicted_same = predicted[left] == predicted[right]
            if expected_same and predicted_same:
                tp += 1
            elif not expected_same and predicted_same:
                fp += 1
            elif expected_same and not predicted_same:
                fn += 1
            else:
                tn += 1
    precision = _safe_div(tp, tp + fp, empty=1.0)
    recall = _safe_div(tp, tp + fn, empty=1.0)

    # Place node names are arbitrary.  Evaluation aligns each predicted cluster
    # to its largest-overlap private reference cluster, then scores topology and
    # entity attachment.  Pairwise place metrics above retain merge/split costs.
    predicted_to_truth = {}
    for predicted_place in sorted(set(predicted.values())):
        overlaps = {}
        for observation in observations:
            if predicted[observation] == predicted_place:
                truth_place = truth[observation]
                overlaps[truth_place] = overlaps.get(truth_place, 0) + 1
        predicted_to_truth[predicted_place] = min(
            overlaps, key=lambda place: (-overlaps[place], place))

    loop_predictions = prediction["loop_pair_predictions"]
    _require(type(loop_predictions) is list, "loop predictions must be a list")
    predicted_loops = {}
    for row in loop_predictions:
        _exact_keys(row, {"pair_id", "is_same_place"}, "loop prediction")
        _require(type(row["pair_id"]) is str and row["pair_id"] and
                 type(row["is_same_place"]) is bool and
                 row["pair_id"] not in predicted_loops,
                 "loop prediction is invalid or duplicated")
        predicted_loops[row["pair_id"]] = row["is_same_place"]
    reference_loops = {}
    for row in reference["loop_pairs"]:
        _exact_keys(row, {"pair_id", "is_same_place"}, "loop reference")
        _require(type(row["pair_id"]) is str and row["pair_id"] and
                 type(row["is_same_place"]) is bool and
                 row["pair_id"] not in reference_loops,
                 "loop reference is invalid or duplicated")
        reference_loops[row["pair_id"]] = row["is_same_place"]
    _require(set(predicted_loops) == set(reference_loops),
             "loop prediction/reference pair IDs differ")
    loop_tp = sum(predicted_loops[key] and reference_loops[key]
                  for key in reference_loops)
    loop_fp = sum(predicted_loops[key] and not reference_loops[key]
                  for key in reference_loops)
    loop_fn = sum(not predicted_loops[key] and reference_loops[key]
                  for key in reference_loops)
    loop_precision = _safe_div(loop_tp, loop_tp + loop_fp, empty=1.0)
    loop_recall = _safe_div(loop_tp, loop_tp + loop_fn, empty=1.0)

    _require(type(prediction["edge_endpoint_pairs"]) is list and
             type(reference["edge_endpoint_pairs"]) is list and
             all(type(row) is list for row in
                 prediction["edge_endpoint_pairs"] +
                 reference["edge_endpoint_pairs"]),
             "edge endpoint pairs must be lists")
    predicted_edge_rows = prediction["edge_endpoint_pairs"]
    reference_edge_rows = reference["edge_endpoint_pairs"]
    _require(all(len(row) == 3 and row[1] in predicted_to_truth and
                 row[2] in predicted_to_truth
                 for row in predicted_edge_rows),
             "predicted edge endpoint is not a predicted place")
    predicted_edges = {
        (row[0], predicted_to_truth[row[1]], predicted_to_truth[row[2]])
        for row in predicted_edge_rows
    }
    reference_edges = {tuple(row) for row in reference_edge_rows}
    _require(all(len(row) == 3 and all(type(item) is str and item for item in row)
                 for row in predicted_edges | reference_edges),
             "edge endpoint pairs must be [relation,from,to]")
    edge_tp = len(predicted_edges & reference_edges)
    edge_precision = _safe_div(edge_tp, len(predicted_edges), empty=1.0)
    edge_recall = _safe_div(edge_tp, len(reference_edges), empty=1.0)

    _require(type(prediction["entity_place_attachments"]) is list and
             type(reference["entity_place_attachments"]) is list and
             all(type(row) is list for row in
                 prediction["entity_place_attachments"] +
                 reference["entity_place_attachments"]),
             "entity attachments must be lists")
    _require(all(len(row) == 2 and row[1] in predicted_to_truth
                 for row in prediction["entity_place_attachments"]),
             "predicted entity attachment is not a predicted place")
    predicted_entities = {
        (row[0], predicted_to_truth[row[1]])
        for row in prediction["entity_place_attachments"]
    }
    reference_entities = {tuple(row) for row in
                          reference["entity_place_attachments"]}
    _require(all(len(row) == 2 and all(type(item) is str and item for item in row)
                 for row in predicted_entities | reference_entities),
             "entity attachments must be [entity,place]")
    entity_accuracy = _safe_div(
        len(predicted_entities & reference_entities), len(reference_entities),
        empty=1.0)

    contamination = prediction["contamination_series"]
    _require(type(contamination) is list and contamination and
             all(type(value) in {int, float} and
                 math.isfinite(float(value)) and 0.0 <= float(value) <= 1.0
                 for value in contamination),
             "contamination series must contain finite fractions in [0,1]")
    if len(contamination) == 1:
        contamination_auc = float(contamination[0])
    else:
        contamination_auc = sum(
            (float(left) + float(right)) / 2.0
            for left, right in zip(contamination, contamination[1:])
        ) / (len(contamination) - 1)
    errors = prediction["error_decomposition"]
    expected_errors = set(approved["metrics"]["error_decomposition"])
    _require(type(errors) is dict and set(errors) == expected_errors and
             all(type(value) is int and value >= 0 for value in errors.values()),
             "D-210 error decomposition changed")
    result = {
        "schema_version": METRIC_SCHEMA,
        "scenario_id": scenario_id,
        "evidence_role": approved["scenarios"][scenario_id]["evidence_role"],
        "headline_eligible": scenario_id in HEADLINE_SCENARIOS,
        "place_pairwise_precision": precision,
        "place_pairwise_recall": recall,
        "place_pairwise_f1": _f1(precision, recall),
        "duplicate_place_rate": _safe_div(fn, tp + fn, empty=0.0),
        "false_merge_rate": _safe_div(fp, fp + tn, empty=0.0),
        "loop_closure_precision": loop_precision,
        "loop_closure_recall": loop_recall,
        "topology_edge_endpoint_f1": _f1(edge_precision, edge_recall),
        "entity_place_attachment_accuracy": entity_accuracy,
        "contamination_auc": contamination_auc,
        "error_decomposition": clone_json(errors),
        "exact_action_or_true_pose_oracle_included": False,
    }
    result["metrics_sha256"] = _payload_sha(result, "metrics_sha256")
    return result


def aggregate_p0_metrics(
    episodes: Sequence[Mapping[str, Any]], *, contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Macro-average all P0 rows and a separate headline-only subset."""

    approved = validate_contract(contract)
    _require(type(episodes) in {list, tuple} and episodes,
             "metric aggregation needs episode rows")
    rows = [clone_json(dict(row)) for row in episodes]
    metric_names = approved["metrics"]["primary"]
    for row in rows:
        _require(row.get("schema_version") == METRIC_SCHEMA and
                 row.get("metrics_sha256") == _payload_sha(row, "metrics_sha256") and
                 row.get("exact_action_or_true_pose_oracle_included") is False,
                 "episode metric row is invalid or includes an oracle")
    headline = [row for row in rows if row["headline_eligible"]]
    _require(headline, "headline aggregation has no P03/P04/P06/P07/P08 row")

    def means(group: Sequence[Mapping[str, Any]]) -> dict[str, float]:
        return {name: sum(float(row[name]) for row in group) / len(group)
                for name in metric_names}

    result = {
        "schema_version": "vsmt-d210-p0-metric-aggregate-v1",
        "episode_count": len(rows),
        "headline_episode_count": len(headline),
        "all_p0_macro": means(rows),
        "headline_macro": means(headline),
        "headline_scenarios": approved["metrics"]["headline_scenarios"],
        "control_scenarios_excluded_from_headline":
            approved["metrics"]["control_scenarios"],
        "diagnostic_oracles_excluded": True,
    }
    result["aggregate_sha256"] = _payload_sha(result, "aggregate_sha256")
    return result
