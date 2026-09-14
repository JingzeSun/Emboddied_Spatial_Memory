from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from cpmt.hashing import seal_graph  # noqa: E402
from vsmt.baselines import (  # noqa: E402
    ELUAdapter,
    ELUConfig,
    LOWAdapter,
    LOWConfig,
    TAFAdapter,
    TAFConfig,
    WFRAdapter,
    WFRConfig,
)
from vsmt.contracts import run_adapter  # noqa: E402
from vsmt.graph_ops import STATE_KEY  # noqa: E402
from vsmt.shared_memory import (  # noqa: E402
    SharedMemoryConfig,
    prepare_shared_memory,
)


def observed_node(
    node_id: str, *, centroid: list[float], descriptor: list[float],
    lifecycle: str = "confirmed", valid_to: int | None = None,
    observation_count: int = 1, state_updates: Mapping[str, Any] | None = None,
    node_type: str = "entity",
) -> dict[str, Any]:
    state = {
        "descriptor": descriptor,
        "centroid_m": centroid,
        "extent_m": [0.2, 0.2, 0.2],
        "reliability": 1.0,
        "last_seen_s": 0.0,
        "observation_count": observation_count,
    }
    if state_updates:
        state.update(state_updates)
    if node_type == "place":
        state["place_scaffold_key"] = f"{centroid[0]:.9f}:{centroid[2]:.9f}"
    return {
        "node_id": node_id,
        "node_version_id": f"{node_id}@v0",
        "node_type": node_type,
        "lifecycle": lifecycle,
        "valid_from": 0,
        "valid_to": valid_to,
        "evidence_refs": [f"observation:{node_id}"],
        "latent_refs": [],
        "canonical_id": None,
        "predecessor_ids": [],
        "provenance": ["fixture:public"],
        STATE_KEY: state,
    }


def memory(
    *nodes: Mapping[str, Any], edges: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    return seal_graph({
        "schema_version": "cpmt-0.2",
        "graph_id": "graph:baseline-fixture",
        "graph_version": "v0",
        "parent_version": None,
        "nodes": [deepcopy(dict(node)) for node in nodes],
        "edges": [deepcopy(dict(edge)) for edge in (edges or [])],
        "transaction_log": [],
    })


def region(
    *, centroid: list[float], descriptor: list[float], index: int = 0,
    kind: str = "entity",
) -> dict[str, Any]:
    return {
        "region_id": f"region:{index:04d}",
        "structure_kind": kind,
        "mask_sha256": f"{index + 3:x}" * 64,
        "descriptor": descriptor,
        "centroid_m": centroid,
        "extent_m": [0.2, 0.2, 0.2],
        "reliability": 1.0,
        "proposal_source_id": "fixed.region.v1",
    }


def packet(
    graph: Mapping[str, Any], *, regions: list[Mapping[str, Any]],
    include_free_space: bool = False,
    relations: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "vsmt-observation-packet-v2",
        "sample_id_hash": "1" * 64,
        "decision_time_s": 1.0,
        "rgbd_refs": {"rgb_sha256": "2" * 64, "depth_sha256": "3" * 64},
        "camera_pose": {
            "position_m": [0.0, 0.0, 1.0],
            "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
        },
        "robot_state": {"feature_names": [], "values": []},
        "past_actions": [],
        "region_observations": [deepcopy(dict(item)) for item in regions],
        "relation_observations": [
            deepcopy(dict(item)) for item in (relations or [])
        ],
        "free_space_observations": ([{
            "free_space_id": f"free:{index:04d}",
            "time_s": time_s,
            "halfspaces_world": [
                {"normal": [1.0, 0.0, 0.0], "offset_m": 1.0},
                {"normal": [-1.0, 0.0, 0.0], "offset_m": 1.0},
                {"normal": [0.0, 1.0, 0.0], "offset_m": 1.0},
                {"normal": [0.0, -1.0, 0.0], "offset_m": 1.0},
                {"normal": [0.0, 0.0, 1.0], "offset_m": 1.0},
                {"normal": [0.0, 0.0, -1.0], "offset_m": 1.0},
            ],
            "reliability": 1.0,
            "support_sha256": "4" * 64,
        } for index, time_s in enumerate((0.5, 1.0))] if include_free_space else []),
        "prior_memory_ref": {
            "graph_version": graph["graph_version"],
            "graph_sha256": graph["graph_hash"],
        },
        "public_constants": {
            "coordinate_frame": "map",
            "depth_unit": "metre",
            "descriptor_model_id": "dinov2.vits14",
            "proposal_model_id": "fixed.region.v1",
        },
    }


def association_rules(**updates: Any) -> dict[str, dict[str, float]]:
    values = {
        "visual_weight": 0.5,
        "geometry_weight": 0.5,
        "geometry_scale_m": 1.0,
        "association_threshold": 0.7,
    }
    values.update(updates)
    return {
        kind: dict(values) for kind in ("entity", "surface", "fragment")
    }


def low_config(distance: float) -> LOWConfig:
    return LOWConfig(maximum_centroid_distance_m_by_structure_kind={
        kind: distance for kind in ("entity", "surface", "fragment")
    })


def taf_config(**updates: Any) -> TAFConfig:
    fusion_interval = int(updates.pop("fusion_interval", 1))
    duplicate_threshold = float(updates.pop("duplicate_threshold", 0.9))
    return TAFConfig(
        association_rules=association_rules(
            duplicate_threshold=duplicate_threshold, **updates,
        ),
        fusion_interval=fusion_interval,
    )


def elu_config(**updates: Any) -> ELUConfig:
    values = {
        "association_rules": association_rules(),
        "free_space_reliability_threshold": 0.8,
        "free_space_target_expansion_m": 0.02,
        "minimum_free_space_time_separation_s": 0.25,
        "birth_log_odds": 0.0,
        "positive_log_odds_increment": 1.0,
        "negative_log_odds_decrement": 2.0,
        "dormant_log_odds_threshold": -0.5,
        "retract_log_odds_threshold": -1.5,
    }
    values.update(updates)
    return ELUConfig(**values)


def wfr_config(**updates: Any) -> WFRConfig:
    values = {
        "association_rules": association_rules(duplicate_threshold=0.9),
        "confirmation_observations": 2,
        "reconciliation_interval": 1,
        "absent_reconciliations_before_retract": 1,
        "free_space_reliability_threshold": 0.8,
        "free_space_target_expansion_m": 0.02,
        "minimum_free_space_time_separation_s": 0.25,
    }
    values.update(updates)
    return WFRConfig(**values)


class VSMTBaselineTests(unittest.TestCase):
    def test_configs_require_explicit_valid_values(self) -> None:
        with self.assertRaises(ValueError):
            low_config(0.0)
        with self.assertRaisesRegex(ValueError, "sum to one"):
            taf_config(visual_weight=0.8, geometry_weight=0.8)
        with self.assertRaisesRegex(ValueError, "below dormant"):
            elu_config(retract_log_odds_threshold=0.0)
        with self.assertRaises(ValueError):
            wfr_config(reconciliation_interval=0)

    def test_all_four_adapters_consume_the_same_public_relation(self) -> None:
        graph = memory()
        regions = [
            region(centroid=[0.0, 0.1, 0.0], descriptor=[1.0, 0.0], index=0),
            region(
                centroid=[0.0, 0.0, 0.0], descriptor=[0.0, 1.0],
                index=1, kind="place",
            ),
        ]
        relations = [{
            "relation_id": "relation:0000",
            "source_region_id": "region:0000",
            "target_region_id": "region:0001",
            "relation": "located_at",
            "reliability": 1.0,
            "support_sha256": "9" * 64,
        }]
        adapters = [
            LOWAdapter(low_config(0.5)),
            TAFAdapter(taf_config()),
            ELUAdapter(elu_config()),
            WFRAdapter(wfr_config()),
        ]
        prepared, scaffold_memory, shared_audit = prepare_shared_memory(
            packet(graph, regions=regions, relations=relations),
            graph,
            config=SharedMemoryConfig(dormancy_inactivity_horizon_s=100.0),
        )
        self.assertEqual(shared_audit["dormant_node_ids"], [])
        for adapter in adapters:
            with self.subTest(method=adapter.method_id):
                result = run_adapter(
                    adapter,
                    prepared,
                    scaffold_memory,
                )
                open_edges = [
                    edge for edge in result["post_memory"]["edges"]
                    if edge["valid_to"] is None
                ]
                self.assertEqual(len(open_edges), 1)
                self.assertEqual(open_edges[0]["relation"], "located_at")

    def test_low_overwrites_nearest_same_kind(self) -> None:
        graph = memory(observed_node("node-a", centroid=[0.0, 0.0, 0.0],
                                     descriptor=[1.0, 0.0]))
        result = run_adapter(
            LOWAdapter(low_config(0.5)),
            packet(graph, regions=[region(centroid=[0.1, 0.0, 0.0],
                                                  descriptor=[0.0, 1.0])]),
            graph,
        )
        self.assertEqual(result["normalized_delta"]["declared_template"], "BIND")
        open_nodes = [node for node in result["post_memory"]["nodes"]
                      if node["valid_to"] is None]
        self.assertEqual(len(open_nodes), 1)
        self.assertEqual(open_nodes[0][STATE_KEY]["descriptor"], [0.0, 1.0])

    def test_low_births_when_nearest_is_too_far(self) -> None:
        graph = memory(observed_node("node-a", centroid=[0.0, 0.0, 0.0],
                                     descriptor=[1.0, 0.0]))
        result = run_adapter(
            LOWAdapter(low_config(0.1)),
            packet(graph, regions=[region(centroid=[1.0, 0.0, 0.0],
                                                  descriptor=[1.0, 0.0])]),
            graph,
        )
        self.assertEqual(result["normalized_delta"]["declared_template"], "BIRTH")

    def test_taf_fuses_visual_geometric_match(self) -> None:
        graph = memory(observed_node("node-a", centroid=[0.0, 0.0, 0.0],
                                     descriptor=[1.0, 0.0]))
        result = run_adapter(
            TAFAdapter(taf_config(duplicate_threshold=1.0)),
            packet(graph, regions=[region(centroid=[0.1, 0.0, 0.0],
                                                  descriptor=[1.0, 0.0])]),
            graph,
        )
        self.assertEqual(result["normalized_delta"]["declared_template"], "BIND")
        self.assertEqual(result["diagnostics"]["matched_regions"], 1)

    def test_taf_periodically_merges_public_duplicates(self) -> None:
        graph = memory(
            observed_node("node-a", centroid=[0.0, 0.0, 0.0], descriptor=[1.0, 0.0]),
            observed_node("node-b", centroid=[0.01, 0.0, 0.0], descriptor=[1.0, 0.0]),
        )
        result = run_adapter(
            TAFAdapter(taf_config()), packet(graph, regions=[]), graph,
        )
        self.assertEqual(result["normalized_delta"]["declared_template"], "MERGE")
        self.assertEqual(result["diagnostics"]["merged_pairs"], 1)

    def test_taf_merge_reanchors_and_deduplicates_relations(self) -> None:
        nodes = (
            observed_node(
                "node-a", centroid=[0.0, 0.0, 0.0], descriptor=[1.0, 0.0],
            ),
            observed_node(
                "node-b", centroid=[0.01, 0.0, 0.0], descriptor=[1.0, 0.0],
            ),
            observed_node(
                "place-a", centroid=[0.0, 0.0, 0.0], descriptor=[0.0, 1.0],
                node_type="place",
            ),
        )
        edges = [
            {
                "edge_id": f"edge:{index}",
                "edge_version_id": f"edge:{index}@v0",
                "source": source,
                "target": "place-a",
                "relation": "located_at",
                "frame": "map",
                "valid_from": 0,
                "valid_to": None,
                "evidence_refs": [f"observation:edge:{index}"],
                "provenance": [f"fixture:edge:{index}"],
            }
            for index, source in enumerate(("node-a", "node-b"))
        ]
        graph = memory(*nodes, edges=edges)
        result = run_adapter(
            TAFAdapter(taf_config()), packet(graph, regions=[]), graph,
        )
        open_edges = [
            edge for edge in result["post_memory"]["edges"]
            if edge["valid_to"] is None
        ]
        self.assertEqual(len(open_edges), 1)
        self.assertEqual(open_edges[0]["source"], "node-a")
        self.assertEqual(open_edges[0]["target"], "place-a")
        self.assertEqual(
            set(open_edges[0]["evidence_refs"]),
            {"observation:edge:0", "observation:edge:1"},
        )

    def test_elu_retracts_only_with_covering_free_space(self) -> None:
        graph = memory(observed_node(
            "node-a", centroid=[0.0, 0.0, 0.0], descriptor=[1.0, 0.0],
            state_updates={"existence_log_odds": 0.0},
        ))
        result = run_adapter(
            ELUAdapter(elu_config()),
            packet(graph, regions=[], include_free_space=True), graph,
        )
        self.assertEqual(result["normalized_delta"]["declared_template"], "RETRACT")
        self.assertFalse(any(
            node["node_id"] == "node-a" and node["valid_to"] is None
            for node in result["post_memory"]["nodes"]
        ))

    def test_elu_preserves_unmatched_node_without_free_space(self) -> None:
        graph = memory(observed_node(
            "node-a", centroid=[0.0, 0.0, 0.0], descriptor=[1.0, 0.0],
            state_updates={"existence_log_odds": 0.0},
        ))
        result = run_adapter(
            ELUAdapter(elu_config()), packet(graph, regions=[]), graph,
        )
        self.assertEqual(result["normalized_delta"]["declared_template"], "NOOP")
        self.assertEqual(result["post_memory_sha256"], graph["graph_hash"])

    def test_elu_does_not_reactivate_terminal_retracted_identity(self) -> None:
        graph = memory(observed_node(
            "node-a", centroid=[0.0, 0.0, 0.0], descriptor=[1.0, 0.0],
            lifecycle="retracted", valid_to=0,
            state_updates={"existence_log_odds": -2.0},
        ))
        result = run_adapter(
            ELUAdapter(elu_config()),
            packet(graph, regions=[region(centroid=[0.0, 0.0, 0.0],
                                                  descriptor=[1.0, 0.0])]),
            graph,
        )
        self.assertEqual(result["normalized_delta"]["declared_template"], "BIRTH")
        self.assertFalse(any(
            node["node_id"] == "node-a" and node["valid_to"] is None
            for node in result["post_memory"]["nodes"]
        ))

    def test_elu_reactivates_only_open_dormant_identity(self) -> None:
        graph = memory(observed_node(
            "node-a", centroid=[0.0, 0.0, 0.0], descriptor=[1.0, 0.0],
            lifecycle="dormant", state_updates={"existence_log_odds": -1.0},
        ))
        result = run_adapter(
            ELUAdapter(elu_config()),
            packet(graph, regions=[region(
                centroid=[0.0, 0.0, 0.0], descriptor=[1.0, 0.0],
            )]),
            graph,
        )
        self.assertEqual(
            result["normalized_delta"]["declared_template"], "REACTIVATE",
        )
        current = next(
            node for node in result["post_memory"]["nodes"]
            if node["node_id"] == "node-a" and node["valid_to"] is None
        )
        self.assertEqual(current["lifecycle"], "confirmed")

    def test_wfr_births_candidate_fragment(self) -> None:
        graph = memory()
        result = run_adapter(
            WFRAdapter(wfr_config()),
            packet(graph, regions=[region(centroid=[0.0, 0.0, 0.0],
                                                  descriptor=[1.0, 0.0])]),
            graph,
        )
        self.assertEqual(result["normalized_delta"]["declared_template"], "BIRTH")
        open_nodes = [node for node in result["post_memory"]["nodes"]
                      if node["valid_to"] is None]
        self.assertEqual(open_nodes[0]["lifecycle"], "candidate")

    def test_wfr_confirms_fragment_after_registered_observations(self) -> None:
        first_graph = memory(observed_node(
            "node-a", centroid=[0.0, 0.0, 0.0], descriptor=[1.0, 0.0],
            lifecycle="candidate", observation_count=1,
            state_updates={"fragment_observations": 1, "absent_reconciliations": 0},
        ))
        result = run_adapter(
            WFRAdapter(wfr_config()),
            packet(first_graph, regions=[region(centroid=[0.0, 0.0, 0.0],
                                                        descriptor=[1.0, 0.0])]),
            first_graph,
        )
        current = [node for node in result["post_memory"]["nodes"]
                   if node["node_id"] == "node-a" and node["valid_to"] is None]
        self.assertEqual(current[0]["lifecycle"], "confirmed")
        self.assertEqual(result["diagnostics"]["confirmed_fragments"], 1)

    def test_wfr_retracts_only_at_reconciliation(self) -> None:
        graph = memory(observed_node(
            "node-a", centroid=[0.0, 0.0, 0.0], descriptor=[1.0, 0.0],
            state_updates={"absent_reconciliations": 0},
        ))
        result = run_adapter(
            WFRAdapter(wfr_config()),
            packet(graph, regions=[], include_free_space=True), graph,
        )
        self.assertEqual(result["normalized_delta"]["declared_template"], "RETRACT")


if __name__ == "__main__":
    unittest.main()
