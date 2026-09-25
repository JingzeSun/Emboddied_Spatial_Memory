"""S2-05 oracle-frontend probe, step 1: simulator instance masks written as recovered-mask files (diagnostic only).

Usage:
    python ops/vsmt/lean_s2_05_oracle_masks.py --episode-roots <S1-02 root>,<S1-02 root> \\
        --episodes procthor10k-0.1.2-train-00702,... --output-root /root/autodl-tmp/vsmt_private/oracle-masks-<commit>

What it does: for every listed episode it reads the private instance image and the private
``object_id_to_entity_id`` mapping of each frame, turns every labelled instance with at least
``MINIMUM_VISIBLE_PIXELS`` pixels into one boolean mask (the ``MAXIMUM_PROPOSALS_PER_FRAME`` largest
when a frame has more, counted in the receipt), and writes them as ``NNNN.masks.npz`` in exactly the
recovered-mask format the S1-03 generator reads under ``--masks-from`` (packed bits, shape, one
``mask_sha256`` per mask recomputed by the frontend's digest), plus a ``mask_recovery_receipt.json``
with status ``succeeded`` so the generator picks the episode up and skips every other one.  The
generator then builds an oracle cache from these masks with the same DINOv2 descriptors, the same
fragment geometry and the same seals as the SAM cache; the node audit runs on that cache.

白话：这是"感知是不是混杂因素"的探针的第一步。SAM 前端的色块框是单帧深度表面壳，节点 IoU 天然低；
把模拟器自己的实例分割当成"完美分割"喂给同一条 cache 生成管线（不跑 SAM，其余逐字节相同），再用同
一套 runner／teacher／审计跑同样的 4 条 episode，就能看到"框对了以后 F1 能到多少"。它只暴露 mask 的
几何、不暴露实例 ID（ID 仍由方法从外观与位置推断）；输出是探针 cache 的输入，不是新前端、不进任何表，
也不改任何合同。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vsmt import lean_frontend_cache as fc  # noqa: E402

MASK_FILE_SUFFIX = ".masks.npz"
SOURCE = "simulator_instance_masks"


def _git(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=str(ROOT), text=True).strip()


def instance_masks(label_image: np.ndarray, object_id_to_label: dict[str, int], *, minimum_pixels: int, maximum: int) -> tuple[list[np.ndarray], dict[str, Any]]:
    """One boolean mask per labelled instance with enough pixels, the largest ``maximum`` when there are more."""

    image = np.asarray(label_image)
    labels = {int(label) for label in object_id_to_label.values()}
    values, counts = np.unique(image, return_counts=True)
    candidates = [(int(count), int(value)) for value, count in zip(values.tolist(), counts.tolist())
                  if int(value) in labels and int(count) >= minimum_pixels]
    candidates.sort(reverse=True)
    kept = candidates[:maximum]
    masks = [np.ascontiguousarray(image == value) for _count, value in kept]
    return masks, {"labelled_instances": len(labels), "eligible": len(candidates), "kept": len(kept), "capped": len(candidates) > maximum}


def write_masks_file(path: Path, masks: list[np.ndarray], shape: tuple[int, int]) -> list[str]:
    """The S1-03 recovered-mask format: packed bits, [count, H, W], one digest per mask."""

    count = len(masks)
    array = np.asarray(masks, dtype=bool) if count else np.zeros((0, *shape), dtype=bool)
    digests = [fc.mask_sha256_of(array[index]) for index in range(count)]
    packed = np.packbits(array.reshape(count, -1), axis=1) if count else np.zeros((0, 0), dtype=np.uint8)
    np.savez_compressed(path, packed=packed, shape=np.asarray([count, *shape], dtype=np.int64),
                        mask_sha256=np.asarray(digests, dtype="U64"))
    return digests


def write_episode(episode_root: Path, out_dir: Path, *, minimum_pixels: int = fc.MINIMUM_VISIBLE_PIXELS,
                  maximum: int = fc.MAXIMUM_PROPOSALS_PER_FRAME, commit: str = "") -> dict[str, Any]:
    from PIL import Image

    private = episode_root / "private"
    records = sorted(private.glob("*.frame.json"))
    if not records:
        raise FileNotFoundError(f"no private frames under {private}")
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = 0
    masks_total = 0
    capped_frames: list[int] = []
    per_frame: list[int] = []
    for index, record_path in enumerate(records):
        if record_path.name != f"{index:04d}.frame.json":
            raise ValueError(f"private frames are not contiguous at {record_path.name}")
        record = json.loads(record_path.read_text(encoding="utf-8"))
        image = np.asarray(Image.open(private / record["instance_mask_path"]))
        masks, info = instance_masks(image, record["object_id_to_entity_id"], minimum_pixels=minimum_pixels, maximum=maximum)
        write_masks_file(out_dir / f"{index:04d}{MASK_FILE_SUFFIX}", masks, tuple(int(v) for v in image.shape[:2]))
        frames += 1
        masks_total += len(masks)
        per_frame.append(len(masks))
        if info["capped"]:
            capped_frames.append(index)
    receipt = {"status": "succeeded", "source": SOURCE, "episode_id": episode_root.name, "frames": frames,
               "masks_total": masks_total, "masks_per_frame_max": max(per_frame), "masks_per_frame_mean": masks_total / frames,
               "minimum_pixels": minimum_pixels, "maximum_per_frame": maximum, "capped_frames": capped_frames,
               "diagnostic_only": True, "code_commit": commit, "written_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (out_dir / "mask_recovery_receipt.json").write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--episode-roots", required=True, help="comma-separated S1-02 output roots")
    parser.add_argument("--episodes", required=True, help="comma-separated episode ids to write (every other episode is skipped by the generator)")
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()
    commit = _git("rev-parse", "HEAD")
    roots = [Path(p).resolve() for p in args.episode_roots.split(",") if p]
    out_root = Path(args.output_root).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    receipts = []
    for episode_id in [e for e in args.episodes.split(",") if e]:
        candidates = [root / episode_id for root in roots if (root / episode_id / "receipt.json").exists()]
        if len(candidates) != 1:
            print(f"[oracle-masks] {episode_id}: {len(candidates)} episode roots found; refusing", file=sys.stderr)
            return 2
        receipt = write_episode(candidates[0], out_root / episode_id, commit=commit)
        receipts.append(receipt)
        print(f"[oracle-masks] {episode_id}: {receipt['frames']} frames, {receipt['masks_total']} masks, "
              f"max {receipt['masks_per_frame_max']} per frame, capped frames {len(receipt['capped_frames'])}", flush=True)
    (out_root / "oracle_masks_receipt.json").write_text(json.dumps({
        "source": SOURCE, "diagnostic_only": True, "code_commit": commit, "episodes": receipts,
        "note": "probe input for the S2-05 oracle-frontend probe; not a frontend, not a table input, no contract changed",
    }, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
