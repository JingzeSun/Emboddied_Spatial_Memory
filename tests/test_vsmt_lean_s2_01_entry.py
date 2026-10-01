"""D-224 / ruling 84-1 (b), landed under ruling 100-1 (i): the entries pick the ReID head of the episode's mask source.

Pinned: S0-03 pins one head digest per mask source (the main table's instance-segmentation head and the SAM 2.1 table's
SAM2 head) and refuses an unregistered source; an entry reads the mask source from the episode seal (a seal without a
mask_source field is sam2, the pre-ruling-72 SAM2 bytes); the projector is built against the head of that source, so the
instance-segmentation weights are refused for a SAM2 episode and the other way round; the frozen baseline descriptor needs
no weights.  The three entries (S2-01, S2-04, node audit) share these two helpers.  CPU only, seconds.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for item in (PROJECT_ROOT / "src", PROJECT_ROOT / "tests", PROJECT_ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import lean_s2_01_runner as s2_01  # noqa: E402
from vsmt import lean_assignment as la  # noqa: E402
from vsmt import lean_frontend_cache as fc  # noqa: E402
from vsmt import lean_runner as lr  # noqa: E402

INSTANCE = "5cea91cf77901f1eb38e5942ee12a2afbe14e11ba1475bd2957e1cbfe3659a88"
SAM2 = "f6fc67e5f365a4f6d375d6aa16afe15cb0d9769879aa0cc1ab84ff6de9b65073"


class TestHeadPerMaskSource(unittest.TestCase):
    def test_one_pinned_digest_per_registered_mask_source(self) -> None:
        self.assertEqual(tuple(la.REID_WEIGHTS_SHA256_BY_MASK_SOURCE), fc.MASK_SOURCES)
        self.assertEqual(la.reid_weights_sha256_for("simulator_instance_masks"), INSTANCE)
        self.assertEqual(la.reid_weights_sha256_for("sam2"), SAM2)
        self.assertEqual(la.SELECTED_REID_WEIGHTS_SHA256, INSTANCE)  # the main table's head is unchanged
        with self.assertRaises(la.LeanAssignmentError):
            la.reid_weights_sha256_for("sam")


class TestEntryHelpers(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def seal(self, **fields) -> Path:
        (self.dir / "episode_seal.json").write_text(json.dumps({"payload_sha256": "0" * 64, **fields}), encoding="utf-8")
        return self.dir

    def test_the_seal_names_the_source_and_a_sam2_seal_names_none(self) -> None:
        self.assertEqual(s2_01.sealed_mask_source_of(self.seal()), "sam2")
        self.assertEqual(s2_01.sealed_mask_source_of(self.seal(mask_source="simulator_instance_masks")), "simulator_instance_masks")
        with self.assertRaises(fc.LeanFrontendCacheError):
            s2_01.sealed_mask_source_of(self.seal(mask_source="sam"))
        with self.assertRaises(s2_01.EntryRefusal):
            s2_01.sealed_mask_source_of(self.dir / "missing")

    def test_the_projector_is_checked_against_the_head_of_that_source(self) -> None:
        weights = self.dir / "reid_head_vitb14.json"
        weights.write_text(json.dumps({"sha256": SAM2}), encoding="utf-8")
        seen = []

        def projector(payload, *, expected_sha256, device):
            seen.append(expected_sha256)
            return lambda rows: rows

        with mock.patch.object(s2_01.lr, "descriptor_projector", side_effect=projector):
            _, digest = s2_01.reid_projector(la.SELECTED_DESCRIPTOR, str(weights), mask_source="sam2", device="cpu")
            s2_01.reid_projector(la.SELECTED_DESCRIPTOR, str(weights), mask_source="simulator_instance_masks", device="cpu")
        self.assertEqual(seen, [SAM2, INSTANCE])
        self.assertEqual(digest, SAM2)

    def test_the_real_projector_refuses_the_other_sources_head(self) -> None:
        weights = self.dir / "reid_head_vitb14.json"
        weights.write_text(json.dumps({"sha256": INSTANCE}), encoding="utf-8")
        with self.assertRaises(lr.LeanRunnerError) as caught:  # refused on the digest, before the head is loaded
            s2_01.reid_projector(la.SELECTED_DESCRIPTOR, str(weights), mask_source="sam2", device="cpu")
        self.assertEqual(str(caught.exception), "reid_weights_digest_not_the_frozen_one")

    def test_the_baseline_needs_no_weights_and_the_projection_does(self) -> None:
        self.assertEqual(s2_01.reid_projector(la.FROZEN_DESCRIPTOR_BASELINE, None, mask_source="sam2", device="cpu"), (None, None))
        with self.assertRaises(s2_01.EntryRefusal):
            s2_01.reid_projector(la.SELECTED_DESCRIPTOR, None, mask_source="sam2", device="cpu")


if __name__ == "__main__":
    unittest.main()
