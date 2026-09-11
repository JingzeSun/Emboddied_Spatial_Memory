"""Server-only contract tests; the fixture contains no simulated evidence."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from spatial_world_model.pair_contract import audit_dataset, audit_pair, model_input


FIXTURE = Path(__file__).resolve().parents[2] / "data/fixtures/spatial_history/manual_pair.json"


class PairContractTests(unittest.TestCase):
    def setUp(self):
        self.pair = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_fixture_is_not_physics_evidence(self):
        report = audit_pair(self.pair)
        self.assertTrue(report["contract_valid"])
        self.assertEqual(report["origin_kind"], "hand_authored_fixture")
        self.assertFalse(report["physics_and_visibility_verified"])
        self.assertTrue(report["early_visual_evidence_differs"])
        self.assertEqual(report["outcomes_differ_by_action"], [True, True])

    def test_recent_inputs_identical_but_full_inputs_differ(self):
        for action in (0, 1):
            self.assertEqual(model_input(self.pair, 0, action, recent_only=True),
                             model_input(self.pair, 1, action, recent_only=True))
            self.assertNotEqual(model_input(self.pair, 0, action), model_input(self.pair, 1, action))

    def test_public_view_is_an_allowlist(self):
        view = model_input(self.pair, 0, 0)
        self.assertEqual(set(view), {"history", "controls", "goal"})
        text = json.dumps(view)
        for forbidden in ("pair_id", "family_id", "split", "seed", "sha256", "future",
                          "object_position_m", "hidden_obstacles", "action_index"):
            self.assertNotIn(forbidden, text)

    def test_truth_changes_do_not_change_model_features(self):
        before = model_input(self.pair, 0, 0)
        self.pair["worlds"][0]["hidden_obstacles"][0][0] -= 1
        self.pair["worlds"][0]["branches"][0]["future"][0]["object_position_m"][0] += 3
        self.pair["pair_id"] = "different-private-name"
        self.pair["provenance"]["seed"] = 99
        self.assertEqual(before, model_input(self.pair, 0, 0))

    def test_public_view_cannot_mutate_source(self):
        original = deepcopy(self.pair)
        view = model_input(self.pair, 0, 0)
        view["history"][0]["rgb"][0] = 0
        view["controls"][0]["ee_velocity_mps"][0] = 99
        view["goal"]["center_m"][0] = 99
        self.assertEqual(self.pair, original)

    def test_no_contrast_samples_are_retained(self):
        self.pair["worlds"][1]["history"] = deepcopy(self.pair["worlds"][0]["history"])
        for a, b in zip(self.pair["worlds"][0]["branches"], self.pair["worlds"][1]["branches"]):
            b["future"] = deepcopy(a["future"])
        report = audit_dataset([self.pair])[0]
        self.assertFalse(report["early_visual_evidence_differs"])
        self.assertEqual(report["outcomes_differ_by_action"], [False, False])

    def test_recent_sensor_and_robot_shortcuts_rejected(self):
        for field in ("rgb", "depth_m", "ee_velocity_mps", "previous_velocity_mps"):
            with self.subTest(field=field):
                pair = deepcopy(self.pair)
                pair["worlds"][1]["history"][-2][field][0] += 1
                with self.assertRaises(ValueError):
                    audit_pair(pair)

    def test_early_camera_shortcut_rejected(self):
        self.pair["worlds"][1]["history"][0]["camera_position_m"][0] += 1
        with self.assertRaisesRegex(ValueError, "metadata shortcut"):
            audit_pair(self.pair)

    def test_same_snapshot_required_within_each_world(self):
        self.pair["worlds"][0]["branches"][1]["base_snapshot_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "immutable base"):
            audit_pair(self.pair)

    def test_actual_object_transform_cannot_be_an_action(self):
        self.pair["actions"][0][0]["object_delta_m"] = [0.1, 0, 0]
        with self.assertRaisesRegex(ValueError, "unexpected/missing"):
            audit_pair(self.pair)

    def test_hidden_field_cannot_be_nested_in_frame(self):
        self.pair["worlds"][0]["history"][0]["hidden_wall"] = True
        with self.assertRaisesRegex(ValueError, "unexpected/missing"):
            model_input(self.pair, 0, 0)

    def test_future_time_alignment_required(self):
        self.pair["worlds"][0]["branches"][0]["future"][0]["time_s"] = 0.2
        with self.assertRaisesRegex(ValueError, "future time mismatch"):
            audit_pair(self.pair)

    def test_nonfinite_and_boolean_numbers_rejected(self):
        for value in (float("nan"), float("inf"), True, 10 ** 400):
            with self.subTest(value=value):
                pair = deepcopy(self.pair)
                pair["actions"][0][0]["duration_s"] = value
                with self.assertRaises(ValueError):
                    audit_pair(pair)

    def test_bad_image_shape_and_depth_rejected(self):
        for field, value in (("rgb", [1, 2]), ("depth_m", [-1, 1, 1, 1])):
            pair = deepcopy(self.pair)
            pair["worlds"][0]["history"][0][field] = value
            with self.assertRaises(ValueError):
                audit_pair(pair)

    def test_nonlayout_initial_difference_rejected(self):
        self.pair["worlds"][0]["initial_state"]["object_velocity_mps"][0] = 0.1
        with self.assertRaisesRegex(ValueError, "non-layout"):
            audit_pair(self.pair)

    def test_no_test_or_training_split_in_first_contract(self):
        for split in ("test", "validation", "train"):
            self.pair["split"] = split
            with self.assertRaisesRegex(ValueError, "development"):
                audit_pair(self.pair)

    def test_duplicate_pairs_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate pair_id"):
            audit_dataset([self.pair, deepcopy(self.pair)])

    def test_branch_order_and_control_horizon_rejected(self):
        pair = deepcopy(self.pair)
        pair["worlds"][0]["branches"].reverse()
        with self.assertRaisesRegex(ValueError, "order mismatch"):
            audit_pair(pair)
        self.pair["actions"][0][0]["duration_s"] = 0.2
        with self.assertRaisesRegex(ValueError, "sampling times"):
            audit_pair(self.pair)

    def test_empty_prefix_or_empty_dataset_rejected(self):
        self.pair["recent_frames"] = 3
        with self.assertRaisesRegex(ValueError, "early and recent"):
            audit_pair(self.pair)
        with self.assertRaisesRegex(ValueError, "empty dataset"):
            audit_dataset([])

    def test_selector_types_are_strict(self):
        for args in ((True, 0), (0, -1), (2, 0)):
            with self.assertRaises(ValueError):
                model_input(self.pair, *args)


if __name__ == "__main__":
    unittest.main()
