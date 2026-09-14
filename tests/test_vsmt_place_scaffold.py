from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from vsmt.causal_prior import empty_public_memory  # noqa: E402
from vsmt.graph_ops import (  # noqa: E402
    PLACE_SCAFFOLD_ID,
    SCAFFOLD_RELATIONS,
    STATE_KEY,
    GraphRevision,
)
from vsmt.place_scaffold import prepare_place_scaffold  # noqa: E402


def place_region(
    ordinal: int = 0, centroid: tuple[float, float, float] = (0.25, 0.0, -0.25),
) -> dict[str, object]:
    return {
        "region_id": f"region:{ordinal:04d}",
        "structure_kind": "place",
        "mask_sha256": f"{ordinal + 4}" * 64,
        "descriptor": [1.0, 0.0],
        "centroid_m": list(centroid),
        "extent_m": [0.5, 0.0, 0.5],
        "reliability": 0.8,
        "proposal_source_id": "l1.public_depth.floor_place_cell.v1",
    }


def adjacency_observation() -> dict[str, object]:
    return {
        "relation_id": "relation:0000",
        "source_region_id": "region:0000",
        "target_region_id": "region:0001",
        "relation": "adjacent_to",
        "reliability": 0.8,
        "support_sha256": "7" * 64,
    }


def packet(memory: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "vsmt-observation-packet-v3",
        "sample_id_hash": "1" * 64,
        "decision_time_s": 1.0,
        "rgbd_refs": {"rgb_sha256": "2" * 64, "depth_sha256": "3" * 64},
        "camera_pose": {
            "position_m": [0.0, 0.0, 0.0],
            "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
        },
        "robot_state": {"feature_names": [], "values": []},
        "past_actions": [],
        "region_observations": [place_region()],
        "relation_observations": [],
        "free_space_observations": [],
        "visibility_observations": [],
        "prior_memory_ref": {
            "graph_version": memory["graph_version"],
            "graph_sha256": memory["graph_hash"],
        },
        "public_constants": {
            "coordinate_frame": "map",
            "depth_unit": "metre",
            "descriptor_model_id": "dinov2.vits14",
            "proposal_model_id": "fixed.region.v2",
        },
    }


class PlaceScaffoldTests(unittest.TestCase):
    def test_public_audit_identity_does_not_change_scaffold_memory(self) -> None:
        memory = empty_public_memory()
        first = packet(memory)
        second = deepcopy(first)
        second["sample_id_hash"] = "a" * 64
        second["rgbd_refs"] = {"rgb_sha256": "b" * 64, "depth_sha256": "c" * 64}
        first_packet, first_memory = prepare_place_scaffold(
            first, memory, support_envelope_reliability_threshold=0.9,
        )
        second_packet, second_memory = prepare_place_scaffold(
            second, memory, support_envelope_reliability_threshold=0.9,
        )
        self.assertEqual(first_memory, second_memory)
        self.assertNotEqual(first_packet["rgbd_refs"], second_packet["rgbd_refs"])

    def test_revisit_versions_one_coordinate_identity_without_a_learned_template(self) -> None:
        memory = empty_public_memory()
        first_packet, first_memory = prepare_place_scaffold(
            packet(memory), memory, support_envelope_reliability_threshold=0.9,
        )
        current = [node for node in first_memory["nodes"] if node["valid_to"] is None]
        self.assertEqual(len(current), 1)
        node_id = current[0]["node_id"]
        self.assertEqual(current[0]["provenance"], [f"{PLACE_SCAFFOLD_ID}:birth"])
        self.assertEqual(current[0][STATE_KEY]["place_scaffold_key"], "0.250000000:-0.250000000")

        later = deepcopy(first_packet)
        later["decision_time_s"] = 2.0
        later["prior_memory_ref"] = {
            "graph_version": first_memory["graph_version"],
            "graph_sha256": first_memory["graph_hash"],
        }
        _, second_memory = prepare_place_scaffold(
            later, first_memory, support_envelope_reliability_threshold=0.9,
        )
        versions = [node for node in second_memory["nodes"] if node["node_id"] == node_id]
        self.assertEqual(len(versions), 2)
        self.assertEqual(len([node for node in versions if node["valid_to"] is None]), 1)
        self.assertEqual(
            second_memory["transaction_log"][-1]["observed_templates"], [],
        )


class PlaceAdjacencyTests(unittest.TestCase):
    def neighbour_packet(self, memory: dict[str, object]) -> dict[str, object]:
        current = packet(memory)
        current["region_observations"] = [
            place_region(0, (0.25, 0.0, -0.25)),
            place_region(1, (0.75, 0.0, -0.25)),
        ]
        current["relation_observations"] = [adjacency_observation()]
        return current

    def test_scaffold_maintains_adjacency_without_a_learned_template(self) -> None:
        memory = empty_public_memory()
        _, prepared = prepare_place_scaffold(
            self.neighbour_packet(memory), memory,
            support_envelope_reliability_threshold=0.9,
        )
        edges = [edge for edge in prepared["edges"] if edge["valid_to"] is None]
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["relation"], "adjacent_to")
        self.assertEqual(
            edges[0]["provenance"], [f"{PLACE_SCAFFOLD_ID}:adjacency-birth"],
        )
        self.assertEqual(
            prepared["transaction_log"][-1]["observed_templates"], [],
        )

    def test_revisiting_the_same_pair_binds_instead_of_duplicating(self) -> None:
        memory = empty_public_memory()
        first_packet, first_memory = prepare_place_scaffold(
            self.neighbour_packet(memory), memory,
            support_envelope_reliability_threshold=0.9,
        )
        later = deepcopy(first_packet)
        later["decision_time_s"] = 2.0
        later["prior_memory_ref"] = {
            "graph_version": first_memory["graph_version"],
            "graph_sha256": first_memory["graph_hash"],
        }
        _, second_memory = prepare_place_scaffold(
            later, first_memory, support_envelope_reliability_threshold=0.9,
        )
        edges = [edge for edge in second_memory["edges"] if edge["valid_to"] is None]
        self.assertEqual(len(edges), 1)
        self.assertEqual(
            second_memory["transaction_log"][-1]["observed_templates"], [],
        )

    def test_relation_observations_leave_adjacency_to_the_scaffold(self) -> None:
        memory = empty_public_memory()
        _, prepared = prepare_place_scaffold(
            self.neighbour_packet(memory), memory,
            support_envelope_reliability_threshold=0.9,
        )
        node_ids = {
            f"region:{index:04d}": node["node_id"]
            for index, node in enumerate(sorted(
                (node for node in prepared["nodes"] if node["valid_to"] is None),
                key=lambda item: str(item["node_id"]),
            ))
        }
        revision = GraphRevision(
            prepared, method_id="fixture.method.v1",
            support_envelope_reliability_threshold=0.9,
        )
        counts = revision.apply_relation_observations(
            [adjacency_observation()], node_ids,
        )
        self.assertEqual(counts["scaffold_maintained"], 1)
        self.assertEqual(counts["born"], 0)
        self.assertEqual(counts["bound"], 0)
        self.assertIn("adjacent_to", SCAFFOLD_RELATIONS)

    def test_a_new_cell_links_to_a_neighbour_seen_in_an_earlier_packet(self) -> None:
        memory = empty_public_memory()
        first = packet(memory)
        first["region_observations"] = [place_region(0, (0.25, 0.0, -0.25))]
        first_packet, first_memory = prepare_place_scaffold(
            first, memory, support_envelope_reliability_threshold=0.9,
        )
        self.assertEqual(
            [edge for edge in first_memory["edges"] if edge["valid_to"] is None], [],
        )

        second = deepcopy(first_packet)
        second["decision_time_s"] = 2.0
        later_cell = place_region(1, (0.75, 0.0, -0.25))
        later_cell["region_id"] = "region:0000"
        second["region_observations"] = [later_cell]
        second["relation_observations"] = []
        second["prior_memory_ref"] = {
            "graph_version": first_memory["graph_version"],
            "graph_sha256": first_memory["graph_hash"],
        }
        _, second_memory = prepare_place_scaffold(
            second, first_memory, support_envelope_reliability_threshold=0.9,
        )
        edges = [edge for edge in second_memory["edges"] if edge["valid_to"] is None]
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["relation"], "adjacent_to")
        self.assertEqual(
            second_memory["transaction_log"][-1]["observed_templates"], [],
        )

    def test_a_diagonal_cell_is_not_adjacent(self) -> None:
        memory = empty_public_memory()
        current = packet(memory)
        current["region_observations"] = [
            place_region(0, (0.25, 0.0, -0.25)),
            place_region(1, (0.75, 0.0, 0.25)),
        ]
        _, prepared = prepare_place_scaffold(
            current, memory, support_envelope_reliability_threshold=0.9,
        )
        self.assertEqual(
            [edge for edge in prepared["edges"] if edge["valid_to"] is None], [],
        )

    def test_a_memory_method_cannot_write_an_untemplated_edge(self) -> None:
        memory = empty_public_memory()
        _, prepared = prepare_place_scaffold(
            self.neighbour_packet(memory), memory,
            support_envelope_reliability_threshold=0.9,
        )
        revision = GraphRevision(
            prepared, method_id="fixture.method.v1",
            support_envelope_reliability_threshold=0.9,
        )
        open_edge = [
            edge for edge in prepared["edges"] if edge["valid_to"] is None
        ][0]
        with self.assertRaisesRegex(ValueError, "reserved for the trusted"):
            revision.bind_edge(
                open_edge, adjacency_observation(),
                template=None, purpose="adjacency-bind",
            )


if __name__ == "__main__":
    unittest.main()
