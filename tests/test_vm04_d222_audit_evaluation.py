from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vsmt.d222_audit_evaluation import (  # noqa: E402
    D222Error,
    evaluate_frozen_estimator,
    validate_d222_contract,
    verify_frozen_model,
)


D222_PATH = ROOT / "configs/vsmt/vm04_d222_structural_audit_v1.json"
COMMIT = "a" * 40


class D222AuditEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = validate_d222_contract(json.loads(
            D222_PATH.read_text(encoding="utf-8")))

    def active(self):
        return deepcopy(self.contract)

    def closed(self):
        value = deepcopy(self.contract)
        value["status"] = "metrics_frozen_audit_closed"
        for name in value["authorization"]:
            value["authorization"][name] = False
        return value

    def model(self):
        binding = self.contract["frozen_model_binding"]
        weights = np.zeros((3, 396))
        weights[0, 0] = 4.0
        weights[1, 1] = 4.0
        weights[2, 2] = 4.0
        return (
            {"weights_sha256": binding["weights_sha256"],
             "model_id": binding["model_id"], "semantic_head_present": False,
             "structural_weights": weights.tolist(),
             "structural_bias": [0.0, 0.0, 0.0],
             "structural_temperature": 1.0},
            {"normalization_receipt_sha256":
                 binding["normalization_receipt_sha256"],
             "mean": [0.0] * 396,
             "population_std_floor_1e_6": [1.0] * 396},
            {"training_receipt_sha256": binding["training_receipt_sha256"]},
        )

    def arrays(self, houses=8, per_house=4):
        features = []
        labels = []
        house_ids = []
        for house in range(houses):
            for index in range(per_house):
                label = index % 3
                row = np.zeros(396, dtype=np.float32)
                row[label] = 1.0
                features.append(row)
                labels.append(label)
                house_ids.append(f"train:{house:06d}")
        return {
            "features": np.stack(features),
            "structural_labels": np.asarray(labels, dtype=np.uint8),
            "house_ids": np.asarray(house_ids),
        }

    # ---- contract ------------------------------------------------------

    def test_activated_audit_keeps_every_downstream_gate_false(self):
        self.assertEqual("frozen_executable_audit", self.contract["status"])
        authorization = self.contract["authorization"]
        self.assertEqual(
            {"audit_rgbd_generation", "audit_feature_materialization",
             "audit_evaluation"},
            {name for name, value in authorization.items() if value})
        for name in self.contract["run_authorization_policy"][
                "must_remain_false"]:
            self.assertFalse(authorization[name], name)
        validate_d222_contract(self.closed())

    def test_metrics_are_frozen(self):
        metrics = self.contract["frozen_metric_definitions"]
        self.assertTrue(
            metrics["frozen_before_any_audit_observation_existed"])
        self.assertTrue(
            metrics["no_metric_outside_this_list_may_be_computed_or_reported"])
        self.assertEqual(15, metrics["calibration_error"]["bins"])
        self.assertEqual("house", metrics["bootstrap"]["unit"])
        self.assertEqual(10000, metrics["bootstrap"]["resamples"])
        self.assertEqual(260919, metrics["bootstrap"]["seed"])

    def test_contract_forbids_using_the_audit_to_change_anything(self):
        one_shot = self.contract["one_shot"]
        self.assertTrue(one_shot["audit_runs_once"])
        self.assertFalse(one_shot[
            "audit_failure_may_add_houses_change_model_or_thresholds"])
        broken = deepcopy(self.contract)
        broken["one_shot"][
            "audit_failure_may_add_houses_change_model_or_thresholds"] = True
        with self.assertRaisesRegex(D222Error, "one-shot boundary"):
            validate_d222_contract(broken)

    def test_contract_rejects_reopening_a_downstream_gate(self):
        opened = deepcopy(self.contract)
        opened["authorization"]["estimator_retraining"] = True
        with self.assertRaisesRegex(D222Error, "must keep estimator_retraining"):
            validate_d222_contract(opened)

    def test_bootstrap_unit_may_not_be_downgraded_to_frames(self):
        framed = deepcopy(self.contract)
        framed["frozen_metric_definitions"]["bootstrap"]["unit"] = "frame"
        with self.assertRaisesRegex(D222Error, "bootstrap definition"):
            validate_d222_contract(framed)

    # ---- frozen model binding -------------------------------------------

    def test_audit_refuses_weights_it_is_not_bound_to(self):
        weights, normalization, receipt = self.model()
        weights["weights_sha256"] = "f" * 64
        with self.assertRaisesRegex(D222Error, "different weights_sha256"):
            verify_frozen_model(self.contract, weights=weights,
                                normalization=normalization,
                                training_receipt=receipt)

    def test_audit_refuses_a_model_carrying_a_semantic_head(self):
        weights, normalization, receipt = self.model()
        weights["semantic_head_present"] = True
        with self.assertRaisesRegex(D222Error, "semantic head"):
            verify_frozen_model(self.contract, weights=weights,
                                normalization=normalization,
                                training_receipt=receipt)

    # ---- evaluation ------------------------------------------------------

    def test_closed_contract_refuses_to_evaluate(self):
        weights, normalization, receipt = self.model()
        with self.assertRaisesRegex(D222Error, "not authorized"):
            evaluate_frozen_estimator(
                audit_arrays=self.arrays(), weights=weights,
                normalization=normalization, training_receipt=receipt,
                d222_contract=self.closed(), run_commit=COMMIT)

    def test_report_carries_exactly_the_frozen_metrics(self):
        weights, normalization, receipt = self.model()
        report = evaluate_frozen_estimator(
            audit_arrays=self.arrays(), weights=weights,
            normalization=normalization, training_receipt=receipt,
            d222_contract=self.active(), run_commit=COMMIT)
        self.assertIn("structural_nll", report)
        self.assertIn("structural_accuracy", report)
        self.assertIn("calibration_error", report)
        self.assertEqual(15, len(report["calibration_bin_table"]))
        self.assertEqual({"basin", "bottleneck", "unknown"},
                         set(report["per_class_interval"]))
        self.assertEqual({"structural_accuracy", "structural_nll"},
                         set(report["per_house_interval"]))
        self.assertFalse(report["metrics_outside_the_frozen_list_computed"])
        self.assertFalse(report["model_refitted_during_audit"])
        self.assertFalse(report["audit_used_to_select_anything"])
        self.assertFalse(report["reachable_grid_read_at_inference"])
        self.assertEqual(8, report["houses"])
        self.assertEqual(32, report["observations"])

    def test_a_separable_problem_is_solved_and_intervals_are_house_level(self):
        weights, normalization, receipt = self.model()
        report = evaluate_frozen_estimator(
            audit_arrays=self.arrays(), weights=weights,
            normalization=normalization, training_receipt=receipt,
            d222_contract=self.active(), run_commit=COMMIT)
        self.assertEqual(1.0, report["structural_accuracy"])
        low, high = report["per_house_interval"]["structural_accuracy"]
        self.assertLessEqual(low, 1.0)
        self.assertLessEqual(high, 1.0)
        self.assertEqual(10000, report["bootstrap"]["resamples"])
        self.assertEqual("house", report["bootstrap"]["unit"])

    def test_evaluation_is_deterministic(self):
        weights, normalization, receipt = self.model()
        first = evaluate_frozen_estimator(
            audit_arrays=self.arrays(), weights=weights,
            normalization=normalization, training_receipt=receipt,
            d222_contract=self.active(), run_commit=COMMIT)
        second = evaluate_frozen_estimator(
            audit_arrays=self.arrays(), weights=weights,
            normalization=normalization, training_receipt=receipt,
            d222_contract=self.active(), run_commit=COMMIT)
        self.assertEqual(first["audit_report_sha256"],
                         second["audit_report_sha256"])

    def test_malformed_audit_arrays_are_refused(self):
        weights, normalization, receipt = self.model()
        arrays = self.arrays()
        arrays["structural_labels"] = np.full(
            len(arrays["structural_labels"]), 7, dtype=np.uint8)
        with self.assertRaisesRegex(D222Error, "labels are out of range"):
            evaluate_frozen_estimator(
                audit_arrays=arrays, weights=weights,
                normalization=normalization, training_receipt=receipt,
                d222_contract=self.active(), run_commit=COMMIT)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
