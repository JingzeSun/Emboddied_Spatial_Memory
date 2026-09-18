"""Frozen D-215 assets, split rule, and two-head estimator core.

This module does not load models, generate training data, train weights, or read
raw episodes.  It validates the pre-run freeze, assigns whole houses to the
frozen estimator split, and applies already sealed linear-head weights to the
same public DINOv2 and RGB-D geometry features for every P01--P08 observation.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any, Mapping, Sequence

import numpy as np

from cpmt.hashing import canonical_json, clone_json


CONTRACT_SCHEMA = "vsmt-vm04-d215-frontend-freeze-v1"
ESTIMATOR_OUTPUT_SCHEMA = "vsmt-vm04-d215-semantic-structural-output-v1"
MODEL_ID = "d215.dinov2_geometry_two_linear_heads.v1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
GEOMETRY_FEATURE_ORDER = (
    "valid_depth_fraction",
    "depth_q10_m",
    "depth_q50_m",
    "depth_q90_m",
    "current_free_space_volume_m3_clipped_0_50",
    "current_visibility_volume_m3_clipped_0_50",
    "horizontal_opening_width_m_clipped_0_10",
    "forward_clearance_m_clipped_0_10",
    "left_clearance_m_clipped_0_10",
    "right_clearance_m_clipped_0_10",
    "surface_count_clipped_0_64",
    "mean_absolute_surface_normal_y",
)
SEMANTIC_LABELS = ("room", "corridor", "unknown")
STRUCTURAL_LABELS = ("basin", "bottleneck", "unknown")
AUTHORIZATION_KEYS = {
    "server_asset_download", "dependency_install", "training_data_generation",
    "estimator_training", "production_reader", "route_survey",
    "route_sealing", "raw_generation", "private_evaluation",
}
AUTOMATIC_CONFIG_SHA256 = (
    "df828bcfac74c8dc0dcb0d82731c978f8a17958755822aa44c90e5ac23db2c33"
)
SAM_ASSET_RECEIPT_SHA256 = (
    "6b6e1705ee81ec71475fb0c1b28696c98d2f30740e92a0a380554e9e85bb6a33"
)
SPLIT_RULE_SHA256 = (
    "4fa32f8940cb22516d0c004f9c4b8d7a6cb5c1cd9a85dfb6f63ef6178dd34774"
)
ESTIMATOR_CONFIG_SHA256 = (
    "4cd2bc00e8af7b4897d00d9ad90a69bdb389b1d1dd310705c1c44c5e6b720c70"
)


class D215Error(ValueError):
    """A stable D-215 freeze or inference-boundary failure."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise D215Error(message)


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _hex64(value: Any, name: str) -> str:
    _require(type(value) is str and HEX64.fullmatch(value) is not None,
             f"{name} must be a lowercase SHA-256")
    return value


def _finite_vector(value: Any, length: int, name: str) -> np.ndarray:
    result = np.asarray(value, dtype=np.float64)
    _require(result.shape == (length,) and np.isfinite(result).all(),
             f"{name} must contain {length} finite values")
    return result


def _derived_digests(value: Mapping[str, Any]) -> dict[str, str]:
    sam = value["sam2"]
    automatic = _sha({
        "automatic_mask_generator": sam["automatic_mask_generator"],
        "proposal_boundary": sam["proposal_boundary"],
    })
    asset = _sha({
        "model_id": sam["model_id"],
        "repository_url": sam["repository_url"],
        "repository_commit": sam["repository_commit"],
        "official_model_config_path": sam["official_model_config_path"],
        "official_model_config_bytes": sam["official_model_config_bytes"],
        "official_model_config_sha256": sam["official_model_config_sha256"],
        "checkpoint_url": sam["checkpoint_url"],
        "checkpoint_bytes": sam["checkpoint_bytes"],
        "checkpoint_sha256": sam["checkpoint_sha256"],
        "automatic_mask_and_boundary_config_sha256": automatic,
    })
    estimator = value["semantic_structural_estimator"]
    split_payload = {
        key: item for key, item in estimator["training_split"].items()
        if key not in {
            "actual_partition_manifest_receipt_sha256", "split_rule_sha256",
        }
    }
    split = _sha(split_payload)
    inference = _sha({
        "model_id": estimator["model_id"],
        "scenario_blind": estimator["scenario_blind"],
        "shared_for_all_p01_to_p08": estimator["shared_for_all_p01_to_p08"],
        "architecture": estimator["architecture"],
        "public_geometry_feature_order":
            estimator["public_geometry_feature_order"],
        "normalization": estimator["normalization"],
        "forbidden_features": estimator["forbidden_features"],
        "training": estimator["training"],
        "training_split_rule_sha256": split,
        "label_boundary": estimator["label_boundary"],
    })
    return {
        "automatic": automatic, "asset": asset,
        "split": split, "inference": inference,
    }


def validate_d215_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Validate every frozen D-215 field while keeping run gates closed."""

    value = clone_json(dict(contract))
    _require(set(value) == {
        "schema_version", "decision_id", "status", "authorization", "sam2",
        "semantic_structural_estimator", "p08_qualification",
        "production_reader_preconditions",
    }, "D-215 contract has unexpected fields")
    _require(value["schema_version"] == CONTRACT_SCHEMA and
             value["decision_id"] == "D-215" and value["status"] ==
             "frozen_assets_estimator_split_and_p08_thresholds_training_and_reader_closed",
             "D-215 contract identity or status changed")
    _require(set(value["authorization"]) == AUTHORIZATION_KEYS and
             all(item is False for item in value["authorization"].values()),
             "D-215 must keep every execution gate closed")
    sam = value["sam2"]
    _require(sam["model_id"] ==
             "sam2.1.hiera_small.per_frame_automatic_mask_generator" and
             sam["repository_commit"] ==
             "2b90b9f5ceec907a1c18123530e92e794ad901a4" and
             sam["official_model_config_bytes"] == 3761 and
             sam["official_model_config_sha256"] ==
             "0f36b91e86e58d06c87e42997166212468b88b98b60e4d816d5e4d4d088b6f55" and
             sam["checkpoint_bytes"] == 184416285 and
             sam["checkpoint_sha256"] ==
             "6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38",
             "D-215 pinned SAM2 asset changed")
    _require(sam["automatic_mask_generator"] == {
        "points_per_side": 32, "points_per_batch": 64,
        "pred_iou_thresh": 0.8, "stability_score_thresh": 0.95,
        "stability_score_offset": 1.0, "box_nms_thresh": 1.0,
        "crop_n_layers": 0, "crop_nms_thresh": 1.0,
        "min_mask_region_area": 0, "output_mode": "binary_mask",
    }, "D-215 SAM2 automatic-mask config changed")
    boundary = sam["proposal_boundary"]
    _require(boundary["input_fields"] == ["current_public_rgb"] and
             boundary["cross_frame_memory_enabled"] is False and
             boundary["minimum_visible_pixels"] == 196 and
             boundary["maximum_proposals_per_frame"] == 64 and
             boundary["overlap_policy"] ==
             "preserve_independent_overlapping_proposals",
             "D-215 SAM2 public proposal boundary changed")
    estimator = value["semantic_structural_estimator"]
    architecture = estimator["architecture"]
    _require(estimator["model_id"] == MODEL_ID and
             estimator["scenario_blind"] is True and
             estimator["shared_for_all_p01_to_p08"] is True and
             architecture["dinov2_descriptor_dimension"] == 384 and
             architecture["public_geometry_feature_dimension"] == 12 and
             architecture["concatenated_feature_dimension"] == 396 and
             architecture["hidden_layers"] == 0 and
             architecture["semantic_labels"] == list(SEMANTIC_LABELS) and
             architecture["structural_labels"] == list(STRUCTURAL_LABELS) and
             estimator["public_geometry_feature_order"] ==
             list(GEOMETRY_FEATURE_ORDER),
             "D-215 estimator architecture or public features changed")
    forbidden = estimator["forbidden_features"]
    _require(all(item in forbidden for item in (
        "scenario_id", "scenario_role", "route_index", "house_id",
        "reachable_grid", "room_metadata", "instance_mask", "object_id",
        "teacher", "future",
    )), "D-215 estimator forbidden-input list weakened")
    split = estimator["training_split"]
    _require(split["source_manifest_sha256"] ==
             "7db1df1edb714162089b56e62f5258a947c5c6ddc38ed2b7082582d4659269bd" and
             split["eligible_house_ids_sha256"] ==
             "31b9d819afafcbef8d9bc3466fa00d49e6605cfbe1af3827ddf1a25fa0fb6d87" and
             split["split_unit"] == "house_id" and
             split["train_buckets_inclusive"] == [0, 79] and
             split["calibration_buckets_inclusive"] == [80, 89] and
             split["audit_buckets_inclusive"] == [90, 99] and
             split["excluded_house_ids"] ==
             ["train:004270", "train:008243"] and
             split["actual_partition_manifest_receipt_sha256"] is None and
             split["cross_split_house_overlap_allowed"] is False and
             split["frame_or_route_level_random_split_allowed"] is False,
             "D-215 estimator split boundary changed")
    label = estimator["label_boundary"]
    _require(label["semantic_annotators_receive_scenario_or_house_identity"] is False
             and label["reference_labels_available_to_inference_or_cache"] is False
             and label["p0_house_private_metadata_used_for_training"] is False
             and label["unknown_required_for_ambiguous_or_disagreeing_label"] is True,
             "D-215 training-label isolation changed")
    digests = _derived_digests(value)
    _require(sam["automatic_mask_and_boundary_config_sha256"] ==
             digests["automatic"] and
             sam["asset_receipt_sha256"] == digests["asset"] and
             split["split_rule_sha256"] == digests["split"] and
             estimator["inference_config_sha256"] == digests["inference"],
             "D-215 derived freeze digest mismatch")
    _require(digests == {
        "automatic": AUTOMATIC_CONFIG_SHA256,
        "asset": SAM_ASSET_RECEIPT_SHA256,
        "split": SPLIT_RULE_SHA256,
        "inference": ESTIMATOR_CONFIG_SHA256,
    }, "D-215 frozen payload changed even though it was rehashed")
    for name in (
        "automatic_mask_and_boundary_config_sha256", "asset_receipt_sha256",
    ):
        _hex64(sam[name], f"D-215 SAM2 {name}")
    _hex64(split["split_rule_sha256"], "D-215 split-rule digest")
    _hex64(estimator["inference_config_sha256"],
           "D-215 estimator config digest")
    _require(estimator["normalization_receipt_sha256"] is None and
             estimator["weights_sha256"] is None and
             estimator["training_receipt_sha256"] is None,
             "D-215 unrun estimator artifacts must remain null")
    _require(value["p08_qualification"] == {
        "basin_probability_minimum": 0.7,
        "bottleneck_probability_minimum": 0.7,
        "fragment_descriptor_cosine_minimum": 0.85,
        "fragment_centroid_distance_maximum_m": 0.35,
        "minimum_distinct_views_per_basin": 2,
        "qualifying_role_must_be_unique_argmax": True,
        "threshold_equality_passes": True,
        "room_corridor_semantics_gate_identity_or_qualification": False,
        "threshold_selection_source":
            "a_priori_conservative_contract_not_route_yield",
        "failure_policy":
            "retain_p08_construction_failure_without_threshold_change_route_reselection_or_replacement",
    }, "D-215 P08 qualification freeze changed")
    _require(value["production_reader_preconditions"] and
             value["production_reader_preconditions"][-1] ==
             "keep_all_execution_authorizations_false_until_a_separate_reader_commit",
             "D-215 production reader gate changed")
    return value


def assign_estimator_house_split(
    house_id: str, *, contract: Mapping[str, Any],
) -> str:
    """Assign one whole house without inspecting frames, labels, or yield."""

    frozen = validate_d215_contract(contract)
    _require(type(house_id) is str and house_id,
             "D-215 house ID must be a nonempty string")
    split = frozen["semantic_structural_estimator"]["training_split"]
    if house_id in split["excluded_house_ids"]:
        return "excluded"
    payload = (f"{split['split_salt']}|{split['source_manifest_sha256']}|"
               f"{house_id}").encode("utf-8")
    bucket = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") % 100
    if bucket <= 79:
        return "train"
    if bucket <= 89:
        return "calibration"
    return "audit"


def _temperature_softmax(logits: np.ndarray, temperature: float) -> np.ndarray:
    _require(type(temperature) in {int, float} and
             math.isfinite(float(temperature)) and float(temperature) > 0.0,
             "D-215 temperature must be finite and positive")
    scaled = logits / float(temperature)
    scaled -= np.max(scaled)
    values = np.exp(scaled)
    return values / values.sum()


def run_frozen_two_head_estimator(
    *, dinov2_descriptor: Sequence[float],
    public_geometry_features: Mapping[str, float],
    normalization_mean: Sequence[float], normalization_std: Sequence[float],
    semantic_weights: Any, semantic_bias: Sequence[float],
    structural_weights: Any, structural_bias: Sequence[float],
    semantic_temperature: float, structural_temperature: float,
    weights_sha256: str, normalization_receipt_sha256: str,
    training_receipt_sha256: str,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply sealed weights to public features; no scenario argument exists."""

    frozen = validate_d215_contract(contract)
    estimator = frozen["semantic_structural_estimator"]
    _require(estimator["weights_sha256"] is not None and
             estimator["normalization_receipt_sha256"] is not None and
             estimator["training_receipt_sha256"] is not None,
             "D-215 estimator has not been trained and sealed")
    _require(weights_sha256 == estimator["weights_sha256"] and
             normalization_receipt_sha256 ==
             estimator["normalization_receipt_sha256"] and
             training_receipt_sha256 == estimator["training_receipt_sha256"],
             "D-215 estimator artifact receipt mismatch")
    descriptor = _finite_vector(dinov2_descriptor, 384, "DINOv2 descriptor")
    _require(set(public_geometry_features) == set(GEOMETRY_FEATURE_ORDER),
             "D-215 public geometry feature schema changed")
    geometry = _finite_vector(
        [public_geometry_features[name] for name in GEOMETRY_FEATURE_ORDER],
        12, "public geometry features",
    )
    raw = np.concatenate((descriptor, geometry))
    mean = _finite_vector(normalization_mean, 396, "normalization mean")
    std = _finite_vector(normalization_std, 396, "normalization std")
    _require(np.all(std >= 1e-6), "D-215 normalization std is below its floor")
    normalized = (raw - mean) / std
    semantic_w = np.asarray(semantic_weights, dtype=np.float64)
    structural_w = np.asarray(structural_weights, dtype=np.float64)
    _require(semantic_w.shape == (3, 396) and np.isfinite(semantic_w).all() and
             structural_w.shape == (3, 396) and
             np.isfinite(structural_w).all(),
             "D-215 estimator weight shape is invalid")
    semantic_b = _finite_vector(semantic_bias, 3, "semantic bias")
    structural_b = _finite_vector(structural_bias, 3, "structural bias")
    _hex64(weights_sha256, "D-215 weights digest")
    _hex64(normalization_receipt_sha256,
           "D-215 normalization receipt digest")
    _hex64(training_receipt_sha256, "D-215 training receipt digest")
    semantic = _temperature_softmax(
        semantic_w @ normalized + semantic_b, semantic_temperature,
    )
    structural = _temperature_softmax(
        structural_w @ normalized + structural_b, structural_temperature,
    )
    value = {
        "schema_version": ESTIMATOR_OUTPUT_SCHEMA,
        "model_id": MODEL_ID,
        "inference_config_sha256": estimator["inference_config_sha256"],
        "weights_sha256": weights_sha256,
        "normalization_receipt_sha256": normalization_receipt_sha256,
        "training_receipt_sha256": training_receipt_sha256,
        "public_feature_sha256": _sha({
            "dinov2_descriptor": descriptor.tolist(),
            "public_geometry_features": {
                name: float(public_geometry_features[name])
                for name in GEOMETRY_FEATURE_ORDER
            },
        }),
        "semantic_probabilities": {
            label: float(semantic[index])
            for index, label in enumerate(SEMANTIC_LABELS)
        },
        "structural_role_probabilities": {
            label: float(structural[index])
            for index, label in enumerate(STRUCTURAL_LABELS)
        },
        "scenario_or_route_input_used": False,
    }
    value["inference_receipt_sha256"] = _sha(value)
    return value
