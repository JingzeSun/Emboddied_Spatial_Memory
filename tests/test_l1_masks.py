from __future__ import annotations

import json
import unittest

import numpy as np

from vsmt.l1_masks import (
    KEEP_SUPPORTED_BORDER_REGIONS,
    REJECT_BORDER_REGIONS,
    L1MaskConfig,
    anonymize_instance_masks,
)


def config(*, minimum: int = 1, border: str = KEEP_SUPPORTED_BORDER_REGIONS) -> L1MaskConfig:
    return L1MaskConfig(
        minimum_visible_pixels=minimum,
        border_truncation_policy=border,
    )


class L1MaskTests(unittest.TestCase):
    def test_disconnected_visible_components_remain_one_region(self) -> None:
        mask = np.zeros((5, 5), dtype=np.uint8)
        mask[1, 1] = 1
        mask[3, 3] = 1
        result = anonymize_instance_masks({"Chair|private": mask}, config())
        self.assertEqual(len(result.regions), 1)
        self.assertEqual(result.regions[0].visible_pixel_count, 2)
        np.testing.assert_array_equal(result.regions[0].as_array(), mask.astype(bool))

    def test_instance_id_permutation_does_not_change_public_cache(self) -> None:
        left = np.zeros((4, 4), dtype=np.uint8)
        right = np.zeros((4, 4), dtype=np.uint8)
        left[1, 1] = 1
        right[2, 2] = 1
        first = anonymize_instance_masks({"Cup|7": left, "Cup|9": right}, config())
        second = anonymize_instance_masks({"opaque-b": left, "opaque-a": right}, config())
        self.assertEqual(first.public_cache(), second.public_cache())
        self.assertEqual(first.public_cache_sha256(), second.public_cache_sha256())
        self.assertNotEqual(
            first.private_instance_mapping_sha256,
            second.private_instance_mapping_sha256,
        )

    def test_input_enumeration_order_does_not_change_public_cache(self) -> None:
        first_mask = np.zeros((4, 4), dtype=np.uint8)
        second_mask = np.zeros((4, 4), dtype=np.uint8)
        first_mask[1, 2] = 1
        second_mask[2, 1] = 1
        first = anonymize_instance_masks({"a": first_mask, "b": second_mask}, config())
        second = anonymize_instance_masks({"b": second_mask, "a": first_mask}, config())
        self.assertEqual(first.public_cache_sha256(), second.public_cache_sha256())

    def test_distinct_instances_remain_distinct_regions(self) -> None:
        left = np.zeros((4, 5), dtype=np.uint8)
        right = np.zeros((4, 5), dtype=np.uint8)
        left[1:3, 1] = 1
        right[1:3, 3] = 1
        result = anonymize_instance_masks({"same-class-a": left, "same-class-b": right}, config())
        self.assertEqual([item.region_id for item in result.regions], [
            "region:0000", "region:0001",
        ])

    def test_small_region_failure_is_preserved_anonymously(self) -> None:
        mask = np.zeros((4, 4), dtype=np.uint8)
        mask[1, 1] = 1
        result = anonymize_instance_masks({"private-object": mask}, config(minimum=2))
        self.assertEqual(result.regions, ())
        self.assertEqual(len(result.rejected), 1)
        self.assertEqual(result.rejected[0].reason, "below_minimum_visible_pixels")

    def test_border_policy_is_explicit(self) -> None:
        mask = np.zeros((4, 4), dtype=np.uint8)
        mask[0, 2] = 1
        kept = anonymize_instance_masks({"private-object": mask}, config())
        rejected = anonymize_instance_masks(
            {"private-object": mask}, config(border=REJECT_BORDER_REGIONS),
        )
        self.assertEqual(len(kept.regions), 1)
        self.assertEqual(rejected.rejected[0].reason, "touches_image_border")

    def test_empty_instance_has_no_public_region_or_failure(self) -> None:
        result = anonymize_instance_masks(
            {"offscreen-private-object": np.zeros((3, 3), dtype=np.uint8)}, config(),
        )
        self.assertEqual(result.regions, ())
        self.assertEqual(result.rejected, ())

    def test_overlapping_instance_masks_fail_closed(self) -> None:
        left = np.zeros((3, 3), dtype=np.uint8)
        right = np.zeros((3, 3), dtype=np.uint8)
        left[1, 1] = 1
        right[1, 1] = 1
        with self.assertRaisesRegex(ValueError, "must not overlap"):
            anonymize_instance_masks({"a": left, "b": right}, config())

    def test_public_cache_contains_no_instance_identity(self) -> None:
        mask = np.zeros((4, 4), dtype=np.uint8)
        mask[1, 1] = 1
        result = anonymize_instance_masks({"Cup|private-secret": mask}, config())
        encoded = json.dumps(result.public_cache(), sort_keys=True)
        self.assertNotIn("Cup", encoded)
        self.assertNotIn("private-secret", encoded)


if __name__ == "__main__":
    unittest.main()
