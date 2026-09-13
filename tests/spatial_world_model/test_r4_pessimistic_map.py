import unittest

from spatial_world_model.r4_pessimistic_map import (
    circle_sweep_cells, decision_body_free_cells, pessimistic_trajectory,
    prediction_from_trajectory,
)


DOMAIN = {"object_radius_m": .07, "pusher_half_size_m": [.15, .025, .025]}


def observed(free):
    return {
        "cell_m": .01, "nominal_free_cells": [list(v) for v in free],
        "current_object": {
            "status": "association_ready",
            "position_intervals_m": [[-.001, .001], [-.001, .001], [.04, .04]],
            "robot_state": {"position_m": [0., -.2, .1]},
        },
    }


def proxy():
    rows = []
    for step in range(10001):
        rows.append({
            "step_index": step, "time_s": step * .002,
            "object_position_m": [step * .00001, 0., .04],
            "object_velocity_mps": [.005, 0., 0.],
            "robot_position_m": [0., -.2 + step * .00001, .1],
            "robot_velocity_mps": [0., .005, 0.], "servo_force_n": [0., 0.],
            "object_obstacle_contact": False, "robot_obstacle_contact": False,
            "object_robot_contact": False,
        })
    return {"status": "nominal_complete", "trajectory": rows}


class PessimisticMapTests(unittest.TestCase):
    def test_circle_uses_capsule_instead_of_square_corners(self):
        cells = circle_sweep_cells([0., 0.], [0., 0.], .07, .01)
        self.assertIn((0, 0), cells)
        self.assertNotIn((6, 6), cells)

    def test_body_certificate_is_intersection_over_position_interval(self):
        cells = decision_body_free_cells(observed(set()), DOMAIN)
        self.assertIn((0, 0), cells)
        self.assertNotIn((6, 6), cells)
        self.assertTrue(any(y == -20 for _, y in cells))

    def test_first_unseen_sweep_freezes_without_unknown_as_free(self):
        source = proxy()
        initial = decision_body_free_cells(observed(set()), DOMAIN)
        trajectory, audit = pessimistic_trajectory(observed(initial), source, DOMAIN)
        self.assertIsNotNone(audit["stop_step"])
        stop = audit["stop_step"]
        self.assertEqual(len(trajectory), 10001)
        self.assertEqual(trajectory[stop]["object_position_m"],
                         trajectory[stop - 1]["object_position_m"])
        self.assertEqual(trajectory[-1]["object_velocity_mps"], [0., 0., 0.])
        value = prediction_from_trajectory(trajectory, False)
        self.assertEqual(len(value["object_position_m"]), 200)
        self.assertEqual(value["task_success_probability"], 0.)


if __name__ == "__main__":
    unittest.main()
