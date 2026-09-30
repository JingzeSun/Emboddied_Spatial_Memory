#!/bin/bash
# Ruling 96 (a) (2026-10-01, user: "待裁 96 取 (a)，按补全的约束做，跑完拉回结果后立即关机"): one mechanism only -- whether the
#   checkpoint selection accounts for LOG-294's node-F1 gap.  Training stays exactly as it was (the records of ruling93-9722290,
#   the ruling-91 recipe, the five seeds, TRAIN_THREADS 4, gradient clipping over all heads); only which epoch is kept changes.
#   1. retrain VSMT-lean round 1 at the five seeds with --group-selection: one run writes the total-loss selection (weights.json)
#      and the grouped one (weights_grouped.json: association and birth together by the association term, existence alone by
#      the existence term, ties to the earlier epoch);
#   2. reproduction check (ruling96_selection_check.py): the five total-loss weights must carry the digests of the 9722290 heads,
#      else stop before any audit; when they do, the total-loss joint result is the d835cd3 JOINT export (audits are
#      deterministic), so only the grouped heads are audited;
#   3. the grouped heads in the joint closed loop (tau_r 0.5, 5 x 39, largest episode first), merges, and the ruling-95 reading
#      against the d835cd3 AssocOnly heads (the grouped selection is the same for them) and rule arms.
#   Nothing else changes; the confirmation set, validation and test are not read.  FALLBACK_SHUTDOWN_SECONDS > 0 arms the late
#   fallback power-off as in ruling95_compare.sh.  RESUME=1 skips the suite; finished outputs are always kept.
set -u
WORKTREE=$(cd "$(dirname "$0")/../.." && pwd)
cd "$WORKTREE" || exit 2
COMMIT=$(git rev-parse --short HEAD)
PY=/root/miniconda3/bin/python3.12
AUTODL=/root/autodl-tmp
OUTPUTS=$AUTODL/vsmt_outputs
EXPORT_DIR=$OUTPUTS/exports
LOG_DIR=$OUTPUTS/run_logs/ruling96-$COMMIT
CACHE_ROOT=$AUTODL/vsmt_caches/lean-s1-03-oracle-8ebbd05
GEOMETRY_ROOT=$AUTODL/vsmt_private/lean-s1-04-geometry-154776d
REID_WEIGHTS=$AUTODL/vsmt_private/lean-s1-04-diagnostics-oracle-caa50c7/reid_head_vitb14.json
PASS_ROOT=$AUTODL/vsmt_private/lean-s2-05-oracle-c150be0
FIRST=$AUTODL/vsmt_private/ruling89-sides-003b906
HEADS_TAG=9722290
R93=$AUTODL/vsmt_private/ruling93-$HEADS_TAG
PREV=d835cd3
DIAG=$AUTODL/vsmt_private/ruling96-$COMMIT
STATUS=$EXPORT_DIR/ruling96_$COMMIT.status.json
QUOTA=$(awk '{ if ($1 == "max") print 16; else print int($1 / $2) }' /sys/fs/cgroup/cpu.max 2>/dev/null || echo 16)
WORKERS=${WORKERS:-$((QUOTA - 4))}
TRAIN_THREADS=${TRAIN_THREADS:-4}
RESUME=${RESUME:-0}
FALLBACK_SHUTDOWN_SECONDS=${FALLBACK_SHUTDOWN_SECONDS:-0}
SEEDS="7 19 31 43 59"
RULE_ARMS="TAF ELU-P RAC LOW"
REV="--revision-91"
mkdir -p "$EXPORT_DIR" "$LOG_DIR" "$DIAG/training"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
count_bad() { [ -f "$1" ] || { echo 0; return; }; grep -vc 'exit 0$' "$1"; return 0; }
finish() {
  $PY -c "import json,sys,time; json.dump({'commit': '$COMMIT', 'stage_reached': sys.argv[1], 'finished_cst': time.strftime('%Y-%m-%d %H:%M:%S'),
    'suite_exit': '${SUITE_RC:-}', 'training_failed': '${TRAIN_FAILED:-}', 'selection_check_exit': '${CHECK_RC:-}',
    'audits_failed': '${AUDITS_FAILED:-}', 'merges_failed': '${MERGES_FAILED:-}', 'reading_exit': '${READING_RC:-}',
    'reused': {'records': ['$FIRST/dagger_round_0', '$R93/dagger_round_1'], 'previous_heads': '$R93/training/round1/VSMT-lean',
    'assoc_only_and_rule_arms': 'vsmt_lean_ruling95_audit_*_$PREV.json'}, 'workers': $WORKERS, 'train_threads': $TRAIN_THREADS,
    'cpu_quota': $QUOTA, 'memory_max': '$(cat /sys/fs/cgroup/memory.max 2>/dev/null)',
    'worker_basis': 'five trainings with TRAIN_THREADS threads each (the ruling-93 setting, needed for bit reproduction); then audits on cgroup CPU quota minus four, one single-threaded process of about 1-2 GB each, largest episode first',
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
echo "[$(date)] ruling 96 selection at $COMMIT: cpu quota $QUOTA, $WORKERS workers, memory.max $(cat /sys/fs/cgroup/memory.max 2>/dev/null)"
if [ "$RESUME" != "1" ]; then
  PYTHONPATH=src $PY -m unittest discover -s tests -t tests -p "test_*.py" > "$LOG_DIR/suite.log" 2>&1
  SUITE_RC=$?
  echo "[$(date)] suite exit $SUITE_RC: $(grep -E '^Ran |^OK|FAILED' "$LOG_DIR/suite.log" | tail -2 | tr '\n' ' ')"
  [ "$SUITE_RC" = "0" ] || finish suite_failed
fi

# 1. verify what is reused
N0=$(ls "$FIRST"/dagger_round_0/*/ELU-P/receipt.json 2>/dev/null | wc -l)
N1=$(ls "$R93"/dagger_round_1/*/VSMT-lean/receipt.json 2>/dev/null | wc -l)
[ "$N0" = "39" ] && [ "$N1" = "39" ] || { echo "records: round 0 $N0, round 1 $N1, expected 39 each"; finish reused_records_missing; }
CORE="src/vsmt/lean_runner.py src/vsmt/lean_assignment.py src/vsmt/lean_arms.py src/vsmt/lean_memory.py src/vsmt/lean_teacher.py src/vsmt/lean_evaluation.py configs/vsmt"
git diff --quiet "$HEADS_TAG" HEAD -- $CORE || finish core_code_changed_since_the_heads
git diff --quiet "$PREV" HEAD -- $CORE ops/vsmt/lean_s2_05_node_audit.py ops/vsmt/ruling95_reading.py ops/vsmt/ruling82_seed_analysis.py || finish evaluation_code_changed_since_d835cd3
for SEED in $SEEDS; do
  [ -f "$R93/training/round1/VSMT-lean/A$SEED/training_receipt.json" ] || finish previous_receipt_missing
  [ -f "$EXPORT_DIR/vsmt_lean_ruling95_audit_ASSOC-A${SEED}_$PREV.json" ] || finish assoc_only_export_missing
done
for ARM in $RULE_ARMS; do [ -f "$EXPORT_DIR/vsmt_lean_ruling95_audit_RULE-${ARM}_$PREV.json" ] || finish rule_arm_export_missing; done
SRC0="$FIRST:dagger_round_0:ELU-P"
SRC1="$R93:dagger_round_1:VSMT-lean"
echo "[$(date)] reused inputs verified: 39 + 39 records, five previous receipts, the d835cd3 AssocOnly and rule-arm exports, code unchanged"

# 2. retrain with the grouped selection alongside (training unchanged)
TRAIN_JOBS=$LOG_DIR/train_jobs.txt; : > "$TRAIN_JOBS"
for SEED in $SEEDS; do
  T=$DIAG/training/round1/VSMT-lean/A$SEED
  [ -f "$T/weights_grouped.json" ] && continue
  printf '%s\n' "OMP_NUM_THREADS=$TRAIN_THREADS MKL_NUM_THREADS=$TRAIN_THREADS PYTHONPATH=src $PY ops/vsmt/ruling89_train.py --source $SRC0 --source $SRC1 --arm VSMT-lean --seed $SEED --out-dir $T $REV --group-selection > $LOG_DIR/train-A$SEED.log 2>&1; echo \"train A$SEED exit \$?\"" >> "$TRAIN_JOBS"
done
xargs -d '\n' -P 5 -I{} bash -c '{}' < "$TRAIN_JOBS" >> "$LOG_DIR/train_exits.log" 2>&1
TRAIN_FAILED=$(count_bad "$LOG_DIR/train_exits.log")
echo "[$(date)] retrainings: $TRAIN_FAILED failed"; for SEED in $SEEDS; do tail -1 "$LOG_DIR/train-A$SEED.log" 2>/dev/null; done
[ "$TRAIN_FAILED" = "0" ] || finish training_failed

# 3. reproduction check: stop before any audit unless all five total-loss selections reproduce 9722290
$PY ops/vsmt/ruling96_selection_check.py --previous "$R93/training/round1/VSMT-lean" --retrained "$DIAG/training/round1/VSMT-lean" \
  --output "$EXPORT_DIR/vsmt_lean_ruling96_selection_$COMMIT.json" > "$LOG_DIR/check.log" 2>&1
CHECK_RC=$?
cat "$LOG_DIR/check.log"
for SEED in $SEEDS; do cp "$DIAG/training/round1/VSMT-lean/A$SEED/training_receipt.json" "$EXPORT_DIR/vsmt_lean_ruling96_train1_A${SEED}_$COMMIT.json"; done
[ "$CHECK_RC" = "0" ] || finish original_selection_not_reproduced

# 4. the grouped heads in the joint closed loop
episode_root() { for R in "$OUTPUTS/lean-s1-02a-5f9aa71" "$OUTPUTS/lean-s1-02b-5f9aa71"; do [ -d "$R/$1" ] && echo "$R/$1" && return; done; }
EPISODES=$(for E in $(ls "$PASS_ROOT/dagger_round_1"); do [ -f "$PASS_ROOT/dagger_round_1/$E/VSMT-lean/receipt.json" ] && echo "$E"; done)
[ "$(echo $EPISODES | wc -w)" = "39" ] || finish development_episodes_not_39
frames_of() { ls "$CACHE_ROOT/$1" | grep -c 'cache.json.gz$'; }
JOBS=$LOG_DIR/audit_jobs.txt
for SEED in $SEEDS; do
  OUT=$DIAG/audit/GROUPED-A$SEED; W=$DIAG/training/round1/VSMT-lean/A$SEED/weights_grouped.json
  for EP in $EPISODES; do
    [ -f "$OUT/$EP/VSMT-lean/node_audit.json" ] && continue
    printf '%s\t%s\n' "$(frames_of $EP)" "$PY ops/vsmt/lean_s2_05_node_audit.py run --cache-root $CACHE_ROOT --episode-root $(episode_root $EP) --geometry-root $GEOMETRY_ROOT --episode-id $EP --arm VSMT-lean --config '{\"tau_r\": 0.5}' --heads $W --descriptor reid_projection:vitb14 --weights $REID_WEIGHTS --output-root $OUT --device cpu > $LOG_DIR/GROUPED-A$SEED-$EP.log 2>&1; echo \"GROUPED-A$SEED $EP exit \$?\""
  done
done | sort -t$'\t' -k1,1nr | cut -f2- > "$JOBS"
echo "[$(date)] $(wc -l < "$JOBS") grouped joint audits queued on $WORKERS workers (largest episode first)"
xargs -d '\n' -P "$WORKERS" -I{} bash -c '{}' < "$JOBS" >> "$LOG_DIR/audit_exits.log" 2>&1
AUDITS_FAILED=$(count_bad "$LOG_DIR/audit_exits.log")
echo "[$(date)] grouped joint audits: $(grep -c 'exit 0$' "$LOG_DIR/audit_exits.log" 2>/dev/null) ok, $AUDITS_FAILED failed"

# 5. merges and the ruling-95 reading against the d835cd3 AssocOnly heads and rule arms
MERGES_FAILED=0; ARGS=()
for SEED in $SEEDS; do
  RESULT=$EXPORT_DIR/vsmt_lean_ruling96_audit_GROUPED-A${SEED}_$COMMIT.json
  $PY ops/vsmt/lean_s2_05_node_audit.py merge --output-root "$DIAG/audit/GROUPED-A$SEED" --arm VSMT-lean --results "$RESULT" > "$LOG_DIR/merge-A$SEED.log" 2>&1 || MERGES_FAILED=$((MERGES_FAILED + 1))
  ARGS+=(--group "VSMT-lean:$SEED:$RESULT" --group "AssocOnly:$SEED:$EXPORT_DIR/vsmt_lean_ruling95_audit_ASSOC-A${SEED}_$PREV.json")
done
for ARM in $RULE_ARMS; do ARGS+=(--rule-arm "$ARM:$EXPORT_DIR/vsmt_lean_ruling95_audit_RULE-${ARM}_$PREV.json"); done
echo "[$(date)] merges failed: $MERGES_FAILED"
$PY ops/vsmt/ruling95_reading.py "${ARGS[@]}" --output "$EXPORT_DIR/vsmt_lean_ruling96_reading_$COMMIT.json" > "$LOG_DIR/reading.log" 2>&1
READING_RC=$?
echo "[$(date)] reading exit $READING_RC"; cat "$LOG_DIR/reading.log"
finish done
