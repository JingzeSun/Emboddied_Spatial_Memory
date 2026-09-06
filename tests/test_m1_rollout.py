"""Integrity tests for procedural, causally chained M1 rollouts."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from cpmt.hashing import canonical_json
from cpmt.m1_data import validate_online_payload
from cpmt.m1_metrics import rollout_graph_metrics
from cpmt.m1_rollout import (
    CANDIDATE_BUDGET,
    ROLLOUT_TEMPLATE_COUNTS,
    audit_m1_candidate_coverage,
    execute_rollout_choices,
    generate_fixed_candidates,
    generate_m1_paired_rollout_split,
    generate_m1_rollout_split,
    records_sha256,
)


class TestM1ContinuousRollout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(
            (PROJECT / "configs" / "m1_hard_condition.json").read_text(
                encoding="utf-8"
            )
        )
        cls.online, cls.audit, cls.summary = generate_m1_rollout_split(
            cls.config, "validation", sequences=3,
        )

    def test_every_sequence_is_one_real_twenty_step_chain(self):
        self.assertEqual(self.summary["horizon_decisions"], 20)
        self.assertEqual(len(self.online), 60)
        for sequence in self.audit:
            self.assertEqual(len(sequence["steps"]), 20)
            previous_hash = sequence["initial_world"]["graph_hash"]
            for step in sequence["steps"]:
                self.assertEqual(step["online"]["prior_world"]["graph_hash"], previous_hash)
                reference = step["executed_candidates"][
                    step["reference_program_index"]
                ]
                self.assertTrue(reference["legal"])
                previous_hash = reference["post_graph_hash"]
            self.assertEqual(previous_hash, sequence["final_reference_graph_hash"])

    def test_registered_transactions_have_executable_positive_examples(self):
        for sequence in self.audit:
            counts = Counter(sequence["event_order"])
            self.assertEqual(dict(counts), ROLLOUT_TEMPLATE_COUNTS)
            for step in sequence["steps"]:
                reference = step["executed_candidates"][
                    step["reference_program_index"]
                ]
                self.assertTrue(reference["legal"])
                self.assertEqual(reference["template"], step["reference_template"])
        self.assertTrue({
            "NOOP", "BIND", "BIRTH", "REACTIVATE", "RELINK", "RETRACT",
            "SPLIT", "MERGE", "REPLACE",
        } <= set(self.audit[0]["event_order"]))

    def test_candidates_share_each_step_base_and_keep_illegal_failures(self):
        for sequence in self.audit:
            for step in sequence["steps"]:
                base_hashes = {
                    candidate["base_graph_hash"]
                    for candidate in step["executed_candidates"]
                }
                self.assertEqual(base_hashes, {
                    step["online"]["prior_world"]["graph_hash"]
                })
                illegal = [
                    candidate for candidate in step["executed_candidates"]
                    if not candidate["legal"]
                ]
                self.assertGreaterEqual(len(illegal), 1)
                self.assertIn(
                    "ProtectedMutationError",
                    {item["failure"]["type"] for item in illegal},
                )

    def test_fixed_k16_is_deduplicated_and_reference_blind(self):
        step = self.audit[0]["steps"][0]
        event = deepcopy(step["event_spec"])
        base = step["online"]["prior_world"]
        programs, _, generation = generate_fixed_candidates(base, event)
        self.assertEqual(len(programs), CANDIDATE_BUDGET)
        self.assertEqual(generation["budget_k"], 16)
        self.assertEqual(generation["canonical_duplicates_removed"], 0)
        self.assertFalse(generation["reference_fields_read"])
        self.assertEqual(
            {
                "REPLACE" if item["template"] == "COMPOSITE"
                else item["template"]
                for item in programs
            },
            {
                "NOOP", "BIND", "BIRTH", "REACTIVATE", "RELINK",
                "RETRACT", "SPLIT", "MERGE", "REPLACE",
            },
        )
        self.assertNotIn(
            "rollout:", canonical_json(event["proposal_observation"]),
        )
        changed = deepcopy(event)
        changed.pop("reference_spec")
        changed["scenario_family"] = "C11"
        changed_programs, _, _ = generate_fixed_candidates(base, changed)
        self.assertEqual(canonical_json(programs), canonical_json(changed_programs))

    def test_candidate_coverage_has_family_gates_and_keeps_test_sealed(self):
        rows, summary = audit_m1_candidate_coverage(
            self.config, "validation", paired_groups=1,
        )
        self.assertEqual(len(rows), 20)
        self.assertEqual(summary["candidate_budget_k"], 16)
        self.assertEqual(summary["candidate_reference_coverage"], 1.0)
        self.assertEqual(summary["minimum_family_coverage"], 1.0)
        self.assertTrue(summary["coverage_thresholds_met"])
        # Independence is measured, not asserted: an exact hash of the hidden
        # argument would let query similarity alone name the reference.
        decided = summary["reference_argument_decided_by_query"]
        self.assertIsNotNone(decided)
        self.assertGreaterEqual(decided, 0.0)
        self.assertLessEqual(decided, 1.0)
        self.assertNotIn("reference_arguments_independent", summary)
        self.assertEqual(
            summary["proposal_retrieval"],
            self.config["candidates"]["proposal_retrieval"],
        )
        self.assertFalse(summary["formal_gate_eligible"])
        self.assertFalse(summary["coverage_gate_pass"])
        self.assertFalse(summary["test_generated"])
        self.assertFalse(summary["training_run"])
        with self.assertRaisesRegex(ValueError, "test is sealed"):
            audit_m1_candidate_coverage(
                self.config, "test", paired_groups=1,
            )

    def test_hindsight_uses_real_later_reference_states_and_masks_tail(self):
        sequence = self.audit[0]
        expected_lengths = [3] * 18 + [2, 1]
        self.assertEqual(
            [len(step["future_trace"]) for step in sequence["steps"]],
            expected_lengths,
        )
        for step in sequence["steps"]:
            reference_index = step["reference_program_index"]
            energies = step["candidate_energies"]
            # The executed reference reproduces the actual future exactly, so
            # its raw future error is zero. The scored "future" is standardised
            # across candidates so the shared energy weight means the same for
            # every method, which makes the best candidate negative, not zero.
            self.assertEqual(energies[reference_index]["future_raw"], 0.0)
            legal_future = [
                energy["future"] for candidate, energy in zip(
                    step["executed_candidates"], energies, strict=True,
                )
                if candidate["legal"]
            ]
            self.assertEqual(
                energies[reference_index]["future"], min(legal_future),
            )
            # The teacher may disagree with the reference where two candidates
            # are nearly tied on future consistency and the minimal-change cost
            # decides. It is recorded, not asserted away; here the reference
            # reproduces the future exactly, so it must still win.
            self.assertEqual(step["teacher_winner_index"], reference_index)
            self.assertTrue(step["teacher_winner_matches_reference"])
            self.assertTrue(all(
                item["source"] == "actual_executed_reference_sequence"
                for item in step["future_trace"]
            ))
            self.assertTrue(any(
                energy["future_raw"] > 0
                for candidate, energy in zip(
                    step["executed_candidates"],
                    step["candidate_energies"],
                    strict=True,
                )
                if candidate["legal"] and candidate["candidate_index"] != reference_index
            ))
        counterfactual_failures = [
            failure
            for step in sequence["steps"]
            for energy in step["candidate_energies"]
            for failure in energy["counterfactual_rollout_failures"]
        ]
        self.assertTrue(counterfactual_failures)
        self.assertEqual(
            {item["fallback"] for item in counterfactual_failures},
            {"QUARANTINE_KEEP_CURRENT_WORLD"},
        )

    def test_counterfactual_reference_construction_failure_is_quarantined(self):
        _, audits, _ = generate_m1_paired_rollout_split(
            self.config, "train", paired_groups=1, start_group_index=4,
        )
        failures = [
            failure
            for audit in audits
            for step in audit["steps"]
            for energy in step["candidate_energies"]
            for failure in energy["counterfactual_rollout_failures"]
        ]
        self.assertTrue(any(
            failure["failure"].get("phase")
            == "REFERENCE_PROGRAM_CONSTRUCTION"
            for failure in failures
        ))
        self.assertEqual(
            {failure["fallback"] for failure in failures},
            {"QUARANTINE_KEEP_CURRENT_WORLD"},
        )

    def test_oracle_replay_rebuilds_on_previous_predicted_state(self):
        sequence = self.audit[0]
        reference_indices = [
            step["reference_program_index"] for step in sequence["steps"]
        ]
        replay = execute_rollout_choices(sequence, reference_indices)
        self.assertEqual(
            replay["states"][-1]["graph_hash"],
            sequence["final_reference_graph_hash"],
        )
        for index in range(1, 20):
            self.assertEqual(
                replay["decisions"][index]["base_graph_hash"],
                replay["states"][index - 1]["graph_hash"],
            )

    def test_one_wrong_relink_persists_as_rollout_contamination(self):
        sequence = self.audit[0]
        reference_indices = [
            step["reference_program_index"] for step in sequence["steps"]
        ]
        relink_index = next(
            index for index, step in enumerate(sequence["steps"])
            if step["reference_template"] == "RELINK"
        )
        wrong = list(reference_indices)
        wrong[relink_index] = next(
            candidate["candidate_index"]
            for candidate in sequence["steps"][relink_index]["executed_candidates"]
            if candidate["template"] == "NOOP" and candidate["legal"]
        )
        replay = execute_rollout_choices(sequence, wrong)
        references = [
            step["executed_candidates"][step["reference_program_index"]]["post_graph"]
            for step in sequence["steps"]
        ]
        protected = [
            [step["event_spec"]["protected_id"]]
            for step in sequence["steps"]
        ]
        metrics = rollout_graph_metrics(
            replay["states"], references, replay["base_states"], protected,
            horizon=20,
        )
        self.assertEqual(metrics["final_post_graph_correctness"], 0.0)
        self.assertGreater(metrics["memory_contamination_per_100"], 0.0)
        self.assertGreater(metrics["missing_open_facts_per_100"], 0.0)
        for index in range(relink_index + 1, 20):
            self.assertEqual(
                replay["decisions"][index]["base_graph_hash"],
                replay["states"][index - 1]["graph_hash"],
            )

    def test_topology_relationships_and_event_orders_vary_programmatically(self):
        signatures = {
            (
                sequence["topology"]["place_count"],
                sequence["topology"]["surface_count"],
                sequence["topology"]["filler_entity_count"],
                tuple(sequence["event_order"]),
            )
            for sequence in self.audit
        }
        self.assertEqual(len(signatures), 3)
        location_targets = []
        for sequence in self.audit:
            location_targets.append(tuple(sorted(
                edge["target"]
                for edge in sequence["initial_world"]["edges"]
                if edge["relation"] == "located_at"
            )))
        self.assertGreater(len(set(location_targets)), 1)

    def test_split_boundary_determinism_and_test_seal(self):
        train_online, train_audit, _ = generate_m1_rollout_split(
            self.config, "train", sequences=1,
        )
        validation_keys = {
            (sequence["world_seed"], sequence["asset_family"])
            for sequence in self.audit
        }
        train_keys = {
            (sequence["world_seed"], sequence["asset_family"])
            for sequence in train_audit
        }
        self.assertFalse(validation_keys & train_keys)
        self.assertFalse(
            {sequence["asset_family"] for sequence in self.audit}
            & {sequence["asset_family"] for sequence in train_audit}
        )
        repeated_online, repeated_audit, _ = generate_m1_rollout_split(
            self.config, "validation", sequences=3,
        )
        self.assertEqual(records_sha256(self.online), records_sha256(repeated_online))
        self.assertEqual(records_sha256(self.audit), records_sha256(repeated_audit))
        for online in self.online + train_online:
            validate_online_payload(online)
            self.assertEqual(len(online["candidate_programs"]), CANDIDATE_BUDGET)
            self.assertNotIn("reference", canonical_json(online))
            self.assertNotIn("future", canonical_json(online))
        with self.assertRaisesRegex(ValueError, "test is sealed"):
            generate_m1_rollout_split(self.config, "test", sequences=1)


class TestM1PairedContinuousRollout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(
            (PROJECT / "configs" / "m1_hard_condition.json").read_text(
                encoding="utf-8"
            )
        )
        cls.online, cls.audit, cls.summary = generate_m1_paired_rollout_split(
            cls.config, "validation", paired_groups=2,
        )

    def _groups(self):
        groups = {}
        for sequence in self.audit:
            groups.setdefault(sequence["paired_group_id"], []).append(sequence)
        return {
            key: sorted(value, key=lambda item: item["sibling_index"])
            for key, value in groups.items()
        }

    def test_pivot_has_exact_same_online_input_and_different_reference(self):
        self.assertTrue(self.summary["paired_latent_siblings_ready"])
        self.assertEqual(self.summary["exact_ambiguous_decision_pairs"], 2)
        for siblings in self._groups().values():
            self.assertEqual(len(siblings), 2)
            left, right = siblings
            pivot = left["ambiguity_pivot_step"]
            self.assertEqual(pivot, right["ambiguity_pivot_step"])
            self.assertEqual(
                canonical_json(left["initial_world"]),
                canonical_json(right["initial_world"]),
            )
            self.assertEqual(left["primary_event_order"], right["primary_event_order"])
            for step_index in range(pivot + 1):
                self.assertEqual(
                    canonical_json(left["steps"][step_index]["online"]),
                    canonical_json(right["steps"][step_index]["online"]),
                )
            left_pivot = left["steps"][pivot]
            right_pivot = right["steps"][pivot]
            self.assertNotEqual(
                left_pivot["reference_program_index"],
                right_pivot["reference_program_index"],
            )
            self.assertNotEqual(
                left_pivot["reference_template"], right_pivot["reference_template"]
            )
            self.assertNotEqual(
                left_pivot["reference_post_graph_hash"],
                right_pivot["reference_post_graph_hash"],
            )
            self.assertNotEqual(
                canonical_json(left_pivot["future_trace"]),
                canonical_json(right_pivot["future_trace"]),
            )

    def test_each_sibling_oracle_replay_matches_its_own_world(self):
        for sequence in self.audit:
            choices = [
                step["reference_program_index"] for step in sequence["steps"]
            ]
            replay = execute_rollout_choices(sequence, choices)
            self.assertEqual(
                replay["states"][-1]["graph_hash"],
                sequence["final_reference_graph_hash"],
            )

    def test_paired_online_boundary_split_isolation_and_determinism(self):
        for online in self.online:
            validate_online_payload(online)
            self.assertNotIn("reference", canonical_json(online))
            self.assertNotIn("future", canonical_json(online))
        repeated_online, repeated_audit, _ = generate_m1_paired_rollout_split(
            self.config, "validation", paired_groups=2,
        )
        self.assertEqual(records_sha256(self.online), records_sha256(repeated_online))
        self.assertEqual(records_sha256(self.audit), records_sha256(repeated_audit))
        _, train_audit, _ = generate_m1_paired_rollout_split(
            self.config, "train", paired_groups=1,
        )
        self.assertFalse(
            {item["paired_group_id"] for item in self.audit}
            & {item["paired_group_id"] for item in train_audit}
        )
        self.assertFalse(
            {item["asset_family"] for item in self.audit}
            & {item["asset_family"] for item in train_audit}
        )
        with self.assertRaisesRegex(ValueError, "test is sealed"):
            generate_m1_paired_rollout_split(
                self.config, "test", paired_groups=1,
            )

    def test_group_offset_reproduces_the_same_shard(self):
        shard_online, shard_audit, summary = generate_m1_paired_rollout_split(
            self.config, "validation", paired_groups=1, start_group_index=1,
        )
        self.assertEqual(summary["start_group_index"], 1)
        self.assertEqual(records_sha256(shard_online), records_sha256(self.online[40:]))
        self.assertEqual(records_sha256(shard_audit), records_sha256(self.audit[2:]))
        with self.assertRaisesRegex(ValueError, "nonnegative"):
            generate_m1_paired_rollout_split(
                self.config, "validation", paired_groups=1,
                start_group_index=-1,
            )


if __name__ == "__main__":
    unittest.main()
