"""D-221 development-scale prefix extension.

D-219 removed the semantic head, which took the human annotation cost of a
larger sample to zero, and the measured E-02 rate (2.6 s per house at eight
workers) showed elapsed time was never the binding constraint either.  D-221
therefore froze a decision rule *before* reading the structural class histogram;
the measured 856 bottleneck frames selected 2048/128/128.

This module extends the sampled prefix.  It is deliberately not a regeneration:
the selection is ``ascending_sha256(sampling_salt|split|house_id)`` truncated to
a fixed prefix, so growing the count appends new ranks and leaves every existing
rank untouched.  The module refuses to proceed unless it can prove that, house
by house, against the plan that is already on disk.

A prefix extension is not the ``full_house_expansion`` gate, which stays false
everywhere.
"""

from __future__ import annotations

import hashlib
from typing import Any, Mapping, Sequence

from cpmt.hashing import canonical_json, clone_json

from .d217_estimator_development import (
    SPLITS,
    ordered_sample_candidates,
    public_house_ref,
    validate_d217_contract,
)


CONTRACT_SCHEMA = "vsmt-vm04-d221-estimator-scale-rule-v1"
PLAN_SCHEMA = "vsmt-vm04-d221-prefix-extension-plan-v1"
CLOSED_STATUS = "measured_decision_pending_user_review"
ACTIVE_STATUS = "frozen_executable_structural_rgbd_expansion"
AUTHORIZATION_KEYS = {
    "structural_rgbd_expansion", "structural_training",
    "audit_open_or_generation", "production_reader", "route_or_raw_generation",
}
GENERATED_SPLITS = ("train", "calibration")


class D221Error(ValueError):
    """A stable D-221 contract or prefix-extension failure."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise D221Error(message)


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def validate_d221_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the scale rule, its measurement and the selected branch."""

    value = clone_json(dict(contract))
    _require(value.get("schema_version") == CONTRACT_SCHEMA and
             value.get("decision_id") == "D-221",
             "D-221 contract identity changed")
    status = value.get("status")
    _require(status in {CLOSED_STATUS, ACTIVE_STATUS,
                        "rule_frozen_measurement_pending"},
             "D-221 contract status is not a registered state")
    authorization = value["authorization"]
    _require(set(authorization) == AUTHORIZATION_KEYS,
             "D-221 authorization has unexpected fields")
    for name in ("structural_training", "audit_open_or_generation",
                 "production_reader", "route_or_raw_generation"):
        _require(authorization[name] is False,
                 f"D-221 must keep {name} false")

    rule = value["frozen_decision_rule"]
    _require(rule["rule_frozen_before_reading_the_measurement"] is True and
             rule["thresholds_may_not_be_adjusted_after_reading"] is True and
             rule["full_house_expansion_permitted"] is False,
             "D-221 frozen rule boundary changed")

    if status == "rule_frozen_measurement_pending":
        _require(value["measurement"] is None and
                 value["resulting_decision"] is None,
                 "the pre-measurement D-221 contract must not carry a result")
        _require(authorization["structural_rgbd_expansion"] is False,
                 "D-221 may not authorize an expansion before the measurement")
        return value

    measurement = value["measurement"]
    _require(measurement is not None and
             measurement["audit_split_read"] is False and
             measurement["model_output_read"] is False and
             measurement["new_simulation_run"] is False,
             "D-221 measurement boundary changed")
    decision = value["resulting_decision"]
    _require(decision is not None and
             decision["rule_was_frozen_before_the_measurement_was_read"] is True
             and decision["thresholds_unchanged_after_reading"] is True and
             decision["full_house_still_refused"] is True,
             "D-221 resulting decision boundary changed")
    _require(_selected_counts(value) is not None,
             "D-221 resulting decision does not name a registered scale")
    if status == CLOSED_STATUS:
        _require(authorization["structural_rgbd_expansion"] is False,
                 "the unreviewed D-221 contract must keep the expansion closed")
    return value


def _selected_counts(contract: Mapping[str, Any]) -> dict[str, int] | None:
    """Map the rule's chosen branch onto explicit per-split house counts."""

    decision = contract["resulting_decision"]["decision"]
    table = {
        "keep_512_train_64_calibration_64_audit":
            {"train": 512, "calibration": 64, "audit": 64},
        "expand_to_2048_train_128_calibration_128_audit":
            {"train": 2048, "calibration": 128, "audit": 128},
        "expand_to_4096_train_256_calibration_256_audit":
            {"train": 4096, "calibration": 256, "audit": 256},
    }
    counts = table.get(decision)
    if counts is None:
        return None
    approved = contract["resulting_decision"].get("approved_scale")
    if approved is not None and approved != counts:
        return None
    return counts


def selected_house_counts(contract: Mapping[str, Any]) -> dict[str, int]:
    value = validate_d221_contract(contract)
    counts = _selected_counts(value)
    _require(counts is not None, "D-221 selected scale is not registered")
    return counts


def plan_prefix_extension(
    *, partition_manifest: Mapping[str, Any],
    existing_private_plan: Mapping[str, Any],
    source_rows_by_house: Mapping[str, Mapping[str, Any]],
    d217_contract: Mapping[str, Any], d221_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Extend the sampled prefix and prove the existing ranks are untouched.

    Returns the unchanged rows, the rows that still have to be generated, and a
    sealed plan that binds both to the partition already on disk.
    """

    contract = validate_d221_contract(d221_contract)
    d217 = validate_d217_contract(d217_contract)
    counts = selected_house_counts(contract)
    old_counts = d217["development_sample"]["house_counts"]
    for split in SPLITS:
        _require(counts[split] >= old_counts[split],
                 f"D-221 may not shrink the {split} prefix")
    _require(counts != old_counts,
             "D-221 extension was invoked without a change of scale")

    partition_receipt = partition_manifest["partition_manifest_receipt_sha256"]
    _require(existing_private_plan["partition_manifest_receipt_sha256"] ==
             partition_receipt,
             "the existing plan is bound to another partition manifest")

    existing_by_key = {}
    for row in existing_private_plan["rows"]:
        key = (row["split"], row["sample_rank"])
        _require(key not in existing_by_key,
                 "the existing plan repeats a split and sample rank")
        existing_by_key[key] = row

    salt = d217["development_sample"]["sampling_salt"]
    unchanged: list[dict[str, Any]] = []
    to_generate: list[dict[str, Any]] = []
    selected: dict[str, list[str]] = {}
    for split in SPLITS:
        candidates = ordered_sample_candidates(
            partition_manifest["rows"], split=split, sampling_salt=salt)
        _require(len(candidates) >= counts[split],
                 f"insufficient {split} houses for the extended prefix")
        selected[split] = candidates[:counts[split]]

    for split in GENERATED_SPLITS:
        for rank, house_id in enumerate(selected[split]):
            reference = public_house_ref(
                split=split, sample_rank=rank,
                partition_manifest_receipt_sha256=partition_receipt)
            previous = existing_by_key.pop((split, rank), None)
            if previous is None:
                _require(rank >= old_counts[split],
                         f"{split} rank {rank} vanished from the existing plan")
                source = source_rows_by_house.get(house_id)
                _require(source is not None,
                         f"source inventory has no record for {house_id}")
                to_generate.append({
                    "split": split, "sample_rank": rank, "house_id": house_id,
                    "source_file_sha256": source["source_file_sha256"],
                    "source_record_sha256": source["source_record_sha256"],
                    "source_locator": source["source_locator"],
                    "public_house_ref": reference,
                })
                continue
            row = {"split": split, "sample_rank": rank, "house_id": house_id,
                   "public_house_ref": reference}
            _require(previous["house_id"] == house_id,
                     f"{split} rank {rank} changed house under the extension")
            _require(previous["public_house_ref"] == reference,
                     f"{split} rank {rank} changed its public house ref")
            unchanged.append(row)
    _require(not existing_by_key,
             "the extended prefix dropped rows that the existing plan had")

    payload = {
        "schema_version": PLAN_SCHEMA,
        "partition_manifest_receipt_sha256": partition_receipt,
        "previous_house_counts": dict(old_counts),
        "extended_house_counts": counts,
        "unchanged_row_count": len(unchanged),
        "rows_to_generate": to_generate,
        "generate_row_count": len(to_generate),
        "audit_house_ids_opened": False,
        "full_house_expansion": False,
        "existing_rgbd_and_features_reused": True,
        "prefix_invariance_verified": True,
        "unchanged_rows_sha256": _sha(unchanged),
        "rows_to_generate_sha256": _sha(to_generate),
    }
    payload["extension_plan_sha256"] = _sha(payload)
    return payload


def validate_extension_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    value = clone_json(dict(plan))
    expected = {
        "schema_version", "partition_manifest_receipt_sha256",
        "previous_house_counts", "extended_house_counts",
        "unchanged_row_count", "rows_to_generate", "generate_row_count",
        "audit_house_ids_opened", "full_house_expansion",
        "existing_rgbd_and_features_reused", "prefix_invariance_verified",
        "unchanged_rows_sha256", "rows_to_generate_sha256",
        "extension_plan_sha256",
    }
    _require(type(value) is dict and set(value) == expected,
             "D-221 extension plan has unexpected fields")
    _require(value["schema_version"] == PLAN_SCHEMA and
             value["audit_house_ids_opened"] is False and
             value["full_house_expansion"] is False and
             value["existing_rgbd_and_features_reused"] is True and
             value["prefix_invariance_verified"] is True,
             "D-221 extension plan boundary changed")
    _require(value["generate_row_count"] == len(value["rows_to_generate"]) and
             value["rows_to_generate_sha256"] == _sha(value["rows_to_generate"]),
             "D-221 extension plan generate rows do not match their digest")
    digest = value.pop("extension_plan_sha256")
    _require(digest == _sha(value), "D-221 extension plan digest mismatch")
    value["extension_plan_sha256"] = digest
    return value
