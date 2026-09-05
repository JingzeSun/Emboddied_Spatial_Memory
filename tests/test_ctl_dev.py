"""Development learning integrity checks; not scientific-effect tests."""
from copy import deepcopy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

import numpy as np
import torch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from cpmt.dev_data import (generate_split, dataset_digest, graph_objects,
                           hindsight_posterior, make_programs, make_world, online_vector)
from cpmt.dev_learning import (METHODS, OnlineModel, oracle_probabilities, run_seed,
                               tensors, train_student)
from cpmt.executor import execute_transaction


class TestCTLDevelopment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((PROJECT / "configs" / "ctl_dev.json").read_text())
        cls.config.update(train_groups=6, validation_groups=4, label_fraction=1.0,
                          ambiguous_fraction=1.0, student_steps=8, device="cpu")
        cls.data, cls.audit = generate_split(cls.config, "train")

    def test_real_branches_and_base_immutability(self):
        base = make_world(0)
        frozen = deepcopy(base)
        posts = [execute_transaction(base, p) for p in make_programs(base, 1)]
        self.assertEqual(base, frozen)
        self.assertEqual(graph_objects(posts[0]), {"old": 0, "protected": 2})
        self.assertEqual(graph_objects(posts[1]), {"old": 0, "new": 1, "protected": 2})
        self.assertEqual(graph_objects(posts[2]), {"old": 1, "protected": 2})
        self.assertTrue(any(e["valid_to"] == 2 for e in posts[2]["edges"]))

    def test_online_allowlist_rejects_future_and_truth(self):
        online = deepcopy(self.audit[0]["online"])
        online_vector(online)
        for key in ("future", "future_poses", "oracle_template", "simulator_truth"):
            polluted = dict(online, **{key: 123})
            with self.assertRaises(ValueError):
                online_vector(polluted)
        online["decision_time"] = 3
        with self.assertRaises(ValueError):
            online_vector(online)

    def test_identical_input_can_have_distinct_future(self):
        for i in range(0, len(self.audit), 3):
            np.testing.assert_array_equal(self.data["x"][i + 1], self.data["x"][i + 2])
            self.assertNotEqual(int(self.data["y"][i + 1]), int(self.data["y"][i + 2]))
            self.assertFalse(np.array_equal(self.data["future"][i + 1],
                                           self.data["future"][i + 2]))

    def test_visible_history_can_disambiguate(self):
        config = dict(self.config, ambiguous_fraction=0.0)
        data, audit = generate_split(config, "train")
        for i in range(0, len(audit), 3):
            a, b = audit[i + 1]["online"], audit[i + 2]["online"]
            self.assertEqual(a["current_region"], b["current_region"])
            self.assertEqual(a["base_features"], b["base_features"])
            self.assertNotEqual(a["history"], b["history"])
            self.assertFalse(np.array_equal(data["x"][i + 1], data["x"][i + 2]))

    def test_split_and_label_boundary(self):
        validation, _ = generate_split(self.config, "validation")
        self.assertFalse(set(validation["group"]) & set(self.data["group"]))
        self.assertFalse(validation["labelled"].any())
        with self.assertRaises(ValueError):
            generate_split(self.config, "test")
        with self.assertRaises(ValueError):
            generate_split(dict(self.config, test_access=True), "train")

    def test_data_reproducible_and_auditable(self):
        repeat, audit = generate_split(self.config, "train")
        self.assertEqual(dataset_digest(audit), dataset_digest(self.audit))
        for name in self.data:
            np.testing.assert_array_equal(self.data[name], repeat[name])

    def test_teacher_components_and_preedit_penalties(self):
        for i, case in enumerate(self.audit):
            energies = case["candidate_energies"]
            for j, energy in enumerate(energies):
                total = sum(self.config["energy_weights"][k] * energy[k]
                            for k in self.config["energy_weights"])
                self.assertAlmostEqual(total, energy["total"])
                self.assertAlmostEqual(
                    total - self.config["energy_weights"]["future"] * energy["future"],
                    float(self.data["penalties"][i, j]))
                if energy["illegal"]:
                    self.assertIsNotNone(case["candidate_failures"][j])
                    self.assertIsNone(case["post_worlds"][j])
                    self.assertIsNone(case["future_predictions"][j])
                    self.assertEqual(case["teacher_posterior"][j], 0.0)
                else:
                    self.assertIsNone(case["candidate_failures"][j])
                    self.assertIsNotNone(case["post_worlds"][j])
            expected = hindsight_posterior(np.array([e["total"] for e in energies]),
                                           self.config["temperature"])
            np.testing.assert_allclose(expected, self.data["pstar"][i])
            expected_current = hindsight_posterior(
                np.asarray(self.data["penalties"][i]), self.config["temperature"]
            )
            np.testing.assert_allclose(
                expected_current, self.data["pstar_current"][i]
            )
        # Teacher ranking is a small synthetic sanity check, not an experiment result.
        np.testing.assert_array_equal(self.data["pstar"].argmax(1), self.data["y"])

    def test_training_changes_weights_without_future_inference(self):
        torch.set_num_threads(2)
        data = tensors(self.data, torch.device("cpu"))
        torch.manual_seed(7)
        initial = OnlineModel(data["x"].shape[1], self.config["hidden_dim"],
                              data["future"].shape[1], self.config["horizon"])
        model, trace = train_student("cpmt_ctl_core", data, data["pstar"],
                                     self.config, 7, torch.device("cpu"))
        self.assertTrue(trace)
        self.assertFalse(torch.equal(initial.classifier.weight, model.classifier.weight))
        with torch.no_grad():
            before = model(data["x"]).clone()
            data["future"].fill_(999)
            data["poses"].fill_(999)
            data["y"].fill_(2)
            after = model(data["x"])
        torch.testing.assert_close(before, after)
        self.assertTrue(torch.isfinite(after).all())

    def test_hindsight_changes_teacher_not_online_vector(self):
        online = self.audit[1]["online"]
        before = online_vector(online).copy()
        teacher_a = hindsight_posterior(np.array([2., 0., 1.]), .06)
        teacher_b = hindsight_posterior(np.array([2., 1., 0.]), .06)
        self.assertNotEqual(int(teacher_a.argmax()), int(teacher_b.argmax()))
        np.testing.assert_array_equal(before, online_vector(online))

    def test_all_six_required_methods_are_wired(self):
        self.assertEqual(
            METHODS,
            (
                "cpmt_ctl_core",
                "direct_classifier",
                "direct_future_loss",
                "execute_current_only",
                "future_no_execution",
                "oracle_candidate_program",
            ),
        )
        data = tensors(self.data, torch.device("cpu"))
        oracle = oracle_probabilities(data)
        np.testing.assert_array_equal(oracle.argmax(1), self.data["y"])
        self.assertTrue(np.allclose(oracle.sum(1), 1.0))

    def test_six_method_cpu_smoke(self):
        config = dict(self.config, student_steps=2, scorer_steps=2, batch_size=8)
        validation, _ = generate_split(config, "validation")
        with TemporaryDirectory(dir=PROJECT) as directory:
            metrics, details = run_seed(
                self.data, validation, config, 7, Path(directory),
                torch.device("cpu"),
            )
        self.assertEqual(tuple(metrics), METHODS)
        self.assertEqual(tuple(details)[:-1], METHODS)
        self.assertEqual(metrics["oracle_candidate_program"]["accuracy"], 1.0)
        self.assertTrue(metrics["oracle_candidate_program"]["oracle_upper_bound"])


if __name__ == "__main__":
    unittest.main()
