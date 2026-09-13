"""D-112 M-SIMPLE: public-map planar inertial prediction.

Unknown space blocks only the body whose complete continuous sweep lacks public
support.  Observed walls remain ordinary collision geometry, so their contacts
cannot be mislabeled as an unknown prior.
"""

from __future__ import annotations

from copy import deepcopy
import math

from shapely.geometry import Point, box
from shapely.ops import unary_union
import shapely

from .pair_contract import require, vector
from .r4_continuous_map import VERSION as MAP_VERSION, classify_uncertified_cells
from .r4_continuous_readout import public_openings, readout
from .r4_continuous_shapes import (
    _box_sweep, _outer_circle_radius, _outer_circle_sweep, _rectangles_union,
    audit_trajectory,
)
from .r4_control_proxy import _clamp, _contacts, _drag, _solve
from .r4_object_association import _fixed
from .r4_query_v2 import validate_controls, validate_domain


VERSION = "spatial-history-r4-m-simple-v1"
PARAMETERS = {
    "timestep_s": .002,
    "steps": 10000,
    "solver_iterations": 10,
    "penetration_slop_m": .0001,
    "position_correction_limit_m": .002,
    "maximum_step_displacement_m": .005,
    "maximum_residual_penetration_m": .005,
    "initial_height_tolerance_m": .002,
    "contact_force_threshold_n": .000001,
    "unknown_clip_bisection_iterations": 24,
    "initial_hypotheses": "public_interval_midpoint_and_four_xy_corners",
    "main_hypothesis": "midpoint",
    "unknown_policy": "occupied_clip_only_denied_body",
    "integrator": "semi_implicit_euler_sequential_impulses",
}


def parameters():
    return deepcopy(PARAMETERS)


def initial_hypotheses(current_object):
    intervals = current_object["position_intervals_m"][:2]
    midpoint = [sum(interval) / 2 for interval in intervals]
    result = [{"name": "midpoint", "position_xy_m": midpoint, "main": True}]
    for x_name, x in (("low", intervals[0][0]), ("high", intervals[0][1])):
        for y_name, y in (("low", intervals[1][0]), ("high", intervals[1][1])):
            value = [x, y]
            if value != midpoint:
                result.append({"name": f"x_{x_name}_y_{y_name}",
                               "position_xy_m": value, "main": False})
    return result


class _ContactLog:
    def __init__(self):
        self.intervals = []

    def record(self, step, body, source, detail=None):
        detail = detail or {}
        if (self.intervals and self.intervals[-1]["last_step"] == step - 1 and
                self.intervals[-1]["body"] == body and
                self.intervals[-1]["source"] == source and
                self.intervals[-1]["detail"] == detail):
            self.intervals[-1]["last_step"] = step
            self.intervals[-1]["step_count"] += 1
        else:
            self.intervals.append({"first_step": step, "last_step": step,
                                   "step_count": 1, "body": body,
                                   "source": source, "detail": detail})


def _body_sweep(body, start, end, public_domain, geometry_parameters):
    if body == 0:
        return _outer_circle_sweep(
            start, end, public_domain["object_radius_m"],
            geometry_parameters["circle_quadrant_segments"],
            geometry_parameters["numeric_guard_m"])
    return _box_sweep(start, end, public_domain["pusher_half_size_m"][:2])


def _initial_footprint(body, position, public_domain, geometry_parameters):
    if body == 0:
        radius = _outer_circle_radius(
            public_domain["object_radius_m"],
            geometry_parameters["circle_quadrant_segments"],
            geometry_parameters["numeric_guard_m"])
        return Point(position).buffer(
            radius, quad_segs=geometry_parameters["circle_quadrant_segments"])
    half = public_domain["pusher_half_size_m"][:2]
    return box(position[0] - half[0], position[1] - half[1],
               position[0] + half[0], position[1] + half[1])


def _clip_to_support(body, start, proposed, support, public_domain, geometry_parameters):
    if start == proposed:
        return list(proposed), None
    sweep = _body_sweep(body, start, proposed, public_domain, geometry_parameters)
    if support.covers(sweep):
        return list(proposed), None
    uncovered = sweep.difference(support)
    low, high = 0., 1.
    for _ in range(PARAMETERS["unknown_clip_bisection_iterations"]):
        middle = (low + high) / 2
        trial = [start[axis] + middle * (proposed[axis] - start[axis]) for axis in (0, 1)]
        if support.covers(_body_sweep(body, start, trial, public_domain,
                                     geometry_parameters)):
            low = middle
        else:
            high = middle
    clipped = [start[axis] + low * (proposed[axis] - start[axis]) for axis in (0, 1)]
    return clipped, uncovered


def _uncovered_detail(continuous_map, geometry):
    if geometry is None or geometry.is_empty:
        return {}
    point = geometry.representative_point()
    cell_m = continuous_map["cell_m"]
    cell = (math.floor(point.x / cell_m), math.floor(point.y / cell_m))
    classified = classify_uncertified_cells(continuous_map, {cell})
    source = next(name for name, cells in classified.items() if cells)
    return {"source": source, "representative_cell": list(cell),
            "uncovered_area_m2": geometry.area}


def _simulate(continuous_map, controls, public_domain, initial_xy, *, step_count=None):
    current = continuous_map["current_object"]
    ground = continuous_map["ground"]
    floor = sum(ground["height_interval_m"]) / 2
    radius = public_domain["object_radius_m"]
    half = public_domain["pusher_half_size_m"][:2]
    robot = current["robot_state"]["position_m"]
    positions = [list(initial_xy), list(robot[:2])]
    velocities = [list(current["interval_mean_velocity_mps"][:2]),
                  list(current["robot_state"]["velocity_mps"][:2])]
    heights = [floor + public_domain["object_half_height_m"], robot[2]]
    robot_z = [heights[1] - public_domain["pusher_half_size_m"][2],
               heights[1] + public_domain["pusher_half_size_m"][2]]
    vertical_active = (True, robot_z[0] <= floor + public_domain["obstacle_height_m"]
                       and robot_z[1] >= floor)
    pair_active = (robot_z[0] <= floor + 2 * public_domain["object_half_height_m"]
                   and robot_z[1] >= floor)
    rectangles = continuous_map["observed_wall_interval_rectangles_xy_m"]
    for rectangle in rectangles:
        vector(rectangle, 4, "observed wall interval rectangle")
        require(rectangle[0] < rectangle[1] and rectangle[2] < rectangle[3],
                "observed wall interval extent")
    geometry_parameters = continuous_map["geometry_parameters"]
    observed_floor = _rectangles_union(
        continuous_map["observed_floor_support_rectangles_xy_m"])
    observed_walls = _rectangles_union(rectangles)
    supports = []
    for body in (0, 1):
        own = _initial_footprint(body, positions[body], public_domain, geometry_parameters)
        support = unary_union((observed_floor, observed_walls, own))
        shapely.prepare(support)
        supports.append(support)
    masses = [public_domain["object_mass_kg"], public_domain["pusher_mass_kg"]]
    dt = PARAMETERS["timestep_s"]
    friction = public_domain["friction"][0]
    gravity = -public_domain["gravity_mps2"][2]
    trace = []
    provenance = _ContactLog()
    maximum_step_displacement = 0.
    maximum_residual_penetration = 0.
    numerical_failure_step = None

    def save(step, force, contacts, unknown_contacts):
        positive = [contact for contact in contacts
                    if contact["jn"] / dt > PARAMETERS["contact_force_threshold_n"]]
        object_unknown = any(body == 0 for body, _ in unknown_contacts)
        robot_unknown = any(body == 1 for body, _ in unknown_contacts)
        trace.append({
            "step_index": step,
            "time_s": step * dt,
            "object_position_m": [*positions[0], heights[0]],
            "object_velocity_mps": [*velocities[0], 0.],
            "robot_position_m": [*positions[1], heights[1]],
            "robot_velocity_mps": [*velocities[1], 0.],
            "servo_force_n": list(force),
            "object_obstacle_contact": object_unknown or any(
                contact["body"] == 0 and contact["obstacle"] is not None
                for contact in positive),
            "robot_obstacle_contact": robot_unknown or any(
                contact["body"] == 1 and contact["obstacle"] is not None
                for contact in positive),
            "object_robot_contact": any(contact["other"] == 1 for contact in positive),
        })

    save(0, [0., 0.], [], [])
    steps = PARAMETERS["steps"] if step_count is None else step_count
    require(type(steps) is int and 0 <= steps <= PARAMETERS["steps"], "simulation step count")
    for step in range(1, steps + 1):
        previous = deepcopy(positions)
        command = controls["ee_velocity_mps"][(step - 1) // 50]
        force = [_clamp(public_domain["velocity_servo_kv"] *
                        (command[axis] - velocities[1][axis]),
                        -public_domain["force_limit_per_axis_n"],
                        public_domain["force_limit_per_axis_n"])
                 for axis in (0, 1)]
        velocities[1] = [value + applied / masses[1] * dt
                         for value, applied in zip(velocities[1], force)]
        velocities[0] = _drag(velocities[0], friction * gravity * dt)
        if heights[1] - public_domain["pusher_half_size_m"][2] \
                <= floor + PARAMETERS["penetration_slop_m"]:
            velocities[1] = _drag(velocities[1], friction * gravity * dt)
        proposed = [[position[axis] + velocity[axis] * dt for axis in (0, 1)]
                    for position, velocity in zip(positions, velocities)]
        unknown_contacts = []
        for body in (0, 1):
            positions[body], uncovered = _clip_to_support(
                body, previous[body], proposed[body], supports[body],
                public_domain, geometry_parameters)
            if uncovered is not None:
                detail = _uncovered_detail(continuous_map, uncovered)
                provenance.record(step, "object" if body == 0 else "pusher",
                                  detail.pop("source"), detail)
                unknown_contacts.append((body, detail))
                velocities[body] = [0., 0.]
        movement = max(math.dist(before, after)
                       for before, after in zip(previous, positions))
        if (not all(math.isfinite(value) for state in (positions, velocities)
                    for body in state for value in body)
                or not math.isfinite(movement)
                or movement > PARAMETERS["maximum_step_displacement_m"]):
            numerical_failure_step = step
            break
        contacts = _contacts(positions, rectangles, radius, half,
                             vertical_active, pair_active)
        _solve(contacts, velocities, masses, friction, dt)
        for contact in contacts:
            if contact["jn"] / dt > PARAMETERS["contact_force_threshold_n"]:
                if contact["other"] == 1:
                    provenance.record(step, "object_and_pusher", "object_pusher")
                elif contact["obstacle"] is not None:
                    provenance.record(step, "object" if contact["body"] == 0 else "pusher",
                                      "observed_wall_interval",
                                      {"obstacle_index": contact["obstacle"]})
        before_correction = deepcopy(positions)
        for contact in contacts:
            body, other = contact["body"], contact["other"]
            depth = min(PARAMETERS["position_correction_limit_m"],
                        max(0., contact["penetration"] - PARAMETERS["penetration_slop_m"]))
            inverse = 1 / masses[body] + (0. if other is None else 1 / masses[other])
            for axis in (0, 1):
                correction = depth * contact["normal"][axis] / inverse
                positions[body][axis] += correction / masses[body]
                if other is not None:
                    positions[other][axis] -= correction / masses[other]
        for body in (0, 1):
            corrected, uncovered = _clip_to_support(
                body, before_correction[body], positions[body], supports[body],
                public_domain, geometry_parameters)
            positions[body] = corrected
            if uncovered is not None:
                detail = _uncovered_detail(continuous_map, uncovered)
                provenance.record(step, "object" if body == 0 else "pusher",
                                  detail.pop("source"), detail)
                unknown_contacts.append((body, detail))
                velocities[body] = [0., 0.]
        residual = max((contact["penetration"] for contact in _contacts(
            positions, rectangles, radius, half, vertical_active, pair_active)), default=0.)
        movement = max(math.dist(before, after)
                       for before, after in zip(previous, positions))
        maximum_step_displacement = max(maximum_step_displacement, movement)
        maximum_residual_penetration = max(maximum_residual_penetration, residual)
        save(step, force, contacts, unknown_contacts)
        if (not all(math.isfinite(value) for state in (positions, velocities)
                    for body in state for value in body)
                or movement > PARAMETERS["maximum_step_displacement_m"]
                or residual > PARAMETERS["maximum_residual_penetration_m"]):
            numerical_failure_step = step
            break
    return {
        "status": "numerical_failure" if numerical_failure_step else "complete",
        "trajectory": trace,
        "contact_provenance": provenance.intervals,
        "numerical_audit": {
            "numerical_failure_step": numerical_failure_step,
            "maximum_step_displacement_m": maximum_step_displacement,
            "maximum_residual_penetration_m": maximum_residual_penetration,
        },
    }


def predict(continuous_map, controls, goal, public_domain, dynamics_parameters,
            readout_parameters):
    """Run midpoint plus fixed interval-corner sensitivity without private inputs."""
    _fixed(dynamics_parameters, PARAMETERS, "M-SIMPLE dynamics parameters")
    validate_controls(controls)
    validate_domain(public_domain)
    require(continuous_map.get("schema_version") == MAP_VERSION, "continuous map version")
    require(not ({"labels", "actual_future", "world_name", "goal", "source_xml"}
                 & set(continuous_map)), "private/control field in continuous map")
    output = {
        "schema_version": VERSION,
        "system": "M-SIMPLE",
        "status": "perception_unresolved",
        "prediction": None,
        "trajectory": None,
        "certificate": None,
        "contact_provenance": [],
        "numerical_audit": None,
        "initialization": None,
        "initial_sensitivity": [],
        "formal_model_ready": False,
    }
    current = continuous_map.get("current_object")
    if current is None or current["status"] != "association_ready":
        return output
    if continuous_map.get("ground") is None:
        output["status"] = "ground_unresolved"
        return output
    floor = sum(continuous_map["ground"]["height_interval_m"]) / 2
    if abs(current["position_m"][2] - public_domain["object_half_height_m"] - floor) \
            > PARAMETERS["initial_height_tolerance_m"]:
        output["status"] = "initial_height_unresolved"
        return output
    if abs(current["robot_state"]["velocity_mps"][2]) > 1e-9:
        output["status"] = "robot_kinematics_unresolved"
        return output
    openings = public_openings(continuous_map)
    hypotheses = initial_hypotheses(current)
    for hypothesis in hypotheses:
        simulation = _simulate(continuous_map, controls, public_domain,
                               hypothesis["position_xy_m"])
        task = readout(openings, simulation["trajectory"], goal, readout_parameters)
        sensitivity = {
            "name": hypothesis["name"],
            "position_xy_m": hypothesis["position_xy_m"],
            "status": simulation["status"],
            "prediction": task["prediction"],
            "nominal_success": task["nominal_success"],
            "contact_provenance": simulation["contact_provenance"],
            "numerical_audit": simulation["numerical_audit"],
        }
        output["initial_sensitivity"].append(sensitivity)
        if hypothesis["main"]:
            output.update(
                status=("complete" if simulation["status"] == "complete" and
                        task["status"] == "nominal_readout_complete" else
                        simulation["status"] if simulation["status"] != "complete"
                        else "task_readout_unresolved"),
                prediction=task["prediction"], trajectory=simulation["trajectory"],
                contact_provenance=simulation["contact_provenance"],
                numerical_audit=simulation["numerical_audit"],
            )
            output["certificate"] = audit_trajectory(
                continuous_map, simulation["trajectory"], public_domain)
    output["initialization"] = {
        "assumption": "upright_fixed_spin_planar_backward_interval_mean",
        "main_hypothesis": "midpoint",
        "position_intervals_m": deepcopy(current["position_intervals_m"]),
        "velocity_intervals_mps": deepcopy(current["interval_mean_velocity_intervals_mps"]),
        "hypotheses": [{"name": value["name"],
                        "position_xy_m": value["position_xy_m"]}
                       for value in hypotheses],
        "model_vertical_velocity_mps": 0.,
        "model_spin_radps": 0.,
    }
    return output
