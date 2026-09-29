#!/bin/bash
# Ruling 86-0 (2026-09-29): node audit v7 over the 39 development episodes for VSMT-lean, AssocOnly and NoVersion at the
# five registered seeds (15 groups, the trained heads of the ruling-81 and ruling-82 runs), then per-group merges, the
# identity-attribution reading, a status file and (SHUTDOWN=1, the default) an AutoDL shutdown after GRACE_SECONDS.
#   In plain terms: read-only diagnostics; no label, record, weight or contract byte is written; nothing is trained.
# Run from a clean worktree at the commit to use:
#   (setsid nohup bash ops/vsmt/ruling86_attribution.sh > /root/autodl-tmp/vsmt_outputs/run_logs/ruling86-<commit>.log 2>&1 < /dev/null &)
# RESUME=1 skips the suite; finished audits (node_audit.json present) are always kept, so a rerun only does what is missing.
set -u
WORKTREE=$(cd "$(dirname "$0")/../.." && pwd)
cd "$WORKTREE" || exit 2
COMMIT=$(git rev-parse --short HEAD)
PY=/root/miniconda3/bin/python3.12
AUTODL=/root/autodl-tmp
OUTPUTS=$AUTODL/vsmt_outputs
EXPORT_DIR=$OUTPUTS/exports
LOG_DIR=$OUTPUTS/run_logs/ruling86-$COMMIT
CACHE_ROOT=$AUTODL/vsmt_caches/lean-s1-03-oracle-8ebbd05
GEOMETRY_ROOT=$AUTODL/vsmt_private/lean-s1-04-geometry-154776d
REID_WEIGHTS=$AUTODL/vsmt_private/lean-s1-04-diagnostics-oracle-caa50c7/reid_head_vitb14.json
PASS_ROOT=$AUTODL/vsmt_private/lean-s2-05-oracle-c150be0
R81=$AUTODL/vsmt_private/ruling81-0e4494d/training
R82=$AUTODL/vsmt_private/ruling82-18f943f/training
DIAG=$AUTODL/vsmt_private/ruling86-$COMMIT
STATUS=$EXPORT_DIR/ruling86_attribution_$COMMIT.status.json
QUOTA=$(awk '{ if ($1 == "max") print 16; else print int($1 / $2) }' /sys/fs/cgroup/cpu.max 2>/dev/null || echo 16)
WORKERS=${WORKERS:-$((QUOTA - 1))}
GRACE_SECONDS=${GRACE_SECONDS:-1800}
SHUTDOWN=${SHUTDOWN:-1}
RESUME=${RESUME:-0}
SEEDS="7 19 31 43 59"
ARMS_RUN="VSMT-lean AssocOnly NoVersion"
mkdir -p "$EXPORT_DIR" "$LOG_DIR" "$DIAG"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

finish() {
  $PY -c "import json,sys,time; json.dump({'commit': '$COMMIT', 'stage_reached': sys.argv[1], 'finished_cst': time.strftime('%Y-%m-%d %H:%M:%S'),
    'suite_exit': '${SUITE_RC:-}', 'audits_ok': '${AUDITS_OK:-}', 'audits_failed': '${AUDITS_FAILED:-}', 'merges_failed': '${MERGES_FAILED:-}',
    'analysis_exit': '${ANALYSIS_RC:-}', 'workers_requested': $WORKERS, 'cpu_quota': $QUOTA,
    'worker_basis': 'cgroup CPU quota minus one; each audit is one single-threaded CPU process of about 1-2 GB',
    'shutdown_after_seconds': $GRACE_SECONDS, 'shutdown': $SHUTDOWN == 1}, open('$STATUS', 'w'), indent=1)" "$1"
  echo "[$(date)] status written ($1); shutdown=$SHUTDOWN after $GRACE_SECONDS s"
  if [ "$SHUTDOWN" = "1" ]; then sleep "$GRACE_SECONDS"; echo "[$(date)] shutting down (AutoDL)"; /usr/bin/shutdown; fi
  exit 0
}

if [ -n "$(git status --porcelain)" ]; then echo "worktree not clean; refusing"; exit 2; fi
if ps -eo args | grep -v grep | grep -E "^sleep [0-9]+$|/usr/bin/shutdown" >/dev/null; then echo "a pending sleep/shutdown exists; refusing"; exit 2; fi
echo "[$(date)] ruling 86-0 attribution at $COMMIT on $(hostname): cpu quota $QUOTA, $WORKERS workers, memory.max $(cat /sys/fs/cgroup/memory.max)"

if [ "$RESUME" != "1" ]; then
  PYTHONPATH=src $PY -m unittest discover -s tests -t tests -p "test_*.py" > "$LOG_DIR/suite.log" 2>&1
  SUITE_RC=$?
  echo "[$(date)] suite exit $SUITE_RC: $(grep -E '^Ran |^OK|FAILED' "$LOG_DIR/suite.log" | tail -2 | tr '\n' ' ')"
  [ "$SUITE_RC" = "0" ] || finish suite_failed
fi

weights_of() {  # arm seed -> the trained heads (NoVersion runs on VSMT-lean's heads)
  local HEAD_ARM=$1; [ "$1" = "NoVersion" ] && HEAD_ARM=VSMT-lean
  case $2 in 7|19) echo "$R81/$HEAD_ARM/A$2/weights.json";; *) echo "$R82/$HEAD_ARM/A$2/weights.json";; esac
}
config_of() { case $1 in AssocOnly) echo '{}';; *) echo '{"tau_r": 0.5}';; esac; }
episode_root() { for R in "$OUTPUTS/lean-s1-02a-5f9aa71" "$OUTPUTS/lean-s1-02b-5f9aa71"; do [ -d "$R/$1" ] && echo "$R/$1" && return; done; }
EPISODES=$(for E in $(ls "$PASS_ROOT/dagger_round_1"); do [ -f "$PASS_ROOT/dagger_round_1/$E/VSMT-lean/receipt.json" ] && echo "$E"; done)
echo "[$(date)] $(echo $EPISODES | wc -w) development episodes"
for ARM in $ARMS_RUN; do for SEED in $SEEDS; do
  W=$(weights_of $ARM $SEED); [ -f "$W" ] || { echo "missing $W"; finish weights_missing; }
done; done

JOBS=$LOG_DIR/jobs.txt; : > "$JOBS"
for ARM in $ARMS_RUN; do
  for SEED in $SEEDS; do
    OUT=$DIAG/audit/$ARM-A$SEED
    for EP in $EPISODES; do
      [ -f "$OUT/$EP/$ARM/node_audit.json" ] && continue
      printf '%s\n' "$PY ops/vsmt/lean_s2_05_node_audit.py run --cache-root $CACHE_ROOT --episode-root $(episode_root $EP) --geometry-root $GEOMETRY_ROOT --episode-id $EP --arm $ARM --config '$(config_of $ARM)' --heads $(weights_of $ARM $SEED) --descriptor reid_projection:vitb14 --weights $REID_WEIGHTS --output-root $OUT --device cpu > $LOG_DIR/$ARM-A$SEED-$EP.log 2>&1; echo \"$ARM A$SEED $EP exit \$?\"" >> "$JOBS"
    done
  done
done
echo "[$(date)] $(wc -l < "$JOBS") audits queued on $WORKERS workers (largest episodes last in no particular order; xargs keeps quotes with -d newline)"
xargs -d '\n' -P "$WORKERS" -I{} bash -c '{}' < "$JOBS" > "$LOG_DIR/exits.log" 2>&1
AUDITS_OK=$(grep -c 'exit 0$' "$LOG_DIR/exits.log"); AUDITS_FAILED=$(grep -vc 'exit 0$' "$LOG_DIR/exits.log")
echo "[$(date)] audits: $AUDITS_OK ok, $AUDITS_FAILED failed"

MERGES_FAILED=0; GROUP_ARGS=()
for ARM in $ARMS_RUN; do
  for SEED in $SEEDS; do
    RESULT=$EXPORT_DIR/vsmt_lean_s2_05_node_audit_ruling86_$ARM-A${SEED}_$COMMIT.json
    $PY ops/vsmt/lean_s2_05_node_audit.py merge --output-root "$DIAG/audit/$ARM-A$SEED" --arm "$ARM" --results "$RESULT" > "$LOG_DIR/merge-$ARM-A$SEED.log" 2>&1
    RC=$?; [ "$RC" = "0" ] || MERGES_FAILED=$((MERGES_FAILED + 1))
    echo "[$(date)] merge $ARM A$SEED exit $RC"
    GROUP_ARGS+=(--group "$ARM:$SEED:$RESULT")
  done
done
$PY ops/vsmt/identity_attribution_analysis.py "${GROUP_ARGS[@]}" --output "$EXPORT_DIR/vsmt_lean_s2_05_identity_attribution_$COMMIT.json" > "$LOG_DIR/analysis.log" 2>&1
ANALYSIS_RC=$?
echo "[$(date)] analysis exit $ANALYSIS_RC"; cat "$LOG_DIR/analysis.log"
finish done
