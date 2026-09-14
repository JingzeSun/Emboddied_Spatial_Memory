#!/usr/bin/env python3
"""Python-3.9-compatible AI2-THOR family worker for the VM-04 audit.

The worker owns one preselected house and all 18 fixed slots.  Target choice
uses anonymous mask geometry only.  Private simulator IDs remain under the
private raw directory and never enter public camera/RGB/depth files.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time


class ResourceStop(RuntimeError):
    """Stop dispatching new fixed slots after a frozen family resource limit."""


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_sha256(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_new_json(path, value):
    path = Path(path)
    payload = (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def save_npy_new(path, array):
    import numpy as np

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            np.save(handle, array, allow_pickle=False)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def save_npz_new(path, **arrays):
    import numpy as np

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            np.savez_compressed(handle, **arrays)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def directory_bytes(path):
    return sum(item.stat().st_size for item in Path(path).rglob("*") if item.is_file())


def open_text(path):
    path = Path(path)
    return gzip.open(str(path), "rt", encoding="utf-8") if path.name.endswith(".gz") else path.open(
        "r", encoding="utf-8"
    )


def records_from_json(path):
    path = Path(path)
    with open_text(path) as handle:
        if path.name.endswith(".jsonl") or path.name.endswith(".jsonl.gz"):
            for index, line in enumerate(handle):
                if line.strip():
                    value = json.loads(line)
                    require(isinstance(value, dict), "source JSONL row is not an object")
                    yield index, value
            return
        value = json.load(handle)
    if isinstance(value, dict) and isinstance(value.get("train"), list):
        rows = value["train"]
    elif isinstance(value, dict) and isinstance(value.get("houses"), list):
        rows = value["houses"]
    elif isinstance(value, list):
        rows = value
    elif isinstance(value, dict):
        rows = [value]
    else:
        raise RuntimeError("unsupported source JSON shape")
    for index, row in enumerate(rows):
        require(isinstance(row, dict), "source row is not an object")
        yield index, row


def load_source_record(source_root, locator):
    root = Path(source_root).resolve()
    path = (root / locator["relative_path"]).resolve()
    require(root in path.parents and path.is_file(), "source locator escapes or is missing")
    for index, row in records_from_json(path):
        if index == locator["index"]:
            return dict(row)
    raise RuntimeError("source locator index is absent")


def rank_visible_instance_ids(instance_masks):
    import numpy as np

    ranked = []
    shape = None
    for private_id, raw in instance_masks.items():
        mask = np.asarray(raw, dtype=np.bool_)
        if mask.ndim != 2:
            continue
        shape = shape or tuple(mask.shape)
        require(tuple(mask.shape) == shape, "instance masks have inconsistent shapes")
        flat = mask.reshape(-1)
        indices = np.flatnonzero(flat)
        if len(indices) < 196:
            continue
        digest = hashlib.sha256(
            canonical_json([mask.shape[0], mask.shape[1]] + flat.astype(int).tolist()).encode(
                "utf-8"
            )
        ).hexdigest()
        ranked.append((int(indices[0]), int(len(indices)), digest, str(private_id)))
    ranked.sort()
    return [row[-1] for row in ranked]


def intervention_actions(program, frame_index, targets, initial_objects):
    required = 2 if program in {"SPLIT", "REPLACE"} else 1
    require(len(targets) >= required, "%s requires %s public targets" % (program, required))
    primary = targets[0]
    secondary = targets[1] if len(targets) > 1 else None
    if frame_index == -1 and program in {"BIRTH", "REPLACE"}:
        return [{"action": "DisableObject", "objectId": primary if program == "BIRTH" else secondary}]
    if frame_index == 16 and program == "REACTIVATE":
        return [{"action": "DisableObject", "objectId": primary}]
    if frame_index == 22 and program in {"RETRACT", "REPLACE"}:
        return [{"action": "DisableObject", "objectId": primary}]
    if frame_index == 24 and program in {"BIRTH", "REACTIVATE"}:
        return [{"action": "EnableObject", "objectId": primary}]
    if frame_index == 24 and program == "REPLACE":
        return [{"action": "EnableObject", "objectId": secondary}]
    if frame_index == 24 and program == "RELINK":
        value = initial_objects.get(primary)
        require(isinstance(value, dict) and isinstance(value.get("position"), dict),
                "RELINK target lacks an initial position")
        position = dict(value["position"])
        position["x"] = float(position["x"]) + 0.5
        return [{
            "action": "TeleportObject", "objectId": primary, "position": position,
            "rotation": value.get("rotation", {"x": 0, "y": 0, "z": 0}),
            "forceAction": True,
        }]
    return []


def registered_agent_action(replicate, frame_index):
    """Return one predeclared public camera action and its numeric command."""

    require(replicate in (0, 1), "replicate must be zero or one")
    sign = 1.0 if (frame_index + replicate) % 2 == 0 else -1.0
    name = "RotateRight" if sign > 0 else "RotateLeft"
    return ({"action": name, "degrees": 0.25}, [0.0, sign * 0.25])


def camera_pose(event):
    metadata = event.metadata
    position = metadata.get("cameraPosition") or metadata["agent"]["position"]
    yaw = math.radians(float(metadata["agent"]["rotation"]["y"]))
    pitch = math.radians(float(metadata["agent"].get("cameraHorizon", 0.0)))
    cy, sy = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
    cx, sx = math.cos(pitch / 2.0), math.sin(pitch / 2.0)
    quaternion = [sx * cy, cx * sy, -sx * sy, cx * cy]
    height, width = event.frame.shape[:2]
    field_of_view = float(metadata.get("fov", 90.0))
    focal = 0.5 * float(width) / math.tan(math.radians(field_of_view) / 2.0)
    return ({
        "position_m": [float(position[axis]) for axis in ("x", "y", "z")],
        "quaternion_xyzw": [float(value) for value in quaternion],
    }, {"fx": focal, "fy": focal, "cx": (width - 1) / 2.0, "cy": (height - 1) / 2.0})


def capture_frame(
    event, public_directory, private_directory, frame_index, actions, targets,
    past_actions,
):
    import numpy as np

    require(event.metadata.get("lastActionSuccess") is True,
            "simulator action failed: %s" % event.metadata.get("errorMessage"))
    public_frame = public_directory / ("frame_%04d" % frame_index)
    private_frame = private_directory / ("frame_%04d" % frame_index)
    pose, calibration = camera_pose(event)
    rgb = np.asarray(event.frame, dtype=np.uint8)
    depth = np.asarray(event.depth_frame, dtype=np.float32)
    save_npy_new(public_frame / "rgb.npy", rgb)
    save_npy_new(public_frame / "depth.npy", depth)
    write_new_json(public_frame / "camera.json", {
        "frame_index": frame_index, "time_s": frame_index * 0.3,
        "pose": pose, "calibration": calibration, "last_action_success": True,
        "past_actions": list(past_actions),
        "rgb_sha256": sha256(public_frame / "rgb.npy"),
        "depth_sha256": sha256(public_frame / "depth.npy"),
    })
    masks = [(str(key), np.asarray(value, dtype=np.uint8)) for key, value in event.instance_masks.items()]
    masks.sort(key=lambda item: item[0])
    stack = np.stack([item[1] for item in masks], axis=0) if masks else np.zeros(
        (0, rgb.shape[0], rgb.shape[1]), dtype=np.uint8
    )
    save_npz_new(private_frame / "instance_masks.npz", masks=stack)
    object_rows = {
        str(row["objectId"]): {
            "position": row.get("position"), "rotation": row.get("rotation"),
            "visible": row.get("visible"), "isPickedUp": row.get("isPickedUp"),
        } for row in event.metadata.get("objects", [])
    }
    write_new_json(private_frame / "mapping.json", {
        "frame_index": frame_index, "private_instance_ids": [item[0] for item in masks],
        "target_instance_ids": list(targets), "applied_actions": list(actions),
        "objects": object_rows,
        "instance_masks_sha256": sha256(private_frame / "instance_masks.npz"),
        "public_camera_sha256": sha256(public_frame / "camera.json"),
    })
    return {
        "frame_index": frame_index,
        "public_camera_sha256": sha256(public_frame / "camera.json"),
        "private_mapping_sha256": sha256(private_frame / "mapping.json"),
        "visible_instance_count": len(masks),
    }


def run_episode(house, assignment, episode_root, family_byte_limit):
    from ai2thor.controller import Controller
    from ai2thor.platform import CloudRendering

    program = assignment["program"]
    public_directory = episode_root / "public"
    private_directory = episode_root / "private"
    public_directory.mkdir(parents=True)
    private_directory.mkdir(parents=True)
    controller = Controller(
        platform=CloudRendering, scene=house, width=224, height=224,
        renderDepthImage=True, renderInstanceSegmentation=True,
    )
    started = time.monotonic()
    frames, actions = [], []
    try:
        probe = controller.step(action="Pass")
        require(probe.metadata.get("lastActionSuccess") is True, "initial simulator Pass failed")
        targets = rank_visible_instance_ids(probe.instance_masks)
        required_targets = 2 if program in {"SPLIT", "REPLACE"} else 1
        require(len(targets) >= required_targets,
                "insufficient anonymous visible targets for %s" % program)
        targets = targets[:required_targets]
        initial_objects = {str(row["objectId"]): dict(row) for row in probe.metadata.get("objects", [])}
        event = probe
        for action in intervention_actions(program, -1, targets, initial_objects):
            event = controller.step(**action)
            actions.append(dict({"frame_index": -1, "success": event.metadata.get("lastActionSuccess")}, **action))
            require(event.metadata.get("lastActionSuccess") is True, "setup intervention failed")
        past_actions = []
        for frame_index in range(32):
            frame_actions = intervention_actions(program, frame_index, targets, initial_objects)
            for action in frame_actions:
                event = controller.step(**action)
                actions.append(dict({"frame_index": frame_index,
                                     "success": event.metadata.get("lastActionSuccess")}, **action))
                require(event.metadata.get("lastActionSuccess") is True,
                        "intervention failed at frame %s" % frame_index)
            agent_action, command = registered_agent_action(
                assignment["replicate"], frame_index
            )
            event = controller.step(**agent_action)
            require(event.metadata.get("lastActionSuccess") is True,
                    "registered agent action failed at frame %s" % frame_index)
            past_actions.append({
                "end_time_s": frame_index * 0.3, "command": command,
            })
            frames.append(capture_frame(event, public_directory, private_directory,
                                        frame_index, frame_actions, targets, past_actions))
            if directory_bytes(episode_root.parent) > family_byte_limit:
                raise ResourceStop("family byte limit exceeded")
        receipt = {
            "schema_version": "vsmt-vm04-two-house-raw-episode-v1",
            "episode_id": assignment["episode_id"], "family_id": assignment["family_id"],
            "slot": assignment["slot"], "attempted": True, "raw_complete": True,
            "frame_count": len(frames), "frames": frames,
            "intervention_count": len(actions),
            "registered_agent_action_count": len(past_actions),
            "registered_agent_action_policy": "alternating_quarter_degree_yaw_by_replicate",
            "public_target_selection_rule": "anonymous_mask_canonical_order",
            "wall_seconds": time.monotonic() - started,
        }
        write_new_json(episode_root / "raw.receipt.json", receipt)
        write_new_json(private_directory / "intervention.json", {
            "episode_id": assignment["episode_id"], "program": program,
            "replicate": assignment["replicate"], "target_instance_ids": targets,
            "actions": actions,
        })
        return receipt
    finally:
        controller.stop()


def main():
    import resource

    parser = argparse.ArgumentParser()
    parser.add_argument("--run-stage", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--family-id", required=True)
    parser.add_argument("--family-byte-limit", type=int, required=True)
    parser.add_argument("--process-address-limit", type=int, required=True)
    arguments = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (
        arguments.process_address_limit, arguments.process_address_limit,
    ))
    stage = arguments.run_stage.resolve()
    inventory = read_json(stage / "private/inventory.json")
    public_plan = read_json(stage / "public/episode_plan.json")
    private_plan = read_json(stage / "private/episode_plan.json")
    private_by_id = {
        row["episode_id"]: row for row in private_plan["assignments"]
        if row["family_id"] == arguments.family_id
    }
    public_rows = [row for row in public_plan["episodes"]
                   if row["family_id"] == arguments.family_id]
    require(len(public_rows) == len(private_by_id) == 18,
            "family worker must own exactly 18 slots")
    house_ids = {row["source_house_id"] for row in private_by_id.values()}
    require(len(house_ids) == 1, "family worker must own one source house")
    house_id = next(iter(house_ids))
    locator = next(row["source_locator"] for row in inventory["houses"]
                   if row["house_id"] == house_id)
    house = load_source_record(arguments.source_root, locator)
    family_root = stage / "execution" / arguments.family_id
    results = []
    ordered_rows = sorted(public_rows, key=lambda row: row["slot"])
    resource_stopped = False
    for row_index, public in enumerate(ordered_rows):
        private = private_by_id[public["episode_id"]]
        assignment = dict(private, slot=public["slot"])
        episode_root = family_root / "episodes" / public["episode_id"]
        episode_root.mkdir(parents=True)
        try:
            run_episode(house, assignment, episode_root, arguments.family_byte_limit)
            results.append({"episode_id": public["episode_id"], "status": "complete",
                            "receipt_sha256": sha256(episode_root / "raw.receipt.json")})
        except Exception as error:
            failure = {
                "schema_version": "vsmt-vm04-two-house-raw-episode-failure-v1",
                "episode_id": public["episode_id"], "family_id": arguments.family_id,
                "slot": public["slot"], "attempted": True, "raw_complete": False,
                "error_type": type(error).__name__, "error": str(error),
            }
            write_new_json(episode_root / "raw.failure.json", failure)
            results.append({"episode_id": public["episode_id"], "status": "failed",
                            "failure_sha256": sha256(episode_root / "raw.failure.json")})
            if isinstance(error, ResourceStop):
                resource_stopped = True
                for remaining in ordered_rows[row_index + 1:]:
                    remaining_root = family_root / "episodes" / remaining["episode_id"]
                    remaining_root.mkdir(parents=True)
                    not_started = {
                        "schema_version": "vsmt-vm04-two-house-raw-not-started-v1",
                        "episode_id": remaining["episode_id"],
                        "family_id": arguments.family_id, "slot": remaining["slot"],
                        "attempted": False, "raw_complete": False,
                        "reason": "family_resource_stop",
                    }
                    write_new_json(remaining_root / "raw.not-started.json", not_started)
                    results.append({
                        "episode_id": remaining["episode_id"], "status": "not_started",
                        "not_started_sha256": sha256(remaining_root / "raw.not-started.json"),
                    })
                break
    write_new_json(family_root / "worker.receipt.json", {
        "schema_version": "vsmt-vm04-two-house-family-worker-receipt-v1",
        "family_id": arguments.family_id, "source_house_id": house_id,
        "episode_count": 18, "episodes": results,
        "completed_count": sum(row["status"] == "complete" for row in results),
        "failed_count": sum(row["status"] == "failed" for row in results),
        "not_started_count": sum(row["status"] == "not_started" for row in results),
        "resource_stopped": resource_stopped,
        "family_bytes": directory_bytes(family_root), "success": True,
    })
    print("VM04_TWO_HOUSE_WORKER_OK family=%s slots=18" % arguments.family_id, flush=True)


if __name__ == "__main__":
    main()
