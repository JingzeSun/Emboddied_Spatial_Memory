"""D-224 / S1-02 R1: the coverage-revisit route planner, as a pure function.

Everything here is arithmetic on a reachable set the generator already
holds.  No simulator is imported or started.  The planner turns (house
start pose, reachable positions, eligible containers, the interventions
chosen for the window) into one registered action sequence and the frame
bookkeeping the generator needs to know which frames are sweep one, the
transition and sweep two.

白话：这个模块解决"给定这栋房子能走的格子和要看的容器，走哪条路、在哪转身、
在哪抬头"。输入是起始位姿、可达位置、合格容器的中心点和本次要重访的容器；输出
是一串登记好的动作，以及每段（扫掠一／过渡／扫掠二）对应的观察序号范围。例如
三个容器分别在客厅、厨房、卧室，输出就是从起点依次走到三个视点并注视、再走一
段过渡、再回到被干预的那两个视点的动作序列。它不启动模拟器、不看图像、不知道
哪个物体会被干预（那是选择器的事），也不保证视点真的看得清。

The rules bound by the S0-02 contract:

* coverage is over eligible containers, not space;
* a viewpoint is the nearest admissible grid cell within the registered
  distance range whose best yaw/pitch puts the container centre in the
  90-degree frustum, ties broken by grid order;
* the tour is nearest-neighbour with grid-order tie-break, no local search;
* paths are BFS shortest paths with grid-order tie-break, encoded as turn
  then MoveAhead, never strafing;
* move interventions revisit both source and destination, in the order
  the caller supplies (drawn from the seeded RNG by the selector);
* exceeding the action cap raises, it never truncates.
"""

from __future__ import annotations

import math
from collections import deque
from typing import Any, Iterable, Mapping, Sequence

from vsmt.lean_intervention import (
    MAXIMUM_ACTIONS,
    VIEWPOINT_DISTANCE_M,
    VIEWPOINT_PITCH_OPTIONS,
)


GRID_M = 0.25
TURN_DEGREES = 90
LOOK_DEGREES = 30
HALF_FOV_DEGREES = 45.0  # square 224 px image, 90 degree field of view

#: yaw -> unit step on the grid.  AI2-THOR: yaw 0 faces +z, 90 faces +x.
_HEADING = {0: (0, 1), 90: (1, 0), 180: (0, -1), 270: (-1, 0)}


class LeanRouteError(ValueError):
    """Raised when no admissible route exists or the action cap would be hit."""


# --------------------------------------------------------------------------
# grid
# --------------------------------------------------------------------------

def snap(value: float, grid: float = GRID_M) -> int:
    """Snap a metre coordinate to an integer grid index."""

    return int(round(value / grid))


def reachable_cells(positions: Iterable[Mapping[str, float]], grid: float = GRID_M) -> set[tuple[int, int]]:
    """Snap reachable positions to (ix, iz) grid cells.

    白话：输入模拟器给的可达位置，输出吸附到 0.25 m 网格后的整数格子集合。例如
    (1.02, 0.95, 2.48) 变成 (4, 10)。y 被丢掉——路线在一层平面上。
    """

    return {(snap(p["x"], grid), snap(p["z"], grid)) for p in positions}


def neighbours(cell: tuple[int, int]) -> list[tuple[int, int]]:
    ix, iz = cell
    return [(ix, iz + 1), (ix + 1, iz), (ix, iz - 1), (ix - 1, iz)]


Edge = frozenset  # an undirected grid edge: frozenset({cell_a, cell_b})


def edge(a: tuple[int, int], b: tuple[int, int]) -> frozenset:
    return frozenset((a, b))


def bfs_path(cells: set[tuple[int, int]], start: tuple[int, int],
             goal: tuple[int, int], blocked: frozenset | set = frozenset()) -> list[tuple[int, int]]:
    """Shortest grid path from start to goal, ties broken by grid order.

    白话：在可达格子上找最短路。并列时按 (ix, iz) 的字典序展开，因此同一对起
    终点在任何机器上得到同一条路。找不到就报错，不绕行、不猜。`blocked` 是执行中
    被模拟器拒绝过的格间边（例如两格之间有把椅子），带着它重算就是绕行——绕行本
    身也是确定性的，因为拒绝是模拟器对同一 house 的确定答案。
    """

    if start not in cells or goal not in cells:
        raise LeanRouteError("bfs_endpoint_not_reachable")
    if start == goal:
        return [start]
    parent: dict[tuple[int, int], tuple[int, int]] = {start: start}
    queue: deque[tuple[int, int]] = deque([start])
    while queue:
        here = queue.popleft()
        for nxt in sorted(neighbours(here)):
            if nxt in cells and nxt not in parent and edge(here, nxt) not in blocked:
                parent[nxt] = here
                if nxt == goal:
                    path = [goal]
                    while path[-1] != start:
                        path.append(parent[path[-1]])
                    return list(reversed(path))
                queue.append(nxt)
    raise LeanRouteError("bfs_no_path")


# --------------------------------------------------------------------------
# viewpoints
# --------------------------------------------------------------------------

def _bearing_degrees(dx: float, dz: float) -> float:
    """AI2-THOR yaw that faces (dx, dz): 0 -> +z, 90 -> +x."""

    return math.degrees(math.atan2(dx, dz)) % 360.0


def _angular_distance(a: float, b: float) -> float:
    d = abs((a - b + 180.0) % 360.0 - 180.0)
    return d


def best_yaw(dx: float, dz: float) -> tuple[int, float]:
    """The registered yaw closest to the bearing, and the residual error."""

    bearing = _bearing_degrees(dx, dz)
    yaw = min((0, 90, 180, 270), key=lambda y: (_angular_distance(y, bearing), y))
    return yaw, _angular_distance(yaw, bearing)


def best_pitch(elevation_degrees: float) -> tuple[int, float]:
    """The registered horizon that best centres the elevation, and the residual.

    AI2-THOR horizon is positive looking down, so the central ray sits at
    -horizon elevation and the residual is |elevation + horizon|.
    """

    pitch = min(VIEWPOINT_PITCH_OPTIONS, key=lambda p: (abs(elevation_degrees + p), p))
    return pitch, abs(elevation_degrees + pitch)


def admissible_viewpoints(
    container_center: Mapping[str, float], cells: set[tuple[int, int]],
    *, camera_height_m: float, grid: float = GRID_M,
) -> list[dict[str, Any]]:
    """All (cell, yaw, pitch) from which the container centre is in the frustum.

    白话：输入容器中心和可达格子，输出所有能把容器中心放进 90° 视锥的视点，每个
    视点带距离、最佳朝向与俯仰。距离只在 [0.75, 2.5] m 之间找；朝向从四个 90° 档
    里挑最接近的，水平误差 > 45° 就不算；俯仰从 −30/0/30 里挑最接近的，竖直误差
    > 45° 也不算。它不检查中间有没有墙挡着——那要靠真实深度帧判定。
    """

    low, high = VIEWPOINT_DISTANCE_M
    out: list[dict[str, Any]] = []
    cx, cy, cz = container_center["x"], container_center["y"], container_center["z"]
    for cell in sorted(cells):
        px, pz = cell[0] * grid, cell[1] * grid
        dx, dz = cx - px, cz - pz
        horizontal = math.hypot(dx, dz)
        if horizontal < low or horizontal > high:
            continue
        yaw, yaw_err = best_yaw(dx, dz)
        if yaw_err > HALF_FOV_DEGREES:
            continue
        elevation = math.degrees(math.atan2(cy - camera_height_m, horizontal))
        pitch, pitch_err = best_pitch(elevation)
        if pitch_err > HALF_FOV_DEGREES:
            continue
        out.append({"cell": cell, "yaw": yaw, "pitch": pitch,
                    "distance_m": round(horizontal, 4)})
    return out


def select_viewpoint(container_center: Mapping[str, float], cells: set[tuple[int, int]],
                     *, camera_height_m: float, grid: float = GRID_M,
                     component: set[tuple[int, int]] | None = None) -> dict[str, Any]:
    """The nearest admissible viewpoint, ties broken by grid order.

    ``component`` restricts the candidates to cells the agent can still reach (see
    :func:`reachable_component`); ``None`` means every reachable cell is a candidate.
    """

    candidates = admissible_viewpoints(container_center, cells,
                                       camera_height_m=camera_height_m, grid=grid)
    if component is not None:
        candidates = [v for v in candidates if v["cell"] in component]
    if not candidates:
        raise LeanRouteError("no_admissible_viewpoint")
    return min(candidates, key=lambda v: (v["distance_m"], v["cell"]))


def reachable_component(cells: set[tuple[int, int]], start: tuple[int, int],
                        blocked: frozenset | set = frozenset()) -> set[tuple[int, int]]:
    """Every cell reachable from ``start`` without crossing a blocked edge.

    白话：被模拟器拒绝过的格间边可能把一个视点格从当前位置"割开"（例如视点在椅
    子后面的死角）。这个函数从当前格出发做一次 BFS，返回带着黑名单还走得到的全部
    格子；`select_viewpoint(..., component=...)` 只在这些格子里选视点，因此重选出的
    视点仍是"最近的可达合格视点"，规则不变，只是把"可达"从事先全知改成带着实测黑
    名单算。它不删黑名单、不猜边是否真的能走。
    """

    if start not in cells:
        raise LeanRouteError("bfs_endpoint_not_reachable")
    seen = {start}
    queue: deque[tuple[int, int]] = deque([start])
    while queue:
        here = queue.popleft()
        for nxt in sorted(neighbours(here)):
            if nxt in cells and nxt not in seen and edge(here, nxt) not in blocked:
                seen.add(nxt)
                queue.append(nxt)
    return seen


# --------------------------------------------------------------------------
# tour and encoding
# --------------------------------------------------------------------------

def nearest_neighbour_tour(start: tuple[int, int], targets: Sequence[tuple[int, int]]) -> list[int]:
    """Visit order of targets by nearest-neighbour from start, grid-order tie-break.

    白话：从起点出发，每次去最近的未访问目标（曼哈顿距离），并列取格子序小的。
    不做任何事后优化，因此顺序是输入的纯函数。返回目标的下标顺序。
    """

    remaining = list(range(len(targets)))
    here = start
    order: list[int] = []
    while remaining:
        nxt = min(remaining, key=lambda i: (abs(targets[i][0] - here[0]) + abs(targets[i][1] - here[1]),
                                            targets[i]))
        order.append(nxt)
        remaining.remove(nxt)
        here = targets[nxt]
    return order


def turn_actions(from_yaw: int, to_yaw: int) -> list[str]:
    """Minimal 90-degree turns from one registered yaw to another."""

    delta = (to_yaw - from_yaw) % 360
    if delta == 0:
        return []
    if delta == 90:
        return ["RotateRight"]
    if delta == 270:
        return ["RotateLeft"]
    return ["RotateRight", "RotateRight"]


def look_actions(from_pitch: int, to_pitch: int) -> list[str]:
    steps = (to_pitch - from_pitch) // LOOK_DEGREES
    return ["LookDown"] * steps if steps > 0 else ["LookUp"] * (-steps)


def encode_path(path: Sequence[tuple[int, int]], start_yaw: int) -> tuple[list[str], int]:
    """Turn a cell path into turn-then-MoveAhead actions; returns the final yaw."""

    actions: list[str] = []
    yaw = start_yaw
    for a, b in zip(path, path[1:]):
        step = (b[0] - a[0], b[1] - a[1])
        target_yaw = next(y for y, h in _HEADING.items() if h == step)
        actions.extend(turn_actions(yaw, target_yaw))
        yaw = target_yaw
        actions.append("MoveAhead")
    return actions, yaw


# --------------------------------------------------------------------------
# the route
# --------------------------------------------------------------------------

def plan_route(
    *,
    reachable: Iterable[Mapping[str, float]],
    start_pose: Mapping[str, Any],
    camera_height_m: float,
    containers: Mapping[str, Mapping[str, float]],
    revisit_sequence: Sequence[str],
    transition_cell: tuple[int, int] | None = None,
    grid: float = GRID_M,
    max_actions: int = MAXIMUM_ACTIONS,
    blocked: frozenset | set = frozenset(),
) -> dict[str, Any]:
    """Plan sweep one, the transition and sweep two as one action sequence.

    白话：输入起始位姿、可达位置、合格容器（id → 中心）、扫掠二要按顺序重访的
    容器 id 列表（由选择器给出，move 的源与目标都在里面且顺序已由 RNG 决定），可
    选一个过渡段要去的格子；输出动作序列与三段的观察序号范围。观察序号 0 是起
    点，之后每个动作产生一个观察。动作总数超过登记上限（裁决 40 后为 4000）直接报错，不截断。
    """

    cells = reachable_cells(reachable, grid)
    start_cell = (snap(start_pose["position"]["x"], grid), snap(start_pose["position"]["z"], grid))
    if start_cell not in cells:
        raise LeanRouteError("start_pose_not_on_reachable_grid")
    yaw = int(round(start_pose["rotation"]["y"])) % 360
    if yaw not in _HEADING:
        raise LeanRouteError("start_yaw_not_registered")
    pitch = int(round(start_pose.get("horizon", 0)))

    viewpoints = {cid: select_viewpoint(center, cells, camera_height_m=camera_height_m, grid=grid)
                  for cid, center in containers.items()}
    ids = sorted(viewpoints)
    order = nearest_neighbour_tour(start_cell, [viewpoints[c]["cell"] for c in ids])

    actions: list[str] = []
    segments: dict[str, list[int]] = {}
    here = start_cell

    def visit(cid: str) -> None:
        nonlocal here, yaw, pitch
        vp = viewpoints[cid]
        path = bfs_path(cells, here, vp["cell"], blocked)
        moved, yaw = encode_path(path, yaw)
        actions.extend(moved)
        actions.extend(turn_actions(yaw, vp["yaw"]))
        yaw = vp["yaw"]
        actions.extend(look_actions(pitch, vp["pitch"]))
        pitch = vp["pitch"]
        here = vp["cell"]

    first = len(actions)
    for index in order:
        visit(ids[index])
    segments["sweep_one"] = [first, len(actions)]

    first = len(actions)
    if transition_cell is not None:
        path = bfs_path(cells, here, transition_cell, blocked)
        moved, yaw = encode_path(path, yaw)
        actions.extend(moved)
        here = transition_cell
    segments["transition"] = [first, len(actions)]

    first = len(actions)
    for cid in revisit_sequence:
        if cid not in viewpoints:
            raise LeanRouteError(f"revisit_target_has_no_viewpoint:{cid}")
        visit(cid)
    segments["sweep_two"] = [first, len(actions)]

    if len(actions) > max_actions:
        raise LeanRouteError(f"route_cap_hit:planned={len(actions)}:cap={max_actions}")
    return {
        "actions": actions,
        "observation_count": len(actions) + 1,
        "segments": segments,
        "viewpoints": {cid: dict(viewpoints[cid], cell=list(viewpoints[cid]["cell"])) for cid in ids},
        "sweep_one_order": [ids[i] for i in order],
        "revisit_sequence": list(revisit_sequence),
        "start_cell": list(start_cell),
        "blocked_edges": sorted([list(c) for c in sorted(e)] for e in blocked),
    }


__all__ = [
    "GRID_M",
    "HALF_FOV_DEGREES",
    "LeanRouteError",
    "admissible_viewpoints",
    "best_pitch",
    "best_yaw",
    "bfs_path",
    "edge",
    "encode_path",
    "look_actions",
    "nearest_neighbour_tour",
    "plan_route",
    "reachable_cells",
    "reachable_component",
    "select_viewpoint",
    "snap",
    "turn_actions",
]
