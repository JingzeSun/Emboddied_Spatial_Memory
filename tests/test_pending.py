from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from cpmt.errors import ContractError, PreconditionError  # noqa: E402
from cpmt.hashing import seal_graph  # noqa: E402
from cpmt.pending import (  # noqa: E402
    consume_pending,
    create_pending_store,
    decide_commit,
    quarantine_evidence,
    register_relevant_opportunity,
    retrieve_pending,
    validate_commit_decision,
    validate_pending_store,
)


FIXTURE_ROOT = (
    PROJECT_ROOT
    / "experiments"
    / "counterfactual_transaction_learning"
    / "fixtures"
    / "draft"
    / "C09"
)


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_decision() -> dict:
    return load_json(FIXTURE_ROOT / "commit" / "uncertain.json")


def load_evidence() -> dict:
    return load_json(
        FIXTURE_ROOT / "evidence" / "ambiguous-chair-t5.json"
    )


def load_program(filename: str = "noop.json") -> dict:
    return load_json(FIXTURE_ROOT / "transactions" / filename)


def build_pending() -> dict:
    return quarantine_evidence(
        create_pending_store("pending-C09"),
        pending_id="trace-chair-uncertain",
        decision=load_decision(),
        evidence_event=load_evidence(),
        latent_ref="latent:C09:coarse-chair-like",
        spatial_ref="space:C09:left-or-right",
        semantic_hints=["chair-like", "furniture"],
        provenance_ref="fixture:C09:quarantine",
    )


class CommitDecisionTests(unittest.TestCase):
    def test_fixture_decision_quarantines_ambiguous_posteriors(
        self,
    ) -> None:
        expected = load_decision()
        actual = decide_commit(
            expected["candidate_posteriors"],
            decision_id=expected["decision_id"],
            at=expected["at"],
            commit_probability=expected["commit_probability"],
            margin_threshold=expected["margin_threshold"],
        )
        self.assertEqual(actual, expected)
        self.assertIsNone(actual["selected_candidate_id"])
        validate_commit_decision(actual)

    def test_confident_posterior_commits_top_candidate(self) -> None:
        decision = decide_commit(
            {"bind": 0.9, "birth": 0.1},
            decision_id="decision-confident",
            at=5,
            commit_probability=0.7,
            margin_threshold=0.15,
        )
        self.assertEqual(decision["action"], "COMMIT")
        self.assertEqual(decision["selected_candidate_id"], "bind")
        self.assertEqual(decision["reasons"], [])

    def test_invalid_posterior_mass_is_rejected(self) -> None:
        with self.assertRaises(ContractError):
            decide_commit(
                {"bind": 0.8, "birth": 0.8},
                decision_id="decision-invalid",
                at=5,
                commit_probability=0.7,
                margin_threshold=0.15,
            )

    def test_serialized_action_cannot_override_recomputed_gate(
        self,
    ) -> None:
        forged = load_decision()
        forged["action"] = "COMMIT"
        forged["selected_candidate_id"] = "transactions/noop.json"
        with self.assertRaises(ContractError):
            validate_commit_decision(forged)


class PendingMemoryTests(unittest.TestCase):
    def test_quarantine_keeps_weak_cognition_outside_world(self) -> None:
        world = seal_graph(load_json(FIXTURE_ROOT / "world.json"))
        before = deepcopy(world)
        store = build_pending()
        validate_pending_store(store)

        self.assertEqual(world, before)
        self.assertEqual(len(store["records"]), 1)
        record = store["records"][0]
        self.assertEqual(record["status"], "active_pending")
        self.assertAlmostEqual(record["effective_support"], 0.08)
        self.assertIn(
            "latent:C09:coarse-chair-like",
            record["retrieval"]["latent_refs"],
        )
        self.assertEqual(record["retrieval"]["spatial_refs"], [])
        self.assertEqual(
            set(record["retrieval"]["semantic_hints"]),
            {"chair-like", "furniture"},
        )

    def test_duplicate_time_view_is_retained_without_extra_support(
        self,
    ) -> None:
        store = build_pending()
        event = load_evidence()
        event["evidence_id"] = "obs:C09:t5:duplicate-region"
        event["reliability"] = 0.9
        decision = load_decision()
        decision["decision_id"] = "decision:C09:t6:duplicate"
        decision["at"] = 6

        result = quarantine_evidence(
            store,
            pending_id="trace-chair-uncertain",
            decision=decision,
            evidence_event=event,
            latent_ref="latent:C09:coarse-chair-like",
            spatial_ref="space:C09:left-or-right",
            semantic_hints=["chair-like"],
            provenance_ref="fixture:C09:duplicate-view",
        )

        record = result["records"][0]
        self.assertEqual(len(record["evidence"]), 2)
        self.assertEqual(
            record["evidence"][1]["independence_weight"],
            0.0,
        )
        self.assertEqual(
            record["evidence"][1]["decision_weight"],
            0.0,
        )
        self.assertAlmostEqual(record["effective_support"], 0.08)

    def test_nonopportunities_do_not_consume_budget(self) -> None:
        store = build_pending()
        for relevant, can_disambiguate in (
            (False, True),
            (True, False),
        ):
            unchanged = register_relevant_opportunity(
                store,
                pending_id="trace-chair-uncertain",
                opportunity_id=(
                    f"opportunity-{relevant}-{can_disambiguate}"
                ),
                at=6,
                relevant=relevant,
                can_disambiguate=can_disambiguate,
                decision_still_unresolved=True,
                opportunity_budget=2,
            )
            self.assertEqual(unchanged, store)

        once = register_relevant_opportunity(
            store,
            pending_id="trace-chair-uncertain",
            opportunity_id="opportunity-valid-1",
            at=6,
            relevant=True,
            can_disambiguate=True,
            decision_still_unresolved=True,
            opportunity_budget=2,
        )
        self.assertEqual(
            once["records"][0]["status"],
            "active_pending",
        )
        archived = register_relevant_opportunity(
            once,
            pending_id="trace-chair-uncertain",
            opportunity_id="opportunity-valid-2",
            at=7,
            relevant=True,
            can_disambiguate=True,
            decision_still_unresolved=True,
            opportunity_budget=2,
        )
        self.assertEqual(
            archived["records"][0]["status"],
            "archived_unresolved",
        )
        self.assertEqual(len(archived["records"][0]["evidence"]), 1)

    def test_archived_trace_is_searchable_and_can_reactivate(self) -> None:
        store = build_pending()
        archived = store
        for index in (1, 2):
            archived = register_relevant_opportunity(
                archived,
                pending_id="trace-chair-uncertain",
                opportunity_id=f"opportunity-{index}",
                at=5 + index,
                relevant=True,
                can_disambiguate=True,
                decision_still_unresolved=True,
                opportunity_budget=2,
            )
        matches = retrieve_pending(
            archived,
            latent_ref="latent:C09:coarse-chair-like",
            semantic_hints=["chair-like"],
        )
        self.assertEqual(matches[0]["status"], "archived_unresolved")

        event = load_evidence()
        event.update(
            {
                "evidence_id": "obs:C09:t8:chair-like",
                "time_index": 8,
                "viewpoint_id": "view:C09:valid-revisit",
                "reliability": 0.2,
                "pose_valid": True,
                "depth_valid": True,
                "visibility": "visible",
            }
        )
        decision = decide_commit(
            {"transactions/noop.json": 0.55,
             "transactions/relink.json": 0.45},
            decision_id="decision:C09:t8:still-uncertain",
            at=8,
            commit_probability=0.7,
            margin_threshold=0.15,
        )
        reactivated = quarantine_evidence(
            archived,
            pending_id="trace-chair-uncertain",
            decision=decision,
            evidence_event=event,
            latent_ref="latent:C09:coarse-chair-like",
            spatial_ref="space:C09:right",
            semantic_hints=["chair-like"],
            provenance_ref="fixture:C09:revisit",
        )
        record = reactivated["records"][0]
        self.assertEqual(record["status"], "active_pending")
        self.assertEqual(record["reactivation_count"], 1)
        self.assertEqual(len(record["archive_history"]), 1)
        self.assertEqual(record["opportunity_cycle"], 1)
        self.assertEqual(record["relevant_opportunity_ids"], [])
        self.assertEqual(len(record["opportunity_history"]), 2)
        self.assertIn(
            "space:C09:right",
            record["retrieval"]["spatial_refs"],
        )

    def test_consumption_requires_all_evidence_and_keeps_audit(
        self,
    ) -> None:
        store = build_pending()
        program = load_program()
        missing = deepcopy(program)
        missing["evidence_refs"] = []

        with self.assertRaises(PreconditionError):
            consume_pending(
                store,
                pending_id="trace-chair-uncertain",
                transaction_program=missing,
                at=8,
            )

        consumed = consume_pending(
            store,
            pending_id="trace-chair-uncertain",
            transaction_program=program,
            at=8,
        )
        record = consumed["records"][0]
        self.assertEqual(record["status"], "consumed")
        self.assertEqual(
            record["consumed_by_transaction"],
            "tx-C09-noop-pose-fault",
        )
        self.assertEqual(len(record["evidence"]), 1)
        self.assertIn(
            "tx-C09-noop-pose-fault",
            record["provenance"],
        )
        self.assertEqual(
            retrieve_pending(
                consumed,
                latent_ref="latent:C09:coarse-chair-like",
            ),
            [],
        )

    def test_duplicate_evidence_is_rejected_atomically(self) -> None:
        store = build_pending()
        before = deepcopy(store)

        with self.assertRaises(PreconditionError):
            quarantine_evidence(
                store,
                pending_id="trace-chair-uncertain",
                decision=load_decision(),
                evidence_event=load_evidence(),
                latent_ref="latent:C09:coarse-chair-like",
                spatial_ref=None,
                semantic_hints=["chair-like"],
                provenance_ref="fixture:C09:duplicate",
            )
        self.assertEqual(store, before)


if __name__ == "__main__":
    unittest.main()
