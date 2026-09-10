#!/usr/bin/env bash
# S5 checks/generation are foreground; only long evaluation defaults background.
cd -- "$(dirname -- "$0")/.." || exit 1
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONUNBUFFERED=1
python ops/m1_corrected_confirmation.py "$@"
cpmt_s5_exit=$?
printf 'S5_COMMAND_EXIT=%s\n' "$cpmt_s5_exit"
exit "$cpmt_s5_exit"
