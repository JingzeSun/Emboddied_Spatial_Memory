"""VM-05 method taxonomy and fail-closed readiness tests; no model is run."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from vsmt.vm05_protocol import (
    DETERMINISTIC_ADAPTERS,
    LEARNED_RANKERS,
    assert_vm05_action_authorized,
    validate_vm05_readiness,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/vsmt/vm05_training_validation_readiness_v1.json"


def config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


class VM05ReadinessTests(unittest.TestCase):
    def test_method_taxonomy_separates_training_from_configuration_selection(self) -> None:
        value = validate_vm05_readiness(config())
        classes = value["execution_classes"]
        self.assertEqual(tuple(classes["learned_candidate_rankers"]["methods"]),
                         LEARNED_RANKERS)
        self.assertEqual(tuple(classes["deterministic_mechanism_adapters"]["methods"]),
                         DETERMINISTIC_ADAPTERS)
        self.assertTrue(classes["learned_candidate_rankers"]["requires_gradient_training"])
        self.assertFalse(classes["deterministic_mechanism_adapters"]["requires_gradient_training"])

    def test_shared_frontend_is_frozen_and_method_independent(self) -> None:
        frontend = validate_vm05_readiness(config())["shared_frontend"]
        self.assertFalse(frontend["gradient_updates"])
        self.assertFalse(frontend["method_private_perception_models_allowed"])
        self.assertTrue(frontend["identical_cached_input_bytes_for_all_methods"])

    def test_training_validation_and_confirmation_fail_closed(self) -> None:
        for action in ("train", "validate", "confirm"):
            with self.subTest(action=action), self.assertRaisesRegex(
                ValueError, "not authorized"
            ):
                assert_vm05_action_authorized(config(), action=action)

    def test_wall_clock_timeout_is_forbidden_but_resource_safety_remains(self) -> None:
        value = validate_vm05_readiness(config())
        self.assertIsNone(value["wall_clock_timeout_seconds"])
        safety = value["resource_safety"]
        self.assertFalse(safety["wall_clock_timeout_allowed"])
        self.assertTrue(safety["RAM_safety_check_required"])
        self.assertTrue(safety["GPU_VRAM_safety_check_required"])
        self.assertTrue(safety["disk_free_space_safety_check_required"])

    def test_parallel_work_uses_capacity_selected_multiple_workers(self) -> None:
        workers = validate_vm05_readiness(config())["multi_worker_execution"]
        self.assertEqual(workers["minimum_workers_when_at_least_two_independent_units_exist"], 2)
        self.assertTrue(workers["worker_count_is_selected_by_capacity_probe"])
        self.assertTrue(workers["canonical_merge_independent_of_worker_completion_order"])

    def test_unresolved_scientific_values_remain_null(self) -> None:
        value = validate_vm05_readiness(config())
        learned = value["execution_classes"]["learned_candidate_rankers"]
        for key in ("architecture", "optimizer", "training_steps", "seed_count"):
            self.assertIsNone(learned[key])
        self.assertIsNone(
            value["execution_classes"]["deterministic_mechanism_adapters"]["configuration_spaces"]
        )
        self.assertIsNone(
            value["execution_classes"]["deterministic_internal_control"]["decision_formula"]
        )


if __name__ == "__main__":
    unittest.main()
