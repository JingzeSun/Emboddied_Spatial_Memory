"""D-212 correction of the D-211 route seal and one raw smoke.

This module does not plan routes and does not touch a simulator.  It binds the
two already audited development houses, recomputes the reachable-grid and
scenario semantics of all twelve publicly constructed routes, and limits raw
execution to slot 0.  Adapter materialization, private evaluation, metrics and
the remaining eleven raw episodes stay closed.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any, Mapping, Sequence

from cpmt.hashing import canonical_json, clone_json

from .d210_place_memory import (
    D210Error,
    build_p0_manifests,
    validate_contract as validate_d210_contract,
    validate_route_plan,
)


CONTRACT_SCHEMA = "vsmt-vm04-d211-p0-seal-single-smoke-contract-v2"
ROUTE_BINDING_SCHEMA = "vsmt-vm04-d211-route-execution-binding-v2"
ROUTE_BUNDLE_SCHEMA = "vsmt-vm04-d211-route-bundle-v2"
SEALED_BINDINGS_SCHEMA = "vsmt-vm04-d211-sealed-route-bindings-v2"
REACHABLE_SCAN_SCHEMA = "vsmt-vm04-d211-reachable-scan-v1"
PUBLIC_ROUTE_EVIDENCE_SCHEMA = "vsmt-vm04-d211-public-route-evidence-v1"
SCENARIO_RECEIPT_SCHEMA = "vsmt-vm04-d211-scenario-receipt-v1"
STEP_RECEIPT_SCHEMA = "vsmt-vm04-d211-step-reachability-v1"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
GRID_TOLERANCE_M = 0.01


class D211Error(D210Error):
    """D-211 scope, source binding, route seal or smoke boundary changed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise D211Error(message)


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _payload_sha(record: Mapping[str, Any], field: str) -> str:
    value = clone_json(dict(record))
    value.pop(field, None)
    return _sha(value)


def _exact(value: Any, keys: set[str], name: str) -> None:
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


def validate_d211_contract(
    contract: Mapping[str, Any], *, base_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the user-authorized overlay without treating it as run proof."""

    base = validate_d210_contract(base_contract)
    value = clone_json(dict(contract))
    _exact(value, {
        "schema_version", "decision_id", "status", "reviewed_baseline_commit",
        "expected_reviewed_implementation_commit", "activation_policy",
        "base_contract", "authorization", "source_binding", "route_sealing",
        "simulator_runtime", "single_slot_smoke", "resource_policy",
    }, "D-211 contract")
    _require(value["schema_version"] == CONTRACT_SCHEMA and
             value["decision_id"] == "D-212" and
             value["status"] in {
                 "authorized_scope_implementation_pending_reviewed_commit",
                 "frozen_executable_seal_and_single_slot_smoke",
             } and
             value["reviewed_baseline_commit"] ==
             "8d6bd13158a5cfd56a110460dc5c926015e5b52c",
             "D-211 identity or reviewed baseline changed")
    expected_commit = value["expected_reviewed_implementation_commit"]
    _require(expected_commit is None or
             (type(expected_commit) is str and
              HEX40.fullmatch(expected_commit) is not None),
             "D-211 reviewed code commit is invalid")
    if value["status"] == "frozen_executable_seal_and_single_slot_smoke":
        _require(expected_commit is not None,
                 "an executable D-211 contract needs a reviewed code commit")
    else:
        _require(expected_commit is None,
                 "the implementation-review D-211 contract cannot pin code")
    _require(value["activation_policy"] == {
        "executable_checkout_must_be_clean": True,
        "executable_checkout_parent_must_equal_reviewed_implementation_commit":
            True,
        "activation_commit_may_change_only": [
            "configs/vsmt/vm04_d211_p0_seal_single_smoke_v2.json",
        ],
    }, "D-212 activation policy changed")

    base_ref = value["base_contract"]
    _require(base_ref == {
        "relative_path": "configs/vsmt/vm04_d210_dual_layer_p0_v1.json",
        "file_sha256":
            "d93f43b654eac64469aa87d6e9b6542531ab3ab463588bb9a53199fef911b60c",
        "validated_value_sha256": _sha(base),
    }, "D-211 base D-210 binding changed")
    _require(value["authorization"] == {
        "source_house_binding_authorized": True,
        "twelve_route_sealing_authorized": True,
        "single_slot_raw_smoke_authorized": True,
        "private_simulator_pose_capture_authorized": True,
        "private_instance_and_entity_truth_capture_authorized": True,
        "twelve_slot_raw_generation_authorized": False,
        "adapter_materialization_authorized": False,
        "private_evaluation_authorized": False,
        "training_authorized": False,
        "validation_authorized": False,
        "confirmation_authorized": False,
    }, "D-211 authorization scope changed")

    source = value["source_binding"]
    _exact(source, {
        "source", "source_release_commit", "source_report_relative_path",
        "source_report_file_sha256", "houses", "reuse_role",
        "replacement_after_route_or_smoke_failure_allowed",
    }, "D-211 source binding")
    _require(source["source"] == "ProcTHOR-10K_train_0.1.2" and
             source["source_release_commit"] ==
             "d54954a81e7126001e552c2d7904ee2e0d49eaae" and
             source["source_report_relative_path"] ==
             "results/vsmt_vm04_root_cause_audit_v1.json" and
             source["source_report_file_sha256"] ==
             "ecf4e6735016db4dea71873193d0a7fbdb606480a18237cb7871129f562ece73" and
             source["reuse_role"] ==
             "already_audited_development_houses_only_not_confirmation" and
             source["replacement_after_route_or_smoke_failure_allowed"] is False,
             "D-211 source provenance changed")
    expected_houses = [
        {"house_slot": 0, "source_house_id": "train:004270",
         "source_record_sha256":
             "79a1cfe6c80e913305cc6d2ea047323bca1d05763b29a162cbef23c76b80026f"},
        {"house_slot": 1, "source_house_id": "train:008243",
         "source_record_sha256":
             "cdbd7bf8e91a6fc3a52b1a92487e22badc234793d23c74c0a59240d43980bea7"},
    ]
    _require(source["houses"] == expected_houses,
             "D-211 fixed development houses changed")

    _require(value["route_sealing"] == {
        "slot_count": 12,
        "complete_action_sequence_required": True,
        "private_initial_pose_required": True,
        "initial_yaw_multiple_degrees": 90.0,
        "reachable_scan_record_and_recomputed_step_receipt_required": True,
        "public_rgbd_evidence_record_required": True,
        "scenario_specific_recomputable_receipt_required": True,
        "future_action_outcome_or_private_reference_allowed": False,
        "all_planned_translation_endpoints_preverified_reachable": True,
        "p04_alias_selection_rule":
            "top_public_cosine_pair_among_nominal_pairs_separated_by_at_least_1_5m",
        "p04_absolute_similarity_threshold": None,
        "scenario_role_change_after_failure_allowed": False,
        "route_replacement_after_smoke_outcome_allowed": False,
        "sealed_output_is_immutable": True,
    }, "D-211 route-sealing boundary changed")
    _require(value["simulator_runtime"] == {
        "ai2thor_package_version": "5.0.0",
        "platform": "CloudRendering",
        "width": 224, "height": 224, "field_of_view_degrees": 90.0,
        "grid_size_m": 0.25, "snap_to_grid": True,
        "rotate_step_degrees": 90.0, "render_depth_image": True,
        "render_instance_segmentation": True,
    }, "D-212 simulator runtime changed")
    _require(value["single_slot_smoke"] == {
        "slot": 0, "house_slot": 0, "scenario_id": "P01",
        "role": "engineering_only_not_headline_or_effect_evidence",
        "fresh_controller_required": True,
        "simulator_intervention_allowed": False,
        "observation_zero_saved": True,
        "observation_after_every_successful_registered_action_saved": True,
        "failed_action_receipt_and_completed_prefix_retained": True,
        "append_only_action_and_private_frame_journals_required": True,
        "public_raw_channels": [
            "rgb_uint8_npy", "depth_m_float32_npy",
            "sensor_calibration_json", "frame_digest",
        ],
        "private_ground_truth_channels": [
            "per_observation_agent_world_pose",
            "per_observation_camera_world_pose",
            "per_observation_instance_masks",
            "per_observation_simulator_object_to_private_entity_mapping",
            "per_observation_entity_state",
            "public_frame_digest_binding",
        ],
        "provenance_channels": [
            "complete_sealed_route", "registered_action_requests_and_success",
            "action_and_observation_ordinals", "capture_monotonic_time_ns",
            "source_record_digest", "worker_terminal_receipt",
        ],
        "forbidden_public_and_provenance_outputs": [
            "simulator_world_pose", "instance_masks", "simulator_object_id",
            "private_entity_id", "reference_place_region", "loop_pair_label",
            "teacher_target", "adapter_packet", "model_metric",
        ],
        "success_condition":
            "observation_count_equals_planned_action_count_plus_one_and_all_registered_actions_succeed",
        "failure_replacement_allowed": False,
    }, "D-211 single-slot smoke boundary changed")
    _require(value["resource_policy"] == {
        "worker_count": 1,
        "single_worker_reason":
            "the_authorized_smoke_contains_exactly_one_execution_unit",
        "wall_clock_timeout_allowed": False,
        "minimum_data_disk_free_bytes": 8589934592,
        "emergency_data_disk_free_bytes": 4294967296,
        "maximum_smoke_output_bytes": 2147483648,
    }, "D-211 resource policy changed")
    _require(base["slot_plan"][0] == {
        "slot": 0, "house_slot": 0, "scenario_id": "P01", "seed": 26091800,
    }, "D-210 slot zero changed under D-211")
    return value


def _normalize_pose(pose: Mapping[str, Any], name: str) -> dict[str, float]:
    _exact(pose, {"x_m", "y_m", "z_m", "yaw_deg", "horizon_deg"}, name)
    return {key: _finite(pose[key], f"{name} {key}") for key in pose}


def _axis_forward(yaw_deg: float) -> tuple[float, float]:
    quadrant = yaw_deg / 90.0
    nearest = round(quadrant)
    _require(abs(quadrant - nearest) <= 1e-9,
             "planned translation must start from an axis-aligned yaw")
    return ((0.0, 1.0), (1.0, 0.0), (0.0, -1.0),
            (-1.0, 0.0))[int(nearest) % 4]


def nominal_route_poses(
    route_plan: Mapping[str, Any], initial_pose: Mapping[str, Any],
    *, base_contract: Mapping[str, Any],
) -> list[dict[str, float]]:
    """Integrate registered commands for planning checks, never place truth."""

    route = validate_route_plan(route_plan, base_contract)
    pose = _normalize_pose(initial_pose, "D-211 initial pose")
    x, y, z = pose["x_m"], pose["y_m"], pose["z_m"]
    yaw, horizon = pose["yaw_deg"], pose["horizon_deg"]
    poses = [dict(pose)]
    for action in route["actions"]:
        name = action["action"]
        if name in {"MoveAhead", "MoveBack", "MoveLeft", "MoveRight"}:
            forward_x, forward_z = _axis_forward(yaw)
            right_x, right_z = forward_z, -forward_x
            lateral, forward = {
                "MoveAhead": (0.0, 1.0), "MoveBack": (0.0, -1.0),
                "MoveLeft": (-1.0, 0.0), "MoveRight": (1.0, 0.0),
            }[name]
            magnitude = float(action["request"]["moveMagnitude"])
            x += magnitude * (forward * forward_x + lateral * right_x)
            z += magnitude * (forward * forward_z + lateral * right_z)
        elif name in {"RotateLeft", "RotateRight"}:
            sign = -1.0 if name == "RotateLeft" else 1.0
            yaw = (yaw + sign * float(action["request"]["degrees"])) % 360.0
        elif name in {"LookUp", "LookDown"}:
            sign = -1.0 if name == "LookUp" else 1.0
            horizon += sign * float(action["request"]["degrees"])
        poses.append({"x_m": x, "y_m": y, "z_m": z,
                      "yaw_deg": yaw, "horizon_deg": horizon})
    return poses


def seal_reachable_scan(
    *, house_slot: int, source_house_id: str,
    raw_positions: Sequence[Mapping[str, Any]], contract: Mapping[str, Any],
    base_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Seal the actual pre-execution grid so route checks are recomputable."""

    approved = validate_d211_contract(contract, base_contract=base_contract)
    _require(type(house_slot) is int and house_slot in {0, 1},
             "reachable scan house slot is invalid")
    source = approved["source_binding"]["houses"][house_slot]
    _require(source_house_id == source["source_house_id"],
             "reachable scan source house changed")
    _require(type(raw_positions) in {list, tuple} and raw_positions,
             "reachable scan contains no positions")
    positions = []
    for index, row in enumerate(raw_positions):
        _exact(row, {"x", "y", "z"}, f"reachable position {index}")
        positions.append({axis: _finite(row[axis], f"reachable {index}.{axis}")
                          for axis in ("x", "y", "z")})
    positions.sort(key=lambda row: (row["x"], row["y"], row["z"]))
    grid = float(approved["simulator_runtime"]["grid_size_m"])
    origin = positions[0]
    cells: set[tuple[int, int]] = set()
    for row in positions:
        _require(abs(row["y"] - origin["y"]) <= GRID_TOLERANCE_M,
                 "multilevel reachable scans need a separate reviewed route")
        key = (round((row["x"] - origin["x"]) / grid),
               round((row["z"] - origin["z"]) / grid))
        _require(key not in cells, "reachable scan repeats a grid cell")
        _require(abs(row["x"] - (origin["x"] + key[0] * grid)) <=
                 GRID_TOLERANCE_M and
                 abs(row["z"] - (origin["z"] + key[1] * grid)) <=
                 GRID_TOLERANCE_M,
                 "reachable position is off the registered grid")
        cells.add(key)
    value = {
        "schema_version": REACHABLE_SCAN_SCHEMA,
        "house_slot": house_slot, "source_house_id": source_house_id,
        "source_action": "GetReachablePositions",
        "source_action_success": True,
        "scan_phase": "pre_execution_public_reachable_scan",
        "grid_size_m": grid, "origin_x_m": origin["x"],
        "origin_z_m": origin["z"], "level_y_m": origin["y"],
        "cells": [[a, b] for a, b in sorted(cells)],
        "private_identity_used": False,
        "future_or_action_outcome_used": False,
        "positions_chosen_after_failure": False,
    }
    value["reachable_scan_sha256"] = _payload_sha(
        value, "reachable_scan_sha256")
    return validate_reachable_scan(
        value, contract=approved, base_contract=base_contract)


def validate_reachable_scan(
    scan: Mapping[str, Any], *, contract: Mapping[str, Any],
    base_contract: Mapping[str, Any],
) -> dict[str, Any]:
    approved = validate_d211_contract(contract, base_contract=base_contract)
    value = clone_json(dict(scan))
    _exact(value, {
        "schema_version", "house_slot", "source_house_id", "source_action",
        "source_action_success", "scan_phase", "grid_size_m", "origin_x_m",
        "origin_z_m", "level_y_m", "cells", "private_identity_used",
        "future_or_action_outcome_used", "positions_chosen_after_failure",
        "reachable_scan_sha256",
    }, "D-211 reachable scan")
    slot = value["house_slot"]
    _require(type(slot) is int and slot in {0, 1} and
             value["source_house_id"] ==
             approved["source_binding"]["houses"][slot]["source_house_id"],
             "reachable scan house binding changed")
    _require(value["schema_version"] == REACHABLE_SCAN_SCHEMA and
             value["source_action"] == "GetReachablePositions" and
             value["source_action_success"] is True and
             value["scan_phase"] == "pre_execution_public_reachable_scan" and
             value["grid_size_m"] == 0.25 and
             value["private_identity_used"] is False and
             value["future_or_action_outcome_used"] is False and
             value["positions_chosen_after_failure"] is False,
             "reachable scan provenance changed")
    for name in ("origin_x_m", "origin_z_m", "level_y_m"):
        value[name] = _finite(value[name], name)
    cells = value["cells"]
    _require(type(cells) is list and cells and all(
        type(row) is list and len(row) == 2 and
        all(type(item) is int for item in row) for row in cells),
        "reachable cells must be nonempty integer pairs")
    _require([tuple(row) for row in cells] == sorted(set(tuple(row) for row in cells)),
             "reachable cells must be unique and sorted")
    _hex64(value["reachable_scan_sha256"], "reachable scan digest")
    _require(value["reachable_scan_sha256"] ==
             _payload_sha(value, "reachable_scan_sha256"),
             "reachable scan digest mismatch")
    return value


def _reachable_cell(scan: Mapping[str, Any], pose: Mapping[str, float]) -> list[int]:
    grid = float(scan["grid_size_m"])
    key = [round((pose["x_m"] - float(scan["origin_x_m"])) / grid),
           round((pose["z_m"] - float(scan["origin_z_m"])) / grid)]
    _require(abs(pose["x_m"] -
                 (float(scan["origin_x_m"]) + key[0] * grid)) <=
             GRID_TOLERANCE_M and
             abs(pose["z_m"] -
                 (float(scan["origin_z_m"]) + key[1] * grid)) <=
             GRID_TOLERANCE_M,
             "planned observation is off the reachable grid")
    _require(key in scan["cells"], "planned observation is not reachable")
    return key


def seal_step_reachability(
    *, route_plan: Mapping[str, Any], initial_pose: Mapping[str, Any],
    reachable_scan: Mapping[str, Any], contract: Mapping[str, Any],
    base_contract: Mapping[str, Any],
) -> dict[str, Any]:
    route = validate_route_plan(route_plan, base_contract)
    scan = validate_reachable_scan(
        reachable_scan, contract=contract, base_contract=base_contract)
    _require(scan["house_slot"] == route["house_slot"],
             "route and reachable scan house slots disagree")
    poses = nominal_route_poses(
        route, initial_pose, base_contract=base_contract)
    steps = [{"observation_index": index,
              "action": None if index == 0 else
                  route["actions"][index - 1]["action"],
              "cell": _reachable_cell(scan, pose), "reachable": True}
             for index, pose in enumerate(poses)]
    value = {
        "schema_version": STEP_RECEIPT_SCHEMA,
        "route_plan_sha256": route["route_plan_sha256"],
        "reachable_scan_sha256": scan["reachable_scan_sha256"],
        "verified_observation_count": len(steps), "steps": steps,
        "every_planned_translation_endpoint_verified_reachable": True,
        "tolerance_relaxed": False,
    }
    value["step_reachability_sha256"] = _payload_sha(
        value, "step_reachability_sha256")
    return value


def _normalize_public_observations(
    observations: Sequence[Mapping[str, Any]], *, route: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    for raw in observations:
        row = clone_json(dict(raw))
        _exact(row, {"observation_index", "rgb_sha256", "depth_sha256",
                     "calibration_sha256", "place_descriptor",
                     "public_region_role", "visible_entity_region_refs"},
               "public route evidence observation")
        index = row["observation_index"]
        _require(type(index) is int and 0 <= index < route["observation_count"],
                 "public route evidence index is outside the route")
        for field in ("rgb_sha256", "depth_sha256", "calibration_sha256"):
            _hex64(row[field], field)
        descriptor = row["place_descriptor"]
        _require(type(descriptor) is list and descriptor and all(
            type(item) in {int, float} and math.isfinite(float(item))
            for item in descriptor), "place descriptor is invalid")
        norm = math.sqrt(sum(float(item) ** 2 for item in descriptor))
        _require(norm > 0.0, "place descriptor must be nonzero")
        row["place_descriptor"] = [float(item) for item in descriptor]
        _require(row["public_region_role"] in {"room", "corridor", "unknown"},
                 "public region role is invalid")
        refs = row["visible_entity_region_refs"]
        _require(type(refs) is list and refs == sorted(set(refs)) and all(
            type(item) is str and item.startswith("region:") for item in refs),
            "visible entity refs must be sorted anonymous public regions")
        rows.append(row)
    _require(rows and [row["observation_index"] for row in rows] ==
             sorted(set(row["observation_index"] for row in rows)),
             "public route evidence indices must be unique and sorted")
    return rows


def seal_public_route_evidence(
    *, route_plan: Mapping[str, Any], observations: Sequence[Mapping[str, Any]],
    base_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Seal public pre-execution RGB-D descriptors used only for route choice."""

    route = validate_route_plan(route_plan, base_contract)
    rows = _normalize_public_observations(observations, route=route)
    value = {
        "schema_version": PUBLIC_ROUTE_EVIDENCE_SCHEMA,
        "slot": route["slot"],
        "route_plan_sha256": route["route_plan_sha256"],
        "scan_phase": "pre_execution_public_rgbd_route_survey",
        "observations": rows, "contains_world_pose": False,
        "contains_instance_or_object_identity": False,
        "future_or_action_outcome_used": False,
    }
    value["public_route_evidence_sha256"] = _payload_sha(
        value, "public_route_evidence_sha256")
    return validate_public_route_evidence(value, route_plan=route,
                                          base_contract=base_contract)


def validate_public_route_evidence(
    evidence: Mapping[str, Any], *, route_plan: Mapping[str, Any],
    base_contract: Mapping[str, Any],
) -> dict[str, Any]:
    route = validate_route_plan(route_plan, base_contract)
    value = clone_json(dict(evidence))
    _exact(value, {"schema_version", "slot", "route_plan_sha256", "scan_phase",
                   "observations", "contains_world_pose",
                   "contains_instance_or_object_identity",
                   "future_or_action_outcome_used",
                   "public_route_evidence_sha256"},
           "D-211 public route evidence")
    _require(value["schema_version"] == PUBLIC_ROUTE_EVIDENCE_SCHEMA and
             value["slot"] == route["slot"] and
             value["route_plan_sha256"] == route["route_plan_sha256"] and
             value["scan_phase"] == "pre_execution_public_rgbd_route_survey" and
             value["contains_world_pose"] is False and
             value["contains_instance_or_object_identity"] is False and
             value["future_or_action_outcome_used"] is False,
             "public route evidence boundary changed")
    normalized = _normalize_public_observations(
        value["observations"], route=route)
    _require(value["observations"] == normalized,
             "public route evidence observations are not canonical")
    _hex64(value["public_route_evidence_sha256"],
           "public route evidence digest")
    _require(value["public_route_evidence_sha256"] ==
             _payload_sha(value, "public_route_evidence_sha256"),
             "public route evidence digest mismatch")
    return value


def _position_distance(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    return math.hypot(float(left["x_m"]) - float(right["x_m"]),
                      float(left["z_m"]) - float(right["z_m"]))


def _yaw_distance(left: float, right: float) -> float:
    return abs(((float(left) - float(right) + 180.0) % 360.0) - 180.0)


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    _require(len(left) == len(right), "place descriptor dimensions disagree")
    numerator = sum(float(a) * float(b) for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(float(a) ** 2 for a in left))
    right_norm = math.sqrt(sum(float(b) ** 2 for b in right))
    return numerator / (left_norm * right_norm)


def _inverse_route(action_names: Sequence[str]) -> bool:
    inverse = {
        "MoveAhead": "MoveBack", "MoveBack": "MoveAhead",
        "MoveLeft": "MoveRight", "MoveRight": "MoveLeft",
        "RotateLeft": "RotateRight", "RotateRight": "RotateLeft",
        "LookUp": "LookDown", "LookDown": "LookUp",
    }
    if len(action_names) % 2:
        return False
    half = len(action_names) // 2
    return list(action_names[half:]) == [
        inverse[name] for name in reversed(action_names[:half])]


def _observation_map(evidence: Mapping[str, Any]) -> dict[int, dict[str, Any]]:
    return {row["observation_index"]: row for row in evidence["observations"]}


def _annotation_keys(scenario: str) -> set[str]:
    return {
        "P01": {"bend_observation_indices", "frontier_observation_index"},
        "P02": {"turnaround_observation_index", "return_observation_index"},
        "P03": {"loop_anchor_observation_indices"},
        "P04": {"alias_observation_indices"},
        "P05": {"same_place_observation_indices"},
        "P06": {"junction_observation_indices",
                "branch_endpoint_observation_indices"},
        "P07": {"loop_observation_ranges"},
        "P08": {"room_anchor_observation_indices",
                "corridor_observation_indices"},
    }[scenario]


def seal_scenario_receipt(
    *, route_plan: Mapping[str, Any], initial_pose: Mapping[str, Any],
    public_route_evidence: Mapping[str, Any],
    annotations: Mapping[str, Any], contract: Mapping[str, Any],
    base_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Recompute the distinct geometric/public claim of one P01--P08 route."""

    approved = validate_d211_contract(contract, base_contract=base_contract)
    route = validate_route_plan(route_plan, base_contract)
    evidence = validate_public_route_evidence(
        public_route_evidence, route_plan=route, base_contract=base_contract)
    note = clone_json(dict(annotations))
    _exact(note, _annotation_keys(route["scenario_id"]),
           f"{route['scenario_id']} scenario annotations")
    poses = nominal_route_poses(route, initial_pose, base_contract=base_contract)
    names = [row["action"] for row in route["actions"]]
    n = len(names)
    observations = _observation_map(evidence)
    scenario = route["scenario_id"]
    facts: dict[str, Any]

    if scenario == "P01":
        bends = note["bend_observation_indices"]
        frontier = note["frontier_observation_index"]
        _require(type(bends) is list and len(bends) == 2 and
                 bends == sorted(set(bends)) and
                 all(type(index) is int and 1 <= index <= n for index in bends),
                 "P01 needs two ordered bend observations")
        turns = [names[index - 1] for index in bends]
        _require(turns in (["RotateLeft", "RotateRight"],
                           ["RotateRight", "RotateLeft"]),
                 "P01 bends must be opposite registered quarter turns")
        _require(type(frontier) is int and frontier == n and
                 _position_distance(poses[0], poses[frontier]) >= 1.5,
                 "P01 frontier must finish at least 1.5 m from the start")
        segment_headings = []
        for index, name in enumerate(names):
            if name in {"MoveAhead", "MoveBack", "MoveLeft", "MoveRight"}:
                dx = round((poses[index + 1]["x_m"] - poses[index]["x_m"]) / .25)
                dz = round((poses[index + 1]["z_m"] - poses[index]["z_m"]) / .25)
                direction = [dx, dz]
                if not segment_headings or segment_headings[-1] != direction:
                    segment_headings.append(direction)
        _require(len(segment_headings) >= 3 and
                 segment_headings[0] == segment_headings[2] and
                 segment_headings[0] != segment_headings[1],
                 "P01 route does not contain a Z-shaped three-segment prefix")
        facts = {"z_segment_headings": segment_headings[:3],
                 "start_to_frontier_distance_m":
                     _position_distance(poses[0], poses[frontier])}
    elif scenario == "P02":
        halfway = note["turnaround_observation_index"]
        returned = note["return_observation_index"]
        _require(type(halfway) is int and halfway * 2 == n and returned == n and
                 _inverse_route(names),
                 "P02 second half must be the exact registered inverse route")
        distance = _position_distance(poses[0], poses[-1])
        _require(distance <= 1e-9 and _yaw_distance(
            poses[0]["yaw_deg"], poses[-1]["yaw_deg"]) <= 1e-9,
            "P02 exact inverse route does not return to its initial pose")
        facts = {"exact_inverse": True, "return_position_error_m": distance}
    elif scenario == "P03":
        anchors = note["loop_anchor_observation_indices"]
        _require(anchors == [0, n] and not _inverse_route(names),
                 "P03 must close by an alternate, non-inverse path")
        distance = _position_distance(poses[0], poses[-1])
        unique = {(round(row["x_m"] / .25), round(row["z_m"] / .25))
                  for row in poses}
        _require(distance <= float(base_contract["reference_policy"]
                                   ["loop_positive_max_position_error_m"]) and
                 len(unique) >= 4,
                 "P03 route is not a nontrivial alternate loop closure")
        facts = {"alternate_path": True, "return_position_error_m": distance,
                 "unique_nominal_cells": len(unique)}
    elif scenario == "P04":
        pair = note["alias_observation_indices"]
        _require(type(pair) is list and len(pair) == 2 and pair[0] < pair[1] and
                 all(index in observations for index in pair),
                 "P04 alias pair must name two public survey observations")
        minimum = float(base_contract["reference_policy"]
                        ["negative_minimum_position_separation_m"])
        candidates = []
        rows = evidence["observations"]
        for left_index, left in enumerate(rows):
            for right in rows[left_index + 1:]:
                a, b = left["observation_index"], right["observation_index"]
                if _position_distance(poses[a], poses[b]) >= minimum:
                    candidates.append((_cosine(left["place_descriptor"],
                                               right["place_descriptor"]),
                                       [a, b]))
        _require(candidates, "P04 has no publicly surveyed nonreturn pair")
        candidates.sort(key=lambda item: (-item[0], item[1]))
        score, selected = candidates[0]
        _require(pair == selected,
                 "P04 alias pair is not the public top-ranked separated pair")
        facts = {"selection_rule": approved["route_sealing"]
                 ["p04_alias_selection_rule"],
                 "absolute_similarity_threshold": None,
                 "selected_public_cosine": score,
                 "nominal_separation_m":
                     _position_distance(poses[pair[0]], poses[pair[1]])}
    elif scenario == "P05":
        pair = note["same_place_observation_indices"]
        _require(pair == [0, n], "P05 must compare the route endpoints")
        distance = _position_distance(poses[0], poses[-1])
        yaw = _yaw_distance(poses[0]["yaw_deg"], poses[-1]["yaw_deg"])
        _require(distance <= 1e-9 and abs(yaw - 180.0) <= 1e-9,
                 "P05 must end at the same position with opposite heading")
        facts = {"position_error_m": distance, "yaw_difference_deg": yaw}
    elif scenario == "P06":
        junctions = note["junction_observation_indices"]
        endpoints = note["branch_endpoint_observation_indices"]
        _require(type(junctions) is list and len(junctions) == 2 and
                 type(endpoints) is list and len(endpoints) == 2 and
                 all(type(index) is int and 0 <= index <= n
                     for index in junctions + endpoints),
                 "P06 waypoint indices are invalid")
        _require(_position_distance(poses[junctions[0]], poses[junctions[1]])
                 <= 1e-9, "P06 route does not revisit one junction")
        junction = poses[junctions[0]]
        vectors = [(poses[index]["x_m"] - junction["x_m"],
                    poses[index]["z_m"] - junction["z_m"])
                   for index in endpoints]
        lengths = [math.hypot(*vector) for vector in vectors]
        _require(min(lengths) >= .5 and
                 vectors[0][0] * vectors[1][0] +
                 vectors[0][1] * vectors[1][1] <=
                 -0.99 * lengths[0] * lengths[1],
                 "P06 branch endpoints are not opposite arms of a T junction")
        facts = {"junction_revisited": True,
                 "branch_lengths_m": lengths,
                 "new_branch_relations_compile_to": "BIRTH_ADD_EDGE_not_RELINK"}
    elif scenario == "P07":
        ranges = note["loop_observation_ranges"]
        _require(type(ranges) is list and len(ranges) == 2 and
                 all(type(row) is list and len(row) == 2 for row in ranges) and
                 ranges[0][0] == 0 and ranges[0][1] == ranges[1][0] and
                 ranges[1][1] == n,
                 "P07 must register two contiguous loop ranges")
        center = poses[0]
        sets = []
        for start, end in ranges:
            _require(_position_distance(poses[start], center) <= 1e-9 and
                     _position_distance(poses[end], center) <= 1e-9,
                     "P07 loop does not return to the shared center")
            cells = {(round(row["x_m"] / .25), round(row["z_m"] / .25))
                     for row in poses[start:end + 1]
                     if _position_distance(row, center) > 1e-9}
            _require(cells, "P07 loop has no non-center cells")
            sets.append(cells)
        _require(sets[0].isdisjoint(sets[1]),
                 "P07 loops overlap outside the shared center")
        facts = {"shared_center_visit_count": 3,
                 "loop_noncenter_cell_counts": [len(row) for row in sets],
                 "noncenter_overlap_count": 0}
    else:
        rooms = note["room_anchor_observation_indices"]
        corridor = note["corridor_observation_indices"]
        _require(type(rooms) is list and len(rooms) == 2 and rooms[0] < rooms[1]
                 and type(corridor) is list and corridor and
                 all(index in observations for index in rooms + corridor),
                 "P08 public room/corridor evidence indices are invalid")
        _require(all(observations[index]["public_region_role"] == "room"
                     and observations[index]["visible_entity_region_refs"]
                     for index in rooms) and
                 all(observations[index]["public_region_role"] == "corridor"
                     for index in corridor) and
                 rooms[0] < min(corridor) <= max(corridor) < rooms[1] and
                 _position_distance(poses[rooms[0]], poses[rooms[1]]) >= 1.5,
                 "P08 lacks public room-corridor-room/entity evidence")
        facts = {"room_anchor_separation_m":
                     _position_distance(poses[rooms[0]], poses[rooms[1]]),
                 "room_entity_region_counts": [len(observations[index]
                    ["visible_entity_region_refs"]) for index in rooms]}

    value = {
        "schema_version": SCENARIO_RECEIPT_SCHEMA,
        "slot": route["slot"], "scenario_id": scenario,
        "route_plan_sha256": route["route_plan_sha256"],
        "public_route_evidence_sha256":
            evidence["public_route_evidence_sha256"],
        "annotations": note, "derived_facts": facts,
        "computed_from_registered_actions_and_pre_execution_public_evidence":
            True,
        "future_or_action_outcome_used": False,
        "private_reference_label_used": False,
    }
    value["scenario_receipt_sha256"] = _payload_sha(
        value, "scenario_receipt_sha256")
    return value


def validate_scenario_receipt(
    receipt: Mapping[str, Any], *, route_plan: Mapping[str, Any],
    initial_pose: Mapping[str, Any], public_route_evidence: Mapping[str, Any],
    contract: Mapping[str, Any], base_contract: Mapping[str, Any],
) -> dict[str, Any]:
    value = clone_json(dict(receipt))
    _exact(value, {"schema_version", "slot", "scenario_id",
                   "route_plan_sha256", "public_route_evidence_sha256",
                   "annotations", "derived_facts",
                   "computed_from_registered_actions_and_pre_execution_public_evidence",
                   "future_or_action_outcome_used", "private_reference_label_used",
                   "scenario_receipt_sha256"}, "D-211 scenario receipt")
    rebuilt = seal_scenario_receipt(
        route_plan=route_plan, initial_pose=initial_pose,
        public_route_evidence=public_route_evidence,
        annotations=value["annotations"], contract=contract,
        base_contract=base_contract)
    _require(value == rebuilt, "scenario receipt does not recompute")
    return value


def validate_route_execution_binding(
    binding: Mapping[str, Any], *, route_plan: Mapping[str, Any],
    reachable_scan: Mapping[str, Any],
    public_route_evidence: Mapping[str, Any],
    scenario_receipt: Mapping[str, Any], contract: Mapping[str, Any],
    base_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the private start pose and public evidence binding of one route."""

    approved = validate_d211_contract(contract, base_contract=base_contract)
    route = validate_route_plan(route_plan, base_contract)
    value = clone_json(dict(binding))
    _exact(value, {
        "schema_version", "slot", "house_slot", "scenario_id",
        "route_plan_sha256", "initial_pose", "reachable_scan_sha256",
        "public_rgbd_route_evidence_sha256", "step_reachability_sha256",
        "scenario_receipt_sha256",
        "all_planned_translation_endpoints_preverified_reachable",
        "constructed_from_pre_execution_public_evidence_only",
        "future_action_outcome_used", "private_reference_used",
        "execution_binding_sha256",
    }, "D-211 route execution binding")
    _require(value["schema_version"] == ROUTE_BINDING_SCHEMA and
             (value["slot"], value["house_slot"], value["scenario_id"],
              value["route_plan_sha256"]) ==
             (route["slot"], route["house_slot"], route["scenario_id"],
              route["route_plan_sha256"]),
             "route execution binding disagrees with its D-210 route")
    pose = _normalize_pose(value["initial_pose"], "D-211 initial pose")
    value["initial_pose"] = pose
    multiple = approved["route_sealing"]["initial_yaw_multiple_degrees"]
    _require(abs(pose["yaw_deg"] / multiple -
                 round(pose["yaw_deg"] / multiple)) <= 1e-9 and
             pose["horizon_deg"] == 0.0,
             "D-211 initial pose must use an axis-aligned yaw and zero horizon")
    scan = validate_reachable_scan(
        reachable_scan, contract=approved, base_contract=base_contract)
    evidence = validate_public_route_evidence(
        public_route_evidence, route_plan=route, base_contract=base_contract)
    _require(value["reachable_scan_sha256"] == scan["reachable_scan_sha256"] and
             value["public_rgbd_route_evidence_sha256"] ==
             evidence["public_route_evidence_sha256"],
             "route binding evidence digests do not match supplied records")
    step_receipt = seal_step_reachability(
        route_plan=route, initial_pose=pose, reachable_scan=scan,
        contract=approved, base_contract=base_contract)
    semantic = validate_scenario_receipt(
        scenario_receipt, route_plan=route, initial_pose=pose,
        public_route_evidence=evidence, contract=approved,
        base_contract=base_contract)
    _require(value["step_reachability_sha256"] ==
             step_receipt["step_reachability_sha256"] and
             value["scenario_receipt_sha256"] ==
             semantic["scenario_receipt_sha256"],
             "route binding recomputed receipt digests disagree")
    _require(value["all_planned_translation_endpoints_preverified_reachable"]
             is True and
             value["constructed_from_pre_execution_public_evidence_only"] is True and
             value["future_action_outcome_used"] is False and
             value["private_reference_used"] is False,
             "D-211 route evidence boundary changed")
    _require(value["execution_binding_sha256"] ==
             _payload_sha(value, "execution_binding_sha256"),
             "D-211 route execution binding digest mismatch")
    return value


def seal_route_execution_binding(
    *, route_plan: Mapping[str, Any], initial_pose: Mapping[str, Any],
    reachable_scan: Mapping[str, Any],
    public_route_evidence: Mapping[str, Any],
    scenario_receipt: Mapping[str, Any], contract: Mapping[str, Any],
    base_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Seal one route's private start pose after public route construction."""

    route = validate_route_plan(route_plan, base_contract)
    approved = validate_d211_contract(contract, base_contract=base_contract)
    pose = _normalize_pose(initial_pose, "D-211 initial pose")
    scan = validate_reachable_scan(
        reachable_scan, contract=approved, base_contract=base_contract)
    evidence = validate_public_route_evidence(
        public_route_evidence, route_plan=route, base_contract=base_contract)
    step = seal_step_reachability(
        route_plan=route, initial_pose=pose, reachable_scan=scan,
        contract=approved, base_contract=base_contract)
    semantic = validate_scenario_receipt(
        scenario_receipt, route_plan=route, initial_pose=pose,
        public_route_evidence=evidence, contract=approved,
        base_contract=base_contract)
    value = {
        "schema_version": ROUTE_BINDING_SCHEMA,
        "slot": route["slot"], "house_slot": route["house_slot"],
        "scenario_id": route["scenario_id"],
        "route_plan_sha256": route["route_plan_sha256"],
        "initial_pose": pose,
        "reachable_scan_sha256": scan["reachable_scan_sha256"],
        "public_rgbd_route_evidence_sha256":
            evidence["public_route_evidence_sha256"],
        "step_reachability_sha256": step["step_reachability_sha256"],
        "scenario_receipt_sha256": semantic["scenario_receipt_sha256"],
        "all_planned_translation_endpoints_preverified_reachable": True,
        "constructed_from_pre_execution_public_evidence_only": True,
        "future_action_outcome_used": False,
        "private_reference_used": False,
    }
    value["execution_binding_sha256"] = _payload_sha(
        value, "execution_binding_sha256")
    return validate_route_execution_binding(
        value, route_plan=route, reachable_scan=scan,
        public_route_evidence=evidence, scenario_receipt=semantic,
        contract=approved, base_contract=base_contract)


def build_sealed_route_batch(
    *, rows: Sequence[Mapping[str, Any]], contract: Mapping[str, Any],
    base_contract: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Create D-210 public/private manifests plus twelve private bindings."""

    approved = validate_d211_contract(contract, base_contract=base_contract)
    _require(type(rows) in {list, tuple} and len(rows) == 12,
             "D-211 route bundle must contain twelve rows")
    routes: list[dict[str, Any]] = []
    bindings: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        _exact(row, {"route_plan", "reachable_scan",
                     "public_route_evidence", "scenario_receipt",
                     "execution_binding"},
               f"D-211 route row {index}")
        route = validate_route_plan(row["route_plan"], base_contract)
        binding = validate_route_execution_binding(
            row["execution_binding"], route_plan=route,
            reachable_scan=row["reachable_scan"],
            public_route_evidence=row["public_route_evidence"],
            scenario_receipt=row["scenario_receipt"], contract=approved,
            base_contract=base_contract)
        routes.append(route)
        bindings.append(binding)
    _require([route["slot"] for route in routes] == list(range(12)),
             "D-211 route rows must be ordered unique slots 0 through 11")
    public, private = build_p0_manifests(
        source_houses=approved["source_binding"]["houses"],
        route_plans=routes, contract=base_contract)
    binding_manifest = {
        "schema_version": SEALED_BINDINGS_SCHEMA,
        "public_manifest_sha256": public["manifest_sha256"],
        "private_manifest_sha256": private["manifest_sha256"],
        "binding_count": 12,
        "bindings": bindings,
        "route_replacement_after_smoke_outcome_allowed": False,
    }
    binding_manifest["manifest_sha256"] = _payload_sha(
        binding_manifest, "manifest_sha256")
    return public, private, binding_manifest


def assert_single_slot_smoke_authorized(
    contract: Mapping[str, Any], *, base_contract: Mapping[str, Any],
    reviewed_implementation_commit: str,
) -> dict[str, Any]:
    """Open only slot 0 after this implementation has a reviewed commit."""

    approved = validate_d211_contract(contract, base_contract=base_contract)
    _require(approved["status"] ==
             "frozen_executable_seal_and_single_slot_smoke" and
             approved["authorization"]["single_slot_raw_smoke_authorized"]
             is True and
             approved["authorization"]["twelve_slot_raw_generation_authorized"]
             is False,
             "D-211 single-slot raw smoke is not executable")
    _require(reviewed_implementation_commit ==
             approved["expected_reviewed_implementation_commit"],
             "D-212 reviewed implementation commit mismatch")
    return approved
