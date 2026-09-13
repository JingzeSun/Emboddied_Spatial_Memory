from copy import deepcopy
import math
import unittest

from spatial_world_model import r4_continuous_map as maps
from spatial_world_model import r4_continuous_readout as readout
from spatial_world_model import r4_simple_dynamics as dynamics
from spatial_world_model.r4_query_v2 import domain_spec


def controls(x=0., y=0.):
    return {"ee_velocity_mps": [[x, y, 0.] for _ in range(200)],
            "duration_s": [.1] * 200}


def goal():
    return {
        "goal_center_xy_m": [0., 2.65],
        "goal_x_bounds_m": [-.25, .25],
        "goal_y_bounds_m": [2.45, 2.85],
        "require_ordered_actual_gate_passage": True,
        "gate_attempt_rule": "forward center-plane crossing starts attempt; center retreat below plane cancels; rear clearance completes same active attempt",
        "goal_containment": "entire actual cylinder horizontal projection",
        "settled_interval_s": [19., 20.],
        "maximum_object_linear_speed_mps": .02,
        "containment_boundary_tolerance_m": .001,
        "collision_is_task_failure": False,
        "failure_cost": 1,
        "success_cost": 0,
    }


def current(position=(0., 0., .04), interval_width=0., velocity=(0., 0., 0.),
            robot=(0., -.25, .05)):
    return {
        "status": "association_ready",
        "position_m": list(position),
        "position_intervals_m": [[position[axis] - interval_width,
                                  position[axis] + interval_width]
                                 for axis in range(3)],
        "interval_mean_velocity_mps": list(velocity),
        "interval_mean_velocity_intervals_mps": [[value, value] for value in velocity],
        "robot_state": {"position_m": list(robot), "velocity_mps": [0., 0., 0.]},
    }


def continuous_map(floor=((-1., 1., -1., 3.),), walls=None, object_value=None):
    if walls is None:
        walls = ((-1., -.2, .5, .55), (.2, 1., .5, .55),
                 (-1., -.2, 1.5, 1.55), (.2, 1., 1.5, 1.55))
    cell = .005
    floor_cells = []
    for rectangle in floor:
        for x in range(math.ceil(rectangle[0] / cell), math.floor(rectangle[1] / cell)):
            for y in range(math.ceil(rectangle[2] / cell), math.floor(rectangle[3] / cell)):
                floor_cells.append([x, y])
    wall_cells = []
    for rectangle in walls:
        for x in range(math.floor(rectangle[0] / cell), math.ceil(rectangle[1] / cell)):
            for y in range(math.floor(rectangle[2] / cell), math.ceil(rectangle[3] / cell)):
                wall_cells.append([x, y])
    return {
        "schema_version": maps.VERSION,
        "status": "nominal_map_ready",
        "cell_m": cell,
        "geometry_parameters": maps.parameters(),
        "ground": {"height_interval_m": [0., 0.]},
        "current_object": object_value or current(),
        "observed_floor_cells": floor_cells,
        "observed_floor_support_rectangles_xy_m": [list(value) for value in floor],
        "observed_wall_interval_cells": wall_cells,
        "observed_wall_interval_rectangles_xy_m": [list(value) for value in walls],
        "body_occlusion_unknown_cells": [],
    }


class SimpleDynamicsTests(unittest.TestCase):
    def test_complete_zero_control_prediction_and_independent_certificate(self):
        observed = continuous_map(
            floor=((-1., 1., -1., -.1), (-1., -.08, -.1, .1),
                   (.08, 1., -.1, .1), (-1., 1., .1, 3.)),
            object_value=current(interval_width=.001))
        result = dynamics.predict(observed, controls(), goal(), domain_spec(),
                                  dynamics.parameters(), readout.parameters())
        self.assertEqual(result["status"], "complete")
        self.assertEqual(len(result["trajectory"]), 10001)
        self.assertEqual(len(result["prediction"]["object_position_m"]), 200)
        self.assertEqual(len(result["initial_sensitivity"]), 5)
        self.assertFalse(result["certificate"]["complete_sweep_contained"])
        self.assertFalse(result["formal_model_ready"])

    def test_unknown_clips_only_denied_body_while_object_keeps_inertia(self):
        observed = continuous_map(
            floor=((-1., 1., -.15, .5),), walls=(),
            object_value=current(velocity=(.1, 0., 0.), robot=(0., -.4, .05)))
        simulation = dynamics._simulate(observed, controls(y=-.5), domain_spec(),
                                        [0., 0.], step_count=80)
        self.assertGreater(simulation["trajectory"][-1]["object_position_m"][0], 0.)
        self.assertTrue(any(value["body"] == "pusher" and
                            value["source"] != "observed_wall_interval"
                            for value in simulation["contact_provenance"]))
        self.assertFalse(any(value["body"] == "object" and
                             value["source"] != "observed_wall_interval"
                             for value in simulation["contact_provenance"]))

    def test_observed_wall_and_unknown_sources_are_distinct(self):
        observed = continuous_map(
            floor=((-1., 1., -.5, .5),),
            walls=((-1., 1., -.34, -.29),),
            object_value=current(robot=(0., -.4, .05)))
        simulation = dynamics._simulate(observed, controls(y=.5), domain_spec(),
                                        [0., 0.], step_count=300)
        self.assertTrue(any(value["source"] == "observed_wall_interval"
                            for value in simulation["contact_provenance"]))
        self.assertFalse(any(value["source"] in
                             {"body_occlusion_unknown", "sampling_gap_unknown",
                              "outside_observed_region"}
                             for value in simulation["contact_provenance"]))

    def test_pusher_contact_transfers_momentum(self):
        observed = continuous_map(floor=((-1., 1., -1., 1.),), walls=())
        simulation = dynamics._simulate(observed, controls(y=.5), domain_spec(),
                                        [0., 0.], step_count=800)
        self.assertGreater(simulation["trajectory"][-1]["object_position_m"][1], 0.)
        self.assertTrue(any(value["source"] == "object_pusher"
                            for value in simulation["contact_provenance"]))

    def test_same_input_is_deterministic_and_private_fields_are_rejected(self):
        observed = continuous_map()
        first = dynamics._simulate(observed, controls(), domain_spec(), [0., 0.], step_count=5)
        second = dynamics._simulate(observed, controls(), domain_spec(), [0., 0.], step_count=5)
        self.assertEqual(first, second)
        private = deepcopy(observed)
        private["source_xml"] = "forbidden.xml"
        with self.assertRaises(ValueError):
            dynamics.predict(private, controls(), goal(), domain_spec(),
                             dynamics.parameters(), readout.parameters())


if __name__ == "__main__":
    unittest.main()
