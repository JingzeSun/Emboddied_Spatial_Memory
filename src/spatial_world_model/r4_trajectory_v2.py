"""R4 per-gate trajectory audit, derived from D-071 without threshold changes.

Only gate center/width lookup differs from the original assessor. Old source
bytes remain intact. See METHOD/DATA for the independent R4 source binding.
"""
from copy import deepcopy
import math
from .pair_contract import require
from .two_gate_contract import NAMES, _sample_valid, _support
from .r4_families_v2 import validate_family_config


def assess_trajectory(samples, config, *, world_name):
    """Score a complete raw trajectory; missing visibility requests are returned.

    ``raw_task_success`` describes geometry and settlement even when physics is
    invalid. ``task_success`` is None for invalid physics; callers must not turn
    those branches into ordinary failures in an information-value matrix.
    """
    validate_family_config(config)
    require(type(world_name) is str and world_name in NAMES, "unknown audit world")
    require(isinstance(samples, list) and len(samples) == 10001, "need t0 and every 0.002 s through 20 s")
    for index, sample in enumerate(samples):
        _sample_valid(sample, index)
    geom, task, audit = config["geometry"], config["task_success"], config["engineering_audit"]
    epsilon = task["containment_boundary_tolerance_m"]
    support = [_support(s["object_axis_world"], geom["object_radius_m"], geom["object_half_height_m"])
               for s in samples]
    checks = {name: True for name in ("finite_states", "height", "tilt", "force_limit", "corridor_bounds",
                                     "penetration", "step_translation")}
    maxima = {"penetration_m": 0.0, "step_translation_m": 0.0, "actuator_force_n": 0.0,
              "object_tilt_rad": 0.0}
    first_failure = {}
    required = set(range(0, len(samples), 50))
    critical = set()
    events = []
    active = [None, None]
    completed = [[], []]
    attempts = [0, 0]
    goal_all, speed_all = True, True
    positive_gate_contact_steps = []
    positive_obstacle_contact_steps = []

    def check(name, condition, index):
        if not condition:
            checks[name] = False
            first_failure.setdefault(name, index)

    for index, (sample, extent) in enumerate(zip(samples, support)):
        pos = sample["object_position_m"]
        check("height", audit["object_height_range_m"][0] <= pos[2] <= audit["object_height_range_m"][1], index)
        tilt = math.acos(max(-1, min(1, sample["object_axis_world"][2])))
        maxima["object_tilt_rad"] = max(maxima["object_tilt_rad"], tilt)
        check("tilt", tilt <= audit["maximum_object_tilt_rad"], index)
        force = max(abs(v) for v in sample["actuator_force_n"])
        maxima["actuator_force_n"] = max(maxima["actuator_force_n"], force)
        check("force_limit", force <= geom["force_limit_per_axis_n"], index)
        for axis, bounds in enumerate((geom["side_wall_inner_x_m"], geom["side_wall_y_bounds_m"])):
            check("corridor_bounds", pos[axis] - extent[axis] >= bounds[0] - epsilon
                  and pos[axis] + extent[axis] <= bounds[1] + epsilon, index)
        if index:
            for field in ("object_position_m", "pusher_position_m"):
                delta = math.dist(sample[field], samples[index - 1][field])
                maxima["step_translation_m"] = max(maxima["step_translation_m"], delta)
                check("step_translation", delta <= audit["maximum_dynamic_body_translation_per_physics_step_m"], index)
        obstacle_contact, gate_contact = False, False
        for contact in sample["contacts"]:
            names = contact["geoms"]
            if "object" in names or "pusher" in names:
                penetration = max(0.0, -contact["distance_m"])
                maxima["penetration_m"] = max(maxima["penetration_m"], penetration)
                check("penetration", penetration <= audit["maximum_dynamic_body_contact_penetration_m"], index)
            positive = contact["distance_m"] <= 0 and contact["normal_force_n"] > audit["contact_force_min_n"]
            if "object" in names and positive:
                obstacle_contact |= any(n.startswith(("gate_", "side_")) for n in names)
                gate_contact |= any(n.startswith("gate_") for n in names)
        if obstacle_contact:
            critical.add(index)
            positive_obstacle_contact_steps.append(index)
        if gate_contact:
            positive_gate_contact_steps.append(index)

        if index:
            previous = samples[index - 1]
            for gate, gate_y in enumerate(geom["gate_y_m"]):
                if active[gate] is not None and pos[1] < gate_y:
                    event = events[active[gate]]
                    event["status"] = "cancelled"
                    event["cancel_index"] = index
                    active[gate] = None
                if previous["object_position_m"][1] < gate_y <= pos[1]:
                    attempts[gate] += 1
                    fraction = ((gate_y - previous["object_position_m"][1]) /
                                (pos[1] - previous["object_position_m"][1]))
                    cross_time = previous["time_s"] + fraction * (sample["time_s"] - previous["time_s"])
                    cross_x = previous["object_position_m"][0] + fraction * (pos[0] - previous["object_position_m"][0])
                    center_x = geom["gate_centers_x_m"][gate][world_name[gate]]
                    opening = abs(cross_x - center_x) <= geom["gate_widths_m"][gate] / 2 + epsilon
                    ordered = gate == 0 or any(t < cross_time for t in completed[0])
                    event = {"gate_index": gate, "attempt_index": attempts[gate],
                             "cross_before_index": index - 1, "cross_after_index": index,
                             "cross_time_s": cross_time, "cross_x_m": cross_x,
                             "opening_valid": opening, "ordered": ordered,
                             "status": "active" if opening and ordered else "invalid",
                             "cancel_index": None, "completion_index": None, "completion_time_s": None}
                    events.append(event)
                    active[gate] = len(events) - 1 if opening and ordered else None
                    critical.update((index - 1, index))
                if (active[gate] is not None and
                        pos[1] - extent[1] >= gate_y + geom["wall_thickness_m"] / 2 - epsilon):
                    event = events[active[gate]]
                    event.update(status="completed", completion_index=index, completion_time_s=sample["time_s"])
                    completed[gate].append(sample["time_s"])
                    active[gate] = None
                    critical.update((index - 1, index))
        if sample["time_s"] >= task["settled_interval_s"][0] - 1e-9:
            for axis, bounds in enumerate((task["goal_x_bounds_m"], task["goal_y_bounds_m"])):
                goal_all &= (pos[axis] - extent[axis] >= bounds[0] - epsilon
                             and pos[axis] + extent[axis] <= bounds[1] + epsilon)
            speed_all &= math.sqrt(sum(v * v for v in sample["object_linear_velocity_mps"])) <= task["maximum_object_linear_speed_mps"]
    required.update(critical)
    missing = sorted(i for i in required if samples[i]["object_visible_pixels"] is None)
    visible_critical = sorted(i for i in critical if samples[i]["object_visible_pixels"] not in (None, 0))
    physics_valid = all(checks.values())
    raw_success = bool(all(completed) and goal_all and speed_all)
    final = samples[-1]["object_position_m"]
    final_distance = math.sqrt(sum(max(bounds[0] - final[i], 0, final[i] - bounds[1]) ** 2
                                   for i, bounds in enumerate((task["goal_x_bounds_m"], task["goal_y_bounds_m"]))))
    return {"raw_task_success": raw_success, "task_success": raw_success if physics_valid else None,
            "physics_valid": physics_valid, "physics_checks": checks,
            "physics_failures": sorted(first_failure), "failures": sorted(first_failure),
            "first_physics_failure_indices": first_failure, "physics_maxima": maxima,
            "gate_events": events, "ordered_gate_passage": bool(all(completed)),
            "settled_containment": bool(goal_all), "settled_speed": bool(speed_all),
            "required_visibility_indices": sorted(required), "critical_visibility_indices": sorted(critical),
            "visibility_valid": not missing and not visible_critical,
            "visibility_checks": {"complete": not missing, "critical_out_of_view": not missing and not visible_critical},
            "missing_visibility_indices": missing, "visible_critical_indices": visible_critical,
            "positive_gate_contact_steps": positive_gate_contact_steps,
            "gate_contact_steps": len(positive_gate_contact_steps),
            "positive_obstacle_contact_steps": positive_obstacle_contact_steps,
            "terminal": {"object_position_m": deepcopy(final), "center_distance_to_goal_region_m": final_distance,
                         "object_linear_speed_mps": math.sqrt(sum(v * v for v in samples[-1]["object_linear_velocity_mps"]))}}
