"""Operations regressions with temporary receipts; never start server work."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'ops'),str(ROOT/'scripts'),str(ROOT/'src')]
import m1_corrected_followon as ops
from cpmt.m1_s5_training import write_json
from cpmt.run_provenance import file_sha256


class TestFollowonDelivery(unittest.TestCase):
    def test_refit_estimate_uses_sixty_selected_paths_and_four_workers(self):
        from m1_corrected_training_plan import ARCHES, METHODS, SEEDS
        selected={a:{m:{'learning_rate':.0006,'steps':1000,'auxiliary_weight':1.}
            for m in ['outcome_scorer',*METHODS]} for a in ARCHES}
        rows={};artifacts={}
        for a in ARCHES:
            for m in ['outcome_scorer',*METHODS]:
                for s in SEEDS:
                    key=f'{a}/{m}/{s}';artifacts[key]=key
                    rows[str(Path(key)/'result.json')]={'wall_seconds':100.,'binding':{'job':{
                        'architecture':a,'method':m,'seed':s,'learning_rate':.0006,'auxiliary_weight':1.,'checkpoints':[300,1000,3000,10000]}}}
        report={'selected':selected,'artifacts':artifacts}
        def read(path):return report if path.name=='budget.report.json' else rows[str(path)]
        with patch.object(ops,'read_json',side_effect=read):
            value=ops.refit_runtime_estimate(Path('stage'))
        self.assertAlmostEqual(value,60/4*100*.28*(1000/799)*1.2)
        self.assertLess(value,1800)

    def test_success_reuses_without_subprocess(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);(p/'capacity.log').write_text('ok');b={'source':'x'}
            write_json(p/'capacity.completed.json',{'binding':b,'exit_code':0,
                'result_files':{},'log_sha256':file_sha256(p/'capacity.log')})
            with patch.object(ops,'prerequisite'),patch.object(ops,'command') as run:
                self.assertEqual(ops.run_step(p,'capacity',b),0);run.assert_not_called()

    def test_failed_stage_is_not_restarted(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);(p/'capacity.log').write_text('failed');b={'source':'x'}
            write_json(p/'capacity.completed.json',{'binding':b,'exit_code':1,
                'result_files':{},'log_sha256':file_sha256(p/'capacity.log')})
            with patch.object(ops,'prerequisite'),patch.object(ops,'command') as run:
                self.assertEqual(ops.run_step(p,'capacity',b),1);run.assert_not_called()

    def test_interrupted_stage_is_not_restarted(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);write_json(p/'capacity.attempt.json',{})
            with patch.object(ops,'prerequisite'),patch.object(ops,'command') as run:
                with self.assertRaisesRegex(ValueError,'incomplete attempt'):ops.run_step(p,'capacity',{})
                run.assert_not_called()

    def test_failed_check_exports_without_success_report(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);(p/'run').mkdir();(p/'results').mkdir();(p/'capacity.log').write_text('preserved failure')
            b={'source':'x'};write_json(p/'capacity.completed.json',{'binding':b,'exit_code':1,
                'result_files':{},'log_sha256':file_sha256(p/'capacity.log')})
            with patch.object(ops,'ROOT',p):
                self.assertEqual(ops.export(p,'checks',b),0)
                exported=ops.read_json(p/ops.EXPORTS['checks']);self.assertFalse(exported['pass'])
                self.assertEqual(ops.export(p,'checks',b),0)

    def test_changed_completed_report_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);(p/'run').mkdir();(p/'capacity.log').write_text('ok');b={'source':'x'}
            write_json(p/'run/capacity.report.json',{'pass':True})
            write_json(p/'capacity.completed.json',{'binding':b,'exit_code':0,
                'result_files':{'capacity.report.json':file_sha256(p/'run/capacity.report.json')},
                'log_sha256':file_sha256(p/'capacity.log')})
            write_json(p/'run/capacity.report.json',{'pass':False})
            with self.assertRaisesRegex(ValueError,'report changed'):ops.verify_step(p,'capacity',b)

    def test_early_export_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);(p/'prepare.log').write_text('ok');b={}
            write_json(p/'prepare.completed.json',{'binding':b,'exit_code':0,'result_files':{},'log_sha256':file_sha256(p/'prepare.log')})
            with self.assertRaisesRegex(ValueError,'not complete'):ops.export(p,'checks',b)


if __name__=='__main__':unittest.main()
