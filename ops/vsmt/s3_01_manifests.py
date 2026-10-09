#!/usr/bin/env python3
"""S3-01 (ruling 102-8): write the three S3 manifests from the split S1-02a froze.

From the split parameters frozen in the S1-02a contract (configs/vsmt/lean_s1_02a_pilot_v2.json, `split_freeze`) and the
ruling-81 confirmation-house registry, derives the S3 test (100 houses), validation (50) and train (positions 100-399 of the
train block, 300 houses) lists, checks that the confirmation set recomputes item by item and that the lists are disjoint,
and writes configs/vsmt/lean_s3_01_manifests.json. It computes lists only: no data is generated and no house is read. The
same inputs always give the same bytes; a test recomputes them.

Usage:
  python ops/vsmt/s3_01_manifests.py [--output configs/vsmt/lean_s3_01_manifests.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from vsmt import lean_s3_manifests as m  # noqa: E402

SPLIT_SOURCE = "configs/vsmt/lean_s1_02a_pilot_v2.json"
CONFIRMATION = "configs/vsmt/lean_ruling81_confirmation_houses.json"
OUTPUT = "configs/vsmt/lean_s3_01_manifests.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--output", default=OUTPUT)
    args = parser.parse_args(argv)
    freeze = json.loads((ROOT / SPLIT_SOURCE).read_text(encoding="utf-8"))["split_freeze"]
    registry = json.loads((ROOT / CONFIRMATION).read_text(encoding="utf-8"))
    manifest = m.build(freeze, split_freeze_source=f"{SPLIT_SOURCE} split_freeze", confirmation_registry=registry)
    out = ROOT / args.output if not Path(args.output).is_absolute() else Path(args.output)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"[s3-01-manifests] test {manifest['counts']['test']}, validation {manifest['counts']['validation']}, "
          f"train {manifest['counts']['train']} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
