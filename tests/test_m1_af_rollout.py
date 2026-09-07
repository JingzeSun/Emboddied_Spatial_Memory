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
    OnlineModel,
    OutcomeScorer,
    SCORER_DIAGNOSTIC_POLICY,
    apply_candidate_admissibility_to_probabilities,
    masked_candidate_logits,
    masked_candidate_probabilities,
    outcome_scorer_diagnostics,
)
from cpmt.m1_af_rollout import (
    CANDIDATE_FAILURE_TYPE_TO_CODE,
    CANDIDATE_FEATURE_DIM,
    ONLINE_CONTEXT_DIM,
    TEMPLATES,
    _program_touches_protected,
    build_rollout_learning_arrays,
    calibrate_shared_commit_rule,
    candidate_current_relation_targets,
    causal_rollout_metrics,
    current_now_comparability_diagnostics,
    mechanism_slice_selection_diagnostics,
    online_feature_vector,
    posterior_term_influence_diagnostics,
    resolve_af_smoke_config,
    run_af_seed,
    selection_error_decomposition,
    static_preflight_diagnostics,
    structured_relation_oracle_probabilities,
    structured_relation_target_only_diagnostics,
    training_inner_dev_mask,
    uniform_admissible_random_accuracy,
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

    def test_set_transformer_is_candidate_permutation_equivariant(self):
        torch.manual_seed(17)
        batch, candidates, context_dim, candidate_dim = 2, 4, 5, 3
        future_dim, horizon, relation_dim = 6, 2, 5
        context = torch.randn(batch, context_dim)
        blocks = torch.randn(batch, candidates, candidate_dim)
        x = torch.cat((context, blocks.reshape(batch, -1)), dim=1)
        poses = torch.randn(batch, horizon)
        permutation = torch.tensor([2, 0, 3, 1])
        permuted_x = torch.cat((
            context, blocks[:, permutation].reshape(batch, -1),
        ), dim=1)
        model = OnlineModel(
            x.shape[1], 8, future_dim, horizon,
            num_candidates=candidates, candidate_dim=candidate_dim,
            relation_dim=relation_dim,
            architecture="cross_candidate_set_transformer_v1",
            attention_heads=2, set_attention_blocks=2,
            feedforward_dim=16, dropout=0.0,
        ).eval()
        scorer = OutcomeScorer(
            x.shape[1], 8, relation_dim, horizon,
            num_candidates=candidates, candidate_dim=candidate_dim,
            architecture="cross_candidate_set_transformer_v1",
            attention_heads=2, set_attention_blocks=2,
            feedforward_dim=16, dropout=0.0,
        ).eval()
        with torch.no_grad():
            torch.testing.assert_close(
                model(permuted_x), model(x)[:, permutation],
            )
            torch.testing.assert_close(
                model.structured_relation_prediction(permuted_x, poses),
                model.structured_relation_prediction(x, poses)[:, permutation],
            )
            torch.testing.assert_close(
                scorer.predict_candidates(permuted_x, poses),
                scorer.predict_candidates(x, poses)[:, permutation],
            )

    def test_registered_primary_architecture_settings_are_resolved(self):
        smoke = json.loads(
            (PROJECT / "configs" / "m1_af_smoke.json").read_text(
                encoding="utf-8"
            )
        )
        smoke["architecture"] = "cross_candidate_set_transformer_v1"
        resolved = resolve_af_smoke_config(self.hard, smoke)
        expected = self.hard["architecture_evaluation"][
            "cross_candidate_set_transformer_v1"
        ]
        self.assertEqual(resolved["hidden_dim"], expected["model_dim"])
        self.assertEqual(
            resolved["attention_heads"], expected["attention_heads"],
        )
        self.assertEqual(
            resolved["set_attention_blocks"],
            expected["set_attention_blocks"],
        )
        smoke["architecture"] = "unregistered"
        with self.assertRaisesRegex(ValueError, "unregistered"):
            resolve_af_smoke_config(self.hard, smoke)

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
        self.assertEqual(self.train["x"].shape[0], 80)
        self.assertEqual(self.validation["x"].shape[0], 40)
        first = self.validation_audit[0]
        second = self.validation_audit[1]
        pivot = first["ambiguity_pivot_step"]
        self.assertEqual(pivot, second["ambiguity_pivot_step"])
        left_index = pivot
        right_index = 20 + pivot
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

    def test_current_proxy_audit_uses_common_support_and_is_reference_blind(self):
        audit = current_now_comparability_diagnostics(
            self.train, self.hard["data"]["scenario_families"],
        )
        self.assertGreater(audit["common_support_rows"], 0)
        self.assertGreater(audit["executed_now_unavailable_online_rows"], 0)
        self.assertEqual(
            audit["exact_ambiguity_current_target_identity_rate"], 1.0,
        )
        self.assertFalse(audit["strength_cap_enforced"])
        self.assertEqual(
            audit["by_family"]["C10"]["proxy"][
                "reference_in_minimum_set_rate"
            ],
            0.5,
        )

        step = next(
            step for sequence in self.train_audit for step in sequence["steps"]
            if step["scenario_family"] == "C10"
        )
        program = step["online"]["candidate_programs"][0]
        baseline = candidate_current_relation_targets(
            program, step["online"],
            self.hard["future"]["no_execution_now_target_policy"],
        )
        changed = deepcopy(step["online"])
        changed["audit_only_reference_program_index"] = (
            step["reference_program_index"] + 1
        ) % 16
        changed["audit_only_future"] = ["mutated"]
        after = candidate_current_relation_targets(
            program, changed,
            self.hard["future"]["no_execution_now_target_policy"],
        )
        for left, right in zip(baseline, after, strict=True):
            np.testing.assert_array_equal(left, right)

    def test_executed_teacher_covers_reference_and_illegal_is_masked(self):
        health_minimum = self.hard["energy"]["teacher_health_gate"][
            "reference_agreement_overall_minimum"
        ]
        self.assertGreaterEqual(
            float(np.mean(self.train["pstar"].argmax(axis=1) == self.train["y"])),
            health_minimum,
        )
        self.assertGreaterEqual(
            float(np.mean(
                self.validation["pstar"].argmax(axis=1)
                == self.validation["y"]
            )),
            health_minimum,
        )
        self.assertEqual(self.train["teacher_matches_reference"].shape, (80,))
        self.assertEqual(self.train["scenario_family_index"].shape, (80,))
        self.assertEqual(
            set(self.train["scenario_family_index"]), set(range(12)) | {-1},
        )
        for term in (
            "now", "future", "edit", "growth", "collateral", "illegal",
            "now_raw", "now_natural_range", "future_raw",
        ):
            self.assertEqual(
                self.train[f"candidate_energy_{term}"].shape, (80, 16),
            )
        self.assertTrue(np.all(np.isfinite(self.train["x"])))
        self.assertTrue(np.all(np.isfinite(self.train["future"])))
        self.assertTrue(np.all((self.train["penalties"] >= 1_000_000).sum(axis=1) >= 1))
        self.assertEqual(self.train["penalties"].shape[1], 16)
        self.assertEqual(self.validation["penalties"].shape[1], 16)
        # E may use only transaction-declared costs at candidate-scoring time;
        # executor-derived illegality/collateral remains unavailable to it.
        self.assertEqual(self.train["no_execution_penalties"].shape, (80, 16))
        self.assertTrue(np.all(np.isfinite(self.train["no_execution_penalties"])))
        self.assertTrue(np.all(self.train["no_execution_penalties"] < 1_000_000))
        preflight = self.train["candidate_static_preflight_pass"]
        legal = self.train["candidate_legal"]
        self.assertEqual(preflight.shape, (80, 16))
        self.assertFalse(np.any(~preflight & legal))
        self.assertTrue(np.any(~preflight & ~legal))
        rows = np.arange(len(self.train["y"]))
        self.assertTrue(np.all(preflight[rows, self.train["y"]]))
        self.assertTrue(np.all(preflight.any(axis=1)))
        self.assertTrue(np.all(
            (self.train["candidate_execution_failure_code"] == 0) == legal
        ))
        self.assertTrue(np.all(
            (self.train["candidate_static_preflight_failure_code"] == 0)
            == preflight
        ))
        current_relation_dim = 3
        relation_dim = current_relation_dim + 3 * 6
        self.assertEqual(
            self.train["relation_targets"].shape,
            (80, 16, relation_dim),
        )
        self.assertEqual(
            self.train["relation_mask"].shape,
            self.train["relation_targets"].shape,
        )
        self.assertTrue(np.all(self.train["relation_mask"].sum(axis=2) > 0))
        active_desired = self.train["relation_desired"][
            self.train["relation_mask"] > 0
        ]
        self.assertTrue(np.all(np.isin(active_desired, [0.0, 1.0])))
        current_mask = self.train["relation_mask"][:, :, :current_relation_dim]
        current_desired = self.train["relation_desired"][
            :, :, :current_relation_dim
        ][current_mask > 0]
        self.assertTrue(np.any(current_desired == 0.0))
        future_mask = self.train["relation_mask"][:, :, current_relation_dim:]
        future_desired = self.train["relation_desired"][
            :, :, current_relation_dim:
        ][future_mask > 0]
        np.testing.assert_array_equal(
            future_desired, np.ones_like(future_desired),
        )

    def test_fixed_current_scale_and_soft_posterior_influence_are_audited(self):
        audit = current_now_comparability_diagnostics(
            self.train, self.hard["data"]["scenario_families"],
        )
        scaling = audit["fixed_natural_range_scaling"]
        self.assertTrue(scaling["all_available_values_within_0_1"])
        self.assertLessEqual(
            scaling["maximum_absolute_scaling_error"], 1e-6,
        )
        self.assertTrue(set(scaling["natural_ranges"]) <= {1.0, 2.0, 4.0})

        contract = self.hard["energy"]["posterior_influence_audit"]
        influence = posterior_term_influence_diagnostics(
            self.train,
            weights=self.hard["energy"]["weights"],
            temperature=self.hard["energy"]["temperature"],
            scenario_families=self.hard["data"]["scenario_families"],
            terms=contract["terms"],
            total_variation_thresholds=contract[
                "total_variation_thresholds"
            ],
        )
        self.assertEqual(influence["interpretation"],
                         "posterior_distribution_not_argmax_only")
        self.assertEqual(set(influence["terms"]), set(contract["terms"]))
        self.assertGreater(
            influence["terms"]["now"]["all"]["total_variation"]["mean"],
            0.0,
        )

    def test_mechanism_slices_are_complete_and_descriptive(self):
        report = mechanism_slice_selection_diagnostics(
            self.train["pstar"], self.train,
            self.hard["evaluation"]["mechanism_diagnostic_slices"],
            commit_probability=0.0, margin_threshold=0.0,
        )
        self.assertFalse(report["primary_gate"])
        self.assertEqual(
            set(report["slices"]),
            set(self.hard["evaluation"]["mechanism_diagnostic_slices"][
                "precedence"
            ]),
        )
        self.assertTrue(all(
            item["rows"] > 0 for item in report["slices"].values()
        ))
        self.assertEqual(
            report["slices"]["temporal_underdetermination"]["definition"],
            "scenario_family_equals_C10",
        )

    def test_every_generated_row_has_an_admitted_noop_fallback(self):
        noop_index = TEMPLATES.index("NOOP")
        for arrays in (self.train, self.validation):
            noop = arrays["candidate_templates"] == noop_index
            self.assertTrue(np.all(noop.any(axis=1)))
            self.assertTrue(np.all(arrays["candidate_static_preflight_pass"][noop]))
            self.assertTrue(np.all(
                (noop & arrays["candidate_static_preflight_pass"]).any(axis=1)
            ))

    def test_masked_random_floor_uses_each_rows_effective_k(self):
        admitted = np.asarray([
            [True, True, False, False],
            [True, True, True, True],
        ])
        self.assertAlmostEqual(
            uniform_admissible_random_accuracy(admitted),
            (1 / 2 + 1 / 4) / 2,
        )
        self.assertEqual(
            SCORER_DIAGNOSTIC_POLICY["primary_bce_mismatch_diagnostic"],
            "ranking_relevant_bce",
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
        for method in METHODS:
            causal = results[method]["causal_rollout"]
            self.assertEqual(
                causal["raw_static_rejected_selection_rate"], 0.0,
            )
            self.assertEqual(
                set(causal["mechanism_diagnostic_slices"]["slices"]),
                set(self.hard["evaluation"][
                    "mechanism_diagnostic_slices"
                ]["precedence"]),
            )
            self.assertFalse(
                causal["mechanism_diagnostic_slices"]["primary_gate"]
            )
        self.assertEqual(
            oracle["causal_rollout"]["memory_contamination_per_100"], 0.0,
        )
        self.assertIn(
            "current_future_relation_bce",
            details["outcome_scorer_training"][0],
        )

    def test_set_transformer_runs_full_a_to_f_with_matched_students(self):
        raw = json.loads(
            (PROJECT / "configs" / "m1_af_smoke.json").read_text(
                encoding="utf-8"
            )
        )
        raw["architecture"] = "cross_candidate_set_transformer_v1"
        config = resolve_af_smoke_config(self.hard, raw)
        config.update(student_steps=1, scorer_steps=1, batch_size=8)
        results, _, models = run_af_seed(
            self.train, self.validation, self.validation_audit, config, 7,
        )
        self.assertEqual(set(results), set(METHODS))
        counts = {
            results[method]["student_parameters"]
            for method in METHODS if method != "oracle_candidate_program"
        }
        self.assertEqual(len(counts), 1)
        for method in METHODS:
            if method != "oracle_candidate_program":
                self.assertEqual(
                    models[method].architecture,
                    "cross_candidate_set_transformer_v1",
                )

    def test_shared_candidate_mask_keeps_slots_and_zeroes_rejections(self):
        logits = torch.tensor([[0.0, 100.0, 1.0]], dtype=torch.float32)
        admissible = torch.tensor([[True, False, True]])
        masked_logits = masked_candidate_logits(logits, admissible)
        self.assertEqual(tuple(masked_logits.shape), (1, 3))
        self.assertTrue(torch.isneginf(masked_logits[0, 1]))
        probabilities = masked_candidate_probabilities(logits, admissible)
        self.assertEqual(float(probabilities[0, 1]), 0.0)
        self.assertAlmostEqual(float(probabilities.sum()), 1.0, places=6)
        existing = apply_candidate_admissibility_to_probabilities(
            torch.tensor([[0.2, 0.7, 0.1]]), admissible,
        )
        self.assertEqual(float(existing[0, 1]), 0.0)
        self.assertAlmostEqual(float(existing.sum()), 1.0, places=6)
        with self.assertRaisesRegex(ValueError, "every candidate"):
            masked_candidate_probabilities(
                logits, torch.zeros_like(admissible),
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

    def test_structured_current_energy_keeps_its_fixed_zero_to_one_scale(self):
        arrays = {
            "relation_targets": np.asarray([[[1.0], [0.9]]]),
            "relation_mask": np.ones((1, 2, 1), dtype=np.float32),
            "relation_desired": np.ones((1, 2, 1), dtype=np.float32),
            "no_execution_penalties": np.zeros((1, 2), dtype=np.float32),
        }
        probabilities = structured_relation_oracle_probabilities(
            arrays, future_weight=0.0, now_weight=1.0,
            current_relation_dim=1, temperature=0.25,
        )
        expected_first = 1.0 / (1.0 + np.exp(-0.1 / 0.25))
        self.assertAlmostEqual(
            float(probabilities[0, 0]), float(expected_first), places=6,
        )

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
        self.assertTrue(audit["filter_enabled_for_method_selection"])
        self.assertFalse(audit["preflight_pass_claims_executor_legality"])
        self.assertEqual(
            audit[
                "maximum_teacher_decision_change_rate_due_to_residual_executor_illegal"
            ],
            0.0,
        )
        residual = dict(arrays)
        residual["candidate_static_preflight_pass"] = np.asarray([[
            True, True, True,
        ]])
        residual["candidate_static_preflight_failure_code"] = np.asarray([[
            0, 0, 0,
        ]])
        residual_audit = static_preflight_diagnostics(residual)
        self.assertEqual(
            residual_audit[
                "maximum_teacher_decision_change_rate_due_to_residual_executor_illegal"
            ],
            1.0,
        )
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
            "relation_desired": torch.ones((2, 2, 1), dtype=torch.float32),
            "y": torch.tensor([0, 1], dtype=torch.long),
            "penalties": torch.zeros((2, 2), dtype=torch.float32),
            "candidate_static_preflight_pass": torch.tensor([
                [True, True],
                [True, True],
            ]),
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
        self.assertEqual(
            diagnostics["target_discriminative_relation_elements"], 2,
        )
        self.assertEqual(diagnostics["ranking_relevant_relation_elements"], 2)
        self.assertEqual(diagnostics["reference_positive_margin_rate"], 1.0)

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
