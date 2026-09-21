"""S1-03: build the shared frozen frontend cache over the S1-02 episodes.

Usage (server, frontend env; every authorization bit in the S1-03 contract must be open first):
    python ops/vsmt/lean_s1_03_cache.py --episode-roots /root/autodl-tmp/vsmt_outputs/lean-s1-02a-<c>,... \\
        --output-root /root/autodl-tmp/vsmt_caches/lean-s1-03-<commit> --assets-json <private>/s103_assets.json \\
        --workers 4 --worker-basis "<the measured evidence the worker count rests on>"

What one worker does, per episode, and what it writes:
  1. read that episode's public plane only -- RGB, metric depth, intrinsics, causal relative pose;
     the private and provenance planes are never opened and their paths are never constructed;
  2. run the frozen SAM 2.1 automatic mask generator on the RGB -- D-215's arguments with the two
     NMS thresholds superseded to 0.7 by ruling 43 -- and admit the proposals under the D-215
     boundary (>=196 px, <=64 per frame, overflow and duplicates fail the episode);
  3. run frozen DINOv2 ViT-S/14 and ViT-B/14 over the same RGB through the reviewed extractor
     (ImageNet normalisation, inference mode, shape and finiteness checks) and pool one descriptor
     per mask per set; S1-05 selects between the sets later, this stage stores both;
  4. build each fragment's geometry from the public depth, seal the frame, and write it as one
     gzip-compressed JSON file per frame (``NNNN.cache.json.gz``; the seal covers the decoded
     object, not the bytes on disk, so the compression is free to change);
  5. seal the episode and write a receipt; any frame failure fails the episode with a registered
     reason and the episode keeps its receipt.

Every asset the run loads is digested here and checked against the registry that pinned it (the
S1-03 contract for SAM 2.1, the S1-01 registry for DINOv2); the digests written into every frame
are the ones computed from the bytes actually loaded, never copied from a user-supplied file.

The public clock handed to the D-223 free-space materialiser is the frame index in seconds
(``time_s = index``): the rolling window is counted in observations, which is what D-223 froze.

白话：这个入口把 S1-02 的公开画面变成五个臂共读的一份 cache。它是本阶段唯一加载模型的
部件，所有几何与阈值都来自已冻结的 D-215／D-223，不在这里重新定义。它不读 private 面、不判断
身份、不训练任何东西；任何一帧出问题就整条 episode 失败并留回执，不静默丢帧。每个 worker 进程
只装一次模型；每条 episode 的回执记录实测的显存峰值、内存峰值、每帧秒数和写入字节数，作为
worker 数与磁盘预算的依据。
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import multiprocessing as mp
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
for item in (ROOT / "src", HERE.parent):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import numpy as np  # noqa: E402

from vsmt import lean_frontend_cache as fc  # noqa: E402
from vsmt.shared_frontend_core import (  # noqa: E402
    AnonymousMask, DINORegionConfig, FreeSpaceMaterializationConfig,
    PublicGeometryConfig, SurfaceMaterializationConfig, materialize_place_support,
)
from vsmt.l1_entities import extract_dinov2_patch_tokens, pool_dinov2_region_descriptor  # noqa: E402
from vsmt.l1_structures import materialize_public_surfaces  # noqa: E402

CONTRACT_PATH = ROOT / "configs" / "vsmt" / "lean_s1_03_frontend_cache_v1.json"
D223_CONTRACT_PATH = ROOT / "configs" / "vsmt" / "vm04_d223_f01_production_reader_v1.json"
D215_CONTRACT_PATH = ROOT / "configs" / "vsmt" / "vm04_d215_frontend_freeze_v1.json"
ASSET_REGISTRY_PATH = ROOT / "configs" / "vsmt" / "lean_s1_assets_capacity_v2.json"

#: Authorization bits that must be open before this entry point does anything real.
REQUIRED_AUTHORIZATION = ("asset_acquisition", "model_loading", "cache_generation",
                          "descriptor_extraction", "server_run")

#: descriptor set name -> S1-01 registry asset id of its checkpoint
DESCRIPTOR_ASSET_IDS = {"vits14": "dinov2_vit_s14_checkpoint", "vitb14": "dinov2_vit_b14_checkpoint"}

#: one frame on disk
FRAME_FILE_SUFFIX = ".cache.json.gz"


class CacheFailure(Exception):
    def __init__(self, reason: str, detail: str = "") -> None:
        assert reason in fc.FAILURE_REASONS, reason
        super().__init__(f"{reason}: {detail}")
        self.reason, self.detail = reason, detail


# --------------------------------------------------------------------------
# frozen configuration, read from the bound D-223 contract rather than retyped
# --------------------------------------------------------------------------

def frozen_frontend() -> dict[str, Any]:
    """The D-223 frontend block, checked against the digest S1-03 binds."""

    d223 = json.loads(D223_CONTRACT_PATH.read_text(encoding="utf-8"))
    frontend = d223["frontend"]
    if frontend["frontend_config_sha256"] != fc.D223_FRONTEND_CONFIG_SHA256:
        raise CacheFailure("public_input_missing_or_malformed",
                           "the bound D-223 frontend digest no longer matches")
    return frontend


def descriptor_configs(frontend: dict[str, Any]) -> dict[str, DINORegionConfig]:
    """One pooling config per descriptor set; only the token dimension differs."""

    base = dict(frontend["descriptor"])
    out = {}
    for name, dimension in fc.DESCRIPTOR_DIMENSIONS.items():
        out[name] = DINORegionConfig(**{**base, "patch_token_dimension": dimension})
    return out


def geometry_config(frontend: dict[str, Any]) -> PublicGeometryConfig:
    return PublicGeometryConfig(**frontend["fragment_geometry"])


def surface_config(frontend: dict[str, Any]) -> SurfaceMaterializationConfig:
    return SurfaceMaterializationConfig(**frontend["surface"])


def free_space_config(frontend: dict[str, Any]) -> FreeSpaceMaterializationConfig:
    raw = dict(frontend["free_space"])
    raw["block_widths_in_tiles"] = tuple(raw["block_widths_in_tiles"])
    return FreeSpaceMaterializationConfig(**raw)


# --------------------------------------------------------------------------
# assets: digested here, checked against the registry that pinned them
# --------------------------------------------------------------------------

def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(repository: Path, *arguments: str) -> str:
    return subprocess.run(["git", "-C", str(repository), *arguments], capture_output=True,
                          text=True, check=True).stdout.strip()


def verify_assets(assets: dict[str, str], contract: dict[str, Any]) -> dict[str, Any]:
    """Digest every asset this run will load and check it against where it was pinned.

    SAM 2.1 (repository commit, config file, checkpoint) is checked against the S1-03 contract's
    ``bound_frozen_frontend`` block; the DINOv2 repository and both checkpoints against the S1-01
    asset registry.  A repository must be at the pinned commit with no tracked file modified.
    Returns the verified digests, which are what the cache frames carry.

    白话：runner 不相信 assets 文件里写的摘要，而是自己把要加载的字节算一遍，再跟合同／登记表
    上钉的值比对；写进每一帧的 `descriptor_asset_sha256s` 就是这里算出的值。
    """

    bound = contract["bound_frozen_frontend"]
    registry = {row["asset_id"]: row for row in
                json.loads(ASSET_REGISTRY_PATH.read_text(encoding="utf-8"))["asset_registry"]}
    d215 = json.loads(D215_CONTRACT_PATH.read_text(encoding="utf-8"))["sam2"]
    verified: dict[str, Any] = {}

    sam2_repository = Path(assets["sam2_repository"])
    head = _git(sam2_repository, "rev-parse", "HEAD")
    if head != bound["sam2_repository_commit"]:
        raise CacheFailure("public_input_missing_or_malformed", f"sam2 repository at {head[:12]}, not the pinned commit")
    if _git(sam2_repository, "status", "--porcelain", "--untracked-files=no"):
        raise CacheFailure("public_input_missing_or_malformed", "sam2 repository has modified tracked files")
    config_path = sam2_repository / d215["official_model_config_path"]
    config_digest = file_sha256(config_path)
    if config_digest != d215["official_model_config_sha256"]:
        raise CacheFailure("public_input_missing_or_malformed", f"sam2 config digest changed: {config_digest[:16]}")
    checkpoint = Path(assets["sam2_checkpoint"])
    checkpoint_digest = file_sha256(checkpoint)
    if checkpoint_digest != bound["sam2_checkpoint_sha256"]:
        raise CacheFailure("public_input_missing_or_malformed", f"sam2 checkpoint digest changed: {checkpoint_digest[:16]}")
    verified["sam2"] = {"repository_commit": head, "config_sha256": config_digest,
                        "checkpoint_sha256": checkpoint_digest, "checkpoint_bytes": checkpoint.stat().st_size}

    dinov2_repository = Path(assets["dinov2_repository"])
    head = _git(dinov2_repository, "rev-parse", "HEAD")
    if head != registry["dinov2_repository"]["pinned_ref"]:
        raise CacheFailure("public_input_missing_or_malformed", f"dinov2 repository at {head[:12]}, not the pinned commit")
    if _git(dinov2_repository, "status", "--porcelain", "--untracked-files=no"):
        raise CacheFailure("public_input_missing_or_malformed", "dinov2 repository has modified tracked files")
    verified["dinov2"] = {"repository_commit": head, "checkpoints": {}}
    for name, asset_id in DESCRIPTOR_ASSET_IDS.items():
        row = registry[asset_id]
        path = Path(assets[f"dinov2_{name}_checkpoint"])
        size = path.stat().st_size
        digest = file_sha256(path)
        if size != row["bytes"] or digest != row["sha256"]:
            raise CacheFailure("public_input_missing_or_malformed",
                               f"dinov2 {name} checkpoint does not match the registry ({size} bytes, {digest[:16]})")
        verified["dinov2"]["checkpoints"][name] = {"asset_id": asset_id, "sha256": digest, "bytes": size}
    verified["descriptor_asset_sha256s"] = {
        name: verified["dinov2"]["checkpoints"][name]["sha256"] for name in fc.DESCRIPTOR_SETS}
    return verified


# --------------------------------------------------------------------------
# public plane reader: public only, by construction
# --------------------------------------------------------------------------

def read_public_frame(public_dir: Path, index: int) -> dict[str, Any]:
    """One public frame.  Only paths under ``public`` are ever built."""

    record = json.loads((public_dir / f"{index:04d}.frame.json").read_text(encoding="utf-8"))
    rgb_path = public_dir / record["rgb_path"]
    depth_path = public_dir / record["depth_path"]
    for path in (rgb_path, depth_path):
        if path.parent.resolve() != public_dir.resolve():
            raise CacheFailure("public_input_missing_or_malformed", f"path escapes the public plane: {path}")
    from PIL import Image
    rgb = np.asarray(Image.open(rgb_path), dtype=np.uint8)
    depth = np.load(depth_path).astype(np.float32)
    return {"record": record, "rgb": rgb, "depth": depth}


def load_cache_frame(path: Path) -> dict[str, Any]:
    """Decode one written frame; the object returned is what the frame seal covers."""

    with gzip.open(path, "rb") as handle:
        return json.loads(handle.read().decode("utf-8"))


def causal_pose(record: dict[str, Any]) -> dict[str, Any]:
    pose = record["relative_pose"]
    return {"position_m": list(pose["position_m"]), "quaternion_xyzw": list(pose["quaternion_xyzw"])}


def camera_forward(quaternion: list[float]) -> list[float]:
    """The camera's +z axis in world coordinates, as a unit vector."""

    x, y, z, w = (float(v) for v in quaternion)
    # the same unit tolerance the frozen core applies to a causal pose (shared_frontend_core)
    if not np.isfinite([x, y, z, w]).all() or abs(np.sqrt(x * x + y * y + z * z + w * w) - 1.0) > 1e-6:
        raise CacheFailure("public_input_missing_or_malformed", "camera quaternion is not a unit quaternion")
    forward = np.array([2 * (x * z + y * w), 2 * (y * z - x * w), 1 - 2 * (x * x + y * y)])
    norm = float(np.linalg.norm(forward))
    if not np.isfinite(norm) or norm <= 0:
        raise CacheFailure("public_input_missing_or_malformed", "degenerate camera orientation")
    return [float(v) for v in forward / norm]


# --------------------------------------------------------------------------
# frozen models
# --------------------------------------------------------------------------

class FrozenModels:
    """SAM 2.1 and both DINOv2 backbones, loaded once per worker and never trained.

    白话：这个类只负责把冻结的模型装进显存并按帧吐出 mask 与 patch token。它不改任何超参
    （全部来自 D-215／D-223 的冻结配置），不做微调，也不跨帧传递任何状态。DINOv2 的加载与
    预处理走的是 D-218 已审的同一条路（hub backbone、strict 加载、ImageNet 归一化、推理模式），
    不在这里另写一份。
    """

    def __init__(self, frontend: dict[str, Any], assets: dict[str, str],
                 descriptor_cfgs: dict[str, DINORegionConfig], device: str = "cuda") -> None:
        import torch
        from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
        from sam2.build_sam import build_sam2

        if device == "cuda" and not torch.cuda.is_available():
            raise CacheFailure("public_input_missing_or_malformed", "cuda requested but unavailable")
        d215 = json.loads(D215_CONTRACT_PATH.read_text(encoding="utf-8"))["sam2"]
        self.torch = torch
        self.device = device
        self.descriptor_cfgs = descriptor_cfgs
        # The registry pins the config by its repository-relative path; hydra resolves names
        # against the installed package root (pkg://sam2), so the same file is named without the
        # leading package directory.  The mapping is recorded here, not assumed, and the file the
        # registry pinned is the file that is loaded -- verified by digest below.
        registered = d215["official_model_config_path"]
        hydra_name = registered.split("/", 1)[1] if registered.startswith("sam2/") else registered
        config_on_disk = Path(assets["sam2_repository"]) / registered
        actual = hashlib.sha256(config_on_disk.read_bytes()).hexdigest()
        if actual != d215["official_model_config_sha256"]:
            raise CacheFailure("public_input_missing_or_malformed",
                               f"sam2 config digest changed: {actual[:16]}")
        sam = build_sam2(hydra_name, assets["sam2_checkpoint"], device=device)
        # Ruling 43: the generator runs D-215's frozen arguments with the two NMS thresholds
        # superseded by reference from the S1-03 contract.  The effective config is rebuilt here
        # from D-215 plus exactly those two overrides and its digest is checked against the one
        # the contract pins, so neither file can drift from the other unnoticed.
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        supersession = contract["sam2_nms_supersession"]
        effective = {**d215["automatic_mask_generator"], **supersession["to"]}
        if effective != supersession["effective_automatic_mask_generator"]:
            raise CacheFailure("public_input_missing_or_malformed", "effective generator config drifted")
        # same formula as vsmt.d215_frontend_freeze._derived_digests (canonical-JSON sha256)
        if fc.sha({"automatic_mask_generator": effective, "proposal_boundary": d215["proposal_boundary"]}) != fc.EFFECTIVE_AUTOMATIC_CONFIG_SHA256:
            raise CacheFailure("public_input_missing_or_malformed", "effective generator digest drifted")
        self.generator = SAM2AutomaticMaskGenerator(sam, **effective)

        # DINOv2: the reviewed D-218 loading path -- the repository's own hub constructors, the
        # checkpoint loaded as weights only and applied strictly, gradients off, evaluation mode.
        repository = str(Path(assets["dinov2_repository"]))
        if repository not in sys.path:
            sys.path.insert(0, repository)
        from dinov2.hub import backbones
        self.dino = {}
        for name in fc.DESCRIPTOR_SETS:
            model = getattr(backbones, f"dinov2_{name}")(pretrained=False)
            state = torch.load(assets[f"dinov2_{name}_checkpoint"], map_location="cpu", weights_only=True)
            model.load_state_dict(state, strict=True)
            self.dino[name] = model.requires_grad_(False).eval().to(device)

    def masks(self, rgb: np.ndarray) -> list[np.ndarray]:
        return [np.asarray(row["segmentation"], dtype=bool) for row in self.generator.generate(rgb)]

    def patch_tokens(self, rgb: np.ndarray) -> dict[str, np.ndarray]:
        """Patch-token grids per descriptor set, through the reviewed extractor."""

        return {name: extract_dinov2_patch_tokens(model, rgb, self.descriptor_cfgs[name], device=self.device)
                for name, model in self.dino.items()}

    def reset_peak_memory(self) -> None:
        if self.device == "cuda":
            self.torch.cuda.reset_peak_memory_stats()

    def peak_reserved_mib(self) -> float | None:
        if self.device != "cuda":
            return None
        return round(self.torch.cuda.max_memory_reserved() / 2 ** 20, 1)


_WORKER_MODELS: FrozenModels | None = None


def worker_models(frontend: dict[str, Any], assets: dict[str, str],
                  descriptor_cfgs: dict[str, DINORegionConfig]) -> FrozenModels:
    """The models of this worker process, built on first use and kept for every later episode."""

    global _WORKER_MODELS
    if _WORKER_MODELS is None:
        _WORKER_MODELS = FrozenModels(frontend, assets, descriptor_cfgs)
    return _WORKER_MODELS


def peak_rss_mib() -> float | None:
    try:
        import resource
    except ImportError:  # not a Linux worker
        return None
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)


# --------------------------------------------------------------------------
# one episode
# --------------------------------------------------------------------------

def surface_mapping(item: Any) -> dict[str, Any]:
    """The geometry of one frozen surface region; its public_record() omits the plane, so the
    dataclass attributes are read directly.  The descriptor is not carried over."""

    return {"centroid_m": list(item.centroid_m), "extent_m": list(item.extent_m),
            "plane_normal": list(item.plane_normal), "plane_offset_m": float(item.plane_offset_m),
            "mask_sha256": item.mask_sha256}


def anonymous(mask: np.ndarray, ordinal: int) -> AnonymousMask:
    binary = np.ascontiguousarray(mask.astype(np.uint8))
    payload = [int(binary.shape[0]), int(binary.shape[1]), *binary.reshape(-1).tolist()]
    return AnonymousMask(
        region_id=f"region:{ordinal:04d}", mask_sha256=fc.sha(payload),
        height=int(binary.shape[0]), width=int(binary.shape[1]),
        row_major_values=tuple(int(v) for v in binary.reshape(-1)),
        visible_pixel_count=int(binary.sum()),
        touches_border=bool(binary[0].any() or binary[-1].any()
                            or binary[:, 0].any() or binary[:, -1].any()),
    )


def build_episode(task: dict[str, Any]) -> dict[str, Any]:
    started = time.time()
    episode_id = task["episode_id"]
    out_dir = Path(task["out"])
    receipt: dict[str, Any] = {"episode_id": episode_id, "code_commit": task["commit"]}
    histogram: dict[str, int] = {}
    fragments_total = 0
    frames_with_fragments = 0
    bytes_written = 0
    bytes_uncompressed = 0
    seconds = {"sam": 0.0, "dino": 0.0, "other": 0.0}
    frame_limit = task.get("frame_limit")
    models: FrozenModels | None = None
    frames_done = 0
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        frontend = frozen_frontend()
        geometry = geometry_config(frontend)
        surface = surface_config(frontend)
        free_space_cfg = free_space_config(frontend)
        descriptor_cfgs = descriptor_configs(frontend)
        primary = descriptor_cfgs[fc.DESCRIPTOR_SETS[0]]
        models = worker_models(frontend, task["assets"], descriptor_cfgs)
        models.reset_peak_memory()
        prior_free_space: list[Any] = []
        public_dir = Path(task["episode_root"]) / "public"
        count = len(sorted(public_dir.glob("*.frame.json")))
        if count < 1:
            raise CacheFailure("public_input_missing_or_malformed", "no public frames")
        if frame_limit is not None:
            count = min(count, int(frame_limit))
        seal_inputs = []
        for index in range(count):
            mark = time.time()
            frame = read_public_frame(public_dir, index)
            record = frame["record"]
            raw = models.masks(frame["rgb"])
            seconds["sam"] += time.time() - mark
            mark = time.time()
            tokens = models.patch_tokens(frame["rgb"])
            seconds["dino"] += time.time() - mark
            mark = time.time()
            admitted = fc.admit_proposals([anonymous(mask, ordinal) for ordinal, mask in enumerate(raw)])
            pose = causal_pose(record)
            # the two public volumes and the surfaces come from the bound D-223 materialisers on the
            # same public depth; rho_free needs no separate gate (ruling 42), and the place
            # descriptor the support helper also returns is dropped here per METHOD section 5
            depth_digest = fc.sha(frame["depth"].tobytes().hex())
            pose_digest = fc.sha({"calibration": record["intrinsics"], "causal_pose": pose})
            support = materialize_place_support(
                depth_m=frame["depth"], calibration=record["intrinsics"], geometry_pose=pose,
                patch_tokens=tokens[fc.DESCRIPTOR_SETS[0]], descriptor=primary,
                free_space=free_space_cfg, time_s=float(index), depth_sha256=depth_digest,
                calibration_and_pose_sha256=pose_digest, prior_free_space=prior_free_space)
            prior_free_space = ([*prior_free_space, support.current_free_space]
                                [-free_space_cfg.rolling_public_observation_times:])
            surfaces = [fc.project_surface(surface_mapping(item), ordinal=ordinal)
                        for ordinal, item in enumerate(materialize_public_surfaces(
                            frame["depth"], record["intrinsics"], pose,
                            tokens[fc.DESCRIPTOR_SETS[0]], primary, surface))]
            rows = []
            for ordinal, mask in enumerate(admitted):
                descriptors = {
                    name: list(pool_dinov2_region_descriptor(
                        tokens[name], mask.as_array(), descriptor_cfgs[name]).values)
                    for name in fc.DESCRIPTOR_SETS}
                rows.append(fc.build_fragment(
                    ordinal=ordinal, mask=mask, depth_m=frame["depth"],
                    calibration=record["intrinsics"], pose=pose, geometry_config=geometry,
                    descriptors=descriptors))
                del descriptors
            built = fc.build_frame(
                tick=index + 1, frame_digest=record["frame_digest"],
                camera_position_m=pose["position_m"],
                camera_forward=camera_forward(pose["quaternion_xyzw"]),
                fragments=rows, surfaces=surfaces,
                free_space=support.free_space, visibility=support.visibility,
                frontend_config_sha256=fc.D223_FRONTEND_CONFIG_SHA256,
                descriptor_asset_sha256s=task["descriptor_asset_sha256s"])
            payload = json.dumps(built).encode("utf-8")
            compressed = gzip.compress(payload, compresslevel=6)
            (out_dir / f"{index:04d}{FRAME_FILE_SUFFIX}").write_bytes(compressed)
            bytes_written += len(compressed)
            bytes_uncompressed += len(payload)
            # the episode seal needs only each frame's tick and seal; the frame itself is not kept
            seal_inputs.append({"tick": built["tick"], "frame_seal": built["frame_seal"]})
            key = str(len(rows))
            histogram[key] = histogram.get(key, 0) + 1
            fragments_total += len(rows)
            frames_with_fragments += int(len(rows) > 0)
            frames_done += 1
            seconds["other"] += time.time() - mark
        sealed = fc.seal_episode(seal_inputs, frontend_config_sha256=fc.D223_FRONTEND_CONFIG_SHA256)
        (out_dir / "episode_seal.json").write_text(json.dumps(sealed, indent=1))
        receipt.update({"status": "succeeded", "frames": frames_done, "fragments": fragments_total,
                        "frames_with_fragments": frames_with_fragments,
                        "fragments_per_frame_histogram": dict(sorted(histogram.items(), key=lambda kv: int(kv[0]))),
                        "episode_seal_sha256": sealed["payload_sha256"]})
    except (CacheFailure, fc.LeanFrontendCacheError) as failure:
        receipt.update({"status": "failed", "reason": failure.reason,
                        "detail": getattr(failure, "detail", str(failure))[:400]})
    except Exception as exc:  # noqa: BLE001
        receipt.update({"status": "failed", "reason": "public_input_missing_or_malformed",
                        "detail": (repr(exc) + " | " + traceback.format_exc()[-800:])})
    wall = time.time() - started
    receipt.update({
        "frames_processed": frames_done,
        "frame_limit": frame_limit,
        "wall_seconds": round(wall, 1),
        "seconds_per_frame": round(wall / frames_done, 3) if frames_done else None,
        "seconds_by_part": {k: round(v, 1) for k, v in seconds.items()},
        "bytes_written": bytes_written,
        "bytes_uncompressed": bytes_uncompressed,
        "peak_vram_reserved_mib": models.peak_reserved_mib() if models is not None else None,
        "peak_rss_mib": peak_rss_mib(),
        "worker_pid": os.getpid(),
    })
    (out_dir / "receipt.json").write_text(json.dumps(receipt, indent=1))
    return receipt


# --------------------------------------------------------------------------
# orchestrator
# --------------------------------------------------------------------------

def resource_snapshot() -> dict[str, Any]:
    """What this machine offers at launch; the evidence the worker count is judged against."""

    snapshot: dict[str, Any] = {"cpu_count": os.cpu_count()}
    try:
        import torch
        if torch.cuda.is_available():
            free, total = torch.cuda.mem_get_info()
            snapshot["gpu"] = {"name": torch.cuda.get_device_name(0), "count": torch.cuda.device_count(),
                               "total_mib": round(total / 2 ** 20), "free_mib_at_launch": round(free / 2 ** 20)}
    except Exception as exc:  # noqa: BLE001
        snapshot["gpu"] = {"error": repr(exc)[:200]}
    try:
        meminfo = Path("/proc/meminfo").read_text(encoding="utf-8").splitlines()
        rows = {line.split(":")[0]: int(line.split()[1]) for line in meminfo if ":" in line}
        snapshot["ram_total_gib"] = round(rows["MemTotal"] / 2 ** 20, 1)
        snapshot["ram_available_gib"] = round(rows["MemAvailable"] / 2 ** 20, 1)
    except Exception:  # noqa: BLE001
        pass
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--episode-roots", required=True,
                        help="comma-separated S1-02 output roots; every succeeded episode under them is cached")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--assets-json", required=True,
                        help="a JSON file mapping asset_id to its path on this machine; every asset is "
                             "digested and checked against its registry before anything is loaded")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--worker-basis", default="",
                        help="the measured evidence the worker count rests on; recorded in plan and receipt")
    parser.add_argument("--trial-frame-limit", type=int, default=None,
                        help="measurement only: cache at most this many frames per episode and write a "
                             "trial receipt instead of the stage receipt; never a stage run")
    parser.add_argument("--trial-episodes", type=int, default=None,
                        help="measurement only: cache at most this many episodes (requires --trial-frame-limit)")
    args = parser.parse_args()
    trial = args.trial_frame_limit is not None
    if args.trial_episodes is not None and not trial:
        print("--trial-episodes requires --trial-frame-limit; refusing")
        return 2

    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    fc.validate_contract(contract)
    closed = [name for name in REQUIRED_AUTHORIZATION if not contract["authorization"].get(name)]
    if closed:
        print(f"authorization bits closed, refusing: {', '.join(closed)}")
        return 2
    for slot in contract["policy_values_without_defaults"]:
        node = contract
        for part in slot.split("."):
            node = node[part]
        if node is None:
            print(f"registered value still null, refusing: {slot}")
            return 2

    frontend = frozen_frontend()
    assets = json.loads(Path(args.assets_json).read_text(encoding="utf-8"))
    verified = verify_assets(assets, contract)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                            cwd=ROOT).stdout.strip()
    out_root = Path(args.output_root)
    if trial and not out_root.name.endswith("-trial"):
        print("a trial run must write to an output root ending in -trial; refusing")
        return 2
    if not trial and out_root.name.endswith("-trial"):
        print("a stage run must not write to a -trial output root; refusing")
        return 2
    out_root.mkdir(parents=True, exist_ok=True)

    episodes = []
    for root in args.episode_roots.split(","):
        for directory in sorted(Path(root).glob("procthor10k-*")):
            receipt_path = directory / "receipt.json"
            if not receipt_path.exists():
                continue
            if json.loads(receipt_path.read_text(encoding="utf-8"))["status"] != "succeeded":
                continue
            episodes.append(directory)
    if not episodes:
        print("no succeeded episodes under the given roots; refusing")
        return 2
    if trial and args.trial_episodes is not None:
        episodes = episodes[:max(1, args.trial_episodes)]

    tasks = [{
        "episode_id": directory.name, "episode_root": str(directory),
        "out": str(out_root / directory.name), "commit": commit, "assets": assets,
        "descriptor_asset_sha256s": verified["descriptor_asset_sha256s"],
        "frame_limit": args.trial_frame_limit,
    } for directory in episodes]
    actual_workers = max(1, min(args.workers, len(tasks)))
    snapshot = resource_snapshot()

    plan = {"stage": "s1-03", "trial": trial, "episodes": [t["episode_id"] for t in tasks], "commit": commit,
            "frontend_config_sha256": fc.D223_FRONTEND_CONFIG_SHA256,
            "asset_verification": verified,
            "requested_workers": args.workers, "actual_workers": actual_workers,
            "worker_basis": args.worker_basis, "resources_at_launch": snapshot,
            "sharding": "one episode per task, tasks handed to a spawn pool one at a time, "
                        "results merged in episode_id order",
            "trial_frame_limit": args.trial_frame_limit, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (out_root / ("trial_plan.json" if trial else "plan.json")).write_text(json.dumps(plan, indent=1))
    print(f"[s1-03] {len(tasks)} episodes, {actual_workers} workers (requested {args.workers}), "
          f"trial={trial}, commit {commit[:12]}", flush=True)

    started = time.time()
    context = mp.get_context("spawn")
    results = []
    with context.Pool(processes=actual_workers) as pool:
        for row in pool.imap_unordered(build_episode, tasks, chunksize=1):
            results.append(row)
            print(f"[s1-03] {len(results)}/{len(tasks)} {row['episode_id']} {row['status']} "
                  f"frames={row.get('frames_processed')} s/frame={row.get('seconds_per_frame')} "
                  f"vram={row.get('peak_vram_reserved_mib')}MiB rss={row.get('peak_rss_mib')}MiB "
                  f"bytes={row.get('bytes_written')} "
                  f"{('reason=' + str(row.get('reason'))) if row['status'] != 'succeeded' else ''} "
                  f"elapsed={time.time() - started:.0f}s", flush=True)
    results = sorted(results, key=lambda row: row["episode_id"])
    failed = [row for row in results if row["status"] != "succeeded"]
    merged: dict[str, int] = {}
    for row in results:
        for key, value in (row.get("fragments_per_frame_histogram") or {}).items():
            merged[key] = merged.get(key, 0) + value
    frames_total = sum(r.get("frames", 0) for r in results)
    receipt = {
        "stage": "s1-03", "trial": trial, "code_commit": commit,
        "episodes_planned": len(tasks), "episodes_succeeded": len(results) - len(failed),
        "episodes_failed": len(failed),
        "failure_receipts": [{"episode_id": r["episode_id"], "reason": r["reason"],
                              "detail": r.get("detail", "")[:400]} for r in failed],
        "frames_total": frames_total,
        "fragments_total": sum(r.get("fragments", 0) for r in results),
        "fragments_per_frame_histogram": dict(sorted(merged.items(), key=lambda kv: int(kv[0]))),
        "frames_with_zero_fragments": merged.get("0", 0),
        "fragment_yield_frames_with_at_least_one_fragment": (
            sum(r.get("frames_with_fragments", 0) for r in results) / max(1, frames_total)),
        "descriptor_sets_extracted": list(fc.DESCRIPTOR_SETS),
        "frontend_config_sha256": fc.D223_FRONTEND_CONFIG_SHA256,
        "descriptor_asset_sha256s": verified["descriptor_asset_sha256s"],
        "wall_clock_seconds": round(time.time() - started, 1),
        "requested_workers": args.workers, "actual_workers": actual_workers,
        "worker_basis": args.worker_basis, "resources_at_launch": snapshot,
        "frames_processed_total": sum(r.get("frames_processed", 0) for r in results),
        "bytes_written_total": sum(r.get("bytes_written", 0) for r in results),
        "bytes_uncompressed_total": sum(r.get("bytes_uncompressed", 0) for r in results),
        "peak_vram_reserved_mib_max": max([r.get("peak_vram_reserved_mib") or 0 for r in results] or [0]),
        "peak_rss_mib_max": max([r.get("peak_rss_mib") or 0 for r in results] or [0]),
        "seconds_by_part_total": {k: round(sum((r.get("seconds_by_part") or {}).get(k, 0.0) for r in results), 1)
                                  for k in ("sam", "dino", "other")},
        "trial_frame_limit": args.trial_frame_limit,
        "exit_status": 0 if not failed else 1,
    }
    (out_root / ("trial_receipt.json" if trial else "s1_03_receipt.json")).write_text(json.dumps(receipt, indent=1))
    print(json.dumps(receipt, indent=1))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
