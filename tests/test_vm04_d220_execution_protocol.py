"""D-220 forbids the activation-commit gate in any D-223 stage.

D-220 removed the "reviewed implementation commit plus a single-file activation
child plus an exact parent match" triple gate after it was empirically
falsified: one unrelated documentation commit was enough to lock an already
authorized stage.  F-00 and F-01 reintroduced it, and commits a7d5269, 9260cf2
and e2508a0 are the artifacts of that mistake -- two of them exist only to open
and re-close the gate, and the run they guarded was blocked anyway.

These tests are the regression guard.  The historical D-211/D-216/D-217/D-218
stages are deliberately out of scope: they really did execute under the older
protocol against contract bytes that must not change.
"""

from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
ABOLISHED_CONTRACT_FIELDS = (
    "activation_commit_may_change_only",
    "executable_checkout_parent_must_equal_reviewed_implementation_commit",
    "expected_reviewed_implementation_commit",
)
D220_PROTOCOL = "d220_contract_bits_plus_clean_checkout_plus_run_receipt"
D223_CONTRACTS = (
    "configs/vsmt/vm04_d223_f00_topology_precheck_v1.json",
    "configs/vsmt/vm04_d223_f01_production_reader_v1.json",
)
D223_STAGES = (
    "ops/vsmt/vm04_d223_f00_topology_precheck.py",
    "ops/vsmt/vm04_d223_f01_production_reader.py",
)


class D220ExecutionProtocolTests(unittest.TestCase):
    def test_d223_contracts_carry_no_abolished_gate_field(self):
        for relative in D223_CONTRACTS:
            text = (ROOT / relative).read_text(encoding="utf-8")
            for field in ABOLISHED_CONTRACT_FIELDS:
                self.assertNotIn(field, text, f"{relative} kept {field}")

    def test_d223_contracts_declare_the_d220_protocol_and_receipt_fields(self):
        for relative in D223_CONTRACTS:
            policy = json.loads(
                (ROOT / relative).read_text(encoding="utf-8"))["activation_policy"]
            self.assertEqual(D220_PROTOCOL, policy["execution_protocol"])
            self.assertTrue(policy["executable_checkout_must_be_clean"])
            self.assertEqual([
                "execution_commit", "contract_sha256", "input_digests",
                "output_digests", "resource_basis", "failures",
            ], policy["run_receipt_must_record"])

    def test_d223_stages_do_not_inspect_the_parent_commit(self):
        for relative in D223_STAGES:
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn('"HEAD^"', text, f"{relative} reads HEAD^")
            for field in ABOLISHED_CONTRACT_FIELDS:
                self.assertNotIn(field, text, f"{relative} reads {field}")

    def test_d223_stages_still_require_a_clean_checkout(self):
        for relative in D223_STAGES:
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("requires a clean checkout", text,
                          f"{relative} dropped the clean-checkout requirement")


if __name__ == "__main__":
    unittest.main()
