"""Integrity tests for procedural, causally chained M1 rollouts."""
from collections import Counter
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
    ROLLOUT_TEMPLATE_COUNTS,
    execute_rollout_choices,
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
                self.assertEqual(len(illegal), 1)
                self.assertEqual(illegal[0]["failure"]["type"], "ProtectedMutationError")

    def test_hindsight_uses_real_later_reference_states_and_masks_tail(self):
        sequence = self.audit[0]
        expected_lengths = [3] * 18 + [2, 1]
        self.assertEqual(
            [len(step["future_trace"]) for step in sequence["steps"]],
            expected_lengths,
        )
        for step in sequence["steps"]:
            reference_index = step["reference_program_index"]
            self.assertEqual(step["candidate_energies"][reference_index]["future"], 0.0)
            self.assertEqual(step["teacher_winner_index"], reference_index)
            self.assertTrue(all(
                item["source"] == "actual_executed_reference_sequence"
                for item in step["future_trace"]
            ))
            self.assertTrue(any(
                energy["future"] > 0
                for candidate, energy in zip(
                    step["executed_candidates"],
                    step["candidate_energies"],
                    strict=True,
                )
                if candidate["legal"] and candidate["candidate_index"] != reference_index
            ))

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
