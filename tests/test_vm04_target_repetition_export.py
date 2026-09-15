"""Repetition accounting uses private IDs but exports anonymous counts."""

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops/vsmt"))
spec = importlib.util.spec_from_file_location(
    "vm04_target_repetition_export",
    ROOT / "ops/vsmt/vm04_target_repetition_export.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TargetRepetitionTests(unittest.TestCase):
    def test_top1_and_unordered_top2_have_separate_repeat_counts(self):
        records = [
            {"visible_authored_asset_instance_ids": ["secret-chair", "secret-mug"]},
            {"visible_authored_asset_instance_ids": ["secret-mug", "secret-chair"]},
            {"visible_authored_asset_instance_ids": ["secret-chair", "secret-lamp"]},
        ]
        result = module.anonymous_repeats(records,
                                          "visible_authored_asset_instance_ids")
        self.assertEqual(result["repeated_top1_count"], 1)
        self.assertEqual(result["repeated_top2_set_count"], 1)
        self.assertNotIn("secret", str(result))


if __name__ == "__main__":
    unittest.main()
