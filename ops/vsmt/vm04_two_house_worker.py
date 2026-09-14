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


MINIMUM_ANONYMOUS_MASK_PIXELS = 196
CARDINAL_YAW_DEGREES = (0, 90, 180, 270)
_ASSET_ID_DATABASE = None


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


def _material_properties(value):
    if isinstance(value, str) and value:
        return {"name": value}
    require(isinstance(value, dict), "legacy material must be a string or object")
    return json.loads(json.dumps(value))


def upgrade_house_schema_v1(house, asset_id_database):
    """Upgrade a frozen ProcTHOR 0.0.1 record using the official 1.0.0 semantics."""

    source = json.loads(json.dumps(house))
    schema = source.get("metadata", {}).get("schema")
    require(schema in {"0.0.1", "1.0.0"}, "unsupported ProcTHOR house schema")
    if schema == "1.0.0":
        return source

    procedural = source["proceduralParameters"]
    ceiling = _material_properties(procedural["ceilingMaterial"])
    if procedural.get("ceilingColor"):
        ceiling["color"] = json.loads(json.dumps(procedural["ceilingColor"]))
    for legacy, current in (
        ("ceilingMaterialTilingXDivisor", "tilingDivisorX"),
        ("ceilingMaterialTilingYDivisor", "tilingDivisorY"),
    ):
        if procedural.get(legacy) is not None:
            ceiling[current] = procedural.pop(legacy)
    procedural["ceilingMaterial"] = ceiling

    for room in source["rooms"]:
        floor = _material_properties(room["floorMaterial"])
        if room.get("floorColor"):
            floor["color"] = room.pop("floorColor")
        for legacy, current in (
            ("floorMaterialTilingXDivisor", "tilingDivisorX"),
            ("floorMaterialTilingYDivisor", "tilingDivisorY"),
        ):
            if room.get(legacy) is not None:
                floor[current] = room.pop(legacy)
        room["floorMaterial"] = floor
        for ceiling_row in room.get("ceilings", []):
            if "materialProperties" in ceiling_row:
                ceiling_row["material"] = ceiling_row.pop("materialProperties")
            material = _material_properties(ceiling_row["material"])
            for legacy, current in (
                ("tilingDivisorX", "tilingDivisorX"),
                ("tilingDivisorY", "tilingDivisorY"),
            ):
                if ceiling_row.get(legacy) is not None:
                    material[current] = ceiling_row.pop(legacy)
            ceiling_row["material"] = material

    for wall in source["walls"]:
        if "materialProperties" in wall:
            wall["material"] = wall.pop("materialProperties")
        material = _material_properties(wall.get("material", {}))
        if wall.get("materialId"):
            material["name"] = wall.pop("materialId")
        if wall.get("color"):
            material["color"] = json.loads(json.dumps(wall["color"]))
        wall["material"] = material
        if str(wall["id"]).split("|")[1] == "exterior":
            wall["roomId"] = "exterior"

    for opening in source["windows"] + source["doors"]:
        if opening.get("color"):
            material = _material_properties(opening.get("material", {}))
            material["color"] = json.loads(json.dumps(opening["color"]))
            opening["material"] = material
        asset_id = opening["assetId"]
        require(asset_id in asset_id_database, "opening asset is missing from pinned database")
        asset_box = asset_id_database[asset_id]["boundingBox"]
        old_box = opening.pop("boundingBox")
        offset = opening.pop("assetOffset")
        opening["holePolygon"] = [old_box["min"], old_box["max"]]
        opening["assetPosition"] = {
            "x": old_box["min"]["x"] + offset["x"] + asset_box["x"] / 2.0,
            "y": old_box["min"]["y"] + offset["y"] + asset_box["y"] / 2.0,
            "z": 0,
        }

    for object_row in source["objects"]:
        if "materialProperties" in object_row:
            object_row["material"] = object_row.pop("materialProperties")
        if object_row.get("color"):
            material = _material_properties(object_row.get("material", {}))
            material["color"] = object_row.pop("color")
            object_row["material"] = material
    source["metadata"]["schema"] = "1.0.0"
    return source


def load_pinned_asset_id_database():
    global _ASSET_ID_DATABASE
    if _ASSET_ID_DATABASE is None:
        import procthor

        path = Path(procthor.__file__).resolve().parent / "databases" / "asset-database.json"
        require(path.is_file(), "pinned ProcTHOR asset database is missing")
        by_type = read_json(path)
        _ASSET_ID_DATABASE = {
            str(asset["assetId"]): asset
            for assets in by_type.values() for asset in assets
        }
    return _ASSET_ID_DATABASE


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
        if len(indices) < MINIMUM_ANONYMOUS_MASK_PIXELS:
            continue
        digest = hashlib.sha256(
            canonical_json([mask.shape[0], mask.shape[1]] + flat.astype(int).tolist()).encode(
                "utf-8"
            )
        ).hexdigest()
        ranked.append((int(indices[0]), int(len(indices)), digest, str(private_id)))
    ranked.sort()
    return [row[-1] for row in ranked]


def anonymous_mask_support(instance_masks):
    """Return ID-independent eligible-mask count and total pixel support."""

    import numpy as np

    eligible_pixels = []
    shape = None
    for raw in instance_masks.values():
        mask = np.asarray(raw, dtype=np.bool_)
        if mask.ndim != 2:
            continue
        shape = shape or tuple(mask.shape)
        require(tuple(mask.shape) == shape, "instance masks have inconsistent shapes")
        pixels = int(np.count_nonzero(mask))
        if pixels >= MINIMUM_ANONYMOUS_MASK_PIXELS:
            eligible_pixels.append(pixels)
    return len(eligible_pixels), sum(eligible_pixels)


def select_initial_viewpoint(candidates):
    """Select the frozen public start pose without using instance identities."""

    require(candidates, "no reachable viewpoint has two eligible anonymous masks")
    return min(candidates, key=lambda row: (
        -int(row["eligible_anonymous_mask_count"]),
        -int(row["total_eligible_anonymous_mask_pixels"]),
        float(row["position"]["x"]), float(row["position"]["y"]),
        float(row["position"]["z"]), int(row["rotation_y_degrees"]),
    ))


def discover_initial_viewpoint(controller):
    """Scan reachable positions once and return one anonymous-geometry pose."""

    reachable = controller.step(action="GetReachablePositions")
    require(reachable.metadata.get("lastActionSuccess") is True,
            "GetReachablePositions failed")
    raw_positions = reachable.metadata.get("actionReturn")
    require(isinstance(raw_positions, list) and raw_positions,
            "GetReachablePositions returned no positions")
    positions = sorted({
        (float(row["x"]), float(row["y"]), float(row["z"]))
        for row in raw_positions
        if isinstance(row, dict) and all(axis in row for axis in ("x", "y", "z"))
    })
    require(positions, "GetReachablePositions returned no valid positions")
    candidates = []
    for x, y, z in positions:
        for yaw in CARDINAL_YAW_DEGREES:
            event = controller.step(
                action="TeleportFull", x=x, y=y, z=z,
                rotation={"x": 0, "y": yaw, "z": 0}, horizon=0,
                standing=True, forceAction=True,
            )
            if event.metadata.get("lastActionSuccess") is not True:
                continue
            count, pixels = anonymous_mask_support(event.instance_masks)
            if count < 2:
                continue
            candidates.append({
                "position": {"x": x, "y": y, "z": z},
                "rotation_y_degrees": yaw, "horizon_degrees": 0,
                "standing": True,
                "eligible_anonymous_mask_count": count,
                "total_eligible_anonymous_mask_pixels": pixels,
            })
    return select_initial_viewpoint(candidates)


def make_controller(house):
    from ai2thor.controller import Controller
    from ai2thor.platform import CloudRendering

    upgraded_house = upgrade_house_schema_v1(house, load_pinned_asset_id_database())
    controller = Controller(
        platform=CloudRendering, scene=upgraded_house, width=224, height=224,
        renderDepthImage=True, renderInstanceSegmentation=True,
    )
    initial = controller.last_event
    if initial.metadata.get("lastActionSuccess") is not True:
        error = initial.metadata.get("errorMessage") or "unknown scene creation error"
        controller.stop()
        raise RuntimeError("initial ProcTHOR scene creation failed: %s" % error)
    if not initial.metadata.get("objects"):
        controller.stop()
        raise RuntimeError("initial ProcTHOR scene has no objects")
    return controller


def teleport_to_initial_viewpoint(controller, start_pose):
    position = start_pose["position"]
    return controller.step(
        action="TeleportFull", x=position["x"], y=position["y"], z=position["z"],
        rotation={"x": 0, "y": start_pose["rotation_y_degrees"], "z": 0},
        horizon=start_pose["horizon_degrees"], standing=start_pose["standing"],
        forceAction=True,
    )


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


def run_episode(house, assignment, episode_root, family_byte_limit, start_pose):
    program = assignment["program"]
    public_directory = episode_root / "public"
    private_directory = episode_root / "private"
    public_directory.mkdir(parents=True)
    private_directory.mkdir(parents=True)
    controller = make_controller(house)
    started = time.monotonic()
    frames, actions = [], []
    try:
        probe = teleport_to_initial_viewpoint(controller, start_pose)
        require(probe.metadata.get("lastActionSuccess") is True,
                "initial simulator TeleportFull failed")
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
            "initial_viewpoint": start_pose,
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
    start_pose = None
    start_pose_error = None
    search_controller = make_controller(house)
    try:
        start_pose = discover_initial_viewpoint(search_controller)
    except Exception as error:
        start_pose_error = "%s: %s" % (type(error).__name__, error)
    finally:
        search_controller.stop()
    if start_pose is not None:
        write_new_json(family_root / "initial_viewpoint.receipt.json", {
            "schema_version": "vsmt-vm04-two-house-initial-viewpoint-v1",
            "family_id": arguments.family_id,
            "selection_rule": (
                "maximize_eligible_mask_count_then_total_eligible_pixels_then_"
                "lexicographic_x_y_z_yaw"
            ),
            "pose": start_pose, "success": True,
        })
    results = []
    ordered_rows = sorted(public_rows, key=lambda row: row["slot"])
    resource_stopped = False
    for row_index, public in enumerate(ordered_rows):
        private = private_by_id[public["episode_id"]]
        assignment = dict(private, slot=public["slot"])
        episode_root = family_root / "episodes" / public["episode_id"]
        episode_root.mkdir(parents=True)
        try:
            require(start_pose_error is None, "initial viewpoint search failed: %s" % start_pose_error)
            run_episode(
                house, assignment, episode_root, arguments.family_byte_limit, start_pose,
            )
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
        "initial_viewpoint_search_succeeded": start_pose is not None,
        "initial_viewpoint_receipt_sha256": (
            sha256(family_root / "initial_viewpoint.receipt.json")
            if start_pose is not None else None
        ),
        "family_bytes": directory_bytes(family_root), "success": True,
    })
    print("VM04_TWO_HOUSE_WORKER_OK family=%s slots=18" % arguments.family_id, flush=True)


if __name__ == "__main__":
    main()
