#!/bin/bash
# S3-07: the external validation on 3RScan (ruling 111, user 2026-10-07: 「待裁 111 全按推荐」; amendment 1: 「待裁 111 修订一取 (a)」).
#
# Two phases on two kinds of host, from a clean detached worktree of the S3-07 run commit (its src/, ops/ and configs/ differ from
# the frozen commit only by the S3-07 files and the registration edits; results/ holds the S3-04 freeze receipt):
#   GPU host (the same RTX 5090 model as S3-02):   RECEIPT=<freeze_receipt.json> bash ops/vsmt/s3_07_external.sh gpu
#   audit host (B1 and its admitted workers):       RECEIPT=<freeze_receipt.json> bash ops/vsmt/s3_07_external.sh audit
#   either:                                         bash ops/vsmt/s3_07_external.sh status
#   long runs in the background: setsid nohup env RECEIPT=... bash ops/vsmt/s3_07_external.sh gpu > <log> 2>&1 < /dev/null &
#
# Steps (ops/vsmt/s3_07_manifest.py; run root $RUN_ROOT):
#   gpu:   suite -> check (E1, receipt committed, converter commit registered, cache glob, contract open) -> render -> convert ->
#          reader-check -> cache (both front ends) -> e2 (two S3-02 train episodes regenerated, seals equal the committed exports) ->
#          handoff (tree digests of every root, usable episodes); then copy $EPISODE_ROOT, $GEOMETRY_ROOT, $CACHE_ROOT_BASE and
#          $RUN_ROOT to the audit host at the same paths
#   audit: suite -> check -> receive (copied roots equal the hand-over) -> inputs -> e3 (the receipt's G4 probe audits rerun here,
#          bit for bit against S3-03) -> run (the job pool; admitted workers with kind 'audit' share the work) -> merge -> stats ->
#          export ($EXPORT_DIR/vsmt_lean_s3_07_*_<commit>.json)
# Run a phase again to resume after an engineering failure: finished scans, pairs, caches and audits are kept. No fallback power-off.
#
# Environment: RECEIPT (required), AUTODL, SCANS_ROOT, META, LABELS, RENDER_ROOT, EPISODE_ROOT, GEOMETRY_ROOT, CACHE_ROOT_BASE,
# ASSETS_JSON, GPUS, RENDER_WORKERS, CONVERT_WORKERS, INSTANCE_WORKERS, SAM2_WORKERS, S3_02_TRAIN_ROOT, S3_03_RUN_ROOT, EXPORT_DIR,
# RUN_ROOT, BUDGET_CORES, E3_WORKERS, PY.
set -u
WORKTREE=$(cd "$(dirname "$0")/../.." && pwd)
cd "$WORKTREE" || exit 2
SHORT=$(git rev-parse HEAD | cut -c1-7)
PY=${PY:-/root/miniconda3/bin/python3.12}
AUTODL=${AUTODL:-/root/autodl-tmp}
SCANS_ROOT=${SCANS_ROOT:-$AUTODL/3rscan/scans}
META=${META:-$AUTODL/3rscan/meta/3RScan.json}
LABELS=${LABELS:-$AUTODL/3rscan/meta/3RScan.v2 Semantic Classes - Mapping.csv}
RENDER_ROOT=${RENDER_ROOT:-$AUTODL/vsmt_private/s3-07-render-$SHORT}
EPISODE_ROOT=${EPISODE_ROOT:-$AUTODL/vsmt_outputs/s3-07-$SHORT}
GEOMETRY_ROOT=${GEOMETRY_ROOT:-$AUTODL/vsmt_private/s3-07-geometry-$SHORT}
CACHE_ROOT_BASE=${CACHE_ROOT_BASE:-$AUTODL/vsmt_caches/s3-07-$SHORT}
ASSETS_JSON=${ASSETS_JSON:-$AUTODL/vsmt_private/s103_assets.json}
GPUS=${GPUS:-0,1}
RENDER_WORKERS=${RENDER_WORKERS:-8}
CONVERT_WORKERS=${CONVERT_WORKERS:-8}
INSTANCE_WORKERS=${INSTANCE_WORKERS:-12}
SAM2_WORKERS=${SAM2_WORKERS:-8}
S3_02_TRAIN_ROOT=${S3_02_TRAIN_ROOT:-$AUTODL/vsmt_outputs/s3-02-3f6ef1d/train}
S3_03_RUN_ROOT=${S3_03_RUN_ROOT:-$AUTODL/vsmt_private/s3-03-run}
EXPORT_DIR=${EXPORT_DIR:-$AUTODL/vsmt_outputs/exports}
RUN_ROOT=${RUN_ROOT:-$AUTODL/vsmt_private/s3-07-run}
LOG_DIR=$AUTODL/vsmt_outputs/run_logs/s3-07-$SHORT
COMMAND=${1:-}
case "$COMMAND" in gpu|audit|status) ;; *) echo "usage: RECEIPT=... bash ops/vsmt/s3_07_external.sh gpu|audit | bash ops/vsmt/s3_07_external.sh status"; exit 2;; esac
M() { PYTHONPATH=src $PY ops/vsmt/s3_07_manifest.py "$@"; }
if [ "$COMMAND" = "status" ]; then M status --run-root "$RUN_ROOT"; exit 0; fi
if [ -z "${RECEIPT:-}" ]; then echo "refused: RECEIPT is required (the S3-04 freeze receipt)"; exit 2; fi
if [ -n "$(git status --porcelain)" ]; then echo "refused: the worktree is not clean"; exit 2; fi
if ps -eo args | grep -v grep | grep -E "^sleep [0-9]+$|/usr/bin/shutdown" > /dev/null; then
  echo "refused: a fallback power-off may be armed (a sleep or a shutdown is pending); stop it first"; exit 2
fi
mkdir -p "$RUN_ROOT" "$LOG_DIR" "$EXPORT_DIR"
exec 9> "$RUN_ROOT/.lock"
if ! flock -n 9; then echo "refused: another S3-07 driver holds $RUN_ROOT/.lock"; exit 2; fi
COMMON=(--receipt "$RECEIPT" --s3-03-run-root "$S3_03_RUN_ROOT" --log-dir "$LOG_DIR")
step() {  # name, then the subcommand's own options
  NAME=$1; shift
  echo "[$(date)] $NAME"
  M "$NAME" --run-root "$RUN_ROOT" "${COMMON[@]}" "$@" 2>&1 | tee -a "$LOG_DIR/$NAME.log"
  CODE=${PIPESTATUS[0]}
  if [ "$CODE" != "0" ]; then echo "[$(date)] $NAME stopped (exit $CODE): $RUN_ROOT/$NAME.json"; exit "$CODE"; fi
}
echo "[$(date)] S3-07 $COMMAND at $SHORT: run root $RUN_ROOT, logs $LOG_DIR"
echo "[$(date)] full test suite -> $LOG_DIR/suite-$COMMAND.log"
if ! PYTHONPATH=src $PY -m unittest discover -s tests -t tests -p "test_*.py" > "$LOG_DIR/suite-$COMMAND.log" 2>&1; then
  echo "[$(date)] the test suite failed ($LOG_DIR/suite-$COMMAND.log)"; exit 1
fi
if [ "$COMMAND" = "gpu" ]; then
  step check --role gpu
  step render --scans-root "$SCANS_ROOT" --meta "$META" --render-root "$RENDER_ROOT" --workers "$RENDER_WORKERS" \
    --worker-basis "RENDER_WORKERS=$RENDER_WORKERS: single-threaded numpy renderer, about 0.12 s per frame per worker (sample run c0f350a)"
  step convert --scans-root "$SCANS_ROOT" --meta "$META" --labels "$LABELS" --render-root "$RENDER_ROOT" --episode-root "$EPISODE_ROOT" \
    --geometry-root "$GEOMETRY_ROOT" --workers "$CONVERT_WORKERS" \
    --worker-basis "CONVERT_WORKERS=$CONVERT_WORKERS: single-threaded, about 0.07 s per frame per worker (sample run d05f337)"
  step reader-check --episode-root "$EPISODE_ROOT" --geometry-root "$GEOMETRY_ROOT"
  step cache --episode-root "$EPISODE_ROOT" --cache-root-base "$CACHE_ROOT_BASE" --assets-json "$ASSETS_JSON" --gpus "$GPUS" \
    --instance-workers "$INSTANCE_WORKERS" --sam2-workers "$SAM2_WORKERS" \
    --worker-basis "S3-02 rule: two threads per instance worker; SAM2 $SAM2_WORKERS workers over cards $GPUS (4 per card measured best on a 5090, LOG-302/303)"
  step e2 --s3-02-train-root "$S3_02_TRAIN_ROOT" --assets-json "$ASSETS_JSON" --gpus "$GPUS"
  step handoff --episode-root "$EPISODE_ROOT" --geometry-root "$GEOMETRY_ROOT"
  echo "[$(date)] GPU phase finished; copy $EPISODE_ROOT $GEOMETRY_ROOT $CACHE_ROOT_BASE and $RUN_ROOT to the audit host at the same paths"
else
  step check --role audit
  step receive
  step inputs
  step e3 ${E3_WORKERS:+--workers "$E3_WORKERS"}
  step run ${BUDGET_CORES:+--budget-cores "$BUDGET_CORES"}
  step merge
  step stats
  step export --export-dir "$EXPORT_DIR"
  echo "[$(date)] S3-07 finished; exports $EXPORT_DIR/vsmt_lean_s3_07_*_$SHORT.json (pull, check sha256, commit to results/, write the LOG)"
fi
