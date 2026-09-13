"""Shared graph storage operations for VSMT comparison adapters.

These helpers provide a common, version-preserving output wrapper.  They do
not choose associations or lifecycle decisions; each comparison mechanism
does that in its own adapter.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any, Iterable, Mapping

from cpmt.executor import validate_graph
from cpmt.hashing import canonical_json, clone_json, seal_graph


STATE_KEY = "vsmt_observation_state"


def finite_number(value: Any, name: str) -> float:
    if type(value) not in {int, float} or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def validate_threshold(value: Any, name: str, *, low: float, high: float) -> float:
    result = finite_number(value, name)
    if not low <= result <= high:
        raise ValueError(f"{name} must be within [{low}, {high}]")
    return result


def observation_state(node: Mapping[str, Any]) -> dict[str, Any] | None:
    state = node.get(STATE_KEY)
    if type(state) is not dict:
        return None
    required = {
        "descriptor", "centroid_m", "extent_m", "reliability",
        "last_seen_s", "observation_count",
    }
    if not required <= state.keys():
        return None
    descriptor = state["descriptor"]
    centroid = state["centroid_m"]
    extent = state["extent_m"]
    if not (
        type(descriptor) is list and descriptor
        and type(centroid) is list and len(centroid) == 3
        and type(extent) is list and len(extent) == 3
    ):
        return None
    return state


def open_nodes(graph: Mapping[str, Any], *, include_dormant: bool = True) -> list[dict[str, Any]]:
    lifecycles = {"candidate", "confirmed"}
    if include_dormant:
        lifecycles.add("dormant")
    return [
        node for node in graph["nodes"]
        if node.get("valid_to") is None
        and node.get("lifecycle") in lifecycles
        and observation_state(node) is not None
    ]


def archived_nodes(graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    open_ids = {
        node["node_id"] for node in graph["nodes"]
        if node.get("valid_to") is None
    }
    latest: dict[str, dict[str, Any]] = {}
    for node in graph["nodes"]:
        if (
            node.get("valid_to") is None
            or node["node_id"] in open_ids
            or observation_state(node) is None
        ):
            continue
        previous = latest.get(node["node_id"])
        if previous is None or (
            int(node["valid_from"]), str(node["node_version_id"])
        ) > (
            int(previous["valid_from"]), str(previous["node_version_id"])
        ):
            latest[node["node_id"]] = node
    return list(latest.values())


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return -1.0
    numerator = sum(float(a) * float(b) for a, b in zip(left, right))
    left_norm = math.sqrt(sum(float(value) ** 2 for value in left))
    right_norm = math.sqrt(sum(float(value) ** 2 for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return -1.0
    return max(-1.0, min(1.0, numerator / (left_norm * right_norm)))


def centroid_distance(left: Mapping[str, Any], right: Mapping[str, Any]) -> float:
    return math.sqrt(sum(
        (float(a) - float(b)) ** 2
        for a, b in zip(left["centroid_m"], right["centroid_m"])
    ))


def association_score(
    region: Mapping[str, Any], node: Mapping[str, Any], *,
    visual_weight: float, geometry_weight: float, geometry_scale_m: float,
) -> float:
    state = observation_state(node)
    if state is None or region["structure_kind"] != node.get("node_type"):
        return -1.0
    visual = (cosine_similarity(region["descriptor"], state["descriptor"]) + 1.0) / 2.0
    distance = centroid_distance(region, state)
    geometry = max(0.0, 1.0 - distance / geometry_scale_m)
    return visual_weight * visual + geometry_weight * geometry


def node_pair_score(
    left: Mapping[str, Any], right: Mapping[str, Any], *,
    visual_weight: float, geometry_weight: float, geometry_scale_m: float,
) -> float:
    left_state = observation_state(left)
    right_state = observation_state(right)
    if (
        left_state is None or right_state is None
        or left.get("node_type") != right.get("node_type")
    ):
        return -1.0
    visual = (cosine_similarity(
        left_state["descriptor"], right_state["descriptor"]
    ) + 1.0) / 2.0
    distance = centroid_distance(left_state, right_state)
    geometry = max(0.0, 1.0 - distance / geometry_scale_m)
    return visual_weight * visual + geometry_weight * geometry


def fully_covered_by_free_space(
    node: Mapping[str, Any], free_spaces: Iterable[Mapping[str, Any]], *,
    minimum_reliability: float,
) -> bool:
    state = observation_state(node)
    if state is None:
        return False
    lower = [
        float(center) - float(size) / 2.0
        for center, size in zip(state["centroid_m"], state["extent_m"])
    ]
    upper = [
        float(center) + float(size) / 2.0
        for center, size in zip(state["centroid_m"], state["extent_m"])
    ]
    return any(
        float(free_space["reliability"]) >= minimum_reliability
        and all(
            float(container_low) <= item_low
            and item_high <= float(container_high)
            for container_low, container_high, item_low, item_high in zip(
                free_space["minimum_m"], free_space["maximum_m"], lower, upper,
            )
        )
        for free_space in free_spaces
    )


def next_tick(graph: Mapping[str, Any]) -> int:
    values = [0]
    for node in graph["nodes"]:
        values.append(int(node["valid_from"]))
        if node.get("valid_to") is not None:
            values.append(int(node["valid_to"]))
    for edge in graph["edges"]:
        values.append(int(edge["valid_from"]))
        if edge.get("valid_to") is not None:
            values.append(int(edge["valid_to"]))
    return max(values) + 1


def opaque_id(*parts: object, prefix: str) -> str:
    encoded = canonical_json([str(part) for part in parts]).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(encoded).hexdigest()[:16]}"


class GraphRevision:
    """Mutable work copy used only inside one adapter update."""

    def __init__(self, graph: Mapping[str, Any], *, method_id: str):
        self.graph = clone_json(dict(graph))
        validate_graph(self.graph, verify_hash=True)
        self.method_id = method_id
        self.pre_hash = str(self.graph["graph_hash"])
        self.tick = next_tick(self.graph)
        self.templates: list[str] = []
        self.created_nodes: list[str] = []
        self.closed_nodes: list[str] = []
        self.created_edges: list[str] = []
        self.closed_edges: list[str] = []

    def _new_version_id(self, node_id: str, purpose: str) -> str:
        return opaque_id(
            self.pre_hash, self.method_id, self.tick, node_id, purpose,
            len(self.created_nodes), prefix="node-version",
        )

    def _state_from_region(
        self, region: Mapping[str, Any], decision_time_s: float, *,
        previous: Mapping[str, Any] | None = None, fused: bool = False,
    ) -> dict[str, Any]:
        count = int(previous.get("observation_count", 0)) if previous else 0
        if previous and fused:
            previous_weight = max(1, count)
            current_weight = max(1e-9, float(region["reliability"]))
            total = previous_weight + current_weight

            def blend(old: list[float], new: list[float]) -> list[float]:
                return [
                    (previous_weight * float(a) + current_weight * float(b)) / total
                    for a, b in zip(old, new)
                ]

            descriptor = blend(previous["descriptor"], region["descriptor"])
            centroid = blend(previous["centroid_m"], region["centroid_m"])
            extent = blend(previous["extent_m"], region["extent_m"])
        else:
            descriptor = [float(value) for value in region["descriptor"]]
            centroid = [float(value) for value in region["centroid_m"]]
            extent = [float(value) for value in region["extent_m"]]
        result = clone_json(dict(previous)) if previous else {}
        result.update({
            "descriptor": descriptor,
            "centroid_m": centroid,
            "extent_m": extent,
            "reliability": float(region["reliability"]),
            "last_seen_s": float(decision_time_s),
            "observation_count": count + 1,
        })
        return result

    def create_node(
        self, region: Mapping[str, Any], decision_time_s: float, *,
        lifecycle: str, state_updates: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        node_id = opaque_id(
            self.pre_hash, self.method_id, self.tick, region["region_id"],
            len(self.created_nodes), prefix="node",
        )
        version_id = self._new_version_id(node_id, "birth")
        state = self._state_from_region(region, decision_time_s)
        if state_updates:
            state.update(clone_json(dict(state_updates)))
        node = {
            "node_id": node_id,
            "node_version_id": version_id,
            "node_type": region["structure_kind"],
            "lifecycle": lifecycle,
            "valid_from": self.tick,
            "valid_to": None,
            "evidence_refs": [f"observation:{region['mask_sha256']}"],
            "latent_refs": [],
            "canonical_id": None,
            "predecessor_ids": [],
            "provenance": [f"{self.method_id}:birth"],
            STATE_KEY: state,
        }
        self.graph["nodes"].append(node)
        self.created_nodes.append(version_id)
        self.templates.append("BIRTH")
        return node

    def update_node(
        self, node: Mapping[str, Any], region: Mapping[str, Any],
        decision_time_s: float, *, lifecycle: str | None = None,
        fused: bool, template: str, state_updates: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        current = next(
            item for item in self.graph["nodes"]
            if item["node_version_id"] == node["node_version_id"]
        )
        if current["valid_to"] is None:
            current["valid_to"] = self.tick
            self.closed_nodes.append(current["node_version_id"])
        previous_state = observation_state(current)
        state = self._state_from_region(
            region, decision_time_s, previous=previous_state, fused=fused,
        )
        if state_updates:
            state.update(clone_json(dict(state_updates)))
        version_id = self._new_version_id(current["node_id"], template.lower())
        successor = clone_json(current)
        successor.update({
            "node_version_id": version_id,
            "lifecycle": lifecycle or current["lifecycle"],
            "valid_from": self.tick,
            "valid_to": None,
            "evidence_refs": list(dict.fromkeys(
                list(current.get("evidence_refs", []))
                + [f"observation:{region['mask_sha256']}"]
            )),
            "predecessor_ids": [current["node_version_id"]],
            "provenance": list(current["provenance"]) + [f"{self.method_id}:{template.lower()}"],
            STATE_KEY: state,
        })
        self.graph["nodes"].append(successor)
        self.created_nodes.append(version_id)
        self.templates.append(template)
        return successor

    def lifecycle_node(
        self, node: Mapping[str, Any], *, lifecycle: str, template: str | None,
        state_updates: Mapping[str, Any], terminal: bool = False,
    ) -> dict[str, Any]:
        current = next(
            item for item in self.graph["nodes"]
            if item["node_version_id"] == node["node_version_id"]
        )
        if current["valid_to"] is None:
            current["valid_to"] = self.tick
            self.closed_nodes.append(current["node_version_id"])
        purpose = template.lower() if template is not None else "internal-state"
        version_id = self._new_version_id(current["node_id"], purpose)
        successor = clone_json(current)
        state = clone_json(observation_state(current) or {})
        state.update(clone_json(dict(state_updates)))
        successor.update({
            "node_version_id": version_id,
            "lifecycle": lifecycle,
            "valid_from": self.tick,
            "valid_to": self.tick if terminal else None,
            "predecessor_ids": [current["node_version_id"]],
            "provenance": list(current["provenance"]) + [f"{self.method_id}:{purpose}"],
            STATE_KEY: state,
        })
        self.graph["nodes"].append(successor)
        self.created_nodes.append(version_id)
        if terminal:
            self.closed_nodes.append(version_id)
            self._close_incident_edges(current["node_id"])
        if template is not None:
            self.templates.append(template)
        return successor

    def reactivate_node(
        self, node: Mapping[str, Any], region: Mapping[str, Any],
        decision_time_s: float, *, state_updates: Mapping[str, Any],
    ) -> dict[str, Any]:
        state = self._state_from_region(
            region, decision_time_s, previous=observation_state(node), fused=True,
        )
        state.update(clone_json(dict(state_updates)))
        version_id = self._new_version_id(node["node_id"], "reactivate")
        successor = clone_json(node)
        successor.update({
            "node_version_id": version_id,
            "lifecycle": "confirmed",
            "valid_from": self.tick,
            "valid_to": None,
            "evidence_refs": list(dict.fromkeys(
                list(node.get("evidence_refs", []))
                + [f"observation:{region['mask_sha256']}"]
            )),
            "predecessor_ids": [node["node_version_id"]],
            "provenance": list(node["provenance"]) + [f"{self.method_id}:reactivate"],
            STATE_KEY: state,
        })
        self.graph["nodes"].append(successor)
        self.created_nodes.append(version_id)
        self.templates.append("REACTIVATE")
        return successor

    def merge_nodes(self, winner: Mapping[str, Any], loser: Mapping[str, Any]) -> dict[str, Any]:
        winner_state = observation_state(winner)
        loser_state = observation_state(loser)
        if winner_state is None or loser_state is None:
            raise ValueError("MERGE requires two observation-state nodes")
        count_left = max(1, int(winner_state["observation_count"]))
        count_right = max(1, int(loser_state["observation_count"]))
        total = count_left + count_right

        def blend(key: str) -> list[float]:
            return [
                (count_left * float(a) + count_right * float(b)) / total
                for a, b in zip(winner_state[key], loser_state[key])
            ]

        synthetic_region = {
            "region_id": "region:0000",
            "structure_kind": winner["node_type"],
            "mask_sha256": hashlib.sha256(canonical_json([
                winner["node_version_id"], loser["node_version_id"],
            ]).encode("utf-8")).hexdigest(),
            "descriptor": blend("descriptor"),
            "centroid_m": blend("centroid_m"),
            "extent_m": blend("extent_m"),
            "reliability": max(
                float(winner_state["reliability"]),
                float(loser_state["reliability"]),
            ),
        }
        merged = self.update_node(
            winner, synthetic_region,
            max(float(winner_state["last_seen_s"]), float(loser_state["last_seen_s"])),
            fused=False, template="MERGE",
            state_updates={"observation_count": total},
        )
        current_loser = next(
            item for item in self.graph["nodes"]
            if item["node_version_id"] == loser["node_version_id"]
        )
        if current_loser["valid_to"] is None:
            current_loser["valid_to"] = self.tick
            self.closed_nodes.append(current_loser["node_version_id"])
            self._close_incident_edges(current_loser["node_id"])
        return merged

    def _close_incident_edges(self, node_id: str) -> None:
        for edge in self.graph["edges"]:
            if (
                edge.get("valid_to") is None
                and node_id in {edge.get("source"), edge.get("target")}
            ):
                edge["valid_to"] = self.tick
                self.closed_edges.append(edge["edge_version_id"])

    def finish(self, *, confidence: float, runtime_ms: float,
               diagnostics: Mapping[str, Any]) -> dict[str, Any]:
        changed = any((
            self.created_nodes, self.closed_nodes,
            self.created_edges, self.closed_edges,
        ))
        if not self.templates and not changed:
            return {
                "schema_version": "vsmt-memory-update-result-v1",
                "method_id": self.method_id,
                "pre_memory_sha256": self.pre_hash,
                "post_memory": clone_json(self.graph),
                "post_memory_sha256": self.pre_hash,
                "normalized_delta": {
                    "declared_template": "NOOP",
                    "created_node_version_ids": [],
                    "closed_node_version_ids": [],
                    "created_edge_version_ids": [],
                    "closed_edge_version_ids": [],
                },
                "confidence": confidence,
                "runtime_ms": runtime_ms,
                "diagnostics": clone_json(dict(diagnostics)),
            }
        distinct_templates = list(dict.fromkeys(self.templates))
        declared = (
            distinct_templates[0]
            if len(distinct_templates) == 1 else None
        )
        parent = str(self.graph["graph_version"])
        version_payload = {
            "parent": parent,
            "method_id": self.method_id,
            "tick": self.tick,
            "created_nodes": self.created_nodes,
            "closed_nodes": self.closed_nodes,
            "created_edges": self.created_edges,
            "closed_edges": self.closed_edges,
            "templates": distinct_templates,
        }
        self.graph["parent_version"] = parent
        self.graph["graph_version"] = opaque_id(
            canonical_json(version_payload), prefix="graph-version",
        )
        self.graph["transaction_log"].append({
            "method_id": self.method_id,
            "logical_tick": self.tick,
            "declared_template": declared,
            "observed_templates": distinct_templates,
        })
        self.graph = seal_graph(self.graph)
        validate_graph(self.graph, verify_hash=True)
        return {
            "schema_version": "vsmt-memory-update-result-v1",
            "method_id": self.method_id,
            "pre_memory_sha256": self.pre_hash,
            "post_memory": self.graph,
            "post_memory_sha256": self.graph["graph_hash"],
            "normalized_delta": {
                "declared_template": declared,
                "created_node_version_ids": list(dict.fromkeys(self.created_nodes)),
                "closed_node_version_ids": list(dict.fromkeys(self.closed_nodes)),
                "created_edge_version_ids": list(dict.fromkeys(self.created_edges)),
                "closed_edge_version_ids": list(dict.fromkeys(self.closed_edges)),
            },
            "confidence": confidence,
            "runtime_ms": runtime_ms,
            "diagnostics": clone_json(dict(diagnostics)),
        }
