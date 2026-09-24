"""S2-05: export a pass of the development root to a committed results/ report with provenance.

Usage:
    python ops/vsmt/lean_s2_05_export.py --output-root /root/autodl-tmp/vsmt_private/lean-s2-05-<commit> \\
        --pass calibration --arm LOW --results results/vsmt_lean_s2_05_calibration_<commit>.json

What it writes: the pass plan and receipt, the merged calibration report when the pass produced one
(quantiles and histograms), every episode's seven-metric report with its decomposition totals and
the sha256 of its receipt, the code commits found in the receipts, and the count of episodes that
failed.  No private byte enters the file: the episode reports carry object keys only inside the
recovery lists, which the S0-04 reporting fields already allow, and no frame, mask, descriptor or
label is copied.

白话：把服务器上一趟的产物压成一份可提交的 results 报告：趟计划与回执、合并后的校准分位数、每条
episode 的七项指标与三分解总计和回执摘要、代码提交号。它不复制任何帧、mask、描述子或标签。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from vsmt import lean_evaluation as ev  # noqa: E402


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--pass", dest="pass_name", required=True)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--results", required=True, help="the results/ path to write")
    args = parser.parse_args()
    pass_root = Path(args.output_root).resolve() / args.pass_name
    receipt_path = pass_root / f"pass_receipt.{args.arm}.json"
    if not receipt_path.exists():
        print(f"[s2-05-export] refused: no pass receipt at {receipt_path}", file=sys.stderr)
        return 2
    pass_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    episodes: dict[str, Any] = {}
    commits: set[str] = set()
    for episode_dir in sorted(p for p in pass_root.iterdir() if p.is_dir() and (p / args.arm / "receipt.json").exists()):
        path = episode_dir / args.arm / "receipt.json"
        receipt = json.loads(path.read_text(encoding="utf-8"))
        commits.add(str(receipt.get("code_commit")))
        episodes[episode_dir.name] = {
            "status": receipt.get("status"), "receipt_sha256": sha256_of(path), "frames": receipt.get("frames"),
            "wall_seconds": receipt.get("wall_seconds"), "illegal_programs": receipt.get("illegal_programs"), "atoms": receipt.get("atoms"),
            "final_entities_by_state": receipt.get("final_entities_by_state"), "window": receipt.get("window"),
            "executed_interventions": receipt.get("executed_interventions"),
            "report": receipt.get("report"), "headline": ev.headline_values(receipt["report"]) if receipt.get("report") else None,
            "decomposition_totals": (receipt.get("diagnostics") or {}).get("decomposition_totals"),
            "spawned_after_reload_keys": (receipt.get("diagnostics") or {}).get("spawned_after_reload_keys"),
            "nuisance_largest_advantage": (receipt.get("nuisance_probes") or {}).get("largest_advantage"),
            "elu_p_counts": receipt.get("elu_p_counts"),
        }
    calibration_path = pass_root / "calibration_report.json"
    calibration = json.loads(calibration_path.read_text(encoding="utf-8")) if calibration_path.exists() else None
    out = {
        "schema_version": "vsmt-lean-s2-05-pass-export-v1", "stage": "S2-05", "pass": args.pass_name, "arm": args.arm,
        "output_root": str(pass_root.parent), "code_commits_in_receipts": sorted(commits),
        "pass_receipt": pass_receipt, "pass_receipt_sha256": sha256_of(receipt_path),
        "episodes_exported": len(episodes), "episodes_failed": len(pass_receipt.get("episodes_failed", [])),
        "calibration_report": calibration, "calibration_report_sha256": sha256_of(calibration_path) if calibration else None,
        "episodes": episodes,
    }
    target = Path(args.results)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"[s2-05-export] wrote {target} ({len(episodes)} episodes, commits {sorted(commits)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
