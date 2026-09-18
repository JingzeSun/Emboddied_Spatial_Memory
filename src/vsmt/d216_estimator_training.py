"""D-216 house-split materialization and estimator training seals.

This module has no simulator, RGB-D reader, route, or production-cache API.
It assigns eligible houses using the frozen D-215 rule, validates explicitly
sealed training arrays, fits the two frozen affine heads, and returns immutable
normalization/weight/training receipts.  Execution remains controlled by the
separate D-216 stage contract.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import math
from pathlib import PurePosixPath
import re
from typing import Any, Mapping, Sequence

import numpy as np

from cpmt.hashing import canonical_json, clone_json
from .d215_frontend_freeze import (
    GEOMETRY_FEATURE_ORDER,
    SEMANTIC_LABELS,
    STRUCTURAL_LABELS,
    validate_d215_contract,
)
from .two_house_audit import validate_source_inventory


CONTRACT_SCHEMA = "vsmt-vm04-d216-estimator-training-seal-v1"
RESERVED_SCHEMA = "vsmt-vm04-d216-reserved-house-manifest-v1"
SPLIT_SCHEMA = "vsmt-vm04-d216-house-split-manifest-v1"
BUNDLE_SCHEMA = "vsmt-vm04-d216-estimator-training-bundle-v1"
EVIDENCE_SCHEMA = "vsmt-vm04-d216-training-evidence-index-v1"
SEMANTIC_RECEIPT_SCHEMA = "vsmt-vm04-d216-semantic-annotation-receipt-v1"
STRUCTURAL_RECEIPT_SCHEMA = "vsmt-vm04-d216-structural-label-receipt-v1"
NORMALIZATION_SCHEMA = "vsmt-vm04-d216-normalization-v1"
WEIGHTS_SCHEMA = "vsmt-vm04-d216-two-head-weights-v1"
TRAINING_RECEIPT_SCHEMA = "vsmt-vm04-d216-training-receipt-v1"
SUCCESS_SCHEMA = "vsmt-vm04-d216-training-success-v1"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SPLITS = ("train", "calibration", "audit")
SOURCE_MANIFEST_SHA256 = (
    "7db1df1edb714162089b56e62f5258a947c5c6ddc38ed2b7082582d4659269bd"
)
ELIGIBLE_HOUSE_IDS_SHA256 = (
    "31b9d819afafcbef8d9bc3466fa00d49e6605cfbe1af3827ddf1a25fa0fb6d87"
)
SPLIT_RULE_SHA256 = (
    "4fa32f8940cb22516d0c004f9c4b8d7a6cb5c1cd9a85dfb6f63ef6178dd34774"
)
SPLIT_SALT = "d215-shared-rgbd-frontend-split-v1"
NPZ_ARRAY_NAMES = (
    "features", "semantic_labels", "structural_labels", "house_ids",
    "observation_ids", "public_observation_sha256",
    "semantic_annotation_receipt_sha256",
    "structural_label_receipt_sha256",
)
REQUIRED_RESERVED_ROLES = (
    "P0_route_and_raw_development", "VM04_validation", "VM04_confirmation",
)


class D216Error(ValueError):
    """A stable D-216 split, training-input, or artifact-seal failure."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise D216Error(message)


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _sealed(payload: Mapping[str, Any], field: str) -> dict[str, Any]:
    value = clone_json(dict(payload))
    value[field] = _sha(value)
    return value


def _hex(value: Any, length: int, name: str) -> str:
    pattern = HEX40 if length == 40 else HEX64
    _require(type(value) is str and pattern.fullmatch(value) is not None,
             f"{name} must be a lowercase SHA-{length * 4}")
    return value


def _exact_keys(value: Mapping[str, Any], expected: set[str], name: str) -> None:
    _require(set(value) == expected, f"{name} has unexpected fields")


def validate_d216_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the review candidate and prove every execution gate is closed."""

    value = clone_json(dict(contract))
    _exact_keys(value, {
        "schema_version", "decision_id", "status", "reviewed_baseline_commit",
        "expected_reviewed_implementation_commit", "d215_binding",
        "authorization", "activation_policy", "split_manifest", "training_bundle",
        "optimizer_completion", "sealed_outputs", "reader_boundary",
    }, "D-216 contract")
    _require(value["schema_version"] == CONTRACT_SCHEMA and
             value["decision_id"] == "D-216" and value["status"] in {
                 "implementation_pending_review_all_execution_closed",
                 "frozen_executable_split_and_estimator_training_seal",
             },
             "D-216 identity or review status changed")
    _require(value["reviewed_baseline_commit"] ==
             "7dd44d2b95f5eb2a28393e9825b197f476026322",
             "D-216 review binding changed")
    _require(value["d215_binding"] == {
        "relative_path": "configs/vsmt/vm04_d215_frontend_freeze_v1.json",
        "file_sha256": "c3d6736f67b300eca03882c081e56e6bf4d65ad1913bcc411df8477fbd188db8",
        "source_manifest_sha256": "7db1df1edb714162089b56e62f5258a947c5c6ddc38ed2b7082582d4659269bd",
        "eligible_house_ids_sha256": "31b9d819afafcbef8d9bc3466fa00d49e6605cfbe1af3827ddf1a25fa0fb6d87",
        "split_rule_sha256": "4fa32f8940cb22516d0c004f9c4b8d7a6cb5c1cd9a85dfb6f63ef6178dd34774",
        "inference_config_sha256": "4cd2bc00e8af7b4897d00d9ad90a69bdb389b1d1dd310705c1c44c5e6b720c70",
    }, "D-216 D-215 binding changed")
    expected_auth = {
        "split_manifest_materialization", "training_frame_generation",
        "semantic_annotation_import", "training_bundle_sealing",
        "estimator_training", "artifact_sealing", "production_reader",
        "route_survey", "raw_generation", "private_evaluation",
    }
    policy = value["activation_policy"]
    _require(policy == {
        "active_status": "frozen_executable_split_and_estimator_training_seal",
        "activation_commit_may_change_only": [
            "configs/vsmt/vm04_d216_estimator_training_seal_v1.json"],
        "active_true_authorizations": [
            "split_manifest_materialization", "semantic_annotation_import",
            "training_bundle_sealing", "estimator_training", "artifact_sealing"],
        "must_remain_false": [
            "training_frame_generation", "production_reader", "route_survey",
            "raw_generation", "private_evaluation"],
    }, "D-216 activation policy changed")
    _require(set(value["authorization"]) == expected_auth,
             "D-216 authorization keys changed")
    if value["status"] == "implementation_pending_review_all_execution_closed":
        _require(value["expected_reviewed_implementation_commit"] is None and
                 not any(value["authorization"].values()),
                 "D-216 implementation commit must keep all execution closed")
    else:
        _hex(value["expected_reviewed_implementation_commit"], 40,
             "expected reviewed implementation commit")
        _require({name for name, enabled in value["authorization"].items()
                  if enabled} == set(policy["active_true_authorizations"]) and
                 all(value["authorization"][name] is False
                     for name in policy["must_remain_false"]),
                 "D-216 active authorization scope changed")
    split = value["split_manifest"]
    _require(split["schema_version"] == SPLIT_SCHEMA and
             split["reserved_house_manifest_schema"] == RESERVED_SCHEMA and
             split["required_reserved_roles"] == list(REQUIRED_RESERVED_ROLES)
             and split["p0_house_ids"] ==
             ["train:004270", "train:008243"] and
             split["include_every_eligible_house_exactly_once"] is True and
             split["excluded_rows_remain_in_manifest"] is True and
             split["assignment_reads_frames_labels_or_route_yield"] is False
             and split["cross_split_house_overlap_allowed"] is False,
             "D-216 split-manifest boundary changed")
    bundle = value["training_bundle"]
    _require(bundle["schema_version"] == BUNDLE_SCHEMA and
             bundle["training_evidence_index_schema"] == EVIDENCE_SCHEMA and
             bundle["semantic_annotation_receipt_schema"] ==
             SEMANTIC_RECEIPT_SCHEMA and
             bundle["structural_label_receipt_schema"] ==
             STRUCTURAL_RECEIPT_SCHEMA and
             bundle["required_splits"] == list(SPLITS) and
             bundle["npz_array_names"] == list(NPZ_ARRAY_NAMES) and
             bundle["feature_dtype"] == "float32" and
             bundle["feature_dimension"] == 396 and
             bundle["label_dtype"] == "uint8" and
             bundle["semantic_labels"] == list(SEMANTIC_LABELS) and
             bundle["structural_labels"] == list(STRUCTURAL_LABELS) and
             bundle["house_id_is_training_management_only_and_never_a_model_feature"]
             is True,
             "D-216 training-bundle boundary changed")
    forbidden = set(bundle["forbidden_fields"])
    _require({"scenario_id", "scenario_role", "route_index", "reachable_grid",
              "room_metadata", "instance_mask", "object_id", "teacher",
              "future"}.issubset(forbidden),
             "D-216 forbidden training fields were weakened")
    optimizer = value["optimizer_completion"]
    _require(optimizer == {
        "implementation": "torch_adamw_two_affine_heads",
        "parameter_initialization": "all_weights_and_biases_zero",
        "adamw_beta1": 0.9, "adamw_beta2": 0.999,
        "adamw_epsilon": 1e-8,
        "batch_order": "torch_cpu_randperm_seed_plus_epoch",
        "class_weight_rule":
            "inverse_sqrt_train_class_fraction_clipped_0_5_to_4_without_renormalization",
        "early_stopping_metric_expansion":
            "mean_semantic_nll_plus_mean_structural_nll_on_calibration",
        "minimum_delta_resets_patience_only": True,
        "checkpoint_always_tracks_strict_lowest_metric": True,
        "temperature_fit": "golden_section_on_log_temperature",
        "temperature_log_bounds": [-6.0, 6.0],
        "temperature_iterations": 96,
        "audit_split_affects_checkpoint_or_temperature": False,
        "deterministic_algorithms_required": True,
        "wall_clock_timeout_allowed": False,
    }, "D-216 optimizer completion changed")
    _require(value["sealed_outputs"] == {
        "normalization_schema": NORMALIZATION_SCHEMA,
        "weights_schema": WEIGHTS_SCHEMA,
        "training_receipt_schema": TRAINING_RECEIPT_SCHEMA,
        "success_schema": SUCCESS_SCHEMA,
        "overwrite_allowed": False,
        "raw_features_labels_house_ids_or_paths_in_weight_artifacts": False,
    }, "D-216 sealed-output boundary changed")
    _require(value["reader_boundary"] == {
        "production_reader_implemented_in_this_decision": False,
        "reader_may_start_before_real_weight_receipts_are_reviewed": False,
        "route_or_raw_execution_opened": False,
        "legacy_grid_deletion_opened": False,
    }, "D-216 reader boundary changed")
    return value


def make_reserved_house_manifest(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Seal explicit P0/validation/confirmation exclusions before splitting."""

    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(rows):
        _exact_keys(raw, {"house_id", "roles"}, f"reserved rows[{index}]")
        house_id = raw["house_id"]
        roles = raw["roles"]
        _require(type(house_id) is str and house_id and type(roles) is list and
                 roles and all(type(item) is str for item in roles),
                 "reserved house row is malformed")
        unique_roles = sorted(set(roles))
        _require(len(unique_roles) == len(roles) and
                 set(unique_roles).issubset(REQUIRED_RESERVED_ROLES),
                 "reserved house role is duplicated or unknown")
        normalized.append({"house_id": house_id, "roles": unique_roles})
    normalized.sort(key=lambda row: row["house_id"])
    ids = [row["house_id"] for row in normalized]
    _require(len(ids) == len(set(ids)), "reserved house IDs must be unique")
    observed_roles = {role for row in normalized for role in row["roles"]}
    _require(observed_roles == set(REQUIRED_RESERVED_ROLES),
             "all three reserved house roles must be bound before splitting")
    by_id = {row["house_id"]: row["roles"] for row in normalized}
    for house_id in ("train:004270", "train:008243"):
        _require("P0_route_and_raw_development" in by_id.get(house_id, []),
                 "both frozen P0 houses must be explicitly reserved")
    payload = {
        "schema_version": RESERVED_SCHEMA,
        "rows": normalized,
        "house_count": len(normalized),
        "role_counts": {
            role: sum(role in row["roles"] for row in normalized)
            for role in REQUIRED_RESERVED_ROLES
        },
    }
    return _sealed(payload, "reserved_manifest_receipt_sha256")


def validate_reserved_house_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    value = clone_json(dict(manifest))
    _exact_keys(value, {"schema_version", "rows", "house_count", "role_counts",
                        "reserved_manifest_receipt_sha256"},
                "reserved house manifest")
    _hex(value["reserved_manifest_receipt_sha256"], 64,
         "reserved manifest receipt")
    _require(value == make_reserved_house_manifest(value["rows"]),
             "reserved house manifest content or receipt changed")
    return value


def _house_bucket(house_id: str, d215: Mapping[str, Any]) -> int:
    split = d215["semantic_structural_estimator"]["training_split"]
    payload = (f"{split['split_salt']}|{split['source_manifest_sha256']}|"
               f"{house_id}").encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") % 100


def make_house_split_manifest(
    *, source_inventory: Mapping[str, Any],
    reserved_house_manifest: Mapping[str, Any],
    d215_contract: Mapping[str, Any], d216_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Materialize every eligible house without reading observations or yield."""

    validate_d216_contract(d216_contract)
    d215 = validate_d215_contract(d215_contract)
    inventory = validate_source_inventory(source_inventory)
    reserved = validate_reserved_house_manifest(reserved_house_manifest)
    binding = d216_contract["d215_binding"]
    _require(inventory["source_manifest_sha256"] ==
             binding["source_manifest_sha256"] and
             inventory["eligible_house_ids_sha256"] ==
             binding["eligible_house_ids_sha256"],
             "source inventory does not match the frozen D-215 universe")
    ids = inventory["eligible_house_ids"]
    _require(_sha(ids) == binding["eligible_house_ids_sha256"],
             "eligible house ID bytes changed")
    id_set = set(ids)
    _require(all(row["house_id"] in id_set for row in reserved["rows"]),
             "reserved manifest contains a house outside the eligible universe")
    roles_by_house = {row["house_id"]: row["roles"] for row in reserved["rows"]}
    d215_split = d215["semantic_structural_estimator"]["training_split"]
    rows: list[dict[str, Any]] = []
    for house_id in ids:
        roles = roles_by_house.get(house_id, [])
        bucket = _house_bucket(house_id, d215)
        if roles or house_id in d215_split["excluded_house_ids"]:
            split = "excluded"
        elif bucket <= d215_split["train_buckets_inclusive"][1]:
            split = "train"
        elif bucket <= d215_split["calibration_buckets_inclusive"][1]:
            split = "calibration"
        else:
            split = "audit"
        rows.append({
            "house_id": house_id,
            "split": split,
            "hash_bucket": None if split == "excluded" else
                bucket,
            "exclusion_roles": roles,
            "planned_observations": 0 if split == "excluded" else 32,
        })
    counts = Counter(row["split"] for row in rows)
    payload = {
        "schema_version": SPLIT_SCHEMA,
        "d215_split_rule_sha256": binding["split_rule_sha256"],
        "source_inventory_sha256": inventory["inventory_sha256"],
        "source_manifest_sha256": inventory["source_manifest_sha256"],
        "eligible_house_ids_sha256": inventory["eligible_house_ids_sha256"],
        "reserved_manifest_receipt_sha256":
            reserved["reserved_manifest_receipt_sha256"],
        "house_count": len(rows),
        "split_counts": {name: counts[name]
                         for name in (*SPLITS, "excluded")},
        "rows": rows,
        "frames_labels_routes_or_yield_read": False,
    }
    return _sealed(payload, "partition_manifest_receipt_sha256")


def validate_house_split_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    value = clone_json(dict(manifest))
    _exact_keys(value, {
        "schema_version", "d215_split_rule_sha256", "source_inventory_sha256",
        "source_manifest_sha256", "eligible_house_ids_sha256",
        "reserved_manifest_receipt_sha256", "house_count", "split_counts",
        "rows", "frames_labels_routes_or_yield_read",
        "partition_manifest_receipt_sha256",
    }, "house split manifest")
    _require(value["schema_version"] == SPLIT_SCHEMA and
             value["frames_labels_routes_or_yield_read"] is False,
             "house split manifest boundary changed")
    _require(value["d215_split_rule_sha256"] == SPLIT_RULE_SHA256 and
             value["source_manifest_sha256"] == SOURCE_MANIFEST_SHA256 and
             value["eligible_house_ids_sha256"] ==
             ELIGIBLE_HOUSE_IDS_SHA256,
             "house split manifest is not bound to the D-215 universe")
    for name in ("d215_split_rule_sha256", "source_inventory_sha256",
                 "source_manifest_sha256", "eligible_house_ids_sha256",
                 "reserved_manifest_receipt_sha256",
                 "partition_manifest_receipt_sha256"):
        _hex(value[name], 64, name)
    rows = value["rows"]
    _require(type(rows) is list and value["house_count"] == len(rows),
             "house split row count mismatch")
    ids: list[str] = []
    for index, row in enumerate(rows):
        _exact_keys(row, {"house_id", "split", "hash_bucket",
                          "exclusion_roles", "planned_observations"},
                    f"house split rows[{index}]")
        _require(type(row["house_id"]) is str and row["house_id"] and
                 row["split"] in {*SPLITS, "excluded"},
                 "house split row identity is invalid")
        excluded = row["split"] == "excluded"
        _require((excluded and row["hash_bucket"] is None and
                  row["planned_observations"] == 0 and
                  bool(row["exclusion_roles"])) or
                 (not excluded and type(row["hash_bucket"]) is int and
                  0 <= row["hash_bucket"] <= 99 and
                  row["planned_observations"] == 32 and
                  row["exclusion_roles"] == []),
                 "house split assignment or exclusion is inconsistent")
        ids.append(row["house_id"])
    _require(ids == sorted(ids) and len(ids) == len(set(ids)),
             "house split rows must be unique and sorted")
    _require(len(ids) == 10000 and _sha(ids) == ELIGIBLE_HOUSE_IDS_SHA256,
             "house split manifest does not contain the complete frozen universe")
    reserved_rows = [{"house_id": row["house_id"],
                      "roles": row["exclusion_roles"]}
                     for row in rows if row["exclusion_roles"]]
    reserved = make_reserved_house_manifest(reserved_rows)
    _require(reserved["reserved_manifest_receipt_sha256"] ==
             value["reserved_manifest_receipt_sha256"],
             "house split reserved-role receipt mismatch")
    for row in rows:
        if row["split"] == "excluded":
            continue
        payload = (f"{SPLIT_SALT}|{SOURCE_MANIFEST_SHA256}|"
                   f"{row['house_id']}").encode("utf-8")
        bucket = int.from_bytes(hashlib.sha256(payload).digest()[:8],
                                "big") % 100
        expected = "train" if bucket <= 79 else (
            "calibration" if bucket <= 89 else "audit")
        _require(row["hash_bucket"] == bucket and row["split"] == expected,
                 "house split row differs from the frozen hash assignment")
    counts = Counter(row["split"] for row in rows)
    _require(value["split_counts"] == {
        name: counts[name] for name in (*SPLITS, "excluded")
    }, "house split counts changed")
    receipt = value.pop("partition_manifest_receipt_sha256")
    _require(receipt == _sha(value), "house split receipt mismatch")
    value["partition_manifest_receipt_sha256"] = receipt
    return value


def _string_vector(value: Any, length: int, name: str) -> list[str]:
    array = np.asarray(value)
    _require(array.shape == (length,) and array.dtype.kind in {"U", "S"},
             f"{name} must be a one-dimensional fixed-width string array")
    result = [item.decode("utf-8") if isinstance(item, bytes) else str(item)
              for item in array.tolist()]
    _require(all(result), f"{name} contains an empty value")
    return result


def _array_content_digest(arrays: Mapping[str, Any]) -> str:
    """Hash exact numeric bytes and logical string values without JSON bulk."""

    rows: list[dict[str, Any]] = []
    for name in NPZ_ARRAY_NAMES:
        array = np.asarray(arrays[name])
        if array.dtype.kind in {"U", "S"}:
            logical = [item.decode("utf-8") if isinstance(item, bytes)
                       else str(item) for item in array.reshape(-1).tolist()]
            content = _sha(logical)
        else:
            content = hashlib.sha256(
                np.ascontiguousarray(array).tobytes(order="C")).hexdigest()
        rows.append({
            "name": name, "dtype": array.dtype.str,
            "shape": list(array.shape), "content_sha256": content,
        })
    return _sha(rows)


def make_training_evidence_index(
    rows: Sequence[Mapping[str, Any]], *, d215_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Seal human semantic and graph-rule structural labels per observation."""

    d215 = validate_d215_contract(d215_contract)
    structural_rule_sha = _sha(d215["semantic_structural_estimator"]
                               ["label_boundary"]["structural_reference_rule"])
    output: list[dict[str, Any]] = []
    for index, raw in enumerate(rows):
        _exact_keys(raw, {
            "observation_id", "public_observation_sha256",
            "annotator_a_label", "annotator_b_label", "adjudicated_label",
            "unresolved_disagreement", "structural_label",
        }, f"training evidence rows[{index}]")
        observation_id = raw["observation_id"]
        public_sha = _hex(raw["public_observation_sha256"], 64,
                          "public observation")
        _require(type(observation_id) is str and observation_id and
                 raw["annotator_a_label"] in SEMANTIC_LABELS and
                 raw["annotator_b_label"] in SEMANTIC_LABELS and
                 raw["adjudicated_label"] in SEMANTIC_LABELS and
                 raw["structural_label"] in STRUCTURAL_LABELS and
                 type(raw["unresolved_disagreement"]) is bool,
                 "training evidence labels are invalid")
        if raw["unresolved_disagreement"]:
            _require(raw["adjudicated_label"] == "unknown",
                     "unresolved semantic disagreement must be unknown")
        semantic = _sealed({
            "schema_version": SEMANTIC_RECEIPT_SCHEMA,
            "observation_id": observation_id,
            "public_observation_sha256": public_sha,
            "annotator_a_label": raw["annotator_a_label"],
            "annotator_b_label": raw["annotator_b_label"],
            "adjudicated_label": raw["adjudicated_label"],
            "unresolved_disagreement": raw["unresolved_disagreement"],
            "annotators_received_scenario_or_house_identity": False,
            "annotation_input": "single_frame_public_rgbd_only",
        }, "semantic_annotation_receipt_sha256")
        structural = _sealed({
            "schema_version": STRUCTURAL_RECEIPT_SCHEMA,
            "observation_id": observation_id,
            "public_observation_sha256": public_sha,
            "structural_label": raw["structural_label"],
            "d215_structural_reference_rule_sha256": structural_rule_sha,
            "reference_grid_available_to_inference_or_cache": False,
            "p0_house_private_metadata_used": False,
        }, "structural_label_receipt_sha256")
        output.append({
            "observation_id": observation_id,
            "public_observation_sha256": public_sha,
            "semantic": semantic, "structural": structural,
        })
    output.sort(key=lambda row: row["observation_id"])
    ids = [row["observation_id"] for row in output]
    _require(ids and len(ids) == len(set(ids)),
             "training evidence observation IDs must be unique")
    return _sealed({
        "schema_version": EVIDENCE_SCHEMA,
        "d215_inference_config_sha256":
            d215["semantic_structural_estimator"]["inference_config_sha256"],
        "row_count": len(output), "rows": output,
        "scenario_house_route_identity_given_to_annotators": False,
        "reference_labels_available_to_inference_or_cache": False,
    }, "training_evidence_index_sha256")


def validate_training_evidence_index(
    index: Mapping[str, Any], *, d215_contract: Mapping[str, Any],
) -> dict[str, Any]:
    value = clone_json(dict(index))
    _exact_keys(value, {
        "schema_version", "d215_inference_config_sha256", "row_count", "rows",
        "scenario_house_route_identity_given_to_annotators",
        "reference_labels_available_to_inference_or_cache",
        "training_evidence_index_sha256",
    }, "training evidence index")
    _require(value["schema_version"] == EVIDENCE_SCHEMA and
             value["scenario_house_route_identity_given_to_annotators"] is False
             and value["reference_labels_available_to_inference_or_cache"] is False
             and value["row_count"] == len(value["rows"]),
             "training evidence boundary changed")
    raw_rows = []
    for row in value["rows"]:
        semantic, structural = row["semantic"], row["structural"]
        _require(semantic["observation_id"] == row["observation_id"] ==
                 structural["observation_id"] and
                 semantic["public_observation_sha256"] ==
                 row["public_observation_sha256"] ==
                 structural["public_observation_sha256"],
                 "training evidence subreceipts are cross-wired")
        raw_rows.append({
            "observation_id": row["observation_id"],
            "public_observation_sha256": row["public_observation_sha256"],
            "annotator_a_label": semantic["annotator_a_label"],
            "annotator_b_label": semantic["annotator_b_label"],
            "adjudicated_label": semantic["adjudicated_label"],
            "unresolved_disagreement": semantic["unresolved_disagreement"],
            "structural_label": structural["structural_label"],
        })
    rebuilt = make_training_evidence_index(
        raw_rows, d215_contract=d215_contract)
    _require(value == rebuilt, "training evidence content or receipt changed")
    return value


def validate_training_shard_arrays(
    arrays: Mapping[str, Any], *, split: str,
    partition_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate one exact NPZ schema and return only aggregate audit facts."""

    partition = validate_house_split_manifest(partition_manifest)
    _require(split in SPLITS, "training shard split is invalid")
    _require(set(arrays) == set(NPZ_ARRAY_NAMES),
             "training shard arrays differ from the frozen exact schema")
    features = np.asarray(arrays["features"])
    _require(features.dtype == np.dtype("float32") and features.ndim == 2 and
             features.shape[1] == 396 and features.shape[0] > 0 and
             np.isfinite(features).all(),
             "training features must be finite float32 [N,396]")
    count = int(features.shape[0])
    semantic = np.asarray(arrays["semantic_labels"])
    structural = np.asarray(arrays["structural_labels"])
    _require(semantic.dtype == np.dtype("uint8") and
             structural.dtype == np.dtype("uint8") and
             semantic.shape == (count,) and structural.shape == (count,) and
             np.all(semantic < 3) and np.all(structural < 3),
             "training labels must be uint8 class indices in [0,2]")
    houses = _string_vector(arrays["house_ids"], count, "house_ids")
    observations = _string_vector(
        arrays["observation_ids"], count, "observation_ids")
    _require(len(observations) == len(set(observations)),
             "observation IDs must be unique within a shard")
    split_by_house = {row["house_id"]: row["split"]
                      for row in partition["rows"]}
    _require(all(split_by_house.get(house_id) == split for house_id in houses),
             "training row house does not belong to its declared split")
    digest_vectors: dict[str, list[str]] = {}
    for name in ("public_observation_sha256",
                 "semantic_annotation_receipt_sha256",
                 "structural_label_receipt_sha256"):
        values = _string_vector(arrays[name], count, name)
        _require(all(HEX64.fullmatch(item) is not None for item in values),
                 f"{name} contains a non-SHA-256 value")
        digest_vectors[name] = values
    return {
        "row_count": count,
        "house_count": len(set(houses)),
        "observation_ids_sha256": _sha(observations),
        "house_ids_sha256": _sha(houses),
        "public_observation_digests_sha256":
            _sha(digest_vectors["public_observation_sha256"]),
        "semantic_annotation_receipts_sha256":
            _sha(digest_vectors["semantic_annotation_receipt_sha256"]),
        "structural_label_receipts_sha256":
            _sha(digest_vectors["structural_label_receipt_sha256"]),
        "array_content_sha256": _array_content_digest(arrays),
        "semantic_class_counts": [int(np.sum(semantic == index))
                                  for index in range(3)],
        "structural_class_counts": [int(np.sum(structural == index))
                                    for index in range(3)],
        "observation_ids": observations,
    }


def make_training_bundle_manifest(
    *, shards: Sequence[Mapping[str, Any]],
    partition_manifest: Mapping[str, Any],
    training_evidence_index: Mapping[str, Any],
    d215_contract: Mapping[str, Any], d216_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Seal immutable NPZ shard identities after validating every array."""

    validate_d216_contract(d216_contract)
    partition = validate_house_split_manifest(partition_manifest)
    evidence = validate_training_evidence_index(
        training_evidence_index, d215_contract=d215_contract)
    evidence_by_id = {row["observation_id"]: row for row in evidence["rows"]}
    output_rows: list[dict[str, Any]] = []
    arrays_by_key: dict[tuple[str, str], Mapping[str, Any]] = {}
    all_ids: list[str] = []
    for index, shard in enumerate(shards):
        _exact_keys(shard, {"relative_path", "file_sha256", "split", "arrays"},
                    f"shards[{index}]")
        path = shard["relative_path"]
        _require(type(path) is str and path and "\\" not in path and
                 not PurePosixPath(path).is_absolute() and
                 ".." not in PurePosixPath(path).parts,
                 "training shard path must be safe and relative")
        file_sha = _hex(shard["file_sha256"], 64, "training shard file")
        split = shard["split"]
        summary = validate_training_shard_arrays(
            shard["arrays"], split=split, partition_manifest=partition)
        observation_ids = summary.pop("observation_ids")
        all_ids.extend(observation_ids)
        arrays = shard["arrays"]
        public_values = _string_vector(
            arrays["public_observation_sha256"], len(observation_ids),
            "public_observation_sha256")
        semantic_receipts = _string_vector(
            arrays["semantic_annotation_receipt_sha256"], len(observation_ids),
            "semantic_annotation_receipt_sha256")
        structural_receipts = _string_vector(
            arrays["structural_label_receipt_sha256"], len(observation_ids),
            "structural_label_receipt_sha256")
        semantic_labels = np.asarray(arrays["semantic_labels"])
        structural_labels = np.asarray(arrays["structural_labels"])
        for row_index, observation_id in enumerate(observation_ids):
            item = evidence_by_id.get(observation_id)
            _require(item is not None and
                     item["public_observation_sha256"] ==
                     public_values[row_index] and
                     item["semantic"]["semantic_annotation_receipt_sha256"] ==
                     semantic_receipts[row_index] and
                     item["structural"]["structural_label_receipt_sha256"] ==
                     structural_receipts[row_index] and
                     SEMANTIC_LABELS[int(semantic_labels[row_index])] ==
                     item["semantic"]["adjudicated_label"] and
                     STRUCTURAL_LABELS[int(structural_labels[row_index])] ==
                     item["structural"]["structural_label"],
                     "training shard label or receipt differs from evidence index")
        arrays_by_key[(split, path)] = shard["arrays"]
        output_rows.append({
            "relative_path": path, "file_sha256": file_sha,
            "split": split, **summary,
        })
    _require(len(all_ids) == len(set(all_ids)),
             "observation IDs overlap across training shards")
    _require(set(all_ids) == set(evidence_by_id),
             "training shards and evidence index observation sets differ")
    output_rows.sort(key=lambda row: (SPLITS.index(row["split"]),
                                      row["relative_path"]))
    _require({row["split"] for row in output_rows} == set(SPLITS),
             "training bundle must contain train, calibration, and audit")
    split_content = {}
    for split in SPLITS:
        selected = [arrays_by_key[(row["split"], row["relative_path"])]
                    for row in output_rows if row["split"] == split]
        combined = {name: np.concatenate(
            [np.asarray(item[name]) for item in selected], axis=0)
                    for name in NPZ_ARRAY_NAMES}
        split_content[split] = _array_content_digest(combined)
    payload = {
        "schema_version": BUNDLE_SCHEMA,
        "partition_manifest_receipt_sha256":
            partition["partition_manifest_receipt_sha256"],
        "training_evidence_index_sha256":
            evidence["training_evidence_index_sha256"],
        "feature_dimension": 396,
        "array_names": list(NPZ_ARRAY_NAMES),
        "shards": output_rows,
        "row_counts": {
            split: sum(row["row_count"] for row in output_rows
                       if row["split"] == split) for split in SPLITS
        },
        "global_observation_ids_sha256": _sha(sorted(all_ids)),
        "split_array_content_sha256": split_content,
        "scenario_route_private_or_future_fields_present": False,
    }
    return _sealed(payload, "training_bundle_sha256")


def validate_training_bundle_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    value = clone_json(dict(manifest))
    _exact_keys(value, {
        "schema_version", "partition_manifest_receipt_sha256",
        "training_evidence_index_sha256",
        "feature_dimension", "array_names", "shards", "row_counts",
        "global_observation_ids_sha256", "split_array_content_sha256",
        "scenario_route_private_or_future_fields_present",
        "training_bundle_sha256",
    }, "training bundle manifest")
    _require(value["schema_version"] == BUNDLE_SCHEMA and
             value["feature_dimension"] == 396 and
             value["array_names"] == list(NPZ_ARRAY_NAMES) and
             value["scenario_route_private_or_future_fields_present"] is False,
             "training bundle schema boundary changed")
    for name in ("partition_manifest_receipt_sha256",
                 "training_evidence_index_sha256",
                 "global_observation_ids_sha256", "training_bundle_sha256"):
        _hex(value[name], 64, name)
    _require(type(value["shards"]) is list and value["shards"] and
             {row["split"] for row in value["shards"]} == set(SPLITS),
             "training bundle split coverage is incomplete")
    expected_row_keys = {
        "relative_path", "file_sha256", "split", "row_count", "house_count",
        "observation_ids_sha256", "house_ids_sha256",
        "public_observation_digests_sha256",
        "semantic_annotation_receipts_sha256",
        "structural_label_receipts_sha256", "semantic_class_counts",
        "structural_class_counts", "array_content_sha256",
    }
    for row in value["shards"]:
        _exact_keys(row, expected_row_keys, "training bundle shard")
        path = row["relative_path"]
        _require(type(path) is str and path and "\\" not in path and
                 not PurePosixPath(path).is_absolute() and
                 ".." not in PurePosixPath(path).parts,
                 "training bundle shard path is unsafe")
        for name in ("file_sha256", "observation_ids_sha256",
                     "house_ids_sha256", "public_observation_digests_sha256",
                     "semantic_annotation_receipts_sha256",
                     "structural_label_receipts_sha256",
                     "array_content_sha256"):
            _hex(row[name], 64, name)
        semantic_counts = row["semantic_class_counts"]
        structural_counts = row["structural_class_counts"]
        _require(row["split"] in SPLITS and type(row["row_count"]) is int and
                 row["row_count"] > 0 and type(row["house_count"]) is int and
                 0 < row["house_count"] <= row["row_count"] and
                 type(semantic_counts) is list and
                 type(structural_counts) is list and
                 len(semantic_counts) == 3 and len(structural_counts) == 3 and
                 all(type(count) is int and count >= 0
                     for count in semantic_counts + structural_counts) and
                 sum(semantic_counts) == row["row_count"] and
                 sum(structural_counts) == row["row_count"],
                 "training bundle shard summary is invalid")
    _require(value["shards"] == sorted(
        value["shards"], key=lambda row: (
            SPLITS.index(row["split"]), row["relative_path"])),
        "training bundle shards are not in deterministic order")
    _require(value["row_counts"] == {
        split: sum(row["row_count"] for row in value["shards"]
                   if row["split"] == split) for split in SPLITS
    }, "training bundle row counts changed")
    _require(set(value["split_array_content_sha256"]) == set(SPLITS),
             "training bundle split content digests are incomplete")
    for digest in value["split_array_content_sha256"].values():
        _hex(digest, 64, "split array content digest")
    receipt = value.pop("training_bundle_sha256")
    _require(receipt == _sha(value), "training bundle digest mismatch")
    value["training_bundle_sha256"] = receipt
    return value


def _class_weights(labels: np.ndarray) -> np.ndarray:
    counts = np.bincount(labels.astype(np.int64), minlength=3)
    _require(np.all(counts > 0),
             "every train class must have at least one example")
    fractions = counts.astype(np.float64) / float(counts.sum())
    return np.clip(1.0 / np.sqrt(fractions), 0.5, 4.0)


def _temperature(logits: np.ndarray, labels: np.ndarray,
                 lower: float = -6.0, upper: float = 6.0,
                 iterations: int = 96) -> float:
    def objective(log_t: float) -> float:
        scaled = logits / math.exp(log_t)
        maximum = np.max(scaled, axis=1, keepdims=True)
        log_sum = np.log(np.exp(scaled - maximum).sum(axis=1)) + maximum[:, 0]
        return float(np.mean(log_sum - scaled[np.arange(len(labels)), labels]))

    ratio = (math.sqrt(5.0) - 1.0) / 2.0
    left, right = lower, upper
    x1 = right - ratio * (right - left)
    x2 = left + ratio * (right - left)
    f1, f2 = objective(x1), objective(x2)
    for _ in range(iterations):
        if f1 <= f2:
            right, x2, f2 = x2, x1, f1
            x1 = right - ratio * (right - left)
            f1 = objective(x1)
        else:
            left, x1, f1 = x1, x2, f2
            x2 = left + ratio * (right - left)
            f2 = objective(x2)
    return math.exp((left + right) / 2.0)


def _probability_metrics(logits: np.ndarray, labels: np.ndarray,
                         temperature: float) -> dict[str, float]:
    scaled = logits / temperature
    scaled -= np.max(scaled, axis=1, keepdims=True)
    probabilities = np.exp(scaled)
    probabilities /= probabilities.sum(axis=1, keepdims=True)
    nll = -np.log(np.maximum(
        probabilities[np.arange(len(labels)), labels], 1e-300)).mean()
    accuracy = np.mean(np.argmax(probabilities, axis=1) == labels)
    return {"mean_nll": float(nll), "accuracy": float(accuracy)}


def fit_and_seal_estimator(
    *, split_arrays: Mapping[str, Mapping[str, Any]],
    partition_manifest: Mapping[str, Any],
    training_bundle_manifest: Mapping[str, Any],
    d215_contract: Mapping[str, Any], d216_contract: Mapping[str, Any],
    implementation_commit: str, device: str = "cpu",
) -> dict[str, dict[str, Any]]:
    """Fit frozen heads and return four content-addressed artifacts."""

    validate_d216_contract(d216_contract)
    d215 = validate_d215_contract(d215_contract)
    partition = validate_house_split_manifest(partition_manifest)
    bundle = validate_training_bundle_manifest(training_bundle_manifest)
    _require(bundle["partition_manifest_receipt_sha256"] ==
             partition["partition_manifest_receipt_sha256"],
             "training bundle is bound to another partition manifest")
    _hex(implementation_commit, 40, "implementation commit")
    _require(set(split_arrays) == set(SPLITS),
             "fit input must contain exactly train/calibration/audit")
    validated: dict[str, dict[str, np.ndarray]] = {}
    for split in SPLITS:
        validate_training_shard_arrays(
            split_arrays[split], split=split, partition_manifest=partition)
        validated[split] = {
            name: np.asarray(split_arrays[split][name])
            for name in ("features", "semantic_labels", "structural_labels")
        }
        _require(validated[split]["features"].shape[0] ==
                 bundle["row_counts"][split],
                 f"{split} arrays do not match sealed bundle row count")
        _require(_array_content_digest(split_arrays[split]) ==
                 bundle["split_array_content_sha256"][split],
                 f"{split} arrays do not match the sealed content digest")
    train_x = validated["train"]["features"].astype(np.float64)
    mean = train_x.mean(axis=0)
    std = np.maximum(train_x.std(axis=0, ddof=0), 1e-6)
    normalized = {
        split: ((values["features"].astype(np.float64) - mean) / std)
        .astype(np.float32)
        for split, values in validated.items()
    }
    semantic_weights = _class_weights(validated["train"]["semantic_labels"])
    structural_weights = _class_weights(
        validated["train"]["structural_labels"])
    training = d215["semantic_structural_estimator"]["training"]

    try:
        import torch
        import torch.nn.functional as torch_f
    except ImportError as error:  # pragma: no cover - environment failure
        raise D216Error("PyTorch is required for D-216 estimator training") from error
    _require(device == "cpu" or device.startswith("cuda"),
             "training device must be cpu or cuda")
    if device.startswith("cuda"):
        _require(torch.cuda.is_available(), "requested CUDA device is unavailable")
    torch.use_deterministic_algorithms(True)
    torch.manual_seed(training["seed"])
    target_device = torch.device(device)
    tensors = {
        split: torch.as_tensor(values, dtype=torch.float32,
                               device=target_device)
        for split, values in normalized.items()
    }
    labels = {
        split: {
            "semantic": torch.as_tensor(validated[split]["semantic_labels"],
                                        dtype=torch.long, device=target_device),
            "structural": torch.as_tensor(
                validated[split]["structural_labels"], dtype=torch.long,
                device=target_device),
        } for split in SPLITS
    }
    semantic_w = torch.nn.Parameter(torch.zeros((3, 396), device=target_device))
    semantic_b = torch.nn.Parameter(torch.zeros(3, device=target_device))
    structural_w = torch.nn.Parameter(torch.zeros((3, 396), device=target_device))
    structural_b = torch.nn.Parameter(torch.zeros(3, device=target_device))
    optimizer = torch.optim.AdamW(
        [semantic_w, semantic_b, structural_w, structural_b],
        lr=training["learning_rate"],
        betas=(0.9, 0.999), eps=1e-8,
        weight_decay=training["weight_decay"],
    )
    sem_class = torch.as_tensor(semantic_weights, dtype=torch.float32,
                                device=target_device)
    struct_class = torch.as_tensor(structural_weights, dtype=torch.float32,
                                   device=target_device)

    def logits(split: str) -> tuple[Any, Any]:
        x = tensors[split]
        return (x @ semantic_w.t() + semantic_b,
                x @ structural_w.t() + structural_b)

    best_metric = math.inf
    patience_reference = math.inf
    stale = 0
    best_epoch = 0
    best_state: tuple[Any, ...] | None = None
    history: list[dict[str, Any]] = []
    train_count = tensors["train"].shape[0]
    batch_size = training["batch_size"]
    for epoch in range(1, training["maximum_epochs"] + 1):
        generator = torch.Generator(device="cpu")
        generator.manual_seed(training["seed"] + epoch)
        order = torch.randperm(train_count, generator=generator)
        batch_loss_sum = 0.0
        for start in range(0, train_count, batch_size):
            indices = order[start:start + batch_size].to(target_device)
            x = tensors["train"].index_select(0, indices)
            sem_y = labels["train"]["semantic"].index_select(0, indices)
            struct_y = labels["train"]["structural"].index_select(0, indices)
            optimizer.zero_grad(set_to_none=True)
            sem_logits = x @ semantic_w.t() + semantic_b
            struct_logits = x @ structural_w.t() + structural_b
            loss = (torch_f.cross_entropy(sem_logits, sem_y, weight=sem_class) +
                    torch_f.cross_entropy(struct_logits, struct_y,
                                          weight=struct_class))
            loss.backward()
            optimizer.step()
            batch_loss_sum += float(loss.detach().cpu()) * len(indices)
        with torch.no_grad():
            sem_cal, struct_cal = logits("calibration")
            metric = float((
                torch_f.cross_entropy(sem_cal, labels["calibration"]["semantic"]) +
                torch_f.cross_entropy(struct_cal,
                                      labels["calibration"]["structural"])
            ).cpu())
        history.append({
            "epoch": epoch,
            "train_weighted_mean_loss": batch_loss_sum / train_count,
            "calibration_sum_mean_nll": metric,
        })
        if metric < best_metric:
            best_metric = metric
            best_epoch = epoch
            best_state = tuple(parameter.detach().cpu().clone() for parameter in
                               (semantic_w, semantic_b, structural_w, structural_b))
        if metric < patience_reference - training["early_stopping_minimum_delta"]:
            patience_reference = metric
            stale = 0
        else:
            stale += 1
        if stale >= training["early_stopping_patience_epochs"]:
            break
    _require(best_state is not None, "training did not produce a checkpoint")
    sem_w_np, sem_b_np, struct_w_np, struct_b_np = (
        value.numpy().astype(np.float64) for value in best_state)

    def numpy_logits(split: str) -> tuple[np.ndarray, np.ndarray]:
        x = normalized[split].astype(np.float64)
        return x @ sem_w_np.T + sem_b_np, x @ struct_w_np.T + struct_b_np

    sem_cal_np, struct_cal_np = numpy_logits("calibration")
    semantic_temperature = _temperature(
        sem_cal_np, validated["calibration"]["semantic_labels"].astype(int))
    structural_temperature = _temperature(
        struct_cal_np,
        validated["calibration"]["structural_labels"].astype(int))
    metrics: dict[str, Any] = {}
    for split in SPLITS:
        sem_logits_np, struct_logits_np = numpy_logits(split)
        metrics[split] = {
            "semantic": _probability_metrics(
                sem_logits_np, validated[split]["semantic_labels"].astype(int),
                semantic_temperature),
            "structural": _probability_metrics(
                struct_logits_np,
                validated[split]["structural_labels"].astype(int),
                structural_temperature),
        }

    normalization = _sealed({
        "schema_version": NORMALIZATION_SCHEMA,
        "model_id": d215["semantic_structural_estimator"]["model_id"],
        "partition_manifest_receipt_sha256":
            partition["partition_manifest_receipt_sha256"],
        "training_bundle_sha256": bundle["training_bundle_sha256"],
        "feature_order": [f"dinov2_{index:03d}" for index in range(384)] +
            list(GEOMETRY_FEATURE_ORDER),
        "mean": mean.tolist(), "population_std_floor_1e_6": std.tolist(),
        "train_row_count": int(train_count),
    }, "normalization_receipt_sha256")
    weights = _sealed({
        "schema_version": WEIGHTS_SCHEMA,
        "model_id": d215["semantic_structural_estimator"]["model_id"],
        "d215_inference_config_sha256":
            d216_contract["d215_binding"]["inference_config_sha256"],
        "normalization_receipt_sha256":
            normalization["normalization_receipt_sha256"],
        "semantic_weights": sem_w_np.tolist(),
        "semantic_bias": sem_b_np.tolist(),
        "structural_weights": struct_w_np.tolist(),
        "structural_bias": struct_b_np.tolist(),
        "semantic_temperature": semantic_temperature,
        "structural_temperature": structural_temperature,
    }, "weights_sha256")
    receipt = _sealed({
        "schema_version": TRAINING_RECEIPT_SCHEMA,
        "implementation_commit": implementation_commit,
        "partition_manifest_receipt_sha256":
            partition["partition_manifest_receipt_sha256"],
        "training_bundle_sha256": bundle["training_bundle_sha256"],
        "normalization_receipt_sha256":
            normalization["normalization_receipt_sha256"],
        "weights_sha256": weights["weights_sha256"],
        "device_type": target_device.type,
        "torch_version": torch.__version__,
        "seed": training["seed"],
        "optimizer": "AdamW",
        "adamw_betas": [0.9, 0.999], "adamw_epsilon": 1e-8,
        "epochs_completed": len(history), "best_epoch": best_epoch,
        "best_calibration_sum_mean_nll_before_temperature": best_metric,
        "early_stopped": len(history) < training["maximum_epochs"],
        "semantic_train_class_weights": semantic_weights.tolist(),
        "structural_train_class_weights": structural_weights.tolist(),
        "history": history, "post_temperature_metrics": metrics,
        "audit_used_for_checkpoint_or_temperature": False,
        "wall_clock_timeout_used": False,
        "production_reader_executed": False,
    }, "training_receipt_sha256")
    success = _sealed({
        "schema_version": SUCCESS_SCHEMA,
        "partition_manifest_receipt_sha256":
            partition["partition_manifest_receipt_sha256"],
        "training_bundle_sha256": bundle["training_bundle_sha256"],
        "normalization_receipt_sha256":
            normalization["normalization_receipt_sha256"],
        "weights_sha256": weights["weights_sha256"],
        "training_receipt_sha256": receipt["training_receipt_sha256"],
        "real_weight_receipt_reviewed": False,
        "production_reader_authorized": False,
    }, "success_receipt_sha256")
    return {"normalization": normalization, "weights": weights,
            "training_receipt": receipt, "success": success}
