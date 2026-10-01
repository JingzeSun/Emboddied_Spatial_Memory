#!/bin/bash
# S2-06: the SAM 2.1 development table, one command (ruling 100, user 2026-10-01: 「待裁 100 取 (a)，加 100-6 复现要求」).
#
# Usage (server, from a clean detached worktree of the reviewed commit; nothing here needs a GPU):
#   bash ops/vsmt/s2_06_sam2.sh all        every stage in order; a finished stage is kept, a hold or a stop ends the run
#   bash ops/vsmt/s2_06_sam2.sh <stage>    one stage; every earlier stage must be done
#   bash ops/vsmt/s2_06_sam2.sh status     the stage markers
#   long runs in the background:  nohup bash ops/vsmt/s2_06_sam2.sh all > <log> 2>&1 &
#   (launch and return: the driver refuses to start while a 'sleep N' or a shutdown is pending, since an earlier
#    driver's fallback power-off may be armed; kill that driver and its sleep first)
#
# Stages (each writes a marker under $RUN_ROOT/stages and its exports under $EXPORT_DIR, named *_<tag>.json):
#   check              full test suite; every input pinned in $RUN_ROOT/inputs.json (two caches of 39 episodes sealed with the
#                      right mask source, geometry tables, S1-02 episodes, both ReID heads at their S0-03 digests, the 7c76970
#                      grouped heads at their frozen digests, the committed exports the reading compares with); episodes by size
#   pilot              the largest SAM2 episode: its calibration job (kept: it is part of the calibration pass) and a timing-only
#                      TAF audit, both measured; compared with the instance-segmentation audit time of the same episode
#   calibration        ruling 75: TAF at theta_a 0.7, no gate, with the calibration histograms and the ELU-P counts, 39 episodes
#   grid-review        ruling 100-2 step 2 with the ruling 101 (1)(a) verdict (ops/vsmt/s2_06_grid_review.py): a SAM2 point outside a
#                      grid on a side the instance-segmentation point is not -> STOP for a ruling (marker 'stopped'); outside on
#                      the same side -> listed for S3-01, no stop
#   elu-p-fit          ruling 75 / 100-1 (ii): fit-elu-p over the calibration pass; until the SAM2 values are registered in S0-05
#                      (a commit, pre-authorised by ruling 68 (10)) the stage HOLDS; at the registering commit it checks equality
#   round0             ELU-P at the rollout configuration and the SAM2 fitted values: round-0 records, 39 episodes
#   train0             VSMT-lean and AssocOnly, seed 7, the frozen recipe (ruling89_train.py --revision-91), total-loss selection
#   round1             each learned arm's own round-1 records from its round-0 head (VSMT-lean at tau_r 0.5)
#   train1             both arms at the five seeds on round 0 + own round 1; VSMT-lean also keeps the grouped selection
#   audits             19 groups x 39 SAM2 episodes: VSMT-lean, NoVersion (grouped heads) and AssocOnly at five seeds; TAF, RAC,
#                      LOW at their development configurations, ELU-P at its round-0 configuration with the SAM2 fitted values
#   instance-noversion a reproduction probe (current code reproduces a 7c76970 instance audit), then NoVersion with the 7c76970
#                      grouped heads on the 39 instance-segmentation episodes (5 x 39)
#   merge              node-audit merges of all 24 groups
#   reading            ops/vsmt/s2_06_reading.py: ruling 100-3 on both front ends, side by side
#   verify             a determinism probe (one SAM2 audit run again), every recorded digest checked, the final run manifest
#
# Environment (optional): RUN_ROOT (default $AUTODL/vsmt_private/s2-06-sam2), TRAIN_THREADS (4; weights are bit-reproducible at
#   the same commit and thread count), WORKERS (override of the computed audit/pass workers), FALLBACK_SHUTDOWN_SECONDS (0 = off;
#   > 0: after the status is written, power off that long later unless another vsmt job runs), ACCEPT_CODE_CHANGE=1 (keep stages
#   finished at an earlier commit although code changed since; recorded in the marker), REPRO_TRAINING=1 (verify also retrains the
#   round-0 AssocOnly head and compares its digest), PY, AUTODL and the input paths below.
# Resume: run 'all' again; finished stages are kept, a stage whose code changed since it ran is refused (only the SAM2 fit
#   registration and documents may change), passes resume episode by episode, audits and trainings skip finished outputs.
set -u
WORKTREE=$(cd "$(dirname "$0")/../.." && pwd)
cd "$WORKTREE" || exit 2
HEAD_COMMIT=$(git rev-parse HEAD)
SHORT=$(git rev-parse --short HEAD)
PY=${PY:-/root/miniconda3/bin/python3.12}
AUTODL=${AUTODL:-/root/autodl-tmp}
OUTPUTS=$AUTODL/vsmt_outputs
EXPORT_DIR=${EXPORT_DIR:-$OUTPUTS/exports}
SAM2_CACHE=${SAM2_CACHE:-$AUTODL/vsmt_caches/lean-s1-03-154776d}
INSTANCE_CACHE=${INSTANCE_CACHE:-$AUTODL/vsmt_caches/lean-s1-03-oracle-8ebbd05}
GEOMETRY_ROOT=${GEOMETRY_ROOT:-$AUTODL/vsmt_private/lean-s1-04-geometry-154776d}
EPISODE_ROOTS=${EPISODE_ROOTS:-$OUTPUTS/lean-s1-02a-5f9aa71,$OUTPUTS/lean-s1-02b-5f9aa71}
SAM2_REID=${SAM2_REID:-$AUTODL/vsmt_private/exports/reid_head_vitb14_154776d.json}
INSTANCE_REID=${INSTANCE_REID:-$AUTODL/vsmt_private/lean-s1-04-diagnostics-oracle-caa50c7/reid_head_vitb14.json}
INSTANCE_HEADS=${INSTANCE_HEADS:-$AUTODL/vsmt_private/ruling96-7c76970/training/round1/VSMT-lean}
INSTANCE_TAF_AUDITS=${INSTANCE_TAF_AUDITS:-$AUTODL/vsmt_private/ruling95-d835cd3/audit/RULE-TAF}
RUN_ROOT=${RUN_ROOT:-$AUTODL/vsmt_private/s2-06-sam2}
TRAIN_THREADS=${TRAIN_THREADS:-4}
FALLBACK_SHUTDOWN_SECONDS=${FALLBACK_SHUTDOWN_SECONDS:-0}
ACCEPT_CODE_CHANGE=${ACCEPT_CODE_CHANGE:-0}
REPRO_TRAINING=${REPRO_TRAINING:-0}
STAGES="check pilot calibration grid-review elu-p-fit round0 train0 round1 train1 audits instance-noversion merge reading verify"
SEEDS="7 19 31 43 59"
RULE_ARMS="TAF ELU-P RAC LOW"
REV="--revision-91"
DESCRIPTOR=reid_projection:vitb14
COMMAND=${1:-}
case " $STAGES all status " in *" $COMMAND "*) ;; *) echo "usage: bash ops/vsmt/s2_06_sam2.sh all|status|<stage> (stages: $STAGES)"; exit 2;; esac
if [ "$COMMAND" = "status" ]; then PYTHONPATH=src $PY ops/vsmt/s2_06_manifest.py status --run-root "$RUN_ROOT"; exit 0; fi
mkdir -p "$RUN_ROOT/stages" "$EXPORT_DIR"
[ -f "$RUN_ROOT/run_tag" ] || echo "$SHORT" > "$RUN_ROOT/run_tag"
TAG=$(cat "$RUN_ROOT/run_tag")  # the commit of the first check: every export of this run carries it
LOG_DIR=$OUTPUTS/run_logs/s2-06-$TAG
STATUS=$EXPORT_DIR/s2_06_$TAG.status.json
mkdir -p "$LOG_DIR"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1  # passes and audits: one thread per process
ACCEPT_FLAG=""; [ "$ACCEPT_CODE_CHANGE" = "1" ] && ACCEPT_FLAG="--accept-code-change"
DETAIL=""; REACHED=""
M() { PYTHONPATH=src $PY ops/vsmt/s2_06_manifest.py "$@"; }
count_bad() { [ -f "$1" ] || { echo 0; return; }; grep -vc 'exit 0$' "$1"; return 0; }
gate() { $PY -c "import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if ($2) else 1)" "$1"; }
episode_root() { local R; for R in ${EPISODE_ROOTS//,/ }; do [ -d "$R/$1" ] && echo "$R/$1" && return; done; }
largest_first() { sort -t$'\t' -k1,1nr | cut -f2-; }
arm_of() { case $1 in VSMT-*) echo VSMT-lean;; NOVER-*|INSTANCE-NOVER-*) echo NoVersion;; ASSOC-*) echo AssocOnly;; RULE-*) echo "${1#RULE-}";; esac; }
config_of() {  # pass arm -> the registered configuration on the SAM2 front end (ruling 68; ELU-P with the SAM2 fitted values)
  PYTHONPATH=src $PY -c "
import json, sys
sys.path.insert(0, 'ops/vsmt')
import lean_s2_05_development as d
config = d.expected_pass_config(sys.argv[1], sys.argv[2], mask_source='sam2')
assert config is not None and all(value is not None for key, value in config.items() if key != 'd_a'), config
print(json.dumps(config))" "$1" "$2"
}
workers_plan() {  # WORKERS, PASS_WORKERS, TRAIN_PARALLEL from the cgroup quota, memory and the measured peaks (s2_06_manifest.py workers)
  read -r WORKERS_NOW PASS_WORKERS TRAIN_PARALLEL < <(M workers --run-root "$RUN_ROOT" --train-threads "$TRAIN_THREADS" ${WORKERS:+--workers "$WORKERS"})
  echo "[$(date)] workers: audits $WORKERS_NOW, passes $PASS_WORKERS, trainings $TRAIN_PARALLEL x $TRAIN_THREADS threads ($RUN_ROOT/workers.json)"
}

finish() {
  REACHED=$1
  $PY -c "import json, sys, time; json.dump({'tag': '$TAG', 'commit': '$HEAD_COMMIT', 'stage_reached': sys.argv[1], 'detail': sys.argv[2],
    'finished_cst': time.strftime('%Y-%m-%d %H:%M:%S'), 'run_root': '$RUN_ROOT', 'log_dir': '$LOG_DIR',
    'workers': json.load(open('$RUN_ROOT/workers.json')) if __import__('os').path.exists('$RUN_ROOT/workers.json') else None,
    'train_threads': $TRAIN_THREADS, 'fallback_shutdown_seconds': $FALLBACK_SHUTDOWN_SECONDS}, open('$STATUS', 'w'), indent=1)" "$REACHED" "$DETAIL"
  M status --run-root "$RUN_ROOT"
  echo "[$(date)] status written ($REACHED) -> $STATUS"
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

run_pass() {  # pass arm config heads workers [flags...] -- one S2-04 run per SAM2 episode (lean_s2_05_development.py run-pass)
  local PASS=$1 ARM=$2 CONFIG=$3 HEADS=$4 N=$5; shift 5
  PYTHONPATH=src $PY ops/vsmt/lean_s2_05_development.py run-pass --pass "$PASS" --arm "$ARM" --config "$CONFIG" ${HEADS:+--heads "$HEADS"} \
    --cache-root "$SAM2_CACHE" --episode-roots "$EPISODE_ROOTS" --geometry-root "$GEOMETRY_ROOT" --output-root "$RUN_ROOT" \
    --descriptor "$DESCRIPTOR" --weights "$SAM2_REID" --mask-source sam2 --workers "$N" --largest-first \
    --worker-basis "S2-06: one single-threaded process per episode, $N workers ($RUN_ROOT/workers.json)" --resume "$@"
}
export_pass() {  # pass arm name
  $PY ops/vsmt/lean_s2_05_export.py --output-root "$RUN_ROOT" --pass "$1" --arm "$2" --results "$EXPORT_DIR/vsmt_lean_s2_06_$3_$TAG.json"
}
audit_jobs() {  # front group config heads -- one node-audit line per episode not yet audited, prefixed by its frame count
  local FRONT=$1 GROUP=$2 CONFIG=$3 HEADS=$4 ARM CACHE REID TSV MASK OUT HEADFLAG="" FRAMES EP
  ARM=$(arm_of "$GROUP")
  if [ "$FRONT" = sam2 ]; then CACHE=$SAM2_CACHE; REID=$SAM2_REID; MASK=sam2; OUT=$RUN_ROOT/audit/$GROUP
  else CACHE=$INSTANCE_CACHE; REID=$INSTANCE_REID; MASK=simulator_instance_masks; OUT=$RUN_ROOT/audit_instance/$GROUP; fi
  TSV=$RUN_ROOT/episodes_$MASK.tsv
  [ -n "$HEADS" ] && HEADFLAG="--heads $HEADS"
  while IFS=$'\t' read -r FRAMES EP; do
    [ -f "$OUT/$EP/$ARM/node_audit.json" ] && continue
    printf '%s\t%s\n' "$FRAMES" "$PY ops/vsmt/lean_s2_05_node_audit.py run --cache-root $CACHE --episode-root $(episode_root "$EP") --geometry-root $GEOMETRY_ROOT --episode-id $EP --arm $ARM --config '$CONFIG' $HEADFLAG --descriptor $DESCRIPTOR --weights $REID --mask-source $MASK --output-root $OUT --device cpu > $LOG_DIR/audit-$GROUP-$EP.log 2>&1; echo \"$GROUP $EP exit \$?\""
  done < "$TSV"
}
run_jobs() {  # jobs-file parallelism exits-file (the exits of earlier attempts move to <exits-file>.history)
  [ -f "$3" ] && cat "$3" >> "$3.history"
  : > "$3"
  echo "[$(date)] $(wc -l < "$1") jobs on $2 workers (largest episode first)"
  xargs -d '\n' -P "$2" -I{} bash -c '{}' < "$1" >> "$3" 2>&1
  local BAD; BAD=$(count_bad "$3")
  echo "[$(date)] $(grep -c 'exit 0$' "$3" 2>/dev/null) ok, $BAD failed (exits in $3)"
  [ "$BAD" = "0" ]
}

# ---------------------------------------------------------------- stages
stage_check() {
  PYTHONPATH=src $PY -m unittest discover -s tests -t tests -p "test_*.py" > "$LOG_DIR/suite-$SHORT.log" 2>&1
  local RC=$?
  echo "[$(date)] suite exit $RC: $(grep -E '^Ran |^OK|FAILED' "$LOG_DIR/suite-$SHORT.log" | tail -2 | tr '\n' ' ')"
  [ "$RC" = "0" ] || { DETAIL="full test suite failed ($LOG_DIR/suite-$SHORT.log)"; return 1; }
  M check --run-root "$RUN_ROOT" --repo-root "$WORKTREE" --autodl-root "$AUTODL" --sam2-cache "$SAM2_CACHE" --instance-cache "$INSTANCE_CACHE" \
    --geometry-root "$GEOMETRY_ROOT" --episode-roots "$EPISODE_ROOTS" --sam2-reid "$SAM2_REID" --instance-reid "$INSTANCE_REID"
  RC=$?
  cp "$RUN_ROOT/inputs.json" "$RUN_ROOT/inputs-$SHORT.json"
  cp "$RUN_ROOT/inputs.json" "$EXPORT_DIR/vsmt_lean_s2_06_check_$TAG.json"
  [ "$RC" = "0" ] || { DETAIL="input check failed: problems in $RUN_ROOT/inputs.json"; return 1; }
  workers_plan
  DETAIL="suite and inputs ok at $SHORT"
}

stage_pilot() {
  local FRAMES EP P1="" P2="" R1=0 R2=0
  read -r FRAMES EP < <(head -1 "$RUN_ROOT/episodes_sam2.tsv")
  mkdir -p "$RUN_ROOT/pilot"
  echo "[$(date)] pilot on the largest SAM2 episode $EP ($FRAMES frames): its calibration job and a timing-only TAF audit"
  # a job measured with exit 0 earlier is not run again: its timing would be that of a resume
  if ! gate "$RUN_ROOT/pilot/calibration_job.json" "d['exit'] == 0" 2>/dev/null; then
    M run-measured --out "$RUN_ROOT/pilot/calibration_job.json" -- $PY ops/vsmt/lean_s2_05_development.py run-pass --pass calibration --arm TAF \
      --config '{"theta_a": 0.7, "d_a": null}' --calibration --elu-p-counts --episodes "$EP" --cache-root "$SAM2_CACHE" \
      --episode-roots "$EPISODE_ROOTS" --geometry-root "$GEOMETRY_ROOT" --output-root "$RUN_ROOT" --descriptor "$DESCRIPTOR" \
      --weights "$SAM2_REID" --mask-source sam2 --workers 1 --worker-basis "S2-06 pilot: the largest episode alone" --resume \
      > "$LOG_DIR/pilot-calibration.log" 2>&1 &
    P1=$!
  fi
  if ! gate "$RUN_ROOT/pilot/audit_job.json" "d['exit'] == 0" 2>/dev/null; then
    M run-measured --out "$RUN_ROOT/pilot/audit_job.json" -- $PY ops/vsmt/lean_s2_05_node_audit.py run --cache-root "$SAM2_CACHE" \
      --episode-root "$(episode_root "$EP")" --geometry-root "$GEOMETRY_ROOT" --episode-id "$EP" --arm TAF --config "$(config_of development_table TAF)" \
      --descriptor "$DESCRIPTOR" --weights "$SAM2_REID" --mask-source sam2 --output-root "$RUN_ROOT/pilot/audit" --device cpu \
      > "$LOG_DIR/pilot-audit.log" 2>&1 &
    P2=$!
  fi
  [ -n "$P1" ] && { wait "$P1"; R1=$?; }
  [ -n "$P2" ] && { wait "$P2"; R2=$?; }
  M pilot --run-root "$RUN_ROOT" --instance-audit "$INSTANCE_TAF_AUDITS/$EP/TAF/node_audit.json"
  cp "$RUN_ROOT/pilot/pilot.json" "$EXPORT_DIR/vsmt_lean_s2_06_pilot_$TAG.json"
  [ "$R1" = "0" ] && [ "$R2" = "0" ] || { DETAIL="pilot job failed (calibration $R1, audit $R2)"; return 1; }
  workers_plan
  DETAIL="pilot on $EP: see $RUN_ROOT/pilot/pilot.json"
}

stage_calibration() {
  workers_plan
  run_pass calibration TAF '{"theta_a": 0.7, "d_a": null}' "" "$PASS_WORKERS" --calibration --elu-p-counts > "$LOG_DIR/calibration.log" 2>&1
  local RC=$?
  tail -1 "$LOG_DIR/calibration.log"
  [ "$RC" = "0" ] || { DETAIL="calibration pass failed ($LOG_DIR/calibration.log)"; return 1; }
  $PY ops/vsmt/lean_s2_05_development.py calibration-report --output-root "$RUN_ROOT" > "$LOG_DIR/calibration-report.log" 2>&1 \
    || { DETAIL="calibration-report failed"; return 1; }
  export_pass calibration TAF calibration || { DETAIL="calibration export failed"; return 1; }
  DETAIL="39 calibration episodes merged"
}

stage_grid_review() {
  $PY ops/vsmt/s2_06_grid_review.py --calibration "$RUN_ROOT/calibration/calibration_report.json" \
    --reference results/vsmt_lean_s2_05_calibration_oracle_850c533.json --output "$EXPORT_DIR/vsmt_lean_s2_06_grid_review_$TAG.json"
  case $? in
    0) DETAIL="no grid out by ruling 101 (1)(a); checks outside on the same side as instance segmentation are listed for S3-01";;
    4) DETAIL="out of grid ($EXPORT_DIR/vsmt_lean_s2_06_grid_review_$TAG.json): stop, a ruling stores grids per mask_source (ruling 100-2 step 2, 101 (1)(a))"; return 11;;
    *) DETAIL="grid review refused its inputs"; return 1;;
  esac
}

stage_elu_p_fit() {
  $PY ops/vsmt/lean_s2_05_development.py fit-elu-p --output-root "$RUN_ROOT" --from-pass calibration > "$LOG_DIR/elu-p-fit.log" 2>&1
  local RC=$?
  cat "$LOG_DIR/elu-p-fit.log"
  cp "$RUN_ROOT/calibration/elu_p_fit.json" "$EXPORT_DIR/vsmt_lean_s2_06_elu_p_fit_$TAG.json" 2>/dev/null
  [ "$RC" = "0" ] || { DETAIL="fit refused, or a refit differs from the registered SAM2 values (exit $RC)"; return 1; }
  if gate "$RUN_ROOT/calibration/elu_p_fit.json" "d['mask_source'] == 'sam2' and d['matches_the_registered_values'] is True"; then
    DETAIL="the refit equals the SAM2 values registered in S0-05"
    return 0
  fi
  DETAIL="hold: register the SAM2 fitted values of $RUN_ROOT/calibration/elu_p_fit.json in S0-05 (ruling 68 (10), ruling 100-1 (ii)), commit, then run 'all' at that commit"
  return 10
}

stage_round0() {
  workers_plan
  local CONFIG
  CONFIG=$(config_of dagger_round_0 ELU-P) || { DETAIL="no registered ELU-P round-0 configuration for sam2"; return 1; }
  echo "[$(date)] round 0: ELU-P at $CONFIG"
  run_pass dagger_round_0 ELU-P "$CONFIG" "" "$PASS_WORKERS" > "$LOG_DIR/round0.log" 2>&1
  local RC=$?
  tail -1 "$LOG_DIR/round0.log"
  [ "$RC" = "0" ] || { DETAIL="round-0 pass failed ($LOG_DIR/round0.log)"; return 1; }
  export_pass dagger_round_0 ELU-P round0_ELU-P || { DETAIL="round-0 export failed"; return 1; }
  DETAIL="39 round-0 ELU-P episodes"
}

train_job() {  # round arm seed out-dir sources... -- one training line (the frozen recipe, TRAIN_THREADS threads, peak memory measured)
  local ROUND=$1 ARM=$2 SEED=$3 OUT=$4 GROUP=""; shift 4
  local SOURCES="" S
  for S in "$@"; do SOURCES="$SOURCES --source $S"; done
  [ "$ROUND" = "1" ] && [ "$ARM" = "VSMT-lean" ] && GROUP="--group-selection"
  echo "mkdir -p $OUT && env OMP_NUM_THREADS=$TRAIN_THREADS MKL_NUM_THREADS=$TRAIN_THREADS $PY ops/vsmt/s2_06_manifest.py run-measured --out $OUT/measured.json -- $PY ops/vsmt/ruling89_train.py$SOURCES --arm $ARM --seed $SEED --out-dir $OUT $REV $GROUP > $LOG_DIR/train$ROUND-$ARM-A$SEED.log 2>&1; echo \"train$ROUND $ARM A$SEED exit \$?\""
}
check_trainings() {  # round -- every receipt present and not diverged; receipts exported
  local ROUND=$1 R BAD=0
  for R in $(find "$RUN_ROOT/training/round$ROUND" -name training_receipt.json | sort); do
    gate "$R" "not d['diverged'] and d.get('validation_curve_terms')" || { echo "diverged or without per-epoch terms: $R"; BAD=$((BAD + 1)); }
    local ARM SEED
    ARM=$($PY -c "import json,sys; print(json.load(open(sys.argv[1]))['arm'])" "$R"); SEED=$($PY -c "import json,sys; print(json.load(open(sys.argv[1]))['seed'])" "$R")
    cp "$R" "$EXPORT_DIR/vsmt_lean_s2_06_train${ROUND}_${ARM}_A${SEED}_$TAG.json"
  done
  [ "$BAD" = "0" ]
}

stage_train0() {
  local JOBS=$LOG_DIR/train0_jobs.txt ARM
  : > "$JOBS"
  for ARM in VSMT-lean AssocOnly; do
    [ -f "$RUN_ROOT/training/round0/$ARM/training_receipt.json" ] && continue
    train_job 0 "$ARM" 7 "$RUN_ROOT/training/round0/$ARM" "$RUN_ROOT:dagger_round_0:ELU-P" >> "$JOBS"
  done
  run_jobs "$JOBS" 2 "$LOG_DIR/train0_exits.log" || { DETAIL="a round-0 training failed"; return 1; }
  [ "$(find "$RUN_ROOT/training/round0" -name training_receipt.json | wc -l)" = "2" ] || { DETAIL="round-0 receipts missing"; return 1; }
  check_trainings 0 || { DETAIL="a round-0 training diverged"; return 1; }
  workers_plan
  DETAIL="round-0 heads for VSMT-lean and AssocOnly (seed 7)"
}

stage_round1() {
  workers_plan
  local HALF=$(( (PASS_WORKERS + 1) / 2 )) P1 P2 R1 R2
  run_pass dagger_round_1 VSMT-lean "$(config_of dagger_round_1 VSMT-lean)" "$RUN_ROOT/training/round0/VSMT-lean/weights.json" "$HALF" \
    > "$LOG_DIR/round1-VSMT-lean.log" 2>&1 &
  P1=$!
  run_pass dagger_round_1 AssocOnly "$(config_of dagger_round_1 AssocOnly)" "$RUN_ROOT/training/round0/AssocOnly/weights.json" "$HALF" \
    > "$LOG_DIR/round1-AssocOnly.log" 2>&1 &
  P2=$!
  wait "$P1"; R1=$?; wait "$P2"; R2=$?
  tail -1 "$LOG_DIR/round1-VSMT-lean.log" "$LOG_DIR/round1-AssocOnly.log"
  [ "$R1" = "0" ] && [ "$R2" = "0" ] || { DETAIL="round-1 pass failed (VSMT-lean $R1, AssocOnly $R2)"; return 1; }
  export_pass dagger_round_1 VSMT-lean round1_VSMT-lean && export_pass dagger_round_1 AssocOnly round1_AssocOnly || { DETAIL="round-1 export failed"; return 1; }
  DETAIL="round-1 records of both learned arms, 39 episodes each"
}

stage_train1() {
  workers_plan
  local JOBS=$LOG_DIR/train1_jobs.txt SEED ARM
  : > "$JOBS"
  for SEED in $SEEDS; do
    for ARM in VSMT-lean AssocOnly; do
      [ -f "$RUN_ROOT/training/round1/$ARM/A$SEED/training_receipt.json" ] && continue
      train_job 1 "$ARM" "$SEED" "$RUN_ROOT/training/round1/$ARM/A$SEED" "$RUN_ROOT:dagger_round_0:ELU-P" "$RUN_ROOT:dagger_round_1:$ARM" >> "$JOBS"
    done
  done
  run_jobs "$JOBS" "$TRAIN_PARALLEL" "$LOG_DIR/train1_exits.log" || { DETAIL="a round-1 training failed"; return 1; }
  [ "$(find "$RUN_ROOT/training/round1" -name training_receipt.json | wc -l)" = "10" ] || { DETAIL="round-1 receipts missing"; return 1; }
  check_trainings 1 || { DETAIL="a round-1 training diverged"; return 1; }
  DETAIL="ten round-1 heads (VSMT-lean grouped and total-loss, AssocOnly)"
}

stage_audits() {
  workers_plan
  local JOBS=$LOG_DIR/audit_jobs.txt SEED ARM HEADS ELUP
  ELUP=$(config_of dagger_round_0 ELU-P) || { DETAIL="no registered ELU-P configuration for sam2"; return 1; }
  {
    for SEED in $SEEDS; do
      HEADS=$RUN_ROOT/training/round1/VSMT-lean/A$SEED/weights_grouped.json
      audit_jobs sam2 "VSMT-A$SEED" "$(config_of development_table VSMT-lean)" "$HEADS"
      audit_jobs sam2 "NOVER-A$SEED" "$(config_of development_table NoVersion)" "$HEADS"
      audit_jobs sam2 "ASSOC-A$SEED" "$(config_of development_table AssocOnly)" "$RUN_ROOT/training/round1/AssocOnly/A$SEED/weights.json"
    done
    for ARM in TAF RAC LOW; do audit_jobs sam2 "RULE-$ARM" "$(config_of development_table $ARM)" ""; done
    audit_jobs sam2 "RULE-ELU-P" "$ELUP" ""
  } | largest_first > "$JOBS"
  run_jobs "$JOBS" "$WORKERS_NOW" "$LOG_DIR/audit_exits.log" || { DETAIL="SAM2 audits failed (see $LOG_DIR/audit_exits.log)"; return 1; }
  DETAIL="19 groups x 39 SAM2 audits"
}

stage_instance_noversion() {
  workers_plan
  local FRAMES EP PROBE=$RUN_ROOT/verify/instance_probe JOBS=$LOG_DIR/instance_jobs.txt SEED
  read -r FRAMES EP < <(tail -1 "$RUN_ROOT/episodes_simulator_instance_masks.tsv")
  mkdir -p "$RUN_ROOT/verify"
  # reproduction probe: today's code must reproduce the 7c76970 instance-segmentation audit it is set beside (smallest episode, seed 7)
  if [ ! -f "$PROBE/$EP/VSMT-lean/node_audit.json" ]; then
    $PY ops/vsmt/lean_s2_05_node_audit.py run --cache-root "$INSTANCE_CACHE" --episode-root "$(episode_root "$EP")" --geometry-root "$GEOMETRY_ROOT" \
      --episode-id "$EP" --arm VSMT-lean --config "$(config_of development_table VSMT-lean)" --heads "$INSTANCE_HEADS/A7/weights_grouped.json" \
      --descriptor "$DESCRIPTOR" --weights "$INSTANCE_REID" --mask-source simulator_instance_masks --output-root "$PROBE" --device cpu \
      > "$LOG_DIR/instance-probe.log" 2>&1 || { DETAIL="instance reproduction probe failed to run"; return 1; }
  fi
  M probe --rerun "$PROBE/$EP/VSMT-lean/node_audit.json" --merged results/vsmt_lean_ruling96_audit_GROUPED-A7_7c76970.json \
    --out "$RUN_ROOT/verify/probe_instance.json" || { DETAIL="today's code does not reproduce the 7c76970 audit of $EP: stop"; return 1; }
  for SEED in $SEEDS; do
    audit_jobs instance "INSTANCE-NOVER-A$SEED" "$(config_of development_table NoVersion)" "$INSTANCE_HEADS/A$SEED/weights_grouped.json"
  done | largest_first > "$JOBS"
  run_jobs "$JOBS" "$WORKERS_NOW" "$LOG_DIR/instance_exits.log" || { DETAIL="instance NoVersion audits failed"; return 1; }
  DETAIL="5 x 39 instance-segmentation NoVersion audits; reproduction probe identical"
}

stage_merge() {
  local GROUP OUT BAD=0
  for GROUP in $(for S in $SEEDS; do echo VSMT-A$S NOVER-A$S ASSOC-A$S; done) $(for A in $RULE_ARMS; do echo RULE-$A; done) \
               $(for S in $SEEDS; do echo INSTANCE-NOVER-A$S; done); do
    case $GROUP in INSTANCE-*) OUT=$RUN_ROOT/audit_instance/$GROUP;; *) OUT=$RUN_ROOT/audit/$GROUP;; esac
    $PY ops/vsmt/lean_s2_05_node_audit.py merge --output-root "$OUT" --arm "$(arm_of "$GROUP")" \
      --results "$EXPORT_DIR/vsmt_lean_s2_06_audit_${GROUP}_$TAG.json" > "$LOG_DIR/merge-$GROUP.log" 2>&1 || BAD=$((BAD + 1))
  done
  [ "$BAD" = "0" ] || { DETAIL="$BAD merges failed"; return 1; }
  DETAIL="24 merged audits exported"
}

stage_reading() {
  local ARGS=() SEED ARM
  for SEED in $SEEDS; do
    ARGS+=(--sam2-group "VSMT-lean:$SEED:$EXPORT_DIR/vsmt_lean_s2_06_audit_VSMT-A${SEED}_$TAG.json"
           --sam2-group "NoVersion:$SEED:$EXPORT_DIR/vsmt_lean_s2_06_audit_NOVER-A${SEED}_$TAG.json"
           --sam2-group "AssocOnly:$SEED:$EXPORT_DIR/vsmt_lean_s2_06_audit_ASSOC-A${SEED}_$TAG.json"
           --instance-group "VSMT-lean:$SEED:results/vsmt_lean_ruling96_audit_GROUPED-A${SEED}_7c76970.json"
           --instance-group "NoVersion:$SEED:$EXPORT_DIR/vsmt_lean_s2_06_audit_INSTANCE-NOVER-A${SEED}_$TAG.json"
           --instance-group "AssocOnly:$SEED:results/vsmt_lean_ruling95_audit_ASSOC-A${SEED}_d835cd3.json")
  done
  for ARM in $RULE_ARMS; do
    ARGS+=(--sam2-rule-arm "$ARM:$EXPORT_DIR/vsmt_lean_s2_06_audit_RULE-${ARM}_$TAG.json"
           --instance-rule-arm "$ARM:results/vsmt_lean_ruling95_audit_RULE-${ARM}_d835cd3.json")
  done
  $PY ops/vsmt/s2_06_reading.py "${ARGS[@]}" --instance-reading results/vsmt_lean_ruling96_reading_7c76970.json \
    --output "$EXPORT_DIR/vsmt_lean_s2_06_reading_$TAG.json" || { DETAIL="reading refused (see the log)"; return 1; }
  DETAIL="ruling 100-3 reading written"
}

stage_verify() {
  local FRAMES EP PROBE=$RUN_ROOT/verify/sam2_probe
  read -r FRAMES EP < <(tail -1 "$RUN_ROOT/episodes_sam2.tsv")
  if [ ! -f "$PROBE/$EP/VSMT-lean/node_audit.json" ]; then  # determinism: the smallest SAM2 episode's VSMT-A7 audit, run again
    $PY ops/vsmt/lean_s2_05_node_audit.py run --cache-root "$SAM2_CACHE" --episode-root "$(episode_root "$EP")" --geometry-root "$GEOMETRY_ROOT" \
      --episode-id "$EP" --arm VSMT-lean --config "$(config_of development_table VSMT-lean)" --heads "$RUN_ROOT/training/round1/VSMT-lean/A7/weights_grouped.json" \
      --descriptor "$DESCRIPTOR" --weights "$SAM2_REID" --mask-source sam2 --output-root "$PROBE" --device cpu > "$LOG_DIR/sam2-probe.log" 2>&1 \
      || { DETAIL="SAM2 determinism probe failed to run"; return 1; }
  fi
  M probe --rerun "$PROBE/$EP/VSMT-lean/node_audit.json" --original "$RUN_ROOT/audit/VSMT-A7/$EP/VSMT-lean/node_audit.json" \
    --out "$RUN_ROOT/verify/probe_sam2.json" || { DETAIL="the SAM2 audit of $EP is not reproduced"; return 1; }
  if [ "$REPRO_TRAINING" = "1" ]; then  # optional: retrain the round-0 AssocOnly head and compare the digest
    local T=$RUN_ROOT/verify/train0_AssocOnly
    [ -f "$T/training_receipt.json" ] || env OMP_NUM_THREADS=$TRAIN_THREADS MKL_NUM_THREADS=$TRAIN_THREADS $PY ops/vsmt/ruling89_train.py \
      --source "$RUN_ROOT:dagger_round_0:ELU-P" --arm AssocOnly --seed 7 --out-dir "$T" $REV > "$LOG_DIR/verify-train0.log" 2>&1
    $PY -c "import json,sys; a=json.load(open(sys.argv[1]))['weights_sha256']; b=json.load(open(sys.argv[2]))['weights_sha256']; print('retrained weights', 'identical' if a == b else 'DIFFER'); sys.exit(0 if a == b else 3)" \
      "$T/training_receipt.json" "$RUN_ROOT/training/round0/AssocOnly/training_receipt.json" || { DETAIL="the retrained round-0 AssocOnly head differs"; return 1; }
  fi
  M verify --run-root "$RUN_ROOT" --export-dir "$EXPORT_DIR" --tag "$TAG" || { DETAIL="verify found problems (vsmt_lean_s2_06_verify_$TAG.json)"; return 1; }
  DETAIL="every recorded digest checked; manifest vsmt_lean_s2_06_manifest_$TAG.json"
}

# ---------------------------------------------------------------- driver
run_one() {  # stage: 0 done, 10 hold, 11 stopped, anything else failed
  local STAGE=$1 STARTED RC
  STARTED=$(date -u +%Y-%m-%dT%H:%M:%SZ); DETAIL=""
  echo "[$(date)] stage $STAGE: start at $SHORT"
  "stage_${STAGE//-/_}"
  RC=$?
  case $RC in
    0) M mark --run-root "$RUN_ROOT" --stage "$STAGE" --status done --exit 0 --started "$STARTED" --detail "$DETAIL" $ACCEPT_FLAG;;
    10) M mark --run-root "$RUN_ROOT" --stage "$STAGE" --status hold --exit 10 --started "$STARTED" --detail "$DETAIL" $ACCEPT_FLAG; finish "hold:$STAGE";;
    11) M mark --run-root "$RUN_ROOT" --stage "$STAGE" --status stopped --exit 11 --started "$STARTED" --detail "$DETAIL" $ACCEPT_FLAG; finish "stopped:$STAGE";;
    *) M mark --run-root "$RUN_ROOT" --stage "$STAGE" --status failed --exit "$RC" --started "$STARTED" --detail "$DETAIL" $ACCEPT_FLAG; finish "failed:$STAGE";;
  esac
}

if [ -n "$(git status --porcelain)" ]; then echo "worktree not clean; refusing"; exit 2; fi
if ps -eo args | grep -v grep | grep -E "^sleep [0-9]+$|/usr/bin/shutdown" > /dev/null; then echo "a pending sleep/shutdown exists; refusing"; exit 2; fi
echo "[$(date)] S2-06 at $SHORT (run tag $TAG): run root $RUN_ROOT, cpu.max $(cat /sys/fs/cgroup/cpu.max 2>/dev/null), memory.max $(cat /sys/fs/cgroup/memory.max 2>/dev/null)"
if [ "$COMMAND" = "all" ]; then
  for STAGE in $STAGES; do
    STATE=$(M stage-state --run-root "$RUN_ROOT" --stage "$STAGE" $ACCEPT_FLAG)
    case $? in
      0) echo "[$(date)] stage $STAGE: kept ($STATE)";;
      1) run_one "$STAGE";;
      *) DETAIL="$STATE"; echo "[$(date)] stage $STAGE: refused ($STATE)"; finish "blocked:$STAGE";;
    esac
  done
  finish done
fi
for STAGE in $STAGES; do  # one stage: everything before it must be done at this commit (or carried over by the rule above)
  [ "$STAGE" = "$COMMAND" ] && break
  STATE=$(M stage-state --run-root "$RUN_ROOT" --stage "$STAGE" $ACCEPT_FLAG) || { echo "stage $STAGE is not done ($STATE); refusing $COMMAND"; exit 2; }
done
run_one "$COMMAND"
finish "$COMMAND"
