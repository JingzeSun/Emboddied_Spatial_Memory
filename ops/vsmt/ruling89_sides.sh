#!/bin/bash
# Ruling 89-2 (existence side) and 89-3 (association side), one chain on the development set, as registered in DECISIONS
#   "ruling 89 execution rules (two)".  Steps, each after the previous one's exit evidence:
#   0. clean worktree, full suite;
#   1. round 0 regenerated: ELU-P at the rollout configuration on the 39 development episodes under the new recall and the
#      extended existence rows (S2-05 run-pass dagger_round_0 into this diag root); in parallel the 89-3 baseline: the five
#      ruling-81/82 VSMT-lean heads in the learned-association + teacher-existence cell under the new recall;
#   2. same-input-different-answer on the round-0 training houses (must be 0, else stop before any training); then in parallel
#      the P3 imitations (taf, low, handcost, rac, elup) on the round-0 records and the round-0 training (VSMT-lean, seed 7);
#   3. round 1: VSMT-lean rollouts with the round-0 head (S2-05 run-pass dagger_round_1);
#   4. state coverage in events on round 0 + round 1 training houses (>= 200 events per state over >= 15 houses, else stop);
#   5. round-1 training on round 0 + round 1 at the five registered seeds;
#   6. the two half-ceiling cells per seed: teacher association + new existence (89-2), learned association (new) + teacher
#      existence (89-3); merges; the reading (ruling89_checks.py) once the P3 runs are in.
#   Read-only diagnostics on the development set; nothing here is a table row, validation or test.  Never shuts down.
# Run from a clean worktree at the commit to use:
#   (setsid nohup bash ops/vsmt/ruling89_sides.sh > /root/autodl-tmp/vsmt_outputs/run_logs/ruling89-sides-<commit>.log 2>&1 < /dev/null &)
# RESUME=1 skips the suite; every step keeps finished outputs and only does what is missing.
# REVISION_91=1 (pending ruling 91 only, never by default): trainings and P3 use the cosine-decayed rate with gradient clipping,
#   the diag root gets the suffix -r91, and the five P3 imitations run first as a gate (all must pass before any rollout).
set -u
WORKTREE=$(cd "$(dirname "$0")/../.." && pwd)
cd "$WORKTREE" || exit 2
COMMIT=$(git rev-parse --short HEAD)
TAG=${DIAG_COMMIT:-$COMMIT}  # the diag root / export tag; DIAG_COMMIT resumes an earlier commit's root
PY=/root/miniconda3/bin/python3.12
AUTODL=/root/autodl-tmp
OUTPUTS=$AUTODL/vsmt_outputs
EXPORT_DIR=$OUTPUTS/exports
LOG_DIR=$OUTPUTS/run_logs/ruling89-sides-$TAG
CACHE_ROOT=$AUTODL/vsmt_caches/lean-s1-03-oracle-8ebbd05
GEOMETRY_ROOT=$AUTODL/vsmt_private/lean-s1-04-geometry-154776d
REID_WEIGHTS=$AUTODL/vsmt_private/lean-s1-04-diagnostics-oracle-caa50c7/reid_head_vitb14.json
EPISODE_ROOTS=$OUTPUTS/lean-s1-02a-5f9aa71,$OUTPUTS/lean-s1-02b-5f9aa71
R81=$AUTODL/vsmt_private/ruling81-0e4494d/training
R82=$AUTODL/vsmt_private/ruling82-18f943f/training
REVISION_91=${REVISION_91:-0}
REV_FLAG=""; REV_SUFFIX=""; [ "$REVISION_91" = "1" ] && { REV_FLAG="--revision-91"; REV_SUFFIX="-r91"; }
DIAG=$AUTODL/vsmt_private/ruling89-sides-$TAG$REV_SUFFIX
LOG_DIR=$LOG_DIR$REV_SUFFIX
PROBES=$DIAG/probes
STATUS=$EXPORT_DIR/ruling89_sides_$TAG${REV_SUFFIX}.status.json
QUOTA=$(awk '{ if ($1 == "max") print 16; else print int($1 / $2) }' /sys/fs/cgroup/cpu.max 2>/dev/null || echo 16)
WORKERS=${WORKERS:-$((QUOTA - 4))}
PASS_WORKERS=${PASS_WORKERS:-39}
RESUME=${RESUME:-0}
SEEDS="7 19 31 43 59"
TARGETS="taf low handcost rac elup"
MASK_SOURCE=simulator_instance_masks
mkdir -p "$EXPORT_DIR" "$LOG_DIR" "$DIAG" "$PROBES/imitation" "$DIAG/training"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

finish() {
  $PY -c "import json,sys,time; json.dump({'commit': '$COMMIT', 'diag_tag': '$TAG', 'stage_reached': sys.argv[1], 'finished_cst': time.strftime('%Y-%m-%d %H:%M:%S'),
    'suite_exit': '${SUITE_RC:-}', 'round0_exit': '${ROUND0_RC:-}', 'baseline_failed': '${BASE_FAILED:-}', 'same_input_exit': '${SAME_RC:-}',
    'round0_training_exit': '${TRAIN0_RC:-}', 'round1_exit': '${ROUND1_RC:-}', 'coverage_exit': '${COVER_RC:-}',
    'round1_training_failed': '${TRAIN1_FAILED:-}', 'cells_failed': '${CELLS_FAILED:-}', 'merges_failed': '${MERGES_FAILED:-}',
    'p3_failed': '${P3_FAILED:-}', 'reading_exit': '${READING_RC:-}', 'workers': $WORKERS, 'pass_workers': $PASS_WORKERS, 'cpu_quota': $QUOTA,
    'memory_max': '$(cat /sys/fs/cgroup/memory.max 2>/dev/null)',
    'worker_basis': 'cgroup CPU quota minus four; a pass runs one single-threaded process per episode, an audit about 1-2 GB, a training about 10-20 GB',
    'shutdown': False}, open('$STATUS', 'w'), indent=1)" "$1"
  echo "[$(date)] status written ($1)"
  exit 0
}
count_bad() {  # lines of an exits log that do not end in "exit 0" (0 when the log is missing)
  [ -f "$1" ] || { echo 0; return; }
  grep -vc 'exit 0$' "$1"
  return 0
}
gate() {  # json file, python expression on d -> exit 0 when true
  $PY -c "import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if ($2) else 1)" "$1"
}

if [ -n "$(git status --porcelain)" ]; then echo "worktree not clean; refusing"; exit 2; fi
echo "[$(date)] ruling 89-2/89-3 at $COMMIT (diag tag $TAG) on $(hostname): cpu quota $QUOTA, $WORKERS workers, pass workers $PASS_WORKERS, memory.max $(cat /sys/fs/cgroup/memory.max)"
echo "[$(date)] recall global count $(PYTHONPATH=src $PY -c 'from vsmt import lean_assignment as la; print(la.RECALL_GLOBAL_COUNT)')"
if [ "$RESUME" != "1" ]; then
  PYTHONPATH=src $PY -m unittest discover -s tests -t tests -p "test_*.py" > "$LOG_DIR/suite.log" 2>&1
  SUITE_RC=$?
  echo "[$(date)] suite exit $SUITE_RC: $(grep -E '^Ran |^OK|FAILED' "$LOG_DIR/suite.log" | tail -2 | tr '\n' ' ')"
  [ "$SUITE_RC" = "0" ] || finish suite_failed
fi

old_weights() { case $1 in 7|19) echo "$R81/VSMT-lean/A$1/weights.json";; *) echo "$R82/VSMT-lean/A$1/weights.json";; esac; }
for SEED in $SEEDS; do [ -f "$(old_weights $SEED)" ] || { echo "missing $(old_weights $SEED)"; finish old_weights_missing; }; done
episode_root() { for R in "$OUTPUTS/lean-s1-02a-5f9aa71" "$OUTPUTS/lean-s1-02b-5f9aa71"; do [ -d "$R/$1" ] && echo "$R/$1" && return; done; }
PASS_ROOT=$AUTODL/vsmt_private/lean-s2-05-oracle-c150be0  # the 39 development episodes, as in rulings 88 and 89-1
EPISODES=$(for E in $(ls "$PASS_ROOT/dagger_round_1"); do [ -f "$PASS_ROOT/dagger_round_1/$E/VSMT-lean/receipt.json" ] && echo "$E"; done)
echo "[$(date)] $(echo $EPISODES | wc -w) development episodes"
audit_jobs() {  # group, flags, heads -> job lines for the missing audits
  local GROUP=$1 FLAGS=$2 HEADS=$3 OUT=$DIAG/audit/$1
  for EP in $EPISODES; do
    [ -f "$OUT/$EP/VSMT-lean/node_audit.json" ] && continue
    printf '%s\n' "$PY ops/vsmt/lean_s2_05_node_audit.py run --cache-root $CACHE_ROOT --episode-root $(episode_root $EP) --geometry-root $GEOMETRY_ROOT --episode-id $EP --arm VSMT-lean --config '{\"tau_r\": 0.5}' $FLAGS --heads $HEADS --descriptor reid_projection:vitb14 --weights $REID_WEIGHTS --output-root $OUT --device cpu > $LOG_DIR/$GROUP-$EP.log 2>&1; echo \"$GROUP $EP exit \$?\""
  done
}
run_pass() {  # pass, arm, config, [heads]
  local HEADS_FLAG=""; [ -n "${4:-}" ] && HEADS_FLAG="--heads $4"
  PYTHONPATH=src $PY ops/vsmt/lean_s2_05_development.py run-pass --pass "$1" --arm "$2" --config "$3" $HEADS_FLAG --cache-root "$CACHE_ROOT" \
    --episode-roots "$EPISODE_ROOTS" --geometry-root "$GEOMETRY_ROOT" --output-root "$DIAG" --descriptor reid_projection:vitb14 \
    --mask-source $MASK_SOURCE --weights "$REID_WEIGHTS" --workers "$PASS_WORKERS" --worker-basis "ruling 89 sides: one process per episode" --resume
}

# 1. round 0 regenerated, and the 89-3 baseline in parallel
ROUND0_CONFIG=$(PYTHONPATH=src:ops/vsmt $PY -c "import json, lean_s2_05_development as e; print(json.dumps(e.expected_pass_config('dagger_round_0', 'ELU-P')))")
echo "[$(date)] step 1: round 0 (ELU-P $ROUND0_CONFIG) and the baseline cells"
run_pass dagger_round_0 ELU-P "$ROUND0_CONFIG" > "$LOG_DIR/round0.log" 2>&1 &
ROUND0_PID=$!
BASE_JOBS=$LOG_DIR/baseline_jobs.txt; : > "$BASE_JOBS"
for SEED in $SEEDS; do audit_jobs "LA-OE-old-A$SEED" "--oracle-existence node_primary" "$(old_weights $SEED)" >> "$BASE_JOBS"; done
xargs -d '\n' -P "$((WORKERS - PASS_WORKERS > 8 ? WORKERS - PASS_WORKERS : 8))" -I{} bash -c '{}' < "$BASE_JOBS" >> "$LOG_DIR/baseline_exits.log" 2>&1 &
BASE_PID=$!
wait $ROUND0_PID; ROUND0_RC=$?
echo "[$(date)] round 0 exit $ROUND0_RC: $(tail -1 "$LOG_DIR/round0.log")"
[ "$ROUND0_RC" = "0" ] || { wait $BASE_PID; finish round0_failed; }
SRC0="$DIAG:dagger_round_0:ELU-P"

# 2. same input, then P3 and the round-0 training
if [ ! -f "$PROBES/same_input.json" ]; then
  PYTHONPATH=src $PY ops/vsmt/ruling89_probes.py same-input --source "$SRC0" --output "$PROBES/same_input.json" > "$LOG_DIR/same_input.log" 2>&1
fi
SAME_RC=$?
echo "[$(date)] same input exit $SAME_RC: $(tr '\n' ' ' < "$LOG_DIR/same_input.log" | cut -c1-400)"
gate "$PROBES/same_input.json" "d['pass']" || { wait $BASE_PID; finish same_input_not_zero; }
P3_JOBS=$LOG_DIR/p3_jobs.txt; : > "$P3_JOBS"
for T in $TARGETS; do
  [ -f "$PROBES/imitation/imitation_$T.json" ] && continue
  printf '%s\n' "PYTHONPATH=src $PY ops/vsmt/ruling89_probes.py imitation --source $SRC0 --target $T --output-dir $PROBES/imitation $REV_FLAG > $LOG_DIR/p3-$T.log 2>&1; echo \"P3 $T exit \$?\"" >> "$P3_JOBS"
done
xargs -d '\n' -P 5 -I{} bash -c '{}' < "$P3_JOBS" >> "$LOG_DIR/p3_exits.log" 2>&1 &
P3_PID=$!
if [ "$REVISION_91" = "1" ]; then  # pending ruling 91: P3 is the gate before any rollout
  wait $P3_PID
  for T in $TARGETS; do gate "$PROBES/imitation/imitation_$T.json" "d['pass']" || { wait $BASE_PID; finish p3_gate_failed_under_revision_91; }; done
  echo "[$(date)] revision 91: all five P3 targets pass on both readings"
fi
T0=$DIAG/training/round0/VSMT-lean
if [ ! -f "$T0/weights.json" ]; then
  PYTHONPATH=src $PY ops/vsmt/ruling89_train.py --source "$SRC0" --arm VSMT-lean --seed 7 --out-dir "$T0" $REV_FLAG > "$LOG_DIR/train0.log" 2>&1
fi
TRAIN0_RC=$?
echo "[$(date)] round-0 training exit $TRAIN0_RC: $(tail -1 "$LOG_DIR/train0.log")"
[ -f "$T0/weights.json" ] && gate "$T0/training_receipt.json" "not d['diverged']" || { wait $BASE_PID $P3_PID; finish round0_training_failed; }

# 3. round 1: VSMT-lean rollouts with the round-0 head
run_pass dagger_round_1 VSMT-lean '{"tau_r": 0.5}' "$T0/weights.json" > "$LOG_DIR/round1.log" 2>&1
ROUND1_RC=$?
echo "[$(date)] round 1 exit $ROUND1_RC: $(tail -1 "$LOG_DIR/round1.log")"
[ "$ROUND1_RC" = "0" ] || { wait $BASE_PID $P3_PID; finish round1_failed; }
SRC1="$DIAG:dagger_round_1:VSMT-lean"

# 4. state coverage in events
if [ ! -f "$PROBES/coverage_events.json" ]; then
  PYTHONPATH=src $PY ops/vsmt/ruling89_probes.py coverage-events --source "$SRC0" --source "$SRC1" --output "$PROBES/coverage_events.json" > "$LOG_DIR/coverage.log" 2>&1
fi
COVER_RC=$?
echo "[$(date)] coverage exit $COVER_RC: $(tr '\n' ' ' < "$LOG_DIR/coverage.log" | cut -c1-400)"
gate "$PROBES/coverage_events.json" "d['pass']" || { wait $BASE_PID $P3_PID; finish coverage_below_the_line; }

# 5. round-1 training at the five seeds
TRAIN_JOBS=$LOG_DIR/train1_jobs.txt; : > "$TRAIN_JOBS"
for SEED in $SEEDS; do
  T1=$DIAG/training/round1/VSMT-lean/A$SEED
  [ -f "$T1/weights.json" ] && continue
  printf '%s\n' "PYTHONPATH=src $PY ops/vsmt/ruling89_train.py --source $SRC0 --source $SRC1 --arm VSMT-lean --seed $SEED --out-dir $T1 $REV_FLAG > $LOG_DIR/train1-A$SEED.log 2>&1; echo \"train1 A$SEED exit \$?\"" >> "$TRAIN_JOBS"
done
xargs -d '\n' -P 5 -I{} bash -c '{}' < "$TRAIN_JOBS" >> "$LOG_DIR/train1_exits.log" 2>&1
TRAIN1_FAILED=$(count_bad "$LOG_DIR/train1_exits.log")
echo "[$(date)] round-1 trainings: $(grep -c 'exit 0$' "$LOG_DIR/train1_exits.log") ok, $TRAIN1_FAILED failed"
[ "$TRAIN1_FAILED" = "0" ] || { wait $BASE_PID $P3_PID; finish round1_training_failed; }

# 6. the half-ceiling cells, merges, reading
CELL_JOBS=$LOG_DIR/cell_jobs.txt; : > "$CELL_JOBS"
for SEED in $SEEDS; do
  W=$DIAG/training/round1/VSMT-lean/A$SEED/weights.json
  audit_jobs "OA-LE-new-A$SEED" "--oracle-association" "$W" >> "$CELL_JOBS"
  audit_jobs "LA-OE-new-A$SEED" "--oracle-existence node_primary" "$W" >> "$CELL_JOBS"
done
wait $BASE_PID
BASE_FAILED=$(count_bad "$LOG_DIR/baseline_exits.log")
echo "[$(date)] baseline audits: $(grep -c 'exit 0$' "$LOG_DIR/baseline_exits.log") ok, $BASE_FAILED failed; $(wc -l < "$CELL_JOBS") cell audits queued"
xargs -d '\n' -P "$WORKERS" -I{} bash -c '{}' < "$CELL_JOBS" >> "$LOG_DIR/cell_exits.log" 2>&1
CELLS_FAILED=$(count_bad "$LOG_DIR/cell_exits.log")
echo "[$(date)] cell audits: $(grep -c 'exit 0$' "$LOG_DIR/cell_exits.log") ok, $CELLS_FAILED failed"
MERGES_FAILED=0; ARGS=()
for SEED in $SEEDS; do
  for GROUP in "OA-LE-new-A$SEED" "LA-OE-new-A$SEED" "LA-OE-old-A$SEED"; do
    RESULT=$EXPORT_DIR/vsmt_lean_ruling89_audit_${GROUP}_$TAG.json
    $PY ops/vsmt/lean_s2_05_node_audit.py merge --output-root "$DIAG/audit/$GROUP" --arm VSMT-lean --results "$RESULT" > "$LOG_DIR/merge-$GROUP.log" 2>&1
    RC=$?; [ "$RC" = "0" ] || MERGES_FAILED=$((MERGES_FAILED + 1))
    case $GROUP in OA-LE-new-*) ARGS+=(--oa-le "$SEED:$RESULT");; LA-OE-new-*) ARGS+=(--la-oe-new "$SEED:$RESULT");; *) ARGS+=(--la-oe-old "$SEED:$RESULT");; esac
  done
done
echo "[$(date)] merges failed: $MERGES_FAILED; waiting for P3"
wait $P3_PID
P3_FAILED=$(count_bad "$LOG_DIR/p3_exits.log")
for T in $TARGETS; do
  F=$PROBES/imitation/imitation_$T.json
  [ -f "$F" ] && cp "$F" "$EXPORT_DIR/vsmt_lean_ruling89_p3_${T}_$TAG.json" && ARGS+=(--imitation "$T:$EXPORT_DIR/vsmt_lean_ruling89_p3_${T}_$TAG.json")
done
cp "$PROBES/same_input.json" "$EXPORT_DIR/vsmt_lean_ruling89_same_input_$TAG.json"
cp "$PROBES/coverage_events.json" "$EXPORT_DIR/vsmt_lean_ruling89_coverage_events_$TAG.json"
for SEED in $SEEDS; do cp "$DIAG/training/round1/VSMT-lean/A$SEED/training_receipt.json" "$EXPORT_DIR/vsmt_lean_ruling89_train1_A${SEED}_$TAG.json"; done
cp "$T0/training_receipt.json" "$EXPORT_DIR/vsmt_lean_ruling89_train0_A7_$TAG.json"
$PY ops/vsmt/ruling89_checks.py --same-input "$EXPORT_DIR/vsmt_lean_ruling89_same_input_$TAG.json" \
  --coverage-events "$EXPORT_DIR/vsmt_lean_ruling89_coverage_events_$TAG.json" "${ARGS[@]}" \
  --output "$EXPORT_DIR/vsmt_lean_ruling89_checks_$TAG.json" > "$LOG_DIR/reading.log" 2>&1
READING_RC=$?
echo "[$(date)] reading exit $READING_RC"; cat "$LOG_DIR/reading.log"
CHECKS=$EXPORT_DIR/vsmt_lean_ruling89_checks_$TAG.json
gate "$CHECKS" "d['existence_side_89_2']['pass'] and d['association_side_89_3']['pass']" || finish sides_read_not_both_passed

# 7. 89-4 (only after both sides passed; execution rules (two), supplement): the joint closed loop, VSMT-lean with the
#    five round-1 heads, tau_r 0.5, no oracle, no new DAgger round
echo "[$(date)] both sides passed; step 7: 89-4 joint closed loop"
JOINT_JOBS=$LOG_DIR/joint_jobs.txt; : > "$JOINT_JOBS"
for SEED in $SEEDS; do
  W=$DIAG/training/round1/VSMT-lean/A$SEED/weights.json
  audit_jobs "JOINT-A$SEED" "" "$W" >> "$JOINT_JOBS"
done
xargs -d '\n' -P "$WORKERS" -I{} bash -c '{}' < "$JOINT_JOBS" >> "$LOG_DIR/joint_exits.log" 2>&1
JOINT_FAILED=$(count_bad "$LOG_DIR/joint_exits.log")
echo "[$(date)] joint audits: $(grep -c 'exit 0$' "$LOG_DIR/joint_exits.log") ok, $JOINT_FAILED failed"
for SEED in $SEEDS; do
  RESULT=$EXPORT_DIR/vsmt_lean_ruling89_audit_JOINT-A${SEED}_$TAG.json
  $PY ops/vsmt/lean_s2_05_node_audit.py merge --output-root "$DIAG/audit/JOINT-A$SEED" --arm VSMT-lean --results "$RESULT" > "$LOG_DIR/merge-JOINT-A$SEED.log" 2>&1 || MERGES_FAILED=$((MERGES_FAILED + 1))
  ARGS+=(--joint "$SEED:$RESULT")
done
$PY ops/vsmt/ruling89_checks.py --same-input "$EXPORT_DIR/vsmt_lean_ruling89_same_input_$TAG.json" \
  --coverage-events "$EXPORT_DIR/vsmt_lean_ruling89_coverage_events_$TAG.json" "${ARGS[@]}" \
  --output "$EXPORT_DIR/vsmt_lean_ruling89_checks_joint_$TAG.json" > "$LOG_DIR/reading_joint.log" 2>&1
READING_RC=$?
echo "[$(date)] joint reading exit $READING_RC"; cat "$LOG_DIR/reading_joint.log"
finish done_with_89_4
