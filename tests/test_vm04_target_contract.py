"""V3 target choices cannot silently turn a proposal into generation."""

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from vsmt.vm04_target_contract import validate_target_boundary_proposal


class TargetContractTests(unittest.TestCase):
    def setUp(self):
        self.value = json.loads((ROOT / "configs/vsmt/vm04_target_boundary_proposal_v3.json")
                                .read_text(encoding="utf-8"))

    def test_proposal_is_closed_and_pins_pose_without_private_reselection(self):
        self.assertFalse(validate_target_boundary_proposal(self.value)[
            "generation_authorized"])
        changed = dict(self.value, private_asset_membership_may_affect_pose=True)
        with self.assertRaisesRegex(ValueError, "source/pose/eligibility"):
            validate_target_boundary_proposal(changed)
        changed = dict(self.value, generation_authorized=True)
        with self.assertRaisesRegex(ValueError, "cannot run"):
            validate_target_boundary_proposal(changed)

    def test_probe_only_requires_explicit_semantics_and_still_blocks_generation(self):
        frozen = dict(self.value, status="frozen_target_probe_only",
                      target_capability_probe_authorized=True)
        with self.assertRaisesRegex(ValueError, "explicit semantic"):
            validate_target_boundary_proposal(frozen)
        frozen.update({
            "relink_requires_moveable_or_pickupable": True,
            "static_authored_asset_lifecycle_policy":
                "exclude_static_assets_from_physical_lifecycle_targets",
            "l1_oracle_entity_structure_separation_policy":
                "author_assets_as_anonymous_entity_regions_architecture_as_public_structure_only",
        })
        self.assertFalse(validate_target_boundary_proposal(frozen)[
            "generation_authorized"])
        frozen["generation_authorized"] = True
        with self.assertRaisesRegex(ValueError, "must not open generation"):
            validate_target_boundary_proposal(frozen)


if __name__ == "__main__":
    unittest.main()
