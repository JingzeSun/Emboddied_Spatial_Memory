"""V3 action-probe stage remains review-gated and exports anonymous counts."""

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops/vsmt"))
sys.path.insert(0, str(ROOT / "src"))
import vm04_target_action_probe as probe


class TargetActionProbeTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(probe.CONFIG_PATH.read_text(encoding="utf-8"))
        self.target = json.loads(probe.TARGET_CONTRACT_PATH.read_text(
            encoding="utf-8"))
        self.closed_config = dict(
            self.config, status="implementation_only_not_executable",
            probe_execution_authorized=False, expected_reviewed_probe_code=None)
        self.closed_target = dict(
            self.target, status="approved_semantics_implementation_only",
            target_capability_probe_authorized=False)

    def patched_load(self, changed):
        def read(path):
            return changed if path == probe.CONFIG_PATH else self.closed_target
        return patch.object(probe.audit, "read_json", side_effect=read)

    def test_review_only_contract_blocks_execution_before_stage_creation(self):
        actual, target = probe.load_config()
        self.assertEqual(actual["generation_authorized"], False)
        self.assertEqual(target["generation_authorized"], False)
        with self.patched_load(self.closed_config):
            config, closed_target = probe.load_config()
            self.assertEqual(config["status"],
                             "implementation_only_not_executable")
            self.assertEqual(closed_target["status"],
                             "approved_semantics_implementation_only")
            with self.assertRaisesRegex(RuntimeError, "execution remains closed"):
                probe.run("unused", Path("missing"), Path("missing"), Path("missing"))
            with self.assertRaisesRegex(RuntimeError, "export remains closed"):
                probe.export("unused", Path("missing"))

    def test_generation_or_unreviewed_probe_gate_cannot_be_opened(self):
        with self.patched_load(dict(self.closed_config, generation_authorized=True)):
            with self.assertRaisesRegex(RuntimeError, "cannot open generation"):
                probe.load_config()
        with self.patched_load(dict(self.closed_config, probe_execution_authorized=True)):
            with self.assertRaisesRegex(RuntimeError, "executable field"):
                probe.load_config()
        with self.patched_load(dict(self.closed_config, minimum_position_spacing_m=0.5)):
            with self.assertRaisesRegex(RuntimeError, "scope changed"):
                probe.load_config()

    def test_anonymous_repetition_reports_counts_without_ids(self):
        private_slots = [
            {"v3_target_instance_ids": ["secret-chair"]},
            {"v3_target_instance_ids": ["secret-chair"]},
            {"v3_target_instance_ids": ["secret-painting", "secret-chair"]},
            {"v3_target_instance_ids": []},
        ]
        counts = probe.anonymous_target_repeats(private_slots)
        self.assertEqual(counts["selected_physical_slot_count"], 3)
        self.assertEqual(counts["repeated_top1_count"], 1)
        self.assertEqual(counts["repeated_selected_target_set_count"], 1)
        self.assertNotIn("secret", str(counts))

    def test_public_report_cannot_export_private_action_or_object_details(self):
        receipt = {"scan_receipt_sha256": "a" * 64,
                   "v3_target_contract_sha256": "b" * 64,
                   "requested_workers": 2, "actual_workers": 2,
                   "resource_evidence": {"visible_cpu_count": 16},
                   "single_worker_benchmark": {
                       "requested_workers": 1, "actual_workers": 1,
                       "private_receipt_sha256": "e" * 64},
                   "worker_exits": [{"family_id": "audit-family:00",
                                     "exit_code": 0, "log_sha256": "c" * 64}]}
        report = probe.public_report_payload(
            "reviewed", "d" * 64, receipt,
            [{"family_id": "audit-family:00", "program": "BIRTH",
              "status": "intervention_rejected", "count": 36}],
            [{"family_id": "audit-family:00", "repeated_top1_count": 1}])
        self.assertFalse(report["private_ids_exported"])
        self.assertEqual(report["semantic_positive_labels_issued"], 0)
        self.assertNotIn("objectId", str(report))
        self.assertNotIn("errorMessage", str(report))
        with self.assertRaisesRegex(RuntimeError, "36 fixed slots"):
            probe.public_report_payload("reviewed", "d" * 64, receipt,
                                        [{"count": 35}], [])

    def test_server_check_fans_out_independent_modules(self):
        self.assertEqual(len(probe.CHECK_GROUPS), 3)
        modules = [module for _, group in probe.CHECK_GROUPS for module in group]
        self.assertIn("tests.test_vm04_target_selection_v3", modules)
        self.assertIn("tests.test_vm04_target_action_probe_worker", modules)
        self.assertIn("tests.test_vm04_target_action_probe", modules)

    def test_measured_peak_rss_must_fit_two_worker_safety_multiple(self):
        peak_kib = 2 * 1024 * 1024
        self.assertTrue(probe.memory_sufficient_for_two_workers(
            peak_kib, 8 * 1024 ** 3, 4.0))
        self.assertFalse(probe.memory_sufficient_for_two_workers(
            peak_kib, 8 * 1024 ** 3 - 1, 4.0))
        self.assertFalse(probe.memory_sufficient_for_two_workers(
            0, 16 * 1024 ** 3, 4.0))

    def test_sampled_gpu_demand_requires_twice_peak_and_static_headroom(self):
        gib = 1024 ** 3
        safe, device, peak = probe.measured_gpu_sufficient(
            [12 * gib, 20 * gib], [10 * gib, 16 * gib],
            [10 * gib, 12 * gib], 8 * gib, 2.0)
        self.assertTrue(safe)
        self.assertEqual((device, peak), (1, 4 * gib))
        unsafe, _, _ = probe.measured_gpu_sufficient(
            [12 * gib, 20 * gib], [10 * gib, 16 * gib],
            [10 * gib, 8 * gib - 1], 8 * gib, 2.0)
        self.assertFalse(unsafe)
        unmeasured, device, peak = probe.measured_gpu_sufficient(
            [20 * gib], [20 * gib], [20 * gib], 8 * gib, 2.0)
        self.assertFalse(unmeasured)
        self.assertIsNone(device)
        self.assertEqual(peak, 0)


if __name__ == "__main__":
    unittest.main()
