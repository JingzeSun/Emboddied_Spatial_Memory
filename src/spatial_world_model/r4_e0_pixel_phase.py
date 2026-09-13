"""Audit-only helpers for the D-116 E0 pixel-phase intervention.

These functions do not change E0, complete missing geometry, or choose a new
camera path.  They explain which rendered pixels make the unchanged E0 accept
or reject one already registered gate observation.
"""

from __future__ import annotations

import math

from .pair_contract import require
from . import public_geometry as e0


def phase_fractions(denominator, numerators):
    require(type(denominator) is int and denominator > 0, "positive phase denominator required")
    require(isinstance(numerators, list) and numerators, "phase numerators required")
    require(all(type(value) is int for value in numerators), "integer phase numerators required")
    require(numerators == sorted(set(numerators)) and 0 in numerators,
            "phase numerators must be unique, ordered and include zero")
    require(numerators[0] == -denominator // 2 and numerators[-1] == denominator // 2,
            "phase sweep must cover one centered pixel pitch")
    return [value / denominator for value in numerators]


def pixel_pitch_m(observation, plane_height_m):
    """World-space x distance between adjacent pixels at a horizontal plane."""
    e0.number(plane_height_m, "plane height")
    e0.vector(observation["camera_position_m"], 3, "camera position")
    e0.vector(observation["intrinsics"], 4, "intrinsics")
    camera_z = observation["camera_position_m"][2]
    focal_x = observation["intrinsics"][0]
    require(camera_z > plane_height_m and focal_x > 0, "plane must be below a finite camera")
    rotation = e0._rotation(observation["camera_xyzw"])
    require(abs(rotation[2][0]) <= 1e-9 and abs(rotation[2][1]) <= 1e-9
            and abs(rotation[2][2] + 1) <= 1e-9, "strict top-down camera required")
    return (camera_z - plane_height_m) / focal_x


def projected_column(observation, world_x_m, plane_height_m):
    """Project a world x coordinate on the registered horizontal plane."""
    pitch = pixel_pitch_m(observation, plane_height_m)
    camera_x = observation["camera_position_m"][0]
    center_x = observation["intrinsics"][2]
    value = center_x + (world_x_m - camera_x) / pitch
    nearest = math.floor(value + 0.5)
    return {
        "projected_u": value,
        "nearest_pixel_u": nearest,
        "signed_phase_from_nearest_pixel": value - nearest,
        "pixel_pitch_m": pitch,
    }


def _geom_name(geom_names, width, u, v):
    return geom_names[v * width + u]


def gate_gap_trace(observation, geom_names, left_geom_name, right_geom_name,
                   wall_top_height_m, public_sensor_spec, extractor_parameters):
    """Trace unchanged-E0 row pairs whose endpoints are the registered gate.

    ``geom_names`` is private segmentation audit information.  It is used only
    after the public E0 prediction is sealed and never enters that prediction.
    """
    width, height = observation["width"], observation["height"]
    require(isinstance(geom_names, list) and len(geom_names) == width * height,
            "one segmentation name per pixel required")
    rotation = e0._rotation(observation["camera_xyzw"])
    near = public_sensor_spec["near_depth_m"] + public_sensor_spec["clip_margin_m"]
    far = public_sensor_spec["far_depth_m"] - public_sensor_spec["clip_margin_m"]
    valid, points = [], []
    for index, depth in enumerate(observation["depth_m"]):
        accepted = near < depth < far
        valid.append(accepted)
        if accepted:
            ray = e0._ray(observation, rotation, index % width, index // width)
            points.append((observation["camera_position_m"][2] + depth * ray[2], index))

    matching_clusters = []
    tolerance = extractor_parameters["plane_tolerance_m"]
    for cluster in e0._height_clusters(points, extractor_parameters["maximum_cluster_height_span_m"]):
        height_interval = [cluster[0][0] - tolerance, cluster[-1][0] + tolerance]
        if height_interval[0] <= wall_top_height_m <= height_interval[1]:
            matching_clusters.append((cluster, height_interval))
    require(len(matching_clusters) == 1, "wall top must belong to exactly one E0 height cluster")

    cluster, height_interval = matching_clusters[0]
    pixels = {index for _, index in cluster}
    by_row = {}
    for index in sorted(pixels):
        by_row.setdefault(index // width, []).append(index % width)
    rows = []
    for v, columns in sorted(by_row.items()):
        runs = e0._runs(columns)
        for left, right in zip(runs, runs[1:]):
            if (_geom_name(geom_names, width, left[1], v) != left_geom_name
                    or _geom_name(geom_names, width, right[0], v) != right_geom_name):
                continue
            gap = list(range(left[1] + 1, right[0]))
            failures = []
            for u in gap:
                index = v * width + u
                required = (e0._intersection_depths(
                    observation, rotation, (u, v), height_interval)[1]
                    + extractor_parameters["minimum_farther_depth_separation_m"])
                actual = observation["depth_m"][index]
                if valid[index] and actual >= required:
                    continue
                ray = e0._ray(observation, rotation, u, v)
                failures.append({
                    "pixel_uv": [u, v],
                    "geom_name": geom_names[index],
                    "actual_depth_m": actual,
                    "required_depth_m": required,
                    "depth_shortfall_m": max(0.0, required - actual),
                    "derived_world_height_m": observation["camera_position_m"][2] + actual * ray[2],
                    "valid_depth": valid[index],
                })
            rows.append({
                "image_row_v": v,
                "left_run": list(left),
                "right_run": list(right),
                "gap_columns": [gap[0], gap[-1]] if gap else None,
                "farther_pass": not failures,
                "failures": failures,
                "height_interval_m": list(height_interval),
            })
    return {
        "left_geom_name": left_geom_name,
        "right_geom_name": right_geom_name,
        "matching_row_pairs": len(rows),
        "farther_passing_row_pairs": sum(row["farther_pass"] for row in rows),
        "failed_pixels": sum(len(row["failures"]) for row in rows),
        "rows": rows,
    }
