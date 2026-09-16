"""Fail-closed checks for the proposed D-183 amendments to D-182."""

import hashlib
import json
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs/vsmt/vm04_observation_suitability_proposal_v1.json"
AMENDMENT = ROOT / "configs/vsmt/vm04_observation_suitability_d183_amendment_proposal_v1.json"


class D183AmendmentProposalTests(unittest.TestCase):
    def setUp(self):
        self.amendment = json.loads(AMENDMENT.read_text(encoding="utf-8"))

    def test_amendment_is_closed_and_binds_approved_d182_bytes(self):
        self.assertEqual(
            self.amendment["status"],
            "approved_for_schema_implementation_review_not_executable")
        self.assertTrue(self.amendment["authorization"][
            "merge_into_base_contract_authorized"])
        self.assertTrue(self.amendment["authorization"][
            "schema_implementation_authorized"])
        self.assertFalse(self.amendment["authorization"]["pilot_authorized"])
        self.assertFalse(self.amendment["authorization"][
            "formal_generation_authorized"])
        base = self.amendment["base_contract"]
        blob = subprocess.check_output([
            "git", "show", f"{base['git_commit']}:{base['path']}"
        ], cwd=ROOT)
        self.assertEqual(
            base["git_blob_content_sha256"], hashlib.sha256(blob).hexdigest())

    def test_pilot_count_rule_is_pre_registered_and_bounded(self):
        rule = self.amendment["L_pilot_determines_formal_N_proposal"]
        self.assertEqual(rule["pilot_family_count"], 6)
        self.assertEqual(rule["ordered_source_pool_minimum_eligible_houses"], 70)
        self.assertEqual(rule["count_rule"], {
            "pilot_completed_5_or_6": 48,
            "pilot_completed_4": 64,
            "pilot_completed_0_to_3": "stop_and_require_new_contract_version",
        })
        self.assertEqual(rule["maximum_N"], 64)
        self.assertFalse(rule[
            "pilot_CFO_history_or_oracle_results_allowed_for_N"])
        self.assertFalse(rule[
            "additional_houses_after_formal_failures_allowed"])

    def test_easy_programs_remain_in_aggregate_but_lose_standalone_claim(self):
        policy = self.amendment[
            "M_per_program_identifiability_reporting_proposal"]
        self.assertEqual(len(policy["required_programs"]), 9)
        self.assertEqual(
            policy["easy_class_action"],
            "retain_in_aggregate_denominator_but_forbid_standalone_evidence_for_that_program")
        self.assertFalse(policy["easy_class_blocks_whole_dataset"])
        self.assertFalse(policy[
            "post_result_program_removal_relabeling_or_resampling_allowed"])

    def test_split_merge_artifacts_are_pre_registered_or_fail(self):
        artifact = self.amendment[
            "N_deterministic_SPLIT_MERGE_artifact_proposal"]
        self.assertTrue(artifact["program_assignment_sealed_before_generation"])
        self.assertFalse(artifact[
            "posthoc_program_label_from_observed_artifact_allowed"])
        self.assertEqual(
            artifact["artifact_not_realized_action"],
            "construction_failure_keep_registered_program_never_relabel")
        self.assertIsNone(artifact["exact_geometry_parameters"])


if __name__ == "__main__":
    unittest.main()
