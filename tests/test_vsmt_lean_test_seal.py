"""Ruling 103-1: the S3 test roots carry a marker, every data-reading entry refuses a path under it, and the seal recomputes.

Pinned: a pending or sealed marker covers the root and everything below it (an episode directory, a frame file) but not a sibling
root; the seal holds one tree digest per episode for each of the four roots plus their top-level files, its digest ignores only the
time it was written, and verify_seal names every changed file, extra or missing episode, changed root file, missing marker and
marker of another seal; build_seal refuses a raw root that does not hold exactly the manifest; the six entries that read caches,
episodes or geometry refuse a sealed root before reading anything, and every ops entry that takes such a root either calls the guard
or is one of the producers.  CPU only, about a second.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for item in (PROJECT_ROOT / "src", PROJECT_ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from vsmt import lean_test_seal as ts  # noqa: E402

HOUSES = ["procthor10k-0.1.2-train-00007", "procthor10k-0.1.2-train-00042", "procthor10k-0.1.2-train-00311"]
#: entries that write these roots, or only check their receipts and seals for run bookkeeping; every other ops entry that takes a
#: cache, episode or geometry root must call the guard
NOT_READERS = {"lean_s1_02a_pilot.py", "lean_s1_03_cache.py", "lean_s1_03_export.py", "lean_s1_04_object_geometry.py",
             "s2_06_manifest.py", "s3_02_manifest.py"}


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestMarkerAndGuard(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_a_marker_covers_its_root_and_everything_below_but_not_a_sibling(self) -> None:
        test_root, train_root = self.base / "caches" / "test", self.base / "caches" / "train"
        write(test_root / HOUSES[0] / "0000.cache.json.gz", "x")
        write(train_root / HOUSES[1] / "0000.cache.json.gz", "x")
        self.assertIsNone(ts.refusal([test_root, train_root], reader="r"))  # nothing sealed yet
        ts.write_marker(test_root, kind="sam2_cache", state=ts.STATE_PENDING)
        for path in (test_root, test_root / HOUSES[0], test_root / HOUSES[0] / "0000.cache.json.gz"):
            with self.assertRaises(ts.LeanTestSealError) as caught:
                ts.refuse_sealed([train_root, path], reader="node-audit run")
            self.assertTrue(str(caught.exception).startswith("sealed_test_root:node-audit run:"))
        self.assertIsNone(ts.refusal([train_root, train_root / HOUSES[1], None, ""], reader="r"))
        self.assertIn("ruling 103-1", ts.refusal([test_root], reader="r"))

    def test_a_root_one_level_above_a_test_root_is_refused(self) -> None:
        caches = self.base / "caches"
        test_root, train_root = caches / "test", caches / "train"
        write(test_root / HOUSES[0] / "0000.cache.json.gz", "x")
        write(train_root / HOUSES[1] / "0000.cache.json.gz", "x")
        write(caches / "README.txt", "a file beside the split roots")
        ts.write_marker(test_root, kind="sam2_cache", state=ts.STATE_PENDING)
        self.assertEqual(ts.sealed_marker(caches), test_root / ts.MARKER_NAME)  # ruling 104-6: one level down
        self.assertIn("sealed_test_root:", ts.refusal([caches], reader="r"))
        self.assertIsNone(ts.refusal([self.base], reader="r"))  # two levels above: not a root of test data by itself
        self.assertIsNone(ts.refusal([train_root, train_root / HOUSES[1]], reader="r"))  # a sibling stays readable

    def test_marker_states(self) -> None:
        with self.assertRaises(ts.LeanTestSealError):
            ts.write_marker(self.base, kind="raw", state=ts.STATE_SEALED)  # a sealed marker names its seal
        with self.assertRaises(ts.LeanTestSealError):
            ts.write_marker(self.base, kind="raw", state=ts.STATE_PENDING, seal_digest="d")
        with self.assertRaises(ts.LeanTestSealError):
            ts.write_marker(self.base, kind="cache", state=ts.STATE_PENDING)
        marker = json.loads(ts.write_marker(self.base, kind="raw", state=ts.STATE_SEALED, seal_digest="d").read_text(encoding="utf-8"))
        self.assertEqual((marker["kind"], marker["state"], marker["seal_sha256"]), ("raw", "sealed", "d"))


class TestSeal(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.roots = {kind: base / kind / "test" for kind in ts.SEAL_KINDS}
        for kind, root in self.roots.items():
            for index, house in enumerate(HOUSES):
                status = "failed" if index == 2 else "succeeded"
                if kind != "raw" and status == "failed":
                    continue  # a failed generation leaves no geometry or cache episode
                write(root / house / "receipt.json", json.dumps({"status": status}))
                write(root / house / "public" / "0000.frame.json", f"{kind}-{house}")
            write(root / "stage_receipt.json", json.dumps({"kind": kind}))
            ts.write_marker(root, kind=kind, state=ts.STATE_PENDING)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_seal_round_trip_and_every_kind_of_change(self) -> None:
        seal, digest = ts.seal_roots(self.roots, houses=HOUSES, tag="abc1234")
        self.assertEqual(seal["counts"], {"raw": {"episodes": 3, "succeeded": 2}, "geometry": {"episodes": 2, "succeeded": 2},
                                          "instance_cache": {"episodes": 2, "succeeded": 2}, "sam2_cache": {"episodes": 2, "succeeded": 2}})
        self.assertEqual(ts.verify_seal(seal), [])
        again = ts.build_seal(self.roots, houses=HOUSES, tag="abc1234")
        again["sealed_utc"] = "2099-01-01T00:00:00Z"
        self.assertEqual(ts.seal_sha256(again), digest)  # only the time differs
        write(self.roots["sam2_cache"] / HOUSES[0] / "public" / "0000.frame.json", "changed")
        write(self.roots["geometry"] / HOUSES[2] / "receipt.json", "{}")  # an episode that was not sealed
        write(self.roots["raw"] / "plan.resume.json", "{}")  # a new top-level file
        (self.roots["instance_cache"] / ts.MARKER_NAME).unlink()
        ts.write_marker(self.roots["raw"], kind="raw", state=ts.STATE_SEALED, seal_digest="0" * 64)
        self.assertEqual(sorted(ts.verify_seal(seal)), sorted([
            f"episode_digest_differs:sam2_cache:{HOUSES[0]}", "episode_set_differs:geometry", "root_files_differ:raw",
            "marker_not_this_seal:raw", "marker_missing:instance_cache"]))

    def test_the_raw_root_must_hold_exactly_the_manifest(self) -> None:
        with self.assertRaises(ts.LeanTestSealError) as caught:
            ts.build_seal(self.roots, houses=HOUSES + ["procthor10k-0.1.2-train-09999"], tag="t")
        self.assertEqual(str(caught.exception), "raw_test_root_does_not_hold_exactly_the_manifest")
        with self.assertRaises(ts.LeanTestSealError):
            ts.build_seal({k: v for k, v in self.roots.items() if k != "geometry"}, houses=HOUSES, tag="t")

    def test_tree_digest_is_order_free_and_content_bound(self) -> None:
        first = ts.tree_digest(self.roots["raw"] / HOUSES[0])
        self.assertEqual(first["files"], 2)
        write(self.roots["raw"] / HOUSES[0] / "public" / "0000.frame.json", "raw-" + HOUSES[0])  # same bytes rewritten
        self.assertEqual(ts.tree_digest(self.roots["raw"] / HOUSES[0]), first)
        write(self.roots["raw"] / HOUSES[0] / "public" / "0001.frame.json", "")
        self.assertNotEqual(ts.tree_digest(self.roots["raw"] / HOUSES[0])["sha256"], first["sha256"])


class TestEntriesRefuseSealedRoots(unittest.TestCase):
    """Each entry stops on the guard before it opens a contract, a cache or an episode."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.cache = base / "caches" / "test"
        self.episodes = base / "raw" / "test"
        self.geometry = base / "geometry" / "test"
        for root, kind in ((self.cache, "sam2_cache"), (self.episodes, "raw"), (self.geometry, "geometry")):
            ts.write_marker(root, kind=kind, state=ts.STATE_PENDING)
        self.episode = self.episodes / HOUSES[0]
        self.episode.mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def call(self, function, *, argv=None, args=None) -> tuple[int, str]:
        err = io.StringIO()
        with contextlib.redirect_stderr(err), mock.patch.object(sys, "argv", ["entry"] + (argv or [])):
            code = function(args) if args is not None else function()
        return code, err.getvalue()

    def common(self) -> list[str]:
        return ["--cache-root", str(self.cache), "--episode-id", HOUSES[0], "--arm", "TAF", "--config", "{}",
                "--descriptor", "reid_projection:vitb14", "--output-root", str(Path(self.tmp.name) / "out")]

    def assert_refused(self, code: int, err: str) -> None:
        self.assertEqual(code, 2, err)
        self.assertIn("sealed_test_root:", err)

    def test_s2_01_runner(self) -> None:
        import lean_s2_01_runner as entry

        self.assert_refused(*self.call(entry.main, argv=self.common() + ["--episode-root", str(self.episode)]))

    def test_s2_04_single_episode(self) -> None:
        import lean_s2_04_evaluate_episode as entry

        argv = self.common() + ["--episode-root", str(self.episode), "--geometry-root", str(self.geometry), "--mask-source", "sam2"]
        self.assert_refused(*self.call(entry.main, argv=argv))

    def test_s2_05_run_pass(self) -> None:
        import lean_s2_05_development as entry

        args = argparse.Namespace(cache_root=str(self.cache), geometry_root=str(self.geometry), episode_roots=f"{self.episodes},")
        self.assert_refused(*self.call(entry.cmd_run_pass, args=args))

    def test_node_audit_run(self) -> None:
        import lean_s2_05_node_audit as entry

        args = argparse.Namespace(cache_root=str(self.cache), episode_root=str(self.episode), geometry_root=str(self.geometry))
        self.assert_refused(*self.call(entry.run, args=args))

    def test_s1_04_diagnostics(self) -> None:
        import lean_s1_04_diagnostics as entry

        argv = ["--cache-root", str(self.cache), "--episode-roots", str(self.episodes), "--geometry-root", str(self.geometry),
                "--output-root", str(Path(self.tmp.name) / "out")]
        self.assert_refused(*self.call(entry.main, argv=argv))

    def test_ruling89_history_audit(self) -> None:
        import ruling89_history_audit as entry

        argv = ["run", "--cache-root", str(self.cache), "--episode-root", str(self.episode), "--episode-id", HOUSES[0], "--arm", "TAF",
                "--config", "{}", "--descriptor", "reid_projection:vitb14", "--mask-source", "sam2", "--output", "x.json"]
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = entry.main(argv)
        self.assert_refused(code, err.getvalue())

    def test_every_root_reading_entry_calls_the_guard(self) -> None:
        pattern = re.compile(r"""["'](--cache-root|--episode-roots?|--geometry-root)["']""")
        unguarded = []
        for path in sorted((PROJECT_ROOT / "ops" / "vsmt").glob("*.py")):
            text = path.read_text(encoding="utf-8")
            if pattern.search(text) and path.name not in NOT_READERS and "lean_test_seal.refus" not in text:
                unguarded.append(path.name)
        self.assertEqual(unguarded, [])


if __name__ == "__main__":
    unittest.main()
