"""S3-07 (rulings 111-4, 111-5): the annotated-mesh renderer (lean_s3_07_render) against analytic depth and the frozen readers.

Meshes are synthetic and built in the target camera's frame, then carried into a scan frame through the inverse of
``world_to_camera``, so every expected depth is a closed-form ray-plane intersection.  The last check renders a tilted plane
under a general scan pose and back-projects the depth with the frozen D-223 code (``lean_object_geometry.backproject_mask``) and
the public pose of ``lean_s3_07_3rscan.camera_pose``: the points land back on the plane.
"""

from __future__ import annotations

import copy
import math
import struct
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vsmt import lean_object_geometry as og  # noqa: E402
from vsmt import lean_s3_07_3rscan as r3  # noqa: E402
from vsmt import lean_s3_07_render as rr  # noqa: E402

COLOR = {"fx": 877.5, "fy": 877.5, "cx": 479.75, "cy": 269.75}
TARGET = r3.target_intrinsics(COLOR, (960, 540))


def rotation_about(axis, angle: float) -> np.ndarray:
    axis = np.asarray(axis, dtype=np.float64) / np.linalg.norm(axis)
    k = np.asarray([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    return np.eye(3) + math.sin(angle) * k + (1 - math.cos(angle)) * k @ k


def pose(rotation: np.ndarray, translation) -> np.ndarray:
    matrix = np.eye(4)
    matrix[:3, :3] = rotation
    matrix[:3, 3] = translation
    return matrix


POSE = pose(rotation_about([0.2, -0.4, 1.0], 0.9), [1.3, -0.6, 1.1])


def mesh_from_camera(points_camera, faces, labels, raw_pose=POSE) -> dict:
    """Vertices given in the target camera frame, carried into the scan frame of ``raw_pose``."""

    rc, tc = rr.world_to_camera(raw_pose)
    points = np.asarray(points_camera, dtype=np.float64)
    scan = (points - tc) @ rc  # rc is orthonormal: its inverse is its transpose
    return {"vertices": scan, "faces": np.asarray(faces, dtype=np.int64), "object_ids": np.asarray(labels, dtype=np.int64)}


def quad(x0, x1, y0, y1, z_of, label_left, label_right=None, base=0):
    right = label_left if label_right is None else label_right
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    points = [(x, y, z_of(x, y)) for x, y in corners]
    labels = [label_left, right, right, label_left]
    return points, [(base, base + 1, base + 2), (base, base + 2, base + 3)], labels


def ray(u: float, v: float) -> np.ndarray:
    return np.asarray([(u - TARGET["cx"]) / TARGET["fx"], (TARGET["cy"] - v) / TARGET["fy"], 1.0])


class RenderTests(unittest.TestCase):
    def test_fronto_parallel_plane_has_its_depth_and_label_everywhere(self) -> None:
        points, faces, labels = quad(-5, 5, -5, 5, lambda x, y: 2.0, 9)
        instance, depth, counts = rr.render(mesh_from_camera(points, faces, labels), POSE, TARGET)
        self.assertEqual((instance.dtype, depth.dtype, instance.shape), (np.uint16, np.float32, (224, 224)))
        self.assertTrue((instance == 9).all())
        self.assertTrue(np.allclose(depth, 2.0, rtol=0, atol=1e-6))
        self.assertEqual((counts["pixels_hit"], counts["faces_rasterised"], counts["faces_ray_cast"]), (224 * 224, 2, 0))

    def test_nearer_surface_occludes_and_its_outline_is_the_projection(self) -> None:
        far_p, far_f, far_l = quad(-5, 5, -5, 5, lambda x, y: 3.0, 3)
        near_p, near_f, near_l = quad(-0.1, 0.1, -0.1, 0.1, lambda x, y: 1.0, 7, base=4)
        instance, depth, _counts = rr.render(mesh_from_camera(far_p + near_p, far_f + near_f, far_l + near_l), POSE, TARGET)
        half = TARGET["fx"] * 0.1  # the near square spans cx +- 36.4 px at 1 m
        inside_u, outside_u = int(math.floor(TARGET["cx"] + half)) - 1, int(math.ceil(TARGET["cx"] + half)) + 1
        row = int(round(TARGET["cy"]))
        self.assertEqual((int(instance[row, inside_u]), float(depth[row, inside_u])), (7, 1.0))
        self.assertEqual((int(instance[row, outside_u]), float(depth[row, outside_u])), (3, 3.0))

    def test_tilted_plane_depth_is_the_ray_plane_intersection(self) -> None:
        points, faces, labels = quad(-6, 6, -6, 6, lambda x, y: 2.0 + 0.5 * x, 4)
        _instance, depth, _counts = rr.render(mesh_from_camera(points, faces, labels), POSE, TARGET)
        for u, v in ((0, 0), (111, 112), (223, 30), (40, 200)):
            d = ray(u, v)
            expected = 2.0 / (1.0 - 0.5 * d[0])  # z = t on a ray with d_z = 1
            self.assertAlmostEqual(float(depth[v, u]), expected, delta=2e-6 * expected)

    def test_a_face_crossing_the_camera_plane_is_ray_cast_exactly(self) -> None:
        floor = [(-3.0, -1.0, -1.0), (3.0, -1.0, -1.0), (0.0, -1.0, 8.0)]  # one edge behind the camera
        instance, depth, counts = rr.render(mesh_from_camera(floor, [(0, 1, 2)], [5, 5, 5]), POSE, TARGET)
        self.assertEqual((counts["faces_rasterised"], counts["faces_ray_cast"]), (0, 1))
        u, v = 112, 200
        d = ray(u, v)
        self.assertLess(d[1], 0)
        t = -1.0 / d[1]
        self.assertEqual(int(instance[v, u]), 5)
        self.assertAlmostEqual(float(depth[v, u]), t, delta=1e-6 * t)
        self.assertEqual(int(instance[10, u]), 0)  # above the horizon: no hit
        self.assertEqual(float(depth[10, u]), r3.INVALID_DEPTH_M)

    def test_label_is_the_nearest_corner_of_the_hit_face(self) -> None:
        points, faces, labels = quad(-5, 5, -5, 5, lambda x, y: 2.0, 1, label_right=2)
        instance, _depth, _counts = rr.render(mesh_from_camera(points, faces, labels), POSE, TARGET)
        self.assertTrue((instance[:, :100] == 1).all())
        self.assertTrue((instance[:, 125:] == 2).all())

    def test_unannotated_vertices_and_empty_views_read_as_background(self) -> None:
        points, faces, labels = quad(-5, 5, -5, 5, lambda x, y: 2.0, 0)
        instance, depth, counts = rr.render(mesh_from_camera(points, faces, labels), POSE, TARGET)
        self.assertTrue((instance == rr.BACKGROUND_LABEL).all() and (depth == 2.0).all())
        self.assertEqual(counts["pixels_labelled"], 0)
        behind_p, behind_f, behind_l = quad(-5, 5, -5, 5, lambda x, y: -2.0, 4)
        instance, depth, counts = rr.render(mesh_from_camera(behind_p, behind_f, behind_l), POSE, TARGET)
        self.assertTrue((instance == 0).all() and (depth == 0.0).all())
        self.assertEqual(counts["faces_rasterised"] + counts["faces_ray_cast"], 0)

    def test_rendering_is_deterministic_and_independent_of_face_order(self) -> None:
        far_p, far_f, far_l = quad(-5, 5, -5, 5, lambda x, y: 3.0 + 0.2 * y, 3)
        near_p, near_f, near_l = quad(-0.3, 0.2, -0.25, 0.35, lambda x, y: 1.5 - 0.1 * x, 7, base=4)
        mesh = mesh_from_camera(far_p + near_p, far_f + near_f, far_l + near_l)
        first = rr.render(mesh, POSE, TARGET)
        again = rr.render(copy.deepcopy(mesh), POSE, TARGET)
        reordered = dict(mesh, faces=mesh["faces"][::-1].copy())
        flipped = rr.render(reordered, POSE, TARGET)
        for a, b in ((first, again), (first, flipped)):
            self.assertTrue(np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1]))

    def test_rendered_depth_back_projects_onto_the_plane_through_the_frozen_reader(self) -> None:
        """Renderer, public pose and the frozen D-223 back-projection agree: depth pixels land on the scan's plane."""

        points, faces, labels = quad(-6, 6, -6, 6, lambda x, y: 2.5 + 0.4 * x - 0.3 * y, 2)
        mesh = mesh_from_camera(points, faces, labels)
        _instance, depth, _counts = rr.render(mesh, POSE, TARGET)
        rotation, position, _res = r3.camera_pose(POSE)
        public = r3.relative_pose(rotation, position, position)
        mask = np.zeros((224, 224), dtype=bool)
        mask[::17, ::13] = True
        recovered = og.backproject_mask(mask, depth, TARGET, {k: public[k] for k in ("position_m", "quaternion_xyzw")},
                                        minimum_depth_m=0.05, maximum_depth_m=20.0)
        plane = r3.to_project_world(mesh["vertices"]) - position  # the plane's corners in the episode frame
        normal = np.cross(plane[1] - plane[0], plane[2] - plane[0])
        normal /= np.linalg.norm(normal)
        self.assertGreater(len(recovered), 100)
        self.assertLess(float(np.max(np.abs((recovered - plane[0]) @ normal))), 5e-6)

    def test_world_to_camera_inverts_the_public_pose(self) -> None:
        rc, tc = rr.world_to_camera(POSE)
        rotation, position, _res = r3.camera_pose(POSE)
        point = np.asarray([[0.7, -1.1, 2.4]])
        camera = rc @ point[0] + tc
        self.assertTrue(np.allclose(rotation @ camera + position, r3.to_project_world(point)[0], atol=1e-12))


def ply_bytes(vertices, labels, faces, *, binary: bool) -> bytes:
    header = ["ply", "format " + ("binary_little_endian" if binary else "ascii") + " 1.0", f"element vertex {len(vertices)}",
              "property float x", "property float y", "property float z", "property uchar red", "property uchar green",
              "property uchar blue", "property ushort objectId", "property ushort globalId", "property uchar NYU40",
              "property uchar Eigen13", "property uchar RIO27", f"element face {len(faces)}",
              "property list uchar uint vertex_indices", "end_header"]
    head = ("\n".join(header) + "\n").encode("ascii")
    if not binary:
        rows = [f"{x} {y} {z} 1 2 3 {o} 9 5 4 3" for (x, y, z), o in zip(vertices, labels)]
        rows += [f"3 {a} {b} {c}" for a, b, c in faces]
        return head + ("\n".join(rows) + "\n").encode("ascii")
    body = b"".join(struct.pack("<fffBBBHHBBB", x, y, z, 1, 2, 3, o, 9, 5, 4, 3) for (x, y, z), o in zip(vertices, labels))
    body += b"".join(struct.pack("<BIII", 3, a, b, c) for a, b, c in faces)
    return head + body


class PlyTests(unittest.TestCase):
    VERTICES = [(0.0, 0.0, 0.0), (1.5, 0.0, 0.25), (0.0, 2.0, -0.5), (1.0, 1.0, 1.0)]
    LABELS = [4, 4, 0, 12]
    FACES = [(0, 1, 2), (1, 3, 2)]

    def test_ascii_and_binary_read_the_same(self) -> None:
        a = rr.read_ply(ply_bytes(self.VERTICES, self.LABELS, self.FACES, binary=False))
        b = rr.read_ply(ply_bytes(self.VERTICES, self.LABELS, self.FACES, binary=True))
        for key in ("vertices", "object_ids", "faces"):
            self.assertTrue(np.array_equal(a[key], b[key]), key)
        self.assertEqual(a["object_ids"].tolist(), self.LABELS)
        self.assertEqual(a["faces"].tolist(), [list(f) for f in self.FACES])
        self.assertTrue(np.allclose(a["vertices"], self.VERTICES))

    def test_refusals(self) -> None:
        good = ply_bytes(self.VERTICES, self.LABELS, self.FACES, binary=False).decode("ascii")
        with self.assertRaisesRegex(rr.LeanS307RenderError, "ply_face_not_triangle"):
            rr.read_ply(good.replace("3 1 3 2", "4 1 3 2 0").replace("element face 2", "element face 2").encode("ascii"))
        with self.assertRaisesRegex(rr.LeanS307RenderError, "ply_face_index_out_of_range"):
            rr.read_ply(good.replace("3 1 3 2", "3 1 7 2").encode("ascii"))
        with self.assertRaisesRegex(rr.LeanS307RenderError, "ply_vertex_property_missing:objectId"):
            rr.read_ply(good.replace("property ushort objectId", "property ushort instance").encode("ascii"))
        with self.assertRaisesRegex(rr.LeanS307RenderError, "ply_format_unsupported"):
            rr.read_ply(good.replace("format ascii 1.0", "format binary_big_endian 1.0").encode("ascii"))

    def test_contract_names_the_render_rules(self) -> None:
        contract = r3.load_contract()
        rr.check_contract(contract)
        broken = copy.deepcopy(contract)
        broken["render"]["raster_near_m"] = 0.05
        with self.assertRaisesRegex(rr.LeanS307RenderError, "contract_render_near_mismatch"):
            rr.check_contract(broken)


if __name__ == "__main__":
    unittest.main()
