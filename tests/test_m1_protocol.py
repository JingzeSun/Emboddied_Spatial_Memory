"""Pre-test M1 protocol integrity tests; these do not generate or read test data."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from cpmt.m1_protocol import load_and_validate, protocol_sha256, validate_m1_protocol


class TestM1Protocol(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = PROJECT / "configs" / "m1_hard_condition.json"
        cls.config = load_and_validate(cls.path)

    def test_candidate_is_valid_and_fingerprinted(self):
        self.assertEqual(len(protocol_sha256(self.config)), 64)
        self.assertFalse(self.config["test_access"])

    def test_test_access_cannot_be_enabled(self):
        changed = deepcopy(self.config)
        changed["test_access"] = True
        with self.assertRaisesRegex(ValueError, "test access"):
            validate_m1_protocol(changed)

    def test_required_control_cannot_be_removed(self):
        changed = deepcopy(self.config)
        changed["methods"] = changed["methods"][:-1]
        with self.assertRaisesRegex(ValueError, "six A-F"):
            validate_m1_protocol(changed)

    def test_future_cannot_switch_to_planned_actions(self):
        changed = deepcopy(self.config)
        changed["future"]["source"] = "planned_action_sequence"
        with self.assertRaisesRegex(ValueError, "executed trajectory"):
            validate_m1_protocol(changed)

    def test_paired_group_bootstrap_is_required(self):
        changed = deepcopy(self.config)
        changed["evaluation"]["bootstrap"]["unit"] = "case_id"
        with self.assertRaisesRegex(ValueError, "paired groups"):
            validate_m1_protocol(changed)

    def test_endpoint_bootstrap_does_not_claim_family_strata(self):
        changed = deepcopy(self.config)
        changed["evaluation"]["bootstrap"]["stratify_by"] = "scenario_family"
        with self.assertRaisesRegex(ValueError, "one mixed registered"):
            validate_m1_protocol(changed)

    def test_e_cannot_execute_candidate_branches(self):
        changed = deepcopy(self.config)
        changed["future"]["no_execution_candidate_execution"] = (
            "allowed_during_training"
        )
        with self.assertRaisesRegex(ValueError, "may not execute"):
            validate_m1_protocol(changed)

    def test_recovery_stays_bounded_and_global_path_stays_in_m2(self):
        changed = deepcopy(self.config)
        changed["recovery"]["global_async_reconciliation"] = "M1"
        with self.assertRaisesRegex(ValueError, "global reconciliation"):
            validate_m1_protocol(changed)
        changed = deepcopy(self.config)
        changed["recovery"]["candidate_generator"] = "learned"
        with self.assertRaisesRegex(ValueError, "learned or expanded"):
            validate_m1_protocol(changed)

    def test_commit_report_partition_cannot_tune(self):
        changed = deepcopy(self.config)
        changed["training"]["commit_calibration"][
            "report_partition_selects_nothing"
        ] = False
        with self.assertRaisesRegex(ValueError, "cannot tune"):
            validate_m1_protocol(changed)

    def test_commit_grid_has_a_reachable_k_way_threshold(self):
        changed = deepcopy(self.config)
        changed["training"]["commit_calibration"][
            "commit_probability_grid"
        ] = [0.45, 0.55]
        with self.assertRaisesRegex(ValueError, "K-way softmax"):
            validate_m1_protocol(changed)


if __name__ == "__main__":
    unittest.main()
