"""Front end: one RGB-D frame and its instance masks -> one frame in the format of the frozen front-end cache.

What happens to a frame, in the order of the frozen cache builder (``ops/vsmt/lean_s1_03_cache.py``):

1. the frame is brought to 224 x 224 (``conventions.resize_to_frame_size``);
2. the masks are admitted under the frozen proposal boundary (``lean_frontend_cache.admit_proposals``): at least 196
   pixels, at most 64 per frame, ordered by mask digest;
3. DINOv2 ViT-B/14 patch tokens are extracted once per frame and pooled under each mask
   (``l1_entities.extract_dinov2_patch_tokens``, ``l1_entities.pool_dinov2_region_descriptor``), with the pinned
   repository commit and checkpoint digest of the asset registry;
4. each fragment's centroid, box and valid-depth ratio come from the frozen back-projection
   (``l1_entities.backproject_public_entity_geometry``, ``lean_frontend_cache.fragment_aabb``);
5. the frame is sealed (``lean_frontend_cache.build_frame``) and its public depth view is attached
   (``lean_runner.fragment_surface_points``), as the audit readers do.

Differences from the frozen cache, all outside what the memory reads: only the ViT-B/14 descriptor is computed (the
memory reads the ReID projection of it; ViT-S/14 served only the frozen-descriptor baseline); the free-space,
visibility and surface records are not computed (the per-frame loop has derived entity geometry from the depth view
since ruling 74 and never reads them); and, unless ``strict=True``, a frame with more than 64 admitted masks is
skipped and a fragment without enough valid depth is dropped, where the cache builder failed the whole episode.
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np

from . import _repo
from .conventions import FRAME_SIZE, CameraIntrinsics, CameraPose, resize_to_frame_size
from cpmt.hashing import canonical_json
from vsmt import lean_frontend_cache as fc
from vsmt import lean_runner as lr
from vsmt.l1_entities import (DINORegionConfig, L1EntityConstructionError, PublicGeometryConfig,
                              backproject_public_entity_geometry, extract_dinov2_patch_tokens,
                              pool_dinov2_region_descriptor)
from vsmt.l1_masks import AnonymousMask

DESCRIPTOR_SET = "vitb14"
D223_CONTRACT = _repo.CONFIG_DIR / "vm04_d223_f01_production_reader_v1.json"
ASSET_REGISTRY = _repo.CONFIG_DIR / "lean_s1_assets_capacity_v2.json"
S1_03_CONTRACT = _repo.CONFIG_DIR / "lean_s1_03_frontend_cache_v1.json"
D215_CONTRACT = _repo.CONFIG_DIR / "vm04_d215_frontend_freeze_v1.json"

#: The seal of a plug-in frame names this front end, not the frozen cache's: the record omits ViT-S/14 and the volumes.
PLUGIN_FRONTEND_SHA256 = hashlib.sha256(canonical_json({
    "front_end": "vsmt_memory", "frozen_frontend_config_sha256": fc.D223_FRONTEND_CONFIG_SHA256,
    "descriptor_sets": [DESCRIPTOR_SET], "volumes": "not_computed"}).encode("utf-8")).hexdigest()


class FrontEndError(ValueError):
    """A frame the front end refuses (only raised with ``strict=True`` or for malformed input)."""


def frozen_configs() -> tuple[DINORegionConfig, PublicGeometryConfig]:
    """The descriptor and fragment-geometry configurations of the frozen front end, digest-checked."""

    frontend = _repo.load_json(D223_CONTRACT)["frontend"]
    if frontend["frontend_config_sha256"] != fc.D223_FRONTEND_CONFIG_SHA256:
        raise FrontEndError("the D-223 front-end contract no longer matches the digest the cache module binds")
    descriptor = DINORegionConfig(**{**frontend["descriptor"],
                                     "patch_token_dimension": fc.DESCRIPTOR_DIMENSIONS[DESCRIPTOR_SET]})
    return descriptor, PublicGeometryConfig(**frontend["fragment_geometry"])


def registered_asset(asset_id: str) -> dict[str, Any]:
    """One row of the S1-01 asset registry (source URL, pinned commit, byte size and SHA-256)."""

    rows = {row["asset_id"]: row for row in _repo.load_json(ASSET_REGISTRY)["asset_registry"]}
    return dict(rows[asset_id])


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_pinned_file(url: str, sha256: str, target: Path) -> Path:
    """Download ``url`` to ``target`` unless a file with the pinned digest is already there; refuse any other digest."""

    target = Path(target)
    if target.exists() and file_sha256(target) == sha256:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    with urllib.request.urlopen(url) as response, partial.open("wb") as handle:  # noqa: S310 (pinned https URL)
        while chunk := response.read(1 << 20):
            handle.write(chunk)
    if file_sha256(partial) != sha256:
        partial.unlink()
        raise FrontEndError(f"{url} does not have the pinned SHA-256 {sha256[:12]}")
    partial.replace(target)
    return target


class DinoV2Extractor:
    """Frozen DINOv2 ViT-B/14 patch tokens through the reviewed extractor.

    The model code is the DINOv2 repository at the commit the asset registry pins: either a local clone
    (``repository``) or ``torch.hub`` at that commit.  The checkpoint must have the registered SHA-256; when no path is
    given it is downloaded once from the registered URL into ``cache_dir`` (346 MB).
    """

    def __init__(self, *, cache_dir: Path, repository: Path | None = None, checkpoint: Path | None = None,
                 device: str = "cpu") -> None:
        import torch

        code = registered_asset("dinov2_repository")
        weights = registered_asset("dinov2_vit_b14_checkpoint")
        if checkpoint is None:
            checkpoint = fetch_pinned_file(weights["source_url"], weights["sha256"],
                                           Path(cache_dir) / "dinov2" / Path(weights["source_url"]).name)
        elif file_sha256(Path(checkpoint)) != weights["sha256"]:
            raise FrontEndError(f"{checkpoint} is not the registered DINOv2 ViT-B/14 checkpoint")
        if repository is not None:
            if str(repository) not in sys.path:
                sys.path.insert(0, str(repository))
            from dinov2.hub import backbones

            model = backbones.dinov2_vitb14(pretrained=False)
        else:
            model = torch.hub.load(f"facebookresearch/dinov2:{code['pinned_ref']}", "dinov2_vitb14", pretrained=False,
                                   trust_repo=True, skip_validation=True, verbose=False)
        state = torch.load(str(checkpoint), map_location="cpu", weights_only=True)
        model.load_state_dict(state, strict=True)
        self.model = model.requires_grad_(False).eval().to(device)
        self.device = device
        self.config, _ = frozen_configs()
        self.checkpoint_sha256 = weights["sha256"]

    def __call__(self, rgb: np.ndarray) -> np.ndarray:
        """Patch tokens (16, 16, 768) of one 224 x 224 uint8 RGB image."""

        return extract_dinov2_patch_tokens(self.model, rgb, self.config, device=self.device)


class Sam2MaskGenerator:
    """SAM 2.1 Hiera Small automatic masks with the frozen generator settings (optional dependency ``sam2``).

    The settings are D-215's with the two NMS thresholds of ruling 43, read from the S1-03 contract; the checkpoint must
    have the registered SHA-256 and is downloaded once into ``cache_dir`` when no path is given (184 MB).  The frozen
    cache used the ``sam2`` repository at commit ``2b90b9f5``; install that commit to reproduce its masks.
    """

    def __init__(self, *, cache_dir: Path, checkpoint: Path | None = None, device: str = "cpu") -> None:
        from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
        from sam2.build_sam import build_sam2

        weights = registered_asset("sam2_checkpoint")
        if checkpoint is None:
            checkpoint = fetch_pinned_file(weights["source_url"], weights["sha256"],
                                           Path(cache_dir) / "sam2" / Path(weights["source_url"]).name)
        elif file_sha256(Path(checkpoint)) != weights["sha256"]:
            raise FrontEndError(f"{checkpoint} is not the registered SAM 2.1 Hiera Small checkpoint")
        registered = _repo.load_json(D215_CONTRACT)["sam2"]["official_model_config_path"]
        hydra_name = registered.split("/", 1)[1] if registered.startswith("sam2/") else registered
        settings = _repo.load_json(S1_03_CONTRACT)["sam2_nms_supersession"]["effective_automatic_mask_generator"]
        self.generator = SAM2AutomaticMaskGenerator(build_sam2(hydra_name, str(checkpoint), device=device), **settings)

    def __call__(self, rgb: np.ndarray) -> list[np.ndarray]:
        return [np.asarray(row["segmentation"], dtype=bool) for row in self.generator.generate(rgb)]


@dataclass
class BuiltFrame:
    """One frame in the cache format, or the reason it was skipped."""

    cache_frame: dict[str, Any] | None
    fragment_to_mask: dict[str, int] = field(default_factory=dict)
    dropped_masks: list[tuple[int, str]] = field(default_factory=list)
    skipped_reason: str | None = None
    calibration: dict[str, float] | None = None
    pose: dict[str, list[float]] | None = None


def anonymous_mask(mask: np.ndarray, ordinal: int) -> AnonymousMask:
    """The anonymous mask record the frozen admission reads (same digest as the cache builder's)."""

    binary = np.ascontiguousarray(np.asarray(mask, dtype=bool))
    values = binary.reshape(-1).astype(np.uint8)
    return AnonymousMask(region_id=f"region:{ordinal:04d}", mask_sha256=fc.mask_sha256_of(binary),
                         height=int(binary.shape[0]), width=int(binary.shape[1]),
                         row_major_values=tuple(int(v) for v in values), visible_pixel_count=int(values.sum()),
                         touches_border=bool(binary[0].any() or binary[-1].any() or binary[:, 0].any()
                                             or binary[:, -1].any()))


def camera_forward(quaternion_xyzw: Sequence[float]) -> list[float]:
    """The camera's +z axis in the world, normalised, by the cache builder's formula
    (``ops/vsmt/lean_s1_03_cache.camera_forward``); the existence features read it.  Across numpy builds the norm can
    differ in the last bit."""

    x, y, z, w = (float(v) for v in quaternion_xyzw)
    forward = np.array([2 * (x * z + y * w), 2 * (y * z - x * w), 1 - 2 * (x * x + y * y)])
    return [float(v) for v in forward / float(np.linalg.norm(forward))]


def frame_digest_of(rgb: np.ndarray, depth_m: np.ndarray, tick: int) -> str:
    """A 64-hex digest of the frame's bytes; the per-frame loop uses it to tie the depth view to the frame."""

    payload = {"rgb": hashlib.sha256(np.ascontiguousarray(rgb).tobytes()).hexdigest(),
               "depth": hashlib.sha256(np.ascontiguousarray(depth_m).tobytes()).hexdigest(), "tick": int(tick)}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def public_depth_view(frame_digest: str, depth_m: np.ndarray, calibration: dict[str, float],
                      pose: dict[str, list[float]], masks_by_fragment: dict[str, np.ndarray]) -> dict[str, Any]:
    """The view ``lean_runner.run_frame`` reads for entity geometry (rulings 74 and 75), fields in the frozen order."""

    view: dict[str, Any] = {"frame_digest": frame_digest, "depth_m": np.asarray(depth_m, dtype=np.float32),
                            "calibration": calibration, "pose": pose}
    view["fragment_surface_points"] = {fragment_id: lr.fragment_surface_points(mask, view)
                                       for fragment_id, mask in masks_by_fragment.items()}
    return view


def build_frame(
    *, tick: int, rgb: np.ndarray, depth_m: np.ndarray, intrinsics: CameraIntrinsics, pose: CameraPose,
    masks: Sequence[np.ndarray], patch_tokens: Callable[[np.ndarray], np.ndarray], strict: bool = False,
) -> BuiltFrame:
    """Turn one frame into the cache record the per-frame loop consumes, with its public depth view attached.

    ``masks`` are boolean arrays of the image size, one per object instance, in any order; the returned
    ``fragment_to_mask`` maps each fragment ID to the index of its mask in this list.  ``patch_tokens`` maps a
    224 x 224 uint8 RGB image to DINOv2 ViT-B/14 patch tokens (``DinoV2Extractor``).
    """

    rgb = np.asarray(rgb)
    depth = np.asarray(depth_m, dtype=np.float32)
    if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.dtype != np.uint8:
        raise FrontEndError("rgb must be a uint8 array of shape (H, W, 3)")
    if depth.shape != rgb.shape[:2] or (intrinsics.height, intrinsics.width) != depth.shape:
        raise FrontEndError("rgb, depth and intrinsics must describe the same image size")
    if any(np.asarray(m).shape != depth.shape for m in masks):
        raise FrontEndError("every mask must have the image size")
    rgb, depth, masks, intrinsics = resize_to_frame_size(rgb, depth, list(masks), intrinsics)
    calibration, pose_record = intrinsics.as_calibration(), pose.as_pose()
    descriptor_config, geometry_config = frozen_configs()

    # admission: identical masks are one proposal (the cache builder failed the episode on a duplicate)
    first_index: dict[str, int] = {}
    anonymous: list[AnonymousMask] = []
    dropped: list[tuple[int, str]] = []
    for index, mask in enumerate(masks):
        record = anonymous_mask(mask, index)
        if record.mask_sha256 in first_index:
            if strict:
                raise FrontEndError(f"duplicate_proposal_mask: masks {first_index[record.mask_sha256]} and {index}")
            dropped.append((index, "duplicate_mask"))
            continue
        first_index[record.mask_sha256] = index
        if record.visible_pixel_count < fc.MINIMUM_VISIBLE_PIXELS:
            dropped.append((index, "below_196_pixels"))
        anonymous.append(record)
    try:
        admitted = fc.admit_proposals(anonymous)
    except fc.LeanFrontendCacheError as exc:
        if strict:
            raise FrontEndError(str(exc)) from exc
        return BuiltFrame(cache_frame=None, dropped_masks=dropped, skipped_reason=exc.reason,
                          calibration=calibration, pose=pose_record)

    tokens = patch_tokens(rgb) if admitted else None
    rows: list[dict[str, Any]] = []
    fragment_masks: dict[str, np.ndarray] = {}
    fragment_to_mask: dict[str, int] = {}
    for record in admitted:
        mask = record.as_array()
        try:
            geometry = backproject_public_entity_geometry(mask, depth, calibration, pose_record, geometry_config)
            lower, upper = fc.fragment_aabb(mask, depth, calibration, pose_record, geometry_config)
        except (L1EntityConstructionError, fc.LeanFrontendCacheError) as exc:
            if strict:
                raise FrontEndError(f"fragment_depth_support_insufficient: mask {first_index[record.mask_sha256]}") from exc
            dropped.append((first_index[record.mask_sha256], "insufficient_valid_depth"))
            continue
        descriptor = pool_dinov2_region_descriptor(tokens, mask, descriptor_config).values
        fragment_id = f"fragment:{len(rows):04d}"
        rows.append({"fragment_id": fragment_id, f"descriptor_{DESCRIPTOR_SET}": [float(v) for v in descriptor],
                     "centroid_m": [float(v) for v in geometry.centroid_m], "aabb_min_m": lower, "aabb_max_m": upper,
                     "pixel_count": int(record.visible_pixel_count), "depth_valid_ratio": float(geometry.reliability),
                     "supported_by": None, "mask_sha256": record.mask_sha256})
        fragment_masks[fragment_id] = mask
        fragment_to_mask[fragment_id] = first_index[record.mask_sha256]

    digest = frame_digest_of(rgb, depth, tick)
    frame = fc.build_frame(tick=int(tick), frame_digest=digest, camera_position_m=pose_record["position_m"],
                           camera_forward=camera_forward(pose_record["quaternion_xyzw"]), fragments=rows,
                           surfaces=[], free_space=[], visibility=[], frontend_config_sha256=PLUGIN_FRONTEND_SHA256,
                           descriptor_asset_sha256s={DESCRIPTOR_SET: registered_asset("dinov2_vit_b14_checkpoint")["sha256"]})
    frame[lr.PUBLIC_DEPTH_VIEW_KEY] = public_depth_view(digest, depth, calibration, pose_record, fragment_masks)
    return BuiltFrame(cache_frame=frame, fragment_to_mask=fragment_to_mask, dropped_masks=sorted(dropped),
                      calibration=calibration, pose=pose_record)


__all__ = ["BuiltFrame", "DinoV2Extractor", "FRAME_SIZE", "FrontEndError", "Sam2MaskGenerator", "build_frame",
           "frozen_configs", "public_depth_view"]
