#!/bin/bash
# Ruling 74 boot (2026-09-26): the S2-05 calibration pass under the per-point depth test, then shutdown.
#   0. full test suite at this commit (stop on failure)
#   1. run-pass calibration: LOW with no gate over the 39 instance-segmentation cache episodes, the retrained
#      ReID head (ruling 73 (3)), WORKERS workers x 1 thread (the default leaves one core of the cgroup quota free)
#   2. calibration-report and export to exports/
#   3. a status file, then (SHUTDOWN=1, the default) AutoDL shutdown after a grace period for the laptop to fetch
# Run from a clean worktree at the commit to test:  nohup bash ops/vsmt/ruling74_calibration.sh > <log> 2>&1 &
# Resumable: rerun with RESUME=1 after an interruption (run-pass --resume keeps finished receipts).
set -u
WORKTREE=$(cd "$(dirname "$0")/../.." && pwd)
cd "$WORKTREE"
COMMIT=$(git rev-parse --short HEAD)
PY=/root/miniconda3/bin/python3.12
OUTPUTS=/root/autodl-tmp/vsmt_outputs
EXPORT_DIR=$OUTPUTS/exports
LOG_DIR=$OUTPUTS/run_logs
CACHE_ROOT=/root/autodl-tmp/vsmt_caches/lean-s1-03-oracle-8ebbd05
EPISODE_ROOTS=$OUTPUTS/lean-s1-02a-5f9aa71,$OUTPUTS/lean-s1-02b-5f9aa71
GEOMETRY_ROOT=/root/autodl-tmp/vsmt_private/lean-s1-04-geometry-154776d
REID_WEIGHTS=/root/autodl-tmp/vsmt_private/lean-s1-04-diagnostics-oracle-caa50c7/reid_head_vitb14.json
PASS_ROOT=/root/autodl-tmp/vsmt_private/lean-s2-05-oracle-$COMMIT
STATUS=$EXPORT_DIR/ruling74_calibration_$COMMIT.status.json
QUOTA=$(awk '{ if ($1 == "max") print 16; else print int($1 / $2) }' /sys/fs/cgroup/cpu.max 2>/dev/null || echo 16)
WORKERS=${WORKERS:-$((QUOTA - 1))}
GRACE_SECONDS=${GRACE_SECONDS:-1200}
SHUTDOWN=${SHUTDOWN:-1}
RESUME=${RESUME:-0}
mkdir -p "$EXPORT_DIR" "$LOG_DIR"

finish() {
  $PY -c "import json,sys,time; json.dump({'commit': '$COMMIT', 'stage_reached': sys.argv[1], 'finished_cst': time.strftime('%Y-%m-%d %H:%M:%S'),
    'suite_exit': '${SUITE_RC:-}', 'pass_exit': '${PASS_RC:-}', 'report_exit': '${REPORT_RC:-}', 'export_exit': '${EXPORT_RC:-}',
    'workers': $WORKERS, 'cpu_quota': $QUOTA, 'shutdown_after_seconds': $GRACE_SECONDS, 'shutdown': $SHUTDOWN == 1}, open('$STATUS', 'w'), indent=1)" "$1"
  echo "[$(date)] status written ($1); shutdown=$SHUTDOWN after $GRACE_SECONDS s"
  if [ "$SHUTDOWN" = "1" ]; then sleep "$GRACE_SECONDS"; echo "[$(date)] shutting down (AutoDL)"; /usr/bin/shutdown; fi
  exit 0
}

if [ -n "$(git status --porcelain)" ]; then echo "worktree not clean; refusing"; exit 2; fi
echo "[$(date)] ruling-74 calibration at $COMMIT, cpu quota $QUOTA, $WORKERS workers, resume=$RESUME"

if [ "$RESUME" != "1" ]; then
  PYTHONPATH=src $PY -m unittest discover -s tests -t tests -p "test_*.py" > "$LOG_DIR/suite-$COMMIT.log" 2>&1
  SUITE_RC=$?
  echo "[$(date)] suite exit $SUITE_RC: $(grep '^Ran ' "$LOG_DIR/suite-$COMMIT.log" | tail -1)"
  [ "$SUITE_RC" = "0" ] || finish suite_failed
fi

RESUME_FLAG=""
[ "$RESUME" = "1" ] && RESUME_FLAG="--resume"
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 $PY ops/vsmt/lean_s2_05_development.py run-pass --pass calibration \
  --arm LOW --config '{"d_low": null}' --calibration --cache-root "$CACHE_ROOT" --mask-source simulator_instance_masks \
  --episode-roots "$EPISODE_ROOTS" --geometry-root "$GEOMETRY_ROOT" --descriptor reid_projection:vitb14 --weights "$REID_WEIGHTS" \
  --output-root "$PASS_ROOT" --device cpu --workers "$WORKERS" $RESUME_FLAG \
  --worker-basis "cgroup quota $QUOTA CPUs / 62 GiB; streaming S2-04 workers are CPU-bound at about 1 GB RSS (0313469 pass); $WORKERS workers x 1 thread leave one core for the orchestrator; the same thread setting as every pass on the instance-segmentation cache" \
  > "$LOG_DIR/s2-05-calibration-$COMMIT.log" 2>&1
PASS_RC=$?
echo "[$(date)] calibration pass exit $PASS_RC"
$PY ops/vsmt/lean_s2_05_development.py calibration-report --output-root "$PASS_ROOT" >> "$LOG_DIR/s2-05-calibration-$COMMIT.log" 2>&1
REPORT_RC=$?
$PY ops/vsmt/lean_s2_05_export.py --output-root "$PASS_ROOT" --pass calibration --arm LOW \
  --results "$EXPORT_DIR/vsmt_lean_s2_05_calibration_oracle_$COMMIT.json" >> "$LOG_DIR/s2-05-calibration-$COMMIT.log" 2>&1
EXPORT_RC=$?
echo "[$(date)] report exit $REPORT_RC, export exit $EXPORT_RC"
finish done
