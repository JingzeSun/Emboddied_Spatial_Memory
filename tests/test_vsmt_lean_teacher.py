"""D-224 / S0-04 tests for the teacher, the decomposition and the metrics.

The continue gate for S0-04 is: the metric list is frozen; private truth
opens only against a two-seal receipt; every label is either resolvable or
counted; the evaluator's matching is independent of the method's solver and
agrees with brute force; every boolean claim in the contract is bound.
Hand-built cases only; nothing here is a result.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path
import random
import sys
import unittest
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from vsmt.lean_memory import apply_program, empty_memory  # noqa: E402
from vsmt.lean_teacher import (  # noqa: E402
    ABLATION_ARMS,
    ASSOCIATION_STATUSES,
    BOOTSTRAP_ITERATIONS,
    CONTRACT_SCHEMA_VERSION,
    DECOMPOSITION,
    EXISTENCE_STATUSES,
    EXPECTED_BOOLEAN_CLAIMS,
    IOU_MIN,
    MAIN_GATE,
    METRICS,
    METRIC_FIELDS,
    METRIC_NOT_APPLICABLE_RULE,
    NULL_POLICY_PATHS,
    NUISANCE_FIELDS,
    RULINGS_DECISION_ID,
    LeanTeacherError,
    _max_weight_matching,
    _max_weight_matching_dense,
    ablation_report,
    assert_private_gate,
    assert_report_keys,
    association_targets,
    build_private_gate,
    contamination_auc,
    decompose_frame,
    entity_identity,
    episode_recovery_latency,
    evaluate_frame,
    existence_labels,
    false_retract_rate,
    fragment_dominance,
    identity_continuity,
    main_gate,
    micro_average,
    missing_residual_rate,
    nuisance_probe,
    object_memory_correct,
    paired_house_bootstrap,
    run_nuisance_probes,
    size_and_cost,
    strongest_control,
    undefined_houses,
    validate_teacher_contract,
)


CONTRACT_PATH = PROJECT_ROOT / "configs" / "vsmt" / "lean_s0_teacher_metrics_v2.json"
MODULE_PATH = PROJECT_ROOT / "src" / "vsmt" / "lean_teacher.py"
METHOD_ID = "vsmt.lean.test.v1"
DOMINANCE = 0.6
DELTA = 0.5
KEYS = {"region:0000": "obj:mug", "region:0001": "obj:book"}


def digest(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def frag(fragment_id: str, *, descriptor: list[float], centroid: list[float]) -> dict[str, Any]:
    return {
        "fragment_id": fragment_id,
        "descriptor": list(descriptor),
        "centroid_m": list(centroid),
        "aabb_min_m": [value - 0.1 for value in centroid],
        "aabb_max_m": [value + 0.1 for value in centroid],
        "pixel_count": 400,
        "supported_by": None,
    }


def box(centroid: list[float], *, half: float = 0.1, present: bool = True, in_scope: bool = True) -> dict[str, Any]:
    if not present:
        return {"present": False, "in_scope": in_scope}
    return {
        "present": True,
        "in_scope": in_scope,
        "centroid_m": list(centroid),
        "aabb_min_m": [value - half for value in centroid],
        "aabb_max_m": [value + half for value in centroid],
    }


def step(memory: Mapping[str, Any], seed: str, operations: list[dict[str, Any]], *, limit: int = 2) -> dict[str, Any]:
    return apply_program(
        memory, {"frame_digest": digest(seed), "operations": operations},
        method_id=METHOD_ID, dormancy_missed_opportunity_limit=limit,
    )


def two_entity_memory() -> tuple[dict[str, Any], str, str]:
    """BIRTH a mug at the origin and a book one metre away, at tick 1."""

    memory = step(empty_memory(episode_id="ep-0001"), "f1", [
        {"atom": "BIRTH", "fragment": frag("region:0000", descriptor=[1.0, 0.0], centroid=[0.0, 0.0, 0.0])},
        {"atom": "BIRTH", "fragment": frag("region:0001", descriptor=[0.0, 1.0], centroid=[1.0, 0.0, 0.0])},
    ])
    by_fragment = {
        entity["evidence"][0]["fragment_id"]: str(entity["entity_id"])
        for entity in memory["entities"]
    }
    return memory, by_fragment["region:0000"], by_fragment["region:0001"]


def entity_of(memory: Mapping[str, Any], entity_id: str) -> dict[str, Any]:
    return [item for item in memory["entities"] if item["entity_id"] == entity_id][0]


def evidence_map(memory: Mapping[str, Any], keys: Mapping[str, str | None]) -> dict[str, str | None]:
    """Map every evidence fragment of the memory to a private key."""

    out: dict[str, str | None] = {}
    for entity in memory["entities"]:
        for item in entity["evidence"]:
            out[f"{item['frame_digest']}|{item['fragment_id']}"] = keys.get(item["fragment_id"])
    return out


def overlap(pixel_count: int = 400, **shares: float) -> dict[str, Any]:
    return {
        "overlap": {key.replace("_", ":"): value for key, value in shares.items()},
        "pixel_count": pixel_count,
    }


def gate() -> dict[str, Any]:
    return {
        "frame_digest": digest("f2"),
        "stage_a_seal_sha256": digest("a"),
        "stage_b_seal_sha256": digest("b"),
        "private_may_open": True,
    }


class TestPrivateGate(unittest.TestCase):
    def test_a_two_seal_receipt_passes(self) -> None:
        assert_private_gate(gate())

    def test_a_receipt_missing_stage_b_is_rejected(self) -> None:
        receipt = gate()
        del receipt["stage_b_seal_sha256"]
        with self.assertRaises(LeanTeacherError) as caught:
            assert_private_gate(receipt)
        self.assertEqual(str(caught.exception), "private_gate_fields_invalid")

    def test_a_closed_receipt_is_rejected(self) -> None:
        receipt = gate()
        receipt["private_may_open"] = False
        with self.assertRaises(LeanTeacherError) as caught:
            assert_private_gate(receipt)
        self.assertEqual(str(caught.exception), "private_gate_not_open")

    def _stages(self) -> tuple[dict[str, Any], dict[str, Any]]:
        stage_a = {
            "frame_digest": digest("f2"), "seal_sha256": digest("a"),
            "recall": {}, "association_rows": [], "birth_rows": [],
        }
        stage_b = {
            "frame_digest": digest("f2"), "seal_sha256": digest("b"),
            "stage_a_seal_sha256": digest("a"), "assignment": {}, "existence_rows": [],
        }
        return stage_a, stage_b

    def test_two_chained_seals_build_a_receipt(self) -> None:
        stage_a, stage_b = self._stages()
        receipt = build_private_gate(stage_a, stage_b)
        self.assertTrue(receipt["private_may_open"])
        self.assertEqual(receipt["stage_a_seal_sha256"], digest("a"))
        self.assertEqual(receipt["stage_b_seal_sha256"], digest("b"))

    def test_a_broken_chain_yields_no_receipt(self) -> None:
        stage_a, stage_b = self._stages()
        stage_b["stage_a_seal_sha256"] = digest("tampered")
        with self.assertRaises(LeanTeacherError) as caught:
            build_private_gate(stage_a, stage_b)
        self.assertEqual(str(caught.exception), "gate_chain_broken")

    def test_stage_b_for_another_frame_yields_no_receipt(self) -> None:
        stage_a, stage_b = self._stages()
        stage_b["frame_digest"] = digest("f3")
        with self.assertRaises(LeanTeacherError) as caught:
            build_private_gate(stage_a, stage_b)
        self.assertEqual(str(caught.exception), "gate_frame_mismatch")

    def test_stage_b_without_existence_rows_yields_no_receipt(self) -> None:
        stage_a, stage_b = self._stages()
        del stage_b["existence_rows"]
        with self.assertRaises(LeanTeacherError) as caught:
            build_private_gate(stage_a, stage_b)
        self.assertEqual(str(caught.exception), "gate_stage_b_incomplete:existence_rows")

    def test_the_teacher_opens_no_files_and_imports_no_solver(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        for forbidden in ("lean_assignment", "open(", "json.load", "np.load", "Path("):
            self.assertNotIn(forbidden, source, forbidden)


class TestEntityIdentity(unittest.TestCase):
    def test_a_strict_majority_resolves(self) -> None:
        memory, mug, _ = two_entity_memory()
        identity = entity_identity(entity_of(memory, mug), evidence_map(memory, KEYS))
        self.assertEqual(identity["key"], "obj:mug")
        self.assertTrue(identity["resolvable"])

    def test_a_split_vote_is_ambiguous_not_guessed(self) -> None:
        memory, mug, _ = two_entity_memory()
        memory = step(memory, "f2", [
            {"atom": "BIND", "entity_id": mug, "fragment": frag("region:0009", descriptor=[1.0, 0.0], centroid=[0.0, 0.0, 0.0])},
        ])
        identity = entity_identity(entity_of(memory, mug), evidence_map(memory, {**KEYS, "region:0009": "obj:cup"}))
        self.assertFalse(identity["resolvable"])
        self.assertIsNone(identity["key"])
        self.assertEqual(identity["reason"], "no_strict_majority")
        self.assertEqual(identity["keys_seen"], ["obj:cup", "obj:mug"])

    def test_background_evidence_does_not_vote(self) -> None:
        memory, mug, _ = two_entity_memory()
        memory = step(memory, "f2", [
            {"atom": "BIND", "entity_id": mug, "fragment": frag("region:0009", descriptor=[1.0, 0.0], centroid=[0.0, 0.0, 0.0])},
        ])
        identity = entity_identity(entity_of(memory, mug), evidence_map(memory, {**KEYS, "region:0009": None}))
        self.assertEqual(identity["key"], "obj:mug")
        self.assertEqual(identity["evidence_keyed"], 1)
        self.assertEqual(identity["evidence_total"], 2)

    def test_no_keyed_evidence_is_unresolvable(self) -> None:
        memory, mug, _ = two_entity_memory()
        identity = entity_identity(entity_of(memory, mug), {})
        self.assertFalse(identity["resolvable"])
        self.assertEqual(identity["reason"], "no_keyed_evidence")


class TestFragmentDominance(unittest.TestCase):
    def test_no_instance_is_unlabelled(self) -> None:
        out = fragment_dominance({}, dominance_min_share=DOMINANCE)
        self.assertEqual((out["status"], out["reason"]), ("unlabelled", "no_instance"))

    def test_two_instances_below_threshold_are_ambiguous(self) -> None:
        out = fragment_dominance({"obj:mug": 0.45, "obj:book": 0.4}, dominance_min_share=DOMINANCE)
        self.assertEqual((out["status"], out["reason"]), ("identity_ambiguous", "fragment_dominance"))
        self.assertEqual(out["instance_count"], 2)

    def test_a_tie_at_the_top_is_ambiguous_even_above_threshold(self) -> None:
        out = fragment_dominance({"obj:mug": 0.5, "obj:book": 0.5}, dominance_min_share=0.5)
        self.assertEqual(out["status"], "identity_ambiguous")

    def test_one_instance_below_threshold_is_unlabelled(self) -> None:
        out = fragment_dominance({"obj:mug": 0.3}, dominance_min_share=DOMINANCE)
        self.assertEqual((out["status"], out["reason"]), ("unlabelled", "dominant_share_below_threshold"))

    def test_a_dominant_instance_resolves(self) -> None:
        out = fragment_dominance({"obj:mug": 0.7, "obj:book": 0.2}, dominance_min_share=DOMINANCE)
        self.assertEqual((out["status"], out["key"]), ("dominant", "obj:mug"))

    def test_shares_over_one_are_rejected(self) -> None:
        with self.assertRaises(LeanTeacherError) as caught:
            fragment_dominance({"obj:mug": 0.7, "obj:book": 0.4}, dominance_min_share=DOMINANCE)
        self.assertEqual(str(caught.exception), "fragment_overlap_exceeds_one")


class TestAssociationTargets(unittest.TestCase):
    def _targets(self, memory: Mapping[str, Any], recall: Mapping[str, list[str]],
                 instance: Mapping[str, Mapping[str, Any]], keys: Mapping[str, str | None] = KEYS) -> dict[str, dict[str, Any]]:
        return association_targets(
            memory, recall=recall, fragment_instance=instance,
            evidence_instance=evidence_map(memory, keys), dominance_min_share=DOMINANCE,
        )

    def test_a_recalled_matching_entity_is_the_target(self) -> None:
        memory, mug, book = two_entity_memory()
        targets = self._targets(memory, {"region:0002": [mug, book]}, {"region:0002": overlap(obj_mug=0.9)})
        self.assertEqual(targets["region:0002"]["status"], "labelled")
        self.assertEqual(targets["region:0002"]["target"], mug)

    def test_a_matching_entity_outside_recall_is_a_recall_miss(self) -> None:
        memory, mug, book = two_entity_memory()
        targets = self._targets(memory, {"region:0002": [book]}, {"region:0002": overlap(obj_mug=0.9)})
        self.assertEqual(targets["region:0002"]["status"], "recall_miss")
        self.assertEqual(targets["region:0002"]["target"], mug)

    def test_an_object_absent_from_memory_targets_birth(self) -> None:
        memory, mug, book = two_entity_memory()
        targets = self._targets(memory, {"region:0002": [mug, book]}, {"region:0002": overlap(obj_lamp=0.9)})
        self.assertEqual(targets["region:0002"]["status"], "birth")
        self.assertEqual(targets["region:0002"]["target"], "birth:region:0002")

    def test_a_background_fragment_is_unlabelled(self) -> None:
        memory, mug, _ = two_entity_memory()
        targets = self._targets(memory, {"region:0002": [mug]}, {"region:0002": overlap(obj_mug=0.4)})
        self.assertEqual(targets["region:0002"]["status"], "unlabelled")
        self.assertIsNone(targets["region:0002"]["target"])

    def test_a_fragment_straddling_two_objects_is_identity_ambiguous(self) -> None:
        memory, mug, book = two_entity_memory()
        targets = self._targets(memory, {"region:0002": [mug, book]}, {"region:0002": overlap(obj_mug=0.5, obj_book=0.45)})
        self.assertEqual(targets["region:0002"]["status"], "identity_ambiguous")
        self.assertEqual(targets["region:0002"]["reason"], "fragment_dominance")

    def test_an_object_trapped_in_an_ambiguous_entity_is_not_guessed_as_birth(self) -> None:
        memory, mug, book = two_entity_memory()
        memory = step(memory, "f2", [
            {"atom": "BIND", "entity_id": mug, "fragment": frag("region:0009", descriptor=[1.0, 0.0], centroid=[0.0, 0.0, 0.0])},
        ])
        keys = {**KEYS, "region:0009": "obj:cup"}
        # The cup's only evidence sits inside the now-ambiguous mug entity.
        recalled = self._targets(memory, {"region:0002": [mug]}, {"region:0002": overlap(obj_cup=0.9)}, keys)
        self.assertEqual(recalled["region:0002"]["status"], "identity_ambiguous")
        self.assertEqual(recalled["region:0002"]["reason"], "entity_identity")
        not_recalled = self._targets(memory, {"region:0002": [book]}, {"region:0002": overlap(obj_cup=0.9)}, keys)
        self.assertEqual(not_recalled["region:0002"]["status"], "identity_ambiguous")

    def test_duplicates_resolve_to_the_earliest_identity(self) -> None:
        memory, mug, book = two_entity_memory()
        memory = step(memory, "f2", [
            {"atom": "BIRTH", "fragment": frag("region:0005", descriptor=[1.0, 0.0], centroid=[0.05, 0.0, 0.0])},
        ])
        duplicate = [str(item["entity_id"]) for item in memory["entities"] if item["evidence"][0]["fragment_id"] == "region:0005"][0]
        keys = {**KEYS, "region:0005": "obj:mug"}
        both = self._targets(memory, {"region:0007": [mug, duplicate]}, {"region:0007": overlap(obj_mug=0.9)}, keys)
        self.assertEqual(both["region:0007"]["target"], mug)
        self.assertEqual(both["region:0007"]["duplicate_identity_count"], 1)
        only_duplicate = self._targets(memory, {"region:0007": [duplicate]}, {"region:0007": overlap(obj_mug=0.9)}, keys)
        self.assertEqual(only_duplicate["region:0007"]["status"], "labelled")
        self.assertEqual(only_duplicate["region:0007"]["target"], duplicate)

    def test_a_retracted_entity_is_a_legal_target(self) -> None:
        memory, mug, book = two_entity_memory()
        memory = step(memory, "f2", [{"atom": "RETRACT", "entity_id": mug}])
        targets = self._targets(memory, {"region:0002": [mug, book]}, {"region:0002": overlap(obj_mug=0.9)})
        self.assertEqual(targets["region:0002"]["target"], mug)

    def test_the_recall_is_neither_edited_nor_reordered(self) -> None:
        memory, mug, book = two_entity_memory()
        recall = {"region:0002": [book, mug], "region:0003": [mug]}
        before = json.dumps(recall, sort_keys=True)
        self._targets(memory, recall, {"region:0002": overlap(obj_mug=0.9), "region:0003": overlap(obj_book=0.9)})
        self.assertEqual(json.dumps(recall, sort_keys=True), before)

    def test_two_fragments_of_one_object_keep_one_target(self) -> None:
        """D-224-X ruling X1: the fragment with the most pixels on the object keeps it."""

        memory, mug, book = two_entity_memory()
        recall = {"region:0002": [mug], "region:0003": [mug]}
        instance = {"region:0002": overlap(obj_mug=0.9, pixel_count=500), "region:0003": overlap(obj_mug=0.95, pixel_count=300)}
        targets = self._targets(memory, recall, instance)
        # 0.9 * 500 = 450 object pixels beats 0.95 * 300 = 285.
        self.assertEqual((targets["region:0002"]["status"], targets["region:0002"]["target"]), ("labelled", mug))
        self.assertEqual(targets["region:0003"]["status"], "duplicate_of_labelled")
        self.assertIsNone(targets["region:0003"]["target"])
        self.assertEqual(targets["region:0003"]["duplicate_of"], "region:0002")
        self.assertEqual(targets["region:0003"]["displaced_target"], mug)
        decomposed = decompose_frame(
            targets=targets, assignment={"region:0002": mug, "region:0003": "birth:region:0003"},
            existence={}, decisions={},
        )
        self.assertEqual(decomposed["totals"]["amortization_error"], 0)
        self.assertEqual(decomposed["totals"]["correct"], 1)
        self.assertEqual(decomposed["totals"]["duplicate_of_labelled"], 1)
        self.assertEqual(decomposed["totals"]["decisions"], 2)

    def test_the_student_may_carry_the_object_through_any_member_of_the_group(self) -> None:
        """Review correction (LOG-225): binding the smaller fragment to the target is not an error."""

        memory, mug, book = two_entity_memory()
        recall = {"region:0002": [mug, book], "region:0003": [mug, book]}
        instance = {"region:0002": overlap(obj_mug=0.9, pixel_count=500), "region:0003": overlap(obj_mug=0.9, pixel_count=300)}
        targets = self._targets(memory, recall, instance)
        self.assertEqual(targets["region:0002"]["status"], "labelled")
        self.assertEqual(targets["region:0003"]["status"], "duplicate_of_labelled")
        # The small fragment takes the mug, the keeper births: the object reached its entity.
        via_duplicate = decompose_frame(
            targets=targets, assignment={"region:0002": "birth:region:0002", "region:0003": mug},
            existence={}, decisions={},
        )
        self.assertEqual((via_duplicate["totals"]["correct"], via_duplicate["totals"]["amortization_error"]), (1, 0))
        # Nobody takes the mug: one error, charged once.
        nobody = decompose_frame(
            targets=targets, assignment={"region:0002": "birth:region:0002", "region:0003": "birth:region:0003"},
            existence={}, decisions={},
        )
        self.assertEqual((nobody["totals"]["correct"], nobody["totals"]["amortization_error"]), (0, 1))
        # The duplicate takes the mug but the keeper is bound to the book: a wrong binding, still one error.
        misbound = decompose_frame(
            targets=targets, assignment={"region:0002": book, "region:0003": mug},
            existence={}, decisions={},
        )
        self.assertEqual((misbound["totals"]["correct"], misbound["totals"]["amortization_error"]), (0, 1))
        self.assertEqual(misbound["totals"]["duplicate_of_labelled"], 1)
        self.assertEqual(misbound["totals"]["decisions"], 2)

    def test_duplicate_tie_breaks_are_pixel_count_then_fragment_id(self) -> None:
        memory, mug, _ = two_entity_memory()
        recall = {"region:0002": [mug], "region:0003": [mug], "region:0004": [mug]}
        instance = {
            "region:0002": overlap(obj_mug=0.8, pixel_count=400),
            "region:0003": overlap(obj_mug=0.64, pixel_count=500),
            "region:0004": overlap(obj_mug=0.8, pixel_count=400),
        }
        targets = self._targets(memory, recall, instance)
        # 320 object pixels each (0.8 * 400 and 0.64 * 500); region:0003 has the larger fragment.
        self.assertEqual(targets["region:0003"]["status"], "labelled")
        self.assertEqual(targets["region:0002"]["status"], "duplicate_of_labelled")
        self.assertEqual(targets["region:0004"]["status"], "duplicate_of_labelled")
        instance["region:0003"] = overlap(obj_mug=0.8, pixel_count=400)
        targets = self._targets(memory, recall, instance)
        self.assertEqual(targets["region:0002"]["status"], "labelled")
        self.assertEqual(targets["region:0003"]["status"], "duplicate_of_labelled")

    def test_fragments_with_different_targets_or_birth_targets_are_not_folded(self) -> None:
        memory, mug, book = two_entity_memory()
        memory = step(memory, "f2", [
            {"atom": "BIRTH", "fragment": frag("region:0005", descriptor=[1.0, 0.0], centroid=[0.05, 0.0, 0.0])},
        ])
        duplicate = [str(item["entity_id"]) for item in memory["entities"] if item["evidence"][0]["fragment_id"] == "region:0005"][0]
        keys = {**KEYS, "region:0005": "obj:mug"}
        # Same object, but each fragment recalls a different carrier: both can be satisfied.
        targets = self._targets(memory, {"region:0006": [mug], "region:0007": [duplicate]},
                                {"region:0006": overlap(obj_mug=0.9), "region:0007": overlap(obj_mug=0.9)}, keys)
        self.assertEqual({targets["region:0006"]["status"], targets["region:0007"]["status"]}, {"labelled"})
        self.assertNotEqual(targets["region:0006"]["target"], targets["region:0007"]["target"])
        # Two fragments of a new object each get their own birth column.
        births = self._targets(memory, {"region:0008": [mug], "region:0009": [mug]},
                               {"region:0008": overlap(obj_lamp=0.9), "region:0009": overlap(obj_lamp=0.9)}, keys)
        self.assertEqual({births["region:0008"]["status"], births["region:0009"]["status"]}, {"birth"})
        # Two recall misses stay recall misses: the student is not charged either way.
        misses = self._targets(memory, {"region:0010": [book], "region:0011": [book]},
                               {"region:0010": overlap(obj_mug=0.9), "region:0011": overlap(obj_mug=0.9)}, keys)
        self.assertEqual({misses["region:0010"]["status"], misses["region:0011"]["status"]}, {"recall_miss"})

    def test_a_fragment_instance_without_pixel_count_is_rejected(self) -> None:
        memory, mug, _ = two_entity_memory()
        with self.assertRaises(LeanTeacherError) as caught:
            self._targets(memory, {"region:0002": [mug]}, {"region:0002": {"overlap": {"obj:mug": 0.9}}})
        self.assertIn("fragment_instance_missing", str(caught.exception))

    def test_a_recalled_unknown_entity_is_rejected(self) -> None:
        memory, mug, _ = two_entity_memory()
        with self.assertRaises(LeanTeacherError) as caught:
            self._targets(memory, {"region:0002": ["entity:nope"]}, {"region:0002": overlap(obj_mug=0.9)})
        self.assertIn("recall_entity_unknown", str(caught.exception))

    def test_a_missing_fragment_instance_is_rejected(self) -> None:
        memory, mug, _ = two_entity_memory()
        with self.assertRaises(LeanTeacherError) as caught:
            self._targets(memory, {"region:0002": [mug]}, {})
        self.assertIn("fragment_instance_missing", str(caught.exception))


class TestExistenceLabels(unittest.TestCase):
    def _labels(self, memory: Mapping[str, Any], candidates: list[str],
                state: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
        return existence_labels(
            memory, candidates=candidates, object_state=state,
            evidence_instance=evidence_map(memory, KEYS), delta_moved_m=DELTA,
        )

    def test_an_absent_object_is_gone(self) -> None:
        memory, mug, _ = two_entity_memory()
        labels = self._labels(memory, [mug], {"obj:mug": {"present": False}})
        self.assertEqual((labels[mug]["status"], labels[mug]["reason"]), ("gone", "absent"))

    def test_a_moved_object_is_gone(self) -> None:
        memory, mug, _ = two_entity_memory()
        labels = self._labels(memory, [mug], {"obj:mug": {"present": True, "centroid_m": [3.0, 0.0, 0.0]}})
        self.assertEqual((labels[mug]["status"], labels[mug]["reason"]), ("gone", "moved"))

    def test_an_occluded_object_in_place_is_present(self) -> None:
        memory, mug, _ = two_entity_memory()
        labels = self._labels(memory, [mug], {"obj:mug": {"present": True, "centroid_m": [0.1, 0.0, 0.0]}})
        self.assertEqual(labels[mug]["status"], "present")

    def test_a_dormant_candidate_is_labelled(self) -> None:
        memory, mug, _ = two_entity_memory()
        memory = step(memory, "f2", [{"atom": "NOOP", "entity_id": mug}], limit=1)
        self.assertEqual(entity_of(memory, mug)["state"], "dormant")
        labels = self._labels(memory, [mug], {"obj:mug": {"present": False}})
        self.assertEqual(labels[mug]["status"], "gone")

    def test_a_retracted_candidate_is_rejected_not_skipped(self) -> None:
        memory, mug, _ = two_entity_memory()
        memory = step(memory, "f2", [{"atom": "RETRACT", "entity_id": mug}])
        with self.assertRaises(LeanTeacherError) as caught:
            self._labels(memory, [mug], {"obj:mug": {"present": False}})
        self.assertIn("existence_candidate_state_not_eligible", str(caught.exception))

    def test_an_ambiguous_candidate_is_counted_not_guessed(self) -> None:
        memory, mug, _ = two_entity_memory()
        memory = step(memory, "f2", [
            {"atom": "BIND", "entity_id": mug, "fragment": frag("region:0009", descriptor=[1.0, 0.0], centroid=[0.0, 0.0, 0.0])},
        ])
        labels = existence_labels(
            memory, candidates=[mug], object_state={"obj:mug": {"present": False}},
            evidence_instance=evidence_map(memory, {**KEYS, "region:0009": "obj:cup"}), delta_moved_m=DELTA,
        )
        self.assertEqual(labels[mug]["status"], "identity_ambiguous")

    def test_an_unknown_candidate_is_rejected(self) -> None:
        memory, _, _ = two_entity_memory()
        with self.assertRaises(LeanTeacherError) as caught:
            self._labels(memory, ["entity:nope"], {})
        self.assertIn("existence_candidate_unknown", str(caught.exception))


class TestDecomposition(unittest.TestCase):
    def test_each_decision_lands_in_exactly_one_class_and_the_classes_add_up(self) -> None:
        targets = {
            "f1": {"status": "labelled", "target": "e1"},
            "f2": {"status": "labelled", "target": "e2"},
            "f3": {"status": "recall_miss", "target": "e3"},
            "f4": {"status": "identity_ambiguous", "target": None},
            "f5": {"status": "unlabelled", "target": None},
            "f6": {"status": "birth", "target": "birth:f6"},
        }
        assignment = {"f1": "e1", "f2": "birth:f2", "f3": "birth:f3", "f4": "e9", "f5": "e9", "f6": "birth:f6"}
        existence = {"e7": {"status": "gone"}, "e8": {"status": "present"}, "e9": {"status": "identity_ambiguous"}}
        decisions = {"e7": "NOOP", "e8": "RETRACT", "e9": "RETRACT"}
        out = decompose_frame(targets=targets, assignment=assignment, existence=existence, decisions=decisions)
        self.assertEqual(out["association"]["correct"], 2)
        self.assertEqual(out["association"]["amortization_error"], 1)
        self.assertEqual(out["association"]["recall_miss"], 1)
        self.assertEqual(out["association"]["teacher_error"], 1)
        self.assertEqual(out["association"]["unlabelled"], 1)
        self.assertEqual(out["existence"], {"candidates": 3, "teacher_error": 1, "correct": 0, "false_retract": 1, "missed_retract": 1})
        totals = out["totals"]
        self.assertEqual(totals, {
            "recall_miss": 1, "teacher_error": 2, "amortization_error": 3, "correct": 2, "unlabelled": 1, "duplicate_of_labelled": 0, "decisions": 9,
        })
        self.assertEqual(sum(totals[name] for name in DECOMPOSITION) + totals["correct"] + totals["unlabelled"], totals["decisions"])

    def test_a_fragment_without_an_assignment_is_rejected(self) -> None:
        with self.assertRaises(LeanTeacherError) as caught:
            decompose_frame(targets={"f1": {"status": "labelled", "target": "e1"}}, assignment={}, existence={}, decisions={})
        self.assertEqual(str(caught.exception), "assignment_fragments_differ_from_targets")

    def test_a_candidate_without_a_decision_is_rejected(self) -> None:
        with self.assertRaises(LeanTeacherError) as caught:
            decompose_frame(targets={}, assignment={}, existence={"e1": {"status": "gone"}}, decisions={})
        self.assertEqual(str(caught.exception), "decisions_differ_from_existence_candidates")

    def test_a_decision_other_than_retract_or_noop_is_rejected(self) -> None:
        with self.assertRaises(LeanTeacherError) as caught:
            decompose_frame(targets={}, assignment={}, existence={"e1": {"status": "gone"}}, decisions={"e1": "BIND"})
        self.assertEqual(str(caught.exception), "decision_not_retract_or_noop")

    def test_taking_another_fragments_birth_column_is_rejected(self) -> None:
        with self.assertRaises(LeanTeacherError) as caught:
            decompose_frame(targets={"f1": {"status": "birth", "target": "birth:f1"}}, assignment={"f1": "birth:f2"}, existence={}, decisions={})
        self.assertEqual(str(caught.exception), "assignment_took_another_fragments_birth_column")


class TestEvaluatorMatching(unittest.TestCase):
    def test_matching_agrees_with_brute_force(self) -> None:
        rng = random.Random(4242)
        for _ in range(40):
            rows = rng.randint(0, 4)
            columns = rng.randint(0, 4)
            weights = [[rng.choice([0.0, 0.0, 0.31, 0.5, 0.8, 1.0]) for _ in range(columns)] for _ in range(rows)]
            pairs = _max_weight_matching(weights)
            got = sum(weights[r][c] for r, c in pairs)
            best = 0.0
            if rows and columns:
                for size in range(0, min(rows, columns) + 1):
                    for row_subset in itertools.combinations(range(rows), size):
                        for column_perm in itertools.permutations(range(columns), size):
                            best = max(best, sum(weights[r][c] for r, c in zip(row_subset, column_perm)))
            self.assertAlmostEqual(got, best, places=9)
            self.assertEqual(len({r for r, _ in pairs}), len(pairs))
            self.assertEqual(len({c for _, c in pairs}), len(pairs))

    def test_component_matching_equals_the_v1_dense_solve(self) -> None:
        """D-224-X ruling X5: per-component solves return the v1 pairs on tie-free weights."""

        rng = random.Random(9090)
        for _ in range(40):
            rows = rng.randint(0, 30)
            columns = rng.randint(0, 12)
            weights = [[0.0] * columns for _ in range(rows)]
            for row in range(rows):
                if columns and rng.random() < 0.9:
                    weights[row][rng.randrange(columns)] = rng.uniform(0.3, 1.0)
                if columns and rng.random() < 0.2:
                    weights[row][rng.randrange(columns)] = rng.uniform(0.3, 1.0)
            got = _max_weight_matching(weights)
            expected = _max_weight_matching_dense(weights) if rows and columns else []
            self.assertEqual(got, expected)

    def test_component_matching_keeps_the_v1_count_and_weight_under_ties(self) -> None:
        rng = random.Random(6060)
        for _ in range(40):
            rows = rng.randint(1, 12)
            columns = rng.randint(1, 8)
            weights = [[rng.choice([0.0, 0.0, 0.31, 0.5, 0.8]) for _ in range(columns)] for _ in range(rows)]
            got = _max_weight_matching(weights)
            expected = _max_weight_matching_dense(weights)
            self.assertEqual(len(got), len(expected))
            self.assertAlmostEqual(
                sum(weights[r][c] for r, c in got), sum(weights[r][c] for r, c in expected), places=9,
            )
            self.assertEqual(len({r for r, _ in got}), len(got))
            self.assertEqual(len({c for _, c in got}), len(got))

    def _evaluate(self, memory: Mapping[str, Any], truth: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
        return evaluate_frame(
            memory, truth_objects=truth, evidence_instance=evidence_map(memory, KEYS),
            iou_min=IOU_MIN, delta_moved_m=DELTA,
        )

    def test_node_precision_recall_and_stale_entities(self) -> None:
        memory, mug, book = two_entity_memory()
        truth = {"obj:mug": box([0.0, 0.0, 0.0]), "obj:book": box([1.0, 0.0, 0.0]), "obj:lamp": box([5.0, 0.0, 0.0])}
        out = self._evaluate(memory, truth)
        self.assertAlmostEqual(out["node_precision"], 1.0)
        self.assertAlmostEqual(out["node_recall"], 2 / 3)
        self.assertAlmostEqual(out["node_f1"], 0.8)
        self.assertEqual(out["stale_entities"], [])
        self.assertEqual(out["wrongly_absent_objects"], ["obj:lamp"])
        self.assertAlmostEqual(out["contamination_fraction"], 1 / 3)

        truth["obj:mug"] = box([4.0, 0.0, 0.0])
        moved = self._evaluate(memory, truth)
        self.assertEqual(moved["stale_entities"], [mug])
        self.assertEqual(moved["wrongly_absent_objects"], ["obj:lamp", "obj:mug"])
        self.assertAlmostEqual(moved["node_precision"], 0.5)

    def test_a_dormant_entity_still_counts_as_predicted(self) -> None:
        memory, mug, book = two_entity_memory()
        memory = step(memory, "f2", [{"atom": "NOOP", "entity_id": mug}], limit=1)
        self.assertEqual(entity_of(memory, mug)["state"], "dormant")
        gone = self._evaluate(memory, {"obj:mug": box([0.0, 0.0, 0.0], present=False), "obj:book": box([1.0, 0.0, 0.0])})
        self.assertEqual(gone["predicted"], 2)
        self.assertAlmostEqual(gone["node_precision"], 0.5)
        self.assertEqual(gone["stale_entities"], [mug])
        retracted = step(memory, "f3", [{"atom": "RETRACT", "entity_id": mug}])
        cleared = self._evaluate(retracted, {"obj:mug": box([0.0, 0.0, 0.0], present=False), "obj:book": box([1.0, 0.0, 0.0])})
        self.assertEqual(cleared["predicted"], 1)
        self.assertAlmostEqual(cleared["node_precision"], 1.0)
        self.assertEqual(cleared["stale_entities"], [])

    def test_the_evaluator_ignores_surface_ids(self) -> None:
        memory, mug, book = two_entity_memory()
        truth = {"obj:mug": box([0.0, 0.0, 0.0]), "obj:book": box([1.0, 0.0, 0.0])}
        baseline = self._evaluate(memory, truth)
        # Same geometry, but every entity now carries a surface id set by the executor.
        with_surface = step(empty_memory(episode_id="ep-0001"), "f1", [
            {"atom": "BIRTH", "fragment": {**frag("region:0000", descriptor=[1.0, 0.0], centroid=[0.0, 0.0, 0.0]), "supported_by": "surface:7"}},
            {"atom": "BIRTH", "fragment": {**frag("region:0001", descriptor=[0.0, 1.0], centroid=[1.0, 0.0, 0.0]), "supported_by": "surface:9"}},
        ])
        self.assertEqual({e["supported_by"] for e in with_surface["entities"]}, {"surface:7", "surface:9"})
        out = self._evaluate(with_surface, truth)
        for key in ("node_precision", "node_recall", "node_f1", "matched", "predicted", "truth", "contamination_fraction"):
            self.assertEqual(out[key], baseline[key], key)

    def test_out_of_scope_objects_are_neither_truth_nodes_nor_stale(self) -> None:
        """D-224-X ruling X6: the table carries in_scope; the evaluator applies the scope."""

        memory, mug, book = two_entity_memory()
        truth = {"obj:mug": box([0.0, 0.0, 0.0]), "obj:book": box([1.0, 0.0, 0.0], in_scope=False)}
        out = self._evaluate(memory, truth)
        self.assertEqual(out["truth"], 1)
        # Review correction (LOG-225): the book's entity resolves to a present
        # object outside the scope, so it leaves the precision denominator too.
        self.assertEqual(out["predicted"], 1)
        self.assertAlmostEqual(out["node_precision"], 1.0)
        self.assertEqual(out["out_of_scope_entities"], [book])
        self.assertEqual(out["stale_entities"], [])
        self.assertEqual(out["wrongly_absent_objects"], [])
        self.assertAlmostEqual(out["contamination_fraction"], 0.0)
        # An absent out-of-scope object still makes its entity stale.
        gone = self._evaluate(memory, {"obj:mug": box([0.0, 0.0, 0.0]), "obj:book": box([1.0, 0.0, 0.0], present=False, in_scope=False)})
        self.assertEqual(gone["stale_entities"], [book])
        with self.assertRaises(LeanTeacherError) as caught:
            self._evaluate(memory, {"obj:mug": box([0.0, 0.0, 0.0])})
        self.assertIn("truth_object_unknown", str(caught.exception))
        with self.assertRaises(LeanTeacherError) as caught:
            self._evaluate(memory, {"obj:mug": {"present": True, "centroid_m": [0.0, 0.0, 0.0], "aabb_min_m": [-0.1] * 3, "aabb_max_m": [0.1] * 3}, "obj:book": box([1.0, 0.0, 0.0])})
        self.assertIn("truth_object_in_scope_invalid", str(caught.exception))

    def test_empty_frames_report_none_not_zero(self) -> None:
        out = evaluate_frame(
            empty_memory(episode_id="ep-0002"), truth_objects={}, evidence_instance={},
            iou_min=IOU_MIN, delta_moved_m=DELTA,
        )
        self.assertIsNone(out["node_precision"])
        self.assertIsNone(out["node_recall"])
        self.assertIsNone(out["node_f1"])


class TestLifecycleMetrics(unittest.TestCase):
    def test_missing_residual_counts_stale_old_positions_including_dormant(self) -> None:
        memory, mug, book = two_entity_memory()
        memory = step(memory, "f2", [{"atom": "NOOP", "entity_id": mug}], limit=1)
        out = missing_residual_rate(
            memory, evidence_instance=evidence_map(memory, KEYS),
            missing_objects={
                "obj:mug": {"old_centroid_m": [0.0, 0.0, 0.0], "old_place_observable_since_intervention": True},
                "obj:book": {"old_centroid_m": [9.0, 0.0, 0.0], "old_place_observable_since_intervention": True},
                "obj:lamp": {"old_centroid_m": [2.0, 0.0, 0.0], "old_place_observable_since_intervention": False},
            },
            delta_moved_m=DELTA,
        )
        self.assertAlmostEqual(out["missing_residual_rate"], 0.5)
        self.assertEqual(out["residual_keys"], ["obj:mug"])
        self.assertEqual((out["judged"], out["not_yet_observable"]), (2, 1))

    def test_a_retracted_entity_is_not_a_residual(self) -> None:
        memory, mug, _ = two_entity_memory()
        memory = step(memory, "f2", [{"atom": "RETRACT", "entity_id": mug}])
        out = missing_residual_rate(
            memory, evidence_instance=evidence_map(memory, KEYS),
            missing_objects={"obj:mug": {"old_centroid_m": [0.0, 0.0, 0.0], "old_place_observable_since_intervention": True}},
            delta_moved_m=DELTA,
        )
        self.assertAlmostEqual(out["missing_residual_rate"], 0.0)

    def test_false_retract_rate(self) -> None:
        existence = {"e1": {"status": "present"}, "e2": {"status": "gone"}, "e3": {"status": "identity_ambiguous"}}
        out = false_retract_rate(existence, {"e1": "RETRACT", "e2": "RETRACT", "e3": "RETRACT"})
        self.assertAlmostEqual(out["false_retract_rate"], 0.5)
        self.assertEqual((out["judged_retracts"], out["ambiguous_retracts"]), (2, 1))
        none = false_retract_rate(existence, {"e1": "NOOP", "e2": "NOOP", "e3": "NOOP"})
        self.assertIsNone(none["false_retract_rate"])

    def test_identity_continuity_accepts_any_prior_carrier_and_not_a_birth(self) -> None:
        out = identity_continuity(
            reobserved={"obj:mug": "f1", "obj:book": "f2", "obj:lamp": "f3", "obj:pen": "f4"},
            carriers_before_move={"obj:mug": ["e1", "e1dup"], "obj:book": ["e2"], "obj:pen": ["e4"]},
            assignment={"f1": "e1dup", "f2": "birth:f2", "f3": "e5", "f4": "e9"},
        )
        self.assertAlmostEqual(out["identity_continuity"], 1 / 3)
        self.assertEqual((out["kept"], out["judged"], out["no_prior_carrier"]), (1, 3, 1))

    def test_object_memory_correct_for_the_three_intervention_kinds(self) -> None:
        memory, mug, book = two_entity_memory()
        evidence = evidence_map(memory, KEYS)
        removed = {"kind": "removed", "old_centroid_m": [0.0, 0.0, 0.0]}
        self.assertFalse(object_memory_correct(memory, evidence_instance=evidence, key="obj:mug", expectation=removed, delta_moved_m=DELTA))
        retracted = step(memory, "f2", [{"atom": "RETRACT", "entity_id": mug}])
        self.assertTrue(object_memory_correct(retracted, evidence_instance=evidence, key="obj:mug", expectation=removed, delta_moved_m=DELTA))
        moved = {"kind": "moved", "old_centroid_m": [0.0, 0.0, 0.0], "new_centroid_m": [3.0, 0.0, 0.0]}
        self.assertFalse(object_memory_correct(retracted, evidence_instance=evidence, key="obj:mug", expectation=moved, delta_moved_m=DELTA))
        reactivated = step(retracted, "f3", [
            {"atom": "REACTIVATE", "entity_id": mug, "fragment": frag("region:0010", descriptor=[1.0, 0.0], centroid=[3.0, 0.0, 0.0])},
        ])
        evidence = evidence_map(reactivated, {**KEYS, "region:0010": "obj:mug"})
        self.assertTrue(object_memory_correct(reactivated, evidence_instance=evidence, key="obj:mug", expectation=moved, delta_moved_m=DELTA))
        added = {"kind": "added", "new_centroid_m": [1.0, 0.0, 0.0]}
        self.assertTrue(object_memory_correct(reactivated, evidence_instance=evidence, key="obj:book", expectation=added, delta_moved_m=DELTA))

    def test_recovery_latency_starts_at_first_observable_frame(self) -> None:
        frames = [
            {"obj:mug": {"observable": False, "correct": False}, "obj:pen": {"observable": False, "correct": False}},
            {"obj:mug": {"observable": True, "correct": False}, "obj:book": {"observable": True, "correct": False}, "obj:pen": {"observable": False, "correct": True}},
            {"obj:mug": {"observable": True, "correct": False}, "obj:book": {"observable": False, "correct": False}, "obj:pen": {"observable": False, "correct": True}},
            {"obj:mug": {"observable": True, "correct": True}, "obj:book": {"observable": False, "correct": False}, "obj:pen": {"observable": False, "correct": True}},
        ]
        out = episode_recovery_latency(frames)
        self.assertEqual(out["per_object"]["obj:mug"], 2)
        self.assertIsNone(out["per_object"]["obj:book"])
        self.assertEqual(out["unrecovered"], ["obj:book"])
        self.assertEqual(out["never_observable"], ["obj:pen"])
        self.assertAlmostEqual(out["recovery_latency_frames"], 2.0)
        self.assertEqual(out["recovered"], 1)

    def test_contamination_auc_is_the_trapezoid_area(self) -> None:
        self.assertAlmostEqual(contamination_auc([0.0, 0.5, 0.5, 0.0])["contamination_auc"], (0.25 + 0.5 + 0.25) / 3)
        self.assertAlmostEqual(contamination_auc([0.4])["contamination_auc"], 0.4)
        self.assertIsNone(contamination_auc([])["contamination_auc"])
        with self.assertRaises(LeanTeacherError):
            contamination_auc([1.5])

    def test_size_and_cost(self) -> None:
        memory, mug, _ = two_entity_memory()
        memory = step(memory, "f2", [{"atom": "RETRACT", "entity_id": mug}])
        out = size_and_cost(memory, runtime_per_frame_s=0.02, peak_memory_bytes=1024)
        self.assertEqual(out, {"active_entity_count": 1, "lifecycle_version_count": 3, "runtime_per_frame_s": 0.02, "peak_memory_bytes": 1024})
        # Three BINDs open three more versions but no lifecycle version (D-224-X X6).
        bound = memory
        for index, seed in enumerate(("f3", "f4", "f5")):
            active = [e["entity_id"] for e in bound["entities"] if e["state"] == "active"][0]
            bound = step(bound, seed, [{"atom": "BIND", "entity_id": active,
                                        "fragment": frag(f"region:001{index}", descriptor=[0.0, 1.0], centroid=[1.0, 0.0, 0.0])}])
        self.assertEqual(sum(len(e["versions"]) for e in bound["entities"]), 6)
        self.assertEqual(size_and_cost(bound, runtime_per_frame_s=0.0, peak_memory_bytes=0)["lifecycle_version_count"], 3)
        with self.assertRaises(LeanTeacherError):
            size_and_cost(memory, runtime_per_frame_s=-1.0, peak_memory_bytes=1024)

    def test_micro_average(self) -> None:
        records = [{"matched": 1, "predicted": 2}, {"matched": 3, "predicted": 4}]
        self.assertAlmostEqual(micro_average(records, numerator="matched", denominator="predicted"), 4 / 6)
        self.assertIsNone(micro_average([], numerator="matched", denominator="predicted"))


class TestReportClosure(unittest.TestCase):
    def test_the_seven_metrics_pass(self) -> None:
        report = {name: {field: None for field in METRIC_FIELDS[name]} for name in METRICS}
        assert_report_keys(report)
        self.assertEqual(len(METRICS), 7)

    def test_an_eighth_metric_is_rejected(self) -> None:
        with self.assertRaises(LeanTeacherError) as caught:
            assert_report_keys({"composite_score": {"value": 1.0}})
        self.assertEqual(str(caught.exception), "report_metric_outside_frozen_list:composite_score")

    def test_an_extra_field_is_rejected(self) -> None:
        with self.assertRaises(LeanTeacherError) as caught:
            assert_report_keys({"node_prf1": {"node_precision": 1.0, "node_map": 0.5}})
        self.assertEqual(str(caught.exception), "report_field_outside_frozen_list:node_prf1.node_map")


class TestStatistics(unittest.TestCase):
    def _houses(self) -> dict[str, dict[str, float]]:
        return {
            f"house-{index:03d}": {
                "VSMT-lean": 0.10 + 0.01 * (index % 3), "TAF": 0.30 + 0.02 * (index % 5),
                "LOW": 0.25 + 0.02 * (index % 4), "NoVersion": 0.20 + 0.01 * (index % 2),
            }
            for index in range(20)
        }

    def test_bootstrap_is_deterministic_and_direction_aware(self) -> None:
        first = paired_house_bootstrap(self._houses(), arm="VSMT-lean", control="TAF", iterations=500, seed=11, direction="lower")
        second = paired_house_bootstrap(self._houses(), arm="VSMT-lean", control="TAF", iterations=500, seed=11, direction="lower")
        self.assertEqual(first, second)
        self.assertGreater(first["lower_bound_one_sided"], 0.0)
        flipped = paired_house_bootstrap(self._houses(), arm="VSMT-lean", control="TAF", iterations=500, seed=11, direction="higher")
        self.assertLess(flipped["lower_bound_one_sided"], 0.0)
        self.assertEqual(BOOTSTRAP_ITERATIONS, 10000)

    def test_a_house_missing_an_arm_breaks_the_pairing_and_is_rejected(self) -> None:
        houses = self._houses()
        del houses["house-003"]["TAF"]
        with self.assertRaises(LeanTeacherError) as caught:
            paired_house_bootstrap(houses, arm="VSMT-lean", control="TAF", iterations=10, seed=0, direction="lower")
        self.assertEqual(str(caught.exception), "bootstrap_house_missing_arm:house-003")

    def test_bootstrap_needs_two_paired_houses(self) -> None:
        with self.assertRaises(LeanTeacherError) as caught:
            paired_house_bootstrap({"h": {"VSMT-lean": 1.0, "TAF": 2.0}}, arm="VSMT-lean", control="TAF", iterations=10, seed=0, direction="lower")
        self.assertEqual(str(caught.exception), "bootstrap_needs_two_houses")

    def test_an_undefined_house_is_excluded_for_every_arm_and_counted(self) -> None:
        """D-224-X ruling X2."""

        houses = self._houses()
        houses["house-004"]["TAF"] = None
        houses["house-009"]["VSMT-lean"] = None
        excluded = undefined_houses(houses, arms=["VSMT-lean", "TAF", "LOW", "NoVersion"])
        self.assertEqual(excluded, ["house-004", "house-009"])
        out = paired_house_bootstrap(houses, arm="VSMT-lean", control="LOW", iterations=50, seed=1, direction="lower", excluded_houses=excluded)
        self.assertEqual(out["houses"], 18)
        self.assertEqual(out["excluded_undefined"], 2)
        self.assertEqual(out["excluded_houses"], ["house-004", "house-009"])
        with self.assertRaises(LeanTeacherError) as caught:
            paired_house_bootstrap(houses, arm="VSMT-lean", control="TAF", iterations=50, seed=1, direction="lower")
        self.assertEqual(str(caught.exception), "bootstrap_house_metric_undefined:house-004")
        with self.assertRaises(LeanTeacherError) as caught:
            strongest_control(houses, controls=["TAF", "LOW"], direction="lower")
        self.assertEqual(str(caught.exception), "bootstrap_house_metric_undefined:house-004")
        self.assertEqual(strongest_control(houses, controls=["TAF", "LOW"], direction="lower", excluded_houses=excluded), "LOW")
        report = ablation_report(houses, direction="lower", seed=3, iterations=20, ablations=["NoVersion"], excluded_houses=excluded)
        self.assertEqual(report["per_ablation"]["NoVersion"]["excluded_undefined"], 2)
        missing = self._houses()
        del missing["house-002"]["LOW"]
        with self.assertRaises(LeanTeacherError) as caught:
            undefined_houses(missing, arms=["VSMT-lean", "LOW"])
        self.assertEqual(str(caught.exception), "bootstrap_house_missing_arm:house-002")

    def test_a_metric_undefined_by_construction_excludes_only_the_applicable_arms(self) -> None:
        """Review correction (LOG-225): never-retracting arms report false_retract_rate as not applicable."""

        self.assertEqual(METRIC_NOT_APPLICABLE_RULE["false_retract_rate"], "arms_whose_vocabulary_lacks_RETRACT")
        houses = self._houses()
        for house in houses:
            houses[house]["TAF"] = None  # TAF never retracts: undefined in every house
        # Without the carve-out every house is excluded and nothing can be paired.
        self.assertEqual(len(undefined_houses(houses, arms=["VSMT-lean", "TAF", "LOW", "NoVersion"])), 20)
        excluded = undefined_houses(houses, arms=["VSMT-lean", "TAF", "LOW", "NoVersion"], not_applicable=["TAF"])
        self.assertEqual(excluded, [])
        out = paired_house_bootstrap(houses, arm="VSMT-lean", control="LOW", iterations=50, seed=1, direction="lower", excluded_houses=excluded, not_applicable=["TAF"])
        self.assertEqual(out["houses"], 20)
        with self.assertRaises(LeanTeacherError) as caught:
            paired_house_bootstrap(houses, arm="VSMT-lean", control="TAF", iterations=50, seed=1, direction="lower", not_applicable=["TAF"])
        self.assertEqual(str(caught.exception), "bootstrap_arm_not_applicable:TAF")
        self.assertEqual(strongest_control(houses, controls=["TAF", "LOW"], direction="lower", not_applicable=["TAF"]), "LOW")
        with self.assertRaises(LeanTeacherError):
            strongest_control(houses, controls=["TAF"], direction="lower", not_applicable=["TAF"])
        report = ablation_report(houses, direction="lower", seed=3, iterations=20, ablations=["NoVersion", "TAF"], not_applicable=["TAF"])
        self.assertEqual(report["per_ablation"]["TAF"], {"not_applicable": True})
        self.assertEqual(report["per_ablation"]["NoVersion"]["houses"], 20)
        with self.assertRaises(LeanTeacherError):
            undefined_houses(houses, arms=["TAF"], not_applicable=["TAF"])

    def test_the_strongest_control_is_picked_per_direction(self) -> None:
        self.assertEqual(strongest_control(self._houses(), controls=["TAF", "LOW"], direction="lower"), "LOW")
        self.assertEqual(strongest_control(self._houses(), controls=["TAF", "LOW"], direction="higher"), "TAF")

    def test_main_gate_requires_both_metrics(self) -> None:
        self.assertTrue(main_gate({"missing_residual_rate": 0.02, "identity_continuity": 0.05})["passed"])
        self.assertFalse(main_gate({"missing_residual_rate": 0.02, "identity_continuity": -0.01})["passed"])
        with self.assertRaises(LeanTeacherError):
            main_gate({"missing_residual_rate": 0.02})

    def test_ablations_are_reported_not_gated(self) -> None:
        out = ablation_report(self._houses(), direction="lower", seed=3, iterations=50, ablations=["NoVersion"])
        self.assertFalse(out["gated"])
        self.assertEqual(out["in_main_table"], ["AssocOnly"])
        self.assertEqual(out["per_ablation"]["NoVersion"]["arm"], "VSMT-lean")
        self.assertEqual(ABLATION_ARMS, ("NoVersion", "HandCost", "HeuristicLabel", "AssocOnly"))


class TestNuisanceProbe(unittest.TestCase):
    def _records(self) -> list[dict[str, Any]]:
        return [
            {
                "frame_index": index % 2, "path": "p", "seed": 7, "house_index": index // 10,
                "association_status": "labelled" if index % 3 else "birth",
                "association_target_is_birth": index % 3 == 0,
                "existence_status": "gone" if index % 2 else "present",
            }
            for index in range(20)
        ]

    def test_a_leaking_field_beats_the_majority(self) -> None:
        out = nuisance_probe(self._records(), field="frame_index", label="existence_status")
        self.assertGreater(out["advantage"], 0.3)
        clean = nuisance_probe(self._records(), field="path", label="existence_status")
        self.assertLessEqual(clean["advantage"], 0.0)

    def test_every_field_is_probed_against_every_label(self) -> None:
        out = run_nuisance_probes(self._records())
        self.assertEqual(set(out["per_label"]), {"association_status", "association_target_is_birth", "existence_status"})
        for probes in out["per_label"].values():
            self.assertEqual(tuple(probes), NUISANCE_FIELDS)
        self.assertGreater(out["largest_advantage"], 0.3)

    def test_an_unknown_field_is_rejected(self) -> None:
        with self.assertRaises(LeanTeacherError) as caught:
            nuisance_probe([{"x": 1, "label": "a"}, {"x": 2, "label": "b"}], field="x", label="label")
        self.assertEqual(str(caught.exception), "nuisance_field_unknown")


class TestMachineContract(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def _fresh(self) -> dict[str, Any]:
        return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    @staticmethod
    def _set(contract: dict[str, Any], path: str, value: Any) -> None:
        node = contract
        parts = path.split(".")
        for part in parts[:-1]:
            node = node[part]
        node[parts[-1]] = value

    def test_contract_agrees_with_the_implementation(self) -> None:
        validate_teacher_contract(self.contract)
        self.assertEqual(self.contract["schema_version"], CONTRACT_SCHEMA_VERSION)
        self.assertEqual(tuple(self.contract["metrics"]["names"]), METRICS)
        self.assertEqual(tuple(self.contract["decomposition"]["classes"]), DECOMPOSITION)
        self.assertEqual(tuple(self.contract["labels"]["association_statuses"]), ASSOCIATION_STATUSES)
        self.assertEqual(tuple(self.contract["labels"]["existence_statuses"]), EXISTENCE_STATUSES)
        self.assertEqual(tuple(self.contract["nuisance_probe"]["fields"]), NUISANCE_FIELDS)
        self.assertEqual(tuple(tuple(item) for item in self.contract["statistics"]["main_gate"]), MAIN_GATE)
        self.assertEqual(len(self.contract["authorization"]), 6)

    def test_the_truth_box_source_is_bound_to_ruling_45(self) -> None:
        # D-224-S1 ruling 45 (2026-09-22): the per-frame private record never carried a box, so
        # the truth box is the simulator's initial box translated by the recorded position; the
        # observed-set box is only a comparison column.
        from vsmt.lean_teacher import TRUTH_BOX_SOURCE

        source = self.contract["private_truth_inputs"]["truth_box_source"]
        self.assertEqual(source["rule"], TRUTH_BOX_SOURCE)
        self.assertEqual(TRUTH_BOX_SOURCE, "simulator_initial_axis_aligned_box_plus_recorded_translation")
        self.assertTrue(source["boxes_are_in_the_episode_frame"])
        self.assertTrue(source["observed_set_box_is_a_proxy_reported_only_as_a_comparison_column"])
        broken = self._fresh()
        self._set(broken, "private_truth_inputs.truth_box_source.rule", "observed_set_box")
        with self.assertRaises(LeanTeacherError) as caught:
            validate_teacher_contract(broken)
        self.assertEqual(str(caught.exception), "contract_truth_box_source_mismatch")

    def test_flipping_any_boolean_claim_is_rejected(self) -> None:
        self.assertGreaterEqual(len(EXPECTED_BOOLEAN_CLAIMS), 40)
        for path, expected in EXPECTED_BOOLEAN_CLAIMS.items():
            broken = self._fresh()
            self._set(broken, path, not expected)
            with self.assertRaises(LeanTeacherError, msg=path) as caught:
                validate_teacher_contract(broken)
            self.assertEqual(str(caught.exception), f"contract_claim_flipped:{path}", path)

    def test_an_unbound_boolean_claim_is_rejected(self) -> None:
        broken = self._fresh()
        broken["metrics"]["dormant_may_be_dropped_quietly"] = True
        with self.assertRaises(LeanTeacherError) as caught:
            validate_teacher_contract(broken)
        self.assertEqual(str(caught.exception), "contract_unbound_boolean_claim:metrics.dormant_may_be_dropped_quietly")

    def test_a_missing_boolean_claim_is_rejected(self) -> None:
        broken = self._fresh()
        del broken["metrics"]["no_composite_score"]
        with self.assertRaises(LeanTeacherError) as caught:
            validate_teacher_contract(broken)
        self.assertEqual(str(caught.exception), "contract_missing_boolean_claim:metrics.no_composite_score")

    def test_adding_an_eighth_metric_is_rejected(self) -> None:
        broken = self._fresh()
        broken["metrics"]["names"] = list(broken["metrics"]["names"]) + ["composite_score"]
        with self.assertRaises(LeanTeacherError) as caught:
            validate_teacher_contract(broken)
        self.assertEqual(str(caught.exception), "contract_metric_names_mismatch")

    def test_adding_a_reported_field_is_rejected(self) -> None:
        broken = self._fresh()
        broken["metrics"]["reported_fields"]["node_prf1"].append("node_map")
        with self.assertRaises(LeanTeacherError) as caught:
            validate_teacher_contract(broken)
        self.assertEqual(str(caught.exception), "contract_metric_fields_mismatch")

    def test_changing_a_decision_frozen_constant_is_rejected(self) -> None:
        for path in ("metrics.node_prf1.iou_min", "statistics.bootstrap_iterations", "statistics.confidence_one_sided"):
            broken = self._fresh()
            self._set(broken, path, 0.25)
            with self.assertRaises(LeanTeacherError) as caught:
                validate_teacher_contract(broken)
            self.assertEqual(str(caught.exception), f"contract_frozen_constant_mismatch:{path}")
        self.assertEqual(IOU_MIN, 0.3)

    def test_policy_values_must_still_be_null(self) -> None:
        self.assertEqual(len(NULL_POLICY_PATHS), 5)
        for path in NULL_POLICY_PATHS:
            broken = self._fresh()
            self._set(broken, path, 0.5)
            with self.assertRaises(LeanTeacherError) as caught:
                validate_teacher_contract(broken)
            self.assertIn("must_be_null_before_freeze", str(caught.exception))

    def test_changing_the_candidate_or_present_state_sets_is_rejected(self) -> None:
        broken = self._fresh()
        broken["metrics"]["memory_present_states"] = ["active"]
        with self.assertRaises(LeanTeacherError) as caught:
            validate_teacher_contract(broken)
        self.assertEqual(str(caught.exception), "contract_memory_present_states_mismatch")
        broken = self._fresh()
        broken["labels"]["existence"]["candidate_states"] = ["active", "dormant", "retracted"]
        with self.assertRaises(LeanTeacherError) as caught:
            validate_teacher_contract(broken)
        self.assertEqual(str(caught.exception), "contract_existence_candidate_states_mismatch")

    def test_the_rulings_decision_is_bound(self) -> None:
        broken = self._fresh()
        broken["user_rulings"]["decision_id"] = "D-224-XX"
        with self.assertRaises(LeanTeacherError) as caught:
            validate_teacher_contract(broken)
        self.assertEqual(str(caught.exception), "contract_rulings_decision_mismatch")
        broken = self._fresh()
        del broken["user_rulings"]["L"]
        with self.assertRaises(LeanTeacherError) as caught:
            validate_teacher_contract(broken)
        self.assertEqual(str(caught.exception), "contract_rulings_incomplete")
        self.assertEqual(RULINGS_DECISION_ID, "D-224-LQ")

    def test_every_authorization_bit_is_false_and_the_set_is_fixed(self) -> None:
        broken = self._fresh()
        broken["authorization"]["test_split_read"] = True
        with self.assertRaises(LeanTeacherError) as caught:
            validate_teacher_contract(broken)
        self.assertEqual(str(caught.exception), "contract_claim_flipped:authorization.test_split_read")
        broken = self._fresh()
        broken["authorization"]["data_generation"] = False
        with self.assertRaises(LeanTeacherError) as caught:
            validate_teacher_contract(broken)
        self.assertEqual(str(caught.exception), "contract_unbound_boolean_claim:authorization.data_generation")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
