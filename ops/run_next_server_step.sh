#!/usr/bin/env bash
# Unique phase: train-only scope impact diagnostic on 201 EXISTING probe audits.
# Preconditions: accepted D047 probe and cached audits; original science unchanged.
# Reads only train audit cache, accepted reports, code/configs. No regeneration,
# candidate execution, model loading, validation/test or original-output writes.
# Writes separate diagnostic units/report/log and one exact results export.
# Running tasks only report status; successful output is verified/reused.
# Failed/interrupted tasks retain all evidence and require review before restart.
set -uo pipefail
export CPMT_SERVER_STEP_ID="m1_v6_d050_train_scope_impact"
CPMT_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
export CPMT_REPO_DIR="$(git -C "$CPMT_SCRIPT_DIR" rev-parse --show-toplevel)" || exit 2
export CPMT_IMPACT_DIR="/root/autodl-tmp/cpmt_outputs/m1-v6-d050-train-scope-impact"
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export CUDA_VISIBLE_DEVICES=""
cd "$CPMT_REPO_DIR" || exit 2
[[ -d /root/autodl-tmp ]] || exit 2

cpmt_verify_export() {
python - <<'PY_VERIFY'
import json,os,sys
from pathlib import Path
sys.path.insert(0,'src')
from cpmt.run_provenance import file_sha256
root=Path.cwd();out=Path(os.environ['CPMT_IMPACT_DIR'])
marker=json.loads((out/'scope_impact.ok.json').read_text())
target=root/'results/m1_v6_d050_train_scope_impact.json'
assert marker['stage']==os.environ['CPMT_SERVER_STEP_ID']
assert marker['diagnostic_sha256']==file_sha256(out/'diagnostic_report.json')
assert marker['export_sha256']==file_sha256(target)
assert json.loads(target.read_text())['diagnostic_report']==json.loads((out/'diagnostic_report.json').read_text())
print('EXPORT_VERIFIED path='+str(target)+' sha256='+file_sha256(target))
print('SERVER_STEP_OK id='+marker['stage']+' inspected_groups=201')
print('NEXT=review_export_then_commit_only_results/m1_v6_d050_train_scope_impact.json')
PY_VERIFY
}

if [[ "${1:-}" == "--worker" && "$#" -eq 1 ]]; then
  # Descriptor 9 must be inherited from the launcher that owns worker.lock.
  [[ -e /proc/$$/fd/9 && -f "$CPMT_IMPACT_DIR/started.json" ]] || exit 2
  (
    python -m unittest discover -s tests -p test_m1_scope_impact.py -v || exit $?
    python scripts/run_m1_scope_impact.py --out-dir "$CPMT_IMPACT_DIR" || exit $?
    python - <<'PY_EXPORT'
import json,os,subprocess,sys
from pathlib import Path
sys.path.insert(0,'src')
from cpmt.m1_s5_training import read_json,write_json,require
from cpmt.run_provenance import file_sha256
root=Path.cwd();out=Path(os.environ['CPMT_IMPACT_DIR']);name='m1_v6_d050_train_scope_impact'
report=read_json(out/'diagnostic_report.json')
require(report['groups']==201 and report['schema_version']=='cpmt-train-scope-impact-v1','incomplete impact report')
require(all(report[k] is False for k in ['validation_read','test_access','model_evaluation_performed','candidates_executed']), 'boundary violation')
require(report['by_kind']['reference']['rows']==8040, 'incomplete paired reference trajectories')
require(not report['diagnostic_provenance']['git_dirty'], 'diagnostic used dirty checkout')
target=root/'results'/f'{name}.json'
if target.exists():
    require(read_json(target)['diagnostic_report']==report, 'existing export differs; preserve it')
else:
    subprocess.run([sys.executable,'scripts/export_run_report.py','--out-dir',str(out),'--name',name,
                    '--note','Train-only fixed-candidate scope impact; no production correction or validation/model evaluation.'],check=True)
require(read_json(target)['diagnostic_report']==report,'export round trip mismatch')
write_json(out/'scope_impact.ok.json',{'stage':os.environ['CPMT_SERVER_STEP_ID'],
    'diagnostic_sha256':file_sha256(out/'diagnostic_report.json'),'export_sha256':file_sha256(target)})
PY_EXPORT
  )
  CPMT_WORKER_EXIT=$?
  printf '%s\n' "$CPMT_WORKER_EXIT" > "$CPMT_IMPACT_DIR/worker_exit.txt"
  if [[ "$CPMT_WORKER_EXIT" -eq 0 ]]; then
    cpmt_verify_export || exit 1
  else
    printf 'SERVER_STEP_FAILED id=%s reason=impact_failed_requires_review exit=%s\n' "$CPMT_SERVER_STEP_ID" "$CPMT_WORKER_EXIT"
  fi
  exit "$CPMT_WORKER_EXIT"
fi

[[ "$#" -eq 0 ]] || exit 2
command -v flock >/dev/null 2>&1 || exit 2
mkdir -p "$CPMT_IMPACT_DIR" || exit 2
exec 9>"$CPMT_IMPACT_DIR/worker.lock"
if ! flock -n 9; then
  printf 'SERVER_STEP_RUNNING id=%s\nLOG=%s/impact.log\n' "$CPMT_SERVER_STEP_ID" "$CPMT_IMPACT_DIR"
  tail -n 5 "$CPMT_IMPACT_DIR/impact.log" 2>/dev/null || true
  exit 0
fi
if [[ -f "$CPMT_IMPACT_DIR/worker_exit.txt" ]]; then
  if [[ "$(cat "$CPMT_IMPACT_DIR/worker_exit.txt")" == "0" ]]; then
    cpmt_verify_export
    exit $?
  fi
  printf 'SERVER_STEP_FAILED id=%s reason=previous_attempt_requires_review_no_automatic_restart\n' "$CPMT_SERVER_STEP_ID"
  exit 1
fi
if [[ -f "$CPMT_IMPACT_DIR/started.json" || -f "$CPMT_IMPACT_DIR/failure.json" ]]; then
  printf 'SERVER_STEP_FAILED id=%s reason=interrupted_attempt_requires_review\n' "$CPMT_SERVER_STEP_ID"
  exit 1
fi
python - <<'PY_START'
import json,os,subprocess
from pathlib import Path
assert not subprocess.check_output(['git','status','--porcelain']).strip(), 'clean checkout required'
out=Path(os.environ['CPMT_IMPACT_DIR'])
with (out/'started.json').open('x') as stream:
    json.dump({'stage':os.environ['CPMT_SERVER_STEP_ID'],
               'commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()},stream)
PY_START
[[ "$?" -eq 0 ]] || exit 1
nohup bash "$CPMT_SCRIPT_DIR/run_next_server_step.sh" --worker > "$CPMT_IMPACT_DIR/impact.log" 2>&1 < /dev/null &
CPMT_WORKER_PID=$!
printf 'SERVER_STEP_STARTED id=%s pid=%s\nLOG=%s/impact.log\n' "$CPMT_SERVER_STEP_ID" "$CPMT_WORKER_PID" "$CPMT_IMPACT_DIR"
printf 'Re-run bash ops/run_next_server_step.sh to inspect status; it will not launch duplicates.\n'
printf 'Keep this checkout unchanged while the worker runs. NEXT=review_train_scope_impact_report\n'
