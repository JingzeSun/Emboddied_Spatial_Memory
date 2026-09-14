"""Method-independent place and opportunity-based dormancy preparation.

白话：这个包装在五个方法运行前逐字节相同地更新地点证据，并用当前方法
自己的图判断实体是否连续错失了公开、未遮挡的观测机会。它不把离开视野
的墙钟时间当证据，也不读取 teacher、future 或 private 数据。
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

from cpmt.hashing import clone_json

from .contracts import build_adapter_input, canonical_sha256, validate_observation_packet
from .graph_ops import (
    GraphRevision,
    association_score,
    fully_covered_by_free_space,
    observation_state,
    open_nodes,
    validate_threshold,
)
from .place_scaffold import prepare_place_scaffold


SHARED_MAINTENANCE_ID = "vsmt.shared.dormancy.v2"


@dataclass(frozen=True)
class SharedMemoryConfig:
    """All scientific values are explicit; no opportunity rule is implicit."""

    support_envelope_reliability_threshold: float
    support_envelope_margin_m: float
    minimum_consecutive_missed_opportunities: int
    opportunity_reliability_threshold: float
    free_space_reliability_threshold: float
    association_visual_weight: float
    association_geometry_weight: float
    association_geometry_scale_m: float
    association_bind_threshold: float

    def __post_init__(self) -> None:
        validate_threshold(
            self.support_envelope_reliability_threshold,
            "support_envelope_reliability_threshold", low=0.0, high=1.0,
        )
        for name in (
            "opportunity_reliability_threshold",
            "free_space_reliability_threshold",
            "association_visual_weight",
            "association_geometry_weight",
            "association_bind_threshold",
        ):
            validate_threshold(getattr(self, name), name, low=0.0, high=1.0)
        if not math.isclose(
            float(self.association_visual_weight)
            + float(self.association_geometry_weight),
            1.0,
            abs_tol=1e-9,
        ):
            raise ValueError("shared association weights must sum to one")
        if (
            type(self.support_envelope_margin_m) not in {int, float}
            or not math.isfinite(float(self.support_envelope_margin_m))
            or float(self.support_envelope_margin_m) < 0.0
        ):
            raise ValueError("support_envelope_margin_m must be non-negative")
        if (
            type(self.association_geometry_scale_m) not in {int, float}
            or not math.isfinite(float(self.association_geometry_scale_m))
            or float(self.association_geometry_scale_m) <= 0.0
        ):
            raise ValueError("association_geometry_scale_m must be positive")
        if (
            type(self.minimum_consecutive_missed_opportunities) is not int
            or self.minimum_consecutive_missed_opportunities < 1
        ):
            raise ValueError(
                "minimum_consecutive_missed_opportunities must be positive"
            )


def _has_current_bind_eligible_region(
    node: Mapping[str, Any], regions: list[Mapping[str, Any]], *,
    config: SharedMemoryConfig,
) -> bool:
    return any(
        region.get("structure_kind") == "entity"
        and association_score(
            region,
            node,
            visual_weight=float(config.association_visual_weight),
            geometry_weight=float(config.association_geometry_weight),
            geometry_scale_m=float(config.association_geometry_scale_m),
        ) >= float(config.association_bind_threshold)
        for region in regions
    )


def _covered(
    node: Mapping[str, Any], observations: list[Mapping[str, Any]], *,
    minimum_reliability: float, margin_m: float,
    config: SharedMemoryConfig,
) -> bool:
    return fully_covered_by_free_space(
        node,
        observations,
        minimum_reliability=minimum_reliability,
        target_expansion_m=margin_m,
        support_reliability_threshold=(
            config.support_envelope_reliability_threshold
        ),
    )


def prepare_shared_memory(
    packet: Mapping[str, Any],
    prior_memory: Mapping[str, Any],
    *,
    config: SharedMemoryConfig,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Return one shared packet/memory pair and a public preparation audit."""

    prepared, scaffold_memory = prepare_place_scaffold(
        packet, prior_memory,
        support_envelope_reliability_threshold=(
            config.support_envelope_reliability_threshold
        ),
    )
    model_input = build_adapter_input(prepared, scaffold_memory)
    revision = GraphRevision(
        scaffold_memory, method_id=SHARED_MAINTENANCE_ID,
        support_envelope_reliability_threshold=(
            config.support_envelope_reliability_threshold
        ),
    )
    dormant_node_ids: list[str] = []
    reset_node_ids: list[str] = []
    missed_node_ids: list[str] = []
    visible_empty_node_ids: list[str] = []
    for node in sorted(open_nodes(revision.graph), key=lambda item: str(item["node_id"])):
        if (
            node.get("node_type") != "entity"
            or node.get("lifecycle") not in {"candidate", "confirmed"}
        ):
            continue
        state = observation_state(node)
        if state is None:
            continue
        missed = int(state.get("missed_observation_opportunities", 0))
        if missed < 0:
            raise ValueError("missed observation opportunity count is invalid")
        if _has_current_bind_eligible_region(
            node, model_input["region_observations"], config=config,
        ):
            if missed:
                revision.lifecycle_node(
                    node,
                    lifecycle=str(node["lifecycle"]),
                    template=None,
                    state_updates={"missed_observation_opportunities": 0},
                )
                reset_node_ids.append(str(node["node_id"]))
            continue
        if _covered(
            node,
            model_input["free_space_observations"],
            minimum_reliability=float(config.free_space_reliability_threshold),
            margin_m=float(config.support_envelope_margin_m),
            config=config,
        ):
            visible_empty_node_ids.append(str(node["node_id"]))
            continue
        if not _covered(
            node,
            model_input["visibility_observations"],
            minimum_reliability=float(config.opportunity_reliability_threshold),
            margin_m=0.0,
            config=config,
        ):
            continue
        updated_missed = missed + 1
        state_updates: dict[str, Any] = {
            "missed_observation_opportunities": updated_missed,
        }
        lifecycle = str(node["lifecycle"])
        if updated_missed >= config.minimum_consecutive_missed_opportunities:
            state_updates["pre_dormancy_lifecycle"] = lifecycle
            lifecycle = "dormant"
            dormant_node_ids.append(str(node["node_id"]))
        else:
            missed_node_ids.append(str(node["node_id"]))
        revision.lifecycle_node(
            node,
            lifecycle=lifecycle,
            template=None,
            state_updates=state_updates,
        )

    result = revision.finish(
        confidence=1.0,
        runtime_ms=0.0,
        diagnostics={
            "dormant_node_ids": dormant_node_ids,
            "missed_node_ids": missed_node_ids,
            "reset_node_ids": reset_node_ids,
            "visible_empty_node_ids": visible_empty_node_ids,
        },
    )
    memory = result["post_memory"]
    final_packet = clone_json(prepared)
    final_packet["prior_memory_ref"] = {
        "graph_version": memory["graph_version"],
        "graph_sha256": memory["graph_hash"],
    }
    validated = validate_observation_packet(final_packet)
    audit = {
        "schema_version": "vsmt-shared-memory-audit-v1",
        "input_pre_memory_sha256": prior_memory["graph_hash"],
        "place_scaffold_post_memory_sha256": scaffold_memory["graph_hash"],
        "post_memory_sha256": memory["graph_hash"],
        "minimum_consecutive_missed_opportunities": (
            config.minimum_consecutive_missed_opportunities
        ),
        "opportunity_reliability_threshold": float(
            config.opportunity_reliability_threshold
        ),
        "dormant_node_ids": dormant_node_ids,
        "missed_node_ids": missed_node_ids,
        "reset_node_ids": reset_node_ids,
        "visible_empty_node_ids": visible_empty_node_ids,
    }
    audit["audit_sha256"] = canonical_sha256(audit)
    return validated, memory, audit
