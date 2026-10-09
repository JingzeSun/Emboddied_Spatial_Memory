"""S3-07 (ruling 111-8 step 3): render each 3RScan scan's annotated mesh at the 224 x 224 target camera, one worker per scan.

Usage (GPU host of S3-07, frozen frontend environment; CPU only):
    python ops/vsmt/s3_07_render.py --scans-root /root/autodl-tmp/3rscan/scans --meta /root/autodl-tmp/3rscan/meta/3RScan.json \\
        --out-root /root/autodl-tmp/s3_07_render-<commit>-sample --purpose sample --workers 4 --worker-basis "<evidence>"

For each scan: reads ``_info.txt`` (colour intrinsics) and the per-frame poses from ``sequence.zip`` and the annotated mesh
PLY, draws each frame's 16-bit instance image and metric depth at the target camera with ``lean_s3_07_render.render``,
writes ``<out>/<scan>/frame-NNNNNN.instance.png`` and ``.depth.npy``, and finally the scan's ``receipt.json`` (per-frame
output digests, mesh SHA-256, target intrinsics, counts, time, commit). ``--purpose sample`` draws only the registered
sample scene (the first validation scene by reference-scan ID and its rescans) into a root ending in ``-sample``, for the
sample check (111-8 step 4) of mesh against sensor depth; ``--purpose formal`` draws every validation scan and requires
the contract's ``authorization.formal_conversion`` open, every sample slot filled and a clean checkout. Resuming:
succeeded scans are kept; scans without a receipt (interrupted) are cleared and redrawn; failed scans are kept as they
are and only recorded. It reads no sensor depth and no change annotation and writes no episode (``s3_07_convert.py``
does).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import os
import shutil
import subprocess
import sys
import time
import traceback
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402

from vsmt import lean_s3_07_3rscan as r3  # noqa: E402
from vsmt import lean_s3_07_render as rr  # noqa: E402

STAGE = "vsmt.lean.s3_07.render.v1"
PURPOSES = ("sample", "formal")
SAMPLE_SUFFIX = "-sample"
THREAD_VARIABLES = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validation_scans(meta: list[dict[str, Any]]) -> list[list[str]]:
    """The validation scenes of ``3RScan.json`` sorted by reference id, each as [reference, rescans in listed order]."""

    scenes = sorted((scene for scene in meta if scene.get("type") == "validation"), key=lambda scene: scene["reference"])
    return [[scene["reference"], *[scan["reference"] for scan in scene["scans"]]] for scene in scenes]


def sample_scans(meta: list[dict[str, Any]]) -> list[str]:
    """Ruling 111 (DATA section 10, batch 1): the first validation scene by reference id and all its rescans."""

    scenes = validation_scans(meta)
    if not scenes:
        raise r3.LeanS307Error("no_validation_scene")
    return scenes[0]


def frame_names(names: list[str]) -> list[str]:
    """``frame-NNNNNN`` stems of the frames that carry a pose, in frame order."""

    stems = sorted(name[:-len(".pose.txt")].rsplit("/", 1)[-1] for name in names if name.endswith(".pose.txt"))
    return stems


def render_scan(task: dict[str, Any]) -> dict[str, Any]:
    """One worker, one scan: every frame rendered and written, then the scan's receipt (written last, so its presence = done)."""

    started = time.time()
    scan, out_dir = task["scan"], Path(task["out_dir"])
    receipt: dict[str, Any] = {"stage": STAGE, "scan": scan, "code_commit": task["commit"], "contract_sha256": task["contract_sha256"],
                               "purpose": task["purpose"], "render_rule": {"label_rule": rr.LABEL_RULE, "coverage_rule": rr.COVERAGE_RULE,
                                                                           "raster_near_m": rr.RASTER_NEAR_M}}
    try:
        scan_dir = Path(task["scans_root"]) / scan
        mesh_bytes = (scan_dir / "labels.instances.annotated.v2.ply").read_bytes()
        mesh = rr.read_ply(mesh_bytes)
        with zipfile.ZipFile(scan_dir / "sequence.zip") as archive:
            names = archive.namelist()
            info_names = [name for name in names if name.endswith("_info.txt")]
            if len(info_names) != 1:
                raise r3.LeanS307Error("sequence_info_missing_or_repeated")
            info = r3.parse_info(archive.read(info_names[0]).decode("utf-8"))
            target = r3.target_intrinsics(info["color_intrinsics"], info["color_size_wh"])
            prefix = info_names[0][:-len("_info.txt")]
            frames = frame_names(names)
            if not frames:
                raise r3.LeanS307Error("sequence_without_frames")
            out_dir.mkdir(parents=True, exist_ok=False)
            rows = []
            totals: dict[str, int] = {}
            from PIL import Image

            for stem in frames:
                pose = r3.parse_pose(archive.read(f"{prefix}{stem}.pose.txt").decode("utf-8"))
                instance, depth, counts = rr.render(mesh, pose, target)
                Image.fromarray(instance).save(out_dir / f"{stem}.instance.png")
                np.save(out_dir / f"{stem}.depth.npy", depth)
                rows.append({"frame": stem, "instance_sha256": sha256_bytes(instance.tobytes()),
                             "depth_sha256": sha256_bytes(depth.tobytes()), **counts})
                for key, value in counts.items():
                    totals[key] = totals.get(key, 0) + int(value)
        receipt.update({"status": "succeeded", "frames": len(rows), "mesh_sha256": sha256_bytes(mesh_bytes),
                        "mesh_faces": int(len(mesh["faces"])), "mesh_vertices": int(len(mesh["vertices"])),
                        "color_size_wh": list(info["color_size_wh"]), "color_intrinsics": info["color_intrinsics"],
                        "target_intrinsics": target, "totals": totals, "per_frame": rows})
    except Exception as exc:  # noqa: BLE001 -- every failure is recorded on the scan, the pool goes on
        receipt.update({"status": "failed", "reason": type(exc).__name__ + ":" + str(exc)[:200],
                        "detail": traceback.format_exc()[-800:]})
    receipt["wall_seconds"] = round(time.time() - started, 1)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "receipt.json").write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    return {key: receipt.get(key) for key in ("scan", "status", "frames", "reason", "wall_seconds")}


def git_state() -> tuple[str, int]:
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "src", "ops", "configs"], capture_output=True, text=True,
                           cwd=ROOT).stdout.splitlines()
    return commit, len(dirty)


def plan_tasks(scans: list[str], out_root: Path, *, resume: bool) -> tuple[list[str], list[dict[str, Any]], list[str]]:
    """(scans to render, receipts kept, interrupted scans cleared): succeeded and failed receipts are kept, a scan directory without
    a receipt is an interrupted render and is cleared before it is redone; without ``resume`` any existing scan directory refuses."""

    todo, kept, cleared = [], [], []
    for scan in scans:
        directory = out_root / scan
        receipt = directory / "receipt.json"
        if receipt.exists():
            if not resume:
                raise r3.LeanS307Error("output_exists_pass_resume:" + scan)
            data = json.loads(receipt.read_text(encoding="utf-8"))
            kept.append({key: data.get(key) for key in ("scan", "status", "frames", "reason", "wall_seconds")})
        elif directory.exists():
            if not resume:
                raise r3.LeanS307Error("output_exists_pass_resume:" + scan)
            shutil.rmtree(directory)
            cleared.append(scan)
            todo.append(scan)
        else:
            todo.append(scan)
    return todo, kept, cleared


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--scans-root", required=True)
    parser.add_argument("--meta", required=True, help="3RScan.json")
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--purpose", choices=PURPOSES, required=True)
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--worker-basis", default="", help="the measured evidence the worker count rests on (recorded)")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)

    contract = r3.load_contract()
    rr.check_contract(contract)
    contract_sha = sha256_bytes(r3.CONTRACT_PATH.read_bytes())
    meta = json.loads(Path(args.meta).read_text(encoding="utf-8"))
    commit, dirty = git_state()
    out_root = Path(args.out_root)
    if args.purpose == "sample":
        if not out_root.name.endswith(SAMPLE_SUFFIX):
            print(f"a sample render must write to an output root ending in {SAMPLE_SUFFIX}; refusing")
            return 2
        scans = sample_scans(meta)
    else:
        blocking = r3.blocking_null_slots(contract)
        if blocking or not contract["authorization"]["formal_conversion"]:
            print(f"formal rendering is not open (authorization.formal_conversion={contract['authorization']['formal_conversion']}, "
                  f"sample slots still null: {blocking}); refusing")
            return 2
        if dirty:
            print(f"{dirty} uncommitted change(s) under src/ops/configs; a formal render runs on a clean checkout; refusing")
            return 2
        if out_root.name.endswith(SAMPLE_SUFFIX):
            print(f"a formal render must not write to a {SAMPLE_SUFFIX} root; refusing")
            return 2
        scans = [scan for scene in validation_scans(meta) for scan in scene]
    missing = [scan for scan in scans if not (Path(args.scans_root) / scan).is_dir()]
    if missing:
        print(f"{len(missing)} scan(s) missing under {args.scans_root}, e.g. {missing[:3]}; refusing")
        return 2
    if args.workers < 1:
        print("--workers must be at least 1; refusing")
        return 2
    out_root.mkdir(parents=True, exist_ok=True)
    try:
        todo, kept, cleared = plan_tasks(scans, out_root, resume=args.resume)
    except r3.LeanS307Error as exc:
        print(f"{exc}; refusing")
        return 2
    actual = min(args.workers, max(1, len(todo)))
    plan = {"stage": STAGE, "purpose": args.purpose, "code_commit": commit, "dirty_files": dirty, "contract_sha256": contract_sha,
            "scans": scans, "todo": todo, "kept": [row["scan"] for row in kept], "cleared_interrupted": cleared,
            "workers_requested": args.workers, "workers_actual": actual, "worker_basis": args.worker_basis,
            "threads_per_worker": 1, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    (out_root / f"plan-{stamp}.json").write_text(json.dumps(plan, indent=1), encoding="utf-8")
    print(f"[s3-07 render] {args.purpose}: {len(todo)} scans to render, {len(kept)} kept, {len(cleared)} interrupted cleared, "
          f"{actual} workers (requested {args.workers}), commit {commit[:12]}", flush=True)
    for name in THREAD_VARIABLES:
        os.environ[name] = "1"
    tasks = [{"scan": scan, "scans_root": args.scans_root, "out_dir": str(out_root / scan), "commit": commit,
              "contract_sha256": contract_sha, "purpose": args.purpose} for scan in todo]
    results: list[dict[str, Any]] = list(kept)
    started = time.time()
    if tasks:
        with mp.get_context("spawn").Pool(processes=actual) as pool:
            for row in pool.imap_unordered(render_scan, tasks, chunksize=1):
                results.append(row)
                print(f"[s3-07 render] {len(results)}/{len(scans)} {row['scan']} {row['status']} frames={row.get('frames')} "
                      f"{row.get('wall_seconds')}s {('reason=' + str(row.get('reason'))) if row['status'] != 'succeeded' else ''}",
                      flush=True)
    by_status: dict[str, int] = {}
    for row in results:
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
    summary = {**plan, "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "wall_seconds": round(time.time() - started, 1), "by_status": by_status,
               "results": sorted(results, key=lambda row: row["scan"])}
    (out_root / "render_receipt.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(f"[s3-07 render] done: {by_status}", flush=True)
    return 0 if by_status.get("succeeded", 0) == len(scans) else 1


if __name__ == "__main__":
    sys.exit(main())
