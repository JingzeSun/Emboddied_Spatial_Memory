"""D-090: public surface map with a separate observed-wall height rule.

Nominal raster geometry has explicit assumptions; it is not a certified free
volume or a complete reconstruction. See METHOD#r4-map-control-engineering.
"""
from copy import deepcopy
import math

from .pair_contract import keys, require
from . import r4_object_association as objects
from . import r4_object_surfaces as surfaces
from .r4_coverage import _indices

VERSION = "spatial-history-r4-observed-map-v2"
HISTORY_VERSION = "spatial-history-r4-map-history-v1"
PARAMETERS = {"cell_m": .01, "origin_xy_m": [0.,0.], "minimum_ground_axis_extent_m": .3,
              "height_tolerance_m": .0004, "quad_height_span_m": .0002,
              "obstacle_height_m": .3, "obstacle_thickness_m": .05,
              "raster_rule": "cell_center_inside_observed_horizontal_quad",
              "ground_rule": "lowest_large_observed_horizontal_plane",
              "dynamic_rule": "same_frame_top_and_conditional_side_support",
              "static_rule": "observed_common_wall_height_relative_to_same_frame_ground"}


def parameters():
    return deepcopy(PARAMETERS)


def _cell(point):
    return tuple(math.floor(v/PARAMETERS["cell_m"]) for v in point[:2])


def _rect_cells(rect):
    h = PARAMETERS["cell_m"]
    x0,x1,y0,y1 = rect
    for x in range(math.ceil(x0/h-.5),math.floor(x1/h-.5)+1):
        for y in range(math.ceil(y0/h-.5),math.floor(y1/h-.5)+1):
            yield x,y


def _rectangles(cells):
    """Merge occupied row runs, then exactly matching consecutive rows."""
    rows = {}
    for x,y in cells:
        rows.setdefault(y,[]).append(x)
    active, rectangles = {}, []
    previous = None
    for y,xs in sorted(rows.items()):
        xs = sorted(xs)
        spans = []
        for x in xs:
            if spans and spans[-1][1]+1 == x:
                spans[-1][1] = x
            else:
                spans.append([x,x])
        next_active = {}
        for lo,hi in spans:
            key = lo,hi
            if previous is not None and previous+1 == y and key in active:
                box = active.pop(key)
                box[3] = y
            else:
                box = [lo,hi,y,y]
            next_active[key] = box
        rectangles.extend(active.values())
        active,previous = next_active,y
    rectangles.extend(active.values())
    h=PARAMETERS["cell_m"]
    return [[x0*h,(x1+1)*h,y0*h,(y1+1)*h] for x0,x1,y0,y1 in sorted(rectangles)]


def build_map(history, public_sensor_spec, common_shape, map_parameters, *, history_mode="full", history_cut_index=None):
    objects._fixed(map_parameters,PARAMETERS,"map parameters")
    objects._specs(public_sensor_spec,common_shape,objects.parameters())
    keys(history,"schema_version frames","map history")
    require(history["schema_version"]==HISTORY_VERSION,"map history version")
    indices=_indices(history_mode,history_cut_index)
    frames=history["frames"]
    require(isinstance(frames,list) and len(frames)==len(indices),"map causal slice")
    for frame,index in zip(frames,indices):
        objects._validate_frame(frame,index)
    require(all(objects._close(f["camera_position_m"][0],frames[0]["camera_position_m"][0]) for f in frames),"map camera x changed")
    # Entries remain geometric observations until ground height is selected.
    observations, ground_candidates, ambiguity, frame_audit = {},[],{},[]
    for local,(frame,index) in enumerate(zip(frames,indices)):
        result=surfaces.frame_candidates(frame,public_sensor_spec,common_shape,surfaces.parameters(),source_index=index)
        geometry=surfaces.Geometry(frame)
        stats={"local_index":local,"source_index":index,"time_s":frame["time_s"],
               "association_ready":result["association_ready"],"reasons":list(result["reasons"]),"accepted_components":0,
               "unexcluded_components":0,"attached_side_components":0,"wall_height_resolved_components":0,
               "static_eligible_components":0,"supported_quads":0}
        large=[c for c in result["components"] if c["classification"]=="incompatible_extent"
               and min(c["observed_axis_extent_m"])>=PARAMETERS["minimum_ground_axis_extent_m"]]
        local_ground=min((sum(c["top_height_interval_m"])/2 for c in large),default=None)
        for component in result["components"]:
            pixels=set(map(tuple,component["support_pixels"]))
            kind=component["classification"]
            wall_height=(kind=="unexcluded_component" and local_ground is not None
                         and all(abs(h-local_ground-PARAMETERS["obstacle_height_m"])<=PARAMETERS["height_tolerance_m"]
                                 for h in component["top_height_interval_m"]))
            if kind!="incompatible_extent" and not wall_height:
                role={"accepted_candidate":"accepted_components", "attached_side_support":"attached_side_components"}.get(kind,"unexcluded_components")
                stats[role]+=1
                if role=="unexcluded_components":
                    for p in pixels:
                        ambiguity[_cell(geometry.point(p,frame["depth_m"][p[0]*80+p[1]]))]=local
                continue
            stats["static_eligible_components"]+=1
            stats["wall_height_resolved_components"]+=int(wall_height)
            heights=component["top_height_interval_m"]
            if min(component["observed_axis_extent_m"]) >= PARAMETERS["minimum_ground_axis_extent_m"]:
                ground_candidates.append({"interval_m":list(heights),"source":[local,*min(pixels)]})
            for r,c in sorted(pixels):
                quad=((r,c),(r+1,c),(r,c+1),(r+1,c+1))
                if not all(p in pixels for p in quad):
                    continue
                pts=[geometry.point(p,frame["depth_m"][p[0]*80+p[1]]) for p in quad]
                if max(p[2] for p in pts)-min(p[2] for p in pts)>PARAMETERS["quad_height_span_m"]:
                    continue
                stats["supported_quads"]+=1
                # Axis-aligned nominal patch, explicitly not a free-volume proof.
                rect=[min(p[0] for p in pts),max(p[0] for p in pts),min(p[1] for p in pts),max(p[1] for p in pts)]
                for cell in _rect_cells(rect):
                    bucket=observations.setdefault(cell,[])
                    same=next((v for v in bucket if max(v["height_m"][1],heights[1])-min(v["height_m"][0],heights[0]) <= PARAMETERS["height_tolerance_m"]),None)
                    if same is None:
                        bucket.append({"height_m":list(heights),"first_source":[local,r,c],"last_source":[local,r,c],"quad_observations":1})
                    else:
                        same["height_m"]=[min(same["height_m"][0],heights[0]),max(same["height_m"][1],heights[1])]
                        same["last_source"]=[local,r,c]
                        same["quad_observations"]+=1
        frame_audit.append(stats)
    ground=None
    if ground_candidates:
        first=min(ground_candidates,key=lambda g:(sum(g["interval_m"]),g["source"]))
        compatible=[g for g in ground_candidates if max(g["interval_m"][0],first["interval_m"][0]) <= min(g["interval_m"][1],first["interval_m"][1])]
        interval=[max(g["interval_m"][0] for g in compatible),min(g["interval_m"][1] for g in compatible)]
        if interval[0]<=interval[1]:
            ground={"height_interval_m":interval,"source_witnesses":[g["source"] for g in compatible]}
    floor,occupied,unknown=set(),set(),set(ambiguity)
    cells=[]
    for cell,bucket in sorted(observations.items()):
        roles=[]
        for item in bucket:
            role="unclassified_surface"
            if ground is not None:
                z=sum(item["height_m"])/2; floor_z=sum(ground["height_interval_m"])/2
                if abs(z-floor_z)<=PARAMETERS["height_tolerance_m"]: role="floor_proxy"
                elif abs(z-floor_z-PARAMETERS["obstacle_height_m"])<=PARAMETERS["height_tolerance_m"]: role="wall_top_proxy"
            roles.append(role)
            cells.append({"cell_xy":list(cell),"role":role,**item})
        if "floor_proxy" in roles: floor.add(cell)
        if "wall_top_proxy" in roles: occupied.add(cell)
        if len(set(roles))>1 or "unclassified_surface" in roles: unknown.add(cell)
        elif cell in ambiguity and max(v["last_source"][0] for v in bucket)>ambiguity[cell]: unknown.discard(cell)
    conflicts=floor & occupied
    unknown.update(conflicts)
    free=floor-occupied-unknown
    object_state=None
    if indices[-2:]==[119,120]:
        object_state=surfaces.associate_objects({"schema_version":objects.HISTORY_VERSION,"frames":frames[-2:]},
                                               public_sensor_spec,common_shape,surfaces.parameters())
    return {"schema_version":VERSION,"status":"nominal_map_ready" if ground else "ground_unresolved",
            "cell_m":PARAMETERS["cell_m"],"ground":ground,"surface_cells":cells,
            "floor_cells":[list(c) for c in sorted(floor)],"nominal_free_cells":[list(c) for c in sorted(free)],
            "occupied_cells":[list(c) for c in sorted(occupied)],"unknown_cells":[list(c) for c in sorted(unknown)],
            "conflict_cells":[list(c) for c in sorted(conflicts)],"obstacle_rectangles_xy_m":_rectangles(occupied),
            "frame_audit":frame_audit,"current_object":object_state,"certified_free_volume":False,
            "assumptions":["lowest_large_horizontal_plane_is_support","locally_horizontal_quad_interpolation",
                           "static_large_surfaces","common_wall_height_surface_is_nominally_static",
                           "side_support_is_conditional_same_cylinder","observed_wall_tops_extruded_to_observed_support",
                           "cell_center_raster_is_nominal_geometry_not_interval_certification"]}
