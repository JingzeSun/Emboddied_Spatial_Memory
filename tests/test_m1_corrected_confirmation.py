"""Small metadata/writer regressions; no real data generation or model training."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts'),str(ROOT/'ops')]
import m1_corrected_confirmation_plan as plan
import run_m1_corrected_confirmation as runner
from cpmt.m1_s5_training import read_json,write_json
from cpmt.run_provenance import file_sha256
from test_m1_audit_iteration import pair,row


class TestCorrectedConfirmation(unittest.TestCase):
    def test_frozen_plan_and_no_test_or_selection(self):
        original=read_json(ROOT/plan.PLAN);plan.validate_plan(original)
        changes={'indices':list(range(200)),'test_access':True,'model_selection_performed':True,
                 'seeds':[7],'horizon':1,'evaluation_workers':8,'smoke_train_group':78,'commit_probability':.5}
        for k,v in changes.items():
            bad=deepcopy(original);bad[k]=v
            with self.subTest(k=k),self.assertRaises(ValueError):plan.validate_plan(bad)

    def test_existing_algorithms_are_unchanged(self):
        result=plan.source_bridge();self.assertTrue(result['existing_algorithms_unchanged'])
        self.assertGreater(result['verified_existing_files'],50)

    def test_actual_exports_form_exact_registered_sixty_model_matrix(self):
        p=read_json(ROOT/plan.PLAN)
        exports={k:read_json(ROOT/v['path']) for k,v in p['input_exports'].items()}
        self.assertEqual(plan.validate_exports(exports,p)['trained_models'],60)
        broken=deepcopy(exports);model=next(iter(broken['refit']['reports']['refit']['models'].values()))
        model['checkpoint']+=1
        with self.assertRaisesRegex(ValueError,'recipe'):plan.validate_exports(broken,p)

    def test_generation_rejects_test_and_replacement_groups_before_generator(self):
        with patch.object(runner,'generate_m1_paired_rollout_split') as called:
            for split,index in [('test',4),('validation',0),('validation',204),('train',78)]:
                with self.assertRaises(ValueError):runner.make_group(('unused','unused',split,index,{}))
            called.assert_not_called()

    def test_new_writer_and_reader_reuse_complete_pair_and_reject_mutation(self):
        audits=pair('rollout-pair:train:000001')
        for audit in audits:
            for step in audit['steps']:
                step['scenario_family']='C00';step['executed_candidates'][0].update(legal=True,static_preflight_pass=True,post_graph={})
        arrays={'y':np.zeros(40,dtype=np.int64),'group':np.zeros(40,dtype=np.int64),
                'recovery':np.array([False]*38+[True]*2)}
        with tempfile.TemporaryDirectory() as tmp,patch.object(runner,'load_and_validate',return_value={}),\
             patch.object(runner,'generate_m1_paired_rollout_split',return_value=(None,audits,{})) as generated,\
             patch.object(runner,'rollout_learning_arrays_from_audits',return_value=arrays),patch.object(runner,'validate_graph'):
            task=('unused',tmp,'train',1,{'source':'fixed'})
            made=runner.make_group(task);self.assertEqual(runner.make_group(task),made);self.assertEqual(generated.call_count,1)
            specs,loaded=runner.read_groups([made],{'source':'fixed'},'train')
            self.assertEqual(len(list(runner.ReplayableAudits(specs))),2)
            self.assertEqual(set(loaded['group']),{1})
            with (Path(made['path'])/'audits.json.gz').open('ab') as f:f.write(b'tampered')
            with self.assertRaises(ValueError):runner.read_groups([made],{'source':'fixed'},'train')

    def test_oracle_wrapper_supports_repeated_reads_and_preserves_f_failure(self):
        g='rollout-pair:train:000001';pairs=pair(g);rows=[row(g,s) for s in [0,1]]
        for r in rows:r['metrics'].update(runner.F_REQUIRED)
        passes=[]
        def fake(model,audits,config,**kwargs):
            passes.extend([list(audits),list(audits),list(audits)])
            self.assertTrue(kwargs['oracle']);self.assertFalse(kwargs['observable_oracle'])
            return {'p95_forward_latency_ms':0},rows
        with tempfile.TemporaryDirectory() as tmp,patch('m1_paired_evaluation.read_audits',return_value=pairs),\
             patch.object(runner,'causal_rollout_metrics',side_effect=fake):
            task=(str(Path(tmp)/'unit'),{}, {'paired_group_id':g},'oracle_candidate_program',{})
            runner.run_oracle(task);self.assertEqual([len(p) for p in passes],[2,2,2])
            rows[0]['metrics']['final_active_graph_correctness']=0
            bad=(str(Path(tmp)/'bad'),*task[1:])
            with self.assertRaisesRegex(ValueError,'F integrity'):runner.run_oracle(bad)
            self.assertTrue((Path(tmp)/'.bad.incomplete/failure.json').is_file())

    def test_current_policy_overrides_saved_checkpoint_policy(self):
        hard=read_json(ROOT/'configs/m1_hard_condition_v7.json');p=read_json(ROOT/plan.PLAN)
        policy=read_json(ROOT/'configs/m1_candidate_availability_policy.json')
        with patch.object(runner,'contracts',return_value=(hard,{},{})):
            actual=runner.config_for({'plan':p,'registration':{'candidate_availability_policy':policy}},
                {'candidate_availability_policy':{'invalid':True},'device':'cuda'})
        self.assertEqual(actual['candidate_availability_policy'],policy);self.assertEqual(actual['device'],'cpu')

    def test_health_does_not_replace_or_hide_failed_family(self):
        hard={'data':{'scenario_families':['C00']},'candidates':{'coverage_gate_overall':1,'coverage_gate_each_family':1},
              'energy':{'teacher_health_gate':{'reference_agreement_overall_minimum':.9,'reference_agreement_each_family_minimum':.8}}}
        summary={'invariant_violations':0,'coverage':{'C00':{'decisions':40,'covered':40}},
            'generator_summary':{'teacher_reference_agreement_by_family':{'C00':{'support':38,'reference_agreement':.5}}}}
        health=runner.data_health([summary],hard)
        self.assertFalse(health['gates']['teacher_health']);self.assertTrue(health['gates']['candidate_coverage'])
        summary['coverage']['C00']['decisions']=0
        with self.assertRaisesRegex(ValueError,'denominator'):runner.data_health([summary],hard)

    def test_evaluate_reserves_before_opening_validation_arrays(self):
        binding={'plan':{'indices':list(range(4,204))}}
        with tempfile.TemporaryDirectory() as tmp,patch.object(runner,'consume',return_value=({}, {'models':{}}, {})),\
             patch.object(runner,'verify_unit'),patch.object(runner,'manifest_for',return_value={'groups':[]}),\
             patch('m1_train_preflight.capacity',return_value={'workers':4}),\
             patch.object(runner,'read_groups',side_effect=RuntimeError('stop before read')):
            p=Path(tmp);(p/'data').mkdir();write_json(p/'data_manifest.json',{})
            with self.assertRaisesRegex(RuntimeError,'stop before read'):runner.evaluate(p,binding)
            self.assertTrue((p/'validation_trial.json').exists())
            self.assertTrue(read_json(p/'data/confirmation_consumption.json')['validation_trial_consumed'])

    def test_saved_model_parent_rename_keeps_shard_paths_valid_and_reuses(self):
        from cpmt.m1_s5_confirmation import complete_unit
        g='rollout-pair:train:000001';rows=[row(g,s) for s in [0,1]]
        specs=[{'path':'bound_audit','sha256':'fixed','paired_group_id':g}]
        saved={'path':'saved_model','checkpoint':3000,'marker_sha256':'fixed','seed':7,'method':'cpmt_ctl_core'}
        def parallel(output,binding,model,specs,config,workers):
            shard=output/'group_000000'
            complete_unit(shard,{'source':'fixed'},lambda p:write_json(p/'result.json',{'sequences':rows}))
            return {'sequences':rows,'shards':[{'paired_group_id':g,'path':str(shard),
                'marker_sha256':file_sha256(shard/'complete.json')}],'wall_seconds':1}
        with tempfile.TemporaryDirectory() as tmp,patch.object(runner,'verify_saved',return_value=(None,{'binding':{'config':{}}})),\
             patch.object(runner,'config_for',return_value={}),patch.object(runner,'teacher_forced',return_value={'diagnostic':True}),\
             patch.object(runner,'evaluate_parallel',side_effect=parallel) as called,\
             patch.object(runner,'serial_forward_replay',return_value={'forward_calls':40}):
            p=Path(tmp);first=runner.run_model(p,{},'model',saved,specs,{})
            second=runner.run_model(p,{},'model',saved,specs,{})
            self.assertEqual(first,second);self.assertEqual(called.call_count,1)
            self.assertTrue(Path(first['evaluation']['shards'][0]['path']).is_dir())
            self.assertFalse((p/'.model.incomplete').exists())

    def test_summary_uses_all_registered_pairs_and_seeds_without_reselection(self):
        # Exercise final report wiring using complete metadata rows and mocked
        # expensive statistics/shard I/O, never real validation observations.
        binding={'plan':{'indices':list(range(4,204)),'oracle_methods':['oracle_candidate_program','observable_information_oracle']},'registration':{'fixed':True}}
        models={};results={}
        groups=[f'rollout-pair:validation:{i:06d}' for i in range(4,204)]
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'data').mkdir();write_json(p/'data_manifest.json',{})
            manifest={'candidate_coverage':1,'teacher_reference_agreement':1,'groups':[]}
            trial={'binding':{**binding,'data_manifest_sha256':file_sha256(p/'data_manifest.json')}}
            write_json(p/'validation_trial.json',trial);write_json(p/'data/confirmation_consumption.json',trial)
            for a in runner.ARCHES:
                for m in runner.METHODS:
                    for seed in runner.SEEDS:
                        key=f'{a}_{m}_{seed}';loc=p/key;loc.mkdir()
                        rr=[row(g,s) for g in groups for s in [0,1]]
                        for record in rr:record['metrics'].update(runner.F_REQUIRED)
                        result={'sequences':rr,'teacher_forced':{},'evaluation':{'shards':[]},'latency':{},'wall_seconds':1,
                                'aggregate':{'seed':seed}}
                        write_json(loc/'result.json',result);write_json(loc/'complete.json',{'binding':{'audits':[]}})
                        models[key]={'path':str(loc),'marker_sha256':file_sha256(loc/'complete.json'),'model_sha256':'fixed',
                                     'architecture':a,'method':m,'seed':seed}
            oracles={}
            for method in binding['plan']['oracle_methods']:
                write_json(p/f'{method}.json',{'sequences':rr,'shards':[]})
                oracles[method]=file_sha256(p/f'{method}.json')
            write_json(p/'evaluation_manifest.json',{'binding':binding,'models':models,'oracles':oracles})
            def stat(payloads,reg,**kwargs):
                self.assertEqual(set(payloads),set(runner.METHODS));self.assertEqual(kwargs['groups'],groups)
                self.assertEqual(kwargs['split'],'validation')
                for v in payloads.values():self.assertEqual({r['aggregate']['seed'] for r in v},set(runner.SEEDS))
                return {'fixed_statistics':True}
            with patch.object(runner,'manifest_for',return_value=manifest),patch.object(runner,'verify_unit'),\
                 patch.object(runner,'merge_shards',side_effect=lambda *a:rr),\
                 patch.object(runner,'registered_statistics',side_effect=stat) as stats,\
                 patch.object(runner,'capture_run_provenance',return_value={}):
                runner.summarize(p,binding)
                self.assertEqual(stats.call_count,2)
            report=read_json(p/'confirmation_report.json')
            self.assertEqual(len(report['per_model']),50);self.assertFalse(report['formal_test_release'])
            self.assertFalse(report['model_selection_performed'])


if __name__=='__main__':unittest.main()
