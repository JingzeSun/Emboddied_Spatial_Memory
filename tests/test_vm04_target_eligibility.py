"""Trusted target eligibility, separate from deployed perception and pose choice."""

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vsmt.vm04_target_eligibility import asset_target_profiles, authored_asset_ids


class TargetBoundaryTests(unittest.TestCase):
    def test_author_house_hierarchy_excludes_architecture_and_keeps_children(self):
        house = {
            "objects": [{"id": "chair", "children": [{"id": "drawer"}]}],
            "walls": [{"id": "wall"}], "doors": [{"id": "door"}],
            "windows": [{"id": "window"}], "rooms": [{"id": "room"}],
        }
        self.assertEqual(authored_asset_ids(house), frozenset({"chair", "drawer"}))
        house["walls"].append({"id": "drawer"})
        with self.assertRaisesRegex(ValueError, "overlap"):
            authored_asset_ids(house)

    def test_profiles_preserve_geometry_rank_and_ignore_object_class_text(self):
        ranked = ["wall", "painting", "chair"]
        metadata = {
            "wall": {"position": {"x": 0, "y": 0, "z": 0}, "moveable": False},
            "painting": {"position": {"x": 1, "y": 0, "z": 0},
                         "moveable": False, "objectType": "Painting"},
            "chair": {"position": {"x": 2, "y": 0, "z": 0},
                      "moveable": True, "objectType": "Chair"},
        }
        ids = frozenset({"painting", "chair"})
        expected = {"authored_asset": ["painting", "chair"],
                    "movable_asset": ["chair"]}
        self.assertEqual(asset_target_profiles(ranked, metadata, ids), expected)
        metadata["chair"]["objectType"] = "Wall"
        metadata["painting"]["objectType"] = "Chair"
        self.assertEqual(asset_target_profiles(ranked, metadata, ids), expected)

    def test_missing_real_position_and_duplicate_rank_are_rejected(self):
        metadata = {"chair": {"moveable": True}}
        ids = frozenset({"chair"})
        self.assertEqual(asset_target_profiles(["chair"], metadata, ids),
                         {"authored_asset": [], "movable_asset": []})
        with self.assertRaisesRegex(ValueError, "unique"):
            asset_target_profiles(["chair", "chair"], metadata, ids)
        metadata["chair"]["position"] = {"x": float("nan"), "y": 0, "z": 0}
        self.assertEqual(asset_target_profiles(["chair"], metadata, ids),
                         {"authored_asset": [], "movable_asset": []})


if __name__ == "__main__":
    unittest.main()
