"""Continuous D-112 containment using fixed Shapely/GEOS polygon operations.

Observed free rectangles and current-body cores are inner approximations.  A
circle sweep uses the analytic secant scale so every chord of the polygonal
buffer lies outside the requested circle.  Thus approximation can reject a
valid sweep but cannot certify an uncovered circular sliver as free.
"""

from __future__ import annotations

import math

import shapely
from shapely.geometry import LineString, MultiPoint, Point, box
from shapely.ops import unary_union

from .pair_contract import require


VERSION = "spatial-history-r4-continuous-shapes-v1"
SHAPELY_VERSION = "2.1.2"


def _dependency_versions():
    require(shapely.__version__ == SHAPELY_VERSION, "unregistered Shapely version")
    return {"shapely": shapely.__version__, "geos": shapely.geos_version_string}


def _inner_circle(center, radius, quadrant_segments):
    return Point(center).buffer(radius, quad_segs=quadrant_segments)


def _outer_circle_radius(radius, quadrant_segments, numeric_guard_m=0.):
    return radius / math.cos(math.pi / (4 * quadrant_segments)) + numeric_guard_m


def _outer_circle_sweep(start, end, radius, quadrant_segments, numeric_guard_m=0.):
    outer_radius = _outer_circle_radius(radius, quadrant_segments, numeric_guard_m)
    if start[0] == end[0] and start[1] == end[1]:
        return Point(start[:2]).buffer(outer_radius, quad_segs=quadrant_segments)
    return LineString((start[:2], end[:2])).buffer(
        outer_radius, quad_segs=quadrant_segments, cap_style="round", join_style="round")


def _box_sweep(start, end, half_size):
    points = []
    for center in (start, end):
        for sx in (-1, 1):
            for sy in (-1, 1):
                points.append((center[0] + sx * half_size[0],
                               center[1] + sy * half_size[1]))
    return MultiPoint(points).convex_hull


def _rectangles_union(rectangles):
    shapes = [box(rectangle[0], rectangle[2], rectangle[1], rectangle[3])
              for rectangle in rectangles]
    return unary_union(shapes) if shapes else Point().buffer(0)


def assumption_free_geometry(continuous_map, public_domain, *, include_common_body_core=True):
    """Inner free geometry minus the full pessimistic observed-wall intervals."""
    _dependency_versions()
    q = continuous_map["geometry_parameters"]["circle_quadrant_segments"]
    floor = _rectangles_union(continuous_map["observed_floor_support_rectangles_xy_m"])
    walls = _rectangles_union(continuous_map["observed_wall_interval_rectangles_xy_m"])
    free_parts = [floor]
    current = continuous_map["current_object"]
    if include_common_body_core and current is not None and current["status"] == "association_ready":
        intervals = current["position_intervals_m"][:2]
        radius = public_domain["object_radius_m"]
        object_core = None
        for center in ((x, y) for x in intervals[0] for y in intervals[1]):
            circle = _inner_circle(center, radius, q)
            object_core = circle if object_core is None else object_core.intersection(circle)
        robot = current["robot_state"]["position_m"]
        half = public_domain["pusher_half_size_m"][:2]
        free_parts.extend((object_core,
                           box(robot[0] - half[0], robot[1] - half[1],
                               robot[0] + half[0], robot[1] + half[1])))
    free = unary_union(free_parts)
    return free.difference(walls) if not walls.is_empty else free


def audit_trajectory(continuous_map, trajectory, public_domain, *, object_radius_m=None):
    """Return the first outer-approximated body sweep not covered by inner free geometry."""
    require(isinstance(trajectory, list) and trajectory, "trajectory required")
    dependency_versions = _dependency_versions()
    parameters = continuous_map["geometry_parameters"]
    q = parameters["circle_quadrant_segments"]
    require(math.isclose(parameters["circle_outer_radius_scale"],
                         1 / math.cos(math.pi / (4 * q)), rel_tol=0, abs_tol=1e-15),
            "circle outer scale does not match quadrant segments")
    free = assumption_free_geometry(continuous_map, public_domain)
    radius = (public_domain["object_radius_m"] if object_radius_m is None
              else object_radius_m)
    require(type(radius) in (int, float) and radius >= public_domain["object_radius_m"],
            "audit object radius must contain the public cylinder radius")
    half = public_domain["pusher_half_size_m"][:2]
    maximum_uncovered_area = 0.
    cached_positions = None
    cached_uncovered = None
    for step in range(1, len(trajectory)):
        previous, current = trajectory[step - 1], trajectory[step]
        positions = (tuple(previous["object_position_m"][:2]),
                     tuple(current["object_position_m"][:2]),
                     tuple(previous["robot_position_m"][:2]),
                     tuple(current["robot_position_m"][:2]))
        if positions == cached_positions:
            object_uncovered, pusher_uncovered = cached_uncovered
        else:
            object_sweep = _outer_circle_sweep(
                previous["object_position_m"], current["object_position_m"], radius, q,
                parameters["numeric_guard_m"])
            pusher_sweep = _box_sweep(
                previous["robot_position_m"], current["robot_position_m"], half)
            object_uncovered = object_sweep.difference(free)
            pusher_uncovered = pusher_sweep.difference(free)
            cached_positions = positions
            cached_uncovered = (object_uncovered, pusher_uncovered)
        maximum_uncovered_area = max(maximum_uncovered_area,
                                     object_uncovered.area, pusher_uncovered.area)
        if not object_uncovered.is_empty or not pusher_uncovered.is_empty:
            body = "object" if not object_uncovered.is_empty else "pusher"
            first_uncovered = (object_uncovered if body == "object" else pusher_uncovered)
            point = first_uncovered.representative_point()
            cell_m = continuous_map["cell_m"]
            cell = (math.floor(point.x / cell_m), math.floor(point.y / cell_m))
            from .r4_continuous_map import classify_uncertified_cells
            classified = classify_uncertified_cells(continuous_map, {cell})
            region_kind = next(name for name, cells in classified.items() if cells)
            return {
                "assumption_conditioned": True,
                "complete_sweep_contained": False,
                "first_uncertified_step": step,
                "first_uncertified_time_s": step * .002,
                "body": body,
                "region_kind": region_kind,
                "representative_cell": list(cell),
                "object_uncovered_area_m2": object_uncovered.area,
                "pusher_uncovered_area_m2": pusher_uncovered.area,
                "outer_circle_radial_excess_m":
                    _outer_circle_radius(radius, q, parameters["numeric_guard_m"]) - radius,
                "dependency_versions": dependency_versions,
            }
    return {
        "assumption_conditioned": True,
        "complete_sweep_contained": True,
        "first_uncertified_step": None,
        "first_uncertified_time_s": None,
        "body": None,
        "region_kind": None,
        "representative_cell": None,
        "object_uncovered_area_m2": 0.,
        "pusher_uncovered_area_m2": 0.,
        "outer_circle_radial_excess_m": _outer_circle_radius(
            radius, q, parameters["numeric_guard_m"]) - radius,
        "dependency_versions": dependency_versions,
    }
