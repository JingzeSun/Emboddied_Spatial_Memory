from __future__ import annotations

import json
import math
import unittest

import numpy as np

from vsmt.l1_entities import (
    AI2THOR_CAMERA_AXIS_Z,
    DINORegionConfig,
    L1EntityConstructionError,
    PublicGeometryConfig,
    backproject_public_entity_geometry,
    mask_patch_weights,
    materialize_l1_entity_observation,
    pool_dinov2_region_descriptor,
    preprocess_dinov2_rgb,
)
from vsmt.l1_masks import (
    KEEP_SUPPORTED_BORDER_REGIONS,
    L1MaskConfig,
    anonymize_instance_masks,
)


def descriptor_config(*, minimum_weight: float = 1.0) -> DINORegionConfig:
    return DINORegionConfig(
        image_height=224,
        image_width=224,
        patch_size_pixels=14,
        patch_token_dimension=384,
        minimum_total_patch_weight=minimum_weight,
        unit_norm_validation_tolerance=1e-5,
    )


def geometry_config(
    *, absolute: int = 32, fraction: float = 0.25,
) -> PublicGeometryConfig:
    return PublicGeometryConfig(
        depth_convention=AI2THOR_CAMERA_AXIS_Z,
        minimum_depth_m=0.05,
        maximum_depth_m=20.0,
        absolute_minimum_valid_depth_points=absolute,
        minimum_valid_depth_fraction=fraction,
    )


IDENTITY_POSE = {
    "position_m": [0.0, 0.0, 0.0],
    "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
}
UNIT_INTRINSICS = {"fx": 1.0, "fy": 1.0, "cx": 0.0, "cy": 0.0}


class L1EntityTests(unittest.TestCase):
    def test_rgb_preprocessing_is_exact_chw_float32(self) -> None:
        rgb = np.zeros((224, 224, 3), dtype=np.uint8)
        result = preprocess_dinov2_rgb(rgb, descriptor_config())
        self.assertEqual(result.shape, (3, 224, 224))
        self.assertEqual(result.dtype, np.float32)
        np.testing.assert_allclose(
            result[:, 0, 0],
            -np.asarray([0.485, 0.456, 0.406])
            / np.asarray([0.229, 0.224, 0.225]),
            rtol=1e-6,
        )

    def test_rgb_preprocessing_rejects_non_uint8(self) -> None:
        with self.assertRaisesRegex(ValueError, "RGB must be uint8"):
            preprocess_dinov2_rgb(
                np.zeros((224, 224, 3), dtype=np.float32), descriptor_config(),
            )

    def test_patch_weights_are_mask_fraction(self) -> None:
        mask = np.zeros((224, 224), dtype=np.bool_)
        mask[:7, :14] = True
        weights = mask_patch_weights(mask, descriptor_config())
        self.assertEqual(weights.shape, (16, 16))
        self.assertEqual(weights[0, 0], 0.5)
        self.assertEqual(float(weights.sum()), 0.5)

    def test_weighted_pool_is_unit_normalized_without_cls_token(self) -> None:
        mask = np.zeros((224, 224), dtype=np.bool_)
        mask[:14, :14] = True
        tokens = np.zeros((16, 16, 384), dtype=np.float32)
        tokens[0, 0, :2] = [3.0, 4.0]
        result = pool_dinov2_region_descriptor(tokens, mask, descriptor_config())
        self.assertEqual(result.total_patch_weight, 1.0)
        np.testing.assert_allclose(result.values[:2], [0.6, 0.8], atol=1e-7)
        self.assertAlmostEqual(np.linalg.norm(result.values), 1.0, places=6)

    def test_descriptor_support_failure_is_explicit(self) -> None:
        mask = np.zeros((224, 224), dtype=np.bool_)
        mask[:7, :14] = True
        tokens = np.ones((16, 16, 384), dtype=np.float32)
        with self.assertRaisesRegex(
            L1EntityConstructionError, "insufficient_dino_patch_support",
        ):
            pool_dinov2_region_descriptor(tokens, mask, descriptor_config())

    def test_zero_descriptor_failure_is_explicit(self) -> None:
        mask = np.zeros((224, 224), dtype=np.bool_)
        mask[:14, :14] = True
        tokens = np.zeros((16, 16, 384), dtype=np.float32)
        with self.assertRaisesRegex(
            L1EntityConstructionError, "zero_or_nonfinite_dino_descriptor",
        ):
            pool_dinov2_region_descriptor(tokens, mask, descriptor_config())

    def test_approved_depth_support_formula_uses_larger_requirement(self) -> None:
        config = geometry_config()
        self.assertEqual(config.required_valid_depth_points(40), 32)
        self.assertEqual(config.required_valid_depth_points(200), 50)

    def test_depth_is_camera_axis_z_not_euclidean_ray_length(self) -> None:
        mask = np.asarray([[True, True]], dtype=np.bool_)
        depth = np.asarray([[2.0, 2.0]], dtype=np.float32)
        geometry = backproject_public_entity_geometry(
            mask,
            depth,
            UNIT_INTRINSICS,
            IDENTITY_POSE,
            geometry_config(absolute=1, fraction=1.0),
        )
        np.testing.assert_allclose(geometry.centroid_m, [1.0, 0.0, 2.0])
        np.testing.assert_allclose(geometry.extent_m, [2.0, 0.0, 0.0])

    def test_camera_to_world_pose_transforms_visible_points(self) -> None:
        mask = np.asarray([[True]], dtype=np.bool_)
        depth = np.asarray([[2.0]], dtype=np.float32)
        half_turn_y = {
            "position_m": [1.0, 2.0, 3.0],
            "quaternion_xyzw": [0.0, 1.0, 0.0, 0.0],
        }
        geometry = backproject_public_entity_geometry(
            mask,
            depth,
            UNIT_INTRINSICS,
            half_turn_y,
            geometry_config(absolute=1, fraction=1.0),
        )
        np.testing.assert_allclose(geometry.centroid_m, [1.0, 2.0, 1.0])

    def test_quaternion_sign_does_not_change_geometry(self) -> None:
        mask = np.asarray([[True]], dtype=np.bool_)
        depth = np.asarray([[2.0]], dtype=np.float32)
        positive = backproject_public_entity_geometry(
            mask, depth, UNIT_INTRINSICS, IDENTITY_POSE,
            geometry_config(absolute=1, fraction=1.0),
        )
        negative = backproject_public_entity_geometry(
            mask,
            depth,
            UNIT_INTRINSICS,
            {"position_m": [0.0, 0.0, 0.0], "quaternion_xyzw": [0.0, 0.0, 0.0, -1.0]},
            geometry_config(absolute=1, fraction=1.0),
        )
        self.assertEqual(positive, negative)

    def test_invalid_depth_is_excluded_and_reliability_is_public_fraction(self) -> None:
        mask = np.ones((2, 2), dtype=np.bool_)
        depth = np.asarray([[1.0, np.nan], [21.0, 2.0]], dtype=np.float32)
        geometry = backproject_public_entity_geometry(
            mask,
            depth,
            UNIT_INTRINSICS,
            IDENTITY_POSE,
            geometry_config(absolute=1, fraction=0.5),
        )
        self.assertEqual(geometry.valid_depth_point_count, 2)
        self.assertEqual(geometry.required_valid_depth_point_count, 2)
        self.assertEqual(geometry.reliability, 0.5)

    def test_insufficient_depth_failure_is_explicit(self) -> None:
        mask = np.ones((8, 8), dtype=np.bool_)
        depth = np.full((8, 8), np.nan, dtype=np.float32)
        with self.assertRaisesRegex(
            L1EntityConstructionError, "insufficient_valid_depth_support",
        ):
            backproject_public_entity_geometry(
                mask, depth, UNIT_INTRINSICS, IDENTITY_POSE, geometry_config(),
            )

    def test_materialized_record_has_only_shared_public_region_fields(self) -> None:
        mask = np.zeros((224, 224), dtype=np.bool_)
        mask[:14, :14] = True
        region = anonymize_instance_masks(
            {"private-instance": mask},
            L1MaskConfig(196, KEEP_SUPPORTED_BORDER_REGIONS),
        ).regions[0]
        tokens = np.ones((16, 16, 384), dtype=np.float32)
        depth = np.ones((224, 224), dtype=np.float32)
        observation = materialize_l1_entity_observation(
            region,
            tokens,
            depth,
            {"fx": 112.0, "fy": 112.0, "cx": 111.5, "cy": 111.5},
            IDENTITY_POSE,
            descriptor_config(),
            geometry_config(),
        )
        record = observation.public_record()
        self.assertEqual(len(record["descriptor"]), 384)
        self.assertEqual(record["reliability"], 1.0)
        encoded = json.dumps(record, sort_keys=True)
        self.assertNotIn("private-instance", encoded)
        self.assertNotIn("instance_id", encoded)
        self.assertNotIn("class", encoded)


if __name__ == "__main__":
    unittest.main()
