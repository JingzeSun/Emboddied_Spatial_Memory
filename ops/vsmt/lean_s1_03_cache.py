"""S1-03: build the shared frozen frontend cache over the S1-02 episodes.

Usage (server, frontend env; every authorization bit in the S1-03 contract must be open first):
    python ops/vsmt/lean_s1_03_cache.py --episode-roots /root/autodl-tmp/vsmt_outputs/lean-s1-02a-<c>,... \\
        --output-root /root/autodl-tmp/vsmt_caches/lean-s1-03-<commit> --assets-json <private>/s103_assets.json \\
        --workers 4 --worker-basis "<the measured evidence the worker count rests on>" \\
        [--masks-from /root/autodl-tmp/vsmt_caches/<superseded root with recovered masks>]

What one worker does, per episode, and what it writes:
  1. read that episode's public plane only -- RGB, metric depth, intrinsics, causal relative pose;
     the private and provenance planes are never opened and their paths are never constructed;
     the pose is read through ``vsmt.lean_public_pose`` under the contract's
     ``public_pose_correction`` block (ruling 49): an episode from a registered pre-ruling S1-02
     commit gets its pitch sign restored, one from a registered corrected encoder is read as
     written, and any other commit is refused before the run starts;
  2. run the frozen SAM 2.1 automatic mask generator on the RGB -- D-215's arguments with the two
     NMS thresholds superseded to 0.7 by ruling 43 -- and admit the proposals under the D-215
     boundary (>=196 px, <=64 per frame, overflow and duplicates fail the episode); with
     ``--masks-from`` (ruling 49) SAM is not loaded at all: the frame's masks are read from the
     superseded root's ``NNNN.masks.npz`` (written by ``--recover-masks``, RGB-only and therefore
     valid), every mask is re-digested from its pixels against the stored digest, and the same
     admission runs on them; an episode without a succeeded recovery receipt there is skipped and
     listed, never silently run through SAM;
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
import shutil
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
from vsmt import lean_public_pose as pp  # noqa: E402
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
#: the recovered fragment masks of one frame (``--recover-masks``): packed bits in cache fragment
#: order plus each mask's digest, so a reader can verify the file against the sealed frame
MASK_FILE_SUFFIX = ".masks.npz"
#: registered outcomes of the mask recovery pass (pending ruling 48; LOG-241 section four)
RECOVERY_FAILURE_REASONS = (
    "fragment_mask_mismatch",
    "cache_missing_or_unsealed",
    "public_input_missing_or_malformed",
    "proposal_overflow",
    "duplicate_proposal_mask",
)
S1_04_CONTRACT_PATH = ROOT / "configs" / "vsmt" / "lean_s1_04_frontend_diagnostics_v1.json"


class CacheFailure(Exception):
    def __init__(self, reason: str, detail: str = "") -> None:
        assert reason in fc.FAILURE_REASONS, reason
        super().__init__(f"{reason}: {detail}")
        self.reason, self.detail = reason, detail


class InfrastructureAbort(Exception):
    """The machine, not the data, stopped an episode: the episode is aborted, never failed.

    白话：磁盘快满这类机器问题不是数据问题，不能记成 episode 的科学失败；它让整个运行停下，
    这条 episode 留 `aborted` 回执，之后用 --resume 从头重做这一条。
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}")
        self.reason, self.detail = reason, detail


def blocking_null_slots(contract: dict[str, Any]) -> list[str]:
    """Registered values that are still null and that this stage would consume.

    Ruling 42 left the five ``supported_by`` thresholds null on purpose: the cache writes the field
    as null by construction (``build_fragment`` never receives a value) and nothing in this stage
    reads them, so they do not block generation while the contract records the field as null
    until frozen.  Any other null registered value still refuses the run.

    白话：合同里登记为待冻结的值，只有本阶段真的要用到的才能拦住生成；`supported_by` 的五个
    阈值按裁决 42 留 null、字段写 null，不拦。别的 null 值照旧拒绝。
    """

    rule = contract["supported_by_rule"]
    exempt_prefix = "supported_by_rule.value_slots."
    exempt = rule.get("recorded_as_null_until_the_thresholds_are_frozen") is True \
        and rule.get("enters_association_features") is False
    blocking = []
    for slot in contract["policy_values_without_defaults"]:
        node: Any = contract
        for part in slot.split("."):
            node = node[part]
        if node is None and not (exempt and slot.startswith(exempt_prefix)):
            blocking.append(slot)
    return blocking


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


def write_masks_file(path: Path, masks: list[np.ndarray], mask_sha256s: list[str], *, shape: tuple[int, int]) -> int:
    """The recovered masks of one frame, packed, in cache fragment order; returns the bytes written."""

    count = len(masks)
    if count:
        array = np.asarray(masks, dtype=bool)
        if array.shape[1:] != tuple(shape):
            raise CacheFailure("public_input_missing_or_malformed", f"mask shape {array.shape[1:]} != {shape}")
    else:
        array = np.zeros((0, *shape), dtype=bool)
    packed = np.packbits(array.reshape(count, -1), axis=1) if count else np.zeros((0, 0), dtype=np.uint8)
    np.savez_compressed(path, packed=packed, shape=np.asarray([count, *shape], dtype=np.int64),
                        mask_sha256=np.asarray(list(mask_sha256s), dtype="U64"))
    return path.stat().st_size


def read_masks_file(path: Path) -> dict[str, Any]:
    """Decode one recovered-mask file: ``masks`` (bool [n, H, W]) and ``mask_sha256`` (list)."""

    with np.load(path) as archive:
        count, height, width = (int(v) for v in archive["shape"])
        packed = archive["packed"]
        shas = [str(v) for v in archive["mask_sha256"]]
    if count:
        flat = np.unpackbits(packed, axis=1)[:, :height * width].astype(bool)
        masks = flat.reshape(count, height, width)
    else:
        masks = np.zeros((0, height, width), dtype=bool)
    return {"masks": masks, "mask_sha256": shas}


def match_recovered_masks(cache_frame: dict[str, Any], admitted: list[Any]) -> dict[str, Any]:
    """Do the re-run proposals reproduce the sealed frame's fragments, digest for digest, in order?

    白话：回收 mask 的前提是 SAM 在同一配置下逐位复现出当初进 cache 的那些 mask。这里把重算并
    按 D-215 边界准入、按摘要排序后的 mask 摘要序列，与封印帧里的 fragment 摘要序列逐位比对；
    不一致就整条 episode 登记 ``fragment_mask_mismatch``，不用 IoU 近似匹配冒充一致。
    """

    expected = [row["mask_sha256"] for row in cache_frame["fragments"]]
    found = [mask.mask_sha256 for mask in admitted]
    mismatched = [i for i, (a, b) in enumerate(zip(expected, found)) if a != b]
    if len(expected) != len(found):
        mismatched += list(range(min(len(expected), len(found)), max(len(expected), len(found))))
    return {"matched": not mismatched, "cache_count": len(expected), "recovered_count": len(found),
            "mismatched_positions": mismatched}


def recover_episode_masks(task: dict[str, Any]) -> dict[str, Any]:
    """Re-run SAM only over one cached episode and write ``NNNN.masks.npz`` beside every frame.

    白话：不改 cache 里的任何字节。逐帧重跑冻结的 SAM 与同一准入规则，摘要逐位对上才写 mask 文
    件；对不上就整条失败并留回执。DINO 不跑。回执记每帧是否匹配、字节数与每帧秒数。
    """

    started = time.time()
    episode_id = task["episode_id"]
    cache_dir = Path(task["cache_dir"])
    receipt: dict[str, Any] = {"episode_id": episode_id, "code_commit": task["commit"], "mode": "recover_masks"}
    frames_done = 0
    fragments_total = 0
    bytes_written = 0
    mismatched_frames: list[dict[str, Any]] = []
    models: FrozenModels | None = None
    try:
        cache_receipt = json.loads((cache_dir / "receipt.json").read_text(encoding="utf-8"))
        if cache_receipt.get("status") != "succeeded":
            raise CacheFailure("public_input_missing_or_malformed", "cache episode did not succeed")
        seal = json.loads((cache_dir / "episode_seal.json").read_text(encoding="utf-8"))
        frame_paths = sorted(cache_dir.glob(f"*{FRAME_FILE_SUFFIX}"))
        if len(frame_paths) != seal["episode_frame_count"]:
            raise CacheFailure("public_input_missing_or_malformed", "cache frame count differs from the seal")
        frontend = frozen_frontend()
        models = worker_models(frontend, task["assets"], descriptor_configs(frontend))
        models.reset_peak_memory()
        public_dir = Path(task["episode_root"]) / "public"
        seal_inputs = []
        for index, frame_path in enumerate(frame_paths):
            cache_frame = load_cache_frame(frame_path)
            if cache_frame["tick"] != index + 1:
                raise CacheFailure("public_input_missing_or_malformed", f"tick {cache_frame['tick']} at {index}")
            seal_inputs.append({"tick": cache_frame["tick"], "frame_seal": cache_frame["frame_seal"]})
            frame = read_public_frame(public_dir, index)
            raw = models.masks(frame["rgb"])
            admitted = fc.admit_proposals([anonymous(mask, ordinal) for ordinal, mask in enumerate(raw)])
            match = match_recovered_masks(cache_frame, admitted)
            if not match["matched"]:
                mismatched_frames.append({"index": index, **{k: v for k, v in match.items() if k != "matched"}})
                if len(mismatched_frames) >= int(task.get("mismatch_limit") or 1):
                    raise CacheFailure("public_input_missing_or_malformed", "fragment_mask_mismatch")
                continue
            bytes_written += write_masks_file(
                cache_dir / f"{index:04d}{MASK_FILE_SUFFIX}", [mask.as_array() for mask in admitted],
                [mask.mask_sha256 for mask in admitted], shape=tuple(frame["rgb"].shape[:2]))
            fragments_total += len(admitted)
            frames_done += 1
        recomputed = fc.seal_episode(seal_inputs, frontend_config_sha256=fc.D223_FRONTEND_CONFIG_SHA256)
        if recomputed["payload_sha256"] != seal["payload_sha256"]:
            raise CacheFailure("public_input_missing_or_malformed", "cache_missing_or_unsealed")
        if mismatched_frames:
            receipt.update({"status": "failed", "reason": "fragment_mask_mismatch"})
        else:
            receipt.update({"status": "succeeded"})
        receipt["episode_seal_sha256"] = seal["payload_sha256"]
    except (CacheFailure, fc.LeanFrontendCacheError) as failure:
        detail = getattr(failure, "detail", str(failure))
        reason = "fragment_mask_mismatch" if "fragment_mask_mismatch" in detail else (
            "cache_missing_or_unsealed" if "cache_missing_or_unsealed" in detail else failure.reason)
        receipt.update({"status": "failed", "reason": reason if reason in RECOVERY_FAILURE_REASONS else
                        "public_input_missing_or_malformed", "detail": detail[:400]})
    except Exception as exc:  # noqa: BLE001
        receipt.update({"status": "failed", "reason": "public_input_missing_or_malformed",
                        "detail": (repr(exc) + " | " + traceback.format_exc()[-800:])})
    wall = time.time() - started
    receipt.update({
        "frames_written": frames_done, "fragments_written": fragments_total,
        "mismatched_frames": mismatched_frames, "bytes_written": bytes_written,
        "wall_seconds": round(wall, 1), "seconds_per_frame": round(wall / frames_done, 3) if frames_done else None,
        "peak_vram_reserved_mib": models.peak_reserved_mib() if models is not None else None,
        "peak_rss_mib": peak_rss_mib(), "worker_pid": os.getpid(),
    })
    (cache_dir / "mask_recovery_receipt.json").write_text(json.dumps(receipt, indent=1))
    return receipt


def recovery_plan(cache_root: Path) -> dict[str, list[str]]:
    """What a recovery pass over an existing cache root already holds, per succeeded cache episode.

    A succeeded recovery receipt is reused; a failed one is final and kept -- the episode is not
    retried under this root, so a SAM mismatch stays on record instead of being overwritten by a
    later attempt; an episode without a recovery receipt runs.  Same rule as ``resume_plan``.

    白话：mask 回收的续跑只做还没有回执的 episode。成功回执直接复用；失败回执（比如 SAM 不逐位
    复现）保留原样、不自动重试也不覆盖；要重试属于用户裁决，不由脚本自作主张。
    """

    kept_succeeded, kept_failed, run = [], [], []
    for receipt_path in sorted(cache_root.glob("procthor10k-*/receipt.json")):
        cache_dir = receipt_path.parent
        if json.loads(receipt_path.read_text(encoding="utf-8")).get("status") != "succeeded":
            continue
        previous = cache_dir / "mask_recovery_receipt.json"
        if previous.exists():
            status = json.loads(previous.read_text(encoding="utf-8")).get("status")
            (kept_succeeded if status == "succeeded" else kept_failed).append(cache_dir.name)
            continue
        run.append(cache_dir.name)
    return {"kept_succeeded": kept_succeeded, "kept_failed": kept_failed, "run": run}


def recover_masks_main(args: Any, *, contract: dict[str, Any], assets: dict[str, str], commit: str) -> int:
    """``--recover-masks``: the SAM-only pass over an existing cache root (LOG-241, ruling 48)."""

    s1_04 = json.loads(S1_04_CONTRACT_PATH.read_text(encoding="utf-8"))
    if s1_04["authorization"].get("fragment_mask_recovery") is not True:
        print("S1-04 authorization bit fragment_mask_recovery is closed; refusing")
        return 2
    cache_root = Path(args.output_root)
    if not cache_root.exists():
        print(f"cache root does not exist: {cache_root}; refusing")
        return 2
    roots = {directory.name: directory for root in args.episode_roots.split(",")
             for directory in sorted(Path(root).glob("procthor10k-*"))}
    planned = recovery_plan(cache_root)
    tasks = []
    kept: list[dict[str, Any]] = []
    for episode_id in planned["kept_succeeded"] + planned["kept_failed"]:
        kept.append(json.loads((cache_root / episode_id / "mask_recovery_receipt.json").read_text(encoding="utf-8")))
    for episode_id in planned["run"]:
        if episode_id not in roots:
            print(f"no S1-02 episode root for {episode_id}; refusing")
            return 2
        tasks.append({"episode_id": episode_id, "cache_dir": str(cache_root / episode_id), "episode_root": str(roots[episode_id]),
                      "commit": commit, "assets": assets, "mismatch_limit": 1})
    actual_workers = max(1, min(args.workers, max(1, len(tasks))))
    plan = {"stage": "s1-03-mask-recovery", "commit": commit, "episodes": [t["episode_id"] for t in tasks],
            "kept_from_receipts": [r["episode_id"] for r in kept],
            "kept_succeeded": planned["kept_succeeded"], "kept_failed_never_retried": planned["kept_failed"],
            "requested_workers": args.workers,
            "actual_workers": actual_workers, "worker_basis": args.worker_basis,
            "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    (cache_root / f"mask_recovery_plan-{stamp}.json").write_text(json.dumps(plan, indent=1))
    print(f"[s1-03 recover-masks] {len(tasks)} episodes to run ({len(kept)} kept), {actual_workers} workers, "
          f"commit {commit[:12]}", flush=True)
    started = time.time()
    results = list(kept)
    if tasks:
        context = mp.get_context("spawn")
        with context.Pool(processes=actual_workers) as pool:
            for row in pool.imap_unordered(recover_episode_masks, tasks, chunksize=1):
                results.append(row)
                print(f"[s1-03 recover-masks] {len(results)}/{len(tasks) + len(kept)} {row['episode_id']} {row['status']} "
                      f"frames={row.get('frames_written')} s/frame={row.get('seconds_per_frame')} "
                      f"{('reason=' + str(row.get('reason'))) if row['status'] != 'succeeded' else ''} "
                      f"elapsed={time.time() - started:.0f}s", flush=True)
    results.sort(key=lambda r: r["episode_id"])
    succeeded = [r for r in results if r["status"] == "succeeded"]
    receipt = {
        "stage": "s1-03-mask-recovery", "code_commit": commit,
        "episodes_planned": len(tasks) + len(kept), "episodes_succeeded": len(succeeded),
        "episodes_failed": len(results) - len(succeeded),
        "failure_receipts": [{"episode_id": r["episode_id"], "reason": r.get("reason"),
                              "mismatched_frames": r.get("mismatched_frames", [])[:5]} for r in results if r["status"] != "succeeded"],
        "frames_written": sum(r.get("frames_written", 0) for r in succeeded),
        "fragments_written": sum(r.get("fragments_written", 0) for r in succeeded),
        "bytes_written": sum(r.get("bytes_written", 0) for r in succeeded),
        "episode_seals": {r["episode_id"]: r.get("episode_seal_sha256") for r in succeeded},
        "requested_workers": args.workers, "actual_workers": actual_workers, "worker_basis": args.worker_basis,
        "wall_clock_seconds": round(time.time() - started, 1),
        "complete": len(results) == len(tasks) + len(kept),
    }
    name = "s1_03_mask_recovery_receipt.json" if receipt["complete"] and receipt["episodes_failed"] == 0 \
        else f"s1_03_mask_recovery_receipt.partial-{stamp}.json"
    (cache_root / name).write_text(json.dumps(receipt, indent=1))
    print(json.dumps(receipt, indent=1))
    return 0 if receipt["complete"] and receipt["episodes_failed"] == 0 else 1


def causal_pose(record: dict[str, Any], *, code_commit: str, policy: dict[str, Any]) -> dict[str, Any]:
    """The public frame's causal pose, read under the ruling-49 correction policy.

    白话：位姿不再原样照抄。按合同 ``public_pose_correction`` 登记的提交表，旧编码器生成的
    episode 把俯仰角符号翻回来，新编码器生成的照原样读，没登记的提交拒绝。位置不变。
    """

    try:
        return pp.public_camera_pose(record, code_commit=code_commit, policy=policy)
    except pp.LeanPublicPoseError as exc:
        raise CacheFailure("public_input_missing_or_malformed", f"public_pose:{exc}") from exc


def recovered_masks(path: Path, shape: tuple[int, int]) -> list[np.ndarray]:
    """One frame's masks from a superseded root's ``NNNN.masks.npz``, each re-digested from its pixels.

    白话：``--masks-from`` 不跑 SAM，而是读旧根里回收好的 mask 文件。读进来的每个 mask 都按定义
    从像素重算摘要，与文件里存的摘要逐位比对，尺寸也要和本帧 RGB 一致；对不上就整条失败。
    """

    if not path.exists():
        raise CacheFailure("public_input_missing_or_malformed", f"recovered masks missing: {path.name}")
    loaded = read_masks_file(path)
    masks = np.asarray(loaded["masks"], dtype=bool)
    if masks.shape[0] != len(loaded["mask_sha256"]):
        raise CacheFailure("public_input_missing_or_malformed", f"{path.name}: {masks.shape[0]} masks for {len(loaded['mask_sha256'])} digests")
    if masks.shape[0] and tuple(masks.shape[1:]) != tuple(shape):
        raise CacheFailure("public_input_missing_or_malformed", f"{path.name}: mask shape {masks.shape[1:]} != frame {shape}")
    for index, digest in enumerate(loaded["mask_sha256"]):
        if fc.mask_sha256_of(masks[index]) != digest:
            raise CacheFailure("public_input_missing_or_malformed", f"{path.name}: mask {index} pixels do not reproduce the stored digest")
    return [masks[index] for index in range(masks.shape[0])]


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
                 descriptor_cfgs: dict[str, DINORegionConfig], device: str = "cuda", *, load_sam: bool = True) -> None:
        import torch

        if device == "cuda" and not torch.cuda.is_available():
            raise CacheFailure("public_input_missing_or_malformed", "cuda requested but unavailable")
        self.torch = torch
        self.device = device
        self.descriptor_cfgs = descriptor_cfgs
        # ``--masks-from`` (ruling 49) reads recovered masks instead of running SAM, so the
        # generator is not built at all in that mode and ``masks`` refuses to be called.
        self.generator = None
        if load_sam:
            from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
            from sam2.build_sam import build_sam2

            d215 = json.loads(D215_CONTRACT_PATH.read_text(encoding="utf-8"))["sam2"]
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
        if self.generator is None:
            raise CacheFailure("public_input_missing_or_malformed", "SAM was not loaded in this worker (--masks-from mode)")
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
                  descriptor_cfgs: dict[str, DINORegionConfig], *, load_sam: bool = True) -> FrozenModels:
    """The models of this worker process, built on first use and kept for every later episode."""

    global _WORKER_MODELS
    if _WORKER_MODELS is None:
        _WORKER_MODELS = FrozenModels(frontend, assets, descriptor_cfgs, load_sam=load_sam)
    if load_sam and _WORKER_MODELS.generator is None:
        raise CacheFailure("public_input_missing_or_malformed", "this worker was started without SAM")
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
    disk_floor = int(task.get("disk_floor_bytes") or 0)
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
        masks_from = Path(task["masks_from"]) / episode_id if task.get("masks_from") else None
        models = worker_models(frontend, task["assets"], descriptor_cfgs, load_sam=masks_from is None)
        models.reset_peak_memory()
        pose_policy = task["pose_policy"]
        try:
            pose_corrected = pp.correction_applies(task["episode_code_commit"], pose_policy)
        except pp.LeanPublicPoseError as exc:
            raise CacheFailure("public_input_missing_or_malformed", f"public_pose:{exc}") from exc
        receipt.update({"episode_code_commit": task["episode_code_commit"], "pose_correction_applied": pose_corrected,
                        "mask_source": ("recovered:" + str(masks_from)) if masks_from else "sam"})
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
            if masks_from is not None:
                raw = recovered_masks(masks_from / f"{index:04d}{MASK_FILE_SUFFIX}", tuple(frame["rgb"].shape[:2]))
            else:
                raw = models.masks(frame["rgb"])
            seconds["sam"] += time.time() - mark
            mark = time.time()
            tokens = models.patch_tokens(frame["rgb"])
            seconds["dino"] += time.time() - mark
            mark = time.time()
            admitted = fc.admit_proposals([anonymous(mask, ordinal) for ordinal, mask in enumerate(raw)])
            pose = causal_pose(record, code_commit=task["episode_code_commit"], policy=pose_policy)
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
            if disk_floor:
                free = shutil.disk_usage(out_dir).free
                if free - len(compressed) < disk_floor:
                    raise InfrastructureAbort("disk_floor", f"free {free} bytes, floor {disk_floor} bytes")
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
    except InfrastructureAbort as abort:
        receipt.update({"status": "aborted", "reason": abort.reason, "detail": abort.detail[:400]})
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


def resume_plan(out_root: Path, episode_ids: list[str]) -> dict[str, list[str]]:
    """What an existing output root already holds, per episode, and what a resume must redo.

    A succeeded or failed receipt is final and kept (a failed episode is never replaced); an
    aborted receipt or a directory without one is a partial that the resume clears and redoes.

    白话：续跑只重做没跑完的 episode——有 succeeded 或 failed 回执的都保留原样，被中断的
    （aborted 回执或根本没有回执）整目录清掉重来。它不换样本，也不重跑已经成功的。
    """

    kept_succeeded, kept_failed, redo = [], [], []
    for episode_id in episode_ids:
        directory = out_root / episode_id
        receipt_path = directory / "receipt.json"
        if receipt_path.exists():
            status = json.loads(receipt_path.read_text(encoding="utf-8")).get("status")
            if status == "succeeded":
                kept_succeeded.append(episode_id)
                continue
            if status == "failed":
                kept_failed.append(episode_id)
                continue
        redo.append(episode_id)
    return {"kept_succeeded": kept_succeeded, "kept_failed": kept_failed, "redo": redo}


def stage_receipt(results: list[dict[str, Any]], *, tasks_planned: int, commit: str, trial: bool,
                  verified: dict[str, Any], args: argparse.Namespace, actual_workers: int,
                  snapshot: dict[str, Any], started: float, aborted: dict[str, Any] | None,
                  interrupted: list[str]) -> dict[str, Any]:
    results = sorted(results, key=lambda row: row["episode_id"])
    failed = [row for row in results if row["status"] == "failed"]
    succeeded = [row for row in results if row["status"] == "succeeded"]
    merged: dict[str, int] = {}
    for row in results:
        for key, value in (row.get("fragments_per_frame_histogram") or {}).items():
            merged[key] = merged.get(key, 0) + value
    frames_total = sum(r.get("frames", 0) for r in succeeded)
    complete = aborted is None and not interrupted and len(succeeded) + len(failed) == tasks_planned
    return {
        "stage": "s1-03", "trial": trial, "code_commit": commit, "complete": complete,
        "episodes_planned": tasks_planned, "episodes_succeeded": len(succeeded),
        "episodes_failed": len(failed),
        "failure_receipts": [{"episode_id": r["episode_id"], "reason": r["reason"],
                              "detail": r.get("detail", "")[:400]} for r in failed],
        "frames_total": frames_total,
        "fragments_total": sum(r.get("fragments", 0) for r in succeeded),
        "fragments_per_frame_histogram": dict(sorted(merged.items(), key=lambda kv: int(kv[0]))),
        "frames_with_zero_fragments": merged.get("0", 0),
        "fragment_yield_frames_with_at_least_one_fragment": (
            sum(r.get("frames_with_fragments", 0) for r in succeeded) / max(1, frames_total)),
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
        "disk_floor_gib": args.disk_floor_gib,
        "aborted": aborted, "interrupted_episodes": sorted(interrupted),
        "exit_status": 3 if (aborted or interrupted) else (0 if not failed else 1),
    }


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
    parser.add_argument("--disk-floor-gib", type=float, default=2.0,
                        help="a worker aborts the run instead of writing a frame that would leave less "
                             "than this free on the output volume; a safety line, not a compute budget")
    parser.add_argument("--resume", action="store_true",
                        help="continue an existing output root: succeeded and failed receipts are kept, "
                             "aborted or receipt-less episodes are cleared and redone")
    parser.add_argument("--trial-frame-limit", type=int, default=None,
                        help="measurement only: cache at most this many frames per episode and write a "
                             "trial receipt instead of the stage receipt; never a stage run")
    parser.add_argument("--trial-episodes", type=int, default=None,
                        help="measurement only: cache at most this many episodes (requires --trial-frame-limit)")
    parser.add_argument("--recover-masks", action="store_true",
                        help="SAM-only pass over an existing cache root (--output-root): re-run the frozen "
                             "generator per frame, verify every mask digest against the sealed frame and write "
                             "NNNN.masks.npz beside it; needs the S1-04 fragment_mask_recovery bit")
    parser.add_argument("--masks-from", default=None,
                        help="ruling 49: a superseded cache root whose episodes carry recovered masks "
                             "(NNNN.masks.npz plus a succeeded mask_recovery_receipt.json); SAM is not loaded, "
                             "the masks are read and re-digested from their pixels per frame; episodes without "
                             "a succeeded recovery receipt there are skipped and listed")
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
    blocking = blocking_null_slots(contract)
    if blocking:
        print(f"registered value still null and consumed by this stage, refusing: {', '.join(blocking)}")
        return 2

    frontend = frozen_frontend()
    assets = json.loads(Path(args.assets_json).read_text(encoding="utf-8"))
    verified = verify_assets(assets, contract)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                            cwd=ROOT).stdout.strip()
    if args.recover_masks:
        if trial or args.resume or args.masks_from:
            print("--recover-masks cannot be combined with --resume, --masks-from or a trial; refusing")
            return 2
        return recover_masks_main(args, contract=contract, assets=assets, commit=commit)
    pose_policy = contract["public_pose_correction"]
    masks_from = Path(args.masks_from).resolve() if args.masks_from else None
    if masks_from is not None and not masks_from.is_dir():
        print(f"--masks-from root does not exist: {masks_from}; refusing")
        return 2
    out_root = Path(args.output_root)
    if trial and not out_root.name.endswith("-trial"):
        print("a trial run must write to an output root ending in -trial; refusing")
        return 2
    if not trial and out_root.name.endswith("-trial"):
        print("a stage run must not write to a -trial output root; refusing")
        return 2
    if out_root.exists() and any(out_root.iterdir()) and not args.resume:
        print(f"output root exists and is not empty: {out_root}; pass --resume to continue it")
        return 2
    out_root.mkdir(parents=True, exist_ok=True)

    episodes = []
    episode_commits: dict[str, str] = {}
    skipped_no_recovered_masks: list[dict[str, Any]] = []
    for root in args.episode_roots.split(","):
        for directory in sorted(Path(root).glob("procthor10k-*")):
            receipt_path = directory / "receipt.json"
            if not receipt_path.exists():
                continue
            source = json.loads(receipt_path.read_text(encoding="utf-8"))
            if source["status"] != "succeeded":
                continue
            # ruling 49: the pose policy must know this episode's generator commit before anything runs
            try:
                pp.correction_applies(source.get("code_commit"), pose_policy)
            except pp.LeanPublicPoseError as exc:
                print(f"{directory.name}: {exc}; refusing (register the commit in public_pose_correction first)")
                return 2
            if masks_from is not None:
                recovery_receipt = masks_from / directory.name / "mask_recovery_receipt.json"
                recovery = json.loads(recovery_receipt.read_text(encoding="utf-8")) if recovery_receipt.exists() else None
                if not recovery or recovery.get("status") != "succeeded":
                    old_cache = masks_from / directory.name / "receipt.json"
                    old = json.loads(old_cache.read_text(encoding="utf-8")) if old_cache.exists() else {}
                    skipped_no_recovered_masks.append({
                        "episode_id": directory.name,
                        "reason": ((recovery or {}).get("reason") or old.get("reason") or "no_recovery_receipt"),
                        "source_cache_status": old.get("status"), "recovery_status": (recovery or {}).get("status")})
                    continue
            episode_commits[directory.name] = source["code_commit"]
            episodes.append(directory)
    if not episodes:
        print("no succeeded episodes under the given roots; refusing")
        return 2
    if trial and args.trial_episodes is not None:
        episodes = episodes[:max(1, args.trial_episodes)]

    resumed = resume_plan(out_root, [d.name for d in episodes]) if args.resume else None
    kept_results: list[dict[str, Any]] = []
    if resumed:
        for episode_id in resumed["kept_succeeded"] + resumed["kept_failed"]:
            kept_results.append(json.loads((out_root / episode_id / "receipt.json").read_text(encoding="utf-8")))
        for episode_id in resumed["redo"]:
            partial = out_root / episode_id
            if partial.exists():
                shutil.rmtree(partial)
        episodes = [d for d in episodes if d.name in set(resumed["redo"])]

    tasks = [{
        "episode_id": directory.name, "episode_root": str(directory),
        "out": str(out_root / directory.name), "commit": commit, "assets": assets,
        "descriptor_asset_sha256s": verified["descriptor_asset_sha256s"],
        "frame_limit": args.trial_frame_limit,
        "disk_floor_bytes": int(args.disk_floor_gib * 2 ** 30),
        "episode_code_commit": episode_commits[directory.name], "pose_policy": pose_policy,
        "masks_from": (str(masks_from) if masks_from is not None else None),
    } for directory in episodes]
    pose_correction = {
        "decision_id": pose_policy["decision_id"], "rule": pose_policy["rule"],
        "applies_to_s1_02_code_commits": list(pose_policy["applies_to_s1_02_code_commits"]),
        "episodes_corrected": sorted(e for e, c in episode_commits.items() if pp.correction_applies(c, pose_policy)),
        "episodes_read_as_written": sorted(e for e, c in episode_commits.items() if not pp.correction_applies(c, pose_policy)),
    }
    tasks_planned = len(tasks) + len(kept_results)
    actual_workers = max(1, min(args.workers, max(1, len(tasks))))
    snapshot = resource_snapshot()
    snapshot["output_volume_free_gib_at_launch"] = round(shutil.disk_usage(out_root).free / 2 ** 30, 2)

    plan = {"stage": "s1-03", "trial": trial, "episodes": [t["episode_id"] for t in tasks], "commit": commit,
            "frontend_config_sha256": fc.D223_FRONTEND_CONFIG_SHA256,
            "asset_verification": verified,
            "requested_workers": args.workers, "actual_workers": actual_workers,
            "worker_basis": args.worker_basis, "resources_at_launch": snapshot,
            "sharding": "one episode per task, tasks handed to a spawn pool one at a time, "
                        "results merged in episode_id order",
            "disk_floor_gib": args.disk_floor_gib, "resume": resumed,
            "masks_from": (str(masks_from) if masks_from is not None else None),
            "episodes_skipped_no_recovered_masks": skipped_no_recovered_masks,
            "pose_correction": pose_correction,
            "trial_frame_limit": args.trial_frame_limit, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    plan_name = ("trial_plan" if trial else "plan") + (f".resume-{stamp}" if resumed else "") + ".json"
    (out_root / plan_name).write_text(json.dumps(plan, indent=1))
    print(f"[s1-03] {len(tasks)} episodes to run ({len(kept_results)} kept from receipts), {actual_workers} workers "
          f"(requested {args.workers}), trial={trial}, commit {commit[:12]}, "
          f"free {snapshot['output_volume_free_gib_at_launch']} GiB, floor {args.disk_floor_gib} GiB", flush=True)

    started = time.time()
    results: list[dict[str, Any]] = list(kept_results)
    aborted: dict[str, Any] | None = None
    if tasks:
        context = mp.get_context("spawn")
        pool = context.Pool(processes=actual_workers)
        try:
            for row in pool.imap_unordered(build_episode, tasks, chunksize=1):
                results.append(row)
                print(f"[s1-03] {len(results)}/{tasks_planned} {row['episode_id']} {row['status']} "
                      f"frames={row.get('frames_processed')} s/frame={row.get('seconds_per_frame')} "
                      f"vram={row.get('peak_vram_reserved_mib')}MiB rss={row.get('peak_rss_mib')}MiB "
                      f"bytes={row.get('bytes_written')} "
                      f"{('reason=' + str(row.get('reason'))) if row['status'] != 'succeeded' else ''} "
                      f"elapsed={time.time() - started:.0f}s", flush=True)
                if row["status"] == "aborted":
                    aborted = {"episode_id": row["episode_id"], "reason": row["reason"], "detail": row.get("detail", "")}
                    print(f"[s1-03] ABORT {row['reason']}: {row.get('detail', '')}; stopping the pool", flush=True)
                    pool.terminate()
                    break
            else:
                pool.close()
        finally:
            pool.join()
    done = {row["episode_id"] for row in results}
    interrupted = [t["episode_id"] for t in tasks if t["episode_id"] not in done]
    receipt = stage_receipt(results, tasks_planned=tasks_planned, commit=commit, trial=trial, verified=verified,
                            args=args, actual_workers=actual_workers, snapshot=snapshot, started=started,
                            aborted=aborted, interrupted=interrupted)
    receipt.update({
        "mask_source": ("recovered:" + str(masks_from)) if masks_from is not None else "sam",
        "episodes_skipped_no_recovered_masks": skipped_no_recovered_masks,
        "pose_correction": pose_correction,
        "episodes_pose_corrected": sorted(r["episode_id"] for r in results if r.get("pose_correction_applied")),
    })
    if trial:
        name = "trial_receipt.json"
    elif receipt["complete"]:
        name = "s1_03_receipt.json"
    else:
        name = f"s1_03_receipt.partial-{stamp}.json"
    (out_root / name).write_text(json.dumps(receipt, indent=1))
    print(json.dumps({k: v for k, v in receipt.items() if k not in ("resources_at_launch",)}, indent=1))
    return receipt["exit_status"]


if __name__ == "__main__":
    sys.exit(main())
