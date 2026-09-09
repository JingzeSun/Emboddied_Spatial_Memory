"""Bounded replays of saved train failures; no new data/rollout/training."""
from copy import deepcopy
import inspect
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cpmt import m1_rollout as rollout
from cpmt.executor import validate_graph
from cpmt.hashing import canonical_json


class TestCandidateAvailability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        report = json.loads((ROOT / "results/m1_v7_d051_train_branch_preflight.json").read_text())
        cls.snapshots = [v for k, v in report["failure_diagnostics"].items()
                         if k.endswith("failure_snapshot.json")]

    def test_all_real_failure_snapshots_keep_strict_errors(self):
        self.assertEqual(len(self.snapshots), 16)
        for saved in self.snapshots:
            with self.subTest(group=saved["group"]):
                with self.assertRaises(ValueError) as caught:
                    rollout.generate_fixed_candidates(saved["base_world"], saved["event"])
                self.assertEqual(str(caught.exception), saved["error_message"])

    def test_opt_in_retains_real_candidates_and_records_missing_slots(self):
        for saved in self.snapshots:
            with self.subTest(group=saved["group"]):
                graph, event = saved["base_world"], saved["event"]
                before = canonical_json(graph)
                validate_graph(graph)
                programs, evidence, audit = rollout.generate_fixed_candidates(graph, event, allow_unavailable=True)
                executed = rollout._execute_candidates(graph, programs, evidence)
                self.assertEqual(canonical_json(graph), before)
                self.assertEqual(len(programs), 16)
                self.assertEqual(audit["unavailable_slots"], 1)
                missing = [c for c in executed if c.get("slot_status") == "unavailable"]
                self.assertEqual(len(missing), 1)
                self.assertFalse(missing[0]["static_preflight_pass"])
                self.assertFalse(missing[0]["execution_attempted"])
                self.assertIsNone(missing[0]["post_graph"])
                self.assertEqual(missing[0]["failure"]["type"], "ProposalUnavailable")
                noops = [c for c in executed if c["template"] == "NOOP"]
                self.assertEqual(len(noops), 1)
                self.assertTrue(noops[0]["legal"] and noops[0]["static_preflight_pass"])
                self.assertTrue(all(c["base_graph_hash"] == graph["graph_hash"] for c in executed))

    def test_missing_slot_does_not_call_executor_or_pretend_to_be_noop(self):
        saved = self.snapshots[0]
        graph, event = saved["base_world"], saved["event"]
        slot = rollout._unavailable_slot(graph, event, "MERGE", "one", "insufficient_distinct_merge_pairs")
        with patch.object(rollout, "execute_transaction", side_effect=AssertionError("executed empty slot")), patch.object(
                rollout, "preflight_transaction", side_effect=AssertionError("preflight empty slot")):
            row = rollout._execute_candidates(graph, [slot], {})[0]
        self.assertEqual(row["template"], "MERGE")
        self.assertFalse(row["legal"])

    def test_hidden_reference_fields_do_not_change_repair(self):
        saved = self.snapshots[0]
        event = deepcopy(saved["event"])
        event.update(reference_spec={"malicious": "unused"}, scenario_family="NOT_A_FAMILY", future="unused")
        first = rollout.generate_fixed_candidates(saved["base_world"], saved["event"], allow_unavailable=True)
        second = rollout.generate_fixed_candidates(saved["base_world"], event, allow_unavailable=True)
        self.assertEqual(first, second)

    def test_healthy_catalog_preserves_programs_evidence_and_order(self):
        # Synthetic non-C11 event on an existing graph. Actual unchanged
        # reference/recovery states are compared separately on the server.
        saved = next(s for s in self.snapshots if s["group"] == 66)
        event = deepcopy(saved["event"])
        event["proposal_observation"]["unrelated_context_active"] = False
        strict, evidence, _ = rollout.generate_fixed_candidates(saved["base_world"], event)
        optional, other_evidence, audit = rollout.generate_fixed_candidates(
            saved["base_world"], event, allow_unavailable=True)
        self.assertEqual(strict, optional)
        self.assertEqual(evidence, other_evidence)
        self.assertEqual(audit["unavailable_slots"], 0)

    def test_legal_duplicate_becomes_unavailable_not_extra_noop(self):
        saved = self.snapshots[0]
        graph, event = saved["base_world"], saved["event"]
        noop = rollout._noop_program(graph, event)
        programs = [deepcopy(noop) for _ in range(16)]
        for i, program in enumerate(programs):
            program["transaction_id"] += f":{i}"
        with patch.object(rollout, "_build_fixed_candidate_catalog", return_value=(programs, {})):
            with self.assertRaisesRegex(AssertionError, "collapsed"):
                rollout.generate_fixed_candidates(graph, event)
            slots, _, audit = rollout.generate_fixed_candidates(graph, event, allow_unavailable=True)
        self.assertEqual(audit["canonical_duplicates_removed"], 15)
        self.assertEqual(audit["unavailable_slots"], 15)
        self.assertEqual(sum(not rollout._is_unavailable_slot(p) for p in slots), 1)
        self.assertTrue(all(p["unavailable_reason"] == "canonical_duplicate"
                            for p in slots if rollout._is_unavailable_slot(p)))

    def test_unexpected_errors_still_escape(self):
        saved = self.snapshots[0]
        event = deepcopy(saved["event"])
        del event["proposal_observation"]["node_query"]
        with self.assertRaisesRegex(ValueError, "proposal_observation fields"):
            rollout.generate_fixed_candidates(saved["base_world"], event, allow_unavailable=True)

    def test_formal_entrypoints_are_strict_by_default(self):
        for function in (rollout.generate_fixed_candidates, rollout.materialize_rollout_step):
            self.assertIs(inspect.signature(function).parameters["allow_unavailable"].default, False)


if __name__ == "__main__":
    unittest.main()
