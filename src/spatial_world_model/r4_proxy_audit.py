"""Independent post-seal engineering metrics. No predictor imports or repairs."""
import math
from .pair_contract import require, vector
from .r4_scoring_v2 import validate_labels


def _mean(values): return math.fsum(values)/len(values) if values else None


def compare_object(association, actual_initial):
    """Current geometric estimate versus sealed evaluation-only initial truth."""
    out={"status":association["status"],"position_error_m":None,"position_interval_contains_actual":None,
         "backward_mean_as_initial_velocity_error_mps":None,"instantaneous_velocity_observed":False,
         "orientation_error_rad":None,"spin_error_radps":None}
    if association["status"]=="association_ready":
        position=actual_initial["object_position_m"]; velocity=actual_initial["object_linear_velocity_mps"]
        vector(position,3,"actual initial position"); vector(velocity,3,"actual initial velocity")
        out.update(position_error_m=math.dist(association["position_m"],position),
                   position_interval_contains_actual=[lo<=v<=hi for (lo,hi),v in zip(association["position_intervals_m"],position)],
                   backward_mean_as_initial_velocity_error_mps=math.dist(association["interval_mean_velocity_mps"],velocity))
    return out


def compare_branch(proxy,task,actual,labels):
    validate_labels(labels)
    require(len(actual)==10001,"complete original actual trajectory required")
    for i,row in enumerate(actual):
        require(row["step_index"]==i and math.isclose(row["time_s"],i*.002,rel_tol=0,abs_tol=1e-8),"actual clock")
        for key in ("object_position_m","pusher_position_m","object_linear_velocity_mps"): vector(row[key],3,key)
    samples=proxy["trajectory"]
    out={"proxy_status":proxy["status"],"readout_status":task["status"],"actual_success":labels["task_success"],
         "nominal_success":task["nominal_success"],"formal_prediction_available":False,
         "first_unknown_step":proxy["first_unknown_step"],"unknown_sweep_steps":proxy["unknown_sweep_steps"],
         "numerical_failure_step":proxy["numerical_failure_step"],"compared_future_steps":0,
         "object_position_error_m":None,"robot_position_error_m":None,"robot_interval_mean_velocity_error_mps":None,
         "initial_position_proxy_error_m":None,"initial_velocity_proxy_error_mps":None,
         "robot_instantaneous_velocity_error_mps":None,"robot_instantaneous_velocity_reference":"not_present_in_original_trajectory",
         "contact_brier":None,"contact_positive_recall":None,"contact_negative_false_positive_rate":None}
    if samples:
        future=[i for i in range(50,min(len(samples),10001),50)]
        obj=[math.dist(samples[i]["object_position_m"],actual[i]["object_position_m"]) for i in future]
        robot=[math.dist(samples[i]["robot_position_m"],actual[i]["pusher_position_m"]) for i in future]
        velocity=[math.dist([(samples[i]["robot_position_m"][a]-samples[i-50]["robot_position_m"][a])/.1 for a in range(3)],
                            [(actual[i]["pusher_position_m"][a]-actual[i-50]["pusher_position_m"][a])/.1 for a in range(3)]) for i in future]
        out.update(compared_future_steps=len(future),object_position_error_m=obj,robot_position_error_m=robot,
                   robot_interval_mean_velocity_error_mps=velocity,object_position_mean_error_m=_mean(obj),robot_position_mean_error_m=_mean(robot),
                   initial_position_proxy_error_m=math.dist(samples[0]["object_position_m"],actual[0]["object_position_m"]),
                   initial_velocity_proxy_error_mps=math.dist(proxy["initialization"]["backward_mean_velocity_mps"],actual[0]["object_linear_velocity_mps"]))
    if samples is not None and len(samples)==10001:
        predicted=[any(s["object_obstacle_contact"] for s in samples[i*50+1:(i+1)*50+1]) for i in range(200)]
        target=labels["interval_contact"]
        positives=sum(target); negatives=200-positives
        out.update(contact_brier=_mean([(int(p)-int(t))**2 for p,t in zip(predicted,target)]),
                   contact_positive_recall=sum(p and t for p,t in zip(predicted,target))/positives if positives else None,
                   contact_negative_false_positive_rate=sum(p and not t for p,t in zip(predicted,target))/negatives if negatives else None,
                   nominal_contact_intervals=predicted,actual_contact_intervals=list(target))
    return out


def compare_map(observed_map,static_boxes,floor_height):
    """Evaluation-only boxes come from original XML after the public seal."""
    cell=observed_map["cell_m"]
    for box in static_boxes: vector(box,4,"actual static box")
    def inside(key):
        x,y=((v+.5)*cell for v in key)
        return any(b[0]<=x<=b[1] and b[2]<=y<=b[3] for b in static_boxes)
    occupied=observed_map["occupied_cells"]; free=observed_map["nominal_free_cells"]
    true_cells=set()
    for x0,x1,y0,y1 in static_boxes:
        for x in range(math.ceil(x0/cell-.5),math.floor(x1/cell-.5)+1):
            for y in range(math.ceil(y0/cell-.5),math.floor(y1/cell-.5)+1): true_cells.add((x,y))
    hits=sum(inside(c) for c in occupied); false_free=sum(inside(c) for c in free)
    ground=observed_map["ground"]
    return {"nominal_occupied_cells":len(occupied),"nominal_free_cells":len(free),"true_wall_cells_full_world":len(true_cells),
            "occupied_cell_precision":hits/len(occupied) if occupied else None,
            "full_world_wall_cell_recall":len(set(map(tuple,occupied))&true_cells)/len(true_cells) if true_cells else None,
            "false_free_cells":false_free,"false_free_fraction":false_free/len(free) if free else None,
            "ground_midpoint_error_m":abs(sum(ground["height_interval_m"])/2-floor_height) if ground else None,
            "certified_free_volume":False}


def nominal_selection(branches):
    require(len(branches)==9,"nine registered branches required")
    if any(b["nominal_success"] is None or b["actual_success"] is None for b in branches):
        return {"status":"incomplete","nominal_expected_failure_cost":None,"formal_selection_regret":None}
    maximum=max(b["nominal_success"] for b in branches)
    chosen=[i for i,b in enumerate(branches) if b["nominal_success"]==maximum]
    return {"status":"diagnostic_only","chosen_slots":chosen,
            "nominal_expected_failure_cost":sum(not branches[i]["actual_success"] for i in chosen)/len(chosen),
            "actual_best_failure_cost":int(not any(b["actual_success"] for b in branches)),"formal_selection_regret":None}
