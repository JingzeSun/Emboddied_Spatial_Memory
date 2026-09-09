"""Server-only runner integration checks, using train fixtures and tiny models."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import torch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
sys.path.insert(0, str(PROJECT / "scripts"))
import run_m1_s5_confirmation as runner
from cpmt.dev_learning import OnlineModel
from cpmt.m1_s5_training import read_json
from cpmt.m1_s5_confirmation import verify_unit
from cpmt.m1_protocol import load_and_validate
from cpmt.m1_rollout import generate_m1_paired_rollout_split
from cpmt.m1_af_rollout import rollout_learning_arrays_from_audits, causal_rollout_metrics
import test_m1_s5_confirmation as metadata_tests


class TestS5ConfirmationRunner(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        cls.hard=load_and_validate(PROJECT / "configs/m1_hard_condition_v7.json")
        cls.plan=read_json(PROJECT / "configs/m1_s5_confirmation_plan.json")
        cls.online, cls.audits, cls.summary=generate_m1_paired_rollout_split(cls.hard,"train",paired_groups=1)
        cls.arrays=rollout_learning_arrays_from_audits(cls.hard,cls.audits,future_hash_bins=32)

    def test_eval_config_preserves_selected_recipe_and_fixes_registered_gate(self):
        saved={"architecture":"shared_candidate_mlp_v1","student_steps":10000,"auxiliary_weight":10,"device":"cuda","commit_probability":0.9}
        cfg=runner.evaluation_config(self.hard,self.plan,saved)
        self.assertEqual((cfg["student_steps"],cfg["auxiliary_weight"]),(10000,10))
        self.assertEqual((cfg["device"],cfg["cpu_threads"],cfg["commit_probability"],cfg["margin_threshold"]),("cpu",1,0,0))
        self.assertEqual(saved["device"],"cuda")

    def test_group_cache_uses_existing_generator_encoder_and_reuses_completed_files(self):
        # Supply only pre-generated train fixtures; do not generate S5 validation.
        with tempfile.TemporaryDirectory() as tmp,patch.object(runner,"generate_m1_paired_rollout_split",return_value=(self.online,self.audits,self.summary)) as generator:
            task=(str(PROJECT / "configs/m1_hard_condition_v7.json"),tmp,4,{"fixture":True})
            index, marker=runner.make_group(task)
            self.assertEqual(index,4)
            self.assertEqual(generator.call_args.kwargs,{"paired_groups":1,"start_group_index":4})
            directory=Path(tmp) / "group_000004"
            with np.load(directory / "learning.npz",allow_pickle=False) as arrays:
                self.assertEqual(set(arrays["group"].tolist()),{4})
                for key,value in self.arrays.items():
                    if key != "group": np.testing.assert_array_equal(arrays[key],value)
            self.assertEqual(runner.make_group(task)[1],marker)
            self.assertEqual(generator.call_count,1)

    def test_audit_collection_retains_complete_pairs_and_rejects_identity_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp) / "group_000004";directory.mkdir()
            audits=[{"paired_group_id":"rollout-pair:validation:000004","sibling_index":s,"steps":[{}]*20} for s in (0,1)]
            runner.write_gzip(directory / "audits.json.gz",audits)
            collection=runner.AuditCollection(Path(tmp),[4])
            self.assertEqual(list(collection),list(collection))
            audits.pop();runner.write_gzip(directory / "audits.json.gz",audits)
            with self.assertRaisesRegex(ValueError,"broken sibling pair"):list(collection)

    def test_optional_audit_recorder_does_not_change_causal_choices_or_metrics(self):
        cfg=runner.evaluation_config(self.hard,self.plan)
        before, sequences=causal_rollout_metrics(None,self.audits,cfg,oracle=True)
        records=[]
        after, recorded=causal_rollout_metrics(None,self.audits,cfg,oracle=True,
            audit_sink=lambda materialized,choice,current:records.append((choice["post_graph_hash"],current["graph_hash"])))
        self.assertEqual(before,after);self.assertEqual(sequences,recorded)
        self.assertEqual(len(records),40);self.assertTrue(all(a==b for a,b in records))

    def test_reference_history_diagnostic_excludes_recovery_rows_and_never_trains(self):
        model=OnlineModel(input_dim=self.arrays["x"].shape[1],hidden=8,
            future_dim=self.arrays["future"].shape[-1],horizon=3,num_candidates=16,
            candidate_dim=33,relation_dim=self.arrays["relation_targets"].shape[-1],architecture="shared_candidate_mlp_v1").eval()
        before={k:v.clone() for k,v in model.state_dict().items()}
        result=runner.teacher_forced(model,self.arrays)
        self.assertTrue(result["reference_history_only"]);self.assertFalse(result["model_selection_performed"])
        self.assertIsNone(result["recovery_accuracy"])
        self.assertTrue(all(torch.equal(v,model.state_dict()[k]) for k,v in before.items()))

    def test_completed_causal_unit_resumes_without_model_forward_or_rollout(self):
        rows=metadata_tests.TestS5ConfirmationMetadata.sequences()
        binding={"method":"cpmt_ctl_core","seed":7}
        with tempfile.TemporaryDirectory() as tmp,patch.object(runner,"causal_rollout_metrics",return_value=({"p95_forward_latency_ms":1.0},rows)) as rollout:
            path=Path(tmp) / "unit"
            first=runner.evaluate_one(path,binding,None,[],{},[4])
            second=runner.evaluate_one(path,binding,None,[],{},[4])
            self.assertEqual(first,second);self.assertEqual(rollout.call_count,1)
            verify_unit(path,binding)

    def test_incomplete_causal_chain_is_retained_as_failure_not_published(self):
        rows=metadata_tests.TestS5ConfirmationMetadata.sequences();rows[0]["choices"].pop()
        with tempfile.TemporaryDirectory() as tmp,patch.object(runner,"causal_rollout_metrics",return_value=({},rows)):
            path=Path(tmp) / "unit"
            with self.assertRaisesRegex(ValueError,"incomplete trajectory"):
                runner.evaluate_one(path,{"method":"cpmt_ctl_core","seed":7},None,[],{},[4])
            self.assertFalse(path.exists());self.assertTrue((Path(tmp) / ".unit.incomplete" / "failure.json").exists())

    def test_statistics_count_pairs_not_siblings_or_training_seeds(self):
        hard=deepcopy(self.hard);hard["evaluation"]["bootstrap"]["resamples"]=20
        overlay=read_json(PROJECT / "configs/m1_endpoint_viability_probe.json")
        payloads={}
        for method in ("cpmt_ctl_core","direct_future_loss","future_no_execution"):
            payloads[method]=[]
            for seed in (7,19,31,43,59):
                sequences=[]
                for group in (4,5):
                    for sibling in (0,1):
                        metrics={"paired_group_id":str(group),"sequence_id":f"{group}:{sibling}",
                            "final_active_graph_correctness":1.0 if method=="cpmt_ctl_core" else 0.9,
                            "final_graded_open_memory_correctness":1.0 if method=="cpmt_ctl_core" else 0.9,
                            "open_fact_error_auc_per_100_decisions":0.0 if method=="cpmt_ctl_core" else 50.0,
                            "false_birth_growth_per_100":0.0,"collateral_violation_per_100":0.0,"active_node_state_error_per_100":0.0}
                        sequences.append({"metrics":metrics})
                payloads[method].append({"aggregate":{"seed":seed},"sequences":sequences})
        result=runner._paired_causal_statistics(payloads,hard,overlay)
        self.assertEqual(result["paired_groups"],2);self.assertEqual(result["sequence_seed_rows"],20)
        self.assertAlmostEqual(result["contrasts"]["A_vs_C"]["active_graph_correctness"]["effect"],0.1)
        self.assertEqual(result["contrasts"]["A_vs_E"]["open_fact_error_burden"]["minimum_effect"],40.0)
