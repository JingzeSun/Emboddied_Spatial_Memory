from copy import deepcopy
import math
import unittest

from spatial_world_model import r4_continuous_map as maps
from spatial_world_model import r4_continuous_readout as readout
from spatial_world_model import r4_object_association as objects
from spatial_world_model import r4_observed_map_v2 as nominal_maps
from spatial_world_model.r4_query_v2 import domain_spec


FOCAL = 40 / math.tan(math.radians(21))


def frame(time=0., wall=False):
    value = {
        "time_s": time, "width": 80, "height": 80,
        "camera_position_m": [0., -.2, 1.4], "camera_xyzw": [1., 0., 0., 0.],
        "intrinsics": [FOCAL, FOCAL, 39.5, 39.5],
        "ee_position_m": [0., -.4, .05], "ee_velocity_mps": [0., 0., 0.],
        "depth_m": [1.4] * 6400,
    }
    object_depth = 1.32
    for row in range(80):
        for column in range(80):
            x = (column - 39.5) * object_depth / FOCAL
            y = -.2 - (row - 39.5) * object_depth / FOCAL
            if x * x + y * y <= .07 ** 2:
                value["depth_m"][row * 80 + column] = object_depth
    if wall:
        for row in range(8, 13):
            for column in range(9):
                value["depth_m"][row * 80 + column] = 1.1
    return value


def build(wall=False):
    history = {"schema_version": nominal_maps.HISTORY_VERSION,
               "frames": [frame(-.1, wall), frame(0., wall)]}
    return maps.build_map(
        history, objects.sensor_spec(), objects.common_shape_spec(), domain_spec(),
        nominal_maps.parameters(), maps.parameters(), history_mode="recent")


def opening_prediction(intervals):
    return {
        "schema_version": "public-openings-v1",
        "candidates": [{
            "coordinate_intervals_m": intervals,
            "coordinates_m": [math.fsum(value) / 2 for value in intervals],
            "plane_height_interval_m": [.2999, .3001],
            "support": [],
        }],
        "conflicts": [], "incomplete_observations": [], "rejected_counts": {},
        "history_frames": 2,
    }


def synthetic_map():
    floor = {(0, 0): (12, 3, 4), (1, 0): (12, 3, 4), (2, 0): (20, 8, 9)}
    walls = {(2, 0): (17, 5, 6)}
    body_core = {(0, 1)}
    body_possible = {(0, 1), (1, 1)}
    wall_cells = set(walls)
    certified = (set(floor) | body_core) - wall_cells
    return {
        "observed_wall_interval_cells": [list(cell) for cell in walls],
        "body_occlusion_unknown_cells": [list(cell) for cell in body_possible - body_core],
        "observed_floor_cells": [list(cell) for cell in floor],
        "certified_free_cells": [list(cell) for cell in certified],
    }


class ContinuousMapTests(unittest.TestCase):
    def test_uncertified_provenance_keeps_wall_and_unknown_separate(self):
        kinds = maps.classify_uncertified_cells(synthetic_map(), {(2, 0), (1, 1), (3, 0), (20, 20)})
        self.assertEqual(kinds["observed_wall_interval"], [[2, 0]])
        self.assertEqual(kinds["body_occlusion_unknown"], [[1, 1]])
        self.assertEqual(kinds["sampling_gap_unknown"], [[3, 0]])
        self.assertEqual(kinds["outside_observed_region"], [[20, 20]])

    def test_parameters_and_domain_are_immutable_values(self):
        value = maps.parameters()
        value["cell_m"] = .01
        self.assertEqual(maps.parameters()["cell_m"], .005)
        domain = domain_spec()
        shape = {key: domain[key] for key in ("object_radius_m", "object_half_height_m",
                                               "pusher_half_size_m")}
        bad = deepcopy(shape)
        bad["object_radius_m"] = .08
        self.assertNotEqual(bad, shape)

    def test_public_depth_builds_whole_cell_floor_and_body_core(self):
        result = build()
        self.assertEqual(result["status"], "opening_intervals_unresolved")
        self.assertTrue(result["assumption_conditioned"])
        self.assertTrue(result["observed_floor_cells"])
        self.assertTrue(result["decision_body_core_cells"])
        self.assertTrue(result["body_occlusion_unknown_cells"])
        self.assertTrue(result["floor_cell_witnesses"])
        self.assertFalse(result["observed_wall_interval_cells"])
        self.assertFalse(result["formal_model_ready"])

    def test_observed_wall_interval_cannot_remain_certified_free(self):
        result = build(wall=True)
        walls = set(map(tuple, result["observed_wall_interval_cells"]))
        free = set(map(tuple, result["certified_free_cells"]))
        self.assertTrue(walls)
        self.assertFalse(walls & free)
        self.assertEqual(len(result["wall_cell_witnesses"]), len(walls))

    def test_opening_interval_extremes_shrink_gap_and_expand_front(self):
        raw = [[-1., -.1, .5, .55], [.1, 1., .5, .55]]
        intervals = [[-.1, -.02], [.02, .1], [.495, .505]]
        rectangles, records, status = maps._propagate_opening_intervals(
            raw, [intervals], .05, .005)
        self.assertEqual(status, "continuous_map_ready")
        self.assertEqual(rectangles, [[-1., -.02, .495, .555], [.02, 1., .495, .555]])
        self.assertEqual(records[0]["coordinate_intervals_m"], intervals)
        free = [[x, y] for x in range(-4, 4) for y in range(90, 121)]
        value = {"cell_m": .005, "observed_floor_cells": free,
                 "observed_wall_interval_rectangles_xy_m": rectangles}
        openings = readout.public_openings(value)
        self.assertEqual(openings[0]["x_bounds_m"], [-.02, .02])
        self.assertTrue(openings[0]["coordinate_uncertainty_certified"])
        self.assertAlmostEqual(math.fsum((intervals[0][0], intervals[0][1])) / 2,
                               -.06)
        self.assertAlmostEqual(math.fsum((intervals[1][0], intervals[1][1])) / 2,
                               .06)

    def test_opening_interval_without_both_observed_wall_sides_is_unresolved(self):
        intervals = [[-.1, -.02], [.02, .1], [.49, .51]]
        rectangles, records, status = maps._propagate_opening_intervals(
            [[-1., -.1, .5, .55]], [intervals], .05, .005)
        self.assertEqual(rectangles, [])
        self.assertEqual(records, [])
        self.assertEqual(status, "opening_0_wall_side_unresolved")

    def test_public_opening_input_rejects_private_or_midpoint_changed_fields(self):
        prediction = opening_prediction([[-.1, -.02], [.02, .1], [.49, .51]])
        prediction["labels"] = {}
        with self.assertRaises(ValueError):
            maps._opening_intervals(prediction, 2)
        prediction.pop("labels")
        prediction["candidates"][0]["coordinates_m"][0] = 0.
        with self.assertRaises(ValueError):
            maps._opening_intervals(prediction, 2)


if __name__ == "__main__":
    unittest.main()
