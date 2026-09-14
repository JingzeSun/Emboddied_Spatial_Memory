"""Public-only causal prior construction for VSMT controlled comparisons.

The builder consumes validated observation packets in time order and performs
    only deterministic BIRTH/BIND updates. A candidate is explicitly confirmed
    after a BIND supplies its second distinct public evidence reference. Private
    evaluation, future data and teacher values are absent from every function
    signature by design.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import re
from typing import Any, Mapping, Sequence

from cpmt.executor import validate_graph
from cpmt.hashing import clone_json, seal_graph

from .contracts import (
    build_adapter_input,
    canonical_sha256,
    validate_observation_packet,
)
from .graph_ops import (
    GraphRevision,
    association_score,
    open_nodes,
    validate_threshold,
)


RECEIPT_SCHEMA = "vsmt-causal-prior-receipt-v1"
BUILDER_ID = "vsmt.public.bootstrap.v1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
LEARNED_STRUCTURE_KINDS = {"entity", "surface", "fragment"}


def _positive(value: Any, name: str) -> float:
    if type(value) not in {int, float} or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be a finite number")
    result = float(value)
    if result <= 0.0:
        raise ValueError(f"{name} must be positive")
    return result


@dataclass(frozen=True)
class PublicBootstrapConfig:
    """All scientific values are required; this class has no defaults."""

    association_rules: Mapping[str, Mapping[str, float]]
    maximum_regions_per_packet: int
    builder_revision: str

    def __post_init__(self) -> None:
        if set(self.association_rules) != LEARNED_STRUCTURE_KINDS:
            raise ValueError(
                "bootstrap association_rules must explicitly cover "
                "entity, surface, and fragment but not place"
            )
        expected = {
            "visual_weight", "geometry_weight", "geometry_scale_m",
            "association_threshold",
        }
        for kind, rule in self.association_rules.items():
            if type(rule) is not dict or set(rule) != expected:
                raise ValueError(f"bootstrap {kind} association rule is malformed")
            visual = validate_threshold(
                rule["visual_weight"], f"{kind}.visual_weight", low=0.0, high=1.0,
            )
            geometry = validate_threshold(
                rule["geometry_weight"], f"{kind}.geometry_weight", low=0.0, high=1.0,
            )
            if not math.isclose(visual + geometry, 1.0, abs_tol=1e-12):
                raise ValueError(f"{kind} visual and geometry weights must sum to one")
            _positive(rule["geometry_scale_m"], f"{kind}.geometry_scale_m")
            validate_threshold(
                rule["association_threshold"], f"{kind}.association_threshold",
                low=0.0, high=1.0,
            )
        if (
            type(self.maximum_regions_per_packet) is not int
            or self.maximum_regions_per_packet <= 0
        ):
            raise ValueError("maximum_regions_per_packet must be a positive integer")
        if (
            type(self.builder_revision) is not str
            or not self.builder_revision
            or any(character.isspace() for character in self.builder_revision)
        ):
            raise ValueError("builder_revision must be a nonempty token")


def empty_public_memory() -> dict[str, Any]:
    """Return the same content-free starting graph for every episode."""

    return seal_graph({
        "schema_version": "cpmt-0.2",
        "graph_id": "graph:public-bootstrap-v1",
        "graph_version": "graph-version:empty-v1",
        "parent_version": None,
        "nodes": [],
        "edges": [],
        "transaction_log": [],
    })


def _best_match(
    region: Mapping[str, Any], revision: GraphRevision, used_node_ids: set[str],
    config: PublicBootstrapConfig,
) -> tuple[float, dict[str, Any]] | None:
    kind = str(region["structure_kind"])
    rule = config.association_rules[kind]
    rows = [
        (
            association_score(
                region,
                node,
                visual_weight=rule["visual_weight"],
                geometry_weight=rule["geometry_weight"],
                geometry_scale_m=rule["geometry_scale_m"],
            ),
            node,
        )
        for node in open_nodes(revision.graph, include_dormant=False)
        if node["node_id"] not in used_node_ids
    ]
    if not rows:
        return None
    return sorted(rows, key=lambda item: (-item[0], str(item[1]["node_id"])))[0]


def advance_public_bootstrap(
    packet: Mapping[str, Any], prior_memory: Mapping[str, Any], *,
    config: PublicBootstrapConfig,
) -> dict[str, Any]:
    """Apply one deterministic public packet and return a shared result record."""

    model_input = build_adapter_input(packet, prior_memory)
    regions = model_input["region_observations"]
    if len(regions) > config.maximum_regions_per_packet:
        raise ValueError("packet exceeds maximum_regions_per_packet")

    revision = GraphRevision(prior_memory, method_id=BUILDER_ID)
    used_node_ids: set[str] = set()
    decisions: list[dict[str, Any]] = []
    region_node_ids: dict[str, str] = {}
    for region in regions:
        if region["structure_kind"] != "place":
            continue
        place = revision.upsert_place_scaffold(
            region, float(model_input["decision_time_s"]),
        )
        region_node_ids[str(region["region_id"])] = str(place["node_id"])
        decisions.append({
            "template": "PLACE_SCAFFOLD",
            "region_id": region["region_id"],
            "node_id": place["node_id"],
            "association_score": None,
        })
    for region in regions:
        if region["structure_kind"] == "place":
            continue
        ranked = _best_match(region, revision, used_node_ids, config)
        threshold = config.association_rules[region["structure_kind"]][
            "association_threshold"
        ]
        if ranked is not None and ranked[0] >= threshold:
            score, matched = ranked
            current_evidence = f"observation:{region['mask_sha256']}"
            promote = (
                matched["lifecycle"] == "candidate"
                and len(set(matched["evidence_refs"]) | {current_evidence}) >= 2
            )
            updated = revision.update_node(
                matched,
                region,
                float(model_input["decision_time_s"]),
                lifecycle="confirmed" if promote else None,
                fused=True,
                template="BIND",
            )
            used_node_ids.add(str(updated["node_id"]))
            region_node_ids[str(region["region_id"])] = str(updated["node_id"])
            decisions.append({
                "template": "BIND",
                "region_id": region["region_id"],
                "node_id": updated["node_id"],
                "association_score": float(score),
                "promoted_to_confirmed": promote,
            })
        else:
            created = revision.create_node(
                region,
                float(model_input["decision_time_s"]),
                lifecycle="candidate",
            )
            used_node_ids.add(str(created["node_id"]))
            region_node_ids[str(region["region_id"])] = str(created["node_id"])
            decisions.append({
                "template": "BIRTH",
                "region_id": region["region_id"],
                "node_id": created["node_id"],
                "association_score": None,
                "promoted_to_confirmed": False,
            })

    relation_counts = revision.apply_relation_observations(
        model_input["relation_observations"], region_node_ids,
    )
    public_reliabilities = [
        *[float(region["reliability"]) for region in regions],
        *[
            float(relation["reliability"])
            for relation in model_input["relation_observations"]
        ],
    ]
    confidence = (
        sum(public_reliabilities) / len(public_reliabilities)
        if public_reliabilities else 1.0
    )
    result = revision.finish(
        confidence=confidence,
        runtime_ms=0.0,
        diagnostics={
            "bootstrap_decisions": decisions,
            "packet_region_count": len(regions),
            "relation_updates": relation_counts,
        },
    )
    return clone_json(result)


def _receipt_payload(receipt: Mapping[str, Any]) -> dict[str, Any]:
    payload = clone_json(dict(receipt))
    payload.pop("receipt_sha256", None)
    return payload


def _memory_sha256(memory: Mapping[str, Any]) -> str:
    graph = clone_json(dict(memory))
    validate_graph(graph, verify_hash=True)
    digest = graph.get("graph_hash")
    if type(digest) is not str or HEX64.fullmatch(digest) is None:
        raise ValueError("memory graph must carry a valid graph_hash")
    return digest


def validate_causal_prior_receipt(
    receipt: Mapping[str, Any], *, final_memory: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    expected = {
        "schema_version",
        "builder_id",
        "builder_revision",
        "builder_code_sha256",
        "builder_config_sha256",
        "initial_memory_sha256",
        "ordered_public_packet_sha256s",
        "ordered_adapter_input_sha256s",
        "committed_update_sha256s",
        "version_chain_sha256s",
        "final_prior_memory_sha256",
        "packet_count",
        "receipt_sha256",
    }
    if set(receipt) != expected:
        raise ValueError(f"causal prior receipt must contain exactly {sorted(expected)}")
    if receipt["schema_version"] != RECEIPT_SCHEMA:
        raise ValueError("wrong causal prior receipt schema")
    if receipt["builder_id"] != BUILDER_ID:
        raise ValueError("wrong causal prior builder_id")
    for key in {
        "builder_code_sha256",
        "builder_config_sha256",
        "initial_memory_sha256",
        "final_prior_memory_sha256",
        "receipt_sha256",
    }:
        if type(receipt[key]) is not str or HEX64.fullmatch(receipt[key]) is None:
            raise ValueError(f"{key} must be a lowercase SHA-256 digest")
    sequence_keys = {
        "ordered_public_packet_sha256s",
        "ordered_adapter_input_sha256s",
        "committed_update_sha256s",
        "version_chain_sha256s",
    }
    for key in sequence_keys:
        values = receipt[key]
        if type(values) is not list or any(
            type(value) is not str or HEX64.fullmatch(value) is None
            for value in values
        ):
            raise ValueError(f"{key} must contain SHA-256 digests")
    count = receipt["packet_count"]
    if type(count) is not int or count < 0:
        raise ValueError("packet_count must be a non-negative integer")
    for key in sequence_keys - {"version_chain_sha256s"}:
        if len(receipt[key]) != count:
            raise ValueError(f"{key} must have packet_count entries")
    if len(receipt["version_chain_sha256s"]) != count + 1:
        raise ValueError("version_chain_sha256s must include initial plus every packet")
    if receipt["version_chain_sha256s"][0] != receipt["initial_memory_sha256"]:
        raise ValueError("version chain does not start from initial memory")
    if receipt["version_chain_sha256s"][-1] != receipt["final_prior_memory_sha256"]:
        raise ValueError("version chain does not end at final memory")
    expected_seal = canonical_sha256(_receipt_payload(receipt))
    if receipt["receipt_sha256"] != expected_seal:
        raise ValueError("causal prior receipt digest mismatch")
    if final_memory is not None and (
        _memory_sha256(final_memory) != receipt["final_prior_memory_sha256"]
    ):
        raise ValueError("causal prior receipt is bound to a different final memory")
    return clone_json(dict(receipt))


def build_causal_prior(
    packets: Sequence[Mapping[str, Any]], *, config: PublicBootstrapConfig,
    builder_code_sha256: str,
) -> dict[str, Any]:
    """Build and seal one causal prior without accepting any private value."""

    if type(builder_code_sha256) is not str or HEX64.fullmatch(
        builder_code_sha256,
    ) is None:
        raise ValueError("builder_code_sha256 must be a lowercase SHA-256 digest")

    memory = empty_public_memory()
    initial_hash = _memory_sha256(memory)
    packet_hashes: list[str] = []
    adapter_hashes: list[str] = []
    update_hashes: list[str] = []
    version_hashes = [initial_hash]
    previous_time = -math.inf
    for packet in packets:
        public = validate_observation_packet(packet)
        decision_time = float(public["decision_time_s"])
        if decision_time < previous_time:
            raise ValueError("causal prior packets must be ordered by decision_time_s")
        previous_time = decision_time
        model_input = build_adapter_input(public, memory)
        packet_hashes.append(canonical_sha256(public))
        adapter_hashes.append(canonical_sha256(model_input))
        result = advance_public_bootstrap(public, memory, config=config)
        update_hashes.append(canonical_sha256({
            "pre_memory_sha256": result["pre_memory_sha256"],
            "post_memory_sha256": result["post_memory_sha256"],
            "normalized_delta": result["normalized_delta"],
            "bootstrap_decisions": result["diagnostics"]["bootstrap_decisions"],
        }))
        memory = clone_json(result["post_memory"])
        version_hashes.append(_memory_sha256(memory))

    receipt: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA,
        "builder_id": BUILDER_ID,
        "builder_revision": config.builder_revision,
        "builder_code_sha256": builder_code_sha256,
        "builder_config_sha256": canonical_sha256(asdict(config)),
        "initial_memory_sha256": initial_hash,
        "ordered_public_packet_sha256s": packet_hashes,
        "ordered_adapter_input_sha256s": adapter_hashes,
        "committed_update_sha256s": update_hashes,
        "version_chain_sha256s": version_hashes,
        "final_prior_memory_sha256": _memory_sha256(memory),
        "packet_count": len(packets),
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return {
        "prior_memory": memory,
        "receipt": validate_causal_prior_receipt(receipt, final_memory=memory),
    }
