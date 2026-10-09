"""Export a front-end cache root (S1-03 or one S3-02 split and mask source) as a small ``results/*.json`` report.

Used by ``ops/vsmt/s3_02_data.sh`` for the instance-mask and SAM2 caches of the S3 train and validation splits.  The
report holds the schema version, code commit, stage-receipt summary, one row per episode (frames, fragments, seconds
per frame, bytes, seal digest) and the histogram of fragments per frame.  It copies no frame, descriptor, mask, private
instance ID or asset, and recomputes nothing: the yield is quoted from the stage receipt.

Usage (server, any Python with the standard library):
    python ops/vsmt/lean_s1_03_export.py --cache-root /root/autodl-tmp/vsmt_caches/lean-s1-03-<commit> \\
        --out results/vsmt_lean_s1_03_report_<commit>.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "vsmt-lean-s1-03-report-v1"
#: Per-episode receipt fields copied as they are; nothing else leaves the server.
EPISODE_FIELDS = (
    "status", "reason", "detail", "frames", "fragments", "frames_with_fragments", "episode_seal_sha256",
    "frames_processed", "wall_seconds", "seconds_per_frame", "seconds_by_part", "bytes_written",
    "bytes_uncompressed", "peak_vram_reserved_mib", "peak_rss_mib", "mask_source", "masks_from",
)
#: Stage receipt fields copied as they are (the histogram and the failure list are handled apart).
STAGE_FIELDS = (
    "stage", "trial", "code_commit", "complete", "episodes_planned", "episodes_succeeded", "episodes_failed",
    "frames_total", "fragments_total", "frames_with_zero_fragments", "fragment_yield_frames_with_at_least_one_fragment",
    "frontend_config_sha256", "descriptor_sets_extracted", "descriptor_asset_sha256s", "wall_clock_seconds",
    "requested_workers", "actual_workers", "worker_basis", "frames_processed_total", "bytes_written_total",
    "bytes_uncompressed_total", "peak_vram_reserved_mib_max", "peak_rss_mib_max", "seconds_by_part_total",
    "resources_at_launch", "aborted", "interrupted_episodes", "exit_status", "mask_source", "masks_from",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def episode_rows(root: Path) -> list[dict[str, Any]]:
    rows = []
    for receipt_path in sorted(root.glob("procthor10k-*/receipt.json")):
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        row: dict[str, Any] = {"episode_id": receipt["episode_id"], "code_commit": receipt.get("code_commit")}
        for name in EPISODE_FIELDS:
            value = receipt.get(name)
            row[name] = value.replace("\n", " ")[:400] if isinstance(value, str) and name == "detail" else value
        row["fragments_per_frame_histogram"] = receipt.get("fragments_per_frame_histogram")
        row["frame_files"] = len(list(receipt_path.parent.glob("*.cache.json.gz")))
        row["mask_files"] = len(list(receipt_path.parent.glob("*.masks.npz")))
        seal = receipt_path.parent / "episode_seal.json"  # ruling 72: a seal naming no source is sam2
        row["episode_seal_mask_source"] = (json.loads(seal.read_text(encoding="utf-8")).get("mask_source", "sam2")
                                           if seal.exists() else None)
        recovery = receipt_path.parent / "mask_recovery_receipt.json"
        row["mask_recovery_status"] = (json.loads(recovery.read_text(encoding="utf-8")).get("status")
                                       if recovery.exists() else None)
        rows.append(row)
    return rows


def build_report(root: Path) -> dict[str, Any]:
    stage_path = root / "s1_03_receipt.json"
    if not stage_path.exists():
        partials = sorted(root.glob("s1_03_receipt.partial-*.json"))
        if not partials:
            raise SystemExit(f"no stage receipt under {root}")
        stage_path = partials[-1]
    stage = json.loads(stage_path.read_text(encoding="utf-8"))
    plans = sorted(p for p in root.glob("plan*.json"))
    rows = episode_rows(root)
    return {
        "schema_version": SCHEMA_VERSION,
        "exported_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "cache_root": str(root),
        "stage_receipt_file": stage_path.name,
        "stage_receipt_sha256": _sha256(stage_path),
        "plan_files": [{"name": p.name, "sha256": _sha256(p)} for p in plans],
        "stage": {name: stage.get(name) for name in STAGE_FIELDS},
        "failure_receipts": stage.get("failure_receipts", []),
        "fragments_per_frame_histogram": stage.get("fragments_per_frame_histogram"),
        "episodes": rows,
        "episodes_with_recovered_masks": sum(1 for r in rows if r["mask_recovery_status"] == "succeeded"),
        "private_ids_exported": False,
        "contains_frames_descriptors_or_masks": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--cache-root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    report = build_report(Path(args.cache_root).resolve())
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    stage = report["stage"]
    print(f"[s1-03 export] {out} episodes {stage['episodes_succeeded']}/{stage['episodes_planned']} "
          f"frames {stage['frames_total']} fragments {stage['fragments_total']} sha256 {_sha256(out)[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
