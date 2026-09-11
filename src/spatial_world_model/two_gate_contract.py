"""Standard-library contract and offline scoring for the SH-04-R2 fixture.

No simulator, filesystem, model, or legacy research implementation is imported.
Public v1 binds the approved 121-frame clock; private trajectory truth is scored
separately and is never accepted by ``model_input``. See docs/METHOD.md.
"""
from copy import deepcopy
import hashlib
import json
import math

from .pair_contract import frame, keys, number, require, vector


VERSION = "spatial-history-two-gate-public-v1"
NAMES = ("LL", "LR", "RL", "RR")
GOAL_KEYS = ("goal_center_xy_m goal_x_bounds_m goal_y_bounds_m "
             "require_ordered_actual_gate_passage gate_attempt_rule goal_containment "
             "settled_interval_s maximum_object_linear_speed_mps "
             "containment_boundary_tolerance_m collision_is_task_failure failure_cost success_cost")
SAMPLE_KEYS = ("step_index time_s object_position_m object_axis_world "
               "object_linear_velocity_mps pusher_position_m actuator_force_n "
               "contacts object_visible_pixels")
ATTEMPT_RULE = ("forward center-plane crossing starts attempt; center retreat below plane "
                "cancels; rear clearance completes same active attempt")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _bounds(value, where):
    vector(value, 2, where)
    require(value[0] < value[1], f"{where}: unordered bounds")


def _positive(value, where):
    number(value, where)
    require(value > 0, f"{where}: must be positive")


def _goal_valid(goal):
    keys(goal, GOAL_KEYS, "goal")
    for name in ("goal_x_bounds_m", "goal_y_bounds_m", "settled_interval_s"):
        _bounds(goal[name], "goal." + name)
    vector(goal["goal_center_xy_m"], 2, "goal.center")
    require(goal["require_ordered_actual_gate_passage"] is True, "ordered passage required")
    require(goal["collision_is_task_failure"] is False, "contact is not task failure")
    require(goal["gate_attempt_rule"] == ATTEMPT_RULE, "unknown passage rule")
    require(goal["goal_containment"] == "entire actual cylinder horizontal projection",
            "unknown containment rule")
    for name in ("maximum_object_linear_speed_mps", "containment_boundary_tolerance_m"):
        _positive(goal[name], "goal." + name)
    for name, expected in (("failure_cost", 1), ("success_cost", 0)):
        number(goal[name], name)
        require(goal[name] == expected, "unsupported task cost")


def validate_config(config):
    """Validate numerical inputs; operational authorization is checked by ops."""
    required = set(("version status scene_direction_approved numeric_protocol_approved "
                    "generation_authorized training_authorized simulator physics_reference "
                    "physics_reference_sha256 physics_reference_policy worlds world_weights "
                    "geometry observation controls task_success engineering_audit budget_proposal").split())
    optional = {"approval_decision", "proposal_source", "proposal_sha256"}
    require(isinstance(config, dict) and required <= set(config)
            and set(config) <= required | optional, "config fields")
    for name in ("scene_direction_approved", "numeric_protocol_approved",
                 "generation_authorized", "training_authorized"):
        require(type(config[name]) is bool, "config approval must be boolean")
    require(config["worlds"] == list(NAMES), "four ordered worlds required")
    vector(config["world_weights"], 4, "world weights")
    require(config["world_weights"] == [0.25] * 4, "v1 requires equal world weights")
    keys(config["simulator"], "mujoco numpy timestep_s", "simulator")
    require(config["simulator"]["mujoco"] == "3.3.7"
            and config["simulator"]["numpy"] == "2.2.6", "simulator versions")
    number(config["simulator"]["timestep_s"], "timestep")
    require(config["simulator"]["timestep_s"] == 0.002, "v1 physics clock")
    geometry = config["geometry"]
    keys(geometry, "gate_y_m gate_center_x_m gate_clear_width_m wall_thickness_m wall_height_m "
         "cross_wall_outer_x_m side_wall_inner_x_m side_wall_y_bounds_m side_wall_thickness_m "
         "object_radius_m object_half_height_m object_mass_kg object_initial_position_m "
         "pusher_half_size_m pusher_mass_kg pusher_initial_position_m initial_body_velocities "
         "friction velocity_servo_kv control_limit_per_axis_mps force_limit_per_axis_n "
         "visual_occlusion_screen", "geometry")
    for name in ("gate_y_m", "cross_wall_outer_x_m", "side_wall_inner_x_m", "side_wall_y_bounds_m"):
        _bounds(geometry[name], name)
    keys(geometry["gate_center_x_m"], "L R", "gate centers")
    for item in geometry["gate_center_x_m"].values():
        number(item, "gate center")
    for name in ("gate_clear_width_m", "wall_thickness_m", "wall_height_m",
                 "side_wall_thickness_m", "object_radius_m", "object_half_height_m",
                 "object_mass_kg", "pusher_mass_kg", "velocity_servo_kv",
                 "control_limit_per_axis_mps", "force_limit_per_axis_n"):
        _positive(geometry[name], name)
    for name in ("object_initial_position_m", "pusher_initial_position_m", "pusher_half_size_m", "friction"):
        vector(geometry[name], 3, name)
    require(all(v > 0 for v in geometry["pusher_half_size_m"]), "invalid pusher dimensions")
    require(all(v >= 0 for v in geometry["friction"]), "negative friction")
    require(geometry["visual_occlusion_screen"] is False, "v1 has no occlusion screen")
    require(geometry["initial_body_velocities"] == "zero", "initial velocity rule")
    _goal_valid(config["task_success"])
    obs = config["observation"]
    require(isinstance(obs, dict), "observation config")
    for name, expected in (("history_frame_count", 121), ("recent_frames", 2),
                           ("history_duration_s", 12.0), ("sample_s", 0.1),
                           ("settle_before_history_s", 0.5)):
        number(obs[name], name)
        require(obs[name] == expected, "public v1 history clock mismatch")
    require(type(obs["history_frame_count"]) is int and type(obs["recent_frames"]) is int,
            "frame counts must be integers")
    audit = config["engineering_audit"]
    _bounds(audit["object_height_range_m"], "height range")
    for name in ("maximum_object_tilt_rad", "maximum_dynamic_body_contact_penetration_m",
                 "maximum_dynamic_body_translation_per_physics_step_m", "contact_force_min_n",
                 "future_visibility_sample_s", "minimum_fixed_single_view_information_regret"):
        _positive(audit[name], name)
    require(audit["future_visibility_sample_s"] == 0.1, "v1 visibility cadence")
    require(type(audit["minimum_successful_actions_each_world"]) is int
            and 1 <= audit["minimum_successful_actions_each_world"] <= 4, "success count")
    require(type(audit["critical_interaction_object_visible_pixels"]) is int
            and audit["critical_interaction_object_visible_pixels"] == 0, "visibility count")
    _expand_controls(config)


def _expand_controls(config):
    controls = config["controls"]
    keys(controls, "kind phase_duration_s phase_vy_mps phase_vz_mps phase_vx_mps sample_s "
         "control_steps horizon_s runtime_control_uses_object_truth", "controls config")
    require(controls["kind"] == "ee_velocity_world_mps", "control semantics")
    require(controls["runtime_control_uses_object_truth"] is False, "truth feedback forbidden")
    number(controls["sample_s"], "control sample")
    number(controls["horizon_s"], "control horizon")
    require(controls["sample_s"] == 0.1 and controls["horizon_s"] == 20.0,
            "public v1 control clock mismatch")
    require(type(controls["control_steps"]) is int and controls["control_steps"] == 200,
            "v1 control count")
    require(isinstance(controls["phase_duration_s"], list) and controls["phase_duration_s"], "phases")
    length = len(controls["phase_duration_s"])
    for name in ("phase_duration_s", "phase_vy_mps", "phase_vz_mps"):
        vector(controls[name], length, name)
    keys(controls["phase_vx_mps"], "LL LR RL RR", "vx phases")
    result = {}
    limit = config["geometry"]["control_limit_per_axis_mps"]
    for action in NAMES:
        vector(controls["phase_vx_mps"][action], length, "vx phases")
        expanded = []
        for duration, vx, vy, vz in zip(controls["phase_duration_s"],
                                      controls["phase_vx_mps"][action],
                                      controls["phase_vy_mps"], controls["phase_vz_mps"]):
            require(duration > 0, "nonpositive phase")
            count = round(duration / controls["sample_s"])
            require(math.isclose(count * controls["sample_s"], duration, rel_tol=0, abs_tol=1e-9),
                    "phase is not a whole control sample")
            require(vz == 0 and all(abs(v) <= limit for v in (vx, vy)), "control exceeds limits")
            expanded.extend({"duration_s": controls["sample_s"], "ee_velocity_mps": [vx, vy, vz]}
                            for _ in range(count))
        require(len(expanded) == controls["control_steps"], "expanded control length")
        result[action] = expanded
    require(len({_canonical(value) for value in result.values()}) == 4, "duplicate actions")
    return result


def expand_controls(config):
    """Expand registered phases into four 200-step numerical control sequences."""
    validate_config(config)
    return _expand_controls(config)


def _public_valid(public):
    keys(public, "schema_version history actions goal", "public")
    require(public["schema_version"] == VERSION, "public version")
    history = public["history"]
    require(isinstance(history, list) and len(history) == 121, "public v1 requires 121 history frames")
    for index, value in enumerate(history):
        frame(value, f"history[{index}]")
        require(math.isclose(value["time_s"], 0.5 + index * 0.1, rel_tol=0, abs_tol=1e-9),
                "history contains future, missing, or misaligned frame")
    require(len({(f["width"], f["height"]) for f in history}) == 1, "resolution changed")
    keys(public["actions"], "LL LR RL RR", "public actions")
    for action in public["actions"].values():
        require(isinstance(action, list) and len(action) == 200, "public action length")
        for control in action:
            keys(control, "duration_s ee_velocity_mps", "public control")
            number(control["duration_s"], "duration")
            vector(control["ee_velocity_mps"], 3, "velocity")
            require(control["duration_s"] == 0.1, "public control cadence")
            require(control["ee_velocity_mps"][2] == 0
                    and all(abs(v) <= 0.5 for v in control["ee_velocity_mps"]), "public velocity limits")
    require(len({_canonical(v) for v in public["actions"].values()}) == 4, "duplicate public actions")
    _goal_valid(public["goal"])
    require(public["goal"]["settled_interval_s"] == [19, 20], "v1 settlement interval")


def make_public(history, config):
    """Create a standalone public record; no world IDs or private geometry."""
    validate_config(config)
    public = deepcopy({"schema_version": VERSION, "history": history,
                       "actions": _expand_controls(config), "goal": config["task_success"]})
    _public_valid(public)
    return public


def model_input(public, action_name, history_indices=None):
    """Validate full public input before selecting history; return no selectors."""
    _public_valid(public)
    require(type(action_name) is str and action_name in NAMES, "unknown action")
    if history_indices is None:
        history = public["history"]
    else:
        require(isinstance(history_indices, (list, tuple)) and history_indices, "history indices")
        require(all(type(i) is int and 0 <= i < 121 for i in history_indices), "invalid history index")
        require(list(history_indices) == sorted(set(history_indices)), "indices must be unique and chronological")
        history = [public["history"][i] for i in history_indices]
    return deepcopy({"history": history, "controls": public["actions"][action_name], "goal": public["goal"]})


def _sample_valid(sample, index):
    keys(sample, SAMPLE_KEYS, f"sample[{index}]")
    require(type(sample["step_index"]) is int and sample["step_index"] == index, "sample index")
    number(sample["time_s"], "sample time")
    require(math.isclose(sample["time_s"], index * 0.002, rel_tol=0, abs_tol=1e-9), "sample clock")
    for name in ("object_position_m", "object_axis_world", "object_linear_velocity_mps", "pusher_position_m"):
        vector(sample[name], 3, name)
    vector(sample["actuator_force_n"], 2, "actuator force")
    require(abs(sum(v * v for v in sample["object_axis_world"]) - 1) <= 1e-6, "object axis norm")
    require(sample["object_visible_pixels"] is None or
            type(sample["object_visible_pixels"]) is int and sample["object_visible_pixels"] >= 0,
            "visibility must be a count or missing")
    require(isinstance(sample["contacts"], list), "contacts must be a list")
    for contact in sample["contacts"]:
        keys(contact, "geoms distance_m normal_force_n", "contact")
        require(isinstance(contact["geoms"], list) and len(contact["geoms"]) == 2
                and all(type(g) is str and g for g in contact["geoms"]), "contact geom names")
        number(contact["distance_m"], "contact distance")
        number(contact["normal_force_n"], "contact normal force")


def _support(axis, radius, half_height):
    return [radius * math.sqrt(max(0, 1 - v * v)) + half_height * abs(v) for v in axis]


def assess_trajectory(samples, config, *, world_name):
    """Score a complete raw trajectory; missing visibility requests are returned.

    ``raw_task_success`` describes geometry and settlement even when physics is
    invalid. ``task_success`` is None for invalid physics; callers must not turn
    those branches into ordinary failures in an information-value matrix.
    """
    validate_config(config)
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
                    center_x = geom["gate_center_x_m"][world_name[gate]]
                    opening = abs(cross_x - center_x) <= geom["gate_clear_width_m"] / 2 + epsilon
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


def audit_family(public_worlds, outcomes, config):
    """Audit all fixed-frame partitions; booleans must come from valid physics.

    Each decision uses the SAME selected frame for all candidate queries. A
    retriever choosing frames after reading the full history is a different
    information condition and is not bounded by this diagnostic.
    """
    validate_config(config)
    keys(public_worlds, "LL LR RL RR", "public worlds")
    keys(outcomes, "LL LR RL RR", "outcomes")
    for world in NAMES:
        _public_valid(public_worlds[world])
        keys(outcomes[world], "LL LR RL RR", "world outcomes")
        require(all(type(v) is bool for v in outcomes[world].values()), "outcomes need valid-physics booleans")
    controls = _expand_controls(config)
    checks = {
        "registered_common_actions": all(p["actions"] == controls for p in public_worlds.values()),
        "registered_common_goal": all(p["goal"] == config["task_success"] for p in public_worlds.values()),
        "same_recent_public_inputs": len({_canonical(p["history"][-2:]) for p in public_worlds.values()}) == 1,
        "same_history_metadata": True,
        "each_world_has_success": all(sum(outcomes[w].values()) >= config["engineering_audit"]["minimum_successful_actions_each_world"] for w in NAMES),
    }
    for index in range(121):
        metadata = [{k: v for k, v in public_worlds[w]["history"][index].items()
                     if k not in ("rgb", "depth_m")} for w in NAMES]
        checks["same_history_metadata"] &= len({_canonical(v) for v in metadata}) == 1
    bases = {w: _sha({"recent": public_worlds[w]["history"][-2:],
                      "actions": public_worlds[w]["actions"], "goal": public_worlds[w]["goal"]}) for w in NAMES}
    rows = []
    for index in range(121):
        partitions = {}
        for world in NAMES:
            key = (bases[world], _sha(public_worlds[world]["history"][index]))
            partitions.setdefault(key, []).append(world)
        groups, total_regret = [], 0.0
        for group in partitions.values():
            costs = {action: sum(not outcomes[w][action] for w in group) / len(group) for action in NAMES}
            oracle = sum(not any(outcomes[w].values()) for w in group) / len(group)
            regret = min(costs.values()) - oracle
            total_regret += len(group) / 4 * regret
            groups.append({"worlds": group, "action_expected_failure_cost": costs,
                           "fully_informed_expected_failure_cost": oracle, "information_regret": regret})
        rows.append({"frame_index": index, "equivalence_groups": groups, "information_regret": total_regret})
    threshold = config["engineering_audit"]["minimum_fixed_single_view_information_regret"]
    checks["every_fixed_single_view_information_regret"] = all(row["information_regret"] >= threshold for row in rows)
    return {"checks": checks, "contract_audit_passed": all(checks.values()),
            "accepted": all(checks.values()), "failed_checks": [k for k, v in checks.items() if not v],
            "frame_information": rows,
            "fixed_single_view_audit": rows,
            "minimum_information_regret": min(row["information_regret"] for row in rows),
            "outcomes": deepcopy(outcomes), "physics_and_geometry_recovery_verified": False}
