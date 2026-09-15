"""Pure, non-executable plan for the fixed two-house real-action probe."""

from __future__ import annotations

from collections import deque
import hashlib
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
PROPOSAL_PATH = ROOT / "configs/vsmt/vm04_relink_interaction_probe_proposal_v1.json"
ENDPOINT_REPORT = ROOT / "results/vsmt_vm04_relink_endpoint_two_house_probe_v1.json"
GRID_SIZE_M = 0.25  # AI2-THOR initialization and frozen v2 reachable grid.


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_proposal(value):
    """No action probe runs while the stance, receptacle and force are open."""
    require(value["version"] == "vsmt-vm04-relink-interaction-probe-proposal-v1" and
            value["status"] in ("requires_action_plan_review_not_executable",
                                "frozen_fixed_two_house_probe_only") and
            value["fixed_source_house_ids"] == ["train:004270", "train:008243"] and
            value["fixed_family_ids"] == ["audit-family:00", "audit-family:01"] and
            value["original_relink_slots_by_family"] == [[4, 11], [6, 12]] and
            value["source_v1_action_probe_receipt_sha256"] ==
                "b328caa335857a8e85fe26ac994c069115ba5baa218c2f9a4bee41a87b424333" and
            value["source_v2_scan_receipt_sha256"] ==
                "044fd705e998b1dea9bc62bdd730ff2fc583f9880901131f8927aefb10bb9fd5" and
            value["source_v3_target_contract_sha256"] ==
                "7d11335be9a8b85cc26dd1c2058c36f71c93d9db0cef4f33fdda2ec7cfa6dbac" and
            value["source_endpoint_report_sha256"] == sha256(ENDPOINT_REPORT) and
            value["source_provenance_policy"] ==
                "verify_original_private_slot_scan_pose_house_and_receipts_before_each_branch" and
            value["frozen_scene_policy"] ==
                "original_house_pose_slot_target_and_pre_intervention_camera_prefix_no_reselection" and
            value["first_post_initial_pose_agent_motion_policy"] ==
                "real_rotate_and_move_actions_only_no_navigation_teleport" and
            value["route_geometry_source"] ==
                "l1_anonymous_visible_entity_depth_geometry_plus_public_reachable_grid" and
            value["route_geometry_role"] ==
                "approach_stance_only_never_true_asset_position_or_relink_destination" and
            value["route_selection_policy"] ==
                "single_deterministic_cardinal_grid_route_before_interaction_outcomes_no_fallback" and
            value["target_capability_policy"] ==
                "pickupable_only_uses_pickup_put_moveable_only_uses_push_and_pull_ambiguous_dual_capability_fails" and
            value["pickupable_actions"] == ["PickupObject", "PutObject"] and
            value["moveable_actions"] == ["PushObject", "PullObject"] and
            value["push_pull_branch_policy"] ==
                "independent_fresh_scene_per_direction_report_both_never_pick_winner" and
            all(value[key] is False for key in (
                "all_interaction_actions_force_action", "pickup_force_action",
                "put_force_action", "push_force_action", "pull_force_action",
                "generation_authorized", "training_authorized",
                "memory_history_checked")) and
            value["physical_displacement_reporting_policy"] ==
                "report_xyz_m_and_settled_state_no_semantic_positive_threshold" and
            value["robot_path_claim_policy"] ==
                "only_actual_successful_agent_motions_to_interaction_stance" and
            value["pickup_put_claim_policy"] ==
                "verify_isPickedUp_transition_and_final_parent_receptacle_no_continuous_object_path_or_memory_label" and
            value["push_pull_claim_policy"] ==
                "verify_action_return_and_actual_asset_motion_or_no_motion_without_memory_label" and
            value["private_error_and_object_id_policy"] ==
                "private_only_public_family_modality_stage_counts_and_digests" and
            value["failure_policy"] ==
                "retain_original_fixed_branch_no_target_route_receptacle_direction_house_or_slot_substitution" and
            value["resource_policy"] ==
                "max_safe_workers_from_fresh_cpu_gpu_cgroup_io_and_sampled_single_controller_demand" and
            value["semantic_positive_labels_issued"] == 0,
            "RELINK interaction design scope or input boundary changed")
    for key in ("source_v1_action_probe_receipt_sha256",
                "source_v2_scan_receipt_sha256", "source_v3_target_contract_sha256",
                "source_endpoint_report_sha256"):
        require(re.fullmatch(r"[0-9a-f]{64}", value[key]) is not None,
                "invalid RELINK interaction source digest")
    open_fields = ("pickup_manual_interact", "put_place_stationary",
                   "receptacle_target_source",
                   "public_typed_receptacle_reader_verified_sha256",
                   "pinned_simulator_putobject_api_smoke_receipt_sha256",
                   "trusted_private_interaction_runner_sha256",
                   "push_pull_force_ladder_newtons",
                   "agent_start_grid_snap_tolerance_m",
                   "agent_step_real_pose_tolerance_m")
    if value["status"] == "requires_action_plan_review_not_executable":
        require(all(value[key] is None for key in open_fields) and
                value["probe_authorized"] is False,
                "unreviewed interaction probe must remain closed")
    else:
        require(type(value["pickup_manual_interact"]) is bool and
                type(value["put_place_stationary"]) is bool and
                value["receptacle_target_source"] ==
                    "public_typed_receptacle_region_frozen_before_private_action_mapping" and
                re.fullmatch(r"[0-9a-f]{64}", value[
                    "public_typed_receptacle_reader_verified_sha256"]) is not None and
                re.fullmatch(r"[0-9a-f]{64}", value[
                    "pinned_simulator_putobject_api_smoke_receipt_sha256"]) is not None and
                re.fullmatch(r"[0-9a-f]{64}", value[
                    "trusted_private_interaction_runner_sha256"]) is not None and
                type(value["push_pull_force_ladder_newtons"]) is list and
                len(value["push_pull_force_ladder_newtons"]) >= 2 and
                all(type(force) is float and math.isfinite(force) and force > 0
                    for force in value["push_pull_force_ladder_newtons"]) and
                value["push_pull_force_ladder_newtons"] == sorted(set(
                    value["push_pull_force_ladder_newtons"])) and
                value["push_pull_force_ladder_newtons"] ==
                    [20.0, 80.0, 160.0] and
                all(type(value[key]) is float and
                    math.isfinite(value[key]) and value[key] > 0
                    for key in open_fields[7:]) and
                value["probe_authorized"] is True,
                "executable interaction branch still lacks reviewed action rule")
    return value


def load_proposal():
    return validate_proposal(json.loads(PROPOSAL_PATH.read_text(encoding="utf-8")))


def capability_branches(metadata_object):
    """Classify the already frozen target; never choose a replacement asset."""
    pickupable = metadata_object.get("pickupable") is True
    moveable = metadata_object.get("moveable") is True
    require(pickupable != moveable,
            "target must have exactly one real-action capability in this probe")
    return ("pickup_put",) if pickupable else ("push", "pull")


def _xyz(position, name):
    require(type(position) is dict and
            all(type(position.get(axis)) in (int, float) and
                math.isfinite(float(position[axis]))
                for axis in ("x", "y", "z")),
            "%s must be finite xyz" % name)
    return {axis: float(position[axis]) for axis in ("x", "y", "z")}


def _centroid_xyz(value):
    require(type(value) in (list, tuple) and len(value) == 3 and
            all(type(v) in (int, float) and math.isfinite(float(v))
                for v in value),
            "anonymous visible region centroid must be finite xyz")
    return tuple(float(v) for v in value)


def single_public_approach_route(start_position, anonymous_visible_centroid_m,
                                 reachable_positions,
                                 *, start_snap_tolerance_m):
    """Choose one cardinal route using visible geometry and reachable grid.

    The centroid is an approach hint, not the asset's real simulator position.
    This function has no objectId, metadata asset pose, action result, or retry.
    """
    start = _xyz(start_position, "public agent start")
    target_x, _, target_z = _centroid_xyz(anonymous_visible_centroid_m)
    require(type(start_snap_tolerance_m) is float and
            math.isfinite(start_snap_tolerance_m) and
            start_snap_tolerance_m > 0 and
            type(reachable_positions) is list and reachable_positions,
            "reviewed snap tolerance and public reachable positions required")
    positions = sorted((_xyz(row, "public reachable position")
                        for row in reachable_positions),
                       key=lambda row: (row["x"], row["y"], row["z"]))
    origin = positions[0]
    nodes = {}
    for row in positions:
        require(abs(row["y"] - origin["y"]) <= 0.01,
                "multilevel reachable grid needs a separately reviewed route")
        key = (round((row["x"] - origin["x"]) / GRID_SIZE_M),
               round((row["z"] - origin["z"]) / GRID_SIZE_M))
        require(key not in nodes and
                abs(row["x"] - (origin["x"] + key[0] * GRID_SIZE_M)) <= 0.01 and
                abs(row["z"] - (origin["z"] + key[1] * GRID_SIZE_M)) <= 0.01,
                "public reachable points are not a unique 0.25 m grid")
        nodes[key] = row
    start_key = min(nodes, key=lambda key: (
        math.hypot(nodes[key]["x"] - start["x"],
                   nodes[key]["z"] - start["z"]),
        nodes[key]["x"], nodes[key]["z"]))
    require(math.hypot(nodes[start_key]["x"] - start["x"],
                       nodes[start_key]["z"] - start["z"]) <=
            start_snap_tolerance_m,
            "original public start is off the frozen reachable grid")
    goal_key = min(nodes, key=lambda key: (
        math.hypot(nodes[key]["x"] - target_x,
                   nodes[key]["z"] - target_z),
        nodes[key]["x"], nodes[key]["z"]))
    queue = deque([start_key])
    previous = {start_key: None}
    while queue and goal_key not in previous:
        current = queue.popleft()
        for step in ((0, 1), (1, 0), (0, -1), (-1, 0)):
            neighbor = current[0] + step[0], current[1] + step[1]
            if neighbor in nodes and neighbor not in previous:
                previous[neighbor] = current
                queue.append(neighbor)
    require(goal_key in previous,
            "single predeclared cardinal public route is unavailable")
    keys = []
    current = goal_key
    while current is not None:
        keys.append(current)
        current = previous[current]
    path = [nodes[key] for key in reversed(keys)]
    return {"path_positions": path,
            "approach_centroid_m": list(_centroid_xyz(
                anonymous_visible_centroid_m)),
            "route_source": "public_grid_and_l1_anonymous_visible_geometry",
            "true_asset_position_used": False,
            "target_instance_id_used": False,
            "agent_motion_executed": False,
            "fallback_routes_considered": 0}


def agent_actions_for_route(path_positions, current_yaw_degrees,
                            anonymous_visible_centroid_m):
    """Turn and move along the sealed route; do not teleport the agent."""
    require(type(path_positions) is list and path_positions and
            type(current_yaw_degrees) in (int, float) and
            math.isfinite(float(current_yaw_degrees)),
            "public route and real current yaw required")
    path = [_xyz(row, "public path node") for row in path_positions]
    target_x, _, target_z = _centroid_xyz(anonymous_visible_centroid_m)
    actions = []
    yaw = float(current_yaw_degrees) % 360

    def turn_to(destination):
        nonlocal yaw
        right = (destination - yaw) % 360
        left = (yaw - destination) % 360
        if min(right, left) > 0.000001:
            if right <= left:
                actions.append({"action": "RotateRight", "degrees": right})
            else:
                actions.append({"action": "RotateLeft", "degrees": left})
        yaw = destination % 360

    for before, after in zip(path, path[1:]):
        dx = after["x"] - before["x"]
        dz = after["z"] - before["z"]
        require(abs(math.hypot(dx, dz) - GRID_SIZE_M) <= 0.01 and
                (abs(dx) <= 0.01 or abs(dz) <= 0.01),
                "agent route contains a non-cardinal grid edge")
        turn_to(math.degrees(math.atan2(dx, dz)) % 360)
        actions.append({"action": "MoveAhead",
                        "moveMagnitude": GRID_SIZE_M})
    dx = target_x - path[-1]["x"]
    dz = target_z - path[-1]["z"]
    if math.hypot(dx, dz) > 0.000001:
        turn_to(math.degrees(math.atan2(dx, dz)) % 360)
    return actions
