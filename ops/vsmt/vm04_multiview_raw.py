#!/usr/bin/env python3
"""Write one post-D-183 multiview episode with a strict public/private split."""

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
from vsmt.vm04_odometry import DeclaredOdometry  # noqa: E402
from vsmt.vm04_observation_runner import (  # noqa: E402
    ObservationConstructionError,
    public_route_projection,
    validate_route_plan,
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ObservationConstructionError(message)


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


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
    payload = (json.dumps(value, sort_keys=True, indent=2,
                          ensure_ascii=False) + "\n").encode("utf-8")
    _write_new_bytes(path, payload)


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


def _write_new_npz(path: Path, **arrays: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            np.savez_compressed(handle, **arrays)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _simulator_camera_values(event: Any) -> dict[str, Any]:
    metadata = getattr(event, "metadata", None)
    _require(type(metadata) is dict, "simulator event metadata is missing")
    agent = metadata.get("agent")
    _require(type(agent) is dict and type(agent.get("position")) is dict and
             type(agent.get("rotation")) is dict,
             "simulator camera pose is missing")
    position = metadata.get("cameraPosition") or agent["position"]
    _require(type(position) is dict, "simulator camera position is missing")
    values = {
        "x_m": position.get("x"), "y_m": position.get("y"),
        "z_m": position.get("z"), "yaw_deg": agent["rotation"].get("y"),
        "horizon_deg": agent.get("cameraHorizon", 0.0),
        "vertical_fov_deg": metadata.get("fov"),
    }
    _require(all(type(value) in {int, float} for value in values.values()),
             "simulator camera values are not numeric")
    frame = np.asarray(getattr(event, "frame", None))
    _require(frame.ndim == 3 and frame.shape[2] == 3,
             "camera record requires an HxWx3 RGB frame")
    height, width = frame.shape[:2]
    return {
        **{key: float(value) for key, value in values.items()},
        "image_height": int(height), "image_width": int(width),
    }


def _private_camera_truth(event: Any, observation_index: int) -> dict[str, Any]:
    """The true world pose, written to the private evaluation side only (D-206)."""

    values = _simulator_camera_values(event)
    yaw = math.radians(values["yaw_deg"])
    pitch = math.radians(values["horizon_deg"])
    cy, sy = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
    cx, sx = math.cos(pitch / 2.0), math.sin(pitch / 2.0)
    return {
        "schema_version": "vsmt-vm04-raw-private-camera-truth-v1",
        "observation_index": observation_index,
        "world_pose": {
            "position_m": [values["x_m"], values["y_m"], values["z_m"]],
            "quaternion_xyzw": [
                float(sx * cy), float(cx * sy), float(-sx * sy), float(cx * cy),
            ],
            "yaw_deg": values["yaw_deg"],
            "horizon_deg": values["horizon_deg"],
        },
        "role": "post_seal_evaluation_only_never_a_deployment_input",
    }


def _public_camera_record(
    event: Any, observation_index: int, relative_pose: Mapping[str, Any],
) -> dict[str, Any]:
    """Public camera record carrying calibration and the relative estimate only.

    D-206: the simulator world pose is not published.  Intrinsics stay public
    because they are a fixed sensor property rather than a localisation answer,
    and the public depth geometry needs them.
    """

    values = _simulator_camera_values(event)
    width = values["image_width"]
    focal = 0.5 * float(width) / math.tan(
        math.radians(values["vertical_fov_deg"]) / 2.0)
    _require(relative_pose.get("observation_index") == observation_index,
             "relative pose does not match this observation index")
    _require(relative_pose.get("is_world_pose") is False,
             "public camera record may not carry a world pose")
    return {
        "schema_version": "vsmt-vm04-raw-public-camera-v2",
        "observation_index": observation_index,
        "vertical_fov_deg": values["vertical_fov_deg"],
        "image_height": values["image_height"],
        "image_width": width,
        "pose_frame": relative_pose["frame"],
        "is_world_pose": False,
        "noise_model_id": relative_pose["noise_model_id"],
        "pose": {
            "position_m": list(relative_pose["position_m"]),
            "quaternion_xyzw": list(relative_pose["quaternion_xyzw"]),
        },
        "calibration": {
            "fx": focal, "fy": focal,
            "cx": (float(width) - 1.0) / 2.0,
            "cy": (float(values["image_height"]) - 1.0) / 2.0,
        },
    }


class RawEpisodeStore:
    """Append-only raw writer; a failed episode keeps every completed frame."""

    def __init__(
        self, episode_root: Path, *, plan: Mapping[str, Any],
        contract: Mapping[str, Any],
    ) -> None:
        self.root = Path(episode_root)
        _require(not self.root.exists(), "episode output already exists")
        self.route = validate_route_plan(plan, contract=contract)
        self.public_route = public_route_projection(plan, contract=contract)
        self.public_root = self.root / "public"
        self.private_root = self.root / "private"
        self.public_root.mkdir(parents=True)
        self.private_root.mkdir()
        _write_new_json(self.public_root / "route.json", self.public_route)
        _write_new_json(self.private_root / "route-plan.json", self.route)
        self.public_frames: list[dict[str, Any]] = []
        self.private_frames: list[dict[str, Any]] = []
        self.finalized = False
        pose_channel = contract.get("public_pose_channel")
        _require(type(pose_channel) is dict,
                 "D-206 public pose channel is missing from the contract")
        self.odometry = DeclaredOdometry(
            noise_model=pose_channel["declared_odometry_noise_model"],
            action_request_templates=contract["observation_trajectory"][
                "registered_action_request_templates"],
            episode_seed_material=(
                f"{self.route['episode_id']}|{self.route['route_plan_sha256']}"
            ),
        )

    def extract_public_frame(
        self, event: Any, observation_index: int,
    ) -> dict[str, Any]:
        """Persist both sides, then return only the public RGB-D view."""

        _require(not self.finalized, "episode store is already finalized")
        _require(observation_index == len(self.public_frames),
                 "raw observations must be contiguous from zero")
        rgb = np.asarray(getattr(event, "frame", None), dtype=np.uint8)
        depth = np.asarray(getattr(event, "depth_frame", None), dtype=np.float32)
        _require(rgb.ndim == 3 and rgb.shape[2] == 3,
                 "public RGB frame must be HxWx3")
        _require(depth.ndim == 2 and depth.shape == rgb.shape[:2],
                 "public depth frame must match RGB height and width")
        if observation_index == 0:
            relative_pose = self.odometry.pose()
        else:
            action = self.route["registered_actions"][observation_index - 1]
            relative_pose = self.odometry.advance(action["action"])
        camera = _public_camera_record(event, observation_index, relative_pose)
        camera_truth = _private_camera_truth(event, observation_index)

        name = f"frame_{observation_index:04d}"
        public_directory = self.public_root / "raw" / name
        private_directory = self.private_root / "raw" / name
        rgb_path = public_directory / "rgb.npy"
        depth_path = public_directory / "depth_m.npy"
        camera_path = public_directory / "camera.json"
        _write_new_npy(rgb_path, rgb)
        _write_new_npy(depth_path, depth)
        _write_new_json(camera_path, camera)
        public_record = {
            "schema_version": "vsmt-vm04-raw-public-frame-v1",
            "observation_index": observation_index,
            "rgb_sha256": _sha_file(rgb_path),
            "depth_m_sha256": _sha_file(depth_path),
            "camera_sha256": _sha_file(camera_path),
        }
        public_record["source_frame_sha256"] = _sha_value(public_record)
        public_record_path = public_directory / "frame.json"
        _write_new_json(public_record_path, public_record)
        public_record["frame_record_sha256"] = _sha_file(public_record_path)

        masks = getattr(event, "instance_masks", None)
        _require(type(masks) is dict, "private instance masks are missing")
        _require(all(type(key) is str and key for key in masks),
                 "private instance mask IDs must be nonempty strings")
        private_ids = sorted(masks)
        mask_rows = []
        for private_id in private_ids:
            mask = np.asarray(masks[private_id], dtype=np.uint8)
            _require(mask.shape == depth.shape,
                     "private instance mask shape differs from public frame")
            mask_rows.append(mask)
        stack = (np.stack(mask_rows, axis=0) if mask_rows else
                 np.empty((0, *depth.shape), dtype=np.uint8))
        masks_path = private_directory / "instance_masks.npz"
        _write_new_npz(masks_path, masks=stack)
        truth_path = private_directory / "camera_truth.json"
        _write_new_json(truth_path, camera_truth)
        mapping = {
            "schema_version": "vsmt-vm04-raw-private-frame-map-v1",
            "observation_index": observation_index,
            "private_instance_ids": private_ids,
            "instance_masks_sha256": _sha_file(masks_path),
            "camera_truth_sha256": _sha_file(truth_path),
            "public_frame_record_sha256": public_record["frame_record_sha256"],
            "public_source_frame_sha256": public_record["source_frame_sha256"],
        }
        mapping_path = private_directory / "mapping.json"
        _write_new_json(mapping_path, mapping)
        private_record = {
            "observation_index": observation_index,
            "instance_masks_sha256": mapping["instance_masks_sha256"],
            "camera_truth_sha256": mapping["camera_truth_sha256"],
            "private_mapping_sha256": _sha_file(mapping_path),
            "public_frame_record_sha256": public_record["frame_record_sha256"],
        }
        self.public_frames.append(public_record)
        self.private_frames.append(private_record)
        return {
            "rgb": rgb.copy(),
            "depth_m": depth.copy(),
            "camera": dict(camera),
            "source_frame_sha256": public_record["source_frame_sha256"],
            "private_fields_removed": True,
        }

    def finalize(self, result: Mapping[str, Any]) -> dict[str, Any]:
        """Write exactly one public/private terminal pair and bound manifests."""

        _require(not self.finalized, "episode store is already finalized")
        _require(result.get("status") in {"raw_complete", "raw_failure"},
                 "worker result has no terminal status")
        public_terminal = {
            "schema_version": "vsmt-vm04-multiview-raw-terminal-v1",
            "episode_id": self.route["episode_id"],
            "status": result["status"],
            "reason": result.get("reason"),
            "route_plan_sha256": self.route["route_plan_sha256"],
            "route_receipt": result.get("route_receipt"),
            "construction_verdict": result.get("construction_verdict"),
            "public_observation_prefix": result.get("public_observation_prefix"),
            "failed_route_replacement_allowed": False,
        }
        public_terminal_path = self.public_root / "raw.terminal.json"
        _write_new_json(public_terminal_path, public_terminal)
        private_terminal = {
            "schema_version": "vsmt-vm04-multiview-private-terminal-v1",
            "episode_id": self.route["episode_id"],
            "status": result["status"],
            "intervention_executed": result.get("intervention_executed", False),
            "private_intervention_record":
                result.get("private_intervention_record"),
            "public_terminal_sha256": _sha_file(public_terminal_path),
        }
        private_terminal_path = self.private_root / "raw.terminal.json"
        _write_new_json(private_terminal_path, private_terminal)
        public_manifest = {
            "schema_version": "vsmt-vm04-raw-public-episode-manifest-v1",
            "episode_id": self.route["episode_id"],
            "public_route_file_sha256": _sha_file(
                self.public_root / "route.json"),
            "frame_count": len(self.public_frames),
            "frames": self.public_frames,
            "public_terminal_sha256": _sha_file(public_terminal_path),
        }
        public_manifest_path = self.public_root / "raw.manifest.json"
        _write_new_json(public_manifest_path, public_manifest)
        private_manifest = {
            "schema_version": "vsmt-vm04-raw-private-episode-manifest-v1",
            "episode_id": self.route["episode_id"],
            "private_route_plan_file_sha256": _sha_file(
                self.private_root / "route-plan.json"),
            "public_manifest_sha256": _sha_file(public_manifest_path),
            "frame_count": len(self.private_frames),
            "frames": self.private_frames,
            "private_terminal_sha256": _sha_file(private_terminal_path),
        }
        private_manifest_path = self.private_root / "raw.manifest.json"
        _write_new_json(private_manifest_path, private_manifest)
        self.finalized = True
        return {
            "episode_root": str(self.root),
            "status": result["status"],
            "frame_count": len(self.public_frames),
            "public_manifest_sha256": _sha_file(public_manifest_path),
            "raw_episode_manifest_sha256": _sha_file(private_manifest_path),
        }

    def finalize_exception(self, error: BaseException) -> dict[str, Any]:
        """Retain raw prefix without exposing exception text publicly."""

        result = {
            "status": "raw_failure",
            "reason": "simulator_or_worker_exception",
            "public_observation_prefix": None,
            "intervention_executed": False,
            "private_intervention_record": {
                "exception_type": type(error).__name__,
                "exception_message": str(error),
            },
        }
        return self.finalize(result)
