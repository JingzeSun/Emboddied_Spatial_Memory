"""Conservative planar geometry shared by the two D-112 map baselines.

Cells are an implementation cache, not point samples.  A free cell denotes its
entire closed square.  A swept body therefore requests every cell whose square
intersects the continuous sweep; checking cell centres is never sufficient.
"""

from __future__ import annotations

import math

from .pair_contract import require


VERSION = "spatial-history-r4-continuous-geometry-v1"
NUMERIC_EPSILON_M = 1e-12


def cell_bounds(cell, cell_m):
    require(cell_m > 0, "positive cell size required")
    x, y = cell
    return x * cell_m, (x + 1) * cell_m, y * cell_m, (y + 1) * cell_m


def cells_fully_in_rectangle(rectangle, cell_m):
    """Return cells whose entire closed square is contained in a rectangle."""
    x0, x1, y0, y1 = rectangle
    require(x0 <= x1 and y0 <= y1, "ordered rectangle required")
    lo_x = math.ceil((x0 - NUMERIC_EPSILON_M) / cell_m)
    hi_x = math.floor((x1 + NUMERIC_EPSILON_M) / cell_m) - 1
    lo_y = math.ceil((y0 - NUMERIC_EPSILON_M) / cell_m)
    hi_y = math.floor((y1 + NUMERIC_EPSILON_M) / cell_m) - 1
    if lo_x > hi_x or lo_y > hi_y:
        return set()
    return {(x, y) for x in range(lo_x, hi_x + 1)
            for y in range(lo_y, hi_y + 1)}


def cells_intersecting_rectangle(rectangle, cell_m):
    """Return a conservative closed-cell intersection with a rectangle."""
    x0, x1, y0, y1 = rectangle
    require(x0 <= x1 and y0 <= y1, "ordered rectangle required")
    lo_x = math.floor((x0 - NUMERIC_EPSILON_M) / cell_m)
    hi_x = math.floor((x1 + NUMERIC_EPSILON_M) / cell_m)
    lo_y = math.floor((y0 - NUMERIC_EPSILON_M) / cell_m)
    hi_y = math.floor((y1 + NUMERIC_EPSILON_M) / cell_m)
    return {(x, y) for x in range(lo_x, hi_x + 1)
            for y in range(lo_y, hi_y + 1)}


def _point_rectangle_distance2(point, rectangle):
    x0, x1, y0, y1 = rectangle
    dx = max(x0 - point[0], 0., point[0] - x1)
    dy = max(y0 - point[1], 0., point[1] - y1)
    return dx * dx + dy * dy


def _segment_intersects_rectangle(start, end, rectangle):
    """Liang-Barsky intersection, including contact with the boundary."""
    x0, x1, y0, y1 = rectangle
    dx, dy = end[0] - start[0], end[1] - start[1]
    lower, upper = 0., 1.
    for origin, delta, lo, hi in ((start[0], dx, x0, x1),
                                  (start[1], dy, y0, y1)):
        if abs(delta) <= NUMERIC_EPSILON_M:
            if origin < lo - NUMERIC_EPSILON_M or origin > hi + NUMERIC_EPSILON_M:
                return False
            continue
        first, second = (lo - origin) / delta, (hi - origin) / delta
        if first > second:
            first, second = second, first
        lower, upper = max(lower, first), min(upper, second)
        if lower > upper + NUMERIC_EPSILON_M:
            return False
    return True


def _point_segment_distance2(point, start, end):
    dx, dy = end[0] - start[0], end[1] - start[1]
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return (point[0] - start[0]) ** 2 + (point[1] - start[1]) ** 2
    fraction = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length2
    fraction = max(0., min(1., fraction))
    nearest = start[0] + fraction * dx, start[1] + fraction * dy
    return (point[0] - nearest[0]) ** 2 + (point[1] - nearest[1]) ** 2


def _orientation(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_intersect(a, b, c, d):
    values = (_orientation(a, b, c), _orientation(a, b, d),
              _orientation(c, d, a), _orientation(c, d, b))
    if ((values[0] > NUMERIC_EPSILON_M and values[1] < -NUMERIC_EPSILON_M)
            or (values[0] < -NUMERIC_EPSILON_M and values[1] > NUMERIC_EPSILON_M)):
        if ((values[2] > NUMERIC_EPSILON_M and values[3] < -NUMERIC_EPSILON_M)
                or (values[2] < -NUMERIC_EPSILON_M and values[3] > NUMERIC_EPSILON_M)):
            return True
    # Collinear/touching cases are covered by a zero point-to-segment distance.
    return min(_point_segment_distance2(a, c, d),
               _point_segment_distance2(b, c, d),
               _point_segment_distance2(c, a, b),
               _point_segment_distance2(d, a, b)) <= NUMERIC_EPSILON_M ** 2


def _segment_rectangle_distance2(start, end, rectangle):
    if _segment_intersects_rectangle(start, end, rectangle):
        return 0.
    x0, x1, y0, y1 = rectangle
    corners = ((x0, y0), (x0, y1), (x1, y0), (x1, y1))
    edges = ((corners[0], corners[1]), (corners[0], corners[2]),
             (corners[1], corners[3]), (corners[2], corners[3]))
    result = min(_point_rectangle_distance2(start, rectangle),
                 _point_rectangle_distance2(end, rectangle),
                 *( _point_segment_distance2(corner, start, end) for corner in corners))
    if any(_segments_intersect(start, end, first, second) for first, second in edges):
        return 0.
    return result


def circle_sweep_intersecting_cells(start, end, radius, cell_m):
    """All grid squares touched by a circle translated along one segment."""
    require(radius > 0, "positive circle radius required")
    bounds = (min(start[0], end[0]) - radius,
              max(start[0], end[0]) + radius,
              min(start[1], end[1]) - radius,
              max(start[1], end[1]) + radius)
    candidates = cells_intersecting_rectangle(bounds, cell_m)
    radius2 = (radius + NUMERIC_EPSILON_M) ** 2
    return {cell for cell in candidates
            if _segment_rectangle_distance2(start, end, cell_bounds(cell, cell_m)) <= radius2}


def box_sweep_intersecting_cells(start, end, half_size, cell_m):
    """All grid squares touched by a fixed-axis box translated along a segment."""
    require(len(half_size) == 2 and all(value > 0 for value in half_size),
            "positive box half size required")
    bounds = (min(start[0], end[0]) - half_size[0],
              max(start[0], end[0]) + half_size[0],
              min(start[1], end[1]) - half_size[1],
              max(start[1], end[1]) + half_size[1])
    candidates = cells_intersecting_rectangle(bounds, cell_m)
    result = set()
    for cell in candidates:
        x0, x1, y0, y1 = cell_bounds(cell, cell_m)
        expanded = (x0 - half_size[0], x1 + half_size[0],
                    y0 - half_size[1], y1 + half_size[1])
        if _segment_intersects_rectangle(start, end, expanded):
            result.add(cell)
    return result


def circle_core_cells(position_intervals, radius, cell_m):
    """Cells wholly inside the circle for every allowed centre position."""
    require(len(position_intervals) == 2 and all(len(axis) == 2 for axis in position_intervals),
            "two position intervals required")
    centers = [(x, y) for x in position_intervals[0] for y in position_intervals[1]]
    bounds = (position_intervals[0][0] - radius, position_intervals[0][1] + radius,
              position_intervals[1][0] - radius, position_intervals[1][1] + radius)
    result = set()
    for cell in cells_intersecting_rectangle(bounds, cell_m):
        x0, x1, y0, y1 = cell_bounds(cell, cell_m)
        corners = ((x0, y0), (x0, y1), (x1, y0), (x1, y1))
        if max(math.dist(point, center) for point in corners for center in centers) <= radius:
            result.add(cell)
    return result


def box_core_cells(position_intervals, half_size, cell_m):
    """Cells wholly inside the fixed-axis box for every allowed centre position."""
    core = (position_intervals[0][1] - half_size[0],
            position_intervals[0][0] + half_size[0],
            position_intervals[1][1] - half_size[1],
            position_intervals[1][0] + half_size[1])
    return cells_fully_in_rectangle(core, cell_m) if core[0] <= core[1] and core[2] <= core[3] else set()


def first_uncertified_sweep(trajectory, certified_free_cells, *, object_radius,
                            pusher_half_size, cell_m):
    """Audit the first complete swept shape that leaves the certified cell union."""
    require(len(trajectory) >= 1, "trajectory required")
    free = set(certified_free_cells)
    for step in range(1, len(trajectory)):
        previous, current = trajectory[step - 1], trajectory[step]
        object_cells = circle_sweep_intersecting_cells(
            previous["object_position_m"], current["object_position_m"], object_radius, cell_m)
        pusher_cells = box_sweep_intersecting_cells(
            previous["robot_position_m"], current["robot_position_m"], pusher_half_size, cell_m)
        object_denied, pusher_denied = object_cells - free, pusher_cells - free
        if object_denied or pusher_denied:
            return {
                "complete_sweep_contained": False,
                "first_uncertified_step": step,
                "object_denied_cells": sorted(object_denied),
                "pusher_denied_cells": sorted(pusher_denied),
            }
    return {"complete_sweep_contained": True, "first_uncertified_step": None,
            "object_denied_cells": [], "pusher_denied_cells": []}
