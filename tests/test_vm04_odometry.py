"""Checks for the D-206 declared noisy action odometry and the pose channel."""

import copy
import json
import math
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vsmt.vm04_odometry import (  # noqa: E402
    DeclaredOdometry,
    OdometryError,
    dead_reckoned_poses,
    validate_noise_model,
)


CONTRACT = json.loads((
    ROOT / "configs/vsmt/vm04_observation_suitability_v3.json"
).read_text(encoding="utf-8"))
NOISE = CONTRACT["public_pose_channel"]["declared_odometry_noise_model"]
TEMPLATES = CONTRACT["observation_trajectory"][
    "registered_action_request_templates"]


def _odometry(seed="episode:test"):
    return DeclaredOdometry(
        noise_model=NOISE, action_request_templates=TEMPLATES,
        episode_seed_material=seed,
    )


class NoiseModelTests(unittest.TestCase):
    def test_frozen_model_is_accepted(self):
        sigma = validate_noise_model(NOISE)
        self.assertEqual(len(sigma), 5)
        self.assertTrue(all(value > 0.0 for value in sigma.values()))

    def test_zero_sigma_is_rejected_as_an_integration_task(self):
        silent = copy.deepcopy(NOISE)
        silent["translation_relative_sigma"] = 0.0
        with self.assertRaises(OdometryError):
            validate_noise_model(silent)

    def test_unregistered_model_is_rejected(self):
        other = copy.deepcopy(NOISE)
        other["model_id"] = "some_other_model"
        with self.assertRaises(OdometryError):
            validate_noise_model(other)

    def test_noise_may_not_claim_it_perturbs_the_simulator(self):
        leaky = copy.deepcopy(NOISE)
        leaky["simulator_executes_the_commanded_action_unchanged"] = False
        with self.assertRaises(OdometryError):
            validate_noise_model(leaky)

    def test_adjustable_noise_is_rejected(self):
        tunable = copy.deepcopy(NOISE)
        tunable["may_be_increased_after_seeing_results"] = True
        with self.assertRaises(OdometryError):
            validate_noise_model(tunable)


class DeadReckoningTests(unittest.TestCase):
    def test_observation_zero_is_the_identity_frame(self):
        pose = _odometry().pose()
        self.assertEqual(pose["position_m"], [0.0, 0.0, 0.0])
        self.assertEqual(pose["yaw_deg"], 0.0)
        self.assertEqual(pose["observation_index"], 0)
        self.assertFalse(pose["is_world_pose"])

    def test_same_episode_replays_the_same_drift(self):
        route = ["MoveAhead", "RotateLeft", "MoveAhead", "LookDown"]
        first = dead_reckoned_poses(
            route, noise_model=NOISE, action_request_templates=TEMPLATES,
            episode_seed_material="episode:same")
        second = dead_reckoned_poses(
            route, noise_model=NOISE, action_request_templates=TEMPLATES,
            episode_seed_material="episode:same")
        self.assertEqual(first, second)

    def test_different_episodes_drift_differently(self):
        route = ["MoveAhead"] * 8
        first = dead_reckoned_poses(
            route, noise_model=NOISE, action_request_templates=TEMPLATES,
            episode_seed_material="episode:a")[-1]
        second = dead_reckoned_poses(
            route, noise_model=NOISE, action_request_templates=TEMPLATES,
            episode_seed_material="episode:b")[-1]
        self.assertNotEqual(first["position_m"], second["position_m"])

    def test_estimate_differs_from_the_commanded_magnitude(self):
        odometry = _odometry()
        odometry.advance("MoveAhead")
        increment = odometry.applied_increments()[0]
        self.assertEqual(increment["commanded_m"],
                         TEMPLATES["MoveAhead"]["moveMagnitude"])
        self.assertNotEqual(increment["estimated_m"], increment["commanded_m"])
        self.assertLess(
            abs(increment["estimated_m"] - increment["commanded_m"]),
            0.25 * increment["commanded_m"],
            "declared noise should stay a small perturbation")

    def test_n_actions_produce_n_plus_one_poses(self):
        route = ["MoveAhead", "RotateRight", "MoveLeft"]
        poses = dead_reckoned_poses(
            route, noise_model=NOISE, action_request_templates=TEMPLATES,
            episode_seed_material="episode:count")
        self.assertEqual(len(poses), len(route) + 1)
        self.assertEqual([pose["observation_index"] for pose in poses],
                         list(range(len(route) + 1)))

    def test_forward_motion_follows_the_current_heading(self):
        """A left turn from the +z heading must send MoveAhead toward -x."""

        straight = dead_reckoned_poses(
            ["MoveAhead"] * 4, noise_model=NOISE,
            action_request_templates=TEMPLATES,
            episode_seed_material="episode:straight")[-1]
        self.assertGreater(straight["position_m"][2], 0.5)
        self.assertLess(abs(straight["position_m"][0]), 0.2)

        turned = dead_reckoned_poses(
            ["RotateLeft"] * 3 + ["MoveAhead"] * 4, noise_model=NOISE,
            action_request_templates=TEMPLATES,
            episode_seed_material="episode:turned")[-1]
        self.assertLess(turned["position_m"][0], -0.5)
        self.assertLess(abs(turned["position_m"][2]), 0.2)
        self.assertLess(abs(abs(turned["yaw_deg"]) - 90.0), 10.0)

    def test_look_actions_change_pitch_without_moving(self):
        odometry = _odometry()
        odometry.advance("LookDown")
        pose = odometry.pose()
        self.assertEqual(pose["position_m"], [0.0, 0.0, 0.0])
        self.assertGreater(pose["pitch_deg"], 0.0)

    def test_unregistered_action_is_rejected(self):
        with self.assertRaises(OdometryError):
            _odometry().advance("Teleport")

    def test_incomplete_template_set_is_rejected(self):
        partial = {name: TEMPLATES[name] for name in ("MoveAhead", "RotateLeft")}
        with self.assertRaises(OdometryError):
            DeclaredOdometry(noise_model=NOISE,
                             action_request_templates=partial,
                             episode_seed_material="episode:partial")

    def test_empty_seed_material_is_rejected(self):
        with self.assertRaises(OdometryError):
            _odometry(seed="")

    def test_z_route_ends_displaced_rather_than_back_at_the_origin(self):
        """The user's Z-route: two opposite turns must not read as a loop."""

        route = (["MoveAhead"] * 16 + ["RotateLeft"] * 3 +
                 ["MoveAhead"] * 12 + ["RotateRight"] * 3 +
                 ["MoveAhead"] * 16)
        end = dead_reckoned_poses(
            route, noise_model=NOISE, action_request_templates=TEMPLATES,
            episode_seed_material="episode:zroute")[-1]
        distance = math.hypot(end["position_m"][0], end["position_m"][2])
        self.assertGreater(distance, 5.0,
                           "a Z route must not dead reckon back to the origin")
        self.assertLess(abs(end["yaw_deg"]), 10.0,
                        "two opposite turns should restore the heading")


if __name__ == "__main__":
    unittest.main()
