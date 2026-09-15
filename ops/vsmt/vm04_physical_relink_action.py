"""Trusted server-side endpoint gate for physical VM04 RELINK diagnostics."""

from __future__ import annotations

import math


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def validate_contract(value):
    require(value["version"] == "vsmt-vm04-physical-relink-endpoint-contract-v1" and
            value["status"] == "frozen_fixed_two_house_endpoint_probe_only" and
            value["fixed_two_house_endpoint_probe_authorized"] is True and
            value["generation_authorized"] is False and
            value["training_authorized"] is False and
            value["fixed_house_ids"] == ["train:004270", "train:008243"] and
            value["fixed_family_ids"] == ["audit-family:00", "audit-family:01"] and
            value["fixed_relink_slots_per_family"] == 2 and
            value["physical_target_requires_moveable_or_pickupable"] is True and
            value["registered_request_policy"] ==
            "same_frozen_source_position_plus_0_5_x_no_target_or_destination_reselection" and
            value["simulator_action"] == "TeleportObject" and
            value["force_action"] is False and
            type(value["terminal_real_position_tolerance_m"]) is float and
            value["terminal_real_position_tolerance_m"] == 0.005 and
            value["rejection_policy"] ==
            "fail_original_fixed_slot_no_retry_no_substitute" and
            value["success_claim"] ==
            "simulator_nonforced_endpoint_accepted_and_real_poststate_matches_only" and
            value["robot_manipulation_path_reachability_checked"] is False and
            value["memory_history_checked"] is False and
            value["semantic_positive_label_issued"] is False and
            value["private_error_message_policy"] ==
            "retain_original_text_private_export_only_anonymous_reason_category",
            "physical RELINK endpoint scope/gate changed")
    return value


def nonforced_original_request(registered_action, initial_object, contract):
    """Only change forceAction; never choose an easier destination or asset."""
    validate_contract(contract)
    require(type(registered_action) is dict and
            registered_action.get("action") == "TeleportObject" and
            registered_action.get("forceAction") is True and
            type(registered_action.get("objectId")) is str and
            type(registered_action.get("position")) is dict and
            type(initial_object) is dict and
            (initial_object.get("moveable") is True or
             initial_object.get("pickupable") is True),
            "RELINK needs original registered movable authored asset")
    before = initial_object.get("position")
    requested = registered_action["position"]
    require(type(before) is dict and
            all(type(before.get(axis)) in (int, float) and
                type(requested.get(axis)) in (int, float) and
                math.isfinite(float(before[axis])) and
                math.isfinite(float(requested[axis]))
                for axis in ("x", "y", "z")) and
            abs(float(requested["x"]) - (float(before["x"]) + 0.5)) < 0.000001 and
            abs(float(requested["y"]) - float(before["y"])) < 0.000001 and
            abs(float(requested["z"]) - float(before["z"])) < 0.000001,
            "RELINK request differs from frozen x+0.5 endpoint")
    return {**registered_action, "forceAction": False}


def object_row(event, object_id):
    return next((row for row in event.metadata.get("objects", [])
                 if row.get("objectId") == object_id), None)


def endpoint_verdict(registered_action, immediate_event, terminal_event, contract):
    """Separate simulator acceptance, real endpoint, motion, and memory claim."""
    validate_contract(contract)
    metadata = immediate_event.metadata
    accepted = metadata.get("lastActionSuccess") is True
    error = metadata.get("errorMessage") or ""
    collision_reported = (not accepted and " is colliding with " in error and
                          " after teleport." in error)
    result = {"simulator_nonforced_action_accepted": accepted,
              "simulator_final_pose_collision_reported": collision_reported,
              "private_error_message": error,
              "robot_manipulation_path_reachability_checked": False,
              "memory_history_checked": False,
              "semantic_positive_label_issued": False,
              "status": "not_evaluated"}
    if not accepted:
        result["status"] = ("simulator_endpoint_collision_rejected"
                            if collision_reported else
                            "simulator_endpoint_other_rejected")
        return result
    if terminal_event is None:
        result["status"] = "terminal_event_missing"
        return result
    object_id = registered_action["objectId"]
    immediate = object_row(immediate_event, object_id)
    terminal = object_row(terminal_event, object_id)
    requested = registered_action["position"]
    result["immediate_real_position"] = (
        immediate.get("position") if immediate else None)
    result["terminal_real_position"] = (
        terminal.get("position") if terminal else None)
    result["terminal_is_moving"] = (
        terminal.get("isMoving") if terminal else None)
    positions = (result["immediate_real_position"],
                 result["terminal_real_position"])
    tolerance = contract["terminal_real_position_tolerance_m"]
    valid = all(type(position) is dict and
                all(type(position.get(axis)) in (int, float) and
                    math.isfinite(float(position[axis])) and
                    abs(float(position[axis]) - float(requested[axis])) <= tolerance
                    for axis in ("x", "y", "z"))
                for position in positions)
    if not valid:
        result["status"] = "simulator_endpoint_poststate_mismatch"
    elif result["terminal_is_moving"] is True:
        result["status"] = "simulator_endpoint_unsettled"
    else:
        result["status"] = "simulator_nonforced_endpoint_accepted_and_real_poststate_matches"
    return result
