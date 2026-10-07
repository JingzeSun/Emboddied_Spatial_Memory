"""S3-07 (ruling 111-8 step 4): pair assembly (lean_s3_07_episode) and the converter (ops/vsmt/s3_07_convert.py).

The end-to-end case builds a synthetic 3RScan scene -- a reference and one rescan, each with its own annotated mesh, semseg
OBBs, a sequence.zip (info, poses, JPEG colour, 16-bit PGM depth) and a 3RScan.json entry with an alignment, a removal and a
rigid move -- renders both scans with the real renderer, runs the sample check, converts the pair, and reads the episode back
with the frozen readers (reader-check).  No 3RScan bytes are used.
"""

from __future__ import annotations

import copy
import io
import json
import math
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for item in (ROOT / "src", ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import s3_07_convert as convert  # noqa: E402
import s3_07_render as render_cli  # noqa: E402
from vsmt import lean_s3_07_3rscan as r3  # noqa: E402
from vsmt import lean_s3_07_episode as ep  # noqa: E402

REFERENCE = "0aaaaaaa-0000-0000-0000-000000000001"
RESCAN = "0aaaaaaa-0000-0000-0000-000000000002"
LABELS = {"floor": 2, "lamp": 35, "chair": 5, "cup": 40, "box": 40}
INFO = """m_colorWidth = 960
m_colorHeight = 540
m_depthWidth = 224
m_depthHeight = 172
m_depthShift = 1000
m_calibrationColorIntrinsic = 877.5 0 479.75 0 0 877.5 269.75 0 0 0 1 0 0 0 0 1
m_calibrationColorExtrinsic = 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1
m_calibrationDepthIntrinsic = 204.75 0 111.69 0 0 280.93 85.66 0 0 0 1 0 0 0 0 1
m_calibrationDepthExtrinsic = 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1
"""


def rotation_about(axis, angle):
    axis = np.asarray(axis, dtype=float) / np.linalg.norm(axis)
    k = np.asarray([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    return np.eye(3) + math.sin(angle) * k + (1 - math.cos(angle)) * k @ k


def rigid(rotation, translation):
    m = np.eye(4)
    m[:3, :3] = rotation
    m[:3, 3] = translation
    return m


#: rescan -> reference; the rescan's own files are expressed through its inverse
ALIGNMENT = rigid(rotation_about([0, 0, 1], 0.17), [0.3, -0.2, 0.0])
TO_RESCAN = np.linalg.inv(ALIGNMENT)
#: a phone held upright records a sideways frame: raw +x points down; the camera looks along +X, tilted 25 deg down
LOOK = np.asarray([[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]]) @ rotation_about([0.0, 1.0, 0.0], 0.45)
#: objects in the reference frame (Z up): id -> (label, centre, size); the chair moves 1.26 m, the cup goes, the box comes
REFERENCE_OBJECTS = {1: ("floor", (0.5, 0.0, -0.005), (7.0, 6.0, 0.01)), 2: ("lamp", (1.0, -0.8, 0.4), (0.3, 0.3, 0.8)),
                     3: ("chair", (1.0, 0.6, 0.45), (0.5, 0.5, 0.9)), 4: ("cup", (0.6, 0.0, 0.1), (0.2, 0.2, 0.2))}
RESCAN_OBJECTS = {1: REFERENCE_OBJECTS[1], 2: REFERENCE_OBJECTS[2], 3: ("chair", (2.2, 1.0, 0.45), (0.5, 0.5, 0.9)),
                  5: ("box", (1.6, -0.2, 0.25), (0.4, 0.4, 0.5))}
CAMERAS = {REFERENCE: [(-2.0, y, 1.4) for y in (-0.3, 0.0, 0.3)], RESCAN: [(-2.0, y, 1.4) for y in (-0.1, 0.2)]}


def cuboid(centre, size, rotation=np.eye(3)):
    half = np.asarray(size) / 2.0
    corners = np.asarray([[sx, sy, sz] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)], dtype=float) * half
    vertices = corners @ rotation.T + np.asarray(centre)
    faces = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4),
             (1, 5, 7), (1, 7, 3)]
    return vertices, faces


def write_scan(root: Path, scan: str, objects: dict, to_scan: np.ndarray) -> None:
    from PIL import Image

    directory = root / scan
    directory.mkdir(parents=True)
    rotation_scan = to_scan[:3, :3]
    vertices, faces, ids, groups = [], [], [], []
    for oid, (label, centre, size) in objects.items():
        local_centre = rotation_scan @ np.asarray(centre) + to_scan[:3, 3]
        v, f = cuboid(local_centre, size, rotation_scan)
        base = len(vertices)
        vertices.extend(v.tolist())
        faces.extend([(a + base, b + base, c + base) for a, b, c in f])
        ids.extend([oid] * 8)
        groups.append({"id": oid, "objectId": oid, "label": label, "segments": [],
                       "obb": {"centroid": local_centre.tolist(), "axesLengths": list(size),
                               "normalizedAxes": rotation_scan.T.reshape(-1).tolist()}})  # rows = the box's axes
    header = ["ply", "format ascii 1.0", f"element vertex {len(vertices)}", "property float x", "property float y",
              "property float z", "property ushort objectId", f"element face {len(faces)}", "property list uchar uint vertex_indices",
              "end_header"]
    rows = [f"{x:.9f} {y:.9f} {z:.9f} {oid}" for (x, y, z), oid in zip(vertices, ids)] + [f"3 {a} {b} {c}" for a, b, c in faces]
    (directory / "labels.instances.annotated.v2.ply").write_text("\n".join(header + rows) + "\n", encoding="ascii")
    (directory / "semseg.v2.json").write_text(json.dumps({"scan_id": scan, "segGroups": groups}), encoding="utf-8")
    rng = np.random.default_rng(len(objects))
    with zipfile.ZipFile(directory / "sequence.zip", "w") as archive:
        archive.writestr("_info.txt", INFO)
        for index, position in enumerate(CAMERAS[scan]):
            pose = to_scan @ rigid(LOOK, position)
            archive.writestr(f"frame-{index:06d}.pose.txt", "\n".join(" ".join(f"{v:.9f}" for v in row) for row in pose))
            colour = io.BytesIO()
            Image.fromarray(rng.integers(0, 256, (540, 960, 3), dtype=np.uint8)).save(colour, format="JPEG")
            archive.writestr(f"frame-{index:06d}.color.jpg", colour.getvalue())
            depth = np.full((172, 224), 1800, dtype=">u2")
            depth[:, :8] = 0
            archive.writestr(f"frame-{index:06d}.depth.pgm", b"P5\n224 172\n65535\n" + depth.tobytes())


def meta_entry() -> list[dict]:
    return [{"reference": REFERENCE, "type": "validation", "ambiguity": [],
             "scans": [{"reference": RESCAN, "transform": ALIGNMENT.T.reshape(-1).tolist(), "removed": [4], "nonrigid": [],
                        "rigid": [{"instance_reference": 3, "instance_rescan": 3, "symmetry": 0, "transform": [0] * 16}]}]},
            {"reference": "ffffffff-0000-0000-0000-000000000009", "type": "test", "ambiguity": [], "scans": []}]


class EndToEndTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.scans = self.root / "scans"
        write_scan(self.scans, REFERENCE, REFERENCE_OBJECTS, np.eye(4))
        write_scan(self.scans, RESCAN, RESCAN_OBJECTS, TO_RESCAN)
        self.meta = self.root / "3RScan.json"
        self.meta.write_text(json.dumps(meta_entry()))
        self.render = self.root / "render-sample"
        for scan in (REFERENCE, RESCAN):
            row = render_cli.render_scan({"scan": scan, "scans_root": str(self.scans), "out_dir": str(self.render / scan),
                                          "commit": "0" * 40, "contract_sha256": "0" * 64, "purpose": "sample"})
            self.assertEqual(row["status"], "succeeded", row)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_sample_check_then_conversion_then_frozen_readers(self) -> None:
        meta = json.loads(self.meta.read_text())
        report = convert.sample_check(self.scans, meta, LABELS)
        self.assertEqual(report["slots"], {"alignment_translation_unit": "m", "obb_axes_layout": "rows",
                                           "image_rotation_confirmed": True, "ambiguity_structure_confirmed": True})
        self.assertLess(report["translation_unit"][RESCAN]["m"], 1e-6)
        self.assertGreater(report["translation_unit"][RESCAN]["mm"], 0.2)
        self.assertGreater(report["rotation"][REFERENCE]["medians"]["clockwise_90"], 0.99)
        slots_path = self.root / "sample_check.json"
        slots_path.write_text(json.dumps(report))
        out, geometry = self.root / "episodes-sample", self.root / "geometry-sample"
        argv = ["convert", "--scans-root", str(self.scans), "--meta", str(self.meta), "--labels", "unused.csv",
                "--render-root", str(self.render), "--out-root", str(out), "--geometry-root", str(geometry), "--purpose", "sample",
                "--workers", "1", "--worker-basis", "test", "--slots-from", str(slots_path)]
        with mock.patch.object(convert, "load_labels", return_value=LABELS):
            self.assertEqual(convert.main(argv), 0)
        episode = r3.episode_id(REFERENCE, RESCAN)
        receipt = json.loads((out / episode / "receipt.json").read_text())
        self.assertEqual((receipt["status"], receipt["observations"], receipt["frames_reference"], receipt["window"]),
                         ("succeeded", 5, 3, [2, 2]))
        self.assertEqual(receipt["interventions"], {"remove": 1, "move": 1, "add": 1})
        self.assertEqual((receipt["source_index"], receipt["house_id"]), (0, REFERENCE))
        log = json.loads((out / episode / "provenance" / "interventions.json").read_text())
        self.assertEqual([(row["object_id"], row["kind"]) for row in log["executed"]],
                         [("chair|3", "move"), ("cup|4", "remove"), ("box|5", "add")])  # reference ids, then additions
        table = json.loads((geometry / episode / "object_geometry.json").read_text())
        self.assertEqual([row["object_id"] for row in table["objects"]], ["box|5", "chair|3", "cup|4", "lamp|2"])  # floor out
        moved = log["executed"][0]["point"]
        self.assertTrue(np.allclose(moved, r3.to_project_world([2.2, 1.0, 0.45]), atol=1e-6))  # aligned, axes swapped
        last_private = json.loads((out / episode / "private" / "0004.frame.json").read_text())
        self.assertNotIn("cup|4", last_private["object_id_to_entity_id"])
        first_private = json.loads((out / episode / "private" / "0000.frame.json").read_text())
        self.assertIn("room|1", first_private["object_id_to_entity_id"])  # the floor is rendered, structural, out of scope
        self.assertEqual(json.loads(self.meta.read_text())[0]["reference"], REFERENCE)
        diagnostics = receipt["diagnostics"]
        self.assertEqual((diagnostics["frames_over_64_regions"], diagnostics["frames_with_mesh_support_failure"]), (0, 0))
        self.assertLess(diagnostics["sensor_valid_share_mean"], 1.0)  # the synthetic sensor hole
        check = convert.reader_check_episode(out / episode, geometry)
        self.assertTrue(check["passed"], check)
        self.assertEqual((check["frames"], check["interventions"], check["window"]), (5, 3, [2, 2]))
        # resume keeps the converted pair; an interrupted one (no receipt) is redone with the same frame digests
        digests = receipt["frame_digests_sha256"]
        (out / episode / "receipt.json").unlink()
        with mock.patch.object(convert, "load_labels", return_value=LABELS):
            self.assertEqual(convert.main(argv), 2)  # existing output without --resume
            self.assertEqual(convert.main(argv + ["--resume"]), 0)
        self.assertEqual(json.loads((out / episode / "receipt.json").read_text())["frame_digests_sha256"], digests)

    def test_refusals(self) -> None:
        base = ["convert", "--scans-root", str(self.scans), "--meta", str(self.meta), "--labels", "x", "--render-root",
                str(self.render), "--workers", "1"]
        with mock.patch.object(convert, "load_labels", return_value=LABELS):
            self.assertEqual(convert.main(base + ["--out-root", str(self.root / "e"), "--geometry-root", str(self.root / "g"),
                                                  "--purpose", "sample"]), 2)  # roots must end in -sample
            emptied = r3.load_contract()
            emptied["sample_check"] = {name: None for name in r3.SAMPLE_CHECK_SLOTS}
            with mock.patch.object(convert.r3, "load_contract", return_value=emptied):
                self.assertEqual(convert.main(base + ["--out-root", str(self.root / "e-sample"), "--geometry-root",
                                                      str(self.root / "g-sample"), "--purpose", "sample"]), 2)  # slots null
            closed = r3.load_contract()
            closed["authorization"]["formal_conversion"] = False
            with mock.patch.object(convert.r3, "load_contract", return_value=closed):
                self.assertEqual(convert.main(base + ["--out-root", str(self.root / "e"), "--geometry-root", str(self.root / "g"),
                                                      "--purpose", "formal"]), 2)  # formal closed
        from vsmt import lean_test_seal

        sealed = self.root / "sealed-test-root"
        lean_test_seal.write_marker(sealed, kind="raw", state="sealed", seal_digest="0" * 64)
        with mock.patch.object(convert, "load_labels", return_value=LABELS):
            self.assertEqual(convert.main(base + ["--out-root", str(sealed / "e-sample"), "--geometry-root",
                                                  str(self.root / "g-sample"), "--purpose", "sample"]), 2)  # a sealed test root
        with self.assertRaisesRegex(r3.LeanS307Error, "label_mapping_digest_mismatch"):
            bad = self.root / "labels.csv"
            bad.write_text("Global ID,Label,,NYU40 Mapping\n")
            convert.load_labels(bad, r3.load_contract())


def box(centre, size):
    c, s = np.asarray(centre, dtype=float), np.asarray(size, dtype=float)
    return {"centroid_m": c.tolist(), "aabb_min_m": (c - s / 2).tolist(), "aabb_max_m": (c + s / 2).tolist(), "size_m": s.tolist()}


class EpisodeFunctionTests(unittest.TestCase):
    def test_keys_follow_the_reference_identity_and_flag_label_changes(self) -> None:
        reference = {3: {"label": "chair"}, 7: {"label": "floor"}}
        rescan = {3: {"label": "office chair"}, 9: {"label": "chair"}}
        keys = ep.object_keys(reference, rescan, {"chair": 5, "office chair": 5, "floor": 2}, {})
        self.assertEqual(keys["rescan"], {3: "chair|3", 9: "chair|9"})
        self.assertEqual((keys["label_changed"], keys["structural_reference"]), ([3], {7}))
        with self.assertRaisesRegex(ep.LeanS307EpisodeError, "label_not_in_mapping:sofa"):
            ep.object_keys({1: {"label": "sofa"}}, {}, {"chair": 5}, {})

    def test_private_record_lists_rendered_labels_and_counts_unknown_ones(self) -> None:
        image = np.zeros((224, 224), dtype=np.uint16)
        image[:100, :100] = 3
        image[150:, 150:] = 42  # no semseg object
        record, unknown = ep.private_record(7, image, key_of_label={3: "chair|3"}, position_of_key={"chair|3": [1, 2, 3]},
                                            frame_digest="a" * 64)
        self.assertEqual(record["object_id_to_entity_id"], {"chair|3": 3})
        self.assertEqual(record["object_visibility"], {"chair|3": 10000})
        self.assertEqual(record["object_poses"], {"chair|3": {"x": 1.0, "y": 2.0, "z": 3.0}})
        self.assertEqual((record["instance_mask_path"], unknown), ("0007.instance.png", {42: 74 * 74}))

    def test_frame_diagnostics_apply_the_frozen_support_rule(self) -> None:
        import lean_s1_03_cache as cache_runner

        geometry = cache_runner.geometry_config(cache_runner.frozen_frontend())
        image = np.zeros((224, 224), dtype=np.uint16)
        image[:50, :50] = 1   # 2,500 px
        image[100:105, :10] = 2  # 50 px, below the 196 px admission
        mesh = np.full((224, 224), 2.0, dtype=np.float32)
        sensor = mesh.copy()
        sensor[:50, :45] = 0.0  # 2,250 of the region's 2,500 px invalid: 250 valid < max(32, 625)
        out = ep.frame_diagnostics(image, mesh, sensor, labels=[1, 2], geometry=geometry)
        self.assertEqual((out["regions"], out["over_cap"], out["mesh_support_failures"], out["sensor_support_failures"]),
                         (1, False, 0, 1))
        self.assertAlmostEqual(out["mesh_minus_sensor_median_m"], 0.0)

    def test_layout_and_unit_checks_stop_when_the_evidence_is_weak(self) -> None:
        turn = rotation_about([0, 0, 1], 0.6)
        vertices, _faces = cuboid((0, 0, 0), (1.0, 0.2, 0.2), turn)
        objects = {5: {"obb": {"centroid": [0, 0, 0], "axesLengths": [1.0, 0.2, 0.2], "normalizedAxes": turn.T.reshape(-1).tolist()}}}
        dense = {5: np.concatenate([vertices + offset for offset in np.linspace(-0.001, 0.001, 5)[:, None]])}
        check = ep.obb_layout_check(objects, dense)
        self.assertEqual(check["chosen"], "rows")
        self.assertGreater(check["rows"], check["columns"])
        far = ep.translation_unit_check({2: np.zeros((3, 3))}, {2: np.full((3, 3), 5.0)}, [2], list(np.eye(4).reshape(-1)))
        self.assertIsNone(far["chosen"])
        self.assertFalse(ep.ambiguity_structure_ok([{"reference": "x", "ambiguity": [[{"source": 1}]]}])["passed"])

    def test_geometry_table_passes_the_frozen_validator(self) -> None:
        rows = [ep._table_row("chair|3", "chair", box([1, 0.4, 2], [0.5, 0.9, 0.5]))]
        table = ep.geometry_table(episode_id="3rscan-a-b", house_id="a", source_index=0, code_commit="0" * 40,
                                  origin_world_m=[0.1, 1.4, -2.0], rows=rows)
        self.assertEqual(table["objects"][0]["initial_aabb_size_m"], [0.5, 0.9, 0.5])
        broken = copy.deepcopy(rows)
        broken[0]["initial_aabb_size_m"] = [-1.0, 0.0, 0.0]
        with self.assertRaises(Exception):
            ep.geometry_table(episode_id="3rscan-a-b", house_id="a", source_index=0, code_commit="0" * 40,
                              origin_world_m=[0, 0, 0], rows=broken)
        self.assertEqual(ep.window_record(1), {"window": [0, 0], "frames": 0, "window_protocol": ep.WINDOW_PROTOCOL})


if __name__ == "__main__":
    unittest.main()
