"""Pre-registered public program construction for VM-04.

This module binds each registered program to the exact public memory objects or
public rules that must exist before generation.  SPLIT/MERGE additionally bind
an expected deterministic proposal-cardinality transition and require every
fresh replay to realize it.  Private identity may grade later, but is absent
from these plans and receipts.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping, Sequence

from cpmt.executor import validate_graph
from cpmt.hashing import canonical_json, clone_json


HEX64 = re.compile(r"^[0-9a-f]{64}$")
PROGRAMS = (
    "NOOP", "BIND", "BIRTH", "REACTIVATE", "RELINK", "RETRACT",
    "SPLIT", "MERGE", "REPLACE",
)
PLAN_SCHEMA = "vsmt-vm04-public-program-construction-plan-v1"
ARTIFACT_SCHEMA = "vsmt-vm04-split-merge-artifact-plan-v1"
ARTIFACT_RECEIPT_SCHEMA = "vsmt-vm04-split-merge-artifact-receipt-v1"


REQUIRED_PRECONDITION_REFS = {
    "NOOP": {
        "stable_public_memory_sha256", "current_observation_rule_sha256",
    },
    "BIND": {
        "open_node_version_id", "prior_evidence_sha256",
        "current_region_selection_rule_sha256",
    },
    "BIRTH": {"reveal_locus_public_ref", "absence_scope_sha256"},
    "REACTIVATE": {"dormant_node_version_id", "prior_evidence_sha256"},
    "RELINK": {
        "open_entity_node_version_id", "old_located_at_edge_version_id",
        "old_place_node_version_id", "new_place_public_ref",
    },
    "RETRACT": {
        "open_entity_or_edge_version_id", "prior_evidence_sha256",
        "absence_rule_sha256",
    },
    "SPLIT": {
        "undersegmented_prior_node_version_id", "artifact_plan_sha256",
    },
    "MERGE": {
        "first_prior_node_version_id", "second_prior_node_version_id",
        "artifact_plan_sha256",
    },
    "REPLACE": {
        "open_old_entity_node_version_id", "new_reveal_locus_public_ref",
        "new_identity_absence_scope_sha256",
    },
}


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _hex(value: Any, name: str) -> str:
    if type(value) is not str or HEX64.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256")
    return value


def _payload_sha(value: Mapping[str, Any], seal_name: str) -> str:
    payload = clone_json(dict(value))
    payload.pop(seal_name, None)
    return _sha(payload)


def _open_nodes(memory: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(row["node_version_id"]): row
        for row in memory["nodes"] if row["valid_to"] is None
    }


def _open_edges(memory: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(row["edge_version_id"]): row
        for row in memory["edges"] if row["valid_to"] is None
    }


def _require_token(value: Any, name: str) -> str:
    if type(value) is not str or not value or any(character.isspace() for character in value):
        raise ValueError(f"{name} must be a nonempty token")
    return value


def make_split_merge_artifact_plan(
    *, program: str, family_id: str, geometry_spec_sha256: str,
    frontend_config_sha256: str, far_pose_public_ref: str,
    near_pose_public_ref: str, fresh_replay_repeat_count: int,
) -> dict[str, Any]:
    """Seal the expected public artifact before any generation outcome."""

    if program not in {"SPLIT", "MERGE"}:
        raise ValueError("artifact plan is only valid for SPLIT or MERGE")
    if type(fresh_replay_repeat_count) is not int or fresh_replay_repeat_count < 1:
        raise ValueError("fresh_replay_repeat_count must be positive")
    plan = {
        "schema_version": ARTIFACT_SCHEMA,
        "program": program,
        "family_id": _require_token(family_id, "family_id"),
        "geometry_spec_sha256": _hex(geometry_spec_sha256, "geometry_spec_sha256"),
        "frontend_config_sha256": _hex(
            frontend_config_sha256, "frontend_config_sha256",
        ),
        "far_pose_public_ref": _require_token(
            far_pose_public_ref, "far_pose_public_ref",
        ),
        "near_pose_public_ref": _require_token(
            near_pose_public_ref, "near_pose_public_ref",
        ),
        "fresh_replay_repeat_count": fresh_replay_repeat_count,
        "expected_far_public_entity_count": 1 if program == "SPLIT" else 2,
        "expected_near_public_entity_count": 2 if program == "SPLIT" else 1,
        "program_assignment_sealed_before_generation": True,
        "posthoc_relabel_allowed": False,
    }
    plan["artifact_plan_sha256"] = _sha(plan)
    return plan


def validate_split_merge_artifact_receipt(
    receipt: Mapping[str, Any], *, plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Require the registered transition on every independent fresh replay."""

    if plan.get("artifact_plan_sha256") != _payload_sha(
        plan, "artifact_plan_sha256",
    ) or plan.get("schema_version") != ARTIFACT_SCHEMA:
        raise ValueError("SPLIT/MERGE artifact plan seal mismatch")
    expected = {
        "schema_version", "artifact_plan_sha256", "program", "replays",
        "artifact_realized_on_every_replay", "construction_failure_reason",
        "posthoc_relabel_or_replacement_used", "receipt_sha256",
    }
    if set(receipt) != expected:
        raise ValueError("artifact receipt has unexpected fields")
    if receipt["schema_version"] != ARTIFACT_RECEIPT_SCHEMA:
        raise ValueError("wrong artifact receipt schema")
    if (receipt["artifact_plan_sha256"] != plan["artifact_plan_sha256"] or
            receipt["program"] != plan["program"]):
        raise ValueError("artifact receipt does not bind its plan")
    rows = receipt["replays"]
    if type(rows) is not list or len(rows) != plan["fresh_replay_repeat_count"]:
        raise ValueError("artifact receipt has wrong replay count")
    realized = True
    for index, row in enumerate(rows):
        if type(row) is not dict or set(row) != {
            "replay_index", "far_public_packet_sha256",
            "near_public_packet_sha256", "far_public_entity_region_ids",
            "near_public_entity_region_ids", "transition_support_sha256",
        }:
            raise ValueError("artifact replay row is malformed")
        if row["replay_index"] != index:
            raise ValueError("artifact replay indices are not canonical")
        for name in (
            "far_public_packet_sha256", "near_public_packet_sha256",
            "transition_support_sha256",
        ):
            _hex(row[name], name)
        far = row["far_public_entity_region_ids"]
        near = row["near_public_entity_region_ids"]
        if (type(far) is not list or type(near) is not list or
                any(type(item) is not str or not item for item in [*far, *near]) or
                len(far) != len(set(far)) or len(near) != len(set(near))):
            raise ValueError("artifact entity region IDs are malformed")
        realized = realized and (
            len(far) == plan["expected_far_public_entity_count"] and
            len(near) == plan["expected_near_public_entity_count"]
        )
    if receipt["artifact_realized_on_every_replay"] is not realized:
        raise ValueError("artifact realized flag is not mechanically derived")
    expected_failure = None if realized else "registered_split_merge_artifact_not_realized"
    if receipt["construction_failure_reason"] != expected_failure:
        raise ValueError("artifact construction failure reason mismatch")
    if receipt["posthoc_relabel_or_replacement_used"] is not False:
        raise ValueError("failed SPLIT/MERGE may not be relabeled or replaced")
    if receipt["receipt_sha256"] != _payload_sha(receipt, "receipt_sha256"):
        raise ValueError("artifact receipt digest mismatch")
    return clone_json(dict(receipt))


def make_program_construction_plan(
    *, episode_id: str, family_id: str, program: str,
    prior_memory: Mapping[str, Any], prior_memory_sha256: str,
    precondition_refs: Mapping[str, Any], visibility_subject_seal_sha256: str,
    matcher_config_sha256: str,
    artifact_plan: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Verify program-specific public prerequisites and seal their references."""

    if program not in PROGRAMS:
        raise ValueError("program is not registered")
    graph = clone_json(dict(prior_memory))
    validate_graph(graph, verify_hash=True)
    if graph.get("graph_hash") != _hex(prior_memory_sha256, "prior_memory_sha256"):
        raise ValueError("program plan prior memory digest mismatch")
    refs = clone_json(dict(precondition_refs))
    if set(refs) != REQUIRED_PRECONDITION_REFS[program]:
        raise ValueError("program precondition refs do not match registered slots")
    for name, value in refs.items():
        if name.endswith("sha256"):
            _hex(value, name)
        else:
            _require_token(value, name)
    nodes = _open_nodes(graph)
    edges = _open_edges(graph)

    def node(version_name: str) -> Mapping[str, Any]:
        version_id = refs[version_name]
        if version_id not in nodes:
            raise ValueError(f"{version_name} is not an open prior node")
        return nodes[version_id]

    if program == "BIND":
        node("open_node_version_id")
    elif program == "NOOP":
        if refs["stable_public_memory_sha256"] != prior_memory_sha256:
            raise ValueError("NOOP stable memory ref does not bind prior memory")
    elif program == "REACTIVATE":
        if node("dormant_node_version_id")["lifecycle"] != "dormant":
            raise ValueError("REACTIVATE requires a dormant prior node")
    elif program == "RELINK":
        entity = node("open_entity_node_version_id")
        place = node("old_place_node_version_id")
        if entity["node_type"] != "entity" or place["node_type"] != "place":
            raise ValueError("RELINK prior node types are invalid")
        edge_id = refs["old_located_at_edge_version_id"]
        edge = edges.get(edge_id)
        if (edge is None or edge["relation"] != "located_at" or
                edge["source"] != entity["node_id"] or
                edge["target"] != place["node_id"]):
            raise ValueError("RELINK lacks its open old located_at edge")
    elif program == "RETRACT":
        version_id = refs["open_entity_or_edge_version_id"]
        if version_id not in nodes and version_id not in edges:
            raise ValueError("RETRACT target is not open in prior memory")
        if version_id in nodes and nodes[version_id]["node_type"] != "entity":
            raise ValueError("RETRACT node target must be an entity")
    elif program == "SPLIT":
        if node("undersegmented_prior_node_version_id")["node_type"] != "entity":
            raise ValueError("SPLIT prior node must be an entity")
    elif program == "MERGE":
        first = node("first_prior_node_version_id")
        second = node("second_prior_node_version_id")
        if (first["node_type"] != "entity" or second["node_type"] != "entity" or
                first["node_id"] == second["node_id"]):
            raise ValueError("MERGE requires two distinct prior entity nodes")
    elif program == "REPLACE":
        if node("open_old_entity_node_version_id")["node_type"] != "entity":
            raise ValueError("REPLACE old node must be an entity")

    artifact_sha = None
    if program in {"SPLIT", "MERGE"}:
        if artifact_plan is None or artifact_plan.get("program") != program:
            raise ValueError("SPLIT/MERGE requires its registered artifact plan")
        artifact_sha = artifact_plan.get("artifact_plan_sha256")
        if artifact_sha != _payload_sha(artifact_plan, "artifact_plan_sha256"):
            raise ValueError("SPLIT/MERGE artifact plan seal mismatch")
        if refs["artifact_plan_sha256"] != artifact_sha:
            raise ValueError("program precondition does not bind artifact plan")
    elif artifact_plan is not None:
        raise ValueError("non-SPLIT/MERGE program may not bind an artifact plan")

    plan = {
        "schema_version": PLAN_SCHEMA,
        "episode_id": _require_token(episode_id, "episode_id"),
        "family_id": _require_token(family_id, "family_id"),
        "program": program,
        "prior_memory_sha256": prior_memory_sha256,
        "precondition_refs": refs,
        "visibility_subject_seal_sha256": _hex(
            visibility_subject_seal_sha256, "visibility_subject_seal_sha256",
        ),
        "matcher_config_sha256": _hex(
            matcher_config_sha256, "matcher_config_sha256",
        ),
        "artifact_plan_sha256": artifact_sha,
        "program_assignment_sealed_before_generation": True,
        "restricted_inputs_used": False,
    }
    plan["construction_plan_sha256"] = _sha(plan)
    return plan
