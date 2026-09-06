"""Bundle one run's small JSON reports into a single committable file.

Generation and training may happen on a rented machine while analysis happens
elsewhere, so the numbers need a path back that does not involve copying arrays
around. Arrays stay in ``outputs/`` and are never committed; this writes only
the summaries, plus enough provenance to tell later whether two reports are
comparable: the git commit, whether the tree was dirty, the protocol hash, the
dataset version, and the interpreter and library versions that produced them.

Usage on the machine that ran the experiment:

    python scripts/export_run_report.py --out-dir outputs/m1_formal --name m1_formal
    git add results && git commit -m "results: m1 formal-scale run" && git push
"""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))


def _git(*args: str) -> str | None:
    try:
        return subprocess.run(("git", *args), cwd=PROJECT, capture_output=True,
                              text=True, check=True, timeout=20).stdout.strip()
    except Exception:
        return None


def _environment() -> dict[str, object]:
    info: dict[str, object] = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "hostname": platform.node(),
    }
    try:
        import os
        info["cpu_count"] = os.cpu_count()
    except Exception:
        pass
    for module in ("numpy", "torch"):
        try:
            info[module] = __import__(module).__version__
        except Exception:
            info[module] = None
    try:
        import torch
        info["cuda_available"] = bool(torch.cuda.is_available())
        if torch.cuda.is_available():
            info["cuda_device"] = torch.cuda.get_device_name(0)
    except Exception:
        pass
    return info


def _read(path: Path) -> object | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        return {"unreadable": str(error)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True,
                        help="the run directory passed to the runners")
    parser.add_argument("--name", required=True,
                        help="basename for results/<name>.json")
    parser.add_argument("--results-dir", type=Path, default=PROJECT / "results")
    parser.add_argument("--note", default="",
                        help="one line recorded with the report")
    args = parser.parse_args()

    out_dir = args.out_dir
    if not out_dir.is_dir():
        print(f"no such run directory: {out_dir}")
        return 1

    causal_rows = sorted(
        (p.stem, _read(p)) for p in (out_dir / "causal").glob("*.json")
    ) if (out_dir / "causal").is_dir() else []

    report = {
        "name": args.name,
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": args.note,
        "formal_run": False,
        "test_generated": False,
        "provenance": {
            "git_commit": _git("rev-parse", "HEAD"),
            "git_branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "git_dirty": bool(_git("status", "--porcelain")),
            "environment": _environment(),
        },
        "af_report": _read(out_dir / "af_report.json"),
        "teacher_forced_only": _read(out_dir / "af_teacher_forced.json"),
        "generation_manifests": {
            path.name: _read(path)
            for path in sorted(out_dir.glob("*.manifest.json"))
        },
        "causal_per_seed": {name: value for name, value in causal_rows},
        # Anything else a runner dropped here, so a new report does not need a
        # change in this script to travel back with the rest of the run.
        "other_reports": {
            path.name: _read(path)
            for path in sorted(out_dir.glob("*.json"))
            if path.name not in {"af_report.json", "af_teacher_forced.json"}
            and not path.name.endswith(".manifest.json")
        },
    }
    if report["af_report"] is None and report["teacher_forced_only"] is None:
        print(f"no af_report.json or af_teacher_forced.json under {out_dir}")
        return 1

    args.results_dir.mkdir(parents=True, exist_ok=True)
    target = args.results_dir / f"{args.name}.json"
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                      encoding="utf-8")
    size = target.stat().st_size
    print(f"wrote {target}  ({size/1024:.1f} KB)")
    if report["provenance"]["git_dirty"]:
        print("WARNING: the working tree was dirty, so this report may not "
              "correspond to the recorded commit")
    complete = (report["af_report"] or {}).get("causal_complete")
    if complete is False:
        print("NOTE: causal_complete is false, so the protocol's primary "
              "metrics are not established by this run")
    print("\nnext: git add results && git commit && git push")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
