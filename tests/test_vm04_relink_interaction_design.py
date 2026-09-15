"""Fixed-scene action design cannot turn private outcomes into a route."""

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops/vsmt"))
import vm04_relink_interaction_design as design


class VM04RelinkInteractionDesignTests(unittest.TestCase):
    def setUp(self):
        self.proposal = design.load_proposal()
        self.reachable = [{"x": x, "y": 0.9, "z": z}
                          for x in (0.0, 0.25, 0.5)
                          for z in (0.0, 0.25)]

    def test_fixed_four_slots_stay_closed_until_route_force_and_put_api_review(self):
        self.assertEqual(self.proposal["original_relink_slots_by_family"],
                         [[4, 11], [6, 12]])
        self.assertFalse(self.proposal["probe_authorized"])
        for key in ("generation_authorized", "training_authorized",
                    "memory_history_checked"):
            self.assertFalse(self.proposal[key])
        for key in ("push_pull_force_ladder_newtons",
                    "receptacle_target_source",
                    "public_typed_receptacle_reader_verified_sha256",
                    "pinned_simulator_putobject_api_smoke_receipt_sha256",
                    "trusted_private_interaction_runner_sha256",
                    "pickup_manual_interact", "put_place_stationary"):
            self.assertIsNone(self.proposal[key])
        for change in ({"probe_authorized": True},
                       {"push_pull_force_ladder_newtons": [20.0, 80.0]},
                       {"status": "frozen_fixed_two_house_probe_only"},
                       {"generation_authorized": True},
                       {"first_post_initial_pose_agent_motion_policy":
                        "TeleportFull_to_target"}):
            with self.assertRaises(ValueError):
                design.validate_proposal(dict(self.proposal, **change))

    def test_original_exclusive_capability_selects_one_pickup_or_two_independent_forces(self):
        self.assertEqual(design.capability_branches(
            {"pickupable": True, "moveable": False}), ("pickup_put",))
        self.assertEqual(design.capability_branches(
            {"pickupable": False, "moveable": True}), ("push", "pull"))
        for object_row in ({"pickupable": False, "moveable": False},
                           {"pickupable": True, "moveable": True}):
            with self.assertRaisesRegex(ValueError, "exactly one"):
                design.capability_branches(object_row)

    def test_public_route_is_deterministic_and_has_no_private_asset_identity(self):
        start = {"x": 0.0, "y": 0.9, "z": 0.0}
        region = [0.5, 0.8, 0.25]
        first = design.single_public_approach_route(start, region,
            self.reachable, start_snap_tolerance_m=0.02)
        second = design.single_public_approach_route(start, region,
            list(reversed(self.reachable)), start_snap_tolerance_m=0.02)
        self.assertEqual(first, second)
        self.assertEqual(first["path_positions"][0], start)
        self.assertEqual(first["path_positions"][-1],
                         {"x": 0.5, "y": 0.9, "z": 0.25})
        self.assertFalse(first["true_asset_position_used"])
        self.assertFalse(first["target_instance_id_used"])
        self.assertEqual(first["fallback_routes_considered"], 0)
        self.assertNotIn("objectId", json.dumps(first))

    def test_real_action_plan_turns_and_moves_without_navigation_teleport(self):
        route = design.single_public_approach_route(
            {"x": 0.0, "y": 0.9, "z": 0.0}, [0.5, 0.8, 0.25],
            self.reachable, start_snap_tolerance_m=0.02)
        actions = design.agent_actions_for_route(
            route["path_positions"], 0.0, route["approach_centroid_m"])
        self.assertTrue(actions)
        self.assertTrue(any(row["action"] == "MoveAhead" for row in actions))
        self.assertTrue(all(row["action"] in
            ("RotateRight", "RotateLeft", "MoveAhead") for row in actions))
        self.assertEqual(sum(row["action"] == "MoveAhead" for row in actions),
                         len(route["path_positions"]) - 1)

    def test_unavailable_route_or_off_grid_start_fails_without_substitution(self):
        start = {"x": 0.0, "y": 0.9, "z": 0.0}
        with self.assertRaisesRegex(ValueError, "off the frozen reachable"):
            design.single_public_approach_route(
                {"x": 0.12, "y": 0.9, "z": 0.0}, [0.5, 0.8, 0.25],
                self.reachable, start_snap_tolerance_m=0.02)
        with self.assertRaisesRegex(ValueError, "route is unavailable"):
            design.single_public_approach_route(start, [0.5, 0.8, 0.25],
                [self.reachable[0], self.reachable[-1]],
                start_snap_tolerance_m=0.02)


if __name__ == "__main__":
    unittest.main()
