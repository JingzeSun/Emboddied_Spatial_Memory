"""Tests for the trusted materializer digest chain."""

import copy
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vsmt.vm04_materializer_receipt import (
    MaterializerReceiptError,
    make_materializer_receipt,
    validate_materializer_receipt,
)


SHA = "0" * 64
SEQUENCE_DIGESTS = {
    "public_frame_context_manifest_sha256": SHA,
    "causal_prior_receipt_sha256": SHA,
    "prior_memory_sha256": SHA,
}


def _row(index):
    return {
        "observation_index": index,
        "raw_public_frame_sha256": "1" * 64,
        "raw_private_masks_sha256": "2" * 64,
        "public_packet_sha256": "3" * 64,
        "private_crosswalk_sha256": "4" * 64,
    }


class MaterializerReceiptTests(unittest.TestCase):
    def test_binds_contiguous_public_and_private_outputs(self):
        receipt = make_materializer_receipt(
            [_row(0), _row(1)], episode_id="episode:001",
            route_plan_sha256=SHA, raw_episode_manifest_sha256=SHA,
            materializer_code_sha256=SHA, materializer_config_sha256=SHA,
            **SEQUENCE_DIGESTS,
        )
        self.assertEqual(validate_materializer_receipt(receipt), receipt)
        self.assertFalse(receipt["deployment_reader_may_open_private_crosswalks"])
        schema = json.loads((
            ROOT / "schemas/vsmt_vm04_materializer_receipt.schema.json"
        ).read_text(encoding="utf-8"))
        self.assertEqual(
            set(receipt),
            set(schema["required"]),
        )

    def test_rejects_gap_in_frame_bindings(self):
        with self.assertRaisesRegex(MaterializerReceiptError, "contiguous"):
            make_materializer_receipt(
                [_row(0), _row(2)], episode_id="episode:001",
                route_plan_sha256=SHA, raw_episode_manifest_sha256=SHA,
                materializer_code_sha256=SHA, materializer_config_sha256=SHA,
                **SEQUENCE_DIGESTS,
            )

    def test_rejects_tampered_crosswalk_binding(self):
        receipt = make_materializer_receipt(
            [_row(0)], episode_id="episode:001",
            route_plan_sha256=SHA, raw_episode_manifest_sha256=SHA,
            materializer_code_sha256=SHA, materializer_config_sha256=SHA,
            **SEQUENCE_DIGESTS,
        )
        changed = copy.deepcopy(receipt)
        changed["frames"][0]["private_crosswalk_sha256"] = "5" * 64
        with self.assertRaisesRegex(MaterializerReceiptError, "digest mismatch"):
            validate_materializer_receipt(changed)


if __name__ == "__main__":
    unittest.main()
