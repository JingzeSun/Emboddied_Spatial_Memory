#!/usr/bin/env bash
# S4: compile paper/main.tex in both versions -- review (anonymous, the default) and final (authors and links) -- with
# pdflatex, bibtex, pdflatex x2 into paper/build/ (ignored by git), then check each PDF against the RA-L limits.
# 白话：在装了 TeX（MiKTeX 或 TeX Live）的机器上一次编出两版论文：匿名初投稿版 build/vsmt_review.pdf（作者栏不写作者信息、
# 发布链接写成 link withheld for review）与正式版 build/vsmt_final.pdf（作者与链接）。两版只差 main.tex 里的一个开关
# （\iffinalversion；本脚本给正式版定义 \VSMTFINAL）。每版都核对：页数不超过 RA-L 的 8 页（6＋2 页，图表、参考文献全算）、
# 0 处溢出（Overfull）、没有未定义的引用；匿名版另查 PDF 文本里没有作者名、单位、邮箱与个人仓库名。任何一项不过，退出码为 1。
# 例如表格太宽或正文写超了一页，会在这里报出来。它不生成表与图：先跑 make_tables.py、make_figures.py。
# Usage (repository root): bash paper/tools/build.sh
# Windows with a per-user MiKTeX: the binaries are found under %LOCALAPPDATA%/Programs/MiKTeX/miktex/bin/x64.
set -u
PAPER="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$PAPER/build"
MAX_PAGES=8
# strings that would identify the author in the anonymous review version (case-insensitive)
IDENTIFYING="jingze|jsun0632|sydney|jingzesun498|gmail"
mkdir -p "$OUT"
BIN=""
if ! command -v pdflatex >/dev/null 2>&1 && [ -n "${LOCALAPPDATA:-}" ] && [ -d "$LOCALAPPDATA/Programs/MiKTeX/miktex/bin/x64" ]; then
  BIN="$LOCALAPPDATA/Programs/MiKTeX/miktex/bin/x64/"
fi
cd "$PAPER" || exit 9
STATUS=0

build() {  # $1 = review | final
  local job="vsmt_$1" source="main.tex" pass code
  if [ "$1" = final ]; then source='\def\VSMTFINAL{}\input{main.tex}'; fi
  for pass in 1 2 3; do
    if [ "$pass" = 2 ]; then
      (cd "$OUT" && BIBINPUTS="$PAPER:$PAPER;" "${BIN}bibtex" "$job" > "$OUT/${job}_bibtex.out" 2>&1)
      code=$?; [ "$code" = 0 ] || { echo "$job: bibtex exit $code (see build/${job}_bibtex.out)"; return 1; }
    fi
    "${BIN}pdflatex" -interaction=nonstopmode -halt-on-error -output-directory="$OUT" -jobname="$job" "$source" \
      > "$OUT/${job}_pdflatex_$pass.out" 2>&1
    code=$?; [ "$code" = 0 ] || { echo "$job: pdflatex pass $pass exit $code (see build/${job}_pdflatex_$pass.out)"; return 1; }
  done
  local log="$OUT/$job.log" pages overfull undefined result=0
  pages=$(tr -d '\r\n' < "$log" | grep -o "Output written on [^(]*([0-9]* pages" | grep -o "[0-9]* pages" | grep -o "[0-9]*")
  overfull=$(grep -c "Overfull" "$log")
  undefined=$(grep -c -E "undefined|Label\(s\) may have changed" "$log")
  echo "$job: ${pages:-?} pages (limit $MAX_PAGES), $overfull overfull boxes, $undefined undefined or unstable references"
  grep -E "Overfull|undefined|Label\(s\) may have changed" "$log" | head -10
  [ -n "$pages" ] && [ "$pages" -le "$MAX_PAGES" ] && [ "$overfull" = 0 ] && [ "$undefined" = 0 ] || result=1
  if [ "$1" = review ]; then
    if command -v "${BIN}pdftotext" >/dev/null 2>&1 || [ -x "${BIN}pdftotext.exe" ]; then
      local found
      found=$("${BIN}pdftotext" -q "$OUT/$job.pdf" - | grep -o -i -E "$IDENTIFYING" | sort -u | tr '\n' ' ')
      if [ -n "$found" ]; then echo "$job: identifying text in the anonymous version: $found"; result=1
      else echo "$job: no identifying text found ($IDENTIFYING)"; fi
    else
      echo "$job: pdftotext not found, anonymity of the PDF text not checked"
    fi
  fi
  return "$result"
}

for version in review final; do
  build "$version" || STATUS=1
done
[ "$STATUS" = 0 ] && echo "both versions pass" || echo "CHECK FAILED"
exit "$STATUS"
