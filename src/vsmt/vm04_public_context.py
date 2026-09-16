"""Build public per-frame materialization contexts from a sealed public route."""

from __future__ import annotations

import hashlib
import math
from typing import Any, Mapping, Sequence

from cpmt.hashing import canonical_json, clone_json

REGISTERED_ACTIONS = {
    "MoveAhead", "MoveBack", "MoveLeft", "MoveRight",
    "RotateLeft", "RotateRight", "LookUp", "LookDown",
}


def _sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
PUBLIC_ROUTE_KEYS = {
    "schema_version", "consumer_scope", "episode_id", "branch_type",
    "visibility_subject_kind", "visibility_subject_public_ref", "initial_pose",
    "registered_actions", "phase_observation_indices", "planned_poses",
    "intervention_after_observation_index", "terminal_reobservation_indices",
    "private_route_plan_sha256", "public_route_sha256",
}


def _finite_vector(value: Any, name: str) -> list[float]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or not value:
        raise ValueError(f"{name} must be a nonempty numeric sequence")
    result = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"{name} must contain only numbers")
        number = float(item)
        if not math.isfinite(number):
            raise ValueError(f"{name} must contain only finite numbers")
        result.append(number)
    return result


def _validated_public_route(route: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(route, Mapping) or set(route) != PUBLIC_ROUTE_KEYS:
        raise ValueError("public route has unexpected fields")
    result = clone_json(dict(route))
    if result["schema_version"] != "vsmt-vm04-public-observation-route-v1":
        raise ValueError("wrong public route schema")
    if result["consumer_scope"] != "construction_provenance_only_not_adapter_input":
        raise ValueError("public route has the wrong consumer scope")
    actions = result["registered_actions"]
    if not isinstance(actions, list) or not actions:
        raise ValueError("public route requires registered actions")
    if any(
        type(row) is not dict
        or set(row) != {"step_index", "action"}
        or row["step_index"] != index
        or row["action"] not in REGISTERED_ACTIONS
        for index, row in enumerate(actions)
    ):
        raise ValueError("public route actions are not canonical")
    payload = clone_json(result)
    claimed = payload.pop("public_route_sha256")
    if claimed != _sha256(payload):
        raise ValueError("public route digest mismatch")
    return result


def make_public_frame_contexts(
    public_route: Mapping[str, Any], *,
    decision_times_s: Sequence[float],
    decision_time_rule_id: str,
    action_command_vectors: Mapping[str, Sequence[float]],
    action_encoding_id: str,
    robot_states: Sequence[Mapping[str, Any]],
    public_constants: Mapping[str, Any],
) -> dict[str, Any]:
    """Make N+1 contexts; observation i contains exactly actions 0..i-1."""

    route = _validated_public_route(public_route)
    for value, name in (
        (decision_time_rule_id, "decision_time_rule_id"),
        (action_encoding_id, "action_encoding_id"),
    ):
        if type(value) is not str or not value or any(char.isspace() for char in value):
            raise ValueError(f"{name} must be a nonempty token")

    if not isinstance(action_command_vectors, Mapping) or set(
        action_command_vectors
    ) != REGISTERED_ACTIONS:
        raise ValueError("action command table must cover every registered action")
    vectors = {
        action: _finite_vector(
            action_command_vectors[action], f"action_command_vectors.{action}",
        )
        for action in sorted(REGISTERED_ACTIONS)
    }
    dimensions = {len(vector) for vector in vectors.values()}
    if len(dimensions) != 1:
        raise ValueError("all action command vectors must have one dimension")
    if len({tuple(vector) for vector in vectors.values()}) != len(vectors):
        raise ValueError("registered actions must have distinct command vectors")

    count = len(route["registered_actions"]) + 1
    if isinstance(decision_times_s, (str, bytes)) or len(decision_times_s) != count:
        raise ValueError("decision times must contain one value per observation")
    times = []
    for value in decision_times_s:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("decision times must be numeric")
        number = float(value)
        if not math.isfinite(number) or number < 0.0:
            raise ValueError("decision times must be finite and nonnegative")
        times.append(number)
    if any(left >= right for left, right in zip(times, times[1:])):
        raise ValueError("decision times must be strictly increasing")
    if isinstance(robot_states, (str, bytes)) or len(robot_states) != count:
        raise ValueError("robot_states must contain one row per observation")

    completed_actions: list[dict[str, Any]] = []
    contexts = []
    for index in range(count):
        if index:
            action = route["registered_actions"][index - 1]["action"]
            completed_actions.append({
                "end_time_s": times[index],
                "command": vectors[action],
            })
        sample_id_hash = hashlib.sha256(canonical_json({
            "public_route_sha256": route["public_route_sha256"],
            "observation_index": index,
            "decision_time_s": times[index],
        }).encode("utf-8")).hexdigest()
        contexts.append({
            "sample_id_hash": sample_id_hash,
            "decision_time_s": times[index],
            "robot_state": clone_json(dict(robot_states[index])),
            "past_actions": clone_json(completed_actions),
            "public_constants": clone_json(dict(public_constants)),
        })

    manifest = {
        "schema_version": "vsmt-vm04-public-frame-context-manifest-v1",
        "public_route_sha256": route["public_route_sha256"],
        "observation_count": count,
        "decision_time_rule_id": decision_time_rule_id,
        "decision_times_sha256": _sha256(times),
        "action_encoding_id": action_encoding_id,
        "action_command_vectors_sha256": _sha256(vectors),
        "ordered_context_sha256s": [
            _sha256(context) for context in contexts
        ],
        "private_program_target_teacher_or_future_used": False,
    }
    manifest["manifest_sha256"] = _sha256(manifest)
    return {"contexts": contexts, "manifest": manifest}
