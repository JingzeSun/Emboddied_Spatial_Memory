"""One bounded iterator repair: verify old successes, retain the failed run.

No old marker is rewritten and no GPU training is executed. Adoption needs a
fresh full test and a checked, evaluation-only source transition from ef210c0.
"""
from __future__ import annotations
import ast
from copy import deepcopy
import gzip
import hashlib
import io
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts'), str(ROOT / 'ops')]
from cpmt.m1_s5_training import read_json, write_json, require
from cpmt.m1_s5_confirmation import complete_unit, verify_unit
from cpmt.run_provenance import file_sha256, source_tree_sha256
from m1_candidate_availability import run_test
from m1_corrected_training_plan import consume_probe, consume_process_check, input_spec, CHECK_EXPORT
from run_m1_corrected_followon import immutable_json, completed_paths

BASE = 'ef210c0'
ROOTS = ('src', 'scripts', 'configs', 'tests')
EVALUATOR = 'scripts/m1_paired_evaluation.py'
NEW_TEST = 'tests/test_m1_audit_iteration.py'
CLASS_SOURCE = '''class ReplayableAudits:
    """Each traversal reopens the bound shards; only one pair stays in memory."""
    def __init__(self, specs):
        self.specs = tuple(dict(spec) for spec in specs)
    def __iter__(self):
        for spec in self.specs:
            yield from read_audits(spec)
'''


def historical_files(root=ROOT):
    raw = subprocess.check_output(['git', 'archive', BASE, *ROOTS], cwd=root)
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        return {m.name: archive.extractfile(m).read() for m in archive.getmembers() if m.isfile()}


def linux_tree_hash(files):
    digest = hashlib.sha256()
    for name, blob in sorted(files.items()):
        data = blob.replace(b'\r\n', b'\n')
        if name.endswith('.ps1'): data = data.replace(b'\n', b'\r\n')
        digest.update(name.encode() + b'\0' + data + b'\0')
    return digest.hexdigest()


def verify_iterator_delta(before, after):
    old, new = ast.parse(before), ast.parse(after)
    classes = [n for n in new.body if isinstance(n, ast.ClassDef) and n.name == 'ReplayableAudits']
    require(len(classes) == 1 and ast.dump(classes[0]) == ast.dump(ast.parse(CLASS_SOURCE).body[0]), 'unreviewed reader class')
    new.body.remove(classes[0])
    class ReplaceIterator(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            if node.name == 'audits': return None
            return self.generic_visit(node)
        def visit_Call(self, node):
            if isinstance(node.func, ast.Name) and node.func.id == 'audits':
                return ast.Call(func=ast.Name(id='ReplayableAudits', ctx=ast.Load()),
                    args=[ast.Name(id='specs', ctx=ast.Load())], keywords=[])
            return self.generic_visit(node)
    # Transform only run_serial, so changes in any other scientific function fail.
    for i,node in enumerate(old.body):
        if isinstance(node, ast.FunctionDef) and node.name == 'run_serial':
            old.body[i] = ReplaceIterator().visit(node)
    require(ast.dump(old) == ast.dump(new), 'source delta exceeds the reviewed iterator repair')


def transition(root=ROOT):
    old = historical_files(root)
    listed = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '--', *ROOTS], cwd=root, text=True).splitlines()
    require(set(listed) == set(old) | {NEW_TEST}, 'unexpected source/test file set in repair')
    for name, blob in old.items():
        current = (root / name).read_bytes()
        if name == EVALUATOR: verify_iterator_delta(blob.decode('utf-8'), current.decode('utf-8'))
        else: require(blob.replace(b'\r\n', b'\n') == current.replace(b'\r\n', b'\n'), 'non-evaluation source changed: ' + name)
    old_hash = linux_tree_hash(old)
    require(old_hash.startswith('cc2d5e2113ed'), 'unexpected historical source hash')
    return {'base_commit': subprocess.check_output(['git', 'rev-parse', BASE], cwd=root, text=True).strip(),
        'previous_source_and_tests_sha256': old_hash,
        'source_and_tests_sha256': source_tree_sha256(root, roots=ROOTS),
        'scientific_delta': 'one_shot_iterator_to_repeatable_disk_reader_only',
        'training_code_data_and_recipes_unchanged': True,
        'evaluator_sha256': file_sha256(root / EVALUATOR), 'new_test_sha256': file_sha256(root / NEW_TEST)}


def test_binding(binding):
    return {'followon': binding, 'transition': transition(), 'repair_ops_sha256': file_sha256(Path(__file__))}


def repair_test(stage, binding):
    return run_test(stage, test_binding(binding))


def verify_adoption(stage, binding):
    receipt = read_json(stage / 'adoption.json')
    require(receipt['pass'] and receipt['binding'] == binding and receipt['transition'] == transition(), 'adoption source changed')
    tested = read_json(stage / 'test.completed.json')
    require(tested['binding'] == test_binding(binding) and tested['exit_code'] == 0
        and not any(tested[k] for k in ['errors', 'failures', 'skipped']), 'repair full test did not pass')
    require(file_sha256(stage / 'test.log') == tested['log_sha256'], 'repair test log changed')
    require(file_sha256(stage / 'test.completed.json') == receipt['repair_test_sha256'], 'repair test receipt changed')
    require(receipt['repair_full_test'] == tested, 'adopted full test differs')
    for name, digest in receipt['input_exports'].items(): require(file_sha256(ROOT / name) == digest, 'adopted export changed')
    for name, digest in receipt['new_artifacts'].items(): require(file_sha256(stage / name) == digest, 'adopted artifact changed')
    return receipt


def verify_failure(old):
    require(not any((old / f'{a}.{suffix}.json').exists() for a in ['budget', 'refit'] for suffix in ['attempt', 'launch', 'completed']), 'later work already started; repair is not applicable')
    failures = list((old / 'run/interfaces').rglob('failure.json'))
    require(len(failures) == 1, 'unexpected interface failure inventory')
    failure = read_json(failures[0])
    require(failure == {'type': 'ValueError', 'message': 'missing/duplicate sibling pair'}, 'different failure needs review')
    require(failures[0].parent.name == '.serial.incomplete', 'failure was not initial serial reader')
    with gzip.open(failures[0].parent / 'execution.jsonl.gz', 'rb') as stream:
        require(stream.read(1) == b'', 'execution already occurred; expected exhausted iterator')
    require(not list((old / 'run/interfaces').rglob('complete.json')), 'unexpected completed interface work')
    return {'failure': failure, 'execution_records': 0,
        'log_tail': (old / 'interfaces.log').read_text(encoding='utf-8').splitlines()[-80:]}


def adopt(stage, binding):
    from m1_corrected_followon import verify_step
    if (stage / 'adoption.json').exists():
        verify_adoption(stage, binding)
        print('FOLLOWON_ADOPTION_REUSED no training or regeneration', flush=True)
        return 0
    checked = read_json(stage / 'test.completed.json')
    require(checked['binding'] == test_binding(binding) and checked['exit_code'] == 0
        and not any(checked[k] for k in ['errors', 'failures', 'skipped']), 'fresh repair full test must pass')
    require(file_sha256(stage / 'test.log') == checked['log_sha256'], 'repair test log changed')
    delta = transition(); old_source = delta['previous_source_and_tests_sha256']
    old = stage.parent / ('m1-v7-d054-followon-' + old_source[:12])
    require(old.resolve() != stage.resolve() and old.is_dir(), 'original failed directory missing')
    require(not (stage / 'adopt.attempt.json').exists(), 'partial adoption retained; review required')
    # Read-only inspection of the exact previous run, while holding its lock.
    import fcntl
    with (old / 'phase.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        old_ops = read_json(old / 'prepare.completed.json')['binding']
        require(old_ops['source_and_tests_sha256'] == old_source, 'wrong prior run')
        for key, name in [('ops_sha256','ops/m1_corrected_followon.py'), ('shell_sha256','ops/m1_corrected_followon.sh')]:
            blob = subprocess.check_output(['git','show',f'{BASE}:{name}'],cwd=ROOT).replace(b'\r\n',b'\n')
            require(old_ops[key] == hashlib.sha256(blob).hexdigest(), 'prior operations version changed')
        for action in ['prepare','capacity']:
            require(verify_step(old, action, old_ops)['exit_code'] == 0, 'old prerequisite not successful')
        require(verify_step(old, 'interfaces', old_ops)['exit_code'] != 0, 'expected failed interface stage')
        failure = verify_failure(old)
        exported, registered = consume_probe()
        consume_process_check(old_source)  # Recheck the real old GPU pairs, not a fabricated new-source report.
        old_binding = read_json(old / 'run/binding.json')
        require(old_binding['source_and_tests_sha256'] == old_source and old_binding['input'] == input_spec()
            and old_binding['registration'] == registered, 'old input or registration changed')
        for name, digest in old_binding['input_exports'].items(): require(file_sha256(ROOT / name) == digest, 'original export changed')
        verify_unit(old / 'run/prepared', old_binding)
        capacity_paths = completed_paths(old / 'run', 'capacity')
        require(capacity_paths and len(capacity_paths['artifacts']) == 4, 'missing capacity jobs')
        from m1_corrected_training_plan import validate_recipe
        validate_recipe(read_json(old / 'run/capacity.recipe.json'))
        capacity = read_json(old / 'run/capacity.report.json')
        require(capacity['pass'] and capacity['source_and_tests_sha256'] == old_source
            and capacity['workers'] == 4 and capacity['steps'] == 2 and capacity['train_groups'] == 1000, 'capacity evidence invalid')
        inventory = {str(p.relative_to(old)): file_sha256(p) for p in sorted(old.rglob('*')) if p.is_file() and p.name != 'phase.lock'}
        # Only after all reuse evidence passes, write new verification receipts.
        write_json(stage / 'adopt.attempt.json', {'binding':binding, 'transition':delta})
        new_binding = {**old_binding, 'source_and_tests_sha256': delta['source_and_tests_sha256'],
            'verified_reuse': {'previous_run':str(old), 'previous_source_and_tests_sha256':old_source,
                'reason':'training_and_capacity_paths_unchanged_by_iterator_repair'}}
        run = stage / 'run';run.mkdir(parents=True,exist_ok=True)
        immutable_json(run / 'binding.json', new_binding)
        prepared = read_json(old / 'run/prepared/report.json')
        adopted_prepared = {**prepared, 'source_and_tests_sha256':delta['source_and_tests_sha256'],
            'execution_source_and_tests_sha256':old_source, 'role':'verified_reuse_not_reexecution'}
        complete_unit(run / 'prepared',new_binding,lambda p:write_json(p / 'report.json',adopted_prepared))
        immutable_json(run / 'capacity.report.json',{**capacity,
            'adoption': {'verification_source_and_tests_sha256':delta['source_and_tests_sha256'],
                'original_report_path':str(old / 'run/capacity.report.json'), 'original_report_sha256':file_sha256(old / 'run/capacity.report.json'),
                'role':'original_execution_reused_not_repeated'}})
        for action,names in [('prepare',['binding.json','prepared/report.json']),('capacity',['capacity.report.json'])]:
            log = stage / f'{action}.log'
            log.write_text(f'ADOPTED_SUCCESS action={action} original={old} no_execution=true\n',encoding='utf-8')
            write_json(stage / f'{action}.completed.json',{'binding':binding,'exit_code':0,'wall_seconds':0.0,
                'role':'verified_reuse_not_reexecution','execution_source_and_tests_sha256':old_source,
                'original_completion_sha256':file_sha256(old / f'{action}.completed.json'),
                'result_files':{n:file_sha256(run / n) for n in names},'log_sha256':file_sha256(log)})
        new_files = {str(p.relative_to(stage)):file_sha256(p) for p in sorted(run.rglob('*')) if p.is_file()}
        for a in ['prepare','capacity']:
            for suffix in ['.log','.completed.json']:new_files[a+suffix]=file_sha256(stage / (a+suffix))
        write_json(stage / 'adoption.json',{'binding':binding,'transition':delta,'pass':True,
            'repair_test_sha256':file_sha256(stage / 'test.completed.json'),'repair_full_test':checked,
            'input_exports':old_binding['input_exports'],'original_directory':str(old),'original_files':inventory,
            'original_failure':failure,'new_artifacts':new_files,
            'gpu_training_repeated':False,'capacity_training_repeated':False,'probe_repeated':False,
            'validation_access':False,'test_access':False})
        require(all(file_sha256(old / n)==h for n,h in inventory.items()), 'old evidence changed during adoption')
    verify_adoption(stage,binding)
    print('FOLLOWON_ADOPTION_OK gpu_check_reused=true capacity_reused=true original_failure_preserved=true',flush=True)
    print('NEXT=bash ops/m1_corrected_followon.sh interfaces',flush=True)
    return 0
