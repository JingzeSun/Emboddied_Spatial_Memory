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
from tests.test_vm04_observation_runner import (  # noqa: E402
    _builder_receipt,
    _contract,
    _receipt,
    _route,
)
from tests.test_vm04_program_construction import (  # noqa: E402
    artifact,
    receipt as artifact_receipt,
)
from tests.test_vsmt_public_candidates import (  # noqa: E402
    graph_fixture,
    packet_fixture,
)
from vsmt.vm04_program_construction import (  # noqa: E402
    make_program_construction_plan,
)
from vsmt.vm04_program_matcher import (  # noqa: E402
    Vm04ProgramMatcherConfig,
    make_program_matcher_receipt,
    matcher_config_sha256,
    validate_program_matcher_receipt,
)


def config() -> Vm04ProgramMatcherConfig:
    return Vm04ProgramMatcherConfig(
        association_rules={
            kind: {
                "visual_weight": 0.7,
                "geometry_weight": 0.3,
                "geometry_scale_m": 1.0,
                "association_threshold": 0.8,
            }
            for kind in ("entity", "surface", "fragment")
        },
        minimum_region_reliability=0.9,
        minimum_unique_score_margin=0.05,
        minimum_relation_reliability=0.9,
        free_space_reliability_threshold=0.9,
        support_envelope_reliability_threshold=0.9,
        support_envelope_margin_m=0.02,
        minimum_free_space_time_separation_s=0.25,
        minimum_independent_negative_observations=2,
    )


def graph(*, include_active=True, include_dormant=False):
    value = graph_fixture()
    nodes = []
    for node in value["nodes"]:
        if node["node_id"] == "entity-a" and not include_active:
            continue
        if node["node_id"] == "entity-b":
            continue
        if node["node_id"] == "entity-d" and not include_dormant:
            continue
        nodes.append(node)
    return seal_graph({
        **{key: item for key, item in value.items() if key != "graph_hash"},
        "nodes": nodes,
        "edges": [
            edge for edge in value["edges"]
            if include_active or edge["source"] != "entity-a"
        ],
    })


def route_and_receipt(program, target_mask_sha256):
    route = _route(program)
    receipt = _receipt(route)
    for index in route["terminal_reobservation_indices"]:
        row = receipt["observations"][index]
        assessment = dict(row["visibility_assessment"])
        assessment.pop("assessment_sha256")
        assessment["current_public_support_sha256"] = target_mask_sha256
        from vsmt.vm04_observation_runner import make_public_visibility_assessment
        assessment = make_public_visibility_assessment(
            subject_public_ref=assessment["subject_public_ref"],
            subject_reference_sealed_before_frame=True,
            projected_public_sample_count=assessment[
                "projected_public_sample_count"
            ],
            unoccluded_public_sample_count=assessment[
                "unoccluded_public_sample_count"
            ],
            current_public_support_sha256=target_mask_sha256,
            terminal_reobservation_phase=True,
        )
        builder = _builder_receipt(assessment, index)
        row["visibility_assessment"] = assessment
        row["visibility_builder_receipt"] = builder
        row["public_evidence_sha256"] = builder["receipt_sha256"]
    return route, receipt


def plan(program, memory, refs, *, episode_id, artifact_plan=None):
    return make_program_construction_plan(
        episode_id=episode_id, family_id="family:001",
        program=program, prior_memory=memory,
        prior_memory_sha256=memory["graph_hash"], precondition_refs=refs,
        visibility_subject_seal_sha256="a" * 64,
        matcher_config_sha256=matcher_config_sha256(config()),
        artifact_plan=artifact_plan,
    )


def run(program, memory, packet, refs, *, artifact_plan=None,
        artifact_result=None):
    target_mask = packet["region_observations"][0]["mask_sha256"]
    route, route_receipt = route_and_receipt(program, target_mask)
    construction = plan(
        program, memory, refs, episode_id=route["episode_id"],
        artifact_plan=artifact_plan,
    )
    return make_program_matcher_receipt(
        construction_plan=construction, prior_memory=memory,
        current_packet=packet, route_plan=route, route_receipt=route_receipt,
        observation_contract=_contract(), config=config(),
        artifact_plan=artifact_plan, artifact_receipt=artifact_result,
    )


class Vm04ProgramMatcherTests(unittest.TestCase):
    def test_noop_requires_every_reliable_region_to_have_an_active_unique_match(self):
        memory = graph()
        packet = packet_fixture(memory)
        packet["region_observations"] = [packet["region_observations"][0]]
        packet["relation_observations"] = []
        result = run("NOOP", memory, packet, {
            "stable_public_memory_sha256": memory["graph_hash"],
            "current_observation_rule_sha256": "1" * 64,
        })
        self.assertTrue(result["program_public_match_satisfied"])

        packet["region_observations"][0]["descriptor"] = [-1.0, 0.0]
        failed = run("NOOP", memory, packet, {
            "stable_public_memory_sha256": memory["graph_hash"],
            "current_observation_rule_sha256": "1" * 64,
        })
        self.assertFalse(failed["program_public_match_satisfied"])

    def test_bind_and_birth_are_separated_by_public_match(self):
        memory = graph()
        packet = packet_fixture(memory)
        packet["region_observations"] = [packet["region_observations"][0]]
        packet["relation_observations"] = []
        bind = run("BIND", memory, packet, {
            "open_node_version_id": "entity-a@v0",
            "prior_evidence_sha256": "1" * 64,
            "current_region_selection_rule_sha256": "2" * 64,
        })
        self.assertTrue(bind["program_public_match_satisfied"])
        self.assertFalse(bind["semantic_identity_truth_established"])

        birth = run("BIRTH", memory, packet, {
            "reveal_locus_public_ref": "locus:new",
            "absence_scope_sha256": "1" * 64,
        })
        self.assertFalse(birth["program_public_match_satisfied"])
        self.assertIn("BIRTH_target_has_public_prior_match",
                      birth["construction_failure_reasons"])

        unmatched = packet_fixture(memory, current_bind_matches=False)
        unmatched["region_observations"] = [unmatched["region_observations"][0]]
        unmatched["relation_observations"] = []
        born = run("BIRTH", memory, unmatched, {
            "reveal_locus_public_ref": "locus:new",
            "absence_scope_sha256": "1" * 64,
        })
        self.assertTrue(born["program_public_match_satisfied"])

    def test_reactivate_requires_registered_dormant_match(self):
        memory = graph(include_active=False, include_dormant=True)
        dormant = next(
            node for node in memory["nodes"] if node["node_id"] == "entity-d"
        )
        dormant["vsmt_observation_state"]["centroid_m"] = [0.0, 0.0, 0.0]
        dormant["vsmt_observation_state"]["observation_aabb_min_m"] = [
            -0.05, -0.05, -0.05,
        ]
        dormant["vsmt_observation_state"]["observation_aabb_max_m"] = [
            0.05, 0.05, 0.05,
        ]
        memory = seal_graph({key: value for key, value in memory.items()
                             if key != "graph_hash"})
        packet = packet_fixture(memory)
        packet["region_observations"] = [packet["region_observations"][0]]
        packet["relation_observations"] = []
        result = run("REACTIVATE", memory, packet, {
            "dormant_node_version_id": "entity-d@v0",
            "prior_evidence_sha256": "1" * 64,
        })
        self.assertTrue(result["program_public_match_satisfied"])

    def test_relink_requires_public_new_place_relation(self):
        memory = graph()
        packet = packet_fixture(memory)
        packet["region_observations"].pop(1)
        packet["region_observations"][1]["region_id"] = "region:0001"
        packet["relation_observations"][0]["target_region_id"] = "region:0001"
        result = run("RELINK", memory, packet, {
            "open_entity_node_version_id": "entity-a@v0",
            "old_located_at_edge_version_id": "edge:located@v0",
            "old_place_node_version_id": "place-a@v0",
            "new_place_public_ref": "place-b@v0",
        })
        self.assertTrue(result["program_public_match_satisfied"])
        self.assertEqual(result["relation_evidence"][
            "new_place_node_version_id"], "place-b@v0")

        packet["relation_observations"] = []
        failed = run("RELINK", memory, packet, {
            "open_entity_node_version_id": "entity-a@v0",
            "old_located_at_edge_version_id": "edge:located@v0",
            "old_place_node_version_id": "place-a@v0",
            "new_place_public_ref": "place-b@v0",
        })
        self.assertFalse(failed["program_public_match_satisfied"])

    def test_retract_and_replace_require_two_visible_empty_observations(self):
        memory = graph()
        packet = packet_fixture(memory, current_bind_matches=False)
        packet["region_observations"] = [packet["region_observations"][0]]
        packet["relation_observations"] = []
        retract = run("RETRACT", memory, packet, {
            "open_entity_or_edge_version_id": "entity-a@v0",
            "prior_evidence_sha256": "1" * 64,
            "absence_rule_sha256": "2" * 64,
        })
        self.assertTrue(retract["program_public_match_satisfied"])
        self.assertEqual(retract["negative_evidence_count"], 2)

        one = packet_fixture(
            memory, free_times=(0.5,), current_bind_matches=False,
        )
        one["region_observations"] = [one["region_observations"][0]]
        one["relation_observations"] = []
        failed = run("REPLACE", memory, one, {
            "open_old_entity_node_version_id": "entity-a@v0",
            "new_reveal_locus_public_ref": "locus:replacement",
            "new_identity_absence_scope_sha256": "1" * 64,
        })
        self.assertFalse(failed["program_public_match_satisfied"])
        self.assertIn("insufficient_independent_visible_empty_evidence",
                      failed["construction_failure_reasons"])

    def test_split_receipt_is_required_and_does_not_establish_identity_truth(self):
        memory = graph()
        packet = packet_fixture(memory)
        split_plan = artifact("SPLIT", 2)
        valid = artifact_receipt(split_plan, [(1, 2), (1, 2)])
        result = run("SPLIT", memory, packet, {
            "undersegmented_prior_node_version_id": "entity-a@v0",
            "artifact_plan_sha256": split_plan["artifact_plan_sha256"],
        }, artifact_plan=split_plan, artifact_result=valid)
        self.assertTrue(result["program_public_match_satisfied"])
        self.assertFalse(result["private_identity_used"])
        self.assertFalse(result["semantic_identity_truth_established"])

        merge_memory = graph_fixture()
        merge_packet = packet_fixture(merge_memory)
        merge_plan = artifact("MERGE", 1)
        merged = artifact_receipt(merge_plan, [(2, 1)])
        merge = run("MERGE", merge_memory, merge_packet, {
            "first_prior_node_version_id": "entity-a@v0",
            "second_prior_node_version_id": "entity-b@v0",
            "artifact_plan_sha256": merge_plan["artifact_plan_sha256"],
        }, artifact_plan=merge_plan, artifact_result=merged)
        self.assertTrue(merge["program_public_match_satisfied"])

    def test_matcher_values_are_bound_and_have_no_implicit_defaults(self):
        with self.assertRaises(TypeError):
            Vm04ProgramMatcherConfig()  # type: ignore[call-arg]
        changed = replace(config(), minimum_unique_score_margin=0.1)
        self.assertNotEqual(
            matcher_config_sha256(config()), matcher_config_sha256(changed),
        )
        schema = json.loads((
            ROOT / "schemas/vsmt_vm04_program_matcher.schema.json"
        ).read_text(encoding="utf-8"))
        self.assertEqual(len(schema["oneOf"]), 2)
        self.assertIn("receipt", schema["$defs"])

    def test_matcher_receipt_tampering_is_rejected_by_replay(self):
        memory = graph()
        packet = packet_fixture(memory)
        packet["region_observations"] = [packet["region_observations"][0]]
        packet["relation_observations"] = []
        route, route_receipt = route_and_receipt(
            "BIND", packet["region_observations"][0]["mask_sha256"],
        )
        construction = plan(
            "BIND", memory, {
                "open_node_version_id": "entity-a@v0",
                "prior_evidence_sha256": "1" * 64,
                "current_region_selection_rule_sha256": "2" * 64,
            }, episode_id=route["episode_id"],
        )
        inputs = {
            "construction_plan": construction,
            "prior_memory": memory,
            "current_packet": packet,
            "route_plan": route,
            "route_receipt": route_receipt,
            "observation_contract": _contract(),
            "config": config(),
        }
        receipt = make_program_matcher_receipt(**inputs)
        validate_program_matcher_receipt(receipt, **inputs)
        receipt["program_public_match_satisfied"] = False
        with self.assertRaisesRegex(ValueError, "does not reproduce"):
            validate_program_matcher_receipt(receipt, **inputs)


if __name__ == "__main__":
    unittest.main()
