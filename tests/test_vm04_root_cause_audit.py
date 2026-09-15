"""VM-04 diagnostic export keeps private instance IDs out of public counts."""

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops/vsmt"))
spec = importlib.util.spec_from_file_location(
    "vm04_root_cause_audit", ROOT / "ops/vsmt/vm04_root_cause_audit.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RootCauseAuditTests(unittest.TestCase):
    def test_source_membership_counts_do_not_export_private_ids(self):
        rows = [
            {"target_instance_ids": ["wall-secret-1", "chair-secret-1"]},
            {"target_instance_ids": ["painting-secret-2", "wall-secret-2"]},
        ]
        result = module.summarize_targets(
            rows, frozenset({"chair-secret-1", "painting-secret-2"}))
        self.assertEqual(result, {"authored_asset": 2, "not_authored_asset": 2,
                                  "selected_pose_count": 2})
        self.assertNotIn("secret", str(result))
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            module.summarize_targets([{"target_instance_ids": ["only-one"]}],
                                     frozenset({"only-one"}))


if __name__ == "__main__":
    unittest.main()
