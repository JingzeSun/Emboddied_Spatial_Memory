"""Pure contracts for the VM-04 two-house development audit.

The functions here plan and validate source inventory, house selection,
episode slots, public seals, and post-seal strict recall.  They never open a
dataset, launch AI2-THOR, load private files, or write to disk; those effects
belong to the reviewed ops entrypoint.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import hmac
import math
import re
from typing import Any, Mapping, Sequence

from cpmt.hashing import canonical_json, clone_json


INVENTORY_SCHEMA = "vsmt-vm04-two-house-source-inventory-v1"
SELECTION_SCHEMA = "vsmt-vm04-two-house-selection-v1"
PUBLIC_PLAN_SCHEMA = "vsmt-vm04-two-house-public-plan-v1"
PRIVATE_PLAN_SCHEMA = "vsmt-vm04-two-house-private-plan-v1"
PUBLIC_SEAL_SCHEMA = "vsmt-vm04-two-house-public-seal-v1"
PRIVATE_EVALUATION_SCHEMA = "vsmt-vm04-two-house-private-evaluation-v1"
REGISTERED_PROGRAMS = (
    "NOOP", "BIND", "BIRTH", "REACTIVATE", "RELINK", "RETRACT", "SPLIT",
    "MERGE", "REPLACE",
)
ASSOCIATION_PROFILE_IDS = ("strict", "balanced", "permissive_capacity_upper_bound")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _sealed(value: Mapping[str, Any], field: str) -> dict[str, Any]:
    result = clone_json(dict(value))
    result[field] = _sha256({key: item for key, item in result.items() if key != field})
    return result


def _hex64(value: Any, name: str) -> str:
    _require(type(value) is str and HEX64.fullmatch(value) is not None,
             f"{name} must be a lowercase SHA-256")
    return str(value)


def validate_two_house_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Validate v1 unchanged and the proposed slot-viewpoint v2 separately."""

    record = clone_json(dict(config))
    _require(record.get("version") in {
        "vsmt-vm04-l1-two-house-audit-proposal-v1",
        "vsmt-vm04-l1-two-house-audit-proposal-v2",
    }, "two-house config version is unknown")
    slot_viewpoint_v2 = record["version"].endswith("-v2")
    required = {
        "version", "status", "decision", "engineering_baseline_reviewed_code",
        "engineering_receipt_sha256", "engineering_baseline_blocking_reason",
        "audit_numeric_values_approved", "implementation_authorized",
        "source_inventory_authorized", "generation_authorized",
        "private_audit_authorized", "training_authorized",
        "validation_effect_authorized", "confirmation_authorized", "scope",
        "source_inventory_proposal", "family_selection_proposal",
        "generator_initial_viewpoint", "source_house_schema_compatibility",
        "audit_only_association_profiles",
        "audit_only_lifecycle_and_capacity_values", "two_layer_execution_proposal",
        "completion_and_failure_policy", "resource_and_worker_proposal",
        "required_receipts", "implementation_required_before_any_run",
        "still_blocked",
    }
    _require(required <= record.keys(), "two-house config is missing required fields")
    _require(record["audit_numeric_values_approved"] is True,
             "D-144 audit numeric values are not approved")
    _require(record["implementation_authorized"] is True,
             "two-house implementation is not authorized")
    _require(record["status"] in {
        "approved_for_implementation_not_executable",
        "inventory_executable_generation_blocked",
        "generation_executable",
    }, "two-house status is unknown")
    for name in (
        "source_inventory_authorized", "generation_authorized",
        "private_audit_authorized", "training_authorized",
        "validation_effect_authorized", "confirmation_authorized",
    ):
        _require(type(record[name]) is bool, f"{name} must be boolean")
    _hex64(record["engineering_receipt_sha256"], "engineering_receipt_sha256")
    reviewed = record["engineering_baseline_reviewed_code"]
    _require(type(reviewed) is str and re.fullmatch(r"[0-9a-f]{40}", reviewed) is not None,
             "engineering baseline must be a full commit")

    source = record["source_inventory_proposal"]
    _require(source["source"] == "ProcTHOR-10K" and source["author_partition"] == "train",
             "two-house source must remain ProcTHOR-10K author train")
    _require(source["data_release_tag"] == "0.1.2",
             "two-house source release changed")
    _require(source["house_selection_may_not_share_a_run_with_manifest_freezing"] is True,
             "inventory and house selection must remain separate runs")

    family = record["family_selection_proposal"]
    expected_family = {
        "audit_family_count": 2, "programs_per_family": 9,
        "replicates_per_program_per_family": 2, "episodes_per_family": 18,
        "total_episodes": 36, "observations_per_episode": 32,
        "total_observations": 1152,
        "decision_observation_index_zero_based": 24,
    }
    for name, expected in expected_family.items():
        _require(family.get(name) == expected, f"frozen family value changed: {name}")
    _require(family["public_prefix_indices_inclusive"] == [0, 24]
             and family["future_private_indices_inclusive"] == [25, 31],
             "public/private observation boundary changed")
    _require(family["failed_family_or_episode_replacement"] is False,
             "failed families or episodes may not be replaced")

    viewpoint = record["generator_initial_viewpoint"]
    _require(viewpoint["reachable_position_source"] == "AI2-THOR_GetReachablePositions"
             and viewpoint["yaw_degrees"] == [0, 90, 180, 270]
             and viewpoint["horizon_degrees"] == 0,
             "generator initial viewpoint scan changed")
    _require(viewpoint["minimum_anonymous_mask_pixels"] == 196
             and viewpoint["minimum_eligible_anonymous_masks"] == 2,
             "generator anonymous visibility threshold changed")
    if slot_viewpoint_v2:
        _require({
            "family_ranked_physical_viewpoints_and_sha256",
            "slot_rank_index_pose_and_viewpoint_receipt_sha256",
            "private_capability_and_failed_intervention_diagnostic_sha256",
        } <= set(record["required_receipts"]),
                 "v2 viewpoint/diagnostic receipts are missing")
        _require(viewpoint["selection_rule"] ==
                 "rank_physical_object_mask_support_then_pose_slot_index",
                 "v2 viewpoint rule changed")
        _require(viewpoint["search_once_per_house_family"] is True
                 and viewpoint["reuse_frozen_pose_for_all_family_slots"] is False
                 and viewpoint["slot_pose_rule"] == "rank_index_equals_zero_based_slot"
                 and viewpoint["insufficient_ranked_poses"] ==
                 "fail_fixed_slot_without_wraparound_or_house_replacement"
                 and viewpoint["physical_object_filter"] ==
                 "instance_masks_intersection_metadata_objects"
                 and viewpoint["minimum_eligible_mask_semantics"] ==
                 "physical_objects_only"
                 and viewpoint["unique_target_sets_required"] is None
                 and viewpoint["additional_quality_floor"] is None,
                 "v2 slot-viewpoint contract changed")
    else:
        _require(viewpoint["selection_rule"] == (
            "maximize_eligible_mask_count_then_total_eligible_pixels_then_"
            "lexicographic_x_y_z_yaw"
        ), "generator initial viewpoint selection rule changed")
        _require(viewpoint["search_once_per_house_family"] is True
                 and viewpoint["reuse_frozen_pose_for_all_family_slots"] is True,
                 "generator viewpoint must be frozen once per family")
    _require(viewpoint["private_instance_id_or_class_may_affect_pose"] is False
             and viewpoint["future_or_program_result_may_affect_pose"] is False
             and viewpoint["failed_search_replacement_house_allowed"] is False,
             "generator viewpoint anti-selection guard changed")

    compatibility = record["source_house_schema_compatibility"]
    _require(compatibility["source_schema"] == "0.0.1"
             and compatibility["simulator_required_schema"] == "1.0.0",
             "source house schema compatibility changed")
    _require(compatibility["upgrade_semantics_commit"] ==
             "53d5bd4c8c96a699e6a615dc390abb670cc9d353",
             "source house upgrade semantics commit changed")
    _require(compatibility["upgrade_semantics_source"] ==
             "allenai/procthor procthor/utils/upgrade_house_version.py"
             and compatibility["asset_dimensions_source"] ==
             "installed_pinned_procthor_asset-database.json",
             "source house schema compatibility source changed")
    for name in (
        "source_record_mutation_allowed",
        "upgrade_may_read_program_future_or_private_evaluation",
    ):
        _require(compatibility[name] is False, f"schema compatibility guard changed: {name}")
    for name in (
        "upgraded_house_must_be_deterministic",
        "controller_initial_event_success_required",
        "controller_initial_objects_must_be_nonempty",
        "bootstrap_pose_is_not_the_selected_public_start_pose",
    ):
        _require(compatibility[name] is True, f"schema compatibility guard changed: {name}")
    _require(compatibility["reachable_position_bootstrap_pose_source"] ==
             "upgraded_house_metadata_agent",
             "reachable-position bootstrap source changed")

    values = record["audit_only_lifecycle_and_capacity_values"]
    expected_values = {
        "support_envelope_reliability_threshold": 0.9,
        "support_envelope_margin_m_per_side": 0.02,
        "opportunity_reliability_threshold": 0.9,
        "minimum_consecutive_missed_opportunities": 3,
        "candidate_capacity_replay_values": [16, 32, 64],
        "maximum_ambiguous_relation_variables": 6,
        "maximum_relation_variants": 729,
        "maximum_total_incident_edges": 32,
    }
    for name, expected in expected_values.items():
        _require(values.get(name) == expected, f"frozen audit value changed: {name}")
    _require(values["support_margin_sensitivity_report_m_per_side"] == [0.02, 0.05],
             "support margin sensitivity changed")
    for name in (
        "support_margin_may_be_reduced_to_improve_yield",
        "opportunity_reliability_threshold_may_be_reduced_to_improve_yield",
        "missed_opportunity_count_may_be_reduced_to_improve_yield",
    ):
        _require(values[name] is False, f"anti-yield guard changed: {name}")

    resources = record["resource_and_worker_proposal"]
    _require(resources["simulator_house_family_workers"] == 2,
             "two family workers are required")
    _require(resources["GPU_descriptor_consumers"] == 1,
             "one deterministic descriptor consumer is required")
    _require(resources["training_steps"] == 0
             and resources["new_asset_download_bytes"] == 0,
             "audit may not train or download assets")
    _require(resources["overwrite_existing_stage"] is False,
             "audit stages may not be overwritten")
    return record


def assert_two_house_action_authorized(
    config: Mapping[str, Any], *, action: str,
) -> dict[str, Any]:
    """Fail closed unless the separately reviewed action bit is open."""

    record = validate_two_house_config(config)
    fields = {
        "inventory": "source_inventory_authorized",
        "select": "source_inventory_authorized",
        "generate": "generation_authorized",
        "private-eval": "private_audit_authorized",
    }
    _require(action in fields, f"unknown two-house action {action!r}")
    _require(record[fields[action]] is True, f"two-house {action} is not authorized")
    if action in {"inventory", "select"}:
        _require(record["status"] in {
            "inventory_executable_generation_blocked", "generation_executable",
        }, "inventory status gate is closed")
    if action in {"generate", "private-eval"}:
        _require(record["status"] == "generation_executable",
                 "generation status gate is closed")
        source = record["source_inventory_proposal"]
        for name in (
            "source_manifest_sha256", "license_snapshot_sha256",
            "eligible_house_ids_sha256",
        ):
            _hex64(source.get(name), name)
        ids = source.get("audit_house_ids")
        _require(type(ids) is list and len(ids) == 2
                 and all(type(item) is str and item for item in ids)
                 and len(set(ids)) == 2, "exactly two audit house IDs must be frozen")
        _hex64(record["family_selection_proposal"].get(
            "private_program_assignment_salt_sha256"
        ), "private_program_assignment_salt_sha256")
    if action == "private-eval":
        _require(record["generation_authorized"] is True,
                 "private evaluation requires generation authorization")
    _require(record["training_authorized"] is False
             and record["confirmation_authorized"] is False,
             "two-house audit may not authorize training or confirmation")
    return record


def make_source_inventory(
    houses: Sequence[Mapping[str, Any]], *, source_release_commit: str,
    license_files: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Seal mechanically parsed author-train rows without selecting houses."""

    _require(type(houses) in (list, tuple) and houses,
             "source inventory needs at least one house")
    _require(re.fullmatch(r"[0-9a-f]{40}", source_release_commit) is not None,
             "source release commit must be a full commit")
    rows: list[dict[str, Any]] = []
    for index, raw in enumerate(houses):
        _require(type(raw) is dict, f"houses[{index}] must be an object")
        _require(set(raw) == {
            "house_id", "source_file_sha256", "source_record_sha256",
            "source_locator",
        }, f"houses[{index}] has unexpected fields")
        house_id = raw["house_id"]
        _require(type(house_id) is str and house_id,
                 f"houses[{index}].house_id must be nonempty")
        rows.append({
            "house_id": house_id,
            "source_file_sha256": _hex64(
                raw["source_file_sha256"], "source_file_sha256"
            ),
            "source_record_sha256": _hex64(
                raw["source_record_sha256"], "source_record_sha256"
            ),
            "source_locator": clone_json(raw["source_locator"]),
        })
    rows.sort(key=lambda row: row["house_id"])
    ids = [row["house_id"] for row in rows]
    _require(len(ids) == len(set(ids)), "eligible house IDs must be unique")
    licenses = sorted(
        [clone_json(dict(item)) for item in license_files],
        key=lambda item: str(item.get("name")),
    )
    _require(licenses and all(set(item) == {"name", "sha256", "bytes"}
                              for item in licenses),
             "license snapshot rows are malformed")
    for item in licenses:
        _require(type(item["name"]) is str and item["name"],
                 "license name must be nonempty")
        _hex64(item["sha256"], "license sha256")
        _require(type(item["bytes"]) is int and item["bytes"] >= 0,
                 "license byte count must be nonnegative")
    public_rows = [{key: value for key, value in row.items() if key != "source_locator"}
                   for row in rows]
    result = {
        "schema_version": INVENTORY_SCHEMA,
        "source_release_commit": source_release_commit,
        "author_partition": "train",
        "house_count": len(rows),
        "source_manifest_sha256": _sha256(public_rows),
        "eligible_house_ids_sha256": _sha256(ids),
        "license_snapshot_sha256": _sha256(licenses),
        "eligible_house_ids": ids,
        "houses": rows,
        "license_files": licenses,
        "selection_performed": False,
        "generation_performed": False,
        "private_data_opened": False,
    }
    return _sealed(result, "inventory_sha256")


def validate_source_inventory(inventory: Mapping[str, Any]) -> dict[str, Any]:
    record = clone_json(dict(inventory))
    expected = {
        "schema_version", "source_release_commit", "author_partition",
        "house_count", "source_manifest_sha256", "eligible_house_ids_sha256",
        "license_snapshot_sha256", "eligible_house_ids", "houses",
        "license_files", "selection_performed", "generation_performed",
        "private_data_opened", "inventory_sha256",
    }
    _require(set(record) == expected, "source inventory has unexpected fields")
    _require(record["schema_version"] == INVENTORY_SCHEMA,
             "wrong source inventory schema")
    _require(record == make_source_inventory(
        record["houses"], source_release_commit=record["source_release_commit"],
        license_files=record["license_files"],
    ), "source inventory digest or ordering changed")
    return record


def select_audit_houses(
    inventory: Mapping[str, Any], *, split_seed: int, family_count: int = 2,
) -> dict[str, Any]:
    """Select houses only from an already sealed inventory."""

    source = validate_source_inventory(inventory)
    _require(type(split_seed) is int and split_seed >= 0,
             "split_seed must be nonnegative")
    _require(type(family_count) is int and family_count == 2,
             "the development audit requires exactly two houses")
    digest = source["source_manifest_sha256"]
    ranked = sorted(source["eligible_house_ids"], key=lambda house_id: (
        hashlib.sha256(f"{digest}|{split_seed}|{house_id}".encode("utf-8")).hexdigest(),
        house_id,
    ))
    _require(len(ranked) >= family_count, "not enough eligible houses")
    selected = ranked[:family_count]
    result = {
        "schema_version": SELECTION_SCHEMA,
        "inventory_sha256": source["inventory_sha256"],
        "source_manifest_sha256": digest,
        "eligible_house_ids_sha256": source["eligible_house_ids_sha256"],
        "split_seed": split_seed,
        "ordering_rule": "ascending_sha256_of_source_manifest_sha256_split_seed_and_house_id",
        "audit_house_ids": selected,
        "rank_commitments": [
            hashlib.sha256(
                f"{digest}|{split_seed}|{house_id}".encode("utf-8")
            ).hexdigest() for house_id in selected
        ],
        "selection_input_is_inventory_only": True,
        "generation_performed": False,
        "private_data_opened": False,
    }
    return _sealed(result, "selection_sha256")


def validate_house_selection(
    selection: Mapping[str, Any], *, inventory: Mapping[str, Any],
) -> dict[str, Any]:
    source = validate_source_inventory(inventory)
    record = clone_json(dict(selection))
    expected = select_audit_houses(
        source, split_seed=record.get("split_seed"), family_count=2,
    )
    _require(record == expected, "house selection is not reproducible from inventory")
    return record


def make_episode_plans(
    selection: Mapping[str, Any], *, inventory: Mapping[str, Any],
    assignment_salt: bytes, config_version: str,
) -> dict[str, dict[str, Any]]:
    """Create public label-free slots and a separate private assignment plan."""

    selected = validate_house_selection(selection, inventory=inventory)
    _require(type(assignment_salt) is bytes and len(assignment_salt) >= 32,
             "assignment_salt must contain at least 32 bytes")
    _require(type(config_version) is str and config_version,
             "config_version must be nonempty")
    public_rows: list[dict[str, Any]] = []
    private_rows: list[dict[str, Any]] = []
    for family_index, house_id in enumerate(selected["audit_house_ids"]):
        family_id = f"audit-family:{family_index:02d}"
        assignments = [(program, replicate) for program in REGISTERED_PROGRAMS
                       for replicate in range(2)]
        assignments.sort(key=lambda item: hmac.new(
            assignment_salt,
            f"{family_id}|{item[0]}|{item[1]}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest())
        for slot, (program, replicate) in enumerate(assignments):
            episode_id = "audit-episode:" + hashlib.sha256(
                f"{config_version}|{family_id}|{slot}".encode("utf-8")
            ).hexdigest()[:24]
            public_rows.append({
                "episode_id": episode_id,
                "family_id": family_id,
                "slot": slot,
                "observation_count": 32,
                "decision_observation_index_zero_based": 24,
            })
            private_rows.append({
                "episode_id": episode_id,
                "family_id": family_id,
                "source_house_id": house_id,
                "program": program,
                "replicate": replicate,
            })
    public = _sealed({
        "schema_version": PUBLIC_PLAN_SCHEMA,
        "config_version": config_version,
        "selection_sha256": selected["selection_sha256"],
        "family_count": 2,
        "episode_count": 36,
        "episodes": public_rows,
        "program_assignment_exposed": False,
    }, "manifest_sha256")
    private = _sealed({
        "schema_version": PRIVATE_PLAN_SCHEMA,
        "config_version": config_version,
        "public_manifest_sha256": public["manifest_sha256"],
        "assignment_salt_sha256": hashlib.sha256(assignment_salt).hexdigest(),
        "episode_count": 36,
        "assignments": private_rows,
    }, "manifest_sha256")
    return validate_episode_plans({"public": public, "private": private})


def validate_episode_plans(
    plans: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    _require(set(plans) == {"public", "private"},
             "episode plans require public and private files")
    public = validate_public_episode_plan(plans["public"])
    private = clone_json(dict(plans["private"]))
    _require(private.get("schema_version") == PRIVATE_PLAN_SCHEMA,
             "wrong episode plan schema")
    for record in (private,):
        _hex64(record.get("manifest_sha256"), "manifest_sha256")
        _require(record["manifest_sha256"] == _sha256({
            key: value for key, value in record.items() if key != "manifest_sha256"
        }), "episode manifest digest mismatch")
    _require(public["episode_count"] == private["episode_count"] == 36,
             "two-house plan must have 36 episodes")
    _require(public["family_count"] == 2 and public["program_assignment_exposed"] is False,
             "public plan leaked assignment or changed family count")
    _require(private["public_manifest_sha256"] == public["manifest_sha256"],
             "private plan is bound to another public plan")
    public_rows = public["episodes"]
    private_rows = private["assignments"]
    _require(len(public_rows) == len(private_rows) == 36,
             "episode row count mismatch")
    public_ids = [row["episode_id"] for row in public_rows]
    private_ids = [row["episode_id"] for row in private_rows]
    _require(public_ids == private_ids and len(set(public_ids)) == 36,
             "public/private episode identities differ")
    _require(all(set(row) == {
        "episode_id", "family_id", "slot", "observation_count",
        "decision_observation_index_zero_based",
    } for row in public_rows), "public episode rows expose unexpected fields")
    _require(all(row["observation_count"] == 32
                 and row["decision_observation_index_zero_based"] == 24
                 for row in public_rows), "episode observation shape changed")
    counts = Counter((row["family_id"], row["program"])
                     for row in private_rows)
    _require(set(row["program"] for row in private_rows) == set(REGISTERED_PROGRAMS),
             "private plan does not cover all programs")
    _require(all(counts[(f"audit-family:{family:02d}", program)] == 2
                 for family in range(2) for program in REGISTERED_PROGRAMS),
             "each family must contain two replicates of every program")
    return {"public": public, "private": private}


def validate_public_episode_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the label-free plan without opening its private companion."""

    public = clone_json(dict(plan))
    expected = {
        "schema_version", "config_version", "selection_sha256", "family_count",
        "episode_count", "episodes", "program_assignment_exposed", "manifest_sha256",
    }
    _require(set(public) == expected, "public episode plan has unexpected fields")
    _require(public.get("schema_version") == PUBLIC_PLAN_SCHEMA,
             "wrong public episode plan schema")
    _hex64(public.get("manifest_sha256"), "manifest_sha256")
    _require(public["manifest_sha256"] == _sha256({
        key: value for key, value in public.items() if key != "manifest_sha256"
    }), "public episode manifest digest mismatch")
    rows = public["episodes"]
    _require(public["episode_count"] == 36 and public["family_count"] == 2,
             "public episode plan shape changed")
    _require(public["program_assignment_exposed"] is False,
             "public episode plan exposes assignments")
    _require(type(rows) is list and len(rows) == 36
             and len({row.get("episode_id") for row in rows}) == 36,
             "public episode plan needs 36 unique rows")
    _require(all(set(row) == {
        "episode_id", "family_id", "slot", "observation_count",
        "decision_observation_index_zero_based",
    } for row in rows), "public episode rows expose unexpected fields")
    _require(all(row["observation_count"] == 32
                 and row["decision_observation_index_zero_based"] == 24
                 for row in rows), "public episode observation shape changed")
    return public


def make_public_seal(
    episode_rows: Sequence[Mapping[str, Any]], *, public_manifest_sha256: str,
    capacities: Sequence[int], worker_completion_order: Sequence[str],
) -> dict[str, Any]:
    """Seal canonical public audit rows before any private label is opened."""

    _hex64(public_manifest_sha256, "public_manifest_sha256")
    _require(list(capacities) == [16, 32, 64], "capacity replay values changed")
    rows = [clone_json(dict(row)) for row in episode_rows]
    rows.sort(key=lambda row: row.get("episode_id", ""))
    _require(len(rows) == 36 and len({row.get("episode_id") for row in rows}) == 36,
             "public seal must contain 36 unique episode rows")
    forbidden = {"program", "reference", "teacher", "instance_id", "source_house_id"}
    for index, row in enumerate(rows):
        _require(not (forbidden & set(row)),
                 f"public audit row {index} contains a private field")
        profiles = row.get("profiles")
        _require(type(profiles) is dict and set(profiles) == set(ASSOCIATION_PROFILE_IDS),
                 f"public audit row {index} lacks the frozen association profiles")
        for profile in profiles.values():
            _require(type(profile) is dict and set(map(int, profile.get("catalogs", {})))
                     == {16, 32, 64},
                     f"public audit row {index} lacks all capacity replays")
    result = {
        "schema_version": PUBLIC_SEAL_SCHEMA,
        "public_manifest_sha256": public_manifest_sha256,
        "capacity_replay_values": [16, 32, 64],
        "episode_count": 36,
        "episodes": rows,
        "worker_completion_order": list(worker_completion_order),
        "canonical_episode_digest": _sha256(rows),
        "canonical_digest_independent_of_worker_completion_order": True,
        "private_data_opened": False,
        "teacher_computed": False,
        "method_predictions_computed": False,
    }
    return _sealed(result, "public_seal_sha256")


def evaluate_private_recall(
    public_seal: Mapping[str, Any], private_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Score strict canonical keys only after a valid public seal exists."""

    seal = clone_json(dict(public_seal))
    _require(seal.get("schema_version") == PUBLIC_SEAL_SCHEMA,
             "private evaluation requires a public seal")
    _require(seal.get("public_seal_sha256") == _sha256({
        key: value for key, value in seal.items() if key != "public_seal_sha256"
    }), "public seal digest mismatch")
    _require(seal.get("private_data_opened") is False,
             "public seal must predate private access")
    public_by_id = {row["episode_id"]: row for row in seal["episodes"]}
    rows = [clone_json(dict(row)) for row in private_rows]
    _require(len(rows) == 36 and len({row.get("episode_id") for row in rows}) == 36,
             "private evaluation needs 36 unique terminal rows")
    evaluated: list[dict[str, Any]] = []
    aggregates: dict[str, dict[str, int]] = defaultdict(
        lambda: {"attempted": 0, "constructed": 0, "strict_hits_16": 0,
                 "strict_hits_32": 0, "strict_hits_64": 0}
    )
    for row in sorted(rows, key=lambda item: item["episode_id"]):
        episode_id = row["episode_id"]
        public = public_by_id.get(episode_id)
        _require(public is not None, "private row has no sealed public episode")
        required = {
            "episode_id", "family_id", "program", "replicate", "constructed",
            "construction_failure_reason", "canonical_reference_key_sha256_by_profile",
            "entity_retract_legal_at_margin_0_02",
            "entity_retract_legal_at_margin_0_05",
        }
        _require(set(row) == required, "private evaluation row has unexpected fields")
        _require(row["program"] in REGISTERED_PROGRAMS, "unknown private program")
        constructed = row["constructed"] is True
        references = row["canonical_reference_key_sha256_by_profile"]
        if constructed:
            _require(type(references) is dict and set(references) == set(ASSOCIATION_PROFILE_IDS),
                     "constructed row needs one reference key per profile")
            for profile_id, reference in references.items():
                _hex64(reference, f"canonical_reference_key_sha256_by_profile.{profile_id}")
            _require(row["construction_failure_reason"] is None,
                     "constructed row may not have a failure reason")
        else:
            _require(references is None and type(row["construction_failure_reason"]) is str,
                     "failed construction needs one reason and no reference key")
        hits: dict[str, dict[str, bool | None]] = {}
        for profile_id in ASSOCIATION_PROFILE_IDS:
            hits[profile_id] = {}
            for capacity in (16, 32, 64):
                keys = public["profiles"][profile_id]["catalogs"][str(capacity)][
                    "canonical_candidate_key_sha256s"
                ]
                _require(type(keys) is list and all(
                    type(item) is str and HEX64.fullmatch(item) for item in keys
                ), "public candidate keys are malformed")
                hits[profile_id][str(capacity)] = (
                    None if not constructed else references[profile_id] in keys
                )
        group = aggregates[f"{row['family_id']}|{row['program']}"]
        group["attempted"] += 1
        group["constructed"] += int(constructed)
        for capacity in (16, 32, 64):
            group[f"strict_hits_{capacity}"] += int(
                hits["strict"][str(capacity)] is True
            )
        evaluated.append({
            "episode_id": episode_id,
            "family_id": row["family_id"],
            "program": row["program"],
            "replicate": row["replicate"],
            "constructed": constructed,
            "construction_failure_reason": row["construction_failure_reason"],
            "strict_exact_canonical_reference_program_recall": hits,
            "candidate_miss_reason": {
                profile_id: {
                    str(capacity): (
                        "construction_failed_not_candidate_miss"
                        if not constructed else (
                            None if hits[profile_id][str(capacity)] is True
                            else "exact_canonical_reference_program_absent"
                        )
                    )
                    for capacity in (16, 32, 64)
                }
                for profile_id in ASSOCIATION_PROFILE_IDS
            },
            "entity_RETRACT_legal_candidate_recall": {
                "margin_0_02_m": (
                    hits if row["entity_retract_legal_at_margin_0_02"] is True else None
                ),
                "margin_0_05_m": (
                    hits if row["entity_retract_legal_at_margin_0_05"] is True else None
                ),
            },
        })
    result = {
        "schema_version": PRIVATE_EVALUATION_SCHEMA,
        "public_seal_sha256": seal["public_seal_sha256"],
        "episode_count": 36,
        "episodes": evaluated,
        "by_family_and_program": dict(sorted(aggregates.items())),
        "semantic_equivalence_class_recall": None,
        "teacher_ranking_or_probability_computed": False,
        "method_predictions_or_effects_computed": False,
        "private_opened_after_public_seal": True,
    }
    return _sealed(result, "evaluation_sha256")


def capacity_probe(
    *, free_bytes: int, visible_cpu_count: int, requested_workers: int,
    predicted_wall_seconds: float, predicted_stage_bytes: int,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a fail-closed pre-run resource decision without starting workers."""

    record = validate_two_house_config(config)
    resources = record["resource_and_worker_proposal"]
    for name, value in {
        "free_bytes": free_bytes, "visible_cpu_count": visible_cpu_count,
        "requested_workers": requested_workers, "predicted_stage_bytes": predicted_stage_bytes,
    }.items():
        _require(type(value) is int and value >= 0, f"{name} must be nonnegative")
    _require(type(predicted_wall_seconds) in (int, float)
             and math.isfinite(predicted_wall_seconds)
             and predicted_wall_seconds >= 0, "predicted wall time must be finite")
    ready = bool(
        requested_workers == resources["simulator_house_family_workers"]
        and visible_cpu_count >= requested_workers
        and free_bytes >= resources["minimum_free_data_disk_bytes_before_start"]
        and predicted_stage_bytes <= resources["maximum_stage_bytes"]
    )
    return {
        "requested_workers": requested_workers,
        "actual_workers_required": 2,
        "visible_cpu_count": visible_cpu_count,
        "free_data_disk_bytes": free_bytes,
        "predicted_wall_seconds": float(predicted_wall_seconds),
        "wall_clock_limit_seconds": resources["hard_wall_clock_seconds"],
        "wall_clock_timeout_disabled": resources["hard_wall_clock_seconds"] is None,
        "predicted_stage_bytes": predicted_stage_bytes,
        "ready": ready,
        "generation_started": False,
    }
