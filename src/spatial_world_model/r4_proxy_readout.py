"""Public nominal task readout; never calls the private trajectory assessor."""
import math

from .pair_contract import require
from .r4_query_v2 import validate_goal
from .r4_object_association import _fixed

PARAMETERS={"expected_task_openings":2,"wall_thickness_m":.05,"wall_band_tolerance_m":.02,
            "minimum_wall_band_m":.02,"maximum_wall_band_m":.08,"object_radius_m":.07}


def parameters(): return dict(PARAMETERS)


def public_openings(observed_map):
    free=set(map(tuple,observed_map["nominal_free_cells"]))
    cell=observed_map["cell_m"]
    boxes=[b for b in observed_map["obstacle_rectangles_xy_m"]
           if PARAMETERS["minimum_wall_band_m"] <= b[3]-b[2] <= PARAMETERS["maximum_wall_band_m"]]
    groups=[]
    for box in sorted(boxes,key=lambda b:(b[2],b[0])):
        if groups and box[2] <= max(b[3] for b in groups[-1]) + observed_map["cell_m"]:
            groups[-1].append(box)
        else: groups.append([box])
    openings=[]
    for group in groups:
        front=min(b[2] for b in group); back=max(b[3] for b in group)
        if abs(back-front-PARAMETERS["wall_thickness_m"])>PARAMETERS["wall_band_tolerance_m"]: continue
        spans=[]
        for box in sorted(group):
            if spans and box[0]<=spans[-1][1]: spans[-1][1]=max(spans[-1][1],box[1])
            else: spans.append(box[:2])
        for left,right in zip(spans,spans[1:]):
            if left[1]<right[0]:
                columns=[x for x in range(math.ceil(left[1]/cell),math.floor(right[0]/cell))
                         if all((x,y) in free for y in range(math.floor(front/cell),math.ceil(back/cell)))]
                if not columns: continue
                openings.append({"x_bounds_m":[left[1],right[0]],"plane_y_m":front+PARAMETERS["wall_thickness_m"]/2,
                                 "source_rectangles":group,"observed_through_columns":columns,
                                 "coordinate_uncertainty_certified":False})
    return sorted(openings,key=lambda v:(v["plane_y_m"],v["x_bounds_m"]))


def readout(observed_map,proxy,goal,readout_parameters):
    _fixed(readout_parameters,PARAMETERS,"readout parameters"); validate_goal(goal)
    openings=public_openings(observed_map)
    result={"status":"task_readout_unresolved","openings":openings,"events":[],"nominal_success":None,
            "nominal_object_contact_intervals":None,"formal_prediction":None}
    samples=proxy["trajectory"]
    if proxy["status"]!="nominal_complete" or samples is None or len(samples)!=10001 or len(openings)!=2: return result
    active=[None,None]; completed=[[],[]]; events=[]
    goal_all=speed_all=True; radius=PARAMETERS["object_radius_m"]
    eps=goal["containment_boundary_tolerance_m"]
    for index,sample in enumerate(samples):
        require(sample["step_index"]==index,"proxy step order")
        pos=sample["object_position_m"]; time=sample["time_s"]
        if index:
            old=samples[index-1]
            for gate,opening in enumerate(openings):
                y=opening["plane_y_m"]
                if active[gate] is not None and pos[1]<y:
                    events[active[gate]]["status"]="cancelled"; active[gate]=None
                if old["object_position_m"][1]<y<=pos[1]:
                    fraction=(y-old["object_position_m"][1])/(pos[1]-old["object_position_m"][1])
                    cross_time=old["time_s"]+fraction*(time-old["time_s"])
                    cross_x=old["object_position_m"][0]+fraction*(pos[0]-old["object_position_m"][0])
                    valid=opening["x_bounds_m"][0]-eps<=cross_x<=opening["x_bounds_m"][1]+eps
                    ordered=gate==0 or any(t<cross_time for t in completed[0])
                    events.append({"gate_index":gate,"cross_time_s":cross_time,"cross_x_m":cross_x,
                                   "status":"active" if valid and ordered else "invalid","completion_time_s":None})
                    active[gate]=len(events)-1 if valid and ordered else None
                if active[gate] is not None and pos[1]-radius>=y+PARAMETERS["wall_thickness_m"]/2-eps:
                    events[active[gate]].update(status="completed",completion_time_s=time)
                    completed[gate].append(time); active[gate]=None
        if time>=goal["settled_interval_s"][0]-1e-9:
            for axis,bounds in enumerate((goal["goal_x_bounds_m"],goal["goal_y_bounds_m"])):
                goal_all &= pos[axis]-radius>=bounds[0]-eps and pos[axis]+radius<=bounds[1]+eps
            speed_all &= math.sqrt(sum(v*v for v in sample["object_velocity_mps"]))<=goal["maximum_object_linear_speed_mps"]
    result.update(status="nominal_readout_complete",events=events,nominal_success=bool(all(completed) and goal_all and speed_all),
                  settled_containment=bool(goal_all),settled_speed=bool(speed_all),ordered_gate_passage=bool(all(completed)),
                  nominal_object_contact_intervals=[any(s["object_obstacle_contact"] for s in samples[i*50+1:(i+1)*50+1]) for i in range(200)])
    return result
