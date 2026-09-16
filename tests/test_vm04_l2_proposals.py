from __future__ import annotations

import inspect
from pathlib import Path
import sys
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vsmt.vm04_l2_proposals import (  # noqa: E402
    MODEL_ID,
    PROMPT_POLICY,
    Vm04L2ProposalConfig,
    run_vm04_l2_proposal_frontend,
    validate_vm04_l2_proposal_receipt,
)


def config() -> Vm04L2ProposalConfig:
    return Vm04L2ProposalConfig(
        image_height=8,
        image_width=8,
        minimum_visible_pixels=4,
        border_truncation_policy="keep_if_minimum_support",
        maximum_proposals_per_frame=8,
        model_id=MODEL_ID,
        repository_commit="1" * 40,
        checkpoint_sha256="2" * 64,
        automatic_mask_generator_config_sha256="3" * 64,
        assets_receipt_sha256="4" * 64,
        generator_code_sha256="5" * 64,
        prompt_policy=PROMPT_POLICY,
        cross_frame_memory_enabled=False,
        overlap_policy="preserve_independent_overlapping_proposals",
    )


class Generator:
    def __init__(self, masks):
        self.masks = masks
        self.inputs = []

    def generate(self, rgb):
        self.inputs.append(rgb.copy())
        return [{"segmentation": mask, "ignored_model_score": 0.9}
                for mask in self.masks]


class Vm04L2ProposalTests(unittest.TestCase):
    def test_public_rgb_only_and_overlaps_are_preserved(self):
        first = np.zeros((8, 8), dtype=np.bool_)
        first[1:5, 1:5] = True
        second = np.zeros((8, 8), dtype=np.bool_)
        second[3:7, 3:7] = True
        generator = Generator([second, first])
        output = run_vm04_l2_proposal_frontend(
            rgb=np.zeros((8, 8, 3), dtype=np.uint8),
            public_rgb_file_sha256="a" * 64,
            generator=generator,
            config=config(),
        )
        self.assertEqual(len(output["masks"]), 2)
        self.assertTrue(np.logical_and(
            output["masks"][0].as_array(), output["masks"][1].as_array(),
        ).any())
        self.assertEqual(output["receipt"]["generator_input_fields"],
                         ["current_public_rgb"])
        validate_vm04_l2_proposal_receipt(
            output["receipt"], expected_public_rgb_file_sha256="a" * 64,
            expected_config=config(),
        )

    def test_canonical_order_does_not_depend_on_generator_order(self):
        left = np.zeros((8, 8), dtype=np.bool_)
        left[1:3, 1:3] = True
        right = np.zeros((8, 8), dtype=np.bool_)
        right[5:7, 5:7] = True
        kwargs = {
            "rgb": np.zeros((8, 8, 3), dtype=np.uint8),
            "public_rgb_file_sha256": "a" * 64,
            "config": config(),
        }
        first = run_vm04_l2_proposal_frontend(
            generator=Generator([right, left]), **kwargs,
        )
        second = run_vm04_l2_proposal_frontend(
            generator=Generator([left, right]), **kwargs,
        )
        self.assertEqual(first["receipt"]["ordered_mask_sha256s"],
                         second["receipt"]["ordered_mask_sha256s"])

    def test_duplicate_masks_fail_instead_of_being_silently_selected(self):
        mask = np.zeros((8, 8), dtype=np.bool_)
        mask[1:3, 1:3] = True
        with self.assertRaisesRegex(ValueError, "duplicate mask"):
            run_vm04_l2_proposal_frontend(
                rgb=np.zeros((8, 8, 3), dtype=np.uint8),
                public_rgb_file_sha256="a" * 64,
                generator=Generator([mask, mask.copy()]), config=config(),
            )

    def test_function_signature_has_no_private_or_temporal_input(self):
        names = set(inspect.signature(
            run_vm04_l2_proposal_frontend,
        ).parameters)
        self.assertEqual(names, {
            "rgb", "public_rgb_file_sha256", "generator", "config",
        })


if __name__ == "__main__":
    unittest.main()
