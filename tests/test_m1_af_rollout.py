"""Tests for the shared A-F online adapter and causal rollout smoke."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

import numpy as np
import torch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from cpmt.dev_learning import (
    METHODS,
    OutcomeScorer,
    outcome_scorer_diagnostics,
)
from cpmt.m1_af_rollout import (
    CANDIDATE_FAILURE_TYPE_TO_CODE,
    CANDIDATE_FEATURE_DIM,
    ONLINE_CONTEXT_DIM,
    _program_touches_protected,
    build_rollout_learning_arrays,
    calibrate_shared_commit_rule,
    causal_rollout_metrics,
    online_feature_vector,
    resolve_af_smoke_config,
    run_af_seed,
    selection_error_decomposition,
    static_preflight_diagnostics,
    structured_relation_oracle_probabilities,
    structured_relation_target_only_diagnostics,
    training_inner_dev_mask,
)


class TestM1AFCausalRollout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hard = json.loads(
            (PROJECT / "configs" / "m1_hard_condition.json").read_text(
                encoding="utf-8"
            )
        )
        smoke = json.loads(
            (PROJECT / "configs" / "m1_af_smoke.json").read_text(
                encoding="utf-8"
            )
        )
        cls.config = resolve_af_smoke_config(cls.hard, smoke)
        cls.train, cls.train_audit, cls.train_summary = build_rollout_learning_arrays(
            cls.hard, "train", paired_groups=2,
            future_hash_bins=cls.config["future_hash_bins"],
        )
        cls.validation, cls.validation_audit, cls.validation_summary = (
            build_rollout_learning_arrays(
                cls.hard, "validation", paired_groups=1,
                future_hash_bins=cls.config["future_hash_bins"],
            )
        )

    def test_online_encoder_rejects_audit_and_ignores_hindsight_storage(self):
        step = self.validation_audit[0]["steps"][0]
        before = online_feature_vector(step["online"])
        changed = deepcopy(step)
        changed["future_trace"] = []
        after = online_feature_vector(changed["online"])
        np.testing.assert_array_equal(before, after)
        with self.assertRaisesRegex(ValueError, "exactly"):
            online_feature_vector(step)

    def test_same_template_candidates_are_separable_after_argument_features(self):
        """Without query-aligned arguments the three RELINK slots encode alike."""
        step = self.validation_audit[0]["steps"][0]
        vector = online_feature_vector(step["online"])
        blocks = vector[ONLINE_CONTEXT_DIM:].reshape(16, CANDIDATE_FEATURE_DIM)
        self.assertEqual(
            len(vector), ONLINE_CONTEXT_DIM + 16 * CANDIDATE_FEATURE_DIM
        )
        distinct = {tuple(np.round(block, 6)) for block in blocks}
        self.assertEqual(len(distinct), 16)

    def test_protected_touch_matches_exact_structured_ids(self):
        program = {
            "protected_ids": ["node-1"],
            "operations": [{"arguments": {"node_id": "node-10"}}],
        }
        self.assertFalse(_program_touches_protected(program))
        program["operations"][0]["arguments"]["node_id"] = "node-1"
        self.assertTrue(_program_touches_protected(program))

    def test_selection_error_splits_template_from_argument(self):
        probabilities = np.eye(16, dtype=np.float32)[self.validation["y"]]
        perfect = selection_error_decomposition(probabilities, self.validation)
        self.assertEqual(perfect["accuracy"], 1.0)
        self.assertEqual(perfect["template_accuracy"], 1.0)
        self.assertEqual(perfect["argument_error_with_correct_template"], 0.0)
        self.assertEqual(perfect["ambiguous_pair_containment"], 1.0)
        shifted = np.eye(16, dtype=np.float32)[(self.validation["y"] + 1) % 16]
        degraded = selection_error_decomposition(shifted, self.validation)
        self.assertEqual(degraded["accuracy"], 0.0)
        self.assertLessEqual(degraded["template_accuracy"], 1.0)

        outside = probabilities.copy()
        ambiguous = np.asarray(self.validation["ambiguous"], dtype=bool)
        group = int(self.validation["group"][ambiguous][0])
        mask = ambiguous & (self.validation["group"] == group)
        pair = set(int(value) for value in self.validation["y"][mask])
        third = next(index for index in range(16) if index not in pair)
        outside[mask] = np.eye(16, dtype=np.float32)[third]
        diagnosed = selection_error_decomposition(outside, self.validation)
        self.assertEqual(diagnosed["ambiguous_pair_containment"], 0.0)

        illegal = selection_error_decomposition(
            np.asarray([[0.0, 1.0], [1.0, 0.0]], dtype=np.float32),
            {
                "candidate_templates": np.asarray([[0, 1], [0, 1]]),
                "y": np.asarray([0, 1]),
                "ambiguous": np.asarray([False, False]),
                "recovery": np.asarray([False, False]),
                "group": np.asarray([0, 1]),
                "candidate_legal": np.asarray(
                    [[True, False], [False, True]], dtype=bool,
                ),
            },
        )
        self.assertEqual(illegal["raw_illegal_selection_rate"], 1.0)
        self.assertEqual(illegal["illegal_wrong_template_rate"], 1.0)
        self.assertEqual(illegal["legal_wrong_template_rate"], 0.0)

    def test_arrays_keep_exact_ambiguous_pair_and_groupwise_labels(self):
        self.assertEqual(self.train["x"].shape[0], 84)
        self.assertEqual(self.validation["x"].shape[0], 42)
        first = self.validation_audit[0]
        second = self.validation_audit[1]
        pivot = first["ambiguity_pivot_step"]
        self.assertEqual(pivot, second["ambiguity_pivot_step"])
        left_index = pivot
        right_index = 21 + pivot
        np.testing.assert_array_equal(
            self.validation["x"][left_index], self.validation["x"][right_index]
        )
        self.assertNotEqual(
            int(self.validation["y"][left_index]),
            int(self.validation["y"][right_index]),
        )
        self.assertTrue(self.validation["ambiguous"][left_index])
        self.assertTrue(self.validation["ambiguous"][right_index])
        for group in np.unique(self.train["group"]):
            labels = self.train["labelled"][self.train["group"] == group]
            self.assertEqual(len(set(labels.tolist())), 1)
        self.assertEqual(int(self.validation["recovery"].sum()), 2)
        for sequence in self.validation_audit:
            recovery = sequence["recovery_examples"]
            self.assertEqual(len(recovery), 1)
            self.assertEqual(recovery[0]["reference_template"], "RELINK")
            self.assertTrue(recovery[0]["teacher_winner_matches_reference"])

    def test_train_inner_dev_partition_keeps_complete_groups(self):
        mask = training_inner_dev_mask(self.train)
        self.assertTrue(mask.any())
        self.assertTrue((~mask).any())
        for group in np.unique(self.train["group"]):
            assignments = mask[self.train["group"] == group]
            self.assertEqual(len(set(assignments.tolist())), 1)

    def test_executed_teacher_covers_reference_and_illegal_is_masked(self):
        self.assertTrue(np.all(self.train["pstar"].argmax(axis=1) == self.train["y"]))
        self.assertTrue(np.all(self.validation["pstar"].argmax(axis=1) == self.validation["y"]))
        self.assertTrue(np.all(np.isfinite(self.train["x"])))
        self.assertTrue(np.all(np.isfinite(self.train["future"])))
        self.assertTrue(np.all((self.train["penalties"] >= 1_000_000).sum(axis=1) >= 1))
        self.assertEqual(self.train["penalties"].shape[1], 16)
        self.assertEqual(self.validation["penalties"].shape[1], 16)
        # E may use only transaction-declared costs at candidate-scoring time;
        # executor-derived illegality/collateral remains unavailable to it.
        self.assertEqual(self.train["no_execution_penalties"].shape, (84, 16))
        self.assertTrue(np.all(np.isfinite(self.train["no_execution_penalties"])))
        self.assertTrue(np.all(self.train["no_execution_penalties"] < 1_000_000))
        preflight = self.train["candidate_static_preflight_pass"]
        legal = self.train["candidate_legal"]
        self.assertEqual(preflight.shape, (84, 16))
        self.assertFalse(np.any(~preflight & legal))
        self.assertTrue(np.any(~preflight & ~legal))
        self.assertTrue(np.all(
            (self.train["candidate_execution_failure_code"] == 0) == legal
        ))
        self.assertTrue(np.all(
            (self.train["candidate_static_preflight_failure_code"] == 0)
            == preflight
        ))
        relation_dim = 3 * 6
        self.assertEqual(
            self.train["relation_targets"].shape,
            (84, 16, relation_dim),
        )
        self.assertEqual(
            self.train["relation_mask"].shape,
            self.train["relation_targets"].shape,
        )
        self.assertTrue(np.all(self.train["relation_mask"].sum(axis=2) > 0))
        np.testing.assert_array_equal(
            self.train["relation_desired"][self.train["relation_mask"] > 0],
            np.ones_like(
                self.train["relation_desired"][self.train["relation_mask"] > 0]
            ),
        )

    def test_six_method_training_and_causal_oracle_smoke(self):
        config = deepcopy(self.config)
        config["student_steps"] = 2
        config["scorer_steps"] = 2
        results, details, _ = run_af_seed(
            self.train, self.validation, self.validation_audit, config, 7,
        )
        self.assertEqual(set(results), set(METHODS))
        counts = {
            results[method]["student_parameters"]
            for method in METHODS if method != "oracle_candidate_program"
        }
        self.assertEqual(len(counts), 1)
        oracle = results["oracle_candidate_program"]
        self.assertEqual(oracle["teacher_forced"]["accuracy"], 1.0)
        self.assertEqual(
            oracle["causal_rollout"]["final_post_graph_correctness"], 1.0
        )
        self.assertIn(
            "initial_step_raw_invalid_selection_rate",
            oracle["causal_rollout"],
        )
        self.assertEqual(oracle["causal_rollout"]["memory_contamination_per_100"], 0.0)
        self.assertIn(
            "future_relation_bce", details["outcome_scorer_training"][0]
        )

    def test_observable_oracle_couples_the_ambiguous_pair(self):
        metrics, rows = causal_rollout_metrics(
            None, self.validation_audit, self.config, observable_oracle=True,
        )
        self.assertAlmostEqual(metrics["mean_active_graph_correctness"], 0.975)
        self.assertEqual(metrics["final_active_graph_correctness"], 1.0)
        self.assertEqual(metrics["final_history_exactness"], 0.5)
        choices = []
        for sequence in rows:
            pivot = self.validation_audit[
                int(sequence["metrics"]["sibling_index"])
            ]["ambiguity_pivot_step"]
            choices.append(sequence["choices"][pivot]["selected_index"])
        self.assertEqual(len(set(choices)), 1)
        revisit_choices = [
            sequence["choices"][audit["recovery_revisit_step"]]
            for sequence, audit in zip(rows, self.validation_audit, strict=True)
        ]
        corrected = [
            choice for choice in revisit_choices
            if choice["revisit_triggered"]
        ]
        self.assertEqual(len(corrected), 1)
        self.assertEqual(corrected[0]["selected_template"], "RELINK")
        self.assertEqual(corrected[0]["active_correct_after"], 1.0)
        self.assertEqual(metrics["triggered_revisit_count"], 1.0)
        self.assertEqual(metrics["triggered_revisit_commit_rate"], 1.0)
        self.assertEqual(
            metrics["triggered_revisit_active_resolution_rate"], 1.0,
        )
        self.assertEqual(metrics["designed_recovery_eligible_sequences"], 1.0)
        self.assertEqual(metrics["designed_recovery_trigger_rate"], 1.0)
        self.assertEqual(metrics["designed_recovery_rate_within_window"], 1.0)
        self.assertEqual(
            metrics["any_first_error_recovery_eligible_sequences"], 1.0,
        )
        self.assertEqual(
            metrics["any_first_error_recovery_rate_within_window"], 1.0,
        )

    def test_commit_calibration_uses_only_its_paired_group_half(self):
        probabilities = np.asarray([
            [0.6, 0.4], [0.6, 0.4], [0.6, 0.4], [0.99, 0.01],
            [0.99, 0.01],
        ], dtype=np.float32)
        arrays = {
            "calibration": np.asarray([True, True, True, False, True]),
            "recovery": np.asarray([False, False, False, False, True]),
            "candidate_legal": np.ones((5, 2), dtype=bool),
            "active_correct": np.asarray([
                [1, 0], [0, 1], [0, 1], [1, 0], [1, 0],
            ], dtype=np.float32),
            "base_active_correct": np.asarray([0, 1, 1, 0, 0], dtype=np.float32),
            "fact_errors": np.asarray([
                [0, 1], [1, 0], [1, 0], [0, 1], [0, 1],
            ], dtype=np.float32),
            "base_fact_errors": np.asarray([1, 0, 0, 1, 1], dtype=np.float32),
            "excess_nodes": np.zeros((5, 2), dtype=np.float32),
            "base_excess_nodes": np.zeros(5, dtype=np.float32),
        }
        first = calibrate_shared_commit_rule(
            {"A:seed7": probabilities}, arrays, self.hard,
        )
        self.assertEqual(first["selected"]["commit_probability"], 0.65)
        self.assertEqual(first["calibration_rows"], 3)
        self.assertEqual(first["report_rows"], 1)
        self.assertEqual(first["excluded_recovery_training_rows"], 1)
        changed = deepcopy(arrays)
        changed["active_correct"][3] = [0, 1]
        second = calibrate_shared_commit_rule(
            {"A:seed7": probabilities}, changed, self.hard,
        )
        self.assertEqual(first["selected"], second["selected"])
        changed_recovery = deepcopy(arrays)
        changed_recovery["active_correct"][4] = [0, 1]
        third = calibrate_shared_commit_rule(
            {"A:seed7": probabilities}, changed_recovery, self.hard,
        )
        self.assertEqual(first["selected"], third["selected"])

    def test_structured_relation_oracle_prefers_the_true_claim(self):
        arrays = {
            "relation_targets": np.asarray([[[1.0], [0.0]]]),
            "relation_mask": np.ones((1, 2, 1), dtype=np.float32),
            "relation_desired": np.ones((1, 2, 1), dtype=np.float32),
            "no_execution_penalties": np.zeros((1, 2), dtype=np.float32),
        }
        probabilities = structured_relation_oracle_probabilities(
            arrays, future_weight=1.0, temperature=0.25,
        )
        self.assertEqual(probabilities.shape, (1, 2))
        self.assertEqual(int(probabilities.argmax(axis=1)[0]), 0)
        self.assertAlmostEqual(float(probabilities.sum()), 1.0)

    def test_target_only_relation_diagnostic_preserves_ties(self):
        diagnostics = structured_relation_target_only_diagnostics({
            "relation_targets": np.asarray([
                [[1.0], [0.0], [0.0]],
                [[1.0], [1.0], [0.0]],
            ]),
            "relation_mask": np.ones((2, 3, 1), dtype=np.float32),
            "relation_desired": np.ones((2, 3, 1), dtype=np.float32),
            "y": np.asarray([0, 1]),
            "ambiguous": np.asarray([False, True]),
        })
        self.assertEqual(
            diagnostics["all"]["reference_in_minimum_set_rate"], 1.0,
        )
        self.assertEqual(
            diagnostics["all"]["unique_reference_minimum_rate"], 0.5,
        )
        self.assertEqual(
            diagnostics["all"]["uniform_tie_break_expected_accuracy"], 0.75,
        )
        self.assertEqual(
            diagnostics["all"]["mean_minimum_set_size"], 1.5,
        )

    def test_static_preflight_diagnostic_filters_without_using_execution_mask(self):
        protected_code = CANDIDATE_FAILURE_TYPE_TO_CODE[
            "ProtectedMutationError"
        ]
        arrays = {
            "relation_targets": np.asarray([[
                [1.0], [1.0], [0.0],
            ]]),
            "relation_mask": np.ones((1, 3, 1), dtype=np.float32),
            "relation_desired": np.ones((1, 3, 1), dtype=np.float32),
            "no_execution_penalties": np.asarray([
                [0.14, 0.05, 0.0],
            ], dtype=np.float32),
            "y": np.asarray([0]),
            "ambiguous": np.asarray([False]),
            "candidate_static_preflight_pass": np.asarray([[
                True, False, True,
            ]]),
            "candidate_legal": np.asarray([[True, False, True]]),
            "candidate_templates": np.asarray([[0, 1, 2]]),
            "candidate_execution_failure_code": np.asarray([[
                0, protected_code, 0,
            ]]),
            "candidate_static_preflight_failure_code": np.asarray([[
                0, protected_code, 0,
            ]]),
        }
        raw = structured_relation_target_only_diagnostics(arrays)
        filtered = structured_relation_target_only_diagnostics(
            arrays,
            static_preflight_pass=arrays[
                "candidate_static_preflight_pass"
            ],
        )
        self.assertEqual(
            raw["all"]["uniform_tie_break_expected_accuracy"], 0.5,
        )
        self.assertEqual(
            filtered["all"]["uniform_tie_break_expected_accuracy"], 1.0,
        )
        unfiltered_oracle = structured_relation_oracle_probabilities(
            arrays, future_weight=1.0, temperature=0.25,
        )
        filtered_oracle = structured_relation_oracle_probabilities(
            arrays, future_weight=1.0, temperature=0.25,
            static_preflight_pass=arrays[
                "candidate_static_preflight_pass"
            ],
        )
        self.assertEqual(int(unfiltered_oracle.argmax(axis=1)[0]), 1)
        self.assertEqual(int(filtered_oracle.argmax(axis=1)[0]), 0)
        audit = static_preflight_diagnostics(arrays)
        self.assertEqual(audit["illegal_detection_recall"], 1.0)
        self.assertEqual(audit["legal_false_rejection_rate"], 0.0)
        self.assertEqual(audit["reference_static_preflight_pass_rate"], 1.0)
        self.assertEqual(
            audit["relation_tie_audit"][
                "minimum_set_contains_executor_illegal_row_rate"
            ],
            1.0,
        )

    def test_outcome_scorer_diagnostics_separates_fit_and_ranking(self):
        model = OutcomeScorer(
            input_dim=6, hidden=4, future_dim=1, horizon=1,
            num_candidates=2, candidate_dim=2,
        )
        for parameter in model.parameters():
            parameter.data.zero_()
        data = {
            "x": torch.zeros((2, 6), dtype=torch.float32),
            "poses": torch.zeros((2, 1), dtype=torch.float32),
            "relation_targets": torch.tensor([
                [[1.0], [0.0]],
                [[0.0], [0.0]],
            ]),
            "relation_mask": torch.ones((2, 2, 1), dtype=torch.float32),
            "y": torch.tensor([0, 1], dtype=torch.long),
            "candidate_legal": torch.tensor([
                [True, True],
                [True, False],
            ]),
        }
        teacher = torch.tensor([[1.0, 0.0], [0.0, 1.0]])
        diagnostics = outcome_scorer_diagnostics(model, data, teacher)
        self.assertEqual(diagnostics["rows"], 2)
        self.assertAlmostEqual(diagnostics["masked_bce"], np.log(2), places=6)
        self.assertEqual(diagnostics["masked_binary_accuracy"], 0.25)
        self.assertEqual(diagnostics["teacher_accuracy"], 1.0)
        self.assertEqual(diagnostics["raw_illegal_selection_rate"], 0.5)

    def test_config_cannot_claim_formal_or_open_test(self):
        raw = json.loads(
            (PROJECT / "configs" / "m1_af_smoke.json").read_text(encoding="utf-8")
        )
        raw["test_access"] = True
        with self.assertRaisesRegex(ValueError, "test-sealed"):
            resolve_af_smoke_config(self.hard, raw)
        raw["test_access"] = False
        raw["formal_run"] = True
        with self.assertRaisesRegex(ValueError, "nonformal"):
            resolve_af_smoke_config(self.hard, raw)


if __name__ == "__main__":
    unittest.main()
