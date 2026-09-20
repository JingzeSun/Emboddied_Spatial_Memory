"""S1-02a pilot: four workers, one ProcTHOR house each, end to end.

Usage (server, simulator env):
    python ops/vsmt/lean_s1_02a_pilot.py --output-root /root/autodl-tmp/vsmt_outputs/lean-s1-02a-<commit> \
        --source /root/autodl-tmp/vsmt_sources/procthor-10k-0.1.2/train.jsonl.gz --workers 4

What one worker does, in order, and what it writes:
  1. load the house, upgrade its schema (reused from vm04_two_house_worker),
     start CloudRendering with the S0-02 parameters, teleport to the
     house-authored agent pose, read GetReachablePositions;
  2. plan sweep one + the transition (lean_route), execute them, saving the
     three planes every frame; sweep one gives each object's max visible
     pixels (private instance masks), the transition gives, for every
     container, a public-visibility verdict per frame (S0-02 verdict source);
  3. U = containers invisible in every transition frame; enumerate the
     feasible triples (lean_interventions), pre-screen placement, sample,
     execute the interventions at the transition cell;
  4. plan sweep two from the sampled interventions, execute it;
  5. write provenance (route, reachable set, interventions, verdicts) and a
     per-house receipt; a failure of any kind leaves a failure receipt with
     a registered reason and keeps the prefix.

The orchestrator selects the pilot houses with lean_pilot (head of the
frozen split's train block), runs the workers, validates the receipts with
the S1-02a contract checkers and derives the S1-02b worker count.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import multiprocessing as mp
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any

try:  # Unix only; the runner targets the Linux server
    import resource
except ImportError:  # pragma: no cover - Windows import check
    resource = None

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
for item in (ROOT / "src", HERE.parent):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt import lean_interventions as sel  # noqa: E402
from vsmt import lean_pilot, lean_route  # noqa: E402
from vsmt.lean_intervention import (  # noqa: E402
    FAILURE_REASONS, MAXIMUM_ACTIONS, MINIMUM_WINDOW_FRAMES, PUBLIC_FRAME_FIELDS,
    PRIVATE_FRAME_FIELDS, FORBIDDEN_PUBLIC_KEYS,
)
from vsmt.vm04_public_visibility import (  # noqa: E402
    Vm04PublicVisibilityConfig, assess_public_visibility_from_depth,
    seal_public_visibility_subject,
)
import vm04_two_house_worker as house_loader  # noqa: E402

CONTRACT_S0_02 = ROOT / "configs" / "vsmt" / "lean_s0_intervention_data_v3.json"
CONTRACT_S1_02A = ROOT / "configs" / "vsmt" / "lean_s1_02a_pilot_v2.json"
DATASET_TAG = "procthor10k-0.1.2-train"
WIDTH = HEIGHT = 224
FOV = 90.0
VIS_CONFIG = Vm04PublicVisibilityConfig(
    minimum_depth_m=0.05, maximum_depth_m=20.0, occlusion_depth_tolerance_m=0.05,
    sampling_stride_pixels=4, maximum_subject_samples=512, minimum_subject_samples=32,
)


def sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class PilotFailure(Exception):
    def __init__(self, reason: str, detail: str = ""):
        assert reason in FAILURE_REASONS, reason
        super().__init__(f"{reason}: {detail}")
        self.reason, self.detail = reason, detail


# --------------------------------------------------------------------------
# camera model shared by the public plane and the visibility verdicts
# --------------------------------------------------------------------------

def intrinsics() -> dict[str, float]:
    f = (HEIGHT / 2.0) / math.tan(math.radians(FOV / 2.0))
    return {"fx": f, "fy": f, "cx": (WIDTH - 1) / 2.0, "cy": (HEIGHT - 1) / 2.0}


def camera_pose(meta: dict[str, Any]) -> dict[str, Any]:
    """Camera-to-world pose as {position_m, quaternion_xyzw} from AI2-THOR metadata."""

    cam = meta["cameraPosition"]
    yaw = math.radians(float(meta["agent"]["rotation"]["y"]))
    pitch = math.radians(float(meta["agent"]["cameraHorizon"]))  # positive = down
    cy_, sy_ = math.cos(yaw), math.sin(yaw)
    cp_, sp_ = math.cos(-pitch), math.sin(-pitch)
    ry = np.array([[cy_, 0, sy_], [0, 1, 0], [-sy_, 0, cy_]])
    rx = np.array([[1, 0, 0], [0, cp_, -sp_], [0, sp_, cp_]])
    r = ry @ rx
    t = np.trace(r)
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        w, x, y, z = 0.25 * s, (r[2, 1] - r[1, 2]) / s, (r[0, 2] - r[2, 0]) / s, (r[1, 0] - r[0, 1]) / s
    else:
        i = int(np.argmax([r[0, 0], r[1, 1], r[2, 2]]))
        if i == 0:
            s = math.sqrt(1.0 + r[0, 0] - r[1, 1] - r[2, 2]) * 2
            w, x, y, z = (r[2, 1] - r[1, 2]) / s, 0.25 * s, (r[0, 1] + r[1, 0]) / s, (r[0, 2] + r[2, 0]) / s
        elif i == 1:
            s = math.sqrt(1.0 + r[1, 1] - r[0, 0] - r[2, 2]) * 2
            w, x, y, z = (r[0, 2] - r[2, 0]) / s, (r[0, 1] + r[1, 0]) / s, 0.25 * s, (r[1, 2] + r[2, 1]) / s
        else:
            s = math.sqrt(1.0 + r[2, 2] - r[0, 0] - r[1, 1]) * 2
            w, x, y, z = (r[1, 0] - r[0, 1]) / s, (r[0, 2] + r[2, 0]) / s, (r[1, 2] + r[2, 1]) / s, 0.25 * s
    q = np.array([x, y, z, w]); q = q / np.linalg.norm(q)
    return {"position_m": [float(cam["x"]), float(cam["y"]), float(cam["z"])],
            "quaternion_xyzw": [float(v) for v in q]}


def relative_pose(pose: dict[str, Any], origin: dict[str, Any]) -> dict[str, Any]:
    """Episode-relative pose: translation relative to observation 0's camera."""

    p = np.array(pose["position_m"]) - np.array(origin["position_m"])
    return {"position_m": [float(v) for v in p], "quaternion_xyzw": pose["quaternion_xyzw"],
            "origin": "observation_0_camera"}


# --------------------------------------------------------------------------
# per-frame capture to the three planes
# --------------------------------------------------------------------------

class Episode:
    def __init__(self, house_id: str, out: Path, house: dict[str, Any]):
        self.house_id, self.out = house_id, out
        self.public, self.private, self.prov = out / "public", out / "private", out / "provenance"
        for d in (self.public, self.private, self.prov):
            d.mkdir(parents=True, exist_ok=True)
        self.house = house
        self.index = -1
        self.origin: dict[str, Any] | None = None
        self.frames: list[dict[str, Any]] = []          # per-frame private geometry we keep in memory
        self.visible_pixels: dict[str, int] = {}
        self.bytes_written = 0
        self.actions_done: list[dict[str, Any]] = []

    def _write(self, path: Path, data: bytes) -> str:
        path.write_bytes(data)
        self.bytes_written += len(data)
        return sha_bytes(data)

    def capture(self, event: Any, action: str | None) -> dict[str, Any]:
        self.index += 1
        idx = self.index
        meta = event.metadata
        rgb = np.asarray(event.frame, dtype=np.uint8)
        depth = np.asarray(event.depth_frame, dtype=np.float32)
        masks = event.instance_masks or {}
        pose = camera_pose(meta)
        if self.origin is None:
            self.origin = pose
        # public
        rgb_path = self.public / f"{idx:04d}.rgb.png"
        depth_path = self.public / f"{idx:04d}.depth.npy"
        Image.fromarray(rgb).save(rgb_path, format="PNG")
        self.bytes_written += rgb_path.stat().st_size
        np.save(depth_path, depth)
        self.bytes_written += depth_path.stat().st_size
        public_record = {
            "observation_index": idx,
            "rgb_path": rgb_path.name,
            "depth_path": depth_path.name,
            "intrinsics": intrinsics(),
            "relative_pose": relative_pose(pose, self.origin),
            "action_summary": {"action": action, "success": bool(meta.get("lastActionSuccess"))},
        }
        public_record["frame_digest"] = sha({"rgb": sha_bytes(rgb.tobytes()), "depth": sha_bytes(depth.tobytes()),
                                             **{k: public_record[k] for k in ("observation_index", "relative_pose", "action_summary")}})
        assert tuple(public_record) == PUBLIC_FRAME_FIELDS, tuple(public_record)
        _reject_forbidden(public_record)
        self._write(self.public / f"{idx:04d}.frame.json", (json.dumps(public_record) + "\n").encode())
        # private
        label = np.zeros((HEIGHT, WIDTH), dtype=np.uint16)
        ids = sorted(masks)
        for n, oid in enumerate(ids, start=1):
            m = np.asarray(masks[oid], dtype=bool)
            label[m] = n
            self.visible_pixels[oid] = max(self.visible_pixels.get(oid, 0), int(m.sum()))
        mask_path = self.private / f"{idx:04d}.instance.png"
        Image.fromarray(label).save(mask_path, format="PNG")
        self.bytes_written += mask_path.stat().st_size
        objects = {o["objectId"]: o for o in meta["objects"]}
        private_record = {
            "observation_index": idx,
            "instance_mask_path": mask_path.name,
            "object_id_to_entity_id": {oid: n for n, oid in enumerate(ids, start=1)},
            "object_poses": {oid: objects[oid]["position"] for oid in ids if oid in objects},
            "object_visibility": {oid: int(np.asarray(masks[oid]).sum()) for oid in ids},
            "frame_digest": public_record["frame_digest"],
        }
        assert tuple(private_record) == PRIVATE_FRAME_FIELDS
        self._write(self.private / f"{idx:04d}.frame.json", (json.dumps(private_record) + "\n").encode())
        self.frames.append({"index": idx, "pose": pose, "depth": depth, "masks": masks,
                            "camera_position": dict(meta["cameraPosition"]), "frame_digest": public_record["frame_digest"]})
        self.actions_done.append({"index": idx, "action": action, "success": bool(meta.get("lastActionSuccess")),
                                  "error": (meta.get("errorMessage") or "")[:200]})
        return self.frames[-1]


def _reject_forbidden(record: Any) -> None:
    if isinstance(record, dict):
        for k, v in record.items():
            if k in FORBIDDEN_PUBLIC_KEYS:
                raise PilotFailure("frame_write_failed", f"forbidden public key {k}")
            _reject_forbidden(v)
    elif isinstance(record, list):
        for v in record:
            _reject_forbidden(v)


# --------------------------------------------------------------------------
# worker
# --------------------------------------------------------------------------

def _execute(controller: Any, ep: Episode, actions: list[str]) -> None:
    for a in actions:
        if len(ep.actions_done) > MAXIMUM_ACTIONS:
            raise PilotFailure("route_not_placeable", "action cap hit; not truncating")
        event = controller.step(action=a)
        ep.capture(event, a)
        if event.metadata.get("lastActionSuccess") is not True:
            raise PilotFailure("action_rejected", f"{a} @ {ep.index}: {event.metadata.get('errorMessage')}")


def _containers(meta: dict[str, Any]) -> dict[str, dict[str, float]]:
    out = {}
    for o in meta["objects"]:
        if o.get("receptacle") and not o.get("pickupable"):
            bb = o.get("axisAlignedBoundingBox") or {}
            c = bb.get("center") or o["position"]
            out[o["objectId"]] = {"x": float(c["x"]), "y": float(c["y"]), "z": float(c["z"])}
    return out


def _object_table(meta: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for o in meta["objects"]:
        parents = o.get("parentReceptacles") or []
        rows.append({"object_id": o["objectId"], "asset_id": o.get("assetId"),
                     "pickupable": bool(o.get("pickupable")), "parent_receptacle": parents[0] if parents else None,
                     "is_agent": False, "is_structure": not bool(o.get("pickupable")) and not bool(o.get("receptacle"))})
    return rows


def _seal_container_subjects(ep: Episode, containers: dict[str, Any], sweep_one: tuple[int, int],
                             viewpoint_frames: dict[str, int]) -> dict[str, dict[str, Any]]:
    """Seal one visibility subject per container from its sweep-one viewpoint frame (private mask, provenance only)."""

    subjects = {}
    calib = intrinsics()
    for cid, fidx in viewpoint_frames.items():
        fr = ep.frames[fidx]
        mask = np.asarray(fr["masks"].get(cid, np.zeros((HEIGHT, WIDTH), bool)), dtype=bool)
        if int(mask.sum()) < VIS_CONFIG.minimum_subject_samples * VIS_CONFIG.sampling_stride_pixels ** 2:
            continue
        try:
            subjects[cid] = seal_public_visibility_subject(
                subject_public_ref=f"container:{sha(cid)[:16]}", source_public_packet_sha256=fr["frame_digest"],
                source_observation_index=fidx, public_mask=mask, public_depth_m=fr["depth"],
                camera_calibration=calib, camera_pose=fr["pose"], config=VIS_CONFIG)
        except ValueError:
            continue
    return subjects


def _invisible_set(ep: Episode, subjects: dict[str, dict[str, Any]], transition: tuple[int, int]) -> tuple[set[str], list[dict[str, Any]]]:
    """Containers whose subject projects zero unoccluded samples in EVERY transition frame."""

    calib = intrinsics()
    invisible, verdicts = set(subjects), []
    for fidx in range(transition[0] + 1, transition[1] + 1):
        fr = ep.frames[fidx]
        for cid, subject in subjects.items():
            r = assess_public_visibility_from_depth(
                subject=subject, current_observation_index=fidx, public_depth_m=fr["depth"],
                camera_calibration=calib, camera_pose=fr["pose"], current_public_support_sha256=None,
                terminal_reobservation_phase=False, config=VIS_CONFIG)
            unoccluded = r["assessment"]["unoccluded_public_sample_count"]
            verdicts.append({"observation_index": fidx, "container": cid, "unoccluded": int(unoccluded),
                             "depth_frame_digest": fr["frame_digest"], "receipt_sha256": r["receipt"]["receipt_sha256"]})
            if unoccluded > 0:
                invisible.discard(cid)
    return invisible, verdicts


def _prescreen(controller: Any, containers: dict[str, Any]) -> tuple[dict[str, bool], dict[str, Any]]:
    ok, points = {}, {}
    for cid in sorted(containers):
        ev = controller.step(action="GetSpawnCoordinatesAboveReceptacle", objectId=cid, anywhere=True)
        pts = ev.metadata.get("actionReturn") or []
        ok[cid] = bool(ev.metadata.get("lastActionSuccess")) and len(pts) > 0
        if ok[cid]:
            points[cid] = pts[0]
    return ok, points


def _apply_interventions(controller: Any, rows: list[dict[str, Any]], spawn_points: dict[str, Any]) -> list[dict[str, Any]]:
    log = []
    for row in rows:
        kind = row["kind"]
        if kind == "remove":
            ev = controller.step(action="RemoveFromScene", objectId=row["object_id"])
        elif kind == "move":
            ev = controller.step(action="PlaceObjectAtPoint", objectId=row["object_id"], position=spawn_points[row["destination"]])
        else:
            ev = controller.step(action="SpawnAsset", assetId=row["asset_id"], generatedId=row["generated_id"],
                                 position=spawn_points[row["destination"]], rotation={"x": 0, "y": 0, "z": 0})
        ok = ev.metadata.get("lastActionSuccess") is True
        log.append({**row, "executed": ok, "error": (ev.metadata.get("errorMessage") or "")[:300]})
        if not ok:
            raise PilotFailure("intervention_execution_failed", f"{kind} {row['object_id']}: {ev.metadata.get('errorMessage')}")
    return log


def run_house(task: dict[str, Any]) -> dict[str, Any]:
    house_id, index, out = task["house_id"], task["index"], Path(task["out"])
    t0 = time.time()
    receipt: dict[str, Any] = {"house_id": house_id, "source_index": index, "code_commit": task["commit"]}
    controller = None
    try:
        house = house_loader.load_source_record(task["source_root"], {"relative_path": task["source_rel"], "index": index})
        upgraded = house_loader.upgrade_house_schema_v1(house, house_loader.load_pinned_asset_id_database())
        from ai2thor.controller import Controller
        from ai2thor.platform import CloudRendering
        controller = Controller(platform=CloudRendering, scene=upgraded, width=WIDTH, height=HEIGHT, fieldOfView=FOV,
                                gridSize=0.25, snapToGrid=True, rotateStepDegrees=90, renderDepthImage=True,
                                renderInstanceSegmentation=True)
        if controller.last_event.metadata.get("lastActionSuccess") is not True:
            raise PilotFailure("house_load_failed", str(controller.last_event.metadata.get("errorMessage")))
        ev = house_loader.bootstrap_house_agent(controller, upgraded)
        ep = Episode(house_id, out, upgraded)
        ep.capture(ev, None)
        reach = controller.step(action="GetReachablePositions").metadata.get("actionReturn") or []
        if not reach:
            raise PilotFailure("house_load_failed", "no reachable positions")
        meta = ev.metadata
        start = {"position": meta["agent"]["position"], "rotation": meta["agent"]["rotation"], "horizon": meta["agent"]["cameraHorizon"]}
        cam_h = float(meta["cameraPosition"]["y"])
        containers = _containers(meta)
        # viewpoints reachable? drop containers without one (recorded)
        cells = lean_route.reachable_cells(reach)
        usable, dropped = {}, []
        for cid, c in sorted(containers.items()):
            try:
                lean_route.select_viewpoint(c, cells, camera_height_m=cam_h); usable[cid] = c
            except lean_route.LeanRouteError:
                dropped.append(cid)
        if not usable:
            raise PilotFailure("route_not_placeable", "no container has an admissible viewpoint")
        # stage 1: sweep one + transition to the farthest cell from the last viewpoint
        plan1 = lean_route.plan_route(reachable=reach, start_pose=start, camera_height_m=cam_h, containers=usable,
                                      revisit_sequence=[], transition_cell=None)
        last_cell = tuple(plan1["viewpoints"][plan1["sweep_one_order"][-1]]["cell"])
        far = max(sorted(cells), key=lambda c: (len(lean_route.bfs_path(cells, last_cell, c)), c))
        plan1 = lean_route.plan_route(reachable=reach, start_pose=start, camera_height_m=cam_h, containers=usable,
                                      revisit_sequence=[], transition_cell=far)
        (ep.prov / "route_stage1.json").write_text(json.dumps(plan1, indent=1))
        s1 = plan1["segments"]["sweep_one"]; tr = plan1["segments"]["transition"]
        _execute(controller, ep, plan1["actions"])
        window_frames = tr[1] - tr[0]
        # which frame is each container's viewpoint frame: the last frame of its visit in sweep one
        # viewpoint frame = last sweep-one frame in which the agent stands on that viewpoint cell
        vp_frames: dict[str, int] = {}
        for cid in plan1["sweep_one_order"]:
            vp = plan1["viewpoints"][cid]
            for fr in ep.frames[s1[0]:s1[1] + 1]:
                cp = fr["camera_position"]
                if (lean_route.snap(cp["x"]), lean_route.snap(cp["z"])) == tuple(vp["cell"]):
                    vp_frames[cid] = fr["index"]
        null_window = sel.is_null_window(task["split_seed"], house_id)
        subjects = _seal_container_subjects(ep, usable, s1, vp_frames)
        invisible, verdicts = _invisible_set(ep, subjects, tr)
        (ep.prov / "window_verdicts.json").write_text(json.dumps({"window": tr, "frames": window_frames, "invisible": sorted(invisible), "verdicts": verdicts}, indent=1))
        interventions: list[dict[str, Any]] = []
        feasible: list[dict[str, Any]] = []
        if not null_window:
            if window_frames < MINIMUM_WINDOW_FRAMES:
                raise PilotFailure("intervention_window_unavailable", f"window {window_frames} < {MINIMUM_WINDOW_FRAMES}")
            objects = _object_table(controller.last_event.metadata)
            eligible = sel.eligible_objects(objects, ep.visible_pixels)
            ok, spawn_points = _prescreen(controller, {c: usable[c] for c in usable})
            feasible = sel.feasible_triples(eligible, list(usable), invisible, ok)
            if not feasible:
                raise PilotFailure("intervention_window_unavailable", f"feasible set empty; U={len(invisible)} eligible={len(eligible)}")
            interventions = sel.sample_interventions(feasible, split_seed=task["split_seed"], house_id=house_id)
            log = _apply_interventions(controller, interventions, spawn_points)
        else:
            log = []
        # stage 2: sweep two
        revisit = sel.revisit_sequence(interventions, split_seed=task["split_seed"], house_id=house_id)
        here = controller.last_event.metadata["agent"]
        start2 = {"position": here["position"], "rotation": here["rotation"], "horizon": here["cameraHorizon"]}
        # sweep two: from the real pose, visit exactly the revisit sequence (its "sweep one" IS the revisit)
        plan2b = lean_route.plan_route(reachable=reach, start_pose=start2, camera_height_m=cam_h,
                                       containers={c: usable[c] for c in revisit} if revisit else {},
                                       revisit_sequence=[], transition_cell=None,
                                       max_actions=max(1, MAXIMUM_ACTIONS - len(plan1["actions"])))
        actions2 = plan2b["actions"]
        (ep.prov / "route_stage2.json").write_text(json.dumps({"revisit_sequence": revisit, "plan": plan2b}, indent=1))
        _execute(controller, ep, actions2)
        (ep.prov / "reachable.json").write_text(json.dumps(reach))
        (ep.prov / "interventions.json").write_text(json.dumps({"null_window": null_window, "feasible_set_size": len(feasible),
                                                                "invisible_container_set_size": len(invisible), "executed": log,
                                                                "dropped_containers_no_viewpoint": dropped}, indent=1))
        receipt.update({"status": "succeeded", "observations": ep.index + 1, "actions": len(ep.actions_done) - 1,
                        "null_window": null_window, "executed_interventions": len(log), "feasible_set_size": len(feasible),
                        "invisible_container_set_size": len(invisible), "window_frames": window_frames,
                        "containers_usable": len(usable), "containers_dropped": len(dropped)})
    except PilotFailure as f:
        receipt.update({"status": "failed", "reason": f.reason, "detail": f.detail})
    except Exception as e:  # noqa: BLE001
        reason = "house_load_failed" if controller is None else "frame_write_failed"
        receipt.update({"status": "failed", "reason": reason, "detail": (repr(e) + " | " + traceback.format_exc()[-1500:])})
    finally:
        if controller is not None:
            try:
                controller.stop()
            except Exception:  # noqa: BLE001
                pass
    ru = resource.getrusage(resource.RUSAGE_SELF) if resource else None
    receipt["occupancy"] = {"peak_rss_gb": (ru.ru_maxrss / 1e6) if ru else 0.0,
                            "cpu_seconds": (ru.ru_utime + ru.ru_stime) if ru else 0.0,
                            "wall_seconds": time.time() - t0, "bytes_written": _dir_bytes(out)}
    (out / "receipt.json").write_text(json.dumps(receipt, indent=1))
    return receipt


def _dir_bytes(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0


# --------------------------------------------------------------------------
# orchestrator
# --------------------------------------------------------------------------

def _vram_peak_sampler(stop: mp.Event, out: mp.Queue) -> None:
    peak = 0.0
    while not stop.is_set():
        try:
            txt = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                                 capture_output=True, text=True, timeout=10).stdout.strip()
            peak = max(peak, float(txt.split("\n")[0]))
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)
    out.put(peak)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--workers", type=int, default=lean_pilot.PILOT_WORKERS)
    args = ap.parse_args()
    contract = json.loads(CONTRACT_S1_02A.read_text(encoding="utf-8"))
    lean_pilot.validate_pilot_contract(contract)
    if not all(contract["authorization"].values()):
        print("authorization bits closed; refusing"); return 2
    freeze = contract["split_freeze"]
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    source = Path(args.source)
    pool = [f"{DATASET_TAG}-{i:05d}" for i, _ in house_loader.records_from_json(source)]
    selected = lean_pilot.select_pilot_houses(pool, freeze)
    lean_pilot.validate_pilot_plan({"workers": args.workers, "houses_per_worker": 1, "house_ids": selected}, pool, freeze)
    out_root = Path(args.output_root); out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "plan.json").write_text(json.dumps({"selected": selected, "split": freeze, "commit": commit, "pool_size": len(pool)}, indent=1))
    tasks = [{"house_id": h, "index": int(h.rsplit("-", 1)[1]), "out": str(out_root / h), "source_root": str(source.parent),
              "source_rel": source.name, "split_seed": freeze["seed"], "commit": commit} for h in selected]
    base_vram = float(subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.strip().split("\n")[0])
    stop, q = mp.Event(), mp.Queue()
    sampler = mp.Process(target=_vram_peak_sampler, args=(stop, q)); sampler.start()
    t0 = time.time()
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=args.workers) as pool_:
        results = pool_.map(run_house, tasks)
    wall = time.time() - t0
    stop.set(); sampler.join(timeout=30)
    vram_peak = q.get() if not q.empty() else base_vram
    results = sorted(results, key=lambda r: r["house_id"])  # deterministic merge order
    failed = [r for r in results if r["status"] != "succeeded"]
    pilot_receipt = {
        "split_seed": freeze["seed"], "split_sizes": {"train": freeze["train_houses"], "validation": freeze["validation_houses"], "test": freeze["test_houses"]},
        "selected_house_ids": selected, "planned": len(selected), "succeeded": len(results) - len(failed), "failed": len(failed),
        "failure_receipts": [{"house_id": r["house_id"], "reason": r["reason"], "detail": r.get("detail", "")[:400]} for r in failed],
        "wall_clock_seconds": round(wall, 1), "exit_codes": [0 if r["status"] == "succeeded" else 1 for r in results], "code_commit": commit,
    }
    lean_pilot.validate_pilot_receipt(pilot_receipt)
    occ = [r["occupancy"] for r in results]
    occupancy_receipt = {
        "concurrency_verified_at": args.workers,
        "cpu_cores_per_worker": max(o["cpu_seconds"] / max(o["wall_seconds"], 1e-6) for o in occ),
        "ram_gb_per_worker": max(o["peak_rss_gb"] for o in occ),
        "vram_gb_per_worker": max(0.0, (vram_peak - base_vram) / 1024.0) / args.workers,
        "disk_gb_per_worker": max(o["bytes_written"] for o in occ) / 1e9,
        "simulator_concurrency_limit": args.workers,
        "statistic": lean_pilot.REQUIRED_STATISTIC, "workload": lean_pilot.REQUIRED_WORKLOAD,
        "failures": [r["house_id"] for r in failed],
    }
    lean_pilot.validate_occupancy_receipt(occupancy_receipt)
    (out_root / "pilot_receipt.json").write_text(json.dumps(pilot_receipt, indent=1))
    (out_root / "occupancy_receipt.json").write_text(json.dumps({**occupancy_receipt, "vram_peak_total_mib": vram_peak, "vram_base_mib": base_vram}, indent=1))
    print(json.dumps({"pilot": pilot_receipt, "occupancy": occupancy_receipt, "per_house": results}, indent=1, default=str))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
