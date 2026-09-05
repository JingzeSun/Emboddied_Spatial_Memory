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


if __name__ == "__main__":
    unittest.main()
