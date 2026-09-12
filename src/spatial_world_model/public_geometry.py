"""Public depth-only opening envelopes for the D-076 top-down engineering rig.

This pure function reads no files and knows no gate count, layout, frame selector,
RGB code, control or target. It is not a general mapper or a physics predictor.
All coordinates and supporting pixel pairs are observations, never private labels.
"""
from copy import deepcopy
import math

from .pair_contract import frame, keys, number, require, vector


VERSION = "public-openings-v1"
_CANONICAL_ROTATION = [[1, 0, 0], [0, -1, 0], [0, 0, -1]]
_SENSOR_DECLARATIONS = {
    "depth_kind": "camera_axis_z_m",
    "pixel_centers": "integer_u_v_with_public_intrinsics",
    "source_policy": "shared_rig_only_near_and_far_from_pinned_reference_not_per_world_xml",
}
_EXTRACTOR_DECLARATIONS = {
    "input": "validated_history_frames_only",
    "used_fields": ["depth_m", "width", "height", "camera_position_m", "camera_xyzw", "intrinsics"],
    "assumptions": ["static_observed_horizontal_surfaces", "axis_aligned_rectangular_boundaries",
                    "calibrated_canonical_top_down_camera"],
    "gap_rule": "all_intervening_pixels_valid_and_farther",
    "height_clustering": "sorted_greedy_complete_span",
    "boundary_rule": "adjacent_surface_and_farther_valid_ray_footprints_intersect_same_plane_interval",
    "fusion": "overlap_graph_then_common_interval_intersection_conflicts_preserved",
    "candidate_count": "unbounded_by_task_gate_count",
    "missing_boundary": "unknown_not_completed",
    "unobserved_space": "unknown_not_free",
    "rgb_used": False,
    "controls_or_goal_used": False,
    "private_labels_or_layout_used": False,
}
_FLOAT_PARAMETERS = (
    "plane_tolerance_m", "maximum_cluster_height_span_m",
    "minimum_farther_depth_separation_m", "pixel_footprint_half_width", "coordinate_guard_m",
)
_COUNT_PARAMETERS = (
    "minimum_each_side_run_pixels", "minimum_consecutive_support_rows",
    "minimum_each_side_front_witness_columns",
)
_REJECTED_KEYS = (
    "zero_depth_pixels", "clipped_depth_pixels", "insufficient_side_run_pairs",
    "invalid_gap_pairs", "nonfarther_gap_pairs", "insufficient_row_groups",
    "insufficient_side_patch_groups", "missing_front_groups", "incompatible_boundary_groups",
)


def _declarations(value, expected, where):
    for name, constant in expected.items():
        require(type(value[name]) is type(constant) and value[name] == constant,
                f"{where}.{name}: unsupported declaration")


def _parameters(sensor, parameters):
    keys(sensor, " ".join(_SENSOR_DECLARATIONS) + " near_depth_m far_depth_m clip_margin_m "
         "camera_to_world_rotation rotation_entry_tolerance", "public_sensor_spec")
    keys(parameters, " ".join((*_EXTRACTOR_DECLARATIONS, *_FLOAT_PARAMETERS, *_COUNT_PARAMETERS)),
         "extractor_parameters")
    _declarations(sensor, _SENSOR_DECLARATIONS, "public_sensor_spec")
    _declarations(parameters, _EXTRACTOR_DECLARATIONS, "extractor_parameters")
    for name in ("near_depth_m", "far_depth_m", "clip_margin_m", "rotation_entry_tolerance"):
        number(sensor[name], f"public_sensor_spec.{name}")
        require(sensor[name] > 0, f"public_sensor_spec.{name}: must be positive")
    require(sensor["near_depth_m"] + 2 * sensor["clip_margin_m"] < sensor["far_depth_m"],
            "public_sensor_spec: empty valid depth range")
    rotation = sensor["camera_to_world_rotation"]
    require(isinstance(rotation, list) and len(rotation) == 3, "sensor rotation shape")
    for row in rotation:
        vector(row, 3, "sensor rotation")
    require(rotation == _CANONICAL_ROTATION, "only canonical top-down sensor supported")
    require(sensor["rotation_entry_tolerance"] <= 1e-6, "rotation tolerance exceeds supported rig")
    for name in _FLOAT_PARAMETERS:
        number(parameters[name], name)
        require(parameters[name] > 0, f"{name}: must be positive")
    for name in _COUNT_PARAMETERS:
        require(type(parameters[name]) is int and parameters[name] >= 2,
                f"{name}: at least two required")
    require(parameters["pixel_footprint_half_width"] == 0.5, "full half-pixel footprints required")


def _rotation(quaternion):
    # Normalize only the already contract-validated unit quaternion. q and -q agree.
    length = math.sqrt(sum(component * component for component in quaternion))
    x, y, z, w = (component / length for component in quaternion)
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]


def _ray(observation, rotation, u, v):
    fx, fy, cx, cy = observation["intrinsics"]
    camera_ray = ((u - cx) / fx, (v - cy) / fy, 1.0)
    ray = [sum(row[i] * camera_ray[i] for i in range(3)) for row in rotation]
    require(all(math.isfinite(value) for value in ray) and ray[2] < 0,
            "unsupported/nonfinite downward ray")
    return ray


def _intersection_depths(observation, rotation, pixel, height_interval):
    ray = _ray(observation, rotation, *pixel)
    values = [(height - observation["camera_position_m"][2]) / ray[2]
              for height in height_interval]
    require(all(math.isfinite(value) and value > 0 for value in values),
            "candidate plane does not have finite forward intersections")
    return min(values), max(values)


def _boundary_interval(observation, rotation, pixels, height_interval, axis, parameters):
    positions = []
    half_width = parameters["pixel_footprint_half_width"]
    camera = observation["camera_position_m"]
    for u, v in pixels:
        for du in (-half_width, half_width):
            for dv in (-half_width, half_width):
                ray = _ray(observation, rotation, u + du, v + dv)
                for height in height_interval:
                    depth = (height - camera[2]) / ray[2]
                    position = camera[axis] + depth * ray[axis]
                    require(math.isfinite(position) and math.isfinite(depth) and depth > 0,
                            "nonfinite boundary projection")
                    positions.append(position)
    guard = parameters["coordinate_guard_m"]
    return [min(positions) - guard, max(positions) + guard]


def _common(intervals):
    lower = max(interval[0] for interval in intervals)
    upper = min(interval[1] for interval in intervals)
    return [lower, upper] if lower <= upper else None


def _height_clusters(points, maximum_span):
    """Cluster (world_z, flat_pixel_index) by total span, never single-link chains."""
    ordered = sorted(points)
    clusters = []
    for point in ordered:
        if not clusters or point[0] - clusters[-1][0][0] > maximum_span:
            clusters.append([])
        clusters[-1].append(point)
    return clusters


def _runs(columns):
    result = []
    for column in sorted(columns):
        if not result or column != result[-1][1] + 1:
            result.append([column, column])
        else:
            result[-1][1] = column
    return result


def _components(items, adjacent):
    """Deterministic connected components, including singleton observations."""
    remaining = set(range(len(items)))
    result = []
    while remaining:
        seed = min(remaining)
        remaining.remove(seed)
        todo, component = [seed], [seed]
        while todo:
            source = todo.pop()
            neighbors = [target for target in sorted(remaining) if adjacent(items[source], items[target])]
            for target in neighbors:
                remaining.remove(target)
                todo.append(target)
                component.append(target)
        result.append([items[index] for index in sorted(component)])
    return result


def _support(frame_index, pixels, kind, interval, height_interval):
    return {"local_frame_index": frame_index, "pixel_pair": [list(pixel) for pixel in pixels],
            "boundary_kind": kind, "raw_interval_m": list(interval),
            "plane_height_interval_m": list(height_interval)}


def _incomplete(frame_index, rows, height_interval, reason):
    return {"local_frame_index": frame_index, "row_span": [min(rows), max(rows)],
            "plane_height_interval_m": list(height_interval), "reason": reason}


def _farther(observation, rotation, pixel, height_interval, valid, parameters):
    index = pixel[1] * observation["width"] + pixel[0]
    return (valid[index] and observation["depth_m"][index]
            >= _intersection_depths(observation, rotation, pixel, height_interval)[1]
            + parameters["minimum_farther_depth_separation_m"])


def _frame_candidates(observation, frame_index, rotation, sensor, parameters, rejected, incomplete):
    width, height = observation["width"], observation["height"]
    near = sensor["near_depth_m"] + sensor["clip_margin_m"]
    far = sensor["far_depth_m"] - sensor["clip_margin_m"]
    valid, points = [], []
    for index, depth in enumerate(observation["depth_m"]):
        accepted = near < depth < far
        valid.append(accepted)
        if not accepted:
            rejected["zero_depth_pixels" if depth == 0 else "clipped_depth_pixels"] += 1
            continue
        ray = _ray(observation, rotation, index % width, index // width)
        world_z = observation["camera_position_m"][2] + depth * ray[2]
        require(math.isfinite(world_z), "nonfinite backprojected height")
        points.append((world_z, index))
    candidates = []
    for cluster in _height_clusters(points, parameters["maximum_cluster_height_span_m"]):
        tolerance = parameters["plane_tolerance_m"]
        height_interval = [cluster[0][0] - tolerance, cluster[-1][0] + tolerance]
        pixels = {index for _, index in cluster}
        by_row = {}
        for index in sorted(pixels):
            by_row.setdefault(index // width, []).append(index % width)
        rows = []
        for v, columns in sorted(by_row.items()):
            runs = _runs(columns)
            for left, right in zip(runs, runs[1:]):
                if any(run[1] - run[0] + 1 < parameters["minimum_each_side_run_pixels"]
                       for run in (left, right)):
                    rejected["insufficient_side_run_pairs"] += 1
                    continue
                gap = [(u, v) for u in range(left[1] + 1, right[0])]
                if not all(valid[pv * width + pu] for pu, pv in gap):
                    rejected["invalid_gap_pairs"] += 1
                    incomplete.append(_incomplete(frame_index, [v], height_interval, "gap_invalid_depth"))
                    continue
                if not all(_farther(observation, rotation, pixel, height_interval, valid, parameters)
                           for pixel in gap):
                    rejected["nonfarther_gap_pairs"] += 1
                    incomplete.append(_incomplete(frame_index, [v], height_interval, "gap_not_farther"))
                    continue
                pairs = [[(left[1], v), (left[1] + 1, v)], [(right[0], v), (right[0] - 1, v)]]
                intervals = [_boundary_interval(observation, rotation, pair, height_interval, 0, parameters)
                             for pair in pairs]
                rows.append({"v": v, "left": left, "right": right, "intervals": intervals,
                             "support": [_support(frame_index, pair, kind, interval, height_interval)
                                         for pair, kind, interval in zip(pairs, ("x_left", "x_right"), intervals)]})

        def neighboring(first, second):
            return abs(first["v"] - second["v"]) == 1 and all(
                _common([first["intervals"][axis], second["intervals"][axis]]) is not None
                for axis in (0, 1))

        for group in _components(rows, neighboring):
            row_indices = [row["v"] for row in group]
            if (len(set(row_indices)) < parameters["minimum_consecutive_support_rows"]
                    or len(set(row_indices)) != len(group)):
                rejected["insufficient_row_groups"] += 1
                incomplete.append(_incomplete(frame_index, row_indices, height_interval, "insufficient_consecutive_rows"))
                continue
            edges = [_common([row["intervals"][axis] for row in group]) for axis in (0, 1)]
            if any(edge is None for edge in edges):
                rejected["incompatible_boundary_groups"] += 1
                incomplete.append(_incomplete(frame_index, row_indices, height_interval, "incompatible_side_intervals"))
                continue
            patches = [[max(row[side][0] for row in group), min(row[side][1] for row in group)]
                       for side in ("left", "right")]
            if any(end - start + 1 < parameters["minimum_each_side_run_pixels"] for start, end in patches):
                rejected["insufficient_side_patch_groups"] += 1
                incomplete.append(_incomplete(frame_index, row_indices, height_interval, "insufficient_two_dimensional_patches"))
                continue
            witnesses = []
            enough_front = True
            for start, end in patches:
                side_witnesses = []
                for u in range(start, end + 1):
                    v = max(row_indices)
                    while v + 1 < height and (v + 1) * width + u in pixels:
                        v += 1
                    if v + 1 >= height or not _farther(observation, rotation, (u, v + 1),
                                                       height_interval, valid, parameters):
                        continue
                    pair = [(u, v), (u, v + 1)]  # Increasing image v is the smaller-world-y side.
                    interval = _boundary_interval(observation, rotation, pair, height_interval, 1, parameters)
                    side_witnesses.append(_support(frame_index, pair, "y_front", interval, height_interval))
                if len(side_witnesses) < parameters["minimum_each_side_front_witness_columns"]:
                    enough_front = False
                witnesses.extend(side_witnesses)
            if not enough_front:
                rejected["missing_front_groups"] += 1
                incomplete.append(_incomplete(frame_index, row_indices, height_interval, "missing_front_witnesses"))
                continue
            front = _common([witness["raw_interval_m"] for witness in witnesses])
            if front is None:
                rejected["incompatible_boundary_groups"] += 1
                incomplete.append(_incomplete(frame_index, row_indices, height_interval, "incompatible_front_intervals"))
                continue
            intervals = edges + [front]
            support = [item for row in group for item in row["support"]] + witnesses
            candidates.append({"coordinate_intervals_m": intervals,
                               "coordinates_m": [(interval[0] + interval[1]) / 2 for interval in intervals],
                               "plane_height_interval_m": list(height_interval), "support": support})
    return candidates


def _fuse_candidates(candidates):
    def overlapping(first, second):
        return all(_common([left, right]) is not None for left, right in zip(
            first["coordinate_intervals_m"] + [first["plane_height_interval_m"]],
            second["coordinate_intervals_m"] + [second["plane_height_interval_m"]]))

    fused, conflicts = [], []
    for members in _components(candidates, overlapping):
        intervals = [_common([member["coordinate_intervals_m"][axis] for member in members])
                     for axis in range(3)]
        height_interval = _common([member["plane_height_interval_m"] for member in members])
        if height_interval is None or any(interval is None for interval in intervals):
            conflicts.append({"reason": "empty_common_intersection", "members": deepcopy(members)})
            continue
        fused.append({"coordinate_intervals_m": intervals,
                      "coordinates_m": [(interval[0] + interval[1]) / 2 for interval in intervals],
                      "plane_height_interval_m": height_interval,
                      "support": deepcopy([item for member in members for item in member["support"]])})
    fused.sort(key=lambda item: (*item["coordinates_m"], *item["plane_height_interval_m"]))
    return fused, conflicts


def recover_openings(history, public_sensor_spec, extractor_parameters):
    """Return independent observed opening envelopes; unknown space stays unknown.

    Invalid frames, nonchronological histories, unsupported camera poses and any
    extra parameter (including an entire proposal or private field) raise ValueError.
    Pixel pairs are [[u_surface,v_surface], [u_farther,v_farther]]. Output ordering
    is deterministic and has no near/far gate identity. See docs/METHOD.md, D-076.
    """
    _parameters(public_sensor_spec, extractor_parameters)
    require(isinstance(history, list) and history, "history: nonempty frame list required")
    rotations = []
    for index, observation in enumerate(history):
        frame(observation, f"history[{index}]")
        if index:
            require(history[index - 1]["time_s"] < observation["time_s"], "history not strictly chronological")
        require((observation["width"], observation["height"]) == (history[0]["width"], history[0]["height"]),
                "history resolution changed")
        rotation = _rotation(observation["camera_xyzw"])
        require(all(abs(rotation[row][column] - _CANONICAL_ROTATION[row][column])
                    <= public_sensor_spec["rotation_entry_tolerance"]
                    for row in range(3) for column in range(3)), "unsupported camera rotation")
        rotations.append(rotation)
    rejected = {name: 0 for name in _REJECTED_KEYS}
    incomplete, raw = [], []
    for index, (observation, rotation) in enumerate(zip(history, rotations)):
        raw.extend(_frame_candidates(observation, index, rotation, public_sensor_spec,
                                     extractor_parameters, rejected, incomplete))
    candidates, conflicts = _fuse_candidates(raw)
    return {"schema_version": VERSION, "candidates": candidates, "conflicts": conflicts,
            "incomplete_observations": incomplete, "rejected_counts": rejected,
            "history_frames": len(history)}
