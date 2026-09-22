"""S1-04: frontend diagnostics over the development cache (rulings 45/46/47).

Usage (server, frontend env; the S1-04 contract's ``private_plane_reading``, ``diagnostics_run`` and
``server_run`` bits must be open, plus ``reid_adapter_head_training`` for ``--reid``):
    python ops/vsmt/lean_s1_04_diagnostics.py \\
        --cache-root /root/autodl-tmp/vsmt_caches/lean-s1-03-<c> \\
        --episode-roots /root/autodl-tmp/vsmt_outputs/lean-s1-02a-<c>,/root/autodl-tmp/vsmt_outputs/lean-s1-02b-<c> \\
        --geometry-root /root/autodl-tmp/vsmt_private/lean-s1-04-geometry-<c> \\
        --output-root /root/autodl-tmp/vsmt_private/lean-s1-04-diagnostics-<commit> \\
        --workers 8 --worker-basis "<evidence>" [--reid]

What one worker does, per cached episode, and what it writes:
  1. read the sealed cache frames and verify the episode seal; read the recovered fragment masks
     (``NNNN.masks.npz``, S1-03 ``--recover-masks``) and verify every mask digest against the frame;
  2. open the private plane (allowed here: the cache was sealed before) and label every fragment
     by the strict-majority rule over private instance pixels; read the episode's geometry table
     and walk the truth tracker (ruling 45) to get each object's truth box per frame;
  3. compute, for both frozen descriptor sets: cross-view separation (add objects separately), the
     recall_miss curve against the ideal memory (ruling 46), and the fragment-versus-truth IoU
     rows with the observed-set proxy as a comparison column;
  4. write ``diagnostics.json`` and ``labelled_fragments.npz`` (both descriptor sets, object keys,
     centroids, frame indices; private-derived, stays under this private output root) and a receipt.

The orchestrator pools separation values, merges the recall curves, pools the IoU rows, and with
``--reid`` trains one projection head per frozen set on the 30 training houses (ruling 47), scores
it on the 12 selection houses only, applies the S1-05 selection rule and writes the weights.

白话：这个入口在开发 cache 上回答三件事：冻结描述子分不分得开同一物体的不同视角，S0-03 的召回
规则在不同 k/k′/半径下漏多少，单视角色块盒对整物体真值盒的 IoU 有多大。它读 private（cache 已封
印，允许）、读几何表、读回收的 mask；不选描述子、不定任何臂的参数、不算论文指标。加 ``--reid`` 时
按 30/12 留出训练投影并只在 12 条选择 house 上评分。
"""

from __future__ import annotations

import argparse
import gzip
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

import lean_s1_03_cache as cache_runner  # noqa: E402
from vsmt import lean_frontend_cache as fc  # noqa: E402
from vsmt import lean_frontend_diagnostics as fd  # noqa: E402
from vsmt import lean_object_geometry as og  # noqa: E402
from vsmt import lean_reid_head as rh  # noqa: E402

CONTRACT_PATH = ROOT / "configs" / "vsmt" / "lean_s1_04_frontend_diagnostics_v1.json"
S1_02A_CONTRACT_PATH = ROOT / "configs" / "vsmt" / "lean_s1_02a_pilot_v2.json"
REQUIRED_AUTHORIZATION = ("private_plane_reading", "diagnostics_run", "server_run")
DESCRIPTOR_KEYS = {"vits14": "descriptor_vits14", "vitb14": "descriptor_vitb14"}


class DiagnosticsFailure(Exception):
    def __init__(self, reason: str, detail: str = "") -> None:
        assert reason in fd.FAILURE_REASONS, reason
        super().__init__(f"{reason}: {detail}")
        self.reason, self.detail = reason, detail


def _git(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=str(ROOT), text=True).strip()


# --------------------------------------------------------------------------
# pure helpers (tested without models or files)
# --------------------------------------------------------------------------

def object_of_label(private_record: dict[str, Any]) -> dict[int, str]:
    return {int(label): str(oid) for oid, label in private_record["object_id_to_entity_id"].items()}


def label_frames(cache_frames: list[dict[str, Any]], masks_by_frame: list[dict[str, Any]],
                 private_records: list[dict[str, Any]], label_images: list[np.ndarray]) -> list[dict[str, Any]]:
    """Diagnostic frames: every cache fragment with its strict-majority private label.

    白话：把 cache 的每帧色块和回收的 mask 对上（摘要逐位核对），再拿私有实例图算每个色块落在
    哪个物体上的像素占比，严格过半才标。输出只保留诊断要的字段，两套描述子都带着。
    """

    if not (len(cache_frames) == len(masks_by_frame) == len(private_records) == len(label_images)):
        raise DiagnosticsFailure("private_plane_missing_or_malformed", "frame counts differ across planes")
    out = []
    for index, frame in enumerate(cache_frames):
        masks = masks_by_frame[index]
        expected = [row["mask_sha256"] for row in frame["fragments"]]
        if list(masks["mask_sha256"]) != expected:
            raise DiagnosticsFailure("fragment_masks_missing", f"frame {index}: recovered masks do not match the sealed frame")
        record = private_records[index]
        if record.get("observation_index") != index:
            raise DiagnosticsFailure("private_plane_missing_or_malformed", f"private record {index} out of order")
        labels = label_images[index]
        mapping = object_of_label(record)
        fragments = []
        for n, row in enumerate(frame["fragments"]):
            overlap = fd.overlap_from_masks(masks["masks"][n], labels, mapping)
            fragments.append({
                "fragment_id": row["fragment_id"], "object": fd.label_fragment(overlap),
                "descriptor_vits14": row["descriptor_vits14"], "descriptor_vitb14": row["descriptor_vitb14"],
                "centroid_m": row["centroid_m"], "aabb_min_m": row["aabb_min_m"], "aabb_max_m": row["aabb_max_m"],
                "pixel_count": row["pixel_count"],
            })
        out.append({"tick": frame["tick"], "fragments": fragments})
    return out


def iou_rows(labelled_frames: list[dict[str, Any]], truth_by_frame: list[dict[str, dict[str, Any]]],
             proxy_boxes: dict[str, tuple[list[float], list[float]]], rows_by_object: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per labelled fragment whose object has a truth box in that frame."""

    rows = []
    for frame, truth in zip(labelled_frames, truth_by_frame):
        for fragment in frame["fragments"]:
            key = fragment["object"]
            if key is None:
                continue
            entry = truth.get(key)
            if not entry or not entry.get("present") or entry.get("aabb_min_m") is None:
                continue
            proxy = proxy_boxes.get(key)
            meta = rows_by_object.get(key, {})
            rows.append({
                "iou_truth": og.aabb_iou(fragment["aabb_min_m"], fragment["aabb_max_m"], entry["aabb_min_m"], entry["aabb_max_m"]),
                "iou_proxy": (og.aabb_iou(fragment["aabb_min_m"], fragment["aabb_max_m"], proxy[0], proxy[1]) if proxy else None),
                "pickupable": bool(meta.get("pickupable")), "receptacle": bool(meta.get("receptacle")),
            })
    return rows


def descriptor_frames(labelled_frames: list[dict[str, Any]], set_name: str) -> list[dict[str, Any]]:
    """The labelled frames with one descriptor set exposed as ``descriptor``."""

    key = DESCRIPTOR_KEYS[set_name]
    return [{"tick": frame["tick"], "fragments": [
        {"fragment_id": f["fragment_id"], "object": f["object"], "descriptor": f[key], "centroid_m": f["centroid_m"]}
        for f in frame["fragments"]]} for frame in labelled_frames]


def labelled_arrays(labelled_frames: list[dict[str, Any]]) -> dict[str, np.ndarray]:
    """Arrays for the ReID stage: both descriptor sets, object keys, centroids, frame indices."""

    rows = [(i, f) for i, frame in enumerate(labelled_frames) for f in frame["fragments"] if f["object"] is not None]
    return {
        "frame_index": np.asarray([i for i, _ in rows], dtype=np.int64),
        "object": np.asarray([f["object"] for _, f in rows], dtype="U128"),
        "descriptor_vits14": np.asarray([f["descriptor_vits14"] for _, f in rows], dtype=np.float32).reshape(len(rows), -1),
        "descriptor_vitb14": np.asarray([f["descriptor_vitb14"] for _, f in rows], dtype=np.float32).reshape(len(rows), -1),
        "centroid_m": np.asarray([f["centroid_m"] for _, f in rows], dtype=np.float64).reshape(len(rows), -1),
    }


def frames_from_arrays(arrays: dict[str, np.ndarray], set_name: str) -> list[dict[str, Any]]:
    """Rebuild diagnostic frames (one descriptor set) from ``labelled_arrays`` output."""

    key = DESCRIPTOR_KEYS[set_name]
    count = int(arrays["frame_index"].max()) + 1 if arrays["frame_index"].size else 0
    frames = [{"tick": i + 1, "fragments": []} for i in range(count)]
    for n in range(arrays["frame_index"].shape[0]):
        i = int(arrays["frame_index"][n])
        frames[i]["fragments"].append({"fragment_id": f"{i}:{n}", "object": str(arrays["object"][n]),
                                       "descriptor": arrays[key][n].tolist(), "centroid_m": arrays["centroid_m"][n].tolist()})
    return frames


# --------------------------------------------------------------------------
# one episode
# --------------------------------------------------------------------------

def load_cache_episode(cache_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    receipt_path = cache_dir / "receipt.json"
    if not receipt_path.exists() or json.loads(receipt_path.read_text(encoding="utf-8")).get("status") != "succeeded":
        raise DiagnosticsFailure("cache_missing_or_unsealed", "no succeeded cache receipt")
    seal = json.loads((cache_dir / "episode_seal.json").read_text(encoding="utf-8"))
    frames = [cache_runner.load_cache_frame(path) for path in sorted(cache_dir.glob(f"*{cache_runner.FRAME_FILE_SUFFIX}"))]
    recomputed = fc.seal_episode([{"tick": f["tick"], "frame_seal": f["frame_seal"]} for f in frames],
                                 frontend_config_sha256=fc.D223_FRONTEND_CONFIG_SHA256)
    if recomputed["payload_sha256"] != seal["payload_sha256"]:
        raise DiagnosticsFailure("cache_missing_or_unsealed", "episode seal mismatch")
    return frames, seal


def load_masks(cache_dir: Path, count: int) -> list[dict[str, Any]]:
    out = []
    for index in range(count):
        path = cache_dir / f"{index:04d}{cache_runner.MASK_FILE_SUFFIX}"
        if not path.exists():
            raise DiagnosticsFailure("fragment_masks_missing", f"{path.name} (run lean_s1_03_cache.py --recover-masks)")
        out.append(cache_runner.read_masks_file(path))
    return out


def load_private(episode_root: Path, count: int) -> tuple[list[dict[str, Any]], list[np.ndarray]]:
    from PIL import Image
    private = episode_root / "private"
    records, images = [], []
    for index in range(count):
        record = json.loads((private / f"{index:04d}.frame.json").read_text(encoding="utf-8"))
        records.append(record)
        images.append(np.asarray(Image.open(private / record["instance_mask_path"])))
    return records, images


def proxy_boxes_over_episode(episode_root: Path, records: list[dict[str, Any]], images: list[np.ndarray],
                             *, minimum_depth_m: float, maximum_depth_m: float) -> dict[str, tuple[list[float], list[float]]]:
    """The observed-set box per object: union over frames of its private mask's back-projection box."""

    public = episode_root / "public"
    boxes: dict[str, tuple[list[float] | None, list[float] | None]] = {}
    for index, (record, labels) in enumerate(zip(records, images)):
        frame = json.loads((public / f"{index:04d}.frame.json").read_text(encoding="utf-8"))
        depth = np.load(public / frame["depth_path"]).astype(np.float32)
        pose = {"position_m": list(frame["relative_pose"]["position_m"]),
                "quaternion_xyzw": list(frame["relative_pose"]["quaternion_xyzw"])}
        for oid, label in record["object_id_to_entity_id"].items():
            mask = labels == int(label)
            if not mask.any():
                continue
            points = og.backproject_mask(mask, depth, frame["intrinsics"], pose,
                                         minimum_depth_m=minimum_depth_m, maximum_depth_m=maximum_depth_m)
            if points.shape[0] == 0:
                continue
            lower, upper = points.min(axis=0).tolist(), points.max(axis=0).tolist()
            previous = boxes.get(oid, (None, None))
            boxes[oid] = og.union_box(previous[0], previous[1], lower, upper)
    return {oid: (lo, hi) for oid, (lo, hi) in boxes.items() if lo is not None}


def diagnose_episode(task: dict[str, Any]) -> dict[str, Any]:
    started = time.time()
    episode_id = task["episode_id"]
    out_dir = Path(task["out"])
    receipt: dict[str, Any] = {"episode_id": episode_id, "code_commit": task["commit"]}
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        cache_dir = Path(task["cache_dir"])
        episode_root = Path(task["episode_root"])
        frames, seal = load_cache_episode(cache_dir)
        masks = load_masks(cache_dir, len(frames))
        records, images = load_private(episode_root, len(frames))
        labelled = label_frames(frames, masks, records, images)
        table_path = Path(task["geometry_dir"]) / og.TABLE_FILE_NAME
        if not table_path.exists():
            raise DiagnosticsFailure("table_invalid", f"{table_path} missing (run lean_s1_04_object_geometry.py)")
        table = og.validate_geometry_table(json.loads(table_path.read_text(encoding="utf-8")))
        executed, window = cache_runner_read_interventions(episode_root / "provenance")
        tracker = og.EpisodeTruthTracker(table, executed_interventions=executed, window=window)
        truth_by_frame = [tracker.update(index, record) for index, record in enumerate(records)]
        proxies = proxy_boxes_over_episode(episode_root, records, images,
                                           minimum_depth_m=task["minimum_depth_m"], maximum_depth_m=task["maximum_depth_m"])
        rows_by_object = {row["object_id"]: row for row in table["objects"]}
        add_objects = sorted(row["object_id"] for row in executed if row.get("kind") == "add")
        result: dict[str, Any] = {
            "episode_id": episode_id, "frames": len(frames), "episode_seal_sha256": seal["payload_sha256"],
            "fragments": sum(len(f["fragments"]) for f in labelled),
            "fragments_labelled": sum(1 for f in labelled for x in f["fragments"] if x["object"] is not None),
            "add_objects": add_objects,
            "separation": {}, "recall_curve": {},
            "fragment_truth_iou_rows": iou_rows(labelled, truth_by_frame, proxies, rows_by_object),
        }
        for set_name in DESCRIPTOR_KEYS:
            frames_for_set = descriptor_frames(labelled, set_name)
            result["separation"][set_name] = fd.separation_statistics(frames_for_set, separate_objects=add_objects)
            result["recall_curve"][set_name] = fd.recall_curve(frames_for_set)
        (out_dir / "diagnostics.json").write_text(json.dumps(result), encoding="utf-8")
        np.savez_compressed(out_dir / "labelled_fragments.npz", **labelled_arrays(labelled))
        receipt.update({"status": "succeeded", "frames": len(frames), "fragments": result["fragments"],
                        "fragments_labelled": result["fragments_labelled"], "episode_seal_sha256": seal["payload_sha256"],
                        "iou_rows": len(result["fragment_truth_iou_rows"])})
    except DiagnosticsFailure as failure:
        receipt.update({"status": "failed", "reason": failure.reason, "detail": failure.detail[:400]})
    except (og.LeanObjectGeometryError, fd.LeanDiagnosticsError) as exc:
        receipt.update({"status": "failed", "reason": "private_plane_missing_or_malformed", "detail": str(exc)[:400]})
    except Exception as exc:  # noqa: BLE001
        receipt.update({"status": "failed", "reason": "private_plane_missing_or_malformed",
                        "detail": (repr(exc) + " | " + traceback.format_exc()[-800:])})
    receipt.update({"wall_seconds": round(time.time() - started, 1), "worker_pid": os.getpid()})
    (out_dir / "receipt.json").write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    return receipt


def cache_runner_read_interventions(provenance_dir: Path) -> tuple[list[dict[str, Any]], list[int] | None]:
    """Same reader as the geometry tool (kept local so this runner does not import the simulator env module)."""

    executed: list[dict[str, Any]] = []
    window = None
    log_path = provenance_dir / "interventions.json"
    if log_path.exists():
        executed = [row for row in json.loads(log_path.read_text(encoding="utf-8")).get("executed", [])
                    if row.get("executed", True)]
    verdict_path = provenance_dir / "window_verdicts.json"
    if verdict_path.exists():
        raw = json.loads(verdict_path.read_text(encoding="utf-8")).get("window")
        if raw is not None:
            window = [int(raw[0]), int(raw[1])]
    return executed, window


# --------------------------------------------------------------------------
# aggregation and the ReID stage
# --------------------------------------------------------------------------

def aggregate(results: list[dict[str, Any]], out_root: Path) -> dict[str, Any]:
    """Pool the per-episode diagnostics of every succeeded episode."""

    pooled_sep: dict[str, list[float]] = {name: [] for name in DESCRIPTOR_KEYS}
    pooled_sep_add: dict[str, list[float]] = {name: [] for name in DESCRIPTOR_KEYS}
    curves: dict[str, list[dict[str, Any]]] = {name: [] for name in DESCRIPTOR_KEYS}
    rows: list[dict[str, Any]] = []
    per_house: dict[str, Any] = {}
    seals: dict[str, str] = {}
    for receipt in results:
        if receipt["status"] != "succeeded":
            continue
        data = json.loads((out_root / receipt["episode_id"] / "diagnostics.json").read_text(encoding="utf-8"))
        seals[receipt["episode_id"]] = data["episode_seal_sha256"]
        for name in DESCRIPTOR_KEYS:
            sep = data["separation"][name]
            pooled_sep[name].extend(sep["values"])
            curves[name].append(data["recall_curve"][name])
        rows.extend(data["fragment_truth_iou_rows"])
        per_house[receipt["episode_id"]] = {
            "fragments": data["fragments"], "fragments_labelled": data["fragments_labelled"],
            "separation_median": {name: data["separation"][name]["statistics"]["median"] for name in DESCRIPTOR_KEYS},
            "iou_median": fd.summarise([r["iou_truth"] for r in data["fragment_truth_iou_rows"]])["median"],
        }
    return {
        "episodes_used": len(seals),
        "separation_by_set": {name: fd.summarise(values) for name, values in pooled_sep.items()},
        "recall_curve_by_set": {name: (fd.merge_recall_curves(c) if c else None) for name, c in curves.items()},
        "fragment_truth_iou": fd.iou_statistics(rows),
        "per_house": per_house,
        "cache_episode_seals": seals,
    }


def reid_stage(results: list[dict[str, Any]], out_root: Path, *, contract: dict[str, Any], split_seed: int,
               device: str) -> dict[str, Any]:
    """Ruling 47: train one head per frozen set on the training houses, score on the selection houses."""

    values = {name: contract["reid_training"][name] for name in fd.REID_VALUE_SLOTS}
    houses = [r["episode_id"] for r in results if r["status"] == "succeeded"]
    split = rh.holdout_split(houses, seed=split_seed)
    report: dict[str, Any] = {"holdout": split, "values": values, "by_set": {}}
    arrays = {house: dict(np.load(out_root / house / "labelled_fragments.npz")) for house in houses}
    for set_name in DESCRIPTOR_KEYS:
        key = DESCRIPTOR_KEYS[set_name]
        train_episodes = {house: frames_from_arrays(arrays[house], set_name) for house in split["training_houses"]}
        data = rh.training_set(train_episodes, descriptor_key="descriptor")
        trained = rh.train_head(data["descriptors"], data["classes"], output_dimension=contract["reid_training"]["output_dimension"],
                                device=device, **values)
        weights_path = out_root / f"reid_head_{set_name}.json"
        weights_path.write_text(json.dumps(trained["weights"]), encoding="utf-8")
        selection_values: list[float] = []
        frozen_values: list[float] = []
        for house in split["selection_houses"]:
            frames = frames_from_arrays(arrays[house], set_name)
            frozen_values.extend(fd.separation_statistics(frames)["values"])
            projected = rh.project_frames(frames, trained["head"], source_key="descriptor")
            selection_values.extend(fd.separation_statistics(projected, descriptor_key="reid_projection")["values"])
        report["by_set"][set_name] = {
            "training_fragments": data["fragments"], "training_classes": data["class_count"],
            "classes_with_positives": data["classes_with_positives"], "diverged": trained["diverged"],
            "loss_curve": trained["loss_curve"], "weights_sha256": trained["weights"]["sha256"],
            "weights_file": weights_path.name,
            "selection_houses_separation_frozen": fd.summarise(frozen_values),
            "selection_houses_separation_projection": fd.summarise(selection_values),
        }
    medians = {}
    for set_name, entry in report["by_set"].items():
        medians[set_name] = entry["selection_houses_separation_frozen"]["median"]
        medians[f"reid_projection:{set_name}"] = entry["selection_houses_separation_projection"]["median"]
    report["selection_rule"] = rh.select_descriptor(medians, threshold=contract["reid_training"]["selection_rule_threshold"])
    report["selection_rule"]["note"] = "S1-05 applies this; nothing is frozen here"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--cache-root", required=True)
    parser.add_argument("--episode-roots", required=True, help="comma-separated S1-02 output roots")
    parser.add_argument("--geometry-root", required=True, help="the S1-04 object geometry output root")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--worker-basis", default="")
    parser.add_argument("--reid", action="store_true", help="also train and score the ReID heads (ruling 47)")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--allow-dirty", action="store_true", help="tests only")
    args = parser.parse_args()

    contract = fd.validate_contract(json.loads(CONTRACT_PATH.read_text(encoding="utf-8")))
    required = list(REQUIRED_AUTHORIZATION) + (["reid_adapter_head_training"] if args.reid else [])
    closed = [name for name in required if contract["authorization"].get(name) is not True]
    if closed:
        print(f"[s1-04] refused: authorization bits still closed: {closed}", file=sys.stderr)
        return 2
    if args.reid:
        null_values = [name for name in fd.REID_VALUE_SLOTS if contract["reid_training"][name] is None]
        if null_values:
            print(f"[s1-04] refused: ReID training values still null: {null_values}", file=sys.stderr)
            return 2
    if not args.allow_dirty and _git("status", "--porcelain"):
        print("[s1-04] refused: the checkout is not clean", file=sys.stderr)
        return 2
    commit = _git("rev-parse", "HEAD")
    geometry = json.loads((ROOT / "configs" / "vsmt" / "vm04_d223_f01_production_reader_v1.json").read_text(encoding="utf-8"))["frontend"]["fragment_geometry"]
    split_seed = int(json.loads(S1_02A_CONTRACT_PATH.read_text(encoding="utf-8"))["split_freeze"]["seed"])
    cache_root = Path(args.cache_root).resolve()
    out_root = Path(args.output_root).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    roots = {directory.name: directory for root in args.episode_roots.split(",")
             for directory in sorted(Path(root).glob("procthor10k-*"))}
    tasks = []
    skipped = []
    for receipt_path in sorted(cache_root.glob("procthor10k-*/receipt.json")):
        cache_dir = receipt_path.parent
        if json.loads(receipt_path.read_text(encoding="utf-8")).get("status") != "succeeded":
            skipped.append(cache_dir.name)
            continue
        tasks.append({"episode_id": cache_dir.name, "cache_dir": str(cache_dir), "episode_root": str(roots[cache_dir.name]),
                      "geometry_dir": str(Path(args.geometry_root) / cache_dir.name), "out": str(out_root / cache_dir.name),
                      "commit": commit, "minimum_depth_m": float(geometry["minimum_depth_m"]),
                      "maximum_depth_m": float(geometry["maximum_depth_m"])})
    actual = max(1, min(args.workers, max(1, len(tasks))))
    (out_root / "plan.json").write_text(json.dumps({
        "stage": "s1-04-diagnostics", "commit": commit, "episodes": [t["episode_id"] for t in tasks],
        "episodes_skipped_no_cache": skipped, "requested_workers": args.workers, "actual_workers": actual,
        "worker_basis": args.worker_basis, "reid": args.reid, "split_seed": split_seed,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=1), encoding="utf-8")
    print(f"[s1-04] {len(tasks)} episodes ({len(skipped)} skipped without cache), {actual} workers, commit {commit[:12]}", flush=True)
    started = time.time()
    results: list[dict[str, Any]] = []
    if actual <= 1:
        for task in tasks:
            results.append(diagnose_episode(task))
            print(f"[s1-04] {len(results)}/{len(tasks)} {results[-1]['episode_id']} {results[-1]['status']}", flush=True)
    else:
        context = mp.get_context("spawn")
        with context.Pool(processes=actual) as pool:
            for receipt in pool.imap_unordered(diagnose_episode, tasks, chunksize=1):
                results.append(receipt)
                print(f"[s1-04] {len(results)}/{len(tasks)} {receipt['episode_id']} {receipt['status']} "
                      f"{('reason=' + str(receipt.get('reason'))) if receipt['status'] != 'succeeded' else ''}", flush=True)
    results.sort(key=lambda r: r["episode_id"])
    report = aggregate(results, out_root)
    report.update({
        "stage": "s1-04-diagnostics", "code_commit": commit, "episodes_planned": len(tasks),
        "episodes_skipped_no_cache": skipped,
        "episodes_failed": [{"episode_id": r["episode_id"], "reason": r.get("reason"), "detail": (r.get("detail") or "")[:200]}
                            for r in results if r["status"] != "succeeded"],
        "fragments_labelled": sum(r.get("fragments_labelled", 0) for r in results if r["status"] == "succeeded"),
        "fragments_unlabelled": sum(r.get("fragments", 0) - r.get("fragments_labelled", 0) for r in results if r["status"] == "succeeded"),
        "requested_workers": args.workers, "actual_workers": actual, "worker_basis": args.worker_basis,
        "wall_clock_seconds": round(time.time() - started, 1),
    })
    if args.reid and report["episodes_used"]:
        report["reid"] = reid_stage(results, out_root, contract=contract, split_seed=split_seed, device=args.device)
    (out_root / "s1_04_diagnostics_receipt.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    summary = {k: v for k, v in report.items() if k not in ("per_house", "cache_episode_seals", "recall_curve_by_set")}
    if "reid" in summary:
        summary["reid"] = {k: v for k, v in summary["reid"].items() if k != "by_set"}
    print(json.dumps(summary, indent=1))
    return 0 if not report["episodes_failed"] else 1


if __name__ == "__main__":
    sys.exit(main())
