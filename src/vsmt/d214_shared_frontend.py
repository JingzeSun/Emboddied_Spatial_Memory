"""Scenario-blind shared RGB-D front-end core for D-214.

The front end consumes only the current public RGB-D frame, camera calibration,
a causal episode-relative pose, a public pose belief, and the incoming action
summary.  It emits observations, not persistent identities.  In particular a
SAM proposal is a ``fragment`` and a full-frame place descriptor is a
``place_observation``; neither becomes an entity or place ID here.

Real SAM, DINOv2, and structural-estimator assets are verified by their own loaders.
This module composes their public outputs, seals identical method caches, and
implements the P04/P08 qualification algorithms without accepting a scenario
identifier in the materialization API.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import inspect
import math
import re
from typing import Any, Mapping, Sequence

import numpy as np

from cpmt.hashing import canonical_json, clone_json

from .l1_entities import (
    DINORegionConfig,
    PublicGeometryConfig,
    materialize_l1_entity_observation,
    pool_dinov2_region_descriptor,
)
from .l1_masks import AnonymousMask
from .l1_structures import (
    FreeSpaceFrustum,
    FreeSpaceMaterializationConfig,
    SurfaceMaterializationConfig,
    assemble_free_space_history,
    materialize_public_free_space,
    materialize_public_surfaces,
    materialize_public_visibility,
)


CONTRACT_SCHEMA = "vsmt-vm04-d214-shared-rgbd-frontend-contract-v2"
FRAME_SCHEMA = "vsmt-vm04-d214-shared-rgbd-frame-cache-v2"
EPISODE_SCHEMA = "vsmt-vm04-d214-shared-rgbd-episode-cache-v2"
P04_SCHEMA = "vsmt-vm04-d214-p04-qualification-v1"
P08_SCHEMA = "vsmt-vm04-d214-p08-qualification-v2"
RETIREMENT_SCHEMA = "vsmt-vm04-d214-legacy-grid-retirement-readiness-v1"
FRAGMENT_SOURCE_ID = "l2.sam2.1_hiera_small.fragment.dinov2_vits14.public_depth.v1"
PLACE_SOURCE_ID = "l2.dinov2_vits14.public_rgbd.non_grid_place_observation.v1"
MAIN_METHODS = ("VSMT", "TAF", "ELU", "WFR", "LOW")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_KEY_TOKENS = (
    "scenario_id", "scenario_role", "world_pose", "reachable_grid",
    "room_metadata", "instance_mask", "object_id", "private_entity",
    "teacher", "reference_transaction", "future_observation", "future_state",
)
AUTHORIZATION_KEYS = {
    "route_survey", "route_sealing", "raw_generation",
    "frontend_materialization", "adapter_materialization",
    "private_evaluation", "training", "validation_effect", "confirmation",
}
PUBLIC_INPUTS = [
    "current_rgb_uint8", "current_depth_m_float32", "camera_intrinsics",
    "causal_episode_relative_camera_pose", "continuous_pose_belief",
    "incoming_transition_action_summary", "prior_public_free_space",
]
FORBIDDEN_INPUTS = [
    "scenario_id", "scenario_role", "simulator_world_pose",
    "reachable_grid_place_identity", "room_metadata", "instance_mask",
    "object_id", "private_entity_id", "teacher", "reference_transaction",
    "future_observation", "future_state",
]


class D214Error(ValueError):
    """A stable D-214 contract, cache, or qualification failure."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise D214Error(message)


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _payload_sha(value: Mapping[str, Any], field: str) -> str:
    payload = clone_json(dict(value))
    payload.pop(field, None)
    return _sha(payload)


def _hex64(value: Any, name: str) -> str:
    _require(type(value) is str and HEX64.fullmatch(value) is not None,
             f"{name} must be a lowercase SHA-256")
    return value


def _finite(value: Any, name: str) -> float:
    _require(type(value) in {int, float} and math.isfinite(float(value)),
             f"{name} must be finite")
    return float(value)


def _exact(value: Any, expected: set[str], name: str) -> None:
    _require(type(value) is dict and set(value) == expected,
             f"{name} has unexpected fields")


def _reject_forbidden_keys(value: Any, path: str = "") -> None:
    if type(value) is dict:
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered == "is_world_pose" and child is False:
                continue
            _require(not any(token in lowered for token in FORBIDDEN_KEY_TOKENS),
                     f"D-214 public cache contains forbidden field {path}/{key}")
            _reject_forbidden_keys(child, f"{path}/{key}")
    elif type(value) is list:
        for index, child in enumerate(value):
            _reject_forbidden_keys(child, f"{path}/{index}")


def validate_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the approved but intentionally non-executable D-214 contract."""

    value = clone_json(dict(contract))
    _exact(value, {
        "schema_version", "decision_id", "status", "authorization",
        "implementation_boundary", "global_scope", "public_inputs",
        "forbidden_inputs", "shared_outputs", "asset_state",
        "scenario_qualification", "legacy_grid_retirement",
    }, "D-214 contract")
    _require(value["schema_version"] == CONTRACT_SCHEMA and
             value["decision_id"] == "D-214" and
             value["status"] ==
             "d219_structural_only_estimator_and_p08_thresholds_frozen_reader_pending",
             "D-214 contract identity or status changed")
    _exact(value["authorization"], AUTHORIZATION_KEYS,
           "D-214 authorization")
    _require(all(item is False for item in value["authorization"].values()),
             "D-214 implementation contract must keep every run gate closed")
    _require(value["implementation_boundary"] == {
        "public_output_composition_and_cache_core_implemented": True,
        "sam_dinov2_structural_inference_orchestration_implemented": False,
        "production_raw_reader_implemented": False,
        "server_executable": False,
    }, "D-214 implementation boundary changed")
    _require(value["public_inputs"] == PUBLIC_INPUTS and
             value["forbidden_inputs"] == FORBIDDEN_INPUTS,
             "D-214 public or forbidden input boundary changed")
    scope = value["global_scope"]
    _require(scope["covered_scenarios"] == [
        "P01", "P02", "P03", "P04", "P05", "P06", "P07", "P08",
    ] and scope["frontend_receives_scenario_id"] is False and
             scope["one_schema_for_every_scenario"] is True and
             scope["identical_cached_bytes_for_main_methods"] == list(MAIN_METHODS)
             and scope["method_private_frontend_allowed"] is False and
             scope["keyframe_policy"] == "every_saved_public_observation",
             "D-214 global scenario-blind scope changed")
    _require(scope["p09_p10_schema_compatible_but_execution_deferred"] is True,
             "D-214 deferred P09/P10 boundary changed")
    outputs = value["shared_outputs"]
    _require(outputs["place_observation"]["metric_grid_defines_identity"] is False
             and outputs["place_observation"]
             ["structural_class_defines_place_identity"] is False and
             outputs["fragment_observation"]
             ["persistent_entity_identity_assigned"] is False,
             "D-214 output identity boundary changed")
    _require(outputs["cache"] == {
        "content_addressed": True,
        "immutable": True,
        "contains_raw_paths": False,
        "contains_private_crosswalk": False,
    }, "D-214 immutable public cache boundary changed")
    assets = value["asset_state"]
    _require(assets["dinov2"] == {
        "model_id": "dinov2.vits14",
        "repository_commit":
            "7764ea0f912e53c92e82eb78a2a1631e92725fc8",
        "checkpoint_sha256":
            "b938bf1bc15cd2ec0feacfe3a1bb553fe8ea9ca46a7e1d8d00217f29aef60cd9",
    }, "D-214 DINOv2 asset pin changed")
    _require(assets["sam2"] == {
        "model_id": "sam2.1.hiera_small.per_frame_automatic_mask_generator",
        "repository_commit": "2b90b9f5ceec907a1c18123530e92e794ad901a4",
        "official_model_config_sha256":
            "0f36b91e86e58d06c87e42997166212468b88b98b60e4d816d5e4d4d088b6f55",
        "checkpoint_sha256":
            "6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38",
        "automatic_mask_generator_config_sha256":
            "df828bcfac74c8dc0dcb0d82731c978f8a17958755822aa44c90e5ac23db2c33",
        "assets_receipt_sha256":
            "6b6e1705ee81ec71475fb0c1b28696c98d2f30740e92a0a380554e9e85bb6a33",
    }, "D-214 frozen SAM2 asset state changed")
    _require(assets["structural_estimator"] == {
        "structural_labels": ["basin", "bottleneck", "unknown"],
        "model_id": "d219.dinov2_geometry_single_structural_head.v1",
        "training_source_manifest_sha256":
            "7db1df1edb714162089b56e62f5258a947c5c6ddc38ed2b7082582d4659269bd",
        "split_rule_sha256":
            "4fa32f8940cb22516d0c004f9c4b8d7a6cb5c1cd9a85dfb6f63ef6178dd34774",
        "actual_partition_manifest_receipt_sha256": None,
        "weights_sha256": None,
        "normalization_receipt_sha256": None,
        "training_receipt_sha256": None,
        "inference_config_sha256": None,
    }, "D-214 frozen estimator state changed")
    qualification = value["scenario_qualification"]
    _require(set(qualification) == {
        "P04", "P08", "P01_P02_P03_P05_P06_P07",
    }, "D-214 route qualification coverage changed")
    p04 = value["scenario_qualification"]["P04"]
    _require(p04["minimum_public_nominal_separation_m"] == 1.5 and
             p04["absolute_similarity_threshold"] is None and
             p04["old_quadrant_rgbd_descriptor_allowed"] is False,
             "D-214 P04 qualification changed")
    p08 = value["scenario_qualification"]["P08"]
    _require(p08["minimum_distinct_views_per_basin"] == 2 and
             p08["basin_probability_minimum"] == 0.7 and
             p08["bottleneck_probability_minimum"] == 0.7 and
             p08["fragment_descriptor_cosine_minimum"] == 0.85 and
             p08["fragment_centroid_distance_maximum_m"] == 0.35 and
             p08["qualifying_role_must_be_unique_argmax"] is True,
             "D-214 frozen P08 qualification changed")
    _require(qualification["P01_P02_P03_P05_P06_P07"] == {
        "existing_geometric_route_templates_may_be_reused": True,
        "must_rebind_to_d214_cache": True,
        "reachable_grid_role":
            "route_planning_and_mechanical_verification_only",
    }, "D-214 non-P04/P08 route rebinding changed")
    retirement = value["legacy_grid_retirement"]
    _require(retirement["retirement_requested_by_user"] is True and
             retirement["delete_now"] is False and
             retirement["wildcard_deletion_allowed"] is False,
             "D-214 legacy-grid retirement safety changed")
    _require(retirement["preconditions"] == [
        "all_new_d214_caches_generated",
        "all_cache_and_source_digests_verified",
        "p04_and_p08_requalified",
        "p01_to_p08_routes_rebound",
        "reviewed_retirement_receipt_lists_exact_targets",
        "no_reproduction_dependency_points_to_targets",
    ], "D-214 legacy-grid retirement preconditions changed")
    return value


@dataclass(frozen=True)
class D214FrontendConfig:
    descriptor: DINORegionConfig
    fragment_geometry: PublicGeometryConfig
    surface: SurfaceMaterializationConfig
    free_space: FreeSpaceMaterializationConfig
    frontend_config_sha256: str

    def __post_init__(self) -> None:
        _hex64(self.frontend_config_sha256, "D-214 frontend config digest")


@dataclass(frozen=True)
class P08EligibilityConfig:
    basin_probability_minimum: float
    bottleneck_probability_minimum: float
    fragment_descriptor_cosine_minimum: float
    fragment_centroid_distance_maximum_m: float
    minimum_distinct_views_per_basin: int = 2
    qualifying_role_must_be_unique_argmax: bool = True

    def __post_init__(self) -> None:
        for name in (
            "basin_probability_minimum", "bottleneck_probability_minimum",
            "fragment_descriptor_cosine_minimum",
        ):
            value = _finite(getattr(self, name), name)
            _require(0.0 <= value <= 1.0, f"{name} must lie in [0, 1]")
        _require(_finite(
            self.fragment_centroid_distance_maximum_m,
            "fragment_centroid_distance_maximum_m",
        ) > 0.0, "fragment centroid distance must be positive")
        _require(type(self.minimum_distinct_views_per_basin) is int and
                 self.minimum_distinct_views_per_basin >= 2,
                 "P08 needs at least two distinct views per basin")
        _require(self.qualifying_role_must_be_unique_argmax is True,
                 "D-215 requires a unique structural-role argmax")
        _require((self.basin_probability_minimum,
                  self.bottleneck_probability_minimum,
                  self.fragment_descriptor_cosine_minimum,
                  self.fragment_centroid_distance_maximum_m,
                  self.minimum_distinct_views_per_basin) ==
                 (0.7, 0.7, 0.85, 0.35, 2),
                 "D-215 P08 thresholds are frozen")


def _probabilities(value: Mapping[str, Any], labels: tuple[str, ...], name: str) -> dict[str, float]:
    _exact(value, set(labels), name)
    result = {label: _finite(value[label], f"{name}.{label}") for label in labels}
    _require(all(0.0 <= item <= 1.0 for item in result.values()) and
             abs(sum(result.values()) - 1.0) <= 1e-6,
             f"{name} must be a normalized probability vector")
    return result


def _pose_belief(value: Mapping[str, Any], observation_index: int) -> dict[str, Any]:
    record = clone_json(dict(value))
    _exact(record, {
        "schema_version", "observation_index", "frame", "mean_x_y_z_yaw",
        "covariance_diagonal", "source_id", "is_world_pose",
        "defines_place_identity", "belief_sha256",
    }, "D-214 pose belief")
    _require(record["observation_index"] == observation_index and
             record["frame"] == "episode_relative_observation_zero_origin" and
             record["is_world_pose"] is False and
             record["defines_place_identity"] is False,
             "D-214 pose belief is not causal episode-relative evidence")
    mean = [_finite(item, "pose belief mean") for item in record["mean_x_y_z_yaw"]]
    covariance = [_finite(item, "pose belief covariance")
                  for item in record["covariance_diagonal"]]
    _require(len(mean) == 4 and len(covariance) == 4 and
             all(item >= 0.0 for item in covariance),
             "D-214 pose belief needs four means and variances")
    _require(record["belief_sha256"] == _payload_sha(record, "belief_sha256"),
             "D-214 pose belief digest mismatch")
    return record


def _camera_pose(value: Mapping[str, Any]) -> dict[str, Any]:
    record = clone_json(dict(value))
    _exact(record, {"position_m", "quaternion_xyzw", "is_world_pose", "source_id"},
           "D-214 causal camera pose")
    _require(record["is_world_pose"] is False and
             type(record["source_id"]) is str and record["source_id"],
             "D-214 camera pose must be causal and episode-relative")
    position = [_finite(item, "camera position") for item in record["position_m"]]
    quaternion = [_finite(item, "camera quaternion")
                  for item in record["quaternion_xyzw"]]
    _require(len(position) == 3 and len(quaternion) == 4 and
             abs(math.sqrt(sum(item * item for item in quaternion)) - 1.0) <= 1e-6,
             "D-214 camera pose shape or quaternion is invalid")
    return {"position_m": position, "quaternion_xyzw": quaternion}


def materialize_shared_rgbd_frame(
    *, observation_index: int, decision_time_s: float,
    rgb_sha256: str, depth_sha256: str,
    camera_calibration: Mapping[str, Any],
    causal_camera_pose: Mapping[str, Any], pose_belief: Mapping[str, Any],
    incoming_transition_action_summary: Mapping[str, Any] | None,
    depth_m: Any, patch_tokens: Any,
    public_fragment_masks: Sequence[AnonymousMask],
    l2_proposal_receipt_sha256: str,
    structural_role_probabilities: Mapping[str, Any],
    structural_model_receipt_sha256: str,
    prior_free_space: Sequence[Sequence[FreeSpaceFrustum]],
    config: D214FrontendConfig,
) -> dict[str, Any]:
    """Materialize one scenario-blind shared frame cache.

    The signature deliberately has no scenario, route-role, private, teacher,
    or future argument.  Callers must run SAM and DINO before this boundary
    using their separately verified frozen assets.
    """

    _require(type(observation_index) is int and observation_index >= 0,
             "D-214 observation index is invalid")
    time_s = _finite(decision_time_s, "D-214 decision time")
    _require(time_s >= 0.0, "D-214 decision time must be nonnegative")
    _hex64(rgb_sha256, "D-214 RGB digest")
    _hex64(depth_sha256, "D-214 depth digest")
    _hex64(l2_proposal_receipt_sha256, "D-214 proposal receipt digest")
    _hex64(structural_model_receipt_sha256, "D-214 structural receipt digest")
    _require(type(config) is D214FrontendConfig, "D-214 config type is invalid")
    belief = _pose_belief(pose_belief, observation_index)
    geometry_pose = _camera_pose(causal_camera_pose)
    structural = _probabilities(
        structural_role_probabilities, ("basin", "bottleneck", "unknown"),
        "D-214 structural probabilities",
    )
    masks = tuple(public_fragment_masks)
    _require(all(type(item) is AnonymousMask for item in masks),
             "D-214 fragment proposals must be AnonymousMask values")

    fragments = []
    for mask in masks:
        observed = materialize_l1_entity_observation(
            mask, patch_tokens, depth_m, camera_calibration, geometry_pose,
            config.descriptor, config.fragment_geometry,
        )
        fragments.append({
            "region_id": "",
            "structure_kind": "fragment",
            "mask_sha256": observed.mask_sha256,
            "descriptor": list(observed.descriptor.values),
            "centroid_m": list(observed.geometry.centroid_m),
            "extent_m": list(observed.geometry.extent_m),
            "reliability": observed.geometry.reliability,
            "proposal_source_id": FRAGMENT_SOURCE_ID,
        })
    fragments.sort(key=lambda row: (row["mask_sha256"], row["centroid_m"]))

    surfaces = materialize_public_surfaces(
        depth_m, camera_calibration, geometry_pose, patch_tokens,
        config.descriptor, config.surface,
    )
    surface_records = [item.public_record("") for item in surfaces]
    surface_records.sort(key=lambda row: (row["mask_sha256"], row["centroid_m"]))
    region_records = [*fragments, *surface_records]
    for index, record in enumerate(region_records):
        record["region_id"] = f"region:{index:04d}"

    full_mask = np.ones(
        (config.descriptor.image_height, config.descriptor.image_width),
        dtype=np.bool_,
    )
    place_descriptor = pool_dinov2_region_descriptor(
        patch_tokens, full_mask, config.descriptor,
    )
    current_free_space = materialize_public_free_space(
        depth_m, camera_calibration, geometry_pose,
        time_s=time_s, depth_sha256=depth_sha256,
        camera_calibration_and_pose_sha256=_sha({
            "calibration": clone_json(dict(camera_calibration)),
            "causal_pose": geometry_pose,
        }), config=config.free_space,
    )
    free_space = assemble_free_space_history(
        [*prior_free_space, current_free_space],
        rolling_public_observation_times=config.free_space.rolling_public_observation_times,
    )
    visibility = materialize_public_visibility(
        current_free_space, surface_clearance_m=config.free_space.surface_clearance_m,
    )
    finite_depth = np.asarray(depth_m)
    valid_fraction = float(np.isfinite(finite_depth).mean())
    surface_support = sorted(record["mask_sha256"] for record in surface_records)
    place = {
        "place_observation_id": f"place-observation:{observation_index:04d}",
        "observation_index": observation_index,
        "persistent_place_id": None,
        "identity_assigned": False,
        "metric_grid_identity_used": False,
        "descriptor": list(place_descriptor.values),
        "pose_belief_sha256": belief["belief_sha256"],
        "pose_belief_mean_x_y_z_yaw": clone_json(belief["mean_x_y_z_yaw"]),
        "pose_belief_covariance_diagonal": clone_json(
            belief["covariance_diagonal"]),
        "structural_role_probabilities": structural,
        "structural_class_defines_identity": False,
        "surface_support_sha256s": surface_support,
        "free_space_support_sha256": _sha(free_space),
        "reliability": valid_fraction,
        "proposal_source_id": PLACE_SOURCE_ID,
    }
    place["place_observation_sha256"] = _sha(place)
    transition = (None if incoming_transition_action_summary is None else
                  clone_json(dict(incoming_transition_action_summary)))
    if transition is not None:
        _reject_forbidden_keys(transition, "/incoming_transition_action_summary")
    frame = {
        "schema_version": FRAME_SCHEMA,
        "observation_index": observation_index,
        "decision_time_s": time_s,
        "keyframe_policy": "every_saved_public_observation",
        "rgb_sha256": rgb_sha256,
        "depth_sha256": depth_sha256,
        "camera_calibration_sha256": _sha(dict(camera_calibration)),
        "pose_belief": belief,
        "incoming_transition_action_summary": transition,
        "fragment_observations": [
            row for row in region_records if row["structure_kind"] == "fragment"
        ],
        "surface_observations": [
            row for row in region_records if row["structure_kind"] == "surface"
        ],
        "place_observation": place,
        "free_space_observations": free_space,
        "visibility_observations": visibility,
        "l2_proposal_receipt_sha256": l2_proposal_receipt_sha256,
        "structural_model_receipt_sha256": structural_model_receipt_sha256,
        "frontend_config_sha256": config.frontend_config_sha256,
        "public_only": True,
    }
    _reject_forbidden_keys(frame)
    frame["frame_cache_sha256"] = _sha(frame)
    return validate_frame_cache(frame)


def validate_frame_cache(frame: Mapping[str, Any]) -> dict[str, Any]:
    value = clone_json(dict(frame))
    _exact(value, {
        "schema_version", "observation_index", "decision_time_s",
        "keyframe_policy", "rgb_sha256", "depth_sha256",
        "camera_calibration_sha256", "pose_belief",
        "incoming_transition_action_summary", "fragment_observations",
        "surface_observations", "place_observation",
        "free_space_observations", "visibility_observations",
        "l2_proposal_receipt_sha256", "structural_model_receipt_sha256",
        "frontend_config_sha256", "public_only", "frame_cache_sha256",
    }, "D-214 frame cache")
    _require(value["schema_version"] == FRAME_SCHEMA and
             value["public_only"] is True and
             value["keyframe_policy"] == "every_saved_public_observation",
             "D-214 frame cache identity changed")
    index = value["observation_index"]
    _require(type(index) is int and index >= 0, "D-214 cache index is invalid")
    _pose_belief(value["pose_belief"], index)
    for field in (
        "rgb_sha256", "depth_sha256", "camera_calibration_sha256",
        "l2_proposal_receipt_sha256", "structural_model_receipt_sha256",
        "frontend_config_sha256", "frame_cache_sha256",
    ):
        _hex64(value[field], field)
    fragments = value["fragment_observations"]
    surfaces = value["surface_observations"]
    _require(type(fragments) is list and type(surfaces) is list,
             "D-214 region observations must be arrays")
    regions = [*fragments, *surfaces]
    _require([row["region_id"] for row in regions] == [
        f"region:{ordinal:04d}" for ordinal in range(len(regions))
    ], "D-214 regions must use contiguous packet-local ordinals")
    _require(all(row["structure_kind"] == "fragment" for row in fragments) and
             all(row["structure_kind"] == "surface" for row in surfaces),
             "D-214 fragments or surfaces changed structure kind")
    region_keys = {
        "region_id", "structure_kind", "mask_sha256", "descriptor",
        "centroid_m", "extent_m", "reliability", "proposal_source_id",
    }
    for ordinal, row in enumerate(regions):
        _exact(row, region_keys, f"D-214 region {ordinal}")
        _hex64(row["mask_sha256"], f"D-214 region {ordinal} mask digest")
        descriptor = [_finite(item, "D-214 region descriptor")
                      for item in row["descriptor"]]
        centroid = [_finite(item, "D-214 region centroid")
                    for item in row["centroid_m"]]
        extent = [_finite(item, "D-214 region extent")
                  for item in row["extent_m"]]
        reliability = _finite(row["reliability"], "D-214 region reliability")
        _require(descriptor and len(centroid) == 3 and len(extent) == 3 and
                 all(item >= 0.0 for item in extent) and
                 0.0 <= reliability <= 1.0,
                 "D-214 region geometry or reliability is invalid")
        expected_source = (FRAGMENT_SOURCE_ID if row["structure_kind"] == "fragment"
                           else "l1.public_depth.planar_surface.v1")
        _require(row["proposal_source_id"] == expected_source,
                 "D-214 region proposal source changed")
    place = value["place_observation"]
    _exact(place, {
        "place_observation_id", "observation_index", "persistent_place_id",
        "identity_assigned", "metric_grid_identity_used", "descriptor",
        "pose_belief_sha256", "pose_belief_mean_x_y_z_yaw",
        "pose_belief_covariance_diagonal", "structural_role_probabilities",
        "structural_class_defines_identity",
        "surface_support_sha256s", "free_space_support_sha256", "reliability",
        "proposal_source_id", "place_observation_sha256",
    }, "D-214 place observation")
    _require(place["persistent_place_id"] is None and
             place["identity_assigned"] is False and
             place["metric_grid_identity_used"] is False and
             place["structural_class_defines_identity"] is False,
             "D-214 place observation assigned an identity")
    _require(place["observation_index"] == index and
             place["place_observation_id"] ==
             f"place-observation:{index:04d}" and
             place["proposal_source_id"] == PLACE_SOURCE_ID and
             place["pose_belief_sha256"] ==
             value["pose_belief"]["belief_sha256"],
             "D-214 place observation binding changed")
    descriptor = [_finite(item, "D-214 place descriptor")
                  for item in place["descriptor"]]
    _require(descriptor and abs(math.sqrt(sum(item * item for item in descriptor))
                                - 1.0) <= 1e-5,
             "D-214 place descriptor must be unit normalized")
    _hex64(place["free_space_support_sha256"],
           "D-214 place free-space support")
    _require(type(place["surface_support_sha256s"]) is list and
             place["surface_support_sha256s"] ==
             sorted(set(place["surface_support_sha256s"])),
             "D-214 surface supports must be sorted and unique")
    for digest in place["surface_support_sha256s"]:
        _hex64(digest, "D-214 place surface support")
    _require(0.0 <= _finite(place["reliability"], "D-214 place reliability")
             <= 1.0, "D-214 place reliability must lie in [0, 1]")
    _probabilities(place["structural_role_probabilities"],
                   ("basin", "bottleneck", "unknown"), "structural probabilities")
    _require(place["place_observation_sha256"] ==
             _payload_sha(place, "place_observation_sha256"),
             "D-214 place observation digest mismatch")
    _require(type(value["free_space_observations"]) is list and
             type(value["visibility_observations"]) is list and
             value["free_space_observations"] and
             value["visibility_observations"],
             "D-214 public volumes must be nonempty arrays")
    if value["incoming_transition_action_summary"] is not None:
        _require(type(value["incoming_transition_action_summary"]) is dict,
                 "D-214 transition summary must be an object or null")
        transition = value["incoming_transition_action_summary"]
        _require(index > 0 and
                 type(transition.get("start_observation_index")) is int and
                 transition["start_observation_index"] < index and
                 transition.get("end_observation_index") == index,
                 "D-214 transition summary does not end at the current observation")
        _hex64(transition.get("summary_sha256"),
               "D-214 transition summary digest")
        _reject_forbidden_keys(value["incoming_transition_action_summary"],
                               "/incoming_transition_action_summary")
    else:
        _require(index == 0,
                 "D-214 only observation zero may omit its incoming transition")
    _reject_forbidden_keys(value)
    _require(value["frame_cache_sha256"] ==
             _payload_sha(value, "frame_cache_sha256"),
             "D-214 frame cache digest mismatch")
    return value


def seal_episode_cache(
    frames: Sequence[Mapping[str, Any]], *, episode_public_id: str,
    dinov2_assets_receipt_sha256: str, sam2_assets_receipt_sha256: str,
    structural_assets_receipt_sha256: str,
) -> dict[str, Any]:
    """Seal one scenario-free ordered cache shared by all five methods."""

    _require(type(episode_public_id) is str and episode_public_id,
             "D-214 episode public ID is invalid")
    rows = [validate_frame_cache(frame) for frame in frames]
    _require(rows and [row["observation_index"] for row in rows] ==
             list(range(len(rows))), "D-214 frames must be contiguous from zero")
    _require(all(left["decision_time_s"] < right["decision_time_s"]
                 for left, right in zip(rows, rows[1:])),
             "D-214 frame times must be strictly increasing")
    for name, digest in (
        ("DINOv2 assets receipt", dinov2_assets_receipt_sha256),
        ("SAM2 assets receipt", sam2_assets_receipt_sha256),
        ("structural assets receipt", structural_assets_receipt_sha256),
    ):
        _hex64(digest, name)
    _require(len({row["frontend_config_sha256"] for row in rows}) == 1,
             "D-214 frames used different front-end configs")
    value = {
        "schema_version": EPISODE_SCHEMA,
        "episode_public_id": episode_public_id,
        "frame_count": len(rows),
        "frames": rows,
        "ordered_frame_cache_sha256s": [
            row["frame_cache_sha256"] for row in rows
        ],
        "frontend_config_sha256": rows[0]["frontend_config_sha256"],
        "dinov2_assets_receipt_sha256": dinov2_assets_receipt_sha256,
        "sam2_assets_receipt_sha256": sam2_assets_receipt_sha256,
        "structural_assets_receipt_sha256": structural_assets_receipt_sha256,
        "scenario_blind_materialization": True,
        "restricted_information_used": False,
        "main_methods": list(MAIN_METHODS),
    }
    value["episode_cache_sha256"] = _sha(value)
    _reject_forbidden_keys(value)
    return value


def validate_episode_cache(episode_cache: Mapping[str, Any]) -> dict[str, Any]:
    value = clone_json(dict(episode_cache))
    _exact(value, {
        "schema_version", "episode_public_id", "frame_count", "frames",
        "ordered_frame_cache_sha256s", "frontend_config_sha256",
        "dinov2_assets_receipt_sha256", "sam2_assets_receipt_sha256",
        "structural_assets_receipt_sha256", "scenario_blind_materialization",
        "restricted_information_used", "main_methods", "episode_cache_sha256",
    }, "D-214 episode cache")
    _require(value["schema_version"] == EPISODE_SCHEMA and
             value["scenario_blind_materialization"] is True and
             value["restricted_information_used"] is False and
             value["main_methods"] == list(MAIN_METHODS),
             "D-214 episode cache boundary changed")
    frames = [validate_frame_cache(frame) for frame in value["frames"]]
    _require(type(value["frame_count"]) is int and
             value["frame_count"] == len(frames) and frames and
             [frame["observation_index"] for frame in frames] ==
             list(range(len(frames))),
             "D-214 episode cache frame sequence is invalid")
    _require(all(left["decision_time_s"] < right["decision_time_s"]
                 for left, right in zip(frames, frames[1:])),
             "D-214 episode cache times must be strictly increasing")
    _require(value["ordered_frame_cache_sha256s"] == [
        frame["frame_cache_sha256"] for frame in frames
    ] and len({frame["frontend_config_sha256"] for frame in frames}) == 1 and
             value["frontend_config_sha256"] ==
             frames[0]["frontend_config_sha256"],
             "D-214 episode cache frame binding mismatch")
    for field in (
        "frontend_config_sha256", "dinov2_assets_receipt_sha256",
        "sam2_assets_receipt_sha256", "structural_assets_receipt_sha256",
        "episode_cache_sha256",
    ):
        _hex64(value[field], field)
    _reject_forbidden_keys(value)
    _require(value["episode_cache_sha256"] ==
             _payload_sha(value, "episode_cache_sha256"),
             "D-214 episode cache digest mismatch")
    return value


def identical_method_cache_views(
    episode_cache: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Return five independent clones whose canonical bytes are identical."""

    value = validate_episode_cache(episode_cache)
    views = {method: clone_json(value) for method in MAIN_METHODS}
    _require(len({_sha(item) for item in views.values()}) == 1,
             "D-214 main methods received different cache bytes")
    return views


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    a = np.asarray(left, dtype=np.float64)
    b = np.asarray(right, dtype=np.float64)
    _require(a.shape == b.shape and a.ndim == 1 and a.size > 0 and
             np.isfinite(a).all() and np.isfinite(b).all(),
             "D-214 descriptors are incompatible")
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    _require(denominator > 0.0, "D-214 descriptor has zero norm")
    return float(a @ b / denominator)


def qualify_p04(
    episode_cache: Mapping[str, Any], *,
    public_nominal_positions_xz_m: Sequence[Sequence[float]],
    minimum_separation_m: float = 1.5,
) -> dict[str, Any]:
    """Select the public DINO top-1 alias pair without an absolute threshold."""

    _require(minimum_separation_m == 1.5,
             "D-214 P04 minimum separation is frozen at 1.5 m")
    sealed = validate_episode_cache(episode_cache)
    frames = sealed["frames"]
    _require(type(frames) is list and len(frames) == len(public_nominal_positions_xz_m),
             "D-214 P04 positions must align with every cached frame")
    positions = []
    for value in public_nominal_positions_xz_m:
        _require(len(value) == 2, "D-214 P04 position must be x/z")
        positions.append((_finite(value[0], "P04 x"), _finite(value[1], "P04 z")))
    candidates = []
    for left in range(len(frames)):
        for right in range(left + 1, len(frames)):
            distance = math.dist(positions[left], positions[right])
            if distance + 1e-12 < minimum_separation_m:
                continue
            score = _cosine(
                frames[left]["place_observation"]["descriptor"],
                frames[right]["place_observation"]["descriptor"],
            )
            candidates.append((-score, left, right, distance))
    _require(candidates, "D-214 P04 has no pair at the frozen separation")
    negative_score, left, right, distance = sorted(candidates)[0]
    value = {
        "schema_version": P04_SCHEMA,
        "episode_cache_sha256": sealed["episode_cache_sha256"],
        "selected_observation_indices": [left, right],
        "public_nominal_separation_m": distance,
        "dinov2_cosine_similarity": -negative_score,
        "absolute_similarity_threshold_used": False,
        "old_quadrant_rgbd_descriptor_used": False,
    }
    value["qualification_sha256"] = _sha(value)
    return value


def _stable_fragment_pair(
    frames: Sequence[Mapping[str, Any]], indices: Sequence[int], *,
    config: P08EligibilityConfig,
) -> dict[str, Any] | None:
    for left_offset, left_index in enumerate(indices):
        for right_index in indices[left_offset + 1:]:
            for left in frames[left_index]["fragment_observations"]:
                for right in frames[right_index]["fragment_observations"]:
                    cosine = _cosine(left["descriptor"], right["descriptor"])
                    distance = math.dist(left["centroid_m"], right["centroid_m"])
                    if (cosine >= config.fragment_descriptor_cosine_minimum and
                            distance <= config.fragment_centroid_distance_maximum_m):
                        return {
                            "observation_indices": [left_index, right_index],
                            "region_ids": [left["region_id"], right["region_id"]],
                            "descriptor_cosine": cosine,
                            "centroid_distance_m": distance,
                        }
    return None


def _qualifies_structural_role(
    probabilities: Mapping[str, float], role: str, threshold: float,
) -> bool:
    """Require both the frozen probability floor and a unique winning role."""

    value = probabilities[role]
    return value >= threshold and all(
        value > probability for label, probability in probabilities.items()
        if label != role
    )


def qualify_p08(
    episode_cache: Mapping[str, Any], *, config: P08EligibilityConfig,
) -> dict[str, Any]:
    """Find an ordered basin→bottleneck→basin with stable public fragments."""

    _require(type(config) is P08EligibilityConfig,
             "D-214 P08 eligibility config is invalid")
    sealed = validate_episode_cache(episode_cache)
    frames = sealed["frames"]
    _require(type(frames) is list and len(frames) >= 5,
             "D-214 P08 needs a nontrivial ordered sequence")
    basin = [
        _qualifies_structural_role(
            frame["place_observation"]["structural_role_probabilities"],
            "basin", config.basin_probability_minimum,
        ) for frame in frames
    ]
    bottleneck = [
        _qualifies_structural_role(
            frame["place_observation"]["structural_role_probabilities"],
            "bottleneck", config.bottleneck_probability_minimum,
        ) for frame in frames
    ]
    bottleneck_runs: list[list[int]] = []
    active: list[int] = []
    for index, accepted in enumerate(bottleneck):
        if accepted:
            active.append(index)
        elif active:
            bottleneck_runs.append(active)
            active = []
    if active:
        bottleneck_runs.append(active)
    selected = None
    for middle in bottleneck_runs:
        if middle[0] == 0 or middle[-1] == len(frames) - 1:
            continue
        left = []
        cursor = middle[0] - 1
        while cursor >= 0 and basin[cursor]:
            left.append(cursor)
            cursor -= 1
        left.reverse()
        right = []
        cursor = middle[-1] + 1
        while cursor < len(frames) and basin[cursor]:
            right.append(cursor)
            cursor += 1
        if (len(left) < config.minimum_distinct_views_per_basin or
                len(right) < config.minimum_distinct_views_per_basin):
            continue
        left_pair = _stable_fragment_pair(frames, left, config=config)
        right_pair = _stable_fragment_pair(frames, right, config=config)
        if left_pair is not None and right_pair is not None:
            selected = (left, middle, right, left_pair, right_pair)
            break
    _require(selected is not None,
             "D-214 P08 lacks an ordered public basin-bottleneck-basin with stable fragments")
    left, middle, right, left_pair, right_pair = selected
    value = {
        "schema_version": P08_SCHEMA,
        "episode_cache_sha256": sealed["episode_cache_sha256"],
        "first_basin_observation_indices": left,
        "bottleneck_observation_indices": middle,
        "second_basin_observation_indices": right,
        "first_basin_stable_fragment": left_pair,
        "second_basin_stable_fragment": right_pair,
        "structural_class_used_for_place_identity": False,
        "private_metadata_used": False,
        "configuration": {
            "basin_probability_minimum": config.basin_probability_minimum,
            "bottleneck_probability_minimum":
                config.bottleneck_probability_minimum,
            "fragment_descriptor_cosine_minimum":
                config.fragment_descriptor_cosine_minimum,
            "fragment_centroid_distance_maximum_m":
                config.fragment_centroid_distance_maximum_m,
            "minimum_distinct_views_per_basin":
                config.minimum_distinct_views_per_basin,
            "qualifying_role_must_be_unique_argmax":
                config.qualifying_role_must_be_unique_argmax,
        },
    }
    value["qualification_sha256"] = _sha(value)
    return value


def legacy_grid_retirement_readiness(
    *, all_new_caches_generated: bool, all_digests_verified: bool,
    p04_and_p08_requalified: bool, all_routes_rebound: bool,
    reviewed_exact_targets: Sequence[str],
    reproduction_dependencies_remaining: Sequence[str],
) -> dict[str, Any]:
    """Return a read-only deletion gate; this function never deletes files."""

    targets = list(reviewed_exact_targets)
    dependencies = list(reproduction_dependencies_remaining)
    _require(all(type(item) is str and item and "*" not in item and "?" not in item
                 for item in targets),
             "D-214 retirement targets must be exact paths without wildcards")
    ready = bool(
        all_new_caches_generated and all_digests_verified and
        p04_and_p08_requalified and all_routes_rebound and targets and
        not dependencies
    )
    value = {
        "schema_version": RETIREMENT_SCHEMA,
        "all_new_caches_generated": bool(all_new_caches_generated),
        "all_digests_verified": bool(all_digests_verified),
        "p04_and_p08_requalified": bool(p04_and_p08_requalified),
        "all_routes_rebound": bool(all_routes_rebound),
        "reviewed_exact_targets": targets,
        "reproduction_dependencies_remaining": dependencies,
        "wildcard_deletion_allowed": False,
        "ready_for_user_requested_deletion": ready,
        "deletion_performed": False,
    }
    value["readiness_sha256"] = _sha(value)
    return value


def materializer_parameter_names() -> tuple[str, ...]:
    """Expose the public API shape for an explicit scenario-leak regression."""

    return tuple(inspect.signature(materialize_shared_rgbd_frame).parameters)
