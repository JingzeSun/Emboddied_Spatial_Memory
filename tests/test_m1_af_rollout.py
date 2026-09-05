"""Tests for the shared A-F online adapter and causal rollout smoke."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from cpmt.dev_learning import METHODS
from cpmt.m1_af_rollout import (
    CANDIDATE_FEATURE_DIM,
    ONLINE_CONTEXT_DIM,
    build_rollout_learning_arrays,
    online_feature_vector,
    resolve_af_smoke_config,
    run_af_seed,
    selection_error_decomposition,
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

    def test_selection_error_splits_template_from_argument(self):
        probabilities = np.eye(16, dtype=np.float32)[self.validation["y"]]
        perfect = selection_error_decomposition(probabilities, self.validation)
        self.assertEqual(perfect["accuracy"], 1.0)
        self.assertEqual(perfect["template_accuracy"], 1.0)
        self.assertEqual(perfect["argument_error_with_correct_template"], 0.0)
        shifted = np.eye(16, dtype=np.float32)[(self.validation["y"] + 1) % 16]
        degraded = selection_error_decomposition(shifted, self.validation)
        self.assertEqual(degraded["accuracy"], 0.0)
        self.assertLessEqual(degraded["template_accuracy"], 1.0)

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

    def test_executed_teacher_covers_reference_and_illegal_is_masked(self):
        self.assertTrue(np.all(self.train["pstar"].argmax(axis=1) == self.train["y"]))
        self.assertTrue(np.all(self.validation["pstar"].argmax(axis=1) == self.validation["y"]))
        self.assertTrue(np.all(np.isfinite(self.train["x"])))
        self.assertTrue(np.all(np.isfinite(self.train["future"])))
        self.assertTrue(np.all((self.train["penalties"] >= 1_000_000).sum(axis=1) >= 1))
        self.assertEqual(self.train["penalties"].shape[1], 16)
        self.assertEqual(self.validation["penalties"].shape[1], 16)

    def test_six_method_training_and_causal_oracle_smoke(self):
        config = deepcopy(self.config)
        config["student_steps"] = 2
        config["scorer_steps"] = 2
        results, _, _ = run_af_seed(
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
        self.assertEqual(oracle["causal_rollout"]["memory_contamination_per_100"], 0.0)

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
