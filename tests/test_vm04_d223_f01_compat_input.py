from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt.d223_f01_compat_input import (  # noqa: E402
    D223F01CompatError,
    build_observation_zero_compat_bundle,
    deterministic_f01_npz_bytes,
    select_first_d217_public_train_sample,
    validate_compat_receipt,
)
from vsmt.d223_f01_production_reader import (  # noqa: E402
    validate_f01_contract,
    validate_public_input_manifest,
)


CONTRACT_PATH = (
    ROOT / "configs/vsmt/vm04_d223_f01_production_reader_v1.json")
STAGE_PATH = ROOT / "ops/vsmt/vm04_d223_f01_production_reader.py"


def sha(value) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def seal(value: dict, field: str) -> dict:
    result = json.loads(canonical_json(value))
    result[field] = sha(result)
    return result


def source_arrays() -> dict[str, np.ndarray]:
    observation_ids = [hashlib.sha256(
        f"observation-{index}".encode("utf-8")).hexdigest()
        for index in range(32)]
    rgb = np.zeros((32, 224, 224, 3), dtype=np.uint8)
    rgb[0, ..., 1] = 37
    depth = np.full((32, 224, 224), 2.0, dtype=np.float32)
    intrinsics = np.tile(
        np.asarray([112.0, 112.0, 111.5, 111.5], dtype=np.float64),
        (32, 1))
    return {
        "rgb_uint8": rgb,
        "depth_m_float32": depth,
        "camera_intrinsics_float64": intrinsics,
        "observation_ids": np.asarray(observation_ids),
    }


def source_receipt(
    *, rank: int, npz_sha256: str = "b" * 64,
    arrays: dict[str, np.ndarray] | None = None,
) -> dict:
    values = arrays or source_arrays()
    return seal({
        "schema_version": "vsmt-vm04-d217-public-rgbd-house-v1",
        "split": "train",
        "sample_rank": rank,
        "public_house_ref": "d217-public-house-fixture",
        "observation_count": 32,
        "observation_ids_sha256": sha(
            [str(item) for item in values["observation_ids"].tolist()]),
        "rgbd_npz_sha256": npz_sha256,
        "contains_house_world_pose_grid_instance_scenario_teacher_or_future":
            False,
    }, "public_receipt_sha256")


def write_source_sample(public_root: Path, rank: int) -> Path:
    sample = public_root / "train" / f"sample_{rank:04d}"
    sample.mkdir(parents=True)
    arrays = source_arrays()
    npz_path = sample / "rgbd.npz"
    np.savez(npz_path, **arrays)
    digest = hashlib.sha256(npz_path.read_bytes()).hexdigest()
    (sample / "receipt.json").write_text(
        canonical_json(source_receipt(
            rank=rank, npz_sha256=digest, arrays=arrays)) + "\n",
        encoding="utf-8")
    return sample


class D223F01CompatInputTests(unittest.TestCase):
    def test_contract_freezes_d217_adapter_and_keeps_execution_closed(self):
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        value = validate_f01_contract(contract)
        adapter = value["compatibility_input_adapter"]
        self.assertEqual(adapter["source_split"], "train")
        self.assertEqual(adapter["selected_observation_index"], 0)
        self.assertEqual(
            adapter["selected_sample_incomplete_or_malformed_policy"],
            "fail_do_not_skip")
        self.assertTrue(adapter["diagnostic_compatibility_only"])
        self.assertFalse(
            adapter["eligible_for_formal_data_p04_p08_or_paper_results"])
        self.assertFalse(adapter["private_root_or_sidecar_read_allowed"])
        if value["status"] == "implementation_pending_review_all_execution_closed":
            self.assertFalse(any(value["authorization"].values()))

    def test_selector_uses_lowest_existing_public_train_rank(self):
        with tempfile.TemporaryDirectory() as temporary:
            public_root = Path(temporary) / "public"
            write_source_sample(public_root, 9)
            selected_expected = write_source_sample(public_root, 3)
            (public_root / "calibration" / "sample_0000").mkdir(parents=True)
            (Path(temporary) / "private" / "train").mkdir(parents=True)
            selected, receipt, arrays = (
                select_first_d217_public_train_sample(public_root))
            self.assertEqual(selected, selected_expected)
            self.assertEqual(receipt["sample_rank"], 3)
            self.assertEqual(arrays["rgb_uint8"].shape, (32, 224, 224, 3))

    def test_selector_does_not_skip_a_malformed_earlier_sample(self):
        with tempfile.TemporaryDirectory() as temporary:
            public_root = Path(temporary) / "public"
            malformed = public_root / "train" / "sample_0002"
            malformed.mkdir(parents=True)
            (malformed / "receipt.json").write_text("{}", encoding="utf-8")
            write_source_sample(public_root, 7)
            with self.assertRaisesRegex(
                    D223F01CompatError, "incomplete or has extra files"):
                select_first_d217_public_train_sample(public_root)

    def test_source_validation_rejects_private_flag_and_array_drift(self):
        arrays = source_arrays()
        receipt = source_receipt(rank=3, arrays=arrays)
        receipt[
            "contains_house_world_pose_grid_instance_scenario_teacher_or_future"
        ] = True
        receipt = seal({key: value for key, value in receipt.items()
                        if key != "public_receipt_sha256"},
                       "public_receipt_sha256")
        with self.assertRaisesRegex(D223F01CompatError, "identity changed"):
            build_observation_zero_compat_bundle(
                source_receipt=receipt, source_arrays=arrays,
                frontend_config_sha256="c" * 64,
                execution_commit="d" * 40)

        arrays = source_arrays()
        receipt = source_receipt(rank=3, arrays=arrays)
        arrays["extra"] = np.asarray([1])
        with self.assertRaisesRegex(D223F01CompatError, "NPZ fields"):
            build_observation_zero_compat_bundle(
                source_receipt=receipt, source_arrays=arrays,
                frontend_config_sha256="c" * 64,
                execution_commit="d" * 40)

    def test_bundle_is_deterministic_single_frame_origin_pose(self):
        arrays = source_arrays()
        receipt = source_receipt(rank=3, arrays=arrays)
        first = build_observation_zero_compat_bundle(
            source_receipt=receipt, source_arrays=arrays,
            frontend_config_sha256="c" * 64, execution_commit="d" * 40)
        second = build_observation_zero_compat_bundle(
            source_receipt=receipt, source_arrays=arrays,
            frontend_config_sha256="c" * 64, execution_commit="d" * 40)
        self.assertEqual(first, second)
        npz_bytes, manifest, compat_receipt = first
        validate_public_input_manifest(manifest)
        validate_compat_receipt(compat_receipt)
        self.assertEqual(manifest["frame_count"], 1)
        row = manifest["rows"][0]
        self.assertEqual(
            row["causal_episode_relative_camera_pose"]["position_m"],
            [0.0, 0.0, 0.0])
        self.assertEqual(
            row["continuous_pose_belief"]["mean_x_y_z_yaw"],
            [0.0, 0.0, 0.0, 0.0])
        self.assertEqual(
            row["continuous_pose_belief"]["covariance_diagonal"],
            [0.0, 0.0, 0.0, 0.0])
        self.assertIsNone(row["incoming_transition_action_summary"])
        with np.load(io.BytesIO(npz_bytes), allow_pickle=False) as output:
            self.assertEqual(set(output.files), {
                "rgb_uint8", "depth_m_float32"})
            np.testing.assert_array_equal(
                output["rgb_uint8"], arrays["rgb_uint8"][:1])
            np.testing.assert_array_equal(
                output["depth_m_float32"], arrays["depth_m_float32"][:1])

    def test_method_input_is_anonymous_and_receipt_marks_diagnostic_only(self):
        arrays = source_arrays()
        receipt = source_receipt(rank=3, arrays=arrays)
        _npz, manifest, compat_receipt = build_observation_zero_compat_bundle(
            source_receipt=receipt, source_arrays=arrays,
            frontend_config_sha256="c" * 64, execution_commit="d" * 40)
        encoded_manifest = canonical_json(manifest)
        self.assertNotIn("public_house_ref", encoded_manifest)
        self.assertNotIn(receipt["public_house_ref"], encoded_manifest)
        self.assertNotIn(str(arrays["observation_ids"][0]), encoded_manifest)
        self.assertEqual(compat_receipt["selected_sample_rank"], 3)
        self.assertTrue(compat_receipt["compatibility_only"])
        self.assertFalse(
            compat_receipt["formal_data_p04_p08_or_paper_eligible"])
        self.assertFalse(compat_receipt["private_input_read"])
        self.assertFalse(compat_receipt["calibration_or_audit_input_read"])

    def test_deterministic_npz_has_stable_bytes(self):
        arrays = source_arrays()
        first = deterministic_f01_npz_bytes(
            rgb_uint8=arrays["rgb_uint8"][:1],
            depth_m_float32=arrays["depth_m_float32"][:1])
        second = deterministic_f01_npz_bytes(
            rgb_uint8=arrays["rgb_uint8"][:1],
            depth_m_float32=arrays["depth_m_float32"][:1])
        self.assertEqual(first, second)
        self.assertEqual(hashlib.sha256(first).hexdigest(),
                         hashlib.sha256(second).hexdigest())

    def test_closed_stage_rejects_adapter_before_external_paths(self):
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        if contract["status"] != (
                "implementation_pending_review_all_execution_closed"):
            self.skipTest("checked-in F-01 contract is active")
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "must-not-exist"
            receipt = Path(temporary) / "must-not-exist.json"
            result = subprocess.run([
                sys.executable, str(STAGE_PATH), "prepare-d217-compat",
                "--d217-public-root", str(Path(temporary) / "missing-public"),
                "--output-root", str(output),
                "--receipt-path", str(receipt),
            ], cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("closed pending review", result.stderr)
            self.assertFalse(output.exists())
            self.assertFalse(receipt.exists())


if __name__ == "__main__":
    unittest.main()
