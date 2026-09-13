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


OBSERVATION_SCHEMA = "vsmt-observation-packet-v1"
CANDIDATE_SCHEMA = "vsmt-candidate-catalog-v1"
TEACHER_SCHEMA = "vsmt-teacher-targets-v1"
RESULT_SCHEMA = "vsmt-memory-update-result-v1"
PRIVATE_SCHEMA = "vsmt-private-evaluation-v1"
INVARIANCE_SCHEMA = "vsmt-private-mutation-invariance-v1"

HEX64 = re.compile(r"^[0-9a-f]{64}$")
OPAQUE_REGION = re.compile(r"^region:[0-9]{4}$")
OPAQUE_CANDIDATE = re.compile(r"^candidate:[0-9]{4}$")
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
    "prior_memory_ref",
    "public_constants",
}
RGBD_REF_KEYS = {"rgb_sha256", "depth_sha256"}
POSE_KEYS = {"position_m", "quaternion_xyzw"}
ROBOT_STATE_KEYS = {"feature_names", "values"}
ACTION_KEYS = {"end_time_s", "command"}
REGION_KEYS = {
    "region_id",
    "mask_sha256",
    "descriptor",
    "centroid_m",
    "extent_m",
    "reliability",
    "proposal_source_id",
}
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


class AdapterInput(TypedDict):
    """The only value passed to a deployable memory-update method."""

    decision_time_s: float
    camera_pose: dict[str, Any]
    robot_state: dict[str, Any]
    past_actions: list[dict[str, Any]]
    region_observations: list[dict[str, Any]]
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
        "derivations", "candidates", "catalog_sha256",
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

    candidates = catalog["candidates"]
    _require(type(candidates) is list and candidates,
             "candidate catalog must be nonempty")
    for index, item in enumerate(candidates):
        _require(type(item) is dict, f"candidates[{index}] must be an object")
        _exact_keys(item, {"candidate_id", "program", "program_sha256"},
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
) -> dict[str, Any]:
    """Seal candidates from public values; no private argument exists by design."""

    public = validate_observation_packet(packet)
    memory_digest = _public_memory_digest(prior_memory)
    candidates = [
        {
            "candidate_id": f"candidate:{index:04d}",
            "program": clone_json(dict(program)),
            "program_sha256": canonical_sha256(program),
        }
        for index, program in enumerate(programs)
    ]
    catalog: dict[str, Any] = {
        "schema_version": CANDIDATE_SCHEMA,
        "public_sha256": canonical_sha256(public),
        "prior_memory_sha256": memory_digest,
        "generator_id": generator_id,
        "derivations": clone_json(derivations),
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
    return validate_memory_update_result(
        result,
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
