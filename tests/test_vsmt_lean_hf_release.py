"""S3-05R (ruling 110): deterministic episode tars, release items, checks against the S3-02 seal and cache exports, batches."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for item in (ROOT / "src", ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from vsmt import lean_hf_release as hf  # noqa: E402
from vsmt import lean_test_seal as ts  # noqa: E402


def write(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode("utf-8") if isinstance(data, str) else data)


def episode(root: Path, name: str, *, reverse: bool = False) -> Path:
    files = [("receipt.json", '{"status": "succeeded", "episode_seal_sha256": "abc"}'), ("frames/0001.npz", b"\x00\x01" * 50),
             ("frames/0000.npz", b"\x02" * 70), ("meta.json", "{}")]
    for relative, data in (reversed(files) if reverse else files):
        write(root / name / relative, data)
    return root / name


class DeterministicTarTest(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp())

    def test_same_content_same_bytes_whatever_times_modes_and_order(self):
        a = episode(self.base / "a", "ep-1")
        b = episode(self.base / "b", "ep-1", reverse=True)
        os.utime(b / "meta.json", (1_000_000, 1_000_000))
        os.chmod(b / "meta.json", 0o600)
        hf.write_deterministic_tar(a, self.base / "a.tar")
        hf.write_deterministic_tar(b, self.base / "b.tar")
        self.assertEqual(hf.file_sha256(self.base / "a.tar"), hf.file_sha256(self.base / "b.tar"))

    def test_different_content_different_bytes(self):
        a = episode(self.base / "a", "ep-1")
        b = episode(self.base / "b", "ep-1")
        write(b / "meta.json", "{ }")
        hf.write_deterministic_tar(a, self.base / "a.tar")
        hf.write_deterministic_tar(b, self.base / "b.tar")
        self.assertNotEqual(hf.file_sha256(self.base / "a.tar"), hf.file_sha256(self.base / "b.tar"))

    def test_extract_restores_the_tree_digest_and_equals_the_seal_algorithm(self):
        a = episode(self.base / "src", "ep-1")
        hf.write_deterministic_tar(a, self.base / "ep.tar")
        restored = hf.safe_extract(self.base / "ep.tar", self.base / "dst")
        self.assertEqual(restored, self.base / "dst" / "ep-1")
        self.assertEqual(hf.tree_digest(restored), hf.tree_digest(a))
        self.assertEqual(hf.tree_digest(a), ts.tree_digest(a))  # nothing excluded: the seal's own digest

    def test_excluded_files_are_neither_tarred_nor_digested(self):
        a = episode(self.base / "src", "ep-1")
        write(a / "half.json.tmp", "x")
        write(a / ".lock", "")
        hf.write_deterministic_tar(a, self.base / "ep.tar")
        restored = hf.safe_extract(self.base / "ep.tar", self.base / "dst")
        self.assertFalse((restored / "half.json.tmp").exists())
        self.assertEqual(hf.tree_digest(a), hf.tree_digest(restored))

    def test_extract_refuses_an_existing_target(self):
        a = episode(self.base / "src", "ep-1")
        hf.write_deterministic_tar(a, self.base / "ep.tar")
        hf.safe_extract(self.base / "ep.tar", self.base / "dst")
        with self.assertRaisesRegex(hf.ReleaseError, "restore_target_exists"):
            hf.safe_extract(self.base / "ep.tar", self.base / "dst")


class ItemsAndChecksTest(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp())
        self.root = self.base / "vsmt_outputs" / "s3-02-x" / "test"
        for name in ("ep-1", "ep-2"):
            episode(self.root, name)
        write(self.root / "s3_receipt.json", "{}")
        write(self.root / ts.MARKER_NAME, "{}")
        write(self.root / ".lock", "")
        (self.root / "hosts").mkdir()

    def group(self, checks=()):
        return hf.Group("u/eval", "dataset", "test/raw", str(self.root), "vsmt_outputs/s3-02-x/test", "children", tuple(checks))

    def test_children_mode_tars_dirs_and_keeps_root_files(self):
        items = hf.items_of(self.group())
        self.assertEqual([(i.kind, i.path_in_repo) for i in items],
                         [("file", f"test/raw/_root/{ts.MARKER_NAME}"), ("tar", "test/raw/ep-1.tar"), ("tar", "test/raw/ep-2.tar"),
                          ("file", "test/raw/_root/s3_receipt.json")])
        self.assertEqual(items[1].restore_path, "vsmt_outputs/s3-02-x/test/ep-1")

    def test_files_mode_lists_every_file_recursively(self):
        group = hf.Group("u/m", "model", "exports", str(self.root / "ep-1"), "vsmt_outputs/exports", "files")
        self.assertEqual([i.path_in_repo for i in hf.items_of(group)],
                         ["exports/frames/0000.npz", "exports/frames/0001.npz", "exports/meta.json", "exports/receipt.json"])

    def test_build_records_sha_bytes_and_tree(self):
        item = hf.items_of(self.group())[1]
        record = hf.build_item(item, self.base / "staging")
        self.assertEqual(record["sha256"], hf.file_sha256(self.base / "staging" / "test/raw/ep-1.tar"))
        self.assertEqual(record["tree"], ts.tree_digest(self.root / "ep-1"))
        restored = hf.safe_extract(self.base / "staging" / "test/raw/ep-1.tar", self.base / "restored")
        self.assertEqual(hf.verify_restored(record, restored), [])
        (restored / "meta.json").write_text("changed", encoding="utf-8")
        self.assertEqual(hf.verify_restored(record, restored), ["tree_differs:test/raw/ep-1.tar"])

    def test_test_seal_check(self):
        seal = {"kinds": {kind: {"episodes": {}, "root_files": {}} for kind in ts.SEAL_KINDS}}
        seal["kinds"]["raw"]["episodes"] = {"ep-1": ts.tree_digest(self.root / "ep-1")}
        seal["kinds"]["raw"]["root_files"] = {"s3_receipt.json": {"bytes": 2, "sha256": ts.file_sha256(self.root / "s3_receipt.json")}}
        items = {i.name: i for i in hf.items_of(self.group(("test_seal",)))}
        for name in ("ep-1", "s3_receipt.json", ts.MARKER_NAME):
            record = hf.build_item(items[name], self.base / "staging")
            self.assertEqual(hf.check_item(items[name], record, seal=seal), [], name)
        record = hf.build_item(items["ep-2"], self.base / "staging")  # not in this seal: a difference
        self.assertEqual(hf.check_item(items["ep-2"], record, seal=seal), ["test_seal_differs:raw:ep-2"])

    def test_cache_export_check(self):
        group = hf.Group("u/eval", "dataset", "validation/instance_cache", str(self.root), "x", "children", ("cache_export",))
        item = [i for i in hf.items_of(group) if i.name == "ep-1"][0]
        record = hf.build_item(item, self.base / "staging")
        self.assertEqual(hf.check_item(item, record, cache_exports={"instance_cache": {"ep-1": "abc"}}), [])
        self.assertEqual(hf.check_item(item, record, cache_exports={"instance_cache": {"ep-1": "zzz"}}),
                         ["cache_export_differs:instance_cache:ep-1"])
        export = {"episodes": [{"episode_id": "ep-1", "status": "succeeded", "episode_seal_sha256": "abc"},
                               {"episode_id": "ep-9", "status": "failed", "episode_seal_sha256": None}]}
        self.assertEqual(hf.cache_export_expectations(export), {"ep-1": "abc"})

    def test_tiers_cover_the_four_repos(self):
        tiers = hf.tiers("/b")
        self.assertEqual(sorted(tiers), ["T0", "T1", "T2", "T3"])
        self.assertEqual({g.repo for g in tiers["T1"]}, {"Jsun0632/vsmt-lean-s3-eval"})
        self.assertEqual(len(tiers["T1"]), 8)
        self.assertTrue(all("test_seal" in g.checks for g in tiers["T1"] if g.prefix.startswith("test/")))
        self.assertTrue(all(g.prefix.startswith("train/") for g in tiers["T3"]))
        self.assertEqual({g.repo_type for g in tiers["T0"]}, {"model"})


class ThreeRScanGuardTest(unittest.TestCase):
    """Ruling 114-3: nothing from 3RScan is released; the S3-07 metric JSONs stay allowed."""

    def setUp(self):
        self.base = Path(tempfile.mkdtemp())

    def test_s3_07_data_roots_are_refused(self):
        for name in ("s3-07-4e7a206", "s3-07-run-4e7a206", "S3-07-geometry-x", "scans_3RScan"):
            root = self.base / name
            episode(root, "ep-1")
            group = hf.Group("u/x", "dataset", "x", str(root), "x", "children")
            with self.assertRaisesRegex(hf.ReleaseError, "three_rscan_not_released"):
                hf.items_of(group)

    def test_an_s3_07_child_directory_is_refused(self):
        root = self.base / "caches"
        episode(root, "s3-07-d12707f")
        with self.assertRaisesRegex(hf.ReleaseError, "three_rscan_not_released"):
            hf.items_of(hf.Group("u/x", "dataset", "x", str(root), "x", "children"))
        with self.assertRaisesRegex(hf.ReleaseError, "three_rscan_not_released"):
            hf.items_of(hf.Group("u/x", "model", "x", str(root), "x", "files"))

    def test_the_s3_07_metric_exports_are_allowed(self):
        exports = self.base / "exports"
        write(exports / "vsmt_lean_s3_07_statistics_aa94373.json", "{}")
        write(exports / "vsmt_lean_s3_05_statistics_8d58475.json", "{}")
        names = [i.name for i in hf.items_of(hf.Group("u/m", "model", "exports", str(exports), "e", "files"))]
        self.assertEqual(names, ["vsmt_lean_s3_05_statistics_8d58475.json", "vsmt_lean_s3_07_statistics_aa94373.json"])

    def test_the_real_tiers_hold_no_3rscan_root(self):
        for groups in hf.tiers("/root/autodl-tmp").values():
            for group in groups:
                self.assertFalse(hf.three_rscan_source(Path(group.root)), group.root)


class BatchesAndManifestTest(unittest.TestCase):
    def test_batches_respect_the_limit(self):
        self.assertEqual(hf.batches([("a", 4), ("b", 4), ("c", 4), ("d", 20), ("e", 1)], 10), [["a", "b"], ["c"], ["d"], ["e"]])
        self.assertEqual(hf.batches([], 10), [])

    def test_manifest_digest_ignores_write_time_only(self):
        records = [{"path_in_repo": "b", "bytes": 1}, {"path_in_repo": "a", "bytes": 2}]
        one = hf.manifest("T1", records, code_commit="c", repos=[("u/r", "dataset")], problems=[], written_utc="t1")
        two = hf.manifest("T1", list(reversed(records)), code_commit="c", repos=[("u/r", "dataset")], problems=[], written_utc="t2")
        self.assertEqual(one["manifest_sha256"], two["manifest_sha256"])
        self.assertEqual([r["path_in_repo"] for r in one["items"]], ["a", "b"])
        self.assertEqual(one["counts"], {"items": 2, "bytes": 3})


if __name__ == "__main__":
    unittest.main()
