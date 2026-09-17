"""Pre-terminal temporal sealing for VM-04 public construction plans.

The reviewed materializer calls this boundary after the preceding public
packet has updated causal memory and before it opens the final registered
terminal frame.  The resulting receipt is a timing/provenance assertion only;
it does not run the matcher or establish semantic identity truth.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping

from cpmt.executor import validate_graph
from cpmt.hashing import canonical_json, clone_json

from .vm04_program_construction import make_program_construction_plan


REQUEST_SCHEMA = "vsmt-vm04-online-program-plan-request-v1"
RECEIPT_SCHEMA = "vsmt-vm04-online-program-plan-temporal-receipt-v1"
RECEIPT_SCHEMA_V2 = "vsmt-vm04-online-program-plan-temporal-receipt-v2"
BUNDLE_KEYS = {"construction_plan", "matcher_prior_memory", "temporal_receipt"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
PROGRAMS = {
    "NOOP", "BIND", "BIRTH", "REACTIVATE", "RELINK", "RETRACT",
    "SPLIT", "MERGE", "REPLACE",
}


class OnlineProgramPlanSealError(ValueError):
    """The plan request or its temporal seal is inconsistent."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise OnlineProgramPlanSealError(message)


def _hex64(value: Any, name: str) -> str:
    _require(type(value) is str and HEX64.fullmatch(value) is not None,
             f"{name} must be a lowercase SHA-256")
    return value


def _token(value: Any, name: str) -> str:
    _require(type(value) is str and value and
             not any(character.isspace() for character in value),
             f"{name} must be a nonempty token")
    return value


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _payload_sha(value: Mapping[str, Any], seal_name: str) -> str:
    payload = clone_json(dict(value))
    payload.pop(seal_name, None)
    return _sha(payload)


def _validate_parent_request_provenance_receipt(
    receipt: Mapping[str, Any], *, request: Mapping[str, Any],
    route_plan: Mapping[str, Any], prior_memory: Mapping[str, Any],
    last_completed_observation_index: int,
) -> dict[str, Any]:
    """Validate the reviewed D-203/D-204 boundary before D-202 consumes it."""

    record = clone_json(dict(receipt))
    terminal = request["terminal_observation_index"]
    _require(
        record.get("schema_version") ==
        "vsmt-vm04-parent-program-request-provenance-receipt-v2" and
        record.get("receipt_sha256") ==
        _payload_sha(record, "receipt_sha256"),
        "parent request provenance receipt is invalid",
    )
    _require(
        record.get("episode_id") == request["episode_id"] ==
        route_plan.get("episode_id") and
        record.get("program") == request["program"] ==
        route_plan.get("program") and
        record.get("route_plan_sha256") ==
        request["route_plan_sha256"] == route_plan.get("route_plan_sha256") and
        record.get("request_sha256") == request["request_sha256"] and
        record.get("prior_memory_sha256") == prior_memory["graph_hash"] and
        record.get("last_completed_observation_index") ==
        last_completed_observation_index and
        record.get("sealed_before_observation_index") == terminal,
        "parent request provenance bindings differ",
    )
    for name in (
        "precondition_refs_derived_deterministically_from_public_memory",
        "request_provenance_established_by_parent_core",
        "selector_spec_pre_terminal_registration_established",
    ):
        _require(record.get(name) is True,
                 "parent request provenance proof is incomplete")
    for name in (
        "caller_supplied_precondition_refs_used",
        "episode_root_or_raw_path_argument_available",
        "terminal_public_or_private_frame_opened",
        "future_observation_opened",
        "teacher_reference_or_private_identity_used",
        "consumed_by_D202_temporal_receipt",
        "clears_D201_temporal_seal_pending",
    ):
        _require(record.get(name) is False,
                 "parent request provenance used a forbidden channel")
    _hex64(record.get("spec_sha256"), "parent spec_sha256")
    _hex64(record.get("public_route_sha256"),
           "parent public_route_sha256")
    _hex64(record.get("parent_stage_code_sha256"),
           "parent parent_stage_code_sha256")
    _hex64(record.get("selector_temporal_receipt_sha256"),
           "parent selector_temporal_receipt_sha256")
    return record


def make_online_program_plan_request(
    *, episode_id: str, family_id: str, program: str,
    route_plan_sha256: str, terminal_observation_index: int,
    precondition_refs: Mapping[str, Any],
    visibility_subject_seal_sha256: str, matcher_config_sha256: str,
) -> dict[str, Any]:
    """Seal all non-memory plan inputs before the terminal frame is opened."""

    _require(program in PROGRAMS, "program is not registered")
    _require(type(terminal_observation_index) is int and
             terminal_observation_index > 0,
             "terminal observation index must be positive")
    _require(type(precondition_refs) is dict,
             "precondition_refs must be a mapping")
    request = {
        "schema_version": REQUEST_SCHEMA,
        "episode_id": _token(episode_id, "episode_id"),
        "family_id": _token(family_id, "family_id"),
        "program": program,
        "route_plan_sha256": _hex64(
            route_plan_sha256, "route_plan_sha256"
        ),
        "terminal_observation_index": terminal_observation_index,
        "precondition_refs": clone_json(dict(precondition_refs)),
        "visibility_subject_seal_sha256": _hex64(
            visibility_subject_seal_sha256,
            "visibility_subject_seal_sha256",
        ),
        "matcher_config_sha256": _hex64(
            matcher_config_sha256, "matcher_config_sha256"
        ),
        "private_identity_used": False,
        "teacher_or_reference_transaction_used": False,
    }
    request["request_sha256"] = _sha(request)
    return request


def validate_online_program_plan_request(
    request: Mapping[str, Any],
) -> dict[str, Any]:
    expected = {
        "schema_version", "episode_id", "family_id", "program",
        "route_plan_sha256", "terminal_observation_index",
        "precondition_refs", "visibility_subject_seal_sha256",
        "matcher_config_sha256", "private_identity_used",
        "teacher_or_reference_transaction_used", "request_sha256",
    }
    _require(type(request) is dict and set(request) == expected,
             "online program plan request has unexpected fields")
    record = clone_json(dict(request))
    _require(record["schema_version"] == REQUEST_SCHEMA,
             "wrong online program plan request schema")
    _require(record["private_identity_used"] is False and
             record["teacher_or_reference_transaction_used"] is False,
             "online plan request used a restricted input")
    rebuilt = make_online_program_plan_request(
        episode_id=record["episode_id"], family_id=record["family_id"],
        program=record["program"],
        route_plan_sha256=record["route_plan_sha256"],
        terminal_observation_index=record["terminal_observation_index"],
        precondition_refs=record["precondition_refs"],
        visibility_subject_seal_sha256=record[
            "visibility_subject_seal_sha256"
        ],
        matcher_config_sha256=record["matcher_config_sha256"],
    )
    _require(record == rebuilt, "online program plan request digest mismatch")
    return record


def seal_online_program_construction_plan(
    *, request: Mapping[str, Any], route_plan: Mapping[str, Any],
    prior_memory: Mapping[str, Any], last_completed_observation_index: int,
    materializer_code_sha256: str,
    parent_request_provenance_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create the plan and timing receipt before the terminal frame is read."""

    registered = validate_online_program_plan_request(request)
    memory = clone_json(dict(prior_memory))
    validate_graph(memory, verify_hash=True)
    _hex64(materializer_code_sha256, "materializer_code_sha256")
    terminal = registered["terminal_observation_index"]
    _require(last_completed_observation_index == terminal - 1,
             "online plan seal is not immediately before terminal observation")
    _require(
        registered["episode_id"] == route_plan.get("episode_id") and
        registered["program"] == route_plan.get("program") and
        registered["route_plan_sha256"] ==
        route_plan.get("route_plan_sha256") and
        registered["visibility_subject_seal_sha256"] ==
        route_plan.get("visibility_subject_seal_sha256") and
        type(route_plan.get("terminal_reobservation_indices")) is list and
        route_plan["terminal_reobservation_indices"] and
        route_plan["terminal_reobservation_indices"][-1] == terminal,
        "online plan request and registered route differ",
    )
    artifact_plan = route_plan.get("split_merge_artifact_plan")
    plan = make_program_construction_plan(
        episode_id=registered["episode_id"],
        family_id=registered["family_id"],
        program=registered["program"],
        prior_memory=memory,
        prior_memory_sha256=memory["graph_hash"],
        precondition_refs=registered["precondition_refs"],
        visibility_subject_seal_sha256=registered[
            "visibility_subject_seal_sha256"
        ],
        matcher_config_sha256=registered["matcher_config_sha256"],
        artifact_plan=artifact_plan,
    )
    parent_receipt = None
    if parent_request_provenance_receipt is not None:
        parent_receipt = _validate_parent_request_provenance_receipt(
            parent_request_provenance_receipt,
            request=registered,
            route_plan=route_plan,
            prior_memory=memory,
            last_completed_observation_index=last_completed_observation_index,
        )
    receipt = {
        "schema_version": RECEIPT_SCHEMA_V2 if parent_receipt else RECEIPT_SCHEMA,
        "episode_id": registered["episode_id"],
        "program": registered["program"],
        "request_sha256": registered["request_sha256"],
        "route_plan_sha256": registered["route_plan_sha256"],
        "construction_plan_sha256": plan["construction_plan_sha256"],
        "matcher_prior_memory_sha256": memory["graph_hash"],
        "matcher_config_sha256": registered["matcher_config_sha256"],
        "materializer_code_sha256": materializer_code_sha256,
        "last_completed_observation_index": last_completed_observation_index,
        "sealed_before_observation_index": terminal,
        "terminal_public_frame_opened_before_seal": False,
        "terminal_private_frame_opened_before_seal": False,
        "future_observation_opened_before_seal": False,
        "teacher_opened_before_seal": False,
        "reference_transaction_opened_before_seal": False,
        "private_identity_used": False,
        "request_provenance_established_by_parent_stage": parent_receipt is not None,
        "clears_episode_temporal_seal_pending": False,
    }
    if parent_receipt is not None:
        receipt["parent_request_provenance_receipt_sha256"] = parent_receipt[
            "receipt_sha256"
        ]
        receipt["parent_request_provenance_consumed_by_D202"] = True
    receipt["receipt_sha256"] = _sha(receipt)
    return {
        "construction_plan": plan,
        "matcher_prior_memory": memory,
        "temporal_receipt": receipt,
    }


def validate_online_program_plan_seal(
    bundle: Mapping[str, Any], *, request: Mapping[str, Any],
    route_plan: Mapping[str, Any], materializer_code_sha256: str,
    parent_request_provenance_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Rebuild a temporal seal from its exact prior memory and request."""

    _require(type(bundle) is dict and set(bundle) == BUNDLE_KEYS,
             "online program plan seal bundle has unexpected fields")
    record = clone_json(dict(bundle))
    receipt = record["temporal_receipt"]
    _require(type(receipt) is dict and
             receipt.get("schema_version") == (
                 RECEIPT_SCHEMA_V2 if parent_request_provenance_receipt
                 is not None else RECEIPT_SCHEMA
             ) and
             receipt.get("receipt_sha256") ==
             _payload_sha(receipt, "receipt_sha256"),
             "online program plan temporal receipt is invalid")
    for name in (
        "terminal_public_frame_opened_before_seal",
        "terminal_private_frame_opened_before_seal",
        "future_observation_opened_before_seal",
        "teacher_opened_before_seal",
        "reference_transaction_opened_before_seal",
        "private_identity_used",
        "clears_episode_temporal_seal_pending",
    ):
        _require(receipt.get(name) is False,
                 "online plan temporal receipt used a forbidden channel")
    _require(receipt.get("request_provenance_established_by_parent_stage") is
             (parent_request_provenance_receipt is not None),
             "online plan parent provenance state changed")
    rebuilt = seal_online_program_construction_plan(
        request=request, route_plan=route_plan,
        prior_memory=record["matcher_prior_memory"],
        last_completed_observation_index=receipt[
            "last_completed_observation_index"
        ],
        materializer_code_sha256=materializer_code_sha256,
        parent_request_provenance_receipt=parent_request_provenance_receipt,
    )
    _require(record == rebuilt, "online program plan seal does not reproduce")
    return record
