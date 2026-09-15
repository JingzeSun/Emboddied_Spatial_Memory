"""Private v3 selector consumes only approved, closed contract values."""

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from vsmt.vm04_target_selection_v3 import select_private_targets_at_fixed_pose


class TargetSelectionTests(unittest.TestCase):
    def setUp(self):
        def mask(top, left):
            return [[top <= r < top + 14 and left <= c < left + 14
                     for c in range(28)] for r in range(28)]

        # These four legal positive instance masks have disjoint pixels.
        self.masks = {
            "wall": mask(0, 0), "painting": mask(0, 14),
            "chair": mask(14, 0), "mug": mask(14, 14),
        }
        self.metadata = {
            "wall": {"position": {"x": 0, "y": 0, "z": 0}},
            "painting": {"position": {"x": 1, "y": 0, "z": 0}},
            "chair": {"position": {"x": 2, "y": 0, "z": 0}, "moveable": True},
            "mug": {"position": {"x": 3, "y": 0, "z": 0}, "pickupable": True},
        }
        self.authored = frozenset({"painting", "chair", "mug"})
        self.contract = json.loads(
            (ROOT / "configs/vsmt/vm04_target_boundary_proposal_v3.json")
            .read_text(encoding="utf-8"))

    def select(self, program, masks=None, contract=None):
        return select_private_targets_at_fixed_pose(
            program, self.masks if masks is None else masks,
            self.metadata, self.authored,
            contract=self.contract if contract is None else contract)

    def test_approved_static_visibility_eligibility_and_physical_relink(self):
        self.assertEqual(self.select("BIRTH"), ["painting"])
        self.assertEqual(self.select("RELINK"), ["chair"])
        self.assertEqual(self.select("REPLACE"), ["painting", "chair"])
        self.assertEqual(self.select("REPLACE", dict(reversed(
            list(self.masks.items())))), ["painting", "chair"])
        self.metadata["chair"]["objectType"] = "Wall"
        self.assertEqual(self.select("RELINK"), ["chair"])
        with self.assertRaisesRegex(ValueError, "no physical intervention"):
            self.select("SPLIT")

    def test_shortage_preserves_fixed_slot_without_architecture_fallback(self):
        with self.assertRaisesRegex(ValueError, "original fixed slot"):
            self.select("REPLACE", {name: mask for name, mask in
                                    self.masks.items() if name in
                                    ("wall", "painting")})
        with self.assertRaisesRegex(ValueError, "original fixed slot"):
            self.select("RELINK", {"wall": self.masks["wall"],
                                   "painting": self.masks["painting"]})

    def test_contract_drift_fails_before_target_ranking(self):
        changed = dict(self.contract, minimum_mask_pixels=197)
        with self.assertRaisesRegex(ValueError, "source/pose/eligibility"):
            self.select("BIRTH", contract=changed)
        changed = dict(self.contract, relink_requires_moveable_or_pickupable=False)
        with self.assertRaisesRegex(ValueError, "approved v3 semantic"):
            self.select("RELINK", contract=changed)
        changed = dict(self.contract, status="requires_semantic_review_not_executable")
        changed.update({name: None for name in (
            "relink_requires_moveable_or_pickupable",
            "static_authored_asset_lifecycle_policy",
            "non_intervention_typed_region_target_policy",
            "l1_oracle_entity_structure_separation_policy")})
        with self.assertRaisesRegex(ValueError, "not been approved"):
            self.select("BIRTH", contract=changed)

    def test_duplicate_positive_masks_refuse_private_id_tiebreak(self):
        masks = dict(self.masks, copy_of_painting=self.masks["painting"])
        authored = self.authored | {"copy_of_painting"}
        self.metadata["copy_of_painting"] = {
            "position": {"x": 4, "y": 0, "z": 0}}
        with self.assertRaisesRegex(ValueError, "indistinguishable public geometry"):
            select_private_targets_at_fixed_pose(
                "BIRTH", masks, self.metadata, authored,
                contract=self.contract)
        del self.metadata["copy_of_painting"]
        self.assertEqual(select_private_targets_at_fixed_pose(
            "BIRTH", masks, self.metadata, authored,
            contract=self.contract), ["painting"])


if __name__ == "__main__":
    unittest.main()
