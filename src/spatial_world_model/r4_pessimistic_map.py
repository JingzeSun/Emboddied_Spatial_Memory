"""Pessimistic completion of the public-map dynamics baseline.

The nominal solver may only contribute its prefix while both swept bodies stay
inside observed-free or decision-time body-certified cells. The first remaining
unknown is treated as a blocking static obstacle and the system stops.
"""

from __future__ import annotations

from copy import deepcopy
import math

from .pair_contract import require
from .r4_query_v2 import PREDICTION_VERSION, validate_prediction

VERSION = "spatial-history-r4-pessimistic-map-v1"


def _cell_center(cell, cell_m):
    return ((cell[0] + .5) * cell_m, (cell[1] + .5) * cell_m)


def _candidate_cells(bounds, cell_m):
    x0, x1, y0, y1 = bounds
    return {(x, y)
            for x in range(math.floor(x0 / cell_m), math.floor(x1 / cell_m) + 1)
            for y in range(math.floor(y0 / cell_m), math.floor(y1 / cell_m) + 1)}


def _distance_to_segment(point, start, end):
    delta = (end[0] - start[0], end[1] - start[1])
    length2 = delta[0] ** 2 + delta[1] ** 2
    if length2 == 0:
        return math.dist(point, start)
    fraction = max(0., min(1., ((point[0] - start[0]) * delta[0]
                                + (point[1] - start[1]) * delta[1]) / length2))
    closest = (start[0] + fraction * delta[0], start[1] + fraction * delta[1])
    return math.dist(point, closest)


def circle_sweep_cells(start, end, radius, cell_m):
    bounds = (min(start[0], end[0]) - radius, max(start[0], end[0]) + radius,
              min(start[1], end[1]) - radius, max(start[1], end[1]) + radius)
    return {cell for cell in _candidate_cells(bounds, cell_m)
            if _distance_to_segment(_cell_center(cell, cell_m), start, end) <= radius}


def box_sweep_cells(start, end, half, cell_m):
    """A conservative axis-aligned swept box; extra cells can only stop earlier."""
    bounds = (min(start[0], end[0]) - half[0], max(start[0], end[0]) + half[0],
              min(start[1], end[1]) - half[1], max(start[1], end[1]) + half[1])
    return _candidate_cells(bounds, cell_m)


def decision_body_free_cells(observed_map, public_domain):
    """Cells whose centers lie inside every allowed current body placement."""
    cell_m = observed_map["cell_m"]
    state = observed_map["current_object"]
    require(state is not None and state["status"] == "association_ready", "object association required")
    intervals = state["position_intervals_m"][:2]
    radius = public_domain["object_radius_m"]
    bounds = (intervals[0][0] - radius, intervals[0][1] + radius,
              intervals[1][0] - radius, intervals[1][1] + radius)
    object_cells = set()
    corners = [(x, y) for x in intervals[0] for y in intervals[1]]
    for cell in _candidate_cells(bounds, cell_m):
        point = _cell_center(cell, cell_m)
        if max(math.dist(point, center) for center in corners) <= radius:
            object_cells.add(cell)
    robot = state["robot_state"]["position_m"]
    half = public_domain["pusher_half_size_m"][:2]
    robot_bounds = (robot[0] - half[0], robot[0] + half[0],
                    robot[1] - half[1], robot[1] + half[1])
    robot_cells = {cell for cell in _candidate_cells(robot_bounds, cell_m)
                   if abs(_cell_center(cell, cell_m)[0] - robot[0]) <= half[0]
                   and abs(_cell_center(cell, cell_m)[1] - robot[1]) <= half[1]}
    return object_cells | robot_cells


def pessimistic_trajectory(observed_map, nominal_proxy, public_domain):
    """Keep the certified nominal prefix, then freeze at the first unknown sweep."""
    require(nominal_proxy["status"] == "nominal_complete"
            and len(nominal_proxy["trajectory"]) == 10001, "complete nominal proxy required")
    cell_m = observed_map["cell_m"]
    require(cell_m == .01, "registered map cell size")
    traversable = set(map(tuple, observed_map["nominal_free_cells"]))
    traversable |= decision_body_free_cells(observed_map, public_domain)
    radius = public_domain["object_radius_m"]
    half = public_domain["pusher_half_size_m"][:2]
    source = nominal_proxy["trajectory"]
    stop = None
    denied = None
    for step in range(1, len(source)):
        old, new = source[step - 1], source[step]
        object_cells = circle_sweep_cells(old["object_position_m"], new["object_position_m"],
                                          radius, cell_m)
        robot_cells = box_sweep_cells(old["robot_position_m"], new["robot_position_m"],
                                      half, cell_m)
        object_denied = object_cells - traversable
        robot_denied = robot_cells - traversable
        if object_denied or robot_denied:
            stop = step
            denied = {"object": object_denied, "pusher": robot_denied}
            break
    if stop is None:
        return deepcopy(source), {"stop_step": None, "object_denied": False,
                                  "pusher_denied": False, "denied_cell_count": 0,
                                  "decision_body_free_cells": len(decision_body_free_cells(observed_map, public_domain))}
    result = deepcopy(source[:stop])
    anchor = deepcopy(source[stop - 1])
    for step in range(stop, 10001):
        row = deepcopy(anchor)
        row.update(step_index=step, time_s=step * .002,
                   object_velocity_mps=[0., 0., 0.], robot_velocity_mps=[0., 0., 0.],
                   servo_force_n=[0., 0.], object_robot_contact=False,
                   object_obstacle_contact=(step == stop and bool(denied["object"])),
                   robot_obstacle_contact=(step == stop and bool(denied["pusher"])))
        result.append(row)
    return result, {
        "stop_step": stop,
        "object_denied": bool(denied["object"]),
        "pusher_denied": bool(denied["pusher"]),
        "denied_cell_count": len(denied["object"] | denied["pusher"]),
        "decision_body_free_cells": len(decision_body_free_cells(observed_map, public_domain)),
    }


def prediction_from_trajectory(trajectory, nominal_success):
    positions = [trajectory[index]["object_position_m"] for index in range(50, 10001, 50)]
    contacts = [any(row["object_obstacle_contact"]
                    for row in trajectory[index * 50 + 1:(index + 1) * 50 + 1])
                for index in range(200)]
    result = {
        "schema_version": PREDICTION_VERSION,
        "prediction_times_s": [index / 10 for index in range(1, 201)],
        "object_position_m": deepcopy(positions),
        "obstacle_contact_probability": [float(value) for value in contacts],
        "task_success_probability": float(nominal_success),
    }
    validate_prediction(result)
    return result


def predict(observed_map, nominal_proxy, public_domain, goal):
    """Produce one complete pessimistic M prediction and keep its stopping audit."""
    from .r4_proxy_readout import parameters, readout

    trajectory, audit = pessimistic_trajectory(observed_map, nominal_proxy, public_domain)
    proxy = deepcopy(nominal_proxy)
    proxy.update(status="nominal_complete", trajectory=trajectory,
                 kind="pessimistic_unknown_as_blocking", main_prediction=None,
                 eligible_for_P=False, uncertainty_status="unknown_is_blocking_after_body_certificate")
    task = readout(observed_map, proxy, goal, parameters())
    require(task["status"] == "nominal_readout_complete", "pessimistic task readout incomplete")
    common = prediction_from_trajectory(trajectory, task["nominal_success"])
    return {"schema_version": VERSION, "prediction": common, "proxy": proxy,
            "task": task, "audit": audit, "formal_prediction_available": True,
            "formal_model_ready": False,
            "unknown_assumed_free": False, "uses_private_truth": False}
