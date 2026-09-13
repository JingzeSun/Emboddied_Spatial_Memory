"""Task readout for D-112 public continuous-map trajectories.

Openings are inferred from the pessimistic wall rectangles.  The readout uses
only the predicted trajectory and public goal; it never opens labels or source
world geometry.
"""

from __future__ import annotations

import math

from .pair_contract import require
from .r4_object_association import _fixed
from .r4_query_v2 import PREDICTION_VERSION, validate_goal, validate_prediction


VERSION = "spatial-history-r4-continuous-readout-v1"
PARAMETERS = {
    "expected_task_openings": 2,
    "wall_thickness_m": .05,
    "wall_band_tolerance_m": .035,
    "minimum_wall_band_m": .02,
    "maximum_wall_band_m": .085,
    "object_radius_m": .07,
    "object_half_height_m": .04,
}


def parameters():
    return dict(PARAMETERS)


def public_openings(continuous_map):
    """Return gaps between observed wall-interval rectangles, never truth IDs."""
    cell = continuous_map["cell_m"]
    free = set(map(tuple, continuous_map["observed_floor_cells"]))
    boxes = [list(box) for box in continuous_map["observed_wall_interval_rectangles_xy_m"]
             if PARAMETERS["minimum_wall_band_m"] <= box[3] - box[2]
             <= PARAMETERS["maximum_wall_band_m"]]
    groups = []
    for obstacle in sorted(boxes, key=lambda value: (value[2], value[0])):
        if groups and obstacle[2] <= max(value[3] for value in groups[-1]) + cell:
            groups[-1].append(obstacle)
        else:
            groups.append([obstacle])
    openings = []
    for group in groups:
        front = min(value[2] for value in group)
        back = max(value[3] for value in group)
        if abs(back - front - PARAMETERS["wall_thickness_m"]) \
                > PARAMETERS["wall_band_tolerance_m"]:
            continue
        spans = []
        for obstacle in sorted(group):
            if spans and obstacle[0] <= spans[-1][1]:
                spans[-1][1] = max(spans[-1][1], obstacle[1])
            else:
                spans.append(obstacle[:2])
        for left, right in zip(spans, spans[1:]):
            if left[1] >= right[0]:
                continue
            columns = [x for x in range(math.ceil(left[1] / cell),
                                        math.floor(right[0] / cell))
                       if all((x, y) in free
                              for y in range(math.floor(front / cell),
                                             math.ceil(back / cell)))]
            if columns:
                openings.append({
                    "x_bounds_m": [left[1], right[0]],
                    "plane_y_m": (front + back) / 2,
                    "source_rectangles": group,
                    "observed_through_columns": columns,
                    "coordinate_uncertainty_certified": True,
                    "assumption_conditioned": True,
                    "boundary_semantics": "pessimistic_public_opening_interval_wall_union",
                })
    return sorted(openings, key=lambda value: (value["plane_y_m"], value["x_bounds_m"]))


def readout(openings, trajectory, goal, readout_parameters):
    """Evaluate a complete predicted trace and pack the common 200-step output."""
    _fixed(readout_parameters, PARAMETERS, "continuous readout parameters")
    validate_goal(goal)
    result = {
        "schema_version": VERSION,
        "status": "task_readout_unresolved",
        "openings": openings,
        "events": [],
        "nominal_success": None,
        "settled_containment": None,
        "settled_speed": None,
        "ordered_gate_passage": None,
        "prediction": None,
    }
    if len(trajectory) != 10001 or len(openings) != PARAMETERS["expected_task_openings"]:
        return result
    active = [None, None]
    completed = [[], []]
    events = []
    goal_all = True
    speed_all = True
    radius = PARAMETERS["object_radius_m"]
    half_height = PARAMETERS["object_half_height_m"]
    epsilon = goal["containment_boundary_tolerance_m"]
    def extent(sample, axis):
        direction = sample.get("object_axis_world")
        if direction is None:
            return radius
        require(isinstance(direction, list) and len(direction) == 3,
                "object axis must be a 3-vector")
        component = direction[axis]
        return radius * math.sqrt(max(0., 1 - component * component)) \
            + half_height * abs(component)
    for index, sample in enumerate(trajectory):
        require(sample["step_index"] == index, "trajectory step order")
        position = sample["object_position_m"]
        time_s = sample["time_s"]
        if index:
            previous = trajectory[index - 1]
            for gate, opening in enumerate(openings):
                plane_y = opening["plane_y_m"]
                if active[gate] is not None and position[1] < plane_y:
                    events[active[gate]]["status"] = "cancelled"
                    active[gate] = None
                if previous["object_position_m"][1] < plane_y <= position[1]:
                    fraction = ((plane_y - previous["object_position_m"][1]) /
                                (position[1] - previous["object_position_m"][1]))
                    cross_time = previous["time_s"] + fraction * (time_s - previous["time_s"])
                    cross_x = (previous["object_position_m"][0] + fraction *
                               (position[0] - previous["object_position_m"][0]))
                    valid = (opening["x_bounds_m"][0] - epsilon <= cross_x
                             <= opening["x_bounds_m"][1] + epsilon)
                    ordered = gate == 0 or any(value < cross_time for value in completed[0])
                    events.append({"gate_index": gate, "cross_time_s": cross_time,
                                   "cross_x_m": cross_x,
                                   "status": "active" if valid and ordered else "invalid",
                                   "completion_time_s": None})
                    active[gate] = len(events) - 1 if valid and ordered else None
                if (active[gate] is not None and
                        position[1] - extent(sample, 1) >= plane_y + PARAMETERS["wall_thickness_m"] / 2
                        - epsilon):
                    events[active[gate]].update(status="completed", completion_time_s=time_s)
                    completed[gate].append(time_s)
                    active[gate] = None
        if time_s >= goal["settled_interval_s"][0] - 1e-9:
            for axis, bounds in enumerate((goal["goal_x_bounds_m"], goal["goal_y_bounds_m"])):
                body_extent = extent(sample, axis)
                goal_all &= (position[axis] - body_extent >= bounds[0] - epsilon and
                             position[axis] + body_extent <= bounds[1] + epsilon)
            speed_all &= math.sqrt(sum(value * value for value in
                                       sample["object_velocity_mps"])) \
                <= goal["maximum_object_linear_speed_mps"]
    contact = [any(row["object_obstacle_contact"]
                   for row in trajectory[index * 50 + 1:(index + 1) * 50 + 1])
               for index in range(200)]
    success = bool(all(completed) and goal_all and speed_all)
    prediction = {
        "schema_version": PREDICTION_VERSION,
        "prediction_times_s": [index / 10 for index in range(1, 201)],
        "object_position_m": [list(trajectory[index * 50]["object_position_m"])
                              for index in range(1, 201)],
        "obstacle_contact_probability": [float(value) for value in contact],
        "task_success_probability": float(success),
    }
    validate_prediction(prediction)
    result.update(status="nominal_readout_complete", events=events,
                  nominal_success=success, settled_containment=bool(goal_all),
                  settled_speed=bool(speed_all), ordered_gate_passage=bool(all(completed)),
                  prediction=prediction)
    return result
