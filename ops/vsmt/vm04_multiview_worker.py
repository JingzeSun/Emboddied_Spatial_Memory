"""Injected-controller worker core for post-D-183 multiview episodes.

A trusted extractor strips simulator-private metadata before the public capture
callback runs.  Private program/instance data reaches only the intervention
callback, and only after a public hidden assessment has been sealed.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Callable, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
OPS = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(OPS) not in sys.path:
    sys.path.insert(0, str(OPS))

from vsmt.vm04_observation_runner import (  # noqa: E402
    ObservationConstructionError,
    assess_route_receipt,
    assert_generation_authorized,
    validate_registered_action_request_templates,
    validate_public_visibility_assessment,
    validate_route_plan,
)


TrustedPublicFrameExtractor = Callable[[Any, int], Mapping[str, Any]]
PublicCapture = Callable[[Mapping[str, Any], int, str, bool], Mapping[str, Any]]
PrivateIntervention = Callable[[Any, Mapping[str, Any]], Mapping[str, Any]]

PUBLIC_FRAME_KEYS = {
    "rgb", "depth_m", "camera", "source_frame_sha256",
    "private_fields_removed",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ObservationConstructionError(message)


def _metadata(event: Any) -> Mapping[str, Any]:
    metadata = getattr(event, "metadata", None)
    _require(type(metadata) is dict, "simulator event metadata is missing")
    return metadata


def _actual_pose(event: Any) -> dict[str, float]:
    metadata = _metadata(event)
    agent = metadata.get("agent")
    _require(type(agent) is dict, "simulator agent metadata is missing")
    position = agent.get("position")
    rotation = agent.get("rotation")
    _require(type(position) is dict and type(rotation) is dict,
             "simulator agent pose is missing")
    values = {
        "x_m": position.get("x"), "y_m": position.get("y"),
        "z_m": position.get("z"), "yaw_deg": rotation.get("y"),
    }
    _require(all(type(value) in {int, float} for value in values.values()),
             "simulator agent pose is not numeric")
    return {key: float(value) for key, value in values.items()}


def _action_success(event: Any) -> bool:
    value = _metadata(event).get("lastActionSuccess")
    _require(type(value) is bool, "simulator action success is missing")
    return value


def _public_frame(
    event: Any, observation_index: int,
    extractor: TrustedPublicFrameExtractor,
) -> dict[str, Any]:
    frame = dict(extractor(event, observation_index))
    _require(set(frame) == PUBLIC_FRAME_KEYS,
             "trusted public frame extractor returned unexpected fields")
    _require(frame["private_fields_removed"] is True,
             "trusted public frame extractor did not attest private removal")
    digest = frame["source_frame_sha256"]
    _require(type(digest) is str and len(digest) == 64 and
             all(character in "0123456789abcdef" for character in digest),
             "trusted public frame digest is invalid")
    _require(type(frame["camera"]) is dict,
             "trusted public camera record is invalid")
    return frame


def _capture_row(
    *, event: Any, observation_index: int, route: Mapping[str, Any],
    trusted_public_frame_extractor: TrustedPublicFrameExtractor,
    public_capture: PublicCapture,
) -> dict[str, Any]:
    terminal = observation_index in route["terminal_reobservation_indices"]
    frame = _public_frame(
        event, observation_index, trusted_public_frame_extractor)
    captured = dict(public_capture(
        frame, observation_index, route["visibility_subject_public_ref"], terminal,
    ))
    _require(set(captured) == {"visibility_assessment", "public_evidence_sha256"},
             "public capture returned unexpected fields")
    assessment = validate_public_visibility_assessment(
        captured["visibility_assessment"],
        expected_subject_public_ref=route["visibility_subject_public_ref"],
    )
    evidence = captured["public_evidence_sha256"]
    _require(type(evidence) is str and len(evidence) == 64 and
             all(character in "0123456789abcdef" for character in evidence),
             "public evidence digest is invalid")
    return {
        "observation_index": observation_index,
        "visibility_assessment": assessment,
        "public_evidence_sha256": evidence,
        "actual_pose": _actual_pose(event),
        "registered_camera_action_success": _action_success(event),
    }


def _prefix_failure(
    *, route: Mapping[str, Any], observations: list[dict[str, Any]],
    reason: str, intervention_executed: bool,
    private_intervention_record: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "status": "raw_failure",
        "reason": reason,
        "route_plan_sha256": route["route_plan_sha256"],
        "public_observation_prefix": observations,
        "intervention_executed": intervention_executed,
        "private_intervention_record": (
            dict(private_intervention_record)
            if private_intervention_record is not None else None
        ),
        "failed_route_replacement_allowed": False,
    }


def _execute_route_core(
    controller: Any, *, plan: Mapping[str, Any], contract: Mapping[str, Any],
    action_request_templates: Mapping[str, Mapping[str, Any]],
    trusted_public_frame_extractor: TrustedPublicFrameExtractor,
    public_capture: PublicCapture,
    private_intervention: PrivateIntervention | None,
) -> dict[str, Any]:
    """Review/test core; production callers must use ``run_authorized_route``."""

    route = validate_route_plan(plan, contract=contract)
    initial = route["initial_pose"]
    event = controller.step(
        action="TeleportFull",
        position={"x": initial["x_m"], "y": initial["y_m"],
                  "z": initial["z_m"]},
        rotation={"x": 0.0, "y": initial["yaw_deg"], "z": 0.0},
        horizon=0.0,
        standing=True,
        forceAction=False,
    )
    observations = [_capture_row(
        event=event, observation_index=0, route=route,
        trusted_public_frame_extractor=trusted_public_frame_extractor,
        public_capture=public_capture,
    )]
    if not observations[0]["registered_camera_action_success"]:
        return _prefix_failure(
            route=route, observations=observations,
            reason="initial_teleport_failed", intervention_executed=False,
            private_intervention_record=None,
        )

    intervention_executed = False
    private_record = None
    intervention_index = route["intervention_after_observation_index"]
    requests = validate_registered_action_request_templates(
        action_request_templates
    )
    for action_index, action_row in enumerate(route["registered_actions"]):
        request = dict(requests[action_row["action"]])
        event = controller.step(**request)
        observation_index = action_index + 1
        row = _capture_row(
            event=event, observation_index=observation_index, route=route,
            trusted_public_frame_extractor=trusted_public_frame_extractor,
            public_capture=public_capture,
        )
        observations.append(row)
        if not row["registered_camera_action_success"]:
            return _prefix_failure(
                route=route, observations=observations,
                reason="registered_camera_action_failed",
                intervention_executed=intervention_executed,
                private_intervention_record=private_record,
            )
        if observation_index == intervention_index:
            state = row["visibility_assessment"]["visibility_state"]
            if state not in {"occluded", "out_of_view"}:
                return _prefix_failure(
                    route=route, observations=observations,
                    reason="intervention_visible_to_camera",
                    intervention_executed=False,
                    private_intervention_record=None,
                )
            _require(private_intervention is not None,
                     "world-intervention route lacks a private executor")
            private_record = dict(private_intervention(event, route))
            intervention_executed = True

    receipt = {
        "schema_version": "vsmt-vm04-observation-route-receipt-v1",
        "route_plan_sha256": route["route_plan_sha256"],
        "observations": observations,
    }
    verdict = assess_route_receipt(receipt, plan=route, contract=contract)
    return {
        "status": "raw_complete" if verdict["constructed"] else "raw_failure",
        "route_receipt": receipt,
        "construction_verdict": verdict,
        "intervention_executed": intervention_executed,
        "private_intervention_record": private_record,
        "failed_route_replacement_allowed": False,
    }


def run_authorized_route(
    controller: Any, *, plan: Mapping[str, Any], contract: Mapping[str, Any],
    episode_root: Path,
    public_capture: PublicCapture,
    private_intervention: PrivateIntervention | None,
) -> dict[str, Any]:
    """Production wrapper: fail before controller use until all gates are open."""

    assert_generation_authorized(contract)
    from vm04_multiview_raw import RawEpisodeStore

    templates = contract["observation_trajectory"][
        "registered_action_request_templates"]
    store = RawEpisodeStore(episode_root, plan=plan, contract=contract)
    try:
        result = _execute_route_core(
            controller, plan=plan, contract=contract,
            action_request_templates=templates,
            trusted_public_frame_extractor=store.extract_public_frame,
            public_capture=public_capture,
            private_intervention=private_intervention,
        )
    except BaseException as error:
        store.finalize_exception(error)
        raise
    raw_receipt = store.finalize(result)
    return {"worker_result": result, "raw_receipt": raw_receipt}
