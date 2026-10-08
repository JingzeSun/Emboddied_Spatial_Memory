#!/usr/bin/env python3
"""S4: pack the paper sources for an Overleaf upload into paper/build/vsmt_overleaf.zip.

白话：把 Overleaf 编译所需的源文件打成一个 zip：``main.tex``、``refs.bib``、``sections/*.tex``、``tables/*.tex``、
``figures/*.pdf`` 与两张 TikZ 图 ``figures/{overview,method}.tex``。在 Overleaf 用 New Project → Upload Project 上传即可；
默认编出匿名初投稿版，把 ``main.tex`` 顶部的 ``\\finalversionfalse`` 改成 ``\\finalversiontrue`` 就是正式版。
输入是 ``paper/`` 下已生成的源文件（先跑 make_tables.py、make_figures.py）；输出是 zip 与文件清单。它不编译、不改源文件，
zip 里的时间戳固定为源文件的修改时间，成员按路径排序。例如表格改了就重跑本脚本再上传。

Usage (repository root): python paper/tools/pack_overleaf.py
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
OUT = PAPER / "build" / "vsmt_overleaf.zip"
PATTERNS = ("main.tex", "refs.bib", "sections/*.tex", "tables/*.tex", "figures/*.pdf", "figures/*.tex")


def main() -> int:
    members = sorted({path for pattern in PATTERNS for path in PAPER.glob(pattern) if path.is_file()})
    if not any(path.name == "main.tex" for path in members):
        print("paper/main.tex not found", file=sys.stderr)
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in members:
            archive.write(path, path.relative_to(PAPER).as_posix())
    for path in members:
        print(path.relative_to(PAPER).as_posix())
    print(f"{len(members)} files -> {OUT.relative_to(PAPER.parent).as_posix()} ({OUT.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
