"""Tiny disk fixtures only: no model imports, generation, or validation data."""
import copy
import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('case_export', Path(__file__).parents[1] / 'export_m1_s5_case.py')
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class CaseExportTests(unittest.TestCase):
    def fixture(self, root):
        audit_path = root / 'audits.json.gz'
        pair = [{'paired_group_id': mod.GROUP, 'sibling_index': s, 'steps': [{}] * 20} for s in (0, 1)]
        audit_path.write_bytes(gzip.compress(json.dumps(pair).encode()))
        audit = {'path': str(audit_path), 'sha256': mod.digest(audit_path.read_bytes()), 'paired_group_id': mod.GROUP}
        models = {}
        for seed in (7, 19, 31, 43, 59):
            for method in mod.METHODS:
                key = f'{seed}_{method}'
                metrics = [{'paired_group_id': mod.GROUP, 'sibling_index': s, 'sequence_id': f'group69:s{s}'} for s in (0, 1)]
                model = {'architecture': mod.ARCH, 'seed': seed, 'method': method, 'metrics': metrics,
                         'model_sha256': 'fake-model', 'evaluation': {'shards': []}}
                models[key] = model
                if seed not in (7, 19):
                    continue
                path = root / key
                path.mkdir()
                sequences, records = [], []
                for s in (0, 1):
                    choices = [{'step_index': t, 'base_graph_hash': f'{s}-{t}', 'post_graph_hash': f'{s}-{t+1}'} for t in range(20)]
                    sequences.append({'metrics': metrics[s], 'choices': choices})
                    records.extend({'choice': c, 'materialized': {'audit_sibling_index': s, 'audit_sequence_id': metrics[s]['sequence_id']},
                                    'current': {'graph_hash': c['post_graph_hash']}} for c in choices)
                binding = {'audit': audit}
                (path / 'result.json').write_text(json.dumps({'binding': binding, 'sequences': sequences}))
                (path / 'execution.jsonl.gz').write_bytes(gzip.compress(('\n'.join(json.dumps(r) for r in records)).encode()))
                marker = {'schema_version': 'cpmt-s5-unit-v1', 'binding': binding,
                          'files': {p.name: mod.digest(p.read_bytes()) for p in path.iterdir()}}
                (path / 'complete.json').write_text(json.dumps(marker))
                model['evaluation']['shards'] = [{'path': str(path), 'paired_group_id': mod.GROUP,
                                                  'marker_sha256': mod.digest((path / 'complete.json').read_bytes())}]
        return {'engineering_pass': True, 'test_access': False, 'report': {'per_model': models}, 'binding': {'science': {}}}

    def test_complete_extraction_roundtrip_and_reuse(self):
        import base64
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = mod.extract(self.fixture(root))
            self.assertEqual(result['counts'], {'units': 4, 'sequences': 8, 'decisions': 160})
            for unit in result['units']:
                for name, blob in unit['files'].items():
                    restored = gzip.decompress(base64.b64decode(blob['payload']))
                    self.assertEqual(restored, (Path(unit['source']['path']) / name).read_bytes())
            output = root / 'out.json'
            self.assertEqual(mod.write_once(output, b'one'), 'VERIFIED')
            self.assertEqual(mod.write_once(output, b'one'), 'REUSED')
            with self.assertRaisesRegex(ValueError, 'preserved'):
                mod.write_once(output, b'two')
            self.assertEqual(output.read_bytes(), b'one')

    def test_tamper_and_report_pair_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.fixture(root)
            changed = copy.deepcopy(report)
            changed['report']['per_model']['7_cpmt_ctl_core']['metrics'][0]['sequence_id'] = 'wrong'
            with self.assertRaisesRegex(ValueError, 'metrics differ'):
                mod.extract(changed)
            path = Path(report['report']['per_model']['7_cpmt_ctl_core']['evaluation']['shards'][0]['path'])
            (path / 'execution.jsonl.gz').write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'file changed'):
                mod.extract(report)

    def test_incomplete_execution_rejected_even_with_consistent_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self.fixture(Path(tmp))
            spec = report['report']['per_model']['7_cpmt_ctl_core']['evaluation']['shards'][0]
            path = Path(spec['path'])
            execution = path / 'execution.jsonl.gz'
            lines = gzip.decompress(execution.read_bytes()).splitlines()
            execution.write_bytes(gzip.compress(b'\n'.join(lines[:-1])))
            marker = json.loads((path / 'complete.json').read_bytes())
            marker['files'][execution.name] = mod.digest(execution.read_bytes())
            (path / 'complete.json').write_text(json.dumps(marker))
            spec['marker_sha256'] = mod.digest((path / 'complete.json').read_bytes())
            with self.assertRaisesRegex(ValueError, '40 recorded'):
                mod.extract(report)


if __name__ == '__main__':
    unittest.main()
