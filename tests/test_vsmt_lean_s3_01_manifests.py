"""S3-01 manifests (ruling 102-8): the committed file recomputes from the frozen split, the confirmation block reproduces the
ruling-81 registry, and the five blocks never overlap.  CPU only, about a second (10,000 house ids hashed once)."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for item in (PROJECT_ROOT / "src", PROJECT_ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from vsmt import lean_s3_manifests as m  # noqa: E402

CONFIGS = PROJECT_ROOT / "configs" / "vsmt"


def load(name: str) -> dict:
    return json.loads((CONFIGS / name).read_text(encoding="utf-8"))


class TestS3Manifests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.freeze = load("lean_s1_02a_pilot_v2.json")["split_freeze"]
        cls.registry = load("lean_ruling81_confirmation_houses.json")
        cls.manifest = load("lean_s3_01_manifests.json")

    def test_the_committed_file_recomputes(self):
        m.validate(self.manifest, self.freeze, self.registry)
        self.assertEqual(self.manifest["counts"], {"test": 100, "validation": 50, "train": 300, "development_excluded": 50,
                                                   "confirmation_excluded": 50})

    def test_the_confirmation_block_is_the_ruling_81_list_and_nothing_overlaps(self):
        lists = m.derive(self.freeze)
        self.assertEqual(lists["confirmation_excluded"], self.registry["houses"])
        self.assertEqual(m.houses_sha256(lists["confirmation_excluded"]), self.registry["houses_sha256"])
        self.assertTrue(all(value == 0 for value in self.manifest["overlaps"].values()))
        self.assertEqual(len(self.manifest["overlaps"]), 10)

    def test_test_and_validation_are_the_frozen_split(self):
        from vsmt.lean_intervention import assign_split

        pool = m.house_pool()
        split = assign_split(pool, seed=20260920, train=len(pool) - 150, validation=50, test=100)
        self.assertEqual(self.manifest["test"], split["test"])
        self.assertEqual(self.manifest["validation"], split["validation"])
        self.assertEqual(self.manifest["train"], split["train"][100:400])

    def test_an_edited_list_is_refused(self):
        broken = copy.deepcopy(self.manifest)
        broken["train"][0], broken["train"][1] = broken["train"][1], broken["train"][0]
        with self.assertRaises(m.LeanS3ManifestError) as caught:
            m.validate(broken, self.freeze, self.registry)
        self.assertEqual(str(caught.exception), "manifest_list_mismatch:train")
        moved = dict(self.freeze, seed=1)
        with self.assertRaises(m.LeanS3ManifestError):
            m.validate(self.manifest, moved, self.registry)


if __name__ == "__main__":
    unittest.main()
