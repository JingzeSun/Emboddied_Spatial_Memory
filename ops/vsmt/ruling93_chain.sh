#!/bin/bash
# Ruling 93 (a) (2026-09-30): the full chain under the ruling-91 recipe (cosine-decayed rate 1e-3 -> 1e-5, gradient clipping 1.0,
#   existence decisions on the ln w corrected logit), with P3 reported only and read on the uncorrected logits (93-2), and no
#   cap on revisions (93-1: the user decides after each reading).  Order:
#   0. clean worktree, full suite;
#   1. verify and reuse: round-0 ELU-P records and the five old-head baseline cells of ruling89-sides-003b906, the passing
#      history audit of c02cb98 (stop when missing or when the relevant code changed since);
#   2. the five P3 imitations in the background (report only); round-0 training (seed 7) -> round-1 rollouts -> state coverage
#      in events (still a stop line before training) -> round-1 training at the five seeds -> the two half-ceiling cells ->
#      merges -> the 89-2 / 89-3 reading (history audit required, --p3-report-only);
#   3. only if both sides pass: 89-4, the joint closed loop (VSMT-lean, the five round-1 heads, tau_r 0.5, no oracle).
#   Everything writes to vsmt_private/ruling93-<commit>, exports vsmt_lean_ruling93_*_<commit>.  Never shuts down.
#   RESUME=1 skips the suite; finished outputs are kept.
set -u
WORKTREE=$(cd "$(dirname "$0")/../.." && pwd)
cd "$WORKTREE" || exit 2
COMMIT=$(git rev-parse --short HEAD)
PY=/root/miniconda3/bin/python3.12
AUTODL=/root/autodl-tmp
OUTPUTS=$AUTODL/vsmt_outputs
EXPORT_DIR=$OUTPUTS/exports
LOG_DIR=$OUTPUTS/run_logs/ruling93-$COMMIT
CACHE_ROOT=$AUTODL/vsmt_caches/lean-s1-03-oracle-8ebbd05
GEOMETRY_ROOT=$AUTODL/vsmt_private/lean-s1-04-geometry-154776d
REID_WEIGHTS=$AUTODL/vsmt_private/lean-s1-04-diagnostics-oracle-caa50c7/reid_head_vitb14.json
EPISODE_ROOTS=$OUTPUTS/lean-s1-02a-5f9aa71,$OUTPUTS/lean-s1-02b-5f9aa71
PASS_ROOT=$AUTODL/vsmt_private/lean-s2-05-oracle-c150be0
FIRST_TAG=003b906
FIRST=$AUTODL/vsmt_private/ruling89-sides-$FIRST_TAG
AUDIT_TAG=c02cb98
HISTORY_AUDIT=$EXPORT_DIR/vsmt_lean_ruling89_history_audit_$AUDIT_TAG.json
HISTORY_STATUS=$EXPORT_DIR/ruling89_recheck_$AUDIT_TAG.status.json
DIAG=$AUTODL/vsmt_private/ruling93-$COMMIT
PROBES=$DIAG/probes
STATUS=$EXPORT_DIR/ruling93_$COMMIT.status.json
QUOTA=$(awk '{ if ($1 == "max") print 16; else print int($1 / $2) }' /sys/fs/cgroup/cpu.max 2>/dev/null || echo 16)
WORKERS=${WORKERS:-$((QUOTA - 4))}
PASS_WORKERS=${PASS_WORKERS:-32}
RESUME=${RESUME:-0}
SEEDS="7 19 31 43 59"
TARGETS="taf low handcost rac elup"
REV="--revision-91"
mkdir -p "$EXPORT_DIR" "$LOG_DIR" "$DIAG" "$PROBES/imitation" "$DIAG/training"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
count_bad() { [ -f "$1" ] || { echo 0; return; }; grep -vc 'exit 0$' "$1"; return 0; }
gate() { $PY -c "import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if ($2) else 1)" "$1"; }
finish() {
  $PY -c "import json,sys,time; json.dump({'commit': '$COMMIT', 'stage_reached': sys.argv[1], 'finished_cst': time.strftime('%Y-%m-%d %H:%M:%S'),
    'suite_exit': '${SUITE_RC:-}', 'p3_failed': '${P3_FAILED:-}', 'round0_training_exit': '${TRAIN0_RC:-}', 'round1_exit': '${ROUND1_RC:-}',
    'round1_training_failed': '${TRAIN1_FAILED:-}', 'cells_failed': '${CELLS_FAILED:-}', 'merges_failed': '${MERGES_FAILED:-}',
    'joint_failed': '${JOINT_FAILED:-}', 'reading_exit': '${READING_RC:-}', 'reused': {'round0_records': '$FIRST/dagger_round_0',
    'baseline_cells_tag': '$FIRST_TAG', 'history_audit': '$HISTORY_AUDIT'}, 'workers': $WORKERS, 'pass_workers': $PASS_WORKERS,
    'cpu_quota': $QUOTA, 'memory_max': '$(cat /sys/fs/cgroup/memory.max 2>/dev/null)',
    'worker_basis': 'cgroup CPU quota minus four; a pass runs one process per episode, an audit about 1-2 GB, a training about 10-20 GB',
    'shutdown': False}, open('$STATUS', 'w'), indent=1)" "$1"
  echo "[$(date)] status written ($1)"; exit 0
}

if [ -n "$(git status --porcelain)" ]; then echo "worktree not clean; refusing"; exit 2; fi
echo "[$(date)] ruling 93 chain at $COMMIT: cpu quota $QUOTA, $WORKERS workers; recall $(PYTHONPATH=src $PY -c 'from vsmt import lean_assignment as la; print(la.RECALL_GLOBAL_COUNT)')"
if [ "$RESUME" != "1" ]; then
  PYTHONPATH=src $PY -m unittest discover -s tests -t tests -p "test_*.py" > "$LOG_DIR/suite.log" 2>&1
  SUITE_RC=$?
  echo "[$(date)] suite exit $SUITE_RC: $(grep -E '^Ran |^OK|FAILED' "$LOG_DIR/suite.log" | tail -2 | tr '\n' ' ')"
  [ "$SUITE_RC" = "0" ] || finish suite_failed
fi

# 1. verify what is reused
N0=$(ls "$FIRST"/dagger_round_0/*/ELU-P/receipt.json 2>/dev/null | wc -l)
[ "$N0" = "39" ] || { echo "round-0 receipts: $N0, expected 39"; finish reused_round0_missing; }
git diff --quiet "$FIRST_TAG" HEAD -- src/vsmt/lean_runner.py src/vsmt/lean_assignment.py src/vsmt/lean_arms.py src/vsmt/lean_memory.py \
  src/vsmt/lean_teacher.py src/vsmt/lean_evaluation.py configs/vsmt || finish reused_round0_code_changed
for SEED in $SEEDS; do [ -f "$EXPORT_DIR/vsmt_lean_ruling89_audit_LA-OE-old-A${SEED}_$FIRST_TAG.json" ] || finish reused_baseline_missing; done
[ -f "$HISTORY_AUDIT" ] && gate "$HISTORY_AUDIT" "d['pass'] is True" || finish history_audit_missing_or_failed
gate "$HISTORY_STATUS" "d['stage_reached'] == 'done' and d['jobs_failed'] == '0'" || finish history_audit_incomplete
git diff --quiet "$AUDIT_TAG" HEAD -- src/vsmt/lean_runner.py src/vsmt/lean_assignment.py src/vsmt/lean_arms.py src/vsmt/lean_memory.py \
  ops/vsmt/ruling89_history_audit.py || finish history_audit_code_changed
echo "[$(date)] reused inputs verified: 39 round-0 receipts ($FIRST_TAG), 5 baseline cells, history audit $AUDIT_TAG pass"
SRC0="$FIRST:dagger_round_0:ELU-P"

# 2. P3, report only (ruling 93-2), in the background; read on the uncorrected logits
P3_JOBS=$LOG_DIR/p3_jobs.txt; : > "$P3_JOBS"
for T in $TARGETS; do
  [ -f "$PROBES/imitation/imitation_$T.json" ] && continue
  printf '%s\n' "PYTHONPATH=src $PY ops/vsmt/ruling89_probes.py imitation --source $SRC0 --target $T --output-dir $PROBES/imitation $REV --read-uncorrected > $LOG_DIR/p3-$T.log 2>&1; echo \"P3 $T exit \$?\"" >> "$P3_JOBS"
done
xargs -d '\n' -P 5 -I{} bash -c '{}' < "$P3_JOBS" >> "$LOG_DIR/p3_exits.log" 2>&1 &
P3_PID=$!
ARGS=()

run_pass() {  # pass, arm, config, heads
  PYTHONPATH=src $PY ops/vsmt/lean_s2_05_development.py run-pass --pass "$1" --arm "$2" --config "$3" --heads "$4" --cache-root "$CACHE_ROOT" \
    --episode-roots "$EPISODE_ROOTS" --geometry-root "$GEOMETRY_ROOT" --output-root "$DIAG" --descriptor reid_projection:vitb14 \
    --mask-source simulator_instance_masks --weights "$REID_WEIGHTS" --workers "$PASS_WORKERS" --worker-basis "ruling 93: one process per episode" --resume
}
episode_root() { for R in "$OUTPUTS/lean-s1-02a-5f9aa71" "$OUTPUTS/lean-s1-02b-5f9aa71"; do [ -d "$R/$1" ] && echo "$R/$1" && return; done; }
EPISODES=$(for E in $(ls "$PASS_ROOT/dagger_round_1"); do [ -f "$PASS_ROOT/dagger_round_1/$E/VSMT-lean/receipt.json" ] && echo "$E"; done)
audit_jobs() {  # group, flags, heads
  local OUT=$DIAG/audit/$1
  for EP in $EPISODES; do
    [ -f "$OUT/$EP/VSMT-lean/node_audit.json" ] && continue
    printf '%s\n' "$PY ops/vsmt/lean_s2_05_node_audit.py run --cache-root $CACHE_ROOT --episode-root $(episode_root $EP) --geometry-root $GEOMETRY_ROOT --episode-id $EP --arm VSMT-lean --config '{\"tau_r\": 0.5}' $2 --heads $3 --descriptor reid_projection:vitb14 --weights $REID_WEIGHTS --output-root $OUT --device cpu > $LOG_DIR/$1-$EP.log 2>&1; echo \"$1 $EP exit \$?\""
  done
}

# 3. round 0 training, round 1, coverage, round-1 training, cells
T0=$DIAG/training/round0/VSMT-lean
[ -f "$T0/weights.json" ] || PYTHONPATH=src $PY ops/vsmt/ruling89_train.py --source "$SRC0" --arm VSMT-lean --seed 7 --out-dir "$T0" $REV > "$LOG_DIR/train0.log" 2>&1
TRAIN0_RC=$?
echo "[$(date)] round-0 training exit $TRAIN0_RC: $(tail -1 "$LOG_DIR/train0.log" 2>/dev/null)"
[ -f "$T0/weights.json" ] && gate "$T0/training_receipt.json" "not d['diverged']" || finish round0_training_failed
run_pass dagger_round_1 VSMT-lean '{"tau_r": 0.5}' "$T0/weights.json" > "$LOG_DIR/round1.log" 2>&1
ROUND1_RC=$?
echo "[$(date)] round 1 exit $ROUND1_RC: $(tail -1 "$LOG_DIR/round1.log")"
[ "$ROUND1_RC" = "0" ] || finish round1_failed
SRC1="$DIAG:dagger_round_1:VSMT-lean"
[ -f "$PROBES/coverage_events.json" ] || PYTHONPATH=src $PY ops/vsmt/ruling89_probes.py coverage-events --source "$SRC0" --source "$SRC1" --output "$PROBES/coverage_events.json" > "$LOG_DIR/coverage.log" 2>&1
gate "$PROBES/coverage_events.json" "d['pass']" || finish coverage_below_the_line
cp "$PROBES/coverage_events.json" "$EXPORT_DIR/vsmt_lean_ruling93_coverage_events_$COMMIT.json"
TRAIN_JOBS=$LOG_DIR/train1_jobs.txt; : > "$TRAIN_JOBS"
for SEED in $SEEDS; do
  T1=$DIAG/training/round1/VSMT-lean/A$SEED
  [ -f "$T1/weights.json" ] && continue
  printf '%s\n' "PYTHONPATH=src $PY ops/vsmt/ruling89_train.py --source $SRC0 --source $SRC1 --arm VSMT-lean --seed $SEED --out-dir $T1 $REV > $LOG_DIR/train1-A$SEED.log 2>&1; echo \"train1 A$SEED exit \$?\"" >> "$TRAIN_JOBS"
done
xargs -d '\n' -P 5 -I{} bash -c '{}' < "$TRAIN_JOBS" >> "$LOG_DIR/train1_exits.log" 2>&1
TRAIN1_FAILED=$(count_bad "$LOG_DIR/train1_exits.log")
echo "[$(date)] round-1 trainings: $TRAIN1_FAILED failed"
[ "$TRAIN1_FAILED" = "0" ] || finish round1_training_failed
CELL_JOBS=$LOG_DIR/cell_jobs.txt; : > "$CELL_JOBS"
for SEED in $SEEDS; do
  W=$DIAG/training/round1/VSMT-lean/A$SEED/weights.json
  audit_jobs "OA-LE-r93-A$SEED" "--oracle-association" "$W" >> "$CELL_JOBS"
  audit_jobs "LA-OE-r93-A$SEED" "--oracle-existence node_primary" "$W" >> "$CELL_JOBS"
done
xargs -d '\n' -P "$WORKERS" -I{} bash -c '{}' < "$CELL_JOBS" >> "$LOG_DIR/cell_exits.log" 2>&1
CELLS_FAILED=$(count_bad "$LOG_DIR/cell_exits.log")
echo "[$(date)] cell audits: $CELLS_FAILED failed"
MERGES_FAILED=0
for SEED in $SEEDS; do
  for GROUP in "OA-LE-r93-A$SEED" "LA-OE-r93-A$SEED"; do
    RESULT=$EXPORT_DIR/vsmt_lean_ruling93_audit_${GROUP}_$COMMIT.json
    $PY ops/vsmt/lean_s2_05_node_audit.py merge --output-root "$DIAG/audit/$GROUP" --arm VSMT-lean --results "$RESULT" > "$LOG_DIR/merge-$GROUP.log" 2>&1 || MERGES_FAILED=$((MERGES_FAILED + 1))
    case $GROUP in OA-LE-*) ARGS+=(--oa-le "$SEED:$RESULT");; *) ARGS+=(--la-oe-new "$SEED:$RESULT");; esac
  done
  ARGS+=(--la-oe-old "$SEED:$EXPORT_DIR/vsmt_lean_ruling89_audit_LA-OE-old-A${SEED}_$FIRST_TAG.json")
  cp "$DIAG/training/round1/VSMT-lean/A$SEED/training_receipt.json" "$EXPORT_DIR/vsmt_lean_ruling93_train1_A${SEED}_$COMMIT.json"
done
cp "$T0/training_receipt.json" "$EXPORT_DIR/vsmt_lean_ruling93_train0_A7_$COMMIT.json"
wait $P3_PID
P3_FAILED=$(count_bad "$LOG_DIR/p3_exits.log")
for T in $TARGETS; do
  F=$PROBES/imitation/imitation_$T.json
  [ -f "$F" ] || continue
  cp "$F" "$EXPORT_DIR/vsmt_lean_ruling93_p3_${T}_$COMMIT.json"
  ARGS+=(--imitation "$T:$EXPORT_DIR/vsmt_lean_ruling93_p3_${T}_$COMMIT.json")
  echo "[$(date)] P3 (reported) $T: $($PY -c "import json; d=json.load(open('$F')); print({k: round(v['train']['balanced_agreement'], 4) for k, v in d['readings'].items()})")"
done
COMMON=(--p3-report-only --history-audit "$HISTORY_AUDIT" --coverage-events "$EXPORT_DIR/vsmt_lean_ruling93_coverage_events_$COMMIT.json")
$PY ops/vsmt/ruling89_checks.py "${COMMON[@]}" "${ARGS[@]}" --output "$EXPORT_DIR/vsmt_lean_ruling93_checks_$COMMIT.json" > "$LOG_DIR/reading.log" 2>&1
READING_RC=$?
echo "[$(date)] reading exit $READING_RC"; cat "$LOG_DIR/reading.log"
gate "$EXPORT_DIR/vsmt_lean_ruling93_checks_$COMMIT.json" "d['existence_side_89_2']['pass'] and d['association_side_89_3']['pass']" || finish sides_not_both_passed

# 4. 89-4 only when both sides passed
JOINT_JOBS=$LOG_DIR/joint_jobs.txt; : > "$JOINT_JOBS"
for SEED in $SEEDS; do audit_jobs "JOINT-r93-A$SEED" "" "$DIAG/training/round1/VSMT-lean/A$SEED/weights.json" >> "$JOINT_JOBS"; done
xargs -d '\n' -P "$WORKERS" -I{} bash -c '{}' < "$JOINT_JOBS" >> "$LOG_DIR/joint_exits.log" 2>&1
JOINT_FAILED=$(count_bad "$LOG_DIR/joint_exits.log")
for SEED in $SEEDS; do
  RESULT=$EXPORT_DIR/vsmt_lean_ruling93_audit_JOINT-r93-A${SEED}_$COMMIT.json
  $PY ops/vsmt/lean_s2_05_node_audit.py merge --output-root "$DIAG/audit/JOINT-r93-A$SEED" --arm VSMT-lean --results "$RESULT" > "$LOG_DIR/merge-JOINT-A$SEED.log" 2>&1 || MERGES_FAILED=$((MERGES_FAILED + 1))
  ARGS+=(--joint "$SEED:$RESULT")
done
$PY ops/vsmt/ruling89_checks.py "${COMMON[@]}" "${ARGS[@]}" --output "$EXPORT_DIR/vsmt_lean_ruling93_checks_joint_$COMMIT.json" > "$LOG_DIR/reading_joint.log" 2>&1
READING_RC=$?
echo "[$(date)] joint reading exit $READING_RC"; cat "$LOG_DIR/reading_joint.log"
finish done_with_89_4
