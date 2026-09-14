"""VM-01 public/private and shared-adapter contracts.

This module deliberately contains no candidate proposal, teacher scoring,
metric, or model logic.  It only makes the deployable information boundary
explicit and binds later artifacts to immutable digests.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping, Protocol, TypedDict, runtime_checkable

from cpmt.executor import validate_graph
from cpmt.hashing import canonical_json, clone_json, compute_graph_hash


OBSERVATION_SCHEMA = "vsmt-observation-packet-v3"
CANDIDATE_SCHEMA = "vsmt-candidate-catalog-v2"
TEACHER_SCHEMA = "vsmt-teacher-targets-v1"
RESULT_SCHEMA = "vsmt-memory-update-result-v1"
PRIVATE_SCHEMA = "vsmt-private-evaluation-v1"
INVARIANCE_SCHEMA = "vsmt-private-mutation-invariance-v1"

HEX64 = re.compile(r"^[0-9a-f]{64}$")
OPAQUE_REGION = re.compile(r"^region:[0-9]{4}$")
OPAQUE_FREE_SPACE = re.compile(r"^free:[0-9]{4}$")
OPAQUE_VISIBILITY = re.compile(r"^visibility:[0-9]{4}$")
OPAQUE_RELATION = re.compile(r"^relation:[0-9]{4}$")
OPAQUE_CANDIDATE = re.compile(r"^candidate:[0-9]{4}$")
OPAQUE_LATENT_REF = re.compile(r"^latent:[0-9a-f]{16,64}$")
IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")
FEATURE_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

OBSERVATION_KEYS = {
    "schema_version",
    "sample_id_hash",
    "decision_time_s",
    "rgbd_refs",
    "camera_pose",
    "robot_state",
    "past_actions",
    "region_observations",
    "relation_observations",
    "free_space_observations",
    "visibility_observations",
    "prior_memory_ref",
    "public_constants",
}
RGBD_REF_KEYS = {"rgb_sha256", "depth_sha256"}
POSE_KEYS = {"position_m", "quaternion_xyzw"}
ROBOT_STATE_KEYS = {"feature_names", "values"}
ACTION_KEYS = {"end_time_s", "command"}
REGION_KEYS = {
    "region_id",
    "structure_kind",
    "mask_sha256",
    "descriptor",
    "centroid_m",
    "extent_m",
    "reliability",
    "proposal_source_id",
}
FREE_SPACE_KEYS = {
    "free_space_id",
    "time_s",
    "halfspaces_world",
    "reliability",
    "support_sha256",
}
VISIBILITY_KEYS = {
    "visibility_id",
    "time_s",
    "halfspaces_world",
    "reliability",
    "support_sha256",
}
HALFSPACE_KEYS = {"normal", "offset_m"}
RELATION_KEYS = {
    "relation_id",
    "source_region_id",
    "target_region_id",
    "relation",
    "reliability",
    "support_sha256",
}
RELATION_ENDPOINT_KINDS = {
    "located_at": ("entity", "place"),
    "contains": ("place", "entity"),
    "supported_by": ("entity", "surface"),
    "adjacent_to": ("place", "place"),
}
STRUCTURE_KINDS = {"entity", "place", "surface", "fragment"}
PRIOR_REF_KEYS = {"graph_version", "graph_sha256"}
PUBLIC_CONSTANT_KEYS = {
    "coordinate_frame",
    "depth_unit",
    "descriptor_model_id",
    "proposal_model_id",
}

FORBIDDEN_INFORMATION_KEYS = {
    "answer",
    "future",
    "future_observation",
    "future_state",
    "ground_truth",
    "instance_id",
    "label",
    "merge_queries",
    "oracle",
    "private_eval",
    "reference",
    "reference_spec",
    "reference_transaction",
    "scenario_family",
    "teacher",
    "template_label",
    "true_mask",
    "world_id",
}
FORBIDDEN_INFORMATION_KEY_FRAGMENTS = {
    "answer",
    "future",
    "ground_truth",
    "instance_id",
    "label",
    "merge_queries",
    "oracle",
    "private",
    "reference",
    "scenario_family",
    "teacher",
    "true_mask",
    "world_id",
}
PUBLIC_MECHANISM_KEYS = {"composition_label"}
FORBIDDEN_DERIVATION_TOKENS = {
    "answer",
    "future",
    "ground_truth",
    "instance_id",
    "label",
    "oracle",
    "private",
    "reference",
    "scenario",
    "teacher",
    "true_mask",
}
PUBLIC_DERIVATION_ROOTS = {
    "/decision_time_s",
    "/camera_pose",
    "/robot_state",
    "/past_actions",
    "/region_observations",
    "/relation_observations",
    "/free_space_observations",
    "/visibility_observations",
    "/public_constants",
}
MEMORY_DERIVATION_ROOTS = {
    "/graph_version",
    "/nodes",
    "/edges",
    "/transaction_log",
}
NORMALIZED_DELTA_KEYS = {
    "declared_template",
    "created_node_version_ids",
    "closed_node_version_ids",
    "created_edge_version_ids",
    "closed_edge_version_ids",
}
DECLARED_TEMPLATES = {
    "NOOP",
    "BIND",
    "BIRTH",
    "REACTIVATE",
    "RELINK",
    "RETRACT",
    "SPLIT",
    "MERGE",
    "REPLACE",
}
SEMANTIC_IN_PLACE_FIELDS_BY_TEMPLATE = {
    "MERGE": frozenset({"lifecycle", "canonical_id"}),
}


class AdapterInput(TypedDict):
    """The only value passed to a deployable memory-update method."""

    decision_time_s: float
    camera_pose: dict[str, Any]
    robot_state: dict[str, Any]
    past_actions: list[dict[str, Any]]
    region_observations: list[dict[str, Any]]
    relation_observations: list[dict[str, Any]]
    free_space_observations: list[dict[str, Any]]
    visibility_observations: list[dict[str, Any]]
    prior_memory: dict[str, Any]
    public_constants: dict[str, str]


@runtime_checkable
class MemoryUpdateAdapter(Protocol):
    """Common online interface; private evaluation is intentionally absent."""

    method_id: str

    def update(self, model_input: AdapterInput) -> Mapping[str, Any]:
        """Return one ``vsmt-memory-update-result-v1`` record."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _exact_keys(value: Mapping[str, Any], expected: set[str], name: str) -> None:
    _require(set(value) == expected, f"{name} must contain exactly {sorted(expected)}")


def _is_number(value: Any) -> bool:
    return type(value) in {int, float} and math.isfinite(float(value))


def _number(value: Any, name: str, *, minimum: float | None = None) -> float:
    _require(_is_number(value), f"{name} must be a finite number")
    result = float(value)
    if minimum is not None:
        _require(result >= minimum, f"{name} must be >= {minimum}")
    return result


def _vector(
    value: Any,
    name: str,
    *,
    length: int | None = None,
    nonempty: bool = False,
    minimum: float | None = None,
) -> list[float]:
    _require(type(value) is list, f"{name} must be a list")
    if length is not None:
        _require(len(value) == length, f"{name} must have length {length}")
    if nonempty:
        _require(bool(value), f"{name} must be nonempty")
    return [
        _number(item, f"{name}[{index}]", minimum=minimum)
        for index, item in enumerate(value)
    ]


def _hex64(value: Any, name: str) -> str:
    _require(type(value) is str and HEX64.fullmatch(value) is not None,
             f"{name} must be a lowercase SHA-256 hex digest")
    return value


def _identifier(value: Any, name: str) -> str:
    _require(type(value) is str and IDENTIFIER.fullmatch(value) is not None,
             f"{name} must be a lowercase opaque identifier")
    return value


def _reject_forbidden_keys(value: Any, *, location: str = "$") -> None:
    if type(value) is dict:
        for key, item in value.items():
            _require(type(key) is str, f"{location} contains a non-string key")
            normalized = key.lower()
            if normalized not in PUBLIC_MECHANISM_KEYS:
                _require(
                    normalized not in FORBIDDEN_INFORMATION_KEYS
                    and not any(
                        fragment in normalized
                        for fragment in FORBIDDEN_INFORMATION_KEY_FRAGMENTS
                    ),
                    f"forbidden information key {key!r} at {location}",
                )
            _reject_forbidden_keys(item, location=f"{location}.{key}")
    elif type(value) is list:
        for index, item in enumerate(value):
            _reject_forbidden_keys(item, location=f"{location}[{index}]")
    else:
        _require(value is None or type(value) in {str, int, float, bool},
                 f"{location} is not JSON-native")
        if type(value) is float:
            _require(math.isfinite(value), f"{location} is not finite")


def _validate_json_native(value: Any, *, location: str = "$") -> None:
    if type(value) is dict:
        for key, item in value.items():
            _require(type(key) is str, f"{location} contains a non-string key")
            _validate_json_native(item, location=f"{location}.{key}")
    elif type(value) is list:
        for index, item in enumerate(value):
            _validate_json_native(item, location=f"{location}[{index}]")
    else:
        _require(value is None or type(value) in {str, int, float, bool},
                 f"{location} is not JSON-native")
        if type(value) is float:
            _require(math.isfinite(value), f"{location} is not finite")


def canonical_sha256(value: Any) -> str:
    """Hash a public-safe JSON value using the repository canonical encoding."""

    _reject_forbidden_keys(value)
    return _raw_canonical_sha256(value)


def _raw_canonical_sha256(value: Any) -> str:
    _validate_json_native(value)
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _graph_digest(graph: Mapping[str, Any]) -> str:
    copy = clone_json(dict(graph))
    validate_graph(copy, verify_hash=True)
    return compute_graph_hash(copy)


def _public_memory_digest(graph: Mapping[str, Any]) -> str:
    _reject_forbidden_keys(graph, location="$.prior_memory")
    nodes = graph.get("nodes")
    _require(type(nodes) is list, "prior memory nodes must be a list")
    for node_index, node in enumerate(nodes):
        _require(type(node) is dict,
                 f"prior memory nodes[{node_index}] must be an object")
        latent_refs = node.get("latent_refs")
        _require(type(latent_refs) is list and all(
            type(item) is str and OPAQUE_LATENT_REF.fullmatch(item) is not None
            for item in latent_refs
        ), (
            f"prior memory nodes[{node_index}].latent_refs must contain only "
            "public-derived opaque latent digests"
        ))
    return _graph_digest(graph)


def validate_observation_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and clone one public-only online observation packet."""

    _exact_keys(packet, OBSERVATION_KEYS, "observation packet")
    _require(packet["schema_version"] == OBSERVATION_SCHEMA,
             "wrong observation packet schema")
    _hex64(packet["sample_id_hash"], "sample_id_hash")
    decision_time = _number(packet["decision_time_s"], "decision_time_s", minimum=0.0)

    rgbd_refs = packet["rgbd_refs"]
    _require(type(rgbd_refs) is dict, "rgbd_refs must be an object")
    _exact_keys(rgbd_refs, RGBD_REF_KEYS, "rgbd_refs")
    for key in sorted(RGBD_REF_KEYS):
        _hex64(rgbd_refs[key], f"rgbd_refs.{key}")

    pose = packet["camera_pose"]
    _require(type(pose) is dict, "camera_pose must be an object")
    _exact_keys(pose, POSE_KEYS, "camera_pose")
    _vector(pose["position_m"], "camera_pose.position_m", length=3)
    quaternion = _vector(
        pose["quaternion_xyzw"], "camera_pose.quaternion_xyzw", length=4,
    )
    norm = math.sqrt(sum(item * item for item in quaternion))
    _require(abs(norm - 1.0) <= 1e-6, "camera quaternion must have unit norm")

    robot = packet["robot_state"]
    _require(type(robot) is dict, "robot_state must be an object")
    _exact_keys(robot, ROBOT_STATE_KEYS, "robot_state")
    names = robot["feature_names"]
    values = robot["values"]
    _require(type(names) is list and all(
        type(item) is str and FEATURE_NAME.fullmatch(item) is not None
        for item in names
    ), "robot_state.feature_names must be lowercase field identifiers")
    _require(len(names) == len(set(names)), "robot_state feature names must be unique")
    _vector(values, "robot_state.values", length=len(names))

    actions = packet["past_actions"]
    _require(type(actions) is list, "past_actions must be a list")
    last_time = -math.inf
    for index, action in enumerate(actions):
        _require(type(action) is dict, f"past_actions[{index}] must be an object")
        _exact_keys(action, ACTION_KEYS, f"past_actions[{index}]")
        end_time = _number(action["end_time_s"], f"past_actions[{index}].end_time_s",
                           minimum=0.0)
        _require(last_time <= end_time <= decision_time,
                 "past action times must be ordered and not enter the future")
        last_time = end_time
        _vector(action["command"], f"past_actions[{index}].command", nonempty=True)

    regions = packet["region_observations"]
    _require(type(regions) is list, "region_observations must be a list")
    for index, region in enumerate(regions):
        _require(type(region) is dict, f"region_observations[{index}] must be an object")
        _exact_keys(region, REGION_KEYS, f"region_observations[{index}]")
        expected_id = f"region:{index:04d}"
        _require(
            type(region["region_id"]) is str
            and OPAQUE_REGION.fullmatch(region["region_id"]) is not None
            and region["region_id"] == expected_id,
            "region IDs must be packet-local opaque ordinals",
        )
        _require(type(region["structure_kind"]) is str
                 and region["structure_kind"] in STRUCTURE_KINDS,
                 "region structure_kind is not supported")
        _hex64(region["mask_sha256"], f"region_observations[{index}].mask_sha256")
        _vector(region["descriptor"], f"region_observations[{index}].descriptor",
                nonempty=True)
        _vector(region["centroid_m"], f"region_observations[{index}].centroid_m",
                length=3)
        _vector(region["extent_m"], f"region_observations[{index}].extent_m",
                length=3, minimum=0.0)
        reliability = _number(region["reliability"],
                              f"region_observations[{index}].reliability")
        _require(0.0 <= reliability <= 1.0, "region reliability must be within [0, 1]")
        _identifier(region["proposal_source_id"],
                    f"region_observations[{index}].proposal_source_id")

    region_by_id = {region["region_id"]: region for region in regions}
    relations = packet["relation_observations"]
    _require(type(relations) is list, "relation_observations must be a list")
    for index, relation in enumerate(relations):
        _require(type(relation) is dict,
                 f"relation_observations[{index}] must be an object")
        _exact_keys(relation, RELATION_KEYS,
                    f"relation_observations[{index}]")
        expected_id = f"relation:{index:04d}"
        _require(
            type(relation["relation_id"]) is str
            and OPAQUE_RELATION.fullmatch(relation["relation_id"]) is not None
            and relation["relation_id"] == expected_id,
            "relation IDs must be packet-local opaque ordinals",
        )
        source_id = relation["source_region_id"]
        target_id = relation["target_region_id"]
        _require(type(source_id) is str and type(target_id) is str,
                 "relation endpoints must be strings")
        _require(source_id in region_by_id and target_id in region_by_id,
                 "relation endpoints must reference packet-local regions")
        _require(source_id != target_id, "relation endpoints must be distinct")
        relation_kind = relation["relation"]
        _require(type(relation_kind) is str
                 and relation_kind in RELATION_ENDPOINT_KINDS,
                 "relation kind is not supported")
        expected_kinds = RELATION_ENDPOINT_KINDS[relation_kind]
        actual_kinds = (
            region_by_id[source_id]["structure_kind"],
            region_by_id[target_id]["structure_kind"],
        )
        _require(actual_kinds == expected_kinds,
                 "relation endpoint kinds do not match relation type")
        reliability = _number(
            relation["reliability"],
            f"relation_observations[{index}].reliability",
        )
        _require(0.0 <= reliability <= 1.0,
                 "relation reliability must be within [0, 1]")
        _hex64(relation["support_sha256"],
               f"relation_observations[{index}].support_sha256")

    free_spaces = packet["free_space_observations"]
    _require(type(free_spaces) is list, "free_space_observations must be a list")
    previous_free_time = -math.inf
    for index, free_space in enumerate(free_spaces):
        _require(type(free_space) is dict,
                 f"free_space_observations[{index}] must be an object")
        _exact_keys(free_space, FREE_SPACE_KEYS,
                    f"free_space_observations[{index}]")
        expected_id = f"free:{index:04d}"
        _require(
            type(free_space["free_space_id"]) is str
            and OPAQUE_FREE_SPACE.fullmatch(free_space["free_space_id"]) is not None
            and free_space["free_space_id"] == expected_id,
            "free-space IDs must be packet-local opaque ordinals",
        )
        free_time = _number(
            free_space["time_s"],
            f"free_space_observations[{index}].time_s", minimum=0.0,
        )
        _require(previous_free_time <= free_time <= decision_time,
                 "free-space times must be ordered and not enter the future")
        previous_free_time = free_time
        halfspaces = free_space["halfspaces_world"]
        _require(type(halfspaces) is list and len(halfspaces) == 6,
                 "free-space frustum must contain exactly six halfspaces")
        for plane_index, halfspace in enumerate(halfspaces):
            name = f"free_space_observations[{index}].halfspaces_world[{plane_index}]"
            _require(type(halfspace) is dict, f"{name} must be an object")
            _exact_keys(halfspace, HALFSPACE_KEYS, name)
            normal = _vector(halfspace["normal"], f"{name}.normal", length=3)
            norm = math.sqrt(sum(value * value for value in normal))
            _require(abs(norm - 1.0) <= 1e-6,
                     "free-space halfspace normals must have unit norm")
            _number(halfspace["offset_m"], f"{name}.offset_m")
        reliability = _number(
            free_space["reliability"],
            f"free_space_observations[{index}].reliability",
        )
        _require(0.0 <= reliability <= 1.0,
                 "free-space reliability must be within [0, 1]")
        _hex64(free_space["support_sha256"],
               f"free_space_observations[{index}].support_sha256")

    visibility = packet["visibility_observations"]
    _require(type(visibility) is list, "visibility_observations must be a list")
    previous_visibility_time = -math.inf
    for index, item in enumerate(visibility):
        name = f"visibility_observations[{index}]"
        _require(type(item) is dict, f"{name} must be an object")
        _exact_keys(item, VISIBILITY_KEYS, name)
        expected_id = f"visibility:{index:04d}"
        _require(
            type(item["visibility_id"]) is str
            and OPAQUE_VISIBILITY.fullmatch(item["visibility_id"]) is not None
            and item["visibility_id"] == expected_id,
            "visibility IDs must be packet-local opaque ordinals",
        )
        item_time = _number(item["time_s"], f"{name}.time_s", minimum=0.0)
        _require(previous_visibility_time <= item_time <= decision_time,
                 "visibility times must be ordered and not enter the future")
        previous_visibility_time = item_time
        halfspaces = item["halfspaces_world"]
        _require(type(halfspaces) is list and len(halfspaces) == 6,
                 "visibility frustum must contain exactly six halfspaces")
        for plane_index, halfspace in enumerate(halfspaces):
            plane_name = f"{name}.halfspaces_world[{plane_index}]"
            _require(type(halfspace) is dict, f"{plane_name} must be an object")
            _exact_keys(halfspace, HALFSPACE_KEYS, plane_name)
            normal = _vector(
                halfspace["normal"], f"{plane_name}.normal", length=3,
            )
            norm = math.sqrt(sum(value * value for value in normal))
            _require(abs(norm - 1.0) <= 1e-6,
                     "visibility halfspace normals must have unit norm")
            _number(halfspace["offset_m"], f"{plane_name}.offset_m")
        reliability = _number(item["reliability"], f"{name}.reliability")
        _require(0.0 <= reliability <= 1.0,
                 "visibility reliability must be within [0, 1]")
        _hex64(item["support_sha256"], f"{name}.support_sha256")

    prior_ref = packet["prior_memory_ref"]
    _require(type(prior_ref) is dict, "prior_memory_ref must be an object")
    _exact_keys(prior_ref, PRIOR_REF_KEYS, "prior_memory_ref")
    _require(type(prior_ref["graph_version"]) is str and prior_ref["graph_version"],
             "prior_memory_ref.graph_version must be nonempty")
    _hex64(prior_ref["graph_sha256"], "prior_memory_ref.graph_sha256")

    constants = packet["public_constants"]
    _require(type(constants) is dict, "public_constants must be an object")
    _exact_keys(constants, PUBLIC_CONSTANT_KEYS, "public_constants")
    for key, value in constants.items():
        _identifier(value, f"public_constants.{key}")

    _reject_forbidden_keys(packet)
    return clone_json(dict(packet))


def build_adapter_input(
    packet: Mapping[str, Any], prior_memory: Mapping[str, Any],
) -> AdapterInput:
    """Strip audit identity and artifact references from the deployable input."""

    public = validate_observation_packet(packet)
    memory = clone_json(dict(prior_memory))
    digest = _public_memory_digest(memory)
    _require(public["prior_memory_ref"]["graph_sha256"] == digest,
             "prior memory digest does not match the public reference")
    _require(public["prior_memory_ref"]["graph_version"] == memory["graph_version"],
             "prior memory version does not match the public reference")
    return {
        "decision_time_s": float(public["decision_time_s"]),
        "camera_pose": clone_json(public["camera_pose"]),
        "robot_state": clone_json(public["robot_state"]),
        "past_actions": clone_json(public["past_actions"]),
        "region_observations": clone_json(public["region_observations"]),
        "relation_observations": clone_json(public["relation_observations"]),
        "free_space_observations": clone_json(
            public["free_space_observations"]
        ),
        "visibility_observations": clone_json(
            public["visibility_observations"]
        ),
        "prior_memory": memory,
        "public_constants": clone_json(public["public_constants"]),
    }


def _validate_derivation_pointer(pointer: Any, roots: set[str], name: str) -> None:
    _require(type(pointer) is str and pointer.startswith("/"),
             f"{name} must be a JSON pointer")
    lowered = pointer.lower()
    _require(not any(token in lowered for token in FORBIDDEN_DERIVATION_TOKENS),
             f"{name} contains a forbidden information source")
    _require(any(pointer == root or pointer.startswith(root + "/") for root in roots),
             f"{name} is outside the allowed source roots")


def _candidate_catalog_payload(catalog: Mapping[str, Any]) -> dict[str, Any]:
    payload = clone_json(dict(catalog))
    payload.pop("catalog_sha256", None)
    return payload


def validate_candidate_catalog(
    catalog: Mapping[str, Any], *, packet: Mapping[str, Any] | None = None,
    prior_memory: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a public-only candidate seal without asking which slot is correct."""

    expected = {
        "schema_version", "public_sha256", "prior_memory_sha256", "generator_id",
        "derivations", "capacity_audit", "capacity_summary", "candidates",
        "catalog_sha256",
    }
    _exact_keys(catalog, expected, "candidate catalog")
    _require(catalog["schema_version"] == CANDIDATE_SCHEMA,
             "wrong candidate catalog schema")
    _hex64(catalog["public_sha256"], "candidate public_sha256")
    _hex64(catalog["prior_memory_sha256"], "candidate prior_memory_sha256")
    _identifier(catalog["generator_id"], "candidate generator_id")
    _hex64(catalog["catalog_sha256"], "catalog_sha256")

    derivations = catalog["derivations"]
    _require(type(derivations) is list and derivations,
             "candidate derivations must be a nonempty list")
    names: list[str] = []
    for index, item in enumerate(derivations):
        _require(type(item) is dict, f"derivations[{index}] must be an object")
        _exact_keys(item, {"name", "public_fields", "prior_memory_fields"},
                    f"derivations[{index}]")
        names.append(_identifier(item["name"], f"derivations[{index}].name"))
        _require(type(item["public_fields"]) is list and item["public_fields"],
                 "each derivation must name at least one public field")
        _require(type(item["prior_memory_fields"]) is list,
                 "prior_memory_fields must be a list")
        for pointer in item["public_fields"]:
            _validate_derivation_pointer(pointer, PUBLIC_DERIVATION_ROOTS,
                                         "public derivation pointer")
        for pointer in item["prior_memory_fields"]:
            _validate_derivation_pointer(pointer, MEMORY_DERIVATION_ROOTS,
                                         "memory derivation pointer")
    _require(len(names) == len(set(names)), "candidate derivation names must be unique")

    capacity_rows = catalog["capacity_audit"]
    _require(type(capacity_rows) is list and capacity_rows,
             "candidate capacity_audit must be a nonempty list")
    bucket_ids: list[str] = []
    retained_by_bucket: dict[str, int] = {}
    for index, row in enumerate(capacity_rows):
        _require(type(row) is dict, f"capacity_audit[{index}] must be an object")
        _exact_keys(row, {
            "bucket_id", "template", "scope", "capacity",
            "pre_cap_candidate_count", "pre_cap_group_count",
            "retained_candidate_count", "retained_group_count",
            "oversized_group_count", "ambiguity_guard_rejected_group_count",
            "total_incident_guard_rejected_node_count",
            "cutoff_group_count", "cutoff_candidate_count",
            "unused_capacity", "current_positive_blocked_node_count",
            "endpoint_pair_evaluation_count",
            "minimum_retained_priority",
            "minimum_retained_priority_group_count",
        }, f"capacity_audit[{index}]")
        for key in ("bucket_id", "template", "scope"):
            _require(type(row[key]) is str and bool(row[key]),
                     f"capacity_audit[{index}].{key} must be nonempty")
        bucket_id = str(row["bucket_id"])
        _require(bucket_id == f"{row['template']}|{row['scope']}",
                 "candidate capacity bucket ID must bind template and scope")
        bucket_ids.append(bucket_id)
        counts: dict[str, int] = {}
        for key in (
            "capacity", "pre_cap_candidate_count", "pre_cap_group_count",
            "retained_candidate_count", "retained_group_count",
            "oversized_group_count",
            "ambiguity_guard_rejected_group_count",
            "total_incident_guard_rejected_node_count",
            "cutoff_group_count", "cutoff_candidate_count",
            "unused_capacity", "current_positive_blocked_node_count",
            "endpoint_pair_evaluation_count",
            "minimum_retained_priority_group_count",
        ):
            value = row[key]
            _require(type(value) is int and value >= 0,
                     f"capacity_audit[{index}].{key} must be a non-negative integer")
            counts[key] = value
        _require(counts["capacity"] > 0, "candidate bucket capacity must be positive")
        _require(counts["retained_candidate_count"] <= counts["capacity"],
                 "retained candidates exceed bucket capacity")
        _require(
            counts["unused_capacity"]
            == counts["capacity"] - counts["retained_candidate_count"],
            "candidate bucket unused capacity is inconsistent",
        )
        _require(
            counts["retained_candidate_count"] <= counts["pre_cap_candidate_count"],
            "retained candidates exceed their pre-cap count",
        )
        _require(counts["retained_group_count"] <= counts["pre_cap_group_count"],
                 "retained groups exceed their pre-cap count")
        _require(counts["oversized_group_count"] <= counts["pre_cap_group_count"],
                 "oversized groups exceed their pre-cap count")
        _require(
            counts["ambiguity_guard_rejected_group_count"]
            <= counts["pre_cap_group_count"],
            "ambiguity-guarded groups exceed their pre-cap count",
        )
        minimum_priority = row["minimum_retained_priority"]
        _require(
            minimum_priority is None
            or _is_number(minimum_priority),
            "minimum_retained_priority must be null or finite",
        )
        if counts["retained_group_count"] == 0:
            _require(minimum_priority is None,
                     "empty candidate bucket must have null minimum priority")
            _require(counts["minimum_retained_priority_group_count"] == 0,
                     "empty candidate bucket must have zero minimum-priority groups")
        else:
            _require(minimum_priority is not None,
                     "nonempty candidate bucket needs a minimum priority")
            _require(
                0 < counts["minimum_retained_priority_group_count"]
                <= counts["retained_group_count"],
                "minimum-priority group count is inconsistent",
            )
        retained_by_bucket[bucket_id] = counts["retained_candidate_count"]
    _require(len(bucket_ids) == len(set(bucket_ids)),
             "candidate capacity bucket IDs must be unique")

    capacity_summary = catalog["capacity_summary"]
    _require(type(capacity_summary) is dict,
             "candidate capacity_summary must be an object")
    _exact_keys(capacity_summary, {
        "bucket_count", "total_capacity", "total_pre_cap_candidate_count",
        "total_retained_candidate_count", "total_truncated_candidate_count",
    }, "candidate capacity_summary")
    expected_summary = {
        "bucket_count": len(capacity_rows),
        "total_capacity": sum(row["capacity"] for row in capacity_rows),
        "total_pre_cap_candidate_count": sum(
            row["pre_cap_candidate_count"] for row in capacity_rows
        ),
        "total_retained_candidate_count": sum(
            row["retained_candidate_count"] for row in capacity_rows
        ),
        "total_truncated_candidate_count": sum(
            row["pre_cap_candidate_count"] - row["retained_candidate_count"]
            for row in capacity_rows
        ),
    }
    _require(capacity_summary == expected_summary,
             "candidate capacity_summary does not match its buckets")

    candidates = catalog["candidates"]
    _require(type(candidates) is list and candidates,
             "candidate catalog must be nonempty")
    for index, item in enumerate(candidates):
        _require(type(item) is dict, f"candidates[{index}] must be an object")
        _exact_keys(item, {
            "candidate_id", "program", "program_sha256",
            "online_evidence", "online_evidence_sha256", "enumeration",
        },
                    f"candidates[{index}]")
        expected_id = f"candidate:{index:04d}"
        _require(
            type(item["candidate_id"]) is str
            and OPAQUE_CANDIDATE.fullmatch(item["candidate_id"]) is not None
            and item["candidate_id"] == expected_id,
            "candidate IDs must be catalog-local opaque ordinals",
        )
        _require(type(item["program"]) is dict, "candidate program must be an object")
        _reject_forbidden_keys(item["program"], location=f"$.candidates[{index}].program")
        _require(item["program"].get("proposer") in {"deterministic", "learned"},
                 "an online candidate must declare deterministic or learned proposer")
        expected_program_hash = canonical_sha256(item["program"])
        _require(item["program_sha256"] == expected_program_hash,
                 "candidate program digest mismatch")
        _require(type(item["online_evidence"]) is dict,
                 "candidate online_evidence must be an object")
        _reject_forbidden_keys(
            item["online_evidence"],
            location=f"$.candidates[{index}].online_evidence",
        )
        expected_evidence_hash = canonical_sha256(item["online_evidence"])
        _require(item["online_evidence_sha256"] == expected_evidence_hash,
                 "candidate online evidence digest mismatch")
        enumeration = item["enumeration"]
        _require(type(enumeration) is dict,
                 "candidate enumeration must be an object")
        _exact_keys(enumeration, {
            "bucket_id", "enumeration_priority", "priority_components",
        }, f"candidates[{index}].enumeration")
        _require(enumeration["bucket_id"] in retained_by_bucket,
                 "candidate enumeration names an unknown capacity bucket")
        _number(enumeration["enumeration_priority"],
                "candidate enumeration_priority")
        components = enumeration["priority_components"]
        _require(type(components) is dict,
                 "candidate priority_components must be an object")
        for name, value in components.items():
            _identifier(name, "candidate priority component name")
            _number(value, f"candidate priority component {name}")

    observed_retained = {
        bucket_id: sum(
            item["enumeration"]["bucket_id"] == bucket_id
            for item in candidates
        )
        for bucket_id in bucket_ids
    }
    _require(observed_retained == retained_by_bucket,
             "candidate capacity audit retained counts do not match the catalog")

    expected_hash = canonical_sha256(_candidate_catalog_payload(catalog))
    _require(catalog["catalog_sha256"] == expected_hash,
             "candidate catalog digest mismatch")
    if packet is not None:
        _require(catalog["public_sha256"] == canonical_sha256(
            validate_observation_packet(packet)
        ), "candidate catalog is bound to a different public packet")
    if prior_memory is not None:
        _require(catalog["prior_memory_sha256"] == _public_memory_digest(prior_memory),
                 "candidate catalog is bound to a different prior memory")
    return clone_json(dict(catalog))


def seal_candidate_catalog(
    packet: Mapping[str, Any], prior_memory: Mapping[str, Any],
    *, generator_id: str, derivations: list[Mapping[str, Any]],
    programs: list[Mapping[str, Any]],
    online_evidence: list[Mapping[str, Any]] | None = None,
    enumeration_audits: list[Mapping[str, Any]] | None = None,
    capacity_audit: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Seal candidates from public values; no private argument exists by design."""

    public = validate_observation_packet(packet)
    memory_digest = _public_memory_digest(prior_memory)
    evidence_rows = online_evidence or [{} for _ in programs]
    _require(len(evidence_rows) == len(programs),
             "online_evidence must have one object per program")
    enumeration_rows = enumeration_audits or [
        {
            "bucket_id": "EXTERNAL|global",
            "enumeration_priority": 0.0,
            "priority_components": {},
        }
        for _ in programs
    ]
    _require(len(enumeration_rows) == len(programs),
             "enumeration_audits must have one object per program")
    capacity_rows = capacity_audit or [{
        "bucket_id": "EXTERNAL|global",
        "template": "EXTERNAL",
        "scope": "global",
        "capacity": max(1, len(programs)),
        "pre_cap_candidate_count": len(programs),
        "pre_cap_group_count": len(programs),
        "retained_candidate_count": len(programs),
        "retained_group_count": len(programs),
        "oversized_group_count": 0,
        "ambiguity_guard_rejected_group_count": 0,
        "total_incident_guard_rejected_node_count": 0,
        "cutoff_group_count": 0,
        "cutoff_candidate_count": 0,
        "unused_capacity": 0,
        "current_positive_blocked_node_count": 0,
        "endpoint_pair_evaluation_count": 0,
        "minimum_retained_priority": 0.0 if programs else None,
        "minimum_retained_priority_group_count": len(programs),
    }]
    candidates = [
        {
            "candidate_id": f"candidate:{index:04d}",
            "program": clone_json(dict(program)),
            "program_sha256": canonical_sha256(program),
            "online_evidence": clone_json(dict(evidence_rows[index])),
            "online_evidence_sha256": canonical_sha256(evidence_rows[index]),
            "enumeration": clone_json(dict(enumeration_rows[index])),
        }
        for index, program in enumerate(programs)
    ]
    catalog: dict[str, Any] = {
        "schema_version": CANDIDATE_SCHEMA,
        "public_sha256": canonical_sha256(public),
        "prior_memory_sha256": memory_digest,
        "generator_id": generator_id,
        "derivations": clone_json(derivations),
        "capacity_audit": clone_json(capacity_rows),
        "capacity_summary": {
            "bucket_count": len(capacity_rows),
            "total_capacity": sum(row["capacity"] for row in capacity_rows),
            "total_pre_cap_candidate_count": sum(
                row["pre_cap_candidate_count"] for row in capacity_rows
            ),
            "total_retained_candidate_count": sum(
                row["retained_candidate_count"] for row in capacity_rows
            ),
            "total_truncated_candidate_count": sum(
                row["pre_cap_candidate_count"] - row["retained_candidate_count"]
                for row in capacity_rows
            ),
        },
        "candidates": candidates,
    }
    catalog["catalog_sha256"] = canonical_sha256(catalog)
    return validate_candidate_catalog(catalog, packet=public, prior_memory=prior_memory)


def _teacher_payload(targets: Mapping[str, Any]) -> dict[str, Any]:
    payload = clone_json(dict(targets))
    payload.pop("teacher_sha256", None)
    return payload


def validate_teacher_targets(
    targets: Mapping[str, Any], catalog: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind teacher values to existing candidates without permitting catalog edits."""

    candidate_catalog = validate_candidate_catalog(catalog)
    expected = {
        "schema_version", "catalog_sha256", "teacher_id", "targets",
        "teacher_sha256",
    }
    _exact_keys(targets, expected, "teacher targets")
    _require(targets["schema_version"] == TEACHER_SCHEMA,
             "wrong teacher target schema")
    _require(targets["catalog_sha256"] == candidate_catalog["catalog_sha256"],
             "teacher targets bind a different candidate catalog")
    _identifier(targets["teacher_id"], "teacher_id")
    rows = targets["targets"]
    _require(type(rows) is list, "teacher targets must be a list")
    expected_ids = [item["candidate_id"] for item in candidate_catalog["candidates"]]
    observed_ids: list[str] = []
    probabilities: list[float] = []
    for index, row in enumerate(rows):
        _require(type(row) is dict, f"teacher targets[{index}] must be an object")
        _exact_keys(row, {"candidate_id", "score", "probability"},
                    f"teacher targets[{index}]")
        observed_ids.append(str(row["candidate_id"]))
        _number(row["score"], f"teacher targets[{index}].score")
        probability = _number(row["probability"],
                              f"teacher targets[{index}].probability", minimum=0.0)
        _require(probability <= 1.0, "teacher probability must be within [0, 1]")
        probabilities.append(probability)
    _require(observed_ids == expected_ids,
             "teacher targets must preserve the exact candidate IDs and order")
    _require(abs(sum(probabilities) - 1.0) <= 1e-6,
             "teacher probabilities must sum to one")
    _hex64(targets["teacher_sha256"], "teacher_sha256")
    _require(targets["teacher_sha256"] == _raw_canonical_sha256(
        _teacher_payload(targets)
    ),
             "teacher target digest mismatch")
    return clone_json(dict(targets))


def seal_teacher_targets(
    catalog: Mapping[str, Any], *, teacher_id: str,
    scores: list[float], probabilities: list[float],
) -> dict[str, Any]:
    """Create labels for the already-sealed catalog and no other candidates."""

    candidate_catalog = validate_candidate_catalog(catalog)
    candidate_ids = [item["candidate_id"] for item in candidate_catalog["candidates"]]
    _require(len(scores) == len(candidate_ids) == len(probabilities),
             "teacher values must have one row per sealed candidate")
    record: dict[str, Any] = {
        "schema_version": TEACHER_SCHEMA,
        "catalog_sha256": candidate_catalog["catalog_sha256"],
        "teacher_id": teacher_id,
        "targets": [
            {
                "candidate_id": candidate_id,
                "score": float(score),
                "probability": float(probability),
            }
            for candidate_id, score, probability in zip(
                candidate_ids, scores, probabilities, strict=True,
            )
        ],
    }
    record["teacher_sha256"] = _raw_canonical_sha256(record)
    return validate_teacher_targets(record, candidate_catalog)


def validate_memory_update_result(
    result: Mapping[str, Any], *, expected_method_id: str | None = None,
    expected_pre_memory_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate structural output while leaving semantic equivalence undecided."""

    expected = {
        "schema_version", "method_id", "pre_memory_sha256", "post_memory",
        "post_memory_sha256", "normalized_delta", "confidence", "runtime_ms",
        "diagnostics",
    }
    _exact_keys(result, expected, "memory update result")
    _require(result["schema_version"] == RESULT_SCHEMA, "wrong result schema")
    method_id = _identifier(result["method_id"], "method_id")
    if expected_method_id is not None:
        _require(method_id == expected_method_id, "adapter returned the wrong method_id")
    pre_digest = _hex64(result["pre_memory_sha256"], "pre_memory_sha256")
    if expected_pre_memory_sha256 is not None:
        _require(pre_digest == expected_pre_memory_sha256,
                 "result is bound to a different prior memory")
    post_memory = clone_json(dict(result["post_memory"]))
    post_digest = _public_memory_digest(post_memory)
    _require(result["post_memory_sha256"] == post_digest,
             "post memory digest mismatch")

    delta = result["normalized_delta"]
    _require(type(delta) is dict, "normalized_delta must be an object")
    _exact_keys(delta, NORMALIZED_DELTA_KEYS, "normalized_delta")
    template = delta["declared_template"]
    _require(template is None or template in DECLARED_TEMPLATES,
             "declared_template is not a registered VSMT template")
    for key in NORMALIZED_DELTA_KEYS - {"declared_template"}:
        values = delta[key]
        _require(type(values) is list and all(type(item) is str and item for item in values),
                 f"normalized_delta.{key} must be a list of nonempty IDs")
        _require(len(values) == len(set(values)),
                 f"normalized_delta.{key} must not contain duplicates")

    confidence = _number(result["confidence"], "confidence")
    _require(0.0 <= confidence <= 1.0, "confidence must be within [0, 1]")
    _number(result["runtime_ms"], "runtime_ms", minimum=0.0)
    _require(type(result["diagnostics"]) is dict, "diagnostics must be an object")
    _reject_forbidden_keys(result["diagnostics"], location="$.diagnostics")
    return clone_json(dict(result))


def audit_memory_update_result(
    prior_memory: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    protected_node_ids: set[str] | frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Recompute graph changes for every method without imposing its mechanism."""

    before = clone_json(dict(prior_memory))
    validate_graph(before, verify_hash=True)
    validated = validate_memory_update_result(result)
    _require(
        validated["pre_memory_sha256"] == before["graph_hash"],
        "common audit result is bound to a different prior memory",
    )
    after = validated["post_memory"]
    before_nodes = {node["node_version_id"]: node for node in before["nodes"]}
    after_nodes = {node["node_version_id"]: node for node in after["nodes"]}
    before_edges = {edge["edge_version_id"]: edge for edge in before["edges"]}
    after_edges = {edge["edge_version_id"]: edge for edge in after["edges"]}

    created_nodes = sorted(set(after_nodes) - set(before_nodes))
    created_edges = sorted(set(after_edges) - set(before_edges))
    missing_nodes = sorted(set(before_nodes) - set(after_nodes))
    missing_edges = sorted(set(before_edges) - set(after_edges))
    closed_nodes = sorted(
        version_id for version_id, node in after_nodes.items()
        if node.get("valid_to") is not None
        and (
            version_id not in before_nodes
            or before_nodes[version_id].get("valid_to") is None
        )
    )
    closed_edges = sorted(
        version_id for version_id, edge in after_edges.items()
        if edge.get("valid_to") is not None
        and (
            version_id not in before_edges
            or before_edges[version_id].get("valid_to") is None
        )
    )
    recomputed = {
        "created_node_version_ids": created_nodes,
        "closed_node_version_ids": closed_nodes,
        "created_edge_version_ids": created_edges,
        "closed_edge_version_ids": closed_edges,
    }
    declared = validated["normalized_delta"]
    delta_matches = all(
        set(declared[key]) == set(values) for key, values in recomputed.items()
    )

    mutated_nodes = sorted(
        version_id for version_id in set(before_nodes) & set(after_nodes)
        if canonical_sha256(before_nodes[version_id])
        != canonical_sha256(after_nodes[version_id])
    )
    mutated_edges = sorted(
        version_id for version_id in set(before_edges) & set(after_edges)
        if canonical_sha256(before_edges[version_id])
        != canonical_sha256(after_edges[version_id])
    )
    declared_template = validated["normalized_delta"]["declared_template"]
    if declared_template is not None:
        observed_templates = {str(declared_template)}
    else:
        tail = after.get("transaction_log", [])[-1:]
        entry = tail[0] if tail else None
        observed_templates = (
            {str(item) for item in entry.get("observed_templates", [])}
            if type(entry) is dict else set()
        )
    # 白话：只有结果声明了不止一个模板时，允许的"已声明就地变化"字段才是这些
    # 模板的并集，比逐版本判定宽。这里把这一放宽如实标出来，不让它默默成立。
    semantic_allowance_templates = sorted(
        template for template in observed_templates
        if SEMANTIC_IN_PLACE_FIELDS_BY_TEMPLATE.get(template)
    )
    semantic_allowance_is_result_level = len(observed_templates) > 1

    def classify_mutation(
        kind: str, version_id: str,
        old: Mapping[str, Any], new: Mapping[str, Any],
    ) -> dict[str, Any]:
        fields = sorted(
            key for key in set(old) | set(new) if old.get(key) != new.get(key)
        )
        remaining = set(fields)
        closure = (
            old.get("valid_to") is None
            and type(new.get("valid_to")) is int
        )
        if closure:
            remaining.discard("valid_to")

        append_fields: list[str] = []
        for field in ("evidence_refs", "provenance"):
            if field not in remaining:
                continue
            old_values = old.get(field)
            new_values = new.get(field)
            if (
                old.get("valid_to") is None
                and type(old_values) is list
                and type(new_values) is list
                and new_values[:len(old_values)] == old_values
                and len(new_values) >= len(old_values)
            ):
                append_fields.append(field)
                remaining.discard(field)

        allowed_semantic = frozenset().union(*(
            SEMANTIC_IN_PLACE_FIELDS_BY_TEMPLATE.get(template, frozenset())
            for template in observed_templates
        ))
        semantic_fields = sorted(remaining & set(allowed_semantic))
        if semantic_fields and old.get("valid_to") is not None:
            remaining.update(semantic_fields)
            semantic_fields = []
        remaining -= set(semantic_fields)
        if remaining:
            classification = "undeclared_destructive_rewrite"
        elif semantic_fields:
            classification = "declared_semantic_transition"
        elif append_fields:
            classification = "append_only_evidence_or_provenance"
        elif closure:
            classification = "closure_only"
        else:
            classification = "undeclared_destructive_rewrite"
        return {
            "record_kind": kind,
            "version_id": version_id,
            "classification": classification,
            "changed_fields": fields,
            "append_only_fields": append_fields,
            "declared_semantic_fields": semantic_fields,
        }

    mutation_classifications = [
        classify_mutation(
            "node", version_id, before_nodes[version_id], after_nodes[version_id],
        )
        for version_id in mutated_nodes
    ] + [
        classify_mutation(
            "edge", version_id, before_edges[version_id], after_edges[version_id],
        )
        for version_id in mutated_edges
    ]
    destructive_rewrites = sorted(
        item["version_id"] for item in mutation_classifications
        if item["classification"] == "undeclared_destructive_rewrite"
    )
    semantic_transitions = sorted(
        item["version_id"] for item in mutation_classifications
        if item["classification"] == "declared_semantic_transition"
    )
    shape_violations: list[str] = []
    created_node_records = [after_nodes[version_id] for version_id in created_nodes]
    alias_versions = [
        str(node["node_version_id"]) for node in created_node_records
        if node.get("lifecycle") == "alias"
    ]
    terminal_versions = [
        str(node["node_version_id"]) for node in created_node_records
        if node.get("lifecycle") == "retracted"
        and node.get("valid_to") == node.get("valid_from")
    ]
    if alias_versions and "MERGE" not in observed_templates:
        shape_violations.append("alias_successor_without_merge")
    if terminal_versions and not observed_templates & {"RETRACT", "SPLIT", "REPLACE"}:
        shape_violations.append("terminal_retraction_without_retracting_template")
    if observed_templates == {"NOOP"} and any((
        created_nodes, created_edges, closed_nodes, closed_edges,
        mutated_nodes, mutated_edges,
    )):
        shape_violations.append("noop_changed_graph")
    if observed_templates == {"BIND"} and (
        created_edges or closed_edges
        or any(
            node.get("lifecycle") == "alias"
            or node.get("lifecycle") == "retracted"
            for node in created_node_records
        )
    ):
        shape_violations.append("bind_exceeded_version_successor_or_append_scope")
    if observed_templates == {"RELINK"} and (created_nodes or closed_nodes):
        shape_violations.append("relink_changed_node_versions")
    if observed_templates == {"BIRTH"} and (closed_nodes or closed_edges):
        shape_violations.append("birth_closed_preexisting_versions")
    template_diff_allowlist_passed = (
        not destructive_rewrites and not shape_violations
        and not (semantic_transitions and "MERGE" not in observed_templates)
    )
    protected = set(protected_node_ids)
    protected_node_changes = sorted(
        node_id for node_id in protected
        if [node for node in before["nodes"] if node["node_id"] == node_id]
        != [node for node in after["nodes"] if node["node_id"] == node_id]
    )

    def open_topology(graph: Mapping[str, Any], node_id: str) -> list[list[str]]:
        return sorted([
            [
                str(edge["source"]), str(edge["target"]),
                str(edge["relation"]), str(edge["frame"]),
            ]
            for edge in graph["edges"]
            if edge.get("valid_to") is None
            and node_id in {edge["source"], edge["target"]}
        ])

    protected_topology_changes = sorted(
        node_id for node_id in protected
        if open_topology(before, node_id) != open_topology(after, node_id)
    )
    semantic_cost = semantic_edit_accounting(before, validated)
    return {
        "schema_version": "vsmt-common-post-update-audit-v2",
        "structural_validation_passed": True,
        "history_preserved": not missing_nodes and not missing_edges,
        "declared_delta_matches_graph_diff": delta_matches,
        "recomputed_delta": recomputed,
        "missing_preexisting_node_version_ids": missing_nodes,
        "missing_preexisting_edge_version_ids": missing_edges,
        "preexisting_node_version_mutations": mutated_nodes,
        "preexisting_edge_version_mutations": mutated_edges,
        "preexisting_version_mutation_classifications": (
            mutation_classifications
        ),
        "undeclared_destructive_rewrite_version_ids": destructive_rewrites,
        "declared_semantic_transition_version_ids": semantic_transitions,
        "semantic_allowance_templates": semantic_allowance_templates,
        "semantic_allowance_is_result_level": (
            semantic_allowance_is_result_level
        ),
        "template_diff_allowlist_passed": template_diff_allowlist_passed,
        "template_diff_allowlist_violations": shape_violations,
        "protected_node_state_change_ids": protected_node_changes,
        "protected_incident_topology_change_ids": protected_topology_changes,
        "semantic_edit_accounting": semantic_cost,
    }


def semantic_edit_accounting(
    prior_memory: Mapping[str, Any], result: Mapping[str, Any],
) -> dict[str, Any]:
    """Count high-level atoms and canonical relation facts, not version churn."""

    before = clone_json(dict(prior_memory))
    validated = validate_memory_update_result(result)
    after = validated["post_memory"]
    declared = validated["normalized_delta"]["declared_template"]
    instances: list[str]
    if declared is not None:
        instances = [str(declared)]
    else:
        tail = after.get("transaction_log", [])[-1:]
        entry = tail[0] if tail else None
        if type(entry) is dict and type(entry.get("observed_template_instances")) is list:
            instances = [str(item) for item in entry["observed_template_instances"]]
        elif type(entry) is dict and type(entry.get("observed_templates")) is list:
            instances = [str(item) for item in entry["observed_templates"]]
        else:
            instances = []
    atom_count = sum(
        0 if template == "NOOP" else 2 if template == "REPLACE" else 1
        for template in instances
    )

    canonical: dict[str, str] = {}
    for node in after["nodes"]:
        if (
            node.get("valid_to") is None
            and node.get("lifecycle") == "alias"
            and type(node.get("canonical_id")) is str
        ):
            canonical[str(node["node_id"])] = str(node["canonical_id"])

    def resolve(node_id: str) -> str:
        seen: set[str] = set()
        current = node_id
        while current in canonical and current not in seen:
            seen.add(current)
            current = canonical[current]
        return current

    def facts(graph: Mapping[str, Any]) -> set[tuple[str, str, str, str]]:
        return {
            (
                resolve(str(edge["source"])),
                resolve(str(edge["target"])),
                str(edge["relation"]),
                str(edge["frame"]),
            )
            for edge in graph["edges"]
            if edge.get("valid_to") is None
            and resolve(str(edge["source"])) != resolve(str(edge["target"]))
        }

    before_facts = facts(before)
    after_facts = facts(after)
    added = sorted(after_facts - before_facts)
    removed = sorted(before_facts - after_facts)
    delta = validated["normalized_delta"]
    raw_edge_churn = (
        len(delta["created_edge_version_ids"])
        + len(delta["closed_edge_version_ids"])
    )
    return {
        "schema_version": "vsmt-semantic-edit-accounting-v1",
        "high_level_template_instances": instances,
        "high_level_atom_count": atom_count,
        "new_persistent_semantic_relation_facts": [list(item) for item in added],
        "removed_persistent_semantic_relation_facts": [list(item) for item in removed],
        "semantic_relation_growth_count": len(added),
        "raw_edge_version_churn": raw_edge_churn,
        "canonical_reanchor_churn_is_atom_cost": False,
    }


def run_adapter(
    adapter: MemoryUpdateAdapter, packet: Mapping[str, Any],
    prior_memory: Mapping[str, Any],
) -> dict[str, Any]:
    """Run one adapter without making any private value reachable."""

    _require(isinstance(adapter, MemoryUpdateAdapter),
             "adapter does not implement MemoryUpdateAdapter")
    model_input = build_adapter_input(packet, prior_memory)
    adapter_input = clone_json(model_input)
    before = canonical_sha256(adapter_input)
    pre_digest = _graph_digest(prior_memory)
    result = adapter.update(adapter_input)
    _require(canonical_sha256(adapter_input) == before,
             "adapter input mutated during inference")
    validated = validate_memory_update_result(
        result,
        expected_method_id=adapter.method_id,
        expected_pre_memory_sha256=pre_digest,
    )
    _require(
        "common_post_update_audit" not in validated["diagnostics"],
        "adapter may not supply the common post-update audit",
    )
    protected_place_ids = frozenset(
        str(node["node_id"])
        for node in prior_memory["nodes"]
        if node.get("valid_to") is None
        and node.get("node_type") == "place"
        and type(node.get("vsmt_observation_state")) is dict
        and node["vsmt_observation_state"].get("place_scaffold_key") is not None
    )
    audit = audit_memory_update_result(
        prior_memory, validated, protected_node_ids=protected_place_ids,
    )
    _require(
        audit["declared_delta_matches_graph_diff"],
        "normalized_delta does not match the actual graph version difference",
    )
    _require(
        audit["history_preserved"],
        "adapter physically removed preexisting version history",
    )
    _require(
        audit["template_diff_allowlist_passed"],
        "adapter performed an undeclared destructive version rewrite",
    )
    _require(
        not audit["protected_node_state_change_ids"],
        "adapter changed the online protected place scaffold",
    )
    validated["diagnostics"]["common_post_update_audit"] = audit
    return validate_memory_update_result(
        validated,
        expected_method_id=adapter.method_id,
        expected_pre_memory_sha256=pre_digest,
    )


def _private_payload(record: Mapping[str, Any]) -> dict[str, Any]:
    payload = clone_json(dict(record))
    payload.pop("private_sha256", None)
    return payload


def validate_private_evaluation(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate private evaluation data through an explicitly separate API."""

    expected = {
        "schema_version", "sample_id_hash", "public_sha256", "reference_memory",
        "reference_transaction_equivalence", "future_observation_sha256",
        "simulator_identity_map", "semantic_case_id", "private_sha256",
    }
    _exact_keys(record, expected, "private evaluation")
    _require(record["schema_version"] == PRIVATE_SCHEMA, "wrong private schema")
    _hex64(record["sample_id_hash"], "private sample_id_hash")
    _hex64(record["public_sha256"], "private public_sha256")
    _graph_digest(record["reference_memory"])
    equivalence = record["reference_transaction_equivalence"]
    _require(type(equivalence) is list and all(
        type(group) is list and all(type(item) is str and item for item in group)
        for group in equivalence
    ), "reference_transaction_equivalence must be a list of ID lists")
    futures = record["future_observation_sha256"]
    _require(type(futures) is list, "future_observation_sha256 must be a list")
    for index, digest in enumerate(futures):
        _hex64(digest, f"future_observation_sha256[{index}]")
    identity_map = record["simulator_identity_map"]
    _require(type(identity_map) is dict and all(
        type(key) is str and type(value) is str for key, value in identity_map.items()
    ), "simulator_identity_map must be a string mapping")
    _identifier(record["semantic_case_id"], "semantic_case_id")
    _hex64(record["private_sha256"], "private_sha256")
    _require(record["private_sha256"] == _raw_canonical_sha256(
        _private_payload(record)
    ), "private evaluation digest mismatch")
    return clone_json(dict(record))


def seal_private_evaluation(record: Mapping[str, Any]) -> dict[str, Any]:
    """Seal private data without passing it through public-only hash guards."""

    payload = clone_json(dict(record))
    _require("private_sha256" not in payload,
             "unsealed private evaluation must not contain private_sha256")
    payload["private_sha256"] = _raw_canonical_sha256(payload)
    return validate_private_evaluation(payload)


def validate_private_mutation_invariance(records: list[Mapping[str, Any]]) -> None:
    """Require public online artifacts to stay fixed across private mutations."""

    _require(len(records) >= 2, "private mutation audit needs at least two variants")
    expected_keys = {
        "schema_version", "public_sha256", "private_sha256",
        "candidate_catalog_sha256", "adapter_input_sha256", "logits_sha256",
    }
    public_values: dict[str, set[str]] = {
        key: set() for key in (
            "public_sha256", "candidate_catalog_sha256",
            "adapter_input_sha256", "logits_sha256",
        )
    }
    private_values: set[str] = set()
    for index, record in enumerate(records):
        _exact_keys(record, expected_keys, f"invariance record[{index}]")
        _require(record["schema_version"] == INVARIANCE_SCHEMA,
                 "wrong private mutation invariance schema")
        for key in public_values:
            public_values[key].add(_hex64(record[key], f"record[{index}].{key}"))
        private_values.add(_hex64(record["private_sha256"],
                                  f"record[{index}].private_sha256"))
    _require(len(private_values) == len(records),
             "private mutation variants must have distinct private digests")
    for key, values in public_values.items():
        _require(len(values) == 1, f"private mutation changed {key}")


def _load_unique_json(path: Path, *, maximum_bytes: int = 4 * 1024 * 1024) -> Any:
    resolved = path.resolve(strict=True)
    _require(resolved.is_file(), "contract input must be one explicit file")
    _require(resolved.stat().st_size <= maximum_bytes,
             "contract input exceeds the bounded metadata size")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            _require(key not in result, f"duplicate JSON key {key!r}")
            result[key] = value
        return result

    return json.loads(resolved.read_text(encoding="utf-8"),
                      object_pairs_hook=unique_object)


def load_public_observation(path: str | Path) -> dict[str, Any]:
    """Load exactly one public packet; never search its directory for labels."""

    value = _load_unique_json(Path(path))
    _require(type(value) is dict, "public observation file must contain an object")
    return validate_observation_packet(value)


def load_private_evaluation(path: str | Path) -> dict[str, Any]:
    """Load exactly one private record through the evaluation-only API."""

    value = _load_unique_json(Path(path))
    _require(type(value) is dict, "private evaluation file must contain an object")
    return validate_private_evaluation(value)
