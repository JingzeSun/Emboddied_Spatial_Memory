"""D-224 / S2-04 tests: the episode entry closes its streams before it re-reads the nuisance file (LOG-256).

Pinned on rows shaped like the real nuisance rows with enough entropy to push the compressed output
past the gzip write buffers: finish_streams closes the three streams first and then re-reads every
row written (the probes see them all); reading the nuisance file while its writer is still open is
wrong in both regimes the calibration pass hit (nothing on disk yet gives zero rows, a partial member
on disk raises EOFError); a re-read row count that differs from the rows written is refused. CPU only,
seconds.
"""
from __future__ import annotations

import gzip
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for item in (PROJECT_ROOT / "src", PROJECT_ROOT / "tests", PROJECT_ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import lean_s2_04_evaluate_episode as entry  # noqa: E402

STATUSES = ("labelled", "identity_ambiguous", "duplicate_of_labelled", "birth", "recall_miss")
CACHE_PATH = "/root/autodl-tmp/vsmt_caches/lean-s1-03-154776d/procthor10k-0.1.2-train-00406"


def nuisance_rows(frames: int, seed: int) -> list[dict]:
    """Rows shaped like the entry writes them; random statuses and counts keep the compressed size honest."""

    rng = random.Random(seed)
    rows = []
    for tick in range(1, frames + 1):
        meta = {"path": CACHE_PATH, "seed": 20260920, "house_index": 406, "frame_index": tick - 1}
        association = [{**meta, "association_status": rng.choice(STATUSES), "association_target_is_birth": rng.random() < 0.1}
                       for _ in range(rng.randint(4, 16))]
        existence = [{**meta, "existence_status": rng.choice(("present", "gone", "identity_ambiguous"))} for _ in range(rng.randint(0, 2))]
        rows.append({"tick": tick, "association": association, "existence": existence})
    return rows


class TestFinishStreams(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.rows = nuisance_rows(1400, seed=7)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def streams(self):
        return tuple(entry.Stream(self.dir / name) for name in ("labels.jsonl.gz", "training_records.jsonl.gz", "nuisance.jsonl.gz"))

    def test_close_before_reread_returns_every_row_past_the_gzip_buffers(self):
        labels, training, nuisance = self.streams()
        for row in self.rows:
            labels.write({"tick": row["tick"], "frame_index": row["tick"] - 1})
            training.write({"tick": row["tick"], "targets": []})
            nuisance.write(row)
        result = entry.finish_streams(labels, training, nuisance)
        self.assertGreater(result["nuisance_file_bytes"], 32 * 1024, "the fixture must exceed the write buffers to be meaningful")
        self.assertEqual(result["nuisance_rows_written"], len(self.rows))
        self.assertEqual(result["nuisance_probes"]["association_rows"], sum(len(r["association"]) for r in self.rows))
        self.assertEqual(result["nuisance_probes"]["existence_rows"], sum(len(r["existence"]) for r in self.rows))
        self.assertIsNotNone(result["nuisance_probes"]["association"])
        with gzip.open(self.dir / "nuisance.jsonl.gz", "rb") as handle:
            on_disk = [json.loads(line) for line in handle.read().decode("utf-8").splitlines() if line]
        self.assertEqual(on_disk, self.rows)
        for name in ("labels_file_bytes", "training_file_bytes"):
            self.assertGreater(result[name], 0)

    def test_reading_before_close_is_wrong_in_both_regimes(self):
        small = entry.Stream(self.dir / "small.jsonl.gz")
        for row in self.rows[:40]:
            small.write(row)
        self.assertEqual(entry._reread(small.path), [], "nothing has reached the disk yet: the probes would see zero rows")
        small.close()
        large = entry.Stream(self.dir / "large.jsonl.gz")
        for row in self.rows:
            large.write(row)
        with self.assertRaises(EOFError):
            entry._reread(large.path)
        large.close()
        self.assertEqual(len(entry._reread(large.path)), len(self.rows))

    def test_row_count_mismatch_is_refused(self):
        labels, training, nuisance = self.streams()
        for row in self.rows[:10]:
            nuisance.write(row)
        nuisance.rows += 1  # a writer that lost a row must not produce a receipt
        with self.assertRaisesRegex(RuntimeError, "nuisance_stream_reread_mismatch"):
            entry.finish_streams(labels, training, nuisance)


if __name__ == "__main__":
    unittest.main()
