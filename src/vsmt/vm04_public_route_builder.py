"""Deterministic public-geometry route search for post-D-183 VM-04.

The builder consumes only anonymous pose scans, public visibility assessments,
and a registered directed action graph.  Program assignment is construction
metadata; simulator identity and future action outcomes are not inputs.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Mapping, Sequence

from cpmt.hashing import clone_json

from .vm04_observation_runner import (
    BRANCH_STATES,
    FAMILY_LAYERS,
    PROGRAMS,
    ROUTE_SCHEMA,
    WORLD_INTERVENTION_PROGRAMS,
    ObservationConstructionError,
    _pose,
    _require,
    _route_step_budget,
    _sha,
    _translation,
    _yaw_distance,
    validate_approved_contract,
    validate_public_visibility_assessment,
    validate_visibility_builder_receipt_binding,
    validate_route_plan,
)
from .vm04_reachable_scan import ReachableGrid


def _validate_graph(
    pose_scans: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]], *,
    subject_public_ref: str, subject_seal_sha256: str,
    visibility_config_sha256: str, contract: Mapping[str, Any],
    reachable_grid: ReachableGrid | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, str]]]]:
    approved = validate_approved_contract(contract)
    allowed_actions = set(approved["observation_trajectory"]
                          ["registered_post_initial_actions"])
    nodes: dict[str, dict[str, Any]] = {}
    for raw in pose_scans:
        _require(type(raw) is dict and set(raw) == {
            "pose_id", "pose", "visibility_assessment", "public_evidence_sha256",
            "visibility_builder_receipt",
            "current_public_depth_sha256",
            "camera_calibration_and_pose_sha256",
            "scan_phase", "support_role", "future_or_action_outcome_used",
        }, "public pose scan has unexpected fields")
        _require(raw["scan_phase"] == "pre_intervention_public_route_scan",
                 "route scan must be sealed before the intervention")
        _require(
            raw["support_role"] ==
            "pre_intervention_public_subject_or_locus_not_post_action_confirmation",
            "route scan support has an invalid role",
        )
        _require(raw["future_or_action_outcome_used"] is False,
                 "route scan used future or action-outcome information")
        pose_id = raw["pose_id"]
        _require(type(pose_id) is str and pose_id and pose_id not in nodes,
                 "pose IDs must be unique nonempty strings")
        pose = _pose(raw["pose"], "public scan pose")
        assessment = validate_public_visibility_assessment(
            raw["visibility_assessment"],
            expected_subject_public_ref=subject_public_ref,
        )
        builder_receipt = validate_visibility_builder_receipt_binding(
            raw["visibility_builder_receipt"], assessment=assessment,
            observation_index=raw["visibility_builder_receipt"].get(
                "current_observation_index", -1,
            ),
            expected_subject_seal_sha256=subject_seal_sha256,
            expected_config_sha256=visibility_config_sha256,
            expected_current_public_depth_sha256=
                raw["current_public_depth_sha256"],
            expected_camera_calibration_and_pose_sha256=
                raw["camera_calibration_and_pose_sha256"],
        )
        evidence = raw["public_evidence_sha256"]
        _require(type(evidence) is str and len(evidence) == 64 and
                 all(character in "0123456789abcdef" for character in evidence),
                 "public pose evidence must be a lowercase SHA-256")
        _require(evidence == builder_receipt["receipt_sha256"],
                 "public pose evidence does not bind its visibility receipt")
        # D-207 per-step yield guard: a scanned pose that is not a verified
        # reachable cell cannot be a planned observation, because the route
        # would only discover the blocked action once the simulator runs.
        _require(reachable_grid is None or reachable_grid.pose_is_reachable(pose),
                 f"scanned pose {pose_id} is not on a verified reachable cell")
        nodes[pose_id] = {
            "pose_id": pose_id,
            "pose": pose,
            "visibility_assessment": assessment,
            "public_evidence_sha256": evidence,
        }
    _require(nodes, "public pose scan is empty")

    adjacency = {pose_id: [] for pose_id in nodes}
    seen_edges = set()
    for raw in edges:
        _require(type(raw) is dict and set(raw) == {
            "from_pose_id", "to_pose_id", "action",
        }, "public route edge has unexpected fields")
        source = raw["from_pose_id"]
        target = raw["to_pose_id"]
        action = raw["action"]
        _require(source in nodes and target in nodes,
                 "public route edge references an unknown pose")
        _require(action in allowed_actions, "public route edge action is unregistered")
        key = (source, action, target)
        _require(key not in seen_edges, "public route edge is duplicated")
        seen_edges.add(key)
        adjacency[source].append({
            "from_pose_id": source, "to_pose_id": target, "action": action,
        })
    for rows in adjacency.values():
        rows.sort(key=lambda row: (row["action"], row["to_pose_id"]))
    return nodes, adjacency


def _has_public_support(node: Mapping[str, Any]) -> bool:
    return node["visibility_assessment"]["current_public_support_sha256"] is not None


def build_route_plan_from_public_graph(
    *, episode_id: str, program: str, branch_type: str,
    visibility_subject_public_ref: str, visibility_subject_seal_sha256: str,
    visibility_builder_config_sha256: str,
    pose_scans: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    split_merge_artifact_plan: Mapping[str, Any] | None,
    contract: Mapping[str, Any],
    family_layer: str = "entity",
    reachable_scan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the shortest deterministic route satisfying D-182/D-183.

    ``family_layer`` selects the D-207 registered action budget: the entity
    layer keeps the frozen D-182 cap, the place layer gets the longer budget a
    Z-route needs.

    Passing ``reachable_scan`` restricts the search to poses that a real sealed
    ``GetReachablePositions`` scan verified, which is the D-207 per-step yield
    guard for this builder: every scanned pose the search may plan through is
    already a reachable cell.  It is optional only so that the pure schema
    tests can keep running without a scan; production callers pass one.
    """

    approved = validate_approved_contract(contract)
    _require(family_layer in FAMILY_LAYERS, "family layer is not registered")
    _require(program in PROGRAMS, "program is not registered")
    _require(branch_type in BRANCH_STATES, "branch type is not registered")
    _require(type(episode_id) is str and episode_id, "episode_id must be nonempty")
    _require(type(visibility_subject_public_ref) is str and
             visibility_subject_public_ref,
             "visibility subject public ref must be nonempty")
    grid = (None if reachable_scan is None else
            ReachableGrid(reachable_scan, contract=approved))
    nodes, adjacency = _validate_graph(
        pose_scans, edges, subject_public_ref=visibility_subject_public_ref,
        subject_seal_sha256=visibility_subject_seal_sha256,
        visibility_config_sha256=visibility_builder_config_sha256,
        contract=approved, reachable_grid=grid,
    )
    hidden_state = BRANCH_STATES[branch_type]
    numbers = (
        approved["observation_trajectory"]
        ["frozen_numeric_values"]
    )
    max_steps = _route_step_budget(approved, family_layer)
    minimum_each = numbers["minimum_public_observations_per_visibility_state"]

    starts = sorted(
        pose_id for pose_id, node in nodes.items()
        if node["visibility_assessment"]["visibility_state"] == "visible"
        and _has_public_support(node)
    )
    queue = deque()
    visited: dict[tuple[Any, ...], int] = {}
    for pose_id in starts:
        queue.append({
            "pose_ids": [pose_id],
            "actions": [],
            "phase": "visible",
            "visible_indices": [0],
            "hidden_indices": [],
            "reobserved_indices": [],
            "precondition_pose_id": None,
            "challenge_pose_id": None,
        })

    while queue:
        state = queue.popleft()
        current_id = state["pose_ids"][-1]
        if len(state["actions"]) >= max_steps:
            continue
        for edge in adjacency[current_id]:
            next_id = edge["to_pose_id"]
            node = nodes[next_id]
            visibility = node["visibility_assessment"]["visibility_state"]
            index = len(state["pose_ids"])
            candidate = clone_json(state)
            candidate["pose_ids"].append(next_id)
            candidate["actions"].append(edge["action"])

            if state["phase"] == "visible":
                if visibility == "visible" and _has_public_support(node):
                    candidate["visible_indices"].append(index)
                elif (visibility == hidden_state and
                      len(state["visible_indices"]) >= minimum_each):
                    candidate["phase"] = "hidden"
                    candidate["precondition_pose_id"] = current_id
                    candidate["hidden_indices"] = [index]
                else:
                    continue
            elif state["phase"] == "hidden":
                if visibility == hidden_state:
                    candidate["hidden_indices"].append(index)
                elif (visibility == "visible" and _has_public_support(node) and
                      len(state["hidden_indices"]) >= minimum_each):
                    pre_id = state["precondition_pose_id"]
                    challenge_id = current_id
                    if _translation(nodes[pre_id]["pose"],
                                    nodes[challenge_id]["pose"]) < numbers[
                                        "minimum_key_pose_translation_m"]:
                        continue
                    candidate["phase"] = "reobserved"
                    candidate["challenge_pose_id"] = challenge_id
                    candidate["reobserved_indices"] = [index]
                else:
                    continue
            else:
                if visibility != "visible" or not _has_public_support(node):
                    continue
                candidate["reobserved_indices"].append(index)

            if (candidate["phase"] == "reobserved" and
                    len(candidate["reobserved_indices"]) >= minimum_each):
                pre_id = candidate["precondition_pose_id"]
                challenge_id = candidate["challenge_pose_id"]
                reobservation_id = next_id
                pre = nodes[pre_id]["pose"]
                challenge = nodes[challenge_id]["pose"]
                reobservation = nodes[reobservation_id]["pose"]
                if _translation(pre, reobservation) < numbers[
                        "minimum_reobservation_translation_m"]:
                    continue
                if max(_yaw_distance(pre["yaw_deg"], challenge["yaw_deg"]),
                       _yaw_distance(pre["yaw_deg"], reobservation["yaw_deg"])) < numbers[
                           "minimum_key_pose_yaw_change_degrees"]:
                    continue
                actions = [
                    {"step_index": action_index, "action": action}
                    for action_index, action in enumerate(candidate["actions"])
                ]
                subject_kind = "reveal_locus" if program == "BIRTH" else (
                    "old_track_and_new_reveal_locus" if program == "REPLACE"
                    else "target_track"
                )
                plan = {
                    "schema_version": ROUTE_SCHEMA,
                    "episode_id": episode_id,
                    "program": program,
                    "branch_type": branch_type,
                    "visibility_subject_kind": subject_kind,
                    "visibility_subject_public_ref":
                        visibility_subject_public_ref,
                    "visibility_subject_seal_sha256":
                        visibility_subject_seal_sha256,
                    "visibility_builder_config_sha256":
                        visibility_builder_config_sha256,
                    "initial_pose": nodes[candidate["pose_ids"][0]]["pose"],
                    "registered_actions": actions,
                    "phase_observation_indices": {
                        "precondition_visible": candidate["visible_indices"],
                        "challenge_hidden": candidate["hidden_indices"],
                        "reobserved": candidate["reobserved_indices"],
                    },
                    "planned_poses": {
                        "precondition": pre,
                        "challenge": challenge,
                        "reobservation": reobservation,
                    },
                    "intervention_after_observation_index": (
                        candidate["hidden_indices"][-1]
                        if program in WORLD_INTERVENTION_PROGRAMS else None
                    ),
                    "terminal_reobservation_indices":
                        candidate["reobserved_indices"][-minimum_each:],
                    "family_layer": family_layer,
                    "split_merge_artifact_plan": (
                        clone_json(split_merge_artifact_plan)
                        if split_merge_artifact_plan is not None else None
                    ),
                }
                plan["route_plan_sha256"] = _sha(plan)
                return validate_route_plan(plan, contract=approved)

            visit_key = (
                next_id, candidate["phase"],
                min(len(candidate["visible_indices"]), minimum_each),
                min(len(candidate["hidden_indices"]), minimum_each),
                min(len(candidate["reobserved_indices"]), minimum_each),
                candidate["precondition_pose_id"], candidate["challenge_pose_id"],
            )
            depth = len(candidate["actions"])
            if visited.get(visit_key, max_steps + 1) <= depth:
                continue
            visited[visit_key] = depth
            queue.append(candidate)

    raise ObservationConstructionError(
        f"no_registered_{branch_type}_route_within_{max_steps}_steps")
