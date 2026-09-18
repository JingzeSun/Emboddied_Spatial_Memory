from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt.d215_frontend_freeze import validate_d215_contract  # noqa: E402
from vsmt.d216_estimator_training import (  # noqa: E402
    make_house_split_manifest,
    make_reserved_house_manifest,
    validate_d216_contract,
)
from vsmt.d219_estimator_training import (  # noqa: E402
    D219Error,
    fit_and_seal_structural_estimator,
    make_structural_bundle_manifest,
    validate_d219_contract,
    validate_structural_bundle_manifest,
    validate_structural_shard_arrays,
    verify_frozen_predecessors,
)


D215_PATH = ROOT / "configs/vsmt/vm04_d215_frontend_freeze_v1.json"
D216_PATH = ROOT / "configs/vsmt/vm04_d216_estimator_training_seal_v1.json"
D219_PATH = ROOT / "configs/vsmt/vm04_d219_structural_only_estimator_v1.json"
COMMIT = "0" * 40


def digest(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def arrays_for(split: str, house: str, offset: float = 0.0):
    """Build one structural-only shard with every class present."""

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
        "structural_labels": labels.copy(),
        "house_ids": np.asarray([house] * count),
        "observation_ids": np.asarray(
            [f"{split}-observation-{index}" for index in range(count)]),
        "public_observation_sha256": marker.copy(),
        "structural_label_receipt_sha256": marker.copy(),
    }


class D219StructuralOnlyEstimatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d215 = validate_d215_contract(json.loads(
            D215_PATH.read_text(encoding="utf-8")))
        cls.d216 = validate_d216_contract(json.loads(
            D216_PATH.read_text(encoding="utf-8")))
        cls.d219 = validate_d219_contract(json.loads(
            D219_PATH.read_text(encoding="utf-8")))
        ids = [f"train:{index:06d}" for index in range(10000)]
        cls.inventory = {
            "source_manifest_sha256":
                cls.d216["d215_binding"]["source_manifest_sha256"],
            "eligible_house_ids_sha256": digest(ids),
            "eligible_house_ids": ids,
            "inventory_sha256": "a" * 64,
        }
        reserved = make_reserved_house_manifest([
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
                reserved_house_manifest=reserved,
                d215_contract=cls.d215, d216_contract=cls.d216)
        cls.house_by_split = {
            split: next(row["house_id"] for row in cls.partition["rows"]
                        if row["split"] == split)
            for split in ("train", "calibration", "audit")
        }

    def split_arrays(self, splits=("train", "calibration")):
        """E-06 trains on train+calibration; audit stays sealed until E-08."""

        return {split: arrays_for(split, self.house_by_split[split])
                for split in splits}

    def bundle(self, split_arrays):
        return make_structural_bundle_manifest(
            split_arrays=split_arrays, partition_manifest=self.partition,
            d219_contract=self.d219)

    # ---- contract ----------------------------------------------------

    def test_activated_training_keeps_every_downstream_gate_false(self):
        """E-06 is authorized; everything after it must stay shut."""

        self.assertEqual("frozen_executable_structural_training",
                         self.d219["status"])
        self.assertTrue(self.d219["authorization"]["structural_training"])
        for name in self.d219["run_authorization_policy"]["must_remain_false"]:
            self.assertFalse(self.d219["authorization"][name], name)
        self.assertFalse(
            self.d219["authorization"]["audit_open_or_generation"])
        self.assertFalse(any(self.d219["closed_downstream"].values()))
        opened = deepcopy(self.d219)
        opened["authorization"]["audit_open_or_generation"] = True
        with self.assertRaisesRegex(D219Error, "must keep"):
            validate_d219_contract(opened)

    def test_closed_contract_would_keep_every_gate_false(self):
        closed = deepcopy(self.d219)
        closed["status"] = "implementation_pending_review_all_execution_closed"
        closed["authorization"]["structural_training"] = True
        with self.assertRaisesRegex(D219Error, "must keep every run gate"):
            validate_d219_contract(closed)

    def test_contract_pins_single_head_and_public_only_inference(self):
        architecture = self.d219["structural_estimator"]["architecture"]
        self.assertIsNone(architecture["semantic_head"])
        self.assertEqual(0, architecture["hidden_layers"])
        self.assertEqual(["basin", "bottleneck", "unknown"],
                         architecture["structural_labels"])
        boundary = self.d219["label_boundary"]
        self.assertFalse(boundary["p08_may_read_reachable_grid_truth"])
        self.assertIn("inference",
                      boundary["private_reachable_grid_forbidden_scope"])
        self.assertIn("audit_split_label_generation",
                      boundary["private_reachable_grid_permitted_scope"])
        leaked = deepcopy(self.d219)
        leaked["label_boundary"]["p08_may_read_reachable_grid_truth"] = True
        with self.assertRaisesRegex(D219Error, "label boundary"):
            validate_d219_contract(leaked)

    def test_contract_forbids_a_constant_unknown_placeholder(self):
        faked = deepcopy(self.d219)
        faked["removed_semantic_head"][
            "constant_unknown_placeholder_allowed"] = True
        with self.assertRaisesRegex(D219Error, "semantic removal"):
            validate_d219_contract(faked)

    def test_contract_may_not_retune_the_frozen_p08_numbers(self):
        tuned = deepcopy(self.d219)
        tuned["p08_qualification"]["may_be_tuned_by_route_yield"] = True
        with self.assertRaisesRegex(D219Error, "frozen P08 numbers"):
            validate_d219_contract(tuned)

    def test_activation_never_opens_the_downstream_gates(self):
        active = deepcopy(self.d219)
        active["status"] = "frozen_executable_structural_training"
        active["authorization"]["structural_training"] = True
        validate_d219_contract(active)
        active["authorization"]["production_reader"] = True
        with self.assertRaisesRegex(D219Error, "must keep production_reader"):
            validate_d219_contract(active)

    # ---- frozen predecessor chain -------------------------------------

    def test_frozen_predecessor_bytes_must_not_change(self):
        bindings = self.d219["frozen_predecessor_bindings"]
        paths = [bindings[f"{key}_relative_path"]
                 for key in ("d215", "d216", "d217", "d218")]
        blobs = {path: (ROOT / path).read_bytes() for path in paths}
        self.assertEqual({"d215", "d216", "d217", "d218"},
                         set(verify_frozen_predecessors(
                             self.d219, file_bytes=blobs)))
        tampered = dict(blobs)
        tampered[paths[0]] = blobs[paths[0]] + b" "
        with self.assertRaisesRegex(D219Error, "d215 bytes changed"):
            verify_frozen_predecessors(self.d219, file_bytes=tampered)

    # ---- shards and bundle --------------------------------------------

    def test_shard_rejects_the_removed_semantic_arrays(self):
        arrays = arrays_for("train", self.house_by_split["train"])
        arrays["semantic_labels"] = np.zeros(9, dtype=np.uint8)
        with self.assertRaisesRegex(D219Error, "removed semantic array"):
            validate_structural_shard_arrays(
                arrays, split="train", partition_manifest=self.partition)

    def test_shard_rejects_a_house_from_another_split(self):
        arrays = arrays_for("train", self.house_by_split["calibration"])
        with self.assertRaisesRegex(D219Error, "does not belong"):
            validate_structural_shard_arrays(
                arrays, split="train", partition_manifest=self.partition)

    def test_bundle_seals_counts_and_detects_tampering(self):
        split_arrays = self.split_arrays()
        bundle = self.bundle(split_arrays)
        self.assertFalse(bundle["semantic_arrays_present"])
        self.assertEqual({"train": 9, "calibration": 9},
                         bundle["row_counts"])
        self.assertEqual([3, 3, 3],
                         bundle["structural_class_counts"]["train"])
        self.assertEqual(bundle, validate_structural_bundle_manifest(bundle))
        tampered = deepcopy(bundle)
        tampered["row_counts"]["train"] = 8
        with self.assertRaisesRegex(D219Error, "digest mismatch"):
            validate_structural_bundle_manifest(tampered)

    # ---- training ------------------------------------------------------

    def test_bundle_and_fit_work_while_the_audit_split_is_still_sealed(self):
        """E-06 runs before E-08, so audit arrays do not exist yet."""

        split_arrays = self.split_arrays()
        bundle = self.bundle(split_arrays)
        self.assertEqual(["train", "calibration"], bundle["splits_present"])
        self.assertFalse(bundle["audit_split_present"])
        sealed = fit_and_seal_structural_estimator(
            split_arrays=split_arrays, partition_manifest=self.partition,
            structural_bundle_manifest=bundle,
            d215_contract=self.d215, d219_contract=self.d219,
            implementation_commit=COMMIT)
        receipt = sealed["training_receipt"]
        self.assertEqual(["train", "calibration"], receipt["splits_used"])
        self.assertFalse(receipt["audit_split_present"])
        self.assertNotIn("audit", receipt["post_temperature_metrics"])
        self.assertFalse(receipt["audit_used_for_checkpoint_or_temperature"])

    def test_bundle_still_requires_train_and_calibration(self):
        with self.assertRaisesRegex(D219Error, "train and calibration"):
            self.bundle({"train": arrays_for(
                "train", self.house_by_split["train"])})

    def test_fit_produces_one_head_and_no_semantic_artifact(self):
        split_arrays = self.split_arrays()
        sealed = fit_and_seal_structural_estimator(
            split_arrays=split_arrays, partition_manifest=self.partition,
            structural_bundle_manifest=self.bundle(split_arrays),
            d215_contract=self.d215, d219_contract=self.d219,
            implementation_commit=COMMIT)
        weights = sealed["weights"]
        self.assertEqual((3, 396), np.asarray(
            weights["structural_weights"]).shape)
        self.assertEqual(3, len(weights["structural_bias"]))
        self.assertGreater(weights["structural_temperature"], 0.0)
        self.assertFalse(weights["semantic_head_present"])
        flattened = canonical_json(sealed)
        self.assertNotIn("semantic_weights", flattened)
        self.assertNotIn("semantic_temperature", flattened)
        receipt = sealed["training_receipt"]
        self.assertFalse(receipt["semantic_head_trained"])
        self.assertFalse(receipt["human_annotation_consumed"])
        self.assertFalse(receipt["reachable_grid_read_at_inference"])
        self.assertFalse(
            receipt["audit_used_for_checkpoint_or_temperature"])
        self.assertEqual(
            "d219.dinov2_geometry_single_structural_head.v1",
            weights["model_id"])
        self.assertFalse(sealed["success"]["audit_authorized"])
        self.assertFalse(sealed["success"]["production_reader_authorized"])

    def test_fit_is_deterministic_for_identical_input(self):
        first_arrays = self.split_arrays()
        second_arrays = self.split_arrays()
        first = fit_and_seal_structural_estimator(
            split_arrays=first_arrays, partition_manifest=self.partition,
            structural_bundle_manifest=self.bundle(first_arrays),
            d215_contract=self.d215, d219_contract=self.d219,
            implementation_commit=COMMIT)
        second = fit_and_seal_structural_estimator(
            split_arrays=second_arrays, partition_manifest=self.partition,
            structural_bundle_manifest=self.bundle(second_arrays),
            d215_contract=self.d215, d219_contract=self.d219,
            implementation_commit=COMMIT)
        self.assertEqual(first["weights"]["weights_sha256"],
                         second["weights"]["weights_sha256"])
        self.assertEqual(first["normalization"]["normalization_receipt_sha256"],
                         second["normalization"]
                         ["normalization_receipt_sha256"])

    def test_fit_rejects_arrays_that_do_not_match_the_sealed_bundle(self):
        split_arrays = self.split_arrays()
        bundle = self.bundle(split_arrays)
        swapped = self.split_arrays()
        swapped["train"]["features"][0, 0] += 1.0
        with self.assertRaisesRegex(D219Error, "sealed content digest"):
            fit_and_seal_structural_estimator(
                split_arrays=swapped, partition_manifest=self.partition,
                structural_bundle_manifest=bundle,
                d215_contract=self.d215, d219_contract=self.d219,
                implementation_commit=COMMIT)

    def test_fit_requires_a_real_implementation_commit(self):
        split_arrays = self.split_arrays()
        with self.assertRaisesRegex(D219Error, "implementation commit"):
            fit_and_seal_structural_estimator(
                split_arrays=split_arrays, partition_manifest=self.partition,
                structural_bundle_manifest=self.bundle(split_arrays),
                d215_contract=self.d215, d219_contract=self.d219,
                implementation_commit="not-a-commit")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
