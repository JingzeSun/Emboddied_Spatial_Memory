"""Server full-suite fixtures: real reconstruction and saved model evaluation."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'src')]
from cpmt.dev_learning import OnlineModel
from cpmt.m1_protocol import load_and_validate
from cpmt.m1_rollout import generate_m1_paired_rollout_split
from cpmt.m1_af_rollout import rollout_learning_arrays_from_audits
from cpmt.m1_s5_confirmation import complete_unit
from cpmt.m1_s5_training import write_json
from cpmt.run_provenance import file_sha256
from run_m1_corrected_probe import (contracts, prepare_group, Audits, evaluate_unit, load_checkpoint)
from run_m1_s5_train import model_kwargs


class TestCorrectedProbeRollout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        cls.hard = load_and_validate(ROOT / 'configs/m1_hard_condition_v7.json')
        _, audits, _ = generate_m1_paired_rollout_split(cls.hard, 'train', paired_groups=1)
        cls.arrays = rollout_learning_arrays_from_audits(cls.hard, audits, future_hash_bins=32)

    def test_real_group_reconstruction_and_saved_model_causal_path(self):
        _, _, binding = contracts()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); train = root / 'train'; (train / 'shards').mkdir(parents=True)
            shard = train / 'shards/train_000000.npz'
            np.savez(shard, **self.arrays)
            write_json(train / 'generation.ok.json', {'file_sha256': {'shards/train_000000.npz': file_sha256(shard)}})
            prepare_group((str(root / 'audits'), str(train), 0, binding))
            unit_binding = {**binding, 'method': 'A', 'seed': 7}
            kwargs = model_kwargs(self.arrays, binding['config'], False)
            torch.manual_seed(7)
            model = OnlineModel(**kwargs).eval()
            sample = torch.as_tensor(self.arrays['x'][:2])
            with torch.no_grad(): before = model(sample).clone()
            def save(path):
                torch.save({'binding': unit_binding, 'model_kwargs': kwargs, 'state_dict': model.state_dict()}, path / 'model.pt')
            complete_unit(root / 'model', unit_binding, save)
            loaded, _ = load_checkpoint(root / 'model', unit_binding)
            with torch.no_grad(): self.assertTrue(torch.equal(before, loaded(sample)))
            result = evaluate_unit(root / 'evaluation', unit_binding, loaded, Audits(root / 'audits', [0]), [0])
            self.assertEqual(len(result['sequences']), 2)
            self.assertEqual(result['aggregate']['candidate_availability']['decisions'], 40)
            self.assertEqual(evaluate_unit(root / 'evaluation', unit_binding, loaded, Audits(root / 'audits', [0]), [0]), result)


if __name__ == '__main__': unittest.main()
