#!/bin/bash
# S3-03: training and configuration selection, one command (ruling 104, user 2026-10-03:
# 「待裁 104 全按推荐；加速方案全按推荐（含 1b 不停机登记）；104-5 暂缓」).
#
# Usage (server, from a clean detached worktree of the reviewed commit; CPU only, nothing here needs a GPU):
#   bash ops/vsmt/s3_03_train_select.sh all      check -> the job pool -> exports -> verify; run it again to resume
#   bash ops/vsmt/s3_03_train_select.sh status   the pool's state (jobs by status, the stop reason)
#   long runs in the background:  nohup bash ops/vsmt/s3_03_train_select.sh all > <log> 2>&1 &
#   (the driver refuses to start while a 'sleep N' or a shutdown is pending -- an earlier driver's fallback power-off may be
#    armed -- while an S3-03 pool or job still runs, or while another driver holds the run root's lock $RUN_ROOT/.lock)
#
# Steps:
#   check   the full test suite; $RUN_ROOT/inputs.json: the S3-02 exports equal its run manifest (raw receipts, cache seals,
#           geometry receipts, counts), the four test roots carry markers sealed with the exported seal (only the marker files
#           are read), both ReID heads at their S0-03 digests, and per front end the usable train and validation episodes
#           (manifest, raw, geometry table and cache all present)
#   run     the job pool (ops/vsmt/s3_03_jobs.py; the graph is s3_03_manifest.build_jobs): per front end the calibration pass ->
#           the ELU-P fit (run-local values) -> round 0 with HeuristicLabel's labels -> the round-0 gate (G4, split nuisance probe)
#           -> round-0 training of VSMT-lean, AssocOnly, HeuristicLabel -> round 1 -> round-1 training at five seeds -> the
#           learned-arm validation audits; the rule-arm audits fill free cores from the start (ELU-P after its fit); the audit
#           and training equivalence probes run alongside and stop the run if they differ; merges, readings, determinism probe
#   export  $EXPORT_DIR/vsmt_lean_s3_03_*_<tag>.json (inputs, fits, gates, trainings, readings, jobs)
#   verify  every job ended, every gate passed, and S0-05's fitted values equal the run's (ruling 104-1 1b: until the
#           registration commit is pulled, verify reports elu_p_values_not_registered and exits 3; nothing reruns), the manifest
#
# Environment (optional): AUTODL, S3_02_TAG (3f6ef1d), EXPORT_DIR, RUN_ROOT (default $AUTODL/vsmt_private/s3-03-run),
#   INSTANCE_REID, SAM2_REID, FRONTS (instance,sam2), ADOPT_CALIBRATION_INSTANCE / ADOPT_CALIBRATION_SAM2 (an existing calibration
#   pass root of that front end, the S3 pre-fit, adopted after one of its episodes is reproduced byte for byte), MEMORY_GIB
#   ("audit=5 pass=4": defaults before the first measurement), ACCEPT_CODE_CHANGE=1 (keep jobs finished before a code change;
#   recorded), RETRY_FAILED=1 (rerun failed and gate-failed jobs after a fix or a ruling; their outputs are set aside under
#   $RUN_ROOT/failed first; never done by default), FALLBACK_SHUTDOWN_SECONDS (0 = off; > 0: after the status is written, power
#   off that long later unless another vsmt job runs), PY,
#   PROVISIONAL_INPUTS=1 (user 2026-10-04: start beside the S3-02 run on the same host before S3-02 has exported its run manifest;
#   the check reads train and validation from their roots, which must already be complete by S3-02's own rules -- so both front
#   ends' validation caches must be done -- and records what they rest on; the first full check after the export must find the
#   same episodes and digests or the run stops, and verify refuses inputs that are still provisional),
#   BUDGET_CORES (the pool's core budget instead of the cgroup quota, e.g. to leave the S3-02 SAM2 cache its cores; recorded),
#   MEMORY_FIXED_GIB ("train1=5.5 audit=2 ...": a fixed reservation per memory class instead of 1.25 x the measured peak and
#   the round-1 fallback; user 2026-10-04 on the memory-bound CPU host; scheduling only; the live cgroup guard still pauses
#   dispatch; recorded in workers.json).
# Drain (user 2026-10-04: change code or upgrade the host between training batches): touch $RUN_ROOT/DRAIN; the pool starts
#   nothing more and ends when the running jobs end, the status says 'drained' and no fallback power-off is armed; remove the
#   file before the next 'all' (the driver refuses while it exists).
# Remote hosts (user 2026-10-04: more CPU hosts beside this one; the S3 stages after S3-03 that need no GPU can use the same):
#   1. here, once: ssh-keygen -t ed25519 -N "" -f /root/.ssh/vsmt_workers_ed25519; its .pub goes into each host's
#      /root/.ssh/authorized_keys;
#   2. python ops/vsmt/remote_hosts.py setup --run-root $RUN_ROOT --name w1 --address <gateway> --port <port> [--kinds audit,train1]
#      (copies the python prefix, this worktree with its repository, the validation inputs, the ReID heads and, for trainings,
#      the round-0 records, each to the same absolute path; about 45 GB);
#   3. python ops/vsmt/remote_hosts.py admit --run-root $RUN_ROOT --name w1 --address <gateway> --port <port> [--kinds ...]
#      (versions, code and inputs byte for byte, two audits per front end rerun identical, a short training identical;
#      writes $RUN_ROOT/hosts/w1.json with its budget: its cgroup less 2 cores and 8 GiB);
#   the running pool reads $RUN_ROOT/hosts/ every 30 s: audits and trainings that do not fit here go to an admitted host (each
#   job's state names its host); "paused": true in the host file stops new jobs there; a connection failure requeues the job
#   and writes $RUN_ROOT/hosts/w1.suspended (remove it once the host is back).
# Resume: run 'all' again; finished jobs are kept (only the fit registration files and documents may change since), jobs that
#   were interrupted are set aside under $RUN_ROOT/interrupted and rerun, audits keep their finished configurations, trainings
#   continue from their last epoch-end checkpoint (bit-identical to an uninterrupted training); the adoption choice of the first
#   run is kept. Exit status: 0 when verify passed, otherwise the failing step's code (the status
#   JSON says which).
set -u
WORKTREE=$(cd "$(dirname "$0")/../.." && pwd)
cd "$WORKTREE" || exit 2
HEAD_COMMIT=$(git rev-parse HEAD)
SHORT=$(git rev-parse --short HEAD)
PY=${PY:-/root/miniconda3/bin/python3.12}
AUTODL=${AUTODL:-/root/autodl-tmp}
OUTPUTS=$AUTODL/vsmt_outputs
EXPORT_DIR=${EXPORT_DIR:-$OUTPUTS/exports}
S3_02_TAG=${S3_02_TAG:-3f6ef1d}
RUN_ROOT=${RUN_ROOT:-$AUTODL/vsmt_private/s3-03-run}
SAM2_REID=${SAM2_REID:-$AUTODL/vsmt_private/exports/reid_head_vitb14_154776d.json}
INSTANCE_REID=${INSTANCE_REID:-$AUTODL/vsmt_private/lean-s1-04-diagnostics-oracle-caa50c7/reid_head_vitb14.json}
FRONTS=${FRONTS:-instance,sam2}
FALLBACK_SHUTDOWN_SECONDS=${FALLBACK_SHUTDOWN_SECONDS:-0}
ACCEPT_CODE_CHANGE=${ACCEPT_CODE_CHANGE:-0}
# the job processes themselves (a 'status' call, an editor or a pager holding one of these files does not match)
JOB_PATTERN="s3_03_manifest.py (run|fit|gate-round0|train-threads|probe-audit|adopt-calibration|readings|probe-determinism|coverage|export|verify) |s3_03_jobs.py run-measured |lean_s2_04_evaluate_episode.py --|lean_s2_05_node_audit.py (run|merge) --|s3_03_train.py (train|probe|time) --"
COMMAND=${1:-}
case "$COMMAND" in all|status) ;; *) echo "usage: bash ops/vsmt/s3_03_train_select.sh all|status"; exit 2;; esac
M() { PYTHONPATH=src $PY ops/vsmt/s3_03_manifest.py "$@"; }
if [ "$COMMAND" = "status" ]; then M status --run-root "$RUN_ROOT"; exit 0; fi
if [ -n "$(git status --porcelain)" ]; then echo "refused: the worktree is not clean"; exit 2; fi
if ps -eo args | grep -v grep | grep -E "^sleep [0-9]+$|/usr/bin/shutdown" > /dev/null; then
  echo "refused: a fallback power-off may be armed (a sleep or a shutdown is pending); stop it first"; exit 2
fi
if pgrep -f "$JOB_PATTERN" > /dev/null; then echo "refused: an S3-03 pool or one of its jobs (or another vsmt entry) is running"; exit 2; fi
if [ -e "$RUN_ROOT/DRAIN" ]; then echo "refused: $RUN_ROOT/DRAIN exists (a drain was asked for); remove it to run again"; exit 2; fi
mkdir -p "$RUN_ROOT" "$EXPORT_DIR"
exec 9> "$RUN_ROOT/.lock"  # held by this driver and its pool for the whole run; a second driver on the same root stops here
if ! flock -n 9; then echo "refused: another driver holds $RUN_ROOT/.lock (its test suite, check or pool is running)"; exit 2; fi
[ -f "$RUN_ROOT/run_tag" ] || echo "$SHORT" > "$RUN_ROOT/run_tag"
TAG=$(cat "$RUN_ROOT/run_tag")  # the commit of the first check: every export of this run carries it
LOG_DIR=$OUTPUTS/run_logs/s3-03-$TAG
STATUS=$EXPORT_DIR/s3_03_$TAG.status.json
mkdir -p "$LOG_DIR"
DETAIL=""

finish() {  # step, exit status (0 only when verify passed)
  $PY -c "import json, os, sys, time; json.dump({'tag': '$TAG', 'commit': '$HEAD_COMMIT', 'step_reached': sys.argv[1], 'detail': sys.argv[2],
    'finished_cst': time.strftime('%Y-%m-%d %H:%M:%S'), 'run_root': '$RUN_ROOT', 'log_dir': '$LOG_DIR',
    'pool': json.load(open('$RUN_ROOT/pool.json')) if os.path.exists('$RUN_ROOT/pool.json') else None,
    'fallback_shutdown_seconds': $FALLBACK_SHUTDOWN_SECONDS}, open('$STATUS', 'w'), indent=1)" "$1" "$DETAIL"
  M status --run-root "$RUN_ROOT"
  echo "[$(date)] status written ($1: $DETAIL) -> $STATUS"
  if [ "${DRAINED:-0}" = "1" ]; then
    echo "[$(date)] drained on request: no fallback power-off"
  elif [ "$FALLBACK_SHUTDOWN_SECONDS" -gt 0 ] 2>/dev/null; then
    echo "[$(date)] fallback armed: power off in $FALLBACK_SHUTDOWN_SECONDS s unless another vsmt job runs"
    sleep "$FALLBACK_SHUTDOWN_SECONDS"
    if pgrep -f "$JOB_PATTERN|lean_s2_05_development.py|ruling89_train.py" > /dev/null; then
      echo "[$(date)] another vsmt job is running; no fallback shutdown"
    else
      echo "[$(date)] fallback shutdown (AutoDL)"; /usr/bin/shutdown
    fi
  fi
  exit "${2:-1}"
}

echo "[$(date)] S3-03 at $SHORT (run tag $TAG): full test suite -> $LOG_DIR/suite-$SHORT.log"
if ! PYTHONPATH=src $PY -m unittest discover -s tests -t tests -p "test_*.py" > "$LOG_DIR/suite-$SHORT.log" 2>&1; then
  DETAIL="the test suite failed ($LOG_DIR/suite-$SHORT.log)"; finish check 1
fi
if ! M check --run-root "$RUN_ROOT" --autodl-root "$AUTODL" --s3-02-tag "$S3_02_TAG" --export-dir "$EXPORT_DIR" \
     --instance-reid "$INSTANCE_REID" --sam2-reid "$SAM2_REID" --fronts "$FRONTS" ${PROVISIONAL_INPUTS:+--provisional}; then
  DETAIL="inputs refused ($RUN_ROOT/inputs.json)"; finish check 1
fi
cp "$RUN_ROOT/inputs.json" "$RUN_ROOT/inputs-$SHORT.json"

OPTIONS=()
[ -n "${ADOPT_CALIBRATION_INSTANCE:-}" ] && OPTIONS+=(--adopt-calibration "instance=$ADOPT_CALIBRATION_INSTANCE")
[ -n "${ADOPT_CALIBRATION_SAM2:-}" ] && OPTIONS+=(--adopt-calibration "sam2=$ADOPT_CALIBRATION_SAM2")
for ITEM in ${MEMORY_GIB:-}; do OPTIONS+=(--memory-gib "$ITEM"); done
for ITEM in ${MEMORY_FIXED_GIB:-}; do OPTIONS+=(--memory-fixed-gib "$ITEM"); done
[ "$ACCEPT_CODE_CHANGE" = "1" ] && OPTIONS+=(--accept-code-change)
[ "${RETRY_FAILED:-0}" = "1" ] && OPTIONS+=(--retry-failed)
[ -n "${BUDGET_CORES:-}" ] && OPTIONS+=(--budget-cores "$BUDGET_CORES")
echo "[$(date)] the job pool: per-job logs in $LOG_DIR, state in $RUN_ROOT/jobs, snapshot in $RUN_ROOT/pool.json"
M run --run-root "$RUN_ROOT" --log-dir "$LOG_DIR" ${OPTIONS[@]+"${OPTIONS[@]}"}
RUN_EXIT=$?
M export --run-root "$RUN_ROOT" --export-dir "$EXPORT_DIR" --tag "$TAG"
if [ "$RUN_EXIT" != "0" ]; then
  REASON=$($PY -c "import json; print(json.load(open('$RUN_ROOT/pool.json')).get('stop_reason'))" 2>/dev/null)
  [ "$REASON" = "drained" ] && DRAINED=1
  DETAIL="the pool stopped (exit $RUN_EXIT): $REASON"; finish run "$RUN_EXIT"
fi
if M verify --run-root "$RUN_ROOT" --export-dir "$EXPORT_DIR" --tag "$TAG"; then
  DETAIL="every job ended, every gate passed, the fitted values are registered; exports in $EXPORT_DIR (*_$TAG.json)"; finish verify 0
fi
DETAIL="verify reported problems: $EXPORT_DIR/vsmt_lean_s3_03_verify_$TAG.json (elu_p_values_not_registered alone means: pull the registration commit and run all again)"
finish verify 3
