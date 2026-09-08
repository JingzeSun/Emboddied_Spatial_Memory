#!/usr/bin/env bash
# Unique phase: the registered MLP arm in an independent worktree; GPU may be shared.
# Inputs: D-048 full-test success + existing v8 1,000-group train arrays.
# Read: repository, preceding marker, train arrays/manifest. No validation/test.
# Write: only this arm's data-disk log, execution status and final budget report.
# Resume: background worker survives terminal disconnect; lock prevents duplicates.
# A completed report is reused. An interrupted arm without a report is NOT restarted.
# No checkpoint resume exists inside the scientific runner; retain failures for review.
set -uo pipefail
export CPMT_SERVER_STEP_ID="m1_v6_d048_mlp_train_inner_dev_budget"
export CPMT_ARCHITECTURE="shared_candidate_mlp_v1"
export CPMT_EXPECTED_TEST_COMMIT="27d79eaa8f2312f62fff411d249bf574af061d8e"
export CPMT_EXPECTED_REGISTRATION="d366935b14975a18cf3e0af58833fcb8a1151c5929c8848d40677d692fd51e1d"
export CPMT_EXPECTED_PROTOCOL="73666cabb77b4884302d77ca621669bfdc77e86a44951b8a92b97208509c0eec"
export CPMT_EXPECTED_TRAIN_DIGEST="e8a890f1b254a7109af641fea57fcbea5efd931b4272d8e96cb870f51604b168"
CPMT_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
export CPMT_REPO_DIR="$(git -C "$CPMT_SCRIPT_DIR" rev-parse --show-toplevel)" || exit 2
export CPMT_CURRENT_COMMIT="$(git -C "$CPMT_REPO_DIR" rev-parse HEAD)" || exit 2
export CPMT_OUTPUT_DIR="/root/autodl-tmp/cpmt_outputs/m1-v6-d048-budget-mlp"
export CPMT_FULL_TEST_MARKER="/root/autodl-tmp/cpmt_outputs/m1-v6-d048-full-test-27d79ea/full_test.ok.json"
# Resolve the actual primary checkout via Git; do not guess its path or spelling.
export CPMT_SOURCE_REPO="$(python - "$CPMT_REPO_DIR" <<'PY'
import subprocess,sys
from pathlib import Path
root=Path(sys.argv[1])
p=Path(subprocess.check_output(['git','-C',str(root),'rev-parse','--git-common-dir'],text=True).strip())
print((p if p.is_absolute() else root/p).resolve().parent)
PY
)" || exit 2
export CPMT_EXPECTED_PRIMARY_COMMIT="72f1b8a879b86c6b37f107ac29a14989a6b67f07"
export CPMT_PRIMARY_RUN_DIR="/root/autodl-tmp/cpmt_outputs/m1-v6-d048-budget-set-transformer"
export CPMT_TRAIN="$CPMT_SOURCE_REPO/outputs/m1-v6-v8-d043-train-g1000-53539ce/train.npz"
export CPMT_MARKER="$CPMT_OUTPUT_DIR/budget.ok.json"
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=8
export MKL_NUM_THREADS=8
cpmt_fail() { printf "SERVER_STEP_FAILED id=%s reason=%s\nLOG=%s/budget.log\n" "$CPMT_SERVER_STEP_ID" "$1" "$CPMT_OUTPUT_DIR" >&2; exit 1; }
[[ "$#" -eq 0 ]] || cpmt_fail unexpected_arguments
[[ "$CPMT_REPO_DIR" != "$CPMT_SOURCE_REPO" ]] || cpmt_fail independent_worktree_required_do_not_pull_the_running_checkout
cd "$CPMT_REPO_DIR" || cpmt_fail repository_unavailable

cpmt_check_prerequisites() {
  git diff --quiet || return 1
  git diff --cached --quiet || return 1
  [[ -z "$(git ls-files --others --exclude-standard)" ]] || return 1
  python - <<'PY'
import json,os,subprocess,sys
from pathlib import Path
sys.path.insert(0,'src')
from cpmt.m1_protocol import load_and_validate,load_and_validate_endpoint_probe,protocol_sha256
from cpmt.m1_registration import load_registration
from cpmt.run_provenance import source_tree_sha256
e=os.environ; root=Path.cwd()
assert subprocess.check_output(['git','-C',e['CPMT_SOURCE_REPO'],'rev-parse','HEAD'],text=True).strip()==e['CPMT_EXPECTED_PRIMARY_COMMIT'], 'primary checkout changed'
primary=json.loads((Path(e['CPMT_PRIMARY_RUN_DIR'])/'started.json').read_text())
assert primary['commit']==e['CPMT_EXPECTED_PRIMARY_COMMIT'] and primary['architecture']=='cross_candidate_set_transformer_v1'
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==e['CPMT_CURRENT_COMMIT']
m=json.loads(Path(e['CPMT_FULL_TEST_MARKER']).read_text(encoding='utf-8'))
assert m['schema_version']=='cpmt-d048-full-test-marker-v1'
assert m['commit']==e['CPMT_EXPECTED_TEST_COMMIT'] and m['tests_run']==221 and m['exit_code']==0
assert m['failures']==0 and m['errors']==0 and m['skipped']==0
assert m['registration_sha256']==e['CPMT_EXPECTED_REGISTRATION']
assert m['source_and_tests_sha256']==source_tree_sha256(root,roots=('src','scripts','configs','tests'))
assert m['test_access'] is False and m['formal_validation_arrays_read'] is False
hard=load_and_validate(root/'configs/m1_hard_condition.json')
overlay=load_and_validate_endpoint_probe(root/'configs/m1_endpoint_viability_probe.json',hard)
r=load_registration(root,hard,overlay)
assert protocol_sha256(r)==e['CPMT_EXPECTED_REGISTRATION'] and protocol_sha256(hard)==e['CPMT_EXPECTED_PROTOCOL']
assert e['CPMT_ARCHITECTURE'] in hard['training']['pretest_budget_selection']['architectures']
print('FULL_TEST_AND_REGISTRATION_PREREQUISITES_OK tests=221 test_access=false',flush=True)
PY
}

cpmt_finish_report() {
  cpmt_check_prerequisites || return 1
  python - <<'PY'
import hashlib,json,os
from pathlib import Path
e=os.environ; out=Path(e['CPMT_OUTPUT_DIR']); path=out/'budget_report.json'
assert (out/'runner_exit.txt').read_text().strip()=='0'
started=json.loads((out/'started.json').read_text())
assert started['commit']==e['CPMT_CURRENT_COMMIT'] and started['stage']==e['CPMT_SERVER_STEP_ID']
r=json.loads(path.read_text(encoding='utf-8'))
assert r['schema_version']=='cpmt-m1-v8-train-inner-dev-budget-v3'
assert r['architecture']==e['CPMT_ARCHITECTURE'] and r['architecture_result_selection_forbidden'] is True
assert r['protocol_sha256']==e['CPMT_EXPECTED_PROTOCOL'] and r['post_probe_registration_sha256']==e['CPMT_EXPECTED_REGISTRATION']
assert r['formal_run'] is False and r['test_generated'] is False and r['causal_complete'] is False
assert r['training_provenance']['git_commit']==e['CPMT_CURRENT_COMMIT'] and r['training_provenance']['git_dirty'] is False
assert r['input_arrays']['train']['arrays_digest']==e['CPMT_EXPECTED_TRAIN_DIGEST']
p=r['partition']; assert p['train_paired_groups']==1000
assert len(p['fitting_group_ids'])==799 and len(p['inner_dev_group_ids'])==201
assert not(set(p['fitting_group_ids']) & set(p['inner_dev_group_ids']))
assert p['validation_arrays_read'] is False and p['validation_trial_consumed'] is False and p['test_access'] is False
assert set(r['selected']['student_hyperparameters_by_method'])==set('ABCDE')
assert len(r['scorer']['runs'])==60 and len(r['students']['runs'])==300
aux=r['students']['C_auxiliary_weight_runs']
assert len(aux)==15
assert sum(row['selection_stage']=='reused_anchor_run_at_fixed_selected_compute' for row in aux)==5
assert sum(row['selection_stage']=='auxiliary_weight_at_fixed_selected_compute' for row in aux)==10
assert r['parameter_fairness']['learning_rate_updates_grid_cells_per_method']==12
m={'schema_version':'cpmt-d048-budget-arm-marker-v1','stage':e['CPMT_SERVER_STEP_ID'],
   'commit':e['CPMT_CURRENT_COMMIT'],'architecture':e['CPMT_ARCHITECTURE'],
   'registration_sha256':e['CPMT_EXPECTED_REGISTRATION'],'train_arrays_digest':e['CPMT_EXPECTED_TRAIN_DIGEST'],
   'report_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'runner_exit_code':0,
   'validation_arrays_read':False,'test_access':False}
marker=Path(e['CPMT_MARKER'])
if marker.exists():
    assert json.loads(marker.read_text())==m
else:
    tmp=marker.with_suffix('.tmp'); tmp.write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8'); tmp.replace(marker)
print(f"BUDGET_REPORT_VALIDATED architecture={e['CPMT_ARCHITECTURE']}",flush=True)
PY
}

cpmt_resource_snapshot() {
  python - "$1" <<'PY'
import datetime,json,os,subprocess,sys
from pathlib import Path
e=os.environ; queries={}
for name,query in [('device','--query-gpu=index,name,utilization.gpu,memory.used,memory.total'),
                   ('processes','--query-compute-apps=pid,process_name,used_gpu_memory')]:
    try:
        r=subprocess.run(['nvidia-smi',query,'--format=csv,noheader'],capture_output=True,text=True,timeout=15)
        queries[name]={'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr}
    except (OSError,subprocess.TimeoutExpired) as error:
        queries[name]={'unavailable':str(error)}
m={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'architecture':e['CPMT_ARCHITECTURE'],
   'cpu_logical_count':os.cpu_count(),'torch_threads':8,'gpu_sharing_allowed':True,
   'primary_run_directory':e['CPMT_PRIMARY_RUN_DIR'],'primary_commit':e['CPMT_EXPECTED_PRIMARY_COMMIT'],
   'runtime_not_an_exclusive_gpu_benchmark':True,'nvidia_smi':queries}
(Path(e['CPMT_OUTPUT_DIR'])/sys.argv[1]).write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8')
PY
}

if [[ "${CPMT_BUDGET_WORKER:-0}" == "1" ]]; then
  # Descriptor 9, inherited from the launcher, owns the lock until this job exits.
  trap 'CPMT_WORKER_EXIT=$?; printf "%s\n" "$CPMT_WORKER_EXIT" > "$CPMT_OUTPUT_DIR/worker_exit.txt"' EXIT
  cpmt_check_prerequisites || cpmt_fail prerequisites_changed
  python - <<'PY' || cpmt_fail train_or_cuda_prerequisite_failed
import json,os,sys
from pathlib import Path
import numpy as np
import torch
sys.path.insert(0,'src')
from cpmt.run_provenance import arrays_sha256
e=os.environ; path=Path(e['CPMT_TRAIN'])
m=json.loads(path.with_suffix('.manifest.json').read_text(encoding='utf-8'))
with np.load(path,allow_pickle=True) as f: a={k:f[k] for k in f.files}
assert arrays_sha256(a)==m['arrays_digest']==e['CPMT_EXPECTED_TRAIN_DIGEST']
assert m['protocol_sha256']==e['CPMT_EXPECTED_PROTOCOL'] and m['split']=='train'
assert m['teacher_health_gate']['pass'] is True and len(set(a['group'].tolist()))==1000
assert torch.cuda.is_available(), 'CUDA required; do not silently start hours of CPU training'
print(f"TRAIN_ARRAYS_OK groups=1000 digest={m['arrays_digest']} cuda={torch.cuda.get_device_name(0)}",flush=True)
PY
  cpmt_resource_snapshot resource_start.json || cpmt_fail resource_start_record_failed
  printf "BUDGET_RUN_BEGIN architecture=%s\n" "$CPMT_ARCHITECTURE"
  python scripts/run_m1_train_inner_dev_budget.py --train "$CPMT_TRAIN" --out-dir "$CPMT_OUTPUT_DIR" --architecture "$CPMT_ARCHITECTURE" --device cuda --threads 8
  CPMT_RUN_EXIT=$?
  printf "%s\n" "$CPMT_RUN_EXIT" > "$CPMT_OUTPUT_DIR/runner_exit.txt"
  printf "BUDGET_RUN_EXIT=%s\n" "$CPMT_RUN_EXIT"
  cpmt_resource_snapshot resource_end.json || cpmt_fail resource_end_record_failed
  [[ "$CPMT_RUN_EXIT" -eq 0 ]] || cpmt_fail budget_runner_failed_no_automatic_restart
  cpmt_finish_report || cpmt_fail budget_report_validation_failed
  printf "SERVER_STEP_OK id=%s\n" "$CPMT_SERVER_STEP_ID"
  exit 0
fi

command -v flock >/dev/null 2>&1 || cpmt_fail flock_missing
command -v nohup >/dev/null 2>&1 || cpmt_fail nohup_missing
[[ -d /root/autodl-tmp ]] || cpmt_fail data_disk_missing
mkdir -p "$CPMT_OUTPUT_DIR" || cpmt_fail output_directory_creation_failed
exec 9>"$CPMT_OUTPUT_DIR/worker.lock"
if ! flock -n 9; then
  printf "SERVER_STEP_RUNNING id=%s\nLOG=%s/budget.log\n" "$CPMT_SERVER_STEP_ID" "$CPMT_OUTPUT_DIR"
  [[ ! -f "$CPMT_OUTPUT_DIR/budget.log" ]] || tail -n 8 "$CPMT_OUTPUT_DIR/budget.log"
  exit 0
fi
cpmt_check_prerequisites || cpmt_fail full_test_or_registration_prerequisite_failed
if [[ -f "$CPMT_MARKER" || -f "$CPMT_OUTPUT_DIR/runner_exit.txt" ]]; then
  cpmt_finish_report || cpmt_fail previous_attempt_requires_review_no_automatic_restart
  printf "SERVER_STEP_OK id=%s\nBUDGET_REPORT=%s/budget_report.json\n" "$CPMT_SERVER_STEP_ID" "$CPMT_OUTPUT_DIR"
  exit 0
fi
[[ ! -f "$CPMT_OUTPUT_DIR/started.json" && ! -f "$CPMT_OUTPUT_DIR/budget.log" && ! -f "$CPMT_OUTPUT_DIR/budget_report.json" ]] || cpmt_fail interrupted_attempt_requires_review_no_automatic_restart
CPMT_REMOTE_HEAD="$(git ls-remote origin refs/heads/main | awk '{print $1}')"
[[ "$CPMT_REMOTE_HEAD" == "$CPMT_CURRENT_COMMIT" ]] || cpmt_fail origin_main_does_not_match_checkout
python - <<'PY' || cpmt_fail start_record_failed
import datetime,json,os
from pathlib import Path
e=os.environ
m={'stage':e['CPMT_SERVER_STEP_ID'],'commit':e['CPMT_CURRENT_COMMIT'],
   'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
   'architecture':e['CPMT_ARCHITECTURE'],'read_boundary':'existing_train_arrays_only',
   'input_source_repository':e['CPMT_SOURCE_REPO'],'gpu_sharing_allowed':True,
   'concurrent_primary_run_directory':e['CPMT_PRIMARY_RUN_DIR'],
   'runtime_not_an_exclusive_gpu_benchmark':True,
   'write_boundary':e['CPMT_OUTPUT_DIR'],'validation_arrays_read':False,'test_access':False}
(Path(e['CPMT_OUTPUT_DIR'])/'started.json').write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8')
PY
CPMT_BUDGET_WORKER=1 nohup bash "$CPMT_SCRIPT_DIR/run_next_server_step.sh" > "$CPMT_OUTPUT_DIR/budget.log" 2>&1 < /dev/null 9>&9 &
CPMT_WORKER_PID=$!
printf "%s\n" "$CPMT_WORKER_PID" > "$CPMT_OUTPUT_DIR/worker.pid"
printf "SERVER_STEP_STARTED id=%s pid=%s\nLOG=%s/budget.log\n" "$CPMT_SERVER_STEP_ID" "$CPMT_WORKER_PID" "$CPMT_OUTPUT_DIR"
printf "Re-run bash ops/run_next_server_step.sh to inspect status; it will not launch duplicates.\n"
printf "Keep this checkout unchanged while the worker runs. NEXT=review_both_registered_arms_before_export_or_validation\n"
