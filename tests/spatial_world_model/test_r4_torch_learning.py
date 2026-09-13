import unittest

from spatial_world_model.r4_torch_learning import aggregate_metrics, branch_metrics, optimizer


class TorchLearningBridgeTests(unittest.TestCase):
    def test_optimizer_registration_and_frozen_parameters(self):
        import torch
        model = torch.nn.Sequential(torch.nn.Linear(2, 3), torch.nn.Linear(3, 1))
        model[0].requires_grad_(False)
        value = optimizer(model, 0.0003)
        self.assertEqual(value.defaults["weight_decay"], .01)
        self.assertEqual(value.param_groups[0]["params"], list(model[1].parameters()))
        with self.assertRaises(ValueError):
            optimizer(model, 0.001)

    def test_metrics_use_probabilities_and_branch_equal_mean(self):
        import torch
        task = {
            "object_position_m": torch.zeros(1, 200, 3),
            "contact_logit": torch.zeros(1, 200),
            "success_logit": torch.zeros(1),
        }
        targets = {
            "object_position_m": [[.01, 0, 0]] * 200,
            "interval_contact": [False] * 100 + [True] * 100,
            "task_success": True,
        }
        row = branch_metrics(task, targets)
        self.assertAlmostEqual(row["position_error_m"], .01, places=6)
        self.assertEqual(row["contact_brier"], .25)
        self.assertEqual(row["success_brier"], .25)
        aggregate = aggregate_metrics([row, {"position_error_m": .03,
                                              "contact_brier": .75,
                                              "success_brier": .75}])
        self.assertAlmostEqual(aggregate["position_error_m"], .02, places=7)
        self.assertEqual(aggregate["contact_brier"], .5)
        self.assertEqual(aggregate["success_brier"], .5)


if __name__ == "__main__":
    unittest.main()
