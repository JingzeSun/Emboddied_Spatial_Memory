"""Planning arithmetic and resource tests; no models or dataset generation."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from cpmt.m1_scope_rebuild import corrected_test_groups, feasible_layouts, runtime_recommendation


class TestScopeRebuild(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads((PROJECT / "configs/m1_scope_rebuild_plan.json").read_text())
        endpoints = self.plan["endpoints"]
        self.cells = {(endpoints[m], c): {"nondegenerate": True, "paired_group_standard_deviation": 0.1}
                      for m in ("semantic", "support", "burden") for c in endpoints["contrasts"]}

    def test_small_corrected_sd_cannot_reduce_registered_floor(self):
        self.assertEqual(corrected_test_groups(self.plan, self.cells, oracle_integrity_pass=True), 1350)

    def test_largest_of_all_six_cells_controls_upward_only_size(self):
        cell = self.cells[(self.plan["endpoints"]["support"], "A_vs_E")]
        cell["paired_group_standard_deviation"] = 0.6
        self.assertEqual(corrected_test_groups(self.plan, self.cells, oracle_integrity_pass=True), 3140)

    def test_observed_effect_cannot_change_sample_size(self):
        original = corrected_test_groups(self.plan, self.cells, oracle_integrity_pass=True)
        for cell in self.cells.values():
            cell["observed_mean_difference"] = -900
        self.assertEqual(corrected_test_groups(self.plan, self.cells, oracle_integrity_pass=True), original)

    def test_oracle_failure_and_degenerate_or_missing_cells_stop(self):
        with self.assertRaises(ValueError):
            corrected_test_groups(self.plan, self.cells, oracle_integrity_pass=False)
        for sd in (0.0, float("nan"), float("inf"), -1.0):
            cells = deepcopy(self.cells)
            cells[next(iter(cells))]["paired_group_standard_deviation"] = sd
            with self.assertRaises(ValueError):
                corrected_test_groups(self.plan, cells, oracle_integrity_pass=True)
        self.cells.pop(next(iter(self.cells)))
        with self.assertRaises(ValueError):
            corrected_test_groups(self.plan, self.cells, oracle_integrity_pass=True)

    def test_cpu_quota_prevents_thread_oversubscription(self):
        accepted, skipped = feasible_layouts(self.plan, cpu_capacity=2, gpu_free_gib=30, host_available_gib=100)
        self.assertEqual(accepted, [{"workers": 1, "threads": 1}, {"workers": 2, "threads": 1}])
        self.assertTrue(all("cpu_capacity" in s["reasons"] for s in skipped))

    def test_memory_reserves_prevent_unsafe_four_process_admission(self):
        accepted, skipped = feasible_layouts(self.plan, cpu_capacity=16, gpu_free_gib=16, host_available_gib=100)
        self.assertNotIn({"workers": 4, "threads": 1}, accepted)
        self.assertEqual(skipped[-1]["reasons"], ["gpu_headroom"])

    def test_runtime_tie_prefers_less_concurrency_and_has_no_accuracy_input(self):
        result = runtime_recommendation([{"workers": 1, "threads": 1, "elapsed_seconds": 104},
                                         {"workers": 2, "threads": 1, "elapsed_seconds": 100},
                                         {"workers": 4, "threads": 1, "elapsed_seconds": 110}])
        self.assertEqual(result["workers"], 1)
        with self.assertRaises(ValueError):
            runtime_recommendation([{"workers": 1, "threads": 1, "elapsed_seconds": float("nan")}])

    def test_plan_preserves_old_grid_and_closes_confirmation_retuning(self):
        hard = json.loads((PROJECT / "configs/m1_hard_condition.json").read_text())
        budget = hard["training"]["pretest_budget_selection"]
        controls = self.plan["overfit_controls"]
        self.assertEqual(controls["seeds"], budget["seeds"])
        self.assertEqual(controls["learning_rates"], budget["learning_rates"])
        self.assertEqual(controls["checkpoints"], budget["student_update_checkpoints"])
        self.assertFalse(controls["grid_expansion"])
        self.assertFalse(controls["validation_selects_settings"])
        self.assertFalse(controls["validation_unfavorable_result_allows_retuning"])
        self.assertEqual(self.plan["endpoints"]["collateral_margin_per_100"], 0.5)
        self.assertFalse(self.plan["endpoints"]["endpoint_reselection"])


if __name__ == "__main__":
    unittest.main()
