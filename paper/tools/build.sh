#!/usr/bin/env bash
# S4: compile paper/main.tex in both versions -- review (anonymous, the default) and final (authors and links) -- with
# pdflatex, bibtex, pdflatex x2 into paper/build/ (ignored by git), then check each PDF against the RA-L limits.
# Outputs: build/vsmt_review.pdf (no author information; release links read "link withheld for review") and
# build/vsmt_final.pdf (authors and links). The versions differ only in the \iffinalversion switch of main.tex; this
# script defines \VSMTFINAL for the final one. Each PDF must have at most 8 pages (RA-L: 6 + 2, figures, tables and
# references included), no overfull box and no undefined reference; the review PDF's text must not contain the
# author's name, affiliation, e-mail or personal repository names. Any failure gives exit code 1. Tables and figures
# are not generated here: run make_tables.py and make_figures.py first.
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
