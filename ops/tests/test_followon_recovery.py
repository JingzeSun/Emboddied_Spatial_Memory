"""Failure-shape and adoption guards; no server data or training."""
from pathlib import Path
import sys
import tempfile
import unittest
import gzip
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'ops'),str(ROOT/'scripts'),str(ROOT/'src')]
import m1_followon_recovery as repair
import m1_corrected_followon as followon
from cpmt.m1_s5_training import write_json
from cpmt.run_provenance import file_sha256


class TestFollowonRecovery(unittest.TestCase):
    def fixture(self,root,content=b''):
        partial=root/'run/interfaces/architecture/method/.serial.incomplete';partial.mkdir(parents=True)
        write_json(partial/'failure.json',{'type':'ValueError','message':'missing/duplicate sibling pair'})
        with gzip.open(partial/'execution.jsonl.gz','wb') as stream:stream.write(content)
        (root/'interfaces.log').write_text('original traceback',encoding='utf-8')
        return partial

    def test_only_empty_execution_failure_can_be_adopted(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);partial=self.fixture(p)
            self.assertEqual(repair.verify_failure(p)['execution_records'],0)
            with gzip.open(partial/'execution.jsonl.gz','wb') as stream:stream.write(b'actual execution')
            with self.assertRaisesRegex(ValueError,'execution already'):repair.verify_failure(p)

    def test_different_failure_or_later_training_is_not_adopted(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);partial=self.fixture(p)
            write_json(p/'budget.attempt.json',{})
            with self.assertRaisesRegex(ValueError,'later work'):repair.verify_failure(p)
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);partial=self.fixture(p)
            write_json(partial/'failure.json',{'type':'ValueError','message':'different issue'})
            with self.assertRaisesRegex(ValueError,'different failure'):repair.verify_failure(p)

    def test_old_gpu_source_requires_explicit_verified_adoption(self):
        data={'full_test':{'exit_code':0},'completion':{'exit_code':0},
            'report':{'pass':True,'binding':{'source_and_tests_sha256':'old'}}}
        with patch.object(followon,'read_json',return_value=data),\
             patch.object(repair,'verify_adoption',side_effect=ValueError('unverified bridge')) as verify:
            with self.assertRaisesRegex(ValueError,'unverified bridge'):
                followon.prerequisite(Path('stage'),'prepare',{'source_and_tests_sha256':'new'})
            verify.assert_called_once()

    def test_adoption_requires_fresh_full_test_not_old_test(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);binding={'source_and_tests_sha256':'new'}
            write_json(p/'test.completed.json',{'binding':{'old':True},'exit_code':0})
            with patch.object(repair,'test_binding',return_value={'new':True}):
                with self.assertRaisesRegex(ValueError,'fresh repair full test'):repair.adopt(p,binding)
            self.assertFalse((p/'adopt.attempt.json').exists())

    def test_verification_detects_changed_reused_artifact(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);(p/'test.log').write_text('ok');(p/'artifact.json').write_text('{}')
            binding={'source':'new'};delta={'old':'old','new':'new'}
            tested={'binding':{'test':'new'},'exit_code':0,'errors':0,'failures':0,'skipped':0,
                'log_sha256':file_sha256(p/'test.log')}
            write_json(p/'test.completed.json',tested)
            write_json(p/'adoption.json',{'binding':binding,'transition':delta,'pass':True,'repair_full_test':tested,
                'repair_test_sha256':file_sha256(p/'test.completed.json'),'input_exports':{},
                'new_artifacts':{'artifact.json':file_sha256(p/'artifact.json')}})
            with patch.object(repair,'transition',return_value=delta),patch.object(repair,'test_binding',return_value={'test':'new'}):
                repair.verify_adoption(p,binding)
                (p/'artifact.json').write_text('{"changed":true}')
                with self.assertRaisesRegex(ValueError,'artifact changed'):repair.verify_adoption(p,binding)


if __name__=='__main__':unittest.main()
