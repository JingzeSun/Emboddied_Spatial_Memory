#!/bin/bash
# Ruling 93, revised (a) (2026-09-30): threshold-sensitivity diagnostic plus read-only scores, no training.
#   The five round-1 heads of ruling93-9722290 (the kept epoch-0 checkpoints) in the teacher-association + learned-existence
#   cell at the pre-registered tau_r 0.15 / 0.2 / 0.3 (5 seeds x 39 episodes x 3 = 585 audits, largest episode first), the
#   existing tau_r 0.5 cell as the reference, and in parallel ruling93_scores.py (existence score distributions and the two
#   loss terms at the kept checkpoint).  It selects no threshold, trains nothing, starts no 89-4.  Never shuts down.
set -u
WORKTREE=$(cd "$(dirname "$0")/../.." && pwd)
cd "$WORKTREE" || exit 2
COMMIT=$(git rev-parse --short HEAD)
PY=/root/miniconda3/bin/python3.12
AUTODL=/root/autodl-tmp
OUTPUTS=$AUTODL/vsmt_outputs
EXPORT_DIR=$OUTPUTS/exports
LOG_DIR=$OUTPUTS/run_logs/ruling93-tau-$COMMIT
CACHE_ROOT=$AUTODL/vsmt_caches/lean-s1-03-oracle-8ebbd05
GEOMETRY_ROOT=$AUTODL/vsmt_private/lean-s1-04-geometry-154776d
REID_WEIGHTS=$AUTODL/vsmt_private/lean-s1-04-diagnostics-oracle-caa50c7/reid_head_vitb14.json
PASS_ROOT=$AUTODL/vsmt_private/lean-s2-05-oracle-c150be0
HEADS_TAG=9722290
HEADS_ROOT=$AUTODL/vsmt_private/ruling93-$HEADS_TAG
FIRST=$AUTODL/vsmt_private/ruling89-sides-003b906
DIAG=$AUTODL/vsmt_private/ruling93-tau-$COMMIT
STATUS=$EXPORT_DIR/ruling93_tau_$COMMIT.status.json
QUOTA=$(awk '{ if ($1 == "max") print 16; else print int($1 / $2) }' /sys/fs/cgroup/cpu.max 2>/dev/null || echo 16)
WORKERS=${WORKERS:-$((QUOTA - 6))}
RESUME=${RESUME:-0}
SEEDS="7 19 31 43 59"
TAUS="0.15 0.2 0.3"
mkdir -p "$EXPORT_DIR" "$LOG_DIR" "$DIAG"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
count_bad() { [ -f "$1" ] || { echo 0; return; }; grep -vc 'exit 0$' "$1"; return 0; }
finish() {
  $PY -c "import json,sys,time; json.dump({'commit': '$COMMIT', 'stage_reached': sys.argv[1], 'finished_cst': time.strftime('%Y-%m-%d %H:%M:%S'),
    'suite_exit': '${SUITE_RC:-}', 'audits_failed': '${AUDITS_FAILED:-}', 'scores_exit': '${SCORES_RC:-}', 'merges_failed': '${MERGES_FAILED:-}',
    'reading_exit': '${READING_RC:-}', 'heads': '$HEADS_ROOT', 'workers': $WORKERS, 'cpu_quota': $QUOTA,
    'worker_basis': 'cgroup CPU quota minus six (one scores process with 4 threads alongside); audits single-threaded, largest episode first',
    'shutdown': False}, open('$STATUS', 'w'), indent=1)" "$1"
  echo "[$(date)] status written ($1)"; exit 0
}
if [ -n "$(git status --porcelain)" ]; then echo "worktree not clean; refusing"; exit 2; fi
echo "[$(date)] ruling 93 tau sweep at $COMMIT: cpu quota $QUOTA, $WORKERS workers"
if [ "$RESUME" != "1" ]; then
  PYTHONPATH=src $PY -m unittest discover -s tests -t tests -p "test_*.py" > "$LOG_DIR/suite.log" 2>&1
  SUITE_RC=$?
  echo "[$(date)] suite exit $SUITE_RC: $(grep -E '^Ran |^OK|FAILED' "$LOG_DIR/suite.log" | tail -2 | tr '\n' ' ')"
  [ "$SUITE_RC" = "0" ] || finish suite_failed
fi
for SEED in $SEEDS; do
  [ -f "$HEADS_ROOT/training/round1/VSMT-lean/A$SEED/weights.json" ] || finish heads_missing
  [ -f "$EXPORT_DIR/vsmt_lean_ruling93_audit_OA-LE-r93-A${SEED}_$HEADS_TAG.json" ] || finish reference_cell_missing
done
WEIGHT_ARGS=(); for SEED in $SEEDS; do WEIGHT_ARGS+=(--weights "$SEED:$HEADS_ROOT/training/round1/VSMT-lean/A$SEED/weights.json"); done
OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 PYTHONPATH=src $PY ops/vsmt/ruling93_scores.py --source "$FIRST:dagger_round_0:ELU-P" \
  --source "$HEADS_ROOT:dagger_round_1:VSMT-lean" "${WEIGHT_ARGS[@]}" --output "$EXPORT_DIR/vsmt_lean_ruling93_scores_$COMMIT.json" > "$LOG_DIR/scores.log" 2>&1 &
SCORES_PID=$!
episode_root() { for R in "$OUTPUTS/lean-s1-02a-5f9aa71" "$OUTPUTS/lean-s1-02b-5f9aa71"; do [ -d "$R/$1" ] && echo "$R/$1" && return; done; }
frames_of() { ls "$CACHE_ROOT/$1" | grep -c 'cache.json.gz$'; }
EPISODES=$(for E in $(ls "$PASS_ROOT/dagger_round_1"); do [ -f "$PASS_ROOT/dagger_round_1/$E/VSMT-lean/receipt.json" ] && echo "$E"; done)
JOBS=$LOG_DIR/jobs.txt
for TAU in $TAUS; do for SEED in $SEEDS; do
  G=OA-LE-tau$TAU-A$SEED; OUT=$DIAG/audit/$G; W=$HEADS_ROOT/training/round1/VSMT-lean/A$SEED/weights.json
  for EP in $EPISODES; do
    [ -f "$OUT/$EP/VSMT-lean/node_audit.json" ] && continue
    printf '%s\t%s\n' "$(frames_of $EP)" "$PY ops/vsmt/lean_s2_05_node_audit.py run --cache-root $CACHE_ROOT --episode-root $(episode_root $EP) --geometry-root $GEOMETRY_ROOT --episode-id $EP --arm VSMT-lean --config '{\"tau_r\": $TAU}' --oracle-association --heads $W --descriptor reid_projection:vitb14 --weights $REID_WEIGHTS --output-root $OUT --device cpu > $LOG_DIR/$G-$EP.log 2>&1; echo \"$G $EP exit \$?\""
  done
done; done | sort -t$'\t' -k1,1nr | cut -f2- > "$JOBS"
echo "[$(date)] $(wc -l < "$JOBS") audits queued (largest episode first); scores running as pid $SCORES_PID"
xargs -d '\n' -P "$WORKERS" -I{} bash -c '{}' < "$JOBS" >> "$LOG_DIR/exits.log" 2>&1
AUDITS_FAILED=$(count_bad "$LOG_DIR/exits.log")
echo "[$(date)] audits: $(grep -c 'exit 0$' "$LOG_DIR/exits.log") ok, $AUDITS_FAILED failed"
MERGES_FAILED=0; ARGS=()
for TAU in $TAUS; do for SEED in $SEEDS; do
  G=OA-LE-tau$TAU-A$SEED; RESULT=$EXPORT_DIR/vsmt_lean_ruling93_audit_${G}_$COMMIT.json
  $PY ops/vsmt/lean_s2_05_node_audit.py merge --output-root "$DIAG/audit/$G" --arm VSMT-lean --results "$RESULT" > "$LOG_DIR/merge-$G.log" 2>&1 || MERGES_FAILED=$((MERGES_FAILED + 1))
  ARGS+=(--cell "$TAU:$SEED:$RESULT")
done; done
for SEED in $SEEDS; do ARGS+=(--cell "0.5:$SEED:$EXPORT_DIR/vsmt_lean_ruling93_audit_OA-LE-r93-A${SEED}_$HEADS_TAG.json"); done
wait $SCORES_PID; SCORES_RC=$?
echo "[$(date)] scores exit $SCORES_RC"; tail -5 "$LOG_DIR/scores.log"
$PY ops/vsmt/ruling93_tau_reading.py "${ARGS[@]}" --output "$EXPORT_DIR/vsmt_lean_ruling93_tau_reading_$COMMIT.json" > "$LOG_DIR/reading.log" 2>&1
READING_RC=$?
echo "[$(date)] reading exit $READING_RC"; cat "$LOG_DIR/reading.log"
finish done
