"""Pure metadata checks; no model execution or validation dataset reads."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from cpmt.m1_s5_confirmation import (complete_unit, group_indices, load_confirmation_plan,
    reserve_trial, validate_confirmation_test_marker, validate_sequence_rows, verify_unit)
from cpmt.m1_s5_training import read_json
from cpmt.m1_protocol import load_and_validate, load_and_validate_endpoint_probe, protocol_sha256


class TestS5ConfirmationMetadata(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hard = load_and_validate(PROJECT / "configs/m1_hard_condition.json")
        cls.overlay = load_and_validate_endpoint_probe(PROJECT / "configs/m1_endpoint_viability_probe.json", cls.hard)
        cls.plan, cls.training = load_confirmation_plan(PROJECT, cls.hard, cls.overlay)

    def test_frozen_plan_excludes_all_historical_groups_and_binds_sixty_models(self):
        self.assertEqual(group_indices(self.plan), list(range(4, 204)))
        self.assertEqual(len(self.training["models"]), 60)
        self.assertFalse(self.plan["evaluation"]["model_selection_performed"])
        self.assertFalse(self.plan["formal_test_release"])

    def test_historical_overlap_is_rejected(self):
        plan = deepcopy(self.plan);plan["data"]["start_group_index"] = 3
        with self.assertRaisesRegex(ValueError, "historical validation overlap"):
            group_indices(plan)

    def test_plan_cannot_enable_test_or_change_gate(self):
        from cpmt import m1_s5_confirmation as module
        real_read = module.read_json
        for edit in (lambda p:p.update(test_access=True), lambda p:p["evaluation"].update(commit_probability=0.5)):
            plan = deepcopy(self.plan);edit(plan)
            with patch.object(module, "read_json", side_effect=lambda p:plan if p.name == "m1_s5_confirmation_plan.json" else real_read(p)):
                with self.assertRaises(ValueError):
                    load_confirmation_plan(PROJECT, self.hard, self.overlay)

    def test_completed_unit_reuses_without_calling_producer_and_rejects_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "unit"
            complete_unit(path, {"model":"one"}, lambda p:(p / "result.json").write_text("{}"))
            complete_unit(path, {"model":"one"}, lambda p:self.fail("completed unit rerun"))
            with self.assertRaisesRegex(ValueError, "binding mismatch"):
                verify_unit(path, {"model":"other"})
            (path / "result.json").write_text("corrupt")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                verify_unit(path, {"model":"one"})
            reservation = Path(tmp) / "consumption.json"
            reserve_trial(reservation, {"model":"one"}, path)
            reserve_trial(reservation, {"model":"one"}, path)
            with self.assertRaisesRegex(ValueError, "different run"):
                reserve_trial(reservation, {"model":"one"}, Path(tmp) / "another-output")

    def test_partial_failure_is_retained_and_cannot_silently_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "unit"
            def fail(p):
                (p / "progress.json").write_text("{}")
                raise RuntimeError("fixture interruption")
            with self.assertRaises(RuntimeError): complete_unit(path, {}, fail)
            self.assertTrue((path.parent / ".unit.incomplete" / "failure.json").is_file())
            with self.assertRaisesRegex(ValueError, "requires review"):
                complete_unit(path, {}, lambda p:self.fail("partial unit rerun"))

    @staticmethod
    def sequences():
        return [{"metrics":{"paired_group_id":"rollout-pair:validation:000004", "sibling_index":s,"sequence_id":str(s)},
            "choices":[{"step_index":i,"base_graph_hash":str(i),"post_graph_hash":str(i+1)} for i in range(20)]} for s in (0,1)]

    def test_pair_validation_rejects_missing_sibling_duplicate_or_broken_chain(self):
        rows = self.sequences();validate_sequence_rows(rows, [4])
        for bad in (rows[:1], [rows[0],rows[0]]):
            with self.assertRaises(ValueError):validate_sequence_rows(bad, [4])
        rows[1]["choices"][4]["base_graph_hash"] = "reset-to-reference"
        with self.assertRaisesRegex(ValueError, "state chain broken"):
            validate_sequence_rows(rows, [4])

    def test_pair_validation_requires_all_twenty_steps(self):
        rows = self.sequences();rows[0]["choices"].pop()
        with self.assertRaisesRegex(ValueError, "incomplete trajectory"):
            validate_sequence_rows(rows, [4])

    def test_full_test_marker_binds_plan_source_and_access(self):
        marker={"schema_version":"cpmt-s5-confirmation-tests-v1","exit_code":0,"failures":0,"errors":0,"skipped":0,
            "tests_run":250,"expected_tests":250,"plan_sha256":protocol_sha256(self.plan),
            "source_and_tests_sha256":"fixture-source","source_tree_unchanged":True,"validation_data_read":False,"test_access":False}
        with patch("cpmt.m1_s5_confirmation.source_tree_sha256",return_value="fixture-source"):
            validate_confirmation_test_marker(marker,PROJECT,self.plan)
            marker["test_access"]=True
            with self.assertRaises(ValueError):validate_confirmation_test_marker(marker,PROJECT,self.plan)
