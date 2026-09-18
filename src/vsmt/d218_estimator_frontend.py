"""D-218 blind semantic annotation and frozen public feature extraction.

The pure functions in this module accept only one public RGB-D observation or
already-blinded task records.  They expose no simulator, house, route, private
label, estimator-training, production-reader, or P04/P08 API.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any, Mapping, Sequence

import numpy as np

from cpmt.hashing import canonical_json, clone_json
from .d215_frontend_freeze import GEOMETRY_FEATURE_ORDER, validate_d215_contract
from .d217_estimator_development import validate_d217_contract
from .l1_entities import DINORegionConfig, pool_dinov2_region_descriptor
from .l1_structures import SurfaceMaterializationConfig, materialize_public_surfaces


CONTRACT_SCHEMA = "vsmt-vm04-d218-estimator-annotation-features-v1"
ANNOTATION_PACKAGE_SCHEMA = "vsmt-vm04-d218-blind-annotation-package-v1"
ANNOTATION_SUBMISSION_SCHEMA = "vsmt-vm04-d218-blind-annotation-submission-v1"
ADJUDICATION_SCHEMA = "vsmt-vm04-d218-semantic-adjudication-v1"
FEATURE_SHARD_SCHEMA = "vsmt-vm04-d218-public-feature-shard-v1"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
LABELS = ("room", "corridor", "unknown")
PACKAGE_ROLES = ("annotator_a", "annotator_b")


class D218Error(ValueError):
    """A stable D-218 contract, annotation, or feature construction failure."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise D218Error(message)


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _array_sha(array: Any) -> str:
    value = np.ascontiguousarray(np.asarray(array))
    return hashlib.sha256(value.tobytes(order="C")).hexdigest()


def _seal(value: Mapping[str, Any], field: str) -> dict[str, Any]:
    result = clone_json(dict(value))
    result[field] = _sha(result)
    return result


def _exact(value: Mapping[str, Any], fields: set[str], name: str) -> None:
    _require(type(value) is dict and set(value) == fields,
             f"{name} has unexpected fields")


def _hex(value: Any, length: int, name: str) -> str:
    pattern = HEX40 if length == 40 else HEX64
    _require(type(value) is str and pattern.fullmatch(value) is not None,
             f"{name} must be a lowercase SHA-{length * 4}")
    return value


def validate_d218_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the implementation candidate and keep all execution closed."""

    value = clone_json(dict(contract))
    _exact(value, {
        "schema_version", "decision_id", "status", "reviewed_baseline_commit",
        "expected_reviewed_implementation_commit", "bindings", "authorization",
        "activation_policy", "annotation", "features", "closed_downstream",
    }, "D-218 contract")
    _require(value["schema_version"] == CONTRACT_SCHEMA and
             value["decision_id"] == "D-218" and value["status"] in {
                 "implementation_pending_review_all_execution_closed",
                 "frozen_executable_train_calibration_annotation_and_features",
             }, "D-218 identity or status changed")
    _require(value["reviewed_baseline_commit"] ==
             "af7aa8059bf235b7c812f2685e770f830dd5ae51",
             "D-218 reviewed baseline changed")
    bindings = value["bindings"]
    _require(bindings == {
        "d215_relative_path": "configs/vsmt/vm04_d215_frontend_freeze_v1.json",
        "d215_file_sha256":
            "c3d6736f67b300eca03882c081e56e6bf4d65ad1913bcc411df8477fbd188db8",
        "d217_relative_path":
            "configs/vsmt/vm04_d217_estimator_development_rgbd_v1.json",
        "d217_file_sha256":
            "1499806b8a34eb71ec0785128111b28236f8cee8b95b61a94f624c608702643d",
        "d217_generation_activation_commit":
            "0c4f9851006dbb996864c9af82d60ff4b28c09b2",
    }, "D-218 upstream binding changed")
    expected_auth = {
        "annotation_package_export", "annotation_submission_import",
        "feature_materialization", "audit_open_or_generation",
        "estimator_training", "full_house_expansion", "production_reader",
        "p04_p08_qualification", "route_or_raw_generation",
        "private_evaluation",
    }
    _require(set(value["authorization"]) == expected_auth,
             "D-218 authorization keys changed")
    policy = value["activation_policy"]
    active = {"annotation_package_export", "annotation_submission_import",
              "feature_materialization"}
    _require(set(policy) == {
        "active_status", "activation_commit_may_change_only",
        "active_true_authorizations", "must_remain_false"} and
        policy["active_status"] ==
        "frozen_executable_train_calibration_annotation_and_features" and
        policy["activation_commit_may_change_only"] == [
            "configs/vsmt/vm04_d218_estimator_annotation_features_v1.json"] and
        set(policy["active_true_authorizations"]) == active and
        set(policy["must_remain_false"]) == expected_auth - active,
        "D-218 activation policy changed")
    if value["status"] == "implementation_pending_review_all_execution_closed":
        _require(value["expected_reviewed_implementation_commit"] is None and
                 not any(value["authorization"].values()),
                 "D-218 review candidate must keep all execution closed")
    else:
        _hex(value["expected_reviewed_implementation_commit"], 40,
             "D-218 reviewed implementation commit")
        _require({name for name, enabled in value["authorization"].items()
                  if enabled} == active,
                 "D-218 active authorization scope changed")
    annotation = value["annotation"]
    _require(annotation["input"] == "single_frame_public_rgbd_only" and
             annotation["labels"] == list(LABELS) and
             annotation["package_roles"] == list(PACKAGE_ROLES) and
             annotation["independent_distinct_annotator_ids_required"] is True and
             annotation["shared_media_content_addressed"] is True and
             annotation["browser_network_dependency"] is False and
             annotation["disagreement_policy"] ==
             "independent_adjudicator_or_unknown" and
             {"house_id", "scenario_id", "world_pose", "reachable_grid",
              "room_metadata", "instance_mask", "object_id", "structural_label",
              "teacher", "future"}.issubset(
                  set(annotation["annotator_forbidden_fields"])),
             "D-218 blind annotation boundary changed")
    features = value["features"]
    dino = features["dinov2"]
    geometry = features["geometry"]
    _require(features["output_dimension"] == 396 and dino == {
        "model_id": "dinov2.vits14",
        "repository_url": "https://github.com/facebookresearch/dinov2",
        "repository_commit": "7764ea0f912e53c92e82eb78a2a1631e92725fc8",
        "checkpoint_sha256":
            "b938bf1bc15cd2ec0feacfe3a1bb553fe8ea9ca46a7e1d8d00217f29aef60cd9",
        "input_shape": [224, 224, 3], "patch_size_pixels": 14,
        "patch_grid": [16, 16], "patch_token_dimension": 384,
        "descriptor":
            "l2_normalized_full_frame_occupancy_weighted_mean_of_x_norm_patchtokens",
        "preprocessing":
            "uint8_srgb_to_float_0_1_then_imagenet_mean_std",
        "model_eval_and_parameters_frozen": True,
    }, "D-218 DINOv2 feature definition changed")
    _require(geometry["feature_order_source"] == "D-215" and
             geometry["valid_depth_range_m"] == [0.05, 20.0] and
             geometry["depth_quantile_method"] == "numpy_linear" and
             geometry["free_space_surface_clearance_m"] == 0.1 and
             geometry["volume_clip_m3"] == [0.0, 50.0] and
             geometry["clearance_quantile"] == 0.1 and
             geometry["surface_algorithm"] ==
             "D-205_frozen_public_depth_planar_surface_v1" and
             geometry["surface_tile_pixels"] == 14 and
             features["public_output_arrays"] == [
                 "features_float32", "observation_ids",
                 "public_observation_sha256"] and
             {"house_id", "scenario_id", "world_pose", "reachable_grid",
              "room_metadata", "instance_mask", "object_id", "semantic_label",
              "structural_label", "teacher", "future"}.issubset(
                  set(features["forbidden_inputs"])) and
             features["overwrite_allowed"] is False and
             features["wall_clock_timeout_allowed"] is False,
             "D-218 geometry or public feature boundary changed")
    _require(value["closed_downstream"] == {
        "audit_opened": False, "estimator_weights_produced": False,
        "production_cache_produced": False, "p04_p08_requalified": False,
        "route_or_raw_generated": False, "private_evaluation_run": False,
    }, "D-218 downstream execution boundary changed")
    return value


def validate_upstream_contracts(
    *, d215_contract: Mapping[str, Any], d217_contract: Mapping[str, Any],
    d218_contract: Mapping[str, Any],
) -> None:
    """Check semantic/feature freezes without opening any external paths."""

    validate_d215_contract(d215_contract)
    d217 = validate_d217_contract(d217_contract)
    d218 = validate_d218_contract(d218_contract)
    _require(d217["status"] == d217["activation_policy"]["active_status"] and
             d217["authorization"]["audit_open_or_generation"] is False and
             d217["authorization"]["estimator_training"] is False and
             d217["authorization"]["production_reader"] is False and
             d217["authorization"]["p04_p08_qualification"] is False and
             d217["authorization"]["route_or_raw_generation"] is False and
             d218["bindings"]["d217_generation_activation_commit"] ==
             "0c4f9851006dbb996864c9af82d60ff4b28c09b2",
             "D-218 requires the closed downstream D-217 generation contract")


def public_observation_sha256(
    *, observation_id: str, rgb_uint8: Any, depth_m_float32: Any,
    camera_intrinsics_float64: Any,
) -> str:
    """Content-address one public frame without a house or sample identifier."""

    rgb = np.asarray(rgb_uint8)
    depth = np.asarray(depth_m_float32)
    intrinsics = np.asarray(camera_intrinsics_float64)
    _require(type(observation_id) is str and HEX64.fullmatch(observation_id),
             "public observation ID must be an opaque SHA-256")
    _require(rgb.dtype == np.uint8 and rgb.shape == (224, 224, 3),
             "public RGB schema changed")
    _require(depth.dtype == np.float32 and depth.shape == (224, 224),
             "public depth schema changed")
    _require(intrinsics.dtype == np.float64 and intrinsics.shape == (4,) and
             np.isfinite(intrinsics).all() and
             intrinsics[0] > 0.0 and intrinsics[1] > 0.0,
             "public intrinsics schema changed")
    return _sha({
        "schema_version": "vsmt-vm04-d218-public-observation-content-v1",
        "observation_id": observation_id,
        "rgb_uint8_sha256": _array_sha(rgb),
        "depth_m_float32_sha256": _array_sha(depth),
        "camera_intrinsics_float64": [float(item) for item in intrinsics],
    })


def make_annotation_package(
    records: Sequence[Mapping[str, Any]], *, package_role: str,
    d218_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Seal one role-specific order over shared blinded media records."""

    contract = validate_d218_contract(d218_contract)
    _require(package_role in PACKAGE_ROLES, "annotation package role is invalid")
    forbidden = set(contract["annotation"]["annotator_forbidden_fields"])
    rows: list[dict[str, Any]] = []
    for index, raw in enumerate(records):
        _exact(raw, {
            "observation_id", "public_observation_sha256", "rgb_media_path",
            "rgb_media_sha256", "depth_media_path", "depth_media_sha256",
        }, f"annotation media records[{index}]")
        _require(not (set(raw) & forbidden),
                 "annotation media record exposes a forbidden field")
        observation_id = raw["observation_id"]
        public_sha = _hex(raw["public_observation_sha256"], 64,
                          "public observation")
        _hex(observation_id, 64, "opaque observation ID")
        _hex(raw["rgb_media_sha256"], 64, "RGB media")
        _hex(raw["depth_media_sha256"], 64, "depth media")
        for field in ("rgb_media_path", "depth_media_path"):
            path = raw[field]
            _require(type(path) is str and path.startswith("../../media/") and
                     "\\" not in path and ".." not in path[6:],
                     "annotation media path is not a safe shared-media path")
        rows.append({
            "task_id": _sha({"role": package_role,
                             "observation_id": observation_id}),
            "observation_id": observation_id,
            "public_observation_sha256": public_sha,
            "rgb_media_path": raw["rgb_media_path"],
            "rgb_media_sha256": raw["rgb_media_sha256"],
            "depth_media_path": raw["depth_media_path"],
            "depth_media_sha256": raw["depth_media_sha256"],
        })
    rows.sort(key=lambda row: hashlib.sha256(
        f"{package_role}|{row['observation_id']}".encode("utf-8")).hexdigest())
    ids = [row["observation_id"] for row in rows]
    _require(rows and len(ids) == len(set(ids)),
             "annotation observations must be nonempty and unique")
    return _seal({
        "schema_version": ANNOTATION_PACKAGE_SCHEMA,
        "package_role": package_role,
        "labels": list(LABELS),
        "input": "single_frame_public_rgbd_only",
        "task_count": len(rows),
        "tasks": rows,
        "scenario_house_route_identity_included": False,
        "private_or_structural_label_included": False,
        "network_dependency": False,
    }, "annotation_package_sha256")


def validate_annotation_package(
    package: Mapping[str, Any], *, d218_contract: Mapping[str, Any],
) -> dict[str, Any]:
    value = clone_json(dict(package))
    _exact(value, {
        "schema_version", "package_role", "labels", "input", "task_count",
        "tasks", "scenario_house_route_identity_included",
        "private_or_structural_label_included", "network_dependency",
        "annotation_package_sha256",
    }, "annotation package")
    _require(value["schema_version"] == ANNOTATION_PACKAGE_SCHEMA and
             value["labels"] == list(LABELS) and
             value["input"] == "single_frame_public_rgbd_only" and
             value["scenario_house_route_identity_included"] is False and
             value["private_or_structural_label_included"] is False and
             value["network_dependency"] is False and
             value["task_count"] == len(value["tasks"]),
             "annotation package boundary changed")
    records = [{key: row[key] for key in (
        "observation_id", "public_observation_sha256", "rgb_media_path",
        "rgb_media_sha256", "depth_media_path", "depth_media_sha256")}
               for row in value["tasks"]]
    rebuilt = make_annotation_package(
        records, package_role=value["package_role"],
        d218_contract=d218_contract)
    _require(value == rebuilt, "annotation package content or receipt changed")
    return value


def make_annotation_submission(
    *, package: Mapping[str, Any], annotator_id: str,
    labels_by_task_id: Mapping[str, str], d218_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate a complete offline response and bind it to one blind package."""

    manifest = validate_annotation_package(
        package, d218_contract=d218_contract)
    _require(type(annotator_id) is str and annotator_id.strip() == annotator_id and
             3 <= len(annotator_id) <= 64,
             "annotator ID must be a stable 3--64 character code")
    expected = {row["task_id"] for row in manifest["tasks"]}
    _require(set(labels_by_task_id) == expected,
             "annotation submission must label every task exactly once")
    rows = []
    for task in manifest["tasks"]:
        label = labels_by_task_id[task["task_id"]]
        _require(label in LABELS, "annotation submission contains an invalid label")
        rows.append({"task_id": task["task_id"], "label": label})
    return _seal({
        "schema_version": ANNOTATION_SUBMISSION_SCHEMA,
        "package_role": manifest["package_role"],
        "annotation_package_sha256": manifest["annotation_package_sha256"],
        "annotator_id": annotator_id,
        "rows": rows,
        "row_count": len(rows),
        "other_annotator_results_seen": False,
        "scenario_house_route_identity_seen": False,
    }, "annotation_submission_sha256")


def validate_annotation_submission(
    submission: Mapping[str, Any], *, package: Mapping[str, Any],
    d218_contract: Mapping[str, Any],
) -> dict[str, Any]:
    value = clone_json(dict(submission))
    _exact(value, {
        "schema_version", "package_role", "annotation_package_sha256",
        "annotator_id", "rows", "row_count", "other_annotator_results_seen",
        "scenario_house_route_identity_seen", "annotation_submission_sha256",
    }, "annotation submission")
    _require(value["schema_version"] == ANNOTATION_SUBMISSION_SCHEMA and
             value["other_annotator_results_seen"] is False and
             value["scenario_house_route_identity_seen"] is False and
             value["row_count"] == len(value["rows"]),
             "annotation submission boundary changed")
    labels = {row["task_id"]: row["label"] for row in value["rows"]}
    _require(len(labels) == len(value["rows"]),
             "annotation submission task IDs are duplicated")
    rebuilt = make_annotation_submission(
        package=package, annotator_id=value["annotator_id"],
        labels_by_task_id=labels, d218_contract=d218_contract)
    _require(value == rebuilt, "annotation submission content or receipt changed")
    return value


def adjudicate_annotations(
    *, package_a: Mapping[str, Any], package_b: Mapping[str, Any],
    submission_a: Mapping[str, Any], submission_b: Mapping[str, Any],
    adjudicator_id: str | None, adjudicated_labels_by_observation_id:
        Mapping[str, str] | None,
    d218_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Merge independent labels; unresolved disagreements become unknown."""

    a_package = validate_annotation_package(
        package_a, d218_contract=d218_contract)
    b_package = validate_annotation_package(
        package_b, d218_contract=d218_contract)
    _require(a_package["package_role"] == "annotator_a" and
             b_package["package_role"] == "annotator_b",
             "adjudication requires the A and B package roles")
    a = validate_annotation_submission(
        submission_a, package=a_package, d218_contract=d218_contract)
    b = validate_annotation_submission(
        submission_b, package=b_package, d218_contract=d218_contract)
    _require(a["annotator_id"] != b["annotator_id"],
             "the two blind annotations must come from different annotators")
    task_a = {row["task_id"]: row for row in a_package["tasks"]}
    task_b = {row["task_id"]: row for row in b_package["tasks"]}
    labels_a = {task_a[row["task_id"]]["observation_id"]: row["label"]
                for row in a["rows"]}
    labels_b = {task_b[row["task_id"]]["observation_id"]: row["label"]
                for row in b["rows"]}
    public_a = {row["observation_id"]: row["public_observation_sha256"]
                for row in a_package["tasks"]}
    public_b = {row["observation_id"]: row["public_observation_sha256"]
                for row in b_package["tasks"]}
    _require(public_a == public_b and set(labels_a) == set(labels_b),
             "blind annotation packages do not cover identical public observations")
    supplied = dict(adjudicated_labels_by_observation_id or {})
    disagreements = {key for key in labels_a if labels_a[key] != labels_b[key]}
    _require(set(supplied).issubset(disagreements) and
             all(label in LABELS for label in supplied.values()),
             "adjudication labels must address only disagreements")
    if adjudicator_id is None:
        _require(not supplied, "adjudication labels require an adjudicator ID")
    else:
        _require(type(adjudicator_id) is str and 3 <= len(adjudicator_id) <= 64 and
                 adjudicator_id not in {a["annotator_id"], b["annotator_id"]},
                 "adjudicator must be distinct from both annotators")
    rows = []
    for observation_id in sorted(labels_a):
        same = labels_a[observation_id] == labels_b[observation_id]
        unresolved = not same and observation_id not in supplied
        final = labels_a[observation_id] if same else supplied.get(
            observation_id, "unknown")
        rows.append({
            "observation_id": observation_id,
            "public_observation_sha256": public_a[observation_id],
            "annotator_a_label": labels_a[observation_id],
            "annotator_b_label": labels_b[observation_id],
            "adjudicated_label": final,
            "unresolved_disagreement": unresolved,
            "resolution": ("agreement" if same else
                           "independent_adjudication" if not unresolved else
                           "unresolved_unknown"),
        })
    return _seal({
        "schema_version": ADJUDICATION_SCHEMA,
        "package_a_sha256": a_package["annotation_package_sha256"],
        "package_b_sha256": b_package["annotation_package_sha256"],
        "submission_a_sha256": a["annotation_submission_sha256"],
        "submission_b_sha256": b["annotation_submission_sha256"],
        "annotator_a_id": a["annotator_id"],
        "annotator_b_id": b["annotator_id"],
        "adjudicator_id": adjudicator_id,
        "row_count": len(rows),
        "disagreement_count": len(disagreements),
        "unresolved_disagreement_count": sum(
            row["unresolved_disagreement"] for row in rows),
        "rows": rows,
        "scenario_house_route_identity_used": False,
    }, "semantic_adjudication_sha256")


def _surface_config() -> SurfaceMaterializationConfig:
    return SurfaceMaterializationConfig(
        tile_size_pixels=14,
        minimum_valid_depth_fraction_per_tile=0.9,
        initial_maximum_rms_point_to_plane_m=0.015,
        initial_maximum_p95_point_to_plane_m=0.03,
        merge_maximum_normal_angle_degrees=10.0,
        merge_maximum_mutual_centroid_to_plane_m=0.03,
        final_inlier_point_to_plane_m=0.02,
        final_minimum_inlier_fraction=0.9,
        final_maximum_rms_point_to_plane_m=0.01,
        minimum_inlier_pixels=784,
        minimum_depth_m=0.05,
        maximum_depth_m=20.0,
    )


def _descriptor_config() -> DINORegionConfig:
    return DINORegionConfig(
        image_height=224, image_width=224, patch_size_pixels=14,
        patch_token_dimension=384, minimum_total_patch_weight=1.0,
        unit_norm_validation_tolerance=1e-5,
    )


def public_geometry_features(
    *, depth_m_float32: Any, camera_intrinsics_float64: Any,
    patch_tokens: Any, d218_contract: Mapping[str, Any],
) -> dict[str, float]:
    """Compute the frozen twelve public camera-frame geometry features."""

    contract = validate_d218_contract(d218_contract)
    depth = np.asarray(depth_m_float32)
    intrinsics = np.asarray(camera_intrinsics_float64)
    _require(depth.dtype == np.float32 and depth.shape == (224, 224),
             "feature depth schema changed")
    _require(intrinsics.dtype == np.float64 and intrinsics.shape == (4,) and
             np.isfinite(intrinsics).all(), "feature intrinsics schema changed")
    fx, fy, cx, cy = (float(item) for item in intrinsics)
    _require(fx > 0.0 and fy > 0.0, "feature focal lengths must be positive")
    geometry = contract["features"]["geometry"]
    minimum, maximum = geometry["valid_depth_range_m"]
    valid = np.isfinite(depth) & (depth >= minimum) & (depth <= maximum)
    _require(bool(valid.any()), "public depth has no valid values")
    values = depth[valid].astype(np.float64)
    q10, q50, q90 = np.quantile(values, [0.1, 0.5, 0.9], method="linear")
    pixel_factor = 1.0 / (3.0 * fx * fy)
    visibility_volume = float(np.sum(values ** 3, dtype=np.float64) * pixel_factor)
    clearance = float(geometry["free_space_surface_clearance_m"])
    free_axes = np.maximum(values - clearance, 0.0)
    free_volume = float(np.sum(free_axes ** 3, dtype=np.float64) * pixel_factor)
    volume_min, volume_max = geometry["volume_clip_m3"]

    def columns(left: float, right: float) -> slice:
        return slice(int(math.floor(left * depth.shape[1])),
                     int(math.ceil(right * depth.shape[1])))

    row_start = int(math.floor(
        geometry["horizontal_opening_rows_fraction"][0] * depth.shape[0]))
    row_stop = int(math.ceil(
        geometry["horizontal_opening_rows_fraction"][1] * depth.shape[0]))
    band_valid = valid[row_start:row_stop]
    valid_columns = np.flatnonzero(band_valid.any(axis=0))
    if len(valid_columns) < 2:
        opening = 0.0
    else:
        band_depth = depth[row_start:row_stop][band_valid]
        opening_depth = float(np.quantile(
            band_depth.astype(np.float64), 0.5, method="linear"))
        opening = ((float(valid_columns[-1] - valid_columns[0]) + 1.0) *
                   opening_depth / fx)

    def clearance_feature(column_slice: slice) -> float:
        region = depth[:, column_slice]
        region_valid = valid[:, column_slice]
        if not region_valid.any():
            return 0.0
        result = float(np.quantile(
            region[region_valid].astype(np.float64),
            geometry["clearance_quantile"], method="linear"))
        return float(np.clip(result, *geometry["clearance_clip_m"]))

    calibration = {"fx": fx, "fy": fy, "cx": cx, "cy": cy}
    pose = {"position_m": [0.0, 0.0, 0.0],
            "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0]}
    surfaces = materialize_public_surfaces(
        depth, calibration, pose, patch_tokens, _descriptor_config(),
        _surface_config())
    surface_count = float(np.clip(
        len(surfaces), *geometry["surface_count_clip"]))
    normals = [abs(float(item.plane_normal[1])) for item in surfaces
               if item.plane_normal is not None]
    mean_normal_y = float(np.mean(normals)) if normals else float(
        geometry["no_surface_mean_absolute_normal_y"])
    result = {
        "valid_depth_fraction": float(valid.mean()),
        "depth_q10_m": float(q10),
        "depth_q50_m": float(q50),
        "depth_q90_m": float(q90),
        "current_free_space_volume_m3_clipped_0_50": float(np.clip(
            free_volume, volume_min, volume_max)),
        "current_visibility_volume_m3_clipped_0_50": float(np.clip(
            visibility_volume, volume_min, volume_max)),
        "horizontal_opening_width_m_clipped_0_10": float(np.clip(
            opening, *geometry["clearance_clip_m"])),
        "forward_clearance_m_clipped_0_10": clearance_feature(columns(
            *geometry["forward_column_fraction"])),
        "left_clearance_m_clipped_0_10": clearance_feature(columns(
            *geometry["left_column_fraction"])),
        "right_clearance_m_clipped_0_10": clearance_feature(columns(
            *geometry["right_column_fraction"])),
        "surface_count_clipped_0_64": surface_count,
        "mean_absolute_surface_normal_y": mean_normal_y,
    }
    _require(tuple(result) == GEOMETRY_FEATURE_ORDER and
             all(math.isfinite(item) for item in result.values()),
             "public geometry feature order or value changed")
    return result


def materialize_estimator_feature(
    *, depth_m_float32: Any, camera_intrinsics_float64: Any,
    patch_tokens: Any, d218_contract: Mapping[str, Any],
) -> np.ndarray:
    """Concatenate a full-frame DINO descriptor and twelve public features."""

    validate_d218_contract(d218_contract)
    config = _descriptor_config()
    full_mask = np.ones((224, 224), dtype=np.bool_)
    descriptor = pool_dinov2_region_descriptor(
        patch_tokens, full_mask, config)
    geometry = public_geometry_features(
        depth_m_float32=depth_m_float32,
        camera_intrinsics_float64=camera_intrinsics_float64,
        patch_tokens=patch_tokens, d218_contract=d218_contract)
    feature = np.asarray([
        *descriptor.values,
        *(geometry[name] for name in GEOMETRY_FEATURE_ORDER),
    ], dtype=np.float32)
    _require(feature.shape == (396,) and np.isfinite(feature).all(),
             "D-218 estimator feature must be finite float32[396]")
    return feature


def make_feature_shard_receipt(
    *, features_float32: Any, observation_ids: Any,
    public_observation_digests: Any, source_public_receipt_sha256: str,
    d218_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Seal one public feature shard without house identity or labels."""

    contract = validate_d218_contract(d218_contract)
    features = np.asarray(features_float32)
    ids = np.asarray(observation_ids)
    digests = np.asarray(public_observation_digests)
    _require(features.dtype == np.float32 and features.ndim == 2 and
             features.shape[1] == 396 and features.shape[0] > 0 and
             np.isfinite(features).all(),
             "feature shard must contain finite float32[N,396]")
    count = features.shape[0]
    _require(ids.shape == (count,) and ids.dtype.kind in {"U", "S"} and
             digests.shape == (count,) and digests.dtype.kind in {"U", "S"},
             "feature shard ID vectors changed")
    logical_ids = [item.decode() if isinstance(item, bytes) else str(item)
                   for item in ids.tolist()]
    logical_digests = [item.decode() if isinstance(item, bytes) else str(item)
                       for item in digests.tolist()]
    _require(len(logical_ids) == len(set(logical_ids)) and
             all(HEX64.fullmatch(item) for item in logical_ids) and
             all(HEX64.fullmatch(item) for item in logical_digests),
             "feature shard IDs or public digests are invalid")
    _hex(source_public_receipt_sha256, 64, "source public receipt")
    return _seal({
        "schema_version": FEATURE_SHARD_SCHEMA,
        "row_count": count,
        "feature_dimension": 396,
        "feature_dtype": "float32",
        "feature_bytes_sha256": _array_sha(features),
        "observation_ids_sha256": _sha(logical_ids),
        "public_observation_digests_sha256": _sha(logical_digests),
        "source_public_receipt_sha256": source_public_receipt_sha256,
        "d215_inference_config_sha256":
            "4cd2bc00e8af7b4897d00d9ad90a69bdb389b1d1dd310705c1c44c5e6b720c70",
        "dinov2_repository_commit":
            contract["features"]["dinov2"]["repository_commit"],
        "dinov2_checkpoint_sha256":
            contract["features"]["dinov2"]["checkpoint_sha256"],
        "scenario_house_route_private_label_or_future_used": False,
    }, "feature_shard_receipt_sha256")
