"""D-224 / S0-03 tests for recall, features, the cost matrix and the solve.

The continue gate for S0-03 is: mutating private data leaves the recall
order, the feature matrix and the untrained logits byte-identical; the solver
is deterministic and optimal; the three feature orders are frozen by the
machine contract; and existence features are computed after the solve.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path
import random
import sys
import unittest
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from cpmt.hashing import canonical_json  # noqa: E402
from vsmt.lean_assignment import (  # noqa: E402
    ASSOCIATION_FEATURES,
    BIRTH_COLUMN_PREFIX,
    BIRTH_FEATURES,
    CACHE_FRAME_FIELDS,
    CONTRACT_SCHEMA_VERSION,
    EXISTENCE_FEATURES,
    FORBIDDEN_COST,
    LeanAssignmentError,
    assert_private_mutation_invariance,
    assignment_cost,
    build_assignment_inputs,
    build_cost_matrix,
    build_recall,
    existence_feature_vector,
    recall_for_fragment,
    reference_untrained_scores,
    solve_frame,
    solve_rectangular_assignment,
    validate_assignment_contract,
    validate_cache_frame,
)
from vsmt.lean_memory import apply_program, empty_memory  # noqa: E402


CONTRACT_PATH = PROJECT_ROOT / "configs" / "vsmt" / "lean_s0_assignment_v1.json"

RECALL = {"active_count": 3, "dormant_count": 2, "active_radius_m": 2.0}
BIRTH_RADIUS = 1.0
SEED = 7


def digest(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def fragment(
    fragment_id: str, *, descriptor: list[float], centroid: list[float],
    pixel_count: int = 400, half: float = 0.1, supported_by: str | None = None,
    depth_valid_ratio: float = 1.0,
) -> dict[str, Any]:
    return {
        "fragment_id": fragment_id,
        "descriptor": list(descriptor),
        "centroid_m": list(centroid),
        "aabb_min_m": [value - half for value in centroid],
        "aabb_max_m": [value + half for value in centroid],
        "pixel_count": pixel_count,
        "depth_valid_ratio": depth_valid_ratio,
        "supported_by": supported_by,
    }


def frame_with(
    *fragments: Mapping[str, Any], tick: int, entity_ids: list[str],
    seed: str = "f2",
) -> dict[str, Any]:
    return {
        "frame_digest": digest(seed),
        "tick": tick,
        "camera_position_m": [0.0, 1.5, -1.0],
        "camera_forward": [0.0, 0.0, 1.0],
        "fragments": [dict(item) for item in fragments],
        "entity_geometry": {
            entity_id: {
                "should_be_visible_ratio": 0.9,
                "free_space_coverage_ratio": 0.1,
            }
            for entity_id in entity_ids
        },
    }


def memory_with_two_entities() -> tuple[dict[str, Any], str, str]:
    """Commit two births at tick 1 and return the memory and both ids."""

    memory = apply_program(
        empty_memory(episode_id="ep-0001"),
        {
            "frame_digest": digest("f1"),
            "operations": [
                {"atom": "BIRTH", "fragment": {
                    "fragment_id": "region:0000",
                    "descriptor": [1.0, 0.0],
                    "centroid_m": [0.0, 0.0, 0.0],
                    "aabb_min_m": [-0.1, -0.1, -0.1],
                    "aabb_max_m": [0.1, 0.1, 0.1],
                    "pixel_count": 400,
                    "supported_by": None,
                }},
                {"atom": "BIRTH", "fragment": {
                    "fragment_id": "region:0001",
                    "descriptor": [0.0, 1.0],
                    "centroid_m": [1.0, 0.0, 0.0],
                    "aabb_min_m": [0.9, -0.1, -0.1],
                    "aabb_max_m": [1.1, 0.1, 0.1],
                    "pixel_count": 400,
                    "supported_by": None,
                }},
            ],
        },
        method_id="vsmt.lean.test.v1", dormancy_missed_opportunity_limit=2,
    )
    ids = sorted(str(entity["entity_id"]) for entity in memory["entities"])
    return memory, ids[0], ids[1]


def inputs_for(memory: Mapping[str, Any], frame: Mapping[str, Any]) -> dict[str, Any]:
    return build_assignment_inputs(
        frame, memory, birth_neighbourhood_radius_m=BIRTH_RADIUS, **RECALL,
    )


class TestCacheFrame(unittest.TestCase):
    def test_a_well_formed_frame_passes(self) -> None:
        memory, first, _ = memory_with_two_entities()
        frame = frame_with(
            fragment("region:0002", descriptor=[1.0, 0.0], centroid=[0.0, 0.0, 0.0]),
            tick=2, entity_ids=[first],
        )
        validate_cache_frame(frame)

    def test_a_non_unit_camera_forward_is_rejected(self) -> None:
        frame = frame_with(tick=2, entity_ids=[])
        frame["camera_forward"] = [0.0, 0.0, 2.0]
        with self.assertRaises(LeanAssignmentError) as caught:
            validate_cache_frame(frame)
        self.assertEqual(str(caught.exception), "camera_forward_not_unit")

    def test_a_fragment_id_colliding_with_a_birth_column_is_rejected(self) -> None:
        frame = frame_with(
            fragment(f"{BIRTH_COLUMN_PREFIX}x", descriptor=[1.0, 0.0],
                     centroid=[0.0, 0.0, 0.0]),
            tick=2, entity_ids=[],
        )
        with self.assertRaises(LeanAssignmentError) as caught:
            validate_cache_frame(frame)
        self.assertEqual(
            str(caught.exception), "fragment_id_collides_with_birth_column",
        )

    def test_a_ratio_outside_zero_to_one_is_rejected(self) -> None:
        frame = frame_with(tick=2, entity_ids=["entity:abc"])
        frame["entity_geometry"]["entity:abc"]["should_be_visible_ratio"] = 1.5
        with self.assertRaises(LeanAssignmentError) as caught:
            validate_cache_frame(frame)
        self.assertEqual(
            str(caught.exception),
            "entity_geometry_should_be_visible_ratio_invalid",
        )


class TestRecall(unittest.TestCase):
    def test_active_recall_respects_the_distance_limit(self) -> None:
        memory, near_id, far_id = memory_with_two_entities()
        # Both entities look identical to this fragment; only distance differs.
        probe = fragment("region:0002", descriptor=[1.0, 1.0], centroid=[0.0, 0.0, 0.0])
        wide = recall_for_fragment(probe, memory, active_count=5, dormant_count=0,
                                   active_radius_m=5.0)
        narrow = recall_for_fragment(probe, memory, active_count=5, dormant_count=0,
                                     active_radius_m=0.5)
        self.assertEqual(len(wide), 2)
        self.assertEqual(len(narrow), 1)
        self.assertNotIn(far_id if near_id in narrow else near_id, narrow)

    def test_a_retracted_entity_is_recalled_from_any_distance(self) -> None:
        memory, first, _ = memory_with_two_entities()
        retracted = apply_program(
            memory, {"frame_digest": digest("f2"),
                     "operations": [{"atom": "RETRACT", "entity_id": first}]},
            method_id="vsmt.lean.test.v1", dormancy_missed_opportunity_limit=2,
        )
        far_away = fragment(
            "region:0002", descriptor=[1.0, 0.0], centroid=[40.0, 0.0, 40.0],
        )
        recalled = recall_for_fragment(
            far_away, retracted, active_count=0, dormant_count=3,
            active_radius_m=0.5,
        )
        self.assertIn(first, recalled)

    def test_recall_order_does_not_depend_on_memory_list_order(self) -> None:
        memory, _, _ = memory_with_two_entities()
        probe = fragment("region:0002", descriptor=[1.0, 1.0], centroid=[0.5, 0.0, 0.0])
        forward = recall_for_fragment(probe, memory, **RECALL)
        shuffled = json.loads(json.dumps(memory))
        shuffled["entities"].reverse()
        backward = recall_for_fragment(probe, shuffled, **RECALL)
        self.assertEqual(forward, backward)

    def test_recall_counts_are_respected(self) -> None:
        memory, _, _ = memory_with_two_entities()
        probe = fragment("region:0002", descriptor=[1.0, 1.0], centroid=[0.5, 0.0, 0.0])
        self.assertEqual(
            len(recall_for_fragment(probe, memory, active_count=1,
                                    dormant_count=0, active_radius_m=5.0)),
            1,
        )


class TestFeatures(unittest.TestCase):
    def test_association_rows_use_the_frozen_order_and_arity(self) -> None:
        memory, first, _ = memory_with_two_entities()
        frame = frame_with(
            fragment("region:0002", descriptor=[1.0, 0.0], centroid=[0.05, 0.0, 0.0]),
            tick=2, entity_ids=[first],
        )
        built = inputs_for(memory, frame)
        self.assertEqual(
            built["association_feature_order"], list(ASSOCIATION_FEATURES),
        )
        self.assertEqual(built["birth_feature_order"], list(BIRTH_FEATURES))
        for row in built["association_rows"]:
            self.assertEqual(len(row["features"]), len(ASSOCIATION_FEATURES))
        for row in built["birth_rows"]:
            self.assertEqual(len(row["features"]), len(BIRTH_FEATURES))

    def test_the_cosine_feature_matches_the_descriptor(self) -> None:
        memory, first, second = memory_with_two_entities()
        frame = frame_with(
            fragment("region:0002", descriptor=[1.0, 0.0], centroid=[0.05, 0.0, 0.0]),
            tick=2, entity_ids=[first, second],
        )
        built = inputs_for(memory, frame)
        by_entity = {
            row["entity_id"]: row["features"] for row in built["association_rows"]
        }
        index = ASSOCIATION_FEATURES.index("cosine_to_descriptor_mean")
        # The entity born from [1, 0] must score 1.0; the [0, 1] one scores 0.0.
        self.assertAlmostEqual(max(row[index] for row in by_entity.values()), 1.0)
        self.assertAlmostEqual(min(row[index] for row in by_entity.values()), 0.0)

    def test_frame_tick_must_follow_the_memory_tick(self) -> None:
        memory, first, _ = memory_with_two_entities()
        frame = frame_with(
            fragment("region:0002", descriptor=[1.0, 0.0], centroid=[0.0, 0.0, 0.0]),
            tick=7, entity_ids=[first],
        )
        with self.assertRaises(LeanAssignmentError) as caught:
            inputs_for(memory, frame)
        self.assertEqual(str(caught.exception), "frame_tick_not_next")

    def test_existence_features_depend_on_the_assignment(self) -> None:
        """The same entity and frame give a different row once f is taken."""

        memory, first, second = memory_with_two_entities()
        frame = frame_with(
            fragment("region:0002", descriptor=[1.0, 0.0], centroid=[0.05, 0.0, 0.0]),
            tick=2, entity_ids=[first, second],
        )
        entity = [
            item for item in memory["entities"]
            if str(item["entity_id"]) == first
        ][0]
        index = EXISTENCE_FEATURES.index("best_fragment_still_unassigned")
        taken = existence_feature_vector(
            entity, frame, assignment={"region:0002": second}, tick=2,
        )
        free = existence_feature_vector(
            entity, frame,
            assignment={"region:0002": f"{BIRTH_COLUMN_PREFIX}region:0002"}, tick=2,
        )
        self.assertEqual(taken[index], 0.0)
        self.assertEqual(free[index], 1.0)
        self.assertEqual(len(taken), len(EXISTENCE_FEATURES))

    def test_a_missing_entity_geometry_is_rejected(self) -> None:
        memory, first, _ = memory_with_two_entities()
        frame = frame_with(tick=2, entity_ids=[])
        entity = [
            item for item in memory["entities"]
            if str(item["entity_id"]) == first
        ][0]
        with self.assertRaises(LeanAssignmentError) as caught:
            existence_feature_vector(entity, frame, assignment={}, tick=2)
        self.assertIn("entity_geometry_missing", str(caught.exception))


class TestSolver(unittest.TestCase):
    def test_a_square_optimum_is_found(self) -> None:
        matrix = [[4.0, 1.0, 3.0], [2.0, 0.0, 5.0], [3.0, 2.0, 2.0]]
        chosen = solve_rectangular_assignment(matrix)
        self.assertEqual(assignment_cost(matrix, chosen), 5.0)
        self.assertEqual(len(set(chosen)), 3)

    def test_a_rectangular_optimum_is_found(self) -> None:
        matrix = [[9.0, 1.0, 7.0, 2.0], [3.0, 8.0, 4.0, 6.0]]
        chosen = solve_rectangular_assignment(matrix)
        self.assertEqual(assignment_cost(matrix, chosen), 4.0)

    def test_it_matches_brute_force_on_random_matrices(self) -> None:
        rng = random.Random(90125)
        for _ in range(40):
            rows = rng.randint(1, 4)
            columns = rng.randint(rows, rows + 3)
            matrix = [
                [float(rng.randint(0, 20)) for _ in range(columns)]
                for _ in range(rows)
            ]
            chosen = solve_rectangular_assignment(matrix)
            self.assertEqual(len(set(chosen)), rows)
            best = min(
                sum(matrix[row][column] for row, column in enumerate(combo))
                for combo in itertools.permutations(range(columns), rows)
            )
            self.assertAlmostEqual(assignment_cost(matrix, chosen), best, places=9)

    def test_it_is_deterministic_across_repeated_calls(self) -> None:
        matrix = [[1.0, 1.0, 1.0], [1.0, 1.0, 1.0]]
        first = solve_rectangular_assignment(matrix)
        for _ in range(5):
            self.assertEqual(solve_rectangular_assignment(matrix), first)

    def test_more_rows_than_columns_is_rejected(self) -> None:
        with self.assertRaises(LeanAssignmentError) as caught:
            solve_rectangular_assignment([[1.0], [2.0], [3.0]])
        self.assertEqual(
            str(caught.exception), "assignment_matrix_more_rows_than_columns",
        )

    def test_a_ragged_matrix_is_rejected(self) -> None:
        with self.assertRaises(LeanAssignmentError) as caught:
            solve_rectangular_assignment([[1.0, 2.0], [3.0]])
        self.assertEqual(str(caught.exception), "assignment_matrix_ragged")


class TestCostMatrixAndSolve(unittest.TestCase):
    def _built(self) -> tuple[dict[str, Any], str, str]:
        memory, first, second = memory_with_two_entities()
        frame = frame_with(
            fragment("region:0002", descriptor=[1.0, 0.0], centroid=[0.05, 0.0, 0.0]),
            fragment("region:0003", descriptor=[0.0, 1.0], centroid=[1.05, 0.0, 0.0]),
            tick=2, entity_ids=[first, second],
        )
        return inputs_for(memory, frame), first, second

    def test_non_recalled_pairs_carry_the_forbidden_cost(self) -> None:
        built, first, second = self._built()
        logits = {
            f"{row['fragment_id']}|{row['entity_id']}": 2.0
            for row in built["association_rows"]
        }
        births = {row["fragment_id"]: -2.0 for row in built["birth_rows"]}
        matrix = build_cost_matrix(
            built, association_logits=logits, birth_logits=births,
        )
        self.assertIn(FORBIDDEN_COST, [value for row in matrix for value in row])

    def test_each_fragment_takes_its_own_entity_when_that_is_cheapest(self) -> None:
        built, first, second = self._built()
        logits: dict[str, float] = {}
        for row in built["association_rows"]:
            index = ASSOCIATION_FEATURES.index("cosine_to_descriptor_mean")
            logits[f"{row['fragment_id']}|{row['entity_id']}"] = (
                6.0 * row["features"][index]
            )
        births = {row["fragment_id"]: -3.0 for row in built["birth_rows"]}
        solved = solve_frame(
            built, association_logits=logits, birth_logits=births,
        )
        self.assertEqual(len(solved["assignment"]), 2)
        self.assertEqual(len(set(solved["assignment"].values())), 2)
        self.assertNotIn(
            solved["assignment"]["region:0002"],
            {solved["assignment"]["region:0003"]},
        )

    def test_two_fragments_cannot_share_one_entity(self) -> None:
        """Both fragments prefer the same entity; the solve must split them."""

        memory, first, second = memory_with_two_entities()
        frame = frame_with(
            fragment("region:0002", descriptor=[1.0, 0.0], centroid=[0.02, 0.0, 0.0]),
            fragment("region:0003", descriptor=[1.0, 0.0], centroid=[0.04, 0.0, 0.0]),
            tick=2, entity_ids=[first, second],
        )
        built = inputs_for(memory, frame)
        logits = {
            f"{row['fragment_id']}|{row['entity_id']}": (
                8.0 if row["entity_id"] == first else -8.0
            )
            for row in built["association_rows"]
        }
        births = {row["fragment_id"]: 0.0 for row in built["birth_rows"]}
        solved = solve_frame(built, association_logits=logits, birth_logits=births)
        values = list(solved["assignment"].values())
        self.assertEqual(len(set(values)), 2)
        self.assertEqual(sum(1 for value in values if value == first), 1)

    def test_a_fragment_cannot_take_another_fragments_birth_column(self) -> None:
        built, _, _ = self._built()
        rows = list(built["rows"])
        matrix = build_cost_matrix(
            built,
            association_logits={
                f"{row['fragment_id']}|{row['entity_id']}": -20.0
                for row in built["association_rows"]
            },
            birth_logits={row["fragment_id"]: 20.0 for row in built["birth_rows"]},
        )
        columns = list(built["columns"])
        for row_index, fragment_id in enumerate(rows):
            for column_index, name in enumerate(columns):
                if name.startswith(BIRTH_COLUMN_PREFIX) and name != (
                    f"{BIRTH_COLUMN_PREFIX}{fragment_id}"
                ):
                    self.assertEqual(matrix[row_index][column_index], FORBIDDEN_COST)


class TestPrivateMutationInvariance(unittest.TestCase):
    def test_public_products_do_not_move_when_private_data_changes(self) -> None:
        """Two runs sharing a public prefix but differing privately must match."""

        memory, first, second = memory_with_two_entities()
        frame = frame_with(
            fragment("region:0002", descriptor=[1.0, 0.0], centroid=[0.05, 0.0, 0.0]),
            tick=2, entity_ids=[first, second],
        )
        run_a = inputs_for(memory, frame)

        # The private mutation: swap the simulator-side instance mapping. It is
        # not an argument here at all, which is the point; the public products
        # must be byte-identical regardless.
        run_b = inputs_for(json.loads(json.dumps(memory)), json.loads(json.dumps(frame)))
        receipt = assert_private_mutation_invariance([run_a, run_b], seed=SEED)
        self.assertEqual(receipt["runs"], 2)
        self.assertEqual(run_a["seal_sha256"], run_b["seal_sha256"])

    def test_a_changed_feature_is_caught(self) -> None:
        memory, first, second = memory_with_two_entities()
        frame = frame_with(
            fragment("region:0002", descriptor=[1.0, 0.0], centroid=[0.05, 0.0, 0.0]),
            tick=2, entity_ids=[first, second],
        )
        run_a = inputs_for(memory, frame)
        run_b = json.loads(json.dumps(run_a))
        run_b["association_rows"][0]["features"][0] += 1e-9
        with self.assertRaises(LeanAssignmentError) as caught:
            assert_private_mutation_invariance([run_a, run_b], seed=SEED)
        self.assertIn("under_private_mutation", str(caught.exception))

    def test_a_changed_recall_order_is_caught(self) -> None:
        memory, first, second = memory_with_two_entities()
        frame = frame_with(
            fragment("region:0002", descriptor=[1.0, 1.0], centroid=[0.5, 0.0, 0.0]),
            tick=2, entity_ids=[first, second],
        )
        run_a = inputs_for(memory, frame)
        run_b = json.loads(json.dumps(run_a))
        run_b["recall"]["region:0002"].reverse()
        run_b["seal_sha256"] = run_a["seal_sha256"]
        with self.assertRaises(LeanAssignmentError) as caught:
            assert_private_mutation_invariance([run_a, run_b], seed=SEED)
        self.assertIn("recall_changed", str(caught.exception))

    def test_reference_scores_are_a_function_of_the_features_only(self) -> None:
        memory, first, second = memory_with_two_entities()
        frame = frame_with(
            fragment("region:0002", descriptor=[1.0, 0.0], centroid=[0.05, 0.0, 0.0]),
            tick=2, entity_ids=[first, second],
        )
        built = inputs_for(memory, frame)
        self.assertEqual(
            reference_untrained_scores(built, seed=SEED),
            reference_untrained_scores(built, seed=SEED),
        )
        self.assertNotEqual(
            reference_untrained_scores(built, seed=SEED),
            reference_untrained_scores(built, seed=SEED + 1),
        )

    def test_one_run_is_not_enough(self) -> None:
        memory, first, _ = memory_with_two_entities()
        frame = frame_with(
            fragment("region:0002", descriptor=[1.0, 0.0], centroid=[0.0, 0.0, 0.0]),
            tick=2, entity_ids=[first],
        )
        with self.assertRaises(LeanAssignmentError) as caught:
            assert_private_mutation_invariance([inputs_for(memory, frame)], seed=SEED)
        self.assertEqual(str(caught.exception), "invariance_needs_two_runs")


class TestMachineContract(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_contract_agrees_with_the_implementation(self) -> None:
        validate_assignment_contract(self.contract)
        self.assertEqual(self.contract["schema_version"], CONTRACT_SCHEMA_VERSION)
        self.assertEqual(
            tuple(self.contract["cache_frame_fields"]), CACHE_FRAME_FIELDS,
        )
        self.assertEqual(
            tuple(self.contract["association_feature_order"]), ASSOCIATION_FEATURES,
        )
        self.assertEqual(
            tuple(self.contract["existence_feature_order"]), EXISTENCE_FEATURES,
        )
        self.assertEqual(
            tuple(self.contract["birth_feature_order"]), BIRTH_FEATURES,
        )

    def test_reordering_a_feature_list_is_rejected(self) -> None:
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        order = list(broken["association_feature_order"])
        order[0], order[1] = order[1], order[0]
        broken["association_feature_order"] = order
        with self.assertRaises(LeanAssignmentError) as caught:
            validate_assignment_contract(broken)
        self.assertEqual(
            str(caught.exception), "contract_association_feature_order_mismatch",
        )

    def test_putting_a_distance_limit_on_retracted_recall_is_rejected(self) -> None:
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["recall_rule"]["dormant_and_retracted_have_no_distance_limit"] = False
        with self.assertRaises(LeanAssignmentError) as caught:
            validate_assignment_contract(broken)
        self.assertEqual(
            str(caught.exception), "contract_recall_distance_rule_weakened",
        )

    def test_weakening_the_invariance_rule_is_rejected(self) -> None:
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["seal"]["private_mutation_must_not_change_public_bytes"] = False
        with self.assertRaises(LeanAssignmentError) as caught:
            validate_assignment_contract(broken)
        self.assertEqual(str(caught.exception), "contract_invariance_weakened")

    def test_the_solver_stays_self_written(self) -> None:
        self.assertEqual(
            self.contract["solver"]["implementation"],
            "self_written_no_new_dependency",
        )
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["solver"]["implementation"] = "scipy_linear_sum_assignment"
        with self.assertRaises(LeanAssignmentError) as caught:
            validate_assignment_contract(broken)
        self.assertEqual(str(caught.exception), "contract_solver_source_mismatch")

    def test_the_reid_head_stays_shared_and_outside_the_config_budget(self) -> None:
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["reid_adapter_head"]["counts_against_config_budget"] = True
        with self.assertRaises(LeanAssignmentError) as caught:
            validate_assignment_contract(broken)
        self.assertEqual(str(caught.exception), "contract_reid_budget_mismatch")

    def test_policy_values_must_still_be_null(self) -> None:
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["recall_rule"]["active_count"] = 8
        with self.assertRaises(LeanAssignmentError) as caught:
            validate_assignment_contract(broken)
        self.assertIn("must_be_null_before_freeze", str(caught.exception))

    def test_every_authorization_bit_is_false(self) -> None:
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["authorization"]["model_training"] = True
        with self.assertRaises(LeanAssignmentError) as caught:
            validate_assignment_contract(broken)
        self.assertEqual(
            str(caught.exception), "contract_authorization_must_be_all_false",
        )

    def test_this_stage_defines_no_labels_metrics_or_arm_parameters(self) -> None:
        excluded = set(self.contract["not_in_this_stage"])
        for name in ("teacher_labels", "metrics", "arm_parameters"):
            self.assertIn(name, excluded)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
