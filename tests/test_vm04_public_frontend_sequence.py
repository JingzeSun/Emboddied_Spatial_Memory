from __future__ import annotations

import inspect
from pathlib import Path
import sys
import unittest

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tests.test_vm04_public_frontend import config as frontend_config  # noqa: E402
from vsmt.causal_prior import PublicBootstrapConfig  # noqa: E402
from vsmt.vm04_public_frontend_sequence import (  # noqa: E402
    Vm04PublicFrontendSequence,
)


def bootstrap_config() -> PublicBootstrapConfig:
    return PublicBootstrapConfig(
        association_rules={
            kind: {
                "visual_weight": 0.5,
                "geometry_weight": 0.5,
                "geometry_scale_m": 1.0,
                "association_threshold": 0.7,
            }
            for kind in ("entity", "surface", "fragment")
        },
        support_envelope_reliability_threshold=0.9,
        maximum_regions_per_packet=512,
        builder_revision="fixture.v1",
    )


def contexts() -> list[dict]:
    constants = {
        "coordinate_frame": "map",
        "depth_unit": "metre",
        "descriptor_model_id": "dinov2.vits14",
        "proposal_model_id": "l1.oracle-mask.public-depth.v1",
    }
    return [
        {
            "sample_id_hash": f"{index + 1:x}" * 64,
            "decision_time_s": float(index),
            "robot_state": {"feature_names": [], "values": []},
            "past_actions": [],
            "public_constants": constants,
        }
        for index in range(2)
    ]


def raws(index: int):
    mask = np.zeros((1, 224, 224), dtype=np.uint8)
    mask[0, :14, :14] = 1
    public = {
        "rgb": np.zeros((224, 224, 3), dtype=np.uint8),
        "depth_m": np.full((224, 224), 2.0, dtype=np.float32),
        "camera": {
            "pose": {
                "position_m": [0.0, 0.0, 0.0],
                "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
            },
            "calibration": {
                "fx": 112.0, "fy": 112.0, "cx": 111.5, "cy": 111.5,
            },
        },
        "rgb_sha256": "a" * 64,
        "depth_sha256": "b" * 64,
        "source_frame_sha256": f"{index + 10:x}" * 64,
    }
    private = {
        "instance_masks": mask,
        "private_instance_ids": ["Chair|private"],
    }
    return public, private


def tokens(_rgb, _index):
    result = np.zeros((16, 16, 4), dtype=np.float32)
    result[..., 0] = 1.0
    return result


class Vm04PublicFrontendSequenceTests(unittest.TestCase):
    def test_contiguous_frames_build_and_replay_one_public_memory_chain(self):
        callback = Vm04PublicFrontendSequence(
            public_frame_contexts=contexts(),
            private_frame_roles=["old", "new"],
            patch_token_extractor=tokens,
            frontend_config=frontend_config(),
            bootstrap_config=bootstrap_config(),
            builder_code_sha256="c" * 64,
        )
        first = callback(*raws(0), 0)
        second = callback(*raws(1), 1)
        final = callback.finalized_result()

        self.assertEqual(
            first["public_packet"]["prior_memory_ref"]["graph_sha256"],
            final["causal_prior_receipt"]["initial_memory_sha256"],
        )
        self.assertEqual(
            second["public_packet"]["prior_memory_ref"]["graph_sha256"],
            final["causal_prior_receipt"]["version_chain_sha256s"][1],
        )
        self.assertEqual(
            final["prior_memory"]["graph_hash"],
            final["causal_prior_receipt"]["final_prior_memory_sha256"],
        )
        self.assertEqual(
            final["ordered_public_packet_sha256s"],
            final["causal_prior_receipt"]["ordered_public_packet_sha256s"],
        )

    def test_out_of_order_or_incomplete_finalize_fails_closed(self):
        callback = Vm04PublicFrontendSequence(
            public_frame_contexts=contexts(),
            private_frame_roles=["old", "new"],
            patch_token_extractor=tokens,
            frontend_config=frontend_config(),
            bootstrap_config=bootstrap_config(),
            builder_code_sha256="c" * 64,
        )
        with self.assertRaisesRegex(ValueError, "contiguous from zero"):
            callback(*raws(1), 1)
        callback(*raws(0), 0)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            callback.finalized_result()

    def test_api_has_no_program_target_teacher_or_future_channel(self):
        names = inspect.signature(Vm04PublicFrontendSequence).parameters
        self.assertFalse(any(
            token in name
            for name in names
            for token in ("program", "target", "teacher", "future")
        ))
        with self.assertRaisesRegex(ValueError, "contain exactly"):
            Vm04PublicFrontendSequence(
                public_frame_contexts=[{**contexts()[0], "private_program": "SPLIT"}],
                private_frame_roles=["old"],
                patch_token_extractor=tokens,
                frontend_config=frontend_config(),
                bootstrap_config=bootstrap_config(),
                builder_code_sha256="c" * 64,
            )


if __name__ == "__main__":
    unittest.main()
