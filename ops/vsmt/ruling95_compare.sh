#!/bin/bash
# Ruling 95 (a) (2026-09-30, user: "待裁 95 取 (a)"): the main question read directly on the 39 development houses, no gate.
#   joint VSMT-lean -- the five round-1 heads of ruling93-9722290 as trained (association and existence both learned, tau_r 0.5
#                      on the ln w corrected logit, k' 3): the registered configuration, nothing retrained;
#   AssocOnly       -- retrained with the same association-side changes (field-wise encoding, round-0 ELU-P records plus its own
#                      round-1 records, the ruling-91 recipe; no existence term): round-0 training (seed 7) -> its own round-1
#                      rollouts -> round-1 training at the five seeds;
#   rule arms       -- TAF, RAC, LOW at their development configurations and ELU-P at its round-0 configuration, rerun on the
#                      current evaluator (ruling 88-4 changed the false-retract definition since the LOG-270 table).
#   Then merges and ruling95_reading.py: the 82-1 orders of VSMT-lean against AssocOnly, the ruling-95 classification fixed
#   before the run, the rule arms, the 85-4 ratio and the 89-4 lines (reference only).  No threshold, weight or configuration
#   is selected; the confirmation set, validation and test are not read.
#   The five VSMT-lean audits and the four rule arms run while AssocOnly's round-0 training runs.
#   FALLBACK_SHUTDOWN_SECONDS > 0 (user 2026-09-30: power off right after the results are pulled) arms a late fallback: that
#   long after the status is written the driver powers off unless another vsmt job is running; the operator normally pulls the
#   exports and powers off first.  RESUME=1 skips the suite; finished outputs are always kept.
set -u
WORKTREE=$(cd "$(dirname "$0")/../.." && pwd)
cd "$WORKTREE" || exit 2
COMMIT=$(git rev-parse --short HEAD)
PY=/root/miniconda3/bin/python3.12
AUTODL=/root/autodl-tmp
OUTPUTS=$AUTODL/vsmt_outputs
EXPORT_DIR=$OUTPUTS/exports
LOG_DIR=$OUTPUTS/run_logs/ruling95-$COMMIT
CACHE_ROOT=$AUTODL/vsmt_caches/lean-s1-03-oracle-8ebbd05
GEOMETRY_ROOT=$AUTODL/vsmt_private/lean-s1-04-geometry-154776d
REID_WEIGHTS=$AUTODL/vsmt_private/lean-s1-04-diagnostics-oracle-caa50c7/reid_head_vitb14.json
EPISODE_ROOTS=$OUTPUTS/lean-s1-02a-5f9aa71,$OUTPUTS/lean-s1-02b-5f9aa71
PASS_ROOT=$AUTODL/vsmt_private/lean-s2-05-oracle-c150be0
FIRST_TAG=003b906
FIRST=$AUTODL/vsmt_private/ruling89-sides-$FIRST_TAG
HEADS_TAG=9722290
HEADS_ROOT=$AUTODL/vsmt_private/ruling93-$HEADS_TAG/training/round1/VSMT-lean
REFERENCE_82=$WORKTREE/results/vsmt_lean_s2_05_ruling82_seed_analysis_18f943f.json
DIAG=$AUTODL/vsmt_private/ruling95-$COMMIT
STATUS=$EXPORT_DIR/ruling95_$COMMIT.status.json
QUOTA=$(awk '{ if ($1 == "max") print 16; else print int($1 / $2) }' /sys/fs/cgroup/cpu.max 2>/dev/null || echo 16)
WORKERS=${WORKERS:-$((QUOTA - 4))}
PASS_WORKERS=${PASS_WORKERS:-39}
TRAIN_THREADS=${TRAIN_THREADS:-4}
RESUME=${RESUME:-0}
FALLBACK_SHUTDOWN_SECONDS=${FALLBACK_SHUTDOWN_SECONDS:-0}
SEEDS="7 19 31 43 59"
RULE_ARMS="TAF ELU-P RAC LOW"
REV="--revision-91"
mkdir -p "$EXPORT_DIR" "$LOG_DIR" "$DIAG/training"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
count_bad() { [ -f "$1" ] || { echo 0; return; }; grep -vc 'exit 0$' "$1"; return 0; }
gate() { $PY -c "import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if ($2) else 1)" "$1"; }
finish() {
  $PY -c "import json,sys,time; json.dump({'commit': '$COMMIT', 'stage_reached': sys.argv[1], 'finished_cst': time.strftime('%Y-%m-%d %H:%M:%S'),
    'suite_exit': '${SUITE_RC:-}', 'round0_training_exit': '${TRAIN0_RC:-}', 'first_audits_failed': '${FIRST_FAILED:-}',
    'round1_exit': '${ROUND1_RC:-}', 'round1_training_failed': '${TRAIN1_FAILED:-}', 'assoc_audits_failed': '${ASSOC_FAILED:-}',
    'merges_failed': '${MERGES_FAILED:-}', 'reading_exit': '${READING_RC:-}',
    'reused': {'vsmt_lean_heads': '$HEADS_ROOT', 'round0_records': '$FIRST/dagger_round_0'}, 'workers': $WORKERS,
    'pass_workers': $PASS_WORKERS, 'train_threads': $TRAIN_THREADS, 'cpu_quota': $QUOTA, 'memory_max': '$(cat /sys/fs/cgroup/memory.max 2>/dev/null)',
    'worker_basis': 'cgroup CPU quota minus four; while a training runs the audits get TRAIN_THREADS fewer workers; an audit is one single-threaded process of about 1-2 GB, a training about 10-20 GB, a pass one process per episode; audits largest episode first',
    'fallback_shutdown_seconds': $FALLBACK_SHUTDOWN_SECONDS}, open('$STATUS', 'w'), indent=1)" "$1"
  echo "[$(date)] status written ($1)"
  if [ "$FALLBACK_SHUTDOWN_SECONDS" -gt 0 ] 2>/dev/null; then
    echo "[$(date)] fallback armed: power off in $FALLBACK_SHUTDOWN_SECONDS s unless another vsmt job runs"
    sleep "$FALLBACK_SHUTDOWN_SECONDS"
    if pgrep -f "lean_s2_05_node_audit.py run|lean_s2_05_development.py|ruling89_train.py" > /dev/null; then
      echo "[$(date)] another vsmt job is running; no fallback shutdown"
    else
      echo "[$(date)] fallback shutdown (AutoDL)"; /usr/bin/shutdown
    fi
  fi
  exit 0
}

if [ -n "$(git status --porcelain)" ]; then echo "worktree not clean; refusing"; exit 2; fi
if ps -eo args | grep -v grep | grep -E "^sleep [0-9]+$|/usr/bin/shutdown" > /dev/null; then echo "a pending sleep/shutdown exists; refusing"; exit 2; fi
echo "[$(date)] ruling 95 comparison at $COMMIT: cpu quota $QUOTA, $WORKERS workers, memory.max $(cat /sys/fs/cgroup/memory.max 2>/dev/null); recall $(PYTHONPATH=src $PY -c 'from vsmt import lean_assignment as la; print(la.RECALL_GLOBAL_COUNT)')"
if [ "$RESUME" != "1" ]; then
  PYTHONPATH=src $PY -m unittest discover -s tests -t tests -p "test_*.py" > "$LOG_DIR/suite.log" 2>&1
  SUITE_RC=$?
  echo "[$(date)] suite exit $SUITE_RC: $(grep -E '^Ran |^OK|FAILED' "$LOG_DIR/suite.log" | tail -2 | tr '\n' ' ')"
  [ "$SUITE_RC" = "0" ] || finish suite_failed
fi

# 1. verify what is reused: the round-0 ELU-P records, the five VSMT-lean heads, and no change to the code that produced them
N0=$(ls "$FIRST"/dagger_round_0/*/ELU-P/receipt.json 2>/dev/null | wc -l)
[ "$N0" = "39" ] || { echo "round-0 receipts: $N0, expected 39"; finish reused_round0_missing; }
CORE="src/vsmt/lean_runner.py src/vsmt/lean_assignment.py src/vsmt/lean_arms.py src/vsmt/lean_memory.py src/vsmt/lean_teacher.py src/vsmt/lean_evaluation.py configs/vsmt"
git diff --quiet "$FIRST_TAG" HEAD -- $CORE || finish reused_round0_code_changed
git diff --quiet "$HEADS_TAG" HEAD -- $CORE || finish reused_heads_code_changed
for SEED in $SEEDS; do [ -f "$HEADS_ROOT/A$SEED/weights.json" ] || finish vsmt_lean_heads_missing; done
SRC0="$FIRST:dagger_round_0:ELU-P"
config_of() {  # the registered configuration of a rule arm (ELU-P: its round-0 rollout configuration)
  local PASS=development_table; [ "$1" = "ELU-P" ] && PASS=dagger_round_0
  PYTHONPATH=src $PY -c "import sys, json; sys.path.insert(0, 'ops/vsmt'); import lean_s2_05_development as d; c = d.expected_pass_config(sys.argv[1], sys.argv[2]); assert c is not None; print(json.dumps(c))" "$PASS" "$1"
}
for ARM in $RULE_ARMS; do C=$(config_of "$ARM") || finish rule_config_unresolved; echo "[$(date)] $ARM config $C"; done
echo "[$(date)] reused inputs verified: 39 round-0 receipts ($FIRST_TAG), five VSMT-lean heads ($HEADS_TAG), core code unchanged"

episode_root() { for R in "$OUTPUTS/lean-s1-02a-5f9aa71" "$OUTPUTS/lean-s1-02b-5f9aa71"; do [ -d "$R/$1" ] && echo "$R/$1" && return; done; }
EPISODES=$(for E in $(ls "$PASS_ROOT/dagger_round_1"); do [ -f "$PASS_ROOT/dagger_round_1/$E/VSMT-lean/receipt.json" ] && echo "$E"; done)
[ "$(echo $EPISODES | wc -w)" = "39" ] || finish development_episodes_not_39
frames_of() { ls "$CACHE_ROOT/$1" | grep -c 'cache.json.gz$'; }
largest_first() { sort -t$'\t' -k1,1nr | cut -f2-; }
audit_jobs() {  # group, arm, config, heads (empty for a rule arm)
  local OUT=$DIAG/audit/$1 HEADS=""
  [ -n "$4" ] && HEADS="--heads $4"
  for EP in $EPISODES; do
    [ -f "$OUT/$EP/$2/node_audit.json" ] && continue
    printf '%s\t%s\n' "$(frames_of $EP)" "$PY ops/vsmt/lean_s2_05_node_audit.py run --cache-root $CACHE_ROOT --episode-root $(episode_root $EP) --geometry-root $GEOMETRY_ROOT --episode-id $EP --arm $2 --config '$3' $HEADS --descriptor reid_projection:vitb14 --weights $REID_WEIGHTS --output-root $OUT --device cpu > $LOG_DIR/$1-$EP.log 2>&1; echo \"$1 $EP exit \$?\""
  done
}
run_pass() {  # pass, arm, config, heads
  PYTHONPATH=src $PY ops/vsmt/lean_s2_05_development.py run-pass --pass "$1" --arm "$2" --config "$3" --heads "$4" --cache-root "$CACHE_ROOT" \
    --episode-roots "$EPISODE_ROOTS" --geometry-root "$GEOMETRY_ROOT" --output-root "$DIAG" --descriptor reid_projection:vitb14 \
    --mask-source simulator_instance_masks --weights "$REID_WEIGHTS" --workers "$PASS_WORKERS" --worker-basis "ruling 95: one process per episode" --resume
}

# 2. AssocOnly round-0 training in the background; meanwhile the joint VSMT-lean audits and the four rule arms
T0=$DIAG/training/round0/AssocOnly
TRAIN0_PID=""
if [ ! -f "$T0/weights.json" ]; then
  OMP_NUM_THREADS=$TRAIN_THREADS MKL_NUM_THREADS=$TRAIN_THREADS PYTHONPATH=src $PY ops/vsmt/ruling89_train.py --source "$SRC0" --arm AssocOnly --seed 7 --out-dir "$T0" $REV > "$LOG_DIR/train0.log" 2>&1 &
  TRAIN0_PID=$!
fi
FIRST_JOBS=$LOG_DIR/first_jobs.txt
{
  for SEED in $SEEDS; do audit_jobs "JOINT-A$SEED" VSMT-lean '{"tau_r": 0.5}' "$HEADS_ROOT/A$SEED/weights.json"; done
  for ARM in $RULE_ARMS; do audit_jobs "RULE-$ARM" "$ARM" "$(config_of $ARM)" ""; done
} | largest_first > "$FIRST_JOBS"
echo "[$(date)] $(wc -l < "$FIRST_JOBS") joint and rule-arm audits queued on $((WORKERS - TRAIN_THREADS)) workers (largest episode first)"
xargs -d '\n' -P "$((WORKERS - TRAIN_THREADS))" -I{} bash -c '{}' < "$FIRST_JOBS" >> "$LOG_DIR/first_exits.log" 2>&1
FIRST_FAILED=$(count_bad "$LOG_DIR/first_exits.log")
echo "[$(date)] joint and rule-arm audits: $(grep -c 'exit 0$' "$LOG_DIR/first_exits.log" 2>/dev/null) ok, $FIRST_FAILED failed"
if [ -n "$TRAIN0_PID" ]; then wait "$TRAIN0_PID"; TRAIN0_RC=$?; else TRAIN0_RC=0; fi
echo "[$(date)] AssocOnly round-0 training exit $TRAIN0_RC: $(tail -1 "$LOG_DIR/train0.log" 2>/dev/null)"
[ -f "$T0/weights.json" ] && gate "$T0/training_receipt.json" "not d['diverged']" || finish round0_training_failed

# 3. AssocOnly's own round-1 rollouts, then round-1 training at the five seeds on round 0 plus its own round 1
run_pass dagger_round_1 AssocOnly '{}' "$T0/weights.json" > "$LOG_DIR/round1.log" 2>&1
ROUND1_RC=$?
echo "[$(date)] AssocOnly round 1 exit $ROUND1_RC: $(tail -1 "$LOG_DIR/round1.log")"
[ "$ROUND1_RC" = "0" ] || finish round1_failed
SRC1="$DIAG:dagger_round_1:AssocOnly"
TRAIN_JOBS=$LOG_DIR/train1_jobs.txt; : > "$TRAIN_JOBS"
for SEED in $SEEDS; do
  T1=$DIAG/training/round1/AssocOnly/A$SEED
  [ -f "$T1/weights.json" ] && continue
  printf '%s\n' "OMP_NUM_THREADS=$TRAIN_THREADS MKL_NUM_THREADS=$TRAIN_THREADS PYTHONPATH=src $PY ops/vsmt/ruling89_train.py --source $SRC0 --source $SRC1 --arm AssocOnly --seed $SEED --out-dir $T1 $REV > $LOG_DIR/train1-A$SEED.log 2>&1; echo \"train1 A$SEED exit \$?\"" >> "$TRAIN_JOBS"
done
xargs -d '\n' -P 5 -I{} bash -c '{}' < "$TRAIN_JOBS" >> "$LOG_DIR/train1_exits.log" 2>&1
TRAIN1_FAILED=$(count_bad "$LOG_DIR/train1_exits.log")
echo "[$(date)] AssocOnly round-1 trainings: $TRAIN1_FAILED failed"
[ "$TRAIN1_FAILED" = "0" ] || finish round1_training_failed

# 4. AssocOnly closed loop at the five seeds
ASSOC_JOBS=$LOG_DIR/assoc_jobs.txt
for SEED in $SEEDS; do audit_jobs "ASSOC-A$SEED" AssocOnly '{}' "$DIAG/training/round1/AssocOnly/A$SEED/weights.json"; done | largest_first > "$ASSOC_JOBS"
echo "[$(date)] $(wc -l < "$ASSOC_JOBS") AssocOnly audits queued on $WORKERS workers"
xargs -d '\n' -P "$WORKERS" -I{} bash -c '{}' < "$ASSOC_JOBS" >> "$LOG_DIR/assoc_exits.log" 2>&1
ASSOC_FAILED=$(count_bad "$LOG_DIR/assoc_exits.log")
echo "[$(date)] AssocOnly audits: $ASSOC_FAILED failed"

# 5. merges, receipts and the reading
MERGES_FAILED=0; ARGS=()
result_of() { echo "$EXPORT_DIR/vsmt_lean_ruling95_audit_$1_$COMMIT.json"; }
merge() {  # group, arm (runs in this shell, so the failure count is kept)
  $PY ops/vsmt/lean_s2_05_node_audit.py merge --output-root "$DIAG/audit/$1" --arm "$2" --results "$(result_of "$1")" > "$LOG_DIR/merge-$1.log" 2>&1 || MERGES_FAILED=$((MERGES_FAILED + 1))
}
for SEED in $SEEDS; do
  merge "JOINT-A$SEED" VSMT-lean; ARGS+=(--group "VSMT-lean:$SEED:$(result_of "JOINT-A$SEED")")
  merge "ASSOC-A$SEED" AssocOnly; ARGS+=(--group "AssocOnly:$SEED:$(result_of "ASSOC-A$SEED")")
  cp "$DIAG/training/round1/AssocOnly/A$SEED/training_receipt.json" "$EXPORT_DIR/vsmt_lean_ruling95_train1_AssocOnly_A${SEED}_$COMMIT.json"
done
for ARM in $RULE_ARMS; do merge "RULE-$ARM" "$ARM"; ARGS+=(--rule-arm "$ARM:$(result_of "RULE-$ARM")"); done
cp "$T0/training_receipt.json" "$EXPORT_DIR/vsmt_lean_ruling95_train0_AssocOnly_A7_$COMMIT.json"
echo "[$(date)] merges failed: $MERGES_FAILED"
$PY ops/vsmt/ruling95_reading.py "${ARGS[@]}" --reference-82 "$REFERENCE_82" --output "$EXPORT_DIR/vsmt_lean_ruling95_reading_$COMMIT.json" > "$LOG_DIR/reading.log" 2>&1
READING_RC=$?
echo "[$(date)] reading exit $READING_RC"; cat "$LOG_DIR/reading.log"
finish done
