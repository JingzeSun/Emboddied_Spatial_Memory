"""S3-05R fetch (ops/vsmt/hf_fetch.py): a released tier restores byte for byte to its original layout; corruption is refused."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for item in (ROOT / "src", ROOT / "ops" / "vsmt", ROOT / "tests"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import hf_fetch as fetch  # noqa: E402
import hf_release as driver  # noqa: E402
import test_vsmt_hf_release_driver as driver_tests  # noqa: E402  (module import: its tests are not collected twice)

ROOTS = driver_tests.ROOTS
from vsmt import lean_hf_release as hf  # noqa: E402
from vsmt import lean_test_seal as ts  # noqa: E402


class StoringHub:
    """A fake hub that keeps the uploaded bytes, so fetch can download them back."""

    def __init__(self, store: Path) -> None:
        self.store = store

    def ensure_repo(self, repo, repo_type):
        (self.store / repo.replace("/", "__")).mkdir(parents=True, exist_ok=True)

    def upload(self, repo, repo_type, folder, message):
        target = self.store / repo.replace("/", "__")
        shutil.copytree(folder, target, dirs_exist_ok=True)
        return "commit"

    def fetch(self, repo, repo_type, path, revision, directory):
        out = Path(directory) / path
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.store / repo.replace("/", "__") / path, out)
        return out


class FetchTest(unittest.TestCase):
    def setUp(self):
        maker = driver_tests.DriverTest()
        maker.setUp()
        self.base, self.state, self.staging = maker.base, maker.state, maker.staging
        self.hub = StoringHub(self.base / "hub")
        self.assertEqual(driver.run_tier("T1", base=str(self.base), state=self.state, staging=self.staging, batch_bytes=10 ** 9,
                                         uploader=self.hub, free_bytes=lambda path: 10 ** 12, commit="c" * 40), 0)
        self.dest = Path(tempfile.mkdtemp())

    def restore(self, prefixes=()):
        return fetch.restore("Jsun0632/vsmt-lean-s3-eval", "dataset", None, dest=self.dest, prefixes=prefixes, downloader=self.hub)

    def test_full_tier_restores_the_original_layout_byte_for_byte(self):
        result = self.restore()
        self.assertEqual(result, {"restored": 24, "skipped": 0, "problems": []})
        for kind, path in ROOTS.items():
            for split in ("validation", "test"):
                for episode in ("procthor10k-0.1.2-train-00001", "procthor10k-0.1.2-train-00002"):
                    self.assertEqual(ts.tree_digest(self.dest / path / split / episode), ts.tree_digest(self.base / path / split / episode))
                self.assertEqual((self.dest / path / split / "plan.json").read_bytes(), (self.base / path / split / "plan.json").read_bytes())

    def test_select_restores_only_the_prefix_and_a_rerun_skips(self):
        self.assertEqual(self.restore(["validation/instance_cache/"])["restored"], 3)
        self.assertFalse((self.dest / ROOTS["raw"]).exists())
        self.assertEqual(self.restore(["validation/instance_cache/"]), {"restored": 0, "skipped": 3, "problems": []})

    def test_a_corrupted_download_is_refused(self):
        stored = self.base / "hub" / "Jsun0632__vsmt-lean-s3-eval" / "test/raw/procthor10k-0.1.2-train-00001.tar"
        stored.write_bytes(stored.read_bytes()[:-512] + b"x" * 512)
        result = self.restore(["test/raw/"])
        self.assertEqual(result["problems"], ["download_differs:test/raw/procthor10k-0.1.2-train-00001.tar"])

    def test_an_existing_different_target_is_refused(self):
        self.restore(["test/geometry/"])
        (self.dest / ROOTS["geometry"] / "test" / "procthor10k-0.1.2-train-00002" / "data.bin").write_text("local edit", encoding="utf-8")
        result = self.restore(["test/geometry/"])
        self.assertEqual(result["problems"], [f"existing_target_differs:{ROOTS['geometry']}/test/procthor10k-0.1.2-train-00002"])

    def test_manifest_records_match_the_seal_for_test(self):
        body = json.loads((self.state / hf.MANIFEST_NAME).read_text(encoding="utf-8"))
        rows = {r["path_in_repo"]: r for r in body["items"]}
        seal = json.loads((self.base / driver.SEAL_EXPORT).read_text(encoding="utf-8"))
        self.assertEqual(rows["test/sam2_cache/procthor10k-0.1.2-train-00002.tar"]["tree"],
                         seal["kinds"]["sam2_cache"]["episodes"]["procthor10k-0.1.2-train-00002"])


if __name__ == "__main__":
    unittest.main()
