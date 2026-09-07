"""Unit checks for small-report export discovery."""
from pathlib import Path
import json
import sys
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from scripts.export_run_report import _runtime_profiles  # noqa: E402


class TestExportRunReport(unittest.TestCase):
    def test_nested_runtime_profiles_keep_relative_paths(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for arm in ("set_transformer", "shared_mlp"):
                target = root / arm / "runtime_profile.json"
                target.parent.mkdir()
                target.write_text(
                    json.dumps({"architecture": arm}), encoding="utf-8",
                )
            self.assertEqual(
                _runtime_profiles(root),
                {
                    "set_transformer/runtime_profile.json": {
                        "architecture": "set_transformer",
                    },
                    "shared_mlp/runtime_profile.json": {
                        "architecture": "shared_mlp",
                    },
                },
            )


if __name__ == "__main__":
    unittest.main()
