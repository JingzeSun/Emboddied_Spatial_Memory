"""D-086: native v2 public depth coverage and history selection, stdlib only.

Pure values only: no RGB, controls, goals, files, objects, labels or simulator.
Surface voxels are coverage keys, never an occupied/free-space map.
See docs/METHOD.md#r4-coverage and docs/DATA.md#r4-coverage-data.
"""
from copy import deepcopy
import math

from .pair_contract import keys, number, require, vector


HISTORY_VERSION = "spatial-history-r4-depth-history-v1"
SURFACE_VERSION = "spatial-history-r4-surface-coverage-v1"
SELECTION_VERSION = "spatial-history-r4-coverage-selection-v1"
RESOLUTION = 80
_FIELDS = "time_s width height depth_m camera_position_m camera_xyzw intrinsics"
_SENSOR = {
    "depth_kind": "camera_axis_distance_m",
    "pixel_centers": "integer_u_v",
    "near_depth_m": 0.04,
    "far_depth_m": 20.0,
    "clip_margin_m": 0.0001,
}
_PARAMETERS = {"voxel_m": 0.02, "recent_keep": 2, "additional_frames": 8,
               "origin_m": [0.0, 0.0, 0.0]}


def sensor_spec():
    """Shared sensor constants; caller must bind these to the source manifest."""
    return deepcopy(_SENSOR)


def parameters():
    return deepcopy(_PARAMETERS)


def _fixed(value, expected, where):
    if isinstance(expected, dict):
        keys(value, " ".join(expected), where)
        for name in expected:
            _fixed(value[name], expected[name], f"{where}.{name}")
    elif isinstance(expected, list):
        require(isinstance(value, list) and len(value) == len(expected), where)
        for item, reference in zip(value, expected):
            _fixed(item, reference, where)
    elif type(expected) in (int, float):
        number(value, where)
        if type(expected) is int:
            require(type(value) is int, f"{where}: integer required")
        require(value == expected, f"{where}: frozen value changed")
    else:
        require(type(value) is str and value == expected, where)


def _indices(mode, cut):
    require(type(mode) is str and mode in ("full", "recent", "prefix"), "history mode")
    if mode == "prefix":
        require(type(cut) is int and 0 <= cut <= 120, "prefix cut index")
        return list(range(cut + 1))
    require(cut is None, "cut only permitted for prefix")
    return list(range(121)) if mode == "full" else [119, 120]


def _close(a, b):
    return math.isclose(a, b, rel_tol=0, abs_tol=1e-9)


def _rotation(quaternion):
    # Normalize only within the already validated public quaternion tolerance.
    norm = math.sqrt(math.fsum(q * q for q in quaternion))
    x, y, z, w = (q / norm for q in quaternion)
    return [[1 - 2 * (y*y + z*z), 2 * (x*y - z*w), 2 * (x*z + y*w)],
            [2 * (x*y + z*w), 1 - 2 * (x*x + z*z), 2 * (y*z - x*w)],
            [2 * (x*z - y*w), 2 * (y*z + x*w), 1 - 2 * (x*x + y*y)]]


def _validate_history(history, mode, cut):
    keys(history, "schema_version frames", "depth history")
    require(history["schema_version"] == HISTORY_VERSION, "depth history version")
    indices = _indices(mode, cut)
    frames = history["frames"]
    require(isinstance(frames, list) and len(frames) == len(indices), "selected frame count")
    focal = 40 / math.tan(math.radians(21))
    first_x = None
    for local, (row, original) in enumerate(zip(frames, indices)):
        where = f"depth history frame[{local}]"
        keys(row, _FIELDS, where)
        number(row["time_s"], where)
        require(_close(row["time_s"], (original - 120) / 10), "relative history clock")
        require(type(row["width"]) is int and type(row["height"]) is int
                and row["width"] == row["height"] == RESOLUTION, "native 80x80 required")
        vector(row["depth_m"], RESOLUTION ** 2, "native depth")
        require(all(d >= 0 for d in row["depth_m"]), "negative depth")
        vector(row["camera_position_m"], 3, "camera position")
        vector(row["camera_xyzw"], 4, "camera quaternion")
        vector(row["intrinsics"], 4, "intrinsics")
        require(all(_close(a, b) for a, b in zip(row["intrinsics"],
                    [focal, focal, 39.5, 39.5])), "v2 native intrinsics")
        qx, qy, qz, qw = row["camera_xyzw"]
        require(_close(abs(qx), 1) and all(abs(q) <= 1e-9 for q in (qy, qz, qw)),
                "v2 canonical top-down quaternion")
        x, y, z = row["camera_position_m"]
        require(-0.12 <= x <= 0.12 and _close(z, 1.4), "v2 camera translation/height")
        if first_x is None:
            first_x = x
        require(_close(x, first_x), "camera x changed within history")
        if original == 0 or original >= 110:
            require(_close(y, -0.2), "v2 start/terminal camera")
    return frames


def _project(row, local, sensor, params):
    rotation = _rotation(row["camera_xyzw"])
    fx, fy, cx, cy = row["intrinsics"]
    camera = row["camera_position_m"]
    low = sensor["near_depth_m"] + sensor["clip_margin_m"]
    high = sensor["far_depth_m"] - sensor["clip_margin_m"]
    voxels, zero, clipped = {}, 0, 0
    for flat, depth in enumerate(row["depth_m"]):
        if depth == 0:
            zero += 1
            continue
        if not low < depth < high:
            clipped += 1
            continue
        v, u = divmod(flat, RESOLUTION)
        ray = [(u - cx) / fx, (v - cy) / fy, 1.0]
        point = [camera[axis] + depth * math.fsum(rotation[axis][j] * ray[j] for j in range(3))
                 for axis in range(3)]
        require(all(math.isfinite(p) for p in point), "nonfinite projection")
        # Deliberately no rounding/epsilon: a boundary belongs to its floor cell.
        scaled = [(p - origin) / params["voxel_m"]
                  for p, origin in zip(point, params["origin_m"])]
        require(all(math.isfinite(p) for p in scaled), "nonfinite voxel coordinate")
        key = tuple(math.floor(p) for p in scaled)
        voxels.setdefault(key, []).append([v, u])
    ordered = sorted(voxels)
    return {"local_index": local, "time_s": row["time_s"],
            "voxel_keys": [list(key) for key in ordered],
            "source_pixels": [voxels[key] for key in ordered],
            "valid_pixels": RESOLUTION ** 2 - zero - clipped,
            "zero_depth_pixels": zero, "clipped_depth_pixels": clipped}


def project_history(history, public_sensor_spec, selection_parameters, *,
                    history_mode="full", history_cut_index=None):
    """Project exactly the supplied causal slice; validate every pixel first.

    This validates values, not filesystem provenance. No raw query or hidden
    unselected frames are accepted. Output owns its arrays and includes all
    source pixels for each surface voxel; there is no object/semantic ranking.
    """
    _fixed(public_sensor_spec, _SENSOR, "public sensor")
    _fixed(selection_parameters, _PARAMETERS, "coverage parameters")
    frames = _validate_history(history, history_mode, history_cut_index)
    return {"schema_version": SURFACE_VERSION,
            "frames": [_project(row, local, public_sensor_spec, selection_parameters)
                       for local, row in enumerate(frames)]}


def _select(coverages, times, recent_keep, additional):
    """Internal greedy primitive; public callers cannot inject voxel coverage."""
    seed = list(range(max(0, len(times) - recent_keep), len(times)))
    selected, covered, trace = set(), set(), []

    def take(index, role):
        added = len(coverages[index] - covered)
        covered.update(coverages[index])
        selected.add(index)
        trace.append({"local_index": index, "role": role, "new_voxels": added})

    for index in seed:
        take(index, "recent")
    for _ in range(min(additional, len(times) - len(seed))):
        index = min((i for i in range(len(times)) if i not in selected),
                    key=lambda i: (-len(coverages[i] - covered), times[i]))
        take(index, "greedy")
    ordered = sorted(selected, key=lambda i: times[i])
    return ordered, trace, len(covered)


def select_history(history, public_sensor_spec, selection_parameters, *,
                   history_mode="full", history_cut_index=None):
    """Return original local frame indices, ordered times and coverage evidence.

    The outer adapter fetches RGBD using these indices. It must not feed audit
    IDs, source pixel numbers or greedy scores to a model as semantic tokens.
    This selector neither encodes RGB nor demonstrates useful gate retention.
    """
    surfaces = project_history(history, public_sensor_spec, selection_parameters,
                               history_mode=history_mode, history_cut_index=history_cut_index)
    frames = surfaces["frames"]
    coverages = [set(map(tuple, row["voxel_keys"])) for row in frames]
    times = [row["time_s"] for row in frames]
    selected, trace, count = _select(coverages, times, selection_parameters["recent_keep"],
                                     selection_parameters["additional_frames"])
    return {"schema_version": SELECTION_VERSION, "selected_local_indices": selected,
            "selected_time_s": [times[i] for i in selected],
            "selection_trace": trace, "selected_union_voxels": count,
            "frame_surfaces": surfaces}
