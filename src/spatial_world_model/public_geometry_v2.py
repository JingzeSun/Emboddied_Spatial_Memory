"""Public-only opening envelopes with explicit boundary-compatible pixel bands.

E0-v2 preserves E0-v1's sensor, plane, support, fusion, and strict-farther
requirements.  A valid pixel which lies strictly beyond a candidate top-plane
interval but short of the unchanged farther separation may occur only in a
contiguous edge band between a top surface and a non-empty strict-farther
interior.  Such pixels widen the wall boundary interval; they never certify
free space.  This pure function reads no files or private labels.
"""

import math

from .pair_contract import frame, keys, number, require, vector
from . import public_geometry as v1


VERSION = "public-openings-v2"
_CANONICAL_ROTATION = [[1, 0, 0], [0, -1, 0], [0, 0, -1]]
_SENSOR_DECLARATIONS = {
    "depth_kind": "camera_axis_z_m",
    "pixel_centers": "integer_u_v_with_public_intrinsics",
    "source_policy": "shared_rig_only_near_and_far_from_pinned_reference_not_per_world_xml",
}
_EXTRACTOR_DECLARATIONS = {
    "input": "validated_history_frames_only",
    "used_fields": ["depth_m", "width", "height", "camera_position_m",
                    "camera_xyzw", "intrinsics"],
    "assumptions": ["static_observed_horizontal_surfaces",
                    "axis_aligned_rectangular_boundaries",
                    "calibrated_canonical_top_down_camera"],
    "gap_rule": "contiguous_edge_boundary_bands_and_nonempty_strict_farther_interior",
    "height_clustering": "sorted_greedy_complete_span",
    "boundary_rule": "adjacent_envelope_or_common_observed_depth_face_footprints_within_transition_envelope",
    "boundary_compatible_rule": "valid_depth_beyond_plane_interval_but_short_of_unchanged_farther_separation",
    "fusion": "overlap_graph_then_common_interval_intersection_conflicts_preserved",
    "candidate_count": "unbounded_by_task_gate_count",
    "missing_boundary": "unknown_not_completed",
    "unobserved_space": "unknown_not_free",
    "boundary_compatible_pixels_certify_free": False,
    "rgb_used": False,
    "controls_or_goal_used": False,
    "private_labels_or_layout_used": False,
}
_FLOAT_PARAMETERS = (
    "plane_tolerance_m", "maximum_cluster_height_span_m",
    "minimum_farther_depth_separation_m", "pixel_footprint_half_width",
    "coordinate_guard_m",
)
_COUNT_PARAMETERS = (
    "minimum_each_side_run_pixels", "minimum_consecutive_support_rows",
    "minimum_each_side_front_witness_columns",
)
_FIXED_SENSOR_NUMBERS = {
    "near_depth_m": 0.04,
    "far_depth_m": 20.0,
    "clip_margin_m": 0.0001,
    "rotation_entry_tolerance": 0.000001,
}
_FIXED_EXTRACTOR_NUMBERS = {
    "plane_tolerance_m": 0.0001,
    "maximum_cluster_height_span_m": 0.0002,
    "minimum_farther_depth_separation_m": 0.0002,
    "pixel_footprint_half_width": 0.5,
    "coordinate_guard_m": 0.000001,
    "minimum_each_side_run_pixels": 2,
    "minimum_consecutive_support_rows": 2,
    "minimum_each_side_front_witness_columns": 2,
}
_REJECTED_KEYS = (
    "zero_depth_pixels", "clipped_depth_pixels", "insufficient_side_run_pairs",
    "invalid_gap_pairs", "nonboundary_gap_pairs", "gap_without_strict_farther_pairs",
    "insufficient_row_groups", "insufficient_side_patch_groups",
    "missing_front_groups", "incompatible_boundary_groups",
)
_EVIDENCE_KEYS = (
    "strict_farther_gap_pixels", "boundary_compatible_gap_pixels",
    "strict_farther_front_witnesses", "boundary_compatible_front_pixels",
)


def _declarations(value, expected, where):
    for name, constant in expected.items():
        require(type(value[name]) is type(constant) and value[name] == constant,
                f"{where}.{name}: unsupported declaration")


def _parameters(sensor, parameters):
    keys(sensor, " ".join(_SENSOR_DECLARATIONS) + " near_depth_m far_depth_m clip_margin_m "
         "camera_to_world_rotation rotation_entry_tolerance", "public_sensor_spec")
    keys(parameters, " ".join((*_EXTRACTOR_DECLARATIONS, *_FLOAT_PARAMETERS,
                               *_COUNT_PARAMETERS)), "extractor_parameters")
    _declarations(sensor, _SENSOR_DECLARATIONS, "public_sensor_spec")
    _declarations(parameters, _EXTRACTOR_DECLARATIONS, "extractor_parameters")
    for name in ("near_depth_m", "far_depth_m", "clip_margin_m", "rotation_entry_tolerance"):
        number(sensor[name], f"public_sensor_spec.{name}")
        require(sensor[name] > 0, f"public_sensor_spec.{name}: must be positive")
        require(sensor[name] == _FIXED_SENSOR_NUMBERS[name],
                f"public_sensor_spec.{name}: frozen value changed")
    require(sensor["near_depth_m"] + 2 * sensor["clip_margin_m"] < sensor["far_depth_m"],
            "public_sensor_spec: empty valid depth range")
    rotation = sensor["camera_to_world_rotation"]
    require(isinstance(rotation, list) and len(rotation) == 3, "sensor rotation shape")
    for row in rotation:
        vector(row, 3, "sensor rotation")
    require(rotation == _CANONICAL_ROTATION, "only canonical top-down sensor supported")
    require(sensor["rotation_entry_tolerance"] <= 1e-6,
            "rotation tolerance exceeds supported rig")
    for name in _FLOAT_PARAMETERS:
        number(parameters[name], name)
        require(parameters[name] > 0, f"{name}: must be positive")
        require(parameters[name] == _FIXED_EXTRACTOR_NUMBERS[name],
                f"{name}: frozen value changed")
    for name in _COUNT_PARAMETERS:
        require(type(parameters[name]) is int and parameters[name] >= 2,
                f"{name}: at least two required")
        require(parameters[name] == _FIXED_EXTRACTOR_NUMBERS[name],
                f"{name}: frozen value changed")
    require(parameters["pixel_footprint_half_width"] == 0.5,
            "full half-pixel footprints required")


def _support(frame_index, surface_pixel, farther_pixel, boundary_pixels, kind,
             interval, height_interval):
    return {
        "local_frame_index": frame_index,
        "pixel_pair": [list(surface_pixel), list(farther_pixel)],
        "boundary_compatible_pixels": [list(pixel) for pixel in boundary_pixels],
        "transition_kind": ("boundary_compatible_band" if boundary_pixels
                            else "adjacent_strict_farther"),
        "boundary_kind": kind,
        "raw_interval_m": list(interval),
        "plane_height_interval_m": list(height_interval),
    }


def _pixel_evidence(observation, rotation, pixel, height_interval, valid, parameters):
    """Classify one non-top pixel without weakening the strict-farther test."""
    index = pixel[1] * observation["width"] + pixel[0]
    if not valid[index]:
        return "invalid"
    depth = observation["depth_m"][index]
    plane_far = v1._intersection_depths(observation, rotation, pixel, height_interval)[1]
    if depth >= plane_far + parameters["minimum_farther_depth_separation_m"]:
        return "strict_farther"
    if depth > plane_far:
        return "boundary_compatible"
    return "nonboundary_nearer"


def _face_interval(observation, rotation, pixels, axis, parameters):
    """Intersect full pixel footprints at observed depth for one possible vertical face."""
    guard = parameters["coordinate_guard_m"]
    half = parameters["pixel_footprint_half_width"]
    camera = observation["camera_position_m"]
    intervals = []
    for u, v in pixels:
        depth = observation["depth_m"][v * observation["width"] + u]
        positions = []
        for du in (-half, half):
            for dv in (-half, half):
                ray = v1._ray(observation, rotation, u + du, v + dv)
                positions.append(camera[axis] + depth * ray[axis])
        intervals.append([min(positions) - guard, max(positions) + guard])
    return v1._common(intervals)


def _transition_interval(observation, rotation, pair, boundary_pixels,
                         height_interval, axis, parameters):
    envelope = v1._boundary_interval(
        observation, rotation, pair, height_interval, axis, parameters)
    if not boundary_pixels:
        return envelope
    face = _face_interval(observation, rotation, boundary_pixels, axis, parameters)
    return None if face is None else v1._common([envelope, face])


def _gap_transition(observation, rotation, gap, height_interval, valid, parameters,
                    evidence):
    labels = [_pixel_evidence(observation, rotation, pixel, height_interval, valid, parameters)
              for pixel in gap]
    if "invalid" in labels:
        return None, "gap_invalid_depth"
    farther = [index for index, label in enumerate(labels) if label == "strict_farther"]
    if not farther:
        return None, "gap_without_strict_farther"
    first, last = farther[0], farther[-1]
    if (any(label != "boundary_compatible" for label in labels[:first])
            or any(label != "strict_farther" for label in labels[first:last + 1])
            or any(label != "boundary_compatible" for label in labels[last + 1:])):
        return None, "gap_contains_nonboundary_or_interior_ambiguity"
    evidence["strict_farther_gap_pixels"] += last - first + 1
    evidence["boundary_compatible_gap_pixels"] += first + len(labels) - last - 1
    return {
        "left_farther": gap[first],
        "right_farther": gap[last],
        "left_boundary_pixels": gap[:first],
        "right_boundary_pixels": gap[last + 1:],
    }, None


def _front_transition(observation, rotation, u, surface_v, height_interval, valid,
                      parameters, evidence):
    boundary_pixels = []
    for v in range(surface_v + 1, observation["height"]):
        pixel = (u, v)
        kind = _pixel_evidence(observation, rotation, pixel, height_interval, valid, parameters)
        if kind == "boundary_compatible":
            boundary_pixels.append(pixel)
            continue
        if kind == "strict_farther":
            evidence["strict_farther_front_witnesses"] += 1
            evidence["boundary_compatible_front_pixels"] += len(boundary_pixels)
            return pixel, boundary_pixels
        return None
    return None


def _frame_candidates(observation, frame_index, rotation, sensor, parameters,
                      rejected, incomplete, evidence):
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
        ray = v1._ray(observation, rotation, index % width, index // width)
        world_z = observation["camera_position_m"][2] + depth * ray[2]
        require(math.isfinite(world_z), "nonfinite backprojected height")
        points.append((world_z, index))

    candidates = []
    for cluster in v1._height_clusters(points, parameters["maximum_cluster_height_span_m"]):
        tolerance = parameters["plane_tolerance_m"]
        height_interval = [cluster[0][0] - tolerance, cluster[-1][0] + tolerance]
        pixels = {index for _, index in cluster}
        by_row = {}
        for index in sorted(pixels):
            by_row.setdefault(index // width, []).append(index % width)
        rows = []
        for v, columns in sorted(by_row.items()):
            runs = v1._runs(columns)
            for left, right in zip(runs, runs[1:]):
                if any(run[1] - run[0] + 1 < parameters["minimum_each_side_run_pixels"]
                       for run in (left, right)):
                    rejected["insufficient_side_run_pairs"] += 1
                    continue
                gap = [(u, v) for u in range(left[1] + 1, right[0])]
                transition, reason = _gap_transition(
                    observation, rotation, gap, height_interval, valid, parameters, evidence)
                if transition is None:
                    if reason == "gap_invalid_depth":
                        rejected["invalid_gap_pairs"] += 1
                    elif reason == "gap_without_strict_farther":
                        rejected["gap_without_strict_farther_pairs"] += 1
                    else:
                        rejected["nonboundary_gap_pairs"] += 1
                    incomplete.append(v1._incomplete(frame_index, [v], height_interval, reason))
                    continue
                pairs = [
                    [(left[1], v), transition["left_farther"]],
                    [(right[0], v), transition["right_farther"]],
                ]
                bands = [transition["left_boundary_pixels"],
                         transition["right_boundary_pixels"]]
                intervals = [_transition_interval(observation, rotation, pair, band,
                                                  height_interval, 0, parameters)
                             for pair, band in zip(pairs, bands)]
                if any(interval is None for interval in intervals):
                    rejected["incompatible_boundary_groups"] += 1
                    incomplete.append(v1._incomplete(
                        frame_index, [v], height_interval, "incompatible_boundary_face_band"))
                    continue
                rows.append({
                    "v": v, "left": left, "right": right, "intervals": intervals,
                    "support": [
                        _support(frame_index, pair[0], pair[1], band, kind, interval,
                                 height_interval)
                        for pair, band, kind, interval in zip(
                            pairs, bands, ("x_left", "x_right"), intervals)
                    ],
                })

        def neighboring(first, second):
            return abs(first["v"] - second["v"]) == 1 and all(
                v1._common([first["intervals"][axis], second["intervals"][axis]]) is not None
                for axis in (0, 1))

        for group in v1._components(rows, neighboring):
            row_indices = [row["v"] for row in group]
            if (len(set(row_indices)) < parameters["minimum_consecutive_support_rows"]
                    or len(set(row_indices)) != len(group)):
                rejected["insufficient_row_groups"] += 1
                incomplete.append(v1._incomplete(
                    frame_index, row_indices, height_interval, "insufficient_consecutive_rows"))
                continue
            edges = [v1._common([row["intervals"][axis] for row in group])
                     for axis in (0, 1)]
            if any(edge is None for edge in edges):
                rejected["incompatible_boundary_groups"] += 1
                incomplete.append(v1._incomplete(
                    frame_index, row_indices, height_interval, "incompatible_side_intervals"))
                continue
            patches = [[max(row[side][0] for row in group),
                        min(row[side][1] for row in group)]
                       for side in ("left", "right")]
            if any(end - start + 1 < parameters["minimum_each_side_run_pixels"]
                   for start, end in patches):
                rejected["insufficient_side_patch_groups"] += 1
                incomplete.append(v1._incomplete(
                    frame_index, row_indices, height_interval,
                    "insufficient_two_dimensional_patches"))
                continue
            witnesses = []
            enough_front = True
            for start, end in patches:
                side_witnesses = []
                for u in range(start, end + 1):
                    surface_v = max(row_indices)
                    while (surface_v + 1 < height
                           and (surface_v + 1) * width + u in pixels):
                        surface_v += 1
                    transition = _front_transition(
                        observation, rotation, u, surface_v, height_interval, valid,
                        parameters, evidence)
                    if transition is None:
                        continue
                    farther_pixel, boundary_pixels = transition
                    pair = [(u, surface_v), farther_pixel]
                    interval = _transition_interval(
                        observation, rotation, pair, boundary_pixels,
                        height_interval, 1, parameters)
                    if interval is None:
                        continue
                    side_witnesses.append(_support(
                        frame_index, pair[0], pair[1], boundary_pixels, "y_front",
                        interval, height_interval))
                if len(side_witnesses) < parameters["minimum_each_side_front_witness_columns"]:
                    enough_front = False
                witnesses.extend(side_witnesses)
            if not enough_front:
                rejected["missing_front_groups"] += 1
                incomplete.append(v1._incomplete(
                    frame_index, row_indices, height_interval, "missing_front_witnesses"))
                continue
            front = v1._common([witness["raw_interval_m"] for witness in witnesses])
            if front is None:
                rejected["incompatible_boundary_groups"] += 1
                incomplete.append(v1._incomplete(
                    frame_index, row_indices, height_interval, "incompatible_front_intervals"))
                continue
            intervals = edges + [front]
            support = [item for row in group for item in row["support"]] + witnesses
            candidates.append({
                "coordinate_intervals_m": intervals,
                "coordinates_m": [(interval[0] + interval[1]) / 2 for interval in intervals],
                "plane_height_interval_m": list(height_interval),
                "support": support,
            })
    return candidates


def recover_openings(history, public_sensor_spec, extractor_parameters):
    """Return E0-v2 public opening intervals; unsupported geometry stays unresolved."""
    _parameters(public_sensor_spec, extractor_parameters)
    require(isinstance(history, list) and history, "history: nonempty frame list required")
    rotations = []
    for index, observation in enumerate(history):
        frame(observation, f"history[{index}]")
        if index:
            require(history[index - 1]["time_s"] < observation["time_s"],
                    "history not strictly chronological")
        require((observation["width"], observation["height"])
                == (history[0]["width"], history[0]["height"]),
                "history resolution changed")
        rotation = v1._rotation(observation["camera_xyzw"])
        require(all(abs(rotation[row][column] - _CANONICAL_ROTATION[row][column])
                    <= public_sensor_spec["rotation_entry_tolerance"]
                    for row in range(3) for column in range(3)),
                "unsupported camera rotation")
        rotations.append(rotation)
    rejected = {name: 0 for name in _REJECTED_KEYS}
    evidence = {name: 0 for name in _EVIDENCE_KEYS}
    incomplete, raw = [], []
    for index, (observation, rotation) in enumerate(zip(history, rotations)):
        raw.extend(_frame_candidates(
            observation, index, rotation, public_sensor_spec, extractor_parameters,
            rejected, incomplete, evidence))
    candidates, conflicts = v1._fuse_candidates(raw)
    return {
        "schema_version": VERSION,
        "candidates": candidates,
        "conflicts": conflicts,
        "incomplete_observations": incomplete,
        "rejected_counts": rejected,
        "evidence_counts": evidence,
        "history_frames": len(history),
    }
