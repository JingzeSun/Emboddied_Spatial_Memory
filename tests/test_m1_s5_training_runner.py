"""Small runner/torch checks; run on AutoDL with the full suite, not local load tests."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import ExitStack, redirect_stdout
import io

import numpy as np
import torch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))
sys.path.insert(0, str(PROJECT / "src"))
import run_m1_s5_train as runner
from cpmt.m1_s5_training import component_spec, ensure_artifact, read_json
from cpmt.dev_learning import OnlineModel, OutcomeScorer


class TestM1S5TrainingRunner(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hard = read_json(PROJECT / "configs/m1_hard_condition.json")
        cls.plan = read_json(PROJECT / "configs/m1_s5_training_plan.json")
        cls.registration = read_json(PROJECT / "configs/m1_post_probe_registration.json")

    def test_config_consumes_budgets_and_fixed_gate_for_every_arm(self):
        for architecture, arm in self.plan["arms"].items():
            for method, setting in arm["selected"]["student_hyperparameters_by_method"].items():
                component = component_spec(self.plan, architecture, 7, method)
                cfg = runner.training_config(self.hard, self.plan, self.registration, component)
                self.assertEqual(cfg["student_steps"], setting["student_steps"])
                self.assertEqual(cfg["learning_rate"], setting["learning_rate"])
                self.assertEqual(cfg["auxiliary_weight"], setting.get("direct_future_auxiliary_weight", 1.0))
                self.assertEqual((cfg["commit_probability"], cfg["margin_threshold"]), (0.0, 0.0))

    def test_saved_models_reload_exactly_for_both_architectures_and_classes(self):
        # Tiny untrained models check serialization and constructor metadata,
        # not scientific effectiveness, GPU/CPU equivalence, or throughput.
        with tempfile.TemporaryDirectory() as directory:
            for architecture in self.plan["arms"]:
                for method in ("outcome_scorer", "cpmt_ctl_core"):
                    component = component_spec(self.plan, architecture, 7, method)
                    config = runner.training_config(self.hard, self.plan, self.registration, component)
                    config.update(hidden_dim=8, feedforward_dim=16, candidate_feature_dim=2,
                                  current_relation_dim=2, set_attention_blocks=1)
                    train = {"x": torch.zeros(2, 8), "penalties": torch.zeros(2, 2),
                             "future": torch.zeros(2, 4), "relation_targets": torch.zeros(2, 2, 4)}
                    kwargs = runner.model_kwargs(train, config, method == "outcome_scorer")
                    model = (OutcomeScorer if method == "outcome_scorer" else OnlineModel)(**kwargs).eval()
                    path = Path(directory) / architecture / method
                    def produce(target):
                        torch.save({"model_class": type(model).__name__, "binding": {}, "component": component,
                                    "model_kwargs": kwargs, "state_dict": model.state_dict()}, target)
                        return {"model_kwargs": kwargs}
                    ensure_artifact(path, {}, component, produce)
                    restored, _ = runner.load_saved_model(path, {}, component, torch.device("cpu"))
                    for key, value in model.state_dict().items():
                        self.assertTrue(torch.equal(value, restored.state_dict()[key]))
                    if method != "outcome_scorer":
                        with torch.no_grad():
                            self.assertTrue(torch.equal(model(train["x"]), restored(train["x"])))

    def test_student_uses_supplied_teacher_and_frozen_configuration(self):
        component = component_spec(self.plan, "shared_candidate_mlp_v1", 7, "direct_future_loss")
        cfg = runner.training_config(self.hard, self.plan, self.registration, component)
        train = {"x": torch.zeros(1, 8), "penalties": torch.zeros(1, 2), "future": torch.zeros(1, 4),
                 "relation_targets": torch.zeros(1, 2, 4)}
        cfg.update(hidden_dim=8, candidate_feature_dim=2, current_relation_dim=2)
        teacher = torch.tensor([[0.3, 0.7]])
        model = OnlineModel(**runner.model_kwargs(train, cfg, False))
        with tempfile.TemporaryDirectory() as directory, patch.object(runner, "train_student", return_value=(model, [])) as train_call:
            runner.train_component(train, cfg, {}, component, teacher, Path(directory) / "model.pt", torch.device("cpu"), {})
            self.assertIs(train_call.call_args.args[1], train)
            self.assertIs(train_call.call_args.args[2], teacher)
            self.assertEqual(train_call.call_args.args[3]["student_steps"], 10000)
            self.assertEqual(train_call.call_args.args[3]["auxiliary_weight"], 10.0)

    def test_scorer_second_dataset_is_train_alias_and_teacher_is_saved(self):
        component = component_spec(self.plan, "shared_candidate_mlp_v1", 7, "outcome_scorer")
        cfg = runner.training_config(self.hard, self.plan, self.registration, component)
        train = {"x": torch.zeros(1, 8), "penalties": torch.zeros(1, 2), "future": torch.zeros(1, 4),
                 "relation_targets": torch.zeros(1, 2, 4)}
        cfg.update(hidden_dim=8, candidate_feature_dim=2, current_relation_dim=2)
        teacher = torch.tensor([[0.4, 0.6]])
        model = OutcomeScorer(**runner.model_kwargs(train, cfg, True))
        with tempfile.TemporaryDirectory() as directory, patch.object(runner, "train_outcome_scorer", return_value=(model, {"train": teacher}, [])) as call:
            target = Path(directory) / "model.pt"
            runner.train_component(train, cfg, {}, component, None, target, torch.device("cpu"), {})
            self.assertIs(call.call_args.args[0], train)
            self.assertIs(call.call_args.args[1], train)
            saved = torch.load(target, weights_only=True)
            self.assertTrue(torch.equal(saved["train_teacher"], teacher))

    def test_dispatches_all_selected_models_and_resume_trains_nothing(self):
        arrays = {"group": np.arange(1000), "y": np.zeros(1000, dtype=int),
                  "labelled": np.arange(1000) % 10 == 0, "x": np.zeros((1000, 8)),
                  "future": np.zeros((1000, 4)), "relation_targets": np.zeros((1000, 2, 4)),
                  "penalties": np.zeros((1000, 2)), "pstar": np.full((1000, 2), .5),
                  "pstar_current": np.full((1000, 2), .5)}
        calls = []
        def fake_train(train, cfg, binding, component, teacher, path, device, provenance):
            calls.append(component)
            self.assertEqual(len(train["y"]), 1000)
            if component["method"] == "future_no_execution":
                self.assertTrue(torch.equal(teacher, torch.full((1000, 2), .5)))
            path.write_bytes(b"dispatch-only model")
            return {"parameter_count": 42, "wall_seconds": 0, "model_kwargs": {}, "config": cfg}
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            out = Path(directory)
            marker = out / "test.json"
            marker.write_text("{}")
            cpu = torch.device("cpu")
            stack.enter_context(patch.object(runner, "validate_test_marker"))
            stack.enter_context(patch.object(runner, "capture_run_provenance", return_value={"git_dirty": False}))
            loader = stack.enter_context(patch.object(runner, "_load_train", return_value=(
                arrays, {"arrays_digest": self.plan["train_arrays_digest"]})))
            stack.enter_context(patch.object(runner.torch.cuda, "is_available", return_value=True))
            stack.enter_context(patch.object(runner.torch.cuda, "get_device_name", return_value="test-only"))
            stack.enter_context(patch.object(runner.torch.cuda, "empty_cache"))
            stack.enter_context(patch.object(runner.torch, "device", return_value=cpu))
            stack.enter_context(patch.object(runner, "train_component", side_effect=fake_train))
            stack.enter_context(patch.object(runner, "load_saved_model", return_value=(
                object(), {"train_teacher": torch.full((1000, 2), .5)})))
            stack.enter_context(redirect_stdout(io.StringIO()))
            result = runner.run_training(PROJECT, out / "train.npz", out, marker)
            self.assertEqual(len(calls), 60)
            self.assertEqual(result["status"], "complete")
            again = runner.run_training(PROJECT, out / "train.npz", out, marker)
            self.assertEqual(len(calls), 60, "resume must not train any completed model")
            self.assertEqual(again["models"], result["models"])
            self.assertEqual(loader.call_count, 2)
            self.assertTrue(all(call.args[0] == out / "train.npz" for call in loader.call_args_list))


if __name__ == "__main__":
    unittest.main()
