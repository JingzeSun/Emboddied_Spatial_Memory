"""Small dictionary tests only; no dataset, models or candidate executions."""
from copy import deepcopy
import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace
import unittest

spec = importlib.util.spec_from_file_location("scope_impact", Path(__file__).resolve().parents[1] /
                                             "scripts/run_m1_scope_impact.py")
impact = importlib.util.module_from_spec(spec)
spec.loader.exec_module(impact)


class TestScopeImpact(unittest.TestCase):
    def setUp(self):
        self.graph = {"edges": [{"edge_id": "ab", "source": "a", "target": "b"},
                                {"edge_id": "bc", "source": "b", "target": "c"}]}

    def test_one_hop_is_order_independent_and_keeps_second_hop_outside(self):
        original = deepcopy(self.graph)
        expected = {"a", "ab", "b"}
        self.assertEqual(impact.expand_one_hop(self.graph, {"a"}), expected)
        self.assertEqual(impact.expand_one_hop({"edges": self.graph["edges"][::-1]}, {"a"}), expected)
        self.assertEqual(self.graph, original)

    def test_edge_retrieval_includes_endpoints_but_not_adjacent_edges(self):
        self.assertEqual(impact.expand_one_hop(self.graph, {"ab"}), {"ab", "a", "b"})

    def test_closed_edges_do_not_expand_scope(self):
        self.graph["edges"][0]["valid_to"] = 7
        self.assertEqual(impact.expand_one_hop(self.graph, {"a"}), {"a"})

    def test_unrelated_pool_keeps_original_protection_and_lifecycle_rules(self):
        graph = {"nodes": [{"node_id": name, "lifecycle": life, "valid_to": end}
                            for name, life, end in [("outside", "confirmed", None), ("inside", "confirmed", None),
                                                   ("protected", "confirmed", None), ("bound", "candidate", None),
                                                   ("closed", "confirmed", 1), ("sleep", "dormant", None)]]}
        self.assertEqual(impact.unrelated_pool(graph, {"protected_id": "protected"}, {"inside"}, ["bound"]), ["outside"])

    def test_shared_mask_removes_changes_confined_to_rejected_candidates(self):
        before, after = [0.2, 0.3, 0.5], [0.1, 0.15, 0.75]
        self.assertGreater(impact.distribution_difference(before, after)["tv"], 0)
        a = impact.masked_probability(before, [True, True, False])
        b = impact.masked_probability(after, [True, True, False])
        self.assertEqual(impact.distribution_difference(a, b), {"tv": 0, "argmax_changed": False})
        with self.assertRaises(ValueError):
            impact.masked_probability(before, [False, False, False])

    def test_retrieval_queries_are_preserved_and_union_is_not_recursively_expanded(self):
        self.graph["nodes"] = [{"node_id": n, "node_type": "entity"} for n in ("a", "b", "c")]
        event = {"proposal_observation": {"node_query": "n", "edge_query": "e", "place_query": "p", "merge_queries": ["m"]}}
        calls = []
        def rank(ids, query, ev, *, kind):
            calls.append((query, kind))
            return ["a"] if kind == "node" else []
        self.assertEqual(impact.diagnostic_scope(self.graph, event, 3, rank), {"a", "ab", "b"})
        self.assertEqual(calls, [("n", "node"), ("e", "edge"), ("p", "place"), ("m", "merge-scope-0")])

    def toy_step(self):
        graph = deepcopy(self.graph)
        graph["nodes"] = [{"node_id": n, "node_type": "entity"} for n in ("a", "b", "c")]
        event = {"proposal_observation": {"node_query": 0, "edge_query": 0, "place_query": 0,
                                           "merge_queries": [], "unrelated_context_active": False}}
        scope = {"a", "ab", "b", "bc", "c"}
        step = {"online": {"prior_world": graph}, "event_spec": event, "current_evidence_scope_ids": list(scope),
                "candidate_energies": [{"collateral": 0.0, "total": 0.0, "masked": False} for _ in range(2)],
                "executed_candidates": [{"post_graph": {"touched": n}, "legal": True, "static_preflight_pass": True}
                                        for n in ("a", "c")],
                "teacher_posterior": [0.5, 0.5], "step_index": 0, "scenario_family": "fixture"}
        def posterior(energies, temperature):
            values = [math.exp(-e["total"]/temperature) for e in energies]
            return [v/sum(values) for v in values]
        rollout = SimpleNamespace(_current_online_evidence_scope=lambda *a, **kw: scope,
                                  _rank_by_observation=lambda ids, q, e, kind: ["a"] if kind == "node" else [],
                                  _collateral_mutation=lambda base, post, s: float(post["touched"] not in s),
                                  _teacher_posterior=posterior)
        hard = {"candidates": {"proposal_retrieval": {"enumerated_ranks": 3}},
                "energy": {"weights": {"collateral": 1.0}, "temperature": 1.0}}
        return step, hard, rollout

    def test_fixed_candidate_rescoring_preserves_inputs_and_changes_posterior(self):
        step, hard, rollout = self.toy_step()
        original = deepcopy(step)
        row = impact.inspect_step(step, hard, rollout)
        self.assertEqual(row["collateral_changes"], [{"candidate_index": 1, "old": 0.0, "new": 1.0, "admissible": True}])
        self.assertAlmostEqual(row["fixed_candidates_shared_mask_posterior"]["tv"], 1/(1+math.exp(-1))-0.5)
        self.assertEqual(step, original)

    def test_cache_energy_disagreement_fails_instead_of_reporting_new_impact(self):
        step, hard, rollout = self.toy_step()
        step["candidate_energies"][0]["collateral"] = 2.0
        with self.assertRaisesRegex(ValueError, "cached collateral"):
            impact.inspect_step(step, hard, rollout)


if __name__ == "__main__":
    unittest.main()
