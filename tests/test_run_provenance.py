"""Checks for stage-specific generation/training/export provenance."""
from pathlib import Path
import sys
import unittest

import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from cpmt.run_provenance import arrays_sha256, capture_run_provenance


class TestRunProvenance(unittest.TestCase):
    def test_array_digest_is_order_independent_and_content_sensitive(self):
        left = {"b": np.asarray([2], dtype=np.int64),
                "a": np.asarray([1], dtype=np.int64)}
        right = {"a": left["a"], "b": left["b"]}
        self.assertEqual(arrays_sha256(left), arrays_sha256(right))
        changed = {**right, "b": np.asarray([3], dtype=np.int64)}
        self.assertNotEqual(arrays_sha256(left), arrays_sha256(changed))

    def test_stage_snapshot_names_the_entrypoint_and_exact_worktree(self):
        provenance = capture_run_provenance(
            PROJECT, component="unit_test",
            entrypoint=PROJECT / "tests" / "test_run_provenance.py",
        )
        self.assertEqual(provenance["component"], "unit_test")
        self.assertEqual(provenance["schema_version"], "cpmt-run-provenance-v1")
        self.assertEqual(len(provenance["git_commit"]), 40)
        self.assertEqual(len(provenance["git_diff_sha256"]), 64)
        self.assertEqual(len(provenance["source_tree_sha256"]), 64)
        self.assertEqual(len(provenance["entrypoint_sha256"]), 64)
        self.assertEqual(
            provenance["entrypoint"], "tests/test_run_provenance.py",
        )
        self.assertIsInstance(provenance["git_dirty"], bool)


if __name__ == "__main__":
    unittest.main()
