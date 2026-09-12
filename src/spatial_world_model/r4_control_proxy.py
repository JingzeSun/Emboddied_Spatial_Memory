"""Finite-force planar diagnostic predictor for D-089; no actual future input.

All nine controls must start from the same public map. This engineering proxy
does not certify initial-state/geometry uncertainty for formal M or P use.
"""
from copy import deepcopy
import math

from .pair_contract import require, keys, vector
from .r4_object_association import _fixed
from .r4_observed_map import VERSION as MAP_VERSION
from .r4_query_v2 import validate_controls, validate_domain

VERSION="spatial-history-r4-control-proxy-v1"
PARAMETERS={"timestep_s":.002,"steps":10000,"solver_iterations":10,"restitution":0.,
            "penetration_slop_m":.0001,"baumgarte_fraction":.2,"position_correction_limit_m":.002,
            "maximum_step_displacement_m":.005,"maximum_residual_penetration_m":.005,
            "initial_height_tolerance_m":.002,"contact_force_threshold_n":.000001,
            "initialization":"upright_fixed_spin_planar_backward_mean_proxy",
            "main_uncertainty_certified":False}


def parameters(): return deepcopy(PARAMETERS)


def _clamp(value,low,high): return min(high,max(low,value))


def _circle_box(position,radius,box):
    x,y=position
    closest=[_clamp(x,box[0],box[1]),_clamp(y,box[2],box[3])]
    delta=[x-closest[0],y-closest[1]]; distance=math.hypot(*delta)
    if distance>radius: return None
    if distance>0: return [d/distance for d in delta],radius-distance
    face=min(((x-box[0],[-1.,0.]),(box[1]-x,[1.,0.]),(y-box[2],[0.,-1.]),(box[3]-y,[0.,1.])),key=lambda a:a[0])
    return face[1],radius+face[0]


def _box_box(position,half,box):
    overlaps=[min(position[0]+half[0],box[1])-max(position[0]-half[0],box[0]),
              min(position[1]+half[1],box[3])-max(position[1]-half[1],box[2])]
    if min(overlaps)<0: return None
    # Exit distance, also defined when one rectangle contains the other.
    choices=[(position[0]+half[0]-box[0],[-1.,0.]),(box[1]-position[0]+half[0],[1.,0.]),
             (position[1]+half[1]-box[2],[0.,-1.]),(box[3]-position[1]+half[1],[0.,1.])]
    depth,normal=min(choices,key=lambda x:x[0])
    return normal,depth


def _contacts(positions,rectangles,radius,half,vertical_active=(True,True),pair_active=True):
    result=[]
    for obstacle,box in enumerate(rectangles):
        for body,hit in ((0,_circle_box(positions[0],radius,box)),(1,_box_box(positions[1],half,box))):
            if hit is not None and vertical_active[body]:
                result.append({"body":body,"other":None,"obstacle":obstacle,"normal":hit[0],"penetration":hit[1],"jn":0.,"jt":0.})
    robot=positions[1]
    hit=_circle_box(positions[0],radius,[robot[0]-half[0],robot[0]+half[0],robot[1]-half[1],robot[1]+half[1]])
    if hit is not None and pair_active:
        result.append({"body":0,"other":1,"obstacle":None,"normal":hit[0],"penetration":hit[1],"jn":0.,"jt":0.})
    return result


def _solve(contacts,velocities,masses,mu,dt):
    for _ in range(PARAMETERS["solver_iterations"]):
        for c in contacts:
            body,other=c["body"],c["other"]; n=c["normal"]; t=[-n[1],n[0]]
            inv=1/masses[body]+(0 if other is None else 1/masses[other])
            relative=[velocities[body][a]-(0 if other is None else velocities[other][a]) for a in (0,1)]
            target=PARAMETERS["baumgarte_fraction"]*max(0,c["penetration"]-PARAMETERS["penetration_slop_m"])/dt
            normal=max(0,c["jn"]+(target-sum(v*w for v,w in zip(relative,n)))/inv)
            dn=normal-c["jn"]; c["jn"]=normal
            for a in (0,1):
                velocities[body][a]+=dn*n[a]/masses[body]
                if other is not None: velocities[other][a]-=dn*n[a]/masses[other]
            relative=[velocities[body][a]-(0 if other is None else velocities[other][a]) for a in (0,1)]
            tangent=_clamp(c["jt"]-sum(v*w for v,w in zip(relative,t))/inv,-mu*normal,mu*normal)
            change=tangent-c["jt"]; c["jt"]=tangent
            for a in (0,1):
                velocities[body][a]+=change*t[a]/masses[body]
                if other is not None: velocities[other][a]-=change*t[a]/masses[other]


def _drag(velocity,amount):
    speed=math.hypot(*velocity)
    return [v*max(0,1-amount/speed) for v in velocity] if speed else list(velocity)


def _sweep_known(previous,current,half,known,cell,cache):
    bounds=tuple(math.floor(v/cell) for v in (min(previous[0],current[0])-half[0],max(previous[0],current[0])+half[0],
                 min(previous[1],current[1])-half[1],max(previous[1],current[1])+half[1]))
    if bounds not in cache:
        a,b,c,d=bounds
        cache[bounds]=all((x,y) in known for x in range(a,b+1) for y in range(c,d+1))
    return cache[bounds]


def predict_control(observed_map,controls,public_domain,control_parameters):
    _fixed(control_parameters,PARAMETERS,"control parameters")
    validate_controls(controls); validate_domain(public_domain)
    require(observed_map.get("schema_version")==MAP_VERSION,"observed map version")
    require(not ({"labels","actual_future","world_name","goal"}&set(observed_map)),"private/control input in map")
    object_state=observed_map["current_object"]
    output={"schema_version":VERSION,"kind":"predicted","status":"perception_unresolved","trajectory":None,
            "robot_path":None,"main_prediction":None,"eligible_for_P":False,
            "uncertainty_status":"initial_state_and_geometry_envelope_not_certified",
            "first_unknown_step":None,"unknown_sweep_steps":0,"numerical_failure_step":None,
            "initialization":None,"maximum_step_displacement_m":0.,"maximum_residual_penetration_m":0.}
    if object_state is None or object_state["status"]!="association_ready": return output
    if observed_map["ground"] is None:
        output["status"]="ground_unresolved"; return output
    if abs(object_state["robot_state"]["velocity_mps"][2])>1e-9:
        output["status"]="robot_kinematics_unresolved"; return output
    floor=sum(observed_map["ground"]["height_interval_m"])/2
    d=public_domain; radius=d["object_radius_m"]; half=d["pusher_half_size_m"][:2]
    initial=object_state["position_m"]
    if abs(initial[2]-d["object_half_height_m"]-floor)>PARAMETERS["initial_height_tolerance_m"]:
        output["status"]="initial_height_unresolved"; return output
    positions=[initial[:2],object_state["robot_state"]["position_m"][:2]]
    velocities=[object_state["interval_mean_velocity_mps"][:2],object_state["robot_state"]["velocity_mps"][:2]]
    heights=[floor+d["object_half_height_m"],object_state["robot_state"]["position_m"][2]]
    robot_z=[heights[1]-d["pusher_half_size_m"][2],heights[1]+d["pusher_half_size_m"][2]]
    vertical_active=(True,robot_z[0]<=floor+d["obstacle_height_m"] and robot_z[1]>=floor)
    pair_active=robot_z[0]<=floor+2*d["object_half_height_m"] and robot_z[1]>=floor
    output["initialization"]={"assumption":PARAMETERS["initialization"],"public_object_position_m":list(initial),
        "position_intervals_m":deepcopy(object_state["position_intervals_m"]),
        "backward_mean_velocity_mps":list(object_state["interval_mean_velocity_mps"]),
        "velocity_intervals_mps":deepcopy(object_state["interval_mean_velocity_intervals_mps"]),
        "model_object_height_m":heights[0],"model_vertical_velocity_mps":0.,"model_spin_radps":0.}
    rectangles=observed_map["obstacle_rectangles_xy_m"]
    for box in rectangles:
        vector(box,4,"obstacle rectangle"); require(box[0]<box[1] and box[2]<box[3],"obstacle extent")
    known=(set(map(tuple,observed_map["nominal_free_cells"]))|set(map(tuple,observed_map["occupied_cells"]))) - set(map(tuple,observed_map["unknown_cells"]))
    cell=observed_map["cell_m"]; require(cell==.01,"map cell")
    cache={}; masses=[d["object_mass_kg"],d["pusher_mass_kg"]]
    dt=PARAMETERS["timestep_s"]; mu=d["friction"][0]; gravity=-d["gravity_mps2"][2]
    trajectory=[]; robot_path=[]
    def save(step,force,contacts):
        positive=[c for c in contacts if c["jn"]/dt>PARAMETERS["contact_force_threshold_n"]]
        row={"step_index":step,"time_s":step*dt,"object_position_m":[*positions[0],heights[0]],
             "object_velocity_mps":[*velocities[0],0.],"robot_position_m":[*positions[1],heights[1]],
             "robot_velocity_mps":[*velocities[1],0.],"servo_force_n":list(force),
             "object_obstacle_contact":any(c["body"]==0 and c["obstacle"] is not None for c in positive),
             "robot_obstacle_contact":any(c["body"]==1 and c["obstacle"] is not None for c in positive),
             "object_robot_contact":any(c["other"]==1 for c in positive)}
        trajectory.append(row)
        if step%50==0: robot_path.append({k:deepcopy(row[k]) for k in ("time_s","robot_position_m","robot_velocity_mps")})
    save(0,[0,0],[])
    for step in range(1,PARAMETERS["steps"]+1):
        old=deepcopy(positions)
        command=controls["ee_velocity_mps"][(step-1)//50]
        force=[_clamp(d["velocity_servo_kv"]*(command[a]-velocities[1][a]),-d["force_limit_per_axis_n"],d["force_limit_per_axis_n"]) for a in (0,1)]
        velocities[1]=[v+f/masses[1]*dt for v,f in zip(velocities[1],force)]
        velocities[0]=_drag(velocities[0],mu*gravity*dt)
        if heights[1]-d["pusher_half_size_m"][2]<=floor+PARAMETERS["penetration_slop_m"]:
            velocities[1]=_drag(velocities[1],mu*gravity*dt)
        positions=[[p+v*dt for p,v in zip(pos,vel)] for pos,vel in zip(positions,velocities)]
        movement=max(math.dist(a,b) for a,b in zip(old,positions))
        if (not all(math.isfinite(v) for state in (positions,velocities) for body in state for v in body)
                or not math.isfinite(movement) or movement>PARAMETERS["maximum_step_displacement_m"]):
            output["numerical_failure_step"]=step
            if math.isfinite(movement): output["maximum_step_displacement_m"]=movement
            break
        contacts=_contacts(positions,rectangles,radius,half,vertical_active,pair_active)
        _solve(contacts,velocities,masses,mu,dt)
        for contact in contacts:
            body,other=contact["body"],contact["other"]
            depth=min(PARAMETERS["position_correction_limit_m"],max(0,contact["penetration"]-PARAMETERS["penetration_slop_m"]))
            inv=1/masses[body]+(0 if other is None else 1/masses[other])
            for axis in (0,1):
                correction=depth*contact["normal"][axis]/inv
                positions[body][axis]+=correction/masses[body]
                if other is not None: positions[other][axis]-=correction/masses[other]
        residual=max((c["penetration"] for c in _contacts(positions,rectangles,radius,half,vertical_active,pair_active)),default=0.)
        movement=max(math.dist(a,b) for a,b in zip(old,positions))
        output["maximum_step_displacement_m"]=max(output["maximum_step_displacement_m"],movement)
        output["maximum_residual_penetration_m"]=max(output["maximum_residual_penetration_m"],residual)
        valid=all(_sweep_known(p,q,size,known,cell,cache) for p,q,size in zip(old,positions,([radius,radius],half)))
        if not valid:
            output["unknown_sweep_steps"]+=1
            if output["first_unknown_step"] is None: output["first_unknown_step"]=step
        save(step,force,contacts)
        if (not all(math.isfinite(v) for state in (positions,velocities) for body in state for v in body)
                or movement>PARAMETERS["maximum_step_displacement_m"] or residual>PARAMETERS["maximum_residual_penetration_m"]):
            output["numerical_failure_step"]=step; break
    output["trajectory"]=trajectory; output["robot_path"]=robot_path
    output["status"]="numerical_failure" if output["numerical_failure_step"] else "nominal_complete"
    return output
