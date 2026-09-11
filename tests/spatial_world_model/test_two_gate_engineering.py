"""Pure orchestration checks. Run only through the server SH-04-R2 entry point."""
from copy import deepcopy
import unittest

from spatial_world_model.two_gate_engineering import compare_replay, observation_checks, step_ids


class TwoGateEngineeringTests(unittest.TestCase):
    def test_fixed_inventory_has_fresh_reverse_replays(self):
        ids = step_ids({"worlds": ["LL", "LR", "RL", "RR"]})
        self.assertEqual(len(ids), 37)
        primary = [value.removeprefix("primary-") for value in ids if value.startswith("primary-")]
        replay = [value.removeprefix("replay-") for value in ids if value.startswith("replay-")]
        self.assertEqual(replay, list(reversed(primary)))
        self.assertEqual(len(set(ids)), len(ids))

    def test_replay_does_not_pass_missing_or_changed_raw_artifacts(self):
        self.assertFalse(compare_replay({}, {})["equal"])
        fields = ("base_snapshot_sha256", "control_sha256", "state_spec", "state_shape",
                  "sensor_count", "step_count", "files", "end_snapshot", "assessment")
        first = {key: {"value": 1} for key in fields}
        second = deepcopy(first)
        self.assertTrue(compare_replay(first, second)["equal"])
        second["files"] = {"trajectory.jsonl": {"sha256": "changed", "bytes": 3}}
        result = compare_replay(first, second)
        self.assertFalse(result["equal"])
        self.assertEqual(result["different_fields"], ["files"])

    def evidence_fixture(self):
        config = {"worlds": ["LL", "LR", "RL", "RR"], "observation": {
            "history_frame_count": 4, "recent_frames": 2, "resolution": [64, 64],
            "fixed_view_frame_indices": {"A": 0, "B": 1},
            "minimum_each_gate_segment_pixels_in_designated_view": 4}}
        common = {name: 0 for name in ("gate_0_left", "gate_0_right", "gate_1_left", "gate_1_right")}
        common.update(object=8, pusher=8)
        near, far = deepcopy(common), deepcopy(common)
        near.update(gate_0_left=4, gate_0_right=4)
        far.update(gate_1_left=4, gate_1_right=4)
        publics = {w: {"history": [{"height": 64, "width": 64} for _ in range(4)]}
                   for w in config["worlds"]}
        evidence = {w: {"visibility": deepcopy([near, far, common, common]),
                        "observation_preserves_integration": True} for w in config["worlds"]}
        snapshots = {w: {"state_spec": 1, "state": [0, 0], "xml_sha256": w} for w in config["worlds"]}
        return publics, evidence, snapshots, config

    def test_transit_leak_cannot_hide_behind_designated_view_checks(self):
        publics, evidence, snapshots, config = self.evidence_fixture()
        self.assertTrue(all(observation_checks(publics, evidence, snapshots, config).values()))
        evidence["LL"]["visibility"][0]["gate_1_left"] = 1
        result = observation_checks(publics, evidence, snapshots, config)
        self.assertFalse(result["no_single_frame_sees_both_gates"])
        self.assertFalse(result["designated_near_view"])

    def test_truth_snapshot_cannot_be_replaced_by_same_recent_pixels(self):
        publics, evidence, snapshots, config = self.evidence_fixture()
        snapshots["LR"]["state"][0] = 0.1
        result = observation_checks(publics, evidence, snapshots, config)
        self.assertFalse(result["same_nonlayout_integration"])

    def test_incomplete_visibility_is_not_empty_success(self):
        publics, evidence, snapshots, config = self.evidence_fixture()
        evidence["LL"]["visibility"] = []
        result = observation_checks(publics, evidence, snapshots, config)
        self.assertFalse(result["complete_history_evidence"])
        self.assertFalse(result["recent_gates_invisible"])

    def test_boolean_or_negative_pixel_count_rejected(self):
        for value in (True, -1, 4097):
            publics, evidence, snapshots, config = self.evidence_fixture()
            evidence["LL"]["visibility"][0]["object"] = value
            with self.assertRaises(ValueError):
                observation_checks(publics, evidence, snapshots, config)

    def test_resolution_change_cannot_pass_registered_sensor_audit(self):
        publics, evidence, snapshots, config = self.evidence_fixture()
        publics["LL"]["history"][0]["width"] = 32
        self.assertFalse(observation_checks(publics, evidence, snapshots, config)["registered_sensor_resolution"])

    def test_distinct_geometry_pixels_cannot_exceed_image_total(self):
        publics, evidence, snapshots, config = self.evidence_fixture()
        evidence["LL"]["visibility"][0].update(object=3000, pusher=3000)
        with self.assertRaises(ValueError):
            observation_checks(publics, evidence, snapshots, config)


if __name__ == "__main__":
    unittest.main()
