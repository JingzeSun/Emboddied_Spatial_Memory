"""Clean-room mechanism-level memory adapters for the VSMT comparison.

These are independent task adaptations, not official reproductions.  TAF is
inspired by ConceptGraphs (ICRA 2024), ELU by Fusion++ (3DV 2018), Dengler et
al. (ECMR 2021), and POCD (RSS 2022), and WFR by Khronos (RSS 2024).  No
upstream source, class layout, default threshold, or test was copied.

Sources:
https://arxiv.org/abs/2309.16650
https://arxiv.org/abs/1808.08378
https://arxiv.org/abs/2011.06895
https://www.roboticsproceedings.org/rss18/p013.html
https://www.roboticsproceedings.org/rss20/p081.html
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Any, Mapping

from .contracts import AdapterInput
from .graph_ops import (
    GraphRevision,
    association_score,
    centroid_distance,
    covering_free_space_times,
    finite_number,
    node_pair_score,
    observation_state,
    open_nodes,
    validate_threshold,
)
from .place_scaffold import place_region_node_ids


LEARNED_STRUCTURE_KINDS = {"entity", "surface", "fragment"}


def _positive(value: Any, name: str) -> float:
    result = finite_number(value, name)
    if result <= 0.0:
        raise ValueError(f"{name} must be positive")
    return result


def _positive_integer(value: Any, name: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _weights(visual: float, geometry: float) -> None:
    validate_threshold(visual, "visual_weight", low=0.0, high=1.0)
    validate_threshold(geometry, "geometry_weight", low=0.0, high=1.0)
    if not math.isclose(visual + geometry, 1.0, abs_tol=1e-12):
        raise ValueError("visual_weight and geometry_weight must sum to one")


def _validate_association_rules(
    rules: Mapping[str, Mapping[str, float]], *,
    expected_fields: set[str], name: str,
) -> None:
    if type(rules) is not dict or set(rules) != LEARNED_STRUCTURE_KINDS:
        raise ValueError(
            f"{name} must explicitly cover entity, surface, and fragment but not place"
        )
    for kind, rule in rules.items():
        if type(rule) is not dict or set(rule) != expected_fields:
            raise ValueError(f"{name}.{kind} is malformed")
        if {"visual_weight", "geometry_weight"} <= expected_fields:
            _weights(rule["visual_weight"], rule["geometry_weight"])
        if "geometry_scale_m" in expected_fields:
            _positive(rule["geometry_scale_m"], f"{name}.{kind}.geometry_scale_m")
        for field in expected_fields & {
            "association_threshold", "duplicate_threshold",
        }:
            validate_threshold(
                rule[field], f"{name}.{kind}.{field}", low=0.0, high=1.0,
            )


@dataclass(frozen=True)
class LOWConfig:
    maximum_centroid_distance_m_by_structure_kind: Mapping[str, float]

    def __post_init__(self) -> None:
        rules = self.maximum_centroid_distance_m_by_structure_kind
        if type(rules) is not dict or set(rules) != LEARNED_STRUCTURE_KINDS:
            raise ValueError(
                "LOW distance rules must explicitly cover entity, surface, and "
                "fragment but not place"
            )
        for kind, value in rules.items():
            _positive(value, f"maximum_centroid_distance_m.{kind}")

    def maximum_distance(self, structure_kind: str) -> float:
        return self.maximum_centroid_distance_m_by_structure_kind[structure_kind]


@dataclass(frozen=True)
class TAFConfig:
    association_rules: Mapping[str, Mapping[str, float]]
    fusion_interval: int

    def __post_init__(self) -> None:
        _validate_association_rules(
            self.association_rules,
            expected_fields={
                "visual_weight", "geometry_weight", "geometry_scale_m",
                "association_threshold", "duplicate_threshold",
            },
            name="TAF association_rules",
        )
        _positive_integer(self.fusion_interval, "fusion_interval")

    def rule(self, structure_kind: str) -> Mapping[str, float]:
        return self.association_rules[structure_kind]


@dataclass(frozen=True)
class ELUConfig:
    association_rules: Mapping[str, Mapping[str, float]]
    free_space_reliability_threshold: float
    free_space_target_expansion_m: float
    minimum_free_space_time_separation_s: float
    birth_log_odds: float
    positive_log_odds_increment: float
    negative_log_odds_decrement: float
    dormant_log_odds_threshold: float
    retract_log_odds_threshold: float

    def __post_init__(self) -> None:
        _validate_association_rules(
            self.association_rules,
            expected_fields={
                "visual_weight", "geometry_weight", "geometry_scale_m",
                "association_threshold",
            },
            name="ELU association_rules",
        )
        validate_threshold(
            self.free_space_reliability_threshold,
            "free_space_reliability_threshold", low=0.0, high=1.0,
        )
        if finite_number(
            self.free_space_target_expansion_m,
            "free_space_target_expansion_m",
        ) < 0.0:
            raise ValueError("free_space_target_expansion_m must be non-negative")
        _positive(
            self.minimum_free_space_time_separation_s,
            "minimum_free_space_time_separation_s",
        )
        finite_number(self.birth_log_odds, "birth_log_odds")
        _positive(self.positive_log_odds_increment, "positive_log_odds_increment")
        _positive(self.negative_log_odds_decrement, "negative_log_odds_decrement")
        finite_number(self.dormant_log_odds_threshold,
                      "dormant_log_odds_threshold")
        finite_number(self.retract_log_odds_threshold,
                      "retract_log_odds_threshold")
        if self.retract_log_odds_threshold >= self.dormant_log_odds_threshold:
            raise ValueError("retract threshold must be below dormant threshold")

    def rule(self, structure_kind: str) -> Mapping[str, float]:
        return self.association_rules[structure_kind]


@dataclass(frozen=True)
class WFRConfig:
    association_rules: Mapping[str, Mapping[str, float]]
    confirmation_observations: int
    reconciliation_interval: int
    absent_reconciliations_before_retract: int
    free_space_reliability_threshold: float
    free_space_target_expansion_m: float
    minimum_free_space_time_separation_s: float

    def __post_init__(self) -> None:
        _validate_association_rules(
            self.association_rules,
            expected_fields={
                "visual_weight", "geometry_weight", "geometry_scale_m",
                "association_threshold", "duplicate_threshold",
            },
            name="WFR association_rules",
        )
        _positive_integer(self.confirmation_observations,
                          "confirmation_observations")
        _positive_integer(self.reconciliation_interval,
                          "reconciliation_interval")
        _positive_integer(self.absent_reconciliations_before_retract,
                          "absent_reconciliations_before_retract")
        validate_threshold(
            self.free_space_reliability_threshold,
            "free_space_reliability_threshold", low=0.0, high=1.0,
        )
        if finite_number(
            self.free_space_target_expansion_m,
            "free_space_target_expansion_m",
        ) < 0.0:
            raise ValueError("free_space_target_expansion_m must be non-negative")
        _positive(
            self.minimum_free_space_time_separation_s,
            "minimum_free_space_time_separation_s",
        )

    def rule(self, structure_kind: str) -> Mapping[str, float]:
        return self.association_rules[structure_kind]


def _ranked_matches(
    region: Mapping[str, Any], nodes: list[dict[str, Any]], *,
    rule: Mapping[str, float],
) -> list[tuple[float, dict[str, Any]]]:
    rows = [
        (
            association_score(
                region, node,
                visual_weight=rule["visual_weight"],
                geometry_weight=rule["geometry_weight"],
                geometry_scale_m=rule["geometry_scale_m"],
            ),
            node,
        )
        for node in nodes
    ]
    return sorted(rows, key=lambda item: (-item[0], str(item[1]["node_id"])))


def _current_node(revision: GraphRevision, node_id: str) -> dict[str, Any] | None:
    matches = [
        node for node in revision.graph["nodes"]
        if node["node_id"] == node_id and node.get("valid_to") is None
    ]
    if len(matches) > 1:
        raise ValueError(f"node {node_id!r} has multiple open versions")
    return matches[0] if matches else None


def _greedy_duplicate_merges(
    revision: GraphRevision, *,
    association_rules: Mapping[str, Mapping[str, float]],
) -> int:
    merge_count = 0
    while True:
        nodes = sorted((
            node for node in open_nodes(revision.graph)
            if node.get("node_type") != "place"
        ), key=lambda node: str(node["node_id"]))
        choices: list[tuple[float, str, str, dict[str, Any], dict[str, Any]]] = []
        for left_index, left in enumerate(nodes):
            for right in nodes[left_index + 1:]:
                if left.get("node_type") != right.get("node_type"):
                    continue
                rule = association_rules[str(left["node_type"])]
                score = node_pair_score(
                    left, right,
                    visual_weight=rule["visual_weight"],
                    geometry_weight=rule["geometry_weight"],
                    geometry_scale_m=rule["geometry_scale_m"],
                )
                if score >= rule["duplicate_threshold"]:
                    choices.append((
                        score, str(left["node_id"]), str(right["node_id"]), left, right,
                    ))
        if not choices:
            return merge_count
        _, _, _, winner, loser = sorted(
            choices, key=lambda item: (-item[0], item[1], item[2])
        )[0]
        revision.merge_nodes(winner, loser)
        merge_count += 1


class LOWAdapter:
    """Last-Observation Overwrite naïve baseline."""

    method_id = "low.adapter.v1"

    def __init__(self, config: LOWConfig):
        self.config = config

    def update(self, model_input: AdapterInput) -> Mapping[str, Any]:
        started = time.perf_counter()
        revision = GraphRevision(model_input["prior_memory"], method_id=self.method_id)
        used: set[str] = set()
        region_node_ids = place_region_node_ids(
            model_input["region_observations"], revision.graph,
        )
        matched = 0
        born = 0
        for region in model_input["region_observations"]:
            if region["structure_kind"] == "place":
                continue
            eligible = [
                node for node in open_nodes(revision.graph, include_dormant=False)
                if node["node_id"] not in used
                and node.get("node_type") == region["structure_kind"]
            ]
            ranked = sorted(
                ((
                    centroid_distance(region, observation_state(node) or {}), node
                ) for node in eligible),
                key=lambda item: (item[0], str(item[1]["node_id"])),
            )
            if ranked and ranked[0][0] <= self.config.maximum_distance(
                str(region["structure_kind"])
            ):
                node = ranked[0][1]
                updated = revision.update_node(
                    node, region, float(model_input["decision_time_s"]),
                    fused=False, template="BIND",
                )
                region_node_ids[str(region["region_id"])] = str(updated["node_id"])
                used.add(str(node["node_id"]))
                matched += 1
            else:
                created = revision.create_node(
                    region, float(model_input["decision_time_s"]),
                    lifecycle="confirmed",
                )
                region_node_ids[str(region["region_id"])] = str(created["node_id"])
                born += 1
        relation_counts = revision.apply_relation_observations(
            model_input["relation_observations"], region_node_ids,
        )
        confidence = (
            sum(float(region["reliability"])
                for region in model_input["region_observations"])
            / max(1, len(model_input["region_observations"]))
        )
        return revision.finish(
            confidence=confidence,
            runtime_ms=(time.perf_counter() - started) * 1000.0,
            diagnostics={
                "matched_regions": matched,
                "born_regions": born,
                "relation_updates": relation_counts,
            },
        )


class TAFAdapter:
    """Thresholded Association and Fusion mechanism-level adaptation."""

    method_id = "taf.adapter.v1"

    def __init__(self, config: TAFConfig):
        self.config = config

    def update(self, model_input: AdapterInput) -> Mapping[str, Any]:
        started = time.perf_counter()
        revision = GraphRevision(model_input["prior_memory"], method_id=self.method_id)
        used: set[str] = set()
        region_node_ids = place_region_node_ids(
            model_input["region_observations"], revision.graph,
        )
        matched = 0
        born = 0
        for region in model_input["region_observations"]:
            if region["structure_kind"] == "place":
                continue
            rule = self.config.rule(str(region["structure_kind"]))
            eligible = [
                node for node in open_nodes(revision.graph, include_dormant=False)
                if node["node_id"] not in used
            ]
            ranked = _ranked_matches(
                region, eligible, rule=rule,
            )
            if ranked and ranked[0][0] >= rule["association_threshold"]:
                node = ranked[0][1]
                updated = revision.update_node(
                    node, region, float(model_input["decision_time_s"]),
                    fused=True, template="BIND",
                )
                region_node_ids[str(region["region_id"])] = str(updated["node_id"])
                used.add(str(node["node_id"]))
                matched += 1
            else:
                created = revision.create_node(
                    region, float(model_input["decision_time_s"]),
                    lifecycle="confirmed",
                )
                region_node_ids[str(region["region_id"])] = str(created["node_id"])
                born += 1
        relation_counts = revision.apply_relation_observations(
            model_input["relation_observations"], region_node_ids,
        )
        merged = 0
        if revision.tick % self.config.fusion_interval == 0:
            merged = _greedy_duplicate_merges(
                revision, association_rules=self.config.association_rules,
            )
        confidence = (
            sum(float(region["reliability"])
                for region in model_input["region_observations"])
            / max(1, len(model_input["region_observations"]))
        )
        return revision.finish(
            confidence=confidence,
            runtime_ms=(time.perf_counter() - started) * 1000.0,
            diagnostics={
                "matched_regions": matched,
                "born_regions": born,
                "merged_pairs": merged,
                "relation_updates": relation_counts,
            },
        )


class ELUAdapter:
    """Existence-Likelihood Updating mechanism-level adaptation."""

    method_id = "elu.adapter.v1"

    def __init__(self, config: ELUConfig):
        self.config = config

    def _score(self, region: Mapping[str, Any], node: Mapping[str, Any]) -> float:
        rule = self.config.rule(str(region["structure_kind"]))
        return association_score(
            region, node,
            visual_weight=rule["visual_weight"],
            geometry_weight=rule["geometry_weight"],
            geometry_scale_m=rule["geometry_scale_m"],
        )

    def update(self, model_input: AdapterInput) -> Mapping[str, Any]:
        started = time.perf_counter()
        revision = GraphRevision(model_input["prior_memory"], method_id=self.method_id)
        initial_open = [
            node for node in open_nodes(revision.graph)
            if node.get("node_type") != "place"
        ]
        used: set[str] = set()
        region_node_ids = place_region_node_ids(
            model_input["region_observations"], revision.graph,
        )
        reactivated = 0
        born = 0
        positive = 0
        for region in model_input["region_observations"]:
            if region["structure_kind"] == "place":
                continue
            rule = self.config.rule(str(region["structure_kind"]))
            active_ranked = _ranked_matches(
                region, [node for node in initial_open if node["node_id"] not in used],
                rule=rule,
            )
            if active_ranked and active_ranked[0][0] >= rule["association_threshold"]:
                node = active_ranked[0][1]
                state = observation_state(node) or {}
                log_odds = float(state.get("existence_log_odds", self.config.birth_log_odds))
                log_odds += (
                    self.config.positive_log_odds_increment
                    * float(region["reliability"])
                )
                updated = revision.update_node(
                    node, region, float(model_input["decision_time_s"]),
                    lifecycle="confirmed", fused=True,
                    template="REACTIVATE" if node["lifecycle"] == "dormant" else "BIND",
                    state_updates={"existence_log_odds": log_odds},
                )
                region_node_ids[str(region["region_id"])] = str(updated["node_id"])
                used.add(str(node["node_id"]))
                positive += 1
                if node["lifecycle"] == "dormant":
                    reactivated += 1
                continue

            created = revision.create_node(
                region, float(model_input["decision_time_s"]),
                lifecycle="confirmed",
                state_updates={"existence_log_odds": self.config.birth_log_odds},
            )
            region_node_ids[str(region["region_id"])] = str(created["node_id"])
            born += 1

        relation_counts = revision.apply_relation_observations(
            model_input["relation_observations"], region_node_ids,
        )

        dormant = 0
        retracted = 0
        for original in initial_open:
            node_id = str(original["node_id"])
            if node_id in used:
                continue
            current = _current_node(revision, node_id)
            if current is None or len(covering_free_space_times(
                current, model_input["free_space_observations"],
                minimum_reliability=self.config.free_space_reliability_threshold,
                target_expansion_m=self.config.free_space_target_expansion_m,
                minimum_time_separation_s=(
                    self.config.minimum_free_space_time_separation_s
                ),
            )) < 2:
                continue
            state = observation_state(current) or {}
            log_odds = float(state.get("existence_log_odds", self.config.birth_log_odds))
            log_odds -= self.config.negative_log_odds_decrement
            if log_odds <= self.config.retract_log_odds_threshold:
                revision.lifecycle_node(
                    current, lifecycle="retracted", template="RETRACT",
                    state_updates={"existence_log_odds": log_odds}, terminal=True,
                )
                retracted += 1
            elif log_odds <= self.config.dormant_log_odds_threshold:
                revision.lifecycle_node(
                    current, lifecycle="dormant", template=None,
                    state_updates={"existence_log_odds": log_odds},
                )
                dormant += 1

        evidence_count = positive + reactivated + born + dormant + retracted
        confidence = min(1.0, evidence_count / max(1, len(initial_open) + len(
            model_input["region_observations"]
        )))
        return revision.finish(
            confidence=confidence,
            runtime_ms=(time.perf_counter() - started) * 1000.0,
            diagnostics={
                "positive_updates": positive,
                "born_regions": born,
                "reactivated_nodes": reactivated,
                "dormant_nodes": dormant,
                "retracted_nodes": retracted,
                "relation_updates": relation_counts,
            },
        )


class WFRAdapter:
    """Windowed Fragment Reconciliation mechanism-level adaptation."""

    method_id = "wfr.adapter.v1"

    def __init__(self, config: WFRConfig):
        self.config = config

    def update(self, model_input: AdapterInput) -> Mapping[str, Any]:
        started = time.perf_counter()
        revision = GraphRevision(model_input["prior_memory"], method_id=self.method_id)
        initial_open = [
            node for node in open_nodes(revision.graph)
            if node.get("node_type") != "place"
        ]
        used: set[str] = set()
        region_node_ids = place_region_node_ids(
            model_input["region_observations"], revision.graph,
        )
        matched = 0
        fragments = 0
        for region in model_input["region_observations"]:
            if region["structure_kind"] == "place":
                continue
            rule = self.config.rule(str(region["structure_kind"]))
            ranked = _ranked_matches(
                region, [node for node in initial_open if node["node_id"] not in used],
                rule=rule,
            )
            if ranked and ranked[0][0] >= rule["association_threshold"]:
                node = ranked[0][1]
                state = observation_state(node) or {}
                updated = revision.update_node(
                    node, region, float(model_input["decision_time_s"]),
                    lifecycle=node["lifecycle"], fused=True, template="BIND",
                    state_updates={
                        "fragment_observations": int(
                            state.get("fragment_observations", 0)
                        ) + 1,
                        "absent_reconciliations": 0,
                    },
                )
                region_node_ids[str(region["region_id"])] = str(updated["node_id"])
                used.add(str(node["node_id"]))
                matched += 1
            else:
                created = revision.create_node(
                    region, float(model_input["decision_time_s"]),
                    lifecycle="candidate",
                    state_updates={
                        "fragment_observations": 1,
                        "absent_reconciliations": 0,
                    },
                )
                region_node_ids[str(region["region_id"])] = str(created["node_id"])
                fragments += 1

        relation_counts = revision.apply_relation_observations(
            model_input["relation_observations"], region_node_ids,
        )

        confirmed = 0
        retracted = 0
        merged = 0
        if revision.tick % self.config.reconciliation_interval == 0:
            for node in list(open_nodes(revision.graph)):
                current = _current_node(revision, str(node["node_id"]))
                if current is None:
                    continue
                state = observation_state(current) or {}
                if (
                    current["lifecycle"] == "candidate"
                    and int(state.get("fragment_observations", 0))
                    >= self.config.confirmation_observations
                ):
                    revision.lifecycle_node(
                        current, lifecycle="confirmed", template="BIND",
                        state_updates={"absent_reconciliations": 0},
                    )
                    confirmed += 1

            for original in initial_open:
                node_id = str(original["node_id"])
                if node_id in used:
                    continue
                current = _current_node(revision, node_id)
                if current is None or len(covering_free_space_times(
                    current, model_input["free_space_observations"],
                    minimum_reliability=(
                        self.config.free_space_reliability_threshold
                    ),
                    target_expansion_m=self.config.free_space_target_expansion_m,
                    minimum_time_separation_s=(
                        self.config.minimum_free_space_time_separation_s
                    ),
                )) < 2:
                    continue
                state = observation_state(current) or {}
                absent = int(state.get("absent_reconciliations", 0)) + 1
                if absent >= self.config.absent_reconciliations_before_retract:
                    revision.lifecycle_node(
                        current, lifecycle="retracted", template="RETRACT",
                        state_updates={"absent_reconciliations": absent}, terminal=True,
                    )
                    retracted += 1
                else:
                    revision.lifecycle_node(
                        current, lifecycle=current["lifecycle"], template=None,
                        state_updates={"absent_reconciliations": absent},
                    )

            merged = _greedy_duplicate_merges(
                revision, association_rules=self.config.association_rules,
            )

        confidence = min(1.0, (
            matched + confirmed + merged + retracted
        ) / max(1, len(model_input["region_observations"]) + len(initial_open)))
        return revision.finish(
            confidence=confidence,
            runtime_ms=(time.perf_counter() - started) * 1000.0,
            diagnostics={
                "matched_regions": matched,
                "new_fragments": fragments,
                "confirmed_fragments": confirmed,
                "merged_pairs": merged,
                "retracted_nodes": retracted,
                "relation_updates": relation_counts,
            },
        )
