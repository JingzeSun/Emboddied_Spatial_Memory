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
from vsmt.d215_frontend_freeze import validate_d215_contract  # noqa: E402
from vsmt.d216_estimator_training import (  # noqa: E402
    D216Error,
    NPZ_ARRAY_NAMES,
    fit_and_seal_estimator,
    make_house_split_manifest,
    make_reserved_house_manifest,
    make_training_evidence_index,
    make_training_bundle_manifest,
    validate_d216_contract,
    validate_house_split_manifest,
    validate_training_shard_arrays,
)
import vm04_d216_estimator_stage as stage  # noqa: E402


D215_PATH = ROOT / "configs/vsmt/vm04_d215_frontend_freeze_v1.json"
D216_PATH = ROOT / "configs/vsmt/vm04_d216_estimator_training_seal_v1.json"


def digest(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def arrays_for(split: str, house: str, offset: float = 0.0):
    count = 9
    features = np.zeros((count, 396), dtype=np.float32)
    labels = np.asarray([0, 1, 2] * 3, dtype=np.uint8)
    for index, label in enumerate(labels):
        features[index, label] = 2.0 + offset
        features[index, 3 + label] = float(index) / 10.0
    marker = np.asarray([hashlib.sha256(
        f"{split}-{index}".encode()).hexdigest() for index in range(count)])
    return {
        "features": features,
        "semantic_labels": labels.copy(),
        "structural_labels": labels.copy(),
        "house_ids": np.asarray([house] * count),
        "observation_ids": np.asarray(
            [f"{split}-observation-{index}" for index in range(count)]),
        "public_observation_sha256": marker.copy(),
        "semantic_annotation_receipt_sha256": marker.copy(),
        "structural_label_receipt_sha256": marker.copy(),
    }


def attach_evidence(split_arrays, d215):
    rows = []
    for arrays in split_arrays.values():
        for index, observation_id in enumerate(arrays["observation_ids"]):
            semantic = ("room", "corridor", "unknown")[
                int(arrays["semantic_labels"][index])]
            structural = ("basin", "bottleneck", "unknown")[
                int(arrays["structural_labels"][index])]
            rows.append({
                "observation_id": str(observation_id),
                "public_observation_sha256":
                    str(arrays["public_observation_sha256"][index]),
                "annotator_a_label": semantic,
                "annotator_b_label": semantic,
                "adjudicated_label": semantic,
                "unresolved_disagreement": False,
                "structural_label": structural,
            })
    evidence = make_training_evidence_index(rows, d215_contract=d215)
    by_id = {row["observation_id"]: row for row in evidence["rows"]}
    for arrays in split_arrays.values():
        arrays["semantic_annotation_receipt_sha256"] = np.asarray([
            by_id[str(observation_id)]["semantic"]
            ["semantic_annotation_receipt_sha256"]
            for observation_id in arrays["observation_ids"]])
        arrays["structural_label_receipt_sha256"] = np.asarray([
            by_id[str(observation_id)]["structural"]
            ["structural_label_receipt_sha256"]
            for observation_id in arrays["observation_ids"]])
    return evidence


class D216EstimatorTrainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d215 = validate_d215_contract(json.loads(
            D215_PATH.read_text(encoding="utf-8")))
        cls.d216 = validate_d216_contract(json.loads(
            D216_PATH.read_text(encoding="utf-8")))
        ids = [f"train:{index:06d}" for index in range(10000)]
        cls.inventory = {
            "source_manifest_sha256": cls.d216["d215_binding"]
            ["source_manifest_sha256"],
            "eligible_house_ids_sha256": digest(ids),
            "eligible_house_ids": ids,
            "inventory_sha256": "a" * 64,
        }
        cls.reserved = make_reserved_house_manifest([
            {"house_id": "train:004270",
             "roles": ["P0_route_and_raw_development"]},
            {"house_id": "train:008243",
             "roles": ["P0_route_and_raw_development"]},
            {"house_id": "train:000001", "roles": ["VM04_validation"]},
            {"house_id": "train:000002", "roles": ["VM04_confirmation"]},
        ])
        with patch("vsmt.d216_estimator_training.validate_source_inventory",
                   return_value=cls.inventory):
            cls.partition = make_house_split_manifest(
                source_inventory=cls.inventory,
                reserved_house_manifest=cls.reserved,
                d215_contract=cls.d215, d216_contract=cls.d216)
        cls.house_by_split = {
            split: next(row["house_id"] for row in cls.partition["rows"]
                        if row["split"] == split) for split in
            ("train", "calibration", "audit")
        }

    def test_review_candidate_closes_every_execution_and_reader_gate(self):
        self.assertFalse(any(self.d216["authorization"].values()))
        self.assertIsNone(self.d216["expected_reviewed_implementation_commit"])
        self.assertFalse(self.d216["reader_boundary"]
                         ["production_reader_implemented_in_this_decision"])
        changed = deepcopy(self.d216)
        changed["authorization"]["production_reader"] = True
        with self.assertRaisesRegex(D216Error, "execution closed"):
            validate_d216_contract(changed)

    def test_reserved_manifest_requires_all_roles_and_both_p0_houses(self):
        reserved = make_reserved_house_manifest([
            {"house_id": "train:004270",
             "roles": ["P0_route_and_raw_development"]},
            {"house_id": "train:008243",
             "roles": ["P0_route_and_raw_development"]},
            {"house_id": "train:000001", "roles": ["VM04_validation"]},
            {"house_id": "train:000002", "roles": ["VM04_confirmation"]},
        ])
        self.assertEqual(4, reserved["house_count"])
        with self.assertRaisesRegex(D216Error, "all three"):
            make_reserved_house_manifest([
                {"house_id": "train:004270",
                 "roles": ["P0_route_and_raw_development"]},
                {"house_id": "train:008243",
                 "roles": ["P0_route_and_raw_development"]},
            ])

    def test_full_house_manifest_uses_frozen_universe_and_never_reads_frames(self):
        manifest = self.partition
        self.assertEqual(10000, manifest["house_count"])
        self.assertFalse(manifest["frames_labels_routes_or_yield_read"])
        by_id = {row["house_id"]: row for row in manifest["rows"]}
        self.assertEqual("excluded", by_id["train:004270"]["split"])
        self.assertEqual("excluded", by_id["train:000001"]["split"])
        self.assertEqual(10000, sum(manifest["split_counts"].values()))

    def test_exact_training_schema_rejects_scenario_and_cross_split_house(self):
        partition = self.partition
        arrays = arrays_for("train", self.house_by_split["train"])
        summary = validate_training_shard_arrays(
            arrays, split="train", partition_manifest=partition)
        self.assertEqual(9, summary["row_count"])
        changed = dict(arrays)
        changed["scenario_id"] = np.asarray(["P08"] * 9)
        with self.assertRaisesRegex(D216Error, "exact schema"):
            validate_training_shard_arrays(
                changed, split="train", partition_manifest=partition)
        wrong = dict(arrays)
        wrong["house_ids"] = np.asarray(
            [self.house_by_split["calibration"]] * 9)
        with self.assertRaisesRegex(D216Error, "declared split"):
            validate_training_shard_arrays(
                wrong, split="train", partition_manifest=partition)

    def test_fit_seals_deterministic_weights_without_raw_training_values(self):
        partition = self.partition
        split_arrays = {
            "train": arrays_for("train", self.house_by_split["train"]),
            "calibration": arrays_for(
                "calibration", self.house_by_split["calibration"], offset=0.1),
            "audit": arrays_for(
                "audit", self.house_by_split["audit"], offset=0.2),
        }
        evidence = attach_evidence(split_arrays, self.d215)
        shards = [{
            "relative_path": f"{split}.npz", "file_sha256": str(index) * 64,
            "split": split, "arrays": split_arrays[split],
        } for index, split in enumerate(("train", "calibration", "audit"), 1)]
        bundle = make_training_bundle_manifest(
            shards=shards, partition_manifest=partition,
            training_evidence_index=evidence, d215_contract=self.d215,
            d216_contract=self.d216)
        first = fit_and_seal_estimator(
            split_arrays=split_arrays, partition_manifest=partition,
            training_bundle_manifest=bundle, d215_contract=self.d215,
            d216_contract=self.d216, implementation_commit="a" * 40,
            device="cpu")
        second = fit_and_seal_estimator(
            split_arrays=split_arrays, partition_manifest=partition,
            training_bundle_manifest=bundle, d215_contract=self.d215,
            d216_contract=self.d216, implementation_commit="a" * 40,
            device="cpu")
        self.assertEqual(first, second)
        self.assertGreater(first["weights"]["semantic_temperature"], 0.0)
        self.assertFalse(first["training_receipt"]
                         ["audit_used_for_checkpoint_or_temperature"])
        encoded = canonical_json(first["weights"])
        self.assertNotIn("house_id", encoded)
        self.assertNotIn("observation_id", encoded)
        self.assertFalse(first["success"]["production_reader_authorized"])

    def test_bundle_resolves_every_label_to_blind_annotation_evidence(self):
        split_arrays = {
            "train": arrays_for("train", self.house_by_split["train"]),
            "calibration": arrays_for(
                "calibration", self.house_by_split["calibration"]),
            "audit": arrays_for("audit", self.house_by_split["audit"]),
        }
        evidence = attach_evidence(split_arrays, self.d215)
        split_arrays["audit"]["semantic_labels"][0] = 1
        shards = [{
            "relative_path": f"{split}.npz", "file_sha256": str(index) * 64,
            "split": split, "arrays": split_arrays[split],
        } for index, split in enumerate(("train", "calibration", "audit"), 1)]
        with self.assertRaisesRegex(D216Error, "differs from evidence"):
            make_training_bundle_manifest(
                shards=shards, partition_manifest=self.partition,
                training_evidence_index=evidence, d215_contract=self.d215,
                d216_contract=self.d216)
        with self.assertRaisesRegex(D216Error, "must be unknown"):
            make_training_evidence_index([{
                "observation_id": "ambiguous", "public_observation_sha256":
                    "f" * 64,
                "annotator_a_label": "room",
                "annotator_b_label": "corridor",
                "adjudicated_label": "room",
                "unresolved_disagreement": True,
                "structural_label": "unknown",
            }], d215_contract=self.d215)

    def test_stage_refuses_before_opening_missing_external_input(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.json"
            with self.assertRaisesRegex(RuntimeError, "closed pending"):
                stage.seal_split(
                    source_inventory_path=missing,
                    reserved_manifest_path=missing,
                    output_path=Path(directory) / "output.json")


if __name__ == "__main__":
    unittest.main()
