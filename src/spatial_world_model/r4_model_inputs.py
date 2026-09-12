"""Public-only numerical adapter inputs; no filesystem, simulator, or labels.

Raw RGB/depth stay in the native 80-pixel row-major form. Framework adapters
perform the final reshape/cast. See D-093 and METHOD for each public scale.
"""
from .r4_query_v2 import model_features


def prepare(query, *, history_mode='full', history_cut_index=None):
    value = model_features(query, history_mode=history_mode, history_cut_index=history_cut_index)
    h, d, goal = value['history'], value['domain_spec'], value['goal']
    domain = [*d['gravity_mps2'], d['object_radius_m'], d['object_half_height_m'],
              d['object_mass_kg'], *d['pusher_half_size_m'], d['pusher_mass_kg'],
              *d['friction'], d['velocity_servo_kv']/100,
              d['control_limit_per_axis_mps']/0.5, d['force_limit_per_axis_n']/20,
              d['obstacle_thickness_m'], d['obstacle_height_m'], d['depth_far_clip_m']/20]
    metadata = [[*position, *[x/0.5 for x in velocity], *camera, *quaternion,
                 *[x/80 for x in intrinsic], time/20, *domain]
                for position, velocity, camera, quaternion, intrinsic, time in zip(
                    h['ee_position_m'],h['ee_velocity_mps'],h['camera_position_m'],
                    h['camera_xyzw'],h['intrinsics'],h['time_s'])]
    history = {'rgb':h['rgb'], 'depth_m':h['depth_m'], 'depth_valid':h['depth_valid'],
               'metadata':metadata,
               'previous_action':[[*[x/0.5 for x in velocity],1.0] for velocity in h['previous_velocity_mps']],
               'reset':[True]+[False]*(len(h['time_s'])-1)}
    controls = [[*[x/0.5 for x in velocity], duration/0.1]
                for velocity,duration in zip(value['controls']['ee_velocity_mps'],value['controls']['duration_s'])]
    target = [*goal['goal_center_xy_m'], *goal['goal_x_bounds_m'],*goal['goal_y_bounds_m'],
              *[x/20 for x in goal['settled_interval_s']],goal['maximum_object_linear_speed_mps']/0.5,
              goal['containment_boundary_tolerance_m'],goal['failure_cost'],goal['success_cost']]
    assert all(len(row)==37 for row in metadata) and len(target)==12
    return {'history':history,'controls':controls,'goal':target}
