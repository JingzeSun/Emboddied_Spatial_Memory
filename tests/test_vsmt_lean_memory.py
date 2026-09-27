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
    DORMANCY_MISSED_OPPORTUNITY_LIMIT,
    SHARED_DEDUP,
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
        # a sealed memory is never changed in place (LOG-254); a tampered copy of it must fail
        tampered = json.loads(json.dumps(memory))
        only_entity(tampered)["missed_opportunity_count"] = 1
        with self.assertRaises(LeanMemoryError) as caught:
            validate_memory(tampered)
        self.assertEqual(str(caught.exception), "memory_digest_mismatch")

    def test_tick_without_a_matching_log_is_rejected(self) -> None:
        memory = empty_memory(episode_id="ep-0001")
        memory["tick"] = 5
        with self.assertRaises(LeanMemoryError) as caught:
            validate_memory(memory)
        self.assertEqual(
            str(caught.exception), "memory_transaction_log_length_mismatch",
        )


class TestValidationCache(unittest.TestCase):
    """Engineering (LOG-254): a memory object validated once is not walked again while its digest stands."""

    def test_a_cache_entry_names_its_object_so_an_address_reuse_cannot_skip_the_digest_check(self) -> None:
        """Server suite at 4e8028d: a freed memory's id came back on a twin with the same digest and a tamper slipped through."""

        import vsmt.lean_memory as lm

        first, _ = born_memory()
        validate_memory(first)
        key = lm._validated_key(first)
        self.assertIs(lm._VALIDATED_MEMORIES[key], first)  # the entry keeps the object alive, so its id stays unique
        twin = json.loads(json.dumps(born_memory()[0]))  # same digest, tick and entity count as ``first``; a different object
        self.assertEqual(twin["memory_digest"], first["memory_digest"])
        only_entity(twin)["missed_opportunity_count"] = 1
        # mimic an address reuse: an entry under the twin's key that names another object must not count as a hit
        lm._VALIDATED_MEMORIES[lm._validated_key(twin)] = first
        with self.assertRaises(LeanMemoryError) as caught:
            validate_memory(twin)
        self.assertEqual(str(caught.exception), "memory_digest_mismatch")
        validate_memory(born_memory()[0])  # a store trims the cache back to its limit
        self.assertLessEqual(len(lm._VALIDATED_MEMORIES), lm._VALIDATED_MEMORIES_LIMIT)

    def test_the_same_sealed_object_validates_to_an_equal_copy_and_a_tampered_copy_is_refused(self) -> None:
        memory = empty_memory(episode_id="ep-cache")
        first = validate_memory(memory)
        second = validate_memory(memory)  # cache hit: same object, same digest
        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        self.assertIsNot(second["entities"], memory["entities"])
        tampered = json.loads(json.dumps(memory))
        tampered["tick"] = 5  # a different object: validated in full and refused
        with self.assertRaises(LeanMemoryError):
            validate_memory(tampered)
        resealed = json.loads(json.dumps(memory))
        resealed["memory_digest"] = "0" * 64
        with self.assertRaises(LeanMemoryError) as caught:
            validate_memory(resealed)
        self.assertEqual(str(caught.exception), "memory_digest_mismatch")


class TestIncrementalDigestAndCopyOnWrite(unittest.TestCase):
    """2026-09-27: per-record cached serialisation, per-record validation memo and a copy-on-write executor."""

    def _sequence(self) -> list[dict[str, Any]]:
        a = fragment("region:0000", descriptor=[1.0, 0.0], centroid=[0.0, 0.0, 0.0])
        b = fragment("region:0001", descriptor=[0.0, 1.0], centroid=[3.0, 0.0, 0.0])
        memories = [commit(empty_memory(episode_id="ep-cow"), "f1", [{"atom": "BIRTH", "fragment": a}, {"atom": "BIRTH", "fragment": b}])]
        by_place = {e["centroid_m"][0]: str(e["entity_id"]) for e in memories[-1]["entities"]}
        ids = [by_place[0.0], by_place[3.0]]  # ids[0] is a (at the origin), ids[1] is b
        steps = [
            ("f2", [{"atom": "BIND", "entity_id": ids[0], "fragment": fragment("region:0002", descriptor=[1.0, 0.0], centroid=[0.1, 0.0, 0.0])},
                    {"atom": "NOOP", "entity_id": ids[1]}], None),
            ("f3", [{"atom": "NOOP", "entity_id": ids[1]}], None),  # ids[1] goes dormant (limit 2)
            ("f4", [{"atom": "REACTIVATE", "entity_id": ids[1], "fragment": fragment("region:0004", descriptor=[0.0, 1.0], centroid=[3.0, 0.1, 0.0])},
                    {"atom": "BIRTH", "fragment": fragment("region:0005", descriptor=[1.0, 0.001], centroid=[0.12, 0.0, 0.0])}], None),
            ("f5", [], DEDUP),  # the fresh twin of ids[0] folds
            ("f6", [{"atom": "RETRACT", "entity_id": ids[1]}], DEDUP),
        ]
        for seed, ops, dedup in steps:
            memories.append(commit(memories[-1], seed, ops, dedup=dedup))
        return memories

    def test_the_executor_never_changes_the_memory_it_was_given(self) -> None:
        from vsmt.lean_memory import memory_digest_from_scratch

        memories = self._sequence()
        for memory in memories:  # every earlier memory still matches its own digest, serialised in one piece
            self.assertEqual(memory_digest_from_scratch(memory), memory["memory_digest"])
        self.assertEqual(len(memories[-1]["transaction_log"]), 6)
        folds = memories[4]["transaction_log"][-1]["post_maintenance"]["dedup"]
        self.assertEqual(len(folds), 1)  # a and its fresh twin fold on the first dedup tick
        a_id = {e["centroid_m"][0]: str(e["entity_id"]) for e in memories[0]["entities"]}[0.0]
        self.assertIn(a_id, (folds[0]["canonical_entity_id"], folds[0]["folded_entity_id"]))

    def test_the_assembled_serialisation_equals_the_one_piece_serialisation(self) -> None:
        import vsmt.lean_memory as lm

        for memory in self._sequence():
            payload = {key: value for key, value in memory.items() if key != "memory_digest"}
            self.assertEqual(lm._canonical_payload(memory), lm.canonical_json(payload))
            copy = json.loads(json.dumps(memory))  # no cached part at all
            self.assertEqual(lm._canonical_payload(copy), lm.canonical_json(payload))

    def test_the_same_sequence_on_copies_gives_the_same_digests(self) -> None:
        first = [m["memory_digest"] for m in self._sequence()]
        import vsmt.lean_memory as lm

        lm._PART_JSON.clear()
        lm._ITEM_JSON.clear()
        lm._VALIDATED_PARTS.clear()
        lm._VALIDATED_ITEMS.clear()
        lm._VALIDATED_MEMORIES.clear()
        self.assertEqual([m["memory_digest"] for m in self._sequence()], first)

    def test_a_changed_entity_shares_its_closed_versions_and_evidence_and_leaves_the_old_record_open(self) -> None:
        memories = self._sequence()
        a_id = {e["centroid_m"][0]: str(e["entity_id"]) for e in memories[0]["entities"]}[0.0]
        before = next(e for e in memories[0]["entities"] if e["entity_id"] == a_id)
        after = next(e for e in memories[1]["entities"] if e["entity_id"] == a_id)  # BIND at f2
        self.assertIsNot(before, after)
        self.assertIs(after["evidence"][0], before["evidence"][0])  # evidence items are shared, never changed
        self.assertIsNone(before["versions"][-1]["closed_at"])  # the old memory's open version stays open
        self.assertEqual(after["versions"][0]["closed_at"], 2)
        self.assertEqual(len(before["versions"]), 1)
        self.assertEqual(len(before["evidence"]), 1)

    def test_the_entity_serialisation_from_item_parts_equals_the_one_piece_string(self) -> None:
        import vsmt.lean_memory as lm

        for memory in self._sequence():
            for entity in memory["entities"]:
                self.assertEqual(lm._entity_canonical_json(entity, lm.canonical_json), lm.canonical_json(entity))

    def test_dedup_copying_only_survivors_equals_copying_every_candidate(self) -> None:
        """Three near-duplicates fold on one tick; the survivor of the first pair is changed again by the second."""

        import vsmt.lean_memory as lm

        def build() -> dict[str, Any]:
            memory = commit(empty_memory(episode_id="ep-dd"), "f1", [
                {"atom": "BIRTH", "fragment": fragment(f"region:000{i}", descriptor=[1.0, 0.001 * i], centroid=[0.02 * i, 0.0, 0.0])}
                for i in range(3)])
            return commit(memory, "f2", [], dedup=DEDUP)

        fast = build()
        folds = fast["transaction_log"][-1]["post_maintenance"]["dedup"]
        self.assertEqual(len(folds), 2)  # a pair folds, then its survivor folds the third record
        self.assertEqual(folds[0]["canonical_entity_id"], folds[1]["canonical_entity_id"])
        self.assertEqual(len(fast["entities"]), 1)
        original = lm._apply_dedup

        def every_candidate(memory: dict[str, Any], **kwargs: Any) -> list[dict[str, Any]]:  # the 97b76b0 behaviour
            own = kwargs.pop("own")
            for entity in list(memory["entities"]):
                if entity["state"] in lm.DEDUP_ELIGIBLE_STATES:
                    own(str(entity["entity_id"]))
            return original(memory, **kwargs, own=None)

        lm._apply_dedup = every_candidate
        try:
            slow = build()
        finally:
            lm._apply_dedup = original
        self.assertEqual(lm.canonical_json(fast), lm.canonical_json(slow))

    def test_a_tampered_shared_item_in_a_copy_is_still_refused(self) -> None:
        memories = self._sequence()
        tampered = json.loads(json.dumps(memories[-1]))  # new objects throughout: nothing is taken from the memo
        tampered["entities"][0]["evidence"][0]["frame_digest"] = "z" * 64
        with self.assertRaises(LeanMemoryError):
            validate_memory(tampered)


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


class TestDedupPrefilter(unittest.TestCase):
    """The numpy prefilter (2026-09-27) may only drop pairs the scalar tests would reject."""

    @staticmethod
    def _entities(seed: int, count: int, width: int = 128) -> list[dict[str, Any]]:
        import random

        rng = random.Random(seed)
        prototypes = [[rng.gauss(0.0, 1.0) for _ in range(width)] for _ in range(6)]
        out = []
        for index in range(count):
            base = prototypes[index % len(prototypes)]
            noise = rng.choice((0.05, 0.3, 1.0))
            out.append({"entity_id": f"entity:{index:04d}",
                        "descriptor_mean": [value + rng.gauss(0.0, noise) for value in base],
                        "centroid_m": [rng.uniform(0.0, 2.0), rng.uniform(0.0, 0.5), rng.uniform(0.0, 2.0)]})
        return out

    @staticmethod
    def _scalar_pairs(entities: list[dict[str, Any]], cosine_min: float, distance_max: float) -> set[tuple[int, int]]:
        from vsmt.lean_geometry import centroid_distance, cosine_similarity

        return {(i, j) for i in range(len(entities)) for j in range(i + 1, len(entities))
                if cosine_similarity(entities[i]["descriptor_mean"], entities[j]["descriptor_mean"]) >= cosine_min
                and centroid_distance(entities[i], entities[j]) <= distance_max}

    def test_every_pair_the_scalar_tests_accept_survives_even_at_the_exact_threshold(self) -> None:
        from vsmt.lean_geometry import centroid_distance, cosine_similarity
        from vsmt.lean_memory import DEDUP_PREFILTER_BLOCK_ROWS, _dedup_pair_candidates

        entities = self._entities(7, DEDUP_PREFILTER_BLOCK_ROWS + 45)  # crosses a block boundary
        # thresholds equal to a real pair's scalar values, so that pair sits exactly on both limits
        cosine_min = cosine_similarity(entities[0]["descriptor_mean"], entities[6]["descriptor_mean"])
        distance_max = centroid_distance(entities[0], entities[6])
        for policy in ({"descriptor_cosine_min": cosine_min, "centroid_distance_max_m": distance_max},
                       {"descriptor_cosine_min": 0.6, "centroid_distance_max_m": 0.5},
                       {"descriptor_cosine_min": -1.0, "centroid_distance_max_m": 10.0}):
            candidates = _dedup_pair_candidates(entities, policy)
            self.assertEqual(candidates, sorted(candidates))  # row-major, the order of the scalar loop
            accepted = self._scalar_pairs(entities, policy["descriptor_cosine_min"], policy["centroid_distance_max_m"])
            self.assertTrue(accepted <= set(candidates), policy)
            self.assertLess(len(candidates), len(accepted) + 50)  # a prefilter that keeps almost nothing extra
        self.assertIn((0, 6), _dedup_pair_candidates(entities, {"descriptor_cosine_min": cosine_min,
                                                                "centroid_distance_max_m": distance_max}))

    def test_irregular_or_zero_descriptors_keep_every_pair(self) -> None:
        from vsmt.lean_memory import _dedup_pair_candidates

        policy = {"descriptor_cosine_min": 0.6, "centroid_distance_max_m": 0.5}
        mixed = [{"descriptor_mean": [1.0, 0.0], "centroid_m": [0.0, 0.0, 0.0]},
                 {"descriptor_mean": [1.0, 0.0, 0.0], "centroid_m": [0.0, 0.0, 0.0]},
                 {"descriptor_mean": [0.0, 1.0], "centroid_m": [5.0, 0.0, 0.0]}]
        self.assertEqual(_dedup_pair_candidates(mixed, policy), [(0, 1), (0, 2), (1, 2)])
        zero = [{"descriptor_mean": [0.0, 0.0], "centroid_m": [0.0, 0.0, 0.0]},
                {"descriptor_mean": [1.0, 0.0], "centroid_m": [0.1, 0.0, 0.0]}]
        self.assertEqual(_dedup_pair_candidates(zero, policy), [(0, 1)])  # the scalar test rejects it, not the filter

    def test_the_folds_equal_the_all_pairs_rule(self) -> None:
        import vsmt.lean_memory as lm

        rng_entities = self._entities(11, 60, width=8)
        memory = empty_memory(episode_id="ep-prefilter")
        births = [{"atom": "BIRTH", "fragment": fragment(f"region:{i:04d}", descriptor=e["descriptor_mean"],
                                                         centroid=[v * 0.2 for v in e["centroid_m"]])}
                  for i, e in enumerate(rng_entities)]
        memory = commit(memory, "f1", births)
        policy = dict(DEDUP, descriptor_cosine_min=0.6, centroid_distance_max_m=0.5, aabb_iou_min=0.05)
        fast = commit(memory, "f2", [], dedup=policy)
        original = lm._dedup_pair_candidates
        lm._dedup_pair_candidates = lambda entities, _policy: [(i, j) for i in range(len(entities)) for j in range(i + 1, len(entities))]
        try:
            slow = commit(memory, "f2", [], dedup=policy)
        finally:
            lm._dedup_pair_candidates = original
        self.assertGreater(len(fast["transaction_log"][-1]["post_maintenance"]["dedup"]), 0)
        self.assertEqual(fast["memory_digest"], slow["memory_digest"])
        self.assertEqual(canonical_json(fast), canonical_json(slow))


class TestDedupEligibilityRulingSeventySix(unittest.TestCase):
    """D-224-S1 ruling 76 (2)(a): dormant records join the dedup; the survivor takes the later record's geometry."""

    def _a_then_b(self) -> tuple[dict[str, Any], str, str, dict[str, Any]]:
        a = fragment("region:0000", descriptor=[1.0, 0.0], centroid=[0.0, 0.0, 0.0])
        first = commit(empty_memory(episode_id="ep-0076"), "f1", [{"atom": "BIRTH", "fragment": a}])
        a_id = str(only_entity(first)["entity_id"])
        b = fragment("region:0001", descriptor=[1.0, 0.001], centroid=[0.05, 0.0, 0.0], half=0.12)
        second = commit(first, "f2", [{"atom": "BIRTH", "fragment": b}, {"atom": "NOOP", "entity_id": a_id}])
        b_id = next(str(e["entity_id"]) for e in second["entities"] if str(e["entity_id"]) != a_id)
        return second, a_id, b_id, b

    def test_a_dormant_record_folds_into_an_active_survivor_with_the_later_geometry(self) -> None:
        memory, a_id, b_id, b = self._a_then_b()
        memory = commit(memory, "f3", [{"atom": "NOOP", "entity_id": a_id}])
        states = {str(e["entity_id"]): e["state"] for e in memory["entities"]}
        self.assertEqual(states, {a_id: "dormant", b_id: "active"})
        entity = only_entity(commit(memory, "f4", [], dedup=DEDUP))
        self.assertEqual(entity["entity_id"], a_id)  # the earlier identity survives
        self.assertEqual(entity["state"], "active")
        self.assertEqual(entity["versions"][-1]["opened_by"], "dedup")
        self.assertEqual(entity["centroid_m"], b["centroid_m"])  # the later record's centroid, not a count-weighted blend
        self.assertEqual(entity["aabb_min_m"], b["aabb_min_m"])
        self.assertEqual(entity["last_seen_tick"], 2)

    def test_two_dormant_records_fold_into_a_dormant_survivor(self) -> None:
        memory, a_id, b_id, b = self._a_then_b()
        memory = commit(memory, "f3", [{"atom": "NOOP", "entity_id": a_id}, {"atom": "NOOP", "entity_id": b_id}])
        memory = commit(memory, "f4", [{"atom": "NOOP", "entity_id": b_id}])
        self.assertEqual({e["state"] for e in memory["entities"]}, {"dormant"})
        entity = only_entity(commit(memory, "f5", [], dedup=DEDUP))
        self.assertEqual(entity["state"], "dormant")
        self.assertEqual(entity["versions"][-1]["opened_by"], "dedup_dormant")
        self.assertEqual(entity["versions"][-1]["state"], "dormant")
        self.assertEqual(entity["centroid_m"], b["centroid_m"])

    def test_a_retracted_record_is_never_folded(self) -> None:
        memory, a_id, _, _ = self._a_then_b()
        memory = commit(memory, "f3", [{"atom": "RETRACT", "entity_id": a_id}])
        merged = commit(memory, "f4", [], dedup=DEDUP)
        self.assertEqual(len(merged["entities"]), 2)
        self.assertEqual(merged["transaction_log"][-1]["post_maintenance"]["dedup"], [])

    def test_the_contract_binds_the_dedup_rule(self) -> None:
        from vsmt.lean_memory import DEDUP_ELIGIBLE_STATES, DEDUP_RULE

        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(contract["shared_dedup"]["rule"], DEDUP_RULE)
        self.assertEqual(tuple(contract["shared_dedup"]["eligible_states"]), DEDUP_ELIGIBLE_STATES)
        for name, value in (("eligible_states", ["active"]), ("rule", "periodic_deterministic_merge_of_duplicate_active_entities"),
                            ("survivor_state", "always_active")):
            broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
            broken["shared_dedup"][name] = value
            with self.assertRaises(LeanMemoryError) as caught:
                validate_entity_memory_contract(broken)
            self.assertEqual(str(caught.exception), "contract_dedup_rule_mismatch")


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

        self.assertEqual(VERSION_OPENED_BY, ("birth", "bind", "reactivate", "retract", "dormant", "dedup", "dedup_dormant"))
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

    def test_frozen_policy_values_are_bound_and_cannot_reopen_by_edit(self) -> None:
        # D-224-S1 ruling 67 (2026-09-24): the five values are frozen; another number is refused,
        # and nulling one without registering it as open is refused too
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(contract["shared_dormancy"]["dormancy_missed_opportunity_limit"], DORMANCY_MISSED_OPPORTUNITY_LIMIT)
        self.assertEqual({name: contract["shared_dedup"][name] for name in SHARED_DEDUP}, SHARED_DEDUP)
        self.assertEqual(contract["policy_values_without_defaults"], [])
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["shared_dedup"]["aabb_iou_min"] = 0.2
        with self.assertRaises(LeanMemoryError) as caught:
            validate_entity_memory_contract(broken)
        self.assertEqual(str(caught.exception), "contract_aabb_iou_min_differs_from_the_frozen_constant")
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["shared_dormancy"]["dormancy_missed_opportunity_limit"] = None
        with self.assertRaises(LeanMemoryError) as caught:
            validate_entity_memory_contract(broken)
        self.assertEqual(str(caught.exception), "contract_dormancy_missed_opportunity_limit_null_but_not_registered_as_open")

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
