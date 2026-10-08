#!/usr/bin/env bash
# S4: compile paper/main.tex with pdflatex, bibtex, pdflatex x2 into paper/build/ (ignored by git).
# 白话：在装了 TeX（MiKTeX 或 TeX Live）的机器上把论文编成 PDF。输入是 paper/ 下的源文件；输出 paper/build/main.pdf 和日志，
# 最后列出溢出（Overfull）行与未定义引用。例如表格太宽会在这里报出来。它不生成表与图：先跑 make_tables.py、make_figures.py。
# Usage (repository root): bash paper/tools/build.sh
# Windows with a per-user MiKTeX: the binaries are found under %LOCALAPPDATA%/Programs/MiKTeX/miktex/bin/x64.
set -u
PAPER="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$PAPER/build"
mkdir -p "$OUT"
BIN=""
if ! command -v pdflatex >/dev/null 2>&1 && [ -n "${LOCALAPPDATA:-}" ] && [ -d "$LOCALAPPDATA/Programs/MiKTeX/miktex/bin/x64" ]; then
  BIN="$LOCALAPPDATA/Programs/MiKTeX/miktex/bin/x64/"
fi
cd "$PAPER" || exit 9
pass() { "${BIN}pdflatex" -interaction=nonstopmode -halt-on-error -output-directory="$OUT" main.tex > "$OUT/pdflatex_$1.out" 2>&1; local code=$?; echo "pdflatex pass $1: exit $code"; return $code; }
pass 1 || exit 1
(cd "$OUT" && BIBINPUTS="$PAPER:$PAPER;" "${BIN}bibtex" main > "$OUT/bibtex.out" 2>&1); echo "bibtex: exit $?"
pass 2 || exit 1
pass 3 || exit 1
echo "overfull boxes: $(grep -c 'Overfull' "$OUT/main.log")"
grep -E "undefined|Citation .* undefined" "$OUT/main.log" | head -10
grep -o "Output written on .*" "$OUT/main.log" | head -1
