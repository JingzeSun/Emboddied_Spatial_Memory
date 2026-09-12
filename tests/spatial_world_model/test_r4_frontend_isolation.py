"""Server-only regression checks for the v2r1 public process read boundary."""
import ast
from pathlib import Path
import unittest

import r4_frontend_stage_v2r1 as stage


class IsolationTests(unittest.TestCase):
    def test_public_guard_allows_only_registered_public_original_files(self):
        self.assertEqual(len(stage.CFG['public_registration']),16)
        for name in stage.CFG['public_registration']:
            stage.public_read_guard('open',(str(stage.SOURCE/name),'rb',0))
        for name in stage.CFG['truth_registration']:
            with self.assertRaises(ValueError):
                stage.public_read_guard('open',(str(stage.SOURCE/name),'rb',0))

    def test_source_metadata_has_no_private_values_or_unregistered_paths(self):
        merged={**stage.CFG['public_registration'],**stage.CFG['truth_registration']}
        self.assertEqual(len(merged),320)
        self.assertTrue(all(set(v)=={'bytes','sha256'} for v in merged.values()))
        with self.assertRaises(ValueError):stage.public_read_guard('open',(str(stage.SOURCE/'run_receipt.json'),'rb',0))

    def test_parent_report_function_is_digest_only(self):
        tree=ast.parse(Path(stage.__file__).read_text())
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='verify_parent_bytes')
        calls={ast.unparse(n.func) for n in ast.walk(function) if isinstance(n,ast.Call)}
        self.assertEqual(calls,{'record','require'})
        self.assertFalse(any(isinstance(n,ast.Name) and n.id=='parent' for n in ast.walk(tree)))
