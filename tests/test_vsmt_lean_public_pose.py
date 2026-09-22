"""D-224-S1 ruling 49: the public camera pose read with the pitch sign restored.

What is pinned here: the pre-ruling S1-02 encoding Ry(yaw) * Rx(-p) corrected by this module is
exactly Ry(yaw) * Rx(+p) for every yaw and every registered pitch (-30, 0, 30); the fixed encoder
in the S1-02 runner writes Ry(yaw) * Rx(+p) directly, so "old encoding + correction" and "new
encoding" agree bit for bit within float tolerance; the position never changes; the correction is
applied only to episodes from the registered defective commits, skipped for registered corrected
ones and refused for any other commit; and the S1-03 contract block agrees with the core.
"""

from __future__ import annotations

import json
import math
import sys
import unittest
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT / "src", PROJECT_ROOT / "ops" / "vsmt"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import lean_s1_02a_pilot as pilot  # noqa: E402
from vsmt import lean_frontend_cache as fc  # noqa: E402
from vsmt import lean_public_pose as pp  # noqa: E402
from vsmt.l1_entities import _camera_values  # noqa: E402

CONTRACT_PATH = PROJECT_ROOT / "configs" / "vsmt" / "lean_s1_04_frontend_diagnostics_v1.json"
S1_03_CONTRACT_PATH = PROJECT_ROOT / "configs" / "vsmt" / "lean_s1_03_frontend_cache_v1.json"
DEFECTIVE = "c222c51a1906f3703a6115c968e77f349306faa9"
CORRECTED = "7c10d2c8f5d06e37c2d8fa3792f2b4058ecf2b69"
CALIBRATION = {"fx": 112.0, "fy": 112.0, "cx": 111.5, "cy": 111.5}


def ry(yaw_deg: float) -> np.ndarray:
    c, s = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def old_encoding(yaw_deg: float, pitch_deg: float) -> list[float]:
    """What camera_pose wrote before ruling 49: Ry(yaw) * Rx(-pitch)."""

    return pp.quaternion_xyzw_from_rotation(ry(yaw_deg) @ pp.rotation_x(-math.radians(pitch_deg)))


def true_rotation(yaw_deg: float, pitch_deg: float) -> np.ndarray:
    return ry(yaw_deg) @ pp.rotation_x(math.radians(pitch_deg))


class CorrectionTests(unittest.TestCase):
    def test_the_correction_turns_the_old_encoding_into_ry_yaw_rx_plus_pitch(self) -> None:
        for yaw in (0.0, 90.0, 180.0, 270.0, 37.5):
            for pitch in (-30.0, 0.0, 30.0):
                corrected = pp.corrected_quaternion_xyzw(old_encoding(yaw, pitch))
                np.testing.assert_allclose(pp.rotation_from_quaternion_xyzw(corrected), true_rotation(yaw, pitch), atol=1e-9)
                self.assertAlmostEqual(math.degrees(pp.recovered_pitch_radians(old_encoding(yaw, pitch))), pitch, places=9)

    def test_a_corrected_camera_that_looks_down_has_a_negative_forward_y(self) -> None:
        corrected = pp.corrected_quaternion_xyzw(old_encoding(0.0, 30.0))
        forward = pp.camera_forward(corrected)
        np.testing.assert_allclose(forward, [0.0, -0.5, math.cos(math.radians(30.0))], atol=1e-9)
        # the D-223 decoder reads the corrected quaternion the same way this module does
        _, _, _, _, _, rotation = _camera_values(CALIBRATION, {"position_m": [0.0, 0.0, 0.0], "quaternion_xyzw": corrected})
        np.testing.assert_allclose(rotation, pp.rotation_from_quaternion_xyzw(corrected), atol=1e-12)

    def test_the_fixed_encoder_agrees_with_old_encoding_plus_correction(self) -> None:
        for yaw in (0.0, 90.0, 225.0):
            for horizon in (-30.0, 0.0, 30.0):
                meta = {"cameraPosition": {"x": 1.0, "y": 1.625, "z": -2.0},
                        "agent": {"rotation": {"y": yaw}, "cameraHorizon": horizon}}
                new = pilot.camera_pose(meta)["quaternion_xyzw"]
                np.testing.assert_allclose(pp.rotation_from_quaternion_xyzw(new), true_rotation(yaw, horizon), atol=1e-9)
                np.testing.assert_allclose(pp.rotation_from_quaternion_xyzw(new),
                                           pp.rotation_from_quaternion_xyzw(pp.corrected_quaternion_xyzw(old_encoding(yaw, horizon))), atol=1e-9)
        # looking down 30 degrees: the fixed encoder's forward axis points below the horizon
        self.assertLess(pp.camera_forward(pilot.camera_pose({"cameraPosition": {"x": 0, "y": 1.5, "z": 0},
                                                             "agent": {"rotation": {"y": 0.0}, "cameraHorizon": 30.0}})["quaternion_xyzw"])[1], 0.0)

    def test_a_zero_pitch_pose_is_unchanged_and_the_position_never_moves(self) -> None:
        pose = {"position_m": [0.3, -0.1, 2.0], "quaternion_xyzw": old_encoding(90.0, 0.0), "origin": "observation_0_camera"}
        out = pp.correct_relative_pose(pose)
        self.assertEqual(out["position_m"], [0.3, -0.1, 2.0])
        np.testing.assert_allclose(out["quaternion_xyzw"], pose["quaternion_xyzw"], atol=1e-12)
        moved = pp.correct_relative_pose({"position_m": [5.0, 6.0, 7.0], "quaternion_xyzw": old_encoding(0.0, 30.0)})
        self.assertEqual(moved["position_m"], [5.0, 6.0, 7.0])

    def test_quaternion_round_trip(self) -> None:
        rng = np.random.default_rng(49)
        for _ in range(50):
            q = rng.normal(size=4)
            q = q / np.linalg.norm(q)
            back = pp.quaternion_xyzw_from_rotation(pp.rotation_from_quaternion_xyzw(q))
            np.testing.assert_allclose(pp.rotation_from_quaternion_xyzw(back), pp.rotation_from_quaternion_xyzw(q), atol=1e-9)
        with self.assertRaises(pp.LeanPublicPoseError):
            pp.rotation_from_quaternion_xyzw([0.0, 0.0, 0.0, 2.0])


class PolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = json.loads(S1_03_CONTRACT_PATH.read_text(encoding="utf-8"))["public_pose_correction"]

    def test_the_contract_lists_the_two_defective_commits_and_the_registered_corrected_encoder(self) -> None:
        self.assertEqual(self.policy["applies_to_s1_02_code_commits"],
                         [DEFECTIVE, "a397d16b93d202cf50b849a87cbfbb55e5ca06c0"])
        # the ruling-50 regeneration's generator commit, registered once its data existed
        self.assertEqual(self.policy["correct_encoder_since_code_commits"], [CORRECTED])
        self.assertEqual(set(self.policy["applies_to_s1_02_code_commits"]) & set(self.policy["correct_encoder_since_code_commits"]), set())
        self.assertEqual(self.policy["rule"], pp.CORRECTION_RULE)
        fc.validate_contract(json.loads(S1_03_CONTRACT_PATH.read_text(encoding="utf-8")))

    def test_an_episode_from_the_registered_corrected_encoder_is_read_as_written(self) -> None:
        import math
        # what the fixed encoder writes when the agent looks down 30 degrees
        written = pp.quaternion_xyzw_from_rotation(pp.rotation_x(math.radians(30.0)))
        record = {"relative_pose": {"position_m": [1.0, 0.0, 2.0], "quaternion_xyzw": written, "origin": "observation_0_camera"}}
        pose = pp.public_camera_pose(record, code_commit=CORRECTED, policy=self.policy)
        np.testing.assert_allclose(pose["quaternion_xyzw"], written, atol=1e-12)
        self.assertLess(pp.camera_forward(pose["quaternion_xyzw"])[1], 0.0)
        self.assertFalse(pp.correction_applies(CORRECTED, self.policy))
        self.assertTrue(pp.correction_applies(DEFECTIVE, self.policy))

    def test_correction_is_applied_skipped_or_refused_by_commit(self) -> None:
        record = {"relative_pose": {"position_m": [0.0, 0.0, 0.0], "quaternion_xyzw": old_encoding(0.0, 30.0), "origin": "observation_0_camera"}}
        corrected = pp.public_camera_pose(record, code_commit=DEFECTIVE, policy=self.policy)
        self.assertLess(pp.camera_forward(corrected["quaternion_xyzw"])[1], 0.0)
        policy = dict(self.policy, correct_encoder_since_code_commits=["f" * 40])
        as_written = pp.public_camera_pose(record, code_commit="f" * 40, policy=policy)
        np.testing.assert_allclose(as_written["quaternion_xyzw"], record["relative_pose"]["quaternion_xyzw"], atol=1e-12)
        with self.assertRaises(pp.LeanPublicPoseError) as caught:
            pp.public_camera_pose(record, code_commit="0" * 40, policy=self.policy)
        self.assertIn("episode_code_commit_not_registered", str(caught.exception))
        with self.assertRaises(pp.LeanPublicPoseError):
            pp.public_camera_pose(record, code_commit=None, policy=self.policy)
        with self.assertRaises(pp.LeanPublicPoseError):
            pp.correction_applies(DEFECTIVE, dict(self.policy, correct_encoder_since_code_commits=[DEFECTIVE]))


if __name__ == "__main__":
    unittest.main()
