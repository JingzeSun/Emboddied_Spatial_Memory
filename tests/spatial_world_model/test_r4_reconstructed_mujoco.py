from copy import deepcopy
import unittest

from spatial_world_model import r4_continuous_readout as readout
from spatial_world_model import r4_reconstructed_mujoco as physics
from spatial_world_model.r4_query_v2 import domain_spec
from tests.spatial_world_model.test_r4_simple_dynamics import (
    continuous_map, controls, current, goal,
)


class ReconstructedMujocoTests(unittest.TestCase):
    def test_xml_is_standalone_public_reconstruction(self):
        observed = continuous_map()
        xml, provenance = physics.build_xml(observed, domain_spec(), [0., 0.])
        self.assertIn("spatial-history-r4-public-reconstruction-v1", xml)
        self.assertIn("observed_wall_0000", xml)
        self.assertNotIn("world_name", xml)
        self.assertNotIn("snapshot", xml)
        self.assertFalse(provenance["source_xml_used"])
        self.assertEqual(len(provenance["wall_geometries"]), 4)

    def test_complete_output_uses_all_registered_initial_hypotheses(self):
        observed = continuous_map(object_value=current(interval_width=.001))
        result = physics.predict(observed, controls(), goal(), domain_spec(),
                                 physics.parameters(), readout.parameters())
        self.assertEqual(result["status"], "complete")
        self.assertEqual(len(result["trajectory"]), 10001)
        self.assertEqual(len(result["prediction"]["object_position_m"]), 200)
        self.assertEqual(len(result["initial_sensitivity"]), 5)
        self.assertEqual(result["certificate"]["object_projection"],
                         "orientation_independent_cylinder_bounding_sphere")
        self.assertFalse(result["generated_scene"]["source_xml_used"])
        self.assertFalse(result["formal_model_ready"])

    def test_unknown_stops_pusher_without_stopping_inertial_object(self):
        observed = continuous_map(
            floor=((-1., 1., -.15, .5),), walls=(),
            object_value=current(velocity=(.1, 0., 0.), robot=(0., -.4, .05)))
        simulation = physics._simulate(observed, controls(y=-.5), domain_spec(),
                                       [0., 0.], step_count=80)
        self.assertGreater(simulation["trajectory"][-1]["object_position_m"][0], 0.)
        self.assertTrue(any(value["body"] == "pusher" and
                            value["source"] != "observed_wall_interval"
                            for value in simulation["contact_provenance"]))

    def test_engine_object_pusher_contact_transfers_motion(self):
        observed = continuous_map(floor=((-1., 1., -1., 1.),), walls=())
        simulation = physics._simulate(observed, controls(y=.5), domain_spec(),
                                       [0., 0.], step_count=800)
        self.assertGreater(simulation["trajectory"][-1]["object_position_m"][1], 0.)
        self.assertTrue(any(value["source"] == "object_pusher"
                            for value in simulation["contact_provenance"]))

    def test_engine_wall_contact_keeps_observed_provenance(self):
        observed = continuous_map(
            floor=((-1., 1., -.5, .5),),
            walls=((-1., 1., -.34, -.29),),
            object_value=current(robot=(0., -.4, .05)))
        simulation = physics._simulate(observed, controls(y=.5), domain_spec(),
                                       [0., 0.], step_count=300)
        self.assertTrue(any(value["source"] == "observed_wall_interval"
                            and value["body"] == "pusher"
                            for value in simulation["contact_provenance"]))

    def test_engine_replay_is_deterministic(self):
        observed = continuous_map()
        first = physics._simulate(observed, controls(), domain_spec(), [0., 0.], step_count=5)
        second = physics._simulate(observed, controls(), domain_spec(), [0., 0.], step_count=5)
        self.assertEqual(first, second)

    def test_private_map_fields_are_rejected(self):
        observed = continuous_map()
        private = deepcopy(observed)
        private["snapshot"] = {"state": []}
        with self.assertRaises(ValueError):
            physics.predict(private, controls(), goal(), domain_spec(),
                            physics.parameters(), readout.parameters())


if __name__ == "__main__":
    unittest.main()
