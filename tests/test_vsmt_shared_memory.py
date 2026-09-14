from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import unittest
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from cpmt.hashing import seal_graph  # noqa: E402
from vsmt.graph_ops import STATE_KEY  # noqa: E402
from vsmt.shared_memory import (  # noqa: E402
    SharedMemoryConfig,
    prepare_shared_memory,
)


def observed_node(
    node_id: str, *, lifecycle: str, node_type: str = "entity",
) -> dict[str, Any]:
    state: dict[str, Any] = {
        "descriptor": [1.0, 0.0],
        "centroid_m": [0.0, 0.0, 0.0],
        "extent_m": [0.1, 0.1, 0.1],
        "reliability": 1.0,
        "last_seen_s": 0.0,
        "observation_count": 2,
        "observation_aabb_min_m": [-0.05, -0.05, -0.05],
        "observation_aabb_max_m": [0.05, 0.05, 0.05],
        "support_envelope_min_m": [-0.05, -0.05, -0.05],
        "support_envelope_max_m": [0.05, 0.05, 0.05],
        "support_envelope_observation_count": 2,
        "support_envelope_reliability_threshold": 0.9,
    }
    return {
        "node_id": node_id,
        "node_version_id": f"{node_id}@v0",
        "node_type": node_type,
        "lifecycle": lifecycle,
        "valid_from": 0,
        "valid_to": None,
        "evidence_refs": [f"observation:{node_id}"],
        "latent_refs": ["latent:" + hashlib.sha256(node_id.encode()).hexdigest()],
        "canonical_id": None,
        "predecessor_ids": [],
        "provenance": ["fixture:public"],
        STATE_KEY: state,
    }


def memory() -> dict[str, Any]:
    return seal_graph({
        "schema_version": "cpmt-0.2",
        "graph_id": "graph:shared-memory",
        "graph_version": "v0",
        "parent_version": None,
        "nodes": [
            observed_node("entity-confirmed", lifecycle="confirmed"),
            observed_node("entity-candidate", lifecycle="candidate"),
        ],
        "edges": [],
        "transaction_log": [],
    })


def packet(graph: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "vsmt-observation-packet-v3",
        "sample_id_hash": "1" * 64,
        "decision_time_s": 10.0,
        "rgbd_refs": {"rgb_sha256": "2" * 64, "depth_sha256": "3" * 64},
        "camera_pose": {
            "position_m": [0.0, 0.0, 1.0],
            "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
        },
        "robot_state": {"feature_names": [], "values": []},
        "past_actions": [],
        "region_observations": [],
        "relation_observations": [],
        "free_space_observations": [],
        "visibility_observations": [],
        "prior_memory_ref": {
            "graph_version": graph["graph_version"],
            "graph_sha256": graph["graph_hash"],
        },
        "public_constants": {
            "coordinate_frame": "map",
            "depth_unit": "metre",
            "descriptor_model_id": "dinov2.vits14",
            "proposal_model_id": "fixed.region.v2",
        },
    }


def visibility_record(identifier: str = "visibility:0000") -> dict[str, Any]:
    return {
        "visibility_id": identifier,
        "time_s": 10.0,
        "halfspaces_world": [
            {"normal": [1.0, 0.0, 0.0], "offset_m": 1.0},
            {"normal": [-1.0, 0.0, 0.0], "offset_m": 1.0},
            {"normal": [0.0, 1.0, 0.0], "offset_m": 1.0},
            {"normal": [0.0, -1.0, 0.0], "offset_m": 1.0},
            {"normal": [0.0, 0.0, 1.0], "offset_m": 1.0},
            {"normal": [0.0, 0.0, -1.0], "offset_m": 1.0},
        ],
        "reliability": 1.0,
        "support_sha256": "d" * 64,
    }


def shared_config(*, missed: int = 1) -> SharedMemoryConfig:
    return SharedMemoryConfig(
        support_envelope_reliability_threshold=0.9,
        support_envelope_margin_m=0.02,
        minimum_consecutive_missed_opportunities=missed,
        opportunity_reliability_threshold=0.8,
        free_space_reliability_threshold=0.8,
        association_visual_weight=0.5,
        association_geometry_weight=0.5,
        association_geometry_scale_m=1.0,
        association_bind_threshold=0.7,
    )


class SharedMemoryTests(unittest.TestCase):
    def test_public_opportunity_covers_candidate_and_confirmed_entities(self) -> None:
        graph = memory()
        current_packet = packet(graph)
        current_packet["visibility_observations"] = [visibility_record()]
        prepared, post, audit = prepare_shared_memory(
            current_packet,
            graph,
            config=shared_config(),
        )
        current = {
            node["node_id"]: node for node in post["nodes"]
            if node["valid_to"] is None
        }
        self.assertEqual(current["entity-confirmed"]["lifecycle"], "dormant")
        self.assertEqual(current["entity-candidate"]["lifecycle"], "dormant")
        self.assertEqual(
            audit["dormant_node_ids"],
            ["entity-candidate", "entity-confirmed"],
        )
        self.assertEqual(
            current["entity-candidate"][STATE_KEY]["pre_dormancy_lifecycle"],
            "candidate",
        )
        self.assertEqual(audit["input_pre_memory_sha256"], graph["graph_hash"])
        self.assertEqual(prepared["prior_memory_ref"]["graph_sha256"], post["graph_hash"])

    def test_audit_only_identity_does_not_change_shared_memory(self) -> None:
        graph = memory()
        first = packet(graph)
        second = deepcopy(first)
        second["sample_id_hash"] = "a" * 64
        second["rgbd_refs"] = {"rgb_sha256": "b" * 64, "depth_sha256": "c" * 64}
        _, first_memory, first_audit = prepare_shared_memory(
            first, graph, config=shared_config(),
        )
        _, second_memory, second_audit = prepare_shared_memory(
            second, graph, config=shared_config(),
        )
        self.assertEqual(first_memory, second_memory)
        self.assertEqual(first_audit, second_audit)

    def test_elapsed_time_without_visibility_is_not_an_opportunity(self) -> None:
        graph = memory()
        _, post, audit = prepare_shared_memory(
            packet(graph), graph, config=shared_config(),
        )
        self.assertEqual(post, graph)
        self.assertEqual(audit["dormant_node_ids"], [])

    def test_visible_empty_routes_away_from_dormancy(self) -> None:
        graph = memory()
        current_packet = packet(graph)
        current_packet["visibility_observations"] = [visibility_record()]
        empty = visibility_record()
        del empty["visibility_id"]
        empty["free_space_id"] = "free:0000"
        current_packet["free_space_observations"] = [empty]
        _, post, audit = prepare_shared_memory(
            current_packet, graph, config=shared_config(),
        )
        self.assertEqual(post, graph)
        self.assertEqual(
            audit["visible_empty_node_ids"],
            ["entity-candidate", "entity-confirmed"],
        )

    def test_same_visibility_is_intersected_with_each_memory_node(self) -> None:
        graph = memory()
        candidate = next(
            node for node in graph["nodes"]
            if node["node_id"] == "entity-candidate"
        )
        candidate[STATE_KEY]["centroid_m"] = [5.0, 0.0, 0.0]
        candidate[STATE_KEY]["observation_aabb_min_m"] = [4.95, -0.05, -0.05]
        candidate[STATE_KEY]["observation_aabb_max_m"] = [5.05, 0.05, 0.05]
        candidate[STATE_KEY]["support_envelope_min_m"] = [4.95, -0.05, -0.05]
        candidate[STATE_KEY]["support_envelope_max_m"] = [5.05, 0.05, 0.05]
        graph = seal_graph(graph)
        current_packet = packet(graph)
        current_packet["visibility_observations"] = [visibility_record()]
        _, post, audit = prepare_shared_memory(
            current_packet, graph, config=shared_config(),
        )
        current = {
            node["node_id"]: node for node in post["nodes"]
            if node["valid_to"] is None
        }
        self.assertEqual(current["entity-confirmed"]["lifecycle"], "dormant")
        self.assertEqual(current["entity-candidate"]["lifecycle"], "candidate")
        self.assertEqual(audit["dormant_node_ids"], ["entity-confirmed"])

    def test_current_bind_eligible_region_resets_missed_count(self) -> None:
        graph = memory()
        confirmed = next(
            node for node in graph["nodes"]
            if node["node_id"] == "entity-confirmed"
        )
        confirmed[STATE_KEY]["missed_observation_opportunities"] = 2
        graph = seal_graph(graph)
        current_packet = packet(graph)
        current_packet["region_observations"] = [{
            "region_id": "region:0000",
            "structure_kind": "entity",
            "mask_sha256": "e" * 64,
            "descriptor": [1.0, 0.0],
            "centroid_m": [0.0, 0.0, 0.0],
            "extent_m": [0.1, 0.1, 0.1],
            "reliability": 1.0,
            "proposal_source_id": "fixed.region.v2",
        }]
        _, post, audit = prepare_shared_memory(
            current_packet, graph, config=shared_config(missed=3),
        )
        current = next(
            node for node in post["nodes"]
            if node["node_id"] == "entity-confirmed" and node["valid_to"] is None
        )
        self.assertEqual(
            current[STATE_KEY]["missed_observation_opportunities"], 0,
        )
        self.assertEqual(audit["reset_node_ids"], ["entity-confirmed"])


if __name__ == "__main__":
    unittest.main()
