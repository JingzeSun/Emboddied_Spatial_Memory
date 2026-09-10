from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'ops'),str(ROOT/'scripts'),str(ROOT/'src')]
import m1_corrected_confirmation as ops
from cpmt.m1_s5_training import write_json,read_json
from cpmt.run_provenance import file_sha256


class TestConfirmationDelivery(unittest.TestCase):
    def test_global_reservation_reuses_same_binding_rejects_new_directory_or_source(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(ops,'OUTPUT_ROOT',Path(tmp)):
            stage=Path(tmp)/'stage';value=ops.reserve_generation(stage,{'source':'a'})
            self.assertEqual(value,ops.reserve_generation(stage,{'source':'a'}))
            with self.assertRaises(ValueError):ops.reserve_generation(Path(tmp)/'other',{'source':'a'})
            with self.assertRaises(ValueError):ops.reserve_generation(stage,{'source':'b'})

    def test_success_reuses_and_failure_does_not_restart(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(ops,'prerequisites'),patch.object(ops,'command') as command:
            p=Path(tmp);binding={'source':'fixed'};(p/'smoke.log').write_text('done')
            write_json(p/'smoke.completed.json',{'binding':binding,'exit_code':1,'log_sha256':file_sha256(p/'smoke.log'),'result_files':{}})
            self.assertEqual(ops.run_step(p,'smoke',binding),1);command.assert_not_called()

    def test_partial_step_is_not_silently_restarted(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(ops,'prerequisites'),patch.object(ops,'command') as command:
            p=Path(tmp);write_json(p/'generate.attempt.json',{})
            with self.assertRaisesRegex(ValueError,'interrupted'):ops.run_step(p,'generate',{})
            command.assert_not_called()

    def test_export_cannot_treat_launch_as_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'missing step'):ops.export(Path(tmp),'confirmation',{})

    def test_dependency_requires_current_full_test(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);write_json(p/'test.completed.json',{'binding':{'old':1},'exit_code':0})
            with self.assertRaisesRegex(ValueError,'full tests'):ops.prerequisites(p,'prepare',{'new':1})

    def test_compact_export_preserves_report_and_reuses_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'results').mkdir();p=root/'stage';(p/'run').mkdir(parents=True)
            for action in ['prepare','smoke','generate']:write_json(p/f'{action}.completed.json',{})
            write_json(p/'test.completed.json',{'exit_code':0})
            report={'groups':[{'index':4,'metrics':{'value':.125}}],'test_access':False}
            write_json(p/'run/data_manifest.json',report)
            with patch.object(ops,'ROOT',root),patch.object(ops,'verify_step',return_value={'exit_code':0}):
                self.assertEqual(ops.export(p,'data',{}),0)
                path=root/ops.EXPORTS['data'];before=path.read_bytes()
                self.assertEqual(read_json(path)['report'],report);self.assertEqual(before.count(b'\n'),1)
                self.assertEqual(ops.export(p,'data',{}),0);self.assertEqual(path.read_bytes(),before)
                write_json(p/'run/data_manifest.json',{'changed':True})
                with self.assertRaisesRegex(ValueError,'different export'):ops.export(p,'data',{})


if __name__=='__main__':unittest.main()
