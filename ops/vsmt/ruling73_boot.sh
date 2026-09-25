#!/bin/bash
# Ruling 73 boot (2026-09-26): one server session for the two approved read-only / retraining steps.
#   0. full test suite at this commit (stop here on failure)
#   1. depth probe smoke: one episode, one arm, 30 frames
#   2. in parallel: S1-04 --reid on the instance-segmentation cache (2 workers: the two largest episodes take
#      about 43 GB of the 62 GiB cgroup) and the depth probe on 16 development episodes x {TAF, LOW} (6 workers,
#      one thread each, about 1 GB each)
#   3. reports copied to exports/, a status file written, then (SHUTDOWN=1, the default) AutoDL shutdown after
#      a grace period so the laptop can fetch the reports
# Run from a clean worktree at the commit to test:  nohup bash ops/vsmt/ruling73_boot.sh > <log> 2>&1 &
# Nothing here freezes a value or changes a contract; the reports feed the ruling-73 follow-up.
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
REID_WEIGHTS=/root/autodl-tmp/vsmt_private/lean-s1-04-diagnostics-154776d/reid_head_vitb14.json
S1_04_ROOT=/root/autodl-tmp/vsmt_private/lean-s1-04-diagnostics-oracle-$COMMIT
PROBE_ROOT=/root/autodl-tmp/vsmt_private/lean-s2-05-depth-probe-$COMMIT
PROBE_EPISODES=procthor10k-0.1.2-train-00702,procthor10k-0.1.2-train-08905,procthor10k-0.1.2-train-01394,procthor10k-0.1.2-train-07270,procthor10k-0.1.2-train-08422,procthor10k-0.1.2-train-03288,procthor10k-0.1.2-train-04388,procthor10k-0.1.2-train-05879,procthor10k-0.1.2-train-00236,procthor10k-0.1.2-train-05966,procthor10k-0.1.2-train-07815,procthor10k-0.1.2-train-00975,procthor10k-0.1.2-train-09339,procthor10k-0.1.2-train-08566,procthor10k-0.1.2-train-04742,procthor10k-0.1.2-train-08552
STATUS=$EXPORT_DIR/ruling73_boot_$COMMIT.status.json
GRACE_SECONDS=${GRACE_SECONDS:-1200}
SHUTDOWN=${SHUTDOWN:-1}
mkdir -p "$EXPORT_DIR" "$LOG_DIR"

finish() {  # $1 = stage reached; writes the status file, then waits and shuts down
  SUITE_RC=${SUITE_RC:-} SMOKE_RC=${SMOKE_RC:-} S1_04_RC=${S1_04_RC:-} PROBE_RC=${PROBE_RC:-} MERGE_RC=${MERGE_RC:-} \
  $PY -c "import json,os,time,sys; json.dump({'commit': '$COMMIT', 'stage_reached': sys.argv[1], 'finished_cst': time.strftime('%Y-%m-%d %H:%M:%S'),
    'suite_exit': os.environ.get('SUITE_RC'), 'smoke_exit': os.environ.get('SMOKE_RC'), 's1_04_exit': os.environ.get('S1_04_RC'),
    'probe_exit': os.environ.get('PROBE_RC'), 'merge_exit': os.environ.get('MERGE_RC'), 'shutdown_after_seconds': $GRACE_SECONDS,
    'shutdown': $SHUTDOWN == 1}, open('$STATUS', 'w'), indent=1)" "$1"
  echo "[$(date)] status written ($1); shutdown=$SHUTDOWN after $GRACE_SECONDS s"
  if [ "$SHUTDOWN" = "1" ]; then sleep "$GRACE_SECONDS"; echo "[$(date)] shutting down (AutoDL)"; /usr/bin/shutdown; fi
  exit 0
}

if [ -n "$(git status --porcelain)" ]; then echo "worktree not clean; refusing"; exit 2; fi
echo "[$(date)] ruling-73 boot at $COMMIT"

# 0. full suite
PYTHONPATH=src $PY -m unittest discover -s tests -t tests -p "test_*.py" > "$LOG_DIR/suite-$COMMIT.log" 2>&1
SUITE_RC=$?
echo "[$(date)] suite exit $SUITE_RC: $(grep '^Ran ' "$LOG_DIR/suite-$COMMIT.log")"
[ "$SUITE_RC" = "0" ] || finish suite_failed

# 1. depth probe smoke
SMOKE_EPISODE_ROOT=$(ls -d $OUTPUTS/lean-s1-02a-5f9aa71/procthor10k-0.1.2-train-00702 $OUTPUTS/lean-s1-02b-5f9aa71/procthor10k-0.1.2-train-00702 2>/dev/null | head -1)
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 $PY ops/vsmt/lean_s2_05_depth_probe.py run   --cache-root "$CACHE_ROOT" --mask-source simulator_instance_masks --episode-root "$SMOKE_EPISODE_ROOT"   --geometry-root "$GEOMETRY_ROOT" --episode-id procthor10k-0.1.2-train-00702 --arm TAF --descriptor reid_projection:vitb14   --weights "$REID_WEIGHTS" --output-root "$PROBE_ROOT-smoke" --frames 30
SMOKE_RC=$?
echo "[$(date)] probe smoke exit $SMOKE_RC"

# 2. S1-04 --reid (background) and the depth probe (foreground) in parallel
$PY ops/vsmt/lean_s1_04_diagnostics.py --cache-root "$CACHE_ROOT" --episode-roots "$EPISODE_ROOTS" \
  --geometry-root "$GEOMETRY_ROOT" --output-root "$S1_04_ROOT" --workers 2 --reid --device cuda \
  --worker-basis "ruling 73 (3): ReID retrained on the instance-segmentation cache; 2 workers as at 154776d (the two largest episodes take about 43 GB of the 62 GiB cgroup; RSS grows with episode length), running beside a 6-worker depth probe (about 1 GB each)" \
  > "$LOG_DIR/s1-04-oracle-$COMMIT.log" 2>&1 &
S1_04_PID=$!
if [ "$SMOKE_RC" = "0" ]; then
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 $PY ops/vsmt/lean_s2_05_depth_probe.py pool \
    --cache-root "$CACHE_ROOT" --mask-source simulator_instance_masks --episode-roots "$EPISODE_ROOTS" \
    --geometry-root "$GEOMETRY_ROOT" --descriptor reid_projection:vitb14 --weights "$REID_WEIGHTS" \
    --output-root "$PROBE_ROOT" --episodes "$PROBE_EPISODES" --arms TAF,LOW --workers 6 \
    --worker-basis "16-core / 62 GiB cgroup shared with S1-04 (2 workers, about 43 GB peak); 6 probe workers x 1 thread at about 1 GB each" \
    > "$LOG_DIR/depth-probe-$COMMIT.log" 2>&1
  PROBE_RC=$?
  $PY ops/vsmt/lean_s2_05_depth_probe.py merge --output-root "$PROBE_ROOT" --results "$EXPORT_DIR/vsmt_lean_s2_05_depth_probe_$COMMIT.json" \
    >> "$LOG_DIR/depth-probe-$COMMIT.log" 2>&1
  MERGE_RC=$?
  echo "[$(date)] probe exit $PROBE_RC, merge exit $MERGE_RC"
fi
wait $S1_04_PID
S1_04_RC=$?
echo "[$(date)] S1-04 exit $S1_04_RC"
[ -f "$S1_04_ROOT/s1_04_diagnostics_receipt.json" ] && cp "$S1_04_ROOT/s1_04_diagnostics_receipt.json" "$EXPORT_DIR/vsmt_lean_s1_04_diagnostics_oracle_$COMMIT.json"
finish done
