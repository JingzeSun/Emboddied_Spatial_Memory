#!/usr/bin/env bash
# Fixed engineering phase only; never launch while the corrected probe runs.
set -uo pipefail
CPMT_OPS_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
CPMT_REPO_DIR="$(git -C "$CPMT_OPS_DIR" rev-parse --show-toplevel)" || exit 2
cd "$CPMT_REPO_DIR" || exit 2
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONUNBUFFERED=1
python ops/m1_parallel_training_check.py "$@"
CPMT_EXIT=$?
printf 'PARALLEL_TRAINING_CHECK_COMMAND_EXIT=%s\n' "$CPMT_EXIT"
exit "$CPMT_EXIT"
