"""D-112 public continuous-support map for M-SIMPLE and M-PHYS.

The function has no file access.  It reprojects only supplied public depth and
keeps a conservative whole-cell cache of assumption-conditioned floor support,
observed wall intervals, and the current-body core.
"""

from __future__ import annotations

from copy import deepcopy
import math

from .pair_contract import keys, require
from . import public_geometry
from . import r4_object_association as objects
from . import r4_object_surfaces as surfaces
from . import r4_observed_map_v2 as nominal_maps
from .r4_continuous_geometry import (
    box_core_cells,
    box_possible_cells,
    cells_fully_in_rectangle,
    cells_intersecting_rectangle,
    circle_core_cells,
    circle_possible_cells,
    merge_cells_to_rectangles,
)
from .r4_coverage import _indices
from .r4_query_v2 import validate_domain


VERSION = "spatial-history-r4-continuous-map-v1"
PARAMETERS = {
    "cell_m": .005,
    "numeric_guard_m": .000001,
    "circle_quadrant_segments": 32,
    "circle_outer_radius_scale": 1.000301272041302,
    "floor_support": "whole_cell_inside_one_observed_locally_horizontal_quad",
    "wall_support": "cell_intersects_observed_wall_top_or_opening_boundary_interval",
    "body_core": "whole_cell_inside_every_allowed_current_body_placement",
    "unknown_priority": ["observed_wall_interval", "body_occlusion_unknown",
                         "sampling_gap_unknown", "outside_observed_region"],
}


def parameters():
    return deepcopy(PARAMETERS)


def _rectangle(points, margin):
    rectangle = [min(point[0] for point in points) + margin,
                 max(point[0] for point in points) - margin,
                 min(point[1] for point in points) + margin,
                 max(point[1] for point in points) - margin]
    return rectangle if rectangle[0] <= rectangle[1] and rectangle[2] <= rectangle[3] else None


def _support(history, public_sensor_spec, common_shape, ground, indices, continuous_parameters):
    cell_m = continuous_parameters["cell_m"]
    guard = continuous_parameters["numeric_guard_m"]
    floor_mid = math.fsum(ground["height_interval_m"]) / 2
    floor_witnesses, wall_witnesses = {}, {}
    counts = {"flat_quads": 0, "floor_quads": 0, "wall_quads": 0,
              "ignored_height_quads": 0}
    support_bounds = None
    for frame, source_index in zip(history["frames"], indices):
        result = surfaces.frame_candidates(
            frame, public_sensor_spec, common_shape, surfaces.parameters(), source_index=source_index)
        geometry = surfaces.Geometry(frame)
        for component in result["components"]:
            if component["classification"] in ("accepted_candidate", "attached_side_support"):
                continue
            pixels = set(map(tuple, component["support_pixels"]))
            for row, column in sorted(pixels):
                quad = ((row, column), (row + 1, column),
                        (row, column + 1), (row + 1, column + 1))
                if not all(pixel in pixels for pixel in quad):
                    continue
                points = [geometry.point(pixel, frame["depth_m"][pixel[0] * 80 + pixel[1]])
                          for pixel in quad]
                if max(point[2] for point in points) - min(point[2] for point in points) \
                        > nominal_maps.PARAMETERS["quad_height_span_m"]:
                    continue
                counts["flat_quads"] += 1
                heights = [point[2] for point in points]
                source = (source_index, row, column)
                if max(abs(height - floor_mid) for height in heights) \
                        <= nominal_maps.PARAMETERS["height_tolerance_m"]:
                    rectangle = _rectangle(points, guard)
                    if rectangle is not None:
                        counts["floor_quads"] += 1
                        for cell in cells_fully_in_rectangle(rectangle, cell_m):
                            floor_witnesses.setdefault(cell, source)
                        if support_bounds is None:
                            support_bounds = list(rectangle)
                        else:
                            support_bounds = [min(support_bounds[0], rectangle[0]),
                                              max(support_bounds[1], rectangle[1]),
                                              min(support_bounds[2], rectangle[2]),
                                              max(support_bounds[3], rectangle[3])]
                elif max(abs(height - floor_mid - nominal_maps.PARAMETERS["obstacle_height_m"])
                         for height in heights) <= nominal_maps.PARAMETERS["height_tolerance_m"]:
                    rectangle = _rectangle(points, -guard)
                    if rectangle is not None:
                        counts["wall_quads"] += 1
                        for cell in cells_intersecting_rectangle(rectangle, cell_m):
                            wall_witnesses.setdefault(cell, source)
                else:
                    counts["ignored_height_quads"] += 1
    return floor_witnesses, wall_witnesses, counts, support_bounds


def _fixed(value, expected, where):
    objects._fixed(value, expected, where)


def _opening_intervals(prediction, history_frames):
    """Validate the sealed public E0 result without accepting private additions."""
    keys(prediction, "schema_version candidates conflicts incomplete_observations "
         "rejected_counts history_frames", "public opening prediction")
    require(prediction["schema_version"] == public_geometry.VERSION,
            "public opening prediction version")
    require(prediction["history_frames"] == history_frames,
            "public opening prediction history length")
    require(prediction["conflicts"] == [], "conflicting public opening intervals")
    require(isinstance(prediction["candidates"], list) and prediction["candidates"],
            "public opening intervals missing")
    validated = []
    for index, candidate in enumerate(prediction["candidates"]):
        keys(candidate, "coordinate_intervals_m coordinates_m plane_height_interval_m support",
             f"public opening candidate {index}")
        intervals = candidate["coordinate_intervals_m"]
        require(isinstance(intervals, list) and len(intervals) == 3,
                "opening candidate coordinate intervals")
        for interval in intervals:
            require(isinstance(interval, list) and len(interval) == 2 and
                    all(type(value) in (int, float) and math.isfinite(value)
                        for value in interval) and interval[0] <= interval[1],
                    "invalid opening coordinate interval")
        coordinates = candidate["coordinates_m"]
        require(isinstance(coordinates, list) and len(coordinates) == 3 and
                all(type(value) in (int, float) and math.isfinite(value)
                    for value in coordinates), "invalid opening coordinates")
        require(all(abs(coordinates[axis] - math.fsum(intervals[axis]) / 2) <= 1e-12
                    for axis in range(3)), "opening midpoint differs from interval")
        require(intervals[0][1] < intervals[1][0], "opening interval has no certain gap")
        validated.append(deepcopy(intervals))
    return validated


def _propagate_opening_intervals(wall_rectangles, coordinate_intervals,
                                 wall_thickness_m, cell_m):
    """Outer-approximate wall faces from E0 boundary intervals and observed tops."""
    propagated, records = [], []
    for candidate_index, intervals in enumerate(coordinate_intervals):
        left, right, front = intervals
        opening_mid = math.fsum((left[0], left[1], right[0], right[1])) / 4
        y_band = [front[0] - cell_m, front[1] + wall_thickness_m + cell_m]
        nearby = [rectangle for rectangle in wall_rectangles
                  if rectangle[2] <= y_band[1] and rectangle[3] >= y_band[0]]
        left_support = [rectangle for rectangle in nearby
                        if math.fsum(rectangle[:2]) / 2 < opening_mid and
                        rectangle[0] < left[1]]
        right_support = [rectangle for rectangle in nearby
                         if math.fsum(rectangle[:2]) / 2 > opening_mid and
                         rectangle[1] > right[0]]
        if not left_support or not right_support:
            return [], [], f"opening_{candidate_index}_wall_side_unresolved"
        left_rectangle = [min(value[0] for value in left_support),
                          max(left[1], max(value[1] for value in left_support)),
                          min(front[0], min(value[2] for value in left_support)),
                          max(front[1] + wall_thickness_m,
                              max(value[3] for value in left_support))]
        right_rectangle = [min(right[0], min(value[0] for value in right_support)),
                           max(value[1] for value in right_support),
                           min(front[0], min(value[2] for value in right_support)),
                           max(front[1] + wall_thickness_m,
                               max(value[3] for value in right_support))]
        propagated.extend((left_rectangle, right_rectangle))
        records.append({
            "candidate_index": candidate_index,
            "coordinate_intervals_m": deepcopy(intervals),
            "left_wall_outer_rectangle_xy_m": left_rectangle,
            "right_wall_outer_rectangle_xy_m": right_rectangle,
            "rule": "left_uses_x_left_upper_right_uses_x_right_lower_front_uses_full_interval",
        })
    return propagated, records, "continuous_map_ready"


def build_map(history, public_sensor_spec, common_shape, public_domain,
              nominal_map_parameters, continuous_parameters, *, history_mode="full",
              history_cut_index=None, public_opening_prediction=None):
    """Build one public D-112 map; private geometry and future state are rejected."""
    _fixed(continuous_parameters, PARAMETERS, "continuous map parameters")
    validate_domain(public_domain)
    for key in ("object_radius_m", "object_half_height_m", "pusher_half_size_m"):
        require(public_domain[key] == common_shape[key], "common shape and public domain differ")
    keys(history, "schema_version frames", "continuous map history")
    require(history["schema_version"] == nominal_maps.HISTORY_VERSION, "map history version")
    require(not ({"labels", "actual_future", "world_name", "split", "audit"} & set(history)),
            "private field in map input")
    nominal = nominal_maps.build_map(
        history, public_sensor_spec, common_shape, nominal_map_parameters,
        history_mode=history_mode, history_cut_index=history_cut_index)
    indices = _indices(history_mode, history_cut_index)
    result = {
        "schema_version": VERSION,
        "status": "ground_unresolved" if nominal["ground"] is None else nominal["status"],
        "cell_m": PARAMETERS["cell_m"],
        "assumption_conditioned": True,
        "formal_model_ready": False,
        "geometry_parameters": deepcopy(PARAMETERS),
        "ground": deepcopy(nominal["ground"]),
        "current_object": deepcopy(nominal["current_object"]),
        "observed_floor_cells": [],
        "observed_floor_support_rectangles_xy_m": [],
        "observed_wall_interval_cells": [],
        "observed_wall_interval_rectangles_xy_m": [],
        "opening_boundary_intervals": [],
        "wall_interval_propagation": [],
        "wall_interval_derived_cells": [],
        "wall_interval_witnesses": [],
        "decision_body_core_cells": [],
        "body_occlusion_unknown_cells": [],
        "certified_free_cells": [],
        "observed_support_bounds_xy_m": None,
        "floor_cell_witnesses": [],
        "wall_cell_witnesses": [],
        "support_counts": {"flat_quads": 0, "floor_quads": 0,
                           "wall_quads": 0, "ignored_height_quads": 0},
        "assumptions": [
            "ideal_registered_top_down_depth",
            "locally_horizontal_quad_interpolation",
            "public_vertical_wall_minimum_thickness",
            "public_rigid_body_shapes",
            "whole_cell_containment_not_cell_center",
        ],
    }
    if nominal["ground"] is None:
        return result
    floor, walls, counts, support_bounds = _support(
        history, public_sensor_spec, common_shape, nominal["ground"], indices,
        continuous_parameters)
    current = nominal["current_object"]
    body_core, body_possible = set(), set()
    if current is not None and current["status"] == "association_ready":
        object_intervals = current["position_intervals_m"][:2]
        robot = current["robot_state"]["position_m"][:2]
        robot_intervals = ((robot[0], robot[0]), (robot[1], robot[1]))
        radius = public_domain["object_radius_m"]
        half = public_domain["pusher_half_size_m"][:2]
        body_core = circle_core_cells(object_intervals, radius, PARAMETERS["cell_m"])
        body_core |= box_core_cells(robot_intervals, half, PARAMETERS["cell_m"])
        body_possible = circle_possible_cells(object_intervals, radius, PARAMETERS["cell_m"])
        body_possible |= box_possible_cells(robot_intervals, half, PARAMETERS["cell_m"])
    wall_rectangles = merge_cells_to_rectangles(set(walls), PARAMETERS["cell_m"])
    propagated, propagation_records = [], []
    if public_opening_prediction is None:
        result["status"] = "opening_intervals_unresolved"
    else:
        intervals = _opening_intervals(public_opening_prediction, len(history["frames"]))
        propagated, propagation_records, result["status"] = _propagate_opening_intervals(
            wall_rectangles, intervals, public_domain["obstacle_thickness_m"],
            PARAMETERS["cell_m"])
        result["opening_boundary_intervals"] = intervals
    interval_cells = set()
    interval_witnesses = {}
    for record, rectangles in zip(propagation_records,
                                  zip(propagated[::2], propagated[1::2])):
        for side, rectangle in zip(("left", "right"), rectangles):
            for cell in cells_intersecting_rectangle(rectangle, PARAMETERS["cell_m"]):
                interval_cells.add(cell)
                interval_witnesses.setdefault(cell, (record["candidate_index"], side))
    wall_cells = set(walls) | interval_cells
    observed_floor = set(floor)
    body_core -= wall_cells
    certified = (observed_floor | body_core) - wall_cells
    body_ring = body_possible - body_core - wall_cells
    result.update(
        observed_floor_cells=[list(cell) for cell in sorted(observed_floor)],
        observed_floor_support_rectangles_xy_m=merge_cells_to_rectangles(
            observed_floor, PARAMETERS["cell_m"]),
        observed_wall_interval_cells=[list(cell) for cell in sorted(wall_cells)],
        observed_wall_interval_rectangles_xy_m=merge_cells_to_rectangles(
            wall_cells, PARAMETERS["cell_m"]),
        wall_interval_propagation=propagation_records,
        wall_interval_derived_cells=[list(cell) for cell in sorted(interval_cells)],
        wall_interval_witnesses=[[*cell, *interval_witnesses[cell]]
                                 for cell in sorted(interval_witnesses)],
        decision_body_core_cells=[list(cell) for cell in sorted(body_core)],
        body_occlusion_unknown_cells=[list(cell) for cell in sorted(body_ring)],
        certified_free_cells=[list(cell) for cell in sorted(certified)],
        observed_support_bounds_xy_m=support_bounds,
        floor_cell_witnesses=[[*cell, *floor[cell]] for cell in sorted(floor)],
        wall_cell_witnesses=[[*cell, *walls[cell]] for cell in sorted(walls)],
        support_counts=counts,
    )
    return result


def classify_uncertified_cells(continuous_map, cells):
    """Classify model-blocking cells without turning an unknown into an observed wall."""
    walls = set(map(tuple, continuous_map["observed_wall_interval_cells"]))
    ring = set(map(tuple, continuous_map["body_occlusion_unknown_cells"]))
    floor = set(map(tuple, continuous_map["observed_floor_cells"]))
    result = {key: [] for key in PARAMETERS["unknown_priority"]}
    for cell in sorted(set(cells)):
        if cell in walls:
            kind = "observed_wall_interval"
        elif cell in ring:
            kind = "body_occlusion_unknown"
        elif any((cell[0] + dx, cell[1] + dy) in floor
                 for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
            kind = "sampling_gap_unknown"
        else:
            kind = "outside_observed_region"
        result[kind].append(list(cell))
    return result
