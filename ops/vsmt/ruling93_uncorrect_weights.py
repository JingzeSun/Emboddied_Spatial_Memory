#!/usr/bin/env python3
"""Ruling 93 revised (2026-09-30): a copy of a trained heads file with the ln w existence offset removed (the original is untouched).

白话：同一组权重，只把“存在决策前减去 ln w”的偏移去掉，重算摘要后另存一份；用它在 τ_r 0.5 下跑格，就是“不校正、原始分数
阈值 0.5”的工作点（w≈65 时等于保留校正、τ≈0.015）。它不改变网络的任何参数，也不改变分数排序。

Usage:
  python ops/vsmt/ruling93_uncorrect_weights.py --input <weights.json> --output <weights_uncorrected.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from cpmt.hashing import canonical_json  # noqa: E402


def uncorrected(payload: Mapping[str, Any]) -> dict[str, Any]:
    from vsmt import lean_model as model

    model.load_heads(payload)  # the input must itself be valid
    out = json.loads(json.dumps(payload))
    removed = out.pop("existence_logit_offset", None)
    if removed is None:
        raise ValueError("weights_have_no_existence_offset")
    out["training"] = {**out.get("training", {}), "derived": {"from_sha256": payload["sha256"], "change": "existence_logit_offset removed",
                                                              "removed_offset": removed}}
    out["sha256"] = hashlib.sha256(canonical_json({k: v for k, v in out.items() if k not in ("training", "sha256")}).encode("utf-8")).hexdigest()
    heads = model.load_heads(out)
    assert float(getattr(heads, "existence_logit_offset", 0.0)) == 0.0
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    out = uncorrected(json.loads(Path(args.input).read_text(encoding="utf-8")))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(out), encoding="utf-8")
    print(f"{args.output}: {out['sha256'][:12]} (from {out['training']['derived']['from_sha256'][:12]}, offset {out['training']['derived']['removed_offset']['value']:.4f} removed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
