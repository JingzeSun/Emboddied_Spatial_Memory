from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
OPS = ROOT / "ops/vsmt"
for item in (SRC, OPS):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt.d218_estimator_frontend import (  # noqa: E402
    D218Error,
    adjudicate_annotations,
    make_annotation_package,
    make_annotation_submission,
    make_feature_shard_receipt,
    materialize_estimator_feature,
    public_geometry_features,
    public_observation_sha256,
    validate_annotation_package,
    validate_d218_contract,
)
import vm04_d218_estimator_annotation_stage as annotation_stage  # noqa: E402
import vm04_d218_estimator_feature_stage as feature_stage  # noqa: E402


CONTRACT_PATH = ROOT / "configs/vsmt/vm04_d218_estimator_annotation_features_v1.json"


def digest(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def media_records(count=3):
    return [{
        "observation_id": digest({"observation": index}),
        "public_observation_sha256": digest({"public": index}),
        "rgb_media_path": f"../../media/{index}.rgb.png",
        "rgb_media_sha256": digest({"rgb": index}),
        "depth_media_path": f"../../media/{index}.depth.png",
        "depth_media_sha256": digest({"depth": index}),
    } for index in range(count)]


class D218EstimatorFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = validate_d218_contract(json.loads(
            CONTRACT_PATH.read_text(encoding="utf-8")))

    def test_review_candidate_keeps_annotation_features_and_downstream_closed(self):
        self.assertEqual(
            "implementation_pending_review_all_execution_closed",
            self.contract["status"])
        self.assertFalse(any(self.contract["authorization"].values()))
        self.assertFalse(any(self.contract["closed_downstream"].values()))
        changed = deepcopy(self.contract)
        changed["authorization"]["p04_p08_qualification"] = True
        with self.assertRaises(D218Error):
            validate_d218_contract(changed)
        changed = deepcopy(self.contract)
        changed["features"]["forbidden_inputs"].remove("house_id")
        with self.assertRaises(D218Error):
            validate_d218_contract(changed)

    def test_blind_packages_have_role_specific_order_and_no_identity_fields(self):
        records = media_records(8)
        package_a = make_annotation_package(
            records, package_role="annotator_a", d218_contract=self.contract)
        package_b = make_annotation_package(
            records, package_role="annotator_b", d218_contract=self.contract)
        validate_annotation_package(package_a, d218_contract=self.contract)
        self.assertEqual(
            {row["observation_id"] for row in package_a["tasks"]},
            {row["observation_id"] for row in package_b["tasks"]})
        self.assertNotEqual(
            [row["observation_id"] for row in package_a["tasks"]],
            [row["observation_id"] for row in package_b["tasks"]])
        encoded = canonical_json(package_a["tasks"])
        for forbidden in ("house_id", "sample_rank", "scenario_id",
                          "world_pose", "structural_label", "teacher", "future"):
            self.assertNotIn(forbidden, encoded)

    def test_two_distinct_annotators_and_unresolved_disagreement_becomes_unknown(self):
        records = media_records(4)
        package_a = make_annotation_package(
            records, package_role="annotator_a", d218_contract=self.contract)
        package_b = make_annotation_package(
            records, package_role="annotator_b", d218_contract=self.contract)
        labels_a = {row["task_id"]: "room" for row in package_a["tasks"]}
        labels_b = {row["task_id"]: "room" for row in package_b["tasks"]}
        disputed = package_b["tasks"][0]
        labels_b[disputed["task_id"]] = "corridor"
        submission_a = make_annotation_submission(
            package=package_a, annotator_id="annotator-alpha",
            labels_by_task_id=labels_a, d218_contract=self.contract)
        submission_b = make_annotation_submission(
            package=package_b, annotator_id="annotator-beta",
            labels_by_task_id=labels_b, d218_contract=self.contract)
        merged = adjudicate_annotations(
            package_a=package_a, package_b=package_b,
            submission_a=submission_a, submission_b=submission_b,
            adjudicator_id=None, adjudicated_labels_by_observation_id=None,
            d218_contract=self.contract)
        row = next(item for item in merged["rows"]
                   if item["observation_id"] == disputed["observation_id"])
        self.assertEqual("unknown", row["adjudicated_label"])
        self.assertTrue(row["unresolved_disagreement"])
        with self.assertRaisesRegex(D218Error, "different annotators"):
            same_person = make_annotation_submission(
                package=package_b, annotator_id="annotator-alpha",
                labels_by_task_id=labels_b, d218_contract=self.contract)
            adjudicate_annotations(
                package_a=package_a, package_b=package_b,
                submission_a=submission_a, submission_b=same_person,
                adjudicator_id=None, adjudicated_labels_by_observation_id=None,
                d218_contract=self.contract)

    def test_independent_adjudicator_can_resolve_only_actual_disagreements(self):
        records = media_records(2)
        package_a = make_annotation_package(
            records, package_role="annotator_a", d218_contract=self.contract)
        package_b = make_annotation_package(
            records, package_role="annotator_b", d218_contract=self.contract)
        labels_a = {row["task_id"]: "room" for row in package_a["tasks"]}
        labels_b = {row["task_id"]: "corridor" for row in package_b["tasks"]}
        a = make_annotation_submission(
            package=package_a, annotator_id="person-a",
            labels_by_task_id=labels_a, d218_contract=self.contract)
        b = make_annotation_submission(
            package=package_b, annotator_id="person-b",
            labels_by_task_id=labels_b, d218_contract=self.contract)
        resolution = {row["observation_id"]: "corridor"
                      for row in package_a["tasks"]}
        merged = adjudicate_annotations(
            package_a=package_a, package_b=package_b,
            submission_a=a, submission_b=b, adjudicator_id="person-c",
            adjudicated_labels_by_observation_id=resolution,
            d218_contract=self.contract)
        self.assertEqual(0, merged["unresolved_disagreement_count"])
        self.assertTrue(all(row["adjudicated_label"] == "corridor"
                            for row in merged["rows"]))

    def test_public_observation_digest_and_feature_are_deterministic(self):
        rgb = np.zeros((224, 224, 3), dtype=np.uint8)
        depth = np.full((224, 224), 2.0, dtype=np.float32)
        intrinsics = np.asarray([112.0, 112.0, 111.5, 111.5], dtype=np.float64)
        observation_id = "a" * 64
        first_digest = public_observation_sha256(
            observation_id=observation_id, rgb_uint8=rgb,
            depth_m_float32=depth, camera_intrinsics_float64=intrinsics)
        rgb[0, 0, 0] = 1
        second_digest = public_observation_sha256(
            observation_id=observation_id, rgb_uint8=rgb,
            depth_m_float32=depth, camera_intrinsics_float64=intrinsics)
        self.assertNotEqual(first_digest, second_digest)
        tokens = np.ones((16, 16, 384), dtype=np.float32)
        geometry = public_geometry_features(
            depth_m_float32=depth, camera_intrinsics_float64=intrinsics,
            patch_tokens=tokens, d218_contract=self.contract)
        self.assertEqual(12, len(geometry))
        self.assertEqual(1.0, geometry["valid_depth_fraction"])
        self.assertLess(
            geometry["current_free_space_volume_m3_clipped_0_50"],
            geometry["current_visibility_volume_m3_clipped_0_50"])
        feature = materialize_estimator_feature(
            depth_m_float32=depth, camera_intrinsics_float64=intrinsics,
            patch_tokens=tokens, d218_contract=self.contract)
        self.assertEqual(np.float32, feature.dtype)
        self.assertEqual((396,), feature.shape)
        self.assertAlmostEqual(1.0, float(np.linalg.norm(feature[:384])), places=5)

    def test_feature_receipt_contains_no_house_label_or_route(self):
        features = np.zeros((2, 396), dtype=np.float32)
        ids = np.asarray(["a" * 64, "b" * 64])
        public = np.asarray(["c" * 64, "d" * 64])
        receipt = make_feature_shard_receipt(
            features_float32=features, observation_ids=ids,
            public_observation_digests=public,
            source_public_receipt_sha256="e" * 64,
            d218_contract=self.contract)
        encoded = canonical_json(receipt)
        for forbidden in ("house_id", "semantic_label", "structural_label",
                          "route_index", "scenario_id"):
            self.assertNotIn(forbidden, encoded)

    def test_annotation_export_creates_offline_ui_from_public_npz_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            public = root / "public/train/sample_0000"
            public.mkdir(parents=True)
            rgb = np.zeros((32, 224, 224, 3), dtype=np.uint8)
            depth = np.full((32, 224, 224), 2.0, dtype=np.float32)
            intrinsics = np.tile(
                np.asarray([112.0, 112.0, 111.5, 111.5], dtype=np.float64),
                (32, 1))
            ids = np.asarray([digest({"frame": index}) for index in range(32)])
            npz = public / "rgbd.npz"
            np.savez_compressed(
                npz, rgb_uint8=rgb, depth_m_float32=depth,
                camera_intrinsics_float64=intrinsics, observation_ids=ids)
            receipt = {
                "schema_version": "vsmt-vm04-d217-public-rgbd-house-v1",
                "split": "train", "sample_rank": 0,
                "public_house_ref": "f" * 64, "observation_count": 32,
                "observation_ids_sha256": digest(ids.tolist()),
                "rgbd_npz_sha256": annotation_stage._sha256(npz),
                "contains_house_world_pose_grid_instance_scenario_teacher_or_future":
                    False,
            }
            receipt["public_receipt_sha256"] = digest(receipt)
            (public / "receipt.json").write_text(
                canonical_json(receipt) + "\n", encoding="utf-8")
            output = root / "annotation"
            with patch.object(annotation_stage, "_execution_checkout",
                              return_value="1" * 40):
                result = annotation_stage.export_packages(
                    public_root=root / "public", output_root=output)
                replay = annotation_stage.export_packages(
                    public_root=root / "public", output_root=output)
            self.assertEqual(result, replay)
            self.assertEqual(32, result["observation_count"])
            self.assertTrue((output / "packages/annotator_a/index.html").is_file())
            manifest = json.loads((output /
                "packages/annotator_a/manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(32, manifest["task_count"])
            self.assertNotIn("train", canonical_json(manifest))
            self.assertEqual(64, len(list((output / "media").glob("*.png"))))

    def test_feature_terminal_is_rehashed_before_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "train/sample_0000"
            target.mkdir(parents=True)
            arrays = {
                "features_float32": np.zeros((2, 396), dtype=np.float32),
                "observation_ids": np.asarray(["a" * 64, "b" * 64]),
                "public_observation_sha256":
                    np.asarray(["c" * 64, "d" * 64]),
            }
            shard = target / "features.npz"
            np.savez_compressed(shard, **arrays)
            receipt = make_feature_shard_receipt(
                features_float32=arrays["features_float32"],
                observation_ids=arrays["observation_ids"],
                public_observation_digests=
                    arrays["public_observation_sha256"],
                source_public_receipt_sha256="e" * 64,
                d218_contract=self.contract)
            receipt["feature_npz_sha256"] = feature_stage._sha256(shard)
            receipt["stage_receipt_sha256"] = digest(receipt)
            (target / "receipt.json").write_text(
                canonical_json(receipt) + "\n", encoding="utf-8")
            job = {"split": "train", "sample_name": "sample_0000",
                   "public_receipt_sha256": "e" * 64}
            reused = feature_stage._existing_result(
                root, job, self.contract)
            self.assertTrue(reused["success"])
            self.assertTrue(reused["reused"])
            with shard.open("ab") as handle:
                handle.write(b"tamper")
            with self.assertRaisesRegex(RuntimeError, "bytes changed"):
                feature_stage._existing_result(root, job, self.contract)

    def test_closed_stages_reject_before_missing_external_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing"
            with self.assertRaisesRegex(
                    RuntimeError, "closed pending implementation review"):
                annotation_stage.export_packages(
                    public_root=missing, output_root=missing / "output")
            with self.assertRaisesRegex(
                    RuntimeError, "closed pending implementation review"):
                feature_stage.materialize(
                    public_root=missing, output_root=missing / "features",
                    dino_repository=missing / "dino",
                    dino_checkpoint=missing / "checkpoint",
                    requested_io_workers=4)


if __name__ == "__main__":
    unittest.main()
