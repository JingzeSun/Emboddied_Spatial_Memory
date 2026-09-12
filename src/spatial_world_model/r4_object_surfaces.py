"""D-090: conditional cylinder side-surface ownership from public depth only.

See METHOD#r4-frontend-revision-v2. This is a nominal geometric assumption,
not a semantic identity certificate or an observed instantaneous rigid state.
"""
from copy import deepcopy
import math

from . import r4_object_association as base
from .pair_contract import keys, require

VERSION = "spatial-history-r4-object-surfaces-v2"
PARAMETERS = {"attachment": "all_pixels_four_adjacent_to_one_accepted_top",
              "height": "below_top_within_common_full_cylinder_height",
              "radial": "whole_center_box_inside_pixel_diagonal_annulus",
              "certificate": False}


def parameters():
    return deepcopy(PARAMETERS)


class Geometry(base._Geometry):
    def diagonal(self, pixels, heights):
        # The validated camera is strictly top-down. Its ray plane z is constant:
        # every pixel diagonal has this length, independent of pixel location.
        return max(abs(self.camera[2]-h) for h in heights)*math.hypot(1/self.fx, 1/self.fy) + base.FIT["coordinate_guard_m"]


def _ownership(fragment, candidate, points):
    support = set(map(tuple, candidate["support_pixels"]))
    ring = set(map(tuple, candidate["outer_ring_pixels"]))
    center = candidate["position_intervals_m"][:2]
    top = candidate["top_height_interval_m"]
    tolerance = max(candidate["radial_tolerance_m"], fragment["radial_tolerance_m"])
    radius = base.SHAPE["object_radius_m"]
    bounds = []
    for pixel in map(tuple, fragment["support_pixels"]):
        r, c = pixel
        if pixel not in ring or not any((r+dr,c+dc) in support for dr,dc in ((1,0),(-1,0),(0,1),(0,-1))):
            return None
        x,y,z = points[pixel]
        if not top[0]-2*base.SHAPE["object_half_height_m"] <= z < top[0]-base.SEGMENTATION["outer_ring_min_height_gap_m"]:
            return None
        low = math.hypot(*(max(lo-v,0,v-hi) for v,(lo,hi) in zip((x,y),center)))
        high = math.hypot(*(max(abs(v-lo),abs(v-hi)) for v,(lo,hi) in zip((x,y),center)))
        if low < radius-tolerance or high > radius+tolerance:
            return None
        bounds.append({"pixel":list(pixel), "height_m":z, "radial_interval_m":[low,high]})
    return {"parent_component_index":candidate["component_index"], "points":bounds,
            "radial_tolerance_m":tolerance, "conditional_same_cylinder":True,
            "identity_certified":False}


def frame_candidates(frame, sensor, shape, surface_parameters, *, source_index):
    base._fixed(surface_parameters, PARAMETERS, "surface parameters")
    base._specs(sensor, shape, base.parameters())
    base._validate_frame(frame, source_index)
    geometry = Geometry(frame)
    masked = geometry.pusher_mask(frame["ee_position_m"], sensor)
    result = {"time_s":frame["time_s"], "components":[], "pusher_mask_pixels":None,
              "association_ready":False, "selected_component_index":None,
              "position_m":None, "position_intervals_m":None, "reasons":[],
              "surface_ownership_certified":False}
    if masked is None:
        result["reasons"] = ["pusher_projection_unresolved"]
        return result
    result["pusher_mask_pixels"] = [list(p) for p in sorted(masked)]
    points = {divmod(i,80):geometry.point(divmod(i,80),d) for i,d in enumerate(frame["depth_m"])
              if sensor["near_depth_m"]+sensor["clip_margin_m"] < d < sensor["far_depth_m"]-sensor["clip_margin_m"]}
    components = base._components({p:xyz for p,xyz in points.items() if p not in masked})
    result["components"] = [base._candidate(i,c,points,masked,geometry) for i,c in enumerate(components)]
    accepted = [c for c in result["components"] if c["classification"] == "accepted_candidate"]
    for fragment in result["components"]:
        if fragment["classification"] != "unexcluded_component":
            continue
        parents = [e for c in accepted if (e := _ownership(fragment,c,points)) is not None]
        fragment["possible_parent_count"] = len(parents)
        if len(parents) == 1:
            fragment["original_classification"] = fragment["classification"]
            fragment["classification"] = "attached_side_support"
            fragment["ownership"] = parents[0]
            # Original reasons remain a record of why this is not a second top.
    if not accepted:
        result["reasons"].append("no_accepted_candidate")
    elif len(accepted) > 1:
        result["reasons"].append("multiple_accepted_candidates")
    if any(c["classification"] == "unexcluded_component" for c in result["components"]):
        result["reasons"].append("unexcluded_support")
    if len(accepted) == 1 and not result["reasons"]:
        row = accepted[0]
        result.update(association_ready=True, selected_component_index=row["component_index"],
                      position_m=deepcopy(row["position_m"]),
                      position_intervals_m=deepcopy(row["position_intervals_m"]))
    return result


def associate_objects(history, sensor, shape, surface_parameters):
    keys(history, "schema_version frames", "object history")
    require(history["schema_version"] == base.HISTORY_VERSION, "object history version")
    frames = history["frames"]
    require(isinstance(frames,list) and len(frames)==2, "two recent frames required")
    results = [frame_candidates(f,sensor,shape,surface_parameters,source_index=119+i) for i,f in enumerate(frames)]
    require(base._close(frames[0]["camera_position_m"][0],frames[1]["camera_position_m"][0]), "camera x changed")
    ready = all(r["association_ready"] for r in results)
    result = {"schema_version":VERSION, "status":"association_ready" if ready else "perception_unresolved",
              "reasons":[] if ready else ["missing_frame_estimate"], "frame_results":results,
              "position_m":deepcopy(results[1]["position_m"]) if ready else None,
              "position_intervals_m":deepcopy(results[1]["position_intervals_m"]) if ready else None,
              "velocity_time_interval_s":[f["time_s"] for f in frames],
              "interval_mean_velocity_mps":None, "interval_mean_velocity_intervals_mps":None,
              "velocity_kind":"backward_interval_mean", "instantaneous_velocity_observed":False,
              "orientation_xyzw":None, "angular_velocity_radps":None, "dynamics_initial_state_ready":False,
              "surface_ownership_certified":False,
              "robot_state":{"position_m":list(frames[1]["ee_position_m"]),
                             "velocity_mps":list(frames[1]["ee_velocity_mps"]),"source":"public_proprioception"}}
    if ready:
        result["interval_mean_velocity_mps"],result["interval_mean_velocity_intervals_mps"] = base._velocity(
            results[0],results[1],frames[1]["time_s"]-frames[0]["time_s"])
    return result
