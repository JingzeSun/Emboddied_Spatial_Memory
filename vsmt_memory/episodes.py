"""Reader for one released ProcTHOR episode (Hugging Face T1/T3), for the examples and the parity tests.

An episode restored by ``ops/vsmt/hf_fetch.py`` has a raw directory (``public/NNNN.frame.json``, ``.rgb.png``,
``.depth.npy``; a private and a provenance plane that this reader never opens) and one cache directory per front end
(``NNNN.cache.json.gz`` with ``NNNN.masks.npz``, ``episode_seal.json``).  The reader returns either the public frame
(RGB, depth, intrinsics, pose, and the cache's masks) for ``VSMTMemory.step``, or the sealed cache frame with its depth
view for ``VSMTMemory.step_cache_frame``, the way the audit runner reads them.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

import numpy as np

from . import _repo
from .conventions import CameraIntrinsics, CameraPose
from .frontend import public_depth_view, registered_asset
from vsmt import lean_frontend_cache as fc
from vsmt import lean_public_pose as pp

S1_03_CONTRACT = _repo.CONFIG_DIR / "lean_s1_03_frontend_cache_v1.json"
DESCRIPTOR_ASSET_IDS = {"vits14": "dinov2_vit_s14_checkpoint", "vitb14": "dinov2_vit_b14_checkpoint"}


class EpisodeError(ValueError):
    """A released episode that is incomplete or does not match its seals."""


def read_masks_file(path: Path) -> list[np.ndarray]:
    """The masks of one cache frame, in fragment order (packed bits, as the cache builder writes them)."""

    with np.load(path) as archive:
        count, height, width = (int(v) for v in archive["shape"])
        packed = archive["packed"]
    if not count:
        return []
    flat = np.unpackbits(packed, axis=1)[:, :height * width].astype(bool)
    return list(flat.reshape(count, height, width))


class HfEpisode:
    """One restored episode: ``raw_dir`` is ``.../s3-02-<tag>/<split>/<episode>``, ``cache_dir`` the same episode in
    ``.../s3-02-<instance|sam2>-<tag>/<split>/<episode>``."""

    def __init__(self, raw_dir: Path, cache_dir: Path) -> None:
        self.raw_dir, self.cache_dir = Path(raw_dir), Path(cache_dir)
        self.public_dir = self.raw_dir / "public"
        if not self.public_dir.is_dir() or not (self.cache_dir / "episode_seal.json").exists():
            raise EpisodeError(f"not a restored episode: {self.raw_dir} / {self.cache_dir}")
        self.episode_id = self.raw_dir.name
        self.code_commit = str(_repo.load_json(self.raw_dir / "receipt.json")["code_commit"])
        self.pose_policy = _repo.load_json(S1_03_CONTRACT)["public_pose_correction"]
        self.seal = _repo.load_json(self.cache_dir / "episode_seal.json")
        self.mask_source = fc.sealed_mask_source(self.seal)
        self.frame_count = int(self.seal["episode_frame_count"])

    def _record(self, index: int) -> dict[str, Any]:
        return _repo.load_json(self.public_dir / f"{index:04d}.frame.json")

    def public_frame(self, index: int) -> dict[str, Any]:
        """RGB, depth, intrinsics and causal pose of frame ``index`` (0-based), plus the cache's masks of that frame."""

        from PIL import Image

        record = self._record(index)
        with Image.open(self.public_dir / record["rgb_path"]) as image:
            rgb = np.asarray(image, dtype=np.uint8)
        depth = np.load(self.public_dir / record["depth_path"]).astype(np.float32)
        pose = pp.public_camera_pose(record, code_commit=self.code_commit, policy=self.pose_policy)
        k = record["intrinsics"]
        return {"rgb": rgb, "depth_m": depth,
                "intrinsics": CameraIntrinsics(fx=k["fx"], fy=k["fy"], cx=k["cx"], cy=k["cy"],
                                               width=depth.shape[1], height=depth.shape[0]),
                "pose": CameraPose(position_m=tuple(pose["position_m"]), quaternion_xyzw=tuple(pose["quaternion_xyzw"])),
                "masks": read_masks_file(self.cache_dir / f"{index:04d}.masks.npz")}

    def cache_frame(self, index: int, *, verify_seal: bool = True) -> dict[str, Any]:
        """The sealed cache frame of ``index`` with its public depth view attached, as the audit runner reads it."""

        with gzip.open(self.cache_dir / f"{index:04d}.cache.json.gz", "rb") as handle:
            frame = json.loads(handle.read().decode("utf-8"))
        if verify_seal:
            digests = {name: registered_asset(asset)["sha256"] for name, asset in DESCRIPTOR_ASSET_IDS.items()}
            fc.verify_frame_seal(frame, frontend_config_sha256=fc.D223_FRONTEND_CONFIG_SHA256,
                                 descriptor_asset_sha256s=digests)
        record = self._record(index)
        if record["frame_digest"] != frame["frame_digest"]:
            raise EpisodeError(f"frame {index}: the cache frame and the public frame differ")
        masks = read_masks_file(self.cache_dir / f"{index:04d}.masks.npz")
        if len(masks) != len(frame["fragments"]):
            raise EpisodeError(f"frame {index}: {len(masks)} masks for {len(frame['fragments'])} fragments")
        by_fragment = {}
        for mask, fragment in zip(masks, frame["fragments"]):
            if fc.mask_sha256_of(mask) != fragment["mask_sha256"]:
                raise EpisodeError(f"frame {index}: a mask does not reproduce {fragment['fragment_id']}")
            by_fragment[str(fragment["fragment_id"])] = mask
        depth = np.load(self.public_dir / record["depth_path"]).astype(np.float32)
        pose = pp.public_camera_pose(record, code_commit=self.code_commit, policy=self.pose_policy)
        frame["public_depth_view"] = public_depth_view(record["frame_digest"], depth, record["intrinsics"], pose,
                                                       by_fragment)
        return frame


__all__ = ["EpisodeError", "HfEpisode", "read_masks_file"]
