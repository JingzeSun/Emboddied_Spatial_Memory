"""S1-02a pilot: four workers, one ProcTHOR house each, end to end.

Usage (server, simulator env):
    python ops/vsmt/lean_s1_02a_pilot.py --output-root /root/autodl-tmp/vsmt_outputs/lean-s1-02a-<commit> \
        --source /root/autodl-tmp/vsmt_sources/procthor-10k-0.1.2/train.jsonl.gz --workers 4 \
        --private-salt-file /root/autodl-tmp/vsmt_private/null_window_salt.txt

What one worker does, in order, and what it writes:
  1. load the house, upgrade its schema (reused from vm04_two_house_worker),
     start CloudRendering with the S0-02 parameters, teleport to the
     house-authored agent pose, read GetReachablePositions;
  2. plan sweep one + the transition (lean_route), execute them, saving the
     three planes every frame; sweep one gives each object's max visible
     pixels (private instance masks), the transition gives, for every
     container, a public-visibility verdict per frame (S0-02 verdict source);
  3. U = containers invisible in every transition frame (subjects sealed from
     the best sweep-one frame, ruling 35); enumerate the feasible triples
     (lean_interventions), dry-run the placements, sample, draw the control
     containers (ruling 34); execute the interventions at the transition cell
     unless the episode is a salted null draw (ruling 37), which keeps the
     sample and the controls and skips only the execution;
  4. sweep two visits the intervened containers and the controls, interleaved
     by the seeded RNG;
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
    DRY_RUN_DESTINATIONS_PER_OBJECT, DRY_RUN_MAX_POINTS, FAILURE_REASONS, MAX_REPLANS, MAXIMUM_ACTIONS,
    MINIMUM_WINDOW_FRAMES, MIN_SUBJECT_PIXELS,
    MIN_VISIBLE_PIXELS, PUBLIC_FRAME_FIELDS, check_move_minimum,
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
    """Camera-to-world pose as {position_m, quaternion_xyzw} from AI2-THOR metadata.

    Ry(yaw) * Rx(+pitch): ``cameraHorizon`` is positive when the agent looks down, and with this
    sign the camera's forward axis (+z) gets a negative world-y component, as the VM-04 worker and
    the D-223 back-projection have always assumed.  Ruling 49 (2026-09-22): until then this
    function used Rx(-pitch), so every episode generated before it (c222c51, a397d16) carries a
    quaternion that looks up by the pitch; readers correct those episodes through
    ``vsmt.lean_public_pose`` under the S1-03 contract's ``public_pose_correction`` block, and the
    generated files are never rewritten.
    """

    cam = meta["cameraPosition"]
    yaw = math.radians(float(meta["agent"]["rotation"]["y"]))
    pitch = math.radians(float(meta["agent"]["cameraHorizon"]))  # positive = down
    cy_, sy_ = math.cos(yaw), math.sin(yaw)
    cp_, sp_ = math.cos(pitch), math.sin(pitch)
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
        self.pixels_by_frame: list[dict[str, int]] = []   # per frame: object id -> private mask pixels (visible only)
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
        self.pixels_by_frame.append(dict(private_record["object_visibility"]))
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
    """Non-pickupable receptacles.  The room floor carries AI2-THOR's receptacle flag but is not a
    container in the paper's sense (its "viewpoint" is the house centre); it is excluded and the
    exclusion is written to the receipt."""

    out = {}
    for o in meta["objects"]:
        if o.get("objectType") == "Floor":
            continue
        if o.get("receptacle") and not o.get("pickupable"):
            bb = o.get("axisAlignedBoundingBox") or {}
            c = bb.get("center") or o["position"]
            out[o["objectId"]] = {"x": float(c["x"]), "y": float(c["y"]), "z": float(c["z"])}
    return out


def _object_table(meta: dict[str, Any]) -> list[dict[str, Any]]:
    """Object rows for the selector.  ``parent_receptacle`` is the first non-Floor entry of
    ``parentReceptacles`` (ruling 52: entry 0 is the room floor for anything on low furniture, which
    silently removed 10% of the eligible objects as sources) and ``parent_receptacles`` keeps the
    full list exactly as the simulator reported it."""

    rows = []
    for o in meta["objects"]:
        parents = list(o.get("parentReceptacles") or [])
        rows.append({"object_id": o["objectId"], "asset_id": o.get("assetId"),
                     "pickupable": bool(o.get("pickupable")), "parent_receptacle": sel.parent_receptacle_of(parents),
                     "parent_receptacles": parents,
                     "is_agent": False, "is_structure": not bool(o.get("pickupable")) and not bool(o.get("receptacle"))})
    return rows


def _max_pixels(ep: Episode, lo: int, hi: int) -> dict[str, int]:
    """Per object: the most private mask pixels in frames lo..hi inclusive."""

    out: dict[str, int] = {}
    for fr in ep.pixels_by_frame[lo:hi + 1]:
        for oid, px in fr.items():
            if px > out.get(oid, 0):
                out[oid] = px
    return out


def _seal_container_subjects(ep: Episode, containers: dict[str, Any],
                             sweep_one: tuple[int, int]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Seal one visibility subject per container from the sweep-one frame with the most container
    pixels (ruling 35); private mask, provenance only.  Returns (subjects, per-container frame record).

    白话：以前用"最后一次站在视点格上的那一帧"封印，结果 972/1521 个容器在那一帧里是
    0 像素（几个容器共用一个视点格、或后来路过了那个格子），只有 411 个能封印，U 因此
    极小且偏向抽屉。现在取扫掠一里该容器像素最多的那一帧，≥512 像素才封印。
    """

    subjects, frames = {}, {}
    calib = intrinsics()
    lo, hi = sweep_one
    for cid in sorted(containers):
        best_px, best_idx = 0, None
        for idx in range(lo, hi + 1):
            px = ep.pixels_by_frame[idx].get(cid, 0)
            if px > best_px:
                best_px, best_idx = px, idx
        frames[cid] = {"frame": best_idx, "pixels": best_px, "sealed": False}
        if best_idx is None or best_px < MIN_SUBJECT_PIXELS:
            continue
        fr = ep.frames[best_idx]
        mask = np.asarray(fr["masks"][cid], dtype=bool)
        try:
            subjects[cid] = seal_public_visibility_subject(
                subject_public_ref=f"container:{sha(cid)[:16]}", source_public_packet_sha256=fr["frame_digest"],
                source_observation_index=best_idx, public_mask=mask, public_depth_m=fr["depth"],
                camera_calibration=calib, camera_pose=fr["pose"], config=VIS_CONFIG)
            frames[cid]["sealed"] = True
        except ValueError as exc:
            frames[cid]["seal_error"] = str(exc)
    return subjects, frames


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
#: A reverted object is back when it is within this distance of the pose it held when the dry run
#: started.  It is an engineering epsilon for "the same place", not a science parameter: after a
#: kinematic teleport the pose is exact, and physics settling moves a resting object by under a
#: millimetre.  S0-02 already says a failed revert fails the house; checking lastActionSuccess
#: alone did not implement that -- in the 4bff1a8 run TeleportObject reported success while
#: leaving objects 0.05 m to 10.9 m away (eggs that crack, objects ejected by a collider), in
#: three episodes that were then recorded as successes (LOG-239).
REVERT_TOLERANCE_M = 0.01


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


def _object_position(controller: Any, oid: str) -> dict[str, float] | None:
    o = next((x for x in controller.last_event.metadata["objects"] if x["objectId"] == oid), None)
    return None if o is None else dict(o["position"])


def _distance(a: dict[str, float] | None, b: dict[str, float] | None) -> float | None:
    if a is None or b is None:
        return None
    return math.dist([a["x"], a["y"], a["z"]], [b["x"], b["y"], b["z"]])


def _revert_object(controller: Any, oid: str, orig_pos: dict[str, float], orig_rot: dict[str, float]) -> dict[str, Any]:
    """Put a dry-run object back and verify it is there; never leave an unregistered change behind.

    白话：试放之后必须把物体放回原位。`TeleportObject` 报告成功并不等于物体真的回去了——
    4bff1a8 的数据里有报告成功却停在 0.05 m 到 10.9 m 外的（鸡蛋摔碎、被碰撞体弹开），其中
    三条还被记成成功的 episode。窗口内任何没有登记的位移都是污染：teacher 会在扫掠二看到
    一个"没人动过却换了地方"的物体。现在逐次核对真实位置，先普通放回、不行再运动学放回，
    仍然超过 1 cm 就让整条 episode 失败（S0-02 的 revert_failure_fails_the_house）。
    """

    log: list[dict[str, Any]] = []
    for attempt, kinematic in enumerate(((False,), (True,)), start=1):
        step: dict[str, Any] = {"action": "TeleportObject", "objectId": oid, "position": orig_pos,
                                "rotation": orig_rot, "forceAction": True}
        if kinematic[0]:
            step["forceKinematic"] = True
        event = controller.step(**step)
        if kinematic[0]:
            controller.step(action="Pass")
        drift = _distance(_object_position(controller, oid), orig_pos)
        log.append({"attempt": attempt, "force_kinematic": bool(kinematic[0]),
                    "action_success": event.metadata.get("lastActionSuccess") is True,
                    "error": (event.metadata.get("errorMessage") or "")[:160],
                    "drift_m": None if drift is None else round(drift, 4)})
        if drift is not None and drift <= REVERT_TOLERANCE_M:
            return {"ok": True, "drift_m": round(drift, 4), "attempts": log}
    return {"ok": False, "drift_m": log[-1]["drift_m"], "attempts": log}


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
                   viewpoints: dict[str, Any], min_px: int, beat: Any = None,
                   table: list[dict[str, Any]] | None = None,
                   destinations: dict[str, list[str]] | None = None) -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]]]:
    """Try every (object, U destination) placement for real, peek, and put the object back.

    白话（裁决 31，proposed）：可行集里的 move／add 不再靠"容器有生成点"猜，而是在窗口
    内真的把物体放过去一次、从该容器的重访视点偷看一眼（私有渲染，≥196 像素才算），再
    用 TeleportObject 把物体放回原位。只有真放得下且看得见的 (物体, 目的容器) 对才进 F，
    并记住那个点。窗口内容器本就不可见、干预之间不采帧，所以试放不会进入 public。
    """

    meta = controller.last_event.metadata
    objs = {o["objectId"]: o for o in meta["objects"]}
    # every object's pose before the dry run touches anything: the dry run must leave the world
    # exactly here.  Testing one object can knock another off a surface, and that object's own row
    # may already be behind us, so the whole set is swept once at the end.
    before = {oid: (dict(o["position"]), dict(o["rotation"])) for oid, o in objs.items() if o.get("pickupable")}
    ok: dict[tuple[str, str], dict[str, Any]] = {}
    table = [] if table is None else table
    for row in candidates:
        if beat is not None:
            beat()
        oid = row["object_id"]; o = objs.get(oid)
        if o is None:
            continue
        orig_pos, orig_rot = dict(o["position"]), dict(o["rotation"])
        # ruling 39: the destinations this object is tested against come from the seeded per-object
        # draw; without a draw (replay of the S1 runs) every U destination is tested in grid order
        order = destinations.get(oid, []) if destinations is not None else sorted(u_containers)
        for dst in order:
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
            # A rejected PlaceObjectAtPoint can still have moved the object: in the 12d4209 pilot a
            # teddy bear ended 12.2 m from its pose with no placement ever reported as successful.
            # So the pose is verified and, if it moved at all, restored -- whether or not anything
            # was placed.  Only a restore that fails fails the house.
            observed = _distance(_object_position(controller, oid), orig_pos)
            if placed_any or observed is None or observed > REVERT_TOLERANCE_M:
                revert = _revert_object(controller, oid, orig_pos, orig_rot)
                revert["moved_without_a_successful_placement"] = (not placed_any)
                revert["drift_before_revert_m"] = None if observed is None else round(observed, 4)
            else:
                revert = {"ok": None, "drift_m": round(observed, 4), "attempts": [], "nothing_moved": True}
            table.append({"object_id": oid, "destination": dst, "tries": tried, "placed_any": placed_any, "best_pixels": best,
                          "feasible": found is not None, "revert_ok": revert["ok"], "revert_drift_m": revert["drift_m"],
                          "revert_attempts": revert["attempts"],
                          "original_position": orig_pos, "original_rotation": orig_rot})
            if revert["ok"] is False:
                raise PilotFailure(
                    "intervention_execution_failed",
                    f"dry-run could not put {oid} back: {revert['drift_m']} m from its original pose after "
                    f"{len(revert['attempts'])} teleports (tolerance {REVERT_TOLERANCE_M} m, moved without a "
                    f"successful placement={revert.get('moved_without_a_successful_placement')}); an unregistered "
                    f"displacement inside the window would corrupt the labels, so the house fails"[:400])
            if found is not None:
                ok[(oid, dst)] = {"point": found, "pixels": best, "tries": tried}
    _sweep_back(controller, before, table)
    return ok, table


def _sweep_back(controller: Any, before: dict[str, tuple[dict[str, float], dict[str, float]]],
                table: list[dict[str, Any]]) -> None:
    """Every pickupable object must end the dry run where it began; restore the ones that did not.

    白话：试放某个物体时可能把旁边的物体碰下桌子，而那个物体自己那一行可能早就测完了，
    逐行核对抓不到它。所以 dry-run 结束时把全部可拾取物体和开工前的快照比一遍，动了的
    放回去并登记，放不回去就整条作废。这样"窗口里除了登记的干预之外什么都没变"才是可证
    的，而不是假定的——裁决 34 的对照容器正是靠这一条成立。
    """

    moved = []
    for oid, (pos, rot) in sorted(before.items()):
        drift = _distance(_object_position(controller, oid), pos)
        if drift is None or drift > REVERT_TOLERANCE_M:
            outcome = _revert_object(controller, oid, pos, rot)
            moved.append({"object_id": oid, "drift_before_m": None if drift is None else round(drift, 4),
                          "restored": outcome["ok"], "drift_after_m": outcome["drift_m"]})
            if outcome["ok"] is False:
                table.append({"final_sweep": moved})
                raise PilotFailure(
                    "intervention_execution_failed",
                    f"dry-run final sweep could not put {oid} back: {outcome['drift_m']} m from its original "
                    f"pose (tolerance {REVERT_TOLERANCE_M} m); the window would contain an unregistered "
                    f"displacement, so the house fails"[:400])
    table.append({"final_sweep": moved, "objects_checked": len(before)})


def _object_pose(controller: Any, oid: str) -> dict[str, Any] | None:
    o = next((x for x in controller.last_event.metadata["objects"] if x["objectId"] == oid), None)
    return None if o is None else {"position": dict(o["position"]), "rotation": dict(o["rotation"])}


def _apply_interventions(controller: Any, rows: list[dict[str, Any]], *, viewpoints: dict[str, Any],
                         attempts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Execute the sampled interventions.  Every row's attempt record is appended to ``attempts``
    before anything can raise, so a failed house still leaves the full attempt table.

    白话：执行放置时先试 dry-run 记住的那个点并偷看；若放不下或看不见（4bff1a8 里有 3 个
    house 是这样），不再只在旧的 32 个点里找，而是重新向模拟器要当前状态下的生成点、
    再均匀取 32 个逐点试放并偷看。每个点的错误、放置前物体的真实位姿都写进 provenance，
    失败也写，这样下次能定因。
    """

    log = []
    for row in rows:
        kind = row["kind"]
        oid = row["object_id"]
        vp = viewpoints.get(row.get("destination") or "")
        record: dict[str, Any] = {**row, "pose_before_execution": _object_pose(controller, oid), "attempts": []}
        attempts.append(record)
        seen_px, point_source, ev = None, None, None
        if kind == "remove":
            # RemoveFromScene hangs Unity in Procedural scenes (NullReferenceException while generating
            # metadata; reproduced on a fresh controller, LOG-236).  DisableObject deactivates the
            # GameObject: 0 px in instance segmentation, no collider, still listed in simulator
            # metadata with visible=false.  Private frame records are built from instance masks,
            # so a disabled object never appears in them.
            ev = controller.step(action="DisableObject", objectId=oid)
            ok = ev.metadata.get("lastActionSuccess") is True
            record["attempts"].append({"executor": "DisableObject", "ok": ok, "error": (ev.metadata.get("errorMessage") or "")[:300]})
            executor = "DisableObject"
        else:
            assert kind == "move" or row.get("add_source") == "unseen_existing", row
            if vp is None:
                raise PilotFailure("intervention_execution_failed", f"{kind} {oid}: destination has no viewpoint")
            candidates: list[tuple[str, Any]] = []
            if row.get("point") is not None:
                candidates.append(("dry_run", row["point"]))
            fresh = controller.step(action="GetSpawnCoordinatesAboveReceptacle", objectId=row["destination"],
                                    anywhere=True).metadata.get("actionReturn") or []
            candidates += [("fresh_spawn_points", pt) for pt in _spread(fresh, DRY_RUN_MAX_POINTS) if pt != row.get("point")]
            record["fresh_spawn_point_count"] = len(fresh)
            for source, pt in candidates:
                ev = controller.step(action="PlaceObjectAtPoint", objectId=oid, position=pt)
                placed = ev.metadata.get("lastActionSuccess") is True
                att = {"source": source, "point": pt, "placed": placed, "error": (ev.metadata.get("errorMessage") or "")[:200], "pixels": None}
                if placed:
                    att["pixels"] = _peek_pixels(controller, vp, oid)
                record["attempts"].append(att)
                if placed and att["pixels"] >= MIN_VISIBLE_PIXELS:
                    seen_px, point_source = att["pixels"], source
                    break
            ok = point_source is not None
            if not ok and ev is not None and ev.metadata.get("lastActionSuccess") is True:
                best = max((att["pixels"] or 0) for att in record["attempts"])
                ev.metadata["lastActionSuccess"] = False
                ev.metadata["errorMessage"] = f"placed but not visible from the viewpoint at any of {len(candidates)} points (best {best} px)"
            executor = "PlaceObjectAtPoint(unseen_existing)" if row.get("add_source") == "unseen_existing" else "PlaceObjectAtPoint"
        record.update({"executed": ok, "placement_tries": len(record["attempts"]), "executor": executor,
                       "verified_pixels": seen_px, "point_source": point_source,
                       "error": ("" if ok else (ev.metadata.get("errorMessage") or "")[:300])})
        log.append({k: v for k, v in record.items() if k not in ("attempts", "pose_before_execution")})
        if not ok:
            raise PilotFailure("intervention_execution_failed", f"{kind} {oid}: {record['error']}")
    return log


def _remaining_to(controller: Any, ep: Episode, cells: set, blocked: set, vp_box: dict[str, Any], *, cid: str,
                  center: dict[str, float], cam_h: float, reselections: list[dict[str, Any]], phase: str) -> list[str]:
    """Actions from the real pose to the container's viewpoint under the blocklist.  If the blocklist
    has cut the viewpoint cell off, the nearest admissible viewpoint inside the reachable component
    is selected instead and the change is recorded (00975 in the 4bff1a8 run).

    白话：被拒绝的格间边可能把视点格割开（视点在椅子后面的死角）。以前只换路不换视点，
    走不到就整条作废；现在在"带黑名单还走得到"的格子里重选最近的合格视点，并把新旧视点
    写进 provenance。规则没变（最近合格视点、并列按网格序），只是"可达"改为按实测算。
    """

    here, yaw = _agent_cell_yaw(controller)
    pitch = int(round(controller.last_event.metadata["agent"]["cameraHorizon"]))
    vp = vp_box["vp"]
    try:
        path = lean_route.bfs_path(cells, here, tuple(vp["cell"]), blocked)
    except lean_route.LeanRouteError as exc:
        if "bfs_no_path" not in str(exc):
            raise
        component = lean_route.reachable_component(cells, here, blocked)
        new_vp = lean_route.select_viewpoint(center, cells, camera_height_m=cam_h, component=component)
        new_vp = dict(new_vp, cell=list(new_vp["cell"]))
        if tuple(new_vp["cell"]) == tuple(vp["cell"]):
            raise
        reselections.append({"phase": phase, "container": cid, "observation_index": ep.index,
                             "old": dict(vp), "new": dict(new_vp), "blocked_edges": len(blocked)})
        vp_box["vp"] = vp = new_vp
        path = lean_route.bfs_path(cells, here, tuple(vp["cell"]), blocked)
    moved, yaw2 = lean_route.encode_path(path, yaw)
    return moved + lean_route.turn_actions(yaw2, vp["yaw"]) + lean_route.look_actions(pitch, vp["pitch"])


def _farthest_cell(cells: set, origin: tuple[int, int], blocked: set) -> tuple[int, int]:
    """The reachable cell with the longest BFS path from ``origin`` under the blocklist, ties by grid order."""

    component = lean_route.reachable_component(cells, origin, blocked)
    return max(sorted(component), key=lambda c: (len(lean_route.bfs_path(cells, origin, c, blocked)), c))


def _walk_window_segment(controller: Any, ep: Episode, cells: set, blocked: set, replans: list[dict[str, Any]], *,
                         frames: int, replan_on: bool) -> dict[str, Any]:
    """Pending ruling 53 probe: after the transition, keep walking towards the cell farthest from
    where the transition ended for exactly ``frames`` actions; that segment is the window.

    白话（待裁 53 的探针，用户 2026-09-23 授权"先跑前几条看看效果"）：现行规则把整段过渡当窗口，
    小房子走一遍就把每个容器都看到一次，U 为空。这里在过渡走到最远格之后，再朝"离现在位置最远的
    可达格"继续走恰好 L 步（转身也算一步、也出一帧），U 只在这 L 帧上算。输入是当前位姿、可达格、
    黑名单和 L；输出是这段的观察序号范围、真正走了几步、目标格和"到目标格一共有几步可走"。走不满
    L 步（先到了目标格）整条按 intervention_window_unavailable 失败，不缩短窗口。它不改 U 的算法、
    像素阈值或抽样，不是 S1-02 的冻结协议，产物只作估算。
    """

    here, yaw = _agent_cell_yaw(controller)
    target = _farthest_cell(cells, here, blocked)
    available = len(lean_route.encode_path(lean_route.bfs_path(cells, here, target, blocked), yaw)[0])
    start = len(ep.actions_done) - 1

    def _remaining(bl: set) -> list[str]:
        h, y = _agent_cell_yaw(controller)
        acts = lean_route.encode_path(lean_route.bfs_path(cells, h, target, bl), y)[0]
        budget = frames - (len(ep.actions_done) - 1 - start)
        return acts[:max(0, budget)]

    _execute(controller, ep, _remaining(blocked), blocked=blocked, replans=replans, replan=_remaining if replan_on else None)
    end = len(ep.actions_done) - 1
    record = {"segment": [start, end], "frames_requested": frames, "frames_walked": end - start,
              "start_cell": list(here), "start_yaw": yaw, "target_cell": list(target), "path_actions_available": available,
              "rule": "walk_towards_the_cell_farthest_from_the_transition_end_for_exactly_L_actions"}
    (ep.prov / "window_segment.json").write_text(json.dumps(record, indent=1))
    if end - start < frames:
        raise PilotFailure("intervention_window_unavailable",
                           f"window segment {end - start} < {frames} frames (path to the farthest cell had {available} actions); "
                           f"not shortened")
    return record


def run_house(task: dict[str, Any]) -> dict[str, Any]:
    house_id, index, out = task["house_id"], task["index"], Path(task["out"])
    t0 = time.time()
    receipt: dict[str, Any] = {"house_id": house_id, "source_index": index, "code_commit": task["commit"]}
    # defaults are the contract rules after rulings 25-38; the old values remain selectable only to replay s1-02b/159654f
    replan_on = bool(task.get("replan_blocked_edges", True))
    placement_tries = int(task.get("placement_tries", DRY_RUN_MAX_POINTS))
    add_source = str(task.get("add_source", "unseen_existing"))
    destination_points = str(task.get("destination_points", "anywhere"))
    placement_prescreen = str(task.get("placement_prescreen", "dry_run"))
    dry_run_per_object = int(task.get("dry_run_destinations_per_object", DRY_RUN_DESTINATIONS_PER_OBJECT))
    receipt["options"] = {"dry_run_destinations_per_object": dry_run_per_object, "replan_blocked_edges": replan_on, "placement_tries": placement_tries,
                          "stratify_by_kind": bool(task.get("stratify_by_kind", True)),
                          "add_source": add_source, "destination_points": destination_points,
                          "placement_prescreen": placement_prescreen, "twin_control": True,
                          "subject_seal_frame": "sweep_one_frame_with_the_most_container_pixels"}
    # ruling 37: the null draw is salted; the salt never enters the receipt, only its digest
    null_window = sel.is_null_window(task["split_seed"], house_id, task["private_salt"])
    receipt["null_window"] = null_window
    receipt["null_window_salt_sha256"] = sha_bytes(task["private_salt"].encode("utf-8"))
    controller = None
    attempts: list[dict[str, Any]] = []
    reselections: list[dict[str, Any]] = []
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
        floor_excluded = sorted(o["objectId"] for o in meta["objects"] if o.get("objectType") == "Floor" and o.get("receptacle"))
        # viewpoints reachable from the start cell? drop containers without one (recorded)
        cells = lean_route.reachable_cells(reach)
        start_cell = (lean_route.snap(start["position"]["x"]), lean_route.snap(start["position"]["z"]))
        component0 = lean_route.reachable_component(cells, start_cell) if start_cell in cells else None
        usable, dropped = {}, []
        for cid, c in sorted(containers.items()):
            try:
                lean_route.select_viewpoint(c, cells, camera_height_m=cam_h, component=component0); usable[cid] = c
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
        for cid in order:
            vp_box = {"vp": plan1["viewpoints"][cid]}
            def _remaining(bl, _box=vp_box, _cid=cid):
                return _remaining_to(controller, ep, cells, bl, _box, cid=_cid, center=usable[_cid], cam_h=cam_h,
                                     reselections=reselections, phase="sweep_one")
            _execute(controller, ep, _remaining(blocked), blocked=blocked, replans=replans,
                     replan=_remaining if replan_on else None)
            plan1["viewpoints"][cid] = vp_box["vp"]
        s1 = [s1_start, len(ep.actions_done) - 1]
        def _to_far(bl):
            here, yaw = _agent_cell_yaw(controller)
            path = lean_route.bfs_path(cells, here, far, bl)
            return lean_route.encode_path(path, yaw)[0]
        tr_start = len(ep.actions_done) - 1
        _execute(controller, ep, _to_far(blocked), blocked=blocked, replans=replans, replan=_to_far if replan_on else None)
        tr = [tr_start, len(ep.actions_done) - 1]
        # pending ruling 53 probe: an optional window segment of exactly window_segment_frames actions
        # walked after the transition; U is then computed on that segment only (0 = frozen whole-transition rule)
        seg_frames = int(task.get("window_segment_frames", 0) or 0)
        window_segment = (_walk_window_segment(controller, ep, cells, blocked, replans, frames=seg_frames, replan_on=replan_on)
                          if seg_frames > 0 else None)
        window = list(window_segment["segment"]) if window_segment else tr
        segments = {"sweep_one": s1, "transition": tr}
        if window_segment:
            segments["window_segment"] = window
        plan1 = dict(plan1, segments=segments, blocked_edges=sorted([list(c) for c in sorted(e)] for e in blocked),
                     replans=replans, executed_actions=len(ep.actions_done) - 1, viewpoint_reselections=list(reselections),
                     floor_excluded=floor_excluded)
        (ep.prov / "route_stage1.json").write_text(json.dumps(plan1, indent=1))
        window_frames = window[1] - window[0]
        # ruling 35: subjects sealed from the best sweep-one frame; U = invisible in every window frame
        subjects, subject_frames = _seal_container_subjects(ep, usable, tuple(s1))
        invisible, verdicts = _invisible_set(ep, subjects, tuple(window))
        (ep.prov / "window_verdicts.json").write_text(json.dumps(
            {"window": window, "frames": window_frames,
             "window_protocol": ("two_segment_probe_pending_ruling_53" if window_segment else "whole_transition"),
             "leave_segment": (tr if window_segment else None), "window_segment": window_segment,
             "invisible": sorted(invisible), "subjects": subject_frames, "verdicts": verdicts}, indent=1))
        # ruling 34 (twin control): every episode, null or not, builds U, F, the sample and the controls;
        # a null episode skips only the execution
        if window_frames < MINIMUM_WINDOW_FRAMES:
            raise PilotFailure("intervention_window_unavailable", f"window {window_frames} < {MINIMUM_WINDOW_FRAMES}")
        objects = _object_table(controller.last_event.metadata)
        px_sweep_one = _max_pixels(ep, s1[0], s1[1])        # ruling 38: eligibility counts sweep-one frames only
        px_before_window = _max_pixels(ep, 0, window[1])    # unseen: never rendered before the window ends
        eligible = sel.eligible_objects(objects, px_sweep_one)
        unseen = sel.unseen_objects(objects, px_before_window) if add_source == "unseen_existing" else None
        # ruling 52: the full object table with every parentReceptacles list goes to provenance before the
        # dry run, so an empty feasible set can be traced to the exact filter that emptied it
        eligible_ids = {o["object_id"] for o in eligible}
        unseen_ids = {o["object_id"] for o in (unseen or [])}
        (ep.prov / "object_table.json").write_text(json.dumps(
            {"parent_receptacle_rule": "first_non_Floor_entry_of_parentReceptacles (ruling 52)",
             "invisible_containers": sorted(invisible),
             "objects": [{**{k: o[k] for k in ("object_id", "asset_id", "pickupable", "parent_receptacle", "parent_receptacles")},
                          "pixels_sweep_one": px_sweep_one.get(o["object_id"], 0),
                          "pixels_before_window_end": px_before_window.get(o["object_id"], 0),
                          "eligible": o["object_id"] in eligible_ids, "unseen": o["object_id"] in unseen_ids,
                          "parent_in_U": o["parent_receptacle"] in invisible}
                         for o in objects if o["pickupable"]]}, indent=1))
        ok, spawn_points = _prescreen(controller, {c: usable[c] for c in usable}, tries=placement_tries,
                                      anywhere=(destination_points != "top"))
        pair_ok, dry_run_table = None, None
        if placement_prescreen == "dry_run":
            cand = [o for o in eligible if o["parent_receptacle"] in invisible] + list(unseen or [])
            dests = sel.dry_run_destinations(cand, invisible, split_seed=task["split_seed"], house_id=house_id,
                                             per_object=dry_run_per_object)
            pairs_total = sum(1 for o in cand for d in sorted(invisible)
                              if d != o.get("parent_receptacle") and d in spawn_points and d in plan1["viewpoints"])
            dry_run_table = []
            try:
                pair_ok, dry_run_table = _dry_run_pairs(controller, cand, invisible, spawn_points, plan1["viewpoints"],
                                                        MIN_VISIBLE_PIXELS, beat=ep.beat, table=dry_run_table, destinations=dests)
            finally:
                (ep.prov / "placement_dry_run.json").write_text(json.dumps(dry_run_table, indent=1))
        feasible = sel.feasible_triples(eligible, list(usable), invisible, ok, unseen=unseen, pair_ok=pair_ok)
        if not feasible:
            raise PilotFailure("intervention_window_unavailable",
                               f"feasible set empty; U={len(invisible)} eligible={len(eligible)} "
                               f"eligible_on_U={sum(1 for o in eligible if o['parent_receptacle'] in invisible)} "
                               f"unseen={len(unseen or [])} destinations_with_points={sum(1 for c in invisible if ok.get(c))} "
                               f"dry_run_pairs_feasible={len(pair_ok) if pair_ok is not None else None}")
        interventions = sel.sample_interventions(feasible, split_seed=task["split_seed"], house_id=house_id,
                                                 stratify_by_kind=bool(task.get("stratify_by_kind", True)),
                                                 one_placement_per_destination=(placement_prescreen == "dry_run"))
        controls = sel.select_controls(eligible, list(usable), invisible, interventions,
                                       split_seed=task["split_seed"], house_id=house_id)
        feasible_by_kind: dict[str, int] = {}
        for row in feasible:
            feasible_by_kind[row["kind"]] = feasible_by_kind.get(row["kind"], 0) + 1
        (ep.prov / "interventions_sampled.json").write_text(json.dumps(
            {"null_window": null_window, "feasible_set_size": len(feasible), "feasible_by_kind": feasible_by_kind,
             "invisible_container_set_size": len(invisible),
             "eligible_object_count": len(eligible), "unseen_object_count": (len(unseen) if unseen is not None else None),
             "destinations_with_points": sum(1 for c in invisible if ok.get(c)),
             "dry_run_pairs_tested": (sum(1 for r in dry_run_table if "object_id" in r) if dry_run_table is not None else None),
             "dry_run_pairs_total": (pairs_total if dry_run_table is not None else None),
             "dry_run_destinations_per_object": dry_run_per_object,
             "feasible_set_size_estimate": (round(len(feasible) * pairs_total / max(1, sum(1 for r in dry_run_table if "object_id" in r)), 1)
                                            if dry_run_table is not None and any("object_id" in r for r in dry_run_table) else None),
             "dry_run_final_sweep": next((r for r in (dry_run_table or []) if "final_sweep" in r), None),
             "dry_run_pairs_feasible": (len(pair_ok) if pair_ok is not None else None), "sampled": interventions,
             "controls": controls}, indent=1))
        if null_window:
            log = []   # twin: the sample and the controls are kept, nothing is executed
        else:
            try:
                log = _apply_interventions(controller, interventions, viewpoints=plan1["viewpoints"], attempts=attempts)
            except PilotFailure:
                (ep.prov / "interventions_attempted.json").write_text(json.dumps(attempts, indent=1))
                raise
            except Exception as exc:  # noqa: BLE001 - a simulator-side timeout is an intervention failure, not a write failure
                (ep.prov / "interventions_attempted.json").write_text(json.dumps(attempts, indent=1))
                raise PilotFailure("intervention_execution_failed", f"simulator: {exc!r}"[:400]) from exc
        # stage 2: sweep two visits the intervened containers and the controls, interleaved by the seeded RNG
        control_ids = [c["container"] for c in controls["controls"]]
        revisit = sel.revisit_sequence(interventions, split_seed=task["split_seed"], house_id=house_id, controls=control_ids)
        here = controller.last_event.metadata["agent"]
        start2 = {"position": here["position"], "rotation": here["rotation"], "horizon": here["cameraHorizon"]}
        executed_so_far = len(ep.actions_done) - 1
        plan2b = lean_route.plan_route(reachable=reach, start_pose=start2, camera_height_m=cam_h,
                                       containers={c: usable[c] for c in revisit} if revisit else {},
                                       revisit_sequence=[], transition_cell=None,
                                       max_actions=max(1, MAXIMUM_ACTIONS - executed_so_far))
        s2_start = len(ep.actions_done) - 1
        for cid in revisit:
            vp_box = {"vp": plan1["viewpoints"][cid]}   # the viewpoint the dry-run peeked from (after any sweep-one reselection)
            def _remaining2(bl, _box=vp_box, _cid=cid):
                return _remaining_to(controller, ep, cells, bl, _box, cid=_cid, center=usable[_cid], cam_h=cam_h,
                                     reselections=reselections, phase="sweep_two")
            _execute(controller, ep, _remaining2(blocked), blocked=blocked, replans=replans,
                     replan=_remaining2 if replan_on else None)
        s2 = [s2_start, len(ep.actions_done) - 1]
        moves = [r for r in log if r["kind"] == "move"]
        moves_source_first = sum(1 for r in moves if revisit.index(r["source"]) < revisit.index(r["destination"]))
        (ep.prov / "route_stage2.json").write_text(json.dumps({"revisit_sequence": revisit, "plan": plan2b, "segments": {"sweep_two": s2},
                                                                "viewpoints_used": {c: plan1["viewpoints"][c] for c in revisit},
                                                                "blocked_edges": sorted([list(c) for c in sorted(e)] for e in blocked),
                                                                "replans": replans, "viewpoint_reselections": reselections}, indent=1))
        (ep.prov / "reachable.json").write_text(json.dumps(reach))
        (ep.prov / "interventions.json").write_text(json.dumps({"null_window": null_window, "feasible_set_size": len(feasible),
                                                                "eligible_object_count": len(eligible),
                                                                "invisible_container_set_size": len(invisible), "executed": log,
                                                                "sampled": interventions, "controls": controls,
                                                                "moves_executed": len(moves), "moves_source_first": moves_source_first,
                                                                "attempts": attempts,
                                                                "dropped_containers_no_viewpoint": dropped, "floor_excluded": floor_excluded}, indent=1))
        receipt.update({"status": "succeeded", "observations": ep.index + 1, "actions": len(ep.actions_done) - 1,
                        "null_window": null_window, "executed_interventions": len(log), "sampled_interventions": len(interventions),
                        "feasible_set_size": len(feasible), "invisible_container_set_size": len(invisible), "window_frames": window_frames,
                        "containers_usable": len(usable), "containers_dropped": len(dropped), "containers_sealed": len(subjects),
                        "controls": len(control_ids), "controls_outside_U": controls["from_outside_U"], "controls_shortfall": controls["shortfall"],
                        "moves_executed": len(moves), "moves_source_first": moves_source_first,
                        "viewpoint_reselections": len(reselections), "sweep_two_actions": s2[1] - s2[0],
                        "window_protocol": ("two_segment_probe_pending_ruling_53" if window_segment else "whole_transition"),
                        "leave_segment_frames": tr[1] - tr[0], "window_segment": window_segment})
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
    ap.add_argument("--stage", choices=["s1-02a", "s1-02b", "regenerate", "window-probe"], default="s1-02a")
    ap.add_argument("--houses", default="",
                    help="regenerate: comma-separated house ids to rerun into --output-root; each one's old directory "
                         "must already have been moved aside (never overwritten) and the rerun must be named by a ruling")
    ap.add_argument("--ruling", default="",
                    help="regenerate: the user ruling that authorises rerunning these houses (e.g. D-224-S1 ruling 40)")
    ap.add_argument("--pilot-root", help="S1-02b: the finished S1-02a output root (occupancy receipt, pilot houses)")
    ap.add_argument("--development-houses", type=int, default=50)
    ap.add_argument("--resume", action="store_true",
                    help="S1-02b: skip houses with a receipt; mark interrupted dirs failed; never regenerate")
    ap.add_argument("--simulator-concurrency-limit", type=int, default=None,
                    help="S1-02b: the Unity concurrency assumed safe for the worker derivation when it exceeds "
                         "the pilot-verified count; the derivation still takes the minimum over CPU/RAM/VRAM/disk, "
                         "and the receipt records the assumption and is_extrapolation=true (S1-01 worker rule)")
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
    ap.add_argument("--dry-run-destinations-per-object", type=int, default=DRY_RUN_DESTINATIONS_PER_OBJECT,
                    help="ruling 39: U destinations tested per candidate object, drawn by the seeded RNG; "
                         "0 tests every destination and only replays the S1 runs (c222c51/a397d16)")
    ap.add_argument("--placement-prescreen", choices=["spawn_points", "dry_run"], default="dry_run",
                    help="rulings 31/32: real placement + viewpoint peek + revert during the window, one placement per destination")
    ap.add_argument("--destination-points", choices=["anywhere", "top", "verified"], default="anywhere",
                    help="kept for the smoke record; dry_run supersedes it")
    ap.add_argument("--window-segment-frames", type=int, default=0,
                    help="window-probe only (pending ruling 53): after the transition walk exactly this many actions "
                         "towards the farthest cell and compute U on that segment; 0 = the frozen whole-transition rule")
    ap.add_argument("--probe-note", default="",
                    help="window-probe: who authorised the probe and what it estimates; written to the plan and receipt")
    ap.add_argument("--private-salt-file", required=True,
                    help="ruling 37: a file outside the repository holding the private salt mixed into the "
                         "null-window draw; only its sha256 is written to plan.json and the receipts")
    args = ap.parse_args()
    args.private_salt = _read_private_salt(args.private_salt_file)
    if args.stage == "s1-02b":
        return main_s1_02b(args)
    if args.stage == "regenerate":
        return main_regenerate(args)
    if args.stage == "window-probe":
        return main_window_probe(args)
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
    (out_root / "plan.json").write_text(json.dumps({"selected": selected, "split": freeze, "commit": commit, "pool_size": len(pool),
                                                    "null_window_salt_sha256": sha_bytes(args.private_salt.encode("utf-8"))}, indent=1))
    tasks = [{"house_id": h, "index": int(h.rsplit("-", 1)[1]), "out": str(out_root / h), "source_root": str(source.parent),
              "source_rel": source.name, "split_seed": freeze["seed"], "commit": commit, "private_salt": args.private_salt,
              "replan_blocked_edges": args.replan_blocked_edges, "placement_tries": args.placement_tries, "stratify_by_kind": args.stratify_by_kind, "add_source": args.add_source, "destination_points": args.destination_points, "placement_prescreen": args.placement_prescreen, "dry_run_destinations_per_object": args.dry_run_destinations_per_object} for h in selected]
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


def _read_private_salt(path: str) -> str:
    """The private null-window salt (ruling 37).  Lives outside the repository; never printed."""

    p = Path(path).resolve()
    if ROOT in p.parents:
        raise SystemExit("the private salt must not live inside the repository")
    salt = p.read_text(encoding="utf-8").strip()
    if len(salt) < 32:
        raise SystemExit("the private salt must be at least 32 characters")
    return salt


def _collect_house_receipts(out_root: Path) -> list[dict[str, Any]]:
    return sorted((json.loads(p.read_text(encoding="utf-8")) for p in out_root.glob("procthor10k-*/receipt.json")),
                  key=lambda r: r["house_id"])


def main_regenerate(args: argparse.Namespace) -> int:
    """Rerun named houses of an existing output root under a user ruling, then rewrite the stage receipt.

    白话（裁决 40）：用户把 `maximum_actions` 从 2000 改到 4000 并裁定"只重生成触顶失败的 house"。
    这个入口只做这一件事：被点名的 house 的旧目录必须已经被移走（不覆盖），按当前提交重跑它们，
    然后把该输出根下现有的全部逐 house 回执重新汇总成阶段回执。占用回执（S1-02a）不重算——它是
    在 4 路并发下量的，单独重跑一条不是同一个测量。回执里同时记下所有出现过的代码提交，
    以及本次是按哪条裁决重生成了哪些 house，旧目录在哪。它不是"重试到好为止"：名单来自裁决，
    不来自结果。
    """

    houses = [h for h in args.houses.split(",") if h]
    if not houses or not args.ruling:
        print("regenerate needs --houses and --ruling"); return 2
    out_root = Path(args.output_root)
    contract = json.loads(CONTRACT_S1_02A.read_text(encoding="utf-8"))
    lean_pilot.validate_pilot_contract(contract)
    freeze = contract["split_freeze"]
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    source = Path(args.source)
    stage_receipt = None
    for name in ("pilot_receipt.json", "s1_02b_receipt.json"):
        if (out_root / name).exists():
            stage_receipt = name
    if stage_receipt is None:
        print("no stage receipt under the output root; refusing"); return 2
    for h in houses:
        if (out_root / h).exists():
            print(f"{h}: directory still present under the output root; move it aside first, never overwrite"); return 3
    tasks = [{"house_id": h, "index": int(h.rsplit("-", 1)[1]), "out": str(out_root / h), "source_root": str(source.parent),
              "source_rel": source.name, "split_seed": freeze["seed"], "commit": commit, "private_salt": args.private_salt,
              "replan_blocked_edges": args.replan_blocked_edges, "placement_tries": args.placement_tries,
              "stratify_by_kind": args.stratify_by_kind, "add_source": args.add_source,
              "destination_points": args.destination_points, "placement_prescreen": args.placement_prescreen, "dry_run_destinations_per_object": args.dry_run_destinations_per_object} for h in houses]
    t0 = time.time()
    fresh = _run_with_timeout(tasks, max(1, min(args.workers or 1, len(tasks))), args.stall_timeout_s, commit)
    wall = time.time() - t0
    results = _collect_house_receipts(out_root)
    failed = [r for r in results if r["status"] != "succeeded"]
    record = {"ruling": args.ruling, "code_commit": commit, "houses": houses,
              "results": [{"house_id": r["house_id"], "status": r["status"], "reason": r.get("reason"),
                           "detail": (r.get("detail") or "")[:300], "executed_interventions": r.get("executed_interventions")} for r in fresh],
              "wall_clock_seconds": round(wall, 1), "code_commits_now_present": sorted({r.get("code_commit") for r in results})}
    (out_root / f"regenerate-{commit[:7]}.json").write_text(json.dumps(record, indent=1))
    receipt = json.loads((out_root / stage_receipt).read_text(encoding="utf-8"))
    if stage_receipt == "pilot_receipt.json":
        # the field set is fixed by the S1-02a contract; only the outcome fields move, code_commit
        # stays the commit of the original run and regenerate-<commit>.json carries the second one
        receipt.update({"succeeded": len(results) - len(failed), "failed": len(failed),
                        "failure_receipts": [{"house_id": r["house_id"], "reason": r["reason"], "detail": r.get("detail", "")[:400]} for r in failed],
                        "exit_codes": [0 if r["status"] == "succeeded" else 1 for r in results]})
        lean_pilot.validate_pilot_receipt(receipt)
    else:
        non_null = [r for r in results if not r.get("null_window", False)]
        ok_non_null = [r for r in non_null if r["status"] == "succeeded" and r.get("executed_interventions", 0) >= 1]
        yield_rate = (len(ok_non_null) / len(non_null)) if non_null else None
        moves = sum(int(r.get("moves_executed") or 0) for r in results)
        moves_first = sum(int(r.get("moves_source_first") or 0) for r in results)
        receipt.update({"succeeded": len(results) - len(failed), "failed": len(failed),
                        "failure_receipts": [{"house_id": r["house_id"], "reason": r["reason"], "detail": r.get("detail", "")[:400]} for r in failed],
                        "null_window_episodes": len(results) - len(non_null),
                        "null_window_failed": len([r for r in results if r.get("null_window", False) and r["status"] != "succeeded"]),
                        "yield_house_level_non_null": yield_rate, "yield_gate_passed": (yield_rate is not None and yield_rate >= 0.6),
                        "moves_executed": moves, "moves_source_first": moves_first,
                        "move_minimum": check_move_minimum(moves, moves_first, is_train_block=False),
                        "controls_total": sum(int(r.get("controls") or 0) for r in results),
                        "controls_outside_U": sum(int(r.get("controls_outside_U") or 0) for r in results),
                        "code_commits": sorted({r.get("code_commit") for r in results}),
                        "regenerated": {"ruling": args.ruling, "houses": houses, "code_commit": commit}})
    (out_root / stage_receipt).write_text(json.dumps(receipt, indent=1))
    print(json.dumps({"regenerate": record, "stage_receipt": {k: v for k, v in receipt.items() if k not in ("failure_receipts",)}}, indent=1, default=str))
    return 0 if not [r for r in fresh if r["status"] != "succeeded"] else 1


def main_window_probe(args: argparse.Namespace) -> int:
    """Run named houses under the pending-ruling-53 two-segment window and write an estimate receipt.

    白话：用户 2026-09-23 说"先别生成 50 条，先跑前几条看看效果估算一下"。这个入口只跑点名的几栋
    house，过渡之后再走恰好 L 步作窗口段（见 `_walk_window_segment`），其余流程（封印、U、dry-run、
    抽样、对照、扫掠二）与 S1-02 完全相同，然后把每栋的 U、可行集、执行的干预、move、U 内对照和
    两段帧数汇总成 `window_probe_receipt.json`。输出根必须是新的；产物不是 S1-02 数据：S0-02 合同
    的窗口定义没有改，S1-03 合同的提交登记表也不含本提交，所以任何读者都会拒绝把它当开发数据。
    它不算成品率门、不重算占用回执，也不是裁决 53 的批准。
    """

    houses = [h for h in args.houses.split(",") if h]
    if not houses or args.window_segment_frames <= 0 or not args.probe_note:
        print("window-probe needs --houses, --window-segment-frames > 0 and --probe-note"); return 2
    out_root = Path(args.output_root)
    if out_root.exists() and any(out_root.glob("procthor10k-*")):
        print("output root already holds houses; refusing (a probe never overwrites)"); return 3
    out_root.mkdir(parents=True, exist_ok=True)
    contract = json.loads(CONTRACT_S1_02A.read_text(encoding="utf-8"))
    lean_pilot.validate_pilot_contract(contract)
    freeze = contract["split_freeze"]
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    source = Path(args.source)
    workers = max(1, min(args.workers or 1, len(houses)))
    plan = {"stage": "window-probe", "pending_ruling": "D-224-S1 ruling 53 (proposal, not approved)", "probe_note": args.probe_note,
            "window_segment_frames": args.window_segment_frames, "houses": houses, "commit": commit, "split": freeze,
            "requested_workers": args.workers, "actual_workers": workers,
            "not_s1_02_data": "S0-02 window rule unchanged; this commit is not in the S1-03 encoder registry, readers refuse it",
            "null_window_salt_sha256": sha_bytes(args.private_salt.encode("utf-8"))}
    (out_root / "window_probe_plan.json").write_text(json.dumps(plan, indent=1))
    tasks = [{"house_id": h, "index": int(h.rsplit("-", 1)[1]), "out": str(out_root / h), "source_root": str(source.parent),
              "source_rel": source.name, "split_seed": freeze["seed"], "commit": commit, "private_salt": args.private_salt,
              "replan_blocked_edges": args.replan_blocked_edges, "placement_tries": args.placement_tries,
              "stratify_by_kind": args.stratify_by_kind, "add_source": args.add_source,
              "destination_points": args.destination_points, "placement_prescreen": args.placement_prescreen,
              "dry_run_destinations_per_object": args.dry_run_destinations_per_object,
              "window_segment_frames": args.window_segment_frames} for h in houses]
    t0 = time.time()
    fresh = _run_with_timeout(tasks, workers, args.stall_timeout_s, commit)
    wall = time.time() - t0
    results = sorted(fresh, key=lambda r: r["house_id"])
    keys = ("house_id", "status", "reason", "detail", "null_window", "invisible_container_set_size", "feasible_set_size",
            "eligible_object_count", "containers_usable", "containers_sealed", "window_frames", "leave_segment_frames",
            "window_segment", "executed_interventions", "executed_kinds", "moves_executed", "moves_source_first",
            "controls", "controls_outside_U", "controls_shortfall", "observations", "actions")
    rows = [{k: r.get(k) for k in keys} for r in results]
    for row in rows:
        row["detail"] = (row.get("detail") or "")[:300]
        row["wall_seconds"] = round(float((r := next(x for x in results if x["house_id"] == row["house_id"]))["occupancy"]["wall_seconds"]), 1)
        row["controls_from_U"] = (None if row["controls"] is None else int(row["controls"]) - int(row["controls_outside_U"] or 0))
    ok = [r for r in results if r["status"] == "succeeded"]
    kinds: dict[str, int] = {}
    for r in ok:
        for k, v in (r.get("executed_kinds") or {}).items():
            kinds[k] = kinds.get(k, 0) + int(v)
    reasons: dict[str, int] = {}
    for r in results:
        if r["status"] != "succeeded":
            reasons[r.get("reason") or "unknown"] = reasons.get(r.get("reason") or "unknown", 0) + 1
    non_null = [r for r in results if not r.get("null_window", False)]
    summary = {"houses": len(results), "succeeded": len(ok), "failed": len(results) - len(ok), "failures_by_reason": reasons,
               "null_window_episodes": len(results) - len(non_null),
               "non_null_with_interventions": sum(1 for r in non_null if r["status"] == "succeeded" and (r.get("executed_interventions") or 0) >= 1),
               "non_null_total": len(non_null),
               "U_sizes": [r.get("invisible_container_set_size") for r in results],
               "feasible_sizes": [r.get("feasible_set_size") for r in results],
               "executed_kinds": kinds, "moves_executed": sum(int(r.get("moves_executed") or 0) for r in ok),
               "moves_source_first": sum(int(r.get("moves_source_first") or 0) for r in ok),
               "controls_total": sum(int(r.get("controls") or 0) for r in ok),
               "controls_outside_U": sum(int(r.get("controls_outside_U") or 0) for r in ok),
               "window_frames": [r.get("window_frames") for r in results],
               "leave_segment_frames": [r.get("leave_segment_frames") for r in results],
               "wall_clock_seconds": round(wall, 1), "actual_workers": workers, "code_commit": commit}
    (out_root / "window_probe_receipt.json").write_text(json.dumps({"plan": plan, "summary": summary, "houses": rows}, indent=1))
    print(json.dumps({"summary": summary, "houses": rows}, indent=1, default=str))
    return 0 if len(ok) == len(results) else 1


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
    verified_limit = occupancy["simulator_concurrency_limit"]
    if args.simulator_concurrency_limit is not None:
        # the pilot only proves that its own worker count runs; a larger assumed limit is an
        # extrapolation from single-worker cost and is recorded as one, never quietly lowered later
        occupancy["simulator_concurrency_limit"] = max(int(args.simulator_concurrency_limit), 1)
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
    if pilot_plan.get("null_window_salt_sha256") != sha_bytes(args.private_salt.encode("utf-8")):
        print("the private salt differs from the pilot's; refusing"); return 2
    houses = block[lean_pilot.PILOT_TOTAL_HOUSES:args.development_houses]
    out_root = Path(args.output_root); out_root.mkdir(parents=True, exist_ok=True)
    # a resumed run must not overwrite the first run's plan (its commit, measurements and GPU are
    # evidence); it writes its own plan file next to it
    plan_name = f"plan.resume-{commit[:7]}.json" if (args.resume and (out_root / "plan.json").exists()) else "plan.json"
    (out_root / plan_name).write_text(json.dumps({"stage": "s1-02b", "houses": houses, "pilot_root": str(pilot_root),
                                                    "derived": scale, "requested_workers": workers, "measurements": measurements,
                                                    "simulator_concurrency_limit_verified": verified_limit,
                                                    "simulator_concurrency_limit_assumed": occupancy["simulator_concurrency_limit"],
                                                    "commit": commit, "null_window_salt_sha256": sha_bytes(args.private_salt.encode("utf-8"))}, indent=1))
    tasks = [{"house_id": h, "index": int(h.rsplit("-", 1)[1]), "out": str(out_root / h), "source_root": str(source.parent),
              "source_rel": source.name, "split_seed": freeze["seed"], "commit": commit, "private_salt": args.private_salt,
              "replan_blocked_edges": args.replan_blocked_edges, "placement_tries": args.placement_tries, "stratify_by_kind": args.stratify_by_kind, "add_source": args.add_source, "destination_points": args.destination_points, "placement_prescreen": args.placement_prescreen, "dry_run_destinations_per_object": args.dry_run_destinations_per_object} for h in houses]
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
    null_failed = [r for r in results if r.get("null_window", False) and r["status"] != "succeeded"]
    moves = sum(int(r.get("moves_executed") or 0) for r in results)
    moves_first = sum(int(r.get("moves_source_first") or 0) for r in results)
    receipt = {
        "stage": "s1-02b", "code_commit": commit, "houses_planned": len(houses), "succeeded": len(results) - len(failed),
        "failed": len(failed), "failure_receipts": [{"house_id": r["house_id"], "reason": r["reason"], "detail": r.get("detail", "")[:400]} for r in failed],
        "null_window_episodes": len(results) - len(non_null), "null_window_failed": len(null_failed),
        "yield_house_level_non_null": yield_rate,
        "moves_executed": moves, "moves_source_first": moves_first,
        "move_minimum": check_move_minimum(moves, moves_first, is_train_block=False),
        "controls_total": sum(int(r.get("controls") or 0) for r in results),
        "controls_outside_U": sum(int(r.get("controls_outside_U") or 0) for r in results),
        "null_window_salt_sha256": sha_bytes(args.private_salt.encode("utf-8")),
        "yield_gate": s1_01 and json.loads(CONTRACT_S0_02.read_text(encoding="utf-8"))["intervention_window"]["minimum_yield"],
        "yield_gate_passed": (yield_rate is not None and yield_rate >= 0.6),
        "options": {"replan_blocked_edges": args.replan_blocked_edges, "placement_tries": args.placement_tries, "stratify_by_kind": args.stratify_by_kind, "add_source": args.add_source, "destination_points": args.destination_points, "placement_prescreen": args.placement_prescreen, "dry_run_destinations_per_object": args.dry_run_destinations_per_object},
        "requested_workers": workers, "actual_workers": workers, "derived_worker_count": scale["worker_count"],
        "binding_constraint": scale["binding_constraint"], "concurrency_verified_at": scale["concurrency_verified_at"],
        "simulator_concurrency_limit_verified": verified_limit,
        "simulator_concurrency_limit_assumed": occupancy["simulator_concurrency_limit"],
        "is_extrapolation": scale["is_extrapolation"], "wall_clock_seconds": round(wall, 1),
        "development_total_with_pilot": len(houses) + lean_pilot.PILOT_TOTAL_HOUSES,
    }
    (out_root / "s1_02b_receipt.json").write_text(json.dumps(receipt, indent=1))
    print(json.dumps({"receipt": receipt, "per_house": results}, indent=1, default=str))
    return 0 if receipt["yield_gate_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
