"""Declared noisy action odometry for the D-206 public pose channel.

Before D-206 the public ObservationPacket carried the exact simulator world
camera pose, so place identity was not inferred, it was given.  This module
replaces that channel: the public pose is dead reckoned from the registered
camera actions in an episode-relative frame whose origin is observation zero,
with the frozen noise model applied to the *estimate only*.  The simulator
still executes the commanded action unchanged and the true world pose is
written to the private evaluation side.

The noise is derived by hashing the sealed episode identifier together with the
observation index and a component name, so a replay of the same episode
reproduces the same drift without depending on any global RNG stream.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any, Mapping

from cpmt.hashing import clone_json


NOISE_MODEL_ID = "registered_action_odometry_noise_v1"
POSE_SCHEMA = "vsmt-vm04-public-relative-pose-v1"
TRANSLATION_ACTIONS = {
    "MoveAhead": (0.0, 1.0),
    "MoveBack": (0.0, -1.0),
    "MoveRight": (1.0, 0.0),
    "MoveLeft": (-1.0, 0.0),
}
YAW_ACTIONS = {"RotateRight": 1.0, "RotateLeft": -1.0}
PITCH_ACTIONS = {"LookDown": 1.0, "LookUp": -1.0}


class OdometryError(ValueError):
    """Fail-closed odometry or noise-model error."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise OdometryError(message)


def _unit_interval(material: str) -> float:
    """Deterministic uniform in (0, 1) from a seed string."""

    digest = hashlib.sha256(material.encode("utf-8")).digest()
    return (int.from_bytes(digest[:8], "big") + 0.5) / float(1 << 64)


def _gaussian(material: str) -> float:
    """Deterministic standard normal via Box-Muller on two hashed uniforms."""

    first = _unit_interval(material + "|u0")
    second = _unit_interval(material + "|u1")
    return math.sqrt(-2.0 * math.log(first)) * math.cos(2.0 * math.pi * second)


def validate_noise_model(model: Mapping[str, Any]) -> dict[str, float]:
    """Accept only the frozen D-206 model with positive, non-zero sigmas."""

    _require(type(model) is dict and model.get("model_id") == NOISE_MODEL_ID,
             "unregistered odometry noise model")
    _require(model.get("seeded_and_reproducible") is True,
             "odometry noise must be seeded and reproducible")
    _require(model.get("simulator_executes_the_commanded_action_unchanged")
             is True,
             "odometry noise may not perturb the simulator")
    _require(model.get("may_be_increased_after_seeing_results") is False,
             "odometry noise must not be adjustable after results")
    values = {}
    for name in ("translation_relative_sigma", "translation_absolute_sigma_m",
                 "rotation_relative_sigma", "rotation_absolute_sigma_deg",
                 "lateral_slip_sigma_m"):
        value = model.get(name)
        _require(type(value) in {int, float} and math.isfinite(float(value)) and
                 float(value) > 0.0,
                 f"odometry {name} must be a positive finite number; a zero "
                 f"sigma would reduce the Z-route to an integration task")
        values[name] = float(value)
    return values


class DeclaredOdometry:
    """Episode-relative dead reckoning with the frozen declared noise."""

    def __init__(
        self, *, noise_model: Mapping[str, Any],
        action_request_templates: Mapping[str, Mapping[str, Any]],
        episode_seed_material: str,
    ) -> None:
        self.sigma = validate_noise_model(noise_model)
        _require(type(episode_seed_material) is str and episode_seed_material,
                 "odometry needs a sealed episode seed material")
        self.seed_material = episode_seed_material
        self.templates = {
            str(name): dict(request)
            for name, request in action_request_templates.items()
        }
        _require(set(self.templates) ==
                 set(TRANSLATION_ACTIONS) | set(YAW_ACTIONS) | set(PITCH_ACTIONS),
                 "odometry needs all eight registered action templates")
        self._x = 0.0
        self._z = 0.0
        self._yaw = 0.0
        self._pitch = 0.0
        self._index = 0
        self._applied: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ pose --
    @property
    def observation_index(self) -> int:
        return self._index

    def pose(self) -> dict[str, Any]:
        """The current episode-relative estimate; observation zero is identity."""

        yaw = math.radians(self._yaw)
        pitch = math.radians(self._pitch)
        cy, sy = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
        cx, sx = math.cos(pitch / 2.0), math.sin(pitch / 2.0)
        return {
            "schema_version": POSE_SCHEMA,
            "frame": "episode_relative_observation_zero_origin",
            "observation_index": self._index,
            "position_m": [self._x, 0.0, self._z],
            "yaw_deg": self._yaw,
            "pitch_deg": self._pitch,
            "quaternion_xyzw": [
                float(sx * cy), float(cx * sy), float(-sx * sy), float(cx * cy),
            ],
            "is_world_pose": False,
            "noise_model_id": NOISE_MODEL_ID,
        }

    def applied_increments(self) -> list[dict[str, Any]]:
        return clone_json(self._applied)

    # --------------------------------------------------------------- advance --
    def advance(self, action_name: str) -> dict[str, Any]:
        """Apply one registered action's commanded delta plus declared noise."""

        _require(action_name in self.templates,
                 f"{action_name} is not a registered camera action")
        request = self.templates[action_name]
        index = self._index + 1
        tag = f"{self.seed_material}|{index:04d}|{action_name}"

        if action_name in TRANSLATION_ACTIONS:
            commanded = float(request["moveMagnitude"])
            realised = commanded * (
                1.0 + self.sigma["translation_relative_sigma"] *
                _gaussian(tag + "|scale")
            ) + self.sigma["translation_absolute_sigma_m"] * _gaussian(tag + "|bias")
            slip = self.sigma["lateral_slip_sigma_m"] * _gaussian(tag + "|slip")
            lateral_unit, forward_unit = TRANSLATION_ACTIONS[action_name]
            body_x = lateral_unit * realised + (
                slip if forward_unit else 0.0
            )
            body_z = forward_unit * realised + (
                slip if lateral_unit else 0.0
            )
            heading = math.radians(self._yaw)
            self._x += body_x * math.cos(heading) + body_z * math.sin(heading)
            self._z += body_z * math.cos(heading) - body_x * math.sin(heading)
            increment = {
                "action": action_name, "commanded_m": commanded,
                "estimated_m": realised, "lateral_slip_m": slip,
            }
        elif action_name in YAW_ACTIONS:
            commanded = float(request["degrees"]) * YAW_ACTIONS[action_name]
            realised = commanded * (
                1.0 + self.sigma["rotation_relative_sigma"] *
                _gaussian(tag + "|scale")
            ) + self.sigma["rotation_absolute_sigma_deg"] * _gaussian(tag + "|bias")
            self._yaw = (self._yaw + realised + 180.0) % 360.0 - 180.0
            increment = {
                "action": action_name, "commanded_deg": commanded,
                "estimated_deg": realised,
            }
        else:
            commanded = float(request["degrees"]) * PITCH_ACTIONS[action_name]
            realised = commanded * (
                1.0 + self.sigma["rotation_relative_sigma"] *
                _gaussian(tag + "|scale")
            ) + self.sigma["rotation_absolute_sigma_deg"] * _gaussian(tag + "|bias")
            self._pitch += realised
            increment = {
                "action": action_name, "commanded_deg": commanded,
                "estimated_deg": realised,
            }

        self._index = index
        self._applied.append(increment)
        return self.pose()


def dead_reckoned_poses(
    action_names: list[str], *, noise_model: Mapping[str, Any],
    action_request_templates: Mapping[str, Mapping[str, Any]],
    episode_seed_material: str,
) -> list[dict[str, Any]]:
    """Return N+1 episode-relative poses for N registered actions."""

    odometry = DeclaredOdometry(
        noise_model=noise_model,
        action_request_templates=action_request_templates,
        episode_seed_material=episode_seed_material,
    )
    poses = [odometry.pose()]
    for action_name in action_names:
        poses.append(odometry.advance(action_name))
    return poses
