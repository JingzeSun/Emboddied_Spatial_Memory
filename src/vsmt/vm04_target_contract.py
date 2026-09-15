"""VM-04 v3 proposed target-boundary contract; no execution authorization."""

from __future__ import annotations

import re
from typing import Any, Mapping

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def validate_target_boundary_proposal(value: Mapping[str, Any]) -> dict[str, Any]:
    if type(value) is not dict:
        raise ValueError("VM-04 v3 contract must be a JSON object")

    def require(test: bool, message: str) -> None:
        if not test:
            raise ValueError(message)

    require(value.get("version") == "vsmt-vm04-target-boundary-proposal-v3",
            "wrong target-boundary contract version")
    for name, expected in (
        ("source_v2_scan_receipt_sha256",
         "044fd705e998b1dea9bc62bdd730ff2fc583f9880901131f8927aefb10bb9fd5"),
        ("source_v2_scan_report_sha256",
         "575d34d084864009bc847e4b91ba144279408dc6a28f0a3e8e1433157a089f32"),
        ("source_public_episode_manifest_sha256",
         "403a7039cea8d8097fca1344d0041bc021ee6a231cfbede38066e690ab1bf406"),
        ("source_private_episode_manifest_sha256",
         "cb8e05aea4da7f92b9463adf411986e0183f8a6660217a4bd08f6b5ac36ecaa4"),
        ("fixed_source_house_ids", ["train:004270", "train:008243"]),
        ("fixed_family_ids", ["audit-family:00", "audit-family:01"]),
        ("fixed_slots_per_family", 18),
        ("minimum_position_spacing_m", 1.0),
        ("pose_source",
         "reuse_v2_frozen_spaced_poses_without_target_driven_reselection"),
        ("private_asset_membership_may_affect_pose", False),
        ("trusted_private_target_boundary",
         "recursive_author_house_objects_ids_intersect_current_metadata_objects_with_finite_position"),
        ("private_target_rank",
         "existing_anonymous_mask_geometry_order_after_trusted_eligibility"),
        ("physical_intervention_programs",
         ["BIRTH", "REACTIVATE", "RELINK", "RETRACT", "REPLACE"]),
        ("minimum_qualified_visible_assets_for_replace", 2),
        ("minimum_mask_pixels", 196),
        ("target_repeat_policy",
         "report_only_no_target_pose_or_house_reselection"),
        ("failed_search_replacement_house_allowed", False),
        ("asset_visibility_shortage_policy",
         "record_original_fixed_slot_failure_no_wrap_or_replacement"),
    ):
        require(type(value.get(name)) is type(expected) and value[name] == expected,
                "frozen v3 source/pose/eligibility policy changed: " + name)
    for name, digest in value.items():
        if name.endswith("_sha256"):
            require(type(digest) is str and HEX64.fullmatch(digest) is not None,
                    "v3 SHA-256 field must be 64 lowercase hex characters: " + name)
    require(value["training_authorized"] is False,
            "v3 target proposal never authorizes training")
    choices = ("relink_requires_moveable_or_pickupable",
               "static_authored_asset_lifecycle_policy",
               "non_intervention_typed_region_target_policy",
               "l1_oracle_entity_structure_separation_policy")
    if value.get("status") == "requires_semantic_review_not_executable":
        require(all(value.get(name) is None for name in choices),
                "proposed v3 semantic fields must stay unresolved")
        require(value["target_capability_probe_authorized"] is False and
                value["generation_authorized"] is False,
                "proposed v3 cannot run physical probes or generation")
    elif value.get("status") in ("approved_semantics_implementation_only",
                                  "frozen_target_probe_only"):
        require(value["relink_requires_moveable_or_pickupable"] is True and
                value["static_authored_asset_lifecycle_policy"] ==
                    "allow_visibility_lifecycle_if_action_poststate_and_memory_history_verified" and
                value["non_intervention_typed_region_target_policy"] ==
                    "public_typed_region_evidence_no_simulator_action_target" and
                value["l1_oracle_entity_structure_separation_policy"] ==
                    "author_assets_as_anonymous_entity_regions_architecture_as_public_structure_only",
                "approved v3 semantic/source choices changed")
        if value["status"] == "approved_semantics_implementation_only":
            require(value["target_capability_probe_authorized"] is False and
                    value["generation_authorized"] is False,
                    "approved v3 implementation must not run probe or generation")
        else:
            require(value["target_capability_probe_authorized"] is True and
                    value["generation_authorized"] is False,
                    "v3 target probe gate must not open generation")
    else:
        raise ValueError("unknown v3 target-boundary status")
    return dict(value)
