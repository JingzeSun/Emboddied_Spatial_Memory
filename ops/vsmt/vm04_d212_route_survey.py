#!/usr/bin/env python3
"""Generate the D-212 route bundle from public grid and RGB-D surveys."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt.d211_p0_smoke import (  # noqa: E402
    ROUTE_BUNDLE_SCHEMA,
    seal_reachable_scan,
)
from vsmt.d212_route_survey import (  # noqa: E402
    build_route_bundle_row,
    plan_route_from_reachable_scan,
    public_frame_descriptor,
    public_region_refs,
    survey_algorithm_sha256,
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _array_sha(array: Any) -> str:
    value = np.asarray(array)
    digest = hashlib.sha256()
    digest.update(str(value.dtype).encode("ascii"))
    digest.update(canonical_json(list(value.shape)).encode("utf-8"))
    digest.update(value.tobytes(order="C"))
    return digest.hexdigest()


def _calibration(event: Any) -> dict[str, Any]:
    metadata = getattr(event, "metadata", None)
    _require(type(metadata) is dict, "route survey event metadata is missing")
    fov = metadata.get("fov")
    rgb = np.asarray(getattr(event, "frame", None))
    _require(type(fov) in {int, float} and math.isfinite(float(fov)) and
             rgb.ndim == 3 and rgb.shape[2] == 3,
             "route survey calibration source is invalid")
    height, width = rgb.shape[:2]
    focal = .5 * height / math.tan(math.radians(float(fov)) / 2.0)
    return {
        "schema_version": "vsmt-vm04-d212-route-survey-calibration-v1",
        "image_height": int(height), "image_width": int(width),
        "vertical_fov_deg": float(fov), "fx": focal, "fy": focal,
        "cx": (width - 1.0) / 2.0, "cy": (height - 1.0) / 2.0,
        "contains_camera_or_agent_pose": False,
    }


def _observation(event: Any, index: int, *, scenario: str,
                 annotations: Mapping[str, Any]) -> dict[str, Any]:
    rgb = np.asarray(getattr(event, "frame", None), dtype=np.uint8)
    depth = np.asarray(getattr(event, "depth_frame", None), dtype=np.float32)
    role = "unknown"
    if scenario == "P08":
        if index in annotations["room_anchor_observation_indices"]:
            role = "room"
        elif index in annotations["corridor_observation_indices"]:
            role = "corridor"
    calibration = _calibration(event)
    return {
        "observation_index": index,
        "rgb_sha256": _array_sha(rgb),
        "depth_sha256": _array_sha(depth),
        "calibration_sha256": hashlib.sha256(
            canonical_json(calibration).encode("utf-8")).hexdigest(),
        "place_descriptor": public_frame_descriptor(rgb, depth),
        "public_region_role": role,
        "visible_entity_region_refs": public_region_refs(rgb, depth),
    }


def _success(event: Any) -> tuple[bool, str]:
    metadata = getattr(event, "metadata", None)
    _require(type(metadata) is dict, "route survey event metadata is missing")
    success = metadata.get("lastActionSuccess")
    _require(type(success) is bool, "route survey action success is missing")
    message = metadata.get("errorMessage", "")
    _require(type(message) is str, "route survey error message is not text")
    return success, hashlib.sha256(message.encode("utf-8")).hexdigest()


def survey_house(
    controller: Any, *, house_slot: int, source_house_id: str,
    slots: list[int], contract: Mapping[str, Any],
    base_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Survey every fixed slot for one house; never replace a failed route."""

    scan_event = controller.step(action="GetReachablePositions")
    scan_success, scan_error_sha = _success(scan_event)
    _require(scan_success, "public GetReachablePositions failed: " + scan_error_sha)
    positions = scan_event.metadata.get("actionReturn")
    _require(type(positions) is list and positions,
             "public GetReachablePositions returned no positions")
    scan = seal_reachable_scan(
        house_slot=house_slot, source_house_id=source_house_id,
        raw_positions=positions, contract=contract,
        base_contract=base_contract)
    rows = []
    slot_receipts = []
    for slot in slots:
        planned = plan_route_from_reachable_scan(
            slot=slot, reachable_scan=scan, contract=contract,
            base_contract=base_contract)
        route = planned["route_plan"]
        pose = planned["initial_pose"]
        teleport = {
            "action": "TeleportFull",
            "position": {"x": pose["x_m"], "y": pose["y_m"],
                         "z": pose["z_m"]},
            "rotation": {"x": 0.0, "y": pose["yaw_deg"], "z": 0.0},
            "horizon": 0.0, "standing": True, "forceAction": False,
        }
        event = controller.step(**teleport)
        ok, error_sha = _success(event)
        receipt = {
            "slot": slot, "scenario_id": route["scenario_id"],
            "route_plan_sha256": route["route_plan_sha256"],
            "planned_action_count": route["planned_action_count"],
            "completed_action_count": 0,
            "status": "survey_running" if ok else "survey_failure",
            "failure_action_index": None if ok else -1,
            "failure_error_sha256": None if ok else error_sha,
            "route_replaced_after_failure": False,
            "instance_mask_or_object_identity_read": False,
        }
        observations = []
        if ok:
            observations.append(_observation(
                event, 0, scenario=route["scenario_id"],
                annotations=planned["provisional_annotations"]))
        for action in route["actions"] if ok else []:
            event = controller.step(**dict(action["request"]))
            ok, error_sha = _success(event)
            if not ok:
                receipt.update({
                    "status": "survey_failure",
                    "failure_action_index": action["step_index"],
                    "failure_error_sha256": error_sha,
                })
                break
            receipt["completed_action_count"] += 1
            observations.append(_observation(
                event, action["step_index"] + 1,
                scenario=route["scenario_id"],
                annotations=planned["provisional_annotations"]))
        if receipt["status"] == "survey_failure":
            slot_receipts.append(receipt)
            return {"status": "route_survey_failure", "rows": rows,
                    "slot_receipts": slot_receipts,
                    "reachable_scan": scan}
        receipt["status"] = "survey_complete"
        row = build_route_bundle_row(
            planned=planned, reachable_scan=scan,
            public_observations=observations, contract=contract,
            base_contract=base_contract)
        rows.append(row)
        slot_receipts.append(receipt)
    return {"status": "route_survey_complete", "rows": rows,
            "slot_receipts": slot_receipts, "reachable_scan": scan}


def make_bundle(house_results: list[Mapping[str, Any]]) -> dict[str, Any]:
    rows = []
    for result in house_results:
        _require(result["status"] == "route_survey_complete",
                 "cannot seal a route bundle from a failed house survey")
        rows.extend(result["rows"])
    rows.sort(key=lambda row: row["route_plan"]["slot"])
    _require([row["route_plan"]["slot"] for row in rows] == list(range(12)),
             "route survey did not produce the twelve fixed slots")
    return {"schema_version": ROUTE_BUNDLE_SCHEMA, "rows": rows}


def make_stage_receipt(*, house_results: list[Mapping[str, Any]],
                       requested_workers: int, actual_workers: int,
                       resource_basis: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "vsmt-vm04-d212-route-survey-stage-receipt-v1",
        "status": ("route_survey_complete" if all(
            row["status"] == "route_survey_complete" for row in house_results)
                   else "route_survey_failure"),
        "survey_algorithm_sha256": survey_algorithm_sha256(),
        "requested_workers": requested_workers,
        "actual_workers": actual_workers,
        "resource_basis": dict(resource_basis),
        "deterministic_merge_order": [0, 1],
        "house_results": [{
            "house_slot": index, "status": row["status"],
            "completed_slots": len(row["rows"]),
            "slot_receipts": row["slot_receipts"],
        } for index, row in enumerate(house_results)],
        "future_raw_episode_or_private_reference_used": False,
        "route_replacement_after_failure": False,
    }
