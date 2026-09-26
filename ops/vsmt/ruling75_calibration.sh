#!/bin/bash
# Ruling 75 boot (2026-09-26): the evidence ceiling on an ideal memory and the calibration pass on the gated
# development association (TAF at the rollout theta_a, no gate) with the ELU-P counts, then the ELU-P fit, then shutdown.
#   0. full test suite at this commit (stop on failure)
#   1. evidence ceiling (read-only, lean_s2_05_evidence_ceiling.py) over the 39 episodes, merged to exports/
#   2. run-pass calibration with --calibration --elu-p-counts (WORKERS workers x 1 thread)
#   3. calibration-report, fit-elu-p --from-pass calibration, export of the calibration pass
#   4. a status file, then (SHUTDOWN=1) AutoDL shutdown after a grace period for the laptop to fetch
# Run from a clean worktree at the commit to test:  nohup bash ops/vsmt/ruling75_calibration.sh > <log> 2>&1 &
# RESUME=1 skips the suite and continues both steps (finished ceiling files and pass receipts are kept).
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
CEILING_ROOT=/root/autodl-tmp/vsmt_private/lean-s2-05-evidence-ceiling-$COMMIT
STATUS=$EXPORT_DIR/ruling75_calibration_$COMMIT.status.json
QUOTA=$(awk '{ if ($1 == "max") print 16; else print int($1 / $2) }' /sys/fs/cgroup/cpu.max 2>/dev/null || echo 16)
WORKERS=${WORKERS:-$((QUOTA - 1))}
GRACE_SECONDS=${GRACE_SECONDS:-1200}
SHUTDOWN=${SHUTDOWN:-1}
RESUME=${RESUME:-0}
mkdir -p "$EXPORT_DIR" "$LOG_DIR"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

finish() {
  $PY -c "import json,sys,time; json.dump({'commit': '$COMMIT', 'stage_reached': sys.argv[1], 'finished_cst': time.strftime('%Y-%m-%d %H:%M:%S'),
    'suite_exit': '${SUITE_RC:-}', 'ceiling_exit': '${CEILING_RC:-}', 'ceiling_merge_exit': '${CEILING_MERGE_RC:-}', 'pass_exit': '${PASS_RC:-}',
    'report_exit': '${REPORT_RC:-}', 'fit_exit': '${FIT_RC:-}', 'export_exit': '${EXPORT_RC:-}',
    'workers': $WORKERS, 'cpu_quota': $QUOTA, 'shutdown_after_seconds': $GRACE_SECONDS, 'shutdown': $SHUTDOWN == 1}, open('$STATUS', 'w'), indent=1)" "$1"
  echo "[$(date)] status written ($1); shutdown=$SHUTDOWN after $GRACE_SECONDS s"
  if [ "$SHUTDOWN" = "1" ]; then sleep "$GRACE_SECONDS"; echo "[$(date)] shutting down (AutoDL)"; /usr/bin/shutdown; fi
  exit 0
}

if [ -n "$(git status --porcelain)" ]; then echo "worktree not clean; refusing"; exit 2; fi
echo "[$(date)] ruling-75 calibration at $COMMIT, cpu quota $QUOTA, $WORKERS workers, resume=$RESUME"

if [ "$RESUME" != "1" ]; then
  PYTHONPATH=src $PY -m unittest discover -s tests -t tests -p "test_*.py" > "$LOG_DIR/suite-$COMMIT.log" 2>&1
  SUITE_RC=$?
  echo "[$(date)] suite exit $SUITE_RC: $(grep '^Ran ' "$LOG_DIR/suite-$COMMIT.log" | tail -1)"
  [ "$SUITE_RC" = "0" ] || finish suite_failed
fi

$PY ops/vsmt/lean_s2_05_evidence_ceiling.py pool --cache-root "$CACHE_ROOT" --mask-source simulator_instance_masks \
  --episode-roots "$EPISODE_ROOTS" --geometry-root "$GEOMETRY_ROOT" --output-root "$CEILING_ROOT" --workers "$WORKERS" \
  --worker-basis "cgroup quota $QUOTA CPUs; read-only per-episode replay without any arm, about 1 GB each; $WORKERS workers x 1 thread" \
  > "$LOG_DIR/evidence-ceiling-$COMMIT.log" 2>&1
CEILING_RC=$?
$PY ops/vsmt/lean_s2_05_evidence_ceiling.py merge --output-root "$CEILING_ROOT" \
  --results "$EXPORT_DIR/vsmt_lean_s2_05_evidence_ceiling_$COMMIT.json" >> "$LOG_DIR/evidence-ceiling-$COMMIT.log" 2>&1
CEILING_MERGE_RC=$?
echo "[$(date)] evidence ceiling exit $CEILING_RC, merge exit $CEILING_MERGE_RC"

RESUME_FLAG=""
[ "$RESUME" = "1" ] && RESUME_FLAG="--resume"
$PY ops/vsmt/lean_s2_05_development.py run-pass --pass calibration --arm TAF --config '{"theta_a": 0.7, "d_a": null}' \
  --calibration --elu-p-counts --cache-root "$CACHE_ROOT" --mask-source simulator_instance_masks \
  --episode-roots "$EPISODE_ROOTS" --geometry-root "$GEOMETRY_ROOT" --descriptor reid_projection:vitb14 --weights "$REID_WEIGHTS" \
  --output-root "$PASS_ROOT" --device cpu --workers "$WORKERS" $RESUME_FLAG \
  --worker-basis "cgroup quota $QUOTA CPUs / 62 GiB; streaming S2-04 workers CPU-bound at about 1 GB RSS; $WORKERS workers x 1 thread; the same thread setting as every pass on the instance-segmentation cache" \
  > "$LOG_DIR/s2-05-calibration-$COMMIT.log" 2>&1
PASS_RC=$?
echo "[$(date)] calibration pass exit $PASS_RC"
$PY ops/vsmt/lean_s2_05_development.py calibration-report --output-root "$PASS_ROOT" >> "$LOG_DIR/s2-05-calibration-$COMMIT.log" 2>&1
REPORT_RC=$?
$PY ops/vsmt/lean_s2_05_development.py fit-elu-p --output-root "$PASS_ROOT" --from-pass calibration >> "$LOG_DIR/s2-05-calibration-$COMMIT.log" 2>&1
FIT_RC=$?
[ -f "$PASS_ROOT/calibration/elu_p_fit.json" ] && cp "$PASS_ROOT/calibration/elu_p_fit.json" "$EXPORT_DIR/vsmt_lean_s2_05_elu_p_fit_$COMMIT.json"
$PY ops/vsmt/lean_s2_05_export.py --output-root "$PASS_ROOT" --pass calibration --arm TAF \
  --results "$EXPORT_DIR/vsmt_lean_s2_05_calibration_oracle_$COMMIT.json" >> "$LOG_DIR/s2-05-calibration-$COMMIT.log" 2>&1
EXPORT_RC=$?
echo "[$(date)] report exit $REPORT_RC, fit exit $FIT_RC, export exit $EXPORT_RC"
finish done
