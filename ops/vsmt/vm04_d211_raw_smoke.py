#!/usr/bin/env python3
"""Append-only RGB-D/provenance/private-pose writer for D-211 slot zero.

Public raw contains RGB-D and camera intrinsics; provenance contains the sealed
route and every attempted registered action.  Simulator agent/camera poses are
captured in a separate private ground-truth file which deployable readers must
not mount.  No place label, instance mask, adapter packet or metric is built.
A failed registered action keeps all earlier observations and its action
receipt, then terminates without substituting another route or house.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import sys
from typing import Any, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt.d210_place_memory import validate_route_plan  # noqa: E402
from vsmt.d211_p0_smoke import (  # noqa: E402
    validate_d211_contract,
    validate_route_execution_binding,
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _sha_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_new_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _write_new_json(path: Path, value: Any) -> None:
    _write_new_bytes(path, (canonical_json(value) + "\n").encode("utf-8"))


def _write_new_npy(path: Path, array: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            np.save(handle, array, allow_pickle=False)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _event_metadata(event: Any) -> Mapping[str, Any]:
    metadata = getattr(event, "metadata", None)
    _require(type(metadata) is dict, "simulator event metadata is missing")
    return metadata


def _action_receipt(
    event: Any, *, action_index: int | None, request: Mapping[str, Any],
    role: str,
) -> dict[str, Any]:
    metadata = _event_metadata(event)
    success = metadata.get("lastActionSuccess")
    _require(type(success) is bool, "simulator action success is missing")
    error_message = metadata.get("errorMessage", "")
    _require(type(error_message) is str,
             "simulator action error message is not text")
    public_request = (dict(request) if role == "registered_route_action" else {
        "action": "TeleportFull", "forceAction": False,
        "private_execution_binding_sha256_used": True,
    })
    return {
        "role": role,
        "action_index": action_index,
        "request": public_request,
        "success": success,
        "error_message_present": bool(error_message),
        "error_message_sha256": hashlib.sha256(
            error_message.encode("utf-8")).hexdigest(),
        "contains_world_pose": False,
        "contains_private_label": False,
    }


def _sensor_calibration(event: Any, observation_index: int) -> dict[str, Any]:
    metadata = _event_metadata(event)
    vertical_fov = metadata.get("fov")
    _require(type(vertical_fov) in {int, float} and
             math.isfinite(float(vertical_fov)) and 0.0 < float(vertical_fov) < 180.0,
             "simulator vertical field of view is invalid")
    rgb = np.asarray(getattr(event, "frame", None))
    _require(rgb.ndim == 3 and rgb.shape[2] == 3,
             "smoke RGB frame must be HxWx3")
    height, width = rgb.shape[:2]
    # AI2-THOR exposes a vertical field of view. With square pixels the image
    # height, not the width, determines both focal lengths in pixels.
    focal = 0.5 * float(height) / math.tan(
        math.radians(float(vertical_fov)) / 2.0)
    return {
        "schema_version": "vsmt-vm04-d211-public-sensor-calibration-v1",
        "observation_index": observation_index,
        "image_height": int(height), "image_width": int(width),
        "vertical_fov_deg": float(vertical_fov),
        "fx": focal, "fy": focal,
        "cx": (float(width) - 1.0) / 2.0,
        "cy": (float(height) - 1.0) / 2.0,
        "contains_camera_or_agent_pose": False,
    }


def _finite_number(value: Any, name: str) -> float:
    _require(type(value) in {int, float} and math.isfinite(float(value)),
             f"{name} is missing or non-finite")
    return float(value)


def _xyz(value: Any, name: str) -> dict[str, float]:
    _require(type(value) is dict, f"{name} is missing")
    return {axis: _finite_number(value.get(axis), f"{name}.{axis}")
            for axis in ("x", "y", "z")}


def _private_pose(
    event: Any, observation_index: int, public_frame_sha256: str,
) -> dict[str, Any]:
    """Extract simulator truth without exposing it to public/provenance files."""

    metadata = _event_metadata(event)
    agent = metadata.get("agent")
    _require(type(agent) is dict, "simulator agent pose is missing")
    rotation = agent.get("rotation")
    horizon = _finite_number(agent.get("cameraHorizon"),
                             "agent.cameraHorizon")
    value = {
        "schema_version": "vsmt-vm04-d211-private-simulator-pose-v1",
        "observation_index": observation_index,
        "public_frame_sha256": public_frame_sha256,
        "agent_world_pose": {
            "position_m": _xyz(agent.get("position"), "agent.position"),
            "rotation_deg": _xyz(rotation, "agent.rotation"),
            "camera_horizon_deg": horizon,
        },
        "camera_world_pose": {
            "position_m": _xyz(metadata.get("cameraPosition"),
                               "cameraPosition"),
            "yaw_deg": _finite_number(
                rotation.get("y") if type(rotation) is dict else None,
                "agent.rotation.y"),
            "horizon_deg": horizon,
            "orientation_source":
                "metadata.agent.rotation.y_plus_agent.cameraHorizon",
        },
        "private_ground_truth_only": True,
        "candidate_or_model_reader_allowed": False,
    }
    value["pose_sha256"] = _sha_value(value)
    return value


class D211RawSmokeStore:
    """Write one immutable RGB-D prefix and its action provenance."""

    def __init__(
        self, root: Path, *, route: Mapping[str, Any],
        execution_binding: Mapping[str, Any], source_record_sha256: str,
        public_manifest_sha256: str, episode_id: str,
        maximum_output_bytes: int,
    ) -> None:
        self.root = Path(root)
        _require(not self.root.exists(),
                 "smoke output exists; never overwrite an earlier attempt")
        self.root.mkdir(parents=True)
        self.public_root = self.root / "public"
        self.provenance_root = self.root / "provenance"
        self.private_root = self.root / "private"
        self.public_root.mkdir()
        self.provenance_root.mkdir()
        self.private_root.mkdir()
        self.route = dict(route)
        self.binding = dict(execution_binding)
        self.source_record_sha256 = source_record_sha256
        self.public_manifest_sha256 = public_manifest_sha256
        _require(type(episode_id) is str and episode_id.startswith("d210:p0:"),
                 "smoke episode ID is invalid")
        self.episode_id = episode_id
        self.maximum_output_bytes = maximum_output_bytes
        self.frames: list[dict[str, Any]] = []
        self.private_poses: list[dict[str, Any]] = []
        self.action_receipts: list[dict[str, Any]] = []
        self.finalized = False
        _write_new_json(self.provenance_root / "route.json", self.route)
        _write_new_json(self.provenance_root / "execution-binding-ref.json", {
            "schema_version": "vsmt-vm04-d211-execution-binding-ref-v1",
            "execution_binding_sha256":
                self.binding["execution_binding_sha256"],
            "initial_pose_copied_to_raw_smoke": False,
        })

    def _bytes_written(self) -> int:
        return sum(path.stat().st_size for path in self.root.rglob("*")
                   if path.is_file())

    def append_action_receipt(self, receipt: Mapping[str, Any]) -> None:
        _require(not self.finalized, "smoke store is finalized")
        self.action_receipts.append(dict(receipt))

    def capture(self, event: Any, observation_index: int) -> dict[str, Any]:
        _require(not self.finalized, "smoke store is finalized")
        _require(observation_index == len(self.frames),
                 "smoke observations must be contiguous from zero")
        rgb = np.asarray(getattr(event, "frame", None), dtype=np.uint8)
        depth = np.asarray(getattr(event, "depth_frame", None), dtype=np.float32)
        _require(rgb.ndim == 3 and rgb.shape[2] == 3 and
                 depth.ndim == 2 and depth.shape == rgb.shape[:2],
                 "smoke RGB-D shapes are invalid")
        calibration = _sensor_calibration(event, observation_index)
        # Validate the private pose before creating any files for this frame.
        private_pose = _private_pose(
            event, observation_index, "0" * 64)
        frame_root = self.public_root / "raw" / f"frame_{observation_index:04d}"
        rgb_path = frame_root / "rgb.npy"
        depth_path = frame_root / "depth_m.npy"
        calibration_path = frame_root / "sensor-calibration.json"
        _write_new_npy(rgb_path, rgb)
        _write_new_npy(depth_path, depth)
        _write_new_json(calibration_path, calibration)
        record = {
            "schema_version": "vsmt-vm04-d211-public-raw-frame-v1",
            "observation_index": observation_index,
            "rgb_sha256": _sha_file(rgb_path),
            "depth_m_sha256": _sha_file(depth_path),
            "sensor_calibration_sha256": _sha_file(calibration_path),
            "contains_world_pose": False,
            "contains_instance_masks": False,
        }
        record["frame_sha256"] = _sha_value(record)
        private_pose["public_frame_sha256"] = record["frame_sha256"]
        private_pose.pop("pose_sha256")
        private_pose["pose_sha256"] = _sha_value(private_pose)
        _write_new_json(frame_root / "frame.json", record)
        self.frames.append(record)
        self.private_poses.append(private_pose)
        _require(self._bytes_written() <= self.maximum_output_bytes,
                 "smoke output crossed the registered byte safety limit")
        return record

    def finalize(self, *, status: str, reason: str | None) -> dict[str, Any]:
        _require(not self.finalized, "smoke store is already finalized")
        _require(status in {"raw_smoke_complete", "raw_smoke_failure"},
                 "smoke terminal status is invalid")
        _require((reason is None) == (status == "raw_smoke_complete"),
                 "smoke reason/status disagree")
        _require(len(self.private_poses) == len(self.frames),
                 "public observations and private poses lost alignment")
        action_path = self.provenance_root / "action-receipts.json"
        action_record = {
            "schema_version": "vsmt-vm04-d211-action-receipts-v1",
            "route_plan_sha256": self.route["route_plan_sha256"],
            "receipts": self.action_receipts,
            "complete_per_action_sequence_retained": True,
        }
        _write_new_json(action_path, action_record)
        private_pose_path = self.private_root / "simulator-poses.json"
        private_pose_record = {
            "schema_version":
                "vsmt-vm04-d211-private-simulator-pose-series-v1",
            "episode_id": self.episode_id,
            "route_plan_sha256": self.route["route_plan_sha256"],
            "observation_count": len(self.private_poses),
            "poses": self.private_poses,
            "opened_after_candidate_seal": True,
            "candidate_or_model_reader_allowed": False,
            "contains_place_or_loop_labels": False,
        }
        _write_new_json(private_pose_path, private_pose_record)
        public_manifest = {
            "schema_version": "vsmt-vm04-d211-public-raw-smoke-manifest-v1",
            "episode_id": self.episode_id,
            "slot": self.route["slot"],
            "scenario_id": self.route["scenario_id"],
            "status": status, "reason": reason,
            "frame_count": len(self.frames), "frames": self.frames,
            "world_pose_exported": False, "instance_masks_exported": False,
            "adapter_materialized": False, "private_evaluation_performed": False,
        }
        public_path = self.public_root / "raw-smoke.manifest.json"
        _write_new_json(public_path, public_manifest)
        completed_actions = sum(
            row.get("role") == "registered_route_action" and
            row.get("success") is True
            for row in self.action_receipts)
        receipt = {
            "schema_version": "vsmt-vm04-d211-raw-smoke-receipt-v1",
            "status": status, "reason": reason,
            "slot": self.route["slot"],
            "route_plan_sha256": self.route["route_plan_sha256"],
            "execution_binding_sha256":
                self.binding["execution_binding_sha256"],
            "sealed_public_batch_manifest_sha256": self.public_manifest_sha256,
            "source_record_sha256": self.source_record_sha256,
            "planned_action_count": self.route["planned_action_count"],
            "completed_registered_action_count": completed_actions,
            "saved_post_action_observation_count": max(0, len(self.frames) - 1),
            "observation_count": len(self.frames),
            "public_raw_manifest_sha256": _sha_file(public_path),
            "action_receipts_sha256": _sha_file(action_path),
            "private_simulator_poses_sha256": _sha_file(private_pose_path),
            "private_simulator_pose_count": len(self.private_poses),
            "failed_route_replacement_allowed": False,
            "twelve_slot_generation_started": False,
            "adapter_materialized": False,
            "private_evaluation_performed": False,
        }
        receipt["receipt_sha256"] = _sha_value(receipt)
        _write_new_json(self.root / "smoke.receipt.json", receipt)
        self.finalized = True
        return receipt


def run_raw_smoke_core(
    controller: Any, *, route_plan: Mapping[str, Any],
    execution_binding: Mapping[str, Any], d211_contract: Mapping[str, Any],
    base_contract: Mapping[str, Any], output_root: Path,
    source_record_sha256: str, public_manifest_sha256: str,
    episode_id: str,
) -> dict[str, Any]:
    """Execute only the pre-authorized slot; caller owns the fresh controller."""

    approved = validate_d211_contract(d211_contract,
                                      base_contract=base_contract)
    route = validate_route_plan(route_plan, base_contract)
    binding = validate_route_execution_binding(
        execution_binding, route_plan=route, contract=approved,
        base_contract=base_contract)
    smoke = approved["single_slot_smoke"]
    _require((route["slot"], route["house_slot"], route["scenario_id"]) ==
             (smoke["slot"], smoke["house_slot"], smoke["scenario_id"]),
             "only the D-211 registered smoke slot may execute")
    source = approved["source_binding"]["houses"][route["house_slot"]]
    _require(source_record_sha256 == source["source_record_sha256"],
             "smoke source record digest changed")
    store = D211RawSmokeStore(
        output_root, route=route, execution_binding=binding,
        source_record_sha256=source_record_sha256,
        public_manifest_sha256=public_manifest_sha256,
        episode_id=episode_id,
        maximum_output_bytes=approved["resource_policy"]
        ["maximum_smoke_output_bytes"],
    )
    pose = binding["initial_pose"]
    teleport = {
        "action": "TeleportFull",
        "position": {"x": pose["x_m"], "y": pose["y_m"], "z": pose["z_m"]},
        "rotation": {"x": 0.0, "y": pose["yaw_deg"], "z": 0.0},
        "horizon": pose["horizon_deg"], "standing": True,
        "forceAction": False,
    }
    try:
        event = controller.step(**teleport)
        setup_receipt = _action_receipt(
            event, action_index=None, request=teleport, role="setup_teleport")
        store.append_action_receipt(setup_receipt)
        if not setup_receipt["success"]:
            return store.finalize(
                status="raw_smoke_failure", reason="initial_teleport_failed")
        store.capture(event, 0)
        for action in route["actions"]:
            request = dict(action["request"])
            event = controller.step(**request)
            receipt = _action_receipt(
                event, action_index=action["step_index"], request=request,
                role="registered_route_action")
            store.append_action_receipt(receipt)
            if not receipt["success"]:
                return store.finalize(
                    status="raw_smoke_failure",
                    reason="registered_route_action_failed")
            store.capture(event, action["step_index"] + 1)
        _require(len(store.frames) == route["observation_count"],
                 "successful smoke did not save N+1 observations")
        return store.finalize(status="raw_smoke_complete", reason=None)
    except BaseException as error:
        if not store.finalized:
            store.append_action_receipt({
                "role": "worker_exception", "action_index": None,
                "request": {}, "success": False,
                "error_message_present": True,
                "error_message_sha256": hashlib.sha256(
                    str(error).encode("utf-8")).hexdigest(),
                "exception_type": type(error).__name__,
                "contains_world_pose": False,
                "contains_private_label": False,
            })
            store.finalize(status="raw_smoke_failure",
                           reason="worker_exception")
        raise
