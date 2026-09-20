"""Read-only simulator probe: why an `add` (SpawnAsset duplicate) is never seen in sweep two.

白话：S1-02b 里 81 个执行"成功"的 `add`，在扫掠二的私有实例分割里全部是 0 像素
（pilot 的 6 个也是）。本探测在一个 house 上用新控制器逐步核对：SpawnAsset 报成功
后，复制件到底有没有进入元数据、它的 objectId 是什么、位置在哪、几步物理之后
还在不在、从目的容器的视点看能不能分割出来；并比较 `anywhere=True/False` 两种
预筛点。输出 JSON 报告；不写数据集，不改合同。它不证明其他动作类型的可辨性。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
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


def _mask_keys(event: Any) -> dict[str, int]:
    return {k: int(np.asarray(m).sum()) for k, m in (event.instance_masks or {}).items()}


def _find(meta: dict[str, Any], object_id: str) -> dict[str, Any] | None:
    return next((o for o in meta["objects"] if o["objectId"] == object_id), None)


def probe(upgraded: dict[str, Any], object_id: str, destination: str, anywhere: bool) -> dict[str, Any]:
    r: dict[str, Any] = {"object_id": object_id, "destination": destination, "anywhere": anywhere}
    c = None
    try:
        c = _controller(upgraded)
        meta = c.last_event.metadata
        src = _find(meta, object_id); dst = _find(meta, destination)
        if src is None or dst is None:
            return {**r, "exception": f"missing: src={src is None} dst={dst is None}"}
        r["asset_id"] = src.get("assetId")
        r["destination_openable"] = dst.get("openable"); r["destination_isOpen"] = dst.get("isOpen")
        ev = c.step(action="GetSpawnCoordinatesAboveReceptacle", objectId=destination, anywhere=anywhere)
        pts = ev.metadata.get("actionReturn") or []
        r["spawn_points"] = len(pts)
        if not pts:
            return r
        pt = pts[0]
        r["point"] = pt
        dbb = (dst.get("axisAlignedBoundingBox") or {})
        r["destination_bbox_center"] = dbb.get("center"); r["destination_bbox_size"] = dbb.get("size")
        # view before
        r["view"] = _teleport_to_view(c, dbb.get("center") or dst["position"])
        before_keys = _mask_keys(c.last_event)
        n_before = len(c.last_event.metadata["objects"])
        gid = "dup_probe_000000"
        t0 = time.time()
        ev = c.step(action="SpawnAsset", assetId=src.get("assetId"), generatedId=gid, position=pt, rotation={"x": 0, "y": 0, "z": 0})
        r["spawn"] = {"seconds": round(time.time() - t0, 3), "success": ev.metadata.get("lastActionSuccess"),
                      "error": (ev.metadata.get("errorMessage") or "")[:300], "actionReturn": ev.metadata.get("actionReturn")}
        objs = ev.metadata["objects"]
        r["objects_before_after"] = [n_before, len(objs)]
        new_ids = [o["objectId"] for o in objs if o["objectId"] not in {x["objectId"] for x in meta["objects"]}]
        r["new_object_ids"] = new_ids[:5]
        dup = _find(ev.metadata, gid) or (next((o for o in objs if o["objectId"] in new_ids), None))
        if dup is not None:
            r["dup"] = {"objectId": dup["objectId"], "assetId": dup.get("assetId"), "position": dup["position"],
                        "visible": dup.get("visible"), "parentReceptacles": dup.get("parentReceptacles"),
                        "isPickedUp": dup.get("isPickedUp")}
        after_keys = _mask_keys(ev)
        r["mask_keys_added_at_spawn"] = sorted(set(after_keys) - set(before_keys))
        r["dup_pixels_at_spawn"] = after_keys.get(gid, 0)
        # let physics settle, re-render from the same pose, then re-teleport to the viewpoint
        poses = []
        for _ in range(5):
            ev = c.step(action="Pass")
            d = _find(ev.metadata, gid)
            poses.append(d["position"] if d else None)
        r["dup_positions_after_5_pass"] = poses
        keys = _mask_keys(ev)
        r["mask_keys_added_after_pass"] = sorted(set(keys) - set(before_keys))
        r["dup_pixels_after_pass"] = keys.get(gid, 0)
        r["view_again"] = _teleport_to_view(c, dbb.get("center") or dst["position"])
        keys = _mask_keys(c.last_event)
        r["dup_pixels_from_viewpoint"] = keys.get(gid, 0)
        r["max_new_key_pixels_from_viewpoint"] = max([keys[k] for k in set(keys) - set(before_keys)] or [0])
        # also look straight at the spawn point from the nearest reachable cell
        r["view_point"] = _teleport_to_view(c, {"x": pt["x"], "y": pt["y"], "z": pt["z"]})
        keys = _mask_keys(c.last_event)
        r["dup_pixels_from_point_view"] = keys.get(gid, 0)
        r["new_keys_from_point_view"] = {k: keys[k] for k in set(keys) - set(before_keys)}
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
    ap.add_argument("--source", required=True)
    ap.add_argument("--house-index", type=int, required=True)
    ap.add_argument("--object-id", required=True)
    ap.add_argument("--destination", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    src = Path(args.source)
    house = house_loader.load_source_record(str(src.parent), {"relative_path": src.name, "index": args.house_index})
    upgraded = house_loader.upgrade_house_schema_v1(house, house_loader.load_pinned_asset_id_database())
    report = {"probe": "lean_s1_add_visibility_probe", "house_index": args.house_index,
              "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "trials": []}
    for anywhere in (True, False):
        t = probe(upgraded, args.object_id, args.destination, anywhere)
        report["trials"].append(t); print(json.dumps(t, default=str), flush=True)
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, default=str))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
