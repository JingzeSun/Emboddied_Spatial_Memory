#!/usr/bin/env python3
"""One-house D-217 public RGB-D generator; no instance channel is requested."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
OPS = Path(__file__).resolve().parent
for item in (SRC, OPS):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt.d217_estimator_development import (  # noqa: E402
    select_reachable_positions,
    structural_label_from_reachable,
)
import vm04_two_house_worker as source_worker  # noqa: E402


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _make_controller(house: dict[str, Any], config: dict[str, Any]):
    from ai2thor.controller import Controller
    from ai2thor.platform import CloudRendering

    upgraded = source_worker.upgrade_house_schema_v1(
        house, source_worker.load_pinned_asset_id_database())
    values = config["rgbd_generation"]
    controller = Controller(
        platform=CloudRendering, scene=upgraded,
        width=values["width"], height=values["height"],
        fieldOfView=values["vertical_fov_degrees"],
        gridSize=values["grid_size_m"], snapToGrid=values["snap_to_grid"],
        rotateStepDegrees=values["rotate_step_degrees"],
        renderDepthImage=True, renderInstanceSegmentation=False,
    )
    if controller.last_event.metadata.get("lastActionSuccess") is not True:
        error = controller.last_event.metadata.get("errorMessage")
        controller.stop()
        raise RuntimeError(f"ProcTHOR scene creation failed: {error}")
    source_worker.bootstrap_house_agent(controller, upgraded)
    return controller


def generate_house(task: dict[str, Any]) -> dict[str, Any]:
    """Generate exactly 32 observations or retain one immutable failure."""

    row = task["row"]
    split = row["split"]
    rank = row["sample_rank"]
    root = Path(task["output_root"])
    private_dir = root / "private" / split / f"sample_{rank:04d}"
    public_dir = root / "public" / split / f"sample_{rank:04d}"
    failure_path = private_dir / "failure.json"
    controller = None
    try:
        house = source_worker.load_source_record(
            task["source_root"], row["source_locator"])
        observed_source_sha = _sha(house)
        if observed_source_sha != row["source_record_sha256"]:
            raise RuntimeError("source record digest changed")
        controller = _make_controller(house, task["contract"])
        reachable_event = controller.step(action="GetReachablePositions")
        if reachable_event.metadata.get("lastActionSuccess") is not True:
            raise RuntimeError("GetReachablePositions failed")
        reachable = reachable_event.metadata.get("actionReturn")
        if not isinstance(reachable, list) or not reachable:
            raise RuntimeError("GetReachablePositions returned no positions")
        positions = select_reachable_positions(
            row["house_id"], reachable,
            split_salt=task["d215_split_salt"], count=8,
            minimum_separation_m=1.0)
        frames, depths, intrinsics, observation_ids = [], [], [], []
        labels, private_observations = [], []
        values = task["contract"]["rgbd_generation"]
        height, width = values["height"], values["width"]
        fy = (height / 2.0) / np.tan(
            np.deg2rad(values["vertical_fov_degrees"]) / 2.0)
        fx = fy
        cx, cy = (width - 1.0) / 2.0, (height - 1.0) / 2.0
        for position_index, position in enumerate(positions):
            structural = structural_label_from_reachable(reachable, position)
            for yaw in values["yaw_degrees"]:
                event = controller.step(
                    action="TeleportFull", x=position["x"], y=position["y"],
                    z=position["z"],
                    rotation={"x": 0.0, "y": float(yaw), "z": 0.0},
                    horizon=values["horizon_degrees"],
                    standing=values["standing"], forceAction=True)
                if event.metadata.get("lastActionSuccess") is not True:
                    raise RuntimeError(
                        f"TeleportFull failed at position {position_index} yaw {yaw}")
                rgb = np.asarray(event.frame)
                depth = np.asarray(event.depth_frame)
                if rgb.shape != (height, width, 3) or rgb.dtype != np.uint8:
                    raise RuntimeError("RGB frame schema changed")
                if depth.shape != (height, width) or not np.issubdtype(
                        depth.dtype, np.floating):
                    raise RuntimeError("depth frame schema changed")
                observation_id = _sha({
                    "public_house_ref": row["public_house_ref"],
                    "position_index": position_index, "yaw_degrees": yaw,
                })
                frames.append(rgb.copy())
                depths.append(depth.astype(np.float32, copy=True))
                intrinsics.append([fx, fy, cx, cy])
                observation_ids.append(observation_id)
                labels.append(structural)
                private_observations.append({
                    "observation_id": observation_id,
                    "position_index": position_index,
                    "world_position": position,
                    "yaw_degrees": yaw,
                    "structural_label": structural,
                })
        arrays = {
            "rgb_uint8": np.stack(frames),
            "depth_m_float32": np.stack(depths),
            "camera_intrinsics_float64": np.asarray(intrinsics, dtype=np.float64),
            "observation_ids": np.asarray(observation_ids),
        }
        public_path = public_dir / "rgbd.npz"
        source_worker.save_npz_new(public_path, **arrays)
        public_receipt = {
            "schema_version": "vsmt-vm04-d217-public-rgbd-house-v1",
            "split": split, "sample_rank": rank,
            "public_house_ref": row["public_house_ref"],
            "observation_count": 32,
            "observation_ids_sha256": _sha(observation_ids),
            "rgbd_npz_sha256": source_worker.sha256(public_path),
            "contains_house_world_pose_grid_instance_scenario_teacher_or_future":
                False,
        }
        public_receipt["public_receipt_sha256"] = _sha(public_receipt)
        source_worker.write_new_json(public_dir / "receipt.json", public_receipt)
        reachable_rows = sorted({
            (round(float(item["x"]), 6), round(float(item["y"]), 6),
             round(float(item["z"]), 6)) for item in reachable})
        private_receipt = {
            "schema_version": "vsmt-vm04-d217-private-rgbd-house-v1",
            "split": split, "sample_rank": rank, "house_id": row["house_id"],
            "source_record_sha256": row["source_record_sha256"],
            "public_receipt_sha256": public_receipt["public_receipt_sha256"],
            "reachable_grid_sha256": _sha(reachable_rows),
            "selected_world_positions": positions,
            "observations": private_observations,
            "structural_label_counts": {
                name: labels.count(name)
                for name in ("basin", "bottleneck", "unknown")},
            "instance_segmentation_requested_or_read": False,
        }
        private_receipt["private_receipt_sha256"] = _sha(private_receipt)
        source_worker.write_new_json(private_dir / "receipt.json", private_receipt)
        return {
            "split": split, "sample_rank": rank, "success": True,
            "public_receipt_sha256": public_receipt["public_receipt_sha256"],
            "private_receipt_sha256": private_receipt["private_receipt_sha256"],
            "public_file_bytes": public_path.stat().st_size,
        }
    except Exception as error:
        failure = {
            "schema_version": "vsmt-vm04-d217-house-failure-v1",
            "split": split, "sample_rank": rank, "house_id": row["house_id"],
            "error_type": type(error).__name__, "message": str(error),
            "replacement_allowed": False,
        }
        source_worker.write_new_json(failure_path, failure)
        return {
            "split": split, "sample_rank": rank, "success": False,
            "failure_sha256": source_worker.sha256(failure_path),
            "error_type": type(error).__name__,
        }
    finally:
        if controller is not None:
            controller.stop()
