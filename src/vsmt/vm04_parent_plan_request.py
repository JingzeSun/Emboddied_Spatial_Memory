"""Public-only parent-stage derivation of VM-04 online plan requests.

The parent core receives an already sealed public route, a pre-registered
selector specification, and the causal memory immediately before the terminal
observation.  It has no filesystem or raw-frame input and deterministically
resolves stable public node IDs to their current open versions.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping

from cpmt.executor import validate_graph
from cpmt.hashing import canonical_json, clone_json

from .vm04_online_plan_seal import make_online_program_plan_request


SPEC_SCHEMA = "vsmt-vm04-parent-program-request-spec-v1"
RECEIPT_SCHEMA = "vsmt-vm04-parent-program-request-provenance-receipt-v1"
RECEIPT_SCHEMA_V2 = "vsmt-vm04-parent-program-request-provenance-receipt-v2"
SELECTOR_TEMPORAL_SCHEMA = "vsmt-vm04-parent-selector-temporal-receipt-v1"
PUBLIC_ROUTE_SCHEMA = "vsmt-vm04-public-observation-route-v1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")

SELECTOR_KEYS = {
    "NOOP": {"current_observation_rule_sha256"},
    "BIND": {
        "open_node_id", "prior_evidence_sha256",
        "current_region_selection_rule_sha256",
    },
    "BIRTH": {"absence_scope_sha256"},
    "REACTIVATE": {"dormant_node_id", "prior_evidence_sha256"},
    "RELINK": {"entity_node_id", "old_place_node_id", "new_place_public_ref"},
    "RETRACT": {"entity_node_id", "prior_evidence_sha256", "absence_rule_sha256"},
    "SPLIT": {"undersegmented_node_id", "artifact_plan_sha256"},
    "MERGE": {"first_node_id", "second_node_id", "artifact_plan_sha256"},
    "REPLACE": {"old_entity_node_id", "new_identity_absence_scope_sha256"},
}


class ParentPlanRequestError(ValueError):
    """The parent request specification or public derivation is invalid."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ParentPlanRequestError(message)


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _payload_sha(value: Mapping[str, Any], seal: str) -> str:
    payload = clone_json(dict(value))
    payload.pop(seal, None)
    return _sha(payload)


def _hex(value: Any, name: str) -> str:
    _require(type(value) is str and HEX64.fullmatch(value) is not None,
             f"{name} must be a lowercase SHA-256")
    return value


def _token(value: Any, name: str) -> str:
    _require(type(value) is str and value and
             not any(character.isspace() for character in value),
             f"{name} must be a nonempty token")
    return value


def _validate_public_route(route: Mapping[str, Any]) -> dict[str, Any]:
    expected = {
        "schema_version", "consumer_scope", "episode_id", "branch_type",
        "visibility_subject_kind", "visibility_subject_public_ref",
        "visibility_subject_seal_sha256", "visibility_builder_config_sha256",
        "world_pose_excluded", "family_layer",
        "registered_actions", "phase_observation_indices",
        "intervention_after_observation_index",
        "terminal_reobservation_indices", "private_route_plan_sha256",
        "public_route_sha256",
    }
    _require(type(route) is dict and set(route) == expected,
             "parent public route has unexpected fields")
    record = clone_json(dict(route))
    _require(record["schema_version"] == PUBLIC_ROUTE_SCHEMA and
             record["consumer_scope"] ==
             "construction_provenance_only_not_adapter_input",
             "parent public route schema or scope changed")
    _hex(record["public_route_sha256"], "public_route_sha256")
    _hex(record["private_route_plan_sha256"], "private_route_plan_sha256")
    _hex(record["visibility_subject_seal_sha256"],
         "visibility_subject_seal_sha256")
    terminal = record["terminal_reobservation_indices"]
    _require(type(terminal) is list and terminal and
             all(type(index) is int and index >= 0 for index in terminal),
             "parent public route terminal indices are invalid")
    _require(record["public_route_sha256"] ==
             _payload_sha(record, "public_route_sha256"),
             "parent public route digest mismatch")
    return record


def make_parent_program_request_spec(
    *, public_route: Mapping[str, Any], family_id: str, program: str,
    selector_inputs: Mapping[str, Any], matcher_config_sha256: str,
) -> dict[str, Any]:
    """Pre-register public selectors without accepting version IDs or raw data."""

    route = _validate_public_route(public_route)
    _require(program in SELECTOR_KEYS, "parent program is not registered")
    expected_subject = "reveal_locus" if program == "BIRTH" else (
        "old_track_and_new_reveal_locus" if program == "REPLACE" else
        "target_track"
    )
    _require(route["visibility_subject_kind"] == expected_subject,
             "parent program and public route subject differ")
    selectors = clone_json(dict(selector_inputs))
    _require(set(selectors) == SELECTOR_KEYS[program],
             "parent selector inputs do not match the registered program")
    for name, value in selectors.items():
        if name.endswith("sha256"):
            _hex(value, name)
        else:
            _token(value, name)
    spec = {
        "schema_version": SPEC_SCHEMA,
        "episode_id": _token(route["episode_id"], "episode_id"),
        "family_id": _token(family_id, "family_id"),
        "program": program,
        "public_route_sha256": route["public_route_sha256"],
        "route_plan_sha256": route["private_route_plan_sha256"],
        "terminal_observation_index": route["terminal_reobservation_indices"][-1],
        "visibility_subject_seal_sha256":
            route["visibility_subject_seal_sha256"],
        "matcher_config_sha256": _hex(
            matcher_config_sha256, "matcher_config_sha256"
        ),
        "selector_inputs": selectors,
        "caller_supplied_version_ids_allowed": False,
        "terminal_or_future_observation_used": False,
        "private_identity_teacher_or_reference_used": False,
    }
    spec["spec_sha256"] = _sha(spec)
    return spec


def validate_parent_program_request_spec(
    spec: Mapping[str, Any], *, public_route: Mapping[str, Any],
) -> dict[str, Any]:
    expected = {
        "schema_version", "episode_id", "family_id", "program",
        "public_route_sha256", "route_plan_sha256",
        "terminal_observation_index", "visibility_subject_seal_sha256",
        "matcher_config_sha256", "selector_inputs",
        "caller_supplied_version_ids_allowed",
        "terminal_or_future_observation_used",
        "private_identity_teacher_or_reference_used", "spec_sha256",
    }
    _require(type(spec) is dict and set(spec) == expected,
             "parent request spec has unexpected fields")
    record = clone_json(dict(spec))
    _require(record["schema_version"] == SPEC_SCHEMA and
             record["caller_supplied_version_ids_allowed"] is False and
             record["terminal_or_future_observation_used"] is False and
             record["private_identity_teacher_or_reference_used"] is False,
             "parent request spec used a restricted input")
    rebuilt = make_parent_program_request_spec(
        public_route=public_route, family_id=record["family_id"],
        program=record["program"], selector_inputs=record["selector_inputs"],
        matcher_config_sha256=record["matcher_config_sha256"],
    )
    _require(record == rebuilt, "parent request spec does not reproduce")
    return record


def seal_parent_selector_spec_before_raw_capture(
    *, spec: Mapping[str, Any], public_route: Mapping[str, Any],
    parent_stage_code_sha256: str,
) -> dict[str, Any]:
    """Seal selector bytes before the trusted raw writer accepts frame zero."""

    route = _validate_public_route(public_route)
    registered = validate_parent_program_request_spec(spec, public_route=route)
    receipt = {
        "schema_version": SELECTOR_TEMPORAL_SCHEMA,
        "episode_id": registered["episode_id"],
        "program": registered["program"],
        "spec_sha256": registered["spec_sha256"],
        "public_route_sha256": route["public_route_sha256"],
        "route_plan_sha256": route["private_route_plan_sha256"],
        "parent_stage_code_sha256": _hex(
            parent_stage_code_sha256, "parent_stage_code_sha256"
        ),
        "sealed_before_raw_observation_index": 0,
        "public_raw_frame_count_before_seal": 0,
        "private_raw_frame_count_before_seal": 0,
        "terminal_public_or_private_frame_opened": False,
        "future_observation_opened": False,
        "selector_spec_pre_terminal_registration_established": True,
    }
    receipt["receipt_sha256"] = _sha(receipt)
    return receipt


def validate_parent_selector_temporal_receipt(
    receipt: Mapping[str, Any], *, spec: Mapping[str, Any],
    public_route: Mapping[str, Any], parent_stage_code_sha256: str,
) -> dict[str, Any]:
    rebuilt = seal_parent_selector_spec_before_raw_capture(
        spec=spec, public_route=public_route,
        parent_stage_code_sha256=parent_stage_code_sha256,
    )
    _require(clone_json(dict(receipt)) == rebuilt,
             "parent selector temporal receipt does not reproduce")
    return rebuilt


def _open_node(memory: Mapping[str, Any], node_id: str, name: str) -> Mapping[str, Any]:
    rows = [row for row in memory["nodes"]
            if row["node_id"] == node_id and row["valid_to"] is None]
    _require(len(rows) == 1, f"{name} must resolve to exactly one open public node")
    return rows[0]


def _derive_refs(
    program: str, selectors: Mapping[str, Any], route: Mapping[str, Any],
    memory: Mapping[str, Any],
) -> dict[str, Any]:
    if program == "NOOP":
        return {"stable_public_memory_sha256": memory["graph_hash"], **selectors}
    if program == "BIND":
        row = _open_node(memory, selectors["open_node_id"], "open_node_id")
        return {"open_node_version_id": row["node_version_id"],
                "prior_evidence_sha256": selectors["prior_evidence_sha256"],
                "current_region_selection_rule_sha256":
                    selectors["current_region_selection_rule_sha256"]}
    if program == "BIRTH":
        return {"reveal_locus_public_ref":
                route["visibility_subject_public_ref"], **selectors}
    if program == "REACTIVATE":
        row = _open_node(memory, selectors["dormant_node_id"], "dormant_node_id")
        _require(row["lifecycle"] == "dormant",
                 "REACTIVATE selector must resolve a dormant public node")
        return {"dormant_node_version_id": row["node_version_id"],
                "prior_evidence_sha256": selectors["prior_evidence_sha256"]}
    if program == "RELINK":
        entity = _open_node(memory, selectors["entity_node_id"], "entity_node_id")
        place = _open_node(memory, selectors["old_place_node_id"], "old_place_node_id")
        _require(entity["node_type"] == "entity" and
                 place["node_type"] == "place",
                 "RELINK selectors must resolve an entity and a place")
        edges = [row for row in memory["edges"] if row["valid_to"] is None and
                 row["relation"] == "located_at" and
                 row["source"] == entity["node_id"] and
                 row["target"] == place["node_id"]]
        _require(len(edges) == 1,
                 "RELINK selector must resolve one open public located_at edge")
        return {"open_entity_node_version_id": entity["node_version_id"],
                "old_located_at_edge_version_id": edges[0]["edge_version_id"],
                "old_place_node_version_id": place["node_version_id"],
                "new_place_public_ref": selectors["new_place_public_ref"]}
    if program == "RETRACT":
        row = _open_node(memory, selectors["entity_node_id"], "entity_node_id")
        _require(row["node_type"] == "entity",
                 "parent RETRACT currently supports public entity nodes only")
        return {"open_entity_or_edge_version_id": row["node_version_id"],
                "prior_evidence_sha256": selectors["prior_evidence_sha256"],
                "absence_rule_sha256": selectors["absence_rule_sha256"]}
    if program == "SPLIT":
        row = _open_node(memory, selectors["undersegmented_node_id"],
                         "undersegmented_node_id")
        _require(row["node_type"] == "entity",
                 "SPLIT selector must resolve a public entity")
        return {"undersegmented_prior_node_version_id": row["node_version_id"],
                "artifact_plan_sha256": selectors["artifact_plan_sha256"]}
    if program == "MERGE":
        first = _open_node(memory, selectors["first_node_id"], "first_node_id")
        second = _open_node(memory, selectors["second_node_id"], "second_node_id")
        _require(first["node_type"] == second["node_type"] == "entity" and
                 first["node_id"] != second["node_id"],
                 "MERGE selectors must name distinct public entities")
        return {"first_prior_node_version_id": first["node_version_id"],
                "second_prior_node_version_id": second["node_version_id"],
                "artifact_plan_sha256": selectors["artifact_plan_sha256"]}
    row = _open_node(memory, selectors["old_entity_node_id"], "old_entity_node_id")
    _require(row["node_type"] == "entity",
             "REPLACE selector must resolve a public entity")
    return {"open_old_entity_node_version_id": row["node_version_id"],
            "new_reveal_locus_public_ref": route["visibility_subject_public_ref"],
            "new_identity_absence_scope_sha256":
                selectors["new_identity_absence_scope_sha256"]}


def derive_parent_online_program_plan_request(
    *, spec: Mapping[str, Any], public_route: Mapping[str, Any],
    prior_memory: Mapping[str, Any], last_completed_observation_index: int,
    parent_stage_code_sha256: str,
    selector_temporal_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Derive exact version refs without accepting an episode path or raw frame."""

    route = _validate_public_route(public_route)
    registered = validate_parent_program_request_spec(spec, public_route=route)
    memory = clone_json(dict(prior_memory))
    validate_graph(memory, verify_hash=True)
    _hex(parent_stage_code_sha256, "parent_stage_code_sha256")
    terminal = registered["terminal_observation_index"]
    _require(last_completed_observation_index == terminal - 1,
             "parent request derivation is not immediately before terminal")
    refs = _derive_refs(
        registered["program"], registered["selector_inputs"], route, memory,
    )
    request = make_online_program_plan_request(
        episode_id=registered["episode_id"], family_id=registered["family_id"],
        program=registered["program"],
        route_plan_sha256=registered["route_plan_sha256"],
        terminal_observation_index=terminal, precondition_refs=refs,
        visibility_subject_seal_sha256=
            registered["visibility_subject_seal_sha256"],
        matcher_config_sha256=registered["matcher_config_sha256"],
    )
    selector_receipt = None
    if selector_temporal_receipt is not None:
        selector_receipt = validate_parent_selector_temporal_receipt(
            selector_temporal_receipt, spec=registered, public_route=route,
            parent_stage_code_sha256=parent_stage_code_sha256,
        )
    receipt = {
        "schema_version": (
            RECEIPT_SCHEMA_V2 if selector_receipt is not None else RECEIPT_SCHEMA
        ),
        "episode_id": registered["episode_id"],
        "program": registered["program"],
        "spec_sha256": registered["spec_sha256"],
        "public_route_sha256": registered["public_route_sha256"],
        "route_plan_sha256": registered["route_plan_sha256"],
        "prior_memory_sha256": memory["graph_hash"],
        "request_sha256": request["request_sha256"],
        "parent_stage_code_sha256": parent_stage_code_sha256,
        "last_completed_observation_index": last_completed_observation_index,
        "sealed_before_observation_index": terminal,
        "precondition_refs_derived_deterministically_from_public_memory": True,
        "caller_supplied_precondition_refs_used": False,
        "episode_root_or_raw_path_argument_available": False,
        "terminal_public_or_private_frame_opened": False,
        "future_observation_opened": False,
        "teacher_reference_or_private_identity_used": False,
        "request_provenance_established_by_parent_core": True,
        "selector_spec_pre_terminal_registration_established":
            selector_receipt is not None,
        "consumed_by_D202_temporal_receipt": False,
        "clears_D201_temporal_seal_pending": False,
    }
    if selector_receipt is not None:
        receipt["selector_temporal_receipt_sha256"] = selector_receipt[
            "receipt_sha256"
        ]
    receipt["receipt_sha256"] = _sha(receipt)
    return {"online_request": request, "provenance_receipt": receipt}


def validate_parent_online_program_plan_request(
    bundle: Mapping[str, Any], *, spec: Mapping[str, Any],
    public_route: Mapping[str, Any], prior_memory: Mapping[str, Any],
    parent_stage_code_sha256: str,
    selector_temporal_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    _require(type(bundle) is dict and
             set(bundle) == {"online_request", "provenance_receipt"},
             "parent request bundle has unexpected fields")
    receipt = bundle["provenance_receipt"]
    expected_schema = (
        RECEIPT_SCHEMA_V2 if selector_temporal_receipt is not None else RECEIPT_SCHEMA
    )
    _require(type(receipt) is dict and receipt.get("schema_version") == expected_schema and
             receipt.get("receipt_sha256") == _payload_sha(receipt, "receipt_sha256"),
             "parent request provenance receipt is invalid")
    rebuilt = derive_parent_online_program_plan_request(
        spec=spec, public_route=public_route, prior_memory=prior_memory,
        last_completed_observation_index=receipt["last_completed_observation_index"],
        parent_stage_code_sha256=parent_stage_code_sha256,
        selector_temporal_receipt=selector_temporal_receipt,
    )
    _require(clone_json(dict(bundle)) == rebuilt,
             "parent request provenance bundle does not reproduce")
    return rebuilt
