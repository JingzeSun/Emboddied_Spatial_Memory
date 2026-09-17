from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cpmt.hashing import seal_graph  # noqa: E402
from tests.test_vsmt_public_candidates import (  # noqa: E402
    config as candidate_config,
    graph_fixture,
    node,
    packet_fixture,
)
from vsmt.d213_unified_graph import (  # noqa: E402
    D213Error,
    allowed_templates,
    audit_sealed_candidate_catalog,
    build_ablation_memory_view,
    graph_complexity_metrics,
    validate_contract,
    validate_unified_graph,
    validate_unsealed_candidate_rows,
)
from vsmt.public_candidates import generate_public_candidate_catalog  # noqa: E402


CONTRACT_PATH = ROOT / "configs/vsmt/vm04_d213_unified_typed_graph_v1.json"


class D213UnifiedTypedGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = validate_contract(json.loads(
            CONTRACT_PATH.read_text(encoding="utf-8")
        ))

    def test_contract_freezes_unified_graph_gate_and_five_ablations(self) -> None:
        self.assertEqual(
            ["place", "entity", "surface", "fragment"],
            self.contract["unified_graph"]["node_types"],
        )
        self.assertEqual(
            ["NOOP", "BIND", "BIRTH", "MERGE"],
            self.contract["typed_gate"]["place"],
        )
        self.assertFalse(self.contract["transaction_vocabulary"]["create_is_atom"])
        self.assertEqual(
            ["Place-4", "VSMT-Typed", "VSMT-Flat8", "VSMT-NoPlace",
             "VSMT-NoVersion"],
            list(self.contract["ablations"]),
        )
        self.assertFalse(any(self.contract["authorization"].values()))

    def test_gate_rejects_place_retract_before_candidate_seal(self) -> None:
        row = {
            "program": {
                "template": "RETRACT",
                "operations": [],
            },
            "enumeration": {"bucket_id": "RETRACT|place"},
        }
        with self.assertRaisesRegex(D213Error, "not legal for scope 'place'"):
            validate_unsealed_candidate_rows(
                [row], variant="VSMT-Typed", contract=self.contract,
            )
        audit = validate_unsealed_candidate_rows(
            [row], variant="VSMT-Flat8", contract=self.contract,
        )
        self.assertEqual(1, audit["candidate_count"])
        self.assertTrue(audit["gate_inputs_public_only"])

    def test_relation_birth_is_an_atom_plus_add_edge_not_create(self) -> None:
        row = {
            "program": {
                "template": "BIRTH",
                "operations": [{"op_type": "ADD_EDGE", "arguments": {}}],
            },
            "enumeration": {"bucket_id": "BIRTH|relation:route_transition"},
        }
        validate_unsealed_candidate_rows(
            [row], variant="VSMT-Typed", contract=self.contract,
        )
        poisoned = json.loads(json.dumps(row))
        poisoned["program"]["template"] = "CREATE"
        with self.assertRaisesRegex(D213Error, "unknown atom"):
            validate_unsealed_candidate_rows(
                [poisoned], variant="VSMT-Typed", contract=self.contract,
            )

    def test_place_only_and_no_place_have_opposite_relation_visibility(self) -> None:
        self.assertTrue(allowed_templates(
            "relation:route_transition", variant="Place-4",
            contract=self.contract,
        ))
        self.assertFalse(allowed_templates(
            "relation:supported_by", variant="Place-4",
            contract=self.contract,
        ))
        self.assertFalse(allowed_templates(
            "relation:located_at", variant="VSMT-NoPlace",
            contract=self.contract,
        ))
        self.assertTrue(allowed_templates(
            "relation:supported_by", variant="VSMT-NoPlace",
            contract=self.contract,
        ))

    def test_public_candidate_generator_can_enforce_the_typed_gate(self) -> None:
        graph = graph_fixture()
        configured = replace(
            candidate_config(), typed_gate_contract=self.contract,
            candidate_variant="VSMT-Typed",
        )
        catalog = generate_public_candidate_catalog(
            packet_fixture(graph), graph, config=configured,
        )
        audit = audit_sealed_candidate_catalog(
            catalog, variant="VSMT-Typed", contract=self.contract,
        )
        self.assertEqual(len(catalog["candidates"]), audit["candidate_count"])
        self.assertEqual(catalog["catalog_sha256"], audit["catalog_sha256"])

    def test_relation_reactivation_is_executable_and_preserves_identity(self) -> None:
        graph = graph_fixture()
        graph["edges"][0]["valid_to"] = 1
        graph = seal_graph(graph)
        packet = packet_fixture(graph)
        packet["region_observations"][2]["centroid_m"] = [0.0, 0.0, 0.0]
        configured = replace(
            candidate_config(), typed_gate_contract=self.contract,
            candidate_variant="VSMT-Typed",
        )
        catalog = generate_public_candidate_catalog(
            packet, graph, config=configured,
        )
        rows = [
            item for item in catalog["candidates"]
            if item["program"]["template"] == "REACTIVATE"
            and item["enumeration"]["bucket_id"]
            == "REACTIVATE|relation:located_at"
        ]
        self.assertTrue(rows)
        reopened = next(
            operation["arguments"]["edge"]
            for operation in rows[0]["program"]["operations"]
            if operation["op_type"] == "ADD_EDGE"
        )
        self.assertEqual("edge:located", reopened["edge_id"])
        self.assertNotEqual("edge:located@v0", reopened["edge_version_id"])

    def test_surface_retract_is_generated_but_place_retract_is_not(self) -> None:
        graph = graph_fixture()
        graph["nodes"].append(node("surface-a", "surface", [0.0, 0.0, 0.0]))
        graph = seal_graph(graph)
        configured = replace(
            candidate_config(), typed_gate_contract=self.contract,
            candidate_variant="VSMT-Typed",
        )
        catalog = generate_public_candidate_catalog(
            packet_fixture(graph, current_bind_matches=False), graph,
            config=configured,
        )
        buckets = {
            item["enumeration"]["bucket_id"] for item in catalog["candidates"]
        }
        self.assertIn("RETRACT|surface", buckets)
        self.assertNotIn("RETRACT|place", buckets)

    def test_unified_graph_checks_route_edges_and_derived_entity_cache(self) -> None:
        graph = graph_fixture()
        for node in graph["nodes"]:
            if node["node_id"] == "place-a":
                node["vsmt_observation_state"]["contained_entity_refs"] = [
                    "entity-a"
                ]
        graph["edges"].append({
            "edge_id": "edge:route",
            "edge_version_id": "edge:route@v0",
            "source": "place-a",
            "target": "place-b",
            "relation": "route_transition",
            "frame": "map",
            "valid_from": 0,
            "valid_to": None,
            "evidence_refs": ["observation:route"],
            "provenance": ["fixture:route"],
        })
        graph = seal_graph(graph)
        validate_unified_graph(graph, contract=self.contract)
        poisoned = json.loads(json.dumps(graph))
        place = next(
            node for node in poisoned["nodes"] if node["node_id"] == "place-a"
        )
        place["vsmt_observation_state"]["contained_entity_refs"] = []
        poisoned = seal_graph(poisoned)
        with self.assertRaisesRegex(D213Error, "relation-derived cache"):
            validate_unified_graph(poisoned, contract=self.contract)

    def test_ablation_views_remove_exactly_the_registered_information(self) -> None:
        graph = graph_fixture()
        no_place = build_ablation_memory_view(
            graph, variant="VSMT-NoPlace", contract=self.contract,
        )
        self.assertNotIn("place", no_place["node_types_visible"])
        self.assertTrue(all(
            edge["relation"] != "located_at" for edge in no_place["edges"]
        ))
        no_version = build_ablation_memory_view(
            graph, variant="VSMT-NoVersion", contract=self.contract,
        )
        self.assertFalse(no_version["version_history_visible_to_model"])
        self.assertEqual([], no_version["transaction_log"])
        self.assertTrue(all(
            "node_version_id" not in node for node in no_version["nodes"]
        ))
        typed = build_ablation_memory_view(
            graph, variant="VSMT-Typed", contract=self.contract,
        )
        self.assertTrue(typed["version_history_visible_to_model"])
        self.assertTrue(all("node_version_id" in node for node in typed["nodes"]))

    def test_complexity_metrics_are_derived_from_graph_bytes(self) -> None:
        graph = graph_fixture()
        metrics = graph_complexity_metrics(graph, contract=self.contract)
        self.assertEqual(5, metrics["active_node_count"])
        self.assertEqual({"entity": 3, "place": 2},
                         metrics["active_node_count_by_type"])
        self.assertEqual({"located_at": 1},
                         metrics["active_edge_count_by_relation"])
        self.assertEqual(0, metrics["historical_node_version_count"])


if __name__ == "__main__":
    unittest.main()
