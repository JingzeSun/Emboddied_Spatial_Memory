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
    DRY_RUN_MAX_POINTS, FAILURE_REASONS, MAX_REPLANS, MAXIMUM_ACTIONS, MINIMUM_WINDOW_FRAMES, MIN_VISIBLE_PIXELS,
    PUBLIC_FRAME_FIELDS,
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
        (out / "started.json").write_text(json.dumps({"worker_pid": os.getpid(), "started": time.time()}))
        self.beat()
        self.house = house
        self.index = -1
        self.origin: dict[str, Any] | None = None
        self.frames: list[dict[str, Any]] = []          # per-frame private geometry we keep in memory
        self.visible_pixels: dict[str, int] = {}
        self.bytes_written = 0
        self.actions_done: list[dict[str, Any]] = []

    def beat(self) -> None:
        """Progress heartbeat for the orchestrator's stall detector (not a compute budget)."""

        try:
            (self.out / "heartbeat").write_text(str(time.time()))
        except OSError:
            pass

    def _write(self, path: Path, data: bytes) -> str:
        path.write_bytes(data)
        self.bytes_written += len(data)
        return sha_bytes(data)

    def capture(self, event: Any, action: str | None) -> dict[str, Any]:
        self.beat()
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

def _agent_cell_yaw(controller: Any) -> tuple[tuple[int, int], int]:
    a = controller.last_event.metadata["agent"]
    return (lean_route.snap(a["position"]["x"]), lean_route.snap(a["position"]["z"])), int(round(a["rotation"]["y"])) % 360


def _execute(controller: Any, ep: Episode, actions: list[str], *, blocked: set, replans: list[dict[str, Any]],
             replan: Any = None) -> None:
    """Execute actions; on a rejected MoveAhead, block that edge and let the caller replan.

    ``replan(blocked)`` must return the remaining action list from the real pose.
    A rejection without a replanner, or more than MAX_REPLANS, is a failure.
    """

    queue = list(actions)
    while queue:
        a = queue.pop(0)
        if len(ep.actions_done) > MAXIMUM_ACTIONS:
            raise PilotFailure("route_not_placeable", "action cap hit; not truncating")
        event = controller.step(action=a)
        ep.capture(event, a)
        if event.metadata.get("lastActionSuccess") is True:
            continue
        msg = str(event.metadata.get("errorMessage"))
        if a != "MoveAhead" or replan is None:
            raise PilotFailure("action_rejected", f"{a} @ {ep.index}: {msg}")
        here, yaw = _agent_cell_yaw(controller)
        dx, dz = lean_route._HEADING[yaw]
        blocked_edge = lean_route.edge(here, (here[0] + dx, here[1] + dz))
        if blocked_edge in blocked or len(replans) >= MAX_REPLANS:
            raise PilotFailure("route_not_placeable", f"edge blocked twice or too many replans @ {ep.index}: {msg}")
        blocked.add(blocked_edge)
        replans.append({"observation_index": ep.index, "cell": list(here), "yaw": yaw, "message": msg[:160]})
        queue = replan(blocked)


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


MAX_PLACEMENT_TRIES = 64  # hard cap on --placement-tries; the contract value is DRY_RUN_MAX_POINTS


def _prescreen(controller: Any, containers: dict[str, Any], tries: int = 1,
               anywhere: bool = True) -> tuple[dict[str, bool], dict[str, Any]]:
    """Destination prescreen.  anywhere=False keeps only top-surface spawn points (ruling 31, proposed):
    a closed drawer or an enclosed shelf is a legal spawn box but nothing placed there is observable."""

    ok, points = {}, {}
    for cid in sorted(containers):
        ev = controller.step(action="GetSpawnCoordinatesAboveReceptacle", objectId=cid, anywhere=anywhere)
        pts = ev.metadata.get("actionReturn") or []
        ok[cid] = bool(ev.metadata.get("lastActionSuccess")) and len(pts) > 0
        if ok[cid]:
            points[cid] = _spread(pts, max(1, min(tries, MAX_PLACEMENT_TRIES)))
    return ok, points


def _spread(pts: list[Any], n: int) -> list[Any]:
    """The first point, then points evenly spaced over the simulator's list.

    The list returned by GetSpawnCoordinatesAboveReceptacle is ordered by trigger box and
    position, so its first eight entries sit in one corner of one box (often a closed drawer);
    taking evenly spaced indices covers the other boxes and the top surface.  Deterministic.
    """

    if n <= 1 or len(pts) <= n:
        return list(pts[:n])
    idx = sorted({round(k * (len(pts) - 1) / (n - 1)) for k in range(n)})
    return [pts[i] for i in idx]


def _place(controller: Any, action: str, candidates: list[Any], **kw: Any) -> tuple[Any, int]:
    """Try the candidate points in order; return the first success and how many were tried."""

    ev = None
    for n, pt in enumerate(candidates, start=1):
        ev = controller.step(action=action, position=pt, **kw)
        if ev.metadata.get("lastActionSuccess") is True:
            return ev, n
    return ev, len(candidates)


def _place_verified(controller: Any, action: str, candidates: list[Any], *, object_id: str,
                    viewpoint: dict[str, Any], min_px: int, **kw: Any) -> tuple[Any, int, int]:
    """Like _place, but a point only counts if the object is then visible (>= min_px) from the
    container's sweep-two viewpoint, checked by an off-route private render (ruling 31, proposed).

    白话：放下之后先"偷看"一眼——把 agent 瞬移到该容器的重访视点渲染一帧，看私有实例
    分割里这个物体有没有 ≥196 像素，再瞬移回原位。偷看的帧不进 public，也不计入观察序
    列；它只保证被添加/移动的物体在扫掠二确实看得见，否则换下一个点。
    """

    a = controller.last_event.metadata["agent"]
    home = {"position": dict(a["position"]), "rotation": dict(a["rotation"]), "horizon": a["cameraHorizon"],
            "standing": bool(a.get("isStanding", True))}
    vp_pos = {"x": viewpoint["cell"][0] * lean_route.GRID_M, "y": a["position"]["y"], "z": viewpoint["cell"][1] * lean_route.GRID_M}
    ev, best = None, 0
    for n, pt in enumerate(candidates, start=1):
        ev = controller.step(action=action, position=pt, **kw)
        if ev.metadata.get("lastActionSuccess") is not True:
            continue
        peek = controller.step(action="Teleport", position=vp_pos, rotation={"x": 0, "y": viewpoint["yaw"], "z": 0},
                               horizon=viewpoint["pitch"], standing=True, forceAction=True)
        px = int(np.asarray((peek.instance_masks or {}).get(object_id, np.zeros((1,), dtype=bool))).sum())
        back = controller.step(action="Teleport", position=home["position"], rotation=home["rotation"],
                               horizon=home["horizon"], standing=home["standing"], forceAction=True)
        if back.metadata.get("lastActionSuccess") is not True:
            raise PilotFailure("intervention_execution_failed", f"could not teleport back after the visibility peek: {back.metadata.get('errorMessage')}")
        best = max(best, px)
        if px >= min_px:
            return ev, n, px
    if ev is not None and ev.metadata.get("lastActionSuccess") is True:
        ev.metadata["lastActionSuccess"] = False
        ev.metadata["errorMessage"] = f"placed but not visible from the viewpoint at any of {len(candidates)} points (best {best} px)"
    return ev, len(candidates), best


def _peek_pixels(controller: Any, viewpoint: dict[str, Any], object_id: str) -> int:
    """Off-route private render from a container's viewpoint; the agent is put back exactly."""

    a = controller.last_event.metadata["agent"]
    home = {"position": dict(a["position"]), "rotation": dict(a["rotation"]), "horizon": a["cameraHorizon"],
            "standing": bool(a.get("isStanding", True))}
    vp_pos = {"x": viewpoint["cell"][0] * lean_route.GRID_M, "y": a["position"]["y"], "z": viewpoint["cell"][1] * lean_route.GRID_M}
    peek = controller.step(action="Teleport", position=vp_pos, rotation={"x": 0, "y": viewpoint["yaw"], "z": 0},
                           horizon=viewpoint["pitch"], standing=True, forceAction=True)
    px = int(np.asarray((peek.instance_masks or {}).get(object_id, np.zeros((1,), dtype=bool))).sum())
    back = controller.step(action="Teleport", position=home["position"], rotation=home["rotation"],
                           horizon=home["horizon"], standing=home["standing"], forceAction=True)
    if back.metadata.get("lastActionSuccess") is not True:
        raise PilotFailure("intervention_execution_failed", f"could not teleport back after a peek: {back.metadata.get('errorMessage')}")
    return px


def _dry_run_pairs(controller: Any, candidates: list[dict[str, Any]], u_containers: set[str], spawn_points: dict[str, Any],
                   viewpoints: dict[str, Any], min_px: int, beat: Any = None) -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]]]:
    """Try every (object, U destination) placement for real, peek, and put the object back.

    白话（裁决 31，proposed）：可行集里的 move／add 不再靠"容器有生成点"猜，而是在窗口
    内真的把物体放过去一次、从该容器的重访视点偷看一眼（私有渲染，≥196 像素才算），再
    用 TeleportObject 把物体放回原位。只有真放得下且看得见的 (物体, 目的容器) 对才进 F，
    并记住那个点。窗口内容器本就不可见、干预之间不采帧，所以试放不会进入 public。
    """

    meta = controller.last_event.metadata
    objs = {o["objectId"]: o for o in meta["objects"]}
    ok: dict[tuple[str, str], dict[str, Any]] = {}
    table: list[dict[str, Any]] = []
    for row in candidates:
        if beat is not None:
            beat()
        oid = row["object_id"]; o = objs.get(oid)
        if o is None:
            continue
        orig_pos, orig_rot = dict(o["position"]), dict(o["rotation"])
        for dst in sorted(u_containers):
            if dst == row.get("parent_receptacle") or dst not in spawn_points or dst not in viewpoints:
                continue
            found, best, tried, placed_any = None, 0, 0, False
            for n, pt in enumerate(spawn_points[dst], start=1):
                tried = n
                ev = controller.step(action="PlaceObjectAtPoint", objectId=oid, position=pt)
                if ev.metadata.get("lastActionSuccess") is not True:
                    continue
                placed_any = True
                px = _peek_pixels(controller, viewpoints[dst], oid)
                best = max(best, px)
                if px >= min_px:
                    found = pt; break
            revert_error = ""
            if placed_any:
                back = controller.step(action="TeleportObject", objectId=oid, position=orig_pos, rotation=orig_rot, forceAction=True)
                if back.metadata.get("lastActionSuccess") is not True:
                    revert_error = (back.metadata.get("errorMessage") or "")[:200]
                    back = controller.step(action="TeleportObject", objectId=oid, position=orig_pos, rotation=orig_rot,
                                           forceAction=True, forceKinematic=True)
                    controller.step(action="Pass")
                if back.metadata.get("lastActionSuccess") is not True:
                    # never leave an unrecorded state change behind
                    raise PilotFailure("intervention_execution_failed",
                                       f"dry-run revert failed for {oid}: {revert_error} / {back.metadata.get('errorMessage')}")
                revert_ok = True
            else:
                revert_ok = None  # nothing was moved
            now = next((x["position"] for x in controller.last_event.metadata["objects"] if x["objectId"] == oid), None)
            drift = (math.dist([now["x"], now["y"], now["z"]], [orig_pos["x"], orig_pos["y"], orig_pos["z"]]) if now else None)
            table.append({"object_id": oid, "destination": dst, "tries": tried, "placed_any": placed_any, "best_pixels": best,
                          "feasible": found is not None, "revert_ok": revert_ok, "revert_first_error": revert_error,
                          "revert_drift_m": None if drift is None else round(drift, 4)})
            if found is not None:
                ok[(oid, dst)] = {"point": found, "pixels": best, "tries": tried}
    return ok, table


def _apply_interventions(controller: Any, rows: list[dict[str, Any]], spawn_points: dict[str, Any], *,
                         viewpoints: dict[str, Any] | None = None, verify: bool = False) -> list[dict[str, Any]]:
    log = []
    for row in rows:
        kind = row["kind"]
        tries, seen_px = 1, None
        vp = (viewpoints or {}).get(row.get("destination") or "")
        if kind == "remove":
            # RemoveFromScene hangs Unity in Procedural scenes (NullReferenceException while generating
            # metadata; reproduced on a fresh controller, LOG-236).  DisableObject deactivates the
            # GameObject: 0 px in instance segmentation, no collider, still listed in simulator
            # metadata with visible=false.  Private frame records are built from instance masks,
            # so a disabled object never appears in them.
            ev = controller.step(action="DisableObject", objectId=row["object_id"])
        elif (kind == "move" or row.get("add_source") == "unseen_existing") and row.get("point") is not None:
            # dry-run prescreened pair: the verified point first; if the scene shifted since the dry run
            # (objects nudged, an egg cracked), the other spread points with the same peek check
            ev = controller.step(action="PlaceObjectAtPoint", objectId=row["object_id"], position=row["point"])
            point_source = "dry_run"
            if ev.metadata.get("lastActionSuccess") is True and vp is not None:
                seen_px = _peek_pixels(controller, vp, row["object_id"])
            if (ev.metadata.get("lastActionSuccess") is not True or (seen_px is not None and seen_px < MIN_VISIBLE_PIXELS)) and vp is not None:
                others = [pt for pt in spawn_points.get(row["destination"], []) if pt != row["point"]]
                ev, tries, seen_px = _place_verified(controller, "PlaceObjectAtPoint", others, object_id=row["object_id"],
                                                     viewpoint=vp, min_px=MIN_VISIBLE_PIXELS, objectId=row["object_id"])
                point_source = f"fallback_after_stale_dry_run_point"
            row = {**row, "point_source": point_source}
        elif kind == "move" or row.get("add_source") == "unseen_existing":
            if verify and vp is not None:
                ev, tries, seen_px = _place_verified(controller, "PlaceObjectAtPoint", spawn_points[row["destination"]],
                                                     object_id=row["object_id"], viewpoint=vp, min_px=MIN_VISIBLE_PIXELS,
                                                     objectId=row["object_id"])
            else:
                ev, tries = _place(controller, "PlaceObjectAtPoint", spawn_points[row["destination"]], objectId=row["object_id"])
        else:
            ev, tries = _place(controller, "SpawnAsset", spawn_points[row["destination"]], assetId=row["asset_id"],
                               generatedId=row["generated_id"], rotation={"x": 0, "y": 0, "z": 0})
        ok = ev.metadata.get("lastActionSuccess") is True
        executor = {"remove": "DisableObject", "move": "PlaceObjectAtPoint", "add": "SpawnAsset"}[kind]
        if row.get("add_source") == "unseen_existing":
            executor = "PlaceObjectAtPoint(unseen_existing)"
        log.append({**row, "executed": ok, "placement_tries": tries, "executor": executor, "verified_pixels": seen_px,
                    "error": (ev.metadata.get("errorMessage") or "")[:300]})
        if not ok:
            raise PilotFailure("intervention_execution_failed", f"{kind} {row['object_id']}: {ev.metadata.get('errorMessage')}")
    return log


def run_house(task: dict[str, Any]) -> dict[str, Any]:
    house_id, index, out = task["house_id"], task["index"], Path(task["out"])
    t0 = time.time()
    receipt: dict[str, Any] = {"house_id": house_id, "source_index": index, "code_commit": task["commit"]}
    # defaults are the contract rules after rulings 25-32; the old values remain selectable only to replay s1-02b/159654f
    replan_on = bool(task.get("replan_blocked_edges", True))
    placement_tries = int(task.get("placement_tries", DRY_RUN_MAX_POINTS))
    add_source = str(task.get("add_source", "unseen_existing"))
    destination_points = str(task.get("destination_points", "anywhere"))
    placement_prescreen = str(task.get("placement_prescreen", "dry_run"))
    receipt["options"] = {"replan_blocked_edges": replan_on, "placement_tries": placement_tries,
                          "stratify_by_kind": bool(task.get("stratify_by_kind", True)),
                          "add_source": add_source, "destination_points": destination_points,
                          "placement_prescreen": placement_prescreen}
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
        _note_unity_pid(out, controller)
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
        blocked: set = set(); replans: list[dict[str, Any]] = []
        plan1 = lean_route.plan_route(reachable=reach, start_pose=start, camera_height_m=cam_h, containers=usable,
                                      revisit_sequence=[], transition_cell=far)
        # sweep one is executed waypoint by waypoint so a blocked edge only replans the remainder
        order = plan1["sweep_one_order"]
        s1_start = len(ep.actions_done) - 1
        for k, cid in enumerate(order):
            vp = plan1["viewpoints"][cid]
            def _remaining(bl, _vp=vp):
                here, yaw = _agent_cell_yaw(controller)
                pitch = int(round(controller.last_event.metadata["agent"]["cameraHorizon"]))
                path = lean_route.bfs_path(cells, here, tuple(_vp["cell"]), bl)
                moved, yaw2 = lean_route.encode_path(path, yaw)
                return moved + lean_route.turn_actions(yaw2, _vp["yaw"]) + lean_route.look_actions(pitch, _vp["pitch"])
            _execute(controller, ep, _remaining(blocked), blocked=blocked, replans=replans,
                     replan=_remaining if replan_on else None)
        s1 = [s1_start, len(ep.actions_done) - 1]
        def _to_far(bl):
            here, yaw = _agent_cell_yaw(controller)
            path = lean_route.bfs_path(cells, here, far, bl)
            return lean_route.encode_path(path, yaw)[0]
        tr_start = len(ep.actions_done) - 1
        _execute(controller, ep, _to_far(blocked), blocked=blocked, replans=replans, replan=_to_far if replan_on else None)
        tr = [tr_start, len(ep.actions_done) - 1]
        plan1 = dict(plan1, segments={"sweep_one": s1, "transition": tr}, blocked_edges=sorted([list(c) for c in sorted(e)] for e in blocked),
                     replans=replans, executed_actions=len(ep.actions_done) - 1)
        (ep.prov / "route_stage1.json").write_text(json.dumps(plan1, indent=1))
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
            unseen = sel.unseen_objects(objects, ep.visible_pixels) if add_source == "unseen_existing" else None
            ok, spawn_points = _prescreen(controller, {c: usable[c] for c in usable}, tries=placement_tries,
                                          anywhere=(destination_points != "top"))
            pair_ok, dry_run_table = None, None
            if placement_prescreen == "dry_run":
                cand = [o for o in eligible if o["parent_receptacle"] in invisible] + list(unseen or [])
                pair_ok, dry_run_table = _dry_run_pairs(controller, cand, invisible, spawn_points, plan1["viewpoints"],
                                                        MIN_VISIBLE_PIXELS, beat=ep.beat)
                (ep.prov / "placement_dry_run.json").write_text(json.dumps(dry_run_table, indent=1))
            feasible = sel.feasible_triples(eligible, list(usable), invisible, ok, unseen=unseen, pair_ok=pair_ok)
            if not feasible:
                raise PilotFailure("intervention_window_unavailable", f"feasible set empty; U={len(invisible)} eligible={len(eligible)}")
            interventions = sel.sample_interventions(feasible, split_seed=task["split_seed"], house_id=house_id,
                                                     stratify_by_kind=bool(task.get("stratify_by_kind", True)),
                                                     one_placement_per_destination=(placement_prescreen == "dry_run"))
            feasible_by_kind: dict[str, int] = {}
            for row in feasible:
                feasible_by_kind[row["kind"]] = feasible_by_kind.get(row["kind"], 0) + 1
            (ep.prov / "interventions_sampled.json").write_text(json.dumps(
                {"feasible_set_size": len(feasible), "feasible_by_kind": feasible_by_kind,
                 "invisible_container_set_size": len(invisible),
                 "eligible_object_count": len(eligible), "unseen_object_count": (len(unseen) if unseen is not None else None),
                 "destinations_with_points": sum(1 for c in invisible if ok.get(c)),
                 "dry_run_pairs_tested": (len(dry_run_table) if dry_run_table is not None else None),
                 "dry_run_pairs_feasible": (len(pair_ok) if pair_ok is not None else None), "sampled": interventions}, indent=1))
            try:
                log = _apply_interventions(controller, interventions, spawn_points, viewpoints=plan1["viewpoints"],
                                           verify=(destination_points == "verified"))
            except PilotFailure:
                raise
            except Exception as exc:  # noqa: BLE001 - a simulator-side timeout is an intervention failure, not a write failure
                raise PilotFailure("intervention_execution_failed", f"simulator: {exc!r}"[:400]) from exc
        else:
            log = []
            eligible = []
        # stage 2: sweep two
        revisit = sel.revisit_sequence(interventions, split_seed=task["split_seed"], house_id=house_id)
        here = controller.last_event.metadata["agent"]
        start2 = {"position": here["position"], "rotation": here["rotation"], "horizon": here["cameraHorizon"]}
        # sweep two: from the real pose, visit exactly the revisit sequence (its "sweep one" IS the revisit)
        plan2b = lean_route.plan_route(reachable=reach, start_pose=start2, camera_height_m=cam_h,
                                       containers={c: usable[c] for c in revisit} if revisit else {},
                                       revisit_sequence=[], transition_cell=None,
                                       max_actions=max(1, MAXIMUM_ACTIONS - len(plan1["actions"])))
        for cid in revisit:
            vp = plan2b["viewpoints"][cid]
            def _remaining2(bl, _vp=vp):
                here, yaw = _agent_cell_yaw(controller)
                pitch = int(round(controller.last_event.metadata["agent"]["cameraHorizon"]))
                path = lean_route.bfs_path(cells, here, tuple(_vp["cell"]), bl)
                moved, yaw2 = lean_route.encode_path(path, yaw)
                return moved + lean_route.turn_actions(yaw2, _vp["yaw"]) + lean_route.look_actions(pitch, _vp["pitch"])
            _execute(controller, ep, _remaining2(blocked), blocked=blocked, replans=replans,
                     replan=_remaining2 if replan_on else None)
        (ep.prov / "route_stage2.json").write_text(json.dumps({"revisit_sequence": revisit, "plan": plan2b,
                                                                "blocked_edges": sorted([list(c) for c in sorted(e)] for e in blocked),
                                                                "replans": replans}, indent=1))
        (ep.prov / "reachable.json").write_text(json.dumps(reach))
        (ep.prov / "interventions.json").write_text(json.dumps({"null_window": null_window, "feasible_set_size": len(feasible),
                                                                "eligible_object_count": len(eligible),
                                                                "invisible_container_set_size": len(invisible), "executed": log,
                                                                "dropped_containers_no_viewpoint": dropped}, indent=1))
        receipt.update({"status": "succeeded", "observations": ep.index + 1, "actions": len(ep.actions_done) - 1,
                        "null_window": null_window, "executed_interventions": len(log), "feasible_set_size": len(feasible),
                        "invisible_container_set_size": len(invisible), "window_frames": window_frames,
                        "containers_usable": len(usable), "containers_dropped": len(dropped)})
    except lean_route.LeanRouteError as f:
        receipt.update({"status": "failed", "reason": "route_not_placeable", "detail": f"{f} | {traceback.format_exc()[-600:]}"})
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
    ap.add_argument("--stage", choices=["s1-02a", "s1-02b"], default="s1-02a")
    ap.add_argument("--pilot-root", help="S1-02b: the finished S1-02a output root (occupancy receipt, pilot houses)")
    ap.add_argument("--development-houses", type=int, default=50)
    ap.add_argument("--resume", action="store_true",
                    help="S1-02b: skip houses with a receipt; mark interrupted dirs failed; never regenerate")
    ap.add_argument("--stall-timeout-s", type=int, default=1800,
                    help="a started house with no heartbeat for this long is a stalled worker and is failed; "
                         "queued houses are never timed out; this is not a compute budget")
    # Defaults are the S0-02 v3 rules after D-224-S1 rulings 25-32.  The pre-ruling values stay
    # selectable only to replay the s1-02b/159654f run; they are not a second protocol.
    ap.add_argument("--replan-blocked-edges", action=argparse.BooleanOptionalAction, default=True,
                    help="ruling 27: on a rejected MoveAhead, block that edge and replan the rest")
    ap.add_argument("--placement-tries", type=int, default=DRY_RUN_MAX_POINTS,
                    help="ruling 31: spread candidate points per destination in the dry run")
    ap.add_argument("--stratify-by-kind", action=argparse.BooleanOptionalAction, default=True,
                    help="ruling 29: draw the kind first, then the triple")
    ap.add_argument("--add-source", choices=["spawn_asset", "unseen_existing"], default="unseen_existing",
                    help="ruling 30: relocate a never-rendered real object (spawn_asset = pre-ruling, unobservable)")
    ap.add_argument("--placement-prescreen", choices=["spawn_points", "dry_run"], default="dry_run",
                    help="rulings 31/32: real placement + viewpoint peek + revert during the window, one placement per destination")
    ap.add_argument("--destination-points", choices=["anywhere", "top", "verified"], default="anywhere",
                    help="kept for the smoke record; dry_run supersedes it")
    args = ap.parse_args()
    if args.stage == "s1-02b":
        return main_s1_02b(args)
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
              "source_rel": source.name, "split_seed": freeze["seed"], "commit": commit,
              "replan_blocked_edges": args.replan_blocked_edges, "placement_tries": args.placement_tries, "stratify_by_kind": args.stratify_by_kind, "add_source": args.add_source, "destination_points": args.destination_points, "placement_prescreen": args.placement_prescreen} for h in selected]
    base_vram = float(subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.strip().split("\n")[0])
    stop, q = mp.Event(), mp.Queue()
    sampler = mp.Process(target=_vram_peak_sampler, args=(stop, q), daemon=True); sampler.start()
    t0 = time.time()
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=args.workers) as pool_:
        results = pool_.map(run_house, tasks)
    wall = time.time() - t0
    stop.set()
    try:
        vram_peak = q.get(timeout=30)
    except Exception:  # noqa: BLE001 - sampler died or never sampled
        vram_peak = base_vram
    sampler.join(timeout=5)
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


def _capacity_measurements() -> dict[str, Any]:
    """Read-only capacity readings for the derivation (same 15 names as S1-01)."""

    import psutil
    vm = psutil.virtual_memory()
    du = os.statvfs("/root/autodl-tmp")
    gpu = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout.strip().split(", ")
    free_gb = du.f_bavail * du.f_frsize / 1e9
    return {
        "cpu_logical_cores": os.cpu_count(), "cpu_physical_cores": psutil.cpu_count(logical=False),
        "ram_total_gb": vm.total / 1e9, "ram_available_gb": vm.available / 1e9,
        "gpu_count": 1, "gpu_name": gpu[0], "gpu_total_vram_gb": float(gpu[1]) / 1024.0,
        "gpu_free_vram_gb": (float(gpu[1]) - float(gpu[2])) / 1024.0,
        "disk_free_gb_asset_root": free_gb, "disk_free_gb_install_root": free_gb,
        "python_version": sys.version.split()[0], "torch_version": "n/a-simulator-env", "cuda_available": True,
        "egl_resolves": True, "vulkan_resolves": True,
    }


def _last_progress(out_dir: str) -> float | None:
    """When the house last made progress: heartbeat, else started.json; None if it has not started."""

    for name in ("heartbeat", "started.json"):
        f = Path(out_dir) / name
        if f.exists():
            try:
                return f.stat().st_mtime
            except OSError:
                return None
    return None


def _run_with_timeout(tasks: list[dict[str, Any]], workers: int, stall_s: int, commit: str) -> list[dict[str, Any]]:
    """Run tasks on a spawn pool.  A task is failed only when its worker has stalled: it started and
    has made no progress (no heartbeat) for ``stall_s``.  Queued tasks are never timed out, and
    the wall clock is not a compute budget.  A stalled task's own Unity/worker pids are killed."""

    if not tasks:
        return []
    ctx = mp.get_context("spawn")
    results: list[dict[str, Any]] = []
    with ctx.Pool(processes=workers) as pool_:
        pending = {pool_.apply_async(run_house, (task,)): task for task in tasks}
        while pending:
            for async_result, task in list(pending.items()):
                if async_result.ready():
                    try:
                        results.append(async_result.get())
                    except Exception as exc:  # noqa: BLE001 - worker died; record, do not hang
                        results.append(_timeout_receipt(task, commit, f"worker_error: {exc!r}"[:400]))
                    del pending[async_result]
                    continue
                last = _last_progress(task["out"])
                if last is not None and time.time() - last > stall_s:
                    killed = _kill_stalled(task["out"])
                    results.append(_timeout_receipt(task, commit, f"worker_stalled_{stall_s}s_without_progress; killed {killed}"))
                    del pending[async_result]
            time.sleep(5)
        pool_.terminate()
    return results


def _timeout_receipt(task: dict[str, Any], commit: str, detail: str) -> dict[str, Any]:
    out = Path(task["out"]); out.mkdir(parents=True, exist_ok=True)
    r = {"house_id": task["house_id"], "source_index": task["index"], "code_commit": commit,
         "status": "failed", "reason": "frame_write_failed", "detail": detail,
         "occupancy": {"peak_rss_gb": 0.0, "cpu_seconds": 0.0, "wall_seconds": 0.0, "bytes_written": _dir_bytes(out)}}
    (out / "receipt.json").write_text(json.dumps(r, indent=1))
    return r


def _note_unity_pid(out: Path, controller: Any) -> None:
    pid = getattr(controller, "unity_pid", None)
    if pid is None:
        proc = getattr(getattr(controller, "server", None), "unity_proc", None)
        pid = getattr(proc, "pid", None)
    try:
        d = json.loads((out / "started.json").read_text())
        d["unity_pid"] = pid
        (out / "started.json").write_text(json.dumps(d))
    except (OSError, ValueError):
        pass


def _kill_stalled(out_dir: str) -> dict[str, Any]:
    """Kill only the stalled house's Unity and worker processes, as recorded in its started.json."""

    import signal

    killed: dict[str, Any] = {}
    try:
        d = json.loads((Path(out_dir) / "started.json").read_text())
    except (OSError, ValueError):
        return {"error": "no started.json"}
    for key in ("unity_pid", "worker_pid"):
        pid = d.get(key)
        if not pid:
            continue
        try:
            os.kill(int(pid), signal.SIGKILL)
            killed[key] = int(pid)
        except (OSError, ValueError) as exc:
            killed[key] = f"{pid}: {exc!r}"[:80]
    return killed


def main_s1_02b(args: argparse.Namespace) -> int:
    contract = json.loads(CONTRACT_S1_02A.read_text(encoding="utf-8"))
    lean_pilot.validate_pilot_contract(contract)
    freeze = contract["split_freeze"]
    pilot_root = Path(args.pilot_root)
    occupancy = json.loads((pilot_root / "occupancy_receipt.json").read_text(encoding="utf-8"))
    occupancy = {k: occupancy[k] for k in lean_pilot.OCCUPANCY_RECEIPT_FIELDS}
    pilot_plan = json.loads((pilot_root / "plan.json").read_text(encoding="utf-8"))
    measurements = _capacity_measurements()
    s1_01 = json.loads((ROOT / "configs" / "vsmt" / "lean_s1_assets_capacity_v2.json").read_text(encoding="utf-8"))
    scale = lean_pilot.plan_scale_up(occupancy, measurements, headroom_fraction=s1_01["worker_rule"]["headroom_fraction"])
    workers = min(scale["worker_count"], args.workers) if args.workers else scale["worker_count"]
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    source = Path(args.source)
    pool = [f"{DATASET_TAG}-{i:05d}" for i, _ in house_loader.records_from_json(source)]
    block = lean_pilot.train_block(pool, freeze)
    pilot_houses = block[:lean_pilot.PILOT_TOTAL_HOUSES]
    if pilot_houses != pilot_plan["selected"]:
        print("pilot houses do not match the recomputed head; refusing"); return 2
    houses = block[lean_pilot.PILOT_TOTAL_HOUSES:args.development_houses]
    out_root = Path(args.output_root); out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "plan.json").write_text(json.dumps({"stage": "s1-02b", "houses": houses, "pilot_root": str(pilot_root),
                                                    "derived": scale, "requested_workers": workers, "measurements": measurements,
                                                    "commit": commit}, indent=1))
    tasks = [{"house_id": h, "index": int(h.rsplit("-", 1)[1]), "out": str(out_root / h), "source_root": str(source.parent),
              "source_rel": source.name, "split_seed": freeze["seed"], "commit": commit,
              "replan_blocked_edges": args.replan_blocked_edges, "placement_tries": args.placement_tries, "stratify_by_kind": args.stratify_by_kind, "add_source": args.add_source, "destination_points": args.destination_points, "placement_prescreen": args.placement_prescreen} for h in houses]
    prior: list[dict[str, Any]] = []
    if args.resume:
        pending = []
        for task in tasks:
            d = Path(task["out"])
            if (d / "receipt.json").exists():
                prior.append(json.loads((d / "receipt.json").read_text(encoding="utf-8")))
            elif d.exists():
                # interrupted before a receipt: terminal failure, partial output kept, never rerun
                r = {"house_id": task["house_id"], "source_index": task["index"], "code_commit": commit,
                     "status": "failed", "reason": "frame_write_failed", "detail": "interrupted_before_receipt",
                     "occupancy": {"peak_rss_gb": 0.0, "cpu_seconds": 0.0, "wall_seconds": 0.0, "bytes_written": _dir_bytes(d)}}
                (d / "receipt.json").write_text(json.dumps(r, indent=1))
                prior.append(r)
            else:
                pending.append(task)
        print(f"resume: {len(prior)} terminal, {len(pending)} pending", flush=True)
        tasks = pending
    t0 = time.time()
    results = list(prior) + _run_with_timeout(tasks, workers, args.stall_timeout_s, commit)
    wall = time.time() - t0
    results = sorted(results, key=lambda r: r["house_id"])
    failed = [r for r in results if r["status"] != "succeeded"]
    non_null = [r for r in results if not r.get("null_window", False)]
    ok_non_null = [r for r in non_null if r["status"] == "succeeded" and r.get("executed_interventions", 0) >= 1]
    yield_rate = (len(ok_non_null) / len(non_null)) if non_null else None
    receipt = {
        "stage": "s1-02b", "code_commit": commit, "houses_planned": len(houses), "succeeded": len(results) - len(failed),
        "failed": len(failed), "failure_receipts": [{"house_id": r["house_id"], "reason": r["reason"], "detail": r.get("detail", "")[:400]} for r in failed],
        "null_window_episodes": len(results) - len(non_null), "yield_house_level_non_null": yield_rate,
        "yield_gate": s1_01 and json.loads(CONTRACT_S0_02.read_text(encoding="utf-8"))["intervention_window"]["minimum_yield"],
        "yield_gate_passed": (yield_rate is not None and yield_rate >= 0.6),
        "options": {"replan_blocked_edges": args.replan_blocked_edges, "placement_tries": args.placement_tries, "stratify_by_kind": args.stratify_by_kind, "add_source": args.add_source, "destination_points": args.destination_points, "placement_prescreen": args.placement_prescreen},
        "requested_workers": workers, "actual_workers": workers, "derived_worker_count": scale["worker_count"],
        "binding_constraint": scale["binding_constraint"], "concurrency_verified_at": scale["concurrency_verified_at"],
        "is_extrapolation": scale["is_extrapolation"], "wall_clock_seconds": round(wall, 1),
        "development_total_with_pilot": len(houses) + lean_pilot.PILOT_TOTAL_HOUSES,
    }
    (out_root / "s1_02b_receipt.json").write_text(json.dumps(receipt, indent=1))
    print(json.dumps({"receipt": receipt, "per_house": results}, indent=1, default=str))
    return 0 if receipt["yield_gate_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
