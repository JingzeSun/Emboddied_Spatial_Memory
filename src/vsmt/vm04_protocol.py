"""Fail-closed VM-04 protocol checks and label-independent data planning.

This module only validates configuration and creates manifests.  It does not
open simulator assets, render observations, generate labels, or train models.
"""

from __future__ import annotations

import hashlib
from itertools import product
import re
from typing import Any, Mapping, Sequence

from cpmt.hashing import canonical_json, clone_json


FAMILY_SCHEMA = "vsmt-vm04-family-split-manifest-v1"
PUBLIC_EPISODE_SCHEMA = "vsmt-vm04-public-episode-plan-v1"
PRIVATE_EPISODE_SCHEMA = "vsmt-vm04-private-episode-plan-v1"
ATOMIC_TEMPLATES = (
    "NOOP", "BIND", "BIRTH", "REACTIVATE", "RELINK", "RETRACT", "SPLIT",
    "MERGE",
)
REGISTERED_PROGRAMS = ATOMIC_TEMPLATES + ("REPLACE",)
DEVELOPMENT_SPLITS = ("audit", "train", "validation")
ALL_SPLITS = DEVELOPMENT_SPLITS + ("confirmation",)
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _raw_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _integer(value: Any, name: str, *, minimum: int = 0) -> int:
    _require(type(value) is int and value >= minimum,
             f"{name} must be an integer >= {minimum}")
    return value


def _hex64(value: Any, name: str) -> str:
    _require(type(value) is str and HEX64.fullmatch(value) is not None,
             f"{name} must be a lowercase SHA-256 digest")
    return value


def validate_vm04_protocol(config: Mapping[str, Any]) -> dict[str, Any]:
    """Check frozen arithmetic and structural invariants without authorizing work."""

    record = clone_json(dict(config))
    required_top = {
        "version", "status", "numeric_protocol_approved",
        "implementation_authorized", "asset_download_authorized",
        "generation_authorized", "training_authorized",
        "confirmation_authorized", "scope", "source_proposal",
        "experimental_unit", "split_proposal", "observation_proposal",
        "shared_frontend_proposal", "causal_prior_receipt_proposal",
        "semantic_and_metric_status", "leakage_gates", "budget_proposal",
        "required_review_decisions",
    }
    _require(required_top <= record.keys(), "VM-04 protocol is missing required sections")
    _require(type(record["version"]) is str and record["version"],
             "protocol version must be nonempty")
    for key in {
        "numeric_protocol_approved", "implementation_authorized",
        "asset_download_authorized", "generation_authorized",
        "training_authorized", "confirmation_authorized",
    }:
        _require(type(record[key]) is bool, f"{key} must be boolean")

    scope = record["scope"]
    _require(type(scope) is dict, "scope must be an object")
    _require(tuple(scope.get("atomic_templates", [])) == ATOMIC_TEMPLATES,
             "scope must contain the eight registered atoms in canonical order")
    _require(scope.get("registered_composite_positive") == "REPLACE",
             "REPLACE must be the registered composite positive")

    unit = record["experimental_unit"]
    split = record["split_proposal"]
    _require(type(unit) is dict and type(split) is dict,
             "experimental_unit and split_proposal must be objects")
    programs = _integer(unit.get("programs_per_family"), "programs_per_family", minimum=1)
    replicates = _integer(
        unit.get("replicates_per_program_per_family"),
        "replicates_per_program_per_family", minimum=1,
    )
    episodes = _integer(unit.get("episodes_per_family"), "episodes_per_family", minimum=1)
    observations = _integer(
        unit.get("observations_per_episode"), "observations_per_episode", minimum=1,
    )
    decision = _integer(
        unit.get("decision_observation_index_zero_based"),
        "decision_observation_index_zero_based",
    )
    _require(programs == len(REGISTERED_PROGRAMS),
             "programs_per_family must cover eight atoms plus REPLACE")
    _require(episodes == programs * replicates,
             "episodes_per_family arithmetic is inconsistent")
    _require(decision < observations, "decision observation must be inside the episode")
    _require(unit.get("public_prefix_indices_inclusive") == [0, decision],
             "public prefix must end at the decision observation")
    _require(unit.get("teacher_followup_indices_inclusive") == [decision + 1, observations - 1],
             "teacher followup must begin after the public decision")
    _require(unit.get("single_frame_random_split_allowed") is False,
             "single-frame random splitting must remain disabled")
    _require(unit.get("failed_episode_replacement") is False,
             "failed episodes must not be silently replaced")

    split_counts: dict[str, int] = {}
    episode_counts: dict[str, int] = {}
    for name in ALL_SPLITS:
        split_counts[name] = _integer(
            split.get(f"{name}_families"), f"{name}_families",
        )
        episode_counts[name] = _integer(
            split.get(f"{name}_episodes"), f"{name}_episodes",
        )
        _require(episode_counts[name] == split_counts[name] * episodes,
                 f"{name}_episodes arithmetic is inconsistent")
    _require(split.get("total_families") == sum(split_counts.values()),
             "total_families arithmetic is inconsistent")
    _require(split.get("total_episodes") == sum(episode_counts.values()),
             "total_episodes arithmetic is inconsistent")
    _require(
        split.get("total_observations") == split["total_episodes"] * observations,
        "total_observations arithmetic is inconsistent",
    )
    _integer(split.get("split_seed"), "split_seed")
    _require(split.get("confirmation_generation_deferred") is True,
             "confirmation generation must remain deferred")

    reviews = record["required_review_decisions"]
    _require(type(reviews) is list and all(type(item) is str and item for item in reviews),
             "required_review_decisions must be a list of nonempty strings")
    return record


def assert_vm04_action_authorized(
    config: Mapping[str, Any], *, action: str,
) -> None:
    """Reject every mutating action until its complete frozen gate is explicit."""

    record = validate_vm04_protocol(config)
    authorization = {
        "asset_download": "asset_download_authorized",
        "audit_generation": "generation_authorized",
        "train_validation_generation": "generation_authorized",
        "confirmation_generation": "confirmation_authorized",
        "training": "training_authorized",
    }
    _require(action in authorization, f"unknown VM-04 action {action!r}")
    _require(record["status"] == "frozen_executable",
             "VM-04 protocol status is not frozen_executable")
    _require(record["numeric_protocol_approved"] is True,
             "VM-04 numeric protocol is not approved")
    _require(record["implementation_authorized"] is True,
             "VM-04 implementation is not authorized")
    _require(record[authorization[action]] is True,
             f"VM-04 action {action!r} is not authorized")
    if action == "confirmation_generation":
        _require(record["generation_authorized"] is True,
                 "confirmation also requires generation authorization")
    _require(record["required_review_decisions"] == [],
             "VM-04 still has required review decisions")

    source = record["source_proposal"]
    frontend = record["shared_frontend_proposal"]
    semantics = record["semantic_and_metric_status"]
    leakage = record["leakage_gates"]
    _require(source.get("ai2thor_package_sha256") is not None,
             "AI2-THOR package digest is unresolved")
    _require(source.get("procthor_revision") is not None,
             "ProcTHOR revision is unresolved")
    _require(source.get("procthor_manifest_sha256") is not None,
             "ProcTHOR manifest digest is unresolved")
    region = frontend["region_proposal"]
    _require(region.get("repository_commit") is not None,
             "region proposal commit is unresolved")
    _require(region.get("checkpoint_sha256") is not None,
             "region proposal checkpoint digest is unresolved")
    _require(region.get("automatic_mask_parameters") is not None,
             "region proposal parameters are unresolved")
    _require(frontend["geometry"].get("numeric_thresholds") is not None,
             "public geometry thresholds are unresolved")
    _require(
        record["causal_prior_receipt_proposal"].get("builder_thresholds") is not None,
        "causal prior thresholds are unresolved",
    )
    semantic_flags = {
        key: value for key, value in semantics.items() if key.endswith("_frozen")
    }
    _require(semantic_flags and all(value is True for value in semantic_flags.values()),
             "semantic and metric choices are not all frozen")
    _require(leakage.get("nuisance_probe_gate") is not None,
             "nuisance probe gate is unresolved")


def _manifest_payload(manifest: Mapping[str, Any]) -> dict[str, Any]:
    payload = clone_json(dict(manifest))
    payload.pop("manifest_sha256", None)
    return payload


def make_family_split_manifest(
    eligible_house_ids: Sequence[str], *, config: Mapping[str, Any],
    source_manifest_sha256: str,
) -> dict[str, Any]:
    """Select disjoint house families deterministically; no files are opened."""

    record = validate_vm04_protocol(config)
    source_digest = _hex64(source_manifest_sha256, "source_manifest_sha256")
    house_ids = list(eligible_house_ids)
    _require(all(type(item) is str and item for item in house_ids),
             "eligible house IDs must be nonempty strings")
    _require(len(house_ids) == len(set(house_ids)),
             "eligible house IDs must be unique")
    split = record["split_proposal"]
    required = int(split["total_families"])
    _require(len(house_ids) >= required,
             f"need at least {required} eligible house families")
    seed = int(split["split_seed"])
    ordered = sorted(house_ids, key=lambda house_id: hashlib.sha256(
        f"{source_digest}|{seed}|{house_id}".encode("utf-8")
    ).hexdigest())[:required]

    rows: list[dict[str, Any]] = []
    cursor = 0
    for split_name in ALL_SPLITS:
        count = int(split[f"{split_name}_families"])
        for source_house_id in ordered[cursor:cursor + count]:
            rows.append({
                "family_id": f"family:{cursor:04d}",
                "source_house_id": (
                    None if split_name == "confirmation" else source_house_id
                ),
                "source_house_id_sha256": hashlib.sha256(
                    f"{source_digest}|{source_house_id}".encode("utf-8")
                ).hexdigest(),
                "split": split_name,
                "rank": cursor,
            })
            cursor += 1
    manifest: dict[str, Any] = {
        "schema_version": FAMILY_SCHEMA,
        "protocol_version": record["version"],
        "source_manifest_sha256": source_digest,
        "split_seed": seed,
        "eligible_house_count": len(house_ids),
        "selected_family_count": len(rows),
        "families": rows,
    }
    manifest["manifest_sha256"] = _raw_sha256(manifest)
    return validate_family_split_manifest(manifest, config=record)


def validate_family_split_manifest(
    manifest: Mapping[str, Any], *, config: Mapping[str, Any],
) -> dict[str, Any]:
    record = validate_vm04_protocol(config)
    expected = {
        "schema_version", "protocol_version", "source_manifest_sha256",
        "split_seed", "eligible_house_count", "selected_family_count",
        "families", "manifest_sha256",
    }
    _require(set(manifest) == expected, "family split manifest has unexpected fields")
    _require(manifest["schema_version"] == FAMILY_SCHEMA,
             "wrong family split manifest schema")
    _require(manifest["protocol_version"] == record["version"],
             "family manifest protocol mismatch")
    _hex64(manifest["source_manifest_sha256"], "source_manifest_sha256")
    _hex64(manifest["manifest_sha256"], "manifest_sha256")
    _require(manifest["split_seed"] == record["split_proposal"]["split_seed"],
             "family manifest split seed mismatch")
    rows = manifest["families"]
    _require(type(rows) is list, "families must be a list")
    _require(all(type(row) is dict for row in rows),
             "every family row must be an object")
    _require(type(manifest["eligible_house_count"]) is int
             and manifest["eligible_house_count"] >= len(rows),
             "eligible_house_count must cover every selected family")
    _require(manifest["selected_family_count"] == len(rows),
             "selected family count mismatch")
    _require(len(rows) == record["split_proposal"]["total_families"],
             "family manifest does not contain the frozen total")
    expected_ids = [f"family:{index:04d}" for index in range(len(rows))]
    _require([row.get("family_id") for row in rows] == expected_ids,
             "family IDs must be canonical ordinals")
    for index, row in enumerate(rows):
        _require(set(row) == {
            "family_id", "source_house_id", "source_house_id_sha256", "split", "rank",
        }, f"families[{index}] has unexpected fields")
        _require(row["rank"] == index, "family rank must match canonical order")
        _require(row["split"] in ALL_SPLITS, "family split is not registered")
        _hex64(row["source_house_id_sha256"], "source_house_id_sha256")
        if row["split"] == "confirmation":
            _require(row["source_house_id"] is None,
                     "confirmation source house ID must remain sealed")
        else:
            _require(type(row["source_house_id"]) is str and row["source_house_id"],
                     "development source house ID must be nonempty")
            expected_commitment = hashlib.sha256(
                f"{manifest['source_manifest_sha256']}|{row['source_house_id']}".encode(
                    "utf-8"
                )
            ).hexdigest()
            _require(row["source_house_id_sha256"] == expected_commitment,
                     "development source house commitment mismatch")
    commitments = [row["source_house_id_sha256"] for row in rows]
    _require(len(commitments) == len(set(commitments)),
             "a source house may not cross or repeat across splits")
    for split_name in ALL_SPLITS:
        observed = sum(row.get("split") == split_name for row in rows)
        _require(observed == record["split_proposal"][f"{split_name}_families"],
                 f"{split_name} family count mismatch")
    _require(manifest["manifest_sha256"] == _raw_sha256(_manifest_payload(manifest)),
             "family split manifest digest mismatch")
    return clone_json(dict(manifest))


def reveal_confirmation_family_ids(
    eligible_house_ids: Sequence[str], family_manifest: Mapping[str, Any], *,
    config: Mapping[str, Any],
) -> list[dict[str, str]]:
    """Reveal confirmation source IDs only after the confirmation action gate."""

    record = validate_vm04_protocol(config)
    assert_vm04_action_authorized(record, action="confirmation_generation")
    families = validate_family_split_manifest(family_manifest, config=record)
    house_ids = list(eligible_house_ids)
    _require(all(type(item) is str and item for item in house_ids)
             and len(house_ids) == len(set(house_ids)),
             "eligible house IDs must be unique nonempty strings")
    required = int(record["split_proposal"]["total_families"])
    _require(len(house_ids) >= required,
             f"need at least {required} eligible house families")
    source_digest = families["source_manifest_sha256"]
    seed = int(families["split_seed"])
    ordered = sorted(house_ids, key=lambda house_id: hashlib.sha256(
        f"{source_digest}|{seed}|{house_id}".encode("utf-8")
    ).hexdigest())[:required]
    revealed: list[dict[str, str]] = []
    for row, source_house_id in zip(families["families"], ordered, strict=True):
        commitment = hashlib.sha256(
            f"{source_digest}|{source_house_id}".encode("utf-8")
        ).hexdigest()
        _require(commitment == row["source_house_id_sha256"],
                 "eligible house list does not match the sealed family manifest")
        if row["split"] == "confirmation":
            revealed.append({
                "family_id": row["family_id"],
                "source_house_id": source_house_id,
            })
    return revealed


def make_episode_plan_manifests(
    family_manifest: Mapping[str, Any], *, config: Mapping[str, Any],
    assignment_salt_sha256: str, included_splits: Sequence[str],
) -> dict[str, dict[str, Any]]:
    """Plan balanced episode slots whose public IDs are independent of labels."""

    record = validate_vm04_protocol(config)
    families = validate_family_split_manifest(family_manifest, config=record)
    salt = _hex64(assignment_salt_sha256, "assignment_salt_sha256")
    requested = tuple(included_splits)
    _require(requested and len(requested) == len(set(requested)),
             "included_splits must be nonempty and unique")
    _require(all(split in ALL_SPLITS for split in requested),
             "included_splits contains an unknown split")
    if "confirmation" in requested:
        assert_vm04_action_authorized(record, action="confirmation_generation")
    public_rows: list[dict[str, Any]] = []
    private_rows: list[dict[str, Any]] = []
    replicates = int(record["experimental_unit"]["replicates_per_program_per_family"])
    observations = int(record["experimental_unit"]["observations_per_episode"])
    decision = int(record["experimental_unit"]["decision_observation_index_zero_based"])
    for family in families["families"]:
        if family["split"] not in requested:
            continue
        assignments = list(product(REGISTERED_PROGRAMS, range(replicates)))
        assignments.sort(key=lambda item: hashlib.sha256(
            f"{salt}|{family['family_id']}|{item[0]}|{item[1]}".encode("utf-8")
        ).hexdigest())
        for slot, (program_name, replicate) in enumerate(assignments):
            episode_id = "episode:" + hashlib.sha256(
                f"{record['version']}|{family['family_id']}|{slot}".encode("utf-8")
            ).hexdigest()[:24]
            public_rows.append({
                "episode_id": episode_id,
                "family_id": family["family_id"],
                "split": family["split"],
                "slot": slot,
                "observation_count": observations,
                "decision_observation_index_zero_based": decision,
            })
            private_rows.append({
                "episode_id": episode_id,
                "program": program_name,
                "replicate": replicate,
            })

    public_manifest: dict[str, Any] = {
        "schema_version": PUBLIC_EPISODE_SCHEMA,
        "protocol_version": record["version"],
        "family_manifest_sha256": families["manifest_sha256"],
        "included_splits": list(requested),
        "episode_count": len(public_rows),
        "episodes": public_rows,
    }
    public_manifest["manifest_sha256"] = _raw_sha256(public_manifest)
    private_manifest: dict[str, Any] = {
        "schema_version": PRIVATE_EPISODE_SCHEMA,
        "protocol_version": record["version"],
        "public_episode_manifest_sha256": public_manifest["manifest_sha256"],
        "assignment_salt_sha256": salt,
        "episode_count": len(private_rows),
        "assignments": private_rows,
    }
    private_manifest["manifest_sha256"] = _raw_sha256(private_manifest)
    return validate_episode_plan_manifests(
        {"public": public_manifest, "private": private_manifest},
        family_manifest=families,
        config=record,
    )


def validate_episode_plan_manifests(
    manifests: Mapping[str, Mapping[str, Any]], *,
    family_manifest: Mapping[str, Any], config: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Verify public/private episode plans are balanced and digest-bound."""

    record = validate_vm04_protocol(config)
    families = validate_family_split_manifest(family_manifest, config=record)
    _require(set(manifests) == {"public", "private"},
             "episode plans must contain public and private manifests")
    public = clone_json(dict(manifests["public"]))
    private = clone_json(dict(manifests["private"]))
    expected_public = {
        "schema_version", "protocol_version", "family_manifest_sha256",
        "included_splits", "episode_count", "episodes", "manifest_sha256",
    }
    expected_private = {
        "schema_version", "protocol_version", "public_episode_manifest_sha256",
        "assignment_salt_sha256", "episode_count", "assignments",
        "manifest_sha256",
    }
    _require(set(public) == expected_public, "public episode plan has unexpected fields")
    _require(set(private) == expected_private,
             "private episode plan has unexpected fields")
    _require(public["schema_version"] == PUBLIC_EPISODE_SCHEMA,
             "wrong public episode plan schema")
    _require(private["schema_version"] == PRIVATE_EPISODE_SCHEMA,
             "wrong private episode plan schema")
    _require(public["protocol_version"] == private["protocol_version"] == record["version"],
             "episode plan protocol mismatch")
    _require(public["family_manifest_sha256"] == families["manifest_sha256"],
             "public episode plan is bound to another family manifest")
    _hex64(public["manifest_sha256"], "public manifest_sha256")
    _hex64(private["manifest_sha256"], "private manifest_sha256")
    _hex64(private["assignment_salt_sha256"], "assignment_salt_sha256")
    _require(public["manifest_sha256"] == _raw_sha256(_manifest_payload(public)),
             "public episode plan digest mismatch")
    _require(private["manifest_sha256"] == _raw_sha256(_manifest_payload(private)),
             "private episode plan digest mismatch")
    _require(private["public_episode_manifest_sha256"] == public["manifest_sha256"],
             "private episode plan is bound to another public plan")

    included = public["included_splits"]
    _require(type(included) is list and included
             and len(included) == len(set(included))
             and all(item in ALL_SPLITS for item in included),
             "public included_splits is invalid")
    public_rows = public["episodes"]
    private_rows = private["assignments"]
    _require(type(public_rows) is list and type(private_rows) is list,
             "episode rows must be lists")
    _require(public["episode_count"] == private["episode_count"]
             == len(public_rows) == len(private_rows),
             "episode plan counts differ")
    family_by_id = {row["family_id"]: row for row in families["families"]}
    expected_family_ids = [
        row["family_id"] for row in families["families"]
        if row["split"] in included
    ]
    episodes_per_family = int(record["experimental_unit"]["episodes_per_family"])
    _require(len(public_rows) == len(expected_family_ids) * episodes_per_family,
             "episode plan total is inconsistent with included families")
    observed_episode_ids: list[str] = []
    for row in public_rows:
        _require(type(row) is dict and set(row) == {
            "episode_id", "family_id", "split", "slot", "observation_count",
            "decision_observation_index_zero_based",
        }, "public episode row has unexpected fields")
        family = family_by_id.get(row["family_id"])
        _require(family is not None and family["split"] == row["split"]
                 and row["split"] in included,
                 "public episode row has inconsistent family/split")
        slot = row["slot"]
        _require(type(slot) is int and 0 <= slot < episodes_per_family,
                 "public episode slot is invalid")
        expected_episode_id = "episode:" + hashlib.sha256(
            f"{record['version']}|{row['family_id']}|{slot}".encode("utf-8")
        ).hexdigest()[:24]
        _require(row["episode_id"] == expected_episode_id,
                 "public episode ID encodes unexpected information")
        _require(row["observation_count"]
                 == record["experimental_unit"]["observations_per_episode"],
                 "public episode observation count mismatch")
        _require(row["decision_observation_index_zero_based"]
                 == record["experimental_unit"]["decision_observation_index_zero_based"],
                 "public episode decision index mismatch")
        observed_episode_ids.append(row["episode_id"])
    _require(len(observed_episode_ids) == len(set(observed_episode_ids)),
             "public episode IDs must be unique")
    for family_id in expected_family_ids:
        slots = sorted(
            row["slot"] for row in public_rows if row["family_id"] == family_id
        )
        _require(slots == list(range(episodes_per_family)),
                 "each family must contain every canonical episode slot")

    private_ids: list[str] = []
    private_by_id: dict[str, dict[str, Any]] = {}
    for row in private_rows:
        _require(type(row) is dict and set(row) == {
            "episode_id", "program", "replicate",
        }, "private episode assignment has unexpected fields")
        _require(row["program"] in REGISTERED_PROGRAMS,
                 "private episode program is not registered")
        _require(type(row["replicate"]) is int
                 and 0 <= row["replicate"]
                 < record["experimental_unit"]["replicates_per_program_per_family"],
                 "private episode replicate is invalid")
        private_ids.append(row["episode_id"])
        private_by_id[row["episode_id"]] = row
    _require(private_ids == observed_episode_ids,
             "private assignments must preserve public episode order")
    _require(len(private_by_id) == len(private_ids),
             "private episode IDs must be unique")
    for family_id in expected_family_ids:
        family_episode_ids = [
            row["episode_id"] for row in public_rows if row["family_id"] == family_id
        ]
        pairs = {
            (private_by_id[episode_id]["program"],
             private_by_id[episode_id]["replicate"])
            for episode_id in family_episode_ids
        }
        expected_pairs = set(product(
            REGISTERED_PROGRAMS,
            range(record["experimental_unit"]["replicates_per_program_per_family"]),
        ))
        _require(pairs == expected_pairs,
                 "each family must contain every program/replicate exactly once")
    return {"public": public, "private": private}
