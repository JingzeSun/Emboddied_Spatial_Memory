#!/bin/bash
# LLM-op, the appendix arm on the DeepSeek API (ruling 105, user 2026-10-04: 「待裁 105 全按推荐，但105-11我新租一台机器去同时做」).
#
# On the S3-02 host (read-only there; it touches nothing of the S3-03 run):
#   bash ops/vsmt/llm_op.sh plan                       draw the 15 validation episodes and the pilot episode, write
#                                                      $RUN_ROOT/plan.json and $RUN_ROOT/transfer.txt (the paths to copy)
#   bash ops/vsmt/llm_op.sh transfer <host> <port>     copy those paths, at the same absolute paths, to the LLM-op host over ssh
#                                                      (rsync; SSH_KEY names the key the LLM-op host accepts)
# On the LLM-op host (a clean checkout of the reviewed commit; no GPU needed; the key in $DEEPSEEK_API_KEY_FILE, mode 600):
#   bash ops/vsmt/llm_op.sh test                       the full test suite (log in $RUN_ROOT/logs)
#   bash ops/vsmt/llm_op.sh check                      re-verify every copied cache seal, the raw receipts, the geometry tables and
#                                                      both ReID heads against the plan; the key loads and the API lists the model
#   bash ops/vsmt/llm_op.sh pilot                      both front ends, the first 200 frames of the train pilot episode, live calls,
#                                                      no private read and no metric; registers the model name; exit 3 when the
#                                                      projection is over the $150 cap (stop and report, ruling 105-8)
#   bash ops/vsmt/llm_op.sh run                        the 30 validation episodes (2 front ends x 15) as node-audit runs of record;
#                                                      no new episode at $150, STOP at $200; run it again to resume (archived calls
#                                                      are replayed, never paid twice); long: nohup ... > <log> 2>&1 &
#   bash ops/vsmt/llm_op.sh status                     progress, spend, STOP reason
#   bash ops/vsmt/llm_op.sh export                     results/vsmt_lean_llm_op_<commit>.json
#   bash ops/vsmt/llm_op.sh replay-check <front> <episode>   replay one finished episode from its archive alone; it must match
#
# Environment (optional): PY (/root/miniconda3/bin/python3.12), RUN_ROOT ($AUTODL/vsmt_private/llm-op-run), INPUTS (the S3-03
#   check's inputs.json, for plan), SSH_KEY (for transfer), DEEPSEEK_API_KEY_FILE (/root/.config/vsmt/deepseek.env), WORKERS (at
#   most the check's choice), ACCEPT_PROJECTION=1 (the user accepted a pilot projection over the cap), RESUME_AFTER_STOP=1 (the user
#   decided to go on after a STOP; the STOP file is kept as STOP.<n>), RETRY_FAILED=1, EXPORT_OUT.
# Exit status: 0 done; 2 refused (a closed contract bit, a missing step, a changed plan or commit); 3 a decision point (projection
#   over the cap, a STOP, unfinished episodes); anything else a failure (see $RUN_ROOT/logs).
set -u
WORKTREE=$(cd "$(dirname "$0")/../.." && pwd)
cd "$WORKTREE" || exit 2
SHORT=$(git rev-parse --short HEAD)
PY=${PY:-/root/miniconda3/bin/python3.12}
AUTODL=${AUTODL:-/root/autodl-tmp}
RUN_ROOT=${RUN_ROOT:-$AUTODL/vsmt_private/llm-op-run}
INPUTS=${INPUTS:-$AUTODL/vsmt_private/s3-03-run/inputs.json}
export DEEPSEEK_API_KEY_FILE=${DEEPSEEK_API_KEY_FILE:-/root/.config/vsmt/deepseek.env}
EXPORT_OUT=${EXPORT_OUT:-results/vsmt_lean_llm_op_$SHORT.json}
COMMAND=${1:-}
D() { $PY ops/vsmt/llm_op.py "$@"; }
mkdir -p "$RUN_ROOT/logs"

case "$COMMAND" in
  plan)
    D plan --run-root "$RUN_ROOT" --inputs "$INPUTS"; exit $? ;;
  transfer)
    HOST=${2:?usage: transfer <host> <port>}; PORT=${3:?usage: transfer <host> <port>}
    [ -f "$RUN_ROOT/transfer.txt" ] || { echo "refused: no $RUN_ROOT/transfer.txt (run plan first)"; exit 2; }
    SSH="ssh -p $PORT -o StrictHostKeyChecking=accept-new${SSH_KEY:+ -i $SSH_KEY}"
    echo "[$(date)] copying $(wc -l < "$RUN_ROOT/transfer.txt") paths to root@$HOST:$PORT (same absolute paths)"
    rsync -a -r --relative --files-from="$RUN_ROOT/transfer.txt" -e "$SSH" / "root@$HOST:/"
    CODE=$?
    echo "[$(date)] rsync exit $CODE"; exit $CODE ;;
  test)
    PYTHONPATH=src $PY -m unittest discover -s tests -t tests -p "test_*.py" > "$RUN_ROOT/logs/suite-$SHORT.log" 2>&1
    CODE=$?
    tail -3 "$RUN_ROOT/logs/suite-$SHORT.log"; echo "suite exit $CODE (log $RUN_ROOT/logs/suite-$SHORT.log)"; exit $CODE ;;
  check)
    D check --run-root "$RUN_ROOT" ${WORKERS:+--workers "$WORKERS"}; exit $? ;;
  pilot|run)
    exec 9> "$RUN_ROOT/.lock"
    if ! flock -n 9; then echo "refused: another LLM-op driver holds $RUN_ROOT/.lock"; exit 2; fi
    if [ "$COMMAND" = pilot ]; then D pilot --run-root "$RUN_ROOT"; exit $?; fi
    OPTIONS=()
    [ -n "${WORKERS:-}" ] && OPTIONS+=(--workers "$WORKERS")
    [ "${ACCEPT_PROJECTION:-0}" = 1 ] && OPTIONS+=(--accept-projection)
    [ "${RESUME_AFTER_STOP:-0}" = 1 ] && OPTIONS+=(--resume-after-stop)
    [ "${RETRY_FAILED:-0}" = 1 ] && OPTIONS+=(--retry-failed)
    D run --run-root "$RUN_ROOT" "${OPTIONS[@]}"; exit $? ;;
  status)
    D status --run-root "$RUN_ROOT"; exit $? ;;
  export)
    D export --run-root "$RUN_ROOT" --out "$EXPORT_OUT"; exit $? ;;
  replay-check)
    D replay-check --run-root "$RUN_ROOT" --front "${2:?usage: replay-check <front> <episode>}" --episode "${3:?usage: replay-check <front> <episode>}"
    exit $? ;;
  *)
    echo "usage: bash ops/vsmt/llm_op.sh <plan|transfer|test|check|pilot|run|status|export|replay-check>"; exit 2 ;;
esac
