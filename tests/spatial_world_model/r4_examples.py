"""Hand-authored R4 values for server checks only; no rendered/physical claims."""
from copy import deepcopy


def goal():
    return {
        "goal_center_xy_m": [0, 2.65], "goal_x_bounds_m": [-0.25, 0.25], "goal_y_bounds_m": [2.45, 2.85],
        "require_ordered_actual_gate_passage": True,
        "gate_attempt_rule": "forward center-plane crossing starts attempt; center retreat below plane cancels; rear clearance completes same active attempt",
        "goal_containment": "entire actual cylinder horizontal projection",
        "settled_interval_s": [19, 20], "maximum_object_linear_speed_mps": 0.02,
        "containment_boundary_tolerance_m": 0.001, "collision_is_task_failure": False,
        "failure_cost": 1, "success_cost": 0,
    }


def public(indices=(119, 120)):
    frames = []
    for i in indices:
        frames.append({"time_s": 0.5 + i / 10, "width": 64, "height": 64,
                       "rgb": [0] * 12288, "depth_m": [1.4] * 4095 + [0.0],
                       "camera_position_m": [0, -0.1, 1.4], "camera_xyzw": [1, 0, 0, 0],
                       "intrinsics": [100, 100, 31.5, 31.5],
                       "ee_position_m": [0, -0.25, 0.05], "ee_velocity_mps": [0, 0, 0],
                       "previous_velocity_mps": [0, 0, 0]})
    return {"history": frames,
            "controls": [{"duration_s": 0.1, "ee_velocity_mps": [0, 0.2, 0]} for _ in range(200)],
            "goal": goal()}


def prediction(success=0.5, position=(0, 0, 0), contact=0.0):
    return {"prediction_times_s": [k / 10 for k in range(1, 201)],
            "object_position_m": [list(position) for _ in range(200)],
            "obstacle_contact_probability": [contact] * 200, "task_success_probability": success}


def truth(success=True, position=(0, 0, 0)):
    return {"prediction_times_s": [k / 10 for k in range(1, 201)],
            "object_position_m": [list(position) for _ in range(200)],
            "interval_contact": [False] * 200, "task_success": success,
            "physics_valid": True, "visibility_valid": True, "object_visible_pixels": [0] * 200}


def trace():
    return [{"step_index": i, "time_s": i * 0.002,
             "object_position_m": [i * 0.0001, 0, 0.04], "object_axis_world": [0, 0, 1],
             "object_linear_velocity_mps": [0.05, 0, 0], "pusher_position_m": [0, -0.25, 0.05],
             "actuator_force_n": [0, 0], "contacts": [], "object_visible_pixels": 0 if i % 50 == 0 else None}
            for i in range(10001)]


def registry_rows():
    registry = {"families": ["synthetic-a", "synthetic-b"], "model_seeds": {"D": [17, 29, 43], "F": [17, 29, 43]}}
    rows = []
    for family in registry["families"]:
        for model, seeds in registry["model_seeds"].items():
            for seed in seeds:
                for world in ("LL", "LR", "RL", "RR"):
                    labels = [truth(True), truth(False), truth(False), truth(False)]
                    predictions = [prediction(0.0), prediction(0.0), prediction(0.0), prediction(0.0)]
                    predictions[1 if model == "D" else 0]["task_success_probability"] = 1.0
                    rows.append({"family_id": family, "model_id": model, "seed": seed,
                                 "world_id": world, "predictions": predictions, "labels": labels})
    return rows, registry


def examples():
    # Example of exact ties: one real successful action => expected failure 3/4.
    from spatial_world_model.r4_query import from_public_query
    from spatial_world_model.r4_scoring import score_world
    query = from_public_query(public(), history_mode="recent")
    predictions = [prediction() for _ in range(4)]
    labels = [truth(True), truth(False), truth(False), truth(False)]
    missing = deepcopy(predictions)
    missing[2] = None
    return {"kind": "synthetic_contract_examples_not_model_results", "query": query,
            "predictions": predictions, "labels": labels,
            "tie_score": score_world(predictions, labels), "missing_score": score_world(missing, labels),
            "new_simulation_steps": 0, "new_training_steps": 0, "new_weight_download_bytes": 0}
