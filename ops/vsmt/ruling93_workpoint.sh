#!/bin/bash
# Ruling 93 revised (2026-09-30, user: "按这个做"): a fixed-weight working-point comparison plus residual tracing, no training.
#   The five round-1 heads of ruling93-9722290 in the teacher-association + learned-existence cell, twice, both at tau_r 0.5 and
#   both with the read-only residual trace (node audit --trace-residuals):
#     corrected -- the heads as trained (existence logit minus ln w; the LOG-291 cell again, now traced);
#     raw       -- a copy of each heads file with the ln w offset removed (raw sigmoid threshold 0.5, i.e. corrected tau about 0.015).
#   390 audits largest episode first, merges, the metric reading (ruling93_tau_reading.py, labels corrected / raw) and the
#   residual reading (ruling93_residual_reading.py: every final residual object classified, the six common failing houses apart).
#   No other threshold, no parameter selected, no training, no 89-4.  Never shuts down.
set -u
WORKTREE=$(cd "$(dirname "$0")/../.." && pwd)
cd "$WORKTREE" || exit 2
COMMIT=$(git rev-parse --short HEAD)
PY=/root/miniconda3/bin/python3.12
AUTODL=/root/autodl-tmp
OUTPUTS=$AUTODL/vsmt_outputs
EXPORT_DIR=$OUTPUTS/exports
LOG_DIR=$OUTPUTS/run_logs/ruling93-wp-$COMMIT
CACHE_ROOT=$AUTODL/vsmt_caches/lean-s1-03-oracle-8ebbd05
GEOMETRY_ROOT=$AUTODL/vsmt_private/lean-s1-04-geometry-154776d
REID_WEIGHTS=$AUTODL/vsmt_private/lean-s1-04-diagnostics-oracle-caa50c7/reid_head_vitb14.json
PASS_ROOT=$AUTODL/vsmt_private/lean-s2-05-oracle-c150be0
HEADS_TAG=9722290
HEADS_ROOT=$AUTODL/vsmt_private/ruling93-$HEADS_TAG
DIAG=$AUTODL/vsmt_private/ruling93-wp-$COMMIT
STATUS=$EXPORT_DIR/ruling93_wp_$COMMIT.status.json
QUOTA=$(awk '{ if ($1 == "max") print 16; else print int($1 / $2) }' /sys/fs/cgroup/cpu.max 2>/dev/null || echo 16)
WORKERS=${WORKERS:-$((QUOTA - 4))}
RESUME=${RESUME:-0}
SEEDS="7 19 31 43 59"
FOCUS=00702,01394,03288,05879,07815,08422
mkdir -p "$EXPORT_DIR" "$LOG_DIR" "$DIAG/weights_raw"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
count_bad() { [ -f "$1" ] || { echo 0; return; }; grep -vc 'exit 0$' "$1"; return 0; }
finish() {
  $PY -c "import json,sys,time; json.dump({'commit': '$COMMIT', 'stage_reached': sys.argv[1], 'finished_cst': time.strftime('%Y-%m-%d %H:%M:%S'),
    'suite_exit': '${SUITE_RC:-}', 'audits_failed': '${AUDITS_FAILED:-}', 'merges_failed': '${MERGES_FAILED:-}',
    'metric_reading_exit': '${READING_RC:-}', 'residual_reading_exit': '${RESIDUAL_RC:-}', 'heads': '$HEADS_ROOT', 'workers': $WORKERS,
    'cpu_quota': $QUOTA, 'worker_basis': 'cgroup CPU quota minus four; audits single-threaded, largest episode first', 'shutdown': False},
    open('$STATUS', 'w'), indent=1)" "$1"
  echo "[$(date)] status written ($1)"; exit 0
}
if [ -n "$(git status --porcelain)" ]; then echo "worktree not clean; refusing"; exit 2; fi
echo "[$(date)] ruling 93 working points at $COMMIT: cpu quota $QUOTA, $WORKERS workers"
if [ "$RESUME" != "1" ]; then
  PYTHONPATH=src $PY -m unittest discover -s tests -t tests -p "test_*.py" > "$LOG_DIR/suite.log" 2>&1
  SUITE_RC=$?
  echo "[$(date)] suite exit $SUITE_RC: $(grep -E '^Ran |^OK|FAILED' "$LOG_DIR/suite.log" | tail -2 | tr '\n' ' ')"
  [ "$SUITE_RC" = "0" ] || finish suite_failed
fi
for SEED in $SEEDS; do
  W=$HEADS_ROOT/training/round1/VSMT-lean/A$SEED/weights.json
  [ -f "$W" ] || finish heads_missing
  [ -f "$DIAG/weights_raw/A$SEED.json" ] || PYTHONPATH=src $PY ops/vsmt/ruling93_uncorrect_weights.py --input "$W" --output "$DIAG/weights_raw/A$SEED.json" >> "$LOG_DIR/weights_raw.log" 2>&1 || finish uncorrected_weights_failed
done
cat "$LOG_DIR/weights_raw.log"
episode_root() { for R in "$OUTPUTS/lean-s1-02a-5f9aa71" "$OUTPUTS/lean-s1-02b-5f9aa71"; do [ -d "$R/$1" ] && echo "$R/$1" && return; done; }
frames_of() { ls "$CACHE_ROOT/$1" | grep -c 'cache.json.gz$'; }
EPISODES=$(for E in $(ls "$PASS_ROOT/dagger_round_1"); do [ -f "$PASS_ROOT/dagger_round_1/$E/VSMT-lean/receipt.json" ] && echo "$E"; done)
weights_for() { case $1 in corrected) echo "$HEADS_ROOT/training/round1/VSMT-lean/A$2/weights.json";; raw) echo "$DIAG/weights_raw/A$2.json";; esac; }
JOBS=$LOG_DIR/jobs.txt
for POINT in corrected raw; do for SEED in $SEEDS; do
  G=OA-LE-$POINT-A$SEED; OUT=$DIAG/audit/$G; W=$(weights_for $POINT $SEED)
  for EP in $EPISODES; do
    [ -f "$OUT/$EP/VSMT-lean/node_audit.json" ] && continue
    printf '%s\t%s\n' "$(frames_of $EP)" "$PY ops/vsmt/lean_s2_05_node_audit.py run --cache-root $CACHE_ROOT --episode-root $(episode_root $EP) --geometry-root $GEOMETRY_ROOT --episode-id $EP --arm VSMT-lean --config '{\"tau_r\": 0.5}' --oracle-association --trace-residuals --heads $W --descriptor reid_projection:vitb14 --weights $REID_WEIGHTS --output-root $OUT --device cpu > $LOG_DIR/$G-$EP.log 2>&1; echo \"$G $EP exit \$?\""
  done
done; done | sort -t$'\t' -k1,1nr | cut -f2- > "$JOBS"
echo "[$(date)] $(wc -l < "$JOBS") audits queued (largest episode first)"
xargs -d '\n' -P "$WORKERS" -I{} bash -c '{}' < "$JOBS" >> "$LOG_DIR/exits.log" 2>&1
AUDITS_FAILED=$(count_bad "$LOG_DIR/exits.log")
echo "[$(date)] audits: $(grep -c 'exit 0$' "$LOG_DIR/exits.log") ok, $AUDITS_FAILED failed"
MERGES_FAILED=0; ARGS=(); CELLS=()
for POINT in corrected raw; do
  DIRS=""
  for SEED in $SEEDS; do
    G=OA-LE-$POINT-A$SEED; RESULT=$EXPORT_DIR/vsmt_lean_ruling93_wp_audit_${G}_$COMMIT.json
    $PY ops/vsmt/lean_s2_05_node_audit.py merge --output-root "$DIAG/audit/$G" --arm VSMT-lean --results "$RESULT" > "$LOG_DIR/merge-$G.log" 2>&1 || MERGES_FAILED=$((MERGES_FAILED + 1))
    ARGS+=(--cell "$POINT:$SEED:$RESULT")
    DIRS="$DIRS${DIRS:+,}$DIAG/audit/$G"
  done
  CELLS+=(--cell "$POINT:$DIRS")
done
$PY ops/vsmt/ruling93_tau_reading.py "${ARGS[@]}" --output "$EXPORT_DIR/vsmt_lean_ruling93_wp_reading_$COMMIT.json" > "$LOG_DIR/reading.log" 2>&1
READING_RC=$?
echo "[$(date)] metric reading exit $READING_RC"; cat "$LOG_DIR/reading.log"
$PY ops/vsmt/ruling93_residual_reading.py "${CELLS[@]}" --focus "$FOCUS" --output "$EXPORT_DIR/vsmt_lean_ruling93_wp_residuals_$COMMIT.json" > "$LOG_DIR/residuals.log" 2>&1
RESIDUAL_RC=$?
echo "[$(date)] residual reading exit $RESIDUAL_RC"; cat "$LOG_DIR/residuals.log"
finish done
