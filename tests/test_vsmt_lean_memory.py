"""D-224 / S0-01 contract tests for the VSMT-lean entity memory core.

The continue gate for S0-01 is: every one of the five atoms has a positive and
a negative case, an illegal program rolls back the whole frame, the caller's
prior memory is byte-identical after a rollback, and the D-224-G token field
order is fixed by the machine contract.  These tests prove mechanical
semantics only; they say nothing about whether the method works.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt.lean_memory import (  # noqa: E402
    ATOMS,
    CONTRACT_SCHEMA_VERSION,
    ENTITY_STATES,
    ENTITY_TOKEN_FIELDS,
    LeanMemoryError,
    STATE_ALLOWED_ATOMS,
    apply_program,
    empty_memory,
    entity_tokens,
    expand_program,
    frame_delta,
    memory_digest,
    validate_entity_memory_contract,
    validate_memory,
)


CONTRACT_PATH = PROJECT_ROOT / "configs" / "vsmt" / "lean_s0_entity_memory_v2.json"

METHOD_ID = "vsmt.lean.test.v1"
DORMANCY_LIMIT = 2
DEDUP = {
    "period_ticks": 1,
    "descriptor_cosine_min": 0.99,
    "centroid_distance_max_m": 0.15,
    "aabb_iou_min": 0.3,
}


def digest(seed: str) -> str:
    """Deterministic stand-in for a real frame digest."""

    import hashlib

    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def fragment(
    fragment_id: str, *, descriptor: list[float], centroid: list[float],
    pixel_count: int = 400, half: float = 0.1, supported_by: str | None = None,
) -> dict[str, Any]:
    return {
        "fragment_id": fragment_id,
        "descriptor": list(descriptor),
        "centroid_m": list(centroid),
        "aabb_min_m": [value - half for value in centroid],
        "aabb_max_m": [value + half for value in centroid],
        "pixel_count": pixel_count,
        "supported_by": supported_by,
    }


def program(frame_seed: str, operations: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {"frame_digest": digest(frame_seed), "operations": list(operations)}


def commit(
    memory: Mapping[str, Any], frame_seed: str, operations: list[Mapping[str, Any]],
    *, dedup: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return apply_program(
        memory, program(frame_seed, operations), method_id=METHOD_ID,
        dormancy_missed_opportunity_limit=DORMANCY_LIMIT, dedup=dedup,
    )


def only_entity(memory: Mapping[str, Any]) -> dict[str, Any]:
    assert len(memory["entities"]) == 1, memory["entities"]
    return memory["entities"][0]


def born_memory(*, frame_seed: str = "f1") -> tuple[dict[str, Any], str]:
    """One committed BIRTH; returns the memory and the new entity id."""

    memory = commit(
        empty_memory(episode_id="ep-0001"), frame_seed,
        [{"atom": "BIRTH", "fragment": fragment(
            "region:0000", descriptor=[1.0, 0.0], centroid=[0.0, 0.0, 0.0],
        )}],
    )
    return memory, str(only_entity(memory)["entity_id"])


class TestEmptyMemory(unittest.TestCase):
    def test_empty_memory_is_valid_and_sealed(self) -> None:
        memory = empty_memory(episode_id="ep-0001")
        validate_memory(memory)
        self.assertEqual(memory["tick"], 0)
        self.assertEqual(memory["entities"], [])
        self.assertEqual(memory["transaction_log"], [])
        self.assertEqual(memory["memory_digest"], memory_digest(memory))

    def test_tampered_digest_is_rejected(self) -> None:
        """A structurally legal edit that nothing else guards must still fail."""

        memory, _ = born_memory()
        only_entity(memory)["missed_opportunity_count"] = 1
        with self.assertRaises(LeanMemoryError) as caught:
            validate_memory(memory)
        self.assertEqual(str(caught.exception), "memory_digest_mismatch")

    def test_tick_without_a_matching_log_is_rejected(self) -> None:
        memory = empty_memory(episode_id="ep-0001")
        memory["tick"] = 5
        with self.assertRaises(LeanMemoryError) as caught:
            validate_memory(memory)
        self.assertEqual(
            str(caught.exception), "memory_transaction_log_length_mismatch",
        )


class TestBirth(unittest.TestCase):
    def test_birth_creates_one_active_entity_with_one_open_version(self) -> None:
        memory, entity_id = born_memory()
        entity = only_entity(memory)
        self.assertEqual(memory["tick"], 1)
        self.assertEqual(entity["state"], "active")
        self.assertEqual(entity["observation_count"], 1)
        self.assertEqual(len(entity["versions"]), 1)
        self.assertIsNone(entity["versions"][0]["predecessor"])
        self.assertIsNone(entity["versions"][0]["closed_at"])
        self.assertEqual(entity["versions"][0]["opened_at"], 1)
        self.assertEqual(entity["evidence"], [
            {"frame_digest": digest("f1"), "fragment_id": "region:0000", "tick": 1},
        ])
        self.assertTrue(entity_id.startswith("entity:"))

    def test_birth_reusing_one_fragment_twice_is_illegal(self) -> None:
        duplicate = fragment("region:0000", descriptor=[1.0, 0.0], centroid=[0.0, 0.0, 0.0])
        with self.assertRaises(LeanMemoryError) as caught:
            commit(
                empty_memory(episode_id="ep-0001"), "f1",
                [
                    {"atom": "BIRTH", "fragment": duplicate},
                    {"atom": "BIRTH", "fragment": duplicate},
                ],
            )
        self.assertEqual(str(caught.exception), "fragment_used_twice_in_frame")

    def test_birth_with_mismatched_descriptor_dimension_is_illegal(self) -> None:
        memory, _ = born_memory()
        with self.assertRaises(LeanMemoryError) as caught:
            commit(memory, "f2", [{"atom": "BIRTH", "fragment": fragment(
                "region:0001", descriptor=[1.0, 0.0, 0.0], centroid=[3.0, 0.0, 0.0],
            )}])
        self.assertEqual(
            str(caught.exception), "fragment_descriptor_dimension_mismatch",
        )


class TestBind(unittest.TestCase):
    def test_bind_appends_evidence_and_opens_a_successor_version(self) -> None:
        memory, entity_id = born_memory()
        updated = commit(memory, "f2", [{
            "atom": "BIND",
            "entity_id": entity_id,
            "fragment": fragment(
                "region:0001", descriptor=[1.0, 0.0], centroid=[0.05, 0.0, 0.0],
                pixel_count=900,
            ),
        }])
        entity = only_entity(updated)
        self.assertEqual(entity["state"], "active")
        self.assertEqual(entity["observation_count"], 2)
        self.assertEqual(entity["descriptor_count"], 2)
        self.assertEqual(entity["best_view_pixel_count"], 900)
        self.assertEqual(entity["last_seen_tick"], 2)
        self.assertEqual(len(entity["versions"]), 2)
        self.assertEqual(entity["versions"][0]["closed_at"], 2)
        self.assertEqual(
            entity["versions"][1]["predecessor"], entity["versions"][0]["version_id"],
        )
        self.assertIsNone(entity["versions"][1]["closed_at"])
        self.assertEqual(len(entity["evidence"]), 2)

    def test_bind_to_retracted_entity_is_illegal(self) -> None:
        memory, entity_id = born_memory()
        retracted = commit(memory, "f2", [{"atom": "RETRACT", "entity_id": entity_id}])
        with self.assertRaises(LeanMemoryError) as caught:
            commit(retracted, "f3", [{
                "atom": "BIND",
                "entity_id": entity_id,
                "fragment": fragment(
                    "region:0002", descriptor=[1.0, 0.0], centroid=[0.0, 0.0, 0.0],
                ),
            }])
        self.assertEqual(
            str(caught.exception), "atom_bind_illegal_for_state_retracted",
        )

    def test_bind_to_unknown_entity_is_illegal(self) -> None:
        memory, _ = born_memory()
        with self.assertRaises(LeanMemoryError) as caught:
            commit(memory, "f2", [{
                "atom": "BIND",
                "entity_id": "entity:0000000000000000",
                "fragment": fragment(
                    "region:0002", descriptor=[1.0, 0.0], centroid=[0.0, 0.0, 0.0],
                ),
            }])
        self.assertEqual(str(caught.exception), "operation_target_entity_unknown")


class TestNoopAndDormancy(unittest.TestCase):
    def test_noop_increments_the_missed_counter_without_versioning(self) -> None:
        memory, entity_id = born_memory()
        updated = commit(memory, "f2", [{
            "atom": "NOOP",
            "entity_id": entity_id,
            "decision_basis": {"should_be_visible": True, "existence_prob": 0.1},
        }])
        entity = only_entity(updated)
        self.assertEqual(entity["missed_opportunity_count"], 1)
        self.assertEqual(entity["state"], "active")
        self.assertEqual(len(entity["versions"]), 1)
        logged = updated["transaction_log"][-1]["operations"][0]
        self.assertEqual(logged["decision_basis"]["existence_prob"], 0.1)

    def test_dormancy_fires_at_the_limit_and_a_match_resets_it(self) -> None:
        memory, entity_id = born_memory()
        first = commit(memory, "f2", [{"atom": "NOOP", "entity_id": entity_id}])
        second = commit(first, "f3", [{"atom": "NOOP", "entity_id": entity_id}])
        entity = only_entity(second)
        self.assertEqual(entity["state"], "dormant")
        self.assertEqual(entity["missed_opportunity_count"], DORMANCY_LIMIT)
        self.assertEqual(len(entity["versions"]), 2)
        self.assertEqual(entity["versions"][-1]["state"], "dormant")
        self.assertEqual(
            second["transaction_log"][-1]["post_maintenance"]["dormancy"],
            [{"entity_id": entity_id, "missed_opportunity_count": DORMANCY_LIMIT}],
        )

        revived = commit(second, "f4", [{
            "atom": "REACTIVATE",
            "entity_id": entity_id,
            "fragment": fragment(
                "region:0003", descriptor=[1.0, 0.0], centroid=[0.0, 0.0, 0.0],
            ),
        }])
        self.assertEqual(only_entity(revived)["missed_opportunity_count"], 0)

    def test_noop_on_a_retracted_entity_is_illegal(self) -> None:
        memory, entity_id = born_memory()
        retracted = commit(memory, "f2", [{"atom": "RETRACT", "entity_id": entity_id}])
        with self.assertRaises(LeanMemoryError) as caught:
            commit(retracted, "f3", [{"atom": "NOOP", "entity_id": entity_id}])
        self.assertEqual(
            str(caught.exception), "atom_noop_illegal_for_state_retracted",
        )

    def test_dormancy_limit_must_be_supplied_and_positive(self) -> None:
        memory, entity_id = born_memory()
        with self.assertRaises(LeanMemoryError) as caught:
            apply_program(
                memory, program("f2", [{"atom": "NOOP", "entity_id": entity_id}]),
                method_id=METHOD_ID, dormancy_missed_opportunity_limit=0,
            )
        self.assertEqual(str(caught.exception), "dormancy_limit_invalid")


class TestRetract(unittest.TestCase):
    def test_retract_closes_the_version_and_keeps_evidence(self) -> None:
        memory, entity_id = born_memory()
        updated = commit(memory, "f2", [{
            "atom": "RETRACT",
            "entity_id": entity_id,
            "decision_basis": {"free_space_coverage": 0.94},
        }])
        entity = only_entity(updated)
        self.assertEqual(entity["state"], "retracted")
        self.assertEqual(len(entity["evidence"]), 1)
        self.assertEqual(len(entity["versions"]), 2)
        self.assertEqual(entity["versions"][0]["closed_at"], 2)
        self.assertEqual(entity["versions"][-1]["state"], "retracted")
        self.assertIsNone(entity["versions"][-1]["closed_at"])

    def test_retract_twice_is_illegal(self) -> None:
        memory, entity_id = born_memory()
        retracted = commit(memory, "f2", [{"atom": "RETRACT", "entity_id": entity_id}])
        with self.assertRaises(LeanMemoryError) as caught:
            commit(retracted, "f3", [{"atom": "RETRACT", "entity_id": entity_id}])
        self.assertEqual(
            str(caught.exception), "atom_retract_illegal_for_state_retracted",
        )


class TestReactivate(unittest.TestCase):
    def test_reactivate_restores_the_same_identity(self) -> None:
        memory, entity_id = born_memory()
        retracted = commit(memory, "f2", [{"atom": "RETRACT", "entity_id": entity_id}])
        revived = commit(retracted, "f3", [{
            "atom": "REACTIVATE",
            "entity_id": entity_id,
            "fragment": fragment(
                "region:0004", descriptor=[1.0, 0.0], centroid=[4.0, 0.0, 1.0],
            ),
        }])
        entity = only_entity(revived)
        self.assertEqual(entity["entity_id"], entity_id)
        self.assertEqual(entity["state"], "active")
        self.assertEqual(entity["centroid_m"], [4.0, 0.0, 1.0])
        self.assertEqual(entity["observation_count"], 2)
        self.assertEqual(len(entity["versions"]), 3)
        self.assertEqual(len(entity["evidence"]), 2)

    def test_reactivate_of_an_active_entity_is_illegal(self) -> None:
        memory, entity_id = born_memory()
        with self.assertRaises(LeanMemoryError) as caught:
            commit(memory, "f2", [{
                "atom": "REACTIVATE",
                "entity_id": entity_id,
                "fragment": fragment(
                    "region:0005", descriptor=[1.0, 0.0], centroid=[0.0, 0.0, 0.0],
                ),
            }])
        self.assertEqual(
            str(caught.exception), "atom_reactivate_illegal_for_state_active",
        )


class TestReplaceComposite(unittest.TestCase):
    def test_replace_expands_to_retract_then_birth(self) -> None:
        expanded = expand_program(program("f2", [{
            "atom": "REPLACE",
            "retract_entity_id": "entity:abc",
            "fragment": fragment(
                "region:0006", descriptor=[0.0, 1.0], centroid=[1.0, 0.0, 0.0],
            ),
        }]))
        self.assertEqual(
            [item["atom"] for item in expanded["operations"]], ["RETRACT", "BIRTH"],
        )
        self.assertEqual(
            {item["composite"] for item in expanded["operations"]}, {"REPLACE#0"},
        )

    def test_replace_retracts_the_old_identity_and_births_a_new_one(self) -> None:
        memory, entity_id = born_memory()
        updated = commit(memory, "f2", [{
            "atom": "REPLACE",
            "retract_entity_id": entity_id,
            "fragment": fragment(
                "region:0006", descriptor=[0.0, 1.0], centroid=[0.0, 0.0, 0.0],
            ),
        }])
        self.assertEqual(len(updated["entities"]), 2)
        states = {
            str(entity["entity_id"]): entity["state"]
            for entity in updated["entities"]
        }
        self.assertEqual(states[entity_id], "retracted")
        new_ids = [item for item in states if item != entity_id]
        self.assertEqual(len(new_ids), 1)
        self.assertEqual(states[new_ids[0]], "active")
        atoms = [item["atom"] for item in updated["transaction_log"][-1]["operations"]]
        self.assertEqual(atoms, ["RETRACT", "BIRTH"])

    def test_replace_of_an_already_retracted_entity_fails_whole_frame(self) -> None:
        memory, entity_id = born_memory()
        retracted = commit(memory, "f2", [{"atom": "RETRACT", "entity_id": entity_id}])
        before = canonical_json(retracted)
        with self.assertRaises(LeanMemoryError):
            commit(retracted, "f3", [{
                "atom": "REPLACE",
                "retract_entity_id": entity_id,
                "fragment": fragment(
                    "region:0007", descriptor=[0.0, 1.0], centroid=[0.0, 0.0, 0.0],
                ),
            }])
        self.assertEqual(canonical_json(retracted), before)
        self.assertEqual(len(retracted["entities"]), 1)


class TestAtomicity(unittest.TestCase):
    def test_illegal_second_operation_rolls_back_the_whole_frame(self) -> None:
        memory, entity_id = born_memory()
        before = canonical_json(memory)
        with self.assertRaises(LeanMemoryError) as caught:
            commit(memory, "f2", [
                {"atom": "BIND", "entity_id": entity_id, "fragment": fragment(
                    "region:0008", descriptor=[1.0, 0.0], centroid=[0.0, 0.0, 0.0],
                )},
                {"atom": "RETRACT", "entity_id": entity_id},
            ])
        self.assertEqual(str(caught.exception), "entity_used_twice_in_frame")
        self.assertEqual(canonical_json(memory), before)
        self.assertEqual(memory["tick"], 1)
        self.assertEqual(len(only_entity(memory)["versions"]), 1)

    def test_empty_program_advances_the_tick_and_nothing_else(self) -> None:
        memory, _ = born_memory()
        entity_before = canonical_json(only_entity(memory))
        updated = commit(memory, "f2", [])
        self.assertEqual(updated["tick"], 2)
        self.assertEqual(canonical_json(only_entity(updated)), entity_before)
        self.assertEqual(updated["transaction_log"][-1]["operations"], [])

    def test_unknown_atom_is_rejected(self) -> None:
        memory, entity_id = born_memory()
        with self.assertRaises(LeanMemoryError) as caught:
            commit(memory, "f2", [{"atom": "SPLIT", "entity_id": entity_id}])
        self.assertEqual(str(caught.exception), "operation_atom_unknown")

    def test_two_fragments_cannot_bind_to_the_same_entity(self) -> None:
        memory, entity_id = born_memory()
        with self.assertRaises(LeanMemoryError) as caught:
            commit(memory, "f2", [
                {"atom": "BIND", "entity_id": entity_id, "fragment": fragment(
                    "region:0009", descriptor=[1.0, 0.0], centroid=[0.0, 0.0, 0.0],
                )},
                {"atom": "BIND", "entity_id": entity_id, "fragment": fragment(
                    "region:0010", descriptor=[1.0, 0.0], centroid=[0.1, 0.0, 0.0],
                )},
            ])
        self.assertEqual(str(caught.exception), "entity_used_twice_in_frame")


class TestSharedDedup(unittest.TestCase):
    def _two_near_duplicates(self) -> dict[str, Any]:
        return commit(
            empty_memory(episode_id="ep-0002"), "f1",
            [
                {"atom": "BIRTH", "fragment": fragment(
                    "region:0000", descriptor=[1.0, 0.0], centroid=[0.0, 0.0, 0.0],
                )},
                {"atom": "BIRTH", "fragment": fragment(
                    "region:0001", descriptor=[1.0, 0.001], centroid=[0.05, 0.0, 0.0],
                )},
            ],
        )

    def test_without_a_policy_no_merge_happens(self) -> None:
        memory = self._two_near_duplicates()
        self.assertEqual(len(memory["entities"]), 2)
        self.assertEqual(memory["transaction_log"][-1]["post_maintenance"]["dedup"], [])

    def test_duplicates_fold_into_the_earlier_identity(self) -> None:
        base = self._two_near_duplicates()
        ids_before = sorted(str(item["entity_id"]) for item in base["entities"])
        merged = commit(base, "f2", [], dedup=DEDUP)
        entity = only_entity(merged)
        self.assertEqual(entity["entity_id"], ids_before[0])
        self.assertEqual(entity["canonical_of"], [ids_before[1]])
        self.assertEqual(entity["observation_count"], 2)
        self.assertEqual(len(entity["evidence"]), 2)
        changes = merged["transaction_log"][-1]["post_maintenance"]["dedup"]
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["canonical_entity_id"], ids_before[0])
        self.assertEqual(changes[0]["folded_entity_id"], ids_before[1])

    def test_far_apart_entities_do_not_merge(self) -> None:
        base = commit(
            empty_memory(episode_id="ep-0003"), "f1",
            [
                {"atom": "BIRTH", "fragment": fragment(
                    "region:0000", descriptor=[1.0, 0.0], centroid=[0.0, 0.0, 0.0],
                )},
                {"atom": "BIRTH", "fragment": fragment(
                    "region:0001", descriptor=[1.0, 0.0], centroid=[9.0, 0.0, 0.0],
                )},
            ],
        )
        merged = commit(base, "f2", [], dedup=DEDUP)
        self.assertEqual(len(merged["entities"]), 2)

    def test_dedup_policy_requires_every_value(self) -> None:
        base = self._two_near_duplicates()
        partial = {key: value for key, value in DEDUP.items() if key != "aabb_iou_min"}
        with self.assertRaises(LeanMemoryError) as caught:
            commit(base, "f2", [], dedup=partial)
        self.assertEqual(str(caught.exception), "dedup_fields_invalid")

    def test_dedup_runs_only_on_its_period(self) -> None:
        base = self._two_near_duplicates()
        policy = dict(DEDUP, period_ticks=100)
        merged = commit(base, "f2", [], dedup=policy)
        self.assertEqual(len(merged["entities"]), 2)


class TestEntityTokens(unittest.TestCase):
    def test_token_field_order_is_frozen(self) -> None:
        memory, _ = born_memory()
        tokens = entity_tokens(memory)
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tuple(tokens[0].keys()), ENTITY_TOKEN_FIELDS)
        self.assertEqual(tokens[0]["state_one_hot"], [1, 0, 0])
        self.assertEqual(tokens[0]["age_ticks"], 0)
        self.assertEqual(tokens[0]["version_count"], 1)
        self.assertEqual(tokens[0]["supported_by_present"], False)
        for axis in tokens[0]["extent_m"]:
            self.assertAlmostEqual(axis, 0.2)

    def test_retracted_entities_are_excluded_unless_requested(self) -> None:
        memory, entity_id = born_memory()
        retracted = commit(memory, "f2", [{"atom": "RETRACT", "entity_id": entity_id}])
        self.assertEqual(entity_tokens(retracted), [])
        included = entity_tokens(retracted, include_retracted=True)
        self.assertEqual(len(included), 1)
        self.assertEqual(included[0]["state_one_hot"], [0, 0, 1])

    def test_tokens_carry_no_private_or_scene_identifier(self) -> None:
        memory, _ = born_memory()
        text = canonical_json(entity_tokens(memory))
        for forbidden in ("house", "scenario", "instance", "teacher", "episode"):
            self.assertNotIn(forbidden, text)


class TestFrameDelta(unittest.TestCase):
    def test_delta_lists_only_changed_entities(self) -> None:
        memory, first_id = born_memory()
        updated = commit(memory, "f2", [{"atom": "BIRTH", "fragment": fragment(
            "region:0011", descriptor=[0.0, 1.0], centroid=[5.0, 0.0, 0.0],
        )}])
        delta = frame_delta(updated)
        self.assertEqual(delta["tick"], 2)
        self.assertEqual(len(delta["changed_entities"]), 1)
        self.assertNotIn(first_id, delta["changed_entities"])
        self.assertEqual(delta["unchanged_entity_count"], 1)
        self.assertEqual(delta["folded_entities"], [])

    def test_noop_is_not_a_change_but_dormancy_is(self) -> None:
        memory, entity_id = born_memory()
        first = commit(memory, "f2", [{"atom": "NOOP", "entity_id": entity_id}])
        self.assertEqual(frame_delta(first)["changed_entities"], {})
        second = commit(first, "f3", [{"atom": "NOOP", "entity_id": entity_id}])
        self.assertEqual(
            frame_delta(second)["changed_entities"], {entity_id: ["DORMANT"]},
        )

    def test_delta_for_an_unknown_tick_is_rejected(self) -> None:
        memory, _ = born_memory()
        with self.assertRaises(LeanMemoryError) as caught:
            frame_delta(memory, tick=99)
        self.assertEqual(str(caught.exception), "frame_delta_tick_not_found")


class TestVersionOpenedBy(unittest.TestCase):
    """D-224-X ruling X6: every version says why it was opened."""

    def test_each_atom_and_maintenance_step_stamps_its_opened_by(self) -> None:
        from vsmt.lean_memory import VERSION_OPENED_BY, VERSION_OPENED_BY_STATE

        self.assertEqual(VERSION_OPENED_BY, ("birth", "bind", "reactivate", "retract", "dormant", "dedup"))
        memory, entity_id = born_memory()
        self.assertEqual([v["opened_by"] for v in only_entity(memory)["versions"]], ["birth"])
        bound = commit(memory, "f2", [{"atom": "BIND", "entity_id": entity_id, "fragment": fragment(
            "region:0001", descriptor=[1.0, 0.0], centroid=[0.0, 0.0, 0.0],
        )}])
        self.assertEqual([v["opened_by"] for v in only_entity(bound)["versions"]], ["birth", "bind"])
        retracted = commit(bound, "f3", [{"atom": "RETRACT", "entity_id": entity_id}])
        self.assertEqual(only_entity(retracted)["versions"][-1]["opened_by"], "retract")
        self.assertEqual(only_entity(retracted)["versions"][-1]["state"], "retracted")
        revived = commit(retracted, "f4", [{"atom": "REACTIVATE", "entity_id": entity_id, "fragment": fragment(
            "region:0002", descriptor=[1.0, 0.0], centroid=[2.0, 0.0, 0.0],
        )}])
        self.assertEqual(only_entity(revived)["versions"][-1]["opened_by"], "reactivate")
        dormant = revived
        for seed in ("f5", "f6"):
            dormant = commit(dormant, seed, [{"atom": "NOOP", "entity_id": entity_id}])
        self.assertEqual(only_entity(dormant)["state"], "dormant")
        self.assertEqual(only_entity(dormant)["versions"][-1]["opened_by"], "dormant")
        for version in only_entity(dormant)["versions"]:
            self.assertEqual(version["state"], VERSION_OPENED_BY_STATE[version["opened_by"]])

    def test_dedup_opens_a_dedup_version_and_archives_the_folded_id(self) -> None:
        base = commit(
            empty_memory(episode_id="ep-0003"), "f1",
            [
                {"atom": "BIRTH", "fragment": fragment("region:0000", descriptor=[1.0, 0.0], centroid=[0.0, 0.0, 0.0])},
                {"atom": "BIRTH", "fragment": fragment("region:0001", descriptor=[1.0, 0.001], centroid=[0.05, 0.0, 0.0])},
            ],
        )
        folded_id = sorted(str(item["entity_id"]) for item in base["entities"])[1]
        merged = commit(base, "f2", [], dedup=DEDUP)
        entity = only_entity(merged)
        self.assertEqual(entity["versions"][-1]["opened_by"], "dedup")
        self.assertEqual(entity["canonical_of"], [folded_id])
        self.assertEqual(len(entity["evidence"]), 2)
        self.assertEqual(merged["transaction_log"][-1]["post_maintenance"]["dedup"][0]["folded_entity_id"], folded_id)

    def test_a_version_whose_opened_by_disagrees_with_its_state_is_rejected(self) -> None:
        memory, entity_id = born_memory()
        tampered = json.loads(json.dumps(memory))
        tampered["entities"][0]["versions"][0]["opened_by"] = "retract"
        with self.assertRaises(LeanMemoryError) as caught:
            validate_memory(tampered, verify_digest=False)
        self.assertEqual(str(caught.exception), "version_state_disagrees_with_opened_by")
        tampered = json.loads(json.dumps(memory))
        tampered["entities"][0]["versions"][0]["opened_by"] = "bind"
        with self.assertRaises(LeanMemoryError) as caught:
            validate_memory(tampered, verify_digest=False)
        self.assertEqual(str(caught.exception), "entity_first_version_not_birth")
        tampered = json.loads(json.dumps(memory))
        del tampered["entities"][0]["versions"][0]["opened_by"]
        with self.assertRaises(LeanMemoryError) as caught:
            validate_memory(tampered, verify_digest=False)
        self.assertEqual(str(caught.exception), "version_fields_invalid")


class TestMachineContract(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_the_v2_claims_are_bound(self) -> None:
        self.assertEqual(self.contract["schema_version"], "vsmt-lean-s0-entity-memory-v2")
        self.assertTrue(self.contract["supersedes_contract"]["v1_bytes_frozen"])
        for path, code in (
            (("version_record", "opened_by_values"), "contract_version_opened_by_values_mismatch"),
            (("shared_dedup", "folded_record_is_archived_into_canonical_of_not_deleted"), "contract_dedup_fold_semantics_weakened"),
            (("state_machine", "physical_deletion_allowed"), "contract_physical_deletion_claim_weakened"),
        ):
            broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
            node = broken
            for part in path[:-1]:
                node = node[part]
            value = node[path[-1]]
            node[path[-1]] = (not value) if isinstance(value, bool) else list(value)[:-1]
            with self.assertRaises(LeanMemoryError) as caught:
                validate_entity_memory_contract(broken)
            self.assertEqual(str(caught.exception), code)
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["version_record"]["fields"].remove("opened_by")
        with self.assertRaises(LeanMemoryError) as caught:
            validate_entity_memory_contract(broken)
        self.assertEqual(str(caught.exception), "contract_version_record_lacks_opened_by")

    def test_contract_agrees_with_the_implementation(self) -> None:
        validate_entity_memory_contract(self.contract)
        self.assertEqual(
            self.contract["schema_version"], CONTRACT_SCHEMA_VERSION,
        )
        self.assertEqual(tuple(self.contract["atoms"]), ATOMS)
        self.assertEqual(tuple(self.contract["entity_states"]), ENTITY_STATES)
        self.assertEqual(
            tuple(self.contract["entity_token_schema"]["field_order"]),
            ENTITY_TOKEN_FIELDS,
        )

    def test_contract_state_machine_matches_the_executor(self) -> None:
        allowed = self.contract["state_machine"]["allowed_atoms_by_state"]
        for state, atoms in STATE_ALLOWED_ATOMS.items():
            self.assertEqual(frozenset(allowed[state]), atoms)

    def test_a_sixth_atom_in_the_contract_is_rejected(self) -> None:
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["atoms"] = list(broken["atoms"]) + ["SPLIT"]
        with self.assertRaises(LeanMemoryError) as caught:
            validate_entity_memory_contract(broken)
        self.assertEqual(str(caught.exception), "contract_atoms_mismatch")

    def test_policy_values_must_still_be_null(self) -> None:
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["shared_dedup"]["aabb_iou_min"] = 0.3
        with self.assertRaises(LeanMemoryError) as caught:
            validate_entity_memory_contract(broken)
        self.assertIn("must_be_null_before_freeze", str(caught.exception))

    def test_every_authorization_bit_is_false(self) -> None:
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["authorization"]["model_training"] = True
        with self.assertRaises(LeanMemoryError) as caught:
            validate_entity_memory_contract(broken)
        self.assertEqual(
            str(caught.exception), "contract_authorization_must_be_all_false",
        )

    def test_contract_excludes_the_retired_first_paper_machinery(self) -> None:
        excluded = set(self.contract["not_in_first_paper"])
        for name in ("SPLIT", "RELINK", "place_node", "relation_edge", "type_gate"):
            self.assertIn(name, excluded)


class TestSequenceIntegrity(unittest.TestCase):
    def test_a_move_and_revisit_sequence_keeps_one_identity(self) -> None:
        """BIRTH, two misses (dormant), then REACTIVATE at a new location."""

        memory, entity_id = born_memory()
        memory = commit(memory, "f2", [{"atom": "NOOP", "entity_id": entity_id}])
        memory = commit(memory, "f3", [{"atom": "NOOP", "entity_id": entity_id}])
        self.assertEqual(only_entity(memory)["state"], "dormant")
        memory = commit(memory, "f4", [{
            "atom": "REACTIVATE",
            "entity_id": entity_id,
            "fragment": fragment(
                "region:0012", descriptor=[1.0, 0.0], centroid=[6.0, 0.0, 2.0],
            ),
        }])
        entity = only_entity(memory)
        self.assertEqual(entity["entity_id"], entity_id)
        self.assertEqual(entity["state"], "active")
        self.assertEqual(memory["tick"], 4)
        self.assertEqual(len(memory["transaction_log"]), 4)
        self.assertEqual([record["tick"] for record in memory["transaction_log"]],
                         [1, 2, 3, 4])
        validate_memory(memory)

    def test_history_is_never_physically_deleted(self) -> None:
        memory, entity_id = born_memory()
        for index, seed in enumerate(("f2", "f3"), start=2):
            memory = commit(memory, seed, [{
                "atom": "BIND",
                "entity_id": entity_id,
                "fragment": fragment(
                    f"region:{index:04d}", descriptor=[1.0, 0.0],
                    centroid=[0.01 * index, 0.0, 0.0],
                ),
            }])
        memory = commit(memory, "f4", [{"atom": "RETRACT", "entity_id": entity_id}])
        entity = only_entity(memory)
        self.assertEqual(len(entity["versions"]), 4)
        self.assertEqual(len(entity["evidence"]), 3)
        closed = [item for item in entity["versions"] if item["closed_at"] is not None]
        self.assertEqual(len(closed), 3)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


class TestEntityBoxRule(unittest.TestCase):
    """D-224-S1 ruling 56 continued: the box follows the latest observed frame, never accumulates across frames."""

    def test_a_bind_in_a_later_frame_replaces_the_box(self) -> None:
        memory, entity_id = born_memory()
        far = fragment("region:0001", descriptor=[1.0, 0.0], centroid=[2.0, 0.0, 0.0], half=0.3)
        entity = only_entity(commit(memory, "f2", [{"atom": "BIND", "entity_id": entity_id, "fragment": far}]))
        self.assertEqual(entity["aabb_min_m"], far["aabb_min_m"])
        self.assertEqual(entity["aabb_max_m"], far["aabb_max_m"])

    def test_same_frame_duplicates_merge_into_the_union(self) -> None:
        a = fragment("region:0000", descriptor=[1.0, 0.0], centroid=[0.0, 0.0, 0.0])
        b = fragment("region:0001", descriptor=[1.0, 0.001], centroid=[0.05, 0.0, 0.0])
        base = commit(empty_memory(episode_id="ep-0004"), "f1", [{"atom": "BIRTH", "fragment": a}, {"atom": "BIRTH", "fragment": b}])
        entity = only_entity(commit(base, "f2", [], dedup=DEDUP))
        self.assertEqual(entity["aabb_min_m"], [min(x, y) for x, y in zip(a["aabb_min_m"], b["aabb_min_m"])])
        self.assertEqual(entity["aabb_max_m"], [max(x, y) for x, y in zip(a["aabb_max_m"], b["aabb_max_m"])])

    def test_a_merge_across_frames_keeps_the_later_box(self) -> None:
        a = fragment("region:0000", descriptor=[1.0, 0.0], centroid=[0.0, 0.0, 0.0])
        base = commit(empty_memory(episode_id="ep-0005"), "f1", [{"atom": "BIRTH", "fragment": a}])
        b = fragment("region:0001", descriptor=[1.0, 0.001], centroid=[0.05, 0.0, 0.0], half=0.12)
        later = commit(base, "f2", [{"atom": "BIRTH", "fragment": b}])
        entity = only_entity(commit(later, "f3", [], dedup=DEDUP))
        self.assertEqual(entity["aabb_min_m"], b["aabb_min_m"])
        self.assertEqual(entity["aabb_max_m"], b["aabb_max_m"])

    def test_the_contract_binds_the_box_rule(self) -> None:
        from vsmt.lean_memory import ENTITY_BOX_RULE

        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(contract["entity_box"]["rule"], ENTITY_BOX_RULE)
        validate_entity_memory_contract(contract)
        contract["entity_box"]["cross_frame_accumulation"] = True
        with self.assertRaises(LeanMemoryError) as caught:
            validate_entity_memory_contract(contract)
        self.assertEqual(str(caught.exception), "contract_entity_box_rule_mismatch")
