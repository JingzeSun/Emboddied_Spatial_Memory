"""The S1-03 runner's model-free parts: the on-disk frame format, the episode seal over written
frames, the camera axis, and the asset check refusing a digest that does not match its registry.

The models themselves run only on the server; nothing here loads torch, SAM 2.1 or DINOv2.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT / "src", PROJECT_ROOT / "ops" / "vsmt"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import lean_s1_03_cache as runner  # noqa: E402
from vsmt import lean_frontend_cache as fc  # noqa: E402


class FrameFileTests(unittest.TestCase):
    def test_a_written_frame_decodes_to_the_object_the_seal_covers(self) -> None:
        frame = {"tick": 1, "frame_digest": "a" * 64, "fragments": [], "frame_seal": {"payload_sha256": "b" * 64},
                 "camera_position_m": [0.0, 1.5, 0.25]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / f"0000{runner.FRAME_FILE_SUFFIX}"
            path.write_bytes(gzip.compress(json.dumps(frame).encode("utf-8"), compresslevel=6))
            self.assertEqual(runner.load_cache_frame(path), frame)
            self.assertTrue(path.name.endswith(".cache.json.gz"))

    def test_episode_seal_needs_only_tick_and_frame_seal_of_each_frame(self) -> None:
        full = [{"tick": i + 1, "frame_seal": {"payload_sha256": hashlib.sha256(bytes([i])).hexdigest()},
                 "fragments": [{"x": i}], "surfaces": []} for i in range(3)]
        reduced = [{"tick": f["tick"], "frame_seal": f["frame_seal"]} for f in full]
        digest = fc.D223_FRONTEND_CONFIG_SHA256
        self.assertEqual(fc.seal_episode(full, frontend_config_sha256=digest),
                         fc.seal_episode(reduced, frontend_config_sha256=digest))


class CameraForwardTests(unittest.TestCase):
    def test_identity_rotation_looks_along_positive_z(self) -> None:
        self.assertEqual(runner.camera_forward([0.0, 0.0, 0.0, 1.0]), [0.0, 0.0, 1.0])

    def test_quarter_turn_about_y_looks_along_positive_x(self) -> None:
        half = 2 ** -0.5
        forward = runner.camera_forward([0.0, half, 0.0, half])
        self.assertAlmostEqual(forward[0], 1.0, places=9)
        self.assertAlmostEqual(forward[1], 0.0, places=9)
        self.assertAlmostEqual(forward[2], 0.0, places=9)

    def test_a_non_unit_quaternion_is_refused_at_the_frozen_tolerance(self) -> None:
        for bad in ([0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0 + 1e-5], [float("nan"), 0.0, 0.0, 1.0]):
            with self.assertRaises(runner.CacheFailure):
                runner.camera_forward(bad)
        self.assertEqual(runner.camera_forward([0.0, 0.0, 0.0, 1.0 + 1e-7]), [0.0, 0.0, 1.0])


class AssetVerificationTests(unittest.TestCase):
    """A repository at the wrong commit or a checkpoint with the wrong digest is refused before
    any model is built; the digests the frames carry come from the bytes on disk."""

    def _repository(self, directory: Path) -> str:
        subprocess.run(["git", "init", "-q", str(directory)], check=True)
        (directory / "f").write_text("x")
        env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
               "GIT_COMMITTER_EMAIL": "t@t"}
        subprocess.run(["git", "-C", str(directory), "add", "f"], check=True)
        subprocess.run(["git", "-C", str(directory), "-c", "commit.gpgsign=false", "commit", "-q", "-m", "x"],
                       check=True, env={**dict(__import__("os").environ), **env})
        return subprocess.run(["git", "-C", str(directory), "rev-parse", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()

    def test_a_sam2_repository_at_another_commit_is_refused(self) -> None:
        contract = json.loads(runner.CONTRACT_PATH.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "sam2"
            repository.mkdir()
            self._repository(repository)
            assets = {"sam2_repository": str(repository), "sam2_checkpoint": str(repository / "f"),
                      "dinov2_repository": str(repository)}
            with self.assertRaises(runner.CacheFailure) as caught:
                runner.verify_assets(assets, contract)
            self.assertIn("not the pinned commit", caught.exception.detail)

    def test_file_sha256_matches_hashlib(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "blob"
            path.write_bytes(b"\x00\x01" * 1000)
            self.assertEqual(runner.file_sha256(path), hashlib.sha256(b"\x00\x01" * 1000).hexdigest())


if __name__ == "__main__":
    unittest.main()
