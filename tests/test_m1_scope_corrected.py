"""Scope regression and version guards; dictionary operations only."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from cpmt.m1_protocol import (load_and_validate, protocol_sha256, rollout_source_binding,
                             validate_current_rollout_protocol, validate_m1_protocol, validate_rollout_source)
from cpmt.m1_rollout import (_current_online_evidence_scope, _proposal_context,
                            _collateral_mutation, generate_m1_paired_rollout_split,
                            materialize_rollout_step)


class TestCorrectedScope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hard = load_and_validate(PROJECT / "configs/m1_hard_condition_v7.json")
        cls.legacy = load_and_validate(PROJECT / "configs/m1_hard_condition.json")
        cls.snapshot = json.loads((PROJECT / "results/m1_v6_d050_s5_generation_failure.json").read_text())["diagnostic_report"]["failure_snapshot"]

    def test_corrected_contract_changes_only_version_and_explicit_scope(self):
        expected = deepcopy(self.legacy)
        expected["protocol"] = self.hard["protocol"]
        expected["data"]["dataset_version"] = self.hard["data"]["dataset_version"]
        expected["energy"]["current_online_evidence_scope"] = self.hard["energy"]["current_online_evidence_scope"]
        self.assertEqual(expected, self.hard)
        plan = json.loads((PROJECT / "configs/m1_scope_rebuild_plan.json").read_text())
        self.assertEqual(plan["corrected_source"]["protocol_sha256"], protocol_sha256(self.hard))
        self.assertNotEqual(protocol_sha256(self.legacy), protocol_sha256(self.hard))
        from cpmt.m1_scope_rebuild import validate_rebuild_test_marker
        marker = {"schema_version": "cpmt-scope-rebuild-tests-v1",
                  "corrected_protocol_sha256": protocol_sha256(self.hard), "rebuild_plan_sha256": protocol_sha256(plan),
                  "tests_run": 280, "expected_tests": 280, "exit_code": 0, "failures": 0, "errors": 0, "skipped": 0,
                  "source_tree_unchanged": True, "test_access": False, "validation_confirmation_run": False,
                  "new_confirmation_groups_generated": False, "source_and_tests_sha256": "a"*64,
                  "provenance": {"git_dirty": False}}
        with patch("cpmt.run_provenance.source_tree_sha256", return_value="a"*64):
            validate_rebuild_test_marker(marker, PROJECT, plan, expected_tests=280)
            for field, value in (("source_and_tests_sha256", "b"*64), ("rebuild_plan_sha256", "0"*64),
                                 ("exit_code", 1), ("tests_run", 279), ("test_access", True)):
                with self.assertRaises(ValueError):
                    validate_rebuild_test_marker(dict(marker, **{field: value}), PROJECT, plan, expected_tests=280)

    def test_recursive_or_order_dependent_contracts_are_rejected(self):
        for field, value in (("recursive_expansion", True), ("edge_record_order_invariant", False),
                             ("candidate_independent", False), ("enumerated_ranks", 4)):
            changed = deepcopy(self.hard)
            changed["energy"]["current_online_evidence_scope"][field] = value
            with self.assertRaises(ValueError):
                validate_m1_protocol(changed)

    def test_old_contract_remains_readable_but_cannot_generate_corrected_data(self):
        validate_m1_protocol(self.legacy)
        with patch("cpmt.m1_rollout._generate_sequence") as generate:
            with self.assertRaisesRegex(ValueError, "historical only"):
                generate_m1_paired_rollout_split(self.legacy, "train", paired_groups=1)
            generate.assert_not_called()

    def test_old_audit_rejected_before_materializing_candidates(self):
        with patch("cpmt.m1_rollout.generate_fixed_candidates") as generate:
            with self.assertRaisesRegex(ValueError, "legacy/unversioned"):
                materialize_rollout_step({"steps": []}, {}, 0)
            generate.assert_not_called()

    def test_source_binding_rejects_wrong_dataset_or_config_hash(self):
        binding = rollout_source_binding(self.hard)
        validate_rollout_source({"source_binding": binding}, self.hard)
        for field, value in (("dataset_version", self.legacy["data"]["dataset_version"]),
                             ("protocol_sha256", "0"*64)):
            with self.assertRaises(ValueError):
                validate_rollout_source({"source_binding": dict(binding, **{field: value})}, self.hard)

    def test_dataset_version_cannot_silently_stay_legacy(self):
        changed = deepcopy(self.hard)
        changed["data"]["dataset_version"] = self.legacy["data"]["dataset_version"]
        with self.assertRaisesRegex(ValueError, "v9"):
            validate_current_rollout_protocol(changed)

    @staticmethod
    def tiny_graph():
        return {"nodes": [{"node_id": n, "node_type": "entity"} for n in ("a", "b", "c")],
                "edges": [{"edge_id": "ab", "source": "a", "target": "b"},
                          {"edge_id": "bc", "source": "b", "target": "c"}]}

    @staticmethod
    def tiny_event():
        return {"proposal_observation": {"node_query": [], "edge_query": [], "place_query": [], "merge_queries": []}}

    def test_actual_function_is_one_hop_and_edge_order_invariant(self):
        graph = self.tiny_graph()
        before = deepcopy(graph)
        with patch("cpmt.m1_rollout._rank_by_observation", side_effect=lambda ids, q, e, kind: ["a"] if kind == "node" else []):
            self.assertEqual(_current_online_evidence_scope(graph, self.tiny_event(), ranks=3), {"a", "ab", "b"})
            reverse = dict(graph, edges=graph["edges"][::-1])
            self.assertEqual(_current_online_evidence_scope(reverse, self.tiny_event(), ranks=3), {"a", "ab", "b"})
        self.assertEqual(graph, before)

    def test_actual_function_expands_retrieved_edge_endpoints_once(self):
        with patch("cpmt.m1_rollout._rank_by_observation", side_effect=lambda ids, q, e, kind: ["ab"] if kind == "edge" else []):
            self.assertEqual(_current_online_evidence_scope(self.tiny_graph(), self.tiny_event(), ranks=3), {"a", "ab", "b"})

    def test_closed_edge_does_not_expand_scope(self):
        graph = self.tiny_graph()
        graph["edges"][0]["valid_to"] = 2
        with patch("cpmt.m1_rollout._rank_by_observation", side_effect=lambda ids, q, e, kind: ["a"] if kind == "node" else []):
            self.assertEqual(_current_online_evidence_scope(graph, self.tiny_event(), ranks=3), {"a"})

    def test_retained_group78_snapshot_recovers_target_without_generation(self):
        graph, event = self.snapshot["graph"], self.snapshot["event"]
        before = deepcopy(self.snapshot)
        scope = _current_online_evidence_scope(graph, event, ranks=3)
        self.assertEqual(len(scope), 40)
        reversed_graph = dict(graph, edges=graph["edges"][::-1])
        self.assertEqual(scope, _current_online_evidence_scope(reversed_graph, event, ranks=3))
        self.assertEqual(_proposal_context(graph, event)["collateral_target"], "rollout:validation:000078:entity:mover:0")
        self.assertEqual(self.snapshot, before)

    def test_outside_memory_mutation_is_visible_to_corrected_collateral(self):
        graph, event = self.snapshot["graph"], self.snapshot["event"]
        post = deepcopy(graph)
        target = next(n for n in post["nodes"] if n["node_id"] == "rollout:validation:000078:entity:mover:0")
        target["evidence_refs"] = [*target.get("evidence_refs", []), "fixture:new-evidence"]
        scope = _current_online_evidence_scope(graph, event, ranks=3)
        self.assertEqual(_collateral_mutation(graph, post, scope), 1.0)
        self.assertEqual(_collateral_mutation(graph, post, set(self.snapshot["scope_trace"]["returned_scope_ids"])), 0.0)

    def test_c11_empty_outside_pool_still_raises_without_fallback(self):
        graph, event = self.snapshot["graph"], self.snapshot["event"]
        everything = {n["node_id"] for n in graph["nodes"]}
        with patch("cpmt.m1_rollout._current_online_evidence_scope", return_value=everything):
            with self.assertRaisesRegex(ValueError, "C11 collateral stress requires"):
                _proposal_context(graph, event)

    def test_encoder_rejects_legacy_audit_before_building_arrays(self):
        from cpmt.m1_af_rollout import rollout_learning_arrays_from_audits
        with self.assertRaisesRegex(ValueError, "legacy/unversioned"):
            rollout_learning_arrays_from_audits(self.hard, [{}], future_hash_bins=32)

    def test_existing_shard_directory_is_not_overwritten_or_sent_to_workers(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("parallel_scope_guard", PROJECT / "scripts/generate_m1_parallel.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp, patch.object(module.mp, "Pool") as pool:
            directory = Path(tmp)
            retained = directory / "retained.txt"
            retained.write_text("old evidence")
            with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                module.generate_parallel(PROJECT / "configs/m1_hard_condition_v7.json", "train", 1,
                                         future_hash_bins=32, workers=1, out_dir=directory)
            pool.assert_not_called()
            self.assertEqual(retained.read_text(), "old evidence")


if __name__ == "__main__":
    unittest.main()
