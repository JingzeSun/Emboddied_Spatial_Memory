#!/usr/bin/env bash
# Fixed D-051 phase commands: check, export. No training or held-out access.
# Foreground; all output and exit evidence retained. Never restart an attempt.
set -uo pipefail
CPMT_OPS_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
CPMT_REPO_DIR="$(git -C "$CPMT_OPS_DIR" rev-parse --show-toplevel)" || exit 2
cd "$CPMT_REPO_DIR" || exit 2
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export CUDA_VISIBLE_DEVICES="" PYTHONUNBUFFERED=1
python ops/m1_train_preflight.py "$@"
CPMT_EXIT=$?
printf 'PREFLIGHT_COMMAND_EXIT=%s\n' "$CPMT_EXIT"
exit "$CPMT_EXIT"
