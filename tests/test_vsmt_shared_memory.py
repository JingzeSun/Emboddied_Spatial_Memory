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
        "schema_version": "vsmt-observation-packet-v2",
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


class SharedMemoryTests(unittest.TestCase):
    def test_only_stale_confirmed_entity_becomes_dormant(self) -> None:
        graph = memory()
        prepared, post, audit = prepare_shared_memory(
            packet(graph),
            graph,
            config=SharedMemoryConfig(dormancy_inactivity_horizon_s=5.0),
        )
        current = {
            node["node_id"]: node for node in post["nodes"]
            if node["valid_to"] is None
        }
        self.assertEqual(current["entity-confirmed"]["lifecycle"], "dormant")
        self.assertEqual(current["entity-candidate"]["lifecycle"], "candidate")
        self.assertEqual(audit["dormant_node_ids"], ["entity-confirmed"])
        self.assertEqual(audit["input_pre_memory_sha256"], graph["graph_hash"])
        self.assertEqual(prepared["prior_memory_ref"]["graph_sha256"], post["graph_hash"])

    def test_audit_only_identity_does_not_change_shared_memory(self) -> None:
        graph = memory()
        first = packet(graph)
        second = deepcopy(first)
        second["sample_id_hash"] = "a" * 64
        second["rgbd_refs"] = {"rgb_sha256": "b" * 64, "depth_sha256": "c" * 64}
        _, first_memory, first_audit = prepare_shared_memory(
            first, graph, config=SharedMemoryConfig(5.0),
        )
        _, second_memory, second_audit = prepare_shared_memory(
            second, graph, config=SharedMemoryConfig(5.0),
        )
        self.assertEqual(first_memory, second_memory)
        self.assertEqual(first_audit, second_audit)

    def test_recent_confirmed_entity_remains_active(self) -> None:
        graph = memory()
        current = next(
            node for node in graph["nodes"] if node["node_id"] == "entity-confirmed"
        )
        current[STATE_KEY]["last_seen_s"] = 7.0
        graph = seal_graph(graph)
        _, post, audit = prepare_shared_memory(
            packet(graph), graph, config=SharedMemoryConfig(5.0),
        )
        self.assertEqual(post, graph)
        self.assertEqual(audit["dormant_node_ids"], [])


if __name__ == "__main__":
    unittest.main()
