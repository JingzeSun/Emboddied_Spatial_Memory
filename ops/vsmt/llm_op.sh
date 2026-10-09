#!/bin/bash
# LLM-op, the validation-only arm on the DeepSeek API, paper Table III (ruling 105, user 2026-10-04:
# 「待裁 105 全按推荐，但105-11我新租一台机器去同时做」).
#
# On the S3-02 host (read-only there; it touches nothing of the S3-03 run):
#   bash ops/vsmt/llm_op.sh plan                       draw the validation episode (one per front end since ruling 108; 105-2
#                                                      had 15) and the pilot episode, write $RUN_ROOT/plan.json and
#                                                      $RUN_ROOT/transfer.txt (the paths to copy); refuses
#                                                      S3-03 inputs with problems, and provisional ones unless ALLOW_PROVISIONAL=1
#   bash ops/vsmt/llm_op.sh transfer <host> <port>     copy those paths, at the same absolute paths, to the LLM-op host over ssh
#                                                      (rsync; SSH_KEY names the key the LLM-op host accepts)
# On the LLM-op host (a clean checkout of the reviewed commit; no GPU needed; the key in $DEEPSEEK_API_KEY_FILE, mode 600):
#   bash ops/vsmt/llm_op.sh test                       the full test suite (log in $RUN_ROOT/logs)
#   bash ops/vsmt/llm_op.sh check                      re-verify every copied cache seal, the raw receipts, the geometry tables and
#                                                      both ReID heads against the plan; the key loads and the API lists the model
#   bash ops/vsmt/llm_op.sh pilot                      both front ends, the first 200 frames of the train pilot episode, live calls,
#                                                      no private read and no metric; registers the model name; exit 3 at a decision
#                                                      point: the worst-case projection plus the pilot's spend over the $30 cap, a
#                                                      call kind it could not price, a fallback rate above 2%, two model names
#   bash ops/vsmt/llm_op.sh run                        the validation episodes (2 front ends x 1) as node-audit runs of record;
#                                                      no new episode at $30 (started ones resume), STOP at $40 (ruling 108; the
#                                                      ledger includes the pilot; every worker also checks the ledgers itself);
#                                                      run it again to resume (archived calls are replayed, never paid twice);
#                                                      long: nohup ... > <log> 2>&1 &
#   bash ops/vsmt/llm_op.sh status                     progress, spend, STOP reason
#   bash ops/vsmt/llm_op.sh stop                       write STOP: every worker stops before its next call (killing the driver
#                                                      writes it too)
#   bash ops/vsmt/llm_op.sh replay-check [<front> <episode>]   replay from the archives alone (default: per front end the shortest
#                                                      drawn episode); must match the runs of record; BEFORE export
#   bash ops/vsmt/llm_op.sh export                     results/vsmt_lean_llm_op_<commit>.json (needs a passed replay-check)
#
# Environment (optional): PY (/root/miniconda3/bin/python3.12), RUN_ROOT ($AUTODL/vsmt_private/llm-op-run), INPUTS (the S3-03
#   check's inputs.json, for plan), SSH_KEY (for transfer), DEEPSEEK_API_KEY_FILE (/root/.config/vsmt/deepseek.env), WORKERS (at
#   most the check's choice), ALLOW_PROVISIONAL=1 (plan from provisional S3-03 inputs; recorded), SUPERSEDE_PLAN=1 (ruling
#   108: rewrite a plan made for another episode count, the old one kept as plan.superseded.<sha12>.json), ACCEPT_PILOT=1 (the
#   user accepted the pilot's decision point; recorded), RESUME_AFTER_STOP=1 (the user decided to go on after a STOP; the STOP
#   file is kept as STOP.<n>; past the $40 safety stop of ruling 108 a resumed run stops again at once unless a ruling raises
#   it), RETRY_FAILED=1, EXPORT_OUT.
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
    OPTIONS=()
    [ "${ALLOW_PROVISIONAL:-0}" = 1 ] && OPTIONS+=(--allow-provisional)
    [ "${SUPERSEDE_PLAN:-0}" = 1 ] && OPTIONS+=(--supersede)
    D plan --run-root "$RUN_ROOT" --inputs "$INPUTS" "${OPTIONS[@]}"; exit $? ;;
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
    [ "${ACCEPT_PILOT:-0}" = 1 ] && OPTIONS+=(--accept-pilot)
    [ "${RESUME_AFTER_STOP:-0}" = 1 ] && OPTIONS+=(--resume-after-stop)
    [ "${RETRY_FAILED:-0}" = 1 ] && OPTIONS+=(--retry-failed)
    D run --run-root "$RUN_ROOT" "${OPTIONS[@]}"; exit $? ;;
  status)
    D status --run-root "$RUN_ROOT"; exit $? ;;
  stop)
    D stop --run-root "$RUN_ROOT"; exit $? ;;
  export)
    D export --run-root "$RUN_ROOT" --out "$EXPORT_OUT"; exit $? ;;
  replay-check)
    if [ -n "${2:-}" ]; then D replay-check --run-root "$RUN_ROOT" --front "$2" --episode "${3:?usage: replay-check [<front> <episode>]}"; exit $?; fi
    D replay-check --run-root "$RUN_ROOT"; exit $? ;;
  *)
    echo "usage: bash ops/vsmt/llm_op.sh <plan|transfer|test|check|pilot|run|status|stop|replay-check|export>"; exit 2 ;;
esac
