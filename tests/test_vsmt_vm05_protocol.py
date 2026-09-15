"""VM-05 method taxonomy and fail-closed readiness tests; no model is run."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from vsmt.vm05_protocol import (
    DETERMINISTIC_ADAPTERS,
    EXECUTABLE_STATUS,
    LEARNED_RANKERS,
    PAPER_MECHANISM_ADAPTERS,
    REQUIRED_INPUTS,
    assert_vm05_action_authorized,
    validate_vm05_readiness,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/vsmt/vm05_training_validation_readiness_v1.json"


def config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def frozen_config(*, action: str) -> dict:
    value = config()
    value["status"] = EXECUTABLE_STATUS
    gate = {
        "train": "training_authorized",
        "validate": "validation_effect_authorized",
        "confirm": "confirmation_authorized",
    }[action]
    value[gate] = True
    learned = value["execution_classes"]["learned_candidate_rankers"]
    learned.update({
        "architecture": {"fixture": "resolved"},
        "optimizer": {"fixture": "resolved"},
        "training_steps": 1,
        "seed_count": 1,
    })
    value["execution_classes"]["deterministic_mechanism_adapters"][
        "configuration_spaces"
    ] = {"fixture": "resolved"}
    value["execution_classes"]["deterministic_internal_control"][
        "decision_formula"
    ] = {"fixture": "resolved"}
    value["satisfied_input_sha256s"] = {
        name: f"{index + 1:064x}" for index, name in enumerate(REQUIRED_INPUTS)
    }
    return value


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
                ValueError, "not frozen_executable"
            ):
                assert_vm05_action_authorized(config(), action=action)

    def test_action_authorization_has_a_reachable_frozen_path(self) -> None:
        for action in ("train", "validate", "confirm"):
            with self.subTest(action=action):
                result = assert_vm05_action_authorized(
                    frozen_config(action=action), action=action,
                )
                self.assertTrue(result[{
                    "train": "training_authorized",
                    "validate": "validation_effect_authorized",
                    "confirm": "confirmation_authorized",
                }[action]])

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

    def test_required_null_fields_must_be_explicit(self) -> None:
        paths = (
            ("wall_clock_timeout_seconds",),
            ("status",),
            ("execution_classes", "learned_candidate_rankers", "architecture"),
            ("execution_classes", "learned_candidate_rankers", "optimizer"),
            ("execution_classes", "learned_candidate_rankers", "training_steps"),
            ("execution_classes", "learned_candidate_rankers", "seed_count"),
            ("execution_classes", "deterministic_mechanism_adapters", "configuration_spaces"),
            ("execution_classes", "deterministic_internal_control", "decision_formula"),
        )
        for path in paths:
            value = config()
            target = value
            for key in path[:-1]:
                target = target[key]
            del target[path[-1]]
            with self.subTest(path=path), self.assertRaises(ValueError):
                validate_vm05_readiness(value)

    def test_frozen_lists_are_compared_by_content(self) -> None:
        for key, replacement in (
            ("required_inputs_before_executable", ["nothing_required"] * 8),
            ("prohibited", []),
        ):
            value = config()
            value[key] = replacement
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_vm05_readiness(value)

    def test_negative_method_boundary_tampering_is_rejected(self) -> None:
        mutations = (
            lambda value: value["execution_classes"][
                "deterministic_mechanism_adapters"
            ].__setitem__("requires_gradient_training", True),
            lambda value: value["execution_classes"][
                "learned_candidate_rankers"
            ].__setitem__("architecture", {"hidden": 256}),
            lambda value: value["paper_system_model_boundary"]["TAF"].__setitem__(
                "adapted_memory_update_is_gradient_trained", True
            ),
        )
        for mutate in mutations:
            value = config()
            mutate(value)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                validate_vm05_readiness(value)

    def test_paper_system_model_boundary_values_are_frozen(self) -> None:
        mutations = (
            lambda value: value["paper_system_model_boundary"]["TAF"].__setitem__(
                "source_system", "Khronos"
            ),
            lambda value: value["paper_system_model_boundary"]["TAF"].__setitem__(
                "source_system_uses_pretrained_perception_models", False
            ),
            lambda value: value["paper_system_model_boundary"].__setitem__("policy", ""),
            lambda value: value["paper_system_model_boundary"]["WFR"].__setitem__(
                "source_system_may_consume_external_or_pretrained_semantic_segmentation",
                False,
            ),
        )
        for mutate in mutations:
            value = config()
            mutate(value)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                validate_vm05_readiness(value)

    def test_frozen_state_rejects_zero_or_empty_scientific_values(self) -> None:
        mutations = (
            lambda value: value["execution_classes"]["learned_candidate_rankers"].update(
                training_steps=0
            ),
            lambda value: value["execution_classes"]["learned_candidate_rankers"].update(
                seed_count=0
            ),
            lambda value: value["execution_classes"]["learned_candidate_rankers"].update(
                architecture=False
            ),
            lambda value: value["execution_classes"]["learned_candidate_rankers"].update(
                optimizer=""
            ),
            lambda value: value["execution_classes"][
                "deterministic_mechanism_adapters"
            ].update(configuration_spaces={}),
            lambda value: value["execution_classes"][
                "deterministic_internal_control"
            ].update(decision_formula={}),
        )
        for mutate in mutations:
            value = frozen_config(action="train")
            mutate(value)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                assert_vm05_action_authorized(value, action="train")

    def test_frozen_state_requires_all_external_input_digests(self) -> None:
        missing = frozen_config(action="train")
        missing["satisfied_input_sha256s"].pop(REQUIRED_INPUTS[0])
        with self.assertRaisesRegex(ValueError, "bind every required input"):
            assert_vm05_action_authorized(missing, action="train")

        malformed = frozen_config(action="train")
        malformed["satisfied_input_sha256s"][REQUIRED_INPUTS[0]] = "not-a-digest"
        with self.assertRaisesRegex(ValueError, "lowercase SHA-256"):
            assert_vm05_action_authorized(malformed, action="train")

        planned = config()
        planned["satisfied_input_sha256s"] = {
            REQUIRED_INPUTS[0]: "1" * 64
        }
        with self.assertRaisesRegex(ValueError, "may not claim satisfied"):
            validate_vm05_readiness(planned)

    def test_validation_never_mutates_or_shares_nested_source_state(self) -> None:
        source = config()
        original = json.loads(json.dumps(source))
        validated = validate_vm05_readiness(source)
        validated["execution_classes"]["learned_candidate_rankers"]["architecture"] = {
            "mutated": True
        }
        self.assertEqual(source, original)
        source["execution_classes"]["deterministic_mechanism_adapters"][
            "requires_gradient_training"
        ] = True
        failing_input = json.loads(json.dumps(source))
        with self.assertRaises(ValueError):
            validate_vm05_readiness(source)
        self.assertEqual(source, failing_input)

    def test_paper_adapter_set_does_not_depend_on_low_position(self) -> None:
        self.assertEqual(PAPER_MECHANISM_ADAPTERS, ("TAF", "ELU", "WFR"))
        self.assertNotIn("LOW", PAPER_MECHANISM_ADAPTERS)

    def test_all_learned_and_internal_controls_have_explicit_trial_caps(self) -> None:
        value = validate_vm05_readiness(config())
        classes = value["execution_classes"]
        self.assertEqual(
            classes["learned_candidate_rankers"]["maximum_complete_configurations_per_method"],
            12,
        )
        self.assertEqual(
            classes["deterministic_internal_control"]["maximum_complete_configurations_per_method"],
            12,
        )
        self.assertEqual(
            value["fair_selection"]["maximum_complete_configurations_per_internal_control"],
            12,
        )


if __name__ == "__main__":
    unittest.main()
