"""Read-only audit: was every executed intervention observable in sweep two?

白话：解决的问题是"干预执行成功"不等于"teacher 看得见"。输入是一个阶段输出根
（每个 house 的 provenance/interventions.json、route_stage1.json 和 private 帧记录），
输出每个干预在扫掠一／扫掠二私有实例掩码里的最大像素，并按 add／remove／move 判
可辨：add／move 要在扫掠二某帧 ≥196 像素；remove 要在扫掠一 >0 像素且扫掠二每帧
0 像素。例子：S1-02b 首跑 81 个 add 全部 0 像素（LOG-237），重生成后 78/78 可辨。
它只读 private 与 provenance，不碰 public，不是模型或前端的结果。

Usage: python ops/vsmt/lean_s1_observability_audit.py <output_root> [report.json]
"""

import glob
import json
import os
import sys

root = sys.argv[1]
tot = {"add": [0, 0, 0], "remove": [0, 0, 0], "move": [0, 0, 0]}  # observable, weak(1..195), zero
per_house = {}
dest_types = {}
for ip in sorted(glob.glob(os.path.join(root, "procthor10k-*/provenance/interventions.json"))):
    base = os.path.dirname(os.path.dirname(ip))
    h = base.rsplit("-", 1)[1]
    L = json.load(open(ip))
    ex = [e for e in L.get("executed", []) if e.get("executed")]
    if not ex:
        continue
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
        after = two if e["kind"] != "remove" else one  # the pixel count that should be > 0
        obs = two if e["kind"] in ("add", "move") else (0 if two == 0 else -1)
        if e["kind"] == "remove":
            cat = 0 if two == 0 and one > 0 else 2
        else:
            cat = 0 if two >= 196 else (1 if two > 0 else 2)
        tot[e["kind"]][cat] += 1
        dest_types[e["kind"]][dt][0] += 1
        dest_types[e["kind"]][dt][1] += int(cat == 0)
        rows.append(f"{e['kind']}:{oid.split('|')[0][:12]}->{dt}[{one},{two}]")
    print(h, " ".join(rows))
    per_house[h] = rows
print("TOTAL kind:[observable(>=196 px in sweep two; remove: 0 px in two and >0 in one), weak(1..195), unobservable]", json.dumps(tot))
print("by destination type kind->{type:[n, observable]}", json.dumps(dest_types))
if len(sys.argv) > 2:
    json.dump({"schema_version": "vsmt-lean-s1-observability-audit-v1", "output_root": root,
               "definition": {"observable": "affected object has >= 196 px in some sweep-two private mask (add/move); remove: 0 px in every sweep-two mask and > 0 px in sweep one",
                              "weak": "1..195 px in sweep two", "unobservable": "0 px in sweep two (add/move) or still visible (remove)"},
               "totals_by_kind_observable_weak_unobservable": tot, "by_destination_type": dest_types,
               "per_house": per_house}, open(sys.argv[2], "w"), indent=1)
