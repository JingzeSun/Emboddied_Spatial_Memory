"""D-224 / S0-02 read-only checks for the intervention data contract.

The continue gate for S0-02 is: an intervention may only run while every
container it touches is unobservable for the whole window; ``private`` and
``provenance`` never enter a deployment reader's whitelist; the split is
recomputable and mutually exclusive; failed houses are kept and counted.
These tests prove the checks reject what they must; they say nothing about
whether any episode can actually be generated.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import unittest
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from vsmt.lean_intervention import (  # noqa: E402
    ACTIONS,
    CONTRACT_SCHEMA_VERSION,
    DEPLOYMENT_READABLE_PLANES,
    FAILURE_REASONS,
    INTERVENTION_KINDS,
    PLANES,
    LeanInterventionError,
    assert_reader_whitelist,
    assert_windows_unobservable,
    assign_split,
    house_split_rank,
    summarize_yield,
    validate_failure_receipt,
    validate_intervention_data_contract,
    validate_intervention_plan,
    validate_public_frame_record,
    validate_route_plan,
    validate_split_manifest,
    validate_three_plane_layout,
)


CONTRACT_PATH = PROJECT_ROOT / "configs" / "vsmt" / "lean_s0_intervention_data_v3.json"

SEED = 260919
POOL = [f"house-{index:04d}" for index in range(40)]


def digest(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def intervention(
    intervention_id: str, *, kind: str = "move", start: int = 4, end: int = 6,
    source: str | None = "container:kitchen", target: str | None = "container:bedroom",
    object_ref: str = "object:mug",
) -> dict[str, Any]:
    refs = [value for value in (source, target) if value is not None]
    return {
        "intervention_id": intervention_id,
        "kind": kind,
        "object_ref": object_ref,
        "source_container_ref": source,
        "target_container_ref": target,
        "window_start_index": start,
        "window_end_index": end,
        "container_refs": refs,
    }


def plan_with(*items: Mapping[str, Any]) -> dict[str, Any]:
    return {"house_id": "house-0007", "interventions": [dict(item) for item in items]}


def invisible(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Every container invisible across every window frame."""

    out: dict[str, Any] = {}
    for item in plan["interventions"]:
        for ref in item["container_refs"]:
            for index in range(item["window_start_index"], item["window_end_index"] + 1):
                out[f"{ref}@{index}"] = {
                    "visible": False,
                    "depth_frame_digest": digest(f"depth-{index}"),
                }
    return out


class TestSplit(unittest.TestCase):
    def test_split_is_a_pure_function_of_seed_and_house_id(self) -> None:
        first = house_split_rank("house-0003", seed=SEED)
        second = house_split_rank("house-0003", seed=SEED)
        self.assertEqual(first, second)
        self.assertNotEqual(first, house_split_rank("house-0003", seed=SEED + 1))
        self.assertNotEqual(first, house_split_rank("house-0004", seed=SEED))

    def test_split_is_mutually_exclusive_and_sized(self) -> None:
        split = assign_split(POOL, seed=SEED, train=20, validation=5, test=10)
        self.assertEqual(len(split["train"]), 20)
        self.assertEqual(len(split["validation"]), 5)
        self.assertEqual(len(split["test"]), 10)
        members = split["train"] + split["validation"] + split["test"]
        self.assertEqual(len(set(members)), 35)

    def test_changing_the_train_size_never_touches_test_or_validation(self) -> None:
        """D-224-X ruling X6: test and validation take the first prefixes, train the last."""

        small = assign_split(POOL, seed=SEED, train=10, validation=5, test=10)
        large = assign_split(POOL, seed=SEED, train=20, validation=5, test=10)
        self.assertEqual(small["test"], large["test"])
        self.assertEqual(small["validation"], large["validation"])
        self.assertEqual(small["train"], large["train"][:10])
        self.assertTrue(set(small["train"]).isdisjoint(small["test"]))
        ordered = sorted(POOL, key=lambda item: (house_split_rank(item, seed=SEED), item))
        self.assertEqual(large["test"], ordered[:10])
        self.assertEqual(large["validation"], ordered[10:15])
        self.assertEqual(large["train"], ordered[15:35])

    def test_changing_test_or_validation_moves_the_train_block(self) -> None:
        """Which is why those two sizes and the seed freeze before the first episode."""

        base = assign_split(POOL, seed=SEED, train=10, validation=5, test=10)
        other = assign_split(POOL, seed=SEED, train=10, validation=5, test=8)
        self.assertNotEqual(base["train"], other["train"])

    def test_manifest_that_moves_a_house_is_rejected(self) -> None:
        split = assign_split(POOL, seed=SEED, train=20, validation=5, test=10)
        manifest = {"seed": SEED, "house_pool": POOL, **split}
        validate_split_manifest(manifest)
        tampered = json.loads(json.dumps(manifest))
        tampered["train"][0] = tampered["test"][0]
        with self.assertRaises(LeanInterventionError) as caught:
            validate_split_manifest(tampered)
        self.assertEqual(
            str(caught.exception), "split_train_does_not_match_the_rule",
        )

    def test_pool_smaller_than_the_split_is_rejected(self) -> None:
        with self.assertRaises(LeanInterventionError) as caught:
            assign_split(POOL[:5], seed=SEED, train=20, validation=5, test=10)
        self.assertEqual(str(caught.exception), "house_pool_smaller_than_split")


class TestRoutePlan(unittest.TestCase):
    def test_a_registered_route_passes(self) -> None:
        plan = {
            "house_id": "house-0007",
            "actions": ["MoveAhead", "RotateLeft", "MoveAhead"],
            "observation_count": 4,
        }
        validate_route_plan(plan, maximum_actions=128)

    def test_an_unregistered_action_is_rejected(self) -> None:
        plan = {
            "house_id": "house-0007",
            "actions": ["MoveAhead", "Teleport"],
            "observation_count": 3,
        }
        with self.assertRaises(LeanInterventionError) as caught:
            validate_route_plan(plan, maximum_actions=128)
        self.assertEqual(str(caught.exception), "route_action_not_registered")

    def test_observation_count_must_be_actions_plus_one(self) -> None:
        plan = {
            "house_id": "house-0007",
            "actions": ["MoveAhead", "MoveAhead"],
            "observation_count": 2,
        }
        with self.assertRaises(LeanInterventionError) as caught:
            validate_route_plan(plan, maximum_actions=128)
        self.assertEqual(str(caught.exception), "route_observation_count_mismatch")

    def test_the_protection_limit_is_enforced(self) -> None:
        plan = {
            "house_id": "house-0007",
            "actions": ["MoveAhead"] * 5,
            "observation_count": 6,
        }
        with self.assertRaises(LeanInterventionError) as caught:
            validate_route_plan(plan, maximum_actions=4)
        self.assertEqual(
            str(caught.exception), "route_exceeds_action_protection_limit",
        )


class TestInterventionPlan(unittest.TestCase):
    def test_three_kinds_pass_with_their_own_endpoints(self) -> None:
        plan = plan_with(
            intervention("iv-0", kind="move", object_ref="object:mug"),
            intervention(
                "iv-1", kind="remove", object_ref="object:book",
                source="container:desk", target=None,
            ),
            intervention(
                "iv-2", kind="add", object_ref="object:cup",
                source=None, target="container:shelf",
            ),
        )
        validate_intervention_plan(
            plan, maximum_interventions=10, observation_count=12,
        )

    def test_remove_with_a_target_is_rejected(self) -> None:
        plan = plan_with(intervention(
            "iv-0", kind="remove", source="container:desk", target="container:shelf",
        ))
        with self.assertRaises(LeanInterventionError) as caught:
            validate_intervention_plan(
                plan, maximum_interventions=10, observation_count=12,
            )
        self.assertEqual(str(caught.exception), "remove_must_not_have_target")

    def test_move_to_the_same_container_is_rejected(self) -> None:
        plan = plan_with(intervention(
            "iv-0", kind="move", source="container:desk", target="container:desk",
        ))
        with self.assertRaises(LeanInterventionError) as caught:
            validate_intervention_plan(
                plan, maximum_interventions=10, observation_count=12,
            )
        self.assertEqual(str(caught.exception), "move_source_equals_target")

    def test_one_object_cannot_be_intervened_twice(self) -> None:
        plan = plan_with(
            intervention("iv-0", object_ref="object:mug"),
            intervention("iv-1", object_ref="object:mug"),
        )
        with self.assertRaises(LeanInterventionError) as caught:
            validate_intervention_plan(
                plan, maximum_interventions=10, observation_count=12,
            )
        self.assertEqual(str(caught.exception), "intervention_object_used_twice")

    def test_the_per_episode_limit_is_enforced(self) -> None:
        plan = plan_with(*[
            intervention(f"iv-{index}", object_ref=f"object:{index}")
            for index in range(4)
        ])
        with self.assertRaises(LeanInterventionError) as caught:
            validate_intervention_plan(
                plan, maximum_interventions=3, observation_count=12,
            )
        self.assertEqual(str(caught.exception), "too_many_interventions")

    def test_a_window_past_the_last_observation_is_rejected(self) -> None:
        plan = plan_with(intervention("iv-0", start=10, end=20))
        with self.assertRaises(LeanInterventionError) as caught:
            validate_intervention_plan(
                plan, maximum_interventions=10, observation_count=12,
            )
        self.assertEqual(str(caught.exception), "window_past_last_observation")

    def test_container_refs_must_cover_source_and_target(self) -> None:
        item = intervention("iv-0")
        item["container_refs"] = ["container:kitchen"]
        with self.assertRaises(LeanInterventionError) as caught:
            validate_intervention_plan(
                plan_with(item), maximum_interventions=10, observation_count=12,
            )
        self.assertEqual(
            str(caught.exception), "container_refs_missing_source_or_target",
        )


class TestUnobservableWindow(unittest.TestCase):
    def test_a_fully_invisible_window_passes_and_is_receipted(self) -> None:
        plan = plan_with(intervention("iv-0", start=4, end=6))
        receipt = assert_windows_unobservable(plan, invisible(plan))
        self.assertEqual(receipt["house_id"], "house-0007")
        self.assertEqual(len(receipt["window_receipts"]), 1)
        # two containers over three frames
        self.assertEqual(receipt["window_receipts"][0]["verdict_count"], 6)

    def test_one_visible_frame_fails_the_whole_episode(self) -> None:
        plan = plan_with(intervention("iv-0", start=4, end=6))
        verdicts = invisible(plan)
        verdicts["container:kitchen@5"]["visible"] = True
        with self.assertRaises(LeanInterventionError) as caught:
            assert_windows_unobservable(plan, verdicts)
        self.assertEqual(
            str(caught.exception), "container_visible_inside_window:container:kitchen@5",
        )

    def test_a_missing_verdict_is_not_treated_as_invisible(self) -> None:
        plan = plan_with(intervention("iv-0", start=4, end=6))
        verdicts = invisible(plan)
        del verdicts["container:bedroom@6"]
        with self.assertRaises(LeanInterventionError) as caught:
            assert_windows_unobservable(plan, verdicts)
        self.assertEqual(
            str(caught.exception),
            "visibility_verdict_missing:container:bedroom@6",
        )

    def test_a_verdict_without_its_depth_digest_is_rejected(self) -> None:
        plan = plan_with(intervention("iv-0", start=4, end=4))
        verdicts = invisible(plan)
        verdicts["container:kitchen@4"] = {"visible": False}
        with self.assertRaises(LeanInterventionError) as caught:
            assert_windows_unobservable(plan, verdicts)
        self.assertEqual(
            str(caught.exception), "visibility_verdict_fields_invalid",
        )

    def test_a_truthy_non_false_verdict_is_rejected(self) -> None:
        """``visible`` must be exactly False, not merely falsy."""

        plan = plan_with(intervention("iv-0", start=4, end=4))
        verdicts = invisible(plan)
        verdicts["container:kitchen@4"]["visible"] = 0
        with self.assertRaises(LeanInterventionError) as caught:
            assert_windows_unobservable(plan, verdicts)
        self.assertIn("container_visible_inside_window", str(caught.exception))


class TestPlanesAndReaders(unittest.TestCase):
    def _layout(self) -> dict[str, Any]:
        return {
            "public": ["public/frames.jsonl", "public/rgb/0000.png"],
            "private": ["private/instances.jsonl", "private/interventions.json"],
            "provenance": ["provenance/journal.jsonl"],
        }

    def test_a_disjoint_layout_passes(self) -> None:
        validate_three_plane_layout(self._layout())

    def test_a_file_in_two_planes_is_rejected(self) -> None:
        layout = self._layout()
        layout["private"].append("public/frames.jsonl")
        with self.assertRaises(LeanInterventionError) as caught:
            validate_three_plane_layout(layout)
        self.assertIn("layout_path_in_two_planes", str(caught.exception))

    def test_a_path_outside_its_plane_is_rejected(self) -> None:
        layout = self._layout()
        layout["public"].append("private/instances_copy.jsonl")
        with self.assertRaises(LeanInterventionError) as caught:
            validate_three_plane_layout(layout)
        self.assertIn("layout_path_outside_its_plane", str(caught.exception))

    def test_a_deployment_reader_may_only_mount_public(self) -> None:
        granted = assert_reader_whitelist(
            reader_id="vsmt.lean.frontend", requested_planes=["public"],
            deployment_reader=True,
        )
        self.assertEqual(granted["granted_planes"], ["public"])

    def test_a_deployment_reader_asking_for_private_is_refused(self) -> None:
        with self.assertRaises(LeanInterventionError) as caught:
            assert_reader_whitelist(
                reader_id="vsmt.lean.features",
                requested_planes=["public", "private"], deployment_reader=True,
            )
        self.assertEqual(
            str(caught.exception), "deployment_reader_requested:private",
        )

    def test_the_evaluator_may_mount_private(self) -> None:
        granted = assert_reader_whitelist(
            reader_id="vsmt.lean.evaluator",
            requested_planes=["public", "private"], deployment_reader=False,
        )
        self.assertEqual(granted["granted_planes"], ["private", "public"])

    def test_a_public_frame_carrying_a_scene_identifier_is_rejected(self) -> None:
        record = {
            "observation_index": 3,
            "rgb_path": "public/rgb/0003.png",
            "depth_path": "public/depth/0003.npy",
            "intrinsics": {"fx": 112.0, "fy": 112.0, "cx": 112.0, "cy": 112.0},
            "relative_pose": {"position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0]},
            "action_summary": {"steps": 2, "histogram": {"MoveAhead": 2}},
            "frame_digest": digest("frame-3"),
        }
        validate_public_frame_record(record)
        record["intrinsics"]["scene_name"] = "FloorPlan1"
        with self.assertRaises(LeanInterventionError) as caught:
            validate_public_frame_record(record)
        self.assertEqual(
            str(caught.exception), "public_frame_forbidden_key:scene_name",
        )


class TestFailureAccounting(unittest.TestCase):
    def _receipt(self, house_id: str = "house-0011") -> dict[str, Any]:
        return {
            "house_id": house_id,
            "split": "train",
            "reason": "action_rejected",
            "failed_at_observation_index": 17,
            "kept_prefix_observation_count": 17,
            "replaced": False,
        }

    def test_a_kept_failure_passes(self) -> None:
        validate_failure_receipt(self._receipt())

    def test_a_replaced_house_is_rejected(self) -> None:
        receipt = self._receipt()
        receipt["replaced"] = True
        with self.assertRaises(LeanInterventionError) as caught:
            validate_failure_receipt(receipt)
        self.assertEqual(
            str(caught.exception), "failed_house_must_not_be_replaced",
        )

    def test_an_invented_failure_reason_is_rejected(self) -> None:
        receipt = self._receipt()
        receipt["reason"] = "skipped_for_convenience"
        with self.assertRaises(LeanInterventionError) as caught:
            validate_failure_receipt(receipt)
        self.assertEqual(str(caught.exception), "failure_reason_unknown")

    def test_yield_requires_every_failure_to_be_accounted(self) -> None:
        summary = summarize_yield(
            planned=50, succeeded=48,
            failures=[self._receipt("house-0011"), self._receipt("house-0012")],
        )
        self.assertEqual(summary["failed"], 2)
        self.assertAlmostEqual(summary["yield"], 0.96)

    def test_a_silently_dropped_episode_is_caught(self) -> None:
        with self.assertRaises(LeanInterventionError) as caught:
            summarize_yield(
                planned=50, succeeded=47, failures=[self._receipt("house-0011")],
            )
        self.assertEqual(
            str(caught.exception), "planned_does_not_equal_success_plus_failure",
        )


class TestMachineContract(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_contract_agrees_with_the_implementation(self) -> None:
        validate_intervention_data_contract(self.contract)
        self.assertEqual(self.contract["schema_version"], CONTRACT_SCHEMA_VERSION)
        self.assertEqual(tuple(self.contract["route"]["actions"]), ACTIONS)
        self.assertEqual(
            tuple(self.contract["intervention_kinds"]), INTERVENTION_KINDS,
        )
        self.assertEqual(tuple(self.contract["planes"]), PLANES)
        self.assertEqual(tuple(self.contract["failure_reasons"]), FAILURE_REASONS)
        self.assertEqual(
            frozenset(self.contract["deployment_readable_planes"]),
            DEPLOYMENT_READABLE_PLANES,
        )

    def test_the_split_prefix_order_and_freeze_claims_are_bound(self) -> None:
        """D-224-X ruling X6."""

        from vsmt.lean_intervention import SPLIT_PREFIX_ORDER

        self.assertEqual(SPLIT_PREFIX_ORDER, ("test", "validation", "train"))
        self.assertEqual(tuple(self.contract["split_rule"]["prefix_assignment"]), SPLIT_PREFIX_ORDER)
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["split_rule"]["prefix_assignment"] = ["train", "validation", "test"]
        with self.assertRaises(LeanInterventionError) as caught:
            validate_intervention_data_contract(broken)
        self.assertEqual(str(caught.exception), "contract_split_prefix_order_mismatch")
        for name in (
            "test_and_validation_sizes_and_seed_frozen_before_first_generation",
            "train_size_may_only_decrease_after_registration",
        ):
            broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
            broken["split_rule"][name] = False
            with self.assertRaises(LeanInterventionError) as caught:
                validate_intervention_data_contract(broken)
            self.assertEqual(str(caught.exception), f"contract_split_rule_{name}_weakened")

    def test_an_extra_action_in_the_contract_is_rejected(self) -> None:
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["route"]["actions"] = list(broken["route"]["actions"]) + ["Teleport"]
        with self.assertRaises(LeanInterventionError) as caught:
            validate_intervention_data_contract(broken)
        self.assertEqual(str(caught.exception), "contract_actions_mismatch")

    def test_letting_a_deployment_reader_see_private_is_rejected(self) -> None:
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["deployment_readable_planes"] = ["public", "private"]
        with self.assertRaises(LeanInterventionError) as caught:
            validate_intervention_data_contract(broken)
        self.assertEqual(
            str(caught.exception), "contract_deployment_planes_mismatch",
        )

    def test_weakening_the_window_rule_is_rejected(self) -> None:
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["intervention_window"][
            "every_container_every_frame_must_be_invisible"
        ] = False
        with self.assertRaises(LeanInterventionError) as caught:
            validate_intervention_data_contract(broken)
        self.assertEqual(str(caught.exception), "contract_window_rule_weakened")

    def test_policy_values_must_still_be_null(self) -> None:
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["split_rule"]["seed"] = 260919
        with self.assertRaises(LeanInterventionError) as caught:
            validate_intervention_data_contract(broken)
        # A registered value is open or frozen; either way it must agree
        # with policy_values_without_defaults.
        self.assertIn("still_listed_as_open", str(caught.exception))

    def test_every_authorization_bit_is_false(self) -> None:
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["authorization"]["episode_generation"] = True
        with self.assertRaises(LeanInterventionError) as caught:
            validate_intervention_data_contract(broken)
        self.assertEqual(
            str(caught.exception), "contract_authorization_must_be_all_false",
        )

    def test_the_window_verdict_source_is_the_reviewed_mechanism(self) -> None:
        self.assertEqual(
            self.contract["intervention_window"]["verdict_source"],
            "vm04_public_visibility.assess_public_visibility_from_depth",
        )

    def test_this_stage_defines_no_features_labels_or_metrics(self) -> None:
        excluded = set(self.contract["not_in_this_stage"])
        for name in ("feature_definitions", "teacher_labels", "metrics",
                     "arm_parameters"):
            self.assertIn(name, excluded)


class TestR1I1RuleSections(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_the_rule_sections_bind(self) -> None:
        validate_intervention_data_contract(self.contract)

    def test_coverage_over_space_is_rejected(self) -> None:
        bad = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        bad["route_planning"]["coverage_definition"] = "every_reachable_cell_visited"
        with self.assertRaises(LeanInterventionError):
            validate_intervention_data_contract(bad)

    def test_sequential_resampling_is_rejected(self) -> None:
        bad = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        bad["intervention_selection"]["sequential_resample_on_failure_forbidden"] = False
        with self.assertRaises(LeanInterventionError):
            validate_intervention_data_contract(bad)

    def test_a_shorter_window_floor_is_rejected(self) -> None:
        bad = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        bad["intervention_window"]["minimum_window_frames"] = 1
        with self.assertRaises(LeanInterventionError):
            validate_intervention_data_contract(bad)

    def test_dropping_the_destination_revisit_is_rejected(self) -> None:
        bad = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        bad["route_planning"]["sweep_two_revisits_source_and_destination_for_move"] = False
        with self.assertRaises(LeanInterventionError):
            validate_intervention_data_contract(bad)

    def test_the_cap_may_not_truncate(self) -> None:
        bad = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        bad["route"]["cap_hit_is_a_construction_failure_not_a_truncation"] = False
        with self.assertRaises(LeanInterventionError):
            validate_intervention_data_contract(bad)

    def test_the_six_values_are_frozen(self) -> None:
        self.assertEqual(self.contract["route"]["maximum_actions"], 2000)
        iw = self.contract["intervention_window"]
        self.assertEqual((iw["maximum_interventions_per_episode"], iw["minimum_yield"],
                          iw["minimum_window_frames"]), (6, 0.6, 20))
        self.assertEqual(self.contract["intervention_selection"]["p_null_window"], 0.2)
        self.assertEqual(self.contract["route_planning"]["viewpoint_distance_m"], [0.75, 2.5])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
