import math
import unittest

from shapely.geometry import Point

from spatial_world_model.r4_continuous_shapes import (
    _box_sweep,
    _inner_circle,
    _outer_circle_radius,
    _outer_circle_sweep,
    assumption_free_geometry,
    audit_trajectory,
)


Q = 32
DOMAIN = {"object_radius_m": .07, "pusher_half_size_m": [.15, .025, .025]}


def map_value(floor, wall=()):
    return {
        "geometry_parameters": {
            "circle_quadrant_segments": Q,
            "circle_outer_radius_scale": 1 / math.cos(math.pi / (4 * Q)),
            "numeric_guard_m": .000001,
        },
        "observed_floor_support_rectangles_xy_m": list(floor),
        "observed_wall_interval_rectangles_xy_m": list(wall),
        "current_object": None,
    }


class ContinuousShapeTests(unittest.TestCase):
    def test_inner_and_outer_circle_approximation_directions(self):
        inner = _inner_circle((0., 0.), .07, Q)
        outer = _outer_circle_sweep((0., 0.), (0., 0.), .07, Q, .000001)
        self.assertTrue(outer.covers(Point(0., 0.).buffer(.07, quad_segs=256)))
        self.assertTrue(all(math.hypot(x, y) <= .07 + 1e-15
                            for x, y in inner.exterior.coords))
        self.assertGreater(_outer_circle_radius(.07, Q), .07)

    def test_translated_box_sweep_is_not_its_axis_aligned_bounding_box(self):
        sweep = _box_sweep((0., 0.), (.1, .1), (.01, .01))
        self.assertTrue(sweep.covers(Point(.05, .05)))
        self.assertFalse(sweep.covers(Point(0., .1)))

    def test_wall_interval_is_removed_from_conditioned_free_geometry(self):
        value = map_value([[-1., 1., -1., 1.]], [[-.01, .01, -.5, .5]])
        free = assumption_free_geometry(value, DOMAIN)
        self.assertTrue(free.covers(Point(.5, 0.)))
        self.assertFalse(free.covers(Point(0., 0.)))

    def test_complete_sweep_passes_and_boundary_gap_fails(self):
        trajectory = [
            {"object_position_m": [0., 0., .04], "robot_position_m": [0., -.3, .05]},
            {"object_position_m": [.01, 0., .04], "robot_position_m": [.01, -.3, .05]},
        ]
        complete = map_value([[-.3, .3, -.5, .2]])
        self.assertTrue(audit_trajectory(complete, trajectory, DOMAIN)["complete_sweep_contained"])
        gap = map_value([[-.3, .3, -.5, -.01], [-.3, .3, .01, .2]])
        result = audit_trajectory(gap, trajectory, DOMAIN)
        self.assertFalse(result["complete_sweep_contained"])
        self.assertGreater(result["object_uncovered_area_m2"], 0.)


if __name__ == "__main__":
    unittest.main()
