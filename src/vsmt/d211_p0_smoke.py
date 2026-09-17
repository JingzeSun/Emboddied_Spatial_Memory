"""D-211 authorization overlay for D-210 route sealing and one raw smoke.

This module does not plan routes and does not touch a simulator.  It binds the
two already audited development houses, validates the twelve caller-supplied
publicly constructed routes and their private starting poses, and limits raw
execution to slot 0.  Adapter materialization, private evaluation, metrics and
the remaining eleven raw episodes stay closed.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any, Mapping, Sequence

from cpmt.hashing import canonical_json, clone_json

from .d210_place_memory import (
    D210Error,
    build_p0_manifests,
    validate_contract as validate_d210_contract,
    validate_route_plan,
)


CONTRACT_SCHEMA = "vsmt-vm04-d211-p0-seal-single-smoke-contract-v1"
ROUTE_BINDING_SCHEMA = "vsmt-vm04-d211-route-execution-binding-v1"
ROUTE_BUNDLE_SCHEMA = "vsmt-vm04-d211-route-bundle-v1"
SEALED_BINDINGS_SCHEMA = "vsmt-vm04-d211-sealed-route-bindings-v1"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class D211Error(D210Error):
    """D-211 scope, source binding, route seal or smoke boundary changed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise D211Error(message)


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _payload_sha(record: Mapping[str, Any], field: str) -> str:
    value = clone_json(dict(record))
    value.pop(field, None)
    return _sha(value)


def _exact(value: Any, keys: set[str], name: str) -> None:
    _require(type(value) is dict and set(value) == keys,
             f"{name} has unexpected fields")


def _hex64(value: Any, name: str) -> str:
    _require(type(value) is str and HEX64.fullmatch(value) is not None,
             f"{name} must be a lowercase SHA-256")
    return value


def _finite(value: Any, name: str) -> float:
    _require(type(value) in {int, float} and math.isfinite(float(value)),
             f"{name} must be finite")
    return float(value)


def validate_d211_contract(
    contract: Mapping[str, Any], *, base_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the user-authorized overlay without treating it as run proof."""

    base = validate_d210_contract(base_contract)
    value = clone_json(dict(contract))
    _exact(value, {
        "schema_version", "decision_id", "status", "reviewed_baseline_commit",
        "expected_reviewed_code_commit", "base_contract", "authorization",
        "source_binding", "route_sealing", "single_slot_smoke",
        "resource_policy",
    }, "D-211 contract")
    _require(value["schema_version"] == CONTRACT_SCHEMA and
             value["decision_id"] == "D-211" and
             value["status"] in {
                 "authorized_scope_implementation_pending_reviewed_commit",
                 "frozen_executable_seal_and_single_slot_smoke",
             } and
             value["reviewed_baseline_commit"] ==
             "8d6bd13158a5cfd56a110460dc5c926015e5b52c",
             "D-211 identity or reviewed baseline changed")
    expected_commit = value["expected_reviewed_code_commit"]
    _require(expected_commit is None or
             (type(expected_commit) is str and
              HEX40.fullmatch(expected_commit) is not None),
             "D-211 reviewed code commit is invalid")
    if value["status"] == "frozen_executable_seal_and_single_slot_smoke":
        _require(expected_commit is not None,
                 "an executable D-211 contract needs a reviewed code commit")
    else:
        _require(expected_commit is None,
                 "the implementation-review D-211 contract cannot pin code")

    base_ref = value["base_contract"]
    _require(base_ref == {
        "relative_path": "configs/vsmt/vm04_d210_dual_layer_p0_v1.json",
        "file_sha256":
            "d93f43b654eac64469aa87d6e9b6542531ab3ab463588bb9a53199fef911b60c",
        "validated_value_sha256": _sha(base),
    }, "D-211 base D-210 binding changed")
    _require(value["authorization"] == {
        "source_house_binding_authorized": True,
        "twelve_route_sealing_authorized": True,
        "single_slot_raw_smoke_authorized": True,
        "twelve_slot_raw_generation_authorized": False,
        "adapter_materialization_authorized": False,
        "private_evaluation_authorized": False,
        "training_authorized": False,
        "validation_authorized": False,
        "confirmation_authorized": False,
    }, "D-211 authorization scope changed")

    source = value["source_binding"]
    _exact(source, {
        "source", "source_release_commit", "source_report_relative_path",
        "source_report_file_sha256", "houses", "reuse_role",
        "replacement_after_route_or_smoke_failure_allowed",
    }, "D-211 source binding")
    _require(source["source"] == "ProcTHOR-10K_train_0.1.2" and
             source["source_release_commit"] ==
             "d54954a81e7126001e552c2d7904ee2e0d49eaae" and
             source["source_report_relative_path"] ==
             "results/vsmt_vm04_root_cause_audit_v1.json" and
             source["source_report_file_sha256"] ==
             "ecf4e6735016db4dea71873193d0a7fbdb606480a18237cb7871129f562ece73" and
             source["reuse_role"] ==
             "already_audited_development_houses_only_not_confirmation" and
             source["replacement_after_route_or_smoke_failure_allowed"] is False,
             "D-211 source provenance changed")
    expected_houses = [
        {"house_slot": 0, "source_house_id": "train:004270",
         "source_record_sha256":
             "79a1cfe6c80e913305cc6d2ea047323bca1d05763b29a162cbef23c76b80026f"},
        {"house_slot": 1, "source_house_id": "train:008243",
         "source_record_sha256":
             "cdbd7bf8e91a6fc3a52b1a92487e22badc234793d23c74c0a59240d43980bea7"},
    ]
    _require(source["houses"] == expected_houses,
             "D-211 fixed development houses changed")

    _require(value["route_sealing"] == {
        "slot_count": 12,
        "complete_action_sequence_required": True,
        "private_initial_pose_required": True,
        "initial_yaw_multiple_degrees": 90.0,
        "reachable_scan_and_public_rgbd_evidence_required": True,
        "future_action_outcome_or_private_reference_allowed": False,
        "all_planned_translation_endpoints_preverified_reachable": True,
        "scenario_role_change_after_failure_allowed": False,
        "route_replacement_after_smoke_outcome_allowed": False,
        "sealed_output_is_immutable": True,
    }, "D-211 route-sealing boundary changed")
    _require(value["single_slot_smoke"] == {
        "slot": 0, "house_slot": 0, "scenario_id": "P01",
        "role": "engineering_only_not_headline_or_effect_evidence",
        "fresh_controller_required": True,
        "simulator_intervention_allowed": False,
        "observation_zero_saved": True,
        "observation_after_every_successful_registered_action_saved": True,
        "failed_action_receipt_and_completed_prefix_retained": True,
        "public_raw_channels": [
            "rgb_uint8_npy", "depth_m_float32_npy",
            "sensor_calibration_json", "frame_digest",
        ],
        "provenance_channels": [
            "complete_sealed_route", "registered_action_requests_and_success",
            "source_record_digest", "worker_terminal_receipt",
        ],
        "forbidden_outputs": [
            "simulator_world_pose", "instance_masks", "reference_place_region",
            "loop_pair_label", "teacher_target", "adapter_packet", "model_metric",
        ],
        "success_condition":
            "observation_count_equals_planned_action_count_plus_one_and_all_registered_actions_succeed",
        "failure_replacement_allowed": False,
    }, "D-211 single-slot smoke boundary changed")
    _require(value["resource_policy"] == {
        "worker_count": 1,
        "single_worker_reason":
            "the_authorized_smoke_contains_exactly_one_execution_unit",
        "wall_clock_timeout_allowed": False,
        "minimum_data_disk_free_bytes": 8589934592,
        "emergency_data_disk_free_bytes": 4294967296,
        "maximum_smoke_output_bytes": 2147483648,
    }, "D-211 resource policy changed")
    _require(base["slot_plan"][0] == {
        "slot": 0, "house_slot": 0, "scenario_id": "P01", "seed": 26091800,
    }, "D-210 slot zero changed under D-211")
    return value


def validate_route_execution_binding(
    binding: Mapping[str, Any], *, route_plan: Mapping[str, Any],
    contract: Mapping[str, Any], base_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the private start pose and public evidence binding of one route."""

    approved = validate_d211_contract(contract, base_contract=base_contract)
    route = validate_route_plan(route_plan, base_contract)
    value = clone_json(dict(binding))
    _exact(value, {
        "schema_version", "slot", "house_slot", "scenario_id",
        "route_plan_sha256", "initial_pose", "reachable_scan_sha256",
        "public_rgbd_route_evidence_sha256",
        "all_planned_translation_endpoints_preverified_reachable",
        "constructed_from_pre_execution_public_evidence_only",
        "future_action_outcome_used", "private_reference_used",
        "execution_binding_sha256",
    }, "D-211 route execution binding")
    _require(value["schema_version"] == ROUTE_BINDING_SCHEMA and
             (value["slot"], value["house_slot"], value["scenario_id"],
              value["route_plan_sha256"]) ==
             (route["slot"], route["house_slot"], route["scenario_id"],
              route["route_plan_sha256"]),
             "route execution binding disagrees with its D-210 route")
    pose = value["initial_pose"]
    _exact(pose, {"x_m", "y_m", "z_m", "yaw_deg", "horizon_deg"},
           "D-211 initial pose")
    for key in pose:
        pose[key] = _finite(pose[key], f"initial pose {key}")
    multiple = approved["route_sealing"]["initial_yaw_multiple_degrees"]
    _require(abs(pose["yaw_deg"] / multiple -
                 round(pose["yaw_deg"] / multiple)) <= 1e-9 and
             pose["horizon_deg"] == 0.0,
             "D-211 initial pose must use an axis-aligned yaw and zero horizon")
    _hex64(value["reachable_scan_sha256"], "reachable scan digest")
    _hex64(value["public_rgbd_route_evidence_sha256"],
           "public RGB-D route evidence digest")
    _require(value["all_planned_translation_endpoints_preverified_reachable"]
             is True and
             value["constructed_from_pre_execution_public_evidence_only"] is True and
             value["future_action_outcome_used"] is False and
             value["private_reference_used"] is False,
             "D-211 route evidence boundary changed")
    _require(value["execution_binding_sha256"] ==
             _payload_sha(value, "execution_binding_sha256"),
             "D-211 route execution binding digest mismatch")
    return value


def seal_route_execution_binding(
    *, route_plan: Mapping[str, Any], initial_pose: Mapping[str, Any],
    reachable_scan_sha256: str, public_rgbd_route_evidence_sha256: str,
    contract: Mapping[str, Any], base_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Seal one route's private start pose after public route construction."""

    route = validate_route_plan(route_plan, base_contract)
    value = {
        "schema_version": ROUTE_BINDING_SCHEMA,
        "slot": route["slot"], "house_slot": route["house_slot"],
        "scenario_id": route["scenario_id"],
        "route_plan_sha256": route["route_plan_sha256"],
        "initial_pose": clone_json(dict(initial_pose)),
        "reachable_scan_sha256": reachable_scan_sha256,
        "public_rgbd_route_evidence_sha256":
            public_rgbd_route_evidence_sha256,
        "all_planned_translation_endpoints_preverified_reachable": True,
        "constructed_from_pre_execution_public_evidence_only": True,
        "future_action_outcome_used": False,
        "private_reference_used": False,
    }
    value["execution_binding_sha256"] = _payload_sha(
        value, "execution_binding_sha256")
    return validate_route_execution_binding(
        value, route_plan=route, contract=contract,
        base_contract=base_contract)


def build_sealed_route_batch(
    *, rows: Sequence[Mapping[str, Any]], contract: Mapping[str, Any],
    base_contract: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Create D-210 public/private manifests plus twelve private bindings."""

    approved = validate_d211_contract(contract, base_contract=base_contract)
    _require(type(rows) in {list, tuple} and len(rows) == 12,
             "D-211 route bundle must contain twelve rows")
    routes: list[dict[str, Any]] = []
    bindings: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        _exact(row, {"route_plan", "execution_binding"},
               f"D-211 route row {index}")
        route = validate_route_plan(row["route_plan"], base_contract)
        binding = validate_route_execution_binding(
            row["execution_binding"], route_plan=route, contract=approved,
            base_contract=base_contract)
        routes.append(route)
        bindings.append(binding)
    _require([route["slot"] for route in routes] == list(range(12)),
             "D-211 route rows must be ordered unique slots 0 through 11")
    public, private = build_p0_manifests(
        source_houses=approved["source_binding"]["houses"],
        route_plans=routes, contract=base_contract)
    binding_manifest = {
        "schema_version": SEALED_BINDINGS_SCHEMA,
        "public_manifest_sha256": public["manifest_sha256"],
        "private_manifest_sha256": private["manifest_sha256"],
        "binding_count": 12,
        "bindings": bindings,
        "route_replacement_after_smoke_outcome_allowed": False,
    }
    binding_manifest["manifest_sha256"] = _payload_sha(
        binding_manifest, "manifest_sha256")
    return public, private, binding_manifest


def assert_single_slot_smoke_authorized(
    contract: Mapping[str, Any], *, base_contract: Mapping[str, Any],
    reviewed_code_commit: str,
) -> dict[str, Any]:
    """Open only slot 0 after this implementation has a reviewed commit."""

    approved = validate_d211_contract(contract, base_contract=base_contract)
    _require(approved["status"] ==
             "frozen_executable_seal_and_single_slot_smoke" and
             approved["authorization"]["single_slot_raw_smoke_authorized"]
             is True and
             approved["authorization"]["twelve_slot_raw_generation_authorized"]
             is False,
             "D-211 single-slot raw smoke is not executable")
    _require(reviewed_code_commit == approved["expected_reviewed_code_commit"],
             "D-211 reviewed code commit mismatch")
    return approved
