"""Server-only map/control/readout and post-seal audit artificial checks."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from test_r4_object_association import frame
from r4_examples_v2 import goal,truth,trace
from spatial_world_model import r4_observed_map as m, r4_control_proxy as d, r4_proxy_readout as r, r4_proxy_audit as e
from spatial_world_model import r4_object_association as b
from spatial_world_model.r4_query_v2 import domain_spec


def map_history(frames=None):
    return {"schema_version":m.HISTORY_VERSION,"frames":frames if frames is not None else [frame(-.1),frame()]}


def build(value=None,**kwargs):
    return m.build_map(map_history() if value is None else value,b.sensor_spec(),b.common_shape_spec(),m.parameters(),history_mode=kwargs.pop("history_mode","recent"),**kwargs)


def controls(x=0,y=0): return {"ee_velocity_mps":[[x,y,0] for _ in range(200)],"duration_s":[.1]*200}


def scene():
    # Hand-authored complete ground, not a claim of public reconstruction.
    return {"schema_version":m.VERSION,"cell_m":.01,"ground":{"height_interval_m":[0,0]},
            "obstacle_rectangles_xy_m":[],"nominal_free_cells":[[x,y] for x in range(-70,71) for y in range(-70,351)],
            "occupied_cells":[],"unknown_cells":[],
            "current_object":{"status":"association_ready","position_m":[0,0,.04],"position_intervals_m":[[-.001,.001],[-.001,.001],[.0399,.0401]],
               "interval_mean_velocity_mps":[0,0,0],"interval_mean_velocity_intervals_mps":[[-.02,.02]]*3,
               "robot_state":{"position_m":[0,-.25,.05],"velocity_mps":[0,0,0]}}}


class MapTests(unittest.TestCase):
    def test_recent_map_observes_ground_and_excludes_dynamic_top(self):
        result=build()
        self.assertEqual(result["status"],"nominal_map_ready")
        self.assertAlmostEqual(sum(result["ground"]["height_interval_m"])/2,0)
        self.assertTrue(result["nominal_free_cells"])
        self.assertFalse(result["occupied_cells"])
        self.assertFalse(result["certified_free_volume"])
        self.assertEqual(result["current_object"]["status"],"association_ready")

    def test_no_depth_does_not_invent_ground_or_free_space(self):
        frames=[frame(-.1),frame()]
        for f in frames: f["depth_m"]=[0]*6400
        value=build(map_history(frames))
        self.assertEqual(value["status"],"ground_unresolved")
        self.assertEqual(value["nominal_free_cells"],[])

    def test_observed_wall_height_uses_common_height_not_color_or_template(self):
        frames=[frame(-.1),frame()]
        for f in frames:
            for row in range(8,14):
                for col in range(0,29): f["depth_m"][row*80+col]=1.1
        value=build(map_history(frames))
        self.assertTrue(value["occupied_cells"])
        self.assertTrue(value["obstacle_rectangles_xy_m"])
        self.assertTrue(any(c["role"]=="wall_top_proxy" for c in value["surface_cells"]))

    def test_prefix_cannot_accept_future_frames_or_decision_association(self):
        first=frame(-12)
        value=build(map_history([first]),history_mode="prefix",history_cut_index=0)
        self.assertIsNone(value["current_object"])
        self.assertEqual([x["source_index"] for x in value["frame_audit"]],[0])
        with self.assertRaises(ValueError): build(map_history([first,frame(-11.9)]),history_mode="prefix",history_cut_index=0)

    def test_negative_grid_floor_and_exact_rectangle_merge(self):
        self.assertEqual(m._cell([-.001,-.011,0]),(-1,-2))
        self.assertEqual(m._rectangles({(0,0),(1,0),(0,1),(1,1)}),[[0,.02,0,.02]])
        self.assertEqual(len(m._rectangles({(0,0),(1,1)})),2)

    def test_map_private_fields_and_parameter_changes_rejected_without_io(self):
        value=map_history(); value["labels"]={}
        with self.assertRaises(ValueError): build(value)
        p=m.parameters(); p["cell_m"]=.02
        with self.assertRaises(ValueError): m.build_map(map_history(),b.sensor_spec(),b.common_shape_spec(),p,history_mode="recent")
        source=map_history(); original=deepcopy(source)
        with patch("builtins.open",side_effect=AssertionError("no files")): build(source)
        self.assertEqual(source,original)


class ControlTests(unittest.TestCase):
    def test_zero_control_full_trajectory_and_no_formal_readiness_claim(self):
        result=d.predict_control(scene(),controls(),domain_spec(),d.parameters())
        self.assertEqual(result["status"],"nominal_complete")
        self.assertEqual(len(result["trajectory"]),10001)
        self.assertEqual(len(result["robot_path"]),201)
        self.assertEqual(result["trajectory"][-1]["object_position_m"],[0,0,.04])
        self.assertIsNone(result["main_prediction"])
        self.assertFalse(result["eligible_for_P"])

    def test_finite_force_first_step_is_not_command_integration(self):
        value=d.predict_control(scene(),controls(x=.5),domain_spec(),d.parameters())
        first=value["trajectory"][1]
        self.assertEqual(first["servo_force_n"],[20,0])
        self.assertAlmostEqual(first["robot_velocity_mps"][0],.08)
        self.assertAlmostEqual(first["robot_position_m"][0],.00016)

    def test_dynamic_contact_impulse_conserves_linear_momentum(self):
        velocities=[[0.,0.],[0.,1.]]
        contacts=[{"body":0,"other":1,"normal":[0,1],"penetration":0.,"jn":0.,"jt":0.}]
        d._solve(contacts,velocities,[.15,.5],.25,.002)
        self.assertAlmostEqual(.15*velocities[0][1]+.5*velocities[1][1],.5)
        self.assertAlmostEqual(velocities[0][1],velocities[1][1])
        self.assertGreater(contacts[0]["jn"],0)

    def test_box_and_circle_inside_cases_have_defined_outward_normals(self):
        n,depth=d._circle_box([0,0],.07,[-.1,.1,-.1,.1])
        self.assertEqual(n,[-1.,0.]); self.assertAlmostEqual(depth,.17)
        n,depth=d._box_box([0,0],[.02,.02],[-.1,.1,-.1,.1])
        self.assertEqual(n,[-1.,0.]); self.assertAlmostEqual(depth,.12)
        self.assertIsNone(d._circle_box([1,1],.07,[-.1,.1,-.1,.1]))

    def test_coulomb_drag_never_reverses_velocity(self):
        self.assertEqual(d._drag([.001,0],.01),[0,0])
        for actual, expected in zip(d._drag([3,4],1),[2.4,3.2]):
            self.assertAlmostEqual(actual, expected)

    def test_swept_body_detects_unknown_between_endpoints(self):
        known={(x,y) for x in range(-2,13) for y in range(-2,3)}-{(5,0)}
        self.assertFalse(d._sweep_known([0,0],[.1,0],[.001,.001],known,.01,{}))

    def test_unresolved_state_and_huge_velocity_preserve_explicit_failure(self):
        value=scene(); value["current_object"]["status"]="perception_unresolved"
        self.assertIsNone(d.predict_control(value,controls(),domain_spec(),d.parameters())["trajectory"])
        value=scene(); value["current_object"]["robot_state"]["velocity_mps"]=[1e100,0,0]
        result=d.predict_control(value,controls(),domain_spec(),d.parameters())
        self.assertEqual(result["status"],"numerical_failure")
        self.assertEqual(result["numerical_failure_step"],1)

    def test_candidates_clone_public_initial_state_and_robot_path_hides_object(self):
        source=scene(); before=deepcopy(source)
        first=d.predict_control(source,controls(x=.1),domain_spec(),d.parameters())
        second=d.predict_control(source,controls(),domain_spec(),d.parameters())
        self.assertEqual(source,before)
        self.assertEqual(second["trajectory"][0]["robot_position_m"],[0,-.25,.05])
        self.assertTrue(all(set(row)=={"time_s","robot_position_m","robot_velocity_mps"} for row in first["robot_path"]))


class ReadoutAuditTests(unittest.TestCase):
    def test_object_audit_separates_geometric_estimate_from_unobserved_state(self):
        state=scene()["current_object"]
        actual={"object_position_m":[0,0,.04],"object_linear_velocity_mps":[.1,0,0]}
        result=e.compare_object(state,actual)
        self.assertEqual(result["position_error_m"],0)
        self.assertEqual(result["position_interval_contains_actual"],[True,True,True])
        self.assertEqual(result["backward_mean_as_initial_velocity_error_mps"],.1)
        self.assertFalse(result["instantaneous_velocity_observed"])
        state["status"]="perception_unresolved"
        self.assertIsNone(e.compare_object(state,actual)["position_error_m"])

    def test_openings_require_observed_through_support_and_not_private_gate_ids(self):
        value=scene()
        value["obstacle_rectangles_xy_m"]=[[-.6,-.2,.6,.65],[.2,.6,.6,.65],[-.6,-.2,2.2,2.25],[.2,.6,2.2,2.25]]
        self.assertEqual(len(r.public_openings(value)),2)
        value["nominal_free_cells"]=[]
        self.assertEqual(r.public_openings(value),[])

    def test_readout_unknown_openings_does_not_invalidate_robot_path(self):
        value=scene(); proxy=d.predict_control(value,controls(),domain_spec(),d.parameters())
        result=r.readout(value,proxy,goal(),r.parameters())
        self.assertEqual(result["status"],"task_readout_unresolved")
        self.assertIsNone(result["nominal_success"])
        self.assertEqual(len(proxy["robot_path"]),201)

    def test_map_evaluator_reports_false_free_without_repairing_map(self):
        value={"cell_m":.01,"occupied_cells":[[0,0],[2,2]],"nominal_free_cells":[[1,1]],"ground":{"height_interval_m":[0,0]}}
        before=deepcopy(value); result=e.compare_map(value,[[0,.02,0,.02]],0)
        self.assertEqual(result["occupied_cell_precision"],.5)
        self.assertEqual(result["false_free_cells"],1)
        self.assertEqual(value,before)

    def test_diagnostic_selection_keeps_missing_denominator_and_exact_ties(self):
        branches=[{"nominal_success":True,"actual_success":i==0} for i in range(9)]
        self.assertEqual(e.nominal_selection(branches)["nominal_expected_failure_cost"],8/9)
        branches[0]["nominal_success"]=None
        self.assertIsNone(e.nominal_selection(branches)["nominal_expected_failure_cost"])

    def test_complete_actual_trace_required_for_post_seal_comparison(self):
        with self.assertRaises(ValueError): e.compare_branch({}, {}, trace()[:1],truth())

    def test_joint_public_map_to_control_pipeline_keeps_unknown_flag(self):
        value=build(); proxy=d.predict_control(value,controls(),domain_spec(),d.parameters())
        self.assertEqual(proxy["status"],"nominal_complete")
        self.assertFalse(proxy["eligible_for_P"])
        self.assertEqual(len(value["frame_audit"]),2)

    def test_public_ordered_passage_and_settlement_allow_contact(self):
        value=scene(); value["obstacle_rectangles_xy_m"]=[[-.6,-.2,.6,.65],[.2,.6,.6,.65],[-.6,-.2,2.2,2.25],[.2,.6,2.2,2.25]]
        samples=[{"step_index":i,"time_s":i*.002,"object_position_m":[0,min(2.65,i*.002*.265),.04],
                  "object_velocity_mps":[0,.265 if i<5000 else 0,0],"object_obstacle_contact":True} for i in range(10001)]
        result=r.readout(value,{"status":"nominal_complete","trajectory":samples},goal(),r.parameters())
        self.assertTrue(result["nominal_success"])
        self.assertEqual([v["status"] for v in result["events"]],["completed","completed"])
        self.assertIsNone(result["formal_prediction"])

    def test_independent_error_and_contact_metrics_match_identical_arrays(self):
        actual=trace()
        samples=[{"step_index":v["step_index"],"time_s":v["time_s"],"object_position_m":v["object_position_m"],
                  "robot_position_m":v["pusher_position_m"],"object_obstacle_contact":v["step_index"]==50} for v in actual]
        labels=truth(); labels["interval_contact"][0]=True
        proxy={"status":"nominal_complete","trajectory":samples,"first_unknown_step":None,"unknown_sweep_steps":0,
               "numerical_failure_step":None,"initialization":{"backward_mean_velocity_mps":[.05,0,0]}}
        result=e.compare_branch(proxy,{"status":"nominal_readout_complete","nominal_success":True},actual,labels)
        self.assertEqual(result["compared_future_steps"],200)
        self.assertEqual(result["object_position_mean_error_m"],0)
        self.assertEqual(result["contact_brier"],0)
        self.assertEqual(result["contact_positive_recall"],1)
        self.assertIsNone(result["robot_instantaneous_velocity_error_mps"])
