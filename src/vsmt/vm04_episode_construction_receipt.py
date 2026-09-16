"""Append-only episode evidence joining VM-04 materializer and matcher receipts.

This receipt records whether an already materialized episode satisfies the
public construction matcher.  It does not assign semantic identity truth and
does not turn a failed matcher verdict into a successful family sample.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping, Sequence

from cpmt.hashing import canonical_json, clone_json


SCHEMA = "vsmt-vm04-episode-construction-receipt-v1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
FILE_DIGEST_KEYS = {
    "materializer_receipt_file_sha256",
    "causal_prior_receipt_file_sha256",
    "current_public_packet_file_sha256",
    "construction_plan_file_sha256",
    "matcher_config_file_sha256",
    "matcher_prior_memory_file_sha256",
    "program_matcher_receipt_file_sha256",
}


class EpisodeConstructionReceiptError(ValueError):
    """An episode construction receipt is incomplete or inconsistent."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EpisodeConstructionReceiptError(message)


def _hex64(value: Any, name: str) -> str:
    _require(type(value) is str and HEX64.fullmatch(value) is not None,
             f"{name} must be a lowercase SHA-256")
    return value


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def make_episode_construction_receipt(
    *, episode_id: str, program: str, prior_cutoff_observation_index: int,
    terminal_observation_index: int,
    materializer_receipt_sha256: str, program_matcher_receipt_sha256: str,
    file_digests: Mapping[str, str],
    split_merge_artifact_receipt_file_sha256: str | None,
    program_public_match_satisfied: bool,
    construction_failure_reasons: Sequence[str],
) -> dict[str, Any]:
    """Seal exact audit files and derive construction status from the matcher."""

    _require(type(episode_id) is str and episode_id,
             "episode_id must be nonempty")
    _require(program in {
        "NOOP", "BIND", "BIRTH", "REACTIVATE", "RELINK", "RETRACT",
        "SPLIT", "MERGE", "REPLACE",
    }, "program is not registered")
    _require(type(prior_cutoff_observation_index) is int and
             prior_cutoff_observation_index >= 0,
             "prior_cutoff_observation_index must be nonnegative")
    _require(type(terminal_observation_index) is int and
             terminal_observation_index >= 0,
             "terminal_observation_index must be nonnegative")
    _require(prior_cutoff_observation_index < terminal_observation_index,
             "matcher prior cutoff must precede terminal observation")
    _hex64(materializer_receipt_sha256, "materializer_receipt_sha256")
    _hex64(program_matcher_receipt_sha256,
           "program_matcher_receipt_sha256")
    _require(type(file_digests) is dict and set(file_digests) == FILE_DIGEST_KEYS,
             "episode construction file digests have unexpected fields")
    sealed_files = clone_json(dict(file_digests))
    for name, value in sealed_files.items():
        _hex64(value, name)
    if split_merge_artifact_receipt_file_sha256 is not None:
        _hex64(split_merge_artifact_receipt_file_sha256,
               "split_merge_artifact_receipt_file_sha256")
    _require(type(program_public_match_satisfied) is bool,
             "program_public_match_satisfied must be boolean")
    reasons = list(construction_failure_reasons)
    _require(all(type(reason) is str and reason for reason in reasons) and
             reasons == sorted(set(reasons)),
             "construction failure reasons must be sorted unique strings")
    _require((program_public_match_satisfied and not reasons) or
             (not program_public_match_satisfied and bool(reasons)),
             "matcher verdict and construction failure reasons disagree")
    if program not in {"SPLIT", "MERGE"}:
        _require(split_merge_artifact_receipt_file_sha256 is None,
                 "non-SPLIT/MERGE may not bind an artifact receipt file")

    receipt = {
        "schema_version": SCHEMA,
        "episode_id": episode_id,
        "program": program,
        "prior_cutoff_observation_index": prior_cutoff_observation_index,
        "terminal_observation_index": terminal_observation_index,
        "materializer_receipt_sha256": materializer_receipt_sha256,
        "program_matcher_receipt_sha256": program_matcher_receipt_sha256,
        **sealed_files,
        "split_merge_artifact_receipt_file_sha256":
            split_merge_artifact_receipt_file_sha256,
        "program_public_match_satisfied": program_public_match_satisfied,
        "episode_construction_status": (
            "public_match_satisfied_temporal_seal_pending"
            if program_public_match_satisfied else "construction_failure"
        ),
        "construction_failure_reasons": reasons,
        "construction_plan_pre_terminal_seal_established": False,
        "eligible_for_parent_family_completion": False,
        "posthoc_relabel_or_replacement_used": False,
        "private_identity_used": False,
        "semantic_identity_truth_established": False,
        "deployment_reader_may_open_construction_audit": False,
    }
    receipt["receipt_sha256"] = _sha(receipt)
    return receipt


def validate_episode_construction_receipt(
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the receipt so no caller-supplied completion flag is trusted."""

    expected = {
        "schema_version", "episode_id", "program",
        "prior_cutoff_observation_index", "terminal_observation_index",
        "materializer_receipt_sha256",
        "program_matcher_receipt_sha256", *FILE_DIGEST_KEYS,
        "split_merge_artifact_receipt_file_sha256",
        "program_public_match_satisfied", "episode_construction_status",
        "construction_failure_reasons",
        "construction_plan_pre_terminal_seal_established",
        "eligible_for_parent_family_completion",
        "posthoc_relabel_or_replacement_used", "private_identity_used",
        "semantic_identity_truth_established",
        "deployment_reader_may_open_construction_audit", "receipt_sha256",
    }
    _require(type(receipt) is dict and set(receipt) == expected,
             "episode construction receipt has unexpected fields")
    record = clone_json(dict(receipt))
    _require(record["schema_version"] == SCHEMA,
             "wrong episode construction receipt schema")
    _require(record["posthoc_relabel_or_replacement_used"] is False,
             "construction failure may not be relabeled or replaced")
    _require(record["private_identity_used"] is False and
             record["semantic_identity_truth_established"] is False,
             "episode construction receipt may not assert private identity")
    _require(record["deployment_reader_may_open_construction_audit"] is False,
             "deployment reader may not open construction audit artifacts")
    _require(record["construction_plan_pre_terminal_seal_established"] is False and
             record["eligible_for_parent_family_completion"] is False,
             "offline episode audit cannot establish temporal sealing or family eligibility")
    rebuilt = make_episode_construction_receipt(
        episode_id=record["episode_id"], program=record["program"],
        prior_cutoff_observation_index=record[
            "prior_cutoff_observation_index"
        ],
        terminal_observation_index=record["terminal_observation_index"],
        materializer_receipt_sha256=record["materializer_receipt_sha256"],
        program_matcher_receipt_sha256=
            record["program_matcher_receipt_sha256"],
        file_digests={name: record[name] for name in FILE_DIGEST_KEYS},
        split_merge_artifact_receipt_file_sha256=record[
            "split_merge_artifact_receipt_file_sha256"
        ],
        program_public_match_satisfied=record[
            "program_public_match_satisfied"
        ],
        construction_failure_reasons=record["construction_failure_reasons"],
    )
    _require(record["episode_construction_status"] == rebuilt[
        "episode_construction_status"
    ], "episode construction status is not mechanically derived")
    _require(record == rebuilt, "episode construction receipt digest mismatch")
    return record
