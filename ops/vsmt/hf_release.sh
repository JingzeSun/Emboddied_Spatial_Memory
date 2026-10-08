#!/bin/bash
# S3-05R: release the given tiers to Hugging Face in order (ruling 110), one command per run; rerun to resume.
#
# Usage (B1, from a clean checkout of the release commit, after `hf auth login`):
#   setsid nohup bash ops/vsmt/hf_release.sh T0 T1 > /root/autodl-tmp/vsmt_outputs/run_logs/hf-release.log 2>&1 < /dev/null &
# Per tier: the release tests -> plan -> run (pack, check against the S3-02 seal / cache exports, upload in batches) -> verify
# (remote sizes and sha256 against the manifest; the manifest and the repo revisions are exported to $EXPORT_DIR).
# Environment (optional): PY (default the hf venv, which sees the system packages), STATE, STAGING, EXPORT_DIR, BATCH_GIB.
set -u
WORKTREE=$(cd "$(dirname "$0")/../.." && pwd)
cd "$WORKTREE" || exit 2
PY=${PY:-/root/autodl-tmp/hf-venv/bin/python}
STATE=${STATE:-/root/autodl-tmp/hf-release}
STAGING=${STAGING:-/root/autodl-tmp/hf-staging}
EXPORT_DIR=${EXPORT_DIR:-/root/autodl-tmp/vsmt_outputs/exports}
BATCH_GIB=${BATCH_GIB:-20}
if [ "$#" -eq 0 ]; then echo "usage: bash ops/vsmt/hf_release.sh T0 [T1 T2 T3]"; exit 2; fi
if [ -n "$(git status --porcelain)" ]; then echo "refused: the worktree is not clean"; exit 2; fi
# shellcheck disable=SC1091
[ -f /etc/network_turbo ] && source /etc/network_turbo > /dev/null
echo "[$(date)] S3-05R at $(git rev-parse --short HEAD): tiers $*"
if ! PYTHONPATH=src $PY -m unittest tests.test_vsmt_lean_hf_release tests.test_vsmt_hf_release_driver tests.test_vsmt_hf_fetch > "$STATE-tests.log" 2>&1; then
  echo "[$(date)] the release tests failed ($STATE-tests.log)"; exit 1
fi
for TIER in "$@"; do
  for STEP in plan run verify; do
    case $STEP in
      plan) EXTRA=() ;;
      run) EXTRA=(--staging "$STAGING/$TIER" --batch-gib "$BATCH_GIB") ;;
      verify) EXTRA=(--export-dir "$EXPORT_DIR") ;;
    esac
    echo "[$(date)] $TIER $STEP"
    $PY ops/vsmt/hf_release.py "$STEP" --tier "$TIER" --state-dir "$STATE/$TIER" "${EXTRA[@]}"
    CODE=$?
    if [ "$CODE" != "0" ]; then echo "[$(date)] $TIER $STEP stopped (exit $CODE)"; exit "$CODE"; fi
  done
done
echo "[$(date)] S3-05R finished: $*"
