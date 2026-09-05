"""Run the CPMT single-room visual interface pilot.

This is a data/geometry/teacher audit, not the formal M1 comparison and not
Projective Node Orbit training.  It must run under Linux (WSL2 is supported)
because AI2-THOR 5.0 does not ship a native Windows platform build.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cpmt.visual_pilot import (  # noqa: E402
    backproject_image_point,
    execute_visual_candidates,
    make_visual_base,
    make_visual_programs,
    online_payload,
    project_world_point,
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def gpu_snapshot() -> dict[str, object]:
    command = [
        "nvidia-smi",
        "--query-gpu=name,memory.total,memory.used,driver_version",
        "--format=csv,noheader,nounits",
    ]
    try:
        completed = subprocess.run(
            command, check=True, capture_output=True, text=True, timeout=15
        )
        fields = [field.strip() for field in completed.stdout.splitlines()[0].split(",")]
        return {
            "name": fields[0],
            "memory_total_mib": int(fields[1]),
            "memory_used_mib": int(fields[2]),
            "driver_version": fields[3],
        }
    except (OSError, subprocess.SubprocessError, IndexError, ValueError) as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="CPMT single-room AI2-THOR visual interface pilot"
    )
    result.add_argument("--scene", default="FloorPlan1")
    result.add_argument("--width", type=int, default=480)
    result.add_argument("--height", type=int, default=320)
    result.add_argument("--output", type=Path)
    result.add_argument(
        "--build-cache",
        type=Path,
        default=Path(
            os.environ.get(
                "CPMT_AI2THOR_CACHE",
                str(Path.home() / ".cache" / "cpmt-ai2thor"),
            )
        ),
        help="keep the large Unity build on the Linux filesystem",
    )
    result.add_argument(
        "--render-platform",
        choices=("glx", "cloud"),
        default="glx",
        help="glx uses Linux64/WSLg; cloud uses Vulkan CloudRendering",
    )
    result.add_argument("--dry-run", action="store_true")
    result.add_argument(
        "--smoke-only",
        action="store_true",
        help="start one controller and save one RGB/depth/instance frame",
    )
    return result


def plain_position(value: object) -> dict[str, float]:
    if not isinstance(value, dict):
        raise TypeError(f"expected position mapping, got {type(value).__name__}")
    return {axis: float(value[axis]) for axis in ("x", "y", "z")}


def camera_from_event(event: object) -> dict[str, object]:
    metadata = event.metadata
    agent = metadata["agent"]
    position = metadata.get("cameraPosition") or agent["position"]
    return {
        "position": plain_position(position),
        "rotation": {
            axis: float(agent["rotation"].get(axis, 0.0))
            for axis in ("x", "y", "z")
        },
        "horizon": float(agent.get("cameraHorizon", 0.0)),
    }


def require_success(event: object, action: str) -> object:
    if not event.metadata.get("lastActionSuccess", False):
        message = event.metadata.get("errorMessage", "unknown simulator failure")
        raise RuntimeError(f"{action}: {message}")
    return event


def object_by_id(event: object, object_id: str) -> dict[str, object]:
    matches = [
        item
        for item in event.metadata.get("objects", [])
        if item.get("objectId") == object_id
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"expected target object {object_id!r} once, found {len(matches)}"
        )
    return matches[0]


def object_by_name(event: object, name: str) -> dict[str, object]:
    matches = [
        item
        for item in event.metadata.get("objects", [])
        if item.get("name") == name
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"expected target name {name!r} once, found {len(matches)}"
        )
    return matches[0]


def teleport(controller: object, pose: dict[str, object]) -> object:
    rotation = pose.get("rotation", 0.0)
    if isinstance(rotation, dict):
        rotation = rotation.get("y", 0.0)
    event = controller.step(
        action="TeleportFull",
        x=float(pose["x"]),
        y=float(pose["y"]),
        z=float(pose["z"]),
        rotation=float(rotation),
        horizon=float(pose.get("horizon", 0.0)),
        standing=bool(pose.get("standing", True)),
        forceAction=True,
    )
    return require_success(event, "TeleportFull")


def pose_from_event(event: object, *, yaw_delta: float = 0.0) -> dict[str, object]:
    agent = event.metadata["agent"]
    position = plain_position(agent["position"])
    return {
        **position,
        "rotation": (float(agent["rotation"]["y"]) + yaw_delta) % 360.0,
        "horizon": float(agent.get("cameraHorizon", 0.0)),
        "standing": bool(agent.get("isStanding", True)),
    }


def aligned_pose(
    poses: list[dict[str, object]], target_position: dict[str, float]
) -> dict[str, object]:
    """Choose a nearby pose whose yaw/horizon center the target."""

    def score(pose: dict[str, object]) -> tuple[float, float]:
        rotation = pose.get("rotation", 0.0)
        if isinstance(rotation, dict):
            rotation = rotation.get("y", 0.0)
        dx = target_position["x"] - float(pose["x"])
        dz = target_position["z"] - float(pose["z"])
        horizontal = math.hypot(dx, dz)
        desired_yaw = math.degrees(math.atan2(dx, dz)) % 360.0
        yaw_error = abs((float(rotation) - desired_yaw + 180.0) % 360.0 - 180.0)
        camera_height = float(pose["y"]) + (
            0.675 if bool(pose.get("standing", True)) else 0.45
        )
        desired_horizon = math.degrees(
            math.atan2(camera_height - target_position["y"], horizontal)
        )
        horizon_error = abs(float(pose.get("horizon", 0.0)) - desired_horizon)
        return (yaw_error + horizon_error + 2.0 * horizontal, horizontal)

    if not poses:
        raise RuntimeError("cannot align an empty interactable-pose set")
    return min(poses, key=score)


def target_region(
    event: object,
    object_id: str,
    *,
    width: int,
    height: int,
) -> list[dict[str, object]]:
    import numpy as np

    detection = event.instance_detections2D.get(object_id)
    mask = event.instance_masks.get(object_id)
    if detection is None or mask is None or not bool(np.any(mask)):
        return []
    x0, y0, x1, y1 = [float(value) for value in detection]
    valid_depth = np.asarray(event.depth_frame)[mask]
    valid_depth = valid_depth[np.isfinite(valid_depth) & (valid_depth > 0)]
    if valid_depth.size == 0:
        return []
    return [
        {
            "region_type": "target",
            "bbox": [x0 / width, y0 / height, x1 / width, y1 / height],
            "center": [((x0 + x1) / 2.0) / width, ((y0 + y1) / 2.0) / height],
            "depth": float(np.median(valid_depth)),
            "area_fraction": float(np.count_nonzero(mask)) / float(width * height),
        }
    ]


def save_frame(
    output: Path,
    label: str,
    event: object,
    object_id: str,
    *,
    evidence_ref: str,
    width: int,
    height: int,
) -> dict[str, object]:
    import numpy as np
    from PIL import Image

    frame_dir = output / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    rgb_ref = f"frames/{label}_rgb.png"
    depth_ref = f"frames/{label}_depth.npz"
    instance_ref = f"frames/{label}_instance.png"
    Image.fromarray(event.frame).save(output / rgb_ref)
    Image.fromarray(event.instance_segmentation_frame).save(output / instance_ref)
    np.savez_compressed(output / depth_ref, depth=event.depth_frame)
    target = object_by_id(event, object_id)
    regions = target_region(
        event, object_id, width=width, height=height
    )
    return {
        "evidence_ref": evidence_ref,
        "camera": camera_from_event(event),
        "regions": regions,
        "rgb_ref": rgb_ref,
        "depth_ref": depth_ref,
        "audit": {
            "instance_ref": instance_ref,
            "target_object_id": object_id,
            "target_name": target.get("name"),
            "target_type": target.get("objectType"),
            "metadata_visible": bool(target.get("visible")),
            "metadata_position": plain_position(target["position"]),
        },
    }


def online_view(view: dict[str, object]) -> dict[str, object]:
    return {key: deepcopy(value) for key, value in view.items() if key != "audit"}


def select_target(
    controller: object, *, width: int, height: int
) -> tuple[dict[str, object], dict[str, object]]:
    preferred = {
        name: index
        for index, name in enumerate(
            ("Apple", "Mug", "Bread", "Tomato", "Potato", "Cup", "Bowl", "Plate")
        )
    }
    objects = [
        item
        for item in controller.last_event.metadata.get("objects", [])
        if item.get("pickupable")
    ]
    objects.sort(
        key=lambda item: (
            not bool(item.get("visible")),
            preferred.get(str(item.get("objectType")), 999),
            str(item.get("name")),
        )
    )
    failures: list[str] = []
    evaluated: list[
        tuple[int, float, dict[str, object], dict[str, object]]
    ] = []
    for item in objects[:16]:
        event = controller.step(
            action="GetInteractablePoses",
            objectId=item["objectId"],
            horizons=[-30, 0, 30],
            rotations=list(range(0, 360, 45)),
            standings=[True],
        )
        if not event.metadata.get("lastActionSuccess", False):
            failures.append(
                f"{item.get('name')}: {event.metadata.get('errorMessage')}"
            )
            continue
        poses = list(event.metadata.get("actionReturn") or [])
        if poses:
            pose = aligned_pose(poses, plain_position(item["position"]))
            candidate_event = teleport(controller, pose)
            candidate = object_by_name(candidate_event, str(item["name"]))
            regions = target_region(
                candidate_event,
                str(candidate["objectId"]),
                width=width,
                height=height,
            )
            if not regions:
                continue
            region = regions[0]
            u, v = region["center"]
            margin = min(float(u), 1.0 - float(u), float(v), 1.0 - float(v))
            quality = 1000.0 * float(region["area_fraction"]) + 5.0 * margin
            evaluated.append(
                (
                    preferred.get(str(candidate.get("objectType")), 999),
                    quality,
                    candidate,
                    pose,
                )
            )
    if evaluated:
        _, _, candidate, pose = min(
            evaluated, key=lambda value: (value[0], -value[1])
        )
        return candidate, pose
    raise RuntimeError(
        "no pickupable object has an interactable pose; " + "; ".join(failures[:5])
    )


def choose_relocation(
    controller: object,
    target: dict[str, object],
    old_camera: dict[str, object],
    old_position: dict[str, float],
    *,
    width: int,
    height: int,
    fov: float,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    preferred = {
        name: index
        for index, name in enumerate(
            ("CounterTop", "DiningTable", "SideTable", "CoffeeTable", "Desk")
        )
    }
    receptacles = [
        item
        for item in controller.last_event.metadata.get("objects", [])
        if item.get("receptacle")
        and item.get("objectId") not in set(target.get("parentReceptacles") or [])
    ]
    receptacles.sort(
        key=lambda item: (
            preferred.get(str(item.get("objectType")), 999),
            str(item.get("name")),
        )
    )
    options: list[
        tuple[int, int, float, dict[str, object], dict[str, float]]
    ] = []
    for receptacle in receptacles[:20]:
        event = controller.step(
            action="GetSpawnCoordinatesAboveReceptacle",
            objectId=receptacle["objectId"],
            anywhere=True,
        )
        if not event.metadata.get("lastActionSuccess", False):
            continue
        for point_value in list(event.metadata.get("actionReturn") or [])[:100]:
            point = plain_position(point_value)
            distance = math.sqrt(
                sum((point[axis] - old_position[axis]) ** 2 for axis in ("x", "z"))
            )
            if distance < 0.75:
                continue
            projection = project_world_point(
                point,
                old_camera,
                width=width,
                height=height,
                fov_degrees=fov,
            )
            options.append(
                (
                    1 if str(receptacle.get("objectType")) in preferred else 0,
                    0 if bool(projection["visible"]) else 1,
                    distance,
                    receptacle,
                    point,
                )
            )
    options.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    if not options:
        raise RuntimeError("no valid relocation point at least 0.75 m away")

    target_name = str(target["name"])
    failures: list[str] = []
    for _, _, distance, receptacle, point in options[:300]:
        event = controller.step(
            action="PlaceObjectAtPoint",
            objectId=target["objectId"],
            position=point,
            forceKinematic=True,
        )
        if not event.metadata.get("lastActionSuccess", False):
            failures.append(str(event.metadata.get("errorMessage")))
            continue
        for _ in range(4):
            event = require_success(controller.step(action="Pass"), "Pass")
        moved = object_by_name(event, target_name)
        pose_event = controller.step(
            action="GetInteractablePoses",
            objectId=moved["objectId"],
            horizons=[-30, 0, 30],
            rotations=list(range(0, 360, 45)),
            standings=[True],
        )
        poses = list(pose_event.metadata.get("actionReturn") or [])
        if pose_event.metadata.get("lastActionSuccess", False) and poses:
            return (
                moved,
                aligned_pose(poses, plain_position(moved["position"])),
                {
                    "receptacle_object_id": receptacle["objectId"],
                    "receptacle_type": receptacle.get("objectType"),
                    "requested_point": point,
                    "horizontal_distance": distance,
                },
            )
    raise RuntimeError(
        "relocation placement/interactable-pose search failed: "
        + "; ".join(failures[:5])
    )


def inferred_point(
    view: dict[str, object], *, width: int, height: int, fov: float
) -> dict[str, float]:
    regions = view["regions"]
    if not regions:
        raise RuntimeError("a visible target region is required for backprojection")
    region = regions[0]
    return backproject_image_point(
        region["center"],
        float(region["depth"]),
        view["camera"],
        width=width,
        height=height,
        fov_degrees=fov,
    )


def run_case_audit(
    output: Path,
    case_id: str,
    *,
    known_target: bool,
    old_place: str,
    current_place: str,
    geometry: dict[str, dict[str, float]],
    current: dict[str, object],
    future: list[dict[str, object]],
    expected: str,
    width: int,
    height: int,
    fov: float,
    simulator_audit: dict[str, object],
) -> dict[str, object]:
    base = make_visual_base(
        case_id,
        known_target=known_target,
        old_place=old_place,
        current_place=current_place,
    )
    programs = make_visual_programs(
        case_id, base, current_place=current_place
    )
    current_online = online_view(current)
    future_online_shape = [online_view(item) for item in future]
    result = execute_visual_candidates(
        base,
        programs,
        geometry,
        current_online,
        future_online_shape,
        width=width,
        height=height,
        fov_degrees=fov,
    )
    case_dir = output / "cases" / case_id
    write_json(
        case_dir / "online.json",
        online_payload(case_id, base, programs, current_online, geometry),
    )
    write_json(
        case_dir / "audit.json",
        {
            "schema_version": "cpmt-visual-audit-0.1",
            "case_id": case_id,
            "expected_template": expected,
            "winner": result["winner"],
            "expected_match": result["winner"] == expected,
            "simulator_audit": simulator_audit,
            "future_views": future,
            "executed_candidate_audit": result,
        },
    )
    return {
        "case_id": case_id,
        "expected": expected,
        "winner": result["winner"],
        "expected_match": result["winner"] == expected,
        "online_ref": f"cases/{case_id}/online.json",
        "audit_ref": f"cases/{case_id}/audit.json",
    }


def make_output(requested: Path | None) -> tuple[str, Path]:
    run_id = "visual-pilot-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = requested or ROOT / "outputs" / "visual_pilot" / run_id
    output = output if output.is_absolute() else ROOT / output
    if not inside(output, ROOT / "outputs"):
        raise ValueError("output must be inside project outputs")
    if output.exists():
        raise FileExistsError(f"refusing to reuse output directory: {output}")
    return run_id, output


def main() -> int:
    args = parser().parse_args()
    checks = {
        "platform": platform.platform(),
        "python": sys.version,
        "linux": platform.system() == "Linux",
        "scene": args.scene,
        "render_platform": args.render_platform,
        "resolution": [args.width, args.height],
        "build_cache": str(args.build_cache),
        "gpu": gpu_snapshot(),
    }
    try:
        import ai2thor
        import numpy as np
        from PIL import Image

        checks["ai2thor"] = ai2thor.__version__
        checks["numpy"] = np.__version__
    except ImportError as exc:
        checks["dependency_error"] = f"{type(exc).__name__}: {exc}"

    if args.dry_run:
        print(json.dumps(checks, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if checks["linux"] and "dependency_error" not in checks else 2
    if not checks["linux"]:
        raise RuntimeError("AI2-THOR 5.0 visual pilot must run under Linux/WSL2")

    build_cache = args.build_cache.expanduser().resolve()
    if str(build_cache).startswith("/mnt/"):
        raise RuntimeError(
            "build cache must be on the Linux filesystem, not an NTFS /mnt path"
        )
    build_cache.mkdir(parents=True, exist_ok=True)

    run_id, output = make_output(args.output)
    output.mkdir(parents=True)
    manifest = {
        "schema_version": "cpmt-visual-pilot-0.1",
        "run_id": run_id,
        "stage": "M1-development-data-interface",
        "method": (
            "single_room_visual_smoke"
            if args.smoke_only
            else "three_case_executed_candidate_interface_audit"
        ),
        "status": "running",
        "scene_source": "iTHOR public built-in scene",
        "scene": args.scene,
        "render_platform": args.render_platform,
        "build_cache": str(build_cache),
        "host_safety": {
            "unity_build_on_linux_filesystem": True,
            "small_results_only_on_project_ntfs": True,
            "note": "two host 0x3B crashes require separate dump analysis",
        },
        "test_access": False,
        "online_future_access": False,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "failures": [],
    }
    write_json(output / "manifest.json", manifest)

    controller = None
    started = time.perf_counter()
    gpu_before = gpu_snapshot()
    try:
        from ai2thor.controller import Controller
        from ai2thor.platform import CloudRendering, Linux64
        import numpy as np
        from PIL import Image

        class ProjectController(Controller):
            @property
            def base_dir(self) -> str:
                return str(build_cache)

            def __init__(self, *controller_args: object, **controller_kwargs: object):
                try:
                    super().__init__(*controller_args, **controller_kwargs)
                except Exception:
                    # Controller construction can fail after Unity is spawned but
                    # before assignment in main.  Stop that partial server so a
                    # failed launch cannot poison the next GLX attempt.
                    try:
                        self.stop()
                    except Exception:
                        pass
                    raise

        launch_started = time.perf_counter()
        selected_platform = Linux64 if args.render_platform == "glx" else CloudRendering
        controller = ProjectController(
            platform=selected_platform,
            scene=args.scene,
            width=args.width,
            height=args.height,
            renderDepthImage=True,
            renderInstanceSegmentation=True,
            visibilityDistance=10.0,
            quality="Low",
            server_timeout=45.0,
            server_start_timeout=45.0,
        )
        launch_seconds = time.perf_counter() - launch_started
        event = controller.last_event
        require_success(event, "controller initialization")

        Image.fromarray(event.frame).save(output / "smoke_rgb.png")
        Image.fromarray(event.instance_segmentation_frame).save(
            output / "smoke_instance.png"
        )
        np.savez_compressed(output / "smoke_depth.npz", depth=event.depth_frame)
        smoke = {
            "scene_name": event.metadata.get("sceneName"),
            "agent": event.metadata.get("agent"),
            "fov": event.metadata.get("fov"),
            "frame_shape": list(event.frame.shape),
            "depth_shape": list(event.depth_frame.shape),
            "instance_shape": list(event.instance_segmentation_frame.shape),
            "visible_object_count": sum(
                bool(obj.get("visible")) for obj in event.metadata.get("objects", [])
            ),
            "object_count": len(event.metadata.get("objects", [])),
            "launch_seconds": launch_seconds,
            "step_seconds": [],
        }
        for action in ("RotateRight", "RotateLeft", "Pass"):
            step_started = time.perf_counter()
            result = controller.step(action=action)
            smoke["step_seconds"].append(time.perf_counter() - step_started)
            require_success(result, action)
        write_json(output / "smoke.json", smoke)

        if args.smoke_only:
            manifest.update(
                status="smoke_complete",
                ended_at=datetime.now(timezone.utc).isoformat(),
                wall_seconds=time.perf_counter() - started,
                resource={"gpu_before": gpu_before, "gpu_after": gpu_snapshot()},
                smoke_ref="smoke.json",
            )
        else:
            target, interactable_pose = select_target(
                controller, width=args.width, height=args.height
            )
            target_name = str(target["name"])
            manifest.update(
                target_type=target.get("objectType"),
                target_name=target_name,
            )
            write_json(output / "manifest.json", manifest)

            seen_event = teleport(controller, interactable_pose)
            seen_target = object_by_name(seen_event, target_name)
            seen = save_frame(
                output,
                "t0_seen",
                seen_event,
                str(seen_target["objectId"]),
                evidence_ref="obs:reappearance:t0",
                width=args.width,
                height=args.height,
            )
            if not seen["regions"]:
                raise RuntimeError("selected target produced no t0 region")
            old_pose = pose_from_event(seen_event)

            away_event = teleport(
                controller, pose_from_event(seen_event, yaw_delta=180.0)
            )
            away_target = object_by_name(away_event, target_name)
            away = save_frame(
                output,
                "t1_away",
                away_event,
                str(away_target["objectId"]),
                evidence_ref="obs:first-reveal:before",
                width=args.width,
                height=args.height,
            )
            if away["regions"]:
                raise RuntimeError("180-degree away view still contains target region")

            reappear_event = teleport(controller, old_pose)
            reappear_target = object_by_name(reappear_event, target_name)
            reappear = save_frame(
                output,
                "t2_reappear",
                reappear_event,
                str(reappear_target["objectId"]),
                evidence_ref="obs:reappearance:current",
                width=args.width,
                height=args.height,
            )
            if not reappear["regions"]:
                raise RuntimeError("target failed to reappear at the original pose")

            stable_event = require_success(controller.step(action="Pass"), "Pass")
            stable_target = object_by_name(stable_event, target_name)
            stable = save_frame(
                output,
                "t3_stable_revisit",
                stable_event,
                str(stable_target["objectId"]),
                evidence_ref="obs:reappearance:later",
                width=args.width,
                height=args.height,
            )
            if not stable["regions"]:
                raise RuntimeError("target disappeared before the stable revisit")

            fov = float(stable_event.metadata["fov"])
            old_position = plain_position(stable_target["position"])
            moved_target, new_pose, relocation_record = choose_relocation(
                controller,
                stable_target,
                seen["camera"],
                old_position,
                width=args.width,
                height=args.height,
                fov=fov,
            )

            relocation_event = teleport(controller, new_pose)
            moved_target = object_by_name(relocation_event, target_name)
            relocation_current = save_frame(
                output,
                "t4_relocated_current",
                relocation_event,
                str(moved_target["objectId"]),
                evidence_ref="obs:relocation-revisit:current",
                width=args.width,
                height=args.height,
            )
            if not relocation_current["regions"]:
                raise RuntimeError("relocated target has no current visible region")
            new_pose_exact = pose_from_event(relocation_event)

            old_revisit_event = teleport(controller, old_pose)
            old_revisit_target = object_by_name(old_revisit_event, target_name)
            old_revisit = save_frame(
                output,
                "t5_old_place_revisit",
                old_revisit_event,
                str(old_revisit_target["objectId"]),
                evidence_ref="obs:relocation-revisit:old-later",
                width=args.width,
                height=args.height,
            )
            if old_revisit["regions"]:
                raise RuntimeError(
                    "relocated target remains visible in the old-place revisit"
                )

            new_revisit_event = teleport(controller, new_pose_exact)
            new_revisit_target = object_by_name(new_revisit_event, target_name)
            new_revisit = save_frame(
                output,
                "t6_new_place_revisit",
                new_revisit_event,
                str(new_revisit_target["objectId"]),
                evidence_ref="obs:relocation-revisit:new-later",
                width=args.width,
                height=args.height,
            )
            if not new_revisit["regions"]:
                raise RuntimeError("relocated target failed the new-place revisit")

            old_inferred = inferred_point(
                seen, width=args.width, height=args.height, fov=fov
            )
            reappear_inferred = inferred_point(
                reappear, width=args.width, height=args.height, fov=fov
            )
            relocated_inferred = inferred_point(
                relocation_current,
                width=args.width,
                height=args.height,
                fov=fov,
            )

            frame_audit = {
                "target_initial": seen["audit"],
                "target_relocated": relocation_current["audit"],
                "relocation_action": relocation_record,
            }
            cases = [
                run_case_audit(
                    output,
                    "reappearance",
                    known_target=True,
                    old_place="place-old",
                    current_place="place-old",
                    geometry={"place-old": reappear_inferred},
                    current=reappear,
                    future=[stable],
                    expected="BIND",
                    width=args.width,
                    height=args.height,
                    fov=fov,
                    simulator_audit=frame_audit,
                ),
                run_case_audit(
                    output,
                    "first-reveal",
                    known_target=False,
                    old_place="place-current",
                    current_place="place-current",
                    geometry={"place-current": reappear_inferred},
                    current={
                        **reappear,
                        "evidence_ref": "obs:first-reveal:current",
                    },
                    future=[
                        {
                            **stable,
                            "evidence_ref": "obs:first-reveal:later",
                        }
                    ],
                    expected="BIRTH",
                    width=args.width,
                    height=args.height,
                    fov=fov,
                    simulator_audit={
                        **frame_audit,
                        "pre_reveal": away["audit"],
                    },
                ),
                run_case_audit(
                    output,
                    "relocation-revisit",
                    known_target=True,
                    old_place="place-old",
                    current_place="place-current",
                    geometry={
                        "place-old": old_inferred,
                        "place-current": relocated_inferred,
                    },
                    current=relocation_current,
                    future=[old_revisit, new_revisit],
                    expected="RELINK",
                    width=args.width,
                    height=args.height,
                    fov=fov,
                    simulator_audit=frame_audit,
                ),
            ]
            write_json(
                output / "case_summary.json",
                {
                    "schema_version": "cpmt-visual-summary-0.1",
                    "cases": cases,
                    "all_expected_match": all(
                        bool(item["expected_match"]) for item in cases
                    ),
                },
            )
            manifest.update(
                status=(
                    "interface_audit_complete"
                    if all(bool(item["expected_match"]) for item in cases)
                    else "interface_audit_complete_with_mismatch"
                ),
                ended_at=datetime.now(timezone.utc).isoformat(),
                wall_seconds=time.perf_counter() - started,
                resource={"gpu_before": gpu_before, "gpu_after": gpu_snapshot()},
                smoke_ref="smoke.json",
                case_summary_ref="case_summary.json",
                target_type=target.get("objectType"),
                target_name=target_name,
                fov=fov,
                geometry_source="current depth plus pose backprojection",
            )
    except Exception as exc:  # manifest must retain complete infrastructure failure
        manifest.update(
            status="failed",
            ended_at=datetime.now(timezone.utc).isoformat(),
            wall_seconds=time.perf_counter() - started,
            resource={"gpu_before": gpu_before, "gpu_after": gpu_snapshot()},
        )
        manifest["failures"].append(
            {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
        write_json(output / "manifest.json", manifest)
        print(output)
        return 1
    finally:
        if controller is not None:
            try:
                controller.stop()
            except Exception as stop_error:
                manifest["failures"].append(
                    {
                        "type": type(stop_error).__name__,
                        "message": f"controller.stop: {stop_error}",
                    }
                )
    write_json(output / "manifest.json", manifest)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
