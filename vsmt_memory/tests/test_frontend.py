"""Front end on a synthetic frame: admission, frozen geometry, mask mapping and the depth view (no downloads)."""

from __future__ import annotations

import unittest

import numpy as np

from vsmt_memory.conventions import CameraIntrinsics, CameraPose
from vsmt_memory.frontend import FrontEndError, build_frame, frozen_configs
from vsmt import lean_frontend_cache as fc
from vsmt import lean_runner as lr
from vsmt.l1_entities import backproject_public_entity_geometry

SIZE = 224
INTRINSICS = CameraIntrinsics(fx=112.0, fy=112.0, cx=111.5, cy=111.5, width=SIZE, height=SIZE)
POSE = CameraPose(position_m=(0.5, 1.2, -0.3), quaternion_xyzw=(0.2588190451, 0.0, 0.0, 0.9659258263))


def tokens(_: np.ndarray) -> np.ndarray:
    """Stand-in patch tokens (the pooling and normalisation are the frozen ones; DINOv2 itself is not tested here)."""

    return np.random.default_rng(3).standard_normal((16, 16, 768)).astype(np.float32)


def scene() -> tuple[np.ndarray, np.ndarray, list[np.ndarray]]:
    depth = np.full((SIZE, SIZE), 3.0, dtype=np.float32)
    depth[60:120, 40:100] = 1.5
    depth[150:200, 150:210] = 2.2
    rgb = np.zeros((SIZE, SIZE, 3), dtype=np.uint8)
    masks = [np.zeros((SIZE, SIZE), dtype=bool) for _ in range(4)]
    masks[0][60:120, 40:100] = True          # a box
    masks[1][150:200, 150:210] = True        # another box
    masks[2][5:10, 5:10] = True              # 25 pixels: below the 196-pixel floor
    masks[3][0:30, 120:224] = True           # a region with no valid depth
    depth[0:30, 120:224] = 0.0
    return rgb, depth, masks


class FrontEndTests(unittest.TestCase):
    def test_fragments_carry_the_frozen_geometry_and_map_back_to_masks(self) -> None:
        rgb, depth, masks = scene()
        built = build_frame(tick=1, rgb=rgb, depth_m=depth, intrinsics=INTRINSICS, pose=POSE, masks=masks,
                            patch_tokens=tokens)
        self.assertEqual(sorted(built.fragment_to_mask.values()), [0, 1])
        self.assertEqual(dict(built.dropped_masks), {2: "below_196_pixels", 3: "insufficient_valid_depth"})
        _, geometry_config = frozen_configs()
        for fragment in built.cache_frame["fragments"]:
            mask = masks[built.fragment_to_mask[fragment["fragment_id"]]]
            geometry = backproject_public_entity_geometry(mask, depth, INTRINSICS.as_calibration(), POSE.as_pose(),
                                                          geometry_config)
            lower, upper = fc.fragment_aabb(mask, depth, INTRINSICS.as_calibration(), POSE.as_pose(), geometry_config)
            self.assertEqual(fragment["centroid_m"], list(geometry.centroid_m))
            self.assertEqual((fragment["aabb_min_m"], fragment["aabb_max_m"]), (lower, upper))
            self.assertEqual(fragment["mask_sha256"], fc.mask_sha256_of(mask))
            self.assertAlmostEqual(float(np.linalg.norm(fragment["descriptor_vitb14"])), 1.0, places=5)
        view = built.cache_frame[lr.PUBLIC_DEPTH_VIEW_KEY]
        self.assertEqual(tuple(view), lr.PUBLIC_DEPTH_VIEW_FIELDS)
        self.assertEqual(sorted(view["fragment_surface_points"]), sorted(built.fragment_to_mask))

    def test_strict_mode_refuses_what_the_cache_builder_refused(self) -> None:
        rgb, depth, masks = scene()
        with self.assertRaises(FrontEndError):
            build_frame(tick=1, rgb=rgb, depth_m=depth, intrinsics=INTRINSICS, pose=POSE, masks=masks,
                        patch_tokens=tokens, strict=True)
        with self.assertRaises(FrontEndError):
            build_frame(tick=1, rgb=rgb, depth_m=depth, intrinsics=INTRINSICS, pose=POSE, masks=[masks[0], masks[0]],
                        patch_tokens=tokens, strict=True)

    def test_duplicates_are_folded_and_overflow_skips_the_frame(self) -> None:
        rgb, depth, masks = scene()
        built = build_frame(tick=1, rgb=rgb, depth_m=depth, intrinsics=INTRINSICS, pose=POSE,
                            masks=[masks[0], masks[0].copy()], patch_tokens=tokens)
        self.assertEqual(list(built.fragment_to_mask.values()), [0])
        self.assertEqual(built.dropped_masks, [(1, "duplicate_mask")])
        many = []
        for index in range(65):
            mask = np.zeros((SIZE, SIZE), dtype=bool)
            row, column = divmod(index, 9)
            mask[row * 24:row * 24 + 15, column * 24:column * 24 + 15] = True  # 225 pixels each
            many.append(mask)
        built = build_frame(tick=1, rgb=rgb, depth_m=np.full((SIZE, SIZE), 2.0, np.float32), intrinsics=INTRINSICS,
                            pose=POSE, masks=many, patch_tokens=tokens)
        self.assertIsNone(built.cache_frame)
        self.assertEqual(built.skipped_reason, "proposal_overflow")

    def test_other_resolutions_are_brought_to_224(self) -> None:
        depth = np.full((240, 320), 2.0, dtype=np.float32)
        mask = np.zeros((240, 320), dtype=bool)
        mask[100:160, 120:200] = True
        intrinsics = CameraIntrinsics(fx=160.0, fy=160.0, cx=159.5, cy=119.5, width=320, height=240)
        built = build_frame(tick=1, rgb=np.zeros((240, 320, 3), np.uint8), depth_m=depth, intrinsics=intrinsics,
                            pose=POSE, masks=[mask], patch_tokens=tokens)
        view = built.cache_frame[lr.PUBLIC_DEPTH_VIEW_KEY]
        self.assertEqual(view["depth_m"].shape, (224, 224))
        self.assertAlmostEqual(view["calibration"]["fx"], 160.0 * 224 / 320)

    def test_malformed_input_is_refused(self) -> None:
        rgb, depth, masks = scene()
        with self.assertRaises(FrontEndError):
            build_frame(tick=1, rgb=rgb.astype(np.float32), depth_m=depth, intrinsics=INTRINSICS, pose=POSE,
                        masks=masks, patch_tokens=tokens)
        with self.assertRaises(FrontEndError):
            build_frame(tick=1, rgb=rgb, depth_m=depth[:100], intrinsics=INTRINSICS, pose=POSE, masks=masks,
                        patch_tokens=tokens)


if __name__ == "__main__":
    unittest.main()
