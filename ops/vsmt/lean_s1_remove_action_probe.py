"""Read-only simulator probe: why `remove` and `move` never execute in S1-02b.

白话：S1-02b 里每个抽到 `remove` 的 house 都在 `RemoveFromScene` 上让模拟器超时
（Unity 日志显示 NullReferenceException 出现在删除后生成元数据时），抽到 `move`
的 house 在 `PlaceObjectAtPoint` 的第一个候选点上报"spawn area not clear"。
本探测在一个已失败的 house 上用新的控制器分别验证：

  A. 复现：对同一物体执行 RemoveFromScene，记录异常类型与耗时；
  B. 替代：DisableObject 是否成功、之后元数据是否仍健康（连续步进）、
     物体在私有实例分割里的像素是否从 >0 变为 0（视觉上确实消失）、
     EnableObject 能否恢复（仅记录，不用于数据）；
  C. 放置：对若干容器，把同一物体依次放到 GetSpawnCoordinatesAboveReceptacle
     返回的前 N 个点，记录第几个点成功。

输出一份 JSON 报告到 --out；不写任何数据集产物，不改任何合同值。
它不是数据生成，也不证明干预在公开 RGB 上可辨。
"""

from __future__ import annotations

import argparse
import json
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

from vsmt import lean_route  # noqa: E402
import vm04_two_house_worker as house_loader  # noqa: E402

WIDTH = HEIGHT = 224
FOV = 90.0


def _controller(upgraded: dict[str, Any]) -> Any:
    from ai2thor.controller import Controller
    from ai2thor.platform import CloudRendering

    c = Controller(platform=CloudRendering, scene=upgraded, width=WIDTH, height=HEIGHT, fieldOfView=FOV,
                   gridSize=0.25, snapToGrid=True, rotateStepDegrees=90, renderDepthImage=True,
                   renderInstanceSegmentation=True)
    house_loader.bootstrap_house_agent(c, upgraded)
    return c


def _pixels(event: Any, object_id: str) -> int:
    masks = event.instance_masks or {}
    m = masks.get(object_id)
    return int(np.asarray(m).sum()) if m is not None else 0


def _teleport_to_view(controller: Any, target: dict[str, float]) -> dict[str, Any]:
    reach = controller.step(action="GetReachablePositions").metadata["actionReturn"]
    cells = lean_route.reachable_cells(reach)
    cam_h = float(controller.last_event.metadata["cameraPosition"]["y"])
    vp = lean_route.select_viewpoint(target, cells, camera_height_m=cam_h)
    pos = {"x": vp["cell"][0] * lean_route.GRID_M, "y": controller.last_event.metadata["agent"]["position"]["y"],
           "z": vp["cell"][1] * lean_route.GRID_M}
    ev = controller.step(action="Teleport", position=pos, rotation={"x": 0, "y": vp["yaw"], "z": 0}, horizon=vp["pitch"],
                         standing=True, forceAction=True)
    return {"viewpoint": vp, "teleport_ok": ev.metadata.get("lastActionSuccess")}


def _find(meta: dict[str, Any], object_id: str) -> dict[str, Any] | None:
    return next((o for o in meta["objects"] if o["objectId"] == object_id), None)


def _healthy_steps(controller: Any, n: int = 12) -> dict[str, Any]:
    t0 = time.time(); ok = 0
    for a in (["RotateRight", "MoveAhead", "RotateLeft"] * n)[:n]:
        ev = controller.step(action=a)
        ok += int(bool(ev.metadata.get("objects")))
    return {"steps": n, "metadata_present": ok, "seconds": round(time.time() - t0, 2)}


def trial_remove(upgraded: dict[str, Any], object_id: str) -> dict[str, Any]:
    r: dict[str, Any] = {"action": "RemoveFromScene", "object_id": object_id}
    c = None
    t0 = time.time()
    try:
        c = _controller(upgraded)
        t0 = time.time()
        ev = c.step(action="RemoveFromScene", objectId=object_id)
        r.update({"seconds": round(time.time() - t0, 2), "success": ev.metadata.get("lastActionSuccess"),
                  "error": (ev.metadata.get("errorMessage") or "")[:300],
                  "still_listed": _find(ev.metadata, object_id) is not None})
        r["after"] = _healthy_steps(c)
    except Exception as exc:  # noqa: BLE001
        r.update({"seconds": round(time.time() - t0, 2), "exception": repr(exc)[:400]})
    finally:
        if c is not None:
            try:
                c.stop()
            except Exception:  # noqa: BLE001
                pass
    return r


def trial_disable(upgraded: dict[str, Any], object_id: str) -> dict[str, Any]:
    r: dict[str, Any] = {"action": "DisableObject", "object_id": object_id}
    c = None
    try:
        c = _controller(upgraded)
        obj = _find(c.last_event.metadata, object_id)
        if obj is None:
            return {**r, "exception": "object not in metadata"}
        r["view"] = _teleport_to_view(c, obj["position"])
        r["pixels_before"] = _pixels(c.last_event, object_id)
        t0 = time.time()
        ev = c.step(action="DisableObject", objectId=object_id)
        r.update({"seconds": round(time.time() - t0, 2), "success": ev.metadata.get("lastActionSuccess"),
                  "error": (ev.metadata.get("errorMessage") or "")[:300]})
        after = _find(ev.metadata, object_id)
        r["still_listed"] = after is not None
        r["listed_visible"] = after.get("visible") if after else None
        r["pixels_after"] = _pixels(ev, object_id)
        # a Pass re-renders from the same pose without moving
        ev2 = c.step(action="Pass")
        r["pixels_after_pass"] = _pixels(ev2, object_id)
        r["health"] = _healthy_steps(c)
        r["reachable_ok"] = bool(c.step(action="GetReachablePositions").metadata.get("actionReturn"))
        ev3 = c.step(action="EnableObject", objectId=object_id)
        r["enable_success"] = ev3.metadata.get("lastActionSuccess")
        r["view_back"] = _teleport_to_view(c, obj["position"])
        r["pixels_after_enable"] = _pixels(c.last_event, object_id)
    except Exception as exc:  # noqa: BLE001
        r["exception"] = repr(exc)[:400]; r["traceback"] = traceback.format_exc()[-800:]
    finally:
        if c is not None:
            try:
                c.stop()
            except Exception:  # noqa: BLE001
                pass
    return r


def trial_place(upgraded: dict[str, Any], object_id: str, max_points: int, max_containers: int) -> dict[str, Any]:
    r: dict[str, Any] = {"action": "PlaceObjectAtPoint", "object_id": object_id, "containers": []}
    c = None
    try:
        c = _controller(upgraded)
        meta = c.last_event.metadata
        receptacles = [o["objectId"] for o in meta["objects"] if o.get("receptacle") and not o.get("pickupable")]
        for cid in sorted(receptacles)[:max_containers]:
            ev = c.step(action="GetSpawnCoordinatesAboveReceptacle", objectId=cid, anywhere=True)
            pts = ev.metadata.get("actionReturn") or []
            row = {"container": cid, "points": len(pts), "tries": []}
            for n, pt in enumerate(pts[:max_points], start=1):
                ev = c.step(action="PlaceObjectAtPoint", objectId=object_id, position=pt)
                ok = ev.metadata.get("lastActionSuccess") is True
                row["tries"].append({"n": n, "ok": ok, "error": (ev.metadata.get("errorMessage") or "")[:120]})
                if ok:
                    row["first_success"] = n
                    break
            r["containers"].append(row)
    except Exception as exc:  # noqa: BLE001
        r["exception"] = repr(exc)[:400]
    finally:
        if c is not None:
            try:
                c.stop()
            except Exception:  # noqa: BLE001
                pass
    return r


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--source", required=True, help="train.jsonl.gz")
    ap.add_argument("--house-index", type=int, required=True)
    ap.add_argument("--object-id", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--skip-remove", action="store_true", help="skip trial A (100 s simulator timeout)")
    ap.add_argument("--max-points", type=int, default=8)
    ap.add_argument("--max-containers", type=int, default=4)
    args = ap.parse_args()
    src = Path(args.source)
    house = house_loader.load_source_record(str(src.parent), {"relative_path": src.name, "index": args.house_index})
    upgraded = house_loader.upgrade_house_schema_v1(house, house_loader.load_pinned_asset_id_database())
    report: dict[str, Any] = {"probe": "lean_s1_remove_action_probe", "house_index": args.house_index,
                              "object_id": args.object_id, "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    if not args.skip_remove:
        report["A_remove"] = trial_remove(upgraded, args.object_id); print(json.dumps(report["A_remove"]), flush=True)
    report["B_disable"] = trial_disable(upgraded, args.object_id); print(json.dumps(report["B_disable"]), flush=True)
    report["C_place"] = trial_place(upgraded, args.object_id, args.max_points, args.max_containers)
    print(json.dumps(report["C_place"]), flush=True)
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
