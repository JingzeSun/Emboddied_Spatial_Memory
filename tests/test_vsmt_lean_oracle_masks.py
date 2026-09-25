"""D-224 / S2-05 tests: the oracle-frontend probe's mask writer produces S1-03 recovered-mask files.

Pinned on a synthetic private episode (three frames, uint16 instance images, a private mapping):
every labelled instance with at least the frontend minimum of pixels becomes one mask, a tiny one
is dropped, more than the frontend maximum keeps the largest and is counted as capped, the files
read back through the S1-03 generator's reader with digests the frontend recomputes from the
pixels, and the receipt names the source as diagnostic.  CPU only, seconds.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for item in (PROJECT_ROOT / "src", PROJECT_ROOT / "tests", PROJECT_ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import lean_s2_05_oracle_masks as oracle  # noqa: E402
from vsmt import lean_frontend_cache as fc  # noqa: E402


def synthetic_episode(root: Path, *, frames: int = 3, side: int = 64, instances: int = 5) -> None:
    from PIL import Image

    private = root / "private"
    private.mkdir(parents=True)
    (root / "receipt.json").write_text(json.dumps({"status": "succeeded"}), encoding="utf-8")
    mapping = {f"Mug|surface|{i}|{i}": i for i in range(1, instances + 1)}
    for index in range(frames):
        image = np.zeros((side, side), dtype=np.uint16)
        for i in range(1, instances + 1):
            size = 4 + 6 * i  # 10, 16, 22, 28, 34 pixels a side: 100 px (below 196), 256, 484, 784, 1156
            image[2:2 + size, 2 + 8 * (i - 1) + index:2 + 8 * (i - 1) + index + size // 2 + 1] = i
        Image.fromarray(image).save(private / f"{index:04d}.instance.png")
        (private / f"{index:04d}.frame.json").write_text(json.dumps({
            "frame_digest": f"d{index}", "instance_mask_path": f"{index:04d}.instance.png",
            "object_id_to_entity_id": mapping, "observation_index": index}), encoding="utf-8")


class TestOracleMasks(unittest.TestCase):
    def test_masks_read_back_through_the_generator_reader_with_recomputed_digests(self):
        import lean_s1_03_cache as generator

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "procthor10k-0.1.2-train-99999"
            synthetic_episode(root)
            out = Path(tmp) / "masks" / root.name
            receipt = oracle.write_episode(root, out, commit="test")
            self.assertEqual(receipt["status"], "succeeded")
            self.assertEqual(receipt["frames"], 3)
            self.assertTrue(receipt["diagnostic_only"])
            self.assertEqual(receipt["capped_frames"], [])
            recovery = json.loads((out / "mask_recovery_receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(recovery["source"], oracle.SOURCE)
            for index in range(3):
                loaded = generator.read_masks_file(out / f"{index:04d}{oracle.MASK_FILE_SUFFIX}")
                masks = loaded["masks"]
                self.assertEqual(masks.shape[1:], (64, 64))
                self.assertGreaterEqual(masks.shape[0], 1)
                for n in range(masks.shape[0]):
                    self.assertGreaterEqual(int(masks[n].sum()), fc.MINIMUM_VISIBLE_PIXELS)
                    self.assertEqual(fc.mask_sha256_of(masks[n]), loaded["mask_sha256"][n])
                # the generator's own reader re-digests too and must accept the file
                generator.recovered_masks(out / f"{index:04d}{oracle.MASK_FILE_SUFFIX}", (64, 64))

    def test_small_instances_are_dropped_and_too_many_are_capped_largest_first(self):
        image = np.zeros((40, 40), dtype=np.uint16)
        mapping = {}
        for i in range(1, 8):
            image[0:20, (i - 1) * 5:(i - 1) * 5 + 4] = i  # 80 px each
            mapping[f"Obj|{i}"] = i
        image[25:40, 0:40] = 9  # 600 px, labelled
        mapping["Big|9"] = 9
        image[22:24, 0:40] = 10  # 80 px, unlabelled: never a mask
        masks, info = oracle.instance_masks(image, mapping, minimum_pixels=50, maximum=3)
        self.assertEqual(info["eligible"], 8)
        self.assertEqual(info["kept"], 3)
        self.assertTrue(info["capped"])
        self.assertEqual(int(masks[0].sum()), 600)  # largest first
        masks, info = oracle.instance_masks(image, mapping, minimum_pixels=196, maximum=64)
        self.assertEqual([int(m.sum()) for m in masks], [600])
        self.assertFalse(info["capped"])


if __name__ == "__main__":
    unittest.main()
