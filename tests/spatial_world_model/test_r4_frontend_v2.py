"""D-090 server-only analytic counterexamples, separate from the 16 histories."""
from copy import deepcopy
import math
import unittest

from test_r4_object_association import frame, history
from test_r4_map_control import scene, controls
from spatial_world_model import r4_object_association as old
from spatial_world_model import r4_object_surfaces as surfaces
from spatial_world_model import r4_observed_map_v2 as maps
from spatial_world_model import r4_control_bridge_v2 as bridge
from spatial_world_model import r4_control_proxy as solver
from spatial_world_model.r4_query_v2 import domain_spec


def cylinder(time=0):
    """Independent ray/cylinder intersections, not the ownership algorithm."""
    f=frame(time)
    fx,fy,cx,cy=f["intrinsics"]
    for row in range(80):
        for col in range(80):
            dx=(col-cx)/fx; dy=-(row-cy)/fy
            hits=[1.4]
            top=1.32
            if (dx*top)**2+(-.2+dy*top)**2<=.07**2:
                hits.append(top)
            a=dx*dx+dy*dy; b=-.4*dy; c=.2**2-.07**2
            discr=b*b-4*a*c
            if a and discr>=0:
                for t in ((-b-math.sqrt(discr))/(2*a),(-b+math.sqrt(discr))/(2*a)):
                    if t>0 and 0<=1.4-t<=.08:
                        hits.append(t)
            f["depth_m"][row*80+col]=min(hits)
    return f


def one(f):
    return surfaces.frame_candidates(f,old.sensor_spec(),old.common_shape_spec(),surfaces.parameters(),source_index=120)


def build(frames):
    return maps.build_map({"schema_version":maps.HISTORY_VERSION,"frames":frames},
                          old.sensor_spec(),old.common_shape_spec(),maps.parameters(),history_mode="recent")


class SurfaceTests(unittest.TestCase):
    def test_analytic_cylinder_sides_remain_recorded_and_resolve(self):
        f=cylinder(); result=one(f)
        legacy=old.frame_candidates(f,old.sensor_spec(),old.common_shape_spec(),old.parameters(),source_index=120)
        self.assertFalse(legacy["association_ready"])
        self.assertTrue(result["association_ready"])
        attached=[c for c in result["components"] if c["classification"]=="attached_side_support"]
        self.assertTrue(attached)
        self.assertEqual(sum(len(c["support_pixels"]) for c in result["components"]),
                         sum(len(c["support_pixels"]) for c in legacy["components"]))
        self.assertTrue(all(c["reasons"] and c["ownership"]["identity_certified"] is False for c in attached))

    def test_plain_top_geometry_does_not_change(self):
        f=frame(); before=old.frame_candidates(f,old.sensor_spec(),old.common_shape_spec(),old.parameters(),source_index=120)
        after=one(f)
        self.assertEqual(before["position_m"],after["position_m"])
        self.assertEqual(before["position_intervals_m"],after["position_intervals_m"])

    def test_diagonal_closed_form_matches_original_corner_geometry(self):
        f=frame(); points={(0,0),(79,79),(-1,80),(31,18)}
        for heights in ((-.0001,.0001),(.0799,.0801),(.2999,.3001)):
            self.assertAlmostEqual(surfaces.Geometry(f).diagonal(points,heights),old._Geometry(f).diagonal(points,heights),places=12)

    def test_distant_tiny_fragment_still_blocks(self):
        f=cylinder(); f["depth_m"][5*80+5]=1.2
        result=one(f)
        self.assertFalse(result["association_ready"])
        self.assertIn("unexcluded_support",result["reasons"])

    def test_below_cylinder_fragment_is_not_attached(self):
        f=cylinder(); a=one(f)
        pixel=next(c["support_pixels"][0] for c in a["components"] if c["classification"]=="attached_side_support")
        f["depth_m"][pixel[0]*80+pixel[1]]=1.5
        a=one(f)
        self.assertFalse(a["association_ready"])

    def test_multiple_tops_not_ranked(self):
        self.assertIn("multiple_accepted_candidates",one(frame(centers=((-0.15,0),(.15,0))))["reasons"])

    def test_attachment_requires_four_neighbor_not_diagonal_only(self):
        candidate={"support_pixels":[[1,1]],"outer_ring_pixels":[[2,2]],
                   "position_intervals_m":[[-.001,.001],[-.001,.001]],
                   "top_height_interval_m":[.0799,.0801],"radial_tolerance_m":.02,"component_index":0}
        fragment={"support_pixels":[[2,2]],"radial_tolerance_m":.02}
        self.assertIsNone(surfaces._ownership(fragment,candidate,{(2,2):[.07,0,.04]}))

    def test_radial_interior_is_not_side(self):
        candidate={"support_pixels":[[1,1]],"outer_ring_pixels":[[1,2]],
                   "position_intervals_m":[[-.001,.001],[-.001,.001]],
                   "top_height_interval_m":[.0799,.0801],"radial_tolerance_m":.02,"component_index":0}
        fragment={"support_pixels":[[1,2]],"radial_tolerance_m":.02}
        self.assertIsNone(surfaces._ownership(fragment,candidate,{(1,2):[0,0,.04]}))

    def test_input_and_unobserved_state_boundaries(self):
        f=cylinder(); before=deepcopy(f); one(f); self.assertEqual(f,before)
        h=history(cylinder(-.1),cylinder())
        result=surfaces.associate_objects(h,old.sensor_spec(),old.common_shape_spec(),surfaces.parameters())
        self.assertEqual(result["status"],"association_ready")
        self.assertFalse(result["dynamics_initial_state_ready"])
        self.assertFalse(result["instantaneous_velocity_observed"])
        self.assertIsNone(result["angular_velocity_radps"])
        f["rgb"]=[]
        with self.assertRaises(ValueError):one(f)

    def test_parameters_and_future_clock_cannot_be_changed(self):
        p=surfaces.parameters(); p["certificate"]=True
        with self.assertRaises(ValueError):surfaces.frame_candidates(frame(),old.sensor_spec(),old.common_shape_spec(),p,source_index=120)
        with self.assertRaises(ValueError):one(frame(.1))


class MapTests(unittest.TestCase):
    def short_wall(self,height):
        frames=[cylinder(-.1),cylinder()]
        for f in frames:
            for r in range(8,13):
                for c in range(9):f["depth_m"][r*80+c]=1.4-height
        return frames

    def test_short_observed_wall_retained_without_larger_size(self):
        result=build(self.short_wall(.3))
        self.assertTrue(result["occupied_cells"])
        self.assertTrue(all(f["wall_height_resolved_components"] for f in result["frame_audit"]))
        self.assertTrue(any(c["role"]=="wall_top_proxy" for c in result["surface_cells"]))
        self.assertFalse(result["certified_free_volume"])

    def test_other_height_not_silently_made_wall_or_free(self):
        result=build(self.short_wall(.2))
        self.assertFalse(result["occupied_cells"])
        self.assertTrue(result["unknown_cells"])
        self.assertFalse(set(map(tuple,result["unknown_cells"])) & set(map(tuple,result["nominal_free_cells"])))

    def test_dynamic_top_and_side_never_static_surface(self):
        result=build([cylinder(-.1),cylinder()])
        self.assertEqual(result["current_object"]["status"],"association_ready")
        self.assertTrue(all(f["attached_side_components"] for f in result["frame_audit"]))
        self.assertTrue(all(c["role"]=="floor_proxy" for c in result["surface_cells"]))

    def test_no_ground_witness_no_height_shortcut(self):
        frames=self.short_wall(.3)
        for f in frames:
            f["depth_m"]=[0 if d==1.4 else d for d in f["depth_m"]]
        result=build(frames)
        self.assertIsNone(result["ground"])
        self.assertFalse(result["occupied_cells"])

    def test_map_no_mutation_or_private_fields(self):
        frames=self.short_wall(.3); original=deepcopy(frames)
        build(frames); self.assertEqual(frames,original)
        frames[0]["labels"]={}
        with self.assertRaises(ValueError):build(frames)

    def test_bridge_preserves_solver_and_input(self):
        value=scene(); expected=solver.predict_control(value,controls(),domain_spec(),solver.parameters())
        value["schema_version"]=maps.VERSION; original=deepcopy(value)
        actual=bridge.predict_control(value,controls(),domain_spec(),solver.parameters())
        self.assertEqual(actual["trajectory"],expected["trajectory"])
        self.assertEqual(actual["robot_path"],expected["robot_path"])
        self.assertEqual(value,original)
        self.assertIsNone(actual["main_prediction"])
        self.assertFalse(actual["eligible_for_P"])
        with self.assertRaises(ValueError):bridge.predict_control(scene(),controls(),domain_spec(),solver.parameters())
