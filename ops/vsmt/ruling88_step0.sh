#!/bin/bash
# Ruling 88-2 (2026-09-29): the step-0 package.  One shared queue on quota-minus-one workers:
#   P3 imitation sufficiency (five rule targets), P2 trained-head sensitivity (five seeds), P1 state coverage, then the node audits of the
#   teacher-as-policy decision ceiling -- six deterministic cells (O-V-node, O-V-legacy, O-N-node, O-N-legacy, O-A, O-V-node-recall) and
#   the 2x2 mixed cells (OA-LE teacher association + learned existence, LA-OE learned association + teacher existence) on the five seeds of
#   the ruling-81/82 heads -- over the 39 development episodes; per-cell merges; the reading pre-registered in ruling 88-2
#   (ruling88_analysis.py) against the ruling-86 learned audits and the LOG-270 rule-arm reports; a status file.
#   In plain terms: read-only diagnostics.  The oracle cells let private truth decide before the seals, so nothing here is a method, a
#   table row or a training record; P3 trains diagnostic heads only.  SHUTDOWN defaults to 0 (the cheap instance stays up).
# Run from a clean worktree at the commit to use:
#   (WAIT_FOR=<ruling-87 status file> setsid nohup bash ops/vsmt/ruling88_step0.sh > /root/autodl-tmp/vsmt_outputs/run_logs/ruling88-<commit>.log 2>&1 < /dev/null &)
# WAIT_FOR makes the driver poll (every 5 minutes) until that file exists, so it starts only after the tau_r sweep has finished.
# RESUME=1 skips the suite; finished audits and probe outputs are always kept, so a rerun only does what is missing.
set -u
WORKTREE=$(cd "$(dirname "$0")/../.." && pwd)
cd "$WORKTREE" || exit 2
COMMIT=$(git rev-parse --short HEAD)
PY=/root/miniconda3/bin/python3.12
AUTODL=/root/autodl-tmp
OUTPUTS=$AUTODL/vsmt_outputs
EXPORT_DIR=$OUTPUTS/exports
LOG_DIR=$OUTPUTS/run_logs/ruling88-$COMMIT
CACHE_ROOT=$AUTODL/vsmt_caches/lean-s1-03-oracle-8ebbd05
GEOMETRY_ROOT=$AUTODL/vsmt_private/lean-s1-04-geometry-154776d
REID_WEIGHTS=$AUTODL/vsmt_private/lean-s1-04-diagnostics-oracle-caa50c7/reid_head_vitb14.json
PASS_ROOT=$AUTODL/vsmt_private/lean-s2-05-oracle-c150be0
R81=$AUTODL/vsmt_private/ruling81-0e4494d/training
R82=$AUTODL/vsmt_private/ruling82-18f943f/training
DIAG=$AUTODL/vsmt_private/ruling88-$COMMIT
PROBES=$DIAG/probes
STATUS=$EXPORT_DIR/ruling88_step0_$COMMIT.status.json
QUOTA=$(awk '{ if ($1 == "max") print 16; else print int($1 / $2) }' /sys/fs/cgroup/cpu.max 2>/dev/null || echo 16)
WORKERS=${WORKERS:-$((QUOTA - 1))}
GRACE_SECONDS=${GRACE_SECONDS:-1800}
SHUTDOWN=${SHUTDOWN:-0}
RESUME=${RESUME:-0}
WAIT_FOR=${WAIT_FOR:-}
SEEDS="7 19 31 43 59"
TARGETS="taf low handcost rac elup"
CELLS="O-V-node O-V-legacy O-N-node O-N-legacy O-A O-V-node-recall"
mkdir -p "$EXPORT_DIR" "$LOG_DIR" "$DIAG" "$PROBES/imitation"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

finish() {
  $PY -c "import json,sys,time; json.dump({'commit': '$COMMIT', 'stage_reached': sys.argv[1], 'finished_cst': time.strftime('%Y-%m-%d %H:%M:%S'),
    'suite_exit': '${SUITE_RC:-}', 'jobs_ok': '${JOBS_OK:-}', 'jobs_failed': '${JOBS_FAILED:-}', 'merges_failed': '${MERGES_FAILED:-}',
    'analysis_exit': '${ANALYSIS_RC:-}', 'workers_requested': $WORKERS, 'cpu_quota': $QUOTA, 'memory_max': '$(cat /sys/fs/cgroup/memory.max 2>/dev/null)',
    'worker_basis': 'cgroup CPU quota minus one; every job is one single-threaded CPU process: an audit about 1-2 GB, a P3 association imitation about 6-10 GB, the rest under 2 GB',
    'queue_order': 'P3 imitation, P2 sensitivity, P1 coverage, then the audits cell by cell and episode by episode; merges in the fixed cell order',
    'shutdown_after_seconds': $GRACE_SECONDS, 'shutdown': $SHUTDOWN == 1}, open('$STATUS', 'w'), indent=1)" "$1"
  echo "[$(date)] status written ($1); shutdown=$SHUTDOWN"
  if [ "$SHUTDOWN" = "1" ]; then sleep "$GRACE_SECONDS"; echo "[$(date)] shutting down (AutoDL)"; /usr/bin/shutdown; fi
  exit 0
}

if [ -n "$(git status --porcelain)" ]; then echo "worktree not clean; refusing"; exit 2; fi
if [ -n "$WAIT_FOR" ]; then
  echo "[$(date)] waiting for $WAIT_FOR"
  while [ ! -f "$WAIT_FOR" ]; do sleep 300; done
  echo "[$(date)] found $WAIT_FOR; starting"
fi
echo "[$(date)] ruling 88 step 0 at $COMMIT on $(hostname): cpu quota $QUOTA, $WORKERS workers, memory.max $(cat /sys/fs/cgroup/memory.max)"

if [ "$RESUME" != "1" ]; then
  PYTHONPATH=src $PY -m unittest discover -s tests -t tests -p "test_*.py" > "$LOG_DIR/suite.log" 2>&1
  SUITE_RC=$?
  echo "[$(date)] suite exit $SUITE_RC: $(grep -E '^Ran |^OK|FAILED' "$LOG_DIR/suite.log" | tail -2 | tr '\n' ' ')"
  [ "$SUITE_RC" = "0" ] || finish suite_failed
fi

weights_of() {  # seed -> VSMT-lean's trained heads (ruling 81 seeds 7/19, ruling 82 seeds 31/43/59)
  case $1 in 7|19) echo "$R81/VSMT-lean/A$1/weights.json";; *) echo "$R82/VSMT-lean/A$1/weights.json";; esac
}
cell_arm() { case $1 in O-N-*) echo NoVersion;; O-A) echo AssocOnly;; *) echo VSMT-lean;; esac; }
cell_config() { case $1 in O-A) echo '{}';; *) echo '{"tau_r": 0.5}';; esac; }
cell_flags() {
  case $1 in
    O-V-node|O-N-node) echo "--oracle-association --oracle-existence node_primary";;
    O-V-legacy|O-N-legacy) echo "--oracle-association --oracle-existence centroid_only";;
    O-A) echo "--oracle-association";;
    O-V-node-recall) echo "--oracle-association --oracle-existence node_primary --oracle-recall";;
    OA-LE) echo "--oracle-association";;
    LA-OE) echo "--oracle-existence node_primary";;
  esac
}
episode_root() { for R in "$OUTPUTS/lean-s1-02a-5f9aa71" "$OUTPUTS/lean-s1-02b-5f9aa71"; do [ -d "$R/$1" ] && echo "$R/$1" && return; done; }
for SEED in $SEEDS; do W=$(weights_of $SEED); [ -f "$W" ] || { echo "missing $W"; finish weights_missing; }; done
EPISODES=$(for E in $(ls "$PASS_ROOT/dagger_round_1"); do [ -f "$PASS_ROOT/dagger_round_1/$E/VSMT-lean/receipt.json" ] && echo "$E"; done)
echo "[$(date)] $(echo $EPISODES | wc -w) development episodes"

JOBS=$LOG_DIR/jobs.txt; : > "$JOBS"
for T in $TARGETS; do
  [ -f "$PROBES/imitation/imitation_$T.json" ] && continue
  printf '%s\n' "$PY ops/vsmt/ruling88_probes.py imitation --output-root $PASS_ROOT --target $T --output-dir $PROBES/imitation > $LOG_DIR/p3-$T.log 2>&1; echo \"P3 $T exit \$?\"" >> "$JOBS"
done
for SEED in $SEEDS; do
  [ -f "$PROBES/sensitivity-A$SEED.json" ] && continue
  printf '%s\n' "$PY ops/vsmt/ruling88_probes.py sensitivity --output-root $PASS_ROOT --weights $(weights_of $SEED) --label A$SEED --output $PROBES/sensitivity-A$SEED.json > $LOG_DIR/p2-A$SEED.log 2>&1; echo \"P2 A$SEED exit \$?\"" >> "$JOBS"
done
[ -f "$PROBES/coverage.json" ] || printf '%s\n' "$PY ops/vsmt/ruling88_probes.py coverage --output-root $PASS_ROOT --pass dagger_round_0:ELU-P --pass dagger_round_1:VSMT-lean --output $PROBES/coverage.json > $LOG_DIR/p1.log 2>&1; echo \"P1 coverage exit \$?\"" >> "$JOBS"
GROUPS_RUN=""
for CELL in $CELLS; do GROUPS_RUN="$GROUPS_RUN $CELL"; done
for SEED in $SEEDS; do GROUPS_RUN="$GROUPS_RUN OA-LE-A$SEED LA-OE-A$SEED"; done
for GROUP in $GROUPS_RUN; do
  CELL=${GROUP%-A[0-9]*}; SEED=${GROUP##*-A}; [ "$SEED" = "$GROUP" ] && SEED=""
  ARM=$(cell_arm "$CELL"); CONFIG=$(cell_config "$CELL"); FLAGS=$(cell_flags "$CELL")
  HEADS=""; [ -n "$SEED" ] && HEADS="--heads $(weights_of $SEED)"
  OUT=$DIAG/audit/$GROUP
  for EP in $EPISODES; do
    [ -f "$OUT/$EP/$ARM/node_audit.json" ] && continue
    printf '%s\n' "$PY ops/vsmt/lean_s2_05_node_audit.py run --cache-root $CACHE_ROOT --episode-root $(episode_root $EP) --geometry-root $GEOMETRY_ROOT --episode-id $EP --arm $ARM --config '$CONFIG' $FLAGS $HEADS --descriptor reid_projection:vitb14 --weights $REID_WEIGHTS --output-root $OUT --device cpu > $LOG_DIR/$GROUP-$EP.log 2>&1; echo \"$GROUP $EP exit \$?\"" >> "$JOBS"
  done
done
echo "[$(date)] $(wc -l < "$JOBS") jobs queued on $WORKERS workers"
xargs -d '\n' -P "$WORKERS" -I{} bash -c '{}' < "$JOBS" > "$LOG_DIR/exits.log" 2>&1
JOBS_OK=$(grep -c 'exit 0$' "$LOG_DIR/exits.log"); JOBS_FAILED=$(grep -vc 'exit 0$' "$LOG_DIR/exits.log")
echo "[$(date)] jobs: $JOBS_OK ok, $JOBS_FAILED failed"

MERGES_FAILED=0; ARGS=()
for GROUP in $GROUPS_RUN; do
  CELL=${GROUP%-A[0-9]*}; SEED=${GROUP##*-A}; [ "$SEED" = "$GROUP" ] && SEED=""
  ARM=$(cell_arm "$CELL")
  RESULT=$EXPORT_DIR/vsmt_lean_ruling88_audit_${GROUP}_$COMMIT.json
  $PY ops/vsmt/lean_s2_05_node_audit.py merge --output-root "$DIAG/audit/$GROUP" --arm "$ARM" --results "$RESULT" > "$LOG_DIR/merge-$GROUP.log" 2>&1
  RC=$?; [ "$RC" = "0" ] || MERGES_FAILED=$((MERGES_FAILED + 1))
  echo "[$(date)] merge $GROUP exit $RC"
  if [ -n "$SEED" ]; then ARGS+=(--mixed "$CELL:$SEED:$RESULT"); else ARGS+=(--cell "$CELL:$RESULT"); fi
done
for SEED in $SEEDS; do ARGS+=(--learned "$SEED:$WORKTREE/results/vsmt_lean_s2_05_node_audit_ruling86_VSMT-lean-A${SEED}_378008c.json"); done
for ARM in TAF RAC LOW; do ARGS+=(--rule-arm "$ARM:$WORKTREE/results/vsmt_lean_s2_05_development_table_${ARM}_oracle_8ce7b0b.json"); done
ARGS+=(--rule-arm "ELU-P:$WORKTREE/results/vsmt_lean_s2_05_dagger_round_0_oracle_c150be0.json")
cp "$PROBES/coverage.json" "$EXPORT_DIR/vsmt_lean_ruling88_p1_coverage_$COMMIT.json" 2>/dev/null && ARGS+=(--coverage "$EXPORT_DIR/vsmt_lean_ruling88_p1_coverage_$COMMIT.json")
for SEED in $SEEDS; do
  F=$PROBES/sensitivity-A$SEED.json
  [ -f "$F" ] && cp "$F" "$EXPORT_DIR/vsmt_lean_ruling88_p2_sensitivity_A${SEED}_$COMMIT.json" && ARGS+=(--sensitivity "A$SEED:$EXPORT_DIR/vsmt_lean_ruling88_p2_sensitivity_A${SEED}_$COMMIT.json")
done
for T in $TARGETS; do
  F=$PROBES/imitation/imitation_$T.json
  [ -f "$F" ] && cp "$F" "$EXPORT_DIR/vsmt_lean_ruling88_p3_imitation_${T}_$COMMIT.json" && ARGS+=(--imitation "$T:$EXPORT_DIR/vsmt_lean_ruling88_p3_imitation_${T}_$COMMIT.json")
done
$PY ops/vsmt/ruling88_analysis.py "${ARGS[@]}" --output "$EXPORT_DIR/vsmt_lean_ruling88_step0_$COMMIT.json" > "$LOG_DIR/analysis.log" 2>&1
ANALYSIS_RC=$?
echo "[$(date)] analysis exit $ANALYSIS_RC"; cat "$LOG_DIR/analysis.log"
finish done
