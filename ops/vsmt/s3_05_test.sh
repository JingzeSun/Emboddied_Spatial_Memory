#!/bin/bash
# S3-05: the one test run (ruling 107, user 2026-10-05: 「待裁 107 全按推荐」).
#
# Usage (B1, from a clean detached worktree of a commit whose src/, ops/ and configs/ are the frozen ones and whose results/ holds the
# S3-04 freeze receipt; the user gives the go key):
#   S3_05_GO=<first 12 characters of the receipt digest> RECEIPT=<freeze_receipt.json> bash ops/vsmt/s3_05_test.sh all
#   bash ops/vsmt/s3_05_test.sh status      counts only, never a metric (ruling 107-5)
#   long runs in the background: setsid nohup env S3_05_GO=... RECEIPT=... bash ops/vsmt/s3_05_test.sh all > <log> 2>&1 &
#
# Steps (ops/vsmt/s3_05_manifest.py; run root $AUTODL/vsmt_private/s3-05-run):
#   suite    the full test suite
#   check    verify_freeze against the receipt (code, weights, ELU-P values, test list); the receipt is committed in results/; the
#            go key equals the receipt digest's first 12 characters
#   unseal   the S3-02 seal equals the receipt's, every digest is recomputed, the four test roots are opened as reading 1 with a
#            read record beside each (a resume is the same reading); then the usable test episodes per front end
#   run      the job pool: one job per (selected run, test episode), metrics-only node audits; a crash reruns once with the same
#            inputs, a second failure is a data failure (recorded, the run goes on); admitted hosts with kind 'test' share the work
#   merge    one merged file per run, after every job ended
#   stats    every statistic at once (ruling 107-4: primary gates, fixed sequence, original gate, comparisons, node F1 interval)
#   export   $EXPORT_DIR/vsmt_lean_s3_05_*_<commit>.json and the manifest
# Run 'all' again to resume after an engineering failure: finished audits are kept, the opened roots stay the same reading.
# No fallback power-off. Test copies to remote hosts happen only after 'unseal' (ops/vsmt/remote_hosts.py setup/admit --kinds test).
#
# Environment: S3_05_GO and RECEIPT (required for all), AUTODL, EXPORT_DIR, S3_03_RUN_ROOT, S3_02_TAG (3f6ef1d), RUN_ROOT, BUDGET_CORES, PY.
set -u
WORKTREE=$(cd "$(dirname "$0")/../.." && pwd)
cd "$WORKTREE" || exit 2
SHORT=$(git rev-parse HEAD | cut -c1-7)
PY=${PY:-/root/miniconda3/bin/python3.12}
AUTODL=${AUTODL:-/root/autodl-tmp}
EXPORT_DIR=${EXPORT_DIR:-$AUTODL/vsmt_outputs/exports}
S3_03_RUN_ROOT=${S3_03_RUN_ROOT:-$AUTODL/vsmt_private/s3-03-run}
S3_02_TAG=${S3_02_TAG:-3f6ef1d}
RUN_ROOT=${RUN_ROOT:-$AUTODL/vsmt_private/s3-05-run}
LOG_DIR=$AUTODL/vsmt_outputs/run_logs/s3-05-$SHORT
COMMAND=${1:-}
case "$COMMAND" in all|status) ;; *) echo "usage: S3_05_GO=... RECEIPT=... bash ops/vsmt/s3_05_test.sh all | bash ops/vsmt/s3_05_test.sh status"; exit 2;; esac
M() { PYTHONPATH=src $PY ops/vsmt/s3_05_manifest.py "$@"; }
if [ "$COMMAND" = "status" ]; then M status --run-root "$RUN_ROOT"; exit 0; fi
if [ -z "${RECEIPT:-}" ] || [ -z "${S3_05_GO:-}" ]; then echo "refused: RECEIPT and S3_05_GO are required (ruling 107-1)"; exit 2; fi
if [ -n "$(git status --porcelain)" ]; then echo "refused: the worktree is not clean"; exit 2; fi
if ps -eo args | grep -v grep | grep -E "^sleep [0-9]+$|/usr/bin/shutdown" > /dev/null; then
  echo "refused: a fallback power-off may be armed (a sleep or a shutdown is pending); stop it first"; exit 2
fi
mkdir -p "$RUN_ROOT" "$LOG_DIR" "$EXPORT_DIR"
exec 9> "$RUN_ROOT/.lock"
if ! flock -n 9; then echo "refused: another S3-05 driver holds $RUN_ROOT/.lock"; exit 2; fi
COMMON=(--receipt "$RECEIPT" --s3-03-run-root "$S3_03_RUN_ROOT" --export-dir "$EXPORT_DIR" --s3-02-tag "$S3_02_TAG")
step() {  # name, then the subcommand's own options
  NAME=$1; shift
  echo "[$(date)] $NAME"
  M "$NAME" --run-root "$RUN_ROOT" "${COMMON[@]}" "$@" 2>&1 | tee -a "$LOG_DIR/$NAME.log"
  CODE=${PIPESTATUS[0]}
  if [ "$CODE" != "0" ]; then echo "[$(date)] $NAME stopped (exit $CODE): $RUN_ROOT/$NAME.json"; exit "$CODE"; fi
}
echo "[$(date)] S3-05 at $SHORT: run root $RUN_ROOT, logs $LOG_DIR"
echo "[$(date)] full test suite -> $LOG_DIR/suite.log"
if ! PYTHONPATH=src $PY -m unittest discover -s tests -t tests -p "test_*.py" > "$LOG_DIR/suite.log" 2>&1; then
  echo "[$(date)] the test suite failed ($LOG_DIR/suite.log)"; exit 1
fi
step check
step unseal
step run --log-dir "$LOG_DIR" ${BUDGET_CORES:+--budget-cores "$BUDGET_CORES"}
step merge
step stats
step export
echo "[$(date)] S3-05 finished; exports $EXPORT_DIR/vsmt_lean_s3_05_*_$SHORT.json (pull, check sha256, commit to results/, write the LOG)"
