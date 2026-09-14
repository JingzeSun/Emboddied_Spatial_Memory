from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
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

from cpmt.executor import (  # noqa: E402
    ContractError,
    PreconditionError,
    execute_transaction,
)
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
    state = {
        "descriptor": descriptor or [1.0, 0.0],
        "centroid_m": centroid,
        "extent_m": [0.1, 0.1, 0.1],
        "reliability": 1.0,
        "last_seen_s": 0.0,
        "observation_count": 1,
    }
    if node_type == "place":
        state["place_scaffold_key"] = f"{centroid[0]:.9f}:{centroid[2]:.9f}"
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
        STATE_KEY: state,
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
        "region_observations": [
            region(0, [0.0, 0.0, 0.0]),
            region(1, [0.4, 0.0, 0.0]),
            region(2, [1.0, 0.0, 0.0], kind="place"),
        ],
        "relation_observations": [{
            "relation_id": "relation:0000",
            "source_region_id": "region:0000",
            "target_region_id": "region:0002",
            "relation": "located_at",
            "reliability": 1.0,
            "support_sha256": "b" * 64,
        }],
        "free_space_observations": [
            {
                "free_space_id": f"free:{index:04d}",
                "time_s": time_s,
                "halfspaces_world": [
                    {"normal": [1.0, 0.0, 0.0], "offset_m": 0.2},
                    {"normal": [-1.0, 0.0, 0.0], "offset_m": 0.2},
                    {"normal": [0.0, 1.0, 0.0], "offset_m": 0.2},
                    {"normal": [0.0, -1.0, 0.0], "offset_m": 0.2},
                    {"normal": [0.0, 0.0, 1.0], "offset_m": 0.2},
                    {"normal": [0.0, 0.0, -1.0], "offset_m": 0.2},
                ],
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
        association_rules={
            kind: {
                "visual_weight": 0.7,
                "geometry_weight": 0.3,
                "geometry_scale_m": 1.0,
                "bind_threshold": 0.6,
                "merge_threshold": 0.9,
                "split_region_threshold": 0.6,
            }
            for kind in ("entity", "surface", "fragment")
        },
        split_minimum_separation_m=0.3,
        free_space_reliability_threshold=0.9,
        free_space_target_expansion_m=0.02,
        minimum_free_space_time_separation_s=0.25,
        maximum_candidates_per_bucket=20,
        maximum_split_ambiguous_edges=8,
        maximum_split_total_incident_edges=16,
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

    def test_candidate_capacity_is_partitioned_by_structure_kind(self) -> None:
        graph = graph_fixture()
        public = packet_fixture(graph)
        public["region_observations"].append(
            region(3, [0.0, 0.0, 0.0], kind="surface")
        )
        bounded = replace(config(), maximum_candidates_per_bucket=1)
        catalog = generate_public_candidate_catalog(public, graph, config=bounded)
        birth_rows = {
            row["bucket_id"]: row
            for row in catalog["capacity_audit"]
            if row["template"] == "BIRTH"
        }
        self.assertEqual(birth_rows["BIRTH|entity"]["retained_candidate_count"], 1)
        self.assertEqual(birth_rows["BIRTH|surface"]["retained_candidate_count"], 1)
        self.assertEqual(
            catalog["capacity_summary"]["bucket_count"],
            len(catalog["capacity_audit"]),
        )
        self.assertEqual(
            catalog["capacity_summary"]["total_retained_candidate_count"],
            len(catalog["candidates"]),
        )

    def test_candidate_capacity_summary_cannot_disagree_with_buckets(self) -> None:
        graph = graph_fixture()
        catalog = generate_public_candidate_catalog(
            packet_fixture(graph), graph, config=config(),
        )
        catalog["capacity_summary"]["total_capacity"] += 1
        with self.assertRaisesRegex(ValueError, "does not match its buckets"):
            validate_candidate_catalog(catalog)

    def test_place_scaffold_has_no_learned_node_candidate_bucket(self) -> None:
        graph = graph_fixture()
        catalog = generate_public_candidate_catalog(
            packet_fixture(graph), graph, config=config(),
        )
        self.assertFalse(any(
            row["scope"] == "place" for row in catalog["capacity_audit"]
        ))

    def test_relink_requires_a_public_relation_observation(self) -> None:
        graph = graph_fixture()
        public = packet_fixture(graph)
        public["relation_observations"] = []
        catalog = generate_public_candidate_catalog(public, graph, config=config())
        self.assertNotIn("RELINK", set(labels(catalog)))

    def test_relation_observation_generates_typed_birth_bind_and_relink(self) -> None:
        graph = graph_fixture()
        public = packet_fixture(graph)
        public["region_observations"].append(
            region(3, [0.0, 0.0, 0.0], kind="place")
        )
        public["relation_observations"].extend([
            {
                "relation_id": "relation:0001",
                "source_region_id": "region:0000",
                "target_region_id": "region:0003",
                "relation": "located_at",
                "reliability": 1.0,
                "support_sha256": "c" * 64,
            },
            {
                "relation_id": "relation:0002",
                "source_region_id": "region:0002",
                "target_region_id": "region:0000",
                "relation": "contains",
                "reliability": 1.0,
                "support_sha256": "b" * 64,
            },
        ])
        catalog = generate_public_candidate_catalog(
            public, graph, config=config(),
        )
        programs = [candidate["program"] for candidate in catalog["candidates"]]
        self.assertTrue(any(
            program["template"] == "BIRTH"
            and any(operation["op_type"] == "ADD_EDGE"
                    for operation in program["operations"])
            for program in programs
        ))
        self.assertTrue(any(
            program["template"] == "BIND"
            and any(
                operation["op_type"] == "ATTACH_EVIDENCE"
                and operation["arguments"].get("target_kind") == "edge"
                for operation in program["operations"]
            )
            for program in programs
        ))
        born_edges = [
            operation["arguments"]["edge"]
            for program in programs if program["template"] == "BIRTH"
            for operation in program["operations"]
            if operation["op_type"] == "ADD_EDGE"
        ]
        semantic_births = {
            (
                edge["source"], edge["target"], edge["relation"],
                tuple(edge["evidence_refs"]),
            )
            for edge in born_edges
        }
        self.assertEqual(len(born_edges), len(semantic_births))
        self.assertTrue(any(
            program["template"] == "RELINK"
            and any(
                reference == "observation:" + "b" * 64
                for reference in program["evidence_refs"]
            )
            for program in programs
        ))

    def test_retract_and_replace_need_two_public_times(self) -> None:
        graph = graph_fixture()
        catalog = generate_public_candidate_catalog(
            packet_fixture(graph, free_times=(1.0,)), graph, config=config(),
        )
        observed = set(labels(catalog))
        self.assertNotIn("RETRACT", observed)
        self.assertNotIn("REPLACE", observed)

    def test_retract_rejects_two_times_less_than_quarter_second_apart(self) -> None:
        graph = graph_fixture()
        catalog = generate_public_candidate_catalog(
            packet_fixture(graph, free_times=(0.8, 1.0)), graph, config=config(),
        )
        observed = set(labels(catalog))
        self.assertNotIn("RETRACT", observed)
        self.assertNotIn("REPLACE", observed)

    def test_node_retract_closes_entity_and_all_incident_relations_atomically(self) -> None:
        graph = graph_fixture()
        catalog = generate_public_candidate_catalog(
            packet_fixture(graph), graph, config=config(),
        )
        program = next(
            item["program"] for item in catalog["candidates"]
            if item["program"]["template"] == "RETRACT"
            and item["program"]["retraction_target"] == {
                "kind": "node_version", "version_id": "entity-a@v0",
            }
        )
        evidence = next(
            item["online_evidence"] for item in catalog["candidates"]
            if item["program"] == program
        )
        post = execute_transaction(graph, program, evidence_by_id=evidence)
        self.assertFalse(any(
            node["node_id"] == "entity-a" and node["valid_to"] is None
            for node in post["nodes"]
        ))
        terminal = next(
            node for node in post["nodes"]
            if node["node_id"] == "entity-a" and node["lifecycle"] == "retracted"
        )
        self.assertEqual(terminal["valid_from"], terminal["valid_to"])
        self.assertEqual(terminal["predecessor_ids"], ["entity-a@v0"])
        self.assertTrue(set(program["evidence_refs"]) <= set(terminal["evidence_refs"]))
        self.assertFalse(any(
            edge["valid_to"] is None
            and "entity-a" in {edge["source"], edge["target"]}
            for edge in post["edges"]
        ))
        self.assertTrue(any(
            node["node_id"] == "place-a" and node["valid_to"] is None
            for node in post["nodes"]
        ))

    def test_node_retract_rejects_one_missing_incident_edge_close_without_mutation(self) -> None:
        graph = graph_fixture()
        catalog = generate_public_candidate_catalog(
            packet_fixture(graph), graph, config=config(),
        )
        candidate = next(
            item for item in catalog["candidates"]
            if item["program"]["template"] == "RETRACT"
            and item["program"]["retraction_target"] == {
                "kind": "node_version", "version_id": "entity-a@v0",
            }
        )
        program = deepcopy(candidate["program"])
        program["operations"] = [
            operation for operation in program["operations"]
            if operation["op_type"] != "CLOSE_EDGE_VERSION"
        ]
        before = deepcopy(graph)
        with self.assertRaisesRegex(ContractError, "every open incident edge"):
            execute_transaction(
                graph, program, evidence_by_id=candidate["online_evidence"],
            )
        self.assertEqual(graph, before)

    def test_node_retract_terminal_cannot_rewrite_preserved_state(self) -> None:
        graph = graph_fixture()
        catalog = generate_public_candidate_catalog(
            packet_fixture(graph), graph, config=config(),
        )
        candidate = next(
            item for item in catalog["candidates"]
            if item["program"]["template"] == "RETRACT"
            and item["program"]["retraction_target"] == {
                "kind": "node_version", "version_id": "entity-a@v0",
            }
        )
        program = deepcopy(candidate["program"])
        terminal = next(
            operation["arguments"]["node"]
            for operation in program["operations"]
            if operation["op_type"] == "OPEN_NODE_VERSION"
        )
        terminal[STATE_KEY]["centroid_m"] = [9.0, 9.0, 9.0]
        before = deepcopy(graph)
        with self.assertRaisesRegex(ContractError, "must preserve identity"):
            execute_transaction(
                graph, program, evidence_by_id=candidate["online_evidence"],
            )
        self.assertEqual(graph, before)

    def test_node_retract_cannot_attach_collateral_evidence(self) -> None:
        graph = graph_fixture()
        catalog = generate_public_candidate_catalog(
            packet_fixture(graph), graph, config=config(),
        )
        candidate = next(
            item for item in catalog["candidates"]
            if item["program"]["template"] == "RETRACT"
            and item["program"]["retraction_target"] == {
                "kind": "node_version", "version_id": "entity-a@v0",
            }
        )
        program = deepcopy(candidate["program"])
        program["operations"].append({
            "op_id": "node-retract:collateral",
            "op_type": "ATTACH_EVIDENCE",
            "arguments": {
                "target_kind": "node",
                "node_version_id": "place-a@v0",
                "evidence_ref": program["evidence_refs"][0],
            },
        })
        before = deepcopy(graph)
        with self.assertRaisesRegex(ContractError, "retired source version"):
            execute_transaction(
                graph, program, evidence_by_id=candidate["online_evidence"],
            )
        self.assertEqual(graph, before)

    def test_node_replace_uses_new_public_relations_without_old_identity_evidence(self) -> None:
        graph = graph_fixture()
        catalog = generate_public_candidate_catalog(
            packet_fixture(graph), graph, config=config(),
        )
        candidate = next(
            item for item in catalog["candidates"]
            if item["program"].get("composition_label") == "REPLACE"
            and item["program"]["retraction_target"] == {
                "kind": "node_version", "version_id": "entity-a@v0",
            }
            and any(
                operation["op_type"] == "ADD_EDGE"
                for operation in item["program"]["operations"]
            )
        )
        program = candidate["program"]
        post = execute_transaction(
            graph, program, evidence_by_id=candidate["online_evidence"],
        )
        created = next(
            operation["arguments"]["node"] for operation in program["operations"]
            if operation["op_type"] == "CREATE_NODE"
        )
        self.assertNotEqual(created["node_id"], "entity-a")
        self.assertEqual(created["lifecycle"], "candidate")
        self.assertNotIn("observation:entity-a", created["evidence_refs"])
        new_relations = [
            edge for edge in post["edges"]
            if edge["valid_to"] is None and edge["source"] == created["node_id"]
        ]
        self.assertEqual(len(new_relations), 1)
        self.assertEqual(new_relations[0]["target"], "place-b")
        self.assertEqual(new_relations[0]["relation"], "located_at")
        self.assertNotIn("observation:edge", new_relations[0]["evidence_refs"])

    def test_node_replace_rejects_nononline_new_relation_evidence_atomically(self) -> None:
        graph = graph_fixture()
        catalog = generate_public_candidate_catalog(
            packet_fixture(graph), graph, config=config(),
        )
        candidate = next(
            item for item in catalog["candidates"]
            if item["program"].get("composition_label") == "REPLACE"
            and item["program"]["retraction_target"] == {
                "kind": "node_version", "version_id": "entity-a@v0",
            }
            and any(
                operation["op_type"] == "ADD_EDGE"
                for operation in item["program"]["operations"]
            )
        )
        evidence = deepcopy(candidate["online_evidence"])
        edge = next(
            operation["arguments"]["edge"]
            for operation in candidate["program"]["operations"]
            if operation["op_type"] == "ADD_EDGE"
        )
        evidence[edge["evidence_refs"][0]]["availability"] = "teacher"
        before = deepcopy(graph)
        with self.assertRaisesRegex(
            PreconditionError, "online supporting observation",
        ):
            execute_transaction(
                graph, candidate["program"], evidence_by_id=evidence,
            )
        self.assertEqual(graph, before)

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

    def test_split_public_relation_support_constrains_the_whole_group(self) -> None:
        graph = graph_fixture()
        public = packet_fixture(graph)
        public["region_observations"][2]["centroid_m"] = [0.0, 0.0, 0.0]
        catalog = generate_public_candidate_catalog(public, graph, config=config())
        related = [
            item["program"] for item in catalog["candidates"]
            if item["program"]["template"] == "SPLIT"
            and any(
                operation["op_type"] == "SET_LIFECYCLE"
                and operation["arguments"].get("node_id") == "entity-a"
                for operation in item["program"]["operations"]
            )
        ]
        self.assertEqual(len(related), 1)
        self.assertEqual(
            len(related[0]["split_relation_assignments"][0][
                "successor_node_ids"
            ]),
            1,
        )

    def test_split_oversized_assignment_group_is_not_partially_retained(self) -> None:
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
        split_audit = next(
            row for row in catalog["capacity_audit"]
            if row["bucket_id"] == "SPLIT|entity"
        )
        self.assertGreaterEqual(split_audit["oversized_group_count"], 1)
        self.assertGreaterEqual(split_audit["pre_cap_candidate_count"], 27)

    def test_split_ambiguity_and_total_edge_guards_are_independent(self) -> None:
        graph = graph_fixture()
        public = packet_fixture(graph)
        for guarded in (
            replace(config(), maximum_split_ambiguous_edges=0),
            replace(config(), maximum_split_total_incident_edges=0),
        ):
            catalog = generate_public_candidate_catalog(
                public, graph, config=guarded,
            )
            entity_a_splits = [
                item for item in catalog["candidates"]
                if item["program"]["template"] == "SPLIT"
                and any(
                    operation["op_type"] == "SET_LIFECYCLE"
                    and operation["arguments"].get("node_id") == "entity-a"
                    for operation in item["program"]["operations"]
                )
            ]
            self.assertEqual(entity_a_splits, [])

    def test_merge_reanchors_and_deduplicates_alias_incident_relations(self) -> None:
        graph = graph_fixture()
        graph["edges"].append({
            "edge_id": "edge:located-duplicate",
            "edge_version_id": "edge:located-duplicate@v0",
            "source": "entity-b",
            "target": "place-a",
            "relation": "located_at",
            "frame": "map",
            "valid_from": 0,
            "valid_to": None,
            "evidence_refs": ["observation:edge-duplicate"],
            "provenance": ["fixture:duplicate"],
        })
        graph = seal_graph(graph)
        catalog = generate_public_candidate_catalog(
            packet_fixture(graph), graph, config=config(),
        )
        program = next(
            item["program"] for item in catalog["candidates"]
            if item["program"]["template"] == "MERGE"
            and {
                operation["arguments"]["node_id"]
                for operation in item["program"]["operations"]
                if operation["op_type"] == "CLOSE_NODE_VERSION"
            } == {"entity-a", "entity-b"}
        )
        post = execute_transaction(graph, program)
        open_edges = [edge for edge in post["edges"] if edge["valid_to"] is None]
        located = [
            edge for edge in open_edges
            if edge["relation"] == "located_at"
            and edge["source"] == "entity-a"
            and edge["target"] == "place-a"
        ]
        self.assertEqual(len(located), 1)
        self.assertEqual(
            set(located[0]["evidence_refs"]),
            {"observation:edge", "observation:edge-duplicate"},
        )
        self.assertFalse(any(
            "entity-b" in {edge["source"], edge["target"]} for edge in open_edges
        ))
        self.assertEqual(len(program["merge_relation_rewrites"]), 1)
        self.assertEqual(
            len(program["merge_relation_rewrites"][0]["source_edge_version_ids"]), 2,
        )

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
            and item["program"]["split_relation_assignments"]
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
        self.assertEqual(left["capacity_audit"], right["capacity_audit"])

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
