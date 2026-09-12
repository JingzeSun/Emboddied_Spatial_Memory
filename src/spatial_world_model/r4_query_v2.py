"""R4 v2 public query and prediction value contracts, standard library only.

No files, model state, labels, simulator or tensor backend are accessed.
Images remain flat, row-major JSON lists; tensorization belongs to each adapter.
See docs/DATA.md#r4-data and docs/METHOD.md#r4-common-contract.
"""
from copy import deepcopy
import math

from .pair_contract import frame, keys, number, require, vector
from .two_gate_contract import _goal_valid


VERSION = "spatial-history-r4-query-v2"
PREDICTION_VERSION = "spatial-history-r4-prediction-v2"
SOURCE_VERSION = "spatial-history-r4-public-query-v2"
RESOLUTION = 80
PIXELS = RESOLUTION ** 2
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


def _calibration(raw, original, tx):
    """Fixed D-082 rig; path coverage and real rendering need a separate audit."""
    focal = RESOLUTION / (2 * math.tan(math.radians(21)))
    expected = [focal, focal, 39.5, 39.5]
    require(all(math.isclose(a, b, rel_tol=0, abs_tol=1e-9)
                for a, b in zip(raw["intrinsics"], expected)), "v2 native camera intrinsics")
    x, y, z = raw["camera_position_m"]
    require(math.isclose(x, tx, rel_tol=0, abs_tol=1e-9)
            and math.isclose(z, 1.4, rel_tol=0, abs_tol=1e-9), "v2 camera x/height")
    qx, qy, qz, qw = raw["camera_xyzw"]
    require(math.isclose(abs(qx), 1, rel_tol=0, abs_tol=1e-9)
            and all(abs(v) <= 1e-9 for v in (qy, qz, qw)), "v2 canonical top-down camera")
    if original == 0 or original >= 110:
        require(math.isclose(y, -0.2, rel_tol=0, abs_tol=1e-9), "v2 start/terminal camera")


def validate_query(query, *, history_mode="full", history_cut_index=None):
    """Validate an explicit public-only value. Mode/cut stay outside features.

    A prefix clock remains relative to the future decision, not its own end.
    This is value validation, not an operating-system file permission boundary.
    """
    keys(query, "schema_version history controls goal domain_spec", "query")
    require(query["schema_version"] == VERSION, "v2 query version required")
    validate_goal(query["goal"])
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
        raw.update(time_s=0.5 + original / 10, width=RESOLUTION, height=RESOLUTION)
        frame(raw, "history frame")
        _calibration(raw, original, query["goal"]["goal_center_xy_m"][0])
        mask = hist["depth_valid"][local]
        require(isinstance(mask, list) and len(mask) == PIXELS
                and all(type(m) is bool and m == (d > 0)
                        for m, d in zip(mask, raw["depth_m"])), "depth validity mismatch")
    validate_controls(query["controls"])
    validate_goal(query["goal"])
    validate_domain(query["domain_spec"])


def model_features(query, *, history_mode="full", history_cut_index=None):
    """Validate the version envelope, then return only numerical model fields."""
    validate_query(query, history_mode=history_mode, history_cut_index=history_cut_index)
    return deepcopy({key: query[key] for key in ("history", "controls", "goal", "domain_spec")})


def validate_candidate_queries(queries, *, registered_controls,
                               history_mode="full", history_cut_index=None):
    """Bind nine slots to an externally registered numerical control order.

    This value checker does not generate or certify the D-082 design/registry.
    World/family IDs and registry hashes remain outside model features.
    """
    require(isinstance(queries, list) and len(queries) == 9, "nine query slots required")
    require(isinstance(registered_controls, list) and len(registered_controls) == 9,
            "nine registered controls required")
    for i, controls in enumerate(registered_controls):
        validate_controls(controls)
        require(all(controls != previous for previous in registered_controls[:i]), "duplicate registered controls")
    for i, query in enumerate(queries):
        validate_query(query, history_mode=history_mode, history_cut_index=history_cut_index)
        require(query["controls"] == registered_controls[i], "candidate order/control mismatch")
        require(all(query[key] == queries[0][key] for key in ("history", "goal", "domain_spec")),
                "candidate histories/goals/domain differ")


def from_public_query(public_query, *, history_mode="full", history_cut_index=None):
    """Adapt an already selected, versioned v2 public value, without file access.

    Caller supplies exactly the requested prefix/recent/full frames. All source
    frames are validated, so this function never silently drops contamination.
    Returned RGB/depth lists preserve original values; no float32 conversion here.
    """
    keys(public_query, "schema_version history controls goal", "public query")
    require(public_query["schema_version"] == SOURCE_VERSION, "v2 source query version required")
    indices = _history_indices(history_mode, history_cut_index)
    require(isinstance(public_query["history"], list)
            and len(public_query["history"]) == len(indices), "selected history length")
    columns = {key: [] for key in ["time_s", *FRAME_FIELDS, "depth_valid"]}
    for raw, original in zip(public_query["history"], indices):
        frame(raw, "source frame")
        require(raw["width"] == raw["height"] == RESOLUTION, "native resolution required")
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
    result = {"schema_version": VERSION, "history": columns, "controls": controls, "goal": deepcopy(public_query["goal"]),
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
    keys(value, "schema_version prediction_times_s object_position_m obstacle_contact_probability "
         "task_success_probability", "prediction")
    require(value["schema_version"] == PREDICTION_VERSION, "v2 prediction version required")
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
        "schema_version": PREDICTION_VERSION,
        "prediction_times_s": [i / 10 for i in range(1, STEPS + 1)],
        "object_position_m": [[math.fsum(s["object_position_m"][k][axis] / n for s in samples)
                               for axis in range(3)] for k in range(STEPS)],
        "obstacle_contact_probability": [math.fsum(s["obstacle_contact_probability"][k] / n
                                                  for s in samples) for k in range(STEPS)],
        "task_success_probability": math.fsum(s["task_success_probability"] / n for s in samples),
    }
    validate_prediction(result)
    return result
