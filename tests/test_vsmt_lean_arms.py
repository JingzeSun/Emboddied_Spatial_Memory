"""D-224 / S0-05 tests for the control arms, ablations and configuration grids.

The continue gate for S0-05 is: every method grid is at most twelve and
pre-registered; rule arms have no gradient; every boolean claim in the
contract is bound.  The three D-224-R preconditions (graded costs inside
the gate, a no-gate option in every rule arm's grid, a registered sentinel
for ineligible pairs) each have a positive and a negative case, and the
rule arms are run through the real S0-03 solver on hand-built frames.
Nothing here is a result.
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

from vsmt.lean_assignment import (  # noqa: E402
    build_assignment_inputs,
    seal_solution_and_existence,
    solve_frame,
)
from vsmt.lean_memory import apply_program, empty_memory  # noqa: E402
from vsmt.lean_arms import (  # noqa: E402
    ABLATION_ARMS,
    ALL_ARMS,
    CONTRACT_SCHEMA_VERSION,
    CONTROL_ARMS,
    EXPECTED_BOOLEAN_CLAIMS,
    GRID_PARAMETERS,
    INELIGIBLE_LOGIT,
    MAX_CONFIGS_PER_METHOD,
    NULL_POLICY_PATHS,
    REACTIVATES_RETRACTED,
    RULINGS_DECISION_ID,
    SELECTION_METRIC,
    VOCABULARY,
    LeanArmsError,
    apply_no_version,
    assert_config_budget,
    assert_no_gate_option,
    assert_no_sentinel_chosen,
    assert_split_allowed,
    compile_program,
    ctx_admission,
    eligible_existence_rows,
    elu_p_existence,
    elu_p_observe_matches,
    enumerate_configs,
    gate_association_logits,
    hand_cost_association_logits,
    hand_cost_existence,
    learned_existence,
    low_association_logits,
    never_retract,
    rac_existence,
    rac_observe_matches,
    sentinel_pairs,
    skip_existence,
    validate_arms_contract,
)


CONTRACT_PATH = PROJECT_ROOT / "configs" / "vsmt" / "lean_s0_arms_v1.json"
METHOD_ID = "vsmt.lean.test.v1"
RECALL = {"local_count": 2, "global_count": 2, "local_radius_m": 1.0}
BIRTH_RADIUS = 1.0


def digest(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def fragment(fragment_id: str, *, descriptor: list[float], centroid: list[float]) -> dict[str, Any]:
    return {
        "fragment_id": fragment_id,
        "descriptor": list(descriptor),
        "centroid_m": list(centroid),
        "aabb_min_m": [value - 0.1 for value in centroid],
        "aabb_max_m": [value + 0.1 for value in centroid],
        "pixel_count": 400,
        "depth_valid_ratio": 1.0,
        "supported_by": None,
    }


def memory_fragment(fragment_id: str, *, descriptor: list[float], centroid: list[float]) -> dict[str, Any]:
    item = fragment(fragment_id, descriptor=descriptor, centroid=centroid)
    del item["depth_valid_ratio"]
    return item


def frame_with(*fragments: Mapping[str, Any], tick: int, geometry: Mapping[str, tuple[float, float]], seed: str = "f2") -> dict[str, Any]:
    return {
        "frame_digest": digest(seed),
        "tick": tick,
        "camera_position_m": [0.0, 1.5, -1.0],
        "camera_forward": [0.0, 0.0, 1.0],
        "fragments": [dict(item) for item in fragments],
        "entity_geometry": {
            entity_id: {"should_be_visible_ratio": visible, "free_space_coverage_ratio": coverage}
            for entity_id, (visible, coverage) in geometry.items()
        },
    }


def step(memory: Mapping[str, Any], seed: str, operations: list[dict[str, Any]], *, limit: int = 2) -> dict[str, Any]:
    return apply_program(
        memory, {"frame_digest": digest(seed), "operations": operations},
        method_id=METHOD_ID, dormancy_missed_opportunity_limit=limit,
    )


def two_entity_memory() -> tuple[dict[str, Any], str, str]:
    """A mug at the origin and a book one metre away, both born at tick 1."""

    memory = step(empty_memory(episode_id="ep-0001"), "f1", [
        {"atom": "BIRTH", "fragment": memory_fragment("region:0000", descriptor=[1.0, 0.0], centroid=[0.0, 0.0, 0.0])},
        {"atom": "BIRTH", "fragment": memory_fragment("region:0001", descriptor=[0.0, 1.0], centroid=[1.0, 0.0, 0.0])},
    ])
    by_fragment = {entity["evidence"][0]["fragment_id"]: str(entity["entity_id"]) for entity in memory["entities"]}
    return memory, by_fragment["region:0000"], by_fragment["region:0001"]


def inputs_for(memory: Mapping[str, Any], frame: Mapping[str, Any]) -> dict[str, Any]:
    return build_assignment_inputs(frame, memory, birth_neighbourhood_radius_m=BIRTH_RADIUS, **RECALL)


def states_of(memory: Mapping[str, Any]) -> dict[str, str]:
    return {str(entity["entity_id"]): str(entity["state"]) for entity in memory["entities"]}


def existence_rows_for(memory: Mapping[str, Any], frame: Mapping[str, Any], logits: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    inputs = inputs_for(memory, frame)
    solved = solve_frame(inputs, association_logits=logits["association_logits"], birth_logits=logits["birth_logits"])
    stage_b = seal_solution_and_existence(solved, frame, memory, inputs=inputs)
    return stage_b["existence_rows"], list(stage_b["existence_feature_order"])


class TestGateLogits(unittest.TestCase):
    def setUp(self) -> None:
        self.memory, self.mug, self.book = two_entity_memory()
        self.frame = frame_with(
            fragment("region:0002", descriptor=[0.9, 0.1], centroid=[0.1, 0.0, 0.0]),
            fragment("region:0003", descriptor=[0.8, 0.2], centroid=[3.0, 0.0, 0.0]),
            tick=2, geometry={self.mug: (0.9, 0.1), self.book: (0.9, 0.1)},
        )
        self.inputs = inputs_for(self.memory, self.frame)

    def test_inside_the_gate_the_logit_is_the_cosine_not_a_constant(self) -> None:
        out = gate_association_logits(self.inputs, theta_a=0.5, d_a=1.0, reactivates_retracted=True)
        near = out["association_logits"][f"region:0002|{self.mug}"]
        self.assertGreater(near, 0.99)
        self.assertLess(near, 1.0)
        self.assertEqual(out["birth_logits"], {"region:0002": 0.5, "region:0003": 0.5})

    def test_below_theta_or_beyond_d_a_is_the_sentinel(self) -> None:
        out = gate_association_logits(self.inputs, theta_a=0.5, d_a=1.0, reactivates_retracted=True)
        self.assertEqual(out["association_logits"][f"region:0002|{self.book}"], INELIGIBLE_LOGIT)
        self.assertEqual(out["association_logits"][f"region:0003|{self.mug}"], INELIGIBLE_LOGIT)

    def test_a_null_gate_admits_a_distant_candidate(self) -> None:
        out = gate_association_logits(self.inputs, theta_a=0.5, d_a=None, reactivates_retracted=True)
        self.assertGreater(out["association_logits"][f"region:0003|{self.mug}"], 0.9)

    def test_a_retracted_entity_is_ineligible_unless_the_arm_reactivates(self) -> None:
        retracted = step(self.memory, "f2", [{"atom": "RETRACT", "entity_id": self.mug}])
        frame = frame_with(
            fragment("region:0002", descriptor=[0.9, 0.1], centroid=[0.1, 0.0, 0.0]),
            tick=3, geometry={self.book: (0.9, 0.1)}, seed="f3",
        )
        inputs = inputs_for(retracted, frame)
        rac = gate_association_logits(inputs, theta_a=0.5, d_a=None, reactivates_retracted=REACTIVATES_RETRACTED["RAC"])
        elu = gate_association_logits(inputs, theta_a=0.5, d_a=None, reactivates_retracted=REACTIVATES_RETRACTED["ELU-P"])
        self.assertEqual(rac["association_logits"][f"region:0002|{self.mug}"], INELIGIBLE_LOGIT)
        self.assertGreater(elu["association_logits"][f"region:0002|{self.mug}"], 0.9)

    def test_theta_outside_the_cosine_range_is_rejected(self) -> None:
        with self.assertRaises(LeanArmsError):
            gate_association_logits(self.inputs, theta_a=1.5, d_a=None, reactivates_retracted=True)


class TestLowLogits(unittest.TestCase):
    def setUp(self) -> None:
        self.memory, self.mug, self.book = two_entity_memory()
        self.frame = frame_with(
            fragment("region:0002", descriptor=[0.5, 0.5], centroid=[0.2, 0.0, 0.0]),
            fragment("region:0003", descriptor=[0.5, 0.5], centroid=[4.0, 0.0, 0.0]),
            tick=2, geometry={self.mug: (0.9, 0.1), self.book: (0.9, 0.1)},
        )
        self.inputs = inputs_for(self.memory, self.frame)

    def test_the_nearest_entity_scores_highest_and_birth_sits_at_the_gate(self) -> None:
        out = low_association_logits(self.inputs, d_low=1.5)
        self.assertAlmostEqual(out["association_logits"][f"region:0002|{self.mug}"], -0.2)
        self.assertAlmostEqual(out["association_logits"][f"region:0002|{self.book}"], -0.8)
        self.assertEqual(out["association_logits"][f"region:0003|{self.mug}"], INELIGIBLE_LOGIT)
        self.assertEqual(out["birth_logits"]["region:0002"], -1.5)

    def test_with_no_gate_any_recalled_entity_beats_birth(self) -> None:
        out = low_association_logits(self.inputs, d_low=None)
        far = out["association_logits"][f"region:0003|{self.book}"]
        self.assertNotEqual(far, INELIGIBLE_LOGIT)
        self.assertLess(out["birth_logits"]["region:0003"], far)


class TestRuleArmsThroughTheRealSolver(unittest.TestCase):
    """The three D-224-R preconditions, exercised end to end on S0-03."""

    def setUp(self) -> None:
        self.memory, self.mug, self.book = two_entity_memory()

    def _solve(self, memory: Mapping[str, Any], frame: Mapping[str, Any], logits: Mapping[str, Any]) -> dict[str, str]:
        inputs = inputs_for(memory, frame)
        solved = solve_frame(inputs, association_logits=logits["association_logits"], birth_logits=logits["birth_logits"])
        assert_no_sentinel_chosen(solved["assignment"], logits["association_logits"])
        return solved["assignment"]

    def test_graded_costs_let_the_higher_cosine_win_the_contested_entity(self) -> None:
        frame = frame_with(
            fragment("region:0002", descriptor=[0.8, 0.2], centroid=[0.2, 0.0, 0.0]),
            fragment("region:0003", descriptor=[0.95, 0.05], centroid=[0.1, 0.0, 0.0]),
            tick=2, geometry={self.mug: (0.9, 0.1), self.book: (0.9, 0.1)},
        )
        inputs = inputs_for(self.memory, frame)
        logits = gate_association_logits(inputs, theta_a=0.5, d_a=1.0, reactivates_retracted=False)
        assignment = self._solve(self.memory, frame, logits)
        self.assertEqual(assignment["region:0003"], self.mug)
        self.assertEqual(assignment["region:0002"], "birth:region:0002")

    def test_a_flat_cost_would_have_let_the_entity_id_order_decide(self) -> None:
        frame = frame_with(
            fragment("region:0002", descriptor=[0.8, 0.2], centroid=[0.2, 0.0, 0.0]),
            fragment("region:0003", descriptor=[0.95, 0.05], centroid=[0.1, 0.0, 0.0]),
            tick=2, geometry={self.mug: (0.9, 0.1), self.book: (0.9, 0.1)},
        )
        inputs = inputs_for(self.memory, frame)
        graded = gate_association_logits(inputs, theta_a=0.5, d_a=1.0, reactivates_retracted=False)
        flat = {
            "association_logits": {
                key: (1.0 if value != INELIGIBLE_LOGIT else value)
                for key, value in graded["association_logits"].items()
            },
            "birth_logits": dict(graded["birth_logits"]),
        }
        flat_assignment = self._solve(self.memory, frame, flat)
        # With every eligible cost equal, the mug goes to the smaller row (fragment id), not the better match.
        self.assertEqual(flat_assignment["region:0002"], self.mug)
        self.assertEqual(flat_assignment["region:0003"], "birth:region:0003")

    def test_the_no_gate_option_re_associates_a_moved_object(self) -> None:
        frame = frame_with(
            fragment("region:0002", descriptor=[0.95, 0.05], centroid=[5.0, 0.0, 0.0]),
            tick=2, geometry={self.mug: (0.9, 0.1), self.book: (0.9, 0.1)},
        )
        inputs = inputs_for(self.memory, frame)
        self.assertIn(self.mug, inputs["recall"]["region:0002"])  # the global channel recalled it
        tight = self._solve(self.memory, frame, gate_association_logits(inputs, theta_a=0.5, d_a=1.0, reactivates_retracted=False))
        wide = self._solve(self.memory, frame, gate_association_logits(inputs, theta_a=0.5, d_a=None, reactivates_retracted=False))
        self.assertEqual(tight["region:0002"], "birth:region:0002")
        self.assertEqual(wide["region:0002"], self.mug)

    def test_the_sentinel_is_never_chosen_even_when_nothing_is_eligible(self) -> None:
        frame = frame_with(
            fragment("region:0002", descriptor=[-1.0, 0.0], centroid=[0.0, 0.0, 0.0]),
            tick=2, geometry={self.mug: (0.9, 0.1), self.book: (0.9, 0.1)},
        )
        inputs = inputs_for(self.memory, frame)
        logits = gate_association_logits(inputs, theta_a=0.5, d_a=None, reactivates_retracted=False)
        self.assertEqual(len(sentinel_pairs(logits["association_logits"])), 2)
        assignment = self._solve(self.memory, frame, logits)
        self.assertEqual(assignment, {"region:0002": "birth:region:0002"})

    def test_a_chosen_sentinel_pair_is_caught(self) -> None:
        with self.assertRaises(LeanArmsError) as caught:
            assert_no_sentinel_chosen({"f": "e"}, {"f|e": INELIGIBLE_LOGIT})
        self.assertEqual(str(caught.exception), "sentinel_pair_chosen:f|e")

    def test_elu_p_reactivates_a_retracted_entity_and_rac_recreates_it(self) -> None:
        retracted = step(self.memory, "f2", [{"atom": "RETRACT", "entity_id": self.mug}])
        frame = frame_with(
            fragment("region:0002", descriptor=[0.95, 0.05], centroid=[2.0, 0.0, 0.0]),
            tick=3, geometry={self.book: (0.9, 0.1)}, seed="f3",
        )
        inputs = inputs_for(retracted, frame)
        elu = self._solve(retracted, frame, gate_association_logits(inputs, theta_a=0.5, d_a=None, reactivates_retracted=True))
        rac = self._solve(retracted, frame, gate_association_logits(inputs, theta_a=0.5, d_a=None, reactivates_retracted=False))
        self.assertEqual(elu["region:0002"], self.mug)
        self.assertEqual(rac["region:0002"], "birth:region:0002")
        program = compile_program(elu, states_of(retracted), arm="ELU-P", existence_decisions={})
        self.assertEqual(program[0]["atom"], "REACTIVATE")
        with self.assertRaises(LeanArmsError) as caught:
            compile_program(elu, states_of(retracted), arm="RAC", existence_decisions={})
        self.assertEqual(str(caught.exception), "arm_cannot_reactivate_retracted:RAC")


class TestExistenceCandidates(unittest.TestCase):
    def setUp(self) -> None:
        self.memory, self.mug, self.book = two_entity_memory()

    def test_rows_are_filtered_by_visibility_and_state_with_counts(self) -> None:
        retracted = step(self.memory, "f2", [{"atom": "RETRACT", "entity_id": self.book}])
        frame = frame_with(tick=3, geometry={self.mug: (0.2, 0.0), self.book: (0.9, 0.9)}, seed="f3")
        inputs = inputs_for(retracted, frame)
        rows, order = existence_rows_for(retracted, frame, gate_association_logits(inputs, theta_a=0.5, d_a=None, reactivates_retracted=False))
        out = eligible_existence_rows(rows, order, visible_min_ratio=0.5)
        self.assertEqual(out["eligible"], [])
        self.assertEqual(out["excluded_not_visible"], [self.mug])
        self.assertEqual(out["excluded_retracted"], [self.book])
        visible = eligible_existence_rows(rows, order, visible_min_ratio=0.1)
        self.assertEqual([row["entity_id"] for row in visible["eligible"]], [self.mug])

    def test_taf_and_low_never_retract_and_assoc_only_skips(self) -> None:
        frame = frame_with(tick=2, geometry={self.mug: (0.9, 1.0), self.book: (0.9, 1.0)})
        inputs = inputs_for(self.memory, frame)
        rows, order = existence_rows_for(self.memory, frame, gate_association_logits(inputs, theta_a=0.5, d_a=None, reactivates_retracted=False))
        eligible = eligible_existence_rows(rows, order, visible_min_ratio=0.5)["eligible"]
        self.assertEqual(never_retract(eligible), {self.mug: "NOOP", self.book: "NOOP"})
        self.assertEqual(skip_existence(eligible), {})

    def test_elu_p_log_odds_fall_under_free_space_and_recover_on_a_match(self) -> None:
        frame = frame_with(tick=2, geometry={self.mug: (0.9, 1.0), self.book: (0.9, 0.0)})
        inputs = inputs_for(self.memory, frame)
        rows, order = existence_rows_for(self.memory, frame, gate_association_logits(inputs, theta_a=0.5, d_a=None, reactivates_retracted=True))
        eligible = eligible_existence_rows(rows, order, visible_min_ratio=0.5)["eligible"]
        params = {"initial_log_odds": 2.0, "persistence_log_decay_per_tick": 0.1, "free_space_weight": 1.5, "retract_threshold": 0.0}
        first = elu_p_existence(eligible, order, state={}, **params)
        self.assertEqual(first["decisions"], {self.mug: "NOOP", self.book: "NOOP"})
        self.assertAlmostEqual(first["state"][self.mug], 2.0 - 0.1 - 1.5)
        second = elu_p_existence(eligible, order, state=first["state"], **params)
        self.assertEqual(second["decisions"][self.mug], "RETRACT")
        self.assertEqual(second["decisions"][self.book], "NOOP")
        recovered = elu_p_observe_matches(second["state"], [self.mug], initial_log_odds=2.0, match_gain=3.0)
        self.assertGreater(recovered[self.mug], second["state"][self.mug])

    def test_rac_counts_consecutive_negative_renders_and_resets(self) -> None:
        frame = frame_with(tick=2, geometry={self.mug: (0.9, 0.8), self.book: (0.9, 0.2)})
        inputs = inputs_for(self.memory, frame)
        rows, order = existence_rows_for(self.memory, frame, gate_association_logits(inputs, theta_a=0.5, d_a=None, reactivates_retracted=False))
        eligible = eligible_existence_rows(rows, order, visible_min_ratio=0.5)["eligible"]
        first = rac_existence(eligible, order, state={}, rho_rac=0.5, n_rac=2)
        self.assertEqual(first["decisions"], {self.mug: "NOOP", self.book: "NOOP"})
        self.assertEqual(first["state"], {self.mug: 1, self.book: 0})
        second = rac_existence(eligible, order, state=first["state"], rho_rac=0.5, n_rac=2)
        self.assertEqual(second["decisions"][self.mug], "RETRACT")
        self.assertEqual(second["state"][self.mug], 0)
        cleared = rac_observe_matches({self.mug: 1}, [self.mug])
        self.assertEqual(cleared, {self.mug: 0})

    def test_learned_existence_thresholds_the_sigmoid(self) -> None:
        out = learned_existence({"e1": 2.0, "e2": -2.0}, tau_r=0.5)
        self.assertEqual(out, {"e1": "RETRACT", "e2": "NOOP"})
        with self.assertRaises(LeanArmsError):
            learned_existence({"e1": 0.0}, tau_r=1.0)


class TestCompileAndVocabulary(unittest.TestCase):
    def test_bind_reactivate_birth_and_existence_atoms(self) -> None:
        states = {"e1": "active", "e2": "dormant", "e3": "retracted"}
        program = compile_program(
            {"f1": "e1", "f2": "e2", "f3": "birth:f3"}, states, arm="VSMT-lean",
            existence_decisions={},
        )
        self.assertEqual([op["atom"] for op in program], ["BIND", "REACTIVATE", "BIRTH"])
        full = compile_program({"f1": "e1"}, states, arm="VSMT-lean", existence_decisions={"e2": "RETRACT", "e3": "NOOP"})
        self.assertEqual([op["atom"] for op in full], ["BIND", "RETRACT", "NOOP"])

    def test_assoc_only_rejects_anything_beyond_bind_and_birth(self) -> None:
        with self.assertRaises(LeanArmsError) as caught:
            compile_program({"f1": "e1"}, {"e1": "active"}, arm="AssocOnly", existence_decisions={"e2": "NOOP"})
        self.assertEqual(str(caught.exception), "atom_outside_arm_vocabulary:AssocOnly:NOOP")
        with self.assertRaises(LeanArmsError) as caught:
            compile_program({"f1": "e1"}, {"e1": "dormant"}, arm="AssocOnly", existence_decisions={})
        self.assertEqual(str(caught.exception), "atom_outside_arm_vocabulary:AssocOnly:REACTIVATE")

    def test_taf_may_reactivate_dormant_but_never_retract(self) -> None:
        program = compile_program({"f1": "e1"}, {"e1": "dormant"}, arm="TAF", existence_decisions={})
        self.assertEqual(program[0]["atom"], "REACTIVATE")
        with self.assertRaises(LeanArmsError) as caught:
            compile_program({}, {"e1": "active"}, arm="TAF", existence_decisions={"e1": "RETRACT"})
        self.assertEqual(str(caught.exception), "atom_outside_arm_vocabulary:TAF:RETRACT")

    def test_a_decision_on_an_assigned_entity_or_a_foreign_birth_column_is_rejected(self) -> None:
        with self.assertRaises(LeanArmsError) as caught:
            compile_program({"f1": "e1"}, {"e1": "active"}, arm="VSMT-lean", existence_decisions={"e1": "NOOP"})
        self.assertEqual(str(caught.exception), "existence_decision_on_assigned_entity:e1")
        with self.assertRaises(LeanArmsError) as caught:
            compile_program({"f1": "birth:f2"}, {}, arm="VSMT-lean", existence_decisions={})
        self.assertEqual(str(caught.exception), "fragment_took_another_birth_column")

    def test_every_arm_has_a_vocabulary_and_a_reactivation_flag(self) -> None:
        self.assertEqual(set(VOCABULARY), set(ALL_ARMS))
        self.assertEqual(set(REACTIVATES_RETRACTED), set(ALL_ARMS))
        self.assertEqual(VOCABULARY["AssocOnly"], ("BIND", "BIRTH"))
        self.assertNotIn("RETRACT", VOCABULARY["TAF"])
        self.assertNotIn("RETRACT", VOCABULARY["LOW"])


class TestHandCost(unittest.TestCase):
    """D-224-SW ruling S: stateless hand scores in the three head slots."""

    def setUp(self) -> None:
        self.memory, self.mug, self.book = two_entity_memory()

    def test_every_recalled_pair_is_scored_by_cosine_with_no_gate(self) -> None:
        retracted = step(self.memory, "f2", [{"atom": "RETRACT", "entity_id": self.mug}])
        frame = frame_with(
            fragment("region:0002", descriptor=[0.95, 0.05], centroid=[6.0, 0.0, 0.0]),
            tick=3, geometry={self.book: (0.9, 0.1)}, seed="f3",
        )
        inputs = inputs_for(retracted, frame)
        out = hand_cost_association_logits(inputs, theta_b=0.5)
        self.assertGreater(out["association_logits"][f"region:0002|{self.mug}"], 0.9)
        self.assertNotIn(INELIGIBLE_LOGIT, out["association_logits"].values())
        self.assertEqual(out["birth_logits"], {"region:0002": 0.5})
        solved = solve_frame(inputs, association_logits=out["association_logits"], birth_logits=out["birth_logits"])
        self.assertEqual(solved["assignment"]["region:0002"], self.mug)
        program = compile_program(solved["assignment"], states_of(retracted), arm="HandCost", existence_decisions={})
        self.assertEqual(program[0]["atom"], "REACTIVATE")

    def test_existence_is_this_frames_coverage_against_rho_h(self) -> None:
        frame = frame_with(tick=2, geometry={self.mug: (0.9, 0.8), self.book: (0.9, 0.2)})
        inputs = inputs_for(self.memory, frame)
        rows, order = existence_rows_for(self.memory, frame, hand_cost_association_logits(inputs, theta_b=0.5))
        eligible = eligible_existence_rows(rows, order, visible_min_ratio=0.5)["eligible"]
        self.assertEqual(hand_cost_existence(eligible, order, rho_h=0.5), {self.mug: "RETRACT", self.book: "NOOP"})
        with self.assertRaises(LeanArmsError):
            hand_cost_existence(eligible, order, rho_h=0.0)

    def test_hand_cost_has_no_distance_gate_and_its_own_grid(self) -> None:
        self.assertEqual(GRID_PARAMETERS["HandCost"], ("theta_b", "rho_h"))
        with self.assertRaises(LeanArmsError) as caught:
            assert_no_gate_option("HandCost", {"theta_b": [0.5], "rho_h": [0.5]})
        self.assertEqual(str(caught.exception), "arm_has_no_distance_gate:HandCost")


class TestNoVersion(unittest.TestCase):
    def test_retracted_entities_are_deleted_and_the_memory_resealed(self) -> None:
        memory, mug, book = two_entity_memory()
        memory = step(memory, "f2", [{"atom": "RETRACT", "entity_id": mug}])
        out = apply_no_version(memory)
        self.assertEqual(out["no_version_deleted"], [mug])
        self.assertEqual([entity["entity_id"] for entity in out["entities"]], [book])
        self.assertNotEqual(out["memory_digest"], memory["memory_digest"])
        untouched = apply_no_version(two_entity_memory()[0])
        self.assertEqual(untouched["no_version_deleted"], [])


class TestGridsAndGuards(unittest.TestCase):
    def test_configs_enumerate_in_registered_order(self) -> None:
        configs = enumerate_configs("TAF", {"theta_a": [0.5, 0.7], "d_a": [1.0, None]})
        self.assertEqual(configs[0], {"theta_a": 0.5, "d_a": 1.0})
        self.assertEqual(configs[-1], {"theta_a": 0.7, "d_a": None})
        self.assertEqual(assert_config_budget(configs), 4)
        self.assertEqual(enumerate_configs("AssocOnly", {}), [{}])

    def test_thirteen_configurations_are_rejected(self) -> None:
        configs = enumerate_configs("RAC", {"theta_a": [0.5], "d_a": [None], "rho_rac": [0.3, 0.5, 0.7, 0.9], "n_rac": [1, 2, 3]})
        self.assertEqual(len(configs), 12)
        assert_config_budget(configs)
        with self.assertRaises(LeanArmsError) as caught:
            assert_config_budget(configs + [{"theta_a": 0.6, "d_a": None, "rho_rac": 0.3, "n_rac": 1}])
        self.assertEqual(str(caught.exception), f"config_budget_exceeded:13>{MAX_CONFIGS_PER_METHOD}")

    def test_a_rule_arm_grid_without_the_no_gate_option_is_rejected(self) -> None:
        assert_no_gate_option("LOW", {"d_low": [0.5, None]})
        with self.assertRaises(LeanArmsError) as caught:
            assert_no_gate_option("TAF", {"theta_a": [0.5], "d_a": [1.0, 2.0]})
        self.assertEqual(str(caught.exception), "grid_lacks_no_gate_option:TAF.d_a")
        with self.assertRaises(LeanArmsError):
            assert_no_gate_option("VSMT-lean", {"tau_r": [0.5]})

    def test_mismatched_or_duplicate_grid_values_are_rejected(self) -> None:
        with self.assertRaises(LeanArmsError):
            enumerate_configs("TAF", {"theta_a": [0.5]})
        with self.assertRaises(LeanArmsError):
            enumerate_configs("LOW", {"d_low": [0.5, 0.5]})

    def test_llm_op_runs_on_validation_only(self) -> None:
        assert_split_allowed("LLM-op", "validation")
        assert_split_allowed("TAF", "test")
        with self.assertRaises(LeanArmsError) as caught:
            assert_split_allowed("LLM-op", "test")
        self.assertEqual(str(caught.exception), "split_not_allowed:LLM-op:test")
        with self.assertRaises(LeanArmsError):
            assert_split_allowed("LLM-op", "train")

    def test_ctx_is_admitted_only_when_amortization_error_is_the_largest_class(self) -> None:
        self.assertTrue(ctx_admission({"recall_miss": 10, "teacher_error": 5, "amortization_error": 20})["admitted"])
        self.assertFalse(ctx_admission({"recall_miss": 30, "teacher_error": 5, "amortization_error": 20})["admitted"])
        tie = ctx_admission({"recall_miss": 20, "teacher_error": 5, "amortization_error": 20})
        self.assertFalse(tie["admitted"])
        self.assertEqual(tie["largest"], "amortization_error")


class TestMachineContract(unittest.TestCase):
    def _fresh(self) -> dict[str, Any]:
        return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    @staticmethod
    def _set(contract: dict[str, Any], path: str, value: Any) -> None:
        node = contract
        parts = path.split(".")
        for part in parts[:-1]:
            node = node[part]
        node[parts[-1]] = value

    def test_contract_agrees_with_the_implementation(self) -> None:
        contract = self._fresh()
        validate_arms_contract(contract)
        self.assertEqual(contract["schema_version"], CONTRACT_SCHEMA_VERSION)
        self.assertEqual(tuple(contract["arms"]["controls"]), CONTROL_ARMS)
        self.assertEqual(tuple(contract["ablations"]["names"]), ABLATION_ARMS)
        self.assertEqual(len(contract["authorization"]), 6)
        for arm in ("TAF", "ELU-P", "RAC", "LOW"):
            self.assertEqual(tuple(contract["arms"][arm]["grid"].keys()), GRID_PARAMETERS[arm])

    def test_flipping_any_boolean_claim_is_rejected(self) -> None:
        self.assertGreaterEqual(len(EXPECTED_BOOLEAN_CLAIMS), 60)
        for path, expected in EXPECTED_BOOLEAN_CLAIMS.items():
            broken = self._fresh()
            self._set(broken, path, not expected)
            with self.assertRaises(LeanArmsError, msg=path) as caught:
                validate_arms_contract(broken)
            self.assertEqual(str(caught.exception), f"contract_claim_flipped:{path}", path)

    def test_an_unbound_or_missing_boolean_claim_is_rejected(self) -> None:
        broken = self._fresh()
        broken["arms"]["TAF"]["may_retract_quietly"] = True
        with self.assertRaises(LeanArmsError) as caught:
            validate_arms_contract(broken)
        self.assertEqual(str(caught.exception), "contract_unbound_boolean_claim:arms.TAF.may_retract_quietly")
        broken = self._fresh()
        del broken["budget"]["test_never_selects"]
        with self.assertRaises(LeanArmsError) as caught:
            validate_arms_contract(broken)
        self.assertEqual(str(caught.exception), "contract_missing_boolean_claim:budget.test_never_selects")

    def test_frozen_constants_are_bound(self) -> None:
        for path in ("cost_interface.ineligible_logit", "budget.max_full_configs_per_method", "budget.selection_metric", "arms.VSMT-lean.training.learning_rate", "arms.VSMT-lean.training.epochs"):
            broken = self._fresh()
            self._set(broken, path, -1)
            with self.assertRaises(LeanArmsError) as caught:
                validate_arms_contract(broken)
            self.assertEqual(str(caught.exception), f"contract_frozen_constant_mismatch:{path}")

    def test_policy_values_must_still_be_null(self) -> None:
        self.assertEqual(len(NULL_POLICY_PATHS), 6)
        for path in NULL_POLICY_PATHS:
            broken = self._fresh()
            self._set(broken, path, 0.5)
            with self.assertRaises(LeanArmsError) as caught:
                validate_arms_contract(broken)
            self.assertIn("must_be_null_before_freeze", str(caught.exception))

    def test_vocabulary_and_grid_parameter_changes_are_rejected(self) -> None:
        broken = self._fresh()
        broken["ablations"]["AssocOnly"]["vocabulary"] = ["BIND", "BIRTH", "RETRACT"]
        with self.assertRaises(LeanArmsError) as caught:
            validate_arms_contract(broken)
        self.assertEqual(str(caught.exception), "contract_vocabulary_mismatch:AssocOnly")
        broken = self._fresh()
        broken["arms"]["TAF"]["grid"]["extra_bias"] = {"values": None}
        with self.assertRaises(LeanArmsError) as caught:
            validate_arms_contract(broken)
        self.assertEqual(str(caught.exception), "contract_grid_parameters_mismatch:TAF")
        broken = self._fresh()
        broken["arms"]["LOW"]["gradient"] = "sgd"
        with self.assertRaises(LeanArmsError) as caught:
            validate_arms_contract(broken)
        self.assertEqual(str(caught.exception), "contract_rule_arm_gradient_mismatch:LOW")

    def test_a_frozen_grid_is_checked_for_budget_and_the_no_gate_option(self) -> None:
        frozen = self._fresh()
        frozen["arms"]["TAF"]["grid"]["theta_a"]["values"] = [0.5, 0.6, 0.7]
        frozen["arms"]["TAF"]["grid"]["d_a"]["values"] = [1.0, 2.0, None]
        validate_arms_contract(frozen)
        frozen["arms"]["TAF"]["grid"]["d_a"]["values"] = [1.0, 2.0]
        with self.assertRaises(LeanArmsError) as caught:
            validate_arms_contract(frozen)
        self.assertEqual(str(caught.exception), "grid_lacks_no_gate_option:TAF.d_a")
        frozen["arms"]["TAF"]["grid"]["d_a"]["values"] = [1.0, 2.0, 3.0, 4.0, None]
        with self.assertRaises(LeanArmsError) as caught:
            validate_arms_contract(frozen)
        self.assertEqual(str(caught.exception), "config_budget_exceeded:15>12")

    def test_the_rulings_and_the_label_source_are_bound(self) -> None:
        self.assertEqual(RULINGS_DECISION_ID, "D-224-SW")
        self.assertEqual(SELECTION_METRIC, "node_f1")
        broken = self._fresh()
        broken["user_rulings"]["decision_id"] = "D-224-XX"
        with self.assertRaises(LeanArmsError) as caught:
            validate_arms_contract(broken)
        self.assertEqual(str(caught.exception), "contract_rulings_decision_mismatch")
        broken = self._fresh()
        broken["ablations"]["HeuristicLabel"]["label_source_arm"] = "TAF"
        with self.assertRaises(LeanArmsError) as caught:
            validate_arms_contract(broken)
        self.assertEqual(str(caught.exception), "contract_heuristic_label_source_mismatch")

    def test_the_appendix_split_and_the_arm_lists_are_bound(self) -> None:
        broken = self._fresh()
        broken["appendix_arm"]["splits_allowed"] = ["validation", "test"]
        with self.assertRaises(LeanArmsError) as caught:
            validate_arms_contract(broken)
        self.assertEqual(str(caught.exception), "contract_appendix_split_mismatch")
        broken = self._fresh()
        broken["arms"]["main_table"] = ["VSMT-lean", "TAF", "ELU-P", "RAC", "LOW"]
        with self.assertRaises(LeanArmsError) as caught:
            validate_arms_contract(broken)
        self.assertEqual(str(caught.exception), "contract_main_table_mismatch")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
