"""D-223/F-01 adapter for one diagnostic D-217 public RGB-D frame.

The adapter reads only ``public/train``.  It chooses the lowest-rank public
sample directory, fails if that selected sample is incomplete or malformed,
and turns observation zero into the exact F-01 public bundle schema.  The
result is diagnostic compatibility input, not formal experiment data.
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
import re
from typing import Any, Mapping
import zipfile

import numpy as np

from cpmt.hashing import canonical_json, clone_json
from .d210_place_memory import build_continuous_pose_belief
from .d223_f01_production_reader import (
    INPUT_SCHEMA,
    public_array_sha256,
    validate_public_input_manifest,
)


D217_PUBLIC_SCHEMA = "vsmt-vm04-d217-public-rgbd-house-v1"
COMPAT_RECEIPT_SCHEMA = "vsmt-vm04-d223-f01-d217-compat-receipt-v1"
SAMPLE_DIRECTORY = re.compile(r"^sample_([0-9]{4})$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
OBSERVATION_COUNT = 32
IMAGE_SHAPE = (224, 224)
POSE_SOURCE_ID = "d223.f01.d217_public_observation_zero_origin.v1"


class D223F01CompatError(ValueError):
    """A D-217 public input violated the frozen F-01 compatibility boundary."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise D223F01CompatError(message)


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _payload_sha(value: Mapping[str, Any], field: str) -> str:
    payload = clone_json(dict(value))
    payload.pop(field, None)
    return _sha(payload)


def _seal(value: Mapping[str, Any], field: str) -> dict[str, Any]:
    result = clone_json(dict(value))
    result[field] = _sha(result)
    return result


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate D-217 public JSON key: {key}")
        result[key] = value
    return result


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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
             value["observation_count"] == OBSERVATION_COUNT and
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
             rgb.shape == (OBSERVATION_COUNT, *IMAGE_SHAPE, 3),
             "selected D-217 RGB dtype or shape changed")
    _require(depth.dtype == np.float32 and
             depth.shape == (OBSERVATION_COUNT, *IMAGE_SHAPE),
             "selected D-217 depth dtype or shape changed")
    _require(intrinsics.dtype == np.float64 and
             intrinsics.shape == (OBSERVATION_COUNT, 4) and
             bool(np.all(np.isfinite(intrinsics))) and
             bool(np.all(intrinsics[:, :2] > 0.0)),
             "selected D-217 camera intrinsics changed")
    _require(observation_ids.shape == (OBSERVATION_COUNT,) and
             observation_ids.dtype.kind == "U",
             "selected D-217 observation IDs changed")
    ids = [str(item) for item in observation_ids.tolist()]
    _require(all(HEX64.fullmatch(item) is not None for item in ids) and
             len(set(ids)) == OBSERVATION_COUNT and
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
        match = SAMPLE_DIRECTORY.fullmatch(child.name)
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
    import json
    try:
        receipt = json.loads(
            receipt_path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicates)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise D223F01CompatError(
            "selected D-217 public receipt is unreadable") from error
    validated_receipt = validate_d217_public_receipt(
        receipt, expected_rank=rank, rgbd_npz_sha256=file_sha256(npz_path))
    try:
        with np.load(npz_path, allow_pickle=False) as source:
            _require(set(source.files) == {
                "rgb_uint8", "depth_m_float32", "camera_intrinsics_float64",
                "observation_ids",
            }, "selected D-217 public NPZ fields changed")
            arrays = {name: source[name] for name in source.files}
    except D223F01CompatError:
        raise
    except (OSError, ValueError, KeyError) as error:
        raise D223F01CompatError(
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


def build_observation_zero_compat_bundle(
    *, source_receipt: Mapping[str, Any], source_arrays: Mapping[str, Any],
    frontend_config_sha256: str, execution_commit: str,
) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    """Build one anonymous origin-pose frame plus a separate diagnostic receipt."""

    raw_receipt = clone_json(dict(source_receipt))
    _require(type(raw_receipt.get("sample_rank")) is int and
             type(raw_receipt.get("rgbd_npz_sha256")) is str,
             "selected D-217 public receipt identity changed")
    receipt = validate_d217_public_receipt(
        raw_receipt, expected_rank=raw_receipt["sample_rank"],
        rgbd_npz_sha256=raw_receipt["rgbd_npz_sha256"])
    _require(type(frontend_config_sha256) is str and
             HEX64.fullmatch(frontend_config_sha256) is not None,
             "F-01 frontend config digest is invalid")
    _require(type(execution_commit) is str and
             HEX40.fullmatch(execution_commit) is not None,
             "F-01 compatibility execution commit is invalid")
    arrays = validate_d217_public_arrays(source_arrays, receipt)
    rgb = np.ascontiguousarray(arrays["rgb_uint8"][:1])
    depth = np.ascontiguousarray(arrays["depth_m_float32"][:1])
    intrinsics = arrays["camera_intrinsics_float64"][0]
    observation_id = str(arrays["observation_ids"][0])
    npz_bytes = deterministic_f01_npz_bytes(
        rgb_uint8=rgb, depth_m_float32=depth)
    arrays_digest = hashlib.sha256(npz_bytes).hexdigest()
    episode_public_id = "d223-f01-compat-" + _sha({
        "domain": "d223-f01-d217-public-observation-zero",
        "source_public_receipt_sha256": receipt["public_receipt_sha256"],
        "source_observation_id_sha256": hashlib.sha256(
            observation_id.encode("utf-8")).hexdigest(),
        "frontend_config_sha256": frontend_config_sha256,
    })[:24]
    pose_belief = build_continuous_pose_belief(
        observation_index=0, mean_x_y_z_yaw=[0.0, 0.0, 0.0, 0.0],
        covariance_diagonal=[0.0, 0.0, 0.0, 0.0],
        source_id=POSE_SOURCE_ID)
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
                "source_id": POSE_SOURCE_ID,
            },
            "continuous_pose_belief": pose_belief,
            "incoming_transition_action_summary": None,
        }],
        "restricted_information_used": False,
    }, "manifest_sha256"))
    selection_policy = {
        "source_split": "train",
        "selection": "ascending_sample_rank_first_present_public_sample",
        "selected_sample_incomplete_or_malformed": "fail_do_not_skip",
        "selected_observation_index": 0,
    }
    compat_receipt = validate_compat_receipt(_seal({
        "schema_version": COMPAT_RECEIPT_SCHEMA,
        "stage_id": "F-01",
        "execution_commit": execution_commit,
        "compatibility_only": True,
        "formal_data_p04_p08_or_paper_eligible": False,
        "source_schema": D217_PUBLIC_SCHEMA,
        "source_split": "train",
        "selected_sample_rank": receipt["sample_rank"],
        "selected_observation_index": 0,
        "source_public_receipt_sha256": receipt["public_receipt_sha256"],
        "source_rgbd_npz_sha256": receipt["rgbd_npz_sha256"],
        "source_observation_id_sha256": hashlib.sha256(
            observation_id.encode("utf-8")).hexdigest(),
        "selection_policy_sha256": _sha(selection_policy),
        "output_episode_public_id": episode_public_id,
        "output_arrays_npz_sha256": arrays_digest,
        "output_manifest_sha256": manifest["manifest_sha256"],
        "private_input_read": False,
        "calibration_or_audit_input_read": False,
        "route_or_raw_generated": False,
        "p04_p08_run": False,
    }, "compat_receipt_sha256"))
    return npz_bytes, manifest, compat_receipt


def validate_compat_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    value = clone_json(dict(receipt))
    _require(set(value) == {
        "schema_version", "stage_id", "compatibility_only",
        "execution_commit",
        "formal_data_p04_p08_or_paper_eligible", "source_schema",
        "source_split", "selected_sample_rank", "selected_observation_index",
        "source_public_receipt_sha256", "source_rgbd_npz_sha256",
        "source_observation_id_sha256", "selection_policy_sha256",
        "output_episode_public_id", "output_arrays_npz_sha256",
        "output_manifest_sha256", "private_input_read",
        "calibration_or_audit_input_read", "route_or_raw_generated",
        "p04_p08_run", "compat_receipt_sha256",
    }, "F-01 compatibility receipt fields changed")
    _require(value["schema_version"] == COMPAT_RECEIPT_SCHEMA and
             value["stage_id"] == "F-01" and
             type(value["execution_commit"]) is str and
             HEX40.fullmatch(value["execution_commit"]) is not None and
             value["compatibility_only"] is True and
             value["formal_data_p04_p08_or_paper_eligible"] is False and
             value["source_schema"] == D217_PUBLIC_SCHEMA and
             value["source_split"] == "train" and
             type(value["selected_sample_rank"]) is int and
             value["selected_sample_rank"] >= 0 and
             value["selected_observation_index"] == 0 and
             type(value["output_episode_public_id"]) is str and
             value["output_episode_public_id"].startswith("d223-f01-compat-") and
             value["private_input_read"] is False and
             value["calibration_or_audit_input_read"] is False and
             value["route_or_raw_generated"] is False and
             value["p04_p08_run"] is False,
             "F-01 compatibility receipt boundary changed")
    for field in (
        "source_public_receipt_sha256", "source_rgbd_npz_sha256",
        "source_observation_id_sha256", "selection_policy_sha256",
        "output_arrays_npz_sha256", "output_manifest_sha256",
        "compat_receipt_sha256",
    ):
        _require(type(value[field]) is str and
                 HEX64.fullmatch(value[field]) is not None,
                 f"F-01 compatibility receipt {field} is invalid")
    _require(value["compat_receipt_sha256"] ==
             _payload_sha(value, "compat_receipt_sha256"),
             "F-01 compatibility receipt self digest changed")
    return value
