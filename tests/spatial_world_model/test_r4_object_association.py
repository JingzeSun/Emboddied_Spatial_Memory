"""Server-only full native artificial depth examples; no rendered/real history.

The disk fixture samples an analytic circle directly, independently of fitting.
See METHOD for the conditional geometry and limits of these checks.
"""
from copy import deepcopy
import math
import unittest
from unittest.mock import patch

from spatial_world_model import r4_object_association as a


FOCAL = 40/math.tan(math.radians(21))


def frame(time=0.0, centers=((0.0,0.0),), top=.08, camera_x=0.0, background_depth=1.4):
    value = {"time_s": time, "width": 80, "height": 80,
             "camera_position_m": [camera_x,-.2,1.4], "camera_xyzw": [1,0,0,0],
             "intrinsics": [FOCAL,FOCAL,39.5,39.5], "ee_position_m": [0,-.4,.05],
             "ee_velocity_mps": [.01,0,0], "depth_m": [background_depth]*6400}
    depth = 1.4-top
    for r in range(80):
        for c in range(80):
            x, y = camera_x + (c-39.5)*depth/FOCAL, -.2-(r-39.5)*depth/FOCAL
            if any((x-cx)**2+(y-cy)**2 <= .07**2 for cx,cy in centers):
                value["depth_m"][r*80+c] = depth
    return value


def history(first=None, last=None):
    return {"schema_version": a.HISTORY_VERSION,
            "frames": [frame(-.1) if first is None else first, frame() if last is None else last]}


def resolve(value=None):
    return a.associate_objects(history() if value is None else value,
                               a.sensor_spec(),a.common_shape_spec(),a.parameters())


def one(value):
    return a.frame_candidates(value,a.sensor_spec(),a.common_shape_spec(),a.parameters(),source_index=120)


class R4ObjectAssociationTests(unittest.TestCase):
    def test_full_native_circle_center_encloses_analytic_center(self):
        result = resolve()
        self.assertEqual(result["status"],"association_ready")
        for interval, truth in zip(result["position_intervals_m"],[0,0,.04]):
            self.assertLessEqual(interval[0],truth)
            self.assertGreaterEqual(interval[1],truth)
        self.assertLess(abs(result["position_m"][0]),.007)
        self.assertLess(abs(result["position_m"][1]),.007)
        self.assertAlmostEqual(result["position_m"][2],.04)

    def test_support_is_native_circle_and_weights_are_uniform(self):
        source = frame()
        result = one(source)
        candidate = result["components"][result["selected_component_index"]]
        expected = [list(divmod(i,80)) for i,d in enumerate(source["depth_m"]) if d != 1.4]
        self.assertEqual(candidate["support_pixels"],expected)
        self.assertEqual(candidate["support_weights"],[1/len(expected)]*len(expected))
        self.assertAlmostEqual(sum(candidate["support_weights"]),1)
        self.assertTrue(candidate["contour_transitions"])
        self.assertTrue(all(p not in expected for p in candidate["outer_ring_pixels"]))

    def test_world_translation_and_negative_coordinates_use_camera(self):
        result = resolve(history(frame(-.1,centers=((-0.05,0),),camera_x=.06),
                                 frame(centers=((-0.05,0),),camera_x=.06)))
        self.assertEqual(result["status"],"association_ready")
        self.assertLessEqual(result["position_intervals_m"][0][0],-.05)
        self.assertGreaterEqual(result["position_intervals_m"][0][1],-.05)

    def test_noncanonical_height_is_observed_not_forced_to_template(self):
        result = resolve(history(frame(-.1,top=.12),frame(top=.12)))
        self.assertEqual(result["status"],"association_ready")
        self.assertAlmostEqual(result["position_m"][2],.08)

    def test_equal_estimates_do_not_observe_stationarity_or_spin(self):
        result = resolve()
        self.assertEqual(result["interval_mean_velocity_mps"],[0,0,0])
        self.assertTrue(all(lo < 0 < hi for lo,hi in result["interval_mean_velocity_intervals_mps"]))
        self.assertFalse(result["instantaneous_velocity_observed"])
        self.assertFalse(result["dynamics_initial_state_ready"])
        self.assertIsNone(result["orientation_xyzw"])
        self.assertIsNone(result["angular_velocity_radps"])
        self.assertEqual(result["robot_state"]["velocity_mps"],[.01,0,0])

    def test_moving_circle_velocity_interval_contains_known_displacement(self):
        result = resolve(history(frame(-.1),frame(centers=((.01,0),))))
        self.assertEqual(result["status"],"association_ready")
        self.assertEqual(result["velocity_kind"],"backward_interval_mean")
        lo,hi = result["interval_mean_velocity_intervals_mps"][0]
        self.assertLessEqual(lo,.1)
        self.assertGreaterEqual(hi,.1)

    def test_registered_decimal_velocity_example_and_actual_dt(self):
        first = {"position_m": [0,0,0], "position_intervals_m": [[-.006,.006]]*3}
        last = {"position_m": [.001,.001,.001], "position_intervals_m": [[-.005,.007]]*3}
        nominal,bounds = a._velocity(first,last,.1)
        self.assertAlmostEqual(nominal[0],.01)
        self.assertAlmostEqual(bounds[0][0],-.11)
        self.assertAlmostEqual(bounds[0][1],.13)
        slower,_ = a._velocity(first,last,.1000000005)
        self.assertLess(slower[0],nominal[0])

    def test_two_complete_circles_are_ambiguous_without_temporal_selection(self):
        value = history(last=frame(centers=((-0.15,0),(.15,0))))
        result = resolve(value)
        self.assertEqual(result["status"],"perception_unresolved")
        self.assertIn("multiple_accepted_candidates",result["frame_results"][1]["reasons"])
        self.assertIsNone(result["position_m"])
        self.assertIsNone(result["interval_mean_velocity_mps"])

    def test_tiny_unexcluded_fragment_blocks_otherwise_unique_circle(self):
        value = frame()
        value["depth_m"][5*80+5] = 1.2
        result = one(value)
        self.assertFalse(result["association_ready"])
        self.assertIn("unexcluded_support",result["reasons"])
        self.assertTrue(any(len(c["support_pixels"]) == 1 and c["classification"] == "unexcluded_component"
                            for c in result["components"]))

    def test_missing_second_estimate_retains_first_only_in_diagnostics(self):
        value = frame()
        value["depth_m"] = [0]*6400
        result = resolve(history(last=value))
        self.assertTrue(result["frame_results"][0]["association_ready"])
        self.assertEqual(result["status"],"perception_unresolved")
        self.assertIsNone(result["position_m"])
        self.assertIsNone(result["interval_mean_velocity_intervals_mps"])

    def test_hole_invalid_clipped_and_higher_occluder_are_not_filled(self):
        for depth in (0, .0401, 19.9999, 1.2, 1.4):
            with self.subTest(depth=depth):
                value = frame()
                value["depth_m"][24*80+39] = depth
                result = one(value)
                self.assertFalse(result["association_ready"])
                self.assertTrue(any("incomplete_outline" in c["reasons"] for c in result["components"]))

    def test_image_boundary_truncation_is_unresolved(self):
        result = one(frame(centers=((-.49,0),)))
        self.assertFalse(result["association_ready"])
        self.assertTrue(any("incomplete_outline" in c["reasons"] for c in result["components"]))

    def test_invalid_outer_ring_pixel_prevents_complete_outline(self):
        value = frame()
        r,c = divmod(next(i for i,d in enumerate(value["depth_m"]) if d != 1.4),80)
        value["depth_m"][(r-1)*80+c] = 0
        result = one(value)
        self.assertFalse(result["association_ready"])
        self.assertTrue(any("incomplete_outline" in c["reasons"] for c in result["components"]))

    def test_native_footprint_center_width_gate_at_different_depths(self):
        # Both disks have six-row/column support, but the farther footprint
        # gives a center range wider than 25 mm. No real floor is assumed.
        for depth,ready in ((2.5,True),(2.7,False)):
            value = frame(centers=((0,-.2+8*depth/FOCAL),),top=1.4-depth,background_depth=3.0)
            result = one(value)
            with self.subTest(depth=depth):
                self.assertEqual(result["association_ready"],ready)
                if not ready:
                    self.assertTrue(any("center_interval_too_wide" in c["reasons"] for c in result["components"]))

    def test_pusher_overlap_and_unprojectable_box_are_unresolved(self):
        value = frame()
        value["ee_position_m"] = [0,0,.05]
        self.assertFalse(one(value)["association_ready"])
        value["ee_position_m"] = [0,0,1.4]
        self.assertEqual(one(value)["reasons"],["pusher_projection_unresolved"])

    def test_projected_mask_includes_pixel_footprint_and_padding(self):
        value = frame()
        # Independent ideal-pinhole bounds for the known axis-aligned box.
        coordinates = [(39.5-(y+.2)*FOCAL/(1.4-z),39.5+x*FOCAL/(1.4-z))
                       for x in (-.15,.15) for y in (-.425,-.375) for z in (.025,.075)]
        rlo,rhi = min(p[0] for p in coordinates),max(p[0] for p in coordinates)
        clo,chi = min(p[1] for p in coordinates),max(p[1] for p in coordinates)
        r0,r1 = max(0,math.ceil(rlo-.5)-1),min(79,math.floor(rhi+.5)+1)
        c0,c1 = max(0,math.ceil(clo-.5)-1),min(79,math.floor(chi+.5)+1)
        expected = {(r,c) for r in range(r0,r1+1) for c in range(c0,c1+1)}
        self.assertEqual(set(map(tuple,one(value)["pusher_mask_pixels"])),expected)

    def test_square_top_rejected_by_radius_without_dropping_corners(self):
        value = frame(centers=())
        for r in range(18,31):
            for c in range(33,46):
                value["depth_m"][r*80+c] = 1.32
        result = one(value)
        self.assertFalse(result["association_ready"])
        self.assertTrue(any("radius_mismatch" in c["reasons"] for c in result["components"]))

    def test_height_groups_do_not_chain_and_diagonal_pixels_do_not_connect(self):
        points = {(0,0): [0,0,0],(0,1): [0,0,.00015],(0,2): [0,0,.0003],(1,3): [0,0,.0003]}
        self.assertEqual(a._components(points),[{(0,0),(0,1)},{(0,2)},{(1,3)}])

    def test_chord_axis_mapping_and_empty_center_intersection(self):
        g = a._Geometry(frame())
        component = {(r,c) for r in (20,21) for c in range(30,40)}
        ix,_ = a._center_interval(g,component,[.08,.08],0)
        iy,_ = a._center_interval(g,component,[.08,.08],1)
        self.assertLess(ix[1],0)
        self.assertGreater(iy[0],0)
        shifted = {(20,c) for c in range(30,40)} | {(21,c) for c in range(40,50)}
        empty,_ = a._center_interval(g,shifted,[.08,.08],0)
        self.assertGreater(empty[0],empty[1])

    def test_private_fields_rejected_at_every_public_boundary(self):
        for key in ("rgb","mask","previous_velocity_mps","goal","world_name","labels"):
            with self.subTest(key=key):
                value = history()
                value["frames"][1][key] = []
                with self.assertRaises(ValueError): resolve(value)
        value = history()
        value["candidates"] = []
        with self.assertRaises(ValueError): resolve(value)

    def test_frozen_parameters_reject_booleans_numeric_changes_and_unknowns(self):
        for key,value in (("min_support_pixels",True),("min_support_pixels",16.0),
                          ("min_support_pixels",15),("hole_filling",0),("hole_filling",True)):
            params = a.parameters()
            params["segmentation"][key] = value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                a.associate_objects(history(),a.sensor_spec(),a.common_shape_spec(),params)
        shape = a.common_shape_spec()
        shape["pusher_orientation"] = "measured_identity"
        with self.assertRaises(ValueError): a.associate_objects(history(),a.sensor_spec(),shape,a.parameters())

    def test_depth_clock_calibration_and_proprioception_validation(self):
        for bad in (-1,True,float("nan"),float("inf")):
            value = history()
            value["frames"][1]["depth_m"][0] = bad
            with self.subTest(depth=bad),self.assertRaises(ValueError): resolve(value)
        for key,value in (("time_s",.1),("width",80.0),("intrinsics",[1,1,39.5,39.5]),
                          ("camera_xyzw",[0,0,0,1]),("ee_velocity_mps",[False,0,0])):
            case = history()
            case["frames"][1][key] = value
            with self.subTest(key=key),self.assertRaises(ValueError): resolve(case)
        with self.assertRaises(ValueError): resolve({"schema_version":a.HISTORY_VERSION,"frames":[frame()]})

    def test_quaternion_sign_equivalence_and_single_frame_causality(self):
        value = frame()
        opposite = deepcopy(value)
        opposite["camera_xyzw"] = [-1,0,0,0]
        self.assertEqual(one(value),one(opposite))
        past = deepcopy(value)
        past["time_s"] = -1
        self.assertEqual(a.frame_candidates(past,a.sensor_spec(),a.common_shape_spec(),a.parameters(),source_index=110)["components"],
                         one(value)["components"])
        with self.assertRaises(ValueError):
            a.frame_candidates(past,a.sensor_spec(),a.common_shape_spec(),a.parameters(),source_index=120)

    def test_no_files_and_no_input_or_output_aliasing(self):
        source = history()
        before = deepcopy(source)
        with patch("builtins.open",side_effect=AssertionError("no files")):
            result = resolve(source)
        self.assertEqual(source,before)
        result["robot_state"]["position_m"][0] = 99
        result["position_m"][0] = 99
        self.assertNotEqual(result["frame_results"][1]["position_m"][0],99)
        self.assertEqual(source,before)
        altered = a.parameters()
        altered["segmentation"]["min_support_pixels"] = 99
        self.assertEqual(a.parameters()["segmentation"]["min_support_pixels"],16)
