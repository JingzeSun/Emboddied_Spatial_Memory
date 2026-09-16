from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cpmt.hashing import canonical_json, seal_graph  # noqa: E402
from vsmt.graph_ops import STATE_KEY  # noqa: E402
from vsmt.vm04_program_construction import (  # noqa: E402
    ARTIFACT_RECEIPT_SCHEMA,
    make_program_construction_plan,
    make_split_merge_artifact_plan,
    validate_split_merge_artifact_receipt,
)


def sha(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def node(node_id, node_type, lifecycle="confirmed"):
    state = {
        "descriptor": [1.0, 0.0], "centroid_m": [0.0, 0.0, 0.0],
        "extent_m": [0.1, 0.1, 0.1], "reliability": 1.0,
        "last_seen_s": 0.0, "observation_count": 1,
        "observation_aabb_min_m": [-0.05, -0.05, -0.05],
        "observation_aabb_max_m": [0.05, 0.05, 0.05],
        "support_envelope_min_m": [-0.05, -0.05, -0.05],
        "support_envelope_max_m": [0.05, 0.05, 0.05],
        "support_envelope_observation_count": 1,
        "support_envelope_reliability_threshold": 0.9,
    }
    if node_type == "place":
        state["place_scaffold_key"] = node_id
    return {
        "node_id": node_id, "node_version_id": f"{node_id}@v0",
        "node_type": node_type, "lifecycle": lifecycle,
        "valid_from": 0, "valid_to": None,
        "evidence_refs": [f"observation:{node_id}"],
        "latent_refs": [f"latent:{sha(node_id)}"], "canonical_id": None,
        "predecessor_ids": [], "provenance": ["fixture:public"],
        STATE_KEY: state,
    }


def memory():
    return seal_graph({
        "schema_version": "cpmt-0.2", "graph_id": "graph:construction",
        "graph_version": "v0", "parent_version": None,
        "nodes": [
            node("entity-a", "entity"), node("entity-b", "entity"),
            node("entity-d", "entity", "dormant"), node("place-a", "place"),
        ],
        "edges": [{
            "edge_id": "edge:located", "edge_version_id": "edge:located@v0",
            "source": "entity-a", "target": "place-a",
            "relation": "located_at", "frame": "map", "valid_from": 0,
            "valid_to": None, "evidence_refs": ["observation:edge"],
            "provenance": ["fixture:public"],
        }],
        "transaction_log": [],
    })


def artifact(program="SPLIT", repeats=2):
    return make_split_merge_artifact_plan(
        program=program, family_id="family:001",
        geometry_spec_sha256="1" * 64,
        frontend_config_sha256="2" * 64,
        far_pose_public_ref="pose:far", near_pose_public_ref="pose:near",
        fresh_replay_repeat_count=repeats,
    )


def receipt(plan, counts):
    rows = []
    for index, (far_count, near_count) in enumerate(counts):
        rows.append({
            "replay_index": index,
            "far_public_packet_sha256": f"{index + 3:x}" * 64,
            "near_public_packet_sha256": f"{index + 5:x}" * 64,
            "far_public_entity_region_ids": [
                f"region:far:{item}" for item in range(far_count)
            ],
            "near_public_entity_region_ids": [
                f"region:near:{item}" for item in range(near_count)
            ],
            "transition_support_sha256": f"{index + 7:x}" * 64,
        })
    expected = ((1, 2) if plan["program"] == "SPLIT" else (2, 1))
    realized = all(pair == expected for pair in counts)
    value = {
        "schema_version": ARTIFACT_RECEIPT_SCHEMA,
        "artifact_plan_sha256": plan["artifact_plan_sha256"],
        "program": plan["program"], "replays": rows,
        "artifact_realized_on_every_replay": realized,
        "construction_failure_reason": (
            None if realized else "registered_split_merge_artifact_not_realized"
        ),
        "posthoc_relabel_or_replacement_used": False,
    }
    value["receipt_sha256"] = sha(value)
    return value


class Vm04ProgramConstructionTests(unittest.TestCase):
    def test_all_nine_programs_have_distinct_machine_checked_slots(self):
        graph = memory()
        split = artifact("SPLIT", 2)
        merge = artifact("MERGE", 2)
        refs = {
            "NOOP": {
                "stable_public_memory_sha256": graph["graph_hash"],
                "current_observation_rule_sha256": "1" * 64,
            },
            "BIND": {
                "open_node_version_id": "entity-a@v0",
                "prior_evidence_sha256": "1" * 64,
                "current_region_selection_rule_sha256": "2" * 64,
            },
            "BIRTH": {
                "reveal_locus_public_ref": "locus:new",
                "absence_scope_sha256": "1" * 64,
            },
            "REACTIVATE": {
                "dormant_node_version_id": "entity-d@v0",
                "prior_evidence_sha256": "1" * 64,
            },
            "RELINK": {
                "open_entity_node_version_id": "entity-a@v0",
                "old_located_at_edge_version_id": "edge:located@v0",
                "old_place_node_version_id": "place-a@v0",
                "new_place_public_ref": "place-public:P2",
            },
            "RETRACT": {
                "open_entity_or_edge_version_id": "entity-a@v0",
                "prior_evidence_sha256": "1" * 64,
                "absence_rule_sha256": "2" * 64,
            },
            "SPLIT": {
                "undersegmented_prior_node_version_id": "entity-a@v0",
                "artifact_plan_sha256": split["artifact_plan_sha256"],
            },
            "MERGE": {
                "first_prior_node_version_id": "entity-a@v0",
                "second_prior_node_version_id": "entity-b@v0",
                "artifact_plan_sha256": merge["artifact_plan_sha256"],
            },
            "REPLACE": {
                "open_old_entity_node_version_id": "entity-a@v0",
                "new_reveal_locus_public_ref": "locus:replacement",
                "new_identity_absence_scope_sha256": "1" * 64,
            },
        }
        for program, preconditions in refs.items():
            with self.subTest(program=program):
                plan = make_program_construction_plan(
                    episode_id=f"episode:{program.lower()}",
                    family_id="family:001", program=program,
                    prior_memory=graph, prior_memory_sha256=graph["graph_hash"],
                    precondition_refs=preconditions,
                    visibility_subject_seal_sha256="a" * 64,
                    artifact_plan=(split if program == "SPLIT" else
                                   merge if program == "MERGE" else None),
                )
                self.assertEqual(plan["program"], program)

    def test_relink_requires_the_open_old_located_at_edge(self):
        graph = memory()
        plan = make_program_construction_plan(
            episode_id="episode:001", family_id="family:001",
            program="RELINK", prior_memory=graph,
            prior_memory_sha256=graph["graph_hash"],
            precondition_refs={
                "open_entity_node_version_id": "entity-a@v0",
                "old_located_at_edge_version_id": "edge:located@v0",
                "old_place_node_version_id": "place-a@v0",
                "new_place_public_ref": "place-public:P2",
            },
            visibility_subject_seal_sha256="a" * 64, artifact_plan=None,
        )
        self.assertEqual(plan["program"], "RELINK")
        self.assertFalse(plan["restricted_inputs_used"])

        graph["edges"][0]["relation"] = "adjacent_to"
        graph = seal_graph({key: value for key, value in graph.items()
                            if key != "graph_hash"})
        with self.assertRaisesRegex(ValueError, "old located_at"):
            make_program_construction_plan(
                episode_id="episode:002", family_id="family:001",
                program="RELINK", prior_memory=graph,
                prior_memory_sha256=graph["graph_hash"],
                precondition_refs={
                    "open_entity_node_version_id": "entity-a@v0",
                    "old_located_at_edge_version_id": "edge:located@v0",
                    "old_place_node_version_id": "place-a@v0",
                    "new_place_public_ref": "place-public:P2",
                },
                visibility_subject_seal_sha256="a" * 64, artifact_plan=None,
            )

    def test_split_artifact_must_repeat_without_relabel(self):
        plan = artifact("SPLIT", 2)
        valid = receipt(plan, [(1, 2), (1, 2)])
        self.assertTrue(validate_split_merge_artifact_receipt(
            valid, plan=plan,
        )["artifact_realized_on_every_replay"])

        failed = receipt(plan, [(1, 2), (1, 1)])
        result = validate_split_merge_artifact_receipt(failed, plan=plan)
        self.assertFalse(result["artifact_realized_on_every_replay"])
        self.assertEqual(result["construction_failure_reason"],
                         "registered_split_merge_artifact_not_realized")

    def test_artifact_receipt_cannot_hide_posthoc_replacement(self):
        plan = artifact("MERGE", 1)
        value = receipt(plan, [(2, 1)])
        value["posthoc_relabel_or_replacement_used"] = True
        value["receipt_sha256"] = sha({
            key: item for key, item in value.items() if key != "receipt_sha256"
        })
        with self.assertRaisesRegex(ValueError, "may not be relabeled"):
            validate_split_merge_artifact_receipt(value, plan=plan)

    def test_split_program_must_bind_the_same_artifact_plan(self):
        graph = memory()
        plan = artifact("SPLIT", 2)
        construction = make_program_construction_plan(
            episode_id="episode:003", family_id="family:001",
            program="SPLIT", prior_memory=graph,
            prior_memory_sha256=graph["graph_hash"],
            precondition_refs={
                "undersegmented_prior_node_version_id": "entity-a@v0",
                "artifact_plan_sha256": plan["artifact_plan_sha256"],
            }, visibility_subject_seal_sha256="a" * 64,
            artifact_plan=plan,
        )
        self.assertEqual(construction["artifact_plan_sha256"],
                         plan["artifact_plan_sha256"])


if __name__ == "__main__":
    unittest.main()
