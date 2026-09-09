#!/usr/bin/env bash
# One fixed-anchor phase: test / prepare / train / evaluate / status / export.
set -uo pipefail
CPMT_OPS_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
CPMT_REPO_DIR="$(git -C "$CPMT_OPS_DIR" rev-parse --show-toplevel)" || exit 2
cd "$CPMT_REPO_DIR" || exit 2
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export CUDA_VISIBLE_DEVICES="" PYTHONUNBUFFERED=1
python ops/m1_corrected_probe.py "$@"
CPMT_EXIT=$?
printf 'CORRECTED_PROBE_COMMAND_EXIT=%s\n' "$CPMT_EXIT"
exit "$CPMT_EXIT"
