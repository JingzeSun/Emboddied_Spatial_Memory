#!/bin/bash
# Ruling 89-1 (2026-09-30): the recall diagnostic on the decision-ceiling cell.  One shared queue: the O-V-node cell (teacher association +
#   teacher existence, node-primary labels, VSMT-lean vocabulary, tau_r 0.5) over the 39 development episodes at k' = 3, 5, 8 and 12
#   (node audit v10, --recall-global-count, which also records each moved object's original-carrier global rank); per-k merges; the reading
#   under the frozen rule (ruling89_recall.py: the first of 5, 8, 12 with at most 3 of 65 recall misses, none -> pause).
#   In plain terms: read-only diagnostics, private truth decides before the seals, so nothing here is a method, a table row or a record.
# Run from a clean worktree at the commit to use:
#   (setsid nohup bash ops/vsmt/ruling89_recall.sh > /root/autodl-tmp/vsmt_outputs/run_logs/ruling89-recall-<commit>.log 2>&1 < /dev/null &)
# WORKERS defaults to the CPU quota minus one; set it lower when another job shares the instance.  RESUME=1 skips the suite; finished
# audits are always kept, so a rerun only does what is missing.  The instance is never shut down here.
set -u
WORKTREE=$(cd "$(dirname "$0")/../.." && pwd)
cd "$WORKTREE" || exit 2
COMMIT=$(git rev-parse --short HEAD)
PY=/root/miniconda3/bin/python3.12
AUTODL=/root/autodl-tmp
OUTPUTS=$AUTODL/vsmt_outputs
EXPORT_DIR=$OUTPUTS/exports
LOG_DIR=$OUTPUTS/run_logs/ruling89-recall-$COMMIT
CACHE_ROOT=$AUTODL/vsmt_caches/lean-s1-03-oracle-8ebbd05
GEOMETRY_ROOT=$AUTODL/vsmt_private/lean-s1-04-geometry-154776d
REID_WEIGHTS=$AUTODL/vsmt_private/lean-s1-04-diagnostics-oracle-caa50c7/reid_head_vitb14.json
PASS_ROOT=$AUTODL/vsmt_private/lean-s2-05-oracle-c150be0
DIAG=$AUTODL/vsmt_private/ruling89-recall-$COMMIT
STATUS=$EXPORT_DIR/ruling89_recall_$COMMIT.status.json
QUOTA=$(awk '{ if ($1 == "max") print 16; else print int($1 / $2) }' /sys/fs/cgroup/cpu.max 2>/dev/null || echo 16)
WORKERS=${WORKERS:-$((QUOTA - 1))}
RESUME=${RESUME:-0}
KS="3 5 8 12"
mkdir -p "$EXPORT_DIR" "$LOG_DIR" "$DIAG"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

finish() {
  $PY -c "import json,sys,time; json.dump({'commit': '$COMMIT', 'stage_reached': sys.argv[1], 'finished_cst': time.strftime('%Y-%m-%d %H:%M:%S'),
    'suite_exit': '${SUITE_RC:-}', 'jobs_ok': '${JOBS_OK:-}', 'jobs_failed': '${JOBS_FAILED:-}', 'merges_failed': '${MERGES_FAILED:-}',
    'reading_exit': '${READING_RC:-}', 'workers_requested': $WORKERS, 'cpu_quota': $QUOTA, 'memory_max': '$(cat /sys/fs/cgroup/memory.max 2>/dev/null)',
    'worker_basis': 'CPU quota minus the cores the concurrent confirmation-set generation uses; every audit is one single-threaded CPU process of about 1-3 GB',
    'queue_order': 'k=3 first, then 5, 8, 12, episode by episode; merges in that order', 'shutdown': False}, open('$STATUS', 'w'), indent=1)" "$1"
  echo "[$(date)] status written ($1)"
  exit 0
}

if [ -n "$(git status --porcelain)" ]; then echo "worktree not clean; refusing"; exit 2; fi
echo "[$(date)] ruling 89-1 at $COMMIT on $(hostname): cpu quota $QUOTA, $WORKERS workers, memory.max $(cat /sys/fs/cgroup/memory.max)"
if [ "$RESUME" != "1" ]; then
  PYTHONPATH=src $PY -m unittest discover -s tests -t tests -p "test_*.py" > "$LOG_DIR/suite.log" 2>&1
  SUITE_RC=$?
  echo "[$(date)] suite exit $SUITE_RC: $(grep -E '^Ran |^OK|FAILED' "$LOG_DIR/suite.log" | tail -2 | tr '\n' ' ')"
  [ "$SUITE_RC" = "0" ] || finish suite_failed
fi

episode_root() { for R in "$OUTPUTS/lean-s1-02a-5f9aa71" "$OUTPUTS/lean-s1-02b-5f9aa71"; do [ -d "$R/$1" ] && echo "$R/$1" && return; done; }
EPISODES=$(for E in $(ls "$PASS_ROOT/dagger_round_1"); do [ -f "$PASS_ROOT/dagger_round_1/$E/VSMT-lean/receipt.json" ] && echo "$E"; done)
echo "[$(date)] $(echo $EPISODES | wc -w) development episodes"
JOBS=$LOG_DIR/jobs.txt; : > "$JOBS"
for K in $KS; do
  OUT=$DIAG/audit/O-V-node-k$K
  for EP in $EPISODES; do
    [ -f "$OUT/$EP/VSMT-lean/node_audit.json" ] && continue
    printf '%s\n' "$PY ops/vsmt/lean_s2_05_node_audit.py run --cache-root $CACHE_ROOT --episode-root $(episode_root $EP) --geometry-root $GEOMETRY_ROOT --episode-id $EP --arm VSMT-lean --config '{\"tau_r\": 0.5}' --oracle-association --oracle-existence node_primary --recall-global-count $K --descriptor reid_projection:vitb14 --weights $REID_WEIGHTS --output-root $OUT --device cpu > $LOG_DIR/k$K-$EP.log 2>&1; echo \"k$K $EP exit \$?\"" >> "$JOBS"
  done
done
echo "[$(date)] $(wc -l < "$JOBS") jobs queued on $WORKERS workers"
xargs -d '\n' -P "$WORKERS" -I{} bash -c '{}' < "$JOBS" >> "$LOG_DIR/exits.log" 2>&1
JOBS_OK=$(grep -c 'exit 0$' "$LOG_DIR/exits.log"); JOBS_FAILED=$(grep -vc 'exit 0$' "$LOG_DIR/exits.log")
echo "[$(date)] jobs: $JOBS_OK ok, $JOBS_FAILED failed"

MERGES_FAILED=0; ARGS=()
for K in $KS; do
  RESULT=$EXPORT_DIR/vsmt_lean_ruling89_recall_O-V-node-k${K}_$COMMIT.json
  $PY ops/vsmt/lean_s2_05_node_audit.py merge --output-root "$DIAG/audit/O-V-node-k$K" --arm VSMT-lean --results "$RESULT" > "$LOG_DIR/merge-k$K.log" 2>&1
  RC=$?; [ "$RC" = "0" ] || MERGES_FAILED=$((MERGES_FAILED + 1))
  echo "[$(date)] merge k$K exit $RC"
  ARGS+=(--cell "$K:$RESULT")
done
$PY ops/vsmt/ruling89_recall.py "${ARGS[@]}" --output "$EXPORT_DIR/vsmt_lean_ruling89_recall_$COMMIT.json" > "$LOG_DIR/reading.log" 2>&1
READING_RC=$?
echo "[$(date)] reading exit $READING_RC"; cat "$LOG_DIR/reading.log"
finish done
