"""S1-04 (D-224-S1 ruling 45): one simulator reload per episode -> the private object geometry table.

Usage (server, simulator env; the S1-04 contract's ``object_geometry_reload`` bit must be open):
    /root/autodl-tmp/vsmt-envs/simulator-py39/bin/python ops/vsmt/lean_s1_04_object_geometry.py \\
        --episode-roots /root/autodl-tmp/vsmt_outputs/lean-s1-02a-<c>,/root/autodl-tmp/vsmt_outputs/lean-s1-02b-<c> \\
        --source /root/autodl-tmp/vsmt_sources/procthor-10k-0.1.2/train.jsonl.gz \\
        --output-root /root/autodl-tmp/vsmt_private/lean-s1-04-geometry-<commit> \\
        --workers 4 --worker-basis "<the measured evidence the worker count rests on>"

What one worker does, per succeeded S1-02 episode, and what it writes:
  1. read the episode's receipt (house id, source index); load the same house record from the
     frozen ProcTHOR-10K source, upgrade its schema and start CloudRendering with the S0-02
     parameters, exactly as the S1-02 runner did, but without depth or instance rendering;
  2. teleport to the house-authored agent pose (``bootstrap_house_agent``) and read the metadata
     once: every object's position, rotation and axis-aligned box, plus the camera position,
     which is the origin of every public pose of that episode (observation 0);
  3. write ``<output-root>/<episode_id>/object_geometry.json`` (S0-02 v3 ``private_house_geometry``)
     and stop the simulator; no action other than the bootstrap teleport is ever issued;
  4. run the two residual checks ruling 45 registered, reading the episode's private and
     provenance planes (this is a private-plane tool; it never touches the cache):
       - drift: how far every non-intervened object's recorded position strays from the reload;
       - containment: the share of frame-0 private-mask back-projections that fall inside the
         translated truth box of their object;
  5. write a receipt; a failure of any kind leaves a failure receipt with a registered reason.

The table is a private-plane product: it carries simulator object ids and world coordinates and
must never be mounted by a deployment reader.  It changes no file of the generated episodes.

白话：这个入口把裁决 45 落成文件。每条 episode 把它的 house 在模拟器里重新加载一次，站到 house
自带的起始位姿上，读一遍所有物体的初始位置、朝向和轴对齐盒，写成一份私有几何表；然后拿这份表
去对 episode 里记录的位置做两项残差检查（没被干预的物体有没有漂移、帧 0 的私有 mask 反投影点是
不是落在平移后的盒子里）。它不生成新 episode、不执行任何干预、不读 cache、不训练；失败的 house
留失败回执，不补样。
"""

from __future__ import annotations

import argparse
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

import vm04_two_house_worker as house_loader  # noqa: E402
from vsmt import lean_object_geometry as og  # noqa: E402

CONTRACT_PATH = ROOT / "configs" / "vsmt" / "lean_s1_04_frontend_diagnostics_v1.json"
#: The S1-02 runner's simulator parameters (S0-02); the reload must not differ.
WIDTH = HEIGHT = 224
FOV = 90.0
#: Authorization bit of the S1-04 contract this entry point needs.
REQUIRED_AUTHORIZATION = ("object_geometry_reload", "server_run")
#: Registered failure reasons of this tool.
FAILURE_REASONS = (
    "source_episode_not_succeeded",
    "house_load_failed",
    "metadata_missing_or_malformed",
    "private_plane_missing_or_malformed",
    "table_invalid",
)
#: A frame-0 object needs this many private mask pixels to enter the containment check
#: (the D-215 visibility floor, so the check speaks about objects a fragment could exist for).
CONTAINMENT_MINIMUM_PIXELS = 196


class GeometryFailure(Exception):
    def __init__(self, reason: str, detail: str = "") -> None:
        assert reason in FAILURE_REASONS, reason
        super().__init__(f"{reason}: {detail}")
        self.reason, self.detail = reason, detail


def _git(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=str(ROOT), text=True).strip()


def frozen_fragment_geometry() -> dict[str, Any]:
    """The D-223 fragment geometry (depth bounds) the containment check back-projects with.

    Read from the bound D-223 contract and checked against the digest S1-03 binds, so this tool
    cannot back-project private masks with different depth bounds than the cache used.
    """

    from vsmt import lean_frontend_cache as fc
    d223 = json.loads((ROOT / "configs" / "vsmt" / "vm04_d223_f01_production_reader_v1.json").read_text(encoding="utf-8"))
    frontend = d223["frontend"]
    if frontend["frontend_config_sha256"] != fc.D223_FRONTEND_CONFIG_SHA256:
        raise RuntimeError("the bound D-223 frontend digest no longer matches")
    return dict(frontend["fragment_geometry"])


def blocking_authorization(contract: dict[str, Any]) -> list[str]:
    """The required bits that are still closed."""

    return [name for name in REQUIRED_AUTHORIZATION if contract["authorization"].get(name) is not True]


def episode_tasks(episode_roots: list[Path]) -> list[dict[str, Any]]:
    """Every episode directory with a receipt, succeeded or not, in a fixed order."""

    tasks: list[dict[str, Any]] = []
    for root in episode_roots:
        for receipt_path in sorted(root.glob("procthor10k-*/receipt.json")):
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            tasks.append({"episode_id": receipt_path.parent.name, "episode_root": str(receipt_path.parent),
                          "house_id": receipt.get("house_id"), "source_index": receipt.get("source_index"),
                          "source_status": receipt.get("status")})
    return tasks


# --------------------------------------------------------------------------
# the residual checks (private plane only)
# --------------------------------------------------------------------------

def read_private_records(private_dir: Path) -> list[dict[str, Any]]:
    paths = sorted(private_dir.glob("*.frame.json"))
    if not paths:
        raise GeometryFailure("private_plane_missing_or_malformed", "no private frame records")
    records = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    for index, record in enumerate(records):
        if record.get("observation_index") != index:
            raise GeometryFailure("private_plane_missing_or_malformed", f"frame {index} index mismatch")
    return records


def read_interventions(provenance_dir: Path) -> tuple[list[dict[str, Any]], list[int] | None]:
    """Executed interventions and the unobservable window; a null episode has neither."""

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


def frame0_containment(episode_root: Path, table: dict[str, Any], truth0: dict[str, dict[str, Any]],
                       *, minimum_depth_m: float, maximum_depth_m: float) -> dict[str, Any]:
    """Share of frame-0 private-mask back-projections inside each object's translated truth box.

    白话：帧 0 是干预前、原点所在的那一帧。把每个可见物体的私有 mask 用公开深度和位姿反投影成
    点，数落在它平移后真值盒（外扩 5 cm）里的比例。比例低说明重载的盒子、原点或平移规则有问题，
    不是方法的问题。只看 ≥196 像素的物体。
    """

    from PIL import Image
    public = episode_root / "public"
    private = episode_root / "private"
    record0 = json.loads((public / "0000.frame.json").read_text(encoding="utf-8"))
    private0 = json.loads((private / "0000.frame.json").read_text(encoding="utf-8"))
    depth = np.load(public / record0["depth_path"]).astype(np.float32)
    labels = np.asarray(Image.open(private / private0["instance_mask_path"]))
    pose = {"position_m": list(record0["relative_pose"]["position_m"]),
            "quaternion_xyzw": list(record0["relative_pose"]["quaternion_xyzw"])}
    per_object: dict[str, Any] = {}
    for object_id, label in sorted(private0["object_id_to_entity_id"].items()):
        entry = truth0.get(object_id)
        if entry is None or not entry.get("present") or entry.get("aabb_min_m") is None:
            continue
        mask = labels == int(label)
        pixels = int(mask.sum())
        if pixels < CONTAINMENT_MINIMUM_PIXELS:
            continue
        points = og.backproject_mask(mask, depth, record0["intrinsics"], pose,
                                     minimum_depth_m=minimum_depth_m, maximum_depth_m=maximum_depth_m)
        fraction = og.containment_fraction(points, entry["aabb_min_m"], entry["aabb_max_m"])
        per_object[object_id] = {"pixels": pixels, "valid_points": int(points.shape[0]), "inside_fraction": fraction}
    fractions = sorted(v["inside_fraction"] for v in per_object.values() if v["inside_fraction"] is not None)
    return {
        "objects_checked": len(per_object),
        "median_inside_fraction": (fractions[len(fractions) // 2] if fractions else None),
        "min_inside_fraction": (fractions[0] if fractions else None),
        "objects_below_half": sorted(oid for oid, v in per_object.items()
                                     if v["inside_fraction"] is not None and v["inside_fraction"] < 0.5),
        "per_object": per_object,
    }


def residual_checks(episode_root: Path, table: dict[str, Any], *, minimum_depth_m: float,
                    maximum_depth_m: float) -> dict[str, Any]:
    records = read_private_records(episode_root / "private")
    executed, window = read_interventions(episode_root / "provenance")
    tracker = og.EpisodeTruthTracker(table, executed_interventions=executed, window=window)
    truth0 = tracker.update(0, records[0])
    drift = og.drift_report(table, records, intervened_ids=tracker.intervened_ids())
    containment = frame0_containment(episode_root, table, truth0,
                                     minimum_depth_m=minimum_depth_m, maximum_depth_m=maximum_depth_m)
    return {"frames": len(records), "executed_interventions": len(executed), "window": window,
            "intervened_objects": sorted(tracker.intervened_ids()), "drift": drift, "frame0_containment": containment}


# --------------------------------------------------------------------------
# one episode
# --------------------------------------------------------------------------

def reload_metadata(source_root: Path, source_rel: str, source_index: int) -> tuple[dict[str, Any], Any]:
    """Load the house, start the simulator, bootstrap the agent, return (metadata, controller)."""

    house = house_loader.load_source_record(str(source_root), {"relative_path": source_rel, "index": source_index})
    upgraded = house_loader.upgrade_house_schema_v1(house, house_loader.load_pinned_asset_id_database())
    from ai2thor.controller import Controller
    from ai2thor.platform import CloudRendering
    controller = Controller(platform=CloudRendering, scene=upgraded, width=WIDTH, height=HEIGHT, fieldOfView=FOV,
                            gridSize=0.25, snapToGrid=True, rotateStepDegrees=90,
                            renderDepthImage=False, renderInstanceSegmentation=False)
    if controller.last_event.metadata.get("lastActionSuccess") is not True:
        controller.stop()
        raise GeometryFailure("house_load_failed", str(controller.last_event.metadata.get("errorMessage")))
    event = house_loader.bootstrap_house_agent(controller, upgraded)
    return event.metadata, controller


def build_episode(task: dict[str, Any]) -> dict[str, Any]:
    started = time.time()
    episode_id = task["episode_id"]
    out_dir = Path(task["out"])
    receipt: dict[str, Any] = {"episode_id": episode_id, "house_id": task["house_id"],
                               "source_index": task["source_index"], "code_commit": task["commit"]}
    controller = None
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        if task["source_status"] != "succeeded":
            raise GeometryFailure("source_episode_not_succeeded", str(task["source_status"]))
        if not isinstance(task["source_index"], int) or not task["house_id"]:
            raise GeometryFailure("metadata_missing_or_malformed", "receipt lacks house_id/source_index")
        metadata, controller = reload_metadata(Path(task["source_root"]), task["source_rel"], task["source_index"])
        objects = metadata.get("objects")
        if not isinstance(objects, list) or not objects or "cameraPosition" not in metadata:
            raise GeometryFailure("metadata_missing_or_malformed", "no objects or camera position")
        try:
            table = og.build_geometry_table(
                episode_id=episode_id, house_id=task["house_id"], source_index=task["source_index"],
                code_commit=task["commit"], metadata_objects=objects,
                camera_position_world=metadata["cameraPosition"], agent_pose=metadata["agent"])
        except og.LeanObjectGeometryError as exc:
            raise GeometryFailure("table_invalid", str(exc))
        if controller is not None:
            controller.stop()
        controller = None
        (out_dir / og.TABLE_FILE_NAME).write_text(json.dumps(table, indent=1), encoding="utf-8")
        try:
            residual = residual_checks(Path(task["episode_root"]), table,
                                       minimum_depth_m=task["minimum_depth_m"], maximum_depth_m=task["maximum_depth_m"])
        except og.LeanObjectGeometryError as exc:
            raise GeometryFailure("private_plane_missing_or_malformed", str(exc))
        receipt.update({
            "status": "succeeded", "objects": len(table["objects"]),
            "objects_without_box": len(table["objects_without_box"]),
            "reload_digest": table["reload_digest"], "episode_origin_world_m": table["episode_origin_world_m"],
            "residual": residual,
        })
    except GeometryFailure as failure:
        receipt.update({"status": "failed", "reason": failure.reason, "detail": failure.detail[:400]})
    except Exception as exc:  # noqa: BLE001
        receipt.update({"status": "failed", "reason": "house_load_failed",
                        "detail": (repr(exc) + " | " + traceback.format_exc()[-800:])})
    finally:
        if controller is not None:
            try:
                controller.stop()
            except Exception:  # noqa: BLE001
                pass
    receipt.update({"wall_seconds": round(time.time() - started, 1), "worker_pid": os.getpid()})
    (out_dir / "receipt.json").write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    return receipt


# --------------------------------------------------------------------------
# the stage
# --------------------------------------------------------------------------

def stage_receipt(results: list[dict[str, Any]], *, planned: int, commit: str, requested_workers: int,
                  actual_workers: int, worker_basis: str, wall_seconds: float) -> dict[str, Any]:
    succeeded = [r for r in results if r["status"] == "succeeded"]
    failed = [r for r in results if r["status"] != "succeeded"]
    drift_max = [r["residual"]["drift"]["max_drift_m"] for r in succeeded if r["residual"]["drift"]["max_drift_m"] is not None]
    contain = [r["residual"]["frame0_containment"]["median_inside_fraction"] for r in succeeded
               if r["residual"]["frame0_containment"]["median_inside_fraction"] is not None]
    over = sorted(r["episode_id"] for r in succeeded if r["residual"]["drift"]["objects_over_tolerance"])
    return {
        "stage": "s1-04-object-geometry", "code_commit": commit,
        "episodes_planned": planned, "episodes_succeeded": len(succeeded), "episodes_failed": len(failed),
        "failure_receipts": [{"episode_id": r["episode_id"], "reason": r.get("reason"), "detail": (r.get("detail") or "")[:200]}
                             for r in failed],
        "objects_total": sum(r["objects"] for r in succeeded),
        "objects_without_box_total": sum(r["objects_without_box"] for r in succeeded),
        "drift_max_over_episodes_m": (max(drift_max) if drift_max else None),
        "episodes_with_drift_over_tolerance": over,
        "frame0_containment_median_over_episodes": (sorted(contain)[len(contain) // 2] if contain else None),
        "frame0_containment_min_over_episodes": (min(contain) if contain else None),
        "requested_workers": requested_workers, "actual_workers": actual_workers, "worker_basis": worker_basis,
        "wall_clock_seconds": round(wall_seconds, 1),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--episode-roots", required=True, help="comma-separated S1-02 output roots")
    parser.add_argument("--source", required=True, help="the frozen ProcTHOR-10K train.jsonl.gz")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--worker-basis", default="", help="the measured evidence the worker count rests on")
    parser.add_argument("--allow-dirty", action="store_true", help="tests only; a stage run needs a clean checkout")
    args = parser.parse_args()

    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    closed = blocking_authorization(contract)
    if closed:
        print(f"[s1-04-geometry] refused: authorization bits still closed: {closed}", file=sys.stderr)
        return 2
    if not args.allow_dirty and _git("status", "--porcelain"):
        print("[s1-04-geometry] refused: the checkout is not clean", file=sys.stderr)
        return 2
    commit = _git("rev-parse", "HEAD")
    geometry = frozen_fragment_geometry()
    source = Path(args.source).resolve()
    roots = [Path(p).resolve() for p in args.episode_roots.split(",") if p]
    out_root = Path(args.output_root).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    tasks = episode_tasks(roots)
    for task in tasks:
        task.update({"out": str(out_root / task["episode_id"]), "source_root": str(source.parent),
                     "source_rel": source.name, "commit": commit,
                     "minimum_depth_m": float(geometry["minimum_depth_m"]),
                     "maximum_depth_m": float(geometry["maximum_depth_m"])})
    requested = max(1, int(args.workers))
    actual = min(requested, len(tasks)) if tasks else 0
    plan = {"stage": "s1-04-object-geometry", "commit": commit, "episodes": [t["episode_id"] for t in tasks],
            "source": str(source), "requested_workers": requested, "actual_workers": actual,
            "worker_basis": args.worker_basis, "started": time.time()}
    (out_root / "plan.json").write_text(json.dumps(plan, indent=1), encoding="utf-8")
    print(f"[s1-04-geometry] {len(tasks)} episodes, {actual} workers, commit {commit[:7]}", flush=True)
    started = time.time()
    results: list[dict[str, Any]] = []
    if actual <= 1:
        for task in tasks:
            results.append(build_episode(task))
            print(f"[s1-04-geometry] {len(results)}/{len(tasks)} {results[-1]['episode_id']} {results[-1]['status']}", flush=True)
    else:
        context = mp.get_context("spawn")
        with context.Pool(processes=actual) as pool:
            for receipt in pool.imap_unordered(build_episode, tasks):
                results.append(receipt)
                print(f"[s1-04-geometry] {len(results)}/{len(tasks)} {receipt['episode_id']} {receipt['status']}", flush=True)
    results.sort(key=lambda r: r["episode_id"])
    receipt = stage_receipt(results, planned=len(tasks), commit=commit, requested_workers=requested,
                            actual_workers=actual, worker_basis=args.worker_basis, wall_seconds=time.time() - started)
    (out_root / "s1_04_geometry_receipt.json").write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in receipt.items() if k != "failure_receipts"}, indent=1))
    return 0 if receipt["episodes_failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
