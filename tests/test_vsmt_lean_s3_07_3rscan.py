"""S3-07 (ruling 111): the 3RScan conversion's pure functions (lean_s3_07_3rscan), checked against the frozen readers.

Every fixture is synthetic: no 3RScan bytes are committed (terms of use).  Where a frozen function exists it is the judge: the
target camera and the converted pose are checked by the D-223 back-projection (``lean_object_geometry.backproject_mask``), the
quaternion by ``lean_public_pose``, the frame digest by the S2-04 reader's recomputation, the place rule and the structural
prefixes by ``lean_teacher``.
"""

from __future__ import annotations

import copy
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for item in (ROOT / "src", ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt import lean_object_geometry as og  # noqa: E402
from vsmt import lean_public_pose as pp  # noqa: E402
from vsmt import lean_s3_07_3rscan as r3  # noqa: E402
from vsmt import lean_teacher as lt  # noqa: E402

#: the colour intrinsics of the public sample _info.txt in 3RScan's own reader comment (documentation values, not data)
COLOR = {"fx": 756.832, "fy": 756.026, "cx": 492.889, "cy": 270.419}
DEPTH = {"fx": 176.594, "fy": 240.808, "cx": 114.613, "cy": 85.7915}
#: the reviewed contract, digest of its canonical JSON (re-pinned only with a ruling or a registration commit)
CONTRACT_SHA256 = "cbc664671513f81b681fafc5637532a473b3598df0c0f6bd37c48686d12d1a23"

INFO_TEXT = """m_versionNumber = 4
m_sensorName = StructureSensor
m_colorWidth = 960
m_colorHeight = 540
m_depthWidth = 224
m_depthHeight = 172
m_depthShift = 1000
m_calibrationColorIntrinsic = 756.832 0 492.889 0 0 756.026 270.419 0 0 0 1 0 0 0 0 1
m_calibrationColorExtrinsic = 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1
m_calibrationDepthIntrinsic = 176.594 0 114.613 0 0 240.808 85.7915 0 0 0 1 0 0 0 0 1
m_calibrationDepthExtrinsic = 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1
m_frames.size = 467
"""


def rotation_about(axis: np.ndarray, angle: float) -> np.ndarray:
    axis = np.asarray(axis, dtype=np.float64) / np.linalg.norm(axis)
    k = np.asarray([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    return np.eye(3) + math.sin(angle) * k + (1 - math.cos(angle)) * k @ k


def rigid(rotation: np.ndarray, translation) -> np.ndarray:
    matrix = np.eye(4)
    matrix[:3, :3] = rotation
    matrix[:3, 3] = translation
    return matrix


def box(center, size) -> dict:
    c, s = np.asarray(center, dtype=float), np.asarray(size, dtype=float)
    return {"centroid_m": list(c), "aabb_min_m": list(c - s / 2), "aabb_max_m": list(c + s / 2), "size_m": list(s)}


class ContractTests(unittest.TestCase):
    def test_contract_states_the_module_constants_and_blocks_until_the_sample_check(self) -> None:
        contract = r3.load_contract()
        self.assertEqual(r3.blocking_null_slots(contract), [])  # registered from the sample check (d05f337)
        self.assertEqual(contract["sample_check"], {"alignment_translation_unit": "m", "obb_axes_layout": "rows",
                                                    "image_rotation_confirmed": True, "ambiguity_structure_confirmed": True})
        self.assertTrue(contract["authorization"]["formal_conversion"])  # opened by the registration commit (111-8 step 7)
        emptied = copy.deepcopy(contract)
        emptied["sample_check"] = {name: None for name in r3.SAMPLE_CHECK_SLOTS}
        self.assertEqual(r3.blocking_null_slots(r3.validate_contract(emptied)), list(r3.SAMPLE_CHECK_SLOTS))
        for path, value, code in (
            (("camera", "target_size"), 256, "contract_target_size_mismatch"),
            (("camera", "image_rotation"), "counterclockwise_90", "contract_rotation_mismatch"),
            (("truth", "delta_moved_m"), 0.4, "contract_place_rule_mismatch"),
            (("depth", "source"), "sensor", "contract_depth_mismatch"),
            (("sample_check", "alignment_translation_unit"), "cm", "contract_translation_unit_invalid"),
            (("sample_check", "image_rotation_confirmed"), False, "contract_rotation_confirmed_invalid"),
        ):
            broken = copy.deepcopy(contract)
            broken[path[0]][path[1]] = value
            with self.assertRaisesRegex(r3.LeanS307Error, code):
                r3.validate_contract(broken)

    def test_contract_digest_is_pinned(self) -> None:
        contract = json.loads(r3.CONTRACT_PATH.read_text(encoding="utf-8"))
        digest = __import__("hashlib").sha256(canonical_json(contract).encode("utf-8")).hexdigest()
        self.assertEqual(digest, CONTRACT_SHA256)

    def test_structural_prefixes_are_exactly_the_frozen_evaluators(self) -> None:
        self.assertEqual(set(r3.NYU40_STRUCTURAL_PREFIX.values()), set(lt.STRUCTURAL_TYPES_EXCLUDED))


class ParsingTests(unittest.TestCase):
    def test_info_reads_sizes_and_both_intrinsics(self) -> None:
        info = r3.parse_info(INFO_TEXT)
        self.assertEqual(info["color_size_wh"], (960, 540))
        self.assertEqual(info["depth_size_wh"], (224, 172))
        self.assertEqual(info["color_intrinsics"], COLOR)
        self.assertEqual(info["depth_intrinsics"], DEPTH)
        self.assertEqual(info["frames"], 467)
        with self.assertRaisesRegex(r3.LeanS307Error, "info_extrinsic_not_identity"):
            r3.parse_info(INFO_TEXT.replace("m_calibrationDepthExtrinsic = 1 0 0 0", "m_calibrationDepthExtrinsic = 1 0 0 0.05"))
        with self.assertRaisesRegex(r3.LeanS307Error, "info_field_missing:m_depthShift"):
            r3.parse_info(INFO_TEXT.replace("m_depthShift = 1000\n", ""))

    def test_pose_text_and_orthonormal_rotation(self) -> None:
        rotation = rotation_about([0.3, -0.5, 0.8], 1.1)
        text = "\n".join(" ".join(f"{v:.6f}" for v in row) for row in rigid(rotation, [1.25, -0.5, 2.0]))
        pose = r3.parse_pose(text)
        nearest, moved = r3.orthonormal_rotation(pose[:3, :3])
        self.assertLess(moved, 1e-5)
        self.assertTrue(np.allclose(nearest @ nearest.T, np.eye(3), atol=1e-12))
        with self.assertRaisesRegex(r3.LeanS307Error, "pose_not_rigid"):
            r3.parse_pose("\n".join(" ".join(str(v) for v in row) for row in rigid(1.01 * rotation, [0, 0, 0])))
        with self.assertRaisesRegex(r3.LeanS307Error, "pose_not_16_numbers"):
            r3.parse_pose("1 0 0 0 1 0 0 0 1")

    def test_alignment_is_column_major_with_a_registered_unit(self) -> None:
        rotation = rotation_about([0, 0, 1], 0.7)
        matrix = rigid(rotation, [1.5, -2.0, 0.25])
        values = list(matrix.T.reshape(-1))  # column-major: translation at 12, 13, 14
        self.assertEqual(values[12:15], [1.5, -2.0, 0.25])
        self.assertTrue(np.allclose(r3.alignment_matrix(values, unit="m"), matrix))
        in_mm = list(rigid(rotation, [1500.0, -2000.0, 250.0]).T.reshape(-1))
        self.assertTrue(np.allclose(r3.alignment_matrix(in_mm, unit="mm"), matrix))
        with self.assertRaisesRegex(r3.LeanS307Error, "alignment_translation_unit_not_registered"):
            r3.alignment_matrix(values, unit=None)
        with self.assertRaisesRegex(r3.LeanS307Error, "alignment_not_rigid"):
            r3.alignment_matrix(list(matrix.reshape(-1)), unit="m")  # row-major read as column-major: last row not 0 0 0 1

    def test_label_mapping_reads_the_nyu40_column(self) -> None:
        text = ('"The following gives a full list of the classes ...",,,,,,,,,,,,,\n'
                "Global ID,Label,,NYU40 Mapping,,Eigen Mapping,,RIO27 Mapping,,RIO7 Mapping,#sum,#train,#test,#val\n"
                "1,air conditioner,40,otherprop,7,Objects,26,object,0,-,32,32,3,0\n"
                "4,armchair,5,chair,4,Chair,5,chair,1,seating,375,332,38,43\n"
                "500,wall,1,wall,12,Wall,1,wall,7,structure,605,605,1,0\n")
        self.assertEqual(r3.parse_label_mapping(text), {"air conditioner": 40, "armchair": 5, "wall": 1})
        with self.assertRaisesRegex(r3.LeanS307Error, "label_mapping_duplicate:wall"):
            r3.parse_label_mapping(text + "501,wall,1,wall,12,Wall,1,wall,7,structure,1,1,0,0\n")
        with self.assertRaisesRegex(r3.LeanS307Error, "label_mapping_header_missing"):
            r3.parse_label_mapping("a,b,c\n1,2,3\n")

    def test_semseg_objects_and_unique_ids(self) -> None:
        group = {"id": 0, "objectId": 7, "label": "chair",
                 "obb": {"centroid": [1, 2, 3], "axesLengths": [0.5, 0.6, 0.9], "normalizedAxes": [1, 0, 0, 0, 1, 0, 0, 0, 1]}}
        objects = r3.semseg_objects({"segGroups": [group]})
        self.assertEqual(objects[7]["label"], "chair")
        with self.assertRaisesRegex(r3.LeanS307Error, "semseg_object_id_invalid:7"):
            r3.semseg_objects({"segGroups": [group, dict(group, id=1)]})

    def test_rescan_changes_read_the_observed_ambiguity_structure(self) -> None:
        # the structure 3RScan.json has (scene-level list of lists of instance pairs); the numbers are made up
        scene = {"reference": "a" * 8 + "-0000-0000-0000-" + "0" * 12, "type": "validation",
                 "ambiguity": [[{"instance_source": 31, "instance_target": 33, "transform": [1] * 16},
                                {"instance_source": 33, "instance_target": 31, "transform": [1] * 16}]],
                 "scans": [{"reference": "b" * 8 + "-0000-0000-0000-" + "0" * 12, "transform": list(np.eye(4).T.reshape(-1)),
                            "removed": [5, 5], "nonrigid": [9], "rigid": [{"instance_reference": 4, "instance_rescan": 4,
                                                                          "symmetry": 0, "transform": [1] * 16}]}]}
        changes = r3.rescan_changes(scene, scene["scans"][0]["reference"])
        self.assertEqual(changes["removed"], [5])
        self.assertEqual(changes["rigid"], [(4, 4)])
        self.assertEqual(changes["ambiguity"], [31, 33])
        self.assertEqual(r3.ambiguity_ids([{"instance_source": 2, "instance_target": 3}]), {2, 3})  # a flat list reads the same
        self.assertEqual(r3.ambiguity_ids([]), set())
        with self.assertRaisesRegex(r3.LeanS307Error, "ambiguity_structure_unrecognized"):
            r3.ambiguity_ids([[{"source": 1}]])
        with self.assertRaisesRegex(r3.LeanS307Error, "rescan_not_found_once"):
            r3.rescan_changes(scene, "c" * 8 + "-0000-0000-0000-" + "0" * 12)
        self.assertIs(r3.scene_entry([scene], scene["reference"]), scene)


class CameraTests(unittest.TestCase):
    def test_target_camera_matches_the_pixel_mapping_and_the_axes(self) -> None:
        """A target pixel back-projected in the target camera lands, after S and Q^T, on the raw pixel the mapping names."""

        target = r3.target_intrinsics(COLOR, (960, 540))
        rng = np.random.default_rng(7)
        u_t, v_t = rng.uniform(0, 223, 50), rng.uniform(0, 223, 50)
        z = rng.uniform(0.5, 6.0, 50)
        camera_points = np.column_stack(((u_t - target["cx"]) * z / target["fx"], (target["cy"] - v_t) * z / target["fy"], z))
        raw = camera_points @ (r3.Q.T @ r3.S).T
        u_raw = COLOR["fx"] * raw[:, 0] / raw[:, 2] + COLOR["cx"]
        v_raw = COLOR["fy"] * raw[:, 1] / raw[:, 2] + COLOR["cy"]
        mapped_u, mapped_v = r3.target_to_raw_pixel(u_t, v_t, (960, 540))
        self.assertTrue(np.allclose(mapped_u, u_raw, atol=1e-9) and np.allclose(mapped_v, v_raw, atol=1e-9))
        # the vertical field of view of the target is the raw short side's, about 39 degrees here (ProcTHOR: 90)
        fov = 2 * math.degrees(math.atan(112 / target["fy"]))
        self.assertAlmostEqual(fov, 2 * math.degrees(math.atan((540 / 2) / COLOR["fx"])), delta=0.2)
        self.assertGreater(fov, 30)
        self.assertLess(fov, 45)
        with self.assertRaisesRegex(r3.LeanS307Error, "color_size_unexpected"):
            r3.target_intrinsics(COLOR, (1280, 720))

    def test_upright_rgb_turns_clockwise_crops_and_scales(self) -> None:
        raw = np.zeros((540, 960, 3), dtype=np.uint8)
        raw[:20, :, 0] = 255   # top band of the sideways frame
        raw[-20:, :, 2] = 255  # bottom band
        out = r3.upright_rgb(raw)
        self.assertEqual(out.shape, (224, 224, 3))
        self.assertEqual(out.dtype, np.uint8)
        # turned clockwise, the raw top is the right edge and the raw bottom the left edge
        self.assertGreater(int(out[112, 222, 0]), 200)
        self.assertGreater(int(out[112, 1, 2]), 200)
        self.assertEqual(int(out[112, 112].sum()), 0)
        self.assertTrue(np.array_equal(out, r3.upright_rgb(raw)))
        with self.assertRaisesRegex(r3.LeanS307Error, "color_size_unexpected"):
            r3.upright_rgb(np.zeros((960, 540, 3), dtype=np.uint8))

    def test_converted_pose_round_trips_through_the_frozen_backprojection(self) -> None:
        """A point built through the raw OpenCV camera of a 3RScan pose is recovered by the frozen D-223 back-projection
        from the target pixel, target intrinsics and the converted relative pose -- for a reference frame and an aligned rescan."""

        target = r3.target_intrinsics(COLOR, (960, 540))
        origin_raw = rigid(rotation_about([0.2, 1.0, 0.1], 0.4), [0.3, -1.2, 1.4])
        _r0, origin_position, _res = r3.camera_pose(origin_raw)
        alignment = rigid(rotation_about([0, 0, 1], -0.6), [0.8, 0.4, 0.02])
        for raw_pose, aligned in ((rigid(rotation_about([1.0, -0.3, 0.6], 2.0), [2.0, 1.0, 1.3]), None),
                                  (rigid(rotation_about([0.1, 0.9, -0.4], -1.2), [-0.7, 2.2, 1.1]), alignment)):
            rotation, position, residual = r3.camera_pose(raw_pose, alignment=aligned)
            self.assertLess(residual, 1e-12)
            pose = r3.relative_pose(rotation, position, origin_position)
            self.assertEqual(pose["origin"], "observation_0_camera")
            self.assertTrue(np.allclose(pp.rotation_from_quaternion_xyzw(pose["quaternion_xyzw"]), rotation, atol=1e-12))
            u_t, v_t, z = 57, 160, 2.75
            point_target_camera = np.asarray([(u_t - target["cx"]) * z / target["fx"], (target["cy"] - v_t) * z / target["fy"], z])
            raw_camera_point = r3.Q.T @ r3.S @ point_target_camera
            world = raw_pose[:3, :3] @ raw_camera_point + raw_pose[:3, 3]
            if aligned is not None:
                world = aligned[:3, :3] @ world + aligned[:3, 3]
            expected = r3.to_project_world(world) - origin_position
            mask = np.zeros((224, 224), dtype=bool)
            mask[v_t, u_t] = True
            depth = np.full((224, 224), z, dtype=np.float32)
            frozen_pose = {key: pose[key] for key in ("position_m", "quaternion_xyzw")}
            recovered = og.backproject_mask(mask, depth, target, frozen_pose, minimum_depth_m=0.05, maximum_depth_m=20.0)
            self.assertEqual(recovered.shape, (1, 3))
            self.assertTrue(np.allclose(recovered[0], expected, atol=1e-6), (recovered[0], expected))

    def test_upright_pixels_sit_where_the_mapping_says(self) -> None:
        """A raw frame whose red and green channels encode u and v: after the turn, crop and box filter each target pixel
        carries (within quantisation) the raw coordinates ``target_to_raw_pixel`` names for its centre."""

        vv, uu = np.mgrid[0:540, 0:960].astype(np.float64)
        raw = np.zeros((540, 960, 3), dtype=np.uint8)
        raw[..., 0] = np.rint(uu * 255.0 / 959.0).astype(np.uint8)
        raw[..., 1] = np.rint(vv * 255.0 / 539.0).astype(np.uint8)
        out = r3.upright_rgb(raw).astype(np.float64)
        tv, tu = np.mgrid[0:224, 0:224].astype(np.float64)
        u_raw, v_raw = r3.target_to_raw_pixel(tu, tv, (960, 540))
        self.assertLess(float(np.max(np.abs(out[..., 0] * 959.0 / 255.0 - u_raw))), 6.0)
        self.assertLess(float(np.max(np.abs(out[..., 1] * 539.0 / 255.0 - v_raw))), 4.0)

    def test_roll_of_a_sideways_handheld_frame_ignores_pitch(self) -> None:
        """A phone held upright records a sideways raw frame (raw +x points down, world -Z).  Turned clockwise the image has no
        roll however far the camera looks down or up; the other turns read 0 or -1."""

        sideways = np.asarray([[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]])  # raw camera looking along world +X
        for pitch in (0.0, 0.5, 1.0, 1.3, -0.7):  # tilt about the raw camera's horizontal axis (raw y): + looks down, - up
            pose = rigid(sideways @ rotation_about([0.0, 1.0, 0.0], pitch), [1.0, 2.0, 1.5])
            rotation, _position, _res = r3.camera_pose(pose)
            self.assertAlmostEqual(r3.image_roll_cosine(rotation), 1.0, places=9)
            self.assertTrue(np.allclose(rotation, r3.turned_rotation(pose, "clockwise_90")))
            self.assertAlmostEqual(r3.image_roll_cosine(r3.turned_rotation(pose, "none")), 0.0, places=9)
            self.assertAlmostEqual(r3.image_roll_cosine(r3.turned_rotation(pose, "counterclockwise_90")), -1.0, places=9)
            self.assertAlmostEqual(r3.image_roll_cosine(r3.turned_rotation(pose, "half_turn")), 0.0, places=9)
        straight_down = rigid(sideways @ rotation_about([0.0, 1.0, 0.0], math.pi / 2), [1.0, 2.0, 1.5])
        self.assertTrue(math.isnan(r3.image_roll_cosine(r3.camera_pose(straight_down)[0])))

    def test_world_up_becomes_project_up(self) -> None:
        self.assertTrue(np.allclose(r3.to_project_world([0.0, 0.0, 1.0]), [0.0, 1.0, 0.0]))
        self.assertAlmostEqual(float(np.linalg.det(r3.W)), -1.0)
        self.assertAlmostEqual(float(np.linalg.det(r3.S)), -1.0)
        self.assertAlmostEqual(float(np.linalg.det(r3.Q)), 1.0)

    def test_sensor_depth_follows_the_registered_intrinsics(self) -> None:
        depth = np.full((172, 224), 1500, dtype=np.uint16)
        depth[:, 100:124] = 0  # a hole in the raw middle columns = middle rows of the upright target (rows about 90-133)
        out = r3.sensor_depth_on_target(depth, depth_shift=1000.0, depth_intrinsics=DEPTH, color_intrinsics=COLOR,
                                        color_size_wh=(960, 540))
        self.assertEqual(out.shape, (224, 224))
        self.assertEqual(out.dtype, np.float32)
        for row in (30, 200):
            self.assertAlmostEqual(float(out[row, 112]), 1.5, places=6)
        for column in (5, 112, 218):
            self.assertEqual(float(out[112, column]), r3.INVALID_DEPTH_M)
        self.assertTrue(set(np.unique(out).tolist()) <= {0.0, 1.5})


class TruthTests(unittest.TestCase):
    def test_object_keys_scope_through_the_frozen_rule(self) -> None:
        wall = r3.object_key(3, "wall", 1)
        floor = r3.object_key(5, "floor", 2)
        chair = r3.object_key(12, "office chair", 5)
        odd = r3.object_key(13, "window", 38)  # a label that reads as a prefix but whose class is not structural
        cased = r3.object_key(14, "Wall", 38)  # prefixes are case-sensitive: "Wall" is not the evaluator's "wall"
        self.assertEqual((wall, floor, chair, odd, cased),
                         ("wall|3", "room|5", "office_chair|12", "obj_window|13", "Wall|14"))
        self.assertFalse(lt.in_truth_node_scope(wall, observable_before=True))
        self.assertFalse(lt.in_truth_node_scope(floor, observable_before=True))
        for key in (chair, odd, cased):
            self.assertTrue(lt.in_truth_node_scope(key, observable_before=True))
        self.assertFalse(lt.is_spawned_after_reload(chair))

    def test_object_box_swaps_axes_and_needs_a_registered_layout(self) -> None:
        obb = {"centroid": [1.0, 2.0, 3.0], "axesLengths": [0.4, 0.6, 1.0], "normalizedAxes": [1, 0, 0, 0, 1, 0, 0, 0, 1]}
        result = r3.object_box(obb, layout="rows")
        self.assertTrue(np.allclose(result["centroid_m"], [1.0, 3.0, 2.0]))
        self.assertTrue(np.allclose(result["size_m"], [0.4, 1.0, 0.6]))
        turned = dict(obb, normalizedAxes=list(rotation_about([0, 0, 1], 0.5).reshape(-1)))
        rows = r3.object_box(turned, layout="rows")
        columns = r3.object_box(turned, layout="columns")
        self.assertTrue(np.allclose(rows["centroid_m"], columns["centroid_m"]))
        aligned = r3.object_box(obb, layout="rows", alignment=rigid(np.eye(3), [0.5, 0.0, 0.0]))
        self.assertTrue(np.allclose(aligned["centroid_m"], [1.5, 3.0, 2.0]))
        with self.assertRaisesRegex(r3.LeanS307Error, "obb_axes_layout_not_registered"):
            r3.object_box(obb, layout=None)

    def test_change_classification_follows_ruling_111_3(self) -> None:
        reference = {i: box([i, 0.5, 0.0], [0.4, 0.8, 0.4]) for i in range(1, 9)}
        reference[10] = box([0, 1.5, 3], [6, 3, 0.1])  # a wall
        rescan = {i: box([i, 0.5, 0.0], [0.4, 0.8, 0.4]) for i in (3, 4, 5, 6, 7, 8)}
        rescan[3] = box([3.0, 0.5, 1.2], [0.4, 0.8, 0.4])   # rigid, 1.2 m: move
        rescan[4] = box([4.0, 0.5, 0.1], [0.4, 0.8, 0.4])   # rigid, 0.1 m: small
        rescan[5] = box([5.0, 0.5, 1.2], [0.4, 0.8, 0.4])   # rigid, 1.2 m, but ambiguous
        rescan[7] = box([7.0, 0.5, 2.0], [0.4, 0.8, 0.4])   # in no list, 2 m away
        rescan[9] = box([9.0, 0.5, 0.0], [0.3, 0.3, 0.3])   # only in the rescan: add
        rescan[11] = box([0.0, 1.5, -3.0], [6, 3, 0.1])     # a structural object only in the rescan
        changes = {"removed": [1, 10], "nonrigid": [6], "rigid": [(3, 3), (4, 4), (5, 5)], "ambiguity": [5, 99]}
        result = r3.classify_changes(reference, rescan, changes, structural=[10, 11])
        self.assertEqual(result["outcomes"], {"1": "remove", "2": "remove_unlisted", "3": "move", "4": "small_rigid",
                                              "5": "ambiguous_rigid", "6": "nonrigid", "7": "unlisted_displacement",
                                              "9": "add", "10": "structural_change_ignored", "11": "structural_change_ignored"})
        self.assertEqual([(row["object_id"], row["kind"]) for row in result["interventions"]],
                         [(1, "remove"), (2, "remove"), (3, "move"), (9, "add")])
        self.assertEqual(result["interventions"][2]["point"], rescan[3]["centroid_m"])
        self.assertIsNone(result["interventions"][0]["point"])
        self.assertEqual(result["counts"]["remove_unlisted"], 1)
        self.assertEqual(sum(result["counts"].values()), 10)

    def test_a_large_object_moved_within_its_own_box_is_not_a_move(self) -> None:
        """The same ruler as the node column: a sofa shifted 0.6 m keeps its old centre inside the new box (+0.25 m)."""

        reference = {1: box([0.0, 0.4, 0.0], [2.2, 0.8, 0.9])}
        rescan = {1: box([0.6, 0.4, 0.0], [2.2, 0.8, 0.9])}
        result = r3.classify_changes(reference, rescan, {"removed": [], "nonrigid": [], "rigid": [(1, 1)], "ambiguity": []},
                                     structural=[])
        self.assertEqual(result["outcomes"], {"1": "small_rigid"})
        holds, distance, test = lt.place_holds(r3._place_state(reference[1])["centroid_m"], r3._place_state(rescan[1]),
                                               delta_moved_m=lt.DELTA_MOVED_M)
        self.assertTrue(holds and test == "padded_box" and distance > lt.DELTA_MOVED_M)

    def test_contradictory_change_entries_refuse_the_pair(self) -> None:
        reference = {1: box([0, 0, 0], [1, 1, 1]), 2: box([2, 0, 0], [1, 1, 1])}
        rescan = {1: box([0, 0, 0], [1, 1, 1]), 2: box([2, 0, 0], [1, 1, 1])}
        base = {"removed": [], "nonrigid": [], "rigid": [], "ambiguity": []}
        for changes, code in ((dict(base, removed=[1]), "removed_instance_present_in_rescan:1"),
                              (dict(base, rigid=[(3, 3)]), "rigid_reference_instance_missing:3"),
                              (dict(base, rigid=[(1, 1), (1, 2)]), "rigid_instance_listed_twice:1"),
                              (dict(base, rigid=[(1, 2)]), "rescan_instance_unresolved:1")):
            with self.assertRaisesRegex(r3.LeanS307Error, code):
                r3.classify_changes(reference, rescan, changes, structural=[])

    def test_episode_id_and_degenerate_window(self) -> None:
        ref, rescan = "095821f7-e2c2-2de1-9568-b9ce59920e29", "2e369567-e133-204c-909a-c5da44bb58df"
        self.assertEqual(r3.episode_id(ref, rescan), f"3rscan-{ref}-{rescan}")
        with self.assertRaisesRegex(r3.LeanS307Error, "scan_id_invalid"):
            r3.episode_id("procthor10k-0.1.2-train-00086", rescan)
        self.assertEqual(r3.degenerate_window(245), [244, 244])
        with self.assertRaisesRegex(r3.LeanS307Error, "reference_without_frames"):
            r3.degenerate_window(0)


class PublicFrameTests(unittest.TestCase):
    def test_frame_digest_equals_the_frozen_reader_recomputation(self) -> None:
        from PIL import Image

        import lean_s2_04_evaluate_episode as s204

        rng = np.random.default_rng(3)
        rgb = rng.integers(0, 256, (224, 224, 3), dtype=np.uint8)
        depth = rng.uniform(0.3, 5.0, (224, 224)).astype(np.float32)
        rotation, position, _res = r3.camera_pose(rigid(rotation_about([0, 1, 0], 0.3), [0.5, 0.2, 1.4]))
        pose = r3.relative_pose(rotation, position, position)
        digest = r3.frame_digest(rgb, depth, observation_index=4, relative_pose_record=pose, action_summary=r3.ACTION_SUMMARY)
        with tempfile.TemporaryDirectory() as tmp:
            public = Path(tmp)
            Image.fromarray(rgb).save(public / "0004.rgb.png")
            np.save(public / "0004.depth.npy", depth)
            record = {"observation_index": 4, "rgb_path": "0004.rgb.png", "depth_path": "0004.depth.npy",
                      "relative_pose": json.loads(json.dumps(pose)), "action_summary": dict(r3.ACTION_SUMMARY)}
            self.assertEqual(s204.recomputed_frame_digest(public, record, np.load(public / "0004.depth.npy")), digest)
        with self.assertRaisesRegex(r3.LeanS307Error, "digest_depth_invalid"):
            r3.frame_digest(rgb, depth.astype(np.float64), observation_index=4, relative_pose_record=pose,
                            action_summary=r3.ACTION_SUMMARY)


if __name__ == "__main__":
    unittest.main()
