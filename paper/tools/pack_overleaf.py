#!/usr/bin/env python3
"""S4: pack the paper sources for an Overleaf upload into paper/build/vsmt_overleaf.zip.

The zip holds everything Overleaf needs: ``main.tex``, ``refs.bib``, ``sections/*.tex``, ``tables/*.tex``,
``figures/*.pdf`` and the two TikZ figures ``figures/{overview,method}.tex``. Upload it with New Project → Upload
Project; it builds the anonymous review version by default, and changing ``\\finalversionfalse`` to
``\\finalversiontrue`` at the top of ``main.tex`` builds the final version. Run make_tables.py and make_figures.py
first. The script does not compile or modify sources; zip members are sorted by path and keep the sources'
modification times.

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
