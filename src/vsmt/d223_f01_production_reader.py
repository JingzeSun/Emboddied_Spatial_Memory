"""D-223/F-01 scenario-blind production RGB-D reader.

This overlay deliberately does not call the historical D-214 frame builder:
that schema requires structural probabilities and their model receipt.  F-01
uses the same reviewed public geometry primitives while removing every learned
semantic/structural field from both its function signature and cache bytes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import math
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from cpmt.hashing import canonical_json, clone_json
from .l1_entities import (
    DINORegionConfig,
    PublicGeometryConfig,
    extract_dinov2_patch_tokens,
    materialize_l1_entity_observation,
    pool_dinov2_region_descriptor,
)
from .l1_masks import AnonymousMask, KEEP_SUPPORTED_BORDER_REGIONS
from .l1_structures import (
    FreeSpaceFrustum,
    FreeSpaceMaterializationConfig,
    SurfaceMaterializationConfig,
    assemble_free_space_history,
    materialize_public_free_space,
    materialize_public_surfaces,
    materialize_public_visibility,
)
from .vm04_l2_proposals import (
    PROMPT_POLICY,
    Vm04L2ProposalConfig,
    run_vm04_l2_proposal_frontend,
)


CONTRACT_SCHEMA = "vsmt-vm04-d223-f01-production-reader-v1"
FRAME_SCHEMA = "vsmt-vm04-d223-f01-production-frame-cache-v1"
EPISODE_SCHEMA = "vsmt-vm04-d223-f01-production-episode-cache-v1"
INPUT_SCHEMA = "vsmt-vm04-d223-f01-public-episode-input-v1"
MAIN_METHODS = ("VSMT", "TAF", "ELU", "WFR", "LOW")
FRAGMENT_SOURCE_ID = "d223.sam2.1_hiera_small.fragment.dinov2_vits14.public_depth.v1"
SURFACE_SOURCE_ID = "l1.public_depth.planar_surface.v1"
PLACE_SOURCE_ID = "d223.dinov2_vits14.public_rgbd.non_grid_place_observation.v1"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_KEY_TOKENS = (
    "scenario", "house_id", "route_index", "world_pose", "reachable",
    "room_metadata", "instance", "object_id", "private_entity", "teacher",
    "reference_transaction", "future", "semantic", "structural",
)


class D223F01Error(ValueError):
    """A stable F-01 contract, input-boundary, or cache failure."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise D223F01Error(message)


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _seal(value: Mapping[str, Any], field: str) -> dict[str, Any]:
    result = clone_json(dict(value))
    result[field] = _sha(result)
    return result


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


def public_array_sha256(value: Any) -> str:
    """Seal an array together with its dtype and shape."""

    array = np.ascontiguousarray(np.asarray(value))
    digest = hashlib.sha256()
    digest.update(str(array.dtype).encode("ascii"))
    digest.update(canonical_json(list(array.shape)).encode("utf-8"))
    digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def _reject_forbidden_keys(value: Any, path: str = "") -> None:
    if type(value) is dict:
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered == "is_world_pose" and child is False:
                continue
            _require(not any(token in lowered for token in FORBIDDEN_KEY_TOKENS),
                     f"F-01 public value contains forbidden field {path}/{key}")
            _reject_forbidden_keys(child, f"{path}/{key}")
    elif type(value) is list:
        for index, child in enumerate(value):
            _reject_forbidden_keys(child, f"{path}/{index}")


@dataclass(frozen=True)
class F01FrontendConfig:
    descriptor: DINORegionConfig
    fragment_geometry: PublicGeometryConfig
    surface: SurfaceMaterializationConfig
    free_space: FreeSpaceMaterializationConfig
    frontend_config_sha256: str

    def __post_init__(self) -> None:
        _hex64(self.frontend_config_sha256, "F-01 frontend config digest")


def _frontend_payload(config: F01FrontendConfig) -> dict[str, Any]:
    return {
        "descriptor": asdict(config.descriptor),
        "fragment_geometry": asdict(config.fragment_geometry),
        "surface": asdict(config.surface),
        "free_space": {
            **asdict(config.free_space),
            "block_widths_in_tiles": list(
                config.free_space.block_widths_in_tiles),
        },
    }


def build_frontend_config(contract: Mapping[str, Any]) -> F01FrontendConfig:
    raw = contract["frontend"]
    config = F01FrontendConfig(
        descriptor=DINORegionConfig(**raw["descriptor"]),
        fragment_geometry=PublicGeometryConfig(**raw["fragment_geometry"]),
        surface=SurfaceMaterializationConfig(**raw["surface"]),
        free_space=FreeSpaceMaterializationConfig(
            **{**raw["free_space"], "block_widths_in_tiles":
               tuple(raw["free_space"]["block_widths_in_tiles"])}),
        frontend_config_sha256=raw["frontend_config_sha256"],
    )
    _require(_sha(_frontend_payload(config)) == config.frontend_config_sha256,
             "F-01 frontend config digest changed")
    return config


def build_l2_proposal_config(
    contract: Mapping[str, Any], *, generator_code_sha256: str,
) -> Vm04L2ProposalConfig:
    _hex64(generator_code_sha256, "F-01 proposal generator code digest")
    sam = contract["assets"]["sam2"]
    return Vm04L2ProposalConfig(
        image_height=contract["frontend"]["descriptor"]["image_height"],
        image_width=contract["frontend"]["descriptor"]["image_width"],
        minimum_visible_pixels=sam["minimum_visible_pixels"],
        border_truncation_policy=KEEP_SUPPORTED_BORDER_REGIONS,
        maximum_proposals_per_frame=sam["maximum_proposals_per_frame"],
        model_id=sam["model_id"],
        repository_commit=sam["repository_commit"],
        checkpoint_sha256=sam["checkpoint_sha256"],
        automatic_mask_generator_config_sha256=
            sam["automatic_mask_and_boundary_config_sha256"],
        assets_receipt_sha256=sam["asset_receipt_sha256"],
        generator_code_sha256=generator_code_sha256,
        prompt_policy=PROMPT_POLICY,
        cross_frame_memory_enabled=False,
        overlap_policy=sam["overlap_policy"],
    )


def validate_f01_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    value = clone_json(dict(contract))
    _require(set(value) == {
        "schema_version", "decision_id", "stage_id", "status",
        "reviewed_baseline_commit", "expected_reviewed_implementation_commit",
        "bindings", "authorization", "activation_policy",
        "public_input_boundary", "compatibility_input_adapter", "assets", "frontend",
        "production_output_boundary", "implementation_boundary",
        "resource_policy", "closed_downstream",
    }, "F-01 contract has unexpected fields")
    pending = "implementation_pending_review_all_execution_closed"
    active = "frozen_real_f01_single_episode_reader"
    _require(value["schema_version"] == CONTRACT_SCHEMA and
             value["decision_id"] == "D-223" and value["stage_id"] == "F-01" and
             value["status"] in {pending, active},
             "F-01 contract identity or status changed")
    _require(HEX40.fullmatch(value["reviewed_baseline_commit"]) is not None,
             "F-01 reviewed baseline must be a full commit")
    expected_bindings = {
        "d223_relative_path":
            "configs/vsmt/vm04_d223_p08_topological_qualification_v1.json",
        "d223_file_sha256":
            "737b4a7e108dca30931884460d294d36cc571c2d50fe5bc12daa0ebf9f288b18",
        "f00_contract_relative_path":
            "configs/vsmt/vm04_d223_f00_topology_precheck_v1.json",
        "f00_contract_file_sha256":
            "ec3ddd9949a713853e591f92ec6188a0b7627ac24af2094b7d59160f94d4176b",
        "f00_public_summary_relative_path":
            "results/vsmt_vm04_f00_topology_precheck.json",
        "f00_public_summary_file_sha256":
            "81050c8cbe8306b54c0f9621e014199e860f948f3f3de237dab06885f24ac181",
        "d215_relative_path":
            "configs/vsmt/vm04_d215_frontend_freeze_v1.json",
        "d215_file_sha256":
            "c3d6736f67b300eca03882c081e56e6bf4d65ad1913bcc411df8477fbd188db8",
        "public_entity_geometry_relative_path":
            "configs/vsmt/vm04_l1_environment_v1.json",
        "public_entity_geometry_file_sha256":
            "acecc33b5f4982830219f7f325334fb9311579ddd75551a7de3a1f450c06000a",
        "public_non_entity_geometry_relative_path":
            "configs/vsmt/vm04_l1_non_entity_geometry_review_v1.json",
        "public_non_entity_geometry_file_sha256":
            "9ef7bdfdade97b50a2e1da53ad8b11183427bf9b383feea4f223d9bf4eee5148",
        "d217_relative_path":
            "configs/vsmt/vm04_d217_estimator_development_rgbd_v1.json",
        "d217_file_sha256":
            "1499806b8a34eb71ec0785128111b28236f8cee8b95b61a94f624c608702643d",
    }
    _require(value["bindings"] == expected_bindings,
             "F-01 frozen evidence bindings changed")
    authorization = value["authorization"]
    expected_auth = {
        "d217_public_compat_bundle_generation",
        "real_asset_verification_and_loading", "real_public_input_read",
        "production_cache_generation", "p04_p08_qualification",
        "route_or_raw_generation", "adapter_materialization",
        "private_evaluation", "training", "audit_rerun",
    }
    _require(set(authorization) == expected_auth and
             all(type(flag) is bool for flag in authorization.values()),
             "F-01 authorization fields changed")
    policy = value["activation_policy"]
    active_true = {
        "d217_public_compat_bundle_generation",
        "real_asset_verification_and_loading", "real_public_input_read",
        "production_cache_generation"}
    _require(policy["active_status"] == active and
             set(policy["active_true_authorizations"]) == active_true and
             set(policy["must_remain_false"]) == expected_auth - active_true and
             policy["activation_commit_may_change_only"] == [
                 "configs/vsmt/vm04_d223_f01_production_reader_v1.json"] and
             policy["executable_checkout_must_be_clean"] is True and
             policy["executable_checkout_parent_must_equal_reviewed_implementation_commit"]
             is True, "F-01 activation policy changed")
    if value["status"] == pending:
        _require(value["expected_reviewed_implementation_commit"] is None and
                 not any(authorization.values()),
                 "F-01 review candidate must keep execution closed")
    else:
        _require(type(value["expected_reviewed_implementation_commit"]) is str and
                 HEX40.fullmatch(value["expected_reviewed_implementation_commit"])
                 is not None and
                 {name for name, enabled in authorization.items() if enabled} ==
                 active_true, "F-01 active scope changed")

    public = value["public_input_boundary"]
    _require(public["fields"] == [
        "current_rgb_uint8", "current_depth_m_float32", "camera_intrinsics",
        "causal_episode_relative_camera_pose", "continuous_pose_belief",
        "incoming_transition_action_summary", "prior_public_free_space"] and
        public["forbidden"] == [
            "scenario_id", "scenario_role", "house_id", "route_index",
            "simulator_world_pose", "reachable_grid", "room_metadata",
            "instance_mask", "object_id", "private_entity_id",
            "semantic_label_or_probability",
            "structural_label_or_probability", "teacher",
            "reference_transaction", "future_observation_or_state"] and
        public["input_bundle_schema"] == INPUT_SCHEMA and
        public["single_episode_per_run"] is True and
        set(public) == {"fields", "forbidden", "input_bundle_schema",
                        "single_episode_per_run"},
        "F-01 public input boundary changed")
    _require(value["compatibility_input_adapter"] == {
        "source_schema": "vsmt-vm04-d217-public-rgbd-house-v1",
        "source_split": "train",
        "sample_directory_regex": "^sample_[0-9]{4}$",
        "selection_order":
            "ascending_sample_rank_first_present_public_sample",
        "selected_sample_incomplete_or_malformed_policy":
            "fail_do_not_skip",
        "selected_observation_index": 0,
        "source_required_files": ["receipt.json", "rgbd.npz"],
        "source_npz_arrays": [
            "rgb_uint8", "depth_m_float32", "camera_intrinsics_float64",
            "observation_ids"],
        "pose_policy": {
            "frame": "episode_relative_observation_zero_origin",
            "mean_x_y_z_yaw": [0.0, 0.0, 0.0, 0.0],
            "covariance_diagonal": [0.0, 0.0, 0.0, 0.0],
            "is_world_pose": False,
            "incoming_transition_action_summary": None,
        },
        "output_bundle_schema": INPUT_SCHEMA,
        "diagnostic_compatibility_only": True,
        "eligible_for_formal_data_p04_p08_or_paper_results": False,
        "private_root_or_sidecar_read_allowed": False,
    }, "F-01 D-217 compatibility adapter boundary changed")
    assets = value["assets"]
    dino, sam = assets["dinov2"], assets["sam2"]
    expected_sam = {
        "model_id": "sam2.1.hiera_small.per_frame_automatic_mask_generator",
        "repository_commit": "2b90b9f5ceec907a1c18123530e92e794ad901a4",
        "official_model_config_path":
            "sam2/configs/sam2.1/sam2.1_hiera_s.yaml",
        "official_model_config_bytes": 3761,
        "official_model_config_sha256":
            "0f36b91e86e58d06c87e42997166212468b88b98b60e4d816d5e4d4d088b6f55",
        "checkpoint_bytes": 184416285,
        "checkpoint_sha256":
            "6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38",
        "automatic_mask_generator": {
            "points_per_side": 32, "points_per_batch": 64,
            "pred_iou_thresh": 0.8, "stability_score_thresh": 0.95,
            "stability_score_offset": 1.0, "box_nms_thresh": 1.0,
            "crop_n_layers": 0, "crop_nms_thresh": 1.0,
            "min_mask_region_area": 0, "output_mode": "binary_mask"},
        "minimum_visible_pixels": 196, "maximum_proposals_per_frame": 64,
        "border_truncation_policy":
            "retain_if_minimum_visible_pixels_met",
        "prompt_policy": PROMPT_POLICY,
        "cross_frame_memory_enabled": False,
        "overlap_policy": "preserve_independent_overlapping_proposals",
        "asset_receipt_sha256":
            "6b6e1705ee81ec71475fb0c1b28696c98d2f30740e92a0a380554e9e85bb6a33",
        "automatic_mask_and_boundary_config_sha256":
            "df828bcfac74c8dc0dcb0d82731c978f8a17958755822aa44c90e5ac23db2c33",
    }
    _require(set(assets) == {"dinov2", "sam2",
                             "e06_structural_estimator_loaded"} and dino == {
        "model_id": "dinov2.vits14",
        "repository_commit": "7764ea0f912e53c92e82eb78a2a1631e92725fc8",
        "checkpoint_sha256":
            "b938bf1bc15cd2ec0feacfe3a1bb553fe8ea9ca46a7e1d8d00217f29aef60cd9",
        "input_shape": [224, 224, 3], "patch_size_pixels": 14,
        "patch_token_dimension": 384, "parameters_frozen": True,
        "evaluation_mode": True,
    } and sam == expected_sam and
        assets["e06_structural_estimator_loaded"] is False,
        "F-01 frozen asset policy changed")
    build_frontend_config(value)
    output = value["production_output_boundary"]
    _require(set(output) == {
                 "frame_schema", "episode_schema", "outputs",
                 "semantic_or_structural_probabilities_present",
                 "semantic_or_structural_model_receipts_present",
                 "persistent_entity_or_place_identity_assigned",
                 "reachable_graph_present", "raw_paths_or_private_crosswalk_present",
                 "identical_method_cache_views"} and
             output["frame_schema"] == FRAME_SCHEMA and
             output["episode_schema"] == EPISODE_SCHEMA and
             output["outputs"] == [
                 "anonymous_fragment_observations",
                 "public_depth_surface_observations",
                 "public_free_space_observations",
                 "public_visibility_observations",
                 "non_grid_place_observation", "frozen_dinov2_descriptors"] and
             output["semantic_or_structural_probabilities_present"] is False and
             output["semantic_or_structural_model_receipts_present"] is False and
             output["persistent_entity_or_place_identity_assigned"] is False and
             output["reachable_graph_present"] is False and
             output["raw_paths_or_private_crosswalk_present"] is False and
             output["identical_method_cache_views"] == list(MAIN_METHODS),
             "F-01 production output boundary changed")
    _require(value["implementation_boundary"] == {
        "post_d223_frame_core_implemented": True,
        "post_d223_episode_cache_implemented": True,
        "frozen_asset_verifier_and_loader_implemented": True,
        "public_input_bundle_reader_implemented": True,
        "d217_public_compat_adapter_implemented": True,
        "real_assets_or_public_inputs_opened": False,
        "server_executed": False,
    }, "F-01 implementation boundary changed")
    _require(value["resource_policy"] == {
        "single_episode_execution_unit": True,
        "one_dinov2_model_and_one_sam2_generator_on_one_gpu": True,
        "frame_order_must_be_sequential_for_causal_free_space_history": True,
        "wall_clock_timeout_allowed": False,
        "minimum_free_disk_bytes": 4294967296,
    }, "F-01 resource policy changed")
    _require(set(value["closed_downstream"]) == {
        "production_cache_produced", "p04_p08_requalified",
        "route_or_raw_generated", "adapter_materialized",
        "private_evaluation_run", "training_run", "audit_rerun",
        "f01_success_does_not_automatically_start_f02"},
        "F-01 closed downstream fields changed")
    _require(not any(value["closed_downstream"][key] for key in (
        "production_cache_produced", "p04_p08_requalified",
        "route_or_raw_generated", "adapter_materialized",
        "private_evaluation_run", "training_run", "audit_rerun")) and
        value["closed_downstream"]["f01_success_does_not_automatically_start_f02"]
        is True, "F-01 closed downstream boundary changed")
    return value


def assert_real_f01_authorized(contract: Mapping[str, Any]) -> None:
    required = contract.get("activation_policy", {}).get(
        "active_true_authorizations", [])
    _require(contract.get("status") ==
             contract.get("activation_policy", {}).get("active_status") and
             all(contract.get("authorization", {}).get(name) is True
                 for name in required),
             "F-01 real asset and public-input execution is closed pending review")


def _pose_belief(value: Mapping[str, Any], index: int) -> dict[str, Any]:
    record = clone_json(dict(value))
    _require(set(record) == {
        "schema_version", "observation_index", "frame", "mean_x_y_z_yaw",
        "covariance_diagonal", "source_id", "is_world_pose",
        "defines_place_identity", "belief_sha256",
    }, "F-01 pose belief fields changed")
    _require(record["observation_index"] == index and
             record["frame"] == "episode_relative_observation_zero_origin" and
             record["is_world_pose"] is False and
             record["defines_place_identity"] is False and
             record["belief_sha256"] ==
             _payload_sha(record, "belief_sha256"),
             "F-01 pose belief is not sealed causal public evidence")
    _require(len(record["mean_x_y_z_yaw"]) == 4 and
             len(record["covariance_diagonal"]) == 4 and
             all(_finite(item, "pose belief mean") == float(item)
                 for item in record["mean_x_y_z_yaw"]) and
             all(_finite(item, "pose belief covariance") >= 0.0
                 for item in record["covariance_diagonal"]),
             "F-01 pose belief values changed")
    return record


def _geometry_pose(value: Mapping[str, Any]) -> dict[str, Any]:
    record = clone_json(dict(value))
    _require(set(record) == {
        "position_m", "quaternion_xyzw", "is_world_pose", "source_id"},
        "F-01 causal camera pose fields changed")
    _require(record["is_world_pose"] is False and
             type(record["source_id"]) is str and record["source_id"],
             "F-01 camera pose must be causal and episode-relative")
    position = [_finite(item, "camera position") for item in record["position_m"]]
    quaternion = [_finite(item, "camera quaternion")
                  for item in record["quaternion_xyzw"]]
    _require(len(position) == 3 and len(quaternion) == 4 and
             abs(math.sqrt(sum(item * item for item in quaternion)) - 1.0)
             <= 1e-6, "F-01 camera pose is invalid")
    return {"position_m": position, "quaternion_xyzw": quaternion}


def _validate_volume_records(
    rows: Any, *, prefix: str, record_prefix: str,
) -> None:
    _require(type(rows) is list, f"F-01 {prefix} volumes must be an array")
    id_field = f"{prefix}_id"
    for ordinal, row in enumerate(rows):
        _require(type(row) is dict and set(row) == {
            id_field, "time_s", "halfspaces_world", "reliability",
            "support_sha256"}, f"F-01 {prefix} volume fields changed")
        _require(row[id_field] == f"{record_prefix}:{ordinal:04d}" and
                 _finite(row["time_s"], f"F-01 {prefix} time") >= 0.0 and
                 _finite(row["reliability"], f"F-01 {prefix} reliability") ==
                 1.0 and len(row["halfspaces_world"]) == 6,
                 f"F-01 {prefix} volume identity changed")
        _hex64(row["support_sha256"], f"F-01 {prefix} support")
        for halfspace in row["halfspaces_world"]:
            _require(type(halfspace) is dict and
                     set(halfspace) == {"normal", "offset_m"} and
                     len(halfspace["normal"]) == 3,
                     f"F-01 {prefix} halfspace fields changed")
            normal = [_finite(item, f"F-01 {prefix} normal")
                      for item in halfspace["normal"]]
            _finite(halfspace["offset_m"], f"F-01 {prefix} offset")
            _require(abs(math.sqrt(sum(item * item for item in normal)) - 1.0)
                     <= 1e-6, f"F-01 {prefix} normal is not unit length")


def _materialize_frame(
    *, observation_index: int, decision_time_s: float,
    rgb: Any, depth_m: Any, rgb_source_sha256: str, depth_source_sha256: str,
    camera_calibration: Mapping[str, Any],
    causal_camera_pose: Mapping[str, Any], pose_belief: Mapping[str, Any],
    incoming_transition_action_summary: Mapping[str, Any] | None,
    patch_tokens: Any, public_fragment_masks: Sequence[AnonymousMask],
    l2_proposal_receipt_sha256: str, frozen_assets_receipt_sha256: str,
    prior_free_space: Sequence[Sequence[FreeSpaceFrustum]],
    config: F01FrontendConfig,
) -> tuple[dict[str, Any], tuple[FreeSpaceFrustum, ...]]:
    _require(type(observation_index) is int and observation_index >= 0,
             "F-01 observation index is invalid")
    time_s = _finite(decision_time_s, "F-01 decision time")
    _require(time_s >= 0.0, "F-01 decision time must be nonnegative")
    for name, digest in (
        ("RGB source", rgb_source_sha256),
        ("depth source", depth_source_sha256),
        ("L2 proposal receipt", l2_proposal_receipt_sha256),
        ("frozen assets receipt", frozen_assets_receipt_sha256),
    ):
        _hex64(digest, name)
    image = np.asarray(rgb)
    depth = np.asarray(depth_m)
    expected_shape = (config.descriptor.image_height,
                      config.descriptor.image_width)
    _require(image.dtype == np.uint8 and image.shape == (*expected_shape, 3),
             "F-01 RGB schema changed")
    _require(depth.dtype == np.float32 and depth.shape == expected_shape,
             "F-01 depth schema changed")
    calibration = clone_json(dict(camera_calibration))
    _require(set(calibration) == {"fx", "fy", "cx", "cy"} and
             all(type(calibration[key]) in {int, float} and
                 math.isfinite(float(calibration[key]))
                 for key in calibration) and
             float(calibration["fx"]) > 0.0 and
             float(calibration["fy"]) > 0.0,
             "F-01 camera calibration changed")
    belief = _pose_belief(pose_belief, observation_index)
    geometry_pose = _geometry_pose(causal_camera_pose)
    masks = tuple(public_fragment_masks)
    _require(all(type(item) is AnonymousMask for item in masks),
             "F-01 fragments must be anonymous public masks")

    fragments = []
    for mask in masks:
        observed = materialize_l1_entity_observation(
            mask, patch_tokens, depth, calibration, geometry_pose,
            config.descriptor, config.fragment_geometry)
        fragments.append({
            "region_id": "", "structure_kind": "fragment",
            "mask_sha256": observed.mask_sha256,
            "descriptor": list(observed.descriptor.values),
            "centroid_m": list(observed.geometry.centroid_m),
            "extent_m": list(observed.geometry.extent_m),
            "reliability": observed.geometry.reliability,
            "proposal_source_id": FRAGMENT_SOURCE_ID,
        })
    fragments.sort(key=lambda row: (row["mask_sha256"], row["centroid_m"]))
    surfaces = materialize_public_surfaces(
        depth, calibration, geometry_pose, patch_tokens,
        config.descriptor, config.surface)
    surface_records = [item.public_record("") for item in surfaces]
    surface_records.sort(key=lambda row: (row["mask_sha256"], row["centroid_m"]))
    regions = [*fragments, *surface_records]
    for ordinal, record in enumerate(regions):
        record["region_id"] = f"region:{ordinal:04d}"

    full_mask = np.ones(expected_shape, dtype=np.bool_)
    place_descriptor = pool_dinov2_region_descriptor(
        patch_tokens, full_mask, config.descriptor)
    pose_digest = _sha({"calibration": calibration,
                        "causal_pose": geometry_pose})
    current_free_space = materialize_public_free_space(
        depth, calibration, geometry_pose, time_s=time_s,
        depth_sha256=depth_source_sha256,
        camera_calibration_and_pose_sha256=pose_digest,
        config=config.free_space)
    free_space = assemble_free_space_history(
        [*prior_free_space, current_free_space],
        rolling_public_observation_times=
            config.free_space.rolling_public_observation_times)
    visibility = materialize_public_visibility(
        current_free_space,
        surface_clearance_m=config.free_space.surface_clearance_m)
    valid_depth = (np.isfinite(depth) &
                   (depth >= config.fragment_geometry.minimum_depth_m) &
                   (depth <= config.fragment_geometry.maximum_depth_m))
    place = {
        "place_observation_id": f"place-observation:{observation_index:04d}",
        "observation_index": observation_index,
        "persistent_place_id": None, "identity_assigned": False,
        "metric_grid_identity_used": False,
        "descriptor": list(place_descriptor.values),
        "pose_belief_sha256": belief["belief_sha256"],
        "pose_belief_mean_x_y_z_yaw": clone_json(
            belief["mean_x_y_z_yaw"]),
        "pose_belief_covariance_diagonal": clone_json(
            belief["covariance_diagonal"]),
        "surface_support_sha256s": sorted(
            row["mask_sha256"] for row in surface_records),
        "free_space_support_sha256": _sha(free_space),
        "reliability": float(valid_depth.mean()),
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
        "rgb_source_sha256": rgb_source_sha256,
        "depth_source_sha256": depth_source_sha256,
        "rgb_array_sha256": public_array_sha256(image),
        "depth_array_sha256": public_array_sha256(depth),
        "camera_calibration_and_causal_pose_sha256": pose_digest,
        "pose_belief": belief,
        "incoming_transition_action_summary": transition,
        "fragment_observations": [row for row in regions
                                  if row["structure_kind"] == "fragment"],
        "surface_observations": [row for row in regions
                                 if row["structure_kind"] == "surface"],
        "place_observation": place,
        "free_space_observations": free_space,
        "visibility_observations": visibility,
        "l2_proposal_receipt_sha256": l2_proposal_receipt_sha256,
        "frozen_assets_receipt_sha256": frozen_assets_receipt_sha256,
        "frontend_config_sha256": config.frontend_config_sha256,
        "public_only": True,
    }
    _reject_forbidden_keys(frame)
    frame["frame_cache_sha256"] = _sha(frame)
    return validate_frame_cache(frame), current_free_space


def validate_frame_cache(frame: Mapping[str, Any]) -> dict[str, Any]:
    value = clone_json(dict(frame))
    _require(set(value) == {
        "schema_version", "observation_index", "decision_time_s",
        "keyframe_policy", "rgb_source_sha256", "depth_source_sha256",
        "rgb_array_sha256", "depth_array_sha256",
        "camera_calibration_and_causal_pose_sha256", "pose_belief",
        "incoming_transition_action_summary", "fragment_observations",
        "surface_observations", "place_observation",
        "free_space_observations", "visibility_observations",
        "l2_proposal_receipt_sha256", "frozen_assets_receipt_sha256",
        "frontend_config_sha256", "public_only", "frame_cache_sha256",
    }, "F-01 frame cache fields changed")
    _require(value["schema_version"] == FRAME_SCHEMA and
             value["public_only"] is True and
             value["keyframe_policy"] == "every_saved_public_observation",
             "F-01 frame cache identity changed")
    index = value["observation_index"]
    _require(type(index) is int and index >= 0,
             "F-01 frame index is invalid")
    _pose_belief(value["pose_belief"], index)
    for field in (
        "rgb_source_sha256", "depth_source_sha256", "rgb_array_sha256",
        "depth_array_sha256", "camera_calibration_and_causal_pose_sha256",
        "l2_proposal_receipt_sha256", "frozen_assets_receipt_sha256",
        "frontend_config_sha256", "frame_cache_sha256",
    ):
        _hex64(value[field], field)
    _require(all(row.get("structure_kind") == "fragment"
                 for row in value["fragment_observations"]) and
             all(row.get("structure_kind") == "surface"
                 for row in value["surface_observations"]),
             "F-01 region crossed its fragment/surface collection")
    regions = [*value["fragment_observations"],
               *value["surface_observations"]]
    _require([row.get("region_id") for row in regions] == [
        f"region:{index:04d}" for index in range(len(regions))],
        "F-01 region ordinals changed")
    expected_region_keys = {
        "region_id", "structure_kind", "mask_sha256", "descriptor",
        "centroid_m", "extent_m", "reliability", "proposal_source_id"}
    for ordinal, row in enumerate(regions):
        _require(set(row) == expected_region_keys,
                 f"F-01 region {ordinal} fields changed")
        kind = row["structure_kind"]
        _require(kind in {"fragment", "surface"} and
                 row["proposal_source_id"] ==
                 (FRAGMENT_SOURCE_ID if kind == "fragment" else
                  SURFACE_SOURCE_ID),
                 "F-01 region kind or source changed")
        _hex64(row["mask_sha256"], "F-01 region mask")
        descriptor = [_finite(item, "region descriptor")
                      for item in row["descriptor"]]
        centroid = [_finite(item, "region centroid")
                    for item in row["centroid_m"]]
        extent = [_finite(item, "region extent")
                  for item in row["extent_m"]]
        _require(descriptor and
                 abs(math.sqrt(sum(item * item for item in descriptor)) - 1.0)
                 <= 1e-5 and len(centroid) == 3 and len(extent) == 3 and
                 all(item >= 0.0 for item in extent) and
                 0.0 <= _finite(row["reliability"], "region reliability") <= 1.0,
                 "F-01 region geometry or descriptor changed")
    place = value["place_observation"]
    _require(set(place) == {
        "place_observation_id", "observation_index", "persistent_place_id",
        "identity_assigned", "metric_grid_identity_used", "descriptor",
        "pose_belief_sha256", "pose_belief_mean_x_y_z_yaw",
        "pose_belief_covariance_diagonal", "surface_support_sha256s",
        "free_space_support_sha256", "reliability", "proposal_source_id",
        "place_observation_sha256",
    }, "F-01 place observation fields changed")
    _require(place["persistent_place_id"] is None and
             place["identity_assigned"] is False and
             place["metric_grid_identity_used"] is False and
             place["observation_index"] == index and
             place["place_observation_id"] ==
             f"place-observation:{index:04d}" and
             place["proposal_source_id"] == PLACE_SOURCE_ID and
             place["pose_belief_sha256"] ==
             value["pose_belief"]["belief_sha256"] and
             place["pose_belief_mean_x_y_z_yaw"] ==
             value["pose_belief"]["mean_x_y_z_yaw"] and
             place["pose_belief_covariance_diagonal"] ==
             value["pose_belief"]["covariance_diagonal"],
             "F-01 place observation assigned identity or changed binding")
    descriptor = [_finite(item, "place descriptor")
                  for item in place["descriptor"]]
    _require(descriptor and
             abs(math.sqrt(sum(item * item for item in descriptor)) - 1.0)
             <= 1e-5 and
             0.0 <= _finite(place["reliability"], "place reliability") <= 1.0 and
             place["surface_support_sha256s"] ==
             sorted(set(place["surface_support_sha256s"])) and
             place["surface_support_sha256s"] ==
             sorted(row["mask_sha256"]
                    for row in value["surface_observations"]) and
             all(HEX64.fullmatch(item) is not None
                 for item in place["surface_support_sha256s"]) and
             place["place_observation_sha256"] ==
             _payload_sha(place, "place_observation_sha256"),
             "F-01 place observation digest or descriptor changed")
    _hex64(place["free_space_support_sha256"], "place free-space support")
    _validate_volume_records(value["free_space_observations"],
                             prefix="free_space", record_prefix="free")
    _validate_volume_records(value["visibility_observations"],
                             prefix="visibility", record_prefix="visibility")
    _require(place["free_space_support_sha256"] ==
             _sha(value["free_space_observations"]),
             "F-01 place free-space support changed")
    transition = value["incoming_transition_action_summary"]
    if transition is None:
        _require(index == 0, "only F-01 observation zero may omit transition")
    else:
        _require(type(transition) is dict and index > 0 and
                 type(transition.get("start_observation_index")) is int and
                 transition["start_observation_index"] < index and
                 transition.get("end_observation_index") == index,
                 "F-01 transition does not end at current observation")
        _hex64(transition.get("summary_sha256"), "transition summary")
        _require(transition["summary_sha256"] ==
                 _payload_sha(transition, "summary_sha256"),
                 "F-01 transition summary digest mismatch")
    _reject_forbidden_keys(value)
    _require(value["frame_cache_sha256"] ==
             _payload_sha(value, "frame_cache_sha256"),
             "F-01 frame cache digest mismatch")
    return value


class F01ProductionReader:
    """Stateful one-episode reader with public-only frozen processors."""

    def __init__(
        self, *, contract: Mapping[str, Any], sam_generator: Any,
        patch_token_extractor: Callable[[np.ndarray], Any],
        frozen_assets_receipt_sha256: str,
        proposal_generator_code_sha256: str,
    ) -> None:
        self.contract = validate_f01_contract(contract)
        _require(hasattr(sam_generator, "generate") and
                 callable(sam_generator.generate),
                 "F-01 SAM generator must expose generate(rgb)")
        _require(callable(patch_token_extractor),
                 "F-01 patch-token extractor is not callable")
        self.sam_generator = sam_generator
        self.patch_token_extractor = patch_token_extractor
        self.assets_receipt_sha256 = _hex64(
            frozen_assets_receipt_sha256, "frozen assets receipt")
        self.frontend = build_frontend_config(self.contract)
        self.proposal = build_l2_proposal_config(
            self.contract, generator_code_sha256=proposal_generator_code_sha256)
        self.frames: list[dict[str, Any]] = []
        self.free_space_groups: list[tuple[FreeSpaceFrustum, ...]] = []

    def read_frame(
        self, *, observation_index: int, decision_time_s: float,
        rgb_uint8: Any, depth_m_float32: Any,
        rgb_source_sha256: str, depth_source_sha256: str,
        camera_intrinsics: Mapping[str, Any],
        causal_episode_relative_camera_pose: Mapping[str, Any],
        continuous_pose_belief: Mapping[str, Any],
        incoming_transition_action_summary: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        _require(observation_index == len(self.frames),
                 "F-01 frames must be read contiguously from zero")
        _require(not self.frames or
                 decision_time_s > self.frames[-1]["decision_time_s"],
                 "F-01 decision times must be strictly increasing")
        image = np.asarray(rgb_uint8)
        proposal = run_vm04_l2_proposal_frontend(
            rgb=image, public_rgb_file_sha256=rgb_source_sha256,
            generator=self.sam_generator, config=self.proposal)
        tokens = self.patch_token_extractor(np.ascontiguousarray(image).copy())
        frame, current = _materialize_frame(
            observation_index=observation_index,
            decision_time_s=decision_time_s, rgb=image,
            depth_m=depth_m_float32, rgb_source_sha256=rgb_source_sha256,
            depth_source_sha256=depth_source_sha256,
            camera_calibration=camera_intrinsics,
            causal_camera_pose=causal_episode_relative_camera_pose,
            pose_belief=continuous_pose_belief,
            incoming_transition_action_summary=
                incoming_transition_action_summary,
            patch_tokens=tokens, public_fragment_masks=proposal["masks"],
            l2_proposal_receipt_sha256=proposal["receipt"]["receipt_sha256"],
            frozen_assets_receipt_sha256=self.assets_receipt_sha256,
            prior_free_space=self.free_space_groups, config=self.frontend)
        self.frames.append(frame)
        self.free_space_groups.append(current)
        return clone_json(frame)

    def seal_episode(self, *, episode_public_id: str) -> dict[str, Any]:
        return seal_episode_cache(
            self.frames, episode_public_id=episode_public_id,
            frozen_assets_receipt_sha256=self.assets_receipt_sha256)


def seal_episode_cache(
    frames: Sequence[Mapping[str, Any]], *, episode_public_id: str,
    frozen_assets_receipt_sha256: str,
) -> dict[str, Any]:
    _require(type(episode_public_id) is str and episode_public_id,
             "F-01 episode public ID is missing")
    _hex64(frozen_assets_receipt_sha256, "F-01 frozen assets receipt")
    rows = [validate_frame_cache(frame) for frame in frames]
    _require(rows and [row["observation_index"] for row in rows] ==
             list(range(len(rows))),
             "F-01 episode frames must be contiguous from zero")
    _require(all(left["decision_time_s"] < right["decision_time_s"]
                 for left, right in zip(rows, rows[1:])),
             "F-01 episode times must increase")
    _require(len({row["frontend_config_sha256"] for row in rows}) == 1 and
             {row["frozen_assets_receipt_sha256"] for row in rows} ==
             {frozen_assets_receipt_sha256},
             "F-01 frames used different config or assets")
    episode = {
        "schema_version": EPISODE_SCHEMA,
        "episode_public_id": episode_public_id,
        "frame_count": len(rows), "frames": rows,
        "ordered_frame_cache_sha256s": [row["frame_cache_sha256"]
                                         for row in rows],
        "frontend_config_sha256": rows[0]["frontend_config_sha256"],
        "frozen_assets_receipt_sha256": frozen_assets_receipt_sha256,
        "public_only_materialization": True,
        "restricted_information_used": False,
        "main_methods": list(MAIN_METHODS),
    }
    _reject_forbidden_keys(episode)
    return _seal(episode, "episode_cache_sha256")


def validate_episode_cache(episode: Mapping[str, Any]) -> dict[str, Any]:
    value = clone_json(dict(episode))
    _require(set(value) == {
        "schema_version", "episode_public_id", "frame_count", "frames",
        "ordered_frame_cache_sha256s", "frontend_config_sha256",
        "frozen_assets_receipt_sha256", "public_only_materialization",
        "restricted_information_used", "main_methods",
        "episode_cache_sha256",
    }, "F-01 episode cache fields changed")
    rebuilt = seal_episode_cache(
        value["frames"], episode_public_id=value["episode_public_id"],
        frozen_assets_receipt_sha256=value["frozen_assets_receipt_sha256"])
    _require(value == rebuilt, "F-01 episode cache digest or summary changed")
    return value


def identical_method_cache_views(
    episode: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    value = validate_episode_cache(episode)
    return {method: clone_json(value) for method in MAIN_METHODS}


def validate_public_input_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    value = clone_json(dict(manifest))
    _require(set(value) == {
        "schema_version", "episode_public_id", "frame_count",
        "arrays_npz_sha256", "rows", "restricted_information_used",
        "manifest_sha256",
    }, "F-01 input manifest fields changed")
    _reject_forbidden_keys(value)
    _require(value["schema_version"] == INPUT_SCHEMA and
             type(value["episode_public_id"]) is str and
             value["episode_public_id"] and
             type(value["frame_count"]) is int and value["frame_count"] > 0 and
             value["restricted_information_used"] is False and
             value["manifest_sha256"] ==
             _payload_sha(value, "manifest_sha256"),
             "F-01 input manifest identity or digest changed")
    _hex64(value["arrays_npz_sha256"], "F-01 input NPZ digest")
    rows = value["rows"]
    _require(type(rows) is list and len(rows) == value["frame_count"] and
             [row.get("observation_index") for row in rows] ==
             list(range(len(rows))),
             "F-01 input rows are not contiguous")
    expected = {
        "observation_index", "decision_time_s", "rgb_source_sha256",
        "depth_source_sha256", "camera_intrinsics",
        "causal_episode_relative_camera_pose", "continuous_pose_belief",
        "incoming_transition_action_summary"}
    for index, row in enumerate(rows):
        _require(type(row) is dict and set(row) == expected,
                 f"F-01 input row {index} fields changed")
        _hex64(row["rgb_source_sha256"], "input RGB source")
        _hex64(row["depth_source_sha256"], "input depth source")
        _require(type(row["decision_time_s"]) in {int, float} and
                 math.isfinite(float(row["decision_time_s"])) and
                 float(row["decision_time_s"]) >= 0.0,
                 "F-01 input decision time is invalid")
        calibration = row["camera_intrinsics"]
        _require(type(calibration) is dict and
                 set(calibration) == {"fx", "fy", "cx", "cy"} and
                 all(type(calibration[key]) in {int, float} and
                     math.isfinite(float(calibration[key]))
                     for key in calibration) and
                 float(calibration["fx"]) > 0.0 and
                 float(calibration["fy"]) > 0.0,
                 "F-01 input camera intrinsics changed")
        _pose_belief(row["continuous_pose_belief"], index)
        _geometry_pose(row["causal_episode_relative_camera_pose"])
        transition = row["incoming_transition_action_summary"]
        if transition is None:
            _require(index == 0,
                     "only F-01 input observation zero may omit transition")
        else:
            _require(type(transition) is dict and index > 0 and
                     type(transition.get("start_observation_index")) is int and
                     transition["start_observation_index"] < index and
                     transition.get("end_observation_index") == index,
                     "F-01 input transition does not end at current observation")
            _hex64(transition.get("summary_sha256"), "input transition summary")
            _require(transition["summary_sha256"] ==
                     _payload_sha(transition, "summary_sha256"),
                     "F-01 input transition digest mismatch")
    _require(all(float(left["decision_time_s"]) <
                 float(right["decision_time_s"])
                 for left, right in zip(rows, rows[1:])),
             "F-01 input decision times must increase")
    return value


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_clean_commit(repository: Path, expected_commit: str, name: str) -> None:
    def git(*args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(repository), *args], capture_output=True,
            text=True, check=False)
        _require(result.returncode == 0, f"{name} Git verification failed")
        return result.stdout.strip()
    _require(repository.is_dir() and git("rev-parse", "HEAD") == expected_commit and
             git("status", "--porcelain", "--untracked-files=all") == "",
             f"{name} repository commit or cleanliness changed")


def verify_frozen_assets(
    contract: Mapping[str, Any], *, dino_repository: Path,
    dino_checkpoint: Path, sam_repository: Path, sam_checkpoint: Path,
) -> dict[str, Any]:
    value = validate_f01_contract(contract)
    dino, sam = value["assets"]["dinov2"], value["assets"]["sam2"]
    dino_repository, sam_repository = Path(dino_repository), Path(sam_repository)
    dino_checkpoint, sam_checkpoint = Path(dino_checkpoint), Path(sam_checkpoint)
    _git_clean_commit(dino_repository, dino["repository_commit"], "DINOv2")
    _git_clean_commit(sam_repository, sam["repository_commit"], "SAM2")
    config_path = sam_repository / sam["official_model_config_path"]
    _require(dino_checkpoint.is_file() and sam_checkpoint.is_file() and
             config_path.is_file(), "F-01 frozen asset file is missing")
    _require(_sha_file(dino_checkpoint) == dino["checkpoint_sha256"] and
             _sha_file(sam_checkpoint) == sam["checkpoint_sha256"] and
             sam_checkpoint.stat().st_size == sam["checkpoint_bytes"] and
             _sha_file(config_path) == sam["official_model_config_sha256"] and
             config_path.stat().st_size == sam["official_model_config_bytes"],
             "F-01 frozen asset bytes changed")
    return _seal({
        "schema_version": "vsmt-vm04-d223-f01-frozen-assets-receipt-v1",
        "dinov2_repository_commit": dino["repository_commit"],
        "dinov2_checkpoint_sha256": dino["checkpoint_sha256"],
        "sam2_repository_commit": sam["repository_commit"],
        "sam2_checkpoint_sha256": sam["checkpoint_sha256"],
        "sam2_official_config_sha256": sam["official_model_config_sha256"],
        "repository_worktrees_clean": True,
        "network_access_required": False,
        "e06_structural_estimator_loaded": False,
    }, "frozen_assets_receipt_sha256")


def load_frozen_processors(
    contract: Mapping[str, Any], *, dino_repository: Path,
    dino_checkpoint: Path, sam_repository: Path, sam_checkpoint: Path,
    device: str = "cuda", torch_module: Any = None,
    dino_model_factory: Any = None, sam_builder: Any = None,
    sam_generator_factory: Any = None,
) -> tuple[Any, Callable[[np.ndarray], np.ndarray], dict[str, Any]]:
    _require(device == "cuda", "F-01 frozen models require CUDA")
    value = validate_f01_contract(contract)
    receipt = verify_frozen_assets(
        value, dino_repository=dino_repository,
        dino_checkpoint=dino_checkpoint, sam_repository=sam_repository,
        sam_checkpoint=sam_checkpoint)
    if torch_module is None:
        import torch as torch_module  # type: ignore[no-redef]
    _require(torch_module.cuda.is_available(), "CUDA is unavailable for F-01")
    if dino_model_factory is None:
        sys.path.insert(0, str(Path(dino_repository).resolve()))
        try:
            from dinov2.hub.backbones import dinov2_vits14
        finally:
            sys.path.pop(0)
        dino_model_factory = dinov2_vits14
    dino_model = dino_model_factory(pretrained=False)
    state = torch_module.load(
        Path(dino_checkpoint), map_location="cpu", weights_only=True)
    dino_model.load_state_dict(state, strict=True)
    dino_model.requires_grad_(False)
    dino_model.eval()
    dino_model.to(device)
    _require(not dino_model.training and
             not any(parameter.requires_grad for parameter in
                     dino_model.parameters()),
             "F-01 DINOv2 did not freeze")
    if sam_builder is None or sam_generator_factory is None:
        sys.path.insert(0, str(Path(sam_repository).resolve()))
        try:
            if sam_builder is None:
                from sam2.build_sam import build_sam2 as sam_builder
            if sam_generator_factory is None:
                from sam2.automatic_mask_generator import (
                    SAM2AutomaticMaskGenerator as sam_generator_factory)
        finally:
            sys.path.pop(0)
    sam = value["assets"]["sam2"]
    config_name = sam["official_model_config_path"]
    if config_name.startswith("sam2/"):
        config_name = config_name[len("sam2/"):]
    sam_model = sam_builder(
        config_name, str(Path(sam_checkpoint)), device=device)
    if hasattr(sam_model, "requires_grad_"):
        sam_model.requires_grad_(False)
    if hasattr(sam_model, "eval"):
        sam_model.eval()
    sam_generator = sam_generator_factory(
        sam_model, **sam["automatic_mask_generator"])
    descriptor_config = build_frontend_config(value).descriptor

    def extract(rgb: np.ndarray) -> np.ndarray:
        return extract_dinov2_patch_tokens(
            dino_model, rgb, descriptor_config, device=device)

    return sam_generator, extract, receipt
