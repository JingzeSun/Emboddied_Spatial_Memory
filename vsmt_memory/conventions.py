"""Camera conventions of the frozen front end and conversions from common robotics conventions.

The frozen back-projection (``vsmt.l1_entities.backproject_public_entity_geometry``) reads:

- depth as metric distance along the camera axis (z-depth, not the length of the ray), valid in [0.05 m, 20 m];
- pixel ``(row v, column u)`` with no half-pixel offset: ``x = (u - cx) z / fx``, ``y = (cy - v) z / fy``;
- a camera frame with +x right, +y up and +z forward;
- a camera-to-world pose (position and unit quaternion ``x, y, z, w``) in a gravity-aligned world whose +y axis points
  up.  Heights (the support-height feature of the association head) are read along +y.

Both frames are left-handed, as in the simulator (Unity).  ``CameraPose.from_opencv`` converts a right-handed
OpenCV/ROS pose into this convention by an orthogonal change of axes; distances, volumes and heights are preserved.

Every training episode was rendered at 224 x 224 pixels, which is also the DINOv2 input size of the frozen front end.
``resize_to_frame_size`` brings other resolutions to that size, so that pixel counts (the 196-pixel admission floor and
the birth head's pixel-count feature) keep the scale the cost heads were trained on.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np

from . import _repo  # noqa: F401  (src/ on sys.path)
from vsmt import lean_public_pose as pp

FRAME_SIZE = 224
"""Height and width of every frame the front end processes (the frozen DINOv2 input size)."""

DEPTH_VALID_RANGE_M = (0.05, 20.0)
"""Depth values outside this closed range are treated as invalid by the frozen geometry."""


@dataclass(frozen=True)
class CameraIntrinsics:
    """Pinhole intrinsics of one image, in pixels.

    ``cx``/``cy`` use the convention of the frozen back-projection: pixel ``u`` (column) maps to ``(u - cx) / fx``.
    This is the OpenCV convention as well.
    """

    fx: float
    fy: float
    cx: float
    cy: float
    width: int
    height: int

    def __post_init__(self) -> None:
        values = (self.fx, self.fy, self.cx, self.cy)
        if not all(math.isfinite(float(v)) for v in values) or self.fx <= 0 or self.fy <= 0:
            raise ValueError("intrinsics must be finite with positive focal lengths")
        if int(self.width) < 1 or int(self.height) < 1:
            raise ValueError("image width and height must be positive")

    def as_calibration(self) -> dict[str, float]:
        """The ``calibration`` mapping the frozen functions read."""

        return {"fx": float(self.fx), "fy": float(self.fy), "cx": float(self.cx), "cy": float(self.cy)}

    def resized(self, width: int, height: int) -> "CameraIntrinsics":
        """Intrinsics of the same camera after resizing the image to ``width`` x ``height`` (pixel centres kept)."""

        sx, sy = width / self.width, height / self.height
        return CameraIntrinsics(fx=self.fx * sx, fy=self.fy * sy, cx=(self.cx + 0.5) * sx - 0.5,
                                cy=(self.cy + 0.5) * sy - 0.5, width=int(width), height=int(height))


@dataclass(frozen=True)
class CameraPose:
    """Camera-to-world pose in the frozen convention (see the module docstring).

    The world frame may have any origin and heading, but its +y axis must point up (against gravity): the memory
    compares heights along +y.  Use ``from_opencv`` for poses given in the OpenCV/ROS convention.
    """

    position_m: tuple[float, float, float]
    quaternion_xyzw: tuple[float, float, float, float]

    def __post_init__(self) -> None:
        if len(self.position_m) != 3 or len(self.quaternion_xyzw) != 4:
            raise ValueError("position needs 3 values and the quaternion 4")
        if not all(math.isfinite(float(v)) for v in (*self.position_m, *self.quaternion_xyzw)):
            raise ValueError("pose values must be finite")
        if abs(math.sqrt(sum(float(v) ** 2 for v in self.quaternion_xyzw)) - 1.0) > 1e-6:
            raise ValueError("the quaternion must have unit norm")

    @classmethod
    def from_rotation(cls, rotation: np.ndarray, position_m: Sequence[float]) -> "CameraPose":
        """A pose from a camera-to-world rotation matrix (frozen convention) and a position."""

        quaternion = pp.quaternion_xyzw_from_rotation(np.asarray(rotation, dtype=np.float64))
        return cls(position_m=tuple(float(v) for v in position_m), quaternion_xyzw=tuple(float(v) for v in quaternion))

    @classmethod
    def from_opencv(cls, world_from_camera: np.ndarray, *, world_up: Sequence[float] | str = "z") -> "CameraPose":
        """Convert a right-handed camera-to-world transform with an OpenCV camera (+x right, +y down, +z forward).

        ``world_from_camera`` is a 4 x 4 (or 3 x 4) matrix mapping camera points to world points.  ``world_up`` names
        the world axis that points up: ``"z"`` for ROS/REP-103 maps, ``"-y"`` when the world is the first OpenCV camera
        frame of a level camera, or any 3-vector.  The world is re-expressed with that axis as +y; the conversion is
        orthogonal, so distances, box volumes and heights are unchanged.
        """

        transform = np.asarray(world_from_camera, dtype=np.float64)
        if transform.shape not in ((4, 4), (3, 4)) or not np.isfinite(transform).all():
            raise ValueError("world_from_camera must be a finite 4x4 or 3x4 matrix")
        rotation, translation = transform[:3, :3], transform[:3, 3]
        if not np.allclose(rotation @ rotation.T, np.eye(3), atol=1e-6) or np.linalg.det(rotation) < 0:
            raise ValueError("the rotation part must be a proper rotation (right-handed world and camera)")
        world = world_axes(world_up)
        camera = np.diag([1.0, -1.0, 1.0])  # OpenCV camera -> camera with +y up
        converted = world @ rotation @ camera
        u, _, vt = np.linalg.svd(converted)  # remove rounding drift before the quaternion check
        return cls.from_rotation(u @ vt, world @ translation)

    def rotation(self) -> np.ndarray:
        """The camera-to-world rotation matrix."""

        return pp.rotation_from_quaternion_xyzw(self.quaternion_xyzw)

    def as_pose(self) -> dict[str, list[float]]:
        """The ``pose`` mapping the frozen functions read."""

        return {"position_m": [float(v) for v in self.position_m],
                "quaternion_xyzw": [float(v) for v in self.quaternion_xyzw]}


def world_axes(world_up: Sequence[float] | str) -> np.ndarray:
    """An improper orthogonal matrix taking a right-handed world with the given up axis to the frozen (left-handed,
    +y up) world: a rotation taking ``world_up`` to +y, followed by a flip of z."""

    named = {"x": (1, 0, 0), "-x": (-1, 0, 0), "y": (0, 1, 0), "-y": (0, -1, 0), "z": (0, 0, 1), "-z": (0, 0, -1)}
    up = np.asarray(named[world_up] if isinstance(world_up, str) else world_up, dtype=np.float64)
    if up.shape != (3,) or not np.isfinite(up).all() or np.linalg.norm(up) == 0:
        raise ValueError("world_up must name an axis or be a non-zero 3-vector")
    up = up / np.linalg.norm(up)
    target = np.array([0.0, 1.0, 0.0])
    axis = np.cross(up, target)
    sine, cosine = float(np.linalg.norm(axis)), float(np.dot(up, target))
    if sine < 1e-12:
        to_y = np.eye(3) if cosine > 0 else np.diag([1.0, -1.0, -1.0])  # already up, or a half turn about x
    else:
        k = axis / sine
        skew = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
        to_y = np.eye(3) + sine * skew + (1 - cosine) * skew @ skew
    return np.diag([1.0, 1.0, -1.0]) @ to_y


def to_user_world(points_m: np.ndarray | Sequence[float], *, world_up: Sequence[float] | str = "z") -> np.ndarray:
    """Convert points (..., 3) from the frozen world back to the world given to ``CameraPose.from_opencv``.

    With ``world_up="z"`` the frozen ``(x, y, z)`` is the user's ``(x, z, y)``.  For an entity box, convert its two
    corners and take the element-wise minimum and maximum (exact when ``world_up`` names an axis).
    """

    return np.asarray(points_m, dtype=np.float64) @ world_axes(world_up)  # the inverse of an orthogonal matrix


def _nearest_indices(source: int, target: int) -> np.ndarray:
    return np.minimum(((np.arange(target) + 0.5) * source / target).astype(np.int64), source - 1)


def resize_to_frame_size(
    rgb: np.ndarray, depth_m: np.ndarray, masks: Sequence[np.ndarray], intrinsics: CameraIntrinsics,
) -> tuple[np.ndarray, np.ndarray, list[np.ndarray], CameraIntrinsics]:
    """Resize one frame to ``FRAME_SIZE`` x ``FRAME_SIZE``: RGB bilinear, depth and masks by the nearest pixel centre.

    A frame that already has that size is returned unchanged (the path every training frame took).  Non-square images
    are scaled per axis, and the intrinsics follow, so the geometry stays exact while DINOv2 sees a stretched image.
    """

    height, width = depth_m.shape
    if (height, width) == (FRAME_SIZE, FRAME_SIZE):
        return rgb, depth_m, [np.asarray(m, dtype=bool) for m in masks], intrinsics
    from PIL import Image

    rows, columns = _nearest_indices(height, FRAME_SIZE), _nearest_indices(width, FRAME_SIZE)
    resized_rgb = np.asarray(Image.fromarray(np.asarray(rgb, dtype=np.uint8)).resize((FRAME_SIZE, FRAME_SIZE),
                                                                                       Image.BILINEAR), dtype=np.uint8)
    resized_depth = np.ascontiguousarray(np.asarray(depth_m)[rows][:, columns])
    resized_masks = [np.ascontiguousarray(np.asarray(m, dtype=bool)[rows][:, columns]) for m in masks]
    return resized_rgb, resized_depth, resized_masks, intrinsics.resized(FRAME_SIZE, FRAME_SIZE)
