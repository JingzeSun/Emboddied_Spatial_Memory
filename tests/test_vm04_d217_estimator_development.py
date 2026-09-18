from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
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
from vsmt.d216_estimator_training import validate_d216_contract  # noqa: E402
from vsmt.d217_estimator_development import (  # noqa: E402
    D217Error,
    make_development_plan,
    select_reachable_positions,
    structural_label_from_reachable,
    validate_d217_contract,
)
import vm04_d217_estimator_rgbd_stage as stage  # noqa: E402
import vm04_d217_rgbd_worker as worker  # noqa: E402


D215_PATH = ROOT / "configs/vsmt/vm04_d215_frontend_freeze_v1.json"
D216_PATH = ROOT / "configs/vsmt/vm04_d216_estimator_training_seal_v1.json"
D217_PATH = ROOT / "configs/vsmt/vm04_d217_estimator_development_rgbd_v1.json"


def digest(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class _Event:
    def __init__(self, *, success=True, reachable=None, value=0):
        self.metadata = {"lastActionSuccess": success}
        if reachable is not None:
            self.metadata["actionReturn"] = reachable
        self.frame = np.full((224, 224, 3), value, dtype=np.uint8)
        self.depth_frame = np.full((224, 224), value + 0.5, dtype=np.float32)


class _Controller:
    def __init__(self, reachable, *, fail_teleport=False):
        self.reachable = reachable
        self.fail_teleport = fail_teleport
        self.teleports = 0
        self.stopped = False

    def step(self, **request):
        if request["action"] == "GetReachablePositions":
            return _Event(reachable=self.reachable)
        self.teleports += 1
        return _Event(success=not self.fail_teleport, value=self.teleports)

    def stop(self):
        self.stopped = True


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

    def test_worker_writes_exact_public_arrays_and_keeps_private_identity_separate(self):
        reachable = [{"x": float(index), "y": 0.9, "z": 0.0}
                     for index in range(8)]
        selected = reachable.copy()
        house = {"source": "fixture"}
        controller = _Controller(reachable)
        with tempfile.TemporaryDirectory() as directory, patch.object(
                worker.source_worker, "load_source_record", return_value=house), patch.object(
                worker, "_make_controller", return_value=controller), patch.object(
                worker, "select_reachable_positions", return_value=selected), patch.object(
                worker, "structural_label_from_reachable", return_value="basin"):
            result = worker.generate_house({
                "row": {
                    "split": "train", "sample_rank": 0,
                    "house_id": "train:000123",
                    "source_locator": {"relative_path": "unused", "index": 0},
                    "source_record_sha256": digest(house),
                    "public_house_ref": "c" * 64,
                },
                "source_root": directory, "output_root": directory,
                "contract": self.d217, "d215_split_salt": "salt",
            })
            self.assertTrue(result["success"])
            self.assertTrue(controller.stopped)
            public_dir = Path(directory) / "public/train/sample_0000"
            with np.load(public_dir / "rgbd.npz", allow_pickle=False) as arrays:
                self.assertEqual(set(self.d217["rgbd_generation"]["public_arrays"]),
                                 set(arrays.files))
                self.assertEqual((32, 224, 224, 3), arrays["rgb_uint8"].shape)
                self.assertEqual((32, 224, 224), arrays["depth_m_float32"].shape)
            public_bytes = (public_dir / "receipt.json").read_text(encoding="utf-8")
            self.assertNotIn("train:000123", public_bytes)
            self.assertNotIn("world_position", public_bytes)
            private = json.loads((Path(directory) /
                                  "private/train/sample_0000/receipt.json").read_text(
                                      encoding="utf-8"))
            self.assertEqual("train:000123", private["house_id"])
            self.assertEqual(32, len(private["observations"]))
            reused = stage._existing_result(Path(directory), {
                "split": "train", "sample_rank": 0,
                "house_id": "train:000123",
                "source_record_sha256": digest(house),
                "public_house_ref": "c" * 64,
            })
            self.assertTrue(reused["success"])
            self.assertTrue(reused["reused"])
            with (public_dir / "rgbd.npz").open("ab") as handle:
                handle.write(b"tamper")
            with self.assertRaisesRegex(RuntimeError, "RGB-D bytes changed"):
                stage._existing_result(Path(directory), {
                    "split": "train", "sample_rank": 0,
                    "house_id": "train:000123",
                    "source_record_sha256": digest(house),
                    "public_house_ref": "c" * 64,
                })

    def test_worker_failure_is_retained_and_stage_reuses_it_without_replacement(self):
        reachable = [{"x": float(index), "y": 0.9, "z": 0.0}
                     for index in range(8)]
        house = {"source": "fixture"}
        controller = _Controller(reachable, fail_teleport=True)
        row = {
            "split": "calibration", "sample_rank": 7,
            "house_id": "train:000456",
            "source_locator": {"relative_path": "unused", "index": 0},
            "source_record_sha256": digest(house), "public_house_ref": "d" * 64,
        }
        with tempfile.TemporaryDirectory() as directory, patch.object(
                worker.source_worker, "load_source_record", return_value=house), patch.object(
                worker, "_make_controller", return_value=controller), patch.object(
                worker, "select_reachable_positions", return_value=reachable):
            result = worker.generate_house({
                "row": row, "source_root": directory, "output_root": directory,
                "contract": self.d217, "d215_split_salt": "salt",
            })
            self.assertFalse(result["success"])
            failure_path = Path(directory) / "private/calibration/sample_0007/failure.json"
            failure = json.loads(failure_path.read_text(encoding="utf-8"))
            self.assertFalse(failure["replacement_allowed"])
            reused = stage._existing_result(Path(directory), row)
            self.assertFalse(reused["success"])
            self.assertTrue(reused["reused"])

    def test_stage_respects_activation_before_reading_external_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.json"
            head = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
            parent = subprocess.check_output(
                ["git", "rev-parse", "HEAD^"], cwd=ROOT, text=True).strip()
            changed = subprocess.check_output(
                ["git", "diff-tree", "--no-commit-id", "--name-only", "-r",
                 head], cwd=ROOT, text=True).strip().splitlines()
            exact_activation_checkout = (
                self.d217["status"] == self.d217["activation_policy"][
                    "active_status"] and
                parent == self.d217["expected_reviewed_implementation_commit"] and
                changed == self.d217["activation_policy"]
                ["activation_commit_may_change_only"])
            if exact_activation_checkout:
                expected_error = FileNotFoundError
            else:
                expected_error = RuntimeError
            with self.assertRaises(expected_error) as raised:
                stage.seal_plan(source_inventory_path=missing,
                                output_root=Path(directory) / "output")
            if expected_error is RuntimeError:
                expected_message = (
                    "activation" if self.d217["status"] ==
                    self.d217["activation_policy"]["active_status"] else
                    "closed pending review")
                self.assertIn(expected_message, str(raised.exception))


if __name__ == "__main__":
    unittest.main()
