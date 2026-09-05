"""M1 paired-generator integrity tests; formal test data is never generated."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from cpmt.hashing import canonical_json
from cpmt.m1_data import generate_m1_split, records_sha256, validate_online_payload


class TestM1PairedData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(
            (PROJECT / "configs" / "m1_hard_condition.json").read_text(encoding="utf-8")
        )
        cls.online, cls.audit, cls.summary = generate_m1_split(
            cls.config, "validation", groups_per_family=2,
        )

    def test_all_families_and_positive_templates_are_present(self):
        self.assertEqual(set(self.summary["family_case_counts"]), {
            f"C{index:02d}" for index in range(12)
        })
        templates = {record["reference_template"] for record in self.audit}
        self.assertTrue({
            "NOOP", "BIND", "BIRTH", "REACTIVATE", "RELINK", "RETRACT",
            "SPLIT", "MERGE",
        } <= templates)

    def test_reference_is_covered_legal_and_teacher_top_one(self):
        for record in self.audit:
            index = record["reference_program_index"]
            self.assertLess(index, self.config["candidates"]["budget_k"])
            self.assertTrue(record["executed_candidates"][index]["legal"])
            self.assertEqual(record["teacher_winner_index"], index)
            self.assertEqual(record["candidate_coverage_at_k"], 1.0)
            self.assertEqual(record["candidate_energies"][index]["future"], 0.0)

    def test_future_is_projected_observation_not_reference_graph(self):
        for record in self.audit:
            self.assertEqual(
                len(record["future_trace"]),
                self.config["future"]["primary_horizon"],
            )
            self.assertTrue(any(
                item["legal"] and energy["future"] > 0
                for item, energy in zip(
                    record["executed_candidates"],
                    record["candidate_energies"],
                    strict=True,
                )
            ))
            for step in record["future_trace"]:
                self.assertIn("structural_observation", step)
                self.assertNotIn("reference_state", canonical_json(step))

    def test_candidates_share_base_and_illegal_failures_are_retained(self):
        saw_illegal = False
        for record in self.audit:
            hashes = {
                candidate["base_graph_hash"]
                for candidate in record["executed_candidates"]
            }
            self.assertEqual(len(hashes), 1)
            for candidate in record["executed_candidates"]:
                if not candidate["legal"]:
                    saw_illegal = True
                    self.assertIsNotNone(candidate["failure"])
                    self.assertIsNone(candidate["post_graph"])
        self.assertTrue(saw_illegal)

    def test_ambiguous_siblings_are_exactly_online_identical(self):
        groups = {}
        for record in self.audit:
            groups.setdefault(record["paired_group_id"], []).append(record)
        for siblings in groups.values():
            self.assertEqual(len(siblings), 2)
            if siblings[0]["ambiguity"] == "epistemically_ambiguous":
                self.assertEqual(
                    canonical_json(siblings[0]["online"]),
                    canonical_json(siblings[1]["online"]),
                )
                self.assertNotEqual(
                    siblings[0]["reference_transaction_id"],
                    siblings[1]["reference_transaction_id"],
                )

    def test_identifiable_siblings_differ_only_in_history_cue(self):
        groups = {}
        for record in self.audit:
            groups.setdefault(record["paired_group_id"], []).append(record)
        for siblings in groups.values():
            if siblings[0]["ambiguity"] != "identifiable":
                continue
            left, right = deepcopy(siblings[0]["online"]), deepcopy(siblings[1]["online"])
            self.assertNotEqual(left["history_cues"], right["history_cues"])
            left.pop("history_cues")
            right.pop("history_cues")
            self.assertEqual(canonical_json(left), canonical_json(right))

    def test_train_and_validation_group_keys_are_disjoint(self):
        _, train, _ = generate_m1_split(self.config, "train", groups_per_family=2)
        validation_keys = {
            (item["paired_group_id"], item["world_seed"], item["asset_family"])
            for item in self.audit
        }
        train_keys = {
            (item["paired_group_id"], item["world_seed"], item["asset_family"])
            for item in train
        }
        self.assertFalse(validation_keys & train_keys)
        self.assertFalse(
            {item["asset_family"] for item in self.audit}
            & {item["asset_family"] for item in train}
        )

    def test_test_split_is_physically_unavailable(self):
        with self.assertRaisesRegex(ValueError, "test is sealed"):
            generate_m1_split(self.config, "test", groups_per_family=1)

    def test_online_boundary_and_determinism(self):
        for online in self.online:
            validate_online_payload(online)
        repeated_online, repeated_audit, _ = generate_m1_split(
            self.config, "validation", groups_per_family=2,
        )
        self.assertEqual(records_sha256(self.online), records_sha256(repeated_online))
        self.assertEqual(records_sha256(self.audit), records_sha256(repeated_audit))

    def test_online_boundary_rejects_audit_fields(self):
        polluted = deepcopy(self.online[0])
        polluted["future_features"] = [1, 2, 3]
        with self.assertRaisesRegex(ValueError, "audit-only"):
            validate_online_payload(polluted)


if __name__ == "__main__":
    unittest.main()
