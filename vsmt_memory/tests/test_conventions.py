"""Pose and intrinsics conversions: geometry must be preserved exactly (no downloads)."""

from __future__ import annotations

import math
import unittest

import numpy as np

from vsmt_memory.conventions import (FRAME_SIZE, CameraIntrinsics, CameraPose, resize_to_frame_size, to_user_world,
                                     world_axes)
from vsmt.l1_entities import _camera_values


def random_rotation(rng: np.random.Generator) -> np.ndarray:
    q, r = np.linalg.qr(rng.standard_normal((3, 3)))
    q = q @ np.diag(np.sign(np.diag(r)))
    return q if np.linalg.det(q) > 0 else -q


def backproject_frozen(u: float, v: float, z: float, intrinsics: CameraIntrinsics, pose: CameraPose) -> np.ndarray:
    """A pixel to a world point with the frozen camera values and formula (l1_entities)."""

    fx, fy, cx, cy, position, rotation = _camera_values(intrinsics.as_calibration(), pose.as_pose())
    camera = np.array([(u - cx) * z / fx, (cy - v) * z / fy, z])
    return rotation @ camera + position


class ConventionTests(unittest.TestCase):
    def test_world_axes_are_an_improper_orthogonal_map_taking_up_to_plus_y(self) -> None:
        for up in ("x", "-x", "y", "-y", "z", "-z", (0.3, -0.2, 0.9)):
            axes = world_axes(up)
            vector = np.asarray({"x": (1, 0, 0), "-x": (-1, 0, 0), "y": (0, 1, 0), "-y": (0, -1, 0), "z": (0, 0, 1),
                                 "-z": (0, 0, -1)}.get(up, up), dtype=float) if isinstance(up, str) else np.asarray(up)
            np.testing.assert_allclose(axes @ axes.T, np.eye(3), atol=1e-12)
            self.assertAlmostEqual(float(np.linalg.det(axes)), -1.0, places=12)
            np.testing.assert_allclose(axes @ (vector / np.linalg.norm(vector)), [0, 1, 0], atol=1e-12)

    def test_opencv_pose_back_projects_to_the_same_world_point(self) -> None:
        rng = np.random.default_rng(0)
        intrinsics = CameraIntrinsics(fx=300.0, fy=310.0, cx=159.5, cy=119.5, width=320, height=240)
        for up in ("z", "-y", "y"):
            axes = world_axes(up)
            for _ in range(20):
                rotation, position = random_rotation(rng), rng.uniform(-5, 5, 3)
                transform = np.eye(4)
                transform[:3, :3], transform[:3, 3] = rotation, position
                pose = CameraPose.from_opencv(transform, world_up=up)
                u, v, z = rng.uniform(0, 320), rng.uniform(0, 240), rng.uniform(0.2, 8.0)
                camera_cv = np.array([(u - intrinsics.cx) * z / intrinsics.fx, (v - intrinsics.cy) * z / intrinsics.fy, z])
                expected = axes @ (rotation @ camera_cv + position)
                np.testing.assert_allclose(backproject_frozen(u, v, z, intrinsics, pose), expected, atol=1e-9)

    def test_outputs_convert_back_to_the_user_world(self) -> None:
        points = np.random.default_rng(2).uniform(-5, 5, (10, 3))
        for up in ("z", "-y", (0.2, 0.1, 0.97)):
            np.testing.assert_allclose(to_user_world(points @ world_axes(up).T, world_up=up), points, atol=1e-12)
        np.testing.assert_allclose(to_user_world([1.0, 3.0, 2.0], world_up="z"), [1.0, 2.0, 3.0])

    def test_ros_world_height_becomes_plus_y(self) -> None:
        transform = np.eye(4)
        transform[:3, :3] = np.column_stack([[0, -1, 0], [0, 0, -1], [1, 0, 0]])  # looking along +x, level
        transform[:3, 3] = [1.0, 2.0, 1.5]
        pose = CameraPose.from_opencv(transform, world_up="z")
        self.assertAlmostEqual(pose.position_m[1], 1.5, places=12)
        forward = pose.rotation()[:, 2]
        self.assertAlmostEqual(float(forward[1]), 0.0, places=12)

    def test_resized_intrinsics_keep_pixel_centres(self) -> None:
        intrinsics = CameraIntrinsics(fx=320.0, fy=320.0, cx=319.5, cy=239.5, width=640, height=480)
        small = intrinsics.resized(FRAME_SIZE, FRAME_SIZE)
        self.assertAlmostEqual(small.cx, (FRAME_SIZE - 1) / 2)
        self.assertAlmostEqual(small.cy, (FRAME_SIZE - 1) / 2)
        self.assertAlmostEqual(small.fx, 320.0 * FRAME_SIZE / 640)

    def test_frames_of_the_frozen_size_are_not_resampled(self) -> None:
        rgb = np.random.default_rng(1).integers(0, 255, (224, 224, 3), dtype=np.uint8)
        depth = np.full((224, 224), 2.0, dtype=np.float32)
        intrinsics = CameraIntrinsics(fx=112.0, fy=112.0, cx=111.5, cy=111.5, width=224, height=224)
        out = resize_to_frame_size(rgb, depth, [depth > 1], intrinsics)
        self.assertIs(out[0], rgb)
        self.assertIs(out[1], depth)
        self.assertEqual(out[3], intrinsics)

    def test_pose_validation(self) -> None:
        with self.assertRaises(ValueError):
            CameraPose(position_m=(0.0, 0.0, 0.0), quaternion_xyzw=(0.0, 0.0, 0.0, 2.0))
        with self.assertRaises(ValueError):
            CameraPose.from_opencv(np.diag([1.0, 1.0, -1.0, 1.0]))  # a reflection, not a rotation
        self.assertTrue(math.isclose(sum(v * v for v in CameraPose.from_opencv(np.eye(4)).quaternion_xyzw), 1.0))


if __name__ == "__main__":
    unittest.main()
