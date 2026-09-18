from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt.d215_frontend_freeze import validate_d215_contract  # noqa: E402
from vsmt.d216_estimator_training import (  # noqa: E402
    make_house_split_manifest,
    make_reserved_house_manifest,
    validate_d216_contract,
)
from vsmt.d217_estimator_development import (  # noqa: E402
    ordered_sample_candidates,
    public_house_ref,
    validate_d217_contract,
)
from vsmt.d221_scale_extension import (  # noqa: E402
    D221Error,
    plan_prefix_extension,
    selected_house_counts,
    validate_d221_contract,
    validate_extension_plan,
)


ROOT = Path(__file__).resolve().parents[1]
D215_PATH = ROOT / "configs/vsmt/vm04_d215_frontend_freeze_v1.json"
D216_PATH = ROOT / "configs/vsmt/vm04_d216_estimator_training_seal_v1.json"
D217_PATH = ROOT / "configs/vsmt/vm04_d217_estimator_development_rgbd_v1.json"
D221_PATH = ROOT / "configs/vsmt/vm04_d221_estimator_scale_rule_v1.json"


def digest(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class D221ScaleExtensionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d215 = validate_d215_contract(json.loads(
            D215_PATH.read_text(encoding="utf-8")))
        cls.d216 = validate_d216_contract(json.loads(
            D216_PATH.read_text(encoding="utf-8")))
        cls.d217 = validate_d217_contract(json.loads(
            D217_PATH.read_text(encoding="utf-8")))
        cls.d221 = validate_d221_contract(json.loads(
            D221_PATH.read_text(encoding="utf-8")))
        ids = [f"train:{index:06d}" for index in range(10000)]
        inventory = {
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
                   return_value=inventory):
            cls.partition = make_house_split_manifest(
                source_inventory=inventory, reserved_house_manifest=reserved,
                d215_contract=cls.d215, d216_contract=cls.d216)
        cls.receipt = cls.partition["partition_manifest_receipt_sha256"]
        cls.salt = cls.d217["development_sample"]["sampling_salt"]

    def existing_plan(self, counts=None):
        """Rebuild the plan that D-217 sealed at 512/64/64."""

        counts = counts or self.d217["development_sample"]["house_counts"]
        rows = []
        for split in ("train", "calibration"):
            ordered = ordered_sample_candidates(
                self.partition["rows"], split=split, sampling_salt=self.salt)
            for rank, house_id in enumerate(ordered[:counts[split]]):
                rows.append({
                    "split": split, "sample_rank": rank, "house_id": house_id,
                    "public_house_ref": public_house_ref(
                        split=split, sample_rank=rank,
                        partition_manifest_receipt_sha256=self.receipt),
                })
        return {"partition_manifest_receipt_sha256": self.receipt, "rows": rows}

    def extend(self, existing=None, d221=None):
        return plan_prefix_extension(
            partition_manifest=self.partition,
            existing_private_plan=existing or self.existing_plan(),
            d217_contract=self.d217, d221_contract=d221 or self.d221)

    # ---- contract -----------------------------------------------------

    def test_contract_selects_2048_and_keeps_downstream_closed(self):
        self.assertEqual(
            "frozen_executable_structural_rgbd_expansion", self.d221["status"])
        self.assertEqual({"train": 2048, "calibration": 128, "audit": 128},
                         selected_house_counts(self.d221))
        self.assertTrue(
            self.d221["authorization"]["structural_rgbd_expansion"])
        for name in ("structural_training", "audit_open_or_generation",
                     "production_reader", "route_or_raw_generation"):
            self.assertFalse(self.d221["authorization"][name], name)

    def test_contract_records_that_the_rule_preceded_the_measurement(self):
        rule = self.d221["frozen_decision_rule"]
        self.assertTrue(rule["rule_frozen_before_reading_the_measurement"])
        self.assertTrue(rule["thresholds_may_not_be_adjusted_after_reading"])
        self.assertFalse(rule["full_house_expansion_permitted"])
        decision = self.d221["resulting_decision"]
        self.assertTrue(decision["thresholds_unchanged_after_reading"])
        self.assertTrue(decision["full_house_still_refused"])
        self.assertEqual(856, decision["observed_bottleneck_frames"])

    def test_contract_measurement_never_touched_audit_or_a_model(self):
        measurement = self.d221["measurement"]
        self.assertFalse(measurement["audit_split_read"])
        self.assertFalse(measurement["model_output_read"])
        self.assertFalse(measurement["new_simulation_run"])
        self.assertEqual(856,
                         measurement["structural_label_frames"]["bottleneck"])

    def test_contract_rejects_opening_a_downstream_gate(self):
        opened = deepcopy(self.d221)
        opened["authorization"]["structural_training"] = True
        with self.assertRaisesRegex(D221Error, "must keep structural_training"):
            validate_d221_contract(opened)

    def test_contract_rejects_an_unregistered_scale(self):
        invented = deepcopy(self.d221)
        invented["resulting_decision"]["decision"] = "expand_to_everything"
        with self.assertRaisesRegex(D221Error, "registered scale"):
            validate_d221_contract(invented)

    def test_pre_measurement_contract_may_not_authorize_an_expansion(self):
        early = deepcopy(self.d221)
        early["status"] = "rule_frozen_measurement_pending"
        early["measurement"] = None
        early["resulting_decision"] = None
        early["authorization"]["structural_rgbd_expansion"] = False
        validate_d221_contract(early)
        early["authorization"]["structural_rgbd_expansion"] = True
        with self.assertRaisesRegex(D221Error, "before the measurement"):
            validate_d221_contract(early)

    # ---- prefix invariance ---------------------------------------------

    def test_extension_keeps_every_existing_rank_byte_identical(self):
        existing = self.existing_plan()
        plan = self.extend(existing)
        self.assertEqual(plan, validate_extension_plan(plan))
        self.assertEqual({"train": 512, "calibration": 64, "audit": 64},
                         plan["previous_house_counts"])
        self.assertEqual({"train": 2048, "calibration": 128, "audit": 128},
                         plan["extended_house_counts"])
        self.assertEqual(len(existing["rows"]), plan["unchanged_row_count"])
        self.assertEqual((2048 - 512) + (128 - 64), plan["generate_row_count"])
        self.assertFalse(plan["full_house_expansion"])
        self.assertFalse(plan["audit_house_ids_opened"])
        self.assertTrue(plan["existing_rgbd_and_features_reused"])

    def test_new_rows_start_exactly_after_the_old_prefix(self):
        plan = self.extend()
        by_split = {"train": [], "calibration": []}
        for row in plan["rows_to_generate"]:
            by_split[row["split"]].append(row["sample_rank"])
        self.assertEqual(list(range(512, 2048)), sorted(by_split["train"]))
        self.assertEqual(list(range(64, 128)), sorted(by_split["calibration"]))

    def test_extension_refuses_when_an_existing_house_moved(self):
        tampered = self.existing_plan()
        tampered["rows"][0] = dict(tampered["rows"][0],
                                   house_id="train:009999")
        with self.assertRaisesRegex(D221Error, "changed house"):
            self.extend(tampered)

    def test_extension_refuses_when_a_public_house_ref_changed(self):
        tampered = self.existing_plan()
        tampered["rows"][3] = dict(tampered["rows"][3],
                                   public_house_ref="f" * 64)
        with self.assertRaisesRegex(D221Error, "public house ref"):
            self.extend(tampered)

    def test_extension_refuses_a_plan_from_another_partition(self):
        foreign = self.existing_plan()
        foreign["partition_manifest_receipt_sha256"] = "b" * 64
        with self.assertRaisesRegex(D221Error, "another partition"):
            self.extend(foreign)

    def test_extension_refuses_to_shrink_or_no_op(self):
        same = deepcopy(self.d221)
        same["resulting_decision"]["decision"] = \
            "keep_512_train_64_calibration_64_audit"
        same["resulting_decision"]["approved_scale"] = {
            "train": 512, "calibration": 64, "audit": 64}
        with self.assertRaisesRegex(D221Error, "without a change of scale"):
            self.extend(d221=same)

    def test_extension_is_deterministic(self):
        self.assertEqual(self.extend()["extension_plan_sha256"],
                         self.extend()["extension_plan_sha256"])

    def test_plan_digest_detects_tampering(self):
        plan = self.extend()
        tampered = deepcopy(plan)
        tampered["generate_row_count"] = 1
        with self.assertRaisesRegex(D221Error, "generate rows"):
            validate_extension_plan(tampered)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
