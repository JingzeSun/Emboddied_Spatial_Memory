"""Private v3 selection filters architecture without result-driven replacement."""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from vsmt.vm04_target_selection_v3 import select_private_targets_at_fixed_pose


class TargetSelectionTests(unittest.TestCase):
    def setUp(self):
        self.ranked = ["wall", "painting", "chair", "mug"]
        self.metadata = {
            "wall": {"position": {"x": 0, "y": 0, "z": 0}},
            "painting": {"position": {"x": 1, "y": 0, "z": 0}},
            "chair": {"position": {"x": 2, "y": 0, "z": 0}, "moveable": True},
            "mug": {"position": {"x": 3, "y": 0, "z": 0}, "pickupable": True},
        }
        self.authored = frozenset({"painting", "chair", "mug"})

    def select(self, program, policy, ranked=None):
        return select_private_targets_at_fixed_pose(
            program, self.ranked if ranked is None else ranked,
            self.metadata, self.authored,
            static_authored_asset_lifecycle_policy=policy,
            relink_requires_moveable_or_pickupable=True,
        )

    def test_static_policy_affects_lifecycle_but_not_structural_target_order(self):
        allow = "allow_visibility_lifecycle_if_simulator_action_and_poststate_verified"
        exclude = "exclude_static_assets_from_physical_lifecycle_targets"
        self.assertEqual(self.select("BIRTH", allow), ["painting"])
        self.assertEqual(self.select("BIRTH", exclude), ["chair"])
        self.assertEqual(self.select("SPLIT", exclude), ["painting", "chair"])
        self.assertEqual(self.select("RELINK", allow), ["chair"])
        self.assertEqual(self.select("REPLACE", exclude), ["chair", "mug"])

    def test_shortage_preserves_slot_failure_and_never_falls_back_to_wall(self):
        exclude = "exclude_static_assets_from_physical_lifecycle_targets"
        with self.assertRaisesRegex(ValueError, "original fixed slot"):
            self.select("REPLACE", exclude, ["wall", "painting", "chair"])
        with self.assertRaisesRegex(ValueError, "original fixed slot"):
            self.select("SPLIT", exclude, ["wall", "painting"])
        with self.assertRaisesRegex(ValueError, "explicit movable"):
            select_private_targets_at_fixed_pose(
                "RELINK", self.ranked, self.metadata, self.authored,
                static_authored_asset_lifecycle_policy=exclude,
                relink_requires_moveable_or_pickupable=False)


if __name__ == "__main__":
    unittest.main()
