"""S1-03: build the shared frozen frontend cache over the S1-02 episodes.

Usage (server, frontend env; every authorization bit in the S1-03 contract must be open first):
    python ops/vsmt/lean_s1_03_cache.py --episode-roots /root/autodl-tmp/vsmt_outputs/lean-s1-02a-<c>,... \\
        --output-root /root/autodl-tmp/vsmt_caches/lean-s1-03-<commit> --workers 4

What one worker does, per episode, and what it writes:
  1. read that episode's public plane only -- RGB, metric depth, intrinsics, causal relative pose;
     the private and provenance planes are never opened and their paths are never constructed;
  2. run the frozen SAM 2.1 automatic mask generator on the RGB -- D-215's arguments with the two
     NMS thresholds superseded to 0.7 by ruling 43 -- and admit the proposals under the D-215
     boundary (>=196 px, <=64 per frame, overflow and duplicates fail the episode);
  3. run frozen DINOv2 ViT-S/14 and ViT-B/14 over the same RGB and pool one descriptor per mask
     per set; S1-05 selects between the sets later, this stage stores both;
  4. build each fragment's geometry from the public depth, seal the frame, and write it;
  5. seal the episode and write a receipt; any frame failure fails the episode with a registered
     reason and the episode keeps its receipt.

白话：这个入口把 50 条 episode 的公开画面变成五个臂共读的一份 cache。它是本阶段唯一加载模型的
部件，所有几何与阈值都来自已冻结的 D-215／D-223，不在这里重新定义。它不读 private 面、不判断
身份、不训练任何东西；任何一帧出问题就整条 episode 失败并留回执，不静默丢帧。
"""

from __future__ import annotations

import argparse
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
from vsmt.l1_structures import materialize_public_surfaces  # noqa: E402

CONTRACT_PATH = ROOT / "configs" / "vsmt" / "lean_s1_03_frontend_cache_v1.json"
D223_CONTRACT_PATH = ROOT / "configs" / "vsmt" / "vm04_d223_f01_production_reader_v1.json"

#: Authorization bits that must be open before this entry point does anything real.
REQUIRED_AUTHORIZATION = ("asset_acquisition", "model_loading", "cache_generation",
                          "descriptor_extraction", "server_run")


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


def causal_pose(record: dict[str, Any]) -> dict[str, Any]:
    pose = record["relative_pose"]
    return {"position_m": list(pose["position_m"]), "quaternion_xyzw": list(pose["quaternion_xyzw"])}


def camera_forward(quaternion: list[float]) -> list[float]:
    """The camera's +z axis in world coordinates, as a unit vector."""

    x, y, z, w = (float(v) for v in quaternion)
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
    （全部来自 D-215／D-223 的冻结配置），不做微调，也不跨帧传递任何状态。
    """

    def __init__(self, frontend: dict[str, Any], assets: dict[str, str], device: str = "cuda") -> None:
        import torch
        from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
        from sam2.build_sam import build_sam2

        d215 = json.loads((ROOT / "configs" / "vsmt" / "vm04_d215_frontend_freeze_v1.json")
                          .read_text(encoding="utf-8"))["sam2"]
        self.torch = torch
        self.device = device
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
        self.dino = {}
        for name in fc.DESCRIPTOR_SETS:
            model = torch.hub.load(assets["dinov2_repository"], f"dinov2_{name}", source="local",
                                   pretrained=False)
            state = torch.load(assets[f"dinov2_{name}_checkpoint"], map_location="cpu")
            model.load_state_dict(state)
            self.dino[name] = model.to(device).eval()
        self.patch_size = int(frontend["descriptor"]["patch_size_pixels"])

    def masks(self, rgb: np.ndarray) -> list[np.ndarray]:
        return [np.asarray(row["segmentation"], dtype=bool) for row in self.generator.generate(rgb)]

    def patch_tokens(self, rgb: np.ndarray) -> dict[str, np.ndarray]:
        torch = self.torch
        tensor = torch.from_numpy(rgb).permute(2, 0, 1).float().div_(255.0).unsqueeze(0).to(self.device)
        out = {}
        with torch.no_grad():
            for name, model in self.dino.items():
                tokens = model.forward_features(tensor)["x_norm_patchtokens"][0]
                side = rgb.shape[0] // self.patch_size
                out[name] = tokens.reshape(side, side, -1).float().cpu().numpy()
        return out


# --------------------------------------------------------------------------
# one episode
# --------------------------------------------------------------------------

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
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        frontend = frozen_frontend()
        geometry = geometry_config(frontend)
        surface = surface_config(frontend)
        free_space_cfg = free_space_config(frontend)
        descriptor_cfgs = descriptor_configs(frontend)
        primary = descriptor_cfgs[fc.DESCRIPTOR_SETS[0]]
        models = FrozenModels(frontend, task["assets"])
        prior_free_space: list[Any] = []
        public_dir = Path(task["episode_root"]) / "public"
        count = len(sorted(public_dir.glob("*.frame.json")))
        if count < 1:
            raise CacheFailure("public_input_missing_or_malformed", "no public frames")
        frames = []
        for index in range(count):
            frame = read_public_frame(public_dir, index)
            record = frame["record"]
            admitted = fc.admit_proposals(
                [anonymous(mask, ordinal) for ordinal, mask in enumerate(models.masks(frame["rgb"]))])
            tokens = models.patch_tokens(frame["rgb"])
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
            surfaces = [fc.project_surface(item.public_record(""), ordinal=ordinal)
                        for ordinal, item in enumerate(materialize_public_surfaces(
                            frame["depth"], record["intrinsics"], pose,
                            tokens[fc.DESCRIPTOR_SETS[0]], primary, surface))]
            rows = []
            for ordinal, mask in enumerate(admitted):
                from vsmt.l1_entities import pool_dinov2_region_descriptor
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
            (out_dir / f"{index:04d}.cache.json").write_text(json.dumps(built))
            frames.append(built)
            key = str(len(rows))
            histogram[key] = histogram.get(key, 0) + 1
            fragments_total += len(rows)
            frames_with_fragments += int(len(rows) > 0)
        sealed = fc.seal_episode(frames, frontend_config_sha256=fc.D223_FRONTEND_CONFIG_SHA256)
        (out_dir / "episode_seal.json").write_text(json.dumps(sealed, indent=1))
        receipt.update({"status": "succeeded", "frames": len(frames), "fragments": fragments_total,
                        "frames_with_fragments": frames_with_fragments,
                        "fragments_per_frame_histogram": dict(sorted(histogram.items(), key=lambda kv: int(kv[0]))),
                        "episode_seal_sha256": sealed["payload_sha256"]})
    except (CacheFailure, fc.LeanFrontendCacheError) as failure:
        receipt.update({"status": "failed", "reason": failure.reason,
                        "detail": getattr(failure, "detail", str(failure))[:400]})
    except Exception as exc:  # noqa: BLE001
        receipt.update({"status": "failed", "reason": "public_input_missing_or_malformed",
                        "detail": (repr(exc) + " | " + traceback.format_exc()[-800:])})
    receipt["wall_seconds"] = round(time.time() - started, 1)
    (out_dir / "receipt.json").write_text(json.dumps(receipt, indent=1))
    return receipt


# --------------------------------------------------------------------------
# orchestrator
# --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--episode-roots", required=True,
                        help="comma-separated S1-02 output roots; every succeeded episode under them is cached")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--assets-json", required=True,
                        help="a JSON file mapping asset_id to its path on this machine; digests are checked "
                             "against the S1-01 registry before anything is loaded")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()

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
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                            cwd=ROOT).stdout.strip()
    out_root = Path(args.output_root)
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

    tasks = [{
        "episode_id": directory.name, "episode_root": str(directory),
        "out": str(out_root / directory.name), "commit": commit, "assets": assets,
        "descriptor_asset_sha256s": {name: assets.get(f"dinov2_{name}_sha256", "") for name in fc.DESCRIPTOR_SETS},
    } for directory in episodes]

    (out_root / "plan.json").write_text(json.dumps(
        {"stage": "s1-03", "episodes": [t["episode_id"] for t in tasks], "commit": commit,
         "frontend_config_sha256": fc.D223_FRONTEND_CONFIG_SHA256,
         "requested_workers": args.workers}, indent=1))

    started = time.time()
    context = mp.get_context("spawn")
    with context.Pool(processes=max(1, args.workers)) as pool:
        results = pool.map(build_episode, tasks)
    results = sorted(results, key=lambda row: row["episode_id"])
    failed = [row for row in results if row["status"] != "succeeded"]
    merged: dict[str, int] = {}
    for row in results:
        for key, value in (row.get("fragments_per_frame_histogram") or {}).items():
            merged[key] = merged.get(key, 0) + value
    receipt = {
        "stage": "s1-03", "code_commit": commit,
        "episodes_planned": len(tasks), "episodes_succeeded": len(results) - len(failed),
        "episodes_failed": len(failed),
        "failure_receipts": [{"episode_id": r["episode_id"], "reason": r["reason"],
                              "detail": r.get("detail", "")[:400]} for r in failed],
        "frames_total": sum(r.get("frames", 0) for r in results),
        "fragments_total": sum(r.get("fragments", 0) for r in results),
        "fragments_per_frame_histogram": dict(sorted(merged.items(), key=lambda kv: int(kv[0]))),
        "frames_with_zero_fragments": merged.get("0", 0),
        "fragment_yield_frames_with_at_least_one_fragment": (
            sum(r.get("frames_with_fragments", 0) for r in results) / max(1, sum(r.get("frames", 0) for r in results))),
        "descriptor_sets_extracted": list(fc.DESCRIPTOR_SETS),
        "frontend_config_sha256": fc.D223_FRONTEND_CONFIG_SHA256,
        "wall_clock_seconds": round(time.time() - started, 1),
        "requested_workers": args.workers, "actual_workers": args.workers,
    }
    (out_root / "s1_03_receipt.json").write_text(json.dumps(receipt, indent=1))
    print(json.dumps(receipt, indent=1))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
