"""S3-07 (ruling 111-8 step 3): the render entry ops/vsmt/s3_07_render.py on a synthetic scan directory."""

from __future__ import annotations

import json
import math
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for item in (ROOT / "src", ROOT / "ops" / "vsmt"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import s3_07_render as cli  # noqa: E402
from vsmt import lean_s3_07_render as rr  # noqa: E402

REFERENCE = "095821f7-0000-0000-0000-000000000001"
RESCAN = "095821f7-0000-0000-0000-000000000002"
INFO = """m_colorWidth = 960
m_colorHeight = 540
m_depthWidth = 224
m_depthHeight = 172
m_depthShift = 1000
m_calibrationColorIntrinsic = 877.5 0 479.75 0 0 877.5 269.75 0 0 0 1 0 0 0 0 1
m_calibrationDepthIntrinsic = 204.75 0 111.69 0 0 273.25 85.66 0 0 0 1 0 0 0 0 1
m_frames.size = 2
"""


def rotation_about(axis, angle):
    axis = np.asarray(axis, dtype=float) / np.linalg.norm(axis)
    k = np.asarray([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    return np.eye(3) + math.sin(angle) * k + (1 - math.cos(angle)) * k @ k


def pose(rotation, translation):
    m = np.eye(4)
    m[:3, :3] = rotation
    m[:3, 3] = translation
    return m


POSES = [pose(rotation_about([0, 0, 1], 0.2), [0.0, 0.0, 1.2]), pose(rotation_about([0, 0, 1], 0.25), [0.05, 0.0, 1.2])]


def write_scan(root: Path, scan: str, *, broken: bool = False) -> None:
    directory = root / scan
    directory.mkdir(parents=True)
    rc, tc = rr.world_to_camera(POSES[0])
    camera = np.asarray([(-4, -4, 2.0), (4, -4, 2.0), (4, 4, 2.0), (-4, 4, 2.0)], dtype=float)
    vertices = (camera - tc) @ rc
    header = ["ply", "format ascii 1.0", "element vertex 4", "property float x", "property float y", "property float z",
              "property ushort objectId", "element face 2", "property list uchar uint vertex_indices", "end_header"]
    rows = [f"{x:.9f} {y:.9f} {z:.9f} {label}" for (x, y, z), label in zip(vertices, (3, 3, 8, 8))]
    rows += ["3 0 1 2", "3 0 2 3"] if not broken else ["4 0 1 2 3"]
    (directory / "labels.instances.annotated.v2.ply").write_text("\n".join(header + rows) + "\n", encoding="ascii")
    with zipfile.ZipFile(directory / "sequence.zip", "w") as archive:
        archive.writestr("_info.txt", INFO)
        for index, matrix in enumerate(POSES):
            archive.writestr(f"frame-{index:06d}.pose.txt", "\n".join(" ".join(f"{v:.9f}" for v in row) for row in matrix))
            archive.writestr(f"frame-{index:06d}.color.jpg", b"not read by the renderer")


class RenderEntryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.scans = self.root / "scans"
        for scan in (REFERENCE, RESCAN):
            write_scan(self.scans, scan)
        self.meta = self.root / "3RScan.json"
        self.meta.write_text(json.dumps([
            {"reference": REFERENCE, "type": "validation", "ambiguity": [], "scans": [{"reference": RESCAN}]},
            {"reference": "ffffffff-0000-0000-0000-000000000009", "type": "validation", "ambiguity": [], "scans": []},
            {"reference": "00000000-0000-0000-0000-000000000000", "type": "train", "ambiguity": [], "scans": []}]))
        self.out = self.root / "render-sample"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_main(self, *extra: str, out: Path | None = None, purpose: str = "sample") -> int:
        return cli.main(["--scans-root", str(self.scans), "--meta", str(self.meta), "--out-root", str(out or self.out),
                         "--purpose", purpose, "--workers", "1", "--worker-basis", "test", *extra])

    def test_sample_render_writes_frames_and_receipts_and_resumes(self) -> None:
        self.assertEqual(cli.sample_scans(json.loads(self.meta.read_text())), [REFERENCE, RESCAN])
        self.assertEqual(self.run_main(), 0)
        receipt = json.loads((self.out / REFERENCE / "receipt.json").read_text())
        self.assertEqual((receipt["status"], receipt["frames"], receipt["mesh_faces"]), ("succeeded", 2, 2))
        from PIL import Image

        for row in receipt["per_frame"]:
            instance = np.asarray(Image.open(self.out / REFERENCE / f"{row['frame']}.instance.png"))
            depth = np.load(self.out / REFERENCE / f"{row['frame']}.depth.npy")
            self.assertEqual((instance.dtype, depth.dtype), (np.uint16, np.float32))
            self.assertEqual(cli.sha256_bytes(instance.tobytes()), row["instance_sha256"])
            self.assertEqual(cli.sha256_bytes(depth.tobytes()), row["depth_sha256"])
            self.assertEqual(set(np.unique(instance).tolist()), {3, 8})
        stage = json.loads((self.out / "render_receipt.json").read_text())
        self.assertEqual((stage["by_status"], stage["workers_requested"], stage["workers_actual"]), ({"succeeded": 2}, 1, 1))
        self.assertEqual(self.run_main(), 2)  # existing output without --resume
        digests = [row["depth_sha256"] for row in receipt["per_frame"]]
        (self.out / RESCAN / "receipt.json").unlink()  # an interrupted scan: cleared and redone
        self.assertEqual(self.run_main("--resume"), 0)
        stage = json.loads(sorted(self.out.glob("plan-*.json"))[-1].read_text())
        self.assertEqual((stage["kept"], stage["cleared_interrupted"]), ([REFERENCE], [RESCAN]))
        redone = json.loads((self.out / RESCAN / "receipt.json").read_text())
        self.assertEqual([row["depth_sha256"] for row in redone["per_frame"]], digests)  # same mesh, same poses, same bits

    def test_a_broken_scan_is_recorded_and_kept(self) -> None:
        broken = self.root / "broken"
        write_scan(broken, REFERENCE, broken=True)
        row = cli.render_scan({"scan": REFERENCE, "scans_root": str(broken), "out_dir": str(self.root / "x" / REFERENCE),
                               "commit": "0" * 40, "contract_sha256": "0" * 64, "purpose": "sample"})
        self.assertEqual(row["status"], "failed")
        self.assertIn("ply_face_not_triangle", row["reason"])
        self.assertTrue((self.root / "x" / REFERENCE / "receipt.json").exists())

    def test_refusals(self) -> None:
        self.assertEqual(self.run_main(out=self.root / "render-formal-like"), 2)  # sample needs a -sample root
        from unittest import mock

        closed = cli.r3.load_contract()
        closed["authorization"]["formal_conversion"] = False
        with mock.patch.object(cli.r3, "load_contract", return_value=closed):
            self.assertEqual(self.run_main(out=self.root / "render", purpose="formal"), 2)  # formal closed
