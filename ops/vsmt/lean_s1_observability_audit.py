"""Read-only audit: was every executed intervention observable in sweep two, and did every
control container re-show a seen, unchanged object?

白话：解决的问题是"干预执行成功"不等于"teacher 看得见"，以及"对照容器被重访"不等于
"重访时真的重新看见了没变的物体"。输入是一个阶段输出根（每个 house 的
provenance/interventions.json、route_stage1.json 和 private 帧记录），输出：
  * 每个执行的干预在扫掠一／扫掠二私有实例掩码里的最大像素，按 add／remove／move 判可辨
    （add／move 要在扫掠二某帧 ≥196 像素；remove 要在扫掠一 >0 像素且扫掠二每帧 0 像素）；
  * 每个对照容器（裁决 34）：它登记的已见物体里有几个在扫掠二 ≥196 像素；空窗口 episode 的
    "本该被干预"容器也按同样口径审计（什么都没动，物体应仍可见）。
例子：S1-02b 首跑 81 个 add 全部 0 像素（LOG-237），第二次重生成 78/78 可辨（LOG-238）。
它只读 private 与 provenance，不碰 public，不是模型或前端的结果。

Usage: python ops/vsmt/lean_s1_observability_audit.py <output_root> [report.json]
"""

import glob
import json
import os
import sys

MIN_PX = 196

root = sys.argv[1]
tot = {"add": [0, 0, 0], "remove": [0, 0, 0], "move": [0, 0, 0]}  # observable, weak(1..195), zero
ctrl_tot = {"controls": 0, "controls_with_a_seen_object_reobserved": 0, "control_objects": 0, "control_objects_reobserved": 0}
# a null episode kept its would-be sample and executed nothing, so in sweep two every object that
# would have been removed or moved must still be there.  An add destination has no such object --
# the would-be object sits elsewhere and is never placed -- so it is counted apart rather than
# scored against a denominator it cannot satisfy.
twin_tot = {"null_episodes": 0, "would_be_source_containers": 0, "would_be_sources_intact": 0,
            "would_be_source_objects": 0, "would_be_source_objects_reobserved": 0,
            "would_be_destination_containers_nothing_to_check": 0}
per_house = {}
dest_types = {}
for ip in sorted(glob.glob(os.path.join(root, "procthor10k-*/provenance/interventions.json"))):
    base = os.path.dirname(os.path.dirname(ip))
    h = base.rsplit("-", 1)[1]
    L = json.load(open(ip))
    ex = [e for e in L.get("executed", []) if e.get("executed")]
    r1 = json.load(open(os.path.join(base, "provenance", "route_stage1.json")))
    s1 = r1["segments"]["sweep_one"]; tr = r1["segments"]["transition"]
    frames = sorted(glob.glob(os.path.join(base, "private", "*.frame.json")))
    vis = {}
    for fp in frames:
        d = json.load(open(fp)); i = d["observation_index"]
        for oid, px in d["object_visibility"].items():
            a = vis.setdefault(oid, [0, 0])
            if i <= s1[1]:
                a[0] = max(a[0], px)
            elif i > tr[1]:
                a[1] = max(a[1], px)
    rows = []
    for e in ex:
        oid = (e.get("generated_id") or e["object_id"]) if e["kind"] == "add" else e["object_id"]
        one, two = vis.get(oid, [0, 0])
        dest = e.get("destination") or e.get("source") or ""
        dt = dest.split("|")[0]
        dest_types.setdefault(e["kind"], {}).setdefault(dt, [0, 0])
        if e["kind"] == "remove":
            cat = 0 if two == 0 and one > 0 else 2
        else:
            cat = 0 if two >= MIN_PX else (1 if two > 0 else 2)
        tot[e["kind"]][cat] += 1
        dest_types[e["kind"]][dt][0] += 1
        dest_types[e["kind"]][dt][1] += int(cat == 0)
        rows.append(f"{e['kind']}:{oid.split('|')[0][:12]}->{dt}[{one},{two}]")
    # ruling 34: controls must re-show an unchanged seen object
    controls = (L.get("controls") or {}).get("controls", [])
    crow = []
    for c in controls:
        seen = c.get("seen_objects", [])
        re = [o for o in seen if vis.get(o, [0, 0])[1] >= MIN_PX]
        ctrl_tot["controls"] += 1
        ctrl_tot["controls_with_a_seen_object_reobserved"] += int(bool(re))
        ctrl_tot["control_objects"] += len(seen)
        ctrl_tot["control_objects_reobserved"] += len(re)
        crow.append(f"ctrl:{c['container'].split('|')[0]}[{len(re)}/{len(seen)}]")
    # twin: a null episode kept its would-be sample; those containers were not touched
    twin_row = []
    if L.get("null_window"):
        twin_tot["null_episodes"] += 1
        sources, destinations = {}, set()
        for row in L.get("sampled", []):
            if row["kind"] in ("remove", "move") and row.get("source"):
                sources.setdefault(row["source"], set()).add(row["object_id"])
            if row["kind"] in ("add", "move") and row.get("destination"):
                destinations.add(row["destination"])
        for cont, objs in sorted(sources.items()):
            back = [o for o in objs if vis.get(o, [0, 0])[1] >= MIN_PX]
            twin_tot["would_be_source_containers"] += 1
            twin_tot["would_be_sources_intact"] += int(bool(back))
            twin_tot["would_be_source_objects"] += len(objs)
            twin_tot["would_be_source_objects_reobserved"] += len(back)
            twin_row.append(f"twin_src:{cont.split('|')[0]}[{len(back)}/{len(objs)}]")
        for cont in sorted(destinations - set(sources)):
            twin_tot["would_be_destination_containers_nothing_to_check"] += 1
            twin_row.append(f"twin_dst:{cont.split('|')[0]}[-]")
    print(h, ("NULL " if L.get("null_window") else ""), " ".join(rows + crow + twin_row))
    per_house[h] = {"null_window": bool(L.get("null_window")), "interventions": rows, "controls": crow, "twin": twin_row}
print("TOTAL kind:[observable(>=196 px in sweep two; remove: 0 px in two and >0 in one), weak(1..195), unobservable]", json.dumps(tot))
print("CONTROLS", json.dumps(ctrl_tot))
print("TWIN (null episodes: would-be sources must still hold their object; would-be destinations have nothing to check)",
      json.dumps(twin_tot))
print("BY DESTINATION TYPE kind -> {type: [count, observable]}", json.dumps(dest_types))
if len(sys.argv) > 2:
    json.dump({"schema_version": "vsmt-lean-s1-observability-audit-v2", "output_root": root, "totals": tot,
               "controls": ctrl_tot, "twin": twin_tot, "by_destination_type": dest_types, "per_house": per_house},
              open(sys.argv[2], "w"), indent=1)
    print("wrote", sys.argv[2])
