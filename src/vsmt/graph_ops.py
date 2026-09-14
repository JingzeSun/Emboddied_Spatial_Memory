"""Shared graph storage operations for VSMT comparison adapters.

These helpers provide a common, version-preserving output wrapper.  They do
not choose associations or lifecycle decisions; each comparison mechanism
does that in its own adapter.
"""

from __future__ import annotations

import hashlib
from itertools import product
import math
from typing import Any, Iterable, Mapping, Sequence

from cpmt.executor import validate_graph
from cpmt.hashing import canonical_json, clone_json, seal_graph


STATE_KEY = "vsmt_observation_state"
PLACE_SCAFFOLD_ID = "vsmt.place.scaffold.v1"
# 白话：这些关系由确定性地点骨架维护，不进入任何方法的事务候选空间。
SCAFFOLD_RELATIONS = frozenset({"adjacent_to"})
# 白话：只有这些受信任的确定性包装可以做"不记模板"的边操作；记忆方法一律不行，
# 否则一个适配器可以把建边藏在模板白名单之外。
TRUSTED_SCAFFOLD_METHOD_IDS = frozenset({
    PLACE_SCAFFOLD_ID,
    "vsmt.public.bootstrap.v1",
})


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


def observation_aabb(
    centroid_m: Sequence[Any], extent_m: Sequence[Any],
) -> tuple[list[float], list[float]]:
    if len(centroid_m) != 3 or len(extent_m) != 3:
        raise ValueError("observation AABB needs three-dimensional inputs")
    lower = [
        finite_number(center, "observation centroid")
        - finite_number(size, "observation extent") / 2.0
        for center, size in zip(centroid_m, extent_m, strict=True)
    ]
    upper = [
        finite_number(center, "observation centroid")
        + finite_number(size, "observation extent") / 2.0
        for center, size in zip(centroid_m, extent_m, strict=True)
    ]
    if any(size < 0.0 for size in map(float, extent_m)):
        raise ValueError("observation extent must be non-negative")
    return lower, upper


def state_from_region(
    region: Mapping[str, Any], decision_time_s: float, *,
    support_envelope_reliability_threshold: float,
    previous: Mapping[str, Any] | None = None,
    fused: bool = False,
) -> dict[str, Any]:
    """Build shared observation state from one raw public region."""

    threshold = validate_threshold(
        support_envelope_reliability_threshold,
        "support_envelope_reliability_threshold", low=0.0, high=1.0,
    )
    count = int(previous.get("observation_count", 0)) if previous else 0
    if previous and fused:
        previous_weight = max(1, count)
        current_weight = max(1e-9, float(region["reliability"]))
        total = previous_weight + current_weight

        def blend(old: list[float], new: list[float]) -> list[float]:
            return [
                (previous_weight * float(a) + current_weight * float(b)) / total
                for a, b in zip(old, new, strict=True)
            ]

        descriptor = blend(previous["descriptor"], region["descriptor"])
        centroid = blend(previous["centroid_m"], region["centroid_m"])
        extent = blend(previous["extent_m"], region["extent_m"])
    else:
        descriptor = [float(value) for value in region["descriptor"]]
        centroid = [float(value) for value in region["centroid_m"]]
        extent = [float(value) for value in region["extent_m"]]

    raw_lower, raw_upper = observation_aabb(
        region["centroid_m"], region["extent_m"],
    )
    previous_lower = previous.get("support_envelope_min_m") if previous else None
    previous_upper = previous.get("support_envelope_max_m") if previous else None
    previous_envelope_count = int(
        previous.get("support_envelope_observation_count", 0)
    ) if previous else 0
    previous_threshold = (
        previous.get("support_envelope_reliability_threshold")
        if previous else threshold
    )
    if previous and previous_threshold is not None and not math.isclose(
        float(previous_threshold), threshold, abs_tol=1e-12,
    ):
        raise ValueError("support-envelope reliability threshold changed mid-identity")
    if float(region["reliability"]) >= threshold:
        if previous_lower is None or previous_upper is None:
            envelope_lower, envelope_upper = raw_lower, raw_upper
        else:
            envelope_lower = [
                min(float(previous_lower[axis]), raw_lower[axis])
                for axis in range(3)
            ]
            envelope_upper = [
                max(float(previous_upper[axis]), raw_upper[axis])
                for axis in range(3)
            ]
        envelope_count = previous_envelope_count + 1
    else:
        envelope_lower = clone_json(previous_lower)
        envelope_upper = clone_json(previous_upper)
        envelope_count = previous_envelope_count

    result = clone_json(dict(previous)) if previous else {}
    result.update({
        "descriptor": descriptor,
        "centroid_m": centroid,
        "extent_m": extent,
        "reliability": float(region["reliability"]),
        "last_seen_s": float(decision_time_s),
        "observation_count": count + 1,
        "observation_aabb_min_m": raw_lower,
        "observation_aabb_max_m": raw_upper,
        "support_envelope_min_m": envelope_lower,
        "support_envelope_max_m": envelope_upper,
        "support_envelope_observation_count": envelope_count,
        "support_envelope_reliability_threshold": threshold,
    })
    return result


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
    components = association_components(
        region, node, geometry_scale_m=geometry_scale_m,
    )
    if components is None:
        return -1.0
    return (
        visual_weight * components["visual_similarity"]
        + geometry_weight * components["geometry_proximity"]
    )


def association_components(
    region: Mapping[str, Any], node: Mapping[str, Any], *,
    geometry_scale_m: float,
) -> dict[str, float] | None:
    """Return public visual and geometric terms before weighting."""

    state = observation_state(node)
    if state is None or region["structure_kind"] != node.get("node_type"):
        return None
    visual = (cosine_similarity(region["descriptor"], state["descriptor"]) + 1.0) / 2.0
    distance = centroid_distance(region, state)
    geometry = max(0.0, 1.0 - distance / geometry_scale_m)
    return {
        "visual_similarity": visual,
        "centroid_distance_m": distance,
        "geometry_proximity": geometry,
    }


def node_pair_score(
    left: Mapping[str, Any], right: Mapping[str, Any], *,
    visual_weight: float, geometry_weight: float, geometry_scale_m: float,
) -> float:
    components = node_pair_components(
        left, right, geometry_scale_m=geometry_scale_m,
    )
    if components is None:
        return -1.0
    return (
        visual_weight * components["visual_similarity"]
        + geometry_weight * components["geometry_proximity"]
    )


def node_pair_components(
    left: Mapping[str, Any], right: Mapping[str, Any], *,
    geometry_scale_m: float,
) -> dict[str, float] | None:
    """Return public visual and geometric terms for two memory nodes."""

    left_state = observation_state(left)
    right_state = observation_state(right)
    if (
        left_state is None or right_state is None
        or left.get("node_type") != right.get("node_type")
    ):
        return None
    visual = (cosine_similarity(
        left_state["descriptor"], right_state["descriptor"]
    ) + 1.0) / 2.0
    distance = centroid_distance(left_state, right_state)
    geometry = max(0.0, 1.0 - distance / geometry_scale_m)
    return {
        "visual_similarity": visual,
        "centroid_distance_m": distance,
        "geometry_proximity": geometry,
    }


def fully_covered_by_free_space(
    node: Mapping[str, Any], free_spaces: Iterable[Mapping[str, Any]], *,
    minimum_reliability: float, target_expansion_m: float,
    support_reliability_threshold: float,
) -> bool:
    support_threshold = validate_threshold(
        support_reliability_threshold,
        "support_reliability_threshold", low=0.0, high=1.0,
    )
    state = observation_state(node)
    if state is None:
        return False
    recorded_threshold = state.get("support_envelope_reliability_threshold")
    lower_bound = state.get("support_envelope_min_m")
    upper_bound = state.get("support_envelope_max_m")
    if (
        recorded_threshold is None
        or not math.isclose(float(recorded_threshold), support_threshold, abs_tol=1e-12)
        or type(lower_bound) is not list or len(lower_bound) != 3
        or type(upper_bound) is not list or len(upper_bound) != 3
        or int(state.get("support_envelope_observation_count", 0)) < 1
    ):
        return False
    expansion = finite_number(target_expansion_m, "target_expansion_m")
    if expansion < 0.0:
        raise ValueError("target_expansion_m must be non-negative")
    lower = [
        finite_number(lower_bound[axis], "support envelope lower") - expansion
        for axis in range(3)
    ]
    upper = [
        finite_number(upper_bound[axis], "support envelope upper") + expansion
        for axis in range(3)
    ]
    corners = list(product(*zip(lower, upper)))
    return any(
        float(free_space["reliability"]) >= minimum_reliability
        and all(
            sum(
                float(coefficient) * float(coordinate)
                for coefficient, coordinate in zip(
                    halfspace["normal"], corner, strict=True,
                )
            ) <= float(halfspace["offset_m"]) + 1e-9
            for corner in corners
            for halfspace in free_space["halfspaces_world"]
        )
        for free_space in free_spaces
    )


def open_edges(graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        edge for edge in graph["edges"]
        if edge.get("valid_to") is None
    ]


def _node_type(graph: Mapping[str, Any], node_id: str) -> str | None:
    for node in graph["nodes"]:
        if node["node_id"] == node_id and node.get("valid_to") is None:
            return str(node.get("node_type"))
    return None


def canonical_relation_observation(
    relation: Mapping[str, Any], region_node_ids: Mapping[str, str],
) -> tuple[str, str, str]:
    """Return the one stored direction for a public relation observation."""

    source = region_node_ids[str(relation["source_region_id"])]
    target = region_node_ids[str(relation["target_region_id"])]
    relation_kind = str(relation["relation"])
    if relation_kind == "contains":
        return target, source, "located_at"
    if relation_kind == "adjacent_to" and target < source:
        source, target = target, source
    return source, target, relation_kind


def covering_free_space_times(
    node: Mapping[str, Any], free_spaces: Iterable[Mapping[str, Any]], *,
    minimum_reliability: float, target_expansion_m: float,
    minimum_time_separation_s: float,
    support_reliability_threshold: float,
) -> list[Mapping[str, Any]]:
    separation = finite_number(
        minimum_time_separation_s, "minimum_time_separation_s",
    )
    if separation <= 0.0:
        raise ValueError("minimum_time_separation_s must be positive")
    by_time: dict[float, Mapping[str, Any]] = {}
    for free_space in free_spaces:
        if fully_covered_by_free_space(
            node, [free_space], minimum_reliability=minimum_reliability,
            target_expansion_m=target_expansion_m,
            support_reliability_threshold=support_reliability_threshold,
        ):
            by_time.setdefault(float(free_space["time_s"]), free_space)
    ordered = [by_time[key] for key in sorted(by_time)]
    if len(ordered) < 2:
        return ordered
    qualified: list[Mapping[str, Any]] = []
    for item in ordered:
        if not qualified or (
            float(item["time_s"]) - float(qualified[-1]["time_s"])
            >= separation
        ):
            qualified.append(item)
    return qualified


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


def place_scaffold_key(region: Mapping[str, Any]) -> str:
    if region.get("structure_kind") != "place":
        raise ValueError("place scaffold key requires a place region")
    centroid = region.get("centroid_m")
    if type(centroid) is not list or len(centroid) != 3:
        raise ValueError("place region centroid_m must contain three values")
    x = finite_number(centroid[0], "place centroid x")
    z = finite_number(centroid[2], "place centroid z")
    return f"{x:.9f}:{z:.9f}"


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def place_scaffold_key_from_centre(x: float, z: float) -> str:
    """Format one place scaffold key directly from a cell centre coordinate."""

    return (
        f"{finite_number(x, 'place centre x'):.9f}"
        f":{finite_number(z, 'place centre z'):.9f}"
    )


def place_scaffold_node_id(region: Mapping[str, Any]) -> str:
    return opaque_id(PLACE_SCAFFOLD_ID, place_scaffold_key(region), prefix="node")


class GraphRevision:
    """Mutable work copy used only inside one adapter update."""

    def __init__(
        self, graph: Mapping[str, Any], *, method_id: str,
        support_envelope_reliability_threshold: float,
    ):
        self.graph = clone_json(dict(graph))
        validate_graph(self.graph, verify_hash=True)
        self.method_id = method_id
        self.support_envelope_reliability_threshold = validate_threshold(
            support_envelope_reliability_threshold,
            "support_envelope_reliability_threshold", low=0.0, high=1.0,
        )
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

    def _new_edge_version_id(self, edge_id: str, purpose: str) -> str:
        return opaque_id(
            self.pre_hash, self.method_id, self.tick, edge_id, purpose,
            len(self.created_edges), prefix="edge-version",
        )

    def _state_from_region(
        self, region: Mapping[str, Any], decision_time_s: float, *,
        previous: Mapping[str, Any] | None = None, fused: bool = False,
    ) -> dict[str, Any]:
        return state_from_region(
            region, decision_time_s,
            support_envelope_reliability_threshold=(
                self.support_envelope_reliability_threshold
            ),
            previous=previous, fused=fused,
        )

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

    def upsert_place_scaffold(
        self, region: Mapping[str, Any], decision_time_s: float,
    ) -> dict[str, Any]:
        """Version one coordinate-defined place outside learned transactions."""

        key = place_scaffold_key(region)
        node_id = place_scaffold_node_id(region)
        open_matches = [
            node for node in self.graph["nodes"]
            if node.get("valid_to") is None
            and node.get("node_type") == "place"
            and (observation_state(node) or {}).get("place_scaffold_key") == key
        ]
        if len(open_matches) > 1:
            raise ValueError("place scaffold key has multiple open nodes")
        if open_matches:
            current = open_matches[0]
            if current["node_id"] != node_id:
                raise ValueError("place scaffold node identity is not coordinate-derived")
            current["valid_to"] = self.tick
            self.closed_nodes.append(str(current["node_version_id"]))
            previous = observation_state(current)
            state = self._state_from_region(
                region, decision_time_s, previous=previous, fused=True,
            )
            state["place_scaffold_key"] = key
            successor = clone_json(current)
            successor.update({
                "node_version_id": opaque_id(
                    self.pre_hash, PLACE_SCAFFOLD_ID, self.tick, node_id,
                    "bind", prefix="node-version",
                ),
                "lifecycle": "confirmed",
                "valid_from": self.tick,
                "valid_to": None,
                "evidence_refs": list(dict.fromkeys(
                    list(current["evidence_refs"])
                    + [f"observation:{region['mask_sha256']}"]
                )),
                "predecessor_ids": [current["node_version_id"]],
                "provenance": list(current["provenance"])
                + [f"{PLACE_SCAFFOLD_ID}:bind"],
                STATE_KEY: state,
            })
            self.graph["nodes"].append(successor)
            self.created_nodes.append(str(successor["node_version_id"]))
            return successor

        if any(node["node_id"] == node_id for node in self.graph["nodes"]):
            raise ValueError("place scaffold identity exists without an open version")
        state = self._state_from_region(region, decision_time_s)
        state["place_scaffold_key"] = key
        node = {
            "node_id": node_id,
            "node_version_id": opaque_id(
                self.pre_hash, PLACE_SCAFFOLD_ID, self.tick, node_id,
                "birth", prefix="node-version",
            ),
            "node_type": "place",
            "lifecycle": "confirmed",
            "valid_from": self.tick,
            "valid_to": None,
            "evidence_refs": [f"observation:{region['mask_sha256']}"],
            "latent_refs": [],
            "canonical_id": None,
            "predecessor_ids": [],
            "provenance": [f"{PLACE_SCAFFOLD_ID}:birth"],
            STATE_KEY: state,
        }
        self.graph["nodes"].append(node)
        self.created_nodes.append(str(node["node_version_id"]))
        return node

    def create_edge(
        self, relation: Mapping[str, Any], *, source_node_id: str,
        target_node_id: str,
    ) -> dict[str, Any]:
        edge_id = opaque_id(
            self.pre_hash, self.method_id, self.tick, relation["relation_id"],
            source_node_id, target_node_id, relation["relation"],
            len(self.created_edges), prefix="edge",
        )
        version_id = self._new_edge_version_id(edge_id, "birth")
        edge = {
            "edge_id": edge_id,
            "edge_version_id": version_id,
            "source": source_node_id,
            "target": target_node_id,
            "relation": relation["relation"],
            "frame": "map",
            "valid_from": self.tick,
            "valid_to": None,
            "evidence_refs": [f"observation:{relation['support_sha256']}"],
            "provenance": [f"{self.method_id}:relation-birth"],
        }
        self.graph["edges"].append(edge)
        self.created_edges.append(version_id)
        self.templates.append("BIRTH")
        return edge

    def bind_edge(
        self, edge: Mapping[str, Any], relation: Mapping[str, Any],
    ) -> dict[str, Any]:
        current = next(
            item for item in self.graph["edges"]
            if item["edge_version_id"] == edge["edge_version_id"]
        )
        if current["valid_to"] is not None:
            raise ValueError("relation BIND target must be open")
        evidence = f"observation:{relation['support_sha256']}"
        if evidence not in current["evidence_refs"]:
            current["evidence_refs"].append(evidence)
        provenance = f"{self.method_id}:relation-bind"
        if provenance not in current["provenance"]:
            current["provenance"].append(provenance)
        self.templates.append("BIND")
        return current

    def relink_edge(
        self, edge: Mapping[str, Any], relation: Mapping[str, Any], *,
        target_node_id: str,
    ) -> dict[str, Any]:
        current = next(
            item for item in self.graph["edges"]
            if item["edge_version_id"] == edge["edge_version_id"]
        )
        if current["valid_to"] is not None:
            raise ValueError("RELINK target must be open")
        if current["target"] == target_node_id:
            return self.bind_edge(current, relation)
        current["valid_to"] = self.tick
        self.closed_edges.append(current["edge_version_id"])
        version_id = self._new_edge_version_id(current["edge_id"], "relink")
        successor = clone_json(current)
        successor.update({
            "edge_version_id": version_id,
            "target": target_node_id,
            "valid_from": self.tick,
            "valid_to": None,
            "evidence_refs": list(dict.fromkeys(
                list(current["evidence_refs"])
                + [f"observation:{relation['support_sha256']}"]
            )),
            "provenance": list(current["provenance"])
            + [f"{self.method_id}:relink"],
        })
        self.graph["edges"].append(successor)
        self.created_edges.append(version_id)
        self.templates.append("RELINK")
        return successor

    def _validate_place_adjacency_context(
        self, relation: Mapping[str, Any], *, source_node_id: str,
        target_node_id: str,
    ) -> None:
        """Fail before mutation unless this is a trusted scaffold adjacency."""

        if self.method_id not in TRUSTED_SCAFFOLD_METHOD_IDS:
            raise ValueError(
                "untemplated edge operations are reserved for the trusted "
                "place adjacency scaffold"
            )
        if str(relation.get("relation")) not in SCAFFOLD_RELATIONS:
            raise ValueError(
                "untemplated scaffold edges must use the adjacent_to relation"
            )
        if source_node_id == target_node_id or not all(
            _node_type(self.graph, node_id) == "place"
            for node_id in (source_node_id, target_node_id)
        ):
            raise ValueError(
                "untemplated place adjacency requires two distinct open place nodes"
            )

    def _create_place_adjacency_edge(
        self, relation: Mapping[str, Any], *, source_node_id: str,
        target_node_id: str,
    ) -> dict[str, Any]:
        """Create one trusted deterministic adjacency without a learned atom."""

        self._validate_place_adjacency_context(
            relation,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
        )
        edge_id = opaque_id(
            self.pre_hash, self.method_id, self.tick, relation["relation_id"],
            source_node_id, target_node_id, "adjacent_to",
            len(self.created_edges), prefix="edge",
        )
        version_id = self._new_edge_version_id(edge_id, "birth")
        edge = {
            "edge_id": edge_id,
            "edge_version_id": version_id,
            "source": source_node_id,
            "target": target_node_id,
            "relation": "adjacent_to",
            "frame": "map",
            "valid_from": self.tick,
            "valid_to": None,
            "evidence_refs": [f"observation:{relation['support_sha256']}"],
            "provenance": [f"{self.method_id}:adjacency-birth"],
        }
        self.graph["edges"].append(edge)
        self.created_edges.append(version_id)
        return edge

    def _bind_place_adjacency_edge(
        self, edge: Mapping[str, Any], relation: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Bind evidence to one trusted deterministic adjacency without an atom."""

        current = next(
            item for item in self.graph["edges"]
            if item["edge_version_id"] == edge["edge_version_id"]
        )
        self._validate_place_adjacency_context(
            {
                **dict(relation),
                "relation": current.get("relation"),
            },
            source_node_id=str(current["source"]),
            target_node_id=str(current["target"]),
        )
        if current["valid_to"] is not None:
            raise ValueError("place adjacency BIND target must be open")
        evidence = f"observation:{relation['support_sha256']}"
        if evidence not in current["evidence_refs"]:
            current["evidence_refs"].append(evidence)
        provenance = f"{self.method_id}:adjacency-bind"
        if provenance not in current["provenance"]:
            current["provenance"].append(provenance)
        return current

    def _open_place_scaffold_index(self) -> dict[str, dict[str, Any]]:
        index: dict[str, dict[str, Any]] = {}
        for node in self.graph["nodes"]:
            if node.get("valid_to") is not None or node.get("node_type") != "place":
                continue
            key = (observation_state(node) or {}).get("place_scaffold_key")
            if type(key) is not str:
                continue
            if key in index:
                raise ValueError("place scaffold key has multiple open nodes")
            index[key] = node
        return index

    def _place_cell_size_m(self, nodes: Sequence[Mapping[str, Any]]) -> float:
        sizes = set()
        for node in nodes:
            extent = (observation_state(node) or {}).get("extent_m")
            if type(extent) is not list or len(extent) != 3:
                raise ValueError("place scaffold node is missing its cell extent")
            width = finite_number(extent[0], "place cell width")
            depth = finite_number(extent[2], "place cell depth")
            if width <= 0.0 or not math.isclose(width, depth, abs_tol=1e-9):
                raise ValueError("place cells must be positive and square")
            sizes.add(round(width, 9))
        if len(sizes) != 1:
            raise ValueError("open place scaffold cells disagree on cell size")
        return float(next(iter(sizes)))

    def apply_place_adjacency(
        self, relations: Sequence[Mapping[str, Any]],
        region_node_ids: Mapping[str, str],
    ) -> dict[str, int]:
        """Maintain the deterministic adjacency of the shared place scaffold.

        白话：这一步解决"地面格之间挨着不挨着，本来就由格坐标决定，不该让记忆
        方法去猜"的问题。输入是本帧的地点格到骨架节点的对应和本帧公开的
        `adjacent_to` 观测，输出是骨架自己维护的相邻边及计数；例如本帧新见的格
        (3,6) 会直接与上一帧就已经在图里的格 (3,5) 建立相邻边，本帧同时可见的
        一对则改用该观测的公开支持摘要。它不产生候选事务、不判断可通行，也不
        处理 `located_at` 或 `supported_by`。
        """

        counts = {
            "born": 0, "bound": 0, "deduplicated": 0,
            "observation_supported": 0, "coordinate_derived": 0,
        }
        index = self._open_place_scaffold_index()
        node_to_key = {
            str(node["node_id"]): key for key, node in index.items()
        }
        observed: dict[tuple[str, str], Mapping[str, Any]] = {}
        for relation in relations:
            if str(relation["relation"]) not in SCAFFOLD_RELATIONS:
                continue
            if not all(
                str(relation[field]) in region_node_ids
                for field in ("source_region_id", "target_region_id")
            ):
                raise ValueError(
                    "place adjacency endpoints must be current place regions"
                )
            source, target, _ = canonical_relation_observation(
                relation, region_node_ids,
            )
            if not all(node_id in node_to_key for node_id in (source, target)):
                raise ValueError(
                    "place adjacency requires two open place scaffold nodes"
                )
            observed[(source, target)] = relation

        current_nodes = sorted(
            {
                node_id for node_id in region_node_ids.values()
                if str(node_id) in node_to_key
            },
            key=str,
        )
        if not current_nodes:
            return counts
        cell = self._place_cell_size_m(
            [index[node_to_key[str(node_id)]] for node_id in current_nodes]
        )
        pairs: list[tuple[str, str]] = []
        for node_id in current_nodes:
            centre_x, centre_z = (
                float(part) for part in node_to_key[str(node_id)].split(":")
            )
            for offset_x, offset_z in (
                (cell, 0.0), (-cell, 0.0), (0.0, cell), (0.0, -cell),
            ):
                neighbour = index.get(place_scaffold_key_from_centre(
                    centre_x + offset_x, centre_z + offset_z,
                ))
                if neighbour is None:
                    continue
                pair = tuple(sorted((str(node_id), str(neighbour["node_id"]))))
                if pair[0] == pair[1]:
                    continue
                if pair in pairs:
                    counts["deduplicated"] += 1
                    continue
                pairs.append(pair)  # type: ignore[arg-type]

        for source, target in sorted(pairs):
            relation = observed.get((source, target))
            if relation is None:
                support = _sha256_json([
                    "vsmt.place.scaffold.adjacency.v1",
                    node_to_key[source], node_to_key[target],
                ])
                normalized = {
                    "relation_id": f"scaffold-adjacency:{support[:16]}",
                    "relation": "adjacent_to",
                    "support_sha256": support,
                }
                counts["coordinate_derived"] += 1
            else:
                normalized = dict(relation)
                normalized["relation"] = "adjacent_to"
                counts["observation_supported"] += 1
            exact = sorted((
                edge for edge in open_edges(self.graph)
                if edge["source"] == source
                and edge["target"] == target
                and edge["relation"] == "adjacent_to"
            ), key=lambda edge: str(edge["edge_id"]))
            if exact:
                self._bind_place_adjacency_edge(exact[0], normalized)
                counts["bound"] += 1
                continue
            self._create_place_adjacency_edge(
                normalized, source_node_id=source, target_node_id=target,
            )
            counts["born"] += 1
        return counts

    def apply_relation_observations(
        self, relations: Sequence[Mapping[str, Any]],
        region_node_ids: Mapping[str, str],
    ) -> dict[str, int]:
        counts = {
            "born": 0, "bound": 0, "relinked": 0, "inverse_deduplicated": 0,
            "scaffold_maintained": 0,
        }
        seen: set[tuple[str, str, str, str]] = set()
        for relation in relations:
            if str(relation["relation"]) in SCAFFOLD_RELATIONS:
                counts["scaffold_maintained"] += 1
                continue
            source, target, relation_kind = canonical_relation_observation(
                relation, region_node_ids,
            )
            signature = (
                source, target, relation_kind, str(relation["support_sha256"]),
            )
            if signature in seen:
                counts["inverse_deduplicated"] += 1
                continue
            seen.add(signature)
            normalized = dict(relation)
            normalized["relation"] = relation_kind
            edges = open_edges(self.graph)
            exact = sorted((
                edge for edge in edges
                if edge["source"] == source
                and edge["target"] == target
                and edge["relation"] == relation_kind
            ), key=lambda edge: str(edge["edge_id"]))
            if exact:
                self.bind_edge(exact[0], normalized)
                counts["bound"] += 1
                continue
            movable = sorted((
                edge for edge in edges
                if edge["source"] == source
                and edge["relation"] == relation_kind
                and relation_kind in {"located_at", "supported_by"}
            ), key=lambda edge: str(edge["edge_id"]))
            if movable:
                self.relink_edge(movable[0], normalized, target_node_id=target)
                counts["relinked"] += 1
                continue
            self.create_edge(
                normalized, source_node_id=source, target_node_id=target,
            )
            counts["born"] += 1
        return counts

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
        if node.get("lifecycle") != "dormant" or node.get("valid_to") is not None:
            raise ValueError("REACTIVATE requires one open dormant node version")
        current = next(
            item for item in self.graph["nodes"]
            if item["node_version_id"] == node["node_version_id"]
        )
        current["valid_to"] = self.tick
        self.closed_nodes.append(str(current["node_version_id"]))
        state = self._state_from_region(
            region, decision_time_s, previous=observation_state(current), fused=True,
        )
        state.update(clone_json(dict(state_updates)))
        state["missed_observation_opportunities"] = 0
        evidence_refs = list(dict.fromkeys(
            list(current.get("evidence_refs", []))
            + [f"observation:{region['mask_sha256']}"]
        ))
        prior_lifecycle = (observation_state(current) or {}).get(
            "pre_dormancy_lifecycle", "confirmed",
        )
        successor_lifecycle = (
            "candidate"
            if prior_lifecycle == "candidate" and len(evidence_refs) < 2
            else "confirmed"
        )
        version_id = self._new_version_id(node["node_id"], "reactivate")
        successor = clone_json(current)
        successor.update({
            "node_version_id": version_id,
            "lifecycle": successor_lifecycle,
            "valid_from": self.tick,
            "valid_to": None,
            "evidence_refs": evidence_refs,
            "predecessor_ids": [current["node_version_id"]],
            "provenance": list(current["provenance"])
            + [f"{self.method_id}:reactivate"],
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
        for state in (winner_state, loser_state):
            recorded_threshold = state.get(
                "support_envelope_reliability_threshold"
            )
            if (
                type(recorded_threshold) not in {int, float}
                or not math.isclose(
                    float(recorded_threshold),
                    self.support_envelope_reliability_threshold,
                    abs_tol=1e-12,
                )
            ):
                raise ValueError(
                    "MERGE inputs must use the shared support-envelope threshold"
                )
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
        self._canonicalize_merge_relations(
            canonical_node_id=str(winner["node_id"]),
            source_node_ids={str(winner["node_id"]), str(loser["node_id"])},
        )
        merged = self.update_node(
            winner, synthetic_region,
            max(float(winner_state["last_seen_s"]), float(loser_state["last_seen_s"])),
            fused=False, template="MERGE",
            state_updates={"observation_count": total},
        )
        merged_state = observation_state(merged)
        if merged_state is None:
            raise ValueError("MERGE successor lost observation state")
        latest_state = (
            loser_state
            if float(loser_state["last_seen_s"]) > float(winner_state["last_seen_s"])
            else winner_state
        )
        for key in ("observation_aabb_min_m", "observation_aabb_max_m"):
            merged_state[key] = clone_json(latest_state.get(key))
        left_lower = winner_state.get("support_envelope_min_m")
        right_lower = loser_state.get("support_envelope_min_m")
        left_upper = winner_state.get("support_envelope_max_m")
        right_upper = loser_state.get("support_envelope_max_m")
        if all(type(value) is list and len(value) == 3 for value in (
            left_lower, right_lower, left_upper, right_upper,
        )):
            merged_state["support_envelope_min_m"] = [
                min(float(left_lower[axis]), float(right_lower[axis]))
                for axis in range(3)
            ]
            merged_state["support_envelope_max_m"] = [
                max(float(left_upper[axis]), float(right_upper[axis]))
                for axis in range(3)
            ]
            merged_state["support_envelope_observation_count"] = (
                int(winner_state.get("support_envelope_observation_count", 0))
                + int(loser_state.get("support_envelope_observation_count", 0))
            )
        current_loser = next(
            item for item in self.graph["nodes"]
            if item["node_version_id"] == loser["node_version_id"]
        )
        if current_loser["valid_to"] is None:
            current_loser["valid_to"] = self.tick
            self.closed_nodes.append(current_loser["node_version_id"])
        alias = clone_json(current_loser)
        alias.update({
            "node_version_id": self._new_version_id(
                str(current_loser["node_id"]), "merge-alias",
            ),
            "lifecycle": "alias",
            "canonical_id": str(winner["node_id"]),
            "valid_from": self.tick,
            "valid_to": None,
            "evidence_refs": [],
            "latent_refs": [],
            "predecessor_ids": [current_loser["node_version_id"]],
            "provenance": list(current_loser["provenance"])
            + [f"{self.method_id}:merge-alias"],
        })
        self.graph["nodes"].append(alias)
        self.created_nodes.append(str(alias["node_version_id"]))
        if any(
            edge.get("valid_to") is None
            and current_loser["node_id"] in {edge["source"], edge["target"]}
            for edge in self.graph["edges"]
        ):
            raise ValueError("MERGE left an open relation on the retired identity")
        return merged

    def _canonicalize_merge_relations(
        self, *, canonical_node_id: str, source_node_ids: set[str],
    ) -> None:
        incident = sorted((
            edge for edge in self.graph["edges"]
            if edge.get("valid_to") is None
            and source_node_ids & {str(edge["source"]), str(edge["target"])}
        ), key=lambda edge: (
            int(edge["valid_from"]), str(edge["edge_id"]),
            str(edge["edge_version_id"]),
        ))
        groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
        for edge in incident:
            edge["valid_to"] = self.tick
            self.closed_edges.append(str(edge["edge_version_id"]))
            source = (
                canonical_node_id
                if edge["source"] in source_node_ids else str(edge["source"])
            )
            target = (
                canonical_node_id
                if edge["target"] in source_node_ids else str(edge["target"])
            )
            if source == target:
                continue
            groups.setdefault(
                (source, target, str(edge["relation"]), str(edge["frame"])), [],
            ).append(edge)

        for signature, group in sorted(groups.items()):
            source, target, relation, frame = signature
            identity = min(group, key=lambda edge: (
                int(edge["valid_from"]), str(edge["edge_id"]),
                str(edge["edge_version_id"]),
            ))
            predecessor_versions = sorted(
                str(edge["edge_version_id"]) for edge in group
            )
            successor = clone_json(identity)
            successor.update({
                "edge_version_id": self._new_edge_version_id(
                    str(identity["edge_id"]), "merge-relation",
                ),
                "source": source,
                "target": target,
                "relation": relation,
                "frame": frame,
                "valid_from": self.tick,
                "valid_to": None,
                "evidence_refs": list(dict.fromkeys(
                    reference for edge in group for reference in edge["evidence_refs"]
                )),
                "provenance": list(dict.fromkeys([
                    *(reference for edge in group for reference in edge["provenance"]),
                    *(f"merge_source_edge:{version}" for version in predecessor_versions),
                    f"{self.method_id}:merge-relation",
                ])),
            })
            self.graph["edges"].append(successor)
            self.created_edges.append(str(successor["edge_version_id"]))

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
            "observed_template_instances": list(self.templates),
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
