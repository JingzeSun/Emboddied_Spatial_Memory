#!/bin/bash
# Ruling 97 (a) (2026-10-01, user: "待裁 97 取 (a)，加原规则敏感性一行，跑完拉回结果后立即关机"): the LOG-295 version, frozen,
#   read once on the ruling-81 confirmation set.  ops/vsmt/ruling97_freeze.json fixes everything: the five grouped VSMT-lean heads
#   (primary), the five total-loss VSMT-lean heads (registered sensitivity row), the five AssocOnly heads, the four rule arms at
#   their development configurations; tau_r 0.5 on the ln w corrected logit, k' 3, the frozen front end and evaluation code.
#   No training, no selection.  ruling97_verify.py checks every frozen input first (head digests, rule-arm configurations, the
#   house list; the evaluated houses are the listed ones with episode, cache and geometry, 43 expected) and stops before any
#   audit otherwise.  Then 19 groups x 43 audits, largest episode first, merges, and ruling95_reading.py twice: the primary
#   reading (grouped heads) and the sensitivity reading (total-loss heads), both against AssocOnly and the rule arms.
#   The confirmation set is read once: an engineering failure may be resumed with the same frozen inputs (RESUME=1), nothing
#   else.  FALLBACK_SHUTDOWN_SECONDS > 0 arms the late fallback power-off as before.
set -u
WORKTREE=$(cd "$(dirname "$0")/../.." && pwd)
cd "$WORKTREE" || exit 2
COMMIT=$(git rev-parse --short HEAD)
PY=/root/miniconda3/bin/python3.12
AUTODL=/root/autodl-tmp
OUTPUTS=$AUTODL/vsmt_outputs
EXPORT_DIR=$OUTPUTS/exports
LOG_DIR=$OUTPUTS/run_logs/ruling97-$COMMIT
FREEZE=$WORKTREE/ops/vsmt/ruling97_freeze.json
EPISODE_ROOT=$AUTODL/vsmt_outputs/lean-s1-02c-confirm-2339baa
CACHE_ROOT=$AUTODL/vsmt_caches/lean-s1-03-oracle-confirm-6b65cb1
GEOMETRY_ROOT=$AUTODL/vsmt_private/lean-s1-04-geometry-confirm-6b65cb1
REID_WEIGHTS=$AUTODL/vsmt_private/lean-s1-04-diagnostics-oracle-caa50c7/reid_head_vitb14.json
FROZEN_AT=7c76970
DIAG=$AUTODL/vsmt_private/ruling97-$COMMIT
STATUS=$EXPORT_DIR/ruling97_$COMMIT.status.json
QUOTA=$(awk '{ if ($1 == "max") print 16; else print int($1 / $2) }' /sys/fs/cgroup/cpu.max 2>/dev/null || echo 16)
WORKERS=${WORKERS:-$((QUOTA - 4))}
RESUME=${RESUME:-0}
FALLBACK_SHUTDOWN_SECONDS=${FALLBACK_SHUTDOWN_SECONDS:-0}
SEEDS="7 19 31 43 59"
RULE_ARMS="TAF ELU-P RAC LOW"
mkdir -p "$EXPORT_DIR" "$LOG_DIR" "$DIAG"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
count_bad() { [ -f "$1" ] || { echo 0; return; }; grep -vc 'exit 0$' "$1"; return 0; }
finish() {
  $PY -c "import json,sys,time; json.dump({'commit': '$COMMIT', 'stage_reached': sys.argv[1], 'finished_cst': time.strftime('%Y-%m-%d %H:%M:%S'),
    'suite_exit': '${SUITE_RC:-}', 'verify_exit': '${VERIFY_RC:-}', 'audits_failed': '${AUDITS_FAILED:-}', 'merges_failed': '${MERGES_FAILED:-}',
    'primary_reading_exit': '${PRIMARY_RC:-}', 'sensitivity_reading_exit': '${SENSITIVITY_RC:-}', 'freeze': 'ops/vsmt/ruling97_freeze.json',
    'workers': $WORKERS, 'cpu_quota': $QUOTA, 'memory_max': '$(cat /sys/fs/cgroup/memory.max 2>/dev/null)',
    'worker_basis': 'cgroup CPU quota minus four; each audit is one single-threaded process of about 1-2 GB; largest episode first',
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
echo "[$(date)] ruling 97 confirmation at $COMMIT: cpu quota $QUOTA, $WORKERS workers, memory.max $(cat /sys/fs/cgroup/memory.max 2>/dev/null)"
if [ "$RESUME" != "1" ]; then
  PYTHONPATH=src $PY -m unittest discover -s tests -t tests -p "test_*.py" > "$LOG_DIR/suite.log" 2>&1
  SUITE_RC=$?
  echo "[$(date)] suite exit $SUITE_RC: $(grep -E '^Ran |^OK|FAILED' "$LOG_DIR/suite.log" | tail -2 | tr '\n' ' ')"
  [ "$SUITE_RC" = "0" ] || finish suite_failed
fi

# 1. the evaluation code is the one the frozen version was read with, and every frozen input checks out
CORE="src/vsmt/lean_runner.py src/vsmt/lean_assignment.py src/vsmt/lean_arms.py src/vsmt/lean_memory.py src/vsmt/lean_teacher.py src/vsmt/lean_evaluation.py src/vsmt/lean_model.py configs/vsmt"
git diff --quiet "$FROZEN_AT" HEAD -- $CORE ops/vsmt/lean_s2_05_node_audit.py ops/vsmt/ruling95_reading.py ops/vsmt/ruling82_seed_analysis.py || finish evaluation_code_changed_since_the_frozen_version
PYTHONPATH=src $PY ops/vsmt/ruling97_verify.py --freeze "$FREEZE" --autodl-root "$AUTODL" --plan "$LOG_DIR/plan.tsv" --episodes "$LOG_DIR/episodes.txt" \
  --output "$EXPORT_DIR/vsmt_lean_ruling97_verify_$COMMIT.json" > "$LOG_DIR/verify.log" 2>&1
VERIFY_RC=$?
cat "$LOG_DIR/verify.log"
[ "$VERIFY_RC" = "0" ] || finish frozen_inputs_not_verified

# 2. 19 groups x the evaluated episodes, largest episode first
frames_of() { ls "$CACHE_ROOT/$1" | grep -c 'cache.json.gz$'; }
JOBS=$LOG_DIR/jobs.txt
while IFS=$'\t' read -r GROUP ARM CONFIG HEADS; do
  OUT=$DIAG/audit/$GROUP
  HEADFLAG=""; [ -n "$HEADS" ] && HEADFLAG="--heads $HEADS"
  while read -r EP; do
    [ -f "$OUT/$EP/$ARM/node_audit.json" ] && continue
    printf '%s\t%s\n' "$(frames_of $EP)" "$PY ops/vsmt/lean_s2_05_node_audit.py run --cache-root $CACHE_ROOT --episode-root $EPISODE_ROOT/$EP --geometry-root $GEOMETRY_ROOT --episode-id $EP --arm $ARM --config '$CONFIG' $HEADFLAG --descriptor reid_projection:vitb14 --weights $REID_WEIGHTS --output-root $OUT --device cpu > $LOG_DIR/$GROUP-$EP.log 2>&1; echo \"$GROUP $EP exit \$?\""
  done < "$LOG_DIR/episodes.txt"
done < "$LOG_DIR/plan.tsv" | sort -t$'\t' -k1,1nr | cut -f2- > "$JOBS"
echo "[$(date)] $(wc -l < "$JOBS") confirmation audits queued on $WORKERS workers (largest episode first)"
xargs -d '\n' -P "$WORKERS" -I{} bash -c '{}' < "$JOBS" >> "$LOG_DIR/audit_exits.log" 2>&1
AUDITS_FAILED=$(count_bad "$LOG_DIR/audit_exits.log")
echo "[$(date)] confirmation audits: $(grep -c 'exit 0$' "$LOG_DIR/audit_exits.log" 2>/dev/null) ok, $AUDITS_FAILED failed"

# 3. merges and the two registered readings
MERGES_FAILED=0
result_of() { echo "$EXPORT_DIR/vsmt_lean_ruling97_audit_$1_$COMMIT.json"; }
while IFS=$'\t' read -r GROUP ARM CONFIG HEADS; do
  $PY ops/vsmt/lean_s2_05_node_audit.py merge --output-root "$DIAG/audit/$GROUP" --arm "$ARM" --results "$(result_of "$GROUP")" > "$LOG_DIR/merge-$GROUP.log" 2>&1 || MERGES_FAILED=$((MERGES_FAILED + 1))
done < "$LOG_DIR/plan.tsv"
echo "[$(date)] merges failed: $MERGES_FAILED"
RULES=(); for ARM in $RULE_ARMS; do RULES+=(--rule-arm "$ARM:$(result_of "RULE-$ARM")"); done
reading() {  # VSMT-lean group prefix, output label
  local ARGS=()
  for SEED in $SEEDS; do ARGS+=(--group "VSMT-lean:$SEED:$(result_of "$1-A$SEED")" --group "AssocOnly:$SEED:$(result_of "ASSOC-A$SEED")"); done
  $PY ops/vsmt/ruling95_reading.py "${ARGS[@]}" "${RULES[@]}" --output "$EXPORT_DIR/vsmt_lean_ruling97_reading_$2_$COMMIT.json" > "$LOG_DIR/reading-$2.log" 2>&1
}
reading GROUPED primary; PRIMARY_RC=$?
echo "[$(date)] primary reading exit $PRIMARY_RC"; cat "$LOG_DIR/reading-primary.log"
reading ORIGINAL sensitivity; SENSITIVITY_RC=$?
echo "[$(date)] sensitivity reading exit $SENSITIVITY_RC"; cat "$LOG_DIR/reading-sensitivity.log"
finish done
