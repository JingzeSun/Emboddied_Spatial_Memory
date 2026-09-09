#!/usr/bin/env bash
# Unique phase: corrected v7/v9 1000-group train generation and acceptance.
# Input: clean checkout and matching 280-test success marker (read-only).
# Write only the new source-bound data directory; preserve all old outputs.
# Foreground: historical same-size generation took about 17 minutes / 16 workers.
# Reuse completed generation; partial/failed attempts require review, never rerun.
# No training, probe, validation/test generation, export, or Git mutation.
# Sole success: SERVER_STEP_OK id=m1_v7_d051_corrected_train_generation
set -uo pipefail
export CPMT_SERVER_STEP_ID="m1_v7_d051_corrected_train_generation"
CPMT_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 2
CPMT_REPO_DIR="$(git -C "$CPMT_SCRIPT_DIR" rev-parse --show-toplevel)" || exit 2
export CPMT_ACCEPT_ONLY=0
if [[ "$#" -eq 1 && "$1" == "--accept-only" ]]; then
    export CPMT_ACCEPT_ONLY=1
elif [[ "$#" -ne 0 ]]; then
    printf 'Usage: bash ops/run_next_server_step.sh [--accept-only]\n'
    exit 2
fi
cd "$CPMT_REPO_DIR" || exit 2
[[ -d /root/autodl-tmp ]] || exit 2
[[ -z "$(git status --porcelain)" ]] || { printf 'SERVER_STEP_FAILED reason=checkout_not_clean\n'; exit 1; }
CPMT_SOURCE_SHORT="$(python -c 'import sys;sys.path.insert(0,"src");from cpmt.run_provenance import source_tree_sha256;from pathlib import Path;print(source_tree_sha256(Path.cwd(),roots=("src","scripts","configs","tests"))[:12])')" || exit 2
CPMT_OUTPUT_DIR="/root/autodl-tmp/cpmt_outputs/m1-v7-d051-train-$CPMT_SOURCE_SHORT"
mkdir -p "$CPMT_OUTPUT_DIR" || exit 2
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export CUDA_VISIBLE_DEVICES="" PYTHONUNBUFFERED=1
python - "$CPMT_OUTPUT_DIR" <<'PY_GENERATE' 2>&1 | tee -a "$CPMT_OUTPUT_DIR/generation.log"
import datetime,fcntl,hashlib,math,os,shutil,subprocess,sys,time,traceback
from pathlib import Path
sys.path.insert(0,'src')
from cpmt.m1_protocol import load_and_validate,protocol_sha256,validate_current_rollout_protocol
from cpmt.m1_s5_training import read_json,require,write_json
from cpmt.m1_scope_rebuild import validate_rebuild_test_marker
from cpmt.run_provenance import arrays_sha256,capture_run_provenance,source_tree_sha256

STAGE=os.environ['CPMT_SERVER_STEP_ID']
ROOT=Path.cwd()
OUT=Path(sys.argv[1])

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()

def resources():
    cpu=[float(len(os.sched_getaffinity(0)))];memory=[]
    mount=Path('/sys/fs/cgroup')
    relative=next((line.split(':',2)[2] for line in Path('/proc/self/cgroup').read_text().splitlines()
                   if line.startswith('0::')),'/')
    current=(mount/relative.lstrip('/')).resolve();folders=[mount]
    if current.is_relative_to(mount) and current.exists():
        folders += [current,*[p for p in current.parents if p.is_relative_to(mount)]]
    for folder in set(folders):
        quota=folder/'cpu.max'
        if quota.exists():
            value,period=quota.read_text().split()
            if value!='max': cpu.append(int(value)/int(period))
        limit,used=folder/'memory.max',folder/'memory.current'
        if limit.exists() and used.exists() and limit.read_text().strip()!='max':
            memory.append(max(0,int(limit.read_text())-int(used.read_text()))/2**30)
    quota,period=mount/'cpu/cpu.cfs_quota_us',mount/'cpu/cpu.cfs_period_us'
    if quota.exists() and period.exists() and int(quota.read_text())>0:
        cpu.append(int(quota.read_text())/int(period.read_text()))
    limit,used=mount/'memory/memory.limit_in_bytes',mount/'memory/memory.usage_in_bytes'
    if limit.exists() and used.exists():
        memory.append(max(0,int(limit.read_text())-int(used.read_text()))/2**30)
    memory.append(next(int(line.split()[1])/2**20 for line in Path('/proc/meminfo').read_text().splitlines()
                       if line.startswith('MemAvailable:')))
    available=min(memory);free=shutil.disk_usage(OUT).free/2**30
    workers=min(16,math.floor(min(cpu)),math.floor((available-4)/0.5))
    require(workers>=1 and available>=8 and free>=4,'insufficient CPU/memory/disk headroom; no generation started')
    return {'cpu_capacity':min(cpu),'available_memory_gib':available,'free_disk_gib':free,'workers':workers}

def validate_manifest_header(manifest,binding,hard):
    # The encoder excludes the last (future-less) step of each 20-step chain.
    # Per paired group: 2 * 19 reference learning rows + 2 recovery rows.
    # Keep the historical manifest field name; do not rewrite producer outputs.
    expected={'schema_version':'cpmt-m1-generation-manifest-v5','split':'train',
              'paired_groups_total':1000,'configured_paired_groups_for_split':1000,
              'protocol_sha256':binding['protocol_sha256'],'dataset_version':hard['data']['dataset_version'],
              'decisions':40000,'online_chain_decisions':38000,'recovery_training_examples':2000,
              'retained_shard_count':1000,'formal_run':False,'test_generated':False}
    mismatches={k:{'expected':v,'actual':manifest.get(k)} for k,v in expected.items() if manifest.get(k)!=v}
    require(not mismatches,'generation manifest binding/count mismatch: '+str(mismatches))

def validate_learning_counts(arrays,manifest):
    import numpy as np
    group=np.asarray(arrays['group']);recovery=np.asarray(arrays['recovery'])
    require(group.ndim==1 and group.dtype.kind in 'iu' and recovery.dtype.kind=='b'
            and recovery.shape==group.shape,'invalid group/recovery vectors')
    require(len(group)==len(arrays['y'])==manifest['decisions']==40000,'learning row count mismatch')
    require(np.all((group>=0)&(group<1000)),'train group index out of range')
    online=~recovery
    require(int(online.sum())==manifest['online_chain_decisions']==38000
            and int(recovery.sum())==manifest['recovery_training_examples']==2000,
            'reference-learning/recovery row count mismatch')
    require(np.array_equal(np.unique(group),np.arange(1000))
            and np.array_equal(np.bincount(group[online],minlength=1000),np.full(1000,38))
            and np.array_equal(np.bincount(group[recovery],minlength=1000),np.full(1000,2)),
            'incomplete paired train learning rows: expected 38 reference + 2 recovery per group')

def require_accept_only_prerequisites(out,accept_only):
    if accept_only:
        require((out/'attempt.json').exists() and (out/'runner_exit.json').exists(),
                'accept-only requires an existing attempt and runner exit; generation will not start')

def validate_family_support(arrays,manifest,hard):
    import numpy as np
    families=list(hard['data']['scenario_families'])
    require(manifest['configured_scenario_families']==families,'configured family order mismatch')
    causal=manifest['causal_paired_group_support_by_family']
    require(set(causal)==set(families) and all(v==1000 for v in causal.values()),
            'causal family coverage mismatch')
    group=np.asarray(arrays['group']);recovery=np.asarray(arrays['recovery']);online=~recovery
    codes=np.asarray(arrays['scenario_family_index'])
    require(codes.shape==group.shape and codes.dtype.kind in 'iu','invalid scenario family vector shape/dtype')
    # RECOVERY_RELINK is intentionally outside C00-C11; the production encoder
    # maps its family to -1. It must not enter ordinary-family coverage counts.
    require(np.all((codes[online]>=0)&(codes[online]<len(families))),
            'invalid ordinary scenario family codes: '+str(np.unique(codes[online]).tolist()))
    require(np.all(codes[recovery]==-1),
            'invalid recovery scenario family codes (expected -1): '+str(np.unique(codes[recovery]).tolist()))
    observed={family:int(len(np.unique(group[online & (codes==index)])))
              for index,family in enumerate(families)}
    # A family's only reference occurrence may be the omitted last step.
    # Learning coverage therefore need not be 1000; verify it against rows.
    require(observed==manifest['learning_group_support_by_family'],
            'learning family coverage differs from encoded rows: '+str(observed))

def accept(binding,hard,attempt):
    import numpy as np
    exit_record=read_json(OUT/'runner_exit.json')
    require(exit_record['binding']==binding and exit_record['exit_code']==0,'generation runner did not succeed')
    path=OUT/'train.npz';manifest_path=path.with_suffix('.manifest.json')
    manifest=read_json(manifest_path)
    validate_manifest_header(manifest,binding,hard)
    provenance=manifest['generation_provenance']
    require(provenance['git_dirty'] is False
            and provenance['git_commit']==attempt['provenance']['git_commit']
            and provenance['source_tree_sha256']==binding['source_tree_sha256'],'generation provenance mismatch')
    require(manifest['workers']==attempt['resources']['workers'],'worker count mismatch')
    require(manifest['teacher_health_gate']['applicable'] is True
            and manifest['teacher_health_gate']['pass'] is True,'train teacher health gate failed')
    shards=sorted((OUT/'shards').glob('*.npz'))
    require([p.name for p in shards]==[f'train_{i:06d}.npz' for i in range(1000)],'missing/unexpected shard')
    require(path.stat().st_size==manifest['merged_npz_bytes']
            and sum(p.stat().st_size for p in shards)==manifest['retained_shard_bytes'],'artifact size mismatch')
    with np.load(path,allow_pickle=False) as archive:
        arrays={key:archive[key] for key in archive.files}
    require(arrays_sha256(arrays)==manifest['arrays_digest'],'arrays digest mismatch')
    validate_learning_counts(arrays,manifest)
    validate_family_support(arrays,manifest,hard)
    require(source_tree_sha256(ROOT,roots=('src','scripts','configs','tests'))==binding['source_and_tests_sha256'],
            'source/tests changed during generation')
    return {'schema_version':'cpmt-scope-rebuild-train-v1','binding':binding,'exit_code':0,
            'arrays_path':str(path),'arrays_digest':manifest['arrays_digest'],'manifest':manifest,
            'file_sha256':{'train.npz':digest(path),'train.manifest.json':digest(manifest_path),
                           **{'shards/'+p.name:digest(p) for p in shards}},
            'validation_generated':False,'test_access':False,'training_performed':False,
            'attempt':attempt,'acceptance_provenance':capture_run_provenance(ROOT,component=STAGE,
                                                       entrypoint=ROOT/'ops/run_next_server_step.sh')}

def main():
    require_accept_only_prerequisites(OUT,os.environ['CPMT_ACCEPT_ONLY']=='1')
    plan=read_json(ROOT/'configs/m1_scope_rebuild_plan.json')
    hard_path=ROOT/plan['corrected_source']['path'];hard=load_and_validate(hard_path)
    validate_current_rollout_protocol(hard)
    require(plan['rebuild']['train_groups']==hard['data']['paired_groups']['train']==1000,'train group contract changed')
    source=source_tree_sha256(ROOT,roots=('src','scripts','configs','tests'))
    full_test=OUT.parent/('m1-v7-d051-full-test-'+source[:12])/'full_test.ok.json'
    validate_rebuild_test_marker(read_json(full_test),ROOT,plan,expected_tests=280)
    require(protocol_sha256(hard)==plan['corrected_source']['protocol_sha256'],'corrected protocol mismatch')
    provenance=capture_run_provenance(ROOT,component=STAGE,entrypoint=ROOT/'ops/run_next_server_step.sh')
    require(not provenance['git_dirty'],'checkout must be clean')
    binding={'stage':STAGE,'protocol_sha256':protocol_sha256(hard),'plan_sha256':protocol_sha256(plan),
             'source_tree_sha256':provenance['source_tree_sha256'],'source_and_tests_sha256':source,
             'full_test_marker':str(full_test),'full_test_marker_sha256':digest(full_test),
             'groups':1000,'split':'train','future_hash_bins':32}
    print('SERVER_STEP_BEGIN id='+STAGE+' commit='+provenance['git_commit'],flush=True)
    print('FULL_TEST_REUSED tests=280 marker='+str(full_test),flush=True)
    print('OUTPUT_DIR='+str(OUT)+' training=false validation=false test_access=false',flush=True)
    success=OUT/'generation.ok.json';attempt_path=OUT/'attempt.json'
    if success.exists():
        marker=read_json(success)
        require(marker['binding']==binding and marker['exit_code']==0,'success binding mismatch')
        for relative,expected in marker['file_sha256'].items():
            path=OUT/relative
            require(path.resolve().is_relative_to(OUT.resolve()) and digest(path)==expected,'retained artifact hash mismatch: '+relative)
        print('GENERATION_REUSED arrays_digest='+marker['arrays_digest'],flush=True)
    else:
        if attempt_path.exists():
            attempt=read_json(attempt_path)
            require(attempt['binding']==binding,'existing attempt binding mismatch')
            require((OUT/'runner_exit.json').exists(),'interrupted attempt requires review; no automatic restart')
            require(read_json(OUT/'runner_exit.json')['exit_code']==0,'failed generation requires review; no automatic restart')
            print('GENERATION_ACCEPT_ONLY runner already finished; no data regeneration',flush=True)
        else:
            require(not any((OUT/name).exists() for name in ('train.npz','train.manifest.json','shards','runner_exit.json')),
                    'unrecognized existing artifacts require review')
            machine=resources()
            print('GENERATION_RESOURCES='+str(machine),flush=True)
            command=[sys.executable,'scripts/generate_m1_parallel.py','--config',str(hard_path),
                     '--split','train','--paired-groups','1000','--future-hash-bins','32',
                     '--workers',str(machine['workers']),'--out',str(OUT/'train.npz'),'--shard-dir',str(OUT/'shards')]
            attempt={'binding':binding,'provenance':provenance,'resources':machine,'command':command}
            write_json(attempt_path,attempt)
            started=time.monotonic()
            code=subprocess.run(command,cwd=ROOT).returncode
            write_json(OUT/'runner_exit.json',{'binding':binding,'exit_code':code,'wall_seconds':time.monotonic()-started})
            print('GENERATION_RUN_EXIT='+str(code),flush=True)
            require(code==0,'generation failed; preserve outputs and review before next stage')
        marker=accept(binding,hard,attempt)
        write_json(success,marker)
        print('GENERATION_ACCEPTED groups=1000 learning_rows=40000 reference_learning_rows=38000 recovery_rows=2000 arrays_digest='+marker['arrays_digest'],flush=True)
    print('GENERATION_MARKER='+str(success),flush=True)
    print('NEXT=review_corrected_train_then_deliver_next_stage_separately',flush=True)
    print('SERVER_STEP_OK id='+STAGE,flush=True)

if __name__=='__main__':
    with (OUT/'generation.lock').open('a+') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            print('SERVER_STEP_BUSY id='+STAGE+' log='+str(OUT/'generation.log'),flush=True)
            raise SystemExit(3)
        try:
            main()
        except BaseException as error:
            stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            write_json(OUT/('generation.failed.'+stamp+'.json'),
                       {'type':type(error).__name__,'message':str(error),'traceback':traceback.format_exc()})
            print('SERVER_STEP_FAILED id='+STAGE+' reason='+str(error),flush=True)
            raise
PY_GENERATE
CPMT_EXITS=("${PIPESTATUS[@]}")
printf 'GENERATION_EXIT=%s LOG_WRITE_EXIT=%s\n' "${CPMT_EXITS[0]}" "${CPMT_EXITS[1]}"
[[ "${CPMT_EXITS[0]}" -eq 0 && "${CPMT_EXITS[1]}" -eq 0 ]]
