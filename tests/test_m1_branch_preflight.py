"""Lightweight control-flow tests; no real generation, training or held-out data."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from cpmt.m1_branch_preflight import (GROUPS, POLICIES, choose_candidate,
                                     fixed_plan, run_branch, summarize)


def audit():
    return {"paired_group_id": "rollout-pair:train:000000", "sibling_index": 0,
            "initial_world": {"graph_hash": "v0", "edges": []},
            "steps": [{"online": {"split": "train"}, "event_spec": {"index": i}}
                      for i in range(20)]}


def materialize(audit, base, step):
    return {"executed_candidates": [
        {"candidate_index": i, "template": "NOOP" if i == 0 else "MERGE",
         "static_preflight_pass": i < 2, "legal": i < 2,
         "base_graph_hash": base["graph_hash"],
         "post_graph": deepcopy(base) if i == 0 else {"graph_hash": f"v{step+1}", "edges": []},
         "failure": None if i < 2 else {"message": "fixture rejection"}}
        for i in range(16)]}


class TestTrainBranchPreflight(unittest.TestCase):
    def execute(self, fixture=None, materializer=materialize, scope=lambda *a, **k: set(), policy="prefer_merge"):
        self.records = []
        return run_branch(fixture or audit(), 0, policy, materialize=materializer,
                          scope=scope, validate_graph=lambda g: None, sink=self.records.append)

    def test_fixed_matrix_has_4480_decisions_without_heldout_access(self):
        plan = fixed_plan()
        self.assertEqual(len(GROUPS) * 2 * len(POLICIES) * 20, 4480)
        self.assertEqual(GROUPS, (0, 66, 133, 199, 266, 333, 399, 466,
                                 532, 599, 666, 732, 799, 865, 932, 999))
        self.assertFalse(plan["test_access"])
        self.assertFalse(plan["validation_access"])

    def test_next_step_uses_selected_world_and_preserves_input(self):
        fixture = audit(); before = deepcopy(fixture)
        result = self.execute(fixture)
        self.assertEqual(result["completed_steps"], 20)
        self.assertEqual(result["final_graph_hash"], "v20")
        self.assertEqual([r["base_graph_hash"] for r in self.records], [f"v{i}" for i in range(20)])
        self.assertEqual(fixture, before)

    def test_preflight_admissible_executor_illegal_keeps_world(self):
        def illegal(a, b, s):
            value = materialize(a, b, s)
            value["executed_candidates"][1].update(legal=False, post_graph=None, failure={"message": "runtime"})
            return value
        result = self.execute(materializer=illegal)
        self.assertEqual(result["executor_quarantined"], 20)
        self.assertEqual(result["final_graph_hash"], "v0")

    def test_construction_failure_retains_exact_predicted_base_and_stops(self):
        def broken(a, b, s):
            if s == 1:
                raise ValueError("C11 empty scope complement")
            return materialize(a, b, s)
        with self.assertRaisesRegex(ValueError, "C11"):
            self.execute(materializer=broken)
        self.assertEqual(len(self.records), 2)
        self.assertEqual(self.records[-1]["base_world"]["graph_hash"], "v1")
        self.assertEqual(self.records[-1]["step_index"], 1)
        self.assertEqual(self.records[-1]["kind"], "failure")

    def test_scope_order_failure_is_not_swallowed(self):
        fixture = audit(); fixture["initial_world"]["edges"] = ["a", "b"]
        with self.assertRaisesRegex(ValueError, "edge order"):
            self.execute(fixture, scope=lambda graph, event, **kwargs: {graph["edges"][0]})
        self.assertEqual(self.records[-1]["completed_steps"], 0)

    def test_candidate_collapse_fails_before_selection(self):
        def collapsed(a, b, s):
            value = materialize(a, b, s)
            value["executed_candidates"].pop()
            return value
        with self.assertRaisesRegex(ValueError, "K=16"):
            self.execute(materializer=collapsed)

    def test_validation_cannot_enter_branch_runner(self):
        fixture = audit(); fixture["steps"][0]["online"]["split"] = "validation"
        with self.assertRaisesRegex(ValueError, "non-train"):
            self.execute(fixture)

    def test_selector_uses_no_executed_or_reference_information(self):
        candidates = [{"candidate_index": 0, "template": "NOOP", "static_preflight_pass": True},
                      {"candidate_index": 1, "template": "MERGE", "static_preflight_pass": True}]
        arguments = {"group": 0, "sibling": 1, "step": 3}
        for policy in POLICIES:
            expected = choose_candidate(candidates, policy, **arguments)
            changed = [dict(c, legal=False, post_graph="wrong", future_energy=-999,
                            reference_program_index=99) for c in reversed(candidates)]
            self.assertEqual(expected, choose_candidate(changed, policy, **arguments))

    def test_unavailable_template_is_explicit_noop(self):
        candidates = [{"candidate_index": 0, "template": "NOOP", "static_preflight_pass": True}]
        self.assertEqual(choose_candidate(candidates, "prefer_merge", group=0, sibling=0, step=0), (0, True))

    def test_missing_or_duplicate_matrix_never_passes(self):
        groups = [{"group": g, "status": "pass", "branches": [
            {"group": g, "sibling": s, "policy": p, "completed_steps": 20}
            for s in (0, 1) for p in POLICIES]} for g in GROUPS]
        self.assertTrue(summarize(groups)["pass"])
        groups[0]["branches"][-1] = groups[0]["branches"][0]
        self.assertFalse(summarize(groups)["pass"])
        with self.assertRaisesRegex(ValueError, "incomplete/duplicate"):
            summarize(groups[:-1])

    def test_c11_scope_complement_counts_only_eligible_unrelated_nodes(self):
        fixture = audit()
        fixture["initial_world"]["nodes"] = [
            {"node_id": name, "lifecycle": "confirmed", "valid_to": None}
            for name in ("bind", "protected", "inside", "outside")]
        for step in fixture["steps"]:
            step["event_spec"].update(proposal_observation={"unrelated_context_active": True}, protected_id="protected")
        records = []
        result = run_branch(fixture, 0, "noop", materialize=materialize,
                            scope=lambda *a, **k: {"inside"}, validate_graph=lambda g: None,
                            proposal_context=lambda *a: {"bind_targets": ["bind"],
                                                         "merge_pairs": [["a", "b"], ["a", "c"]]},
                            sink=records.append)
        self.assertEqual(result["minimum_c11_unrelated_candidates"], 1)
        self.assertTrue(all(r["proposal_availability"]["distinct_merge_pairs"] == 2 for r in records))


if __name__ == "__main__":
    unittest.main()
