import json
from pathlib import Path
import tempfile
import unittest

from ops.spatial_history import r4_dual_m_stage_v1 as stage


class DualMStageTests(unittest.TestCase):
    def test_config_registers_development_and_excludes_confirmation(self):
        config, rows = stage.configuration()
        self.assertEqual(len(rows), 52)
        self.assertEqual({row["split"] for row in rows},
                         {"model_train", "model_validation", "probe_train",
                          "probe_validation"})
        self.assertFalse({row["split"] for row in rows} &
                         set(config["forbidden_splits"]))
        self.assertEqual(config["counts"]["systems"], 2)
        self.assertFalse(config["confirmation_authorized"])

    def test_all_bound_sources_exist(self):
        self.assertTrue(all((stage.ROOT / name).is_file() for name in stage.BOUND))

    def test_registered_source_file_detects_changed_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "public").mkdir()
            path = root / "public" / "LL.json.gz"
            path.write_bytes(b"public")
            (root / "public_manifest.json").write_text(json.dumps({
                "LL.json.gz": stage.file_record(path)}))
            self.assertEqual(stage.source_file(root, "public", "LL.json.gz"), path)
            path.write_bytes(b"changed")
            with self.assertRaises(ValueError):
                stage.source_file(root, "public", "LL.json.gz")

    def test_source_family_is_bound_by_global_generation_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "execution" / "r4-00" / "data"
            data.mkdir(parents=True)
            manifest = data / "public_manifest.json"
            manifest.write_text("{}")
            (root / "run_receipt.json").write_text(json.dumps({
                "exit_code": 0, "accepted": True,
                "artifacts": {"r4-00/data/public_manifest.json":
                              stage.file_record(manifest)},
            }))
            self.assertEqual(stage.verified_source_root(root, "r4-00"), data)
            manifest.write_text('{"changed":true}')
            with self.assertRaises(ValueError):
                stage.verified_source_root(root, "r4-00")

    def test_encoding_rejects_nonfinite_values(self):
        with self.assertRaises(ValueError):
            stage.encode({"value": float("nan")})


if __name__ == "__main__":
    unittest.main()
