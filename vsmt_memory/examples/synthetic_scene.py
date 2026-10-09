"""Minimal example: the memory on a synthetic RGB-D stream given in the OpenCV/ROS convention.

A camera in a box-shaped room (world +z up, as in ROS) turns twice on the spot.  Between the two turns, while nothing
is observed, one box is removed and another is moved.  Frames are 320 x 240 (resized to 224 x 224 by the front end),
depth is metric z-depth, and the instance masks come from the renderer.  The example prints the atoms of every frame
and the final entity table, and reports what became of the entities that carried the removed and the moved box.

The scene is not ProcTHOR and its textures are synthetic: the trained cost heads have never seen anything like it, so
the output shows how the interface is used, not how well the method works here.

Run from the repository root (downloads about 100 MB of weights and 346 MB of DINOv2 on the first run):

    python -m vsmt_memory.examples.synthetic_scene
"""

from __future__ import annotations

import argparse
import math
from collections import Counter
from dataclasses import dataclass

import numpy as np

from vsmt_memory import CameraIntrinsics, CameraPose, VSMTMemory

WIDTH, HEIGHT = 320, 240
INTRINSICS = CameraIntrinsics(fx=160.0, fy=160.0, cx=159.5, cy=119.5, width=WIDTH, height=HEIGHT)
ROOM_HALF_M, ROOM_HEIGHT_M = 3.0, 2.6


@dataclass(frozen=True)
class Box:
    name: str
    centre: tuple[float, float, float]
    size: tuple[float, float, float]
    colour: tuple[int, int, int]
    pattern: str


FIRST_VISIT = [
    Box("red crate", (1.6, 0.8, 0.25), (0.5, 0.5, 0.5), (200, 40, 40), "stripes"),
    Box("blue cabinet", (-1.2, 1.9, 0.45), (0.8, 0.5, 0.9), (40, 70, 200), "dots"),
    Box("green bin", (0.9, -1.7, 0.2), (0.4, 0.4, 0.4), (40, 170, 60), "noise"),
    Box("yellow table", (-1.8, -1.0, 0.375), (1.0, 0.7, 0.75), (220, 200, 50), "rings"),
]
SECOND_VISIT = [FIRST_VISIT[1], FIRST_VISIT[3],  # red crate removed, green bin moved
                Box("green bin", (-0.4, -2.1, 0.2), (0.4, 0.4, 0.4), (40, 170, 60), "noise")]


def texture(pattern: str, points: np.ndarray) -> np.ndarray:
    """A brightness factor in [0.4, 1] per point, so that objects differ in texture as well as colour."""

    x, y, z = points[..., 0], points[..., 1], points[..., 2]
    if pattern == "stripes":
        value = np.sin(z * 50.0) > 0
    elif pattern == "dots":
        value = (np.sin(x * 35.0) * np.sin(y * 35.0) * np.sin(z * 35.0)) > 0.25
    elif pattern == "noise":
        cells = np.floor(points * 25.0).astype(np.int64)
        value = ((cells[..., 0] * 73856093) ^ (cells[..., 1] * 19349663) ^ (cells[..., 2] * 83492791)) % 3 == 0
    elif pattern == "rings":
        value = np.sin(np.hypot(x + 1.8, y + 1.0) * 60.0) > 0.4
    elif pattern == "checker":
        value = (np.floor(x * 2) + np.floor(y * 2)) % 2 == 0
    else:  # plain
        return np.full(x.shape, 0.9)
    return np.where(value, 1.0, 0.4)


def camera_pose_opencv(yaw: float, pitch: float = math.radians(-25.0), height: float = 1.3) -> np.ndarray:
    """A 4x4 world-from-camera transform: OpenCV camera (+x right, +y down, +z forward), ROS world (+z up)."""

    forward = np.array([math.cos(yaw) * math.cos(pitch), math.sin(yaw) * math.cos(pitch), math.sin(pitch)])
    right = np.cross(forward, [0.0, 0.0, 1.0])
    right /= np.linalg.norm(right)
    down = np.cross(forward, right)
    transform = np.eye(4)
    transform[:3, :3] = np.column_stack([right, down, forward])
    transform[:3, 3] = [0.0, 0.0, height]
    return transform


def render(boxes: list[Box], world_from_camera: np.ndarray) -> tuple[np.ndarray, np.ndarray, list[np.ndarray], list[str]]:
    """Ray-cast RGB, z-depth, one mask per visible surface (floor, ceiling, walls, boxes) and the surface names."""

    u, v = np.meshgrid(np.arange(WIDTH), np.arange(HEIGHT))
    rays = np.stack([(u - INTRINSICS.cx) / INTRINSICS.fx, (v - INTRINSICS.cy) / INTRINSICS.fy, np.ones_like(u, float)], -1)
    direction = rays @ world_from_camera[:3, :3].T  # unnormalised: the hit distance along it is the z-depth
    origin = world_from_camera[:3, 3]
    depth = np.full((HEIGHT, WIDTH), np.inf)
    label = np.full((HEIGHT, WIDTH), -1)
    normal = np.zeros((HEIGHT, WIDTH, 3))
    surfaces: list[tuple[str, tuple[int, int, int], str]] = []

    def hit(t: np.ndarray, n: np.ndarray, colour: tuple[int, int, int], name: str, pattern: str) -> None:
        closer = (t > 1e-6) & (t < depth)
        depth[closer] = t[closer]
        label[closer] = len(surfaces)
        normal[closer] = n[closer] if n.ndim == 3 else n
        surfaces.append((name, colour, pattern))

    planes = [("floor", 2, 0.0, (150, 140, 130), "checker"), ("ceiling", 2, ROOM_HEIGHT_M, (235, 235, 235), "plain"),
              ("wall +x", 0, ROOM_HALF_M, (190, 180, 200), "plain"), ("wall -x", 0, -ROOM_HALF_M, (180, 200, 190), "plain"),
              ("wall +y", 1, ROOM_HALF_M, (200, 190, 170), "plain"), ("wall -y", 1, -ROOM_HALF_M, (170, 180, 205), "plain")]
    for name, axis, offset, colour, pattern in planes:
        with np.errstate(divide="ignore", invalid="ignore"):
            t = (offset - origin[axis]) / direction[..., axis]
        n = np.zeros(3)
        n[axis] = 1.0
        hit(np.where(np.isfinite(t), t, np.inf), n, colour, name, pattern)
    for box in boxes:
        lower = np.asarray(box.centre) - np.asarray(box.size) / 2
        upper = np.asarray(box.centre) + np.asarray(box.size) / 2
        with np.errstate(divide="ignore", invalid="ignore"):
            t1, t2 = (lower - origin) / direction, (upper - origin) / direction
        near, far = np.minimum(t1, t2), np.maximum(t1, t2)
        t_enter, t_exit = near.max(-1), far.min(-1)
        t = np.where((t_enter <= t_exit) & (t_exit > 0), t_enter, np.inf)
        n = np.zeros((HEIGHT, WIDTH, 3))
        n[np.arange(HEIGHT)[:, None], np.arange(WIDTH)[None, :], near.argmax(-1)] = 1.0
        hit(t, n, box.colour, box.name, box.pattern)

    light = np.abs(normal @ np.array([0.3, 0.5, 0.8])) * 0.5 + 0.5
    points = origin + direction * depth[..., None]
    shade = np.ones((HEIGHT, WIDTH))
    for index, (_, _, pattern) in enumerate(surfaces):
        own = label == index
        shade[own] = texture(pattern, points[own])
    colours = np.array([c for _, c, _ in surfaces], float)[label]
    rgb = np.clip(colours * (light * shade)[..., None], 0, 255).astype(np.uint8)
    masks = [label == index for index in range(len(surfaces)) if (label == index).any()]
    names = [surfaces[index][0] for index in range(len(surfaces)) if (label == index).any()]
    return rgb, depth.astype(np.float32), masks, names


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--frames-per-turn", type=int, default=24)
    parser.add_argument("--seed", type=int, default=7, help="which of the five released training seeds to load")
    args = parser.parse_args()

    memory = VSMTMemory.from_pretrained(front_end="sam2", seed=args.seed)
    carriers: dict[tuple[int, str], set[str]] = {}  # (visit, surface name) -> entities its masks were attached to
    for visit, boxes in enumerate((FIRST_VISIT, SECOND_VISIT), start=1):
        for step in range(args.frames_per_turn):
            transform = camera_pose_opencv(2 * math.pi * step / args.frames_per_turn)
            rgb, depth, masks, names = render(boxes, transform)
            result = memory.step(rgb, depth, INTRINSICS, CameraPose.from_opencv(transform, world_up="z"), masks)
            for op in result.program:
                if op.mask_index is not None:
                    carriers.setdefault((visit, names[op.mask_index]), set()).add(op.entity_id)
            atoms = Counter(op.atom for op in result.program)
            note = f" (skipped: {result.skipped_reason})" if result.skipped_reason else ""
            print(f"visit {visit} frame {result.tick:3d}: " + ", ".join(f"{k} {v}" for k, v in sorted(atoms.items())) + note)

    # what became of each box: map every carrier through the deduplication, then read its final state
    states = {entity.entity_id: entity for entity in memory.entities()}
    final = {key: {memory.resolve(e) for e in ids} - {None} for key, ids in carriers.items()}
    print("\nfinal entities:", dict(Counter(entity.state for entity in states.values())))
    removed = final.get((1, "red crate"), set())
    print("red crate (removed between the turns): carried by " + ", ".join(
        f"{e[:16]} now {states[e].state}" for e in sorted(removed)) + " -> " +
        ("retracted" if removed and all(states[e].state == "retracted" for e in removed) else "NOT retracted"))
    before, after = final.get((1, "green bin"), set()), final.get((2, "green bin"), set())
    print("green bin (moved between the turns): " +
          ("identity kept (the same entity carried it before and after the move)" if before & after
           else "identity NOT kept (new or other entity after the move)"))
    shared = sorted({name for (_, name), ids in final.items() for (_, other), more in final.items()
                     if name != other and ids & more and "wall" not in name + other and "floor" not in name + other})
    if shared:
        print("surfaces bound to a common entity at some point: " + ", ".join(shared))
    print("\nThis synthetic scene is outside the training distribution (ProcTHOR); see docs/PLUGIN.md, Scope.")


if __name__ == "__main__":
    main()
