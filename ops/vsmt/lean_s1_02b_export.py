"""Export an S1-02a/S1-02b output root as a small `results/*.json` report.

白话：解决的问题是服务器上的 `outputs/` 不进 Git，本地没法读结果。输入是一个
阶段输出根目录（含顶层回执和每个 house 的 `receipt.json`），输出是一份带
schema 版本、代码 commit、回执摘要和逐 house 行的 JSON，放进 `results/`，可以
提交、可以本地读。例子：46 个 house 的 S1-02b 跑完后导出成品率、失败分类、
每个 house 的 U／F／抽样类型／执行成功类型。

它不是数据导出：不含任何帧、掩码、私有实例 ID 或资产；也不重新计算任何指标，
只是把已经写死在回执里的数字汇总搬运出来。成品率按顶层回执原样引用，不重算。
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "vsmt-lean-s1-02b-report-v2"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _house_rows(root: Path) -> list[dict[str, Any]]:
    rows = []
    for receipt_path in sorted(root.glob("procthor10k-*/receipt.json")):
        d = json.loads(receipt_path.read_text(encoding="utf-8"))
        base = receipt_path.parent
        row: dict[str, Any] = {
            "house_id": d["house_id"], "source_index": d["source_index"], "status": d["status"],
            "reason": d.get("reason"), "detail": (d.get("detail") or "").replace("\n", " ")[:400],
            "null_window": d.get("null_window"),
            "invisible_container_set_size": d.get("invisible_container_set_size"),
            "feasible_set_size": d.get("feasible_set_size"),
            "observations": d.get("observations"), "window_frames": d.get("window_frames"),
            "containers_usable": d.get("containers_usable"), "containers_dropped": d.get("containers_dropped"),
            "wall_seconds": round(float(d["occupancy"]["wall_seconds"]), 1),
            "peak_rss_gb": d["occupancy"].get("peak_rss_gb"),
            "bytes_written": d["occupancy"].get("bytes_written"),
            "receipt_sha256": _sha256(receipt_path),
        }
        log_path = base / "provenance" / "interventions.json"
        sampled = collections.Counter()
        executed = collections.Counter()
        twin = collections.Counter()
        if log_path.exists():
            log = json.loads(log_path.read_text(encoding="utf-8"))
            for item in log.get("executed", []):
                sampled[item["kind"]] += 1
                if item.get("executed"):
                    executed[item["kind"]] += 1
            for item in log.get("sampled", []):
                twin[item["kind"]] += 1
            row["eligible_object_count"] = log.get("eligible_object_count")
            controls = log.get("controls") or {}
            row["controls"] = [c["container"] for c in controls.get("controls", [])]
            row["controls_from_U"] = controls.get("from_U")
            row["controls_outside_U"] = controls.get("from_outside_U")
            row["controls_shortfall"] = controls.get("shortfall")
            row["moves_executed"] = log.get("moves_executed")
            sampled_path = base / "provenance" / "interventions_sampled.json"
            if sampled_path.exists():
                smp = json.loads(sampled_path.read_text(encoding="utf-8"))
                for key in ("dry_run_pairs_tested", "dry_run_pairs_total", "dry_run_destinations_per_object", "feasible_set_size_estimate"):
                    row[key] = smp.get(key)
            row["moves_source_first"] = log.get("moves_source_first")
        row["sampled_kinds"] = dict(sampled)
        row["executed_kinds"] = dict(executed)
        row["twin_sampled_kinds"] = dict(twin)   # ruling 34: a null episode keeps its would-be sample
        for key in ("containers_sealed", "controls_outside_U", "viewpoint_reselections", "sweep_two_actions", "null_window_salt_sha256"):
            if key in d and key not in row:
                row[key] = d.get(key)
        rows.append(row)
    return rows


def build_report(root: Path, stage_receipt_name: str) -> dict[str, Any]:
    receipt_path = root / stage_receipt_name
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    rows = _house_rows(root)
    by_reason = collections.Counter(r["reason"] for r in rows if r["status"] != "succeeded")
    sampled_total = collections.Counter()
    executed_total = collections.Counter()
    for r in rows:
        sampled_total.update(r["sampled_kinds"])
        executed_total.update(r["executed_kinds"])
    windows = sorted(r["window_frames"] for r in rows if r["window_frames"] is not None)
    return {
        "schema_version": SCHEMA_VERSION,
        "stage": receipt.get("stage"),
        "reviewed_code": receipt.get("code_commit"),
        "stage_receipt_sha256": _sha256(receipt_path),
        "output_root": str(root),
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "houses_planned": receipt.get("houses_planned"),
        "succeeded": receipt.get("succeeded"),
        "failed": receipt.get("failed"),
        "null_window_episodes": receipt.get("null_window_episodes"),
        "yield_house_level_non_null": receipt.get("yield_house_level_non_null"),
        "yield_gate": receipt.get("yield_gate"),
        "yield_gate_passed": receipt.get("yield_gate_passed"),
        "requested_workers": receipt.get("requested_workers"),
        "actual_workers": receipt.get("actual_workers"),
        "derived_worker_count": receipt.get("derived_worker_count"),
        "binding_constraint": receipt.get("binding_constraint"),
        "is_extrapolation": receipt.get("is_extrapolation"),
        "wall_clock_seconds": receipt.get("wall_clock_seconds"),
        "failures_by_reason": dict(by_reason),
        "null_window_failed": receipt.get("null_window_failed"),
        "moves_executed": receipt.get("moves_executed"),
        "moves_source_first": receipt.get("moves_source_first"),
        "move_minimum": receipt.get("move_minimum"),
        "controls_total": receipt.get("controls_total"),
        "controls_outside_U": receipt.get("controls_outside_U"),
        "controls_from_U": ((receipt.get("controls_total") or 0) - (receipt.get("controls_outside_U") or 0)) if receipt.get("controls_total") is not None else None,
        "controls_outside_U_fraction": (round((receipt.get("controls_outside_U") or 0) / receipt["controls_total"], 3)
                                        if receipt.get("controls_total") else None),
        "controls_note": "ruling 41: outside-U controls were visible during the window and are the weaker control; reported separately",
        "null_window_salt_sha256": receipt.get("null_window_salt_sha256"),
        "intervention_kinds_sampled_in_successes": dict(sampled_total),
        "intervention_kinds_executed": dict(executed_total),
        "window_frames_of_successes": windows,
        "bytes_written_total": sum(r["bytes_written"] or 0 for r in rows),
        "houses": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--stage-receipt", default="s1_02b_receipt.json")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    report = build_report(Path(args.output_root), args.stage_receipt)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, sort_keys=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "houses"}, indent=1))
    print(f"wrote {out} ({len(report['houses'])} houses)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
