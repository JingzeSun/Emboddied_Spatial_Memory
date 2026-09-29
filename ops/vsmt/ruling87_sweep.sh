#!/bin/bash
# Ruling 87 revised (2026-09-29): the tau_r sweep on frozen heads. Node audit v8 over the 39 development episodes for
# VSMT-lean and NoVersion at tau_r 0.15, 0.2, 0.25 and 0.3 and the five registered seeds (40 groups, the trained heads of
# the ruling-81 and ruling-82 runs), per-group merges, the pre-registered two-tier reading against the ruling-86 exports
# (VSMT-lean at tau_r 0.5 and AssocOnly, commit 378008c), and a status file.  SHUTDOWN defaults to 0 (the user keeps the
# cheap single-GPU instance running); SHUTDOWN=1 powers off after GRACE_SECONDS.
#   In plain terms: read-only diagnostics; nothing is trained and no label, record, weight or contract byte is written.
# Run from a clean worktree at the commit to use:
#   (setsid nohup bash ops/vsmt/ruling87_sweep.sh > /root/autodl-tmp/vsmt_outputs/run_logs/ruling87-<commit>.log 2>&1 < /dev/null &)
# RESUME=1 skips the suite; finished audits (node_audit.json present) are always kept, so a rerun only does what is missing.
set -u
WORKTREE=$(cd "$(dirname "$0")/../.." && pwd)
cd "$WORKTREE" || exit 2
COMMIT=$(git rev-parse --short HEAD)
PY=/root/miniconda3/bin/python3.12
AUTODL=/root/autodl-tmp
OUTPUTS=$AUTODL/vsmt_outputs
EXPORT_DIR=$OUTPUTS/exports
LOG_DIR=$OUTPUTS/run_logs/ruling87-$COMMIT
CACHE_ROOT=$AUTODL/vsmt_caches/lean-s1-03-oracle-8ebbd05
GEOMETRY_ROOT=$AUTODL/vsmt_private/lean-s1-04-geometry-154776d
REID_WEIGHTS=$AUTODL/vsmt_private/lean-s1-04-diagnostics-oracle-caa50c7/reid_head_vitb14.json
PASS_ROOT=$AUTODL/vsmt_private/lean-s2-05-oracle-c150be0
R81=$AUTODL/vsmt_private/ruling81-0e4494d/training
R82=$AUTODL/vsmt_private/ruling82-18f943f/training
REFERENCE_COMMIT=378008c
DIAG=$AUTODL/vsmt_private/ruling87-$COMMIT
STATUS=$EXPORT_DIR/ruling87_sweep_$COMMIT.status.json
QUOTA=$(awk '{ if ($1 == "max") print 16; else print int($1 / $2) }' /sys/fs/cgroup/cpu.max 2>/dev/null || echo 16)
WORKERS=${WORKERS:-$((QUOTA - 1))}
GRACE_SECONDS=${GRACE_SECONDS:-1800}
SHUTDOWN=${SHUTDOWN:-0}
RESUME=${RESUME:-0}
SEEDS="7 19 31 43 59"
TAUS="0.15 0.2 0.25 0.3"
ARMS_RUN="VSMT-lean NoVersion"
mkdir -p "$EXPORT_DIR" "$LOG_DIR" "$DIAG"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

finish() {
  $PY -c "import json,sys,time; json.dump({'commit': '$COMMIT', 'stage_reached': sys.argv[1], 'finished_cst': time.strftime('%Y-%m-%d %H:%M:%S'),
    'suite_exit': '${SUITE_RC:-}', 'audits_ok': '${AUDITS_OK:-}', 'audits_failed': '${AUDITS_FAILED:-}', 'merges_failed': '${MERGES_FAILED:-}',
    'analysis_exit': '${ANALYSIS_RC:-}', 'workers_requested': $WORKERS, 'cpu_quota': $QUOTA,
    'worker_basis': 'cgroup CPU quota minus one; each audit is one single-threaded CPU process of about 1-2 GB',
    'shutdown_after_seconds': $GRACE_SECONDS, 'shutdown': $SHUTDOWN == 1}, open('$STATUS', 'w'), indent=1)" "$1"
  echo "[$(date)] status written ($1); shutdown=$SHUTDOWN"
  if [ "$SHUTDOWN" = "1" ]; then sleep "$GRACE_SECONDS"; echo "[$(date)] shutting down (AutoDL)"; /usr/bin/shutdown; fi
  exit 0
}

if [ -n "$(git status --porcelain)" ]; then echo "worktree not clean; refusing"; exit 2; fi
echo "[$(date)] ruling 87 tau_r sweep at $COMMIT on $(hostname): cpu quota $QUOTA, $WORKERS workers, memory.max $(cat /sys/fs/cgroup/memory.max)"

if [ "$RESUME" != "1" ]; then
  PYTHONPATH=src $PY -m unittest discover -s tests -t tests -p "test_*.py" > "$LOG_DIR/suite.log" 2>&1
  SUITE_RC=$?
  echo "[$(date)] suite exit $SUITE_RC: $(grep -E '^Ran |^OK|FAILED' "$LOG_DIR/suite.log" | tail -2 | tr '\n' ' ')"
  [ "$SUITE_RC" = "0" ] || finish suite_failed
fi

weights_of() {  # seed -> VSMT-lean's trained heads (NoVersion runs on them too)
  case $1 in 7|19) echo "$R81/VSMT-lean/A$1/weights.json";; *) echo "$R82/VSMT-lean/A$1/weights.json";; esac
}
episode_root() { for R in "$OUTPUTS/lean-s1-02a-5f9aa71" "$OUTPUTS/lean-s1-02b-5f9aa71"; do [ -d "$R/$1" ] && echo "$R/$1" && return; done; }
EPISODES=$(for E in $(ls "$PASS_ROOT/dagger_round_1"); do [ -f "$PASS_ROOT/dagger_round_1/$E/VSMT-lean/receipt.json" ] && echo "$E"; done)
echo "[$(date)] $(echo $EPISODES | wc -w) development episodes"
REF_ARGS=()
for SEED in $SEEDS; do
  W=$(weights_of $SEED); [ -f "$W" ] || { echo "missing $W"; finish weights_missing; }
  for ARM in VSMT-lean AssocOnly; do
    REF=$EXPORT_DIR/vsmt_lean_s2_05_node_audit_ruling86_$ARM-A${SEED}_$REFERENCE_COMMIT.json
    [ -f "$REF" ] || { echo "missing $REF"; finish reference_missing; }
    REF_ARGS+=(--reference "$ARM:$SEED:-:$REF")
  done
done

JOBS=$LOG_DIR/jobs.txt; : > "$JOBS"
for TAU in $TAUS; do
  for ARM in $ARMS_RUN; do
    for SEED in $SEEDS; do
      OUT=$DIAG/audit/$ARM-A$SEED-t$TAU
      for EP in $EPISODES; do
        [ -f "$OUT/$EP/$ARM/node_audit.json" ] && continue
        printf '%s\n' "$PY ops/vsmt/lean_s2_05_node_audit.py run --cache-root $CACHE_ROOT --episode-root $(episode_root $EP) --geometry-root $GEOMETRY_ROOT --episode-id $EP --arm $ARM --config '{\"tau_r\": $TAU}' --heads $(weights_of $SEED) --descriptor reid_projection:vitb14 --weights $REID_WEIGHTS --output-root $OUT --device cpu > $LOG_DIR/$ARM-A$SEED-t$TAU-$EP.log 2>&1; echo \"$ARM A$SEED t$TAU $EP exit \$?\"" >> "$JOBS"
      done
    done
  done
done
echo "[$(date)] $(wc -l < "$JOBS") audits queued on $WORKERS workers"
xargs -d '\n' -P "$WORKERS" -I{} bash -c '{}' < "$JOBS" > "$LOG_DIR/exits.log" 2>&1
AUDITS_OK=$(grep -c 'exit 0$' "$LOG_DIR/exits.log"); AUDITS_FAILED=$(grep -vc 'exit 0$' "$LOG_DIR/exits.log")
echo "[$(date)] audits: $AUDITS_OK ok, $AUDITS_FAILED failed"

MERGES_FAILED=0; SWEEP_ARGS=()
for TAU in $TAUS; do
  for ARM in $ARMS_RUN; do
    for SEED in $SEEDS; do
      RESULT=$EXPORT_DIR/vsmt_lean_s2_05_node_audit_ruling87_$ARM-A$SEED-t${TAU}_$COMMIT.json
      $PY ops/vsmt/lean_s2_05_node_audit.py merge --output-root "$DIAG/audit/$ARM-A$SEED-t$TAU" --arm "$ARM" --results "$RESULT" > "$LOG_DIR/merge-$ARM-A$SEED-t$TAU.log" 2>&1
      RC=$?; [ "$RC" = "0" ] || MERGES_FAILED=$((MERGES_FAILED + 1))
      echo "[$(date)] merge $ARM A$SEED t$TAU exit $RC"
      SWEEP_ARGS+=(--sweep "$ARM:$SEED:$TAU:$RESULT")
    done
  done
done
$PY ops/vsmt/ruling87_sweep_analysis.py "${SWEEP_ARGS[@]}" "${REF_ARGS[@]}" --output "$EXPORT_DIR/vsmt_lean_s2_05_ruling87_sweep_$COMMIT.json" > "$LOG_DIR/analysis.log" 2>&1
ANALYSIS_RC=$?
echo "[$(date)] analysis exit $ANALYSIS_RC"; cat "$LOG_DIR/analysis.log"
finish done
