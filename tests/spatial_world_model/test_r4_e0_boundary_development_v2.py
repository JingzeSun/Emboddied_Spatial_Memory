import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "r4_e0_boundary_development_v2",
    ROOT / "ops/spatial_history/r4_e0_boundary_development_v2.py")
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


class E0BoundaryDevelopmentStageTests(unittest.TestCase):
    def test_fixed_configuration_has_fifty_sealed_families_and_excludes_partials(self):
        config, rows = stage.configuration()
        ids = stage.family_ids(config)
        self.assertEqual(len(ids), 50)
        self.assertEqual(len(set(ids)), 50)
        self.assertEqual(set(config["excluded_unsealed_family_ids"]), {"r4-23", "r4-58"})
        self.assertTrue(set(config["excluded_unsealed_family_ids"]).isdisjoint(ids))
        self.assertEqual(config["e0_only_family_status"], {
            "r4-22": "family_accepted_but_terminal_verify_cancelled",
            "r4-36": "family_rejected_only_by_e0_v1",
        })
        self.assertEqual({rows[item]["split"] for item in ids}, {
            "model_train", "model_validation", "probe_train", "probe_validation"})
        self.assertFalse(config["e0_frontend_upgrade_authorized"])
        self.assertFalse(config["dual_m_authorized"])
        self.assertFalse(config["training_authorized"])

    def test_modes_preserve_registered_source_frame_numbers(self):
        row = {"camera": {"view_frame_indices": {"A": 28, "B": 68}}}
        self.assertEqual(stage.mode_indices(row), {
            "full": list(range(121)), "view_a": [28],
            "view_b": [68], "recent": [119, 120]})
        prediction = {"candidates": [{"support": [{
            "local_frame_index": 0, "boundary_compatible_pixels": [[58, 39]],
            "boundary_kind": "x_right", "plane_height_interval_m": [.2999, .3001],
        }]}]}
        self.assertEqual(stage.boundary_support(prediction, [68])[0]["source_frame_index"], 68)

    @staticmethod
    def _summary_rows():
        result = []
        ids = stage.family_ids()
        for family_index, family_id in enumerate(ids):
            for case_index in range(16):
                failed = family_id == "r4-36" and case_index < 4
                boundary = ([{"geom_name": "gate_0_right", "boundary_kind": "x_right",
                              "registered_gate_wall": True}] if failed else [])
                result.append({
                    "family_id": family_id, "source_status": "fixture",
                    "split": "model_train", "world": "LL", "mode": "full",
                    "v1_prediction_reproduced": True,
                    "v1_assessment": {"accepted": not failed},
                    "v2_assessment": {"accepted": True, "matches": []},
                    "v2_boundary_support": boundary,
                    "no_boundary_v1_success_geometry_exactly_preserved": True,
                })
        return result

    def test_summary_enforces_frozen_census_and_private_boundary_identity(self):
        rows = self._summary_rows()
        value = stage.summarize(rows, 2)
        self.assertTrue(value["accepted"])
        self.assertEqual(value["conclusion"]["case_count"], 800)
        self.assertEqual(value["conclusion"]["v1_accepted_cases"], 796)
        self.assertEqual(value["conclusion"]["v1_failed_cases"], 4)
        rows[-16]["v2_boundary_support"][0].update(
            geom_name="object", registered_gate_wall=False)
        value = stage.summarize(rows, 2)
        self.assertFalse(value["accepted"])
        self.assertFalse(value["checks"]["boundary_pixels_are_registered_walls"])
        self.assertFalse(value["checks"]["no_boundary_body_hits"])


if __name__ == "__main__":
    unittest.main()
