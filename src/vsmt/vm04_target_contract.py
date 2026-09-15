"""VM-04 v3 proposed target-boundary contract; no execution authorization."""

from __future__ import annotations

from typing import Any, Mapping


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
    elif value.get("status") == "frozen_target_probe_only":
        require(value["relink_requires_moveable_or_pickupable"] is True and
                value["static_authored_asset_lifecycle_policy"] in (
                    "allow_visibility_lifecycle_if_simulator_action_and_poststate_verified",
                    "exclude_static_assets_from_physical_lifecycle_targets") and
                value["l1_oracle_entity_structure_separation_policy"] in (
                    "author_assets_as_anonymous_entity_regions_architecture_as_public_structure_only",
                    "separate_l1_oracle_entity_and_structure_regions_both_anonymous_no_ids"),
                "frozen v3 needs explicit semantic/source choices")
        require(value["non_intervention_typed_region_target_policy"] in (
                    "public_typed_region_evidence_no_simulator_action_target",
                    "l1_oracle_private_segmentation_diagnostic_only_no_deployment_target"),
                "frozen v3 needs explicit semantic/source choices")
        require(value["target_capability_probe_authorized"] is True and
                value["generation_authorized"] is False,
                "v3 target probe gate must not open generation")
    else:
        raise ValueError("unknown v3 target-boundary status")
    return dict(value)
