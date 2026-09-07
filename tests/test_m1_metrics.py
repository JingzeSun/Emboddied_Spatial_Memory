"""Hand-checkable M1 graph metric and paired-statistics tests."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from cpmt.m1_data import generate_m1_split
from cpmt.m1_metrics import (
    active_world_record_metrics, evaluate_selected_candidate,
    endpoint_viability_assessment, graph_error_counts, holm_bonferroni,
    open_memory_record_metrics, paired_stratified_bootstrap,
    rollout_graph_metrics,
)


class TestM1Metrics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = json.loads(
            (PROJECT / "configs" / "m1_hard_condition.json").read_text(encoding="utf-8")
        )
        _, cls.audit, _ = generate_m1_split(
            config, "validation", groups_per_family=2,
        )

    def test_reference_choice_is_exact_and_wrong_choice_is_visible(self):
        for record in self.audit:
            correct = evaluate_selected_candidate(
                record, record["reference_program_index"]
            )
            self.assertEqual(correct["post_graph_correct"], 1.0)
            self.assertEqual(correct["memory_contamination"], 0.0)
            wrong_index = next(
                item["candidate_index"]
                for item in record["executed_candidates"]
                if item["legal"]
                and item["candidate_index"] != record["reference_program_index"]
            )
            wrong = evaluate_selected_candidate(record, wrong_index)
            self.assertEqual(wrong["post_graph_correct"], 0.0)

    def test_illegal_choice_is_reported_and_falls_back_without_commit(self):
        record = next(
            row for row in self.audit
            if any(not item["legal"] for item in row["executed_candidates"])
        )
        illegal_index = next(
            item["candidate_index"]
            for item in record["executed_candidates"] if not item["legal"]
        )
        metrics = evaluate_selected_candidate(record, illegal_index)
        self.assertEqual(metrics["raw_invalid_program"], 1.0)
        self.assertEqual(metrics["committed"], 0.0)

    def test_false_birth_and_contamination_are_separate(self):
        record = next(row for row in self.audit if row["case_family"] == "C01")
        reference = record["executed_candidates"][
            record["reference_program_index"]
        ]["post_graph"]
        predicted = deepcopy(reference)
        predicted["nodes"].append({
            "node_id": "extra", "node_version_id": "extra@0",
            "node_type": "entity", "lifecycle": "candidate",
            "valid_from": 5, "valid_to": None, "canonical_id": None,
            "predecessor_ids": [], "evidence_refs": ["ev:extra"],
            "latent_refs": ["latent:extra"], "provenance": ["test"],
        })
        predicted["edges"].append({
            "edge_id": "extra-place", "edge_version_id": "extra-place@0",
            "source": "extra", "target": "place:wrong", "relation": "located_at",
            "frame": "world", "valid_from": 5, "valid_to": None,
            "evidence_refs": ["ev:extra"], "provenance": ["test"],
        })
        metrics = graph_error_counts(
            predicted, reference, record["online"]["prior_world"], [],
        )
        self.assertEqual(metrics["false_birth_growth"], 1.0)
        self.assertEqual(metrics["memory_contamination"], 1.0)
        self.assertEqual(metrics["extra_open_fact_error"], 1.0)
        self.assertEqual(metrics["missing_open_fact_error"], 0.0)

    def test_false_birth_set_difference_cannot_be_cancelled_by_deletion(self):
        record = next(row for row in self.audit if row["case_family"] == "C01")
        reference = deepcopy(record["executed_candidates"][
            record["reference_program_index"]
        ]["post_graph"])
        predicted = deepcopy(reference)
        removed = next(
            node for node in predicted["nodes"]
            if node["node_type"] == "entity"
            and node.get("valid_to") is None
            and node["lifecycle"] not in {"retracted", "alias"}
        )
        removed["valid_to"] = 9
        predicted["nodes"].append({
            "node_id": "false-extra", "node_version_id": "false-extra@0",
            "node_type": "entity", "lifecycle": "candidate",
            "valid_from": 9, "valid_to": None, "canonical_id": None,
            "predecessor_ids": [], "evidence_refs": ["ev:false-extra"],
            "latent_refs": ["latent:false-extra"], "provenance": ["test"],
        })
        metrics = graph_error_counts(predicted, reference, reference, [])
        self.assertEqual(metrics["false_birth_growth"], 1.0)
        self.assertEqual(metrics["missing_open_entities"], 1.0)

    def test_rollout_separates_new_wrong_writes_from_stale_retention(self):
        record = self.audit[0]
        reference = deepcopy(record["executed_candidates"][
            record["reference_program_index"]
        ]["post_graph"])
        wrong = deepcopy(reference)
        extra = deepcopy(next(
            edge for edge in wrong["edges"] if edge.get("valid_to") is None
        ))
        extra["edge_id"] = "test:wrong-write"
        extra["edge_version_id"] = "test:wrong-write@v0"
        extra["target"] = "place:test-wrong-target"
        wrong["edges"].append(extra)
        states = [wrong] * 20
        bases = [reference] + [wrong] * 19
        metrics = rollout_graph_metrics(
            states, [reference] * 20, bases, [[]] * 20, horizon=20,
        )
        self.assertEqual(
            metrics["terminal_extra_open_fact_error_per_100_decisions"],
            5.0,
        )
        self.assertEqual(
            metrics["new_incorrect_open_fact_write_auc_per_100_decisions"],
            5.0,
        )
        self.assertEqual(
            metrics["retained_stale_open_fact_auc_per_100_decisions"],
            95.0,
        )
        self.assertEqual(
            metrics["extra_open_fact_error_auc_per_100_decisions"],
            100.0,
        )
        self.assertEqual(
            metrics["memory_contamination_auc_per_100_decisions"],
            metrics["extra_open_fact_error_auc_per_100_decisions"],
        )

    def test_rollout_requires_real_frozen_horizon(self):
        record = self.audit[0]
        reference = record["executed_candidates"][
            record["reference_program_index"]
        ]["post_graph"]
        states = [reference] * 20
        bases = [record["online"]["prior_world"]] * 20
        metrics = rollout_graph_metrics(states, states, bases, [[]] * 20, horizon=20)
        self.assertEqual(metrics["final_post_graph_correctness"], 1.0)
        self.assertEqual(metrics["final_active_graph_correctness"], 1.0)
        self.assertEqual(metrics["final_graded_active_world_correctness"], 1.0)
        self.assertEqual(metrics["active_node_state_error_per_100"], 0.0)
        self.assertEqual(metrics["final_history_exactness"], 1.0)
        self.assertEqual(metrics["memory_contamination_per_100"], 0.0)
        with self.assertRaisesRegex(ValueError, "ordered sequence"):
            rollout_graph_metrics(states[:19], states[:19], bases[:19], [[]] * 19,
                                  horizon=20)

    def test_graded_active_world_metric_exposes_node_only_error(self):
        record = self.audit[0]
        reference = record["executed_candidates"][
            record["reference_program_index"]
        ]["post_graph"]
        predicted = deepcopy(reference)
        active_node = next(
            node for node in predicted["nodes"] if node.get("valid_to") is None
        )
        active_node["lifecycle"] = "retracted"
        metrics = graph_error_counts(predicted, reference, reference, [])
        self.assertEqual(metrics["memory_contamination"], 0.0)
        self.assertEqual(metrics["missing_open_facts"], 0.0)
        self.assertEqual(metrics["active_graph_correct"], 0.0)
        self.assertLess(metrics["graded_active_world_correctness"], 1.0)
        self.assertEqual(metrics["active_node_state_symmetric_difference"], 2.0)
        self.assertEqual(metrics["active_edge_state_symmetric_difference"], 0.0)

    def test_graded_active_world_metric_preserves_duplicate_edges(self):
        record = self.audit[0]
        reference = deepcopy(record["executed_candidates"][
            record["reference_program_index"]
        ]["post_graph"])
        duplicate = deepcopy(next(
            edge for edge in reference["edges"] if edge.get("valid_to") is None
        ))
        duplicate["edge_id"] = "test:duplicate-semantic-edge"
        duplicate["edge_version_id"] = "test:duplicate-semantic-edge@v0"
        predicted = deepcopy(reference)
        predicted["edges"].append(duplicate)
        graded = active_world_record_metrics(predicted, reference)
        self.assertLess(graded["graded_active_world_correctness"], 1.0)
        self.assertEqual(graded["active_edge_state_symmetric_difference"], 1.0)
        self.assertEqual(
            graded["active_record_union_count"],
            graded["active_reference_record_count"] + 1.0,
        )

    def test_open_memory_grade_exposes_evidence_only_error(self):
        record = self.audit[0]
        reference = deepcopy(record["executed_candidates"][
            record["reference_program_index"]
        ]["post_graph"])
        predicted = deepcopy(reference)
        active_node = next(
            node for node in predicted["nodes"]
            if node.get("valid_to") is None and node.get("evidence_refs")
        )
        active_node["evidence_refs"] = [
            *active_node["evidence_refs"], "test:evidence-only-error",
        ]
        active = active_world_record_metrics(predicted, reference)
        support = open_memory_record_metrics(predicted, reference)
        self.assertEqual(active["graded_active_world_correctness"], 1.0)
        self.assertLess(support["graded_open_memory_correctness"], 1.0)
        self.assertEqual(
            support["open_evidence_attachment_symmetric_difference"], 1.0,
        )

    def test_collateral_union_keeps_both_components_visible(self):
        record = self.audit[0]
        reference = record["executed_candidates"][
            record["reference_program_index"]
        ]["post_graph"]
        states = [reference] * 20
        metrics = rollout_graph_metrics(
            states, states, states, [[]] * 20, horizon=20,
            unrelated_collateral_by_step=[1.0] + [0.0] * 19,
        )
        self.assertEqual(metrics["protected_collateral_violation_per_100"], 0.0)
        self.assertEqual(metrics["unrelated_collateral_violation_per_100"], 5.0)
        self.assertEqual(metrics["collateral_violation_per_100"], 5.0)

    def test_active_recovery_is_not_erased_by_retained_wrong_history(self):
        record = self.audit[0]
        reference = record["executed_candidates"][
            record["reference_program_index"]
        ]["post_graph"]
        wrong = deepcopy(reference)
        source = next(
            edge for edge in wrong["edges"] if edge.get("valid_to") is None
        )
        extra = deepcopy(source)
        extra["edge_id"] = "test:temporary-wrong-edge"
        extra["edge_version_id"] = "test:temporary-wrong-edge@v0"
        extra["evidence_refs"] = ["test:wrong-evidence"]
        wrong["edges"].append(extra)
        recovered = deepcopy(wrong)
        recovered["edges"][-1]["valid_to"] = 7

        single = graph_error_counts(recovered, reference, reference, [])
        self.assertEqual(single["active_graph_correct"], 1.0)
        self.assertEqual(single["open_memory_correct"], 1.0)
        self.assertEqual(single["history_exact"], 0.0)

        states = [reference] * 4 + [wrong, recovered] + [recovered] * 14
        metrics = rollout_graph_metrics(
            states, [reference] * 20, [reference] * 20, [[]] * 20,
            horizon=20, recovery_window=3,
        )
        self.assertEqual(metrics["first_active_error_step"], 4.0)
        self.assertEqual(metrics["time_to_first_recovery"], 1.0)
        self.assertEqual(metrics["recovered_within_window"], 1.0)
        self.assertEqual(metrics["any_first_error_time_to_recovery"], 1.0)
        self.assertEqual(
            metrics["any_first_error_recovered_within_window"], 1.0,
        )
        self.assertEqual(metrics["final_active_graph_correctness"], 1.0)
        self.assertEqual(metrics["final_history_exactness"], 0.0)

    def test_bootstrap_preserves_group_and_effect_direction(self):
        rows = []
        for family in ("C00", "C01"):
            for group in range(3):
                for sibling in range(2):
                    rows.append({
                        "scenario_family": family,
                        "paired_group_id": f"{family}:{group}",
                        "A": {"correct": 1.0, "contamination": 0.0},
                        "C": {"correct": 0.5, "contamination": 2.0},
                    })
        correctness = paired_stratified_bootstrap(
            rows, "A", "C", "correct", higher_is_better=True,
            resamples=200, seed=7,
        )
        contamination = paired_stratified_bootstrap(
            rows, "A", "C", "contamination", higher_is_better=False,
            resamples=200, seed=7,
        )
        self.assertEqual(correctness["effect"], 0.5)
        self.assertEqual(contamination["effect"], 2.0)
        self.assertEqual(correctness["paired_groups"], 6.0)
        self.assertGreater(correctness["ci_low"], 0)
        thresholded = paired_stratified_bootstrap(
            rows, "A", "C", "correct", higher_is_better=True,
            resamples=200, minimum_effect=0.9, seed=7,
        )
        self.assertGreaterEqual(
            thresholded["one_sided_p_at_or_below_minimum"],
            correctness["one_sided_p_at_or_below_minimum"],
        )

    def test_holm_adjustment_is_monotone(self):
        adjusted = holm_bonferroni({"A_vs_C": 0.01, "A_vs_E": 0.04})
        self.assertAlmostEqual(adjusted["A_vs_C"], 0.02)
        self.assertAlmostEqual(adjusted["A_vs_E"], 0.04)

    def test_endpoint_viability_switch_ignores_winner_direction(self):
        rows = []
        for group in range(10):
            for method in ("A", "C", "E", "F"):
                exact = 1.0 if method == "F" else 0.0
                graded = 1.0 if method == "F" else (
                    0.8 + 0.01 * group if method == "A" else 0.7
                )
                rows.append({
                    "paired_group_id": f"g{group}",
                    "method": method,
                    "metrics": {
                        "final_active_graph_correctness": exact,
                        "final_graded_active_world_correctness": graded,
                        "final_graded_open_memory_correctness": graded,
                        "active_node_state_error_per_100": (
                            0.0 if method == "F" else 1.0
                        ),
                        "open_fact_error_auc_per_100_decisions": (
                            0.0 if method == "F" else (
                                5.0 + 0.1 * group if method == "A" else 8.0
                            )
                        ),
                        "final_active_reference_record_count": 40.0 + group,
                    },
                })
        result = endpoint_viability_assessment(rows, expected_groups=10)
        self.assertEqual(
            result["disposition"], "switch_once_to_graded_endpoint",
        )
        self.assertEqual(
            result["selected_metric"],
            "final_graded_active_world_correctness",
        )
        self.assertFalse(result["winner_or_effect_sign_used_for_switch"])
        self.assertEqual(
            result["required_burden_metric"],
            "open_fact_error_auc_per_100_decisions",
        )
        self.assertIn(
            "open_fact_error_auc_per_100_decisions", result["by_metric"],
        )
        self.assertFalse(
            result["by_metric"]["open_fact_error_auc_per_100_decisions"][
                "A_vs_C"
            ]["higher_is_better"]
        )
        self.assertEqual(
            result["by_metric"]["final_active_graph_correctness"][
                "A_vs_C"
            ]["paired_group_standard_deviation"],
            0.0,
        )

    def test_endpoint_viability_oracle_integrity_is_hard_gate(self):
        rows = []
        for group in range(2):
            for method in ("A", "C", "E", "F"):
                rows.append({
                    "paired_group_id": str(group),
                    "method": method,
                    "metrics": {
                        "final_active_graph_correctness": (
                            0.0 if method == "F" and group == 1 else 1.0
                        ),
                        "final_graded_active_world_correctness": 1.0,
                        "final_graded_open_memory_correctness": (
                            1.0 if method == "F" else (
                                0.9 + 0.01 * group if method == "A" else 0.8
                            )
                        ),
                        "active_node_state_error_per_100": 0.0,
                        "open_fact_error_auc_per_100_decisions": (
                            0.0 if method == "F" else (
                                5.0 + 0.1 * group if method == "A" else 8.0
                            )
                        ),
                        "final_active_reference_record_count": 30.0,
                    },
                })
        result = endpoint_viability_assessment(rows, expected_groups=2)
        self.assertEqual(
            result["disposition"], "abort_oracle_integrity_failure",
        )
        self.assertFalse(result["oracle_integrity_pass"])


if __name__ == "__main__":
    unittest.main()
