"""Deterministic QUARANTINE and pending-memory contracts.

Pending memory is deliberately separate from the persistent world graph.
It preserves weak, retrievable evidence without asserting a world identity
or fact. Numeric commit gates are supplied by the caller and must later be
selected on train/validation data, never on test cases.
"""

from __future__ import annotations

from copy import deepcopy
from math import isclose, isfinite
from typing import Any, Iterable, Mapping

from .errors import ContractError, InvariantViolation, PreconditionError


SCHEMA_VERSION = "cpmt-0.2"
PENDING_STATES = {
    "active_pending",
    "archived_unresolved",
    "consumed",
}
SEARCHABLE_STATES = {"active_pending", "archived_unresolved"}


def _validate_probability(value: Any, name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
        or not 0 <= value <= 1
    ):
        raise ContractError(f"{name} must be a finite number in [0, 1]")
    return float(value)


def decide_commit(
    candidate_posteriors: Mapping[str, float],
    *,
    decision_id: str,
    at: int,
    commit_probability: float,
    margin_threshold: float,
) -> dict[str, Any]:
    """Choose COMMIT or QUARANTINE using caller-supplied fixed gates."""

    if not decision_id:
        raise ContractError("decision_id must be non-empty")
    if isinstance(at, bool) or not isinstance(at, int) or at < 0:
        raise ContractError("decision time must be a non-negative integer")
    if not candidate_posteriors:
        raise ContractError("candidate_posteriors cannot be empty")

    normalized: dict[str, float] = {}
    for candidate_id, value in candidate_posteriors.items():
        if not candidate_id:
            raise ContractError("candidate IDs must be non-empty")
        normalized[candidate_id] = _validate_probability(
            value,
            f"posterior[{candidate_id!r}]",
        )
    if not isclose(
        sum(normalized.values()),
        1.0,
        rel_tol=0,
        abs_tol=1e-6,
    ):
        raise ContractError("candidate posteriors must sum to one")

    commit_gate = _validate_probability(
        commit_probability,
        "commit_probability",
    )
    margin_gate = _validate_probability(
        margin_threshold,
        "margin_threshold",
    )
    ranked = sorted(
        normalized.items(),
        key=lambda item: (-item[1], item[0]),
    )
    top_candidate_id, top_probability = ranked[0]
    runner_up_probability = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = round(top_probability - runner_up_probability, 12)

    reasons: list[str] = []
    if top_probability < commit_gate:
        reasons.append("top_probability_below_gate")
    if margin < margin_gate:
        reasons.append("top_two_margin_below_gate")
    action = "QUARANTINE" if reasons else "COMMIT"

    return {
        "schema_version": SCHEMA_VERSION,
        "decision_id": decision_id,
        "at": at,
        "candidate_posteriors": dict(
            sorted(normalized.items())
        ),
        "commit_probability": commit_gate,
        "margin_threshold": margin_gate,
        "action": action,
        "selected_candidate_id": (
            top_candidate_id if action == "COMMIT" else None
        ),
        "top_candidate_id": top_candidate_id,
        "top_probability": top_probability,
        "runner_up_probability": runner_up_probability,
        "margin": margin,
        "reasons": reasons,
    }


def validate_commit_decision(decision: Mapping[str, Any]) -> None:
    """Recompute a serialized decision instead of trusting its action."""

    required = {
        "schema_version",
        "decision_id",
        "at",
        "candidate_posteriors",
        "commit_probability",
        "margin_threshold",
        "action",
        "selected_candidate_id",
        "top_candidate_id",
        "top_probability",
        "runner_up_probability",
        "margin",
        "reasons",
    }
    if set(decision) != required:
        raise ContractError(
            "commit decision fields do not match the cpmt-0.2 contract"
        )
    if decision["schema_version"] != SCHEMA_VERSION:
        raise ContractError("unsupported commit decision schema")
    recomputed = decide_commit(
        decision["candidate_posteriors"],
        decision_id=decision["decision_id"],
        at=decision["at"],
        commit_probability=decision["commit_probability"],
        margin_threshold=decision["margin_threshold"],
    )
    if dict(decision) != recomputed:
        raise ContractError(
            "serialized commit decision does not match recomputation"
        )


def create_pending_store(store_id: str) -> dict[str, Any]:
    """Create an empty pending-memory store."""

    if not store_id:
        raise ContractError("store_id must be non-empty")
    return {
        "schema_version": SCHEMA_VERSION,
        "store_id": store_id,
        "store_version": 0,
        "records": [],
    }


def _record(
    store: dict[str, Any],
    pending_id: str,
) -> dict[str, Any]:
    matches = [
        record
        for record in store["records"]
        if record["pending_id"] == pending_id
    ]
    if len(matches) != 1:
        raise PreconditionError(
            f"expected pending_id {pending_id!r} exactly once, "
            f"found {len(matches)}"
        )
    return matches[0]


def validate_pending_store(store: dict[str, Any]) -> None:
    """Validate lifecycle, uniqueness and evidence-weight invariants."""

    required = {
        "schema_version",
        "store_id",
        "store_version",
        "records",
    }
    missing = required - store.keys()
    if missing:
        raise InvariantViolation(
            f"pending store missing keys: {sorted(missing)}"
        )
    if store["schema_version"] != SCHEMA_VERSION:
        raise InvariantViolation("unsupported pending schema version")
    if not isinstance(store["store_id"], str) or not store["store_id"]:
        raise InvariantViolation("pending store_id must be non-empty")
    if (
        isinstance(store["store_version"], bool)
        or not isinstance(store["store_version"], int)
        or store["store_version"] < 0
    ):
        raise InvariantViolation(
            "pending store_version must be a non-negative integer"
        )
    if not isinstance(store["records"], list):
        raise InvariantViolation("pending records must be a list")

    pending_ids = [
        record.get("pending_id") for record in store["records"]
    ]
    if (
        any(not isinstance(value, str) or not value for value in pending_ids)
        or len(pending_ids) != len(set(pending_ids))
    ):
        raise InvariantViolation(
            "pending IDs must be unique non-empty strings"
        )

    evidence_ids: list[str] = []
    for record in store["records"]:
        _validate_pending_record(record)
        evidence_ids.extend(
            item["evidence_id"] for item in record["evidence"]
        )
    if len(evidence_ids) != len(set(evidence_ids)):
        raise InvariantViolation(
            "an evidence ID may belong to only one pending record"
        )


def _validate_pending_record(record: dict[str, Any]) -> None:
    required = {
        "pending_id",
        "status",
        "created_at",
        "updated_at",
        "evidence",
        "retrieval",
        "decision_history",
        "relevant_opportunity_ids",
        "opportunity_cycle",
        "opportunity_history",
        "archive_history",
        "reactivation_count",
        "effective_support",
        "consumed_at",
        "consumed_by_transaction",
        "provenance",
    }
    missing = required - record.keys()
    if missing:
        raise InvariantViolation(
            f"pending record missing keys: {sorted(missing)}"
        )
    if record["status"] not in PENDING_STATES:
        raise InvariantViolation("unknown pending lifecycle state")
    if (
        record["updated_at"] < record["created_at"]
        or not record["evidence"]
        or not record["decision_history"]
        or not record["provenance"]
    ):
        raise InvariantViolation(
            "pending record has invalid time or empty audit history"
        )
    opportunities = record["relevant_opportunity_ids"]
    if len(opportunities) != len(set(opportunities)):
        raise InvariantViolation(
            "relevant opportunity IDs must be unique"
        )
    history_ids = [
        event["opportunity_id"]
        for event in record["opportunity_history"]
    ]
    if len(history_ids) != len(set(history_ids)):
        raise InvariantViolation(
            "opportunity history IDs must be globally unique"
        )
    current_cycle = record["opportunity_cycle"]
    expected_current = [
        event["opportunity_id"]
        for event in record["opportunity_history"]
        if event["cycle"] == current_cycle
    ]
    if opportunities != expected_current:
        raise InvariantViolation(
            "current opportunity IDs do not match current cycle"
        )

    items = record["evidence"]
    item_ids = [item["evidence_id"] for item in items]
    if len(item_ids) != len(set(item_ids)):
        raise InvariantViolation(
            "pending evidence IDs must be unique"
        )
    for item in items:
        reliability = _validate_probability(
            item["reliability"],
            "evidence reliability",
        )
        independence = _validate_probability(
            item["independence_weight"],
            "evidence independence_weight",
        )
        decision_weight = _validate_probability(
            item["decision_weight"],
            "evidence decision_weight",
        )
        if not isclose(
            decision_weight,
            reliability * independence,
            rel_tol=0,
            abs_tol=1e-9,
        ):
            raise InvariantViolation(
                "decision_weight must equal reliability * independence"
            )
    expected_support = sum(
        item["decision_weight"] for item in items
    )
    if not isclose(
        record["effective_support"],
        expected_support,
        rel_tol=0,
        abs_tol=1e-9,
    ):
        raise InvariantViolation(
            "effective_support does not match evidence weights"
        )

    retrieval = record["retrieval"]
    for key in ("latent_refs", "spatial_refs", "semantic_hints"):
        values = retrieval.get(key)
        if (
            not isinstance(values, list)
            or len(values) != len(set(values))
        ):
            raise InvariantViolation(
                f"retrieval {key} must be a unique list"
            )

    if record["status"] == "consumed":
        if (
            record["consumed_at"] is None
            or not record["consumed_by_transaction"]
        ):
            raise InvariantViolation(
                "consumed pending record needs time and transaction"
            )
    elif (
        record["consumed_at"] is not None
        or record["consumed_by_transaction"] is not None
    ):
        raise InvariantViolation(
            "unconsumed pending record cannot name a consumer"
        )
    if (
        record["status"] == "archived_unresolved"
        and not record["archive_history"]
    ):
        raise InvariantViolation(
            "archived pending record needs archive history"
        )


def _append_unique(values: list[str], value: str | None) -> None:
    if value and value not in values:
        values.append(value)


def quarantine_evidence(
    store: dict[str, Any],
    *,
    pending_id: str,
    decision: Mapping[str, Any],
    evidence_event: Mapping[str, Any],
    latent_ref: str | None,
    spatial_ref: str | None,
    semantic_hints: Iterable[str] = (),
    provenance_ref: str,
) -> dict[str, Any]:
    """Append weak evidence without mutating any persistent-world object."""

    validate_pending_store(store)
    validate_commit_decision(decision)
    if decision["action"] != "QUARANTINE":
        raise PreconditionError(
            "only a QUARANTINE decision may write pending memory"
        )
    if not pending_id or not provenance_ref:
        raise ContractError(
            "pending_id and provenance_ref must be non-empty"
        )
    required_event = {
        "evidence_id",
        "time_index",
        "reliability",
    }
    missing = required_event - evidence_event.keys()
    if missing:
        raise ContractError(
            f"pending evidence missing keys: {sorted(missing)}"
        )
    reliability = _validate_probability(
        evidence_event["reliability"],
        "evidence reliability",
    )
    event_id = evidence_event["evidence_id"]
    if not isinstance(event_id, str) or not event_id:
        raise ContractError("evidence_id must be non-empty")
    if any(
        item["evidence_id"] == event_id
        for record in store["records"]
        for item in record["evidence"]
    ):
        raise PreconditionError(
            f"evidence {event_id!r} is already pending"
        )

    working = deepcopy(store)
    matches = [
        record
        for record in working["records"]
        if record["pending_id"] == pending_id
    ]
    at = decision["at"]
    if matches:
        record = matches[0]
        if record["status"] == "consumed":
            raise PreconditionError(
                "consumed pending record cannot accept evidence"
            )
        if record["status"] == "archived_unresolved":
            record["status"] = "active_pending"
            record["reactivation_count"] += 1
            record["opportunity_cycle"] += 1
            record["relevant_opportunity_ids"] = []
    else:
        record = {
            "pending_id": pending_id,
            "status": "active_pending",
            "created_at": at,
            "updated_at": at,
            "evidence": [],
            "retrieval": {
                "latent_refs": [],
                "spatial_refs": [],
                "semantic_hints": [],
            },
            "decision_history": [],
            "relevant_opportunity_ids": [],
            "opportunity_cycle": 0,
            "opportunity_history": [],
            "archive_history": [],
            "reactivation_count": 0,
            "effective_support": 0.0,
            "consumed_at": None,
            "consumed_by_transaction": None,
            "provenance": [provenance_ref],
        }
        working["records"].append(record)

    viewpoint_id = evidence_event.get("viewpoint_id")
    time_view_key = (evidence_event["time_index"], viewpoint_id)
    existing_keys = {
        (item["time_index"], item["viewpoint_id"])
        for item in record["evidence"]
    }
    independence_weight = (
        0.0 if time_view_key in existing_keys else 1.0
    )
    hints = sorted(set(semantic_hints))
    item = {
        "evidence_id": event_id,
        "time_index": evidence_event["time_index"],
        "viewpoint_id": viewpoint_id,
        "latent_ref": latent_ref,
        "spatial_ref": spatial_ref,
        "semantic_hints": hints,
        "reliability": reliability,
        "independence_weight": independence_weight,
        "decision_weight": reliability * independence_weight,
        "visibility": evidence_event.get("visibility"),
        "pose_valid": evidence_event.get("pose_valid"),
        "depth_valid": evidence_event.get("depth_valid"),
    }
    record["evidence"].append(item)
    record["effective_support"] += item["decision_weight"]
    record["decision_history"].append(deepcopy(dict(decision)))
    record["updated_at"] = max(record["updated_at"], at)
    _append_unique(record["retrieval"]["latent_refs"], latent_ref)
    if (
        evidence_event.get("pose_valid") is True
        and evidence_event.get("depth_valid") is True
    ):
        _append_unique(
            record["retrieval"]["spatial_refs"],
            spatial_ref,
        )
    for hint in hints:
        _append_unique(
            record["retrieval"]["semantic_hints"],
            hint,
        )
    _append_unique(record["provenance"], provenance_ref)

    working["store_version"] += 1
    validate_pending_store(working)
    return working


def register_relevant_opportunity(
    store: dict[str, Any],
    *,
    pending_id: str,
    opportunity_id: str,
    at: int,
    relevant: bool,
    can_disambiguate: bool,
    decision_still_unresolved: bool,
    opportunity_budget: int,
) -> dict[str, Any]:
    """Count only real chances to resolve a pending hypothesis."""

    validate_pending_store(store)
    if (
        isinstance(opportunity_budget, bool)
        or not isinstance(opportunity_budget, int)
        or opportunity_budget < 1
    ):
        raise ContractError(
            "opportunity_budget must be a positive integer"
        )
    if not relevant or not can_disambiguate:
        return deepcopy(store)
    if not opportunity_id:
        raise ContractError("opportunity_id must be non-empty")

    working = deepcopy(store)
    record = _record(working, pending_id)
    if record["status"] != "active_pending":
        raise PreconditionError(
            "only active_pending records count opportunities"
        )
    if any(
        event["opportunity_id"] == opportunity_id
        for event in record["opportunity_history"]
    ):
        raise PreconditionError(
            f"opportunity {opportunity_id!r} is already counted"
        )
    record["relevant_opportunity_ids"].append(opportunity_id)
    record["opportunity_history"].append(
        {
            "opportunity_id": opportunity_id,
            "at": at,
            "cycle": record["opportunity_cycle"],
        }
    )
    record["updated_at"] = max(record["updated_at"], at)
    if (
        decision_still_unresolved
        and len(record["relevant_opportunity_ids"])
        >= opportunity_budget
    ):
        record["status"] = "archived_unresolved"
        record["archive_history"].append(
            {
                "at": at,
                "cycle": record["opportunity_cycle"],
                "reason": "opportunity_budget_exhausted",
            }
        )
    working["store_version"] += 1
    validate_pending_store(working)
    return working


def retrieve_pending(
    store: dict[str, Any],
    *,
    latent_ref: str | None = None,
    spatial_ref: str | None = None,
    semantic_hints: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """Retrieve active or archived traces using auditable exact M0 keys."""

    validate_pending_store(store)
    hints = set(semantic_hints)
    if not latent_ref and not spatial_ref and not hints:
        raise ContractError("pending retrieval needs at least one key")

    results: list[dict[str, Any]] = []
    for record in store["records"]:
        if record["status"] not in SEARCHABLE_STATES:
            continue
        retrieval = record["retrieval"]
        score = 0.0
        if latent_ref and latent_ref in retrieval["latent_refs"]:
            score += 3.0
        if spatial_ref and spatial_ref in retrieval["spatial_refs"]:
            score += 2.0
        score += float(
            len(hints & set(retrieval["semantic_hints"]))
        )
        if score > 0:
            results.append(
                {
                    "pending_id": record["pending_id"],
                    "status": record["status"],
                    "match_score": score,
                    "effective_support": record[
                        "effective_support"
                    ],
                }
            )
    return sorted(
        results,
        key=lambda result: (
            -result["match_score"],
            result["pending_id"],
        ),
    )


def consume_pending(
    store: dict[str, Any],
    *,
    pending_id: str,
    transaction_program: Mapping[str, Any],
    at: int,
) -> dict[str, Any]:
    """Link every pending evidence item to its committing transaction."""

    validate_pending_store(store)
    transaction_id = transaction_program.get("transaction_id")
    if not transaction_id:
        raise ContractError(
            "consuming transaction needs transaction_id"
        )
    program_evidence = set(
        transaction_program.get("evidence_refs", [])
    )

    working = deepcopy(store)
    record = _record(working, pending_id)
    if record["status"] == "consumed":
        raise PreconditionError(
            "pending record has already been consumed"
        )
    pending_evidence = {
        item["evidence_id"] for item in record["evidence"]
    }
    missing = pending_evidence - program_evidence
    if missing:
        raise PreconditionError(
            "transaction does not cite all pending evidence: "
            f"{sorted(missing)}"
        )
    record["status"] = "consumed"
    record["consumed_at"] = at
    record["consumed_by_transaction"] = transaction_id
    record["updated_at"] = max(record["updated_at"], at)
    _append_unique(record["provenance"], transaction_id)
    working["store_version"] += 1
    validate_pending_store(working)
    return working
