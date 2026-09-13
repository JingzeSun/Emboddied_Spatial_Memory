from __future__ import annotations

from copy import deepcopy
import hashlib
import inspect
from pathlib import Path
import sys
import unittest
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from cpmt.executor import ContractError, execute_transaction  # noqa: E402
from cpmt.hashing import seal_graph  # noqa: E402
from vsmt.contracts import (  # noqa: E402
    seal_private_evaluation,
    validate_candidate_catalog,
)
from vsmt.graph_ops import STATE_KEY  # noqa: E402
from vsmt.public_candidates import (  # noqa: E402
    PublicCandidateConfig,
    generate_public_candidate_catalog,
    label_sealed_candidates,
)


def node(
    node_id: str, node_type: str, centroid: list[float], *,
    lifecycle: str = "confirmed", descriptor: list[float] | None = None,
) -> dict[str, Any]:
    latent_digest = hashlib.sha256(node_id.encode("utf-8")).hexdigest()
    return {
        "node_id": node_id,
        "node_version_id": f"{node_id}@v0",
        "node_type": node_type,
        "lifecycle": lifecycle,
        "valid_from": 0,
        "valid_to": None,
        "evidence_refs": [f"observation:{node_id}"],
        "latent_refs": [f"latent:{latent_digest}"],
        "canonical_id": None,
        "predecessor_ids": [],
        "provenance": ["fixture:public"],
        STATE_KEY: {
            "descriptor": descriptor or [1.0, 0.0],
            "centroid_m": centroid,
            "extent_m": [0.1, 0.1, 0.1],
            "reliability": 1.0,
            "last_seen_s": 0.0,
            "observation_count": 1,
        },
    }


def graph_fixture() -> dict[str, Any]:
    nodes = [
        node("entity-a", "entity", [0.0, 0.0, 0.0]),
        node("entity-b", "entity", [0.05, 0.0, 0.0], lifecycle="candidate"),
        node("entity-d", "entity", [0.0, 0.0, 0.0], lifecycle="dormant"),
        node("place-a", "place", [0.0, 0.0, 0.0]),
        node("place-b", "place", [1.0, 0.0, 0.0]),
    ]
    return seal_graph({
        "schema_version": "cpmt-0.2",
        "graph_id": "graph:candidate-fixture",
        "graph_version": "v0",
        "parent_version": None,
        "nodes": nodes,
        "edges": [{
            "edge_id": "edge:located",
            "edge_version_id": "edge:located@v0",
            "source": "entity-a",
            "target": "place-a",
            "relation": "located_at",
            "frame": "map",
            "valid_from": 0,
            "valid_to": None,
            "evidence_refs": ["observation:edge"],
            "provenance": ["fixture:public"],
        }],
        "transaction_log": [],
    })


def region(index: int, centroid: list[float], kind: str = "entity") -> dict[str, Any]:
    return {
        "region_id": f"region:{index:04d}",
        "structure_kind": kind,
        "mask_sha256": f"{index + 5:x}" * 64,
        "descriptor": [1.0, 0.0],
        "centroid_m": centroid,
        "extent_m": [0.1, 0.1, 0.1],
        "reliability": 1.0,
        "proposal_source_id": "fixed.region.v1",
    }


def packet_fixture(
    graph: Mapping[str, Any], *, free_times: tuple[float, ...] = (0.5, 1.0),
) -> dict[str, Any]:
    return {
        "schema_version": "vsmt-observation-packet-v1",
        "sample_id_hash": "1" * 64,
        "decision_time_s": 1.0,
        "rgbd_refs": {"rgb_sha256": "2" * 64, "depth_sha256": "3" * 64},
        "camera_pose": {
            "position_m": [0.0, 0.0, 1.0],
            "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
        },
        "robot_state": {"feature_names": [], "values": []},
        "past_actions": [],
        "region_observations": [
            region(0, [0.0, 0.0, 0.0]),
            region(1, [0.4, 0.0, 0.0]),
            region(2, [1.0, 0.0, 0.0], kind="place"),
        ],
        "free_space_observations": [
            {
                "free_space_id": f"free:{index:04d}",
                "time_s": time_s,
                "minimum_m": [-0.2, -0.2, -0.2],
                "maximum_m": [0.2, 0.2, 0.2],
                "reliability": 1.0,
                "support_sha256": f"{index + 8:x}" * 64,
            }
            for index, time_s in enumerate(free_times)
        ],
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


def config() -> PublicCandidateConfig:
    return PublicCandidateConfig(
        visual_weight=0.7,
        geometry_weight=0.3,
        geometry_scale_m=1.0,
        bind_threshold=0.6,
        merge_threshold=0.9,
        split_region_threshold=0.6,
        split_minimum_separation_m=0.3,
        free_space_reliability_threshold=0.9,
        maximum_candidates_per_template=20,
        maximum_split_incident_edges=2,
    )


def labels(catalog: Mapping[str, Any]) -> list[str]:
    return [
        (
            str(candidate["program"].get("composition_label"))
            if candidate["program"]["template"] == "COMPOSITE"
            else str(candidate["program"]["template"])
        )
        for candidate in catalog["candidates"]
    ]


class PublicCandidateTests(unittest.TestCase):
    def test_generator_signature_has_no_private_argument(self) -> None:
        parameters = inspect.signature(generate_public_candidate_catalog).parameters
        self.assertNotIn("private", parameters)
        self.assertNotIn("teacher", parameters)
        self.assertEqual(set(parameters), {"packet", "prior_memory", "config"})

    def test_public_fixture_emits_all_eight_atoms_and_replace(self) -> None:
        graph = graph_fixture()
        catalog = generate_public_candidate_catalog(
            packet_fixture(graph), graph, config=config(),
        )
        observed = set(labels(catalog))
        self.assertEqual(observed, {
            "NOOP", "BIND", "BIRTH", "REACTIVATE", "RELINK", "RETRACT",
            "SPLIT", "MERGE", "REPLACE",
        })
        self.assertTrue(all(
            candidate["program"]["proposer"] == "deterministic"
            for candidate in catalog["candidates"]
        ))

    def test_retract_and_replace_need_two_public_times(self) -> None:
        graph = graph_fixture()
        catalog = generate_public_candidate_catalog(
            packet_fixture(graph, free_times=(1.0,)), graph, config=config(),
        )
        observed = set(labels(catalog))
        self.assertNotIn("RETRACT", observed)
        self.assertNotIn("REPLACE", observed)

    def test_split_reassigns_an_open_incident_edge_atomically(self) -> None:
        graph = graph_fixture()
        catalog = generate_public_candidate_catalog(
            packet_fixture(graph), graph, config=config(),
        )
        split_programs = [
            item["program"] for item in catalog["candidates"]
            if item["program"]["template"] == "SPLIT"
        ]
        self.assertTrue(split_programs)
        related = [
            program for program in split_programs
            if any(
                operation["op_type"] == "SET_LIFECYCLE"
                and operation["arguments"].get("node_id") == "entity-a"
                for operation in program["operations"]
            )
        ]
        self.assertTrue(related)
        self.assertTrue(all(
            program["split_relation_assignments"][0][
                "source_edge_version_id"
            ] == "edge:located@v0"
            for program in related
        ))
        self.assertEqual(
            {
                len(program["split_relation_assignments"][0][
                    "successor_node_ids"
                ])
                for program in related
            },
            {1, 2},
        )
        self.assertTrue(all(
            any(
                operation["op_type"] == "CLOSE_EDGE_VERSION"
                and operation["arguments"]["edge_id"] == "edge:located"
                for operation in program["operations"]
            )
            for program in related
        ))

    def test_split_skips_nodes_over_the_public_incident_edge_cap(self) -> None:
        graph = graph_fixture()
        for index in range(2):
            graph["edges"].append({
                "edge_id": f"edge:extra:{index}",
                "edge_version_id": f"edge:extra:{index}@v0",
                "source": "entity-a",
                "target": "place-b",
                "relation": f"public_relation_{index}",
                "frame": "map",
                "valid_from": 0,
                "valid_to": None,
                "evidence_refs": [f"observation:extra:{index}"],
                "provenance": ["fixture:public"],
            })
        graph = seal_graph(graph)
        catalog = generate_public_candidate_catalog(
            packet_fixture(graph), graph, config=config(),
        )
        related = [
            item["program"] for item in catalog["candidates"]
            if item["program"]["template"] == "SPLIT"
            and any(
                operation["op_type"] == "SET_LIFECYCLE"
                and operation["arguments"].get("node_id") == "entity-a"
                for operation in item["program"]["operations"]
            )
        ]
        self.assertEqual(related, [])

    def test_split_rejects_an_unassigned_incident_edge_atomically(self) -> None:
        graph = graph_fixture()
        catalog = generate_public_candidate_catalog(
            packet_fixture(graph), graph, config=config(),
        )
        program = deepcopy(next(
            item["program"] for item in catalog["candidates"]
            if item["program"]["template"] == "SPLIT"
            and item["program"]["split_relation_assignments"]
        ))
        program["split_relation_assignments"] = []
        before = deepcopy(graph)

        with self.assertRaisesRegex(
            ContractError, "assign every open incident edge exactly once",
        ):
            execute_transaction(graph, program)
        self.assertEqual(graph, before)

    def test_split_rejects_duplicate_replacement_for_one_successor(self) -> None:
        graph = graph_fixture()
        catalog = generate_public_candidate_catalog(
            packet_fixture(graph), graph, config=config(),
        )
        program = deepcopy(next(
            item["program"] for item in catalog["candidates"]
            if item["program"]["template"] == "SPLIT"
            and len(item["program"]["split_relation_assignments"][0][
                "successor_node_ids"
            ]) == 2
        ))
        assignment = program["split_relation_assignments"][0]
        replacements = [
            operation["arguments"]["edge"]
            for operation in program["operations"]
            if operation["op_type"] == "ADD_EDGE"
        ]
        replacements[1]["source"] = assignment["successor_node_ids"][0]
        before = deepcopy(graph)

        with self.assertRaisesRegex(
            ContractError, "one relation for each named successor",
        ):
            execute_transaction(graph, program)
        self.assertEqual(graph, before)

    def test_audit_identity_does_not_change_programs_or_order(self) -> None:
        graph = graph_fixture()
        left_packet = packet_fixture(graph)
        right_packet = deepcopy(left_packet)
        right_packet["sample_id_hash"] = "a" * 64
        right_packet["rgbd_refs"] = {
            "rgb_sha256": "b" * 64,
            "depth_sha256": "c" * 64,
        }
        left = generate_public_candidate_catalog(left_packet, graph, config=config())
        right = generate_public_candidate_catalog(right_packet, graph, config=config())
        self.assertEqual(
            [candidate["program_sha256"] for candidate in left["candidates"]],
            [candidate["program_sha256"] for candidate in right["candidates"]],
        )
        self.assertEqual(
            [candidate["online_evidence_sha256"] for candidate in left["candidates"]],
            [candidate["online_evidence_sha256"] for candidate in right["candidates"]],
        )

    def test_tampered_online_evidence_breaks_catalog_seal(self) -> None:
        graph = graph_fixture()
        catalog = generate_public_candidate_catalog(
            packet_fixture(graph), graph, config=config(),
        )
        target = next(
            candidate for candidate in catalog["candidates"]
            if candidate["online_evidence"]
        )
        evidence = next(iter(target["online_evidence"].values()))
        evidence["reliability"] = 0.0
        with self.assertRaisesRegex(ValueError, "online evidence digest mismatch"):
            validate_candidate_catalog(catalog)

    def test_teacher_scores_only_sealed_slots(self) -> None:
        graph = graph_fixture()
        public = packet_fixture(graph)
        catalog = generate_public_candidate_catalog(public, graph, config=config())
        before = deepcopy(catalog)
        private = seal_private_evaluation({
            "schema_version": "vsmt-private-evaluation-v1",
            "sample_id_hash": public["sample_id_hash"],
            "public_sha256": catalog["public_sha256"],
            "reference_memory": graph,
            "reference_transaction_equivalence": [["candidate:0000"]],
            "future_observation_sha256": ["d" * 64],
            "simulator_identity_map": {"sim-a": "entity-a"},
            "semantic_case_id": "semantic.merge_or_bind",
        })

        def scorer(
            program: Mapping[str, Any], online_evidence: Mapping[str, Any],
            private_record: Mapping[str, Any],
        ) -> float:
            self.assertIn("reference_memory", private_record)
            self.assertIsInstance(online_evidence, Mapping)
            return 1.0 if program["template"] == "MERGE" else 0.0

        targets = label_sealed_candidates(
            catalog, private, scorer=scorer,
            teacher_id="fixture.teacher.v1", temperature=0.5,
        )
        self.assertEqual(catalog, before)
        self.assertEqual(
            [row["candidate_id"] for row in targets["targets"]],
            [row["candidate_id"] for row in catalog["candidates"]],
        )
        self.assertAlmostEqual(
            sum(row["probability"] for row in targets["targets"]), 1.0,
        )


if __name__ == "__main__":
    unittest.main()
