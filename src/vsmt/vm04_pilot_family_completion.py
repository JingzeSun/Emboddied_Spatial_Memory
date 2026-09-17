"""Mechanical pilot family completion derivation (D-205).

The D-183 rule picks the formal house count from how many of the six pilot
families were *constructed*, and the contract forbids a caller from simply
asserting that number.  This module derives it instead: it consumes the sealed
route plans, the construction verdicts produced by
:func:`vsmt.vm04_observation_runner.assess_route_receipt`, and the SPLIT/MERGE
fresh-replay artifact receipts, and returns one boolean per pilot family plus an
auditable reason list for every family that did not complete.

It never reads CFO accuracy, history accuracy, sealed-catalog oracle recall,
private identity, teacher scores or any model output; the D-183 rule is
explicitly allowed to see construction completion only.  It also evaluates the
D-205 SPLIT/MERGE pilot yield floor, which can demote an atom out of the
confirmatory set but can never change geometry, thresholds or house counts.
"""

from __future__ import annotations

import hashlib
from typing import Any, Mapping, Sequence

from cpmt.hashing import canonical_json, clone_json

from vsmt.vm04_observation_runner import (
    ObservationConstructionError,
    PROGRAMS,
    PILOT_COMPLETION_SCHEMA,
    seal_formal_selection,
    validate_approved_contract,
    validate_source_pool_manifest,
)

VERDICT_SCHEMA = "vsmt-vm04-observation-construction-verdict-v1"
ARTIFACT_SCHEMA = "vsmt-vm04-split-merge-artifact-receipt-v1"
FORBIDDEN_EPISODE_FIELDS = frozenset({
    "constructed", "family_complete", "completion", "cfo_accuracy",
    "history_accuracy", "oracle_recall", "private_identity", "teacher_score",
    "reference_program",
})
ARTIFACT_PROGRAMS = ("SPLIT", "MERGE")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ObservationConstructionError(message)


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _validate_artifact_receipt(
    receipt: Mapping[str, Any], *, program: str, repeat_count: int,
) -> dict[str, Any]:
    """Require every registered fresh replay to report a public realization."""

    _require(type(receipt) is dict and
             receipt.get("schema_version") == ARTIFACT_SCHEMA,
             "wrong SPLIT/MERGE artifact receipt schema")
    _require(receipt.get("program") == program,
             "artifact receipt program does not match the registered program")
    replays = receipt.get("fresh_replays")
    _require(type(replays) is list and len(replays) == repeat_count,
             f"{program} artifact receipt must contain exactly "
             f"{repeat_count} fresh replays")
    realized = []
    for index, replay in enumerate(replays):
        _require(type(replay) is dict and set(replay) == {
            "replay_index", "far_proposal_count_covering_target",
            "near_proposal_count_covering_target", "registered_transition_realized",
        }, f"{program} fresh replay row is malformed")
        _require(replay["replay_index"] == index,
                 f"{program} fresh replay indices must be canonical")
        for field in ("far_proposal_count_covering_target",
                      "near_proposal_count_covering_target"):
            _require(type(replay[field]) is int and replay[field] >= 0,
                     f"{program} {field} must be a nonnegative integer")
        _require(type(replay["registered_transition_realized"]) is bool,
                 f"{program} realization flag must be boolean")
        expected_far, expected_near = (1, 2) if program == "SPLIT" else (2, 1)
        derived = (replay["far_proposal_count_covering_target"] == expected_far and
                   replay["near_proposal_count_covering_target"] == expected_near)
        _require(derived == replay["registered_transition_realized"],
                 f"{program} realization flag does not match its public "
                 f"proposal counts")
        realized.append(derived)
    return {
        "program": program,
        "all_replays_realized": all(realized),
        "realized_replay_count": sum(realized),
        "registered_replay_count": repeat_count,
    }


def derive_pilot_family_completion(
    source_pool: Mapping[str, Any],
    pilot_families: Sequence[Mapping[str, Any]],
    *,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Derive six completion booleans from sealed receipts, never from a caller."""

    approved = validate_approved_contract(contract)
    pool = validate_source_pool_manifest(source_pool)
    construction = approved["deterministic_SPLIT_MERGE_construction"]
    repeat_count = construction["fresh_replay_repeat_count"]
    _require(type(repeat_count) is int and repeat_count >= 2,
             "fresh replay repeat count is not frozen")
    floor = construction["pilot_artifact_yield_floor"]

    _require(type(pilot_families) is list and len(pilot_families) == 6,
             "pilot completion needs exactly six families")

    rows = []
    for index, family in enumerate(pilot_families):
        _require(type(family) is dict and set(family) == {
            "pool_index", "registered_episodes", "artifact_receipts",
        }, "pilot family row has unexpected fields")
        _require(family["pool_index"] == index,
                 "pilot families must be ordered by pool index zero to five")
        expected_house = pool["houses"][index]
        _require(expected_house["cohort"] == "pilot",
                 "pilot family must map to a sealed pilot cohort row")

        episodes = family["registered_episodes"]
        _require(type(episodes) is list and episodes,
                 "a pilot family needs at least one registered episode")
        seen_plans = set()
        reasons: list[str] = []
        for episode in episodes:
            _require(type(episode) is dict and set(episode) == {
                "program", "route_plan_sha256", "construction_verdict",
            }, "registered episode row has unexpected fields")
            _require(not (FORBIDDEN_EPISODE_FIELDS & set(episode)),
                     "registered episode must not carry a completion or model field")
            program = episode["program"]
            _require(program in PROGRAMS, "unregistered program in pilot family")
            verdict = episode["construction_verdict"]
            _require(type(verdict) is dict and
                     verdict.get("schema_version") == VERDICT_SCHEMA,
                     "episode needs a construction verdict from assess_route_receipt")
            _require(verdict.get("route_plan_sha256") == episode["route_plan_sha256"],
                     "construction verdict does not bind the sealed route plan")
            _require(verdict.get("failed_route_replacement_allowed") is False,
                     "construction verdict must retain the no-replacement rule")
            _require(type(verdict.get("constructed")) is bool,
                     "construction verdict must report a boolean")
            plan_digest = episode["route_plan_sha256"]
            _require(plan_digest not in seen_plans,
                     "a route plan may appear at most once per pilot family")
            seen_plans.add(plan_digest)
            if not verdict["constructed"]:
                for reason in verdict.get("failure_reasons") or ["unspecified"]:
                    reasons.append(f"{program}:{reason}")

        receipts = family["artifact_receipts"]
        _require(type(receipts) is dict and
                 set(receipts) <= set(ARTIFACT_PROGRAMS),
                 "artifact receipts may only cover SPLIT and MERGE")
        registered_artifact_programs = {
            episode["program"] for episode in episodes
            if episode["program"] in ARTIFACT_PROGRAMS
        }
        _require(set(receipts) == registered_artifact_programs,
                 "every registered SPLIT/MERGE episode needs one artifact receipt "
                 "and no unregistered artifact receipt is allowed")
        artifacts = {}
        for program in sorted(receipts):
            summary = _validate_artifact_receipt(
                receipts[program], program=program, repeat_count=repeat_count,
            )
            artifacts[program] = summary
            if not summary["all_replays_realized"]:
                reasons.append(f"{program}:fresh_replay_transition_not_realized")

        rows.append({
            "pool_index": index,
            "source_house_commitment": expected_house["source_house_commitment"],
            "registered_episode_count": len(episodes),
            "constructed_episode_count": sum(
                1 for episode in episodes
                if episode["construction_verdict"]["constructed"]
            ),
            "artifact_summaries": artifacts,
            "family_complete": not reasons,
            "incompletion_reasons": sorted(set(reasons)),
        })

    completed = sum(1 for row in rows if row["family_complete"])
    yield_floor = _evaluate_artifact_yield_floor(rows, floor=floor)
    record = {
        "schema_version": PILOT_COMPLETION_SCHEMA,
        "source_pool_manifest_sha256": pool["manifest_sha256"],
        "contract_version": approved.get("version"),
        "fresh_replay_repeat_count": repeat_count,
        "families": rows,
        "pilot_completed_families": completed,
        "derived_from": "sealed_route_receipts_and_construction_verdicts_only",
        "caller_supplied_completion_boolean_used": False,
        "model_or_identifiability_inputs_used": False,
        "split_merge_pilot_yield_floor": yield_floor,
    }
    record["completion_sha256"] = _sha(record)
    return record


def _evaluate_artifact_yield_floor(
    rows: Sequence[Mapping[str, Any]], *, floor: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply the D-205 pilot floor that can only demote, never repair."""

    result: dict[str, Any] = {
        "measured_on": "six_pilot_families_only",
        "thresholds_may_change_after_seeing_pilot_results": False,
        "programs": {},
        "demoted_from_confirmatory_set": [],
    }
    thresholds = {
        "SPLIT": floor[
            "minimum_pilot_families_with_all_SPLIT_fresh_replays_realized"],
        "MERGE": floor[
            "minimum_pilot_families_with_all_MERGE_fresh_replays_realized"],
    }
    for program in ARTIFACT_PROGRAMS:
        registered = [
            row for row in rows if program in row["artifact_summaries"]
        ]
        realized = [
            row for row in registered
            if row["artifact_summaries"][program]["all_replays_realized"]
        ]
        minimum = thresholds[program]
        meets = len(realized) >= minimum
        result["programs"][program] = {
            "registered_pilot_families": len(registered),
            "families_with_all_replays_realized": len(realized),
            "frozen_minimum": minimum,
            "meets_floor": meets,
        }
        if not meets:
            result["demoted_from_confirmatory_set"].append(program)
    result["demoted_from_confirmatory_set"].sort()
    result["remaining_confirmatory_atoms"] = sorted(
        {"SPLIT", "MERGE", "entity_RETRACT"} -
        set(result["demoted_from_confirmatory_set"])
    )
    result["demotion_is_recorded_before_formal_generation_not_repaired"] = True
    return result


def validate_pilot_family_completion(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Re-check a completion record and its digest without recomputing verdicts."""

    _require(type(record) is dict and
             record.get("schema_version") == PILOT_COMPLETION_SCHEMA,
             "wrong pilot family completion schema")
    _require(record.get("caller_supplied_completion_boolean_used") is False and
             record.get("model_or_identifiability_inputs_used") is False,
             "pilot completion record claims a forbidden input")
    families = record.get("families")
    _require(type(families) is list and len(families) == 6,
             "pilot completion record must cover six families")
    _require([row.get("pool_index") for row in families] == list(range(6)),
             "pilot completion families must be canonically ordered")
    _require(record.get("pilot_completed_families") ==
             sum(1 for row in families if row.get("family_complete") is True),
             "pilot completed count does not match the per-family booleans")
    for row in families:
        complete = row.get("family_complete")
        _require(type(complete) is bool, "family_complete must be boolean")
        _require(complete == (not row.get("incompletion_reasons")),
                 "family_complete disagrees with its retained reasons")
    payload = clone_json(dict(record))
    payload.pop("completion_sha256", None)
    _require(record.get("completion_sha256") == _sha(payload),
             "pilot completion digest mismatch")
    return clone_json(dict(record))


def seal_formal_selection_from_pilot(
    source_pool: Mapping[str, Any], completion_record: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply the 6->48/64/stop rule to a mechanically derived completion record."""

    record = validate_pilot_family_completion(completion_record)
    pool = validate_source_pool_manifest(source_pool)
    _require(record["source_pool_manifest_sha256"] == pool["manifest_sha256"],
             "completion record does not bind this sealed source pool")
    selection = seal_formal_selection(
        pool,
        pilot_completion_by_pool_index={
            row["pool_index"]: row["family_complete"] for row in record["families"]
        },
    )
    selection["pilot_completion_sha256"] = record["completion_sha256"]
    selection["pilot_inputs_used"] = "mechanically_derived_construction_completion"
    selection["split_merge_demotions_recorded_before_formal_generation"] = list(
        record["split_merge_pilot_yield_floor"]["demoted_from_confirmatory_set"]
    )
    selection["manifest_sha256"] = _sha(
        {key: value for key, value in selection.items()
         if key != "manifest_sha256"}
    )
    return selection
