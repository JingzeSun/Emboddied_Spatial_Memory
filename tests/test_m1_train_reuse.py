"""Metadata-only provenance tests; shard bytes are mocked, no train arrays loaded."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cpmt import m1_train_reuse as reuse


class TestTrainReuse(unittest.TestCase):
    def fixture(self, directory):
        manifest = {"teacher_health_gate": {"pass": True}}
        (directory / "train.manifest.json").write_text(json.dumps(manifest))
        names = ["train.npz", "train.manifest.json"] + [f"shards/train_{g:06d}.npz" for g in range(1000)]
        marker = {"schema_version": "cpmt-scope-rebuild-train-v1", "exit_code": 0,
                  "arrays_digest": "digest", "arrays_path": str(directory / "train.npz"),
                  "attempt": {"provenance": {"git_commit": "a" * 40}},
                  "binding": {"protocol_sha256": "protocol", "groups": 1000, "split": "train"},
                  "test_access": False, "validation_generated": False, "training_performed": False,
                  "manifest": manifest, "file_sha256": {n: "file-digest" for n in names}}
        marker_path = directory / "generation.ok.json"
        marker_path.write_text(json.dumps(marker))
        policy = {"schema_version": "cpmt-m1-train-reuse-policy-v1", "decision": "D-054",
                  "test_access": False, "regeneration_performed": False, "arrays_digest": "digest",
                  "generation_marker_sha256": "marker-digest", "generation_commit": "a" * 40,
                  "generation_protocol_sha256": "protocol", "evidence_reports": {}, "reviewed_source_changes": {}}
        return marker_path, marker, policy

    def digest(self, path):
        return "marker-digest" if Path(path).name == "generation.ok.json" else "file-digest"

    def test_all_1002_file_names_checked_without_regeneration(self):
        with tempfile.TemporaryDirectory() as temp:
            path, _, policy = self.fixture(Path(temp))
            with patch.object(reuse, "source_changes", return_value={}), patch.object(reuse, "file_digest", side_effect=self.digest) as digest:
                report = reuse.validate_train_reuse(Path(temp), path, policy)
            self.assertTrue(report["accepted"])
            self.assertEqual(report["verified_files"], 1002)
            self.assertFalse(report["all_groups_regenerated_and_compared"])
            self.assertFalse(report["data_generated"])
            self.assertIn(Path(temp) / "shards/train_000999.npz", [c.args[0] for c in digest.call_args_list])

    def test_changed_shard_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path, _, policy = self.fixture(Path(temp))
            with patch.object(reuse, "source_changes", return_value={}), patch.object(reuse, "file_digest",
                    side_effect=lambda p: "tampered" if Path(p).name == "train_000123.npz" else self.digest(p)):
                with self.assertRaisesRegex(ValueError, "train_000123"):
                    reuse.validate_train_reuse(Path(temp), path, policy)

    def test_unreviewed_source_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path, _, policy = self.fixture(Path(temp))
            with patch.object(reuse, "source_changes", return_value={"unexpected.py": {}}), patch.object(reuse, "file_digest", side_effect=self.digest):
                with self.assertRaisesRegex(ValueError, "reviewed"):
                    reuse.validate_train_reuse(Path(temp), path, policy)

    def test_incomplete_manifest_file_list_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path, marker, policy = self.fixture(Path(temp))
            del marker["file_sha256"]["shards/train_000999.npz"]
            path.write_text(json.dumps(marker))
            with patch.object(reuse, "source_changes", return_value={}), patch.object(reuse, "file_digest", side_effect=self.digest):
                with self.assertRaisesRegex(ValueError, "file list incomplete"):
                    reuse.validate_train_reuse(Path(temp), path, policy)

    def test_current_source_matches_reviewed_delta_and_encoding_ast(self):
        policy = json.loads((ROOT / "configs/m1_train_reuse_policy.json").read_text())
        self.assertEqual(reuse.source_changes(ROOT, policy["generation_commit"]), policy["reviewed_source_changes"])


if __name__ == "__main__":
    unittest.main()
