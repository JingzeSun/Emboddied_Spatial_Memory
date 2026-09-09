"""Bounded recipe, pairing and artifact regressions; no training/generation."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import gzip
import json
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
from cpmt.m1_s5_confirmation import complete_unit
from cpmt.m1_s5_training import write_json
from cpmt.run_provenance import file_sha256
import m1_corrected_training_plan as plan
from m1_paired_evaluation import validate_rows, merge_shards, registered_statistics, serial_forward_replay, METRICS
from m1_training_jobs import validate_job
from run_m1_corrected_followon import immutable_json
import run_m1_corrected_followon as followon


def binding():
    return {'source_and_tests_sha256': 'source', 'input': {'input_path': 'train.npz',
        'input_file_sha256': 'file', 'arrays_digest': 'digest', 'groups': list(range(1000))}}


def recipe(stage='scorers'):
    b = binding()
    jobs = [plan.base_job(b,a,s,'outcome_scorer',lr,plan.STEPS) for a in plan.ARCHES for s in plan.SEEDS for lr in plan.RATES]
    return {'schema_version': 'cpmt-corrected-training-recipe-v1', 'stage': stage, 'binding': b, 'jobs': jobs, 'selected': {}}


def sequence(group, sibling):
    return {'metrics': {'paired_group_id': group, 'sibling_index': sibling, 'sequence_id': group+':'+str(sibling),
        **{m: .5 for m in METRICS}, 'false_birth_growth_per_100': 0., 'collateral_violation_per_100': 0.,
        'active_node_state_error_per_100': 0.},
        'choices': [{'step_index': i, 'base_graph_hash': str(i), 'post_graph_hash': str(i+1),
            'selected_static_preflight_pass': True} for i in range(20)]}


class TestCorrectedRecipes(unittest.TestCase):
    def test_full_scorer_grid_is_thirty_optimizer_paths(self):
        r = recipe(); plan.validate_recipe(r)
        self.assertEqual(len(r['jobs']),30)
        self.assertEqual(sum(len(j['checkpoints']) for j in r['jobs']),120)

    def test_missing_seed_is_rejected(self):
        r = recipe(); r['jobs'].pop()
        with self.assertRaisesRegex(ValueError, 'incomplete'): plan.validate_recipe(r)

    def test_duplicate_scientific_job_is_rejected_even_with_new_id(self):
        r = recipe(); other=deepcopy(r['jobs'][0]); other['id']='another';r['jobs'].append(other)
        with self.assertRaisesRegex(ValueError, 'duplicate scientific'): plan.validate_recipe(r)

    def test_rate_steps_population_and_device_drift_rejected(self):
        for key,value in [('learning_rate',.0008),('checkpoints',[300,1000]),('groups',[0]),('device','cpu'),('torch_threads',8),('validation_access',True)]:
            with self.subTest(key=key):
                r=recipe();r['jobs'][0][key]=value
                with self.assertRaises(ValueError):plan.validate_recipe(r)

    def test_capacity_is_four_short_full_population_jobs(self):
        b=binding();r={'schema_version':'cpmt-corrected-training-recipe-v1','stage':'capacity','binding':b,'selected':{},
            'jobs':[plan.base_job(b,a,7,m,.0006,[2],mode='refit') for a in plan.ARCHES for m in ['outcome_scorer',plan.METHODS[0]]]}
        plan.validate_recipe(r);self.assertEqual(len(r['jobs']),4)
        r['jobs'][0]['checkpoints']=[30]
        with self.assertRaisesRegex(ValueError,'capacity'):plan.validate_recipe(r)

    def test_c_weights_are_twenty_paths_at_frozen_compute(self):
        b=binding();selected={a:{'direct_future_loss':{'learning_rate':.0002,'steps':1000}} for a in plan.ARCHES}
        r={'schema_version':'cpmt-corrected-training-recipe-v1','stage':'c_weights','binding':b,'selected':selected,
            'jobs':[plan.base_job(b,a,s,'direct_future_loss',.0002,[1000],weight=w) for a in plan.ARCHES for s in plan.SEEDS for w in [.1,10.]]}
        plan.validate_recipe(r);self.assertEqual(len(r['jobs']),20)
        r['jobs'][0]['checkpoints']=[3000]
        with self.assertRaisesRegex(ValueError,'compute'):plan.validate_recipe(r)

    def test_refit_uses_selected_weight_and_population(self):
        b=binding();selected={a:{m:{'learning_rate':.002,'steps':300,'auxiliary_weight':10. if m=='direct_future_loss' else 1.} for m in plan.METHODS} for a in plan.ARCHES}
        r={'schema_version':'cpmt-corrected-training-recipe-v1','stage':'refit_students','binding':b,'selected':selected,
            'jobs':[plan.base_job(b,a,s,m,.002,[300],mode='refit',weight=selected[a][m]['auxiliary_weight'],
                dependency={'path':'scorer'} if m=='future_no_execution' else None) for a in plan.ARCHES for s in plan.SEEDS for m in plan.METHODS]}
        plan.validate_recipe(r);self.assertEqual(len(r['jobs']),50)
        r['jobs'][0]['mode']='budget'
        with self.assertRaises(ValueError):plan.validate_recipe(r)

    def test_formal_worker_requires_passed_interfaces_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);r=recipe();ready=root/'ready.json'
            write_json(ready,{'pass':True,'source_and_tests_sha256':'source','capacity_pass':True,'interfaces_pass':False})
            r['binding'].update(ready_path=str(ready),ready_sha256=file_sha256(ready))
            jobs=plan.seal_recipe(root/'recipe.json','scorers',r['binding'],r['jobs'])
            with self.assertRaisesRegex(ValueError,'all checks'):validate_job(jobs[0])

    def test_recipe_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'recipe.json';r=recipe();jobs=plan.seal_recipe(path,'scorers',r['binding'],r['jobs'])
            path.write_text('{}')
            with self.assertRaisesRegex(ValueError,'recipe changed'):validate_job(jobs[0])

    def test_budget_uncertainty_seed_matches_original_registration(self):
        hard=plan.read_json(ROOT/'configs/m1_hard_condition_v7.json')
        original=hard['training']['pretest_budget_selection']['selection_uncertainty']
        self.assertTrue(all(plan.UNCERTAINTY[k]==original[k] for k in plan.UNCERTAINTY))

    def test_grid_ties_prefer_fewer_steps_then_lower_rate(self):
        rows=[{'method':'outcome_scorer','seed':s,'learning_rate':lr,'checkpoint':n,
            'reference_accuracy_by_group':{'1':.5,'2':.5}} for s in plan.SEEDS for lr in plan.RATES for n in plan.STEPS]
        chosen,_=plan.select_grid(rows,'outcome_scorer')
        self.assertEqual((chosen['learning_rate'],chosen['steps']),(.0002,300))

    def test_immutable_report_never_replaces_previous(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'report.json';immutable_json(p,{'a':1});immutable_json(p,{'a':1})
            with self.assertRaises(ValueError):immutable_json(p,{'a':2})

    def test_budget_barriers_and_c_selection_use_only_frozen_compute(self):
        # Run the real orchestration/reducers with synthetic checkpoint metrics,
        # replacing only GPU jobs and disk persistence. No arrays/models exist.
        stages=[];saved={};jobs_by_id={};b=binding()
        def run_jobs(output,stage,bind,jobs,selected=None):
            plan.validate_recipe({'schema_version':'cpmt-corrected-training-recipe-v1',
                'stage':stage,'binding':bind,'jobs':jobs,'selected':selected or {}})
            stages.append(stage);jobs_by_id.update({j['id']:j for j in jobs})
            return {'artifacts':{j['id']:j['id'] for j in jobs}}
        def rows(paths):
            result=[]
            for key in paths:
                j=jobs_by_id[key]
                for n in j['checkpoints']:
                    score=.8 if j['learning_rate']==.0006 and n==1000 else .4
                    if j['method']=='direct_future_loss' and j['auxiliary_weight']==.1:score=.9
                    result.append({**j,'checkpoint':n,'reference_accuracy_by_group':{'1':score,'2':score}})
            return result
        def save(path,value):saved[path.name]=deepcopy(value)
        with patch.object(followon,'job_binding',return_value=b),patch.object(followon,'read_json',return_value={
                'capacity_report_sha256':'hash','interfaces_report_sha256':'hash'}),\
             patch.object(followon,'file_sha256',return_value='hash'),patch.object(followon,'completed_paths',return_value=None),\
             patch.object(followon,'run_jobs',side_effect=run_jobs),patch.object(followon,'artifact_rows',side_effect=rows),\
             patch.object(followon,'dependency',return_value={'path':'scorer','checkpoint':1000}),\
             patch.object(followon,'immutable_json',side_effect=save),patch.object(plan,'fixed_groups',return_value=[1,2]):
            followon.budget(Path('unused'),b)
        self.assertEqual(stages,['scorers','students','c_weights'])
        report=saved['budget.report.json'];self.assertEqual(len(report['artifacts']),200)
        self.assertEqual(len(report['scorer_rows'])+len(report['student_rows'])+len(report['c_auxiliary_rows']),740)
        for a in plan.ARCHES:
            self.assertEqual(report['selected'][a]['direct_future_loss']['auxiliary_weight'],.1)
            self.assertEqual(saved['compute.selection.json'][a]['direct_future_loss']['auxiliary_weight'],1.)
            self.assertEqual(report['selected'][a]['direct_future_loss']['steps'],1000)


class TestPairedFollowon(unittest.TestCase):
    def test_latency_replay_uses_shared_mask_and_saved_selected_index(self):
        class FixedModel(torch.nn.Module):
            def forward(self,x): return torch.tensor([[10.,1.]],dtype=torch.float32)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);model=root/'model';shard=root/'shard'
            complete_unit(model,{},lambda p:write_json(p/'dummy.json',{}))
            record={'materialized':{'online':{},'executed_candidates':[
                {'static_preflight_pass':False},{'static_preflight_pass':True}]},'choice':{'selected_index':1}}
            def save(path):
                with gzip.open(path/'execution.jsonl.gz','wt',encoding='utf-8') as stream:stream.write(json.dumps(record)+'\n')
            complete_unit(shard,{},save)
            spec={'path':str(model),'marker_sha256':file_sha256(model/'complete.json'),'checkpoint':30}
            with patch('m1_paired_evaluation.load_model',return_value=(FixedModel(),{})),\
                 patch('cpmt.m1_af_rollout.online_feature_vector',return_value=np.zeros((2,3),dtype=np.float32)):
                result=serial_forward_replay(spec,[{'path':str(shard)}])
            self.assertEqual(result['forward_calls'],1)
            self.assertGreaterEqual(result['p95_forward_latency_ms'],0)
            self.assertFalse(result['machine_global_exclusivity_verified'])

    def test_complete_pairs_and_state_chains(self):
        groups=['rollout-pair:train:000001','rollout-pair:train:000009']
        rows=[sequence(g,s) for g in groups for s in (0,1)];validate_rows(rows,groups)
        for change in ['duplicate','missing','chain','steps','mask','nan']:
            broken=deepcopy(rows)
            if change=='duplicate':broken[-1]=broken[0]
            if change=='missing':broken.pop()
            if change=='chain':broken[0]['choices'][1]['base_graph_hash']='bad'
            if change=='steps':broken[0]['choices'].pop()
            if change=='mask':broken[0]['choices'][0]['selected_static_preflight_pass']=False
            if change=='nan':broken[0]['metrics'][METRICS[0]]=float('nan')
            with self.subTest(change=change):
                with self.assertRaises(ValueError):validate_rows(broken,groups)

    def test_shards_merge_in_canonical_group_order(self):
        with tempfile.TemporaryDirectory() as folder:
            shards=[];specs=[]
            for i in [9,1]:
                group=f'rollout-pair:train:{i:06d}';p=Path(folder)/str(i)
                rows=[sequence(group,s) for s in (1,0)]
                complete_unit(p,{'group':group},lambda d,rows=rows:write_json(d/'result.json',{'sequences':rows}))
                shards.append({'path':str(p),'paired_group_id':group,'marker_sha256':file_sha256(p/'complete.json')})
                specs.append({'paired_group_id':group})
            merged=merge_shards(shards,specs)
            self.assertEqual([(r['metrics']['paired_group_id'],r['metrics']['sibling_index']) for r in merged],
                [(f'rollout-pair:train:{i:06d}',s) for i in [1,9] for s in (0,1)])
            with self.assertRaises(ValueError):merge_shards([shards[0],shards[0]],specs)

    def test_statistics_reject_duplicate_seed_before_reducer(self):
        groups=['rollout-pair:train:000001']
        payloads={m:[{'aggregate':{'seed':7},'sequences':[sequence(groups[0],s) for s in (0,1)]}]*2
            for m in ['cpmt_ctl_core','direct_future_loss','future_no_execution']}
        registered={'schema_version':'cpmt-m1-corrected-post-probe-registration-v1','evaluation_plan':{
            'semantic_metric':METRICS[0],'support_metric':METRICS[1],'burden_metric':METRICS[2],
            'minimum_effects':[.03,.03,40.]}}
        with patch('m1_paired_evaluation.contracts',return_value=({}, {'endpoints':{'minimum_effects':[.03,.03,40.]}}, {})):
            with self.assertRaisesRegex(ValueError,'duplicate seed'):
                registered_statistics(payloads,registered,split='train',groups=groups,seeds=[7],engineering=True)

    def test_full_probe_rows_cannot_be_called_formal_validation(self):
        registered={'schema_version':'cpmt-m1-corrected-post-probe-registration-v1','evaluation_plan':{
            'semantic_metric':METRICS[0],'support_metric':METRICS[1],'burden_metric':METRICS[2],
            'minimum_effects':[.03,.03,40.], 'paired_groups':{'validation':200}}}
        with patch('m1_paired_evaluation.contracts',return_value=({}, {'endpoints':{'minimum_effects':[.03,.03,40.]}}, {})):
            with self.assertRaisesRegex(ValueError,'population'):
                registered_statistics({},registered,split='validation',groups=['rollout-pair:train:000001'])


if __name__=='__main__':unittest.main()
