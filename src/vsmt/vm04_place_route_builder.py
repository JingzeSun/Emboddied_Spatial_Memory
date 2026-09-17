"""Z-route family constructor for the D-206 place layer.

The entity-layer builder searches a public pose graph for the shortest
visible -> hidden -> reobserved branch.  A place-layer family cannot be found
that way, because what makes it a place-layer family is a *shape* that has to
be registered in advance: corridor A, a registered turn, a connecting segment,
the opposite turn, and a visually similar corridor B.  The discriminating
signal is the heading and translation drift accumulated along that shape, so
the geometry is an input to be sealed, not an outcome to be searched for.

Three properties are enforced here that the entity schema does not express.

* **Two registered turns, opposite in sign.**  One turn is a corner; two
  opposite turns are what put corridor B alongside corridor A so that the two
  can be confused in the drifted relative frame.
* **A mandatory later disambiguating observation.**  D-206 is explicit that
  without it the family only tests one-shot association.  With it the family
  tests whether an early wrong place commitment can be revised and how long it
  contaminates the memory, which is what contamination AUC measures.
* **A nonempty ambiguous-commitment window inside corridor B.**  If the route
  never actually observes corridor B while the corridor-A anchor is hidden,
  there is no wrong commitment to revise.

Every planned step is verified against the real sealed reachable scan before
the plan is returned.  A geometry that does not fit the house is a construction
failure of that episode; D-182 forbids changing house, target or route after a
failure, and D-207 forbids relaxing a tolerance to raise yield.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from cpmt.hashing import clone_json

from .vm04_observation_runner import (
    BRANCH_STATES,
    PROGRAMS,
    ROUTE_SCHEMA,
    WORLD_INTERVENTION_PROGRAMS,
    _hex64,
    _payload_sha,
    _pose,
    _require,
    _sha,
    _translation,
    _yaw_distance,
    validate_approved_contract,
    validate_public_visibility_assessment,
    validate_registered_action_request_templates,
    validate_route_plan,
    validate_visibility_builder_receipt_binding,
)
from .vm04_reachable_scan import (
    ReachableGrid,
    nominal_route_poses,
    registered_grid_size_m,
    seal_route_step_reachability,
)


Z_GEOMETRY_SCHEMA = "vsmt-vm04-z-route-geometry-v1"
Z_FAMILY_RECEIPT_SCHEMA = "vsmt-vm04-z-route-family-receipt-v1"
PLACE_LAYER = "place"
TURN_ACTIONS = {"RotateLeft": "RotateRight", "RotateRight": "RotateLeft"}

#: Field set of one sealed pre-intervention observation of the planned route.
SCAN_ROW_FIELDS = {
    "observation_index", "pose", "visibility_assessment",
    "visibility_builder_receipt", "public_evidence_sha256",
    "current_public_depth_sha256", "camera_calibration_and_pose_sha256",
    "scan_phase", "support_role", "future_or_action_outcome_used",
}


def _self_sha(record: Mapping[str, Any], digest_field: str) -> str:
    payload = {key: value for key, value in dict(record).items()
               if key != digest_field}
    return _sha(payload)


def registered_place_programs(contract: Mapping[str, Any]) -> frozenset[str]:
    """Derive the place-layer corrective programs from the contract itself."""

    approved = validate_approved_contract(contract)
    revision = approved.get("place_identity_revision")
    _require(type(revision) is dict,
             "this contract has no D-206 place identity revision block")
    _require(revision.get("place_is_learnable") is True,
             "a place-layer family requires a contract where place is learnable")
    _require(revision.get("place_scaffold_deterministic_identity_retired") is True,
             "the deterministic place scaffold must be retired before a "
             "place-layer family can be constructed")
    corrective = revision.get("corrective_programs")
    _require(type(corrective) is dict and corrective,
             "the contract registers no place-layer corrective programs")
    programs = set()
    for value in corrective.values():
        _require(type(value) is str and value, "corrective program must be text")
        token = value.split()[-1].upper()
        _require(token in PROGRAMS,
                 f"corrective program {value!r} is not a registered program")
        programs.add(token)
    return frozenset(programs)


def _place_route_budget(contract: Mapping[str, Any]) -> int:
    approved = validate_approved_contract(contract)
    budgets = approved["observation_trajectory"].get(
        "maximum_route_steps_by_family_layer")
    _require(type(budgets) is dict and PLACE_LAYER in budgets,
             "this contract registers no place-layer route budget")
    return int(budgets[PLACE_LAYER])


def _positive_multiple(value: Any, unit: float, name: str) -> int:
    _require(type(value) in {int, float} and math.isfinite(float(value)) and
             float(value) > 0.0, f"{name} must be a positive finite number")
    count = round(float(value) / unit)
    _require(count >= 1 and abs(float(value) - count * unit) <= 1e-9,
             f"{name} must be a whole multiple of the frozen registered step")
    return count


def validate_z_route_geometry(
    geometry: Mapping[str, Any], *, contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the pre-registered Z geometry against the D-206 registration."""

    approved = validate_approved_contract(contract)
    registered = approved["place_identity_revision"]["z_route_family"]
    expected = {
        "schema_version", "corridor_a_length_m", "connector_length_m",
        "corridor_b_length_m", "turn_degrees", "first_turn",
        "corridor_a_public_ref", "corridor_b_public_ref",
        "corridors_visually_similar_by_construction",
        "later_disambiguation", "sealed_before_generation",
        "tuned_after_seeing_outcomes", "geometry_sha256",
    }
    _require(type(geometry) is dict and set(geometry) == expected,
             "Z route geometry has unexpected fields")
    _require(geometry["schema_version"] == Z_GEOMETRY_SCHEMA,
             "wrong Z route geometry schema")
    _require(geometry["sealed_before_generation"] is True,
             "Z route geometry must be pre-registered before generation")
    _require(geometry["tuned_after_seeing_outcomes"] is False,
             "Z route geometry may not be tuned after seeing outcomes")
    _require(registered.get("geometry_may_be_tuned_after_seeing_outcomes")
             is False,
             "the contract no longer forbids tuning the Z geometry")
    _require(geometry["corridors_visually_similar_by_construction"] is True and
             registered.get("corridors_must_be_visually_similar_by_construction")
             is True,
             "the two corridors must be visually similar by construction")
    _require(registered.get("requires_two_registered_turns") is True,
             "the contract no longer registers the two-turn Z shape")

    for name in ("corridor_a_public_ref", "corridor_b_public_ref"):
        _require(type(geometry[name]) is str and geometry[name],
                 f"{name} must be a nonempty anonymous public reference")
    _require(geometry["corridor_a_public_ref"] !=
             geometry["corridor_b_public_ref"],
             "the two corridors must be distinct public references")
    _require(geometry["first_turn"] in TURN_ACTIONS,
             "the first registered turn must be a registered rotation")

    disambiguation = geometry["later_disambiguation"]
    _require(type(disambiguation) is dict and set(disambiguation) == {
        "registered_actions", "distinguishing_public_ref",
        "sealed_before_generation",
    }, "later disambiguation has unexpected fields")
    _require(disambiguation["sealed_before_generation"] is True,
             "the later disambiguation must be pre-registered")
    _require(type(disambiguation["distinguishing_public_ref"]) is str and
             disambiguation["distinguishing_public_ref"],
             "the later disambiguation needs a public distinguishing reference")
    actions = disambiguation["registered_actions"]
    allowed = set(approved["observation_trajectory"]
                  ["registered_post_initial_actions"])
    _require(type(actions) is list and actions,
             "a Z route without a later disambiguating observation only tests "
             "one-shot association and is refused")
    _require(all(type(name) is str and name in allowed for name in actions),
             "the later disambiguation uses an unregistered camera action")
    _require(type(registered.get("required_later_disambiguation")) is str and
             registered["required_later_disambiguation"],
             "the contract no longer requires a later disambiguation")

    # Lengths and turns are checked here, not only at expansion time, so a
    # geometry that the frozen 0.25 m / 30 degree steps cannot express is never
    # sealed in the first place.
    grid = registered_grid_size_m(approved)
    templates = validate_registered_action_request_templates(
        approved["observation_trajectory"]["registered_action_request_templates"]
    )
    turn_step = float(templates[geometry["first_turn"]]["degrees"])
    _require(turn_step == float(
        templates[TURN_ACTIONS[geometry["first_turn"]]]["degrees"]),
        "the two registered rotations must share one frozen magnitude")
    for name in ("corridor_a_length_m", "connector_length_m",
                 "corridor_b_length_m"):
        _positive_multiple(geometry[name], grid, name)
    _positive_multiple(geometry["turn_degrees"], turn_step, "turn_degrees")

    _hex64(geometry["geometry_sha256"], "geometry_sha256")
    _require(geometry["geometry_sha256"] ==
             _self_sha(geometry, "geometry_sha256"),
             "Z route geometry digest mismatch")
    return clone_json(dict(geometry))


def seal_z_route_geometry(
    *, corridor_a_length_m: float, connector_length_m: float,
    corridor_b_length_m: float, turn_degrees: float, first_turn: str,
    corridor_a_public_ref: str, corridor_b_public_ref: str,
    later_disambiguation_actions: Sequence[str],
    distinguishing_public_ref: str, contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Seal one pre-registered Z geometry, digest included."""

    geometry = {
        "schema_version": Z_GEOMETRY_SCHEMA,
        "corridor_a_length_m": float(corridor_a_length_m),
        "connector_length_m": float(connector_length_m),
        "corridor_b_length_m": float(corridor_b_length_m),
        "turn_degrees": float(turn_degrees),
        "first_turn": first_turn,
        "corridor_a_public_ref": corridor_a_public_ref,
        "corridor_b_public_ref": corridor_b_public_ref,
        "corridors_visually_similar_by_construction": True,
        "later_disambiguation": {
            "registered_actions": list(later_disambiguation_actions),
            "distinguishing_public_ref": distinguishing_public_ref,
            "sealed_before_generation": True,
        },
        "sealed_before_generation": True,
        "tuned_after_seeing_outcomes": False,
    }
    geometry["geometry_sha256"] = _self_sha(geometry, "geometry_sha256")
    return validate_z_route_geometry(geometry, contract=contract)


def z_route_segments(
    geometry: Mapping[str, Any], *, contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Expand the sealed geometry into registered actions and segment bounds.

    Observation index ``i`` is the state after action ``i - 1``, so a segment of
    ``n`` actions starting after observation ``s`` covers observations
    ``s + 1 .. s + n``.
    """

    approved = validate_approved_contract(contract)
    sealed = validate_z_route_geometry(geometry, contract=approved)
    templates = validate_registered_action_request_templates(
        approved["observation_trajectory"]["registered_action_request_templates"]
    )
    grid = registered_grid_size_m(approved)
    first_turn = sealed["first_turn"]
    second_turn = TURN_ACTIONS[first_turn]
    turn_step = float(templates[first_turn]["degrees"])
    _require(turn_step == float(templates[second_turn]["degrees"]),
             "the two registered rotations must share one frozen magnitude")

    a_steps = _positive_multiple(
        sealed["corridor_a_length_m"], grid, "corridor_a_length_m")
    c_steps = _positive_multiple(
        sealed["connector_length_m"], grid, "connector_length_m")
    b_steps = _positive_multiple(
        sealed["corridor_b_length_m"], grid, "corridor_b_length_m")
    turn_steps = _positive_multiple(
        sealed["turn_degrees"], turn_step, "turn_degrees")
    disambiguation = list(sealed["later_disambiguation"]["registered_actions"])

    actions = (
        ["MoveAhead"] * a_steps +
        [first_turn] * turn_steps +
        ["MoveAhead"] * c_steps +
        [second_turn] * turn_steps +
        ["MoveAhead"] * b_steps +
        disambiguation
    )
    a_end = a_steps
    t1_end = a_end + turn_steps
    c_end = t1_end + c_steps
    t2_end = c_end + turn_steps
    b_end = t2_end + b_steps
    d_end = b_end + len(disambiguation)
    _require(d_end == len(actions), "Z route segment arithmetic is inconsistent")

    budget = _place_route_budget(approved)
    _require(len(actions) <= budget,
             f"the sealed Z geometry needs {len(actions)} registered actions "
             f"but the place-layer budget is {budget}")
    return {
        "registered_action_names": actions,
        "first_turn": first_turn,
        "second_turn": second_turn,
        "turn_actions_each": turn_steps,
        "segments": {
            "corridor_a": [0, a_end],
            "first_turn": [a_end + 1, t1_end],
            "connector": [t1_end + 1, c_end],
            "second_turn": [c_end + 1, t2_end],
            "corridor_b": [t2_end + 1, b_end],
            "later_disambiguation": [b_end + 1, d_end],
        },
        "hidden_window": [a_end + 1, b_end],
        "place_layer_budget": budget,
    }


def _validate_scan_rows(
    rows: Sequence[Mapping[str, Any]], *, planned_poses: Sequence[Mapping[str, float]],
    subject_public_ref: str, subject_seal_sha256: str,
    visibility_config_sha256: str, contract: Mapping[str, Any],
) -> dict[int, dict[str, Any]]:
    """Validate the pre-intervention public scan of every planned observation."""

    approved = validate_approved_contract(contract)
    tolerance = approved["observation_trajectory"]["frozen_numeric_values"]
    by_index: dict[int, dict[str, Any]] = {}
    for raw in rows:
        _require(type(raw) is dict and set(raw) == SCAN_ROW_FIELDS,
                 "Z route scan row has unexpected fields")
        _require(raw["scan_phase"] == "pre_intervention_public_route_scan",
                 "the Z route scan must be sealed before the intervention")
        _require(
            raw["support_role"] ==
            "pre_intervention_public_subject_or_locus_not_post_action_confirmation",
            "Z route scan support has an invalid role",
        )
        _require(raw["future_or_action_outcome_used"] is False,
                 "Z route scan used future or action-outcome information")
        index = raw["observation_index"]
        _require(type(index) is int and 0 <= index < len(planned_poses) and
                 index not in by_index,
                 "Z route scan observation indices must be unique and planned")
        pose = _pose(raw["pose"], "Z route scan pose")
        planned = planned_poses[index]
        _require(_translation(pose, planned) <= tolerance["pose_tolerance_m"] and
                 _yaw_distance(pose["yaw_deg"], planned["yaw_deg"]) <=
                 tolerance["yaw_tolerance_degrees"],
                 f"Z route scan observation {index} is not at its planned pose")
        assessment = validate_public_visibility_assessment(
            raw["visibility_assessment"],
            expected_subject_public_ref=subject_public_ref,
        )
        builder_receipt = validate_visibility_builder_receipt_binding(
            raw["visibility_builder_receipt"], assessment=assessment,
            observation_index=index,
            expected_subject_seal_sha256=subject_seal_sha256,
            expected_config_sha256=visibility_config_sha256,
            expected_current_public_depth_sha256=
                raw["current_public_depth_sha256"],
            expected_camera_calibration_and_pose_sha256=
                raw["camera_calibration_and_pose_sha256"],
        )
        _hex64(raw["public_evidence_sha256"], "public_evidence_sha256")
        _require(raw["public_evidence_sha256"] == builder_receipt["receipt_sha256"],
                 "Z route scan evidence does not bind its visibility receipt")
        by_index[index] = {
            "observation_index": index,
            "pose": pose,
            "visibility_state": assessment["visibility_state"],
            "has_public_support":
                assessment["current_public_support_sha256"] is not None,
            "public_evidence_sha256": raw["public_evidence_sha256"],
        }
    _require(set(by_index) == set(range(len(planned_poses))),
             "the Z route scan must cover observation zero plus every planned step")
    return by_index


def build_z_route_plan(
    *, episode_id: str, program: str, branch_type: str,
    visibility_subject_public_ref: str, visibility_subject_seal_sha256: str,
    visibility_builder_config_sha256: str,
    geometry: Mapping[str, Any], initial_pose: Mapping[str, Any],
    reachable_scan: Mapping[str, Any],
    pose_scan_rows: Sequence[Mapping[str, Any]],
    contract: Mapping[str, Any],
    split_merge_artifact_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one sealed place-layer Z route, or record a construction failure.

    Returns the private route plan together with its step-reachability receipt
    and a Z-family provenance receipt.  The two receipts are separate records
    rather than new plan fields, because the route plan schema is frozen.
    """

    approved = validate_approved_contract(contract)
    place_programs = registered_place_programs(approved)
    _require(type(episode_id) is str and episode_id, "episode_id must be nonempty")
    _require(program in place_programs,
             f"{program} is not a registered place-layer corrective program")
    _require(branch_type in BRANCH_STATES, "branch type is not registered")
    if program in {"SPLIT", "MERGE"}:
        _require(split_merge_artifact_plan is not None,
                 "a place-layer SPLIT or MERGE needs a pre-registered artifact "
                 "plan; this builder does not invent one")
    else:
        _require(split_merge_artifact_plan is None,
                 "only SPLIT and MERGE may carry an artifact plan")
    _require(type(visibility_subject_public_ref) is str and
             visibility_subject_public_ref,
             "visibility subject public ref must be nonempty")
    _hex64(visibility_subject_seal_sha256, "visibility_subject_seal_sha256")
    _hex64(visibility_builder_config_sha256, "visibility_builder_config_sha256")

    sealed_geometry = validate_z_route_geometry(geometry, contract=approved)
    expansion = z_route_segments(sealed_geometry, contract=approved)
    action_names = expansion["registered_action_names"]
    planned = nominal_route_poses(initial_pose, action_names, contract=approved)

    grid = ReachableGrid(reachable_scan, contract=approved)
    for index, pose in enumerate(planned):
        _require(grid.pose_is_reachable(pose),
                 f"planned observation {index} of the Z route is not on a "
                 f"verified reachable cell")

    scan = _validate_scan_rows(
        pose_scan_rows, planned_poses=planned,
        subject_public_ref=visibility_subject_public_ref,
        subject_seal_sha256=visibility_subject_seal_sha256,
        visibility_config_sha256=visibility_builder_config_sha256,
        contract=approved,
    )

    numbers = approved["observation_trajectory"]["frozen_numeric_values"]
    minimum_each = numbers["minimum_public_observations_per_visibility_state"]
    hidden_state = BRANCH_STATES[branch_type]
    segments = expansion["segments"]

    def _visible(row: Mapping[str, Any]) -> bool:
        return row["visibility_state"] == "visible" and row["has_public_support"]

    def _hidden(row: Mapping[str, Any]) -> bool:
        return row["visibility_state"] == hidden_state

    def _indices(bounds: Sequence[int], predicate) -> list[int]:
        first, last = bounds
        return [index for index in range(first, last + 1)
                if predicate(scan[index])]

    precondition = _indices(segments["corridor_a"], _visible)
    challenge = _indices(expansion["hidden_window"], _hidden)
    reobserved = _indices(segments["later_disambiguation"], _visible)
    corridor_b_hidden = _indices(segments["corridor_b"], _hidden)

    _require(len(precondition) >= minimum_each,
             "corridor A does not establish the place anchor publicly")
    _require(len(challenge) >= minimum_each,
             "the Z route has too few hidden observations between the corridors")
    _require(len(reobserved) >= minimum_each,
             "the later disambiguating observation is not publicly supported")
    _require(corridor_b_hidden,
             "corridor B is never observed while the corridor A anchor is "
             "hidden, so the family has no ambiguous commitment to revise")
    _require(max(precondition) < min(challenge) and
             max(challenge) < min(reobserved),
             "Z route phase order is invalid")

    anchors = {
        "precondition": scan[max(precondition)]["pose"],
        "challenge": scan[max(challenge)]["pose"],
        "reobservation": scan[max(reobserved)]["pose"],
    }
    terminal_minimum = (
        approved["lifecycle_poststate_policy"]
        ["multiview_terminal_reobservation_window"]
        ["minimum_registered_public_observations"]
    )
    terminal = reobserved[-terminal_minimum:]
    _require(terminal == list(range(terminal[0], terminal[0] + len(terminal))),
             "the terminal reobservation window is not consecutive")

    subject_kind = "reveal_locus" if program == "BIRTH" else (
        "old_track_and_new_reveal_locus" if program == "REPLACE"
        else "target_track")
    plan = {
        "schema_version": ROUTE_SCHEMA,
        "episode_id": episode_id,
        "program": program,
        "branch_type": branch_type,
        "visibility_subject_kind": subject_kind,
        "visibility_subject_public_ref": visibility_subject_public_ref,
        "visibility_subject_seal_sha256": visibility_subject_seal_sha256,
        "visibility_builder_config_sha256": visibility_builder_config_sha256,
        "initial_pose": _pose(initial_pose, "initial pose"),
        "registered_actions": [
            {"step_index": index, "action": name}
            for index, name in enumerate(action_names)
        ],
        "phase_observation_indices": {
            "precondition_visible": precondition,
            "challenge_hidden": challenge,
            "reobserved": reobserved,
        },
        "planned_poses": anchors,
        "intervention_after_observation_index": (
            challenge[-1] if program in WORLD_INTERVENTION_PROGRAMS else None
        ),
        "terminal_reobservation_indices": terminal,
        "family_layer": PLACE_LAYER,
        "split_merge_artifact_plan": (
            clone_json(dict(split_merge_artifact_plan))
            if split_merge_artifact_plan is not None else None
        ),
    }
    plan["route_plan_sha256"] = _payload_sha(plan)
    route = validate_route_plan(plan, contract=approved)

    reachability = seal_route_step_reachability(
        plan=route, scan=reachable_scan, contract=approved,
    )
    receipt = {
        "schema_version": Z_FAMILY_RECEIPT_SCHEMA,
        "episode_id": episode_id,
        "family_layer": PLACE_LAYER,
        "route_plan_sha256": route["route_plan_sha256"],
        "geometry_sha256": sealed_geometry["geometry_sha256"],
        "reachable_scan_sha256": grid.reachable_scan_sha256,
        "step_reachability_sha256": reachability["step_reachability_sha256"],
        "segments": clone_json(segments),
        "registered_turns": {
            "first": expansion["first_turn"],
            "second": expansion["second_turn"],
            "actions_each": expansion["turn_actions_each"],
            "turns_are_opposite": True,
        },
        "corridor_a_public_ref": sealed_geometry["corridor_a_public_ref"],
        "corridor_b_public_ref": sealed_geometry["corridor_b_public_ref"],
        "corridors_visually_similar_by_construction": True,
        "ambiguous_commitment_observation_indices": corridor_b_hidden,
        "later_disambiguation_observation_indices": reobserved,
        "distinguishing_public_ref":
            sealed_geometry["later_disambiguation"]["distinguishing_public_ref"],
        "registered_action_count": len(action_names),
        "place_layer_budget": expansion["place_layer_budget"],
        "failed_route_replacement_allowed": False,
    }
    receipt["z_route_receipt_sha256"] = _self_sha(
        receipt, "z_route_receipt_sha256")
    return {
        "route_plan": route,
        "step_reachability": reachability,
        "z_route_receipt": receipt,
    }
