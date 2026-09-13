"""D-112 M-PHYS built only from a supplied public continuous map.

MuJoCo resolves ground, observed-wall, object, and pusher contacts.  The same
continuous support predicate as M-SIMPLE enforces the pessimistic unknown prior
after every 0.002-second engine step; no source XML or saved integration state
is accepted by this module.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import math
import xml.etree.ElementTree as ET

import mujoco as mj
import numpy as np
import shapely
from shapely.ops import unary_union

from .pair_contract import require, vector
from .r4_continuous_map import VERSION as MAP_VERSION
from .r4_continuous_readout import public_openings, readout
from .r4_continuous_shapes import _rectangles_union, audit_trajectory
from .r4_object_association import _fixed
from .r4_query_v2 import validate_controls, validate_domain
from .r4_simple_dynamics import (
    _ContactLog, _clip_to_support, _initial_footprint, _uncovered_detail,
    initial_hypotheses,
)


VERSION = "spatial-history-r4-m-phys-v1"
MUJOCO_VERSION = "3.3.7"
NUMPY_VERSION = "2.2.6"
PARAMETERS = {
    "timestep_s": .002,
    "steps": 10000,
    "contact_force_threshold_n": .000001,
    "maximum_step_displacement_m": .005,
    "maximum_contact_penetration_m": .005,
    "initial_height_tolerance_m": .002,
    "initial_hypotheses": "public_interval_midpoint_and_four_xy_corners",
    "main_hypothesis": "midpoint",
    "unknown_constraint": "same_continuous_support_clip_only_denied_body_after_engine_step",
    "object_unknown_sweep_projection": "orientation_independent_cylinder_bounding_sphere",
    "source_xml_allowed": False,
    "saved_integration_state_allowed": False,
}


def parameters():
    return deepcopy(PARAMETERS)


def _numbers(values):
    return " ".join(format(float(value), ".17g") for value in values)


def build_xml(continuous_map, public_domain, initial_xy):
    """Generate a standalone scene; the API deliberately has no XML argument."""
    validate_domain(public_domain)
    require(continuous_map.get("schema_version") == MAP_VERSION, "continuous map version")
    vector(initial_xy, 2, "initial xy")
    ground = continuous_map["ground"]
    require(ground is not None, "ground required")
    floor = sum(ground["height_interval_m"]) / 2
    current = continuous_map["current_object"]
    require(current is not None and current["status"] == "association_ready",
            "associated current object required")
    robot = current["robot_state"]["position_m"]
    root = ET.Element("mujoco", {"model": "spatial-history-r4-public-reconstruction-v1"})
    ET.SubElement(root, "compiler", {"angle": "radian"})
    ET.SubElement(root, "option", {
        "timestep": _numbers((PARAMETERS["timestep_s"],)),
        "gravity": _numbers(public_domain["gravity_mps2"]),
        "integrator": "Euler",
    })
    default = ET.SubElement(root, "default")
    ET.SubElement(default, "geom", {"friction": _numbers(public_domain["friction"]),
                                    "condim": "3"})
    world = ET.SubElement(root, "worldbody")
    ET.SubElement(world, "geom", {"name": "public_ground", "type": "plane",
                                  "pos": _numbers((0., 0., floor)), "size": "5 5 .1"})
    wall_records = []
    height = public_domain["obstacle_height_m"]
    for index, rectangle in enumerate(continuous_map["observed_wall_interval_rectangles_xy_m"]):
        vector(rectangle, 4, "observed wall interval rectangle")
        require(rectangle[0] < rectangle[1] and rectangle[2] < rectangle[3],
                "observed wall interval extent")
        name = f"observed_wall_{index:04d}"
        ET.SubElement(world, "geom", {
            "name": name,
            "type": "box",
            "pos": _numbers(((rectangle[0] + rectangle[1]) / 2,
                              (rectangle[2] + rectangle[3]) / 2,
                              floor + height / 2)),
            "size": _numbers(((rectangle[1] - rectangle[0]) / 2,
                               (rectangle[3] - rectangle[2]) / 2,
                               height / 2)),
        })
        wall_records.append({"geom_name": name, "rectangle_xy_m": list(rectangle),
                             "source": "observed_wall_interval"})
    object_body = ET.SubElement(world, "body", {
        "name": "object", "pos": _numbers((*initial_xy,
                                               floor + public_domain["object_half_height_m"]))})
    ET.SubElement(object_body, "freejoint", {"name": "object_free"})
    ET.SubElement(object_body, "geom", {
        "name": "object_geom", "type": "cylinder",
        "size": _numbers((public_domain["object_radius_m"],
                           public_domain["object_half_height_m"])),
        "mass": _numbers((public_domain["object_mass_kg"],)),
    })
    pusher_body = ET.SubElement(world, "body", {
        "name": "pusher", "pos": _numbers(robot)})
    ET.SubElement(pusher_body, "joint", {"name": "pusher_x", "type": "slide",
                                               "axis": "1 0 0"})
    ET.SubElement(pusher_body, "joint", {"name": "pusher_y", "type": "slide",
                                               "axis": "0 1 0"})
    ET.SubElement(pusher_body, "geom", {
        "name": "pusher_geom", "type": "box",
        "size": _numbers(public_domain["pusher_half_size_m"]),
        "mass": _numbers((public_domain["pusher_mass_kg"],)),
    })
    actuator = ET.SubElement(root, "actuator")
    for joint, axis in (("pusher_x", "x"), ("pusher_y", "y")):
        ET.SubElement(actuator, "velocity", {
            "name": f"servo_{axis}", "joint": joint,
            "kv": _numbers((public_domain["velocity_servo_kv"],)),
            "ctrllimited": "true",
            "ctrlrange": _numbers((-public_domain["control_limit_per_axis_mps"],
                                    public_domain["control_limit_per_axis_mps"])),
            "forcelimited": "true",
            "forcerange": _numbers((-public_domain["force_limit_per_axis_n"],
                                     public_domain["force_limit_per_axis_n"])),
        })
    xml = ET.tostring(root, encoding="unicode")
    return xml, {
        "builder": VERSION,
        "source": "supplied_public_continuous_map_and_domain_constants_only",
        "xml_sha256": hashlib.sha256(xml.encode("utf-8")).hexdigest(),
        "wall_geometries": wall_records,
        "source_xml_used": False,
        "saved_integration_state_used": False,
    }


class _Scene:
    def __init__(self, xml, current):
        require(mj.__version__ == MUJOCO_VERSION, "pinned MuJoCo version mismatch")
        require(np.__version__ == NUMPY_VERSION, "pinned NumPy version mismatch")
        self.model = mj.MjModel.from_xml_string(xml)
        self.data = mj.MjData(self.model)
        self.object_qpos = int(self.model.jnt_qposadr[self.model.joint("object_free").id])
        self.object_dof = int(self.model.jnt_dofadr[self.model.joint("object_free").id])
        self.pusher_qpos = [int(self.model.jnt_qposadr[self.model.joint(name).id])
                            for name in ("pusher_x", "pusher_y")]
        self.pusher_dof = [int(self.model.jnt_dofadr[self.model.joint(name).id])
                           for name in ("pusher_x", "pusher_y")]
        self.pusher_base = list(current["robot_state"]["position_m"][:2])
        velocity = current["interval_mean_velocity_mps"]
        self.data.qvel[self.object_dof:self.object_dof + 3] = velocity
        self.data.qvel[self.pusher_dof] = current["robot_state"]["velocity_mps"][:2]
        mj.mj_forward(self.model, self.data)

    def position(self, body):
        return self.data.body("object" if body == 0 else "pusher").xpos[:2].tolist()

    def velocity(self, body):
        value = np.empty(6, dtype=np.float64)
        mj.mj_objectVelocity(self.model, self.data, mj.mjtObj.mjOBJ_BODY,
                             self.model.body("object" if body == 0 else "pusher").id,
                             value, 0)
        return value[3:].tolist()

    def set_xy_and_stop_planar(self, body, xy):
        if body == 0:
            self.data.qpos[self.object_qpos:self.object_qpos + 2] = xy
            self.data.qvel[self.object_dof:self.object_dof + 2] = 0.
        else:
            self.data.qpos[self.pusher_qpos] = np.asarray(xy) - self.pusher_base
            self.data.qvel[self.pusher_dof] = 0.
        mj.mj_forward(self.model, self.data)

    def contacts(self):
        result = []
        for index in range(self.data.ncon):
            contact = self.data.contact[index]
            force = np.empty(6, dtype=np.float64)
            mj.mj_contactForce(self.model, self.data, index, force)
            result.append({
                "geoms": sorted(self.model.geom(int(geom)).name for geom in contact.geom),
                "distance_m": float(contact.dist),
                "normal_force_n": float(force[0]),
            })
        return result


def _simulate(continuous_map, controls, public_domain, initial_xy, *, step_count=None):
    xml, scene_provenance = build_xml(continuous_map, public_domain, initial_xy)
    scene = _Scene(xml, continuous_map["current_object"])
    geometry_parameters = continuous_map["geometry_parameters"]
    observed_floor = _rectangles_union(
        continuous_map["observed_floor_support_rectangles_xy_m"])
    observed_walls = _rectangles_union(
        continuous_map["observed_wall_interval_rectangles_xy_m"])
    supports = []
    initial_positions = [list(initial_xy), scene.position(1)]
    for body in (0, 1):
        own = _initial_footprint(body, initial_positions[body], public_domain,
                                 geometry_parameters)
        support = unary_union((observed_floor, observed_walls, own))
        shapely.prepare(support)
        supports.append(support)
    sweep_domain = deepcopy(public_domain)
    sweep_domain["object_radius_m"] = math.hypot(
        public_domain["object_radius_m"], public_domain["object_half_height_m"])
    steps = PARAMETERS["steps"] if step_count is None else step_count
    require(type(steps) is int and 0 <= steps <= PARAMETERS["steps"], "simulation step count")
    dt = PARAMETERS["timestep_s"]
    trace = []
    provenance = _ContactLog()
    maximum_displacement = 0.
    maximum_penetration = 0.
    maximum_tilt = 0.
    numerical_failure_step = None

    def sample(step, contacts, unknown_bodies):
        object_position = scene.data.body("object").xpos.tolist()
        pusher_position = scene.data.body("pusher").xpos.tolist()
        axis = scene.data.body("object").xmat.reshape(3, 3)[:, 2].tolist()
        positive = [contact for contact in contacts
                    if contact["distance_m"] <= 0 and
                    contact["normal_force_n"] > PARAMETERS["contact_force_threshold_n"]]
        object_wall = any("object_geom" in contact["geoms"] and
                          any(name.startswith("observed_wall_") for name in contact["geoms"])
                          for contact in positive)
        pusher_wall = any("pusher_geom" in contact["geoms"] and
                          any(name.startswith("observed_wall_") for name in contact["geoms"])
                          for contact in positive)
        pair = any({"object_geom", "pusher_geom"}.issubset(contact["geoms"])
                   for contact in positive)
        trace.append({
            "step_index": step,
            "time_s": step * dt,
            "object_position_m": object_position,
            "object_velocity_mps": scene.velocity(0),
            "object_axis_world": axis,
            "robot_position_m": pusher_position,
            "robot_velocity_mps": scene.velocity(1),
            "servo_force_n": scene.data.actuator_force.tolist(),
            "object_obstacle_contact": object_wall or 0 in unknown_bodies,
            "robot_obstacle_contact": pusher_wall or 1 in unknown_bodies,
            "object_robot_contact": pair,
        })

    sample(0, [], set())
    for step in range(1, steps + 1):
        previous = [scene.position(0), scene.position(1)]
        command = controls["ee_velocity_mps"][(step - 1) // 50]
        scene.data.ctrl[:] = command[:2]
        mj.mj_step(scene.model, scene.data)
        raw_contacts = scene.contacts()
        for contact in raw_contacts:
            if (contact["distance_m"] > 0 or
                    contact["normal_force_n"] <= PARAMETERS["contact_force_threshold_n"]):
                continue
            names = contact["geoms"]
            if {"object_geom", "pusher_geom"}.issubset(names):
                provenance.record(step, "object_and_pusher", "object_pusher")
            for body, geom in (("object", "object_geom"), ("pusher", "pusher_geom")):
                walls = [name for name in names if name.startswith("observed_wall_")]
                if geom in names and walls:
                    provenance.record(step, body, "observed_wall_interval",
                                      {"geom_names": walls})
        unknown_bodies = set()
        for body in (0, 1):
            proposed = scene.position(body)
            clipped, uncovered = _clip_to_support(
                body, previous[body], proposed, supports[body], sweep_domain,
                geometry_parameters)
            if uncovered is not None:
                detail = _uncovered_detail(continuous_map, uncovered)
                provenance.record(step, "object" if body == 0 else "pusher",
                                  detail.pop("source"), detail)
                unknown_bodies.add(body)
                scene.set_xy_and_stop_planar(body, clipped)
        movement = max(math.dist(previous[body], scene.position(body)) for body in (0, 1))
        maximum_displacement = max(maximum_displacement, movement)
        maximum_penetration = max(maximum_penetration,
                                  max((-contact["distance_m"] for contact in raw_contacts), default=0.))
        axis_z = float(scene.data.body("object").xmat.reshape(3, 3)[2, 2])
        maximum_tilt = max(maximum_tilt, math.acos(max(-1., min(1., axis_z))))
        sample(step, raw_contacts, unknown_bodies)
        state_finite = np.isfinite(scene.data.qpos).all() and np.isfinite(scene.data.qvel).all()
        if (not state_finite or any(warning.number for warning in scene.data.warning)
                or movement > PARAMETERS["maximum_step_displacement_m"]
                or maximum_penetration > PARAMETERS["maximum_contact_penetration_m"]):
            numerical_failure_step = step
            break
    return {
        "status": "numerical_failure" if numerical_failure_step else "complete",
        "trajectory": trace,
        "contact_provenance": provenance.intervals,
        "numerical_audit": {
            "numerical_failure_step": numerical_failure_step,
            "maximum_step_displacement_m": maximum_displacement,
            "maximum_contact_penetration_m": maximum_penetration,
            "maximum_object_tilt_rad": maximum_tilt,
            "mujoco_version": mj.__version__,
            "numpy_version": np.__version__,
        },
        "generated_scene": {**scene_provenance, "xml": xml},
    }


def predict(continuous_map, controls, goal, public_domain, dynamics_parameters,
            readout_parameters):
    """Run the same registered midpoint and interval corners as M-SIMPLE."""
    _fixed(dynamics_parameters, PARAMETERS, "M-PHYS dynamics parameters")
    validate_controls(controls)
    validate_domain(public_domain)
    require(continuous_map.get("schema_version") == MAP_VERSION, "continuous map version")
    require(not ({"labels", "actual_future", "world_name", "goal", "source_xml",
                  "snapshot", "integration"} & set(continuous_map)),
            "private/control field in continuous map")
    output = {
        "schema_version": VERSION,
        "system": "M-PHYS",
        "status": "perception_unresolved",
        "prediction": None,
        "trajectory": None,
        "certificate": None,
        "contact_provenance": [],
        "numerical_audit": None,
        "generated_scene": None,
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
        output["initial_sensitivity"].append({
            "name": hypothesis["name"],
            "position_xy_m": hypothesis["position_xy_m"],
            "status": simulation["status"],
            "prediction": task["prediction"],
            "nominal_success": task["nominal_success"],
            "contact_provenance": simulation["contact_provenance"],
            "numerical_audit": simulation["numerical_audit"],
            "generated_scene_sha256": simulation["generated_scene"]["xml_sha256"],
        })
        if hypothesis["main"]:
            output.update(
                status=("complete" if simulation["status"] == "complete" and
                        task["status"] == "nominal_readout_complete" else
                        simulation["status"] if simulation["status"] != "complete"
                        else "task_readout_unresolved"),
                prediction=task["prediction"], trajectory=simulation["trajectory"],
                contact_provenance=simulation["contact_provenance"],
                numerical_audit=simulation["numerical_audit"],
                generated_scene=simulation["generated_scene"],
            )
            bounding_radius = math.hypot(public_domain["object_radius_m"],
                                         public_domain["object_half_height_m"])
            output["certificate"] = audit_trajectory(
                continuous_map, simulation["trajectory"], public_domain,
                object_radius_m=bounding_radius)
            output["certificate"].update(
                object_projection="orientation_independent_cylinder_bounding_sphere",
                object_projection_radius_m=bounding_radius)
    output["initialization"] = {
        "assumption": "upright_free_cylinder_public_backward_interval_mean",
        "main_hypothesis": "midpoint",
        "position_intervals_m": deepcopy(current["position_intervals_m"]),
        "velocity_intervals_mps": deepcopy(current["interval_mean_velocity_intervals_mps"]),
        "hypotheses": [{"name": value["name"],
                        "position_xy_m": value["position_xy_m"]}
                       for value in hypotheses],
        "initial_orientation": "upright",
        "initial_angular_velocity_radps": [0., 0., 0.],
    }
    return output
