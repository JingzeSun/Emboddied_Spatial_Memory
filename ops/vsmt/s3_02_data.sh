#!/bin/bash
# S3-02: the formal data, one command (ruling 103, user 2026-10-02: 「待裁 103 全按推荐」).
#
# Usage (server, from a clean detached worktree of the reviewed commit; 4 cards, data disk with the projected space free):
#   bash ops/vsmt/s3_02_data.sh all        every stage in order; a finished stage is kept, a hold or a stop ends the run
#   bash ops/vsmt/s3_02_data.sh <stage>    one stage; every earlier stage must be done
#   bash ops/vsmt/s3_02_data.sh status     the stage markers
#   long runs in the background:  nohup bash ops/vsmt/s3_02_data.sh all > <log> 2>&1 &
#   (launch and return: the driver refuses to start while a 'sleep N' or a shutdown is pending, since an earlier
#    driver's fallback power-off may be armed; kill that driver and its sleep first)
#
# Stages (each writes a marker under $RUN_ROOT/stages; exports go to $EXPORT_DIR as vsmt_lean_s3_02_*_<tag>.json):
#   check           full test suite; every input pinned in $RUN_ROOT/inputs.json: the S3 manifests, the ProcTHOR source at its
#                   registered digest, the private salt of every S1 generation, the frontend assets, both ReID heads at their S0-03
#                   digests (used from S3-03 on), the simulator interpreter, the cards, the cgroup quota and memory, and free disk
#                   against the projection from the committed S1 reports minus what this run's roots already hold (the check is
#                   redone at every new commit, e.g. after the hold, when the raw episodes are already written; MIN_FREE_GIB
#                   overrides it, recorded)
#   measure         the generator's s3-measure: four train houses at four workers -> the S1-01 occupancy (worker and container peaks)
#   generate        free disk again with the measured bytes per house, minus what is already written (a resume); the generator's
#                   s3 over train, validation and test in one
#                   pool, workers by the S1-01 rule (headroom 0.2) with the simulator limit SIM_LIMIT assumed (recorded as an
#                   extrapolation; 16 = the confirmation generation, 2339baa); the test root is pending-sealed from its creation;
#                   then ruling 36 on train: fewer than 120 moves or 60 source-first -> STOP (marker 'stopped') for a scale ruling
#   hold            ruling 103-3: every generator commit of the raw receipts must be in the S1-03 pose registry
#                   (correct_encoder_since_code_commits); until a commit registers it (pre-authorised; only the S1-03 contract and
#                   its two pinning tests change, as 2339baa -> 6b65cb1) the stage HOLDS; an encoder that differs STOPS
#   geometry        the S1-04 reload per split root, 8 simulator workers (ruling 103-4)
#   instance-cache  the S1-03 cache, --mask-source simulator_instance_masks, per split root, two threads per worker, workers from the
#                   cgroup quota and memory, every card, largest episode first
#   sam2-measure    ruling 84-4: SAM2 trials with 1..4 workers on one card (the largest train episodes, 60 frames each) -> the best
#                   workers per card and the projected hours, printed for the report; the run continues
#   sam2-cache      the S1-03 cache, --mask-source sam2 (D-215 with ruling 43; no mask-layer revision, 102-7), per split root,
#                   the best workers per card on every card, largest episode first
#   export          train and validation reports per house, test as counts only, the measurement, plans, workers, the move check,
#                   the registration record, the SAM2 measurement, and the test seal (ruling 103-1)
#   verify          every split consistent across raw, geometry and both caches, the seal recomputed, the four measured houses
#                   compared with their train copies (recorded), every export digest; the final run manifest
#
# Roots ($AUTODL = /root/autodl-tmp; <tag> = the commit of the first check, kept in $RUN_ROOT/run_tag):
#   raw        $AUTODL/vsmt_outputs/s3-02-<tag>/{measure,train,validation,test}
#   geometry   $AUTODL/vsmt_private/s3-02-geometry-<tag>/{train,validation,test}
#   caches     $AUTODL/vsmt_caches/s3-02-{instance,sam2}-<tag>/{train,validation,test}
#   The four test roots carry TEST_SEALED.json; every data-reading entry refuses them until S3-05 (ruling 103-1).
#
# Environment (optional): RUN_ROOT (default $AUTODL/vsmt_private/s3-02-run), SIM_LIMIT (16), GEN_WORKERS (cap on the derived
#   generator workers), INSTANCE_WORKERS / SAM2_WORKERS (overrides, recorded), MIN_FREE_GIB, FALLBACK_SHUTDOWN_SECONDS (0 = off;
#   > 0: after the status is written, power off that long later unless another vsmt job runs), ACCEPT_CODE_CHANGE=1 (keep stages
#   finished at an earlier commit although code changed since; recorded in the marker), PY, SIM_PY, AUTODL and the input paths below.
# Resume: run 'all' again; finished stages are kept, a stage whose code changed since it ran is refused (only the registration and
#   documents may change); the generator resumes house by house (an interrupted house is failed, never rerun), the caches episode by
#   episode, a finished split is skipped.
set -u
WORKTREE=$(cd "$(dirname "$0")/../.." && pwd)
cd "$WORKTREE" || exit 2
HEAD_COMMIT=$(git rev-parse HEAD)
SHORT=$(git rev-parse --short HEAD)
PY=${PY:-/root/miniconda3/bin/python3.12}
AUTODL=${AUTODL:-/root/autodl-tmp}
SIM_PY=${SIM_PY:-$AUTODL/vsmt-envs/simulator-py39/bin/python}
SOURCE=${SOURCE:-$AUTODL/vsmt_sources/procthor-10k-0.1.2/train.jsonl.gz}
SALT_FILE=${SALT_FILE:-$AUTODL/vsmt_private/null_window_salt.txt}
ASSETS_JSON=${ASSETS_JSON:-$AUTODL/vsmt_private/s103_assets.json}
SAM2_REID=${SAM2_REID:-$AUTODL/vsmt_private/exports/reid_head_vitb14_154776d.json}
INSTANCE_REID=${INSTANCE_REID:-$AUTODL/vsmt_private/lean-s1-04-diagnostics-oracle-caa50c7/reid_head_vitb14.json}
EXPORT_DIR=${EXPORT_DIR:-$AUTODL/vsmt_outputs/exports}
RUN_ROOT=${RUN_ROOT:-$AUTODL/vsmt_private/s3-02-run}
SIM_LIMIT=${SIM_LIMIT:-16}
GEN_WORKERS=${GEN_WORKERS:-}
INSTANCE_WORKERS=${INSTANCE_WORKERS:-}
SAM2_WORKERS=${SAM2_WORKERS:-}
MIN_FREE_GIB=${MIN_FREE_GIB:-}
FALLBACK_SHUTDOWN_SECONDS=${FALLBACK_SHUTDOWN_SECONDS:-0}
ACCEPT_CODE_CHANGE=${ACCEPT_CODE_CHANGE:-0}
STAGES="check measure generate hold geometry instance-cache sam2-measure sam2-cache export verify"
SPLITS="train validation test"
SAM2_TRIAL_FRAMES=60
COMMAND=${1:-}
case " $STAGES all status " in *" $COMMAND "*) ;; *) echo "usage: bash ops/vsmt/s3_02_data.sh all|status|<stage> (stages: $STAGES)"; exit 2;; esac
if [ "$COMMAND" = "status" ]; then PYTHONPATH=src $PY ops/vsmt/s3_02_manifest.py status --run-root "$RUN_ROOT"; exit 0; fi
mkdir -p "$RUN_ROOT/stages" "$EXPORT_DIR"
[ -f "$RUN_ROOT/run_tag" ] || echo "$SHORT" > "$RUN_ROOT/run_tag"
TAG=$(cat "$RUN_ROOT/run_tag")  # the commit of the first check: every root and export of this run carries it
RAW=$AUTODL/vsmt_outputs/s3-02-$TAG
GEOMETRY=$AUTODL/vsmt_private/s3-02-geometry-$TAG
INSTANCE_CACHE=$AUTODL/vsmt_caches/s3-02-instance-$TAG
SAM2_CACHE=$AUTODL/vsmt_caches/s3-02-sam2-$TAG
# the roots the disk projection is about (not the measure root): what they already hold is subtracted from it
RUN_ROOTS="$RAW/train,$RAW/validation,$RAW/test,$GEOMETRY,$INSTANCE_CACHE,$SAM2_CACHE"
LOG_DIR=$AUTODL/vsmt_outputs/run_logs/s3-02-$TAG
STATUS=$EXPORT_DIR/s3_02_$TAG.status.json
mkdir -p "$LOG_DIR"
ACCEPT_FLAG=""; [ "$ACCEPT_CODE_CHANGE" = "1" ] && ACCEPT_FLAG="--accept-code-change"
MIN_FREE_FLAG=""; [ -n "$MIN_FREE_GIB" ] && MIN_FREE_FLAG="--min-free-gib $MIN_FREE_GIB"
DETAIL=""; REACHED=""
M() { PYTHONPATH=src $PY ops/vsmt/s3_02_manifest.py "$@"; }
export_name() { echo "$EXPORT_DIR/vsmt_lean_s3_02_$1_$TAG.json"; }
cache_threads() { env OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 "$@"; }

finish() {
  REACHED=$1
  $PY -c "import json, sys, time; json.dump({'tag': '$TAG', 'commit': '$HEAD_COMMIT', 'stage_reached': sys.argv[1], 'detail': sys.argv[2],
    'finished_cst': time.strftime('%Y-%m-%d %H:%M:%S'), 'run_root': '$RUN_ROOT', 'log_dir': '$LOG_DIR',
    'roots': {'raw': '$RAW', 'geometry': '$GEOMETRY', 'instance_cache': '$INSTANCE_CACHE', 'sam2_cache': '$SAM2_CACHE'},
    'workers': json.load(open('$RUN_ROOT/workers.json')) if __import__('os').path.exists('$RUN_ROOT/workers.json') else None,
    'fallback_shutdown_seconds': $FALLBACK_SHUTDOWN_SECONDS}, open('$STATUS', 'w'), indent=1)" "$REACHED" "$DETAIL"
  M status --run-root "$RUN_ROOT"
  echo "[$(date)] status written ($REACHED) -> $STATUS"
  if [ "$FALLBACK_SHUTDOWN_SECONDS" -gt 0 ] 2>/dev/null; then
    echo "[$(date)] fallback armed: power off in $FALLBACK_SHUTDOWN_SECONDS s unless another vsmt job runs"
    sleep "$FALLBACK_SHUTDOWN_SECONDS"
    if pgrep -f "lean_s1_02a_pilot.py|lean_s1_03_cache.py|lean_s1_04_object_geometry.py|lean_s2_05_node_audit.py run|ruling89_train.py" > /dev/null; then
      echo "[$(date)] another vsmt job is running; no fallback shutdown"
    else
      echo "[$(date)] fallback shutdown (AutoDL)"; /usr/bin/shutdown
    fi
  fi
  exit 0
}

# ---------------------------------------------------------------- stages
stage_check() {
  PYTHONPATH=src $PY -m unittest discover -s tests -t tests -p "test_*.py" > "$LOG_DIR/suite-$SHORT.log" 2>&1
  local RC=$?
  echo "[$(date)] suite exit $RC: $(grep -E '^Ran |^OK|FAILED' "$LOG_DIR/suite-$SHORT.log" | tail -2 | tr '\n' ' ')"
  [ "$RC" = "0" ] || { DETAIL="full test suite failed ($LOG_DIR/suite-$SHORT.log)"; return 1; }
  M check --run-root "$RUN_ROOT" --repo-root "$WORKTREE" --autodl-root "$AUTODL" --source "$SOURCE" --salt-file "$SALT_FILE" \
    --assets-json "$ASSETS_JSON" --sam2-reid "$SAM2_REID" --instance-reid "$INSTANCE_REID" --sim-python "$SIM_PY" \
    --run-roots "$RUN_ROOTS" $MIN_FREE_FLAG
  RC=$?
  cp "$RUN_ROOT/inputs.json" "$RUN_ROOT/inputs-$SHORT.json"
  [ "$RC" = "0" ] || { DETAIL="input check failed: problems in $RUN_ROOT/inputs.json"; return 1; }
  DETAIL="suite and inputs ok at $SHORT"
}

stage_measure() {
  $SIM_PY ops/vsmt/lean_s1_02a_pilot.py --stage s3-measure --output-root "$RAW" --source "$SOURCE" --private-salt-file "$SALT_FILE" \
    > "$LOG_DIR/measure.log" 2>&1
  local RC=$?
  tail -3 "$LOG_DIR/measure.log"
  [ "$RC" = "0" ] || { DETAIL="measurement failed (exit $RC, $LOG_DIR/measure.log)"; return 1; }
  DETAIL="occupancy measured on four train houses ($RAW/measure/occupancy_receipt.json)"
}

stage_generate() {
  M disk --run-root "$RUN_ROOT" --repo-root "$WORKTREE" --autodl-root "$AUTODL" --measure-root "$RAW/measure" \
    --run-roots "$RUN_ROOTS" $MIN_FREE_FLAG \
    || { DETAIL="not enough free disk for the projected outputs ($RUN_ROOT/disk.json): expand the data disk, then run 'all' again"; return 1; }
  local RESUME="" RC
  [ -f "$RAW/plan.json" ] && RESUME="--resume"
  echo "[$(date)] generating train, validation and test ($RESUME); simulator limit $SIM_LIMIT assumed"
  $SIM_PY ops/vsmt/lean_s1_02a_pilot.py --stage s3 --output-root "$RAW" --source "$SOURCE" --private-salt-file "$SALT_FILE" \
    --simulator-concurrency-limit "$SIM_LIMIT" ${GEN_WORKERS:+--workers "$GEN_WORKERS"} $RESUME > "$LOG_DIR/generate.log" 2>&1
  RC=$?
  grep -E '^\[s3\]|^resume' "$LOG_DIR/generate.log" | tail -2
  [ "$RC" = "0" ] || { DETAIL="generation failed (exit $RC, $LOG_DIR/generate.log); run 'all' again to resume"; return 1; }
  M movecheck --run-root "$RUN_ROOT" --raw-root "$RAW"
  case $? in
    0) DETAIL="450 houses attempted; ruling 36 met on train ($RUN_ROOT/movecheck.json)";;
    4) DETAIL="ruling 36: train below 120 moves or 60 source-first ($RUN_ROOT/movecheck.json): stop for a scale ruling, nothing relaxed"; return 11;;
    *) DETAIL="move check could not read the train receipt"; return 1;;
  esac
}

stage_hold() {
  M hold --run-root "$RUN_ROOT" --repo-root "$WORKTREE" --raw-root "$RAW"
  case $? in
    0) DETAIL="every generator commit is registered in the S1-03 pose registry";;
    10) DETAIL="hold: register the generator commit(s) of $RUN_ROOT/hold.json in S1-03 correct_encoder_since_code_commits (ruling 103-3, pre-authorised), commit, then run 'all' at that commit"; return 10;;
    11) DETAIL="a generator commit's camera_pose encoder differs from the registered one ($RUN_ROOT/hold.json): stop"; return 11;;
    *) DETAIL="registration check failed"; return 1;;
  esac
}

stage_geometry() {
  local SPLIT
  for SPLIT in $SPLITS; do
    if M geometry-ok --root "$GEOMETRY/$SPLIT" --raw-root "$RAW/$SPLIT" > /dev/null 2>&1; then
      echo "[$(date)] geometry $SPLIT: kept"
    else
      $SIM_PY ops/vsmt/lean_s1_04_object_geometry.py --episode-roots "$RAW/$SPLIT" --source "$SOURCE" --output-root "$GEOMETRY/$SPLIT" \
        --workers 8 --worker-basis "ruling 103-4: the measured S1-04 setting, 8 simulator workers" > "$LOG_DIR/geometry-$SPLIT.log" 2>&1
      M geometry-ok --root "$GEOMETRY/$SPLIT" --raw-root "$RAW/$SPLIT" || { DETAIL="geometry $SPLIT incomplete ($LOG_DIR/geometry-$SPLIT.log)"; return 1; }
    fi
    [ "$SPLIT" = "test" ] && M seal-pending --root "$GEOMETRY/test" --kind geometry
  done
  DETAIL="geometry tables for every split"
}

run_cache() {  # mask-source cache-root workers gpus seal-kind worker-basis
  local SOURCE_NAME=$1 BASE=$2 N=$3 GPUS=$4 KIND=$5 BASIS=$6 SPLIT RESUME
  for SPLIT in $SPLITS; do
    if M cache-ok --root "$BASE/$SPLIT" --raw-root "$RAW/$SPLIT" --mask-source "$SOURCE_NAME" --quiet > /dev/null 2>&1; then
      echo "[$(date)] $SOURCE_NAME cache $SPLIT: kept"
    else
      RESUME=""; [ -d "$BASE/$SPLIT" ] && [ -n "$(ls -A "$BASE/$SPLIT" 2>/dev/null)" ] && RESUME="--resume"
      echo "[$(date)] $SOURCE_NAME cache $SPLIT: $N workers on cards $GPUS $RESUME"
      cache_threads $PY ops/vsmt/lean_s1_03_cache.py --episode-roots "$RAW/$SPLIT" --output-root "$BASE/$SPLIT" --assets-json "$ASSETS_JSON" \
        --workers "$N" --worker-basis "$BASIS" --mask-source "$SOURCE_NAME" \
        --gpus "$GPUS" --largest-first $RESUME > "$LOG_DIR/$KIND-$SPLIT.log" 2>&1
      tail -1 "$LOG_DIR/$KIND-$SPLIT.log"
      M cache-ok --root "$BASE/$SPLIT" --raw-root "$RAW/$SPLIT" --mask-source "$SOURCE_NAME" \
        || { DETAIL="$SOURCE_NAME cache $SPLIT incomplete or failed by something other than the data ($LOG_DIR/$KIND-$SPLIT.log)"; return 1; }
    fi
    [ "$SPLIT" = "test" ] && M seal-pending --root "$BASE/test" --kind "$KIND"
  done
  return 0
}

stage_instance_cache() {
  local N GPUS
  read -r N GPUS < <(M workers --run-root "$RUN_ROOT" ${INSTANCE_WORKERS:+--workers "$INSTANCE_WORKERS"})
  echo "[$(date)] instance cache: $N workers x 2 threads on cards $GPUS ($RUN_ROOT/workers.json)"
  run_cache simulator_instance_masks "$INSTANCE_CACHE" "$N" "$GPUS" instance_cache \
    "S3-02: two threads per worker, workers from the cgroup quota and memory with the 8ebbd05 peaks ($RUN_ROOT/workers.json)" || return 1
  DETAIL="instance-segmentation cache for every split"
}

stage_sam2_measure() {
  local K TRIAL TRIALS=() GPUS RESUME
  GPUS=$($PY -c "import json; print(','.join(json.load(open('$RUN_ROOT/workers.json'))['instance_cache']['gpus']))")
  for K in 1 2 3 4; do
    TRIAL=$AUTODL/vsmt_caches/s3-02-sam2-measure-k$K-$TAG-trial
    TRIALS+=(--trial "$K=$TRIAL")
    [ -f "$TRIAL/trial_receipt.json" ] && continue
    RESUME=""; [ -d "$TRIAL" ] && RESUME="--resume"
    cache_threads $PY ops/vsmt/lean_s1_03_cache.py --episode-roots "$RAW/train" --output-root "$TRIAL" --assets-json "$ASSETS_JSON" \
      --workers "$K" --worker-basis "ruling 84-4: SAM2 throughput with $K workers on one card" --mask-source sam2 --gpus 0 --largest-first \
      --trial-frame-limit "$SAM2_TRIAL_FRAMES" --trial-episodes "$K" $RESUME > "$LOG_DIR/sam2-measure-k$K.log" 2>&1 \
      || { DETAIL="SAM2 trial with $K workers failed ($LOG_DIR/sam2-measure-k$K.log)"; return 1; }
  done
  local OUT
  OUT=$(M sam2-measure --run-root "$RUN_ROOT" --raw-root "$RAW" --gpus "$GPUS" "${TRIALS[@]}") || { DETAIL="SAM2 measurement refused"; return 1; }
  read -r TOTAL PER_CARD HOURS <<< "$OUT"
  echo "[$(date)] SAM2: $PER_CARD workers per card, $TOTAL in all, about $HOURS h for every split ($RUN_ROOT/sam2_measure.json)"
  DETAIL="SAM2 $PER_CARD workers per card, projected $HOURS h"
}

stage_sam2_cache() {
  local N GPUS
  N=${SAM2_WORKERS:-$($PY -c "import json; print(json.load(open('$RUN_ROOT/sam2_measure.json'))['workers'])")}
  GPUS=$($PY -c "import json; print(','.join(json.load(open('$RUN_ROOT/sam2_measure.json'))['gpus']))")
  run_cache sam2 "$SAM2_CACHE" "$N" "$GPUS" sam2_cache \
    "S3-02: the best SAM2 workers per card from the one-card trials, on every card ($RUN_ROOT/sam2_measure.json)${SAM2_WORKERS:+; SAM2_WORKERS=$SAM2_WORKERS set by the operator}" || return 1
  DETAIL="SAM2 cache for every split"
}

stage_export() {
  local SPLIT BAD=0 F
  for SPLIT in train validation; do
    $PY ops/vsmt/lean_s1_02b_export.py --output-root "$RAW/$SPLIT" --stage-receipt s3_receipt.json --out "$(export_name raw_$SPLIT)" \
      > "$LOG_DIR/export-raw-$SPLIT.log" 2>&1 || BAD=$((BAD + 1))
    cp "$GEOMETRY/$SPLIT/s1_04_geometry_receipt.json" "$(export_name geometry_$SPLIT)" || BAD=$((BAD + 1))
    $PY ops/vsmt/lean_s1_03_export.py --cache-root "$INSTANCE_CACHE/$SPLIT" --out "$(export_name instance_cache_$SPLIT)" \
      > "$LOG_DIR/export-instance-$SPLIT.log" 2>&1 || BAD=$((BAD + 1))
    $PY ops/vsmt/lean_s1_03_export.py --cache-root "$SAM2_CACHE/$SPLIT" --out "$(export_name sam2_cache_$SPLIT)" \
      > "$LOG_DIR/export-sam2-$SPLIT.log" 2>&1 || BAD=$((BAD + 1))
  done
  M test-summary --raw "$RAW/test" --geometry "$GEOMETRY/test" --instance-cache "$INSTANCE_CACHE/test" --sam2-cache "$SAM2_CACHE/test" \
    --out "$(export_name test_summary)" || BAD=$((BAD + 1))
  M seal --repo-root "$WORKTREE" --raw "$RAW/test" --geometry "$GEOMETRY/test" --instance-cache "$INSTANCE_CACHE/test" \
    --sam2-cache "$SAM2_CACHE/test" --tag "$TAG" --out "$RUN_ROOT/test_seal.json" && cp "$RUN_ROOT/test_seal.json" "$(export_name test_seal)" || BAD=$((BAD + 1))
  cp "$RAW/measure/measure_receipt.json" "$(export_name measure)" || BAD=$((BAD + 1))
  $PY -c "import glob, json, os, sys; root = sys.argv[1]; json.dump({os.path.basename(p): json.load(open(p)) for p in sorted(glob.glob(root + '/plan*.json'))},
    open(sys.argv[2], 'w'), indent=1)" "$RAW" "$(export_name generate_plans)" || BAD=$((BAD + 1))
  for F in inputs workers disk movecheck hold sam2_measure; do
    cp "$RUN_ROOT/$F.json" "$(export_name "$F")" || BAD=$((BAD + 1))
  done
  [ "$BAD" = "0" ] || { DETAIL="$BAD exports failed"; return 1; }
  DETAIL="reports exported; test sealed ($RUN_ROOT/test_seal.json)"
}

stage_verify() {
  M verify --run-root "$RUN_ROOT" --repo-root "$WORKTREE" --export-dir "$EXPORT_DIR" --tag "$TAG" --raw "$RAW" --geometry "$GEOMETRY" \
    --instance-cache "$INSTANCE_CACHE" --sam2-cache "$SAM2_CACHE" || { DETAIL="verify found problems ($(export_name verify))"; return 1; }
  DETAIL="every split consistent, the test seal intact; manifest $(export_name manifest)"
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
echo "[$(date)] S3-02 at $SHORT (run tag $TAG): run root $RUN_ROOT, cpu.max $(cat /sys/fs/cgroup/cpu.max 2>/dev/null), memory.max $(cat /sys/fs/cgroup/memory.max 2>/dev/null)"
if [ "$COMMAND" = "all" ]; then
  for STAGE in $STAGES; do
    STATE=$(M stage-state --run-root "$RUN_ROOT" --repo-root "$WORKTREE" --stage "$STAGE" $ACCEPT_FLAG)
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
  STATE=$(M stage-state --run-root "$RUN_ROOT" --repo-root "$WORKTREE" --stage "$STAGE" $ACCEPT_FLAG) || { echo "stage $STAGE is not done ($STATE); refusing $COMMAND"; exit 2; }
done
run_one "$COMMAND"
finish "$COMMAND"
