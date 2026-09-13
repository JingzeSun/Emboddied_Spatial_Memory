from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from cpmt.hashing import seal_graph  # noqa: E402
from vsmt.contracts import (  # noqa: E402
    INVARIANCE_SCHEMA,
    PRIVATE_SCHEMA,
    RESULT_SCHEMA,
    build_adapter_input,
    canonical_sha256,
    load_public_observation,
    run_adapter,
    seal_candidate_catalog,
    seal_private_evaluation,
    seal_teacher_targets,
    validate_candidate_catalog,
    validate_memory_update_result,
    validate_observation_packet,
    validate_private_mutation_invariance,
    validate_teacher_targets,
)


def make_memory() -> dict[str, Any]:
    return seal_graph({
        "schema_version": "cpmt-0.2",
        "graph_id": "graph:fixture",
        "graph_version": "v0",
        "parent_version": None,
        "nodes": [{
            "node_id": "place-1",
            "node_version_id": "place-1@v0",
            "node_type": "place",
            "lifecycle": "confirmed",
            "valid_from": 0,
            "valid_to": None,
            "evidence_refs": ["observation:0000"],
            "latent_refs": [],
            "canonical_id": None,
            "predecessor_ids": [],
            "provenance": ["fixture:public"],
        }],
        "edges": [],
        "transaction_log": [],
    })


def make_packet(memory: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "vsmt-observation-packet-v1",
        "sample_id_hash": "1" * 64,
        "decision_time_s": 2.0,
        "rgbd_refs": {
            "rgb_sha256": "2" * 64,
            "depth_sha256": "3" * 64,
        },
        "camera_pose": {
            "position_m": [0.0, 1.0, 0.0],
            "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
        },
        "robot_state": {
            "feature_names": ["x_m", "y_m"],
            "values": [0.1, 0.2],
        },
        "past_actions": [{"end_time_s": 1.5, "command": [0.0, 0.1]}],
        "region_observations": [{
            "region_id": "region:0000",
            "mask_sha256": "4" * 64,
            "descriptor": [0.25, -0.5],
            "centroid_m": [0.0, 0.0, 1.0],
            "extent_m": [0.2, 0.1, 0.3],
            "reliability": 0.8,
            "proposal_source_id": "fixed.region.v1",
        }],
        "prior_memory_ref": {
            "graph_version": memory["graph_version"],
            "graph_sha256": memory["graph_hash"],
        },
        "public_constants": {
            "coordinate_frame": "map",
            "depth_unit": "metre",
            "descriptor_model_id": "dinov2.vits14",
            "proposal_model_id": "fixed.region.v1",
        },
    }


def make_noop_program(memory: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "cpmt-0.2",
        "transaction_id": "txn:opaque:0000",
        "intent": "PRESERVE",
        "template": "NOOP",
        "base_graph_version": memory["graph_version"],
        "operations": [],
        "evidence_refs": [],
        "protected_ids": [],
        "proposer": "deterministic",
    }


def make_catalog(
    packet: Mapping[str, Any], memory: Mapping[str, Any],
) -> dict[str, Any]:
    return seal_candidate_catalog(
        packet,
        memory,
        generator_id="public.candidate.v1",
        derivations=[{
            "name": "region.memory.association",
            "public_fields": ["/region_observations/0/descriptor"],
            "prior_memory_fields": ["/nodes"],
        }],
        programs=[make_noop_program(memory)],
    )


def make_result(memory: Mapping[str, Any], method_id: str) -> dict[str, Any]:
    return {
        "schema_version": RESULT_SCHEMA,
        "method_id": method_id,
        "pre_memory_sha256": memory["graph_hash"],
        "post_memory": deepcopy(memory),
        "post_memory_sha256": memory["graph_hash"],
        "normalized_delta": {
            "declared_template": "NOOP",
            "created_node_version_ids": [],
            "closed_node_version_ids": [],
            "created_edge_version_ids": [],
            "closed_edge_version_ids": [],
        },
        "confidence": 0.5,
        "runtime_ms": 1.0,
        "diagnostics": {"candidate_count": 1},
    }


class FixtureAdapter:
    method_id = "fixture.adapter"

    def __init__(self, memory: Mapping[str, Any], *, mutate: bool = False):
        self.memory = memory
        self.mutate = mutate
        self.seen_keys: set[str] = set()

    def update(self, model_input: dict[str, Any]) -> Mapping[str, Any]:
        self.seen_keys = set(model_input)
        if self.mutate:
            model_input["region_observations"][0]["reliability"] = 0.0
        return make_result(self.memory, self.method_id)


class VSMTContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.memory = make_memory()
        self.packet = make_packet(self.memory)

    def test_adapter_input_strips_audit_identity_and_artifact_hashes(self) -> None:
        model_input = build_adapter_input(self.packet, self.memory)
        self.assertEqual(
            set(model_input),
            {
                "decision_time_s", "camera_pose", "robot_state", "past_actions",
                "region_observations", "prior_memory", "public_constants",
            },
        )
        self.assertNotIn("sample_id_hash", model_input)
        self.assertNotIn("rgbd_refs", model_input)
        self.assertNotIn("prior_memory_ref", model_input)

    def test_public_packet_rejects_private_reference_field(self) -> None:
        packet = deepcopy(self.packet)
        packet["reference_spec"] = {"target_node_id": "place-1"}
        with self.assertRaises(ValueError):
            validate_observation_packet(packet)

    def test_public_packet_rejects_action_after_decision_time(self) -> None:
        packet = deepcopy(self.packet)
        packet["past_actions"][0]["end_time_s"] = 2.1
        with self.assertRaisesRegex(ValueError, "not enter the future"):
            validate_observation_packet(packet)

    def test_public_packet_rejects_semantic_region_identifier(self) -> None:
        packet = deepcopy(self.packet)
        packet["region_observations"][0]["region_id"] = "region:chair"
        with self.assertRaisesRegex(ValueError, "opaque ordinals"):
            validate_observation_packet(packet)

    def test_adapter_input_requires_exact_prior_memory_binding(self) -> None:
        packet = deepcopy(self.packet)
        packet["prior_memory_ref"]["graph_sha256"] = "9" * 64
        with self.assertRaisesRegex(ValueError, "digest does not match"):
            build_adapter_input(packet, self.memory)

    def test_adapter_input_rejects_private_field_hidden_in_prior_memory(self) -> None:
        memory = deepcopy(self.memory)
        memory["nodes"][0]["reference_node_id"] = "private-42"
        memory = seal_graph(memory)
        packet = make_packet(memory)
        with self.assertRaisesRegex(ValueError, "forbidden information key"):
            build_adapter_input(packet, memory)

    def test_candidate_derivation_rejects_private_pointer(self) -> None:
        catalog = make_catalog(self.packet, self.memory)
        catalog["derivations"][0]["public_fields"] = ["/private_eval/answer"]
        catalog["catalog_sha256"] = canonical_sha256({
            key: value for key, value in catalog.items() if key != "catalog_sha256"
        })
        with self.assertRaises(ValueError):
            validate_candidate_catalog(catalog)

    def test_candidate_program_rejects_oracle_proposer(self) -> None:
        program = make_noop_program(self.memory)
        program["proposer"] = "oracle"
        with self.assertRaises(ValueError):
            seal_candidate_catalog(
                self.packet,
                self.memory,
                generator_id="public.candidate.v1",
                derivations=[{
                    "name": "region.memory.association",
                    "public_fields": ["/region_observations"],
                    "prior_memory_fields": ["/nodes"],
                }],
                programs=[program],
            )

    def test_teacher_cannot_insert_or_reorder_candidates(self) -> None:
        catalog = make_catalog(self.packet, self.memory)
        targets = seal_teacher_targets(
            catalog, teacher_id="hindsight.teacher.v1",
            scores=[0.0], probabilities=[1.0],
        )
        targets["targets"][0]["candidate_id"] = "candidate:9999"
        with self.assertRaisesRegex(ValueError, "exact candidate IDs and order"):
            validate_teacher_targets(targets, catalog)

    def test_run_adapter_exposes_only_deployable_fields(self) -> None:
        adapter = FixtureAdapter(self.memory)
        result = run_adapter(adapter, self.packet, self.memory)
        self.assertEqual(result["method_id"], adapter.method_id)
        self.assertEqual(adapter.seen_keys, {
            "decision_time_s", "camera_pose", "robot_state", "past_actions",
            "region_observations", "prior_memory", "public_constants",
        })

    def test_run_adapter_detects_input_mutation(self) -> None:
        adapter = FixtureAdapter(self.memory, mutate=True)
        with self.assertRaisesRegex(ValueError, "input mutated"):
            run_adapter(adapter, self.packet, self.memory)

    def test_result_rejects_private_field_hidden_in_post_memory(self) -> None:
        post_memory = deepcopy(self.memory)
        post_memory["nodes"][0]["future_identity"] = "private-42"
        post_memory = seal_graph(post_memory)
        result = make_result(self.memory, "fixture.adapter")
        result["post_memory"] = post_memory
        result["post_memory_sha256"] = post_memory["graph_hash"]
        with self.assertRaisesRegex(ValueError, "forbidden information key"):
            validate_memory_update_result(result)

    def test_private_mutation_requires_identical_online_artifacts(self) -> None:
        shared = {
            "schema_version": INVARIANCE_SCHEMA,
            "public_sha256": canonical_sha256(self.packet),
            "candidate_catalog_sha256": make_catalog(
                self.packet, self.memory,
            )["catalog_sha256"],
            "adapter_input_sha256": canonical_sha256(
                build_adapter_input(self.packet, self.memory)
            ),
            "logits_sha256": "5" * 64,
        }
        left = {**shared, "private_sha256": "6" * 64}
        right = {**shared, "private_sha256": "7" * 64}
        validate_private_mutation_invariance([left, right])
        right["logits_sha256"] = "8" * 64
        with self.assertRaisesRegex(ValueError, "changed logits_sha256"):
            validate_private_mutation_invariance([left, right])

    def test_private_record_is_rejected_by_public_validator(self) -> None:
        private = seal_private_evaluation({
            "schema_version": PRIVATE_SCHEMA,
            "sample_id_hash": self.packet["sample_id_hash"],
            "public_sha256": canonical_sha256(self.packet),
            "reference_memory": self.memory,
            "reference_transaction_equivalence": [["candidate:0000"]],
            "future_observation_sha256": ["8" * 64],
            "simulator_identity_map": {"sim-42": "place-1"},
            "semantic_case_id": "semantic.bind_or_birth",
        })
        with self.assertRaises(ValueError):
            validate_observation_packet(private)

    def test_file_loader_rejects_duplicate_json_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "public.json"
            path.write_text('{"schema_version":"x","schema_version":"y"}',
                            encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                load_public_observation(path)


if __name__ == "__main__":
    unittest.main()
