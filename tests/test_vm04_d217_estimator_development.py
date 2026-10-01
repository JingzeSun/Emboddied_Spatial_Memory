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
OPS = ROOT / "ops/vsmt"
for item in (SRC, OPS):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt.d215_frontend_freeze import validate_d215_contract  # noqa: E402
from vsmt.d216_estimator_training import validate_d216_contract  # noqa: E402
from vsmt.d217_estimator_development import (  # noqa: E402
    D217Error,
    make_development_plan,
    select_reachable_positions,
    structural_label_from_reachable,
    validate_d217_contract,
)


D215_PATH = ROOT / "configs/vsmt/vm04_d215_frontend_freeze_v1.json"
D216_PATH = ROOT / "configs/vsmt/vm04_d216_estimator_training_seal_v1.json"
D217_PATH = ROOT / "configs/vsmt/vm04_d217_estimator_development_rgbd_v1.json"


def digest(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class D217EstimatorDevelopmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d215 = validate_d215_contract(json.loads(
            D215_PATH.read_text(encoding="utf-8")))
        cls.d216 = validate_d216_contract(json.loads(
            D216_PATH.read_text(encoding="utf-8")))
        cls.d217 = validate_d217_contract(json.loads(
            D217_PATH.read_text(encoding="utf-8")))
        ids = [f"train:{index:06d}" for index in range(10000)]
        cls.inventory = {
            "source_manifest_sha256": cls.d216["d215_binding"]
            ["source_manifest_sha256"],
            "eligible_house_ids_sha256": digest(ids),
            "eligible_house_ids": ids,
            "inventory_sha256": "a" * 64,
            "houses": [{
                "house_id": house_id,
                "source_file_sha256": "b" * 64,
                "source_record_sha256": digest({"house_id": house_id}),
                "source_locator": {"relative_path": "houses.jsonl", "index": index},
            } for index, house_id in enumerate(ids)],
        }

    def test_review_candidate_closes_execution_and_later_science(self):
        active_status = self.d217["activation_policy"]["active_status"]
        if self.d217["status"] == active_status:
            self.assertEqual(
                {"development_plan_sealing", "capacity_probe",
                 "train_rgbd_generation", "calibration_rgbd_generation"},
                {name for name, enabled in self.d217["authorization"].items()
                 if enabled},
            )
            self.assertRegex(
                self.d217["expected_reviewed_implementation_commit"],
                r"^[0-9a-f]{40}$",
            )
        else:
            self.assertFalse(any(self.d217["authorization"].values()))
            self.assertIsNone(
                self.d217["expected_reviewed_implementation_commit"])
        changed = deepcopy(self.d217)
        changed["authorization"]["audit_open_or_generation"] = True
        with self.assertRaises(D217Error):
            validate_d217_contract(changed)
        changed = deepcopy(self.d217)
        changed["activation_policy"]["active_true_authorizations"].append(
            "audit_open_or_generation")
        with self.assertRaisesRegex(D217Error, "activation policy"):
            validate_d217_contract(changed)

    def test_plan_freezes_512_64_64_without_opening_audit_or_confirmation(self):
        with patch("vsmt.d217_estimator_development.validate_source_inventory",
                   return_value=self.inventory), patch(
                       "vsmt.d216_estimator_training.validate_source_inventory",
                       return_value=self.inventory):
            artifacts = make_development_plan(
                source_inventory=self.inventory, d215_contract=self.d215,
                d216_contract=self.d216, d217_contract=self.d217)
        public = artifacts["public_plan"]
        private = artifacts["private_plan"]
        self.assertEqual({"train": 512, "calibration": 64, "audit": 64},
                         public["sample_counts"])
        self.assertEqual(576, len(private["rows"]))
        self.assertEqual(64, public["audit"]["count"])
        self.assertEqual(12, len(public["validation_house_ids"]))
        self.assertFalse(public["observations_or_labels_read"])
        self.assertFalse(private["audit_opened"])
        confirmation_ids = artifacts["private_confirmation_pool"]["house_ids"]
        self.assertEqual(64, len(confirmation_ids))
        encoded_public = canonical_json(public)
        self.assertFalse(any(house_id in encoded_public
                             for house_id in confirmation_ids))
        selected = {row["house_id"] for row in private["rows"]}
        self.assertTrue(selected.isdisjoint(public["validation_house_ids"]))
        self.assertTrue(selected.isdisjoint(confirmation_ids))
        self.assertNotIn("train:004270", selected)
        self.assertNotIn("train:008243", selected)

    def test_position_selection_is_deterministic_spaced_and_fails_without_eight(self):
        positions = [
            {"x": float(x), "y": 0.9, "z": float(z)}
            for x in range(4) for z in range(4)
        ]
        first = select_reachable_positions(
            "train:000001", positions, split_salt="salt")
        second = select_reachable_positions(
            "train:000001", list(reversed(positions)), split_salt="salt")
        self.assertEqual(first, second)
        self.assertEqual(8, len(first))
        self.assertTrue(all(
            np.linalg.norm(np.asarray(tuple(left.values())) -
                           np.asarray(tuple(right.values()))) >= 1.0 - 1e-12
            for index, left in enumerate(first) for right in first[index + 1:]))
        with self.assertRaisesRegex(D217Error, "fewer than eight"):
            select_reachable_positions(
                "train:000001", positions[:4], split_salt="salt")

    def test_structural_rule_distinguishes_open_basin_and_two_sided_bottleneck(self):
        basin = [{"x": x * 0.25, "y": 0.0, "z": z * 0.25}
                 for x in range(-4, 5) for z in range(-4, 5)]
        self.assertEqual("basin", structural_label_from_reachable(
            basin, {"x": 0.0, "y": 0.0, "z": 0.0}))
        bottleneck = [{"x": 0.0, "y": 0.0, "z": 0.0}]
        for sign in (-1, 1):
            bottleneck.extend(
                {"x": sign * index * 0.25, "y": 0.0, "z": z}
                for index in range(1, 8) for z in (0.0, 0.25))
        self.assertEqual("bottleneck", structural_label_from_reachable(
            bottleneck, {"x": 0.0, "y": 0.0, "z": 0.0}))


if __name__ == "__main__":
    unittest.main()
