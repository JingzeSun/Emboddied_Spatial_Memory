#!/bin/bash
# S3-02 speed bench on one RTX 5090 (user 2026-10-03: 「1 卡 5090 测速，写测速脚本，测 ①②③④⑤」). Read-only on the development
# data: nothing here is S3 data, a formal stage or a method change; every output goes under $BENCH_ROOT/<tag>.
#
# Usage (server, from a clean detached worktree of the pushed commit):
#   bash ops/vsmt/s3_02_bench.sh all        every stage in order; a stage whose export exists is kept; a failed stage is recorded
#                                           and the next one runs (only a failed check stops the run)
#   bash ops/vsmt/s3_02_bench.sh <stage>    one stage
#   bash ops/vsmt/s3_02_bench.sh status     which exports exist
#   long runs in the background:  nohup bash ops/vsmt/s3_02_bench.sh all > <log> 2>&1 &
#
# Stages (exports: $EXPORT_DIR/vsmt_lean_s3_02_bench_<name>_<tag>.json):
#   check          full test suite on this machine (recorded, not a gate); the card, driver, torch on the card, cgroup quota and
#                  memory, free disk; every input present; no input root inside a sealed S3 test root
#   compat         (5) the generator's s3-measure on this machine: four S3 train houses at four workers into the bench root (not S3
#                  data); did Unity / CloudRendering run on this card, and the per-worker CPU and memory -> the S1-01 bounds at one,
#                  two and four cards of this host type
#   sam2-scaling   (1) SAM2 cache trials with 1, 2, 3, 4 workers on card 0, each over the same $SCALING_EPISODES largest development
#                  episodes x the first $SCALING_FRAMES frames; throughput = frames completed / wall clock; failures listed; the
#                  episode seals compared across the four trials
#   caches         (2) the two caches on the same $CACHE_EPISODES largest episodes ($INSTANCE_FRAMES / $SAM2_FRAMES frames): one after
#                  the other, then both at once (the instance workers leave the SAM2 workers two cores each); total wall clocks,
#                  each cache's throughput, resource peaks, and whether both ways write the same episode seals
#   audit-profile  (3) one closed-loop audit (TAF, and VSMT-lean with the S2-06 seed-7 heads) of the median SAM2 development episode
#                  under cProfile: time by function and by module
#   train-device   (4) the S2-06 round-0 records: memory once loaded and once prepared as tensors, then one epoch on the CPU
#                  ($TRAIN_THREADS threads) and one on the GPU, timed
#   collect        every bench export with its digest
#
# Environment (optional): PY, SIM_PY, AUTODL, BENCH_ROOT, EXPORT_DIR, the input paths below, SCALING_EPISODES (12), SCALING_FRAMES
#   (60), CACHE_EPISODES (12), INSTANCE_FRAMES (600), SAM2_FRAMES (120), SAM2_WORKERS (the caches stage's SAM2 workers; default the
#   best of sam2-scaling, else 2), TRAIN_THREADS (4).
set -u
WORKTREE=$(cd "$(dirname "$0")/../.." && pwd)
cd "$WORKTREE" || exit 2
SHORT=$(git rev-parse --short HEAD)
PY=${PY:-/root/miniconda3/bin/python3.12}
AUTODL=${AUTODL:-/root/autodl-tmp}
SIM_PY=${SIM_PY:-$AUTODL/vsmt-envs/simulator-py39/bin/python}
OUTPUTS=$AUTODL/vsmt_outputs
EXPORT_DIR=${EXPORT_DIR:-$OUTPUTS/exports}
EPISODE_ROOTS=${EPISODE_ROOTS:-$OUTPUTS/lean-s1-02a-5f9aa71,$OUTPUTS/lean-s1-02b-5f9aa71}
SAM2_CACHE=${SAM2_CACHE:-$AUTODL/vsmt_caches/lean-s1-03-154776d}
INSTANCE_CACHE=${INSTANCE_CACHE:-$AUTODL/vsmt_caches/lean-s1-03-oracle-8ebbd05}
GEOMETRY_ROOT=${GEOMETRY_ROOT:-$AUTODL/vsmt_private/lean-s1-04-geometry-154776d}
ASSETS_JSON=${ASSETS_JSON:-$AUTODL/vsmt_private/s103_assets.json}
SAM2_REID=${SAM2_REID:-$AUTODL/vsmt_private/exports/reid_head_vitb14_154776d.json}
INSTANCE_REID=${INSTANCE_REID:-$AUTODL/vsmt_private/lean-s1-04-diagnostics-oracle-caa50c7/reid_head_vitb14.json}
SOURCE=${SOURCE:-$AUTODL/vsmt_sources/procthor-10k-0.1.2/train.jsonl.gz}
SALT_FILE=${SALT_FILE:-$AUTODL/vsmt_private/null_window_salt.txt}
S2_06_ROOT=${S2_06_ROOT:-$AUTODL/vsmt_private/s2-06-sam2}
HEADS=${HEADS:-$S2_06_ROOT/training/round1/VSMT-lean/A7/weights_grouped.json}
RECORDS=${RECORDS:-$S2_06_ROOT:dagger_round_0:ELU-P}
BENCH_ROOT=${BENCH_ROOT:-$AUTODL/vsmt_bench}
SCALING_EPISODES=${SCALING_EPISODES:-12}
SCALING_FRAMES=${SCALING_FRAMES:-60}
CACHE_EPISODES=${CACHE_EPISODES:-12}
INSTANCE_FRAMES=${INSTANCE_FRAMES:-600}
SAM2_FRAMES=${SAM2_FRAMES:-120}
SAM2_WORKERS=${SAM2_WORKERS:-}
TRAIN_THREADS=${TRAIN_THREADS:-4}
DESCRIPTOR=reid_projection:vitb14
STAGES="check compat sam2-scaling caches audit-profile train-device collect"
COMMAND=${1:-}
case " $STAGES all status " in *" $COMMAND "*) ;; *) echo "usage: bash ops/vsmt/s3_02_bench.sh all|status|<stage> (stages: $STAGES)"; exit 2;; esac
mkdir -p "$BENCH_ROOT" "$EXPORT_DIR"
[ -f "$BENCH_ROOT/run_tag" ] || echo "$SHORT" > "$BENCH_ROOT/run_tag"
TAG=$(cat "$BENCH_ROOT/run_tag")
OUT=$BENCH_ROOT/$TAG
LOG_DIR=$OUT/logs
mkdir -p "$LOG_DIR"
H() { PYTHONPATH=src $PY ops/vsmt/s3_02_bench.py "$@"; }
MEASURE() { local TO=$1; shift; PYTHONPATH=src $PY ops/vsmt/s2_06_manifest.py run-measured --out "$TO" -- "$@"; }
export_name() { echo "$EXPORT_DIR/vsmt_lean_s3_02_bench_$1_$TAG.json"; }
aside() { [ -e "$1" ] && mv "$1" "$1.partial-$(date +%Y%m%dT%H%M%S)"; return 0; }  # an unfinished run of the bench's own, kept beside
quota() { $PY -c "
import os, pathlib
try:
    q = pathlib.Path('/sys/fs/cgroup/cpu.max').read_text().split()
    print(int(int(q[0]) / int(q[1])) if q[0] != 'max' else os.cpu_count())
except OSError:
    print(os.cpu_count())"; }
start_sampler() { PYTHONPATH=src $PY ops/vsmt/s3_02_bench.py sampler --out "$1" --interval 2 > /dev/null 2>&1 & SAMPLER=$!; }
stop_sampler() { kill "$SAMPLER" 2> /dev/null; wait "$SAMPLER" 2> /dev/null; return 0; }
# one trial-mode cache run on card 0, largest development episodes first, two threads per worker as in S3-02; append
#   --output-root R --mask-source M --workers N --trial-episodes E --trial-frame-limit F --worker-basis B
CACHE=(env OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 "$PY" ops/vsmt/lean_s1_03_cache.py
       --episode-roots "$EPISODE_ROOTS" --assets-json "$ASSETS_JSON" --gpus 0 --largest-first)

stage_check() {
  PYTHONPATH=src $PY -m unittest discover -s tests -t tests -p "test_*.py" > "$LOG_DIR/suite.log" 2>&1
  local RC=$? SUMMARY
  SUMMARY=$(grep -E '^Ran |^OK|^FAILED' "$LOG_DIR/suite.log" | tail -2 | tr '\n' ' ')
  echo "[$(date)] suite exit $RC: $SUMMARY"
  H check --out "$(export_name check)" --repo-root "$WORKTREE" --autodl-root "$AUTODL" --episode-roots "$EPISODE_ROOTS" \
    --sam2-cache "$SAM2_CACHE" --instance-cache "$INSTANCE_CACHE" --geometry-root "$GEOMETRY_ROOT" --assets-json "$ASSETS_JSON" \
    --sam2-reid "$SAM2_REID" --instance-reid "$INSTANCE_REID" --source "$SOURCE" --salt-file "$SALT_FILE" --sim-python "$SIM_PY" \
    --heads "$HEADS" --record-source "$RECORDS" --suite-exit "$RC" --suite-summary "$SUMMARY"
}

stage_compat() {  # (5)
  local ROOT=$OUT/compat
  if [ ! -f "$ROOT/measure/occupancy_receipt.json" ]; then
    aside "$ROOT"
    MEASURE "$OUT/compat_measured.json" $SIM_PY ops/vsmt/lean_s1_02a_pilot.py --stage s3-measure --output-root "$ROOT" --source "$SOURCE" \
      --private-salt-file "$SALT_FILE" > "$LOG_DIR/compat.log" 2>&1
  fi
  H compat --measure-root "$ROOT/measure" --measured "$OUT/compat_measured.json" --out "$(export_name compat)"
}

stage_sam2_scaling() {  # (1)
  local K T TRIALS=()
  for K in 1 2 3 4; do
    T=$OUT/sam2-k$K
    TRIALS+=(--trial "$K=$T")
    [ -f "$T/trial_receipt.json" ] && continue
    aside "$T"  # a cut trial is never resumed: its wall clock would be that of the rest
    MEASURE "$OUT/sam2_k${K}_measured.json" "${CACHE[@]}" --output-root "$T" --mask-source sam2 --workers "$K" \
      --trial-episodes "$SCALING_EPISODES" --trial-frame-limit "$SCALING_FRAMES" \
      --worker-basis "S3-02 bench (1): $K SAM2 workers on one card, the same work in every trial" > "$LOG_DIR/sam2-k$K.log" 2>&1
    echo "[$(date)] SAM2 trial with $K workers: exit $?"
  done
  H scaling "${TRIALS[@]}" --out "$(export_name sam2_scaling)"
}

stage_caches() {  # (2)
  local Q K INSTANCE_ALONE INSTANCE_TOGETHER T0 SEQ PAR P1 P2 ROOT=$OUT/caches
  Q=$(quota)
  K=${SAM2_WORKERS:-$($PY -c "import json, sys; b = json.load(open(sys.argv[1])).get('best_workers_per_card'); print(b or 2)" "$(export_name sam2_scaling)" 2>/dev/null || echo 2)}
  INSTANCE_ALONE=$(( Q / 2 )); INSTANCE_TOGETHER=$(( (Q - 2 * K) / 2 )); [ "$INSTANCE_TOGETHER" -lt 1 ] && INSTANCE_TOGETHER=1
  echo "[$(date)] caches: quota $Q, SAM2 $K workers; instance $INSTANCE_ALONE alone, $INSTANCE_TOGETHER beside SAM2"
  for T in seq-instance seq-sam2 par-instance par-sam2; do aside "$ROOT/$T"; done
  rm -f "$OUT/samples-sequential.jsonl" "$OUT/samples-parallel.jsonl"
  start_sampler "$OUT/samples-sequential.jsonl"; T0=$(date +%s)
  MEASURE "$OUT/caches_seq_instance.json" "${CACHE[@]}" --output-root "$ROOT/seq-instance" --mask-source simulator_instance_masks \
    --workers "$INSTANCE_ALONE" --trial-episodes "$CACHE_EPISODES" --trial-frame-limit "$INSTANCE_FRAMES" \
    --worker-basis "S3-02 bench (2): the instance cache alone" > "$LOG_DIR/caches-seq-instance.log" 2>&1
  MEASURE "$OUT/caches_seq_sam2.json" "${CACHE[@]}" --output-root "$ROOT/seq-sam2" --mask-source sam2 \
    --workers "$K" --trial-episodes "$CACHE_EPISODES" --trial-frame-limit "$SAM2_FRAMES" \
    --worker-basis "S3-02 bench (2): the SAM2 cache alone" > "$LOG_DIR/caches-seq-sam2.log" 2>&1
  SEQ=$(( $(date +%s) - T0 )); stop_sampler
  start_sampler "$OUT/samples-parallel.jsonl"; T0=$(date +%s)
  MEASURE "$OUT/caches_par_sam2.json" "${CACHE[@]}" --output-root "$ROOT/par-sam2" --mask-source sam2 \
    --workers "$K" --trial-episodes "$CACHE_EPISODES" --trial-frame-limit "$SAM2_FRAMES" \
    --worker-basis "S3-02 bench (2): the SAM2 cache beside the instance cache" > "$LOG_DIR/caches-par-sam2.log" 2>&1 &
  P1=$!
  MEASURE "$OUT/caches_par_instance.json" "${CACHE[@]}" --output-root "$ROOT/par-instance" --mask-source simulator_instance_masks \
    --workers "$INSTANCE_TOGETHER" --trial-episodes "$CACHE_EPISODES" --trial-frame-limit "$INSTANCE_FRAMES" \
    --worker-basis "S3-02 bench (2): the instance cache beside SAM2" > "$LOG_DIR/caches-par-instance.log" 2>&1 &
  P2=$!
  wait "$P1"; wait "$P2"
  PAR=$(( $(date +%s) - T0 )); stop_sampler
  H caches --run "seq-instance=$ROOT/seq-instance" --run "seq-sam2=$ROOT/seq-sam2" --run "par-instance=$ROOT/par-instance" \
    --run "par-sam2=$ROOT/par-sam2" --phase-wall "sequential=$SEQ" --phase-wall "parallel=$PAR" \
    --samples "sequential=$OUT/samples-sequential.jsonl" --samples "parallel=$OUT/samples-parallel.jsonl" --out "$(export_name caches)"
}

stage_audit_profile() {  # (3)
  local EP ROOT FRAMES TAF VSMT P1 P2="" DIR=$OUT/audit
  read -r EP ROOT FRAMES < <(H episodes --episode-roots "$EPISODE_ROOTS" --cache-root "$SAM2_CACHE" --pick median) \
    || { echo "no episode to profile"; return 1; }
  TAF=$(H config --pass development_table --arm TAF) || return 1
  VSMT=$(H config --pass development_table --arm VSMT-lean) || return 1
  echo "[$(date)] profiling the audits of $EP ($FRAMES frames)"
  aside "$DIR"; mkdir -p "$DIR"
  env OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=src $PY ops/vsmt/s2_06_manifest.py run-measured \
    --out "$DIR/taf_measured.json" -- $PY -m cProfile -o "$DIR/taf.prof" ops/vsmt/lean_s2_05_node_audit.py run --cache-root "$SAM2_CACHE" \
    --episode-root "$ROOT/$EP" --geometry-root "$GEOMETRY_ROOT" --episode-id "$EP" --arm TAF --config "$TAF" --descriptor "$DESCRIPTOR" \
    --weights "$SAM2_REID" --mask-source sam2 --output-root "$DIR/taf" --device cpu > "$LOG_DIR/audit-taf.log" 2>&1 &
  P1=$!
  if [ -f "$HEADS" ]; then
    env OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=src $PY ops/vsmt/s2_06_manifest.py run-measured \
      --out "$DIR/vsmt_measured.json" -- $PY -m cProfile -o "$DIR/vsmt.prof" ops/vsmt/lean_s2_05_node_audit.py run --cache-root "$SAM2_CACHE" \
      --episode-root "$ROOT/$EP" --geometry-root "$GEOMETRY_ROOT" --episode-id "$EP" --arm VSMT-lean --config "$VSMT" --heads "$HEADS" \
      --descriptor "$DESCRIPTOR" --weights "$SAM2_REID" --mask-source sam2 --output-root "$DIR/vsmt" --device cpu > "$LOG_DIR/audit-vsmt.log" 2>&1 &
    P2=$!
  fi
  wait "$P1"; [ -n "$P2" ] && wait "$P2"
  H profile --prof "TAF=$DIR/taf.prof,$DIR/taf_measured.json" --prof "VSMT-lean=$DIR/vsmt.prof,$DIR/vsmt_measured.json" \
    --episode "$EP" --frames "$FRAMES" --out "$(export_name audit_profile)"
}

stage_train_device() {  # (4)
  env OMP_NUM_THREADS="$TRAIN_THREADS" MKL_NUM_THREADS="$TRAIN_THREADS" PYTHONPATH=src $PY ops/vsmt/s3_02_bench.py train-bench \
    --source "$RECORDS" --arm VSMT-lean --threads "$TRAIN_THREADS" --epochs 1 --devices cpu,cuda --out "$(export_name train_device)" \
    > "$LOG_DIR/train-device.log" 2>&1
  local RC=$?
  tail -1 "$LOG_DIR/train-device.log"
  return $RC
}

stage_collect() { H collect --export-dir "$EXPORT_DIR" --tag "$TAG"; }

export_of() { case $1 in check|compat|caches|collect) echo "$1";; sam2-scaling) echo sam2_scaling;; audit-profile) echo audit_profile;;
  train-device) echo train_device;; esac; }

if [ "$COMMAND" = "status" ]; then
  for STAGE in $STAGES; do
    F=$(export_name "$(export_of "$STAGE")"); [ "$STAGE" = collect ] && F=$(export_name manifest)
    printf '%-14s %s\n' "$STAGE" "$([ -f "$F" ] && echo "exported $F" || echo -)"
  done
  exit 0
fi
if [ -n "$(git status --porcelain)" ]; then echo "worktree not clean; refusing"; exit 2; fi
echo "[$(date)] S3-02 bench at $SHORT (tag $TAG): $OUT, cpu.max $(cat /sys/fs/cgroup/cpu.max 2>/dev/null), memory.max $(cat /sys/fs/cgroup/memory.max 2>/dev/null)"
run_stage() {
  local STAGE=$1 RC
  echo "[$(date)] stage $STAGE: start"
  "stage_${STAGE//-/_}"; RC=$?
  echo "[$(date)] stage $STAGE: exit $RC"
  echo "$STAGE $RC $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$OUT/stage_exits.log"
  return $RC
}
if [ "$COMMAND" = "all" ]; then
  for STAGE in $STAGES; do
    if [ "$STAGE" != collect ] && [ "$STAGE" != check ] && [ -f "$(export_name "$(export_of "$STAGE")")" ]; then
      echo "[$(date)] stage $STAGE: kept ($(export_name "$(export_of "$STAGE")"))"; continue
    fi
    run_stage "$STAGE"
    RC=$?
    if [ "$STAGE" = check ] && [ "$RC" != 0 ]; then echo "[$(date)] check failed: see $(export_name check); stopping"; exit 1; fi
  done
  echo "[$(date)] bench done: $(export_name manifest)"
  exit 0
fi
run_stage "$COMMAND"
