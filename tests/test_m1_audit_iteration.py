"""Repeatable disk-reader regressions; no training or real-world generation."""
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src'),str(ROOT/'ops')]
from cpmt.run_provenance import file_sha256
from cpmt.m1_af_rollout import causal_rollout_metrics
from m1_paired_evaluation import ReplayableAudits, run_serial, METRICS
from m1_followon_recovery import verify_iterator_delta, historical_files, linux_tree_hash


def pair(group):
    return [{'paired_group_id':group,'sibling_index':s,'ambiguity_pivot_step':0,'initial_world':{},
        'steps':[{'reference_program_index':0,'executed_candidates':[{'post_graph_hash':str(s)}]}]*20} for s in [0,1]]


def row(group,sibling):
    return {'metrics':{'paired_group_id':group,'sibling_index':sibling,'sequence_id':group+':'+str(sibling),
        **{m:1. for m in METRICS}},'choices':[{'step_index':i,'base_graph_hash':str(i),
            'post_graph_hash':str(i+1),'selected_static_preflight_pass':True} for i in range(20)]}


class TestAuditIteration(unittest.TestCase):
    def test_disk_reader_reopens_pairs_and_does_not_retain_mutations(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'audit.gz';audits=pair('g')
            with gzip.open(p,'wt',encoding='utf-8') as f:json.dump({'audits':audits},f)
            spec={'path':str(p),'sha256':file_sha256(p),'paired_group_id':'g'}
            reader=ReplayableAudits([spec]);first=list(reader);first[0]['initial_world']['mutated']=True
            self.assertEqual(list(reader),audits)
            self.assertEqual(list(reader),audits)
            spec['path']='changed caller dictionary'
            self.assertEqual(list(reader),audits)

    def test_real_causal_function_reaches_second_pass(self):
        class ReachedRollout(Exception):pass
        with patch('m1_paired_evaluation.read_audits',return_value=pair('g')),\
             patch('cpmt.m1_af_rollout.clone_json',side_effect=ReachedRollout('second traversal')):
            # The real function consumes its first pass for the two pivot hashes.
            # Stop at the first operation of its second pass, before any executor.
            with self.assertRaisesRegex(ReachedRollout,'second traversal'):
                causal_rollout_metrics(None,ReplayableAudits([{}]),{'device':'cpu'})

    def test_run_serial_supplies_repeatable_input_to_multi_pass_consumer(self):
        groups=['g1','g2'];passes=[]
        def consumer(model,audits,config,**kwargs):
            for _ in range(3):passes.append([(a['paired_group_id'],a['sibling_index']) for a in audits])
            return {'p95_forward_latency_ms':0.},[row(g,s) for g in groups for s in [0,1]]
        with tempfile.TemporaryDirectory() as folder,\
             patch('m1_paired_evaluation.read_audits',side_effect=lambda s:pair(s['paired_group_id'])),\
             patch('m1_paired_evaluation.causal_rollout_metrics',side_effect=consumer) as called:
            path=Path(folder)/'unit';specs=[{'paired_group_id':g} for g in groups]
            first=run_serial(path,{},None,specs,{})
            self.assertEqual(passes[0],passes[1]);self.assertEqual(passes[1],passes[2]);self.assertEqual(len(passes[0]),4)
            self.assertEqual(run_serial(path,{},None,specs,{}),first)
            self.assertEqual(called.call_count,1)

    def test_compatibility_bridge_rejects_unrelated_scientific_edit(self):
        old=historical_files();new=(ROOT/'scripts/m1_paired_evaluation.py').read_text(encoding='utf-8')
        before=old['scripts/m1_paired_evaluation.py'].decode('utf-8')
        verify_iterator_delta(before,new)
        with self.assertRaisesRegex(ValueError,'exceeds'):
            verify_iterator_delta(before,new.replace('compresslevel=1','compresslevel=9'))
        with self.assertRaisesRegex(ValueError,'reader class'):
            verify_iterator_delta(before,new.replace('tuple(dict(spec) for spec in specs)','list(specs)'))
        self.assertTrue(linux_tree_hash(old).startswith('cc2d5e2113ed'))


if __name__=='__main__':unittest.main()
