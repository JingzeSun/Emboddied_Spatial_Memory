import tempfile
import unittest
from pathlib import Path

from spatial_world_model.r4_learning_runtime import (
    UniformBranchSampler, accumulated_torch_step, load_torch_checkpoint,
    save_torch_checkpoint,
)


class LearningRuntimeTests(unittest.TestCase):
    def test_sampler_resume_is_exact(self):
        sampler = UniformBranchSampler(["r4-39", "r4-47"], 17)
        first = [sampler.draw() for _ in range(19)]
        resumed = UniformBranchSampler.from_state_dict(sampler.state_dict())
        self.assertEqual([sampler.draw() for _ in range(31)],
                         [resumed.draw() for _ in range(31)])
        self.assertEqual(first[0], {"family_id": "r4-47", "world": "RL",
                                    "action_slot": 5, "action": "c12"})

    def test_accumulation_is_mean_then_single_clipped_update(self):
        import torch
        model = torch.nn.Linear(1, 1, bias=False)
        model.weight.data.fill_(1)
        optimizer = torch.optim.SGD(model.parameters(), lr=.25)
        branches = [{"x": float(i + 1)} for i in range(8)]
        calls = []
        def loss(current, branch):
            calls.append(branch["x"])
            loss = current(torch.tensor([[branch["x"]]])).square().mean()
            return loss, {"square": loss}
        result = accumulated_torch_step(model, optimizer, branches, loss)
        self.assertEqual(calls, list(range(1, 9)))
        self.assertAlmostEqual(result["branch_loss_mean"], 25.5)
        self.assertAlmostEqual(result["gradient_norm_before_clip"], 51.0, places=4)
        self.assertAlmostEqual(model.weight.item(), .75, places=5)

    def test_checkpoint_refuses_overwrite_and_binding_change(self):
        import torch
        model = torch.nn.Linear(1, 1)
        optimizer = torch.optim.AdamW(model.parameters())
        sampler = UniformBranchSampler(["r4-39"], 17)
        payload = {
            "schema_version": "spatial-history-r4-learning-runtime-v1", "update": 0,
            "model": model.state_dict(), "optimizer": optimizer.state_dict(),
            "sampler": sampler.state_dict(), "torch_rng_state": torch.get_rng_state(),
            "cuda_rng_state": [], "binding": {"code": "abc", "data": "def"},
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "update-000000.pt"
            record = save_torch_checkpoint(path, payload)
            self.assertGreater(record["bytes"], 0)
            self.assertEqual(load_torch_checkpoint(path, payload["binding"])["update"], 0)
            with self.assertRaises(ValueError):
                load_torch_checkpoint(path, {"code": "changed"})
            with self.assertRaises(ValueError):
                save_torch_checkpoint(path, payload)


if __name__ == "__main__":
    unittest.main()
