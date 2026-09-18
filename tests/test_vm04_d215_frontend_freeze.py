from __future__ import annotations

from copy import deepcopy
import inspect
import json
from pathlib import Path
import sys
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vsmt.d214_shared_frontend import D214Error, P08EligibilityConfig  # noqa: E402
from vsmt import d215_frontend_freeze as freeze_core  # noqa: E402
from vsmt.d215_frontend_freeze import (  # noqa: E402
    D215Error,
    GEOMETRY_FEATURE_ORDER,
    assign_estimator_house_split,
    run_frozen_two_head_estimator,
    validate_d215_contract,
)


CONTRACT_PATH = ROOT / "configs/vsmt/vm04_d215_frontend_freeze_v1.json"


class D215FrontendFreezeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = validate_d215_contract(json.loads(
            CONTRACT_PATH.read_text(encoding="utf-8")
        ))

    def test_sam_checkpoint_yaml_mask_config_and_receipts_are_frozen(self):
        sam = self.contract["sam2"]
        self.assertEqual(184416285, sam["checkpoint_bytes"])
        self.assertEqual(
            "6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38",
            sam["checkpoint_sha256"],
        )
        self.assertEqual(32, sam["automatic_mask_generator"]["points_per_side"])
        self.assertFalse(sam["proposal_boundary"]["cross_frame_memory_enabled"])
        self.assertFalse(any(self.contract["authorization"].values()))

    def test_asset_or_derived_digest_drift_fails_closed(self):
        changed = deepcopy(self.contract)
        changed["sam2"]["automatic_mask_generator"]["pred_iou_thresh"] = 0.81
        with self.assertRaisesRegex(D215Error, "automatic-mask config"):
            validate_d215_contract(changed)
        changed = deepcopy(self.contract)
        changed["semantic_structural_estimator"]["training_split"][
            "split_rule_sha256"] = "0" * 64
        with self.assertRaisesRegex(D215Error, "derived freeze digest"):
            validate_d215_contract(changed)
        changed = deepcopy(self.contract)
        changed["semantic_structural_estimator"]["training"][
            "learning_rate"] = 0.002
        changed["semantic_structural_estimator"]["inference_config_sha256"] = (
            freeze_core._derived_digests(changed)["inference"]
        )
        with self.assertRaisesRegex(D215Error, "payload changed"):
            validate_d215_contract(changed)

    def test_split_is_house_level_deterministic_and_excludes_p0_houses(self):
        self.assertEqual("excluded", assign_estimator_house_split(
            "train:004270", contract=self.contract,
        ))
        first = assign_estimator_house_split(
            "train:000123", contract=self.contract,
        )
        second = assign_estimator_house_split(
            "train:000123", contract=deepcopy(self.contract),
        )
        self.assertEqual(first, second)
        self.assertIn(first, {"train", "calibration", "audit"})
        observed = {
            assign_estimator_house_split(f"train:{index:06d}",
                                         contract=self.contract)
            for index in range(100)
        }
        self.assertEqual({"train", "calibration", "audit"}, observed)

    def test_estimator_is_scenario_blind_and_blocked_until_training_receipts(self):
        names = inspect.signature(run_frozen_two_head_estimator).parameters
        self.assertFalse(any(
            token in name.lower() for name in names
            for token in ("scenario", "route", "house", "private", "teacher", "future")
        ))
        geometry = {name: 0.0 for name in GEOMETRY_FEATURE_ORDER}
        with self.assertRaisesRegex(D215Error, "not been trained and sealed"):
            run_frozen_two_head_estimator(
                dinov2_descriptor=np.zeros(384),
                public_geometry_features=geometry,
                normalization_mean=np.zeros(396),
                normalization_std=np.ones(396),
                semantic_weights=np.zeros((3, 396)),
                semantic_bias=np.zeros(3),
                structural_weights=np.zeros((3, 396)),
                structural_bias=np.zeros(3),
                semantic_temperature=1.0,
                structural_temperature=1.0,
                weights_sha256="1" * 64,
                normalization_receipt_sha256="2" * 64,
                training_receipt_sha256="3" * 64,
                contract=self.contract,
            )

    def test_p08_four_numbers_are_exact_and_cannot_be_changed(self):
        p08 = self.contract["p08_qualification"]
        self.assertEqual(
            (0.7, 0.7, 0.85, 0.35),
            (p08["basin_probability_minimum"],
             p08["bottleneck_probability_minimum"],
             p08["fragment_descriptor_cosine_minimum"],
             p08["fragment_centroid_distance_maximum_m"]),
        )
        P08EligibilityConfig(0.7, 0.7, 0.85, 0.35)
        with self.assertRaisesRegex(D214Error, "thresholds are frozen"):
            P08EligibilityConfig(0.69, 0.7, 0.85, 0.35)

    def test_training_labels_are_isolated_from_inference(self):
        estimator = self.contract["semantic_structural_estimator"]
        labels = estimator["label_boundary"]
        self.assertFalse(labels["reference_labels_available_to_inference_or_cache"])
        self.assertFalse(labels["p0_house_private_metadata_used_for_training"])
        self.assertIsNone(estimator["training_split"]
                          ["actual_partition_manifest_receipt_sha256"])
        self.assertIsNone(estimator["weights_sha256"])


if __name__ == "__main__":
    unittest.main()
