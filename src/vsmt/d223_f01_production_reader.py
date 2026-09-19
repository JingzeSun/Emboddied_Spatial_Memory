"""D-223/F-01 scenario-blind production RGB-D reader.

This is the production cache profile.  It shares its composition and sealing
mechanics with the legacy D-214 profile through ``shared_frontend_core``, and
differs from it only where D-223 says it must: no learned semantic or
structural field appears in this profile's signatures or cache bytes, and the
E-06 structural head is never loaded.  The two profiles seal different schemas
on purpose, so each keeps its own explicit validator with its own literal
field set rather than one validator that accepts both layouts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import inspect
import io
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import zipfile
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from cpmt.hashing import canonical_json, clone_json
from .d210_place_memory import build_continuous_pose_belief
from .l1_entities import (
    DINORegionConfig,
    PublicGeometryConfig,
    extract_dinov2_patch_tokens,
)
from .l1_masks import AnonymousMask, KEEP_SUPPORTED_BORDER_REGIONS
from .l1_structures import (
    FreeSpaceFrustum,
    FreeSpaceMaterializationConfig,
    SurfaceMaterializationConfig,
)
from . import shared_frontend_core as core
from .vm04_l2_proposals import (
    PROMPT_POLICY,
    Vm04L2ProposalConfig,
    run_vm04_l2_proposal_frontend,
)


CONTRACT_SCHEMA = "vsmt-vm04-d223-f01-production-reader-v1"
FRAME_SCHEMA = "vsmt-vm04-d223-f01-production-frame-cache-v1"
EPISODE_SCHEMA = "vsmt-vm04-d223-f01-production-episode-cache-v1"
INPUT_SCHEMA = "vsmt-vm04-d223-f01-public-episode-input-v1"
D224_SCHEMA = "vsmt-vm04-d224-frozen-sam2-asset-acquisition-v1"
# Every remaining SAM2AutomaticMaskGenerator.__init__ argument at the pinned
# commit that affects which masks come back.  D-215 froze ten arguments and
# these six fell through to library defaults; they are recorded, not changed.
SAM_RECORDED_DEFAULTS = {
    "mask_threshold": 0.0,
    "crop_overlap_ratio": 512 / 1500,
    "crop_n_points_downscale_factor": 1,
    "point_grids": None,
    "use_m2m": False,
    "multimask_output": True,
}
BORDER_POLICY_EXECUTION_CONSTANT = "keep_if_minimum_support"
# The frozen SAM2 asset bytes D-215 pinned.  D-224 must restate exactly these
# when it opens the download and dependency bits by reference, so that the
# acquisition cannot quietly aim at a different commit, config or checkpoint.
SAM_FROZEN_ASSET_BYTES = {
    "sam2_repository_url": "https://github.com/facebookresearch/sam2",
    "sam2_repository_commit": "2b90b9f5ceec907a1c18123530e92e794ad901a4",
    "sam2_official_model_config_path":
        "sam2/configs/sam2.1/sam2.1_hiera_s.yaml",
    "sam2_official_model_config_bytes": 3761,
    "sam2_official_model_config_sha256":
        "0f36b91e86e58d06c87e42997166212468b88b98b60e4d816d5e4d4d088b6f55",
    "sam2_checkpoint_url":
        "https://dl.fbaipublicfiles.com/segment_anything_2/092824/"
        "sam2.1_hiera_small.pt",
    "sam2_checkpoint_bytes": 184416285,
    "sam2_checkpoint_sha256":
        "6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38",
}
D217_PUBLIC_SCHEMA = "vsmt-vm04-d217-public-rgbd-house-v1"
D217_SAMPLE_DIRECTORY = re.compile(r"^sample_([0-9]{4})$")
D217_OBSERVATION_COUNT = 32
D217_IMAGE_SHAPE = (224, 224)
D217_POSE_SOURCE_ID = "d223.f01.d217_public_observation_zero_origin.v1"
D217_SELECTION_POLICY = {
    "source_split": "train",
    "selection": "ascending_sample_rank_first_present_public_sample",
    "selected_sample_incomplete_or_malformed": "fail_do_not_skip",
    "selected_observation_index": 0,
}
MAIN_METHODS = core.MAIN_METHODS
FRAGMENT_SOURCE_ID = "d223.sam2.1_hiera_small.fragment.dinov2_vits14.public_depth.v1"
SURFACE_SOURCE_ID = core.SURFACE_SOURCE_ID
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
        # The contract's policy name and the executed constant are two
        # vocabularies for one rule; the mapping is recorded, not implied.
        border_truncation_policy=sam["border_truncation_policy_execution_constant"],
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


def validate_d224_supersession(
    contract: Mapping[str, Any], *, expected_d215_file_sha256: str,
) -> str:
    """Check the D-224 by-reference supersession and return its core digest.

    D-215 closed ``server_asset_download`` and ``dependency_install``, but its
    bytes are hash-bound by d216, d217 and d218 and were already executed
    against, so the two bits are reopened by reference in D-224 rather than by
    rewriting D-215 -- the same shape D-219 used for its own D-215 clauses.
    F-01 binds the digest of the governance core alone, so opening and later
    reclosing the acquisition bits cannot break the binding, while the two
    superseded clause names, the bound D-215 digest and the expected asset
    bytes cannot move without breaking it.
    """

    value = clone_json(dict(contract))
    _require(value.get("schema_version") == D224_SCHEMA and
             value.get("decision_id") == "D-224",
             "D-224 supersession contract identity changed")
    core = value.get("supersession_core")
    _require(type(core) is dict, "D-224 supersession core is missing")
    superseded = core.get("supersedes")
    _require(type(superseded) is dict and
             superseded.get("d215_clauses_replaced") == [
                 "authorization.server_asset_download",
                 "authorization.dependency_install"] and
             superseded.get("predecessor_bytes_must_not_change") is True and
             superseded.get("supersession_is_by_reference_not_by_rewrite") is True,
             "D-224 must supersede exactly the two D-215 bits by reference")
    predecessor = core.get("frozen_predecessor_bindings")
    _require(type(predecessor) is dict and
             predecessor.get("d215_relative_path") ==
             "configs/vsmt/vm04_d215_frontend_freeze_v1.json" and
             predecessor.get("d215_file_sha256") == expected_d215_file_sha256,
             "D-224 binds different D-215 bytes than F-01 does")
    expected = core.get("expected_assets")
    sam = SAM_FROZEN_ASSET_BYTES
    _require(type(expected) is dict and
             all(expected.get(name) == expected_value
                 for name, expected_value in sam.items()),
             "D-224 expected SAM2 asset bytes differ from the frozen pins")
    _require(core.get("digest_mismatch_policy", {}).get("action") ==
             "stop_and_report_verbatim" and
             not any(flag for name, flag in
                     core.get("digest_mismatch_policy", {}).items()
                     if name != "action" and type(flag) is bool),
             "D-224 must stop on a digest mismatch rather than substitute")
    digest = _sha(core)
    _require(_hex64(value.get("supersession_core_sha256"),
                    "D-224 supersession_core_sha256") == digest,
             "D-224 supersession core digest does not match its own bytes")
    return digest


def validate_f01_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    value = clone_json(dict(contract))
    _require(set(value) == {
        "schema_version", "decision_id", "stage_id", "status",
        "reviewed_baseline_commit",
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
            "52c5daef8cee309cb99fc0e4edaf98ffafc8e0f4a3c0ae4c1ce85ee6391591dd",
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
        "d224_relative_path":
            "configs/vsmt/vm04_d224_frozen_sam2_asset_acquisition_v1.json",
        "d224_supersession_core_sha256":
            "cd825cad1c95c53eb404c851a2d8b1d08cccfbc3d86e5c8b438b9635ba9238b4",
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
    _require(set(policy) == {
        "active_status", "active_true_authorizations", "must_remain_false",
        "executable_checkout_must_be_clean", "execution_protocol",
        "run_receipt_must_record",
    }, "F-01 activation policy fields changed")
    _require(policy["active_status"] == active and
             set(policy["active_true_authorizations"]) == active_true and
             set(policy["must_remain_false"]) == expected_auth - active_true and
             policy["executable_checkout_must_be_clean"] is True and
             policy["execution_protocol"] ==
             "d220_contract_bits_plus_clean_checkout_plus_run_receipt" and
             policy["run_receipt_must_record"] == [
                 "execution_commit", "contract_sha256", "input_digests",
                 "output_digests", "resource_basis", "failures"],
             "F-01 activation policy changed")
    if value["status"] == pending:
        _require(not any(authorization.values()),
                 "F-01 review candidate must keep execution closed")
    else:
        _require({name for name, enabled in authorization.items() if enabled} ==
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
        "automatic_mask_generator_recorded_defaults": dict(
            SAM_RECORDED_DEFAULTS),
        "automatic_mask_generator_recorded_defaults_note":
            sam.get("automatic_mask_generator_recorded_defaults_note"),
        "automatic_mask_generator_argument_source":
            "sam2/automatic_mask_generator.py::SAM2AutomaticMaskGenerator.__init__",
        "minimum_visible_pixels": 196, "maximum_proposals_per_frame": 64,
        "border_truncation_policy":
            "retain_if_minimum_visible_pixels_met",
        "border_truncation_policy_execution_constant":
            BORDER_POLICY_EXECUTION_CONSTANT,
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
    _require(type(sam[
        "automatic_mask_generator_recorded_defaults_note"]) is str and
        sam["automatic_mask_generator_recorded_defaults_note"],
        "F-01 recorded generator defaults need their provenance note")
    _require(BORDER_POLICY_EXECUTION_CONSTANT ==
             KEEP_SUPPORTED_BORDER_REGIONS,
             "F-01 border policy no longer maps onto a known constant")
    _require(not (set(SAM_RECORDED_DEFAULTS) &
                  set(sam["automatic_mask_generator"])),
             "F-01 recorded defaults must not restate a D-215 frozen value")
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
    return core.validate_pose_belief(
        value, index, error=D223F01Error, label="F-01")


def _geometry_pose(value: Mapping[str, Any]) -> dict[str, Any]:
    return core.validate_causal_pose(value, error=D223F01Error, label="F-01")


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
    fragments, surface_records = core.materialize_public_regions(
        masks=tuple(public_fragment_masks), patch_tokens=patch_tokens,
        depth_m=depth, calibration=calibration,
        geometry_pose=geometry_pose, descriptor=config.descriptor,
        fragment_geometry=config.fragment_geometry, surface=config.surface,
        fragment_source_id=FRAGMENT_SOURCE_ID, error=D223F01Error,
        label="F-01",
    )
    regions = [*fragments, *surface_records]
    pose_digest = _sha({"calibration": calibration,
                        "causal_pose": geometry_pose})
    support = core.materialize_place_support(
        depth_m=depth, calibration=calibration,
        geometry_pose=geometry_pose, patch_tokens=patch_tokens,
        descriptor=config.descriptor, free_space=config.free_space,
        time_s=time_s, depth_sha256=depth_source_sha256,
        calibration_and_pose_sha256=pose_digest,
        prior_free_space=prior_free_space,
    )
    current_free_space = support.current_free_space
    free_space, visibility = support.free_space, support.visibility
    # Production reliability clips depth to the configured range as well as
    # requiring it finite; the legacy D-214 profile only requires finite.
    valid_depth = (np.isfinite(depth) &
                   (depth >= config.fragment_geometry.minimum_depth_m) &
                   (depth <= config.fragment_geometry.maximum_depth_m))
    place = {
        "place_observation_id": f"place-observation:{observation_index:04d}",
        "observation_index": observation_index,
        "persistent_place_id": None, "identity_assigned": False,
        "metric_grid_identity_used": False,
        "descriptor": support.place_descriptor,
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
    core.validate_region_records(
        value["fragment_observations"], value["surface_observations"],
        fragment_source_id=FRAGMENT_SOURCE_ID,
        require_unit_descriptor=True, error=D223F01Error, label="F-01",
    )
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
    _hex64(frozen_assets_receipt_sha256, "F-01 frozen assets receipt")
    episode = core.seal_ordered_episode(
        frames, schema_version=EPISODE_SCHEMA,
        episode_public_id=episode_public_id,
        extra_fields={
            "frozen_assets_receipt_sha256": frozen_assets_receipt_sha256,
            "public_only_materialization": True,
            "restricted_information_used": False,
        },
        frame_validator=validate_frame_cache,
        reject_forbidden_keys=_reject_forbidden_keys,
        error=D223F01Error, label="F-01",
    )
    _require({row["frozen_assets_receipt_sha256"]
              for row in episode["frames"]} ==
             {frozen_assets_receipt_sha256},
             "F-01 frames used a different frozen assets receipt")
    return episode


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
    return core.identical_method_cache_views(
        episode, episode_validator=validate_episode_cache,
        error=D223F01Error, label="F-01",
    )


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


def resolve_generator_arguments(
    sam: Mapping[str, Any], factory: Any,
) -> dict[str, Any]:
    """Merge the frozen and recorded generator arguments, refusing drift.

    D-215 froze ten arguments; the contract additionally records the six
    remaining ones that affect which masks come back.  Every argument is
    passed explicitly so the call never depends on a library default, and
    two failure modes are refused outright: an argument the constructor does
    not name -- its ``**kwargs`` would otherwise swallow a misspelled
    contract key -- and a recorded default whose library value has moved away
    from the pinned commit.
    """

    frozen = dict(sam["automatic_mask_generator"])
    recorded = dict(sam["automatic_mask_generator_recorded_defaults"])
    overlap = sorted(set(frozen) & set(recorded))
    _require(not overlap,
             f"F-01 recorded defaults restate frozen values: {overlap}")
    arguments = {**frozen, **recorded}
    parameters = inspect.signature(factory.__init__).parameters
    missing = sorted(name for name in arguments if name not in parameters)
    _require(not missing,
             f"F-01 generator does not name these arguments: {missing}")
    for name, expected in recorded.items():
        default = parameters[name].default
        _require(default == expected,
                 f"F-01 recorded generator default {name} drifted from the "
                 f"pinned commit: library has {default!r}, contract "
                 f"has {expected!r}")
    return arguments


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
    arguments = resolve_generator_arguments(sam, sam_generator_factory)
    sam_generator = sam_generator_factory(sam_model, **arguments)
    descriptor_config = build_frontend_config(value).descriptor

    def extract(rgb: np.ndarray) -> np.ndarray:
        return extract_dinov2_patch_tokens(
            dino_model, rgb, descriptor_config, device=device)

    return sam_generator, extract, receipt


# --- D-217 public compatibility input ---------------------------------
#
# The server holds D-217 public RGB-D houses but no bundle in the exact F-01
# input schema.  These helpers turn observation zero of the lowest-rank
# public/train sample into one F-01 frame so the frozen assets and the reader
# can be exercised together.  A single origin-pose frame is diagnostic only:
# it cannot exercise temporal memory, and it is not formal data, not P04/P08
# evidence, and not a paper result.  Source provenance is recorded in the one
# F-01 run receipt, never inside the method-visible manifest.


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Refuse a source receipt that repeats a key, which JSON would hide."""

    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate D-217 public JSON key: {key}")
        result[key] = value
    return result


def validate_d217_public_receipt(
    receipt: Mapping[str, Any], *, expected_rank: int, rgbd_npz_sha256: str,
) -> dict[str, Any]:
    value = clone_json(dict(receipt))
    _require(set(value) == {
        "schema_version", "split", "sample_rank", "public_house_ref",
        "observation_count", "observation_ids_sha256", "rgbd_npz_sha256",
        "contains_house_world_pose_grid_instance_scenario_teacher_or_future",
        "public_receipt_sha256",
    }, "selected D-217 public receipt fields changed")
    _require(value["schema_version"] == D217_PUBLIC_SCHEMA and
             value["split"] == "train" and
             type(value["sample_rank"]) is int and
             value["sample_rank"] == expected_rank and
             type(value["public_house_ref"]) is str and
             bool(value["public_house_ref"]) and
             value["observation_count"] == D217_OBSERVATION_COUNT and
             value[
                 "contains_house_world_pose_grid_instance_scenario_teacher_or_future"
             ] is False,
             "selected D-217 public receipt identity changed")
    _require(type(value["observation_ids_sha256"]) is str and
             HEX64.fullmatch(value["observation_ids_sha256"]) is not None and
             value["rgbd_npz_sha256"] == rgbd_npz_sha256 and
             type(value["public_receipt_sha256"]) is str and
             HEX64.fullmatch(value["public_receipt_sha256"]) is not None,
             "selected D-217 public receipt digest fields changed")
    _require(value["public_receipt_sha256"] ==
             _payload_sha(value, "public_receipt_sha256"),
             "selected D-217 public receipt self digest changed")
    return value


def validate_d217_public_arrays(
    arrays: Mapping[str, Any], receipt: Mapping[str, Any],
) -> dict[str, np.ndarray]:
    _require(set(arrays) == {
        "rgb_uint8", "depth_m_float32", "camera_intrinsics_float64",
        "observation_ids",
    }, "selected D-217 public NPZ fields changed")
    rgb = np.ascontiguousarray(np.asarray(arrays["rgb_uint8"]))
    depth = np.ascontiguousarray(np.asarray(arrays["depth_m_float32"]))
    intrinsics = np.ascontiguousarray(
        np.asarray(arrays["camera_intrinsics_float64"]))
    observation_ids = np.asarray(arrays["observation_ids"])
    _require(rgb.dtype == np.uint8 and
             rgb.shape == (D217_OBSERVATION_COUNT, *D217_IMAGE_SHAPE, 3),
             "selected D-217 RGB dtype or shape changed")
    _require(depth.dtype == np.float32 and
             depth.shape == (D217_OBSERVATION_COUNT, *D217_IMAGE_SHAPE),
             "selected D-217 depth dtype or shape changed")
    _require(intrinsics.dtype == np.float64 and
             intrinsics.shape == (D217_OBSERVATION_COUNT, 4) and
             bool(np.all(np.isfinite(intrinsics))) and
             bool(np.all(intrinsics[:, :2] > 0.0)),
             "selected D-217 camera intrinsics changed")
    _require(observation_ids.shape == (D217_OBSERVATION_COUNT,) and
             observation_ids.dtype.kind == "U",
             "selected D-217 observation IDs changed")
    ids = [str(item) for item in observation_ids.tolist()]
    _require(all(HEX64.fullmatch(item) is not None for item in ids) and
             len(set(ids)) == D217_OBSERVATION_COUNT and
             _sha(ids) == receipt["observation_ids_sha256"],
             "selected D-217 observation ID commitment changed")
    return {
        "rgb_uint8": rgb,
        "depth_m_float32": depth,
        "camera_intrinsics_float64": intrinsics,
        "observation_ids": np.asarray(ids),
    }


def select_first_d217_public_train_sample(
    public_root: Path,
) -> tuple[Path, dict[str, Any], dict[str, np.ndarray]]:
    """Read the lowest-rank existing public/train sample, never a later fallback."""

    root = Path(public_root)
    train_root = root / "train"
    _require(root.name == "public" and root.is_dir() and not root.is_symlink(),
             "D-217 public root is missing or is a symlink")
    _require(train_root.is_dir() and not train_root.is_symlink(),
             "D-217 public/train root is missing or is a symlink")
    candidates: list[tuple[int, Path]] = []
    for child in train_root.iterdir():
        match = D217_SAMPLE_DIRECTORY.fullmatch(child.name)
        if match is not None and child.is_dir():
            candidates.append((int(match.group(1)), child))
    _require(bool(candidates), "D-217 public/train contains no successful sample")
    rank, selected = min(candidates, key=lambda item: item[0])
    _require(not selected.is_symlink(),
             "selected D-217 public sample is a symlink")
    _require(sorted(item.name for item in selected.iterdir()) ==
             ["receipt.json", "rgbd.npz"],
             "selected D-217 public sample is incomplete or has extra files")
    receipt_path, npz_path = selected / "receipt.json", selected / "rgbd.npz"
    _require(receipt_path.is_file() and not receipt_path.is_symlink() and
             npz_path.is_file() and not npz_path.is_symlink(),
             "selected D-217 public sample files are missing or symlinked")
    try:
        receipt = json.loads(
            receipt_path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicates)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise D223F01Error(
            "selected D-217 public receipt is unreadable") from error
    validated_receipt = validate_d217_public_receipt(
        receipt, expected_rank=rank, rgbd_npz_sha256=_sha_file(npz_path))
    try:
        with np.load(npz_path, allow_pickle=False) as source:
            _require(set(source.files) == {
                "rgb_uint8", "depth_m_float32", "camera_intrinsics_float64",
                "observation_ids",
            }, "selected D-217 public NPZ fields changed")
            arrays = {name: source[name] for name in source.files}
    except D223F01Error:
        raise
    except (OSError, ValueError, KeyError) as error:
        raise D223F01Error(
            "selected D-217 public NPZ is unreadable") from error
    return selected, validated_receipt, validate_d217_public_arrays(
        arrays, validated_receipt)


def _npy_bytes(array: np.ndarray) -> bytes:
    output = io.BytesIO()
    np.lib.format.write_array(
        output, np.ascontiguousarray(array), allow_pickle=False)
    return output.getvalue()


def deterministic_f01_npz_bytes(
    *, rgb_uint8: np.ndarray, depth_m_float32: np.ndarray,
) -> bytes:
    """Serialize exact F-01 arrays without timestamps or platform metadata."""

    arrays = {
        "depth_m_float32.npy": np.ascontiguousarray(depth_m_float32),
        "rgb_uint8.npy": np.ascontiguousarray(rgb_uint8),
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(arrays):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 0
            info.external_attr = 0
            archive.writestr(info, _npy_bytes(arrays[name]))
    return output.getvalue()


def build_observation_zero_compat_input(
    *, source_receipt: Mapping[str, Any], source_arrays: Mapping[str, Any],
    frontend_config_sha256: str,
) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    """Build one anonymous origin-pose frame and its source provenance.

    Returns the deterministic NPZ bytes, the method-visible manifest, and a
    provenance block for the F-01 run receipt.  The manifest deliberately
    carries no sample rank, public house ref, or raw observation ID.
    """

    raw_receipt = clone_json(dict(source_receipt))
    _require(type(raw_receipt.get("sample_rank")) is int and
             type(raw_receipt.get("rgbd_npz_sha256")) is str,
             "selected D-217 public receipt identity changed")
    receipt = validate_d217_public_receipt(
        raw_receipt, expected_rank=raw_receipt["sample_rank"],
        rgbd_npz_sha256=raw_receipt["rgbd_npz_sha256"])
    _hex64(frontend_config_sha256, "F-01 frontend config digest")
    arrays = validate_d217_public_arrays(source_arrays, receipt)
    rgb = np.ascontiguousarray(arrays["rgb_uint8"][:1])
    depth = np.ascontiguousarray(arrays["depth_m_float32"][:1])
    intrinsics = arrays["camera_intrinsics_float64"][0]
    observation_id = str(arrays["observation_ids"][0])
    npz_bytes = deterministic_f01_npz_bytes(
        rgb_uint8=rgb, depth_m_float32=depth)
    arrays_digest = hashlib.sha256(npz_bytes).hexdigest()
    observation_id_digest = hashlib.sha256(
        observation_id.encode("utf-8")).hexdigest()
    episode_public_id = "d223-f01-compat-" + _sha({
        "domain": "d223-f01-d217-public-observation-zero",
        "source_public_receipt_sha256": receipt["public_receipt_sha256"],
        "source_observation_id_sha256": observation_id_digest,
        "frontend_config_sha256": frontend_config_sha256,
    })[:24]
    pose_belief = build_continuous_pose_belief(
        observation_index=0, mean_x_y_z_yaw=[0.0, 0.0, 0.0, 0.0],
        covariance_diagonal=[0.0, 0.0, 0.0, 0.0],
        source_id=D217_POSE_SOURCE_ID)
    manifest = validate_public_input_manifest(_seal({
        "schema_version": INPUT_SCHEMA,
        "episode_public_id": episode_public_id,
        "frame_count": 1,
        "arrays_npz_sha256": arrays_digest,
        "rows": [{
            "observation_index": 0,
            "decision_time_s": 0.0,
            "rgb_source_sha256": public_array_sha256(rgb[0]),
            "depth_source_sha256": public_array_sha256(depth[0]),
            "camera_intrinsics": {
                "fx": float(intrinsics[0]), "fy": float(intrinsics[1]),
                "cx": float(intrinsics[2]), "cy": float(intrinsics[3]),
            },
            "causal_episode_relative_camera_pose": {
                "position_m": [0.0, 0.0, 0.0],
                "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
                "is_world_pose": False,
                "source_id": D217_POSE_SOURCE_ID,
            },
            "continuous_pose_belief": pose_belief,
            "incoming_transition_action_summary": None,
        }],
        "restricted_information_used": False,
    }, "manifest_sha256"))
    provenance = {
        "mode": "d217_public_observation_zero_compatibility",
        "compatibility_only": True,
        "formal_data_p04_p08_or_paper_eligible": False,
        "source_schema": D217_PUBLIC_SCHEMA,
        "source_split": "train",
        "selected_sample_rank": receipt["sample_rank"],
        "selected_observation_index": 0,
        "source_public_receipt_sha256": receipt["public_receipt_sha256"],
        "source_rgbd_npz_sha256": receipt["rgbd_npz_sha256"],
        "source_observation_id_sha256": observation_id_digest,
        "selection_policy_sha256": _sha(D217_SELECTION_POLICY),
        "private_input_read": False,
        "calibration_or_audit_input_read": False,
    }
    _reject_forbidden_keys(manifest)
    return npz_bytes, manifest, provenance
