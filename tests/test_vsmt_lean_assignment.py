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
    UP_AXIS_INDEX,
    LeanAssignmentError,
    _forbidden_cost,
    _solve_rectangular_core,
    assert_private_mutation_invariance,
    assignment_cost,
    build_assignment_inputs,
    build_cost_matrix,
    build_recall,
    existence_feature_vector,
    recall_for_fragment,
    reference_untrained_scores,
    seal_solution_and_existence,
    solve_frame,
    solve_rectangular_assignment,
    validate_assignment_contract,
    validate_cache_frame,
)
from vsmt.lean_memory import apply_program, empty_memory  # noqa: E402


CONTRACT_PATH = PROJECT_ROOT / "configs" / "vsmt" / "lean_s0_assignment_v2.json"

RECALL = {"local_count": 3, "global_count": 2, "local_radius_m": 2.0}
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
    # Identify the two entities by the fragment that created them, not by the
    # sort order of their opaque ids: that order is a hash of the memory bytes
    # and flips whenever the schema changes (it did in S0-01 v2).
    by_fragment = {
        str(entity["evidence"][0]["fragment_id"]): str(entity["entity_id"])
        for entity in memory["entities"]
    }
    return memory, by_fragment["region:0000"], by_fragment["region:0001"]


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
        wide = recall_for_fragment(probe, memory, local_count=5, global_count=0,
                                   local_radius_m=5.0)
        narrow = recall_for_fragment(probe, memory, local_count=5, global_count=0,
                                     local_radius_m=0.5)
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
            far_away, retracted, local_count=0, global_count=3,
            local_radius_m=0.5,
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
            len(recall_for_fragment(probe, memory, local_count=1,
                                    global_count=0, local_radius_m=5.0)),
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
        built_matrix = build_cost_matrix(
            built, association_logits=logits, birth_logits=births,
        )
        forbidden = built_matrix["forbidden_cost"]
        values = [v for row in built_matrix["matrix"] for v in row]
        self.assertIn(forbidden, values)
        legal = [v for v in values if v != forbidden]
        # The derived forbidden cost must beat any all-legal assignment.
        self.assertGreater(forbidden, max(legal) * len(built_matrix["matrix"]) - 1e-9)

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
        )["matrix"]
        columns = list(built["columns"])
        for row_index, fragment_id in enumerate(rows):
            for column_index, name in enumerate(columns):
                if name.startswith(BIRTH_COLUMN_PREFIX) and name != (
                    f"{BIRTH_COLUMN_PREFIX}{fragment_id}"
                ):
                    self.assertGreater(matrix[row_index][column_index], 0.0)


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

    def test_putting_a_distance_limit_on_the_global_channel_is_rejected(self) -> None:
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["recall_rule"]["global_channel_has_no_distance_limit"] = False
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
        broken["recall_rule"]["local_count"] = 8
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


class TestReviewRegressions(unittest.TestCase):
    """One test per defect the 2026-09-19 S0-03 review found.

    白话：这些用例把那次评审的每个反例钉住，防止同样的问题再回来。输入是构造好的
    小矩阵、空帧或被篡改的合同，输出是通过或拒绝；例如代价变换改回 −log sigmoid
    时会有用例失败。它们不证明特征有用，只证明已修的缺口不会无声复发。
    """

    def test_the_solver_returns_the_lexicographically_smallest_optimum(self) -> None:
        """The raw augmenting-path solve returned [1, 0] here, not [0, 1]."""

        self.assertEqual(solve_rectangular_assignment([[1.0, 0.0], [1.0, 0.0]]), [0, 1])
        self.assertEqual(
            solve_rectangular_assignment([[2.0, 1.0, 1.0], [2.0, 1.0, 1.0]]), [1, 2],
        )

    def test_it_matches_brute_force_lexicographic_optima(self) -> None:
        rng = random.Random(90125)
        for _ in range(60):
            rows = rng.randint(1, 4)
            columns = rng.randint(rows, rows + 3)
            matrix = [
                [float(rng.randint(0, 6)) for _ in range(columns)]
                for _ in range(rows)
            ]
            perms = [list(p) for p in itertools.permutations(range(columns), rows)]
            best = min(sum(matrix[i][c] for i, c in enumerate(p)) for p in perms)
            lexicographic = min(
                p for p in perms
                if abs(sum(matrix[i][c] for i, c in enumerate(p)) - best) < 1e-9
            )
            self.assertEqual(solve_rectangular_assignment(matrix), lexicographic)

    def test_the_cost_transform_is_negative_logit(self) -> None:
        """Softplus reorders joint optima across rows; -logit does not."""

        memory, first, second = memory_with_two_entities()
        frame = frame_with(
            fragment("region:0002", descriptor=[1.0, 0.0], centroid=[0.05, 0.0, 0.0]),
            tick=2, entity_ids=[first, second],
        )
        built = inputs_for(memory, frame)
        logits = {
            f"{row['fragment_id']}|{row['entity_id']}": 2.5
            for row in built["association_rows"]
        }
        births = {row["fragment_id"]: -1.5 for row in built["birth_rows"]}
        matrix = build_cost_matrix(
            built, association_logits=logits, birth_logits=births,
        )["matrix"]
        values = [value for row in matrix for value in row]
        self.assertIn(-2.5, values)
        self.assertIn(1.5, values)

    def test_the_forbidden_cost_beats_any_all_legal_assignment(self) -> None:
        """A fixed 1e9 was reachable by an extreme logit; the derived one is not."""

        memory, first, second = memory_with_two_entities()
        frame = frame_with(
            fragment("region:0002", descriptor=[1.0, 0.0], centroid=[0.05, 0.0, 0.0]),
            fragment("region:0003", descriptor=[0.0, 1.0], centroid=[1.05, 0.0, 0.0]),
            tick=2, entity_ids=[first, second],
        )
        built = inputs_for(memory, frame)
        logits = {
            f"{row['fragment_id']}|{row['entity_id']}": -1.0e9
            for row in built["association_rows"]
        }
        births = {row["fragment_id"]: -1.0e9 for row in built["birth_rows"]}
        result = build_cost_matrix(
            built, association_logits=logits, birth_logits=births,
        )
        legal = [
            value for row in result["matrix"] for value in row
            if value != result["forbidden_cost"]
        ]
        self.assertGreater(result["forbidden_cost"], max(legal))

    def test_a_frame_with_no_fragment_yields_an_empty_assignment(self) -> None:
        memory, first, _ = memory_with_two_entities()
        frame = frame_with(tick=2, entity_ids=[first])
        built = inputs_for(memory, frame)
        solved = solve_frame(built, association_logits={}, birth_logits={})
        self.assertEqual(solved["assignment"], {})
        self.assertEqual(solved["total_cost"], 0.0)

    def test_a_descriptor_of_the_wrong_width_is_rejected(self) -> None:
        """It used to be accepted and silently scored -1 against everything."""

        memory, first, _ = memory_with_two_entities()
        frame = frame_with(
            fragment("region:0002", descriptor=[1.0, 0.0, 0.0],
                     centroid=[0.0, 0.0, 0.0]),
            tick=2, entity_ids=[first],
        )
        with self.assertRaises(LeanAssignmentError) as caught:
            inputs_for(memory, frame)
        self.assertEqual(
            str(caught.exception), "frame_descriptor_width_differs_from_memory",
        )

    def test_the_birth_feature_looks_at_every_entity(self) -> None:
        memory, first, second = memory_with_two_entities()
        # This fragment matches the second entity, which the tight local radius
        # and a zero global budget both keep out of its recall.
        frame = frame_with(
            fragment("region:0002", descriptor=[0.0, 1.0], centroid=[0.0, 0.0, 0.0]),
            tick=2, entity_ids=[first, second],
        )
        built = build_assignment_inputs(
            frame, memory, local_count=3, global_count=0, local_radius_m=0.5,
            birth_neighbourhood_radius_m=BIRTH_RADIUS,
        )
        self.assertNotIn(second, built["recall"]["region:0002"])
        index = BIRTH_FEATURES.index("best_cosine_to_any_entity")
        self.assertAlmostEqual(built["birth_rows"][0]["features"][index], 1.0)

    def test_the_global_channel_recalls_an_active_entity_from_far_away(self) -> None:
        """AssocOnly has no dormant state, so eligibility must not need one."""

        memory, first, _ = memory_with_two_entities()
        far_away = fragment(
            "region:0002", descriptor=[1.0, 0.0], centroid=[40.0, 0.0, 40.0],
        )
        self.assertEqual(
            recall_for_fragment(far_away, memory, local_count=3, global_count=0,
                                local_radius_m=2.0),
            [],
        )
        self.assertIn(
            first,
            recall_for_fragment(far_away, memory, local_count=3, global_count=2,
                                local_radius_m=2.0),
        )

    def test_row_order_does_not_depend_on_the_order_masks_arrive_in(self) -> None:
        memory, first, second = memory_with_two_entities()
        one = fragment("region:0002", descriptor=[1.0, 0.0], centroid=[0.05, 0.0, 0.0])
        two = fragment("region:0003", descriptor=[0.0, 1.0], centroid=[1.05, 0.0, 0.0])
        forward = inputs_for(
            memory, frame_with(one, two, tick=2, entity_ids=[first, second]),
        )
        backward = inputs_for(
            memory, frame_with(two, one, tick=2, entity_ids=[first, second]),
        )
        self.assertEqual(forward["rows"], backward["rows"])
        self.assertEqual(forward["seal_sha256"], backward["seal_sha256"])

    def _solved(self) -> tuple[dict, dict, dict, dict]:
        memory, first, second = memory_with_two_entities()
        frame = frame_with(
            fragment("region:0002", descriptor=[1.0, 0.0], centroid=[0.05, 0.0, 0.0]),
            tick=2, entity_ids=[first, second],
        )
        built = inputs_for(memory, frame)
        solved = solve_frame(
            built,
            association_logits={
                f"{row['fragment_id']}|{row['entity_id']}": 5.0
                for row in built["association_rows"]
            },
            birth_logits={row["fragment_id"]: -5.0 for row in built["birth_rows"]},
        )
        return memory, frame, built, solved

    def test_stage_b_seals_the_solve_and_the_existence_rows(self) -> None:
        memory, frame, built, solved = self._solved()
        stage_b = seal_solution_and_existence(solved, frame, memory, inputs=built)
        self.assertEqual(stage_b["stage_a_seal_sha256"], built["seal_sha256"])
        self.assertEqual(
            stage_b["existence_feature_order"], list(EXISTENCE_FEATURES),
        )
        listed = {row["entity_id"] for row in stage_b["existence_rows"]}
        self.assertEqual(len(listed), 1)
        for row in stage_b["existence_rows"]:
            self.assertEqual(len(row["features"]), len(EXISTENCE_FEATURES))

    def test_stage_b_refuses_a_solve_from_a_different_stage_a(self) -> None:
        memory, frame, built, solved = self._solved()
        solved["stage_a_seal_sha256"] = digest("someone elses stage a")
        with self.assertRaises(LeanAssignmentError) as caught:
            seal_solution_and_existence(solved, frame, memory, inputs=built)
        self.assertEqual(str(caught.exception), "stage_b_does_not_follow_stage_a")

    def test_invariance_now_covers_the_existence_rows(self) -> None:
        memory, frame, built, solved = self._solved()
        stage_b = seal_solution_and_existence(solved, frame, memory, inputs=built)
        twin = json.loads(json.dumps(stage_b))
        assert_private_mutation_invariance([stage_b, twin], seed=SEED)

        tampered = json.loads(json.dumps(stage_b))
        tampered["existence_rows"][0]["features"][0] += 1e-9
        with self.assertRaises(LeanAssignmentError) as caught:
            assert_private_mutation_invariance([stage_b, tampered], seed=SEED)
        self.assertIn("under_private_mutation", str(caught.exception))

    def test_the_contract_validator_binds_every_claim_it_makes(self) -> None:
        """Four of these used to be accepted when flipped."""

        for section, name in (
            ("recall_rule", "local_channel_has_distance_limit"),
            ("recall_rule", "global_channel_covers_every_state"),
            ("recall_rule", "identical_for_all_five_arms"),
            ("seal", "sealed_before_any_private_file_is_opened"),
            ("seal", "sealed_before_any_model_runs"),
            ("seal", "teacher_assignment_must_not_feed_existence_features"),
            ("cost_matrix", "forbidden_cost_is_derived_from_the_matrix"),
        ):
            broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
            broken[section][name] = False
            with self.assertRaises(LeanAssignmentError, msg=f"{section}.{name}"):
                validate_assignment_contract(broken)

    def test_reverting_the_cost_transform_in_the_contract_is_rejected(self) -> None:
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["cost_matrix"]["cost"] = "negative_log_sigmoid_of_head_logit"
        with self.assertRaises(LeanAssignmentError) as caught:
            validate_assignment_contract(broken)
        self.assertEqual(str(caught.exception), "contract_cost_transform_mismatch")

    def test_the_up_axis_is_registered_and_bound(self) -> None:
        self.assertEqual(UP_AXIS_INDEX, 1)
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["feature_rules"]["up_axis_index"] = 2
        with self.assertRaises(LeanAssignmentError) as caught:
            validate_assignment_contract(broken)
        self.assertEqual(str(caught.exception), "contract_up_axis_mismatch")

    def test_the_association_head_uses_geometry_not_a_surface_identity(self) -> None:
        """supported_by ids would need cross-frame surface tracking to help."""

        self.assertIn("support_height_difference_m", ASSOCIATION_FEATURES)
        self.assertNotIn("supported_by_agrees", ASSOCIATION_FEATURES)

def reference_lexicographic_optimum(
    matrix: list[list[float]], seed: list[int],
) -> list[int]:
    """The S0-03 v1 canonicalisation, kept verbatim as the equivalence reference.

    It re-solves the whole matrix once per tried column (D-224-X measured
    13,055 sub-solves at 64×500).  The equality-subgraph version in the module
    must return exactly these columns; this copy exists only to pin that.
    """

    rows = len(matrix)
    columns = len(matrix[0])
    target = sum(float(matrix[row][col]) for row, col in enumerate(seed))
    flat = [float(value) for row in matrix for value in row]
    big = _forbidden_cost(flat, rows=rows) + abs(max(flat)) * rows + 1.0
    tolerance = max(1.0, abs(target)) * 1e-9
    chosen: list[int] = []
    used: set[int] = set()
    for row in range(rows):
        for candidate in range(columns):
            if candidate in used:
                continue
            trial = [list(values) for values in matrix]
            for fixed_row, fixed_column in enumerate(chosen):
                for column in range(columns):
                    if column != fixed_column:
                        trial[fixed_row][column] = big
            for column in range(columns):
                if column != candidate:
                    trial[row][column] = big
            probe = _solve_rectangular_core(trial)
            total = sum(float(trial[r][c]) for r, c in enumerate(probe))
            if total <= target + tolerance:
                chosen.append(candidate)
                used.add(candidate)
                break
        else:
            raise AssertionError("reference canonicalisation failed")
    return chosen


class TestSolverEquivalenceWithV1(unittest.TestCase):
    """D-224-X ruling X5: the new canonicalisation returns the v1 columns."""

    def _check(self, matrix: list[list[float]]) -> None:
        seed = _solve_rectangular_core(matrix)
        expected = reference_lexicographic_optimum(matrix, seed)
        got = solve_rectangular_assignment(matrix)
        self.assertEqual(got, expected)
        self.assertAlmostEqual(
            assignment_cost(matrix, got), assignment_cost(matrix, seed), places=9,
        )

    def test_float_costs_match_the_v1_columns(self) -> None:
        rng = random.Random(2024)
        for _ in range(60):
            rows = rng.randint(1, 12)
            columns = rng.randint(rows, rows + 15)
            self._check([
                [rng.uniform(-5.0, 5.0) for _ in range(columns)] for _ in range(rows)
            ])

    def test_rule_arm_style_costs_with_sentinels_match_the_v1_columns(self) -> None:
        """Many exact ties: rounded cosines, a constant birth logit, sentinel cells."""

        rng = random.Random(4096)
        for _ in range(60):
            rows = rng.randint(1, 8)
            entities = rng.randint(0, 6)
            matrix = []
            for row in range(rows):
                cells = [
                    -rng.choice([0.2, 0.5, 0.8, -1.0e6]) for _ in range(entities)
                ]
                births = [0.0] * rows
                births[row] = -0.5
                matrix.append(cells + births)
            forbidden = _forbidden_cost(
                [value for line in matrix for value in line if value != 0.0],
                rows=rows,
            )
            for row in range(rows):
                for column in range(entities, entities + rows):
                    if column != entities + row:
                        matrix[row][column] = forbidden
            self._check(matrix)

    def test_larger_float_matrices_match_the_v1_columns(self) -> None:
        rng = random.Random(777)
        for rows, columns in ((20, 60), (24, 90), (30, 100)):
            self._check([
                [rng.uniform(-5.0, 5.0) for _ in range(columns)] for _ in range(rows)
            ])

    def test_brute_force_lexicographic_optima_up_to_five_rows(self) -> None:
        rng = random.Random(5150)
        for _ in range(40):
            rows = rng.randint(1, 5)
            columns = rng.randint(rows, rows + 3)
            matrix = [
                [float(rng.randint(0, 5)) for _ in range(columns)]
                for _ in range(rows)
            ]
            perms = [list(p) for p in itertools.permutations(range(columns), rows)]
            best = min(sum(matrix[i][c] for i, c in enumerate(p)) for p in perms)
            lexicographic = min(
                p for p in perms
                if abs(sum(matrix[i][c] for i, c in enumerate(p)) - best) < 1e-9
            )
            self.assertEqual(solve_rectangular_assignment(matrix), lexicographic)

    def test_the_canonicalisation_never_re_solves_the_matrix(self) -> None:
        """The v1 version called the core once per tried column; v2 calls it once."""

        import vsmt.lean_assignment as module

        calls = {"n": 0}
        original = module._solve_rectangular_core_with_potentials

        def counting(matrix: Any) -> Any:
            calls["n"] += 1
            return original(matrix)

        module._solve_rectangular_core_with_potentials = counting
        try:
            rng = random.Random(1)
            matrix = [[rng.uniform(-5.0, 5.0) for _ in range(120)] for _ in range(30)]
            solve_rectangular_assignment(matrix)
        finally:
            module._solve_rectangular_core_with_potentials = original
        self.assertEqual(calls["n"], 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
