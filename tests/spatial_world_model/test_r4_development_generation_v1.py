import json
from pathlib import Path
import unittest

from spatial_world_model.r4_families_v2 import family_config, validate_family_config


ROOT = Path(__file__).resolve().parents[2]
CONFIG = json.loads((ROOT / "configs/spatial_history/r4_development_generation_v1.json").read_text())
DESIGN = json.loads((ROOT / CONFIG["design"]).read_text())


class DevelopmentGenerationContractTests(unittest.TestCase):
    def test_exact_new_family_count_and_order(self):
        expected = [
            row["family_id"] for row in DESIGN["rows"]
            if row["split"] in CONFIG["allowed_splits"] and row["family_id"] not in CONFIG["existing_family_ids"]
        ]
        self.assertEqual(CONFIG["new_family_ids"], expected)
        self.assertEqual(len(expected), 48)

    def test_confirmation_is_absent(self):
        split = {row["family_id"]: row["split"] for row in DESIGN["rows"]}
        self.assertFalse(set(CONFIG["new_family_ids"]) & {key for key, value in split.items() if value in CONFIG["forbidden_splits"]})

    def test_all_development_families_accounted_once(self):
        combined = CONFIG["existing_family_ids"] + CONFIG["new_family_ids"]
        self.assertEqual(len(combined), len(set(combined)))
        self.assertEqual(len(combined), 52)

    def test_generation_stays_unreleased_in_config(self):
        self.assertFalse(CONFIG["implementation_review_complete"])
        self.assertFalse(CONFIG["generation_authorized"])
        self.assertFalse(CONFIG["training_authorized"])
        self.assertFalse(CONFIG["confirmation_authorized"])

    def test_each_new_family_materializes(self):
        base = json.loads((ROOT / CONFIG["base"]).read_text())
        rows = {row["family_id"]: row for row in DESIGN["rows"]}
        for family_id in CONFIG["new_family_ids"]:
            validate_family_config(family_config(base, rows[family_id]))

    def test_worker_range_is_bounded(self):
        self.assertEqual(CONFIG["limits"]["workers_default"], 6)
        self.assertEqual(CONFIG["limits"]["workers_allowed"], list(range(1, 9)))

    def test_output_is_new_and_external_reuse_is_explicit(self):
        self.assertNotEqual(CONFIG["run_directory"], CONFIG["existing_stage"])
        self.assertEqual(CONFIG["existing_family_ids"], DESIGN["engineering_family_ids"])


if __name__ == "__main__":
    unittest.main()
