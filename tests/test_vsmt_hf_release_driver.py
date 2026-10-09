"""S3-05R driver (ops/vsmt/hf_release.py): batched, resumable upload of one tier with a fake hub; refusal on a seal mismatch."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for item in (ROOT / "src", ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import hf_release as driver  # noqa: E402
from vsmt import lean_hf_release as hf  # noqa: E402
from vsmt import lean_test_seal as ts  # noqa: E402

TAG = "3f6ef1d"
ROOTS = {"raw": f"vsmt_outputs/s3-02-{TAG}", "geometry": f"vsmt_private/s3-02-geometry-{TAG}",
         "instance_cache": f"vsmt_caches/s3-02-instance-{TAG}", "sam2_cache": f"vsmt_caches/s3-02-sam2-{TAG}"}


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class FakeHub:
    def __init__(self) -> None:
        self.repos: dict[tuple[str, str], dict[str, dict]] = {}
        self.uploads: list[tuple[str, int]] = []

    def ensure_repo(self, repo, repo_type):
        self.repos.setdefault((repo, repo_type), {})

    def upload(self, repo, repo_type, folder, message):
        files = [p for p in Path(folder).rglob("*") if p.is_file()]
        for path in files:
            self.repos[(repo, repo_type)][path.relative_to(folder).as_posix()] = {"bytes": path.stat().st_size, "sha256": hf.file_sha256(path)}
        self.uploads.append((repo, len(files)))
        return f"commit{len(self.uploads):04d}"

    def remote_files(self, repo, repo_type):
        return dict(self.repos[(repo, repo_type)])

    def head(self, repo, repo_type):
        return f"rev{len(self.uploads)}"


class DriverTest(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp())
        for kind, path in ROOTS.items():
            for split in ("validation", "test"):
                root = self.base / path / split
                for name in ("procthor10k-0.1.2-train-00001", "procthor10k-0.1.2-train-00002"):
                    write(root / name / "receipt.json", json.dumps({"status": "succeeded", "kind": kind, "split": split}))
                    write(root / name / "data.bin", f"{kind}-{split}-{name}" * 40)
                write(root / "plan.json", "{}")
        self.seal = {"kinds": {kind: {"episodes": {d.name: ts.tree_digest(d) for d in sorted((self.base / ROOTS[kind] / "test").iterdir()) if d.is_dir()},
                                      "root_files": ts._root_files(self.base / ROOTS[kind] / "test")} for kind in ts.SEAL_KINDS}}
        write(self.base / driver.SEAL_EXPORT, json.dumps(self.seal))
        self.state = self.base / "state"
        self.staging = self.base / "staging"

    def run_t1(self, hub, batch=10 ** 9):
        return driver.run_tier("T1", base=str(self.base), state=self.state, staging=self.staging, batch_bytes=batch, uploader=hub,
                               free_bytes=lambda path: 10 ** 12, commit="c" * 40)

    def test_uploads_every_item_writes_the_manifest_and_verifies(self):
        hub = FakeHub()
        self.assertEqual(self.run_t1(hub), 0)
        remote = hub.repos[("Jsun0632/vsmt-lean-s3-eval", "dataset")]
        self.assertIn("test/raw/procthor10k-0.1.2-train-00001.tar", remote)
        self.assertIn("validation/sam2_cache/_root/plan.json", remote)
        self.assertIn(hf.MANIFEST_NAME, remote)
        body = json.loads((self.state / hf.MANIFEST_NAME).read_text(encoding="utf-8"))
        self.assertEqual(body["counts"]["items"], 2 * 4 * 3)  # 2 splits x 4 kinds x (2 episodes + plan.json)
        report = driver.verify_tier("T1", state=self.state, uploader=hub)
        self.assertTrue(report["pass"], report["problems"])

    def test_resume_uploads_nothing_twice_and_small_batches_split(self):
        hub = FakeHub()
        self.assertEqual(self.run_t1(hub, batch=1), 0)
        item_commits = len(hub.uploads) - 1  # the last one is the manifest
        self.assertEqual(item_commits, 24)
        again = FakeHub()
        again.repos = hub.repos
        self.assertEqual(self.run_t1(again), 0)
        self.assertEqual(len(again.uploads), 1)  # only the manifest again

    def test_a_test_episode_that_differs_from_the_seal_stops_before_upload(self):
        write(self.base / ROOTS["raw"] / "test" / "procthor10k-0.1.2-train-00002" / "data.bin", "changed")
        hub = FakeHub()
        self.assertEqual(self.run_t1(hub), 3)
        problems = json.loads((self.state / "problems.json").read_text(encoding="utf-8"))
        self.assertEqual(problems["problems"], ["test_seal_differs:raw:procthor10k-0.1.2-train-00002"])
        uploaded = hub.repos[("Jsun0632/vsmt-lean-s3-eval", "dataset")]
        self.assertNotIn("test/raw/procthor10k-0.1.2-train-00002.tar", uploaded)
        self.assertNotIn(hf.MANIFEST_NAME, uploaded)

    def test_verify_finds_a_corrupted_remote_file(self):
        hub = FakeHub()
        self.run_t1(hub)
        hub.repos[("Jsun0632/vsmt-lean-s3-eval", "dataset")]["test/raw/procthor10k-0.1.2-train-00001.tar"]["sha256"] = "0" * 64
        report = driver.verify_tier("T1", state=self.state, uploader=hub)
        self.assertEqual(report["problems"], ["remote_differs:test/raw/procthor10k-0.1.2-train-00001.tar"])

    def test_cards_upload_the_card_and_the_licence_per_repo(self):
        hub = FakeHub()
        cards = self.base / "cards"
        write(cards / "README_T1.md", "---\nlicense: cc-by-4.0\nviewer: false\n---\n# T1\n")
        write(cards / driver.LICENSE_FILE, "Apache License")
        hub.ensure_repo("Jsun0632/vsmt-lean-s3-eval", "dataset")
        refs = driver.upload_cards("T1", uploader=hub, staging=self.staging, cards_dir=cards)
        self.assertEqual(len(refs), 1)
        self.assertEqual(sorted(hub.repos[("Jsun0632/vsmt-lean-s3-eval", "dataset")]), ["LICENSE-APACHE-2.0", "README.md"])
        with self.assertRaisesRegex(hf.ReleaseError, "cards_missing:T2"):
            driver.upload_cards("T2", uploader=hub, staging=self.staging, cards_dir=cards)

    def test_the_committed_cards_carry_the_ruling_114_licences(self):
        for tier, licence in (("T0", "apache-2.0"), ("T1", "cc-by-4.0"), ("T2", "cc-by-4.0"), ("T3", "cc-by-4.0")):
            text = (driver.CARDS_DIR / f"README_{tier}.md").read_text(encoding="utf-8")
            self.assertIn(f"license: {licence}", text.split("---")[1])
            self.assertIn("No 3RScan data is redistributed", text)
            self.assertNotIn("Unity authoriz", text)
            if tier != "T0":
                self.assertIn("viewer: false", text.split("---")[1])
        self.assertEqual(hf.file_sha256(driver.CARDS_DIR / driver.LICENSE_FILE),
                         "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30")  # the apache.org text

    def test_stops_when_the_disk_is_short(self):
        hub = FakeHub()
        code = driver.run_tier("T1", base=str(self.base), state=self.state, staging=self.staging, batch_bytes=10 ** 9, uploader=hub,
                               free_bytes=lambda path: 1, commit="c" * 40)
        self.assertEqual(code, 3)


if __name__ == "__main__":
    unittest.main()
