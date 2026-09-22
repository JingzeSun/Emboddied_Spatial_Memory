"""The S1-03 runner's ``--recover-masks`` pass, model-free parts: the packed mask file round-trips
with its digests in cache fragment order, the digest-for-digest comparison against a sealed frame
refuses any mismatch, reordering or count difference, and the pass is guarded by the S1-04
``fragment_mask_recovery`` bit.  SAM is never loaded here.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT / "src", PROJECT_ROOT / "ops" / "vsmt"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import lean_s1_03_cache as runner  # noqa: E402
from cpmt.hashing import canonical_json  # noqa: E402

S1_04_CONTRACT = PROJECT_ROOT / "configs" / "vsmt" / "lean_s1_04_frontend_diagnostics_v1.json"


def mask_digest(binary: np.ndarray) -> str:
    array = np.ascontiguousarray(binary.astype(np.uint8))
    payload = [int(array.shape[0]), int(array.shape[1]), *array.reshape(-1).tolist()]
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


class MaskFileTests(unittest.TestCase):
    def test_masks_round_trip_in_order_with_their_digests(self) -> None:
        rng = np.random.default_rng(48)
        masks = [rng.random((20, 30)) > 0.5 for _ in range(3)]
        shas = [mask_digest(m) for m in masks]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / f"0007{runner.MASK_FILE_SUFFIX}"
            written = runner.write_masks_file(path, masks, shas, shape=(20, 30))
            self.assertGreater(written, 0)
            back = runner.read_masks_file(path)
            self.assertEqual(back["mask_sha256"], shas)
            self.assertEqual(back["masks"].shape, (3, 20, 30))
            for original, restored in zip(masks, back["masks"]):
                np.testing.assert_array_equal(original, restored)
            # digests recomputed from the restored masks are the same ones the sealed frame carries
            self.assertEqual([mask_digest(m) for m in back["masks"]], shas)
            empty = Path(directory) / f"0008{runner.MASK_FILE_SUFFIX}"
            runner.write_masks_file(empty, [], [], shape=(20, 30))
            self.assertEqual(runner.read_masks_file(empty)["masks"].shape, (0, 20, 30))

    def test_a_mask_of_the_wrong_shape_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(runner.CacheFailure):
                runner.write_masks_file(Path(directory) / "x.npz", [np.zeros((4, 4), dtype=bool)], ["a" * 64], shape=(5, 5))


class MatchTests(unittest.TestCase):
    def test_only_an_identical_digest_sequence_matches(self) -> None:
        rng = np.random.default_rng(49)
        arrays = [rng.random((32, 32)) > 0.5 for _ in range(3)]  # about 512 px each, above the 196 px floor
        admitted = runner.fc.admit_proposals([runner.anonymous(a, i) for i, a in enumerate(arrays)])
        self.assertEqual(len(admitted), 3)
        frame = {"fragments": [{"mask_sha256": m.mask_sha256} for m in admitted]}
        self.assertTrue(runner.match_recovered_masks(frame, admitted)["matched"])
        reordered = list(reversed(admitted))
        result = runner.match_recovered_masks(frame, reordered)
        self.assertFalse(result["matched"])
        self.assertEqual(result["mismatched_positions"], [0, 2])
        fewer = runner.match_recovered_masks(frame, admitted[:2])
        self.assertFalse(fewer["matched"])
        self.assertEqual((fewer["cache_count"], fewer["recovered_count"], fewer["mismatched_positions"]), (3, 2, [2]))
        changed = dict(frame)
        changed["fragments"] = [{"mask_sha256": "0" * 64}] + frame["fragments"][1:]
        self.assertEqual(runner.match_recovered_masks(changed, admitted)["mismatched_positions"], [0])


class GuardTests(unittest.TestCase):
    def test_the_recovery_bit_is_closed_in_the_s1_04_contract(self) -> None:
        contract = json.loads(S1_04_CONTRACT.read_text(encoding="utf-8"))
        self.assertIs(contract["authorization"]["fragment_mask_recovery"], False)
        self.assertEqual(runner.RECOVERY_FAILURE_REASONS[0], "fragment_mask_mismatch")
        self.assertEqual(runner.S1_04_CONTRACT_PATH, S1_04_CONTRACT)


if __name__ == "__main__":
    unittest.main()
