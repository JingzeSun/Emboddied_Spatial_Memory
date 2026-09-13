import math
import unittest

from spatial_world_model.r4_continuous_geometry import (
    box_core_cells,
    box_sweep_intersecting_cells,
    cells_fully_in_rectangle,
    circle_core_cells,
    circle_sweep_intersecting_cells,
    first_uncertified_sweep,
)


class ContinuousGeometryTests(unittest.TestCase):
    def test_rectangle_requires_the_complete_cell(self):
        self.assertEqual(cells_fully_in_rectangle((.001, .019, .001, .019), .01), set())
        self.assertEqual(cells_fully_in_rectangle((0., .02, 0., .01), .01), {(0, 0), (1, 0)})

    def test_circle_core_rejects_a_cell_whose_centre_only_is_inside(self):
        intervals = ((-.001, .001), (-.001, .001))
        cells = circle_core_cells(intervals, .07, .01)
        self.assertIn((5, 0), cells)
        self.assertNotIn((6, 0), cells)
        self.assertLess(math.dist((.065, .005), (-.001, -.001)), .07)

    def test_circle_sweep_includes_a_touched_cell_with_outside_centre(self):
        cells = circle_sweep_intersecting_cells((0., 0.), (0., 0.), .07, .01)
        self.assertGreater(math.dist((.065, .035), (0., 0.)), .07)
        self.assertIn((6, 3), cells)

    def test_box_core_uses_the_intersection_of_allowed_poses(self):
        cells = box_core_cells(((-.01, .01), (-.01, .01)), (.03, .02), .01)
        self.assertEqual(cells, {(-2, -1), (-2, 0), (-1, -1), (-1, 0),
                                 (0, -1), (0, 0), (1, -1), (1, 0)})

    def test_diagonal_box_sweep_does_not_use_the_full_bounding_box(self):
        cells = box_sweep_intersecting_cells((0., 0.), (.1, .1), (.01, .01), .01)
        self.assertIn((5, 5), cells)
        self.assertNotIn((0, 9), cells)

    def test_first_uncertified_step_checks_both_complete_bodies(self):
        trajectory = [
            {"object_position_m": [0., 0., .04], "robot_position_m": [0., -.2, .1]},
            {"object_position_m": [.001, 0., .04], "robot_position_m": [0., -.199, .1]},
        ]
        object_cells = circle_sweep_intersecting_cells((0., 0.), (.001, 0.), .07, .01)
        pusher_cells = box_sweep_intersecting_cells((0., -.2), (0., -.199), (.15, .025), .01)
        complete = first_uncertified_sweep(
            trajectory, object_cells | pusher_cells, object_radius=.07,
            pusher_half_size=(.15, .025), cell_m=.01)
        self.assertTrue(complete["complete_sweep_contained"])
        incomplete = first_uncertified_sweep(
            trajectory, (object_cells | pusher_cells) - {next(iter(pusher_cells))},
            object_radius=.07, pusher_half_size=(.15, .025), cell_m=.01)
        self.assertFalse(incomplete["complete_sweep_contained"])
        self.assertEqual(incomplete["first_uncertified_step"], 1)


if __name__ == "__main__":
    unittest.main()
