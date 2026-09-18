"""Public-only route planning helpers for the D-212 two-house engineering run.

The planner consumes a sealed ``GetReachablePositions`` grid.  It does not
consume simulator object identities, instance masks, a teacher transaction, or
the result of a later raw episode.  Route-specific RGB-D evidence is attached
only after one deterministic route has been selected; a failed survey is kept
as a failure and is never replaced by another template.
"""

from __future__ import annotations

from collections import deque
import hashlib
import math
from typing import Any, Mapping, Sequence

from cpmt.hashing import canonical_json

from .d210_place_memory import build_route_plan
from .d211_p0_smoke import (
    D211Error,
    seal_public_route_evidence,
    seal_route_execution_binding,
    seal_scenario_receipt,
    validate_d211_contract,
    validate_reachable_scan,
)


class D212RouteSurveyError(D211Error):
    """A fixed public route cannot be constructed or surveyed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise D212RouteSurveyError(message)


def _inverse(actions: Sequence[str]) -> list[str]:
    inverse = {
        "MoveAhead": "MoveBack", "MoveBack": "MoveAhead",
        "MoveLeft": "MoveRight", "MoveRight": "MoveLeft",
        "RotateLeft": "RotateRight", "RotateRight": "RotateLeft",
        "LookUp": "LookDown", "LookDown": "LookUp",
    }
    return [inverse[name] for name in reversed(actions)]


def _advance(cell: tuple[int, int], yaw_quarters: int,
             action: str) -> tuple[tuple[int, int], int]:
    yaw_quarters %= 4
    if action == "RotateLeft":
        return cell, (yaw_quarters - 1) % 4
    if action == "RotateRight":
        return cell, (yaw_quarters + 1) % 4
    forward = ((0, 1), (1, 0), (0, -1), (-1, 0))[yaw_quarters]
    right = (forward[1], -forward[0])
    lateral, ahead = {
        "MoveAhead": (0, 1), "MoveBack": (0, -1),
        "MoveLeft": (-1, 0), "MoveRight": (1, 0),
    }[action]
    return ((cell[0] + ahead * forward[0] + lateral * right[0],
             cell[1] + ahead * forward[1] + lateral * right[1]),
            yaw_quarters)


def _trace(start: tuple[int, int], yaw_quarters: int,
           actions: Sequence[str]) -> list[tuple[int, int]]:
    cells = [start]
    cell = start
    yaw = yaw_quarters
    for action in actions:
        cell, yaw = _advance(cell, yaw, action)
        cells.append(cell)
    return cells


def _fit(actions: Sequence[str], cells: set[tuple[int, int]]) -> tuple[
        tuple[int, int], int] | None:
    for start in sorted(cells):
        for yaw in range(4):
            if all(cell in cells for cell in _trace(start, yaw, actions)):
                return start, yaw
    return None


def _fit_first(candidates: Sequence[Sequence[str]],
               cells: set[tuple[int, int]]) -> tuple[
                   list[str], tuple[int, int], int]:
    for candidate in candidates:
        actions = list(candidate)
        fitted = _fit(actions, cells)
        if fitted is not None:
            return actions, fitted[0], fitted[1]
    raise D212RouteSurveyError(
        "the fixed scenario templates do not fit this sealed reachable grid")


def _neighbors(cell: tuple[int, int],
               cells: set[tuple[int, int]]) -> list[tuple[int, int]]:
    return sorted(candidate for candidate in (
        (cell[0] - 1, cell[1]), (cell[0] + 1, cell[1]),
        (cell[0], cell[1] - 1), (cell[0], cell[1] + 1),
    ) if candidate in cells)


def _shortest_path(start: tuple[int, int], end: tuple[int, int],
                   cells: set[tuple[int, int]]) -> list[tuple[int, int]]:
    queue = deque([start])
    parent: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    while queue:
        cell = queue.popleft()
        if cell == end:
            break
        for candidate in _neighbors(cell, cells):
            if candidate not in parent:
                parent[candidate] = cell
                queue.append(candidate)
    _require(end in parent, "reachable scan unexpectedly contains two components")
    result = []
    cell: tuple[int, int] | None = end
    while cell is not None:
        result.append(cell)
        cell = parent[cell]
    return list(reversed(result))


def _path_actions(path: Sequence[tuple[int, int]]) -> list[str]:
    actions = []
    # Keep yaw at zero.  Cardinal motion is expressed with public registered
    # strafing actions; no hidden world orientation is needed.
    for left, right in zip(path, path[1:]):
        delta = (right[0] - left[0], right[1] - left[1])
        actions.append({
            (0, 1): "MoveAhead", (0, -1): "MoveBack",
            (-1, 0): "MoveLeft", (1, 0): "MoveRight",
        }[delta])
    return actions


def _p08_path(cells: set[tuple[int, int]]) -> list[tuple[int, int]]:
    _require(len(cells) >= 7, "P08 needs at least seven reachable cells")

    def openness(cell: tuple[int, int]) -> int:
        return sum((cell[0] + dx, cell[1] + dz) in cells
                   for dx in range(-2, 3) for dz in range(-2, 3))

    ranked = sorted(cells, key=lambda cell: (-openness(cell), cell))
    # Evaluate a bounded, deterministic public candidate set.  The two end
    # points maximize local free-space support; the selected interior anchor
    # is the narrowest cell on their shortest path.  No simulator room label is
    # consulted, and a later RGB-D failure cannot trigger another pair.
    endpoints = ranked[:min(32, len(ranked))]
    candidates = []
    for index, start in enumerate(endpoints):
        for end in endpoints[index + 1:]:
            distance = math.hypot(end[0] - start[0], end[1] - start[1])
            if distance < 6.0:
                continue
            path = _shortest_path(start, end, cells)
            if len(path) >= 7:
                interior = min(range(1, len(path) - 1),
                               key=lambda i: (openness(path[i]), i))
                contrast = (min(openness(start), openness(end)) -
                            openness(path[interior]))
                candidates.append((-contrast, len(path), start, end, path))
    if not candidates:
        # Small/long rooms can place one useful endpoint outside the top 32.
        start = ranked[0]
        far = sorted(cells, key=lambda cell: (
            -math.hypot(cell[0] - start[0], cell[1] - start[1]), cell))
        end = next((cell for cell in far if math.hypot(
            cell[0] - start[0], cell[1] - start[1]) >= 6.0), None)
        _require(end is not None, "P08 has no public route at least 1.5 m long")
        return _shortest_path(start, end, cells)
    candidates.sort(key=lambda row: row[:4])
    return candidates[0][4]


def _scenario_candidate(scenario: str,
                        cells: set[tuple[int, int]]) -> tuple[
                            list[str], tuple[int, int], int, dict[str, Any]]:
    if scenario == "P01":
        candidates = []
        for outer in range(8, 2, -1):
            for connector in range(6, 1, -1):
                for turn in ("RotateRight", "RotateLeft"):
                    other = "RotateLeft" if turn == "RotateRight" else "RotateRight"
                    candidates.append(
                        ["MoveAhead"] * outer + [turn] +
                        ["MoveAhead"] * connector + [other] +
                        ["MoveAhead"] * outer)
        actions, start, yaw = _fit_first(candidates, cells)
        bends = [i + 1 for i, name in enumerate(actions)
                 if name.startswith("Rotate")]
        return actions, start, yaw, {
            "bend_observation_indices": bends,
            "frontier_observation_index": len(actions),
        }

    if scenario in {"P02", "P05"}:
        candidates = []
        for first in range(10, 2, -1):
            for second in range(10, 2, -1):
                outward = (["MoveAhead"] * first + ["RotateRight"] +
                           ["MoveAhead"] * second)
                route = outward + _inverse(outward)
                if scenario == "P05":
                    route += ["RotateRight", "RotateRight"]
                candidates.append(route)
        actions, start, yaw = _fit_first(candidates, cells)
        if scenario == "P02":
            note = {"turnaround_observation_index": len(actions) // 2,
                    "return_observation_index": len(actions)}
        else:
            note = {"same_place_observation_indices": [0, len(actions)]}
        return actions, start, yaw, note

    if scenario == "P03":
        candidates = []
        for first in range(8, 1, -1):
            for second in range(8, 1, -1):
                candidates.append(
                    ["MoveAhead"] * first + ["RotateRight"] +
                    ["MoveAhead"] * second + ["RotateRight"] +
                    ["MoveAhead"] * first + ["RotateRight"] +
                    ["MoveAhead"] * second + ["RotateRight"])
        actions, start, yaw = _fit_first(candidates, cells)
        return actions, start, yaw, {
            "loop_anchor_observation_indices": [0, len(actions)]}

    if scenario == "P04":
        candidates = []
        for first in range(12, 5, -1):
            for second in range(8, 1, -1):
                candidates.append(
                    ["MoveAhead"] * first + ["RotateRight"] +
                    ["MoveAhead"] * second)
        actions, start, yaw = _fit_first(candidates, cells)
        # The actual pair is derived after the public RGB-D descriptors exist.
        return actions, start, yaw, {}

    if scenario == "P06":
        candidates = []
        for arm in range(12, 1, -1):
            candidates.append(["MoveAhead"] * arm +
                              ["MoveBack"] * arm +
                              ["MoveBack"] * arm)
        actions, start, yaw = _fit_first(candidates, cells)
        arm = len(actions) // 3
        return actions, start, yaw, {
            "junction_observation_indices": [0, 2 * arm],
            "branch_endpoint_observation_indices": [arm, 3 * arm],
        }

    if scenario == "P07":
        candidates = []
        for first in range(7, 1, -1):
            for second in range(7, 1, -1):
                one = (["MoveAhead"] * first + ["MoveRight"] * second +
                       ["MoveBack"] * first + ["MoveLeft"] * second)
                two = (["MoveBack"] * first + ["MoveLeft"] * second +
                       ["MoveAhead"] * first + ["MoveRight"] * second)
                candidates.append(one + two)
        actions, start, yaw = _fit_first(candidates, cells)
        half = len(actions) // 2
        return actions, start, yaw, {
            "loop_observation_ranges": [[0, half], [half, len(actions)]]}

    _require(scenario == "P08", f"unsupported P0 scenario {scenario}")
    path = _p08_path(cells)
    actions = _path_actions(path)
    def openness(cell: tuple[int, int]) -> int:
        return sum((cell[0] + dx, cell[1] + dz) in cells
                   for dx in range(-2, 3) for dz in range(-2, 3))
    interior = min(range(1, len(path) - 1), key=lambda index: (
        openness(path[index]), index))
    return actions, path[0], 0, {
        "room_anchor_observation_indices": [0, len(actions)],
        "corridor_observation_indices": [interior],
    }


def plan_route_from_reachable_scan(
    *, slot: int, reachable_scan: Mapping[str, Any],
    contract: Mapping[str, Any], base_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Choose one deterministic fixed-family route from a public grid."""

    approved = validate_d211_contract(contract, base_contract=base_contract)
    scan = validate_reachable_scan(
        reachable_scan, contract=approved, base_contract=base_contract)
    slot_spec = base_contract["slot_plan"][slot]
    _require(scan["house_slot"] == slot_spec["house_slot"],
             "route slot and reachable scan house disagree")
    cells = {tuple(row) for row in scan["cells"]}
    actions, start, yaw, annotations = _scenario_candidate(
        slot_spec["scenario_id"], cells)
    keyframes = sorted(set([0, len(actions)] + list(range(0, len(actions) + 1, 4))))
    route = build_route_plan(
        slot=slot, action_names=actions,
        keyframe_observation_indices=keyframes, contract=base_contract)
    initial_pose = {
        "x_m": float(scan["origin_x_m"]) + start[0] * float(scan["grid_size_m"]),
        "y_m": float(scan["level_y_m"]),
        "z_m": float(scan["origin_z_m"]) + start[1] * float(scan["grid_size_m"]),
        "yaw_deg": float(yaw * 90), "horizon_deg": 0.0,
    }
    return {"route_plan": route, "initial_pose": initial_pose,
            "provisional_annotations": annotations}


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    numerator = sum(float(a) * float(b) for a, b in zip(left, right))
    left_norm = math.sqrt(sum(float(a) ** 2 for a in left))
    right_norm = math.sqrt(sum(float(b) ** 2 for b in right))
    return numerator / (left_norm * right_norm)


def _finish_annotations(route: Mapping[str, Any], initial_pose: Mapping[str, Any],
                        observations: Sequence[Mapping[str, Any]],
                        provisional: Mapping[str, Any],
                        base_contract: Mapping[str, Any]) -> dict[str, Any]:
    scenario = route["scenario_id"]
    if scenario != "P04":
        return dict(provisional)
    # Reconstruct nominal positions without importing private world truth.
    from .d211_p0_smoke import nominal_route_poses
    poses = nominal_route_poses(route, initial_pose,
                                base_contract=base_contract)
    candidates = []
    for index, left in enumerate(observations):
        for right in observations[index + 1:]:
            a, b = left["observation_index"], right["observation_index"]
            distance = math.hypot(poses[a]["x_m"] - poses[b]["x_m"],
                                  poses[a]["z_m"] - poses[b]["z_m"])
            if distance >= 1.5:
                candidates.append((-_cosine(left["place_descriptor"],
                                            right["place_descriptor"]), [a, b]))
    _require(candidates, "P04 public survey produced no pair at least 1.5 m apart")
    candidates.sort()
    return {"alias_observation_indices": candidates[0][1]}


def build_route_bundle_row(
    *, planned: Mapping[str, Any], reachable_scan: Mapping[str, Any],
    public_observations: Sequence[Mapping[str, Any]],
    contract: Mapping[str, Any], base_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind a selected route to public survey evidence and private start pose."""

    route = planned["route_plan"]
    initial_pose = planned["initial_pose"]
    evidence = seal_public_route_evidence(
        route_plan=route, observations=public_observations,
        base_contract=base_contract)
    annotations = _finish_annotations(
        route, initial_pose, evidence["observations"],
        planned["provisional_annotations"], base_contract)
    scenario = seal_scenario_receipt(
        route_plan=route, initial_pose=initial_pose,
        public_route_evidence=evidence, annotations=annotations,
        contract=contract, base_contract=base_contract)
    binding = seal_route_execution_binding(
        route_plan=route, initial_pose=initial_pose,
        reachable_scan=reachable_scan, public_route_evidence=evidence,
        scenario_receipt=scenario, contract=contract,
        base_contract=base_contract)
    return {"route_plan": route, "reachable_scan": dict(reachable_scan),
            "public_route_evidence": evidence,
            "scenario_receipt": scenario, "execution_binding": binding}


def public_frame_descriptor(rgb: Any, depth: Any) -> list[float]:
    """Small deterministic RGB-D survey descriptor; not the model frontend."""

    import numpy as np
    rgb_array = np.asarray(rgb, dtype=np.float32)
    depth_array = np.asarray(depth, dtype=np.float32)
    _require(rgb_array.ndim == 3 and rgb_array.shape[2] == 3,
             "public survey RGB must be HxWx3")
    _require(depth_array.shape == rgb_array.shape[:2],
             "public survey depth shape disagrees with RGB")
    features = []
    for y0, y1 in ((0, rgb_array.shape[0] // 2),
                   (rgb_array.shape[0] // 2, rgb_array.shape[0])):
        for x0, x1 in ((0, rgb_array.shape[1] // 2),
                       (rgb_array.shape[1] // 2, rgb_array.shape[1])):
            tile_rgb = rgb_array[y0:y1, x0:x1] / 255.0
            tile_depth = depth_array[y0:y1, x0:x1]
            finite = tile_depth[np.isfinite(tile_depth)]
            features.extend(tile_rgb.mean(axis=(0, 1)).tolist())
            features.append(float(finite.mean()) if finite.size else 0.0)
    norm = math.sqrt(sum(value * value for value in features))
    _require(norm > 0.0, "public RGB-D descriptor is zero")
    return [float(value / norm) for value in features]


def public_region_refs(rgb: Any, depth: Any) -> list[str]:
    """Return anonymous RGB-D tile proposals without simulator identities."""

    import numpy as np
    rgb_array = np.asarray(rgb, dtype=np.uint8)
    depth_array = np.asarray(depth, dtype=np.float32)
    refs = []
    height, width = depth_array.shape
    for row in range(2):
        for column in range(2):
            y0, y1 = row * height // 2, (row + 1) * height // 2
            x0, x1 = column * width // 2, (column + 1) * width // 2
            tile_depth = depth_array[y0:y1, x0:x1]
            tile_rgb = rgb_array[y0:y1, x0:x1]
            if np.isfinite(tile_depth).any() and float(tile_rgb.std()) >= 2.0:
                payload = (tile_rgb.tobytes() + tile_depth.tobytes() +
                           bytes([row, column]))
                refs.append("region:" + hashlib.sha256(payload).hexdigest()[:24])
    if not refs and np.isfinite(depth_array).any():
        refs.append("region:" + hashlib.sha256(
            rgb_array.tobytes() + depth_array.tobytes()).hexdigest()[:24])
    return sorted(set(refs))


def survey_algorithm_sha256() -> str:
    """Stable semantic tag stored in receipts, separate from Git binding."""

    return hashlib.sha256(canonical_json({
        "planner": "fixed_public_grid_templates_v1",
        "descriptor": "four_quadrant_rgb_mean_depth_mean_l2_v1",
        "regions": "four_quadrant_rgb_depth_anonymous_regions_v1",
        "route_replacement_after_failure": False,
    }).encode("utf-8")).hexdigest()
