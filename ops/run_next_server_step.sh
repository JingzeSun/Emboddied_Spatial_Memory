#!/usr/bin/env bash
# Unique active phase: fixed D-047 train-only endpoint viability probe.
set -uo pipefail
CPMT_SERVER_STEP_ID="m1_v6_v8_d047_fixed_train_only_endpoint_probe"
CPMT_EXPECTED_PROTOCOL="73666cabb77b4884302d77ca621669bfdc77e86a44951b8a92b97208509c0eec"
CPMT_EXPECTED_DATASET="m1-paired-latent-worlds-v8-fixed-range-current-energy"
CPMT_EXPECTED_FULL_TEST_COMMIT="d36ab9730fed0c32a2d7924ac0969c5acc013019"
CPMT_EXPECTED_TRAIN_DIGEST="e8a890f1b254a7109af641fea57fcbea5efd931b4272d8e96cb870f51604b168"
CPMT_TRAIN_RELATIVE="outputs/m1-v6-v8-d043-train-g1000-53539ce/train.npz"
CPMT_DATA_ROOT="/root/autodl-tmp"
CPMT_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
CPMT_REPO_DIR="$(git -C "$CPMT_SCRIPT_DIR" rev-parse --show-toplevel)" || exit 2
CPMT_CURRENT_COMMIT="$(git -C "$CPMT_REPO_DIR" rev-parse HEAD)" || exit 2
CPMT_COMMIT_SHORT="$(git -C "$CPMT_REPO_DIR" rev-parse --short=7 HEAD)" || exit 2
CPMT_OUTPUT_DIR="$CPMT_DATA_ROOT/cpmt_outputs/m1-v6-v8-d047-endpoint-probe-$CPMT_COMMIT_SHORT"
CPMT_MARKER="$CPMT_OUTPUT_DIR/endpoint_probe.ok.json"
CPMT_FULL_TEST_MARKER="$CPMT_REPO_DIR/outputs/m1-v6-v8-d046-full-test-d36ab97/full_test.ok.json"
CPMT_TRAIN="$CPMT_REPO_DIR/$CPMT_TRAIN_RELATIVE"
cpmt_fail() { local CPMT_FAILURE_MESSAGE="$1"; printf "SERVER_STEP_FAILED id=%s reason=%s\n" "$CPMT_SERVER_STEP_ID" "$CPMT_FAILURE_MESSAGE" >&2; exit 1; }
[[ "$#" -eq 0 ]] || cpmt_fail unexpected_arguments
command -v python >/dev/null 2>&1 || cpmt_fail python_not_found
command -v git >/dev/null 2>&1 || cpmt_fail git_not_found
git -C "$CPMT_REPO_DIR" diff --quiet || cpmt_fail tracked_changes_present
git -C "$CPMT_REPO_DIR" diff --cached --quiet || cpmt_fail staged_changes_present
[[ -z "$(git -C "$CPMT_REPO_DIR" ls-files --others --exclude-standard)" ]] || cpmt_fail untracked_files_present
CPMT_REMOTE_HEAD="$(git -C "$CPMT_REPO_DIR" ls-remote origin refs/heads/main | awk '{print $1}')"
[[ "$CPMT_REMOTE_HEAD" == "$CPMT_CURRENT_COMMIT" ]] || cpmt_fail origin_main_does_not_match_checkout
[[ -f "$CPMT_FULL_TEST_MARKER" ]] || cpmt_fail preceding_full_test_marker_missing
[[ -f "$CPMT_TRAIN" && -f "${CPMT_TRAIN%.npz}.manifest.json" ]] || cpmt_fail train_arrays_or_manifest_missing
[[ -d "$CPMT_DATA_ROOT" ]] || cpmt_fail data_disk_missing
mkdir -p "$CPMT_OUTPUT_DIR" || cpmt_fail output_directory_creation_failed
CPMT_PROBE_SHA256="$(sha256sum "$CPMT_REPO_DIR/configs/m1_endpoint_viability_probe.json" | awk '{print $1}')" || cpmt_fail probe_hash_failed
python - "$CPMT_FULL_TEST_MARKER" "$CPMT_EXPECTED_FULL_TEST_COMMIT" "$CPMT_EXPECTED_PROTOCOL" "$CPMT_EXPECTED_DATASET" "$CPMT_PROBE_SHA256" <<'PY' || cpmt_fail preceding_full_test_marker_invalid
import json,sys
from pathlib import Path
m=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
assert m['schema_version']=='cpmt-full-test-marker-v1' and m['commit']==sys.argv[2]
assert m['protocol_sha256']==sys.argv[3] and m['dataset_version']==sys.argv[4] and m['probe_config_sha256']==sys.argv[5]
assert m['exit_code']==0 and int(m['tests_run'])>=210
print(f"FULL_TEST_PREREQUISITE_OK tests={m['tests_run']}")
PY
python - "$CPMT_TRAIN" "$CPMT_EXPECTED_TRAIN_DIGEST" "$CPMT_EXPECTED_PROTOCOL" "$CPMT_EXPECTED_DATASET" <<'PY' || cpmt_fail train_manifest_invalid
import hashlib,json,sys
from pathlib import Path
import numpy as np
p=Path(sys.argv[1]); m=json.loads(p.with_suffix('.manifest.json').read_text(encoding='utf-8')); a={k:v for k,v in np.load(p,allow_pickle=True).items()}; h=hashlib.sha256()
for k in sorted(a):
    v=np.asarray(a[k]); h.update(k.encode()); h.update(str(v.dtype).encode()); h.update(str(v.shape).encode()); h.update(np.ascontiguousarray(v).tobytes())
assert h.hexdigest()==sys.argv[2] and m['arrays_digest']==sys.argv[2] and m['protocol_sha256']==sys.argv[3] and m['dataset_version']==sys.argv[4] and m['split']=='train'
print(f"TRAIN_ARRAYS_OK groups={len(set(a['group'].tolist()))} digest={h.hexdigest()}")
PY
printf "SERVER_STEP_BEGIN id=%s\nrepo=%s\ncommit=%s\n" "$CPMT_SERVER_STEP_ID" "$CPMT_REPO_DIR" "$CPMT_CURRENT_COMMIT"
printf "read_boundary=train_arrays_and_reconstructed_train_inner_dev_audits_only\nwrite_boundary=%s\nvalidation_arrays_read=false test_access=false\n" "$CPMT_OUTPUT_DIR"
if [[ -f "$CPMT_MARKER" ]]; then
  python - "$CPMT_MARKER" "$CPMT_CURRENT_COMMIT" "$CPMT_EXPECTED_TRAIN_DIGEST" <<'PY' || cpmt_fail existing_probe_marker_mismatch
import json,sys
from pathlib import Path
m=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')); assert m['schema_version']=='cpmt-endpoint-probe-marker-v1' and m['status']=='complete' and m['commit']==sys.argv[2] and m['train_arrays_digest']==sys.argv[3] and m['validation_arrays_read'] is False and m['test_access'] is False
print(f"ENDPOINT_PROBE_MARKER_REUSED disposition={m['disposition']}")
PY
else
  (cd "$CPMT_REPO_DIR" && python scripts/run_m1_endpoint_probe.py --train "$CPMT_TRAIN" --out-dir "$CPMT_OUTPUT_DIR" --workers 16 --threads 8 --device auto) 2>&1 | tee "$CPMT_OUTPUT_DIR/endpoint_probe.log"
  CPMT_PROBE_EXIT=${PIPESTATUS[0]}; printf "ENDPOINT_PROBE_EXIT=%s\n" "$CPMT_PROBE_EXIT"; [[ "$CPMT_PROBE_EXIT" -eq 0 ]] || cpmt_fail endpoint_probe_failed
  python - "$CPMT_OUTPUT_DIR/endpoint_probe_report.json" "$CPMT_MARKER" "$CPMT_CURRENT_COMMIT" "$CPMT_EXPECTED_TRAIN_DIGEST" <<'PY' || cpmt_fail endpoint_probe_marker_write_failed
import hashlib,json,sys
from pathlib import Path
rpath,mpath=Path(sys.argv[1]),Path(sys.argv[2]); r=json.loads(rpath.read_text(encoding='utf-8')); assert r['status']=='complete' and r['validation_arrays_read'] is False and r['test_access'] is False
m={'schema_version':'cpmt-endpoint-probe-marker-v1','status':'complete','commit':sys.argv[3],'train_arrays_digest':sys.argv[4],'report_sha256':hashlib.sha256(rpath.read_bytes()).hexdigest(),'disposition':r['endpoint_assessment']['disposition'],'selected_test_groups':r['endpoint_assessment']['selected_test_groups'],'validation_arrays_read':False,'test_access':False}; mpath.write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8'); print(f"ENDPOINT_PROBE_MARKER_WRITTEN disposition={m['disposition']}")
PY
fi
CPMT_RESULT_NAME="m1_v6_d047_endpoint_probe"
(cd "$CPMT_REPO_DIR" && python scripts/export_run_report.py \
  --out-dir "$CPMT_OUTPUT_DIR" --name "$CPMT_RESULT_NAME" \
  --note "D-047 fixed train-only endpoint probe; full causal rows remain on the server data disk.") \
  || cpmt_fail endpoint_result_export_failed
git -C "$CPMT_REPO_DIR" add -- "results/$CPMT_RESULT_NAME.json" || \
  cpmt_fail endpoint_result_stage_failed
if git -C "$CPMT_REPO_DIR" diff --cached --quiet; then
  printf "RESULT_PUSH_REUSED path=results/%s.json\n" "$CPMT_RESULT_NAME"
else
  git -C "$CPMT_REPO_DIR" commit -m "results: D-047 endpoint probe" || \
    cpmt_fail endpoint_result_commit_failed
  git -C "$CPMT_REPO_DIR" push origin main || cpmt_fail endpoint_result_push_failed
  printf "RESULT_PUSH_OK path=results/%s.json\n" "$CPMT_RESULT_NAME"
fi
printf "ENDPOINT_PROBE_REPORT=%s/endpoint_probe_report.json\nSERVER_STEP_OK id=%s\n" "$CPMT_OUTPUT_DIR" "$CPMT_SERVER_STEP_ID"
printf "NEXT=review_endpoint_probe_report_then_register_or_stop_before_budget_grid\n"
