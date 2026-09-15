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

    def test_approved_semantics_are_closed_and_pin_pose(self):
        self.assertFalse(validate_target_boundary_proposal(self.value)[
            "generation_authorized"])
        changed = dict(self.value, private_asset_membership_may_affect_pose=True)
        with self.assertRaisesRegex(ValueError, "source/pose/eligibility"):
            validate_target_boundary_proposal(changed)
        changed = dict(self.value, generation_authorized=True)
        with self.assertRaisesRegex(ValueError, "must not run"):
            validate_target_boundary_proposal(changed)

    def test_proposal_requires_null_and_probe_only_still_blocks_generation(self):
        proposal = dict(self.value, status="requires_semantic_review_not_executable")
        with self.assertRaisesRegex(ValueError, "must stay unresolved"):
            validate_target_boundary_proposal(proposal)
        proposal.update({name: None for name in (
            "relink_requires_moveable_or_pickupable",
            "static_authored_asset_lifecycle_policy",
            "non_intervention_typed_region_target_policy",
            "l1_oracle_entity_structure_separation_policy")})
        validate_target_boundary_proposal(proposal)
        frozen = dict(self.value, status="frozen_target_probe_only",
                      target_capability_probe_authorized=True)
        self.assertFalse(validate_target_boundary_proposal(frozen)[
            "generation_authorized"])
        alternative = dict(frozen,
            l1_oracle_entity_structure_separation_policy=
                "separate_l1_oracle_entity_and_structure_regions_both_anonymous_no_ids")
        with self.assertRaisesRegex(ValueError, "approved v3 semantic"):
            validate_target_boundary_proposal(alternative)
        frozen["generation_authorized"] = True
        with self.assertRaisesRegex(ValueError, "must not open generation"):
            validate_target_boundary_proposal(frozen)

    def test_new_contract_rejects_malformed_manifest_and_numeric_drift(self):
        bad = dict(self.value, source_public_episode_manifest_sha256=
                   self.value["source_public_episode_manifest_sha256"] + "f")
        with self.assertRaisesRegex(ValueError, "source/pose/eligibility"):
            validate_target_boundary_proposal(bad)
        bad = dict(self.value, extra_sha256="f" * 65)
        with self.assertRaisesRegex(ValueError, "64 lowercase hex"):
            validate_target_boundary_proposal(bad)
        bad = dict(self.value, minimum_mask_pixels=197)
        with self.assertRaisesRegex(ValueError, "source/pose/eligibility"):
            validate_target_boundary_proposal(bad)
        bad = dict(self.value, target_capability_probe_authorized=True)
        with self.assertRaisesRegex(ValueError, "must not run"):
            validate_target_boundary_proposal(bad)


if __name__ == "__main__":
    unittest.main()
