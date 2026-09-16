from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vsmt.vm04_public_visibility import (  # noqa: E402
    Vm04PublicVisibilityConfig,
    assess_public_visibility_from_depth,
    seal_public_visibility_subject,
)


CALIBRATION = {"fx": 4.0, "fy": 4.0, "cx": 3.5, "cy": 3.5}
POSE = {
    "position_m": [0.0, 0.0, 0.0],
    "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
}


def config():
    return Vm04PublicVisibilityConfig(
        minimum_depth_m=0.05,
        maximum_depth_m=20.0,
        occlusion_depth_tolerance_m=0.05,
        sampling_stride_pixels=1,
        maximum_subject_samples=16,
        minimum_subject_samples=4,
    )


def subject():
    mask = np.zeros((8, 8), dtype=np.bool_)
    mask[2:6, 2:6] = True
    return seal_public_visibility_subject(
        subject_public_ref="subject:public-0001",
        source_public_packet_sha256="a" * 64,
        source_observation_index=0,
        public_mask=mask,
        public_depth_m=np.full((8, 8), 2.0, dtype=np.float32),
        camera_calibration=CALIBRATION,
        camera_pose=POSE,
        config=config(),
    )


def assess(depth, *, pose=POSE, terminal=False, support=None):
    return assess_public_visibility_from_depth(
        subject=subject(), current_observation_index=1,
        public_depth_m=depth,
        camera_calibration=CALIBRATION, camera_pose=pose,
        current_public_support_sha256=support,
        terminal_reobservation_phase=terminal,
        config=config(),
    )


class Vm04PublicVisibilityTests(unittest.TestCase):
    def test_public_depth_distinguishes_visible_occluded_and_out_of_view(self):
        visible = assess(np.full((8, 8), 2.0, dtype=np.float32))
        self.assertEqual(visible["assessment"]["visibility_state"], "visible")

        occluded = assess(np.full((8, 8), 1.0, dtype=np.float32))
        self.assertEqual(occluded["assessment"]["visibility_state"], "occluded")

        moved = {
            "position_m": [100.0, 0.0, 0.0],
            "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
        }
        outside = assess(np.full((8, 8), 2.0, dtype=np.float32), pose=moved)
        self.assertEqual(outside["assessment"]["visibility_state"], "out_of_view")

    def test_terminal_reobservation_requires_current_public_support(self):
        without = assess(
            np.full((8, 8), 2.0, dtype=np.float32), terminal=True,
        )
        self.assertEqual(without["assessment"]["visibility_state"], "visible")
        with_support = assess(
            np.full((8, 8), 2.0, dtype=np.float32), terminal=True,
            support="b" * 64,
        )
        self.assertEqual(with_support["assessment"]["visibility_state"],
                         "reobserved")

    def test_missing_depth_cannot_authorize_hidden_intervention(self):
        missing = assess(np.full((8, 8), np.nan, dtype=np.float32))
        self.assertEqual(missing["assessment"]["visibility_state"], "visible")
        self.assertTrue(missing["receipt"][
            "invalid_or_missing_depth_treated_as_unoccluded"])

    def test_subject_seal_rejects_private_style_extra_field(self):
        value = subject()
        value["instance_id"] = "private"
        with self.assertRaisesRegex(ValueError, "seal mismatch"):
            assess_public_visibility_from_depth(
                subject=value, current_observation_index=1,
                public_depth_m=np.full((8, 8), 2.0, dtype=np.float32),
                camera_calibration=CALIBRATION, camera_pose=POSE,
                current_public_support_sha256=None,
                terminal_reobservation_phase=False, config=config(),
            )


if __name__ == "__main__":
    unittest.main()
