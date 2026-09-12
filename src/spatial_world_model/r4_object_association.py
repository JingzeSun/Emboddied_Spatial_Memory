"""D-088: pure public upright-cylinder association, not a dynamics state.

Chinese contract: docs/METHOD.md#r4-object-association and DATA counterpart.
Only native depth/proprioception values; no files, RGB, labels or controls.
"""
from copy import deepcopy
import math

from .pair_contract import keys, number, require, vector
from .r4_coverage import _rotation, sensor_spec


HISTORY_VERSION = "spatial-history-r4-object-history-v1"
RESULT_VERSION = "spatial-history-r4-object-association-v1"
FIELDS = "time_s width height depth_m camera_position_m camera_xyzw intrinsics ee_position_m ee_velocity_mps"
SHAPE = {"object_radius_m": 0.07, "object_half_height_m": 0.04,
         "pusher_half_size_m": [0.15, 0.025, 0.025],
         "pusher_orientation": "fixed_world_axes_from_common_xy_slide_kinematics"}
SEGMENTATION = {
    "pusher_mask": "projected_box_rectangle_pixel_footprint_intersection",
    "pusher_mask_padding_pixels": 1,
    "height_grouping": "ascending_z_row_column_greedy_total_span",
    "height_group_max_span_m": 0.0002, "top_height_interval_padding_m": 0.0001,
    "component_connectivity": 4, "outer_ring_connectivity": 8,
    "outer_ring_min_height_gap_m": 0.0002, "min_support_pixels": 16,
    "min_row_span_pixels": 6, "min_column_span_pixels": 6,
    "require_single_run_each_row_and_column": True,
    "require_complete_valid_unmasked_outer_ring": True,
    "hole_filling": False, "drop_outlier_pixels": False}
FIT = {
    "center_xy": "intersection_of_all_row_and_column_chord_midpoint_intervals",
    "transition_bounds": "foreground_and_adjacent_background_pixel_centers_at_top_height_endpoints",
    "coordinate_guard_m": 0.000001, "max_center_axis_interval_width_m": 0.025,
    "center_z": "top_height_minus_known_half_height",
    "radial_tolerance": "maximum_full_pixel_diagonal_on_top_height_interval_plus_coordinate_guard",
    "require_full_component_and_outer_ring_radius_checks": True,
    "require_axis_extent_within_diameter_plus_or_minus_twice_radial_tolerance": True,
    "support_weights": "uniform_one_over_top_component_pixel_count",
    "interval_kind": "conditional_raster_geometry_envelope_not_statistical_confidence",
    "candidate_order": "minimum_row_column_then_minimum_height",
    "ambiguous_small_components": "retain_unless_observed_axis_extent_exceeds_diameter_plus_twice_radial_tolerance",
    "rank_candidates_to_choose_one": False, "use_temporal_distance_to_disambiguate": False}
ASSUMPTIONS = ["upright_cylinder_proxy_not_observed_pose", "complete_circular_outline",
               "pixel_transition_envelope", "observed_components_only_uniqueness"]


def common_shape_spec():
    return deepcopy(SHAPE)


def parameters():
    return {"segmentation": deepcopy(SEGMENTATION), "fit": deepcopy(FIT)}


def _fixed(value, expected, where):
    if isinstance(expected, dict):
        keys(value, " ".join(expected), where)
        for key in expected:
            _fixed(value[key], expected[key], f"{where}.{key}")
    elif isinstance(expected, list):
        require(isinstance(value, list) and len(value) == len(expected), where)
        for a, b in zip(value, expected):
            _fixed(a, b, where)
    elif type(expected) in (int, float):
        number(value, where)
        require(type(expected) is not int or type(value) is int, where)
        require(value == expected, where)
    else:
        require(type(value) is type(expected) and value == expected, where)


def _specs(sensor, shape, params):
    _fixed(sensor, sensor_spec(), "public sensor")
    _fixed(shape, SHAPE, "common shape")
    _fixed(params, parameters(), "association parameters")


def _close(a, b):
    return math.isclose(a, b, rel_tol=0, abs_tol=1e-9)


def _validate_frame(frame, source_index):
    require(type(source_index) is int and 0 <= source_index <= 120, "source index")
    keys(frame, FIELDS, "object frame")
    number(frame["time_s"], "time")
    require(_close(frame["time_s"], (source_index - 120) / 10), "relative history clock")
    require(type(frame["width"]) is int and type(frame["height"]) is int
            and frame["width"] == frame["height"] == 80, "native 80x80 required")
    vector(frame["depth_m"], 6400, "depth")
    require(all(d >= 0 for d in frame["depth_m"]), "negative depth")
    for name in ("camera_position_m", "ee_position_m", "ee_velocity_mps"):
        vector(frame[name], 3, name)
    vector(frame["camera_xyzw"], 4, "quaternion")
    vector(frame["intrinsics"], 4, "intrinsics")
    focal = 40 / math.tan(math.radians(21))
    require(all(_close(a, b) for a, b in zip(frame["intrinsics"], [focal, focal, 39.5, 39.5])),
            "v2 intrinsics")
    x, y, z = frame["camera_position_m"]
    require(-0.12 <= x <= 0.12 and _close(z, 1.4), "v2 camera translation")
    if source_index == 0 or source_index >= 110:
        require(_close(y, -0.2), "v2 terminal camera")
    qx, qy, qz, qw = frame["camera_xyzw"]
    require(_close(abs(qx), 1) and all(abs(q) <= 1e-9 for q in (qy, qz, qw)), "v2 top-down camera")


class _Geometry:
    def __init__(self, frame):
        self.camera = frame["camera_position_m"]
        self.rotation = _rotation(frame["camera_xyzw"])
        self.fx, self.fy, self.cx, self.cy = frame["intrinsics"]

    def ray(self, row, col):
        local = [(col - self.cx) / self.fx, (row - self.cy) / self.fy, 1.0]
        return [math.fsum(a*b for a, b in zip(axis, local)) for axis in self.rotation]

    def point(self, pixel, depth):
        out = [c + depth*r for c, r in zip(self.camera, self.ray(*pixel))]
        require(all(math.isfinite(v) for v in out), "nonfinite projection")
        return out

    def plane(self, pixel, height):
        ray = self.ray(*pixel)
        return self.point(pixel, (height-self.camera[2]) / ray[2])

    def diagonal(self, pixels, heights):
        largest = 0.0
        for row, col in pixels:
            for height in heights:
                for sign in (-1, 1):
                    a = self.plane((row-.5, col-sign*.5), height)
                    b = self.plane((row+.5, col+sign*.5), height)
                    largest = max(largest, math.dist(a[:2], b[:2]))
        return largest + FIT["coordinate_guard_m"]

    def pusher_mask(self, position, sensor):
        projected = []
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    delta = [p+s*h-c for p, s, h, c in zip(
                        position, (sx, sy, sz), SHAPE["pusher_half_size_m"], self.camera)]
                    local = [math.fsum(self.rotation[j][i]*delta[j] for j in range(3)) for i in range(3)]
                    if not all(math.isfinite(v) for v in local) or not (
                        sensor["near_depth_m"]+sensor["clip_margin_m"] < local[2]
                        < sensor["far_depth_m"]-sensor["clip_margin_m"]):
                        return None
                    projected.append((self.cy+self.fy*local[1]/local[2], self.cx+self.fx*local[0]/local[2]))
        if not all(math.isfinite(v) for p in projected for v in p):
            return None
        low = [min(p[a] for p in projected) for a in range(2)]
        high = [max(p[a] for p in projected) for a in range(2)]
        base = {(r, c) for r in range(80) for c in range(80)
                if r+.5 >= low[0] and r-.5 <= high[0] and c+.5 >= low[1] and c-.5 <= high[1]}
        return {(r+dr, c+dc) for r, c in base for dr in (-1, 0, 1) for dc in (-1, 0, 1)
                if 0 <= r+dr < 80 and 0 <= c+dc < 80}


def _components(points):
    ordered = sorted(points, key=lambda p: (points[p][2], *p))
    groups, start = [], 0
    while start < len(ordered):
        end = start+1
        while end < len(ordered) and points[ordered[end]][2]-points[ordered[start]][2] <= SEGMENTATION["height_group_max_span_m"]:
            end += 1
        remaining = set(ordered[start:end])
        while remaining:
            seed = min(remaining)
            remaining.remove(seed)
            component, stack = {seed}, [seed]
            while stack:
                r, c = stack.pop()
                for p in ((r-1,c),(r+1,c),(r,c-1),(r,c+1)):
                    if p in remaining:
                        remaining.remove(p)
                        component.add(p)
                        stack.append(p)
            groups.append(component)
        start = end
    return sorted(groups, key=lambda g: (*min(g), min(points[p][2] for p in g)))


def _ring(component):
    return {(r+dr,c+dc) for r,c in component for dr in (-1,0,1) for dc in (-1,0,1)} - component


def _runs(component, axis):
    result = {}
    for p in sorted(component):
        result.setdefault(p[axis], []).append(p[1-axis])
    return {key: sorted(values) for key, values in result.items()}


def _center_interval(geometry, component, heights, image_axis):
    # Rows constrain world x; columns constrain world y (whose sign is reversed).
    coordinate = image_axis
    transitions, intervals = [], []
    for fixed, values in sorted(_runs(component, image_axis).items()):
        edges = []
        for foreground, background in ((values[0], values[0]-1), (values[-1], values[-1]+1)):
            pixels = [(fixed, v) if image_axis == 0 else (v, fixed) for v in (foreground, background)]
            coordinates = [geometry.plane(p, h)[coordinate] for p in pixels for h in heights]
            edges.append([min(coordinates)-FIT["coordinate_guard_m"], max(coordinates)+FIT["coordinate_guard_m"]])
            transitions.append({"world_axis": coordinate, "pixels": [list(p) for p in pixels],
                                "coordinate_interval_m": edges[-1]})
        intervals.append([(edges[0][i]+edges[1][i])/2 for i in (0,1)])
    return [max(v[0] for v in intervals), min(v[1] for v in intervals)], transitions


def _candidate(index, component, points, masked, geometry):
    zmin, zmax = min(points[p][2] for p in component), max(points[p][2] for p in component)
    heights = [zmin-SEGMENTATION["top_height_interval_padding_m"], zmax+SEGMENTATION["top_height_interval_padding_m"]]
    ring = _ring(component)
    delta = geometry.diagonal(component | ring, heights)
    extent = [max(points[p][a] for p in component)-min(points[p][a] for p in component) for a in (0,1)]
    row = {"component_index": index, "classification": "unexcluded_component", "reasons": [],
           "support_pixels": [list(p) for p in sorted(component)], "outer_ring_pixels": [list(p) for p in sorted(ring)],
           "top_height_interval_m": heights, "radial_tolerance_m": delta,
           "observed_axis_extent_m": extent, "position_m": None, "position_intervals_m": None,
           "support_weights": None, "contour_transitions": [], "radius_checks": None,
           "interval_kind": FIT["interval_kind"], "assumption_refs": list(ASSUMPTIONS)}
    diameter = 2*SHAPE["object_radius_m"]
    if any(v > diameter+2*delta for v in extent):
        row["classification"] = "incompatible_extent"
        return row
    spans = [max(p[a] for p in component)-min(p[a] for p in component)+1 for a in (0,1)]
    if (len(component) < SEGMENTATION["min_support_pixels"]
            or spans[0] < SEGMENTATION["min_row_span_pixels"]
            or spans[1] < SEGMENTATION["min_column_span_pixels"]):
        row["reasons"].append("insufficient_support")
    continuous = all(values == list(range(values[0],values[-1]+1))
                     for axis in (0,1) for values in _runs(component,axis).values())
    complete = all(p in points and p not in masked and points[p][2] < zmin-SEGMENTATION["outer_ring_min_height_gap_m"] for p in ring)
    if not continuous or not complete:
        row["reasons"].append("incomplete_outline")
    if row["reasons"]:
        return row
    # image rows -> world x; image columns -> world y.
    ix, tx = _center_interval(geometry, component, heights, 0)
    iy, ty = _center_interval(geometry, component, heights, 1)
    row["contour_transitions"] = tx+ty
    row["position_intervals_m"] = [ix,iy,[h-SHAPE["object_half_height_m"] for h in heights]]
    if any(i[0] > i[1] for i in (ix,iy)):
        row["reasons"].append("center_interval_empty")
        return row
    row["position_m"] = [sum(i)/2 for i in row["position_intervals_m"]]
    if any(i[1]-i[0] > FIT["max_center_axis_interval_width_m"] for i in (ix,iy)):
        row["reasons"].append("center_interval_too_wide")
    center = row["position_m"][:2]
    top = sum(heights)/2
    foreground = [geometry.plane(p,top)[:2] for p in sorted(component)]
    background = [geometry.plane(p,top)[:2] for p in sorted(ring)]
    max_fg = max(math.dist(p,center) for p in foreground)
    min_bg = min(math.dist(p,center) for p in background)
    plane_extent = [max(p[a] for p in foreground)-min(p[a] for p in foreground) for a in (0,1)]
    row["radius_checks"] = {"max_foreground_radius_m": max_fg, "min_outer_ring_radius_m": min_bg,
                            "plane_axis_extent_m": plane_extent}
    if (max_fg > SHAPE["object_radius_m"]+delta or min_bg < SHAPE["object_radius_m"]-delta
            or any(not diameter-2*delta <= v <= diameter+2*delta for v in plane_extent)):
        row["reasons"].append("radius_mismatch")
    if not row["reasons"]:
        row["classification"] = "accepted_candidate"
        row["support_weights"] = [1/len(component)]*len(component)
    return row


def _frame(frame, sensor):
    geometry = _Geometry(frame)
    masked = geometry.pusher_mask(frame["ee_position_m"], sensor)
    out = {"time_s": frame["time_s"], "components": [], "pusher_mask_pixels": None,
           "association_ready": False, "selected_component_index": None,
           "position_m": None, "position_intervals_m": None, "reasons": []}
    if masked is None:
        out["reasons"] = ["pusher_projection_unresolved"]
        return out
    out["pusher_mask_pixels"] = [list(p) for p in sorted(masked)]
    points = {divmod(i,80): geometry.point(divmod(i,80),d) for i,d in enumerate(frame["depth_m"])
              if sensor["near_depth_m"]+sensor["clip_margin_m"] < d < sensor["far_depth_m"]-sensor["clip_margin_m"]}
    available = {p: xyz for p,xyz in points.items() if p not in masked}
    out["components"] = [_candidate(i,g,points,masked,geometry) for i,g in enumerate(_components(available))]
    accepted = [r for r in out["components"] if r["classification"] == "accepted_candidate"]
    if not accepted:
        out["reasons"].append("no_accepted_candidate")
    elif len(accepted) > 1:
        out["reasons"].append("multiple_accepted_candidates")
    if any(r["classification"] == "unexcluded_component" for r in out["components"]):
        out["reasons"].append("unexcluded_support")
    if len(accepted) == 1 and not out["reasons"]:
        row = accepted[0]
        out.update(association_ready=True, selected_component_index=row["component_index"],
                   position_m=deepcopy(row["position_m"]), position_intervals_m=deepcopy(row["position_intervals_m"]))
    return out


def frame_candidates(frame, public_sensor_spec, common_shape, association_parameters, *, source_index):
    """One causal frame only; index verifies the original relative clock."""
    _specs(public_sensor_spec, common_shape, association_parameters)
    _validate_frame(frame,source_index)
    return _frame(frame, public_sensor_spec)


def _velocity(first, last, dt):
    return ([(b-a)/dt for a,b in zip(first["position_m"],last["position_m"])],
            [[(b[0]-a[1])/dt,(b[1]-a[0])/dt] for a,b in zip(first["position_intervals_m"],last["position_intervals_m"])])


def associate_objects(history, public_sensor_spec, common_shape, association_parameters):
    """Resolve exactly two native recent frames; never accept injected candidates."""
    _specs(public_sensor_spec, common_shape, association_parameters)
    keys(history, "schema_version frames", "object history")
    require(history["schema_version"] == HISTORY_VERSION, "object history version")
    frames = history["frames"]
    require(isinstance(frames,list) and len(frames) == 2, "two recent frames required")
    for i,frame in enumerate(frames):
        _validate_frame(frame,119+i)
    require(_close(frames[0]["camera_position_m"][0],frames[1]["camera_position_m"][0]), "camera x changed")
    results = [_frame(frame,public_sensor_spec) for frame in frames]
    ready = all(r["association_ready"] for r in results)
    out = {"schema_version": RESULT_VERSION, "status": "association_ready" if ready else "perception_unresolved",
           "reasons": [] if ready else ["missing_frame_estimate"], "frame_results": results,
           "position_m": deepcopy(results[1]["position_m"]) if ready else None,
           "position_intervals_m": deepcopy(results[1]["position_intervals_m"]) if ready else None,
           "velocity_time_interval_s": [f["time_s"] for f in frames], "interval_mean_velocity_mps": None,
           "interval_mean_velocity_intervals_mps": None, "velocity_kind": "backward_interval_mean",
           "instantaneous_velocity_observed": False, "orientation_xyzw": None,
           "angular_velocity_radps": None, "dynamics_initial_state_ready": False,
           "robot_state": {"position_m": list(frames[1]["ee_position_m"]),
                           "velocity_mps": list(frames[1]["ee_velocity_mps"]), "source": "public_proprioception"}}
    if ready:
        out["interval_mean_velocity_mps"], out["interval_mean_velocity_intervals_mps"] = _velocity(
            results[0],results[1],frames[1]["time_s"]-frames[0]["time_s"])
    return out
