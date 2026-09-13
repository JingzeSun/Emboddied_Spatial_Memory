import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "r4_development_protocol_v3", ROOT / "ops/spatial_history/r4_development_protocol_v3.py")
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


class DevelopmentProtocolV3Test(unittest.TestCase):
    def test_fixed_partition_and_no_confirmation(self):
        config, families, reused = stage.configuration()
        self.assertEqual(len(families), 52)
        self.assertEqual(len(reused), 50)
        self.assertEqual(config["generate_family_ids"], ["r4-23", "r4-58"])
        self.assertFalse({row["split"] for row in families} & set(config["forbidden_splits"]))

    def test_observation_remains_y_only_with_family_constant_x(self):
        config, families, _ = stage.configuration()
        base = stage.read(ROOT / config["base"])
        for row in families:
            value = stage.family_config(base, row)
            self.assertTrue(all(set(segment) == {"time_s", "y_m"}
                                for segment in value["observation"]["camera_segments"]))
            self.assertIsInstance(value["observation"]["camera_x_m"], (int, float))
            self.assertEqual(len(value["observation"]["camera_segments"]), 6)
        self.assertFalse(config["observation_trajectory"]["new_x_motion"])

    def test_only_registered_v1_e0_failure_can_be_replaced(self):
        config, _, _ = stage.configuration()
        checks = {"physics": True, "public_geometry": False, "replay_equal": True}
        result = {"failed_checks": ["public_geometry"], "checks": checks}
        self.assertTrue(stage.source_non_e0_accepted(result, "r4-36", config))
        self.assertFalse(stage.source_non_e0_accepted(result, "r4-22", config))
        result["failed_checks"] = ["physics"]
        result["checks"]["physics"] = False
        self.assertFalse(stage.source_non_e0_accepted(result, "r4-36", config))

    def test_xy_upgrade_is_future_new_version_not_automatic(self):
        config, _, _ = stage.configuration()
        value = config["xy_upgrade_contingency"]
        self.assertEqual(value["trigger_systems"], ["D", "F", "W"])
        self.assertEqual(value["trigger_stage"], "after_complete_SH05_only")
        self.assertTrue(value["preserve_current_denominator_and_results"])
        self.assertFalse(value["automatic_release"])
        self.assertIn("before_first_main_training_result", value["good_performance_numeric_rule_status"])

    def test_config_cannot_authorize_downstream_work(self):
        config = json.loads((ROOT / stage.CONFIG_PATH).read_text(encoding="utf-8"))
        self.assertTrue(config["data_completion_authorized"])
        self.assertFalse(config["dual_m_authorized"])
        self.assertFalse(config["training_authorized"])
        self.assertFalse(config["confirmation_authorized"])

    def test_generator_dispatches_only_registered_boundary_version(self):
        from spatial_world_model import public_geometry, public_geometry_v2, r4_generation_v2
        self.assertIs(r4_generation_v2.opening_recoverer({"version": "old"}),
                      public_geometry.recover_openings)
        self.assertIs(r4_generation_v2.opening_recoverer(
            {"version": "sh05-r4-e0-boundary-v2-review-v1"}),
            public_geometry_v2.recover_openings)


if __name__ == "__main__":
    unittest.main()
