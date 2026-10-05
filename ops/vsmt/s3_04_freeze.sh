#!/bin/bash
# S3-04: the choice on validation and the freeze before test, one command (ruling 106, user 2026-10-05: 「待裁 106 全按推荐」).
#
# Usage (B1, from a clean detached worktree of the reviewed freeze commit, after S3-03's closing verify passed; CPU only):
#   bash ops/vsmt/s3_04_freeze.sh all      check -> select (both front ends) -> probe (both) -> receipt -> verify; run again to resume
#   bash ops/vsmt/s3_04_freeze.sh status   each step's pass, commit and first problems
#
# Steps (ops/vsmt/s3_04_manifest.py; output root $AUTODL/vsmt_private/s3-04-<commit>, one per commit):
#   suite    the full test suite at this commit
#   check    G1 (S3-03's verify at the registration commit had no problem, its exports equal its manifest, the 30 round-1 weights
#            files equal their receipts, S0-05's ELU-P values equal the run's) and G5 (the four test roots still sealed by the
#            exported seal; marker files only)
#   select   per front end: G2 (readings recomputed from the merged audits equal S3-03's), G3 (one event count per metric), the
#            choice (lean_arms.select_configuration, ruling 102-4), the S3-05 run list and the probe episodes
#   probe    per front end: G4, every selected run (learned arms at each seed) rerun on two validation episodes, bit for bit
#            against S3-03's audits (the most expensive step: about 100 small audits, parallel within the cgroup)
#   receipt  only when all of the above passed at this commit and S3-05's entry exists: the freeze receipt and the exports
#            $EXPORT_DIR/vsmt_lean_s3_04_*_<commit>.json
#   verify   the receipt digest, the code and frozen files against the receipt, the exports' digests; the manifest
# A step that passed at this commit is kept on a resume; a new commit redoes every step in its own output root. No fallback
# power-off (ruling 106-7). Next (ruling 106-5): commit the exports to results/, push, and wait for the user before S3-05.
#
# Environment (optional): AUTODL, EXPORT_DIR, S3_03_RUN_ROOT ($AUTODL/vsmt_private/s3-03-run), S3_03_TAG (10f7013),
#   PROBE_WORKERS (default: the largest safe number from the cgroup), PY.
set -u
WORKTREE=$(cd "$(dirname "$0")/../.." && pwd)
cd "$WORKTREE" || exit 2
SHORT=$(git rev-parse --short=7 HEAD)
PY=${PY:-/root/miniconda3/bin/python3.12}
AUTODL=${AUTODL:-/root/autodl-tmp}
EXPORT_DIR=${EXPORT_DIR:-$AUTODL/vsmt_outputs/exports}
S3_03_RUN_ROOT=${S3_03_RUN_ROOT:-$AUTODL/vsmt_private/s3-03-run}
S3_03_TAG=${S3_03_TAG:-10f7013}
OUT=$AUTODL/vsmt_private/s3-04-$SHORT
LOG_DIR=$AUTODL/vsmt_outputs/run_logs/s3-04-$SHORT
COMMAND=${1:-}
case "$COMMAND" in all|status) ;; *) echo "usage: bash ops/vsmt/s3_04_freeze.sh all|status"; exit 2;; esac
M() { PYTHONPATH=src $PY ops/vsmt/s3_04_manifest.py "$@"; }
if [ "$COMMAND" = "status" ]; then M status --out-root "$OUT"; exit 0; fi
if [ -n "$(git status --porcelain)" ]; then echo "refused: the worktree is not clean"; exit 2; fi
if ps -eo args | grep -v grep | grep -E "^sleep [0-9]+$|/usr/bin/shutdown" > /dev/null; then
  echo "refused: a fallback power-off may be armed (a sleep or a shutdown is pending); stop it first"; exit 2
fi
if pgrep -f "s3_03_train_select.sh all|s3_03_jobs.py run-measured |s3_03_manifest.py run " > /dev/null; then
  echo "refused: the S3-03 driver or its pool still runs (S3-04 reads S3-03's finished run)"; exit 2
fi
mkdir -p "$OUT" "$LOG_DIR" "$EXPORT_DIR"
exec 9> "$OUT/.lock"
if ! flock -n 9; then echo "refused: another S3-04 driver holds $OUT/.lock"; exit 2; fi
COMMON=(--s3-03-run-root "$S3_03_RUN_ROOT" --export-dir "$EXPORT_DIR" --s3-03-tag "$S3_03_TAG")
done_here() { [ "$($PY -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('pass') is True and d.get('code_commit','').startswith(sys.argv[2]))" "$OUT/$1.json" "$SHORT" 2>/dev/null)" = "True" ]; }
step() {  # name, then the subcommand and its options
  NAME=$1; shift
  if done_here "$NAME"; then echo "[$(date)] $NAME: passed at $SHORT, kept"; return 0; fi
  echo "[$(date)] $NAME"
  M "$@" --out-root "$OUT" "${COMMON[@]}" 2>&1 | tee -a "$LOG_DIR/$NAME.log"
  CODE=${PIPESTATUS[0]}
  if [ "$CODE" != "0" ]; then echo "[$(date)] $NAME stopped (exit $CODE): $OUT/$NAME.json"; exit "$CODE"; fi
}
echo "[$(date)] S3-04 at $SHORT: output $OUT, logs $LOG_DIR"
if [ ! -f "$OUT/suite-$SHORT.ok" ]; then
  echo "[$(date)] full test suite -> $LOG_DIR/suite.log"
  if ! PYTHONPATH=src $PY -m unittest discover -s tests -t tests -p "test_*.py" > "$LOG_DIR/suite.log" 2>&1; then
    echo "[$(date)] the test suite failed ($LOG_DIR/suite.log)"; exit 1
  fi
  touch "$OUT/suite-$SHORT.ok"
fi
step check check
for FRONT in instance sam2; do step "select_$FRONT" select --front "$FRONT"; done
for FRONT in instance sam2; do step "probe_$FRONT" probe --front "$FRONT" ${PROBE_WORKERS:+--workers "$PROBE_WORKERS"}; done
step receipt receipt
M verify --out-root "$OUT" "${COMMON[@]}" 2>&1 | tee -a "$LOG_DIR/verify.log"
CODE=${PIPESTATUS[0]}
echo "[$(date)] S3-04 finished (verify exit $CODE); exports $EXPORT_DIR/vsmt_lean_s3_04_*_$SHORT.json"
exit "$CODE"
