#!/usr/bin/env python3
"""S3-01 (ruling 102-8): write the three S3 manifests from the split S1-02a froze.

白话：从 S1-02a 合同里冻结的划分参数和裁决 81 的确认集登记文件出发，算出 S3 的 test（100）、validation（50）、train（train 块
第 100～399 位，300 个）三份名单，核对确认集逐项重算一致、各份互不重叠，写进 configs/vsmt/lean_s3_01_manifests.json。它只算
名单，不生成数据、不读任何 house；同一输入永远写出同样的字节，测试会重算核对。

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
