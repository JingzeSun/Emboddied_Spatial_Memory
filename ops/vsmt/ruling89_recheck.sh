#!/bin/bash
# Ruling 89-2 / 89-3 re-check after the ASTRA review (2026-09-30), on the provisional k' = 3 artifacts of diag root
#   ruling89-sides-003b906, nothing retrained for the method:
#   1. the history summaries against independent executors (ruling89_history_audit.py): ELU-P at the rollout configuration and
#      RAC at rho 0.70 / 0.85 x n 2 / 3 / 5 run by the runner on the 39 development episodes, every eligible row compared with the
#      arm's own decisions and state, plus the deliberately wrong summary that must be caught;
#   2. the five P3 imitations again under the unchanged ruling-89 recipe, with the lowest-training-loss reading taken from each
#      epoch-end checkpoint scored on the whole training set with its weights fixed (the running mean was used before);
#   3. the 89-2 / 89-3 reading again with these two in place of the same-input table and the old P3 files.
# Read-only diagnostics on the development set.  Never shuts down.  RESUME=1 skips the suite.
set -u
WORKTREE=$(cd "$(dirname "$0")/../.." && pwd)
cd "$WORKTREE" || exit 2
COMMIT=$(git rev-parse --short HEAD)
PY=/root/miniconda3/bin/python3.12
AUTODL=/root/autodl-tmp
OUTPUTS=$AUTODL/vsmt_outputs
EXPORT_DIR=$OUTPUTS/exports
LOG_DIR=$OUTPUTS/run_logs/ruling89-recheck-$COMMIT
CACHE_ROOT=$AUTODL/vsmt_caches/lean-s1-03-oracle-8ebbd05
REID_WEIGHTS=$AUTODL/vsmt_private/lean-s1-04-diagnostics-oracle-caa50c7/reid_head_vitb14.json
PASS_ROOT=$AUTODL/vsmt_private/lean-s2-05-oracle-c150be0
SIDES=$AUTODL/vsmt_private/ruling89-sides-003b906
DIAG=$AUTODL/vsmt_private/ruling89-recheck-$COMMIT
STATUS=$EXPORT_DIR/ruling89_recheck_$COMMIT.status.json
QUOTA=$(awk '{ if ($1 == "max") print 16; else print int($1 / $2) }' /sys/fs/cgroup/cpu.max 2>/dev/null || echo 16)
WORKERS=${WORKERS:-$((QUOTA - 4))}
RESUME=${RESUME:-0}
TARGETS="taf low handcost rac elup"
mkdir -p "$EXPORT_DIR" "$LOG_DIR" "$DIAG/history" "$DIAG/imitation"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
count_bad() { [ -f "$1" ] || { echo 0; return; }; grep -vc 'exit 0$' "$1"; return 0; }
finish() {
  $PY -c "import json,sys,time; json.dump({'commit': '$COMMIT', 'stage_reached': sys.argv[1], 'finished_cst': time.strftime('%Y-%m-%d %H:%M:%S'),
    'suite_exit': '${SUITE_RC:-}', 'jobs_failed': '${JOBS_FAILED:-}', 'reading_exit': '${READING_RC:-}', 'workers': $WORKERS, 'cpu_quota': $QUOTA,
    'memory_max': '$(cat /sys/fs/cgroup/memory.max 2>/dev/null)', 'worker_basis': 'cgroup CPU quota minus four; one single-threaded process per job',
    'shutdown': False}, open('$STATUS', 'w'), indent=1)" "$1"
  echo "[$(date)] status written ($1)"; exit 0
}
if [ -n "$(git status --porcelain)" ]; then echo "worktree not clean; refusing"; exit 2; fi
echo "[$(date)] ruling 89 re-check at $COMMIT: cpu quota $QUOTA, $WORKERS workers; recall $(PYTHONPATH=src $PY -c 'from vsmt import lean_assignment as la; print(la.RECALL_GLOBAL_COUNT)')"
if [ "$RESUME" != "1" ]; then
  PYTHONPATH=src $PY -m unittest discover -s tests -t tests -p "test_*.py" > "$LOG_DIR/suite.log" 2>&1
  SUITE_RC=$?
  echo "[$(date)] suite exit $SUITE_RC: $(grep -E '^Ran |^OK|FAILED' "$LOG_DIR/suite.log" | tail -2 | tr '\n' ' ')"
  [ "$SUITE_RC" = "0" ] || finish suite_failed
fi
episode_root() { for R in "$OUTPUTS/lean-s1-02a-5f9aa71" "$OUTPUTS/lean-s1-02b-5f9aa71"; do [ -d "$R/$1" ] && echo "$R/$1" && return; done; }
EPISODES=$(for E in $(ls "$PASS_ROOT/dagger_round_1"); do [ -f "$PASS_ROOT/dagger_round_1/$E/VSMT-lean/receipt.json" ] && echo "$E"; done)
ELUP=$(cd ops/vsmt && PYTHONPATH=../../src $PY -c "import json, lean_s2_05_development as e; print(json.dumps(e.expected_pass_config('dagger_round_0', 'ELU-P')))")
JOBS=$LOG_DIR/jobs.txt; : > "$JOBS"
SRC0="$SIDES:dagger_round_0:ELU-P"
for T in $TARGETS; do
  [ -f "$DIAG/imitation/imitation_$T.json" ] && continue
  printf '%s\n' "PYTHONPATH=src $PY ops/vsmt/ruling89_probes.py imitation --source $SRC0 --target $T --output-dir $DIAG/imitation > $LOG_DIR/p3-$T.log 2>&1; echo \"P3 $T exit \$?\"" >> "$JOBS"
done
add_history() {  # label, arm, config
  for EP in $EPISODES; do
    OUT=$DIAG/history/$1/$EP.json
    [ -f "$OUT" ] && continue
    printf '%s\n' "PYTHONPATH=src $PY ops/vsmt/ruling89_history_audit.py run --cache-root $CACHE_ROOT --episode-root $(episode_root $EP) --episode-id $EP --arm $2 --config '$3' --descriptor reid_projection:vitb14 --weights $REID_WEIGHTS --mask-source simulator_instance_masks --output $OUT > $LOG_DIR/h-$1-$EP.log 2>&1; echo \"history $1 $EP exit \$?\"" >> "$JOBS"
  done
}
add_history ELU-P ELU-P "$ELUP"
for RHO in 0.7 0.85; do for N in 2 3 5; do
  add_history "RAC-$RHO-$N" RAC "{\"theta_a\": 0.7, \"d_a\": null, \"rho_rac\": $RHO, \"n_rac\": $N}"
done; done
echo "[$(date)] $(wc -l < "$JOBS") jobs queued on $WORKERS workers"
xargs -d '\n' -P "$WORKERS" -I{} bash -c '{}' < "$JOBS" >> "$LOG_DIR/exits.log" 2>&1
JOBS_FAILED=$(count_bad "$LOG_DIR/exits.log")
echo "[$(date)] jobs: $(grep -c 'exit 0$' "$LOG_DIR/exits.log") ok, $JOBS_FAILED failed"
mkdir -p "$DIAG/history_all"
for D in "$DIAG"/history/*/; do L=$(basename "$D"); for F in "$D"*.json; do cp "$F" "$DIAG/history_all/$L-$(basename "$F")"; done; done
PYTHONPATH=src $PY ops/vsmt/ruling89_history_audit.py merge --input-dir "$DIAG/history_all" --output "$EXPORT_DIR/vsmt_lean_ruling89_history_audit_$COMMIT.json" > "$LOG_DIR/history_merge.log" 2>&1
echo "[$(date)] history merge exit $?: $(grep -o '"pass": [a-z]*' "$LOG_DIR/history_merge.log" | tail -1)"
ARGS=()
for T in $TARGETS; do
  F=$DIAG/imitation/imitation_$T.json
  [ -f "$F" ] && cp "$F" "$EXPORT_DIR/vsmt_lean_ruling89_p3_recheck_${T}_$COMMIT.json" && ARGS+=(--imitation "$T:$EXPORT_DIR/vsmt_lean_ruling89_p3_recheck_${T}_$COMMIT.json")
done
for SEED in 7 19 31 43 59; do
  ARGS+=(--oa-le "$SEED:$EXPORT_DIR/vsmt_lean_ruling89_audit_OA-LE-new-A${SEED}_003b906.json")
  ARGS+=(--la-oe-new "$SEED:$EXPORT_DIR/vsmt_lean_ruling89_audit_LA-OE-new-A${SEED}_003b906.json")
  ARGS+=(--la-oe-old "$SEED:$EXPORT_DIR/vsmt_lean_ruling89_audit_LA-OE-old-A${SEED}_003b906.json")
done
$PY ops/vsmt/ruling89_checks.py --same-input "$EXPORT_DIR/vsmt_lean_ruling89_same_input_003b906.json" \
  --history-audit "$EXPORT_DIR/vsmt_lean_ruling89_history_audit_$COMMIT.json" \
  --coverage-events "$EXPORT_DIR/vsmt_lean_ruling89_coverage_events_003b906.json" "${ARGS[@]}" \
  --output "$EXPORT_DIR/vsmt_lean_ruling89_checks_recheck_$COMMIT.json" > "$LOG_DIR/reading.log" 2>&1
READING_RC=$?
echo "[$(date)] reading exit $READING_RC"; cat "$LOG_DIR/reading.log"
finish done
