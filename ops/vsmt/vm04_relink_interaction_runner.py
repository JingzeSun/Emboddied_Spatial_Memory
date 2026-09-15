"""Reviewable fixed-slot interaction core. No simulator stage is opened here."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import vm04_relink_interaction_design as design

ROOT = Path(__file__).resolve().parents[2]
FORCE_PATH = ROOT / "configs/vsmt/vm04_relink_force_prereg_v1.json"
SMOKE_PATH = ROOT / "configs/vsmt/vm04_relink_put_api_smoke_v1.json"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def force_prereg():
    value = json.loads(FORCE_PATH.read_text(encoding="utf-8"))
    require(value["version"] == "vsmt-vm04-relink-force-prereg-v1" and
            value["status"] == "frozen_for_runner_review_no_action_execution" and
            value["fixed_slots_by_family"] == [[4, 11], [6, 12]] and
            value["force_unit"] == "newton" and
            value["eligible_modality"] == "moveable_only_push_and_pull" and
            value["force_ladder_newtons"] == [20.0, 80.0, 160.0] and
            value["expected_moveable_targets"] == 3 and
            value["expected_force_branches"] == 18 and
            value["expected_pickup_put_branches"] == 1 and
            value["zero_displacement_in_denominator"] is True and
            all(value[key] is False for key in
                ("probe_authorized", "generation_authorized", "training_authorized")),
            "force pre-registration changed")
    return value


def pinned_api_spec():
    value = json.loads(SMOKE_PATH.read_text(encoding="utf-8"))
    require(value["version"] == "vsmt-vm04-relink-put-api-smoke-v1" and
            value["status"] == "pinned_spec_real_smoke_pending" and
            value["simulator_python"] ==
                "/root/autodl-tmp/vsmt-envs/simulator-py39/bin/python" and
            value["ai2thor_version"] == "5.0.0" and
            value["cloud_rendering_build_commit"] ==
                "f0825767cd50d69f666c7f282e54abfe58f1e917" and
            value["cloud_rendering_zip_sha256"] ==
                "1fd5f998644a6dd522a4cf6604c05360a75a5c27f450a7486c20e52dc2b67bb9" and
            value["pickup_manual_interact"] is False and
            value["put_place_stationary"] is True and
            value["force_action"] is False and
            value["real_smoke_receipt_sha256"] is None and
            value["interaction_probe_authorized"] is False,
            "PutObject API smoke specification changed")
    return value


def public_receptacle_choice(regions):
    """Require public type evidence; generic L1 surfaces are insufficient."""
    require(type(regions) is list, "public regions must be a list")
    candidates = []
    for region in regions:
        require(type(region) is dict, "public region must be a record")
        require(not any(key in region for key in
            ("objectId", "instance_id", "private_id", "reference_transaction",
             "future_state", "ground_truth", "metadata_receptacle")),
            "private identity or future leaked into public receptacle evidence")
        if region.get("semantic_type") != "receptacle":
            continue
        require(region.get("evidence_source") == "public_current_rgb_depth" and
                type(region.get("region_id")) is str and
                region["region_id"] and
                type(region.get("mask_sha256")) is str and
                len(region["mask_sha256"]) == 64 and
                type(region.get("reliability")) in (int, float) and
                math.isfinite(float(region["reliability"])) and
                0.0 <= region["reliability"] <= 1.0,
                "receptacle lacks public typed evidence")
        # Selection uses only public evidence, with an explicit stable tie break.
        candidates.append(region)
    require(candidates, "no public typed receptacle; do not use private metadata")
    chosen = min(candidates, key=lambda row: (-float(row["reliability"]),
                                              row["region_id"], row["mask_sha256"]))
    return {key: chosen[key] for key in
            ("region_id", "semantic_type", "evidence_source", "mask_sha256",
             "reliability")}


def freeze_public_plan(start, yaw, visible_centroid, reachable, receptacle_regions,
                       *, snap_tolerance_m):
    """Seal route and receptacle before target ID, private mapping or outcomes."""
    route = design.single_public_approach_route(
        start, visible_centroid, reachable,
        start_snap_tolerance_m=snap_tolerance_m)
    actions = design.agent_actions_for_route(
        route["path_positions"], yaw, route["approach_centroid_m"])
    receptacle = public_receptacle_choice(receptacle_regions)
    plan = {"schema_version": "vsmt-vm04-public-interaction-plan-v1",
            "route": route, "agent_actions": actions,
            "receptacle": receptacle, "sealed_before_private_mapping": True,
            "private_id_used": False, "interaction_outcome_used": False}
    return {"plan": plan, "plan_sha256": digest(plan)}


def private_receptacle_mapping(sealed, mapping):
    """Trusted execution adapter must map the sealed region, never re-rank it."""
    require(digest(sealed["plan"]) == sealed["plan_sha256"] and
            sealed["plan"]["sealed_before_private_mapping"] is True,
            "public plan was not sealed")
    require(type(mapping) is dict and
            set(mapping) == {sealed["plan"]["receptacle"]["region_id"]} and
            type(next(iter(mapping.values()))) is str and
            next(iter(mapping.values())),
            "private mapping must contain exactly the preselected public region")
    return next(iter(mapping.values()))


def map_sealed_public_mask_to_private_id(sealed, public_mask_bytes,
                                         live_instance_masks):
    """Trusted execution-only association by mask overlap, never asset type."""
    require(digest(sealed["plan"]) == sealed["plan_sha256"] and
            type(public_mask_bytes) is bytes and public_mask_bytes and
            hashlib.sha256(public_mask_bytes).hexdigest() ==
                sealed["plan"]["receptacle"]["mask_sha256"] and
            type(live_instance_masks) is dict and live_instance_masks,
            "sealed public mask or live private mask mapping absent")
    require(set(public_mask_bytes) <= {0, 1}, "public mask must be binary")
    scores = []
    for object_id, private_mask in live_instance_masks.items():
        require(type(object_id) is str and object_id and
                type(private_mask) is bytes and
                len(private_mask) == len(public_mask_bytes) and
                set(private_mask) <= {0, 1},
                "private instance mask shape or encoding differs")
        overlap = sum(a == 1 and b == 1 for a, b in
                      zip(public_mask_bytes, private_mask))
        scores.append((overlap, object_id))
    best = max(score for score, _ in scores)
    winners = [object_id for score, object_id in scores if score == best]
    require(best > 0 and len(winners) == 1,
            "no unique visible instance overlap for sealed public receptacle")
    return {sealed["plan"]["receptacle"]["region_id"]: winners[0]}


def _mask_bytes(value):
    if type(value) is bytes:
        return value
    # AI2-THOR instance_masks entries are Boolean arrays on the private side.
    require(hasattr(value, "astype") and hasattr(value, "tobytes"),
            "private instance mask must be binary array or bytes")
    return value.astype("uint8").tobytes()


def _object(event, object_id):
    rows = [row for row in event.metadata.get("objects", [])
            if row.get("objectId") == object_id]
    require(len(rows) == 1, "fixed private target missing or duplicated")
    row = rows[0]
    return {"object_id": object_id, "position": design._xyz(row["position"],
            "actual private object pose"), "is_moving": row.get("isMoving"),
            "is_picked_up": row.get("isPickedUp"),
            "parent_receptacles": row.get("parentReceptacles")}


def _agent(event):
    row = event.metadata.get("agent")
    require(type(row) is dict and type(row.get("position")) is dict and
            type(row.get("rotation")) is dict and
            type(row["rotation"].get("y")) in (int, float),
            "actual agent pose absent")
    return {"position": design._xyz(row["position"], "actual agent pose"),
            "yaw": float(row["rotation"]["y"])}


def _diagnostic(event):
    return {"last_action_success": event.metadata.get("lastActionSuccess"),
            "error_message": event.metadata.get("errorMessage"),
            "error_code": event.metadata.get("errorCode")}


def execute_fixed_branch(controller, sealed, *, target_id, receptacle_mapping,
                         modality, force_newtons, agent_pose_tolerance_m,
                         public_receptacle_mask_bytes=None):
    """One fresh controller supplied by parent; record every attempted action."""
    require(design.load_proposal()["probe_authorized"] is True,
            "real interaction probe is closed until reviewed API and runner receipts")
    force_prereg()
    spec = pinned_api_spec()
    require(digest(sealed["plan"]) == sealed["plan_sha256"] and
            type(target_id) is str and target_id and
            type(agent_pose_tolerance_m) is float and
            math.isfinite(agent_pose_tolerance_m) and agent_pose_tolerance_m > 0 and
            modality in ("pickup_put", "push", "pull"),
            "unreviewed or unsealed interaction branch")
    if modality == "pickup_put":
        require(force_newtons is None, "pickup branch has no force ladder")
        require(type(public_receptacle_mask_bytes) is bytes and
                hasattr(controller.last_event, "instance_masks"),
                "public mask and current private segmentation required for mapping")
        verified_mapping = map_sealed_public_mask_to_private_id(
            sealed, public_receptacle_mask_bytes,
            {object_id: _mask_bytes(mask) for object_id, mask in
             controller.last_event.instance_masks.items()})
        require(receptacle_mapping == verified_mapping,
                "private mapping differs from sealed public mask overlap")
        receptacle_id = private_receptacle_mapping(sealed, receptacle_mapping)
    else:
        require(force_newtons in force_prereg()["force_ladder_newtons"] and
                receptacle_mapping is None,
                "push/pull must use every pre-registered force independently")
        receptacle_id = None
    record = {"schema_version": "vsmt-vm04-private-interaction-branch-v1",
              "public_plan_sha256": sealed["plan_sha256"],
              "target_object_id": target_id,
              "mapped_receptacle_object_id": receptacle_id,
              "modality": modality, "force_newtons": force_newtons,
              "actions": [], "status": "not_started",
              "memory_history_checked": False,
              "semantic_positive_label_issued": False}
    try:
        event = controller.last_event
        before = _object(event, target_id)
        agent_start = _agent(event)
        expected_start = sealed["plan"]["route"]["path_positions"][0]
        start_error = math.sqrt(sum((agent_start["position"][axis] -
                                     expected_start[axis]) ** 2
                                    for axis in ("x", "y", "z")))
        if start_error > agent_pose_tolerance_m:
            record.update(status="navigation_real_start_pose_mismatch",
                          actual_agent_start=agent_start,
                          start_position_error_m=start_error)
            return record
        target = next(row for row in event.metadata["objects"]
                      if row["objectId"] == target_id)
        require(design.capability_branches(target) ==
                (("pickup_put",) if modality == "pickup_put" else ("push", "pull")),
                "branch contradicts frozen target capability")
        if receptacle_id is not None:
            recipient = next((row for row in event.metadata["objects"]
                              if row.get("objectId") == receptacle_id), None)
            require(recipient is not None and recipient.get("receptacle") is True,
                    "preselected public receptacle has no valid private execution target")
        record["before"] = before
        for index, action in enumerate(sealed["plan"]["agent_actions"]):
            require(action["action"] in ("RotateRight", "RotateLeft", "MoveAhead"),
                    "navigation teleport or unreviewed action")
            event = controller.step(**action)
            actual = _agent(event)
            diagnostic = _diagnostic(event)
            record["actions"].append({"stage": "navigation", "index": index,
                                      "request": action, "actual_agent": actual,
                                      "diagnostic": diagnostic})
            if diagnostic["last_action_success"] is not True:
                record["status"] = "navigation_action_rejected"
                return record
            if action["action"] == "MoveAhead":
                path_index = sum(row["request"]["action"] == "MoveAhead"
                                 for row in record["actions"]) 
                expected = sealed["plan"]["route"]["path_positions"][path_index]
                distance = math.sqrt(sum((actual["position"][axis] - expected[axis]) ** 2
                                         for axis in ("x", "y", "z")))
                if distance > agent_pose_tolerance_m:
                    record["status"] = "navigation_real_pose_mismatch"
                    return record
        if modality == "pickup_put":
            requests = ({"action": "PickupObject", "objectId": target_id,
                         "forceAction": False,
                         "manualInteract": spec["pickup_manual_interact"]},
                        {"action": "PutObject", "objectId": receptacle_id,
                         "forceAction": False,
                         "placeStationary": spec["put_place_stationary"]})
        else:
            requests = ({"action": "PushObject" if modality == "push" else
                         "PullObject", "objectId": target_id,
                         "moveMagnitude": force_newtons, "forceAction": False},)
        for request in requests:
            event = controller.step(**request)
            diagnostic = _diagnostic(event)
            state = _object(event, target_id)
            record["actions"].append({"stage": "interaction", "request": request,
                                      "target_after": state,
                                      "diagnostic": diagnostic})
            if diagnostic["last_action_success"] is not True:
                record["status"] = "interaction_action_rejected"
                return record
            if (request["action"] == "PickupObject" and
                    state["is_picked_up"] is not True):
                record["status"] = "pickup_state_mismatch"
                return record
        final = _object(event, target_id)
        record["after"] = final
        record["displacement_m"] = {axis:
            final["position"][axis] - before["position"][axis]
            for axis in ("x", "y", "z")}
        if (modality == "pickup_put" and
                (final["is_picked_up"] is not False or
                 receptacle_id not in (final["parent_receptacles"] or []))):
            record["status"] = "put_parent_or_pickup_state_mismatch"
        else:
            record["status"] = "actions_recorded_no_memory_verdict"
        return record
    except Exception as error:
        record.update(status="branch_exception_preserved",
                      error_type=type(error).__name__, error=str(error))
        return record


def putobject_api_smoke(controller, held_id, receptacle_id):
    """Separate pinned-build smoke: keep failures and observed parent mapping."""
    spec = pinned_api_spec()
    require(type(held_id) is str and held_id and
            type(receptacle_id) is str and receptacle_id and
            held_id != receptacle_id, "two distinct smoke assets required")
    record = {"schema_version": "vsmt-vm04-private-put-api-smoke-v1",
              "spec_sha256": hashlib.sha256(SMOKE_PATH.read_bytes()).hexdigest(),
              "held_object_id": held_id, "receptacle_object_id": receptacle_id,
              "actions": [], "status": "not_started"}
    try:
        requests = ({"action": "PickupObject", "objectId": held_id,
                     "forceAction": False,
                     "manualInteract": spec["pickup_manual_interact"]},
                    {"action": "PutObject", "objectId": receptacle_id,
                     "forceAction": False,
                     "placeStationary": spec["put_place_stationary"]})
        for request in requests:
            event = controller.step(**request)
            record["actions"].append({"request": request,
                                      "diagnostic": _diagnostic(event),
                                      "held_state": _object(event, held_id)})
            if event.metadata.get("lastActionSuccess") is not True:
                record["status"] = "smoke_action_rejected_inconclusive"
                return record
        held = record["actions"][-1]["held_state"]
        record["status"] = ("target_receptacle_parameter_confirmed" if
            held["is_picked_up"] is False and
            receptacle_id in (held["parent_receptacles"] or []) else
            "put_returned_success_without_target_parent_inconclusive")
        return record
    except Exception as error:
        record.update(status="smoke_exception_inconclusive",
                      error_type=type(error).__name__, error=str(error))
        return record
