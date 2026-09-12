"""R4 public query and prediction value contracts, standard library only.

No files, model state, labels, simulator or tensor backend are accessed.
Images remain flat, row-major JSON lists; tensorization belongs to each adapter.
See docs/DATA.md#r4-data and docs/METHOD.md#r4-common-contract.
"""
from copy import deepcopy
import math

from .pair_contract import frame, keys, number, require, vector
from .two_gate_contract import _goal_valid


VERSION = "spatial-history-r4-query-v1"
PREDICTION_VERSION = "spatial-history-r4-prediction-v1"
STEPS = 200
DT = 0.1
FRAME_FIELDS = ("rgb depth_m camera_position_m camera_xyzw intrinsics "
                "ee_position_m ee_velocity_mps previous_velocity_mps").split()
DOMAIN = {
    "gravity_mps2": [0.0, 0.0, -9.81],
    "object_radius_m": 0.07, "object_half_height_m": 0.04, "object_mass_kg": 0.15,
    "pusher_half_size_m": [0.15, 0.025, 0.025], "pusher_mass_kg": 0.5,
    "friction": [0.25, 0.005, 0.0001], "velocity_servo_kv": 100,
    "control_limit_per_axis_mps": 0.5, "force_limit_per_axis_n": 20,
    "obstacle_thickness_m": 0.05, "obstacle_height_m": 0.3,
    "depth_kind": "camera_axis_distance_m", "depth_invalid_value": 0,
    "depth_far_clip_m": 20.0,
    "camera_convention": "camera_to_world_xyzw_local_x_right_y_down_z_forward",
}


def domain_spec():
    """Common D-071 constants, never an instance geometry or body state."""
    return deepcopy(DOMAIN)


def _same_constants(value, expected, where):
    if isinstance(expected, dict):
        keys(value, " ".join(expected), where)
        for key in expected:
            _same_constants(value[key], expected[key], f"{where}.{key}")
    elif isinstance(expected, list):
        require(isinstance(value, list) and len(value) == len(expected), where)
        for item, ref in zip(value, expected):
            _same_constants(item, ref, where)
    elif type(expected) in (int, float):
        number(value, where)
        require(value == expected, f"{where}: changed common constant")
    else:
        require(type(value) is str and value == expected, f"{where}: changed convention")


def validate_domain(value):
    _same_constants(value, DOMAIN, "domain_spec")


def validate_goal(goal):
    _goal_valid(goal)
    require(goal["settled_interval_s"] == [19, 20], "settlement interval")
    require(goal["goal_y_bounds_m"] == [2.45, 2.85]
            and goal["goal_center_xy_m"][1] == 2.65, "registered y goal")
    tx = goal["goal_center_xy_m"][0]
    require(-0.12 <= tx <= 0.12, "goal translation outside R4 range")
    require(all(math.isclose(x, ref + tx, abs_tol=1e-12, rel_tol=0)
                for x, ref in zip(goal["goal_x_bounds_m"], [-0.25, 0.25])), "goal x bounds")
    require(goal["maximum_object_linear_speed_mps"] == 0.02
            and goal["containment_boundary_tolerance_m"] == 0.001, "goal precision changed")


def validate_controls(controls):
    keys(controls, "ee_velocity_mps duration_s", "controls")
    for name in controls:
        require(isinstance(controls[name], list) and len(controls[name]) == STEPS,
                "exactly 200 controls required")
    for velocity, duration in zip(controls["ee_velocity_mps"], controls["duration_s"]):
        vector(velocity, 3, "control velocity")
        number(duration, "control duration")
        require(duration == DT and velocity[2] == 0
                and all(abs(v) <= 0.5 for v in velocity), "control clock or units")


def _history_indices(mode, cut):
    require(type(mode) is str and mode in ("full", "recent", "prefix"), "history mode")
    if mode == "prefix":
        require(type(cut) is int and 0 <= cut <= 120, "prefix cut index")
        return list(range(cut + 1))
    require(cut is None, "cut only belongs to prefix queries")
    return list(range(121)) if mode == "full" else [119, 120]


def validate_query(query, *, history_mode="full", history_cut_index=None):
    """Validate an explicit public-only value. Mode/cut stay outside features.

    A prefix clock remains relative to the future decision, not its own end.
    This is value validation, not an operating-system file permission boundary.
    """
    keys(query, "history controls goal domain_spec", "query")
    indices = _history_indices(history_mode, history_cut_index)
    hist = query["history"]
    keys(hist, "time_s depth_valid " + " ".join(FRAME_FIELDS), "history")
    require(all(isinstance(v, list) and len(v) == len(indices) for v in hist.values()),
            "history column length")
    for local, original in enumerate(indices):
        time_s = hist["time_s"][local]
        number(time_s, "history clock")
        require(math.isclose(time_s, (original - 120) / 10, abs_tol=1e-9, rel_tol=0),
                "future, missing or misaligned history frame")
        # Reuse the old pixel/calibration validator with its nonnegative clock.
        raw = {key: hist[key][local] for key in FRAME_FIELDS}
        raw.update(time_s=0.5 + original / 10, width=64, height=64)
        frame(raw, "history frame")
        mask = hist["depth_valid"][local]
        require(isinstance(mask, list) and len(mask) == 4096
                and all(type(m) is bool and m == (d > 0)
                        for m, d in zip(mask, raw["depth_m"])), "depth validity mismatch")
    validate_controls(query["controls"])
    validate_goal(query["goal"])
    validate_domain(query["domain_spec"])


def from_public_query(public_query, *, history_mode="full", history_cut_index=None):
    """Adapt an already selected R2-style public value, without file access.

    Caller supplies exactly the requested prefix/recent/full frames. All source
    frames are validated, so this function never silently drops contamination.
    Returned RGB/depth lists preserve original values; no float32 conversion here.
    """
    keys(public_query, "history controls goal", "public query")
    indices = _history_indices(history_mode, history_cut_index)
    require(isinstance(public_query["history"], list)
            and len(public_query["history"]) == len(indices), "selected history length")
    columns = {key: [] for key in ["time_s", *FRAME_FIELDS, "depth_valid"]}
    for raw, original in zip(public_query["history"], indices):
        frame(raw, "source frame")
        require(raw["width"] == raw["height"] == 64, "native resolution required")
        require(math.isclose(raw["time_s"], 0.5 + original / 10, abs_tol=1e-9, rel_tol=0),
                "source clock mismatch")
        columns["time_s"].append((original - 120) / 10)
        for key in FRAME_FIELDS:
            columns[key].append(deepcopy(raw[key]))
        columns["depth_valid"].append([v > 0 for v in raw["depth_m"]])
    source_controls = public_query["controls"]
    require(isinstance(source_controls, list) and len(source_controls) == STEPS, "source controls")
    controls = {"ee_velocity_mps": [], "duration_s": []}
    for step in source_controls:
        keys(step, "ee_velocity_mps duration_s", "source control")
        for name in controls:
            controls[name].append(deepcopy(step[name]))
    result = {"history": columns, "controls": controls, "goal": deepcopy(public_query["goal"]),
              "domain_spec": domain_spec()}
    validate_query(result, history_mode=history_mode, history_cut_index=history_cut_index)
    return result


def validate_times(times):
    require(isinstance(times, list) and len(times) == STEPS, "prediction time count")
    for index, value in enumerate(times, 1):
        number(value, "prediction time")
        require(math.isclose(value, index / 10, abs_tol=1e-9, rel_tol=0), "prediction clock")


def probability(value, where):
    number(value, where)
    require(0 <= value <= 1, f"{where}: probability outside [0,1]")


def validate_prediction(value):
    keys(value, "prediction_times_s object_position_m obstacle_contact_probability "
         "task_success_probability", "prediction")
    validate_times(value["prediction_times_s"])
    require(isinstance(value["object_position_m"], list)
            and len(value["object_position_m"]) == STEPS, "position count")
    for pos in value["object_position_m"]:
        vector(pos, 3, "predicted position")
    probs = value["obstacle_contact_probability"]
    require(isinstance(probs, list) and len(probs) == STEPS, "contact count")
    for p in probs:
        probability(p, "contact")
    probability(value["task_success_probability"], "whole success")


def mean_predictions(samples):
    """Aggregate one deterministic or 16 stochastic samples; no dropped draws."""
    require(isinstance(samples, list) and len(samples) in (1, 16), "one or 16 samples required")
    for item in samples:
        validate_prediction(item)
    n = len(samples)
    result = {
        "prediction_times_s": [i / 10 for i in range(1, STEPS + 1)],
        "object_position_m": [[math.fsum(s["object_position_m"][k][axis] / n for s in samples)
                               for axis in range(3)] for k in range(STEPS)],
        "obstacle_contact_probability": [math.fsum(s["obstacle_contact_probability"][k] / n
                                                  for s in samples) for k in range(STEPS)],
        "task_success_probability": math.fsum(s["task_success_probability"] / n for s in samples),
    }
    validate_prediction(result)
    return result
